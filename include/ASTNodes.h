#ifndef ASTNODES_H
#define ASTNODES_H

class ASTNode {
public:
    virtual ~ASTNode() = default;
    virtual void print() const = 0;
};

class Expr : public ASTNode {};
class Stmt : public ASTNode {};


#endif
