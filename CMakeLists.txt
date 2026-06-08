cmake_minimum_required(VERSION 3.24)

project(CrossGLCompiler
  VERSION 0.1.0
  DESCRIPTION "CrossGL native compiler"
  LANGUAGES C CXX)

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(CROSSGL_ENABLE_WARNINGS "Enable strict compiler warnings" ON)
option(CROSSGL_REQUIRE_PYTHON_TESTS
  "Require Python-backed tests when BUILD_TESTING is enabled" OFF)
option(CROSSGL_ENABLE_MLIR_EXPERIMENTAL
  "Enable the experimental native MLIR pipeline gate when MLIR is configured" OFF)

find_package(LLVM CONFIG QUIET)
find_package(MLIR CONFIG QUIET)

if(LLVM_FOUND)
  message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION}: ${LLVM_DIR}")
endif()

if(MLIR_FOUND)
  message(STATUS "Found MLIR: ${MLIR_DIR}")
  set(CROSSGL_MLIR_FOUND_TEXT TRUE)
else()
  set(CROSSGL_MLIR_FOUND_TEXT FALSE)
endif()

if(CROSSGL_ENABLE_MLIR_EXPERIMENTAL AND NOT MLIR_FOUND)
  message(STATUS
    "CROSSGL_ENABLE_MLIR_EXPERIMENTAL is ON, but MLIR was not found; "
    "the native MLIR pipeline remains unavailable; "
    "MLIR_FOUND=${CROSSGL_MLIR_FOUND_TEXT}; "
    "target crossgl_mlir_experiment will not be created")
endif()

set(CROSSGL_MLIR_EXPERIMENT_SOURCES
  experimental/mlir/CrossGLMLIRExperiment.cpp
)
set(CROSSGL_MLIR_EXPERIMENT_FIXTURES
  tests/fixtures/MinimalComputeShader.cgl
  tests/fixtures/ScalarExpressionComputeShader.cgl
  tests/fixtures/StorageBufferComputeShader.cgl
  tests/fixtures/IfComputeShader.cgl
  tests/fixtures/VulkanTextureSamplerLodShader.cgl
)
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS
  tests/fixtures/mlir/minimal_compute_builtin_module.mlir
)
list(LENGTH CROSSGL_MLIR_EXPERIMENT_SOURCES
  CROSSGL_MLIR_EXPERIMENT_SOURCE_COUNT)
list(LENGTH CROSSGL_MLIR_EXPERIMENT_FIXTURES
  CROSSGL_MLIR_EXPERIMENT_FIXTURE_COUNT)
list(LENGTH CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS
  CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUT_COUNT)
set(CROSSGL_MLIR_EXPERIMENT_SOURCE_PRESENT_COUNT 0)
foreach(CROSSGL_MLIR_EXPERIMENT_SOURCE IN LISTS
    CROSSGL_MLIR_EXPERIMENT_SOURCES)
  if(EXISTS
      "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_SOURCE}")
    math(EXPR CROSSGL_MLIR_EXPERIMENT_SOURCE_PRESENT_COUNT
      "${CROSSGL_MLIR_EXPERIMENT_SOURCE_PRESENT_COUNT} + 1")
  endif()
endforeach()
set(CROSSGL_MLIR_EXPERIMENT_FIXTURE_PRESENT_COUNT 0)
foreach(CROSSGL_MLIR_EXPERIMENT_FIXTURE IN LISTS
    CROSSGL_MLIR_EXPERIMENT_FIXTURES)
  if(EXISTS
      "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_FIXTURE}")
    math(EXPR CROSSGL_MLIR_EXPERIMENT_FIXTURE_PRESENT_COUNT
      "${CROSSGL_MLIR_EXPERIMENT_FIXTURE_PRESENT_COUNT} + 1")
  endif()
endforeach()
set(CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUT_PRESENT_COUNT 0)
foreach(CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUT IN LISTS
    CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS)
  if(EXISTS
      "${CMAKE_CURRENT_SOURCE_DIR}/${CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUT}")
    math(EXPR CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUT_PRESENT_COUNT
      "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUT_PRESENT_COUNT} + 1")
  endif()
endforeach()
message(STATUS
  "CrossGL MLIR experiment scaffold sources present: "
  "${CROSSGL_MLIR_EXPERIMENT_SOURCE_PRESENT_COUNT}/"
  "${CROSSGL_MLIR_EXPERIMENT_SOURCE_COUNT}; fixtures present: "
  "${CROSSGL_MLIR_EXPERIMENT_FIXTURE_PRESENT_COUNT}/"
  "${CROSSGL_MLIR_EXPERIMENT_FIXTURE_COUNT}; verifier inputs present: "
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUT_PRESENT_COUNT}/"
  "${CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUT_COUNT}")

add_library(crossgl_compiler
  src/Backend/BackendHIR.cpp
  src/Backend/BackendIntrinsics.cpp
  src/Backend/BackendPlan.cpp
  src/Backend/BackendTokens.cpp
  src/Backend/DirectXBackend.cpp
  src/Backend/MetalBackend.cpp
  src/Backend/OpenGLBackend.cpp
  src/Backend/ResourceArrays.cpp
  src/Backend/SPIRVModule.cpp
  src/Backend/StorageBufferSupport.cpp
  src/Backend/Target.cpp
  src/Backend/TargetCapabilities.cpp
  src/Backend/TargetLegalization.cpp
  src/Backend/TextureCompare.cpp
  src/Backend/TextureSample.cpp
  src/Backend/TextureTypes.cpp
  src/Backend/Toolchain.cpp
  src/Backend/VulkanBackend.cpp
  src/Basic/Diagnostic.cpp
  src/Basic/Json.cpp
  src/Basic/SHA256.cpp
  src/Driver/Compiler.cpp
  src/Driver/CompilerPipeline.cpp
  src/Driver/DebugMetadata.cpp
  src/Driver/LanguageFeatureReport.cpp
  src/Driver/PackageDebugArtifacts.cpp
  src/Driver/PackageIntegrity.cpp
  src/Driver/PackageInspect.cpp
  src/Driver/PackageJson.cpp
  src/Driver/PackageMetadata.cpp
  src/Driver/PackagePublication.cpp
  src/Driver/Reflection.cpp
  src/Driver/SourceRemap.cpp
  src/Driver/StorageCapabilities.cpp
  src/Driver/StorageLayout.cpp
  src/Driver/TargetExplanation.cpp
  src/Frontend/Lexer.cpp
  src/Frontend/Parser.cpp
  src/Frontend/TokenText.cpp
  src/HIR/BuiltinEffects.cpp
  src/HIR/ConstantFolding.cpp
  src/HIR/HIR.cpp
  src/HIR/HIRDialect.cpp
  src/HIR/Intrinsics.cpp
  src/HIR/SideEffects.cpp
  src/HIR/StorageShape.cpp
  src/HIR/TypeSemantics.cpp
  src/IR/IRPrinter.cpp
  src/Optimizer/HIRPassManager.cpp
)

target_include_directories(crossgl_compiler
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)

target_compile_definitions(crossgl_compiler
  PUBLIC
    CROSSGL_VERSION="${PROJECT_VERSION}"
)

if(LLVM_FOUND)
  target_compile_definitions(crossgl_compiler PUBLIC
    CROSSGL_HAS_LLVM=1
    CROSSGL_LLVM_VERSION="${LLVM_PACKAGE_VERSION}"
  )
else()
  target_compile_definitions(crossgl_compiler PUBLIC
    CROSSGL_HAS_LLVM=0
    CROSSGL_LLVM_VERSION="not-found"
  )
endif()

if(MLIR_FOUND)
  target_compile_definitions(crossgl_compiler PUBLIC CROSSGL_HAS_MLIR=1)
else()
  target_compile_definitions(crossgl_compiler PUBLIC CROSSGL_HAS_MLIR=0)
endif()

if(CROSSGL_ENABLE_MLIR_EXPERIMENTAL)
  target_compile_definitions(crossgl_compiler PUBLIC
    CROSSGL_ENABLE_MLIR_EXPERIMENTAL=1)
else()
  target_compile_definitions(crossgl_compiler PUBLIC
    CROSSGL_ENABLE_MLIR_EXPERIMENTAL=0)
endif()

if(CROSSGL_ENABLE_WARNINGS)
  if(MSVC)
    target_compile_options(crossgl_compiler PRIVATE /W4 /permissive-)
  else()
    target_compile_options(crossgl_compiler PRIVATE -Wall -Wextra -Wpedantic)
  endif()
endif()

if(CROSSGL_ENABLE_MLIR_EXPERIMENTAL AND MLIR_FOUND)
  add_library(crossgl_mlir_experiment OBJECT
    ${CROSSGL_MLIR_EXPERIMENT_SOURCES})
  target_compile_features(crossgl_mlir_experiment PRIVATE cxx_std_20)
  target_compile_definitions(crossgl_mlir_experiment PRIVATE
    CROSSGL_MLIR_EXPERIMENT_COMPILE_GATED=1)
  target_include_directories(crossgl_mlir_experiment PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/include")
  if(CROSSGL_ENABLE_WARNINGS)
    if(MSVC)
      target_compile_options(crossgl_mlir_experiment PRIVATE /W4 /permissive-)
    else()
      target_compile_options(crossgl_mlir_experiment PRIVATE
        -Wall -Wextra -Wpedantic)
    endif()
  endif()
  message(STATUS
    "CrossGL MLIR experiment scaffold enabled for fixture-limited sources; "
    "CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON; "
    "MLIR_FOUND=${CROSSGL_MLIR_FOUND_TEXT}; "
    "target crossgl_mlir_experiment created")
else()
  if(CROSSGL_ENABLE_MLIR_EXPERIMENTAL)
    message(STATUS
      "CrossGL MLIR experiment scaffold skipped: MLIR not found; "
      "CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON; "
      "MLIR_FOUND=${CROSSGL_MLIR_FOUND_TEXT}; "
      "target crossgl_mlir_experiment not created")
  else()
    message(STATUS
      "CrossGL MLIR experiment scaffold not built: "
      "CROSSGL_ENABLE_MLIR_EXPERIMENTAL=OFF; "
      "target crossgl_mlir_experiment not created")
  endif()
endif()

add_executable(cglc tools/cglc/main.cpp)
target_link_libraries(cglc PRIVATE crossgl_compiler)

include(CTest)
include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLTests.cmake")
if(BUILD_TESTING)
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLMLIRExperimentTests.cmake")
endif()

set(CROSSGL_INSTALL_CMAKEDIR
  "${CMAKE_INSTALL_LIBDIR}/cmake/CrossGLCompiler")

install(TARGETS cglc crossgl_compiler
  EXPORT CrossGLCompilerTargets
  RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
  LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  INCLUDES DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}")
install(DIRECTORY include/
  DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}")
install(DIRECTORY docs/schemas docs/schema-defs
  DESTINATION "${CMAKE_INSTALL_DATADIR}/crossgl")
install(DIRECTORY runtime/
  DESTINATION "${CMAKE_INSTALL_DATADIR}/crossgl/runtime"
  PATTERN "__pycache__" EXCLUDE
  PATTERN "*.pyc" EXCLUDE)

install(EXPORT CrossGLCompilerTargets
  NAMESPACE CrossGL::
  FILE CrossGLCompilerTargets.cmake
  DESTINATION "${CROSSGL_INSTALL_CMAKEDIR}")

write_basic_package_version_file(
  "${CMAKE_CURRENT_BINARY_DIR}/CrossGLCompilerConfigVersion.cmake"
  VERSION "${PROJECT_VERSION}"
  COMPATIBILITY SameMajorVersion)
configure_package_config_file(
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/CrossGLCompilerConfig.cmake.in"
  "${CMAKE_CURRENT_BINARY_DIR}/CrossGLCompilerConfig.cmake"
  INSTALL_DESTINATION "${CROSSGL_INSTALL_CMAKEDIR}")
install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/CrossGLCompilerConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/CrossGLCompilerConfigVersion.cmake"
  DESTINATION "${CROSSGL_INSTALL_CMAKEDIR}")

if(BUILD_TESTING)
  include(ProcessorCount)
  ProcessorCount(CROSSGL_PACKAGE_SMOKE_PROCESSORS_DETECTED)
  set(CROSSGL_PACKAGE_SMOKE_PROCESSORS_DEFAULT "1")
  if(DEFINED ENV{CROSSGL_CI_JOBS}
      AND NOT "$ENV{CROSSGL_CI_JOBS}" STREQUAL "")
    set(CROSSGL_PACKAGE_SMOKE_PROCESSORS_DEFAULT "$ENV{CROSSGL_CI_JOBS}")
  elseif(DEFINED ENV{CMAKE_BUILD_PARALLEL_LEVEL}
      AND NOT "$ENV{CMAKE_BUILD_PARALLEL_LEVEL}" STREQUAL "")
    set(CROSSGL_PACKAGE_SMOKE_PROCESSORS_DEFAULT
      "$ENV{CMAKE_BUILD_PARALLEL_LEVEL}")
  elseif(DEFINED ENV{CTEST_PARALLEL_LEVEL}
      AND NOT "$ENV{CTEST_PARALLEL_LEVEL}" STREQUAL "")
    set(CROSSGL_PACKAGE_SMOKE_PROCESSORS_DEFAULT "$ENV{CTEST_PARALLEL_LEVEL}")
  elseif(CROSSGL_PACKAGE_SMOKE_PROCESSORS_DETECTED GREATER 0)
    set(CROSSGL_PACKAGE_SMOKE_PROCESSORS_DEFAULT
      "${CROSSGL_PACKAGE_SMOKE_PROCESSORS_DETECTED}")
  endif()
  set(CROSSGL_PACKAGE_SMOKE_PROCESSORS
    "${CROSSGL_PACKAGE_SMOKE_PROCESSORS_DEFAULT}"
    CACHE STRING "CTest processors reserved by CrossGL install/CPack smoke tests")
  if(NOT CROSSGL_PACKAGE_SMOKE_PROCESSORS MATCHES "^[1-9][0-9]*$")
    message(FATAL_ERROR
      "CROSSGL_PACKAGE_SMOKE_PROCESSORS must be a positive integer")
  endif()

  add_test(NAME cglc_install_layout_smoke
    COMMAND ${CMAKE_COMMAND}
      "-DBUILD_DIR=${CMAKE_BINARY_DIR}"
      "-DSOURCE_DIR=${CMAKE_CURRENT_SOURCE_DIR}"
      "-DINSTALL_PREFIX=${CMAKE_BINARY_DIR}/install-ctest-smoke"
      "-DCMAKE_CONFIGURATION_TYPES=${CMAKE_CONFIGURATION_TYPES}"
      "-DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}"
      "-DCROSSGL_SMOKE_PARALLEL_LEVEL=${CROSSGL_PACKAGE_SMOKE_PROCESSORS}"
      "-DCROSSGL_PYTHON3=${CROSSGL_PYTHON3}"
      -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/CrossGLInstallSmoke.cmake")
  set_tests_properties(cglc_install_layout_smoke PROPERTIES
    LABELS "readiness;native-install-smoke;package-layout-smoke"
    PROCESSORS "${CROSSGL_PACKAGE_SMOKE_PROCESSORS}")
endif()

set(CPACK_PACKAGE_NAME "CrossGLCompiler")
set(CPACK_PACKAGE_VENDOR "CrossGL")
set(CPACK_PACKAGE_VERSION "${PROJECT_VERSION}")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "${PROJECT_DESCRIPTION}")
set(CPACK_GENERATOR "TGZ")
include(CPack)

if(BUILD_TESTING)
  add_test(NAME cglc_cpack_layout_smoke
    COMMAND ${CMAKE_COMMAND}
      "-DBUILD_DIR=${CMAKE_BINARY_DIR}"
      "-DSOURCE_DIR=${CMAKE_CURRENT_SOURCE_DIR}"
      "-DCPACK_CONFIG=${CMAKE_BINARY_DIR}/CPackConfig.cmake"
      "-DCPACK_COMMAND=${CMAKE_CPACK_COMMAND}"
      "-DCMAKE_CONFIGURATION_TYPES=${CMAKE_CONFIGURATION_TYPES}"
      "-DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}"
      "-DCROSSGL_SMOKE_PARALLEL_LEVEL=${CROSSGL_PACKAGE_SMOKE_PROCESSORS}"
      "-DCROSSGL_PYTHON3=${CROSSGL_PYTHON3}"
      -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/CrossGLCPackSmoke.cmake")
  set_tests_properties(cglc_cpack_layout_smoke PROPERTIES
    LABELS "readiness;native-package-smoke;package-layout-smoke"
    PROCESSORS "${CROSSGL_PACKAGE_SMOKE_PROCESSORS}")
endif()
