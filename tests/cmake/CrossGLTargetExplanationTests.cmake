if(APPLE)
  set(CROSSGL_GRAPHICS_DEFAULT_TARGET metal)
  set(CROSSGL_GRAPHICS_AUTO_SELECTED_TARGET metal)
  set(CROSSGL_GRAPHICS_AUTO_SELECTION_REASON auto-host-default)
  set(CROSSGL_GRAPHICS_AUTO_FALLBACK_NATIVE_TARGET vulkan)
  set(CROSSGL_NATIVE_UNSUPPORTED_DEFAULT_TARGET metal)
  set(CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET metal)
  set(CROSSGL_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET metal)
  set(CROSSGL_NATIVE_UNSUPPORTED_SOURCE_FALLBACK_SELECTION_REASON
      auto-recommended-target)
elseif(WIN32)
  set(CROSSGL_GRAPHICS_DEFAULT_TARGET directx)
  set(CROSSGL_GRAPHICS_AUTO_SELECTED_TARGET metal)
  set(CROSSGL_GRAPHICS_AUTO_SELECTION_REASON auto-recommended-target)
  set(CROSSGL_GRAPHICS_AUTO_FALLBACK_NATIVE_TARGET vulkan)
  set(CROSSGL_NATIVE_UNSUPPORTED_DEFAULT_TARGET directx)
  set(CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET metal)
  set(CROSSGL_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET metal)
  set(CROSSGL_NATIVE_UNSUPPORTED_SOURCE_FALLBACK_SELECTION_REASON
      auto-host-default)
else()
  set(CROSSGL_GRAPHICS_DEFAULT_TARGET vulkan)
  set(CROSSGL_GRAPHICS_AUTO_SELECTED_TARGET vulkan)
  set(CROSSGL_GRAPHICS_AUTO_SELECTION_REASON auto-host-default)
  set(CROSSGL_GRAPHICS_AUTO_FALLBACK_NATIVE_TARGET metal)
  set(CROSSGL_NATIVE_UNSUPPORTED_DEFAULT_TARGET vulkan)
  set(CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET vulkan)
  set(CROSSGL_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET vulkan)
  set(CROSSGL_NATIVE_UNSUPPORTED_SOURCE_FALLBACK_SELECTION_REASON
      auto-recommended-target)
endif()

set(CROSSGL_TARGET_RAW_HIR_BACKEND_INPUT_SHADER
    ${CMAKE_CURRENT_BINARY_DIR}/target-raw-hir-backend-input.cgl)
file(WRITE ${CROSSGL_TARGET_RAW_HIR_BACKEND_INPUT_SHADER} [=[
shader TargetRawHIRBackendInputShader {
  compute precompute_environment {
    layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;

    vec3 getSamplingVector(vec2 uv, int face) {
      vec3 result;
      for (int rawIndex = 0; rawIndex++; rawIndex++) {
        result = vec3(1.0, -uv.y, -uv.x);
      }
      return normalize(result);
    }

    void main() {
      vec3 direction = getSamplingVector(vec2(0.0, 0.0), 0);
      return;
    }
  }
}
]=])

set(CROSSGL_EXPECT_EXPLAIN_TARGETS_RAW_HIR_FAILURE
    ${CMAKE_CURRENT_BINARY_DIR}/ExpectExplainTargetsRawHIRFailure.cmake)
file(WRITE ${CROSSGL_EXPECT_EXPLAIN_TARGETS_RAW_HIR_FAILURE} [=[
if(NOT DEFINED CGLC)
  message(FATAL_ERROR "CGLC is required")
endif()
if(NOT DEFINED INPUT)
  message(FATAL_ERROR "INPUT is required")
endif()

execute_process(
  COMMAND "${CGLC}" explain-targets "${INPUT}"
  RESULT_VARIABLE result
  OUTPUT_VARIABLE stdout
  ERROR_VARIABLE stderr)
if(result EQUAL 0)
  message(FATAL_ERROR "expected explain-targets to reject raw HIR, got: ${stdout}")
endif()
string(FIND "${stderr}" "opt.hir-raw-statement-backend-input" diagnostic_position)
if(diagnostic_position EQUAL -1)
  message(FATAL_ERROR "expected opt.hir-raw-statement-backend-input diagnostic, got: ${stderr}")
endif()
]=])

add_test(NAME cglc_explain_targets_raw_hir_backend_input_rejected
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_TARGET_RAW_HIR_BACKEND_INPUT_SHADER}
    -P ${CROSSGL_EXPECT_EXPLAIN_TARGETS_RAW_HIR_FAILURE})

foreach(CROSSGL_TARGET_RAW_HIR_BACKEND_INPUT_TARGET
        metal vulkan directx opengl)
  add_test(
    NAME cglc_raw_hir_backend_input_${CROSSGL_TARGET_RAW_HIR_BACKEND_INPUT_TARGET}_no_package_planned_failure
    COMMAND ${CMAKE_COMMAND}
      -DCGLC=$<TARGET_FILE:cglc>
      -DINPUT=${CROSSGL_TARGET_RAW_HIR_BACKEND_INPUT_SHADER}
      -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-raw-hir-backend-input-${CROSSGL_TARGET_RAW_HIR_BACKEND_INPUT_TARGET}.cglb
      -DTARGET=${CROSSGL_TARGET_RAW_HIR_BACKEND_INPUT_TARGET}
      -DEXPECT_NO_OUTPUT_PACKAGE=ON
      -DMODE=planned-build-failure
      -DEXPECTED_DIAGNOSTIC=opt.hir-raw-statement-backend-input
      "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
      "-DEXPECTED_DIAGNOSTIC_FIELDS=code=opt.hir-raw-statement-backend-input|severity=error"
      "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=raw statement|message=backend/package input"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
endforeach()

add_test(NAME cglc_explain_targets_graphics_package_decisions
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=SimpleShader|defaultTarget=${CROSSGL_GRAPHICS_DEFAULT_TARGET}|buildableTargetCount=4|recommendedTarget=${CROSSGL_GRAPHICS_AUTO_SELECTED_TARGET}|recommendedPackageMode=native"
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.sourcePackageSupported=false|metal.packageBuildSupported=true|metal.supportStatus=native|metal.legalizationState=legalized|metal.packageMode=native|metal.packageDecisionProvenance=native-package-available|metal.packageDecisionReason=native-package-available|metal.packageRankScore=0|metal.missingCapabilityCount=0|metal.requiredToolCount=2|metal.missingToolCount=0|metal.optionalNativeToolMissing=false|metal.optionalNativeToolStatus=not-required|vulkan.nativeImplemented=true|vulkan.sourcePackageSupported=false|vulkan.packageBuildSupported=true|vulkan.supportStatus=native|vulkan.legalizationState=legalized|vulkan.packageMode=native|vulkan.packageDecisionProvenance=native-package-available|vulkan.packageDecisionReason=native-package-available|vulkan.packageRankScore=0|vulkan.missingCapabilityCount=0|vulkan.requiredToolCount=2|vulkan.missingToolCount=0|vulkan.optionalNativeToolMissing=false|vulkan.optionalNativeToolStatus=not-required|directx.nativeImplemented=true|directx.sourcePackageSupported=true|directx.packageBuildSupported=true|directx.supportStatus=source-package|directx.legalizationState=legalized|directx.packageMode=source-package|directx.packageDecisionProvenance=source-package-only|directx.packageDecisionReason=source-package-available|directx.packageRankScore=1|directx.missingCapabilityCount=3|directx.requiredToolCount=2|directx.missingToolCount=2|directx.optionalNativeToolMissing=true|directx.optionalNativeToolStatus=missing|opengl.nativeImplemented=false|opengl.sourcePackageSupported=true|opengl.packageBuildSupported=true|opengl.supportStatus=source-package|opengl.legalizationState=legalized|opengl.packageMode=source-package|opengl.packageDecisionProvenance=source-package-only|opengl.packageDecisionReason=source-package-available|opengl.packageRankScore=1|opengl.missingCapabilityCount=3|opengl.requiredToolCount=2|opengl.missingToolCount=2|opengl.optionalNativeToolMissing=true|opengl.optionalNativeToolStatus=missing"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.stage.vertex-shader|metal.requiredCapabilities=metal.stage.fragment-shader|metal.requiredToolIds=metal.toolchain.xcrun-metal|metal.toolRequirementEvidenceIds=target-legalization.v1.metal.tool-requirements.present|vulkan.requiredCapabilities=vulkan.stage.vertex-shader|vulkan.requiredCapabilities=vulkan.stage.fragment-shader|vulkan.requiredToolIds=vulkan.validation.spirv-val|directx.requiredCapabilities=directx.stage.vertex-shader|directx.requiredCapabilities=directx.stage.fragment-shader|directx.missingCapabilities=directx.backend.native-dxil-package|directx.legalizationCoreEvidenceIds=target-legalization.v1.directx.package-mode.source-package|directx.requiredToolIds=directx.toolchain.dxc|directx.missingToolIds=directx.validation.dxil-validator|directx.toolRequirementEvidenceIds=target-legalization.v1.directx.tool-requirement.missing.validation.dxil-validator|opengl.requiredCapabilities=opengl.stage.vertex-shader|opengl.requiredCapabilities=opengl.stage.fragment-shader|opengl.missingCapabilities=opengl.backend.native-glsl-package|opengl.requiredToolIds=opengl.toolchain.opengl-driver|opengl.missingToolIds=opengl.validation.glsl-program-validation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

crossgl_add_python_expect_test(
  NAME cglc_explain_targets_graphics_schema_recommended_target
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DMODE=explain-targets
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/target-explanation-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=SimpleShader|defaultTarget=${CROSSGL_GRAPHICS_DEFAULT_TARGET}|buildableTargetCount=4|recommendedTarget=${CROSSGL_GRAPHICS_AUTO_SELECTED_TARGET}|recommendedPackageMode=native"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=targets=4"
    "-DEXPECTED_TARGET_FIELDS=metal.supportStatus=native|metal.legalizationState=legalized|metal.packageDecisionProvenance=native-package-available|metal.requiredCapabilityCount=9|metal.missingCapabilityCount=0|metal.requiredToolCount=2|metal.missingToolCount=0|metal.optionalNativeToolStatus=not-required|vulkan.supportStatus=native|vulkan.legalizationState=legalized|vulkan.packageDecisionProvenance=native-package-available|vulkan.requiredCapabilityCount=9|vulkan.missingCapabilityCount=0|vulkan.requiredToolCount=2|vulkan.missingToolCount=0|vulkan.optionalNativeToolStatus=not-required|directx.supportStatus=source-package|directx.legalizationState=legalized|directx.packageDecisionProvenance=source-package-only|directx.requiredCapabilityCount=8|directx.missingCapabilityCount=3|directx.requiredToolCount=2|directx.missingToolCount=2|directx.optionalNativeToolStatus=missing|opengl.supportStatus=source-package|opengl.legalizationState=legalized|opengl.packageDecisionProvenance=source-package-only|opengl.requiredCapabilityCount=8|opengl.missingCapabilityCount=3|opengl.requiredToolCount=2|opengl.missingToolCount=2|opengl.optionalNativeToolStatus=missing")

add_test(NAME cglc_target_decision_graphics_auto_recommends_native_default
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DTARGET=auto
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|targetDecision.requestedTarget=auto|targetDecision.selectedTarget=${CROSSGL_GRAPHICS_AUTO_SELECTED_TARGET}|targetDecision.selectionReason=${CROSSGL_GRAPHICS_AUTO_SELECTION_REASON}|targetDecision.selectedTargetNativeImplemented=true|targetDecision.selectedTargetSourcePackageSupported=false|targetDecision.selectedTargetPackageBuildSupported=true|targetDecision.selectedTargetPackageMode=native|targetDecision.selectedTargetMissingCapabilityCount=0|targetDecision.selectedTargetDiagnosticCount=0|targetDecision.fallbackTargetRecordCount=3"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=targetDecision.diagnostics=0|targetDecision.nonViableTargets=0"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.viableTargets=metal|targetDecision.viableTargets=vulkan|targetDecision.viableTargets=directx|targetDecision.viableTargets=opengl|targetDecision.fallbackTargets=${CROSSGL_GRAPHICS_AUTO_FALLBACK_NATIVE_TARGET}"
    -DTARGET_EXPLANATION_ROOT=targetDecision
    -DTARGET_RECORD_ARRAY_FIELD=fallbackTargetRecords
    "-DEXPECTED_TARGET_FIELDS=${CROSSGL_GRAPHICS_AUTO_FALLBACK_NATIVE_TARGET}.packageMode=native|${CROSSGL_GRAPHICS_AUTO_FALLBACK_NATIVE_TARGET}.packageBuildSupported=true|${CROSSGL_GRAPHICS_AUTO_FALLBACK_NATIVE_TARGET}.missingCapabilityCount=0|directx.packageMode=source-package|directx.packageBuildSupported=true|directx.missingCapabilityCount=3|opengl.packageMode=source-package|opengl.packageBuildSupported=true|opengl.missingCapabilityCount=3"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.missingCapabilities=directx.backend.native-dxil-package|opengl.missingCapabilities=opengl.backend.native-glsl-package"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

crossgl_add_python_expect_test(
  NAME cglc_target_decision_graphics_auto_target_capabilities_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DTARGET=auto
    -DSTAGE=debug
    -DMODE=dump-stage
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/debug-metadata-v11.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|targetCapabilities.defaultTarget=${CROSSGL_GRAPHICS_DEFAULT_TARGET}|targetDecision.requestedTarget=auto|targetDecision.selectedTarget=${CROSSGL_GRAPHICS_AUTO_SELECTED_TARGET}|targetDecision.selectionReason=${CROSSGL_GRAPHICS_AUTO_SELECTION_REASON}|targetDecision.selectedTargetMissingCapabilityCount=0|targetDecision.selectedTargetDiagnosticCount=0"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=targetCapabilities.summaries=4|targetDecision.selectedTargetMissingCapabilityGroups=0|targetDecision.diagnostics=0"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.selectedTargetLegalizationCoreEvidenceIds=target-legalization.v1.${CROSSGL_GRAPHICS_AUTO_SELECTED_TARGET}.decision"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_FIELDS=metal.requiredCapabilityGroups.4.kind=stage|metal.requiredCapabilityGroups.4.count=2|vulkan.requiredCapabilityGroups.5.kind=stage|vulkan.requiredCapabilityGroups.5.count=2|directx.requiredCapabilityGroups.0.kind=backend|directx.requiredCapabilityGroups.0.count=2|directx.missingCapabilityGroups.0.kind=backend|directx.missingCapabilityGroups.0.count=1|opengl.requiredCapabilityGroups.0.kind=backend|opengl.requiredCapabilityGroups.0.count=2|opengl.missingCapabilityGroups.0.kind=backend|opengl.missingCapabilityGroups.0.count=1"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilityGroups.4.capabilities=metal.stage.vertex-shader|metal.requiredCapabilityGroups.4.capabilities=metal.stage.fragment-shader|metal.legalizationCoreEvidenceIds=target-legalization.v1.metal.decision|vulkan.requiredCapabilityGroups.5.capabilities=vulkan.stage.vertex-shader|vulkan.requiredCapabilityGroups.5.capabilities=vulkan.stage.fragment-shader|vulkan.legalizationCoreEvidenceIds=target-legalization.v1.vulkan.decision|directx.missingCapabilityGroups.0.capabilities=directx.backend.native-dxil-package|directx.legalizationCoreEvidenceIds=target-legalization.v1.directx.package-mode.source-package|opengl.missingCapabilityGroups.0.capabilities=opengl.backend.native-glsl-package|opengl.legalizationCoreEvidenceIds=target-legalization.v1.opengl.package-mode.source-package")

add_test(NAME cglc_target_decision_graphics_source_package_targets
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_SIMPLE_SHADER}
    -DTARGET=opengl
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|targetDecision.requestedTarget=opengl|targetDecision.selectedTarget=opengl|targetDecision.selectionReason=explicit-target|targetDecision.selectedTargetNativeImplemented=false|targetDecision.selectedTargetSourcePackageSupported=true|targetDecision.selectedTargetPackageBuildSupported=true|targetDecision.selectedTargetPackageMode=source-package|targetDecision.selectedTargetMissingCapabilityCount=3|targetDecision.selectedTargetDiagnosticCount=0|targetDecision.fallbackTargetRecordCount=3"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=targetDecision.diagnostics=0|targetDecision.nonViableTargets=0"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.viableTargets=metal|targetDecision.viableTargets=vulkan|targetDecision.viableTargets=directx|targetDecision.viableTargets=opengl|targetDecision.selectedTargetMissingCapabilities=opengl.backend.native-glsl-package|targetDecision.selectedTargetMissingCapabilities=opengl.toolchain.opengl-driver|targetDecision.selectedTargetMissingCapabilities=opengl.validation.glsl-program-validation"
    -DTARGET_EXPLANATION_ROOT=targetDecision
    -DTARGET_RECORD_ARRAY_FIELD=fallbackTargetRecords
    "-DEXPECTED_TARGET_FIELDS=metal.packageMode=native|metal.packageBuildSupported=true|vulkan.packageMode=native|vulkan.packageBuildSupported=true|directx.packageMode=source-package|directx.packageBuildSupported=true|directx.missingCapabilityCount=3"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.missingCapabilities=directx.backend.native-dxil-package|directx.legalizationCoreEvidenceIds=target-legalization.v1.directx.package-mode.source-package"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

crossgl_add_python_expect_test(
  NAME cglc_target_decision_selected_target_diagnostic_groups_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_RUNTIME_TEXTURE_RESOURCE_ARRAY_CONFLICT_SHADER}
    -DTARGET=directx
    -DSTAGE=debug
    -DMODE=dump-stage
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/debug-metadata-v11.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|targetDecision.requestedTarget=directx|targetDecision.selectedTarget=directx|targetDecision.selectedTargetPackageMode=unsupported|targetDecision.selectedTargetMissingCapabilityCount=4|targetDecision.selectedTargetDiagnosticCount=1|targetDecision.selectedTargetMissingCapabilityGroups.0.kind=backend|targetDecision.selectedTargetMissingCapabilityGroups.0.count=1|targetDecision.selectedTargetMissingCapabilityGroups.1.kind=toolchain|targetDecision.selectedTargetMissingCapabilityGroups.1.count=1|targetDecision.selectedTargetMissingCapabilityGroups.2.kind=validation|targetDecision.selectedTargetMissingCapabilityGroups.2.count=1|targetDecision.selectedTargetMissingCapabilityGroups.3.kind=diagnostic|targetDecision.selectedTargetMissingCapabilityGroups.3.count=1|targetDecision.diagnostics.0.code=directx.unsupported-runtime-resource-array|targetDecision.diagnostics.0.severity=error|targetDecision.diagnostics.0.capabilityGroups.0.kind=backend|targetDecision.diagnostics.0.capabilityGroups.0.count=1|targetDecision.diagnostics.0.capabilityGroups.1.kind=toolchain|targetDecision.diagnostics.0.capabilityGroups.1.count=1|targetDecision.diagnostics.0.capabilityGroups.2.kind=validation|targetDecision.diagnostics.0.capabilityGroups.2.count=1|targetDecision.diagnostics.0.capabilityGroups.3.kind=diagnostic|targetDecision.diagnostics.0.capabilityGroups.3.count=1"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.selectedTargetMissingCapabilityGroups.0.capabilities=directx.backend.native-dxil-package|targetDecision.selectedTargetMissingCapabilityGroups.1.capabilities=directx.toolchain.dxc|targetDecision.selectedTargetMissingCapabilityGroups.2.capabilities=directx.validation.dxil-validator|targetDecision.selectedTargetMissingCapabilityGroups.3.capabilities=directx.diagnostic.directx.unsupported-runtime-resource-array|targetDecision.selectedTargetLegalizationCoreEvidenceIds=target-legalization.v1.directx.package-mode.unsupported|targetDecision.diagnostics.0.capabilityGroups.0.capabilities=directx.backend.native-dxil-package|targetDecision.diagnostics.0.capabilityGroups.1.capabilities=directx.toolchain.dxc|targetDecision.diagnostics.0.capabilityGroups.2.capabilities=directx.validation.dxil-validator|targetDecision.diagnostics.0.capabilityGroups.3.capabilities=directx.diagnostic.directx.unsupported-runtime-resource-array|targetDecision.diagnostics.0.legalizationCoreEvidenceIds=target-legalization.v1.directx.package-mode.unsupported"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_FIELDS=directx.packageBuildSupported=false|directx.packageMode=unsupported|directx.missingCapabilityGroups.0.kind=backend|directx.missingCapabilityGroups.1.kind=toolchain|directx.missingCapabilityGroups.2.kind=validation|directx.missingCapabilityGroups.3.kind=diagnostic"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=directx.missingCapabilityGroups.0.capabilities=directx.backend.native-dxil-package|directx.missingCapabilityGroups.1.capabilities=directx.toolchain.dxc|directx.missingCapabilityGroups.2.capabilities=directx.validation.dxil-validator|directx.missingCapabilityGroups.3.capabilities=directx.diagnostic.directx.unsupported-runtime-resource-array")

add_test(NAME cglc_explain_targets_native_runtime_storage_buffer_array_source_fallback
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_BUFFER_ARRAY_UNSUPPORTED_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=MetalStorageBufferArrayUnsupportedShader|defaultTarget=${CROSSGL_NATIVE_UNSUPPORTED_DEFAULT_TARGET}|buildableTargetCount=2|recommendedTarget=directx|recommendedPackageMode=source-package"
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.sourcePackageSupported=false|metal.packageBuildSupported=false|metal.packageMode=unsupported|metal.packageDecisionReason=unsupported|metal.packageRankScore=2|metal.missingCapabilityCount=2|vulkan.nativeImplemented=true|vulkan.sourcePackageSupported=false|vulkan.packageBuildSupported=false|vulkan.packageMode=unsupported|vulkan.packageDecisionReason=unsupported|vulkan.packageRankScore=2|vulkan.missingCapabilityCount=2|directx.nativeImplemented=true|directx.sourcePackageSupported=true|directx.packageBuildSupported=true|directx.packageMode=source-package|directx.packageDecisionReason=source-package-available|directx.packageRankScore=1|opengl.nativeImplemented=false|opengl.sourcePackageSupported=true|opengl.packageBuildSupported=true|opengl.packageMode=source-package|opengl.packageDecisionReason=source-package-available|opengl.packageRankScore=1|opengl.missingCapabilityCount=3"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.missingCapabilities=metal.backend.native-metal-package|metal.missingCapabilities=metal.diagnostic.metal.unsupported-storage-buffer-array|vulkan.missingCapabilities=vulkan.backend.vulkan-prototype-package|vulkan.missingCapabilities=vulkan.diagnostic.vulkan.prototype-unsupported-runtime-resource-array|directx.missingCapabilities=directx.backend.native-dxil-package|opengl.missingCapabilities=opengl.backend.native-glsl-package|opengl.missingCapabilities=opengl.toolchain.opengl-driver|opengl.missingCapabilities=opengl.validation.glsl-program-validation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_explain_targets_metal_storage_buffer_array_unsupported_legalization
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_BUFFER_ARRAY_UNSUPPORTED_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=MetalStorageBufferArrayUnsupportedShader|buildableTargetCount=2|recommendedTarget=directx|recommendedPackageMode=source-package"
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.sourcePackageSupported=false|metal.packageBuildSupported=false|metal.packageMode=unsupported|metal.packageDecisionReason=unsupported|metal.packageRankScore=2|metal.requiredCapabilityCount=12|metal.missingCapabilityCount=2"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.backend.native-metal-package|metal.requiredCapabilities=metal.resource.storage-buffer|metal.requiredCapabilities=metal.resource.descriptor-array|metal.missingCapabilities=metal.backend.native-metal-package|metal.missingCapabilities=metal.diagnostic.metal.unsupported-storage-buffer-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_build_metal_storage_buffer_array_no_package_unsupported_failure
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_BUFFER_ARRAY_UNSUPPORTED_SHADER}
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-metal-storage-buffer-array-unsupported-legalization.cglb
    -DTARGET=metal
    -DEXPECT_NO_OUTPUT_PACKAGE=ON
    -DMODE=planned-build-failure
    -DEXPECTED_DIAGNOSTIC=target.unsupported
    "-DEXPECTED_DIAGNOSTICS_JSON_ARRAY_LENGTHS=diagnostics=1"
    "-DEXPECTED_DIAGNOSTIC_FIELDS=target=metal"
    "-DEXPECTED_DIAGNOSTIC_ARRAY_CONTAINS=missingCapabilities=metal.backend.native-metal-package|missingCapabilities=metal.diagnostic.metal.unsupported-storage-buffer-array"
    "-DEXPECTED_DIAGNOSTIC_FIELD_CONTAINS=message=target 'metal' cannot build a package for this module|message=metal.diagnostic.metal.unsupported-storage-buffer-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_target_decision_auto_skips_unsupported_native_storage_buffer_array
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_BUFFER_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=auto
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|targetDecision.requestedTarget=auto|targetDecision.selectedTarget=directx|targetDecision.selectionReason=${CROSSGL_NATIVE_UNSUPPORTED_SOURCE_FALLBACK_SELECTION_REASON}|targetDecision.selectedTargetNativeImplemented=true|targetDecision.selectedTargetSourcePackageSupported=true|targetDecision.selectedTargetPackageBuildSupported=true|targetDecision.selectedTargetPackageMode=source-package|targetDecision.selectedTargetDiagnosticCount=0|targetDecision.fallbackTargetRecordCount=1"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=targetDecision.diagnostics=0|targetDecision.fallbackTargets=1|targetDecision.viableTargets=2"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.viableTargets=directx|targetDecision.viableTargets=opengl|targetDecision.fallbackTargets=opengl|targetDecision.nonViableTargets=metal|targetDecision.nonViableTargets=vulkan|targetDecision.selectedTargetMissingCapabilities=directx.backend.native-dxil-package"
    -DTARGET_EXPLANATION_ROOT=targetCapabilities
    -DTARGET_RECORD_ARRAY_FIELD=summaries
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.packageBuildSupported=false|metal.packageMode=unsupported|vulkan.nativeImplemented=true|vulkan.packageBuildSupported=false|vulkan.packageMode=unsupported|directx.packageBuildSupported=true|directx.packageMode=source-package|opengl.packageBuildSupported=true|opengl.packageMode=source-package"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.missingCapabilities=metal.diagnostic.metal.unsupported-storage-buffer-array|vulkan.missingCapabilities=vulkan.diagnostic.vulkan.prototype-unsupported-runtime-resource-array"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_explain_targets_native_storage_buffer_index_native_fallback
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_BUFFER_OUT_OF_RANGE_DESCRIPTOR_ARRAY_UNSUPPORTED_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=MetalStorageBufferOutOfRangeDescriptorArrayUnsupportedShader|defaultTarget=${CROSSGL_NATIVE_UNSUPPORTED_DEFAULT_TARGET}|buildableTargetCount=3|recommendedTarget=vulkan|recommendedPackageMode=native"
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.sourcePackageSupported=false|metal.packageBuildSupported=false|metal.packageMode=unsupported|metal.packageDecisionReason=unsupported|metal.packageRankScore=2|metal.missingCapabilityCount=2|vulkan.nativeImplemented=true|vulkan.sourcePackageSupported=false|vulkan.packageBuildSupported=true|vulkan.packageMode=native|vulkan.packageDecisionReason=native-package-available|vulkan.packageRankScore=0|vulkan.missingCapabilityCount=0|directx.packageBuildSupported=true|directx.packageMode=source-package|opengl.packageBuildSupported=true|opengl.packageMode=source-package"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.missingCapabilities=metal.backend.native-metal-package|metal.missingCapabilities=metal.diagnostic.metal.unsupported-storage-buffer-array-index|directx.missingCapabilities=directx.backend.native-dxil-package|opengl.missingCapabilities=opengl.backend.native-glsl-package"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_target_decision_explicit_unsupported_native_storage_buffer_index
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_STORAGE_BUFFER_OUT_OF_RANGE_DESCRIPTOR_ARRAY_UNSUPPORTED_SHADER}
    -DTARGET=metal
    -DSTAGE=debug
    -DMODE=dump-stage
    "-DEXPECTED_JSON_FIELDS=schemaVersion=11|targetDecision.requestedTarget=metal|targetDecision.selectedTarget=metal|targetDecision.selectionReason=explicit-target|targetDecision.selectedTargetNativeImplemented=true|targetDecision.selectedTargetSourcePackageSupported=false|targetDecision.selectedTargetPackageBuildSupported=false|targetDecision.selectedTargetPackageMode=unsupported|targetDecision.selectedTargetMissingCapabilityCount=2|targetDecision.selectedTargetDiagnosticCount=1|targetDecision.diagnostics.0.code=target.unsupported|targetDecision.diagnostics.0.target=metal|targetDecision.fallbackTargetRecordCount=3"
    "-DEXPECTED_JSON_ARRAY_CONTAINS=targetDecision.nonViableTargets=metal|targetDecision.viableTargets=vulkan|targetDecision.fallbackTargets=vulkan|targetDecision.selectedTargetMissingCapabilities=metal.backend.native-metal-package|targetDecision.selectedTargetMissingCapabilities=metal.diagnostic.metal.unsupported-storage-buffer-array-index|targetDecision.diagnostics.0.capabilities=metal.backend.native-metal-package|targetDecision.diagnostics.0.capabilities=metal.diagnostic.metal.unsupported-storage-buffer-array-index"
    -DTARGET_EXPLANATION_ROOT=targetDecision
    -DTARGET_RECORD_ARRAY_FIELD=fallbackTargetRecords
    "-DEXPECTED_TARGET_FIELDS=vulkan.nativeImplemented=true|vulkan.packageBuildSupported=true|vulkan.packageMode=native|directx.packageBuildSupported=true|directx.packageMode=source-package|opengl.packageBuildSupported=true|opengl.packageMode=source-package"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_explain_targets_directx_graphics_storage_buffer_source_package_evidence
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=DirectXGraphicsStorageBufferResourceShader|buildableTargetCount=3|recommendedTarget=metal|recommendedPackageMode=native"
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.packageBuildSupported=true|metal.packageMode=native|metal.packageDecisionReason=native-package-available|metal.missingCapabilityCount=0|vulkan.nativeImplemented=true|vulkan.sourcePackageSupported=false|vulkan.packageBuildSupported=true|vulkan.packageMode=native|vulkan.packageDecisionReason=native-package-available|vulkan.requiredCapabilityCount=15|vulkan.missingCapabilityCount=0|directx.nativeImplemented=true|directx.sourcePackageSupported=true|directx.packageBuildSupported=true|directx.packageMode=source-package|directx.packageDecisionReason=source-package-available|directx.requiredCapabilityCount=14|directx.missingCapabilityCount=3|opengl.nativeImplemented=false|opengl.sourcePackageSupported=false|opengl.packageBuildSupported=false|opengl.packageMode=unsupported|opengl.packageDecisionReason=unsupported|opengl.missingCapabilityCount=2"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=vulkan.requiredCapabilities=vulkan.stage.vertex-shader|vulkan.requiredCapabilities=vulkan.stage.fragment-shader|vulkan.requiredCapabilities=vulkan.resource.storage-buffer|vulkan.requiredCapabilities=vulkan.layout.vector-storage-buffer|vulkan.requiredCapabilities=vulkan.operation.storage-buffer-read|vulkan.requiredCapabilities=vulkan.operation.storage-buffer-write|directx.requiredCapabilities=directx.stage.vertex-shader|directx.requiredCapabilities=directx.stage.fragment-shader|directx.requiredCapabilities=directx.resource.storage-buffer|directx.requiredCapabilities=directx.layout.vector-storage-buffer|directx.requiredCapabilities=directx.operation.storage-buffer-read|directx.requiredCapabilities=directx.operation.storage-buffer-write|directx.missingCapabilities=directx.backend.native-dxil-package|directx.missingCapabilities=directx.toolchain.dxc|directx.missingCapabilities=directx.validation.dxil-validator|opengl.missingCapabilities=opengl.backend.glsl-lowering|opengl.missingCapabilities=opengl.diagnostic.opengl.source-unsupported"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_explain_targets_metal_graphics_descriptor_array_native_evidence
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=MetalGraphicsDescriptorArrayShader|buildableTargetCount=2|recommendedTarget=${CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET}|recommendedPackageMode=native"
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.sourcePackageSupported=false|metal.packageBuildSupported=true|metal.packageMode=native|metal.packageDecisionReason=native-package-available|metal.requiredCapabilityCount=21|metal.missingCapabilityCount=0"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.backend.native-metal-package|metal.requiredCapabilities=metal.stage.vertex-shader|metal.requiredCapabilities=metal.stage.fragment-shader|metal.requiredCapabilities=metal.resource.sampled-texture|metal.requiredCapabilities=metal.resource.sampler-state|metal.requiredCapabilities=metal.resource.descriptor-array|metal.requiredCapabilities=metal.layout.fixed-array|metal.requiredCapabilities=metal.texture.depth-compare-format|metal.requiredCapabilities=metal.operation.texture-shadow-compare-explicit-lod"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_explain_targets_opengl_graphics_descriptor_array_source_package_evidence
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_OPENGL_GRAPHICS_DESCRIPTOR_ARRAY_RESOURCES_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=OpenGLGraphicsDescriptorArrayResourcesShader|buildableTargetCount=4"
    "-DEXPECTED_TARGET_FIELDS=opengl.nativeImplemented=false|opengl.sourcePackageSupported=true|opengl.packageBuildSupported=true|opengl.packageMode=source-package|opengl.packageDecisionReason=source-package-available|opengl.requiredCapabilityCount=16|opengl.missingCapabilityCount=3"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=opengl.requiredCapabilities=opengl.stage.vertex-shader|opengl.requiredCapabilities=opengl.stage.fragment-shader|opengl.requiredCapabilities=opengl.resource.sampled-texture|opengl.requiredCapabilities=opengl.resource.sampler-state|opengl.requiredCapabilities=opengl.resource.descriptor-array|opengl.requiredCapabilities=opengl.layout.fixed-array|opengl.requiredCapabilities=opengl.operation.texture-explicit-lod|opengl.missingCapabilities=opengl.backend.native-glsl-package|opengl.missingCapabilities=opengl.toolchain.opengl-driver|opengl.missingCapabilities=opengl.validation.glsl-program-validation"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

add_test(NAME cglc_explain_targets_vulkan_runtime_texture_sampler_descriptor_array_native_evidence
  COMMAND ${CMAKE_COMMAND}
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_VULKAN_RUNTIME_TEXTURE_SAMPLER_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    -DMODE=explain-targets
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|module=VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader|buildableTargetCount=3|recommendedTarget=${CROSSGL_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_RECOMMENDED_TARGET}|recommendedPackageMode=native"
    "-DEXPECTED_TARGET_FIELDS=metal.nativeImplemented=true|metal.sourcePackageSupported=false|metal.packageBuildSupported=true|metal.packageMode=native|metal.packageDecisionReason=native-package-available|metal.requiredCapabilityCount=26|metal.missingCapabilityCount=0|vulkan.nativeImplemented=true|vulkan.sourcePackageSupported=false|vulkan.packageBuildSupported=true|vulkan.packageMode=native|vulkan.packageDecisionReason=native-package-available|vulkan.requiredCapabilityCount=29|vulkan.missingCapabilityCount=0"
    "-DEXPECTED_TARGET_ARRAY_CONTAINS=metal.requiredCapabilities=metal.backend.native-metal-package|metal.requiredCapabilities=metal.stage.compute-kernel|metal.requiredCapabilities=metal.execution.workgroup-size|metal.requiredCapabilities=metal.resource.runtime-descriptor-array|metal.requiredCapabilities=metal.resource.runtime-texture-descriptor-array|metal.requiredCapabilities=metal.resource.runtime-sampler-descriptor-array|metal.requiredCapabilities=metal.layout.runtime-array|metal.requiredCapabilities=metal.resource.descriptor-array|metal.requiredCapabilities=metal.operation.nonuniform-descriptor-index|metal.requiredCapabilities=metal.operation.nonuniform-texture-descriptor-index|metal.requiredCapabilities=metal.operation.nonuniform-sampler-descriptor-index|vulkan.requiredCapabilities=vulkan.backend.vulkan-prototype-package|vulkan.requiredCapabilities=vulkan.stage.compute-kernel|vulkan.requiredCapabilities=vulkan.execution.workgroup-size|vulkan.requiredCapabilities=vulkan.resource.runtime-descriptor-array|vulkan.requiredCapabilities=vulkan.resource.runtime-texture-descriptor-array|vulkan.requiredCapabilities=vulkan.resource.runtime-sampler-descriptor-array|vulkan.requiredCapabilities=vulkan.layout.runtime-array|vulkan.requiredCapabilities=vulkan.resource.descriptor-array|vulkan.requiredCapabilities=vulkan.operation.nonuniform-descriptor-index|vulkan.requiredCapabilities=vulkan.operation.nonuniform-texture-descriptor-index|vulkan.requiredCapabilities=vulkan.operation.nonuniform-sampler-descriptor-index|vulkan.requiredCapabilities=vulkan.extension.SPV_EXT_descriptor_indexing|vulkan.requiredCapabilities=vulkan.capability.ShaderNonUniformEXT|vulkan.requiredCapabilities=vulkan.capability.SampledImageArrayNonUniformIndexingEXT"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)
