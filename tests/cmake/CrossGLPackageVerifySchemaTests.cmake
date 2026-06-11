function(crossgl_add_package_verify_json_schema_test)
  set(one_value_args
    NAME
    TARGET
    INPUT
    OUTPUT
    LOGICAL_INPUT
    SOURCE_REMAP
    MANIFEST_MUTATION_KIND)
  set(multi_value_args
    EXPECTED_JSON_FIELDS
    EXPECTED_JSON_FIELD_ONE_OF
    EXPECTED_JSON_ARRAY_LENGTHS
    EXPECTED_MANIFEST_JSON_FIELDS
    EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS
    EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS
    EXPECTED_DEBUG_METADATA_JSON_FIELDS
    EXPECTED_HIR_SOURCE_MAP_JSON_FIELDS
    EXPECTED_SOURCE_REMAP_PROVENANCE_JSON_FIELDS
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS)
  cmake_parse_arguments(CROSSGL_VERIFY_SCHEMA "" "${one_value_args}"
    "${multi_value_args}" ${ARGN})
  if(NOT CROSSGL_VERIFY_SCHEMA_NAME)
    message(FATAL_ERROR
      "crossgl_add_package_verify_json_schema_test requires NAME")
  endif()
  if(NOT CROSSGL_VERIFY_SCHEMA_TARGET)
    message(FATAL_ERROR
      "crossgl_add_package_verify_json_schema_test requires TARGET")
  endif()
  if(NOT CROSSGL_VERIFY_SCHEMA_INPUT)
    message(FATAL_ERROR
      "crossgl_add_package_verify_json_schema_test requires INPUT")
  endif()
  if(NOT CROSSGL_VERIFY_SCHEMA_OUTPUT)
    set(CROSSGL_VERIFY_SCHEMA_OUTPUT
      "${CMAKE_CURRENT_BINARY_DIR}/${CROSSGL_VERIFY_SCHEMA_TARGET}-verify-schema.cglb")
  endif()

  set(verify_schema_definitions
      -DCGLC=$<TARGET_FILE:cglc>
      "-DINPUT=${CROSSGL_VERIFY_SCHEMA_INPUT}"
      "-DTARGET=${CROSSGL_VERIFY_SCHEMA_TARGET}"
      "-DOUTPUT=${CROSSGL_VERIFY_SCHEMA_OUTPUT}"
      -DMODE=package-verify-json-schema
      "-DEXPECTED_JSON_FIELDS=${CROSSGL_VERIFY_SCHEMA_EXPECTED_JSON_FIELDS}"
      "-DEXPECTED_JSON_FIELD_ONE_OF=${CROSSGL_VERIFY_SCHEMA_EXPECTED_JSON_FIELD_ONE_OF}"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=${CROSSGL_VERIFY_SCHEMA_EXPECTED_JSON_ARRAY_LENGTHS}"
      "-DEXPECTED_MANIFEST_JSON_FIELDS=${CROSSGL_VERIFY_SCHEMA_EXPECTED_MANIFEST_JSON_FIELDS}"
      "-DEXPECTED_MANIFEST_JSON_ARRAY_CONTAINS=${CROSSGL_VERIFY_SCHEMA_EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS}"
      "-DEXPECTED_MANIFEST_JSON_ARRAY_LENGTHS=${CROSSGL_VERIFY_SCHEMA_EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS}"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=${CROSSGL_VERIFY_SCHEMA_EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS}"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS=${CROSSGL_VERIFY_SCHEMA_EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS}"
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=${CROSSGL_VERIFY_SCHEMA_EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS}"
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-verify-v1.schema.json
      -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
  if(CROSSGL_VERIFY_SCHEMA_LOGICAL_INPUT)
    list(APPEND verify_schema_definitions
      "-DLOGICAL_INPUT=${CROSSGL_VERIFY_SCHEMA_LOGICAL_INPUT}")
  endif()
  if(CROSSGL_VERIFY_SCHEMA_SOURCE_REMAP)
    list(APPEND verify_schema_definitions
      "-DSOURCE_REMAP=${CROSSGL_VERIFY_SCHEMA_SOURCE_REMAP}")
  endif()
  if(CROSSGL_VERIFY_SCHEMA_EXPECTED_DEBUG_METADATA_JSON_FIELDS)
    list(APPEND verify_schema_definitions
      "-DEXPECTED_DEBUG_METADATA_JSON_FIELDS=${CROSSGL_VERIFY_SCHEMA_EXPECTED_DEBUG_METADATA_JSON_FIELDS}")
  endif()
  if(CROSSGL_VERIFY_SCHEMA_EXPECTED_HIR_SOURCE_MAP_JSON_FIELDS)
    list(APPEND verify_schema_definitions
      "-DEXPECTED_HIR_SOURCE_MAP_JSON_FIELDS=${CROSSGL_VERIFY_SCHEMA_EXPECTED_HIR_SOURCE_MAP_JSON_FIELDS}")
  endif()
  if(CROSSGL_VERIFY_SCHEMA_EXPECTED_SOURCE_REMAP_PROVENANCE_JSON_FIELDS)
    list(APPEND verify_schema_definitions
      "-DEXPECTED_SOURCE_REMAP_PROVENANCE_JSON_FIELDS=${CROSSGL_VERIFY_SCHEMA_EXPECTED_SOURCE_REMAP_PROVENANCE_JSON_FIELDS}")
  endif()
  if(CROSSGL_VERIFY_SCHEMA_MANIFEST_MUTATION_KIND)
    list(APPEND verify_schema_definitions
      "-DMANIFEST_MUTATION_KIND=${CROSSGL_VERIFY_SCHEMA_MANIFEST_MUTATION_KIND}")
  endif()

  crossgl_add_python_expect_test(
    NAME "${CROSSGL_VERIFY_SCHEMA_NAME}"
    DEFINITIONS ${verify_schema_definitions})
endfunction()

function(crossgl_add_package_verify_json_failure_schema_test)
  set(options TOOLCHAIN_DISABLE_FALLBACK)
  set(one_value_args
    NAME
    FAILURE_KIND
    TARGET
    INPUT
    OUTPUT
    TOOLCHAIN_PATH
    MANIFEST_MUTATION_KIND)
  set(multi_value_args EXPECTED_JSON_FIELDS EXPECTED_JSON_ARRAY_LENGTHS)
  cmake_parse_arguments(CROSSGL_VERIFY_FAILURE_SCHEMA
    "${options}"
    "${one_value_args}" "${multi_value_args}" ${ARGN})
  if(NOT CROSSGL_VERIFY_FAILURE_SCHEMA_NAME)
    message(FATAL_ERROR
      "crossgl_add_package_verify_json_failure_schema_test requires NAME")
  endif()
  if(NOT CROSSGL_VERIFY_FAILURE_SCHEMA_FAILURE_KIND)
    message(FATAL_ERROR
      "crossgl_add_package_verify_json_failure_schema_test requires FAILURE_KIND")
  endif()
  if(NOT CROSSGL_VERIFY_FAILURE_SCHEMA_OUTPUT)
    set(CROSSGL_VERIFY_FAILURE_SCHEMA_OUTPUT
      "${CMAKE_CURRENT_BINARY_DIR}/${CROSSGL_VERIFY_FAILURE_SCHEMA_NAME}.cglb")
  endif()

  set(verify_failure_definitions
      -DCGLC=$<TARGET_FILE:cglc>
      "-DINPUT=${CROSSGL_VERIFY_FAILURE_SCHEMA_INPUT}"
      "-DTARGET=${CROSSGL_VERIFY_FAILURE_SCHEMA_TARGET}"
      "-DOUTPUT=${CROSSGL_VERIFY_FAILURE_SCHEMA_OUTPUT}"
      -DMODE=package-verify-json-failure
      "-DFAILURE_KIND=${CROSSGL_VERIFY_FAILURE_SCHEMA_FAILURE_KIND}"
      "-DEXPECTED_JSON_FIELDS=${CROSSGL_VERIFY_FAILURE_SCHEMA_EXPECTED_JSON_FIELDS}"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=${CROSSGL_VERIFY_FAILURE_SCHEMA_EXPECTED_JSON_ARRAY_LENGTHS}"
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-verify-v1.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      -DSTORED_ZIP_PACKAGE_CREATOR=${CMAKE_CURRENT_FUNCTION_LIST_DIR}/CreateStoredZipPackage.py)
  if(CROSSGL_VERIFY_FAILURE_SCHEMA_TOOLCHAIN_PATH)
    list(APPEND verify_failure_definitions
      "-DTOOLCHAIN_PATH=${CROSSGL_VERIFY_FAILURE_SCHEMA_TOOLCHAIN_PATH}")
  endif()
  if(CROSSGL_VERIFY_FAILURE_SCHEMA_TOOLCHAIN_DISABLE_FALLBACK)
    list(APPEND verify_failure_definitions -DTOOLCHAIN_DISABLE_FALLBACK=ON)
  endif()
  if(CROSSGL_VERIFY_FAILURE_SCHEMA_MANIFEST_MUTATION_KIND)
    list(APPEND verify_failure_definitions
      "-DMANIFEST_MUTATION_KIND=${CROSSGL_VERIFY_FAILURE_SCHEMA_MANIFEST_MUTATION_KIND}")
  endif()

  crossgl_add_python_expect_test(
    NAME "${CROSSGL_VERIFY_FAILURE_SCHEMA_NAME}"
    DEFINITIONS ${verify_failure_definitions})
endfunction()

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_missing_package_failure
  FAILURE_KIND missing-package
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/missing-package-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary=null|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.missing-package"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_invalid_package_dir_failure
  FAILURE_KIND invalid-package-dir
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/invalid-package-dir-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary=null|diagnosticCounts.error=3|diagnostics.0.severity=error|diagnostics.0.code=package.verify.read-failed|diagnostics.1.severity=error|diagnostics.1.code=package.verify.read-failed|diagnostics.2.severity=error|diagnostics.2.code=package.verify.read-failed"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=3")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_stored_zip_package_failure
  FAILURE_KIND stored-zip-package
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/stored-zip-package-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary=null|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.unsupported-format"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_invalid_json_metadata_failure
  FAILURE_KIND invalid-json-metadata
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/invalid-json-metadata-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary=null|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.invalid-json"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_source_mismatch_failure
  FAILURE_KIND source-mismatch
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/source-mismatch-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary.module=StorageBufferComputeShader|summary.target=directx|summary.artifactCount=7|summary.debugArtifactsPresent=true|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.source-hash-mismatch"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_missing_emitted_native_binary_failure
  FAILURE_KIND missing-native-binary
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/missing-emitted-native-binary-verify-schema.cglb
  TOOLCHAIN_PATH ${CROSSGL_FAKE_DXC_SUCCESS_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary.module=StorageBufferComputeShader|summary.target=directx|summary.nativeBinaryStatus=null|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.targetLegalizationEvidence.health=ok|summary.targetLegalizationEvidence.packageMode=native|summary.targetLegalizationEvidence.packageModeSource=manifest.packageArtifactRequirements|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.missing-artifact"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_tampered_native_artifact_descriptor_failure
  FAILURE_KIND tampered-native-artifact-descriptor
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/tampered-native-artifact-descriptor-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary.module=StorageBufferComputeShader|summary.target=directx|summary.nativeBinaryStatus=planned|summary.artifactCount=7|summary.debugArtifactsPresent=true|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.native-artifact-source-path-mismatch"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_planned_native_artifact_optimization_level_failure
  FAILURE_KIND tampered-planned-native-artifact-optimization-level
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/planned-native-artifact-optimization-level-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary.module=StorageBufferComputeShader|summary.target=directx|summary.nativeBinaryStatus=planned|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=invalid|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.native-artifact-descriptor-invalid"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_planned_native_artifact_compiler_tool_failure
  FAILURE_KIND tampered-planned-native-artifact-compiler-tool
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/planned-native-artifact-compiler-tool-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary.module=StorageBufferComputeShader|summary.target=directx|summary.nativeBinaryStatus=planned|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=invalid|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.native-artifact-descriptor-invalid"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_unavailable_native_artifact_validator_tool_failure
  FAILURE_KIND tampered-unavailable-native-artifact-validator-tool
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/unavailable-native-artifact-validator-tool-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary.module=StorageBufferComputeShader|summary.target=directx|summary.nativeBinaryStatus=planned|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=invalid|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.native-artifact-descriptor-invalid"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_null_artifact_requirements_failure
  FAILURE_KIND malformed-package-artifact-requirements
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/null-artifact-requirements-verify-schema.cglb
  MANIFEST_MUTATION_KIND null-package-artifact-requirements
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary=null|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.invalid-manifest|diagnostics.0.message=package manifest packageArtifactRequirements is invalid"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_malformed_artifact_requirements_failure
  FAILURE_KIND malformed-package-artifact-requirements
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/malformed-artifact-requirements-verify-schema.cglb
  MANIFEST_MUTATION_KIND empty-package-artifact-requirements-required-path-artifacts
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary=null|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.invalid-manifest|diagnostics.0.message=package manifest packageArtifactRequirements.requiredPathArtifacts must contain at least one artifact key"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_target_conflicting_artifact_requirements_failure
  FAILURE_KIND target-conflicting-package-artifact-requirements
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/target-conflicting-artifact-requirements-verify-schema.cglb
  MANIFEST_MUTATION_KIND conflicting-package-artifact-requirements-required-path-artifacts
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary.module=StorageBufferComputeShader|summary.target=directx|summary.nativeBinaryStatus=planned|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.targetLegalizationEvidence.health=ok|summary.targetLegalizationEvidence.packageMode=source-package|summary.targetLegalizationEvidence.packageModeSource=manifest.packageArtifactRequirements|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds.0=target-legalization.v1.directx.package-artifacts.source-package|summary.targetLegalizationEvidence.checks.packageArtifactRequirementEvidenceIdsPresent=true|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.invalid-manifest|diagnostics.0.message=package manifest packageArtifactRequirements.requiredPathArtifacts must match manifest target contract: expected [backendSource, nativeBinary], got [backendAssembly, nativeBinary]"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds=6|summary.targetLegalizationEvidence.missingEvidence=0")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_duplicate_selected_target_resource_binding_failure
  FAILURE_KIND duplicate-selected-target-resource-binding
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/duplicate-selected-target-resource-binding-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary.module=StorageBufferComputeShader|summary.target=directx|summary.nativeBinaryStatus=planned|summary.artifactCount=7|summary.debugArtifactsPresent=true|diagnosticCounts.error=2|diagnostics.0.severity=error|diagnostics.0.code=package.verify.reflection-target-resource-binding-duplicate|diagnostics.0.message=reflection selected-target resource binding stage 'compute' entryPoint 'compute_main' name 'values' kind 'buffer' duplicates an earlier binding for target 'directx'|diagnostics.1.severity=error|diagnostics.1.code=package.verify.reflection-target-resource-binding-evidence-duplicate|diagnostics.1.message=reflection selected-target resource binding 'values' duplicates target legalization resource binding evidenceId 'target-legalization.v1.directx.resource-binding.compute.compute_main.values'"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=2")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_selected_target_resource_binding_array_element_count_mismatch_failure
  FAILURE_KIND selected-target-resource-binding-array-element-count-mismatch
  TARGET directx
  INPUT ${CROSSGL_DIRECTX_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/selected-target-resource-binding-array-element-count-mismatch-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary.module=DirectXStorageImageDescriptorArrayShader|summary.target=directx|summary.nativeBinaryStatus=planned|summary.artifactCount=7|summary.debugArtifactsPresent=true|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.reflection-target-resource-binding-array-mismatch|diagnostics.0.message=reflection selected-target resource binding 'colorImages' arrayElementCount must match reflected resource array metadata: expected 2, got 3"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_selected_target_resource_binding_array_element_count_missing_failure
  FAILURE_KIND selected-target-resource-binding-array-element-count-missing
  TARGET directx
  INPUT ${CROSSGL_DIRECTX_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/selected-target-resource-binding-array-element-count-missing-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary.module=DirectXStorageImageDescriptorArrayShader|summary.target=directx|summary.nativeBinaryStatus=planned|summary.artifactCount=7|summary.debugArtifactsPresent=true|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.reflection-target-resource-binding-array-mismatch|diagnostics.0.message=reflection selected-target resource binding 'colorImages' arrayElementCount must match reflected resource array metadata: expected 2, got <missing>"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_verify_json_failure_schema_test(
  NAME cglc_package_verify_json_schema_selected_target_resource_binding_array_dimensions_mismatch_failure
  FAILURE_KIND selected-target-resource-binding-array-dimensions-mismatch
  TARGET directx
  INPUT ${CROSSGL_DIRECTX_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/selected-target-resource-binding-array-dimensions-mismatch-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|summary.module=DirectXStorageImageDescriptorArrayShader|summary.target=directx|summary.nativeBinaryStatus=planned|summary.artifactCount=7|summary.debugArtifactsPresent=true|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.verify.reflection-target-resource-binding-array-mismatch|diagnostics.0.message=reflection selected-target resource binding 'colorImages' arrayDimensions must match reflected resource array metadata: expected [{\"elementCount\":2,\"kind\":\"fixed\",\"source\":\"COUNT\"}], got [{\"elementCount\":3,\"kind\":\"fixed\",\"source\":\"COUNT\"}]"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

set(CROSSGL_DIRECTX_COMPUTE_BACKEND_SOURCE_MAP_PACKAGE_VERIFY_FIELDS
  "summary.backendSourceMap.artifactPresent=true|summary.backendSourceMap.exists=true|summary.backendSourceMap.health=ok|summary.backendSourceMap.path=backend/directx/StorageBufferComputeShader.backend-source-map.json|summary.backendSourceMap.target=directx|summary.backendSourceMap.module=StorageBufferComputeShader|summary.backendSourceMap.mappingGranularity=statement|summary.backendSourceMap.sourceBackend=crossgl-hir|summary.backendSourceMap.targetBackend=hlsl|summary.backendSourceMap.backendLanguage=hlsl|summary.backendSourceMap.checks.identityMatchesContract=true|summary.backendSourceMap.checks.targetMatchesPackage=true|summary.backendSourceMap.checks.moduleMatchesPackage=true|summary.backendSourceMap.checks.mappingGranularityMatchesContract=true|summary.backendSourceMap.checks.sourceBackendPresent=true|summary.backendSourceMap.checks.targetBackendMatchesBackendLanguage=true|summary.backendSourceMap.checks.backendLanguagePresent=true|summary.backendSourceMap.checks.backendLineCountPresent=true|summary.backendSourceMap.checks.backendLineCountMatchesSource=true|summary.backendSourceMap.checks.backendSpansWithinSource=true|summary.backendSourceMap.checks.mappingCountMatchesMappings=true")

crossgl_add_package_verify_json_schema_test(
  NAME cglc_package_verify_json_schema_directx_source_package
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-directx-package-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=true|summary.module=StorageBufferComputeShader|summary.target=directx|summary.artifactCount=7|summary.debugArtifactsPresent=true|${CROSSGL_DIRECTX_COMPUTE_BACKEND_SOURCE_MAP_PACKAGE_VERIFY_FIELDS}|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/directx/StorageBufferComputeShader.native-artifact.json|summary.targetLegalizationEvidence.manifestToolRequirements.present=true|summary.targetLegalizationEvidence.manifestToolRequirements.target=directx|summary.targetLegalizationEvidence.manifestToolRequirements.packageMode=source-package|summary.targetLegalizationEvidence.manifestToolRequirements.requiredToolCount=2|summary.targetLegalizationEvidence.manifestToolRequirements.missingToolCount=2|summary.targetLegalizationEvidence.manifestToolRequirements.optionalNativeToolMissing=true|summary.targetLegalizationEvidence.manifestToolRequirements.optionalNativeToolStatus=missing|summary.targetLegalizationEvidence.checks.manifestToolRequirementsTargetMatchesPackage=true|summary.targetLegalizationEvidence.checks.manifestToolRequirementsPackageModeMatchesRequirements=true|summary.targetLegalizationEvidence.checks.manifestToolRequirementEvidenceIdsPresent=true|summary.targetLegalizationEvidence.checks.debugMetadataToolRequirementsMatchManifest=true|diagnosticCounts.error=0"
  EXPECTED_JSON_FIELD_ONE_OF
    "summary.targetLegalizationEvidence.checks.targetExplanationToolRequirementsMatchManifest=null,true"
  EXPECTED_JSON_ARRAY_LENGTHS
    "summary.targetLegalizationEvidence.manifestToolRequirements.requiredToolIds=2|summary.targetLegalizationEvidence.manifestToolRequirements.missingToolIds=2|summary.targetLegalizationEvidence.manifestToolRequirements.toolRequirementEvidenceIds=5"
  EXPECTED_MANIFEST_JSON_FIELDS
    "schemaVersion=1|target=directx|module=StorageBufferComputeShader|artifacts.backendSource=backend/directx/StorageBufferComputeShader.hlsl|artifacts.nativeBinary=backend/directx/StorageBufferComputeShader.dxil|artifacts.nativeArtifactDescriptor=backend/directx/StorageBufferComputeShader.native-artifact.json"
  EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
    "target=directx|binaryKind=directx.dxil|nativeBinaryStatus=planned|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=unknown|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=unavailable|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O3|optimizationEvidence.profile=compute=cs_6_0|validationStatus=unavailable|toolchainProvenance.tools.0.name=CrossGL-Compiler|toolchainProvenance.tools.0.role=generator|toolchainProvenance.tools.1.name=dxc|toolchainProvenance.tools.1.role=compiler|toolchainProvenance.tools.1.executable=dxc|toolchainProvenance.tools.1.executableSource=not-found|toolchainProvenance.tools.1.versionProbeStatus=unavailable"
  EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS
    "toolchainProvenance.tools=2|validationDiagnostics=0")

set(CROSSGL_PACKAGE_VERIFY_SOURCE_REMAP_FULL_FILE
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-full-file.json")
file(SHA256 "${CROSSGL_PACKAGE_VERIFY_SOURCE_REMAP_FULL_FILE}"
     CROSSGL_PACKAGE_VERIFY_SOURCE_REMAP_FULL_FILE_SHA256)
file(SIZE "${CROSSGL_PACKAGE_VERIFY_SOURCE_REMAP_FULL_FILE}"
     CROSSGL_PACKAGE_VERIFY_SOURCE_REMAP_FULL_FILE_SIZE_BYTES)
crossgl_add_package_verify_json_schema_test(
  NAME cglc_package_verify_json_schema_directx_source_package_logical_source_remap
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-directx-source-remap-package-verify-schema.cglb
  LOGICAL_INPUT generated/from-translator.cgl
  SOURCE_REMAP ${CROSSGL_PACKAGE_VERIFY_SOURCE_REMAP_FULL_FILE}
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=true|summary.module=StorageBufferComputeShader|summary.target=directx|summary.artifactCount=8|summary.debugArtifactsPresent=true|${CROSSGL_DIRECTX_COMPUTE_BACKEND_SOURCE_MAP_PACKAGE_VERIFY_FIELDS}|summary.backendSourceMap.sourceRemapPresent=true|summary.backendSourceMap.sourceRemapGeneratedFile=generated/from-translator.cgl|summary.backendSourceMap.sourceRemapMappingCount=1|summary.backendSourceMap.sourceRemapSha256=${CROSSGL_PACKAGE_VERIFY_SOURCE_REMAP_FULL_FILE_SHA256}|summary.backendSourceMap.sourceRemapSizeBytes=${CROSSGL_PACKAGE_VERIFY_SOURCE_REMAP_FULL_FILE_SIZE_BYTES}|summary.backendSourceMap.checks.sourceRemapHashPresent=true|summary.backendSourceMap.checks.sourceRemapMappingCountPositive=true|summary.backendSourceMap.checks.sourceRemapMatchesProvenance=true|summary.sourceRemap.artifactPresent=true|summary.sourceRemap.exists=true|summary.sourceRemap.health=ok|summary.sourceRemap.path=ir/source-remap-provenance.json|summary.sourceRemap.target=directx|summary.sourceRemap.generatedFile=generated/from-translator.cgl|summary.sourceRemap.mappingGranularity=source-span|summary.sourceRemap.mappingCount=1|summary.sourceRemap.sourceSha256=${CROSSGL_PACKAGE_VERIFY_SOURCE_REMAP_FULL_FILE_SHA256}|summary.sourceRemap.sourceSizeBytes=${CROSSGL_PACKAGE_VERIFY_SOURCE_REMAP_FULL_FILE_SIZE_BYTES}|summary.sourceRemap.checks.identityMatchesContract=true|summary.sourceRemap.checks.targetMatchesPackage=true|summary.sourceRemap.checks.mappingGranularityMatchesContract=true|summary.sourceRemap.checks.mappingCountPositive=true|summary.sourceRemap.checks.sourceHashPresent=true|diagnosticCounts.error=0"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=0"
  EXPECTED_MANIFEST_JSON_FIELDS
    "schemaVersion=1|target=directx|module=StorageBufferComputeShader|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.sourceRemap=ir/source-remap-provenance.json"
  EXPECTED_DEBUG_METADATA_JSON_FIELDS
    "hirSourceLocations.types.0.location.file=generated/from-translator.cgl|hirSourceLocations.types.0.originalLocation.file=shaders/original.crossgl"
  EXPECTED_HIR_SOURCE_MAP_JSON_FIELDS
    "hirSourceLocations.types.0.location.file=generated/from-translator.cgl|hirSourceLocations.types.0.originalLocation.file=shaders/original.crossgl"
  EXPECTED_SOURCE_REMAP_PROVENANCE_JSON_FIELDS
    "schemaVersion=1|kind=crossgl.sourceRemapProvenance|contractVersion=source-remap-provenance-v1|target=directx|generatedFile=generated/from-translator.cgl|mappingCount=1|sourceRemap.sha256.value=${CROSSGL_PACKAGE_VERIFY_SOURCE_REMAP_FULL_FILE_SHA256}|sourceRemap.sizeBytes=${CROSSGL_PACKAGE_VERIFY_SOURCE_REMAP_FULL_FILE_SIZE_BYTES}"
  EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
    "target=directx|binaryKind=directx.dxil|nativeBinaryStatus=planned|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=unknown|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=unavailable|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O3|optimizationEvidence.profile=compute=cs_6_0|validationStatus=unavailable|toolchainProvenance.tools.1.name=dxc|toolchainProvenance.tools.1.executableSource=not-found|toolchainProvenance.tools.1.versionProbeStatus=unavailable"
  EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS
    "toolchainProvenance.tools=2|validationDiagnostics=0")

function(crossgl_add_directx_descriptor_array_package_verify_schema_test)
  set(one_value_args
    NAME
    INPUT
    OUTPUT
    MODULE
    EXPECTED_TARGET_FEATURE_COUNT
    EXPECTED_TARGET_FEATURE_EVIDENCE_COUNT)
  cmake_parse_arguments(CROSSGL_DIRECTX_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA ""
    "${one_value_args}" "" ${ARGN})
  if(NOT CROSSGL_DIRECTX_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_NAME)
    message(FATAL_ERROR
      "crossgl_add_directx_descriptor_array_package_verify_schema_test requires NAME")
  endif()
  if(NOT CROSSGL_DIRECTX_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_INPUT)
    message(FATAL_ERROR
      "crossgl_add_directx_descriptor_array_package_verify_schema_test requires INPUT")
  endif()
  if(NOT CROSSGL_DIRECTX_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_OUTPUT)
    message(FATAL_ERROR
      "crossgl_add_directx_descriptor_array_package_verify_schema_test requires OUTPUT")
  endif()
  if(NOT CROSSGL_DIRECTX_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_MODULE)
    message(FATAL_ERROR
      "crossgl_add_directx_descriptor_array_package_verify_schema_test requires MODULE")
  endif()

  set(directx_descriptor_array_module
      "${CROSSGL_DIRECTX_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_MODULE}")
  set(directx_descriptor_array_target_feature_field "")
  if(DEFINED
      CROSSGL_DIRECTX_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_EXPECTED_TARGET_FEATURE_COUNT)
    set(directx_descriptor_array_target_feature_field
        "|summary.reflection.targetFeatureCount=${CROSSGL_DIRECTX_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_EXPECTED_TARGET_FEATURE_COUNT}")
  endif()
  set(directx_descriptor_array_target_feature_array_length "")
  if(DEFINED
      CROSSGL_DIRECTX_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_EXPECTED_TARGET_FEATURE_EVIDENCE_COUNT)
    set(directx_descriptor_array_target_feature_array_length
        "|summary.reflection.targetFeatureEvidenceIds=${CROSSGL_DIRECTX_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_EXPECTED_TARGET_FEATURE_EVIDENCE_COUNT}")
  endif()
  crossgl_add_package_verify_json_schema_test(
    NAME ${CROSSGL_DIRECTX_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_NAME}
    TARGET directx
    INPUT ${CROSSGL_DIRECTX_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_INPUT}
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/${CROSSGL_DIRECTX_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_OUTPUT}
    EXPECTED_JSON_FIELDS
      "schemaVersion=1|success=true|summary.module=${directx_descriptor_array_module}|summary.target=directx|summary.nativeBinaryStatus=planned|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/directx/${directx_descriptor_array_module}.native-artifact.json${directx_descriptor_array_target_feature_field}|summary.targetLegalizationEvidence.health=ok|summary.targetLegalizationEvidence.packageMode=source-package|summary.targetLegalizationEvidence.packageModeSource=manifest.packageArtifactRequirements|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds.0=target-legalization.v1.directx.package-artifacts.source-package|summary.targetLegalizationEvidence.manifestToolRequirements.present=true|summary.targetLegalizationEvidence.manifestToolRequirements.target=directx|summary.targetLegalizationEvidence.manifestToolRequirements.packageMode=source-package|summary.targetLegalizationEvidence.manifestToolRequirements.requiredToolCount=2|summary.targetLegalizationEvidence.manifestToolRequirements.missingToolCount=2|summary.targetLegalizationEvidence.manifestToolRequirements.optionalNativeToolMissing=true|summary.targetLegalizationEvidence.manifestToolRequirements.optionalNativeToolStatus=missing|summary.targetLegalizationEvidence.checks.packageArtifactRequirementEvidenceIdsPresent=true|summary.targetLegalizationEvidence.checks.manifestToolRequirementsTargetMatchesPackage=true|summary.targetLegalizationEvidence.checks.manifestToolRequirementsPackageModeMatchesRequirements=true|summary.targetLegalizationEvidence.checks.manifestToolRequirementEvidenceIdsPresent=true|summary.targetLegalizationEvidence.checks.debugMetadataToolRequirementsMatchManifest=true|diagnosticCounts.error=0"
    EXPECTED_JSON_FIELD_ONE_OF
      "summary.targetLegalizationEvidence.checks.targetExplanationToolRequirementsMatchManifest=null,true"
    EXPECTED_JSON_ARRAY_LENGTHS
      "diagnostics=0${directx_descriptor_array_target_feature_array_length}|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds=6|summary.targetLegalizationEvidence.missingEvidence=0|summary.targetLegalizationEvidence.manifestToolRequirements.requiredToolIds=2|summary.targetLegalizationEvidence.manifestToolRequirements.missingToolIds=2|summary.targetLegalizationEvidence.manifestToolRequirements.toolRequirementEvidenceIds=5"
    EXPECTED_MANIFEST_JSON_FIELDS
      "schemaVersion=1|target=directx|module=${directx_descriptor_array_module}|targetLegalizationToolRequirements.target=directx|targetLegalizationToolRequirements.packageMode=source-package|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=2|targetLegalizationToolRequirements.optionalNativeToolMissing=true|targetLegalizationToolRequirements.optionalNativeToolStatus=missing|packageArtifactRequirements.target=directx|packageArtifactRequirements.packageMode=source-package|packageArtifactRequirements.requiresNativeBinaryStatus=true|packageArtifactRequirements.allowsPlannedNativeBinary=true|packageArtifactRequirements.allowsPlannedNativeSourceEvidence=true|artifacts.backendSource=backend/directx/${directx_descriptor_array_module}.hlsl|artifacts.nativeBinary=backend/directx/${directx_descriptor_array_module}.dxil|artifacts.nativeBinaryStatus=planned|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/directx/${directx_descriptor_array_module}.native-artifact.json|artifacts.targetExplanation=ir/target-explanation.json"
    EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS
      "targetLegalizationToolRequirements.requiredToolIds=directx.toolchain.dxc|targetLegalizationToolRequirements.missingToolIds=directx.validation.dxil-validator|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.directx.tool-requirement.required.toolchain.dxc|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.directx.tool-requirement.missing.validation.dxil-validator|packageArtifactRequirements.requiredPathArtifacts=backendSource|packageArtifactRequirements.requiredPathArtifacts=nativeBinary|packageArtifactRequirements.evidenceIds=target-legalization.v1.directx.package-artifacts.source-package|packageArtifactRequirements.evidenceIds=target-legalization.v1.directx.package-artifact.native-binary-status.required|packageArtifactRequirements.evidenceIds=target-legalization.v1.directx.package-artifact.planned-native-binary.allowed|packageArtifactRequirements.evidenceIds=target-legalization.v1.directx.package-artifact.planned-native-source-evidence.allowed"
    EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS
      "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=2|targetLegalizationToolRequirements.toolRequirementEvidenceIds=5|packageArtifactRequirements.requiredPathArtifacts=2|packageArtifactRequirements.evidenceIds=6"
    EXPECTED_DEBUG_METADATA_JSON_FIELDS
      "targetDecision.selectedTarget=directx|targetDecision.selectedTargetPackageMode=source-package|targetDecision.selectedTargetSourcePackageSupported=true|targetDecision.selectedTargetRequiredToolCount=2|targetDecision.selectedTargetMissingToolCount=2|targetDecision.selectedTargetOptionalNativeToolMissing=true|targetDecision.selectedTargetOptionalNativeToolStatus=missing"
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
      "target=directx|binaryKind=directx.dxil|sourcePath=backend/directx/${directx_descriptor_array_module}.hlsl|sourceHash.algorithm=sha256|nativeBinaryStatus=planned|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=unknown|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=unavailable|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O3|optimizationEvidence.profile=compute=cs_6_0|validationStatus=unavailable|toolchainProvenance.tools.0.name=CrossGL-Compiler|toolchainProvenance.tools.0.role=generator|toolchainProvenance.tools.1.name=dxc|toolchainProvenance.tools.1.role=compiler|toolchainProvenance.tools.1.executable=dxc|toolchainProvenance.tools.1.executableSource=not-found|toolchainProvenance.tools.1.versionProbeStatus=unavailable"
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS
      "sourceHash.value"
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS
      "toolchainProvenance.tools=2|validationDiagnostics=0")
endfunction()

crossgl_add_directx_descriptor_array_package_verify_schema_test(
  NAME cglc_package_verify_json_schema_directx_storage_image_descriptor_array_source_package
  INPUT ${CROSSGL_DIRECTX_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER}
  OUTPUT test-directx-storage-image-descriptor-array-package-verify-schema.cglb
  MODULE DirectXStorageImageDescriptorArrayShader
  EXPECTED_TARGET_FEATURE_COUNT 22
  EXPECTED_TARGET_FEATURE_EVIDENCE_COUNT 32)

crossgl_add_directx_descriptor_array_package_verify_schema_test(
  NAME cglc_package_verify_json_schema_directx_storage_image_nonuniform_descriptor_array_source_package
  INPUT ${CROSSGL_DIRECTX_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
  OUTPUT test-directx-storage-image-nonuniform-descriptor-array-package-verify-schema.cglb
  MODULE DirectXStorageImageNonUniformDescriptorArrayShader)

crossgl_add_directx_descriptor_array_package_verify_schema_test(
  NAME cglc_package_verify_json_schema_directx_texture_compare_descriptor_array_source_package
  INPUT ${CROSSGL_TEXTURE_COMPARE_DESCRIPTOR_ARRAY_SHADER}
  OUTPUT test-directx-texture-compare-descriptor-array-package-verify-schema.cglb
  MODULE TextureCompareDescriptorArrayShader)

crossgl_add_directx_descriptor_array_package_verify_schema_test(
  NAME cglc_package_verify_json_schema_directx_storage_image_explicit_format_descriptor_array_source_package
  INPUT ${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
  OUTPUT test-directx-storage-image-explicit-format-descriptor-array-package-verify-schema.cglb
  MODULE StorageImageExplicitFormatDescriptorArrayShader)

crossgl_add_directx_descriptor_array_package_verify_schema_test(
  NAME cglc_package_verify_json_schema_directx_storage_image_atomic_descriptor_array_source_package
  INPUT ${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
  OUTPUT test-directx-storage-image-atomic-descriptor-array-package-verify-schema.cglb
  MODULE StorageImageAtomicDescriptorArrayShader)

crossgl_add_package_verify_json_schema_test(
  NAME cglc_package_verify_json_schema_directx_storage_image_access_qualifier_source_package
  TARGET directx
  INPUT ${CROSSGL_DIRECTX_STORAGE_IMAGE_ACCESS_QUALIFIER_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-directx-storage-image-access-qualifier-package-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=true|summary.module=DirectXStorageImageAccessQualifierShader|summary.target=directx|summary.nativeBinaryStatus=planned|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/directx/DirectXStorageImageAccessQualifierShader.native-artifact.json|summary.targetLegalizationEvidence.health=ok|summary.targetLegalizationEvidence.packageMode=source-package|summary.targetLegalizationEvidence.packageModeSource=manifest.packageArtifactRequirements|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds.0=target-legalization.v1.directx.package-artifacts.source-package|summary.targetLegalizationEvidence.manifestToolRequirements.present=true|summary.targetLegalizationEvidence.manifestToolRequirements.target=directx|summary.targetLegalizationEvidence.manifestToolRequirements.packageMode=source-package|summary.targetLegalizationEvidence.manifestToolRequirements.requiredToolCount=2|summary.targetLegalizationEvidence.manifestToolRequirements.missingToolCount=2|summary.targetLegalizationEvidence.manifestToolRequirements.optionalNativeToolMissing=true|summary.targetLegalizationEvidence.manifestToolRequirements.optionalNativeToolStatus=missing|summary.targetLegalizationEvidence.debugMetadata.target=directx|summary.targetLegalizationEvidence.debugMetadata.packageMode=source-package|summary.targetLegalizationEvidence.checks.packageArtifactRequirementEvidenceIdsPresent=true|summary.targetLegalizationEvidence.checks.manifestToolRequirementsTargetMatchesPackage=true|summary.targetLegalizationEvidence.checks.manifestToolRequirementsPackageModeMatchesRequirements=true|summary.targetLegalizationEvidence.checks.manifestToolRequirementEvidenceIdsPresent=true|summary.targetLegalizationEvidence.checks.debugMetadataTargetMatchesPackage=true|summary.targetLegalizationEvidence.checks.debugMetadataPackageModeMatchesRequirements=true|summary.targetLegalizationEvidence.checks.debugMetadataToolRequirementsMatchManifest=true|diagnosticCounts.error=0"
  EXPECTED_JSON_FIELD_ONE_OF
    "summary.targetLegalizationEvidence.checks.targetExplanationToolRequirementsMatchManifest=null,true"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=0|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds=6|summary.targetLegalizationEvidence.missingEvidence=0|summary.targetLegalizationEvidence.manifestToolRequirements.requiredToolIds=2|summary.targetLegalizationEvidence.manifestToolRequirements.missingToolIds=2|summary.targetLegalizationEvidence.manifestToolRequirements.toolRequirementEvidenceIds=5"
  EXPECTED_MANIFEST_JSON_FIELDS
    "schemaVersion=1|target=directx|module=DirectXStorageImageAccessQualifierShader|targetLegalizationToolRequirements.target=directx|targetLegalizationToolRequirements.packageMode=source-package|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=2|targetLegalizationToolRequirements.optionalNativeToolMissing=true|targetLegalizationToolRequirements.optionalNativeToolStatus=missing|packageArtifactRequirements.target=directx|packageArtifactRequirements.packageMode=source-package|packageArtifactRequirements.requiresNativeBinaryStatus=true|packageArtifactRequirements.allowsPlannedNativeBinary=true|packageArtifactRequirements.allowsPlannedNativeSourceEvidence=true|artifacts.backendSource=backend/directx/DirectXStorageImageAccessQualifierShader.hlsl|artifacts.nativeBinary=backend/directx/DirectXStorageImageAccessQualifierShader.dxil|artifacts.nativeBinaryStatus=planned|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/directx/DirectXStorageImageAccessQualifierShader.native-artifact.json|artifacts.targetExplanation=ir/target-explanation.json"
  EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS
    "targetLegalizationToolRequirements.requiredToolIds=directx.toolchain.dxc|targetLegalizationToolRequirements.missingToolIds=directx.validation.dxil-validator|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.directx.tool-requirement.required.toolchain.dxc|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.directx.tool-requirement.missing.validation.dxil-validator|packageArtifactRequirements.requiredPathArtifacts=backendSource|packageArtifactRequirements.requiredPathArtifacts=nativeBinary|packageArtifactRequirements.evidenceIds=target-legalization.v1.directx.package-artifacts.source-package|packageArtifactRequirements.evidenceIds=target-legalization.v1.directx.package-artifact.native-binary-status.required|packageArtifactRequirements.evidenceIds=target-legalization.v1.directx.package-artifact.planned-native-binary.allowed|packageArtifactRequirements.evidenceIds=target-legalization.v1.directx.package-artifact.planned-native-source-evidence.allowed"
  EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS
    "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=2|targetLegalizationToolRequirements.toolRequirementEvidenceIds=5|packageArtifactRequirements.requiredPathArtifacts=2|packageArtifactRequirements.evidenceIds=6"
  EXPECTED_DEBUG_METADATA_JSON_FIELDS
    "targetDecision.selectedTarget=directx|targetDecision.selectedTargetPackageMode=source-package|targetDecision.selectedTargetSourcePackageSupported=true|targetDecision.selectedTargetRequiredToolCount=2|targetDecision.selectedTargetMissingToolCount=2|targetDecision.selectedTargetOptionalNativeToolMissing=true|targetDecision.selectedTargetOptionalNativeToolStatus=missing"
  EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
    "target=directx|binaryKind=directx.dxil|sourcePath=backend/directx/DirectXStorageImageAccessQualifierShader.hlsl|sourceHash.algorithm=sha256|nativeBinaryStatus=planned|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=unknown|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=unavailable|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O3|optimizationEvidence.profile=compute=cs_6_0|validationStatus=unavailable|toolchainProvenance.tools.0.name=CrossGL-Compiler|toolchainProvenance.tools.0.role=generator|toolchainProvenance.tools.1.name=dxc|toolchainProvenance.tools.1.role=compiler|toolchainProvenance.tools.1.executable=dxc|toolchainProvenance.tools.1.executableSource=not-found|toolchainProvenance.tools.1.versionProbeStatus=unavailable"
  EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS
    "sourceHash.value"
  EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS
    "toolchainProvenance.tools=2|validationDiagnostics=0")

crossgl_add_package_verify_json_schema_test(
  NAME cglc_package_verify_json_schema_legacy_missing_artifact_requirements_compat
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/legacy-missing-artifact-requirements-verify-schema.cglb
  MANIFEST_MUTATION_KIND remove-package-artifact-requirements
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=true|summary.module=StorageBufferComputeShader|summary.target=directx|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/directx/StorageBufferComputeShader.native-artifact.json|diagnosticCounts.note=1|diagnosticCounts.error=0|diagnostics.0.severity=note|diagnostics.0.code=package.verify.legacy-artifact-requirements-fallback|diagnostics.0.message=manifest is missing packageArtifactRequirements and is using legacy compatibility defaults for package verification only"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1"
  EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
    "target=directx|binaryKind=directx.dxil|nativeBinaryStatus=planned|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=unknown|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=unavailable|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O3|optimizationEvidence.profile=compute=cs_6_0|validationStatus=unavailable|toolchainProvenance.tools.0.name=CrossGL-Compiler|toolchainProvenance.tools.0.role=generator|toolchainProvenance.tools.1.name=dxc|toolchainProvenance.tools.1.role=compiler|toolchainProvenance.tools.1.executable=dxc|toolchainProvenance.tools.1.executableSource=not-found|toolchainProvenance.tools.1.versionProbeStatus=unavailable"
  EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS
    "toolchainProvenance.tools=2|validationDiagnostics=0")

function(crossgl_add_directx_compute_fake_dxc_package_verify_test)
  set(options TOOLCHAIN_DISABLE_FALLBACK)
  set(one_value_args
    NAME
    TOOLCHAIN_PATH
    EXPECTED_NATIVE_BINARY_STATUS
    EXPECTED_TOOL_LOG
    EXPECTED_TOOL_LOG_CONTAINS)
  cmake_parse_arguments(CROSSGL_DIRECTX_FAKE_DXC_VERIFY
    "${options}" "${one_value_args}" "" ${ARGN})
  if(NOT CROSSGL_DIRECTX_FAKE_DXC_VERIFY_NAME)
    message(FATAL_ERROR
      "crossgl_add_directx_compute_fake_dxc_package_verify_test requires NAME")
  endif()
  if(NOT CROSSGL_DIRECTX_FAKE_DXC_VERIFY_TOOLCHAIN_PATH)
    message(FATAL_ERROR
      "crossgl_add_directx_compute_fake_dxc_package_verify_test requires TOOLCHAIN_PATH")
  endif()
  if(NOT CROSSGL_DIRECTX_FAKE_DXC_VERIFY_EXPECTED_NATIVE_BINARY_STATUS)
    message(FATAL_ERROR
      "crossgl_add_directx_compute_fake_dxc_package_verify_test requires EXPECTED_NATIVE_BINARY_STATUS")
  endif()

  set(directx_fake_dxc_verify_native_descriptor_paths
    "sourceHash.value")
  set(directx_fake_dxc_verify_native_descriptor_fields
    "|sourceHash.algorithm=sha256|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=unknown|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=unavailable|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O3|optimizationEvidence.profile=compute=cs_6_0|toolchainProvenance.tools.0.name=CrossGL-Compiler|toolchainProvenance.tools.0.role=generator|toolchainProvenance.tools.1.name=dxc|toolchainProvenance.tools.1.role=compiler|toolchainProvenance.tools.1.executable=dxc|toolchainProvenance.tools.1.executableSource=not-found|toolchainProvenance.tools.1.versionProbeStatus=unavailable|validationStatus=unavailable")
  set(directx_fake_dxc_verify_native_descriptor_array_lengths
    "toolchainProvenance.tools=2|validationDiagnostics=0")
  if(CROSSGL_DIRECTX_FAKE_DXC_VERIFY_EXPECTED_NATIVE_BINARY_STATUS STREQUAL
     "planned" AND CROSSGL_DIRECTX_FAKE_DXC_VERIFY_EXPECTED_TOOL_LOG)
    set(directx_fake_dxc_verify_native_descriptor_fields
      "|sourceHash.algorithm=sha256|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=unknown|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=not-run|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O3|optimizationEvidence.profile=compute=cs_6_0|toolchainProvenance.tools.0.name=CrossGL-Compiler|toolchainProvenance.tools.0.role=generator|toolchainProvenance.tools.1.name=dxc|toolchainProvenance.tools.1.role=compiler|toolchainProvenance.tools.1.executable=dxc|toolchainProvenance.tools.1.executableSource=PATH|toolchainProvenance.tools.1.versionProbeStatus=failed|validationStatus=unavailable")
  endif()
  if(CROSSGL_DIRECTX_FAKE_DXC_VERIFY_EXPECTED_NATIVE_BINARY_STATUS STREQUAL
     "emitted")
    set(directx_fake_dxc_verify_native_descriptor_paths
      "sourceHash.value|artifactHash.value|sizeBytes|toolchainProvenance.tools.1.resolvedExecutable|toolchainProvenance.tools.1.versionDetail")
    set(directx_fake_dxc_verify_native_descriptor_fields
      "|sourceHash.algorithm=sha256|artifactPath=backend/directx/StorageBufferComputeShader.dxil|artifactHash.algorithm=sha256|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=O3|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=applied|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O3|optimizationEvidence.profile=compute=cs_6_0|validationStatus=not-run|toolchainProvenance.tools.1.name=dxc|toolchainProvenance.tools.1.role=compiler|toolchainProvenance.tools.1.version=unknown|toolchainProvenance.tools.1.executable=dxc|toolchainProvenance.tools.1.executableSource=PATH|toolchainProvenance.tools.1.versionProbeStatus=failed")
    set(directx_fake_dxc_verify_native_descriptor_array_lengths
      "toolchainProvenance.tools=2|validationDiagnostics=0")
  endif()

  set(directx_fake_dxc_verify_summary_native_binary_status
    "${CROSSGL_DIRECTX_FAKE_DXC_VERIFY_EXPECTED_NATIVE_BINARY_STATUS}")
  set(directx_fake_dxc_verify_manifest_native_binary_status_field
    "|artifacts.nativeBinaryStatus=${CROSSGL_DIRECTX_FAKE_DXC_VERIFY_EXPECTED_NATIVE_BINARY_STATUS}")
  set(directx_fake_dxc_verify_raw_descriptor_native_binary_status_field
    "|nativeBinaryStatus=${CROSSGL_DIRECTX_FAKE_DXC_VERIFY_EXPECTED_NATIVE_BINARY_STATUS}")
  set(directx_fake_dxc_verify_manifest_package_fields
    "targetLegalizationToolRequirements.packageMode=source-package|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=2|targetLegalizationToolRequirements.optionalNativeToolMissing=true|targetLegalizationToolRequirements.optionalNativeToolStatus=missing|packageArtifactRequirements.packageMode=source-package|packageArtifactRequirements.requiresNativeBinaryStatus=true|packageArtifactRequirements.allowsPlannedNativeBinary=true|packageArtifactRequirements.allowsPlannedNativeSourceEvidence=true")
  set(directx_fake_dxc_verify_manifest_array_contains
    "targetLegalizationToolRequirements.requiredToolIds=directx.toolchain.dxc|targetLegalizationToolRequirements.missingToolIds=directx.validation.dxil-validator|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.directx.tool-requirement.required.toolchain.dxc|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.directx.tool-requirement.missing.validation.dxil-validator")
  set(directx_fake_dxc_verify_manifest_array_lengths
    "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=2|targetLegalizationToolRequirements.toolRequirementEvidenceIds=5")
  if(CROSSGL_DIRECTX_FAKE_DXC_VERIFY_EXPECTED_NATIVE_BINARY_STATUS STREQUAL
     "emitted")
    set(directx_fake_dxc_verify_summary_native_binary_status "null")
    set(directx_fake_dxc_verify_manifest_native_binary_status_field "")
    set(directx_fake_dxc_verify_raw_descriptor_native_binary_status_field "")
    set(directx_fake_dxc_verify_manifest_package_fields
      "targetLegalizationToolRequirements.packageMode=native|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=0|targetLegalizationToolRequirements.optionalNativeToolMissing=false|targetLegalizationToolRequirements.optionalNativeToolStatus=not-required|packageArtifactRequirements.packageMode=native|packageArtifactRequirements.requiresNativeBinaryStatus=false|packageArtifactRequirements.allowsPlannedNativeBinary=false|packageArtifactRequirements.allowsPlannedNativeSourceEvidence=false")
    set(directx_fake_dxc_verify_manifest_array_contains
      "targetLegalizationToolRequirements.requiredToolIds=directx.toolchain.dxc|targetLegalizationToolRequirements.requiredToolIds=directx.validation.dxil-validator|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.directx.tool-requirement.required.toolchain.dxc|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.directx.tool-requirement.required.validation.dxil-validator")
    set(directx_fake_dxc_verify_manifest_array_lengths
      "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=0|targetLegalizationToolRequirements.toolRequirementEvidenceIds=3")
  endif()
  set(verify_definitions
    -DCGLC=$<TARGET_FILE:cglc>
    "-DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}"
    -DTARGET=directx
    "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/${CROSSGL_DIRECTX_FAKE_DXC_VERIFY_NAME}.cglb"
    -DMODE=package-verify-json-schema
    "-DTOOLCHAIN_PATH=${CROSSGL_DIRECTX_FAKE_DXC_VERIFY_TOOLCHAIN_PATH}"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|success=true|summary.module=StorageBufferComputeShader|summary.target=directx|summary.nativeBinaryStatus=${directx_fake_dxc_verify_summary_native_binary_status}|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/directx/StorageBufferComputeShader.native-artifact.json|diagnosticCounts.error=0"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=directx|module=StorageBufferComputeShader|targetLegalizationToolRequirements.target=directx|${directx_fake_dxc_verify_manifest_package_fields}|artifacts.backendSource=backend/directx/StorageBufferComputeShader.hlsl|artifacts.nativeBinary=backend/directx/StorageBufferComputeShader.dxil${directx_fake_dxc_verify_manifest_native_binary_status_field}|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/directx/StorageBufferComputeShader.native-artifact.json"
    "-DEXPECTED_MANIFEST_JSON_ARRAY_CONTAINS=${directx_fake_dxc_verify_manifest_array_contains}"
    "-DEXPECTED_MANIFEST_JSON_ARRAY_LENGTHS=${directx_fake_dxc_verify_manifest_array_lengths}"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=directx|binaryKind=directx.dxil|sourcePath=backend/directx/StorageBufferComputeShader.hlsl${directx_fake_dxc_verify_raw_descriptor_native_binary_status_field}${directx_fake_dxc_verify_native_descriptor_fields}"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-verify-v1.schema.json
    -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
  if(directx_fake_dxc_verify_native_descriptor_paths)
    list(APPEND verify_definitions
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS=${directx_fake_dxc_verify_native_descriptor_paths}")
  endif()
  if(directx_fake_dxc_verify_native_descriptor_array_lengths)
    list(APPEND verify_definitions
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=${directx_fake_dxc_verify_native_descriptor_array_lengths}")
  endif()
  if(CROSSGL_DIRECTX_FAKE_DXC_VERIFY_TOOLCHAIN_DISABLE_FALLBACK)
    list(APPEND verify_definitions -DTOOLCHAIN_DISABLE_FALLBACK=ON)
  endif()
  if(CROSSGL_DIRECTX_FAKE_DXC_VERIFY_EXPECTED_TOOL_LOG)
    list(APPEND verify_definitions
      "-DEXPECTED_TOOL_LOG=${CROSSGL_DIRECTX_FAKE_DXC_VERIFY_EXPECTED_TOOL_LOG}")
  endif()
  if(CROSSGL_DIRECTX_FAKE_DXC_VERIFY_EXPECTED_TOOL_LOG_CONTAINS)
    list(APPEND verify_definitions
      "-DEXPECTED_TOOL_LOG_CONTAINS=${CROSSGL_DIRECTX_FAKE_DXC_VERIFY_EXPECTED_TOOL_LOG_CONTAINS}")
  endif()

  crossgl_add_python_expect_test(
    NAME "${CROSSGL_DIRECTX_FAKE_DXC_VERIFY_NAME}"
    DEFINITIONS ${verify_definitions})
endfunction()

crossgl_add_directx_compute_fake_dxc_package_verify_test(
  NAME cglc_package_verify_directx_compute_fake_dxc_success
  TOOLCHAIN_PATH ${CROSSGL_FAKE_DXC_SUCCESS_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_NATIVE_BINARY_STATUS emitted
  EXPECTED_TOOL_LOG ${CROSSGL_FAKE_DXC_SUCCESS_DIR}/dxc.log
  EXPECTED_TOOL_LOG_CONTAINS "-T cs_6_0 -E compute_main -Fo")

crossgl_add_directx_compute_fake_dxc_package_verify_test(
  NAME cglc_package_verify_directx_compute_fake_dxc_tool_failure
  TOOLCHAIN_PATH ${CROSSGL_FAKE_DXC_FAILURE_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_NATIVE_BINARY_STATUS planned
  EXPECTED_TOOL_LOG ${CROSSGL_FAKE_DXC_FAILURE_DIR}/dxc.log
  EXPECTED_TOOL_LOG_CONTAINS "-T cs_6_0 -E compute_main -Fo")

crossgl_add_directx_compute_fake_dxc_package_verify_test(
  NAME cglc_package_verify_directx_compute_fake_dxc_unavailable
  TOOLCHAIN_PATH ${CROSSGL_FAKE_TOOL_UNAVAILABLE_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_NATIVE_BINARY_STATUS planned)

function(crossgl_add_opengl_compute_fake_glslang_package_verify_test)
  set(options TOOLCHAIN_DISABLE_FALLBACK)
  set(one_value_args
    NAME
    TOOLCHAIN_PATH
    EXPECTED_NATIVE_BINARY_STATUS
    EXPECTED_VALIDATION_STATUS
    EXPECTED_TOOL_LOG
    EXPECTED_TOOL_LOG_CONTAINS)
  cmake_parse_arguments(CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY
    "${options}" "${one_value_args}" "" ${ARGN})
  if(NOT CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_NAME)
    message(FATAL_ERROR
      "crossgl_add_opengl_compute_fake_glslang_package_verify_test requires NAME")
  endif()
  if(NOT CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_TOOLCHAIN_PATH)
    message(FATAL_ERROR
      "crossgl_add_opengl_compute_fake_glslang_package_verify_test requires TOOLCHAIN_PATH")
  endif()
  if(NOT CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_EXPECTED_NATIVE_BINARY_STATUS)
    message(FATAL_ERROR
      "crossgl_add_opengl_compute_fake_glslang_package_verify_test requires EXPECTED_NATIVE_BINARY_STATUS")
  endif()
  if(NOT CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_EXPECTED_VALIDATION_STATUS)
    set(CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_EXPECTED_VALIDATION_STATUS
      unavailable)
  endif()

  set(opengl_fake_glslang_verify_native_descriptor_paths
    "sourceHash.value")
  set(opengl_fake_glslang_verify_native_descriptor_fields
    "|sourceHash.algorithm=sha256|toolchainProvenance.tools.0.name=CrossGL OpenGL backend|toolchainProvenance.tools.0.role=generator|toolchainProvenance.tools.0.executable=cglc|validationStatus=unavailable")
  set(opengl_fake_glslang_verify_native_descriptor_array_lengths
    "toolchainProvenance.tools=1|validationDiagnostics=0")
  if(CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_EXPECTED_NATIVE_BINARY_STATUS
     STREQUAL "validated")
    set(opengl_fake_glslang_verify_native_descriptor_paths
      "sourceHash.value|artifactHash.value|sizeBytes|toolchainProvenance.tools.1.resolvedExecutable|toolchainProvenance.tools.1.versionDetail")
    set(opengl_fake_glslang_verify_native_descriptor_fields
      "|sourceHash.algorithm=sha256|artifactPath=backend/opengl/StorageBufferComputeShader.glsl|artifactHash.algorithm=sha256|validationStatus=validated|toolchainProvenance.tools.1.name=glslangValidator|toolchainProvenance.tools.1.role=validator|toolchainProvenance.tools.1.version=unknown|toolchainProvenance.tools.1.executable=glslangValidator|toolchainProvenance.tools.1.executableSource=PATH|toolchainProvenance.tools.1.versionProbeStatus=failed")
    set(opengl_fake_glslang_verify_native_descriptor_array_lengths
      "toolchainProvenance.tools=2|validationDiagnostics=0")
  elseif(CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_EXPECTED_VALIDATION_STATUS
         STREQUAL "failed")
    set(opengl_fake_glslang_verify_native_descriptor_paths
      "sourceHash.value|toolchainProvenance.tools.1.resolvedExecutable|toolchainProvenance.tools.1.versionDetail")
    set(opengl_fake_glslang_verify_native_descriptor_fields
      "|sourceHash.algorithm=sha256|toolchainProvenance.tools.0.name=CrossGL-Compiler|toolchainProvenance.tools.0.role=generator|toolchainProvenance.tools.1.name=glslangValidator|toolchainProvenance.tools.1.role=validator|toolchainProvenance.tools.1.version=unknown|toolchainProvenance.tools.1.executable=glslangValidator|toolchainProvenance.tools.1.executableSource=PATH|toolchainProvenance.tools.1.versionProbeStatus=failed|validationStatus=failed|validationDiagnostics.0.code=opengl.glslang-failed")
    set(opengl_fake_glslang_verify_native_descriptor_array_lengths
      "toolchainProvenance.tools=2|validationDiagnostics=1")
  endif()

  set(verify_definitions
    -DCGLC=$<TARGET_FILE:cglc>
    "-DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}"
    -DTARGET=opengl
    "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/${CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_NAME}.cglb"
    -DMODE=package-verify-json-schema
    "-DTOOLCHAIN_PATH=${CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_TOOLCHAIN_PATH}"
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|success=true|summary.module=StorageBufferComputeShader|summary.target=opengl|summary.nativeBinaryStatus=${CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_EXPECTED_NATIVE_BINARY_STATUS}|summary.artifactCount=6|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/opengl/StorageBufferComputeShader.native-artifact.json|diagnosticCounts.error=0"
    "-DEXPECTED_MANIFEST_JSON_FIELDS=schemaVersion=1|target=opengl|module=StorageBufferComputeShader|targetLegalizationToolRequirements.target=opengl|targetLegalizationToolRequirements.packageMode=source-package|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=2|targetLegalizationToolRequirements.optionalNativeToolMissing=true|targetLegalizationToolRequirements.optionalNativeToolStatus=missing|artifacts.backendSource=backend/opengl/StorageBufferComputeShader.comp.glsl|artifacts.nativeBinary=backend/opengl/StorageBufferComputeShader.glsl|artifacts.nativeBinaryStatus=${CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_EXPECTED_NATIVE_BINARY_STATUS}|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/opengl/StorageBufferComputeShader.native-artifact.json"
    "-DEXPECTED_MANIFEST_JSON_ARRAY_CONTAINS=targetLegalizationToolRequirements.requiredToolIds=opengl.toolchain.opengl-driver|targetLegalizationToolRequirements.missingToolIds=opengl.validation.glsl-program-validation|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.opengl.tool-requirement.required.toolchain.opengl-driver|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.opengl.tool-requirement.missing.validation.glsl-program-validation"
    "-DEXPECTED_MANIFEST_JSON_ARRAY_LENGTHS=targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=2|targetLegalizationToolRequirements.toolRequirementEvidenceIds=5"
    "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS=target=opengl|binaryKind=opengl.source|sourcePath=backend/opengl/StorageBufferComputeShader.comp.glsl|nativeBinaryStatus=${CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_EXPECTED_NATIVE_BINARY_STATUS}${opengl_fake_glslang_verify_native_descriptor_fields}"
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-verify-v1.schema.json
    -DNATIVE_ARTIFACT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/native-artifact-v0.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py)
  if(opengl_fake_glslang_verify_native_descriptor_paths)
    list(APPEND verify_definitions
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_PATHS=${opengl_fake_glslang_verify_native_descriptor_paths}")
  endif()
  if(opengl_fake_glslang_verify_native_descriptor_array_lengths)
    list(APPEND verify_definitions
      "-DEXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS=${opengl_fake_glslang_verify_native_descriptor_array_lengths}")
  endif()
  if(CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_TOOLCHAIN_DISABLE_FALLBACK)
    list(APPEND verify_definitions -DTOOLCHAIN_DISABLE_FALLBACK=ON)
  endif()
  if(CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_EXPECTED_TOOL_LOG)
    list(APPEND verify_definitions
      "-DEXPECTED_TOOL_LOG=${CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_EXPECTED_TOOL_LOG}")
  endif()
  if(CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_EXPECTED_TOOL_LOG_CONTAINS)
    list(APPEND verify_definitions
      "-DEXPECTED_TOOL_LOG_CONTAINS=${CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_EXPECTED_TOOL_LOG_CONTAINS}")
  endif()

  crossgl_add_python_expect_test(
    NAME "${CROSSGL_OPENGL_FAKE_GLSLANG_VERIFY_NAME}"
    DEFINITIONS ${verify_definitions})
endfunction()

crossgl_add_opengl_compute_fake_glslang_package_verify_test(
  NAME cglc_package_verify_opengl_compute_fake_glslang_success_source_package
  TOOLCHAIN_PATH ${CROSSGL_FAKE_GLSLANG_SUCCESS_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_NATIVE_BINARY_STATUS validated
  EXPECTED_TOOL_LOG ${CROSSGL_FAKE_GLSLANG_SUCCESS_DIR}/glslangValidator.log
  EXPECTED_TOOL_LOG_CONTAINS "glslangValidator success: -S comp")

crossgl_add_opengl_compute_fake_glslang_package_verify_test(
  NAME cglc_package_verify_opengl_compute_fake_glslang_source_package_tool_failure
  TOOLCHAIN_PATH ${CROSSGL_FAKE_GLSLANG_FAILURE_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_NATIVE_BINARY_STATUS planned
  EXPECTED_VALIDATION_STATUS failed
  EXPECTED_TOOL_LOG ${CROSSGL_FAKE_GLSLANG_FAILURE_DIR}/glslangValidator.log
  EXPECTED_TOOL_LOG_CONTAINS "glslangValidator failure: -S comp")

crossgl_add_opengl_compute_fake_glslang_package_verify_test(
  NAME cglc_package_verify_opengl_compute_fake_glslang_source_package_unavailable
  TOOLCHAIN_PATH ${CROSSGL_FAKE_TOOL_UNAVAILABLE_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_NATIVE_BINARY_STATUS planned)

crossgl_label_optional_native_policy_test(
  cglc_package_verify_opengl_compute_fake_glslang_source_package_tool_failure
  opengl)
crossgl_label_optional_native_policy_test(
  cglc_package_verify_opengl_compute_fake_glslang_source_package_unavailable
  opengl)
set_tests_properties(
  cglc_package_verify_opengl_compute_fake_glslang_source_package_tool_failure
  cglc_package_verify_opengl_compute_fake_glslang_source_package_unavailable
  PROPERTIES PROCESSORS 2)
set_property(TEST
  cglc_package_verify_opengl_compute_fake_glslang_source_package_tool_failure
  cglc_package_verify_opengl_compute_fake_glslang_source_package_unavailable
  APPEND PROPERTY LABELS package-verify-build)

set(CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_STATUS planned)
crossgl_add_package_verify_json_schema_test(
  NAME cglc_package_verify_json_schema_directx_graphics_resources_source_package
  TARGET directx
  INPUT ${CROSSGL_DIRECTX_GRAPHICS_RESOURCE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-resources-package-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=true|summary.module=DirectXGraphicsResourceShader|summary.target=directx|summary.nativeBinaryStatus=${CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|summary.artifactCount=8|summary.debugArtifactsPresent=true|diagnosticCounts.error=0"
  EXPECTED_MANIFEST_JSON_FIELDS
    "schemaVersion=1|target=directx|module=DirectXGraphicsResourceShader|artifacts.backendSource=backend/directx/DirectXGraphicsResourceShader.graphics.hlsl|artifacts.nativeBinary=backend/directx/DirectXGraphicsResourceShader.dxil|artifacts.nativeBinaryStatus=${CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/directx/DirectXGraphicsResourceShader.native-artifact.json|artifacts.graphicsAbi=backend/directx/DirectXGraphicsResourceShader.graphics-abi.json"
  EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
    "target=directx|binaryKind=directx.dxil|nativeBinaryStatus=planned|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=unknown|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=unavailable|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O3|optimizationEvidence.profile=vertex=vs_6_0, fragment=ps_6_0|validationStatus=unavailable|toolchainProvenance.tools.0.name=CrossGL-Compiler|toolchainProvenance.tools.0.role=generator|toolchainProvenance.tools.1.name=dxc|toolchainProvenance.tools.1.role=compiler|toolchainProvenance.tools.1.executable=dxc|toolchainProvenance.tools.1.executableSource=not-found|toolchainProvenance.tools.1.versionProbeStatus=unavailable"
  EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS
    "toolchainProvenance.tools=2|validationDiagnostics=0")

crossgl_add_package_verify_json_schema_test(
  NAME cglc_package_verify_json_schema_directx_graphics_storage_buffer_resources_source_package
  TARGET directx
  INPUT ${CROSSGL_DIRECTX_GRAPHICS_STORAGE_BUFFER_RESOURCE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-directx-graphics-storage-buffer-resources-package-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=true|summary.module=DirectXGraphicsStorageBufferResourceShader|summary.target=directx|summary.nativeBinaryStatus=${CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|summary.artifactCount=8|summary.debugArtifactsPresent=true|diagnosticCounts.error=0"
  EXPECTED_MANIFEST_JSON_FIELDS
    "schemaVersion=1|target=directx|module=DirectXGraphicsStorageBufferResourceShader|artifacts.backendSource=backend/directx/DirectXGraphicsStorageBufferResourceShader.graphics.hlsl|artifacts.nativeBinary=backend/directx/DirectXGraphicsStorageBufferResourceShader.dxil|artifacts.nativeBinaryStatus=${CROSSGL_DIRECTX_GRAPHICS_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/directx/DirectXGraphicsStorageBufferResourceShader.native-artifact.json|artifacts.graphicsAbi=backend/directx/DirectXGraphicsStorageBufferResourceShader.graphics-abi.json"
  EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
    "target=directx|binaryKind=directx.dxil|nativeBinaryStatus=planned|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=unknown|optimizationEvidence.policy=crossgl-to-dxc-optimization-map|optimizationEvidence.status=unavailable|optimizationEvidence.tool=dxc|optimizationEvidence.toolFlag=-O3|optimizationEvidence.profile=vertex=vs_6_0, fragment=ps_6_0|validationStatus=unavailable|toolchainProvenance.tools.0.name=CrossGL-Compiler|toolchainProvenance.tools.0.role=generator|toolchainProvenance.tools.1.name=dxc|toolchainProvenance.tools.1.role=compiler|toolchainProvenance.tools.1.executable=dxc|toolchainProvenance.tools.1.executableSource=not-found|toolchainProvenance.tools.1.versionProbeStatus=unavailable"
  EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS
    "toolchainProvenance.tools=2|validationDiagnostics=0")

crossgl_add_package_verify_json_schema_test(
  NAME cglc_package_verify_json_schema_opengl_source_package
  TARGET opengl
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-opengl-package-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=true|summary.module=StorageBufferComputeShader|summary.target=opengl|summary.artifactCount=6|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/opengl/StorageBufferComputeShader.native-artifact.json|diagnosticCounts.error=0"
  EXPECTED_MANIFEST_JSON_FIELDS
    "schemaVersion=1|target=opengl|module=StorageBufferComputeShader|targetLegalizationToolRequirements.target=opengl|targetLegalizationToolRequirements.packageMode=source-package|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=2|targetLegalizationToolRequirements.optionalNativeToolMissing=true|targetLegalizationToolRequirements.optionalNativeToolStatus=missing|artifacts.backendSource=backend/opengl/StorageBufferComputeShader.comp.glsl|artifacts.nativeBinary=backend/opengl/StorageBufferComputeShader.glsl|artifacts.nativeArtifactDescriptor=backend/opengl/StorageBufferComputeShader.native-artifact.json"
  EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS
    "targetLegalizationToolRequirements.requiredToolIds=opengl.toolchain.opengl-driver|targetLegalizationToolRequirements.missingToolIds=opengl.validation.glsl-program-validation|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.opengl.tool-requirement.required.toolchain.opengl-driver|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.opengl.tool-requirement.missing.validation.glsl-program-validation"
  EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS
    "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=2|targetLegalizationToolRequirements.toolRequirementEvidenceIds=5")

if(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR)
  set(CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS validated)
  set(CROSSGL_OPENGL_NATIVE_ARTIFACT_VALIDATION_STATUS validated)
else()
  set(CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS planned)
  set(CROSSGL_OPENGL_NATIVE_ARTIFACT_VALIDATION_STATUS unavailable)
endif()

function(crossgl_add_opengl_descriptor_array_package_verify_schema_test)
  set(one_value_args NAME INPUT OUTPUT MODULE)
  cmake_parse_arguments(CROSSGL_OPENGL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA ""
    "${one_value_args}" "" ${ARGN})
  if(NOT CROSSGL_OPENGL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_NAME)
    message(FATAL_ERROR
      "crossgl_add_opengl_descriptor_array_package_verify_schema_test requires NAME")
  endif()
  if(NOT CROSSGL_OPENGL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_INPUT)
    message(FATAL_ERROR
      "crossgl_add_opengl_descriptor_array_package_verify_schema_test requires INPUT")
  endif()
  if(NOT CROSSGL_OPENGL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_OUTPUT)
    message(FATAL_ERROR
      "crossgl_add_opengl_descriptor_array_package_verify_schema_test requires OUTPUT")
  endif()
  if(NOT CROSSGL_OPENGL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_MODULE)
    message(FATAL_ERROR
      "crossgl_add_opengl_descriptor_array_package_verify_schema_test requires MODULE")
  endif()

  set(opengl_descriptor_array_module
      "${CROSSGL_OPENGL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_MODULE}")
  crossgl_add_package_verify_json_schema_test(
    NAME ${CROSSGL_OPENGL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_NAME}
    TARGET opengl
    INPUT ${CROSSGL_OPENGL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_INPUT}
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/${CROSSGL_OPENGL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_OUTPUT}
    EXPECTED_JSON_FIELDS
      "schemaVersion=1|success=true|summary.module=${opengl_descriptor_array_module}|summary.target=opengl|summary.nativeBinaryStatus=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|summary.artifactCount=6|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/opengl/${opengl_descriptor_array_module}.native-artifact.json|summary.targetLegalizationEvidence.health=ok|summary.targetLegalizationEvidence.packageMode=source-package|summary.targetLegalizationEvidence.packageModeSource=manifest.packageArtifactRequirements|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds.0=target-legalization.v1.opengl.package-artifacts.source-package|summary.targetLegalizationEvidence.manifestToolRequirements.present=true|summary.targetLegalizationEvidence.manifestToolRequirements.target=opengl|summary.targetLegalizationEvidence.manifestToolRequirements.packageMode=source-package|summary.targetLegalizationEvidence.manifestToolRequirements.requiredToolCount=2|summary.targetLegalizationEvidence.manifestToolRequirements.missingToolCount=2|summary.targetLegalizationEvidence.manifestToolRequirements.optionalNativeToolMissing=true|summary.targetLegalizationEvidence.manifestToolRequirements.optionalNativeToolStatus=missing|summary.targetLegalizationEvidence.checks.packageArtifactRequirementEvidenceIdsPresent=true|summary.targetLegalizationEvidence.checks.manifestToolRequirementsTargetMatchesPackage=true|summary.targetLegalizationEvidence.checks.manifestToolRequirementsPackageModeMatchesRequirements=true|summary.targetLegalizationEvidence.checks.manifestToolRequirementEvidenceIdsPresent=true|summary.targetLegalizationEvidence.checks.debugMetadataToolRequirementsMatchManifest=true|diagnosticCounts.error=0"
    EXPECTED_JSON_FIELD_ONE_OF
      "summary.targetLegalizationEvidence.checks.targetExplanationToolRequirementsMatchManifest=null,true"
    EXPECTED_JSON_ARRAY_LENGTHS
      "diagnostics=0|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds=6|summary.targetLegalizationEvidence.missingEvidence=0|summary.targetLegalizationEvidence.manifestToolRequirements.requiredToolIds=2|summary.targetLegalizationEvidence.manifestToolRequirements.missingToolIds=2|summary.targetLegalizationEvidence.manifestToolRequirements.toolRequirementEvidenceIds=5"
    EXPECTED_MANIFEST_JSON_FIELDS
      "schemaVersion=1|target=opengl|module=${opengl_descriptor_array_module}|targetLegalizationToolRequirements.target=opengl|targetLegalizationToolRequirements.packageMode=source-package|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=2|targetLegalizationToolRequirements.optionalNativeToolMissing=true|targetLegalizationToolRequirements.optionalNativeToolStatus=missing|packageArtifactRequirements.target=opengl|packageArtifactRequirements.packageMode=source-package|packageArtifactRequirements.requiresNativeBinaryStatus=true|packageArtifactRequirements.allowsPlannedNativeBinary=true|packageArtifactRequirements.allowsPlannedNativeSourceEvidence=true|artifacts.backendSource=backend/opengl/${opengl_descriptor_array_module}.comp.glsl|artifacts.nativeBinary=backend/opengl/${opengl_descriptor_array_module}.glsl|artifacts.nativeBinaryStatus=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/opengl/${opengl_descriptor_array_module}.native-artifact.json|artifacts.targetExplanation=ir/target-explanation.json"
    EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS
      "targetLegalizationToolRequirements.requiredToolIds=opengl.toolchain.opengl-driver|targetLegalizationToolRequirements.requiredToolIds=opengl.validation.glsl-program-validation|targetLegalizationToolRequirements.missingToolIds=opengl.toolchain.opengl-driver|targetLegalizationToolRequirements.missingToolIds=opengl.validation.glsl-program-validation|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.opengl.tool-requirements.present|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.opengl.tool-requirement.required.toolchain.opengl-driver|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.opengl.tool-requirement.missing.validation.glsl-program-validation|packageArtifactRequirements.requiredPathArtifacts=backendSource|packageArtifactRequirements.requiredPathArtifacts=nativeBinary|packageArtifactRequirements.evidenceIds=target-legalization.v1.opengl.package-artifacts.source-package|packageArtifactRequirements.evidenceIds=target-legalization.v1.opengl.package-artifact.required.backendSource|packageArtifactRequirements.evidenceIds=target-legalization.v1.opengl.package-artifact.required.nativeBinary|packageArtifactRequirements.evidenceIds=target-legalization.v1.opengl.package-artifact.planned-native-binary.allowed"
    EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS
      "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=2|targetLegalizationToolRequirements.toolRequirementEvidenceIds=5|packageArtifactRequirements.requiredPathArtifacts=2|packageArtifactRequirements.evidenceIds=6"
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
      "target=opengl|binaryKind=opengl.source|sourcePath=backend/opengl/${opengl_descriptor_array_module}.comp.glsl|sourceHash.algorithm=sha256|nativeBinaryStatus=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|validationStatus=${CROSSGL_OPENGL_NATIVE_ARTIFACT_VALIDATION_STATUS}")
endfunction()

crossgl_add_package_verify_json_schema_test(
  NAME cglc_package_verify_json_schema_opengl_graphics_resources_source_package
  TARGET opengl
  INPUT ${CROSSGL_OPENGL_GRAPHICS_RESOURCES_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-resources-package-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=true|summary.module=OpenGLGraphicsResourcesShader|summary.target=opengl|summary.nativeBinaryStatus=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|summary.artifactCount=7|summary.debugArtifactsPresent=true|diagnosticCounts.error=0"
  EXPECTED_MANIFEST_JSON_FIELDS
    "schemaVersion=1|target=opengl|module=OpenGLGraphicsResourcesShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsResourcesShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsResourcesShader.glsl|artifacts.nativeBinaryStatus=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/opengl/OpenGLGraphicsResourcesShader.native-artifact.json|artifacts.graphicsAbi=backend/opengl/OpenGLGraphicsResourcesShader.graphics-abi.json")

crossgl_add_package_verify_json_schema_test(
  NAME cglc_package_verify_json_schema_opengl_graphics_descriptor_array_source_package
  TARGET opengl
  INPUT ${CROSSGL_OPENGL_GRAPHICS_DESCRIPTOR_ARRAY_RESOURCES_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-opengl-graphics-descriptor-array-package-verify-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=true|summary.module=OpenGLGraphicsDescriptorArrayResourcesShader|summary.target=opengl|summary.nativeBinaryStatus=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|summary.artifactCount=7|summary.debugArtifactsPresent=true|diagnosticCounts.error=0"
  EXPECTED_MANIFEST_JSON_FIELDS
    "schemaVersion=1|target=opengl|module=OpenGLGraphicsDescriptorArrayResourcesShader|artifacts.backendSource=backend/opengl/OpenGLGraphicsDescriptorArrayResourcesShader.graphics.glsl|artifacts.nativeBinary=backend/opengl/OpenGLGraphicsDescriptorArrayResourcesShader.glsl|artifacts.nativeBinaryStatus=${CROSSGL_OPENGL_SOURCE_PACKAGE_NATIVE_BINARY_STATUS}|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/opengl/OpenGLGraphicsDescriptorArrayResourcesShader.native-artifact.json|artifacts.graphicsAbi=backend/opengl/OpenGLGraphicsDescriptorArrayResourcesShader.graphics-abi.json")

crossgl_add_opengl_descriptor_array_package_verify_schema_test(
  NAME cglc_package_verify_json_schema_opengl_storage_image_descriptor_array_source_package
  INPUT ${CROSSGL_OPENGL_STORAGE_IMAGE_DESCRIPTOR_ARRAY_SHADER}
  OUTPUT test-opengl-storage-image-descriptor-array-package-verify-schema.cglb
  MODULE OpenGLStorageImageDescriptorArrayShader)

crossgl_add_opengl_descriptor_array_package_verify_schema_test(
  NAME cglc_package_verify_json_schema_opengl_storage_image_nonuniform_descriptor_array_source_package
  INPUT ${CROSSGL_OPENGL_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
  OUTPUT test-opengl-storage-image-nonuniform-descriptor-array-package-verify-schema.cglb
  MODULE OpenGLStorageImageNonUniformDescriptorArrayShader)

crossgl_add_opengl_descriptor_array_package_verify_schema_test(
  NAME cglc_package_verify_json_schema_opengl_storage_image_explicit_format_descriptor_array_source_package
  INPUT ${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
  OUTPUT test-opengl-storage-image-explicit-format-descriptor-array-package-verify-schema.cglb
  MODULE StorageImageExplicitFormatDescriptorArrayShader)

crossgl_add_opengl_descriptor_array_package_verify_schema_test(
  NAME cglc_package_verify_json_schema_opengl_storage_image_atomic_descriptor_array_source_package
  INPUT ${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
  OUTPUT test-opengl-storage-image-atomic-descriptor-array-package-verify-schema.cglb
  MODULE StorageImageAtomicDescriptorArrayShader)

if(CROSSGL_HAS_METAL_NATIVE_TOOLS)
  crossgl_add_package_verify_json_schema_test(
    NAME cglc_package_verify_json_schema_metal_native
    TARGET metal
    INPUT ${CROSSGL_SIMPLE_SHADER}
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-metal-package-verify-schema.cglb
    EXPECTED_JSON_FIELDS
      "schemaVersion=1|success=true|summary.module=SimpleShader|summary.target=metal|summary.nativeBinaryStatus=null|summary.artifactCount=8|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/metal/SimpleShader.native-artifact.json|diagnosticCounts.error=0"
    EXPECTED_MANIFEST_JSON_FIELDS
      "schemaVersion=1|target=metal|module=SimpleShader|targetLegalizationToolRequirements.target=metal|targetLegalizationToolRequirements.packageMode=native|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=0|targetLegalizationToolRequirements.optionalNativeToolMissing=false|targetLegalizationToolRequirements.optionalNativeToolStatus=not-required|artifacts.backendSource=backend/metal/SimpleShader.metal|artifacts.intermediate=backend/metal/SimpleShader.air|artifacts.nativeBinary=backend/metal/SimpleShader.metallib|artifacts.nativeArtifactDescriptor=backend/metal/SimpleShader.native-artifact.json|artifacts.graphicsAbi=backend/metal/SimpleShader.graphics-abi.json"
    EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS
      "targetLegalizationToolRequirements.requiredToolIds=metal.toolchain.xcrun-metal|targetLegalizationToolRequirements.requiredToolIds=metal.toolchain.xcrun-metallib|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.metal.tool-requirements.present"
    EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS
      "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=0|targetLegalizationToolRequirements.toolRequirementEvidenceIds=3")
  crossgl_label_optional_native_test(
    cglc_package_verify_json_schema_metal_native metal)
  crossgl_add_package_verify_json_schema_test(
    NAME cglc_package_verify_json_schema_metal_graphics_descriptor_array_native
    TARGET metal
    INPUT ${CROSSGL_METAL_GRAPHICS_DESCRIPTOR_ARRAY_SHADER}
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-metal-graphics-descriptor-array-package-verify-schema.cglb
    EXPECTED_JSON_FIELDS
      "schemaVersion=1|success=true|summary.module=MetalGraphicsDescriptorArrayShader|summary.target=metal|summary.nativeBinaryStatus=null|summary.artifactCount=8|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/metal/MetalGraphicsDescriptorArrayShader.native-artifact.json|summary.nativeArtifactDescriptor.optimizationLevel=O1|summary.nativeArtifactDescriptor.optimizationEvidence.requestedLevel=O1|summary.nativeArtifactDescriptor.optimizationEvidence.effectiveLevel=O2|summary.nativeArtifactDescriptor.optimizationEvidence.policy=metal-conservative-native-package-v1|summary.nativeArtifactDescriptor.optimizationEvidence.status=applied|summary.nativeArtifactDescriptor.optimizationEvidence.tool=xcrun metal|summary.nativeArtifactDescriptor.optimizationEvidence.toolFlag=-O2|summary.targetLegalizationEvidence.health=ok|summary.targetLegalizationEvidence.packageMode=native|summary.targetLegalizationEvidence.packageModeSource=manifest.packageArtifactRequirements|diagnosticCounts.error=0"
    EXPECTED_JSON_ARRAY_LENGTHS
      "diagnostics=0|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds=4|summary.targetLegalizationEvidence.missingEvidence=0"
    EXPECTED_MANIFEST_JSON_FIELDS
      "schemaVersion=1|target=metal|module=MetalGraphicsDescriptorArrayShader|targetLegalizationToolRequirements.target=metal|targetLegalizationToolRequirements.packageMode=native|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=0|targetLegalizationToolRequirements.optionalNativeToolMissing=false|targetLegalizationToolRequirements.optionalNativeToolStatus=not-required|packageArtifactRequirements.target=metal|packageArtifactRequirements.packageMode=native|packageArtifactRequirements.requiresNativeBinaryStatus=false|packageArtifactRequirements.allowsPlannedNativeBinary=false|packageArtifactRequirements.allowsPlannedNativeSourceEvidence=false|artifacts.backendSource=backend/metal/MetalGraphicsDescriptorArrayShader.metal|artifacts.intermediate=backend/metal/MetalGraphicsDescriptorArrayShader.air|artifacts.nativeBinary=backend/metal/MetalGraphicsDescriptorArrayShader.metallib|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/metal/MetalGraphicsDescriptorArrayShader.native-artifact.json|artifacts.targetExplanation=ir/target-explanation.json|artifacts.graphicsAbi=backend/metal/MetalGraphicsDescriptorArrayShader.graphics-abi.json"
    EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS
      "targetLegalizationToolRequirements.requiredToolIds=metal.toolchain.xcrun-metal|targetLegalizationToolRequirements.requiredToolIds=metal.toolchain.xcrun-metallib|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.metal.tool-requirements.present|packageArtifactRequirements.requiredPathArtifacts=backendSource|packageArtifactRequirements.requiredPathArtifacts=intermediate|packageArtifactRequirements.requiredPathArtifacts=nativeBinary|packageArtifactRequirements.evidenceIds=target-legalization.v1.metal.package-artifacts.native"
    EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS
      "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=0|targetLegalizationToolRequirements.toolRequirementEvidenceIds=3|packageArtifactRequirements.requiredPathArtifacts=3|packageArtifactRequirements.evidenceIds=4"
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
      "target=metal|binaryKind=metal.metallib|sourcePath=backend/metal/MetalGraphicsDescriptorArrayShader.metal|artifactPath=backend/metal/MetalGraphicsDescriptorArrayShader.metallib|sourceHash.algorithm=sha256|artifactHash.algorithm=sha256|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=O2|optimizationEvidence.policy=metal-conservative-native-package-v1|optimizationEvidence.status=applied|optimizationEvidence.tool=xcrun metal|optimizationEvidence.toolFlag=-O2|optimizationEvidence.debugInfo=false|optimizationEvidence.profile=release|optimizationEvidence.flags.0=-O2|validationStatus=not-run"
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS
      "toolchainProvenance.tools=3|validationDiagnostics=0")
  crossgl_label_optional_native_test(
    cglc_package_verify_json_schema_metal_graphics_descriptor_array_native metal)

  function(crossgl_add_metal_native_descriptor_array_package_verify_schema_test)
    set(one_value_args NAME INPUT OUTPUT MODULE)
    cmake_parse_arguments(CROSSGL_METAL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA ""
      "${one_value_args}" "" ${ARGN})
    if(NOT CROSSGL_METAL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_NAME)
      message(FATAL_ERROR
        "crossgl_add_metal_native_descriptor_array_package_verify_schema_test requires NAME")
    endif()
    if(NOT CROSSGL_METAL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_INPUT)
      message(FATAL_ERROR
        "crossgl_add_metal_native_descriptor_array_package_verify_schema_test requires INPUT")
    endif()
    if(NOT CROSSGL_METAL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_OUTPUT)
      message(FATAL_ERROR
        "crossgl_add_metal_native_descriptor_array_package_verify_schema_test requires OUTPUT")
    endif()
    if(NOT CROSSGL_METAL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_MODULE)
      message(FATAL_ERROR
        "crossgl_add_metal_native_descriptor_array_package_verify_schema_test requires MODULE")
    endif()

    set(metal_descriptor_array_module
        "${CROSSGL_METAL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_MODULE}")
    crossgl_add_package_verify_json_schema_test(
      NAME ${CROSSGL_METAL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_NAME}
      TARGET metal
      INPUT ${CROSSGL_METAL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_INPUT}
      OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/${CROSSGL_METAL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_OUTPUT}
      EXPECTED_JSON_FIELDS
        "schemaVersion=1|success=true|summary.module=${metal_descriptor_array_module}|summary.target=metal|summary.nativeBinaryStatus=null|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/metal/${metal_descriptor_array_module}.native-artifact.json|summary.nativeArtifactDescriptor.optimizationLevel=O1|summary.nativeArtifactDescriptor.optimizationEvidence.requestedLevel=O1|summary.nativeArtifactDescriptor.optimizationEvidence.effectiveLevel=O2|summary.nativeArtifactDescriptor.optimizationEvidence.policy=metal-conservative-native-package-v1|summary.nativeArtifactDescriptor.optimizationEvidence.status=applied|summary.nativeArtifactDescriptor.optimizationEvidence.tool=xcrun metal|summary.nativeArtifactDescriptor.optimizationEvidence.toolFlag=-O2|summary.targetLegalizationEvidence.health=ok|summary.targetLegalizationEvidence.packageMode=native|summary.targetLegalizationEvidence.packageModeSource=manifest.packageArtifactRequirements|diagnosticCounts.error=0"
      EXPECTED_JSON_ARRAY_LENGTHS
        "diagnostics=0|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds=4|summary.targetLegalizationEvidence.missingEvidence=0"
      EXPECTED_MANIFEST_JSON_FIELDS
        "schemaVersion=1|target=metal|module=${metal_descriptor_array_module}|targetLegalizationToolRequirements.target=metal|targetLegalizationToolRequirements.packageMode=native|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=0|targetLegalizationToolRequirements.optionalNativeToolMissing=false|targetLegalizationToolRequirements.optionalNativeToolStatus=not-required|packageArtifactRequirements.target=metal|packageArtifactRequirements.packageMode=native|packageArtifactRequirements.requiresNativeBinaryStatus=false|packageArtifactRequirements.allowsPlannedNativeBinary=false|packageArtifactRequirements.allowsPlannedNativeSourceEvidence=false|artifacts.backendSource=backend/metal/${metal_descriptor_array_module}.metal|artifacts.intermediate=backend/metal/${metal_descriptor_array_module}.air|artifacts.nativeBinary=backend/metal/${metal_descriptor_array_module}.metallib|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/metal/${metal_descriptor_array_module}.native-artifact.json|artifacts.targetExplanation=ir/target-explanation.json"
      EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS
        "targetLegalizationToolRequirements.requiredToolIds=metal.toolchain.xcrun-metal|targetLegalizationToolRequirements.requiredToolIds=metal.toolchain.xcrun-metallib|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.metal.tool-requirements.present|packageArtifactRequirements.requiredPathArtifacts=backendSource|packageArtifactRequirements.requiredPathArtifacts=intermediate|packageArtifactRequirements.requiredPathArtifacts=nativeBinary|packageArtifactRequirements.evidenceIds=target-legalization.v1.metal.package-artifacts.native"
      EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS
        "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=0|targetLegalizationToolRequirements.toolRequirementEvidenceIds=3|packageArtifactRequirements.requiredPathArtifacts=3|packageArtifactRequirements.evidenceIds=4"
      EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
        "target=metal|binaryKind=metal.metallib|sourcePath=backend/metal/${metal_descriptor_array_module}.metal|artifactPath=backend/metal/${metal_descriptor_array_module}.metallib|sourceHash.algorithm=sha256|artifactHash.algorithm=sha256|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=O2|optimizationEvidence.policy=metal-conservative-native-package-v1|optimizationEvidence.status=applied|optimizationEvidence.tool=xcrun metal|optimizationEvidence.toolFlag=-O2|optimizationEvidence.debugInfo=false|optimizationEvidence.profile=release|optimizationEvidence.flags.0=-O2|validationStatus=not-run"
      EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS
        "toolchainProvenance.tools=3|validationDiagnostics=0")
    crossgl_label_optional_native_test(
      ${CROSSGL_METAL_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_NAME} metal)
  endfunction()

  crossgl_add_metal_native_descriptor_array_package_verify_schema_test(
    NAME cglc_package_verify_json_schema_metal_storage_image_explicit_format_descriptor_array_native
    INPUT ${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
    OUTPUT test-metal-storage-image-explicit-format-descriptor-array-package-verify-schema.cglb
    MODULE StorageImageExplicitFormatDescriptorArrayShader)

  crossgl_add_metal_native_descriptor_array_package_verify_schema_test(
    NAME cglc_package_verify_json_schema_metal_storage_image_atomic_descriptor_array_native
    INPUT ${CROSSGL_METAL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
    OUTPUT test-metal-storage-image-atomic-descriptor-array-package-verify-schema.cglb
    MODULE MetalStorageImageAtomicDescriptorArrayShader)

  crossgl_add_metal_native_descriptor_array_package_verify_schema_test(
    NAME cglc_package_verify_json_schema_metal_storage_image_2d_nonuniform_descriptor_array_native
    INPUT ${CROSSGL_METAL_STORAGE_IMAGE_2D_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    OUTPUT test-metal-storage-image-2d-nonuniform-descriptor-array-package-verify-schema.cglb
    MODULE MetalStorageImage2DNonUniformDescriptorArrayShader)

  crossgl_add_metal_native_descriptor_array_package_verify_schema_test(
    NAME cglc_package_verify_json_schema_metal_storage_image_2d_array_nonuniform_descriptor_array_native
    INPUT ${CROSSGL_METAL_STORAGE_IMAGE_2D_ARRAY_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    OUTPUT test-metal-storage-image-2d-array-nonuniform-descriptor-array-package-verify-schema.cglb
    MODULE MetalStorageImage2DArrayNonUniformDescriptorArrayShader)
else()
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_metal_native_unavailable
    TARGET metal
    REQUIRED_VARS CROSSGL_XCRUN CROSSGL_METAL CROSSGL_METALLIB)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_metal_graphics_descriptor_array_native_unavailable
    TARGET metal
    REQUIRED_VARS CROSSGL_XCRUN CROSSGL_METAL CROSSGL_METALLIB)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_metal_storage_image_explicit_format_descriptor_array_native_unavailable
    TARGET metal
    REQUIRED_VARS CROSSGL_XCRUN CROSSGL_METAL CROSSGL_METALLIB)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_metal_storage_image_atomic_descriptor_array_native_unavailable
    TARGET metal
    REQUIRED_VARS CROSSGL_XCRUN CROSSGL_METAL CROSSGL_METALLIB)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_metal_storage_image_2d_nonuniform_descriptor_array_native_unavailable
    TARGET metal
    REQUIRED_VARS CROSSGL_XCRUN CROSSGL_METAL CROSSGL_METALLIB)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_metal_storage_image_2d_array_nonuniform_descriptor_array_native_unavailable
    TARGET metal
    REQUIRED_VARS CROSSGL_XCRUN CROSSGL_METAL CROSSGL_METALLIB)
endif()

if(CROSSGL_HAS_VULKAN_NATIVE_TOOLS)
  crossgl_add_package_verify_json_schema_test(
    NAME cglc_package_verify_json_schema_vulkan_native
    TARGET vulkan
    INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-package-verify-schema.cglb
    EXPECTED_JSON_FIELDS
      "schemaVersion=1|success=true|summary.module=StorageBufferComputeShader|summary.target=vulkan|summary.nativeBinaryStatus=null|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/vulkan/StorageBufferComputeShader.native-artifact.json|summary.vulkanNativeProfile.applicable=true|summary.vulkanNativeProfile.nativeProfileArtifactPresent=true|summary.vulkanNativeProfile.nativeProfileExists=true|summary.vulkanNativeProfile.health=ok|summary.vulkanNativeProfile.api=vulkan|summary.vulkanNativeProfile.profileName=vulkan-prototype|summary.vulkanNativeProfile.nativeBinary=backend/vulkan/StorageBufferComputeShader.spv|summary.vulkanNativeProfile.backendAssembly=backend/vulkan/StorageBufferComputeShader.spvasm|summary.vulkanNativeProfile.checks.targetMatchesPackage=true|summary.vulkanNativeProfile.checks.moduleMatchesPackage=true|summary.vulkanNativeProfile.checks.nativeBinaryMatchesManifest=true|summary.vulkanNativeProfile.checks.backendAssemblyMatchesManifest=true|summary.vulkanNativeProfile.checks.spirvProfilePresent=true|diagnosticCounts.error=0"
    EXPECTED_MANIFEST_JSON_FIELDS
      "schemaVersion=1|target=vulkan|module=StorageBufferComputeShader|targetLegalizationToolRequirements.target=vulkan|targetLegalizationToolRequirements.packageMode=native|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=0|targetLegalizationToolRequirements.optionalNativeToolMissing=false|targetLegalizationToolRequirements.optionalNativeToolStatus=not-required|artifacts.backendAssembly=backend/vulkan/StorageBufferComputeShader.spvasm|artifacts.nativeBinary=backend/vulkan/StorageBufferComputeShader.spv|artifacts.nativeProfile=backend/vulkan/StorageBufferComputeShader.profile.json|artifacts.nativeArtifactDescriptor=backend/vulkan/StorageBufferComputeShader.native-artifact.json"
    EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS
      "targetLegalizationToolRequirements.requiredToolIds=vulkan.toolchain.spirv-as|targetLegalizationToolRequirements.requiredToolIds=vulkan.validation.spirv-val|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.vulkan.tool-requirements.present"
    EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS
      "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=0|targetLegalizationToolRequirements.toolRequirementEvidenceIds=3")
  crossgl_label_optional_native_test(
    cglc_package_verify_json_schema_vulkan_native vulkan)

  set(vulkan_native_profile_drift_script
      "${CMAKE_CURRENT_BINARY_DIR}/cglc-package-verify-vulkan-native-profile-drift.cmake")
  file(WRITE "${vulkan_native_profile_drift_script}" [=[
if(NOT DEFINED CGLC)
  message(FATAL_ERROR "CGLC is required")
endif()
if(NOT DEFINED INPUT)
  message(FATAL_ERROR "INPUT is required")
endif()
if(NOT DEFINED OUTPUT)
  message(FATAL_ERROR "OUTPUT is required")
endif()
if(NOT DEFINED JSON_SCHEMA)
  message(FATAL_ERROR "JSON_SCHEMA is required")
endif()
if(NOT DEFINED JSON_SCHEMA_VALIDATOR)
  message(FATAL_ERROR "JSON_SCHEMA_VALIDATOR is required")
endif()
if(NOT DEFINED PYTHON3_EXECUTABLE)
  message(FATAL_ERROR "PYTHON3_EXECUTABLE is required")
endif()

file(REMOVE_RECURSE "${OUTPUT}")
execute_process(
  COMMAND "${CGLC}" build "${INPUT}" --target vulkan --output "${OUTPUT}" --debug-ir
  RESULT_VARIABLE build_result
  OUTPUT_VARIABLE build_stdout
  ERROR_VARIABLE build_stderr)
if(NOT build_result EQUAL 0)
  message(FATAL_ERROR "vulkan package build failed: ${build_stderr}${build_stdout}")
endif()

file(READ "${OUTPUT}/manifest.json" manifest)
string(JSON native_profile ERROR_VARIABLE profile_error GET
       "${manifest}" artifacts nativeProfile)
if(NOT profile_error STREQUAL "NOTFOUND")
  message(FATAL_ERROR "expected manifest artifacts.nativeProfile, got: ${profile_error}")
endif()
set(profile_path "${OUTPUT}/${native_profile}")
file(READ "${profile_path}" profile)
string(REPLACE
       "\"module\": \"StorageBufferComputeShader\""
       "\"module\": \"TamperedStorageBufferComputeShader\""
       profile "${profile}")
file(WRITE "${profile_path}" "${profile}")

execute_process(
  COMMAND "${CGLC}" package verify "${OUTPUT}" --json --source "${INPUT}"
  RESULT_VARIABLE verify_result
  OUTPUT_VARIABLE verify_stdout
  ERROR_VARIABLE verify_stderr)
if(verify_result EQUAL 0)
  message(FATAL_ERROR "expected package verify --json to reject drifted nativeProfile")
endif()

string(JSON success GET "${verify_stdout}" success)
if(NOT success STREQUAL "OFF")
  message(FATAL_ERROR "expected success=false, got: ${verify_stdout}")
endif()
string(JSON error_count GET "${verify_stdout}" diagnosticCounts error)
if(NOT error_count STREQUAL "1")
  message(FATAL_ERROR "expected one error, got: ${verify_stdout}")
endif()
string(JSON diagnostic_code GET "${verify_stdout}" diagnostics 0 code)
if(NOT diagnostic_code STREQUAL "package.verify.vulkan-native-profile-drift")
  message(FATAL_ERROR "unexpected diagnostic code: ${verify_stdout}")
endif()
string(JSON profile_health GET "${verify_stdout}" summary vulkanNativeProfile health)
if(NOT profile_health STREQUAL "drift")
  message(FATAL_ERROR "expected summary.vulkanNativeProfile.health=drift, got: ${verify_stdout}")
endif()
string(JSON module_check GET
       "${verify_stdout}" summary vulkanNativeProfile checks moduleMatchesPackage)
if(NOT module_check STREQUAL "OFF")
  message(FATAL_ERROR "expected moduleMatchesPackage=false, got: ${verify_stdout}")
endif()

string(RANDOM LENGTH 8 ALPHABET 0123456789abcdef schema_nonce)
set(instance_path
    "${CMAKE_CURRENT_BINARY_DIR}/crossgl-vulkan-native-profile-drift-${schema_nonce}.json")
file(WRITE "${instance_path}" "${verify_stdout}")
execute_process(
  COMMAND "${PYTHON3_EXECUTABLE}" "${JSON_SCHEMA_VALIDATOR}"
          --schema "${JSON_SCHEMA}"
          --instance "${instance_path}"
  RESULT_VARIABLE schema_result
  OUTPUT_VARIABLE schema_stdout
  ERROR_VARIABLE schema_stderr)
if(NOT schema_result EQUAL 0)
  message(FATAL_ERROR "JSON schema validation failed: ${schema_stderr}${schema_stdout}")
endif()
]=])
  add_test(NAME cglc_package_verify_json_schema_vulkan_native_profile_drift_failure
    COMMAND "${CMAKE_COMMAND}"
      "-DCGLC=$<TARGET_FILE:cglc>"
      "-DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}"
      "-DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-native-profile-drift-package-verify-schema.cglb"
      "-DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-verify-v1.schema.json"
      "-DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py"
      "-DPYTHON3_EXECUTABLE=${CROSSGL_PYTHON3}"
      -P "${vulkan_native_profile_drift_script}")
  crossgl_label_optional_native_test(
    cglc_package_verify_json_schema_vulkan_native_profile_drift_failure vulkan)

  function(crossgl_add_vulkan_native_descriptor_array_package_verify_schema_test)
    set(one_value_args NAME INPUT OUTPUT MODULE)
    cmake_parse_arguments(CROSSGL_VULKAN_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA ""
      "${one_value_args}" "" ${ARGN})
    if(NOT CROSSGL_VULKAN_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_NAME)
      message(FATAL_ERROR
        "crossgl_add_vulkan_native_descriptor_array_package_verify_schema_test requires NAME")
    endif()
    if(NOT CROSSGL_VULKAN_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_INPUT)
      message(FATAL_ERROR
        "crossgl_add_vulkan_native_descriptor_array_package_verify_schema_test requires INPUT")
    endif()
    if(NOT CROSSGL_VULKAN_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_OUTPUT)
      message(FATAL_ERROR
        "crossgl_add_vulkan_native_descriptor_array_package_verify_schema_test requires OUTPUT")
    endif()
    if(NOT CROSSGL_VULKAN_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_MODULE)
      message(FATAL_ERROR
        "crossgl_add_vulkan_native_descriptor_array_package_verify_schema_test requires MODULE")
    endif()

    set(vulkan_descriptor_array_module
        "${CROSSGL_VULKAN_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_MODULE}")
    crossgl_add_package_verify_json_schema_test(
      NAME ${CROSSGL_VULKAN_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_NAME}
      TARGET vulkan
      INPUT ${CROSSGL_VULKAN_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_INPUT}
      OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/${CROSSGL_VULKAN_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_OUTPUT}
      EXPECTED_JSON_FIELDS
        "schemaVersion=1|success=true|summary.module=${vulkan_descriptor_array_module}|summary.target=vulkan|summary.nativeBinaryStatus=null|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/vulkan/${vulkan_descriptor_array_module}.native-artifact.json|summary.nativeArtifactDescriptor.optimizationLevel=O1|summary.nativeArtifactDescriptor.optimizationEvidence.requestedLevel=O1|summary.nativeArtifactDescriptor.optimizationEvidence.effectiveLevel=none|summary.nativeArtifactDescriptor.optimizationEvidence.policy=disabled-by-opt-level|summary.nativeArtifactDescriptor.optimizationEvidence.status=skipped-disabled|summary.nativeArtifactDescriptor.optimizationEvidence.tool=spirv-opt|summary.nativeArtifactDescriptor.optimizationEvidence.evidenceSource.kind=native-profile|summary.nativeArtifactDescriptor.optimizationEvidence.evidenceSource.path=backend/vulkan/${vulkan_descriptor_array_module}.profile.json|summary.targetLegalizationEvidence.health=ok|summary.targetLegalizationEvidence.packageMode=native|summary.targetLegalizationEvidence.packageModeSource=manifest.packageArtifactRequirements|diagnosticCounts.error=0"
      EXPECTED_JSON_ARRAY_LENGTHS
        "diagnostics=0|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds=3|summary.targetLegalizationEvidence.missingEvidence=0"
      EXPECTED_MANIFEST_JSON_FIELDS
        "schemaVersion=1|target=vulkan|module=${vulkan_descriptor_array_module}|targetLegalizationToolRequirements.target=vulkan|targetLegalizationToolRequirements.packageMode=native|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=0|targetLegalizationToolRequirements.optionalNativeToolMissing=false|targetLegalizationToolRequirements.optionalNativeToolStatus=not-required|packageArtifactRequirements.target=vulkan|packageArtifactRequirements.packageMode=native|packageArtifactRequirements.requiresNativeBinaryStatus=false|packageArtifactRequirements.allowsPlannedNativeBinary=false|packageArtifactRequirements.allowsPlannedNativeSourceEvidence=false|artifacts.backendAssembly=backend/vulkan/${vulkan_descriptor_array_module}.spvasm|artifacts.nativeBinary=backend/vulkan/${vulkan_descriptor_array_module}.spv|artifacts.nativeProfile=backend/vulkan/${vulkan_descriptor_array_module}.profile.json|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/vulkan/${vulkan_descriptor_array_module}.native-artifact.json|artifacts.targetExplanation=ir/target-explanation.json"
      EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS
        "targetLegalizationToolRequirements.requiredToolIds=vulkan.toolchain.spirv-as|targetLegalizationToolRequirements.requiredToolIds=vulkan.validation.spirv-val|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.vulkan.tool-requirements.present|packageArtifactRequirements.requiredPathArtifacts=backendAssembly|packageArtifactRequirements.requiredPathArtifacts=nativeBinary|packageArtifactRequirements.evidenceIds=target-legalization.v1.vulkan.package-artifacts.native"
      EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS
        "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=0|targetLegalizationToolRequirements.toolRequirementEvidenceIds=3|packageArtifactRequirements.requiredPathArtifacts=2|packageArtifactRequirements.evidenceIds=3"
      EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
        "target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/${vulkan_descriptor_array_module}.spvasm|artifactPath=backend/vulkan/${vulkan_descriptor_array_module}.spv|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=none|optimizationEvidence.policy=disabled-by-opt-level|optimizationEvidence.status=skipped-disabled|optimizationEvidence.tool=spirv-opt|optimizationEvidence.evidenceSource.kind=native-profile|optimizationEvidence.evidenceSource.path=backend/vulkan/${vulkan_descriptor_array_module}.profile.json|validationStatus=validated|toolchainProvenance.tools.1.name=spirv-as|toolchainProvenance.tools.1.role=assembler|toolchainProvenance.tools.2.name=spirv-val|toolchainProvenance.tools.2.role=validator"
      EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS
        "toolchainProvenance.tools=3|validationDiagnostics=0")
    crossgl_label_optional_native_test(
      ${CROSSGL_VULKAN_DESCRIPTOR_ARRAY_PACKAGE_SCHEMA_NAME} vulkan)
  endfunction()

  crossgl_add_vulkan_native_descriptor_array_package_verify_schema_test(
    NAME cglc_package_verify_json_schema_vulkan_runtime_texture_descriptor_array_native
    INPUT ${CROSSGL_VULKAN_RUNTIME_TEXTURE_DESCRIPTOR_ARRAY_POLICY_SHADER}
    OUTPUT test-vulkan-runtime-texture-descriptor-array-package-verify-schema.cglb
    MODULE VulkanRuntimeTextureDescriptorArrayPolicyShader)

  crossgl_add_vulkan_native_descriptor_array_package_verify_schema_test(
    NAME cglc_package_verify_json_schema_vulkan_runtime_sampler_descriptor_array_native
    INPUT ${CROSSGL_VULKAN_RUNTIME_SAMPLER_DESCRIPTOR_ARRAY_POLICY_SHADER}
    OUTPUT test-vulkan-runtime-sampler-descriptor-array-package-verify-schema.cglb
    MODULE VulkanRuntimeSamplerDescriptorArrayPolicyShader)

  crossgl_add_vulkan_native_descriptor_array_package_verify_schema_test(
    NAME cglc_package_verify_json_schema_vulkan_runtime_shadow_descriptor_array_native
    INPUT ${CROSSGL_VULKAN_RUNTIME_SHADOW_DESCRIPTOR_ARRAY_SHADER}
    OUTPUT test-vulkan-runtime-shadow-descriptor-array-package-verify-schema.cglb
    MODULE VulkanRuntimeShadowDescriptorArrayShader)

  crossgl_add_package_verify_json_schema_test(
    NAME cglc_package_verify_json_schema_vulkan_runtime_texture_sampler_descriptor_array_native
    TARGET vulkan
    INPUT ${CROSSGL_VULKAN_RUNTIME_TEXTURE_SAMPLER_DESCRIPTOR_ARRAY_POLICY_SHADER}
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-texture-sampler-descriptor-array-package-verify-schema.cglb
    EXPECTED_JSON_FIELDS
      "schemaVersion=1|success=true|summary.module=VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader|summary.target=vulkan|summary.nativeBinaryStatus=null|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/vulkan/VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader.native-artifact.json|summary.nativeArtifactDescriptor.optimizationLevel=O1|summary.nativeArtifactDescriptor.optimizationEvidence.requestedLevel=O1|summary.nativeArtifactDescriptor.optimizationEvidence.effectiveLevel=none|summary.nativeArtifactDescriptor.optimizationEvidence.policy=disabled-by-opt-level|summary.nativeArtifactDescriptor.optimizationEvidence.status=skipped-disabled|summary.nativeArtifactDescriptor.optimizationEvidence.tool=spirv-opt|summary.nativeArtifactDescriptor.optimizationEvidence.evidenceSource.kind=native-profile|summary.nativeArtifactDescriptor.optimizationEvidence.evidenceSource.path=backend/vulkan/VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader.profile.json|summary.targetLegalizationEvidence.health=ok|summary.targetLegalizationEvidence.packageMode=native|summary.targetLegalizationEvidence.packageModeSource=manifest.packageArtifactRequirements|diagnosticCounts.error=0"
    EXPECTED_JSON_ARRAY_LENGTHS
      "diagnostics=0|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds=3|summary.targetLegalizationEvidence.missingEvidence=0"
    EXPECTED_MANIFEST_JSON_FIELDS
      "schemaVersion=1|target=vulkan|module=VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader|targetLegalizationToolRequirements.target=vulkan|targetLegalizationToolRequirements.packageMode=native|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=0|targetLegalizationToolRequirements.optionalNativeToolMissing=false|targetLegalizationToolRequirements.optionalNativeToolStatus=not-required|packageArtifactRequirements.target=vulkan|packageArtifactRequirements.packageMode=native|packageArtifactRequirements.requiresNativeBinaryStatus=false|packageArtifactRequirements.allowsPlannedNativeBinary=false|packageArtifactRequirements.allowsPlannedNativeSourceEvidence=false|artifacts.backendAssembly=backend/vulkan/VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader.spv|artifacts.nativeProfile=backend/vulkan/VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader.profile.json|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/vulkan/VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader.native-artifact.json|artifacts.targetExplanation=ir/target-explanation.json"
    EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS
      "targetLegalizationToolRequirements.requiredToolIds=vulkan.toolchain.spirv-as|targetLegalizationToolRequirements.requiredToolIds=vulkan.validation.spirv-val|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.vulkan.tool-requirements.present|packageArtifactRequirements.requiredPathArtifacts=backendAssembly|packageArtifactRequirements.requiredPathArtifacts=nativeBinary|packageArtifactRequirements.evidenceIds=target-legalization.v1.vulkan.package-artifacts.native"
    EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS
      "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=0|targetLegalizationToolRequirements.toolRequirementEvidenceIds=3|packageArtifactRequirements.requiredPathArtifacts=2|packageArtifactRequirements.evidenceIds=3"
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
      "target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader.spvasm|artifactPath=backend/vulkan/VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader.spv|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=none|optimizationEvidence.policy=disabled-by-opt-level|optimizationEvidence.status=skipped-disabled|optimizationEvidence.tool=spirv-opt|optimizationEvidence.evidenceSource.kind=native-profile|optimizationEvidence.evidenceSource.path=backend/vulkan/VulkanRuntimeTextureSamplerDescriptorArrayPolicyShader.profile.json|validationStatus=validated|toolchainProvenance.tools.1.name=spirv-as|toolchainProvenance.tools.1.role=assembler|toolchainProvenance.tools.2.name=spirv-val|toolchainProvenance.tools.2.role=validator"
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS
      "toolchainProvenance.tools=3|validationDiagnostics=0")
  crossgl_label_optional_native_test(
    cglc_package_verify_json_schema_vulkan_runtime_texture_sampler_descriptor_array_native vulkan)
  crossgl_add_package_verify_json_schema_test(
    NAME cglc_package_verify_json_schema_vulkan_runtime_texture_sampler_nonuniform_descriptor_array_native
    TARGET vulkan
    INPUT ${CROSSGL_VULKAN_RUNTIME_TEXTURE_SAMPLER_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-runtime-texture-sampler-nonuniform-descriptor-array-package-verify-schema.cglb
    EXPECTED_JSON_FIELDS
      "schemaVersion=1|success=true|summary.module=VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader|summary.target=vulkan|summary.nativeBinaryStatus=null|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/vulkan/VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader.native-artifact.json|summary.nativeArtifactDescriptor.optimizationLevel=O1|summary.nativeArtifactDescriptor.optimizationEvidence.requestedLevel=O1|summary.nativeArtifactDescriptor.optimizationEvidence.effectiveLevel=none|summary.nativeArtifactDescriptor.optimizationEvidence.policy=disabled-by-opt-level|summary.nativeArtifactDescriptor.optimizationEvidence.status=skipped-disabled|summary.nativeArtifactDescriptor.optimizationEvidence.tool=spirv-opt|summary.nativeArtifactDescriptor.optimizationEvidence.evidenceSource.kind=native-profile|summary.nativeArtifactDescriptor.optimizationEvidence.evidenceSource.path=backend/vulkan/VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader.profile.json|summary.targetLegalizationEvidence.health=ok|summary.targetLegalizationEvidence.packageMode=native|summary.targetLegalizationEvidence.packageModeSource=manifest.packageArtifactRequirements|diagnosticCounts.error=0"
    EXPECTED_JSON_ARRAY_LENGTHS
      "diagnostics=0|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds=3|summary.targetLegalizationEvidence.missingEvidence=0"
    EXPECTED_MANIFEST_JSON_FIELDS
      "schemaVersion=1|target=vulkan|module=VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader|targetLegalizationToolRequirements.target=vulkan|targetLegalizationToolRequirements.packageMode=native|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=0|targetLegalizationToolRequirements.optionalNativeToolMissing=false|targetLegalizationToolRequirements.optionalNativeToolStatus=not-required|packageArtifactRequirements.target=vulkan|packageArtifactRequirements.packageMode=native|packageArtifactRequirements.requiresNativeBinaryStatus=false|packageArtifactRequirements.allowsPlannedNativeBinary=false|packageArtifactRequirements.allowsPlannedNativeSourceEvidence=false|artifacts.backendAssembly=backend/vulkan/VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader.spv|artifacts.nativeProfile=backend/vulkan/VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader.profile.json|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/vulkan/VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader.native-artifact.json|artifacts.targetExplanation=ir/target-explanation.json"
    EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS
      "targetLegalizationToolRequirements.requiredToolIds=vulkan.toolchain.spirv-as|targetLegalizationToolRequirements.requiredToolIds=vulkan.validation.spirv-val|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.vulkan.tool-requirements.present|packageArtifactRequirements.requiredPathArtifacts=backendAssembly|packageArtifactRequirements.requiredPathArtifacts=nativeBinary|packageArtifactRequirements.evidenceIds=target-legalization.v1.vulkan.package-artifacts.native"
    EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS
      "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=0|targetLegalizationToolRequirements.toolRequirementEvidenceIds=3|packageArtifactRequirements.requiredPathArtifacts=2|packageArtifactRequirements.evidenceIds=3"
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
      "target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader.spvasm|artifactPath=backend/vulkan/VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader.spv|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=none|optimizationEvidence.policy=disabled-by-opt-level|optimizationEvidence.status=skipped-disabled|optimizationEvidence.tool=spirv-opt|optimizationEvidence.evidenceSource.kind=native-profile|optimizationEvidence.evidenceSource.path=backend/vulkan/VulkanRuntimeTextureSamplerNonUniformDescriptorArrayShader.profile.json|validationStatus=validated|toolchainProvenance.tools.1.name=spirv-as|toolchainProvenance.tools.1.role=assembler|toolchainProvenance.tools.2.name=spirv-val|toolchainProvenance.tools.2.role=validator"
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS
      "toolchainProvenance.tools=3|validationDiagnostics=0")
  crossgl_label_optional_native_test(
    cglc_package_verify_json_schema_vulkan_runtime_texture_sampler_nonuniform_descriptor_array_native vulkan)

  crossgl_add_vulkan_native_descriptor_array_package_verify_schema_test(
    NAME cglc_package_verify_json_schema_vulkan_storage_image_explicit_format_descriptor_array_native
    INPUT ${CROSSGL_STORAGE_IMAGE_EXPLICIT_FORMAT_DESCRIPTOR_ARRAY_SHADER}
    OUTPUT test-vulkan-storage-image-explicit-format-descriptor-array-package-verify-schema.cglb
    MODULE StorageImageExplicitFormatDescriptorArrayShader)

  crossgl_add_vulkan_native_descriptor_array_package_verify_schema_test(
    NAME cglc_package_verify_json_schema_vulkan_storage_image_atomic_descriptor_array_native
    INPUT ${CROSSGL_STORAGE_IMAGE_ATOMIC_DESCRIPTOR_ARRAY_SHADER}
    OUTPUT test-vulkan-storage-image-atomic-descriptor-array-package-verify-schema.cglb
    MODULE StorageImageAtomicDescriptorArrayShader)

  crossgl_add_package_verify_json_schema_test(
    NAME cglc_package_verify_json_schema_vulkan_storage_image_nonuniform_descriptor_array_native
    TARGET vulkan
    INPUT ${CROSSGL_VULKAN_STORAGE_IMAGE_NONUNIFORM_DESCRIPTOR_ARRAY_SHADER}
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/test-vulkan-storage-image-nonuniform-descriptor-array-package-verify-schema.cglb
    EXPECTED_JSON_FIELDS
      "schemaVersion=1|success=true|summary.module=VulkanStorageImageNonUniformDescriptorArrayShader|summary.target=vulkan|summary.nativeBinaryStatus=null|summary.artifactCount=7|summary.debugArtifactsPresent=true|summary.nativeArtifactDescriptor.artifactPresent=true|summary.nativeArtifactDescriptor.descriptorExists=true|summary.nativeArtifactDescriptor.health=ok|summary.nativeArtifactDescriptor.path=backend/vulkan/VulkanStorageImageNonUniformDescriptorArrayShader.native-artifact.json|summary.nativeArtifactDescriptor.optimizationLevel=O1|summary.nativeArtifactDescriptor.optimizationEvidence.requestedLevel=O1|summary.nativeArtifactDescriptor.optimizationEvidence.effectiveLevel=none|summary.nativeArtifactDescriptor.optimizationEvidence.policy=disabled-by-opt-level|summary.nativeArtifactDescriptor.optimizationEvidence.status=skipped-disabled|summary.nativeArtifactDescriptor.optimizationEvidence.tool=spirv-opt|summary.nativeArtifactDescriptor.optimizationEvidence.evidenceSource.kind=native-profile|summary.nativeArtifactDescriptor.optimizationEvidence.evidenceSource.path=backend/vulkan/VulkanStorageImageNonUniformDescriptorArrayShader.profile.json|summary.targetLegalizationEvidence.health=ok|summary.targetLegalizationEvidence.packageMode=native|summary.targetLegalizationEvidence.packageModeSource=manifest.packageArtifactRequirements|diagnosticCounts.error=0"
    EXPECTED_JSON_ARRAY_LENGTHS
      "diagnostics=0|summary.targetLegalizationEvidence.packageArtifactRequirementEvidenceIds=3|summary.targetLegalizationEvidence.missingEvidence=0"
    EXPECTED_MANIFEST_JSON_FIELDS
      "schemaVersion=1|target=vulkan|module=VulkanStorageImageNonUniformDescriptorArrayShader|targetLegalizationToolRequirements.target=vulkan|targetLegalizationToolRequirements.packageMode=native|targetLegalizationToolRequirements.requiredToolCount=2|targetLegalizationToolRequirements.missingToolCount=0|targetLegalizationToolRequirements.optionalNativeToolMissing=false|targetLegalizationToolRequirements.optionalNativeToolStatus=not-required|packageArtifactRequirements.target=vulkan|packageArtifactRequirements.packageMode=native|packageArtifactRequirements.requiresNativeBinaryStatus=false|packageArtifactRequirements.allowsPlannedNativeBinary=false|packageArtifactRequirements.allowsPlannedNativeSourceEvidence=false|artifacts.backendAssembly=backend/vulkan/VulkanStorageImageNonUniformDescriptorArrayShader.spvasm|artifacts.nativeBinary=backend/vulkan/VulkanStorageImageNonUniformDescriptorArrayShader.spv|artifacts.nativeProfile=backend/vulkan/VulkanStorageImageNonUniformDescriptorArrayShader.profile.json|artifacts.debugMetadata=ir/debug-metadata.json|artifacts.hirSourceMap=ir/hir-source-map.json|artifacts.nativeArtifactDescriptor=backend/vulkan/VulkanStorageImageNonUniformDescriptorArrayShader.native-artifact.json|artifacts.targetExplanation=ir/target-explanation.json"
    EXPECTED_MANIFEST_JSON_ARRAY_CONTAINS
      "targetLegalizationToolRequirements.requiredToolIds=vulkan.toolchain.spirv-as|targetLegalizationToolRequirements.requiredToolIds=vulkan.validation.spirv-val|targetLegalizationToolRequirements.toolRequirementEvidenceIds=target-legalization.v1.vulkan.tool-requirements.present|packageArtifactRequirements.requiredPathArtifacts=backendAssembly|packageArtifactRequirements.requiredPathArtifacts=nativeBinary|packageArtifactRequirements.evidenceIds=target-legalization.v1.vulkan.package-artifacts.native"
    EXPECTED_MANIFEST_JSON_ARRAY_LENGTHS
      "targetLegalizationToolRequirements.requiredToolIds=2|targetLegalizationToolRequirements.missingToolIds=0|targetLegalizationToolRequirements.toolRequirementEvidenceIds=3|packageArtifactRequirements.requiredPathArtifacts=2|packageArtifactRequirements.evidenceIds=3"
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_FIELDS
      "target=vulkan|binaryKind=vulkan.spirv-module|sourcePath=backend/vulkan/VulkanStorageImageNonUniformDescriptorArrayShader.spvasm|artifactPath=backend/vulkan/VulkanStorageImageNonUniformDescriptorArrayShader.spv|optimizationLevel=O1|optimizationEvidence.requestedLevel=O1|optimizationEvidence.effectiveLevel=none|optimizationEvidence.policy=disabled-by-opt-level|optimizationEvidence.status=skipped-disabled|optimizationEvidence.tool=spirv-opt|optimizationEvidence.evidenceSource.kind=native-profile|optimizationEvidence.evidenceSource.path=backend/vulkan/VulkanStorageImageNonUniformDescriptorArrayShader.profile.json|validationStatus=validated|toolchainProvenance.tools.1.name=spirv-as|toolchainProvenance.tools.1.role=assembler|toolchainProvenance.tools.2.name=spirv-val|toolchainProvenance.tools.2.role=validator"
    EXPECTED_NATIVE_ARTIFACT_DESCRIPTOR_JSON_ARRAY_LENGTHS
      "toolchainProvenance.tools=3|validationDiagnostics=0")
  crossgl_label_optional_native_test(
    cglc_package_verify_json_schema_vulkan_storage_image_nonuniform_descriptor_array_native vulkan)
else()
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_vulkan_native_unavailable
    TARGET vulkan
    REQUIRED_VARS CROSSGL_SPIRV_AS CROSSGL_SPIRV_VAL)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_vulkan_runtime_texture_descriptor_array_native_unavailable
    TARGET vulkan
    REQUIRED_VARS CROSSGL_SPIRV_AS CROSSGL_SPIRV_VAL)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_vulkan_runtime_sampler_descriptor_array_native_unavailable
    TARGET vulkan
    REQUIRED_VARS CROSSGL_SPIRV_AS CROSSGL_SPIRV_VAL)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_vulkan_runtime_shadow_descriptor_array_native_unavailable
    TARGET vulkan
    REQUIRED_VARS CROSSGL_SPIRV_AS CROSSGL_SPIRV_VAL)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_vulkan_runtime_texture_sampler_descriptor_array_native_unavailable
    TARGET vulkan
    REQUIRED_VARS CROSSGL_SPIRV_AS CROSSGL_SPIRV_VAL)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_vulkan_runtime_texture_sampler_nonuniform_descriptor_array_native_unavailable
    TARGET vulkan
    REQUIRED_VARS CROSSGL_SPIRV_AS CROSSGL_SPIRV_VAL)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_vulkan_storage_image_explicit_format_descriptor_array_native_unavailable
    TARGET vulkan
    REQUIRED_VARS CROSSGL_SPIRV_AS CROSSGL_SPIRV_VAL)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_vulkan_storage_image_atomic_descriptor_array_native_unavailable
    TARGET vulkan
    REQUIRED_VARS CROSSGL_SPIRV_AS CROSSGL_SPIRV_VAL)
  crossgl_add_optional_native_skip_test(
    NAME cglc_package_verify_json_schema_vulkan_storage_image_nonuniform_descriptor_array_native_unavailable
    TARGET vulkan
    REQUIRED_VARS CROSSGL_SPIRV_AS CROSSGL_SPIRV_VAL)
endif()
