function(crossgl_add_runtime_loader_plan_schema_test)
  set(options TOOLCHAIN_DISABLE_FALLBACK)
  set(one_value_args
    NAME
    TARGET
    INPUT
    OUTPUT
    PACKAGE_RUNTIME_TARGET
    PACKAGE_MODE
    PACKAGE_FORMAT
    EXPECTED_RESULT
    LOGICAL_INPUT
    SOURCE_REMAP
    TOOLCHAIN_PATH)
  set(multi_value_args
    EXPECTED_JSON_FIELDS
    EXPECTED_JSON_ARRAY_CONTAINS
    EXPECTED_JSON_ARRAY_LENGTHS)
  cmake_parse_arguments(CROSSGL_RUNTIME_PLAN
    "${options}" "${one_value_args}" "${multi_value_args}" ${ARGN})
  if(NOT CROSSGL_RUNTIME_PLAN_NAME)
    message(FATAL_ERROR
      "crossgl_add_runtime_loader_plan_schema_test requires NAME")
  endif()
  if(NOT CROSSGL_RUNTIME_PLAN_TARGET)
    message(FATAL_ERROR
      "crossgl_add_runtime_loader_plan_schema_test requires TARGET")
  endif()
  if(NOT CROSSGL_RUNTIME_PLAN_INPUT)
    message(FATAL_ERROR
      "crossgl_add_runtime_loader_plan_schema_test requires INPUT")
  endif()
  if(NOT CROSSGL_RUNTIME_PLAN_OUTPUT)
    set(CROSSGL_RUNTIME_PLAN_OUTPUT
      "${CMAKE_CURRENT_BINARY_DIR}/${CROSSGL_RUNTIME_PLAN_TARGET}-runtime-plan.cglb")
  endif()

  set(runtime_plan_definitions
      -DCGLC=$<TARGET_FILE:cglc>
      "-DINPUT=${CROSSGL_RUNTIME_PLAN_INPUT}"
      "-DTARGET=${CROSSGL_RUNTIME_PLAN_TARGET}"
      "-DOUTPUT=${CROSSGL_RUNTIME_PLAN_OUTPUT}"
      -DMODE=package-runtime-plan
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/runtime-loader-plan-v1.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      -DSTORED_ZIP_PACKAGE_CREATOR=${CMAKE_CURRENT_FUNCTION_LIST_DIR}/CreateStoredZipPackage.py
      "-DEXPECTED_JSON_FIELDS=${CROSSGL_RUNTIME_PLAN_EXPECTED_JSON_FIELDS}"
      "-DEXPECTED_JSON_ARRAY_CONTAINS=${CROSSGL_RUNTIME_PLAN_EXPECTED_JSON_ARRAY_CONTAINS}"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=${CROSSGL_RUNTIME_PLAN_EXPECTED_JSON_ARRAY_LENGTHS}")
  if(CROSSGL_RUNTIME_PLAN_PACKAGE_RUNTIME_TARGET)
    list(APPEND runtime_plan_definitions
      "-DPACKAGE_RUNTIME_TARGET=${CROSSGL_RUNTIME_PLAN_PACKAGE_RUNTIME_TARGET}")
  endif()
  if(CROSSGL_RUNTIME_PLAN_PACKAGE_MODE)
    list(APPEND runtime_plan_definitions
      "-DPACKAGE_MODE=${CROSSGL_RUNTIME_PLAN_PACKAGE_MODE}")
  endif()
  if(CROSSGL_RUNTIME_PLAN_PACKAGE_FORMAT)
    list(APPEND runtime_plan_definitions
      "-DPACKAGE_FORMAT=${CROSSGL_RUNTIME_PLAN_PACKAGE_FORMAT}")
  endif()
  if(DEFINED CROSSGL_RUNTIME_PLAN_EXPECTED_RESULT)
    list(APPEND runtime_plan_definitions
      "-DEXPECTED_RESULT=${CROSSGL_RUNTIME_PLAN_EXPECTED_RESULT}")
  endif()
  if(CROSSGL_RUNTIME_PLAN_LOGICAL_INPUT)
    list(APPEND runtime_plan_definitions
      "-DLOGICAL_INPUT=${CROSSGL_RUNTIME_PLAN_LOGICAL_INPUT}")
  endif()
  if(CROSSGL_RUNTIME_PLAN_SOURCE_REMAP)
    list(APPEND runtime_plan_definitions
      "-DSOURCE_REMAP=${CROSSGL_RUNTIME_PLAN_SOURCE_REMAP}")
  endif()
  if(CROSSGL_RUNTIME_PLAN_TOOLCHAIN_PATH)
    list(APPEND runtime_plan_definitions
      "-DTOOLCHAIN_PATH=${CROSSGL_RUNTIME_PLAN_TOOLCHAIN_PATH}")
  endif()
  if(CROSSGL_RUNTIME_PLAN_TOOLCHAIN_DISABLE_FALLBACK)
    list(APPEND runtime_plan_definitions -DTOOLCHAIN_DISABLE_FALLBACK=ON)
  endif()

  crossgl_add_python_expect_test(
    NAME "${CROSSGL_RUNTIME_PLAN_NAME}"
    DEFINITIONS ${runtime_plan_definitions})
endfunction()

string(CONCAT CROSSGL_RUNTIME_PLAN_DIRECTX_HOST_LOADER_FIELDS
  "hostLoaderIntegration.status=ready|hostLoaderIntegration.summary.targetCount=1|hostLoaderIntegration.summary.loadUnitCount=1|hostLoaderIntegration.summary.readyLoadUnitCount=1|hostLoaderIntegration.summary.blockedLoadUnitCount=0|hostLoaderIntegration.summary.entryPointCount=1|hostLoaderIntegration.summary.resourceBindingCount=1|hostLoaderIntegration.summary.workgroupSizeCount=1|hostLoaderIntegration.summary.functionConstantCount=0|hostLoaderIntegration.summary.specializationConstantCount=0|hostLoaderIntegration.loadUnits.0.id=runtime-loader.directx.backendSource|hostLoaderIntegration.loadUnits.0.target=directx|hostLoaderIntegration.loadUnits.0.packageMode=source-package|hostLoaderIntegration.loadUnits.0.packagePath=backend/directx/StorageBufferComputeShader.hlsl|hostLoaderIntegration.loadUnits.0.artifactFormat=backend-source|hostLoaderIntegration.loadUnits.0.adapterKind=backend-source-loader|hostLoaderIntegration.loadUnits.0.status=ready|hostLoaderIntegration.loadUnits.0.sourceRemap=null"
  "|hostLoaderIntegration.loadUnits.0.backendSourceMap.source=manifest.artifacts.backendSourceMap|hostLoaderIntegration.loadUnits.0.backendSourceMap.packagePath=backend/directx/StorageBufferComputeShader.backend-source-map.json|hostLoaderIntegration.loadUnits.0.backendSourceMap.exists=true|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.available=true|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.kind=crossgl.backendSourceMap|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.target=directx|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.mappingGranularity=statement"
  "|hostLoaderIntegration.loadUnits.0.hostInterface.status=ready|hostLoaderIntegration.loadUnits.0.hostInterface.entryPointCount=1|hostLoaderIntegration.loadUnits.0.hostInterface.resourceBindingCount=1|hostLoaderIntegration.loadUnits.0.hostInterface.workgroupSizeCount=1|hostLoaderIntegration.loadUnits.0.hostInterface.functionConstantCount=0|hostLoaderIntegration.loadUnits.0.hostInterface.specializationConstantCount=0|hostLoaderIntegration.loadUnits.0.validation.loadReady=true|hostLoaderIntegration.loadUnits.0.validation.metadataOnly=true|hostLoaderIntegration.loadUnits.0.validation.compilerInvocationRequired=false|hostLoaderIntegration.loadUnits.0.validation.deviceExecutionRequired=false|hostLoaderIntegration.loadUnits.0.loadSteps.0.kind=load-package-artifact|hostLoaderIntegration.loadUnits.0.loadSteps.0.message=Load the selected runtime package artifact.|hostLoaderIntegration.loadUnits.0.loadSteps.0.target=directx|hostLoaderIntegration.loadUnits.0.loadSteps.0.packagePath=backend/directx/StorageBufferComputeShader.hlsl|hostLoaderIntegration.loadUnits.0.loadSteps.0.hostInterfaceStatus=ready|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.source.field=selectedArtifact.path|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.source.path=backend/directx/StorageBufferComputeShader.hlsl|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.artifact.name=backendSource|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.artifact.packageMode=source-package|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.artifact.artifactFormat=backend-source"
  "|hostLoaderIntegration.loadUnits.0.loadSteps.1.kind=load-backend-source-map|hostLoaderIntegration.loadUnits.0.loadSteps.1.message=Load backend source map metadata for diagnostics.|hostLoaderIntegration.loadUnits.0.loadSteps.1.target=directx|hostLoaderIntegration.loadUnits.0.loadSteps.1.packagePath=backend/directx/StorageBufferComputeShader.backend-source-map.json|hostLoaderIntegration.loadUnits.0.loadSteps.1.hostInterfaceStatus=ready|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.source.field=manifest.artifacts.backendSourceMap|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.source.path=backend/directx/StorageBufferComputeShader.backend-source-map.json|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.provenance.source=loadUnit.backendSourceMap.provenance|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.provenance.available=true"
  "|hostLoaderIntegration.loadUnits.0.loadSteps.2.kind=bind-host-interface|hostLoaderIntegration.loadUnits.0.loadSteps.2.message=Bind reflected host interface metadata.|hostLoaderIntegration.loadUnits.0.loadSteps.2.target=directx|hostLoaderIntegration.loadUnits.0.loadSteps.2.packagePath=backend/directx/StorageBufferComputeShader.hlsl|hostLoaderIntegration.loadUnits.0.loadSteps.2.hostInterfaceStatus=ready|hostLoaderIntegration.loadUnits.0.loadSteps.2.metadata.source.field=reflectionInputs")

string(CONCAT CROSSGL_RUNTIME_PLAN_DIRECTX_NATIVE_HOST_LOADER_FIELDS
  "hostLoaderIntegration.status=ready|hostLoaderIntegration.summary.targetCount=1|hostLoaderIntegration.summary.loadUnitCount=1|hostLoaderIntegration.summary.readyLoadUnitCount=1|hostLoaderIntegration.summary.blockedLoadUnitCount=0|hostLoaderIntegration.summary.entryPointCount=1|hostLoaderIntegration.summary.resourceBindingCount=1|hostLoaderIntegration.summary.workgroupSizeCount=1|hostLoaderIntegration.summary.functionConstantCount=0|hostLoaderIntegration.summary.specializationConstantCount=0|hostLoaderIntegration.loadUnits.0.id=runtime-loader.directx.nativeBinary|hostLoaderIntegration.loadUnits.0.target=directx|hostLoaderIntegration.loadUnits.0.packageMode=native|hostLoaderIntegration.loadUnits.0.packagePath=backend/directx/StorageBufferComputeShader.dxil|hostLoaderIntegration.loadUnits.0.artifactFormat=native-binary|hostLoaderIntegration.loadUnits.0.adapterKind=native-binary-loader|hostLoaderIntegration.loadUnits.0.status=ready|hostLoaderIntegration.loadUnits.0.sourceRemap=null"
  "|hostLoaderIntegration.loadUnits.0.backendSourceMap.source=manifest.artifacts.backendSourceMap|hostLoaderIntegration.loadUnits.0.backendSourceMap.packagePath=backend/directx/StorageBufferComputeShader.backend-source-map.json|hostLoaderIntegration.loadUnits.0.backendSourceMap.exists=true|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.available=true|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.kind=crossgl.backendSourceMap|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.target=directx|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.mappingGranularity=statement"
  "|hostLoaderIntegration.loadUnits.0.hostInterface.status=ready|hostLoaderIntegration.loadUnits.0.hostInterface.entryPointCount=1|hostLoaderIntegration.loadUnits.0.hostInterface.resourceBindingCount=1|hostLoaderIntegration.loadUnits.0.hostInterface.workgroupSizeCount=1|hostLoaderIntegration.loadUnits.0.hostInterface.functionConstantCount=0|hostLoaderIntegration.loadUnits.0.hostInterface.specializationConstantCount=0|hostLoaderIntegration.loadUnits.0.validation.loadReady=true|hostLoaderIntegration.loadUnits.0.validation.metadataOnly=true|hostLoaderIntegration.loadUnits.0.validation.compilerInvocationRequired=false|hostLoaderIntegration.loadUnits.0.validation.deviceExecutionRequired=false|hostLoaderIntegration.loadUnits.0.loadSteps.0.kind=load-package-artifact|hostLoaderIntegration.loadUnits.0.loadSteps.0.message=Load the selected runtime package artifact.|hostLoaderIntegration.loadUnits.0.loadSteps.0.target=directx|hostLoaderIntegration.loadUnits.0.loadSteps.0.packagePath=backend/directx/StorageBufferComputeShader.dxil|hostLoaderIntegration.loadUnits.0.loadSteps.0.hostInterfaceStatus=ready|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.source.field=selectedArtifact.path|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.source.path=backend/directx/StorageBufferComputeShader.dxil|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.artifact.name=nativeBinary|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.artifact.packageMode=native|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.artifact.artifactFormat=native-binary"
  "|hostLoaderIntegration.loadUnits.0.loadSteps.1.kind=load-backend-source-map|hostLoaderIntegration.loadUnits.0.loadSteps.1.message=Load backend source map metadata for diagnostics.|hostLoaderIntegration.loadUnits.0.loadSteps.1.target=directx|hostLoaderIntegration.loadUnits.0.loadSteps.1.packagePath=backend/directx/StorageBufferComputeShader.backend-source-map.json|hostLoaderIntegration.loadUnits.0.loadSteps.1.hostInterfaceStatus=ready|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.source.field=manifest.artifacts.backendSourceMap|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.source.path=backend/directx/StorageBufferComputeShader.backend-source-map.json|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.provenance.source=loadUnit.backendSourceMap.provenance|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.provenance.available=true"
  "|hostLoaderIntegration.loadUnits.0.loadSteps.2.kind=bind-host-interface|hostLoaderIntegration.loadUnits.0.loadSteps.2.message=Bind reflected host interface metadata.|hostLoaderIntegration.loadUnits.0.loadSteps.2.target=directx|hostLoaderIntegration.loadUnits.0.loadSteps.2.packagePath=backend/directx/StorageBufferComputeShader.dxil|hostLoaderIntegration.loadUnits.0.loadSteps.2.hostInterfaceStatus=ready|hostLoaderIntegration.loadUnits.0.loadSteps.2.metadata.source.field=reflectionInputs")

string(CONCAT CROSSGL_RUNTIME_PLAN_VULKAN_HOST_LOADER_FIELDS
  "hostLoaderIntegration.status=ready|hostLoaderIntegration.summary.targetCount=1|hostLoaderIntegration.summary.loadUnitCount=1|hostLoaderIntegration.summary.readyLoadUnitCount=1|hostLoaderIntegration.summary.blockedLoadUnitCount=0|hostLoaderIntegration.summary.entryPointCount=1|hostLoaderIntegration.summary.resourceBindingCount=1|hostLoaderIntegration.summary.workgroupSizeCount=1|hostLoaderIntegration.summary.functionConstantCount=0|hostLoaderIntegration.summary.specializationConstantCount=0|hostLoaderIntegration.loadUnits.0.id=runtime-loader.vulkan.nativeBinary|hostLoaderIntegration.loadUnits.0.target=vulkan|hostLoaderIntegration.loadUnits.0.packageMode=native|hostLoaderIntegration.loadUnits.0.packagePath=backend/vulkan/StorageBufferComputeShader.spv|hostLoaderIntegration.loadUnits.0.artifactFormat=native-binary|hostLoaderIntegration.loadUnits.0.adapterKind=native-binary-loader|hostLoaderIntegration.loadUnits.0.status=ready|hostLoaderIntegration.loadUnits.0.sourceRemap=null"
  "|hostLoaderIntegration.loadUnits.0.backendSourceMap.source=manifest.artifacts.backendSourceMap|hostLoaderIntegration.loadUnits.0.backendSourceMap.packagePath=backend/vulkan/StorageBufferComputeShader.backend-source-map.json|hostLoaderIntegration.loadUnits.0.backendSourceMap.exists=true|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.available=true|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.kind=crossgl.backendSourceMap|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.target=vulkan|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.mappingGranularity=statement"
  "|hostLoaderIntegration.loadUnits.0.hostInterface.status=ready|hostLoaderIntegration.loadUnits.0.hostInterface.entryPointCount=1|hostLoaderIntegration.loadUnits.0.hostInterface.resourceBindingCount=1|hostLoaderIntegration.loadUnits.0.hostInterface.workgroupSizeCount=1|hostLoaderIntegration.loadUnits.0.hostInterface.functionConstantCount=0|hostLoaderIntegration.loadUnits.0.hostInterface.specializationConstantCount=0|hostLoaderIntegration.loadUnits.0.validation.loadReady=true|hostLoaderIntegration.loadUnits.0.validation.metadataOnly=true|hostLoaderIntegration.loadUnits.0.validation.compilerInvocationRequired=false|hostLoaderIntegration.loadUnits.0.validation.deviceExecutionRequired=false|hostLoaderIntegration.loadUnits.0.loadSteps.0.kind=load-package-artifact|hostLoaderIntegration.loadUnits.0.loadSteps.0.message=Load the selected runtime package artifact.|hostLoaderIntegration.loadUnits.0.loadSteps.0.target=vulkan|hostLoaderIntegration.loadUnits.0.loadSteps.0.packagePath=backend/vulkan/StorageBufferComputeShader.spv|hostLoaderIntegration.loadUnits.0.loadSteps.0.hostInterfaceStatus=ready|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.source.field=selectedArtifact.path|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.source.path=backend/vulkan/StorageBufferComputeShader.spv|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.artifact.name=nativeBinary|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.artifact.packageMode=native|hostLoaderIntegration.loadUnits.0.loadSteps.0.metadata.artifact.artifactFormat=native-binary"
  "|hostLoaderIntegration.loadUnits.0.loadSteps.1.kind=load-backend-source-map|hostLoaderIntegration.loadUnits.0.loadSteps.1.message=Load backend source map metadata for diagnostics.|hostLoaderIntegration.loadUnits.0.loadSteps.1.target=vulkan|hostLoaderIntegration.loadUnits.0.loadSteps.1.packagePath=backend/vulkan/StorageBufferComputeShader.backend-source-map.json|hostLoaderIntegration.loadUnits.0.loadSteps.1.hostInterfaceStatus=ready|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.source.field=manifest.artifacts.backendSourceMap|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.source.path=backend/vulkan/StorageBufferComputeShader.backend-source-map.json|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.provenance.source=loadUnit.backendSourceMap.provenance|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.provenance.available=true"
  "|hostLoaderIntegration.loadUnits.0.loadSteps.2.kind=bind-host-interface|hostLoaderIntegration.loadUnits.0.loadSteps.2.message=Bind reflected host interface metadata.|hostLoaderIntegration.loadUnits.0.loadSteps.2.target=vulkan|hostLoaderIntegration.loadUnits.0.loadSteps.2.packagePath=backend/vulkan/StorageBufferComputeShader.spv|hostLoaderIntegration.loadUnits.0.loadSteps.2.hostInterfaceStatus=ready|hostLoaderIntegration.loadUnits.0.loadSteps.2.metadata.source.field=reflectionInputs")

crossgl_add_runtime_loader_plan_schema_test(
  NAME cglc_package_runtime_plan_directx_source_package_auto_schema
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/runtime-plan-directx-source.cglb
  PACKAGE_MODE auto
  EXPECTED_RESULT 0
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|kind=crossgl-runtime-loader-plan|success=true|metadataOnly=true|compilerInvocationRequired=false|deviceExecutionRequired=false|packageFormat=directory|packageTarget=directx|requestedLoaderTarget=directx|targetMatchesPackage=true|requestedPackageMode=auto|selectedPackageMode=source-package|selectedArtifact.name=backendSource|selectedArtifact.path=backend/directx/StorageBufferComputeShader.hlsl|selectedArtifact.packageMode=source-package|selectedArtifact.packageRelative=true|selectedArtifact.exists=true|requiredMetadataInputs.0=manifest.json|requiredMetadataInputs.1=reflection.json|requiredMetadataInputs.2=diagnostics.json|packageArtifactRequirementsSource=manifest.packageArtifactRequirements|packageArtifactRequirements.target=directx|packageArtifactRequirements.packageMode=source-package|targetLegalizationEvidenceSummary.toolRequirementsPresent=true|targetLegalizationEvidenceSummary.target=directx|targetLegalizationEvidenceSummary.packageMode=source-package|targetLegalizationEvidenceSummary.requiredToolCount=2|reflectionSummary.resourceCount=1|reflectionSummary.targetResourceBindingCount=1|reflectionSummary.entryPointCount=1|reflectionSummary.workgroupSizeCount=1|reflectionSummary.threadgroupShapeSource=reflection.workgroupSizes|reflectionInputs.targetResourceBindings.0.set=0|reflectionInputs.targetResourceBindings.0.binding=0|reflectionInputs.targetResourceBindings.0.argumentIndex=0|diagnosticCounts.error=0|${CROSSGL_RUNTIME_PLAN_DIRECTX_HOST_LOADER_FIELDS}"
  EXPECTED_JSON_ARRAY_CONTAINS
    "targetLegalizationEvidenceSummary.requiredToolIds=directx.toolchain.dxc|targetLegalizationEvidenceSummary.requiredToolIds=directx.validation.dxil-validator|hostLoaderIntegration.loadUnits.0.requiredTools=directx.toolchain.dxc|hostLoaderIntegration.loadUnits.0.requiredTools=directx.validation.dxil-validator|hostLoaderIntegration.loadUnits.0.hostResponsibilities=load-package-artifact|hostLoaderIntegration.loadUnits.0.hostResponsibilities=load-backend-source-map|hostLoaderIntegration.loadUnits.0.hostResponsibilities=bind-reflected-entry-points|hostLoaderIntegration.loadUnits.0.hostResponsibilities=bind-reflected-resources|hostLoaderIntegration.loadUnits.0.hostResponsibilities=bind-workgroup-shape|hostLoaderIntegration.loadUnits.0.hostResponsibilities=review-target-tool-requirements"
  EXPECTED_JSON_ARRAY_LENGTHS
    "requiredMetadataInputs=3|packageArtifactRequirements.requiredPathArtifacts=2|hostLoaderIntegration.loadUnits.0.requiredTools=2|hostLoaderIntegration.loadUnits.0.hostResponsibilities=6|hostLoaderIntegration.loadUnits.0.loadSteps=3|hostLoaderIntegration.loadUnits.0.blockers=0|diagnostics=0")

set(CROSSGL_RUNTIME_PLAN_SOURCE_REMAP_FULL_FILE
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-full-file.json")
set(CROSSGL_RUNTIME_PLAN_SOURCE_REMAP_FULL_FILE_METADATA
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-full-file-report-metadata.json")
file(SHA256 "${CROSSGL_RUNTIME_PLAN_SOURCE_REMAP_FULL_FILE}"
     CROSSGL_RUNTIME_PLAN_SOURCE_REMAP_FULL_FILE_SHA256)
file(SIZE "${CROSSGL_RUNTIME_PLAN_SOURCE_REMAP_FULL_FILE}"
     CROSSGL_RUNTIME_PLAN_SOURCE_REMAP_FULL_FILE_SIZE_BYTES)

crossgl_add_runtime_loader_plan_schema_test(
  NAME cglc_package_runtime_plan_directx_source_remap_schema
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/runtime-plan-directx-source-remap.cglb
  PACKAGE_MODE auto
  LOGICAL_INPUT generated/from-translator.cgl
  SOURCE_REMAP ${CROSSGL_RUNTIME_PLAN_SOURCE_REMAP_FULL_FILE_METADATA}
  EXPECTED_RESULT 0
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|kind=crossgl-runtime-loader-plan|success=true|metadataOnly=true|compilerInvocationRequired=false|deviceExecutionRequired=false|packageFormat=directory|packageTarget=directx|requestedLoaderTarget=directx|targetMatchesPackage=true|requestedPackageMode=auto|selectedPackageMode=source-package|selectedArtifact.name=backendSource|selectedArtifact.path=backend/directx/StorageBufferComputeShader.hlsl|selectedArtifact.packageMode=source-package|selectedArtifact.packageRelative=true|selectedArtifact.exists=true|hostLoaderIntegration.loadUnits.0.sourceRemap.source=manifest.artifacts.sourceRemap|hostLoaderIntegration.loadUnits.0.sourceRemap.packagePath=ir/source-remap-provenance.json|hostLoaderIntegration.loadUnits.0.sourceRemap.exists=true|hostLoaderIntegration.loadUnits.0.sourceRemap.provenance.available=true|hostLoaderIntegration.loadUnits.0.sourceRemap.provenance.health=ok|hostLoaderIntegration.loadUnits.0.sourceRemap.provenance.target=directx|hostLoaderIntegration.loadUnits.0.sourceRemap.provenance.generatedFile=generated/from-translator.cgl|hostLoaderIntegration.loadUnits.0.sourceRemap.provenance.mappingGranularity=source-span|hostLoaderIntegration.loadUnits.0.sourceRemap.provenance.mappingCount=1|hostLoaderIntegration.loadUnits.0.sourceRemap.provenance.sourceSha256=${CROSSGL_RUNTIME_PLAN_SOURCE_REMAP_FULL_FILE_SHA256}|hostLoaderIntegration.loadUnits.0.sourceRemap.provenance.sourceSizeBytes=${CROSSGL_RUNTIME_PLAN_SOURCE_REMAP_FULL_FILE_SIZE_BYTES}|hostLoaderIntegration.loadUnits.0.sourceRemap.provenance.sourceRemapTarget=cgl|hostLoaderIntegration.loadUnits.0.sourceRemap.provenance.sourceRemapMappingGranularity=file|hostLoaderIntegration.loadUnits.0.sourceRemap.provenance.sourceRemapSourceBackend=cgl|hostLoaderIntegration.loadUnits.0.sourceRemap.provenance.sourceRemapVariant=debug|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.sourceRemapPresent=true|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.sourceRemapPath=ir/source-remap-provenance.json|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.sourceRemapGeneratedFile=generated/from-translator.cgl|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.sourceRemapTarget=cgl|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.sourceRemapMappingGranularity=file|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.sourceRemapMappingCount=1|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.sourceRemapSourceBackend=cgl|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.sourceRemapVariant=debug|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.sourceRemapSha256=${CROSSGL_RUNTIME_PLAN_SOURCE_REMAP_FULL_FILE_SHA256}|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.sourceRemapSizeBytes=${CROSSGL_RUNTIME_PLAN_SOURCE_REMAP_FULL_FILE_SIZE_BYTES}|hostLoaderIntegration.loadUnits.0.loadSteps.1.kind=load-source-remap|hostLoaderIntegration.loadUnits.0.loadSteps.1.packagePath=ir/source-remap-provenance.json|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.source.field=manifest.artifacts.sourceRemap|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.source.path=ir/source-remap-provenance.json|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.provenance.source=loadUnit.sourceRemap.provenance|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.provenance.available=true|hostLoaderIntegration.loadUnits.0.loadSteps.1.metadata.provenance.health=ok|hostLoaderIntegration.loadUnits.0.loadSteps.2.kind=load-backend-source-map|hostLoaderIntegration.loadUnits.0.loadSteps.2.packagePath=backend/directx/StorageBufferComputeShader.backend-source-map.json|hostLoaderIntegration.loadUnits.0.loadSteps.2.metadata.source.field=manifest.artifacts.backendSourceMap|hostLoaderIntegration.loadUnits.0.loadSteps.2.metadata.source.path=backend/directx/StorageBufferComputeShader.backend-source-map.json|hostLoaderIntegration.loadUnits.0.loadSteps.2.metadata.provenance.source=loadUnit.backendSourceMap.provenance|hostLoaderIntegration.loadUnits.0.loadSteps.2.metadata.provenance.available=true|hostLoaderIntegration.loadUnits.0.loadSteps.2.metadata.provenance.health=ok|hostLoaderIntegration.loadUnits.0.loadSteps.3.kind=bind-host-interface|diagnosticCounts.error=0"
  EXPECTED_JSON_ARRAY_CONTAINS
    "hostLoaderIntegration.loadUnits.0.hostResponsibilities=load-package-artifact|hostLoaderIntegration.loadUnits.0.hostResponsibilities=load-source-remap|hostLoaderIntegration.loadUnits.0.hostResponsibilities=load-backend-source-map|hostLoaderIntegration.loadUnits.0.hostResponsibilities=bind-reflected-entry-points|hostLoaderIntegration.loadUnits.0.hostResponsibilities=bind-reflected-resources|hostLoaderIntegration.loadUnits.0.hostResponsibilities=bind-workgroup-shape|hostLoaderIntegration.loadUnits.0.hostResponsibilities=review-target-tool-requirements"
  EXPECTED_JSON_ARRAY_LENGTHS
    "requiredMetadataInputs=3|packageArtifactRequirements.requiredPathArtifacts=2|hostLoaderIntegration.loadUnits.0.requiredTools=2|hostLoaderIntegration.loadUnits.0.hostResponsibilities=7|hostLoaderIntegration.loadUnits.0.loadSteps=4|hostLoaderIntegration.loadUnits.0.blockers=0|diagnostics=0")

crossgl_add_runtime_loader_plan_schema_test(
  NAME cglc_package_runtime_plan_directx_native_fake_dxc_schema
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/runtime-plan-directx-native-fake-dxc.cglb
  PACKAGE_MODE native
  EXPECTED_RESULT 0
  TOOLCHAIN_PATH ${CROSSGL_FAKE_DXC_SUCCESS_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|kind=crossgl-runtime-loader-plan|success=true|metadataOnly=true|compilerInvocationRequired=false|deviceExecutionRequired=false|packageFormat=directory|packageTarget=directx|requestedLoaderTarget=directx|targetMatchesPackage=true|requestedPackageMode=native|selectedPackageMode=native|selectedArtifact.name=nativeBinary|selectedArtifact.path=backend/directx/StorageBufferComputeShader.dxil|selectedArtifact.packageMode=native|selectedArtifact.packageRelative=true|selectedArtifact.exists=true|requiredMetadataInputs.0=manifest.json|requiredMetadataInputs.1=reflection.json|requiredMetadataInputs.2=diagnostics.json|packageArtifactRequirementsSource=manifest.packageArtifactRequirements|packageArtifactRequirements.target=directx|packageArtifactRequirements.packageMode=native|targetLegalizationEvidenceSummary.toolRequirementsPresent=true|targetLegalizationEvidenceSummary.target=directx|targetLegalizationEvidenceSummary.packageMode=native|targetLegalizationEvidenceSummary.requiredToolCount=2|targetLegalizationEvidenceSummary.missingToolCount=0|reflectionSummary.resourceCount=1|reflectionSummary.targetResourceBindingCount=1|reflectionSummary.entryPointCount=1|reflectionSummary.workgroupSizeCount=1|reflectionSummary.threadgroupShapeSource=reflection.workgroupSizes|reflectionInputs.targetResourceBindings.0.set=0|reflectionInputs.targetResourceBindings.0.binding=0|reflectionInputs.targetResourceBindings.0.argumentIndex=0|diagnosticCounts.error=0|${CROSSGL_RUNTIME_PLAN_DIRECTX_NATIVE_HOST_LOADER_FIELDS}"
  EXPECTED_JSON_ARRAY_CONTAINS
    "targetLegalizationEvidenceSummary.requiredToolIds=directx.toolchain.dxc|targetLegalizationEvidenceSummary.requiredToolIds=directx.validation.dxil-validator|hostLoaderIntegration.loadUnits.0.requiredTools=directx.toolchain.dxc|hostLoaderIntegration.loadUnits.0.requiredTools=directx.validation.dxil-validator|hostLoaderIntegration.loadUnits.0.hostResponsibilities=load-package-artifact|hostLoaderIntegration.loadUnits.0.hostResponsibilities=load-backend-source-map|hostLoaderIntegration.loadUnits.0.hostResponsibilities=bind-reflected-entry-points|hostLoaderIntegration.loadUnits.0.hostResponsibilities=bind-reflected-resources|hostLoaderIntegration.loadUnits.0.hostResponsibilities=bind-workgroup-shape|hostLoaderIntegration.loadUnits.0.hostResponsibilities=review-target-tool-requirements"
  EXPECTED_JSON_ARRAY_LENGTHS
    "requiredMetadataInputs=3|packageArtifactRequirements.requiredPathArtifacts=2|targetLegalizationEvidenceSummary.missingToolIds=0|hostLoaderIntegration.loadUnits.0.requiredTools=2|hostLoaderIntegration.loadUnits.0.hostResponsibilities=6|hostLoaderIntegration.loadUnits.0.loadSteps=3|hostLoaderIntegration.loadUnits.0.blockers=0|diagnostics=0")

crossgl_add_runtime_loader_plan_schema_test(
  NAME cglc_package_runtime_plan_vulkan_native_schema
  TARGET vulkan
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/runtime-plan-vulkan-native.cglb
  PACKAGE_MODE native
  EXPECTED_RESULT 0
  TOOLCHAIN_PATH ${CROSSGL_FAKE_VULKAN_SUCCESS_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|kind=crossgl-runtime-loader-plan|success=true|metadataOnly=true|compilerInvocationRequired=false|deviceExecutionRequired=false|packageFormat=directory|packageTarget=vulkan|requestedLoaderTarget=vulkan|targetMatchesPackage=true|requestedPackageMode=native|selectedPackageMode=native|selectedArtifact.name=nativeBinary|selectedArtifact.path=backend/vulkan/StorageBufferComputeShader.spv|selectedArtifact.packageMode=native|selectedArtifact.packageRelative=true|selectedArtifact.exists=true|packageArtifactRequirementsSource=manifest.packageArtifactRequirements|packageArtifactRequirements.target=vulkan|packageArtifactRequirements.packageMode=native|targetLegalizationEvidenceSummary.toolRequirementsPresent=true|targetLegalizationEvidenceSummary.target=vulkan|targetLegalizationEvidenceSummary.packageMode=native|targetLegalizationEvidenceSummary.requiredToolCount=2|targetLegalizationEvidenceSummary.missingToolCount=0|reflectionSummary.resourceCount=1|reflectionSummary.targetResourceBindingCount=1|reflectionSummary.entryPointCount=1|reflectionSummary.workgroupSizeCount=1|diagnosticCounts.error=0|${CROSSGL_RUNTIME_PLAN_VULKAN_HOST_LOADER_FIELDS}"
  EXPECTED_JSON_ARRAY_CONTAINS
    "targetLegalizationEvidenceSummary.requiredToolIds=vulkan.toolchain.spirv-as|targetLegalizationEvidenceSummary.requiredToolIds=vulkan.validation.spirv-val|hostLoaderIntegration.loadUnits.0.requiredTools=vulkan.toolchain.spirv-as|hostLoaderIntegration.loadUnits.0.requiredTools=vulkan.validation.spirv-val|hostLoaderIntegration.loadUnits.0.hostResponsibilities=load-package-artifact|hostLoaderIntegration.loadUnits.0.hostResponsibilities=load-backend-source-map|hostLoaderIntegration.loadUnits.0.hostResponsibilities=bind-reflected-entry-points|hostLoaderIntegration.loadUnits.0.hostResponsibilities=bind-reflected-resources|hostLoaderIntegration.loadUnits.0.hostResponsibilities=bind-workgroup-shape|hostLoaderIntegration.loadUnits.0.hostResponsibilities=review-target-tool-requirements"
  EXPECTED_JSON_ARRAY_LENGTHS
    "requiredMetadataInputs=3|packageArtifactRequirements.requiredPathArtifacts=2|targetLegalizationEvidenceSummary.missingToolIds=0|hostLoaderIntegration.loadUnits.0.requiredTools=2|hostLoaderIntegration.loadUnits.0.hostResponsibilities=6|hostLoaderIntegration.loadUnits.0.loadSteps=3|hostLoaderIntegration.loadUnits.0.blockers=0|diagnostics=0")

crossgl_add_runtime_loader_plan_schema_test(
  NAME cglc_package_runtime_plan_directx_native_mode_unavailable_schema
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/runtime-plan-directx-native-unavailable.cglb
  PACKAGE_MODE native
  EXPECTED_RESULT 1
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|kind=crossgl-runtime-loader-plan|success=false|metadataOnly=true|compilerInvocationRequired=false|deviceExecutionRequired=false|packageFormat=directory|packageTarget=directx|requestedLoaderTarget=directx|targetMatchesPackage=true|requestedPackageMode=native|selectedPackageMode=null|selectedArtifact=null|packageArtifactRequirementsSource=manifest.packageArtifactRequirements|packageArtifactRequirements.target=directx|packageArtifactRequirements.packageMode=source-package|targetLegalizationEvidenceSummary.target=directx|targetLegalizationEvidenceSummary.packageMode=source-package|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.runtime-plan.native-artifact-unavailable|diagnostics.0.target=directx"
  EXPECTED_JSON_ARRAY_LENGTHS
    "requiredMetadataInputs=3|diagnostics=1")

crossgl_add_runtime_loader_plan_schema_test(
  NAME cglc_package_runtime_plan_vulkan_source_mode_unavailable_schema
  TARGET vulkan
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/runtime-plan-vulkan-source-unavailable.cglb
  PACKAGE_MODE source-package
  EXPECTED_RESULT 1
  TOOLCHAIN_PATH ${CROSSGL_FAKE_VULKAN_SUCCESS_DIR}
  TOOLCHAIN_DISABLE_FALLBACK
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|kind=crossgl-runtime-loader-plan|success=false|metadataOnly=true|compilerInvocationRequired=false|deviceExecutionRequired=false|packageFormat=directory|packageTarget=vulkan|requestedLoaderTarget=vulkan|targetMatchesPackage=true|requestedPackageMode=source-package|selectedPackageMode=null|selectedArtifact=null|packageArtifactRequirementsSource=manifest.packageArtifactRequirements|packageArtifactRequirements.target=vulkan|packageArtifactRequirements.packageMode=native|targetLegalizationEvidenceSummary.target=vulkan|targetLegalizationEvidenceSummary.packageMode=native|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.runtime-plan.source-artifact-unavailable|diagnostics.0.target=vulkan"
  EXPECTED_JSON_ARRAY_LENGTHS
    "requiredMetadataInputs=3|diagnostics=1")

crossgl_add_runtime_loader_plan_schema_test(
  NAME cglc_package_runtime_plan_target_mismatch_schema
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/runtime-plan-target-mismatch.cglb
  PACKAGE_RUNTIME_TARGET vulkan
  PACKAGE_MODE auto
  EXPECTED_RESULT 1
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|kind=crossgl-runtime-loader-plan|success=false|metadataOnly=true|compilerInvocationRequired=false|deviceExecutionRequired=false|packageFormat=directory|packageTarget=directx|requestedLoaderTarget=vulkan|targetMatchesPackage=false|requestedPackageMode=auto|selectedPackageMode=null|selectedArtifact=null|packageArtifactRequirementsSource=manifest.packageArtifactRequirements|packageArtifactRequirements.target=directx|packageArtifactRequirements.packageMode=source-package|targetLegalizationEvidenceSummary.target=directx|targetLegalizationEvidenceSummary.packageMode=source-package|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.runtime-plan.target-mismatch"
  EXPECTED_JSON_ARRAY_LENGTHS
    "requiredMetadataInputs=3|diagnostics=1")

crossgl_add_runtime_loader_plan_schema_test(
  NAME cglc_package_runtime_plan_deflated_zip_unsupported_schema
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/runtime-plan-directx-archive.cglb
  PACKAGE_FORMAT zip
  PACKAGE_MODE auto
  EXPECTED_RESULT 1
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|kind=crossgl-runtime-loader-plan|success=false|metadataOnly=true|compilerInvocationRequired=false|deviceExecutionRequired=false|packageFormat=zip|packageTarget=null|requestedLoaderTarget=directx|targetMatchesPackage=false|requestedPackageMode=auto|selectedPackageMode=null|selectedArtifact=null|packageArtifactRequirementsSource=null|packageArtifactRequirements=null|targetLegalizationEvidenceSummary=null|reflectionSummary=null|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.runtime-plan.unsupported-compression"
  EXPECTED_JSON_ARRAY_LENGTHS
    "requiredMetadataInputs=3|diagnostics=1")

crossgl_add_runtime_loader_plan_schema_test(
  NAME cglc_package_runtime_plan_stored_zip_source_package_auto_schema
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/runtime-plan-directx-stored-archive.cglb
  PACKAGE_FORMAT stored-zip
  PACKAGE_MODE auto
  EXPECTED_RESULT 0
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|kind=crossgl-runtime-loader-plan|success=true|metadataOnly=true|compilerInvocationRequired=false|deviceExecutionRequired=false|packageFormat=zip|packageTarget=directx|requestedLoaderTarget=directx|targetMatchesPackage=true|requestedPackageMode=auto|selectedPackageMode=source-package|selectedArtifact.name=backendSource|selectedArtifact.path=backend/directx/StorageBufferComputeShader.hlsl|selectedArtifact.packageMode=source-package|selectedArtifact.packageRelative=true|selectedArtifact.exists=true|requiredMetadataInputs.0=manifest.json|requiredMetadataInputs.1=reflection.json|requiredMetadataInputs.2=diagnostics.json|packageArtifactRequirementsSource=manifest.packageArtifactRequirements|packageArtifactRequirements.target=directx|packageArtifactRequirements.packageMode=source-package|targetLegalizationEvidenceSummary.toolRequirementsPresent=true|targetLegalizationEvidenceSummary.target=directx|targetLegalizationEvidenceSummary.packageMode=source-package|targetLegalizationEvidenceSummary.requiredToolCount=2|reflectionSummary.resourceCount=1|reflectionSummary.targetResourceBindingCount=1|reflectionSummary.entryPointCount=1|reflectionSummary.workgroupSizeCount=1|reflectionSummary.threadgroupShapeSource=reflection.workgroupSizes|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.available=true|diagnosticCounts.error=0"
  EXPECTED_JSON_ARRAY_CONTAINS
    "targetLegalizationEvidenceSummary.requiredToolIds=directx.toolchain.dxc|targetLegalizationEvidenceSummary.requiredToolIds=directx.validation.dxil-validator"
  EXPECTED_JSON_ARRAY_LENGTHS
    "requiredMetadataInputs=3|packageArtifactRequirements.requiredPathArtifacts=2|diagnostics=0")

crossgl_add_runtime_loader_plan_schema_test(
  NAME cglc_package_runtime_plan_stored_zip_root_source_package_auto_schema
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/runtime-plan-directx-stored-root-archive.cglb
  PACKAGE_FORMAT stored-zip-root
  PACKAGE_MODE auto
  EXPECTED_RESULT 0
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|kind=crossgl-runtime-loader-plan|success=true|metadataOnly=true|compilerInvocationRequired=false|deviceExecutionRequired=false|packageFormat=zip|packageTarget=directx|requestedLoaderTarget=directx|targetMatchesPackage=true|requestedPackageMode=auto|selectedPackageMode=source-package|selectedArtifact.name=backendSource|selectedArtifact.path=backend/directx/StorageBufferComputeShader.hlsl|selectedArtifact.packageMode=source-package|selectedArtifact.packageRelative=true|selectedArtifact.exists=true|requiredMetadataInputs.0=manifest.json|requiredMetadataInputs.1=reflection.json|requiredMetadataInputs.2=diagnostics.json|packageArtifactRequirementsSource=manifest.packageArtifactRequirements|packageArtifactRequirements.target=directx|packageArtifactRequirements.packageMode=source-package|targetLegalizationEvidenceSummary.toolRequirementsPresent=true|targetLegalizationEvidenceSummary.target=directx|targetLegalizationEvidenceSummary.packageMode=source-package|targetLegalizationEvidenceSummary.requiredToolCount=2|reflectionSummary.resourceCount=1|reflectionSummary.targetResourceBindingCount=1|reflectionSummary.entryPointCount=1|reflectionSummary.workgroupSizeCount=1|reflectionSummary.threadgroupShapeSource=reflection.workgroupSizes|hostLoaderIntegration.loadUnits.0.backendSourceMap.provenance.available=true|diagnosticCounts.error=0"
  EXPECTED_JSON_ARRAY_CONTAINS
    "targetLegalizationEvidenceSummary.requiredToolIds=directx.toolchain.dxc|targetLegalizationEvidenceSummary.requiredToolIds=directx.validation.dxil-validator"
  EXPECTED_JSON_ARRAY_LENGTHS
    "requiredMetadataInputs=3|packageArtifactRequirements.requiredPathArtifacts=2|diagnostics=0")

crossgl_add_runtime_loader_plan_schema_test(
  NAME cglc_package_runtime_plan_stored_zip_extra_root_file_source_package_auto_schema
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/runtime-plan-directx-stored-extra-root-archive.cglb
  PACKAGE_FORMAT stored-zip-extra-root
  PACKAGE_MODE auto
  EXPECTED_RESULT 0
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|kind=crossgl-runtime-loader-plan|success=true|metadataOnly=true|compilerInvocationRequired=false|deviceExecutionRequired=false|packageFormat=zip|packageTarget=directx|requestedLoaderTarget=directx|targetMatchesPackage=true|requestedPackageMode=auto|selectedPackageMode=source-package|selectedArtifact.name=backendSource|selectedArtifact.path=backend/directx/StorageBufferComputeShader.hlsl|selectedArtifact.packageMode=source-package|selectedArtifact.packageRelative=true|selectedArtifact.exists=true|requiredMetadataInputs.0=manifest.json|requiredMetadataInputs.1=reflection.json|requiredMetadataInputs.2=diagnostics.json|packageArtifactRequirementsSource=manifest.packageArtifactRequirements|packageArtifactRequirements.target=directx|packageArtifactRequirements.packageMode=source-package|targetLegalizationEvidenceSummary.toolRequirementsPresent=true|targetLegalizationEvidenceSummary.target=directx|targetLegalizationEvidenceSummary.packageMode=source-package|targetLegalizationEvidenceSummary.requiredToolCount=2|reflectionSummary.resourceCount=1|reflectionSummary.targetResourceBindingCount=1|reflectionSummary.entryPointCount=1|reflectionSummary.workgroupSizeCount=1|reflectionSummary.threadgroupShapeSource=reflection.workgroupSizes|diagnosticCounts.error=0"
  EXPECTED_JSON_ARRAY_CONTAINS
    "targetLegalizationEvidenceSummary.requiredToolIds=directx.toolchain.dxc|targetLegalizationEvidenceSummary.requiredToolIds=directx.validation.dxil-validator"
  EXPECTED_JSON_ARRAY_LENGTHS
    "requiredMetadataInputs=3|packageArtifactRequirements.requiredPathArtifacts=2|diagnostics=0")
