#pragma once

#include <cstddef>
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
struct SourceRemap;

struct DirectXSourcePackageResult {
  bool success = false;
  bool nativeBinaryProduced = false;
  std::filesystem::path sourcePath;
  std::filesystem::path nativeBinaryPath;
  std::string nativeBinaryStatus = "planned";
  std::string optimizationRequestedLevel = "O1";
  std::string optimizationPolicy = "crossgl-to-dxc-optimization-map";
  std::string optimizationLevel = "-O3";
  std::string optimizationStatus = "unavailable";
  std::string shaderProfileSummary;
  std::optional<ToolInvocationProvenance> dxcProvenance;
  std::vector<Diagnostic> validationDiagnostics;
};

struct DirectXDxcOptimizationProfile {
  std::string_view requestedLevel;
  std::string_view dxcFlag;
};

DirectXDxcOptimizationProfile
directxDxcOptimizationProfile(OptimizationLevel level);
bool directxTextualBackendSupported(const HIRModule &module);
bool directxSourcePackageSupported(const HIRModule &module,
                                   DiagnosticEngine &diagnostics);
bool directxHasMixedSamplerStateUsage(const HIRModule &module);
bool diagnoseDirectXMixedSamplerStateUsage(const HIRModule &module,
                                           DiagnosticEngine &diagnostics);
bool directxHasUnsupportedStorageBufferArray(const HIRModule &module);
bool diagnoseDirectXUnsupportedStorageBufferArray(
    const HIRModule &module, DiagnosticEngine &diagnostics);
bool directxHasUnsupportedRuntimeResourceArray(const HIRModule &module);
bool diagnoseDirectXUnsupportedRuntimeResourceArray(
    const HIRModule &module, DiagnosticEngine &diagnostics);
bool directxHasUnsupportedStorageBufferElementType(const HIRModule &module);
bool diagnoseDirectXUnsupportedStorageBufferElementType(
    const HIRModule &module, DiagnosticEngine &diagnostics);
bool directxHasUnsupportedFunctionParameterArrayCallFeature(
    const HIRModule &module);
bool diagnoseDirectXUnsupportedFunctionParameterArrayCallFeature(
    const HIRModule &module, DiagnosticEngine &diagnostics);
bool directxHasUnsupportedFunctionParameterArrayDynamicNestedRead(
    const HIRModule &module);
bool diagnoseDirectXUnsupportedFunctionParameterArrayDynamicNestedRead(
    const HIRModule &module, DiagnosticEngine &diagnostics);
bool directxHasUnsupportedFunctionParameterArrayWrite(
    const HIRModule &module);
bool diagnoseDirectXUnsupportedFunctionParameterArrayWrite(
    const HIRModule &module, DiagnosticEngine &diagnostics);
std::optional<std::string>
directxSamplerStateType(const HIRModule &module, const HIRResource &resource);
std::optional<std::string>
directxResourceHLSLType(const HIRModule &module, const HIRResource &resource);
std::size_t directxResourceRegisterIndex(const HIRResource &resource);
std::string directxResourceAddressSpace(HIRResourceKind kind);
std::string directxResourceBindingClass(HIRResourceKind kind);
std::string directxResourceDescriptorType(HIRResourceKind kind);
std::string generateDirectXSource(const HIRModule &module);
std::string generateDirectXSource(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts &resourceBindings);
std::string generateDirectXBackendIR(const HIRModule &module);
std::string generateDirectXBackendIR(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts &resourceBindings);
std::string
generateDirectXBackendSourceMapJson(const HIRModule &module,
                                    const SourceRemap *sourceRemap = nullptr);
std::string generateDirectXBackendSourceMapJson(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts &resourceBindings,
    const SourceRemap *sourceRemap = nullptr);
DirectXSourcePackageResult
buildDirectXSourcePackage(const HIRModule &module,
                          const std::filesystem::path &packageDir,
                          DiagnosticEngine &diagnostics,
                          OptimizationLevel optimizationLevel =
                              OptimizationLevel::O1,
                          const SourceRemap *sourceRemap = nullptr);
DirectXSourcePackageResult buildDirectXSourcePackage(
    const HIRModule &module, const std::filesystem::path &packageDir,
    DiagnosticEngine &diagnostics,
    const TargetLegalizationResourceBindingFacts &resourceBindings,
    OptimizationLevel optimizationLevel = OptimizationLevel::O1,
    const SourceRemap *sourceRemap = nullptr);

} // namespace crossgl
