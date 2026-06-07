#pragma once

#include "crossgl/HIR/HIR.h"

#include <optional>
#include <span>
#include <string_view>
#include <vector>

namespace crossgl {

enum class HIRBuiltinEffect {
  Pure,
  Opaque,
  Structural,
};

struct HIRCallBuiltinEffectRecord {
  std::string_view name;
  HIRBuiltinEffect effect = HIRBuiltinEffect::Opaque;
};

std::string_view hirBuiltinEffectName(HIRBuiltinEffect effect);

std::span<const HIRCallBuiltinEffectRecord> hirCallBuiltinEffects();

std::optional<HIRBuiltinEffect>
lookupHIRCallBuiltinEffect(std::string_view name);

std::optional<HIRBuiltinEffect>
resolveHIRCallEffect(std::string_view name,
                     const std::vector<HIRType> &argumentTypes);

std::optional<HIRBuiltinEffect>
resolveHIRCallEffect(std::string_view name,
                     const std::vector<HIRExpression> &arguments);

bool isPureHIRCallExpression(const HIRExpression &expression);
bool isHIRImageAccessBuiltinCall(std::string_view name);
bool isHIRResourceReadBuiltinCall(std::string_view name);
bool isHIRResourceWriteBuiltinCall(std::string_view name);
bool isHIRTextureAccessBuiltinCall(std::string_view name);
bool isHIRTextureCompareKernelBuiltinCall(std::string_view name);

} // namespace crossgl
