#pragma once

#include "crossgl/HIR/HIR.h"

namespace crossgl {

struct HIRSideEffectSummary {
  bool hasStructuralBuiltin = false;
  bool hasResourceRead = false;
  bool hasResourceWrite = false;
  bool hasUnknownCall = false;
  bool hasStore = false;
  bool hasControlTransfer = false;
  bool hasRawStatement = false;
};

HIRSideEffectSummary
summarizeHIRExpressionSideEffects(const HIRExpression &expression);
HIRSideEffectSummary
summarizeHIRStatementSideEffects(const HIRStatement &statement);

bool hasHIRSideEffects(const HIRSideEffectSummary &summary);
bool isKnownPureHIRExpression(const HIRExpression &expression);
bool isKnownPureHIRStatement(const HIRStatement &statement);

} // namespace crossgl
