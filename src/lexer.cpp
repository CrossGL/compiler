#include "../headers/lexer.h"

bool isaplhanum(char c) { return isdigit(c) or isalpha(c) or c == '_'; } // supports Normal Identifier, along with '_'

Lexer::Lexer(const std::string &source)
{
    this->source = source;
    index = 0;
}

char Lexer::currentChar()
{
    return source[index];
}

bool Lexer::advance()
{
    if (index > source.length() - 1)
        return 0;
    ++index;
    return 1;
}

void Lexer::skipWhitespace()
{
    while (isblank(currentChar()))
    {

        advance();
    }
}

Token Lexer::number()
{
    std::string num = "";

    do
    {
        num += currentChar();
        advance();
    } while (isdigit(currentChar()) or currentChar() == '.'); // if the string has more than 1 '.' that should raise an error in the parser.

    return Token(TokenType::NUMBER, num);
}

Token Lexer::identifier()
{
    std::string vname = "";
    do
    {
        vname += currentChar();
        advance();
    } while (isaplhanum(currentChar()));

    return Token(TokenType::IDENTIFIER, vname);
}
char Lexer::peekAhead()
{
    if (index != source.length() - 1)
        return source[index + 1];
    return '\0';
}
std::vector<Token> Lexer::getTokens()
{
    std::string singleOperators = "+-/*=;(),{}&~><!|%";

    std::vector<Token> tokens;
    do
    {

        if (currentChar() == ' ')
            skipWhitespace();
        if (isalpha(currentChar()))
            tokens.push_back(identifier());
        if (isdigit(currentChar()))
            tokens.push_back(number());
        if (singleOperators.find(currentChar()) != singleOperators.npos)
        {
            std::string s = "";
            s += currentChar();

            //lets check if the operator is continued ahead or has a '=' symbol ahead
            if (peekAhead() == s[0] or peekAhead() == '=')
            { 
                advance();
                s += currentChar();
            }

            tokens.push_back(Token(TokenType::SYMBOL, s));
        }
    } while (advance());

    tokens.push_back(Token(TokenType::END_OF_FILE, "EOF"));
    return tokens;
}