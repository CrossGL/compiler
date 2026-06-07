if(POLICY CMP0054)
  cmake_policy(SET CMP0054 NEW)
endif()

foreach(required_var IN ITEMS CGLC INPUT OUTPUT EXPECTED_MODULE DXC)
  if(NOT DEFINED ${required_var} OR "${${required_var}}" STREQUAL "")
    message(FATAL_ERROR "DirectX toolchain smoke requires ${required_var}")
  endif()
endforeach()

function(crossgl_directx_smoke_run result_var stdout_var stderr_var)
  execute_process(
    COMMAND ${ARGN}
    RESULT_VARIABLE command_result
    OUTPUT_VARIABLE command_stdout
    ERROR_VARIABLE command_stderr)
  set(${result_var} "${command_result}" PARENT_SCOPE)
  set(${stdout_var} "${command_stdout}" PARENT_SCOPE)
  set(${stderr_var} "${command_stderr}" PARENT_SCOPE)
endfunction()

function(crossgl_directx_smoke_normalize_expected value out_var)
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

function(crossgl_directx_smoke_expect_json_field json path expected)
  string(REPLACE "." ";" json_path "${path}")
  string(JSON actual ERROR_VARIABLE json_error GET "${json}" ${json_path})
  if(NOT json_error STREQUAL "NOTFOUND")
    message(FATAL_ERROR
            "expected JSON field '${path}', but lookup failed: ${json_error}. "
            "Output: ${json}")
  endif()
  crossgl_directx_smoke_normalize_expected("${expected}" normalized_expected)
  if(NOT actual STREQUAL "${normalized_expected}")
    message(FATAL_ERROR
            "expected JSON field '${path}' to equal '${expected}', got "
            "'${actual}'. Output: ${json}")
  endif()
endfunction()

function(crossgl_directx_smoke_expect_nonempty_file path description)
  if(NOT EXISTS "${path}")
    message(FATAL_ERROR "expected ${description} at ${path}")
  endif()
  file(SIZE "${path}" file_size)
  if(file_size EQUAL 0)
    message(FATAL_ERROR "expected non-empty ${description} at ${path}")
  endif()
endfunction()

get_filename_component(dxc_dir "${DXC}" DIRECTORY)
if(WIN32)
  set(path_separator ";")
else()
  set(path_separator ":")
endif()
set(ENV{PATH} "${dxc_dir}${path_separator}$ENV{PATH}")
set(ENV{CROSSGL_DISABLE_TOOLCHAIN_FALLBACKS} "1")

file(REMOVE_RECURSE "${OUTPUT}")
crossgl_directx_smoke_run(
  build_result build_stdout build_stderr
  "${CGLC}" build "${INPUT}" --target directx --output "${OUTPUT}" --debug-ir
  --diagnostics-json)
if(NOT "${build_result}" STREQUAL "0")
  message(FATAL_ERROR
          "real DirectX/DXC toolchain smoke failed while building ${INPUT}.\n"
          "dxc: ${DXC}\n"
          "package: ${OUTPUT}\n"
          "stdout:\n${build_stdout}\n"
          "stderr:\n${build_stderr}")
endif()

set(hlsl_source
    "${OUTPUT}/backend/directx/${EXPECTED_MODULE}.hlsl")
set(dxil_file
    "${OUTPUT}/backend/directx/${EXPECTED_MODULE}.dxil")
set(manifest_file "${OUTPUT}/manifest.json")
set(diagnostics_file "${OUTPUT}/diagnostics.json")

crossgl_directx_smoke_expect_nonempty_file("${hlsl_source}"
                                           "generated HLSL source")
crossgl_directx_smoke_expect_nonempty_file("${dxil_file}"
                                           "generated DXIL binary")
crossgl_directx_smoke_expect_nonempty_file("${manifest_file}"
                                           "DirectX manifest")
crossgl_directx_smoke_expect_nonempty_file("${diagnostics_file}"
                                           "DirectX diagnostics")

file(READ "${manifest_file}" manifest_json)
crossgl_directx_smoke_expect_json_field("${manifest_json}" "target"
                                        "directx")
crossgl_directx_smoke_expect_json_field("${manifest_json}" "module"
                                        "${EXPECTED_MODULE}")
crossgl_directx_smoke_expect_json_field("${manifest_json}"
                                        "artifacts.nativeBinaryStatus"
                                        "emitted")

file(READ "${diagnostics_file}" diagnostics_json)
crossgl_directx_smoke_expect_json_field("${diagnostics_json}"
                                        "diagnostics.1.code"
                                        "directx.dxil-emitted")

crossgl_directx_smoke_run(
  inspect_result inspect_stdout inspect_stderr
  "${CGLC}" package inspect "${OUTPUT}" --json)
if(NOT "${inspect_result}" STREQUAL "0")
  message(FATAL_ERROR
          "package inspect failed after DirectX/DXC toolchain smoke build.\n"
          "package: ${OUTPUT}\n"
          "stdout:\n${inspect_stdout}\n"
          "stderr:\n${inspect_stderr}")
endif()
crossgl_directx_smoke_expect_json_field("${inspect_stdout}" "schemaVersion"
                                        "1")
crossgl_directx_smoke_expect_json_field("${inspect_stdout}" "packageFormat"
                                        "directory")
crossgl_directx_smoke_expect_json_field("${inspect_stdout}" "summary.target"
                                        "directx")
crossgl_directx_smoke_expect_json_field("${inspect_stdout}"
                                        "summary.nativeBinaryStatus"
                                        "emitted")
crossgl_directx_smoke_expect_json_field("${inspect_stdout}"
                                        "artifacts.1.name" "nativeBinary")
crossgl_directx_smoke_expect_json_field("${inspect_stdout}"
                                        "artifacts.1.path"
                                        "backend/directx/${EXPECTED_MODULE}.dxil")
crossgl_directx_smoke_expect_json_field("${inspect_stdout}"
                                        "artifacts.1.exists" "true")
crossgl_directx_smoke_expect_json_field("${inspect_stdout}"
                                        "manifest.artifacts.nativeBinaryStatus"
                                        "emitted")

crossgl_directx_smoke_run(
  verify_result verify_stdout verify_stderr
  "${CGLC}" package verify "${OUTPUT}" --source "${INPUT}" --json)
if(NOT "${verify_result}" STREQUAL "0")
  message(FATAL_ERROR
          "package verify failed after DirectX/DXC toolchain smoke build.\n"
          "package: ${OUTPUT}\n"
          "stdout:\n${verify_stdout}\n"
          "stderr:\n${verify_stderr}")
endif()
crossgl_directx_smoke_expect_json_field("${verify_stdout}" "success" "true")
crossgl_directx_smoke_expect_json_field("${verify_stdout}" "summary.target"
                                        "directx")
crossgl_directx_smoke_expect_json_field("${verify_stdout}"
                                        "summary.nativeBinaryStatus"
                                        "emitted")

message(STATUS "DirectX/DXC toolchain smoke produced ${dxil_file}")
