if(POLICY CMP0054)
  cmake_policy(SET CMP0054 NEW)
endif()

foreach(required_var IN ITEMS CGLC INPUT OUTPUT EXPECTED_MODULE GLSLANG_VALIDATOR)
  if(NOT DEFINED ${required_var} OR "${${required_var}}" STREQUAL "")
    message(FATAL_ERROR "OpenGL toolchain smoke requires ${required_var}")
  endif()
endforeach()

function(crossgl_opengl_smoke_run result_var stdout_var stderr_var)
  execute_process(
    COMMAND ${ARGN}
    RESULT_VARIABLE command_result
    OUTPUT_VARIABLE command_stdout
    ERROR_VARIABLE command_stderr)
  set(${result_var} "${command_result}" PARENT_SCOPE)
  set(${stdout_var} "${command_stdout}" PARENT_SCOPE)
  set(${stderr_var} "${command_stderr}" PARENT_SCOPE)
endfunction()

function(crossgl_opengl_smoke_normalize_expected value out_var)
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

function(crossgl_opengl_smoke_expect_json_field json path expected)
  string(REPLACE "." ";" json_path "${path}")
  string(JSON actual ERROR_VARIABLE json_error GET "${json}" ${json_path})
  if(NOT json_error STREQUAL "NOTFOUND")
    message(FATAL_ERROR
            "expected JSON field '${path}', but lookup failed: ${json_error}. "
            "Output: ${json}")
  endif()
  crossgl_opengl_smoke_normalize_expected("${expected}" normalized_expected)
  if(NOT actual STREQUAL "${normalized_expected}")
    message(FATAL_ERROR
            "expected JSON field '${path}' to equal '${expected}', got "
            "'${actual}'. Output: ${json}")
  endif()
endfunction()

function(crossgl_opengl_smoke_expect_diagnostic json expected_code)
  string(JSON diagnostic_count ERROR_VARIABLE diagnostics_error LENGTH "${json}"
         diagnostics)
  if(NOT diagnostics_error STREQUAL "NOTFOUND")
    message(FATAL_ERROR
            "expected diagnostics array, but lookup failed: "
            "${diagnostics_error}. Output: ${json}")
  endif()
  if(diagnostic_count EQUAL 0)
    message(FATAL_ERROR
            "expected diagnostic '${expected_code}', but diagnostics were "
            "empty. Output: ${json}")
  endif()
  math(EXPR last_index "${diagnostic_count} - 1")
  foreach(index RANGE 0 ${last_index})
    string(JSON actual_code ERROR_VARIABLE code_error GET "${json}"
           diagnostics ${index} code)
    if(NOT code_error STREQUAL "NOTFOUND")
      message(FATAL_ERROR
              "failed to read diagnostic ${index} code: ${code_error}. "
              "Output: ${json}")
    endif()
    if(actual_code STREQUAL "${expected_code}")
      return()
    endif()
  endforeach()
  message(FATAL_ERROR
          "expected diagnostic '${expected_code}'. Output: ${json}")
endfunction()

function(crossgl_opengl_smoke_expect_nonempty_file path description)
  if(NOT EXISTS "${path}")
    message(FATAL_ERROR "expected ${description} at ${path}")
  endif()
  file(SIZE "${path}" file_size)
  if(file_size EQUAL 0)
    message(FATAL_ERROR "expected non-empty ${description} at ${path}")
  endif()
endfunction()

get_filename_component(glslang_dir "${GLSLANG_VALIDATOR}" DIRECTORY)
if(WIN32)
  set(path_separator ";")
else()
  set(path_separator ":")
endif()
set(ENV{PATH} "${glslang_dir}${path_separator}$ENV{PATH}")
set(ENV{CROSSGL_DISABLE_TOOLCHAIN_FALLBACKS} "1")

file(REMOVE_RECURSE "${OUTPUT}")
crossgl_opengl_smoke_run(
  build_result build_stdout build_stderr
  "${CGLC}" build "${INPUT}" --target opengl --output "${OUTPUT}" --debug-ir
  --diagnostics-json)
if(NOT "${build_result}" STREQUAL "0")
  message(FATAL_ERROR
          "OpenGL glslang smoke failed while building ${INPUT}.\n"
          "glslangValidator: ${GLSLANG_VALIDATOR}\n"
          "package: ${OUTPUT}\n"
          "stdout:\n${build_stdout}\n"
          "stderr:\n${build_stderr}")
endif()

set(glsl_source
    "${OUTPUT}/backend/opengl/${EXPECTED_MODULE}.comp.glsl")
set(validated_glsl
    "${OUTPUT}/backend/opengl/${EXPECTED_MODULE}.glsl")
set(manifest_path "${OUTPUT}/manifest.json")
set(reflection_path "${OUTPUT}/reflection.json")
set(diagnostics_path "${OUTPUT}/diagnostics.json")
set(debug_metadata_path "${OUTPUT}/ir/debug-metadata.json")

crossgl_opengl_smoke_expect_nonempty_file("${glsl_source}"
                                          "generated OpenGL GLSL source")
crossgl_opengl_smoke_expect_nonempty_file("${validated_glsl}"
                                          "validated OpenGL GLSL artifact")
crossgl_opengl_smoke_expect_nonempty_file("${manifest_path}"
                                          "OpenGL package manifest")
crossgl_opengl_smoke_expect_nonempty_file("${reflection_path}"
                                          "OpenGL reflection metadata")
crossgl_opengl_smoke_expect_nonempty_file("${diagnostics_path}"
                                          "OpenGL diagnostics metadata")
crossgl_opengl_smoke_expect_nonempty_file("${debug_metadata_path}"
                                          "OpenGL debug metadata")

crossgl_opengl_smoke_run(
  glslang_result glslang_stdout glslang_stderr
  "${GLSLANG_VALIDATOR}" -S comp "${glsl_source}")
if(NOT "${glslang_result}" STREQUAL "0")
  file(READ "${glsl_source}" generated_glsl)
  message(FATAL_ERROR
          "real glslangValidator rejected generated OpenGL GLSL.\n"
          "glslangValidator: ${GLSLANG_VALIDATOR}\n"
          "source: ${glsl_source}\n"
          "package: ${OUTPUT}\n"
          "stdout:\n${glslang_stdout}\n"
          "stderr:\n${glslang_stderr}\n"
          "generated GLSL:\n${generated_glsl}")
endif()

file(READ "${manifest_path}" manifest_json)
crossgl_opengl_smoke_expect_json_field("${manifest_json}" "schemaVersion" "1")
crossgl_opengl_smoke_expect_json_field("${manifest_json}" "target" "opengl")
crossgl_opengl_smoke_expect_json_field("${manifest_json}" "module"
                                       "${EXPECTED_MODULE}")
crossgl_opengl_smoke_expect_json_field("${manifest_json}"
                                       "artifacts.backendSource"
                                       "backend/opengl/${EXPECTED_MODULE}.comp.glsl")
crossgl_opengl_smoke_expect_json_field("${manifest_json}"
                                       "artifacts.nativeBinary"
                                       "backend/opengl/${EXPECTED_MODULE}.glsl")
crossgl_opengl_smoke_expect_json_field("${manifest_json}"
                                       "artifacts.nativeBinaryStatus"
                                       "validated")

file(READ "${diagnostics_path}" diagnostics_json)
crossgl_opengl_smoke_expect_diagnostic("${diagnostics_json}"
                                       "opengl.glsl-validated")

file(READ "${debug_metadata_path}" debug_metadata_json)
crossgl_opengl_smoke_expect_json_field("${debug_metadata_json}"
                                       "sourcePackageValidation.target"
                                       "opengl")
crossgl_opengl_smoke_expect_json_field("${debug_metadata_json}"
                                       "sourcePackageValidation.tool"
                                       "glslangValidator")
crossgl_opengl_smoke_expect_json_field("${debug_metadata_json}"
                                       "sourcePackageValidation.status"
                                       "validated")

crossgl_opengl_smoke_run(
  verify_result verify_stdout verify_stderr
  "${CGLC}" package verify "${OUTPUT}" --source "${INPUT}" --json)
if(NOT "${verify_result}" STREQUAL "0")
  message(FATAL_ERROR
          "package verify failed after OpenGL glslang smoke build.\n"
          "package: ${OUTPUT}\n"
          "stdout:\n${verify_stdout}\n"
          "stderr:\n${verify_stderr}")
endif()
crossgl_opengl_smoke_expect_json_field("${verify_stdout}" "success" "true")
crossgl_opengl_smoke_expect_json_field("${verify_stdout}" "summary.target"
                                       "opengl")
crossgl_opengl_smoke_expect_json_field("${verify_stdout}" "summary.module"
                                       "${EXPECTED_MODULE}")
crossgl_opengl_smoke_expect_json_field("${verify_stdout}"
                                       "summary.nativeBinaryStatus"
                                       "validated")

message(STATUS
        "OpenGL glslang smoke validated ${glsl_source} with "
        "${GLSLANG_VALIDATOR}")
