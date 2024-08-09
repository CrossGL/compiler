#ifndef PARSER_H
#define PARSER_H
#include "../headers/lexer.h"
#include<string>
#include<ASTNodes.h>

/*
 * // THESE NOTES HAVE TO BE REMOVED IN THE PRODUCTION PHASE.
 * Top-down ( Recursive descending) parser.
 * Top-down approach uses Left Most derivation.
 * We have to be decisive in which production to use.
 */

class Parser {
private:
    Lexer::Lexer lexer;
public:
    bool _has_error;
    explicit Parser(const std::string& source);



};

#endif
