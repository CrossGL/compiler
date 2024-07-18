#include "lexer.h"
#include<cctype>
#include<stdexcept>
#include<iostream>

static void printTokenDebugInfo (Token& token){
    switch(token.type) {
        case TokenType::NUMBER :
            std::cout << "\nType : Number \n";
            break;
        case TokenType::SYMBOL :
            std::cout << "\nType : Symbol \n";
            break;
        case TokenType::KEYWORD :
            std::cout << "\nType : Keyword \n";
            break;
        case TokenType::IDENTIFIER :
            std::cout << "\nType : Identifier \n";
            break;
        case TokenType::END_OF_FILE :
            std::cout << "\nType : End of file! \n";
            break;
    }
    if(token.type == TokenType::END_OF_FILE) {
        std::cout << "Value : END_OF_FILE!" ;
        return;
    }
    std::cout << "Value : " << token.value ;
}

Lexer::Lexer(const std::string &source) : source{source}, index{0}{}

char Lexer::currentChar() {
    char toBeReturned = '\0';
    if(index < source.length()) {
        toBeReturned = source[index];
    }
    return toBeReturned;
}

inline void Lexer::advance() {
    if(index < source.length()) {
        index += 1;
    }
}

void Lexer::skipWhitespace() {
    while(std::isspace(Lexer::currentChar())) {
        advance();
    }
}

Token Lexer::number() {
    std::string value;
    while(std::isdigit(Lexer::currentChar())) {
        value += Lexer::currentChar();
        advance();
    }
    Token token = {TokenType::NUMBER, value};
    return token;
}

Token Lexer::identifier() {
    std::string identifierValue;
    while(std::isalnum(Lexer::currentChar())) {
        identifierValue += Lexer::currentChar();
        advance();
    }
    if(identifierValue == "if" ||
       identifierValue == "else" ||
       identifierValue == "for" ||
       identifierValue == "while" ||
       identifierValue == "return") {
        return {TokenType::KEYWORD, identifierValue};
    }
    return {TokenType::IDENTIFIER, identifierValue};
}

Token Lexer::symbol() {
    char c = currentChar();
    advance();
    return {TokenType::SYMBOL, std::string(1,c)};
}



std::vector<Token> Lexer::tokenize() {
    std::vector<Token> tokens;
    while(currentChar() != '\0') {
        if(std::isalpha(currentChar())) {
            tokens.push_back(Lexer::identifier());
        }
        else if(std::isdigit(currentChar())) {
            tokens.push_back(Lexer::number()) ;
        }
        else if(std::isspace(currentChar())) {
            Lexer::skipWhitespace();
        }
        else {
            tokens.push_back(Lexer::symbol());
        }
    }
    tokens.push_back({TokenType::END_OF_FILE,""});
    return tokens;
}


int main() {
    std::string source = "while(x=10)";
    Lexer lexer = Lexer(source);
    std::vector<Token> tokens = lexer.tokenize();
    for(auto token : tokens) {
        printTokenDebugInfo(token);
    }

}





