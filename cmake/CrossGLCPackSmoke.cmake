if(NOT DEFINED BUILD_DIR OR BUILD_DIR STREQUAL "")
  message(FATAL_ERROR "BUILD_DIR is required")
endif()
if(NOT DEFINED SOURCE_DIR OR SOURCE_DIR STREQUAL "")
  message(FATAL_ERROR "SOURCE_DIR is required")
endif()
if(NOT DEFINED CPACK_CONFIG OR CPACK_CONFIG STREQUAL "")
  message(FATAL_ERROR "CPACK_CONFIG is required")
endif()
if(NOT DEFINED CPACK_COMMAND OR CPACK_COMMAND STREQUAL "")
  set(CPACK_COMMAND cpack)
endif()

function(crossgl_require_path root relative_path)
  if(NOT EXISTS "${root}/${relative_path}")
    message(FATAL_ERROR "packaged artifact missing: ${root}/${relative_path}")
  endif()
endfunction()

function(crossgl_find_cglc root out_var)
  set(cglc_candidates
    "${root}/bin/cglc${CMAKE_EXECUTABLE_SUFFIX}"
    "${root}/bin/cglc"
    "${root}/bin/cglc.exe")
  foreach(candidate IN LISTS cglc_candidates)
    if(EXISTS "${candidate}")
      set("${out_var}" "${candidate}" PARENT_SCOPE)
      return()
    endif()
  endforeach()
  string(REPLACE ";" ", " cglc_candidate_list "${cglc_candidates}")
  message(FATAL_ERROR "packaged cglc missing; checked ${cglc_candidate_list}")
endfunction()

function(crossgl_check_no_config_path_leaks install_root)
  file(GLOB installed_config_files
    "${install_root}/lib/cmake/CrossGLCompiler/*.cmake")
  if(NOT installed_config_files)
    message(FATAL_ERROR
      "packaged CMake config files missing under ${install_root}")
  endif()

  set(forbidden_paths "${SOURCE_DIR}" "${BUILD_DIR}")
  foreach(forbidden_path IN LISTS forbidden_paths)
    if(forbidden_path STREQUAL "")
      continue()
    endif()
    file(TO_CMAKE_PATH "${forbidden_path}" forbidden_cmake_path)
    foreach(config_file IN LISTS installed_config_files)
      file(READ "${config_file}" config_contents)
      string(FIND "${config_contents}" "${forbidden_path}" direct_match)
      string(FIND "${config_contents}" "${forbidden_cmake_path}" cmake_path_match)
      if(NOT direct_match EQUAL -1 OR NOT cmake_path_match EQUAL -1)
        message(FATAL_ERROR
          "packaged config file contains source/build path: ${config_file}")
      endif()
    endforeach()
  endforeach()
endfunction()

function(crossgl_check_packaged_tree_matches_source source_dir packaged_dir label)
  if(NOT IS_DIRECTORY "${source_dir}")
    message(FATAL_ERROR "${label} source directory missing: ${source_dir}")
  endif()
  if(NOT IS_DIRECTORY "${packaged_dir}")
    message(FATAL_ERROR "${label} package directory missing: ${packaged_dir}")
  endif()

  file(GLOB_RECURSE source_files
    LIST_DIRECTORIES false
    RELATIVE "${source_dir}"
    "${source_dir}/*")
  file(GLOB_RECURSE packaged_files
    LIST_DIRECTORIES false
    RELATIVE "${packaged_dir}"
    "${packaged_dir}/*")
  foreach(path_list source_files packaged_files)
    list(FILTER ${path_list} EXCLUDE REGEX "/$")
    list(SORT ${path_list})
  endforeach()

  if(NOT source_files STREQUAL packaged_files)
    string(REPLACE ";" "\n  " source_file_list "${source_files}")
    string(REPLACE ";" "\n  " packaged_file_list "${packaged_files}")
    message(FATAL_ERROR
      "${label} packaged file list differs from source\n"
      "source files:\n  ${source_file_list}\n"
      "packaged files:\n  ${packaged_file_list}")
  endif()
endfunction()


function(crossgl_check_required_packaged_runtime package_root)
  set(required_runtime_paths
    "share/crossgl/runtime/__init__.py"
    "share/crossgl/runtime/backend_loader.py"
    "share/crossgl/runtime/directx_loader.py"
    "share/crossgl/runtime/package_reader.py"
    "share/crossgl/runtime/loader.py"
    "share/crossgl/runtime/metal_loader.py"
    "share/crossgl/runtime/opengl_loader.py"
    "share/crossgl/runtime/package_target_contracts.py"
    "share/crossgl/runtime/vulkan_loader.py"
    "share/crossgl/runtime/examples/__init__.py"
    "share/crossgl/runtime/examples/source_free_loader.py"
    "share/crossgl/runtime/examples/fixtures/source-free-metal-native.cglb/diagnostics.json"
    "share/crossgl/runtime/examples/fixtures/source-free-metal-native.cglb/manifest.json"
    "share/crossgl/runtime/examples/fixtures/source-free-metal-native.cglb/reflection.json"
    "share/crossgl/runtime/examples/fixtures/source-free-metal-native.cglb/backend/metal/SourceFreeMetalRuntimeExample.metallib"
    "share/crossgl/runtime/examples/fixtures/source-free-opengl.cglb/diagnostics.json"
    "share/crossgl/runtime/examples/fixtures/source-free-opengl.cglb/manifest.json"
    "share/crossgl/runtime/examples/fixtures/source-free-opengl.cglb/reflection.json"
    "share/crossgl/runtime/examples/fixtures/source-free-opengl.cglb/backend/opengl/SourceFreeOpenGLRuntimeExample.comp.glsl")
  foreach(required_runtime_path IN LISTS required_runtime_paths)
    crossgl_require_path("${package_root}" "${required_runtime_path}")
  endforeach()
endfunction()

function(crossgl_assert_source_free_loader_json json_output label)
  set(required_snippets
    "\"sourceInputs\": []"
    "\"sourceParsingRequired\": false"
    "\"compilerInvocationRequired\": false"
    "\"deviceExecutionRequired\": false")
  foreach(required_snippet IN LISTS required_snippets)
    string(FIND "${json_output}" "${required_snippet}" snippet_position)
    if(snippet_position EQUAL -1)
      message(FATAL_ERROR
        "${label} runtime loader output missing ${required_snippet}:\n${json_output}")
    endif()
  endforeach()

  set(checkout_runtime_path "${SOURCE_DIR}/runtime/")
  string(FIND "${json_output}" "${checkout_runtime_path}" source_path_position)
  if(NOT source_path_position EQUAL -1)
    message(FATAL_ERROR
      "${label} runtime loader output contains checkout runtime path "
      "${checkout_runtime_path}:\n${json_output}")
  endif()
endfunction()

function(crossgl_run_packaged_runtime_python_smoke package_root)
  if(NOT DEFINED CROSSGL_PYTHON3 OR CROSSGL_PYTHON3 STREQUAL "")
    message(STATUS
      "CrossGL packaged runtime Python smoke skipped: CROSSGL_PYTHON3 not configured")
    return()
  endif()

  set(runtime_pythonpath "${package_root}/share/crossgl")
  set(metal_package
    "${runtime_pythonpath}/runtime/examples/fixtures/source-free-metal-native.cglb")
  execute_process(
    COMMAND "${CMAKE_COMMAND}" -E env
      "PYTHONPATH=${runtime_pythonpath}"
      "${CROSSGL_PYTHON3}" -m runtime.examples.source_free_loader
      "${metal_package}" metal --json --native-admission
    WORKING_DIRECTORY "${package_root}"
    RESULT_VARIABLE metal_runtime_result
    OUTPUT_VARIABLE metal_runtime_stdout
    ERROR_VARIABLE metal_runtime_stderr)
  if(NOT metal_runtime_result EQUAL 0)
    message(FATAL_ERROR
      "packaged runtime metal source-free loader smoke failed:\n"
      "${metal_runtime_stdout}\n${metal_runtime_stderr}")
  endif()
  crossgl_assert_source_free_loader_json(
    "${metal_runtime_stdout}" "packaged metal native")

  set(opengl_package
    "${runtime_pythonpath}/runtime/examples/fixtures/source-free-opengl.cglb")
  execute_process(
    COMMAND "${CMAKE_COMMAND}" -E env
      "PYTHONPATH=${runtime_pythonpath}"
      "${CROSSGL_PYTHON3}" -m runtime.examples.source_free_loader
      "${opengl_package}" opengl --json
    WORKING_DIRECTORY "${package_root}"
    RESULT_VARIABLE opengl_runtime_result
    OUTPUT_VARIABLE opengl_runtime_stdout
    ERROR_VARIABLE opengl_runtime_stderr)
  if(NOT opengl_runtime_result EQUAL 0)
    message(FATAL_ERROR
      "packaged runtime OpenGL source-package loader smoke failed:\n"
      "${opengl_runtime_stdout}\n${opengl_runtime_stderr}")
  endif()
  crossgl_assert_source_free_loader_json(
    "${opengl_runtime_stdout}" "packaged OpenGL source-package")
  string(FIND "${opengl_runtime_stdout}"
    "\"selectedPackageMode\": \"source-package\"" source_package_position)
  if(source_package_position EQUAL -1)
    message(FATAL_ERROR
      "packaged runtime OpenGL smoke did not select source-package mode:\n"
      "${opengl_runtime_stdout}")
  endif()

  message(STATUS
    "CrossGL packaged runtime source-free loader smoke passed: "
    "sourceInputs=[], sourceParsingRequired=false, "
    "compilerInvocationRequired=false, deviceExecutionRequired=false")
  message(STATUS
    "CrossGL packaged runtime OpenGL source-package smoke passed: "
    "sourceInputs=[], sourceParsingRequired=false, "
    "compilerInvocationRequired=false, deviceExecutionRequired=false")
endfunction()

function(crossgl_smoke_parallel_build_args out_var)
  set(parallel_level "")
  if(DEFINED CROSSGL_SMOKE_PARALLEL_LEVEL
      AND NOT "${CROSSGL_SMOKE_PARALLEL_LEVEL}" STREQUAL "")
    set(parallel_level "${CROSSGL_SMOKE_PARALLEL_LEVEL}")
  elseif(DEFINED ENV{CMAKE_BUILD_PARALLEL_LEVEL}
      AND NOT "$ENV{CMAKE_BUILD_PARALLEL_LEVEL}" STREQUAL "")
    set(parallel_level "$ENV{CMAKE_BUILD_PARALLEL_LEVEL}")
  elseif(DEFINED ENV{CROSSGL_CI_JOBS}
      AND NOT "$ENV{CROSSGL_CI_JOBS}" STREQUAL "")
    set(parallel_level "$ENV{CROSSGL_CI_JOBS}")
  elseif(DEFINED ENV{CTEST_PARALLEL_LEVEL}
      AND NOT "$ENV{CTEST_PARALLEL_LEVEL}" STREQUAL "")
    set(parallel_level "$ENV{CTEST_PARALLEL_LEVEL}")
  endif()

  if(parallel_level STREQUAL "")
    set("${out_var}" "" PARENT_SCOPE)
    return()
  endif()
  if(NOT parallel_level MATCHES "^[1-9][0-9]*$")
    message(FATAL_ERROR
      "CrossGL CPack smoke parallel level must be a positive integer")
  endif()
  set("${out_var}" --parallel "${parallel_level}" PARENT_SCOPE)
endfunction()

set(cpack_output_dir "${BUILD_DIR}/cpack-smoke")
set(cpack_extract_dir "${BUILD_DIR}/cpack-smoke-extract")
file(REMOVE_RECURSE "${cpack_output_dir}" "${cpack_extract_dir}")
file(MAKE_DIRECTORY "${cpack_output_dir}" "${cpack_extract_dir}")

execute_process(
  COMMAND "${CPACK_COMMAND}" --config "${CPACK_CONFIG}" -B "${cpack_output_dir}"
  RESULT_VARIABLE cpack_result
  OUTPUT_VARIABLE cpack_stdout
  ERROR_VARIABLE cpack_stderr)
if(NOT cpack_result EQUAL 0)
  message(FATAL_ERROR
    "CPack smoke failed while creating package:\n${cpack_stdout}\n${cpack_stderr}")
endif()

file(GLOB cpack_archives "${cpack_output_dir}/*.tar.gz")
list(LENGTH cpack_archives cpack_archive_count)
if(NOT cpack_archive_count EQUAL 1)
  message(FATAL_ERROR
    "expected exactly one TGZ archive in ${cpack_output_dir}, found ${cpack_archive_count}: ${cpack_archives}")
endif()
list(GET cpack_archives 0 cpack_archive)

execute_process(
  COMMAND "${CMAKE_COMMAND}" -E tar xzf "${cpack_archive}"
  WORKING_DIRECTORY "${cpack_extract_dir}"
  RESULT_VARIABLE extract_result
  OUTPUT_VARIABLE extract_stdout
  ERROR_VARIABLE extract_stderr)
if(NOT extract_result EQUAL 0)
  message(FATAL_ERROR
    "CPack smoke failed while extracting ${cpack_archive}:\n${extract_stdout}\n${extract_stderr}")
endif()

file(GLOB extracted_entries RELATIVE "${cpack_extract_dir}" "${cpack_extract_dir}/*")
list(LENGTH extracted_entries extracted_entry_count)
if(NOT extracted_entry_count EQUAL 1)
  message(FATAL_ERROR
    "expected package archive to contain one top-level entry, found ${extracted_entry_count}: ${extracted_entries}")
endif()
list(GET extracted_entries 0 extracted_root_name)
set(package_root "${cpack_extract_dir}/${extracted_root_name}")
if(NOT IS_DIRECTORY "${package_root}")
  message(FATAL_ERROR "package root is not a directory: ${package_root}")
endif()

crossgl_find_cglc("${package_root}" cglc_path)
execute_process(
  COMMAND "${cglc_path}" doctor
  RESULT_VARIABLE doctor_result
  OUTPUT_VARIABLE doctor_stdout
  ERROR_VARIABLE doctor_stderr)
if(NOT doctor_result EQUAL 0)
  message(FATAL_ERROR
    "packaged cglc doctor failed:\n${doctor_stdout}\n${doctor_stderr}")
endif()

set(required_paths
  "include/crossgl/Driver/Compiler.h"
  "share/crossgl/schemas/doctor-v1.schema.json"
  "share/crossgl/schema-defs/target-record-v1.json"
  "lib/cmake/CrossGLCompiler/CrossGLCompilerConfig.cmake"
  "lib/cmake/CrossGLCompiler/CrossGLCompilerTargets.cmake")
foreach(required_path IN LISTS required_paths)
  crossgl_require_path("${package_root}" "${required_path}")
endforeach()
crossgl_check_packaged_tree_matches_source(
  "${SOURCE_DIR}/docs/schemas"
  "${package_root}/share/crossgl/schemas"
  "schema contract")
crossgl_check_packaged_tree_matches_source(
  "${SOURCE_DIR}/docs/schema-defs"
  "${package_root}/share/crossgl/schema-defs"
  "schema definition contract")
crossgl_check_required_packaged_runtime("${package_root}")
crossgl_run_packaged_runtime_python_smoke("${package_root}")

file(GLOB packaged_libraries
  "${package_root}/lib/libcrossgl_compiler.*"
  "${package_root}/lib/crossgl_compiler.*")
if(NOT packaged_libraries)
  message(FATAL_ERROR "packaged crossgl_compiler library was not found")
endif()

set(consumer_dir "${BUILD_DIR}/cpack-smoke-consumer")
file(REMOVE_RECURSE "${consumer_dir}")
file(MAKE_DIRECTORY "${consumer_dir}")
file(WRITE "${consumer_dir}/CMakeLists.txt"
  "cmake_minimum_required(VERSION 3.24)\n"
  "project(CrossGLCPackConsumer LANGUAGES CXX)\n"
  "find_package(CrossGLCompiler CONFIG REQUIRED)\n"
  "if(NOT TARGET CrossGL::crossgl_compiler)\n"
  "  message(FATAL_ERROR \"missing CrossGL::crossgl_compiler\")\n"
  "endif()\n"
  "if(NOT TARGET CrossGL::cglc)\n"
  "  message(FATAL_ERROR \"missing CrossGL::cglc\")\n"
  "endif()\n"
  "add_executable(consumer main.cpp)\n"
  "target_compile_features(consumer PRIVATE cxx_std_17)\n"
  "target_link_libraries(consumer PRIVATE CrossGL::crossgl_compiler)\n"
  "add_custom_target(check_cglc_import ALL COMMAND CrossGL::cglc targets)\n")
file(WRITE "${consumer_dir}/main.cpp"
  "#include <crossgl/Backend/Target.h>\n"
  "int main() {\n"
  "  return crossgl::targetName(crossgl::TargetKind::Auto).empty() ? 1 : 0;\n"
  "}\n")
set(consumer_configure_args)
set(consumer_build_args)
if(CMAKE_CONFIGURATION_TYPES)
  set(consumer_build_config "${CMAKE_BUILD_TYPE}")
  if(consumer_build_config STREQUAL "")
    set(consumer_build_config Release)
  endif()
  list(APPEND consumer_build_args --config "${consumer_build_config}")
elseif(CMAKE_BUILD_TYPE)
  list(APPEND consumer_configure_args "-DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}")
endif()
crossgl_smoke_parallel_build_args(crossgl_parallel_build_args)
list(APPEND consumer_build_args ${crossgl_parallel_build_args})
execute_process(
  COMMAND "${CMAKE_COMMAND}" -S "${consumer_dir}" -B "${consumer_dir}/build"
    "-DCMAKE_PREFIX_PATH=${package_root}"
    ${consumer_configure_args}
  RESULT_VARIABLE consumer_result
  OUTPUT_VARIABLE consumer_stdout
  ERROR_VARIABLE consumer_stderr)
if(NOT consumer_result EQUAL 0)
  message(FATAL_ERROR
    "packaged config import failed:\n${consumer_stdout}\n${consumer_stderr}")
endif()
execute_process(
  COMMAND "${CMAKE_COMMAND}" --build "${consumer_dir}/build"
    ${consumer_build_args}
  RESULT_VARIABLE consumer_build_result
  OUTPUT_VARIABLE consumer_build_stdout
  ERROR_VARIABLE consumer_build_stderr)
if(NOT consumer_build_result EQUAL 0)
  message(FATAL_ERROR
    "packaged config consumer build failed:\n${consumer_build_stdout}\n${consumer_build_stderr}")
endif()

crossgl_check_no_config_path_leaks("${package_root}")

message(STATUS "CrossGL CPack layout smoke passed for ${cpack_archive}")
