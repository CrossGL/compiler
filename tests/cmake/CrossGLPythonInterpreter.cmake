if(CROSSGL_PYTHON3)
  set(CROSSGL_PYTHON3 "${CROSSGL_PYTHON3}" CACHE FILEPATH
    "Path to the Python 3 interpreter used by CrossGL tests")
else()
  find_package(Python3 COMPONENTS Interpreter QUIET)
  if(Python3_Interpreter_FOUND)
    set(CROSSGL_PYTHON3 "${Python3_EXECUTABLE}" CACHE FILEPATH
      "Path to the Python 3 interpreter used by CrossGL tests")
  endif()
endif()

if(CROSSGL_PYTHON3)
  string(CONCAT CROSSGL_PYTHON3_SMOKE_SCRIPT
    "import sys; "
    "version = '{}.{}.{}'.format("
    "sys.version_info[0], sys.version_info[1], sys.version_info[2]); "
    "prefix = 'crossgl-python3-smoke-ok ' if "
    "sys.version_info >= (3, 9) else 'crossgl-python3-smoke-too-old '; "
    "print(prefix + version); "
    "raise SystemExit(0 if sys.version_info >= (3, 9) else 1)")
  execute_process(
    COMMAND "${CROSSGL_PYTHON3}" -c "${CROSSGL_PYTHON3_SMOKE_SCRIPT}"
    RESULT_VARIABLE CROSSGL_PYTHON3_SMOKE_RESULT
    OUTPUT_VARIABLE CROSSGL_PYTHON3_SMOKE_OUTPUT
    ERROR_VARIABLE CROSSGL_PYTHON3_SMOKE_ERROR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_STRIP_TRAILING_WHITESPACE)
  set(CROSSGL_PYTHON3_SMOKE_OUTPUT_PATTERN
    "^crossgl-python3-smoke-ok ([0-9]+\\.[0-9]+\\.[0-9]+)$")
  if(CROSSGL_PYTHON3_SMOKE_RESULT STREQUAL "0"
      AND CROSSGL_PYTHON3_SMOKE_OUTPUT MATCHES
        "${CROSSGL_PYTHON3_SMOKE_OUTPUT_PATTERN}")
    set(CROSSGL_PYTHON3_SMOKE_VERSION "${CMAKE_MATCH_1}")
    message(STATUS
      "CrossGL Python test interpreter: ${CROSSGL_PYTHON3} "
      "(${CROSSGL_PYTHON3_SMOKE_VERSION})")
  else()
    string(CONCAT CROSSGL_PYTHON3_SMOKE_MESSAGE
      "CrossGL Python test interpreter check failed for "
      "'${CROSSGL_PYTHON3}'; expected Python 3.9 or newer")
    if(CROSSGL_PYTHON3_SMOKE_OUTPUT)
      string(APPEND CROSSGL_PYTHON3_SMOKE_MESSAGE
        "; stdout: ${CROSSGL_PYTHON3_SMOKE_OUTPUT}")
    endif()
    if(CROSSGL_PYTHON3_SMOKE_ERROR)
      string(APPEND CROSSGL_PYTHON3_SMOKE_MESSAGE
        "; stderr: ${CROSSGL_PYTHON3_SMOKE_ERROR}")
    endif()
    if(CROSSGL_REQUIRE_PYTHON_TESTS)
      message(FATAL_ERROR "${CROSSGL_PYTHON3_SMOKE_MESSAGE}")
    else()
      message(WARNING
        "${CROSSGL_PYTHON3_SMOKE_MESSAGE}; Python-backed CrossGL tests "
        "are disabled")
      set(CROSSGL_PYTHON3 "")
      set(CROSSGL_PYTHON3_DISABLED_BY_SMOKE TRUE)
    endif()
  endif()
endif()

if(NOT CROSSGL_PYTHON3)
  if(CROSSGL_REQUIRE_PYTHON_TESTS)
    message(FATAL_ERROR
      "CROSSGL_REQUIRE_PYTHON_TESTS is ON, but Python 3 was not found")
  elseif(NOT CROSSGL_PYTHON3_DISABLED_BY_SMOKE)
    message(WARNING
      "Python 3 interpreter not found; Python-backed CrossGL tests are disabled")
  endif()
endif()
