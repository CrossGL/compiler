#pragma once

#include "crossgl/HIR/HIR.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <cstddef>
#include <optional>
#include <string>

namespace crossgl {

inline std::optional<HIRType>
backendConstructorScalarOrVectorComponentType(const HIRType &type) {
  if (type.arraySize.has_value() || type.name.empty()) {
    return std::nullopt;
  }
  const std::string baseName = baseTypeName(type);
  if (isVectorType(baseName)) {
    return scalarTypeForVector(baseName);
  }
  if (baseName == "bool" || isNumericScalarTypeName(baseName)) {
    return HIRType{baseName, std::nullopt};
  }
  return std::nullopt;
}

inline bool backendConstructorComponentConvertible(
    const HIRType &targetComponentType, const HIRType &sourceComponentType) {
  if (sameType(targetComponentType, sourceComponentType)) {
    return true;
  }
  if (isScalarBoolType(targetComponentType) ||
      isScalarBoolType(sourceComponentType)) {
    return false;
  }
  return isNumericScalarTypeName(baseTypeName(targetComponentType)) &&
         isNumericScalarTypeName(baseTypeName(sourceComponentType));
}

inline std::optional<std::size_t>
backendConstructorConstituentWidth(const HIRExpression &operand,
                                   const HIRType &componentType) {
  const std::optional<HIRType> operandComponentType =
      backendConstructorScalarOrVectorComponentType(operand.type);
  if (!operandComponentType.has_value() ||
      !backendConstructorComponentConvertible(componentType,
                                              *operandComponentType)) {
    return std::nullopt;
  }
  const std::string operandBaseName = baseTypeName(operand.type);
  if (isVectorType(operandBaseName)) {
    return vectorWidthFromName(operandBaseName);
  }
  return std::size_t{1};
}

template <typename ValueTypeSupported, typename ExpressionSupported>
bool backendConstructorShapeSupported(
    const HIRExpression &expression, ValueTypeSupported valueTypeSupported,
    ExpressionSupported expressionSupported) {
  if (expression.kind != HIRExpressionKind::Constructor ||
      !valueTypeSupported(expression.type) || expression.value.empty() ||
      expression.children.empty()) {
    return false;
  }

  const std::string targetBaseName = baseTypeName(expression.type);
  if (expression.value != targetBaseName) {
    return false;
  }

  for (const HIRExpression &child : expression.children) {
    if (!expressionSupported(child)) {
      return false;
    }
  }

  if (targetBaseName == "bool") {
    return expression.children.size() == 1 &&
           isScalarBoolType(expression.children.front().type);
  }

  if (isNumericScalarTypeName(targetBaseName)) {
    return expression.children.size() == 1 &&
           !expression.children.front().type.arraySize.has_value() &&
           isNumericScalarTypeName(baseTypeName(expression.children.front().type));
  }

  const std::optional<std::size_t> vectorWidth =
      vectorWidthFromName(targetBaseName);
  if (vectorWidth.has_value()) {
    const HIRType componentType = scalarTypeForVector(targetBaseName);
    std::size_t componentCount = 0;
    for (const HIRExpression &operand : expression.children) {
      const std::optional<std::size_t> operandWidth =
          backendConstructorConstituentWidth(operand, componentType);
      if (!operandWidth.has_value()) {
        return false;
      }
      componentCount += *operandWidth;
    }
    return (expression.children.size() == 1 &&
            componentCount == std::size_t{1}) ||
           componentCount == *vectorWidth;
  }

  const std::optional<std::size_t> matrixElementCount =
      matrixElementCountFromName(targetBaseName);
  if (matrixElementCount.has_value()) {
    if (expression.children.size() == 1 &&
        !expression.children.front().type.arraySize.has_value()) {
      const std::string sourceBaseName =
          baseTypeName(expression.children.front().type);
      if (isMatrixType(sourceBaseName) ||
          isNumericScalarTypeName(sourceBaseName)) {
        return true;
      }
    }

    const HIRType componentType{"float", std::nullopt};
    std::size_t componentCount = 0;
    for (const HIRExpression &operand : expression.children) {
      const std::optional<std::size_t> operandWidth =
          backendConstructorConstituentWidth(operand, componentType);
      if (!operandWidth.has_value()) {
        return false;
      }
      componentCount += *operandWidth;
    }
    return componentCount == *matrixElementCount;
  }

  return false;
}

template <typename ExpressionSupported, typename TextureSampleSupported,
          typename TextureCompareSupported, typename ConstructorSupported>
bool expressionSupportedByPolicy(
    const HIRExpression &expression, ExpressionSupported expressionSupported,
    TextureSampleSupported textureSampleSupported,
    TextureCompareSupported textureCompareSupported,
    ConstructorSupported constructorSupported) {
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
    return constructorSupported(expression);
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
