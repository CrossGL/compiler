add_test(NAME cglc_expect_command_json_literal_manifest_self_test
  COMMAND ${CMAKE_COMMAND}
    -DMODE=json-literal-self-test
    -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/ExpectCommand.cmake)

function(crossgl_add_package_inspect_json_failure_schema_test)
  set(one_value_args NAME FAILURE_KIND TARGET INPUT OUTPUT MANIFEST_MUTATION_KIND)
  set(multi_value_args EXPECTED_JSON_FIELDS EXPECTED_JSON_ARRAY_LENGTHS)
  cmake_parse_arguments(CROSSGL_INSPECT_FAILURE_SCHEMA ""
    "${one_value_args}" "${multi_value_args}" ${ARGN})
  if(NOT CROSSGL_INSPECT_FAILURE_SCHEMA_NAME)
    message(FATAL_ERROR
      "crossgl_add_package_inspect_json_failure_schema_test requires NAME")
  endif()
  if(NOT CROSSGL_INSPECT_FAILURE_SCHEMA_FAILURE_KIND)
    message(FATAL_ERROR
      "crossgl_add_package_inspect_json_failure_schema_test requires FAILURE_KIND")
  endif()
  if(NOT CROSSGL_INSPECT_FAILURE_SCHEMA_OUTPUT)
    set(CROSSGL_INSPECT_FAILURE_SCHEMA_OUTPUT
      "${CMAKE_CURRENT_BINARY_DIR}/${CROSSGL_INSPECT_FAILURE_SCHEMA_NAME}.cglb")
  endif()

  set(inspect_failure_definitions
      -DCGLC=$<TARGET_FILE:cglc>
      "-DINPUT=${CROSSGL_INSPECT_FAILURE_SCHEMA_INPUT}"
      "-DTARGET=${CROSSGL_INSPECT_FAILURE_SCHEMA_TARGET}"
      "-DOUTPUT=${CROSSGL_INSPECT_FAILURE_SCHEMA_OUTPUT}"
      -DMODE=package-inspect-json-failure
      "-DFAILURE_KIND=${CROSSGL_INSPECT_FAILURE_SCHEMA_FAILURE_KIND}"
      "-DEXPECTED_JSON_FIELDS=${CROSSGL_INSPECT_FAILURE_SCHEMA_EXPECTED_JSON_FIELDS}"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=${CROSSGL_INSPECT_FAILURE_SCHEMA_EXPECTED_JSON_ARRAY_LENGTHS}"
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      -DSTORED_ZIP_PACKAGE_CREATOR=${CMAKE_CURRENT_FUNCTION_LIST_DIR}/CreateStoredZipPackage.py)
  if(CROSSGL_INSPECT_FAILURE_SCHEMA_MANIFEST_MUTATION_KIND)
    list(APPEND inspect_failure_definitions
      "-DMANIFEST_MUTATION_KIND=${CROSSGL_INSPECT_FAILURE_SCHEMA_MANIFEST_MUTATION_KIND}")
  endif()

  crossgl_add_python_expect_test(
    NAME "${CROSSGL_INSPECT_FAILURE_SCHEMA_NAME}"
    DEFINITIONS ${inspect_failure_definitions})
endfunction()

crossgl_add_package_inspect_json_failure_schema_test(
  NAME cglc_package_inspect_json_schema_missing_package_failure
  FAILURE_KIND missing-package
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/missing-package-inspect-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|packageFormat=null|summary=null|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.inspect.missing-package"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_inspect_json_failure_schema_test(
  NAME cglc_package_inspect_json_schema_non_directory_package_failure
  FAILURE_KIND non-directory-package
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/non-directory-package-inspect-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|packageFormat=null|summary=null|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.inspect.unsupported-format"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_inspect_json_failure_schema_test(
  NAME cglc_package_inspect_json_schema_stored_zip_package_failure
  FAILURE_KIND stored-zip-package
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/stored-zip-package-inspect-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|packageFormat=null|summary=null|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.inspect.unsupported-format"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_inspect_json_failure_schema_test(
  NAME cglc_package_inspect_json_schema_invalid_json_metadata_failure
  FAILURE_KIND invalid-json-metadata
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/invalid-json-metadata-inspect-schema.cglb
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|packageFormat=null|summary=null|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.inspect.invalid-json"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")

crossgl_add_package_inspect_json_failure_schema_test(
  NAME cglc_package_inspect_json_schema_null_artifact_requirements_failure
  FAILURE_KIND malformed-package-artifact-requirements
  TARGET directx
  INPUT ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/null-artifact-requirements-inspect-schema.cglb
  MANIFEST_MUTATION_KIND null-package-artifact-requirements
  EXPECTED_JSON_FIELDS
    "schemaVersion=1|success=false|packageFormat=null|summary=null|diagnosticCounts.error=1|diagnostics.0.severity=error|diagnostics.0.code=package.inspect.invalid-manifest|diagnostics.0.message=package manifest packageArtifactRequirements is invalid"
  EXPECTED_JSON_ARRAY_LENGTHS
    "diagnostics=1")
