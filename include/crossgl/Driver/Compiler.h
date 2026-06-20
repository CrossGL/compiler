#pragma once

#include <filesystem>
#include <optional>
#include <string>

#include "crossgl/Backend/Target.h"
#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/Driver/SourceInput.h"
#include "crossgl/Driver/SourceRemap.h"
#include "crossgl/IR/IRPrinter.h"
#include "crossgl/Optimizer/HIRPassManager.h"

namespace crossgl {

struct DebugMetadataHIRSourceMapFilter;
struct DebugMetadataHIRSourceMapOptions;
struct DebugMetadataHIRSourceMapPagination;

struct CompileRequest {
  std::filesystem::path inputPath;
  std::filesystem::path outputPath;
  TargetKind target = TargetKind::Auto;
  OptimizationLevel optimizationLevel = OptimizationLevel::O1;
  bool debugIR = false;
  std::optional<std::filesystem::path> logicalInputPath;
  std::optional<SourceRemap> sourceRemap;
};

struct CompileResult {
  bool success = false;
  std::filesystem::path artifactPath;
  TargetKind resolvedTarget = TargetKind::Auto;
  std::vector<Diagnostic> diagnostics;
};

struct CheckResult {
  bool success = false;
  std::vector<Diagnostic> diagnostics;
};

CheckResult checkFile(const std::filesystem::path &inputPath);
CheckResult checkSource(const SourceInput &input);
std::optional<std::string> dumpIR(const std::filesystem::path &inputPath,
                                  DumpStage stage, TargetKind target,
                                  DiagnosticEngine &diagnostics);
std::optional<std::string> dumpIR(const SourceInput &input, DumpStage stage,
                                  TargetKind target,
                                  DiagnosticEngine &diagnostics);
std::optional<std::string> dumpIR(const std::filesystem::path &inputPath,
                                  DumpStage stage, TargetKind target,
                                  OptimizationLevel optimizationLevel,
                                  DiagnosticEngine &diagnostics);
std::optional<std::string> dumpIR(const SourceInput &input, DumpStage stage,
                                  TargetKind target,
                                  OptimizationLevel optimizationLevel,
                                  DiagnosticEngine &diagnostics);
std::optional<std::string> dumpIR(
    const std::filesystem::path &inputPath, DumpStage stage, TargetKind target,
    DiagnosticEngine &diagnostics,
    const DebugMetadataHIRSourceMapFilter &sourceMapFilter);
std::optional<std::string> dumpIR(
    const std::filesystem::path &inputPath, DumpStage stage, TargetKind target,
    OptimizationLevel optimizationLevel, DiagnosticEngine &diagnostics,
    const DebugMetadataHIRSourceMapFilter &sourceMapFilter);
std::optional<std::string> dumpIR(
    const std::filesystem::path &inputPath, DumpStage stage, TargetKind target,
    DiagnosticEngine &diagnostics,
    const DebugMetadataHIRSourceMapFilter &sourceMapFilter,
    const DebugMetadataHIRSourceMapPagination &sourceMapPagination);
std::optional<std::string> dumpIR(
    const std::filesystem::path &inputPath, DumpStage stage, TargetKind target,
    OptimizationLevel optimizationLevel, DiagnosticEngine &diagnostics,
    const DebugMetadataHIRSourceMapFilter &sourceMapFilter,
    const DebugMetadataHIRSourceMapPagination &sourceMapPagination);
std::optional<std::string> dumpIR(
    const std::filesystem::path &inputPath, DumpStage stage, TargetKind target,
    OptimizationLevel optimizationLevel, DiagnosticEngine &diagnostics,
    const DebugMetadataHIRSourceMapFilter &sourceMapFilter,
    const DebugMetadataHIRSourceMapPagination &sourceMapPagination,
    const DebugMetadataHIRSourceMapOptions &sourceMapOptions);
std::optional<std::string> dumpIR(
    const SourceInput &input, DumpStage stage, TargetKind target,
    OptimizationLevel optimizationLevel, DiagnosticEngine &diagnostics,
    const DebugMetadataHIRSourceMapFilter &sourceMapFilter,
    const DebugMetadataHIRSourceMapPagination &sourceMapPagination,
    const DebugMetadataHIRSourceMapOptions &sourceMapOptions);
std::optional<std::string>
explainTargets(const std::filesystem::path &inputPath,
               DiagnosticEngine &diagnostics);
std::optional<std::string> explainTargets(const SourceInput &input,
                                          DiagnosticEngine &diagnostics);
std::optional<std::string>
explainTargetsText(const std::filesystem::path &inputPath,
                   DiagnosticEngine &diagnostics);
std::optional<std::string> explainTargetsText(const SourceInput &input,
                                              DiagnosticEngine &diagnostics);
CompileResult compile(const CompileRequest &request);

} // namespace crossgl
