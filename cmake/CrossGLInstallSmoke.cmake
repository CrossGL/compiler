if(NOT DEFINED BUILD_DIR OR BUILD_DIR STREQUAL "")
  message(FATAL_ERROR "BUILD_DIR is required")
endif()
if(NOT DEFINED SOURCE_DIR OR SOURCE_DIR STREQUAL "")
  message(FATAL_ERROR "SOURCE_DIR is required")
endif()
if(NOT DEFINED INSTALL_PREFIX OR INSTALL_PREFIX STREQUAL "")
  message(FATAL_ERROR "INSTALL_PREFIX is required")
endif()

function(crossgl_check_no_config_path_leaks install_root)
  file(GLOB installed_config_files
    "${install_root}/lib/cmake/CrossGLCompiler/*.cmake")
  if(NOT installed_config_files)
    message(FATAL_ERROR
      "installed CMake config files missing under ${install_root}")
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
          "installed config file contains source/build path: ${config_file}")
      endif()
    endforeach()
  endforeach()
endfunction()

function(crossgl_check_installed_tree_matches_source source_dir installed_dir label)
  if(NOT IS_DIRECTORY "${source_dir}")
    message(FATAL_ERROR "${label} source directory missing: ${source_dir}")
  endif()
  if(NOT IS_DIRECTORY "${installed_dir}")
    message(FATAL_ERROR "${label} install directory missing: ${installed_dir}")
  endif()

  file(GLOB_RECURSE source_files
    LIST_DIRECTORIES false
    RELATIVE "${source_dir}"
    "${source_dir}/*")
  file(GLOB_RECURSE installed_files
    LIST_DIRECTORIES false
    RELATIVE "${installed_dir}"
    "${installed_dir}/*")
  foreach(path_list source_files installed_files)
    list(FILTER ${path_list} EXCLUDE REGEX "/$")
    list(SORT ${path_list})
  endforeach()

  if(NOT source_files STREQUAL installed_files)
    string(REPLACE ";" "\n  " source_file_list "${source_files}")
    string(REPLACE ";" "\n  " installed_file_list "${installed_files}")
    message(FATAL_ERROR
      "${label} installed file list differs from source\n"
      "source files:\n  ${source_file_list}\n"
      "installed files:\n  ${installed_file_list}")
  endif()
endfunction()


function(crossgl_check_required_installed_runtime install_root)
  set(required_runtime_paths
    "${install_root}/share/crossgl/runtime/__init__.py"
    "${install_root}/share/crossgl/runtime/backend_loader.py"
    "${install_root}/share/crossgl/runtime/directx_loader.py"
    "${install_root}/share/crossgl/runtime/package_reader.py"
    "${install_root}/share/crossgl/runtime/loader.py"
    "${install_root}/share/crossgl/runtime/metal_loader.py"
    "${install_root}/share/crossgl/runtime/opengl_loader.py"
    "${install_root}/share/crossgl/runtime/package_target_contracts.py"
    "${install_root}/share/crossgl/runtime/vulkan_loader.py"
    "${install_root}/share/crossgl/runtime/examples/__init__.py"
    "${install_root}/share/crossgl/runtime/examples/source_free_loader.py"
    "${install_root}/share/crossgl/runtime/examples/fixtures/source-free-metal-native.cglb/diagnostics.json"
    "${install_root}/share/crossgl/runtime/examples/fixtures/source-free-metal-native.cglb/manifest.json"
    "${install_root}/share/crossgl/runtime/examples/fixtures/source-free-metal-native.cglb/reflection.json"
    "${install_root}/share/crossgl/runtime/examples/fixtures/source-free-metal-native.cglb/backend/metal/SourceFreeMetalRuntimeExample.metallib"
    "${install_root}/share/crossgl/runtime/examples/fixtures/source-free-opengl.cglb/diagnostics.json"
    "${install_root}/share/crossgl/runtime/examples/fixtures/source-free-opengl.cglb/manifest.json"
    "${install_root}/share/crossgl/runtime/examples/fixtures/source-free-opengl.cglb/reflection.json"
    "${install_root}/share/crossgl/runtime/examples/fixtures/source-free-opengl.cglb/backend/opengl/SourceFreeOpenGLRuntimeExample.comp.glsl")
  foreach(required_runtime_path IN LISTS required_runtime_paths)
    if(NOT EXISTS "${required_runtime_path}")
      message(FATAL_ERROR
        "installed runtime artifact missing: ${required_runtime_path}")
    endif()
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

function(crossgl_run_installed_runtime_python_smoke install_root)
  if(NOT DEFINED CROSSGL_PYTHON3 OR CROSSGL_PYTHON3 STREQUAL "")
    message(STATUS
      "CrossGL installed runtime Python smoke skipped: CROSSGL_PYTHON3 not configured")
    return()
  endif()

  set(runtime_pythonpath "${install_root}/share/crossgl")
  set(metal_package
    "${runtime_pythonpath}/runtime/examples/fixtures/source-free-metal-native.cglb")
  execute_process(
    COMMAND "${CMAKE_COMMAND}" -E env
      "PYTHONPATH=${runtime_pythonpath}"
      "${CROSSGL_PYTHON3}" -m runtime.examples.source_free_loader
      "${metal_package}" metal --json --native-admission
    WORKING_DIRECTORY "${install_root}"
    RESULT_VARIABLE metal_runtime_result
    OUTPUT_VARIABLE metal_runtime_stdout
    ERROR_VARIABLE metal_runtime_stderr)
  if(NOT metal_runtime_result EQUAL 0)
    message(FATAL_ERROR
      "installed runtime metal source-free loader smoke failed:\n"
      "${metal_runtime_stdout}\n${metal_runtime_stderr}")
  endif()
  crossgl_assert_source_free_loader_json(
    "${metal_runtime_stdout}" "installed metal native")

  set(opengl_package
    "${runtime_pythonpath}/runtime/examples/fixtures/source-free-opengl.cglb")
  execute_process(
    COMMAND "${CMAKE_COMMAND}" -E env
      "PYTHONPATH=${runtime_pythonpath}"
      "${CROSSGL_PYTHON3}" -m runtime.examples.source_free_loader
      "${opengl_package}" opengl --json
    WORKING_DIRECTORY "${install_root}"
    RESULT_VARIABLE opengl_runtime_result
    OUTPUT_VARIABLE opengl_runtime_stdout
    ERROR_VARIABLE opengl_runtime_stderr)
  if(NOT opengl_runtime_result EQUAL 0)
    message(FATAL_ERROR
      "installed runtime OpenGL source-package loader smoke failed:\n"
      "${opengl_runtime_stdout}\n${opengl_runtime_stderr}")
  endif()
  crossgl_assert_source_free_loader_json(
    "${opengl_runtime_stdout}" "installed OpenGL source-package")
  string(FIND "${opengl_runtime_stdout}"
    "\"selectedPackageMode\": \"source-package\"" source_package_position)
  if(source_package_position EQUAL -1)
    message(FATAL_ERROR
      "installed runtime OpenGL smoke did not select source-package mode:\n"
      "${opengl_runtime_stdout}")
  endif()

  message(STATUS
    "CrossGL installed runtime source-free loader smoke passed: "
    "sourceInputs=[], sourceParsingRequired=false, "
    "compilerInvocationRequired=false, deviceExecutionRequired=false")
  message(STATUS
    "CrossGL installed runtime OpenGL source-package smoke passed: "
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
      "CrossGL install smoke parallel level must be a positive integer")
  endif()
  set("${out_var}" --parallel "${parallel_level}" PARENT_SCOPE)
endfunction()

file(REMOVE_RECURSE "${INSTALL_PREFIX}")

set(install_command "${CMAKE_COMMAND}" --install "${BUILD_DIR}" --prefix
  "${INSTALL_PREFIX}")
if(CMAKE_CONFIGURATION_TYPES AND CMAKE_BUILD_TYPE)
  list(APPEND install_command --config "${CMAKE_BUILD_TYPE}")
endif()
execute_process(
  COMMAND ${install_command}
  RESULT_VARIABLE install_result
  OUTPUT_VARIABLE install_stdout
  ERROR_VARIABLE install_stderr)
if(NOT install_result EQUAL 0)
  message(FATAL_ERROR
    "install smoke failed while installing:\n${install_stdout}\n${install_stderr}")
endif()

set(cglc_candidates
  "${INSTALL_PREFIX}/bin/cglc${CMAKE_EXECUTABLE_SUFFIX}"
  "${INSTALL_PREFIX}/bin/cglc"
  "${INSTALL_PREFIX}/bin/cglc.exe")
set(cglc_path "")
foreach(candidate IN LISTS cglc_candidates)
  if(EXISTS "${candidate}")
    set(cglc_path "${candidate}")
    break()
  endif()
endforeach()
if("${cglc_path}" STREQUAL "")
  string(REPLACE ";" ", " cglc_candidate_list "${cglc_candidates}")
  message(FATAL_ERROR "installed cglc missing; checked ${cglc_candidate_list}")
endif()
execute_process(
  COMMAND "${cglc_path}" doctor
  RESULT_VARIABLE doctor_result
  OUTPUT_VARIABLE doctor_stdout
  ERROR_VARIABLE doctor_stderr)
if(NOT doctor_result EQUAL 0)
  message(FATAL_ERROR
    "installed cglc doctor failed:\n${doctor_stdout}\n${doctor_stderr}")
endif()

set(required_paths
  "${INSTALL_PREFIX}/include/crossgl/Driver/Compiler.h"
  "${INSTALL_PREFIX}/share/crossgl/schemas/doctor-v1.schema.json"
  "${INSTALL_PREFIX}/share/crossgl/schema-defs/target-record-v1.json"
  "${INSTALL_PREFIX}/lib/cmake/CrossGLCompiler/CrossGLCompilerConfig.cmake"
  "${INSTALL_PREFIX}/lib/cmake/CrossGLCompiler/CrossGLCompilerTargets.cmake")
foreach(required_path IN LISTS required_paths)
  if(NOT EXISTS "${required_path}")
    message(FATAL_ERROR "installed artifact missing: ${required_path}")
  endif()
endforeach()
crossgl_check_installed_tree_matches_source(
  "${SOURCE_DIR}/docs/schemas"
  "${INSTALL_PREFIX}/share/crossgl/schemas"
  "schema contract")
crossgl_check_installed_tree_matches_source(
  "${SOURCE_DIR}/docs/schema-defs"
  "${INSTALL_PREFIX}/share/crossgl/schema-defs"
  "schema definition contract")
crossgl_check_required_installed_runtime("${INSTALL_PREFIX}")
crossgl_run_installed_runtime_python_smoke("${INSTALL_PREFIX}")

file(GLOB installed_libraries
  "${INSTALL_PREFIX}/lib/libcrossgl_compiler.*"
  "${INSTALL_PREFIX}/lib/crossgl_compiler.*")
if(NOT installed_libraries)
  message(FATAL_ERROR "installed crossgl_compiler library was not found")
endif()

set(consumer_dir "${BUILD_DIR}/install-smoke-consumer")
file(REMOVE_RECURSE "${consumer_dir}")
file(MAKE_DIRECTORY "${consumer_dir}")
file(WRITE "${consumer_dir}/CMakeLists.txt"
  "cmake_minimum_required(VERSION 3.24)\n"
  "project(CrossGLInstallConsumer LANGUAGES CXX)\n"
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
    "-DCMAKE_PREFIX_PATH=${INSTALL_PREFIX}"
    ${consumer_configure_args}
  RESULT_VARIABLE consumer_result
  OUTPUT_VARIABLE consumer_stdout
  ERROR_VARIABLE consumer_stderr)
if(NOT consumer_result EQUAL 0)
  message(FATAL_ERROR
    "installed package config import failed:\n${consumer_stdout}\n${consumer_stderr}")
endif()
execute_process(
  COMMAND "${CMAKE_COMMAND}" --build "${consumer_dir}/build"
    ${consumer_build_args}
  RESULT_VARIABLE consumer_build_result
  OUTPUT_VARIABLE consumer_build_stdout
  ERROR_VARIABLE consumer_build_stderr)
if(NOT consumer_build_result EQUAL 0)
  message(FATAL_ERROR
    "installed package config consumer build failed:\n${consumer_build_stdout}\n${consumer_build_stderr}")
endif()

crossgl_check_no_config_path_leaks("${INSTALL_PREFIX}")

message(STATUS "CrossGL install layout smoke passed at ${INSTALL_PREFIX}")
