#include "XGLUtils.h"

#include <algorithm>
#include <cctype>
#include <lexer.h>

inline bool XGLUtils::isaplhanum(char c) { return isdigit(c) or isalpha(c); }

bool XGLUtils::isKeywordCheck(const std::string &word) {
  return std::find(keywords.begin(), keywords.end(), word) != keywords.end();
}
