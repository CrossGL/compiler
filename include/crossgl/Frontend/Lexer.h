#pragma once

#include <string>
#include <string_view>
#include <vector>

#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/Frontend/Token.h"

namespace crossgl {

class Lexer {
public:
  Lexer(std::string fileName, std::string_view source, DiagnosticEngine &diagnostics);

  std::vector<Token> lex();

private:
  bool atEnd() const;
  char peek(std::size_t lookahead = 0) const;
  char advance();
  SourceLocation location() const;

  void skipWhitespaceAndComments();
  Token lexIdentifier();
  Token lexNumber();
  Token lexString();
  Token make(TokenKind kind, std::string text, SourceLocation loc) const;

  std::string fileName_;
  std::string_view source_;
  DiagnosticEngine &diagnostics_;
  std::size_t offset_ = 0;
  std::size_t line_ = 1;
  std::size_t column_ = 1;
};

} // namespace crossgl
