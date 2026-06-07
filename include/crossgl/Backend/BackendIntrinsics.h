#pragma once

#include "crossgl/Backend/Target.h"
#include "crossgl/HIR/HIR.h"

#include <optional>
#include <string>

namespace crossgl {

std::optional<std::string>
backendIntrinsicNameForCall(TargetKind target, const HIRExpression &expression);

bool backendIntrinsicCallSupported(TargetKind target,
                                   const HIRExpression &expression);

} // namespace crossgl
