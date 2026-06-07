#pragma once

#include "crossgl/HIR/HIR.h"

namespace crossgl {

template <typename ValueTypeSupported, typename ExpressionSupported,
          typename TextureSampleSupported, typename TextureCompareSupported>
bool expressionSupportedByPolicy(
    const HIRExpression &expression, ValueTypeSupported valueTypeSupported,
    ExpressionSupported expressionSupported,
    TextureSampleSupported textureSampleSupported,
    TextureCompareSupported textureCompareSupported) {
  switch (expression.kind) {
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::Literal:
    return true;
  case HIRExpressionKind::Group:
  case HIRExpressionKind::Unary:
  case HIRExpressionKind::NonUniform:
    return expression.children.size() == 1 &&
           expressionSupported(expression.children.front());
  case HIRExpressionKind::MemberAccess:
    return expression.children.size() == 1 &&
           expressionSupported(expression.children.front());
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::Binary:
    return expression.children.size() == 2 &&
           expressionSupported(expression.children[0]) &&
           expressionSupported(expression.children[1]);
  case HIRExpressionKind::Constructor:
    if (!valueTypeSupported(expression.type)) {
      return false;
    }
    for (const HIRExpression &child : expression.children) {
      if (!expressionSupported(child)) {
        return false;
      }
    }
    return true;
  case HIRExpressionKind::Call:
  case HIRExpressionKind::Select:
    return false;
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    return textureCompareSupported(expression);
  case HIRExpressionKind::TextureSample:
    return textureSampleSupported(expression);
  }
  return false;
}

template <typename Predicate>
bool expressionTreeContains(const HIRExpression &expression,
                            Predicate predicate) {
  if (predicate(expression)) {
    return true;
  }
  for (const HIRExpression &child : expression.children) {
    if (expressionTreeContains(child, predicate)) {
      return true;
    }
  }
  return false;
}

template <typename Visitor>
void visitExpressionTree(const HIRExpression &expression, Visitor &visitor) {
  visitor(expression);
  for (const HIRExpression &child : expression.children) {
    visitExpressionTree(child, visitor);
  }
}

template <typename Visitor>
void visitStatementExpressions(const HIRStatement &statement,
                               Visitor &visitor) {
  visitExpressionTree(statement.target, visitor);
  visitExpressionTree(statement.value, visitor);
  for (const HIRStatement &initializer : statement.initializer) {
    visitStatementExpressions(initializer, visitor);
  }
  for (const HIRStatement &update : statement.update) {
    visitStatementExpressions(update, visitor);
  }
  for (const HIRStatement &child : statement.body) {
    visitStatementExpressions(child, visitor);
  }
  for (const HIRStatement &child : statement.elseBody) {
    visitStatementExpressions(child, visitor);
  }
}

template <typename Visitor>
void visitFunctionExpressions(const HIRFunction &function, Visitor &visitor) {
  for (const HIRStatement &statement : function.body) {
    visitStatementExpressions(statement, visitor);
  }
}

template <typename Visitor>
void visitModuleExpressions(const HIRModule &module, Visitor &visitor,
                            bool includeConstants) {
  if (includeConstants) {
    for (const HIRConstant &constant : module.constants) {
      visitExpressionTree(constant.value, visitor);
    }
  }
  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &function : stage.functions) {
      visitFunctionExpressions(function, visitor);
    }
  }
  for (const HIRFunction &function : module.functions) {
    visitFunctionExpressions(function, visitor);
  }
}

template <typename Predicate>
bool statementExpressionsContain(const HIRStatement &statement,
                                 Predicate predicate) {
  if (expressionTreeContains(statement.target, predicate) ||
      expressionTreeContains(statement.value, predicate)) {
    return true;
  }
  for (const HIRStatement &initializer : statement.initializer) {
    if (statementExpressionsContain(initializer, predicate)) {
      return true;
    }
  }
  for (const HIRStatement &update : statement.update) {
    if (statementExpressionsContain(update, predicate)) {
      return true;
    }
  }
  for (const HIRStatement &child : statement.body) {
    if (statementExpressionsContain(child, predicate)) {
      return true;
    }
  }
  for (const HIRStatement &child : statement.elseBody) {
    if (statementExpressionsContain(child, predicate)) {
      return true;
    }
  }
  return false;
}

template <typename Predicate>
bool functionExpressionsContain(const HIRFunction &function,
                                Predicate predicate) {
  for (const HIRStatement &statement : function.body) {
    if (statementExpressionsContain(statement, predicate)) {
      return true;
    }
  }
  return false;
}

template <typename Predicate>
bool moduleExpressionsContain(const HIRModule &module, Predicate predicate,
                              bool includeConstants) {
  if (includeConstants) {
    for (const HIRConstant &constant : module.constants) {
      if (expressionTreeContains(constant.value, predicate)) {
        return true;
      }
    }
  }
  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &function : stage.functions) {
      if (functionExpressionsContain(function, predicate)) {
        return true;
      }
    }
  }
  for (const HIRFunction &function : module.functions) {
    if (functionExpressionsContain(function, predicate)) {
      return true;
    }
  }
  return false;
}

} // namespace crossgl
