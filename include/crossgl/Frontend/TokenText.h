#pragma once

#include "crossgl/Frontend/Token.h"

#include <string>
#include <vector>

namespace crossgl {

bool isWordLikeToken(TokenKind kind);
std::string tokensToText(const std::vector<Token> &tokens);

} // namespace crossgl
