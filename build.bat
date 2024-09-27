@echo off

set LLVM_BUILD_DIR= thirdparty\llvm-project\build

if NOT EXIST %LLVM_BUILD_DIR% (
	echo run build-mlir.bat first
	EXIT /B
)

if NOT EXIST build (
	MKDIR build
)

cmake -S . -B build -G "Visual Studio 17 2022" -A x64 -DCMAKE_PREFIX_PATH=thirdparty\llvm-project\install

cmake --build build --config Release --target crossgl-opt

:: generates the LLVM Dialect -> print.ll 
.\build\bin\crossgl-opt.exe .\test\Crossgl\print.mlir > build\bin\print.ll

PAUSE