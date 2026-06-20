if(NOT DEFINED CACHE_FILE)
  message(FATAL_ERROR "CACHE_FILE is required")
endif()

if(NOT EXISTS "${CACHE_FILE}")
  message(FATAL_ERROR "CMake cache not found: ${CACHE_FILE}")
endif()

file(READ "${CACHE_FILE}" cache_contents)
if(NOT cache_contents MATCHES
   "(^|\n)CROSSGL_ENABLE_MLIR_EXPERIMENTAL:BOOL=OFF(\n|$)")
  message(FATAL_ERROR
    "CROSSGL_ENABLE_MLIR_EXPERIMENTAL must default to OFF")
endif()
