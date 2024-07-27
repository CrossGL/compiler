add_executable(driver driver.cpp
        ../src/core.cpp
        ../lib/Custom-Namespaces/XGLUtils.cpp)
target_link_libraries(driver CrossGL-Lexer)