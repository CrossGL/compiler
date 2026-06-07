if(NOT DEFINED CGLC)
  message(FATAL_ERROR "CGLC is required")
endif()
if(NOT DEFINED INPUT)
  message(FATAL_ERROR "INPUT is required")
endif()
if(NOT DEFINED OUTPUT)
  message(FATAL_ERROR "OUTPUT is required")
endif()
if(NOT DEFINED EXPECTED_MODULE)
  message(FATAL_ERROR "EXPECTED_MODULE is required")
endif()

file(REMOVE_RECURSE "${OUTPUT}")
execute_process(
  COMMAND "${CGLC}" build "${INPUT}" --target vulkan --output "${OUTPUT}"
  RESULT_VARIABLE build_result
  OUTPUT_VARIABLE build_stdout
  ERROR_VARIABLE build_stderr
)
if(NOT build_result EQUAL 0)
  message(FATAL_ERROR "Vulkan build failed: ${build_stderr}${build_stdout}")
endif()

set(spvasm_path "${OUTPUT}/backend/vulkan/${EXPECTED_MODULE}.spvasm")
if(NOT EXISTS "${spvasm_path}")
  message(FATAL_ERROR "expected Vulkan SPIR-V assembly at ${spvasm_path}")
endif()
file(READ "${spvasm_path}" spvasm)

if(DEFINED EXPECTED_SPVASM_CONTAINS)
  string(REPLACE "|" ";" expected_snippets "${EXPECTED_SPVASM_CONTAINS}")
  foreach(snippet IN LISTS expected_snippets)
    string(FIND "${spvasm}" "${snippet}" snippet_position)
    if(snippet_position EQUAL -1)
      message(FATAL_ERROR "expected Vulkan SPIR-V assembly to contain '${snippet}'")
    endif()
  endforeach()
endif()

if(DEFINED EXPECTED_SPVASM_ORDERED_CONTAINS)
  string(REPLACE "|" ";" expected_ordered_snippets
         "${EXPECTED_SPVASM_ORDERED_CONTAINS}")
  set(previous_snippet_position -1)
  foreach(snippet IN LISTS expected_ordered_snippets)
    string(FIND "${spvasm}" "${snippet}" snippet_position)
    if(snippet_position EQUAL -1)
      message(FATAL_ERROR
              "expected Vulkan SPIR-V assembly to contain '${snippet}'")
    endif()
    if(snippet_position LESS previous_snippet_position)
      message(FATAL_ERROR
              "expected Vulkan SPIR-V assembly snippet '${snippet}' to appear after the previous ordered snippet")
    endif()
    set(previous_snippet_position "${snippet_position}")
  endforeach()
endif()

if(DEFINED UNEXPECTED_SPVASM_CONTAINS)
  string(REPLACE "|" ";" unexpected_snippets "${UNEXPECTED_SPVASM_CONTAINS}")
  foreach(snippet IN LISTS unexpected_snippets)
    string(FIND "${spvasm}" "${snippet}" snippet_position)
    if(NOT snippet_position EQUAL -1)
      message(FATAL_ERROR "expected Vulkan SPIR-V assembly not to contain '${snippet}'")
    endif()
  endforeach()
endif()
