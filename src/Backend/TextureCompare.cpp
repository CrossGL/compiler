#include "crossgl/Backend/TextureCompare.h"

namespace crossgl {

TextureCompareShape textureCompareShape(const HIRType &type) {
  if (type.name == "sampler2DShadow") {
    return TextureCompareShape::Shadow2D;
  }
  if (type.name == "sampler2DArrayShadow") {
    return TextureCompareShape::Shadow2DArray;
  }
  if (type.name == "samplerCubeShadow") {
    return TextureCompareShape::ShadowCube;
  }
  if (type.name == "samplerCubeArrayShadow") {
    return TextureCompareShape::ShadowCubeArray;
  }
  return TextureCompareShape::Unknown;
}

std::string textureCompareShapeName(TextureCompareShape shape) {
  switch (shape) {
  case TextureCompareShape::Shadow2D:
    return "sampler2DShadow";
  case TextureCompareShape::Shadow2DArray:
    return "sampler2DArrayShadow";
  case TextureCompareShape::ShadowCube:
    return "samplerCubeShadow";
  case TextureCompareShape::ShadowCubeArray:
    return "samplerCubeArrayShadow";
  case TextureCompareShape::Unknown:
    break;
  }
  return "unknown";
}

std::optional<TextureCompareOperator>
textureCompareOperatorFromName(std::string_view name) {
  if (name == "never") {
    return TextureCompareOperator::Never;
  }
  if (name == "always") {
    return TextureCompareOperator::Always;
  }
  if (name == "less") {
    return TextureCompareOperator::Less;
  }
  if (name == "less_equal") {
    return TextureCompareOperator::LessEqual;
  }
  if (name == "equal") {
    return TextureCompareOperator::Equal;
  }
  if (name == "not_equal") {
    return TextureCompareOperator::NotEqual;
  }
  if (name == "greater_equal") {
    return TextureCompareOperator::GreaterEqual;
  }
  if (name == "greater") {
    return TextureCompareOperator::Greater;
  }
  return std::nullopt;
}

std::optional<TextureCompareOperator>
textureCompareOperatorFromExpression(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Identifier ||
      !expression.type.name.empty() || expression.type.arraySize.has_value()) {
    return std::nullopt;
  }
  return textureCompareOperatorFromName(expression.value);
}

std::string textureCompareOperatorName(TextureCompareOperator compareOperator) {
  switch (compareOperator) {
  case TextureCompareOperator::Never:
    return "never";
  case TextureCompareOperator::Always:
    return "always";
  case TextureCompareOperator::Less:
    return "less";
  case TextureCompareOperator::LessEqual:
    return "less_equal";
  case TextureCompareOperator::Equal:
    return "equal";
  case TextureCompareOperator::NotEqual:
    return "not_equal";
  case TextureCompareOperator::GreaterEqual:
    return "greater_equal";
  case TextureCompareOperator::Greater:
    return "greater";
  }
  return "unknown";
}

std::string_view
textureCompareOperatorConstantName(TextureCompareOperator compareOperator) {
  switch (compareOperator) {
  case TextureCompareOperator::Never:
    return "CGL_COMPARE_NEVER";
  case TextureCompareOperator::Always:
    return "CGL_COMPARE_ALWAYS";
  case TextureCompareOperator::Less:
    return "CGL_COMPARE_LESS";
  case TextureCompareOperator::LessEqual:
    return "CGL_COMPARE_LESS_EQUAL";
  case TextureCompareOperator::Equal:
    return "CGL_COMPARE_EQUAL";
  case TextureCompareOperator::NotEqual:
    return "CGL_COMPARE_NOT_EQUAL";
  case TextureCompareOperator::GreaterEqual:
    return "CGL_COMPARE_GREATER_EQUAL";
  case TextureCompareOperator::Greater:
    return "CGL_COMPARE_GREATER";
  }
  return "CGL_COMPARE_UNKNOWN";
}

std::optional<std::string_view>
textureCompareOperatorBinarySymbol(TextureCompareOperator compareOperator) {
  switch (compareOperator) {
  case TextureCompareOperator::Less:
    return "<";
  case TextureCompareOperator::LessEqual:
    return "<=";
  case TextureCompareOperator::Equal:
    return "==";
  case TextureCompareOperator::NotEqual:
    return "!=";
  case TextureCompareOperator::GreaterEqual:
    return ">=";
  case TextureCompareOperator::Greater:
    return ">";
  case TextureCompareOperator::Never:
  case TextureCompareOperator::Always:
    break;
  }
  return std::nullopt;
}

std::string_view textureCompareOperatorList() {
  return "never, always, less, less_equal, equal, not_equal, greater_equal, "
         "or greater";
}

std::optional<TextureCompareOperands>
textureCompareOperands(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::TextureCompare) {
    return std::nullopt;
  }
  const bool explicitLod = expression.value == "textureCompareLod";
  if ((!explicitLod && expression.value != "textureCompare") ||
      expression.children.size() != (explicitLod ? 5 : 4)) {
    return std::nullopt;
  }

  TextureCompareOperands operands;
  operands.explicitLod = explicitLod;
  operands.texture = &expression.children[0];
  operands.sampler = &expression.children[1];
  operands.coordinate = &expression.children[2];
  operands.depth = &expression.children[3];
  operands.lod = explicitLod ? &expression.children[4] : nullptr;
  return operands;
}

std::optional<TextureCompareManualOperands>
textureCompareManualOperands(const HIRExpression &expression) {
  const bool hasOffset = expression.value == "textureCompareLodManualOffset";
  const bool gather2x2 =
      expression.value == "textureCompareLodManualGather2x2";
  const bool kernelList = expression.value == "textureCompareLodManualKernel";
  const bool kernel4 = expression.value == "textureCompareLodManualKernel4";
  const bool kernel8 = expression.value == "textureCompareLodManualKernel8";
  const std::size_t kernelTapCount = kernel4 ? 4 : kernel8 ? 8 : 0;
  const bool hasKernel = kernelList || kernelTapCount != 0;
  const std::size_t expectedArguments =
      hasOffset ? 7 : kernelList ? 7 : kernelTapCount != 0
                                                ? 6 + kernelTapCount * 2
                                                : 6;
  if (expression.kind != HIRExpressionKind::TextureCompareLodManual ||
      (expression.value != "textureCompareLodManual" && !hasOffset &&
       !gather2x2 && !kernelList && !kernel4 && !kernel8) ||
      expression.children.size() != expectedArguments) {
    return std::nullopt;
  }

  TextureCompareManualOperands operands;
  operands.texture = &expression.children[0];
  operands.sampler = &expression.children[1];
  operands.coordinate = &expression.children[2];
  operands.depth = &expression.children[3];
  operands.lod = &expression.children[4];
  operands.compareOp = &expression.children[5];
  operands.offset = hasOffset ? &expression.children[6] : nullptr;
  operands.gather2x2 = gather2x2;
  operands.kernelList = kernelList;
  operands.kernel4 = kernel4;
  operands.kernel8 = kernel8;
  if (hasKernel) {
    const std::optional<std::vector<ManualTextureCompareKernelTap>> taps =
        manualTextureCompareKernelTaps(expression);
    if (!taps.has_value()) {
      return std::nullopt;
    }
    operands.kernelTapCount = taps->size();
    for (std::size_t index = 0; index < taps->size(); ++index) {
      operands.kernelOffsets[index] = (*taps)[index].offset;
      operands.kernelWeights[index] = (*taps)[index].weight;
    }
  }
  return operands;
}

std::string textureCompareManualOperationName(
    const TextureCompareManualOperands &operands) {
  if (operands.offset != nullptr) {
    return "textureCompareLodManualOffset";
  }
  if (operands.gather2x2) {
    return "textureCompareLodManualGather2x2";
  }
  if (operands.kernelList) {
    return "textureCompareLodManualKernel";
  }
  if (operands.kernel8) {
    return "textureCompareLodManualKernel8";
  }
  if (operands.kernel4) {
    return "textureCompareLodManualKernel4";
  }
  return "textureCompareLodManual";
}

bool textureCompareHasScalarFloatResult(const HIRExpression &expression) {
  return expression.type.name == "float" && !expression.type.arraySize.has_value();
}

} // namespace crossgl
