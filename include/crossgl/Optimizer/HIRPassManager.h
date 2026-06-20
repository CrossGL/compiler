#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/HIR/HIR.h"

namespace crossgl {

using HIRPassRunner = bool (*)(HIRModule &module,
                               DiagnosticEngine &diagnostics);

struct HIRPassMetadata {
  std::string_view id;
  std::string_view name;
  std::string_view category;
};

struct HIRPass {
  constexpr HIRPass() = default;
  constexpr HIRPass(std::string_view passName, HIRPassRunner runner)
      : id(passName), name(passName), category("custom"), run(runner) {}
  constexpr HIRPass(HIRPassMetadata passMetadata, HIRPassRunner runner)
      : id(passMetadata.id), name(passMetadata.name),
        category(passMetadata.category), run(runner) {}

  std::string_view id;
  std::string_view name;
  std::string_view category;
  HIRPassRunner run = nullptr;
};

enum class HIRPassStatus {
  Completed,
  Failed,
};

enum class OptimizationLevel {
  O0,
  O1,
  O2,
};

enum class HIRVerifierMode {
  Source,
  BackendInput,
};

struct HIRPassPipelineConfig {
  OptimizationLevel optimizationLevel = OptimizationLevel::O1;
  bool validateBackendInput = true;
};

struct HIRVerifierConfig {
  HIRVerifierMode mode = HIRVerifierMode::BackendInput;
};

struct HIRModuleStats {
  std::size_t structCount = 0;
  std::size_t constantCount = 0;
  std::size_t stageCount = 0;
  std::size_t resourceCount = 0;
  std::size_t functionCount = 0;
  std::size_t statementCount = 0;
  std::size_t expressionCount = 0;
};

struct HIRPassResult {
  std::string id;
  std::string name;
  std::string category;
  bool changed = false;
  HIRPassStatus status = HIRPassStatus::Completed;
  std::size_t diagnosticCount = 0;
  std::size_t errorCount = 0;
  std::uint64_t elapsedTimeMicroseconds = 0;
  HIRModuleStats moduleStatsBefore;
  HIRModuleStats moduleStatsAfter;
  HIRModuleStats moduleStatsDelta;
};

struct HIRPassPipelineResult {
  OptimizationLevel optimizationLevel = OptimizationLevel::O1;
  std::string optimizationPolicyId = "custom-pass-list";
  std::string optimizationPolicyName = "Custom HIR pass list";
  std::string optimizationPolicyDescription =
      "Explicit caller-provided HIR pass list.";
  std::string backendInputMode = "caller-defined";
  std::string passScheduleFingerprintPolicy = "scheduled-pass-ids-v1";
  std::string passScheduleFingerprint;
  std::string passScheduleStability = "caller-defined";
  std::size_t scheduledPassCount = 0;
  std::size_t passCount = 0;
  std::size_t changedPassCount = 0;
  std::size_t diagnosticPassCount = 0;
  std::size_t errorPassCount = 0;
  bool changed = false;
  bool completed = true;
  std::string stopReason = "none";
  std::vector<HIRPassResult> passes;
};

struct HIRPassTraceJsonOptions {
  bool includeElapsedTimeMicroseconds = true;
  bool includeModuleStats = true;
};

std::string_view hirPassStatusName(HIRPassStatus status);
std::string_view optimizationLevelName(OptimizationLevel level);
std::string_view hirVerifierModeName(HIRVerifierMode mode);
std::optional<OptimizationLevel> parseOptimizationLevel(std::string_view value);
std::string hirPassScheduleFingerprint(std::span<const HIRPass> passes);
std::span<const HIRPass> defaultHIRPassPipeline();
std::span<const HIRPass> sourceValidationHIRPassPipeline();
std::span<const HIRPass> hirVerifierPassPipeline(HIRVerifierMode mode);
std::span<const HIRPass>
hirPassPipelineForConfig(HIRPassPipelineConfig config);
HIRPassPipelineResult verifyHIRModule(
    HIRModule &module, DiagnosticEngine &diagnostics,
    HIRVerifierConfig config = HIRVerifierConfig{});
HIRPassPipelineResult runHIRPassPipeline(HIRModule &module,
                                         DiagnosticEngine &diagnostics,
                                         std::span<const HIRPass> passes);
HIRPassPipelineResult runHIRPassPipeline(HIRModule &module,
                                         DiagnosticEngine &diagnostics,
                                         HIRPassPipelineConfig config);
HIRPassPipelineResult runHIRPassPipeline(HIRModule &module,
                                         DiagnosticEngine &diagnostics);
std::string hirPassTraceJson(
    const HIRPassPipelineResult &result,
    HIRPassTraceJsonOptions options = HIRPassTraceJsonOptions{});

} // namespace crossgl
