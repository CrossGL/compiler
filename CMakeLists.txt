cmake_minimum_required(VERSION 3.10)

project(compiler VERSION 1.0)

set(LLVM_VERSION  "18.1.8")

find_package(LLVM ${LLVM_VERSION} REQUIRED CONFIG)

include_directories(${LLVM_INCLUDE_DIRS})
link_directories(${LLVM_LIBRARY_DIRS})
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

add_subdirectory(lib)
add_subdirectory(tools)
