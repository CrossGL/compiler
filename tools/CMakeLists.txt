add_executable(driver driver.cpp
        ../src/core.cpp
        ../lib/Custom-Namespaces/XGLUtils.cpp
        ../include/ASTNodes.h
        ../lib/Parser/ASTNodes.cpp)
target_link_libraries(driver CrossGL-Lexer)