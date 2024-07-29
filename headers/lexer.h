//Please don't judge my bad code aha

#ifndef LEXER_H
#define LEXER_H

#include <string>
#include <vector>

enum class TokenType {
    IDENTIFIER,
    KEYWORD,
    NUMBER,
    SYMBOL,
    FUNCTIONCALL,
    DATATYPE,
    END_OF_FILE
};

struct Token {
    TokenType type;
    std::string value;
    Token(TokenType t,std::string v){type=t;value=v;}
};

class Lexer {
public:
    Lexer(const std::string &source);
    std::vector<Token> getTokens();
private:
    std::string source;
    size_t index;
    char currentChar();

    bool advance();
    void skipWhitespace();
    char peekAhead();
    Token number();
    Token datatype();
    Token identifier();
    Token symbol();

};

#endif // LEXER_H
