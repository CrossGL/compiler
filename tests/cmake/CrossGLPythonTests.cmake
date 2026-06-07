function(crossgl_add_required_python_test)
  set(one_value_args NAME)
  set(multi_value_args COMMAND)
  cmake_parse_arguments(CROSSGL_PY_TEST "" "${one_value_args}"
    "${multi_value_args}" ${ARGN})
  if(NOT CROSSGL_PY_TEST_NAME)
    message(FATAL_ERROR "crossgl_add_required_python_test requires NAME")
  endif()
  if(NOT CROSSGL_PY_TEST_COMMAND)
    message(FATAL_ERROR
      "crossgl_add_required_python_test requires COMMAND")
  endif()
  if(CROSSGL_PYTHON3)
    add_test(NAME "${CROSSGL_PY_TEST_NAME}"
      COMMAND ${CROSSGL_PY_TEST_COMMAND})
    set_property(DIRECTORY APPEND PROPERTY
      CROSSGL_REQUIRED_PYTHON_TESTS "${CROSSGL_PY_TEST_NAME}")
  endif()
endfunction()

function(crossgl_add_python_script_test)
  set(one_value_args NAME SCRIPT)
  set(multi_value_args ARGS)
  cmake_parse_arguments(CROSSGL_SCRIPT_TEST "" "${one_value_args}"
    "${multi_value_args}" ${ARGN})
  if(NOT CROSSGL_SCRIPT_TEST_NAME)
    message(FATAL_ERROR "crossgl_add_python_script_test requires NAME")
  endif()
  if(NOT CROSSGL_SCRIPT_TEST_SCRIPT)
    message(FATAL_ERROR "crossgl_add_python_script_test requires SCRIPT")
  endif()
  crossgl_add_required_python_test(
    NAME "${CROSSGL_SCRIPT_TEST_NAME}"
    COMMAND
      "${CROSSGL_PYTHON3}"
      "${CROSSGL_SCRIPT_TEST_SCRIPT}"
      ${CROSSGL_SCRIPT_TEST_ARGS})
endfunction()

function(crossgl_add_python_expect_test)
  set(one_value_args NAME)
  set(multi_value_args DEFINITIONS)
  cmake_parse_arguments(CROSSGL_EXPECT_TEST "" "${one_value_args}"
    "${multi_value_args}" ${ARGN})
  if(NOT CROSSGL_EXPECT_TEST_NAME)
    message(FATAL_ERROR "crossgl_add_python_expect_test requires NAME")
  endif()
  if(NOT CROSSGL_EXPECT_TEST_DEFINITIONS)
    message(FATAL_ERROR
      "crossgl_add_python_expect_test requires DEFINITIONS")
  endif()
  crossgl_add_required_python_test(
    NAME "${CROSSGL_EXPECT_TEST_NAME}"
    COMMAND
      "${CMAKE_COMMAND}"
      ${CROSSGL_EXPECT_TEST_DEFINITIONS}
      "-DPYTHON3_EXECUTABLE=${CROSSGL_PYTHON3}"
      -P "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/ExpectCommand.cmake")
endfunction()

set(CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS_DEFAULT "1")
if(DEFINED ENV{CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS}
    AND NOT "$ENV{CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS}" STREQUAL "")
  set(CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS_DEFAULT
    "$ENV{CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS}")
endif()
set(CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS
  "${CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS_DEFAULT}"
  CACHE STRING "Worker count for cglc_package_inspect_fixtures")
if(NOT CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS MATCHES "^[1-9][0-9]*$")
  message(FATAL_ERROR
    "CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS must be a positive integer")
endif()

set(CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS_DEFAULT "1")
if(DEFINED ENV{CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS}
    AND NOT "$ENV{CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS}" STREQUAL "")
  set(CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS_DEFAULT
    "$ENV{CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS}")
elseif(DEFINED ENV{CROSSGL_CI_JOBS}
    AND NOT "$ENV{CROSSGL_CI_JOBS}" STREQUAL "")
  set(CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS_DEFAULT
    "$ENV{CROSSGL_CI_JOBS}")
endif()
set(CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS
  "${CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS_DEFAULT}"
  CACHE STRING "Worker count for cglc_package_inspect_artifact_inventory_runtime")
if(NOT CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS MATCHES "^[1-9][0-9]*$")
  message(FATAL_ERROR
    "CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS must be a positive integer")
endif()

set(CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS_DEFAULT "1")
if(DEFINED ENV{CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS}
    AND NOT "$ENV{CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS}" STREQUAL "")
  set(CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS_DEFAULT
    "$ENV{CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS}")
elseif(DEFINED ENV{CROSSGL_CI_JOBS}
    AND NOT "$ENV{CROSSGL_CI_JOBS}" STREQUAL "")
  set(CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS_DEFAULT "$ENV{CROSSGL_CI_JOBS}")
endif()
set(CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS
  "${CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS_DEFAULT}"
  CACHE STRING "Worker count for cglc_package_reproducibility")
if(NOT CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS MATCHES "^[1-9][0-9]*$")
  message(FATAL_ERROR
    "CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS must be a positive integer")
endif()

set(CROSSGL_INVALID_JSON_SCHEMA_FIXTURE_JOBS_DEFAULT "1")
if(DEFINED ENV{CROSSGL_INVALID_JSON_SCHEMA_FIXTURE_JOBS}
    AND NOT "$ENV{CROSSGL_INVALID_JSON_SCHEMA_FIXTURE_JOBS}" STREQUAL "")
  set(CROSSGL_INVALID_JSON_SCHEMA_FIXTURE_JOBS_DEFAULT
    "$ENV{CROSSGL_INVALID_JSON_SCHEMA_FIXTURE_JOBS}")
elseif(DEFINED ENV{CROSSGL_CI_JOBS}
    AND NOT "$ENV{CROSSGL_CI_JOBS}" STREQUAL "")
  set(CROSSGL_INVALID_JSON_SCHEMA_FIXTURE_JOBS_DEFAULT "$ENV{CROSSGL_CI_JOBS}")
endif()
set(CROSSGL_INVALID_JSON_SCHEMA_FIXTURE_JOBS
  "${CROSSGL_INVALID_JSON_SCHEMA_FIXTURE_JOBS_DEFAULT}"
  CACHE STRING "Worker count for cglc_invalid_json_schema_fixtures")
if(NOT CROSSGL_INVALID_JSON_SCHEMA_FIXTURE_JOBS MATCHES "^[1-9][0-9]*$")
  message(FATAL_ERROR
    "CROSSGL_INVALID_JSON_SCHEMA_FIXTURE_JOBS must be a positive integer")
endif()

crossgl_add_python_script_test(
  NAME cglc_shared_json_schema_defs
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_shared_json_schema_defs.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR})
crossgl_add_required_python_test(
  NAME cglc_source_remap_v1_json_schema
  COMMAND
    "${CROSSGL_PYTHON3}"
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py"
    --schema
    "${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/source-remap-v1.schema.json"
    --instance
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-basic.json")
crossgl_add_required_python_test(
  NAME cglc_source_remap_provenance_v1_json_schema
  COMMAND
    "${CROSSGL_PYTHON3}"
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py"
    --schema
    "${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/source-remap-provenance-v1.schema.json"
    --instance
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-provenance-v1-basic.json")
crossgl_add_required_python_test(
  NAME cglc_source_batch_manifest_v1_json_schema
  COMMAND
    "${CROSSGL_PYTHON3}"
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py"
    --schema
    "${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/source-batch-manifest-v1.schema.json"
    --instance
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-batch-manifest-v1-basic.json")
crossgl_add_required_python_test(
  NAME cglc_diagnostics_v1_project_json_schema
  COMMAND
    "${CROSSGL_PYTHON3}"
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py"
    --schema
    "${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/diagnostics-v1.schema.json"
    --instance
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/diagnostics-v1-project.json")
crossgl_add_python_script_test(
  NAME cglc_cross_repo_contract_tool
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_cross_repo_contract_tool.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR})
crossgl_add_python_script_test(
  NAME cglc_cross_repo_language_feature_spec
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_cross_repo_language_contract.py
  ARGS
    --compiler-root ${CMAKE_CURRENT_SOURCE_DIR}
    --check-feature-spec)
crossgl_add_python_script_test(
  NAME cglc_cross_repo_language_feature_spec_self_test
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_cross_repo_language_contract.py
  ARGS
    --compiler-root ${CMAKE_CURRENT_SOURCE_DIR}
    --self-test)
crossgl_add_required_python_test(
  NAME cglc_crosstl_language_spec_extractor_compile
  COMMAND
    "${CROSSGL_PYTHON3}"
    -m
    py_compile
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/extract_crosstl_language_spec.py")
crossgl_add_required_python_test(
  NAME cglc_crosstl_language_spec_extractor_cli_compile
  COMMAND
    "${CROSSGL_PYTHON3}"
    -m
    py_compile
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/language-spec/check_extractor_cli.py")
crossgl_add_required_python_test(
  NAME cglc_crosstl_language_spec_extractor_cli
  COMMAND
    "${CROSSGL_PYTHON3}"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/language-spec/check_extractor_cli.py")
crossgl_add_required_python_test(
  NAME cglc_benchmark_build_modes_compile
  COMMAND
    "${CROSSGL_PYTHON3}"
    -m
    py_compile
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/benchmark_build_modes.py")
crossgl_add_required_python_test(
  NAME cglc_performance_corpus_runner_compile
  COMMAND
    "${CROSSGL_PYTHON3}"
    -m
    py_compile
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/benchmark_performance_corpus.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_performance_corpus_manifest.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_performance_corpus_runner.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/compare_performance_reports.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_performance_report_comparator.py")
crossgl_add_python_script_test(
  NAME cglc_benchmark_build_modes
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_benchmark_build_modes.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR})
crossgl_add_python_script_test(
  NAME cglc_performance_corpus_runner
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_performance_corpus_runner.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR})
crossgl_add_python_script_test(
  NAME cglc_performance_corpus_manifest
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_performance_corpus_manifest.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR})
crossgl_add_python_script_test(
  NAME cglc_performance_corpus_manifest_self_test
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_performance_corpus_manifest.py
  ARGS
    --self-test)
crossgl_add_python_script_test(
  NAME cglc_performance_report_comparator
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_performance_report_comparator.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR})
crossgl_add_python_script_test(
  NAME cglc_invalid_json_schema_fixtures
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_invalid_json_schema_fixtures.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --jobs ${CROSSGL_INVALID_JSON_SCHEMA_FIXTURE_JOBS})
if(CROSSGL_PYTHON3)
  set_tests_properties(cglc_invalid_json_schema_fixtures PROPERTIES
    PROCESSORS "${CROSSGL_INVALID_JSON_SCHEMA_FIXTURE_JOBS}")
endif()
crossgl_add_python_script_test(
  NAME cglc_ctest_registration_health
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_ctest_registration.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --build-dir ${CMAKE_BINARY_DIR}
    --ctest-config $<CONFIG>
    --metadata-only)
crossgl_add_python_script_test(
  NAME cglc_ctest_registration_health_windows_path_probe
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_ctest_registration.py
  ARGS
    --self-test)
set(CROSSGL_V0_CONFORMANCE_EXECUTION_WORK_DIR
  "${CMAKE_BINARY_DIR}/conformance/v0-manifest-execution")
set(CROSSGL_V0_CONFORMANCE_EXECUTION_REPORT_DIR
  "${CMAKE_BINARY_DIR}/reports/conformance")
crossgl_add_required_python_test(
  NAME cglc_v0_conformance_manifest_compile
  COMMAND
    "${CROSSGL_PYTHON3}"
    -m
    py_compile
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_conformance_manifest.py")
crossgl_add_python_script_test(
  NAME cglc_v0_conformance_manifest
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_conformance_manifest.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --build-dir ${CMAKE_BINARY_DIR}
    --ctest-config $<CONFIG>)
crossgl_add_python_script_test(
  NAME cglc_v0_conformance_manifest_execution
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_conformance_manifest.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --build-dir ${CMAKE_BINARY_DIR}
    --ctest-config $<CONFIG>
    --cglc $<TARGET_FILE:cglc>
    --work-dir ${CROSSGL_V0_CONFORMANCE_EXECUTION_WORK_DIR}
    --report-json
      ${CROSSGL_V0_CONFORMANCE_EXECUTION_REPORT_DIR}/manifest.v0.execution.json
    --report-text
      ${CROSSGL_V0_CONFORMANCE_EXECUTION_REPORT_DIR}/manifest.v0.execution.txt
    --skip-native-package-builds)
crossgl_add_python_script_test(
  NAME cglc_v0_conformance_manifest_self_test
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_conformance_manifest.py
  ARGS
    --self-test)
crossgl_add_required_python_test(
  NAME cglc_release_provenance_manifest_compile
  COMMAND
    "${CROSSGL_PYTHON3}"
    -m
    py_compile
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_release_provenance_manifest.py")
crossgl_add_python_script_test(
  NAME cglc_release_provenance_manifest_self_test
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_release_provenance_manifest.py
  ARGS
    --self-test)
crossgl_add_python_script_test(
  NAME cglc_release_provenance_manifest_from_stage_report
  SCRIPT
    ${CMAKE_CURRENT_SOURCE_DIR}/tests/release-provenance-manifest/check_from_stage_report.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR})
crossgl_add_required_python_test(
  NAME cglc_doctor_target_explanation_alignment_compile
  COMMAND
    "${CROSSGL_PYTHON3}"
    -m
    py_compile
    "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_doctor_target_explanation_alignment.py")
crossgl_add_python_script_test(
  NAME cglc_doctor_target_explanation_alignment
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_doctor_target_explanation_alignment.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR})
crossgl_add_python_script_test(
  NAME cglc_doctor_target_explanation_alignment_self_test
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_doctor_target_explanation_alignment.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --self-test)
crossgl_add_python_script_test(
  NAME cglc_target_readonly_consumer_alignment
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_target_readonly_consumer_alignment.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>)
crossgl_add_python_script_test(
  NAME cglc_fixture_registration
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_fixture_registration.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR})
crossgl_add_python_script_test(
  NAME cglc_diagnostic_provenance_fixtures
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_diagnostic_provenance_fixtures.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>)
crossgl_add_python_script_test(
  NAME cglc_benchmark_harness_self_test
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/benchmark_cglc.py
  ARGS
    --self-test)
crossgl_add_python_script_test(
  NAME cglc_package_integrity_fixtures
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_package_integrity_fixtures.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>)
crossgl_add_python_script_test(
  NAME cglc_package_inspect_fixtures
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_package_inspect_fixtures.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>
    --jobs ${CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS})
if(CROSSGL_PYTHON3)
  set_tests_properties(cglc_package_inspect_fixtures PROPERTIES
    PROCESSORS "${CROSSGL_PACKAGE_INSPECT_FIXTURE_JOBS}")
endif()
crossgl_add_python_script_test(
  NAME cglc_package_inspect_artifact_inventory_runtime
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_package_artifact_inventory_runtime.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>
    --jobs ${CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS})
if(CROSSGL_PYTHON3)
  set_tests_properties(cglc_package_inspect_artifact_inventory_runtime PROPERTIES
    PROCESSORS "${CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS}")
endif()
crossgl_add_python_script_test(
  NAME cglc_graphics_package_artifacts
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_graphics_package_artifacts.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>)
crossgl_add_python_script_test(
  NAME cglc_graphics_abi_verifier
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_graphics_abi_verifier.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR})
crossgl_add_python_script_test(
  NAME cglc_package_debug_provenance
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_package_debug_provenance.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>)
crossgl_add_python_script_test(
  NAME cglc_package_recover_fixtures
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_package_recover_fixtures.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>)
crossgl_add_python_script_test(
  NAME cglc_package_verify_fixtures
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_package_verify_fixtures.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>)
crossgl_add_python_script_test(
  NAME cglc_package_reproducibility
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_package_reproducibility.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>
    --jobs ${CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS})
if(CROSSGL_PYTHON3)
  set_tests_properties(cglc_package_reproducibility PROPERTIES
    PROCESSORS "${CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS}")
endif()
crossgl_add_python_script_test(
  NAME cglc_package_release_publish_flow
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_package_release_publish_flow.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>
    --work-dir ${CMAKE_BINARY_DIR}/package-release-publish-flow)
crossgl_add_python_script_test(
  NAME cglc_package_release_publish_flow_self_test
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_package_release_publish_flow.py
  ARGS
    --self-test)
crossgl_add_python_script_test(
  NAME cglc_package_release_artifact_contract
  SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_package_release_artifact_contract.py
  ARGS
    --root ${CMAKE_CURRENT_SOURCE_DIR}
    --cglc $<TARGET_FILE:cglc>
    --work-dir ${CMAKE_BINARY_DIR}/package-release-artifact-contract)
