#ifndef LEXER_H
#define LEXER_H

#include <string>
#include <utility>
#include <vector>

enum class TokenType { IDENTIFIER,
                       KEYWORD,
                       NUMBER,
                       SYMBOL,
                       DATATYPE,
                       END_OF_FILE };

inline std::vector<const std::string> keywords = { "int", "float", "bool", "vec2", "vec3", "vec4", "mat2", "mat3", "mat4",
                                       "sampler2D", "sampler3D", "shader", "void", "return", "samplerCube", "uint"
};

struct Token {
  TokenType type;
  std::string value;
  Token(TokenType t, std::string v) {
    type = t;
    value = std::move(v);
  }
};

class Lexer {
public:
  explicit Lexer(const std::string &source);
  std::vector<Token> getTokens();

private:
  std::string source;
  size_t index;
  char currentChar();

  int advance();
  void skipWhitespace();
  Token number();
  Token identifier();
  Token symbol();
};

#endif // LEXER_H