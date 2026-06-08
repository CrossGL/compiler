#pragma once

#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "crossgl/Backend/Toolchain.h"
#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/HIR/HIR.h"
#include "crossgl/Optimizer/HIRPassManager.h"

namespace crossgl {

struct TargetLegalizationResourceBindingFacts;

struct MetalBuildResult {
  bool success = false;
  std::string optimizationRequestedLevel = "O1";
  std::string optimizationPolicy = "metal-conservative-native-package-v1";
  std::string optimizationProfile = "release";
  std::string optimizationLevel = "-O2";
  bool optimizationDebugInfo = false;
  std::vector<std::string> optimizationFlags;
  std::filesystem::path sourcePath;
  std::filesystem::path airPath;
  std::filesystem::path metallibPath;
  std::filesystem::path compileOptionsPath;
};

enum class MetalBuildProfile {
  Debug,
  Release,
};

struct MetalCompileOptions {
  std::string policyName;
  std::string profileName;
  std::string requestedOptimizationLevel;
  std::string optimizationLevel;
  bool debugInfo = false;
  std::string description;
  std::vector<std::string> metalFlags;
  std::vector<std::string> metallibFlags;
};

MetalCompileOptions metalCompileOptionsForProfile(MetalBuildProfile profile);
MetalCompileOptions metalCompileOptionsForOptimizationLevel(
    OptimizationLevel level);

std::string generateMetalSource(const HIRModule &module);

std::string metalResourceABIType(const HIRResource &resource);
std::string metalResourceAddressSpace(const HIRResource &resource);
std::string metalResourceBindingClass(HIRResourceKind kind);
std::string metalResourceBindingClass(const HIRResource &resource);
bool metalResourceIsKernelParameter(HIRResourceKind kind);
std::optional<std::size_t>
metalResourceArgumentIndex(
    const HIRStage &stage, std::string_view resourceName,
    const std::vector<HIRConstant> *constants = nullptr);

// Runs Metal native preflight validation without emitting artifacts or invoking
// the Apple toolchain.
bool metalNativeBackendSupported(const HIRModule &module,
                                 DiagnosticEngine &diagnostics);

MetalBuildResult buildMetalBinary(const HIRModule &module,
                                  const std::filesystem::path &packageDir,
                                  DiagnosticEngine &diagnostics,
                                  OptimizationLevel optimizationLevel =
                                      OptimizationLevel::O1);
MetalBuildResult buildMetalBinary(
    const HIRModule &module, const std::filesystem::path &packageDir,
    DiagnosticEngine &diagnostics,
    const TargetLegalizationResourceBindingFacts &resourceBindings,
    OptimizationLevel optimizationLevel = OptimizationLevel::O1);

} // namespace crossgl
