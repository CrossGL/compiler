cmake_minimum_required(VERSION 3.13)
project(MyMLIRProject)

# Set LLVM_DIR to your LLVM installation path
list(APPEND CMAKE_PREFIX_PATH "path/to/llvm")

find_package(LLVM REQUIRED CONFIG)
find_package(MLIR REQUIRED CONFIG)

message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION}")
message(STATUS "Using LLVMConfig.cmake in: ${LLVM_DIR}")

set(CMAKE_CXX_STANDARD 17 CACHE STRING "C++ standard to conform to")

include_directories(${LLVM_INCLUDE_DIRS})
separate_arguments(LLVM_DEFINITIONS_LIST NATIVE_COMMAND ${LLVM_DEFINITIONS})
add_definitions(${LLVM_DEFINITIONS_LIST})

include_directories(${MLIR_INCLUDE_DIRS})
link_directories(${MLIR_LIBRARY_DIR})

set(CORE_SOURCES
        
)