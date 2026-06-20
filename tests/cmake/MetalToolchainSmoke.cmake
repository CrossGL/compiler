if(POLICY CMP0054)
  cmake_policy(SET CMP0054 NEW)
endif()

foreach(required_var IN ITEMS CGLC INPUT OUTPUT EXPECTED_MODULE XCRUN)
  if(NOT DEFINED ${required_var} OR "${${required_var}}" STREQUAL "")
    message(FATAL_ERROR "Metal toolchain smoke requires ${required_var}")
  endif()
endforeach()

function(crossgl_metal_smoke_trim input out_var)
  string(STRIP "${input}" trimmed)
  set(${out_var} "${trimmed}" PARENT_SCOPE)
endfunction()

function(crossgl_metal_smoke_run result_var stdout_var stderr_var)
  execute_process(
    COMMAND ${ARGN}
    RESULT_VARIABLE command_result
    OUTPUT_VARIABLE command_stdout
    ERROR_VARIABLE command_stderr)
  set(${result_var} "${command_result}" PARENT_SCOPE)
  set(${stdout_var} "${command_stdout}" PARENT_SCOPE)
  set(${stderr_var} "${command_stderr}" PARENT_SCOPE)
endfunction()

function(crossgl_metal_smoke_find_tool tool_name out_var)
  crossgl_metal_smoke_run(find_result find_stdout find_stderr
                          "${XCRUN}" -find "${tool_name}")
  crossgl_metal_smoke_trim("${find_stdout}" tool_path)
  if(NOT "${find_result}" STREQUAL "0" OR tool_path STREQUAL "")
    message(FATAL_ERROR
            "xcrun could not locate ${tool_name} for the Metal toolchain smoke.\n"
            "xcrun: ${XCRUN}\n"
            "stdout:\n${find_stdout}\n"
            "stderr:\n${find_stderr}")
  endif()
  set(${out_var} "${tool_path}" PARENT_SCOPE)
endfunction()

function(crossgl_metal_smoke_normalize_expected value out_var)
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

function(crossgl_metal_smoke_expect_json_field json path expected)
  string(REPLACE "." ";" json_path "${path}")
  string(JSON actual ERROR_VARIABLE json_error GET "${json}" ${json_path})
  if(NOT json_error STREQUAL "NOTFOUND")
    message(FATAL_ERROR
            "expected JSON field '${path}', but lookup failed: ${json_error}. "
            "Output: ${json}")
  endif()
  crossgl_metal_smoke_normalize_expected("${expected}" normalized_expected)
  if(NOT actual STREQUAL "${normalized_expected}")
    message(FATAL_ERROR
            "expected JSON field '${path}' to equal '${expected}', got "
            "'${actual}'. Output: ${json}")
  endif()
endfunction()

function(crossgl_metal_smoke_expect_nonempty_file path description)
  if(NOT EXISTS "${path}")
    message(FATAL_ERROR
            "expected ${description} at ${path}")
  endif()
  file(SIZE "${path}" file_size)
  if(file_size EQUAL 0)
    message(FATAL_ERROR
            "expected non-empty ${description} at ${path}")
  endif()
endfunction()

get_filename_component(xcrun_dir "${XCRUN}" DIRECTORY)
if(WIN32)
  set(path_separator ";")
else()
  set(path_separator ":")
endif()
set(ENV{PATH} "${xcrun_dir}${path_separator}$ENV{PATH}")
set(ENV{CROSSGL_DISABLE_TOOLCHAIN_FALLBACKS} "1")

crossgl_metal_smoke_find_tool(metal resolved_metal)
crossgl_metal_smoke_find_tool(metallib resolved_metallib)

if(DEFINED METAL AND NOT "${METAL}" STREQUAL "" AND
   NOT "${METAL}" STREQUAL "${resolved_metal}")
  message(STATUS
          "Configured Metal compiler path was ${METAL}; current xcrun path is "
          "${resolved_metal}")
endif()
if(DEFINED METALLIB AND NOT "${METALLIB}" STREQUAL "" AND
   NOT "${METALLIB}" STREQUAL "${resolved_metallib}")
  message(STATUS
          "Configured metallib path was ${METALLIB}; current xcrun path is "
          "${resolved_metallib}")
endif()

file(REMOVE_RECURSE "${OUTPUT}")
crossgl_metal_smoke_run(
  build_result build_stdout build_stderr
  "${CGLC}" build "${INPUT}" --target metal --output "${OUTPUT}" --debug-ir
  --diagnostics-json)
if(NOT "${build_result}" STREQUAL "0")
  message(FATAL_ERROR
          "real Metal toolchain smoke failed while building ${INPUT}.\n"
          "xcrun: ${XCRUN}\n"
          "metal: ${resolved_metal}\n"
          "metallib: ${resolved_metallib}\n"
          "package: ${OUTPUT}\n"
          "stdout:\n${build_stdout}\n"
          "stderr:\n${build_stderr}")
endif()

set(metal_source
    "${OUTPUT}/backend/metal/${EXPECTED_MODULE}.metal")
set(air_file
    "${OUTPUT}/backend/metal/${EXPECTED_MODULE}.air")
set(metallib_file
    "${OUTPUT}/backend/metal/${EXPECTED_MODULE}.metallib")
set(compile_options
    "${OUTPUT}/backend/metal/${EXPECTED_MODULE}.metal-compile-options.json")

crossgl_metal_smoke_expect_nonempty_file("${metal_source}"
                                         "generated Metal source")
crossgl_metal_smoke_expect_nonempty_file("${air_file}" "generated AIR")
crossgl_metal_smoke_expect_nonempty_file("${metallib_file}"
                                         "generated metallib")
crossgl_metal_smoke_expect_nonempty_file("${compile_options}"
                                         "Metal compile options")

file(READ "${compile_options}" compile_options_json)
crossgl_metal_smoke_expect_json_field("${compile_options_json}" "target"
                                      "metal")
crossgl_metal_smoke_expect_json_field("${compile_options_json}" "module"
                                      "${EXPECTED_MODULE}")
crossgl_metal_smoke_expect_json_field("${compile_options_json}"
                                      "compile.tool" "xcrun metal")
crossgl_metal_smoke_expect_json_field("${compile_options_json}"
                                      "library.tool" "xcrun metallib")

crossgl_metal_smoke_run(
  verify_result verify_stdout verify_stderr
  "${CGLC}" package verify "${OUTPUT}" --source "${INPUT}" --json)
if(NOT "${verify_result}" STREQUAL "0")
  message(FATAL_ERROR
          "package verify failed after Metal toolchain smoke build.\n"
          "package: ${OUTPUT}\n"
          "stdout:\n${verify_stdout}\n"
          "stderr:\n${verify_stderr}")
endif()
crossgl_metal_smoke_expect_json_field("${verify_stdout}" "success" "true")
crossgl_metal_smoke_expect_json_field("${verify_stdout}" "summary.target"
                                      "metal")
crossgl_metal_smoke_expect_json_field("${verify_stdout}"
                                      "summary.nativeBinaryStatus" "null")
crossgl_metal_smoke_expect_json_field(
  "${verify_stdout}" "summary.nativeArtifactDescriptor.health" "ok")
crossgl_metal_smoke_expect_json_field(
  "${verify_stdout}" "summary.targetLegalizationEvidence.packageMode" "native")

message(STATUS
        "Metal toolchain smoke used xcrun=${XCRUN}; metal=${resolved_metal}; "
        "metallib=${resolved_metallib}; produced ${air_file} and "
        "${metallib_file}")
