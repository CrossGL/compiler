# Validates the optional in-process SPIRV-Tools binary (.spv) emission path.
#
# This script is registered only when the compiler was built WITH SPIRV-Tools
# (CROSSGL_HAVE_SPIRV_TOOLS=1) and spirv-val is available. It builds a fixture to
# the Vulkan target, confirms the sibling <module>.spv binary exists, carries the
# SPIR-V magic word (proving a real assembled binary was written, not the .spvasm
# text), and that spirv-val accepts it for vulkan1.2 / SPIR-V 1.5.

if(POLICY CMP0054)
  cmake_policy(SET CMP0054 NEW)
endif()

foreach(required_var IN ITEMS CGLC INPUT OUTPUT EXPECTED_MODULE SPIRV_VAL)
  if(NOT DEFINED ${required_var} OR "${${required_var}}" STREQUAL "")
    message(FATAL_ERROR "Vulkan SPIRV-Tools binary smoke requires ${required_var}")
  endif()
endforeach()

function(crossgl_spv_smoke_run result_var stdout_var stderr_var)
  execute_process(
    COMMAND ${ARGN}
    RESULT_VARIABLE command_result
    OUTPUT_VARIABLE command_stdout
    ERROR_VARIABLE command_stderr)
  set(${result_var} "${command_result}" PARENT_SCOPE)
  set(${stdout_var} "${command_stdout}" PARENT_SCOPE)
  set(${stderr_var} "${command_stderr}" PARENT_SCOPE)
endfunction()

file(REMOVE_RECURSE "${OUTPUT}")

crossgl_spv_smoke_run(
  build_result build_stdout build_stderr
  "${CGLC}" build "${INPUT}" --target vulkan --output "${OUTPUT}" --debug-ir)
if(NOT "${build_result}" STREQUAL "0")
  message(FATAL_ERROR
          "Vulkan SPIRV-Tools binary smoke failed while building ${INPUT}.\n"
          "package: ${OUTPUT}\n"
          "stdout:\n${build_stdout}\n"
          "stderr:\n${build_stderr}")
endif()

set(vulkan_binary "${OUTPUT}/backend/vulkan/${EXPECTED_MODULE}.spv")
set(vulkan_assembly "${OUTPUT}/backend/vulkan/${EXPECTED_MODULE}.spvasm")

if(NOT EXISTS "${vulkan_assembly}")
  message(FATAL_ERROR "expected generated SPIR-V assembly at ${vulkan_assembly}")
endif()
if(NOT EXISTS "${vulkan_binary}")
  message(FATAL_ERROR "expected assembled SPIR-V binary at ${vulkan_binary}")
endif()
file(SIZE "${vulkan_binary}" binary_size)
if(binary_size LESS 20)
  message(FATAL_ERROR
          "expected a non-trivial SPIR-V binary at ${vulkan_binary}, "
          "got ${binary_size} bytes")
endif()

# Confirm the first word is the SPIR-V magic number (0x07230203). The binary is
# little-endian on this host, so the leading bytes are 03 02 23 07.
file(READ "${vulkan_binary}" magic_hex LIMIT 4 HEX)
if(NOT magic_hex STREQUAL "03022307")
  message(FATAL_ERROR
          "expected SPIR-V magic 0x07230203 (bytes 03022307) at the start of "
          "${vulkan_binary}, got 0x${magic_hex}")
endif()

crossgl_spv_smoke_run(
  validate_result validate_stdout validate_stderr
  "${SPIRV_VAL}" --target-env vulkan1.2 "${vulkan_binary}")
if(NOT "${validate_result}" STREQUAL "0")
  message(FATAL_ERROR
          "spirv-val rejected the SPIRV-Tools-assembled binary.\n"
          "spirv-val: ${SPIRV_VAL}\n"
          "binary: ${vulkan_binary}\n"
          "stdout:\n${validate_stdout}\n"
          "stderr:\n${validate_stderr}")
endif()

message(STATUS
        "SPIRV-Tools binary smoke assembled ${vulkan_binary} "
        "(${binary_size} bytes) and validated it with ${SPIRV_VAL}")
