# Compiler 

## Windows
dependencies for building MLIR: `Visual Studio 17 2022`, `Python`, `CMake`, `Git`
```shell
.\build-mlir.bat # builds thirdparty\llvm-project
```
make sure to run `build-mlir.bat` before running the `build.bat` script
```shell
.\build.bat # complies and executes crossgl-opt target, which generates LLVM IR -> build\bin\print.ll 
```

## Lazy run 

```bash
./run.sh # This will install MLIR using the thirdpartyllvm and compile the CrossGL MLIR dialect
```

## Eager run 
```bash
./eager_run.sh # This will not install MLIR and will only compile the CrossGL MLIR dialect
```
