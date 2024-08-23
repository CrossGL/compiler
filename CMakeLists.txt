cmake_minimum_required(VERSION 3.16)
project(CrossGL LANGUAGES CXX)

# Enable C++17 standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED YES)

# Find MLIR
find_package(MLIR REQUIRED CONFIG)

# Include directories
include_directories(${CMAKE_SOURCE_DIR}/include)

# Add source files
set(SOURCES
        include/CrossGL/CrossGL.cpp
        include/CrossGL/CrossGLDialect.cpp
        include/CrossGL/CrossGLOps.cpp
        "include/Cross GL/CrossGL.h"
        "include/Cross GL/CrossDLDialect.cpp"
        "include/Cross GL/CrossDLDialect.h"
        "include/Cross GL/CrossGLOps.cpp"
        "include/Cross GL/CrossGLOps.h"
        "include/Cross GL/CrossGL.cpp"
        tests/crossgl-tests.cpp
        include/DirectX/DirectXBackend.cpp
        include/DirectX/DirectXBackend.h
        include/Metal/MetalBackend.cpp
        include/Metal/MetalBackend.h
)

# Add backend source files
list(APPEND SOURCES
        include/DirectX/DirectXBackend.cpp
        include/Metal/MetalBackend.cpp
)

# Define the main executable
add_executable(CrossGL ${SOURCES} include/CrossGL/main.cpp)

# Link MLIR libraries
target_link_libraries(CrossGL PRIVATE MLIR)

# Add the test directory
add_subdirectory(tests)
