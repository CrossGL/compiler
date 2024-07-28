#include "ASTNodes.h"
#include<utility>

Variable::Variable(std::string name) : name{std::move(name)}{}

NumericLiteral::NumericLiteral(int value) : value{value} {}


