set(CROSSGL_FAKE_SHADER_TOOL_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/tests/toolchain/FakeShaderTool.cmake")

function(crossgl_configure_fake_metal_xcrun out_dir behavior)
  set(tool_instance "")
  if(ARGC GREATER 2)
    set(tool_instance "-${ARGV2}")
  endif()
  set(tool_dir
      "${CMAKE_CURRENT_BINARY_DIR}/fake-toolchain/xcrun-${behavior}${tool_instance}")
  file(MAKE_DIRECTORY "${tool_dir}")
  set(tool_log "${tool_dir}/xcrun.log")
  file(REMOVE "${tool_log}")

  if(WIN32)
    file(TO_NATIVE_PATH "${CMAKE_COMMAND}" native_cmake_command)
    file(TO_NATIVE_PATH "${CROSSGL_FAKE_SHADER_TOOL_SCRIPT}"
         native_fake_tool_script)
    file(WRITE "${tool_dir}/xcrun.cmd"
         "@echo off\n"
         "\"${native_cmake_command}\" -DFAKE_TOOL_NAME=xcrun -DFAKE_TOOL_BEHAVIOR=${behavior} -DFAKE_TOOL_LOG=\"${tool_log}\" -P \"${native_fake_tool_script}\" -- %*\n"
         "exit /b %ERRORLEVEL%\n")
  else()
    file(WRITE "${tool_dir}/xcrun"
         "#!/bin/sh\n"
         "exec \"${CMAKE_COMMAND}\" -DFAKE_TOOL_NAME=xcrun -DFAKE_TOOL_BEHAVIOR=${behavior} -DFAKE_TOOL_LOG=\"${tool_log}\" -P \"${CROSSGL_FAKE_SHADER_TOOL_SCRIPT}\" -- \"$@\"\n")
    file(CHMOD "${tool_dir}/xcrun"
         PERMISSIONS
           OWNER_READ OWNER_WRITE OWNER_EXECUTE
           GROUP_READ GROUP_EXECUTE
           WORLD_READ WORLD_EXECUTE)
  endif()

  set(${out_dir} "${tool_dir}" PARENT_SCOPE)
endfunction()

crossgl_configure_fake_metal_xcrun(CROSSGL_FAKE_XCRUN_SUCCESS_DIR success)
crossgl_configure_fake_metal_xcrun(CROSSGL_FAKE_XCRUN_O0_SUCCESS_DIR success
                                   o0)
crossgl_configure_fake_metal_xcrun(CROSSGL_FAKE_XCRUN_O2_SUCCESS_DIR success
                                   o2)
crossgl_configure_fake_metal_xcrun(CROSSGL_FAKE_XCRUN_METAL_FAILURE_DIR
                                   metal-failure)
crossgl_configure_fake_metal_xcrun(CROSSGL_FAKE_XCRUN_METALLIB_FAILURE_DIR
                                   metallib-failure)
crossgl_configure_fake_metal_xcrun(CROSSGL_FAKE_XCRUN_METAL_NO_OUTPUT_DIR
                                   metal-no-output)
crossgl_configure_fake_metal_xcrun(CROSSGL_FAKE_XCRUN_METALLIB_NO_OUTPUT_DIR
                                   metallib-no-output)
set(CROSSGL_FAKE_METAL_UNAVAILABLE_DIR
    "${CMAKE_CURRENT_BINARY_DIR}/fake-toolchain/xcrun-unavailable")
file(MAKE_DIRECTORY "${CROSSGL_FAKE_METAL_UNAVAILABLE_DIR}")

add_test(NAME cglc_build_metal_native_fake_xcrun_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-fake-xcrun-success.cglb
    -DEXPECTED_MODULE=SimpleShader
    -DMODE=metal-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_XCRUN_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DEXPECTED_INTERMEDIATE=backend/metal/SimpleShader.air
    -DEXPECTED_NATIVE_BINARY=backend/metal/SimpleShader.metallib
    "-DEXPECTED_INTERMEDIATE_CONTAINS=fake metal air"
    "-DEXPECTED_NATIVE_BINARY_CONTAINS=fake metal metallib"
    "-DEXPECTED_METAL_COMPILE_OPTIONS_JSON_FIELDS=schemaVersion=1|target=metal|module=SimpleShader|policy.name=metal-conservative-native-package-v1|policy.profile=release|policy.requestedOptimizationLevel=O1|policy.optimizationLevel=-O2|policy.debugInfo=false|compile.tool=xcrun metal|compile.sdk=macosx|compile.flags.0=-O2|library.tool=xcrun metallib"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=SimpleShader|targetLegalizationToolRequirements.target=metal|targetLegalizationToolRequirements.packageMode=native|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=0|targetLegalizationToolRequirements.optionalNativeToolMissing=false|targetLegalizationToolRequirements.optionalNativeToolStatus=not-required|artifacts.backendSource=backend/metal/SimpleShader.metal|artifacts.intermediate=backend/metal/SimpleShader.air|artifacts.nativeBinary=backend/metal/SimpleShader.metallib|artifacts.nativeArtifactDescriptor=backend/metal/SimpleShader.native-artifact.json|artifacts.graphicsAbi=backend/metal/SimpleShader.graphics-abi.json"
    "-DEXPECTED_MANIFEST_JSON_ARRAY_CONTAINS=targetLegalizationToolRequirements.requiredToolIds=metal.toolchain.xcrun-metal|targetLegalizationToolRequirements.requiredToolIds=metal.toolchain.xcrun-metallib|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.metal.tool-requirements.present"
    "-DEXPECTED_MANIFEST_JSON_ARRAY_LENGTHS=targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=0|targetLegalizationToolRequirements.toolRequirementEvidenceIds=3"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=metal|binaryKind=metal.metallib|sourcePath=backend/metal/SimpleShader.metal|artifactPath=backend/metal/SimpleShader.metallib|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=O2|optimizationEvidence.policy=metal-conservative-native-package-v1|optimizationEvidence.status=applied|optimizationEvidence.tool=xcrun metal|optimizationEvidence.toolFlag=-O2|optimizationEvidence.debugInfo=false|optimizationEvidence.profile=release|optimizationEvidence.flags.0=-O2|validationStatus=not-run"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=3|validationDiagnostics=0"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SimpleShader|nativeBinary=backend/metal/SimpleShader.metallib"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_XCRUN_SUCCESS_DIR}/xcrun.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=xcrun success: -sdk macosx metallib"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_metal_native_opt_level_o0_fake_xcrun
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-fake-xcrun-o0.cglb
    -DEXPECTED_MODULE=SimpleShader
    -DMODE=metal-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_XCRUN_O0_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DOPT_LEVEL=O0
    -DEXPECTED_INTERMEDIATE=backend/metal/SimpleShader.air
    -DEXPECTED_NATIVE_BINARY=backend/metal/SimpleShader.metallib
    "-DEXPECTED_METAL_COMPILE_OPTIONS_JSON_FIELDS=schemaVersion=1|target=metal|module=SimpleShader|policy.name=metal-conservative-native-package-v1|policy.profile=debug|policy.requestedOptimizationLevel=O0|policy.optimizationLevel=-O0|policy.debugInfo=true|compile.tool=xcrun metal|compile.sdk=macosx|compile.flags.0=-O0|compile.flags.1=-gline-tables-only|library.tool=xcrun metallib"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=SimpleShader|artifacts.backendSource=backend/metal/SimpleShader.metal|artifacts.intermediate=backend/metal/SimpleShader.air|artifacts.nativeBinary=backend/metal/SimpleShader.metallib|artifacts.nativeArtifactDescriptor=backend/metal/SimpleShader.native-artifact.json|artifacts.graphicsAbi=backend/metal/SimpleShader.graphics-abi.json"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=metal|binaryKind=metal.metallib|sourcePath=backend/metal/SimpleShader.metal|artifactPath=backend/metal/SimpleShader.metallib|optimizationLevel=O0|optimizationEvidence.requestedLevel=O0|optimizationEvidence.effectiveLevel=O0|optimizationEvidence.policy=metal-conservative-native-package-v1|optimizationEvidence.status=applied|optimizationEvidence.tool=xcrun metal|optimizationEvidence.toolFlag=-O0|optimizationEvidence.debugInfo=true|optimizationEvidence.profile=debug|optimizationEvidence.flags.0=-O0|optimizationEvidence.flags.1=-gline-tables-only|validationStatus=not-run"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=3|validationDiagnostics=0"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_XCRUN_O0_SUCCESS_DIR}/xcrun.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=xcrun success: -sdk macosx metal -O0 -gline-tables-only"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_XCRUN_O0_SUCCESS_DIR}/xcrun.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=xcrun success: -sdk macosx metallib"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_metal_native_opt_level_o2_fake_xcrun
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-fake-xcrun-o2.cglb
    -DEXPECTED_MODULE=SimpleShader
    -DMODE=metal-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_XCRUN_O2_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    -DOPT_LEVEL=O2
    -DEXPECTED_INTERMEDIATE=backend/metal/SimpleShader.air
    -DEXPECTED_NATIVE_BINARY=backend/metal/SimpleShader.metallib
    "-DEXPECTED_INTERMEDIATE_CONTAINS=fake metal air"
    "-DEXPECTED_NATIVE_BINARY_CONTAINS=fake metal metallib"
    "-DEXPECTED_METAL_COMPILE_OPTIONS_JSON_FIELDS=schemaVersion=1|target=metal|module=SimpleShader|policy.name=metal-conservative-native-package-v1|policy.profile=release|policy.requestedOptimizationLevel=O2|policy.optimizationLevel=-O2|policy.debugInfo=false|compile.tool=xcrun metal|compile.sdk=macosx|compile.flags.0=-O2|library.tool=xcrun metallib"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=SimpleShader|artifacts.backendSource=backend/metal/SimpleShader.metal|artifacts.intermediate=backend/metal/SimpleShader.air|artifacts.nativeBinary=backend/metal/SimpleShader.metallib|artifacts.nativeArtifactDescriptor=backend/metal/SimpleShader.native-artifact.json|artifacts.graphicsAbi=backend/metal/SimpleShader.graphics-abi.json"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=metal|binaryKind=metal.metallib|sourcePath=backend/metal/SimpleShader.metal|artifactPath=backend/metal/SimpleShader.metallib|optimizationLevel=O2|optimizationEvidence.requestedLevel=O2|optimizationEvidence.effectiveLevel=O2|optimizationEvidence.policy=metal-conservative-native-package-v1|optimizationEvidence.status=applied|optimizationEvidence.tool=xcrun metal|optimizationEvidence.toolFlag=-O2|optimizationEvidence.debugInfo=false|optimizationEvidence.profile=release|optimizationEvidence.flags.0=-O2|validationStatus=not-run"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=3|validationDiagnostics=0"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_XCRUN_O2_SUCCESS_DIR}/xcrun.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=xcrun success: -sdk macosx metal -O2"
    -DEXPECTED_SECOND_TOOL_LOG=${CROSSGL_FAKE_XCRUN_O2_SUCCESS_DIR}/xcrun.log
    "-DEXPECTED_SECOND_TOOL_LOG_CONTAINS=xcrun success: -sdk macosx metallib"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set(CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_NATIVE_SOURCE_SNIPPET [=[vertex RasterPayload vertex_main(MeshVertex input [[stage_in]], array<texture2d<float>, RESOURCE_COUNT> heightMaps [[texture(1)]], array<sampler, RESOURCE_COUNT> heightSamplers [[sampler(3)]]) {
  RasterPayload output;
  float4 height = heightMaps[1].sample(heightSamplers[0], input.texCoord, level(0.0));]=])
add_test(NAME cglc_build_metal_graphics_descriptor_array_fake_xcrun_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-graphics-descriptor-array-fake-xcrun.cglb
    -DEXPECTED_MODULE=MetalGraphicsDescriptorArrayShader
    -DMODE=metal-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_XCRUN_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_NATIVE_SOURCE_SNIPPET}"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsDescriptorArrayShader|artifacts.backendSource=backend/metal/MetalGraphicsDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/MetalGraphicsDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/MetalGraphicsDescriptorArrayShader.metallib|artifacts.graphicsAbi=backend/metal/MetalGraphicsDescriptorArrayShader.graphics-abi.json"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsDescriptorArrayShader|nativeBinary=backend/metal/MetalGraphicsDescriptorArrayShader.metallib|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|functionConstants.0.name=RESOURCE_COUNT|functionConstants.0.value=2|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=6|targetResourceBindings=6|vertexLayouts=1|vertexLayouts.0.attributes=3|functionConstants=1|workgroupSizes=0|manualTextureCompareKernels=0"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=heightMaps.stage=vertex|heightMaps.entryPoint=vertex_main|heightMaps.kind=texture|heightMaps.sourceType=sampler2D[RESOURCE_COUNT]|heightMaps.metalType=array<texture2d<float>, RESOURCE_COUNT>|heightMaps.bindingClass=texture|heightMaps.argumentIndex=1|heightMaps.set=0|heightMaps.binding=1|heightMaps.arraySize=RESOURCE_COUNT|heightMaps.arrayElementCount=2|heightSamplers.stage=vertex|heightSamplers.entryPoint=vertex_main|heightSamplers.kind=sampler|heightSamplers.sourceType=sampler[RESOURCE_COUNT]|heightSamplers.metalType=array<sampler, RESOURCE_COUNT>|heightSamplers.bindingClass=sampler|heightSamplers.argumentIndex=3|heightSamplers.arrayElementCount=2|colorMaps.stage=fragment|colorMaps.entryPoint=fragment_main|colorMaps.kind=texture|colorMaps.sourceType=sampler2D[RESOURCE_COUNT]|colorMaps.metalType=array<texture2d<float>, RESOURCE_COUNT>|colorMaps.bindingClass=texture|colorMaps.argumentIndex=1|colorMaps.arrayElementCount=2|linearSamplers.stage=fragment|linearSamplers.kind=sampler|linearSamplers.sourceType=sampler[RESOURCE_COUNT]|linearSamplers.metalType=array<sampler, RESOURCE_COUNT>|linearSamplers.argumentIndex=3|shadowMaps.stage=fragment|shadowMaps.kind=texture|shadowMaps.sourceType=sampler2DShadow[RESOURCE_COUNT]|shadowMaps.metalType=array<depth2d<float>, RESOURCE_COUNT>|shadowMaps.bindingClass=texture|shadowMaps.argumentIndex=6|shadowMaps.arrayElementCount=2|shadowSamplers.stage=fragment|shadowSamplers.kind=sampler|shadowSamplers.sourceType=comparison_sampler[RESOURCE_COUNT]|shadowSamplers.metalType=array<sampler, RESOURCE_COUNT>|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=8|shadowSamplers.arrayElementCount=2"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|sampled-texture.kind=resource|sampler-state.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|depth-compare-format.kind=texture|texture-sample.kind=operation|texture-explicit-lod.kind=operation|texture-shadow-compare-explicit-lod.kind=operation"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_XCRUN_SUCCESS_DIR}/xcrun.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=xcrun success: -sdk macosx metallib"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_add_python_expect_test(
  NAME cglc_package_inspect_metal_graphics_descriptor_array_fake_xcrun
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-graphics-descriptor-array-inspect-fake-xcrun.cglb
    -DMODE=package-inspect-source-package
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_XCRUN_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=MetalGraphicsDescriptorArrayShader|summary.target=metal|summary.nativeBinaryStatus=null|summary.artifactCount=8|summary.debugArtifactsPresent=true|artifacts.5.name=nativeArtifactDescriptor|artifacts.5.path=backend/metal/MetalGraphicsDescriptorArrayShader.native-artifact.json|artifacts.5.exists=true|artifacts.7.name=graphicsAbi|artifacts.7.path=backend/metal/MetalGraphicsDescriptorArrayShader.graphics-abi.json|artifacts.7.exists=true|manifest.target=metal|manifest.artifacts.nativeArtifactDescriptor=backend/metal/MetalGraphicsDescriptorArrayShader.native-artifact.json|manifest.artifacts.graphicsAbi=backend/metal/MetalGraphicsDescriptorArrayShader.graphics-abi.json|nativeArtifactDescriptor.health=ok|nativeArtifactDescriptor.target=metal|nativeArtifactDescriptor.binaryKind=metal.metallib|nativeArtifactDescriptor.sourcePath=backend/metal/MetalGraphicsDescriptorArrayShader.metal|nativeArtifactDescriptor.artifactPath=backend/metal/MetalGraphicsDescriptorArrayShader.metallib|nativeArtifactDescriptor.validationStatus=not-run|nativeArtifactDescriptor.checks.sourceHashMatchesFile=true|nativeArtifactDescriptor.checks.artifactHashMatchesFile=true|nativeArtifactDescriptor.checks.sizeBytesMatchesFile=true|reflection.target=metal|reflection.module=MetalGraphicsDescriptorArrayShader|reflection.targetResourceBindings.0.stage=vertex|reflection.targetResourceBindings.0.argumentIndex=1|reflection.targetResourceBindings.1.stage=vertex|reflection.targetResourceBindings.1.argumentIndex=3|reflection.targetResourceBindings.2.stage=fragment|reflection.targetResourceBindings.2.argumentIndex=1|reflection.targetResourceBindings.4.argumentIndex=6|reflection.targetResourceBindings.5.argumentIndex=8"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=metal|binaryKind=metal.metallib|sourcePath=backend/metal/MetalGraphicsDescriptorArrayShader.metal|artifactPath=backend/metal/MetalGraphicsDescriptorArrayShader.metallib|validationStatus=not-run"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=3|validationDiagnostics=0"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=artifacts=8|reflection.entryPoints=2|reflection.resources=6|reflection.targetResourceBindings=6|reflection.vertexLayouts=1|reflection.vertexLayouts.0.attributes=3|reflection.functionConstants=1|reflection.manualTextureCompareKernels=0|diagnostics.diagnostics=0"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
add_test(NAME cglc_build_metal_mixed_texture_compare_descriptor_array_fake_xcrun_success
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_MIXED_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-mixed-texture-compare-descriptor-array-fake-xcrun.cglb
    -DEXPECTED_MODULE=MetalMixedTextureCompareDescriptorArrayShader
    -DMODE=metal-build
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_XCRUN_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_METAL_SOURCE_SNIPPET=array<texture2d<float>, RESOURCE_COUNT> colorMaps [[texture(2)]], array<depth2d<float>, RESOURCE_COUNT> shadowMaps [[texture(4)]], array<sampler, 2> linearSamplers [[sampler(5)]], array<sampler, 2> shadowSamplers [[sampler(7)]]"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalMixedTextureCompareDescriptorArrayShader|artifacts.backendSource=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.metallib"
    "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalMixedTextureCompareDescriptorArrayShader|nativeBinary=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.metallib|manualTextureCompareKernelSummary.totalCount=0"
    "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=5|targetResourceBindings=5|functionConstants=1|manualTextureCompareKernels=0|workgroupSizes=1"
    "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.metalType=device float4*|values.bindingClass=buffer|values.argumentIndex=0|colorMaps.sourceType=sampler2D[RESOURCE_COUNT]|colorMaps.metalType=array<texture2d<float>, RESOURCE_COUNT>|colorMaps.bindingClass=texture|colorMaps.argumentIndex=2|colorMaps.arraySize=RESOURCE_COUNT|colorMaps.arrayElementCount=2|shadowMaps.sourceType=sampler2DShadow[RESOURCE_COUNT]|shadowMaps.metalType=array<depth2d<float>, RESOURCE_COUNT>|shadowMaps.bindingClass=texture|shadowMaps.argumentIndex=4|shadowMaps.arrayElementCount=2|linearSamplers.sourceType=sampler[2]|linearSamplers.metalType=array<sampler, 2>|linearSamplers.bindingClass=sampler|linearSamplers.argumentIndex=5|shadowSamplers.sourceType=sampler[2]|shadowSamplers.metalType=array<sampler, 2>|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=7"
    "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|sampled-texture.kind=resource|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|storage-buffer-write.kind=operation"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_XCRUN_SUCCESS_DIR}/xcrun.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=xcrun success: -sdk macosx metallib"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_add_python_expect_test(
  NAME cglc_package_inspect_metal_mixed_texture_compare_descriptor_array_fake_xcrun
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_MIXED_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
    -DTARGET=metal
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-mixed-texture-compare-descriptor-array-inspect-fake-xcrun.cglb
    -DMODE=package-inspect-source-package
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_XCRUN_SUCCESS_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=MetalMixedTextureCompareDescriptorArrayShader|summary.target=metal|summary.nativeBinaryStatus=null|summary.artifactCount=7|summary.debugArtifactsPresent=true|artifacts.5.name=nativeArtifactDescriptor|artifacts.5.path=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.native-artifact.json|artifacts.5.exists=true|manifest.target=metal|manifest.artifacts.nativeArtifactDescriptor=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.native-artifact.json|nativeArtifactDescriptor.health=ok|nativeArtifactDescriptor.target=metal|nativeArtifactDescriptor.binaryKind=metal.metallib|nativeArtifactDescriptor.sourcePath=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.metal|nativeArtifactDescriptor.artifactPath=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.metallib|nativeArtifactDescriptor.validationStatus=not-run|nativeArtifactDescriptor.checks.sourceHashMatchesFile=true|nativeArtifactDescriptor.checks.artifactHashMatchesFile=true|nativeArtifactDescriptor.checks.sizeBytesMatchesFile=true|reflection.target=metal|reflection.module=MetalMixedTextureCompareDescriptorArrayShader|reflection.targetResourceBindings.1.argumentIndex=2|reflection.targetResourceBindings.2.argumentIndex=4|reflection.targetResourceBindings.3.argumentIndex=5|reflection.targetResourceBindings.4.argumentIndex=7"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=metal|binaryKind=metal.metallib|sourcePath=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.metal|artifactPath=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.metallib|validationStatus=not-run"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=toolchainProvenance.tools=3|validationDiagnostics=0"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=artifacts=7|reflection.resources=5|reflection.targetResourceBindings=5|reflection.manualTextureCompareKernels=0|diagnostics.diagnostics=0"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
add_test(NAME cglc_build_metal_native_fake_xcrun_metal_tool_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-fake-xcrun-metal-failure.cglb
    -DMODE=metal-build-failure
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_XCRUN_METAL_FAILURE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_STDERR_FRAGMENT=metal.compile-failed"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=metal.compile-failed"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_XCRUN_METAL_FAILURE_DIR}/xcrun.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=xcrun metal-failure: -sdk macosx metal -O2 -c"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_metal_native_fake_xcrun_metallib_tool_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-fake-xcrun-metallib-failure.cglb
    -DMODE=metal-build-failure
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_XCRUN_METALLIB_FAILURE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_STDERR_FRAGMENT=metal.library-failed"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=metal.library-failed"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_XCRUN_METALLIB_FAILURE_DIR}/xcrun.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=xcrun metallib-failure: -sdk macosx metallib"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_metal_native_fake_xcrun_metal_missing_air_tool_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-fake-xcrun-metal-missing-air.cglb
    -DMODE=metal-build-failure
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_XCRUN_METAL_NO_OUTPUT_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_STDERR_FRAGMENT=metal.air-missing"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=metal.air-missing"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=xcrun metal reported success"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_XCRUN_METAL_NO_OUTPUT_DIR}/xcrun.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=xcrun metal-no-output: -sdk macosx metal -O2 -c"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_metal_native_fake_xcrun_metallib_missing_library_tool_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-fake-xcrun-metallib-missing-library.cglb
    -DMODE=metal-build-failure
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_XCRUN_METALLIB_NO_OUTPUT_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_STDERR_FRAGMENT=metal.metallib-missing"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=metal.metallib-missing"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=xcrun metallib reported success"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    -DEXPECTED_TOOL_LOG=${CROSSGL_FAKE_XCRUN_METALLIB_NO_OUTPUT_DIR}/xcrun.log
    "-DEXPECTED_TOOL_LOG_CONTAINS=xcrun metallib-no-output: -sdk macosx metallib"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_build_metal_native_fake_xcrun_unavailable
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-fake-xcrun-unavailable.cglb
    -DMODE=metal-build-failure
    -DTOOLCHAIN_PATH=${CROSSGL_FAKE_METAL_UNAVAILABLE_DIR}
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_STDERR_FRAGMENT=metal.xcrun-missing"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=diagnostics.0.severity=error|diagnostics.0.code=metal.xcrun-missing"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELD_CONTAINS=diagnostics.0.message=xcrun is required"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

crossgl_label_optional_native_policy_test(
  cglc_build_metal_native_fake_xcrun_metal_tool_failure metal)
crossgl_label_optional_native_policy_test(
  cglc_build_metal_native_fake_xcrun_metallib_tool_failure metal)
crossgl_label_optional_native_policy_test(
  cglc_build_metal_native_fake_xcrun_unavailable metal)

crossgl_capture_current_tests(CROSSGL_METAL_NATIVE_TESTS_BEFORE)

if(CROSSGL_HAS_METAL_NATIVE_TOOLS)
  add_test(NAME cglc_metal_toolchain_native_smoke
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SIMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-toolchain-smoke.cglb
      -DEXPECTED_MODULE=SimpleShader
      "-DXCRUN=${CROSSGL_XCRUN}"
      "-DMETAL=${CROSSGL_METAL}"
      "-DMETALLIB=${CROSSGL_METALLIB}"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/MetalToolchainSmoke.cmake)
  crossgl_label_optional_native_test(cglc_metal_toolchain_native_smoke metal)
  add_test(NAME cglc_build_metal_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SIMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal.cglb
      -DEXPECTED_MODULE=SimpleShader
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_add_python_expect_test(
    NAME cglc_manifest_json_schema_metal_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SIMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-manifest-schema.cglb
      -DEXPECTED_MODULE=SimpleShader
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=SimpleShader|sourceHash.algorithm=sha256|packageArtifactRequirements.target=metal|packageArtifactRequirements.packageMode=native|packageArtifactRequirements.requiresNativeBinaryStatus=false|artifacts.backendSource=backend/metal/SimpleShader.metal|artifacts.intermediate=backend/metal/SimpleShader.air|artifacts.nativeBinary=backend/metal/SimpleShader.metallib|artifacts.nativeArtifactDescriptor=backend/metal/SimpleShader.native-artifact.json|artifacts.graphicsAbi=backend/metal/SimpleShader.graphics-abi.json"
      "-DEXPECTED_MANIFEST_JSON_ABSENT_PATHS=artifacts.nativeBinaryStatus"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=metal|binaryKind=metal.metallib|sourcePath=backend/metal/SimpleShader.metal|artifactPath=backend/metal/SimpleShader.metallib|validationStatus=not-run"
      -DMANIFEST_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/manifest-v1.schema.json
      -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
      -DPACKAGE_SCHEMA_ROOT=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py
      -DMODE=metal-build)
  crossgl_add_python_expect_test(
    NAME cglc_reflection_json_schema_metal_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SIMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-reflection-schema.cglb
      -DEXPECTED_MODULE=SimpleShader
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SimpleShader|nativeBinary=backend/metal/SimpleShader.metallib"
      -DREFLECTION_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/reflection-v1.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      -DMODE=metal-build)
  crossgl_add_python_expect_test(
    NAME cglc_package_inspect_json_schema_metal_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SIMPLE_SHADER}
      -DTARGET=metal
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-package-inspect.cglb
      -DMODE=package-inspect-source-package
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=SimpleShader|summary.target=metal|summary.nativeBinaryStatus=null|summary.artifactCount=8|summary.debugArtifactsPresent=true|rootFiles.0.name=manifest|rootFiles.0.exists=true|rootFiles.1.name=reflection|rootFiles.1.exists=true|rootFiles.2.name=diagnostics|rootFiles.2.exists=true|artifacts.0.name=backendSource|artifacts.0.path=backend/metal/SimpleShader.metal|artifacts.0.exists=true|artifacts.1.name=intermediate|artifacts.1.path=backend/metal/SimpleShader.air|artifacts.1.exists=true|artifacts.2.name=nativeBinary|artifacts.2.path=backend/metal/SimpleShader.metallib|artifacts.2.exists=true|artifacts.3.name=debugMetadata|artifacts.3.exists=true|artifacts.4.name=hirSourceMap|artifacts.4.exists=true|artifacts.5.name=nativeArtifactDescriptor|artifacts.5.path=backend/metal/SimpleShader.native-artifact.json|artifacts.5.exists=true|artifacts.7.name=graphicsAbi|artifacts.7.path=backend/metal/SimpleShader.graphics-abi.json|artifacts.7.exists=true|manifest.target=metal|manifest.module=SimpleShader|manifest.artifacts.nativeArtifactDescriptor=backend/metal/SimpleShader.native-artifact.json|manifest.artifacts.graphicsAbi=backend/metal/SimpleShader.graphics-abi.json|nativeArtifactDescriptor.health=ok|nativeArtifactDescriptor.target=metal|nativeArtifactDescriptor.binaryKind=metal.metallib|nativeArtifactDescriptor.sourcePath=backend/metal/SimpleShader.metal|nativeArtifactDescriptor.artifactPath=backend/metal/SimpleShader.metallib|nativeArtifactDescriptor.validationStatus=not-run|nativeArtifactDescriptor.checks.sourceHashMatchesFile=true|nativeArtifactDescriptor.checks.artifactHashMatchesFile=true|nativeArtifactDescriptor.checks.sizeBytesMatchesFile=true|reflection.target=metal|reflection.module=SimpleShader|reflection.nativeBinary=backend/metal/SimpleShader.metallib|diagnostics.schemaVersion=1"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=metal|binaryKind=metal.metallib|sourcePath=backend/metal/SimpleShader.metal|artifactPath=backend/metal/SimpleShader.metallib|validationStatus=not-run"
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
      -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
  crossgl_add_python_expect_test(
    NAME cglc_package_artifact_inventory_json_schema_metal_graphics_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsVaryingPackShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-graphics-artifact-inventory-schema.cglb
      -DEXPECTED_MODULE=MetalGraphicsVaryingPackShader
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsVaryingPackShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/MetalGraphicsVaryingPackShader.metal|artifacts.intermediate=backend/metal/MetalGraphicsVaryingPackShader.air|artifacts.nativeBinary=backend/metal/MetalGraphicsVaryingPackShader.metallib|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/metal/MetalGraphicsVaryingPackShader.native-artifact.json|artifacts.targetExplanation=ir/target-explanation.json"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=metal|binaryKind=metal.metallib|sourcePath=backend/metal/MetalGraphicsVaryingPackShader.metal|artifactPath=backend/metal/MetalGraphicsVaryingPackShader.metallib|validationStatus=not-run"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsVaryingPackShader|nativeBinary=backend/metal/MetalGraphicsVaryingPackShader.metallib|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=0|targetResourceBindings=0|vertexLayouts=1|vertexLayouts.0.attributes=4|functionConstants=0|workgroupSizes=0|manualTextureCompareKernels=0"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMANIFEST_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/manifest-v1.schema.json
      -DREFLECTION_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/reflection-v1.schema.json
      -DDEBUG_METADATA_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/debug-metadata-v11.schema.json
      -DHIR_SOURCE_MAP_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/hir-source-map-v7.schema.json
      -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
      -DPACKAGE_SCHEMA_ROOT=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py
      -DMODE=metal-build)
  crossgl_add_python_expect_test(
    NAME cglc_package_inspect_artifact_inventory_json_schema_metal_graphics_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsVaryingPackShader.cgl
      -DTARGET=metal
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-graphics-package-inspect-artifact-inventory.cglb
      -DMODE=package-inspect-source-package
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=MetalGraphicsVaryingPackShader|summary.target=metal|summary.nativeBinaryStatus=null|summary.artifactCount=8|summary.debugArtifactsPresent=true|debugArtifacts.debugMetadataArtifactPresent=true|debugArtifacts.hirSourceMapArtifactPresent=true|debugArtifacts.debugMetadataExists=true|debugArtifacts.hirSourceMapExists=true|debugArtifacts.health=ok|debugArtifacts.checks.hirSourceLocationsMatch=true|debugArtifacts.checks.sourceMapUnfiltered=true|debugArtifacts.checks.sourceMapUnpaged=true|debugArtifacts.checks.sourceMapRecordsDisabled=true|artifacts.0.name=backendSource|artifacts.0.path=backend/metal/MetalGraphicsVaryingPackShader.metal|artifacts.0.exists=true|artifacts.1.name=intermediate|artifacts.1.path=backend/metal/MetalGraphicsVaryingPackShader.air|artifacts.1.exists=true|artifacts.2.name=nativeBinary|artifacts.2.path=backend/metal/MetalGraphicsVaryingPackShader.metallib|artifacts.2.exists=true|artifacts.3.name=debugMetadata|artifacts.3.path=ir/debug-metadata.json|artifacts.3.exists=true|artifacts.4.name=hirSourceMap|artifacts.4.path=ir/hir-source-map.json|artifacts.4.exists=true|artifacts.5.name=nativeArtifactDescriptor|artifacts.5.path=backend/metal/MetalGraphicsVaryingPackShader.native-artifact.json|artifacts.5.exists=true|artifacts.6.name=targetExplanation|artifacts.6.path=ir/target-explanation.json|artifacts.6.exists=true|artifacts.7.name=graphicsAbi|artifacts.7.path=backend/metal/MetalGraphicsVaryingPackShader.graphics-abi.json|artifacts.7.exists=true|manifest.target=metal|manifest.module=MetalGraphicsVaryingPackShader|manifest.artifacts.backendSource=backend/metal/MetalGraphicsVaryingPackShader.metal|manifest.artifacts.intermediate=backend/metal/MetalGraphicsVaryingPackShader.air|manifest.artifacts.nativeBinary=backend/metal/MetalGraphicsVaryingPackShader.metallib|manifest.artifacts.debugMetadata=ir/debug-metadata.json|manifest.artifacts.hirSourceMap=ir/hir-source-map.json|manifest.artifacts.nativeArtifactDescriptor=backend/metal/MetalGraphicsVaryingPackShader.native-artifact.json|manifest.artifacts.targetExplanation=ir/target-explanation.json|manifest.artifacts.graphicsAbi=backend/metal/MetalGraphicsVaryingPackShader.graphics-abi.json|nativeArtifactDescriptor.health=ok|nativeArtifactDescriptor.target=metal|nativeArtifactDescriptor.binaryKind=metal.metallib|nativeArtifactDescriptor.sourcePath=backend/metal/MetalGraphicsVaryingPackShader.metal|nativeArtifactDescriptor.artifactPath=backend/metal/MetalGraphicsVaryingPackShader.metallib|nativeArtifactDescriptor.validationStatus=not-run|nativeArtifactDescriptor.checks.sourceHashMatchesFile=true|nativeArtifactDescriptor.checks.artifactHashMatchesFile=true|nativeArtifactDescriptor.checks.sizeBytesMatchesFile=true|reflection.target=metal|reflection.module=MetalGraphicsVaryingPackShader|reflection.nativeBinary=backend/metal/MetalGraphicsVaryingPackShader.metallib|reflection.entryPoints.0.stage=vertex|reflection.entryPoints.1.stage=fragment|diagnostics.schemaVersion=1"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=metal|binaryKind=metal.metallib|sourcePath=backend/metal/MetalGraphicsVaryingPackShader.metal|artifactPath=backend/metal/MetalGraphicsVaryingPackShader.metallib|validationStatus=not-run"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=artifacts=8|reflection.entryPoints=2|reflection.resources=0|reflection.targetResourceBindings=0|reflection.vertexLayouts=1|reflection.vertexLayouts.0.attributes=4|reflection.workgroupSizes=0|diagnostics.diagnostics=0"
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
      -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
  add_test(NAME cglc_build_metal_mixed_texture_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_MIXED_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-mixed-texture-compare-descriptor-array-native.cglb
      -DEXPECTED_MODULE=MetalMixedTextureCompareDescriptorArrayShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMaps [[texture(4)]], array<sampler, 2> linearSamplers [[sampler(5)]], array<sampler, 2> shadowSamplers [[sampler(7)]]"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalMixedTextureCompareDescriptorArrayShader|artifacts.backendSource=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalMixedTextureCompareDescriptorArrayShader|nativeBinary=backend/metal/MetalMixedTextureCompareDescriptorArrayShader.metallib|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=5|targetResourceBindings=5|functionConstants=1|manualTextureCompareKernels=0|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.argumentIndex=2|shadowMaps.argumentIndex=4|linearSamplers.argumentIndex=5|shadowSamplers.argumentIndex=7|shadowMaps.metalType=array<depth2d<float>, RESOURCE_COUNT>|shadowSamplers.metalType=array<sampler, 2>"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|descriptor-array.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_GRAPHICS_STAGE_ABI_NATIVE_SOURCE_SNIPPET [=[struct MeshVertex {
  float3 position [[attribute(0)]];
  float2 texCoord [[attribute(1)]];
  float3 tint [[attribute(2)]];
};

struct RasterPayload {
  float4 clipPosition [[position]];
  float2 uv;
  float3 tint;
};

struct FragmentPayload {
  float2 uv;
  float3 tint;
};

struct DualColorTargets {
  float4 primary [[color(0)]];
  float4 secondary [[color(1)]];
};

vertex RasterPayload vertex_main(MeshVertex input [[stage_in]]) {
  RasterPayload output;
  output.clipPosition = float4(input.position, 1.0);
  output.uv = input.texCoord;
  output.tint = input.tint;
  return output;
}

fragment DualColorTargets fragment_main(FragmentPayload input [[stage_in]]) {]=])
  crossgl_add_python_expect_test(
    NAME cglc_build_metal_graphics_stage_abi_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsStagesShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-graphics-stage-abi.cglb
      -DEXPECTED_MODULE=MetalGraphicsStagesShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_GRAPHICS_STAGE_ABI_NATIVE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsStagesShader|artifacts.backendSource=backend/metal/MetalGraphicsStagesShader.metal|artifacts.intermediate=backend/metal/MetalGraphicsStagesShader.air|artifacts.nativeBinary=backend/metal/MetalGraphicsStagesShader.metallib|artifacts.graphicsAbi=backend/metal/MetalGraphicsStagesShader.graphics-abi.json"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsStagesShader|nativeBinary=backend/metal/MetalGraphicsStagesShader.metallib|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main"
      "-DEXPECTED_REFLECTION_JSON_PATHS=vertexLayouts"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|vertexLayouts=1"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py
      -DMODE=metal-build)
  set(CROSSGL_METAL_GRAPHICS_VARYING_PACK_NATIVE_SOURCE_SNIPPET [=[struct PackedVertex {
  float3 position [[attribute(0)]];
  float3 normal [[attribute(1)]];
  float2 texCoord [[attribute(2)]];
  float weight [[attribute(3)]];
};

struct VertexPayload {
  float2 uv;
  float4 position [[position]];
  float3 lighting;
  float weight;
};

struct FragmentPayload {
  float2 uv;
  float3 lighting;
  float weight;
};

struct ShadedTarget {
  float4 shaded [[color(0)]];
};

vertex VertexPayload vertex_main(PackedVertex input [[stage_in]]) {
  VertexPayload output;
  output.uv = input.texCoord;
  output.position = float4(input.position, 1.0);
  output.lighting = input.normal * input.weight + float3(0.1, 0.2, 0.3);
  output.weight = input.weight;
  return output;
}

fragment ShadedTarget fragment_main(FragmentPayload input [[stage_in]]) {
  ShadedTarget output;
  output.shaded = float4(input.lighting.x * input.uv.x, input.lighting.y * input.uv.y, input.lighting.z, input.weight);]=])
  crossgl_add_python_expect_test(
    NAME cglc_build_metal_graphics_varying_pack_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsVaryingPackShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-graphics-varying-pack.cglb
      -DEXPECTED_MODULE=MetalGraphicsVaryingPackShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_GRAPHICS_VARYING_PACK_NATIVE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsVaryingPackShader|artifacts.backendSource=backend/metal/MetalGraphicsVaryingPackShader.metal|artifacts.intermediate=backend/metal/MetalGraphicsVaryingPackShader.air|artifacts.nativeBinary=backend/metal/MetalGraphicsVaryingPackShader.metallib|artifacts.graphicsAbi=backend/metal/MetalGraphicsVaryingPackShader.graphics-abi.json"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsVaryingPackShader|nativeBinary=backend/metal/MetalGraphicsVaryingPackShader.metallib|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main|vertexLayouts.0.attributes.0.name=position|vertexLayouts.0.attributes.0.type=vec3|vertexLayouts.0.attributes.0.location=0|vertexLayouts.0.attributes.1.name=normal|vertexLayouts.0.attributes.1.type=vec3|vertexLayouts.0.attributes.1.location=1|vertexLayouts.0.attributes.2.name=texCoord|vertexLayouts.0.attributes.2.type=vec2|vertexLayouts.0.attributes.2.location=2|vertexLayouts.0.attributes.3.name=weight|vertexLayouts.0.attributes.3.type=float|vertexLayouts.0.attributes.3.location=3|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_PATHS=vertexLayouts"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=0|targetResourceBindings=0|vertexLayouts=1|vertexLayouts.0.attributes=4|functionConstants=0|workgroupSizes=0|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|vertex-shader.kind=stage|fragment-shader.kind=stage|vector-constructor.kind=operation|vector-arithmetic.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py
      -DMODE=metal-build)
  set(CROSSGL_METAL_GRAPHICS_FRAGMENT_RESOURCES_NATIVE_SOURCE_SNIPPET [=[struct TintParams {
  float4 tint;
};

struct ColorTarget {
  float4 color [[color(0)]];
};

vertex RasterPayload vertex_main(MeshVertex input [[stage_in]]) {
  RasterPayload output;
  output.clipPosition = float4(input.position, 1.0);
  output.uv = input.texCoord;
  return output;
}

fragment ColorTarget fragment_main(FragmentPayload input [[stage_in]], constant TintParams& params [[buffer(1)]], texture2d<float> colorMap [[texture(2)]], sampler linearSampler [[sampler(3)]]) {
  ColorTarget output;
  float4 sampled = colorMap.sample(linearSampler, input.uv);
  output.color = sampled * params.tint;]=])
  crossgl_add_python_expect_test(
    NAME cglc_build_metal_graphics_fragment_resources_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsFragmentResourcesShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-graphics-fragment-resources.cglb
      -DEXPECTED_MODULE=MetalGraphicsFragmentResourcesShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_GRAPHICS_FRAGMENT_RESOURCES_NATIVE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsFragmentResourcesShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/MetalGraphicsFragmentResourcesShader.metal|artifacts.intermediate=backend/metal/MetalGraphicsFragmentResourcesShader.air|artifacts.nativeBinary=backend/metal/MetalGraphicsFragmentResourcesShader.metallib|artifacts.graphicsAbi=backend/metal/MetalGraphicsFragmentResourcesShader.graphics-abi.json"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsFragmentResourcesShader|nativeBinary=backend/metal/MetalGraphicsFragmentResourcesShader.metallib|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|vertexLayouts.0.entryPoint=vertex_main|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_PATHS=vertexLayouts"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=3|targetResourceBindings=3|vertexLayouts=1|vertexLayouts.0.attributes=2|functionConstants=0|workgroupSizes=0|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=params.sourceType=TintParams|params.metalType=constant TintParams&|params.addressSpace=constant|params.abi=kernelArgument|params.bindingClass=buffer|params.argumentIndex=1|colorMap.sourceType=sampler2D|colorMap.metalType=texture2d<float>|colorMap.addressSpace=texture|colorMap.abi=kernelArgument|colorMap.bindingClass=texture|colorMap.argumentIndex=2|linearSampler.sourceType=sampler|linearSampler.metalType=sampler|linearSampler.addressSpace=sampler|linearSampler.abi=kernelArgument|linearSampler.bindingClass=sampler|linearSampler.argumentIndex=3"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|vertex-shader.kind=stage|fragment-shader.kind=stage|uniform-buffer.kind=resource|sampled-texture.kind=resource|sampler-state.kind=resource|texture-sample.kind=operation|vector-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py
      -DMODE=metal-build)
  set(CROSSGL_METAL_GRAPHICS_STAGE_RESOURCES_NATIVE_SOURCE_SNIPPET [=[struct FrameParams {
  float4 offset;
  float4 tint;
};

struct MeshVertex {
  float3 position [[attribute(0)]];
  float2 texCoord [[attribute(1)]];
};

struct RasterPayload {
  float4 clipPosition [[position]];
  float2 uv;
  float4 tint;
};

struct FragmentPayload {
  float2 uv;
  float4 tint;
};

struct ColorTarget {
  float4 color [[color(0)]];
};

vertex RasterPayload vertex_main(MeshVertex input [[stage_in]], constant FrameParams& frame [[buffer(0)]]) {
  RasterPayload output;
  output.clipPosition = float4(input.position + frame.offset.xyz, 1.0);
  output.uv = input.texCoord;
  output.tint = frame.tint;
  return output;
}

fragment ColorTarget fragment_main(FragmentPayload input [[stage_in]], texture2d<float> colorMap [[texture(2)]], sampler linearSampler [[sampler(3)]]) {
  ColorTarget output;
  float4 sampled = colorMap.sample(linearSampler, input.uv);
  output.color = sampled * input.tint;]=])
  crossgl_add_python_expect_test(
    NAME cglc_build_metal_graphics_stage_resources_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsStageResourcesShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-graphics-stage-resources.cglb
      -DEXPECTED_MODULE=MetalGraphicsStageResourcesShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_GRAPHICS_STAGE_RESOURCES_NATIVE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsStageResourcesShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/MetalGraphicsStageResourcesShader.metal|artifacts.intermediate=backend/metal/MetalGraphicsStageResourcesShader.air|artifacts.nativeBinary=backend/metal/MetalGraphicsStageResourcesShader.metallib|artifacts.graphicsAbi=backend/metal/MetalGraphicsStageResourcesShader.graphics-abi.json"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsStageResourcesShader|nativeBinary=backend/metal/MetalGraphicsStageResourcesShader.metallib|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.stage=vertex|resources.0.kind=uniform|resources.0.name=frame|resources.0.binding=0|resources.1.stage=fragment|resources.1.kind=texture|resources.1.name=colorMap|resources.1.binding=2|resources.2.stage=fragment|resources.2.kind=sampler|resources.2.name=linearSampler|resources.2.binding=3|vertexLayouts.0.entryPoint=vertex_main|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_PATHS=vertexLayouts"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=3|targetResourceBindings=3|vertexLayouts=1|vertexLayouts.0.attributes=2|functionConstants=0|workgroupSizes=0|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=frame.stage=vertex|frame.entryPoint=vertex_main|frame.kind=uniform|frame.sourceType=FrameParams|frame.metalType=constant FrameParams&|frame.addressSpace=constant|frame.abi=kernelArgument|frame.bindingClass=buffer|frame.argumentIndex=0|frame.set=0|frame.binding=0|colorMap.stage=fragment|colorMap.entryPoint=fragment_main|colorMap.kind=texture|colorMap.sourceType=sampler2D|colorMap.metalType=texture2d<float>|colorMap.addressSpace=texture|colorMap.abi=kernelArgument|colorMap.bindingClass=texture|colorMap.argumentIndex=2|colorMap.set=0|colorMap.binding=2|linearSampler.stage=fragment|linearSampler.entryPoint=fragment_main|linearSampler.kind=sampler|linearSampler.sourceType=sampler|linearSampler.metalType=sampler|linearSampler.addressSpace=sampler|linearSampler.abi=kernelArgument|linearSampler.bindingClass=sampler|linearSampler.argumentIndex=3|linearSampler.set=0|linearSampler.binding=3"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|vertex-shader.kind=stage|fragment-shader.kind=stage|uniform-buffer.kind=resource|sampled-texture.kind=resource|sampler-state.kind=resource|texture-sample.kind=operation|vector-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py
      -DMODE=metal-build)
  crossgl_add_python_expect_test(
    NAME cglc_build_metal_graphics_descriptor_array_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-graphics-descriptor-array.cglb
      -DEXPECTED_MODULE=MetalGraphicsDescriptorArrayShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_NATIVE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsDescriptorArrayShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/MetalGraphicsDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/MetalGraphicsDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/MetalGraphicsDescriptorArrayShader.metallib|artifacts.graphicsAbi=backend/metal/MetalGraphicsDescriptorArrayShader.graphics-abi.json"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsDescriptorArrayShader|nativeBinary=backend/metal/MetalGraphicsDescriptorArrayShader.metallib|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|functionConstants.0.name=RESOURCE_COUNT|functionConstants.0.value=2|vertexLayouts.0.entryPoint=vertex_main|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_PATHS=vertexLayouts"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=6|targetResourceBindings=6|vertexLayouts=1|vertexLayouts.0.attributes=3|functionConstants=1|workgroupSizes=0|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=heightMaps.stage=vertex|heightMaps.entryPoint=vertex_main|heightMaps.kind=texture|heightMaps.sourceType=sampler2D[RESOURCE_COUNT]|heightMaps.metalType=array<texture2d<float>, RESOURCE_COUNT>|heightMaps.addressSpace=texture|heightMaps.abi=kernelArgument|heightMaps.bindingClass=texture|heightMaps.argumentIndex=1|heightMaps.set=0|heightMaps.binding=1|heightMaps.arraySize=RESOURCE_COUNT|heightMaps.arrayElementCount=2|heightSamplers.stage=vertex|heightSamplers.entryPoint=vertex_main|heightSamplers.kind=sampler|heightSamplers.sourceType=sampler[RESOURCE_COUNT]|heightSamplers.metalType=array<sampler, RESOURCE_COUNT>|heightSamplers.addressSpace=sampler|heightSamplers.abi=kernelArgument|heightSamplers.bindingClass=sampler|heightSamplers.argumentIndex=3|heightSamplers.arrayElementCount=2|colorMaps.stage=fragment|colorMaps.entryPoint=fragment_main|colorMaps.kind=texture|colorMaps.sourceType=sampler2D[RESOURCE_COUNT]|colorMaps.metalType=array<texture2d<float>, RESOURCE_COUNT>|colorMaps.bindingClass=texture|colorMaps.argumentIndex=1|colorMaps.arrayElementCount=2|linearSamplers.stage=fragment|linearSamplers.kind=sampler|linearSamplers.sourceType=sampler[RESOURCE_COUNT]|linearSamplers.metalType=array<sampler, RESOURCE_COUNT>|linearSamplers.argumentIndex=3|shadowMaps.stage=fragment|shadowMaps.kind=texture|shadowMaps.sourceType=sampler2DShadow[RESOURCE_COUNT]|shadowMaps.metalType=array<depth2d<float>, RESOURCE_COUNT>|shadowMaps.bindingClass=texture|shadowMaps.argumentIndex=6|shadowMaps.arrayElementCount=2|shadowSamplers.stage=fragment|shadowSamplers.kind=sampler|shadowSamplers.sourceType=comparison_sampler[RESOURCE_COUNT]|shadowSamplers.metalType=array<sampler, RESOURCE_COUNT>|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=8|shadowSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|sampler-state.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|depth-compare-format.kind=texture|texture-sample.kind=operation|texture-explicit-lod.kind=operation|texture-shadow-compare-explicit-lod.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py
      -DMODE=metal-build)
  set(CROSSGL_METAL_GRAPHICS_SHADOW_COMPARE_NATIVE_SOURCE_SNIPPET [=[struct MeshVertex {
  float3 position [[attribute(0)]];
  float2 texCoord [[attribute(1)]];
  float shadowDepth [[attribute(2)]];
};

struct RasterPayload {
  float4 clipPosition [[position]];
  float2 uv;
  float shadowDepth;
};

struct FragmentPayload {
  float2 uv;
  float shadowDepth;
};

struct ColorTarget {
  float4 color [[color(0)]];
};

vertex RasterPayload vertex_main(MeshVertex input [[stage_in]]) {
  RasterPayload output;
  output.clipPosition = float4(input.position, 1.0);
  output.uv = input.texCoord;
  output.shadowDepth = input.shadowDepth;
  return output;
}

fragment ColorTarget fragment_main(FragmentPayload input [[stage_in]], depth2d<float> shadowMap [[texture(2)]], sampler shadowCompareSampler [[sampler(5)]]) {
  ColorTarget output;
  float visibility = shadowMap.sample_compare(shadowCompareSampler, input.uv, input.shadowDepth);
  output.color = float4(visibility, visibility, visibility, 1.0);]=])
  crossgl_add_python_expect_test(
    NAME cglc_build_metal_graphics_shadow_compare_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsShadowCompareShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-graphics-shadow-compare.cglb
      -DEXPECTED_MODULE=MetalGraphicsShadowCompareShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_GRAPHICS_SHADOW_COMPARE_NATIVE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsShadowCompareShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/MetalGraphicsShadowCompareShader.metal|artifacts.intermediate=backend/metal/MetalGraphicsShadowCompareShader.air|artifacts.nativeBinary=backend/metal/MetalGraphicsShadowCompareShader.metallib|artifacts.graphicsAbi=backend/metal/MetalGraphicsShadowCompareShader.graphics-abi.json"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsShadowCompareShader|nativeBinary=backend/metal/MetalGraphicsShadowCompareShader.metallib|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.stage=fragment|resources.0.kind=texture|resources.0.name=shadowMap|resources.0.binding=2|resources.1.stage=fragment|resources.1.kind=sampler|resources.1.name=shadowCompareSampler|resources.1.binding=5|vertexLayouts.0.entryPoint=vertex_main|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_PATHS=vertexLayouts"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|vertexLayouts.0.attributes=3|functionConstants=0|workgroupSizes=0|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.stage=fragment|shadowMap.entryPoint=fragment_main|shadowMap.kind=texture|shadowMap.sourceType=sampler2DShadow|shadowMap.metalType=depth2d<float>|shadowMap.addressSpace=texture|shadowMap.abi=kernelArgument|shadowMap.bindingClass=texture|shadowMap.argumentIndex=2|shadowMap.set=0|shadowMap.binding=2|shadowCompareSampler.stage=fragment|shadowCompareSampler.entryPoint=fragment_main|shadowCompareSampler.kind=sampler|shadowCompareSampler.sourceType=comparison_sampler|shadowCompareSampler.metalType=sampler|shadowCompareSampler.addressSpace=sampler|shadowCompareSampler.abi=kernelArgument|shadowCompareSampler.bindingClass=sampler|shadowCompareSampler.argumentIndex=5|shadowCompareSampler.set=0|shadowCompareSampler.binding=5"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py
      -DMODE=metal-build)
  set(CROSSGL_METAL_GRAPHICS_SHADOW_COMPARE_LOD_NATIVE_SOURCE_SNIPPET [=[struct MeshVertex {
  float3 position [[attribute(0)]];
  float2 texCoord [[attribute(1)]];
  float shadowDepth [[attribute(2)]];
};

struct RasterPayload {
  float4 clipPosition [[position]];
  float2 uv;
  float shadowDepth;
};

struct FragmentPayload {
  float2 uv;
  float shadowDepth;
};

struct ColorTarget {
  float4 color [[color(0)]];
};

vertex RasterPayload vertex_main(MeshVertex input [[stage_in]]) {
  RasterPayload output;
  output.clipPosition = float4(input.position, 1.0);
  output.uv = input.texCoord;
  output.shadowDepth = input.shadowDepth;
  return output;
}

fragment ColorTarget fragment_main(FragmentPayload input [[stage_in]], depth2d<float> shadowMap [[texture(2)]], sampler shadowCompareSampler [[sampler(5)]]) {
  ColorTarget output;
  float visibility = shadowMap.sample_compare(shadowCompareSampler, input.uv, input.shadowDepth, level(2.0));
  output.color = float4(visibility, visibility, visibility, 1.0);]=])
  crossgl_add_python_expect_test(
    NAME cglc_build_metal_graphics_shadow_compare_lod_native
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsShadowCompareLodShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-graphics-shadow-compare-lod.cglb
      -DEXPECTED_MODULE=MetalGraphicsShadowCompareLodShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_GRAPHICS_SHADOW_COMPARE_LOD_NATIVE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsShadowCompareLodShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/MetalGraphicsShadowCompareLodShader.metal|artifacts.intermediate=backend/metal/MetalGraphicsShadowCompareLodShader.air|artifacts.nativeBinary=backend/metal/MetalGraphicsShadowCompareLodShader.metallib|artifacts.graphicsAbi=backend/metal/MetalGraphicsShadowCompareLodShader.graphics-abi.json"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalGraphicsShadowCompareLodShader|nativeBinary=backend/metal/MetalGraphicsShadowCompareLodShader.metallib|entryPoints.0.stage=vertex|entryPoints.0.backendName=vertex_main|entryPoints.1.stage=fragment|entryPoints.1.backendName=fragment_main|resources.0.stage=fragment|resources.0.kind=texture|resources.0.name=shadowMap|resources.0.type=sampler2DShadow|resources.0.set=0|resources.0.binding=2|resources.1.stage=fragment|resources.1.kind=sampler|resources.1.name=shadowCompareSampler|resources.1.type=comparison_sampler|resources.1.set=0|resources.1.binding=5|vertexLayouts.0.entryPoint=vertex_main|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_PATHS=vertexLayouts"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=entryPoints=2|resources=2|targetResourceBindings=2|vertexLayouts=1|vertexLayouts.0.attributes=3|functionConstants=0|workgroupSizes=0|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.stage=fragment|shadowMap.entryPoint=fragment_main|shadowMap.kind=texture|shadowMap.sourceType=sampler2DShadow|shadowMap.metalType=depth2d<float>|shadowMap.addressSpace=texture|shadowMap.abi=kernelArgument|shadowMap.bindingClass=texture|shadowMap.argumentIndex=2|shadowMap.set=0|shadowMap.binding=2|shadowCompareSampler.stage=fragment|shadowCompareSampler.entryPoint=fragment_main|shadowCompareSampler.kind=sampler|shadowCompareSampler.sourceType=comparison_sampler|shadowCompareSampler.metalType=sampler|shadowCompareSampler.addressSpace=sampler|shadowCompareSampler.abi=kernelArgument|shadowCompareSampler.bindingClass=sampler|shadowCompareSampler.argumentIndex=5|shadowCompareSampler.set=0|shadowCompareSampler.binding=5"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|vertex-shader.kind=stage|fragment-shader.kind=stage|sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DPACKAGE_INTEGRITY_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_package_integrity.py
      -DMODE=metal-build)
  set(CROSSGL_METAL_RESOURCE_WORKGROUP_SHARED_NATIVE_SOURCE_SNIPPET [=[kernel void compute_main(constant Params& params [[buffer(2)]], device float* values [[buffer(5)]], texture2d<float> shadowMap [[texture(7)]], sampler linearSampler [[sampler(8)]]) {
  threadgroup float tile[TILE_SIZE];]=])
  add_test(NAME cglc_build_metal_resources_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_RESOURCE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-resources.cglb
      -DEXPECTED_MODULE=ResourceShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_RESOURCE_WORKGROUP_SHARED_NATIVE_SOURCE_SNIPPET}"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=ResourceShader|nativeBinary=backend/metal/ResourceShader.metallib|functionConstants.0.name=TILE_SIZE|functionConstants.0.value=16|functionConstants.1.name=SELECTED_TILE|functionConstants.1.value=16|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=16|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=TILE_SIZE|workgroupSizes.0.sourceY=1|workgroupSizes.0.sourceZ=1|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=5|targetResourceBindings=5|functionConstants=2|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=params.abi=kernelArgument|values.abi=kernelArgument|values.storageBufferLayout.layout=metal-device|shadowMap.bindingClass=texture|linearSampler.bindingClass=sampler|tile.sourceType=float[TILE_SIZE]|tile.metalType=threadgroup float|tile.addressSpace=threadgroup|tile.abi=threadgroupLocal|tile.bindingClass=threadgroup|tile.arraySize=TILE_SIZE|tile.arrayElementCount=16|tile.arrayDimensions.0.source=TILE_SIZE|tile.arrayDimensions.0.elementCount=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|uniform-buffer.kind=resource|storage-buffer.kind=resource|sampled-texture.kind=resource|sampler-state.kind=resource|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|texture-sample.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|structured-loop.kind=controlFlow"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_WORKGROUP_SHARED_NATIVE_SOURCE_SNIPPET [=[kernel void compute_main(device float* values [[buffer(0)]]) {
  threadgroup float tile[GROUP_SIZE];
  tile[0] = values[0];
  tile[1] = tile[0] + 1.0;
  values[1] = tile[1];]=])
  add_test(NAME cglc_build_metal_workgroup_shared_memory_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalWorkgroupSharedMemoryShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-workgroup-shared-memory.cglb
      -DEXPECTED_MODULE=MetalWorkgroupSharedMemoryShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_WORKGROUP_SHARED_NATIVE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalWorkgroupSharedMemoryShader|artifacts.backendSource=backend/metal/MetalWorkgroupSharedMemoryShader.metal|artifacts.intermediate=backend/metal/MetalWorkgroupSharedMemoryShader.air|artifacts.nativeBinary=backend/metal/MetalWorkgroupSharedMemoryShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalWorkgroupSharedMemoryShader|nativeBinary=backend/metal/MetalWorkgroupSharedMemoryShader.metallib|functionConstants.0.name=GROUP_SIZE|functionConstants.0.value=4|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=2|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=GROUP_SIZE|workgroupSizes.0.sourceY=2|workgroupSizes.0.sourceZ=1|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.addressSpace=device|values.abi=kernelArgument|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.layout=metal-device|tile.sourceType=float[GROUP_SIZE]|tile.metalType=threadgroup float|tile.addressSpace=threadgroup|tile.abi=threadgroupLocal|tile.bindingClass=threadgroup|tile.arraySize=GROUP_SIZE|tile.arrayElementCount=4|tile.arrayDimensions.0.source=GROUP_SIZE|tile.arrayDimensions.0.elementCount=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|workgroup-shared-memory.kind=resource|fixed-array.kind=layout|storage-buffer-read.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_COMPUTE_INVOCATION_BUILTIN_NATIVE_SOURCE_SNIPPET [=[kernel void compute_main(uint3 gl_GlobalInvocationID [[thread_position_in_grid]], uint3 gl_LocalInvocationID [[thread_position_in_threadgroup]], uint3 gl_WorkGroupID [[threadgroup_position_in_grid]], device uint* values [[buffer(0)]]) {
  uint globalX = gl_GlobalInvocationID.x;
  uint localY = gl_LocalInvocationID.y;
  uint groupZ = gl_WorkGroupID.z;
  values[0] = globalX + localY + groupZ;]=])
  add_test(NAME cglc_build_metal_compute_invocation_builtin_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalComputeInvocationBuiltinShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-compute-invocation-builtin.cglb
      -DEXPECTED_MODULE=MetalComputeInvocationBuiltinShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ uint*
      -DEXPECTED_METAL_BUFFER_NAME=values
      "-DEXPECTED_METAL_STORE_SNIPPET=values[0] = globalX + localY + groupZ;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_COMPUTE_INVOCATION_BUILTIN_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=uint
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalComputeInvocationBuiltinShader|artifacts.backendSource=backend/metal/MetalComputeInvocationBuiltinShader.metal|artifacts.intermediate=backend/metal/MetalComputeInvocationBuiltinShader.air|artifacts.nativeBinary=backend/metal/MetalComputeInvocationBuiltinShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalComputeInvocationBuiltinShader|nativeBinary=backend/metal/MetalComputeInvocationBuiltinShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=2|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=4|workgroupSizes.0.sourceY=2|workgroupSizes.0.sourceZ=1|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=0|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=uint*|values.metalType=device uint*|values.addressSpace=device|values.abi=kernelArgument|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=uint|values.storageBufferLayout.elementSizeBytes=4|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-write.kind=operation|index-access.kind=operation|local-declaration.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_resource_arrays_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_RESOURCE_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-resource-arrays.cglb
      -DEXPECTED_MODULE=ResourceArrayShader
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_while_compute_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_WHILE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-while-compute.cglb
      -DEXPECTED_MODULE=WhileComputeShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      -DEXPECTED_METAL_BUFFER_NAME=values
      "-DEXPECTED_METAL_STORE_SNIPPET=values[i] = values[i] + 1.0;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=for (; i < 4; )"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=WhileComputeShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=structured-loop.kind=controlFlow"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_IF_NATIVE_SOURCE_SNIPPET [=[if (x > 0.0) {
    y = x;
  } else {
    y = -x;
  }]=])
  add_test(NAME cglc_build_metal_if_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_IF_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-if.cglb
      -DEXPECTED_MODULE=IfComputeShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      -DEXPECTED_METAL_BUFFER_NAME=values
      "-DEXPECTED_METAL_STORE_SNIPPET=values[1] = y;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_IF_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=IfComputeShader|nativeBinary=backend/metal/IfComputeShader.metallib"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|structured-selection.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_IF_SCOPED_NATIVE_SOURCE_SNIPPET [=[if (x > 0.0) {
    float scaled = x * 2.0;
    y = scaled;
  } else {
    float scaled = -x;
    y = scaled;
  }]=])
  add_test(NAME cglc_build_metal_if_scoped_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_IF_SCOPED_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-if-scoped.cglb
      -DEXPECTED_MODULE=IfScopedComputeShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      -DEXPECTED_METAL_BUFFER_NAME=values
      "-DEXPECTED_METAL_STORE_SNIPPET=values[1] = y;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_IF_SCOPED_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=IfScopedComputeShader|nativeBinary=backend/metal/IfScopedComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=metal-device|values.storageBufferLayout.arrayStrideBytes=4"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|structured-selection.kind=controlFlow|scalar-arithmetic.kind=operation|scalar-comparison.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_NESTED_IF_NATIVE_SOURCE_SNIPPET [=[if (x > 0.0) {
    float scaled = x * 2.0;
    if (scaled > 3.0) {
      y = scaled;
    } else {
      y = x;
    }
  } else {
    y = -x;
  }]=])
  add_test(NAME cglc_build_metal_nested_if_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_NESTED_IF_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-nested-if.cglb
      -DEXPECTED_MODULE=NestedIfComputeShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      -DEXPECTED_METAL_BUFFER_NAME=values
      "-DEXPECTED_METAL_STORE_SNIPPET=values[1] = y;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_NESTED_IF_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=NestedIfComputeShader|nativeBinary=backend/metal/NestedIfComputeShader.metallib"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|structured-selection.kind=controlFlow|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_IF_RETURN_NATIVE_SOURCE_SNIPPET [=[if (x > 0.0) {
    values[1] = x;
    return;
  } else {
    values[1] = -x;
    return;
  }]=])
  add_test(NAME cglc_build_metal_if_return_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_IF_RETURN_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-if-return.cglb
      -DEXPECTED_MODULE=IfReturnComputeShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      -DEXPECTED_METAL_BUFFER_NAME=values
      "-DEXPECTED_METAL_STORE_SNIPPET=values[1] = x;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_IF_RETURN_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=IfReturnComputeShader|nativeBinary=backend/metal/IfReturnComputeShader.metallib"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|structured-selection.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_read_modify_write_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_READ_MODIFY_WRITE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-read-modify-write.cglb
      -DEXPECTED_MODULE=ReadModifyWriteComputeShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      -DEXPECTED_METAL_BUFFER_NAME=values
      "-DEXPECTED_METAL_STORE_SNIPPET=values[0] = values[0] + 1.0;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=values[0] = values[0] + 1.0;"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=ReadModifyWriteComputeShader|nativeBinary=backend/metal/ReadModifyWriteComputeShader.metallib"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_buffer_dynamic_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalStorageBufferDynamicDescriptorArrayShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-buffer-dynamic-descriptor-array.cglb
      -DEXPECTED_MODULE=MetalStorageBufferDynamicDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cgl_select_compute_values(descriptor, values_0, values_1)[0]"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageBufferDynamicDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*[2]|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.arrayElementCount=2|values.storageBufferLayout.layout=metal-device"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_buffer_nonuniform_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalStorageBufferNonUniformDescriptorArrayShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-buffer-nonuniform-descriptor-array.cglb
      -DEXPECTED_MODULE=MetalStorageBufferNonUniformDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cgl_select_compute_values(descriptor, values_0, values_1)[0]"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageBufferNonUniformDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*[2]|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.arrayElementCount=2|values.storageBufferLayout.layout=metal-device|descriptors.sourceType=int*|descriptors.metalType=device int*|descriptors.bindingClass=buffer|descriptors.argumentIndex=4|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-storage-buffer-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_runtime_tail_folded_zero_block_index_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalRuntimeTailFoldedZeroBlockIndexShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-runtime-tail-folded-zero-block-index.cglb
      -DEXPECTED_MODULE=MetalRuntimeTailFoldedZeroBlockIndexShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=float4 first = (reinterpret_cast<device float4*>(reinterpret_cast<device char*>(payloads) + 16))[0];"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalRuntimeTailFoldedZeroBlockIndexShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=payloads.sourceType=RuntimePayload*|payloads.metalType=device RuntimePayload*|payloads.bindingClass=buffer|payloads.argumentIndex=0|payloads.storageBufferLayout.elementType=RuntimePayload|payloads.storageBufferLayout.layout=metal-device|outputs.sourceType=vec4*|outputs.metalType=device float4*|outputs.bindingClass=buffer|outputs.argumentIndex=1|outputs.storageBufferLayout.elementType=vec4|outputs.storageBufferLayout.layout=metal-device"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_FUNCTION_PARAMETER_ARRAY_NATIVE_SOURCE_SNIPPET [=[float forwardWeight(array<float, COUNT> weights) {
  return readWeight(weights);
}

kernel void compute_main(device Particle* particles [[buffer(0)]]) {
  float value = forwardWeight(particles[0].weights);
  particles[1].weights[0] = value;
  return;
}]=])
  add_test(NAME cglc_build_metal_function_parameter_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalFunctionParameterArrayShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-function-parameter-array.cglb
      -DEXPECTED_MODULE=MetalFunctionParameterArrayShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ Particle*
      -DEXPECTED_METAL_BUFFER_NAME=particles
      -DEXPECTED_METAL_STRUCT=Particle
      "-DEXPECTED_METAL_FIELD_SNIPPET=array<float, COUNT> weights;"
      "-DEXPECTED_METAL_STORE_SNIPPET=particles[1].weights[0] = value;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_FUNCTION_PARAMETER_ARRAY_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=8
      -DEXPECTED_STRUCT_FIELD=weights
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=2
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalFunctionParameterArrayShader|artifacts.backendSource=backend/metal/MetalFunctionParameterArrayShader.metal|artifacts.intermediate=backend/metal/MetalFunctionParameterArrayShader.air|artifacts.nativeBinary=backend/metal/MetalFunctionParameterArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalFunctionParameterArrayShader|nativeBinary=backend/metal/MetalFunctionParameterArrayShader.metallib|functionConstants.0.name=COUNT|functionConstants.0.value=2|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.metalType=device Particle*|particles.addressSpace=device|particles.bindingClass=buffer|particles.argumentIndex=0|particles.set=0|particles.binding=0|particles.abi=kernelArgument|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.elementSizeBytes=8|particles.storageBufferLayout.arrayStrideBytes=8|particles.storageBufferLayout.layout=metal-device|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.type=float[COUNT]|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.0.arrayStrideBytes=4|particles.storageBufferLayout.fields.0.arrayDimensions.0.source=COUNT|particles.storageBufferLayout.fields.0.arrayDimensions.0.elementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|fixed-array.kind=layout|fixed-array-field.kind=layout|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_TRANSITIVE_HELPER_RESOURCE_SOURCE_SNIPPET [=[float writeResult(float value, device float* values) {
  values[0] = value;
  return value;
}

float forwardResult(float value, device float* values) {
  return writeResult(value + 1.0, values);
}

kernel void compute_main(device float* values [[buffer(0)]]) {
  float base = values[1];
  float result = forwardResult(base, values);
  values[2] = result;]=])
  add_test(NAME cglc_build_metal_transitive_helper_resource_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalTransitiveHelperResourceShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-transitive-helper-resource.cglb
      -DEXPECTED_MODULE=MetalTransitiveHelperResourceShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      -DEXPECTED_METAL_BUFFER_NAME=values
      "-DEXPECTED_METAL_STORE_SNIPPET=values[2] = result;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_TRANSITIVE_HELPER_RESOURCE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalTransitiveHelperResourceShader|nativeBinary=backend/metal/MetalTransitiveHelperResourceShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.addressSpace=device|values.bindingClass=buffer|values.argumentIndex=0|values.set=0|values.binding=0|values.abi=kernelArgument|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_FUNCTION_PARAMETER_ARRAY_WRITE_NATIVE_SOURCE_SNIPPET [=[float rewriteWeight(array<float, COUNT> weights) {
  weights[0] = 1.0;
  return weights[0];
}

kernel void compute_main(device Particle* particles [[buffer(0)]]) {
  float value = rewriteWeight(particles[0].weights);
  particles[1].weights[0] = value;
  return;
}]=])
  add_test(NAME cglc_build_metal_function_parameter_array_write_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalFunctionParameterArrayWriteUnsupportedShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-function-parameter-array-write.cglb
      -DEXPECTED_MODULE=MetalFunctionParameterArrayWriteUnsupportedShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ Particle*
      -DEXPECTED_METAL_BUFFER_NAME=particles
      -DEXPECTED_METAL_STRUCT=Particle
      "-DEXPECTED_METAL_FIELD_SNIPPET=array<float, COUNT> weights;"
      "-DEXPECTED_METAL_STORE_SNIPPET=particles[1].weights[0] = value;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_FUNCTION_PARAMETER_ARRAY_WRITE_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=8
      -DEXPECTED_STRUCT_FIELD=weights
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=2
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalFunctionParameterArrayWriteUnsupportedShader|artifacts.backendSource=backend/metal/MetalFunctionParameterArrayWriteUnsupportedShader.metal|artifacts.intermediate=backend/metal/MetalFunctionParameterArrayWriteUnsupportedShader.air|artifacts.nativeBinary=backend/metal/MetalFunctionParameterArrayWriteUnsupportedShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalFunctionParameterArrayWriteUnsupportedShader|nativeBinary=backend/metal/MetalFunctionParameterArrayWriteUnsupportedShader.metallib|functionConstants.0.name=COUNT|functionConstants.0.value=2|resources.0.name=particles|resources.0.kind=buffer|resources.0.type=Particle*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.metalType=device Particle*|particles.addressSpace=device|particles.bindingClass=buffer|particles.argumentIndex=0|particles.set=0|particles.binding=0|particles.abi=kernelArgument|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.elementSizeBytes=8|particles.storageBufferLayout.arrayStrideBytes=8|particles.storageBufferLayout.layout=metal-device|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.type=float[COUNT]|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.0.arrayStrideBytes=4|particles.storageBufferLayout.fields.0.arrayDimensions.0.source=COUNT|particles.storageBufferLayout.fields.0.arrayDimensions.0.elementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|fixed-array.kind=layout|fixed-array-field.kind=layout|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_NESTED_FUNCTION_PARAMETER_ARRAY_WRITE_NATIVE_SOURCE_SNIPPET [=[float rewriteGrid(array<array<float, COLS>, ROWS> grid) {
  grid[1][2] = grid[0][0] + 1.0;
  return grid[1][2];
}

kernel void compute_main(device float* values [[buffer(0)]]) {
  array<array<float, COLS>, ROWS> localGrid;
  localGrid[0][0] = values[0];
  float selected = rewriteGrid(localGrid);
  values[1] = selected;
  return;
}]=])
  add_test(NAME cglc_build_metal_nested_function_parameter_array_write_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalNestedFunctionParameterArrayWriteUnsupportedShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-nested-function-parameter-array-write.cglb
      -DEXPECTED_MODULE=MetalNestedFunctionParameterArrayWriteUnsupportedShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      -DEXPECTED_METAL_BUFFER_NAME=values
      "-DEXPECTED_METAL_STORE_SNIPPET=values[1] = selected;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_NESTED_FUNCTION_PARAMETER_ARRAY_WRITE_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalNestedFunctionParameterArrayWriteUnsupportedShader|artifacts.backendSource=backend/metal/MetalNestedFunctionParameterArrayWriteUnsupportedShader.metal|artifacts.intermediate=backend/metal/MetalNestedFunctionParameterArrayWriteUnsupportedShader.air|artifacts.nativeBinary=backend/metal/MetalNestedFunctionParameterArrayWriteUnsupportedShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalNestedFunctionParameterArrayWriteUnsupportedShader|nativeBinary=backend/metal/MetalNestedFunctionParameterArrayWriteUnsupportedShader.metallib|functionConstants.0.name=ROWS|functionConstants.0.value=2|functionConstants.1.name=COLS|functionConstants.1.value=3|resources.0.name=values|resources.0.kind=buffer|resources.0.type=float*|resources.0.binding=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=2|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.addressSpace=device|values.bindingClass=buffer|values.argumentIndex=0|values.set=0|values.binding=0|values.abi=kernelArgument|values.storageBufferLayout.elementType=float|values.storageBufferLayout.elementSizeBytes=4|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|fixed-array.kind=layout|index-access.kind=operation|local-declaration.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_LOCAL_ARRAY_ARGUMENT_NATIVE_SOURCE_SNIPPET [=[array<float, COUNT> localWeights;
  localWeights[0] = particles[0].weights[0];
  localWeights[1] = particles[0].weights[1];
  localWeights[2] = particles[0].weights[2];
  localWeights[3] = particles[0].weights[3];
  particles[1].result = forwardWeights(localWeights);]=])
  add_test(NAME cglc_build_metal_local_array_argument_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalLocalArrayArgumentShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-local-array-argument.cglb
      -DEXPECTED_MODULE=MetalLocalArrayArgumentShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ Particle*
      -DEXPECTED_METAL_BUFFER_NAME=particles
      -DEXPECTED_METAL_STRUCT=Particle
      "-DEXPECTED_METAL_FIELD_SNIPPET=array<float, COUNT> weights;"
      "-DEXPECTED_METAL_STORE_SNIPPET=particles[1].result = forwardWeights(localWeights);"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_LOCAL_ARRAY_ARGUMENT_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=20
      -DEXPECTED_STRUCT_FIELD=weights
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=4
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalLocalArrayArgumentShader|artifacts.backendSource=backend/metal/MetalLocalArrayArgumentShader.metal|artifacts.intermediate=backend/metal/MetalLocalArrayArgumentShader.air|artifacts.nativeBinary=backend/metal/MetalLocalArrayArgumentShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalLocalArrayArgumentShader|nativeBinary=backend/metal/MetalLocalArrayArgumentShader.metallib|functionConstants.0.name=COUNT|functionConstants.0.value=4|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.metalType=device Particle*|particles.addressSpace=device|particles.bindingClass=buffer|particles.argumentIndex=0|particles.set=0|particles.binding=0|particles.abi=kernelArgument|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.elementSizeBytes=20|particles.storageBufferLayout.arrayStrideBytes=20|particles.storageBufferLayout.layout=metal-device|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.type=float[COUNT]|particles.storageBufferLayout.fields.0.arrayElementCount=4|particles.storageBufferLayout.fields.0.arrayStrideBytes=4|particles.storageBufferLayout.fields.0.arrayDimensions.0.source=COUNT|particles.storageBufferLayout.fields.0.arrayDimensions.0.elementCount=4|particles.storageBufferLayout.fields.1.name=result|particles.storageBufferLayout.fields.1.offsetBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|fixed-array.kind=layout|fixed-array-field.kind=layout|scalar-arithmetic.kind=operation|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_LOCAL_ARRAY_DYNAMIC_VECTOR_NATIVE_SOURCE_SNIPPET [=[array<float4, COUNT> localValues;
  localValues[0] = outputs[0];
  localValues[1] = outputs[1];
  localValues[2] = outputs[2];
  int index = indices[0];
  outputs[3] = readValue(localValues, index);]=])
  add_test(NAME cglc_build_metal_local_array_dynamic_vector_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalLocalArrayDynamicVectorShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-local-array-dynamic-vector.cglb
      -DEXPECTED_MODULE=MetalLocalArrayDynamicVectorShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float4*
      -DEXPECTED_METAL_BUFFER_NAME=outputs
      "-DEXPECTED_METAL_STORE_SNIPPET=outputs[3] = readValue(localValues, index);"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_LOCAL_ARRAY_DYNAMIC_VECTOR_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalLocalArrayDynamicVectorShader|artifacts.backendSource=backend/metal/MetalLocalArrayDynamicVectorShader.metal|artifacts.intermediate=backend/metal/MetalLocalArrayDynamicVectorShader.air|artifacts.nativeBinary=backend/metal/MetalLocalArrayDynamicVectorShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalLocalArrayDynamicVectorShader|nativeBinary=backend/metal/MetalLocalArrayDynamicVectorShader.metallib|functionConstants.0.name=COUNT|functionConstants.0.value=3|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=outputs.sourceType=vec4*|outputs.metalType=device float4*|outputs.addressSpace=device|outputs.bindingClass=buffer|outputs.argumentIndex=0|outputs.set=0|outputs.binding=0|outputs.abi=kernelArgument|outputs.storageBufferLayout.elementType=vec4|outputs.storageBufferLayout.elementSizeBytes=16|outputs.storageBufferLayout.arrayStrideBytes=16|outputs.storageBufferLayout.layout=metal-device|indices.sourceType=int*|indices.metalType=device int*|indices.addressSpace=device|indices.bindingClass=buffer|indices.argumentIndex=1|indices.set=0|indices.binding=1|indices.abi=kernelArgument|indices.storageBufferLayout.elementType=int|indices.storageBufferLayout.elementSizeBytes=4|indices.storageBufferLayout.arrayStrideBytes=4|indices.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_DYNAMIC_NESTED_FUNCTION_PARAMETER_ARRAY_READ_NATIVE_SOURCE_SNIPPET [=[array<array<float, COLS>, ROWS> grid;
  grid[0][0] = values[0];
  grid[1][2] = values[1];
  int row = int(values[0]);
  int col = int(values[1]);
  float selected = readGrid(grid, row, col);
  values[2] = selected;]=])
  add_test(NAME cglc_build_metal_dynamic_nested_function_parameter_array_read_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalDynamicNestedFunctionParameterArrayReadUnsupportedShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-dynamic-nested-function-parameter-array-read.cglb
      -DEXPECTED_MODULE=MetalDynamicNestedFunctionParameterArrayReadUnsupportedShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      -DEXPECTED_METAL_BUFFER_NAME=values
      "-DEXPECTED_METAL_STORE_SNIPPET=values[2] = selected;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_DYNAMIC_NESTED_FUNCTION_PARAMETER_ARRAY_READ_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalDynamicNestedFunctionParameterArrayReadUnsupportedShader|artifacts.backendSource=backend/metal/MetalDynamicNestedFunctionParameterArrayReadUnsupportedShader.metal|artifacts.intermediate=backend/metal/MetalDynamicNestedFunctionParameterArrayReadUnsupportedShader.air|artifacts.nativeBinary=backend/metal/MetalDynamicNestedFunctionParameterArrayReadUnsupportedShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalDynamicNestedFunctionParameterArrayReadUnsupportedShader|nativeBinary=backend/metal/MetalDynamicNestedFunctionParameterArrayReadUnsupportedShader.metallib|functionConstants.0.name=ROWS|functionConstants.0.value=2|functionConstants.1.name=COLS|functionConstants.1.value=3|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=2|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.addressSpace=device|values.bindingClass=buffer|values.argumentIndex=0|values.set=0|values.binding=0|values.abi=kernelArgument|values.storageBufferLayout.elementType=float|values.storageBufferLayout.elementSizeBytes=4|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|index-access.kind=operation|local-declaration.kind=operation|scalar-constructor.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_DYNAMIC_NESTED_VECTOR_FUNCTION_PARAMETER_ARRAY_READ_NATIVE_SOURCE_SNIPPET [=[array<array<float4, COLS>, ROWS> grid;
  grid[0][0] = values[0];
  grid[1][2] = values[1];
  int row = indices[0];
  int col = indices[1];
  values[2] = readGrid(grid, row, col);]=])
  add_test(NAME cglc_build_metal_dynamic_nested_vector_function_parameter_array_read_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalDynamicNestedVectorFunctionParameterArrayReadShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-dynamic-nested-vector-function-parameter-array-read.cglb
      -DEXPECTED_MODULE=MetalDynamicNestedVectorFunctionParameterArrayReadShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float4*
      -DEXPECTED_METAL_BUFFER_NAME=values
      "-DEXPECTED_METAL_STORE_SNIPPET=values[2] = readGrid(grid, row, col);"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_DYNAMIC_NESTED_VECTOR_FUNCTION_PARAMETER_ARRAY_READ_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalDynamicNestedVectorFunctionParameterArrayReadShader|artifacts.backendSource=backend/metal/MetalDynamicNestedVectorFunctionParameterArrayReadShader.metal|artifacts.intermediate=backend/metal/MetalDynamicNestedVectorFunctionParameterArrayReadShader.air|artifacts.nativeBinary=backend/metal/MetalDynamicNestedVectorFunctionParameterArrayReadShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalDynamicNestedVectorFunctionParameterArrayReadShader|nativeBinary=backend/metal/MetalDynamicNestedVectorFunctionParameterArrayReadShader.metallib|functionConstants.0.name=ROWS|functionConstants.0.value=2|functionConstants.1.name=COLS|functionConstants.1.value=3|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1|workgroupSizes.0.sourceX=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|functionConstants=2|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.metalType=device float4*|values.addressSpace=device|values.bindingClass=buffer|values.argumentIndex=0|values.set=0|values.binding=0|values.abi=kernelArgument|values.storageBufferLayout.elementType=vec4|values.storageBufferLayout.elementSizeBytes=16|values.storageBufferLayout.arrayStrideBytes=16|values.storageBufferLayout.layout=metal-device|indices.sourceType=int*|indices.metalType=device int*|indices.addressSpace=device|indices.bindingClass=buffer|indices.argumentIndex=1|indices.set=0|indices.binding=1|indices.abi=kernelArgument|indices.storageBufferLayout.elementType=int|indices.storageBufferLayout.elementSizeBytes=4|indices.storageBufferLayout.arrayStrideBytes=4|indices.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|vector-storage-buffer.kind=layout|index-access.kind=operation|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_folded_array_helper_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalFoldedArrayHelperShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-folded-array-helper.cglb
      -DEXPECTED_MODULE=MetalFoldedArrayHelperShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=float forwardFolded(array<array<float, COLS>, ROWS> values)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalFoldedArrayHelperShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=outputs.sourceType=float*|outputs.metalType=device float*|outputs.bindingClass=buffer|outputs.argumentIndex=0|outputs.storageBufferLayout.layout=metal-device"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_nested_vector_array_helper_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalNestedVectorArrayHelperShader.cgl
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-nested-vector-array-helper.cglb
      -DEXPECTED_MODULE=MetalNestedVectorArrayHelperShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=float4 forwardVector(array<array<float4, COLS>, ROWS> values)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalNestedVectorArrayHelperShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=outputs.sourceType=vec4*|outputs.metalType=device float4*|outputs.bindingClass=buffer|outputs.argumentIndex=0|outputs.storageBufferLayout.layout=metal-device"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=array<texture2d<float>, TEXTURE_COUNT> colorMaps [[texture(2)]]"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureDescriptorArrayShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/TextureDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/TextureDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/TextureDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureDescriptorArrayShader|nativeBinary=backend/metal/TextureDescriptorArrayShader.metallib|manualTextureCompareKernelSummary.totalCount=0|functionConstants.0.name=TEXTURE_COUNT|functionConstants.0.value=2|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.sourceType=sampler2D[TEXTURE_COUNT]|colorMaps.metalType=array<texture2d<float>, TEXTURE_COUNT>|colorMaps.bindingClass=texture|colorMaps.argumentIndex=2|colorMaps.arraySize=TEXTURE_COUNT|colorMaps.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-descriptor-array.cglb
      -DEXPECTED_MODULE=SamplerDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=array<sampler, SAMPLER_COUNT> linearSamplers [[sampler(5)]]"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerDescriptorArrayShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/SamplerDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/SamplerDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/SamplerDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerDescriptorArrayShader|nativeBinary=backend/metal/SamplerDescriptorArrayShader.metallib|manualTextureCompareKernelSummary.totalCount=0|functionConstants.0.name=SAMPLER_COUNT|functionConstants.0.value=2|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=linearSamplers.sourceType=sampler[SAMPLER_COUNT]|linearSamplers.metalType=array<sampler, SAMPLER_COUNT>|linearSamplers.bindingClass=sampler|linearSamplers.argumentIndex=5|linearSamplers.arraySize=SAMPLER_COUNT|linearSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|sampler-state.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_only_descriptor_array_sample_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-only-descriptor-array-sample.cglb
      -DEXPECTED_MODULE=TextureOnlyDescriptorArraySampleShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=float4 color = colorMaps[1].sample(linearSampler, float2(0.5, 0.5), level(0.0));"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureOnlyDescriptorArraySampleShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/TextureOnlyDescriptorArraySampleShader.metal|artifacts.intermediate=backend/metal/TextureOnlyDescriptorArraySampleShader.air|artifacts.nativeBinary=backend/metal/TextureOnlyDescriptorArraySampleShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureOnlyDescriptorArraySampleShader|nativeBinary=backend/metal/TextureOnlyDescriptorArraySampleShader.metallib|manualTextureCompareKernelSummary.totalCount=0|functionConstants.0.name=TEXTURE_COUNT|functionConstants.0.value=2|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.sourceType=sampler2D[TEXTURE_COUNT]|colorMaps.metalType=array<texture2d<float>, TEXTURE_COUNT>|colorMaps.bindingClass=texture|colorMaps.argumentIndex=2|colorMaps.arraySize=TEXTURE_COUNT|colorMaps.arrayElementCount=2|linearSampler.sourceType=sampler|linearSampler.metalType=sampler|linearSampler.bindingClass=sampler|linearSampler.argumentIndex=5|values.sourceType=vec4*|values.metalType=device float4*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|sampled-texture.kind=resource|sampler-state.kind=resource|descriptor-array.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|index-access.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_only_descriptor_array_sample_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-only-descriptor-array-sample.cglb
      -DEXPECTED_MODULE=SamplerOnlyDescriptorArraySampleShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=float4 color = colorMap.sample(linearSamplers[1], float2(0.5, 0.5), level(0.0));"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerOnlyDescriptorArraySampleShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/SamplerOnlyDescriptorArraySampleShader.metal|artifacts.intermediate=backend/metal/SamplerOnlyDescriptorArraySampleShader.air|artifacts.nativeBinary=backend/metal/SamplerOnlyDescriptorArraySampleShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerOnlyDescriptorArraySampleShader|nativeBinary=backend/metal/SamplerOnlyDescriptorArraySampleShader.metallib|manualTextureCompareKernelSummary.totalCount=0|functionConstants.0.name=SAMPLER_COUNT|functionConstants.0.value=2|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMap.sourceType=sampler2D|colorMap.metalType=texture2d<float>|colorMap.bindingClass=texture|colorMap.argumentIndex=2|linearSamplers.sourceType=sampler[SAMPLER_COUNT]|linearSamplers.metalType=array<sampler, SAMPLER_COUNT>|linearSamplers.bindingClass=sampler|linearSamplers.argumentIndex=5|linearSamplers.arraySize=SAMPLER_COUNT|linearSamplers.arrayElementCount=2|values.sourceType=vec4*|values.metalType=device float4*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|sampled-texture.kind=resource|sampler-state.kind=resource|descriptor-array.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|index-access.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=float visibility = shadowMaps[1].sample_compare(shadowSamplers[0], float2(0.5, 0.5), 0.25);"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCompareDescriptorArrayShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/TextureCompareDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/TextureCompareDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/TextureCompareDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCompareDescriptorArrayShader|nativeBinary=backend/metal/TextureCompareDescriptorArrayShader.metallib|manualTextureCompareKernelSummary.totalCount=0|functionConstants.0.name=SHADOW_COUNT|functionConstants.0.value=2|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|functionConstants=1|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.layout=metal-device|shadowMaps.sourceType=sampler2DShadow[SHADOW_COUNT]|shadowMaps.metalType=array<depth2d<float>, SHADOW_COUNT>|shadowMaps.bindingClass=texture|shadowMaps.argumentIndex=2|shadowMaps.arraySize=SHADOW_COUNT|shadowMaps.arrayElementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.metalType=array<sampler, 2>|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=5|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|sampled-texture.kind=resource|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_compare_descriptor_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-compare-descriptor-array-lod.cglb
      -DEXPECTED_MODULE=TextureCompareDescriptorArrayLodShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=float visibility = shadowMaps[1].sample_compare(shadowSamplers[0], float2(0.5, 0.5), 0.25, level(2.0));"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCompareDescriptorArrayLodShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/TextureCompareDescriptorArrayLodShader.metal|artifacts.intermediate=backend/metal/TextureCompareDescriptorArrayLodShader.air|artifacts.nativeBinary=backend/metal/TextureCompareDescriptorArrayLodShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCompareDescriptorArrayLodShader|nativeBinary=backend/metal/TextureCompareDescriptorArrayLodShader.metallib|manualTextureCompareKernelSummary.totalCount=0|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|functionConstants=0|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.layout=metal-device|shadowMaps.sourceType=sampler2DShadow[2]|shadowMaps.metalType=array<depth2d<float>, 2>|shadowMaps.bindingClass=texture|shadowMaps.argumentIndex=2|shadowMaps.arraySize=2|shadowMaps.arrayElementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.metalType=array<sampler, 2>|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=5|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|sampled-texture.kind=resource|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_only_nonuniform_descriptor_array_sample_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-only-nonuniform-descriptor-array-sample.cglb
      -DEXPECTED_MODULE=TextureOnlyNonUniformDescriptorArraySampleShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=colorMaps[descriptor].sample(linearSampler"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureOnlyNonUniformDescriptorArraySampleShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.sourceType=sampler2D[TEXTURE_COUNT]|colorMaps.metalType=array<texture2d<float>, TEXTURE_COUNT>|colorMaps.bindingClass=texture|colorMaps.argumentIndex=2|colorMaps.arraySize=TEXTURE_COUNT|colorMaps.arrayElementCount=2|linearSampler.sourceType=sampler|linearSampler.metalType=sampler|linearSampler.bindingClass=sampler|linearSampler.argumentIndex=5|values.storageBufferLayout.layout=metal-device|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_only_nonuniform_descriptor_array_sample_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_DESCRIPTOR_ARRAY_SAMPLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-only-nonuniform-descriptor-array-sample.cglb
      -DEXPECTED_MODULE=SamplerOnlyNonUniformDescriptorArraySampleShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=colorMap.sample(linearSamplers[descriptor]"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerOnlyNonUniformDescriptorArraySampleShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMap.sourceType=sampler2D|colorMap.metalType=texture2d<float>|colorMap.bindingClass=texture|colorMap.argumentIndex=2|linearSamplers.sourceType=sampler[SAMPLER_COUNT]|linearSamplers.metalType=array<sampler, SAMPLER_COUNT>|linearSamplers.bindingClass=sampler|linearSamplers.argumentIndex=5|linearSamplers.arraySize=SAMPLER_COUNT|linearSamplers.arrayElementCount=2|values.storageBufferLayout.layout=metal-device|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_compare_nonuniform_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-compare-nonuniform-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCompareNonUniformDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMaps[descriptor].sample_compare(shadowSamplers[descriptor]"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCompareNonUniformDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.metalType=array<depth2d<float>, SHADOW_COUNT>|shadowMaps.bindingClass=texture|shadowMaps.arrayElementCount=2|shadowSamplers.metalType=array<sampler, SHADOW_COUNT>|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_compare_nonuniform_descriptor_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_NONUNIFORM_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-compare-nonuniform-descriptor-array-lod.cglb
      -DEXPECTED_MODULE=TextureCompareNonUniformDescriptorArrayLodShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMaps[descriptor].sample_compare(shadowSamplers[descriptor], float2(0.5, 0.5), 0.25, level(2.0))"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCompareNonUniformDescriptorArrayLodShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.metalType=array<depth2d<float>, SHADOW_COUNT>|shadowMaps.bindingClass=texture|shadowMaps.arrayElementCount=2|shadowSamplers.metalType=array<sampler, SHADOW_COUNT>|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_compare_lod_manual_nonuniform_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-compare-lod-manual-nonuniform-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCompareLodManualNonUniformDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowAtlases[descriptor].sample(rawShadowSamplers[descriptor], float2(0.25, 0.5), uint(1.0), level(2.0)), 0.33, CGL_COMPARE_LESS_EQUAL)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCompareLodManualNonUniformDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.metalType=array<depth2d_array<float>, SHADOW_COUNT>|shadowAtlases.bindingClass=texture|shadowAtlases.arrayElementCount=2|rawShadowSamplers.metalType=array<sampler, RAW_SAMPLER_COUNT>|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_only_nonuniform_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-only-nonuniform-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureOnlyNonUniformCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMaps[descriptor].sample_compare(shadowSampler"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureOnlyNonUniformCompareDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.metalType=array<depth2d<float>, SHADOW_COUNT>|shadowMaps.bindingClass=texture|shadowMaps.arrayElementCount=2|shadowSampler.metalType=sampler|shadowSampler.bindingClass=sampler|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_only_nonuniform_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-only-nonuniform-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=SamplerOnlyNonUniformCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMap.sample_compare(shadowSamplers[descriptor]"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerOnlyNonUniformCompareDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.metalType=depth2d<float>|shadowMap.bindingClass=texture|shadowSamplers.metalType=array<sampler, SAMPLER_COUNT>|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_only_nonuniform_compare_descriptor_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-only-nonuniform-compare-descriptor-array-lod.cglb
      -DEXPECTED_MODULE=TextureOnlyNonUniformCompareDescriptorArrayLodShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMaps[descriptor].sample_compare(shadowSampler, float2(0.5, 0.5), 0.25, level(2.0))"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureOnlyNonUniformCompareDescriptorArrayLodShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.metalType=array<depth2d<float>, SHADOW_COUNT>|shadowMaps.bindingClass=texture|shadowMaps.arrayElementCount=2|shadowSampler.metalType=sampler|shadowSampler.bindingClass=sampler|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_only_nonuniform_compare_descriptor_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-only-nonuniform-compare-descriptor-array-lod.cglb
      -DEXPECTED_MODULE=SamplerOnlyNonUniformCompareDescriptorArrayLodShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMap.sample_compare(shadowSamplers[descriptor], float2(0.5, 0.5), 0.25, level(2.0))"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerOnlyNonUniformCompareDescriptorArrayLodShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.metalType=depth2d<float>|shadowMap.bindingClass=texture|shadowSamplers.metalType=array<sampler, SAMPLER_COUNT>|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_only_nonuniform_compare_lod_manual_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-only-nonuniform-compare-lod-manual-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureOnlyNonUniformCompareLodManualDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowAtlases[descriptor].sample(rawShadowSampler, float2(0.25, 0.5), uint(1.0), level(2.0)), 0.33, CGL_COMPARE_LESS_EQUAL)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureOnlyNonUniformCompareLodManualDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.metalType=array<depth2d_array<float>, SHADOW_COUNT>|shadowAtlases.bindingClass=texture|shadowAtlases.arrayElementCount=2|rawShadowSampler.metalType=sampler|rawShadowSampler.bindingClass=sampler|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_only_nonuniform_compare_lod_manual_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-only-nonuniform-compare-lod-manual-descriptor-array.cglb
      -DEXPECTED_MODULE=SamplerOnlyNonUniformCompareLodManualDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowAtlas.sample(rawShadowSamplers[descriptor], float2(0.25, 0.5), uint(1.0), level(2.0)), 0.33, CGL_COMPARE_LESS_EQUAL)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerOnlyNonUniformCompareLodManualDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlas.metalType=depth2d_array<float>|shadowAtlas.bindingClass=texture|rawShadowSamplers.metalType=array<sampler, RAW_SAMPLER_COUNT>|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_cube_family_compare_lod_manual_nonuniform_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_COMPARE_LOD_MANUAL_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-cube-family-compare-lod-manual-nonuniform-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowCubeArrays[descriptor].sample(rawShadowSamplers[descriptor], float3(0.0, 1.0, 0.0), uint(2.0), level(3.0)), 0.75, CGL_COMPARE_GREATER)"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader|nativeBinary=backend/metal/TextureCubeFamilyCompareLodManualNonUniformDescriptorArrayShader.metallib|manualTextureCompareKernelSummary.totalCount=0|functionConstants.0.name=SHADOW_COUNT|functionConstants.0.value=2|functionConstants.1.name=RAW_SAMPLER_COUNT|functionConstants.1.value=2|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=5|targetResourceBindings=5|functionConstants=2|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.layout=metal-device|descriptors.sourceType=int*|descriptors.metalType=device int*|descriptors.bindingClass=buffer|descriptors.argumentIndex=1|descriptors.storageBufferLayout.layout=metal-device|shadowCubes.sourceType=samplerCubeShadow[SHADOW_COUNT]|shadowCubes.metalType=array<depthcube<float>, SHADOW_COUNT>|shadowCubes.bindingClass=texture|shadowCubes.argumentIndex=2|shadowCubes.arraySize=SHADOW_COUNT|shadowCubes.arrayElementCount=2|shadowCubeArrays.sourceType=samplerCubeArrayShadow[SHADOW_COUNT]|shadowCubeArrays.metalType=array<depthcube_array<float>, SHADOW_COUNT>|shadowCubeArrays.bindingClass=texture|shadowCubeArrays.argumentIndex=4|shadowCubeArrays.arraySize=SHADOW_COUNT|shadowCubeArrays.arrayElementCount=2|rawShadowSamplers.sourceType=sampler[RAW_SAMPLER_COUNT]|rawShadowSamplers.metalType=array<sampler, RAW_SAMPLER_COUNT>|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.argumentIndex=9|rawShadowSamplers.arraySize=RAW_SAMPLER_COUNT|rawShadowSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowCubes.usageRoles=manual-depth-texture|shadowCubeArrays.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|sampled-texture.kind=resource|descriptor-array.kind=resource|cube-dimension.kind=texture|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_cube_family_only_nonuniform_compare_lod_manual_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-cube-family-only-nonuniform-compare-lod-manual-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowCubeArrays[descriptor].sample(rawShadowSampler, float3(0.0, 1.0, 0.0), uint(2.0), level(3.0)), 0.75, CGL_COMPARE_GREATER)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCubes.metalType=array<depthcube<float>, SHADOW_COUNT>|shadowCubes.bindingClass=texture|shadowCubes.arrayElementCount=2|shadowCubeArrays.metalType=array<depthcube_array<float>, SHADOW_COUNT>|shadowCubeArrays.bindingClass=texture|shadowCubeArrays.arrayElementCount=2|rawShadowSampler.metalType=sampler|rawShadowSampler.bindingClass=sampler|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowCubes.usageRoles=manual-depth-texture|shadowCubeArrays.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_cube_family_only_nonuniform_compare_lod_manual_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_CUBE_FAMILY_ONLY_NONUNIFORM_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-cube-family-only-nonuniform-compare-lod-manual-descriptor-array.cglb
      -DEXPECTED_MODULE=SamplerCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowCubeArray.sample(rawShadowSamplers[descriptor], float3(0.0, 1.0, 0.0), uint(2.0), level(3.0)), 0.75, CGL_COMPARE_GREATER)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerCubeFamilyOnlyNonUniformCompareLodManualDescriptorArrayShader|manualTextureCompareKernelSummary.totalCount=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCube.metalType=depthcube<float>|shadowCube.bindingClass=texture|shadowCubeArray.metalType=depthcube_array<float>|shadowCubeArray.bindingClass=texture|rawShadowSamplers.metalType=array<sampler, RAW_SAMPLER_COUNT>|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowCube.usageRoles=manual-depth-texture|shadowCubeArray.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_family_only_nonuniform_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-family-only-nonuniform-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureFamilyOnlyNonUniformCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowCubeArrays[descriptor].sample_compare(shadowSampler, float3(0.0, 1.0, 0.0), uint(2.0), 0.5)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureFamilyOnlyNonUniformCompareDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.metalType=array<depth2d_array<float>, SHADOW_COUNT>|shadowAtlases.bindingClass=texture|shadowAtlases.arrayElementCount=2|shadowCubes.metalType=array<depthcube<float>, SHADOW_COUNT>|shadowCubes.bindingClass=texture|shadowCubes.arrayElementCount=2|shadowCubeArrays.metalType=array<depthcube_array<float>, SHADOW_COUNT>|shadowCubeArrays.bindingClass=texture|shadowCubeArrays.arrayElementCount=2|shadowSampler.bindingClass=sampler|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-texture-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_family_only_nonuniform_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_FAMILY_ONLY_NONUNIFORM_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-family-only-nonuniform-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=SamplerFamilyOnlyNonUniformCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowCubeArray.sample_compare(shadowSamplers[descriptor], float3(0.0, 1.0, 0.0), uint(2.0), 0.5)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerFamilyOnlyNonUniformCompareDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlas.metalType=depth2d_array<float>|shadowAtlas.bindingClass=texture|shadowCube.metalType=depthcube<float>|shadowCube.bindingClass=texture|shadowCubeArray.metalType=depthcube_array<float>|shadowCubeArray.bindingClass=texture|shadowSamplers.metalType=array<sampler, SAMPLER_COUNT>|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2|descriptors.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=nonuniform-descriptor-index.kind=operation|nonuniform-sampler-descriptor-index.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_sampler_descriptor_array_size_mismatch_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_SIZE_MISMATCH_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-sampler-descriptor-array-size-mismatch.cglb
      -DEXPECTED_MODULE=TextureSamplerDescriptorArraySizeMismatchShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=colorMaps[1].sample(linearSamplers[2]"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureSamplerDescriptorArraySizeMismatchShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorMaps.sourceType=sampler2D[TEXTURE_COUNT]|colorMaps.metalType=array<texture2d<float>, TEXTURE_COUNT>|colorMaps.bindingClass=texture|colorMaps.arraySize=TEXTURE_COUNT|colorMaps.arrayElementCount=2|linearSamplers.sourceType=sampler[SAMPLER_COUNT]|linearSamplers.metalType=array<sampler, SAMPLER_COUNT>|linearSamplers.bindingClass=sampler|linearSamplers.arraySize=SAMPLER_COUNT|linearSamplers.arrayElementCount=3|values.storageBufferLayout.layout=metal-device"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_resource_array_access_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_RESOURCE_ARRAY_ACCESS_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-resource-array-access.cglb
      -DEXPECTED_MODULE=ResourceArrayAccessShader
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_sampler_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-sampler-array-lod.cglb
      -DEXPECTED_MODULE=VulkanTextureSamplerArrayLodShader
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_sampler_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-sampler-lod.cglb
      -DEXPECTED_MODULE=VulkanTextureSamplerLodShader
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_sampler_3d_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_3D_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-sampler-3d-lod.cglb
      -DEXPECTED_MODULE=VulkanTextureSampler3DLodShader
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_sampler_3d_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_3D_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-sampler-3d-array-lod.cglb
      -DEXPECTED_MODULE=VulkanTextureSampler3DArrayLodShader
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_sampler_cube_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_CUBE_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-sampler-cube-lod.cglb
      -DEXPECTED_MODULE=VulkanTextureSamplerCubeLodShader
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_sampler_cube_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_TEXTURE_SAMPLER_CUBE_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-sampler-cube-array-lod.cglb
      -DEXPECTED_MODULE=VulkanTextureSamplerCubeArrayLodShader
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_integer_texture_sampler_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_INTEGER_TEXTURE_SAMPLER_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-integer-texture-sampler-lod.cglb
      -DEXPECTED_MODULE=VulkanIntegerTextureSamplerLodShader
      -DEXPECTED_STORAGE_ELEMENT=ivec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_integer_texture_array_sampler_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_INTEGER_TEXTURE_ARRAY_SAMPLER_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-integer-texture-array-sampler-lod.cglb
      -DEXPECTED_MODULE=VulkanIntegerTextureArraySamplerLodShader
      -DEXPECTED_STORAGE_ELEMENT=ivec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_array_dimensions_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ARRAY_DIMENSION_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-array-dimensions.cglb
      -DEXPECTED_MODULE=TextureArrayDimensionShader
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_compare_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_SHADOW_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-compare.cglb
      -DEXPECTED_MODULE=TextureCompareShadowShader
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_comparison_sampler_role_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_COMPARISON_SAMPLER_ROLE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-comparison-sampler-role.cglb
      -DEXPECTED_MODULE=ComparisonSamplerRoleShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMap.sample_compare(shadowCompareSamplers[0]"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=ComparisonSamplerRoleShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.sourceType=sampler2DShadow|shadowMap.metalType=depth2d<float>|shadowMap.bindingClass=texture|shadowCompareSamplers.sourceType=comparison_sampler[2]|shadowCompareSamplers.metalType=array<sampler, 2>|shadowCompareSamplers.bindingClass=sampler|shadowCompareSamplers.argumentIndex=4|shadowCompareSamplers.arraySize=2|shadowCompareSamplers.arrayElementCount=2|linearSampler.bindingClass=sampler|values.storageBufferLayout.layout=metal-device"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_only_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ONLY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-only-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureOnlyCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMaps[1].sample_compare(shadowSampler"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureOnlyCompareDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMaps.sourceType=sampler2DShadow[SHADOW_COUNT]|shadowMaps.metalType=array<depth2d<float>, SHADOW_COUNT>|shadowMaps.bindingClass=texture|shadowMaps.argumentIndex=2|shadowMaps.arraySize=SHADOW_COUNT|shadowMaps.arrayElementCount=2|shadowSampler.sourceType=sampler|shadowSampler.metalType=sampler|shadowSampler.bindingClass=sampler|shadowSampler.argumentIndex=5|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_sampler_only_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SAMPLER_ONLY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-sampler-only-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=SamplerOnlyCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowMap.sample_compare(shadowSamplers[1]"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SamplerOnlyCompareDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowMap.sourceType=sampler2DShadow|shadowMap.metalType=depth2d<float>|shadowMap.bindingClass=texture|shadowMap.argumentIndex=2|shadowSamplers.sourceType=sampler[SAMPLER_COUNT]|shadowSamplers.metalType=array<sampler, SAMPLER_COUNT>|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=5|shadowSamplers.arraySize=SAMPLER_COUNT|shadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_array_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-array-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureArrayCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowAtlases[1].sample_compare(shadowSamplers[0], float2(0.25, 0.5), uint(1.0), 0.33)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureArrayCompareDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.sourceType=sampler2DArrayShadow[SHADOW_COUNT]|shadowAtlases.metalType=array<depth2d_array<float>, SHADOW_COUNT>|shadowAtlases.bindingClass=texture|shadowAtlases.argumentIndex=2|shadowAtlases.arraySize=SHADOW_COUNT|shadowAtlases.arrayElementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.metalType=array<sampler, 2>|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=5|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_cube_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-cube-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCubeCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowCubeArrays[1].sample_compare(shadowSamplers[0], float3(0.0, 1.0, 0.0), uint(2.0), 0.5)"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCubeCompareDescriptorArrayShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCubes.sourceType=samplerCubeShadow[SHADOW_COUNT]|shadowCubes.metalType=array<depthcube<float>, SHADOW_COUNT>|shadowCubes.bindingClass=texture|shadowCubes.argumentIndex=2|shadowCubes.arrayElementCount=2|shadowCubeArrays.sourceType=samplerCubeArrayShadow[SHADOW_COUNT]|shadowCubeArrays.metalType=array<depthcube_array<float>, SHADOW_COUNT>|shadowCubeArrays.bindingClass=texture|shadowCubeArrays.argumentIndex=4|shadowCubeArrays.arraySize=SHADOW_COUNT|shadowCubeArrays.arrayElementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.metalType=array<sampler, 2>|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|cube-dimension.kind=texture|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_array_shadow_compare_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ARRAY_SHADOW_COMPARE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-array-shadow-compare.cglb
      -DEXPECTED_MODULE=TextureArrayShadowCompareShader
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_compare_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-compare-lod.cglb
      -DEXPECTED_MODULE=TextureCompareLodShader
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_2d_shadow_compare_lod_manual_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-2d-shadow-compare-lod-manual.cglb
      -DEXPECTED_MODULE=Texture2DShadowCompareLodManualShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowMap.sample(rawShadowSampler, float2(0.5, 0.5), level(2.0)), 0.25, CGL_COMPARE_LESS)"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_2d_array_shadow_compare_lod_manual_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-2d-array-shadow-compare-lod-manual.cglb
      -DEXPECTED_MODULE=Texture2DArrayShadowCompareLodManualShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowAtlas.sample(rawShadowSampler, float2(0.25, 0.5), uint(1.0), level(2.0)), 0.33, CGL_COMPARE_LESS_EQUAL)"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_2d_shadow_compare_lod_manual_offset_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-2d-shadow-compare-lod-manual-offset.cglb
      -DEXPECTED_MODULE=Texture2DShadowCompareLodManualOffsetShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowMap.sample(rawShadowSampler, float2(0.5, 0.5), level(2.0), int2(1, -1)), 0.25, CGL_COMPARE_LESS)"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_2d_array_shadow_compare_lod_manual_offset_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_OFFSET_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-2d-array-shadow-compare-lod-manual-offset.cglb
      -DEXPECTED_MODULE=Texture2DArrayShadowCompareLodManualOffsetShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowAtlas.sample(rawShadowSampler, float2(0.25, 0.5), uint(1.0), level(2.0), int2(-1, 1)), 0.33, CGL_COMPARE_LESS_EQUAL)"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_2d_shadow_compare_lod_manual_gather_2x2_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_GATHER_2X2_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-2d-shadow-compare-lod-manual-gather-2x2.cglb
      -DEXPECTED_MODULE=Texture2DShadowCompareLodManualGather2x2Shader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowMap.sample(rawShadowSampler, float2(0.5, 0.5), level(2.0), int2(1, 1)), 0.25, CGL_COMPARE_LESS)"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_2d_array_shadow_compare_lod_manual_gather_2x2_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_GATHER_2X2_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-2d-array-shadow-compare-lod-manual-gather-2x2.cglb
      -DEXPECTED_MODULE=Texture2DArrayShadowCompareLodManualGather2x2Shader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowAtlas.sample(rawShadowSampler, float2(0.25, 0.5), uint(1.0), level(2.0), int2(1, 1)), 0.33, CGL_COMPARE_LESS_EQUAL)"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_2d_shadow_compare_lod_manual_kernel_4_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_4_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-2d-shadow-compare-lod-manual-kernel-4.cglb
      -DEXPECTED_MODULE=Texture2DShadowCompareLodManualKernel4Shader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowMap.sample(rawShadowSampler, float2(0.5, 0.5), level(2.0), int2(1, 0)), 0.25, CGL_COMPARE_LESS) * 0.375"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_2d_array_shadow_compare_lod_manual_kernel_4_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_KERNEL_4_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-2d-array-shadow-compare-lod-manual-kernel-4.cglb
      -DEXPECTED_MODULE=Texture2DArrayShadowCompareLodManualKernel4Shader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowAtlas.sample(rawShadowSampler, float2(0.25, 0.5), uint(1.0), level(2.0), int2(-1, 0)), 0.33, CGL_COMPARE_LESS_EQUAL) * 0.30"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=Texture2DArrayShadowCompareLodManualKernel4Shader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/Texture2DArrayShadowCompareLodManualKernel4Shader.metal|artifacts.intermediate=backend/metal/Texture2DArrayShadowCompareLodManualKernel4Shader.air|artifacts.nativeBinary=backend/metal/Texture2DArrayShadowCompareLodManualKernel4Shader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=Texture2DArrayShadowCompareLodManualKernel4Shader|nativeBinary=backend/metal/Texture2DArrayShadowCompareLodManualKernel4Shader.metallib|manualTextureCompareKernelSummary.totalCount=1|manualTextureCompareKernelSummary.staticNormalizedCount=1|manualTextureCompareKernels.0.operation=textureCompareLodManualKernel4|manualTextureCompareKernels.0.sourceKind=fixed4|manualTextureCompareKernels.0.canonicalOperation=textureCompareLodManualKernel|manualTextureCompareKernels.0.tapCount=4|manualTextureCompareKernels.0.weightClass=static-normalized|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|functionConstants=0|workgroupSizes=1|manualTextureCompareKernels=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.layout=metal-device|shadowAtlas.sourceType=sampler2DArrayShadow|shadowAtlas.metalType=depth2d_array<float>|shadowAtlas.bindingClass=texture|shadowAtlas.argumentIndex=2|rawShadowSampler.sourceType=sampler|rawShadowSampler.metalType=sampler|rawShadowSampler.bindingClass=sampler|rawShadowSampler.argumentIndex=5"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|sampled-texture.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|texture-shadow-compare-explicit-lod-manual-kernel-list.kind=operation|index-access.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_2d_shadow_compare_lod_manual_kernel_8_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_8_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-2d-shadow-compare-lod-manual-kernel-8.cglb
      -DEXPECTED_MODULE=Texture2DShadowCompareLodManualKernel8Shader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowMap.sample(rawShadowSampler, float2(0.5, 0.5), level(2.0), int2(1, 1)), 0.25, CGL_COMPARE_LESS) * 0.3125"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_2d_array_shadow_compare_lod_manual_kernel_8_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_ARRAY_SHADOW_COMPARE_LOD_MANUAL_KERNEL_8_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-2d-array-shadow-compare-lod-manual-kernel-8.cglb
      -DEXPECTED_MODULE=Texture2DArrayShadowCompareLodManualKernel8Shader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowAtlas.sample(rawShadowSampler, float2(0.25, 0.5), uint(1.0), level(2.0), int2(1, 1)), 0.33, CGL_COMPARE_LESS_EQUAL) * 0.10"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlas.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_2d_shadow_compare_lod_manual_kernel_list_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-2d-shadow-compare-lod-manual-kernel-list.cglb
      -DEXPECTED_MODULE=Texture2DShadowCompareLodManualKernelListShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowMap.sample(rawShadowSampler, float2(0.5, 0.5), level(2.0), int2(0, -1)), 0.25, CGL_COMPARE_LESS_EQUAL) * 0.15"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=Texture2DShadowCompareLodManualKernelListShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/Texture2DShadowCompareLodManualKernelListShader.metal|artifacts.intermediate=backend/metal/Texture2DShadowCompareLodManualKernelListShader.air|artifacts.nativeBinary=backend/metal/Texture2DShadowCompareLodManualKernelListShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=Texture2DShadowCompareLodManualKernelListShader|nativeBinary=backend/metal/Texture2DShadowCompareLodManualKernelListShader.metallib|manualTextureCompareKernelSummary.totalCount=1|manualTextureCompareKernelSummary.staticNormalizedCount=1|manualTextureCompareKernels.0.operation=textureCompareLodManualKernel|manualTextureCompareKernels.0.sourceKind=tap-list|manualTextureCompareKernels.0.canonicalOperation=textureCompareLodManualKernel|manualTextureCompareKernels.0.tapCount=5|manualTextureCompareKernels.0.weightClass=static-normalized|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|functionConstants=0|workgroupSizes=1|manualTextureCompareKernels=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.layout=metal-device|shadowMap.sourceType=sampler2DShadow|shadowMap.metalType=depth2d<float>|shadowMap.bindingClass=texture|shadowMap.argumentIndex=2|rawShadowSampler.sourceType=sampler|rawShadowSampler.metalType=sampler|rawShadowSampler.bindingClass=sampler|rawShadowSampler.argumentIndex=6"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowMap.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|sampled-texture.kind=resource|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|texture-shadow-compare-explicit-lod-manual-kernel-list.kind=operation|index-access.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_cube_shadow_compare_lod_manual_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_MANUAL_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-cube-shadow-compare-lod-manual.cglb
      -DEXPECTED_MODULE=TextureCubeShadowCompareLodManualShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowCube.sample(rawShadowSampler, float3(0.0, 1.0, 0.0), level(1.0)), 0.5, CGL_COMPARE_GREATER_EQUAL)"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowCube.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_cube_array_shadow_compare_lod_manual_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_ARRAY_SHADOW_COMPARE_LOD_MANUAL_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-cube-array-shadow-compare-lod-manual.cglb
      -DEXPECTED_MODULE=TextureCubeArrayShadowCompareLodManualShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowCubes.sample(rawShadowSampler, float3(0.0, 1.0, 0.0), uint(2.0), level(3.0)), 0.75, CGL_COMPARE_GREATER)"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowCubes.usageRoles=manual-depth-texture|rawShadowSampler.usageRoles=manual-raw-sampler"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_compare_lod_manual_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_COMPARE_LOD_MANUAL_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-compare-lod-manual-descriptor-array.cglb
      -DEXPECTED_MODULE=TextureCompareLodManualDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowAtlases[1].sample(rawShadowSamplers[0], float2(0.25, 0.5), uint(1.0), level(2.0)), 0.33, CGL_COMPARE_LESS_EQUAL)"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCompareLodManualDescriptorArrayShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/TextureCompareLodManualDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/TextureCompareLodManualDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/TextureCompareLodManualDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCompareLodManualDescriptorArrayShader|nativeBinary=backend/metal/TextureCompareLodManualDescriptorArrayShader.metallib|manualTextureCompareKernelSummary.totalCount=0|functionConstants.0.name=SHADOW_COUNT|functionConstants.0.value=2|functionConstants.1.name=RAW_SAMPLER_COUNT|functionConstants.1.value=2|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=3|targetResourceBindings=3|functionConstants=2|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.layout=metal-device|shadowAtlases.sourceType=sampler2DArrayShadow[SHADOW_COUNT]|shadowAtlases.metalType=array<depth2d_array<float>, SHADOW_COUNT>|shadowAtlases.bindingClass=texture|shadowAtlases.argumentIndex=2|shadowAtlases.arraySize=SHADOW_COUNT|shadowAtlases.arrayElementCount=2|rawShadowSamplers.sourceType=sampler[RAW_SAMPLER_COUNT]|rawShadowSamplers.metalType=array<sampler, RAW_SAMPLER_COUNT>|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.argumentIndex=5|rawShadowSamplers.arraySize=RAW_SAMPLER_COUNT|rawShadowSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|sampled-texture.kind=resource|descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare-explicit-lod-manual.kind=operation|index-access.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_mixed_texture_manual_compare_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_MIXED_TEXTURE_MANUAL_COMPARE_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-mixed-texture-manual-compare-descriptor-array.cglb
      -DEXPECTED_MODULE=MixedTextureManualCompareDescriptorArrayShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=cglCompareDepth(shadowAtlases[1].sample(rawShadowSamplers[0], float2(0.25, 0.5), uint(1.0), level(2.0)), 0.33, CGL_COMPARE_LESS_EQUAL)"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MixedTextureManualCompareDescriptorArrayShader|sourceHash.algorithm=sha256|artifacts.backendSource=backend/metal/MixedTextureManualCompareDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/MixedTextureManualCompareDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/MixedTextureManualCompareDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MixedTextureManualCompareDescriptorArrayShader|nativeBinary=backend/metal/MixedTextureManualCompareDescriptorArrayShader.metallib|manualTextureCompareKernelSummary.totalCount=0|functionConstants.0.name=RESOURCE_COUNT|functionConstants.0.value=2|functionConstants.1.name=RAW_SAMPLER_COUNT|functionConstants.1.value=2|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=2|workgroupSizes=1|manualTextureCompareKernels=0"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.metalType=device float4*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.layout=metal-device|colorMaps.sourceType=sampler2D[RESOURCE_COUNT]|colorMaps.metalType=array<texture2d<float>, RESOURCE_COUNT>|colorMaps.bindingClass=texture|colorMaps.argumentIndex=2|colorMaps.arraySize=RESOURCE_COUNT|colorMaps.arrayElementCount=2|shadowMaps.sourceType=sampler2DShadow[RESOURCE_COUNT]|shadowMaps.metalType=array<depth2d<float>, RESOURCE_COUNT>|shadowMaps.bindingClass=texture|shadowMaps.argumentIndex=4|shadowMaps.arraySize=RESOURCE_COUNT|shadowMaps.arrayElementCount=2|shadowAtlases.sourceType=sampler2DArrayShadow[RESOURCE_COUNT]|shadowAtlases.metalType=array<depth2d_array<float>, RESOURCE_COUNT>|shadowAtlases.bindingClass=texture|shadowAtlases.argumentIndex=6|shadowAtlases.arraySize=RESOURCE_COUNT|shadowAtlases.arrayElementCount=2|linearSamplers.sourceType=sampler[RESOURCE_COUNT]|linearSamplers.metalType=array<sampler, RESOURCE_COUNT>|linearSamplers.bindingClass=sampler|linearSamplers.argumentIndex=10|linearSamplers.arrayElementCount=2|shadowSamplers.sourceType=sampler[RESOURCE_COUNT]|shadowSamplers.metalType=array<sampler, RESOURCE_COUNT>|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=12|shadowSamplers.arrayElementCount=2|rawShadowSamplers.sourceType=sampler[RAW_SAMPLER_COUNT]|rawShadowSamplers.metalType=array<sampler, RAW_SAMPLER_COUNT>|rawShadowSamplers.bindingClass=sampler|rawShadowSamplers.argumentIndex=14|rawShadowSamplers.arraySize=RAW_SAMPLER_COUNT|rawShadowSamplers.arrayElementCount=2"
      "-DEXPECTED_REFLECTION_TARGET_ARRAY_CONTAINS=shadowAtlases.usageRoles=manual-depth-texture|rawShadowSamplers.usageRoles=manual-raw-sampler"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|sampled-texture.kind=resource|descriptor-array.kind=resource|depth-compare-format.kind=texture|array-dimension.kind=texture|sampler-state.kind=resource|texture-sample.kind=operation|texture-explicit-lod.kind=operation|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|texture-shadow-compare-explicit-lod-manual.kind=operation|index-access.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_array_compare_descriptor_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_ARRAY_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-array-compare-descriptor-array-lod.cglb
      -DEXPECTED_MODULE=TextureArrayCompareDescriptorArrayLodShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowAtlases[1].sample_compare(shadowSamplers[0], float2(0.25, 0.5), uint(1.0), 0.33, level(2.0))"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureArrayCompareDescriptorArrayLodShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowAtlases.sourceType=sampler2DArrayShadow[SHADOW_COUNT]|shadowAtlases.metalType=array<depth2d_array<float>, SHADOW_COUNT>|shadowAtlases.bindingClass=texture|shadowAtlases.argumentIndex=2|shadowAtlases.arraySize=SHADOW_COUNT|shadowAtlases.arrayElementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.metalType=array<sampler, 2>|shadowSamplers.bindingClass=sampler|shadowSamplers.argumentIndex=5|shadowSamplers.arraySize=2|shadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_texture_cube_compare_descriptor_array_lod_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TEXTURE_CUBE_COMPARE_DESCRIPTOR_ARRAY_LOD_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-texture-cube-compare-descriptor-array-lod.cglb
      -DEXPECTED_MODULE=TextureCubeCompareDescriptorArrayLodShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=shadowCubeArrays[1].sample_compare(shadowSamplers[0], float3(0.0, 1.0, 0.0), uint(2.0), 0.5, level(4.0))"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=TextureCubeCompareDescriptorArrayLodShader"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=shadowCubes.sourceType=samplerCubeShadow[SHADOW_COUNT]|shadowCubes.metalType=array<depthcube<float>, SHADOW_COUNT>|shadowCubes.bindingClass=texture|shadowCubes.argumentIndex=2|shadowCubes.arrayElementCount=2|shadowCubeArrays.sourceType=samplerCubeArrayShadow[SHADOW_COUNT]|shadowCubeArrays.metalType=array<depthcube_array<float>, SHADOW_COUNT>|shadowCubeArrays.bindingClass=texture|shadowCubeArrays.argumentIndex=4|shadowCubeArrays.arraySize=SHADOW_COUNT|shadowCubeArrays.arrayElementCount=2|shadowSamplers.sourceType=sampler[2]|shadowSamplers.metalType=array<sampler, 2>|shadowSamplers.bindingClass=sampler|shadowSamplers.arrayElementCount=2|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=sampled-texture.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|cube-dimension.kind=texture|array-dimension.kind=texture|depth-compare-format.kind=texture|sampler-state.kind=resource|texture-shadow-compare.kind=operation|texture-shadow-compare-explicit-lod.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-write.kind=operation"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_multi_set_resources_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_MULTI_SET_RESOURCE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-multi-set-resources.cglb
      -DEXPECTED_MODULE=MetalMultiSetResourceShader
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_for_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-for.cglb
      -DEXPECTED_MODULE=ForComputeShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      "-DEXPECTED_METAL_STORE_SNIPPET=values[i] = x + 1.0;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=for (int i = 0; i < 4; i++)"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=ForComputeShader|nativeBinary=backend/metal/ForComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|structured-loop.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_for_stride_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_STRIDE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-for-stride.cglb
      -DEXPECTED_MODULE=ForStrideComputeShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      "-DEXPECTED_METAL_STORE_SNIPPET=values[i] = x + 1.0;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=for (int i = 0; i < 8; i+=2)"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=ForStrideComputeShader|nativeBinary=backend/metal/ForStrideComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|structured-loop.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_NESTED_FOR_NATIVE_SOURCE_SNIPPET [=[for (int i = 0; i < 2; i++) {
    for (int j = 0; j < 2; j++) {
      int index = i * 2 + j;]=])
  add_test(NAME cglc_build_metal_nested_for_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_NESTED_FOR_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-nested-for.cglb
      -DEXPECTED_MODULE=NestedForComputeShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      "-DEXPECTED_METAL_STORE_SNIPPET=values[i] = values[i] + 2.0;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_NESTED_FOR_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=NestedForComputeShader|nativeBinary=backend/metal/NestedForComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|structured-loop.kind=controlFlow|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_DYNAMIC_STRIDE_FOR_NATIVE_SOURCE_SNIPPET [=[int stride = 2;
  for (int i = 0; i < 8; i+=stride)]=])
  add_test(NAME cglc_build_metal_for_dynamic_stride_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_DYNAMIC_STRIDE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-for-dynamic-stride.cglb
      -DEXPECTED_MODULE=ForDynamicStrideComputeShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      "-DEXPECTED_METAL_STORE_SNIPPET=values[i] = x + 1.0;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_DYNAMIC_STRIDE_FOR_NATIVE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=ForDynamicStrideComputeShader|nativeBinary=backend/metal/ForDynamicStrideComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|structured-loop.kind=controlFlow|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_for_constant_stride_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_CONSTANT_STRIDE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-for-constant-stride.cglb
      -DEXPECTED_MODULE=ForConstantStrideComputeShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      "-DEXPECTED_METAL_STORE_SNIPPET=values[i] = x + 1.0;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=for (int i = 0; i < 8; i+=TILE_SIZE)"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=ForConstantStrideComputeShader|nativeBinary=backend/metal/ForConstantStrideComputeShader.metallib|functionConstants.0.name=TILE_SIZE|functionConstants.0.type=int|functionConstants.0.value=2|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|structured-loop.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_for_folded_update_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FOR_FOLDED_UPDATE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-for-folded-update.cglb
      -DEXPECTED_MODULE=ForFoldedUpdateComputeShader
      -DMODE=metal-build
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      "-DEXPECTED_METAL_STORE_SNIPPET=values[i] = x + 1.0;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=for (int i = 0; i < 8; i = i + (3))"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=ForFoldedUpdateComputeShader|nativeBinary=backend/metal/ForFoldedUpdateComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|structured-loop.kind=controlFlow|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_arithmetic_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_ARITHMETIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-arithmetic.cglb
      -DEXPECTED_MODULE=ArithmeticComputeShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=kernel void compute_main()"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=ArithmeticComputeShader|nativeBinary=backend/metal/ArithmeticComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=0|targetResourceBindings=0"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|workgroup-size.kind=execution"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_comparison_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_COMPARISON_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-comparison.cglb
      -DEXPECTED_MODULE=ComparisonComputeShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=kernel void compute_main(device float* values [[buffer(0)]])"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=ComparisonComputeShader|nativeBinary=backend/metal/ComparisonComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|storage-buffer.kind=resource"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_FLOAT_EQUALITY_NEGATION_NATIVE_SOURCE_SNIPPET [=[bool equalityNegationFloat = (dynamicFloat != 31.0);
  bool inequalityNegationFloat = (dynamicFloat == 32.0);]=])
  add_test(NAME cglc_build_metal_float_equality_negation_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_FLOAT_EQUALITY_NEGATION_BACKEND_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-float-equality-negation.cglb
      -DEXPECTED_MODULE=FloatEqualityNegationBackendShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_FLOAT_EQUALITY_NEGATION_NATIVE_SOURCE_SNIPPET}"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=FloatEqualityNegationBackendShader|nativeBinary=backend/metal/FloatEqualityNegationBackendShader.metallib|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=int*|values.metalType=device int*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=int|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|compute-kernel.kind=stage|storage-buffer.kind=resource|scalar-comparison.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_BOOLEAN_DE_MORGAN_NATIVE_SOURCE_SNIPPET [=[bool deMorganAnd = (!base || dynamicIndex <= 17);
  bool deMorganOr = (!base && dynamicIndex <= 18);
  bool deMorganComparisonAnd = (dynamicIndex >= 19 || dynamicIndex <= 20);
  bool deMorganComparisonOr = (dynamicIndex >= 21 && dynamicIndex <= 22);]=])
  add_test(NAME cglc_build_metal_boolean_de_morgan_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_BOOLEAN_DE_MORGAN_BACKEND_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-boolean-de-morgan.cglb
      -DEXPECTED_MODULE=BooleanDeMorganBackendShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_BOOLEAN_DE_MORGAN_NATIVE_SOURCE_SNIPPET}"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=BooleanDeMorganBackendShader|nativeBinary=backend/metal/BooleanDeMorganBackendShader.metallib|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=int*|values.metalType=device int*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=int|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|compute-kernel.kind=stage|storage-buffer.kind=resource|scalar-comparison.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_SELECT_EXPRESSION_NATIVE_SOURCE_SNIPPET [=[int selectedInt = base ? dynamicIndex + 1 : dynamicIndex + 2;
  bool selectedBool = base ? dynamicIndex > 3 : dynamicIndex > 4;
  values[1] = selectedInt;
  values[2] = selectedBool ? 1 : 0;]=])
  add_test(NAME cglc_build_metal_select_expression_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SELECT_EXPRESSION_BACKEND_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-select-expression.cglb
      -DEXPECTED_MODULE=SelectExpressionBackendShader
      -DMODE=metal-build
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_SELECT_EXPRESSION_NATIVE_SOURCE_SNIPPET}"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=SelectExpressionBackendShader|nativeBinary=backend/metal/SelectExpressionBackendShader.metallib|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=int*|values.metalType=device int*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=int|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|compute-kernel.kind=stage|storage-buffer.kind=resource|scalar-comparison.kind=operation|select-expression.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_load_local_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_LOAD_LOCAL_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-load-local.cglb
      -DEXPECTED_MODULE=LoadLocalComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      "-DEXPECTED_METAL_STORE_SNIPPET=values[1] = x + 1.0;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=float x = values[0];"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=LoadLocalComputeShader|nativeBinary=backend/metal/LoadLocalComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_scalar_constructor_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_SCALAR_CONSTRUCTOR_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-scalar-constructor.cglb
      -DEXPECTED_MODULE=ScalarConstructorComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      "-DEXPECTED_METAL_STORE_SNIPPET=values[1] = signedBack + unsignedBack;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=uint unsignedValue = uint(source);"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=ScalarConstructorComputeShader|nativeBinary=backend/metal/ScalarConstructorComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|local-declaration.kind=operation|storage-buffer-read.kind=operation|index-access.kind=operation|scalar-constructor.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_MATRIX_SCALAR_ARITHMETIC_SOURCE_SNIPPET [=[void keep(float3x3 scaled, float3x3 rescaled, float3x3 inferred, device float* values) {
  values[0] = 1.0;
  return;
}

kernel void compute_main(device float* values [[buffer(0)]]) {
  float3x3 transform = float3x3(float3(1.0, 2.0, 3.0), float3(4.0, 5.0, 6.0), float3(7.0, 8.0, 9.0));
  float3x3 scaled = transform * 2.0;
  float3x3 rescaled = 0.5 * transform;
  float3x3 inferred = transform * 0.25;
  inferred = inferred * 4.0;
  keep(scaled, rescaled, inferred, values);]=])
  add_test(NAME cglc_build_metal_matrix_scalar_arithmetic_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_MATRIX_SCALAR_ARITHMETIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-matrix-scalar-arithmetic.cglb
      -DEXPECTED_MODULE=MatrixScalarArithmeticComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      "-DEXPECTED_METAL_STORE_SNIPPET=values[0] = 1.0;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_MATRIX_SCALAR_ARITHMETIC_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MatrixScalarArithmeticComputeShader|nativeBinary=backend/metal/MatrixScalarArithmeticComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-write.kind=operation|index-access.kind=operation|local-declaration.kind=operation|matrix-constructor.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_MATRIX_VECTOR_ARITHMETIC_SOURCE_SNIPPET [=[float3 columnProduct = transform * source;
  float3 rowProduct = source * transform;
  float3x3 composed = transform * basis;
  float3 projected = composed * rowProduct;]=])
  add_test(NAME cglc_build_metal_matrix_vector_arithmetic_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_MATRIX_VECTOR_ARITHMETIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-matrix-vector-arithmetic.cglb
      -DEXPECTED_MODULE=MatrixVectorArithmeticComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      "-DEXPECTED_METAL_STORE_SNIPPET=values[1] = rowProduct.y;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_MATRIX_VECTOR_ARITHMETIC_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MatrixVectorArithmeticComputeShader|nativeBinary=backend/metal/MatrixVectorArithmeticComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|vector-constructor.kind=operation|index-access.kind=operation|matrix-constructor.kind=operation|vector-arithmetic.kind=operation|scalar-arithmetic.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_vector_local_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR_LOCAL_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-vector-local.cglb
      -DEXPECTED_MODULE=VectorLocalComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      "-DEXPECTED_METAL_STORE_SNIPPET=values[1] = lifted.y;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=float4 lifted = color + float4(0.5, 0.5, 0.5, 0.0);"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=VectorLocalComputeShader|nativeBinary=backend/metal/VectorLocalComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.arrayStrideBytes=4|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|vector-constructor.kind=operation|vector-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_vector_buffer_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-vector-buffer.cglb
      -DEXPECTED_MODULE=VectorBufferComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float4*
      "-DEXPECTED_METAL_SOURCE_SNIPPET=float4 lifted = color + float4(0.5, 0.5, 0.5, 0.0);"
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=VectorBufferComputeShader|nativeBinary=backend/metal/VectorBufferComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec4*|values.metalType=device float4*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=vec4|values.storageBufferLayout.arrayStrideBytes=16|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|vector-storage-buffer.kind=layout|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|vector-constructor.kind=operation|vector-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_atan_intrinsic_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_ATAN_INTRINSIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-atan-intrinsic.cglb
      -DEXPECTED_MODULE=AtanIntrinsicComputeShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=float angle = atan2(scalars[0], scalars[1]);"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_INTRINSIC_SOURCE_SNIPPET [=[  float scalarLength = abs(frac);
  float vectorLength = length(vectors[0]);
  float alignment = dot(vectors[0], vectors[1]);
  float4 direction = normalize(vectors[0]);
  float4 reflected = reflect(direction, normalize(vectors[1]));
  float4 mixed = mix(direction, reflected, 0.25);
  scalars[2] = scalarLength + vectorLength + alignment;
  vectors[2] = mixed;]=])
  add_test(NAME cglc_build_metal_intrinsics_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_INTRINSIC_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-intrinsics.cglb
      -DEXPECTED_MODULE=IntrinsicComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      -DEXPECTED_METAL_BUFFER_NAME=scalars
      "-DEXPECTED_METAL_STORE_SNIPPET=vectors[2] = mixed;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_INTRINSIC_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=IntrinsicComputeShader|nativeBinary=backend/metal/IntrinsicComputeShader.metallib"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=scalars.sourceType=float*|scalars.metalType=device float*|scalars.bindingClass=buffer|scalars.argumentIndex=0|scalars.storageBufferLayout.layout=metal-device|vectors.sourceType=vec4*|vectors.metalType=device float4*|vectors.bindingClass=buffer|vectors.argumentIndex=1|vectors.storageBufferLayout.elementType=vec4|vectors.storageBufferLayout.arrayStrideBytes=16|vectors.storageBufferLayout.layout=metal-device"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_VECTOR_SWIZZLE_SOURCE_SNIPPET [=[  float3 rgb = color.rgb;
  float2 rg = color.xy;
  float4 rgba = color.rgba;
  values[0] = rgb.z;
  values[1] = rg.y;
  values[2] = rgba.b;]=])
  add_test(NAME cglc_build_metal_vector_swizzle_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR_SWIZZLE_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-vector-swizzle.cglb
      -DEXPECTED_MODULE=VectorSwizzleComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float*
      -DEXPECTED_METAL_BUFFER_NAME=values
      "-DEXPECTED_METAL_STORE_SNIPPET=values[2] = rgba.b;"
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_VECTOR_SWIZZLE_SOURCE_SNIPPET}"
      -DEXPECTED_STORAGE_ELEMENT=float
      -DEXPECTED_STORAGE_STRIDE=4
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=VectorSwizzleComputeShader|nativeBinary=backend/metal/VectorSwizzleComputeShader.metallib"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=float*|values.metalType=device float*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=float|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|local-declaration.kind=operation|storage-buffer-read.kind=operation|vector-constructor.kind=operation|index-access.kind=operation|storage-buffer-write.kind=operation"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_vector_scalar_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR_SCALAR_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-vector-scalar.cglb
      -DEXPECTED_MODULE=VectorScalarComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float4*
      "-DEXPECTED_METAL_STORE_SNIPPET=values[1] = normalized;"
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_vector_scalar_cast_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR_SCALAR_CAST_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-vector-scalar-cast.cglb
      -DEXPECTED_MODULE=VectorScalarCastComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float4*
      "-DEXPECTED_METAL_STORE_SNIPPET=values[1] = biased;"
      -DEXPECTED_STORAGE_ELEMENT=vec4
      -DEXPECTED_STORAGE_STRIDE=16
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_vector3_buffer_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VECTOR3_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-vector3-buffer.cglb
      -DEXPECTED_MODULE=Vector3BufferComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ float3*
      "-DEXPECTED_METAL_SOURCE_SNIPPET=float3 lifted = color + float3(0.5, 0.5, 0.0);"
      -DEXPECTED_STORAGE_ELEMENT=vec3
      -DEXPECTED_STORAGE_STRIDE=16
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=Vector3BufferComputeShader|nativeBinary=backend/metal/Vector3BufferComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=values.sourceType=vec3*|values.metalType=device float3*|values.bindingClass=buffer|values.argumentIndex=0|values.storageBufferLayout.elementType=vec3|values.storageBufferLayout.arrayStrideBytes=16|values.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|vector-storage-buffer.kind=layout|local-declaration.kind=operation|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|index-access.kind=operation|vector-constructor.kind=operation|vector-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_struct_buffer_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-struct-buffer.cglb
      -DEXPECTED_MODULE=StructBufferComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ Particle*
      -DEXPECTED_METAL_BUFFER_NAME=particles
      "-DEXPECTED_METAL_STORE_SNIPPET=particles[1].mass = mass + 1.0;"
      -DEXPECTED_METAL_STRUCT=Particle
      "-DEXPECTED_METAL_FIELD_SNIPPET=float3 position;"
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=48
      -DEXPECTED_STRUCT_FIELD=mass
      -DEXPECTED_STRUCT_FIELD_OFFSET=16
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=StructBufferComputeShader|artifacts.backendSource=backend/metal/StructBufferComputeShader.metal|artifacts.intermediate=backend/metal/StructBufferComputeShader.air|artifacts.nativeBinary=backend/metal/StructBufferComputeShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=StructBufferComputeShader|nativeBinary=backend/metal/StructBufferComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.metalType=device Particle*|particles.addressSpace=device|particles.bindingClass=buffer|particles.argumentIndex=0|particles.set=0|particles.binding=0|particles.abi=kernelArgument|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.elementSizeBytes=48|particles.storageBufferLayout.arrayStrideBytes=48|particles.storageBufferLayout.layout=metal-device|particles.storageBufferLayout.fields.0.name=position|particles.storageBufferLayout.fields.0.offsetBytes=0|particles.storageBufferLayout.fields.0.storageSizeBytes=16|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=16|particles.storageBufferLayout.fields.2.name=velocity|particles.storageBufferLayout.fields.2.offsetBytes=32"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_struct_storage_buffer_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_STRUCT_STORAGE_BUFFER_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-struct-storage-buffer-descriptor-array.cglb
      -DEXPECTED_MODULE=MetalStructStorageBufferDescriptorArrayShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=device Particle* particles_0 [[buffer(1)]], device Particle* particles_1 [[buffer(2)]], device Particle* particles_2 [[buffer(3)]], device float* totals [[buffer(4)]]"
      "-DEXPECTED_METAL_STORE_SNIPPET=totals[0] = mass + particles_0[1].mass;"
      -DEXPECTED_METAL_STRUCT=Particle
      "-DEXPECTED_METAL_FIELD_SNIPPET=float3 position;"
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=32
      -DEXPECTED_STRUCT_FIELD=mass
      -DEXPECTED_STRUCT_FIELD_OFFSET=16
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStructStorageBufferDescriptorArrayShader|artifacts.backendSource=backend/metal/MetalStructStorageBufferDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/MetalStructStorageBufferDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/MetalStructStorageBufferDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStructStorageBufferDescriptorArrayShader|nativeBinary=backend/metal/MetalStructStorageBufferDescriptorArrayShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=2|targetResourceBindings=2|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*[3]|particles.metalType=device Particle*|particles.addressSpace=device|particles.bindingClass=buffer|particles.argumentIndex=1|particles.set=0|particles.binding=1|particles.abi=kernelArgument|particles.arraySize=3|particles.arrayElementCount=3|particles.arrayDimensions.0.source=3|particles.arrayDimensions.0.elementCount=3|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.elementSizeBytes=20|particles.storageBufferLayout.arrayStrideBytes=32|particles.storageBufferLayout.layout=metal-device|particles.storageBufferLayout.fields.0.name=position|particles.storageBufferLayout.fields.0.offsetBytes=0|particles.storageBufferLayout.fields.0.storageSizeBytes=16|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=16|totals.sourceType=float*|totals.metalType=device float*|totals.bindingClass=buffer|totals.argumentIndex=4|totals.storageBufferLayout.elementType=float|totals.storageBufferLayout.arrayStrideBytes=4|totals.storageBufferLayout.layout=metal-device"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|fixed-array.kind=layout|descriptor-array.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|scalar-arithmetic.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_struct_vector_buffer_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_VECTOR_BUFFER_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-struct-vector-buffer.cglb
      -DEXPECTED_MODULE=StructVectorBufferComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ Particle*
      -DEXPECTED_METAL_BUFFER_NAME=particles
      "-DEXPECTED_METAL_STORE_SNIPPET=particles[1].position = lifted;"
      -DEXPECTED_METAL_STRUCT=Particle
      "-DEXPECTED_METAL_FIELD_SNIPPET=float3 position;"
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=48
      -DEXPECTED_STRUCT_FIELD=position
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=StructVectorBufferComputeShader|artifacts.backendSource=backend/metal/StructVectorBufferComputeShader.metal|artifacts.intermediate=backend/metal/StructVectorBufferComputeShader.air|artifacts.nativeBinary=backend/metal/StructVectorBufferComputeShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=StructVectorBufferComputeShader|nativeBinary=backend/metal/StructVectorBufferComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.metalType=device Particle*|particles.addressSpace=device|particles.bindingClass=buffer|particles.argumentIndex=0|particles.set=0|particles.binding=0|particles.abi=kernelArgument|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.elementSizeBytes=48|particles.storageBufferLayout.arrayStrideBytes=48|particles.storageBufferLayout.layout=metal-device|particles.storageBufferLayout.fields.0.name=position|particles.storageBufferLayout.fields.0.offsetBytes=0|particles.storageBufferLayout.fields.0.storageSizeBytes=16|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=16|particles.storageBufferLayout.fields.2.name=velocity|particles.storageBufferLayout.fields.2.offsetBytes=32"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation|vector-arithmetic.kind=operation|vector-constructor.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_runtime_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_RUNTIME_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-runtime-array.cglb
      -DEXPECTED_MODULE=RuntimeArrayShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ RuntimePayload*
      -DEXPECTED_METAL_BUFFER_NAME=payloads
      "-DEXPECTED_METAL_STORE_SNIPPET=(reinterpret_cast<device float*>(reinterpret_cast<device char*>(payloads) + 4))[1] = payloads->count;"
      -DEXPECTED_METAL_STRUCT=RuntimePayload
      "-DEXPECTED_METAL_FIELD_SNIPPET=float count;"
      -DEXPECTED_STORAGE_ELEMENT=RuntimePayload
      -DEXPECTED_STORAGE_STRIDE=0
      -DEXPECTED_STRUCT_FIELD=values
      -DEXPECTED_STRUCT_FIELD_OFFSET=4
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=4
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_runtime_vector_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_RUNTIME_VECTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-runtime-vector-array.cglb
      -DEXPECTED_MODULE=RuntimeVectorArrayShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ RuntimeVectorPayload*
      -DEXPECTED_METAL_BUFFER_NAME=payloads
      "-DEXPECTED_METAL_STORE_SNIPPET=(reinterpret_cast<device float4*>(reinterpret_cast<device char*>(payloads) + 16))[1] = first + float4(0.25, 0.5, 0.75, 1.0);"
      -DEXPECTED_METAL_STRUCT=RuntimeVectorPayload
      "-DEXPECTED_METAL_FIELD_SNIPPET=float count;"
      -DEXPECTED_STORAGE_ELEMENT=RuntimeVectorPayload
      -DEXPECTED_STORAGE_STRIDE=0
      -DEXPECTED_STRUCT_FIELD=values
      -DEXPECTED_STRUCT_FIELD_OFFSET=16
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=16
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_runtime_struct_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_RUNTIME_STRUCT_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-runtime-struct-array.cglb
      -DEXPECTED_MODULE=RuntimeStructArrayShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ RuntimeStructPayload*
      -DEXPECTED_METAL_BUFFER_NAME=payloads
      "-DEXPECTED_METAL_STORE_SNIPPET=(reinterpret_cast<device TailParticle*>(reinterpret_cast<device char*>(payloads) + 16))[1].mass = payloads->count + 1.0;"
      -DEXPECTED_METAL_STRUCT=TailParticle
      "-DEXPECTED_METAL_FIELD_SNIPPET=float3 position;"
      -DEXPECTED_STORAGE_ELEMENT=RuntimeStructPayload
      -DEXPECTED_STORAGE_STRIDE=0
      -DEXPECTED_STRUCT_FIELD=particles
      -DEXPECTED_STRUCT_FIELD_OFFSET=16
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=32
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=RuntimeStructArrayShader|artifacts.backendSource=backend/metal/RuntimeStructArrayShader.metal|artifacts.intermediate=backend/metal/RuntimeStructArrayShader.air|artifacts.nativeBinary=backend/metal/RuntimeStructArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=RuntimeStructArrayShader|nativeBinary=backend/metal/RuntimeStructArrayShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=payloads.sourceType=RuntimeStructPayload*|payloads.metalType=device RuntimeStructPayload*|payloads.addressSpace=device|payloads.bindingClass=buffer|payloads.argumentIndex=0|payloads.set=0|payloads.binding=0|payloads.abi=kernelArgument|payloads.storageBufferLayout.elementType=RuntimeStructPayload|payloads.storageBufferLayout.elementSizeBytes=16|payloads.storageBufferLayout.arrayStrideBytes=0|payloads.storageBufferLayout.layout=metal-device|payloads.storageBufferLayout.fields.0.name=count|payloads.storageBufferLayout.fields.0.offsetBytes=0|payloads.storageBufferLayout.fields.1.name=particles|payloads.storageBufferLayout.fields.1.type=TailParticle[]|payloads.storageBufferLayout.fields.1.offsetBytes=16|payloads.storageBufferLayout.fields.1.arrayStrideBytes=32|payloads.storageBufferLayout.fields.1.arrayDimensions.0.kind=runtime"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|runtime-array.kind=layout|runtime-array-field.kind=layout|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_struct_array_field_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_ARRAY_FIELD_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-struct-array-field.cglb
      -DEXPECTED_MODULE=StructArrayFieldComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ Particle*
      -DEXPECTED_METAL_BUFFER_NAME=particles
      "-DEXPECTED_METAL_STORE_SNIPPET=particles[1].mass = firstWeight;"
      -DEXPECTED_METAL_STRUCT=Particle
      "-DEXPECTED_METAL_FIELD_SNIPPET=array<float, 4> weights;"
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=20
      -DEXPECTED_STRUCT_FIELD=weights
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=4
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=StructArrayFieldComputeShader|artifacts.backendSource=backend/metal/StructArrayFieldComputeShader.metal|artifacts.intermediate=backend/metal/StructArrayFieldComputeShader.air|artifacts.nativeBinary=backend/metal/StructArrayFieldComputeShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=StructArrayFieldComputeShader|nativeBinary=backend/metal/StructArrayFieldComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.metalType=device Particle*|particles.addressSpace=device|particles.bindingClass=buffer|particles.argumentIndex=0|particles.set=0|particles.binding=0|particles.abi=kernelArgument|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.elementSizeBytes=20|particles.storageBufferLayout.arrayStrideBytes=20|particles.storageBufferLayout.layout=metal-device|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.type=float[4]|particles.storageBufferLayout.fields.0.offsetBytes=0|particles.storageBufferLayout.fields.0.arrayElementCount=4|particles.storageBufferLayout.fields.0.arrayStrideBytes=4|particles.storageBufferLayout.fields.0.arrayDimensions.0.elementCount=4|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|fixed-array.kind=layout|fixed-array-field.kind=layout|scalar-vector-elements.kind=array|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_struct_constant_array_field_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_CONSTANT_ARRAY_FIELD_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-struct-constant-array-field.cglb
      -DEXPECTED_MODULE=StructConstantArrayFieldComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ Particle*
      -DEXPECTED_METAL_BUFFER_NAME=particles
      "-DEXPECTED_METAL_STORE_SNIPPET=particles[1].mass = firstWeight;"
      -DEXPECTED_METAL_STRUCT=Particle
      "-DEXPECTED_METAL_FIELD_SNIPPET=array<float, WEIGHT_COUNT> weights;"
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=20
      -DEXPECTED_STRUCT_FIELD=weights
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=4
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=4
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=StructConstantArrayFieldComputeShader|artifacts.backendSource=backend/metal/StructConstantArrayFieldComputeShader.metal|artifacts.intermediate=backend/metal/StructConstantArrayFieldComputeShader.air|artifacts.nativeBinary=backend/metal/StructConstantArrayFieldComputeShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=StructConstantArrayFieldComputeShader|nativeBinary=backend/metal/StructConstantArrayFieldComputeShader.metallib|functionConstants.0.name=WEIGHT_COUNT|functionConstants.0.value=4|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.metalType=device Particle*|particles.addressSpace=device|particles.bindingClass=buffer|particles.argumentIndex=0|particles.set=0|particles.binding=0|particles.abi=kernelArgument|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.elementSizeBytes=20|particles.storageBufferLayout.arrayStrideBytes=20|particles.storageBufferLayout.layout=metal-device|particles.storageBufferLayout.fields.0.name=weights|particles.storageBufferLayout.fields.0.type=float[WEIGHT_COUNT]|particles.storageBufferLayout.fields.0.offsetBytes=0|particles.storageBufferLayout.fields.0.arrayElementCount=4|particles.storageBufferLayout.fields.0.arrayStrideBytes=4|particles.storageBufferLayout.fields.0.arrayDimensions.0.source=WEIGHT_COUNT|particles.storageBufferLayout.fields.0.arrayDimensions.0.elementCount=4|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=16"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|fixed-array.kind=layout|fixed-array-field.kind=layout|scalar-vector-elements.kind=array|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_struct_vector_array_field_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_VECTOR_ARRAY_FIELD_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-struct-vector-array-field.cglb
      -DEXPECTED_MODULE=StructVectorArrayFieldComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ Particle*
      -DEXPECTED_METAL_BUFFER_NAME=particles
      "-DEXPECTED_METAL_STORE_SNIPPET=particles[1].positions[0] = lifted;"
      -DEXPECTED_METAL_STRUCT=Particle
      "-DEXPECTED_METAL_FIELD_SNIPPET=array<float3, 2> positions;"
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=48
      -DEXPECTED_STRUCT_FIELD=positions
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=2
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=16
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=StructVectorArrayFieldComputeShader|artifacts.backendSource=backend/metal/StructVectorArrayFieldComputeShader.metal|artifacts.intermediate=backend/metal/StructVectorArrayFieldComputeShader.air|artifacts.nativeBinary=backend/metal/StructVectorArrayFieldComputeShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=StructVectorArrayFieldComputeShader|nativeBinary=backend/metal/StructVectorArrayFieldComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.metalType=device Particle*|particles.addressSpace=device|particles.bindingClass=buffer|particles.argumentIndex=0|particles.set=0|particles.binding=0|particles.abi=kernelArgument|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.elementSizeBytes=36|particles.storageBufferLayout.arrayStrideBytes=48|particles.storageBufferLayout.layout=metal-device|particles.storageBufferLayout.fields.0.name=positions|particles.storageBufferLayout.fields.0.type=vec3[2]|particles.storageBufferLayout.fields.0.offsetBytes=0|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.0.arrayStrideBytes=16|particles.storageBufferLayout.fields.0.arrayDimensions.0.elementCount=2|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=32"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|fixed-array.kind=layout|fixed-array-field.kind=layout|scalar-vector-elements.kind=array|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_struct_nested_array_field_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STRUCT_NESTED_ARRAY_FIELD_COMPUTE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-struct-nested-array-field.cglb
      -DEXPECTED_MODULE=StructNestedArrayFieldComputeShader
      -DEXPECTED_METAL_BUFFER_TYPE=device\ Particle*
      -DEXPECTED_METAL_BUFFER_NAME=particles
      "-DEXPECTED_METAL_STORE_SNIPPET=particles[1].history[0].position = previous;"
      -DEXPECTED_METAL_STRUCT=Particle
      "-DEXPECTED_METAL_FIELD_SNIPPET=array<Transform, 2> history;"
      -DEXPECTED_STORAGE_ELEMENT=Particle
      -DEXPECTED_STORAGE_STRIDE=80
      -DEXPECTED_STRUCT_FIELD=history
      -DEXPECTED_STRUCT_FIELD_OFFSET=0
      -DEXPECTED_STRUCT_FIELD_ARRAY_COUNT=2
      -DEXPECTED_STRUCT_FIELD_ARRAY_STRIDE=32
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=StructNestedArrayFieldComputeShader|artifacts.backendSource=backend/metal/StructNestedArrayFieldComputeShader.metal|artifacts.intermediate=backend/metal/StructNestedArrayFieldComputeShader.air|artifacts.nativeBinary=backend/metal/StructNestedArrayFieldComputeShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=StructNestedArrayFieldComputeShader|nativeBinary=backend/metal/StructNestedArrayFieldComputeShader.metallib|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=1|workgroupSizes.0.y=1|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=1|targetResourceBindings=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=particles.sourceType=Particle*|particles.metalType=device Particle*|particles.addressSpace=device|particles.bindingClass=buffer|particles.argumentIndex=0|particles.set=0|particles.binding=0|particles.abi=kernelArgument|particles.storageBufferLayout.elementType=Particle|particles.storageBufferLayout.elementSizeBytes=68|particles.storageBufferLayout.arrayStrideBytes=80|particles.storageBufferLayout.layout=metal-device|particles.storageBufferLayout.fields.0.name=history|particles.storageBufferLayout.fields.0.type=Transform[2]|particles.storageBufferLayout.fields.0.offsetBytes=0|particles.storageBufferLayout.fields.0.arrayElementCount=2|particles.storageBufferLayout.fields.0.arrayStrideBytes=32|particles.storageBufferLayout.fields.0.arrayDimensions.0.elementCount=2|particles.storageBufferLayout.fields.1.name=mass|particles.storageBufferLayout.fields.1.offsetBytes=64"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|xcrun-metal.kind=toolchain|xcrun-metallib.kind=toolchain|fixed-array.kind=layout|fixed-array-field.kind=layout|compute-kernel.kind=stage|workgroup-size.kind=execution|storage-buffer.kind=resource|storage-buffer-read.kind=operation|storage-buffer-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_image_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-image-native.cglb
      -DEXPECTED_MODULE=MetalStorageImageShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=texture2d_array<uint, access::read_write> maskAtlas [[texture(5)]]"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImageShader|artifacts.backendSource=backend/metal/MetalStorageImageShader.metal|artifacts.intermediate=backend/metal/MetalStorageImageShader.air|artifacts.nativeBinary=backend/metal/MetalStorageImageShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImageShader|nativeBinary=backend/metal/MetalStorageImageShader.metallib|resources.0.kind=storage_image|resources.0.type=image2D|resources.5.type=uimage2DArray|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImage.sourceType=image2D|colorImage.metalType=texture2d<float, access::read_write>|colorImage.bindingClass=texture|colorImage.argumentIndex=0|colorAtlas.sourceType=image2DArray|colorAtlas.metalType=texture2d_array<float, access::read_write>|maskAtlas.sourceType=uimage2DArray|maskAtlas.metalType=texture2d_array<uint, access::read_write>|coordinates.sourceType=int*|coordinates.bindingClass=buffer"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|storage-image.kind=resource|read-write.kind=storageImage|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_image_access_qualifier_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_ACCESS_QUALIFIER_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-image-access-qualifier-native.cglb
      -DEXPECTED_MODULE=MetalStorageImageAccessQualifierShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=texture2d<float, access::read> readColorImage [[texture(0)]]"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImageAccessQualifierShader|artifacts.backendSource=backend/metal/MetalStorageImageAccessQualifierShader.metal|artifacts.intermediate=backend/metal/MetalStorageImageAccessQualifierShader.air|artifacts.nativeBinary=backend/metal/MetalStorageImageAccessQualifierShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImageAccessQualifierShader|nativeBinary=backend/metal/MetalStorageImageAccessQualifierShader.metallib|resources.0.kind=storage_image|resources.0.type=image2D|resources.5.type=image2DArray|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=readColorImage.metalType=texture2d<float, access::read>|writeColorImage.metalType=texture2d<float, access::write>|readWriteColorImage.metalType=texture2d<float, access::read_write>|readColorAtlas.metalType=texture2d_array<float, access::read>|writeColorAtlas.metalType=texture2d_array<float, access::write>|readWriteColorAtlas.metalType=texture2d_array<float, access::read_write>|coordinates.sourceType=int*|coordinates.bindingClass=buffer"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|storage-image.kind=resource|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_image_access_qualifier_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_ACCESS_QUALIFIER_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-image-access-qualifier-descriptor-array-native.cglb
      -DEXPECTED_MODULE=MetalStorageImageAccessQualifierDescriptorArrayShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=array<texture2d<float, access::read>, IMAGE_COUNT> readColorImages [[texture(0)]]"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImageAccessQualifierDescriptorArrayShader|artifacts.backendSource=backend/metal/MetalStorageImageAccessQualifierDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/MetalStorageImageAccessQualifierDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/MetalStorageImageAccessQualifierDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImageAccessQualifierDescriptorArrayShader|nativeBinary=backend/metal/MetalStorageImageAccessQualifierDescriptorArrayShader.metallib|resources.0.kind=storage_image|resources.0.type=image2D[IMAGE_COUNT]|resources.5.type=image2DArray[ATLAS_COUNT]|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=2|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=readColorImages.metalType=array<texture2d<float, access::read>, IMAGE_COUNT>|writeColorImages.metalType=array<texture2d<float, access::write>, IMAGE_COUNT>|readWriteColorImages.metalType=array<texture2d<float, access::read_write>, IMAGE_COUNT>|readColorAtlases.metalType=array<texture2d_array<float, access::read>, ATLAS_COUNT>|writeColorAtlases.metalType=array<texture2d_array<float, access::write>, ATLAS_COUNT>|readWriteColorAtlases.metalType=array<texture2d_array<float, access::read_write>, ATLAS_COUNT>|writeColorImages.argumentIndex=2|readWriteColorImages.argumentIndex=4|readColorAtlases.argumentIndex=6|writeColorAtlases.argumentIndex=8|readWriteColorAtlases.argumentIndex=10|coordinates.sourceType=int*|coordinates.bindingClass=buffer|coordinates.argumentIndex=12"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|storage-image.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  set(CROSSGL_METAL_STORAGE_IMAGE_EXPLICIT_FORMAT_NATIVE_SOURCE_SNIPPET [=[texture2d<float, access::read> readColor [[texture(0)]], texture2d<int, access::read> readLabel [[texture(1)]], texture2d<uint, access::read> readMask [[texture(2)]], texture2d<uint, access::write> writeMask [[texture(3)]]=])
  add_test(NAME cglc_build_metal_storage_image_explicit_format_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-image-explicit-format-native.cglb
      -DEXPECTED_MODULE=StorageImageExplicitFormatShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=${CROSSGL_METAL_STORAGE_IMAGE_EXPLICIT_FORMAT_NATIVE_SOURCE_SNIPPET}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=StorageImageExplicitFormatShader|artifacts.backendSource=backend/metal/StorageImageExplicitFormatShader.metal|artifacts.intermediate=backend/metal/StorageImageExplicitFormatShader.air|artifacts.nativeBinary=backend/metal/StorageImageExplicitFormatShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=StorageImageExplicitFormatShader|nativeBinary=backend/metal/StorageImageExplicitFormatShader.metallib|resources.0.kind=storage_image|resources.0.storageImageFormat=r32f|resources.1.storageImageFormat=r32i|resources.2.storageImageFormat=r32ui|resources.3.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=readColor.sourceType=image2D|readColor.metalType=texture2d<float, access::read>|readColor.bindingClass=texture|readColor.argumentIndex=0|readColor.storageImageFormat=r32f|readLabel.sourceType=iimage2D|readLabel.metalType=texture2d<int, access::read>|readLabel.argumentIndex=1|readLabel.storageImageFormat=r32i|readMask.sourceType=uimage2D|readMask.metalType=texture2d<uint, access::read>|readMask.argumentIndex=2|readMask.storageImageFormat=r32ui|writeMask.sourceType=uimage2D|writeMask.metalType=texture2d<uint, access::write>|writeMask.argumentIndex=3|writeMask.storageImageFormat=r32ui|colors.sourceType=vec4*|colors.bindingClass=buffer|colors.argumentIndex=4|labels.sourceType=ivec4*|labels.bindingClass=buffer|labels.argumentIndex=5"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|storage-image.kind=resource|read-only.kind=storageImage|write-only.kind=storageImage|2d-dimension.kind=storageImage|r32f-format.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|storage-image-read.kind=operation|storage-image-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_image_atomic_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_STORAGE_IMAGE_ATOMIC_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-image-atomic-native.cglb
      -DEXPECTED_MODULE=StorageImageAtomicShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=int signedOld = signedCounters.atomic_fetch_add(uint2(pixel), int4(1)).x;"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=StorageImageAtomicShader|artifacts.backendSource=backend/metal/StorageImageAtomicShader.metal|artifacts.intermediate=backend/metal/StorageImageAtomicShader.air|artifacts.nativeBinary=backend/metal/StorageImageAtomicShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=StorageImageAtomicShader|nativeBinary=backend/metal/StorageImageAtomicShader.metallib|resources.0.kind=storage_image|resources.0.type=iimage2D|resources.0.storageImageFormat=r32i|resources.1.type=uimage2D|resources.1.storageImageFormat=r32ui|resources.2.type=iimage2DArray|resources.3.type=uimage2DArray|resources.3.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=6|targetResourceBindings=6|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=signedCounters.sourceType=iimage2D|signedCounters.metalType=texture2d<int, access::read_write>|signedCounters.bindingClass=texture|signedCounters.argumentIndex=0|signedCounters.storageImageFormat=r32i|unsignedCounters.sourceType=uimage2D|unsignedCounters.metalType=texture2d<uint, access::read_write>|unsignedCounters.storageImageFormat=r32ui|signedAtlas.sourceType=iimage2DArray|signedAtlas.metalType=texture2d_array<int, access::read_write>|signedAtlas.storageImageFormat=r32i|unsignedAtlas.sourceType=uimage2DArray|unsignedAtlas.metalType=texture2d_array<uint, access::read_write>|unsignedAtlas.storageImageFormat=r32ui|signedResults.bindingClass=buffer|unsignedResults.bindingClass=buffer"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|storage-image.kind=resource|read-write.kind=storageImage|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|storage-buffer.kind=resource|storage-image-read.kind=operation|storage-image-write.kind=operation|storage-image-atomic-add.kind=operation|storage-image-atomic-exchange.kind=operation|storage-image-atomic-min.kind=operation|storage-image-atomic-max.kind=operation|storage-image-atomic-and.kind=operation|storage-image-atomic-or.kind=operation|storage-image-atomic-xor.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_image_atomic_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-image-atomic-descriptor-array-native.cglb
      -DEXPECTED_MODULE=MetalStorageImageAtomicDescriptorArrayShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=array<texture2d_array<uint, access::read_write>, IMAGE_COUNT> unsignedAtlases [[texture(7)]]"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImageAtomicDescriptorArrayShader|artifacts.backendSource=backend/metal/MetalStorageImageAtomicDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/MetalStorageImageAtomicDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/MetalStorageImageAtomicDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImageAtomicDescriptorArrayShader|nativeBinary=backend/metal/MetalStorageImageAtomicDescriptorArrayShader.metallib|functionConstants.0.name=IMAGE_COUNT|functionConstants.0.value=2|resources.1.kind=storage_image|resources.1.type=iimage2D[IMAGE_COUNT]|resources.1.storageImageFormat=r32i|resources.2.type=uimage2D[IMAGE_COUNT]|resources.2.storageImageFormat=r32ui|resources.3.type=iimage2DArray[IMAGE_COUNT]|resources.4.type=uimage2DArray[IMAGE_COUNT]|resources.4.storageImageFormat=r32ui|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=2|workgroupSizes.0.y=2|workgroupSizes.0.z=2"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=7|targetResourceBindings=7|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=slots.bindingClass=buffer|slots.argumentIndex=0|signedCounters.sourceType=iimage2D[IMAGE_COUNT]|signedCounters.metalType=array<texture2d<int, access::read_write>, IMAGE_COUNT>|signedCounters.bindingClass=texture|signedCounters.argumentIndex=1|signedCounters.arraySize=IMAGE_COUNT|signedCounters.arrayElementCount=2|unsignedCounters.metalType=array<texture2d<uint, access::read_write>, IMAGE_COUNT>|unsignedCounters.argumentIndex=3|signedAtlases.metalType=array<texture2d_array<int, access::read_write>, IMAGE_COUNT>|signedAtlases.argumentIndex=5|unsignedAtlases.metalType=array<texture2d_array<uint, access::read_write>, IMAGE_COUNT>|unsignedAtlases.argumentIndex=7|signedResults.bindingClass=buffer|signedResults.argumentIndex=9|unsignedResults.bindingClass=buffer|unsignedResults.argumentIndex=10"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|MSL.kind=sourceLanguage|metallib.kind=binaryFormat|storage-image.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|read-write.kind=storageImage|2d-dimension.kind=storageImage|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|r32i-format.kind=storageImage|r32ui-format.kind=storageImage|storage-buffer.kind=resource|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|storage-image-read.kind=operation|storage-image-write.kind=operation|storage-image-atomic-add.kind=operation|storage-image-atomic-exchange.kind=operation|storage-image-atomic-min.kind=operation|storage-image-atomic-max.kind=operation|storage-image-atomic-and.kind=operation|storage-image-atomic-or.kind=operation|storage-image-atomic-xor.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_image_2d_nonuniform_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_2D_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-image-2d-nonuniform-descriptor-array-native.cglb
      -DEXPECTED_MODULE=MetalStorageImage2DNonUniformDescriptorArrayShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=array<texture2d<float, access::read_write>, IMAGE_COUNT> colorImages [[texture(0)]]"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImage2DNonUniformDescriptorArrayShader|artifacts.backendSource=backend/metal/MetalStorageImage2DNonUniformDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/MetalStorageImage2DNonUniformDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/MetalStorageImage2DNonUniformDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImage2DNonUniformDescriptorArrayShader|nativeBinary=backend/metal/MetalStorageImage2DNonUniformDescriptorArrayShader.metallib|resources.0.kind=storage_image|resources.0.type=image2D[IMAGE_COUNT]|resources.2.type=uimage2D[IMAGE_COUNT]|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorImages.sourceType=image2D[IMAGE_COUNT]|colorImages.metalType=array<texture2d<float, access::read_write>, IMAGE_COUNT>|colorImages.bindingClass=texture|colorImages.arraySize=IMAGE_COUNT|labelImages.metalType=array<texture2d<int, access::read_write>, IMAGE_COUNT>|maskImages.metalType=array<texture2d<uint, access::read_write>, IMAGE_COUNT>|coordinates.sourceType=int*|coordinates.bindingClass=buffer"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|storage-image.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|storage-image-read.kind=operation|storage-image-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  add_test(NAME cglc_build_metal_storage_image_2d_array_nonuniform_descriptor_array_native
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_STORAGE_IMAGE_2D_ARRAY_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-image-2d-array-nonuniform-descriptor-array-native.cglb
      -DEXPECTED_MODULE=MetalStorageImage2DArrayNonUniformDescriptorArrayShader
      "-DEXPECTED_METAL_SOURCE_SNIPPET=array<texture2d_array<float, access::read_write>, ATLAS_COUNT> colorAtlases [[texture(0)]]"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImage2DArrayNonUniformDescriptorArrayShader|artifacts.backendSource=backend/metal/MetalStorageImage2DArrayNonUniformDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/MetalStorageImage2DArrayNonUniformDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/MetalStorageImage2DArrayNonUniformDescriptorArrayShader.metallib"
      "-DEXPECTED_REFLECTION_JSON_FIELDS=schemaVersion=1|target=metal|module=MetalStorageImage2DArrayNonUniformDescriptorArrayShader|nativeBinary=backend/metal/MetalStorageImage2DArrayNonUniformDescriptorArrayShader.metallib|resources.0.kind=storage_image|resources.0.type=image2DArray[ATLAS_COUNT]|resources.2.type=uimage2DArray[ATLAS_COUNT]|workgroupSizes.0.entryPoint=compute_main|workgroupSizes.0.x=4|workgroupSizes.0.y=4|workgroupSizes.0.z=1"
      "-DEXPECTED_REFLECTION_JSON_ARRAY_LENGTHS=resources=4|targetResourceBindings=4|functionConstants=1|workgroupSizes=1"
      "-DEXPECTED_REFLECTION_TARGET_FIELDS=colorAtlases.sourceType=image2DArray[ATLAS_COUNT]|colorAtlases.metalType=array<texture2d_array<float, access::read_write>, ATLAS_COUNT>|colorAtlases.bindingClass=texture|colorAtlases.arraySize=ATLAS_COUNT|labelAtlases.metalType=array<texture2d_array<int, access::read_write>, ATLAS_COUNT>|maskAtlases.metalType=array<texture2d_array<uint, access::read_write>, ATLAS_COUNT>|coordinates.sourceType=int*|coordinates.bindingClass=buffer"
      "-DEXPECTED_REFLECTION_FEATURE_FIELDS=native-metal-package.kind=backend|storage-image.kind=resource|descriptor-array.kind=resource|fixed-array.kind=layout|2d_array-dimension.kind=storageImage|array-dimension.kind=storageImage|nonuniform-descriptor-index.kind=operation|nonuniform-storage-image-descriptor-index.kind=operation|storage-image-read.kind=operation|storage-image-write.kind=operation"
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
      -DMODE=metal-build
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
  crossgl_label_new_optional_native_tests(metal
    "${CROSSGL_METAL_NATIVE_TESTS_BEFORE}")
else()
  crossgl_add_optional_native_skip_test(
    NAME cglc_metal_toolchain_native_smoke_unavailable
    TARGET metal
    REASON "optional Metal toolchain smoke requires Apple xcrun, metal, and metallib"
    REQUIRED_VARS CROSSGL_XCRUN CROSSGL_METAL CROSSGL_METALLIB)
  crossgl_add_optional_native_skip_test(
    NAME cglc_build_metal_native_tools_unavailable
    TARGET metal
    REQUIRED_VARS CROSSGL_XCRUN CROSSGL_METAL CROSSGL_METALLIB)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_inspect_json_schema_metal_native_unavailable
    TARGET metal
    REQUIRED_VARS CROSSGL_XCRUN CROSSGL_METAL CROSSGL_METALLIB)
endif()
