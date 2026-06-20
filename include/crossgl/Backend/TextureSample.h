#pragma once

#include "crossgl/HIR/HIR.h"

#include <optional>

namespace crossgl {

struct TextureSampleOperands {
  const HIRExpression *texture = nullptr;
  const HIRExpression *sampler = nullptr;
  const HIRExpression *coordinate = nullptr;
  const HIRExpression *lod = nullptr;
};

std::optional<TextureSampleOperands>
textureSampleOperands(const HIRExpression &expression);

template <typename ResultTypeSupported, typename TextureOperandSupported,
          typename SamplerOperandSupported, typename ExpressionSupported>
bool textureSampleSupportedByPolicy(
    const HIRExpression &expression, ResultTypeSupported resultTypeSupported,
    TextureOperandSupported textureOperandSupported,
    SamplerOperandSupported samplerOperandSupported,
    ExpressionSupported expressionSupported) {
  const std::optional<TextureSampleOperands> operands =
      textureSampleOperands(expression);
  if (!operands.has_value() || !resultTypeSupported(expression.type)) {
    return false;
  }
  if (!textureOperandSupported(*operands->texture) ||
      !samplerOperandSupported(*operands->sampler)) {
    return false;
  }
  return expressionSupported(*operands->coordinate) &&
         expressionSupported(*operands->lod);
}

} // namespace crossgl
