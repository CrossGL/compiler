#include "crossgl/Backend/BackendIntrinsics.h"

#include "crossgl/HIR/Intrinsics.h"

#include <string_view>
#include <vector>

namespace crossgl {
namespace {

std::vector<HIRType>
intrinsicArgumentTypes(const HIRExpression &expression) {
  std::vector<HIRType> types;
  types.reserve(expression.children.size());
  for (const HIRExpression &child : expression.children) {
    types.push_back(child.type);
  }
  return types;
}

} // namespace

std::optional<std::string>
backendIntrinsicNameForCall(TargetKind target,
                            const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Call ||
      expression.value.empty()) {
    return std::nullopt;
  }

  const std::vector<HIRType> argumentTypes = intrinsicArgumentTypes(expression);
  if (selectHIRIntrinsicSignature(expression.value, argumentTypes) == nullptr) {
    return std::nullopt;
  }

  const std::string_view name = expression.value;
  switch (target) {
  case TargetKind::Metal:
    if (name == "atan" && expression.children.size() == 2) {
      return "atan2";
    }
    return std::string(name);
  case TargetKind::DirectX:
    if (name == "atan" && expression.children.size() == 2) {
      return "atan2";
    }
    if (name == "fract") {
      return "frac";
    }
    if (name == "mix") {
      return "lerp";
    }
    return std::string(name);
  case TargetKind::OpenGL:
    return std::string(name);
  case TargetKind::Vulkan:
  case TargetKind::WGSL:
  case TargetKind::Auto:
    return std::nullopt;
  }
  return std::nullopt;
}

bool backendIntrinsicCallSupported(TargetKind target,
                                   const HIRExpression &expression) {
  return backendIntrinsicNameForCall(target, expression).has_value();
}

} // namespace crossgl
