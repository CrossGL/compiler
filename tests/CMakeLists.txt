# test/CMakeLists.txt

add_executable(crossgl-tests test/crossgl-tests.cpp)
target_link_libraries(crossgl-tests PRIVATE CrossGL)
