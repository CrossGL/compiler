#pragma once

#include <string>
#include <utility>

#include "crossgl/Basic/Diagnostic.h"

namespace crossgl {

enum class TokenKind {
  End,
  Identifier,
  Number,
  String,
  KeywordShader,
  KeywordStruct,
  KeywordVertex,
  KeywordFragment,
  KeywordCompute,
  KeywordReturn,
  KeywordConst,
  KeywordReadonly,
  KeywordWriteonly,
  KeywordReadwrite,
  KeywordVar,
  KeywordUniform,
  KeywordBuffer,
  KeywordShared,
  KeywordInput,
  KeywordOutput,
  KeywordLayout,
  KeywordIn,
  Hash,
  LBrace,
  RBrace,
  LParen,
  RParen,
  LBracket,
  RBracket,
  Semicolon,
  Comma,
  Dot,
  Colon,
  Equal,
  Operator,
};

struct Token {
  TokenKind kind = TokenKind::End;
  std::string text;
  SourceLocation location;
};

std::string tokenKindName(TokenKind kind);
bool isStageKeyword(TokenKind kind);
std::string stageName(TokenKind kind);

} // namespace crossgl
