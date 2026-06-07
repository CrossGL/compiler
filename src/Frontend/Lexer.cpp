#include "crossgl/Frontend/Lexer.h"

#include <cctype>
#include <unordered_map>

namespace crossgl {
namespace {

constexpr std::string_view utf8ByteOrderMark = "\xEF\xBB\xBF";
constexpr std::string_view kSpecUnsupportedForNativeV0 =
    "spec.unsupported-for-native-v0";

bool isIdentifierStart(char ch) {
  return std::isalpha(static_cast<unsigned char>(ch)) || ch == '_';
}

bool isIdentifierBody(char ch) {
  return std::isalnum(static_cast<unsigned char>(ch)) || ch == '_';
}

bool isDecimalDigit(char ch) {
  return std::isdigit(static_cast<unsigned char>(ch));
}

bool isHexDigit(char ch) {
  return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f') ||
         (ch >= 'A' && ch <= 'F');
}

std::size_t scanDecimalExponent(std::string_view source, std::size_t offset) {
  if (offset >= source.size() ||
      (source[offset] != 'e' && source[offset] != 'E')) {
    return 0;
  }

  std::size_t cursor = offset + 1;
  if (cursor < source.size() &&
      (source[cursor] == '+' || source[cursor] == '-')) {
    ++cursor;
  }
  if (cursor >= source.size() || !isDecimalDigit(source[cursor])) {
    return 0;
  }
  while (cursor < source.size() && isDecimalDigit(source[cursor])) {
    ++cursor;
  }
  if (cursor < source.size() &&
      (source[cursor] == 'f' || source[cursor] == 'F')) {
    ++cursor;
  }
  return cursor;
}

std::size_t scanMalformedDecimalExponent(std::string_view source,
                                          std::size_t offset) {
  if (offset >= source.size() ||
      (source[offset] != 'e' && source[offset] != 'E')) {
    return 0;
  }

  std::size_t cursor = offset + 1;
  if (cursor < source.size() &&
      (source[cursor] == '+' || source[cursor] == '-')) {
    ++cursor;
  }
  if (cursor < source.size() && isDecimalDigit(source[cursor])) {
    return 0;
  }
  return cursor;
}

std::size_t scanHexFloatLiteral(std::string_view source, std::size_t offset) {
  if (offset + 2 > source.size() || source[offset] != '0' ||
      (source[offset + 1] != 'x' && source[offset + 1] != 'X')) {
    return 0;
  }

  std::size_t cursor = offset + 2;
  bool hasHexDigits = false;
  while (cursor < source.size() && isHexDigit(source[cursor])) {
    hasHexDigits = true;
    ++cursor;
  }
  if (cursor < source.size() && source[cursor] == '.') {
    ++cursor;
    while (cursor < source.size() && isHexDigit(source[cursor])) {
      hasHexDigits = true;
      ++cursor;
    }
  }
  if (!hasHexDigits || cursor >= source.size() ||
      (source[cursor] != 'p' && source[cursor] != 'P')) {
    return 0;
  }

  ++cursor;
  if (cursor < source.size() &&
      (source[cursor] == '+' || source[cursor] == '-')) {
    ++cursor;
  }
  if (cursor >= source.size() || !isDecimalDigit(source[cursor])) {
    return 0;
  }
  while (cursor < source.size() && isDecimalDigit(source[cursor])) {
    ++cursor;
  }
  if (cursor < source.size() &&
      (source[cursor] == 'f' || source[cursor] == 'F')) {
    ++cursor;
  }
  return cursor;
}

std::size_t scanMalformedHexFloatLiteral(std::string_view source,
                                         std::size_t offset) {
  if (offset + 1 >= source.size() || source[offset] != '0' ||
      (source[offset + 1] != 'x' && source[offset + 1] != 'X')) {
    return 0;
  }

  std::size_t cursor = offset + 2;
  bool hasHexDigits = false;
  bool hasDot = false;
  while (cursor < source.size() && isHexDigit(source[cursor])) {
    hasHexDigits = true;
    ++cursor;
  }
  if (cursor < source.size() && source[cursor] == '.') {
    hasDot = true;
    ++cursor;
    while (cursor < source.size() && isHexDigit(source[cursor])) {
      hasHexDigits = true;
      ++cursor;
    }
  }

  if (!hasHexDigits) {
    return hasDot ? cursor : 0;
  }
  if (cursor >= source.size() ||
      (source[cursor] != 'p' && source[cursor] != 'P')) {
    return hasDot ? cursor : 0;
  }

  ++cursor;
  if (cursor < source.size() &&
      (source[cursor] == '+' || source[cursor] == '-')) {
    ++cursor;
  }
  if (cursor < source.size() && isDecimalDigit(source[cursor])) {
    return 0;
  }
  return cursor;
}

TokenKind keywordKind(std::string_view text) {
  static const std::unordered_map<std::string_view, TokenKind> keywords = {
      {"shader", TokenKind::KeywordShader},
      {"struct", TokenKind::KeywordStruct},
      {"vertex", TokenKind::KeywordVertex},
      {"fragment", TokenKind::KeywordFragment},
      {"compute", TokenKind::KeywordCompute},
      {"return", TokenKind::KeywordReturn},
      {"const", TokenKind::KeywordConst},
      {"readonly", TokenKind::KeywordReadonly},
      {"writeonly", TokenKind::KeywordWriteonly},
      {"readwrite", TokenKind::KeywordReadwrite},
      {"var", TokenKind::KeywordVar},
      {"uniform", TokenKind::KeywordUniform},
      {"buffer", TokenKind::KeywordBuffer},
      {"shared", TokenKind::KeywordShared},
      {"input", TokenKind::KeywordInput},
      {"output", TokenKind::KeywordOutput},
      {"layout", TokenKind::KeywordLayout},
      {"in", TokenKind::KeywordIn},
  };
  auto it = keywords.find(text);
  return it == keywords.end() ? TokenKind::Identifier : it->second;
}

std::string normalizeSourceFileName(std::string fileName) {
  for (char &ch : fileName) {
    if (ch == '\\') {
      ch = '/';
    }
  }
  return fileName;
}

} // namespace

std::string tokenKindName(TokenKind kind) {
  switch (kind) {
  case TokenKind::End:
    return "end of file";
  case TokenKind::Identifier:
    return "identifier";
  case TokenKind::Number:
    return "number";
  case TokenKind::String:
    return "string";
  case TokenKind::KeywordShader:
    return "shader";
  case TokenKind::KeywordStruct:
    return "struct";
  case TokenKind::KeywordVertex:
    return "vertex";
  case TokenKind::KeywordFragment:
    return "fragment";
  case TokenKind::KeywordCompute:
    return "compute";
  case TokenKind::KeywordReturn:
    return "return";
  case TokenKind::KeywordConst:
    return "const";
  case TokenKind::KeywordReadonly:
    return "readonly";
  case TokenKind::KeywordWriteonly:
    return "writeonly";
  case TokenKind::KeywordReadwrite:
    return "readwrite";
  case TokenKind::KeywordVar:
    return "var";
  case TokenKind::KeywordUniform:
    return "uniform";
  case TokenKind::KeywordBuffer:
    return "buffer";
  case TokenKind::KeywordShared:
    return "shared";
  case TokenKind::KeywordInput:
    return "input";
  case TokenKind::KeywordOutput:
    return "output";
  case TokenKind::KeywordLayout:
    return "layout";
  case TokenKind::KeywordIn:
    return "in";
  case TokenKind::Hash:
    return "#";
  case TokenKind::LBrace:
    return "{";
  case TokenKind::RBrace:
    return "}";
  case TokenKind::LParen:
    return "(";
  case TokenKind::RParen:
    return ")";
  case TokenKind::LBracket:
    return "[";
  case TokenKind::RBracket:
    return "]";
  case TokenKind::Semicolon:
    return ";";
  case TokenKind::Comma:
    return ",";
  case TokenKind::Dot:
    return ".";
  case TokenKind::Colon:
    return ":";
  case TokenKind::Equal:
    return "=";
  case TokenKind::Operator:
    return "operator";
  }
  return "unknown";
}

bool isStageKeyword(TokenKind kind) {
  return kind == TokenKind::KeywordVertex || kind == TokenKind::KeywordFragment ||
         kind == TokenKind::KeywordCompute;
}

std::string stageName(TokenKind kind) {
  switch (kind) {
  case TokenKind::KeywordVertex:
    return "vertex";
  case TokenKind::KeywordFragment:
    return "fragment";
  case TokenKind::KeywordCompute:
    return "compute";
  default:
    return "";
  }
}

Lexer::Lexer(std::string fileName, std::string_view source,
             DiagnosticEngine &diagnostics)
    : fileName_(normalizeSourceFileName(std::move(fileName))), source_(source),
      diagnostics_(diagnostics) {
  if (source_.starts_with(utf8ByteOrderMark)) {
    source_.remove_prefix(utf8ByteOrderMark.size());
  }
}

std::vector<Token> Lexer::lex() {
  std::vector<Token> tokens;
  while (!atEnd()) {
    skipWhitespaceAndComments();
    if (atEnd()) {
      break;
    }

    const SourceLocation loc = location();
    const char ch = peek();
    if (isIdentifierStart(ch)) {
      tokens.push_back(lexIdentifier());
      continue;
    }
    if (std::isdigit(static_cast<unsigned char>(ch))) {
      tokens.push_back(lexNumber());
      continue;
    }
    if (ch == '"') {
      tokens.push_back(lexString());
      continue;
    }

    advance();
    switch (ch) {
    case '#':
      tokens.push_back(make(TokenKind::Hash, "#", loc));
      break;
    case '{':
      tokens.push_back(make(TokenKind::LBrace, "{", loc));
      break;
    case '}':
      tokens.push_back(make(TokenKind::RBrace, "}", loc));
      break;
    case '(':
      tokens.push_back(make(TokenKind::LParen, "(", loc));
      break;
    case ')':
      tokens.push_back(make(TokenKind::RParen, ")", loc));
      break;
    case '[':
      tokens.push_back(make(TokenKind::LBracket, "[", loc));
      break;
    case ']':
      tokens.push_back(make(TokenKind::RBracket, "]", loc));
      break;
    case ';':
      tokens.push_back(make(TokenKind::Semicolon, ";", loc));
      break;
    case ',':
      tokens.push_back(make(TokenKind::Comma, ",", loc));
      break;
    case '.':
      if (isDecimalDigit(peek())) {
        std::size_t digitsEnd = offset_;
        while (digitsEnd < source_.size() &&
               isDecimalDigit(source_[digitsEnd])) {
          ++digitsEnd;
        }
        const std::size_t exponentEnd = scanDecimalExponent(source_, digitsEnd);
        if (exponentEnd != 0) {
          std::string text(".");
          while (offset_ < exponentEnd) {
            text.push_back(advance());
          }
          tokens.push_back(make(TokenKind::Number, text, loc));
          break;
        }
        const std::size_t malformedExponentEnd =
            scanMalformedDecimalExponent(source_, digitsEnd);
        if (malformedExponentEnd != 0) {
          std::string text(".");
          while (offset_ < malformedExponentEnd) {
            text.push_back(advance());
          }
          diagnostics_.error("lex.malformed-float-literal",
                             "malformed scientific float literal: exponent "
                             "requires at least one decimal digit",
                             loc);
          tokens.push_back(make(TokenKind::Number, text, loc));
          break;
        }
      }
      tokens.push_back(make(TokenKind::Dot, ".", loc));
      break;
    case ':':
      tokens.push_back(make(TokenKind::Colon, ":", loc));
      break;
    case '=':
      if (peek() == '=') {
        advance();
        tokens.push_back(make(TokenKind::Operator, "==", loc));
      } else {
        tokens.push_back(make(TokenKind::Equal, "=", loc));
      }
      break;
    case '+':
    case '-':
    case '*':
    case '/':
    case '%':
    case '?':
    case '<':
    case '>':
    case '!':
    case '&':
    case '|': {
      std::string text(1, ch);
      if ((ch == '+' && peek() == '+') || (ch == '-' && peek() == '-') ||
          (ch == '<' && peek() == '=') || (ch == '>' && peek() == '=') ||
          (ch == '!' && peek() == '=') || (ch == '&' && peek() == '&') ||
          (ch == '|' && peek() == '|')) {
        text.push_back(advance());
      }
      tokens.push_back(make(TokenKind::Operator, text, loc));
      break;
    }
    case '\\': {
      if (peek() == '\n' || (peek() == '\r' && peek(1) == '\n')) {
        SourceLocation span = loc;
        span.endColumn = loc.column + 1;
        span.endOffset = loc.offset + 1;
        span.length = 1;
        diagnostics_.error(
            std::string(kSpecUnsupportedForNativeV0),
            "CrossTL/CrossGL native v0 does not support "
            "line-splicing/preprocessor continuation syntax "
            "(compatibility id decl.line-splicing-preprocessor)",
            std::move(span));
      } else {
        diagnostics_.error("lex.unexpected-character",
                           "unexpected character '" + std::string(1, ch) + "'",
                           loc);
      }
      break;
    }
    default:
      diagnostics_.error("lex.unexpected-character",
                         "unexpected character '" + std::string(1, ch) + "'", loc);
      break;
    }
  }

  tokens.push_back(make(TokenKind::End, "", location()));
  return tokens;
}

bool Lexer::atEnd() const { return offset_ >= source_.size(); }

char Lexer::peek(std::size_t lookahead) const {
  const std::size_t index = offset_ + lookahead;
  return index < source_.size() ? source_[index] : '\0';
}

char Lexer::advance() {
  const char ch = peek();
  ++offset_;
  if (ch == '\n') {
    ++line_;
    column_ = 1;
  } else {
    ++column_;
  }
  return ch;
}

SourceLocation Lexer::location() const {
  SourceLocation loc{fileName_, line_, column_, offset_};
  loc.endLine = line_;
  loc.endColumn = column_;
  loc.endOffset = offset_;
  return loc;
}

void Lexer::skipWhitespaceAndComments() {
  bool consumed = true;
  while (consumed && !atEnd()) {
    consumed = false;
    while (std::isspace(static_cast<unsigned char>(peek()))) {
      advance();
      consumed = true;
    }
    if (peek() == '/' && peek(1) == '/') {
      while (!atEnd() && peek() != '\n') {
        advance();
      }
      consumed = true;
    } else if (peek() == '/' && peek(1) == '*') {
      const SourceLocation loc = location();
      advance();
      advance();
      while (!atEnd() && !(peek() == '*' && peek(1) == '/')) {
        advance();
      }
      if (atEnd()) {
        diagnostics_.error("lex.unterminated-comment", "unterminated block comment",
                           loc);
        return;
      }
      advance();
      advance();
      consumed = true;
    }
  }
}

Token Lexer::lexIdentifier() {
  const SourceLocation loc = location();
  std::string text;
  while (isIdentifierBody(peek())) {
    text.push_back(advance());
  }
  return make(keywordKind(text), text, loc);
}

Token Lexer::lexNumber() {
  const SourceLocation loc = location();
  const std::size_t literalStart = offset_;
  std::string text;
  while (isDecimalDigit(peek())) {
    text.push_back(advance());
  }
  const std::size_t hexFloatEnd = scanHexFloatLiteral(source_, literalStart);
  if (hexFloatEnd != 0) {
    while (offset_ < hexFloatEnd) {
      text.push_back(advance());
    }
    return make(TokenKind::Number, text, loc);
  }
  const std::size_t malformedHexFloatEnd =
      scanMalformedHexFloatLiteral(source_, literalStart);
  if (malformedHexFloatEnd != 0) {
    while (offset_ < malformedHexFloatEnd) {
      text.push_back(advance());
    }
    diagnostics_.error("lex.malformed-float-literal",
                       "malformed hexadecimal float literal: expected binary "
                       "exponent with at least one decimal digit",
                       loc);
    return make(TokenKind::Number, text, loc);
  }
  if (peek() == '.' && isDecimalDigit(peek(1))) {
    text.push_back(advance());
    while (isDecimalDigit(peek())) {
      text.push_back(advance());
    }
  } else if (peek() == '.' && scanDecimalExponent(source_, offset_ + 1) != 0) {
    text.push_back(advance());
  }
  const std::size_t exponentEnd = scanDecimalExponent(source_, offset_);
  if (exponentEnd != 0) {
    while (offset_ < exponentEnd) {
      text.push_back(advance());
    }
    return make(TokenKind::Number, text, loc);
  }
  const std::size_t malformedExponentEnd =
      scanMalformedDecimalExponent(source_, offset_);
  if (malformedExponentEnd != 0) {
    while (offset_ < malformedExponentEnd) {
      text.push_back(advance());
    }
    diagnostics_.error("lex.malformed-float-literal",
                       "malformed scientific float literal: exponent requires "
                       "at least one decimal digit",
                       loc);
    return make(TokenKind::Number, text, loc);
  }
  return make(TokenKind::Number, text, loc);
}

Token Lexer::lexString() {
  const SourceLocation loc = location();
  std::string text;
  text.push_back(advance());
  while (!atEnd() && peek() != '"') {
    text.push_back(advance());
  }
  if (atEnd()) {
    diagnostics_.error("lex.unterminated-string", "unterminated string literal", loc);
    return make(TokenKind::String, text, loc);
  }
  text.push_back(advance());
  return make(TokenKind::String, text, loc);
}

Token Lexer::make(TokenKind kind, std::string text, SourceLocation loc) const {
  loc.endLine = line_;
  loc.endColumn = column_;
  loc.endOffset = offset_;
  loc.length = loc.endOffset >= loc.offset ? loc.endOffset - loc.offset : 0;
  return Token{kind, std::move(text), std::move(loc)};
}

} // namespace crossgl
