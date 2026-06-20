#include "crossgl/Backend/BackendTokens.h"

namespace crossgl {

bool rawLoopUpdateSupported(const std::vector<Token> &tokens) {
  return tokens.size() == 2 && tokens[0].kind == TokenKind::Identifier &&
         tokens[1].kind == TokenKind::Operator &&
         (tokens[1].text == "++" || tokens[1].text == "--");
}

} // namespace crossgl
