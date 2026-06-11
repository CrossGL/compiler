if(NOT DEFINED CROSSGL_FAKE_SHADER_TOOL_SCRIPT)
  set(CROSSGL_FAKE_SHADER_TOOL_SCRIPT
      "${CMAKE_CURRENT_SOURCE_DIR}/tests/toolchain/FakeShaderTool.cmake")
endif()

if(CROSSGL_PYTHON3)
  add_test(NAME vulkan_native_profile_legacy_requested_level_optional_schema
    COMMAND "${CROSSGL_PYTHON3}"
      "${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py"
      --schema
        "${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/vulkan-native-profile-v1.schema.json"
      --instance
        "${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanNativeProfileLegacyOptimizationProfile.json")
endif()

function(crossgl_configure_fake_vulkan_native_toolchain out_dir
         assembler_behavior validator_behavior)
  set(optimizer_behavior "unavailable")
  if(ARGC GREATER 3)
    set(optimizer_behavior "${ARGV3}")
  endif()
  set(disassembler_behavior "unavailable")
  if(ARGC GREATER 4)
    set(disassembler_behavior "${ARGV4}")
  endif()
  set(tool_dir
      "${CMAKE_CURRENT_BINARY_DIR}/fake-toolchain/vulkan-${out_dir}-${assembler_behavior}-${validator_behavior}-${optimizer_behavior}-${disassembler_behavior}")
  file(MAKE_DIRECTORY "${tool_dir}")

  foreach(tool_name IN ITEMS spirv-as spirv-val spirv-opt spirv-dis)
    if(tool_name STREQUAL "spirv-as")
      set(tool_behavior "${assembler_behavior}")
    elseif(tool_name STREQUAL "spirv-val")
      set(tool_behavior "${validator_behavior}")
    elseif(tool_name STREQUAL "spirv-opt")
      set(tool_behavior "${optimizer_behavior}")
    else()
      set(tool_behavior "${disassembler_behavior}")
    endif()

    set(tool_log "${tool_dir}/${tool_name}.log")
    file(REMOVE "${tool_log}")
    if(tool_behavior STREQUAL "unavailable")
      continue()
    endif()

    if(tool_name STREQUAL "spirv-dis")
      set(disassembler_script "${tool_dir}/FakeSpirvDis.cmake")
      file(WRITE "${disassembler_script}" [=[
set(fake_tool_args "")
set(found_argument_separator OFF)
math(EXPR fake_last_arg "${CMAKE_ARGC} - 1")
foreach(index RANGE 0 ${fake_last_arg})
  if(found_argument_separator)
    list(APPEND fake_tool_args "${CMAKE_ARGV${index}}")
  elseif("${CMAKE_ARGV${index}}" STREQUAL "--")
    set(found_argument_separator ON)
  endif()
endforeach()

string(REPLACE ";" " " fake_tool_command "${fake_tool_args}")
file(APPEND "${FAKE_TOOL_LOG}"
     "spirv-dis ${FAKE_TOOL_BEHAVIOR}: ${fake_tool_command}\n")

list(LENGTH fake_tool_args fake_arg_count)
if(NOT fake_arg_count EQUAL 3)
  message(FATAL_ERROR
          "fake spirv-dis expected 3 arguments, got ${fake_arg_count}: ${fake_tool_command}")
endif()
list(GET fake_tool_args 0 fake_source)
list(GET fake_tool_args 1 fake_output_flag)
list(GET fake_tool_args 2 fake_output)
if(NOT fake_source MATCHES "\\.spv$")
  message(FATAL_ERROR
          "fake spirv-dis expected SPIR-V input ending in .spv, got ${fake_source}")
endif()
if(NOT fake_output_flag STREQUAL "-o")
  message(FATAL_ERROR "fake spirv-dis expected -o, got ${fake_output_flag}")
endif()
if(NOT fake_output MATCHES "\\.disassembly\\.spvasm$")
  message(FATAL_ERROR
          "fake spirv-dis expected output ending in .disassembly.spvasm, got ${fake_output}")
endif()
if(NOT EXISTS "${fake_source}")
  message(FATAL_ERROR
          "fake spirv-dis expected SPIR-V input to exist: ${fake_source}")
endif()

if(FAKE_TOOL_BEHAVIOR STREQUAL "failure")
  message(FATAL_ERROR "fake spirv-dis failure")
elseif(NOT FAKE_TOOL_BEHAVIOR STREQUAL "success")
  message(FATAL_ERROR
          "unknown fake spirv-dis behavior: ${FAKE_TOOL_BEHAVIOR}")
endif()

set(fake_assembly "${fake_source}")
string(REGEX REPLACE "\\.spv$" ".spvasm" fake_assembly "${fake_assembly}")
set(fake_disassembly "; CrossGL fake SPIR-V disassembly\n")
if(EXISTS "${fake_assembly}")
  file(STRINGS "${fake_assembly}" fake_entry_lines
       REGEX "^(OpEntryPoint|OpExecutionMode) ")
  foreach(fake_entry_line IN LISTS fake_entry_lines)
    string(APPEND fake_disassembly "${fake_entry_line}\n")
  endforeach()
else()
  string(APPEND fake_disassembly "OpEntryPoint GLCompute %main \"main\"\n")
endif()
file(WRITE "${fake_output}" "${fake_disassembly}")
      ]=])
      if(WIN32)
        file(TO_NATIVE_PATH "${CMAKE_COMMAND}" native_cmake_command)
        file(TO_NATIVE_PATH "${disassembler_script}" native_disassembler_script)
        file(WRITE "${tool_dir}/${tool_name}.cmd"
             "@echo off\n"
             "\"${native_cmake_command}\" -DFAKE_TOOL_BEHAVIOR=${tool_behavior} -DFAKE_TOOL_LOG=\"${tool_log}\" -P \"${native_disassembler_script}\" -- %*\n"
             "exit /b %ERRORLEVEL%\n")
      else()
        file(WRITE "${tool_dir}/${tool_name}"
             "#!/bin/sh\n"
             "exec \"${CMAKE_COMMAND}\" -DFAKE_TOOL_BEHAVIOR=${tool_behavior} -DFAKE_TOOL_LOG=\"${tool_log}\" -P \"${disassembler_script}\" -- \"$@\"\n")
        file(CHMOD "${tool_dir}/${tool_name}"
             PERMISSIONS
               OWNER_READ OWNER_WRITE OWNER_EXECUTE
               GROUP_READ GROUP_EXECUTE
               WORLD_READ WORLD_EXECUTE)
      endif()
      continue()
    endif()

    if(WIN32)
      file(TO_NATIVE_PATH "${CMAKE_COMMAND}" native_cmake_command)
      file(TO_NATIVE_PATH "${CROSSGL_FAKE_SHADER_TOOL_SCRIPT}"
           native_fake_tool_script)
      file(WRITE "${tool_dir}/${tool_name}.cmd"
           "@echo off\n"
           "\"${native_cmake_command}\" -DFAKE_TOOL_NAME=${tool_name} -DFAKE_TOOL_BEHAVIOR=${tool_behavior} -DFAKE_TOOL_LOG=\"${tool_log}\" -P \"${native_fake_tool_script}\" -- %*\n"
           "exit /b %ERRORLEVEL%\n")
    else()
      file(WRITE "${tool_dir}/${tool_name}"
           "#!/bin/sh\n"
           "exec \"${CMAKE_COMMAND}\" -DFAKE_TOOL_NAME=${tool_name} -DFAKE_TOOL_BEHAVIOR=${tool_behavior} -DFAKE_TOOL_LOG=\"${tool_log}\" -P \"${CROSSGL_FAKE_SHADER_TOOL_SCRIPT}\" -- \"$@\"\n")
      file(CHMOD "${tool_dir}/${tool_name}"
           PERMISSIONS
             OWNER_READ OWNER_WRITE OWNER_EXECUTE
             GROUP_READ GROUP_EXECUTE
             WORLD_READ WORLD_EXECUTE)
    endif()
  endforeach()

  set(${out_dir} "${tool_dir}" PARENT_SCOPE)
endfunction()

crossgl_configure_fake_vulkan_native_toolchain(
  CROSSGL_FAKE_VULKAN_SUCCESS_DIR success success)
crossgl_configure_fake_vulkan_native_toolchain(
  CROSSGL_FAKE_VULKAN_DISASSEMBLY_UNAVAILABLE_DIR success success)
crossgl_configure_fake_vulkan_native_toolchain(
  CROSSGL_FAKE_VULKAN_DISASSEMBLY_SUCCESS_DIR success success unavailable success)
crossgl_configure_fake_vulkan_native_toolchain(
  CROSSGL_FAKE_VULKAN_DISASSEMBLY_FAILURE_DIR success success unavailable failure)
crossgl_configure_fake_vulkan_native_toolchain(
  CROSSGL_FAKE_VULKAN_OPT_SUCCESS_DIR success success success)
crossgl_configure_fake_vulkan_native_toolchain(
  CROSSGL_FAKE_VULKAN_OPT_FAILURE_DIR success success failure)
crossgl_configure_fake_vulkan_native_toolchain(
  CROSSGL_FAKE_VULKAN_OPT_O0_DIR success success success)
crossgl_configure_fake_vulkan_native_toolchain(
  CROSSGL_FAKE_VULKAN_OPT_O1_DIR success success success)
crossgl_configure_fake_vulkan_native_toolchain(
  CROSSGL_FAKE_VULKAN_OPT_O2_DIR success success success)
crossgl_configure_fake_vulkan_native_toolchain(
  CROSSGL_FAKE_VULKAN_ASSEMBLER_FAILURE_DIR failure success)
crossgl_configure_fake_vulkan_native_toolchain(
  CROSSGL_FAKE_VULKAN_VALIDATOR_FAILURE_DIR success failure)
crossgl_configure_fake_vulkan_native_toolchain(
  CROSSGL_FAKE_VULKAN_ASSEMBLER_UNAVAILABLE_DIR unavailable success)
crossgl_configure_fake_vulkan_native_toolchain(
  CROSSGL_FAKE_VULKAN_VALIDATOR_UNAVAILABLE_DIR success unavailable)

add_test(NAME cglc_build_vulkan_native_fake_spirv_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-spirv-success.cglb
    -DEXPECTED_MODULE=StorageBufferComputeShader
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DOPT_LEVEL=O2
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageBufferComputeShader|targetLegalizationToolRequirements.target=vulkan|targetLegalizationToolRequirements.packageMode=native|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=0|targetLegalizationToolRequirements.optionalNativeToolMissing=false|targetLegalizationToolRequirements.optionalNativeToolStatus=not-required|artifacts.backendAssembly=backend/vulkan/StorageBufferComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/StorageBufferComputeShader.spv"
    "-DEXPECTED_MANIFEST_JSON_ARRAY_CONTAINS=targetLegalizationToolRequirements.requiredToolIds=vulkan.toolchain.spirv-as|targetLegalizationToolRequirements.requiredToolIds=vulkan.validation.spirv-val|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.vulkan.tool-requirements.present"
    "-DEXPECTED_MANIFEST_JSON_ARRAY_LENGTHS=targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=0|targetLegalizationToolRequirements.toolRequirementEvidenceIds=3"
    "-DEXPECTED_NATIVE_PROFILE_JSON_FIELDS=debug.optimization.tool=spirv-opt|debug.optimization.policy=use-when-available|debug.optimization.requestedLevel=O2|debug.optimization.level=-O|debug.optimization.status=skipped-tool-missing|debug.optimization.targetEnv=vulkan1.2|debug.optimization.toolStatus=missing"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/StorageBufferComputeShader.spvasm|artifactPath=backend/vulkan/StorageBufferComputeShader.spv|optimizationLevel=O2|optimizationEvidence.requestedLevel=O2|optimizationEvidence.effectiveLevel=none|optimizationEvidence.policy=use-when-available|optimizationEvidence.status=skipped-tool-missing|optimizationEvidence.tool=spirv-opt|optimizationEvidence.toolFlag=-O|validationStatus=validated"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageBufferComputeShader|nativeBinary=backend/vulkan/StorageBufferComputeShader.spv"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_VULKAN_SUCCESS_DIR}/spirv-as.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=spirv-as success: --target-env vulkan1.2"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_VULKAN_SUCCESS_DIR}/spirv-val.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=spirv-val success: --target-env vulkan1.2"
    -DEXPECTED_ABSENT_TOOL_LOG=${CROSSGL_FAKE_VULKAN_SUCCESS_DIR}/spirv-opt.log
    -DMODE=vulkan-build
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

crossgl_add_python_expect_test(
  NAME cglc_build_vulkan_native_fake_intrinsics_import_closure
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_INTRINSIC_COMPUTE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-intrinsics-import-closure.cglb
    -DEXPECTED_MODULE=IntrinsicComputeShader
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/IntrinsicComputeShader.spvasm|artifactPath=backend/vulkan/IntrinsicComputeShader.spv|spirvDependencies.extendedInstructionSets.0.resultId=%glsl_std_450|spirvDependencies.extendedInstructionSets.0.instructionSet=GLSL.std.450|validationStatus=validated"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=spirvDependencies.extendedInstructionSets=1|validationDiagnostics=0"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_ORDERED_CONTAINS=\"schemaVersion\"|\"kind\"|\"contractVersion\"|\"target\"|\"binaryKind\"|\"sourcePath\"|\"sourceHash\"|\"artifactPath\"|\"artifactHash\"|\"sizeBytes\"|\"spirvDependencies\"|\"toolchainProvenance\"|\"optimizationLevel\"|\"optimizationEvidence\"|\"validationStatus\"|\"validationDiagnostics\""
    "-DEXPECTED_SPVASM_CONTAINS=%glsl_std_450 = OpExtInstImport \"GLSL.std.450\"|OpExtInst %float %glsl_std_450 FAbs|OpExtInst %float %glsl_std_450 Sin|OpExtInst %float %glsl_std_450 Sqrt|OpExtInst %float %glsl_std_450 Pow|OpExtInst %vec4 %glsl_std_450 Normalize"
    "-DEXPECTED_SPVASM_ORDERED_CONTAINS=OpCapability Shader|%glsl_std_450 = OpExtInstImport \"GLSL.std.450\"|OpMemoryModel Logical GLSL450|OpEntryPoint GLCompute %compute_main \"main\"|OpExecutionMode %compute_main LocalSize 1 1 1"
    -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    -DMODE=vulkan-build)

add_test(NAME cglc_build_vulkan_native_fake_structured_decorations_validate
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-structured-decorations.cglb
    -DEXPECTED_MODULE=StorageBufferComputeShader
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_SPVASM_CONTAINS=OpMemoryModel Logical GLSL450|OpEntryPoint GLCompute %compute_main \"main\"|OpExecutionMode %compute_main LocalSize 1 1 1|OpDecorate %resource_values DescriptorSet 0|OpDecorate %resource_values Binding 0|OpDecorate %runtimearr_float ArrayStride 4|OpMemberDecorate %StorageBuffer_float 0 Offset 0|OpDecorate %StorageBuffer_float Block"
    "-DEXPECTED_SPVASM_ORDERED_CONTAINS=OpCapability Shader|OpMemoryModel Logical GLSL450|OpEntryPoint GLCompute %compute_main \"main\"|OpExecutionMode %compute_main LocalSize 1 1 1|OpDecorate %resource_values DescriptorSet 0|%void = OpTypeVoid|%compute_main = OpFunction"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_VULKAN_SUCCESS_DIR}/spirv-as.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=spirv-as success: --target-env vulkan1.2"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_VULKAN_SUCCESS_DIR}/spirv-val.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=spirv-val success: --target-env vulkan1.2"
    -DMODE=vulkan-build
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_crosstl_storage_buffer_overload_selection_fake_native
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_CROSSTL_STORAGE_BUFFER_OVERLOAD_SELECTION_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-crosstl-storage-buffer-overload-selection.cglb
    -DEXPECTED_MODULE=VulkanCrossTLStorageBufferOverloadSelectionShader
    -DEXPECTED_STORAGE_ELEMENT=Particle
    -DEXPECTED_STORAGE_STRIDE=32
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanCrossTLStorageBufferOverloadSelectionShader|artifacts.backendAssembly=backend/vulkan/VulkanCrossTLStorageBufferOverloadSelectionShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanCrossTLStorageBufferOverloadSelectionShader.spv"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanCrossTLStorageBufferOverloadSelectionShader|nativeBinary=backend/vulkan/VulkanCrossTLStorageBufferOverloadSelectionShader.spv|resources.0.name=scalars|resources.1.name=vectors|resources.2.name=particles|workgroupSizes.0.entryPoint=compute_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|structs=1|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=scalars.sourceType=float*|scalars.bindingClass=storageBuffer|scalars.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|scalars.binding=0|scalars.storageBufferLayout.arrayStrideBytes=4|vectors.sourceType=vec4*|vectors.binding=1|vectors.storageBufferLayout.arrayStrideBytes=16|particles.sourceType=Particle*|particles.binding=2|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.arrayStrideBytes=32|particles.storageBufferLayout.fields.0.name=position|particles.storageBufferLayout.fields.1.offsetBytes=16"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=compute-kernel.kind=stage|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|index-access.kind=operation|vector-arithmetic.kind=operation|local-declaration.kind=operation|storage-buffer-write.kind=operation|vector-constructor.kind=operation"
    "-DEXPECTED_SPVASM_CONTAINS=%func_crosstl_select_scalar = OpFunction %float None %fn_float_int__|%func_crosstl_select_vector = OpFunction %vec4 None %fn_vec4_int__|%func_crosstl_select_particle = OpFunction %vec4 None %fn_vec4_int__|OpAccessChain %ptr_StorageBuffer_float %resource_scalars %const_int__0 %param_crosstl_select_scalar_index|OpAccessChain %ptr_StorageBuffer_vec4 %resource_vectors %const_int__0 %param_crosstl_select_vector_index|OpAccessChain %ptr_StorageBuffer_vec4 %resource_particles %const_int__0 %param_crosstl_select_particle_index %const_int__0|OpFunctionCall %float %func_crosstl_select_scalar %const_int__0|OpFunctionCall %vec4 %func_crosstl_select_vector %const_int__0|OpFunctionCall %vec4 %func_crosstl_select_particle %const_int__0|OpAccessChain %ptr_StorageBuffer_vec4 %resource_vectors %const_int__0 %const_int__1"
    "-DEXPECTED_SPVASM_ORDERED_CONTAINS=%func_crosstl_select_scalar = OpFunction|%func_crosstl_select_vector = OpFunction|%func_crosstl_select_particle = OpFunction|%compute_main = OpFunction|OpFunctionCall %float %func_crosstl_select_scalar|OpFunctionCall %vec4 %func_crosstl_select_vector|OpFunctionCall %vec4 %func_crosstl_select_particle"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DMODE=vulkan-build
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_native_fake_disassembly_unavailable
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-spirv-dis-unavailable.cglb
    -DEXPECTED_MODULE=StorageBufferComputeShader
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_UNAVAILABLE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageBufferComputeShader|artifacts.backendAssembly=backend/vulkan/StorageBufferComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/StorageBufferComputeShader.spv"
    "-DEXPECTED_NATIVE_PROFILE_JSON_FIELDS=debug.optimization.tool=spirv-opt|debug.optimization.policy=disabled-by-opt-level|debug.optimization.requestedLevel=O1|debug.optimization.level=none|debug.optimization.status=skipped-disabled|debug.optimization.targetEnv=vulkan1.2|debug.optimization.toolStatus=not-run|debug.disassembly.tool=spirv-dis|debug.disassembly.policy=use-when-available|debug.disassembly.status=skipped-tool-missing|debug.disassembly.path=null"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_VULKAN_DISASSEMBLY_EXISTS=FALSE
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_UNAVAILABLE_DIR}/spirv-as.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=spirv-as success: --target-env vulkan1.2"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_UNAVAILABLE_DIR}/spirv-val.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=spirv-val success: --target-env vulkan1.2"
    -DEXPECTED_ABSENT_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_UNAVAILABLE_DIR}/spirv-opt.log
    -DMODE=vulkan-build
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_native_fake_disassembly_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-spirv-dis-success.cglb
    -DEXPECTED_MODULE=StorageBufferComputeShader
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageBufferComputeShader|artifacts.backendAssembly=backend/vulkan/StorageBufferComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/StorageBufferComputeShader.spv"
    "-DEXPECTED_NATIVE_PROFILE_JSON_FIELDS=debug.optimization.tool=spirv-opt|debug.optimization.policy=disabled-by-opt-level|debug.optimization.requestedLevel=O1|debug.optimization.level=none|debug.optimization.status=skipped-disabled|debug.optimization.targetEnv=vulkan1.2|debug.optimization.toolStatus=not-run|debug.disassembly.tool=spirv-dis|debug.disassembly.policy=use-when-available|debug.disassembly.status=emitted|debug.disassembly.path=backend/vulkan/StorageBufferComputeShader.disassembly.spvasm"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_VULKAN_DISASSEMBLY_EXISTS=TRUE
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_SUCCESS_DIR}/spirv-as.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=spirv-as success: --target-env vulkan1.2"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_SUCCESS_DIR}/spirv-val.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=spirv-val success: --target-env vulkan1.2"
    -DEXPECTED_THIRD_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_SUCCESS_DIR}/spirv-dis.log
    "-DEXPECTED_THIRD_TOOL_LOG_CONTAINS=spirv-dis success:"
    -DEXPECTED_ABSENT_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_SUCCESS_DIR}/spirv-opt.log
    -DMODE=vulkan-build
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_native_fake_graphics_spirv_stage_closure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_COMPARE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-graphics-stage-closure.cglb
    -DEXPECTED_MODULE=VulkanGraphicsShadowCompareShader
    -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
    -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowCompareShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsShadowCompareShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsShadowCompareShader.spv|artifacts.nativeProfile=backend/vulkan/VulkanGraphicsShadowCompareShader.profile.json|artifacts.nativeArtifactDescriptor=backend/vulkan/VulkanGraphicsShadowCompareShader.native-artifact.json|artifacts.graphicsAbi=backend/vulkan/VulkanGraphicsShadowCompareShader.graphics-abi.json"
    "-DEXPECTED_NATIVE_PROFILE_JSON_FIELDS=debug.disassembly.tool=spirv-dis|debug.disassembly.policy=use-when-available|debug.disassembly.status=emitted|debug.disassembly.path=backend/vulkan/VulkanGraphicsShadowCompareShader.disassembly.spvasm"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/VulkanGraphicsShadowCompareShader.spvasm|artifactPath=backend/vulkan/VulkanGraphicsShadowCompareShader.spv|validationStatus=validated|optimizationEvidence.evidenceSource.kind=native-profile|optimizationEvidence.evidenceSource.path=backend/vulkan/VulkanGraphicsShadowCompareShader.profile.json"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowCompareShader|nativeBinary=backend/vulkan/VulkanGraphicsShadowCompareShader.spv|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.stage=fragment|resources.0.name=shadowMap|resources.1.stage=fragment|resources.1.name=shadowSampler|vertexLayouts.0.entryPoint=vertex_main"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|workgroupSizes=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.stage=fragment|shadowMap.bindingClass=sampledImage|shadowMap.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowMap.storageClass=UniformConstant|shadowMap.set=0|shadowMap.binding=2|shadowSampler.stage=fragment|shadowSampler.bindingClass=sampler|shadowSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|shadowSampler.storageClass=UniformConstant|shadowSampler.set=0|shadowSampler.binding=3"
    "-DEXPECTED_SPVASM_CONTAINS=OpEntryPoint Vertex|\"vertex_main\"|OpEntryPoint Fragment|\"fragment_main\"|OriginUpperLeft|OpDecorate %resource_fragment_shadowMap DescriptorSet 0|OpDecorate %resource_fragment_shadowMap Binding 2|OpDecorate %resource_fragment_shadowSampler Binding 3"
    "-DEXPECTED_SPVASM_ORDERED_CONTAINS=OpCapability Shader|OpMemoryModel Logical GLSL450|OpEntryPoint Vertex|OpEntryPoint Fragment|OriginUpperLeft"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_VULKAN_DISASSEMBLY_EXISTS=TRUE
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_SUCCESS_DIR}/spirv-as.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=spirv-as success: --target-env vulkan1.2"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_SUCCESS_DIR}/spirv-val.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=spirv-val success: --target-env vulkan1.2"
    -DEXPECTED_THIRD_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_SUCCESS_DIR}/spirv-dis.log
    "-DEXPECTED_THIRD_TOOL_LOG_CONTAINS=spirv-dis success:"
    -DEXPECTED_ABSENT_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_SUCCESS_DIR}/spirv-opt.log
    -DMODE=vulkan-build
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_native_fake_disassembly_tool_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-spirv-dis-failure.cglb
    -DEXPECTED_MODULE=StorageBufferComputeShader
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_FAILURE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageBufferComputeShader|artifacts.backendAssembly=backend/vulkan/StorageBufferComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/StorageBufferComputeShader.spv"
    "-DEXPECTED_NATIVE_PROFILE_JSON_FIELDS=debug.disassembly.tool=spirv-dis|debug.disassembly.policy=use-when-available|debug.disassembly.status=failed|debug.disassembly.path=null"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=warning|diagnostics.0.code=vulkan.disassemble-failed"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    -DEXPECTED_VULKAN_DISASSEMBLY_EXISTS=FALSE
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_FAILURE_DIR}/spirv-as.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=spirv-as success: --target-env vulkan1.2"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_FAILURE_DIR}/spirv-val.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=spirv-val success: --target-env vulkan1.2"
    -DEXPECTED_THIRD_TOOL_LOG=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_FAILURE_DIR}/spirv-dis.log
    "-DEXPECTED_THIRD_TOOL_LOG_CONTAINS=spirv-dis failure:"
    -DMODE=vulkan-build
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_native_fake_spirv_opt_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-spirv-opt-success.cglb
    -DEXPECTED_MODULE=StorageBufferComputeShader
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_OPT_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DOPT_LEVEL=O2
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageBufferComputeShader|artifacts.backendAssembly=backend/vulkan/StorageBufferComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/StorageBufferComputeShader.spv"
    "-DEXPECTED_NATIVE_PROFILE_JSON_FIELDS=debug.optimization.tool=spirv-opt|debug.optimization.policy=use-when-available|debug.optimization.requestedLevel=O2|debug.optimization.level=-O|debug.optimization.status=applied|debug.optimization.targetEnv=vulkan1.2|debug.optimization.toolStatus=available"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/StorageBufferComputeShader.spvasm|artifactPath=backend/vulkan/StorageBufferComputeShader.spv|optimizationLevel=O2|optimizationEvidence.requestedLevel=O2|optimizationEvidence.effectiveLevel=O2|optimizationEvidence.policy=use-when-available|optimizationEvidence.status=applied|optimizationEvidence.tool=spirv-opt|optimizationEvidence.toolFlag=-O|validationStatus=validated"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageBufferComputeShader|nativeBinary=backend/vulkan/StorageBufferComputeShader.spv"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_SUCCESS_DIR}/spirv-as.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=spirv-as success: --target-env vulkan1.2"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_SUCCESS_DIR}/spirv-val.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=spirv-val success: --target-env vulkan1.2"
    -DEXPECTED_THIRD_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_SUCCESS_DIR}/spirv-opt.log
    "-DEXPECTED_THIRD_TOOL_LOG_CONTAINS=spirv-opt success: --target-env=vulkan1.2 -O"
    -DMODE=vulkan-build
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_native_opt_level_o0_skips_spirv_opt
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-spirv-opt-o0.cglb
    -DEXPECTED_MODULE=StorageBufferComputeShader
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_OPT_O0_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DOPT_LEVEL=O0
    "-DEXPECTED_NATIVE_PROFILE_JSON_FIELDS=debug.optimization.tool=spirv-opt|debug.optimization.policy=disabled-by-opt-level|debug.optimization.requestedLevel=O0|debug.optimization.level=none|debug.optimization.status=skipped-disabled|debug.optimization.targetEnv=vulkan1.2|debug.optimization.toolStatus=not-run"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/StorageBufferComputeShader.spvasm|artifactPath=backend/vulkan/StorageBufferComputeShader.spv|optimizationLevel=O0|optimizationEvidence.requestedLevel=O0|optimizationEvidence.effectiveLevel=none|optimizationEvidence.policy=disabled-by-opt-level|optimizationEvidence.status=skipped-disabled|optimizationEvidence.tool=spirv-opt|optimizationEvidence.evidenceSource.kind=native-profile|optimizationEvidence.evidenceSource.path=backend/vulkan/StorageBufferComputeShader.profile.json|validationStatus=validated"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_O0_DIR}/spirv-as.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=spirv-as success: --target-env vulkan1.2"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_O0_DIR}/spirv-val.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=spirv-val success: --target-env vulkan1.2"
    -DEXPECTED_ABSENT_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_O0_DIR}/spirv-opt.log
    -DMODE=vulkan-build
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_native_opt_level_o1_skips_spirv_opt
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-spirv-opt-o1.cglb
    -DEXPECTED_MODULE=StorageBufferComputeShader
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_OPT_O1_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DOPT_LEVEL=O1
    "-DEXPECTED_NATIVE_PROFILE_JSON_FIELDS=debug.optimization.tool=spirv-opt|debug.optimization.policy=disabled-by-opt-level|debug.optimization.requestedLevel=O1|debug.optimization.level=none|debug.optimization.status=skipped-disabled|debug.optimization.targetEnv=vulkan1.2|debug.optimization.toolStatus=not-run"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/StorageBufferComputeShader.spvasm|artifactPath=backend/vulkan/StorageBufferComputeShader.spv|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=none|optimizationEvidence.policy=disabled-by-opt-level|optimizationEvidence.status=skipped-disabled|optimizationEvidence.tool=spirv-opt|optimizationEvidence.evidenceSource.kind=native-profile|optimizationEvidence.evidenceSource.path=backend/vulkan/StorageBufferComputeShader.profile.json|validationStatus=validated"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_O1_DIR}/spirv-as.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=spirv-as success: --target-env vulkan1.2"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_O1_DIR}/spirv-val.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=spirv-val success: --target-env vulkan1.2"
    -DEXPECTED_ABSENT_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_O1_DIR}/spirv-opt.log
    -DMODE=vulkan-build
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_native_opt_level_o2_runs_spirv_opt
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-spirv-opt-o2.cglb
    -DEXPECTED_MODULE=StorageBufferComputeShader
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_OPT_O2_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DOPT_LEVEL=O2
    "-DEXPECTED_NATIVE_PROFILE_JSON_FIELDS=debug.optimization.tool=spirv-opt|debug.optimization.policy=use-when-available|debug.optimization.requestedLevel=O2|debug.optimization.level=-O|debug.optimization.status=applied|debug.optimization.targetEnv=vulkan1.2|debug.optimization.toolStatus=available"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/StorageBufferComputeShader.spvasm|artifactPath=backend/vulkan/StorageBufferComputeShader.spv|optimizationLevel=O2|optimizationEvidence.requestedLevel=O2|optimizationEvidence.effectiveLevel=O2|optimizationEvidence.policy=use-when-available|optimizationEvidence.status=applied|optimizationEvidence.tool=spirv-opt|optimizationEvidence.toolFlag=-O|optimizationEvidence.evidenceSource.kind=native-profile|optimizationEvidence.evidenceSource.path=backend/vulkan/StorageBufferComputeShader.profile.json|validationStatus=validated"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_O2_DIR}/spirv-as.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=spirv-as success: --target-env vulkan1.2"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_O2_DIR}/spirv-val.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=spirv-val success: --target-env vulkan1.2"
    -DEXPECTED_THIRD_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_O2_DIR}/spirv-opt.log
    "-DEXPECTED_THIRD_TOOL_LOG_CONTAINS=spirv-opt success: --target-env=vulkan1.2 -O"
    -DMODE=vulkan-build
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_native_fake_spirv_opt_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=vulkan
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-spirv-opt-failure.cglb
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_OPT_FAILURE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DOPT_LEVEL=O2
    -DEXPECT_NO_OUTPUT_PACKAGE=ON
    -DEXPECTED_DIAGNOSTIC=vulkan.optimize-failed
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=vulkan.optimize-failed"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=requested optimization level O2|diagnostics.0.message=no package was emitted"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_FAILURE_DIR}/spirv-as.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=spirv-as success: --target-env vulkan1.2"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_FAILURE_DIR}/spirv-opt.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=spirv-opt failure: --target-env=vulkan1.2 -O"
    -DEXPECTED_ABSENT_TOOL_LOG=${CROSSGL_FAKE_VULKAN_OPT_FAILURE_DIR}/spirv-val.log
    -DMODE=planned-build-failure
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_native_fake_spirv_as_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=vulkan
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-spirv-as-failure.cglb
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_ASSEMBLER_FAILURE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECT_NO_OUTPUT_PACKAGE=ON
    -DEXPECTED_DIAGNOSTIC=vulkan.assemble-failed
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=vulkan.assemble-failed"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_VULKAN_ASSEMBLER_FAILURE_DIR}/spirv-as.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=spirv-as failure: --target-env vulkan1.2"
    -DMODE=planned-build-failure
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_native_fake_spirv_val_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=vulkan
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-spirv-val-failure.cglb
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_VALIDATOR_FAILURE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECT_NO_OUTPUT_PACKAGE=ON
    -DEXPECTED_DIAGNOSTIC=vulkan.validate-failed
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=vulkan.validate-failed"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_VULKAN_VALIDATOR_FAILURE_DIR}/spirv-as.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=spirv-as success: --target-env vulkan1.2"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_VULKAN_VALIDATOR_FAILURE_DIR}/spirv-val.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=spirv-val failure: --target-env vulkan1.2"
    -DMODE=planned-build-failure
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_native_fake_spirv_as_unavailable_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=vulkan
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-spirv-as-unavailable.cglb
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_ASSEMBLER_UNAVAILABLE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECT_NO_OUTPUT_PACKAGE=ON
    -DEXPECTED_DIAGNOSTIC=vulkan.spirv-as-missing
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=vulkan.spirv-as-missing"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=spirv-as is required"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    -DMODE=planned-build-failure
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_vulkan_native_fake_spirv_val_unavailable_planned_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=vulkan
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-fake-spirv-val-unavailable.cglb
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_VALIDATOR_UNAVAILABLE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECT_NO_OUTPUT_PACKAGE=ON
    -DEXPECTED_DIAGNOSTIC=vulkan.spirv-val-missing
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=vulkan.spirv-val-missing"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=spirv-val is required"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    -DMODE=planned-build-failure
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

crossgl_label_optional_native_policy_test(
  cglc_build_vulkan_native_fake_spirv_success vulkan)
crossgl_label_optional_native_policy_test(
  cglc_build_vulkan_native_fake_intrinsics_import_closure vulkan)
crossgl_label_optional_native_policy_test(
  cglc_build_vulkan_crosstl_storage_buffer_overload_selection_fake_native
  vulkan)
crossgl_label_optional_native_policy_test(
  cglc_build_vulkan_native_fake_disassembly_unavailable vulkan)
crossgl_label_optional_native_policy_test(
  cglc_build_vulkan_native_fake_disassembly_tool_failure vulkan)
crossgl_label_optional_native_policy_test(
  cglc_build_vulkan_native_fake_graphics_spirv_stage_closure vulkan)
crossgl_label_optional_native_policy_test(
  cglc_build_vulkan_native_fake_spirv_opt_planned_failure vulkan)
crossgl_label_optional_native_policy_test(
  cglc_build_vulkan_native_fake_spirv_as_planned_failure vulkan)
crossgl_label_optional_native_policy_test(
  cglc_build_vulkan_native_fake_spirv_as_unavailable_planned_failure vulkan)
crossgl_label_optional_native_policy_test(
  cglc_build_vulkan_native_fake_spirv_val_planned_failure vulkan)
crossgl_label_optional_native_policy_test(
  cglc_build_vulkan_native_fake_spirv_val_unavailable_planned_failure vulkan)

crossgl_capture_current_tests(CROSSGL_VULKAN_NATIVE_TESTS_BEFORE)

if(CROSSGL_HAS_VULKAN_NATIVE_TOOLS)
  set(CROSSGL_VULKAN_TOOLCHAIN_SMOKE_OPTIONAL_ARGS "")
  if(CROSSGL_SPIRV_OPT)
    list(APPEND CROSSGL_VULKAN_TOOLCHAIN_SMOKE_OPTIONAL_ARGS
         "-DSPIRV_OPT=${CROSSGL_SPIRV_OPT}")
  endif()
  if(CROSSGL_SPIRV_DIS)
    list(APPEND CROSSGL_VULKAN_TOOLCHAIN_SMOKE_OPTIONAL_ARGS
         "-DSPIRV_DIS=${CROSSGL_SPIRV_DIS}")
  endif()
  add_test(NAME cglc_vulkan_toolchain_native_smoke
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-toolchain-smoke.cglb
      -DEXPECTED_MODULE=StorageBufferComputeShader
      "-DSPIRV_AS=${CROSSGL_SPIRV_AS}"
      "-DSPIRV_VAL=${CROSSGL_SPIRV_VAL}"
      ${CROSSGL_VULKAN_TOOLCHAIN_SMOKE_OPTIONAL_ARGS}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/VulkanToolchainSmoke.cmake)
  crossgl_label_optional_native_test(cglc_vulkan_toolchain_native_smoke vulkan)
  add_test(NAME cglc_build_vulkan_resource_shader_workgroup_shared_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_RESOURCE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-resource-shader-workgroup-shared.cglb
      -DEXPECTED_MODULE=ResourceShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/ResourceShader.spvasm|artifacts.nativeBinary=backend/vulkan/ResourceShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ResourceShader|nativeBinary=backend/vulkan/ResourceShader.spv|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=16|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=TILE_SIZE"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=5|targetResourceBindings=5|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.binding=5|tile.kind=shared|tile.abi=workgroupLocal|tile.bindingClass=workgroup|tile.storageClass=Workgroup|tile.spirvType=OpVariable<Workgroup, float[TILE_SIZE]>|tile.arrayElementCount=16|tile.arrayDimensions.0.elementCount=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|workgroup-shared-memory.kind=resource|texture-sample.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=%resource_tile = OpVariable %ptr_Workgroup_float_TILE_SIZE_ Workgroup"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_workgroup_shared_declaration_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanWorkgroupSharedDeclarationShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-workgroup-shared-declaration.cglb
      -DEXPECTED_MODULE=VulkanWorkgroupSharedDeclarationShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/VulkanWorkgroupSharedDeclarationShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanWorkgroupSharedDeclarationShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanWorkgroupSharedDeclarationShader|nativeBinary=backend/vulkan/VulkanWorkgroupSharedDeclarationShader.spv|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=2|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=TILE_WIDTH"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|workgroupSizes=1|functionConstants=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.binding=0|tile.kind=shared|tile.abi=workgroupLocal|tile.bindingClass=workgroup|tile.storageClass=Workgroup|tile.spirvType=OpVariable<Workgroup, float[TILE_WIDTH]>|tile.arrayElementCount=4|tile.arrayDimensions.0.elementCount=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|workgroup-shared-memory.kind=resource|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=%resource_tile = OpVariable %ptr_Workgroup_float_TILE_WIDTH_ Workgroup"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_workgroup_shared_declaration_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanWorkgroupSharedDeclarationShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-workgroup-shared-declaration-spvasm.cglb
      -DEXPECTED_MODULE=VulkanWorkgroupSharedDeclarationShader
      "-DEXPECTED_SPVASM_CONTAINS=OpExecutionMode %compute_main LocalSize 4 2 1|%workgrouparr_float_TILE_WIDTH_ = OpTypeArray %float %const_uint_4|%ptr_Workgroup_float_TILE_WIDTH_ = OpTypePointer Workgroup %workgrouparr_float_TILE_WIDTH_|%resource_tile = OpVariable %ptr_Workgroup_float_TILE_WIDTH_ Workgroup"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_tile DescriptorSet|OpDecorate %resource_tile Binding|OpDecorate %workgrouparr_float_TILE_WIDTH_ ArrayStride"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_compute_invocation_builtin_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanComputeInvocationBuiltinShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-compute-invocation-builtin.cglb
      -DEXPECTED_MODULE=VulkanComputeInvocationBuiltinShader
      -DEXPECTED_STORAGE_ELEMENT=uvec3
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/VulkanComputeInvocationBuiltinShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanComputeInvocationBuiltinShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanComputeInvocationBuiltinShader|nativeBinary=backend/vulkan/VulkanComputeInvocationBuiltinShader.spv|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=8|workgroupSizes.0.y=4|workgroupSizes.0.z=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=globalIds.sourceType=uvec3*|globalIds.bindingClass=storageBuffer|globalIds.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|globalIds.storageClass=StorageBuffer|globalIds.set=0|globalIds.binding=0|globalIds.storageBufferLayout.elementType=uvec3|globalIds.storageBufferLayout.layout=std430|globalIds.storageBufferLayout.arrayStrideBytes=16|localIds.binding=1|workgroupIds.binding=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|storage-buffer-write.kind=operation|index-access.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpDecorate %builtin_gl_GlobalInvocationID BuiltIn GlobalInvocationId"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_compute_invocation_builtin_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/vulkan/fixtures/VulkanComputeInvocationBuiltinShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-compute-invocation-builtin-spvasm.cglb
      -DEXPECTED_MODULE=VulkanComputeInvocationBuiltinShader
      "-DEXPECTED_SPVASM_CONTAINS=OpEntryPoint GLCompute %compute_main \"main\" %resource_globalIds %resource_localIds %resource_workgroupIds %builtin_gl_GlobalInvocationID %builtin_gl_LocalInvocationID %builtin_gl_WorkGroupID|OpDecorate %builtin_gl_GlobalInvocationID BuiltIn GlobalInvocationId|OpDecorate %builtin_gl_LocalInvocationID BuiltIn LocalInvocationId|OpDecorate %builtin_gl_WorkGroupID BuiltIn WorkgroupId|%ptr_Input_uvec3 = OpTypePointer Input %uvec3|%builtin_gl_GlobalInvocationID = OpVariable %ptr_Input_uvec3 Input|%builtin_gl_LocalInvocationID = OpVariable %ptr_Input_uvec3 Input|%builtin_gl_WorkGroupID = OpVariable %ptr_Input_uvec3 Input|%tmp_1 = OpLoad %uvec3 %builtin_gl_GlobalInvocationID|%tmp_3 = OpLoad %uvec3 %builtin_gl_LocalInvocationID|%tmp_5 = OpLoad %uvec3 %builtin_gl_WorkGroupID|OpStore %tmp_0 %tmp_1|OpStore %tmp_2 %tmp_3|OpStore %tmp_4 %tmp_5"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpDecorate %builtin_gl_GlobalInvocationID DescriptorSet|OpDecorate %builtin_gl_GlobalInvocationID Binding|OpDecorate %builtin_gl_LocalInvocationID DescriptorSet|OpDecorate %builtin_gl_LocalInvocationID Binding|OpDecorate %builtin_gl_WorkGroupID DescriptorSet|OpDecorate %builtin_gl_WorkGroupID Binding"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_texture_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=%arr_image_sampler2D_TEXTURE_COUNT_ = OpTypeArray %image_2D %const_uint_2"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/TextureDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/TextureDescriptorArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/TextureDescriptorArrayShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|colorMaps.bindingClass=sampledImage|colorMaps.binding=2|colorMaps.arraySize=TEXTURE_COUNT|colorMaps.arrayElementCount=2|colorMaps.arrayDimensions.0.elementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_sampler_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-sampler-descriptor-array.cglb
      -DEXPECTED_MODULE=SamplerDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLER
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=%arr_sampler_sampler_SAMPLER_COUNT_ = OpTypeArray %sampler %const_uint_2"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/SamplerDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/SamplerDescriptorArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/SamplerDescriptorArrayShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=linearSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSamplers.bindingClass=sampler|linearSamplers.binding=5|linearSamplers.arraySize=SAMPLER_COUNT|linearSamplers.arrayElementCount=2|linearSamplers.arrayDimensions.0.elementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampler-state.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_storage_buffer_resource_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_STORAGE_BUFFER_RESOURCE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-storage-buffer-resource.cglb
      -DEXPECTED_MODULE=VulkanGraphicsStorageBufferResourceShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsStorageBufferResourceShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsStorageBufferResourceShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsStorageBufferResourceShader.spv|artifacts.graphicsAbi=backend/vulkan/VulkanGraphicsStorageBufferResourceShader.graphics-abi.json"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsStorageBufferResourceShader|nativeBinary=backend/vulkan/VulkanGraphicsStorageBufferResourceShader.spv|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=4|targetResourceBindings=4|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=vertexOffsets.stage=vertex|vertexOffsets.sourceType=vec4*|vertexOffsets.bindingClass=storageBuffer|vertexOffsets.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|vertexOffsets.storageClass=StorageBuffer|vertexOffsets.binding=0|vertexOffsets.storageBufferLayout.arrayStrideBytes=16|vertexDrawData.stage=vertex|vertexDrawData.sourceType=DrawData*|vertexDrawData.bindingClass=storageBuffer|vertexDrawData.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|vertexDrawData.binding=1|vertexDrawData.storageBufferLayout.elementType=DrawData|vertexDrawData.storageBufferLayout.fields.1.name=tint|vertexDrawData.storageBufferLayout.fields.1.offsetBytes=16|fragmentScales.stage=fragment|fragmentScales.binding=2|fragmentScales.storageBufferLayout.arrayStrideBytes=16|fragmentDrawData.stage=fragment|fragmentDrawData.binding=3|fragmentDrawData.storageBufferLayout.elementType=DrawData"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer.kind=resource|vector-storage-buffer.kind=layout|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpDecorate %resource_vertex_vertexOffsets Binding 0"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_storage_buffer_resource_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_STORAGE_BUFFER_RESOURCE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-storage-buffer-resource-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsStorageBufferResourceShader
      "-DEXPECTED_SPVASM_CONTAINS=OpEntryPoint Vertex|OpEntryPoint Fragment|OpDecorate %resource_vertex_vertexOffsets DescriptorSet 0|OpDecorate %resource_vertex_vertexOffsets Binding 0|OpDecorate %resource_vertex_vertexDrawData Binding 1|OpDecorate %resource_fragment_fragmentScales Binding 2|OpDecorate %resource_fragment_fragmentDrawData Binding 3|OpDecorate %runtimearr_vec4 ArrayStride 16|OpMemberDecorate %StorageBuffer_vec4 0 Offset 0|OpDecorate %StorageBuffer_vec4 Block|OpMemberDecorate %struct_storage_DrawData 0 Offset 0|OpMemberDecorate %struct_storage_DrawData 1 Offset 16|OpAccessChain %ptr_StorageBuffer_vec4 %resource_vertex_vertexOffsets|OpAccessChain %ptr_StorageBuffer_vec4 %resource_vertex_vertexDrawData|OpAccessChain %ptr_StorageBuffer_vec4 %resource_fragment_fragmentDrawData"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpCapability StorageBufferArrayNonUniformIndexingEXT|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_graphics_storage_buffer_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_STORAGE_BUFFER_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-storage-buffer-descriptor-array.cglb
      -DEXPECTED_MODULE=VulkanGraphicsStorageBufferDescriptorArrayShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsStorageBufferDescriptorArrayShader|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsStorageBufferDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsStorageBufferDescriptorArrayShader.spv|artifacts.graphicsAbi=backend/vulkan/VulkanGraphicsStorageBufferDescriptorArrayShader.graphics-abi.json"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsStorageBufferDescriptorArrayShader|nativeBinary=backend/vulkan/VulkanGraphicsStorageBufferDescriptorArrayShader.spv|entryPoints.0.stage=vertex|entryPoints.1.stage=fragment|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=1|targetResourceBindings=1|vertexLayouts=1|workgroupSizes=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=debugValues.stage=fragment|debugValues.sourceType=vec4*[2]|debugValues.bindingClass=storageBuffer|debugValues.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|debugValues.storageClass=StorageBuffer|debugValues.binding=2|debugValues.arrayElementCount=2|debugValues.storageBufferLayout.arrayStrideBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=fixed-array.kind=layout|descriptor-array.kind=resource|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=%arr_StorageBuffer_vec4__2_ = OpTypeArray %StorageBuffer_vec4"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_graphics_storage_buffer_descriptor_array_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_STORAGE_BUFFER_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-storage-buffer-descriptor-array-spvasm.cglb
      -DEXPECTED_MODULE=VulkanGraphicsStorageBufferDescriptorArrayShader
      "-DEXPECTED_SPVASM_CONTAINS=OpEntryPoint Fragment|OpDecorate %resource_fragment_debugValues DescriptorSet 0|OpDecorate %resource_fragment_debugValues Binding 2|%arr_StorageBuffer_vec4__2_ = OpTypeArray %StorageBuffer_vec4|%ptr_StorageBuffer_Resource_vec4__2_ = OpTypePointer StorageBuffer %arr_StorageBuffer_vec4__2_|%resource_fragment_debugValues = OpVariable %ptr_StorageBuffer_Resource_vec4__2_ StorageBuffer|OpAccessChain %ptr_StorageBuffer_vec4 %resource_fragment_debugValues"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpCapability RuntimeDescriptorArrayEXT|OpCapability StorageBufferArrayNonUniformIndexingEXT|NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_runtime_texture_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_RUNTIME_TEXTURE_DESCRIPTOR_ARRAY_POLICY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-texture-descriptor-array-policy.cglb
      -DEXPECTED_MODULE=VulkanRuntimeTextureDescriptorArrayPolicyShader
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      "-DEXPECTED_SPVASM_CONTAINS=OpCapability RuntimeDescriptorArrayEXT|OpExtension \"SPV_EXT_descriptor_indexing\"|OpEntryPoint GLCompute %compute_main \"main\" %resource_values %resource_maps %resource_linearSampler|OpDecorate %resource_maps DescriptorSet 0|OpDecorate %resource_maps Binding 1|OpDecorate %resource_linearSampler DescriptorSet 0|OpDecorate %resource_linearSampler Binding 2|%image_2D = OpTypeImage %float 2D 0 0 0 1 Unknown|%runtimearr_image_sampler2D__ = OpTypeRuntimeArray %image_2D|%ptr_UniformConstant_sampledImage_sampler2D__ = OpTypePointer UniformConstant %runtimearr_image_sampler2D__|%resource_maps = OpVariable %ptr_UniformConstant_sampledImage_sampler2D__ UniformConstant|%ptr_UniformConstant_sampler_sampler = OpTypePointer UniformConstant %sampler|%resource_linearSampler = OpVariable %ptr_UniformConstant_sampler_sampler UniformConstant|OpAccessChain %ptr_UniformConstant_sampledImage_sampler2D %resource_maps %const_int__0|OpLoad %sampler %resource_linearSampler|OpSampledImage %sampled_sampler2D|OpImageSampleExplicitLod %vec4|Lod %const_float__0_0"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/VulkanRuntimeTextureDescriptorArrayPolicyShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0|resources.1.arrayDimensions=1|targetResourceBindings.1.arrayDimensions=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.binding=0|values.storageBufferLayout.arrayStrideBytes=16|maps.sourceType=sampler2D[]|maps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|maps.bindingClass=sampledImage|maps.storageClass=UniformConstant|maps.spirvType=OpTypeRuntimeArray<OpTypeImage<float, 2D, sampled=1>>|maps.set=0|maps.binding=1|maps.arraySize=|maps.arrayDimensions.0.kind=runtime|linearSampler.sourceType=sampler|linearSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSampler.bindingClass=sampler|linearSampler.storageClass=UniformConstant|linearSampler.spirvType=OpTypeSampler|linearSampler.set=0|linearSampler.binding=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|sampled-texture.kind=resource|runtime-array.kind=layout|descriptor-array.kind=resource|runtime-descriptor-array.kind=resource|runtime-texture-descriptor-array.kind=resource|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_runtime_sampler_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_RUNTIME_SAMPLER_DESCRIPTOR_ARRAY_POLICY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-sampler-descriptor-array-policy.cglb
      -DEXPECTED_MODULE=VulkanRuntimeSamplerDescriptorArrayPolicyShader
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      "-DEXPECTED_SPVASM_CONTAINS=OpCapability RuntimeDescriptorArrayEXT|OpExtension \"SPV_EXT_descriptor_indexing\"|OpEntryPoint GLCompute %compute_main \"main\" %resource_values %resource_map %resource_linearSamplers|OpDecorate %resource_map DescriptorSet 0|OpDecorate %resource_map Binding 1|OpDecorate %resource_linearSamplers DescriptorSet 0|OpDecorate %resource_linearSamplers Binding 2|%image_2D = OpTypeImage %float 2D 0 0 0 1 Unknown|%ptr_UniformConstant_sampledImage_sampler2D = OpTypePointer UniformConstant %image_2D|%resource_map = OpVariable %ptr_UniformConstant_sampledImage_sampler2D UniformConstant|%runtimearr_sampler_sampler__ = OpTypeRuntimeArray %sampler|%ptr_UniformConstant_sampler_sampler__ = OpTypePointer UniformConstant %runtimearr_sampler_sampler__|%resource_linearSamplers = OpVariable %ptr_UniformConstant_sampler_sampler__ UniformConstant|OpLoad %image_2D %resource_map|OpAccessChain %ptr_UniformConstant_sampler_sampler %resource_linearSamplers %const_int__0|OpSampledImage %sampled_sampler2D|OpImageSampleExplicitLod %vec4|Lod %const_float__0_0"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/VulkanRuntimeSamplerDescriptorArrayPolicyShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0|resources.2.arrayDimensions=1|targetResourceBindings.2.arrayDimensions=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.binding=0|values.storageBufferLayout.arrayStrideBytes=16|map.sourceType=sampler2D|map.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|map.bindingClass=sampledImage|map.storageClass=UniformConstant|map.spirvType=OpTypeImage<float, 2D, sampled=1>|map.set=0|map.binding=1|linearSamplers.sourceType=sampler[]|linearSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSamplers.bindingClass=sampler|linearSamplers.storageClass=UniformConstant|linearSamplers.spirvType=OpTypeRuntimeArray<OpTypeSampler>|linearSamplers.set=0|linearSamplers.binding=2|linearSamplers.arraySize=|linearSamplers.arrayDimensions.0.kind=runtime"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|sampled-texture.kind=resource|sampler-state.kind=resource|runtime-array.kind=layout|descriptor-array.kind=resource|runtime-descriptor-array.kind=resource|runtime-sampler-descriptor-array.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_runtime_texture_sampler_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_POLICY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-texture-sampler-descriptor-array-policy.cglb
      -DEXPECTED_MODULE=VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      "-DEXPECTED_SPVASM_CONTAINS=OpCapability RuntimeDescriptorArrayEXT|OpExtension \"SPV_EXT_descriptor_indexing\"|OpEntryPoint GLCompute %compute_main \"main\" %resource_values %resource_maps %resource_linearSamplers|OpDecorate %resource_maps Binding 1|OpDecorate %resource_linearSamplers Binding 2|%runtimearr_image_sampler2D__ = OpTypeRuntimeArray %image_2D|%ptr_UniformConstant_sampledImage_sampler2D__ = OpTypePointer UniformConstant %runtimearr_image_sampler2D__|%runtimearr_sampler_sampler__ = OpTypeRuntimeArray %sampler|%ptr_UniformConstant_sampler_sampler__ = OpTypePointer UniformConstant %runtimearr_sampler_sampler__|%resource_maps = OpVariable %ptr_UniformConstant_sampledImage_sampler2D__ UniformConstant|%resource_linearSamplers = OpVariable %ptr_UniformConstant_sampler_sampler__ UniformConstant|OpAccessChain %ptr_UniformConstant_sampledImage_sampler2D %resource_maps %const_int__0|OpAccessChain %ptr_UniformConstant_sampler_sampler %resource_linearSamplers %const_int__0|OpSampledImage %sampled_sampler2D|OpImageSampleExplicitLod %vec4|Lod %const_float__0_0"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0|resources.1.arrayDimensions=1|resources.2.arrayDimensions=1|targetResourceBindings.1.arrayDimensions=1|targetResourceBindings.2.arrayDimensions=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.binding=0|values.storageBufferLayout.arrayStrideBytes=16|maps.sourceType=sampler2D[]|maps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|maps.bindingClass=sampledImage|maps.storageClass=UniformConstant|maps.spirvType=OpTypeRuntimeArray<OpTypeImage<float, 2D, sampled=1>>|maps.set=0|maps.binding=1|maps.arraySize=|maps.arrayDimensions.0.kind=runtime|linearSamplers.sourceType=sampler[]|linearSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSamplers.bindingClass=sampler|linearSamplers.storageClass=UniformConstant|linearSamplers.spirvType=OpTypeRuntimeArray<OpTypeSampler>|linearSamplers.set=0|linearSamplers.binding=2|linearSamplers.arraySize=|linearSamplers.arrayDimensions.0.kind=runtime"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|sampled-texture.kind=resource|runtime-array.kind=layout|descriptor-array.kind=resource|runtime-descriptor-array.kind=resource|runtime-texture-descriptor-array.kind=resource|sampler-state.kind=resource|runtime-sampler-descriptor-array.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_runtime_texture_sampler_nonuniform_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_RUNTIME_TEXTURE_SAMPLER_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-texture-sampler-nonuniform-descriptor-array.cglb
      -DEXPECTED_MODULE=VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      "-DEXPECTED_SPVASM_CONTAINS=OpCapability RuntimeDescriptorArrayEXT|OpCapability ShaderNonUniformEXT|OpCapability SampledImageArrayNonUniformIndexingEXT|OpExtension \"SPV_EXT_descriptor_indexing\"|OpEntryPoint GLCompute %compute_main \"main\" %resource_values %resource_maps %resource_linearSamplers %resource_descriptors|OpDecorate %resource_maps Binding 1|OpDecorate %resource_linearSamplers Binding 2|OpDecorate %resource_descriptors Binding 3|%runtimearr_image_sampler2D__ = OpTypeRuntimeArray %image_2D|%runtimearr_sampler_sampler__ = OpTypeRuntimeArray %sampler|%resource_maps = OpVariable %ptr_UniformConstant_sampledImage_sampler2D__ UniformConstant|%resource_linearSamplers = OpVariable %ptr_UniformConstant_sampler_sampler__ UniformConstant|%resource_descriptors = OpVariable %ptr_StorageBuffer_StorageBuffer_int StorageBuffer|OpDecorate %tmp_2 NonUniformEXT|OpDecorate %tmp_3 NonUniformEXT|OpDecorate %tmp_4 NonUniformEXT|OpDecorate %tmp_5 NonUniformEXT|OpDecorate %tmp_6 NonUniformEXT|OpDecorate %tmp_7 NonUniformEXT|OpDecorate %tmp_9 NonUniformEXT|OpAccessChain %ptr_UniformConstant_sampledImage_sampler2D %resource_maps %tmp_2|OpAccessChain %ptr_UniformConstant_sampler_sampler %resource_linearSamplers %tmp_5|OpSampledImage %sampled_sampler2D %tmp_4 %tmp_7|OpImageSampleExplicitLod %vec4 %tmp_9 %tmp_8 Lod %const_float__0_0"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpCapability StorageBufferArrayNonUniformIndexingEXT"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|manualTextureCompareKernels=0|resources.1.arrayDimensions=1|resources.2.arrayDimensions=1|targetResourceBindings.1.arrayDimensions=1|targetResourceBindings.2.arrayDimensions=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.binding=0|values.storageBufferLayout.arrayStrideBytes=16|maps.sourceType=sampler2D[]|maps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|maps.bindingClass=sampledImage|maps.storageClass=UniformConstant|maps.spirvType=OpTypeRuntimeArray<OpTypeImage<float, 2D, sampled=1>>|maps.set=0|maps.binding=1|maps.arraySize=|maps.arrayDimensions.0.kind=runtime|linearSamplers.sourceType=sampler[]|linearSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSamplers.bindingClass=sampler|linearSamplers.storageClass=UniformConstant|linearSamplers.spirvType=OpTypeRuntimeArray<OpTypeSampler>|linearSamplers.set=0|linearSamplers.binding=2|linearSamplers.arraySize=|linearSamplers.arrayDimensions.0.kind=runtime|descriptors.sourceType=int*|descriptors.bindingClass=storageBuffer|descriptors.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|descriptors.binding=3|descriptors.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|sampled-texture.kind=resource|runtime-array.kind=layout|descriptor-array.kind=resource|runtime-descriptor-array.kind=resource|runtime-texture-descriptor-array.kind=resource|sampler-state.kind=resource|runtime-sampler-descriptor-array.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_runtime_shadow_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_RUNTIME_SHADOW_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-shadow-descriptor-array.cglb
      -DEXPECTED_MODULE=VulkanRuntimeShadowDescriptorArrayShader
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      "-DEXPECTED_SPVASM_CONTAINS=OpCapability RuntimeDescriptorArrayEXT|OpExtension \"SPV_EXT_descriptor_indexing\"|OpEntryPoint GLCompute %compute_main \"main\" %resource_values %resource_shadowMaps %resource_shadowSamplers|OpDecorate %resource_shadowMaps Binding 1|OpDecorate %resource_shadowSamplers Binding 2|%image_depth_2D = OpTypeImage %float 2D 1 0 0 1 Unknown|%runtimearr_image_sampler2DShadow__ = OpTypeRuntimeArray %image_depth_2D|%ptr_UniformConstant_sampledImage_sampler2DShadow__ = OpTypePointer UniformConstant %runtimearr_image_sampler2DShadow__|%runtimearr_sampler_comparison_sampler__ = OpTypeRuntimeArray %sampler|%ptr_UniformConstant_sampler_comparison_sampler__ = OpTypePointer UniformConstant %runtimearr_sampler_comparison_sampler__|%sampled_sampler2DShadow = OpTypeSampledImage %image_depth_2D|%resource_shadowMaps = OpVariable %ptr_UniformConstant_sampledImage_sampler2DShadow__ UniformConstant|%resource_shadowSamplers = OpVariable %ptr_UniformConstant_sampler_comparison_sampler__ UniformConstant|OpAccessChain %ptr_UniformConstant_sampledImage_sampler2DShadow %resource_shadowMaps %const_int__0|OpAccessChain %ptr_UniformConstant_sampler_comparison_sampler %resource_shadowSamplers %const_int__0|OpSampledImage %sampled_sampler2DShadow|OpImageSampleDrefExplicitLod %float|%const_float__0_25 Lod %const_float__0_0"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/VulkanRuntimeShadowDescriptorArrayShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|manualTextureCompareKernels=0|resources.1.arrayDimensions=1|resources.2.arrayDimensions=1|targetResourceBindings.1.arrayDimensions=1|targetResourceBindings.2.arrayDimensions=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.binding=0|values.storageBufferLayout.arrayStrideBytes=4|shadowMaps.sourceType=sampler2DShadow[]|shadowMaps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowMaps.bindingClass=sampledImage|shadowMaps.storageClass=UniformConstant|shadowMaps.spirvType=OpTypeRuntimeArray<OpTypeImage<depth_compare, 2D, sampled=1>>|shadowMaps.set=0|shadowMaps.binding=1|shadowMaps.arraySize=|shadowMaps.arrayDimensions.0.kind=runtime|shadowSamplers.sourceType=comparison_sampler[]|shadowSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|shadowSamplers.bindingClass=sampler|shadowSamplers.storageClass=UniformConstant|shadowSamplers.spirvType=OpTypeRuntimeArray<OpTypeSampler>|shadowSamplers.set=0|shadowSamplers.binding=2|shadowSamplers.arraySize=|shadowSamplers.arrayDimensions.0.kind=runtime"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|sampled-texture.kind=resource|runtime-array.kind=layout|descriptor-array.kind=resource|runtime-descriptor-array.kind=resource|runtime-texture-descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|runtime-sampler-descriptor-array.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_runtime_texture_descriptor_array_conflict_planned_failure
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_RUNTIME_TEXTURE_DESCRIPTOR_ARRAY_CONFLICT_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-texture-descriptor-array-conflict.cglb
      -DTARGET=vulkan
      -DEXPECT_NO_OUTPUT_PACKAGE=ON
      -DEXPECTED_DIAGNOSTIC=target.unsupported
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
      "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=error|target=vulkan|location.line=5|location.column=52|location.length=4|location.endLine=5|location.endColumn=56"
      "-DEXPECTED_DIAGNOSTIC_ARRAY_CONTAINS=missingCapabilities=vulkan.backend.vulkan-prototype-package|missingCapabilities=vulkan.diagnostic.vulkan.prototype-unsupported-runtime-resource-array"
      "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=target 'vulkan' cannot build a package for this module|message=runtime descriptor array 'maps' (texture) at set 0 binding 1 conflicts with runtime descriptor array 'detailMaps' (texture) at set 0 binding 2|message=Vulkan descriptor binding class 'sampledImage' (VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE)|message=policy allow-single-unbounded-descriptor-array permits only one unbounded descriptor array per Vulkan descriptor binding class|message=vulkan.backend.vulkan-prototype-package|message=vulkan.diagnostic.vulkan.prototype-unsupported-runtime-resource-array|message=TargetLegalizationResult: state=rejected|message=provenance=unsupported-native-form|message=target-legalization.v1.vulkan.capability.missing.vulkan.diagnostic.vulkan.prototype-unsupported-runtime-resource-array"
      -DMODE=planned-build-failure
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_resource_array_access_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_RESOURCE_ARRAY_ACCESS_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-resource-array-access.cglb
      -DEXPECTED_MODULE=ResourceArrayAccessShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=3
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=lights.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER|lights.bindingClass=uniformBuffer|lights.arrayElementCount=2|shadowMaps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowMaps.arrayElementCount=3|comparisonSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|comparisonSamplers.arrayElementCount=2"
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_Uniform_float %resource_lights %const_int__1 %const_int__1"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_only_descriptor_array_sample_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-only-descriptor-array-sample.cglb
      -DEXPECTED_MODULE=TextureOnlyDescriptorArraySampleShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleExplicitLod %vec4 %tmp_4 %tmp_3 Lod %const_float__0_0"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/TextureOnlyDescriptorArraySampleShader.spvasm|artifacts.nativeBinary=backend/vulkan/TextureOnlyDescriptorArraySampleShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/TextureOnlyDescriptorArraySampleShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|colorMaps.bindingClass=sampledImage|colorMaps.binding=2|colorMaps.arraySize=TEXTURE_COUNT|colorMaps.arrayElementCount=2|linearSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSampler.bindingClass=sampler|linearSampler.binding=5"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=texture-sample.kind=operation|texture-explicit-lod.kind=operation|descriptor-array.kind=resource"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_sampler_only_descriptor_array_sample_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-sampler-only-descriptor-array-sample.cglb
      -DEXPECTED_MODULE=SamplerOnlyDescriptorArraySampleShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLER
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleExplicitLod %vec4 %tmp_4 %tmp_3 Lod %const_float__0_0"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/SamplerOnlyDescriptorArraySampleShader.spvasm|artifacts.nativeBinary=backend/vulkan/SamplerOnlyDescriptorArraySampleShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/SamplerOnlyDescriptorArraySampleShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMap.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|colorMap.bindingClass=sampledImage|colorMap.binding=2|linearSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSamplers.bindingClass=sampler|linearSamplers.binding=5|linearSamplers.arraySize=SAMPLER_COUNT|linearSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampler-state.kind=resource|texture-explicit-lod.kind=operation|descriptor-array.kind=resource"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_only_nonuniform_descriptor_array_sample_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-only-nonuniform-descriptor-array-sample.cglb
      -DEXPECTED_MODULE=TextureOnlyNonUniformDescriptorArraySampleShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpCapability SampledImageArrayNonUniformIndexingEXT"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_sampler_only_nonuniform_descriptor_array_sample_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-sampler-only-nonuniform-descriptor-array-sample.cglb
      -DEXPECTED_MODULE=SamplerOnlyNonUniformDescriptorArraySampleShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLER
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpCapability SampledImageArrayNonUniformIndexingEXT"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_only_nonuniform_descriptor_array_sample_parity_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-only-nonuniform-descriptor-array-sample-parity.cglb
      -DEXPECTED_MODULE=TextureOnlyNonUniformDescriptorArraySampleShader
      "-DEXPECTED_SPVASM_CONTAINS=OpExtension \"SPV_EXT_descriptor_indexing\"|OpCapability ShaderNonUniformEXT|OpCapability SampledImageArrayNonUniformIndexingEXT|OpDecorate %tmp_2 NonUniformEXT|OpDecorate %tmp_3 NonUniformEXT|OpDecorate %tmp_4 NonUniformEXT|OpDecorate %tmp_7 NonUniformEXT|OpSampledImage %sampled_sampler2D %tmp_4 %tmp_5"
      "-DEXPECTED_SPVASM_ORDERED_CONTAINS=OpCapability Shader|OpCapability ShaderNonUniformEXT|OpCapability SampledImageArrayNonUniformIndexingEXT|OpExtension \"SPV_EXT_descriptor_indexing\"|OpMemoryModel Logical GLSL450|OpEntryPoint GLCompute %compute_main \"main\"|OpExecutionMode %compute_main LocalSize 1 1 1|OpDecorate %tmp_2 NonUniformEXT"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpCapability StorageBufferArrayNonUniformIndexingEXT|OpDecorate %tmp_5 NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_sampler_only_nonuniform_descriptor_array_sample_parity_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-sampler-only-nonuniform-descriptor-array-sample-parity.cglb
      -DEXPECTED_MODULE=SamplerOnlyNonUniformDescriptorArraySampleShader
      "-DEXPECTED_SPVASM_CONTAINS=OpExtension \"SPV_EXT_descriptor_indexing\"|OpCapability ShaderNonUniformEXT|OpCapability SampledImageArrayNonUniformIndexingEXT|OpDecorate %tmp_3 NonUniformEXT|OpDecorate %tmp_4 NonUniformEXT|OpDecorate %tmp_5 NonUniformEXT|OpDecorate %tmp_7 NonUniformEXT|OpSampledImage %sampled_sampler2D %tmp_2 %tmp_5"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpCapability StorageBufferArrayNonUniformIndexingEXT|OpDecorate %tmp_2 NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_texture_only_nonuniform_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-only-nonuniform-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureOnlyNonUniformCompareDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampledImage_sampler2DShadow %resource_shadowMaps %tmp_"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_sampler_only_nonuniform_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-sampler-only-nonuniform-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=SamplerOnlyNonUniformCompareDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLER
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampler_sampler %resource_shadowSamplers %tmp_"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_only_nonuniform_compare_descriptor_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-only-nonuniform-compare-descriptor-array-lod.cglb
      -DEXPECTED_MODULE=TextureOnlyNonUniformCompareDescriptorArrayLodShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=Lod %const_float__2_0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_sampler_only_nonuniform_compare_descriptor_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-sampler-only-nonuniform-compare-descriptor-array-lod.cglb
      -DEXPECTED_MODULE=SamplerOnlyNonUniformCompareDescriptorArrayLodShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLER
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=Lod %const_float__2_0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_only_nonuniform_compare_lod_manual_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-only-nonuniform-compare-lod-manual-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureOnlyNonUniformCompareLodManualDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampledImage_sampler2DArrayShadow %resource_shadowAtlases %tmp_"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_sampler_only_nonuniform_compare_lod_manual_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-sampler-only-nonuniform-compare-lod-manual-descriptor-array.cglb
      -DEXPECTED_MODULE=SamplerOnlyNonUniformCompareLodManualDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLER
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampler_sampler %resource_rawShadowSamplers %tmp_"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_cube_family_only_nonuniform_compare_lod_manual_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-cube-family-only-nonuniform-compare-lod-manual-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampledImage_samplerCubeArrayShadow %resource_shadowCubeArrays %tmp_"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|cube-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_sampler_cube_family_only_nonuniform_compare_lod_manual_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-sampler-cube-family-only-nonuniform-compare-lod-manual-descriptor-array.cglb
      -DEXPECTED_MODULE=SamplerCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLER
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampler_sampler %resource_rawShadowSamplers %tmp_"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|cube-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_family_only_nonuniform_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-family-only-nonuniform-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureFamilyOnlyNonUniformCompareDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampledImage_samplerCubeArrayShadow %resource_shadowCubeArrays %tmp_"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_sampler_family_only_nonuniform_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-sampler-family-only-nonuniform-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=SamplerFamilyOnlyNonUniformCompareDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLER
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampler_sampler %resource_shadowSamplers %tmp_"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|cube-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_compare_nonuniform_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-compare-nonuniform-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCompareNonUniformDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpDecorate %tmp_9 NonUniformEXT"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/TextureCompareNonUniformDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/TextureCompareNonUniformDescriptorArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/TextureCompareNonUniformDescriptorArrayShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=descriptors.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|descriptors.bindingClass=storageBuffer|descriptors.binding=1|shadowMaps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowMaps.bindingClass=sampledImage|shadowMaps.binding=2|shadowMaps.arraySize=SHADOW_COUNT|shadowMaps.arrayElementCount=2|shadowSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|shadowSamplers.bindingClass=sampler|shadowSamplers.binding=5|shadowSamplers.arraySize=SHADOW_COUNT|shadowSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_compare_nonuniform_descriptor_array_parity_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-compare-nonuniform-descriptor-array-parity.cglb
      -DEXPECTED_MODULE=TextureCompareNonUniformDescriptorArrayShader
      "-DEXPECTED_SPVASM_CONTAINS=OpExtension \"SPV_EXT_descriptor_indexing\"|OpCapability ShaderNonUniformEXT|OpCapability SampledImageArrayNonUniformIndexingEXT|OpDecorate %tmp_2 NonUniformEXT|OpDecorate %tmp_3 NonUniformEXT|OpDecorate %tmp_4 NonUniformEXT|OpDecorate %tmp_5 NonUniformEXT|OpDecorate %tmp_6 NonUniformEXT|OpDecorate %tmp_7 NonUniformEXT|OpDecorate %tmp_9 NonUniformEXT|OpAccessChain %ptr_UniformConstant_sampledImage_sampler2DShadow %resource_shadowMaps %tmp_2|OpAccessChain %ptr_UniformConstant_sampler_sampler %resource_shadowSamplers %tmp_5|OpSampledImage %sampled_sampler2DShadow %tmp_4 %tmp_7|OpImageSampleDrefExplicitLod %float %tmp_9 %tmp_8 %const_float__0_25 Lod %const_float__0_0"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpCapability StorageBufferArrayNonUniformIndexingEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_texture_compare_nonuniform_descriptor_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-compare-nonuniform-descriptor-array-lod.cglb
      -DEXPECTED_MODULE=TextureCompareNonUniformDescriptorArrayLodShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=Lod %const_float__2_0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_compare_nonuniform_descriptor_array_lod_parity_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-compare-nonuniform-descriptor-array-lod-parity.cglb
      -DEXPECTED_MODULE=TextureCompareNonUniformDescriptorArrayLodShader
      "-DEXPECTED_SPVASM_CONTAINS=OpExtension \"SPV_EXT_descriptor_indexing\"|OpCapability ShaderNonUniformEXT|OpCapability SampledImageArrayNonUniformIndexingEXT|OpDecorate %tmp_9 NonUniformEXT|OpImageSampleDrefExplicitLod %float %tmp_9 %tmp_8 %const_float__0_25 Lod %const_float__2_0"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpCapability StorageBufferArrayNonUniformIndexingEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_texture_compare_lod_manual_nonuniform_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-compare-lod-manual-nonuniform-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCompareLodManualNonUniformDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpFOrdLessThanEqual %bool"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/TextureCompareLodManualNonUniformDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/TextureCompareLodManualNonUniformDescriptorArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/TextureCompareLodManualNonUniformDescriptorArrayShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=descriptors.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|descriptors.bindingClass=storageBuffer|descriptors.binding=1|shadowAtlases.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowAtlases.bindingClass=sampledImage|shadowAtlases.binding=2|shadowAtlases.arraySize=SHADOW_COUNT|shadowAtlases.arrayElementCount=2|rawShadowSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.binding=5|rawShadowSamplers.arraySize=RAW_SAMPLER_COUNT|rawShadowSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=texture-shadow-compare-explicit-lod-manual.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_compare_lod_manual_nonuniform_descriptor_array_parity_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-compare-lod-manual-nonuniform-descriptor-array-parity.cglb
      -DEXPECTED_MODULE=TextureCompareLodManualNonUniformDescriptorArrayShader
      "-DEXPECTED_SPVASM_CONTAINS=OpExtension \"SPV_EXT_descriptor_indexing\"|OpCapability ShaderNonUniformEXT|OpCapability SampledImageArrayNonUniformIndexingEXT|OpDecorate %tmp_2 NonUniformEXT|OpDecorate %tmp_3 NonUniformEXT|OpDecorate %tmp_4 NonUniformEXT|OpDecorate %tmp_5 NonUniformEXT|OpDecorate %tmp_6 NonUniformEXT|OpDecorate %tmp_7 NonUniformEXT|OpDecorate %tmp_9 NonUniformEXT|OpAccessChain %ptr_UniformConstant_sampledImage_sampler2DArrayShadow %resource_shadowAtlases %tmp_2|OpAccessChain %ptr_UniformConstant_sampler_sampler %resource_rawShadowSamplers %tmp_5|OpSampledImage %sampled_sampler2DArrayShadow %tmp_4 %tmp_7|OpImageSampleExplicitLod %vec4 %tmp_9 %tmp_8 Lod %const_float__2_0|OpFOrdLessThanEqual %bool"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpCapability StorageBufferArrayNonUniformIndexingEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_texture_cube_family_compare_lod_manual_nonuniform_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-cube-family-compare-lod-manual-nonuniform-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpFOrdGreaterThan %bool"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|cube-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|SampledImageArrayNonUniformIndexingEXT.kind=capability|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_sampler_descriptor_array_size_mismatch_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_SIZE_MISMATCH_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-sampler-descriptor-array-size-mismatch.cglb
      -DEXPECTED_MODULE=TextureSamplerDescriptorArraySizeMismatchShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=3
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampler_sampler %resource_linearSamplers %const_int__2"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_sampler_array_descriptors_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_DESCRIPTOR_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-sampler-array-descriptors.cglb
      -DEXPECTED_MODULE=VulkanTextureSamplerArrayDescriptorShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpTypeArray %image_2D"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_sampler_array_access_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_ACCESS_UNSUPPORTED_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-sampler-array-access.cglb
      -DEXPECTED_MODULE=VulkanTextureSamplerArrayAccessUnsupportedShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=Lod %const_float__0_0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_sampler_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-sampler-array-lod.cglb
      -DEXPECTED_MODULE=VulkanTextureSamplerArrayLodShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleExplicitLod"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_sampler_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-sampler-lod.cglb
      -DEXPECTED_MODULE=VulkanTextureSamplerLodShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleExplicitLod"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_sampler_3d_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_3D_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-sampler-3d-lod.cglb
      -DEXPECTED_MODULE=VulkanTextureSampler3DLodShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=OpTypeImage %float 3D"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_sampler_3d_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_3D_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-sampler-3d-array-lod.cglb
      -DEXPECTED_MODULE=VulkanTextureSampler3DArrayLodShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampledImage_sampler3D"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_sampler_cube_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_CUBE_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-sampler-cube-lod.cglb
      -DEXPECTED_MODULE=VulkanTextureSamplerCubeLodShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=OpTypeImage %float Cube"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_sampler_cube_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_CUBE_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-sampler-cube-array-lod.cglb
      -DEXPECTED_MODULE=VulkanTextureSamplerCubeArrayLodShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampledImage_samplerCube"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_integer_texture_sampler_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_INTEGER_TEXTURE_SAMPLER_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-integer-texture-sampler-lod.cglb
      -DEXPECTED_MODULE=VulkanIntegerTextureSamplerLodShader
      -DEXPECTED_STORAGE_ELEMENT=ivec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=OpTypeImage %int 2D"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_integer_texture_array_sampler_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_INTEGER_TEXTURE_ARRAY_SAMPLER_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-integer-texture-array-sampler-lod.cglb
      -DEXPECTED_MODULE=VulkanIntegerTextureArraySamplerLodShader
      -DEXPECTED_STORAGE_ELEMENT=ivec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=OpTypeImage %int 2D 0 1 0 1 Unknown"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_array_dimensions_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ARRAY_DIMENSION_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-array-dimensions.cglb
      -DEXPECTED_MODULE=TextureArrayDimensionShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=OpTypeImage %float 2D 0 1 0 1 Unknown"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_compare_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_SHADOW_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-compare.cglb
      -DEXPECTED_MODULE=TextureCompareShadowShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleDrefExplicitLod"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_comparison_sampler_role_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_COMPARISON_SAMPLER_ROLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-comparison-sampler-role.cglb
      -DEXPECTED_MODULE=ComparisonSamplerRoleShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=%resource_shadowCompareSamplers"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_only_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-only-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureOnlyCompareDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampledImage_sampler2DShadow %resource_shadowMaps %const_int__1"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_sampler_only_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-sampler-only-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=SamplerOnlyCompareDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLER
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampler_sampler %resource_shadowSamplers %const_int__1"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCompareDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleDrefExplicitLod %float %tmp_5 %tmp_4 %const_float__0_25 Lod %const_float__0_0"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/TextureCompareDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/TextureCompareDescriptorArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/TextureCompareDescriptorArrayShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowMaps.bindingClass=sampledImage|shadowMaps.binding=2|shadowMaps.arraySize=SHADOW_COUNT|shadowMaps.arrayElementCount=2|shadowSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|shadowSamplers.bindingClass=sampler|shadowSamplers.binding=5|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=depth-compare-format.kind=texture|sampler-state.kind=resource|descriptor-array.kind=resource|texture-shadow-compare.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_array_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-array-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureArrayCompareDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampledImage_sampler2DArrayShadow %resource_shadowAtlases %const_int__1"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_cube_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-cube-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCubeCompareDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampledImage_samplerCubeArrayShadow %resource_shadowCubeArrays %const_int__1"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_array_shadow_compare_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ARRAY_SHADOW_COMPARE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-array-shadow-compare.cglb
      -DEXPECTED_MODULE=TextureArrayShadowCompareShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleDrefExplicitLod"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_compare_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-compare-lod.cglb
      -DEXPECTED_MODULE=TextureCompareLodShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=Lod %const_float__2_0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_2d_shadow_compare_lod_manual_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-2d-shadow-compare-lod-manual.cglb
      -DEXPECTED_MODULE=Texture2DShadowCompareLodManualShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpFOrdLessThan %bool"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_2d_array_shadow_compare_lod_manual_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-2d-array-shadow-compare-lod-manual.cglb
      -DEXPECTED_MODULE=Texture2DArrayShadowCompareLodManualShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpFOrdLessThanEqual %bool"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_2d_shadow_compare_lod_manual_offset_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-2d-shadow-compare-lod-manual-offset.cglb
      -DEXPECTED_MODULE=Texture2DShadowCompareLodManualOffsetShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=ConstOffset"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_2d_array_shadow_compare_lod_manual_offset_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-2d-array-shadow-compare-lod-manual-offset.cglb
      -DEXPECTED_MODULE=Texture2DArrayShadowCompareLodManualOffsetShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=ConstOffset"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_2d_shadow_compare_lod_manual_gather_2x2_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_GATHER_2X2_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-2d-shadow-compare-lod-manual-gather-2x2.cglb
      -DEXPECTED_MODULE=Texture2DShadowCompareLodManualGather2x2Shader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_CONTAINS=ConstOffset %const_float__2_0 %const_ivec2_0_0|ConstOffset %const_float__2_0 %const_ivec2_1_0|ConstOffset %const_float__2_0 %const_ivec2_0_1|ConstOffset %const_float__2_0 %const_ivec2_1_1|OpFMul %float"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_2d_array_shadow_compare_lod_manual_gather_2x2_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_GATHER_2X2_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-2d-array-shadow-compare-lod-manual-gather-2x2.cglb
      -DEXPECTED_MODULE=Texture2DArrayShadowCompareLodManualGather2x2Shader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_CONTAINS=ConstOffset %const_float__2_0 %const_ivec2_0_0|ConstOffset %const_float__2_0 %const_ivec2_1_0|ConstOffset %const_float__2_0 %const_ivec2_0_1|ConstOffset %const_float__2_0 %const_ivec2_1_1|OpFMul %float"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_2d_shadow_compare_lod_manual_kernel_4_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_4_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-2d-shadow-compare-lod-manual-kernel-4.cglb
      -DEXPECTED_MODULE=Texture2DShadowCompareLodManualKernel4Shader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpFMul %float"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_2d_array_shadow_compare_lod_manual_kernel_4_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_KERNEL_4_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-2d-array-shadow-compare-lod-manual-kernel-4.cglb
      -DEXPECTED_MODULE=Texture2DArrayShadowCompareLodManualKernel4Shader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleExplicitLod %vec4 %tmp_3 %tmp_2 Lod|ConstOffset %const_float__2_0 %const_ivec2_neg1_neg1"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/Texture2DArrayShadowCompareLodManualKernel4Shader.spvasm|artifacts.nativeBinary=backend/vulkan/Texture2DArrayShadowCompareLodManualKernel4Shader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/Texture2DArrayShadowCompareLodManualKernel4Shader.spv|manualTextureCompareKernelSummary.totalCount=1|manualTextureCompareKernelSummary.staticNormalizedCount=1|manualTextureCompareKernels.0.operation=textureCompareLodManualKernel4|manualTextureCompareKernels.0.canonicalOperation=textureCompareLodManualKernel|manualTextureCompareKernels.0.tapCount=4|manualTextureCompareKernels.0.weightClass=static-normalized"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlas.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowAtlas.bindingClass=sampledImage|shadowAtlas.binding=2|rawShadowSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|rawShadowSampler.bindingClass=sampler|rawShadowSampler.binding=5"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=array-dimension.kind=texture|texture-shadow-compare-explicit-lod-manual.kind=operation|texture-shadow-compare-explicit-lod-manual-kernel-list.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_2d_shadow_compare_lod_manual_kernel_8_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_8_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-2d-shadow-compare-lod-manual-kernel-8.cglb
      -DEXPECTED_MODULE=Texture2DShadowCompareLodManualKernel8Shader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpFMul %float"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_2d_array_shadow_compare_lod_manual_kernel_8_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_KERNEL_8_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-2d-array-shadow-compare-lod-manual-kernel-8.cglb
      -DEXPECTED_MODULE=Texture2DArrayShadowCompareLodManualKernel8Shader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpFMul %float"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_2d_shadow_compare_lod_manual_kernel_list_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-2d-shadow-compare-lod-manual-kernel-list.cglb
      -DEXPECTED_MODULE=Texture2DShadowCompareLodManualKernelListShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleExplicitLod %vec4 %tmp_3 %tmp_2 Lod|ConstOffset %const_float__2_0 %const_ivec2_0_0"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=Texture2DShadowCompareLodManualKernelListShader|sourceHash.algorithm=sha256"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=Texture2DShadowCompareLodManualKernelListShader|nativeBinary=backend/vulkan/Texture2DShadowCompareLodManualKernelListShader.spv|manualTextureCompareKernelSummary.totalCount=1|manualTextureCompareKernelSummary.staticNormalizedCount=1|manualTextureCompareKernels.0.operation=textureCompareLodManualKernel|manualTextureCompareKernels.0.sourceKind=tap-list|manualTextureCompareKernels.0.tapCount=5|manualTextureCompareKernels.0.weightClass=static-normalized"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.storageBufferLayout.layout=std430|shadowMap.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowMap.bindingClass=sampledImage|rawShadowSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|rawShadowSampler.bindingClass=sampler"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=depth-compare-format.kind=texture|texture-shadow-compare-explicit-lod-manual.kind=operation|texture-shadow-compare-explicit-lod-manual-kernel-list.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_cube_shadow_compare_lod_manual_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_MANUAL_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-cube-shadow-compare-lod-manual.cglb
      -DEXPECTED_MODULE=TextureCubeShadowCompareLodManualShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpFOrdGreaterThanEqual %bool"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_cube_array_shadow_compare_lod_manual_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-cube-array-shadow-compare-lod-manual.cglb
      -DEXPECTED_MODULE=TextureCubeArrayShadowCompareLodManualShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpFOrdGreaterThan %bool"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_compare_lod_manual_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-compare-lod-manual-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCompareLodManualDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleExplicitLod %vec4 %tmp_5 %tmp_4 Lod %const_float__2_0"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/TextureCompareLodManualDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/TextureCompareLodManualDescriptorArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/TextureCompareLodManualDescriptorArrayShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowAtlases.bindingClass=sampledImage|shadowAtlases.binding=2|shadowAtlases.arraySize=SHADOW_COUNT|shadowAtlases.arrayElementCount=2|rawShadowSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.binding=5|rawShadowSamplers.arraySize=RAW_SAMPLER_COUNT|rawShadowSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=array-dimension.kind=texture|texture-shadow-compare-explicit-lod-manual.kind=operation|descriptor-array.kind=resource"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_compare_descriptor_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-compare-descriptor-array-lod.cglb
      -DEXPECTED_MODULE=TextureCompareDescriptorArrayLodShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleDrefExplicitLod %float %tmp_5 %tmp_4 %const_float__0_25 Lod %const_float__2_0"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/TextureCompareDescriptorArrayLodShader.spvasm|artifacts.nativeBinary=backend/vulkan/TextureCompareDescriptorArrayLodShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/TextureCompareDescriptorArrayLodShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowMaps.bindingClass=sampledImage|shadowMaps.binding=2|shadowMaps.arraySize=2|shadowMaps.arrayElementCount=2|shadowSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|shadowSamplers.bindingClass=sampler|shadowSamplers.binding=5|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=depth-compare-format.kind=texture|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|descriptor-array.kind=resource"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_array_compare_descriptor_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-array-compare-descriptor-array-lod.cglb
      -DEXPECTED_MODULE=TextureArrayCompareDescriptorArrayLodShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=Lod %const_float__2_0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_texture_cube_compare_descriptor_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-texture-cube-compare-descriptor-array-lod.cglb
      -DEXPECTED_MODULE=TextureCubeCompareDescriptorArrayLodShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=Lod %const_float__4_0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|cube-dimension.kind=texture|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_mixed_texture_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_MIXED_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-mixed-texture-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=MixedTextureCompareDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleExplicitLod %vec4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation|vector-arithmetic.kind=operation|storage-buffer-write.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_mixed_texture_manual_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_MIXED_TEXTURE_MANUAL_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-mixed-texture-manual-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=MixedTextureManualCompareDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleExplicitLod %vec4 %tmp_26 %tmp_25 Lod %const_float__2_0"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=artifacts.backendAssembly=backend/vulkan/MixedTextureManualCompareDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/MixedTextureManualCompareDescriptorArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=nativeBinary=backend/vulkan/MixedTextureManualCompareDescriptorArrayShader.spv|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|colorMaps.bindingClass=sampledImage|colorMaps.binding=2|colorMaps.arrayElementCount=2|shadowMaps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowMaps.binding=4|shadowMaps.arrayElementCount=2|shadowAtlases.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowAtlases.binding=6|shadowAtlases.arrayElementCount=2|linearSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSamplers.binding=10|shadowSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|shadowSamplers.binding=12|rawShadowSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|rawShadowSamplers.binding=14|rawShadowSamplers.arraySize=RAW_SAMPLER_COUNT"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=texture-sample.kind=operation|texture-explicit-lod.kind=operation|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|texture-shadow-compare-explicit-lod-manual.kind=operation|descriptor-array.kind=resource"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_runtime_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_RUNTIME_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-array.cglb
      -DEXPECTED_MODULE=RuntimeArrayShader
      -DEXPECTED_STORAGE_ELEMENT=RuntimePayload
      -DEXPECTED_STORAGE_STRIDE=0
      -DEXPECTED_STRUCT_FIELD=values
      -DEXPECTED_STRUCT_FIELD_OFFSET=4
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpTypeRuntimeArray %float"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_runtime_array_dynamic_outer_index_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_RUNTIME_ARRAY_DYNAMIC_OUTER_INDEX_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-array-dynamic-outer-index.cglb
      -DEXPECTED_MODULE=RuntimeArrayDynamicOuterIndexShader
      -DEXPECTED_STORAGE_ELEMENT=RuntimePayload
      -DEXPECTED_STORAGE_STRIDE=0
      -DEXPECTED_STRUCT_FIELD=count
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_StorageBuffer_float %resource_payloads %const_int__0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_runtime_vector_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_RUNTIME_VECTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-vector-array.cglb
      -DEXPECTED_MODULE=RuntimeVectorArrayShader
      -DEXPECTED_STORAGE_ELEMENT=RuntimeVectorPayload
      -DEXPECTED_STORAGE_STRIDE=0
      -DEXPECTED_STRUCT_FIELD=values
      -DEXPECTED_STRUCT_FIELD_OFFSET=16
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=OpTypeRuntimeArray %vec4"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_runtime_struct_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_RUNTIME_STRUCT_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-struct-array.cglb
      -DEXPECTED_MODULE=RuntimeStructArrayShader
      -DEXPECTED_STORAGE_ELEMENT=RuntimeStructPayload
      -DEXPECTED_STORAGE_STRIDE=0
      -DEXPECTED_STRUCT_FIELD=particles
      -DEXPECTED_STRUCT_FIELD_OFFSET=16
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=OpTypeRuntimeArray %struct_TailParticle"
      -DEXPECTED_SPVASM_ACCESS_POINTER=ptr_StorageBuffer_vec3
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=RuntimeStructArrayShader|artifacts.nativeBinary=backend/vulkan/RuntimeStructArrayShader.spv|artifacts.backendAssembly=backend/vulkan/RuntimeStructArrayShader.spvasm"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=RuntimeStructArrayShader|nativeBinary=backend/vulkan/RuntimeStructArrayShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=payloads.sourceType=RuntimeStructPayload*|payloads.bindingClass=storageBuffer|payloads.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|payloads.spirvType=OpTypeRuntimeArray<RuntimeStructPayload>|payloads.storageBufferLayout.layout=std430|payloads.storageBufferLayout.elementType=RuntimeStructPayload|payloads.storageBufferLayout.fields.1.type=TailParticle[]|payloads.storageBufferLayout.fields.1.arrayDimensions.0.kind=runtime"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=runtime-array.kind=layout|runtime-array-field.kind=layout|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|vector-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_storage_buffer_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage.cglb
      -DEXPECTED_MODULE=StorageBufferComputeShader
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_add_python_expect_test(
    NAME cglc_manifest_json_schema_vulkan_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-manifest-schema.cglb
      -DEXPECTED_MODULE=StorageBufferComputeShader
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageBufferComputeShader|sourceHash.algorithm=sha256|packageArtifactRequirements.target=vulkan|packageArtifactRequirements.packageMode=native|packageArtifactRequirements.requiresNativeBinaryStatus=false|artifacts.backendAssembly=backend/vulkan/StorageBufferComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/StorageBufferComputeShader.spv|artifacts.nativeProfile=backend/vulkan/StorageBufferComputeShader.profile.json|artifacts.backendSourceMap=backend/vulkan/StorageBufferComputeShader.backend-source-map.json|artifacts.nativeArtifactDescriptor=backend/vulkan/StorageBufferComputeShader.native-artifact.json"
      "-DEXPECTED_MANIFEST_JSON_ABSENT_PATHS=artifacts.nativeBinaryStatus"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/StorageBufferComputeShader.spvasm|artifactPath=backend/vulkan/StorageBufferComputeShader.spv|validationStatus=validated"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=3|validationDiagnostics=0"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMANIFEST_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/manifest-v1.schema.json
      -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
      -DPACKAGE_SCHEMA_ROOT=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py
      -DMODE=vulkan-build)
  crossgl_add_python_expect_test(
    NAME cglc_reflection_json_schema_vulkan_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-reflection-schema.cglb
      -DEXPECTED_MODULE=StorageBufferComputeShader
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageBufferComputeShader|nativeBinary=backend/vulkan/StorageBufferComputeShader.spv"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.storageClass=StorageBuffer|values.spirvType=OpTypeRuntimeArray<float>|values.storageBufferLayout.layout=std430"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DREFLECTION_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/reflection-v1.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      -DMODE=vulkan-build)
  crossgl_add_python_expect_test(
    NAME cglc_package_inspect_json_schema_vulkan_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
      -DTARGET=vulkan
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-package-inspect.cglb
      -DMODE=package-inspect-source-package
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=StorageBufferComputeShader|summary.target=vulkan|summary.artifactCount=8|summary.debugArtifactsPresent=true|vulkanNativeProfile.health=ok|vulkanNativeProfile.spirvVersion=1.5|vulkanNativeProfile.nativeProfileExists=true|debugArtifacts.backendSourceMap.artifactPresent=true|debugArtifacts.backendSourceMap.exists=true|debugArtifacts.backendSourceMap.health=ok|debugArtifacts.backendSourceMap.path=backend/vulkan/StorageBufferComputeShader.backend-source-map.json|debugArtifacts.backendSourceMap.target=vulkan|debugArtifacts.backendSourceMap.module=StorageBufferComputeShader|debugArtifacts.backendSourceMap.mappingGranularity=statement|debugArtifacts.backendSourceMap.sourceBackend=crossgl-hir|debugArtifacts.backendSourceMap.targetBackend=spvasm|debugArtifacts.backendSourceMap.backendLanguage=spvasm|debugArtifacts.backendSourceMap.checks.backendLineCountPresent=true|debugArtifacts.backendSourceMap.checks.backendLineCountMatchesSource=true|debugArtifacts.backendSourceMap.checks.backendSpansWithinSource=true|debugArtifacts.backendSourceMap.checks.mappingCountMatchesMappings=true|rootFiles.0.name=manifest|rootFiles.0.exists=true|rootFiles.1.name=reflection|rootFiles.1.exists=true|rootFiles.2.name=diagnostics|rootFiles.2.exists=true|artifacts.0.name=backendAssembly|artifacts.0.path=backend/vulkan/StorageBufferComputeShader.spvasm|artifacts.0.exists=true|artifacts.1.name=nativeBinary|artifacts.1.path=backend/vulkan/StorageBufferComputeShader.spv|artifacts.1.exists=true|artifacts.2.name=nativeProfile|artifacts.2.path=backend/vulkan/StorageBufferComputeShader.profile.json|artifacts.2.exists=true|artifacts.3.name=debugMetadata|artifacts.3.exists=true|artifacts.4.name=hirSourceMap|artifacts.4.exists=true|artifacts.5.name=backendSourceMap|artifacts.5.path=backend/vulkan/StorageBufferComputeShader.backend-source-map.json|artifacts.5.exists=true|artifacts.6.name=nativeArtifactDescriptor|artifacts.6.path=backend/vulkan/StorageBufferComputeShader.native-artifact.json|artifacts.6.exists=true|manifest.target=vulkan|manifest.module=StorageBufferComputeShader|manifest.artifacts.backendSourceMap=backend/vulkan/StorageBufferComputeShader.backend-source-map.json|manifest.artifacts.nativeArtifactDescriptor=backend/vulkan/StorageBufferComputeShader.native-artifact.json|nativeArtifactDescriptor.health=ok|nativeArtifactDescriptor.target=vulkan|nativeArtifactDescriptor.binaryKind=vulkan.spirv-module|nativeArtifactDescriptor.sourcePath=backend/vulkan/StorageBufferComputeShader.spvasm|nativeArtifactDescriptor.artifactPath=backend/vulkan/StorageBufferComputeShader.spv|nativeArtifactDescriptor.validationStatus=validated|nativeArtifactDescriptor.checks.sourceHashMatchesFile=true|nativeArtifactDescriptor.checks.artifactHashMatchesFile=true|nativeArtifactDescriptor.checks.sizeBytesMatchesFile=true|reflection.target=vulkan|reflection.module=StorageBufferComputeShader|reflection.nativeBinary=backend/vulkan/StorageBufferComputeShader.spv|diagnostics.schemaVersion=1"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/StorageBufferComputeShader.spvasm|artifactPath=backend/vulkan/StorageBufferComputeShader.spv|validationStatus=validated"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=3|validationDiagnostics=0"
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
      -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
  crossgl_add_python_expect_test(
    NAME cglc_package_inspect_vulkan_disassembly_sidecar_emitted
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
      -DTARGET=vulkan
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-package-inspect-disassembly-emitted.cglb
      -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_SUCCESS_DIR}
      -DTOOLCHAIN_DISABLE_FALLBACK=ON
      -DMODE=package-inspect-source-package
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=StorageBufferComputeShader|summary.target=vulkan|summary.nativeBinaryStatus=null|summary.artifactCount=8|vulkanNativeProfile.health=ok|vulkanNativeProfile.nativeProfileExists=true|vulkanNativeProfile.disassemblyStatus=emitted|vulkanNativeProfile.disassemblyPath=backend/vulkan/StorageBufferComputeShader.disassembly.spvasm|vulkanNativeProfile.disassemblyExists=true|vulkanNativeProfile.checks.emittedDisassemblyExists=true|artifacts.0.name=backendAssembly|artifacts.1.name=nativeBinary|artifacts.2.name=nativeProfile|artifacts.5.name=backendSourceMap|artifacts.5.path=backend/vulkan/StorageBufferComputeShader.backend-source-map.json|artifacts.5.exists=true|artifacts.6.name=nativeArtifactDescriptor|artifacts.6.path=backend/vulkan/StorageBufferComputeShader.native-artifact.json|artifacts.6.exists=true|artifacts.7.name=targetExplanation|artifacts.7.path=ir/target-explanation.json|artifacts.7.exists=true|manifest.artifacts.nativeProfile=backend/vulkan/StorageBufferComputeShader.profile.json|manifest.artifacts.backendSourceMap=backend/vulkan/StorageBufferComputeShader.backend-source-map.json|manifest.artifacts.nativeArtifactDescriptor=backend/vulkan/StorageBufferComputeShader.native-artifact.json|manifest.artifacts.targetExplanation=ir/target-explanation.json|nativeArtifactDescriptor.health=ok|nativeArtifactDescriptor.target=vulkan|nativeArtifactDescriptor.binaryKind=vulkan.spirv-module|nativeArtifactDescriptor.sourcePath=backend/vulkan/StorageBufferComputeShader.spvasm|nativeArtifactDescriptor.artifactPath=backend/vulkan/StorageBufferComputeShader.spv|nativeArtifactDescriptor.validationStatus=validated"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/StorageBufferComputeShader.spvasm|artifactPath=backend/vulkan/StorageBufferComputeShader.spv|validationStatus=validated"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=artifacts=8|diagnostics.diagnostics=0"
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
      -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
  crossgl_add_python_expect_test(
    NAME cglc_package_inspect_vulkan_disassembly_failure_nonfatal
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
      -DTARGET=vulkan
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-package-inspect-disassembly-failed.cglb
      -DTOOLCHAIN_PATH=${CROSSGL_FAKE_VULKAN_DISASSEMBLY_FAILURE_DIR}
      -DTOOLCHAIN_DISABLE_FALLBACK=ON
      -DMODE=package-inspect-source-package
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=StorageBufferComputeShader|summary.target=vulkan|summary.nativeBinaryStatus=null|summary.artifactCount=8|vulkanNativeProfile.health=ok|vulkanNativeProfile.nativeProfileExists=true|vulkanNativeProfile.disassemblyStatus=failed|vulkanNativeProfile.disassemblyPath=null|vulkanNativeProfile.disassemblyExists=null|vulkanNativeProfile.checks.nativeBinaryMatchesManifest=true|vulkanNativeProfile.checks.emittedDisassemblyExists=null|artifacts.1.name=nativeBinary|artifacts.1.exists=true|artifacts.5.name=backendSourceMap|artifacts.5.path=backend/vulkan/StorageBufferComputeShader.backend-source-map.json|artifacts.5.exists=true|artifacts.6.name=nativeArtifactDescriptor|artifacts.6.path=backend/vulkan/StorageBufferComputeShader.native-artifact.json|artifacts.6.exists=true|artifacts.7.name=targetExplanation|artifacts.7.path=ir/target-explanation.json|artifacts.7.exists=true|manifest.artifacts.nativeBinary=backend/vulkan/StorageBufferComputeShader.spv|manifest.artifacts.backendSourceMap=backend/vulkan/StorageBufferComputeShader.backend-source-map.json|manifest.artifacts.nativeArtifactDescriptor=backend/vulkan/StorageBufferComputeShader.native-artifact.json|manifest.artifacts.targetExplanation=ir/target-explanation.json|nativeArtifactDescriptor.health=ok|nativeArtifactDescriptor.target=vulkan|nativeArtifactDescriptor.binaryKind=vulkan.spirv-module|nativeArtifactDescriptor.sourcePath=backend/vulkan/StorageBufferComputeShader.spvasm|nativeArtifactDescriptor.artifactPath=backend/vulkan/StorageBufferComputeShader.spv|nativeArtifactDescriptor.validationStatus=validated"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/StorageBufferComputeShader.spvasm|artifactPath=backend/vulkan/StorageBufferComputeShader.spv|validationStatus=validated"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=artifacts=8|diagnostics.diagnostics=1"
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
      -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
  crossgl_add_python_expect_test(
    NAME cglc_package_artifact_inventory_json_schema_vulkan_graphics_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_COMPARE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-artifact-inventory-schema.cglb
      -DEXPECTED_MODULE=VulkanGraphicsShadowCompareShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE
      -DEXPECTED_STORAGE_BUFFER_METADATA=FALSE
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowCompareShader|sourceHash.algorithm=sha256|artifacts.backendAssembly=backend/vulkan/VulkanGraphicsShadowCompareShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanGraphicsShadowCompareShader.spv|artifacts.nativeProfile=backend/vulkan/VulkanGraphicsShadowCompareShader.profile.json|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/vulkan/VulkanGraphicsShadowCompareShader.native-artifact.json|artifacts.targetExplanation=ir/target-explanation.json|artifacts.graphicsAbi=backend/vulkan/VulkanGraphicsShadowCompareShader.graphics-abi.json"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/VulkanGraphicsShadowCompareShader.spvasm|artifactPath=backend/vulkan/VulkanGraphicsShadowCompareShader.spv|validationStatus=validated"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanGraphicsShadowCompareShader|nativeBinary=backend/vulkan/VulkanGraphicsShadowCompareShader.spv|resources.0.stage=fragment|resources.0.name=shadowMap|resources.0.kind=texture|resources.0.type=sampler2DShadow|resources.0.binding=2|resources.1.stage=fragment|resources.1.name=shadowSampler|resources.1.kind=sampler|resources.1.type=comparison_sampler|resources.1.binding=3|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|functionConstants=0|workgroupSizes=0|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.stage=fragment|shadowMap.bindingClass=sampledImage|shadowMap.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|shadowMap.storageClass=UniformConstant|shadowMap.set=0|shadowMap.binding=2|shadowSampler.stage=fragment|shadowSampler.bindingClass=sampler|shadowSampler.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|shadowSampler.storageClass=UniformConstant|shadowSampler.set=0|shadowSampler.binding=3"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMANIFEST_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/manifest-v1.schema.json
      -DREFLECTION_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/reflection-v1.schema.json
      -DDEBUG_METADATA_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/debug-metadata-v11.schema.json
      -DHIR_SOURCE_MAP_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/hir-source-map-v7.schema.json
      -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
      -DPACKAGE_SCHEMA_ROOT=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py
      -DMODE=vulkan-build)
  crossgl_add_python_expect_test(
    NAME cglc_package_inspect_artifact_inventory_json_schema_vulkan_graphics_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_COMPARE_SHADER}
      -DTARGET=vulkan
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-graphics-package-inspect-artifact-inventory.cglb
      -DMODE=package-inspect-source-package
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=VulkanGraphicsShadowCompareShader|summary.target=vulkan|summary.nativeBinaryStatus=null|summary.artifactCount=8|summary.debugArtifactsPresent=true|vulkanNativeProfile.health=ok|vulkanNativeProfile.profileName=vulkan-prototype|vulkanNativeProfile.nativeProfileExists=true|debugArtifacts.debugMetadataArtifactPresent=true|debugArtifacts.hirSourceMapArtifactPresent=true|debugArtifacts.debugMetadataExists=true|debugArtifacts.hirSourceMapExists=true|debugArtifacts.health=ok|debugArtifacts.checks.hirSourceLocationsMatch=true|debugArtifacts.checks.sourceMapUnfiltered=true|debugArtifacts.checks.sourceMapUnpaged=true|debugArtifacts.checks.sourceMapRecordsDisabled=true|artifacts.0.name=backendAssembly|artifacts.0.path=backend/vulkan/VulkanGraphicsShadowCompareShader.spvasm|artifacts.0.exists=true|artifacts.1.name=nativeBinary|artifacts.1.path=backend/vulkan/VulkanGraphicsShadowCompareShader.spv|artifacts.1.exists=true|artifacts.2.name=nativeProfile|artifacts.2.path=backend/vulkan/VulkanGraphicsShadowCompareShader.profile.json|artifacts.2.exists=true|artifacts.3.name=debugMetadata|artifacts.3.path=ir/debug-metadata.json|artifacts.3.exists=true|artifacts.4.name=hirSourceMap|artifacts.4.path=ir/hir-source-map.json|artifacts.4.exists=true|artifacts.5.name=nativeArtifactDescriptor|artifacts.5.path=backend/vulkan/VulkanGraphicsShadowCompareShader.native-artifact.json|artifacts.5.exists=true|artifacts.6.name=targetExplanation|artifacts.6.path=ir/target-explanation.json|artifacts.6.exists=true|artifacts.7.name=graphicsAbi|artifacts.7.path=backend/vulkan/VulkanGraphicsShadowCompareShader.graphics-abi.json|artifacts.7.exists=true|manifest.target=vulkan|manifest.module=VulkanGraphicsShadowCompareShader|manifest.artifacts.backendAssembly=backend/vulkan/VulkanGraphicsShadowCompareShader.spvasm|manifest.artifacts.nativeBinary=backend/vulkan/VulkanGraphicsShadowCompareShader.spv|manifest.artifacts.nativeProfile=backend/vulkan/VulkanGraphicsShadowCompareShader.profile.json|manifest.artifacts.debugMetadata=ir/debug-metadata.json|manifest.artifacts.hirSourceMap=ir/hir-source-map.json|manifest.artifacts.nativeArtifactDescriptor=backend/vulkan/VulkanGraphicsShadowCompareShader.native-artifact.json|manifest.artifacts.targetExplanation=ir/target-explanation.json|manifest.artifacts.graphicsAbi=backend/vulkan/VulkanGraphicsShadowCompareShader.graphics-abi.json|nativeArtifactDescriptor.health=ok|nativeArtifactDescriptor.target=vulkan|nativeArtifactDescriptor.binaryKind=vulkan.spirv-module|nativeArtifactDescriptor.sourcePath=backend/vulkan/VulkanGraphicsShadowCompareShader.spvasm|nativeArtifactDescriptor.artifactPath=backend/vulkan/VulkanGraphicsShadowCompareShader.spv|nativeArtifactDescriptor.validationStatus=validated|nativeArtifactDescriptor.checks.sourceHashMatchesFile=true|nativeArtifactDescriptor.checks.artifactHashMatchesFile=true|nativeArtifactDescriptor.checks.sizeBytesMatchesFile=true|reflection.target=vulkan|reflection.module=VulkanGraphicsShadowCompareShader|reflection.nativeBinary=backend/vulkan/VulkanGraphicsShadowCompareShader.spv|reflection.entryPoints.0.stage=vertex|reflection.entryPoints.1.stage=fragment|reflection.resources.0.name=shadowMap|reflection.resources.1.name=shadowSampler|diagnostics.schemaVersion=1"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/VulkanGraphicsShadowCompareShader.spvasm|artifactPath=backend/vulkan/VulkanGraphicsShadowCompareShader.spv|validationStatus=validated"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=artifacts=8|reflection.entryPoints=2|reflection.resources=2|reflection.targetResourceBindings=2|reflection.vertexLayouts=1|reflection.workgroupSizes=0|diagnostics.diagnostics=0"
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
      -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
  add_test(NAME cglc_build_vulkan_storage_buffer_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_ARRAY_ACCESS_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage-buffer-array.cglb
      -DEXPECTED_MODULE=StorageBufferArrayAccessShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_StorageBuffer_float %resource_values %const_int__1 %const_int__0 %const_int__0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_struct_storage_buffer_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_STRUCT_ARRAY_ACCESS_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-struct-storage-buffer-array.cglb
      -DEXPECTED_MODULE=StorageBufferStructArrayAccessShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_StorageBuffer_float %resource_particles %const_int__1 %const_int__0 %const_int__0 %const_int__1"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageBufferStructArrayAccessShader|artifacts.nativeBinary=backend/vulkan/StorageBufferStructArrayAccessShader.spv|artifacts.backendAssembly=backend/vulkan/StorageBufferStructArrayAccessShader.spvasm"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageBufferStructArrayAccessShader|nativeBinary=backend/vulkan/StorageBufferStructArrayAccessShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*[2]|particles.bindingClass=storageBuffer|particles.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|particles.spirvType=OpTypeArray<OpTypeRuntimeArray<Particle>, 2>|particles.arrayElementCount=2|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=12"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=fixed-array.kind=layout|descriptor-array.kind=resource|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_struct_storage_buffer_array_field_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_BUFFER_STRUCT_ARRAY_FIELD_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-struct-storage-buffer-array-field.cglb
      -DEXPECTED_MODULE=StorageBufferStructArrayFieldDescriptorArrayShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=48
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      -DEXPECTED_STRUCT_FIELD=history
      -DEXPECTED_STRUCT_FIELD_OFFSET=16
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=2
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=16
      -DEXPECTED_SPVASM_STRUCT_FIELD_INDEX=1
      -DEXPECTED_SPVASM_STRUCT_FIELD_OFFSET=16
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_StorageBuffer_vec3 %resource_particles %const_int__1 %const_int__0 %const_int__0 %const_int__1 %const_int__1 %const_int__0"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageBufferStructArrayFieldDescriptorArrayShader|artifacts.nativeBinary=backend/vulkan/StorageBufferStructArrayFieldDescriptorArrayShader.spv|artifacts.backendAssembly=backend/vulkan/StorageBufferStructArrayFieldDescriptorArrayShader.spvasm"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageBufferStructArrayFieldDescriptorArrayShader|nativeBinary=backend/vulkan/StorageBufferStructArrayFieldDescriptorArrayShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*[2]|particles.bindingClass=storageBuffer|particles.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|particles.spirvType=OpTypeArray<OpTypeRuntimeArray<Particle>, 2>|particles.arrayElementCount=2|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.fields.0.type=float[4]|particles.storageBufferLayout.fields.1.type=Transform[2]|particles.storageBufferLayout.fields.1.arrayDimensions.0.kind=fixed"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=fixed-array.kind=layout|fixed-array-field.kind=layout|descriptor-array.kind=resource|scalar-vector-elements.kind=array|storage-buffer.kind=resource|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_mixed_resource_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_MIXED_RESOURCE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-mixed-resource-descriptor-array.cglb
      -DEXPECTED_MODULE=MixedResourceDescriptorArrayShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpImageSampleExplicitLod %vec4"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_mixed_resource_symbolic_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_MIXED_RESOURCE_SYMBOLIC_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-mixed-resource-symbolic-descriptor-array.cglb
      -DEXPECTED_MODULE=MixedResourceSymbolicDescriptorArrayShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_StorageBuffer_float %resource_particles %const_int__0 %const_int__0 %const_int__1 %const_int__1"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_dynamic_descriptor_array_index_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_DYNAMIC_DESCRIPTOR_ARRAY_INDEX_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-dynamic-descriptor-array-index.cglb
      -DEXPECTED_MODULE=VulkanDynamicDescriptorArrayIndexShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_UniformConstant_sampler_sampler %resource_linearSamplers %tmp_"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_nonuniform_descriptor_array_index_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_NONUNIFORM_DESCRIPTOR_ARRAY_INDEX_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-nonuniform-descriptor-array-index.cglb
      -DEXPECTED_MODULE=VulkanNonUniformDescriptorArrayIndexShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=16
      -DEXPECTED_RESOURCE_ARRAY_COUNT=2
      "-DEXPECTED_SPVASM_SNIPPET=OpCapability ShaderNonUniformEXT"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_nonuniform_descriptor_array_index_parity_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_NONUNIFORM_DESCRIPTOR_ARRAY_INDEX_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-nonuniform-descriptor-array-index-parity.cglb
      -DEXPECTED_MODULE=VulkanNonUniformDescriptorArrayIndexShader
      "-DEXPECTED_SPVASM_CONTAINS=OpExtension \"SPV_EXT_descriptor_indexing\"|OpCapability ShaderNonUniformEXT|OpCapability SampledImageArrayNonUniformIndexingEXT|OpCapability StorageBufferArrayNonUniformIndexingEXT|OpDecorate %tmp_3 NonUniformEXT|OpDecorate %tmp_2 NonUniformEXT|OpDecorate %tmp_13 NonUniformEXT|OpDecorate %tmp_18 NonUniformEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_read_modify_write_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_READ_MODIFY_WRITE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-read-modify-write.cglb
      -DEXPECTED_MODULE=ReadModifyWriteComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ReadModifyWriteComputeShader|nativeBinary=backend/vulkan/ReadModifyWriteComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpFAdd %float"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_arithmetic_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_ARITHMETIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-arithmetic.cglb
      -DEXPECTED_MODULE=ArithmeticComputeShader
      "-DEXPECTED_SPVASM_CONTAINS=OpEntryPoint GLCompute %compute_main \"main\"|OpExecutionMode %compute_main LocalSize 2 1 1|OpReturn"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_load_local_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_LOAD_LOCAL_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-load-local.cglb
      -DEXPECTED_MODULE=LoadLocalComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=LoadLocalComputeShader|nativeBinary=backend/vulkan/LoadLocalComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpFAdd %float"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_comparison_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_COMPARISON_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-comparison.cglb
      -DEXPECTED_MODULE=ComparisonComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ComparisonComputeShader|nativeBinary=backend/vulkan/ComparisonComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=storage-buffer.kind=resource"
      "-DEXPECTED_SPVASM_SNIPPET=OpDecorate %resource_values Binding 0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_boolean_logic_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_BOOLEAN_LOGIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-boolean-logic.cglb
      -DEXPECTED_MODULE=VulkanBooleanLogicComputeShader
      -DEXPECTED_STORAGE_ELEMENT=int
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanBooleanLogicComputeShader|artifacts.backendAssembly=backend/vulkan/VulkanBooleanLogicComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanBooleanLogicComputeShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanBooleanLogicComputeShader|nativeBinary=backend/vulkan/VulkanBooleanLogicComputeShader.spv|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=int*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=int|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|scalar-comparison.kind=operation|scalar-logical.kind=operation|select-expression.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpLogicalAnd %bool"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_boolean_logic_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_BOOLEAN_LOGIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-boolean-logic-spvasm.cglb
      -DEXPECTED_MODULE=VulkanBooleanLogicComputeShader
      "-DEXPECTED_SPVASM_CONTAINS=OpLogicalNot|OpLogicalOr|OpLogicalAnd|OpLogicalEqual|OpLogicalNotEqual|OpSGreaterThan|OpSLessThan|OpIEqual|OpSelect %int"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpTypeImage|OpTypeSampler|NonUniformEXT|vulkan.prototype-unsupported-expression"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_unsigned_arithmetic_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_UNSIGNED_ARITHMETIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-unsigned-arithmetic.cglb
      -DEXPECTED_MODULE=VulkanUnsignedArithmeticComputeShader
      -DEXPECTED_STORAGE_ELEMENT=uint
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanUnsignedArithmeticComputeShader|artifacts.backendAssembly=backend/vulkan/VulkanUnsignedArithmeticComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanUnsignedArithmeticComputeShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanUnsignedArithmeticComputeShader|nativeBinary=backend/vulkan/VulkanUnsignedArithmeticComputeShader.spv|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=uint*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=uint|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|scalar-constructor.kind=operation|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|select-expression.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpUDiv %uint"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_unsigned_arithmetic_spvasm_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_UNSIGNED_ARITHMETIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-unsigned-arithmetic-spvasm.cglb
      -DEXPECTED_MODULE=VulkanUnsignedArithmeticComputeShader
      "-DEXPECTED_SPVASM_CONTAINS=OpIAdd %uint|OpISub %uint|OpIMul %uint|OpUDiv %uint|OpUMod %uint|OpULessThan %bool|OpUGreaterThanEqual %bool|OpSelect %uint"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpSDiv %uint|OpSRem %uint|vulkan.prototype-unsupported-expression"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_float_equality_negation_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FLOAT_EQUALITY_NEGATION_BACKEND_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-float-equality-negation.cglb
      -DEXPECTED_MODULE=FloatEqualityNegationBackendShader
      -DEXPECTED_STORAGE_ELEMENT=int
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=FloatEqualityNegationBackendShader|nativeBinary=backend/vulkan/FloatEqualityNegationBackendShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=int*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=int|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|scalar-constructor.kind=operation|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|select-expression.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpFUnordNotEqual %bool"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_select_expression_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SELECT_EXPRESSION_BACKEND_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-select-expression.cglb
      -DEXPECTED_MODULE=SelectExpressionBackendShader
      -DEXPECTED_STORAGE_ELEMENT=int
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=SelectExpressionBackendShader|nativeBinary=backend/vulkan/SelectExpressionBackendShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=int*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=int|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|select-expression.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpSelect %int"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_if_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_IF_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-if.cglb
      -DEXPECTED_MODULE=IfComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=IfComputeShader|nativeBinary=backend/vulkan/IfComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-selection.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpBranchConditional"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_if_scoped_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_IF_SCOPED_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-if-scoped.cglb
      -DEXPECTED_MODULE=IfScopedComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=IfScopedComputeShader|nativeBinary=backend/vulkan/IfScopedComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|structured-selection.kind=controlFlow|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpSelectionMerge %if_merge_2 None"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_nested_if_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_NESTED_IF_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-nested-if.cglb
      -DEXPECTED_MODULE=NestedIfComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=NestedIfComputeShader|nativeBinary=backend/vulkan/NestedIfComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-selection.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpSelectionMerge %if_merge_"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_if_return_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_IF_RETURN_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-if-return.cglb
      -DEXPECTED_MODULE=IfReturnComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=IfReturnComputeShader|nativeBinary=backend/vulkan/IfReturnComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-selection.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpUnreachable"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_for_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-for.cglb
      -DEXPECTED_MODULE=ForComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ForComputeShader|artifacts.backendAssembly=backend/vulkan/ForComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/ForComputeShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ForComputeShader|nativeBinary=backend/vulkan/ForComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpLoopMerge"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_for_stride_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_STRIDE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-for-stride.cglb
      -DEXPECTED_MODULE=ForStrideComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ForStrideComputeShader|artifacts.backendAssembly=backend/vulkan/ForStrideComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/ForStrideComputeShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ForStrideComputeShader|nativeBinary=backend/vulkan/ForStrideComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=%const_int__2 = OpConstant %int 2"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_nested_for_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_NESTED_FOR_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-nested-for.cglb
      -DEXPECTED_MODULE=NestedForComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=NestedForComputeShader|artifacts.backendAssembly=backend/vulkan/NestedForComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/NestedForComputeShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=NestedForComputeShader|nativeBinary=backend/vulkan/NestedForComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpIMul %int"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_for_dynamic_stride_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_DYNAMIC_STRIDE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-for-dynamic-stride.cglb
      -DEXPECTED_MODULE=ForDynamicStrideComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ForDynamicStrideComputeShader|artifacts.backendAssembly=backend/vulkan/ForDynamicStrideComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/ForDynamicStrideComputeShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ForDynamicStrideComputeShader|nativeBinary=backend/vulkan/ForDynamicStrideComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpIAdd %int"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_for_constant_stride_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_CONSTANT_STRIDE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-for-constant-stride.cglb
      -DEXPECTED_MODULE=ForConstantStrideComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ForConstantStrideComputeShader|artifacts.backendAssembly=backend/vulkan/ForConstantStrideComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/ForConstantStrideComputeShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ForConstantStrideComputeShader|nativeBinary=backend/vulkan/ForConstantStrideComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=%const_int__2 = OpConstant %int 2"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_for_folded_update_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_FOLDED_UPDATE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-for-folded-update.cglb
      -DEXPECTED_MODULE=ForFoldedUpdateComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ForFoldedUpdateComputeShader|artifacts.backendAssembly=backend/vulkan/ForFoldedUpdateComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/ForFoldedUpdateComputeShader.spv"
      "-DEXPECTED_SPVASM_SNIPPET=%const_int__3 = OpConstant %int 3"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ForFoldedUpdateComputeShader|nativeBinary=backend/vulkan/ForFoldedUpdateComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_while_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_WHILE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-while.cglb
      -DEXPECTED_MODULE=WhileComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpLoopMerge"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=WhileComputeShader|nativeBinary=backend/vulkan/WhileComputeShader.spv"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.storageBufferLayout.layout=std430"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow|storage-buffer-write.kind=operation"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_scalar_constructor_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SCALAR_CONSTRUCTOR_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-scalar-constructor.cglb
      -DEXPECTED_MODULE=ScalarConstructorComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=ScalarConstructorComputeShader|nativeBinary=backend/vulkan/ScalarConstructorComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|scalar-constructor.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpConvertFToU %uint"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_matrix_constructor_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_MATRIX_CONSTRUCTOR_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-matrix-constructor.cglb
      -DEXPECTED_MODULE=MatrixConstructorComputeShader
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=MatrixConstructorComputeShader|nativeBinary=backend/vulkan/MatrixConstructorComputeShader.spv|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=std430"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-write.kind=operation|index-access.kind=operation|local-declaration.kind=operation|vector-constructor.kind=operation|matrix-constructor.kind=operation"
      "-DEXPECTED_SPVASM_CONTAINS=%mat2 = OpTypeMatrix %vec2 2|%mat3 = OpTypeMatrix %vec3 3|OpCompositeConstruct %mat2|OpCompositeConstruct %mat3|OpCompositeExtract %float"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_matrix_vector_arithmetic_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_MATRIX_VECTOR_ARITHMETIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-matrix-vector-arithmetic.cglb
      -DEXPECTED_MODULE=MatrixVectorArithmeticComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=MatrixVectorArithmeticComputeShader|nativeBinary=backend/vulkan/MatrixVectorArithmeticComputeShader.spv|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=std430"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|vector-constructor.kind=operation|index-access.kind=operation|matrix-constructor.kind=operation|vector-arithmetic.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_SPVASM_CONTAINS=%mat3 = OpTypeMatrix %vec3 3|%ptr_Function_mat3 = OpTypePointer Function %mat3|OpMatrixTimesVector %vec3|OpVectorTimesMatrix %vec3|OpMatrixTimesMatrix %mat3|OpStore %var_projected"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_matrix_scalar_arithmetic_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_MATRIX_SCALAR_ARITHMETIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-matrix-scalar-arithmetic.cglb
      -DEXPECTED_MODULE=MatrixScalarArithmeticComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=MatrixScalarArithmeticComputeShader|nativeBinary=backend/vulkan/MatrixScalarArithmeticComputeShader.spv|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=std430"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-write.kind=operation|index-access.kind=operation|local-declaration.kind=operation|matrix-constructor.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_SPVASM_CONTAINS=%mat3 = OpTypeMatrix %vec3 3|%ptr_Function_mat3 = OpTypePointer Function %mat3|OpMatrixTimesScalar %mat3|OpStore %var_inferred"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_vector_local_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR_LOCAL_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-vector-local.cglb
      -DEXPECTED_MODULE=VectorLocalComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VectorLocalComputeShader|nativeBinary=backend/vulkan/VectorLocalComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|vector-constructor.kind=operation|vector-arithmetic.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpFAdd %vec4"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_atan_intrinsic_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_ATAN_INTRINSIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-atan-intrinsic.cglb
      -DEXPECTED_MODULE=AtanIntrinsicComputeShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpExtInst %float %glsl_std_450 Atan2"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_intrinsics_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_INTRINSIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-intrinsics.cglb
      -DEXPECTED_MODULE=IntrinsicComputeShader
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=IntrinsicComputeShader|nativeBinary=backend/vulkan/IntrinsicComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=scalars.sourceType=float*|scalars.bindingClass=storageBuffer|scalars.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|scalars.storageBufferLayout.layout=std430|scalars.storageBufferLayout.elementType=float|scalars.storageBufferLayout.arrayStrideBytes=4|vectors.sourceType=vec4*|vectors.bindingClass=storageBuffer|vectors.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|vectors.storageBufferLayout.layout=std430|vectors.storageBufferLayout.elementType=vec4|vectors.storageBufferLayout.arrayStrideBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=scalar-arithmetic.kind=operation|vector-storage-buffer.kind=layout|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpExtInst %vec4 %glsl_std_450 FMix"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_intrinsics_spirv_front_matter_order_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_INTRINSIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-intrinsics-spirv-front-matter-order.cglb
      -DEXPECTED_MODULE=IntrinsicComputeShader
      "-DEXPECTED_SPVASM_ORDERED_CONTAINS=OpCapability Shader|%glsl_std_450 = OpExtInstImport \"GLSL.std.450\"|OpMemoryModel Logical GLSL450|OpEntryPoint GLCompute %compute_main \"main\"|OpExecutionMode %compute_main LocalSize 1 1 1|%void = OpTypeVoid|OpExtInst %vec4 %glsl_std_450 FMix"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_vector_swizzle_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR_SWIZZLE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-vector-swizzle.cglb
      -DEXPECTED_MODULE=VectorSwizzleComputeShader
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VectorSwizzleComputeShader|nativeBinary=backend/vulkan/VectorSwizzleComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageBufferLayout.layout=std430|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|vector-constructor.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpVectorShuffle %vec3"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_vector_scalar_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR_SCALAR_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-vector-scalar.cglb
      -DEXPECTED_MODULE=VectorScalarComputeShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=OpVectorTimesScalar %vec4"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_vector_scalar_cast_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR_SCALAR_CAST_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-vector-scalar-cast.cglb
      -DEXPECTED_MODULE=VectorScalarCastComputeShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_SPVASM_SNIPPET=OpConvertSToF %float"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_vector_buffer_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-vector-buffer.cglb
      -DEXPECTED_MODULE=VectorBufferComputeShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VectorBufferComputeShader|nativeBinary=backend/vulkan/VectorBufferComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=vec4|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vector-storage-buffer.kind=layout|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|vector-constructor.kind=operation|vector-arithmetic.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpFAdd %vec4"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_vector3_buffer_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR3_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-vector3-buffer.cglb
      -DEXPECTED_MODULE=Vector3BufferComputeShader
      -DEXPECTED_STORAGE_ELEMENT=vec3
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=Vector3BufferComputeShader|nativeBinary=backend/vulkan/Vector3BufferComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec3*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=vec3|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vector-storage-buffer.kind=layout|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|vector-constructor.kind=operation|vector-arithmetic.kind=operation"
      "-DEXPECTED_SPVASM_SNIPPET=OpFAdd %vec3"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_struct_buffer_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-struct-buffer.cglb
      -DEXPECTED_MODULE=StructBufferComputeShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=32
      -DEXPECTED_STRUCT_FIELD=mass
      -DEXPECTED_STRUCT_FIELD_OFFSET=12
      -DEXPECTED_SPVASM_STRUCT_FIELD_INDEX=1
      -DEXPECTED_SPVASM_STRUCT_FIELD_OFFSET=12
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_StorageBuffer_float %resource_particles %const_int__0 %const_int__0 %const_int__1"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructBufferComputeShader|artifacts.nativeBinary=backend/vulkan/StructBufferComputeShader.spv|artifacts.backendAssembly=backend/vulkan/StructBufferComputeShader.spvasm"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructBufferComputeShader|nativeBinary=backend/vulkan/StructBufferComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storageBuffer|particles.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|particles.storageClass=StorageBuffer|particles.spirvType=OpTypeRuntimeArray<Particle>|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.fields.0.type=vec3|particles.storageBufferLayout.fields.1.offsetBytes=12|particles.storageBufferLayout.fields.2.type=vec4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_struct_vector_buffer_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_VECTOR_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-struct-vector-buffer.cglb
      -DEXPECTED_MODULE=StructVectorBufferComputeShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=32
      -DEXPECTED_STRUCT_FIELD=position
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_SPVASM_STRUCT_FIELD_INDEX=0
      -DEXPECTED_SPVASM_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_SPVASM_ACCESS_POINTER=ptr_StorageBuffer_vec3
      "-DEXPECTED_SPVASM_SNIPPET=OpAccessChain %ptr_StorageBuffer_vec3 %resource_particles %const_int__0 %const_int__0 %const_int__0"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructVectorBufferComputeShader|artifacts.nativeBinary=backend/vulkan/StructVectorBufferComputeShader.spv|artifacts.backendAssembly=backend/vulkan/StructVectorBufferComputeShader.spvasm"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructVectorBufferComputeShader|nativeBinary=backend/vulkan/StructVectorBufferComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storageBuffer|particles.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|particles.storageClass=StorageBuffer|particles.spirvType=OpTypeRuntimeArray<Particle>|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.fields.0.type=vec3|particles.storageBufferLayout.fields.1.offsetBytes=12|particles.storageBufferLayout.fields.2.type=vec4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|vector-arithmetic.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_struct_nested_field_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_NESTED_FIELD_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-struct-nested-field.cglb
      -DEXPECTED_MODULE=StructNestedFieldComputeShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=32
      -DEXPECTED_STRUCT_FIELD=transform
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_SPVASM_STRUCT_FIELD_INDEX=0
      -DEXPECTED_SPVASM_STRUCT_FIELD_OFFSET=0
      "-DEXPECTED_SPVASM_SNIPPET=OpMemberDecorate %struct_Transform 0 Offset 0"
      -DEXPECTED_SPVASM_ACCESS_POINTER=ptr_StorageBuffer_vec3
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructNestedFieldComputeShader|artifacts.nativeBinary=backend/vulkan/StructNestedFieldComputeShader.spv|artifacts.backendAssembly=backend/vulkan/StructNestedFieldComputeShader.spvasm"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructNestedFieldComputeShader|nativeBinary=backend/vulkan/StructNestedFieldComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storageBuffer|particles.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|particles.storageClass=StorageBuffer|particles.spirvType=OpTypeRuntimeArray<Particle>|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.fields.0.type=Transform|particles.storageBufferLayout.fields.0.storageSizeBytes=16|particles.storageBufferLayout.fields.1.offsetBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|vector-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_struct_array_field_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_ARRAY_FIELD_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-struct-array-field.cglb
      -DEXPECTED_MODULE=StructArrayFieldComputeShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=20
      -DEXPECTED_STRUCT_FIELD=weights
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=4
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=4
      -DEXPECTED_SPVASM_STRUCT_FIELD_INDEX=0
      -DEXPECTED_SPVASM_STRUCT_FIELD_OFFSET=0
      "-DEXPECTED_SPVASM_SNIPPET=OpDecorate %arr_float_4_ ArrayStride 4"
      -DEXPECTED_SPVASM_ACCESS_POINTER=ptr_StorageBuffer_float
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructArrayFieldComputeShader|artifacts.nativeBinary=backend/vulkan/StructArrayFieldComputeShader.spv|artifacts.backendAssembly=backend/vulkan/StructArrayFieldComputeShader.spvasm"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructArrayFieldComputeShader|nativeBinary=backend/vulkan/StructArrayFieldComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storageBuffer|particles.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.fields.0.type=float[4]|particles.storageBufferLayout.fields.0.arrayElementCount=4|particles.storageBufferLayout.fields.0.arrayDimensions.0.kind=fixed|particles.storageBufferLayout.fields.1.offsetBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=fixed-array.kind=layout|fixed-array-field.kind=layout|scalar-vector-elements.kind=array|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_struct_constant_array_field_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_CONSTANT_ARRAY_FIELD_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-struct-constant-array-field.cglb
      -DEXPECTED_MODULE=StructConstantArrayFieldComputeShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=20
      -DEXPECTED_STRUCT_FIELD=weights
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=4
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=4
      -DEXPECTED_SPVASM_STRUCT_FIELD_INDEX=0
      -DEXPECTED_SPVASM_STRUCT_FIELD_OFFSET=0
      "-DEXPECTED_SPVASM_SNIPPET=OpDecorate %arr_float_WEIGHT_COUNT_ ArrayStride 4"
      -DEXPECTED_SPVASM_ACCESS_POINTER=ptr_StorageBuffer_float
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructConstantArrayFieldComputeShader|artifacts.nativeBinary=backend/vulkan/StructConstantArrayFieldComputeShader.spv|artifacts.backendAssembly=backend/vulkan/StructConstantArrayFieldComputeShader.spvasm"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructConstantArrayFieldComputeShader|nativeBinary=backend/vulkan/StructConstantArrayFieldComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storageBuffer|particles.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.fields.0.type=float[WEIGHT_COUNT]|particles.storageBufferLayout.fields.0.arrayElementCount=4|particles.storageBufferLayout.fields.0.arrayDimensions.0.source=WEIGHT_COUNT|particles.storageBufferLayout.fields.1.offsetBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=fixed-array.kind=layout|fixed-array-field.kind=layout|scalar-vector-elements.kind=array|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_struct_vector_array_field_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_VECTOR_ARRAY_FIELD_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-struct-vector-array-field.cglb
      -DEXPECTED_MODULE=StructVectorArrayFieldComputeShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=48
      -DEXPECTED_STRUCT_FIELD=positions
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=2
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=16
      -DEXPECTED_SPVASM_STRUCT_FIELD_INDEX=0
      -DEXPECTED_SPVASM_STRUCT_FIELD_OFFSET=0
      "-DEXPECTED_SPVASM_SNIPPET=OpDecorate %arr_vec3_2_ ArrayStride 16"
      -DEXPECTED_SPVASM_ACCESS_POINTER=ptr_StorageBuffer_vec3
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructVectorArrayFieldComputeShader|artifacts.nativeBinary=backend/vulkan/StructVectorArrayFieldComputeShader.spv|artifacts.backendAssembly=backend/vulkan/StructVectorArrayFieldComputeShader.spvasm"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructVectorArrayFieldComputeShader|nativeBinary=backend/vulkan/StructVectorArrayFieldComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storageBuffer|particles.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.fields.0.type=vec3[2]|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.0.arrayStrideBytes=16|particles.storageBufferLayout.fields.1.offsetBytes=32"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=fixed-array.kind=layout|fixed-array-field.kind=layout|scalar-vector-elements.kind=array|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_struct_nested_array_field_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_NESTED_ARRAY_FIELD_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-struct-nested-array-field.cglb
      -DEXPECTED_MODULE=StructNestedArrayFieldComputeShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=48
      -DEXPECTED_STRUCT_FIELD=history
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=2
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=16
      -DEXPECTED_SPVASM_STRUCT_FIELD_INDEX=0
      -DEXPECTED_SPVASM_STRUCT_FIELD_OFFSET=0
      "-DEXPECTED_SPVASM_SNIPPET=OpDecorate %arr_Transform_2_ ArrayStride 16"
      -DEXPECTED_SPVASM_ACCESS_POINTER=ptr_StorageBuffer_vec3
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructNestedArrayFieldComputeShader|artifacts.nativeBinary=backend/vulkan/StructNestedArrayFieldComputeShader.spv|artifacts.backendAssembly=backend/vulkan/StructNestedArrayFieldComputeShader.spvasm"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StructNestedArrayFieldComputeShader|nativeBinary=backend/vulkan/StructNestedArrayFieldComputeShader.spv|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storageBuffer|particles.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.fields.0.type=Transform[2]|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.0.arrayStrideBytes=16|particles.storageBufferLayout.fields.1.offsetBytes=32"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=fixed-array.kind=layout|fixed-array-field.kind=layout|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_helper_call_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_HELPER_CALL_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-helper-call.cglb
      -DEXPECTED_MODULE=VulkanHelperCallShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_SPVASM_SNIPPET=OpFunctionCall %float %func_scaleAndBias"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_function_parameter_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_FUNCTION_PARAMETER_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-function-parameter-array-native.cglb
      -DEXPECTED_MODULE=VulkanFunctionParameterArrayShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=8
      -DEXPECTED_STRUCT_FIELD=weights
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=2
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanFunctionParameterArrayShader|artifacts.backendAssembly=backend/vulkan/VulkanFunctionParameterArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanFunctionParameterArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanFunctionParameterArrayShader|nativeBinary=backend/vulkan/VulkanFunctionParameterArrayShader.spv|workgroupSizes.0.entryPoint=compute_main|functionConstants.0.name=COUNT|functionConstants.0.value=2|structs.0.fields.0.name=weights|structs.0.fields.0.arrayDimensions.0.elementCount=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=1|structs=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storageBuffer|particles.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|particles.storageClass=StorageBuffer|particles.set=0|particles.binding=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.arrayStrideBytes=8|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.0.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=fixed-array.kind=layout|fixed-array-field.kind=layout|compute-kernel.kind=stage|storage-buffer.kind=resource|local-declaration.kind=operation|index-access.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpCompositeExtract %float %param_readWeight_weights 1"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_function_parameter_array_write_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_FUNCTION_PARAMETER_ARRAY_WRITE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-function-parameter-array-write-native.cglb
      -DEXPECTED_MODULE=VulkanFunctionParameterArrayWriteShader
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=8
      -DEXPECTED_STRUCT_FIELD=weights
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=2
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanFunctionParameterArrayWriteShader|artifacts.backendAssembly=backend/vulkan/VulkanFunctionParameterArrayWriteShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanFunctionParameterArrayWriteShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanFunctionParameterArrayWriteShader|nativeBinary=backend/vulkan/VulkanFunctionParameterArrayWriteShader.spv|workgroupSizes.0.entryPoint=compute_main|functionConstants.0.name=COUNT|functionConstants.0.value=2|structs.0.fields.0.name=weights|structs.0.fields.0.arrayDimensions.0.elementCount=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=1|structs=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.bindingClass=storageBuffer|particles.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|particles.storageClass=StorageBuffer|particles.set=0|particles.binding=0|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.layout=std430|particles.storageBufferLayout.arrayStrideBytes=8|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.0.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=fixed-array.kind=layout|fixed-array-field.kind=layout|compute-kernel.kind=stage|storage-buffer.kind=resource|local-declaration.kind=operation|index-access.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_CONTAINS=%ptr_Function_float_COUNT_ = OpTypePointer Function %fnarr_float_COUNT_|%param_rewriteWeight_weights = OpFunctionParameter %ptr_Function_float_COUNT_|%var_param_array_writeback_rewriteWeight_weights = OpVariable %ptr_Function_float_COUNT_ Function|OpFunctionCall %float %func_rewriteWeight %var_param_array_writeback_rewriteWeight_weights|OpAccessChain %ptr_Function_float %var_param_array_writeback_rewriteWeight_weights|OpAccessChain %ptr_Function_float %param_rewriteWeight_weights"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_local_function_parameter_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-local-function-parameter-array-native.cglb
      -DEXPECTED_MODULE=VulkanLocalFunctionParameterArrayShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanLocalFunctionParameterArrayShader|artifacts.backendAssembly=backend/vulkan/VulkanLocalFunctionParameterArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanLocalFunctionParameterArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanLocalFunctionParameterArrayShader|nativeBinary=backend/vulkan/VulkanLocalFunctionParameterArrayShader.spv|workgroupSizes.0.entryPoint=compute_main|functionConstants.0.name=COUNT|functionConstants.0.value=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=compute-kernel.kind=stage|storage-buffer.kind=resource|local-declaration.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpFunctionCall %float %func_forwardWeight"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_writable_local_function_parameter_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_WRITABLE_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-writable-local-function-parameter-array-native.cglb
      -DEXPECTED_MODULE=VulkanWritableLocalFunctionParameterArrayShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanWritableLocalFunctionParameterArrayShader|artifacts.backendAssembly=backend/vulkan/VulkanWritableLocalFunctionParameterArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanWritableLocalFunctionParameterArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanWritableLocalFunctionParameterArrayShader|nativeBinary=backend/vulkan/VulkanWritableLocalFunctionParameterArrayShader.spv|workgroupSizes.0.entryPoint=compute_main|functionConstants.0.name=COUNT|functionConstants.0.value=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=compute-kernel.kind=stage|storage-buffer.kind=resource|scalar-arithmetic.kind=operation|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpCompositeInsert %arr_float_COUNT_"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_vector_writable_local_function_parameter_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_VECTOR_WRITABLE_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-vector-writable-local-function-parameter-array-native.cglb
      -DEXPECTED_MODULE=VulkanVectorWritableLocalFunctionParameterArrayShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanVectorWritableLocalFunctionParameterArrayShader|artifacts.backendAssembly=backend/vulkan/VulkanVectorWritableLocalFunctionParameterArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanVectorWritableLocalFunctionParameterArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanVectorWritableLocalFunctionParameterArrayShader|nativeBinary=backend/vulkan/VulkanVectorWritableLocalFunctionParameterArrayShader.spv|workgroupSizes.0.entryPoint=compute_main|functionConstants.0.name=COUNT|functionConstants.0.value=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=outputs.sourceType=vec4*|outputs.bindingClass=storageBuffer|outputs.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|outputs.storageClass=StorageBuffer|outputs.set=0|outputs.binding=0|outputs.storageBufferLayout.elementType=vec4|outputs.storageBufferLayout.layout=std430|outputs.storageBufferLayout.arrayStrideBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=compute-kernel.kind=stage|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|vector-arithmetic.kind=operation|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|vector-constructor.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpCompositeInsert %arr_vec4_COUNT_"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_folded_writable_local_function_parameter_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_FOLDED_WRITABLE_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-folded-writable-local-function-parameter-array-native.cglb
      -DEXPECTED_MODULE=VulkanFoldedWritableLocalFunctionParameterArrayShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanFoldedWritableLocalFunctionParameterArrayShader|artifacts.backendAssembly=backend/vulkan/VulkanFoldedWritableLocalFunctionParameterArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanFoldedWritableLocalFunctionParameterArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanFoldedWritableLocalFunctionParameterArrayShader|nativeBinary=backend/vulkan/VulkanFoldedWritableLocalFunctionParameterArrayShader.spv|workgroupSizes.0.entryPoint=compute_main|functionConstants.1.name=COUNT|functionConstants.1.value=2|functionConstants.4.name=OUTPUT_INDEX|functionConstants.4.value=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=5"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=compute-kernel.kind=stage|storage-buffer.kind=resource|scalar-arithmetic.kind=operation|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpCompositeInsert %arr_float_COUNT_"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_folded_nested_local_function_parameter_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_FOLDED_NESTED_LOCAL_FUNCTION_PARAMETER_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-folded-nested-local-function-parameter-array-native.cglb
      -DEXPECTED_MODULE=VulkanFoldedNestedLocalFunctionParameterArrayShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanFoldedNestedLocalFunctionParameterArrayShader|artifacts.backendAssembly=backend/vulkan/VulkanFoldedNestedLocalFunctionParameterArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanFoldedNestedLocalFunctionParameterArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanFoldedNestedLocalFunctionParameterArrayShader|nativeBinary=backend/vulkan/VulkanFoldedNestedLocalFunctionParameterArrayShader.spv|workgroupSizes.0.entryPoint=compute_main|functionConstants.1.name=COLS|functionConstants.1.value=3|functionConstants.2.name=ROWS|functionConstants.2.value=2|functionConstants.7.name=OUTPUT_INDEX|functionConstants.7.value=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=8"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=compute-kernel.kind=stage|storage-buffer.kind=resource|scalar-arithmetic.kind=operation|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpCompositeExtract %float %param_readCorner_grid 1 2"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_dynamic_nested_local_function_parameter_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_DYNAMIC_NESTED_LOCAL_FUNCTION_PARAMETER_ARRAY_UNSUPPORTED_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-dynamic-nested-local-function-parameter-array.cglb
      -DEXPECTED_MODULE=VulkanDynamicNestedLocalFunctionParameterArrayUnsupportedShader
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanDynamicNestedLocalFunctionParameterArrayUnsupportedShader|artifacts.backendAssembly=backend/vulkan/VulkanDynamicNestedLocalFunctionParameterArrayUnsupportedShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanDynamicNestedLocalFunctionParameterArrayUnsupportedShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanDynamicNestedLocalFunctionParameterArrayUnsupportedShader|nativeBinary=backend/vulkan/VulkanDynamicNestedLocalFunctionParameterArrayUnsupportedShader.spv|workgroupSizes.0.entryPoint=compute_main|functionConstants.0.name=ROWS|functionConstants.0.value=2|functionConstants.1.name=COLS|functionConstants.1.value=3|functionConstants.2.name=LAST_COL|functionConstants.2.value=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=3"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|values.set=0|values.binding=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=std430|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=compute-kernel.kind=stage|storage-buffer.kind=resource|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|scalar-constructor.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpIEqual %bool %param_readDynamicRow_row %const_int__1"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_function_parameter_resource_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_FUNCTION_PARAMETER_RESOURCE_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-function-parameter-resource-array-native.cglb
      -DEXPECTED_MODULE=VulkanFunctionParameterResourceArrayShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanFunctionParameterResourceArrayShader|artifacts.backendAssembly=backend/vulkan/VulkanFunctionParameterResourceArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanFunctionParameterResourceArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanFunctionParameterResourceArrayShader|nativeBinary=backend/vulkan/VulkanFunctionParameterResourceArrayShader.spv|resources.0.name=values|resources.1.name=colorMaps|resources.1.kind=texture|resources.1.type=sampler2D[COUNT]|resources.2.name=linearSamplers|resources.2.kind=sampler|resources.2.type=sampler[COUNT]|workgroupSizes.0.entryPoint=compute_main|functionConstants.0.name=COUNT|functionConstants.0.value=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|functionConstants=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.bindingClass=storageBuffer|values.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|values.storageClass=StorageBuffer|colorMaps.sourceType=sampler2D[COUNT]|colorMaps.bindingClass=sampledImage|colorMaps.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|colorMaps.storageClass=UniformConstant|colorMaps.arrayElementCount=2|linearSamplers.sourceType=sampler[COUNT]|linearSamplers.bindingClass=sampler|linearSamplers.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|linearSamplers.storageClass=UniformConstant|linearSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|descriptor-array.kind=resource|sampled-texture.kind=resource|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=%func_sampleFirst = OpFunction %vec4 None %fn_vec4__"
      "-DEXPECTED_SPVASM_CONTAINS=OpAccessChain %ptr_UniformConstant_sampledImage_sampler2D %resource_colorMaps %const_int__0|OpAccessChain %ptr_UniformConstant_sampler_sampler %resource_linearSamplers %const_int__0|OpFunctionCall %vec4 %func_sampleFirst"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_storage_image_read_write_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_STORAGE_IMAGE_READ_WRITE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage-image-read-write-native.cglb
      -DEXPECTED_MODULE=VulkanStorageImageReadWriteShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanStorageImageReadWriteShader|artifacts.backendAssembly=backend/vulkan/VulkanStorageImageReadWriteShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanStorageImageReadWriteShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanStorageImageReadWriteShader|nativeBinary=backend/vulkan/VulkanStorageImageReadWriteShader.spv|resources.0.kind=storage_image|resources.0.type=image2D|resources.5.type=uimage2DArray|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImage.sourceType=image2D|colorImage.bindingClass=storageImage|colorImage.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE|colorImage.storageClass=UniformConstant|colorImage.spirvType=OpTypeImage<float, 2D, sampled=2, format=Rgba32f>|colorAtlas.sourceType=image2DArray|colorAtlas.spirvType=OpTypeImage<float, 2DArray, sampled=2, format=Rgba32f>|maskAtlas.sourceType=uimage2DArray|maskAtlas.spirvType=OpTypeImage<uint, 2DArray, sampled=2, format=Rgba32ui>"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|storage-image.kind=resource|read-write.kind=storageImage|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpImageRead %vec4"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_storage_image_access_qualifier_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_STORAGE_IMAGE_ACCESS_QUALIFIER_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage-image-access-qualifier-native.cglb
      -DEXPECTED_MODULE=VulkanStorageImageAccessQualifierShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=int
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanStorageImageAccessQualifierShader|artifacts.backendAssembly=backend/vulkan/VulkanStorageImageAccessQualifierShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanStorageImageAccessQualifierShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanStorageImageAccessQualifierShader|nativeBinary=backend/vulkan/VulkanStorageImageAccessQualifierShader.spv|resources.0.kind=storage_image|resources.0.type=image2D|resources.5.type=image2D[IMAGE_COUNT]|resources.6.kind=buffer|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=8|targetResourceBindings=8|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=readOnlyImage.sourceType=image2D|readOnlyImage.bindingClass=storageImage|readOnlyImage.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE|readOnlyImage.storageClass=UniformConstant|readOnlyImage.spirvType=OpTypeImage<float, 2D, sampled=2, format=Rgba32f>|readOnlyImage.storageImageAccess=read|writeOnlyImage.storageImageAccess=write|readWriteImage.storageImageAccess=read_write|readOnlyImages.sourceType=image2D[IMAGE_COUNT]|readOnlyImages.storageImageAccess=read|readOnlyImages.arrayElementCount=2|writeOnlyImages.storageImageAccess=write|writeOnlyImages.arrayElementCount=2|readWriteImages.storageImageAccess=read_write|readWriteImages.arrayElementCount=2|slots.sourceType=int*|slots.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|colors.sourceType=vec4*|colors.storageBufferLayout.arrayStrideBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|storage-image.kind=resource|read-only.kind=storageImage|write-only.kind=storageImage|read-write.kind=storageImage|descriptor-array.kind=resource|fixed-array.kind=layout|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|StorageImageArrayNonUniformIndexingEXT.kind=capability|storage-image-read.kind=operation|storage-image-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpDecorate %resource_writeOnlyImage NonReadable"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_storage_image_access_qualifier_descriptor_array_spvasm_snippets
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_STORAGE_IMAGE_ACCESS_QUALIFIER_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage-image-access-qualifier-descriptor-array-spvasm.cglb
      -DEXPECTED_MODULE=VulkanStorageImageAccessQualifierShader
      "-DEXPECTED_SPVASM_CONTAINS=OpCapability StorageImageArrayNonUniformIndexingEXT|OpExtension \"SPV_EXT_descriptor_indexing\"|OpDecorate %resource_readOnlyImages NonWritable|OpDecorate %resource_writeOnlyImages NonReadable|%arr_storageImage_image2D_IMAGE_COUNT_ = OpTypeArray %storage_image_image2D %const_uint_2|%resource_readOnlyImages = OpVariable %ptr_UniformConstant_storageImage_image2D_IMAGE_COUNT_ UniformConstant|%resource_writeOnlyImages = OpVariable %ptr_UniformConstant_storageImage_image2D_IMAGE_COUNT_ UniformConstant|%resource_readWriteImages = OpVariable %ptr_UniformConstant_storageImage_image2D_IMAGE_COUNT_ UniformConstant|OpAccessChain %ptr_UniformConstant_storageImage_image2D %resource_readOnlyImages %tmp_|OpAccessChain %ptr_UniformConstant_storageImage_image2D %resource_writeOnlyImages %tmp_|OpAccessChain %ptr_UniformConstant_storageImage_image2D %resource_readWriteImages %tmp_"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpDecorate %resource_readOnlyImages NonReadable|OpDecorate %resource_writeOnlyImages NonWritable|OpDecorate %resource_readWriteImages NonReadable|OpDecorate %resource_readWriteImages NonWritable|OpCapability SampledImageArrayNonUniformIndexingEXT|OpCapability StorageBufferArrayNonUniformIndexingEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_storage_image_atomic_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_STORAGE_IMAGE_ATOMIC_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage-image-atomic-native.cglb
      -DEXPECTED_MODULE=VulkanStorageImageAtomicShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=int
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanStorageImageAtomicShader|artifacts.backendAssembly=backend/vulkan/VulkanStorageImageAtomicShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanStorageImageAtomicShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanStorageImageAtomicShader|nativeBinary=backend/vulkan/VulkanStorageImageAtomicShader.spv|resources.0.kind=storage_image|resources.0.type=iimage2D|resources.0.storageImageFormat=r32i|resources.1.type=uimage2D|resources.1.storageImageFormat=r32ui|resources.2.type=iimage2DArray|resources.2.storageImageFormat=r32i|resources.3.type=uimage2DArray|resources.3.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=signedCounters.sourceType=iimage2D|signedCounters.bindingClass=storageImage|signedCounters.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE|signedCounters.spirvType=OpTypeImage<int, 2D, sampled=2, format=R32i>|unsignedCounters.spirvType=OpTypeImage<uint, 2D, sampled=2, format=R32ui>|signedAtlas.spirvType=OpTypeImage<int, 2DArray, sampled=2, format=R32i>|unsignedAtlas.spirvType=OpTypeImage<uint, 2DArray, sampled=2, format=R32ui>|signedResults.sourceType=int*|signedResults.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|storage-image.kind=resource|read-write.kind=storageImage|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|storage-buffer.kind=resource|storage-image-read.kind=operation|storage-image-write.kind=operation|storage-image-atomic-add.kind=operation|storage-image-atomic-exchange.kind=operation|storage-image-atomic-min.kind=operation|storage-image-atomic-max.kind=operation|storage-image-atomic-and.kind=operation|storage-image-atomic-or.kind=operation|storage-image-atomic-xor.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpAtomicIAdd %int"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_storage_image_atomic_spvasm_snippets
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_STORAGE_IMAGE_ATOMIC_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage-image-atomic-spvasm.cglb
      -DEXPECTED_MODULE=VulkanStorageImageAtomicShader
      "-DEXPECTED_SPVASM_CONTAINS=OpTypePointer Image %int|OpTypePointer Image %uint|OpImageTexelPointer %ptr_Image_int|OpImageTexelPointer %ptr_Image_uint|OpAtomicIAdd %int|OpAtomicIAdd %uint|OpAtomicSMin %int|OpAtomicUMin %uint|OpAtomicSMax %int|OpAtomicUMax %uint|OpAtomicAnd %int|OpAtomicAnd %uint|OpAtomicOr %int|OpAtomicOr %uint|OpAtomicExchange %int|OpAtomicExchange %uint|OpAtomicXor %int|OpAtomicXor %uint"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  add_test(NAME cglc_build_vulkan_storage_image_atomic_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage-image-atomic-descriptor-array-native.cglb
      -DEXPECTED_MODULE=StorageImageAtomicDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=int
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageImageAtomicDescriptorArrayShader|artifacts.backendAssembly=backend/vulkan/StorageImageAtomicDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/StorageImageAtomicDescriptorArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageImageAtomicDescriptorArrayShader|nativeBinary=backend/vulkan/StorageImageAtomicDescriptorArrayShader.spv|resources.0.kind=buffer|resources.1.kind=storage_image|resources.1.type=iimage2D[IMAGE_COUNT]|resources.1.storageImageFormat=r32i|resources.2.type=uimage2D[IMAGE_COUNT]|resources.2.storageImageFormat=r32ui|resources.3.type=iimage2DArray[IMAGE_COUNT]|resources.4.type=uimage2DArray[IMAGE_COUNT]|resources.4.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=2|functionConstants.0.name=IMAGE_COUNT|functionConstants.0.value=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=signedCounters.sourceType=iimage2D[IMAGE_COUNT]|signedCounters.bindingClass=storageImage|signedCounters.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE|signedCounters.spirvType=OpTypeArray<OpTypeImage<int, 2D, sampled=2, format=R32i>, IMAGE_COUNT>|signedCounters.arrayElementCount=2|unsignedCounters.spirvType=OpTypeArray<OpTypeImage<uint, 2D, sampled=2, format=R32ui>, IMAGE_COUNT>|signedAtlases.spirvType=OpTypeArray<OpTypeImage<int, 2DArray, sampled=2, format=R32i>, IMAGE_COUNT>|unsignedAtlases.spirvType=OpTypeArray<OpTypeImage<uint, 2DArray, sampled=2, format=R32ui>, IMAGE_COUNT>|unsignedAtlases.arrayElementCount=2|slots.sourceType=int*"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|storage-image.kind=resource|read-write.kind=storageImage|descriptor-array.kind=resource|fixed-array.kind=layout|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|StorageImageArrayNonUniformIndexingEXT.kind=capability|storage-image-read.kind=operation|storage-image-write.kind=operation|storage-image-atomic-add.kind=operation|storage-image-atomic-exchange.kind=operation|storage-image-atomic-min.kind=operation|storage-image-atomic-max.kind=operation|storage-image-atomic-and.kind=operation|storage-image-atomic-or.kind=operation|storage-image-atomic-xor.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpCapability StorageImageArrayNonUniformIndexingEXT"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_storage_image_atomic_descriptor_array_spvasm_snippets
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage-image-atomic-descriptor-array-spvasm.cglb
      -DEXPECTED_MODULE=StorageImageAtomicDescriptorArrayShader
      "-DEXPECTED_SPVASM_CONTAINS=OpExtension \"SPV_EXT_descriptor_indexing\"|OpDecorate %tmp_7 NonUniformEXT|OpAccessChain %ptr_UniformConstant_storageImage_iimage2D__storage_image_iimage2D_R32i|OpImageTexelPointer %ptr_Image_int|OpImageTexelPointer %ptr_Image_uint|OpAtomicIAdd %int|OpAtomicIAdd %uint|OpAtomicSMin %int|OpAtomicUMax %uint|OpAtomicAnd %int|OpAtomicOr %uint|OpAtomicExchange %int|OpAtomicExchange %uint|OpAtomicXor %int|OpAtomicXor %uint"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  set(CROSSGL_VULKAN_STORAGE_IMAGE_EXPLICIT_FORMAT_SPVASM_SNIPPET [=[%storage_image_image2D_R32f = OpTypeImage %float 2D 0 0 0 2 R32f
%ptr_UniformConstant_storageImage_image2D__storage_image_image2D_R32f = OpTypePointer UniformConstant %storage_image_image2D_R32f
%int = OpTypeInt 32 1
%storage_image_iimage2D_R32i = OpTypeImage %int 2D 0 0 0 2 R32i
%ptr_UniformConstant_storageImage_iimage2D__storage_image_iimage2D_R32i = OpTypePointer UniformConstant %storage_image_iimage2D_R32i
%uint = OpTypeInt 32 0
%storage_image_uimage2D_R32ui = OpTypeImage %uint 2D 0 0 0 2 R32ui
%ptr_UniformConstant_storageImage_uimage2D__storage_image_uimage2D_R32ui = OpTypePointer UniformConstant %storage_image_uimage2D_R32ui]=])
  add_test(NAME cglc_build_vulkan_storage_image_explicit_format_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage-image-explicit-format-native.cglb
      -DEXPECTED_MODULE=StorageImageExplicitFormatShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE
      -DEXPECTED_STORAGE_BUFFER_METADATA=OFF
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageImageExplicitFormatShader|artifacts.backendAssembly=backend/vulkan/StorageImageExplicitFormatShader.spvasm|artifacts.nativeBinary=backend/vulkan/StorageImageExplicitFormatShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageImageExplicitFormatShader|nativeBinary=backend/vulkan/StorageImageExplicitFormatShader.spv|resources.0.kind=storage_image|resources.0.storageImageFormat=r32f|resources.1.storageImageFormat=r32i|resources.2.storageImageFormat=r32ui|resources.3.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=readColor.sourceType=image2D|readColor.bindingClass=storageImage|readColor.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE|readColor.spirvType=OpTypeImage<float, 2D, sampled=2, format=R32f>|readColor.storageImageFormat=r32f|readLabel.sourceType=iimage2D|readLabel.spirvType=OpTypeImage<int, 2D, sampled=2, format=R32i>|readLabel.storageImageFormat=r32i|readMask.sourceType=uimage2D|readMask.spirvType=OpTypeImage<uint, 2D, sampled=2, format=R32ui>|readMask.storageImageFormat=r32ui|writeMask.sourceType=uimage2D|writeMask.spirvType=OpTypeImage<uint, 2D, sampled=2, format=R32ui>|writeMask.storageImageFormat=r32ui|colors.sourceType=vec4*|colors.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|colors.binding=4|labels.sourceType=ivec4*|labels.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|labels.binding=5"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|storage-image.kind=resource|read-only.kind=storageImage|write-only.kind=storageImage|2d-dimension.kind=storageImage|r32f-format.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=${CROSSGL_VULKAN_STORAGE_IMAGE_EXPLICIT_FORMAT_SPVASM_SNIPPET}"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_VULKAN_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SPVASM_SNIPPET [=[%storage_image_image2D_R32f = OpTypeImage %float 2D 0 0 0 2 R32f
%uint = OpTypeInt 32 0
%const_uint_2 = OpConstant %uint 2
%arr_storageImage_image2D_IMAGE_COUNT___storage_image_image2D_R32f = OpTypeArray %storage_image_image2D_R32f %const_uint_2
%ptr_UniformConstant_storageImage_image2D_IMAGE_COUNT___arr_storageImage_image2D_IMAGE_COUNT___storage_image_image2D_R32f = OpTypePointer UniformConstant %arr_storageImage_image2D_IMAGE_COUNT___storage_image_image2D_R32f
%int = OpTypeInt 32 1
%storage_image_iimage2D_R32i = OpTypeImage %int 2D 0 0 0 2 R32i
%arr_storageImage_iimage2D_IMAGE_COUNT___storage_image_iimage2D_R32i = OpTypeArray %storage_image_iimage2D_R32i %const_uint_2
%ptr_UniformConstant_storageImage_iimage2D_IMAGE_COUNT___arr_storageImage_iimage2D_IMAGE_COUNT___storage_image_iimage2D_R32i = OpTypePointer UniformConstant %arr_storageImage_iimage2D_IMAGE_COUNT___storage_image_iimage2D_R32i
%storage_image_uimage2DArray_R32ui = OpTypeImage %uint 2D 0 1 0 2 R32ui
%arr_storageImage_uimage2DArray_ATLAS_COUNT___storage_image_uimage2DArray_R32ui = OpTypeArray %storage_image_uimage2DArray_R32ui %const_uint_2
%ptr_UniformConstant_storageImage_uimage2DArray_ATLAS_COUNT___arr_storageImage_uimage2DArray_ATLAS_COUNT___storage_image_uimage2DArray_R32ui = OpTypePointer UniformConstant %arr_storageImage_uimage2DArray_ATLAS_COUNT___storage_image_uimage2DArray_R32ui]=])
  add_test(NAME cglc_build_vulkan_storage_image_explicit_format_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage-image-explicit-format-descriptor-array-native.cglb
      -DEXPECTED_MODULE=StorageImageExplicitFormatDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=int
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageImageExplicitFormatDescriptorArrayShader|artifacts.backendAssembly=backend/vulkan/StorageImageExplicitFormatDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/StorageImageExplicitFormatDescriptorArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=StorageImageExplicitFormatDescriptorArrayShader|nativeBinary=backend/vulkan/StorageImageExplicitFormatDescriptorArrayShader.spv|resources.0.kind=storage_image|resources.0.type=image2D[IMAGE_COUNT]|resources.0.storageImageFormat=r32f|resources.1.storageImageFormat=r32i|resources.2.storageImageFormat=r32ui|resources.3.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=8|targetResourceBindings=8|functionConstants=2|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImages.sourceType=image2D[IMAGE_COUNT]|colorImages.bindingClass=storageImage|colorImages.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE|colorImages.spirvType=OpTypeArray<OpTypeImage<float, 2D, sampled=2, format=R32f>, IMAGE_COUNT>|colorImages.arraySize=IMAGE_COUNT|colorImages.arrayElementCount=2|colorImages.storageImageFormat=r32f|labelImages.spirvType=OpTypeArray<OpTypeImage<int, 2D, sampled=2, format=R32i>, IMAGE_COUNT>|labelImages.storageImageFormat=r32i|maskAtlases.spirvType=OpTypeArray<OpTypeImage<uint, 2DArray, sampled=2, format=R32ui>, ATLAS_COUNT>|maskAtlases.storageImageFormat=r32ui|outputAtlases.spirvType=OpTypeArray<OpTypeImage<uint, 2DArray, sampled=2, format=R32ui>, ATLAS_COUNT>|outputAtlases.storageImageFormat=r32ui|slots.sourceType=int*|slots.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|storage-image.kind=resource|read-only.kind=storageImage|write-only.kind=storageImage|descriptor-array.kind=resource|fixed-array.kind=layout|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|r32f-format.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|StorageImageArrayNonUniformIndexingEXT.kind=capability|storage-image-read.kind=operation|storage-image-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=${CROSSGL_VULKAN_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SPVASM_SNIPPET}"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_storage_image_nonuniform_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage-image-nonuniform-descriptor-array-native.cglb
      -DEXPECTED_MODULE=VulkanStorageImageNonUniformDescriptorArrayShader
      -DEXPECTED_DESCRIPTOR_TYPE=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE
      -DEXPECTED_STORAGE_ELEMENT=int
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanStorageImageNonUniformDescriptorArrayShader|artifacts.backendAssembly=backend/vulkan/VulkanStorageImageNonUniformDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanStorageImageNonUniformDescriptorArrayShader.spv"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=vulkan|module=VulkanStorageImageNonUniformDescriptorArrayShader|nativeBinary=backend/vulkan/VulkanStorageImageNonUniformDescriptorArrayShader.spv|resources.0.kind=storage_image|resources.0.type=image2D[IMAGE_COUNT]|resources.1.type=uimage2DArray[IMAGE_COUNT]|resources.2.kind=buffer|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=5|targetResourceBindings=5|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImages.sourceType=image2D[IMAGE_COUNT]|colorImages.bindingClass=storageImage|colorImages.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE|colorImages.storageClass=UniformConstant|colorImages.arraySize=IMAGE_COUNT|colorImages.arrayElementCount=2|maskAtlases.sourceType=uimage2DArray[IMAGE_COUNT]|maskAtlases.arrayElementCount=2|slots.sourceType=int*|slots.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER|colors.sourceType=vec4*|masks.sourceType=uvec4*"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=vulkan-prototype-package.kind=backend|storage-image.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|SPV_EXT_descriptor_indexing.kind=extension|ShaderNonUniformEXT.kind=capability|StorageImageArrayNonUniformIndexingEXT.kind=capability|storage-image-read.kind=operation|storage-image-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      "-DEXPECTED_SPVASM_SNIPPET=OpCapability StorageImageArrayNonUniformIndexingEXT"
      -DMODE=vulkan-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_vulkan_storage_image_nonuniform_descriptor_array_spvasm_snippets
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage-image-nonuniform-descriptor-array-spvasm.cglb
      -DEXPECTED_MODULE=VulkanStorageImageNonUniformDescriptorArrayShader
      "-DEXPECTED_SPVASM_CONTAINS=OpExtension \"SPV_EXT_descriptor_indexing\"|OpCapability ShaderNonUniformEXT|OpCapability StorageImageArrayNonUniformIndexingEXT|%storage_image_image2D = OpTypeImage %float 2D 0 0 0 2 Rgba32f|%arr_storageImage_image2D_IMAGE_COUNT_ = OpTypeArray %storage_image_image2D %const_uint_2|%resource_colorImages = OpVariable %ptr_UniformConstant_storageImage_image2D_IMAGE_COUNT_ UniformConstant|%storage_image_uimage2DArray = OpTypeImage %uint 2D 0 1 0 2 Rgba32ui|%arr_storageImage_uimage2DArray_IMAGE_COUNT_ = OpTypeArray %storage_image_uimage2DArray %const_uint_2|%resource_maskAtlases = OpVariable %ptr_UniformConstant_storageImage_uimage2DArray_IMAGE_COUNT_ UniformConstant|OpDecorate %tmp_|OpAccessChain %ptr_UniformConstant_storageImage_image2D %resource_colorImages %tmp_|OpImageRead %vec4|OpImageWrite %tmp_|OpAccessChain %ptr_UniformConstant_storageImage_uimage2DArray %resource_maskAtlases %tmp_|OpImageRead %uvec4"
      "-DUNEXPECTED_SPVASM_CONTAINS=OpCapability StorageBufferArrayNonUniformIndexingEXT|OpCapability SampledImageArrayNonUniformIndexingEXT"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectVulkanSpvasmSnippets.cmake)
  crossgl_label_new_optional_native_tests(vulkan
    "${CROSSGL_VULKAN_NATIVE_TESTS_BEFORE}")
else()
  crossgl_add_optional_native_skip_test(
    NAME cglc_vulkan_toolchain_native_smoke_unavailable
    TARGET vulkan
    REASON "optional Vulkan toolchain smoke requires spirv-as and spirv-val"
    REQUIRED_VARS CROSSGL_SPIRV_AS CROSSGL_SPIRV_VAL)
  crossgl_add_optional_native_skip_test(
    NAME cglc_build_vulkan_native_tools_unavailable
    TARGET vulkan
    REQUIRED_VARS CROSSGL_SPIRV_AS CROSSGL_SPIRV_VAL)
endif()

if(NOT CROSSGL_HAS_VULKAN_SPIRV_OPT)
  crossgl_add_optional_native_skip_test(
    NAME cglc_vulkan_spirv_opt_native_smoke_unavailable
    TARGET vulkan
    REASON "optional Vulkan spirv-opt metadata smoke requires spirv-opt"
    REQUIRED_VARS CROSSGL_SPIRV_OPT)
endif()

if(NOT CROSSGL_HAS_VULKAN_SPIRV_DIS)
  crossgl_add_optional_native_skip_test(
    NAME cglc_vulkan_spirv_dis_native_smoke_unavailable
    TARGET vulkan
    REASON "optional Vulkan spirv-dis sidecar smoke requires spirv-dis"
    REQUIRED_VARS CROSSGL_SPIRV_DIS)
endif()
