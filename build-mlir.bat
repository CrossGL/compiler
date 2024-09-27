@echo off

set LLVM_SOURCE_DIR=	.\thirdparty\llvm-project\llvm
set LLVM_BUILD_DIR=		.\thirdparty\llvm-project\build

if NOT EXIST %LLVM_BUILD_DIR% (
	MKDIR %LLVM_BUILD_DIR%
)

:: building MLIR with LLVM

cmake -S %LLVM_SOURCE_DIR% -B %LLVM_BUILD_DIR% -G Ninja -DLLVM_ENABLE_PROJECTS=mlir -DLLVM_BUILD_EXAMPLES=OFF -DLLVM_TARGETS_TO_BUILD="X86" -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_ASSERTIONS=ON -DCMAKE_INSTALL_PREFIX=.\thirdparty\llvm-project\install

cmake --build %LLVM_BUILD_DIR% --target install
