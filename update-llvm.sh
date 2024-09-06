#!/bin/bash

set -e

git subtree pull --squash --prefix thirdparty/llvm-project git@github.com:llvm/llvm-project.git main

pushd $PWD/thirdparty/llvm-project/build
cmake -G Ninja ../llvm \
   -DLLVM_ENABLE_PROJECTS=mlir \
   -DLLVM_BUILD_EXAMPLES=ON \
   -DLLVM_TARGETS_TO_BUILD="host" \
   -DCMAKE_BUILD_TYPE=Release \
   -DLLVM_ENABLE_ASSERTIONS=ON -Wno-dev
cmake --build . --target check-mlir

popd
pushd $PWD/build
