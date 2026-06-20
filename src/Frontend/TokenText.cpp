#include "crossgl/Frontend/TokenText.h"

#include <sstream>

namespace crossgl {

bool isWordLikeToken(TokenKind kind) {
  return kind == TokenKind::Identifier || kind == TokenKind::Number ||
         kind == TokenKind::String || kind == TokenKind::KeywordReturn ||
         kind == TokenKind::KeywordConst ||
         kind == TokenKind::KeywordReadonly ||
         kind == TokenKind::KeywordWriteonly ||
         kind == TokenKind::KeywordReadwrite ||
         kind == TokenKind::KeywordUniform ||
         kind == TokenKind::KeywordBuffer || kind == TokenKind::KeywordShared ||
         kind == TokenKind::KeywordInput || kind == TokenKind::KeywordOutput ||
         kind == TokenKind::KeywordIn;
}

std::string tokensToText(const std::vector<Token> &tokens) {
  std::ostringstream out;
  TokenKind previous = TokenKind::End;
  for (const Token &token : tokens) {
    if (isWordLikeToken(previous) && isWordLikeToken(token.kind)) {
      out << ' ';
    }
    out << token.text;
    if (token.kind == TokenKind::Comma) {
      out << ' ';
    }
    previous = token.kind;
  }
  return out.str();
}

} // namespace crossgl
