if(CROSSGL_REQUIRE_PYTHON_TESTS AND NOT BUILD_TESTING)
  message(FATAL_ERROR
    "CROSSGL_REQUIRE_PYTHON_TESTS requires BUILD_TESTING to be enabled")
endif()

if(BUILD_TESTING)
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLPythonInterpreter.cmake")

  function(crossgl_mark_new_ctest_lane before_tests processors lane_label
           test_name_regex)
    get_property(current_tests DIRECTORY PROPERTY TESTS)
    foreach(test_name IN LISTS current_tests)
      if(test_name IN_LIST before_tests)
        continue()
      endif()
      if(NOT test_name MATCHES "${test_name_regex}")
        continue()
      endif()
      set_tests_properties("${test_name}" PROPERTIES
        PROCESSORS "${processors}")
      set_property(TEST "${test_name}" APPEND PROPERTY LABELS "${lane_label}")
    endforeach()
  endfunction()

  add_executable(crossgl_unit_tests tests/unit/CompilerUnitTests.cpp)
  target_link_libraries(crossgl_unit_tests PRIVATE crossgl_compiler)
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLPythonTests.cmake")

  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLTestFixtures.cmake")
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLOptionalNativeTools.cmake")

  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLCoreCommandTests.cmake")
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLCliSurfaceTests.cmake")
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLCheckTests.cmake")
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLOptimizerTests.cmake")
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLDumpTests.cmake")
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLHIRSourceMapTests.cmake")
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLTargetExplanationTests.cmake")
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLBackendDumpTests.cmake")

  crossgl_capture_current_tests(CROSSGL_SOURCE_PACKAGE_TESTS_BEFORE)
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLSourcePackageBuildTests.cmake")
  crossgl_mark_new_ctest_lane(
    "${CROSSGL_SOURCE_PACKAGE_TESTS_BEFORE}" 2 source-package-build
    "^cglc_build_")
  crossgl_mark_new_ctest_lane(
    "${CROSSGL_SOURCE_PACKAGE_TESTS_BEFORE}" 2 native-build
    "^cglc_(directx|opengl)_toolchain_native_smoke$")

  crossgl_capture_current_tests(CROSSGL_VULKAN_NATIVE_BUILD_TESTS_BEFORE)
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLVulkanNativeBuildTests.cmake")
  crossgl_mark_new_ctest_lane(
    "${CROSSGL_VULKAN_NATIVE_BUILD_TESTS_BEFORE}" 2 native-build
    "^(cglc_build_.*_native|cglc_vulkan_toolchain_native_smoke)$")

  crossgl_capture_current_tests(CROSSGL_METAL_NATIVE_BUILD_TESTS_BEFORE)
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLMetalNativeBuildTests.cmake")
  crossgl_mark_new_ctest_lane(
    "${CROSSGL_METAL_NATIVE_BUILD_TESTS_BEFORE}" 2 native-build
    "^(cglc_build_.*_native|cglc_metal_toolchain_native_smoke)$")

  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLPackageInspectSchemaTests.cmake")

  crossgl_capture_current_tests(CROSSGL_PACKAGE_VERIFY_TESTS_BEFORE)
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLPackageVerifySchemaTests.cmake")
  crossgl_mark_new_ctest_lane(
    "${CROSSGL_PACKAGE_VERIFY_TESTS_BEFORE}" 2 package-verify-build
    "^cglc_package_verify_.*(_source_package|_native)$")

  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLRuntimeLoaderPlanTests.cmake")
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLRuntimePackageReaderTests.cmake")
  include("${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/CrossGLPythonTestRegistration.cmake")
endif()
