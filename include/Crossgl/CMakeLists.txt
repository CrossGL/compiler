cmake_minimum_required(VERSION 3.16)
project(mlir-hello LANGUAGES CXX C)

find_package(MLIR REQUIRED CONFIG)


add_mlir_dialect(CrossglOps crossgl)

add_mlir_doc(CrossglDialect CrossglDialect Crossgl/ -gen-dialect-doc)

add_mlir_doc(CrossglOps CrossglOps Crossgl/ -gen-op-doc)
