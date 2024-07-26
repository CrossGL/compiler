#include "lexer.h"

namespace XGLUtils {
  // For better documentation
  bool isaplhanum(char c) { return isdigit(c) or isalpha(c); }
  bool isKeywordCheck(const std::string& string) {
    if(string == "int" || string == "float" || string == "bool" ||
       string == "vec2" || string == "vec3" || string == "vec4" ||
       string == "mat2" || string == "mat3" || string == "mat4" ||
       string == "sampler2D" || string == "sampler3D" || string == "shader" ||
       string == "void" || string == "return"
       )
      return true;
    return false;
  }

}


Lexer::Lexer(const std::string &source) {
  this->source = source;
  index = 0;
}

char Lexer::currentChar() { return source[index]; }

int Lexer::advance() {
  if (index > source.length() - 1)
    return 0;
  ++index;
  return 1;
}

void Lexer::skipWhitespace() {
  while (isblank(currentChar())) {

    advance();
  }
}

Token Lexer::number() {
  std::string num;

  do {
    num += currentChar();
    advance();
  } while (isdigit(currentChar()));

  return {TokenType::NUMBER, num};
}


Token Lexer::identifier() {
  std::string vname;
  do {
    vname += currentChar();
    advance();
  } while (XGLUtils::isaplhanum(
      currentChar()) || currentChar() == '_'); // Underscore support added
  if(XGLUtils::isKeywordCheck(vname)) return {TokenType::KEYWORD, vname};
  return {TokenType::IDENTIFIER, vname};
}

std::vector<Token> Lexer::getTokens() {
  std::vector<Token> tokens;
  do {

    if (currentChar() == ' ')
      skipWhitespace();
    if (currentChar() == '\0')
      tokens.emplace_back(TokenType::END_OF_FILE, "\0");
    if (isalpha(currentChar()))
      tokens.push_back(identifier());
    if (isdigit(currentChar()))
      tokens.push_back(number());
    if (currentChar() == '+' or currentChar() == '-' or currentChar() == '/' or
        currentChar() == '*' or currentChar() == '=' or currentChar() == ';' or
        currentChar() == '(' or currentChar() == ')' or currentChar() == ',') {
      std::string s;
      s += currentChar();
      tokens.emplace_back(TokenType::SYMBOL, s);
    }
  } while (advance());

  return tokens;
}