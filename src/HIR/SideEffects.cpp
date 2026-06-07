#include "crossgl/HIR/SideEffects.h"

#include "crossgl/HIR/BuiltinEffects.h"

#include <optional>
#include <vector>

namespace crossgl {
namespace {

void mergeHIRSideEffectSummary(HIRSideEffectSummary &target,
                               const HIRSideEffectSummary &source) {
  target.hasStructuralBuiltin =
      target.hasStructuralBuiltin || source.hasStructuralBuiltin;
  target.hasResourceRead = target.hasResourceRead || source.hasResourceRead;
  target.hasResourceWrite = target.hasResourceWrite || source.hasResourceWrite;
  target.hasUnknownCall = target.hasUnknownCall || source.hasUnknownCall;
  target.hasStore = target.hasStore || source.hasStore;
  target.hasControlTransfer =
      target.hasControlTransfer || source.hasControlTransfer;
  target.hasRawStatement = target.hasRawStatement || source.hasRawStatement;
}

void mergeHIRExpressionChildrenSideEffects(
    HIRSideEffectSummary &summary, const HIRExpression &expression) {
  for (const HIRExpression &child : expression.children) {
    mergeHIRSideEffectSummary(summary,
                              summarizeHIRExpressionSideEffects(child));
  }
}

void mergeHIRStatementListSideEffects(
    HIRSideEffectSummary &summary,
    const std::vector<HIRStatement> &statements) {
  for (const HIRStatement &statement : statements) {
    mergeHIRSideEffectSummary(summary,
                              summarizeHIRStatementSideEffects(statement));
  }
}

void summarizeHIRCallNodeSideEffects(HIRSideEffectSummary &summary,
                                     const HIRExpression &expression) {
  const std::optional<HIRBuiltinEffect> effect =
      resolveHIRCallEffect(expression.value, expression.children);
  if (!effect.has_value()) {
    summary.hasUnknownCall = true;
    return;
  }

  switch (*effect) {
  case HIRBuiltinEffect::Pure:
    return;
  case HIRBuiltinEffect::Opaque:
    if (!isHIRResourceWriteBuiltinCall(expression.value) &&
        !isHIRResourceReadBuiltinCall(expression.value)) {
      summary.hasUnknownCall = true;
      return;
    }
    if (isHIRResourceWriteBuiltinCall(expression.value)) {
      summary.hasResourceWrite = true;
    }
    if (isHIRResourceReadBuiltinCall(expression.value)) {
      summary.hasResourceRead = true;
    }
    return;
  case HIRBuiltinEffect::Structural:
    summary.hasStructuralBuiltin = true;
    return;
  }
}

} // namespace

HIRSideEffectSummary
summarizeHIRExpressionSideEffects(const HIRExpression &expression) {
  HIRSideEffectSummary summary;
  mergeHIRExpressionChildrenSideEffects(summary, expression);

  switch (expression.kind) {
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::Literal:
  case HIRExpressionKind::Group:
  case HIRExpressionKind::MemberAccess:
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::Constructor:
  case HIRExpressionKind::Unary:
  case HIRExpressionKind::Binary:
  case HIRExpressionKind::Select:
    return summary;
  case HIRExpressionKind::Call:
    summarizeHIRCallNodeSideEffects(summary, expression);
    return summary;
  case HIRExpressionKind::TextureSample:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    summary.hasResourceRead = true;
    return summary;
  }
  summary.hasUnknownCall = true;
  return summary;
}

HIRSideEffectSummary
summarizeHIRStatementSideEffects(const HIRStatement &statement) {
  HIRSideEffectSummary summary;
  mergeHIRSideEffectSummary(summary,
                            summarizeHIRExpressionSideEffects(statement.target));
  mergeHIRSideEffectSummary(summary,
                            summarizeHIRExpressionSideEffects(statement.value));
  mergeHIRStatementListSideEffects(summary, statement.initializer);
  mergeHIRStatementListSideEffects(summary, statement.update);
  mergeHIRStatementListSideEffects(summary, statement.body);
  mergeHIRStatementListSideEffects(summary, statement.elseBody);

  switch (statement.kind) {
  case HIRStatementKind::Declaration:
  case HIRStatementKind::Expression:
    return summary;
  case HIRStatementKind::Assignment:
    summary.hasStore = true;
    return summary;
  case HIRStatementKind::Return:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
    summary.hasControlTransfer = true;
    return summary;
  case HIRStatementKind::If:
  case HIRStatementKind::Block:
    return summary;
  case HIRStatementKind::For:
    if (!statement.updateTokens.empty() && statement.update.empty()) {
      summary.hasRawStatement = true;
    }
    return summary;
  case HIRStatementKind::Raw:
    summary.hasRawStatement = true;
    return summary;
  }
  summary.hasRawStatement = true;
  return summary;
}

bool hasHIRSideEffects(const HIRSideEffectSummary &summary) {
  return summary.hasStructuralBuiltin || summary.hasResourceRead ||
         summary.hasResourceWrite || summary.hasUnknownCall ||
         summary.hasStore || summary.hasControlTransfer ||
         summary.hasRawStatement;
}

bool isKnownPureHIRExpression(const HIRExpression &expression) {
  return !hasHIRSideEffects(summarizeHIRExpressionSideEffects(expression));
}

bool isKnownPureHIRStatement(const HIRStatement &statement) {
  return !hasHIRSideEffects(summarizeHIRStatementSideEffects(statement));
}

} // namespace crossgl
