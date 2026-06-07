#pragma once

#include <cstddef>
#include <filesystem>
#include <string>

#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/HIR/HIR.h"

namespace crossgl {

struct TargetLegalizationResourceBindingFacts;

struct OpenGLSourcePackageResult {
  bool success = false;
  bool sourceValidated = false;
  std::filesystem::path sourcePath;
  std::filesystem::path nativeBinaryPath;
  std::string nativeBinaryStatus = "planned";
  std::string validatorTool = "glslangValidator";
  std::string validatorPolicy = "use-when-available";
  std::string validatorStatus = "skipped-tool-missing";
};

bool openglTextualBackendSupported(const HIRModule &module);
bool openglHasUnsupportedShadowCompareExplicitLodShape(
    const HIRModule &module);
bool diagnoseOpenGLUnsupportedShadowCompareExplicitLodShape(
    const HIRModule &module, DiagnosticEngine &diagnostics);
bool openglHasUnsupportedStorageBufferArray(const HIRModule &module);
bool diagnoseOpenGLUnsupportedStorageBufferArray(
    const HIRModule &module, DiagnosticEngine &diagnostics);
bool openglHasUnsupportedRuntimeResourceArray(const HIRModule &module);
bool diagnoseOpenGLUnsupportedRuntimeResourceArray(
    const HIRModule &module, DiagnosticEngine &diagnostics);
bool openglHasUnsupportedStorageBufferElementType(const HIRModule &module);
bool diagnoseOpenGLUnsupportedStorageBufferElementType(
    const HIRModule &module, DiagnosticEngine &diagnostics);
bool openglHasUnsupportedFunctionParameterArrayCallFeatures(
    const HIRModule &module);
bool diagnoseOpenGLUnsupportedFunctionParameterArrayCallFeatures(
    const HIRModule &module, DiagnosticEngine &diagnostics);
bool openglHasUnsupportedDynamicNestedHelperArrayRead(
    const HIRModule &module);
bool diagnoseOpenGLUnsupportedDynamicNestedHelperArrayRead(
    const HIRModule &module, DiagnosticEngine &diagnostics);
bool openglHasUnsupportedFunctionParameterArrayWrite(const HIRModule &module);
bool diagnoseOpenGLUnsupportedFunctionParameterArrayWrite(
    const HIRModule &module, DiagnosticEngine &diagnostics);
std::size_t openglResourceBindingIndex(const HIRResource &resource);
std::string openglResourceAddressSpace(HIRResourceKind kind);
std::string openglResourceBindingClass(HIRResourceKind kind);
bool openGLSourcePackageSupported(const HIRModule &module,
                                  DiagnosticEngine &diagnostics);
std::string generateOpenGLSource(const HIRModule &module);
std::string generateOpenGLBackendIR(const HIRModule &module);
OpenGLSourcePackageResult
buildOpenGLSourcePackage(const HIRModule &module,
                         const std::filesystem::path &packageDir,
                         DiagnosticEngine &diagnostics);
OpenGLSourcePackageResult buildOpenGLSourcePackage(
    const HIRModule &module, const std::filesystem::path &packageDir,
    DiagnosticEngine &diagnostics,
    const TargetLegalizationResourceBindingFacts &resourceBindings);

} // namespace crossgl
