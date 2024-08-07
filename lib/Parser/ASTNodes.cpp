#include "ASTNodes.h"

#include <iostream>
#include <utility>

Variable::Variable(std::string name) : name{std::move(name)} {}
void Variable::print() const override {
  std::cout << "Variable( " << name << " )\n";
}

NumericLiteral::NumericLiteral(int value) : value{value} {}
void NumericLiteral::print() const override {
  std::cout << "Number( " << value << " )\n";
}

BinaryExpr::BinaryExpr(const std::string &op, const std::shared_ptr<Expr> &left,
                       const std::shared_ptr<Expr> &right) {
  this->op = op;
  this->left = left;
  this->right = right;
}
// should we display AST in an XML like format?
void BinaryExpr::print() const override {
  std::cout << "Binary Expression { \n"
               "Left Operand : ";
  left->print();
  std::cout << "\nOperator : " << op << "\nRight Operand : ";
  right->print();
  std::cout << "\n}";
}
