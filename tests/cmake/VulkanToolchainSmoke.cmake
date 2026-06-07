if(POLICY CMP0054)
  cmake_policy(SET CMP0054 NEW)
endif()
if(POLICY CMP0057)
  cmake_policy(SET CMP0057 NEW)
endif()

foreach(required_var IN ITEMS CGLC INPUT OUTPUT EXPECTED_MODULE SPIRV_AS
                              SPIRV_VAL)
  if(NOT DEFINED ${required_var} OR "${${required_var}}" STREQUAL "")
    message(FATAL_ERROR "Vulkan toolchain smoke requires ${required_var}")
  endif()
endforeach()

function(crossgl_vulkan_smoke_run result_var stdout_var stderr_var)
  execute_process(
    COMMAND ${ARGN}
    RESULT_VARIABLE command_result
    OUTPUT_VARIABLE command_stdout
    ERROR_VARIABLE command_stderr)
  set(${result_var} "${command_result}" PARENT_SCOPE)
  set(${stdout_var} "${command_stdout}" PARENT_SCOPE)
  set(${stderr_var} "${command_stderr}" PARENT_SCOPE)
endfunction()

function(crossgl_vulkan_smoke_normalize_expected value out_var)
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

function(crossgl_vulkan_smoke_expect_json_field json path expected)
  string(REPLACE "." ";" json_path "${path}")
  string(JSON actual ERROR_VARIABLE json_error GET "${json}" ${json_path})
  if(NOT json_error STREQUAL "NOTFOUND")
    message(FATAL_ERROR
            "expected JSON field '${path}', but lookup failed: ${json_error}. "
            "Output: ${json}")
  endif()
  crossgl_vulkan_smoke_normalize_expected("${expected}" normalized_expected)
  if(NOT actual STREQUAL "${normalized_expected}")
    message(FATAL_ERROR
            "expected JSON field '${path}' to equal '${expected}', got "
            "'${actual}'. Output: ${json}")
  endif()
endfunction()

function(crossgl_vulkan_smoke_expect_nonempty_file path description)
  if(NOT EXISTS "${path}")
    message(FATAL_ERROR "expected ${description} at ${path}")
  endif()
  file(SIZE "${path}" file_size)
  if(file_size EQUAL 0)
    message(FATAL_ERROR "expected non-empty ${description} at ${path}")
  endif()
endfunction()

function(crossgl_vulkan_smoke_add_tool_dir tool_path)
  if(NOT tool_path)
    return()
  endif()
  if("${tool_path}" MATCHES "-NOTFOUND$")
    return()
  endif()
  if(NOT EXISTS "${tool_path}")
    message(FATAL_ERROR "configured Vulkan tool does not exist: ${tool_path}")
  endif()
  get_filename_component(tool_dir "${tool_path}" DIRECTORY)
  if(NOT tool_dir IN_LIST crossgl_vulkan_smoke_tool_dirs)
    list(APPEND crossgl_vulkan_smoke_tool_dirs "${tool_dir}")
    set(crossgl_vulkan_smoke_tool_dirs
        "${crossgl_vulkan_smoke_tool_dirs}" PARENT_SCOPE)
  endif()
endfunction()

set(crossgl_vulkan_smoke_tool_dirs "")
crossgl_vulkan_smoke_add_tool_dir("${SPIRV_AS}")
crossgl_vulkan_smoke_add_tool_dir("${SPIRV_VAL}")
if(DEFINED SPIRV_OPT)
  crossgl_vulkan_smoke_add_tool_dir("${SPIRV_OPT}")
endif()
if(DEFINED SPIRV_DIS)
  crossgl_vulkan_smoke_add_tool_dir("${SPIRV_DIS}")
endif()

if(WIN32)
  set(path_separator ";")
else()
  set(path_separator ":")
endif()
string(REPLACE ";" "${path_separator}" tool_path_prefix
       "${crossgl_vulkan_smoke_tool_dirs}")
set(ENV{PATH} "${tool_path_prefix}${path_separator}$ENV{PATH}")
set(ENV{CROSSGL_DISABLE_TOOLCHAIN_FALLBACKS} "1")

file(REMOVE_RECURSE "${OUTPUT}")
set(smoke_scratch_dir "${OUTPUT}.toolchain-smoke")
file(REMOVE_RECURSE "${smoke_scratch_dir}")
file(MAKE_DIRECTORY "${smoke_scratch_dir}")
crossgl_vulkan_smoke_run(
  build_result build_stdout build_stderr
  "${CGLC}" build "${INPUT}" --target vulkan --output "${OUTPUT}" --debug-ir
  --diagnostics-json --opt-level O2)
if(NOT "${build_result}" STREQUAL "0")
  message(FATAL_ERROR
          "real Vulkan toolchain smoke failed while building ${INPUT}.\n"
          "spirv-as: ${SPIRV_AS}\n"
          "spirv-val: ${SPIRV_VAL}\n"
          "spirv-opt: ${SPIRV_OPT}\n"
          "spirv-dis: ${SPIRV_DIS}\n"
          "package: ${OUTPUT}\n"
          "stdout:\n${build_stdout}\n"
          "stderr:\n${build_stderr}")
endif()

set(vulkan_assembly
    "${OUTPUT}/backend/vulkan/${EXPECTED_MODULE}.spvasm")
set(vulkan_binary
    "${OUTPUT}/backend/vulkan/${EXPECTED_MODULE}.spv")
set(vulkan_profile
    "${OUTPUT}/backend/vulkan/${EXPECTED_MODULE}.profile.json")
set(vulkan_disassembly
    "${OUTPUT}/backend/vulkan/${EXPECTED_MODULE}.disassembly.spvasm")

crossgl_vulkan_smoke_expect_nonempty_file("${vulkan_assembly}"
                                          "generated SPIR-V assembly")
crossgl_vulkan_smoke_expect_nonempty_file("${vulkan_binary}"
                                          "generated SPIR-V binary")
crossgl_vulkan_smoke_expect_nonempty_file("${vulkan_profile}"
                                          "Vulkan native profile")
crossgl_vulkan_smoke_expect_nonempty_file("${OUTPUT}/manifest.json"
                                          "package manifest")
crossgl_vulkan_smoke_expect_nonempty_file("${OUTPUT}/reflection.json"
                                          "package reflection")
crossgl_vulkan_smoke_expect_nonempty_file("${OUTPUT}/diagnostics.json"
                                          "package diagnostics")

file(READ "${OUTPUT}/manifest.json" manifest_json)
crossgl_vulkan_smoke_expect_json_field("${manifest_json}" "target" "vulkan")
crossgl_vulkan_smoke_expect_json_field("${manifest_json}" "module"
                                       "${EXPECTED_MODULE}")
crossgl_vulkan_smoke_expect_json_field(
  "${manifest_json}" "artifacts.backendAssembly"
  "backend/vulkan/${EXPECTED_MODULE}.spvasm")
crossgl_vulkan_smoke_expect_json_field(
  "${manifest_json}" "artifacts.nativeBinary"
  "backend/vulkan/${EXPECTED_MODULE}.spv")
crossgl_vulkan_smoke_expect_json_field(
  "${manifest_json}" "artifacts.nativeProfile"
  "backend/vulkan/${EXPECTED_MODULE}.profile.json")

file(READ "${vulkan_profile}" profile_json)
crossgl_vulkan_smoke_expect_json_field("${profile_json}" "target" "vulkan")
crossgl_vulkan_smoke_expect_json_field("${profile_json}" "module"
                                       "${EXPECTED_MODULE}")
crossgl_vulkan_smoke_expect_json_field("${profile_json}"
                                       "profile.vulkanVersion" "1.2")
crossgl_vulkan_smoke_expect_json_field("${profile_json}"
                                       "profile.spirvVersion" "1.0")
crossgl_vulkan_smoke_expect_json_field("${profile_json}"
                                       "debug.validationTargetEnv"
                                       "vulkan1.2")
crossgl_vulkan_smoke_expect_json_field(
  "${profile_json}" "artifacts.backendAssembly"
  "backend/vulkan/${EXPECTED_MODULE}.spvasm")
crossgl_vulkan_smoke_expect_json_field(
  "${profile_json}" "artifacts.nativeBinary"
  "backend/vulkan/${EXPECTED_MODULE}.spv")
crossgl_vulkan_smoke_expect_json_field("${profile_json}"
                                       "debug.optimization.requestedLevel"
                                       "O2")
crossgl_vulkan_smoke_expect_json_field("${profile_json}"
                                       "debug.optimization.policy"
                                       "use-when-available")
crossgl_vulkan_smoke_expect_json_field("${profile_json}"
                                       "debug.optimization.level" "-O")

if(DEFINED SPIRV_OPT AND SPIRV_OPT AND NOT "${SPIRV_OPT}" MATCHES "-NOTFOUND$")
  crossgl_vulkan_smoke_expect_json_field("${profile_json}"
                                         "debug.optimization.status"
                                         "applied")
else()
  crossgl_vulkan_smoke_expect_json_field("${profile_json}"
                                         "debug.optimization.status"
                                         "skipped-tool-missing")
endif()

crossgl_vulkan_smoke_run(
  validate_result validate_stdout validate_stderr
  "${SPIRV_VAL}" --target-env vulkan1.2 "${vulkan_binary}")
if(NOT "${validate_result}" STREQUAL "0")
  message(FATAL_ERROR
          "spirv-val failed on the packaged Vulkan SPIR-V binary.\n"
          "spirv-val: ${SPIRV_VAL}\n"
          "binary: ${vulkan_binary}\n"
          "stdout:\n${validate_stdout}\n"
          "stderr:\n${validate_stderr}")
endif()

set(reassembled_binary
    "${smoke_scratch_dir}/${EXPECTED_MODULE}.reassembled.spv")
crossgl_vulkan_smoke_run(
  assemble_result assemble_stdout assemble_stderr
  "${SPIRV_AS}" --target-env vulkan1.2 "${vulkan_assembly}" -o
  "${reassembled_binary}")
if(NOT "${assemble_result}" STREQUAL "0")
  message(FATAL_ERROR
          "spirv-as failed while reassembling packaged Vulkan assembly.\n"
          "spirv-as: ${SPIRV_AS}\n"
          "assembly: ${vulkan_assembly}\n"
          "stdout:\n${assemble_stdout}\n"
          "stderr:\n${assemble_stderr}")
endif()
crossgl_vulkan_smoke_expect_nonempty_file("${reassembled_binary}"
                                          "reassembled SPIR-V binary")

crossgl_vulkan_smoke_run(
  revalidate_result revalidate_stdout revalidate_stderr
  "${SPIRV_VAL}" --target-env vulkan1.2 "${reassembled_binary}")
if(NOT "${revalidate_result}" STREQUAL "0")
  message(FATAL_ERROR
          "spirv-val failed on the reassembled Vulkan SPIR-V binary.\n"
          "spirv-val: ${SPIRV_VAL}\n"
          "binary: ${reassembled_binary}\n"
          "stdout:\n${revalidate_stdout}\n"
          "stderr:\n${revalidate_stderr}")
endif()

if(DEFINED SPIRV_DIS AND SPIRV_DIS AND NOT "${SPIRV_DIS}" MATCHES "-NOTFOUND$")
  crossgl_vulkan_smoke_expect_json_field("${profile_json}"
                                         "debug.disassembly.status"
                                         "emitted")
  crossgl_vulkan_smoke_expect_json_field(
    "${profile_json}" "debug.disassembly.path"
    "backend/vulkan/${EXPECTED_MODULE}.disassembly.spvasm")
  crossgl_vulkan_smoke_expect_nonempty_file("${vulkan_disassembly}"
                                            "SPIR-V disassembly sidecar")

  set(external_disassembly
      "${smoke_scratch_dir}/${EXPECTED_MODULE}.smoke.disassembly.spvasm")
  crossgl_vulkan_smoke_run(
    disassemble_result disassemble_stdout disassemble_stderr
    "${SPIRV_DIS}" "${vulkan_binary}" -o "${external_disassembly}")
  if(NOT "${disassemble_result}" STREQUAL "0")
    message(FATAL_ERROR
            "spirv-dis failed on the packaged Vulkan SPIR-V binary.\n"
            "spirv-dis: ${SPIRV_DIS}\n"
            "binary: ${vulkan_binary}\n"
            "stdout:\n${disassemble_stdout}\n"
            "stderr:\n${disassemble_stderr}")
  endif()
  crossgl_vulkan_smoke_expect_nonempty_file("${external_disassembly}"
                                            "external SPIR-V disassembly")
else()
  crossgl_vulkan_smoke_expect_json_field("${profile_json}"
                                         "debug.disassembly.status"
                                         "skipped-tool-missing")
  crossgl_vulkan_smoke_expect_json_field("${profile_json}"
                                         "debug.disassembly.path" "null")
endif()

crossgl_vulkan_smoke_run(
  verify_result verify_stdout verify_stderr
  "${CGLC}" package verify "${OUTPUT}" --source "${INPUT}" --json)
if(NOT "${verify_result}" STREQUAL "0")
  message(FATAL_ERROR
          "package verify failed after Vulkan toolchain smoke build.\n"
          "package: ${OUTPUT}\n"
          "stdout:\n${verify_stdout}\n"
          "stderr:\n${verify_stderr}")
endif()
crossgl_vulkan_smoke_expect_json_field("${verify_stdout}" "success" "true")
crossgl_vulkan_smoke_expect_json_field("${verify_stdout}" "summary.target"
                                       "vulkan")
crossgl_vulkan_smoke_expect_json_field("${verify_stdout}"
                                       "summary.nativeBinaryStatus" "null")

if(EXISTS "${vulkan_disassembly}")
  set(disassembly_status "with disassembly ${vulkan_disassembly}")
else()
  set(disassembly_status "without optional disassembly sidecar")
endif()
message(STATUS
        "Vulkan toolchain smoke produced ${vulkan_binary}, "
        "validated it with ${SPIRV_VAL}, and wrote profile "
        "${vulkan_profile} ${disassembly_status}")
