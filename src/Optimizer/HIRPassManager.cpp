#include "crossgl/Optimizer/HIRPassManager.h"
#include "crossgl/Basic/Json.h"
#include "crossgl/HIR/BuiltinEffects.h"
#include "crossgl/HIR/ConstantFolding.h"
#include "crossgl/HIR/Intrinsics.h"
#include "crossgl/HIR/SideEffects.h"
#include "crossgl/HIR/StorageShape.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <iterator>
#include <optional>
#include <ostream>
#include <set>
#include <sstream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace crossgl {
namespace {

bool isValidHIRStageName(std::string_view stage) {
  return stage == "vertex" || stage == "fragment" || stage == "compute";
}

bool hasHIRFunctionBody(const HIRFunction &function) {
  return !function.bodyTokens.empty() || !function.body.empty();
}

template <typename MutateBody>
bool mutateHIRFunctionBody(HIRFunction &function, MutateBody &&mutateBody) {
  const bool changed = mutateBody(function.body);
  if (changed) {
    function.bodyTokens.clear();
  }
  return changed;
}

template <typename MutateUpdate>
bool mutateHIRLoopUpdate(HIRStatement &statement, MutateUpdate &&mutateUpdate) {
  const bool changed = mutateUpdate(statement.update);
  if (changed) {
    statement.updateTokens.clear();
  }
  return changed;
}

bool hasHIRTypeShape(const HIRType &type) {
  return !type.name.empty() || type.arraySize.has_value();
}

bool hasHIRRuntimeArrayDimension(const HIRType &type) {
  if (!type.arraySize.has_value()) {
    return false;
  }

  std::string_view dimensions = *type.arraySize;
  std::size_t begin = 0;
  while (begin <= dimensions.size()) {
    const std::size_t separator = dimensions.find("][", begin);
    const std::string_view dimension =
        separator == std::string_view::npos
            ? dimensions.substr(begin)
            : dimensions.substr(begin, separator - begin);
    if (dimension.empty()) {
      return true;
    }
    if (separator == std::string_view::npos) {
      break;
    }
    begin = separator + 2;
  }
  return false;
}

bool isSingleHIRRuntimeArrayDimension(const HIRType &type) {
  return type.arraySize.has_value() && type.arraySize->empty();
}

bool isEmptyHIRExpressionSlot(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::Empty;
}

bool isHIRPseudoControlIdentifier(std::string_view value) {
  return value == "else";
}

bool isValidHIRUnaryOperator(std::string_view value) {
  return value == "+" || value == "-" || value == "!";
}

bool isValidHIRBinaryOperator(std::string_view value) {
  return value == "+" || value == "-" || value == "*" || value == "/" ||
         value == "%" || value == "<" || value == "<=" || value == ">" ||
         value == ">=" || value == "==" || value == "!=" || value == "&&" ||
         value == "||";
}

bool isHIRImageAccessResourceOperand(const HIRExpression &parent,
                                     std::size_t childIndex) {
  return parent.kind == HIRExpressionKind::Call && childIndex == 0 &&
         isHIRImageAccessBuiltinCall(parent.value);
}

bool hasFixedHIRExpressionChildCount(HIRExpressionKind kind,
                                     std::size_t &expected) {
  switch (kind) {
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::Literal:
    expected = 0;
    return true;
  case HIRExpressionKind::Group:
  case HIRExpressionKind::MemberAccess:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::Unary:
    expected = 1;
    return true;
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::Binary:
    expected = 2;
    return true;
  case HIRExpressionKind::Select:
    expected = 3;
    return true;
  case HIRExpressionKind::Call:
  case HIRExpressionKind::Constructor:
  case HIRExpressionKind::TextureSample:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    return false;
  }
  return false;
}

void reportHIRTextureExpressionShape(const HIRExpression &expression,
                                     const std::string &context,
                                     std::string message,
                                     DiagnosticEngine &diagnostics) {
  diagnostics.error("opt.hir-texture-expression-shape",
                    "HIR " + context + " " +
                        expressionKindName(expression.kind) + " expression " +
                        std::move(message),
                    expression.location);
}

void validateHIRTextureSampleShape(const HIRExpression &expression,
                                   const std::string &context,
                                   DiagnosticEngine &diagnostics) {
  if (expression.value == "texture" || expression.value == "sample") {
    if (expression.children.size() != 2 && expression.children.size() != 3) {
      reportHIRTextureExpressionShape(
          expression, context,
          "with value '" + expression.value +
              "' must have 2 or 3 child expression(s), got " +
              std::to_string(expression.children.size()),
          diagnostics);
    }
    return;
  }

  if (expression.value == "textureLod") {
    if (expression.children.size() != 3 && expression.children.size() != 4) {
      reportHIRTextureExpressionShape(
          expression, context,
          "with value 'textureLod' must have 3 or 4 child expression(s), got " +
              std::to_string(expression.children.size()),
          diagnostics);
    }
    return;
  }

  reportHIRTextureExpressionShape(
      expression, context,
      "must use value 'texture', 'sample', or 'textureLod', got '" +
          expression.value + "'",
      diagnostics);
}

void validateHIRTextureCompareShape(const HIRExpression &expression,
                                    const std::string &context,
                                    DiagnosticEngine &diagnostics) {
  std::size_t expected = 0;
  if (expression.value == "textureCompare") {
    expected = 4;
  } else if (expression.value == "textureCompareLod") {
    expected = 5;
  } else {
    reportHIRTextureExpressionShape(
        expression, context,
        "must use value 'textureCompare' or 'textureCompareLod', got '" +
            expression.value + "'",
        diagnostics);
    return;
  }

  if (expression.children.size() != expected) {
    reportHIRTextureExpressionShape(
        expression, context,
        "with value '" + expression.value + "' must have " +
            std::to_string(expected) + " child expression(s), got " +
            std::to_string(expression.children.size()),
        diagnostics);
  }
}

bool hirManualTextureCompareExpectedChildCount(std::string_view value,
                                               std::size_t &expected) {
  if (value == "textureCompareLodManual") {
    expected = 6;
    return true;
  }
  if (value == "textureCompareLodManualOffset" ||
      value == "textureCompareLodManualKernel") {
    expected = 7;
    return true;
  }
  if (value == "textureCompareLodManualGather2x2") {
    expected = 6;
    return true;
  }
  if (value == "textureCompareLodManualKernel4") {
    expected = 14;
    return true;
  }
  if (value == "textureCompareLodManualKernel8") {
    expected = 22;
    return true;
  }
  return false;
}

void validateHIRManualTextureCompareKernelListShape(
    const HIRExpression &expression, const std::string &context,
    DiagnosticEngine &diagnostics) {
  if (expression.children.size() != 7 ||
      expression.value != "textureCompareLodManualKernel") {
    return;
  }

  const HIRExpression &kernelList = expression.children[6];
  if (kernelList.kind != HIRExpressionKind::Call ||
      !isHIRTextureCompareKernelBuiltinCall(kernelList.value)) {
    reportHIRTextureExpressionShape(
        expression, context,
        "with value 'textureCompareLodManualKernel' must use a "
        "textureCompareKernel(...) call as child expression 6",
        diagnostics);
    return;
  }
  if (kernelList.children.empty()) {
    reportHIRTextureExpressionShape(
        kernelList, context,
        "with value 'textureCompareKernel' must contain at least one tap pair",
        diagnostics);
    return;
  }
  if (kernelList.children.size() % 2 != 0) {
    reportHIRTextureExpressionShape(
        kernelList, context,
        "with value 'textureCompareKernel' must contain complete "
        "offset/weight tap pairs",
        diagnostics);
    return;
  }
  if (kernelList.children.size() / 2 > kMaxManualTextureCompareKernelTaps) {
    reportHIRTextureExpressionShape(
        kernelList, context,
        "with value 'textureCompareKernel' supports at most " +
            std::to_string(kMaxManualTextureCompareKernelTaps) + " tap pairs",
        diagnostics);
  }
}

void validateHIRManualTextureCompareShape(const HIRExpression &expression,
                                          const std::string &context,
                                          DiagnosticEngine &diagnostics) {
  std::size_t expected = 0;
  if (!hirManualTextureCompareExpectedChildCount(expression.value, expected)) {
    reportHIRTextureExpressionShape(
        expression, context,
        "must use a recognized manual texture compare value, got '" +
            expression.value + "'",
        diagnostics);
    return;
  }

  if (expression.children.size() != expected) {
    reportHIRTextureExpressionShape(
        expression, context,
        "with value '" + expression.value + "' must have " +
            std::to_string(expected) + " child expression(s), got " +
            std::to_string(expression.children.size()),
        diagnostics);
    return;
  }

  validateHIRManualTextureCompareKernelListShape(expression, context,
                                                diagnostics);
}

void validateHIRTextureExpressionShape(const HIRExpression &expression,
                                       const std::string &context,
                                       DiagnosticEngine &diagnostics) {
  switch (expression.kind) {
  case HIRExpressionKind::TextureSample:
    validateHIRTextureSampleShape(expression, context, diagnostics);
    return;
  case HIRExpressionKind::TextureCompare:
    validateHIRTextureCompareShape(expression, context, diagnostics);
    return;
  case HIRExpressionKind::TextureCompareLodManual:
    validateHIRManualTextureCompareShape(expression, context, diagnostics);
    return;
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::Literal:
  case HIRExpressionKind::Group:
  case HIRExpressionKind::MemberAccess:
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::Call:
  case HIRExpressionKind::Constructor:
  case HIRExpressionKind::Unary:
  case HIRExpressionKind::Binary:
  case HIRExpressionKind::Select:
    return;
  }
}

void reportHIRExpressionShape(const HIRExpression &expression,
                              const std::string &context, std::string message,
                              DiagnosticEngine &diagnostics) {
  diagnostics.error("opt.hir-expression-shape",
                    "HIR " + context + " " +
                        expressionKindName(expression.kind) + " expression " +
                        std::move(message),
                    expression.location);
}

void validateHIRExpressionPayloadShape(const HIRExpression &expression,
                                       const std::string &context,
                                       DiagnosticEngine &diagnostics) {
  switch (expression.kind) {
  case HIRExpressionKind::Identifier:
    if (expression.value.empty()) {
      reportHIRExpressionShape(expression, context,
                               "must preserve a non-empty identifier value",
                               diagnostics);
    }
    return;
  case HIRExpressionKind::Literal:
    if (expression.value.empty()) {
      reportHIRExpressionShape(expression, context,
                               "must preserve a non-empty literal value",
                               diagnostics);
    }
    return;
  case HIRExpressionKind::MemberAccess:
    if (expression.value.empty()) {
      reportHIRExpressionShape(expression, context,
                               "must preserve a non-empty member name",
                               diagnostics);
    }
    return;
  case HIRExpressionKind::Call:
    if (expression.value.empty()) {
      reportHIRExpressionShape(expression, context,
                               "must preserve a non-empty callee name",
                               diagnostics);
    }
    return;
  case HIRExpressionKind::Constructor:
    if (expression.value.empty()) {
      reportHIRExpressionShape(expression, context,
                               "must preserve a non-empty constructor name",
                               diagnostics);
    }
    if (expression.type.name.empty()) {
      reportHIRExpressionShape(expression, context,
                               "must declare a non-empty result type",
                               diagnostics);
    }
    return;
  case HIRExpressionKind::Unary:
    if (!isValidHIRUnaryOperator(expression.value)) {
      reportHIRExpressionShape(
          expression, context,
          "must use operator '+', '-', or '!', got '" + expression.value + "'",
          diagnostics);
    }
    return;
  case HIRExpressionKind::Binary:
    if (!isValidHIRBinaryOperator(expression.value)) {
      reportHIRExpressionShape(
          expression, context,
          "must use a parsed binary operator, got '" + expression.value + "'",
          diagnostics);
    }
    return;
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Group:
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::Select:
  case HIRExpressionKind::TextureSample:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    return;
  }
}

void validateHIRExpressionShape(const HIRExpression &expression,
                                const std::string &context,
                                DiagnosticEngine &diagnostics) {
  std::size_t expected = 0;
  if (hasFixedHIRExpressionChildCount(expression.kind, expected) &&
      expression.children.size() != expected) {
    diagnostics.error("opt.hir-expression-arity",
                      "HIR " + context + " " +
                          expressionKindName(expression.kind) +
                          " expression must have " +
                          std::to_string(expected) +
                          " child expression(s), got " +
                          std::to_string(expression.children.size()),
                      expression.location);
  }
  validateHIRExpressionPayloadShape(expression, context, diagnostics);
  validateHIRTextureExpressionShape(expression, context, diagnostics);

  for (const HIRExpression &child : expression.children) {
    validateHIRExpressionShape(child, context, diagnostics);
  }
}

SourceLocation hirStatementSourceLocation(const HIRStatement &statement) {
  if (!isEmptyHIRExpressionSlot(statement.target)) {
    return statement.target.location;
  }
  if (!isEmptyHIRExpressionSlot(statement.value)) {
    return statement.value.location;
  }
  if (hasHIRTypeShape(statement.declaredType)) {
    return statement.declaredType.location;
  }
  if (!statement.location.file.empty()) {
    return statement.location;
  }
  if (!statement.rawTokens.empty()) {
    return statement.rawTokens.front().location;
  }
  return {};
}

void reportHIRStatementShape(const HIRStatement &statement,
                             const std::string &context, std::string message,
                             DiagnosticEngine &diagnostics) {
  diagnostics.error("opt.hir-statement-shape", "HIR " + context + " " +
                                                   std::move(message),
                    hirStatementSourceLocation(statement));
}

bool isHIRLoopHeaderStatementKind(HIRStatementKind kind) {
  return kind == HIRStatementKind::Declaration ||
         kind == HIRStatementKind::Assignment ||
         kind == HIRStatementKind::Expression ||
         kind == HIRStatementKind::Raw;
}

void validateHIRUnexpectedStatementContainers(const HIRStatement &statement,
                                              const std::string &context,
                                              DiagnosticEngine &diagnostics) {
  if (!statement.initializer.empty()) {
    reportHIRStatementShape(statement, context,
                            "must not contain loop initializer statements",
                            diagnostics);
  }
  if (!statement.update.empty()) {
    reportHIRStatementShape(statement, context,
                            "must not contain loop update statements",
                            diagnostics);
  }
  if (!statement.updateTokens.empty()) {
    reportHIRStatementShape(statement, context,
                            "must not contain loop update tokens",
                            diagnostics);
  }
  if (!statement.body.empty()) {
    reportHIRStatementShape(statement, context,
                            "must not contain nested body statements",
                            diagnostics);
  }
  if (!statement.elseBody.empty()) {
    reportHIRStatementShape(statement, context,
                            "must not contain else-body statements",
                            diagnostics);
  }
}

void validateHIRStatementShape(const HIRStatement &statement,
                               const std::string &context,
                               DiagnosticEngine &diagnostics) {
  const std::string statementContext =
      context + " " + statementKindName(statement.kind) + " statement";
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    if (statement.name.empty()) {
      reportHIRStatementShape(statement, statementContext,
                              "must declare a variable name", diagnostics);
    }
    if (statement.declaredType.name.empty()) {
      reportHIRStatementShape(statement, statementContext,
                              "must declare a non-empty type", diagnostics);
    }
    if (!isEmptyHIRExpressionSlot(statement.target)) {
      reportHIRStatementShape(statement, statementContext,
                              "must not have an assignment target",
                              diagnostics);
    }
    validateHIRUnexpectedStatementContainers(statement, statementContext,
                                            diagnostics);
    break;
  case HIRStatementKind::Assignment:
    if (isEmptyHIRExpressionSlot(statement.target)) {
      reportHIRStatementShape(statement, statementContext,
                              "must have an assignment target", diagnostics);
    }
    if (isEmptyHIRExpressionSlot(statement.value)) {
      reportHIRStatementShape(statement, statementContext,
                              "must have an assignment value", diagnostics);
    }
    if (!statement.name.empty() || hasHIRTypeShape(statement.declaredType)) {
      reportHIRStatementShape(statement, statementContext,
                              "must not declare a variable", diagnostics);
    }
    validateHIRUnexpectedStatementContainers(statement, statementContext,
                                            diagnostics);
    break;
  case HIRStatementKind::Return:
    if (!isEmptyHIRExpressionSlot(statement.target)) {
      reportHIRStatementShape(statement, statementContext,
                              "must not have an assignment target",
                              diagnostics);
    }
    if (!statement.name.empty() || hasHIRTypeShape(statement.declaredType)) {
      reportHIRStatementShape(statement, statementContext,
                              "must not declare a variable", diagnostics);
    }
    validateHIRUnexpectedStatementContainers(statement, statementContext,
                                            diagnostics);
    break;
  case HIRStatementKind::Expression:
    if (isEmptyHIRExpressionSlot(statement.value)) {
      reportHIRStatementShape(statement, statementContext,
                              "must have an expression value", diagnostics);
    }
    if (!isEmptyHIRExpressionSlot(statement.target)) {
      reportHIRStatementShape(statement, statementContext,
                              "must not have an assignment target",
                              diagnostics);
    }
    if (!statement.name.empty() || hasHIRTypeShape(statement.declaredType)) {
      reportHIRStatementShape(statement, statementContext,
                              "must not declare a variable", diagnostics);
    }
    validateHIRUnexpectedStatementContainers(statement, statementContext,
                                            diagnostics);
    break;
  case HIRStatementKind::Block:
    if (!isEmptyHIRExpressionSlot(statement.target) ||
        !isEmptyHIRExpressionSlot(statement.value) || !statement.name.empty() ||
        hasHIRTypeShape(statement.declaredType) ||
        !statement.initializer.empty() || !statement.update.empty() ||
        !statement.updateTokens.empty() || !statement.elseBody.empty()) {
      reportHIRStatementShape(statement, statementContext,
                              "must contain only body statements",
                              diagnostics);
    }
    break;
  case HIRStatementKind::If:
    if (isEmptyHIRExpressionSlot(statement.value)) {
      reportHIRStatementShape(statement, statementContext,
                              "must have a condition expression", diagnostics);
    }
    if (!isEmptyHIRExpressionSlot(statement.target)) {
      reportHIRStatementShape(statement, statementContext,
                              "must not have an assignment target",
                              diagnostics);
    }
    if (!statement.name.empty() || hasHIRTypeShape(statement.declaredType)) {
      reportHIRStatementShape(statement, statementContext,
                              "must not declare a variable", diagnostics);
    }
    if (!statement.initializer.empty() || !statement.update.empty() ||
        !statement.updateTokens.empty()) {
      reportHIRStatementShape(statement, statementContext,
                              "must not contain loop header fields",
                              diagnostics);
    }
    break;
  case HIRStatementKind::For:
    if (!isEmptyHIRExpressionSlot(statement.target)) {
      reportHIRStatementShape(statement, statementContext,
                              "must not have an assignment target",
                              diagnostics);
    }
    if (!statement.name.empty() || hasHIRTypeShape(statement.declaredType)) {
      reportHIRStatementShape(statement, statementContext,
                              "must not declare a variable", diagnostics);
    }
    if (!statement.elseBody.empty()) {
      reportHIRStatementShape(statement, statementContext,
                              "must not contain else-body statements",
                              diagnostics);
    }
    if (statement.initializer.size() > 1) {
      reportHIRStatementShape(statement, statementContext,
                              "must have at most one initializer statement",
                              diagnostics);
    }
    for (const HIRStatement &initializer : statement.initializer) {
      if (!isHIRLoopHeaderStatementKind(initializer.kind)) {
        reportHIRStatementShape(initializer,
                                statementContext + " initializer",
                                "must be a declaration, assignment, "
                                "expression, or raw statement",
                                diagnostics);
      }
    }
    if (statement.update.size() > 1) {
      reportHIRStatementShape(statement, statementContext,
                              "must have at most one parsed update statement",
                              diagnostics);
    }
    for (const HIRStatement &update : statement.update) {
      if (!isHIRLoopHeaderStatementKind(update.kind)) {
        reportHIRStatementShape(update, statementContext + " update",
                                "must be a declaration, assignment, "
                                "expression, or raw statement",
                                diagnostics);
      }
    }
    break;
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
    if (!isEmptyHIRExpressionSlot(statement.target) ||
        !isEmptyHIRExpressionSlot(statement.value) || !statement.name.empty() ||
        hasHIRTypeShape(statement.declaredType) ||
        !statement.initializer.empty() || !statement.update.empty() ||
        !statement.updateTokens.empty() || !statement.body.empty() ||
        !statement.elseBody.empty()) {
      reportHIRStatementShape(statement, statementContext,
                              "must not contain parsed statement fields",
                              diagnostics);
    }
    break;
  case HIRStatementKind::Raw:
    if (statement.rawTokens.empty()) {
      reportHIRStatementShape(statement, statementContext,
                              "must preserve at least one raw token",
                              diagnostics);
    }
    if (!isEmptyHIRExpressionSlot(statement.target) ||
        !isEmptyHIRExpressionSlot(statement.value) || !statement.name.empty() ||
        hasHIRTypeShape(statement.declaredType) ||
        !statement.initializer.empty() || !statement.update.empty() ||
        !statement.updateTokens.empty() || !statement.body.empty() ||
        !statement.elseBody.empty()) {
      reportHIRStatementShape(statement, statementContext,
                              "must not contain parsed statement fields",
                              diagnostics);
    }
    break;
  }

  if (statement.kind != HIRStatementKind::Raw && !statement.rawTokens.empty()) {
    reportHIRStatementShape(statement, statementContext,
                            "must not preserve raw fallback tokens",
                            diagnostics);
  }
  validateHIRExpressionShape(statement.target, statementContext + " target",
                             diagnostics);
  validateHIRExpressionShape(statement.value, statementContext + " value",
                             diagnostics);
  for (const HIRStatement &initializer : statement.initializer) {
    validateHIRStatementShape(initializer, statementContext + " initializer",
                              diagnostics);
  }
  for (const HIRStatement &update : statement.update) {
    validateHIRStatementShape(update, statementContext + " update",
                              diagnostics);
  }
  for (const HIRStatement &child : statement.body) {
    validateHIRStatementShape(child, statementContext + " body", diagnostics);
  }
  for (const HIRStatement &child : statement.elseBody) {
    validateHIRStatementShape(child, statementContext + " else", diagnostics);
  }
}

void validateHIRFunctionExpressionShapes(const HIRFunction &function,
                                         const std::string &context,
                                         DiagnosticEngine &diagnostics) {
  const std::string functionName =
      function.name.empty() ? std::string("<unnamed>") : function.name;
  const std::string functionContext =
      context + " function '" + functionName + "'";
  for (const HIRStatement &statement : function.body) {
    validateHIRStatementShape(statement, functionContext, diagnostics);
  }
}

void reportHIRControlTransferPlacement(const HIRStatement &statement,
                                       const std::string &context,
                                       std::string message,
                                       DiagnosticEngine &diagnostics) {
  diagnostics.error("opt.hir-control-transfer-placement",
                    "HIR " + context + " " + statementKindName(statement.kind) +
                        " statement " + std::move(message),
                    hirStatementSourceLocation(statement));
}

void validateHIRControlTransferPlacement(const HIRStatement &statement,
                                         const std::string &context,
                                         std::string_view stage,
                                         std::size_t loopDepth,
                                         DiagnosticEngine &diagnostics) {
  const std::string statementContext =
      context + " " + statementKindName(statement.kind) + " statement";
  switch (statement.kind) {
  case HIRStatementKind::Break:
    if (loopDepth == 0) {
      reportHIRControlTransferPlacement(
          statement, context, "is only legal inside a loop body", diagnostics);
    }
    break;
  case HIRStatementKind::Continue:
    if (loopDepth == 0) {
      reportHIRControlTransferPlacement(
          statement, context, "is only legal inside a loop body", diagnostics);
    }
    break;
  case HIRStatementKind::Discard:
    if (stage != "fragment") {
      std::string message = "is only legal in fragment stage functions";
      if (stage.empty()) {
        message += "; top-level functions have no fragment stage context";
      } else {
        message += ", not stage '" + std::string(stage) + "'";
      }
      reportHIRControlTransferPlacement(statement, context, std::move(message),
                                        diagnostics);
    }
    break;
  default:
    break;
  }

  for (const HIRStatement &initializer : statement.initializer) {
    validateHIRControlTransferPlacement(
        initializer, statementContext + " initializer", stage, loopDepth,
        diagnostics);
  }
  for (const HIRStatement &update : statement.update) {
    validateHIRControlTransferPlacement(update, statementContext + " update",
                                        stage, loopDepth, diagnostics);
  }
  const std::size_t childLoopDepth =
      statement.kind == HIRStatementKind::For ? loopDepth + 1 : loopDepth;
  for (const HIRStatement &child : statement.body) {
    validateHIRControlTransferPlacement(child, statementContext + " body",
                                        stage, childLoopDepth, diagnostics);
  }
  for (const HIRStatement &child : statement.elseBody) {
    validateHIRControlTransferPlacement(child, statementContext + " else",
                                        stage, loopDepth, diagnostics);
  }
}

void validateHIRFunctionControlTransferPlacement(const HIRFunction &function,
                                                 const std::string &context,
                                                 std::string_view stage,
                                                 DiagnosticEngine &diagnostics) {
  const std::string functionName =
      function.name.empty() ? std::string("<unnamed>") : function.name;
  const std::string functionContext =
      context + " function '" + functionName + "'";
  for (const HIRStatement &statement : function.body) {
    validateHIRControlTransferPlacement(statement, functionContext, stage, 0,
                                        diagnostics);
  }
}

void validateHIRTopLevelExpressionShapes(const HIRModule &module,
                                         DiagnosticEngine &diagnostics) {
  for (const HIRConstant &constant : module.constants) {
    const std::string constantName =
        constant.name.empty() ? std::string("<unnamed>") : constant.name;
    validateHIRExpressionShape(constant.value,
                               "constant '" + constantName + "' value",
                               diagnostics);
  }

  for (const HIRFunction &function : module.functions) {
    validateHIRFunctionExpressionShapes(function, "top-level", diagnostics);
    validateHIRFunctionControlTransferPlacement(function, "top-level", "",
                                               diagnostics);
  }
}

void validateHIRFunctionNames(std::span<const HIRFunction> functions,
                              const std::string &scopeLabel,
                              DiagnosticEngine &diagnostics) {
  std::set<std::string> definedNames;
  for (const HIRFunction &function : functions) {
    if (function.name.empty()) {
      diagnostics.error("opt.hir-empty-function-name",
                        "HIR " + scopeLabel +
                            " contains a function without a name");
      continue;
    }
    if (hasHIRFunctionBody(function) &&
        !definedNames.insert(function.name).second) {
      diagnostics.error("opt.hir-duplicate-function",
                        "HIR " + scopeLabel +
                            " contains duplicate function definition '" +
                            function.name + "'");
    }
  }
}

struct HIRFunctionSignature {
  HIRType returnType;
  std::vector<HIRParameter> parameters;
};

using HIRFunctionSignatureMap =
    std::unordered_map<std::string, HIRFunctionSignature>;

HIRFunctionSignature makeHIRFunctionSignature(const HIRFunction &function) {
  HIRFunctionSignature signature;
  signature.returnType = function.returnType;
  signature.parameters = function.parameters;
  return signature;
}

SourceLocation hirFunctionSignatureSourceLocation(const HIRFunction &function) {
  if (hasHIRTypeShape(function.returnType)) {
    return function.returnType.location;
  }
  for (const HIRParameter &parameter : function.parameters) {
    if (hasHIRTypeShape(parameter.type)) {
      return parameter.type.location;
    }
  }
  return {};
}

void reportHIRFunctionShape(const HIRFunction &function,
                            const std::string &context, std::string message,
                            DiagnosticEngine &diagnostics) {
  diagnostics.error("opt.hir-function-shape",
                    "HIR " + context + " " + std::move(message),
                    hirFunctionSignatureSourceLocation(function));
}

bool hasCompleteHIRFunctionSignature(const HIRFunction &function) {
  if (function.name.empty() || function.returnType.name.empty()) {
    return false;
  }
  for (const HIRParameter &parameter : function.parameters) {
    if (parameter.type.name.empty()) {
      return false;
    }
  }
  return true;
}

bool sameHIRSignatureType(const HIRType &left, const HIRType &right) {
  return sameType(stripTypeQualifier(left), stripTypeQualifier(right));
}

bool sameHIRFunctionSignature(const HIRFunctionSignature &left,
                              const HIRFunctionSignature &right) {
  if (!sameHIRSignatureType(left.returnType, right.returnType) ||
      left.parameters.size() != right.parameters.size()) {
    return false;
  }
  for (std::size_t index = 0; index < left.parameters.size(); ++index) {
    if (!sameHIRSignatureType(left.parameters[index].type,
                              right.parameters[index].type)) {
      return false;
    }
  }
  return true;
}

std::string formatHIRFunctionSignature(const HIRFunctionSignature &signature) {
  std::ostringstream stream;
  stream << formatType(signature.returnType) << "(";
  for (std::size_t index = 0; index < signature.parameters.size(); ++index) {
    if (index != 0) {
      stream << ", ";
    }
    stream << formatType(signature.parameters[index].type);
  }
  stream << ")";
  return stream.str();
}

void validateHIRFunctionSignatureConsistency(
    std::span<const HIRFunction> functions, const std::string &scopeLabel,
    DiagnosticEngine &diagnostics) {
  HIRFunctionSignatureMap signatures;
  for (const HIRFunction &function : functions) {
    if (!hasCompleteHIRFunctionSignature(function)) {
      continue;
    }
    HIRFunctionSignature signature = makeHIRFunctionSignature(function);
    const auto [existing, inserted] =
        signatures.emplace(function.name, signature);
    if (!inserted && !sameHIRFunctionSignature(existing->second, signature)) {
      diagnostics.error(
          "opt.hir-function-signature-mismatch",
          "HIR " + scopeLabel + " function '" + function.name +
              "' signature mismatch: previous signature '" +
              formatHIRFunctionSignature(existing->second) +
              "', current signature '" + formatHIRFunctionSignature(signature) +
              "'",
          hirFunctionSignatureSourceLocation(function));
    }
  }
}

void validateHIRFunctionSignatures(std::span<const HIRFunction> functions,
                                   const std::string &scopeLabel,
                                   DiagnosticEngine &diagnostics) {
  for (const HIRFunction &function : functions) {
    const std::string functionName =
        function.name.empty() ? std::string("<unnamed>") : function.name;
    const std::string functionContext =
        scopeLabel + " function '" + functionName + "'";
    if (function.returnType.name.empty()) {
      reportHIRFunctionShape(function, functionContext,
                             "must declare a non-empty return type",
                             diagnostics);
    }

    std::set<std::string> parameterNames;
    for (std::size_t index = 0; index < function.parameters.size(); ++index) {
      const HIRParameter &parameter = function.parameters[index];
      const std::string parameterLabel =
          parameter.name.empty() ? std::string("<unnamed>") : parameter.name;
      if (parameter.name.empty()) {
        reportHIRFunctionShape(function, functionContext,
                               "parameter " + std::to_string(index) +
                                   " must declare a variable name",
                               diagnostics);
      } else if (!parameterNames.insert(parameter.name).second) {
        reportHIRFunctionShape(function, functionContext,
                               "contains duplicate parameter '" +
                                   parameter.name + "'",
                               diagnostics);
      }
      if (parameter.type.name.empty()) {
        reportHIRFunctionShape(function, functionContext,
                               "parameter '" + parameterLabel +
                                   "' must declare a non-empty type",
                               diagnostics);
      }
    }
  }
  validateHIRFunctionSignatureConsistency(functions, scopeLabel, diagnostics);
}

SourceLocation hirStructSourceLocation(const HIRStruct &structure) {
  for (const HIRField &field : structure.fields) {
    if (hasHIRTypeShape(field.type)) {
      return field.type.location;
    }
  }
  return {};
}

void reportHIRStructShape(const HIRStruct &structure, std::string message,
                          DiagnosticEngine &diagnostics) {
  diagnostics.error("opt.hir-struct-shape",
                    "HIR struct declaration " + std::move(message),
                    hirStructSourceLocation(structure));
}

void validateHIRStructDeclarations(std::span<const HIRStruct> structs,
                                   DiagnosticEngine &diagnostics) {
  std::set<std::string> structNames;
  for (const HIRStruct &structure : structs) {
    const std::string structName =
        structure.name.empty() ? std::string("<unnamed>") : structure.name;
    if (structure.name.empty()) {
      reportHIRStructShape(structure, "must have a non-empty name",
                           diagnostics);
    } else if (!structNames.insert(structure.name).second) {
      reportHIRStructShape(structure,
                           "contains duplicate struct '" + structure.name +
                               "'",
                           diagnostics);
    }

    std::set<std::string> fieldNames;
    for (std::size_t index = 0; index < structure.fields.size(); ++index) {
      const HIRField &field = structure.fields[index];
      const std::string fieldLabel =
          field.name.empty() ? std::string("<unnamed>") : field.name;
      if (field.name.empty()) {
        reportHIRStructShape(
            structure,
            "struct '" + structName + "' field " + std::to_string(index) +
                " must declare a field name",
            diagnostics);
      } else if (!fieldNames.insert(field.name).second) {
        reportHIRStructShape(structure,
                             "struct '" + structName +
                                 "' contains duplicate field '" + field.name +
                                 "'",
                             diagnostics);
      }
      if (field.type.name.empty()) {
        reportHIRStructShape(structure,
                             "struct '" + structName + "' field '" +
                                 fieldLabel +
                                 "' must declare a non-empty type",
                             diagnostics);
      }
    }
  }
}

SourceLocation hirConstantSourceLocation(const HIRConstant &constant) {
  if (hasHIRTypeShape(constant.type)) {
    return constant.type.location;
  }
  if (!isEmptyHIRExpressionSlot(constant.value)) {
    return constant.value.location;
  }
  return {};
}

void reportHIRConstantShape(const HIRConstant &constant, std::string message,
                            DiagnosticEngine &diagnostics) {
  diagnostics.error("opt.hir-constant-shape",
                    "HIR constant declaration " + std::move(message),
                    hirConstantSourceLocation(constant));
}

void validateHIRConstants(std::span<const HIRConstant> constants,
                          DiagnosticEngine &diagnostics) {
  std::set<std::string> constantNames;
  for (const HIRConstant &constant : constants) {
    const std::string constantName =
        constant.name.empty() ? std::string("<unnamed>") : constant.name;
    if (constant.name.empty()) {
      reportHIRConstantShape(constant, "must have a non-empty name",
                             diagnostics);
    } else if (!constantNames.insert(constant.name).second) {
      reportHIRConstantShape(
          constant, "contains duplicate constant '" + constant.name + "'",
          diagnostics);
    }
    if (constant.type.name.empty()) {
      reportHIRConstantShape(constant,
                             "constant '" + constantName +
                                 "' must declare a non-empty type",
                             diagnostics);
    }
    if (isEmptyHIRExpressionSlot(constant.value)) {
      reportHIRConstantShape(constant,
                             "constant '" + constantName +
                                 "' must have a value expression",
                             diagnostics);
    }
  }
}

void validateHIRResources(const HIRStage &stage,
                          const std::string &stageLabel,
                          DiagnosticEngine &diagnostics) {
  std::set<std::string> names;
  std::set<std::pair<std::size_t, std::size_t>> bindings;
  for (const HIRResource &resource : stage.resources) {
    if (resource.name.empty()) {
      diagnostics.error("opt.hir-empty-resource-name",
                        "HIR stage '" + stageLabel +
                            "' contains a resource without a name");
    } else if (!names.insert(resource.name).second) {
      diagnostics.error("opt.hir-duplicate-resource",
                        "HIR stage '" + stageLabel +
                            "' contains duplicate resource '" + resource.name +
                            "'");
    }
    if (resource.type.name.empty()) {
      const std::string resourceName =
          resource.name.empty() ? std::string("<unnamed>") : resource.name;
      diagnostics.error("opt.hir-resource-shape",
                        "HIR stage '" + stageLabel + "' resource '" +
                            resourceName +
                            "' must declare a non-empty type",
                        resource.type.location);
    }

    if (resource.kind == HIRResourceKind::Shared) {
      continue;
    }
    const std::pair<std::size_t, std::size_t> bindingKey{resource.set,
                                                         resource.binding};
    if (!bindings.insert(bindingKey).second) {
      diagnostics.error("opt.hir-duplicate-resource-binding",
                        "HIR stage '" + stageLabel +
                            "' contains duplicate resource binding set " +
                            std::to_string(resource.set) + ", binding " +
                            std::to_string(resource.binding));
    }
  }
}

bool validateHIRModuleShape(HIRModule &module, DiagnosticEngine &diagnostics) {
  if (module.name.empty()) {
    diagnostics.error("opt.hir-empty-module-name",
                      "HIR module must have a name");
  }
  if (module.stages.empty()) {
    diagnostics.error("opt.hir-no-stages",
                      "HIR module must contain at least one stage");
  }

  validateHIRStructDeclarations(module.structs, diagnostics);
  validateHIRConstants(module.constants, diagnostics);
  validateHIRFunctionNames(module.functions, "top-level function list",
                           diagnostics);
  validateHIRFunctionSignatures(module.functions, "top-level function list",
                                diagnostics);
  validateHIRTopLevelExpressionShapes(module, diagnostics);

  for (const HIRStage &stage : module.stages) {
    const std::string stageLabel =
        stage.stage.empty() ? std::string("<unnamed>") : stage.stage;
    if (stage.stage.empty()) {
      diagnostics.error("opt.hir-empty-stage-name",
                        "HIR stage must have a name");
    } else if (!isValidHIRStageName(stage.stage)) {
      diagnostics.error("opt.hir-invalid-stage-name",
                        "HIR stage '" + stageLabel +
                            "' must be vertex, fragment, or compute");
    }
    if (stage.workgroupSize.has_value() && stage.stage != "compute") {
      diagnostics.error("opt.hir-workgroup-size-stage",
                        "HIR stage '" + stageLabel +
                            "' workgroup size is only legal for compute "
                            "stages");
    }
    if (stage.functions.empty()) {
      diagnostics.error("opt.hir-empty-stage",
                        "HIR stage '" + stageLabel +
                            "' must contain at least one function");
    }
    if (stage.entryPointName.empty()) {
      diagnostics.error("opt.hir-empty-entry-point",
                        "HIR stage '" + stageLabel +
                            "' must have an entry point");
      continue;
    }

    bool foundEntryPoint = false;
    for (const HIRFunction &function : stage.functions) {
      foundEntryPoint = foundEntryPoint ||
                        function.name == stage.entryPointName;
    }
    if (!foundEntryPoint) {
      diagnostics.error("opt.hir-missing-entry-point",
                        "HIR stage '" + stageLabel + "' entry point '" +
                            stage.entryPointName +
                            "' must match a stage function");
    }
    validateHIRFunctionNames(stage.functions,
                             "stage '" + stageLabel + "' function list",
                             diagnostics);
    validateHIRFunctionSignatures(
        stage.functions, "stage '" + stageLabel + "' function list",
        diagnostics);
    validateHIRResources(stage, stageLabel, diagnostics);
    for (const HIRFunction &function : stage.functions) {
      validateHIRFunctionExpressionShapes(function, "stage '" + stageLabel + "'",
                                          diagnostics);
      validateHIRFunctionControlTransferPlacement(
          function, "stage '" + stageLabel + "'", stage.stage, diagnostics);
    }
  }

  return false;
}

void validateHIRStatementBackendInput(const HIRStatement &statement,
                                      const std::string &context,
                                      DiagnosticEngine &diagnostics) {
  const std::string statementContext =
      context + " " + statementKindName(statement.kind) + " statement";
  if (statement.kind == HIRStatementKind::Raw) {
    diagnostics.error("opt.hir-raw-statement-backend-input",
                      "HIR " + statementContext +
                          " must be lowered to structured HIR before "
                          "backend/package input",
                      hirStatementSourceLocation(statement));
  }

  for (const HIRStatement &initializer : statement.initializer) {
    validateHIRStatementBackendInput(
        initializer, statementContext + " initializer", diagnostics);
  }
  for (const HIRStatement &update : statement.update) {
    validateHIRStatementBackendInput(update, statementContext + " update",
                                     diagnostics);
  }
  for (const HIRStatement &child : statement.body) {
    validateHIRStatementBackendInput(child, statementContext + " body",
                                     diagnostics);
  }
  for (const HIRStatement &child : statement.elseBody) {
    validateHIRStatementBackendInput(child, statementContext + " else",
                                     diagnostics);
  }
}

void validateHIRFunctionBackendInput(const HIRFunction &function,
                                     const std::string &context,
                                     DiagnosticEngine &diagnostics) {
  const std::string functionName =
      function.name.empty() ? std::string("<unnamed>") : function.name;
  const std::string functionContext =
      context + " function '" + functionName + "'";
  for (const HIRStatement &statement : function.body) {
    validateHIRStatementBackendInput(statement, functionContext, diagnostics);
  }
}

bool validateHIRBackendInput(HIRModule &module,
                             DiagnosticEngine &diagnostics) {
  for (const HIRFunction &function : module.functions) {
    validateHIRFunctionBackendInput(function, "top-level", diagnostics);
  }
  for (const HIRStage &stage : module.stages) {
    const std::string stageLabel =
        stage.stage.empty() ? std::string("<unnamed>") : stage.stage;
    for (const HIRFunction &function : stage.functions) {
      validateHIRFunctionBackendInput(function, "stage '" + stageLabel + "'",
                                      diagnostics);
    }
  }
  return false;
}

using HIRSymbolTable = std::unordered_map<std::string, HIRType>;
using HIRReadOnlySymbolSet = std::set<std::string>;
using HIRResourceHandleSymbolSet = std::set<std::string>;
using HIRIndexableResourceBaseSet = std::set<std::string>;

struct HIRTypedSymbolContext {
  std::set<std::string> structNames;
  std::unordered_map<std::string, HIRStruct> structs;
  HIRSymbolTable constants;
  HIRSymbolTable globalCBufferFields;
  HIRFunctionSignatureMap functionSignatures;
};

void addHIRFunctionSignatures(HIRFunctionSignatureMap &signatures,
                              const std::vector<HIRFunction> &functions) {
  for (const HIRFunction &function : functions) {
    if (!function.name.empty()) {
      signatures[function.name] = makeHIRFunctionSignature(function);
    }
  }
}

std::optional<HIRType>
hirExpressionEffectiveType(const HIRExpression &expression,
                           const HIRSymbolTable &symbols);

void reportHIRExpressionResultTypeMismatch(
    const HIRExpression &expression, const HIRType &expected,
    const std::string &context, std::string diagnosticCode,
    const HIRTypedSymbolContext &typedContext, DiagnosticEngine &diagnostics);

void reportHIRKnownType(const HIRType &type, const std::string &context,
                        const HIRTypedSymbolContext &typedContext,
                        DiagnosticEngine &diagnostics) {
  if (type.name.empty() || isKnownType(type, typedContext.structNames)) {
    return;
  }
  if (!type.location.file.empty()) {
    return;
  }
  diagnostics.error("opt.hir-unknown-type",
                    "HIR " + context + " uses unknown type '" +
                        formatType(type) + "'",
                    type.location);
}

bool isSourceBackedUnknownHIRType(const HIRType &type,
                                  const HIRTypedSymbolContext &typedContext) {
  return !type.name.empty() && !type.location.file.empty() &&
         !isKnownType(type, typedContext.structNames);
}

bool isManualHIRTextureCompare(std::string_view value) {
  return value == "textureCompareLodManual" ||
         value == "textureCompareLodManualOffset" ||
         value == "textureCompareLodManualGather2x2" ||
         value == "textureCompareLodManualKernel" ||
         value == "textureCompareLodManualKernel4" ||
         value == "textureCompareLodManualKernel8";
}

bool isExplicitHIRTextureSampleLod(std::string_view value) {
  return value == "textureLod";
}

bool isExplicitHIRTextureCompareLod(std::string_view value) {
  return value == "textureCompareLod";
}

bool isHIRScalarNumericType(const HIRType &type) {
  const std::string name = baseTypeName(type);
  return !type.arraySize.has_value() &&
         (isFloatLike(name) || name == "int" || name == "uint");
}

HIRType hirTextureSampleResultType(const HIRType &textureType,
                                   SourceLocation location = {}) {
  const std::string name = baseTypeName(textureType);
  if (!isTextureResourceType(name)) {
    return {};
  }
  if (isComparisonTextureResourceType(name)) {
    return HIRType{"float", std::nullopt, std::move(location)};
  }
  if (name.rfind("isampler", 0) == 0) {
    return HIRType{"ivec4", std::nullopt, std::move(location)};
  }
  if (name.rfind("usampler", 0) == 0) {
    return HIRType{"uvec4", std::nullopt, std::move(location)};
  }
  return HIRType{"vec4", std::nullopt, std::move(location)};
}

std::size_t expectedHIRTextureCoordinateComponents(const HIRType &textureType) {
  const std::string name = baseTypeName(textureType);
  if (name == "sampler2D" || name == "sampler2DShadow" ||
      name == "isampler2D" || name == "usampler2D" || name == "texture2D") {
    return 2;
  }
  if (name == "sampler2DArray" || name == "sampler2DArrayShadow" ||
      name == "isampler2DArray" || name == "usampler2DArray" ||
      name == "texture2DArray") {
    return 3;
  }
  if (name == "sampler3D" || name == "isampler3D" ||
      name == "usampler3D" || name == "texture3D" ||
      name == "samplerCube" || name == "samplerCubeShadow" ||
      name == "isamplerCube" || name == "usamplerCube" ||
      name == "textureCube") {
    return 3;
  }
  if (name == "samplerCubeArray" || name == "samplerCubeArrayShadow" ||
      name == "isamplerCubeArray" || name == "usamplerCubeArray" ||
      name == "textureCubeArray") {
    return 4;
  }
  return 0;
}

std::size_t hirTextureSampleCoordinateIndex(std::size_t argumentCount,
                                            bool explicitLod) {
  const bool hasExplicitSampler = explicitLod ? argumentCount == 4
                                              : argumentCount == 3;
  return hasExplicitSampler ? 2 : 1;
}

std::optional<std::size_t>
hirTextureSampleLodIndex(std::size_t argumentCount, bool explicitLod) {
  if (!explicitLod) {
    return std::nullopt;
  }
  return argumentCount == 4 ? std::optional<std::size_t>{3}
                            : std::optional<std::size_t>{2};
}

void reportHIRTextureExpressionType(const HIRExpression &expression,
                                    const std::string &context,
                                    std::string message,
                                    DiagnosticEngine &diagnostics) {
  diagnostics.error("opt.hir-texture-expression-type",
                    "HIR " + context + " " +
                        expressionKindName(expression.kind) + " expression " +
                        std::move(message),
                    expression.location);
}

void validateHIRTextureCoordinateType(
    const HIRExpression &expression, const HIRType &textureType,
    const HIRExpression &coordinate, const std::string &operation,
    const std::string &context, const HIRSymbolTable &symbols,
    DiagnosticEngine &diagnostics) {
  const std::size_t expectedComponents =
      expectedHIRTextureCoordinateComponents(textureType);
  const std::optional<HIRType> coordinateType =
      hirExpressionEffectiveType(coordinate, symbols);
  if (expectedComponents == 0 || !coordinateType.has_value()) {
    return;
  }
  const std::optional<std::size_t> actualComponents =
      vectorWidthFromName(baseTypeName(*coordinateType));
  if (!actualComponents.has_value() || *actualComponents != expectedComponents) {
    reportHIRTextureExpressionType(
        expression, context,
        operation + " coordinates for '" + formatType(textureType) +
            "' must have " + std::to_string(expectedComponents) +
            " component(s), got '" + formatType(*coordinateType) + "'",
        diagnostics);
  }
}

void validateHIRTextureSampleTypedExpression(
    const HIRExpression &expression, const std::string &context,
    const HIRSymbolTable &symbols, const HIRTypedSymbolContext &typedContext,
    DiagnosticEngine &diagnostics) {
  if (expression.kind != HIRExpressionKind::TextureSample ||
      (expression.value != "texture" && expression.value != "sample" &&
       expression.value != "textureLod")) {
    return;
  }
  const bool explicitLod = isExplicitHIRTextureSampleLod(expression.value);
  if (explicitLod) {
    if (expression.children.size() != 3 && expression.children.size() != 4) {
      return;
    }
  } else if (expression.children.size() != 2 &&
             expression.children.size() != 3) {
    return;
  }

  const std::optional<HIRType> textureType =
      hirExpressionEffectiveType(expression.children.front(), symbols);
  bool valid = true;
  if (textureType.has_value() &&
      !isTextureResourceType(baseTypeName(*textureType))) {
    reportHIRTextureExpressionType(
        expression, context,
        expression.value + " first operand must be a texture resource, got '" +
            formatType(*textureType) + "'",
        diagnostics);
    valid = false;
  }

  const bool hasExplicitSampler =
      explicitLod ? expression.children.size() == 4
                  : expression.children.size() == 3;
  if (hasExplicitSampler) {
    const std::optional<HIRType> samplerType =
        hirExpressionEffectiveType(expression.children[1], symbols);
    if (samplerType.has_value() &&
        !isRawSamplerResourceType(baseTypeName(*samplerType))) {
      reportHIRTextureExpressionType(
          expression, context,
          expression.value + " sampler operand must be a raw sampler, got '" +
              formatType(*samplerType) + "'",
          diagnostics);
      valid = false;
    }
  }

  if (textureType.has_value() &&
      isTextureResourceType(baseTypeName(*textureType))) {
    const std::size_t coordinateIndex =
        hirTextureSampleCoordinateIndex(expression.children.size(), explicitLod);
    validateHIRTextureCoordinateType(expression, *textureType,
                                     expression.children[coordinateIndex],
                                     expression.value, context, symbols,
                                     diagnostics);
  }

  const std::optional<std::size_t> lodIndex =
      hirTextureSampleLodIndex(expression.children.size(), explicitLod);
  if (lodIndex.has_value()) {
    const std::optional<HIRType> lodType =
        hirExpressionEffectiveType(expression.children[*lodIndex], symbols);
    if (lodType.has_value() && !isHIRScalarNumericType(*lodType)) {
      reportHIRTextureExpressionType(
          expression, context,
          expression.value + " lod operand must be scalar numeric, got '" +
              formatType(*lodType) + "'",
          diagnostics);
      valid = false;
    }
  }

  if (valid && textureType.has_value() &&
      isTextureResourceType(baseTypeName(*textureType))) {
    reportHIRExpressionResultTypeMismatch(
        expression,
        hirTextureSampleResultType(*textureType, expression.location), context,
        "opt.hir-texture-expression-type", typedContext, diagnostics);
  }
}

void validateHIRTextureCompareTypedExpression(
    const HIRExpression &expression, const std::string &context,
    const HIRSymbolTable &symbols, const HIRTypedSymbolContext &typedContext,
    DiagnosticEngine &diagnostics) {
  if (expression.kind != HIRExpressionKind::TextureCompare ||
      (expression.value != "textureCompare" &&
       expression.value != "textureCompareLod")) {
    return;
  }
  const bool explicitLod = isExplicitHIRTextureCompareLod(expression.value);
  const std::size_t expectedChildCount = explicitLod ? 5 : 4;
  if (expression.children.size() != expectedChildCount) {
    return;
  }

  const std::optional<HIRType> textureType =
      hirExpressionEffectiveType(expression.children.front(), symbols);
  bool valid = true;
  if (textureType.has_value() &&
      !isComparisonTextureResourceType(baseTypeName(*textureType))) {
    reportHIRTextureExpressionType(
        expression, context,
        expression.value +
            " first operand must be a comparison texture, got '" +
            formatType(*textureType) + "'",
        diagnostics);
    valid = false;
  }

  const std::optional<HIRType> samplerType =
      hirExpressionEffectiveType(expression.children[1], symbols);
  if (samplerType.has_value() &&
      !isSamplerResourceType(baseTypeName(*samplerType))) {
    reportHIRTextureExpressionType(
        expression, context,
        expression.value + " sampler operand must be a sampler or "
            "comparison_sampler, got '" +
            formatType(*samplerType) + "'",
        diagnostics);
    valid = false;
  }

  if (textureType.has_value() &&
      isComparisonTextureResourceType(baseTypeName(*textureType))) {
    validateHIRTextureCoordinateType(expression, *textureType,
                                     expression.children[2], expression.value,
                                     context, symbols, diagnostics);
  }

  const std::optional<HIRType> depthType =
      hirExpressionEffectiveType(expression.children[3], symbols);
  if (depthType.has_value() && !isHIRScalarNumericType(*depthType)) {
    reportHIRTextureExpressionType(
        expression, context,
        expression.value + " depth operand must be scalar numeric, got '" +
            formatType(*depthType) + "'",
        diagnostics);
    valid = false;
  }

  if (explicitLod) {
    const std::optional<HIRType> lodType =
        hirExpressionEffectiveType(expression.children[4], symbols);
    if (lodType.has_value() && !isHIRScalarNumericType(*lodType)) {
      reportHIRTextureExpressionType(
          expression, context,
          expression.value + " lod operand must be scalar numeric, got '" +
              formatType(*lodType) + "'",
          diagnostics);
      valid = false;
    }
  }

  if (valid) {
    reportHIRExpressionResultTypeMismatch(
        expression, HIRType{"float", std::nullopt, expression.location},
        context, "opt.hir-texture-expression-type", typedContext,
        diagnostics);
  }
}

std::optional<std::size_t>
manualHIRTextureCompareTapCount(std::string_view value) {
  if (value == "textureCompareLodManualKernel4") {
    return 4;
  }
  if (value == "textureCompareLodManualKernel8") {
    return 8;
  }
  return std::nullopt;
}

std::size_t expectedManualHIRTextureCompareOperandCount(
    std::string_view value) {
  if (value == "textureCompareLodManualOffset" ||
      value == "textureCompareLodManualKernel") {
    return 7;
  }
  if (const std::optional<std::size_t> tapCount =
          manualHIRTextureCompareTapCount(value)) {
    return 6 + *tapCount * 2;
  }
  return 6;
}

bool isManualHIRTextureCompareOpOperand(const HIRExpression &parent,
                                        std::size_t childIndex) {
  return parent.kind == HIRExpressionKind::TextureCompareLodManual &&
         isManualHIRTextureCompare(parent.value) && childIndex == 5 &&
         parent.children.size() ==
             expectedManualHIRTextureCompareOperandCount(parent.value);
}

std::optional<HIRType> hirExpressionEffectiveType(
    const HIRExpression &expression, const HIRSymbolTable &symbols) {
  if (!expression.type.name.empty()) {
    return expression.type;
  }
  if (expression.kind == HIRExpressionKind::Identifier) {
    const auto symbol = symbols.find(expression.value);
    if (symbol != symbols.end()) {
      return symbol->second;
    }
  }
  if (expression.kind == HIRExpressionKind::Group &&
      expression.children.size() == 1) {
    return hirExpressionEffectiveType(expression.children.front(), symbols);
  }
  return std::nullopt;
}

std::vector<HIRType>
hirExpressionEffectiveTypes(const std::vector<HIRExpression> &expressions,
                            const HIRSymbolTable &symbols) {
  std::vector<HIRType> types;
  types.reserve(expressions.size());
  for (const HIRExpression &expression : expressions) {
    types.push_back(hirExpressionEffectiveType(expression, symbols)
                        .value_or(HIRType{}));
  }
  return types;
}

void validateHIRTypeCompatibility(const HIRType &expected,
                                  const HIRType &actual,
                                  const std::string &context,
                                  const SourceLocation &location,
                                  std::string diagnosticCode,
                                  const HIRTypedSymbolContext &typedContext,
                                  DiagnosticEngine &diagnostics) {
  if (isSourceBackedUnknownHIRType(expected, typedContext) ||
      isSourceBackedUnknownHIRType(actual, typedContext)) {
    return;
  }
  if (!shouldDiagnoseTypeMismatch(expected, actual)) {
    return;
  }
  diagnostics.error(std::move(diagnosticCode),
                    "HIR " + context + " expects type '" +
                        formatType(expected) + "' but got '" +
                        formatType(actual) + "'",
                    location);
}

bool shouldDiagnoseExactHIRTypeMismatch(
    const HIRType &expected, const HIRType &actual,
    const HIRTypedSymbolContext &typedContext) {
  if (expected.name.empty() || actual.name.empty() ||
      sameType(expected, actual)) {
    return false;
  }
  if (isSourceBackedUnknownHIRType(expected, typedContext) ||
      isSourceBackedUnknownHIRType(actual, typedContext)) {
    return false;
  }
  return isKnownType(expected, typedContext.structNames) &&
         isKnownType(actual, typedContext.structNames);
}

void reportHIRExpressionResultTypeMismatch(
    const HIRExpression &expression, const HIRType &expected,
    const std::string &context, std::string diagnosticCode,
    const HIRTypedSymbolContext &typedContext, DiagnosticEngine &diagnostics) {
  if (!shouldDiagnoseExactHIRTypeMismatch(expected, expression.type,
                                         typedContext)) {
    return;
  }
  diagnostics.error(std::move(diagnosticCode),
                    "HIR " + context + " " +
                        expressionKindName(expression.kind) +
                        " expression has result type '" +
                        formatType(expression.type) + "' but expects '" +
                        formatType(expected) + "'",
                    expression.location);
}

std::optional<HIRType> hirKnownCallResultType(
    const HIRExpression &expression, const HIRSymbolTable &symbols) {
  if (expression.kind != HIRExpressionKind::Call) {
    return std::nullopt;
  }
  return inferHIRIntrinsicResultType(
      expression.value, hirExpressionEffectiveTypes(expression.children, symbols),
      expression.location);
}

void validateHIRIntrinsicArity(const HIRExpression &expression,
                               const std::string &context,
                               DiagnosticEngine &diagnostics) {
  if (expression.kind != HIRExpressionKind::Call) {
    return;
  }
  const auto signatures = lookupHIRIntrinsicSignatures(expression.value);
  if (signatures.empty() ||
      acceptsHIRIntrinsicArity(signatures, expression.children.size())) {
    return;
  }
  diagnostics.error("opt.hir-intrinsic-arity",
                    "HIR " + context + " call '" + expression.value +
                        "' expects " +
                        formatHIRIntrinsicArityExpectation(signatures) +
                        ", got " +
                        std::to_string(expression.children.size()),
                    expression.location);
}

void validateHIRIntrinsicArgumentTypes(
    const HIRExpression &expression, const std::string &context,
    const HIRSymbolTable &symbols, const HIRTypedSymbolContext &typedContext,
    DiagnosticEngine &diagnostics) {
  if (expression.kind != HIRExpressionKind::Call) {
    return;
  }
  const auto signatures = lookupHIRIntrinsicSignatures(expression.value);
  if (signatures.empty() ||
      !acceptsHIRIntrinsicArity(signatures, expression.children.size())) {
    return;
  }
  const std::optional<HIRIntrinsicArgumentTypeIssue> issue =
      findHIRIntrinsicArgumentTypeIssue(
          signatures, hirExpressionEffectiveTypes(expression.children, symbols));
  if (!issue.has_value() ||
      isSourceBackedUnknownHIRType(issue->actualType, typedContext)) {
    return;
  }
  const SourceLocation location =
      issue->argumentIndex < expression.children.size()
          ? expression.children[issue->argumentIndex].location
          : expression.location;
  diagnostics.error("opt.hir-intrinsic-argument-type",
                    "HIR " + context + " call '" + expression.value +
                        "' argument " + std::to_string(issue->argumentIndex) +
                        " expects " + issue->expectation + ", got '" +
                        formatType(issue->actualType) + "'",
                    location);
}

std::string formatHIRFunctionArgumentCount(std::size_t count) {
  return count == 1 ? "exactly 1 argument"
                    : "exactly " + std::to_string(count) + " arguments";
}

bool shouldValidateHIRUserFunctionCall(
    const HIRExpression &expression,
    const HIRTypedSymbolContext &typedContext) {
  if (expression.kind != HIRExpressionKind::Call || expression.value.empty()) {
    return false;
  }
  if (expression.value.size() >= 2 && expression.value[0] == '_' &&
      expression.value[1] == '_') {
    return false;
  }
  if (!lookupHIRIntrinsicSignatures(expression.value).empty() ||
      lookupHIRCallBuiltinEffect(expression.value).has_value()) {
    return false;
  }
  const HIRType calleeType{expression.value, std::nullopt,
                           expression.location};
  return !isKnownType(calleeType, typedContext.structNames);
}

void validateHIRUserFunctionCall(
    const HIRExpression &expression, const std::string &context,
    const HIRSymbolTable &symbols, const HIRTypedSymbolContext &typedContext,
    DiagnosticEngine &diagnostics) {
  if (!shouldValidateHIRUserFunctionCall(expression, typedContext)) {
    return;
  }
  const auto function = typedContext.functionSignatures.find(expression.value);
  if (function == typedContext.functionSignatures.end()) {
    if (expression.type.name.empty()) {
      diagnostics.error(
          "opt.hir-unresolved-function-call",
          "HIR " + context + " call '" + expression.value +
              "' does not resolve to a declared function or supported "
              "intrinsic",
          expression.location);
    }
    return;
  }

  const HIRFunctionSignature &signature = function->second;
  if (expression.children.size() != signature.parameters.size()) {
    diagnostics.error(
        "opt.hir-function-call-arity",
        "HIR " + context + " call '" + expression.value + "' expects " +
            formatHIRFunctionArgumentCount(signature.parameters.size()) +
            ", got " + std::to_string(expression.children.size()),
        expression.location);
    return;
  }

  for (std::size_t index = 0; index < signature.parameters.size(); ++index) {
    const HIRType &expected = signature.parameters[index].type;
    const std::optional<HIRType> actual =
        hirExpressionEffectiveType(expression.children[index], symbols);
    const HIRType normalizedExpected = stripTypeQualifier(expected);
    const HIRType normalizedActual =
        actual.has_value() ? stripTypeQualifier(*actual) : HIRType{};
    if (!actual.has_value() ||
        !shouldDiagnoseExactHIRTypeMismatch(normalizedExpected,
                                           normalizedActual, typedContext)) {
      continue;
    }
    diagnostics.error(
        "opt.hir-function-call-argument-type",
        "HIR " + context + " call '" + expression.value + "' argument " +
            std::to_string(index) + " expects '" + formatType(expected) +
            "', got '" + formatType(*actual) + "'",
        expression.children[index].location);
  }

  reportHIRExpressionResultTypeMismatch(
      expression, signature.returnType, context,
      "opt.hir-function-call-type", typedContext, diagnostics);
}

bool isHIRAtomicReadModifyWriteCallName(std::string_view name) {
  return isHIRAtomicIntegerReadModifyWriteIntrinsic(name);
}

bool isHIRAtomicReadModifyWriteCall(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::Call &&
         isHIRAtomicReadModifyWriteCallName(expression.value);
}

std::string hirAtomicReadModifyWriteDiagnosticStem(std::string_view name) {
  return std::string(hirAtomicIntegerReadModifyWriteDiagnosticStem(name));
}

const HIRExpression &unwrapHIRTransparentTargetExpression(
    const HIRExpression &expression) {
  const HIRExpression *current = &expression;
  while ((current->kind == HIRExpressionKind::Group ||
          current->kind == HIRExpressionKind::NonUniform) &&
         current->children.size() == 1) {
    current = &current->children.front();
  }
  return *current;
}

bool isHIRAtomicReadModifyWriteAssignableTarget(
    const HIRExpression &expression) {
  const HIRExpression &target = unwrapHIRTransparentTargetExpression(expression);
  return target.kind == HIRExpressionKind::Identifier ||
         target.kind == HIRExpressionKind::IndexAccess ||
         target.kind == HIRExpressionKind::MemberAccess;
}

bool isHIRAssignableTargetExpression(const HIRExpression &expression) {
  const HIRExpression &target = unwrapHIRTransparentTargetExpression(expression);
  switch (target.kind) {
  case HIRExpressionKind::Identifier:
    return true;
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::MemberAccess:
    return !target.children.empty() &&
           isHIRAssignableTargetExpression(target.children.front());
  default:
    return false;
  }
}

const HIRExpression &
hirAssignmentTargetDiagnosticExpression(const HIRExpression &expression) {
  const HIRExpression &target = unwrapHIRTransparentTargetExpression(expression);
  if ((target.kind == HIRExpressionKind::IndexAccess ||
       target.kind == HIRExpressionKind::MemberAccess) &&
      !target.children.empty() &&
      !isHIRAssignableTargetExpression(target.children.front())) {
    return hirAssignmentTargetDiagnosticExpression(target.children.front());
  }
  return target;
}

bool hirVectorSwizzleHasDuplicateComponents(const HIRType &baseType,
                                            std::string_view member) {
  const std::string baseName = baseTypeName(baseType);
  const std::optional<std::size_t> width = vectorWidthFromName(baseName);
  if (!isVectorType(baseName) || !width.has_value() || member.empty() ||
      member.size() > 4) {
    return false;
  }

  static constexpr std::string_view sets[] = {"xyzw", "rgba", "stpq"};
  const std::string_view *selectedSet = nullptr;
  for (const std::string_view &set : sets) {
    if (set.find(member.front()) != std::string_view::npos) {
      selectedSet = &set;
      break;
    }
  }
  if (selectedSet == nullptr) {
    return false;
  }

  std::array<bool, 4> seen{};
  for (const char component : member) {
    const std::size_t index = selectedSet->find(component);
    if (index == std::string_view::npos || index >= *width) {
      return false;
    }
    if (seen[index]) {
      return true;
    }
    seen[index] = true;
  }
  return false;
}

const HIRExpression *hirDuplicateSwizzleAssignmentTargetExpression(
    const HIRExpression &expression, const HIRSymbolTable &symbols) {
  const HIRExpression &target = unwrapHIRTransparentTargetExpression(expression);
  if ((target.kind == HIRExpressionKind::IndexAccess ||
       target.kind == HIRExpressionKind::MemberAccess) &&
      !target.children.empty()) {
    if (target.kind == HIRExpressionKind::MemberAccess) {
      const HIRExpression &base = target.children.front();
      const std::optional<HIRType> baseType =
          hirExpressionEffectiveType(base, symbols);
      if (baseType.has_value() &&
          hirVectorSwizzleHasDuplicateComponents(*baseType, target.value)) {
        return &target;
      }
    }
    return hirDuplicateSwizzleAssignmentTargetExpression(
        target.children.front(), symbols);
  }
  return nullptr;
}

const HIRExpression *
hirAssignmentTargetRootIdentifier(const HIRExpression &expression) {
  const HIRExpression &target = unwrapHIRTransparentTargetExpression(expression);
  if (target.kind == HIRExpressionKind::Identifier) {
    return &target;
  }
  if ((target.kind == HIRExpressionKind::IndexAccess ||
       target.kind == HIRExpressionKind::MemberAccess) &&
      !target.children.empty()) {
    return hirAssignmentTargetRootIdentifier(target.children.front());
  }
  return nullptr;
}

const HIRExpression *
hirAssignmentTargetDirectIdentifier(const HIRExpression &expression) {
  const HIRExpression &target = unwrapHIRTransparentTargetExpression(expression);
  return target.kind == HIRExpressionKind::Identifier ? &target : nullptr;
}

const HIRExpression *
hirAggregateAssignmentTargetExpression(const HIRExpression &expression) {
  const HIRExpression &target = unwrapHIRTransparentTargetExpression(expression);
  if (!isHIRAssignableTargetExpression(target) || !isArrayType(target.type)) {
    return nullptr;
  }
  const HIRResourceKind kind = resourceKindFromName(target.type.name);
  if (kind != HIRResourceKind::Value && kind != HIRResourceKind::Shared) {
    return nullptr;
  }
  return &target;
}

std::string hirAssignmentTargetDescription(const HIRExpression &target) {
  switch (target.kind) {
  case HIRExpressionKind::Identifier:
    return "'" + target.value + "'";
  case HIRExpressionKind::MemberAccess:
    return "member '" + target.value + "'";
  case HIRExpressionKind::IndexAccess:
    return "indexed expression";
  default:
    return "'" + std::string(expressionKindName(target.kind)) + "' expression";
  }
}

void validateHIRAtomicReadModifyWriteLValue(
    const HIRExpression &expression, const std::string &context,
    const HIRSymbolTable &symbols, DiagnosticEngine &diagnostics) {
  if (!isHIRAtomicReadModifyWriteCall(expression) ||
      expression.children.size() != 2) {
    return;
  }
  const HIRExpression &target = expression.children.front();
  const std::optional<HIRType> targetType =
      hirExpressionEffectiveType(target, symbols);
  if (!targetType.has_value() ||
      (!isAtomicIntegerScalarType(*targetType) &&
       !isIntegerScalarType(*targetType))) {
    return;
  }
  if (!isHIRAtomicReadModifyWriteAssignableTarget(target)) {
    diagnostics.error(
        "opt.hir-" + hirAtomicReadModifyWriteDiagnosticStem(expression.value) +
            "-target-lvalue",
        "HIR " + context +
            " " + expression.value +
            " target must be an assignable scalar integer or "
            "atomic integer storage location",
        target.location);
  }
}

void validateHIRAtomicReadModifyWriteValueUseInExpression(
    const HIRExpression &expression, bool allowRootAtomicReadModifyWrite,
    const std::string &context, DiagnosticEngine &diagnostics) {
  if (expression.kind == HIRExpressionKind::Empty) {
    return;
  }
  if (isHIRAtomicReadModifyWriteCall(expression) &&
      !allowRootAtomicReadModifyWrite) {
    diagnostics.error(
        "opt.hir-" + hirAtomicReadModifyWriteDiagnosticStem(expression.value) +
            "-value-context",
        "HIR " + context +
            " " + expression.value +
            " returned old value is supported only as the whole "
            "declaration initializer or assignment RHS expression",
        expression.location);
  }
  for (std::size_t index = 0; index < expression.children.size(); ++index) {
    validateHIRAtomicReadModifyWriteValueUseInExpression(
        expression.children[index], false,
        context + " child " + std::to_string(index), diagnostics);
  }
}

void validateHIRCallCalleeType(const HIRExpression &expression,
                               const std::string &context,
                               const HIRTypedSymbolContext &typedContext,
                               DiagnosticEngine &diagnostics) {
  if (expression.kind != HIRExpressionKind::Call || expression.value.empty()) {
    return;
  }
  const HIRType calleeType{expression.value, std::nullopt,
                           expression.location};
  if (!isKnownType(calleeType, typedContext.structNames)) {
    return;
  }
  diagnostics.error("opt.hir-call-callee-type",
                    "HIR " + context + " call '" + expression.value +
                        "' names a type; type construction must use a "
                        "constructor expression",
                    expression.location);
}

bool isHIRNumericVectorTypeName(std::string_view name) {
  return name == "vec2" || name == "vec3" || name == "vec4" ||
         name == "ivec2" || name == "ivec3" || name == "ivec4" ||
         name == "uvec2" || name == "uvec3" || name == "uvec4";
}

bool isHIRNumericAggregateType(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return false;
  }
  const std::string name = baseTypeName(type);
  return isHIRNumericVectorTypeName(name) || isMatrixType(name);
}

bool isHIRArithmeticOperandType(const HIRType &type) {
  return isHIRScalarNumericType(type) || isHIRNumericAggregateType(type);
}

bool isHIRArithmeticBinaryOperator(std::string_view op) {
  return op == "+" || op == "-" || op == "*" || op == "/" || op == "%";
}

bool isHIRRelationalBinaryOperator(std::string_view op) {
  return op == "<" || op == "<=" || op == ">" || op == ">=";
}

bool isHIREqualityBinaryOperator(std::string_view op) {
  return op == "==" || op == "!=";
}

bool isHIREqualityOperandPair(const HIRType &left, const HIRType &right) {
  return (isScalarBoolType(left) && isScalarBoolType(right)) ||
         (isHIRScalarNumericType(left) && isHIRScalarNumericType(right));
}

bool isHIRSelectBranchOperandType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value() || isVoidType(type)) {
    return false;
  }
  const std::string name = baseTypeName(type);
  return isScalarBoolType(type) || isHIRScalarNumericType(type) ||
         isHIRNumericVectorTypeName(name) || isMatrixType(name);
}

bool isHIRSelectBranchOperandPair(const HIRType &left, const HIRType &right) {
  if (!isHIRSelectBranchOperandType(left) ||
      !isHIRSelectBranchOperandType(right)) {
    return false;
  }
  return sameType(left, right) ||
         (isHIRScalarNumericType(left) && isHIRScalarNumericType(right));
}

bool isHIRScalarNumericConstructorType(const HIRType &type) {
  return isHIRScalarNumericType(type);
}

bool isHIRConstructorComponentConvertible(const HIRType &targetComponentType,
                                          const HIRType &sourceComponentType) {
  const HIRType target = stripTypeQualifier(targetComponentType);
  const HIRType source = stripTypeQualifier(sourceComponentType);
  if (sameType(target, source)) {
    return true;
  }
  if (isScalarBoolType(target) || isScalarBoolType(source)) {
    return false;
  }
  return isHIRScalarNumericType(target) && isHIRScalarNumericType(source);
}

std::optional<HIRType> hirScalarOrVectorComponentType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return std::nullopt;
  }
  const std::string typeBase = baseTypeName(type);
  if (isVectorType(typeBase)) {
    return scalarTypeForVector(typeBase);
  }
  if (isHIRScalarNumericType(type) || isScalarBoolType(type)) {
    return stripTypeQualifier(type);
  }
  return std::nullopt;
}

std::optional<std::size_t> hirConstructorConstituentWidth(
    const HIRExpression &operand, const HIRType &operandType,
    const HIRType &componentType, std::string_view constructorName,
    std::string_view diagnosticCode, std::string_view constructorKind,
    const std::string &context, DiagnosticEngine &diagnostics, bool &valid) {
  const std::optional<HIRType> operandComponentType =
      hirScalarOrVectorComponentType(operandType);
  if (!operandComponentType.has_value()) {
    if (operandType.name.empty()) {
      return std::nullopt;
    }
    diagnostics.error(
        std::string(diagnosticCode),
        "HIR " + context + " " + std::string(constructorKind) +
            " constructor '" + std::string(constructorName) +
            "' requires scalar or vector operands convertible to component "
            "type '" +
            formatType(componentType) + "', got '" + formatType(operandType) +
            "'",
        operand.location);
    valid = false;
    return std::size_t{0};
  }
  if (!isHIRConstructorComponentConvertible(componentType,
                                            *operandComponentType)) {
    diagnostics.error(
        std::string(diagnosticCode),
        "HIR " + context + " " + std::string(constructorKind) +
            " constructor '" + std::string(constructorName) +
            "' requires scalar or vector operands convertible to component "
            "type '" +
            formatType(componentType) + "', got '" + formatType(operandType) +
            "'",
        operand.location);
    valid = false;
    return std::size_t{0};
  }

  const std::string operandBase = baseTypeName(operandType);
  if (isVectorType(operandBase)) {
    return vectorWidthFromName(operandBase);
  }
  return std::size_t{1};
}

void validateHIRVectorConstructorTypedExpression(
    const HIRExpression &expression, const HIRType &constructorType,
    const std::string &context, const HIRSymbolTable &symbols,
    DiagnosticEngine &diagnostics) {
  const std::string targetBase = baseTypeName(constructorType);
  const std::optional<std::size_t> targetWidth =
      vectorWidthFromName(targetBase);
  if (!targetWidth.has_value() || constructorType.arraySize.has_value()) {
    return;
  }

  const HIRType componentType = scalarTypeForVector(targetBase);
  std::size_t componentCount = 0;
  bool allOperandWidthsKnown = true;
  bool valid = true;
  for (const HIRExpression &operand : expression.children) {
    const std::optional<HIRType> operandType =
        hirExpressionEffectiveType(operand, symbols);
    if (!operandType.has_value()) {
      allOperandWidthsKnown = false;
      continue;
    }
    const std::optional<std::size_t> operandWidth =
        hirConstructorConstituentWidth(
            operand, *operandType, componentType, expression.value,
            "opt.hir-vector-constructor", "vector", context, diagnostics,
            valid);
    if (!operandWidth.has_value()) {
      allOperandWidthsKnown = false;
      continue;
    }
    componentCount += *operandWidth;
  }

  const bool scalarSplat =
      expression.children.size() == 1 && componentCount == std::size_t{1};
  if (valid && allOperandWidthsKnown && !scalarSplat &&
      componentCount != *targetWidth) {
    diagnostics.error("opt.hir-vector-constructor",
                      "HIR " + context + " vector constructor '" +
                          expression.value + "' expects " +
                          std::to_string(*targetWidth) +
                          " scalar components, got " +
                          std::to_string(componentCount),
                      expression.location);
  }
}

void validateHIRMatrixConstructorTypedExpression(
    const HIRExpression &expression, const HIRType &constructorType,
    const std::string &context, const HIRSymbolTable &symbols,
    DiagnosticEngine &diagnostics) {
  const std::string targetBase = baseTypeName(constructorType);
  const std::optional<std::size_t> targetElementCount =
      matrixElementCountFromName(targetBase);
  if (!targetElementCount.has_value() || constructorType.arraySize.has_value()) {
    return;
  }

  if (expression.children.size() == 1) {
    const std::optional<HIRType> sourceType =
        hirExpressionEffectiveType(expression.children.front(), symbols);
    if (!sourceType.has_value() || sourceType->name.empty()) {
      return;
    }
    if (!sourceType->arraySize.has_value()) {
      const std::string sourceBase = baseTypeName(*sourceType);
      if (isMatrixType(sourceBase) || isHIRScalarNumericType(*sourceType)) {
        return;
      }
    }
  }

  const HIRType componentType{"float", std::nullopt};
  std::size_t componentCount = 0;
  bool allOperandTypesKnown = true;
  bool valid = true;
  for (const HIRExpression &operand : expression.children) {
    const std::optional<HIRType> operandType =
        hirExpressionEffectiveType(operand, symbols);
    if (!operandType.has_value()) {
      allOperandTypesKnown = false;
      continue;
    }
    const std::optional<std::size_t> operandWidth =
        hirConstructorConstituentWidth(
            operand, *operandType, componentType, expression.value,
            "opt.hir-matrix-constructor", "matrix", context, diagnostics,
            valid);
    if (!operandWidth.has_value()) {
      allOperandTypesKnown = false;
      continue;
    }
    componentCount += *operandWidth;
  }

  if (valid && allOperandTypesKnown && componentCount != *targetElementCount) {
    diagnostics.error("opt.hir-matrix-constructor",
                      "HIR " + context + " matrix constructor '" +
                          expression.value + "' expects " +
                          std::to_string(*targetElementCount) +
                          " scalar components, got " +
                          std::to_string(componentCount),
                      expression.location);
  }
}

void validateHIRConstructorTypedExpression(
    const HIRExpression &expression, const std::string &context,
    const HIRSymbolTable &symbols, DiagnosticEngine &diagnostics) {
  if (expression.kind != HIRExpressionKind::Constructor ||
      expression.value.empty()) {
    return;
  }

  const HIRType constructorType{expression.value, std::nullopt,
                               expression.location};
  if (isHIRScalarNumericConstructorType(constructorType)) {
    if (expression.children.size() != 1) {
      diagnostics.error("opt.hir-scalar-constructor",
                        "HIR " + context + " scalar numeric constructor '" +
                            expression.value +
                            "' expects exactly one operand, got " +
                            std::to_string(expression.children.size()),
                        expression.location);
      return;
    }

    const std::optional<HIRType> sourceType =
        hirExpressionEffectiveType(expression.children.front(), symbols);
    if (sourceType.has_value() && !sourceType->name.empty() &&
        !isHIRScalarNumericType(*sourceType)) {
      diagnostics.error("opt.hir-scalar-constructor",
                        "HIR " + context + " scalar numeric constructor '" +
                            expression.value +
                            "' requires a scalar numeric operand, got '" +
                            formatType(*sourceType) + "'",
                        expression.children.front().location);
    }
    return;
  }

  validateHIRVectorConstructorTypedExpression(expression, constructorType,
                                             context, symbols, diagnostics);
  validateHIRMatrixConstructorTypedExpression(expression, constructorType,
                                             context, symbols, diagnostics);
}

void validateHIRUnaryOperatorOperandTypes(const HIRExpression &expression,
                                          const std::string &context,
                                          const HIRSymbolTable &symbols,
                                          DiagnosticEngine &diagnostics) {
  if (expression.kind != HIRExpressionKind::Unary ||
      expression.children.size() != 1) {
    return;
  }

  const HIRExpression &operand = expression.children.front();
  const std::optional<HIRType> operandType =
      hirExpressionEffectiveType(operand, symbols);
  if (!operandType.has_value()) {
    return;
  }

  if (expression.value == "!" && !isScalarBoolType(*operandType)) {
    diagnostics.error("opt.hir-logical-operand-type",
                      "HIR " + context +
                          " unary operator '!' requires a scalar bool operand, got '" +
                          formatType(*operandType) + "'",
                      operand.location);
  } else if ((expression.value == "+" || expression.value == "-") &&
             !isHIRArithmeticOperandType(*operandType)) {
    diagnostics.error("opt.hir-unary-operand-type",
                      "HIR " + context + " unary operator '" + expression.value +
                          "' requires a numeric scalar, vector, or matrix operand, got '" +
                          formatType(*operandType) + "'",
                      operand.location);
  }
}

void validateHIRBinaryOperatorOperandTypes(const HIRExpression &expression,
                                           const std::string &context,
                                           const HIRSymbolTable &symbols,
                                           DiagnosticEngine &diagnostics) {
  if (expression.kind != HIRExpressionKind::Binary ||
      expression.children.size() != 2) {
    return;
  }

  const std::optional<HIRType> leftType =
      hirExpressionEffectiveType(expression.children[0], symbols);
  const std::optional<HIRType> rightType =
      hirExpressionEffectiveType(expression.children[1], symbols);
  if (!leftType.has_value() || !rightType.has_value()) {
    return;
  }

  if ((expression.value == "&&" || expression.value == "||") &&
      (!isScalarBoolType(*leftType) || !isScalarBoolType(*rightType))) {
    diagnostics.error("opt.hir-logical-operand-type",
                      "HIR " + context + " logical operator '" + expression.value +
                          "' requires scalar bool operands, got '" +
                          formatType(*leftType) + " " + expression.value + " " +
                          formatType(*rightType) + "'",
                      expression.location);
  } else if (isHIRArithmeticBinaryOperator(expression.value) &&
             (!isHIRArithmeticOperandType(*leftType) ||
              !isHIRArithmeticOperandType(*rightType))) {
    diagnostics.error("opt.hir-binary-operand-type",
                      "HIR " + context + " arithmetic operator '" +
                          expression.value +
                          "' requires numeric scalar, vector, or matrix operands, got '" +
                          formatType(*leftType) + " " + expression.value + " " +
                          formatType(*rightType) + "'",
                      expression.location);
  } else if (isHIRRelationalBinaryOperator(expression.value) &&
             (!isHIRScalarNumericType(*leftType) ||
              !isHIRScalarNumericType(*rightType))) {
    diagnostics.error("opt.hir-comparison-operand-type",
                      "HIR " + context + " comparison operator '" +
                          expression.value +
                          "' requires scalar numeric operands, got '" +
                          formatType(*leftType) + " " + expression.value + " " +
                          formatType(*rightType) + "'",
                      expression.location);
  } else if (isHIREqualityBinaryOperator(expression.value) &&
             !isHIREqualityOperandPair(*leftType, *rightType)) {
    diagnostics.error("opt.hir-equality-operand-type",
                      "HIR " + context + " equality operator '" +
                          expression.value +
                          "' requires scalar bool operands or scalar numeric operands, got '" +
                          formatType(*leftType) + " " + expression.value + " " +
                          formatType(*rightType) + "'",
                      expression.location);
  }
}

void validateHIRSelectOperandTypes(const HIRExpression &expression,
                                   const std::string &context,
                                   const HIRSymbolTable &symbols,
                                   DiagnosticEngine &diagnostics) {
  if (expression.kind != HIRExpressionKind::Select ||
      expression.children.size() != 3) {
    return;
  }

  const std::optional<HIRType> conditionType =
      hirExpressionEffectiveType(expression.children[0], symbols);
  if (conditionType.has_value() && !isScalarBoolType(*conditionType)) {
    diagnostics.error("opt.hir-select-condition-type",
                      "HIR " + context +
                          " select condition must be scalar bool, got '" +
                          formatType(*conditionType) + "'",
                      expression.children[0].location);
  }

  const std::optional<HIRType> trueType =
      hirExpressionEffectiveType(expression.children[1], symbols);
  const std::optional<HIRType> falseType =
      hirExpressionEffectiveType(expression.children[2], symbols);
  if (trueType.has_value() && falseType.has_value() &&
      !isHIRSelectBranchOperandPair(*trueType, *falseType)) {
    diagnostics.error("opt.hir-select-branch-type",
                      "HIR " + context +
                          " select branches must have compatible scalar, vector, "
                          "or matrix value types, got '" +
                          formatType(*trueType) + " and " +
                          formatType(*falseType) + "'",
                      expression.location);
  }
}

bool isHIRStorageBufferResourceBase(
    const HIRExpression &base,
    const HIRIndexableResourceBaseSet *indexableResourceBases) {
  return indexableResourceBases != nullptr &&
         base.kind == HIRExpressionKind::Identifier &&
         indexableResourceBases->contains(base.value);
}

bool isHIRIndexableExpressionType(
    const HIRExpression &base, const HIRType &type,
    const HIRIndexableResourceBaseSet *indexableResourceBases) {
  if (isHIRStorageBufferResourceBase(base, indexableResourceBases)) {
    return true;
  }
  if (type.name.empty()) {
    return true;
  }
  HIRType baseType = stripTypeQualifier(type);
  if (baseType.name.empty()) {
    return true;
  }
  if (!baseType.name.empty() && baseType.name.back() == '*') {
    return true;
  }
  if (baseType.arraySize.has_value()) {
    return true;
  }
  return isVectorType(baseTypeName(baseType));
}

void validateHIRIndexAccessOperandTypes(const HIRExpression &expression,
                                        const std::string &context,
                                        const HIRSymbolTable &symbols,
                                        const HIRIndexableResourceBaseSet
                                            *indexableResourceBases,
                                        DiagnosticEngine &diagnostics) {
  if (expression.kind != HIRExpressionKind::IndexAccess ||
      expression.children.size() < 2) {
    return;
  }

  const std::optional<HIRType> baseType =
      hirExpressionEffectiveType(expression.children[0], symbols);
  if (baseType.has_value() &&
      !isHIRIndexableExpressionType(expression.children[0], *baseType,
                                    indexableResourceBases)) {
    diagnostics.error(
        "opt.hir-index-base-type",
        "HIR " + context +
            " index operator requires an array, storage-buffer pointer, "
            "descriptor array, or vector base, got '" +
            formatType(*baseType) + "'",
        expression.location);
  }

  const std::optional<HIRType> indexType =
      hirExpressionEffectiveType(expression.children[1], symbols);
  if (expression.children[1].kind != HIRExpressionKind::NonUniform &&
      indexType.has_value() && !isIntegerScalarType(*indexType)) {
    diagnostics.error(
        "opt.hir-index-type",
        "HIR " + context +
            " index operator requires a scalar int or uint index, got '" +
            formatType(*indexType) + "'",
        expression.children[1].location);
  }
}

void validateHIRExpressionTypedSymbols(
    const HIRExpression &expression, const std::string &context,
    const HIRSymbolTable &symbols, const HIRTypedSymbolContext &typedContext,
    DiagnosticEngine &diagnostics, bool skipIdentifierResolution = false,
    const HIRIndexableResourceBaseSet *indexableResourceBases = nullptr) {
  if (expression.kind == HIRExpressionKind::Empty) {
    return;
  }

  if (!expression.type.name.empty()) {
    reportHIRKnownType(expression.type, context + " result type", typedContext,
                       diagnostics);
  }

  if (expression.kind == HIRExpressionKind::Identifier &&
      !skipIdentifierResolution &&
      !isHIRPseudoControlIdentifier(expression.value)) {
    const auto symbol = symbols.find(expression.value);
    if (symbol == symbols.end()) {
      if (expression.type.name.empty()) {
        diagnostics.error(
            "opt.hir-unresolved-identifier",
            "HIR " + context + " references unresolved identifier '" +
                expression.value + "'",
            expression.location);
      }
    } else if (!expression.type.name.empty() &&
               !sameType(expression.type, symbol->second)) {
      diagnostics.error("opt.hir-identifier-type",
                        "HIR " + context + " identifier '" + expression.value +
                            "' has result type '" + formatType(expression.type) +
                            "' but resolves to '" + formatType(symbol->second) +
                            "'",
                        expression.location);
    }
  }

  if (expression.kind == HIRExpressionKind::Constructor &&
      !expression.value.empty()) {
    HIRType constructorType{expression.value, std::nullopt, expression.location};
    reportHIRKnownType(constructorType, context + " constructor", typedContext,
                       diagnostics);
    reportHIRExpressionResultTypeMismatch(
        expression, constructorType, context, "opt.hir-constructor-type",
        typedContext, diagnostics);
  }
  validateHIRConstructorTypedExpression(expression, context, symbols,
                                        diagnostics);

  if (const std::optional<HIRType> callResultType =
          hirKnownCallResultType(expression, symbols)) {
    reportHIRExpressionResultTypeMismatch(
        expression, *callResultType, context, "opt.hir-call-type",
        typedContext, diagnostics);
  }
  validateHIRIntrinsicArity(expression, context, diagnostics);
  validateHIRIntrinsicArgumentTypes(expression, context, symbols, typedContext,
                                    diagnostics);
  validateHIRUserFunctionCall(expression, context, symbols, typedContext,
                              diagnostics);
  validateHIRAtomicReadModifyWriteLValue(expression, context, symbols,
                                        diagnostics);
  validateHIRCallCalleeType(expression, context, typedContext, diagnostics);
  validateHIRUnaryOperatorOperandTypes(expression, context, symbols, diagnostics);
  validateHIRBinaryOperatorOperandTypes(expression, context, symbols, diagnostics);
  validateHIRSelectOperandTypes(expression, context, symbols, diagnostics);
  validateHIRIndexAccessOperandTypes(expression, context, symbols,
                                     indexableResourceBases, diagnostics);
  validateHIRTextureSampleTypedExpression(expression, context, symbols,
                                          typedContext, diagnostics);
  validateHIRTextureCompareTypedExpression(expression, context, symbols,
                                           typedContext, diagnostics);

  if (expression.kind == HIRExpressionKind::MemberAccess &&
      expression.children.size() == 1) {
    const std::optional<HIRType> baseType =
        hirExpressionEffectiveType(expression.children.front(), symbols);
    if (baseType.has_value()) {
      const std::string baseName = baseTypeName(*baseType);
      const auto structure = typedContext.structs.find(baseName);
      if (structure != typedContext.structs.end()) {
        const HIRField *field = nullptr;
        for (const HIRField &candidate : structure->second.fields) {
          if (candidate.name == expression.value) {
            field = &candidate;
            break;
          }
        }
        if (field == nullptr) {
          diagnostics.error("opt.hir-member-resolution",
                            "HIR " + context + " member '" + expression.value +
                                "' does not exist on struct '" + baseName + "'",
                            expression.location);
        } else if (!expression.type.name.empty() &&
                   !sameType(expression.type, field->type)) {
          diagnostics.error("opt.hir-member-type",
                            "HIR " + context + " member '" + expression.value +
                                "' has result type '" +
                                formatType(expression.type) +
                                "' but field type is '" +
                                formatType(field->type) + "'",
                            expression.location);
        }
      }
    }
  }

  for (std::size_t index = 0; index < expression.children.size(); ++index) {
    validateHIRExpressionTypedSymbols(
        expression.children[index],
        context + " child " + std::to_string(index), symbols, typedContext,
        diagnostics, isManualHIRTextureCompareOpOperand(expression, index) ||
                         isHIRImageAccessResourceOperand(expression, index),
        indexableResourceBases);
  }
}

void validateHIRConditionType(const HIRExpression &condition,
                              const std::string &context,
                              const HIRSymbolTable &symbols,
                              DiagnosticEngine &diagnostics) {
  const std::optional<HIRType> conditionType =
      hirExpressionEffectiveType(condition, symbols);
  if (conditionType.has_value() && !isScalarBoolType(*conditionType)) {
    diagnostics.error("opt.hir-condition-type",
                      "HIR " + context +
                          " condition must be scalar bool, got '" +
                          formatType(*conditionType) + "'",
                      condition.location);
  }
}

void validateHIRStatementTypedSymbols(
    const HIRStatement &statement, const HIRType &returnType,
    HIRSymbolTable &symbols, const HIRTypedSymbolContext &typedContext,
    HIRReadOnlySymbolSet &readOnlySymbols,
    HIRResourceHandleSymbolSet &resourceHandleSymbols,
    HIRIndexableResourceBaseSet &indexableResourceBases,
    DiagnosticEngine &diagnostics, const std::string &context);

void validateHIRStatementBlockTypedSymbols(
    std::span<const HIRStatement> statements, const HIRType &returnType,
    HIRSymbolTable &symbols, const HIRTypedSymbolContext &typedContext,
    HIRReadOnlySymbolSet &readOnlySymbols,
    HIRResourceHandleSymbolSet &resourceHandleSymbols,
    HIRIndexableResourceBaseSet &indexableResourceBases,
    DiagnosticEngine &diagnostics, const std::string &context) {
  for (const HIRStatement &statement : statements) {
    validateHIRStatementTypedSymbols(statement, returnType, symbols,
                                     typedContext, readOnlySymbols,
                                     resourceHandleSymbols,
                                     indexableResourceBases, diagnostics,
                                     context);
  }
}

void validateHIRStatementTypedSymbols(
    const HIRStatement &statement, const HIRType &returnType,
    HIRSymbolTable &symbols, const HIRTypedSymbolContext &typedContext,
    HIRReadOnlySymbolSet &readOnlySymbols,
    HIRResourceHandleSymbolSet &resourceHandleSymbols,
    HIRIndexableResourceBaseSet &indexableResourceBases,
    DiagnosticEngine &diagnostics, const std::string &context) {
  const std::string statementContext =
      context + " " + statementKindName(statement.kind) + " statement";
  validateHIRAtomicReadModifyWriteValueUseInExpression(
      statement.target, false, statementContext + " target", diagnostics);
  const bool allowRootAtomicReadModifyWrite =
      isHIRAtomicReadModifyWriteCall(statement.value) &&
      (statement.kind == HIRStatementKind::Expression ||
       statement.kind == HIRStatementKind::Declaration ||
       statement.kind == HIRStatementKind::Assignment);
  validateHIRAtomicReadModifyWriteValueUseInExpression(
      statement.value, allowRootAtomicReadModifyWrite,
      statementContext + " value", diagnostics);
  switch (statement.kind) {
  case HIRStatementKind::Declaration: {
    reportHIRKnownType(statement.declaredType,
                       statementContext + " declared type", typedContext,
                       diagnostics);
    validateHIRExpressionTypedSymbols(statement.value,
                                      statementContext + " initializer",
                                      symbols, typedContext, diagnostics, false,
                                      &indexableResourceBases);
    if (!isEmptyHIRExpressionSlot(statement.value)) {
      const std::optional<HIRType> valueType =
          hirExpressionEffectiveType(statement.value, symbols);
      if (valueType.has_value()) {
        validateHIRTypeCompatibility(
            statement.declaredType, *valueType, statementContext + " initializer",
            statement.value.location, "opt.hir-declaration-type", typedContext,
            diagnostics);
      }
    }
    if (!statement.name.empty()) {
      symbols[statement.name] = statement.declaredType;
      readOnlySymbols.erase(statement.name);
      resourceHandleSymbols.erase(statement.name);
      indexableResourceBases.erase(statement.name);
    }
    break;
  }
  case HIRStatementKind::Assignment: {
    validateHIRExpressionTypedSymbols(statement.target,
                                      statementContext + " target", symbols,
                                      typedContext, diagnostics, false,
                                      &indexableResourceBases);
    validateHIRExpressionTypedSymbols(statement.value,
                                      statementContext + " value", symbols,
                                      typedContext, diagnostics, false,
                                      &indexableResourceBases);
    if (!isEmptyHIRExpressionSlot(statement.target) &&
        !isHIRAssignableTargetExpression(statement.target)) {
      const HIRExpression &target =
          hirAssignmentTargetDiagnosticExpression(statement.target);
      diagnostics.error("opt.hir-assignment-target-lvalue",
                        "HIR " + statementContext +
                            " target must be an assignable storage location, "
                            "got '" +
                            expressionKindName(target.kind) + "' expression",
                        target.location);
    }
    if (const HIRExpression *target =
            hirDuplicateSwizzleAssignmentTargetExpression(statement.target,
                                                          symbols)) {
      diagnostics.error("opt.hir-assignment-target-swizzle-duplicate",
                        "HIR " + statementContext +
                            " target swizzle '" + target->value +
                            "' cannot write the same vector component more "
                            "than once",
                        target->location);
    }
    if (const HIRExpression *direct =
            hirAssignmentTargetDirectIdentifier(statement.target);
        direct != nullptr && resourceHandleSymbols.contains(direct->value)) {
      diagnostics.error("opt.hir-assignment-target-readonly",
                        "HIR " + statementContext + " target '" +
                            direct->value + "' is a resource handle",
                        direct->location);
    } else if (const HIRExpression *root =
                   hirAssignmentTargetRootIdentifier(statement.target);
               root != nullptr && readOnlySymbols.contains(root->value)) {
      diagnostics.error("opt.hir-assignment-target-readonly",
                        "HIR " + statementContext + " target '" + root->value +
                            "' is read-only",
                        root->location);
    } else if (const HIRExpression *target =
                   hirAggregateAssignmentTargetExpression(statement.target)) {
      diagnostics.error("opt.hir-assignment-target-lvalue",
                        "HIR " + statementContext + " target " +
                            hirAssignmentTargetDescription(*target) +
                            " has array type '" + formatType(target->type) +
                            "'; assign an element instead",
                        target->location);
    }
    const std::optional<HIRType> targetType =
        hirExpressionEffectiveType(statement.target, symbols);
    const std::optional<HIRType> valueType =
        hirExpressionEffectiveType(statement.value, symbols);
    if (targetType.has_value() && valueType.has_value()) {
      validateHIRTypeCompatibility(*targetType, *valueType, statementContext,
                                   statement.value.location,
                                   "opt.hir-assignment-type", typedContext,
                                   diagnostics);
    }
    break;
  }
  case HIRStatementKind::Return: {
    validateHIRExpressionTypedSymbols(statement.value,
                                      statementContext + " value", symbols,
                                      typedContext, diagnostics, false,
                                      &indexableResourceBases);
    if (isSourceBackedUnknownHIRType(returnType, typedContext)) {
      break;
    }
    if (isVoidType(returnType)) {
      if (!isEmptyHIRExpressionSlot(statement.value)) {
        diagnostics.error("opt.hir-return-type",
                          "HIR " + statementContext +
                              " in void function must not return a value",
                          statement.value.location);
      }
    } else if (isEmptyHIRExpressionSlot(statement.value)) {
      diagnostics.error("opt.hir-return-type",
                        "HIR " + statementContext + " must return type '" +
                            formatType(returnType) + "'",
                        hirStatementSourceLocation(statement));
    } else {
      const std::optional<HIRType> valueType =
          hirExpressionEffectiveType(statement.value, symbols);
      if (valueType.has_value()) {
        validateHIRTypeCompatibility(returnType, *valueType, statementContext,
                                     statement.value.location,
                                     "opt.hir-return-type", typedContext,
                                     diagnostics);
      }
    }
    break;
  }
  case HIRStatementKind::Expression:
    validateHIRExpressionTypedSymbols(statement.value,
                                      statementContext + " value", symbols,
                                      typedContext, diagnostics, false,
                                      &indexableResourceBases);
    break;
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
    break;
  case HIRStatementKind::Block: {
    HIRSymbolTable blockSymbols = symbols;
    HIRReadOnlySymbolSet blockReadOnlySymbols = readOnlySymbols;
    HIRResourceHandleSymbolSet blockResourceHandleSymbols =
        resourceHandleSymbols;
    HIRIndexableResourceBaseSet blockIndexableResourceBases =
        indexableResourceBases;
    validateHIRStatementBlockTypedSymbols(statement.body, returnType,
                                          blockSymbols, typedContext,
                                          blockReadOnlySymbols,
                                          blockResourceHandleSymbols,
                                          blockIndexableResourceBases,
                                          diagnostics,
                                          statementContext + " body");
    break;
  }
  case HIRStatementKind::If: {
    validateHIRExpressionTypedSymbols(statement.value,
                                      statementContext + " condition", symbols,
                                      typedContext, diagnostics, false,
                                      &indexableResourceBases);
    validateHIRConditionType(statement.value, statementContext, symbols,
                             diagnostics);
    HIRSymbolTable thenSymbols = symbols;
    HIRReadOnlySymbolSet thenReadOnlySymbols = readOnlySymbols;
    HIRResourceHandleSymbolSet thenResourceHandleSymbols =
        resourceHandleSymbols;
    HIRIndexableResourceBaseSet thenIndexableResourceBases =
        indexableResourceBases;
    validateHIRStatementBlockTypedSymbols(statement.body, returnType,
                                          thenSymbols, typedContext,
                                          thenReadOnlySymbols,
                                          thenResourceHandleSymbols,
                                          thenIndexableResourceBases,
                                          diagnostics, statementContext + " body");
    HIRSymbolTable elseSymbols = symbols;
    HIRReadOnlySymbolSet elseReadOnlySymbols = readOnlySymbols;
    HIRResourceHandleSymbolSet elseResourceHandleSymbols =
        resourceHandleSymbols;
    HIRIndexableResourceBaseSet elseIndexableResourceBases =
        indexableResourceBases;
    validateHIRStatementBlockTypedSymbols(statement.elseBody, returnType,
                                          elseSymbols, typedContext,
                                          elseReadOnlySymbols,
                                          elseResourceHandleSymbols,
                                          elseIndexableResourceBases,
                                          diagnostics, statementContext + " else");
    break;
  }
  case HIRStatementKind::For: {
    HIRSymbolTable loopSymbols = symbols;
    HIRReadOnlySymbolSet loopReadOnlySymbols = readOnlySymbols;
    HIRResourceHandleSymbolSet loopResourceHandleSymbols =
        resourceHandleSymbols;
    HIRIndexableResourceBaseSet loopIndexableResourceBases =
        indexableResourceBases;
    for (const HIRStatement &initializer : statement.initializer) {
      validateHIRStatementTypedSymbols(initializer, returnType, loopSymbols,
                                       typedContext, loopReadOnlySymbols,
                                       loopResourceHandleSymbols,
                                       loopIndexableResourceBases,
                                       diagnostics,
                                       statementContext + " initializer");
    }
    validateHIRExpressionTypedSymbols(statement.value,
                                      statementContext + " condition", loopSymbols,
                                      typedContext, diagnostics, false,
                                      &loopIndexableResourceBases);
    if (!isEmptyHIRExpressionSlot(statement.value)) {
      validateHIRConditionType(statement.value, statementContext, loopSymbols,
                               diagnostics);
    }
    for (const HIRStatement &update : statement.update) {
      validateHIRStatementTypedSymbols(update, returnType, loopSymbols,
                                       typedContext, loopReadOnlySymbols,
                                       loopResourceHandleSymbols,
                                       loopIndexableResourceBases,
                                       diagnostics,
                                       statementContext + " update");
    }
    HIRSymbolTable bodySymbols = loopSymbols;
    HIRReadOnlySymbolSet bodyReadOnlySymbols = loopReadOnlySymbols;
    HIRResourceHandleSymbolSet bodyResourceHandleSymbols =
        loopResourceHandleSymbols;
    HIRIndexableResourceBaseSet bodyIndexableResourceBases =
        loopIndexableResourceBases;
    validateHIRStatementBlockTypedSymbols(statement.body, returnType,
                                          bodySymbols, typedContext,
                                          bodyReadOnlySymbols,
                                          bodyResourceHandleSymbols,
                                          bodyIndexableResourceBases, diagnostics,
                                          statementContext + " body");
    break;
  }
  case HIRStatementKind::Raw:
    break;
  }
}

HIRTypedSymbolContext collectHIRTypedSymbolContext(const HIRModule &module) {
  HIRTypedSymbolContext context;
  for (const HIRStruct &structure : module.structs) {
    if (!structure.name.empty()) {
      context.structNames.insert(structure.name);
      context.structs[structure.name] = structure;
    }
  }
  for (const HIRConstant &constant : module.constants) {
    if (!constant.name.empty()) {
      context.constants[constant.name] = constant.type;
    }
  }
  addHIRFunctionSignatures(context.functionSignatures, module.functions);
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind != HIRResourceKind::Uniform) {
        continue;
      }
      const auto structure = context.structs.find(baseTypeName(resource.type));
      if (structure == context.structs.end()) {
        continue;
      }
      for (const HIRField &field : structure->second.fields) {
        context.globalCBufferFields[field.name] = field.type;
      }
    }
  }
  return context;
}

HIRSymbolTable baseHIRSymbolsForFunction(
    const HIRFunction &function, const HIRTypedSymbolContext &typedContext) {
  HIRSymbolTable symbols = typedContext.constants;
  for (const auto &[name, type] : typedContext.globalCBufferFields) {
    symbols[name] = type;
  }
  for (const HIRParameter &parameter : function.parameters) {
    if (!parameter.name.empty()) {
      symbols[parameter.name] = parameter.type;
    }
  }
  return symbols;
}

HIRReadOnlySymbolSet baseHIRReadOnlySymbolsForFunction(
    const HIRFunction &function, const HIRTypedSymbolContext &typedContext) {
  HIRReadOnlySymbolSet readOnlySymbols;
  for (const auto &[name, _] : typedContext.constants) {
    readOnlySymbols.insert(name);
  }
  for (const auto &[name, _] : typedContext.globalCBufferFields) {
    readOnlySymbols.insert(name);
  }
  for (const HIRParameter &parameter : function.parameters) {
    if (!parameter.name.empty()) {
      readOnlySymbols.erase(parameter.name);
    }
  }
  return readOnlySymbols;
}

HIRSymbolTable stageHIRSymbolsForFunction(
    const HIRFunction &function, const HIRStage &stage,
    const HIRTypedSymbolContext &typedContext) {
  HIRSymbolTable symbols = baseHIRSymbolsForFunction(function, typedContext);
  if (stage.stage == "compute") {
    symbols["gl_GlobalInvocationID"] = HIRType{"uvec3", std::nullopt};
    symbols["gl_LocalInvocationID"] = HIRType{"uvec3", std::nullopt};
    symbols["gl_WorkGroupID"] = HIRType{"uvec3", std::nullopt};
    symbols["gl_NumWorkGroups"] = HIRType{"uvec3", std::nullopt};
  }
  for (const HIRFunction &stageFunction : stage.functions) {
    for (const HIRParameter &parameter : stageFunction.parameters) {
      if (!parameter.name.empty()) {
        symbols[parameter.name] = parameter.type;
      }
    }
  }
  for (const HIRResource &resource : stage.resources) {
    if (resource.name.empty()) {
      continue;
    }
    if (resource.kind == HIRResourceKind::Uniform) {
      const auto structure =
          typedContext.structs.find(baseTypeName(resource.type));
      if (structure != typedContext.structs.end()) {
        for (const HIRField &field : structure->second.fields) {
          symbols[field.name] = field.type;
        }
      }
    }
    symbols[resource.name] = resource.type;
  }
  for (const HIRParameter &parameter : function.parameters) {
    if (!parameter.name.empty()) {
      symbols[parameter.name] = parameter.type;
    }
  }
  return symbols;
}

HIRReadOnlySymbolSet stageHIRReadOnlySymbolsForFunction(
    const HIRFunction &function, const HIRStage &stage,
    const HIRTypedSymbolContext &typedContext) {
  HIRReadOnlySymbolSet readOnlySymbols =
      baseHIRReadOnlySymbolsForFunction(function, typedContext);
  if (stage.stage == "compute") {
    readOnlySymbols.insert("gl_GlobalInvocationID");
    readOnlySymbols.insert("gl_LocalInvocationID");
    readOnlySymbols.insert("gl_WorkGroupID");
    readOnlySymbols.insert("gl_NumWorkGroups");
  }
  for (const HIRParameter &parameter : function.parameters) {
    if (!parameter.name.empty()) {
      readOnlySymbols.erase(parameter.name);
    }
  }
  return readOnlySymbols;
}

HIRResourceHandleSymbolSet stageHIRResourceHandleSymbolsForFunction(
    const HIRFunction &function, const HIRStage &stage) {
  HIRResourceHandleSymbolSet resourceHandleSymbols;
  for (const HIRResource &resource : stage.resources) {
    if (resource.name.empty() || resource.kind == HIRResourceKind::Shared) {
      continue;
    }
    resourceHandleSymbols.insert(resource.name);
  }
  for (const HIRParameter &parameter : function.parameters) {
    if (!parameter.name.empty()) {
      resourceHandleSymbols.erase(parameter.name);
    }
  }
  return resourceHandleSymbols;
}

HIRIndexableResourceBaseSet stageHIRIndexableResourceBasesForFunction(
    const HIRFunction &function, const HIRStage &stage) {
  HIRIndexableResourceBaseSet indexableResourceBases;
  for (const HIRResource &resource : stage.resources) {
    if (!resource.name.empty() && resource.kind == HIRResourceKind::Buffer) {
      indexableResourceBases.insert(resource.name);
    }
  }
  for (const HIRParameter &parameter : function.parameters) {
    if (!parameter.name.empty()) {
      indexableResourceBases.erase(parameter.name);
    }
  }
  return indexableResourceBases;
}

void validateHIRFunctionTypedSymbols(
    const HIRFunction &function, HIRSymbolTable symbols,
    HIRReadOnlySymbolSet readOnlySymbols,
    HIRResourceHandleSymbolSet resourceHandleSymbols,
    HIRIndexableResourceBaseSet indexableResourceBases,
    const HIRTypedSymbolContext &typedContext, DiagnosticEngine &diagnostics,
    const std::string &context) {
  const std::string functionName =
      function.name.empty() ? std::string("<unnamed>") : function.name;
  const std::string functionContext =
      context + " function '" + functionName + "'";
  reportHIRKnownType(function.returnType, functionContext + " return type",
                     typedContext, diagnostics);
  for (const HIRParameter &parameter : function.parameters) {
    reportHIRKnownType(parameter.type,
                       functionContext + " parameter '" + parameter.name + "'",
                       typedContext, diagnostics);
  }
  validateHIRStatementBlockTypedSymbols(function.body, function.returnType,
                                        symbols, typedContext, readOnlySymbols,
                                        resourceHandleSymbols,
                                        indexableResourceBases, diagnostics,
                                        functionContext);
}

void validateHIRResourceTypedSymbols(const HIRResource &resource,
                                     const std::string &stageLabel,
                                     const HIRTypedSymbolContext &typedContext,
                                     DiagnosticEngine &diagnostics) {
  const std::string resourceName =
      resource.name.empty() ? std::string("<unnamed>") : resource.name;
  const std::string context =
      "stage '" + stageLabel + "' resource '" + resourceName + "'";
  reportHIRKnownType(resource.type, context + " type", typedContext,
                     diagnostics);

  const std::string baseType = baseTypeName(resource.type);
  const bool textureType = isTextureResourceType(baseType);
  const bool storageImageType = isStorageImageResourceType(baseType);
  const bool samplerType = isSamplerResourceType(baseType);
  bool validKindTypePair = true;
  switch (resource.kind) {
  case HIRResourceKind::Texture:
    validKindTypePair = textureType;
    break;
  case HIRResourceKind::StorageImage:
    validKindTypePair = storageImageType;
    break;
  case HIRResourceKind::Sampler:
    validKindTypePair = samplerType;
    break;
  case HIRResourceKind::Uniform:
  case HIRResourceKind::Buffer:
  case HIRResourceKind::Shared:
  case HIRResourceKind::Value:
    validKindTypePair = !textureType && !storageImageType && !samplerType;
    break;
  }

  if (!validKindTypePair) {
    diagnostics.error("opt.hir-resource-type-mismatch",
                      "HIR " + context + " kind '" +
                          resourceKindName(resource.kind) +
                          "' is incompatible with type '" +
                          formatType(resource.type) + "'",
                      resource.type.location);
  }

  if (resource.kind == HIRResourceKind::StorageImage &&
      hasHIRRuntimeArrayDimension(resource.type)) {
    diagnostics.error(
        "opt.hir-storage-image-runtime-descriptor-array",
        "HIR " + context +
            " uses a runtime/unsized storage-image descriptor array, which is "
            "not supported",
        resource.type.location);
  } else if (hasHIRRuntimeArrayDimension(resource.type) &&
             !isSingleHIRRuntimeArrayDimension(resource.type)) {
    diagnostics.error(
        "opt.hir-runtime-resource-array-shape",
        "HIR " + context + " uses invalid runtime descriptor/resource array "
            "shape '" +
            formatType(resource.type) +
            "'; runtime descriptor/resource arrays must use exactly one "
            "unsized descriptor dimension",
        resource.type.location);
  }
}

bool validateHIRTypedSymbols(HIRModule &module, DiagnosticEngine &diagnostics) {
  const HIRTypedSymbolContext typedContext =
      collectHIRTypedSymbolContext(module);

  for (const HIRStruct &structure : module.structs) {
    const std::string structName =
        structure.name.empty() ? std::string("<unnamed>") : structure.name;
    for (const HIRField &field : structure.fields) {
      reportHIRKnownType(field.type,
                         "struct '" + structName + "' field '" + field.name +
                             "'",
                         typedContext, diagnostics);
    }
  }

  for (const HIRConstant &constant : module.constants) {
    const std::string constantName =
        constant.name.empty() ? std::string("<unnamed>") : constant.name;
    reportHIRKnownType(constant.type, "constant '" + constantName + "'",
                       typedContext, diagnostics);
    validateHIRExpressionTypedSymbols(
        constant.value, "constant '" + constantName + "' value",
        typedContext.constants, typedContext, diagnostics);
  }

  for (const HIRFunction &function : module.functions) {
    validateHIRFunctionTypedSymbols(
        function, baseHIRSymbolsForFunction(function, typedContext),
        baseHIRReadOnlySymbolsForFunction(function, typedContext),
        HIRResourceHandleSymbolSet{}, HIRIndexableResourceBaseSet{},
        typedContext, diagnostics, "top-level");
  }

  for (const HIRStage &stage : module.stages) {
    const std::string stageLabel =
        stage.stage.empty() ? std::string("<unnamed>") : stage.stage;
    for (const HIRResource &resource : stage.resources) {
      validateHIRResourceTypedSymbols(resource, stageLabel, typedContext,
                                      diagnostics);
    }
    HIRTypedSymbolContext stageTypedContext = typedContext;
    addHIRFunctionSignatures(stageTypedContext.functionSignatures,
                             stage.functions);
    for (const HIRFunction &function : stage.functions) {
      validateHIRFunctionTypedSymbols(
          function,
          stageHIRSymbolsForFunction(function, stage, stageTypedContext),
          stageHIRReadOnlySymbolsForFunction(function, stage, stageTypedContext),
          stageHIRResourceHandleSymbolsForFunction(function, stage),
          stageHIRIndexableResourceBasesForFunction(function, stage),
          stageTypedContext, diagnostics, "stage '" + stageLabel + "'");
    }
  }

  return false;
}

FoldedHIRValue foldedHIRValueFromScalar(FoldedHIRScalar scalar) {
  FoldedHIRValue value;
  value.components.push_back(std::move(scalar));
  return value;
}

struct HIRFoldContext {
  const HIRScalarConstantMap *globalScalarConstants = nullptr;
  const HIRValueConstantMap *globalValueConstants = nullptr;
  HIRScalarConstantMap scalarConstants;
  HIRValueConstantMap valueConstants;
  std::set<std::string> hiddenNames;
};

HIRFoldContext makeHIRFoldContext(
    const HIRScalarConstantMap &globalScalarConstants,
    const HIRValueConstantMap &globalValueConstants) {
  HIRFoldContext context;
  context.globalScalarConstants = &globalScalarConstants;
  context.globalValueConstants = &globalValueConstants;
  context.scalarConstants = globalScalarConstants;
  context.valueConstants = globalValueConstants;
  return context;
}

void eraseHIRFoldedName(HIRFoldContext &context, const std::string &name) {
  context.scalarConstants.erase(name);
  context.valueConstants.erase(name);
}

void clearHIRLocalFoldedValues(HIRFoldContext &context) {
  context.scalarConstants =
      context.globalScalarConstants == nullptr ? HIRScalarConstantMap{}
                                               : *context.globalScalarConstants;
  context.valueConstants =
      context.globalValueConstants == nullptr ? HIRValueConstantMap{}
                                              : *context.globalValueConstants;
  for (const std::string &name : context.hiddenNames) {
    eraseHIRFoldedName(context, name);
  }
}

std::optional<HIRExpression>
foldedHIRValueToExpression(const FoldedHIRValue &value, const HIRType &type,
                           SourceLocation location) {
  if (value.components.size() == 1) {
    const std::optional<std::string> foldedText =
        formatFoldedHIRScalarForType(value.components.front(), type);
    if (!foldedText.has_value()) {
      return std::nullopt;
    }
    HIRExpression result;
    result.kind = HIRExpressionKind::Literal;
    result.type = type;
    result.value = *foldedText;
    result.location = std::move(location);
    return result;
  }

  if (!isFoldableHIRVectorType(type)) {
    return std::nullopt;
  }
  const std::string constructorName = baseTypeName(type);
  const std::optional<std::size_t> width =
      vectorWidthFromName(constructorName);
  if (!width.has_value() || value.components.size() != *width) {
    return std::nullopt;
  }

  const HIRType componentType = scalarTypeForVector(constructorName);
  HIRExpression result;
  result.kind = HIRExpressionKind::Constructor;
  result.type = type;
  result.value = constructorName;
  result.location = std::move(location);
  result.children.reserve(value.components.size());
  for (const FoldedHIRScalar &component : value.components) {
    const std::optional<std::string> foldedText =
        formatFoldedHIRScalarForType(component, componentType);
    if (!foldedText.has_value()) {
      return std::nullopt;
    }
    HIRExpression child;
    child.kind = HIRExpressionKind::Literal;
    child.type = componentType;
    child.value = *foldedText;
    child.location = result.location;
    result.children.push_back(std::move(child));
  }
  return result;
}

void rememberFoldedHIRDeclaration(HIRFoldContext &context,
                                  const std::string &name,
                                  const HIRType &type,
                                  const HIRExpression &value) {
  if (name.empty()) {
    return;
  }

  context.hiddenNames.insert(name);
  eraseHIRFoldedName(context, name);

  HIRScalarFoldOptions options;
  options.foldIntrinsicCalls = true;
  const std::optional<FoldedHIRValue> foldedValue =
      foldHIRValueExpression(value, context.scalarConstants, options,
                             &context.valueConstants);
  if (!foldedValue.has_value()) {
    return;
  }

  if (foldedValue->components.size() == 1) {
    const FoldedHIRScalar &folded = foldedValue->components.front();
    if (!formatFoldedHIRScalarForType(folded, type).has_value()) {
      return;
    }
    context.scalarConstants[name] = folded;
    context.valueConstants[name] = *foldedValue;
    return;
  }

  if (foldedHIRValueToExpression(*foldedValue, type, value.location)
          .has_value()) {
    context.valueConstants[name] = *foldedValue;
  }
}

HIRExpression makeHIRBoolLiteral(bool value, SourceLocation location) {
  HIRExpression expression;
  expression.kind = HIRExpressionKind::Literal;
  expression.type = HIRType{"bool", std::nullopt};
  expression.value = value ? "true" : "false";
  expression.location = std::move(location);
  return expression;
}

std::optional<std::string>
hirSimpleIdentifierExpression(const HIRExpression &expression) {
  if (expression.kind == HIRExpressionKind::Identifier) {
    return expression.value.empty() ? std::nullopt
                                    : std::optional<std::string>{
                                          expression.value};
  }
  if (expression.kind == HIRExpressionKind::Group &&
      !expression.children.empty()) {
    return hirSimpleIdentifierExpression(expression.children.front());
  }
  return std::nullopt;
}

std::optional<std::string>
hirExpressionRootIdentifier(const HIRExpression &expression) {
  switch (expression.kind) {
  case HIRExpressionKind::Identifier:
    return expression.value.empty() ? std::nullopt
                                    : std::optional<std::string>{
                                          expression.value};
  case HIRExpressionKind::Group:
  case HIRExpressionKind::MemberAccess:
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::NonUniform:
    if (!expression.children.empty()) {
      return hirExpressionRootIdentifier(expression.children.front());
    }
    return std::nullopt;
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Literal:
  case HIRExpressionKind::Call:
  case HIRExpressionKind::Constructor:
  case HIRExpressionKind::Unary:
  case HIRExpressionKind::Binary:
  case HIRExpressionKind::Select:
  case HIRExpressionKind::TextureSample:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    return std::nullopt;
  }
  return std::nullopt;
}

void collectHIRAssignedNames(const HIRStatement &statement,
                             std::set<std::string> &names) {
  if (statement.kind == HIRStatementKind::Assignment) {
    if (std::optional<std::string> name =
            hirExpressionRootIdentifier(statement.target)) {
      names.insert(std::move(*name));
    }
  }

  for (const HIRStatement &initializer : statement.initializer) {
    collectHIRAssignedNames(initializer, names);
  }
  for (const HIRStatement &update : statement.update) {
    collectHIRAssignedNames(update, names);
  }
  for (const HIRStatement &child : statement.body) {
    collectHIRAssignedNames(child, names);
  }
  for (const HIRStatement &child : statement.elseBody) {
    collectHIRAssignedNames(child, names);
  }
}

void collectHIRDeclaredNames(const HIRStatement &statement,
                             std::set<std::string> &names) {
  if (statement.kind == HIRStatementKind::Declaration &&
      !statement.name.empty()) {
    names.insert(statement.name);
  }

  for (const HIRStatement &initializer : statement.initializer) {
    collectHIRDeclaredNames(initializer, names);
  }
  for (const HIRStatement &update : statement.update) {
    collectHIRDeclaredNames(update, names);
  }
  for (const HIRStatement &child : statement.body) {
    collectHIRDeclaredNames(child, names);
  }
  for (const HIRStatement &child : statement.elseBody) {
    collectHIRDeclaredNames(child, names);
  }
}

bool containsRawHIRStatement(std::span<const HIRStatement> statements) {
  for (const HIRStatement &statement : statements) {
    if (statement.kind == HIRStatementKind::Raw ||
        containsRawHIRStatement(statement.initializer) ||
        containsRawHIRStatement(statement.update) ||
        containsRawHIRStatement(statement.body) ||
        containsRawHIRStatement(statement.elseBody)) {
      return true;
    }
  }
  return false;
}

bool containsOpaqueDeadLocalCleanupStatement(
    std::span<const HIRStatement> statements) {
  for (const HIRStatement &statement : statements) {
    if (statement.kind == HIRStatementKind::Raw ||
        (!statement.updateTokens.empty() && statement.update.empty()) ||
        containsOpaqueDeadLocalCleanupStatement(statement.initializer) ||
        containsOpaqueDeadLocalCleanupStatement(statement.update) ||
        containsOpaqueDeadLocalCleanupStatement(statement.body) ||
        containsOpaqueDeadLocalCleanupStatement(statement.elseBody)) {
      return true;
    }
  }
  return false;
}

bool hirStatementAlwaysTerminates(const HIRStatement &statement);

bool hirBlockAlwaysTerminates(std::span<const HIRStatement> statements) {
  for (const HIRStatement &statement : statements) {
    if (hirStatementAlwaysTerminates(statement)) {
      return true;
    }
  }
  return false;
}

bool hirStatementAlwaysTerminates(const HIRStatement &statement) {
  switch (statement.kind) {
  case HIRStatementKind::Return:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
    return true;
  case HIRStatementKind::Block:
    return hirBlockAlwaysTerminates(statement.body);
  case HIRStatementKind::If:
    return hirBlockAlwaysTerminates(statement.body) &&
           hirBlockAlwaysTerminates(statement.elseBody);
  case HIRStatementKind::For:
  case HIRStatementKind::Declaration:
  case HIRStatementKind::Assignment:
  case HIRStatementKind::Expression:
  case HIRStatementKind::Raw:
    return false;
  }
  return false;
}

bool cleanupUnreachableHIRStatementsInBlock(
    std::vector<HIRStatement> &statements);

bool cleanupUnreachableHIRStatementsInStatement(HIRStatement &statement) {
  bool changed = false;
  switch (statement.kind) {
  case HIRStatementKind::Block:
    changed = cleanupUnreachableHIRStatementsInBlock(statement.body) ||
              changed;
    return changed;
  case HIRStatementKind::If:
    changed = cleanupUnreachableHIRStatementsInBlock(statement.body) ||
              changed;
    changed = cleanupUnreachableHIRStatementsInBlock(statement.elseBody) ||
              changed;
    return changed;
  case HIRStatementKind::For:
    changed = cleanupUnreachableHIRStatementsInBlock(statement.body) ||
              changed;
    return changed;
  case HIRStatementKind::Declaration:
  case HIRStatementKind::Assignment:
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Raw:
    return false;
  }
  return false;
}

bool cleanupUnreachableHIRStatementsInBlock(
    std::vector<HIRStatement> &statements) {
  bool changed = false;
  for (HIRStatement &statement : statements) {
    changed = cleanupUnreachableHIRStatementsInStatement(statement) ||
              changed;
  }

  for (std::size_t index = 0; index < statements.size(); ++index) {
    if (!hirStatementAlwaysTerminates(statements[index])) {
      continue;
    }
    if (index + 1 < statements.size()) {
      statements.erase(statements.begin() +
                           static_cast<std::ptrdiff_t>(index + 1),
                       statements.end());
      changed = true;
    }
    break;
  }
  return changed;
}

bool cleanupUnreachableHIRStatements(HIRModule &module, DiagnosticEngine &) {
  bool changed = false;
  for (HIRFunction &function : module.functions) {
    changed =
        mutateHIRFunctionBody(function, cleanupUnreachableHIRStatementsInBlock) ||
        changed;
  }
  for (HIRStage &stage : module.stages) {
    for (HIRFunction &function : stage.functions) {
      changed =
          mutateHIRFunctionBody(function,
                                cleanupUnreachableHIRStatementsInBlock) ||
          changed;
    }
  }
  return changed;
}

bool isPureHIRDeadLocalInitializer(const HIRExpression &expression) {
  return isKnownPureHIRExpression(expression);
}

void collectHIRExpressionIdentifiers(const HIRExpression &expression,
                                     std::set<std::string> &names) {
  if (expression.kind == HIRExpressionKind::Identifier &&
      !expression.value.empty() &&
      !isHIRPseudoControlIdentifier(expression.value)) {
    names.insert(expression.value);
  }
  for (const HIRExpression &child : expression.children) {
    collectHIRExpressionIdentifiers(child, names);
  }
}

void collectHIRExpressionIdentifiersExcept(
    const HIRExpression &expression, std::set<std::string> &names,
    const std::set<std::string> &hiddenNames) {
  if (expression.kind == HIRExpressionKind::Identifier &&
      !expression.value.empty() &&
      !isHIRPseudoControlIdentifier(expression.value) &&
      hiddenNames.find(expression.value) == hiddenNames.end()) {
    names.insert(expression.value);
  }
  for (const HIRExpression &child : expression.children) {
    collectHIRExpressionIdentifiersExcept(child, names, hiddenNames);
  }
}

void collectHIRBlockExternalIdentifiers(
    std::span<const HIRStatement> statements, std::set<std::string> &names,
    std::set<std::string> hiddenNames);

void collectHIRBlockExternalIdentifiersInScope(
    std::span<const HIRStatement> statements, std::set<std::string> &names,
    std::set<std::string> &hiddenNames);

void collectHIRStatementExternalIdentifiers(
    const HIRStatement &statement, std::set<std::string> &names,
    const std::set<std::string> &hiddenNames) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration: {
    collectHIRExpressionIdentifiersExcept(statement.value, names, hiddenNames);
    break;
  }
  case HIRStatementKind::Assignment:
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Raw:
    collectHIRExpressionIdentifiersExcept(statement.target, names, hiddenNames);
    collectHIRExpressionIdentifiersExcept(statement.value, names, hiddenNames);
    break;
  case HIRStatementKind::Block:
    collectHIRBlockExternalIdentifiers(statement.body, names, hiddenNames);
    break;
  case HIRStatementKind::If:
    collectHIRExpressionIdentifiersExcept(statement.value, names, hiddenNames);
    collectHIRBlockExternalIdentifiers(statement.body, names, hiddenNames);
    collectHIRBlockExternalIdentifiers(statement.elseBody, names, hiddenNames);
    break;
  case HIRStatementKind::For: {
    std::set<std::string> loopHiddenNames = hiddenNames;
    collectHIRBlockExternalIdentifiersInScope(statement.initializer, names,
                                             loopHiddenNames);
    collectHIRExpressionIdentifiersExcept(statement.value, names,
                                          loopHiddenNames);
    collectHIRBlockExternalIdentifiers(statement.update, names,
                                       loopHiddenNames);
    collectHIRBlockExternalIdentifiers(statement.body, names, loopHiddenNames);
    break;
  }
  }
}

void collectHIRBlockExternalIdentifiersInScope(
    std::span<const HIRStatement> statements, std::set<std::string> &names,
    std::set<std::string> &hiddenNames) {
  for (const HIRStatement &statement : statements) {
    collectHIRStatementExternalIdentifiers(statement, names, hiddenNames);
    if (statement.kind == HIRStatementKind::Declaration &&
        !statement.name.empty()) {
      hiddenNames.insert(statement.name);
    }
  }
}

void collectHIRBlockExternalIdentifiers(
    std::span<const HIRStatement> statements, std::set<std::string> &names,
    std::set<std::string> hiddenNames) {
  collectHIRBlockExternalIdentifiersInScope(statements, names, hiddenNames);
}

std::set<std::string> collectHIRCurrentScopeDeclarationNames(
    std::span<const HIRStatement> statements) {
  std::set<std::string> names;
  for (const HIRStatement &statement : statements) {
    if (statement.kind == HIRStatementKind::Declaration &&
        !statement.name.empty()) {
      names.insert(statement.name);
    }
  }
  return names;
}

void eraseHIRNames(std::set<std::string> &target,
                   const std::set<std::string> &names) {
  for (const std::string &name : names) {
    target.erase(name);
  }
}

bool cleanupDeadHIRLocalDeclarationsInBlock(
    std::vector<HIRStatement> &statements, std::set<std::string> liveNames,
    bool removeDeclarations);

bool cleanupDeadHIRLocalDeclarationsInStatement(HIRStatement &statement,
                                                std::set<std::string> liveNames,
                                                bool removeDeclarations) {
  bool changed = false;
  switch (statement.kind) {
  case HIRStatementKind::Block:
    changed =
        cleanupDeadHIRLocalDeclarationsInBlock(statement.body, liveNames,
                                               removeDeclarations) ||
        changed;
    return changed;
  case HIRStatementKind::If:
    changed =
        cleanupDeadHIRLocalDeclarationsInBlock(statement.body, liveNames,
                                               removeDeclarations) ||
        changed;
    changed =
        cleanupDeadHIRLocalDeclarationsInBlock(statement.elseBody, liveNames,
                                               removeDeclarations) ||
        changed;
    return changed;
  case HIRStatementKind::For:
    changed = cleanupDeadHIRLocalDeclarationsInBlock(statement.initializer,
                                                     liveNames, false) ||
              changed;
    changed =
        mutateHIRLoopUpdate(
            statement, [&](std::vector<HIRStatement> &update) {
              return cleanupDeadHIRLocalDeclarationsInBlock(update, liveNames,
                                                            false);
            }) ||
        changed;
    changed = cleanupDeadHIRLocalDeclarationsInBlock(statement.body, liveNames,
                                                     removeDeclarations) ||
              changed;
    return changed;
  case HIRStatementKind::Declaration:
  case HIRStatementKind::Assignment:
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Raw:
    return false;
  }
  return false;
}

bool cleanupDeadHIRLocalDeclarationsInBlock(
    std::vector<HIRStatement> &statements, std::set<std::string> liveNames,
    bool removeDeclarations) {
  bool changed = false;
  const std::set<std::string> currentScopeDeclarations =
      collectHIRCurrentScopeDeclarationNames(statements);
  eraseHIRNames(liveNames, currentScopeDeclarations);

  for (std::size_t index = statements.size(); index > 0; --index) {
    HIRStatement &statement = statements[index - 1];
    changed = cleanupDeadHIRLocalDeclarationsInStatement(
                  statement, liveNames, removeDeclarations) ||
              changed;

    if (removeDeclarations &&
        statement.kind == HIRStatementKind::Expression &&
        isKnownPureHIRStatement(statement)) {
      statements.erase(statements.begin() +
                       static_cast<std::ptrdiff_t>(index - 1));
      changed = true;
      continue;
    }

    if (statement.kind == HIRStatementKind::Declaration &&
        !statement.name.empty()) {
      const bool valueIsLive = liveNames.find(statement.name) !=
                               liveNames.end();
      liveNames.erase(statement.name);
      if (removeDeclarations && !valueIsLive &&
          isPureHIRDeadLocalInitializer(statement.value)) {
        statements.erase(statements.begin() +
                         static_cast<std::ptrdiff_t>(index - 1));
        changed = true;
        continue;
      }
      collectHIRExpressionIdentifiers(statement.value, liveNames);
      continue;
    }

    collectHIRStatementExternalIdentifiers(statement, liveNames, {});
  }
  return changed;
}

bool cleanupDeadHIRLocalDeclarations(HIRModule &module, DiagnosticEngine &) {
  bool changed = false;
  auto cleanupFunction = [&](HIRFunction &function) {
    if (containsOpaqueDeadLocalCleanupStatement(function.body)) {
      return;
    }
    changed =
        mutateHIRFunctionBody(
            function, [](std::vector<HIRStatement> &body) {
              return cleanupDeadHIRLocalDeclarationsInBlock(body, {}, true);
            }) ||
        changed;
  };

  for (HIRFunction &function : module.functions) {
    cleanupFunction(function);
  }
  for (HIRStage &stage : module.stages) {
    for (HIRFunction &function : stage.functions) {
      cleanupFunction(function);
    }
  }
  return changed;
}

bool hasHIRLocalDeclarations(std::span<const HIRStatement> statements) {
  for (const HIRStatement &statement : statements) {
    if (statement.kind == HIRStatementKind::Declaration &&
        !statement.name.empty()) {
      return true;
    }
    if (hasHIRLocalDeclarations(statement.initializer) ||
        hasHIRLocalDeclarations(statement.update) ||
        hasHIRLocalDeclarations(statement.body) ||
        hasHIRLocalDeclarations(statement.elseBody)) {
      return true;
    }
  }
  return false;
}

bool hasDuplicateHIRLocalDeclarationInAnyScope(
    std::span<const HIRStatement> statements) {
  std::set<std::string> currentScopeNames;
  for (const HIRStatement &statement : statements) {
    if (statement.kind == HIRStatementKind::Declaration &&
        !statement.name.empty() &&
        !currentScopeNames.insert(statement.name).second) {
      return true;
    }
  }

  for (const HIRStatement &statement : statements) {
    if (hasDuplicateHIRLocalDeclarationInAnyScope(statement.initializer) ||
        hasDuplicateHIRLocalDeclarationInAnyScope(statement.update) ||
        hasDuplicateHIRLocalDeclarationInAnyScope(statement.body) ||
        hasDuplicateHIRLocalDeclarationInAnyScope(statement.elseBody)) {
      return true;
    }
  }
  return false;
}

bool hasAmbiguousHIRLocalStoreCleanupDeclarations(
    const HIRFunction &function) {
  if (hasDuplicateHIRLocalDeclarationInAnyScope(function.body)) {
    return true;
  }
  return false;
}

struct HIRLocalStoreCleanupLiveness {
  std::set<std::size_t> liveBindings;
  std::set<std::string> liveExternalNames;
};

struct HIRLocalStoreCleanupResult {
  bool changed = false;
  HIRLocalStoreCleanupLiveness liveness;
};

using HIRVisibleLocalBindings =
    std::unordered_map<std::string, std::vector<std::size_t>>;
using HIRRewriteableLocalBindings = std::optional<std::set<std::size_t>>;

struct HIRForInitializerDeclarationBindings {
  HIRVisibleLocalBindings visibleBindings;
  std::vector<std::optional<std::size_t>> bindingByIndex;
};

void mergeHIRStoreCleanupLiveness(HIRLocalStoreCleanupLiveness &target,
                                  const HIRLocalStoreCleanupLiveness &source) {
  target.liveBindings.insert(source.liveBindings.begin(),
                             source.liveBindings.end());
  target.liveExternalNames.insert(source.liveExternalNames.begin(),
                                  source.liveExternalNames.end());
}

void pushHIRVisibleLocalBinding(HIRVisibleLocalBindings &visibleBindings,
                                const std::string &name,
                                std::size_t binding) {
  visibleBindings[name].push_back(binding);
}

void popHIRVisibleLocalBinding(HIRVisibleLocalBindings &visibleBindings,
                               const std::string &name,
                               std::size_t binding) {
  auto entry = visibleBindings.find(name);
  if (entry == visibleBindings.end()) {
    return;
  }

  std::vector<std::size_t> &stack = entry->second;
  if (!stack.empty() && stack.back() == binding) {
    stack.pop_back();
  } else {
    const auto found = std::find(stack.begin(), stack.end(), binding);
    if (found != stack.end()) {
      stack.erase(found);
    }
  }

  if (stack.empty()) {
    visibleBindings.erase(entry);
  }
}

std::optional<std::size_t>
resolveHIRVisibleLocalBinding(std::string_view name,
                              const HIRVisibleLocalBindings &visibleBindings) {
  const auto entry = visibleBindings.find(std::string(name));
  if (entry == visibleBindings.end() || entry->second.empty()) {
    return std::nullopt;
  }
  return entry->second.back();
}

std::optional<std::size_t> hirSimpleLocalAssignmentTargetBinding(
    const HIRExpression &target,
    const HIRVisibleLocalBindings &visibleBindings) {
  std::optional<std::string> name = hirSimpleIdentifierExpression(target);
  if (!name.has_value()) {
    return std::nullopt;
  }
  return resolveHIRVisibleLocalBinding(*name, visibleBindings);
}

bool isHIRLocalBindingRewriteable(
    const HIRRewriteableLocalBindings &rewriteableBindings,
    std::size_t binding) {
  return !rewriteableBindings.has_value() ||
         rewriteableBindings->find(binding) != rewriteableBindings->end();
}

HIRRewriteableLocalBindings collectHIRRewriteableVisibleLocalBindings(
    const HIRVisibleLocalBindings &visibleBindings,
    const HIRRewriteableLocalBindings &rewriteableBindings) {
  std::set<std::size_t> bindings;
  for (const auto &entry : visibleBindings) {
    for (std::size_t binding : entry.second) {
      if (isHIRLocalBindingRewriteable(rewriteableBindings, binding)) {
        bindings.insert(binding);
      }
    }
  }
  return HIRRewriteableLocalBindings{std::move(bindings)};
}

void collectHIRExpressionBindingReads(
    const HIRExpression &expression, HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    const std::set<std::string> &hiddenNames) {
  if (expression.kind == HIRExpressionKind::Identifier &&
      !expression.value.empty() &&
      !isHIRPseudoControlIdentifier(expression.value) &&
      hiddenNames.find(expression.value) == hiddenNames.end()) {
    if (std::optional<std::size_t> binding =
            resolveHIRVisibleLocalBinding(expression.value, visibleBindings)) {
      liveness.liveBindings.insert(*binding);
    } else {
      liveness.liveExternalNames.insert(expression.value);
    }
  }
  for (const HIRExpression &child : expression.children) {
    collectHIRExpressionBindingReads(child, liveness, visibleBindings,
                                     hiddenNames);
  }
}

void collectHIRAssignmentReadOperands(
    const HIRStatement &statement, HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    const std::set<std::string> &hiddenNames) {
  if (statement.target.kind != HIRExpressionKind::Identifier ||
      statement.target.value.empty()) {
    collectHIRExpressionBindingReads(statement.target, liveness,
                                     visibleBindings, hiddenNames);
  }
  collectHIRExpressionBindingReads(statement.value, liveness, visibleBindings,
                                   hiddenNames);
}

void collectHIRExpressionUpwardExposedBindingReads(
    const HIRExpression &expression, HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    const std::set<std::string> &hiddenNames,
    const std::set<std::size_t> &definitelyWrittenBindings) {
  if (expression.kind == HIRExpressionKind::Identifier &&
      !expression.value.empty() &&
      !isHIRPseudoControlIdentifier(expression.value) &&
      hiddenNames.find(expression.value) == hiddenNames.end()) {
    if (std::optional<std::size_t> binding =
            resolveHIRVisibleLocalBinding(expression.value, visibleBindings)) {
      if (definitelyWrittenBindings.find(*binding) ==
          definitelyWrittenBindings.end()) {
        liveness.liveBindings.insert(*binding);
      }
    } else {
      liveness.liveExternalNames.insert(expression.value);
    }
  }
  for (const HIRExpression &child : expression.children) {
    collectHIRExpressionUpwardExposedBindingReads(
        child, liveness, visibleBindings, hiddenNames,
        definitelyWrittenBindings);
  }
}

void collectHIRAssignmentUpwardExposedReadOperands(
    const HIRStatement &statement, HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    const std::set<std::string> &hiddenNames,
    std::set<std::size_t> &definitelyWrittenBindings) {
  if (std::optional<std::string> targetName =
          hirSimpleIdentifierExpression(statement.target)) {
    collectHIRExpressionUpwardExposedBindingReads(
        statement.value, liveness, visibleBindings, hiddenNames,
        definitelyWrittenBindings);
    if (hiddenNames.find(*targetName) == hiddenNames.end()) {
      if (std::optional<std::size_t> targetBinding =
              resolveHIRVisibleLocalBinding(*targetName, visibleBindings)) {
        definitelyWrittenBindings.insert(*targetBinding);
      }
    }
    return;
  }

  collectHIRExpressionUpwardExposedBindingReads(
      statement.target, liveness, visibleBindings, hiddenNames,
      definitelyWrittenBindings);
  collectHIRExpressionUpwardExposedBindingReads(
      statement.value, liveness, visibleBindings, hiddenNames,
      definitelyWrittenBindings);
}

std::set<std::size_t>
intersectHIRBindingSets(const std::set<std::size_t> &left,
                        const std::set<std::size_t> &right) {
  std::set<std::size_t> result;
  std::set_intersection(left.begin(), left.end(), right.begin(), right.end(),
                        std::inserter(result, result.end()));
  return result;
}

void collectHIRStoreCleanupBlockExternalReads(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> hiddenNames);

void collectHIRStoreCleanupBlockExternalReadsInScope(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> &hiddenNames);

void collectHIRStoreCleanupLoopUpdateReads(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> hiddenNames);

void collectHIRStoreCleanupLoopBodyReads(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> hiddenNames);

void collectHIRStoreCleanupLoopBodyReadsInScope(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> &hiddenNames);

void collectHIRStoreCleanupLoopContinuationReadsInScope(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> &hiddenNames,
    std::set<std::size_t> &definitelyWrittenBindings);

void collectHIRStoreCleanupLoopContinuationReads(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> hiddenNames,
    std::set<std::size_t> definitelyWrittenBindings);

void collectHIRStoreCleanupStatementExternalReads(
    const HIRStatement &statement, HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    const std::set<std::string> &hiddenNames) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    collectHIRExpressionBindingReads(statement.value, liveness,
                                     visibleBindings, hiddenNames);
    break;
  case HIRStatementKind::Assignment:
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Raw:
    collectHIRExpressionBindingReads(statement.target, liveness,
                                     visibleBindings, hiddenNames);
    collectHIRExpressionBindingReads(statement.value, liveness,
                                     visibleBindings, hiddenNames);
    break;
  case HIRStatementKind::Block:
    collectHIRStoreCleanupBlockExternalReads(statement.body, liveness,
                                             visibleBindings, hiddenNames);
    break;
  case HIRStatementKind::If:
    collectHIRExpressionBindingReads(statement.value, liveness,
                                     visibleBindings, hiddenNames);
    collectHIRStoreCleanupBlockExternalReads(statement.body, liveness,
                                             visibleBindings, hiddenNames);
    collectHIRStoreCleanupBlockExternalReads(statement.elseBody, liveness,
                                             visibleBindings, hiddenNames);
    break;
  case HIRStatementKind::For: {
    std::set<std::string> loopHiddenNames = hiddenNames;
    collectHIRStoreCleanupBlockExternalReadsInScope(
        statement.initializer, liveness, visibleBindings, loopHiddenNames);
    collectHIRExpressionBindingReads(statement.value, liveness,
                                     visibleBindings, loopHiddenNames);
    collectHIRStoreCleanupLoopUpdateReads(statement.update, liveness,
                                          visibleBindings, loopHiddenNames);
    collectHIRStoreCleanupBlockExternalReads(statement.body, liveness,
                                             visibleBindings,
                                             loopHiddenNames);
    break;
  }
  }
}

void collectHIRStoreCleanupLoopUpdateReads(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> hiddenNames) {
  for (const HIRStatement &statement : statements) {
    if (statement.kind == HIRStatementKind::Assignment) {
      collectHIRAssignmentReadOperands(statement, liveness, visibleBindings,
                                       hiddenNames);
      continue;
    }
    collectHIRStoreCleanupStatementExternalReads(statement, liveness,
                                                 visibleBindings, hiddenNames);
    if (statement.kind == HIRStatementKind::Declaration &&
        !statement.name.empty()) {
      hiddenNames.insert(statement.name);
    }
  }
}

void collectHIRStoreCleanupLoopBodyStatementReads(
    const HIRStatement &statement, HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    const std::set<std::string> &hiddenNames) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    collectHIRExpressionBindingReads(statement.value, liveness,
                                     visibleBindings, hiddenNames);
    break;
  case HIRStatementKind::Assignment:
    collectHIRAssignmentReadOperands(statement, liveness, visibleBindings,
                                     hiddenNames);
    break;
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Raw:
    collectHIRExpressionBindingReads(statement.target, liveness,
                                     visibleBindings, hiddenNames);
    collectHIRExpressionBindingReads(statement.value, liveness,
                                     visibleBindings, hiddenNames);
    break;
  case HIRStatementKind::Block:
    collectHIRStoreCleanupLoopBodyReads(statement.body, liveness,
                                        visibleBindings, hiddenNames);
    break;
  case HIRStatementKind::If:
    collectHIRExpressionBindingReads(statement.value, liveness,
                                     visibleBindings, hiddenNames);
    collectHIRStoreCleanupLoopBodyReads(statement.body, liveness,
                                        visibleBindings, hiddenNames);
    collectHIRStoreCleanupLoopBodyReads(statement.elseBody, liveness,
                                        visibleBindings, hiddenNames);
    break;
  case HIRStatementKind::For: {
    std::set<std::string> loopHiddenNames = hiddenNames;
    collectHIRStoreCleanupLoopBodyReadsInScope(
        statement.initializer, liveness, visibleBindings, loopHiddenNames);
    collectHIRExpressionBindingReads(statement.value, liveness,
                                     visibleBindings, loopHiddenNames);
    collectHIRStoreCleanupLoopUpdateReads(statement.update, liveness,
                                          visibleBindings, loopHiddenNames);
    collectHIRStoreCleanupLoopBodyReads(statement.body, liveness,
                                        visibleBindings, loopHiddenNames);
    break;
  }
  }
}

void collectHIRStoreCleanupLoopBodyReadsInScope(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> &hiddenNames) {
  for (const HIRStatement &statement : statements) {
    collectHIRStoreCleanupLoopBodyStatementReads(
        statement, liveness, visibleBindings, hiddenNames);
    if (statement.kind == HIRStatementKind::Declaration &&
        !statement.name.empty()) {
      hiddenNames.insert(statement.name);
    }
  }
}

void collectHIRStoreCleanupLoopBodyReads(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> hiddenNames) {
  collectHIRStoreCleanupLoopBodyReadsInScope(
      statements, liveness, visibleBindings, hiddenNames);
}

void collectHIRStoreCleanupLoopContinuationStatementReads(
    const HIRStatement &statement, HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    const std::set<std::string> &hiddenNames,
    std::set<std::size_t> &definitelyWrittenBindings) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    collectHIRExpressionUpwardExposedBindingReads(
        statement.value, liveness, visibleBindings, hiddenNames,
        definitelyWrittenBindings);
    break;
  case HIRStatementKind::Assignment:
    collectHIRAssignmentUpwardExposedReadOperands(
        statement, liveness, visibleBindings, hiddenNames,
        definitelyWrittenBindings);
    break;
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Raw:
    collectHIRExpressionUpwardExposedBindingReads(
        statement.target, liveness, visibleBindings, hiddenNames,
        definitelyWrittenBindings);
    collectHIRExpressionUpwardExposedBindingReads(
        statement.value, liveness, visibleBindings, hiddenNames,
        definitelyWrittenBindings);
    break;
  case HIRStatementKind::Block: {
    std::set<std::string> blockHiddenNames = hiddenNames;
    collectHIRStoreCleanupLoopContinuationReadsInScope(
        statement.body, liveness, visibleBindings, blockHiddenNames,
        definitelyWrittenBindings);
    break;
  }
  case HIRStatementKind::If: {
    collectHIRExpressionUpwardExposedBindingReads(
        statement.value, liveness, visibleBindings, hiddenNames,
        definitelyWrittenBindings);

    std::set<std::string> thenHiddenNames = hiddenNames;
    std::set<std::size_t> thenWrittenBindings = definitelyWrittenBindings;
    collectHIRStoreCleanupLoopContinuationReadsInScope(
        statement.body, liveness, visibleBindings, thenHiddenNames,
        thenWrittenBindings);

    std::set<std::string> elseHiddenNames = hiddenNames;
    std::set<std::size_t> elseWrittenBindings = definitelyWrittenBindings;
    collectHIRStoreCleanupLoopContinuationReadsInScope(
        statement.elseBody, liveness, visibleBindings, elseHiddenNames,
        elseWrittenBindings);

    definitelyWrittenBindings =
        intersectHIRBindingSets(thenWrittenBindings, elseWrittenBindings);
    break;
  }
  case HIRStatementKind::For: {
    std::set<std::string> loopHiddenNames = hiddenNames;
    collectHIRStoreCleanupLoopContinuationReadsInScope(
        statement.initializer, liveness, visibleBindings, loopHiddenNames,
        definitelyWrittenBindings);
    collectHIRExpressionUpwardExposedBindingReads(
        statement.value, liveness, visibleBindings, loopHiddenNames,
        definitelyWrittenBindings);

    std::set<std::string> nestedBodyHiddenNames = loopHiddenNames;
    std::set<std::size_t> nestedBodyWrittenBindings =
        definitelyWrittenBindings;
    collectHIRStoreCleanupLoopContinuationReadsInScope(
        statement.body, liveness, visibleBindings, nestedBodyHiddenNames,
        nestedBodyWrittenBindings);

    std::set<std::string> nestedUpdateHiddenNames = loopHiddenNames;
    std::set<std::size_t> nestedUpdateWrittenBindings =
        std::move(nestedBodyWrittenBindings);
    collectHIRStoreCleanupLoopContinuationReadsInScope(
        statement.update, liveness, visibleBindings, nestedUpdateHiddenNames,
        nestedUpdateWrittenBindings);
    break;
  }
  }
}

void collectHIRStoreCleanupLoopContinuationReadsInScope(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> &hiddenNames,
    std::set<std::size_t> &definitelyWrittenBindings) {
  for (const HIRStatement &statement : statements) {
    collectHIRStoreCleanupLoopContinuationStatementReads(
        statement, liveness, visibleBindings, hiddenNames,
        definitelyWrittenBindings);
    if (statement.kind == HIRStatementKind::Declaration &&
        !statement.name.empty()) {
      hiddenNames.insert(statement.name);
    }
  }
}

void collectHIRStoreCleanupLoopContinuationReads(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> hiddenNames,
    std::set<std::size_t> definitelyWrittenBindings) {
  collectHIRStoreCleanupLoopContinuationReadsInScope(
      statements, liveness, visibleBindings, hiddenNames,
      definitelyWrittenBindings);
}

void collectHIRStoreCleanupBlockExternalReadsInScope(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> &hiddenNames) {
  for (const HIRStatement &statement : statements) {
    collectHIRStoreCleanupStatementExternalReads(
        statement, liveness, visibleBindings, hiddenNames);
    if (statement.kind == HIRStatementKind::Declaration &&
        !statement.name.empty()) {
      hiddenNames.insert(statement.name);
    }
  }
}

void collectHIRStoreCleanupBlockExternalReads(
    std::span<const HIRStatement> statements,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::set<std::string> hiddenNames) {
  collectHIRStoreCleanupBlockExternalReadsInScope(
      statements, liveness, visibleBindings, hiddenNames);
}

void collectHIRStoreCleanupForLoopContinuationReads(
    const HIRStatement &statement, HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    const std::set<std::string> &hiddenNames) {
  collectHIRExpressionBindingReads(statement.value, liveness, visibleBindings,
                                   hiddenNames);
  collectHIRStoreCleanupLoopContinuationReads(statement.body, liveness,
                                              visibleBindings, hiddenNames, {});
}

bool hasHIRForInitializerDeclaration(const HIRStatement &statement) {
  return std::any_of(statement.initializer.begin(), statement.initializer.end(),
                     [](const HIRStatement &initializer) {
                       return initializer.kind == HIRStatementKind::Declaration;
                     });
}

HIRForInitializerDeclarationBindings bindHIRForInitializerDeclarationReads(
    const HIRStatement &statement, HIRVisibleLocalBindings visibleBindings,
    std::size_t &nextBinding) {
  HIRForInitializerDeclarationBindings result;
  result.visibleBindings = std::move(visibleBindings);
  result.bindingByIndex.resize(statement.initializer.size());

  for (std::size_t index = 0; index < statement.initializer.size(); ++index) {
    const HIRStatement &initializer = statement.initializer[index];
    if (initializer.kind != HIRStatementKind::Declaration ||
        initializer.name.empty()) {
      continue;
    }
    const std::size_t binding = nextBinding++;
    result.bindingByIndex[index] = binding;
    pushHIRVisibleLocalBinding(result.visibleBindings, initializer.name,
                               binding);
  }

  return result;
}

bool cleanupDeadHIRForInitializerDeclarationValues(
    std::vector<HIRStatement> &initializers,
    HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    const std::vector<std::optional<std::size_t>> &bindingByIndex) {
  bool changed = false;

  for (std::size_t index = initializers.size(); index > 0; --index) {
    HIRStatement &initializer = initializers[index - 1];
    if (initializer.kind != HIRStatementKind::Declaration) {
      collectHIRStoreCleanupStatementExternalReads(initializer, liveness,
                                                   visibleBindings, {});
      continue;
    }

    if (index - 1 >= bindingByIndex.size()) {
      collectHIRExpressionBindingReads(initializer.value, liveness,
                                       visibleBindings, {});
      continue;
    }

    const std::optional<std::size_t> binding = bindingByIndex[index - 1];
    if (!binding.has_value()) {
      collectHIRExpressionBindingReads(initializer.value, liveness,
                                       visibleBindings, {});
      continue;
    }

    const bool valueIsLive =
        liveness.liveBindings.find(*binding) != liveness.liveBindings.end();
    liveness.liveBindings.erase(*binding);
    if (!valueIsLive && !isEmptyHIRExpressionSlot(initializer.value) &&
        isPureHIRDeadLocalInitializer(initializer.value)) {
      initializer.value = HIRExpression{};
      changed = true;
      continue;
    }

    collectHIRExpressionBindingReads(initializer.value, liveness,
                                     visibleBindings, {});
  }

  return changed;
}

HIRLocalStoreCleanupResult cleanupDeadHIRLocalStoresInBlock(
    std::vector<HIRStatement> &statements,
    HIRLocalStoreCleanupLiveness liveness,
    HIRVisibleLocalBindings visibleBindings, std::size_t &nextBinding,
    bool rewriteDeclarations,
    HIRRewriteableLocalBindings rewriteableBindings = std::nullopt);

HIRLocalStoreCleanupResult cleanupDeadHIRLoopBodyStoresInBlock(
    HIRStatement &statement, HIRLocalStoreCleanupLiveness liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    const HIRVisibleLocalBindings &rewriteableVisibleBindings,
    std::size_t &nextBinding,
    const HIRRewriteableLocalBindings &rewriteableBindings) {
  collectHIRStoreCleanupLoopUpdateReads(statement.update, liveness,
                                        visibleBindings, {});
  collectHIRStoreCleanupForLoopContinuationReads(statement, liveness,
                                                 visibleBindings, {});
  return cleanupDeadHIRLocalStoresInBlock(
      statement.body, std::move(liveness), visibleBindings, nextBinding, true,
      collectHIRRewriteableVisibleLocalBindings(rewriteableVisibleBindings,
                                                rewriteableBindings));
}

HIRLocalStoreCleanupResult cleanupDeadHIRLoopUpdateStores(
    HIRStatement &statement, HIRLocalStoreCleanupLiveness liveness,
    HIRVisibleLocalBindings visibleBindings, std::size_t &nextBinding,
    HIRRewriteableLocalBindings rewriteableBindings) {
  HIRLocalStoreCleanupResult result;
  mutateHIRLoopUpdate(statement, [&](std::vector<HIRStatement> &update) {
    result = cleanupDeadHIRLocalStoresInBlock(
        update, std::move(liveness), std::move(visibleBindings), nextBinding,
        false, std::move(rewriteableBindings));
    return result.changed;
  });
  return result;
}

HIRLocalStoreCleanupResult cleanupDeadHIRLocalStoresInStatement(
    HIRStatement &statement, const HIRLocalStoreCleanupLiveness &liveness,
    const HIRVisibleLocalBindings &visibleBindings,
    std::size_t &nextBinding,
    const HIRRewriteableLocalBindings &rewriteableBindings) {
  switch (statement.kind) {
  case HIRStatementKind::Block:
    return cleanupDeadHIRLocalStoresInBlock(statement.body, liveness,
                                            visibleBindings, nextBinding,
                                            true, rewriteableBindings);
  case HIRStatementKind::If: {
    HIRLocalStoreCleanupResult thenResult =
        cleanupDeadHIRLocalStoresInBlock(statement.body, liveness,
                                         visibleBindings, nextBinding, true,
                                         rewriteableBindings);
    HIRLocalStoreCleanupResult elseResult =
        cleanupDeadHIRLocalStoresInBlock(statement.elseBody, liveness,
                                         visibleBindings, nextBinding, true,
                                         rewriteableBindings);
    HIRLocalStoreCleanupResult result;
    result.changed = thenResult.changed || elseResult.changed;
    mergeHIRStoreCleanupLiveness(result.liveness, thenResult.liveness);
    mergeHIRStoreCleanupLiveness(result.liveness, elseResult.liveness);
    collectHIRExpressionBindingReads(statement.value, result.liveness,
                                     visibleBindings, {});
    return result;
  }
  case HIRStatementKind::For: {
    if (hasHIRForInitializerDeclaration(statement)) {
      HIRForInitializerDeclarationBindings initializerBindings =
          bindHIRForInitializerDeclarationReads(statement, visibleBindings,
                                                nextBinding);
      HIRLocalStoreCleanupResult bodyLocalResult =
          cleanupDeadHIRLoopBodyStoresInBlock(
              statement, liveness, initializerBindings.visibleBindings,
              visibleBindings, nextBinding, rewriteableBindings);
      HIRLocalStoreCleanupLiveness updateExitLiveness = liveness;
      collectHIRStoreCleanupForLoopContinuationReads(
          statement, updateExitLiveness, initializerBindings.visibleBindings,
          {});
      HIRRewriteableLocalBindings updateRewriteableBindings =
          rewriteableBindings;
      if (updateRewriteableBindings.has_value()) {
        for (const std::optional<std::size_t> &binding :
             initializerBindings.bindingByIndex) {
          if (binding.has_value()) {
            updateRewriteableBindings->insert(*binding);
          }
        }
      }
      HIRLocalStoreCleanupResult updateResult =
          cleanupDeadHIRLoopUpdateStores(
              statement, std::move(updateExitLiveness),
              initializerBindings.visibleBindings, nextBinding,
              std::move(updateRewriteableBindings));
      HIRLocalStoreCleanupResult result{
          bodyLocalResult.changed || updateResult.changed,
          std::move(updateResult.liveness)};
      result.changed =
          cleanupDeadHIRForInitializerDeclarationValues(
              statement.initializer, result.liveness, visibleBindings,
              initializerBindings.bindingByIndex) ||
          result.changed;
      return result;
    }

    HIRLocalStoreCleanupResult bodyLocalResult =
        cleanupDeadHIRLoopBodyStoresInBlock(
            statement, liveness, visibleBindings, visibleBindings, nextBinding,
            rewriteableBindings);

    HIRLocalStoreCleanupLiveness updateExitLiveness = liveness;
    collectHIRStoreCleanupForLoopContinuationReads(
        statement, updateExitLiveness, visibleBindings, {});
    HIRLocalStoreCleanupResult updateResult = cleanupDeadHIRLoopUpdateStores(
        statement, std::move(updateExitLiveness), visibleBindings, nextBinding,
        rewriteableBindings);
    HIRLocalStoreCleanupResult initializerResult =
        cleanupDeadHIRLocalStoresInBlock(statement.initializer,
                                         std::move(updateResult.liveness),
                                         visibleBindings, nextBinding, false);
    initializerResult.changed =
        initializerResult.changed || bodyLocalResult.changed ||
        updateResult.changed;
    return initializerResult;
  }
  case HIRStatementKind::Declaration:
  case HIRStatementKind::Assignment:
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Raw:
    return HIRLocalStoreCleanupResult{false, liveness};
  }
  return HIRLocalStoreCleanupResult{false, liveness};
}

HIRLocalStoreCleanupResult cleanupDeadHIRLocalStoresInBlock(
    std::vector<HIRStatement> &statements,
    HIRLocalStoreCleanupLiveness liveness,
    HIRVisibleLocalBindings visibleBindings, std::size_t &nextBinding,
    bool rewriteDeclarations,
    HIRRewriteableLocalBindings rewriteableBindings) {
  bool changed = false;
  std::vector<std::optional<std::size_t>> localBindingByIndex(
      statements.size());
  for (std::size_t index = 0; index < statements.size(); ++index) {
    const HIRStatement &statement = statements[index];
    if (statement.kind == HIRStatementKind::Declaration &&
        !statement.name.empty()) {
      const std::size_t binding = nextBinding++;
      localBindingByIndex[index] = binding;
      pushHIRVisibleLocalBinding(visibleBindings, statement.name, binding);
      if (rewriteableBindings.has_value()) {
        rewriteableBindings->insert(binding);
      }
    }
  }

  for (std::size_t index = statements.size(); index > 0; --index) {
    HIRStatement &statement = statements[index - 1];
    HIRLocalStoreCleanupResult nestedResult =
        cleanupDeadHIRLocalStoresInStatement(statement, liveness,
                                             visibleBindings, nextBinding,
                                             rewriteableBindings);
    changed = nestedResult.changed || changed;

    switch (statement.kind) {
    case HIRStatementKind::Declaration: {
      const std::optional<std::size_t> binding =
          localBindingByIndex[index - 1];
      if (binding.has_value()) {
        const bool valueIsLive =
            liveness.liveBindings.find(*binding) !=
            liveness.liveBindings.end();
        const bool bindingIsRewriteable =
            isHIRLocalBindingRewriteable(rewriteableBindings, *binding);
        liveness.liveBindings.erase(*binding);
        popHIRVisibleLocalBinding(visibleBindings, statement.name, *binding);
        if (bindingIsRewriteable && rewriteDeclarations && !valueIsLive &&
            !isEmptyHIRExpressionSlot(statement.value) &&
            isPureHIRDeadLocalInitializer(statement.value)) {
          statement.value = HIRExpression{};
          changed = true;
          break;
        }
      }
      collectHIRExpressionBindingReads(statement.value, liveness,
                                       visibleBindings, {});
      break;
    }
    case HIRStatementKind::Assignment: {
      const std::optional<std::size_t> targetBinding =
          hirSimpleLocalAssignmentTargetBinding(statement.target,
                                                visibleBindings);
      if (targetBinding.has_value()) {
        if (!isHIRLocalBindingRewriteable(rewriteableBindings,
                                          *targetBinding)) {
          collectHIRExpressionBindingReads(statement.target, liveness,
                                           visibleBindings, {});
          collectHIRExpressionBindingReads(statement.value, liveness,
                                           visibleBindings, {});
          break;
        }
        const bool valueIsLive =
            liveness.liveBindings.find(*targetBinding) !=
            liveness.liveBindings.end();
        if (!valueIsLive && isPureHIRDeadLocalInitializer(statement.value)) {
          statements.erase(statements.begin() +
                           static_cast<std::ptrdiff_t>(index - 1));
          changed = true;
          continue;
        }
        liveness.liveBindings.erase(*targetBinding);
        collectHIRExpressionBindingReads(statement.value, liveness,
                                         visibleBindings, {});
        break;
      }
      collectHIRExpressionBindingReads(statement.target, liveness,
                                       visibleBindings, {});
      collectHIRExpressionBindingReads(statement.value, liveness,
                                       visibleBindings, {});
      break;
    }
    case HIRStatementKind::Block:
    case HIRStatementKind::If:
    case HIRStatementKind::For:
      liveness = std::move(nestedResult.liveness);
      break;
    case HIRStatementKind::Return:
    case HIRStatementKind::Expression:
    case HIRStatementKind::Break:
    case HIRStatementKind::Continue:
    case HIRStatementKind::Discard:
    case HIRStatementKind::Raw:
      collectHIRStoreCleanupStatementExternalReads(statement, liveness,
                                                   visibleBindings, {});
      break;
    }
  }
  return HIRLocalStoreCleanupResult{changed, std::move(liveness)};
}

bool cleanupDeadHIRLocalStoresOnce(HIRModule &module) {
  bool changed = false;
  auto cleanupFunction = [&](HIRFunction &function) {
    if (containsOpaqueDeadLocalCleanupStatement(function.body)) {
      return;
    }
    if (!hasHIRLocalDeclarations(function.body) ||
        hasAmbiguousHIRLocalStoreCleanupDeclarations(function)) {
      return;
    }
    HIRLocalStoreCleanupLiveness liveness;
    HIRVisibleLocalBindings visibleBindings;
    std::size_t nextBinding = 0;
    HIRLocalStoreCleanupResult result;
    mutateHIRFunctionBody(function, [&](std::vector<HIRStatement> &body) {
      result = cleanupDeadHIRLocalStoresInBlock(
          body, liveness, visibleBindings, nextBinding, true);
      return result.changed;
    });
    changed = result.changed || changed;
  };

  for (HIRFunction &function : module.functions) {
    cleanupFunction(function);
  }
  for (HIRStage &stage : module.stages) {
    for (HIRFunction &function : stage.functions) {
      cleanupFunction(function);
    }
  }
  return changed;
}

bool cleanupDeadHIRLocalStores(HIRModule &module,
                               DiagnosticEngine &diagnostics) {
  bool changed = cleanupDeadHIRLocalStoresOnce(module);
  if (!changed) {
    return false;
  }

  for (;;) {
    const bool declarationsChanged =
        cleanupDeadHIRLocalDeclarations(module, diagnostics);
    const bool storesChanged = cleanupDeadHIRLocalStoresOnce(module);
    changed = declarationsChanged || storesChanged || changed;
    if (!declarationsChanged && !storesChanged) {
      break;
    }
  }
  return changed;
}

bool hirExpressionTypeCanReplaceParent(const HIRExpression &parent,
                                        const HIRExpression &replacement);

bool isLiteralOnlyHIRTemporaryValue(const HIRExpression &expression) {
  switch (expression.kind) {
  case HIRExpressionKind::Literal:
    return expression.children.empty();
  case HIRExpressionKind::Group:
  case HIRExpressionKind::Constructor:
    return std::all_of(expression.children.begin(), expression.children.end(),
                       isLiteralOnlyHIRTemporaryValue);
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::MemberAccess:
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::Call:
  case HIRExpressionKind::Unary:
  case HIRExpressionKind::Binary:
  case HIRExpressionKind::Select:
  case HIRExpressionKind::TextureSample:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    return false;
  }
  return false;
}

bool isO2InlineableLiteralVectorTemporary(const HIRStatement &statement) {
  return statement.kind == HIRStatementKind::Declaration &&
         !statement.name.empty() &&
         isFoldableHIRVectorType(statement.declaredType) &&
         !isEmptyHIRExpressionSlot(statement.value) &&
         isKnownPureHIRExpression(statement.value) &&
         isLiteralOnlyHIRTemporaryValue(statement.value);
}

bool isO2ScalarTemporaryType(const HIRType &type) {
  if (!hasHIRTypeShape(type) || type.arraySize.has_value()) {
    return false;
  }
  const std::string unqualified = stripTypeQualifier(type.name);
  if (!unqualified.empty() && unqualified.back() == '*') {
    return false;
  }
  if (resourceKindFromName(type.name) != HIRResourceKind::Value) {
    return false;
  }
  const std::string base = baseTypeName(type);
  return base == "bool" || isNumericScalarTypeName(base);
}

bool isO2ScalarTemporaryExpressionType(const HIRExpression &expression) {
  return !hasHIRTypeShape(expression.type) ||
         isO2ScalarTemporaryType(expression.type);
}

bool collectO2ScalarTemporaryInitializerReads(
    const HIRExpression &expression, std::set<std::string> &readNames) {
  if (!isO2ScalarTemporaryExpressionType(expression)) {
    return false;
  }

  switch (expression.kind) {
  case HIRExpressionKind::Literal:
    return expression.children.empty();
  case HIRExpressionKind::Identifier:
    if (expression.value.empty() || !expression.children.empty() ||
        !isO2ScalarTemporaryType(expression.type)) {
      return false;
    }
    readNames.insert(expression.value);
    return true;
  case HIRExpressionKind::Group:
    return expression.children.size() == 1 &&
           collectO2ScalarTemporaryInitializerReads(expression.children.front(),
                                                    readNames);
  case HIRExpressionKind::Unary:
    return expression.children.size() == 1 &&
           collectO2ScalarTemporaryInitializerReads(expression.children.front(),
                                                    readNames);
  case HIRExpressionKind::Binary:
    return expression.children.size() == 2 &&
           collectO2ScalarTemporaryInitializerReads(expression.children[0],
                                                    readNames) &&
           collectO2ScalarTemporaryInitializerReads(expression.children[1],
                                                    readNames);
  case HIRExpressionKind::Select:
    return expression.children.size() == 3 &&
           collectO2ScalarTemporaryInitializerReads(expression.children[0],
                                                    readNames) &&
           collectO2ScalarTemporaryInitializerReads(expression.children[1],
                                                    readNames) &&
           collectO2ScalarTemporaryInitializerReads(expression.children[2],
                                                    readNames);
  case HIRExpressionKind::Constructor:
    for (const HIRExpression &child : expression.children) {
      if (!collectO2ScalarTemporaryInitializerReads(child, readNames)) {
        return false;
      }
    }
    return true;
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::MemberAccess:
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::Call:
  case HIRExpressionKind::TextureSample:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    return false;
  }
  return false;
}

bool isO2InlineableScalarTemporary(const HIRStatement &statement,
                                   std::set<std::string> &initializerReads) {
  initializerReads.clear();
  return statement.kind == HIRStatementKind::Declaration &&
         !statement.name.empty() &&
         isO2ScalarTemporaryType(statement.declaredType) &&
         !isEmptyHIRExpressionSlot(statement.value) &&
         isO2ScalarTemporaryType(statement.value.type) &&
         isKnownPureHIRExpression(statement.value) &&
         collectO2ScalarTemporaryInitializerReads(statement.value,
                                                  initializerReads) &&
         initializerReads.find(statement.name) == initializerReads.end();
}

std::size_t countHIRIdentifierReads(const HIRExpression &expression,
                                    std::string_view name) {
  std::size_t count = 0;
  if (expression.kind == HIRExpressionKind::Identifier &&
      expression.value == name && expression.children.empty()) {
    ++count;
  }
  for (const HIRExpression &child : expression.children) {
    count += countHIRIdentifierReads(child, name);
  }
  return count;
}

bool replaceSingleHIRIdentifierRead(HIRExpression &expression,
                                    std::string_view name,
                                    const HIRExpression &replacement) {
  if (expression.kind == HIRExpressionKind::Identifier &&
      expression.value == name && expression.children.empty() &&
      hirExpressionTypeCanReplaceParent(expression, replacement)) {
    HIRExpression newExpression = replacement;
    newExpression.location = expression.location.file.empty()
                                 ? replacement.location
                                 : expression.location;
    expression = std::move(newExpression);
    return true;
  }

  for (HIRExpression &child : expression.children) {
    if (replaceSingleHIRIdentifierRead(child, name, replacement)) {
      return true;
    }
  }
  return false;
}

std::size_t countDirectHIRStatementValueReads(const HIRStatement &statement,
                                              std::string_view name) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
  case HIRStatementKind::Assignment:
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
  case HIRStatementKind::If:
  case HIRStatementKind::For:
    return countHIRIdentifierReads(statement.value, name);
  case HIRStatementKind::Block:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Raw:
    return 0;
  }
  return 0;
}

bool replaceDirectHIRStatementValueRead(HIRStatement &statement,
                                        std::string_view name,
                                        const HIRExpression &replacement) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
  case HIRStatementKind::Assignment:
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
  case HIRStatementKind::If:
  case HIRStatementKind::For:
    return replaceSingleHIRIdentifierRead(statement.value, name, replacement);
  case HIRStatementKind::Block:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Raw:
    return false;
  }
  return false;
}

bool containsHIRNestedContainerIdentifierRead(const HIRStatement &statement,
                                              std::string_view name) {
  auto blockContainsRead = [&](std::span<const HIRStatement> statements) {
    for (const HIRStatement &child : statements) {
      if (countHIRIdentifierReads(child.target, name) != 0 ||
          countHIRIdentifierReads(child.value, name) != 0 ||
          containsHIRNestedContainerIdentifierRead(child, name)) {
        return true;
      }
    }
    return false;
  };

  return blockContainsRead(statement.initializer) ||
         blockContainsRead(statement.update) ||
         blockContainsRead(statement.body) ||
         blockContainsRead(statement.elseBody);
}

std::size_t
countHIRCurrentScopeDeclarations(std::span<const HIRStatement> statements,
                                 std::string_view name) {
  std::size_t count = 0;
  for (const HIRStatement &statement : statements) {
    if (statement.kind == HIRStatementKind::Declaration &&
        statement.name == name) {
      ++count;
    }
  }
  return count;
}

bool inlineO2LiteralVectorTemporariesInBlock(
    std::vector<HIRStatement> &statements);

bool inlineO2LiteralVectorTemporariesInStatement(HIRStatement &statement) {
  bool changed = false;
  switch (statement.kind) {
  case HIRStatementKind::Block:
    changed =
        inlineO2LiteralVectorTemporariesInBlock(statement.body) || changed;
    return changed;
  case HIRStatementKind::If:
    changed =
        inlineO2LiteralVectorTemporariesInBlock(statement.body) || changed;
    changed =
        inlineO2LiteralVectorTemporariesInBlock(statement.elseBody) || changed;
    return changed;
  case HIRStatementKind::For:
    changed = inlineO2LiteralVectorTemporariesInBlock(statement.initializer) ||
              changed;
    changed =
        mutateHIRLoopUpdate(
            statement, [](std::vector<HIRStatement> &update) {
              return inlineO2LiteralVectorTemporariesInBlock(update);
            }) ||
        changed;
    changed =
        inlineO2LiteralVectorTemporariesInBlock(statement.body) || changed;
    return changed;
  case HIRStatementKind::Declaration:
  case HIRStatementKind::Assignment:
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Raw:
    return false;
  }
  return false;
}

bool inlineO2LiteralVectorTemporariesInBlock(
    std::vector<HIRStatement> &statements) {
  bool changed = false;
  for (HIRStatement &statement : statements) {
    changed = inlineO2LiteralVectorTemporariesInStatement(statement) ||
              changed;
  }

  for (std::size_t index = 0; index < statements.size();) {
    HIRStatement &candidate = statements[index];
    if (!isO2InlineableLiteralVectorTemporary(candidate) ||
        countHIRCurrentScopeDeclarations(statements, candidate.name) != 1) {
      ++index;
      continue;
    }

    std::set<std::string> assignedNames;
    std::size_t directReads = 0;
    bool hasNestedRead = false;
    for (std::size_t useIndex = index + 1; useIndex < statements.size();
         ++useIndex) {
      collectHIRAssignedNames(statements[useIndex], assignedNames);
      directReads +=
          countDirectHIRStatementValueReads(statements[useIndex],
                                            candidate.name);
      hasNestedRead = containsHIRNestedContainerIdentifierRead(
                          statements[useIndex], candidate.name) ||
                      hasNestedRead;
    }

    if (assignedNames.find(candidate.name) != assignedNames.end() ||
        directReads != 1 || hasNestedRead) {
      ++index;
      continue;
    }

    HIRExpression replacement = candidate.value;
    bool replaced = false;
    for (std::size_t useIndex = index + 1; useIndex < statements.size();
         ++useIndex) {
      if (replaceDirectHIRStatementValueRead(statements[useIndex],
                                            candidate.name, replacement)) {
        replaced = true;
        break;
      }
    }

    if (!replaced) {
      ++index;
      continue;
    }

    statements.erase(statements.begin() + static_cast<std::ptrdiff_t>(index));
    changed = true;
  }
  return changed;
}

bool inlineO2LiteralVectorTemporaries(HIRModule &module, DiagnosticEngine &) {
  bool changed = false;
  auto optimizeFunction = [&](HIRFunction &function) {
    if (containsOpaqueDeadLocalCleanupStatement(function.body)) {
      return;
    }
    changed =
        mutateHIRFunctionBody(function,
                              inlineO2LiteralVectorTemporariesInBlock) ||
        changed;
  };

  for (HIRFunction &function : module.functions) {
    optimizeFunction(function);
  }
  for (HIRStage &stage : module.stages) {
    for (HIRFunction &function : stage.functions) {
      optimizeFunction(function);
    }
  }
  return changed;
}

bool hasAnyHIRName(const std::set<std::string> &names,
                   const std::set<std::string> &candidates) {
  for (const std::string &name : candidates) {
    if (names.find(name) != names.end()) {
      return true;
    }
  }
  return false;
}

bool inlineO2ScalarTemporariesInBlock(std::vector<HIRStatement> &statements);

bool inlineO2ScalarTemporariesInStatement(HIRStatement &statement) {
  bool changed = false;
  switch (statement.kind) {
  case HIRStatementKind::Block:
    changed = inlineO2ScalarTemporariesInBlock(statement.body) || changed;
    return changed;
  case HIRStatementKind::If:
    changed = inlineO2ScalarTemporariesInBlock(statement.body) || changed;
    changed = inlineO2ScalarTemporariesInBlock(statement.elseBody) || changed;
    return changed;
  case HIRStatementKind::For:
    changed =
        inlineO2ScalarTemporariesInBlock(statement.initializer) || changed;
    changed =
        mutateHIRLoopUpdate(statement, [](std::vector<HIRStatement> &update) {
          return inlineO2ScalarTemporariesInBlock(update);
        }) ||
        changed;
    changed = inlineO2ScalarTemporariesInBlock(statement.body) || changed;
    return changed;
  case HIRStatementKind::Declaration:
  case HIRStatementKind::Assignment:
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Raw:
    return false;
  }
  return false;
}

bool inlineO2ScalarTemporariesInBlock(std::vector<HIRStatement> &statements) {
  bool changed = false;
  for (HIRStatement &statement : statements) {
    changed = inlineO2ScalarTemporariesInStatement(statement) || changed;
  }

  for (std::size_t index = 0; index < statements.size();) {
    HIRStatement &candidate = statements[index];
    std::set<std::string> initializerReads;
    if (!isO2InlineableScalarTemporary(candidate, initializerReads) ||
        countHIRCurrentScopeDeclarations(statements, candidate.name) != 1) {
      ++index;
      continue;
    }

    std::set<std::string> assignedNames;
    std::set<std::string> declaredNames;
    std::size_t directReads = 0;
    bool hasNestedRead = false;
    for (std::size_t useIndex = index + 1; useIndex < statements.size();
         ++useIndex) {
      collectHIRAssignedNames(statements[useIndex], assignedNames);
      collectHIRDeclaredNames(statements[useIndex], declaredNames);
      directReads +=
          countDirectHIRStatementValueReads(statements[useIndex],
                                            candidate.name);
      hasNestedRead = containsHIRNestedContainerIdentifierRead(
                          statements[useIndex], candidate.name) ||
                      hasNestedRead;
    }

    if (assignedNames.find(candidate.name) != assignedNames.end() ||
        directReads != 1 || hasNestedRead ||
        hasAnyHIRName(assignedNames, initializerReads) ||
        hasAnyHIRName(declaredNames, initializerReads)) {
      ++index;
      continue;
    }

    HIRExpression replacement = candidate.value;
    bool replaced = false;
    for (std::size_t useIndex = index + 1; useIndex < statements.size();
         ++useIndex) {
      if (replaceDirectHIRStatementValueRead(statements[useIndex],
                                            candidate.name, replacement)) {
        replaced = true;
        break;
      }
    }

    if (!replaced) {
      ++index;
      continue;
    }

    statements.erase(statements.begin() + static_cast<std::ptrdiff_t>(index));
    changed = true;
  }
  return changed;
}

bool inlineO2ScalarTemporaries(HIRModule &module, DiagnosticEngine &) {
  bool changed = false;
  auto optimizeFunction = [&](HIRFunction &function) {
    if (containsOpaqueDeadLocalCleanupStatement(function.body)) {
      return;
    }
    changed =
        mutateHIRFunctionBody(function, inlineO2ScalarTemporariesInBlock) ||
        changed;
  };

  for (HIRFunction &function : module.functions) {
    optimizeFunction(function);
  }
  for (HIRStage &stage : module.stages) {
    for (HIRFunction &function : stage.functions) {
      optimizeFunction(function);
    }
  }
  return changed;
}

bool isFoldableHIRExpressionMaterializationCandidate(
    HIRExpressionKind kind) {
  switch (kind) {
  case HIRExpressionKind::Call:
  case HIRExpressionKind::Unary:
  case HIRExpressionKind::Binary:
  case HIRExpressionKind::Select:
  case HIRExpressionKind::MemberAccess:
    return true;
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::Literal:
  case HIRExpressionKind::Group:
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::Constructor:
  case HIRExpressionKind::TextureSample:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    return false;
  }
  return false;
}

std::optional<bool> foldedHIRConditionValue(const HIRExpression &condition,
                                            HIRFoldContext &context) {
  HIRScalarFoldOptions options;
  options.foldIntrinsicCalls = true;
  const std::optional<FoldedHIRScalar> folded =
      foldHIRScalarExpression(condition, context.scalarConstants, options,
                              &context.valueConstants);
  if (!folded.has_value()) {
    return std::nullopt;
  }
  return folded->isBool ? folded->boolean : folded->number != 0.0;
}

bool materializeFoldedHIRCondition(HIRExpression &condition,
                                   HIRFoldContext &context) {
  const std::optional<bool> folded = foldedHIRConditionValue(condition, context);
  if (!folded.has_value()) {
    return false;
  }
  if (condition.kind == HIRExpressionKind::Literal &&
      baseTypeName(condition.type) == "bool" &&
      !condition.type.arraySize.has_value() &&
      condition.value == (*folded ? "true" : "false") &&
      condition.children.empty()) {
    return false;
  }
  condition = makeHIRBoolLiteral(*folded, condition.location);
  return true;
}

bool canWrapFoldedHIRSelectArmInConstructor(const HIRType &target,
                                            const HIRType &source) {
  return !target.arraySize.has_value() && !source.arraySize.has_value() &&
         isNumericScalarTypeName(target.name) &&
         isNumericScalarTypeName(source.name);
}

HIRExpression groupedHIRPreservedReplacement(HIRExpression expression);

std::optional<HIRExpression>
prunedFoldedHIRSelectReplacement(HIRExpression &expression, bool condition) {
  const std::size_t selectedIndex = condition ? 1 : 2;
  if (expression.children.size() <= selectedIndex) {
    return std::nullopt;
  }

  const HIRType selectType = expression.type;
  const SourceLocation selectLocation = expression.location;
  const HIRExpression &selected = expression.children[selectedIndex];
  if (!hasHIRTypeShape(selectType) || sameType(selected.type, selectType)) {
    HIRExpression replacement =
        groupedHIRPreservedReplacement(expression.children[selectedIndex]);
    if (!hirExpressionTypeCanReplaceParent(expression, replacement)) {
      return std::nullopt;
    }
    return replacement;
  }

  if (!canWrapFoldedHIRSelectArmInConstructor(selectType, selected.type)) {
    return std::nullopt;
  }

  HIRExpression replacement;
  replacement.kind = HIRExpressionKind::Constructor;
  replacement.value = selectType.name;
  replacement.type = selectType;
  replacement.location = selectLocation;
  replacement.children.push_back(std::move(expression.children[selectedIndex]));
  return replacement;
}

std::optional<HIRExpression>
foldedHIRIndexOperandLiteral(const HIRExpression &expression,
                             HIRFoldContext &context) {
  if (context.globalScalarConstants == nullptr) {
    return std::nullopt;
  }

  HIRScalarFoldOptions options;
  options.foldIntrinsicCalls = true;
  const HIRValueConstantMap *valueConstants = context.globalValueConstants;
  const std::optional<std::string> foldedText = foldHIRIntegerIndexExpression(
      expression, *context.globalScalarConstants, options, valueConstants);
  if (!foldedText.has_value()) {
    return std::nullopt;
  }

  if (expression.kind == HIRExpressionKind::Literal &&
      expression.value == *foldedText && expression.children.empty()) {
    return std::nullopt;
  }

  HIRExpression literal;
  literal.kind = HIRExpressionKind::Literal;
  literal.type = expression.type;
  literal.value = *foldedText;
  literal.location = expression.location;
  return literal;
}

bool materializeFoldedHIRIndexOperand(HIRExpression &expression,
                                      HIRFoldContext &context);

bool canonicalizeFoldedHIRIndexOperands(HIRExpression &expression,
                                        HIRFoldContext &context) {
  bool changed = false;
  if (expression.kind == HIRExpressionKind::IndexAccess &&
      expression.children.size() >= 2) {
    changed =
        canonicalizeFoldedHIRIndexOperands(expression.children[0], context) ||
        changed;
    changed =
        materializeFoldedHIRIndexOperand(expression.children[1], context) ||
        changed;
    for (std::size_t index = 2; index < expression.children.size(); ++index) {
      changed =
          canonicalizeFoldedHIRIndexOperands(expression.children[index],
                                             context) ||
          changed;
    }
    return changed;
  }

  for (HIRExpression &child : expression.children) {
    changed = canonicalizeFoldedHIRIndexOperands(child, context) || changed;
  }
  return changed;
}

bool materializeFoldedHIRIndexOperand(HIRExpression &expression,
                                      HIRFoldContext &context) {
  bool changed = false;
  if (expression.kind == HIRExpressionKind::NonUniform) {
    for (HIRExpression &child : expression.children) {
      changed = materializeFoldedHIRIndexOperand(child, context) || changed;
    }
    return changed;
  }

  changed = canonicalizeFoldedHIRIndexOperands(expression, context) || changed;
  if (std::optional<HIRExpression> folded =
          foldedHIRIndexOperandLiteral(expression, context)) {
    expression = std::move(*folded);
    return true;
  }
  return changed;
}

bool foldConstantHIRIntrinsicExpression(
    HIRExpression &expression, HIRFoldContext &context) {
  if (expression.kind == HIRExpressionKind::TextureCompareLodManual) {
    return canonicalizeFoldedHIRIndexOperands(expression, context);
  }

  bool changed = false;
  for (HIRExpression &child : expression.children) {
    changed = foldConstantHIRIntrinsicExpression(child, context) || changed;
  }
  if (expression.kind == HIRExpressionKind::IndexAccess &&
      expression.children.size() >= 2) {
    changed =
        materializeFoldedHIRIndexOperand(expression.children[1], context) ||
        changed;
  }

  HIRScalarFoldOptions options;
  options.foldIntrinsicCalls = true;
  if (isFoldableHIRExpressionMaterializationCandidate(expression.kind)) {
    const std::optional<FoldedHIRValue> folded =
        foldHIRValueExpression(expression, context.scalarConstants, options,
                               &context.valueConstants);
    if (folded.has_value()) {
      std::optional<HIRExpression> foldedExpression =
          foldedHIRValueToExpression(*folded, expression.type,
                                     expression.location);
      if (foldedExpression.has_value()) {
        expression = std::move(*foldedExpression);
        return true;
      }
    }
  }

  if (expression.kind == HIRExpressionKind::Select &&
      expression.children.size() >= 3) {
    const std::optional<bool> condition =
        foldedHIRConditionValue(expression.children[0], context);
    if (condition.has_value()) {
      std::optional<HIRExpression> replacement =
          prunedFoldedHIRSelectReplacement(expression, *condition);
      if (replacement.has_value()) {
        expression = std::move(*replacement);
        return true;
      }
    }
  }

  return changed;
}

bool foldConstantHIRAssignmentTargetExpression(HIRExpression &expression,
                                               HIRFoldContext &context) {
  if (expression.kind == HIRExpressionKind::TextureCompareLodManual) {
    return false;
  }

  bool changed = false;
  switch (expression.kind) {
  case HIRExpressionKind::Group:
  case HIRExpressionKind::MemberAccess:
  case HIRExpressionKind::NonUniform:
    if (!expression.children.empty()) {
      changed = foldConstantHIRAssignmentTargetExpression(
                    expression.children.front(), context) ||
                changed;
    }
    for (std::size_t index = 1; index < expression.children.size(); ++index) {
      changed =
          foldConstantHIRIntrinsicExpression(expression.children[index],
                                             context) ||
          changed;
    }
    return changed;
  case HIRExpressionKind::IndexAccess:
    if (!expression.children.empty()) {
      changed = foldConstantHIRAssignmentTargetExpression(
                    expression.children.front(), context) ||
                changed;
    }
    for (std::size_t index = 1; index < expression.children.size(); ++index) {
      changed =
          foldConstantHIRIntrinsicExpression(expression.children[index],
                                             context) ||
          changed;
    }
    return changed;
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::Literal:
  case HIRExpressionKind::Call:
  case HIRExpressionKind::Constructor:
  case HIRExpressionKind::Unary:
  case HIRExpressionKind::Binary:
  case HIRExpressionKind::Select:
  case HIRExpressionKind::TextureSample:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    for (HIRExpression &child : expression.children) {
      changed = foldConstantHIRIntrinsicExpression(child, context) || changed;
    }
    return changed;
  }
  return changed;
}

bool foldConstantHIRIntrinsicStatement(
    HIRStatement &statement, HIRFoldContext &context);

bool foldConstantHIRIntrinsicBlock(std::vector<HIRStatement> &statements,
                                   HIRFoldContext &context) {
  bool changed = false;
  for (HIRStatement &statement : statements) {
    changed = foldConstantHIRIntrinsicStatement(statement, context) || changed;
  }
  return changed;
}

bool foldConstantHIRIntrinsicScopedBlock(std::vector<HIRStatement> &statements,
                                         HIRFoldContext context) {
  return foldConstantHIRIntrinsicBlock(statements, context);
}

bool foldConstantHIRIntrinsicStatement(HIRStatement &statement,
                                       HIRFoldContext &context) {
  bool changed = false;

  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    changed = foldConstantHIRIntrinsicExpression(statement.value, context) ||
              changed;
    rememberFoldedHIRDeclaration(context, statement.name,
                                 statement.declaredType, statement.value);
    return changed;
  case HIRStatementKind::Assignment: {
    changed =
        foldConstantHIRAssignmentTargetExpression(statement.target, context) ||
        changed;
    changed = foldConstantHIRIntrinsicExpression(statement.value, context) ||
              changed;
    if (std::optional<std::string> name =
            hirSimpleIdentifierExpression(statement.target)) {
      rememberFoldedHIRDeclaration(context, *name, statement.target.type,
                                   statement.value);
      return changed;
    }
    if (std::optional<std::string> name =
            hirExpressionRootIdentifier(statement.target)) {
      eraseHIRFoldedName(context, *name);
    }
    return changed;
  }
  case HIRStatementKind::Block: {
    const bool blockHasRaw = containsRawHIRStatement(statement.body);
    changed =
        foldConstantHIRIntrinsicScopedBlock(statement.body, context) || changed;
    if (blockHasRaw) {
      clearHIRLocalFoldedValues(context);
      return changed;
    }
    std::set<std::string> assignedNames;
    for (const HIRStatement &child : statement.body) {
      collectHIRAssignedNames(child, assignedNames);
    }
    for (const std::string &name : assignedNames) {
      eraseHIRFoldedName(context, name);
    }
    return changed;
  }
  case HIRStatementKind::If: {
    changed = foldConstantHIRIntrinsicExpression(statement.value, context) ||
              changed;
    changed = materializeFoldedHIRCondition(statement.value, context) ||
              changed;
    const bool thenHasRaw = containsRawHIRStatement(statement.body);
    const bool elseHasRaw = containsRawHIRStatement(statement.elseBody);
    changed = foldConstantHIRIntrinsicScopedBlock(statement.body, context) ||
              changed;
    changed = foldConstantHIRIntrinsicScopedBlock(statement.elseBody, context) ||
              changed;
    if (thenHasRaw || elseHasRaw) {
      clearHIRLocalFoldedValues(context);
      return changed;
    }
    std::set<std::string> assignedNames;
    for (const HIRStatement &child : statement.body) {
      collectHIRAssignedNames(child, assignedNames);
    }
    for (const HIRStatement &child : statement.elseBody) {
      collectHIRAssignedNames(child, assignedNames);
    }
    for (const std::string &name : assignedNames) {
      eraseHIRFoldedName(context, name);
    }
    return changed;
  }
  case HIRStatementKind::For: {
    const bool loopHasRaw = containsRawHIRStatement(statement.initializer) ||
                            containsRawHIRStatement(statement.update) ||
                            containsRawHIRStatement(statement.body) ||
                            (!statement.updateTokens.empty() &&
                             statement.update.empty());
    HIRFoldContext loopContext = context;
    changed =
        foldConstantHIRIntrinsicBlock(statement.initializer, loopContext) ||
        changed;

    std::set<std::string> loopCarriedNames;
    for (const HIRStatement &update : statement.update) {
      collectHIRAssignedNames(update, loopCarriedNames);
    }
    for (const HIRStatement &child : statement.body) {
      collectHIRAssignedNames(child, loopCarriedNames);
    }
    for (const std::string &name : loopCarriedNames) {
      eraseHIRFoldedName(loopContext, name);
    }
    if (loopHasRaw) {
      clearHIRLocalFoldedValues(loopContext);
    }

    changed = foldConstantHIRIntrinsicExpression(statement.value, loopContext) ||
              changed;
    const bool updateChanged =
        mutateHIRLoopUpdate(statement, [&](std::vector<HIRStatement> &update) {
          return foldConstantHIRIntrinsicBlock(update, loopContext);
        });
    changed = updateChanged || changed;
    changed = foldConstantHIRIntrinsicScopedBlock(statement.body, loopContext) ||
              changed;
    if (loopHasRaw) {
      clearHIRLocalFoldedValues(context);
      return changed;
    }
    std::set<std::string> assignedNames;
    for (const HIRStatement &initializer : statement.initializer) {
      collectHIRAssignedNames(initializer, assignedNames);
    }
    for (const HIRStatement &update : statement.update) {
      collectHIRAssignedNames(update, assignedNames);
    }
    for (const HIRStatement &child : statement.body) {
      collectHIRAssignedNames(child, assignedNames);
    }
    for (const std::string &name : assignedNames) {
      eraseHIRFoldedName(context, name);
    }
    return changed;
  }
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
    changed = foldConstantHIRIntrinsicExpression(statement.value, context) ||
              changed;
    return changed;
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
    return false;
  case HIRStatementKind::Raw:
    clearHIRLocalFoldedValues(context);
    return changed;
  }
  return false;
}

bool foldConstantHIRIntrinsicFunction(
    HIRFunction &function, const HIRScalarConstantMap &constantValues,
    const HIRValueConstantMap &valueConstants) {
  HIRFoldContext context = makeHIRFoldContext(constantValues, valueConstants);
  for (const HIRParameter &parameter : function.parameters) {
    if (!parameter.name.empty()) {
      context.hiddenNames.insert(parameter.name);
      eraseHIRFoldedName(context, parameter.name);
    }
  }
  return mutateHIRFunctionBody(function,
                               [&](std::vector<HIRStatement> &body) {
                                 return foldConstantHIRIntrinsicBlock(body,
                                                                       context);
                               });
}

bool foldConstantHIRIntrinsics(HIRModule &module, DiagnosticEngine &) {
  bool changed = false;
  HIRScalarConstantMap constantValues;
  HIRValueConstantMap valueConstants;
  for (const HIRConstant &constant : module.constants) {
    if (constant.name.empty() || !constant.foldedValue.has_value()) {
      continue;
    }
    if (std::optional<FoldedHIRScalar> folded =
            parseFoldedHIRScalar(*constant.foldedValue)) {
      constantValues[constant.name] = *folded;
      valueConstants[constant.name] = foldedHIRValueFromScalar(*folded);
    }
  }

  for (HIRConstant &constant : module.constants) {
    HIRFoldContext constantContext =
        makeHIRFoldContext(constantValues, valueConstants);
    changed = foldConstantHIRIntrinsicExpression(constant.value,
                                                 constantContext) ||
              changed;
    if (constant.name.empty()) {
      continue;
    }
    HIRScalarFoldOptions options;
    options.foldIntrinsicCalls = true;
    const std::optional<FoldedHIRValue> foldedValue =
        foldHIRValueExpression(constant.value, constantValues, options,
                               &valueConstants);
    if (!foldedValue.has_value()) {
      continue;
    }

    if (foldedValue->components.size() == 1) {
      const FoldedHIRScalar &folded = foldedValue->components.front();
      const std::optional<std::string> foldedText =
          formatFoldedHIRScalarForType(folded, constant.type);
      if (!foldedText.has_value()) {
        continue;
      }
      if (constant.foldedValue != foldedText) {
        constant.foldedValue = *foldedText;
        changed = true;
      }
      constantValues[constant.name] = folded;
      valueConstants[constant.name] = *foldedValue;
      continue;
    }

    if (isFoldableHIRVectorType(constant.type)) {
      valueConstants[constant.name] = *foldedValue;
    }
  }

  for (HIRFunction &function : module.functions) {
    changed = foldConstantHIRIntrinsicFunction(function, constantValues,
                                               valueConstants) ||
              changed;
  }
  for (HIRStage &stage : module.stages) {
    for (HIRFunction &function : stage.functions) {
      changed = foldConstantHIRIntrinsicFunction(function, constantValues,
                                                 valueConstants) ||
                changed;
    }
  }
  return changed;
}

std::optional<bool> literalHIRBoolCondition(const HIRExpression &condition) {
  if (condition.kind == HIRExpressionKind::Group &&
      !condition.children.empty()) {
    return literalHIRBoolCondition(condition.children.front());
  }
  if ((condition.kind != HIRExpressionKind::Literal &&
       condition.kind != HIRExpressionKind::Identifier) ||
      baseTypeName(condition.type) != "bool" ||
      condition.type.arraySize.has_value()) {
    return std::nullopt;
  }
  if (condition.value == "true") {
    return true;
  }
  if (condition.value == "false") {
    return false;
  }
  return std::nullopt;
}

bool hirExpressionTypeCanReplaceParent(const HIRExpression &parent,
                                        const HIRExpression &replacement) {
  if (replacement.kind == HIRExpressionKind::Empty) {
    return false;
  }
  if (!hasHIRTypeShape(parent.type)) {
    return true;
  }
  return hasHIRTypeShape(replacement.type) &&
         sameType(parent.type, replacement.type);
}

const HIRExpression *unwrapHIRAlgebraicIdentityLiteral(
    const HIRExpression &expression) {
  if (expression.kind == HIRExpressionKind::Group &&
      expression.children.size() == 1) {
    return unwrapHIRAlgebraicIdentityLiteral(expression.children.front());
  }
  return &expression;
}

const HIRExpression *unwrapHIRAlgebraicGroup(const HIRExpression &expression) {
  if (expression.kind == HIRExpressionKind::Group &&
      expression.children.size() == 1) {
    return unwrapHIRAlgebraicGroup(expression.children.front());
  }
  return &expression;
}

bool isHIRNumericIdentityLiteral(const HIRExpression &expression,
                                 double expected) {
  const HIRExpression *literal =
      unwrapHIRAlgebraicIdentityLiteral(expression);
  if (literal == nullptr || literal->kind != HIRExpressionKind::Literal ||
      !literal->children.empty() ||
      (hasHIRTypeShape(literal->type) &&
       (!isNumericScalarTypeName(baseTypeName(literal->type)) ||
        literal->type.arraySize.has_value()))) {
    return false;
  }

  const std::optional<FoldedHIRScalar> folded =
      parseFoldedHIRScalar(literal->value);
  return folded.has_value() && !folded->isBool &&
         std::fabs(folded->number - expected) < 0.000000001;
}

bool isHIRIntegerIdentityLiteral(const HIRExpression &expression,
                                 double expected) {
  const HIRExpression *literal =
      unwrapHIRAlgebraicIdentityLiteral(expression);
  if (literal == nullptr || literal->kind != HIRExpressionKind::Literal ||
      !literal->children.empty() ||
      (hasHIRTypeShape(literal->type) &&
       (!isIntegerScalarType(literal->type) ||
        literal->type.arraySize.has_value()))) {
    return false;
  }

  const std::optional<FoldedHIRScalar> folded =
      parseFoldedHIRScalar(literal->value);
  return folded.has_value() && !folded->isBool && folded->isInteger &&
         std::fabs(folded->number - expected) < 0.000000001;
}

bool isFloatScalarType(const HIRType &type) {
  const std::string unqualified = stripTypeQualifier(type.name);
  return !type.arraySize.has_value() &&
         (unqualified.empty() || unqualified.back() != '*') &&
         isFloatLike(unqualified);
}

bool isIntegerVectorType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return false;
  }

  const std::string baseName = baseTypeName(type);
  if (!isVectorType(baseName)) {
    return false;
  }
  return isIntegerScalarType(scalarTypeForVector(baseName));
}

bool isIntegerScalarOrVectorType(const HIRType &type) {
  return isIntegerScalarType(type) || isIntegerVectorType(type);
}

bool isHIRFloatIdentityLiteral(const HIRExpression &expression,
                               double expected) {
  const HIRExpression *literal =
      unwrapHIRAlgebraicIdentityLiteral(expression);
  if (literal == nullptr || literal->kind != HIRExpressionKind::Literal ||
      !literal->children.empty() ||
      (hasHIRTypeShape(literal->type) &&
       (!isFloatScalarType(literal->type) ||
        literal->type.arraySize.has_value()))) {
    return false;
  }

  const std::optional<FoldedHIRScalar> folded =
      parseFoldedHIRScalar(literal->value);
  return folded.has_value() && !folded->isBool && !folded->isInteger &&
         std::fabs(folded->number - expected) < 0.000000001;
}

std::optional<HIRExpression>
makeHIRAlgebraicIntegerZeroReplacement(const HIRExpression &expression) {
  if (!hasHIRTypeShape(expression.type) ||
      expression.type.arraySize.has_value() ||
      !isIntegerScalarTypeName(baseTypeName(expression.type))) {
    return std::nullopt;
  }

  const FoldedHIRScalar zero{0.0, false, false, true};
  const std::optional<std::string> foldedText =
      formatFoldedHIRScalarForType(zero, expression.type);
  if (!foldedText.has_value()) {
    return std::nullopt;
  }

  HIRExpression replacement;
  replacement.kind = HIRExpressionKind::Literal;
  replacement.type = expression.type;
  replacement.value = *foldedText;
  replacement.location = expression.location;
  if (!hirExpressionTypeCanReplaceParent(expression, replacement)) {
    return std::nullopt;
  }
  return replacement;
}

bool structurallySameHIRExpression(const HIRExpression &left,
                                   const HIRExpression &right) {
  if (left.kind != right.kind || left.value != right.value ||
      left.children.size() != right.children.size()) {
    return false;
  }
  if (hasHIRTypeShape(left.type) || hasHIRTypeShape(right.type)) {
    if (!hasHIRTypeShape(left.type) || !hasHIRTypeShape(right.type) ||
        !sameType(left.type, right.type)) {
      return false;
    }
  }
  for (std::size_t index = 0; index < left.children.size(); ++index) {
    if (!structurallySameHIRExpression(left.children[index],
                                       right.children[index])) {
      return false;
    }
  }
  return true;
}

bool isHIRNaNFreeScalarSelfComparisonType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  return baseName == "bool" || isIntegerScalarTypeName(baseName);
}

bool isHIRPureLogicalComplementPair(const HIRExpression &plainExpression,
                                    const HIRExpression &negatedExpression) {
  const HIRExpression *plain = unwrapHIRAlgebraicGroup(plainExpression);
  const HIRExpression *negated = unwrapHIRAlgebraicGroup(negatedExpression);
  if (plain == nullptr || negated == nullptr ||
      (hasHIRTypeShape(plain->type) && !isScalarBoolType(plain->type)) ||
      negated->kind != HIRExpressionKind::Unary || negated->value != "!" ||
      negated->children.size() != 1 ||
      (hasHIRTypeShape(negated->type) && !isScalarBoolType(negated->type))) {
    return false;
  }

  const HIRExpression *negatedOperand =
      unwrapHIRAlgebraicGroup(negated->children.front());
  return negatedOperand != nullptr &&
         structurallySameHIRExpression(*plain, *negatedOperand) &&
         isKnownPureHIRExpression(*plain);
}

bool hasHIRPureLogicalComplementOperands(const HIRExpression &left,
                                         const HIRExpression &right) {
  return isHIRPureLogicalComplementPair(left, right) ||
         isHIRPureLogicalComplementPair(right, left);
}

std::optional<std::string_view>
invertedHIRIntegerRelationalOperator(std::string_view operation) {
  if (operation == "<") {
    return ">=";
  }
  if (operation == "<=") {
    return ">";
  }
  if (operation == ">") {
    return "<=";
  }
  if (operation == ">=") {
    return "<";
  }
  return std::nullopt;
}

std::optional<std::string_view>
invertedHIREqualityOperator(std::string_view operation) {
  if (operation == "==") {
    return "!=";
  }
  if (operation == "!=") {
    return "==";
  }
  return std::nullopt;
}

bool isHIREqualityNegationOperandType(const HIRType &type) {
  return isScalarBoolType(type) || isIntegerScalarType(type) ||
         isFloatScalarType(type);
}

bool isHIRPureBooleanAbsorptionPair(const HIRExpression &absorbedExpression,
                                    const HIRExpression &compoundExpression,
                                    std::string_view compoundOperator) {
  const HIRExpression *absorbed = unwrapHIRAlgebraicGroup(absorbedExpression);
  const HIRExpression *compound = unwrapHIRAlgebraicGroup(compoundExpression);
  if (absorbed == nullptr || compound == nullptr ||
      (hasHIRTypeShape(absorbed->type) && !isScalarBoolType(absorbed->type)) ||
      compound->kind != HIRExpressionKind::Binary ||
      compound->value != compoundOperator || compound->children.size() != 2 ||
      (hasHIRTypeShape(compound->type) &&
       !isScalarBoolType(compound->type)) ||
      !isKnownPureHIRExpression(absorbedExpression) ||
      !isKnownPureHIRExpression(compoundExpression)) {
    return false;
  }

  const HIRExpression *compoundLeft =
      unwrapHIRAlgebraicGroup(compound->children[0]);
  const HIRExpression *compoundRight =
      unwrapHIRAlgebraicGroup(compound->children[1]);
  return (compoundLeft != nullptr &&
          structurallySameHIRExpression(*absorbed, *compoundLeft)) ||
         (compoundRight != nullptr &&
          structurallySameHIRExpression(*absorbed, *compoundRight));
}

std::optional<bool> hirScalarBoolAlgebraicLiteral(
    const HIRExpression &expression) {
  const HIRExpression *literal =
      unwrapHIRAlgebraicIdentityLiteral(expression);
  if (literal == nullptr || !literal->children.empty()) {
    return std::nullopt;
  }
  if (literal->kind == HIRExpressionKind::Identifier &&
      !isScalarBoolType(literal->type)) {
    return std::nullopt;
  }
  if (literal->kind != HIRExpressionKind::Literal &&
      literal->kind != HIRExpressionKind::Identifier) {
    return std::nullopt;
  }
  if (literal->kind == HIRExpressionKind::Literal &&
      hasHIRTypeShape(literal->type) && !isScalarBoolType(literal->type)) {
    return std::nullopt;
  }
  if (literal->value == "true") {
    return true;
  }
  if (literal->value == "false") {
    return false;
  }
  return std::nullopt;
}

std::optional<HIRExpression>
algebraicHIRBinaryReplacementExpression(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Binary ||
      expression.children.size() != 2) {
    return std::nullopt;
  }

  const HIRExpression &left = expression.children[0];
  const HIRExpression &right = expression.children[1];
  if (expression.value == "*") {
    if (isHIRNumericIdentityLiteral(right, 0.0) &&
        isKnownPureHIRExpression(left)) {
      return makeHIRAlgebraicIntegerZeroReplacement(expression);
    }
    if (isHIRNumericIdentityLiteral(left, 0.0) &&
        isKnownPureHIRExpression(right)) {
      return makeHIRAlgebraicIntegerZeroReplacement(expression);
    }
  }

  if (expression.value == "-" && structurallySameHIRExpression(left, right) &&
      isKnownPureHIRExpression(left)) {
    return makeHIRAlgebraicIntegerZeroReplacement(expression);
  }

  if (expression.value == "%" && isHIRIntegerIdentityLiteral(right, 1.0) &&
      isKnownPureHIRExpression(left) && isKnownPureHIRExpression(right)) {
    return makeHIRAlgebraicIntegerZeroReplacement(expression);
  }

  if ((expression.value == "==" || expression.value == "!=") &&
      isScalarBoolType(expression.type) &&
      isHIRNaNFreeScalarSelfComparisonType(left.type) &&
      structurallySameHIRExpression(left, right) &&
      isKnownPureHIRExpression(left)) {
    HIRExpression replacement =
        makeHIRBoolLiteral(expression.value == "==", expression.location);
    if (hirExpressionTypeCanReplaceParent(expression, replacement)) {
      return replacement;
    }
  }

  if ((expression.value == "<" || expression.value == "<=" ||
       expression.value == ">" || expression.value == ">=") &&
      isScalarBoolType(expression.type) && isIntegerScalarType(left.type) &&
      structurallySameHIRExpression(left, right) &&
      isKnownPureHIRExpression(left)) {
    HIRExpression replacement =
        makeHIRBoolLiteral(expression.value == "<=" || expression.value == ">=",
                           expression.location);
    if (hirExpressionTypeCanReplaceParent(expression, replacement)) {
      return replacement;
    }
  }

  if ((expression.value == "&&" || expression.value == "||") &&
      isScalarBoolType(expression.type) &&
      hasHIRPureLogicalComplementOperands(left, right)) {
    HIRExpression replacement =
        makeHIRBoolLiteral(expression.value == "||", expression.location);
    if (hirExpressionTypeCanReplaceParent(expression, replacement)) {
      return replacement;
    }
  }

  return std::nullopt;
}

bool canRenderHIRPreservedReplacementWithoutGrouping(
    const HIRExpression &expression) {
  switch (expression.kind) {
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::Literal:
  case HIRExpressionKind::Group:
  case HIRExpressionKind::MemberAccess:
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::Call:
  case HIRExpressionKind::Constructor:
  case HIRExpressionKind::Unary:
  case HIRExpressionKind::TextureSample:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    return true;
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Binary:
  case HIRExpressionKind::Select:
    return false;
  }
  return false;
}

HIRExpression groupedHIRPreservedReplacement(HIRExpression expression) {
  while (expression.kind == HIRExpressionKind::Group &&
         expression.children.size() == 1 &&
         canRenderHIRPreservedReplacementWithoutGrouping(
             expression.children.front())) {
    expression = expression.children.front();
  }
  if (canRenderHIRPreservedReplacementWithoutGrouping(expression)) {
    return expression;
  }

  HIRExpression group;
  group.kind = HIRExpressionKind::Group;
  group.type = expression.type;
  group.location = expression.location;
  group.children.push_back(std::move(expression));
  return group;
}

bool replaceHIRExpressionWithChild(HIRExpression &expression,
                                   std::size_t childIndex) {
  if (childIndex >= expression.children.size() ||
      !hirExpressionTypeCanReplaceParent(expression,
                                         expression.children[childIndex])) {
    return false;
  }
  HIRExpression replacement =
      groupedHIRPreservedReplacement(expression.children[childIndex]);
  if (!hirExpressionTypeCanReplaceParent(expression, replacement)) {
    return false;
  }
  expression = std::move(replacement);
  return true;
}

bool simplifyAlgebraicHIRExpression(HIRExpression &expression);

std::optional<HIRExpression>
booleanDeMorganNegationReplacementExpression(const HIRExpression &expression);

bool simplifyAlgebraicHIRIndexOperand(HIRExpression &expression) {
  if (expression.kind == HIRExpressionKind::NonUniform) {
    bool changed = false;
    for (HIRExpression &child : expression.children) {
      changed = simplifyAlgebraicHIRExpression(child) || changed;
    }
    return changed;
  }
  return simplifyAlgebraicHIRExpression(expression);
}

bool simplifyAlgebraicHIRIndexOperands(HIRExpression &expression) {
  bool changed = false;
  if (expression.kind == HIRExpressionKind::IndexAccess &&
      expression.children.size() >= 2) {
    changed =
        simplifyAlgebraicHIRIndexOperands(expression.children[0]) || changed;
    changed =
        simplifyAlgebraicHIRIndexOperand(expression.children[1]) || changed;
    for (std::size_t index = 2; index < expression.children.size(); ++index) {
      changed =
          simplifyAlgebraicHIRIndexOperands(expression.children[index]) ||
          changed;
    }
    return changed;
  }

  for (HIRExpression &child : expression.children) {
    changed = simplifyAlgebraicHIRIndexOperands(child) || changed;
  }
  return changed;
}

std::optional<HIRExpression>
equalityComparisonNegationReplacementExpression(
    const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Unary || expression.value != "!" ||
      expression.children.size() != 1 || !isScalarBoolType(expression.type)) {
    return std::nullopt;
  }

  const HIRExpression *comparison =
      unwrapHIRAlgebraicGroup(expression.children.front());
  if (comparison == nullptr || comparison->kind != HIRExpressionKind::Binary ||
      comparison->children.size() != 2 || !isScalarBoolType(comparison->type) ||
      !isHIREqualityNegationOperandType(comparison->children[0].type) ||
      !isHIREqualityNegationOperandType(comparison->children[1].type) ||
      !sameType(comparison->children[0].type, comparison->children[1].type) ||
      !isKnownPureHIRExpression(*comparison)) {
    return std::nullopt;
  }

  std::optional<std::string_view> invertedOperator =
      invertedHIREqualityOperator(comparison->value);
  if (!invertedOperator.has_value()) {
    return std::nullopt;
  }

  HIRExpression comparisonReplacement = *comparison;
  comparisonReplacement.value.assign(invertedOperator->data(),
                                     invertedOperator->size());
  comparisonReplacement.type = expression.type;
  comparisonReplacement.location = expression.location;
  if (!hirExpressionTypeCanReplaceParent(expression, comparisonReplacement)) {
    return std::nullopt;
  }

  HIRExpression replacement;
  replacement.kind = HIRExpressionKind::Group;
  replacement.type = expression.type;
  replacement.location = expression.location;
  replacement.children.push_back(std::move(comparisonReplacement));
  if (!hirExpressionTypeCanReplaceParent(expression, replacement)) {
    return std::nullopt;
  }
  return replacement;
}

std::optional<HIRExpression>
integerRelationalNegationReplacementExpression(
    const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Unary || expression.value != "!" ||
      expression.children.size() != 1 || !isScalarBoolType(expression.type)) {
    return std::nullopt;
  }

  const HIRExpression *comparison =
      unwrapHIRAlgebraicGroup(expression.children.front());
  if (comparison == nullptr || comparison->kind != HIRExpressionKind::Binary ||
      comparison->children.size() != 2 || !isScalarBoolType(comparison->type) ||
      !isIntegerScalarType(comparison->children[0].type) ||
      !isIntegerScalarType(comparison->children[1].type) ||
      !sameType(comparison->children[0].type, comparison->children[1].type) ||
      !isKnownPureHIRExpression(*comparison)) {
    return std::nullopt;
  }

  std::optional<std::string_view> invertedOperator =
      invertedHIRIntegerRelationalOperator(comparison->value);
  if (!invertedOperator.has_value()) {
    return std::nullopt;
  }

  HIRExpression replacement = *comparison;
  replacement.value.assign(invertedOperator->data(), invertedOperator->size());
  replacement.type = expression.type;
  replacement.location = expression.location;
  if (!hirExpressionTypeCanReplaceParent(expression, replacement)) {
    return std::nullopt;
  }
  return replacement;
}

bool simplifyAlgebraicHIRUnaryExpression(HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Unary ||
      expression.children.size() != 1) {
    return false;
  }

  HIRExpression &operand = expression.children.front();
  if (expression.value == "-" && isIntegerScalarType(expression.type) &&
      isHIRIntegerIdentityLiteral(operand, 0.0)) {
    std::optional<HIRExpression> replacement =
        makeHIRAlgebraicIntegerZeroReplacement(expression);
    if (replacement.has_value()) {
      expression = std::move(*replacement);
      return true;
    }
  }

  if (expression.value == "+" &&
      (isIntegerScalarType(expression.type) ||
       isFloatScalarType(expression.type)) &&
      hirExpressionTypeCanReplaceParent(expression, operand)) {
    HIRExpression replacement = std::move(operand);
    expression = std::move(replacement);
    return true;
  }

  if (expression.value != "!" || !isScalarBoolType(expression.type)) {
    return false;
  }

  if (std::optional<HIRExpression> replacement =
          equalityComparisonNegationReplacementExpression(expression)) {
    expression = std::move(*replacement);
    return true;
  }

  if (std::optional<HIRExpression> replacement =
          integerRelationalNegationReplacementExpression(expression)) {
    expression = std::move(*replacement);
    return true;
  }

  if (std::optional<HIRExpression> replacement =
          booleanDeMorganNegationReplacementExpression(expression)) {
    expression = std::move(*replacement);
    return true;
  }

  if (operand.kind != HIRExpressionKind::Unary || operand.value != "!" ||
      operand.children.size() != 1 || !isScalarBoolType(operand.type)) {
    return false;
  }

  if (!hirExpressionTypeCanReplaceParent(expression, operand.children.front())) {
    return false;
  }
  HIRExpression replacement = std::move(operand.children.front());
  expression = std::move(replacement);
  return true;
}

bool simplifyAlgebraicHIRGroupExpression(HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Group ||
      expression.children.size() != 1 ||
      expression.children.front().kind != HIRExpressionKind::Group ||
      !hirExpressionTypeCanReplaceParent(expression, expression.children.front())) {
    return false;
  }

  HIRExpression replacement = std::move(expression.children.front());
  expression = std::move(replacement);
  return true;
}

HIRExpression groupedHIRUnaryOperand(HIRExpression expression) {
  return groupedHIRPreservedReplacement(std::move(expression));
}

std::optional<HIRExpression>
makeHIRBoolNegationReplacement(const HIRExpression &expression,
                               const HIRExpression &operand,
                               bool allowDeMorgan) {
  if (!isScalarBoolType(expression.type) ||
      (hasHIRTypeShape(operand.type) && !isScalarBoolType(operand.type))) {
    return std::nullopt;
  }

  const HIRExpression *plainOperand = unwrapHIRAlgebraicGroup(operand);
  if (plainOperand != nullptr && plainOperand->kind == HIRExpressionKind::Unary &&
      plainOperand->value == "!" && plainOperand->children.size() == 1 &&
      (!hasHIRTypeShape(plainOperand->children.front().type) ||
       isScalarBoolType(plainOperand->children.front().type)) &&
      hirExpressionTypeCanReplaceParent(expression,
                                        plainOperand->children.front())) {
    HIRExpression replacement =
        groupedHIRPreservedReplacement(plainOperand->children.front());
    if (hirExpressionTypeCanReplaceParent(expression, replacement)) {
      return replacement;
    }
    return std::nullopt;
  }

  HIRExpression replacement;
  replacement.kind = HIRExpressionKind::Unary;
  replacement.value = "!";
  replacement.type = expression.type;
  replacement.location = expression.location;
  replacement.children.push_back(groupedHIRUnaryOperand(operand));
  if (!hirExpressionTypeCanReplaceParent(expression, replacement)) {
    return std::nullopt;
  }
  if (std::optional<HIRExpression> relationalReplacement =
          equalityComparisonNegationReplacementExpression(replacement)) {
    if (hirExpressionTypeCanReplaceParent(expression, *relationalReplacement)) {
      return relationalReplacement;
    }
  }
  if (std::optional<HIRExpression> relationalReplacement =
          integerRelationalNegationReplacementExpression(replacement)) {
    if (hirExpressionTypeCanReplaceParent(expression, *relationalReplacement)) {
      return relationalReplacement;
    }
  }
  if (allowDeMorgan) {
    if (std::optional<HIRExpression> deMorganReplacement =
            booleanDeMorganNegationReplacementExpression(replacement);
        deMorganReplacement.has_value() &&
        hirExpressionTypeCanReplaceParent(expression, *deMorganReplacement)) {
      return deMorganReplacement;
    }
  }
  return replacement;
}

std::optional<HIRExpression>
makeHIRBoolNegationReplacement(const HIRExpression &expression,
                               const HIRExpression &operand) {
  return makeHIRBoolNegationReplacement(expression, operand, true);
}

std::optional<HIRExpression>
booleanDeMorganNegationReplacementExpression(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Unary || expression.value != "!" ||
      expression.children.size() != 1 || !isScalarBoolType(expression.type)) {
    return std::nullopt;
  }

  const HIRExpression *binary =
      unwrapHIRAlgebraicGroup(expression.children.front());
  if (binary == nullptr || binary->kind != HIRExpressionKind::Binary ||
      (binary->value != "&&" && binary->value != "||") ||
      binary->children.size() != 2 || !isScalarBoolType(binary->type) ||
      !isScalarBoolType(binary->children[0].type) ||
      !isScalarBoolType(binary->children[1].type) ||
      !isKnownPureHIRExpression(*binary) ||
      !isKnownPureHIRExpression(binary->children[0]) ||
      !isKnownPureHIRExpression(binary->children[1])) {
    return std::nullopt;
  }

  std::optional<HIRExpression> left =
      makeHIRBoolNegationReplacement(expression, binary->children[0], false);
  std::optional<HIRExpression> right =
      makeHIRBoolNegationReplacement(expression, binary->children[1], false);
  if (!left.has_value() || !right.has_value()) {
    return std::nullopt;
  }

  HIRExpression binaryReplacement;
  binaryReplacement.kind = HIRExpressionKind::Binary;
  binaryReplacement.value = binary->value == "&&" ? "||" : "&&";
  binaryReplacement.type = expression.type;
  binaryReplacement.location = expression.location;
  binaryReplacement.children.push_back(std::move(*left));
  binaryReplacement.children.push_back(std::move(*right));
  if (!hirExpressionTypeCanReplaceParent(expression, binaryReplacement)) {
    return std::nullopt;
  }

  HIRExpression replacement;
  replacement.kind = HIRExpressionKind::Group;
  replacement.type = expression.type;
  replacement.location = expression.location;
  replacement.children.push_back(std::move(binaryReplacement));
  if (!hirExpressionTypeCanReplaceParent(expression, replacement)) {
    return std::nullopt;
  }
  return replacement;
}

std::optional<HIRExpression>
boolLiteralComparisonReplacementExpression(const HIRExpression &expression) {
  if ((expression.value != "==" && expression.value != "!=") ||
      expression.children.size() != 2 || !isScalarBoolType(expression.type)) {
    return std::nullopt;
  }

  const HIRExpression &left = expression.children[0];
  const HIRExpression &right = expression.children[1];
  const std::optional<bool> leftBool = hirScalarBoolAlgebraicLiteral(left);
  const std::optional<bool> rightBool = hirScalarBoolAlgebraicLiteral(right);
  if (rightBool.has_value() &&
      (!hasHIRTypeShape(left.type) || isScalarBoolType(left.type))) {
    const bool keepOperand = (expression.value == "==") == *rightBool;
    if (keepOperand) {
      HIRExpression replacement = groupedHIRPreservedReplacement(left);
      if (!hirExpressionTypeCanReplaceParent(expression, replacement)) {
        return std::nullopt;
      }
      return replacement;
    }
    return makeHIRBoolNegationReplacement(expression, left);
  }
  if (leftBool.has_value() &&
      (!hasHIRTypeShape(right.type) || isScalarBoolType(right.type))) {
    const bool keepOperand = (expression.value == "==") == *leftBool;
    if (keepOperand) {
      HIRExpression replacement = groupedHIRPreservedReplacement(right);
      if (!hirExpressionTypeCanReplaceParent(expression, replacement)) {
        return std::nullopt;
      }
      return replacement;
    }
    return makeHIRBoolNegationReplacement(expression, right);
  }
  return std::nullopt;
}

std::optional<HIRExpression>
booleanHIRSelectReplacementExpression(HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Select ||
      expression.children.size() < 3 || !isScalarBoolType(expression.type) ||
      !isScalarBoolType(expression.children[0].type)) {
    return std::nullopt;
  }

  const std::optional<bool> thenBool =
      hirScalarBoolAlgebraicLiteral(expression.children[1]);
  const std::optional<bool> elseBool =
      hirScalarBoolAlgebraicLiteral(expression.children[2]);
  if (!thenBool.has_value() || !elseBool.has_value() ||
      *thenBool == *elseBool) {
    return std::nullopt;
  }

  if (*thenBool && !*elseBool) {
    HIRExpression replacement =
        groupedHIRPreservedReplacement(expression.children[0]);
    if (!hirExpressionTypeCanReplaceParent(expression, replacement)) {
      return std::nullopt;
    }
    return replacement;
  }

  return makeHIRBoolNegationReplacement(expression, expression.children[0]);
}

std::optional<HIRExpression>
sameArmHIRSelectReplacementExpression(HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Select ||
      expression.children.size() < 3 ||
      !isKnownPureHIRExpression(expression.children[0]) ||
      !structurallySameHIRExpression(expression.children[1],
                                     expression.children[2]) ||
      !hirExpressionTypeCanReplaceParent(expression, expression.children[1])) {
    return std::nullopt;
  }

  HIRExpression replacement =
      groupedHIRPreservedReplacement(expression.children[1]);
  if (!hirExpressionTypeCanReplaceParent(expression, replacement)) {
    return std::nullopt;
  }
  return replacement;
}

std::optional<std::size_t>
algebraicHIRBinaryReplacementChild(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Binary ||
      expression.children.size() != 2) {
    return std::nullopt;
  }

  const HIRExpression &left = expression.children[0];
  const HIRExpression &right = expression.children[1];
  if (isIntegerScalarOrVectorType(expression.type)) {
    if ((expression.value == "+" || expression.value == "-") &&
        isHIRIntegerIdentityLiteral(right, 0.0) &&
        isKnownPureHIRExpression(right) &&
        hirExpressionTypeCanReplaceParent(expression, left)) {
      return 0;
    }
    if (expression.value == "+" && isHIRIntegerIdentityLiteral(left, 0.0) &&
        isKnownPureHIRExpression(left) &&
        hirExpressionTypeCanReplaceParent(expression, right)) {
      return 1;
    }
    if ((expression.value == "*" || expression.value == "/") &&
        isHIRIntegerIdentityLiteral(right, 1.0) &&
        isKnownPureHIRExpression(right) &&
        hirExpressionTypeCanReplaceParent(expression, left)) {
      return 0;
    }
    if (expression.value == "*" && isHIRIntegerIdentityLiteral(left, 1.0) &&
        isKnownPureHIRExpression(left) &&
        hirExpressionTypeCanReplaceParent(expression, right)) {
      return 1;
    }
  }
  if (isFloatScalarType(expression.type)) {
    if (expression.value == "-" && isHIRFloatIdentityLiteral(right, 0.0) &&
        isKnownPureHIRExpression(right) &&
        hirExpressionTypeCanReplaceParent(expression, left)) {
      return 0;
    }
    if ((expression.value == "*" || expression.value == "/") &&
        isHIRFloatIdentityLiteral(right, 1.0) &&
        isKnownPureHIRExpression(right) &&
        hirExpressionTypeCanReplaceParent(expression, left)) {
      return 0;
    }
    if (expression.value == "*" && isHIRFloatIdentityLiteral(left, 1.0) &&
        isKnownPureHIRExpression(left) &&
        hirExpressionTypeCanReplaceParent(expression, right)) {
      return 1;
    }
  }
  if (expression.value == "&&" && isScalarBoolType(expression.type)) {
    if (structurallySameHIRExpression(left, right) &&
        isKnownPureHIRExpression(left) &&
        hirExpressionTypeCanReplaceParent(expression, left)) {
      return 0;
    }
    if (isHIRPureBooleanAbsorptionPair(left, right, "||") &&
        hirExpressionTypeCanReplaceParent(expression, left)) {
      return 0;
    }
    if (isHIRPureBooleanAbsorptionPair(right, left, "||") &&
        hirExpressionTypeCanReplaceParent(expression, right)) {
      return 1;
    }
    const std::optional<bool> leftBool = hirScalarBoolAlgebraicLiteral(left);
    const std::optional<bool> rightBool = hirScalarBoolAlgebraicLiteral(right);
    if (rightBool == true &&
        hirExpressionTypeCanReplaceParent(expression, left)) {
      return 0;
    }
    if (leftBool == true &&
        hirExpressionTypeCanReplaceParent(expression, right)) {
      return 1;
    }
    if (leftBool == false && isKnownPureHIRExpression(right) &&
        hirExpressionTypeCanReplaceParent(expression, left)) {
      return 0;
    }
    if (rightBool == false && isKnownPureHIRExpression(left) &&
        hirExpressionTypeCanReplaceParent(expression, right)) {
      return 1;
    }
  }
  if (expression.value == "||" && isScalarBoolType(expression.type)) {
    if (structurallySameHIRExpression(left, right) &&
        isKnownPureHIRExpression(left) &&
        hirExpressionTypeCanReplaceParent(expression, left)) {
      return 0;
    }
    if (isHIRPureBooleanAbsorptionPair(left, right, "&&") &&
        hirExpressionTypeCanReplaceParent(expression, left)) {
      return 0;
    }
    if (isHIRPureBooleanAbsorptionPair(right, left, "&&") &&
        hirExpressionTypeCanReplaceParent(expression, right)) {
      return 1;
    }
    const std::optional<bool> leftBool = hirScalarBoolAlgebraicLiteral(left);
    const std::optional<bool> rightBool = hirScalarBoolAlgebraicLiteral(right);
    if (rightBool == false &&
        hirExpressionTypeCanReplaceParent(expression, left)) {
      return 0;
    }
    if (leftBool == false &&
        hirExpressionTypeCanReplaceParent(expression, right)) {
      return 1;
    }
    if (leftBool == true && isKnownPureHIRExpression(right) &&
        hirExpressionTypeCanReplaceParent(expression, left)) {
      return 0;
    }
    if (rightBool == true && isKnownPureHIRExpression(left) &&
        hirExpressionTypeCanReplaceParent(expression, right)) {
      return 1;
    }
  }
  return std::nullopt;
}

bool simplifyAlgebraicHIRSelectExpression(HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Select ||
      expression.children.size() < 3) {
    return false;
  }

  if (std::optional<HIRExpression> replacement =
          booleanHIRSelectReplacementExpression(expression)) {
    expression = std::move(*replacement);
    return true;
  }
  if (std::optional<HIRExpression> replacement =
          sameArmHIRSelectReplacementExpression(expression)) {
    expression = std::move(*replacement);
    return true;
  }

  const std::optional<bool> condition =
      literalHIRBoolCondition(expression.children[0]);
  if (!condition.has_value()) {
    return false;
  }

  const std::size_t discardedIndex = *condition ? 2 : 1;
  if (expression.children.size() <= discardedIndex ||
      !isKnownPureHIRExpression(expression.children[0]) ||
      !isKnownPureHIRExpression(expression.children[discardedIndex])) {
    return false;
  }

  std::optional<HIRExpression> replacement =
      prunedFoldedHIRSelectReplacement(expression, *condition);
  if (!replacement.has_value()) {
    return false;
  }
  expression = std::move(*replacement);
  return true;
}

bool simplifyAlgebraicHIRExpression(HIRExpression &expression) {
  if (expression.kind == HIRExpressionKind::TextureCompareLodManual) {
    return simplifyAlgebraicHIRIndexOperands(expression);
  }

  bool changed = false;
  if (expression.kind == HIRExpressionKind::IndexAccess &&
      expression.children.size() >= 2) {
    changed = simplifyAlgebraicHIRExpression(expression.children[0]) ||
              changed;
    changed =
        simplifyAlgebraicHIRIndexOperand(expression.children[1]) || changed;
    for (std::size_t index = 2; index < expression.children.size(); ++index) {
      changed =
          simplifyAlgebraicHIRExpression(expression.children[index]) || changed;
    }
  } else {
    for (HIRExpression &child : expression.children) {
      changed = simplifyAlgebraicHIRExpression(child) || changed;
    }
  }

  if (simplifyAlgebraicHIRUnaryExpression(expression)) {
    return true;
  }
  if (simplifyAlgebraicHIRGroupExpression(expression)) {
    return true;
  }
  if (std::optional<std::size_t> replacement =
          algebraicHIRBinaryReplacementChild(expression)) {
    return replaceHIRExpressionWithChild(expression, *replacement);
  }
  if (std::optional<HIRExpression> replacement =
          boolLiteralComparisonReplacementExpression(expression)) {
    expression = std::move(*replacement);
    return true;
  }
  if (std::optional<HIRExpression> replacement =
          algebraicHIRBinaryReplacementExpression(expression)) {
    expression = std::move(*replacement);
    return true;
  }
  if (simplifyAlgebraicHIRSelectExpression(expression)) {
    return true;
  }
  return changed;
}

bool simplifyAlgebraicHIRStatement(HIRStatement &statement);

bool simplifyAlgebraicHIRBlock(std::vector<HIRStatement> &statements) {
  bool changed = false;
  for (HIRStatement &statement : statements) {
    changed = simplifyAlgebraicHIRStatement(statement) || changed;
  }
  return changed;
}

bool simplifyAlgebraicHIRStatement(HIRStatement &statement) {
  bool changed = false;
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    changed = simplifyAlgebraicHIRExpression(statement.value) || changed;
    return changed;
  case HIRStatementKind::Assignment:
    changed = simplifyAlgebraicHIRExpression(statement.target) || changed;
    changed = simplifyAlgebraicHIRExpression(statement.value) || changed;
    return changed;
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
    changed = simplifyAlgebraicHIRExpression(statement.value) || changed;
    return changed;
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
    return false;
  case HIRStatementKind::Block:
    changed = simplifyAlgebraicHIRBlock(statement.body) || changed;
    return changed;
  case HIRStatementKind::If:
    changed = simplifyAlgebraicHIRExpression(statement.value) || changed;
    changed = simplifyAlgebraicHIRBlock(statement.body) || changed;
    changed = simplifyAlgebraicHIRBlock(statement.elseBody) || changed;
    return changed;
  case HIRStatementKind::For:
    changed = simplifyAlgebraicHIRBlock(statement.initializer) || changed;
    changed = simplifyAlgebraicHIRExpression(statement.value) || changed;
    changed = mutateHIRLoopUpdate(statement, simplifyAlgebraicHIRBlock) ||
              changed;
    changed = simplifyAlgebraicHIRBlock(statement.body) || changed;
    return changed;
  case HIRStatementKind::Raw:
    return false;
  }
  return changed;
}

bool simplifyAlgebraicHIR(HIRModule &module, DiagnosticEngine &) {
  bool changed = false;
  for (HIRConstant &constant : module.constants) {
    changed = simplifyAlgebraicHIRExpression(constant.value) || changed;
  }
  for (HIRFunction &function : module.functions) {
    changed = mutateHIRFunctionBody(function, simplifyAlgebraicHIRBlock) ||
              changed;
  }
  for (HIRStage &stage : module.stages) {
    for (HIRFunction &function : stage.functions) {
      changed = mutateHIRFunctionBody(function, simplifyAlgebraicHIRBlock) ||
                changed;
    }
  }
  return changed;
}

struct HIRLocalScalarConstant {
  FoldedHIRScalar value;
  HIRType type;
  SourceLocation location;
};

using HIRLocalScalarConstantMap =
    std::unordered_map<std::string, HIRLocalScalarConstant>;

bool isHIRLocalScalarConstantType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  return baseName == "bool" || isNumericScalarTypeName(baseName);
}

const HIRExpression *
unwrapHIRLocalScalarConstantLiteral(const HIRExpression &expression) {
  if (expression.kind == HIRExpressionKind::Group &&
      expression.children.size() == 1) {
    return unwrapHIRLocalScalarConstantLiteral(expression.children.front());
  }
  return &expression;
}

std::optional<HIRLocalScalarConstant>
localScalarConstantFromDeclaration(const HIRStatement &statement) {
  if (statement.kind != HIRStatementKind::Declaration ||
      statement.name.empty() ||
      !isHIRLocalScalarConstantType(statement.declaredType) ||
      !isKnownPureHIRExpression(statement.value)) {
    return std::nullopt;
  }

  const HIRExpression *literal =
      unwrapHIRLocalScalarConstantLiteral(statement.value);
  if (literal == nullptr || literal->kind != HIRExpressionKind::Literal ||
      !literal->children.empty()) {
    return std::nullopt;
  }
  if (!literal->location.file.empty() && literal->location.length != 0 &&
      literal->location.length != literal->value.size()) {
    return std::nullopt;
  }

  std::optional<FoldedHIRScalar> folded =
      parseFoldedHIRScalar(literal->value);
  if (!folded.has_value() ||
      !formatFoldedHIRScalarForType(*folded, statement.declaredType)
           .has_value()) {
    return std::nullopt;
  }

  return HIRLocalScalarConstant{*folded, statement.declaredType,
                                literal->location};
}

std::optional<HIRExpression> replacementForLocalScalarIdentifier(
    const HIRExpression &expression, const HIRLocalScalarConstantMap &constants) {
  if (expression.kind != HIRExpressionKind::Identifier ||
      expression.value.empty() || !expression.children.empty() ||
      isHIRPseudoControlIdentifier(expression.value)) {
    return std::nullopt;
  }

  const auto found = constants.find(expression.value);
  if (found == constants.end()) {
    return std::nullopt;
  }

  const HIRType replacementType =
      hasHIRTypeShape(expression.type) ? expression.type : found->second.type;
  if (!isHIRLocalScalarConstantType(replacementType)) {
    return std::nullopt;
  }

  std::optional<std::string> text =
      formatFoldedHIRScalarForType(found->second.value, replacementType);
  if (!text.has_value()) {
    return std::nullopt;
  }

  HIRExpression replacement;
  replacement.kind = HIRExpressionKind::Literal;
  replacement.type = replacementType;
  replacement.value = *text;
  replacement.location = expression.location.file.empty()
                             ? found->second.location
                             : expression.location;
  return replacement;
}

bool foldPropagatedLocalScalarExpression(HIRExpression &expression) {
  if (!isFoldableHIRExpressionMaterializationCandidate(expression.kind) ||
      !isKnownPureHIRExpression(expression)) {
    return false;
  }

  HIRScalarFoldOptions options;
  options.foldIntrinsicCalls = true;
  const HIRScalarConstantMap scalarConstants;
  const std::optional<FoldedHIRValue> folded =
      foldHIRValueExpression(expression, scalarConstants, options);
  if (!folded.has_value()) {
    return false;
  }

  std::optional<HIRExpression> foldedExpression =
      foldedHIRValueToExpression(*folded, expression.type,
                                 expression.location);
  if (!foldedExpression.has_value()) {
    return false;
  }

  expression = std::move(*foldedExpression);
  return true;
}

bool propagateLocalScalarConstantsInExpression(
    HIRExpression &expression, const HIRLocalScalarConstantMap &constants);

bool propagateLocalScalarConstantsInIndexOperand(
    HIRExpression &expression, const HIRLocalScalarConstantMap &constants) {
  if (expression.kind == HIRExpressionKind::NonUniform) {
    bool changed = false;
    for (HIRExpression &child : expression.children) {
      changed =
          propagateLocalScalarConstantsInExpression(child, constants) ||
          changed;
    }
    return changed;
  }
  return propagateLocalScalarConstantsInExpression(expression, constants);
}

bool propagateLocalScalarConstantsInIndexOperands(
    HIRExpression &expression, const HIRLocalScalarConstantMap &constants) {
  bool changed = false;
  if (expression.kind == HIRExpressionKind::IndexAccess &&
      expression.children.size() >= 2) {
    changed =
        propagateLocalScalarConstantsInIndexOperands(expression.children[0],
                                                     constants) ||
        changed;
    changed =
        propagateLocalScalarConstantsInIndexOperand(expression.children[1],
                                                   constants) ||
        changed;
    for (std::size_t index = 2; index < expression.children.size(); ++index) {
      changed =
          propagateLocalScalarConstantsInIndexOperands(expression.children[index],
                                                       constants) ||
          changed;
    }
    return changed;
  }

  for (HIRExpression &child : expression.children) {
    changed =
        propagateLocalScalarConstantsInIndexOperands(child, constants) ||
        changed;
  }
  return changed;
}

bool propagateLocalScalarConstantsInExpression(
    HIRExpression &expression, const HIRLocalScalarConstantMap &constants) {
  if (expression.kind == HIRExpressionKind::TextureCompareLodManual) {
    return propagateLocalScalarConstantsInIndexOperands(expression, constants);
  }

  if (std::optional<HIRExpression> replacement =
          replacementForLocalScalarIdentifier(expression, constants)) {
    expression = std::move(*replacement);
    return true;
  }

  bool changed = false;
  for (HIRExpression &child : expression.children) {
    changed =
        propagateLocalScalarConstantsInExpression(child, constants) ||
        changed;
  }

  changed = simplifyAlgebraicHIRExpression(expression) || changed;
  if (foldPropagatedLocalScalarExpression(expression)) {
    return true;
  }
  return changed;
}

bool propagateLocalScalarConstantsInAssignmentTarget(
    HIRExpression &expression, const HIRLocalScalarConstantMap &constants) {
  if (expression.kind == HIRExpressionKind::TextureCompareLodManual) {
    return false;
  }

  bool changed = false;
  switch (expression.kind) {
  case HIRExpressionKind::Group:
  case HIRExpressionKind::MemberAccess:
  case HIRExpressionKind::NonUniform:
    if (!expression.children.empty()) {
      changed = propagateLocalScalarConstantsInAssignmentTarget(
                    expression.children.front(), constants) ||
                changed;
    }
    for (std::size_t index = 1; index < expression.children.size(); ++index) {
      changed =
          propagateLocalScalarConstantsInExpression(expression.children[index],
                                                    constants) ||
          changed;
    }
    return changed;
  case HIRExpressionKind::IndexAccess:
    if (!expression.children.empty()) {
      changed = propagateLocalScalarConstantsInAssignmentTarget(
                    expression.children.front(), constants) ||
                changed;
    }
    for (std::size_t index = 1; index < expression.children.size(); ++index) {
      changed =
          propagateLocalScalarConstantsInExpression(expression.children[index],
                                                    constants) ||
          changed;
    }
    return changed;
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::Literal:
  case HIRExpressionKind::Call:
  case HIRExpressionKind::Constructor:
  case HIRExpressionKind::Unary:
  case HIRExpressionKind::Binary:
  case HIRExpressionKind::Select:
  case HIRExpressionKind::TextureSample:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    for (HIRExpression &child : expression.children) {
      changed =
          propagateLocalScalarConstantsInExpression(child, constants) ||
          changed;
    }
    return changed;
  }
  return changed;
}

void eraseLocalScalarConstants(HIRLocalScalarConstantMap &constants,
                               const std::set<std::string> &names) {
  for (const std::string &name : names) {
    constants.erase(name);
  }
}

bool hasHIRCompoundLoopUpdateTokens(std::span<const Token> tokens) {
  for (std::size_t index = 0; index < tokens.size(); ++index) {
    const Token &token = tokens[index];
    if (token.text == "+=" || token.text == "-=" || token.text == "*=" ||
        token.text == "/=" || token.text == "%=" || token.text == "++" ||
        token.text == "--") {
      return true;
    }
    if ((token.text == "+" || token.text == "-" || token.text == "*" ||
         token.text == "/" || token.text == "%") &&
        index + 1 < tokens.size() && tokens[index + 1].text == "=") {
      return true;
    }
  }
  return false;
}

bool propagateLocalScalarConstantsInBlock(
    std::vector<HIRStatement> &statements,
    HIRLocalScalarConstantMap &constants);

bool propagateLocalScalarConstantsInScopedBlock(
    std::vector<HIRStatement> &statements,
    const HIRLocalScalarConstantMap &constants) {
  HIRLocalScalarConstantMap scopedConstants = constants;
  return propagateLocalScalarConstantsInBlock(statements, scopedConstants);
}

bool propagateLocalScalarConstantsInStatement(
    HIRStatement &statement, HIRLocalScalarConstantMap &constants,
    const std::set<std::string> &assignedNames) {
  bool changed = false;
  switch (statement.kind) {
  case HIRStatementKind::Declaration: {
    changed =
        propagateLocalScalarConstantsInExpression(statement.value, constants) ||
        changed;
    if (!statement.name.empty()) {
      constants.erase(statement.name);
      if (assignedNames.find(statement.name) == assignedNames.end()) {
        if (std::optional<HIRLocalScalarConstant> localConstant =
                localScalarConstantFromDeclaration(statement)) {
          constants[statement.name] = std::move(*localConstant);
        }
      }
    }
    return changed;
  }
  case HIRStatementKind::Assignment:
    changed =
        propagateLocalScalarConstantsInAssignmentTarget(statement.target,
                                                       constants) ||
        changed;
    changed =
        propagateLocalScalarConstantsInExpression(statement.value, constants) ||
        changed;
    if (std::optional<std::string> name =
            hirExpressionRootIdentifier(statement.target)) {
      constants.erase(*name);
    }
    return changed;
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
    changed =
        propagateLocalScalarConstantsInExpression(statement.value, constants) ||
        changed;
    return changed;
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
    constants.clear();
    return false;
  case HIRStatementKind::Block:
    changed =
        propagateLocalScalarConstantsInScopedBlock(statement.body, constants) ||
        changed;
    return changed;
  case HIRStatementKind::If: {
    changed =
        propagateLocalScalarConstantsInExpression(statement.value, constants) ||
        changed;
    changed =
        propagateLocalScalarConstantsInScopedBlock(statement.body, constants) ||
        changed;
    changed = propagateLocalScalarConstantsInScopedBlock(statement.elseBody,
                                                         constants) ||
              changed;
    std::set<std::string> branchAssignedNames;
    for (const HIRStatement &child : statement.body) {
      collectHIRAssignedNames(child, branchAssignedNames);
    }
    for (const HIRStatement &child : statement.elseBody) {
      collectHIRAssignedNames(child, branchAssignedNames);
    }
    eraseLocalScalarConstants(constants, branchAssignedNames);
    return changed;
  }
  case HIRStatementKind::For: {
    HIRLocalScalarConstantMap loopConstants = constants;
    changed = propagateLocalScalarConstantsInBlock(statement.initializer,
                                                  loopConstants) ||
              changed;
    std::set<std::string> loopInitializerNames;
    for (const HIRStatement &initializer : statement.initializer) {
      if (initializer.kind == HIRStatementKind::Declaration &&
          !initializer.name.empty()) {
        loopInitializerNames.insert(initializer.name);
      }
    }
    eraseLocalScalarConstants(loopConstants, loopInitializerNames);

    std::set<std::string> loopCarriedNames;
    for (const HIRStatement &update : statement.update) {
      collectHIRAssignedNames(update, loopCarriedNames);
    }
    for (const HIRStatement &child : statement.body) {
      collectHIRAssignedNames(child, loopCarriedNames);
    }
    eraseLocalScalarConstants(loopConstants, loopCarriedNames);
    if (!statement.updateTokens.empty() && statement.update.empty()) {
      loopConstants.clear();
    }

    changed =
        propagateLocalScalarConstantsInExpression(statement.value,
                                                  loopConstants) ||
        changed;
    if (!hasHIRCompoundLoopUpdateTokens(statement.updateTokens)) {
      changed =
          mutateHIRLoopUpdate(
              statement, [&](std::vector<HIRStatement> &update) {
                return propagateLocalScalarConstantsInScopedBlock(
                    update, loopConstants);
              }) ||
          changed;
    }
    changed =
        propagateLocalScalarConstantsInScopedBlock(statement.body,
                                                  loopConstants) ||
        changed;

    std::set<std::string> assignedInLoop;
    for (const HIRStatement &initializer : statement.initializer) {
      collectHIRAssignedNames(initializer, assignedInLoop);
    }
    for (const HIRStatement &update : statement.update) {
      collectHIRAssignedNames(update, assignedInLoop);
    }
    for (const HIRStatement &child : statement.body) {
      collectHIRAssignedNames(child, assignedInLoop);
    }
    eraseLocalScalarConstants(constants, assignedInLoop);
    return changed;
  }
  case HIRStatementKind::Raw:
    constants.clear();
    return false;
  }
  return changed;
}

bool propagateLocalScalarConstantsInBlock(
    std::vector<HIRStatement> &statements,
    HIRLocalScalarConstantMap &constants) {
  bool changed = false;
  std::set<std::string> assignedNames;
  for (const HIRStatement &statement : statements) {
    collectHIRAssignedNames(statement, assignedNames);
  }

  for (HIRStatement &statement : statements) {
    changed = propagateLocalScalarConstantsInStatement(statement, constants,
                                                       assignedNames) ||
              changed;
  }
  return changed;
}

bool propagateLocalScalarConstantsInFunction(HIRFunction &function) {
  HIRLocalScalarConstantMap constants;
  return mutateHIRFunctionBody(
      function, [&](std::vector<HIRStatement> &body) {
        return propagateLocalScalarConstantsInBlock(body, constants);
      });
}

bool propagateLocalScalarConstants(HIRModule &module, DiagnosticEngine &) {
  bool changed = false;
  for (HIRFunction &function : module.functions) {
    changed = propagateLocalScalarConstantsInFunction(function) || changed;
  }
  for (HIRStage &stage : module.stages) {
    for (HIRFunction &function : stage.functions) {
      changed = propagateLocalScalarConstantsInFunction(function) || changed;
    }
  }
  return changed;
}

bool canInlineConstantHIRBranch(std::span<const HIRStatement> statements) {
  for (const HIRStatement &statement : statements) {
    switch (statement.kind) {
    case HIRStatementKind::Declaration:
    case HIRStatementKind::Raw:
      return false;
    case HIRStatementKind::Assignment:
    case HIRStatementKind::Return:
    case HIRStatementKind::Expression:
    case HIRStatementKind::Break:
    case HIRStatementKind::Continue:
    case HIRStatementKind::Discard:
    case HIRStatementKind::Block:
    case HIRStatementKind::If:
    case HIRStatementKind::For:
      break;
    }
  }
  return true;
}

HIRStatement makeScopedHIRBlock(std::vector<HIRStatement> body) {
  HIRStatement block;
  block.kind = HIRStatementKind::Block;
  block.body = std::move(body);
  return block;
}

bool cleanupConstantHIRBranchesInBlock(std::vector<HIRStatement> &statements);

bool cleanupConstantHIRBranchesInStatement(HIRStatement &statement) {
  bool changed = false;
  switch (statement.kind) {
  case HIRStatementKind::Block:
    changed = cleanupConstantHIRBranchesInBlock(statement.body) || changed;
    return changed;
  case HIRStatementKind::If:
    changed = cleanupConstantHIRBranchesInBlock(statement.body) || changed;
    changed = cleanupConstantHIRBranchesInBlock(statement.elseBody) || changed;
    return changed;
  case HIRStatementKind::For:
    changed =
        cleanupConstantHIRBranchesInBlock(statement.initializer) || changed;
    changed =
        mutateHIRLoopUpdate(statement, cleanupConstantHIRBranchesInBlock) ||
        changed;
    changed = cleanupConstantHIRBranchesInBlock(statement.body) || changed;
    return changed;
  case HIRStatementKind::Declaration:
  case HIRStatementKind::Assignment:
  case HIRStatementKind::Return:
  case HIRStatementKind::Expression:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Raw:
    return false;
  }
  return false;
}

bool cleanupConstantHIRBranchesInBlock(std::vector<HIRStatement> &statements) {
  bool changed = false;
  for (std::size_t index = 0; index < statements.size();) {
    HIRStatement &statement = statements[index];
    changed = cleanupConstantHIRBranchesInStatement(statement) || changed;

    if (statement.kind != HIRStatementKind::If) {
      ++index;
      continue;
    }

    const std::optional<bool> condition =
        literalHIRBoolCondition(statement.value);
    if (!condition.has_value()) {
      ++index;
      continue;
    }

    std::vector<HIRStatement> &selected =
        *condition ? statement.body : statement.elseBody;
    if (selected.empty()) {
      statements.erase(statements.begin() +
                       static_cast<std::ptrdiff_t>(index));
      changed = true;
      continue;
    }

    if (canInlineConstantHIRBranch(selected)) {
      std::vector<HIRStatement> replacement = std::move(selected);
      const std::size_t replacementSize = replacement.size();
      auto insertAt =
          statements.erase(statements.begin() +
                           static_cast<std::ptrdiff_t>(index));
      statements.insert(insertAt,
                        std::make_move_iterator(replacement.begin()),
                        std::make_move_iterator(replacement.end()));
      index += replacementSize;
      changed = true;
      continue;
    }

    HIRStatement block = makeScopedHIRBlock(std::move(selected));
    statements[index] = std::move(block);
    changed = true;
    ++index;
  }
  return changed;
}

bool cleanupConstantHIRBranches(HIRModule &module, DiagnosticEngine &) {
  bool changed = false;
  for (HIRFunction &function : module.functions) {
    changed =
        mutateHIRFunctionBody(function, cleanupConstantHIRBranchesInBlock) ||
        changed;
  }
  for (HIRStage &stage : module.stages) {
    for (HIRFunction &function : stage.functions) {
      changed =
          mutateHIRFunctionBody(function, cleanupConstantHIRBranchesInBlock) ||
          changed;
    }
  }
  return changed;
}

struct HIRStorageBufferResourceFieldIssue {
  HIRType type;
  std::string path;
};

bool isHIRDescriptorResourceFieldType(const HIRType &type) {
  const std::string baseName = baseTypeName(type);
  return isTextureResourceType(baseName) || isSamplerResourceType(baseName) ||
         isStorageImageResourceType(baseName);
}

const HIRStruct *findHIRStorageBufferStruct(std::span<const HIRStruct> structs,
                                            std::string_view name) {
  for (const HIRStruct &structure : structs) {
    if (structure.name == name) {
      return &structure;
    }
  }
  return nullptr;
}

void collectHIRStorageBufferResourceFieldIssues(
    const HIRType &type, std::string_view path,
    std::span<const HIRStruct> structs, std::set<std::string> &visiting,
    std::vector<HIRStorageBufferResourceFieldIssue> &issues) {
  if (isHIRDescriptorResourceFieldType(type)) {
    issues.push_back(HIRStorageBufferResourceFieldIssue{type,
                                                        std::string(path)});
    return;
  }

  if (type.arraySize.has_value()) {
    collectHIRStorageBufferResourceFieldIssues(arrayElementType(type), path,
                                               structs, visiting, issues);
    return;
  }

  const std::string structName = baseTypeName(type);
  const HIRStruct *structure = findHIRStorageBufferStruct(structs, structName);
  if (structure == nullptr || !visiting.insert(structName).second) {
    return;
  }

  for (const HIRField &field : structure->fields) {
    const std::string fieldPath =
        path.empty() ? field.name : std::string(path) + "." + field.name;
    collectHIRStorageBufferResourceFieldIssues(field.type, fieldPath, structs,
                                               visiting, issues);
  }

  visiting.erase(structName);
}

std::vector<HIRStorageBufferResourceFieldIssue>
collectHIRStorageBufferResourceFieldIssues(const HIRType &elementType,
                                           std::span<const HIRStruct> structs,
                                           std::string_view resourcePath) {
  std::set<std::string> visiting;
  std::vector<HIRStorageBufferResourceFieldIssue> issues;
  collectHIRStorageBufferResourceFieldIssues(elementType, resourcePath, structs,
                                             visiting, issues);
  return issues;
}

bool validateHIRStorageBufferShapes(HIRModule &module,
                                    DiagnosticEngine &diagnostics) {
  for (const HIRStage &stage : module.stages) {
    const std::string stageLabel =
        stage.stage.empty() ? std::string("<unnamed>") : stage.stage;
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind != HIRResourceKind::Buffer) {
        continue;
      }
      const std::string resourceName =
          resource.name.empty() ? std::string("<unnamed>") : resource.name;
      for (const HIRStorageBufferShapeIssue &issue :
           collectHIRStorageBufferShapeIssues(bufferElementType(resource.type),
                                              module.structs, resourceName)) {
        switch (issue.kind) {
        case HIRStorageBufferShapeIssueKind::RuntimeArrayField:
          diagnostics.error(
              "opt.hir-storage-buffer-runtime-array-field",
              "HIR stage '" + stageLabel + "' storage-buffer resource '" +
                  resourceName + "' runtime array field '" + issue.path +
                  "' must be the direct final field of the storage-buffer "
                  "element struct",
              issue.type.location);
          break;
        case HIRStorageBufferShapeIssueKind::RecursiveStruct:
          diagnostics.error(
              "opt.hir-storage-buffer-recursive-struct",
              "HIR stage '" + stageLabel + "' storage-buffer resource '" +
                  resourceName + "' recursive struct field '" + issue.path +
                  "' with type '" + formatType(issue.type) +
                  "' cannot have a finite storage-buffer layout",
              issue.type.location);
          break;
        }
      }
      for (const HIRStorageBufferResourceFieldIssue &issue :
           collectHIRStorageBufferResourceFieldIssues(
               bufferElementType(resource.type), module.structs,
               resourceName)) {
        diagnostics.error(
            "opt.hir-storage-buffer-resource-field",
            "HIR stage '" + stageLabel + "' storage-buffer resource '" +
                resourceName + "' field '" + issue.path +
                "' has descriptor/resource type '" + formatType(issue.type) +
                "', which cannot be stored in a storage-buffer layout; use a "
                "top-level resource descriptor instead",
            issue.type.location);
      }
    }
  }

  return false;
}

constexpr HIRPassMetadata kValidateModuleShapePass{
    "hir.validate.module-shape", "hir.validate.module-shape", "validation"};
constexpr HIRPassMetadata kValidateTypedSymbolsPass{
    "hir.validate.typed-symbols", "hir.validate.typed-symbols", "validation"};
constexpr HIRPassMetadata kFoldConstantIntrinsicsPass{
    "hir.optimize.fold-constant-intrinsics",
    "hir.optimize.fold-constant-intrinsics", "optimization"};
constexpr HIRPassMetadata kSimplifyAlgebraicPass{
    "hir.optimize.simplify-algebraic", "hir.optimize.simplify-algebraic",
    "optimization"};
constexpr HIRPassMetadata kPropagateLocalScalarsPass{
    "hir.optimize.propagate-local-scalars",
    "hir.optimize.propagate-local-scalars", "optimization"};
constexpr HIRPassMetadata kCleanupConstantBranchesPass{
    "hir.optimize.cleanup-constant-branches",
    "hir.optimize.cleanup-constant-branches", "cleanup"};
constexpr HIRPassMetadata kCleanupUnreachableStatementsPass{
    "hir.optimize.cleanup-unreachable-statements",
    "hir.optimize.cleanup-unreachable-statements", "cleanup"};
constexpr HIRPassMetadata kCleanupDeadLocalDeclarationsPass{
    "hir.optimize.cleanup-dead-local-declarations",
    "hir.optimize.cleanup-dead-local-declarations", "cleanup"};
constexpr HIRPassMetadata kCleanupDeadLocalStoresPass{
    "hir.optimize.cleanup-dead-local-stores",
    "hir.optimize.cleanup-dead-local-stores", "cleanup"};
constexpr HIRPassMetadata kInlineO2ScalarTemporariesPass{
    "hir.optimize.o2.inline-scalar-temporaries",
    "hir.optimize.o2.inline-scalar-temporaries", "optimization"};
constexpr HIRPassMetadata kInlineO2LiteralVectorTemporariesPass{
    "hir.optimize.o2.inline-literal-vector-temporaries",
    "hir.optimize.o2.inline-literal-vector-temporaries", "optimization"};
constexpr HIRPassMetadata kValidateStorageBufferShapesPass{
    "hir.validate.storage-buffer-shapes",
    "hir.validate.storage-buffer-shapes", "validation"};
constexpr HIRPassMetadata kValidateBackendInputPass{
    "hir.validate.backend-input", "hir.validate.backend-input", "validation"};

const std::array<HIRPass, 11> kDefaultHIRPasses = {
    HIRPass{kValidateModuleShapePass, validateHIRModuleShape},
    HIRPass{kValidateTypedSymbolsPass, validateHIRTypedSymbols},
    HIRPass{kFoldConstantIntrinsicsPass, foldConstantHIRIntrinsics},
    HIRPass{kSimplifyAlgebraicPass, simplifyAlgebraicHIR},
    HIRPass{kPropagateLocalScalarsPass, propagateLocalScalarConstants},
    HIRPass{kCleanupConstantBranchesPass, cleanupConstantHIRBranches},
    HIRPass{kCleanupUnreachableStatementsPass, cleanupUnreachableHIRStatements},
    HIRPass{kCleanupDeadLocalDeclarationsPass, cleanupDeadHIRLocalDeclarations},
    HIRPass{kCleanupDeadLocalStoresPass, cleanupDeadHIRLocalStores},
    HIRPass{kValidateStorageBufferShapesPass, validateHIRStorageBufferShapes},
    HIRPass{kValidateBackendInputPass, validateHIRBackendInput},
};

const std::array<HIRPass, 13> kO2HIRPasses = {
    HIRPass{kValidateModuleShapePass, validateHIRModuleShape},
    HIRPass{kValidateTypedSymbolsPass, validateHIRTypedSymbols},
    HIRPass{kFoldConstantIntrinsicsPass, foldConstantHIRIntrinsics},
    HIRPass{kSimplifyAlgebraicPass, simplifyAlgebraicHIR},
    HIRPass{kPropagateLocalScalarsPass, propagateLocalScalarConstants},
    HIRPass{kCleanupConstantBranchesPass, cleanupConstantHIRBranches},
    HIRPass{kCleanupUnreachableStatementsPass, cleanupUnreachableHIRStatements},
    HIRPass{kCleanupDeadLocalDeclarationsPass, cleanupDeadHIRLocalDeclarations},
    HIRPass{kCleanupDeadLocalStoresPass, cleanupDeadHIRLocalStores},
    HIRPass{kInlineO2ScalarTemporariesPass, inlineO2ScalarTemporaries},
    HIRPass{kInlineO2LiteralVectorTemporariesPass,
            inlineO2LiteralVectorTemporaries},
    HIRPass{kValidateStorageBufferShapesPass, validateHIRStorageBufferShapes},
    HIRPass{kValidateBackendInputPass, validateHIRBackendInput},
};

const std::array<HIRPass, 3> kO0SourceValidationPasses = {
    HIRPass{kValidateModuleShapePass, validateHIRModuleShape},
    HIRPass{kValidateTypedSymbolsPass, validateHIRTypedSymbols},
    HIRPass{kValidateStorageBufferShapesPass, validateHIRStorageBufferShapes},
};

const std::array<HIRPass, 4> kO0BackendValidationPasses = {
    HIRPass{kValidateModuleShapePass, validateHIRModuleShape},
    HIRPass{kValidateTypedSymbolsPass, validateHIRTypedSymbols},
    HIRPass{kValidateStorageBufferShapesPass, validateHIRStorageBufferShapes},
    HIRPass{kValidateBackendInputPass, validateHIRBackendInput},
};

constexpr std::string_view kHIRPassScheduleFingerprintPolicy =
    "scheduled-pass-ids-v1";
constexpr std::string_view kStableOptLevelPassSchedule =
    "stable-opt-level-policy";
constexpr std::uint64_t kFNV1a64Offset = 14695981039346656037ull;
constexpr std::uint64_t kFNV1a64Prime = 1099511628211ull;

void updateFNV1a64(std::uint64_t &hash, std::uint8_t byte) {
  hash ^= byte;
  hash *= kFNV1a64Prime;
}

void updateFNV1a64(std::uint64_t &hash, std::string_view value) {
  std::uint64_t size = static_cast<std::uint64_t>(value.size());
  for (unsigned shift = 0; shift < 64; shift += 8) {
    updateFNV1a64(hash, static_cast<std::uint8_t>((size >> shift) & 0xffu));
  }
  for (const char byte : value) {
    updateFNV1a64(hash, static_cast<std::uint8_t>(
                            static_cast<unsigned char>(byte)));
  }
}

std::string formatFNV1a64(std::uint64_t hash) {
  std::ostringstream out;
  out << "fnv1a64:" << std::hex << std::nouppercase << std::setfill('0')
      << std::setw(16) << hash;
  return out.str();
}

} // namespace

std::string_view hirPassStatusName(HIRPassStatus status) {
  switch (status) {
  case HIRPassStatus::Completed:
    return "completed";
  case HIRPassStatus::Failed:
    return "failed";
  }
  return "unknown";
}

std::string_view optimizationLevelName(OptimizationLevel level) {
  switch (level) {
  case OptimizationLevel::O0:
    return "O0";
  case OptimizationLevel::O1:
    return "O1";
  case OptimizationLevel::O2:
    return "O2";
  }
  return "O1";
}

std::string_view hirVerifierModeName(HIRVerifierMode mode) {
  switch (mode) {
  case HIRVerifierMode::Source:
    return "source-validation";
  case HIRVerifierMode::BackendInput:
    return "backend-input-validation";
  }
  return "backend-input-validation";
}

std::optional<OptimizationLevel> parseOptimizationLevel(
    std::string_view value) {
  if (value == "O0") {
    return OptimizationLevel::O0;
  }
  if (value == "O1") {
    return OptimizationLevel::O1;
  }
  if (value == "O2") {
    return OptimizationLevel::O2;
  }
  return std::nullopt;
}

std::string hirPassScheduleFingerprint(std::span<const HIRPass> passes) {
  std::uint64_t hash = kFNV1a64Offset;
  updateFNV1a64(hash, kHIRPassScheduleFingerprintPolicy);
  for (const HIRPass &pass : passes) {
    updateFNV1a64(hash, pass.id);
  }
  return formatFNV1a64(hash);
}

namespace {

std::size_t countHIRExpressions(const HIRExpression &expression) {
  std::size_t count = expression.kind == HIRExpressionKind::Empty ? 0 : 1;
  for (const HIRExpression &child : expression.children) {
    count += countHIRExpressions(child);
  }
  return count;
}

void addHIRStatementStats(const std::vector<HIRStatement> &statements,
                          HIRModuleStats &stats) {
  for (const HIRStatement &statement : statements) {
    ++stats.statementCount;
    stats.expressionCount += countHIRExpressions(statement.target);
    stats.expressionCount += countHIRExpressions(statement.value);
    addHIRStatementStats(statement.initializer, stats);
    addHIRStatementStats(statement.update, stats);
    addHIRStatementStats(statement.body, stats);
    addHIRStatementStats(statement.elseBody, stats);
  }
}

void addHIRFunctionStats(const HIRFunction &function, HIRModuleStats &stats) {
  addHIRStatementStats(function.body, stats);
}

HIRModuleStats hirModuleStats(const HIRModule &module) {
  HIRModuleStats stats;
  stats.structCount = module.structs.size();
  stats.constantCount = module.constants.size();
  stats.stageCount = module.stages.size();
  stats.functionCount = module.functions.size();

  for (const HIRConstant &constant : module.constants) {
    stats.expressionCount += countHIRExpressions(constant.value);
  }
  for (const HIRFunction &function : module.functions) {
    addHIRFunctionStats(function, stats);
  }
  for (const HIRStage &stage : module.stages) {
    stats.resourceCount += stage.resources.size();
    stats.functionCount += stage.functions.size();
    for (const HIRFunction &function : stage.functions) {
      addHIRFunctionStats(function, stats);
    }
  }
  return stats;
}

std::size_t hirModuleStatDelta(std::size_t before, std::size_t after) {
  return before <= after ? after - before : before - after;
}

HIRModuleStats hirModuleStatsDelta(const HIRModuleStats &before,
                                   const HIRModuleStats &after) {
  return HIRModuleStats{
      hirModuleStatDelta(before.structCount, after.structCount),
      hirModuleStatDelta(before.constantCount, after.constantCount),
      hirModuleStatDelta(before.stageCount, after.stageCount),
      hirModuleStatDelta(before.resourceCount, after.resourceCount),
      hirModuleStatDelta(before.functionCount, after.functionCount),
      hirModuleStatDelta(before.statementCount, after.statementCount),
      hirModuleStatDelta(before.expressionCount, after.expressionCount)};
}

void appendHIRModuleStatsJson(std::ostream &out, const HIRModuleStats &stats,
                              std::string_view indent) {
  out << indent << "\"structCount\": " << stats.structCount << ",\n"
      << indent << "\"constantCount\": " << stats.constantCount << ",\n"
      << indent << "\"stageCount\": " << stats.stageCount << ",\n"
      << indent << "\"resourceCount\": " << stats.resourceCount << ",\n"
      << indent << "\"functionCount\": " << stats.functionCount << ",\n"
      << indent << "\"statementCount\": " << stats.statementCount << ",\n"
      << indent << "\"expressionCount\": " << stats.expressionCount << "\n";
}

struct HIRPassPolicyMetadata {
  std::string_view id;
  std::string_view name;
  std::string_view description;
  std::string_view backendInputMode;
  std::string_view passScheduleStability;
};

std::string_view backendInputModeName(bool validateBackendInput) {
  return validateBackendInput ? "backend-input-validation"
                              : "source-validation";
}

HIRPassPolicyMetadata hirPassPolicyMetadataForConfig(
    HIRPassPipelineConfig config) {
  switch (config.optimizationLevel) {
  case OptimizationLevel::O0:
    return HIRPassPolicyMetadata{
        "hir-o0-validation-only", "O0 validation-only",
        "Validation-only HIR policy; no optimization transforms are scheduled.",
        backendInputModeName(config.validateBackendInput),
        kStableOptLevelPassSchedule};
  case OptimizationLevel::O1:
    return HIRPassPolicyMetadata{
        "hir-o1-safe-cleanup", "O1 safe cleanup",
        "Default safe HIR cleanup and folding policy.",
        backendInputModeName(config.validateBackendInput),
        kStableOptLevelPassSchedule};
  case OptimizationLevel::O2:
    return HIRPassPolicyMetadata{
        "hir-o2-conservative-inline", "O2 conservative inline",
        "O1 safe cleanup plus conservative temporary inlining.",
        backendInputModeName(config.validateBackendInput),
        kStableOptLevelPassSchedule};
  }
  return HIRPassPolicyMetadata{
      "hir-o1-safe-cleanup", "O1 safe cleanup",
      "Default safe HIR cleanup and folding policy.",
      backendInputModeName(config.validateBackendInput),
      kStableOptLevelPassSchedule};
}

void applyHIRPassPolicyMetadata(HIRPassPipelineResult &result,
                                HIRPassPolicyMetadata metadata) {
  result.optimizationPolicyId = std::string(metadata.id);
  result.optimizationPolicyName = std::string(metadata.name);
  result.optimizationPolicyDescription = std::string(metadata.description);
  result.backendInputMode = std::string(metadata.backendInputMode);
  result.passScheduleStability = std::string(metadata.passScheduleStability);
}

} // namespace

std::span<const HIRPass> defaultHIRPassPipeline() {
  return kDefaultHIRPasses;
}

std::span<const HIRPass> sourceValidationHIRPassPipeline() {
  return {kDefaultHIRPasses.data(), kDefaultHIRPasses.size() - 1};
}

std::span<const HIRPass> hirVerifierPassPipeline(HIRVerifierMode mode) {
  switch (mode) {
  case HIRVerifierMode::Source:
    return kO0SourceValidationPasses;
  case HIRVerifierMode::BackendInput:
    return kO0BackendValidationPasses;
  }
  return kO0BackendValidationPasses;
}

std::span<const HIRPass>
hirPassPipelineForConfig(HIRPassPipelineConfig config) {
  switch (config.optimizationLevel) {
  case OptimizationLevel::O0:
    if (config.validateBackendInput) {
      return kO0BackendValidationPasses;
    }
    return kO0SourceValidationPasses;
  case OptimizationLevel::O1:
    break;
  case OptimizationLevel::O2:
    if (config.validateBackendInput) {
      return kO2HIRPasses;
    }
    return {kO2HIRPasses.data(), kO2HIRPasses.size() - 1};
  }
  return config.validateBackendInput ? defaultHIRPassPipeline()
                                     : sourceValidationHIRPassPipeline();
}

HIRPassPipelineResult verifyHIRModule(HIRModule &module,
                                      DiagnosticEngine &diagnostics,
                                      HIRVerifierConfig config) {
  HIRPassPipelineConfig passConfig;
  passConfig.optimizationLevel = OptimizationLevel::O0;
  passConfig.validateBackendInput =
      config.mode == HIRVerifierMode::BackendInput;
  return runHIRPassPipeline(module, diagnostics, passConfig);
}

HIRPassPipelineResult runHIRPassPipeline(HIRModule &module,
                                         DiagnosticEngine &diagnostics,
                                         std::span<const HIRPass> passes) {
  HIRPassPipelineResult result;
  result.scheduledPassCount = passes.size();
  result.passScheduleFingerprint = hirPassScheduleFingerprint(passes);
  result.passScheduleFingerprintPolicy =
      std::string(kHIRPassScheduleFingerprintPolicy);
  for (const HIRPass &pass : passes) {
    const std::string passId =
        pass.id.empty() ? std::string("<unnamed>") : std::string(pass.id);
    const std::string passName =
        pass.name.empty() ? passId : std::string(pass.name);
    const std::string passCategory =
        pass.category.empty() ? std::string("<uncategorized>")
                              : std::string(pass.category);
    if (pass.id.empty() || pass.name.empty()) {
      diagnostics.error("opt.pass-unnamed",
                        "HIR optimization pass must have an id and name");
      result.completed = false;
      result.stopReason = "unnamed-pass";
      break;
    }
    if (pass.category.empty()) {
      diagnostics.error("opt.pass-missing-category",
                        "HIR optimization pass '" + passId +
                            "' must have a category");
      result.completed = false;
      result.stopReason = "missing-category";
      break;
    }
    if (!pass.run) {
      diagnostics.error("opt.pass-missing-runner",
                        "HIR optimization pass '" + passId +
                            "' has no runner");
      result.completed = false;
      result.stopReason = "missing-runner";
      break;
    }

    const std::size_t diagnosticCountBefore =
        diagnostics.diagnostics().size();
    const HIRModuleStats moduleStatsBefore = hirModuleStats(module);
    const auto passStart = std::chrono::steady_clock::now();
    const bool passChanged = pass.run(module, diagnostics);
    const auto passEnd = std::chrono::steady_clock::now();
    const HIRModuleStats moduleStatsAfter = hirModuleStats(module);
    const auto elapsedTimeMicroseconds =
        static_cast<std::uint64_t>(std::chrono::duration_cast<
                                   std::chrono::microseconds>(passEnd -
                                                              passStart)
                                       .count());
    const std::vector<Diagnostic> &diagnosticList = diagnostics.diagnostics();
    const auto passDiagnosticBegin =
        diagnosticList.begin() +
        static_cast<std::vector<Diagnostic>::difference_type>(
            diagnosticCountBefore);
    const std::size_t passDiagnosticCount =
        diagnosticList.size() - diagnosticCountBefore;
    const std::size_t passErrorCount = static_cast<std::size_t>(
        std::count_if(passDiagnosticBegin, diagnosticList.end(),
                      [](const Diagnostic &diagnostic) {
                        return diagnostic.severity ==
                               DiagnosticSeverity::Error;
                      }));
    const HIRPassStatus passStatus =
        passErrorCount == 0 ? HIRPassStatus::Completed : HIRPassStatus::Failed;
    result.passes.push_back(HIRPassResult{
        passId,
        passName,
        passCategory,
        passChanged,
        passStatus,
        passDiagnosticCount,
        passErrorCount,
        elapsedTimeMicroseconds,
        moduleStatsBefore,
        moduleStatsAfter,
        hirModuleStatsDelta(moduleStatsBefore, moduleStatsAfter)});
    result.passCount = result.passes.size();
    result.changed = result.changed || passChanged;
    if (passChanged) {
      ++result.changedPassCount;
    }
    if (passDiagnosticCount != 0) {
      ++result.diagnosticPassCount;
    }
    if (passErrorCount != 0) {
      ++result.errorPassCount;
    }
    if (diagnostics.hasErrors()) {
      result.completed = false;
      result.stopReason =
          passErrorCount == 0 ? "diagnostics" : "pass-error";
      break;
    }
  }
  return result;
}

HIRPassPipelineResult runHIRPassPipeline(HIRModule &module,
                                         DiagnosticEngine &diagnostics,
                                         HIRPassPipelineConfig config) {
  HIRPassPipelineResult result = runHIRPassPipeline(
      module, diagnostics, hirPassPipelineForConfig(config));
  result.optimizationLevel = config.optimizationLevel;
  applyHIRPassPolicyMetadata(result, hirPassPolicyMetadataForConfig(config));
  return result;
}

HIRPassPipelineResult runHIRPassPipeline(HIRModule &module,
                                         DiagnosticEngine &diagnostics) {
  return runHIRPassPipeline(module, diagnostics, HIRPassPipelineConfig{});
}

std::string hirPassTraceJson(const HIRPassPipelineResult &result,
                             HIRPassTraceJsonOptions options) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"kind\": \"hir-pass-trace\",\n"
      << "  \"optimizationLevel\": \""
      << escapeJson(std::string(optimizationLevelName(result.optimizationLevel)))
      << "\",\n"
      << "  \"optimizationPolicy\": {\n"
      << "    \"id\": \"" << escapeJson(result.optimizationPolicyId)
      << "\",\n"
      << "    \"name\": \"" << escapeJson(result.optimizationPolicyName)
      << "\",\n"
      << "    \"description\": \""
      << escapeJson(result.optimizationPolicyDescription) << "\",\n"
      << "    \"backendInputMode\": \"" << escapeJson(result.backendInputMode)
      << "\"\n"
      << "  },\n"
      << "  \"passSchedule\": {\n"
      << "    \"fingerprint\": \""
      << escapeJson(result.passScheduleFingerprint) << "\",\n"
      << "    \"fingerprintPolicy\": \""
      << escapeJson(result.passScheduleFingerprintPolicy) << "\",\n"
      << "    \"stability\": \"" << escapeJson(result.passScheduleStability)
      << "\"\n"
      << "  },\n"
      << "  \"scheduledPassCount\": " << result.scheduledPassCount << ",\n"
      << "  \"passCount\": " << result.passCount << ",\n"
      << "  \"changedPassCount\": " << result.changedPassCount << ",\n"
      << "  \"diagnosticPassCount\": " << result.diagnosticPassCount << ",\n"
      << "  \"errorPassCount\": " << result.errorPassCount << ",\n"
      << "  \"changed\": " << (result.changed ? "true" : "false") << ",\n"
      << "  \"completed\": " << (result.completed ? "true" : "false")
      << ",\n"
      << "  \"stopReason\": \"" << escapeJson(result.stopReason) << "\",\n"
      << "  \"passes\": [";
  for (std::size_t index = 0; index < result.passes.size(); ++index) {
    const HIRPassResult &pass = result.passes[index];
    if (index != 0) {
      out << ",";
    }
    out << "\n"
        << "    {\n"
        << "      \"index\": " << index << ",\n"
        << "      \"id\": \"" << escapeJson(pass.id) << "\",\n"
        << "      \"name\": \"" << escapeJson(pass.name) << "\",\n"
        << "      \"category\": \"" << escapeJson(pass.category) << "\",\n"
        << "      \"changed\": " << (pass.changed ? "true" : "false")
        << ",\n"
        << "      \"status\": \""
        << escapeJson(std::string(hirPassStatusName(pass.status))) << "\",\n"
        << "      \"diagnosticCount\": " << pass.diagnosticCount << ",\n"
        << "      \"errorCount\": " << pass.errorCount;
    if (options.includeElapsedTimeMicroseconds) {
      out << ",\n"
          << "      \"elapsedTimeMicroseconds\": "
          << pass.elapsedTimeMicroseconds;
    }
    if (options.includeModuleStats) {
      out << ",\n"
          << "      \"moduleStats\": {\n"
          << "        \"before\": {\n";
      appendHIRModuleStatsJson(out, pass.moduleStatsBefore, "          ");
      out << "        },\n"
          << "        \"after\": {\n";
      appendHIRModuleStatsJson(out, pass.moduleStatsAfter, "          ");
      out << "        },\n"
          << "        \"delta\": {\n";
      appendHIRModuleStatsJson(out, pass.moduleStatsDelta, "          ");
      out << "        }\n"
          << "      }";
    }
    out << "\n"
        << "    }";
  }
  if (!result.passes.empty()) {
    out << "\n  ";
  }
  out << "]\n"
      << "}\n";
  return out.str();
}

} // namespace crossgl
