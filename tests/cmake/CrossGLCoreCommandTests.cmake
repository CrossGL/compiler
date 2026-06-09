add_test(NAME crossgl_unit_tests COMMAND crossgl_unit_tests)
add_executable(crossgl_toolchain_process_capture_tests
  ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ToolchainProcessCaptureTests.cpp)
target_link_libraries(crossgl_toolchain_process_capture_tests
  PRIVATE crossgl_compiler)
add_test(NAME crossgl_toolchain_process_capture_tests
  COMMAND crossgl_toolchain_process_capture_tests)
add_test(NAME cglc_doctor COMMAND cglc doctor)
set_tests_properties(cglc_doctor
  PROPERTIES
    PASS_REGULAR_EXPRESSION
      "MLIR native pipeline: (available|unavailable) \\(requires MLIR configured and CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON\\)")
if(NOT CROSSGL_ENABLE_MLIR_EXPERIMENTAL)
  add_test(NAME crossgl_mlir_experimental_gate_default_off
    COMMAND ${CMAKE_COMMAND}
      "-DCACHE_FILE=${CMAKE_BINARY_DIR}/CMakeCache.txt"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CheckMLIRExperimentalGateDefault.cmake)

  add_test(NAME cglc_doctor_mlir_experimental_gate_default_off
    COMMAND cglc doctor)
  set_tests_properties(cglc_doctor_mlir_experimental_gate_default_off
    PROPERTIES
      PASS_REGULAR_EXPRESSION
        "MLIR native pipeline: unavailable \\(requires MLIR configured and CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON\\)")
endif()
add_test(NAME cglc_planned_failure_requires_diagnostics_json
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DTARGET=directx
    -DMODE=planned-build-failure
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
set_tests_properties(cglc_planned_failure_requires_diagnostics_json
  PROPERTIES
    WILL_FAIL TRUE
    PASS_REGULAR_EXPRESSION "planned-build-failure tests must define parsed diagnostics JSON expectations")
add_test(NAME cglc_doctor_json_toolchain
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DMODE=doctor-json
    "-DEXPECTED_JSON_PATHS=toolchain.hasLLVM|toolchain.llvmConfigured|toolchain.mlirConfigured|toolchain.tools.0.evidenceStatus|toolchain.tools.0.source|toolchain.tools.0.resolvedPath|toolchain.tools.0.probeStatus|toolchain.tools.0.version|toolchain.tools.0.versionDetail"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|toolchain.tools.0.name=cmake|targetExplanation=null"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
if(NOT CROSSGL_ENABLE_MLIR_EXPERIMENTAL)
  add_test(NAME cglc_doctor_json_mlir_experimental_gate_default_off
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DMODE=doctor-json
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|toolchain.mlirNativePipelineAvailable=false|targetExplanation=null"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
endif()
crossgl_add_python_expect_test(
  NAME cglc_doctor_json_schema_toolchain
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DMODE=doctor-json
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/doctor-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_PATHS=toolchain.hasLLVM|toolchain.llvmConfigured|toolchain.mlirConfigured|toolchain.tools.0.evidenceStatus|toolchain.tools.0.source|toolchain.tools.0.resolvedPath|toolchain.tools.0.probeStatus|toolchain.tools.0.version|toolchain.tools.0.versionDetail"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|toolchain.tools.0.name=cmake|targetExplanation=null")

set(CROSSGL_DOCTOR_FAKE_PATH_TOOLS
    "dxc|glslangValidator|spirv-as|spirv-val|spirv-opt|spirv-dis")
if(APPLE)
  string(APPEND CROSSGL_DOCTOR_FAKE_PATH_TOOLS "|xcrun")
  set(CROSSGL_DOCTOR_FAKE_METAL_TOOL_SOURCE xcrun)
  set(CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RECOMMENDED_TARGET metal)
  set(CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET metal)
  set(CROSSGL_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET metal)
elseif(WIN32)
  string(APPEND CROSSGL_DOCTOR_FAKE_PATH_TOOLS "|metal|metallib")
  set(CROSSGL_DOCTOR_FAKE_METAL_TOOL_SOURCE PATH)
  set(CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RECOMMENDED_TARGET metal)
  set(CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET metal)
  set(CROSSGL_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET metal)
else()
  string(APPEND CROSSGL_DOCTOR_FAKE_PATH_TOOLS "|metal|metallib")
  set(CROSSGL_DOCTOR_FAKE_METAL_TOOL_SOURCE PATH)
  set(CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RECOMMENDED_TARGET vulkan)
  set(CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET vulkan)
  set(CROSSGL_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET vulkan)
endif()

add_test(NAME cglc_doctor_json_toolchain_path_tools_available
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DMODE=doctor-json
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/doctor-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    -DPYTHON3_EXECUTABLE=${CROSSGL_PYTHON3}
    "-DFAKE_TOOLCHAIN_TOOLS=${CROSSGL_DOCTOR_FAKE_PATH_TOOLS}"
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|targetExplanation=null"
    -DTARGET_RECORD_ARRAY_FIELD=toolchain.tools
    -DTARGET_RECORD_KEY_FIELD=name
    "-DEXPECTED_TARGET_FIELDS=dxc.available=true|dxc.evidenceStatus=version-captured|dxc.source=PATH|dxc.probeStatus=succeeded|dxc.version=fake dxc 1.0|glslangValidator.available=true|glslangValidator.evidenceStatus=version-captured|glslangValidator.source=PATH|glslangValidator.probeStatus=succeeded|glslangValidator.version=fake glslangValidator 1.0|spirv-as.available=true|spirv-as.evidenceStatus=version-captured|spirv-as.source=PATH|spirv-as.probeStatus=succeeded|spirv-as.version=fake spirv-as 1.0|spirv-val.available=true|spirv-val.evidenceStatus=version-captured|spirv-val.source=PATH|spirv-val.probeStatus=succeeded|spirv-val.version=fake spirv-val 1.0|spirv-opt.available=true|spirv-opt.evidenceStatus=version-captured|spirv-opt.source=PATH|spirv-opt.probeStatus=succeeded|spirv-opt.version=fake spirv-opt 1.0|spirv-opt.detail=Vulkan optimizer policy: O0/O1 record skipped-disabled and do not invoke spirv-opt\; O2 invokes spirv-opt --target-env=vulkan1.2 -O when found and records skipped-tool-missing when absent|spirv-dis.available=true|spirv-dis.evidenceStatus=version-captured|spirv-dis.source=PATH|spirv-dis.probeStatus=succeeded|spirv-dis.version=fake spirv-dis 1.0|metal.available=true|metal.evidenceStatus=version-captured|metal.source=${CROSSGL_DOCTOR_FAKE_METAL_TOOL_SOURCE}|metal.probeStatus=succeeded|metal.version=fake metal 1.0|metallib.available=true|metallib.evidenceStatus=version-captured|metallib.source=${CROSSGL_DOCTOR_FAKE_METAL_TOOL_SOURCE}|metallib.probeStatus=succeeded|metallib.version=fake metallib 1.0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_doctor_json_toolchain_path_tools_missing
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DMODE=doctor-json
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/doctor-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    -DPYTHON3_EXECUTABLE=${CROSSGL_PYTHON3}
    -DFAKE_TOOLCHAIN_TOOLS=
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|targetExplanation=null"
    -DTARGET_RECORD_ARRAY_FIELD=toolchain.tools
    -DTARGET_RECORD_KEY_FIELD=name
    "-DEXPECTED_TARGET_FIELDS=dxc.available=false|dxc.evidenceStatus=tool-missing|dxc.source=not-found|dxc.resolvedPath=|dxc.probeStatus=unavailable|glslangValidator.available=false|glslangValidator.evidenceStatus=tool-missing|glslangValidator.source=not-found|glslangValidator.resolvedPath=|glslangValidator.probeStatus=unavailable|spirv-as.available=false|spirv-as.evidenceStatus=tool-missing|spirv-as.source=not-found|spirv-as.resolvedPath=|spirv-as.probeStatus=unavailable|spirv-val.available=false|spirv-val.evidenceStatus=tool-missing|spirv-val.source=not-found|spirv-val.resolvedPath=|spirv-val.probeStatus=unavailable|spirv-opt.available=false|spirv-opt.evidenceStatus=tool-missing|spirv-opt.source=not-found|spirv-opt.resolvedPath=|spirv-opt.probeStatus=unavailable|spirv-opt.detail=Vulkan optimizer policy: O0/O1 record skipped-disabled and do not invoke spirv-opt\; O2 invokes spirv-opt --target-env=vulkan1.2 -O when found and records skipped-tool-missing when absent|spirv-dis.available=false|spirv-dis.evidenceStatus=tool-missing|spirv-dis.source=not-found|spirv-dis.resolvedPath=|spirv-dis.probeStatus=unavailable|metal.available=false|metal.evidenceStatus=tool-missing|metal.source=not-found|metal.resolvedPath=|metal.probeStatus=unavailable|metallib.available=false|metallib.evidenceStatus=tool-missing|metallib.source=not-found|metallib.resolvedPath=|metallib.probeStatus=unavailable"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

set(CROSSGL_DOCTOR_FAKE_VERSION_FAILED_EXPECTATIONS
    "dxc.available=true|dxc.evidenceStatus=probe-failed|dxc.probeStatus=failed|dxc.version=|dxc.versionDetail=exit 2: fake dxc probe failed|glslangValidator.available=true|glslangValidator.evidenceStatus=probe-failed|glslangValidator.probeStatus=failed|glslangValidator.version=|glslangValidator.versionDetail=exit 2: fake glslangValidator probe failed|spirv-as.available=true|spirv-as.evidenceStatus=probe-failed|spirv-as.probeStatus=failed|spirv-as.version=|spirv-as.versionDetail=exit 2: fake spirv-as probe failed|spirv-val.available=true|spirv-val.evidenceStatus=probe-failed|spirv-val.probeStatus=failed|spirv-val.version=|spirv-val.versionDetail=exit 2: fake spirv-val probe failed|spirv-opt.available=true|spirv-opt.evidenceStatus=probe-failed|spirv-opt.probeStatus=failed|spirv-opt.version=|spirv-opt.versionDetail=exit 2: fake spirv-opt probe failed|metal.available=true|metal.evidenceStatus=probe-failed|metal.probeStatus=failed|metal.version=|metal.versionDetail=exit 2: fake metal probe failed|metallib.available=true|metallib.evidenceStatus=probe-failed|metallib.probeStatus=failed|metallib.version=|metallib.versionDetail=exit 2: fake metallib probe failed")
add_test(NAME cglc_doctor_json_toolchain_path_tools_probe_failed
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DMODE=doctor-json
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/doctor-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    -DPYTHON3_EXECUTABLE=${CROSSGL_PYTHON3}
    "-DFAKE_TOOLCHAIN_TOOLS=${CROSSGL_DOCTOR_FAKE_PATH_TOOLS}"
    -DFAKE_TOOLCHAIN_VERSION_MODE=failed
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|targetExplanation=null"
    -DTARGET_RECORD_ARRAY_FIELD=toolchain.tools
    -DTARGET_RECORD_KEY_FIELD=name
    "-DEXPECTED_TARGET_FIELDS=${CROSSGL_DOCTOR_FAKE_VERSION_FAILED_EXPECTATIONS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

set(CROSSGL_DOCTOR_FAKE_VERSION_UNKNOWN_EXPECTATIONS
    "dxc.available=true|dxc.evidenceStatus=version-unknown|dxc.probeStatus=version-unknown|dxc.version=|dxc.versionDetail=version probe produced no output|glslangValidator.available=true|glslangValidator.evidenceStatus=version-unknown|glslangValidator.probeStatus=version-unknown|glslangValidator.version=|glslangValidator.versionDetail=version probe produced no output|spirv-as.available=true|spirv-as.evidenceStatus=version-unknown|spirv-as.probeStatus=version-unknown|spirv-as.version=|spirv-as.versionDetail=version probe produced no output|spirv-val.available=true|spirv-val.evidenceStatus=version-unknown|spirv-val.probeStatus=version-unknown|spirv-val.version=|spirv-val.versionDetail=version probe produced no output|spirv-opt.available=true|spirv-opt.evidenceStatus=version-unknown|spirv-opt.probeStatus=version-unknown|spirv-opt.version=|spirv-opt.versionDetail=version probe produced no output|metal.available=true|metal.evidenceStatus=version-unknown|metal.probeStatus=version-unknown|metal.version=|metal.versionDetail=version probe produced no output|metallib.available=true|metallib.evidenceStatus=version-unknown|metallib.probeStatus=version-unknown|metallib.version=|metallib.versionDetail=version probe produced no output")
add_test(NAME cglc_doctor_json_toolchain_path_tools_version_unknown
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DMODE=doctor-json
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/doctor-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    -DPYTHON3_EXECUTABLE=${CROSSGL_PYTHON3}
    "-DFAKE_TOOLCHAIN_TOOLS=${CROSSGL_DOCTOR_FAKE_PATH_TOOLS}"
    -DFAKE_TOOLCHAIN_VERSION_MODE=unknown
    -DTOOLCHAIN_DISABLE_FALLBACK=ON
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|targetExplanation=null"
    -DTARGET_RECORD_ARRAY_FIELD=toolchain.tools
    -DTARGET_RECORD_KEY_FIELD=name
    "-DEXPECTED_TARGET_FIELDS=${CROSSGL_DOCTOR_FAKE_VERSION_UNKNOWN_EXPECTATIONS}"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_doctor_target_package_decisions
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DMODE=doctor-input
    "-DMUST_CONTAIN=Target package decisions"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_doctor_json_target_package_decisions
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DMODE=doctor-json
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|targetExplanation.schemaVersion=1|targetExplanation.module=Texture2DShadowCompareLodManualKernelListShader"
    -DTARGET_EXPLANATION_ROOT=targetExplanation
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.packageBuildSupported=true|metal.packageMode=native|metal.packageDecisionReason=native-package-available|metal.packageRankScore=0|vulkan.nativeImplemented=true|vulkan.packageBuildSupported=true|vulkan.packageMode=native|vulkan.packageDecisionReason=native-package-available|vulkan.packageRankScore=0|directx.packageMode=source-package|directx.packageDecisionReason=source-package-available|directx.packageBuildSupported=true|opengl.packageMode=source-package"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.missingCapabilities=directx.backend.native-dxil-package|opengl.missingCapabilities=opengl.backend.native-glsl-package"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_doctor_json_native_predicate_unsupported
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_RUNTIME_TEXTURE_RESOURCE_ARRAY_CONFLICT_SHADER}
    -DMODE=doctor-json
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|targetExplanation.schemaVersion=1|targetExplanation.module=DirectXRuntimeTextureResourceArrayConflictShader|targetExplanation.buildableTargetCount=1|targetExplanation.recommendedTarget=metal|targetExplanation.recommendedPackageMode=native"
    -DTARGET_EXPLANATION_ROOT=targetExplanation
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.sourcePackageSupported=false|metal.packageBuildSupported=true|metal.packageMode=native|metal.packageDecisionReason=native-package-available|metal.packageRankScore=0|metal.missingCapabilityCount=0|vulkan.nativeImplemented=true|vulkan.sourcePackageSupported=false|vulkan.packageBuildSupported=false|vulkan.packageMode=unsupported|vulkan.packageDecisionReason=unsupported|vulkan.packageRankScore=2|vulkan.missingCapabilityCount=2|directx.nativeImplemented=true|directx.sourcePackageSupported=false|directx.packageBuildSupported=false|directx.packageMode=unsupported|directx.packageDecisionReason=unsupported|directx.packageRankScore=2|directx.missingCapabilityCount=4|opengl.sourcePackageSupported=false|opengl.packageBuildSupported=false|opengl.packageMode=unsupported|opengl.packageDecisionReason=unsupported|opengl.packageRankScore=2|opengl.missingCapabilityCount=2"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.backend.native-metal-package|metal.requiredCapabilities=metal.resource.runtime-descriptor-array|metal.requiredCapabilities=metal.resource.runtime-texture-descriptor-array|metal.requiredCapabilities=metal.layout.runtime-array|vulkan.missingCapabilities=vulkan.backend.vulkan-prototype-package|vulkan.missingCapabilities=vulkan.diagnostic.vulkan.prototype-unsupported-runtime-resource-array|directx.missingCapabilities=directx.backend.native-dxil-package|directx.missingCapabilities=directx.toolchain.dxc|directx.missingCapabilities=directx.validation.dxil-validator|directx.missingCapabilities=directx.diagnostic.directx.unsupported-runtime-resource-array|opengl.missingCapabilities=opengl.backend.glsl-lowering|opengl.missingCapabilities=opengl.diagnostic.opengl.unsupported-runtime-resource-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_doctor_json_directx_source_package_predicate_supported
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_MIXED_SAMPLER_USAGE_UNSUPPORTED_SHADER}
    -DMODE=doctor-json
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|targetExplanation.schemaVersion=1|targetExplanation.module=DirectXMixedSamplerUsageUnsupportedShader"
    -DTARGET_EXPLANATION_ROOT=targetExplanation
    "-DEXPECTED_TARGET_FIELDS=directx.nativeImplemented=true|directx.sourcePackageSupported=true|directx.packageBuildSupported=true|directx.packageMode=source-package|directx.packageDecisionReason=source-package-available|directx.packageRankScore=1|opengl.sourcePackageSupported=true|opengl.packageBuildSupported=true|opengl.packageMode=source-package|opengl.packageDecisionReason=source-package-available|opengl.packageRankScore=1"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.missingCapabilities=directx.backend.native-dxil-package|opengl.missingCapabilities=opengl.backend.native-glsl-package"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
add_test(NAME cglc_doctor_json_opengl_source_package_predicate_unsupported
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_CUBE_SHADOW_COMPARE_LOD_UNSUPPORTED_SHADER}
    -DMODE=doctor-json
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|targetExplanation.schemaVersion=1|targetExplanation.module=TextureCubeShadowCompareLodUnsupportedShader"
    -DTARGET_EXPLANATION_ROOT=targetExplanation
    "-DEXPECTED_TARGET_FIELDS=directx.sourcePackageSupported=true|directx.packageBuildSupported=true|directx.packageMode=source-package|directx.packageDecisionReason=source-package-available|directx.packageRankScore=1|opengl.nativeImplemented=false|opengl.sourcePackageSupported=true|opengl.packageBuildSupported=true|opengl.packageMode=source-package|opengl.packageDecisionReason=source-package-available|opengl.packageRankScore=1|opengl.missingCapabilityCount=3"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.missingCapabilities=directx.backend.native-dxil-package|opengl.missingCapabilities=opengl.backend.native-glsl-package|opengl.missingCapabilities=opengl.toolchain.opengl-driver|opengl.missingCapabilities=opengl.validation.glsl-program-validation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_add_python_expect_test(
  NAME cglc_doctor_json_schema_target_explanation
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TEXTURE_2D_SHADOW_COMPARE_LOD_MANUAL_KERNEL_LIST_SHADER}
    -DMODE=doctor-json
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/doctor-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|targetExplanation.schemaVersion=1|targetExplanation.module=Texture2DShadowCompareLodManualKernelListShader|targetExplanation.recommendedPackageMode=native"
    -DTARGET_EXPLANATION_ROOT=targetExplanation
    "-DEXPECTED_TARGET_FIELDS=metal.packageMode=native|vulkan.packageMode=native|directx.packageMode=source-package|opengl.packageMode=source-package"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.missingCapabilities=directx.backend.native-dxil-package|opengl.missingCapabilities=opengl.backend.native-glsl-package")

add_test(NAME cglc_doctor_json_directx_graphics_storage_buffer_source_package_evidence
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SHADER}
    -DMODE=doctor-json
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|targetExplanation.schemaVersion=1|targetExplanation.module=DirectXGraphicsStorageBufferResourceShader|targetExplanation.buildableTargetCount=3|targetExplanation.recommendedTarget=${CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RECOMMENDED_TARGET}|targetExplanation.recommendedPackageMode=native"
    -DTARGET_EXPLANATION_ROOT=targetExplanation
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.packageBuildSupported=true|metal.packageMode=native|metal.packageDecisionReason=native-package-available|metal.missingCapabilityCount=0|vulkan.nativeImplemented=true|vulkan.sourcePackageSupported=false|vulkan.packageBuildSupported=true|vulkan.packageMode=native|vulkan.packageDecisionReason=native-package-available|vulkan.requiredCapabilityCount=15|vulkan.missingCapabilityCount=0|directx.nativeImplemented=true|directx.sourcePackageSupported=true|directx.packageBuildSupported=true|directx.packageMode=source-package|directx.packageDecisionReason=source-package-available|directx.requiredCapabilityCount=14|directx.missingCapabilityCount=3|opengl.nativeImplemented=false|opengl.sourcePackageSupported=false|opengl.packageBuildSupported=false|opengl.packageMode=unsupported|opengl.packageDecisionReason=unsupported|opengl.missingCapabilityCount=2"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=vulkan.requiredCapabilities=vulkan.resource.storage-buffer|vulkan.requiredCapabilities=vulkan.layout.vector-storage-buffer|vulkan.requiredCapabilities=vulkan.operation.storage-buffer-read|vulkan.requiredCapabilities=vulkan.operation.storage-buffer-write|directx.requiredCapabilities=directx.resource.storage-buffer|directx.requiredCapabilities=directx.layout.vector-storage-buffer|directx.requiredCapabilities=directx.operation.storage-buffer-read|directx.requiredCapabilities=directx.operation.storage-buffer-write|directx.missingCapabilities=directx.backend.native-dxil-package|directx.missingCapabilities=directx.toolchain.dxc|directx.missingCapabilities=directx.validation.dxil-validator|opengl.missingCapabilities=opengl.backend.glsl-lowering|opengl.missingCapabilities=opengl.diagnostic.opengl.source-unsupported"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_doctor_json_metal_graphics_descriptor_array_native_evidence
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_SHADER}
    -DMODE=doctor-json
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|targetExplanation.schemaVersion=1|targetExplanation.module=MetalGraphicsDescriptorArrayShader|targetExplanation.buildableTargetCount=2|targetExplanation.recommendedTarget=${CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET}|targetExplanation.recommendedPackageMode=native"
    -DTARGET_EXPLANATION_ROOT=targetExplanation
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.sourcePackageSupported=false|metal.packageBuildSupported=true|metal.packageMode=native|metal.packageDecisionReason=native-package-available|metal.requiredCapabilityCount=21|metal.missingCapabilityCount=0"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.backend.native-metal-package|metal.requiredCapabilities=metal.resource.descriptor-array|metal.requiredCapabilities=metal.layout.fixed-array|metal.requiredCapabilities=metal.texture.depth-compare-format|metal.requiredCapabilities=metal.operation.texture-shadow-compare-explicit-lod"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_doctor_json_opengl_graphics_descriptor_array_source_package_evidence
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_DESCRIPTOR_ARRAY_RESOURCES_SHADER}
    -DMODE=doctor-json
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|targetExplanation.schemaVersion=1|targetExplanation.module=OpenGLGraphicsDescriptorArrayResourcesShader|targetExplanation.buildableTargetCount=4"
    -DTARGET_EXPLANATION_ROOT=targetExplanation
    "-DEXPECTED_TARGET_FIELDS=opengl.nativeImplemented=false|opengl.sourcePackageSupported=true|opengl.packageBuildSupported=true|opengl.packageMode=source-package|opengl.packageDecisionReason=source-package-available|opengl.requiredCapabilityCount=16|opengl.missingCapabilityCount=3"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=opengl.requiredCapabilities=opengl.resource.sampled-texture|opengl.requiredCapabilities=opengl.resource.sampler-state|opengl.requiredCapabilities=opengl.resource.descriptor-array|opengl.requiredCapabilities=opengl.layout.fixed-array|opengl.missingCapabilities=opengl.backend.native-glsl-package|opengl.missingCapabilities=opengl.toolchain.opengl-driver|opengl.missingCapabilities=opengl.validation.glsl-program-validation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_doctor_json_vulkan_runtime_texture_sampler_descriptor_array_native_evidence
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_POLICY_SHADER}
    -DMODE=doctor-json
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|targetExplanation.schemaVersion=1|targetExplanation.module=VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader|targetExplanation.buildableTargetCount=3|targetExplanation.recommendedTarget=${CROSSGL_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET}|targetExplanation.recommendedPackageMode=native"
    -DTARGET_EXPLANATION_ROOT=targetExplanation
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.sourcePackageSupported=false|metal.packageBuildSupported=true|metal.packageMode=native|metal.packageDecisionReason=native-package-available|metal.requiredCapabilityCount=22|metal.missingCapabilityCount=0|vulkan.nativeImplemented=true|vulkan.sourcePackageSupported=false|vulkan.packageBuildSupported=true|vulkan.packageMode=native|vulkan.packageDecisionReason=native-package-available|vulkan.requiredCapabilityCount=22|vulkan.missingCapabilityCount=0"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.backend.native-metal-package|metal.requiredCapabilities=metal.resource.runtime-descriptor-array|metal.requiredCapabilities=metal.resource.runtime-texture-descriptor-array|metal.requiredCapabilities=metal.resource.runtime-sampler-descriptor-array|metal.requiredCapabilities=metal.layout.runtime-array|metal.requiredCapabilities=metal.resource.descriptor-array|vulkan.requiredCapabilities=vulkan.backend.vulkan-prototype-package|vulkan.requiredCapabilities=vulkan.resource.runtime-descriptor-array|vulkan.requiredCapabilities=vulkan.resource.runtime-texture-descriptor-array|vulkan.requiredCapabilities=vulkan.resource.runtime-sampler-descriptor-array|vulkan.requiredCapabilities=vulkan.layout.runtime-array|vulkan.requiredCapabilities=vulkan.resource.descriptor-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_add_python_expect_test(
  NAME cglc_package_inspect_graphics_resources_reflection_contract
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_RESOURCES_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-package-inspect-graphics-resources-reflection.cglb
    -DMODE=package-inspect-source-package
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|summary.module=OpenGLGraphicsResourcesShader|summary.target=opengl|reflection.schemaVersion=1|reflection.target=opengl|reflection.module=OpenGLGraphicsResourcesShader|reflection.entryPoints.0.stage=vertex|reflection.entryPoints.0.backendName=vertex_main|reflection.entryPoints.1.stage=fragment|reflection.entryPoints.1.backendName=fragment_main|reflection.resources.0.stage=vertex|reflection.resources.0.name=vertexParams|reflection.resources.0.kind=uniform|reflection.resources.0.set=0|reflection.resources.0.binding=0|reflection.resources.1.stage=fragment|reflection.resources.1.name=fragmentParams|reflection.resources.1.kind=uniform|reflection.resources.1.set=0|reflection.resources.1.binding=1|reflection.targetResourceBindings.0.stage=vertex|reflection.targetResourceBindings.0.entryPoint=vertex_main|reflection.targetResourceBindings.0.name=vertexParams|reflection.targetResourceBindings.0.kind=uniform|reflection.targetResourceBindings.0.sourceType=FrameParams|reflection.targetResourceBindings.0.addressSpace=uniform|reflection.targetResourceBindings.0.abi=programResourceBinding|reflection.targetResourceBindings.0.bindingClass=uniform-buffer|reflection.targetResourceBindings.0.set=0|reflection.targetResourceBindings.0.binding=0|reflection.targetResourceBindings.1.stage=fragment|reflection.targetResourceBindings.1.entryPoint=fragment_main|reflection.targetResourceBindings.1.name=fragmentParams|reflection.targetResourceBindings.1.kind=uniform|reflection.targetResourceBindings.1.sourceType=FrameParams|reflection.targetResourceBindings.1.addressSpace=uniform|reflection.targetResourceBindings.1.abi=programResourceBinding|reflection.targetResourceBindings.1.bindingClass=uniform-buffer|reflection.targetResourceBindings.1.set=0|reflection.targetResourceBindings.1.binding=1"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=reflection.entryPoints=2|reflection.resources=2|reflection.targetResourceBindings=2|reflection.vertexLayouts=1|reflection.workgroupSizes=0")
crossgl_add_python_expect_test(
  NAME cglc_package_inspect_directx_graphics_shadow_compare_reflection_contract
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-package-inspect-directx-graphics-shadow-compare-reflection.cglb
    -DMODE=package-inspect-source-package
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|summary.module=DirectXGraphicsShadowCompareShader|summary.target=directx|reflection.schemaVersion=1|reflection.target=directx|reflection.module=DirectXGraphicsShadowCompareShader|reflection.entryPoints.1.stage=fragment|reflection.entryPoints.1.backendName=fragment_main|reflection.resources.0.stage=fragment|reflection.resources.0.name=shadowMap|reflection.resources.0.kind=texture|reflection.resources.0.type=sampler2DShadow|reflection.resources.0.set=1|reflection.resources.0.binding=2|reflection.resources.1.stage=fragment|reflection.resources.1.name=shadowSampler|reflection.resources.1.kind=sampler|reflection.resources.1.type=comparison_sampler|reflection.resources.1.set=1|reflection.resources.1.binding=3|reflection.targetResourceBindings.0.stage=fragment|reflection.targetResourceBindings.0.entryPoint=fragment_main|reflection.targetResourceBindings.0.name=shadowMap|reflection.targetResourceBindings.0.kind=texture|reflection.targetResourceBindings.0.sourceType=sampler2DShadow|reflection.targetResourceBindings.0.hlslType=Texture2D<float>|reflection.targetResourceBindings.0.addressSpace=shader-resource|reflection.targetResourceBindings.0.abi=registerBinding|reflection.targetResourceBindings.0.bindingClass=srv|reflection.targetResourceBindings.0.descriptorType=SRV|reflection.targetResourceBindings.0.argumentIndex=2|reflection.targetResourceBindings.0.set=1|reflection.targetResourceBindings.0.binding=2|reflection.targetResourceBindings.1.stage=fragment|reflection.targetResourceBindings.1.entryPoint=fragment_main|reflection.targetResourceBindings.1.name=shadowSampler|reflection.targetResourceBindings.1.kind=sampler|reflection.targetResourceBindings.1.sourceType=comparison_sampler|reflection.targetResourceBindings.1.hlslType=SamplerComparisonState|reflection.targetResourceBindings.1.addressSpace=sampler|reflection.targetResourceBindings.1.abi=registerBinding|reflection.targetResourceBindings.1.bindingClass=sampler|reflection.targetResourceBindings.1.descriptorType=Sampler|reflection.targetResourceBindings.1.argumentIndex=3|reflection.targetResourceBindings.1.set=1|reflection.targetResourceBindings.1.binding=3|reflection.targetFeatures.11.name=texture-shadow-compare|reflection.targetFeatures.11.kind=operation"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=reflection.entryPoints=2|reflection.resources=2|reflection.targetResourceBindings=2|reflection.vertexLayouts=1|reflection.workgroupSizes=0")
crossgl_add_python_expect_test(
  NAME cglc_package_inspect_opengl_graphics_shadow_compare_reflection_contract
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_RESOURCES_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-package-inspect-opengl-graphics-shadow-compare-reflection.cglb
    -DMODE=package-inspect-source-package
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|summary.module=OpenGLGraphicsShadowCompareResourcesShader|summary.target=opengl|reflection.schemaVersion=1|reflection.target=opengl|reflection.module=OpenGLGraphicsShadowCompareResourcesShader|reflection.entryPoints.1.stage=fragment|reflection.entryPoints.1.backendName=fragment_main|reflection.resources.0.stage=fragment|reflection.resources.0.name=shadowMap|reflection.resources.0.kind=texture|reflection.resources.0.type=sampler2DShadow|reflection.resources.0.set=0|reflection.resources.0.binding=2|reflection.resources.1.stage=fragment|reflection.resources.1.name=shadowSampler|reflection.resources.1.kind=sampler|reflection.resources.1.type=comparison_sampler|reflection.resources.1.set=0|reflection.resources.1.binding=3|reflection.targetResourceBindings.0.stage=fragment|reflection.targetResourceBindings.0.entryPoint=fragment_main|reflection.targetResourceBindings.0.name=shadowMap|reflection.targetResourceBindings.0.kind=texture|reflection.targetResourceBindings.0.sourceType=sampler2DShadow|reflection.targetResourceBindings.0.addressSpace=texture|reflection.targetResourceBindings.0.abi=programResourceBinding|reflection.targetResourceBindings.0.bindingClass=texture|reflection.targetResourceBindings.0.argumentIndex=2|reflection.targetResourceBindings.0.set=0|reflection.targetResourceBindings.0.binding=2|reflection.targetResourceBindings.1.stage=fragment|reflection.targetResourceBindings.1.entryPoint=fragment_main|reflection.targetResourceBindings.1.name=shadowSampler|reflection.targetResourceBindings.1.kind=sampler|reflection.targetResourceBindings.1.sourceType=comparison_sampler|reflection.targetResourceBindings.1.addressSpace=sampler|reflection.targetResourceBindings.1.abi=programResourceBinding|reflection.targetResourceBindings.1.bindingClass=sampler|reflection.targetResourceBindings.1.argumentIndex=3|reflection.targetResourceBindings.1.set=0|reflection.targetResourceBindings.1.binding=3|reflection.targetFeatures.11.name=texture-shadow-compare|reflection.targetFeatures.11.kind=operation"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=reflection.entryPoints=2|reflection.resources=2|reflection.targetResourceBindings=2|reflection.vertexLayouts=1|reflection.workgroupSizes=0")
if(CROSSGL_HAS_METAL_NATIVE_TOOLS)
  crossgl_add_python_expect_test(
    NAME cglc_package_inspect_metal_graphics_varying_pack_reflection_contract
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_METAL_GRAPHICS_VARYING_PACK_SHADER}
      -DTARGET=metal
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-package-inspect-metal-graphics-varying-pack-reflection.cglb
      -DMODE=package-inspect-source-package
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|summary.module=MetalGraphicsVaryingPackShader|summary.target=metal|reflection.schemaVersion=1|reflection.target=metal|reflection.module=MetalGraphicsVaryingPackShader|reflection.entryPoints.0.stage=vertex|reflection.entryPoints.0.backendName=vertex_main|reflection.entryPoints.1.stage=fragment|reflection.entryPoints.1.backendName=fragment_main|reflection.vertexLayouts.0.entryPoint=vertex_main|reflection.vertexLayouts.0.attributes.0.name=position|reflection.vertexLayouts.0.attributes.0.type=vec3|reflection.vertexLayouts.0.attributes.0.location=0|reflection.vertexLayouts.0.attributes.1.name=normal|reflection.vertexLayouts.0.attributes.1.type=vec3|reflection.vertexLayouts.0.attributes.1.location=1|reflection.vertexLayouts.0.attributes.2.name=texCoord|reflection.vertexLayouts.0.attributes.2.type=vec2|reflection.vertexLayouts.0.attributes.2.location=2|reflection.vertexLayouts.0.attributes.3.name=weight|reflection.vertexLayouts.0.attributes.3.type=float|reflection.vertexLayouts.0.attributes.3.location=3|reflection.targetFeatures.5.name=vertex-shader|reflection.targetFeatures.5.kind=stage|reflection.targetFeatures.8.name=vector-arithmetic|reflection.targetFeatures.8.kind=operation|reflection.targetFeatures.9.name=fragment-shader|reflection.targetFeatures.9.kind=stage|reflection.targetFeatures.10.name=scalar-arithmetic|reflection.targetFeatures.10.kind=operation"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=reflection.entryPoints=2|reflection.resources=0|reflection.targetResourceBindings=0|reflection.vertexLayouts=1|reflection.vertexLayouts.0.attributes=4|reflection.workgroupSizes=0")
  crossgl_label_optional_native_test(
    cglc_package_inspect_metal_graphics_varying_pack_reflection_contract
    metal)
  crossgl_add_python_expect_test(
    NAME cglc_package_inspect_metal_graphics_shadow_compare_reflection_contract
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsShadowCompareShader.cgl
      -DTARGET=metal
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-package-inspect-metal-graphics-shadow-compare-reflection.cglb
      -DMODE=package-inspect-source-package
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|summary.module=MetalGraphicsShadowCompareShader|summary.target=metal|reflection.schemaVersion=1|reflection.target=metal|reflection.module=MetalGraphicsShadowCompareShader|reflection.entryPoints.1.stage=fragment|reflection.entryPoints.1.backendName=fragment_main|reflection.resources.0.stage=fragment|reflection.resources.0.name=shadowMap|reflection.resources.0.kind=texture|reflection.resources.0.type=sampler2DShadow|reflection.resources.0.set=0|reflection.resources.0.binding=2|reflection.resources.1.stage=fragment|reflection.resources.1.name=shadowCompareSampler|reflection.resources.1.kind=sampler|reflection.resources.1.type=comparison_sampler|reflection.resources.1.set=0|reflection.resources.1.binding=5|reflection.targetResourceBindings.0.stage=fragment|reflection.targetResourceBindings.0.entryPoint=fragment_main|reflection.targetResourceBindings.0.name=shadowMap|reflection.targetResourceBindings.0.kind=texture|reflection.targetResourceBindings.0.sourceType=sampler2DShadow|reflection.targetResourceBindings.0.metalType=depth2d<float>|reflection.targetResourceBindings.0.addressSpace=texture|reflection.targetResourceBindings.0.abi=kernelArgument|reflection.targetResourceBindings.0.bindingClass=texture|reflection.targetResourceBindings.0.argumentIndex=2|reflection.targetResourceBindings.0.set=0|reflection.targetResourceBindings.0.binding=2|reflection.targetResourceBindings.1.stage=fragment|reflection.targetResourceBindings.1.entryPoint=fragment_main|reflection.targetResourceBindings.1.name=shadowCompareSampler|reflection.targetResourceBindings.1.kind=sampler|reflection.targetResourceBindings.1.sourceType=comparison_sampler|reflection.targetResourceBindings.1.metalType=sampler|reflection.targetResourceBindings.1.addressSpace=sampler|reflection.targetResourceBindings.1.abi=kernelArgument|reflection.targetResourceBindings.1.bindingClass=sampler|reflection.targetResourceBindings.1.argumentIndex=5|reflection.targetResourceBindings.1.set=0|reflection.targetResourceBindings.1.binding=5|reflection.targetFeatures.12.name=texture-shadow-compare|reflection.targetFeatures.12.kind=operation"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=reflection.entryPoints=2|reflection.resources=2|reflection.targetResourceBindings=2|reflection.vertexLayouts=1|reflection.workgroupSizes=0")
  crossgl_label_optional_native_test(
    cglc_package_inspect_metal_graphics_shadow_compare_reflection_contract
    metal)
  crossgl_add_python_expect_test(
    NAME cglc_package_inspect_metal_graphics_shadow_compare_lod_reflection_contract
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/tests/metal/fixtures/MetalGraphicsShadowCompareLodShader.cgl
      -DTARGET=metal
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-package-inspect-metal-graphics-shadow-compare-lod-reflection.cglb
      -DMODE=package-inspect-source-package
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|summary.module=MetalGraphicsShadowCompareLodShader|summary.target=metal|reflection.schemaVersion=1|reflection.target=metal|reflection.module=MetalGraphicsShadowCompareLodShader|reflection.entryPoints.1.stage=fragment|reflection.entryPoints.1.backendName=fragment_main|reflection.resources.0.stage=fragment|reflection.resources.0.name=shadowMap|reflection.resources.0.kind=texture|reflection.resources.0.type=sampler2DShadow|reflection.resources.0.set=0|reflection.resources.0.binding=2|reflection.resources.1.stage=fragment|reflection.resources.1.name=shadowCompareSampler|reflection.resources.1.kind=sampler|reflection.resources.1.type=comparison_sampler|reflection.resources.1.set=0|reflection.resources.1.binding=5|reflection.targetResourceBindings.0.target=metal|reflection.targetResourceBindings.0.stage=fragment|reflection.targetResourceBindings.0.entryPoint=fragment_main|reflection.targetResourceBindings.0.name=shadowMap|reflection.targetResourceBindings.0.kind=texture|reflection.targetResourceBindings.0.sourceType=sampler2DShadow|reflection.targetResourceBindings.0.metalType=depth2d<float>|reflection.targetResourceBindings.0.addressSpace=texture|reflection.targetResourceBindings.0.abi=kernelArgument|reflection.targetResourceBindings.0.bindingClass=texture|reflection.targetResourceBindings.0.argumentIndex=2|reflection.targetResourceBindings.0.set=0|reflection.targetResourceBindings.0.binding=2|reflection.targetResourceBindings.1.target=metal|reflection.targetResourceBindings.1.stage=fragment|reflection.targetResourceBindings.1.entryPoint=fragment_main|reflection.targetResourceBindings.1.name=shadowCompareSampler|reflection.targetResourceBindings.1.kind=sampler|reflection.targetResourceBindings.1.sourceType=comparison_sampler|reflection.targetResourceBindings.1.metalType=sampler|reflection.targetResourceBindings.1.addressSpace=sampler|reflection.targetResourceBindings.1.abi=kernelArgument|reflection.targetResourceBindings.1.bindingClass=sampler|reflection.targetResourceBindings.1.argumentIndex=5|reflection.targetResourceBindings.1.set=0|reflection.targetResourceBindings.1.binding=5|reflection.targetFeatures.12.target=metal|reflection.targetFeatures.12.name=texture-shadow-compare|reflection.targetFeatures.12.kind=operation|reflection.targetFeatures.13.target=metal|reflection.targetFeatures.13.name=texture-shadow-compare-explicit-lod|reflection.targetFeatures.13.kind=operation"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=reflection.entryPoints=2|reflection.resources=2|reflection.targetResourceBindings=2|reflection.vertexLayouts=1|reflection.workgroupSizes=0")
  crossgl_label_optional_native_test(
    cglc_package_inspect_metal_graphics_shadow_compare_lod_reflection_contract
    metal)
endif()
if(CROSSGL_HAS_VULKAN_NATIVE_TOOLS)
  crossgl_add_python_expect_test(
    NAME cglc_package_inspect_vulkan_graphics_shadow_compare_reflection_contract
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_COMPARE_SHADER}
      -DTARGET=vulkan
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-package-inspect-vulkan-graphics-shadow-compare-reflection.cglb
      -DMODE=package-inspect-source-package
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|summary.module=VulkanGraphicsShadowCompareShader|summary.target=vulkan|reflection.schemaVersion=1|reflection.target=vulkan|reflection.module=VulkanGraphicsShadowCompareShader|reflection.entryPoints.1.stage=fragment|reflection.entryPoints.1.backendName=fragment_main|reflection.resources.0.stage=fragment|reflection.resources.0.name=shadowMap|reflection.resources.0.kind=texture|reflection.resources.0.type=sampler2DShadow|reflection.resources.0.set=0|reflection.resources.0.binding=2|reflection.resources.1.stage=fragment|reflection.resources.1.name=shadowSampler|reflection.resources.1.kind=sampler|reflection.resources.1.type=comparison_sampler|reflection.resources.1.set=0|reflection.resources.1.binding=3|reflection.targetResourceBindings.0.target=vulkan|reflection.targetResourceBindings.0.stage=fragment|reflection.targetResourceBindings.0.entryPoint=fragment_main|reflection.targetResourceBindings.0.name=shadowMap|reflection.targetResourceBindings.0.kind=texture|reflection.targetResourceBindings.0.sourceType=sampler2DShadow|reflection.targetResourceBindings.0.addressSpace=UniformConstant|reflection.targetResourceBindings.0.abi=descriptor|reflection.targetResourceBindings.0.bindingClass=sampledImage|reflection.targetResourceBindings.0.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|reflection.targetResourceBindings.0.storageClass=UniformConstant|reflection.targetResourceBindings.0.spirvType=OpTypeImage<depth_compare, 2D, sampled=1>|reflection.targetResourceBindings.0.set=0|reflection.targetResourceBindings.0.binding=2|reflection.targetResourceBindings.1.target=vulkan|reflection.targetResourceBindings.1.stage=fragment|reflection.targetResourceBindings.1.entryPoint=fragment_main|reflection.targetResourceBindings.1.name=shadowSampler|reflection.targetResourceBindings.1.kind=sampler|reflection.targetResourceBindings.1.sourceType=comparison_sampler|reflection.targetResourceBindings.1.addressSpace=UniformConstant|reflection.targetResourceBindings.1.abi=descriptor|reflection.targetResourceBindings.1.bindingClass=sampler|reflection.targetResourceBindings.1.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|reflection.targetResourceBindings.1.storageClass=UniformConstant|reflection.targetResourceBindings.1.spirvType=OpTypeSampler|reflection.targetResourceBindings.1.set=0|reflection.targetResourceBindings.1.binding=3|reflection.targetFeatures.12.target=vulkan|reflection.targetFeatures.12.name=texture-shadow-compare|reflection.targetFeatures.12.kind=operation"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=reflection.entryPoints=2|reflection.resources=2|reflection.targetResourceBindings=2|reflection.vertexLayouts=1|reflection.workgroupSizes=0")
  crossgl_label_optional_native_test(
    cglc_package_inspect_vulkan_graphics_shadow_compare_reflection_contract
    vulkan)
  crossgl_add_python_expect_test(
    NAME cglc_package_inspect_vulkan_graphics_shadow_compare_lod_reflection_contract
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_VULKAN_GRAPHICS_SHADOW_COMPARE_LOD_SHADER}
      -DTARGET=vulkan
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-package-inspect-vulkan-graphics-shadow-compare-lod-reflection.cglb
      -DMODE=package-inspect-source-package
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|summary.module=VulkanGraphicsShadowCompareLodShader|summary.target=vulkan|reflection.schemaVersion=1|reflection.target=vulkan|reflection.module=VulkanGraphicsShadowCompareLodShader|reflection.entryPoints.1.stage=fragment|reflection.entryPoints.1.backendName=fragment_main|reflection.resources.0.stage=fragment|reflection.resources.0.name=shadowMap|reflection.resources.0.kind=texture|reflection.resources.0.type=sampler2DShadow|reflection.resources.0.set=0|reflection.resources.0.binding=2|reflection.resources.1.stage=fragment|reflection.resources.1.name=shadowSampler|reflection.resources.1.kind=sampler|reflection.resources.1.type=comparison_sampler|reflection.resources.1.set=0|reflection.resources.1.binding=3|reflection.targetResourceBindings.0.target=vulkan|reflection.targetResourceBindings.0.stage=fragment|reflection.targetResourceBindings.0.entryPoint=fragment_main|reflection.targetResourceBindings.0.name=shadowMap|reflection.targetResourceBindings.0.kind=texture|reflection.targetResourceBindings.0.sourceType=sampler2DShadow|reflection.targetResourceBindings.0.addressSpace=UniformConstant|reflection.targetResourceBindings.0.abi=descriptor|reflection.targetResourceBindings.0.bindingClass=sampledImage|reflection.targetResourceBindings.0.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE|reflection.targetResourceBindings.0.storageClass=UniformConstant|reflection.targetResourceBindings.0.spirvType=OpTypeImage<depth_compare, 2D, sampled=1>|reflection.targetResourceBindings.0.set=0|reflection.targetResourceBindings.0.binding=2|reflection.targetResourceBindings.1.target=vulkan|reflection.targetResourceBindings.1.stage=fragment|reflection.targetResourceBindings.1.entryPoint=fragment_main|reflection.targetResourceBindings.1.name=shadowSampler|reflection.targetResourceBindings.1.kind=sampler|reflection.targetResourceBindings.1.sourceType=comparison_sampler|reflection.targetResourceBindings.1.addressSpace=UniformConstant|reflection.targetResourceBindings.1.abi=descriptor|reflection.targetResourceBindings.1.bindingClass=sampler|reflection.targetResourceBindings.1.descriptorType=VK_DESCRIPTOR_TYPE_SAMPLER|reflection.targetResourceBindings.1.storageClass=UniformConstant|reflection.targetResourceBindings.1.spirvType=OpTypeSampler|reflection.targetResourceBindings.1.set=0|reflection.targetResourceBindings.1.binding=3|reflection.targetFeatures.12.target=vulkan|reflection.targetFeatures.12.name=texture-shadow-compare|reflection.targetFeatures.12.kind=operation|reflection.targetFeatures.13.target=vulkan|reflection.targetFeatures.13.name=texture-shadow-compare-explicit-lod|reflection.targetFeatures.13.kind=operation"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=reflection.entryPoints=2|reflection.resources=2|reflection.targetResourceBindings=2|reflection.vertexLayouts=1|reflection.workgroupSizes=0")
  crossgl_label_optional_native_test(
    cglc_package_inspect_vulkan_graphics_shadow_compare_lod_reflection_contract
    vulkan)
endif()
crossgl_add_python_expect_test(
  NAME cglc_package_inspect_directx_graphics_shadow_compare_lod_reflection_contract
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_SHADOW_COMPARE_LOD_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-package-inspect-directx-graphics-shadow-compare-lod-reflection.cglb
    -DMODE=package-inspect-source-package
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|summary.module=DirectXGraphicsShadowCompareLodShader|summary.target=directx|reflection.schemaVersion=1|reflection.target=directx|reflection.module=DirectXGraphicsShadowCompareLodShader|reflection.entryPoints.1.stage=fragment|reflection.entryPoints.1.backendName=fragment_main|reflection.resources.0.stage=fragment|reflection.resources.0.name=shadowMap|reflection.resources.0.kind=texture|reflection.resources.0.type=sampler2DShadow|reflection.resources.0.set=1|reflection.resources.0.binding=2|reflection.resources.1.stage=fragment|reflection.resources.1.name=shadowSampler|reflection.resources.1.kind=sampler|reflection.resources.1.type=comparison_sampler|reflection.resources.1.set=1|reflection.resources.1.binding=3|reflection.targetResourceBindings.0.target=directx|reflection.targetResourceBindings.0.stage=fragment|reflection.targetResourceBindings.0.entryPoint=fragment_main|reflection.targetResourceBindings.0.name=shadowMap|reflection.targetResourceBindings.0.kind=texture|reflection.targetResourceBindings.0.sourceType=sampler2DShadow|reflection.targetResourceBindings.0.hlslType=Texture2D<float>|reflection.targetResourceBindings.0.addressSpace=shader-resource|reflection.targetResourceBindings.0.abi=registerBinding|reflection.targetResourceBindings.0.bindingClass=srv|reflection.targetResourceBindings.0.descriptorType=SRV|reflection.targetResourceBindings.0.argumentIndex=2|reflection.targetResourceBindings.0.set=1|reflection.targetResourceBindings.0.binding=2|reflection.targetResourceBindings.1.target=directx|reflection.targetResourceBindings.1.stage=fragment|reflection.targetResourceBindings.1.entryPoint=fragment_main|reflection.targetResourceBindings.1.name=shadowSampler|reflection.targetResourceBindings.1.kind=sampler|reflection.targetResourceBindings.1.sourceType=comparison_sampler|reflection.targetResourceBindings.1.hlslType=SamplerComparisonState|reflection.targetResourceBindings.1.addressSpace=sampler|reflection.targetResourceBindings.1.abi=registerBinding|reflection.targetResourceBindings.1.bindingClass=sampler|reflection.targetResourceBindings.1.descriptorType=Sampler|reflection.targetResourceBindings.1.argumentIndex=3|reflection.targetResourceBindings.1.set=1|reflection.targetResourceBindings.1.binding=3|reflection.targetFeatures.11.target=directx|reflection.targetFeatures.11.name=texture-shadow-compare|reflection.targetFeatures.11.kind=operation|reflection.targetFeatures.12.target=directx|reflection.targetFeatures.12.name=texture-shadow-compare-explicit-lod|reflection.targetFeatures.12.kind=operation"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=reflection.entryPoints=2|reflection.resources=2|reflection.targetResourceBindings=2|reflection.vertexLayouts=1|reflection.workgroupSizes=0")
crossgl_add_python_expect_test(
  NAME cglc_package_inspect_opengl_graphics_shadow_compare_lod_reflection_contract
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_SHADOW_COMPARE_LOD_RESOURCES_SHADER}
    -DTARGET=opengl
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-package-inspect-opengl-graphics-shadow-compare-lod-reflection.cglb
    -DMODE=package-inspect-source-package
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|summary.module=OpenGLGraphicsShadowCompareLodResourcesShader|summary.target=opengl|reflection.schemaVersion=1|reflection.target=opengl|reflection.module=OpenGLGraphicsShadowCompareLodResourcesShader|reflection.entryPoints.1.stage=fragment|reflection.entryPoints.1.backendName=fragment_main|reflection.resources.0.stage=fragment|reflection.resources.0.name=shadowMap|reflection.resources.0.kind=texture|reflection.resources.0.type=sampler2DShadow|reflection.resources.0.set=0|reflection.resources.0.binding=2|reflection.resources.1.stage=fragment|reflection.resources.1.name=shadowSampler|reflection.resources.1.kind=sampler|reflection.resources.1.type=comparison_sampler|reflection.resources.1.set=0|reflection.resources.1.binding=3|reflection.targetResourceBindings.0.target=opengl|reflection.targetResourceBindings.0.stage=fragment|reflection.targetResourceBindings.0.entryPoint=fragment_main|reflection.targetResourceBindings.0.name=shadowMap|reflection.targetResourceBindings.0.kind=texture|reflection.targetResourceBindings.0.sourceType=sampler2DShadow|reflection.targetResourceBindings.0.addressSpace=texture|reflection.targetResourceBindings.0.abi=programResourceBinding|reflection.targetResourceBindings.0.bindingClass=texture|reflection.targetResourceBindings.0.argumentIndex=2|reflection.targetResourceBindings.0.set=0|reflection.targetResourceBindings.0.binding=2|reflection.targetResourceBindings.1.target=opengl|reflection.targetResourceBindings.1.stage=fragment|reflection.targetResourceBindings.1.entryPoint=fragment_main|reflection.targetResourceBindings.1.name=shadowSampler|reflection.targetResourceBindings.1.kind=sampler|reflection.targetResourceBindings.1.sourceType=comparison_sampler|reflection.targetResourceBindings.1.addressSpace=sampler|reflection.targetResourceBindings.1.abi=programResourceBinding|reflection.targetResourceBindings.1.bindingClass=sampler|reflection.targetResourceBindings.1.argumentIndex=3|reflection.targetResourceBindings.1.set=0|reflection.targetResourceBindings.1.binding=3|reflection.targetFeatures.11.target=opengl|reflection.targetFeatures.11.name=texture-shadow-compare|reflection.targetFeatures.11.kind=operation|reflection.targetFeatures.12.target=opengl|reflection.targetFeatures.12.name=texture-shadow-compare-explicit-lod|reflection.targetFeatures.12.kind=operation"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=reflection.entryPoints=2|reflection.resources=2|reflection.targetResourceBindings=2|reflection.vertexLayouts=1|reflection.workgroupSizes=0")
add_test(NAME cglc_targets COMMAND cglc targets)
add_test(NAME cglc_check_simple
  COMMAND cglc check ${CROSSGL_SIMPLE_SHADER})
add_test(NAME cglc_check_json_simple
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DMODE=check-json
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=schemaVersion=1"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
crossgl_add_python_expect_test(
  NAME cglc_diagnostics_json_schema_empty
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DMODE=check-json
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/diagnostics-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=schemaVersion=1"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=0")
add_test(NAME cglc_diagnostics_json_check_warning_emission
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_CHECK_WARNING_MANUAL_KERNEL_NON_NORMALIZED_SHADER}
    -DMODE=check-json
    -DEXPECTED_DIAGNOSTIC=sema.texture-compare-kernel-weight-not-normalized
    "-DEXPECTED_DIAGNOSTICS_JSON_PATHS=diagnostics.0.location.offset|diagnostics.0.location.endOffset"
    "-DEXPECTED_DIAGNOSTICS_JSON_FIELDS=schemaVersion=1"
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=severity=warning|location.file=tests/check-failures/WarnTextureCompareLodManualKernelListNonNormalizedWeightShader.cgl|location.line=7|location.column=11|location.length=29|location.endLine=7|location.endColumn=40"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=literal weights sum to 0.8|message=preserves exact user weights"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
