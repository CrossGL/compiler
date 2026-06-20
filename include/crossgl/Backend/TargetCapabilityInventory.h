#pragma once

#include "crossgl/Backend/TargetCapabilities.h"

#include <span>
#include <string_view>
#include <vector>

namespace crossgl {

struct TargetCapabilityRegistryContract {
  TargetKind target = TargetKind::Auto;
  std::string_view packageMode;
  std::string_view nativeSupportClass;
  std::string_view baselineBackendCapability;
  std::string_view nativeArtifactCapability;
  bool nativeImplemented = false;
  bool sourcePackageSelectable = false;
};

struct TargetCapabilityInventory {
  TargetKind target = TargetKind::Auto;
  std::vector<TargetCapability> requiredCapabilities;
};

std::span<const TargetCapabilityRegistryContract>
targetCapabilityRegistryContracts();
const TargetCapabilityRegistryContract *
targetCapabilityRegistryContract(TargetKind target);
std::vector<TargetCapability> targetBaselineCapabilities(TargetKind target);
TargetCapabilityInventory collectTargetCapabilityInventory(
    const HIRModule &module, TargetKind target);

} // namespace crossgl
