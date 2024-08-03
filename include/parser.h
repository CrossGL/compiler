#ifndef PARSER_H
#define PARSER_H
#include "../headers/lexer.h"
#include<string>
#include<ASTNodes.h>

class Parser {
private:
    Lexer::Lexer lexer;
public:
    bool _has_error;
    explicit Parser(const std::string& source);
    std::shared_ptr<Expr> parseExpr()




};

#endif
