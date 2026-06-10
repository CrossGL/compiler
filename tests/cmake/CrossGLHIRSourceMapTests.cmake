if(CROSSGL_RUN_HIR_SOURCE_MAP_RESOURCE_ACCESS_TEST)
  if(NOT DEFINED CGLC)
    message(FATAL_ERROR "CGLC is required")
  endif()
  if(NOT DEFINED PYTHON3_EXECUTABLE)
    message(FATAL_ERROR "PYTHON3_EXECUTABLE is required")
  endif()
  if(NOT DEFINED JSON_SCHEMA_VALIDATOR)
    message(FATAL_ERROR "JSON_SCHEMA_VALIDATOR is required")
  endif()
  if(NOT DEFINED HIR_SOURCE_MAP_JSON_SCHEMA)
    message(FATAL_ERROR "HIR_SOURCE_MAP_JSON_SCHEMA is required")
  endif()
  if(NOT DEFINED STORAGE_IMAGE_FIXTURE)
    message(FATAL_ERROR "STORAGE_IMAGE_FIXTURE is required")
  endif()
  if(NOT DEFINED OUTPUT_JSON)
    message(FATAL_ERROR "OUTPUT_JSON is required")
  endif()

  function(crossgl_hir_source_map_json_path_to_list path out_var)
    string(REPLACE "." ";" path_list "${path}")
    set(${out_var} ${path_list} PARENT_SCOPE)
  endfunction()

  function(crossgl_hir_source_map_normalize_expected_json_value value out_var)
    if("${value}" STREQUAL "true")
      set(normalized ON)
    elseif("${value}" STREQUAL "false")
      set(normalized OFF)
    elseif("${value}" STREQUAL "null")
      set(normalized "")
    else()
      set(normalized "${value}")
    endif()
    set(${out_var} "${normalized}" PARENT_SCOPE)
  endfunction()

  function(crossgl_hir_source_map_expect_json_field json path expected)
    crossgl_hir_source_map_json_path_to_list("${path}" json_path)
    string(JSON actual ERROR_VARIABLE json_error GET "${json}" ${json_path})
    if(NOT json_error STREQUAL "NOTFOUND")
      message(FATAL_ERROR
        "expected JSON field '${path}', but lookup failed: ${json_error}. "
        "Output: ${json}")
    endif()
    crossgl_hir_source_map_normalize_expected_json_value(
      "${expected}" normalized_expected)
    if(NOT actual STREQUAL "${normalized_expected}")
      message(FATAL_ERROR
        "expected JSON field '${path}' to equal '${expected}', got "
        "'${actual}'. Output: ${json}")
    endif()
  endfunction()

  function(crossgl_hir_source_map_expect_json_field_greater_than json path
           minimum)
    crossgl_hir_source_map_json_path_to_list("${path}" json_path)
    string(JSON actual ERROR_VARIABLE json_error GET "${json}" ${json_path})
    if(NOT json_error STREQUAL "NOTFOUND")
      message(FATAL_ERROR
        "expected JSON field '${path}', but lookup failed: ${json_error}. "
        "Output: ${json}")
    endif()
    if(NOT "${actual}" MATCHES "^[0-9]+$")
      message(FATAL_ERROR
        "expected JSON path '${path}' to be an unsigned integer, got "
        "'${actual}'. Output: ${json}")
    endif()
    if(NOT "${actual}" GREATER "${minimum}")
      message(FATAL_ERROR
        "expected JSON field '${path}' to be greater than '${minimum}', "
        "got '${actual}'. Output: ${json}")
    endif()
  endfunction()

  execute_process(
    COMMAND "${CGLC}" dump-ir "${STORAGE_IMAGE_FIXTURE}"
            --stage hir-source-map
            --hir-source-map-schema-version 8
            --source-map-records
            --source-map-resource-record-kind access
            --source-map-record-limit 20
    RESULT_VARIABLE result
    OUTPUT_VARIABLE stdout
    ERROR_VARIABLE stderr)
  if(NOT result EQUAL 0)
    message(FATAL_ERROR
      "expected HIR source-map dump to succeed, got ${result}. "
      "Stdout: ${stdout} Stderr: ${stderr}")
  endif()

  file(WRITE "${OUTPUT_JSON}" "${stdout}")
  execute_process(
    COMMAND "${PYTHON3_EXECUTABLE}" "${JSON_SCHEMA_VALIDATOR}"
            --schema "${HIR_SOURCE_MAP_JSON_SCHEMA}"
            --instance "${OUTPUT_JSON}"
    RESULT_VARIABLE schema_result
    OUTPUT_VARIABLE schema_stdout
    ERROR_VARIABLE schema_stderr)
  if(NOT schema_result EQUAL 0)
    message(FATAL_ERROR
      "HIR source-map schema validation failed. "
      "Stdout: ${schema_stdout} Stderr: ${schema_stderr} JSON: ${stdout}")
  endif()

  crossgl_hir_source_map_expect_json_field("${stdout}" "schemaVersion" "8")
  crossgl_hir_source_map_expect_json_field(
    "${stdout}" "filters.resourceRecordKind" "access")
  crossgl_hir_source_map_expect_json_field(
    "${stdout}" "records.enabled" "true")
  crossgl_hir_source_map_expect_json_field_greater_than(
    "${stdout}" "records.emittedCount" "1")
  crossgl_hir_source_map_expect_json_field(
    "${stdout}" "categoryCounts.resourceRecordKinds.0.name" "access")
  crossgl_hir_source_map_expect_json_field(
    "${stdout}" "categoryCounts.resourceKinds.0.name" "storage_image")

  string(JSON record_count ERROR_VARIABLE records_error LENGTH "${stdout}"
         records items)
  if(NOT records_error STREQUAL "NOTFOUND")
    message(FATAL_ERROR
      "expected HIR source-map records.items array, but lookup failed: "
      "${records_error}. Output: ${stdout}")
  endif()

  set(found_store OFF)
  set(found_load OFF)
  if(record_count GREATER 0)
    math(EXPR last_record_index "${record_count} - 1")
    foreach(index RANGE 0 ${last_record_index})
      string(JSON record_kind ERROR_VARIABLE record_kind_error GET "${stdout}"
             records items ${index} recordKind)
      if(NOT record_kind_error STREQUAL "NOTFOUND")
        message(FATAL_ERROR
          "failed to read records.items.${index}.recordKind: "
          "${record_kind_error}. Output: ${stdout}")
      endif()
      if(NOT record_kind STREQUAL "resource")
        continue()
      endif()

      string(JSON operation ERROR_VARIABLE operation_error GET "${stdout}"
             records items ${index} resource operation)
      if(NOT operation_error STREQUAL "NOTFOUND")
        message(FATAL_ERROR
          "failed to read records.items.${index}.resource.operation: "
          "${operation_error}. Output: ${stdout}")
      endif()

      if(operation STREQUAL "imageStore")
        crossgl_hir_source_map_expect_json_field("${stdout}"
          "records.items.${index}.resource.resourceRecordKind" "access")
        crossgl_hir_source_map_expect_json_field("${stdout}"
          "records.items.${index}.resource.function" "main")
        crossgl_hir_source_map_expect_json_field("${stdout}"
          "records.items.${index}.resource.accessKind" "store")
        crossgl_hir_source_map_expect_json_field("${stdout}"
          "records.items.${index}.resource.resourceKind" "storage_image")
        if(NOT found_store)
          crossgl_hir_source_map_expect_json_field("${stdout}"
            "records.items.${index}.resource.resourceName" "colorImage")
          set(found_store ON)
        endif()
      elseif(operation STREQUAL "imageLoad")
        crossgl_hir_source_map_expect_json_field("${stdout}"
          "records.items.${index}.resource.resourceRecordKind" "access")
        crossgl_hir_source_map_expect_json_field("${stdout}"
          "records.items.${index}.resource.function" "main")
        crossgl_hir_source_map_expect_json_field("${stdout}"
          "records.items.${index}.resource.accessKind" "load")
        crossgl_hir_source_map_expect_json_field("${stdout}"
          "records.items.${index}.resource.resourceKind" "storage_image")
        if(NOT found_load)
          crossgl_hir_source_map_expect_json_field("${stdout}"
            "records.items.${index}.resource.resourceName" "colorImage")
          set(found_load ON)
        endif()
      endif()
    endforeach()
  endif()

  if(NOT found_store)
    message(FATAL_ERROR
      "expected a storage image imageStore access record with contextual "
      "resource fields. Output: ${stdout}")
  endif()
  if(NOT found_load)
    message(FATAL_ERROR
      "expected a storage image imageLoad access record with contextual "
      "resource fields. Output: ${stdout}")
  endif()
  return()
endif()

set(CROSSGL_HIR_SOURCE_MAP_TEST_SCRIPT "${CMAKE_CURRENT_LIST_FILE}")

add_test(NAME cglc_hir_source_map_v8_storage_image_access_records
  COMMAND ${CMAKE_COMMAND}
    -D CROSSGL_RUN_HIR_SOURCE_MAP_RESOURCE_ACCESS_TEST=ON
    -D "CGLC=$<TARGET_FILE:cglc>"
    -D "PYTHON3_EXECUTABLE=${CROSSGL_PYTHON3}"
    -D "JSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py"
    -D "HIR_SOURCE_MAP_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/hir-source-map-v8.schema.json"
    -D "STORAGE_IMAGE_FIXTURE=${CMAKE_CURRENT_SOURCE_DIR}/tests/optimizer/fixtures/StorageImageOptimizerBoundaryShader.cgl"
    -D "OUTPUT_JSON=${CMAKE_CURRENT_BINARY_DIR}/cglc-hir-source-map-v8-storage-image-access-records.json"
    -P "${CROSSGL_HIR_SOURCE_MAP_TEST_SCRIPT}")
