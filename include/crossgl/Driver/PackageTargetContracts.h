#pragma once

// Derived from tools/package_target_contracts.json.
// Do not edit by hand.

#include <array>
#include <cstddef>
#include <string_view>

namespace crossgl {

inline constexpr std::size_t kPackageTargetRequiredArtifactCapacity = 3;
inline constexpr std::size_t kPackageTargetContractCount = 4;

struct PackageTargetContract {
  // Canonical manifest target name, for example "metal" or "directx".
  std::string_view target;
  // Required manifest artifact path fields. Inactive slots are empty.
  std::array<std::string_view, kPackageTargetRequiredArtifactCapacity>
      requiredArtifacts;
  std::size_t requiredArtifactCount = 0;
  // Source-package targets require artifacts.nativeBinaryStatus.
  bool requiresNativeBinaryStatus = false;
  // Source-package targets may report artifacts.nativeBinaryStatus=planned.
  bool allowsPlannedNativeBinary = false;
  // Source-package targets may include planned native source evidence.
  bool allowsPlannedNativeSourceEvidence = false;
};

inline constexpr std::array<PackageTargetContract, kPackageTargetContractCount>
    kPackageTargetContracts{{
        {"metal",
         {"backendSource", "intermediate", "nativeBinary"},
         3,
         false,
         false,
         false},
        {"vulkan",
         {"backendAssembly", "nativeBinary", ""},
         2,
         false,
         false,
         false},
        {"directx",
         {"backendSource", "nativeBinary", ""},
         2,
         true,
         true,
         true},
        {"opengl",
         {"backendSource", "nativeBinary", ""},
         2,
         true,
         true,
         true},
    }};

constexpr const PackageTargetContract *
packageTargetContractFor(std::string_view target) {
  for (const PackageTargetContract &contract : kPackageTargetContracts) {
    if (contract.target == target) {
      return &contract;
    }
  }
  return nullptr;
}

constexpr bool isKnownPackageTarget(std::string_view target) {
  return packageTargetContractFor(target) != nullptr;
}

} // namespace crossgl
