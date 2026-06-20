# Optional native shader tool discovery shared by CTest registration files.
#
# Backend/native tests should use these variables:
# - CROSSGL_SPIRV_AS and CROSSGL_SPIRV_VAL for Vulkan SPIR-V assembly/validation.
# - CROSSGL_SPIRV_OPT for optional Vulkan SPIR-V optimization discovery.
# - CROSSGL_SPIRV_DIS for optional Vulkan SPIR-V disassembly discovery.
# - CROSSGL_DXC for DirectX DXIL emission.
# - CROSSGL_GLSLANG_VALIDATOR for OpenGL GLSL validation.
# - CROSSGL_XCRUN, CROSSGL_METAL, and CROSSGL_METALLIB for Apple Metal builds.
#
# Test labels:
# - optional-native: any CTest that depends on an optional native shader tool.
# - <target>-native: target-specific native tests, for example metal-native.
# - native-tool-available: the tool-backed tests were registered.
# - native-tool-policy: fake-tool policy coverage for failure/unavailable paths.
# - native-tool-unavailable: a sentinel skip test was registered instead.

include(CMakeParseArguments)

find_program(CROSSGL_SPIRV_AS
  NAMES spirv-as
  DOC "SPIR-V assembler used by optional Vulkan native package tests")
find_program(CROSSGL_SPIRV_VAL
  NAMES spirv-val
  DOC "SPIR-V validator used by optional Vulkan native package tests")
find_program(CROSSGL_SPIRV_OPT
  NAMES spirv-opt
  DOC "SPIR-V optimizer discovered for future optional Vulkan optimization tests")
find_program(CROSSGL_SPIRV_DIS
  NAMES spirv-dis
  DOC "SPIR-V disassembler used by optional Vulkan debug sidecar tests")
find_program(CROSSGL_DXC
  NAMES dxc
  DOC "DirectX Shader Compiler used by optional DXIL package tests")
find_program(CROSSGL_GLSLANG_VALIDATOR
  NAMES glslangValidator
  DOC "glslangValidator used by optional OpenGL GLSL package tests")
find_program(CROSSGL_XCRUN
  NAMES xcrun
  DOC "Apple xcrun launcher used to locate Metal native tools")

function(crossgl_find_xcrun_tool output_var tool_name)
  set(resolved_path "")
  if(CROSSGL_XCRUN)
    execute_process(
      COMMAND "${CROSSGL_XCRUN}" -find "${tool_name}"
      RESULT_VARIABLE find_result
      OUTPUT_VARIABLE find_output
      ERROR_QUIET
      OUTPUT_STRIP_TRAILING_WHITESPACE)
    if(find_result EQUAL 0 AND NOT find_output STREQUAL "")
      set(resolved_path "${find_output}")
    endif()
  endif()
  set(${output_var} "${resolved_path}" PARENT_SCOPE)
endfunction()

if(APPLE)
  crossgl_find_xcrun_tool(CROSSGL_METAL metal)
  crossgl_find_xcrun_tool(CROSSGL_METALLIB metallib)
else()
  set(CROSSGL_METAL "")
  set(CROSSGL_METALLIB "")
endif()

if(CROSSGL_SPIRV_AS AND CROSSGL_SPIRV_VAL)
  set(CROSSGL_HAS_VULKAN_NATIVE_TOOLS TRUE)
else()
  set(CROSSGL_HAS_VULKAN_NATIVE_TOOLS FALSE)
endif()

if(CROSSGL_SPIRV_OPT)
  set(CROSSGL_HAS_VULKAN_SPIRV_OPT TRUE)
else()
  set(CROSSGL_HAS_VULKAN_SPIRV_OPT FALSE)
endif()

if(CROSSGL_SPIRV_DIS)
  set(CROSSGL_HAS_VULKAN_SPIRV_DIS TRUE)
else()
  set(CROSSGL_HAS_VULKAN_SPIRV_DIS FALSE)
endif()

if(CROSSGL_DXC)
  set(CROSSGL_HAS_DIRECTX_NATIVE_VALIDATOR TRUE)
  get_filename_component(CROSSGL_DXC_DIR "${CROSSGL_DXC}" DIRECTORY)
else()
  set(CROSSGL_HAS_DIRECTX_NATIVE_VALIDATOR FALSE)
  set(CROSSGL_DXC_DIR "")
endif()

if(CROSSGL_GLSLANG_VALIDATOR)
  set(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR TRUE)
else()
  set(CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR FALSE)
endif()

if(APPLE AND CROSSGL_XCRUN AND CROSSGL_METAL AND CROSSGL_METALLIB)
  set(CROSSGL_HAS_METAL_NATIVE_TOOLS TRUE)
else()
  set(CROSSGL_HAS_METAL_NATIVE_TOOLS FALSE)
endif()

function(crossgl_capture_current_tests out_var)
  get_property(current_tests DIRECTORY PROPERTY TESTS)
  set(${out_var} "${current_tests}" PARENT_SCOPE)
endfunction()

function(crossgl_label_optional_native_test test_name target_name)
  set_tests_properties("${test_name}" PROPERTIES
    LABELS "optional-native;${target_name}-native;native-tool-available")
endfunction()

function(crossgl_label_optional_native_policy_test test_name target_name)
  set_tests_properties("${test_name}" PROPERTIES
    LABELS "optional-native;${target_name}-native;native-tool-policy")
endfunction()

function(crossgl_label_new_optional_native_tests target_name before_tests)
  get_property(current_tests DIRECTORY PROPERTY TESTS)
  foreach(test_name IN LISTS current_tests)
    if(NOT test_name IN_LIST before_tests)
      crossgl_label_optional_native_test("${test_name}" "${target_name}")
    endif()
  endforeach()
endfunction()

function(crossgl_missing_optional_native_vars out_var)
  set(missing_vars "")
  foreach(var_name IN LISTS ARGN)
    if(NOT DEFINED ${var_name} OR NOT ${var_name})
      list(APPEND missing_vars "${var_name}")
    endif()
  endforeach()
  set(${out_var} "${missing_vars}" PARENT_SCOPE)
endfunction()

function(crossgl_add_optional_native_skip_test)
  set(options "")
  set(one_value_args NAME TARGET REASON)
  set(multi_value_args REQUIRED_VARS)
  cmake_parse_arguments(CROSSGL_SKIP
    "${options}" "${one_value_args}" "${multi_value_args}" ${ARGN})

  if(NOT CROSSGL_SKIP_NAME)
    message(FATAL_ERROR "crossgl_add_optional_native_skip_test requires NAME")
  endif()
  if(NOT CROSSGL_SKIP_TARGET)
    message(FATAL_ERROR "crossgl_add_optional_native_skip_test requires TARGET")
  endif()

  crossgl_missing_optional_native_vars(missing_vars ${CROSSGL_SKIP_REQUIRED_VARS})
  if(missing_vars)
    string(REPLACE ";" ", " missing_text "${missing_vars}")
    if(CROSSGL_SKIP_REASON)
      set(skip_reason "${CROSSGL_SKIP_REASON}; missing ${missing_text}")
    else()
      set(skip_reason "optional native ${CROSSGL_SKIP_TARGET} test requires ${missing_text}")
    endif()
    add_test(NAME "${CROSSGL_SKIP_NAME}"
      COMMAND ${CMAKE_COMMAND} -E echo
        "SKIP: optional native ${CROSSGL_SKIP_TARGET} unavailable; ${skip_reason}")
    set_tests_properties("${CROSSGL_SKIP_NAME}" PROPERTIES
      LABELS "optional-native;${CROSSGL_SKIP_TARGET}-native;native-tool-unavailable"
      SKIP_REGULAR_EXPRESSION "^SKIP:")
  endif()
endfunction()

if(APPLE)
  crossgl_missing_optional_native_vars(
    CROSSGL_METAL_NATIVE_MISSING_TOOL_VARS
    CROSSGL_XCRUN CROSSGL_METAL CROSSGL_METALLIB)
  if(CROSSGL_METAL_NATIVE_MISSING_TOOL_VARS)
    string(REPLACE ";" ", " CROSSGL_METAL_NATIVE_TOOL_DETAIL
      "${CROSSGL_METAL_NATIVE_MISSING_TOOL_VARS}")
    set(CROSSGL_METAL_NATIVE_TOOL_DETAIL
      "missing ${CROSSGL_METAL_NATIVE_TOOL_DETAIL}")
  else()
    set(CROSSGL_METAL_NATIVE_TOOL_DETAIL
      "xcrun=${CROSSGL_XCRUN}; metal=${CROSSGL_METAL}; metallib=${CROSSGL_METALLIB}")
  endif()
else()
  set(CROSSGL_METAL_NATIVE_TOOL_DETAIL
    "non-Apple host; unavailable sentinels will be registered")
endif()

message(STATUS
  "CrossGL optional native tools: "
  "vulkan=${CROSSGL_HAS_VULKAN_NATIVE_TOOLS}; "
  "spirv-opt=${CROSSGL_HAS_VULKAN_SPIRV_OPT}; "
  "spirv-dis=${CROSSGL_HAS_VULKAN_SPIRV_DIS}; "
  "directx=${CROSSGL_HAS_DIRECTX_NATIVE_VALIDATOR}; "
  "opengl=${CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR}; "
  "metal=${CROSSGL_HAS_METAL_NATIVE_TOOLS}")
message(STATUS
  "CrossGL optional native Metal tools: ${CROSSGL_METAL_NATIVE_TOOL_DETAIL}")
