#pragma once

#include <filesystem>
#include <optional>
#include <string>

#include "crossgl/Backend/BackendHIR.h"
#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/Driver/SourceInput.h"
#include "crossgl/Frontend/AST.h"
#include "crossgl/HIR/HIR.h"
#include "crossgl/Optimizer/HIRPassManager.h"

namespace crossgl {

struct CompilerModule {
  std::filesystem::path inputPath;
  std::string source;
  ShaderModule ast;
  HIRModule hir;
  HIRPassPipelineResult optimization;
};

struct CompilerModuleOptions {
  OptimizationLevel optimizationLevel = OptimizationLevel::O1;
  bool validateBackendInput = true;
  std::optional<std::filesystem::path> logicalPath;
};

inline HIRBackendInputDescriptor backendInputDescriptorForPipelineResult(
    const HIRPassPipelineResult &result) {
  HIRBackendInputDescriptor descriptor;
  descriptor.backendInputMode = result.backendInputMode;
  descriptor.optimizationPolicyId = result.optimizationPolicyId;

  if (!result.completed ||
      result.backendInputMode != kHIRBackendInputValidationMode) {
    return descriptor;
  }

  for (const HIRPassResult &pass : result.passes) {
    if (pass.id != kHIRBackendInputValidationPassId) {
      continue;
    }
    if (pass.status == HIRPassStatus::Completed && pass.errorCount == 0) {
      descriptor.validationState =
          HIRBackendInputValidationState::Validated;
    }
    break;
  }
  return descriptor;
}

inline HIRBackendInput
backendInputForCompilerModule(const CompilerModule &module) {
  return makeHIRBackendInput(
      module.hir, backendInputDescriptorForPipelineResult(module.optimization));
}

std::optional<CompilerModule>
loadCompilerModule(const std::filesystem::path &inputPath,
                   DiagnosticEngine &diagnostics);
std::optional<CompilerModule>
loadCompilerModule(const std::filesystem::path &inputPath,
                   DiagnosticEngine &diagnostics,
                   CompilerModuleOptions options);
std::optional<CompilerModule>
loadCompilerModuleFromSource(const SourceInput &input,
                             DiagnosticEngine &diagnostics);
std::optional<CompilerModule>
loadCompilerModuleFromSource(const SourceInput &input,
                             DiagnosticEngine &diagnostics,
                             CompilerModuleOptions options);

} // namespace crossgl
