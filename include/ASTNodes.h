#ifndef ASTNODES_H
#define ASTNODES_H
#include <memory>
#include <string>

class ASTNode {
public:
  virtual ~ASTNode() = default;
  virtual void print() const = 0; // DEBUGGING
};

class Expr : public ASTNode {};
class Stmt : public ASTNode {};

class Variable : public Expr {
public:
  std::string name;
  explicit Variable(std::string name);
  void print() const override;
};

class NumericLiteral : public Expr {
public:
  int value;
  explicit NumericLiteral(int value);
  void print() const override;
};

// For handling ' +, -, *, /, %'
class BinaryExpr : public Expr {
public:
  std::string op;
  std::shared_ptr<Expr> left, right;
  BinaryExpr(const std::string &op, const std::shared_ptr<Expr> &left,
             const std::shared_ptr<Expr> &right);
  void print() const override;
};

// For handling assignments
class Assignment : public Expr {
public:
  std::shared_ptr<Variable> left;
  std::shared_ptr<Expr> right;
  Assignment(std::shared_ptr<Variable> variable, std::shared_ptr<Expr> value);
};

#endif
