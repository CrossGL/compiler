set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/fixtures/MinimalComputeShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"1,1,1\""
  "crossgl_source_location_fact_source_file = true"
  "crossgl_source_location_fact_shader_module = true"
  "crossgl_source_location_fact_compute_stage = true"
  "crossgl_source_location_fact_entry_point = true"
  "crossgl_source_location_fact_layout_local_size = true"
  "crossgl_source_location_fact_return_statement = true"
  "crossgl_type_fact_void_entry_point = true"
  "crossgl_resource_count = 0"
  "crossgl_resource_fact_descriptors_empty = true"
  "crossgl_resource_fact_storage_buffers_empty = true"
  "crossgl_resource_fact_storage_images_empty = true"
  "crossgl_resource_fact_textures_empty = true"
  "crossgl_resource_fact_samplers_empty = true"
  "crossgl_target_independent_resource_metadata_empty = true"
  "crossgl_resource_metadata = \"target-independent:none\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/fixtures/MinimalComputeShader.cgl"
  "crossgl_stage"
  "compute"
  "crossgl_entry_point"
  "crossgl_local_size"
  "1,1,1"
  "crossgl_source_location_fact_source_file"
  "crossgl_source_location_fact_shader_module"
  "crossgl_source_location_fact_compute_stage"
  "crossgl_source_location_fact_entry_point"
  "crossgl_source_location_fact_layout_local_size"
  "crossgl_source_location_fact_return_statement"
  "crossgl_type_fact_void_entry_point"
  "crossgl_resource_count"
  "crossgl_resource_fact_descriptors_empty"
  "crossgl_resource_fact_storage_buffers_empty"
  "crossgl_resource_fact_storage_images_empty"
  "crossgl_resource_fact_textures_empty"
  "crossgl_resource_fact_samplers_empty"
  "crossgl_target_independent_resource_metadata_empty"
  "target-independent:none"
  "crossgl_real_mlir_smoke")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_REQUIRED_MARKERS
  "crossgl_fixture = \"tests/fixtures/StorageBufferComputeShader.cgl\""
  "crossgl_stage = \"compute\""
  "crossgl_entry_point = \"main\""
  "crossgl_local_size = \"1,1,1\""
  "crossgl_source_location_fact_source_file = true"
  "crossgl_source_location_fact_shader_module = true"
  "crossgl_source_location_fact_compute_stage = true"
  "crossgl_source_location_fact_entry_point = true"
  "crossgl_source_location_fact_layout_local_size = true"
  "crossgl_source_location_fact_storage_buffer_declaration = true"
  "crossgl_source_location_fact_local_variable_declarations = true"
  "crossgl_source_location_fact_scalar_expression_statements = true"
  "crossgl_source_location_fact_storage_buffer_write = true"
  "crossgl_source_location_fact_return_statement = true"
  "crossgl_type_fact_void_entry_point = true"
  "crossgl_type_fact_float_scalar = true"
  "crossgl_type_fact_float_pointer_storage_buffer = true"
  "crossgl_type_fact_storage_buffer_element_type = true"
  "crossgl_type_fact_binary_expression_result_types = true"
  "crossgl_resource_count = 1"
  "crossgl_descriptor_count = 1"
  "crossgl_descriptor_0_stage = \"compute\""
  "crossgl_descriptor_0_name = \"values\""
  "crossgl_descriptor_0_kind = \"storageBuffer\""
  "crossgl_descriptor_0_set = 0"
  "crossgl_descriptor_0_binding = 0"
  "crossgl_storage_buffer_count = 1"
  "crossgl_storage_buffer_0_name = \"values\""
  "crossgl_storage_buffer_0_type = \"float*\""
  "crossgl_storage_buffer_0_element_type = \"float\""
  "crossgl_storage_buffer_0_address_space = \"storage\""
  "crossgl_storage_buffer_0_write_access = true"
  "crossgl_resource_fact_storage_images_empty = true"
  "crossgl_resource_fact_textures_empty = true"
  "crossgl_resource_fact_samplers_empty = true"
  "crossgl_target_independent_resource_metadata_count = 1"
  "crossgl_target_independent_resource_metadata_0_stage = \"compute\""
  "crossgl_target_independent_resource_metadata_0_name = \"values\""
  "crossgl_target_independent_resource_metadata_0_kind = \"storageBuffer\""
  "crossgl_target_independent_resource_metadata_0_source_type = \"float*\""
  "crossgl_target_independent_resource_metadata_0_element_type = \"float\""
  "crossgl_target_independent_resource_metadata_0_address_space = \"storage\""
  "crossgl_target_independent_resource_metadata_0_access = \"read_write\""
  "crossgl_target_independent_resource_metadata_0_set = 0"
  "crossgl_target_independent_resource_metadata_0_binding = 0"
  "crossgl_target_independent_resource_metadata_0_target_independent = true"
  "crossgl_resource_metadata = \"target-independent:storageBuffer:compute:values:set=0:binding=0:type=float*:element=float:addressSpace=storage:access=read_write\""
  "crossgl_real_mlir_smoke = true")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_OUTPUT_MARKERS
  "crossgl_fixture"
  "tests/fixtures/StorageBufferComputeShader.cgl"
  "crossgl_stage"
  "compute"
  "crossgl_entry_point"
  "crossgl_local_size"
  "1,1,1"
  "crossgl_source_location_fact_storage_buffer_declaration"
  "crossgl_source_location_fact_storage_buffer_write"
  "crossgl_type_fact_float_pointer_storage_buffer"
  "crossgl_resource_count"
  "crossgl_descriptor_count"
  "crossgl_descriptor_0_name"
  "values"
  "crossgl_descriptor_0_kind"
  "storageBuffer"
  "crossgl_storage_buffer_count"
  "crossgl_storage_buffer_0_type"
  "float*"
  "crossgl_storage_buffer_0_element_type"
  "float"
  "crossgl_storage_buffer_0_address_space"
  "storage"
  "crossgl_storage_buffer_0_write_access"
  "crossgl_target_independent_resource_metadata_count"
  "crossgl_target_independent_resource_metadata_0_access"
  "read_write"
  "target-independent:storageBuffer:compute:values"
  "crossgl_real_mlir_smoke")

if(DEFINED CROSSGL_MLIR_EXPERIMENT_VERIFY_SCRIPT)
  foreach(required_var IN ITEMS
      MLIR_OPT
      INPUT_MLIR
      BUILD_DIR
      EXPERIMENT_TARGET
      REQUIRED_MARKERS_VAR
      OUTPUT_MARKERS_VAR)
    if(NOT DEFINED ${required_var} OR "${${required_var}}" STREQUAL "")
      message(FATAL_ERROR
        "CrossGL MLIR experiment verifier missing ${required_var}")
    endif()
  endforeach()
  foreach(marker_var IN ITEMS REQUIRED_MARKERS_VAR OUTPUT_MARKERS_VAR)
    if(NOT DEFINED ${${marker_var}})
      message(FATAL_ERROR
        "CrossGL MLIR experiment verifier marker list ${${marker_var}} missing")
    endif()
  endforeach()

  if(NOT EXISTS "${INPUT_MLIR}")
    message(FATAL_ERROR
      "CrossGL MLIR experiment verifier input missing: ${INPUT_MLIR}")
  endif()
  file(READ "${INPUT_MLIR}" input_mlir)
  foreach(required_marker IN LISTS ${REQUIRED_MARKERS_VAR})
    string(FIND "${input_mlir}" "${required_marker}" marker_index)
    if(marker_index EQUAL -1)
      message(FATAL_ERROR
        "CrossGL MLIR experiment verifier input ${INPUT_MLIR} is missing "
        "required real-MLIR fact-preservation marker ${required_marker}")
    endif()
  endforeach()
  foreach(forbidden_marker IN ITEMS
      "CrossGL pseudo-MLIR"
      "crossgl.real_mlir = \"false\""
      "not a registered MLIR dialect")
    string(FIND "${input_mlir}" "${forbidden_marker}" marker_index)
    if(NOT marker_index EQUAL -1)
      message(FATAL_ERROR
        "CrossGL MLIR experiment verifier input ${INPUT_MLIR} contains "
        "pseudo-MLIR marker ${forbidden_marker}")
    endif()
  endforeach()

  set(build_command
    "${CMAKE_COMMAND}"
    --build "${BUILD_DIR}"
    --target "${EXPERIMENT_TARGET}")
  if(DEFINED BUILD_CONFIG AND NOT "${BUILD_CONFIG}" STREQUAL "")
    list(APPEND build_command --config "${BUILD_CONFIG}")
  endif()
  execute_process(
    COMMAND ${build_command}
    RESULT_VARIABLE build_result
    OUTPUT_VARIABLE build_output
    ERROR_VARIABLE build_error)
  if(NOT build_result EQUAL 0)
    message(FATAL_ERROR
      "failed to build ${EXPERIMENT_TARGET}; stdout: ${build_output}; "
      "stderr: ${build_error}")
  endif()

  execute_process(
    COMMAND "${MLIR_OPT}" --verify-diagnostics "${INPUT_MLIR}"
    RESULT_VARIABLE mlir_result
    OUTPUT_VARIABLE mlir_output
    ERROR_VARIABLE mlir_error)
  if(NOT mlir_result EQUAL 0)
    message(FATAL_ERROR
      "mlir-opt verifier failed for ${INPUT_MLIR}; stdout: ${mlir_output}; "
      "stderr: ${mlir_error}")
  endif()
  foreach(output_marker IN LISTS ${OUTPUT_MARKERS_VAR})
    string(FIND "${mlir_output}" "${output_marker}" marker_index)
    if(marker_index EQUAL -1)
      message(FATAL_ERROR
        "mlir-opt output did not preserve real-MLIR fact-preservation "
        "marker ${output_marker}; stdout: ${mlir_output}; stderr: ${mlir_error}")
    endif()
  endforeach()

  message(STATUS
    "CrossGL MLIR experiment verifier passed for ${INPUT_MLIR}")
  return()
endif()

function(crossgl_mlir_json_string out value)
  string(REPLACE "\\" "\\\\" escaped "${value}")
  string(REPLACE "\"" "\\\"" escaped "${escaped}")
  string(REPLACE "\n" "\\n" escaped "${escaped}")
  set(${out} "\"${escaped}\"" PARENT_SCOPE)
endfunction()

function(crossgl_mlir_json_string_or_null out value)
  if("${value}" STREQUAL "")
    set(${out} "null" PARENT_SCOPE)
  else()
    crossgl_mlir_json_string(json_value "${value}")
    set(${out} "${json_value}" PARENT_SCOPE)
  endif()
endfunction()

function(crossgl_mlir_json_bool out value)
  if(value)
    set(${out} "true" PARENT_SCOPE)
  else()
    set(${out} "false" PARENT_SCOPE)
  endif()
endfunction()

function(crossgl_mlir_json_string_list out)
  set(json "[")
  set(separator "")
  foreach(value IN LISTS ARGN)
    crossgl_mlir_json_string(json_value "${value}")
    string(APPEND json "${separator}${json_value}")
    set(separator ", ")
  endforeach()
  string(APPEND json "]")
  set(${out} "${json}" PARENT_SCOPE)
endfunction()

set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_FIXTURE
  "tests/fixtures/MinimalComputeShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/minimal_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_TEST
  "cglc_mlir_experiment_minimal_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_FIXTURE
  "tests/fixtures/StorageBufferComputeShader.cgl")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT_RELATIVE
  "tests/fixtures/mlir/storage_buffer_compute_builtin_module.mlir")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT_RELATIVE}")
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_TEST
  "cglc_mlir_experiment_storage_buffer_compute_verifier")
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORDS
  "minimal_compute|${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_MINIMAL_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_OUTPUT_MARKERS|minimal compute"
  "storage_buffer_compute|${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_TEST}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_FIXTURE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT_RELATIVE}|${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT}|CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_REQUIRED_MARKERS|CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_OUTPUT_MARKERS|storage-buffer compute")
set(CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE
  "${CMAKE_CURRENT_BINARY_DIR}/mlir/optional_tool_evidence.v0.json")
set(CROSSGL_MLIR_FIXTURE_PARITY_REPORT_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_mlir_fixture_parity_report.py")
set(CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_mlir_package_sidecar_boundary.py")
set(CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_mlir_optional_tool_evidence.py")
set(CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_mlir_textual_dialect_projection.py")
set(CROSSGL_MLIR_OP_TYPE_CATALOG_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_mlir_op_type_catalog.py")
set(CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG
  "experimental/mlir/source_resource_catalog.v0.json")
set(CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_CHECKER
  "tools/check_mlir_source_resource_catalog.py")
set(CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_SCRIPT
  "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_CHECKER}")
set(CROSSGL_MLIR_SOURCE_RESOURCE_PRESERVATION_SECTION
  "sourceResourceEntrypointPreservation")
set(CROSSGL_MLIR_FIXTURE_PARITY_REPORT_TESTS
  cglc_mlir_fixture_parity_report_compile
  cglc_mlir_fixture_parity_report
  cglc_mlir_fixture_parity_report_self_test)
set(CROSSGL_MLIR_FIXTURE_HIR_DUMP_PARITY_TESTS
  cglc_mlir_fixture_hir_dump_parity)
set(CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_TESTS
  cglc_mlir_package_sidecar_boundary_compile
  cglc_mlir_package_sidecar_boundary
  cglc_mlir_package_sidecar_boundary_self_test)
set(CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_TESTS
  cglc_mlir_optional_tool_evidence_compile
  cglc_mlir_optional_tool_evidence
  cglc_mlir_optional_tool_evidence_self_test)
set(CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_TESTS
  cglc_mlir_textual_dialect_projection_compile
  cglc_mlir_textual_dialect_projection
  cglc_mlir_textual_dialect_projection_self_test)
set(CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_TESTS
  cglc_mlir_source_resource_catalog_compile
  cglc_mlir_source_resource_catalog
  cglc_mlir_source_resource_catalog_self_test)
set(CROSSGL_MLIR_OP_TYPE_CATALOG_TESTS
  cglc_mlir_op_type_catalog_compile
  cglc_mlir_op_type_catalog
  cglc_mlir_op_type_catalog_self_test)

if(CROSSGL_PYTHON3)
  add_test(NAME cglc_mlir_fixture_parity_report_compile
    COMMAND "${CROSSGL_PYTHON3}" -m py_compile
      "${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_SCRIPT}")
  add_test(NAME cglc_mlir_fixture_parity_report
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}")
  add_test(NAME cglc_mlir_fixture_parity_report_self_test
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_SCRIPT}"
      --self-test)
  add_test(NAME cglc_mlir_fixture_hir_dump_parity
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}"
      --cglc $<TARGET_FILE:cglc>
      --hir-dump-parity)
  add_test(NAME cglc_mlir_package_sidecar_boundary_compile
    COMMAND "${CROSSGL_PYTHON3}" -m py_compile
      "${CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_SCRIPT}")
  add_test(NAME cglc_mlir_package_sidecar_boundary
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}"
      --cglc $<TARGET_FILE:cglc>)
  add_test(NAME cglc_mlir_package_sidecar_boundary_self_test
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_SCRIPT}"
      --self-test)
  add_test(NAME cglc_mlir_optional_tool_evidence_compile
    COMMAND "${CROSSGL_PYTHON3}" -m py_compile
      "${CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_SCRIPT}")
  add_test(NAME cglc_mlir_optional_tool_evidence
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}"
      --evidence "${CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE}")
  add_test(NAME cglc_mlir_optional_tool_evidence_self_test
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_SCRIPT}"
      --self-test)
  add_test(NAME cglc_mlir_textual_dialect_projection_compile
    COMMAND "${CROSSGL_PYTHON3}" -m py_compile
      "${CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_SCRIPT}")
  add_test(NAME cglc_mlir_textual_dialect_projection
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}")
  add_test(NAME cglc_mlir_textual_dialect_projection_self_test
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_SCRIPT}"
      --self-test)
  add_test(NAME cglc_mlir_source_resource_catalog_compile
    COMMAND "${CROSSGL_PYTHON3}" -m py_compile
      "${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_SCRIPT}")
  add_test(NAME cglc_mlir_source_resource_catalog
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}")
  add_test(NAME cglc_mlir_source_resource_catalog_self_test
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_SCRIPT}"
      --self-test)
  add_test(NAME cglc_mlir_op_type_catalog_compile
    COMMAND "${CROSSGL_PYTHON3}" -m py_compile
      "${CROSSGL_MLIR_OP_TYPE_CATALOG_SCRIPT}")
  add_test(NAME cglc_mlir_op_type_catalog
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_OP_TYPE_CATALOG_SCRIPT}"
      --root "${CMAKE_CURRENT_SOURCE_DIR}")
  add_test(NAME cglc_mlir_op_type_catalog_self_test
    COMMAND "${CROSSGL_PYTHON3}"
      "${CROSSGL_MLIR_OP_TYPE_CATALOG_SCRIPT}"
      --self-test)
  set_tests_properties(${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only"
    PROCESSORS 1)
  set_tests_properties(${CROSSGL_MLIR_FIXTURE_HIR_DUMP_PARITY_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only;hir-parity"
    PROCESSORS 1)
  set_tests_properties(${CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only"
    PROCESSORS 1)
  set_tests_properties(${CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only;mlir-tool-evidence"
    PROCESSORS 1)
  set_tests_properties(${CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only;mlir-textual-dialect-projection"
    PROCESSORS 1)
  set_tests_properties(${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only;mlir-source-resource-catalog"
    PROCESSORS 1)
  set_tests_properties(${CROSSGL_MLIR_OP_TYPE_CATALOG_TESTS} PROPERTIES
    LABELS "mlir;optional-mlir;report-only;mlir-op-type-catalog"
    PROCESSORS 1)
else()
  foreach(CROSSGL_MLIR_FIXTURE_PARITY_REPORT_TEST IN LISTS
      CROSSGL_MLIR_FIXTURE_PARITY_REPORT_TESTS)
    add_test(NAME "${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR fixture parity report requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_FIXTURE_PARITY_REPORT_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
  foreach(CROSSGL_MLIR_FIXTURE_HIR_DUMP_PARITY_TEST IN LISTS
      CROSSGL_MLIR_FIXTURE_HIR_DUMP_PARITY_TESTS)
    add_test(NAME "${CROSSGL_MLIR_FIXTURE_HIR_DUMP_PARITY_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR fixture HIR dump parity requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_FIXTURE_HIR_DUMP_PARITY_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;hir-parity;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
  foreach(CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_TEST IN LISTS
      CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_TESTS)
    add_test(NAME "${CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR package sidecar boundary requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_PACKAGE_SIDECAR_BOUNDARY_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
  foreach(CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_TEST IN LISTS
      CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_TESTS)
    add_test(NAME "${CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR optional-tool evidence requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_OPTIONAL_TOOL_EVIDENCE_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
  foreach(CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_TEST IN LISTS
      CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_TESTS)
    add_test(NAME "${CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR textual dialect projection requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_TEXTUAL_DIALECT_PROJECTION_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
  foreach(CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_TEST IN LISTS
      CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_TESTS)
    add_test(NAME "${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR source/resource catalog requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
  foreach(CROSSGL_MLIR_OP_TYPE_CATALOG_TEST IN LISTS
      CROSSGL_MLIR_OP_TYPE_CATALOG_TESTS)
    add_test(NAME "${CROSSGL_MLIR_OP_TYPE_CATALOG_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR op/type catalog requires Python 3")
    set_tests_properties("${CROSSGL_MLIR_OP_TYPE_CATALOG_TEST}"
      PROPERTIES
        LABELS "mlir;optional-mlir;report-only;python-unavailable"
        SKIP_REGULAR_EXPRESSION "^SKIP:")
  endforeach()
endif()

set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS "")
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_FOUND FALSE)
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_PATH "")
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIND_PROGRAM_ATTEMPTED FALSE)
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_VERSION_PROBE_ATTEMPTED FALSE)
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_DISCOVERY_STATUS
  "not-run-toolchain-incomplete")
if(NOT CROSSGL_ENABLE_MLIR_EXPERIMENTAL)
  list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
    "CROSSGL_ENABLE_MLIR_EXPERIMENTAL=OFF")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS "default-off")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REASON
    "CROSSGL_ENABLE_MLIR_EXPERIMENTAL=OFF; real MLIR verifier disabled by default")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_DISCOVERY_STATUS
    "not-run-default-off")
else()
  if(NOT MLIR_FOUND)
    list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
      "MLIR_FOUND=FALSE")
  endif()
  if(NOT TARGET crossgl_mlir_experiment)
    list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
      "target crossgl_mlir_experiment not created")
  endif()
  foreach(CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORD IN LISTS
      CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORDS)
    string(REPLACE "|" ";" CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS
      "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORD}")
    list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 2
      CROSSGL_MLIR_EXPERIMENT_RECORD_FIXTURE)
    list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 3
      CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_RELATIVE)
    list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 4
      CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT)
    if(NOT EXISTS
        "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_RECORD_FIXTURE}")
      list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
        "${CROSSGL_MLIR_EXPERIMENT_RECORD_FIXTURE} fixture missing")
    endif()
    if(NOT EXISTS "${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT}")
      list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
        "real MLIR verifier input missing: ${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_RELATIVE}")
    endif()
  endforeach()

  if(NOT CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS)
    set(CROSSGL_MLIR_OPT_HINTS "")
    set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIND_PROGRAM_ATTEMPTED TRUE)
    foreach(CROSSGL_MLIR_OPT_HINT_VAR IN ITEMS MLIR_TOOLS_DIR LLVM_TOOLS_BINARY_DIR)
      if(DEFINED ${CROSSGL_MLIR_OPT_HINT_VAR}
          AND NOT "${${CROSSGL_MLIR_OPT_HINT_VAR}}" STREQUAL "")
        list(APPEND CROSSGL_MLIR_OPT_HINTS
          "${${CROSSGL_MLIR_OPT_HINT_VAR}}")
      endif()
    endforeach()
    if(CROSSGL_MLIR_OPT_HINTS)
      find_program(CROSSGL_MLIR_OPT
        NAMES mlir-opt
        HINTS ${CROSSGL_MLIR_OPT_HINTS}
        NO_CACHE
        DOC "MLIR optimizer/verifier used by optional CrossGL MLIR experiment tests")
    else()
      find_program(CROSSGL_MLIR_OPT
        NAMES mlir-opt
        NO_CACHE
        DOC "MLIR optimizer/verifier used by optional CrossGL MLIR experiment tests")
    endif()
    if(CROSSGL_MLIR_OPT)
      set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_FOUND TRUE)
      set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_PATH "${CROSSGL_MLIR_OPT}")
      set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_VERSION_PROBE_ATTEMPTED TRUE)
      execute_process(
        COMMAND "${CROSSGL_MLIR_OPT}" --version
        RESULT_VARIABLE CROSSGL_MLIR_OPT_VERSION_RESULT
        OUTPUT_VARIABLE CROSSGL_MLIR_OPT_VERSION_OUTPUT
        ERROR_VARIABLE CROSSGL_MLIR_OPT_VERSION_ERROR)
      if(CROSSGL_MLIR_OPT_VERSION_RESULT EQUAL 0)
        string(STRIP "${CROSSGL_MLIR_OPT_VERSION_OUTPUT}"
          CROSSGL_MLIR_OPT_VERSION_OUTPUT)
        set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS "toolchain-available")
        set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_DISCOVERY_STATUS
          "available")
      else()
        set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_DISCOVERY_STATUS
          "probe-failed")
        list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
          "mlir-opt --version probe failed")
      endif()
    else()
      set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_DISCOVERY_STATUS "not-found")
      list(APPEND CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS
        "mlir-opt not found")
    endif()
  endif()

  if(CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS)
    string(REPLACE ";" ", " CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REASON
      "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS}")
    set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS "toolchain-unavailable")
  endif()
endif()

set(CROSSGL_MLIR_EXPERIMENT_TARGET_CREATED FALSE)
if(TARGET crossgl_mlir_experiment)
  set(CROSSGL_MLIR_EXPERIMENT_TARGET_CREATED TRUE)
endif()
set(CROSSGL_MLIR_EXPERIMENT_OPTION_DEFAULT "OFF")
if(CROSSGL_ENABLE_MLIR_EXPERIMENTAL)
  set(CROSSGL_MLIR_EXPERIMENT_OPTION_ACTUAL "ON")
else()
  set(CROSSGL_MLIR_EXPERIMENT_OPTION_ACTUAL "OFF")
endif()
set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_PRESENT FALSE)
if(EXISTS "${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT}")
  set(CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_PRESENT TRUE)
endif()
set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT_PRESENT FALSE)
if(EXISTS "${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT}")
  set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT_PRESENT TRUE)
endif()
if(CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS STREQUAL "toolchain-available")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REGISTERED FALSE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REGEX "")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_LABELS_JSON
    "[\"mlir\", \"optional-mlir\", \"mlir-tool-available\"]")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_EVIDENCE_REASON "")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_REGISTRATION_MODE "executable")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_INVOKES_MLIR_OPT TRUE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_USES_VERIFY_DIAGNOSTICS TRUE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_BUILDS_TARGET TRUE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_BUILD_TARGET
    "crossgl_mlir_experiment")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_REQUIRED_FILES
    "${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE}")
  set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFIER_REQUIRED_FILES
    "${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT_RELATIVE}")
else()
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REGISTERED TRUE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REGEX "^SKIP:")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_LABELS_JSON
    "[\"mlir\", \"optional-mlir\", \"mlir-tool-unavailable\"]")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_EVIDENCE_REASON
    "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REASON}")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_REGISTRATION_MODE "skipped")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_INVOKES_MLIR_OPT FALSE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_USES_VERIFY_DIAGNOSTICS FALSE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_BUILDS_TARGET FALSE)
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_BUILD_TARGET "")
  set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_REQUIRED_FILES "")
  set(CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFIER_REQUIRED_FILES "")
endif()
crossgl_mlir_json_bool(CROSSGL_MLIR_OPTION_ENABLED_JSON
  "${CROSSGL_ENABLE_MLIR_EXPERIMENTAL}")
crossgl_mlir_json_bool(CROSSGL_MLIR_FOUND_JSON "${MLIR_FOUND}")
crossgl_mlir_json_bool(CROSSGL_MLIR_TARGET_CREATED_JSON
  "${CROSSGL_MLIR_EXPERIMENT_TARGET_CREATED}")
crossgl_mlir_json_bool(CROSSGL_MLIR_VERIFY_INPUT_PRESENT_JSON
  "${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_PRESENT}")
crossgl_mlir_json_bool(CROSSGL_MLIR_STORAGE_VERIFY_INPUT_PRESENT_JSON
  "${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT_PRESENT}")
crossgl_mlir_json_bool(CROSSGL_MLIR_TOOL_FOUND_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_FOUND}")
crossgl_mlir_json_bool(CROSSGL_MLIR_SKIP_REGISTERED_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REGISTERED}")
crossgl_mlir_json_bool(CROSSGL_MLIR_FIND_PROGRAM_ATTEMPTED_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIND_PROGRAM_ATTEMPTED}")
crossgl_mlir_json_bool(CROSSGL_MLIR_VERSION_PROBE_ATTEMPTED_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_VERSION_PROBE_ATTEMPTED}")
crossgl_mlir_json_bool(CROSSGL_MLIR_REGISTRATION_INVOKES_MLIR_OPT_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_INVOKES_MLIR_OPT}")
crossgl_mlir_json_bool(CROSSGL_MLIR_REGISTRATION_USES_VERIFY_DIAGNOSTICS_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_USES_VERIFY_DIAGNOSTICS}")
crossgl_mlir_json_bool(CROSSGL_MLIR_REGISTRATION_BUILDS_TARGET_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_BUILDS_TARGET}")
crossgl_mlir_json_string(CROSSGL_MLIR_OPTION_DEFAULT_JSON
  "${CROSSGL_MLIR_EXPERIMENT_OPTION_DEFAULT}")
crossgl_mlir_json_string(CROSSGL_MLIR_OPTION_ACTUAL_JSON
  "${CROSSGL_MLIR_EXPERIMENT_OPTION_ACTUAL}")
crossgl_mlir_json_string(CROSSGL_MLIR_STATUS_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS}")
crossgl_mlir_json_string(CROSSGL_MLIR_TOOL_DISCOVERY_STATUS_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_DISCOVERY_STATUS}")
crossgl_mlir_json_string(CROSSGL_MLIR_REGISTRATION_MODE_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_REGISTRATION_MODE}")
crossgl_mlir_json_string_or_null(CROSSGL_MLIR_TOOL_PATH_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_TOOL_PATH}")
crossgl_mlir_json_string_or_null(CROSSGL_MLIR_REGISTRATION_BUILD_TARGET_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_BUILD_TARGET}")
crossgl_mlir_json_string(CROSSGL_MLIR_SKIP_REASON_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_EVIDENCE_REASON}")
crossgl_mlir_json_string(CROSSGL_MLIR_SKIP_REGEX_JSON
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REGEX}")
crossgl_mlir_json_string_list(CROSSGL_MLIR_MISSING_REASONS_JSON
  ${CROSSGL_MLIR_EXPERIMENT_VERIFIER_MISSING_REASONS})
crossgl_mlir_json_string_list(CROSSGL_MLIR_REGISTRATION_REQUIRED_FILES_JSON
  ${CROSSGL_MLIR_EXPERIMENT_VERIFIER_REQUIRED_FILES})
crossgl_mlir_json_string_list(
  CROSSGL_MLIR_STORAGE_REGISTRATION_REQUIRED_FILES_JSON
  ${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFIER_REQUIRED_FILES})
crossgl_mlir_json_string_list(CROSSGL_MLIR_VERIFIER_CTESTS_JSON
  "${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_TEST}"
  "${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_TEST}")
crossgl_mlir_json_string_list(CROSSGL_MLIR_REQUIRED_GATE_FACTS_JSON
  "CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON"
  "MLIR_FOUND=TRUE"
  "target crossgl_mlir_experiment"
  "${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE}"
  "${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT_RELATIVE}"
  "mlir-opt discovery"
  "mlir-opt --version probe")
file(MAKE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/mlir")
file(WRITE "${CROSSGL_MLIR_EXPERIMENT_OPTIONAL_TOOL_EVIDENCE}"
  "{\n"
  "  \"schemaVersion\": 1,\n"
  "  \"kind\": \"crossgl-mlir-optional-tool-evidence-v0\",\n"
  "  \"status\": ${CROSSGL_MLIR_STATUS_JSON},\n"
  "  \"normalBuildRequired\": false,\n"
  "  \"productionLinked\": false,\n"
  "  \"mlirDiscovery\": {\n"
  "    \"cmakeOption\": \"CROSSGL_ENABLE_MLIR_EXPERIMENTAL\",\n"
  "    \"optionDefault\": ${CROSSGL_MLIR_OPTION_DEFAULT_JSON},\n"
  "    \"optionActual\": ${CROSSGL_MLIR_OPTION_ACTUAL_JSON},\n"
  "    \"optionEnabled\": ${CROSSGL_MLIR_OPTION_ENABLED_JSON},\n"
  "    \"cmakePackage\": \"MLIR\",\n"
  "    \"mlirFound\": ${CROSSGL_MLIR_FOUND_JSON},\n"
  "    \"target\": \"crossgl_mlir_experiment\",\n"
  "    \"targetCreated\": ${CROSSGL_MLIR_TARGET_CREATED_JSON}\n"
  "  },\n"
  "  \"verifierInput\": {\n"
  "    \"sourceList\": \"CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS\",\n"
  "    \"path\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE}\",\n"
  "    \"fixture\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_FIXTURE}\",\n"
  "    \"present\": ${CROSSGL_MLIR_VERIFY_INPUT_PRESENT_JSON}\n"
  "  },\n"
  "  \"verifierInputs\": [\n"
  "    {\n"
  "      \"key\": \"minimal_compute\",\n"
  "      \"sourceList\": \"CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS\",\n"
  "      \"path\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE}\",\n"
  "      \"fixture\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_FIXTURE}\",\n"
  "      \"present\": ${CROSSGL_MLIR_VERIFY_INPUT_PRESENT_JSON}\n"
  "    },\n"
  "    {\n"
  "      \"key\": \"storage_buffer_compute\",\n"
  "      \"sourceList\": \"CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS\",\n"
  "      \"path\": \"${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT_RELATIVE}\",\n"
  "      \"fixture\": \"${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_FIXTURE}\",\n"
  "      \"present\": ${CROSSGL_MLIR_STORAGE_VERIFY_INPUT_PRESENT_JSON}\n"
  "    }\n"
  "  ],\n"
  "  \"verifierTool\": {\n"
  "    \"name\": \"mlir-opt\",\n"
  "    \"requiredForNormalBuild\": false,\n"
  "    \"found\": ${CROSSGL_MLIR_TOOL_FOUND_JSON},\n"
  "    \"path\": ${CROSSGL_MLIR_TOOL_PATH_JSON},\n"
  "    \"discoveryStatus\": ${CROSSGL_MLIR_TOOL_DISCOVERY_STATUS_JSON}\n"
  "  },\n"
  "  \"verifierRegistration\": {\n"
  "    \"ctest\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_TEST}\",\n"
  "    \"mode\": ${CROSSGL_MLIR_REGISTRATION_MODE_JSON},\n"
  "    \"invokesMlirOpt\": ${CROSSGL_MLIR_REGISTRATION_INVOKES_MLIR_OPT_JSON},\n"
  "    \"usesVerifyDiagnostics\": ${CROSSGL_MLIR_REGISTRATION_USES_VERIFY_DIAGNOSTICS_JSON},\n"
  "    \"buildsExperimentTarget\": ${CROSSGL_MLIR_REGISTRATION_BUILDS_TARGET_JSON},\n"
  "    \"buildTarget\": ${CROSSGL_MLIR_REGISTRATION_BUILD_TARGET_JSON},\n"
  "    \"input\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE}\",\n"
  "    \"requiredFiles\": ${CROSSGL_MLIR_REGISTRATION_REQUIRED_FILES_JSON},\n"
  "    \"normalBuildRequired\": false,\n"
  "    \"productionLinked\": false\n"
  "  },\n"
  "  \"verifierRegistrations\": [\n"
  "    {\n"
  "      \"key\": \"minimal_compute\",\n"
  "      \"ctest\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_TEST}\",\n"
  "      \"mode\": ${CROSSGL_MLIR_REGISTRATION_MODE_JSON},\n"
  "      \"invokesMlirOpt\": ${CROSSGL_MLIR_REGISTRATION_INVOKES_MLIR_OPT_JSON},\n"
  "      \"usesVerifyDiagnostics\": ${CROSSGL_MLIR_REGISTRATION_USES_VERIFY_DIAGNOSTICS_JSON},\n"
  "      \"buildsExperimentTarget\": ${CROSSGL_MLIR_REGISTRATION_BUILDS_TARGET_JSON},\n"
  "      \"buildTarget\": ${CROSSGL_MLIR_REGISTRATION_BUILD_TARGET_JSON},\n"
  "      \"input\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_INPUT_RELATIVE}\",\n"
  "      \"requiredFiles\": ${CROSSGL_MLIR_REGISTRATION_REQUIRED_FILES_JSON},\n"
  "      \"normalBuildRequired\": false,\n"
  "      \"productionLinked\": false\n"
  "    },\n"
  "    {\n"
  "      \"key\": \"storage_buffer_compute\",\n"
  "      \"ctest\": \"${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_TEST}\",\n"
  "      \"mode\": ${CROSSGL_MLIR_REGISTRATION_MODE_JSON},\n"
  "      \"invokesMlirOpt\": ${CROSSGL_MLIR_REGISTRATION_INVOKES_MLIR_OPT_JSON},\n"
  "      \"usesVerifyDiagnostics\": ${CROSSGL_MLIR_REGISTRATION_USES_VERIFY_DIAGNOSTICS_JSON},\n"
  "      \"buildsExperimentTarget\": ${CROSSGL_MLIR_REGISTRATION_BUILDS_TARGET_JSON},\n"
  "      \"buildTarget\": ${CROSSGL_MLIR_REGISTRATION_BUILD_TARGET_JSON},\n"
  "      \"input\": \"${CROSSGL_MLIR_EXPERIMENT_STORAGE_BUFFER_VERIFY_INPUT_RELATIVE}\",\n"
  "      \"requiredFiles\": ${CROSSGL_MLIR_STORAGE_REGISTRATION_REQUIRED_FILES_JSON},\n"
  "      \"normalBuildRequired\": false,\n"
  "      \"productionLinked\": false\n"
  "    }\n"
  "  ],\n"
  "  \"reportOnlyCatalogs\": {\n"
  "    \"sourceResourceCatalog\": {\n"
  "      \"path\": \"${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG}\",\n"
  "      \"checker\": \"${CROSSGL_MLIR_SOURCE_RESOURCE_CATALOG_CHECKER}\",\n"
  "      \"requiredFixtureSection\": \"${CROSSGL_MLIR_SOURCE_RESOURCE_PRESERVATION_SECTION}\",\n"
  "      \"optionalMlirToolingRequired\": false,\n"
  "      \"normalBuildRequired\": false,\n"
  "      \"productionLinked\": false\n"
  "    }\n"
  "  },\n"
  "  \"toolProbeEvidence\": {\n"
  "    \"defaultOffBranch\": \"if(NOT CROSSGL_ENABLE_MLIR_EXPERIMENTAL)\",\n"
  "    \"findProgramCommand\": \"find_program(CROSSGL_MLIR_OPT NAMES mlir-opt)\",\n"
  "    \"versionProbeCommand\": \"mlir-opt --version\",\n"
  "    \"defaultOffMayRunFindProgram\": false,\n"
  "    \"defaultOffMayRunVersionProbe\": false,\n"
  "    \"findProgramAttempted\": ${CROSSGL_MLIR_FIND_PROGRAM_ATTEMPTED_JSON},\n"
  "    \"versionProbeAttempted\": ${CROSSGL_MLIR_VERSION_PROBE_ATTEMPTED_JSON}\n"
  "  },\n"
  "  \"skipEvidence\": {\n"
  "    \"ctest\": \"${CROSSGL_MLIR_EXPERIMENT_MINIMAL_VERIFY_TEST}\",\n"
  "    \"ctests\": ${CROSSGL_MLIR_VERIFIER_CTESTS_JSON},\n"
  "    \"skipRegistered\": ${CROSSGL_MLIR_SKIP_REGISTERED_JSON},\n"
  "    \"reason\": ${CROSSGL_MLIR_SKIP_REASON_JSON},\n"
  "    \"labels\": ${CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_LABELS_JSON},\n"
  "    \"skipRegularExpression\": ${CROSSGL_MLIR_SKIP_REGEX_JSON}\n"
  "  },\n"
  "  \"skipDiagnostics\": {\n"
  "    \"status\": ${CROSSGL_MLIR_STATUS_JSON},\n"
  "    \"reportOnly\": true,\n"
  "    \"requiredGateFacts\": ${CROSSGL_MLIR_REQUIRED_GATE_FACTS_JSON},\n"
  "    \"missingReasons\": ${CROSSGL_MLIR_MISSING_REASONS_JSON},\n"
  "    \"findProgramAttempted\": ${CROSSGL_MLIR_FIND_PROGRAM_ATTEMPTED_JSON},\n"
  "    \"versionProbeAttempted\": ${CROSSGL_MLIR_VERSION_PROBE_ATTEMPTED_JSON}\n"
  "  }\n"
  "}\n")

foreach(CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORD IN LISTS
    CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORDS)
  string(REPLACE "|" ";" CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS
    "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_RECORD}")
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 1
    CROSSGL_MLIR_EXPERIMENT_RECORD_TEST)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 2
    CROSSGL_MLIR_EXPERIMENT_RECORD_FIXTURE)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 3
    CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_RELATIVE)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 4
    CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 5
    CROSSGL_MLIR_EXPERIMENT_RECORD_REQUIRED_MARKERS_VAR)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 6
    CROSSGL_MLIR_EXPERIMENT_RECORD_OUTPUT_MARKERS_VAR)
  list(GET CROSSGL_MLIR_EXPERIMENT_VERIFIER_FIELDS 7
    CROSSGL_MLIR_EXPERIMENT_RECORD_DESCRIPTION)

  if(NOT CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS STREQUAL
      "toolchain-available")
    add_test(NAME "${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: CrossGL MLIR experiment real MLIR ${CROSSGL_MLIR_EXPERIMENT_RECORD_DESCRIPTION} verifier unavailable: ${CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REASON}")
    set_tests_properties("${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}" PROPERTIES
      LABELS "mlir;optional-mlir;mlir-tool-unavailable"
      SKIP_REGULAR_EXPRESSION "^SKIP:")
    message(STATUS
      "CrossGL MLIR experiment verifier harness skipped: "
      "test=${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}; "
      "status=${CROSSGL_MLIR_EXPERIMENT_VERIFIER_STATUS}; "
      "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_SKIP_REASON}")
  else()
    add_test(NAME "${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}"
      COMMAND ${CMAKE_COMMAND}
        -DCROSSGL_MLIR_EXPERIMENT_VERIFY_SCRIPT=ON
        "-DMLIR_OPT=${CROSSGL_MLIR_OPT}"
        "-DINPUT_MLIR=${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT}"
        "-DREQUIRED_MARKERS_VAR=${CROSSGL_MLIR_EXPERIMENT_RECORD_REQUIRED_MARKERS_VAR}"
        "-DOUTPUT_MARKERS_VAR=${CROSSGL_MLIR_EXPERIMENT_RECORD_OUTPUT_MARKERS_VAR}"
        "-DBUILD_DIR=${CMAKE_CURRENT_BINARY_DIR}"
        -DEXPERIMENT_TARGET=crossgl_mlir_experiment
        "-DBUILD_CONFIG=$<CONFIG>"
        -P ${CMAKE_CURRENT_LIST_FILE})
    set_tests_properties("${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}" PROPERTIES
      LABELS "mlir;optional-mlir;mlir-tool-available"
      PROCESSORS 1
      REQUIRED_FILES "${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT}")
    message(STATUS
      "CrossGL MLIR experiment verifier harness registered: "
      "test=${CROSSGL_MLIR_EXPERIMENT_RECORD_TEST}; "
      "fixture=${CROSSGL_MLIR_EXPERIMENT_RECORD_FIXTURE}; "
      "verifier_input=${CROSSGL_MLIR_EXPERIMENT_RECORD_INPUT_RELATIVE}; "
      "mlir-opt=${CROSSGL_MLIR_OPT}; "
      "mlir-opt --version=${CROSSGL_MLIR_OPT_VERSION_OUTPUT}")
  endif()
endforeach()
