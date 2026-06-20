#pragma once

#include "crossgl/Backend/BackendTokens.h"
#include "crossgl/HIR/HIR.h"

namespace crossgl {

template <typename ValueTypeSupported, typename ExpressionSupported>
bool statementSupportedByPolicy(const HIRStatement &statement,
                                ValueTypeSupported valueTypeSupported,
                                ExpressionSupported expressionSupported);

template <typename ValueTypeSupported, typename ExpressionSupported>
bool loopHeaderStatementSupportedByPolicy(
    const HIRStatement &statement, ValueTypeSupported valueTypeSupported,
    ExpressionSupported expressionSupported) {
  return (statement.kind == HIRStatementKind::Declaration ||
          statement.kind == HIRStatementKind::Assignment ||
          statement.kind == HIRStatementKind::Expression) &&
         statementSupportedByPolicy(statement, valueTypeSupported,
                                    expressionSupported);
}

template <typename ValueTypeSupported, typename ExpressionSupported>
bool statementSupportedByPolicy(const HIRStatement &statement,
                                ValueTypeSupported valueTypeSupported,
                                ExpressionSupported expressionSupported) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    return valueTypeSupported(statement.declaredType) &&
           expressionSupported(statement.value);
  case HIRStatementKind::Assignment:
    return expressionSupported(statement.target) &&
           expressionSupported(statement.value);
  case HIRStatementKind::Return:
    return statement.value.kind == HIRExpressionKind::Empty ||
           expressionSupported(statement.value);
  case HIRStatementKind::Expression:
    return expressionSupported(statement.value);
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
    return true;
  case HIRStatementKind::Block:
    for (const HIRStatement &child : statement.body) {
      if (!statementSupportedByPolicy(child, valueTypeSupported,
                                      expressionSupported)) {
        return false;
      }
    }
    return true;
  case HIRStatementKind::If:
    if (!expressionSupported(statement.value)) {
      return false;
    }
    for (const HIRStatement &child : statement.body) {
      if (!statementSupportedByPolicy(child, valueTypeSupported,
                                      expressionSupported)) {
        return false;
      }
    }
    for (const HIRStatement &child : statement.elseBody) {
      if (!statementSupportedByPolicy(child, valueTypeSupported,
                                      expressionSupported)) {
        return false;
      }
    }
    return true;
  case HIRStatementKind::For:
    if (!expressionSupported(statement.value) || statement.initializer.size() > 1) {
      return false;
    }
    for (const HIRStatement &initializer : statement.initializer) {
      if (!loopHeaderStatementSupportedByPolicy(
              initializer, valueTypeSupported, expressionSupported)) {
        return false;
      }
    }
    if (!statement.update.empty()) {
      if (statement.update.size() > 1) {
        return false;
      }
      for (const HIRStatement &update : statement.update) {
        if (!loopHeaderStatementSupportedByPolicy(
                update, valueTypeSupported, expressionSupported)) {
          return false;
        }
      }
    } else if (!statement.updateTokens.empty() &&
               !rawLoopUpdateSupported(statement.updateTokens)) {
      return false;
    }
    for (const HIRStatement &child : statement.body) {
      if (!statementSupportedByPolicy(child, valueTypeSupported,
                                      expressionSupported)) {
        return false;
      }
    }
    return true;
  case HIRStatementKind::Raw:
    return false;
  }
  return false;
}

template <typename ConstantSupported>
bool constantsSupportedByPolicy(const HIRModule &module,
                                ConstantSupported constantSupported) {
  for (const HIRConstant &constant : module.constants) {
    if (!constantSupported(constant)) {
      return false;
    }
  }
  return true;
}

template <typename StatementSupported>
bool functionBodySupportedByPolicy(const HIRFunction &function,
                                   StatementSupported statementSupported) {
  for (const HIRStatement &statement : function.body) {
    if (!statementSupported(statement)) {
      return false;
    }
  }
  return true;
}

} // namespace crossgl
