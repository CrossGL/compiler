#include "crossgl/Backend/TextureSample.h"

namespace crossgl {

std::optional<TextureSampleOperands>
textureSampleOperands(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::TextureSample ||
      expression.value != "textureLod" || expression.children.size() != 4) {
    return std::nullopt;
  }

  TextureSampleOperands operands;
  operands.texture = &expression.children[0];
  operands.sampler = &expression.children[1];
  operands.coordinate = &expression.children[2];
  operands.lod = &expression.children[3];
  return operands;
}

} // namespace crossgl
