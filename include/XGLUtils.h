#ifndef XGLUTILS_H
#define XGLUTILS_H
#include <string>

namespace XGLUtils {
    static inline bool isaplhanum(char c);
    static bool isKeywordCheck(const std::string& word);
    // Namespace for custom Cross GL exceptions
    namespace XGLException{};


};

#endif //XGLUTILS_H
