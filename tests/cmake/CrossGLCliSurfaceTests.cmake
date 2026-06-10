if(CROSSGL_RUN_CLI_SURFACE_TEST)
  if(NOT DEFINED CGLC)
    message(FATAL_ERROR "CGLC is required")
  endif()
  if(NOT DEFINED EXPECTED_RESULT)
    message(FATAL_ERROR "EXPECTED_RESULT is required")
  endif()
  if(NOT DEFINED CLI_ARG_COUNT)
    set(CLI_ARG_COUNT 0)
  endif()
  if(NOT DEFINED STDOUT_FRAGMENT_COUNT)
    set(STDOUT_FRAGMENT_COUNT 0)
  endif()
  if(NOT DEFINED STDERR_FRAGMENT_COUNT)
    set(STDERR_FRAGMENT_COUNT 0)
  endif()

  set(command "${CGLC}")
  if(CLI_ARG_COUNT GREATER 0)
    math(EXPR last_arg_index "${CLI_ARG_COUNT} - 1")
    foreach(index RANGE 0 ${last_arg_index})
      list(APPEND command "${CLI_ARG_${index}}")
    endforeach()
  endif()

  execute_process(
    COMMAND ${command}
    RESULT_VARIABLE result
    OUTPUT_VARIABLE stdout
    ERROR_VARIABLE stderr
  )

  if(NOT result EQUAL EXPECTED_RESULT)
    message(FATAL_ERROR
      "expected exit code ${EXPECTED_RESULT}, got ${result}. "
      "Stdout: ${stdout} Stderr: ${stderr}")
  endif()

  if(STDOUT_FRAGMENT_COUNT GREATER 0)
    math(EXPR last_stdout_fragment_index "${STDOUT_FRAGMENT_COUNT} - 1")
    foreach(index RANGE 0 ${last_stdout_fragment_index})
      string(FIND "${stdout}" "${STDOUT_FRAGMENT_${index}}" fragment_position)
      if(fragment_position EQUAL -1)
        message(FATAL_ERROR
          "expected stdout to contain '${STDOUT_FRAGMENT_${index}}', got: ${stdout}")
      endif()
    endforeach()
  endif()

  if(STDERR_FRAGMENT_COUNT GREATER 0)
    math(EXPR last_stderr_fragment_index "${STDERR_FRAGMENT_COUNT} - 1")
    foreach(index RANGE 0 ${last_stderr_fragment_index})
      string(FIND "${stderr}" "${STDERR_FRAGMENT_${index}}" fragment_position)
      if(fragment_position EQUAL -1)
        message(FATAL_ERROR
          "expected stderr to contain '${STDERR_FRAGMENT_${index}}', got: ${stderr}")
      endif()
    endforeach()
  endif()
  return()
endif()

set(CROSSGL_CLI_SURFACE_TEST_SCRIPT "${CMAKE_CURRENT_LIST_FILE}")
set(CROSSGL_CLI_MISSING_INPUT_SHADER
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-missing-input-does-not-exist.cgl")
get_filename_component(CROSSGL_CLI_MISSING_INPUT_JSON_FILE
  "${CROSSGL_CLI_MISSING_INPUT_SHADER}" NAME)
file(REMOVE "${CROSSGL_CLI_MISSING_INPUT_SHADER}")

function(crossgl_write_cli_binary_fixture output_path python_bytes_literal)
  execute_process(
    COMMAND "${CROSSGL_PYTHON3}" -c
      "from pathlib import Path; import sys; Path(sys.argv[1]).write_bytes(${python_bytes_literal})"
      "${output_path}"
    RESULT_VARIABLE write_result
    ERROR_VARIABLE write_error)
  if(NOT write_result EQUAL 0)
    message(FATAL_ERROR
      "failed to write CLI binary fixture '${output_path}': ${write_error}")
  endif()
endfunction()

if(CROSSGL_PYTHON3)
  set(CROSSGL_CLI_LEADING_BOM_SHADER
    "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-leading-bom-source.cgl")
  get_filename_component(CROSSGL_CLI_LEADING_BOM_JSON_FILE
    "${CROSSGL_CLI_LEADING_BOM_SHADER}" NAME)
  set(CROSSGL_CLI_NUL_SOURCE_SHADER
    "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-nul-source-byte.cgl")
  get_filename_component(CROSSGL_CLI_NUL_SOURCE_JSON_FILE
    "${CROSSGL_CLI_NUL_SOURCE_SHADER}" NAME)
  set(CROSSGL_CLI_INVALID_UTF8_SHADER
    "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-invalid-utf8-source.cgl")
  get_filename_component(CROSSGL_CLI_INVALID_UTF8_JSON_FILE
    "${CROSSGL_CLI_INVALID_UTF8_SHADER}" NAME)
  crossgl_write_cli_binary_fixture("${CROSSGL_CLI_LEADING_BOM_SHADER}" [=[
(b"\xef\xbb\xbf"
 b"shader LeadingBomSourceShader {\n"
 b"  compute {\n"
 b"    layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;\n"
 b"    void main() { return; }\n"
 b"  }\n"
 b"}\n")
]=])
  crossgl_write_cli_binary_fixture("${CROSSGL_CLI_NUL_SOURCE_SHADER}" [=[
(b"shader NulSourceByteShader {\n"
 b"  compute {\n"
 b"    layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;\n"
 b"    void main() { return; }\n"
 b"  }\n"
 b"}\n"
 b"\x00\n")
]=])
  crossgl_write_cli_binary_fixture("${CROSSGL_CLI_INVALID_UTF8_SHADER}" [=[
(b"shader InvalidUtf8SourceShader {\n"
 b"  compute {\n"
 b"    layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;\n"
 b"    void main() { return; }\n"
 b"  }\n"
 b"}\n"
 b"\xff\n")
]=])
endif()

set(CROSSGL_CLI_SOURCE_BATCH_CHECK_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-check.json")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_CHECK_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"defaults\": {
    \"target\": \"auto\",
    \"optLevel\": \"O1\"
  },
  \"sources\": [
    {
      \"id\": \"simple\",
      \"path\": \"tests/fixtures/SimpleShader.cgl\",
      \"logicalInput\": \"translator/snapshots/SimpleShader.cgl\"
    },
    {
      \"id\": \"fn-style\",
      \"path\": \"tests/fixtures/FnStyleFunctionShader.cgl\",
      \"logicalPath\": \"translator/snapshots/FnStyleFunctionShader.cgl\"
    },
    \"tests/fixtures/MinimalComputeShader.cgl\"
  ]
}
")

set(CROSSGL_CLI_SOURCE_BATCH_BUILD_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-build.json")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_BUILD_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"defaults\": {
    \"target\": \"directx\",
    \"optLevel\": \"O1\"
  },
  \"sources\": [
    {
      \"id\": \"storage\",
      \"path\": \"tests/fixtures/StorageBufferComputeShader.cgl\",
      \"output\": \"${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-storage.cglb\"
    },
    {
      \"id\": \"fn-style\",
      \"path\": \"tests/fixtures/FnStyleFunctionShader.cgl\",
      \"output\": \"${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-fn-style.cglb\",
      \"debugIR\": true
    }
  ]
}
")

set(CROSSGL_CLI_SOURCE_BATCH_BUILD_JSON_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-build-json.json")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_BUILD_JSON_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"defaults\": {
    \"target\": \"directx\",
    \"optLevel\": \"O1\"
  },
  \"sources\": [
    {
      \"id\": \"storage\",
      \"path\": \"tests/fixtures/StorageBufferComputeShader.cgl\",
      \"output\": \"${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-json-storage.cglb\"
    },
    {
      \"id\": \"fn-style\",
      \"path\": \"tests/fixtures/FnStyleFunctionShader.cgl\",
      \"output\": \"${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-json-fn-style.cglb\",
      \"debugIR\": true
    }
  ]
}
")

set(CROSSGL_CLI_SOURCE_BATCH_BUILD_REMAP_JSON_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-build-remap-json.json")
set(CROSSGL_CLI_SOURCE_BATCH_FULL_FILE_REMAP
  "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-full-file.json")
set(CROSSGL_CLI_CROSSTL_PROJECT_REPORT_LINE
  "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/crosstl-project-portability-report-v1-basic.json")
set(CROSSGL_CLI_CROSSTL_PROJECT_REPORT_FILE
  "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/crosstl-project-portability-report-v1-file.json")
set(CROSSGL_CLI_CROSSTL_PROJECT_REPORT_BUILD_OUTPUT_DIR
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-crosstl-project-report-build")
set(CROSSGL_CLI_CROSSTL_PROJECT_REPORT_BUILD_JSON_OUTPUT_DIR
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-crosstl-project-report-build-json")
set(CROSSGL_CLI_CROSSTL_PROJECT_REPORT_NO_TRANSLATED
  "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/crosstl-project-portability-report-v1-no-translated.json")
set(CROSSGL_CLI_CROSSTL_PROJECT_REPORT_MISSING_REMAP
  "${CMAKE_CURRENT_BINARY_DIR}/crosstl-project-report-missing-remap.json")
set(CROSSGL_CLI_CROSSTL_PROJECT_REPORT_TARGET_MISMATCH
  "${CMAKE_CURRENT_BINARY_DIR}/crosstl-project-report-remap-target-mismatch.json")
set(CROSSGL_CLI_CROSSTL_PROJECT_REPORT_GENERATED_MISMATCH
  "${CMAKE_CURRENT_BINARY_DIR}/crosstl-project-report-remap-generated-mismatch.json")
set(CROSSGL_CLI_CROSSTL_PROJECT_REPORT_SELF_REMAP_PATH
  "${CMAKE_CURRENT_BINARY_DIR}/crosstl-project-report-self-remap-path.json")
set(CROSSGL_CLI_CROSSTL_PROJECT_REPORT_ZERO_MAPPING_COUNT
  "${CMAKE_CURRENT_BINARY_DIR}/crosstl-project-report-zero-mapping-count.json")
set(CROSSGL_CLI_CROSSTL_PROJECT_REPORT_STALE_REMAP_HASH
  "${CMAKE_CURRENT_BINARY_DIR}/crosstl-project-report-stale-remap-hash.json")
set(CROSSGL_CLI_CROSSTL_PROJECT_REPORT_LINE_SOURCE_REMAP
  "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/out/cgl/simple.source-remap.json")
set(CROSSGL_CLI_CROSSTL_PROJECT_REPORT_FILE_SOURCE_REMAP
  "${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/out/cgl/simple-file.source-remap.json")
file(WRITE "${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_MISSING_REMAP}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crosstl-project-portability-report\",
  \"project\": { \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\" },
  \"artifacts\": [
    {
      \"source\": \"simple.cgl\",
      \"target\": \"cgl\",
      \"path\": \"tests/fixtures/out/cgl/simple.cgl\",
      \"status\": \"translated\"
    }
  ]
}
")
file(WRITE "${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_TARGET_MISMATCH}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crosstl-project-portability-report\",
  \"project\": { \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\" },
  \"artifacts\": [
    {
      \"source\": \"simple.cgl\",
      \"target\": \"cgl\",
      \"path\": \"tests/fixtures/out/cgl/simple.cgl\",
      \"status\": \"translated\",
      \"sourceRemap\": {
        \"schemaVersion\": 1,
        \"path\": \"tests/fixtures/out/cgl/simple.source-remap.json\",
        \"target\": \"metal\",
        \"generatedFile\": \"tests/fixtures/out/cgl/simple.cgl\",
        \"mappingGranularity\": \"line\",
        \"mappingCount\": 2,
        \"sizeBytes\": 982,
        \"hash\": {
          \"algorithm\": \"sha256\",
          \"value\": \"eb7d2b50594a5705cafaf2cf88eccd18975b597eb9e216caea824c63bea9ec92\"
        }
      }
    }
  ]
}
")
file(WRITE "${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_GENERATED_MISMATCH}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crosstl-project-portability-report\",
  \"project\": { \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\" },
  \"artifacts\": [
    {
      \"source\": \"simple.cgl\",
      \"target\": \"cgl\",
      \"path\": \"tests/fixtures/out/cgl/simple.cgl\",
      \"status\": \"translated\",
      \"sourceRemap\": {
        \"schemaVersion\": 1,
        \"path\": \"tests/fixtures/out/cgl/simple.source-remap.json\",
        \"target\": \"cgl\",
        \"generatedFile\": \"tests/fixtures/SimpleShader.cgl\",
        \"mappingGranularity\": \"line\",
        \"mappingCount\": 2,
        \"sizeBytes\": 982,
        \"hash\": {
          \"algorithm\": \"sha256\",
          \"value\": \"eb7d2b50594a5705cafaf2cf88eccd18975b597eb9e216caea824c63bea9ec92\"
        }
      }
    }
  ]
}
")
file(WRITE "${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_SELF_REMAP_PATH}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crosstl-project-portability-report\",
  \"project\": { \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\" },
  \"artifacts\": [
    {
      \"source\": \"simple.cgl\",
      \"target\": \"cgl\",
      \"path\": \"tests/fixtures/out/cgl/simple.cgl\",
      \"status\": \"translated\",
      \"sourceRemap\": {
        \"schemaVersion\": 1,
        \"path\": \"tests/fixtures/out/cgl/simple.cgl\",
        \"target\": \"cgl\",
        \"generatedFile\": \"tests/fixtures/out/cgl/simple.cgl\",
        \"mappingGranularity\": \"line\",
        \"mappingCount\": 2,
        \"sizeBytes\": 982,
        \"hash\": {
          \"algorithm\": \"sha256\",
          \"value\": \"eb7d2b50594a5705cafaf2cf88eccd18975b597eb9e216caea824c63bea9ec92\"
        }
      }
    }
  ]
}
")
file(WRITE "${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_ZERO_MAPPING_COUNT}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crosstl-project-portability-report\",
  \"project\": { \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\" },
  \"artifacts\": [
    {
      \"source\": \"simple.cgl\",
      \"target\": \"cgl\",
      \"path\": \"tests/fixtures/out/cgl/simple.cgl\",
      \"status\": \"translated\",
      \"sourceRemap\": {
        \"schemaVersion\": 1,
        \"path\": \"tests/fixtures/out/cgl/simple.source-remap.json\",
        \"target\": \"cgl\",
        \"generatedFile\": \"tests/fixtures/out/cgl/simple.cgl\",
        \"mappingGranularity\": \"line\",
        \"mappingCount\": 0,
        \"sizeBytes\": 982,
        \"hash\": {
          \"algorithm\": \"sha256\",
          \"value\": \"eb7d2b50594a5705cafaf2cf88eccd18975b597eb9e216caea824c63bea9ec92\"
        }
      }
    }
  ]
}
")
file(WRITE "${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_STALE_REMAP_HASH}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crosstl-project-portability-report\",
  \"project\": { \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\" },
  \"artifacts\": [
    {
      \"source\": \"simple.cgl\",
      \"target\": \"cgl\",
      \"path\": \"tests/fixtures/out/cgl/simple.cgl\",
      \"status\": \"translated\",
      \"sourceRemap\": {
        \"schemaVersion\": 1,
        \"path\": \"tests/fixtures/out/cgl/simple.source-remap.json\",
        \"target\": \"cgl\",
        \"generatedFile\": \"tests/fixtures/out/cgl/simple.cgl\",
        \"mappingGranularity\": \"line\",
        \"mappingCount\": 2,
        \"sizeBytes\": 982,
        \"hash\": {
          \"algorithm\": \"sha256\",
          \"value\": \"0000000000000000000000000000000000000000000000000000000000000000\"
        }
      }
    }
  ]
}
")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_BUILD_REMAP_JSON_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"defaults\": {
    \"target\": \"directx\",
    \"optLevel\": \"O1\"
  },
  \"sources\": [
    {
      \"id\": \"storage-remapped\",
      \"path\": \"tests/fixtures/StorageBufferComputeShader.cgl\",
      \"logicalInput\": \"generated/from-translator.cgl\",
      \"sourceRemap\": \"tests/fixtures/source-remap-v1-full-file.json\",
      \"output\": \"${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-remap-storage.cglb\",
      \"debugIR\": true
    }
  ]
}
")

if(CROSSGL_PYTHON3)
  set(CROSSGL_CLI_SOURCE_BATCH_CHECK_FAILURE_MANIFEST
    "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-check-failure.json")
  file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_CHECK_FAILURE_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"defaults\": {
    \"target\": \"auto\",
    \"optLevel\": \"O1\"
  },
  \"sources\": [
    {
      \"id\": \"simple\",
      \"path\": \"tests/fixtures/SimpleShader.cgl\"
    },
    {
      \"id\": \"invalid-utf8\",
      \"path\": \"${CROSSGL_CLI_INVALID_UTF8_SHADER}\",
      \"logicalInput\": \"translator/snapshots/InvalidUtf8SourceShader.cgl\"
    }
  ]
}
")

  set(CROSSGL_CLI_SOURCE_BATCH_BUILD_FAILURE_MANIFEST
    "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-build-failure.json")
  file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_BUILD_FAILURE_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"defaults\": {
    \"target\": \"directx\",
    \"optLevel\": \"O1\"
  },
  \"sources\": [
    {
      \"id\": \"invalid-utf8\",
      \"path\": \"${CROSSGL_CLI_INVALID_UTF8_SHADER}\",
      \"logicalInput\": \"translator/snapshots/InvalidUtf8SourceShader.cgl\",
      \"output\": \"${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-invalid-utf8.cglb\"
    },
    {
      \"id\": \"storage\",
      \"path\": \"tests/fixtures/StorageBufferComputeShader.cgl\",
      \"output\": \"${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-partial-storage.cglb\"
    }
  ]
}
")
endif()

set(CROSSGL_CLI_SOURCE_BATCH_UNKNOWN_TOP_LEVEL_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-unknown-top-level.json")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_UNKNOWN_TOP_LEVEL_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"cacheKey\": \"not-part-of-v1\",
  \"sources\": [
    \"tests/fixtures/SimpleShader.cgl\"
  ]
}
")

set(CROSSGL_CLI_SOURCE_BATCH_UNKNOWN_SOURCE_FIELD_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-unknown-source-field.json")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_UNKNOWN_SOURCE_FIELD_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"sources\": [
    {
      \"path\": \"tests/fixtures/SimpleShader.cgl\",
      \"backend\": \"directx\"
    }
  ]
}
")

set(CROSSGL_CLI_SOURCE_BATCH_BAD_DEFAULT_TYPE_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-bad-default-type.json")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_BAD_DEFAULT_TYPE_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"defaults\": {
    \"debugIR\": \"true\"
  },
  \"sources\": [
    \"tests/fixtures/SimpleShader.cgl\"
  ]
}
")

set(CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_ABSOLUTE_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-logical-input-absolute.json")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_ABSOLUTE_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"sources\": [
    {
      \"path\": \"tests/fixtures/SimpleShader.cgl\",
      \"logicalInput\": \"/tmp/generated/SimpleShader.cgl\"
    }
  ]
}
")

set(CROSSGL_CLI_SOURCE_BATCH_LOGICAL_PATH_PARENT_SEGMENT_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-logical-path-parent-segment.json")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_PATH_PARENT_SEGMENT_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"sources\": [
    {
      \"path\": \"tests/fixtures/SimpleShader.cgl\",
      \"logicalPath\": \"translator/../SimpleShader.cgl\"
    }
  ]
}
")

set(CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_DRIVE_PREFIX_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-logical-input-drive-prefix.json")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_DRIVE_PREFIX_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"sources\": [
    {
      \"path\": \"tests/fixtures/SimpleShader.cgl\",
      \"logicalInput\": \"C:/generated/SimpleShader.cgl\"
    }
  ]
}
")

set(CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_BACKSLASH_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-logical-input-backslash.json")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_BACKSLASH_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"sources\": [
    {
      \"path\": \"tests/fixtures/SimpleShader.cgl\",
      \"logicalInput\": \"translator\\\\snapshots\\\\SimpleShader.cgl\"
    }
  ]
}
")

set(CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_EMPTY_SEGMENT_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-logical-input-empty-segment.json")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_EMPTY_SEGMENT_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"sources\": [
    {
      \"path\": \"tests/fixtures/SimpleShader.cgl\",
      \"logicalInput\": \"translator//snapshots/SimpleShader.cgl\"
    }
  ]
}
")

set(CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_CURRENT_SEGMENT_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-logical-input-current-segment.json")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_CURRENT_SEGMENT_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"sources\": [
    {
      \"path\": \"tests/fixtures/SimpleShader.cgl\",
      \"logicalInput\": \"translator/./snapshots/SimpleShader.cgl\"
    }
  ]
}
")

set(CROSSGL_CLI_SOURCE_BATCH_LOGICAL_PATH_ALIAS_INVALID_MANIFEST
  "${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-source-batch-logical-path-alias-invalid.json")
file(WRITE "${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_PATH_ALIAS_INVALID_MANIFEST}"
"{
  \"schemaVersion\": 1,
  \"kind\": \"crossgl.sourceBatchManifest\",
  \"root\": \"${CMAKE_CURRENT_SOURCE_DIR}\",
  \"sources\": [
    {
      \"path\": \"tests/fixtures/SimpleShader.cgl\",
      \"logicalInput\": \"translator/snapshots/SimpleShader.cgl\",
      \"logicalPath\": \"translator/../SimpleShader.cgl\"
    }
  ]
}
")

function(crossgl_append_cli_surface_defines out_var prefix)
  set(defines)
  set(index 0)
  foreach(value IN LISTS ARGN)
    list(APPEND defines "-D${prefix}_${index}=${value}")
    math(EXPR index "${index} + 1")
  endforeach()
  list(APPEND defines "-D${prefix}_COUNT=${index}")
  set(${out_var} ${defines} PARENT_SCOPE)
endfunction()

function(crossgl_add_cli_surface_test name)
  set(one_value_args EXPECTED_RESULT)
  set(multi_value_args ARGS STDOUT_CONTAINS STDERR_CONTAINS)
  cmake_parse_arguments(CLI_SURFACE "" "${one_value_args}"
                        "${multi_value_args}" ${ARGN})
  if(NOT DEFINED CLI_SURFACE_EXPECTED_RESULT)
    message(FATAL_ERROR "${name} must define EXPECTED_RESULT")
  endif()

  crossgl_append_cli_surface_defines(arg_defines CLI_ARG
                                     ${CLI_SURFACE_ARGS})
  crossgl_append_cli_surface_defines(stdout_defines STDOUT_FRAGMENT
                                     ${CLI_SURFACE_STDOUT_CONTAINS})
  crossgl_append_cli_surface_defines(stderr_defines STDERR_FRAGMENT
                                     ${CLI_SURFACE_STDERR_CONTAINS})

  add_test(NAME "${name}"
    COMMAND ${CMAKE_COMMAND}
      -D CROSSGL_RUN_CLI_SURFACE_TEST=ON
      -D "CGLC=$<TARGET_FILE:cglc>"
      -D "EXPECTED_RESULT=${CLI_SURFACE_EXPECTED_RESULT}"
      ${arg_defines}
      ${stdout_defines}
      ${stderr_defines}
      -P "${CROSSGL_CLI_SURFACE_TEST_SCRIPT}")
endfunction()

crossgl_add_cli_surface_test(cglc_cli_no_args_prints_usage
  EXPECTED_RESULT 2
  STDOUT_CONTAINS
    "CrossGL native compiler"
    "Usage:"
    "cglc build <input.cgl>"
    "cglc package inspect <out.cglb> --json")

crossgl_add_cli_surface_test(cglc_cli_unknown_command_fails
  EXPECTED_RESULT 2
  ARGS does-not-exist
  STDOUT_CONTAINS
    "Usage:"
  STDERR_CONTAINS
    "unknown command: does-not-exist")

crossgl_add_cli_surface_test(cglc_cli_help_lists_major_commands
  EXPECTED_RESULT 0
  ARGS --help
  STDOUT_CONTAINS
    "Usage:"
    "cglc doctor"
    "cglc targets"
    "cglc check"
    "cglc explain-targets"
    "cglc language-feature-report"
    "cglc dump-ir"
    "pseudo-mlir"
    "--stage mlir is a compatibility alias for pseudo-mlir"
    "output is not real MLIR"
    "hir-pass-trace"
    "cglc build"
    "cglc package inspect"
    "cglc package verify"
    "cglc package recover"
    "cglc package release"
    "cglc package maintain")

crossgl_add_cli_surface_test(cglc_cli_check_text_success_contract
  EXPECTED_RESULT 0
  ARGS check ${CROSSGL_SIMPLE_SHADER}
  STDOUT_CONTAINS
    "check passed:"
    "SimpleShader.cgl")

crossgl_add_cli_surface_test(cglc_cli_check_diagnostics_json_success_contract
  EXPECTED_RESULT 0
  ARGS check ${CROSSGL_SIMPLE_SHADER} --diagnostics-json
  STDOUT_CONTAINS
    "\"schemaVersion\": 1"
    "\"diagnostics\": []")

crossgl_add_cli_surface_test(cglc_cli_check_source_manifest_success_contract
  EXPECTED_RESULT 0
  ARGS check --source-manifest ${CROSSGL_CLI_SOURCE_BATCH_CHECK_MANIFEST}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"kind\": \"crossgl.sourceBatchResult\""
    "\"entryCount\": 3"
    "\"id\": \"simple\""
    "\"logicalInput\": \"translator/snapshots/SimpleShader.cgl\""
    "\"id\": \"fn-style\""
    "\"logicalInput\": \"translator/snapshots/FnStyleFunctionShader.cgl\""
    "\"id\": \"source-2\""
    "\"success\": true"
    "\"diagnostics\": []")

crossgl_add_cli_surface_test(cglc_cli_check_crosstl_project_report_source_batch_success_contract
  EXPECTED_RESULT 0
  ARGS check --source-batch ${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_LINE}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"kind\": \"crossgl.sourceBatchResult\""
    "\"entryCount\": 1"
    "\"id\": \"simple.cgl\""
    "\"logicalInput\": \"out/cgl/simple.cgl\""
    "\"sourceRemap\": \"${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_LINE_SOURCE_REMAP}\""
    "\"target\": \"auto\""
    "\"success\": true"
    "\"diagnostics\": []")

crossgl_add_python_expect_test(
  NAME cglc_cli_check_source_manifest_result_json_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DMODE=source-batch-check-json
    -DMANIFEST=${CROSSGL_CLI_SOURCE_BATCH_CHECK_MANIFEST}
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/source-batch-result-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|kind=crossgl.sourceBatchResult|success=true|entryCount=3|entries.0.id=simple|entries.0.logicalInput=translator/snapshots/SimpleShader.cgl|entries.0.target=auto|entries.0.success=true|entries.1.id=fn-style|entries.1.logicalInput=translator/snapshots/FnStyleFunctionShader.cgl|entries.1.target=auto|entries.1.success=true|entries.2.id=source-2|entries.2.target=auto|entries.2.success=true|diagnosticReport.schemaVersion=1"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=entries=3|diagnosticReport.diagnostics=0")

crossgl_add_python_expect_test(
  NAME cglc_cli_check_crosstl_project_report_source_batch_result_json_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DMODE=source-batch-check-json
    -DMANIFEST=${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_LINE}
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/source-batch-result-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|kind=crossgl.sourceBatchResult|success=true|entryCount=1|entries.0.id=simple.cgl|entries.0.logicalInput=out/cgl/simple.cgl|entries.0.sourceRemap=${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_LINE_SOURCE_REMAP}|entries.0.target=auto|entries.0.success=true|diagnosticReport.schemaVersion=1"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=entries=1|diagnosticReport.diagnostics=0")

crossgl_add_python_expect_test(
  NAME cglc_cli_check_crosstl_project_report_file_source_batch_result_json_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DMODE=source-batch-check-json
    -DMANIFEST=${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_FILE}
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/source-batch-result-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|kind=crossgl.sourceBatchResult|success=true|entryCount=1|entries.0.id=simple.cgl|entries.0.logicalInput=out/cgl/simple.cgl|entries.0.sourceRemap=${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_FILE_SOURCE_REMAP}|entries.0.target=auto|entries.0.success=true|diagnosticReport.schemaVersion=1"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=entries=1|diagnosticReport.diagnostics=0")

if(CROSSGL_PYTHON3)
  crossgl_add_python_expect_test(
    NAME cglc_cli_check_source_manifest_failure_result_json_schema
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DMODE=source-batch-check-json
      -DMANIFEST=${CROSSGL_CLI_SOURCE_BATCH_CHECK_FAILURE_MANIFEST}
      -DEXPECTED_RESULT=1
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/source-batch-result-v1.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|kind=crossgl.sourceBatchResult|success=false|entryCount=2|entries.0.id=simple|entries.0.target=auto|entries.0.success=true|entries.1.id=invalid-utf8|entries.1.logicalInput=translator/snapshots/InvalidUtf8SourceShader.cgl|entries.1.target=auto|entries.1.success=false|diagnosticReport.schemaVersion=1|diagnosticReport.diagnostics.0.severity=error|diagnosticReport.diagnostics.0.code=io.invalid-source-byte|diagnosticReport.diagnostics.0.location.file=translator/snapshots/InvalidUtf8SourceShader.cgl"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=entries=2|diagnosticReport.diagnostics=1")
endif()

crossgl_add_cli_surface_test(cglc_cli_check_crosstl_project_report_no_translated_fails
  EXPECTED_RESULT 1
  ARGS check --source-batch ${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_NO_TRANSLATED}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "CrossTL project report contains no translated cgl artifacts"
  STDERR_CONTAINS
    "error project.source-batch.invalid-manifest"
    "CrossTL project report contains no translated cgl artifacts")

crossgl_add_cli_surface_test(cglc_cli_check_crosstl_project_report_missing_source_remap_fails
  EXPECTED_RESULT 1
  ARGS check --source-batch ${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_MISSING_REMAP}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "sourceRemap expected translated cgl artifact to record metadata")

crossgl_add_cli_surface_test(cglc_cli_check_crosstl_project_report_remap_target_mismatch_fails
  EXPECTED_RESULT 1
  ARGS check --source-batch ${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_TARGET_MISMATCH}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "sourceRemap.target must match artifact target 'cgl'")

crossgl_add_cli_surface_test(cglc_cli_check_crosstl_project_report_remap_generated_mismatch_fails
  EXPECTED_RESULT 1
  ARGS check --source-batch ${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_GENERATED_MISMATCH}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "sourceRemap.generatedFile must match artifact path")

crossgl_add_cli_surface_test(cglc_cli_check_crosstl_project_report_self_remap_path_fails
  EXPECTED_RESULT 1
  ARGS check --source-batch ${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_SELF_REMAP_PATH}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "sourceRemap.path must reference a sidecar path")

crossgl_add_cli_surface_test(cglc_cli_check_crosstl_project_report_zero_mapping_count_fails
  EXPECTED_RESULT 1
  ARGS check --source-batch ${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_ZERO_MAPPING_COUNT}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "sourceRemap.mappingCount must be positive")

crossgl_add_cli_surface_test(cglc_cli_check_crosstl_project_report_stale_remap_hash_fails
  EXPECTED_RESULT 1
  ARGS check --source-batch ${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_STALE_REMAP_HASH}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "sourceRemap.hash.value does not match referenced sidecar")

crossgl_add_cli_surface_test(cglc_cli_build_crosstl_project_report_requires_output_fails
  EXPECTED_RESULT 1
  ARGS build --source-batch ${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_LINE}
  STDERR_CONTAINS
    "error project.source-batch.invalid-manifest"
    "source batch manifest sources[0] requires output for build"
    "set sources[].output or pass --output-dir")

crossgl_add_cli_surface_test(cglc_cli_build_crosstl_project_report_output_dir_success_contract
  EXPECTED_RESULT 0
  ARGS
    build --source-batch ${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_LINE}
    --target directx
    --output-dir ${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_BUILD_OUTPUT_DIR}
  STDOUT_CONTAINS
    "built "
    "cglc-cli-crosstl-project-report-build"
    "simple.cglb"
    "for directx"
    "batch build passed: 1 sources")

crossgl_add_python_expect_test(
  NAME cglc_cli_build_crosstl_project_report_output_dir_result_json_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DMODE=source-batch-build-json
    -DMANIFEST=${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_LINE}
    -DTARGET=directx
    -DOUTPUT_DIR=${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_BUILD_JSON_OUTPUT_DIR}
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/source-batch-result-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|kind=crossgl.sourceBatchResult|success=true|entryCount=1|entries.0.id=simple.cgl|entries.0.logicalInput=out/cgl/simple.cgl|entries.0.sourceRemap=${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_LINE_SOURCE_REMAP}|entries.0.output=${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_BUILD_JSON_OUTPUT_DIR}/out/cgl/simple.cglb|entries.0.artifact=${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_BUILD_JSON_OUTPUT_DIR}/out/cgl/simple.cglb|entries.0.target=directx|entries.0.success=true|diagnosticReport.schemaVersion=1"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=entries=1"
    "-DEXPECTED_SOURCE_BATCH_PACKAGE=${CROSSGL_CLI_CROSSTL_PROJECT_REPORT_BUILD_JSON_OUTPUT_DIR}/out/cgl/simple.cglb")

crossgl_add_cli_surface_test(cglc_cli_check_source_manifest_missing_path_fails
  EXPECTED_RESULT 2
  ARGS check --source-manifest
  STDERR_CONTAINS
    "--source-manifest requires a path")

crossgl_add_cli_surface_test(cglc_cli_check_source_manifest_unknown_top_level_fails
  EXPECTED_RESULT 1
  ARGS check --source-manifest
    ${CROSSGL_CLI_SOURCE_BATCH_UNKNOWN_TOP_LEVEL_MANIFEST}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "source batch manifest has unexpected property 'cacheKey'"
  STDERR_CONTAINS
    "source batch manifest has unexpected property 'cacheKey'")

crossgl_add_cli_surface_test(cglc_cli_check_source_manifest_unknown_source_field_fails
  EXPECTED_RESULT 1
  ARGS check --source-manifest
    ${CROSSGL_CLI_SOURCE_BATCH_UNKNOWN_SOURCE_FIELD_MANIFEST}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "source batch manifest sources[0] has unexpected property 'backend'"
  STDERR_CONTAINS
    "source batch manifest sources[0] has unexpected property 'backend'")

crossgl_add_cli_surface_test(cglc_cli_check_source_manifest_bad_default_type_fails
  EXPECTED_RESULT 1
  ARGS check --source-manifest
    ${CROSSGL_CLI_SOURCE_BATCH_BAD_DEFAULT_TYPE_MANIFEST}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "source batch manifest defaults.debugIR must be a boolean"
  STDERR_CONTAINS
    "source batch manifest defaults.debugIR must be a boolean")

crossgl_add_cli_surface_test(cglc_cli_check_source_manifest_logical_input_absolute_fails
  EXPECTED_RESULT 1
  ARGS check --source-manifest
    ${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_ABSOLUTE_MANIFEST}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "source batch manifest sources[0].logicalInput must be a stable relative path"
  STDERR_CONTAINS
    "source batch manifest sources[0].logicalInput must be a stable relative path")

crossgl_add_cli_surface_test(cglc_cli_check_source_manifest_logical_path_parent_segment_fails
  EXPECTED_RESULT 1
  ARGS check --source-manifest
    ${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_PATH_PARENT_SEGMENT_MANIFEST}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "source batch manifest sources[0].logicalPath must be a stable relative path"
  STDERR_CONTAINS
    "source batch manifest sources[0].logicalPath must be a stable relative path")

crossgl_add_cli_surface_test(cglc_cli_check_source_manifest_logical_input_drive_prefix_fails
  EXPECTED_RESULT 1
  ARGS check --source-manifest
    ${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_DRIVE_PREFIX_MANIFEST}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "source batch manifest sources[0].logicalInput must be a stable relative path"
  STDERR_CONTAINS
    "source batch manifest sources[0].logicalInput must be a stable relative path")

crossgl_add_cli_surface_test(cglc_cli_check_source_manifest_logical_input_backslash_fails
  EXPECTED_RESULT 1
  ARGS check --source-manifest
    ${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_BACKSLASH_MANIFEST}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "source batch manifest sources[0].logicalInput must be a stable relative path"
  STDERR_CONTAINS
    "source batch manifest sources[0].logicalInput must be a stable relative path")

crossgl_add_cli_surface_test(cglc_cli_check_source_manifest_logical_input_empty_segment_fails
  EXPECTED_RESULT 1
  ARGS check --source-manifest
    ${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_EMPTY_SEGMENT_MANIFEST}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "source batch manifest sources[0].logicalInput must be a stable relative path"
  STDERR_CONTAINS
    "source batch manifest sources[0].logicalInput must be a stable relative path")

crossgl_add_cli_surface_test(cglc_cli_check_source_manifest_logical_input_current_segment_fails
  EXPECTED_RESULT 1
  ARGS check --source-manifest
    ${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_CURRENT_SEGMENT_MANIFEST}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "source batch manifest sources[0].logicalInput must be a stable relative path"
  STDERR_CONTAINS
    "source batch manifest sources[0].logicalInput must be a stable relative path")

crossgl_add_cli_surface_test(cglc_cli_check_source_manifest_logical_path_alias_invalid_fails
  EXPECTED_RESULT 1
  ARGS check --source-manifest
    ${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_PATH_ALIAS_INVALID_MANIFEST}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "source batch manifest sources[0].logicalPath must be a stable relative path"
  STDERR_CONTAINS
    "source batch manifest sources[0].logicalPath must be a stable relative path")

crossgl_add_cli_surface_test(cglc_cli_build_source_manifest_logical_input_drive_prefix_fails
  EXPECTED_RESULT 1
  ARGS build --source-batch
    ${CROSSGL_CLI_SOURCE_BATCH_LOGICAL_INPUT_DRIVE_PREFIX_MANIFEST}
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"project.source-batch.invalid-manifest\""
    "source batch manifest sources[0].logicalInput must be a stable relative path"
  STDERR_CONTAINS
    "source batch manifest sources[0].logicalInput must be a stable relative path")

crossgl_add_cli_surface_test(cglc_cli_check_missing_input_diagnostics_json
  EXPECTED_RESULT 1
  ARGS check ${CROSSGL_CLI_MISSING_INPUT_SHADER} --diagnostics-json
  STDOUT_CONTAINS
    "\"schemaVersion\": 1"
    "\"code\": \"io.read-failed\""
    "\"file\": \"${CROSSGL_CLI_MISSING_INPUT_JSON_FILE}\""
  STDERR_CONTAINS
    "${CROSSGL_CLI_MISSING_INPUT_JSON_FILE}:1:1: error io.read-failed")

if(CROSSGL_PYTHON3)
  crossgl_add_cli_surface_test(cglc_cli_check_leading_bom_source_success
    EXPECTED_RESULT 0
    ARGS check ${CROSSGL_CLI_LEADING_BOM_SHADER}
    STDOUT_CONTAINS
      "check passed:"
      "${CROSSGL_CLI_LEADING_BOM_JSON_FILE}")

  crossgl_add_cli_surface_test(cglc_cli_check_nul_source_diagnostics_json
    EXPECTED_RESULT 1
    ARGS check ${CROSSGL_CLI_NUL_SOURCE_SHADER} --diagnostics-json
    STDOUT_CONTAINS
      "\"schemaVersion\": 1"
      "\"code\": \"io.invalid-source-byte\""
      "\"message\": \"source contains an embedded NUL byte\""
      "\"file\": \"${CROSSGL_CLI_NUL_SOURCE_JSON_FILE}\""
    STDERR_CONTAINS
      "${CROSSGL_CLI_NUL_SOURCE_JSON_FILE}:7:1: error io.invalid-source-byte")

  crossgl_add_cli_surface_test(cglc_cli_check_invalid_source_bytes_diagnostics_json
    EXPECTED_RESULT 1
    ARGS check ${CROSSGL_CLI_INVALID_UTF8_SHADER} --diagnostics-json
    STDOUT_CONTAINS
      "\"schemaVersion\": 1"
      "\"code\": \"io.invalid-source-byte\""
      "\"message\": \"source contains invalid UTF-8 byte 0xFF\""
      "\"file\": \"${CROSSGL_CLI_INVALID_UTF8_JSON_FILE}\""
    STDERR_CONTAINS
      "${CROSSGL_CLI_INVALID_UTF8_JSON_FILE}:7:1: error io.invalid-source-byte")

  crossgl_add_cli_surface_test(cglc_cli_check_logical_input_diagnostics_json
    EXPECTED_RESULT 1
    ARGS check ${CROSSGL_CLI_INVALID_UTF8_SHADER}
      --logical-input generated/from-translator.cgl
      --diagnostics-json
    STDOUT_CONTAINS
      "\"schemaVersion\": 1"
      "\"code\": \"io.invalid-source-byte\""
      "\"file\": \"generated/from-translator.cgl\""
    STDERR_CONTAINS
      "generated/from-translator.cgl:7:1: error io.invalid-source-byte")

  crossgl_add_cli_surface_test(cglc_cli_check_source_remap_diagnostics_json
    EXPECTED_RESULT 1
    ARGS check ${CROSSGL_CLI_INVALID_UTF8_SHADER}
      --logical-input generated/from-translator.cgl
      --source-remap ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-basic.json
      --diagnostics-json
    STDOUT_CONTAINS
      "\"schemaVersion\": 1"
      "\"code\": \"io.invalid-source-byte\""
      "\"file\": \"generated/from-translator.cgl\""
      "\"originalLocation\""
      "\"file\": \"shaders/original.crossgl\""
      "\"line\": 42"
      "\"column\": 9"
    STDERR_CONTAINS
      "shaders/original.crossgl:42:9: error io.invalid-source-byte")

  crossgl_add_cli_surface_test(cglc_cli_build_source_remap_diagnostics_json
    EXPECTED_RESULT 1
    ARGS build ${CROSSGL_CLI_INVALID_UTF8_SHADER}
      --target directx
      --output ${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-build-source-remap-diagnostics.cglb
      --logical-input generated/from-translator.cgl
      --source-remap ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-basic.json
      --diagnostics-json
    STDOUT_CONTAINS
      "\"schemaVersion\": 1"
      "\"code\": \"io.invalid-source-byte\""
      "\"file\": \"generated/from-translator.cgl\""
      "\"originalLocation\""
      "\"file\": \"shaders/original.crossgl\""
      "\"line\": 42"
      "\"column\": 9"
    STDERR_CONTAINS
      "shaders/original.crossgl:42:9: error io.invalid-source-byte")
endif()

crossgl_add_cli_surface_test(cglc_cli_check_source_remap_logical_input_mismatch
  EXPECTED_RESULT 1
  ARGS check ${CROSSGL_SIMPLE_SHADER}
    --logical-input generated/other-source.cgl
    --source-remap ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-basic.json
    --diagnostics-json
  STDOUT_CONTAINS
    "\"schemaVersion\": 1"
    "\"code\": \"io.invalid-source-remap\""
    "source remap generatedFile 'generated/from-translator.cgl' must match compiler input path 'generated/other-source.cgl'"
  STDERR_CONTAINS
    "error io.invalid-source-remap"
    "source remap generatedFile 'generated/from-translator.cgl' must match compiler input path 'generated/other-source.cgl'")

crossgl_add_cli_surface_test(cglc_cli_dump_ir_source_remap_logical_input_mismatch
  EXPECTED_RESULT 1
  ARGS dump-ir ${CROSSGL_SIMPLE_SHADER}
    --stage hir-source-map
    --logical-input generated/other-source.cgl
    --source-remap ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-basic.json
  STDERR_CONTAINS
    "error io.invalid-source-remap"
    "source remap generatedFile 'generated/from-translator.cgl' must match compiler input path 'generated/other-source.cgl'")

crossgl_add_cli_surface_test(cglc_cli_check_crosstl_project_source_remap_sidecar
  EXPECTED_RESULT 0
  ARGS check ${CROSSGL_SIMPLE_SHADER}
    --logical-input out/cgl/simple.cgl
    --source-remap ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-crosstl-project-line.json
  STDOUT_CONTAINS
    "check passed:")

crossgl_add_cli_surface_test(cglc_cli_check_crosstl_project_file_source_remap_sidecar
  EXPECTED_RESULT 0
  ARGS check ${CROSSGL_SIMPLE_SHADER}
    --logical-input out/cgl/simple.cgl
    --source-remap ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-crosstl-project-file.json
  STDOUT_CONTAINS
    "check passed:")

crossgl_add_cli_surface_test(cglc_cli_check_crosstl_project_source_remap_metadata_resolves
  EXPECTED_RESULT 0
  ARGS check ${CROSSGL_SIMPLE_SHADER}
    --logical-input out/cgl/simple.cgl
    --source-remap ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-crosstl-project-report-metadata.json
  STDOUT_CONTAINS
    "check passed:")

crossgl_add_cli_surface_test(cglc_cli_check_crosstl_project_source_remap_metadata_missing_sidecar_fails
  EXPECTED_RESULT 1
  ARGS check ${CROSSGL_SIMPLE_SHADER}
    --logical-input out/cgl/simple.cgl
    --source-remap ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-crosstl-project-report-metadata-missing-sidecar.json
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"io.read-failed\""
    "out/cgl/missing.source-remap.json"
  STDERR_CONTAINS
    "error io.read-failed"
    "out/cgl/missing.source-remap.json")

crossgl_add_cli_surface_test(cglc_cli_check_crosstl_project_report_as_source_remap_fails
  EXPECTED_RESULT 1
  ARGS check ${CROSSGL_SIMPLE_SHADER}
    --logical-input out/cgl/simple.cgl
    --source-remap ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/crosstl-project-portability-report-v1-basic.json
    --diagnostics-json
  STDOUT_CONTAINS
    "\"code\": \"io.invalid-source-remap\""
    "source remap document appears to be a CrossTL project portability report"
    "artifacts[].sourceRemap.path"
  STDERR_CONTAINS
    "error io.invalid-source-remap"
    "pass the compiler sidecar JSON referenced by artifacts[].sourceRemap.path instead")

crossgl_add_cli_surface_test(cglc_cli_dump_ir_default_stage_hir_contract
  EXPECTED_RESULT 0
  ARGS dump-ir ${CROSSGL_SIMPLE_SHADER}
  STDOUT_CONTAINS
    "module SimpleShader")

crossgl_add_cli_surface_test(cglc_cli_dump_ir_hir_pass_trace_contract
  EXPECTED_RESULT 0
  ARGS dump-ir ${CROSSGL_SIMPLE_SHADER} --stage hir-pass-trace
  STDOUT_CONTAINS
    "\"schemaVersion\": 1"
    "\"kind\": \"hir-pass-trace\""
    "\"passCount\": 10"
    "\"name\": \"hir.validate.module-shape\""
    "\"name\": \"hir.optimize.fold-constant-intrinsics\""
    "\"name\": \"hir.validate.storage-buffer-shapes\"")

crossgl_add_cli_surface_test(cglc_cli_dump_ir_invalid_stage_fails
  EXPECTED_RESULT 2
  ARGS dump-ir ${CROSSGL_SIMPLE_SHADER} --stage no-such-stage
  STDERR_CONTAINS
    "error: unknown dump stage"
    "hir-pass-trace")

crossgl_add_cli_surface_test(cglc_cli_dump_ir_batch_manifest_deferred
  EXPECTED_RESULT 2
  ARGS dump-ir ${CROSSGL_SIMPLE_SHADER} --stage hir
    --batch-manifest repo-sources.json
  STDERR_CONTAINS
    "--batch-manifest source manifest mode is supported for check and build"
    "dump-ir must still be invoked per source")

crossgl_add_cli_surface_test(cglc_cli_explain_targets_json_contract
  EXPECTED_RESULT 0
  ARGS explain-targets ${CROSSGL_SIMPLE_SHADER}
  STDOUT_CONTAINS
    "\"schemaVersion\": 1"
    "\"module\": \"SimpleShader\""
    "\"targets\": [")

crossgl_add_cli_surface_test(cglc_cli_explain_targets_batch_manifest_deferred
  EXPECTED_RESULT 2
  ARGS explain-targets ${CROSSGL_SIMPLE_SHADER} --manifest repo-sources.json
  STDERR_CONTAINS
    "--manifest source manifest mode is supported for check and build"
    "explain-targets must still be invoked per source")

if(CROSSGL_PYTHON3)
  crossgl_add_cli_surface_test(cglc_cli_explain_targets_logical_input_diagnostics
    EXPECTED_RESULT 1
    ARGS explain-targets ${CROSSGL_CLI_INVALID_UTF8_SHADER}
      --logical-input generated/from-translator.cgl
    STDERR_CONTAINS
      "generated/from-translator.cgl:7:1: error io.invalid-source-byte"
      "source contains invalid UTF-8 byte 0xFF")
endif()

crossgl_add_cli_surface_test(cglc_cli_explain_targets_missing_input_fails
  EXPECTED_RESULT 2
  ARGS explain-targets
  STDOUT_CONTAINS
    "Usage:"
    "cglc explain-targets <input.cgl> [--logical-input <path>]")

crossgl_add_cli_surface_test(cglc_cli_doctor_text_toolchain_contract
  EXPECTED_RESULT 0
  ARGS doctor
  STDOUT_CONTAINS
    "Host:"
    "Default target:"
    "Tools:"
    "probe=")

crossgl_add_cli_surface_test(cglc_cli_doctor_json_toolchain_contract
  EXPECTED_RESULT 0
  ARGS doctor --json
  STDOUT_CONTAINS
    "\"schemaVersion\": 1"
    "\"toolchain\":"
    "\"evidenceStatus\":"
    "\"source\":"
    "\"probeStatus\":"
    "\"targetExplanation\": null")

crossgl_add_cli_surface_test(cglc_cli_doctor_batch_manifest_deferred
  EXPECTED_RESULT 2
  ARGS doctor ${CROSSGL_SIMPLE_SHADER} --batch repo-sources.json
  STDERR_CONTAINS
    "--batch source manifest mode is supported for check and build"
    "doctor must still be invoked per source")

crossgl_add_cli_surface_test(cglc_cli_language_feature_report_batch_manifest_deferred
  EXPECTED_RESULT 2
  ARGS language-feature-report ${CROSSGL_SIMPLE_SHADER}
    --batch-manifest crosstl-project-portability-report.json
  STDERR_CONTAINS
    "--batch-manifest source manifest mode is supported for check and build"
    "language-feature-report must still be invoked per source")

crossgl_add_cli_surface_test(cglc_cli_build_directx_source_package_success_contract
  EXPECTED_RESULT 0
  ARGS
    build ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    --target directx
    --output ${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-build-directx-success.cglb
  STDOUT_CONTAINS
    "built "
    " for directx")

crossgl_add_cli_surface_test(cglc_cli_build_vulkan_unsupported_diagnostics_json_contract
  EXPECTED_RESULT 1
  ARGS
    build ${CROSSGL_VULKAN_RUNTIME_TEXTURE_DESCRIPTOR_ARRAY_CONFLICT_SHADER}
    --target vulkan
    --output ${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-build-vulkan-unsupported.cglb
    --diagnostics-json
  STDOUT_CONTAINS
    "\"schemaVersion\": 1"
    "\"code\": \"target.unsupported\""
    "\"target\": \"vulkan\""
    "vulkan.backend.vulkan-prototype-package"
  STDERR_CONTAINS
    "target.unsupported")

crossgl_add_cli_surface_test(cglc_cli_build_missing_input_fails
  EXPECTED_RESULT 2
  ARGS build
  STDOUT_CONTAINS
    "Usage:"
    "cglc build <input.cgl>")

crossgl_add_cli_surface_test(cglc_cli_build_source_manifest_success_contract
  EXPECTED_RESULT 0
  ARGS
    build --source-batch ${CROSSGL_CLI_SOURCE_BATCH_BUILD_MANIFEST}
  STDOUT_CONTAINS
    "built "
    "cglc-cli-batch-storage.cglb"
    "cglc-cli-batch-fn-style.cglb"
    "for directx"
    "batch build passed: 2 sources")

crossgl_add_python_expect_test(
  NAME cglc_cli_build_source_manifest_result_json_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DMODE=source-batch-build-json
    -DMANIFEST=${CROSSGL_CLI_SOURCE_BATCH_BUILD_JSON_MANIFEST}
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/source-batch-result-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|kind=crossgl.sourceBatchResult|success=true|entryCount=2|entries.0.id=storage|entries.0.output=${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-json-storage.cglb|entries.0.artifact=${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-json-storage.cglb|entries.0.target=directx|entries.0.success=true|entries.1.id=fn-style|entries.1.output=${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-json-fn-style.cglb|entries.1.artifact=${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-json-fn-style.cglb|entries.1.target=directx|entries.1.success=true|diagnosticReport.schemaVersion=1"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=entries=2")

crossgl_add_python_expect_test(
  NAME cglc_cli_build_source_manifest_source_remap_result_json_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DMODE=source-batch-build-json
    -DMANIFEST=${CROSSGL_CLI_SOURCE_BATCH_BUILD_REMAP_JSON_MANIFEST}
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/source-batch-result-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|kind=crossgl.sourceBatchResult|success=true|entryCount=1|entries.0.id=storage-remapped|entries.0.logicalInput=generated/from-translator.cgl|entries.0.sourceRemap=${CROSSGL_CLI_SOURCE_BATCH_FULL_FILE_REMAP}|entries.0.output=${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-remap-storage.cglb|entries.0.artifact=${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-remap-storage.cglb|entries.0.target=directx|entries.0.success=true|diagnosticReport.schemaVersion=1|diagnosticReport.diagnostics.0.severity=note|diagnosticReport.diagnostics.0.code=directx.source-package-emitted|diagnosticReport.diagnostics.1.severity=warning|diagnosticReport.diagnostics.1.code=directx.source-package-only"
    "-DEXPECTED_JSON_ARRAY_LENGTHS=entries=1|diagnosticReport.diagnostics=2"
    "-DEXPECTED_SOURCE_BATCH_PACKAGE=${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-remap-storage.cglb"
    "-DEXPECTED_SOURCE_REMAP_PROVENANCE_JSON_FIELDS=schemaVersion=1|kind=crossgl.sourceRemapProvenance|contractVersion=source-remap-provenance-v1|target=directx|generatedFile=generated/from-translator.cgl|mappingGranularity=source-span|mappingCount=1"
    -DSOURCE_REMAP_PROVENANCE_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/source-remap-provenance-v1.schema.json
    "-DEXPECTED_PACKAGE_INSPECT_JSON_FIELDS=summary.artifactCount=8|debugArtifacts.backendSourceMap.artifactPresent=true|debugArtifacts.backendSourceMap.exists=true|debugArtifacts.backendSourceMap.health=ok|debugArtifacts.backendSourceMap.path=backend/directx/StorageBufferComputeShader.backend-source-map.json|debugArtifacts.backendSourceMap.kind=crossgl.backendSourceMap|debugArtifacts.backendSourceMap.target=directx|debugArtifacts.backendSourceMap.module=StorageBufferComputeShader|debugArtifacts.backendSourceMap.checks.identityMatchesContract=true|debugArtifacts.backendSourceMap.checks.targetMatchesPackage=true|debugArtifacts.backendSourceMap.checks.moduleMatchesPackage=true|debugArtifacts.backendSourceMap.checks.mappingCountMatchesMappings=true|debugArtifacts.sourceRemap.artifactPresent=true|debugArtifacts.sourceRemap.exists=true|debugArtifacts.sourceRemap.health=ok|debugArtifacts.sourceRemap.generatedFile=generated/from-translator.cgl|debugArtifacts.sourceRemap.mappingCount=1|debugArtifacts.sourceRemap.checks.identityMatchesContract=true|debugArtifacts.sourceRemap.checks.targetMatchesPackage=true|debugArtifacts.sourceRemap.checks.mappingGranularityMatchesContract=true|debugArtifacts.sourceRemap.checks.sourceHashPresent=true"
    -DPACKAGE_INSPECT_JSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json)

if(CROSSGL_PYTHON3)
  crossgl_add_python_expect_test(
    NAME cglc_cli_build_source_manifest_failure_result_json_schema
    DEFINITIONS
      -DCGLC=$<TARGET_FILE:cglc>
      -DMODE=source-batch-build-json
      -DMANIFEST=${CROSSGL_CLI_SOURCE_BATCH_BUILD_FAILURE_MANIFEST}
      -DEXPECTED_RESULT=1
      -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/source-batch-result-v1.schema.json
      -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
      "-DEXPECTED_JSON_FIELDS=schemaVersion=1|kind=crossgl.sourceBatchResult|success=false|entryCount=2|entries.0.id=invalid-utf8|entries.0.logicalInput=translator/snapshots/InvalidUtf8SourceShader.cgl|entries.0.output=${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-invalid-utf8.cglb|entries.0.target=directx|entries.0.success=false|entries.1.id=storage|entries.1.output=${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-partial-storage.cglb|entries.1.artifact=${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-batch-partial-storage.cglb|entries.1.target=directx|entries.1.success=true|diagnosticReport.schemaVersion=1|diagnosticReport.diagnostics.0.severity=error|diagnosticReport.diagnostics.0.code=io.invalid-source-byte|diagnosticReport.diagnostics.0.location.file=translator/snapshots/InvalidUtf8SourceShader.cgl"
      "-DEXPECTED_JSON_ARRAY_LENGTHS=entries=2")
endif()

crossgl_add_cli_surface_test(cglc_cli_build_source_manifest_output_option_fails
  EXPECTED_RESULT 2
  ARGS
    build --source-batch ${CROSSGL_CLI_SOURCE_BATCH_BUILD_MANIFEST}
    --output ${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-build-batch-output.cglb
  STDERR_CONTAINS
    "--output is per-source in source manifest mode")

crossgl_add_cli_surface_test(cglc_cli_build_source_remap_logical_input_mismatch
  EXPECTED_RESULT 1
  ARGS
    build ${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    --target directx
    --output ${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-build-source-remap-mismatch.cglb
    --logical-input generated/other-source.cgl
    --source-remap ${CMAKE_CURRENT_SOURCE_DIR}/tests/fixtures/source-remap-v1-basic.json
    --diagnostics-json
  STDOUT_CONTAINS
    "\"schemaVersion\": 1"
    "\"code\": \"io.invalid-source-remap\""
    "source remap generatedFile 'generated/from-translator.cgl' must match compiler input path 'generated/other-source.cgl'"
  STDERR_CONTAINS
    "error io.invalid-source-remap"
    "source remap generatedFile 'generated/from-translator.cgl' must match compiler input path 'generated/other-source.cgl'")

crossgl_add_cli_surface_test(cglc_cli_package_inspect_requires_json
  EXPECTED_RESULT 2
  ARGS package inspect placeholder.cglb
  STDERR_CONTAINS
    "error: package inspect currently requires --json")

crossgl_add_cli_surface_test(cglc_cli_package_inspect_missing_path_fails
  EXPECTED_RESULT 2
  ARGS package inspect --json
  STDOUT_CONTAINS
    "Usage:"
    "cglc package inspect <out.cglb> --json")

crossgl_add_cli_surface_test(cglc_cli_package_verify_missing_path_fails
  EXPECTED_RESULT 2
  ARGS package verify
  STDOUT_CONTAINS
    "Usage:"
    "cglc package verify <out.cglb>")

crossgl_add_cli_surface_test(cglc_cli_package_recover_missing_action_fails
  EXPECTED_RESULT 2
  ARGS package recover placeholder.cglb
  STDERR_CONTAINS
    "error: package recover requires exactly one of --promote or --discard")

crossgl_add_cli_surface_test(cglc_cli_package_maintain_missing_scan_dir_fails
  EXPECTED_RESULT 2
  ARGS package maintain --scan
  STDERR_CONTAINS
    "error: --scan requires a directory")

crossgl_add_cli_surface_test(cglc_cli_package_release_missing_manifest_output_fails
  EXPECTED_RESULT 2
  ARGS package release --promotion-summary summary.json
  STDERR_CONTAINS
    "error: package release requires --manifest-output")

crossgl_add_python_expect_test(
  NAME cglc_cli_package_inspect_json_success_contract
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-package-inspect-success.cglb
    -DMODE=package-inspect-source-package
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=StorageBufferComputeShader|summary.target=directx|summary.debugArtifactsPresent=true")

crossgl_add_python_expect_test(
  NAME cglc_cli_package_inspect_storage_image_access_json_schema
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_DIRECTX_STORAGE_IMAGE_ACCESS_QUALIFIER_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-package-inspect-storage-image-access.cglb
    -DMODE=package-inspect-source-package
    -DJSON_SCHEMA=${CMAKE_CURRENT_SOURCE_DIR}/docs/schemas/package-inspect-v1.schema.json
    -DJSON_SCHEMA_VALIDATOR=${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_json_schema.py
    "-DEXPECTED_JSON_FIELDS=schemaVersion=1|packageFormat=directory|summary.module=DirectXStorageImageAccessQualifierShader|summary.target=directx|reflection.resources.0.storageImageAccess=read|reflection.resources.1.storageImageAccess=write|reflection.resources.2.storageImageAccess=read_write|reflection.targetResourceBindings.0.storageImageAccess=read|reflection.targetResourceBindings.1.storageImageAccess=write|reflection.targetResourceBindings.2.storageImageAccess=read_write|reflection.targetResourceBindings.2.evidenceId=target-legalization.v1.directx.resource-binding.compute.compute_main.readWriteColor|reflection.targetFeatures.6.name=storage-image|reflection.targetFeatures.6.evidenceIds.0=target-legalization.v1.directx.capability.required.directx.resource.storage-image")

crossgl_add_python_expect_test(
  NAME cglc_cli_package_verify_text_success_contract
  DEFINITIONS
    -DCGLC=$<TARGET_FILE:cglc>
    -DINPUT=${CROSSGL_STORAGE_BUFFER_COMPUTE_SHADER}
    -DTARGET=directx
    -DOUTPUT=${CMAKE_CURRENT_BINARY_DIR}/cglc-cli-package-verify-success.cglb
    -DMODE=package-verify-text
    "-DMUST_CONTAIN=verified package .*StorageBufferComputeShader.* for directx")
