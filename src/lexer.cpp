#include "../headers/lexer.h"

bool isaplhanum(char c){return isdigit(c) or isalpha(c) or c=='_';} // supports Normal Identifier, along with '_'

Lexer::Lexer(const std::string &source)
{
    this->source = source;
    index = 0;
}

char Lexer::currentChar()
{
    return source[index];
}

int Lexer::advance()
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
    } while (isdigit(currentChar()));

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

std::vector<Token> Lexer::getTokens()
{

    std::vector<Token> tokens;
    do
    {

        if (currentChar() == ' ')
            skipWhitespace();
        if (currentChar() == '\0')
            tokens.push_back(Token(TokenType::END_OF_FILE, "\0"));
        if (isalpha(currentChar()))
            tokens.push_back(identifier());
        if (isdigit(currentChar()))
            tokens.push_back(number());
        if (currentChar() == '+' or currentChar() == '-' or currentChar() == '/' or currentChar() == '*' or currentChar() == '=' or currentChar() == ';' or currentChar() == '(' or currentChar() == ')' or currentChar() == ',' or currentChar() == '{' or currentChar() == '}')
        {
            std::string s = "";
            s += currentChar();
            tokens.push_back(Token(TokenType::SYMBOL, s));
        }
    } while (advance());

    return tokens;
}