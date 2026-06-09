#pragma once

#include <filesystem>
#include <string>
#include <vector>

#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/HIR/HIR.h"
#include "crossgl/Optimizer/HIRPassManager.h"

namespace crossgl {

struct TargetLegalizationResourceBindingFacts;

inline constexpr char kVulkanNativeTargetEnv[] = "vulkan1.2";

struct VulkanSPIRVImport {
  std::string resultId;
  std::string instructionSet;
};

struct VulkanPrototypeAssemblyArtifact {
  std::string assembly;
  std::vector<VulkanSPIRVImport> extendedInstructionImports;
};

struct VulkanBuildResult {
  bool success = false;
  std::string validationTargetEnv = kVulkanNativeTargetEnv;
  std::string optimizationRequestedLevel = "O1";
  std::string optimizationPolicy = "disabled-by-opt-level";
  std::string optimizationLevel = "none";
  std::string optimizationStatus = "skipped-disabled";
  std::string optimizationTargetEnv = kVulkanNativeTargetEnv;
  std::string optimizationToolStatus = "not-run";
  std::string disassemblyStatus = "skipped-tool-missing";
  std::filesystem::path assemblyPath;
  std::filesystem::path spvPath;
  std::filesystem::path disassemblyPath;
  std::vector<VulkanSPIRVImport> extendedInstructionImports;
};

bool vulkanResourceUsesDescriptor(HIRResourceKind kind);
std::vector<VulkanSPIRVImport>
canonicalizeVulkanSPIRVImports(std::vector<VulkanSPIRVImport> imports);
std::string vulkanDescriptorType(HIRResourceKind kind);
std::string vulkanResourceStorageClass(HIRResourceKind kind);
std::string vulkanResourceBindingClass(HIRResourceKind kind);
std::string vulkanResourceSPIRVType(const HIRResource &resource);

std::string generateVulkanBackendIR(const HIRModule &module);
std::string generateVulkanPrototypeAssembly(const HIRModule &module,
                                            DiagnosticEngine &diagnostics);
VulkanPrototypeAssemblyArtifact
generateVulkanPrototypeAssemblyArtifact(const HIRModule &module,
                                        DiagnosticEngine &diagnostics);
bool vulkanPrototypeBinarySupported(const HIRModule &module,
                                    DiagnosticEngine &diagnostics);
VulkanBuildResult buildVulkanPrototypeBinary(
    const HIRModule &module, const std::filesystem::path &packageDir,
    DiagnosticEngine &diagnostics,
    OptimizationLevel optimizationLevel = OptimizationLevel::O1);
VulkanBuildResult buildVulkanPrototypeBinary(
    const HIRModule &module, const std::filesystem::path &packageDir,
    DiagnosticEngine &diagnostics,
    const TargetLegalizationResourceBindingFacts &resourceBindings,
    OptimizationLevel optimizationLevel = OptimizationLevel::O1);

} // namespace crossgl
