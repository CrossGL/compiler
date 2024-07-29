#ifndef PARSER_H
#define PARSER_H
#include "../headers/lexer.h"
#include<string>

class Parser {
private:
    Lexer::Lexer lexer;
public:
    bool _has_error;
    explicit Parser(const std::string& source) : lexer(source), _has_error(false) {

    }


};

#endif
