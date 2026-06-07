#pragma once

#include <cstddef>
#include <string>
#include <vector>

#include "crossgl/Backend/Target.h"
#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/HIR/HIR.h"

namespace crossgl {

struct TargetCapability {
  TargetKind target = TargetKind::Auto;
  std::string kind;
  std::string name;
};

struct TargetPackageDecision {
  TargetKind target = TargetKind::Auto;
  std::string targetName;
  bool nativeImplemented = false;
  bool sourcePackageSupported = false;
  bool packageBuildSupported = false;
  std::string packageMode;
  std::string packageDecisionReason;
  std::size_t packageRankScore = 0;
  std::vector<TargetCapability> requiredCapabilities;
  std::vector<TargetCapability> missingCapabilities;
  std::vector<Diagnostic> diagnostics;
};

struct TargetPackageSelection {
  TargetKind preferredTarget = TargetKind::Auto;
  TargetKind selectedTarget = TargetKind::Auto;
  bool selectedTargetBuildable = false;
};

std::string targetCapabilityId(const TargetCapability &capability);
std::vector<TargetCapability>
targetFeatureRequirements(const HIRModule &module, TargetKind target);
std::vector<TargetCapability>
missingTargetCapabilities(const HIRModule &module, TargetKind target);
TargetPackageDecision targetPackageDecision(const HIRModule &module,
                                            TargetKind target);
std::vector<TargetPackageDecision>
targetPackageDecisions(const HIRModule &module);
TargetPackageSelection selectRecommendedPackageTarget(
    const std::vector<TargetPackageDecision> &decisions,
    TargetKind preferredTarget = TargetKind::Auto);
TargetPackageSelection
selectRecommendedPackageTarget(const HIRModule &module,
                               TargetKind preferredTarget = TargetKind::Auto);
std::string formatTargetCapabilityList(
    const std::vector<TargetCapability> &capabilities,
    std::size_t maxItems = 0);

} // namespace crossgl
