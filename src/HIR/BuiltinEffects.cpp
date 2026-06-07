#include "crossgl/HIR/BuiltinEffects.h"

#include "crossgl/HIR/Intrinsics.h"

#include <algorithm>
#include <array>

namespace crossgl {
namespace {

constexpr std::array<HIRCallBuiltinEffectRecord, 30> kHIRCallBuiltinEffects = {{
    {"atomicAdd", HIRBuiltinEffect::Opaque},
    {"atomicAnd", HIRBuiltinEffect::Opaque},
    {"atomicExchange", HIRBuiltinEffect::Opaque},
    {"atomicMax", HIRBuiltinEffect::Opaque},
    {"atomicMin", HIRBuiltinEffect::Opaque},
    {"atomicOr", HIRBuiltinEffect::Opaque},
    {"atomicXor", HIRBuiltinEffect::Opaque},
    {"barrier", HIRBuiltinEffect::Opaque},
    {"imageAtomicAdd", HIRBuiltinEffect::Opaque},
    {"imageAtomicAnd", HIRBuiltinEffect::Opaque},
    {"imageAtomicExchange", HIRBuiltinEffect::Opaque},
    {"imageAtomicMax", HIRBuiltinEffect::Opaque},
    {"imageAtomicMin", HIRBuiltinEffect::Opaque},
    {"imageAtomicOr", HIRBuiltinEffect::Opaque},
    {"imageAtomicXor", HIRBuiltinEffect::Opaque},
    {"imageLoad", HIRBuiltinEffect::Opaque},
    {"imageStore", HIRBuiltinEffect::Opaque},
    {"sample", HIRBuiltinEffect::Opaque},
    {"texture", HIRBuiltinEffect::Opaque},
    {"textureLod", HIRBuiltinEffect::Opaque},
    {"textureCompare", HIRBuiltinEffect::Opaque},
    {"textureCompareKernel", HIRBuiltinEffect::Structural},
    {"textureCompareLod", HIRBuiltinEffect::Opaque},
    {"textureCompareLodManual", HIRBuiltinEffect::Opaque},
    {"textureCompareLodManualGather2x2", HIRBuiltinEffect::Opaque},
    {"textureCompareLodManualKernel", HIRBuiltinEffect::Opaque},
    {"textureCompareLodManualKernel4", HIRBuiltinEffect::Opaque},
    {"textureCompareLodManualKernel8", HIRBuiltinEffect::Opaque},
    {"textureCompareLodManualOffset", HIRBuiltinEffect::Opaque},
    {"workgroupBarrier", HIRBuiltinEffect::Opaque},
}};

HIRBuiltinEffect hirBuiltinEffectFromIntrinsic(HIRIntrinsicEffect effect) {
  switch (effect) {
  case HIRIntrinsicEffect::Pure:
    return HIRBuiltinEffect::Pure;
  case HIRIntrinsicEffect::Opaque:
    return HIRBuiltinEffect::Opaque;
  }
  return HIRBuiltinEffect::Opaque;
}

bool isHIRImageAtomicBuiltinCall(std::string_view name) {
  return name == "imageAtomicAdd" || name == "imageAtomicExchange" ||
         name == "imageAtomicMin" || name == "imageAtomicMax" ||
         name == "imageAtomicAnd" || name == "imageAtomicOr" ||
         name == "imageAtomicXor";
}

} // namespace

std::string_view hirBuiltinEffectName(HIRBuiltinEffect effect) {
  switch (effect) {
  case HIRBuiltinEffect::Pure:
    return "pure";
  case HIRBuiltinEffect::Opaque:
    return "opaque";
  case HIRBuiltinEffect::Structural:
    return "structural";
  }
  return "opaque";
}

std::span<const HIRCallBuiltinEffectRecord> hirCallBuiltinEffects() {
  return kHIRCallBuiltinEffects;
}

std::optional<HIRBuiltinEffect>
lookupHIRCallBuiltinEffect(std::string_view name) {
  const auto found =
      std::find_if(kHIRCallBuiltinEffects.begin(), kHIRCallBuiltinEffects.end(),
                   [name](const HIRCallBuiltinEffectRecord &effect) {
                     return effect.name == name;
                   });
  if (found == kHIRCallBuiltinEffects.end()) {
    return std::nullopt;
  }
  return found->effect;
}

std::optional<HIRBuiltinEffect>
resolveHIRCallEffect(std::string_view name,
                     const std::vector<HIRType> &argumentTypes) {
  if (const std::optional<HIRBuiltinEffect> builtinEffect =
          lookupHIRCallBuiltinEffect(name)) {
    return builtinEffect;
  }
  if (const std::optional<HIRIntrinsicEffect> intrinsicEffect =
          resolveHIRIntrinsicEffect(name, argumentTypes)) {
    return hirBuiltinEffectFromIntrinsic(*intrinsicEffect);
  }
  return std::nullopt;
}

std::optional<HIRBuiltinEffect>
resolveHIRCallEffect(std::string_view name,
                     const std::vector<HIRExpression> &arguments) {
  std::vector<HIRType> argumentTypes;
  argumentTypes.reserve(arguments.size());
  for (const HIRExpression &argument : arguments) {
    argumentTypes.push_back(argument.type);
  }
  return resolveHIRCallEffect(name, argumentTypes);
}

bool isPureHIRCallExpression(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Call) {
    return false;
  }
  const std::optional<HIRBuiltinEffect> effect =
      resolveHIRCallEffect(expression.value, expression.children);
  return effect.has_value() && *effect == HIRBuiltinEffect::Pure;
}

bool isHIRImageAccessBuiltinCall(std::string_view name) {
  return name == "imageStore" || name == "imageLoad" ||
         isHIRImageAtomicBuiltinCall(name);
}

bool isHIRResourceReadBuiltinCall(std::string_view name) {
  return name == "imageLoad" || isHIRImageAtomicBuiltinCall(name) ||
         isHIRTextureAccessBuiltinCall(name);
}

bool isHIRResourceWriteBuiltinCall(std::string_view name) {
  return name == "imageStore" || isHIRImageAtomicBuiltinCall(name) ||
         isHIRAtomicIntegerReadModifyWriteIntrinsic(name);
}

bool isHIRTextureAccessBuiltinCall(std::string_view name) {
  return name == "sample" || name == "texture" || name == "textureLod" ||
         name == "textureCompare" || name == "textureCompareLod" ||
         name == "textureCompareLodManual" ||
         name == "textureCompareLodManualGather2x2" ||
         name == "textureCompareLodManualKernel" ||
         name == "textureCompareLodManualKernel4" ||
         name == "textureCompareLodManualKernel8" ||
         name == "textureCompareLodManualOffset";
}

bool isHIRTextureCompareKernelBuiltinCall(std::string_view name) {
  return name == "textureCompareKernel";
}

} // namespace crossgl
