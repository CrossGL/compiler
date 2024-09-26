@echo off

:: default msvc command-line tool execution
CALL "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"

set LLVM_SOURCE_DIR=	.\thirdparty\llvm-project\llvm
set LLVM_BUILD_DIR=		.\thirdparty\llvm-project\build

MKDIR %LLVM_BUILD_DIR%

:: building MLIR with LLVM

cmake %LLVM_SOURCE_DIR% -B %LLVM_BUILD_DIR% -G "Visual Studio 17 2022" -A x64 -DLLVM_ENABLE_PROJECTS=mlir -DLLVM_BUILD_EXAMPLES=OFF -DLLVM_TARGETS_TO_BUILD="X86" -DCMAKE_BUILD_TYPE=Release -Thost=x64 -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_ASSERTIONS=ON

cmake --build %LLVM_BUILD_DIR% --target check-mlir -j 4
