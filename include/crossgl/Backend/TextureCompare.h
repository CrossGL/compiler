#pragma once

#include "crossgl/HIR/HIR.h"

#include <array>
#include <optional>
#include <string>
#include <string_view>

namespace crossgl {

enum class TextureCompareShape {
  Unknown,
  Shadow2D,
  Shadow2DArray,
  ShadowCube,
  ShadowCubeArray,
};

enum class TextureCompareOperator {
  Never,
  Always,
  Less,
  LessEqual,
  Equal,
  NotEqual,
  GreaterEqual,
  Greater,
};

struct TextureCompareOperands {
  bool explicitLod = false;
  const HIRExpression *texture = nullptr;
  const HIRExpression *sampler = nullptr;
  const HIRExpression *coordinate = nullptr;
  const HIRExpression *depth = nullptr;
  const HIRExpression *lod = nullptr;
};

struct TextureCompareManualOperands {
  const HIRExpression *texture = nullptr;
  const HIRExpression *sampler = nullptr;
  const HIRExpression *coordinate = nullptr;
  const HIRExpression *depth = nullptr;
  const HIRExpression *lod = nullptr;
  const HIRExpression *compareOp = nullptr;
  const HIRExpression *offset = nullptr;
  bool gather2x2 = false;
  bool kernelList = false;
  bool kernel4 = false;
  bool kernel8 = false;
  std::size_t kernelTapCount = 0;
  std::array<const HIRExpression *, kMaxManualTextureCompareKernelTaps>
      kernelOffsets = {};
  std::array<const HIRExpression *, kMaxManualTextureCompareKernelTaps>
      kernelWeights = {};
};

TextureCompareShape textureCompareShape(const HIRType &type);
std::string textureCompareShapeName(TextureCompareShape shape);
std::optional<TextureCompareOperator>
textureCompareOperatorFromName(std::string_view name);
std::optional<TextureCompareOperator>
textureCompareOperatorFromExpression(const HIRExpression &expression);
std::string textureCompareOperatorName(TextureCompareOperator compareOperator);
std::string_view
textureCompareOperatorConstantName(TextureCompareOperator compareOperator);
std::optional<std::string_view>
textureCompareOperatorBinarySymbol(TextureCompareOperator compareOperator);
std::string_view textureCompareOperatorList();

std::optional<TextureCompareOperands>
textureCompareOperands(const HIRExpression &expression);

std::optional<TextureCompareManualOperands>
textureCompareManualOperands(const HIRExpression &expression);
std::string textureCompareManualOperationName(
    const TextureCompareManualOperands &operands);

bool textureCompareHasScalarFloatResult(const HIRExpression &expression);

template <typename TextureOperandSupported, typename SamplerOperandSupported,
          typename ExpressionSupported, typename ExplicitLodTextureSupported>
bool textureCompareSupportedByPolicy(
    const HIRExpression &expression,
    TextureOperandSupported textureOperandSupported,
    SamplerOperandSupported samplerOperandSupported,
    ExpressionSupported expressionSupported,
    ExplicitLodTextureSupported explicitLodTextureSupported) {
  const std::optional<TextureCompareOperands> operands =
      textureCompareOperands(expression);
  if (!operands.has_value() || !textureCompareHasScalarFloatResult(expression)) {
    return false;
  }
  if (!textureOperandSupported(*operands->texture) ||
      !samplerOperandSupported(*operands->sampler)) {
    return false;
  }
  if (operands->explicitLod &&
      !explicitLodTextureSupported(*operands->texture)) {
    return false;
  }
  if (!expressionSupported(*operands->coordinate) ||
      !expressionSupported(*operands->depth)) {
    return false;
  }
  return operands->lod == nullptr || expressionSupported(*operands->lod);
}

template <typename TextureOperandSupported, typename SamplerOperandSupported,
          typename ExpressionSupported>
bool textureCompareManualSupportedByPolicy(
    const HIRExpression &expression,
    TextureOperandSupported textureOperandSupported,
    SamplerOperandSupported samplerOperandSupported,
    ExpressionSupported expressionSupported) {
  const std::optional<TextureCompareManualOperands> operands =
      textureCompareManualOperands(expression);
  if (!operands.has_value() || !textureCompareHasScalarFloatResult(expression)) {
    return false;
  }
  if (!textureOperandSupported(*operands->texture) ||
      !samplerOperandSupported(*operands->sampler)) {
    return false;
  }
  if (!expressionSupported(*operands->coordinate) ||
      !expressionSupported(*operands->depth) ||
      !expressionSupported(*operands->lod)) {
    return false;
  }
  if (operands->offset != nullptr &&
      !expressionSupported(*operands->offset)) {
    return false;
  }
  if (operands->kernelTapCount != 0) {
    for (std::size_t index = 0; index < operands->kernelTapCount; ++index) {
      if (operands->kernelOffsets[index] == nullptr ||
          operands->kernelWeights[index] == nullptr ||
          !expressionSupported(*operands->kernelOffsets[index]) ||
          !expressionSupported(*operands->kernelWeights[index])) {
        return false;
      }
    }
  }
  return textureCompareOperatorFromExpression(*operands->compareOp)
      .has_value();
}

} // namespace crossgl
