mkdir build && cd build
cmake -G  Ninja ..
cmake --build . --target crossgl-opt
cd ..
./build/bin/crossgl-opt ./test/Crossgl/print.mlir  > print.ll
# cat print.ll
