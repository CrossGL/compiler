@echo off

set LLVM_BUILD_DIR= thirdparty\llvm-project\build

if NOT EXIST %LLVM_BUILD_DIR% (
	echo run build-mlir.bat first
	EXIT /B
)

CALL "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"

MKDIR build

cmake -S . -B build -G "Visual Studio 17 2022" -A x64 -DCMAKE_PREFIX_PATH=thirdparty\llvm-project\build\lib\cmake\mlir

cmake --build build --target crossgl-opt -j 2

:: generates the LLVM Dialect -> print.ll 
.\build\bin\crossgl-opt.exe .\test\Crossgl\print.mlir > build\bin\print.ll

PAUSE