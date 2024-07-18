//Please don't judge my bad code aha

#ifndef LEXER_H
#define LEXER_H

#include <iostream>
#include <string>
#include <vector>

enum class TokenType {
    IDENTIFIER,
    KEYWORD,
    NUMBER,
    SYMBOL,
    END_OF_FILE
};

struct Token {
    TokenType type;
    std::string value;
};

static void printTokenDebugInfo (Token& token);

class Lexer {
public:
    explicit Lexer(const std::string &source);
    std::vector<Token> tokenize();
private:
    std::string source;
    size_t index;
    char currentChar();

    inline void advance();
    void skipWhitespace();
    Token number();
    Token identifier();
    Token symbol();
};

#endif // LEXER_H
