#include "crossgl/Driver/Compiler.h"

#include "crossgl/Backend/DirectXBackend.h"
#include "crossgl/Backend/MetalBackend.h"
#include "crossgl/Backend/OpenGLBackend.h"
#include "crossgl/Backend/TargetCapabilities.h"
#include "crossgl/Backend/TargetLegalization.h"
#include "crossgl/Backend/Toolchain.h"
#include "crossgl/Backend/VulkanBackend.h"
#include "crossgl/Basic/Json.h"
#include "crossgl/Basic/SHA256.h"
#include "crossgl/Driver/CompilerPipeline.h"
#include "crossgl/Driver/DebugMetadata.h"
#include "crossgl/Driver/PackageIntegrity.h"
#include "crossgl/Driver/PackagePublication.h"
#include "crossgl/Driver/Reflection.h"
#include "crossgl/Driver/TargetExplanation.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <initializer_list>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>
#include <utility>
#include <vector>

namespace crossgl {
namespace {

struct SourcePackageArtifact {
  std::filesystem::path backendSource;
  std::filesystem::path nativeBinary;
  std::string nativeBinaryStatus;
};

struct NativeArtifactToolProvenance {
  std::string name;
  std::string role;
  std::string version;
  std::string executable;
  std::string resolvedExecutable;
  std::string executableSource;
  std::string versionProbeStatus;
  std::string versionDetail;
  std::string argumentsSha256;
  std::string commandShape;
  std::string responseFilePath;
  std::string outputPath;
  std::string outputSha256;
  std::optional<std::uintmax_t> outputSizeBytes;
  std::string provenanceStatus;
  std::string provenanceDetail;
};

struct NativeArtifactDescriptorSpec {
  std::string binaryKind;
  std::filesystem::path sourcePath;
  std::optional<std::filesystem::path> artifactPath;
  std::optional<std::string> nativeBinaryStatus;
  std::string validationStatus;
  std::string optimizationLevel;
  std::optional<std::string> optimizationEvidenceJson;
  std::vector<NativeArtifactToolProvenance> tools;
  std::vector<Diagnostic> validationDiagnostics;
  std::vector<VulkanSPIRVImport> spirvExtendedInstructionImports;
};

struct NativeOptimizationEvidenceSpec {
  std::string requestedLevel;
  std::string effectiveLevel;
  std::string policy;
  std::string status;
  std::optional<std::string> tool;
  std::optional<std::string> toolFlag;
  std::optional<std::string> evidenceSourceKind;
  std::optional<std::string> evidenceSourcePath;
  std::optional<bool> debugInfo;
  std::optional<std::string> profile;
  std::vector<std::string> flags;
};

struct BackendAdmission {
  TargetLegalizationResult legalization;
  TargetLegalizationAdmissionDecision decision;
  HIRBackendInput input;
};

struct ManifestArtifact {
  std::string name;
  std::string value;
};

struct ManifestArtifactValues {
  std::optional<std::string> backendAssembly;
  std::optional<std::string> backendSource;
  std::optional<std::string> backendSourceMap;
  std::optional<std::string> graphicsAbi;
  std::optional<std::string> intermediate;
  std::optional<std::string> nativeBinary;
  std::optional<std::string> nativeProfile;
  std::optional<std::string> nativeArtifactDescriptor;
  std::optional<std::string> nativeBinaryStatus;
};

DebugMetadataSourcePackageValidation
debugValidationFromOpenGLResult(const OpenGLSourcePackageResult &result) {
  DebugMetadataSourcePackageValidation validation;
  validation.target = "opengl";
  validation.tool = result.validatorTool;
  validation.policy = result.validatorPolicy;
  validation.status = result.validatorStatus;
  return validation;
}

bool writeText(const std::filesystem::path &path, std::string_view text,
               DiagnosticEngine &diagnostics, std::string_view code) {
  std::ofstream output(path, std::ios::binary);
  if (!output) {
    diagnostics.error(std::string(code),
                      "failed to write '" + path.string() + "'");
    return false;
  }
  output << text;
  return true;
}

std::string packageRelativePath(const std::filesystem::path &packageDir,
                                const std::filesystem::path &artifactPath) {
  const auto relative = artifactPath.lexically_relative(packageDir);
  const auto normalized = relative.lexically_normal();
  if (!normalized.empty() && !normalized.is_absolute()) {
    const auto first = normalized.begin();
    if (first == normalized.end() || first->string() != "..") {
      return normalized.generic_string();
    }
  }
  return artifactPath.generic_string();
}

std::optional<std::string> readFileForHash(const std::filesystem::path &path,
                                           DiagnosticEngine &diagnostics,
                                           std::string_view code) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    diagnostics.error(std::string(code),
                      "failed to read artifact for hashing: " + path.string());
    return std::nullopt;
  }
  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    diagnostics.error(std::string(code),
                      "failed to hash artifact: " + path.string());
    return std::nullopt;
  }
  return buffer.str();
}

std::optional<std::string> artifactSha256(const std::filesystem::path &path,
                                          DiagnosticEngine &diagnostics,
                                          std::string_view code) {
  const std::optional<std::string> contents =
      readFileForHash(path, diagnostics, code);
  if (!contents) {
    return std::nullopt;
  }
  return sha256(*contents);
}

std::optional<std::uintmax_t> artifactSize(const std::filesystem::path &path,
                                           DiagnosticEngine &diagnostics,
                                           std::string_view code) {
  std::error_code error;
  if (!std::filesystem::is_regular_file(path, error) || error) {
    diagnostics.error(std::string(code),
                      "artifact is not a regular file: " + path.string());
    return std::nullopt;
  }
  const std::uintmax_t size = std::filesystem::file_size(path, error);
  if (error) {
    diagnostics.error(std::string(code),
                      "failed to inspect artifact size: " + path.string());
    return std::nullopt;
  }
  return size;
}

class StagedPackageDirectory {
public:
  explicit StagedPackageDirectory(std::filesystem::path finalPath)
      : finalPath_(std::move(finalPath)) {}

  StagedPackageDirectory(const StagedPackageDirectory &) = delete;
  StagedPackageDirectory &operator=(const StagedPackageDirectory &) = delete;

  ~StagedPackageDirectory() {
    if (active_) {
      std::error_code ignored;
      std::filesystem::remove_all(stagingPath_, ignored);
    }
  }

  const std::filesystem::path &path() const { return stagingPath_; }

  bool create(DiagnosticEngine &diagnostics) {
    const std::filesystem::path parent = packageParentPath(finalPath_);
    std::error_code error;
    std::filesystem::create_directories(parent, error);
    if (error) {
      diagnostics.error("artifact.create-package",
                        "failed to create package parent directory: " +
                            error.message());
      return false;
    }

    const std::string prefix = packageSidecarPrefix(finalPath_);
    const std::string token = packageSidecarToken();
    for (std::size_t attempt = 0; attempt < 64; ++attempt) {
      const std::filesystem::path candidate =
          parent /
          (prefix + ".staging-" + token + "-" + std::to_string(attempt));
      if (std::filesystem::create_directory(candidate, error)) {
        stagingPath_ = candidate;
        active_ = true;
        return true;
      }
      if (error) {
        diagnostics.error("artifact.create-package",
                          "failed to create package staging directory: " +
                              error.message());
        return false;
      }
    }

    diagnostics.error("artifact.create-package",
                      "failed to create package staging directory near '" +
                          finalPath_.string() + "'");
    return false;
  }

  bool promote(DiagnosticEngine &diagnostics) {
    std::error_code error;
    const bool outputExists = std::filesystem::exists(finalPath_, error);
    if (error) {
      diagnostics.error("artifact.publish-package",
                        "failed to inspect package output path: " +
                            error.message());
      return false;
    }

    std::optional<std::filesystem::path> backupPath;
    if (outputExists) {
      if (!std::filesystem::is_directory(finalPath_, error) || error) {
        diagnostics.error(
            "artifact.publish-package",
            "package output path exists and is not a directory: " +
                finalPath_.string());
        return false;
      }

      backupPath = availablePackageSidecarPath(
          finalPath_, "previous", "artifact.publish-package", diagnostics);
      if (!backupPath) {
        return false;
      }
      std::filesystem::rename(finalPath_, *backupPath, error);
      if (error) {
        diagnostics.error("artifact.publish-package",
                          "failed to move previous package output: " +
                              error.message());
        return false;
      }
    }

    std::filesystem::rename(stagingPath_, finalPath_, error);
    if (error) {
      diagnostics.error("artifact.publish-package",
                        "failed to publish package output: " + error.message());
      if (backupPath) {
        std::error_code restoreError;
        std::filesystem::rename(*backupPath, finalPath_, restoreError);
        if (restoreError) {
          diagnostics.error("artifact.publish-package",
                            "failed to restore previous package output: " +
                                restoreError.message());
        }
      }
      return false;
    }

    active_ = false;
    if (backupPath) {
      std::filesystem::remove_all(*backupPath, error);
      if (error) {
        diagnostics.warning("artifact.cleanup-package",
                            "failed to remove previous package backup: " +
                                error.message());
      }
    }
    return true;
  }

private:
  std::filesystem::path finalPath_;
  std::filesystem::path stagingPath_;
  bool active_ = false;
};

const std::optional<std::string> *
manifestArtifactValue(const ManifestArtifactValues &values,
                      std::string_view name) {
  if (name == "backendAssembly") {
    return &values.backendAssembly;
  }
  if (name == "backendSource") {
    return &values.backendSource;
  }
  if (name == "backendSourceMap") {
    return &values.backendSourceMap;
  }
  if (name == "graphicsAbi") {
    return &values.graphicsAbi;
  }
  if (name == "intermediate") {
    return &values.intermediate;
  }
  if (name == "nativeBinary") {
    return &values.nativeBinary;
  }
  if (name == "nativeProfile") {
    return &values.nativeProfile;
  }
  if (name == "nativeArtifactDescriptor") {
    return &values.nativeArtifactDescriptor;
  }
  if (name == "nativeBinaryStatus") {
    return &values.nativeBinaryStatus;
  }
  return nullptr;
}

std::optional<std::string> *
manifestArtifactValue(ManifestArtifactValues &values, std::string_view name) {
  if (name == "backendAssembly") {
    return &values.backendAssembly;
  }
  if (name == "backendSource") {
    return &values.backendSource;
  }
  if (name == "backendSourceMap") {
    return &values.backendSourceMap;
  }
  if (name == "graphicsAbi") {
    return &values.graphicsAbi;
  }
  if (name == "intermediate") {
    return &values.intermediate;
  }
  if (name == "nativeBinary") {
    return &values.nativeBinary;
  }
  if (name == "nativeProfile") {
    return &values.nativeProfile;
  }
  if (name == "nativeArtifactDescriptor") {
    return &values.nativeArtifactDescriptor;
  }
  if (name == "nativeBinaryStatus") {
    return &values.nativeBinaryStatus;
  }
  return nullptr;
}

void setManifestArtifactValue(ManifestArtifactValues &values,
                              std::string_view name, std::string value) {
  std::optional<std::string> *slot = manifestArtifactValue(values, name);
  if (slot != nullptr) {
    *slot = std::move(value);
  }
}

template <typename Policy>
std::string_view packagePolicyArtifactKey(const Policy *policy,
                                          const std::string Policy::*member,
                                          std::string_view fallback) {
  if (policy != nullptr && !(policy->*member).empty()) {
    return std::string_view(policy->*member);
  }
  return fallback;
}

std::string_view selectNativeArtifactDescriptorArtifactKey(
    const TargetSourcePackageDescriptorPolicy *sourcePackagePolicy,
    const TargetNativePackageDescriptorPolicy *nativePackagePolicy) {
  const std::string_view sourcePackageKey = packagePolicyArtifactKey(
      sourcePackagePolicy,
      &TargetSourcePackageDescriptorPolicy::descriptorArtifactKey, "");
  if (!sourcePackageKey.empty()) {
    return sourcePackageKey;
  }
  return packagePolicyArtifactKey(
      nativePackagePolicy,
      &TargetNativePackageDescriptorPolicy::descriptorArtifactKey,
      "nativeArtifactDescriptor");
}

void appendManifestArtifact(std::vector<ManifestArtifact> &artifacts,
                            const ManifestArtifactValues &values,
                            std::string_view name) {
  const std::optional<std::string> *value = manifestArtifactValue(values, name);
  if (value != nullptr && value->has_value()) {
    artifacts.push_back({std::string(name), **value});
  }
}

void appendPackageRequirementArtifacts(
    std::vector<ManifestArtifact> &artifacts,
    const TargetPackageArtifactRequirements &requirements,
    const ManifestArtifactValues &values) {
  for (std::string_view artifactName : requirements.requiredPathArtifactKeys) {
    appendManifestArtifact(artifacts, values, artifactName);
  }
  if (requirements.requiresNativeBinaryStatus) {
    appendManifestArtifact(artifacts, values, "nativeBinaryStatus");
  }
  appendManifestArtifact(artifacts, values, "nativeProfile");
}

bool samePackageArtifactRequirements(
    const TargetPackageArtifactRequirements &lhs,
    const TargetPackageArtifactRequirements &rhs) {
  return lhs.target == rhs.target && lhs.targetName == rhs.targetName &&
         lhs.packageMode == rhs.packageMode &&
         lhs.packageModeName == rhs.packageModeName &&
         lhs.requiredPathArtifactKeys == rhs.requiredPathArtifactKeys &&
         lhs.requiresNativeBinaryStatus == rhs.requiresNativeBinaryStatus &&
         lhs.allowsPlannedNativeBinary == rhs.allowsPlannedNativeBinary &&
         lhs.allowsPlannedNativeSourceEvidence ==
             rhs.allowsPlannedNativeSourceEvidence &&
         lhs.evidenceIds == rhs.evidenceIds;
}

void appendPackageArtifactRequirementsJson(
    std::ostringstream &out,
    const TargetPackageArtifactRequirements &requirements) {
  out << "  \"packageArtifactRequirements\": {\n"
      << "    \"target\": \"" << escapeJson(requirements.targetName) << "\",\n"
      << "    \"packageMode\": \"" << escapeJson(requirements.packageModeName)
      << "\",\n"
      << "    \"requiredPathArtifacts\": [";
  for (std::size_t index = 0;
       index < requirements.requiredPathArtifactKeys.size(); ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << "\"" << escapeJson(requirements.requiredPathArtifactKeys[index])
        << "\"";
  }
  out << "],\n"
      << "    \"requiresNativeBinaryStatus\": "
      << (requirements.requiresNativeBinaryStatus ? "true" : "false") << ",\n"
      << "    \"allowsPlannedNativeBinary\": "
      << (requirements.allowsPlannedNativeBinary ? "true" : "false") << ",\n"
      << "    \"allowsPlannedNativeSourceEvidence\": "
      << (requirements.allowsPlannedNativeSourceEvidence ? "true" : "false")
      << ",\n"
      << "    \"evidenceIds\": [";
  for (std::size_t index = 0; index < requirements.evidenceIds.size();
       ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << "\"" << escapeJson(requirements.evidenceIds[index]) << "\"";
  }
  out << "]\n"
      << "  },\n";
}

std::filesystem::path
nativeArtifactDescriptorPath(const HIRModule &module, TargetKind target,
                             const std::filesystem::path &packageDir) {
  return packageDir / "backend" / targetName(target) /
         (module.name + ".native-artifact.json");
}

std::filesystem::path graphicsAbiPath(const HIRModule &module,
                                      TargetKind target,
                                      const std::filesystem::path &packageDir) {
  return packageDir / "backend" / targetName(target) /
         (module.name + ".graphics-abi.json");
}

bool isGraphicsAbiStage(std::string_view stage) {
  return stage == "vertex" || stage == "fragment";
}

bool shouldEmitGraphicsAbi(const HIRModule &module) {
  bool hasVertex = false;
  bool hasFragment = false;
  for (const HIRStage &stage : module.stages) {
    if (stage.stage == "vertex") {
      hasVertex = true;
    } else if (stage.stage == "fragment") {
      hasFragment = true;
    }
  }
  return hasVertex && hasFragment;
}

bool hasSourceLocationEvidence(const SourceLocation &location) {
  return !location.file.empty() || location.offset != 0 ||
         location.length != 0 || location.endOffset != 0;
}

const SourceLocation &sourceLocationOrFallback(const SourceLocation &preferred,
                                               const SourceLocation &fallback) {
  return hasSourceLocationEvidence(preferred) ? preferred : fallback;
}

const SourceLocation &
resourceBindingSourceLocation(const HIRResource &resource) {
  if (hasSourceLocationEvidence(resource.bindingSpan)) {
    return resource.bindingSpan;
  }
  if (hasSourceLocationEvidence(resource.layoutSpan)) {
    return resource.layoutSpan;
  }
  if (hasSourceLocationEvidence(resource.declarationSpan)) {
    return resource.declarationSpan;
  }
  return resource.nameSpan;
}

std::string sourceMapRefFile(const SourceLocation &location) {
  std::string file = location.file;
  for (char &ch : file) {
    if (ch == '\\') {
      ch = '/';
    }
  }
  return file;
}

void writeSourceMapRefJson(std::ostringstream &out,
                           const SourceLocation &location,
                           std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"file\": \"" << escapeJson(sourceMapRefFile(location))
      << "\",\n"
      << indent << "  \"line\": " << location.line << ",\n"
      << indent << "  \"column\": " << location.column << ",\n"
      << indent << "  \"offset\": " << location.offset << ",\n"
      << indent << "  \"length\": " << location.length << ",\n"
      << indent << "  \"endLine\": " << location.endLine << ",\n"
      << indent << "  \"endColumn\": " << location.endColumn << ",\n"
      << indent << "  \"endOffset\": " << location.endOffset << "\n"
      << indent << "}";
}

const HIRStage *findHIRStage(const HIRModule &module,
                             std::string_view stageName) {
  for (const HIRStage &stage : module.stages) {
    if (stage.stage == stageName) {
      return &stage;
    }
  }
  return nullptr;
}

const HIRFunction *findStageEntryFunction(const HIRModule &module,
                                          const ReflectionEntryPoint &entry) {
  const HIRStage *stage = findHIRStage(module, entry.stage);
  if (stage == nullptr) {
    return nullptr;
  }
  for (const HIRFunction &function : stage->functions) {
    if (function.name == entry.sourceName) {
      return &function;
    }
  }
  return nullptr;
}

const HIRFunction *findStageEntryFunction(const HIRModule &module,
                                          std::string_view stageName) {
  const HIRStage *stage = findHIRStage(module, stageName);
  if (stage == nullptr) {
    return nullptr;
  }
  for (const HIRFunction &function : stage->functions) {
    if (function.name == stage->entryPointName) {
      return &function;
    }
  }
  return nullptr;
}

const HIRStruct *findHIRStruct(const HIRModule &module, std::string_view name) {
  for (const HIRStruct &structure : module.structs) {
    if (structure.name == name) {
      return &structure;
    }
  }
  return nullptr;
}

const HIRStruct *findEntryReturnStruct(const HIRModule &module,
                                       std::string_view stageName) {
  const HIRFunction *function = findStageEntryFunction(module, stageName);
  if (function == nullptr) {
    return nullptr;
  }
  return findHIRStruct(module, function->returnType.name);
}

const HIRStruct *findEntryFirstParameterStruct(const HIRModule &module,
                                               std::string_view stageName) {
  const HIRFunction *function = findStageEntryFunction(module, stageName);
  if (function == nullptr || function->parameters.empty()) {
    return nullptr;
  }
  return findHIRStruct(module, function->parameters.front().type.name);
}

const HIRResource *findStageResource(const HIRModule &module,
                                     std::string_view stageName,
                                     std::string_view name,
                                     std::string_view kind) {
  const HIRStage *stage = findHIRStage(module, stageName);
  if (stage == nullptr) {
    return nullptr;
  }
  for (const HIRResource &resource : stage->resources) {
    if (resource.name == name && resourceKindName(resource.kind) == kind) {
      return &resource;
    }
  }
  return nullptr;
}

void writeGraphicsAbiArrayDimensions(
    std::ostringstream &out,
    const std::vector<ReflectionArrayDimension> &dimensions,
    std::string_view fieldPrefix) {
  if (dimensions.empty()) {
    return;
  }

  out << fieldPrefix << "\"arrayDimensions\": [";
  for (std::size_t index = 0; index < dimensions.size(); ++index) {
    if (index != 0) {
      out << ", ";
    }
    const ReflectionArrayDimension &dimension = dimensions[index];
    out << "{\"source\":\"" << escapeJson(dimension.source) << "\",\"kind\":\""
        << escapeJson(dimension.kind) << "\"";
    if (dimension.elementCount.has_value()) {
      out << ",\"elementCount\":" << *dimension.elementCount;
    }
    out << "}";
  }
  out << "]";
}

void writeGraphicsAbiStringArray(std::ostringstream &out,
                                 const std::vector<std::string> &values) {
  out << "[";
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << "\"" << escapeJson(values[index]) << "\"";
  }
  out << "]";
}

std::string graphicsAbiVertexFormat(std::string_view type) {
  if (type == "float") {
    return "float32";
  }
  if (type == "vec2") {
    return "float32x2";
  }
  if (type == "vec3") {
    return "float32x3";
  }
  if (type == "vec4") {
    return "float32x4";
  }
  if (type == "double") {
    return "float64";
  }
  if (type == "dvec2") {
    return "float64x2";
  }
  if (type == "dvec3") {
    return "float64x3";
  }
  if (type == "dvec4") {
    return "float64x4";
  }
  if (type == "int") {
    return "int32";
  }
  if (type == "ivec2") {
    return "int32x2";
  }
  if (type == "ivec3") {
    return "int32x3";
  }
  if (type == "ivec4") {
    return "int32x4";
  }
  if (type == "uint") {
    return "uint32";
  }
  if (type == "uvec2") {
    return "uint32x2";
  }
  if (type == "uvec3") {
    return "uint32x3";
  }
  if (type == "uvec4") {
    return "uint32x4";
  }
  if (type == "bool") {
    return "bool";
  }
  if (type == "mat2") {
    return "float32x2x2";
  }
  if (type == "mat3") {
    return "float32x3x3";
  }
  if (type == "mat4") {
    return "float32x4x4";
  }
  return "crossgl:" + std::string(type);
}

std::string graphicsAbiFragmentFormat(std::string_view type) {
  if (type == "float") {
    return "r32f";
  }
  if (type == "vec2") {
    return "rg32f";
  }
  if (type == "vec3") {
    return "rgb32f";
  }
  if (type == "vec4") {
    return "rgba32f";
  }
  if (type == "int") {
    return "r32i";
  }
  if (type == "ivec2") {
    return "rg32i";
  }
  if (type == "ivec3") {
    return "rgb32i";
  }
  if (type == "ivec4") {
    return "rgba32i";
  }
  if (type == "uint") {
    return "r32ui";
  }
  if (type == "uvec2") {
    return "rg32ui";
  }
  if (type == "uvec3") {
    return "rgb32ui";
  }
  if (type == "uvec4") {
    return "rgba32ui";
  }
  return "crossgl:" + std::string(type);
}

std::string graphicsAbiBackendEntryPoint(const ReflectionDocument &reflection,
                                         std::string_view stageName) {
  for (const ReflectionEntryPoint &entry : reflection.entryPoints) {
    if (entry.stage == stageName) {
      return entry.backendName;
    }
  }
  return std::string(stageName);
}

void writeGraphicsAbiEntryPoint(std::ostringstream &out,
                                const HIRModule &module,
                                const ReflectionEntryPoint &entry,
                                std::string_view indent) {
  const HIRFunction *function = findStageEntryFunction(module, entry);
  const SourceLocation sourceMapRef =
      function == nullptr ? SourceLocation{}
                          : sourceLocationOrFallback(function->nameSpan,
                                                     function->declarationSpan);
  out << indent << "{\n"
      << indent << "  \"stage\": \"" << escapeJson(entry.stage) << "\",\n"
      << indent << "  \"sourceName\": \"" << escapeJson(entry.sourceName)
      << "\",\n"
      << indent << "  \"backendName\": \"" << escapeJson(entry.backendName)
      << "\",\n"
      << indent << "  \"sourceMapRef\":\n";
  writeSourceMapRefJson(out, sourceMapRef, std::string(indent) + "  ");
  out << "\n" << indent << "}";
}

void writeGraphicsAbiVertexInput(std::ostringstream &out,
                                 const ReflectionVertexLayout &layout,
                                 const ReflectionVertexAttribute &attribute,
                                 std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"stage\": \"vertex\",\n"
      << indent << "  \"entryPoint\": \"" << escapeJson(layout.entryPoint)
      << "\",\n"
      << indent << "  \"name\": \"" << escapeJson(attribute.name) << "\",\n"
      << indent << "  \"type\": \"" << escapeJson(attribute.type) << "\",\n"
      << indent << "  \"location\": " << attribute.location << ",\n"
      << indent << "  \"format\": \""
      << escapeJson(graphicsAbiVertexFormat(attribute.type)) << "\"\n"
      << indent << "}";
}

void writeGraphicsAbiFragmentOutput(std::ostringstream &out,
                                    std::string_view entryPoint,
                                    const HIRField &field, std::size_t location,
                                    std::string_view indent) {
  const std::string type = formatType(field.type);
  out << indent << "{\n"
      << indent << "  \"stage\": \"fragment\",\n"
      << indent << "  \"entryPoint\": \"" << escapeJson(entryPoint) << "\",\n"
      << indent << "  \"name\": \"" << escapeJson(field.name) << "\",\n"
      << indent << "  \"type\": \"" << escapeJson(type) << "\",\n"
      << indent << "  \"location\": " << location << ",\n"
      << indent << "  \"format\": \""
      << escapeJson(graphicsAbiFragmentFormat(type)) << "\"\n"
      << indent << "}";
}

void writeGraphicsAbiVaryingEndpoint(
    std::ostringstream &out, std::string_view stage,
    std::string_view entryPoint, const HIRField &field, std::size_t location,
    std::string_view direction, std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"stage\": \"" << escapeJson(stage) << "\",\n"
      << indent << "  \"entryPoint\": \"" << escapeJson(entryPoint) << "\",\n"
      << indent << "  \"name\": \"" << escapeJson(field.name) << "\",\n"
      << indent << "  \"type\": \"" << escapeJson(formatType(field.type))
      << "\",\n"
      << indent << "  \"location\": " << location << ",\n"
      << indent << "  \"direction\": \"" << escapeJson(direction) << "\"\n"
      << indent << "}";
}

void writeGraphicsAbiVarying(std::ostringstream &out,
                             std::string_view vertexEntryPoint,
                             const HIRField &vertexField,
                             std::string_view fragmentEntryPoint,
                             const HIRField &fragmentField,
                             std::size_t location, std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"interpolation\": \"smooth\",\n"
      << indent << "  \"producer\":\n";
  writeGraphicsAbiVaryingEndpoint(out, "vertex", vertexEntryPoint, vertexField,
                                  location, "output",
                                  std::string(indent) + "    ");
  out << ",\n" << indent << "  \"consumer\":\n";
  writeGraphicsAbiVaryingEndpoint(out, "fragment", fragmentEntryPoint,
                                  fragmentField, location, "input",
                                  std::string(indent) + "    ");
  out << "\n" << indent << "}";
}

void writeGraphicsAbiBuiltin(std::ostringstream &out, std::string_view stage,
                             std::string_view entryPoint, const HIRField &field,
                             std::string_view builtin,
                             std::string_view direction,
                             std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"stage\": \"" << escapeJson(stage) << "\",\n"
      << indent << "  \"entryPoint\": \"" << escapeJson(entryPoint) << "\",\n"
      << indent << "  \"name\": \"" << escapeJson(field.name) << "\",\n"
      << indent << "  \"builtin\": \"" << escapeJson(builtin) << "\",\n"
      << indent << "  \"type\": \"" << escapeJson(formatType(field.type))
      << "\",\n"
      << indent << "  \"direction\": \"" << escapeJson(direction) << "\"\n"
      << indent << "}";
}

void writeGraphicsAbiResource(std::ostringstream &out, const HIRModule &module,
                              const ReflectionResource &resource,
                              std::string_view indent) {
  const HIRResource *hirResource =
      findStageResource(module, resource.stage, resource.name, resource.kind);
  const SourceLocation sourceMapRef =
      hirResource == nullptr
          ? SourceLocation{}
          : sourceLocationOrFallback(hirResource->declarationSpan,
                                     hirResource->nameSpan);
  out << indent << "{\n"
      << indent << "  \"stage\": \"" << escapeJson(resource.stage) << "\",\n"
      << indent << "  \"name\": \"" << escapeJson(resource.name) << "\",\n"
      << indent << "  \"kind\": \"" << escapeJson(resource.kind) << "\",\n"
      << indent << "  \"type\": \"" << escapeJson(resource.type) << "\"";
  if (!resource.arrayDimensions.empty()) {
    out << ",\n";
    writeGraphicsAbiArrayDimensions(out, resource.arrayDimensions,
                                    std::string(indent) + "  ");
  }
  if (resource.set.has_value()) {
    out << ",\n" << indent << "  \"set\": " << *resource.set;
  }
  if (resource.binding.has_value()) {
    out << ",\n" << indent << "  \"binding\": " << *resource.binding;
  }
  if (resource.addressSpace.has_value()) {
    out << ",\n"
        << indent << "  \"addressSpace\": \""
        << escapeJson(*resource.addressSpace) << "\"";
  }
  if (resource.storageImageFormat.has_value()) {
    out << ",\n"
        << indent << "  \"storageImageFormat\": \""
        << escapeJson(*resource.storageImageFormat) << "\"";
  }
  if (resource.storageImageAccess.has_value()) {
    out << ",\n"
        << indent << "  \"storageImageAccess\": \""
        << escapeJson(*resource.storageImageAccess) << "\"";
  }
  out << ",\n" << indent << "  \"sourceMapRef\":\n";
  writeSourceMapRefJson(out, sourceMapRef, std::string(indent) + "  ");
  out << "\n" << indent << "}";
}

void writeGraphicsAbiRecord(std::ostringstream &out, const HIRModule &module,
                            const ReflectionTargetResourceBinding &record,
                            std::string_view indent) {
  const HIRResource *resource =
      findStageResource(module, record.stage, record.name, record.kind);
  const SourceLocation sourceMapRef =
      resource == nullptr ? SourceLocation{}
                          : resourceBindingSourceLocation(*resource);
  out << indent << "{\n"
      << indent << "  \"target\": \"" << escapeJson(record.target) << "\",\n"
      << indent << "  \"stage\": \"" << escapeJson(record.stage) << "\",\n"
      << indent << "  \"entryPoint\": \"" << escapeJson(record.entryPoint)
      << "\",\n"
      << indent << "  \"name\": \"" << escapeJson(record.name) << "\",\n"
      << indent << "  \"kind\": \"" << escapeJson(record.kind) << "\",\n"
      << indent << "  \"sourceType\": \"" << escapeJson(record.sourceType)
      << "\",\n";
  if (record.metalType.has_value()) {
    out << indent << "  \"metalType\": \"" << escapeJson(*record.metalType)
        << "\",\n";
  }
  if (record.hlslType.has_value()) {
    out << indent << "  \"hlslType\": \"" << escapeJson(*record.hlslType)
        << "\",\n";
  }
  if (record.descriptorType.has_value()) {
    out << indent << "  \"descriptorType\": \""
        << escapeJson(*record.descriptorType) << "\",\n";
  }
  if (record.storageClass.has_value()) {
    out << indent << "  \"storageClass\": \""
        << escapeJson(*record.storageClass) << "\",\n";
  }
  if (record.spirvType.has_value()) {
    out << indent << "  \"spirvType\": \"" << escapeJson(*record.spirvType)
        << "\",\n";
  }
  if (record.storageImageFormat.has_value()) {
    out << indent << "  \"storageImageFormat\": \""
        << escapeJson(*record.storageImageFormat) << "\",\n";
  }
  if (record.storageImageAccess.has_value()) {
    out << indent << "  \"storageImageAccess\": \""
        << escapeJson(*record.storageImageAccess) << "\",\n";
  }
  out << indent << "  \"addressSpace\": \"" << escapeJson(record.addressSpace)
      << "\",\n"
      << indent << "  \"abi\": \"" << escapeJson(record.abi) << "\",\n"
      << indent << "  \"bindingClass\": \"" << escapeJson(record.bindingClass)
      << "\"";
  if (!record.evidenceId.empty()) {
    out << ",\n"
        << indent << "  \"evidenceId\": \"" << escapeJson(record.evidenceId)
        << "\"";
  }
  if (record.argumentIndex.has_value()) {
    out << ",\n" << indent << "  \"argumentIndex\": " << *record.argumentIndex;
  }
  if (record.set.has_value()) {
    out << ",\n" << indent << "  \"set\": " << *record.set;
  }
  if (record.binding.has_value()) {
    out << ",\n" << indent << "  \"binding\": " << *record.binding;
  }
  if (record.arraySize.has_value()) {
    out << ",\n"
        << indent << "  \"arraySize\": \"" << escapeJson(*record.arraySize)
        << "\"";
  }
  if (record.arrayElementCount.has_value()) {
    out << ",\n"
        << indent << "  \"arrayElementCount\": " << *record.arrayElementCount;
  }
  if (!record.arrayDimensions.empty()) {
    out << ",\n";
    writeGraphicsAbiArrayDimensions(out, record.arrayDimensions,
                                    std::string(indent) + "  ");
  }
  if (!record.usageRoles.empty()) {
    out << ",\n" << indent << "  \"usageRoles\": ";
    writeGraphicsAbiStringArray(out, record.usageRoles);
  }
  out << ",\n" << indent << "  \"sourceMapRef\":\n";
  writeSourceMapRefJson(out, sourceMapRef, std::string(indent) + "  ");
  out << "\n" << indent << "}";
}

std::string graphicsAbiJson(const HIRModule &module, TargetKind target,
                            const ReflectionDocument &reflection) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"module\": \"" << escapeJson(module.name) << "\",\n"
      << "  \"target\": \"" << escapeJson(targetName(target)) << "\",\n"
      << "  \"entryPoints\": [";
  bool wroteEntryPoint = false;
  for (const ReflectionEntryPoint &entry : reflection.entryPoints) {
    if (!isGraphicsAbiStage(entry.stage)) {
      continue;
    }
    out << (wroteEntryPoint ? ",\n" : "\n");
    writeGraphicsAbiEntryPoint(out, module, entry, "    ");
    wroteEntryPoint = true;
  }
  if (wroteEntryPoint) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"vertexInputs\": [";
  bool wroteVertexInput = false;
  for (const ReflectionVertexLayout &layout : reflection.vertexLayouts) {
    for (const ReflectionVertexAttribute &attribute : layout.attributes) {
      out << (wroteVertexInput ? ",\n" : "\n");
      writeGraphicsAbiVertexInput(out, layout, attribute, "    ");
      wroteVertexInput = true;
    }
  }
  if (wroteVertexInput) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"varyings\": [";
  const HIRStruct *vertexOutputs = findEntryReturnStruct(module, "vertex");
  const HIRStruct *fragmentInputs =
      findEntryFirstParameterStruct(module, "fragment");
  const std::string vertexEntryPoint =
      graphicsAbiBackendEntryPoint(reflection, "vertex");
  const std::string fragmentEntryPoint =
      graphicsAbiBackendEntryPoint(reflection, "fragment");
  bool wroteVarying = false;
  if (vertexOutputs != nullptr && fragmentInputs != nullptr) {
    std::size_t location = 0;
    for (const HIRField &vertexField : vertexOutputs->fields) {
      if (vertexField.name == "position" ||
          vertexField.name == "clipPosition") {
        continue;
      }
      const std::size_t varyingLocation = location++;
      const std::string vertexType = formatType(vertexField.type);
      for (const HIRField &fragmentField : fragmentInputs->fields) {
        if (fragmentField.name == vertexField.name &&
            formatType(fragmentField.type) == vertexType) {
          out << (wroteVarying ? ",\n" : "\n");
          writeGraphicsAbiVarying(out, vertexEntryPoint, vertexField,
                                  fragmentEntryPoint, fragmentField,
                                  varyingLocation, "    ");
          wroteVarying = true;
          break;
        }
      }
    }
  }
  if (wroteVarying) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"fragmentOutputs\": [";
  const HIRStruct *fragmentOutputs = findEntryReturnStruct(module, "fragment");
  bool wroteFragmentOutput = false;
  if (fragmentOutputs != nullptr) {
    for (std::size_t index = 0; index < fragmentOutputs->fields.size();
         ++index) {
      out << (wroteFragmentOutput ? ",\n" : "\n");
      writeGraphicsAbiFragmentOutput(out, fragmentEntryPoint,
                                     fragmentOutputs->fields[index], index,
                                     "    ");
      wroteFragmentOutput = true;
    }
  }
  if (wroteFragmentOutput) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"builtins\": [";
  bool wroteBuiltin = false;
  if (vertexOutputs != nullptr) {
    for (const HIRField &field : vertexOutputs->fields) {
      if ((field.name == "position" || field.name == "clipPosition") &&
          formatType(field.type) == "vec4") {
        out << (wroteBuiltin ? ",\n" : "\n");
        writeGraphicsAbiBuiltin(out, "vertex", vertexEntryPoint, field,
                                "position", "output", "    ");
        wroteBuiltin = true;
        break;
      }
    }
  }
  if (wroteBuiltin) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"resources\": [";
  bool wroteResource = false;
  for (const ReflectionResource &resource : reflection.resources) {
    if (!isGraphicsAbiStage(resource.stage)) {
      continue;
    }
    out << (wroteResource ? ",\n" : "\n");
    writeGraphicsAbiResource(out, module, resource, "    ");
    wroteResource = true;
  }
  if (wroteResource) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"abiRecords\": [";
  bool wroteRecord = false;
  for (const ReflectionTargetResourceBinding &record :
       reflection.targetResourceBindings) {
    if (!isGraphicsAbiStage(record.stage)) {
      continue;
    }
    out << (wroteRecord ? ",\n" : "\n");
    writeGraphicsAbiRecord(out, module, record, "    ");
    wroteRecord = true;
  }
  if (wroteRecord) {
    out << "\n  ";
  }
  out << "]\n"
      << "}\n";
  return out.str();
}

std::optional<std::filesystem::path>
writeGraphicsAbiSidecar(const HIRModule &module, TargetKind target,
                        const std::filesystem::path &packageDir,
                        const ReflectionDocument &reflection,
                        DiagnosticEngine &diagnostics) {
  if (!shouldEmitGraphicsAbi(module)) {
    return std::nullopt;
  }
  const std::filesystem::path sidecarPath =
      graphicsAbiPath(module, target, packageDir);
  if (!writeText(sidecarPath, graphicsAbiJson(module, target, reflection),
                 diagnostics, "artifact.write-graphics-abi")) {
    return std::nullopt;
  }
  return sidecarPath;
}

void writeNativeArtifactTool(std::ostringstream &out,
                             const NativeArtifactToolProvenance &tool,
                             std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"name\": \"" << escapeJson(tool.name) << "\",\n"
      << indent << "  \"role\": \"" << escapeJson(tool.role) << "\",\n"
      << indent << "  \"version\": \"" << escapeJson(tool.version) << "\",\n"
      << indent << "  \"executable\": \"" << escapeJson(tool.executable)
      << "\"";
  if (!tool.resolvedExecutable.empty()) {
    out << ",\n"
        << indent << "  \"resolvedExecutable\": \""
        << escapeJson(tool.resolvedExecutable) << "\"";
  }
  if (!tool.executableSource.empty()) {
    out << ",\n"
        << indent << "  \"executableSource\": \""
        << escapeJson(tool.executableSource) << "\"";
  }
  if (!tool.versionProbeStatus.empty()) {
    out << ",\n"
        << indent << "  \"versionProbeStatus\": \""
        << escapeJson(tool.versionProbeStatus) << "\"";
  }
  if (!tool.versionDetail.empty()) {
    out << ",\n"
        << indent << "  \"versionDetail\": \"" << escapeJson(tool.versionDetail)
        << "\"";
  }
  if (!tool.argumentsSha256.empty()) {
    out << ",\n"
        << indent << "  \"argumentsSha256\": \""
        << escapeJson(tool.argumentsSha256) << "\"";
  }
  if (!tool.commandShape.empty()) {
    out << ",\n"
        << indent << "  \"commandShape\": \""
        << escapeJson(tool.commandShape) << "\"";
  }
  if (!tool.responseFilePath.empty()) {
    out << ",\n"
        << indent << "  \"responseFilePath\": \""
        << escapeJson(tool.responseFilePath) << "\"";
  }
  if (!tool.outputPath.empty()) {
    out << ",\n"
        << indent << "  \"outputPath\": \"" << escapeJson(tool.outputPath)
        << "\"";
  }
  if (!tool.outputSha256.empty()) {
    out << ",\n"
        << indent << "  \"outputSha256\": \""
        << escapeJson(tool.outputSha256) << "\"";
  }
  if (tool.outputSizeBytes) {
    out << ",\n"
        << indent << "  \"outputSizeBytes\": " << *tool.outputSizeBytes;
  }
  if (!tool.provenanceStatus.empty()) {
    out << ",\n"
        << indent << "  \"provenanceStatus\": \""
        << escapeJson(tool.provenanceStatus) << "\"";
  }
  if (!tool.provenanceDetail.empty()) {
    out << ",\n"
        << indent << "  \"provenanceDetail\": \""
        << escapeJson(tool.provenanceDetail) << "\"";
  }
  out << "\n" << indent << "}";
}

void writeJsonStringArray(std::ostringstream &out,
                          const std::vector<std::string> &values) {
  out << "[";
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << "\"" << escapeJson(values[index]) << "\"";
  }
  out << "]";
}

void writeNativeArtifactValidationDiagnostic(std::ostringstream &out,
                                             const Diagnostic &diagnostic,
                                             std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"code\": \"" << escapeJson(diagnostic.code) << "\",\n"
      << indent << "  \"message\": \"" << escapeJson(diagnostic.message)
      << "\"\n"
      << indent << "}";
}

void appendTargetLegalizationToolRequirementsJson(
    std::ostringstream &out,
    const TargetLegalizationContractProjection &projection) {
  out << "  \"targetLegalizationToolRequirements\": {\n"
      << "    \"target\": \""
      << escapeJson(targetName(projection.targetProfile.resolvedTarget))
      << "\",\n"
      << "    \"packageMode\": \"" << escapeJson(projection.packageModeName)
      << "\",\n"
      << "    \"requiredToolCount\": " << projection.requiredToolCount << ",\n"
      << "    \"missingToolCount\": " << projection.missingToolCount << ",\n"
      << "    \"requiredToolIds\": ";
  writeJsonStringArray(out, projection.requiredToolIds);
  out << ",\n"
      << "    \"missingToolIds\": ";
  writeJsonStringArray(out, projection.missingToolIds);
  out << ",\n"
      << "    \"optionalNativeToolMissing\": "
      << (projection.optionalNativeToolMissing ? "true" : "false") << ",\n"
      << "    \"optionalNativeToolStatus\": \""
      << escapeJson(projection.optionalNativeToolStatusName) << "\",\n"
      << "    \"toolRequirementEvidenceIds\": ";
  writeJsonStringArray(out, projection.toolRequirementEvidenceIds);
  out << "\n"
      << "  },\n";
}

std::string nativeOptimizationEffectiveLevelFromFlag(std::string_view flag) {
  if (flag == "-O0") {
    return "O0";
  }
  if (flag == "-O" || flag == "-O2") {
    return "O2";
  }
  if (flag == "-O3") {
    return "O3";
  }
  if (flag == "none") {
    return "none";
  }
  return "unknown";
}

std::string
nativeOptimizationEvidenceJson(const NativeOptimizationEvidenceSpec &evidence) {
  std::ostringstream out;
  out << "{\n"
      << "    \"requestedLevel\": \"" << escapeJson(evidence.requestedLevel)
      << "\",\n"
      << "    \"effectiveLevel\": \"" << escapeJson(evidence.effectiveLevel)
      << "\",\n"
      << "    \"policy\": \"" << escapeJson(evidence.policy) << "\",\n"
      << "    \"status\": \"" << escapeJson(evidence.status) << "\"";
  if (evidence.tool) {
    out << ",\n"
        << "    \"tool\": \"" << escapeJson(*evidence.tool) << "\"";
  }
  if (evidence.toolFlag) {
    out << ",\n"
        << "    \"toolFlag\": \"" << escapeJson(*evidence.toolFlag) << "\"";
  }
  if (evidence.evidenceSourceKind) {
    out << ",\n"
        << "    \"evidenceSource\": {\n"
        << "      \"kind\": \"" << escapeJson(*evidence.evidenceSourceKind)
        << "\"";
    if (evidence.evidenceSourcePath) {
      out << ",\n"
          << "      \"path\": \"" << escapeJson(*evidence.evidenceSourcePath)
          << "\"";
    }
    out << "\n"
        << "    }";
  }
  if (evidence.debugInfo) {
    out << ",\n"
        << "    \"debugInfo\": " << (*evidence.debugInfo ? "true" : "false");
  }
  if (evidence.profile) {
    out << ",\n"
        << "    \"profile\": \"" << escapeJson(*evidence.profile) << "\"";
  }
  if (!evidence.flags.empty()) {
    out << ",\n"
        << "    \"flags\": ";
    writeJsonStringArray(out, evidence.flags);
  }
  out << "\n"
      << "  }";
  return out.str();
}

std::string spirvDependenciesJson(
    const std::vector<VulkanSPIRVImport> &extendedInstructionImports) {
  std::ostringstream out;
  out << "{\n"
      << "    \"extendedInstructionSets\": [";
  for (std::size_t index = 0; index < extendedInstructionImports.size();
       ++index) {
    const VulkanSPIRVImport &import = extendedInstructionImports[index];
    out << (index == 0 ? "\n" : ",\n") << "      {\n"
        << "        \"resultId\": \"" << escapeJson(import.resultId) << "\",\n"
        << "        \"instructionSet\": \"" << escapeJson(import.instructionSet)
        << "\"\n"
        << "      }";
  }
  if (!extendedInstructionImports.empty()) {
    out << "\n    ";
  }
  out << "]\n"
      << "  }";
  return out.str();
}

std::string
vulkanNativeOptimizationEffectiveLevel(const VulkanBuildResult &vulkanResult) {
  if (vulkanResult.optimizationStatus == "applied") {
    return nativeOptimizationEffectiveLevelFromFlag(
        vulkanResult.optimizationLevel);
  }
  if (vulkanResult.optimizationStatus == "skipped-disabled" ||
      vulkanResult.optimizationStatus == "skipped-tool-missing") {
    return "none";
  }
  return "unknown";
}

std::string directxNativeOptimizationStatus(
    const DirectXSourcePackageResult &directxResult) {
  if (directxResult.nativeBinaryStatus == "emitted" &&
      directxResult.optimizationStatus == "applied") {
    return "applied";
  }
  if (directxResult.optimizationStatus == "unavailable" ||
      directxResult.optimizationStatus == "not-run") {
    return directxResult.optimizationStatus;
  }
  return "not-run";
}

NativeOptimizationEvidenceSpec directxNativeOptimizationEvidence(
    const DirectXSourcePackageResult &directxResult) {
  NativeOptimizationEvidenceSpec evidence;
  evidence.requestedLevel = directxResult.optimizationRequestedLevel;
  evidence.effectiveLevel = "unknown";
  evidence.policy = directxResult.optimizationPolicy;
  evidence.status = directxNativeOptimizationStatus(directxResult);
  if (evidence.status == "applied") {
    evidence.effectiveLevel = nativeOptimizationEffectiveLevelFromFlag(
        directxResult.optimizationLevel);
  }
  if (evidence.requestedLevel.empty()) {
    evidence.requestedLevel = "unknown";
  }
  if (!directxResult.optimizationLevel.empty()) {
    evidence.tool = "dxc";
    evidence.toolFlag = directxResult.optimizationLevel;
  }
  if (!directxResult.shaderProfileSummary.empty()) {
    evidence.profile = directxResult.shaderProfileSummary;
  }
  return evidence;
}

NativeOptimizationEvidenceSpec metalNativeOptimizationEvidence(
    const MetalBuildResult &metalResult,
    const TargetNativePackageDescriptorPolicy &policy) {
  NativeOptimizationEvidenceSpec evidence;
  evidence.requestedLevel = metalResult.optimizationRequestedLevel;
  evidence.effectiveLevel =
      nativeOptimizationEffectiveLevelFromFlag(metalResult.optimizationLevel);
  evidence.policy = metalResult.optimizationPolicy;
  evidence.status = "applied";
  evidence.tool = policy.optimizationToolName.empty()
                      ? "xcrun metal"
                      : policy.optimizationToolName;
  evidence.toolFlag = metalResult.optimizationLevel;
  evidence.debugInfo = metalResult.optimizationDebugInfo;
  evidence.profile = metalResult.optimizationProfile;
  evidence.flags = metalResult.optimizationFlags;
  return evidence;
}

std::string nativeArtifactDescriptorJson(
    const HIRModule &module, TargetKind target,
    const std::filesystem::path &packageDir,
    const NativeArtifactDescriptorSpec &spec, std::string_view sourceHash,
    const std::optional<std::string> &artifactHash,
    const std::optional<std::uintmax_t> &artifactSizeBytes) {
  const std::string sourcePath =
      packageRelativePath(packageDir, spec.sourcePath);
  const std::optional<std::string> artifactPath =
      spec.artifactPath ? std::optional<std::string>(packageRelativePath(
                              packageDir, *spec.artifactPath))
                        : std::nullopt;
  std::vector<NativeArtifactToolProvenance> descriptorTools = spec.tools;
  if (artifactPath && artifactHash && artifactSizeBytes) {
    for (NativeArtifactToolProvenance &tool : descriptorTools) {
      if (tool.outputPath == *artifactPath) {
        tool.outputSha256 = *artifactHash;
        tool.outputSizeBytes = *artifactSizeBytes;
      }
    }
  }
  const std::string invocationFingerprint =
      std::string(targetName(target)) + "\n" + module.name + "\n" +
      spec.binaryKind + "\n" + sourcePath + "\n" +
      (artifactPath ? *artifactPath : std::string()) + "\n" +
      spec.validationStatus + "\n" + spec.optimizationLevel + "\n" +
      (spec.optimizationEvidenceJson ? *spec.optimizationEvidenceJson
                                     : std::string()) +
      "\n";
  const std::vector<VulkanSPIRVImport> spirvExtendedInstructionImports =
      canonicalizeVulkanSPIRVImports(spec.spirvExtendedInstructionImports);
  std::string spirvDependencyFingerprint;
  for (const VulkanSPIRVImport &import : spirvExtendedInstructionImports) {
    spirvDependencyFingerprint += import.resultId;
    spirvDependencyFingerprint += "\n";
    spirvDependencyFingerprint += import.instructionSet;
    spirvDependencyFingerprint += "\n";
  }
  std::string validationDiagnosticFingerprint;
  for (const Diagnostic &diagnostic : spec.validationDiagnostics) {
    validationDiagnosticFingerprint += diagnostic.code;
    validationDiagnosticFingerprint += "\n";
    validationDiagnosticFingerprint += diagnostic.message;
    validationDiagnosticFingerprint += "\n";
  }
  std::string toolInvocationFingerprint;
  for (const NativeArtifactToolProvenance &tool : descriptorTools) {
    toolInvocationFingerprint += tool.name;
    toolInvocationFingerprint += "\n";
    toolInvocationFingerprint += tool.role;
    toolInvocationFingerprint += "\n";
    toolInvocationFingerprint += tool.argumentsSha256;
    toolInvocationFingerprint += "\n";
    toolInvocationFingerprint += tool.commandShape;
    toolInvocationFingerprint += "\n";
    toolInvocationFingerprint += tool.outputPath;
    toolInvocationFingerprint += "\n";
    toolInvocationFingerprint += tool.provenanceStatus;
    toolInvocationFingerprint += "\n";
  }

  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"kind\": \"crossgl.nativeArtifact\",\n"
      << "  \"contractVersion\": \"native-artifact-v0\",\n"
      << "  \"target\": \"" << escapeJson(targetName(target)) << "\",\n"
      << "  \"binaryKind\": \"" << escapeJson(spec.binaryKind) << "\",\n"
      << "  \"sourcePath\": \"" << escapeJson(sourcePath) << "\",\n"
      << "  \"sourceHash\": {\n"
      << "    \"algorithm\": \"sha256\",\n"
      << "    \"value\": \"" << escapeJson(std::string(sourceHash)) << "\"\n"
      << "  }";
  if (artifactPath && artifactHash && artifactSizeBytes) {
    out << ",\n"
        << "  \"artifactPath\": \"" << escapeJson(*artifactPath) << "\",\n"
        << "  \"artifactHash\": {\n"
        << "    \"algorithm\": \"sha256\",\n"
        << "    \"value\": \"" << escapeJson(*artifactHash) << "\"\n"
        << "  },\n"
        << "  \"sizeBytes\": " << *artifactSizeBytes;
  }
  if (!spirvExtendedInstructionImports.empty()) {
    out << ",\n"
        << "  \"spirvDependencies\": "
        << spirvDependenciesJson(spirvExtendedInstructionImports);
  }
  out << ",\n"
      << "  \"toolchainProvenance\": {\n"
      << "    \"producer\": \"CrossGL-Compiler\",\n"
      << "    \"tools\": [";
  for (std::size_t index = 0; index < descriptorTools.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeNativeArtifactTool(out, descriptorTools[index], "      ");
  }
  if (!descriptorTools.empty()) {
    out << "\n    ";
  }
  out << "],\n"
      << "    \"invocation\": {\n"
      << "      \"commandLineSha256\": \""
      << escapeJson(sha256(invocationFingerprint + spirvDependencyFingerprint +
                           validationDiagnosticFingerprint +
                           toolInvocationFingerprint))
      << "\",\n"
      << "      \"environmentSha256\": \"" << escapeJson(sha256("")) << "\"\n"
      << "    }\n"
      << "  },\n"
      << "  \"optimizationLevel\": \"" << escapeJson(spec.optimizationLevel)
      << "\"";
  if (spec.optimizationEvidenceJson) {
    out << ",\n"
        << "  \"optimizationEvidence\": " << *spec.optimizationEvidenceJson;
  }
  out << ",\n"
      << "  \"validationStatus\": \"" << escapeJson(spec.validationStatus)
      << "\"";
  if (spec.nativeBinaryStatus) {
    out << ",\n"
        << "  \"nativeBinaryStatus\": \""
        << escapeJson(*spec.nativeBinaryStatus) << "\"";
  }
  out << ",\n"
      << "  \"validationDiagnostics\": [";
  for (std::size_t index = 0; index < spec.validationDiagnostics.size();
       ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeNativeArtifactValidationDiagnostic(
        out, spec.validationDiagnostics[index], "    ");
  }
  if (!spec.validationDiagnostics.empty()) {
    out << "\n  ";
  }
  out << "]\n"
      << "}\n";
  return out.str();
}

std::optional<std::filesystem::path>
writeNativeArtifactDescriptor(const HIRModule &module, TargetKind target,
                              const std::filesystem::path &packageDir,
                              const NativeArtifactDescriptorSpec &spec,
                              DiagnosticEngine &diagnostics) {
  const std::optional<std::string> sourceHash = artifactSha256(
      spec.sourcePath, diagnostics, "artifact.native-descriptor-source-hash");
  if (!sourceHash) {
    return std::nullopt;
  }

  std::optional<std::string> nativeHash;
  std::optional<std::uintmax_t> nativeSize;
  if (spec.artifactPath) {
    nativeHash = artifactSha256(*spec.artifactPath, diagnostics,
                                "artifact.native-descriptor-artifact-hash");
    nativeSize = artifactSize(*spec.artifactPath, diagnostics,
                              "artifact.native-descriptor-artifact-size");
    if (!nativeHash || !nativeSize) {
      return std::nullopt;
    }
  }

  const std::filesystem::path descriptorPath =
      nativeArtifactDescriptorPath(module, target, packageDir);
  std::string descriptorJson;
  try {
    descriptorJson = nativeArtifactDescriptorJson(
        module, target, packageDir, spec, *sourceHash, nativeHash, nativeSize);
  } catch (const std::logic_error &error) {
    diagnostics.error("artifact.native-descriptor-spirv-dependencies",
                      error.what());
    return std::nullopt;
  }
  if (!writeText(descriptorPath, descriptorJson, diagnostics,
                 "artifact.write-native-artifact-descriptor")) {
    return std::nullopt;
  }
  return descriptorPath;
}

NativeArtifactToolProvenance
nativeArtifactTool(std::string name, std::string role, std::string executable,
                   std::string probeToolName = "") {
  NativeArtifactToolProvenance tool;
  tool.name = std::move(name);
  tool.role = std::move(role);
  tool.version = "unknown";
  tool.executable = std::move(executable);
  const ToolStatus status =
      detectTool(probeToolName.empty() ? tool.executable : probeToolName);
  if (!status.version.empty()) {
    tool.version = status.version;
  }
  tool.resolvedExecutable = status.resolvedPath;
  tool.executableSource = status.source;
  tool.versionProbeStatus = status.probeStatus;
  tool.versionDetail = status.versionDetail;
  if (status.source == "not-found") {
    tool.provenanceStatus = "missing-tool";
    tool.provenanceDetail =
        "tool '" + tool.name + "' was not found; command was not invoked";
  }
  return tool;
}

std::string descriptorRelativePath(const std::filesystem::path &packageDir,
                                   std::string_view path) {
  if (path.empty()) {
    return {};
  }
  const std::filesystem::path parsed(path);
  if (parsed.is_absolute()) {
    return packageRelativePath(packageDir, parsed);
  }
  return parsed.generic_string();
}

void applyInvocationProvenance(
    NativeArtifactToolProvenance &tool,
    const ToolInvocationProvenance &invocation,
    const std::filesystem::path &packageDir) {
  if (!invocation.version.empty()) {
    tool.version = invocation.version;
  }
  if (!invocation.executable.empty()) {
    tool.executable = invocation.executable;
  }
  tool.resolvedExecutable = invocation.resolvedExecutable;
  tool.executableSource = invocation.executableSource;
  tool.versionProbeStatus = invocation.versionProbeStatus;
  tool.versionDetail = invocation.versionDetail;
  tool.argumentsSha256 = invocation.argumentsSha256;
  tool.commandShape = invocation.commandShape;
  tool.responseFilePath =
      descriptorRelativePath(packageDir, invocation.responseFilePath);
  tool.outputPath = descriptorRelativePath(packageDir, invocation.outputPath);
  tool.provenanceStatus = invocation.provenanceStatus;
  tool.provenanceDetail = invocation.provenanceDetail;
}

void applyInvocationProvenance(
    std::vector<NativeArtifactToolProvenance> &tools, std::string_view name,
    std::string_view role, const ToolInvocationProvenance &invocation,
    const std::filesystem::path &packageDir) {
  for (NativeArtifactToolProvenance &tool : tools) {
    if (tool.name == name && tool.role == role) {
      applyInvocationProvenance(tool, invocation, packageDir);
      return;
    }
  }
}

NativeArtifactToolProvenance crossglGeneratorTool() {
  NativeArtifactToolProvenance tool;
  tool.name = "CrossGL-Compiler";
  tool.role = "generator";
  tool.version = CROSSGL_VERSION;
  tool.executable = "cglc";
  return tool;
}

NativeArtifactToolProvenance crossglBackendGeneratorTool(TargetKind target) {
  NativeArtifactToolProvenance tool;
  switch (target) {
  case TargetKind::Auto:
    tool.name = "CrossGL backend";
    break;
  case TargetKind::DirectX:
    tool.name = "CrossGL DirectX backend";
    break;
  case TargetKind::OpenGL:
    tool.name = "CrossGL OpenGL backend";
    break;
  case TargetKind::Metal:
    tool.name = "CrossGL Metal backend";
    break;
  case TargetKind::Vulkan:
    tool.name = "CrossGL Vulkan backend";
    break;
  case TargetKind::WGSL:
    tool.name = "CrossGL WGSL backend";
    break;
  }
  tool.role = "generator";
  tool.version = CROSSGL_VERSION;
  tool.executable = "cglc";
  return tool;
}

std::string nativeDescriptorOptimizationLevel(OptimizationLevel level) {
  return std::string(optimizationLevelName(level));
}

std::vector<NativeArtifactToolProvenance> nativeDescriptorTools(
    std::initializer_list<NativeArtifactToolProvenance> backendTools) {
  std::vector<NativeArtifactToolProvenance> tools;
  tools.push_back(crossglGeneratorTool());
  tools.insert(tools.end(), backendTools.begin(), backendTools.end());
  return tools;
}

std::vector<NativeArtifactToolProvenance> nativeDescriptorTools(
    const std::vector<TargetNativePackageToolPolicy> &backendToolPolicies) {
  std::vector<NativeArtifactToolProvenance> backendTools;
  backendTools.reserve(backendToolPolicies.size());
  for (const TargetNativePackageToolPolicy &policy : backendToolPolicies) {
    backendTools.push_back(nativeArtifactTool(
        policy.name, policy.role, policy.executable, policy.probeName));
  }

  std::vector<NativeArtifactToolProvenance> tools;
  tools.push_back(crossglGeneratorTool());
  tools.insert(tools.end(), backendTools.begin(), backendTools.end());
  return tools;
}

std::vector<NativeArtifactToolProvenance>
plannedSourcePackageDescriptorTools(TargetKind target) {
  return {crossglBackendGeneratorTool(target)};
}

std::string sourcePackageDescriptorOptimizationLevel(
    const TargetSourcePackageDescriptorPolicy &policy,
    OptimizationLevel requestedLevel) {
  if (policy.optimizationLevelMode ==
      TargetSourcePackageDescriptorOptimizationLevelMode::RequestedLevel) {
    return nativeDescriptorOptimizationLevel(requestedLevel);
  }
  return policy.fixedOptimizationLevel;
}

std::optional<std::string> sourcePackageDescriptorOptimizationEvidenceJson(
    const TargetSourcePackageDescriptorPolicy &policy,
    const DirectXSourcePackageResult &directxResult) {
  switch (policy.optimizationEvidenceMode) {
  case TargetSourcePackageDescriptorOptimizationEvidenceMode::None:
    return std::nullopt;
  case TargetSourcePackageDescriptorOptimizationEvidenceMode::DirectXDxc:
    return nativeOptimizationEvidenceJson(
        directxNativeOptimizationEvidence(directxResult));
  }
  return std::nullopt;
}

std::vector<NativeArtifactToolProvenance> sourcePackageDescriptorTools(
    const TargetSourcePackageDescriptorPolicy &policy) {
  switch (policy.toolProvenanceMode) {
  case TargetSourcePackageDescriptorToolProvenanceMode::Planned:
    return plannedSourcePackageDescriptorTools(policy.target);
  case TargetSourcePackageDescriptorToolProvenanceMode::NativeCompiler:
    if (!policy.nativeToolName.empty() && !policy.nativeToolRole.empty() &&
        !policy.nativeToolExecutable.empty()) {
      return nativeDescriptorTools({nativeArtifactTool(
          policy.nativeToolName, policy.nativeToolRole,
          policy.nativeToolExecutable, policy.nativeToolProbeName)});
    }
    break;
  case TargetSourcePackageDescriptorToolProvenanceMode::NativeValidator:
    if (!policy.nativeToolName.empty() && !policy.nativeToolRole.empty() &&
        !policy.nativeToolExecutable.empty()) {
      return nativeDescriptorTools({nativeArtifactTool(
          policy.nativeToolName, policy.nativeToolRole,
          policy.nativeToolExecutable, policy.nativeToolProbeName)});
    }
    break;
  }
  return plannedSourcePackageDescriptorTools(policy.target);
}

bool requireSourcePackageArtifactRequirements(
    const SourcePackageArtifact &artifact,
    const TargetLegalizationContractProjection &projection,
    DiagnosticEngine &diagnostics) {
  if (targetLegalizationProjectionAllowsSourcePackageNativeBinaryStatus(
          projection, artifact.nativeBinaryStatus)) {
    return true;
  }

  const TargetPackageArtifactRequirements &requirements =
      projection.packageArtifactRequirements;
  const std::string target =
      requirements.targetName.empty()
          ? std::string(targetName(projection.targetProfile.resolvedTarget))
          : requirements.targetName;
  diagnostics.error("target.package-artifacts.native-binary-status",
                    "source package nativeBinaryStatus '" +
                        artifact.nativeBinaryStatus +
                        "' is not admitted by target legalization projection "
                        "packageArtifactRequirements "
                        "for " +
                        target);
  return false;
}

std::optional<std::filesystem::path> sourcePackageNativeArtifactPath(
    const SourcePackageArtifact &artifact,
    const TargetSourcePackageDescriptorPolicy &policy) {
  if (!policy.requiresProducedNativeArtifact) {
    return std::nullopt;
  }
  return artifact.nativeBinary;
}

NativeArtifactDescriptorSpec
sourcePackageDescriptorSpec(const SourcePackageArtifact &artifact,
                            const TargetSourcePackageDescriptorPolicy &policy,
                            OptimizationLevel requestedLevel) {
  NativeArtifactDescriptorSpec descriptorSpec;
  descriptorSpec.binaryKind = policy.binaryKind;
  descriptorSpec.sourcePath = artifact.backendSource;
  descriptorSpec.artifactPath =
      sourcePackageNativeArtifactPath(artifact, policy);
  if (policy.includesNativeBinaryStatus) {
    descriptorSpec.nativeBinaryStatus = artifact.nativeBinaryStatus;
  }
  descriptorSpec.validationStatus = policy.validationStatus;
  descriptorSpec.optimizationLevel =
      sourcePackageDescriptorOptimizationLevel(policy, requestedLevel);
  descriptorSpec.tools = sourcePackageDescriptorTools(policy);
  return descriptorSpec;
}

NativeArtifactDescriptorSpec
directxNativeDescriptorSpec(const DirectXSourcePackageResult &directxResult,
                            const TargetNativePackageDescriptorPolicy &policy,
                            const std::filesystem::path &packageDir) {
  NativeArtifactDescriptorSpec descriptorSpec;
  descriptorSpec.binaryKind = policy.binaryKind;
  descriptorSpec.sourcePath = directxResult.sourcePath;
  descriptorSpec.artifactPath = directxResult.nativeBinaryPath;
  descriptorSpec.validationStatus = policy.validationStatus;
  descriptorSpec.optimizationLevel =
      directxResult.optimizationRequestedLevel.empty()
          ? "unknown"
          : directxResult.optimizationRequestedLevel;
  descriptorSpec.optimizationEvidenceJson = nativeOptimizationEvidenceJson(
      directxNativeOptimizationEvidence(directxResult));
  descriptorSpec.tools = nativeDescriptorTools(policy.requiredTools);
  if (directxResult.dxcProvenance) {
    applyInvocationProvenance(descriptorSpec.tools, "dxc", "compiler",
                              *directxResult.dxcProvenance, packageDir);
  }
  return descriptorSpec;
}

std::string projectionResolvedTargetName(
    const TargetLegalizationContractProjection &projection) {
  if (!projection.targetProfile.resolvedTargetName.empty()) {
    return projection.targetProfile.resolvedTargetName;
  }
  if (projection.targetProfile.resolvedTarget != TargetKind::Auto) {
    return std::string(targetName(projection.targetProfile.resolvedTarget));
  }
  return projection.packageArtifactRequirements.targetName.empty()
             ? std::string(
                   targetName(projection.packageArtifactRequirements.target))
             : projection.packageArtifactRequirements.targetName;
}

bool projectionSupportsPackage(
    const TargetLegalizationContractProjection &projection) {
  return targetLegalizationProjectionSupportsPackage(projection);
}

DebugMetadataTargetCapabilitySummary debugSummaryFromProjection(
    const TargetLegalizationContractProjection &projection) {
  DebugMetadataTargetCapabilitySummary summary;
  summary.target = projectionResolvedTargetName(projection);
  summary.nativeImplemented = projection.nativeImplemented;
  summary.sourcePackageSupported = projection.sourcePackageSupported;
  summary.packageBuildSupported = projectionSupportsPackage(projection);
  summary.packageMode = projection.packageModeName;
  summary.packageDecisionReason = projection.reason;
  summary.decisionReasonCodes = projection.consumerDecisionReasonCodes;
  summary.packageRankScore = projection.packageRankScore;
  summary.requiredCapabilityCount = projection.requiredCapabilityCount;
  summary.missingCapabilityCount = projection.missingCapabilityCount;
  summary.requiredToolCount = projection.requiredToolCount;
  summary.missingToolCount = projection.missingToolCount;
  summary.requiredCapabilities = projection.requiredCapabilityIds;
  summary.missingCapabilities = projection.missingCapabilityIds;
  summary.legalizationCoreEvidenceIds = projection.coreEvidenceIds;
  summary.requiredToolIds = projection.requiredToolIds;
  summary.missingToolIds = projection.missingToolIds;
  summary.optionalNativeToolMissing = projection.optionalNativeToolMissing;
  summary.optionalNativeToolStatus = projection.optionalNativeToolStatusName;
  summary.toolRequirementEvidenceIds = projection.toolRequirementEvidenceIds;
  summary.packageArtifactRequirementEvidenceIds =
      projection.packageArtifactRequirementEvidenceIds;
  return summary;
}

void applyDebugMetadataProjection(
    DebugMetadataDocument &document,
    const TargetLegalizationContractProjection &projection,
    TargetKind requestedTarget, bool singleTargetProjection) {
  const std::string resolvedTargetName =
      projectionResolvedTargetName(projection);
  const DebugMetadataTargetCapabilitySummary summary =
      debugSummaryFromProjection(projection);
  if (singleTargetProjection) {
    document.targetCapabilities.defaultTarget = resolvedTargetName;
    document.targetCapabilities.summaries = {summary};
  } else {
    bool replacedSummary = false;
    for (DebugMetadataTargetCapabilitySummary &existing :
         document.targetCapabilities.summaries) {
      if (existing.target == resolvedTargetName) {
        existing = summary;
        replacedSummary = true;
        break;
      }
    }
    if (!replacedSummary) {
      document.targetCapabilities.summaries.push_back(summary);
    }
  }

  document.targetDecision.requestedTarget =
      std::string(targetName(requestedTarget));
  document.targetDecision.selectedTarget = resolvedTargetName;
  document.targetDecision.selectedTargetNativeImplemented =
      projection.nativeImplemented;
  document.targetDecision.selectedTargetSourcePackageSupported =
      projection.sourcePackageSupported;
  document.targetDecision.selectedTargetPackageBuildSupported =
      projectionSupportsPackage(projection);
  document.targetDecision.selectedTargetPackageMode =
      projection.packageModeName;
  document.targetDecision.selectedTargetMissingCapabilityCount =
      projection.missingCapabilityCount;
  document.targetDecision.selectedTargetRequiredToolCount =
      projection.requiredToolCount;
  document.targetDecision.selectedTargetMissingToolCount =
      projection.missingToolCount;
  document.targetDecision.selectedTargetMissingCapabilities =
      projection.missingCapabilityIds;
  document.targetDecision.selectedTargetLegalizationCoreEvidenceIds =
      projection.coreEvidenceIds;
  document.targetDecision.selectedTargetRequiredToolIds =
      projection.requiredToolIds;
  document.targetDecision.selectedTargetMissingToolIds =
      projection.missingToolIds;
  document.targetDecision.selectedTargetOptionalNativeToolMissing =
      projection.optionalNativeToolMissing;
  document.targetDecision.selectedTargetOptionalNativeToolStatus =
      projection.optionalNativeToolStatusName;
  document.targetDecision.selectedTargetToolRequirementEvidenceIds =
      projection.toolRequirementEvidenceIds;
  document.targetDecision.packageArtifactRequirementEvidenceIds =
      projection.packageArtifactRequirementEvidenceIds;
  document.targetDecision.selectedTargetDiagnosticCount = 0;
  document.targetDecision.diagnostics.clear();
}

std::string
remediationFromProjection(const TargetLegalizationContractProjection &projection) {
  if (projection.packageModeName == "native") {
    return "No remediation required; native package output is available.";
  }
  if (projection.packageModeName == "source-package") {
    if (!projection.missingCapabilityIds.empty()) {
      std::ostringstream out;
      out << "Source package output is available; native artifact remediation "
             "requires satisfying: ";
      for (std::size_t index = 0; index < projection.missingCapabilityIds.size();
           ++index) {
        if (index != 0) {
          out << ", ";
        }
        out << projection.missingCapabilityIds[index];
      }
      out << ".";
      return out.str();
    }
    return "No remediation required; source package output is available.";
  }
  if (!projection.missingCapabilityIds.empty()) {
    std::ostringstream out;
    out << "Select a buildable target or satisfy missing target capabilities: ";
    for (std::size_t index = 0; index < projection.missingCapabilityIds.size();
         ++index) {
      if (index != 0) {
        out << ", ";
      }
      out << projection.missingCapabilityIds[index];
    }
    out << ".";
    return out.str();
  }
  return "Select a buildable target.";
}

TargetExplanationTargetRecord targetExplanationRecordFromProjection(
    const TargetLegalizationContractProjection &projection) {
  const std::string resolvedTargetName =
      projectionResolvedTargetName(projection);
  TargetExplanationTargetRecord record;
  record.target = resolvedTargetName;
  record.nativeImplemented = projection.nativeImplemented;
  record.sourcePackageSupported = projection.sourcePackageSupported;
  record.packageBuildSupported = projectionSupportsPackage(projection);
  record.supportStatus = projection.supportStatusName;
  record.legalizationState = projection.stateName;
  record.packageMode = projection.packageModeName;
  record.packageDecisionProvenance = projection.packageDecisionProvenanceName;
  record.packageDecisionReason = projection.reason;
  record.decisionReasonCodes = projection.consumerDecisionReasonCodes;
  record.packageRankScore = projection.packageRankScore;
  record.targetBackend = resolvedTargetName;
  record.artifactLinks = {"ir/target-explanation.json#targets/" +
                          resolvedTargetName};
  record.reportLinks = {"target-explanation-v1#targets/" + resolvedTargetName};
  record.remediation = remediationFromProjection(projection);
  record.requiredCapabilityCount = projection.requiredCapabilityCount;
  record.missingCapabilityCount = projection.missingCapabilityCount;
  record.requiredCapabilities = projection.requiredCapabilityIds;
  record.missingCapabilities = projection.missingCapabilityIds;
  record.legalizationCoreEvidenceIds = projection.coreEvidenceIds;
  record.diagnosticEvidenceIds = projection.diagnosticEvidenceIds;
  record.requiredToolCount = projection.requiredToolCount;
  record.missingToolCount = projection.missingToolCount;
  record.requiredToolIds = projection.requiredToolIds;
  record.missingToolIds = projection.missingToolIds;
  record.optionalNativeToolMissing = projection.optionalNativeToolMissing;
  record.optionalNativeToolStatus = projection.optionalNativeToolStatusName;
  record.toolRequirementEvidenceIds = projection.toolRequirementEvidenceIds;
  record.packageArtifactRequirementEvidenceIds =
      projection.packageArtifactRequirementEvidenceIds;
  return record;
}

bool isBuildableTargetExplanationRecord(
    const TargetExplanationTargetRecord &record) {
  return record.packageBuildSupported && !record.legalizationCoreEvidenceIds.empty();
}

void refreshTargetExplanationRecommendation(TargetExplanationDocument &document) {
  document.buildableTargetCount = 0;
  document.recommendedTarget.reset();
  document.recommendedPackageMode.reset();
  const TargetExplanationTargetRecord *recommended = nullptr;
  for (const TargetExplanationTargetRecord &record : document.targets) {
    if (!isBuildableTargetExplanationRecord(record)) {
      continue;
    }
    ++document.buildableTargetCount;
    if (recommended == nullptr ||
        record.packageRankScore < recommended->packageRankScore ||
        (record.packageRankScore == recommended->packageRankScore &&
         record.target == document.defaultTarget &&
         recommended->target != document.defaultTarget)) {
      recommended = &record;
    }
  }
  if (recommended != nullptr) {
    document.recommendedTarget = recommended->target;
    document.recommendedPackageMode = recommended->packageMode;
  }
}

void applyTargetExplanationProjection(
    TargetExplanationDocument &document,
    const TargetLegalizationContractProjection &projection,
    bool singleTargetProjection) {
  TargetExplanationTargetRecord record =
      targetExplanationRecordFromProjection(projection);
  if (singleTargetProjection) {
    document.targets = {std::move(record)};
    document.defaultTarget = document.targets.front().target;
  } else {
    bool replacedRecord = false;
    for (TargetExplanationTargetRecord &existing : document.targets) {
      if (existing.target == record.target) {
        existing = std::move(record);
        replacedRecord = true;
        break;
      }
    }
    if (!replacedRecord) {
      document.targets.push_back(std::move(record));
    }
  }
  refreshTargetExplanationRecommendation(document);
}

TargetExplanationDocument targetExplanationDocumentFromProjection(
    const HIRModule &module,
    const TargetLegalizationContractProjection &projection) {
  TargetExplanationDocument document;
  document.module = module.name;
  document.targets.push_back(targetExplanationRecordFromProjection(projection));
  document.defaultTarget = document.targets.front().target;
  refreshTargetExplanationRecommendation(document);
  return document;
}

bool rewriteDirectXTargetLegalizationSidecars(
    const HIRModule &module, TargetKind requestedTarget,
    const TargetLegalizationContractProjection &projection,
    const DebugMetadataOptions &debugMetadataOptions,
    const std::optional<std::filesystem::path> &debugMetadataPath,
    const std::optional<std::filesystem::path> &targetExplanationPath,
    DiagnosticEngine &diagnostics, bool singleTargetProjection) {
  if (debugMetadataPath) {
    DebugMetadataDocument document = buildDebugMetadataDocument(
        module, requestedTarget, std::nullopt, debugMetadataOptions);
    applyDebugMetadataProjection(document, projection, requestedTarget,
                                 singleTargetProjection);
    if (!writeText(*debugMetadataPath, debugMetadataJson(document), diagnostics,
                   "artifact.write-debug-metadata")) {
      return false;
    }
  }
  if (targetExplanationPath) {
    TargetExplanationDocument document =
        singleTargetProjection
            ? targetExplanationDocumentFromProjection(module, projection)
            : buildTargetExplanationDocument(module);
    if (!singleTargetProjection) {
      applyTargetExplanationProjection(document, projection,
                                       singleTargetProjection);
    }
    if (!writeText(*targetExplanationPath, targetExplanationJson(document),
                   diagnostics, "artifact.write-target-explanation")) {
      return false;
    }
  }
  return true;
}

std::string manifestJson(
    const HIRModule &module, TargetKind target, std::string_view sourceHash,
    const std::filesystem::path &packageDir,
    const TargetPackageArtifactRequirements &requirements,
    const TargetLegalizationContractProjection &projection,
    const MetalBuildResult *metalResult = nullptr,
    const VulkanBuildResult *vulkanResult = nullptr,
    const std::filesystem::path *vulkanProfilePath = nullptr,
    const SourcePackageArtifact *sourceArtifact = nullptr,
    const TargetSourcePackageDescriptorPolicy *sourcePackagePolicy = nullptr,
    const std::filesystem::path *nativeArtifactDescriptorPath = nullptr,
    const std::filesystem::path *debugMetadataPath = nullptr,
    const std::filesystem::path *hirSourceMapPath = nullptr,
    const std::filesystem::path *backendSourceMapPath = nullptr,
    const std::filesystem::path *sourceRemapProvenancePath = nullptr,
    const std::filesystem::path *targetExplanationPath = nullptr,
    const std::filesystem::path *graphicsAbiPath = nullptr,
    const TargetNativePackageDescriptorPolicy *nativePackagePolicy = nullptr,
    const DirectXSourcePackageResult *directxResult = nullptr) {
  ManifestArtifactValues artifactValues;
  std::vector<ManifestArtifact> artifacts;
  if (metalResult) {
    const std::string_view sourceArtifactKey = packagePolicyArtifactKey(
        nativePackagePolicy,
        &TargetNativePackageDescriptorPolicy::sourceArtifactKey,
        "backendSource");
    const std::string_view nativeBinaryArtifactKey = packagePolicyArtifactKey(
        nativePackagePolicy,
        &TargetNativePackageDescriptorPolicy::nativeBinaryArtifactKey,
        "nativeBinary");
    setManifestArtifactValue(
        artifactValues, sourceArtifactKey,
        packageRelativePath(packageDir, metalResult->sourcePath));
    artifactValues.intermediate =
        packageRelativePath(packageDir, metalResult->airPath);
    setManifestArtifactValue(
        artifactValues, nativeBinaryArtifactKey,
        packageRelativePath(packageDir, metalResult->metallibPath));
  } else if (vulkanResult) {
    const std::string_view sourceArtifactKey = packagePolicyArtifactKey(
        nativePackagePolicy,
        &TargetNativePackageDescriptorPolicy::sourceArtifactKey,
        "backendAssembly");
    const std::string_view nativeBinaryArtifactKey = packagePolicyArtifactKey(
        nativePackagePolicy,
        &TargetNativePackageDescriptorPolicy::nativeBinaryArtifactKey,
        "nativeBinary");
    setManifestArtifactValue(
        artifactValues, sourceArtifactKey,
        packageRelativePath(packageDir, vulkanResult->assemblyPath));
    setManifestArtifactValue(
        artifactValues, nativeBinaryArtifactKey,
        packageRelativePath(packageDir, vulkanResult->spvPath));
    if (vulkanProfilePath != nullptr) {
      const std::string_view profileArtifactKey = packagePolicyArtifactKey(
          nativePackagePolicy,
          &TargetNativePackageDescriptorPolicy::profileArtifactKey,
          "nativeProfile");
      setManifestArtifactValue(
          artifactValues, profileArtifactKey,
          packageRelativePath(packageDir, *vulkanProfilePath));
    }
  } else if (directxResult) {
    const std::string_view sourceArtifactKey = packagePolicyArtifactKey(
        nativePackagePolicy,
        &TargetNativePackageDescriptorPolicy::sourceArtifactKey,
        "backendSource");
    const std::string_view nativeBinaryArtifactKey = packagePolicyArtifactKey(
        nativePackagePolicy,
        &TargetNativePackageDescriptorPolicy::nativeBinaryArtifactKey,
        "nativeBinary");
    setManifestArtifactValue(
        artifactValues, sourceArtifactKey,
        packageRelativePath(packageDir, directxResult->sourcePath));
    setManifestArtifactValue(
        artifactValues, nativeBinaryArtifactKey,
        packageRelativePath(packageDir, directxResult->nativeBinaryPath));
  } else if (sourceArtifact) {
    const std::string_view sourceArtifactKey = packagePolicyArtifactKey(
        sourcePackagePolicy,
        &TargetSourcePackageDescriptorPolicy::sourceArtifactKey,
        "backendSource");
    const std::string_view nativeBinaryArtifactKey = packagePolicyArtifactKey(
        sourcePackagePolicy,
        &TargetSourcePackageDescriptorPolicy::nativeBinaryArtifactKey,
        "nativeBinary");
    setManifestArtifactValue(
        artifactValues, sourceArtifactKey,
        packageRelativePath(packageDir, sourceArtifact->backendSource));
    setManifestArtifactValue(
        artifactValues, nativeBinaryArtifactKey,
        packageRelativePath(packageDir, sourceArtifact->nativeBinary));
    if (sourcePackagePolicy == nullptr ||
        sourcePackagePolicy->includesNativeBinaryStatus) {
      setManifestArtifactValue(artifactValues, "nativeBinaryStatus",
                               sourceArtifact->nativeBinaryStatus);
    }
  } else {
    artifactValues.nativeBinary = "";
  }
  const std::string_view nativeArtifactDescriptorArtifactKey =
      selectNativeArtifactDescriptorArtifactKey(sourcePackagePolicy,
                                                nativePackagePolicy);
  if (nativeArtifactDescriptorPath != nullptr) {
    setManifestArtifactValue(
        artifactValues, nativeArtifactDescriptorArtifactKey,
        packageRelativePath(packageDir, *nativeArtifactDescriptorPath));
  }
  appendPackageRequirementArtifacts(artifacts, requirements, artifactValues);
  if (debugMetadataPath != nullptr) {
    artifacts.push_back(
        {"debugMetadata", packageRelativePath(packageDir, *debugMetadataPath)});
  }
  if (hirSourceMapPath != nullptr) {
    artifacts.push_back(
        {"hirSourceMap", packageRelativePath(packageDir, *hirSourceMapPath)});
  }
  if (backendSourceMapPath != nullptr) {
    artifacts.push_back({"backendSourceMap",
                         packageRelativePath(packageDir,
                                             *backendSourceMapPath)});
  }
  if (sourceRemapProvenancePath != nullptr) {
    artifacts.push_back(
        {"sourceRemap",
         packageRelativePath(packageDir, *sourceRemapProvenancePath)});
  }
  appendManifestArtifact(artifacts, artifactValues,
                         nativeArtifactDescriptorArtifactKey);
  if (targetExplanationPath != nullptr) {
    artifacts.push_back(
        {"targetExplanation",
         packageRelativePath(packageDir, *targetExplanationPath)});
  }
  if (graphicsAbiPath != nullptr) {
    artifacts.push_back(
        {"graphicsAbi", packageRelativePath(packageDir, *graphicsAbiPath)});
  }

  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"compiler\": {\n"
      << "    \"name\": \"CrossGL-Compiler\",\n"
      << "    \"version\": \"" << CROSSGL_VERSION << "\",\n"
      << "    \"llvmVersion\": \"" << escapeJson(CROSSGL_LLVM_VERSION) << "\"\n"
      << "  },\n"
      << "  \"module\": \"" << escapeJson(module.name) << "\",\n"
      << "  \"target\": \"" << escapeJson(targetName(target)) << "\",\n"
      << "  \"sourceHash\": {\n"
      << "    \"algorithm\": \"sha256\",\n"
      << "    \"value\": \"" << escapeJson(sourceHash) << "\"\n"
      << "  },\n";
  appendPackageArtifactRequirementsJson(out, requirements);
  appendTargetLegalizationToolRequirementsJson(out, projection);
  out << "  \"artifacts\": {\n";
  for (std::size_t i = 0; i < artifacts.size(); ++i) {
    out << "    \"" << escapeJson(artifacts[i].name) << "\": \""
        << escapeJson(artifacts[i].value) << "\"";
    if (i + 1 != artifacts.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << "  }\n"
      << "}\n";
  return out.str();
}

std::string sourceRemapProvenanceJson(const SourceRemap &remap,
                                      TargetKind target) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"kind\": \"crossgl.sourceRemapProvenance\",\n"
      << "  \"contractVersion\": \"source-remap-provenance-v1\",\n"
      << "  \"target\": \"" << escapeJson(targetName(target)) << "\",\n"
      << "  \"generatedFile\": \"" << escapeJson(remap.generatedFile) << "\",\n"
      << "  \"mappingGranularity\": \"source-span\",\n"
      << "  \"mappingCount\": " << remap.mappings.size() << ",\n"
      << "  \"sourceRemap\": {\n"
      << "    \"path\": \"" << escapeJson(remap.documentPath.value_or(""))
      << "\",\n"
      << "    \"sha256\": {\n"
      << "      \"algorithm\": \"sha256\",\n"
      << "      \"value\": \"" << escapeJson(remap.documentSha256.value_or(""))
      << "\"\n"
      << "    },\n"
      << "    \"sizeBytes\": "
      << remap.documentSizeBytes.value_or(static_cast<std::uintmax_t>(0));
  if (remap.metadataTarget) {
    out << ",\n"
        << "    \"target\": \"" << escapeJson(*remap.metadataTarget) << "\"";
  }
  if (remap.metadataMappingGranularity) {
    out << ",\n"
        << "    \"mappingGranularity\": \""
        << escapeJson(*remap.metadataMappingGranularity) << "\"";
  }
  if (remap.metadataSourceBackend) {
    out << ",\n"
        << "    \"sourceBackend\": \""
        << escapeJson(*remap.metadataSourceBackend) << "\"";
  }
  if (remap.metadataVariant) {
    out << ",\n"
        << "    \"variant\": \"" << escapeJson(*remap.metadataVariant) << "\"";
  }
  out << "\n"
      << "  }\n"
      << "}\n";
  return out.str();
}

SourceRemap packageLocalBackendSourceMapRemap(
    const SourceRemap &remap, const std::filesystem::path &packageDir,
    const std::filesystem::path &sourceRemapProvenancePath) {
  SourceRemap packageLocalRemap = remap;
  packageLocalRemap.documentPath =
      packageRelativePath(packageDir, sourceRemapProvenancePath);
  return packageLocalRemap;
}

std::string
vulkanNativeProfileJson(const HIRModule &module,
                        const std::filesystem::path &packageDir,
                        const VulkanBuildResult &vulkanResult,
                        const TargetNativePackageDescriptorPolicy &policy) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"module\": \"" << escapeJson(module.name) << "\",\n"
      << "  \"target\": \"" << escapeJson(policy.targetName) << "\",\n"
      << "  \"api\": \"" << escapeJson(policy.profileApi) << "\",\n"
      << "  \"profile\": {\n"
      << "    \"name\": \"" << escapeJson(policy.profileName) << "\",\n"
      << "    \"vulkanVersion\": \"" << escapeJson(policy.vulkanVersion)
      << "\",\n"
      << "    \"spirvVersion\": \"" << escapeJson(policy.spirvVersion) << "\"\n"
      << "  },\n"
      << "  \"generator\": \"" << escapeJson(policy.generatorName) << "\",\n"
      << "  \"artifacts\": {\n"
      << "    \"" << escapeJson(policy.sourceArtifactKey) << "\": \""
      << escapeJson(packageRelativePath(packageDir, vulkanResult.assemblyPath))
      << "\",\n"
      << "    \"" << escapeJson(policy.nativeBinaryArtifactKey) << "\": \""
      << escapeJson(packageRelativePath(packageDir, vulkanResult.spvPath))
      << "\"\n"
      << "  },\n"
      << "  \"debug\": {\n"
      << "    \"binaryFormat\": \"" << escapeJson(policy.binaryFormat)
      << "\",\n"
      << "    \"assemblyFormat\": \"" << escapeJson(policy.assemblyFormat)
      << "\",\n"
      << "    \"validationTargetEnv\": \""
      << escapeJson(vulkanResult.validationTargetEnv) << "\",\n"
      << "    \"optimization\": {\n"
      << "      \"tool\": \"" << escapeJson(policy.optimizationToolName)
      << "\",\n"
      << "      \"policy\": \"" << escapeJson(vulkanResult.optimizationPolicy)
      << "\",\n"
      << "      \"requestedLevel\": \""
      << escapeJson(vulkanResult.optimizationRequestedLevel) << "\",\n"
      << "      \"level\": \"" << escapeJson(vulkanResult.optimizationLevel)
      << "\",\n"
      << "      \"status\": \"" << escapeJson(vulkanResult.optimizationStatus)
      << "\",\n"
      << "      \"targetEnv\": \""
      << escapeJson(vulkanResult.optimizationTargetEnv) << "\",\n"
      << "      \"toolStatus\": \""
      << escapeJson(vulkanResult.optimizationToolStatus) << "\"\n"
      << "    },\n"
      << "    \"disassembly\": {\n"
      << "      \"tool\": \"" << escapeJson(policy.disassemblyToolName)
      << "\",\n"
      << "      \"policy\": \"" << escapeJson(policy.disassemblyPolicy)
      << "\",\n"
      << "      \"status\": \"" << escapeJson(vulkanResult.disassemblyStatus)
      << "\",\n"
      << "      \"path\": ";
  if (vulkanResult.disassemblyPath.empty()) {
    out << "null\n";
  } else {
    out << "\""
        << escapeJson(
               packageRelativePath(packageDir, vulkanResult.disassemblyPath))
        << "\"\n";
  }
  out << "    }\n"
      << "  }\n"
      << "}\n";
  return out.str();
}

bool finalizePackageBuild(const std::filesystem::path &packageDir,
                          std::string_view manifest,
                          std::string_view reflection,
                          const std::filesystem::path &sourcePath,
                          DiagnosticEngine &diagnostics) {
  const bool wroteManifest = writeText(packageDir / "manifest.json", manifest,
                                       diagnostics, "artifact.write-manifest");
  const bool wroteReflection =
      writeText(packageDir / "reflection.json", reflection, diagnostics,
                "artifact.write-reflection");
  const bool wroteDiagnostics =
      writeText(packageDir / "diagnostics.json",
                diagnosticsToJson(diagnostics.diagnostics()), diagnostics,
                "artifact.write-diagnostics");
  if (!wroteManifest || !wroteReflection || !wroteDiagnostics) {
    return false;
  }

  PackageIntegrityResult verification = verifyPackage(packageDir, sourcePath);
  if (!verification.success) {
    for (Diagnostic diagnostic : verification.diagnostics) {
      diagnostics.report(std::move(diagnostic));
    }
    (void)writeText(packageDir / "diagnostics.json",
                    diagnosticsToJson(diagnostics.diagnostics()), diagnostics,
                    "artifact.write-diagnostics");
    return false;
  }

  return !diagnostics.hasErrors();
}

bool finalizeSourcePackageBuild(
    const HIRModule &module, TargetKind target, std::string_view sourceHash,
    const std::filesystem::path &packageDir,
    const TargetLegalizationContractProjection &projection,
    const SourcePackageArtifact &artifact, OptimizationLevel optimizationLevel,
    const DirectXSourcePackageResult *directxResult,
    std::string_view nativeToolName, const TargetLegalizationContract &contract,
    const std::optional<std::filesystem::path> &debugMetadataPath,
    const std::optional<std::filesystem::path> &hirSourceMapPath,
    const std::optional<std::filesystem::path> &backendSourceMapPath,
    const std::optional<std::filesystem::path> &sourceRemapProvenancePath,
    const std::optional<std::filesystem::path> &targetExplanationPath,
    const std::filesystem::path &inputPath,
    StagedPackageDirectory &stagedPackage, DiagnosticEngine &diagnostics,
    const std::vector<Diagnostic> *sourceValidationDiagnostics = nullptr) {
  if (!requireSourcePackageArtifactRequirements(artifact, projection,
                                                diagnostics)) {
    return false;
  }
  if (!projection.sourcePackageDescriptorPolicy.supported) {
    diagnostics.error("target.source-package-descriptor-policy",
                      "target legalization projection did not admit source "
                      "package descriptor policy for " +
                          std::string(targetName(target)));
    return false;
  }

  const TargetSourcePackageDescriptorPolicy descriptorPolicy =
      targetSourcePackageDescriptorPolicy(
          projection, artifact.nativeBinaryStatus, nativeToolName);
  if (!descriptorPolicy.supported) {
    diagnostics.error("target.source-package-descriptor-policy",
                      "target legalization projection did not admit source "
                      "package descriptor policy for nativeBinaryStatus '" +
                          artifact.nativeBinaryStatus + "'");
    return false;
  }
  NativeArtifactDescriptorSpec descriptorSpec = sourcePackageDescriptorSpec(
      artifact, descriptorPolicy, optimizationLevel);
  if (directxResult != nullptr) {
    descriptorSpec.optimizationEvidenceJson =
        sourcePackageDescriptorOptimizationEvidenceJson(descriptorPolicy,
                                                        *directxResult);
    if (directxResult->dxcProvenance) {
      applyInvocationProvenance(descriptorSpec.tools, "dxc", "compiler",
                                *directxResult->dxcProvenance, packageDir);
    }
  }
  if (target == TargetKind::OpenGL && sourceValidationDiagnostics != nullptr &&
      !sourceValidationDiagnostics->empty()) {
    const std::string validatorTool = nativeToolName.empty()
                                          ? "glslangValidator"
                                          : std::string(nativeToolName);
    descriptorSpec.validationStatus = "failed";
    descriptorSpec.tools = nativeDescriptorTools({nativeArtifactTool(
        validatorTool, "validator", validatorTool, validatorTool)});
    descriptorSpec.validationDiagnostics = *sourceValidationDiagnostics;
  }

  const std::optional<std::filesystem::path> descriptorPath =
      writeNativeArtifactDescriptor(module, target, packageDir, descriptorSpec,
                                    diagnostics);
  if (!descriptorPath) {
    return false;
  }

  const std::filesystem::path nativeBinaryPackagePath =
      packageRelativePath(packageDir, artifact.nativeBinary);
  const std::optional<ReflectionDocument> reflectionDocument =
      buildReflectionDocument(module, contract, nativeBinaryPackagePath,
                              diagnostics);
  if (!reflectionDocument) {
    return false;
  }
  const std::optional<std::filesystem::path> graphicsAbiSidecarPath =
      writeGraphicsAbiSidecar(module, target, packageDir, *reflectionDocument,
                              diagnostics);
  if (shouldEmitGraphicsAbi(module) && !graphicsAbiSidecarPath) {
    return false;
  }

  const std::string manifest = manifestJson(
      module, target, sourceHash, packageDir,
      projection.packageArtifactRequirements, projection, nullptr, nullptr,
      nullptr, &artifact, &descriptorPolicy, &*descriptorPath,
      debugMetadataPath ? &*debugMetadataPath : nullptr,
      hirSourceMapPath ? &*hirSourceMapPath : nullptr,
      backendSourceMapPath ? &*backendSourceMapPath : nullptr,
      sourceRemapProvenancePath ? &*sourceRemapProvenancePath : nullptr,
      targetExplanationPath ? &*targetExplanationPath : nullptr,
      graphicsAbiSidecarPath ? &*graphicsAbiSidecarPath : nullptr);
  const std::string reflection = reflectionJson(*reflectionDocument);
  return finalizePackageBuild(packageDir, manifest, reflection, inputPath,
                              diagnostics) &&
         stagedPackage.promote(diagnostics);
}

bool finalizeDirectXNativePackageBuild(
    const HIRModule &module, TargetKind target, std::string_view sourceHash,
    const std::filesystem::path &packageDir,
    const TargetLegalizationContractProjection &projection,
    const DirectXSourcePackageResult &directxResult,
    const TargetLegalizationContract &contract,
    const std::optional<std::filesystem::path> &debugMetadataPath,
    const std::optional<std::filesystem::path> &hirSourceMapPath,
    const std::optional<std::filesystem::path> &backendSourceMapPath,
    const std::optional<std::filesystem::path> &sourceRemapProvenancePath,
    const std::optional<std::filesystem::path> &targetExplanationPath,
    const std::filesystem::path &inputPath,
    StagedPackageDirectory &stagedPackage, DiagnosticEngine &diagnostics) {
  std::error_code artifactError;
  if (!directxResult.nativeBinaryProduced ||
      !std::filesystem::is_regular_file(directxResult.nativeBinaryPath,
                                        artifactError) ||
      artifactError) {
    diagnostics.error(
        "directx.native-artifact-missing",
        "DirectX native package emission requires a produced DXIL "
        "artifact");
    return false;
  }

  const TargetNativePackageDescriptorPolicy nativePackagePolicy =
      targetNativePackageDescriptorPolicy(projection);
  if (!nativePackagePolicy.supported) {
    diagnostics.error("target.native-package-descriptor-policy",
                      "target legalization projection did not admit native "
                      "package descriptor policy for directx");
    return false;
  }

  const std::optional<std::filesystem::path> descriptorPath =
      writeNativeArtifactDescriptor(
          module, target, packageDir,
          directxNativeDescriptorSpec(directxResult, nativePackagePolicy,
                                      packageDir),
          diagnostics);
  if (!descriptorPath) {
    return false;
  }

  const std::filesystem::path nativeBinaryPackagePath =
      packageRelativePath(packageDir, directxResult.nativeBinaryPath);
  const std::optional<ReflectionDocument> reflectionDocument =
      buildReflectionDocument(module, contract, nativeBinaryPackagePath,
                              diagnostics);
  if (!reflectionDocument) {
    return false;
  }
  const std::optional<std::filesystem::path> graphicsAbiSidecarPath =
      writeGraphicsAbiSidecar(module, target, packageDir, *reflectionDocument,
                              diagnostics);
  if (shouldEmitGraphicsAbi(module) && !graphicsAbiSidecarPath) {
    return false;
  }

  const std::string manifest = manifestJson(
      module, target, sourceHash, packageDir,
      projection.packageArtifactRequirements, projection, nullptr, nullptr,
      nullptr, nullptr, nullptr, &*descriptorPath,
      debugMetadataPath ? &*debugMetadataPath : nullptr,
      hirSourceMapPath ? &*hirSourceMapPath : nullptr,
      backendSourceMapPath ? &*backendSourceMapPath : nullptr,
      sourceRemapProvenancePath ? &*sourceRemapProvenancePath : nullptr,
      targetExplanationPath ? &*targetExplanationPath : nullptr,
      graphicsAbiSidecarPath ? &*graphicsAbiSidecarPath : nullptr,
      &nativePackagePolicy, &directxResult);
  const std::string reflection = reflectionJson(*reflectionDocument);
  return finalizePackageBuild(packageDir, manifest, reflection, inputPath,
                              diagnostics) &&
         stagedPackage.promote(diagnostics);
}

void appendUnique(std::vector<std::string> &values, const std::string &value) {
  if (value.empty()) {
    return;
  }
  for (const std::string &existing : values) {
    if (existing == value) {
      return;
    }
  }
  values.push_back(value);
}

std::string formatStringList(const std::vector<std::string> &values,
                             std::size_t limit) {
  std::ostringstream out;
  const std::size_t count = values.size() < limit ? values.size() : limit;
  for (std::size_t index = 0; index < count; ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << values[index];
  }
  if (values.size() > limit) {
    out << ", +" << (values.size() - limit) << " more";
  }
  return out.str();
}

std::vector<std::string> legalizationTraceEvidenceIds(
    const TargetLegalizationAdmissionDecision &decision) {
  const TargetLegalizationContractProjection &projection = decision.projection;
  std::vector<std::string> evidenceIds = projection.coreEvidenceIds;
  for (const std::string &evidenceId : projection.evidenceIds) {
    if (evidenceId.find(".capability.missing.") != std::string::npos ||
        evidenceId.find(".diagnostic.") != std::string::npos) {
      appendUnique(evidenceIds, evidenceId);
    }
  }
  return evidenceIds;
}

std::string targetLegalizationTraceMessage(
    const TargetLegalizationAdmissionDecision &decision) {
  const TargetLegalizationContractProjection &projection = decision.projection;
  std::string message =
      "; TargetLegalizationResult: state=" + projection.stateName +
      ", support=" + projection.supportStatusName +
      ", packageMode=" + projection.packageModeName +
      ", provenance=" + projection.packageDecisionProvenanceName;
  if (!projection.reason.empty()) {
    message += ", reason=" + projection.reason;
  }

  const std::vector<std::string> evidenceIds =
      legalizationTraceEvidenceIds(decision);
  if (!evidenceIds.empty()) {
    message += ", evidence=" + formatStringList(evidenceIds, 12);
  }
  return message;
}

void fillLegalizationDiagnosticFields(
    Diagnostic &diagnostic,
    const TargetLegalizationAdmissionDecision &decision) {
  const TargetLegalizationContractProjection &projection = decision.projection;
  if (diagnostic.target.empty()) {
    diagnostic.target = projection.targetProfile.resolvedTargetName;
  }
  if (diagnostic.missingCapabilities.empty()) {
    diagnostic.missingCapabilities = projection.missingCapabilityIds;
  }
}

std::vector<Diagnostic> diagnosticsWithLegalizationTrace(
    const std::vector<Diagnostic> &diagnostics,
    const TargetLegalizationAdmissionDecision &decision) {
  std::vector<Diagnostic> tracedDiagnostics = diagnostics;
  const std::string trace = targetLegalizationTraceMessage(decision);
  for (Diagnostic &diagnostic : tracedDiagnostics) {
    if (diagnostic.severity != DiagnosticSeverity::Error) {
      continue;
    }
    fillLegalizationDiagnosticFields(diagnostic, decision);
    if (diagnostic.message.find("TargetLegalizationResult:") ==
        std::string::npos) {
      diagnostic.message += trace;
    }
  }
  return tracedDiagnostics;
}

std::optional<HIRBackendInput>
requireNativeBackendInput(const CompilerModule &module,
                          DiagnosticEngine &diagnostics) {
  HIRBackendInput input = backendInputForCompilerModule(module);
  if (hirBackendInputIsValidated(input)) {
    return input;
  }

  diagnostics.error("target.backend-input-contract",
                    "native backend HIR input must satisfy " +
                        std::string(kHIRBackendInputContractId) + "/" +
                        std::string(kHIRBackendInputContractVersion) + " via " +
                        std::string(kHIRBackendInputValidationPassId) +
                        "; pipeline mode is '" +
                        input.descriptor.backendInputMode +
                        "' and validation state is '" +
                        std::string(hirBackendInputValidationStateName(
                            input.descriptor.validationState)) +
                        "'");
  return std::nullopt;
}

std::optional<BackendAdmission>
requireAdmittedBackendInput(const CompilerModule &module,
                            TargetKind requestedTarget,
                            DiagnosticEngine &diagnostics) {
  TargetLegalizationResult legalization =
      legalizeTarget(module.hir, requestedTarget);
  TargetLegalizationAdmissionDecision decision =
      targetLegalizationAdmissionDecision(legalization);
  if (!decision.admitted) {
    const std::vector<Diagnostic> legalizationDiagnostics =
        diagnosticsWithLegalizationTrace(
            targetLegalizationDiagnostics(decision.contract), decision);
    for (const Diagnostic &diagnostic : legalizationDiagnostics) {
      diagnostics.report(diagnostic);
    }
    return std::nullopt;
  }

  std::optional<HIRBackendInput> backendInput =
      requireNativeBackendInput(module, diagnostics);
  if (!backendInput) {
    return std::nullopt;
  }
  return BackendAdmission{std::move(legalization), std::move(decision),
                          std::move(*backendInput)};
}

bool requireSourcePackageAdmission(const BackendAdmission &admission,
                                   TargetKind target,
                                   DiagnosticEngine &diagnostics) {
  const TargetLegalizationContractProjection &projection =
      admission.decision.projection;
  if (admission.decision.admitted &&
      projection.targetProfile.resolvedTarget == target &&
      projection.supportStatus ==
          TargetLegalizationSupportStatus::SourcePackage &&
      projection.packageMode == TargetLegalizationPackageMode::SourcePackage) {
    return true;
  }

  const std::vector<Diagnostic> legalizationDiagnostics =
      diagnosticsWithLegalizationTrace(
          targetLegalizationDiagnostics(admission.decision.contract),
          admission.decision);
  if (!legalizationDiagnostics.empty()) {
    for (const Diagnostic &diagnostic : legalizationDiagnostics) {
      diagnostics.report(diagnostic);
    }
    return false;
  }

  diagnostics.error(
      "target.selected.unsupported",
      "target package admission contract did not select a source-package build "
      "path for " +
          targetName(target) +
          targetLegalizationTraceMessage(admission.decision));
  return false;
}

std::optional<std::string> dumpIRFromCompilerModule(
    CompilerModule &parsed, DumpStage stage, TargetKind target,
    DiagnosticEngine &diagnostics,
    const DebugMetadataHIRSourceMapFilter &sourceMapFilter,
    const DebugMetadataHIRSourceMapPagination &sourceMapPagination,
    const DebugMetadataHIRSourceMapOptions &sourceMapOptions) {
  switch (stage) {
  case DumpStage::HIR:
    return printHIR(parsed.hir);
  case DumpStage::CrossGL:
    return printCrossGLIR(parsed.hir);
  case DumpStage::PseudoMLIR:
    return printPseudoMLIR(parsed.hir);
  case DumpStage::Backend:
    if (std::optional<BackendAdmission> admission =
            requireAdmittedBackendInput(parsed, target, diagnostics)) {
      return printBackendIR(*admission->input.module,
                            admission->legalization.target);
    }
    return std::nullopt;
  case DumpStage::BackendSourceMap:
    if (target != TargetKind::DirectX && target != TargetKind::Metal &&
        target != TargetKind::OpenGL) {
      diagnostics.error("dump.backend-source-map.unsupported-target",
                        "backend source maps currently support directx, "
                        "metal, and opengl only");
      return std::nullopt;
    }
    if (std::optional<BackendAdmission> admission =
            requireAdmittedBackendInput(parsed, target, diagnostics)) {
      if (admission->legalization.target == TargetKind::Metal) {
        return generateMetalBackendSourceMapJson(
            *admission->input.module,
            sourceMapOptions.sourceRemap ? &*sourceMapOptions.sourceRemap
                                         : nullptr);
      }
      if (admission->legalization.target == TargetKind::OpenGL) {
        return generateOpenGLBackendSourceMapJson(
            *admission->input.module, admission->legalization.resourceBindings,
            sourceMapOptions.sourceRemap ? &*sourceMapOptions.sourceRemap
                                         : nullptr);
      }
      return generateDirectXBackendSourceMapJson(
          *admission->input.module, admission->legalization.resourceBindings,
          sourceMapOptions.sourceRemap ? &*sourceMapOptions.sourceRemap
                                       : nullptr);
    }
    return std::nullopt;
  case DumpStage::Debug: {
    DebugMetadataOptions debugMetadataOptions;
    debugMetadataOptions.sourceRemap = sourceMapOptions.sourceRemap;
    return debugMetadataJson(parsed.hir, target, std::nullopt,
                             debugMetadataOptions);
  }
  case DumpStage::HIRSourceMap:
    return hirSourceMapJson(parsed.hir, sourceMapFilter, sourceMapPagination,
                            sourceMapOptions);
  case DumpStage::HIRPassTrace:
    return hirPassTraceJson(parsed.optimization);
  }
  return std::nullopt;
}

} // namespace

CheckResult checkFile(const std::filesystem::path &inputPath) {
  DiagnosticEngine diagnostics;
  CompilerModuleOptions options;
  options.validateBackendInput = false;
  (void)loadCompilerModule(inputPath, diagnostics, options);
  CheckResult result;
  result.success = !diagnostics.hasErrors();
  result.diagnostics = diagnostics.diagnostics();
  return result;
}

CheckResult checkSource(const SourceInput &input) {
  DiagnosticEngine diagnostics;
  CompilerModuleOptions options;
  options.validateBackendInput = false;
  (void)loadCompilerModuleFromSource(input, diagnostics, options);
  CheckResult result;
  result.success = !diagnostics.hasErrors();
  result.diagnostics = diagnostics.diagnostics();
  return result;
}

std::optional<std::string> dumpIR(const std::filesystem::path &inputPath,
                                  DumpStage stage, TargetKind target,
                                  DiagnosticEngine &diagnostics) {
  return dumpIR(inputPath, stage, target, OptimizationLevel::O1, diagnostics);
}

std::optional<std::string> dumpIR(const SourceInput &input, DumpStage stage,
                                  TargetKind target,
                                  DiagnosticEngine &diagnostics) {
  return dumpIR(input, stage, target, OptimizationLevel::O1, diagnostics);
}

std::optional<std::string> dumpIR(const std::filesystem::path &inputPath,
                                  DumpStage stage, TargetKind target,
                                  OptimizationLevel optimizationLevel,
                                  DiagnosticEngine &diagnostics) {
  return dumpIR(inputPath, stage, target, optimizationLevel, diagnostics,
                DebugMetadataHIRSourceMapFilter{},
                DebugMetadataHIRSourceMapPagination{});
}

std::optional<std::string> dumpIR(const SourceInput &input, DumpStage stage,
                                  TargetKind target,
                                  OptimizationLevel optimizationLevel,
                                  DiagnosticEngine &diagnostics) {
  return dumpIR(input, stage, target, optimizationLevel, diagnostics,
                DebugMetadataHIRSourceMapFilter{},
                DebugMetadataHIRSourceMapPagination{},
                DebugMetadataHIRSourceMapOptions{});
}

std::optional<std::string>
dumpIR(const std::filesystem::path &inputPath, DumpStage stage,
       TargetKind target, DiagnosticEngine &diagnostics,
       const DebugMetadataHIRSourceMapFilter &sourceMapFilter) {
  return dumpIR(inputPath, stage, target, OptimizationLevel::O1, diagnostics,
                sourceMapFilter);
}

std::optional<std::string>
dumpIR(const std::filesystem::path &inputPath, DumpStage stage,
       TargetKind target, OptimizationLevel optimizationLevel,
       DiagnosticEngine &diagnostics,
       const DebugMetadataHIRSourceMapFilter &sourceMapFilter) {
  return dumpIR(inputPath, stage, target, optimizationLevel, diagnostics,
                sourceMapFilter, DebugMetadataHIRSourceMapPagination{});
}

std::optional<std::string>
dumpIR(const std::filesystem::path &inputPath, DumpStage stage,
       TargetKind target, DiagnosticEngine &diagnostics,
       const DebugMetadataHIRSourceMapFilter &sourceMapFilter,
       const DebugMetadataHIRSourceMapPagination &sourceMapPagination) {
  return dumpIR(inputPath, stage, target, OptimizationLevel::O1, diagnostics,
                sourceMapFilter, sourceMapPagination);
}

std::optional<std::string>
dumpIR(const std::filesystem::path &inputPath, DumpStage stage,
       TargetKind target, OptimizationLevel optimizationLevel,
       DiagnosticEngine &diagnostics,
       const DebugMetadataHIRSourceMapFilter &sourceMapFilter,
       const DebugMetadataHIRSourceMapPagination &sourceMapPagination) {
  return dumpIR(inputPath, stage, target, optimizationLevel, diagnostics,
                sourceMapFilter, sourceMapPagination,
                DebugMetadataHIRSourceMapOptions{});
}

std::optional<std::string>
dumpIR(const std::filesystem::path &inputPath, DumpStage stage,
       TargetKind target, OptimizationLevel optimizationLevel,
       DiagnosticEngine &diagnostics,
       const DebugMetadataHIRSourceMapFilter &sourceMapFilter,
       const DebugMetadataHIRSourceMapPagination &sourceMapPagination,
       const DebugMetadataHIRSourceMapOptions &sourceMapOptions) {
  CompilerModuleOptions options;
  options.optimizationLevel = optimizationLevel;
  options.validateBackendInput =
      stage == DumpStage::Backend || stage == DumpStage::BackendSourceMap ||
      stage == DumpStage::Debug;
  auto parsed = loadCompilerModule(inputPath, diagnostics, options);
  if (!parsed) {
    return std::nullopt;
  }

  return dumpIRFromCompilerModule(*parsed, stage, target, diagnostics,
                                  sourceMapFilter, sourceMapPagination,
                                  sourceMapOptions);
}

std::optional<std::string>
dumpIR(const SourceInput &input, DumpStage stage, TargetKind target,
       OptimizationLevel optimizationLevel, DiagnosticEngine &diagnostics,
       const DebugMetadataHIRSourceMapFilter &sourceMapFilter,
       const DebugMetadataHIRSourceMapPagination &sourceMapPagination,
       const DebugMetadataHIRSourceMapOptions &sourceMapOptions) {
  CompilerModuleOptions options;
  options.optimizationLevel = optimizationLevel;
  options.validateBackendInput =
      stage == DumpStage::Backend || stage == DumpStage::BackendSourceMap ||
      stage == DumpStage::Debug;
  auto parsed = loadCompilerModuleFromSource(input, diagnostics, options);
  if (!parsed) {
    return std::nullopt;
  }

  return dumpIRFromCompilerModule(*parsed, stage, target, diagnostics,
                                  sourceMapFilter, sourceMapPagination,
                                  sourceMapOptions);
}

std::optional<std::string>
explainTargets(const std::filesystem::path &inputPath,
               DiagnosticEngine &diagnostics) {
  auto parsed = loadCompilerModule(inputPath, diagnostics);
  if (!parsed) {
    return std::nullopt;
  }
  return targetExplanationJson(buildTargetExplanationDocument(parsed->hir));
}

std::optional<std::string> explainTargets(const SourceInput &input,
                                          DiagnosticEngine &diagnostics) {
  auto parsed = loadCompilerModuleFromSource(input, diagnostics);
  if (!parsed) {
    return std::nullopt;
  }
  return targetExplanationJson(buildTargetExplanationDocument(parsed->hir));
}

std::optional<std::string>
explainTargetsText(const std::filesystem::path &inputPath,
                   DiagnosticEngine &diagnostics) {
  auto parsed = loadCompilerModule(inputPath, diagnostics);
  if (!parsed) {
    return std::nullopt;
  }
  return targetExplanationText(buildTargetExplanationDocument(parsed->hir));
}

std::optional<std::string> explainTargetsText(const SourceInput &input,
                                              DiagnosticEngine &diagnostics) {
  auto parsed = loadCompilerModuleFromSource(input, diagnostics);
  if (!parsed) {
    return std::nullopt;
  }
  return targetExplanationText(buildTargetExplanationDocument(parsed->hir));
}

CompileResult compile(const CompileRequest &request) {
  DiagnosticEngine diagnostics;
  CompileResult result;
  const auto assignDiagnostics = [&]() {
    result.diagnostics = diagnostics.diagnostics();
    if (request.sourceRemap) {
      result.diagnostics = diagnosticsWithOriginalSourceLocations(
          result.diagnostics, *request.sourceRemap);
    }
  };

  TargetKind target = request.target == TargetKind::Auto
                          ? defaultTargetForHost()
                          : request.target;
  result.resolvedTarget = target;

  CompilerModuleOptions options;
  options.optimizationLevel = request.optimizationLevel;
  if (request.logicalInputPath) {
    options.logicalPath = *request.logicalInputPath;
  }
  const std::filesystem::path compilerInputPath =
      request.logicalInputPath.value_or(request.inputPath);
  if (request.sourceRemap &&
      !validateSourceRemapGeneratedFile(*request.sourceRemap, compilerInputPath,
                                        diagnostics)) {
    assignDiagnostics();
    return result;
  }
  auto parsed = loadCompilerModule(request.inputPath, diagnostics, options);
  if (!parsed) {
    assignDiagnostics();
    return result;
  }
  std::optional<BackendAdmission> admission =
      requireAdmittedBackendInput(*parsed, request.target, diagnostics);
  if (!admission) {
    assignDiagnostics();
    return result;
  }
  const TargetLegalizationResult &legalization = admission->legalization;
  target = legalization.target;
  result.resolvedTarget = target;
  const HIRModule &backendHIR = *admission->input.module;

  if (target == TargetKind::OpenGL &&
      !requireSourcePackageAdmission(*admission, target, diagnostics)) {
    assignDiagnostics();
    return result;
  }
  if ((target == TargetKind::DirectX || target == TargetKind::OpenGL) &&
      !samePackageArtifactRequirements(
          admission->decision.projection.packageArtifactRequirements,
          legalization.packageArtifactRequirements)) {
    diagnostics.error(
        "target.package-artifact-requirements.projection-mismatch",
        "target legalization projection packageArtifactRequirements diverged "
        "from the legalization result for " +
            std::string(targetName(target)));
    assignDiagnostics();
    return result;
  }

  StagedPackageDirectory stagedPackage(request.outputPath);
  if (!stagedPackage.create(diagnostics)) {
    assignDiagnostics();
    return result;
  }
  const std::filesystem::path &packageDir = stagedPackage.path();

  const std::string sourceHash = sha256(parsed->source);
  std::optional<std::filesystem::path> debugMetadataPath;
  std::optional<std::filesystem::path> hirSourceMapPath;
  std::optional<std::filesystem::path> backendSourceMapPath;
  std::optional<std::filesystem::path> sourceRemapProvenancePath;
  std::optional<std::filesystem::path> targetExplanationPath;
  DebugMetadataOptions debugMetadataOptions;
  DebugMetadataHIRSourceMapOptions sourceMapOptions;
  if (request.sourceRemap) {
    debugMetadataOptions.sourceRemap = request.sourceRemap;
    sourceMapOptions.sourceRemap = request.sourceRemap;
  }

  if (request.debugIR) {
    const auto irDir = packageDir / "ir";
    std::error_code error;
    std::filesystem::create_directories(irDir, error);
    if (error) {
      diagnostics.error("artifact.create-ir-directory",
                        "failed to create IR directory: " + error.message());
      assignDiagnostics();
      return result;
    }
    writeText(irDir / "hir.txt", printHIR(parsed->hir), diagnostics,
              "artifact.write-hir");
    writeText(irDir / "crossgl.mlir", printCrossGLIR(parsed->hir), diagnostics,
              "artifact.write-crossgl-ir");
    const std::string pseudoMLIR = printPseudoMLIR(parsed->hir);
    writeText(irDir / "pseudo-mlir.mlir", pseudoMLIR, diagnostics,
              "artifact.write-pseudo-mlir");
    writeText(irDir / "mlir.mlir", pseudoMLIR, diagnostics,
              "artifact.write-legacy-pseudo-mlir");
    debugMetadataPath = irDir / "debug-metadata.json";
    writeText(*debugMetadataPath,
              debugMetadataJson(parsed->hir, request.target, std::nullopt,
                                debugMetadataOptions),
              diagnostics, "artifact.write-debug-metadata");
    hirSourceMapPath = irDir / "hir-source-map.json";
    writeText(*hirSourceMapPath,
              hirSourceMapJson(parsed->hir, DebugMetadataHIRSourceMapFilter{},
                               DebugMetadataHIRSourceMapPagination{},
                               sourceMapOptions),
              diagnostics, "artifact.write-hir-source-map");
    targetExplanationPath = irDir / "target-explanation.json";
    writeText(
        *targetExplanationPath,
        targetExplanationJson(buildTargetExplanationDocument(parsed->hir)),
        diagnostics, "artifact.write-target-explanation");
    HIRPassTraceJsonOptions packageTraceOptions;
    packageTraceOptions.includeElapsedTimeMicroseconds = false;
    writeText(irDir / "hir-pass-trace.json",
              hirPassTraceJson(parsed->optimization, packageTraceOptions),
              diagnostics, "artifact.write-hir-pass-trace");
    if (request.sourceRemap && request.sourceRemap->documentPath &&
        request.sourceRemap->documentSha256 &&
        request.sourceRemap->documentSizeBytes) {
      sourceRemapProvenancePath = irDir / "source-remap-provenance.json";
      writeText(*sourceRemapProvenancePath,
                sourceRemapProvenanceJson(*request.sourceRemap, target),
                diagnostics, "artifact.write-source-remap-provenance");
    }
  }

  if (target == TargetKind::Metal) {
    MetalBuildResult metal = buildMetalBinary(
        backendHIR, packageDir, diagnostics, legalization.resourceBindings,
        request.optimizationLevel);
    if (metal.success) {
      const TargetLegalizationContractProjection &projection =
          admission->decision.projection;
      const TargetNativePackageDescriptorPolicy nativePackagePolicy =
          targetNativePackageDescriptorPolicy(projection);
      if (!nativePackagePolicy.supported) {
        diagnostics.error("target.native-package-descriptor-policy",
                          "target legalization projection did not admit native "
                          "package descriptor policy for metal");
        assignDiagnostics();
        return result;
      }
      NativeArtifactDescriptorSpec descriptorSpec;
      descriptorSpec.binaryKind = nativePackagePolicy.binaryKind;
      descriptorSpec.sourcePath = metal.sourcePath;
      descriptorSpec.artifactPath = metal.metallibPath;
      descriptorSpec.validationStatus = nativePackagePolicy.validationStatus;
      descriptorSpec.optimizationLevel =
          nativeDescriptorOptimizationLevel(request.optimizationLevel);
      descriptorSpec.optimizationEvidenceJson = nativeOptimizationEvidenceJson(
          metalNativeOptimizationEvidence(metal, nativePackagePolicy));
      descriptorSpec.tools =
          nativeDescriptorTools(nativePackagePolicy.requiredTools);
      if (metal.metalCompilerProvenance) {
        applyInvocationProvenance(descriptorSpec.tools, "xcrun metal",
                                  "compiler",
                                  *metal.metalCompilerProvenance, packageDir);
      }
      if (metal.metallibProvenance) {
        applyInvocationProvenance(descriptorSpec.tools, "xcrun metallib",
                                  "linker", *metal.metallibProvenance,
                                  packageDir);
      }
      const std::optional<std::filesystem::path> descriptorPath =
          writeNativeArtifactDescriptor(backendHIR, target, packageDir,
                                        descriptorSpec, diagnostics);
      if (!descriptorPath) {
        assignDiagnostics();
        return result;
      }
      const std::filesystem::path nativeBinaryPackagePath =
          packageRelativePath(packageDir, metal.metallibPath);
      const std::optional<ReflectionDocument> reflectionDocument =
          buildReflectionDocument(backendHIR, admission->decision.contract,
                                  nativeBinaryPackagePath, diagnostics);
      if (!reflectionDocument) {
        assignDiagnostics();
        return result;
      }
      const std::optional<std::filesystem::path> graphicsAbiSidecarPath =
          writeGraphicsAbiSidecar(backendHIR, target, packageDir,
                                  *reflectionDocument, diagnostics);
      if (shouldEmitGraphicsAbi(backendHIR) && !graphicsAbiSidecarPath) {
        assignDiagnostics();
        return result;
      }
      if (request.debugIR) {
        backendSourceMapPath =
            metal.sourcePath.parent_path() /
            (backendHIR.name + ".backend-source-map.json");
        const SourceRemap *backendSourceMapRemap =
            sourceMapOptions.sourceRemap ? &*sourceMapOptions.sourceRemap
                                         : nullptr;
        std::optional<SourceRemap> packageLocalSourceRemap;
        if (sourceMapOptions.sourceRemap && sourceRemapProvenancePath) {
          packageLocalSourceRemap = packageLocalBackendSourceMapRemap(
              *sourceMapOptions.sourceRemap, packageDir,
              *sourceRemapProvenancePath);
          backendSourceMapRemap = &*packageLocalSourceRemap;
        }
        if (!writeText(*backendSourceMapPath,
                       generateMetalBackendSourceMapJson(
                           backendHIR, backendSourceMapRemap),
                       diagnostics, "artifact.write-backend-source-map")) {
          assignDiagnostics();
          return result;
        }
      }
      const std::string manifest = manifestJson(
          backendHIR, target, sourceHash, packageDir,
          projection.packageArtifactRequirements, projection, &metal, nullptr,
          nullptr, nullptr, nullptr, &*descriptorPath,
          debugMetadataPath ? &*debugMetadataPath : nullptr,
          hirSourceMapPath ? &*hirSourceMapPath : nullptr,
          backendSourceMapPath ? &*backendSourceMapPath : nullptr,
          sourceRemapProvenancePath ? &*sourceRemapProvenancePath : nullptr,
          targetExplanationPath ? &*targetExplanationPath : nullptr,
          graphicsAbiSidecarPath ? &*graphicsAbiSidecarPath : nullptr,
          &nativePackagePolicy);
      const std::string reflection = reflectionJson(*reflectionDocument);
      if (finalizePackageBuild(packageDir, manifest, reflection,
                               request.inputPath, diagnostics) &&
          stagedPackage.promote(diagnostics)) {
        result.artifactPath = request.outputPath;
        result.success = true;
      }
    }
  }

  if (target == TargetKind::Vulkan) {
    VulkanBuildResult vulkan = buildVulkanPrototypeBinary(
        backendHIR, packageDir, diagnostics, legalization.resourceBindings,
        request.optimizationLevel);
    if (vulkan.success) {
      const TargetLegalizationContractProjection &projection =
          admission->decision.projection;
      const TargetNativePackageDescriptorPolicy nativePackagePolicy =
          targetNativePackageDescriptorPolicy(projection);
      if (!nativePackagePolicy.supported) {
        diagnostics.error("target.native-package-descriptor-policy",
                          "target legalization projection did not admit native "
                          "package descriptor policy for vulkan");
        assignDiagnostics();
        return result;
      }
      const std::filesystem::path vulkanProfilePath =
          vulkan.spvPath.parent_path() / (backendHIR.name + ".profile.json");
      if (!writeText(vulkanProfilePath,
                     vulkanNativeProfileJson(backendHIR, packageDir, vulkan,
                                             nativePackagePolicy),
                     diagnostics, "artifact.write-vulkan-native-profile")) {
        assignDiagnostics();
        return result;
      }
      NativeArtifactDescriptorSpec descriptorSpec;
      descriptorSpec.binaryKind = nativePackagePolicy.binaryKind;
      descriptorSpec.sourcePath = vulkan.assemblyPath;
      descriptorSpec.artifactPath = vulkan.spvPath;
      descriptorSpec.validationStatus = nativePackagePolicy.validationStatus;
      descriptorSpec.optimizationLevel = vulkan.optimizationRequestedLevel;
      NativeOptimizationEvidenceSpec optimizationEvidence;
      optimizationEvidence.requestedLevel = vulkan.optimizationRequestedLevel;
      optimizationEvidence.effectiveLevel =
          vulkanNativeOptimizationEffectiveLevel(vulkan);
      optimizationEvidence.policy = vulkan.optimizationPolicy;
      optimizationEvidence.status = vulkan.optimizationStatus;
      optimizationEvidence.tool = nativePackagePolicy.optimizationToolName;
      if (vulkan.optimizationLevel != "none") {
        optimizationEvidence.toolFlag = vulkan.optimizationLevel;
      }
      optimizationEvidence.evidenceSourceKind = "native-profile";
      optimizationEvidence.evidenceSourcePath =
          packageRelativePath(packageDir, vulkanProfilePath);
      descriptorSpec.optimizationEvidenceJson =
          nativeOptimizationEvidenceJson(optimizationEvidence);
      descriptorSpec.tools =
          nativeDescriptorTools(nativePackagePolicy.requiredTools);
      if (vulkan.assemblerProvenance) {
        applyInvocationProvenance(descriptorSpec.tools, "spirv-as",
                                  "assembler",
                                  *vulkan.assemblerProvenance, packageDir);
      }
      if (vulkan.validatorProvenance) {
        applyInvocationProvenance(descriptorSpec.tools, "spirv-val",
                                  "validator",
                                  *vulkan.validatorProvenance, packageDir);
      }
      descriptorSpec.spirvExtendedInstructionImports =
          vulkan.extendedInstructionImports;
      const std::optional<std::filesystem::path> descriptorPath =
          writeNativeArtifactDescriptor(backendHIR, target, packageDir,
                                        descriptorSpec, diagnostics);
      if (!descriptorPath) {
        assignDiagnostics();
        return result;
      }
      const std::filesystem::path nativeBinaryPackagePath =
          packageRelativePath(packageDir, vulkan.spvPath);
      const std::optional<ReflectionDocument> reflectionDocument =
          buildReflectionDocument(backendHIR, admission->decision.contract,
                                  nativeBinaryPackagePath, diagnostics);
      if (!reflectionDocument) {
        assignDiagnostics();
        return result;
      }
      const std::optional<std::filesystem::path> graphicsAbiSidecarPath =
          writeGraphicsAbiSidecar(backendHIR, target, packageDir,
                                  *reflectionDocument, diagnostics);
      if (shouldEmitGraphicsAbi(backendHIR) && !graphicsAbiSidecarPath) {
        assignDiagnostics();
        return result;
      }
      const std::string manifest = manifestJson(
          backendHIR, target, sourceHash, packageDir,
          projection.packageArtifactRequirements, projection, nullptr, &vulkan,
          &vulkanProfilePath, nullptr, nullptr, &*descriptorPath,
          debugMetadataPath ? &*debugMetadataPath : nullptr,
          hirSourceMapPath ? &*hirSourceMapPath : nullptr,
          nullptr,
          sourceRemapProvenancePath ? &*sourceRemapProvenancePath : nullptr,
          targetExplanationPath ? &*targetExplanationPath : nullptr,
          graphicsAbiSidecarPath ? &*graphicsAbiSidecarPath : nullptr,
          &nativePackagePolicy);
      const std::string reflection = reflectionJson(*reflectionDocument);
      if (finalizePackageBuild(packageDir, manifest, reflection,
                               request.inputPath, diagnostics) &&
          stagedPackage.promote(diagnostics)) {
        result.artifactPath = request.outputPath;
        result.success = true;
      }
    }
  }

  if (target == TargetKind::DirectX) {
    DirectXSourcePackageResult directx = buildDirectXSourcePackage(
        backendHIR, packageDir, diagnostics, legalization.resourceBindings,
        request.optimizationLevel);
    if (directx.success) {
      std::error_code directxNativeArtifactError;
      const bool directxNativeArtifactAvailable =
          directx.nativeBinaryProduced &&
          std::filesystem::is_regular_file(directx.nativeBinaryPath,
                                           directxNativeArtifactError) &&
          !directxNativeArtifactError;
      const TargetLegalizationContractProjection directxProjection =
          directxNativeArtifactAvailable
              ? targetLegalizationDirectXNativePromotionProjection(backendHIR,
                                                                   target)
              : targetLegalizationSourcePackageFallbackProjection(backendHIR,
                                                                  target);
      const bool shouldRewriteDirectXSidecars =
          directxNativeArtifactAvailable ||
          admission->decision.projection.packageModeName == "native";
      if (shouldRewriteDirectXSidecars &&
          !rewriteDirectXTargetLegalizationSidecars(
              backendHIR, request.target, directxProjection, debugMetadataOptions,
              debugMetadataPath, targetExplanationPath, diagnostics,
              directxNativeArtifactAvailable)) {
        assignDiagnostics();
        return result;
      }

      const SourcePackageArtifact directxArtifact{
          directx.sourcePath, directx.nativeBinaryPath,
          directx.nativeBinaryStatus};
      if (request.debugIR) {
        backendSourceMapPath =
            directx.sourcePath.parent_path() /
            (backendHIR.name + ".backend-source-map.json");
        const SourceRemap *backendSourceMapRemap =
            sourceMapOptions.sourceRemap ? &*sourceMapOptions.sourceRemap
                                         : nullptr;
        std::optional<SourceRemap> packageLocalSourceRemap;
        if (sourceMapOptions.sourceRemap && sourceRemapProvenancePath) {
          packageLocalSourceRemap = packageLocalBackendSourceMapRemap(
              *sourceMapOptions.sourceRemap, packageDir,
              *sourceRemapProvenancePath);
          backendSourceMapRemap = &*packageLocalSourceRemap;
        }
        if (!writeText(*backendSourceMapPath,
                       generateDirectXBackendSourceMapJson(
                           backendHIR, legalization.resourceBindings,
                           backendSourceMapRemap),
                       diagnostics, "artifact.write-backend-source-map")) {
          assignDiagnostics();
          return result;
        }
      }
      const bool finalized =
          directxProjection.packageMode == TargetLegalizationPackageMode::Native
              ? finalizeDirectXNativePackageBuild(
                    backendHIR, target, sourceHash, packageDir,
                    directxProjection, directx, admission->decision.contract,
                    debugMetadataPath, hirSourceMapPath, backendSourceMapPath,
                    sourceRemapProvenancePath, targetExplanationPath,
                    request.inputPath, stagedPackage, diagnostics)
              : finalizeSourcePackageBuild(
                    backendHIR, target, sourceHash, packageDir,
                    directxProjection, directxArtifact, request.optimizationLevel,
                    &directx, "", admission->decision.contract, debugMetadataPath,
                    hirSourceMapPath, backendSourceMapPath, sourceRemapProvenancePath,
                    targetExplanationPath, request.inputPath, stagedPackage,
                    diagnostics);
      if (finalized) {
        result.artifactPath = request.outputPath;
        result.success = true;
      } else {
        assignDiagnostics();
        return result;
      }
    }
  }

  if (target == TargetKind::OpenGL) {
    OpenGLSourcePackageResult opengl = buildOpenGLSourcePackage(
        backendHIR, packageDir, diagnostics, legalization.resourceBindings);
    if (opengl.success) {
      const bool openglComputeSource =
          singleComputeStage(backendHIR) != nullptr;
      if (debugMetadataPath) {
        writeText(*debugMetadataPath,
                  debugMetadataJson(backendHIR, request.target,
                                    debugValidationFromOpenGLResult(opengl),
                                    debugMetadataOptions),
                  diagnostics, "artifact.write-debug-metadata");
      }
      if (hirSourceMapPath) {
        writeText(*hirSourceMapPath,
                  hirSourceMapJson(
                      backendHIR, DebugMetadataHIRSourceMapFilter{},
                      DebugMetadataHIRSourceMapPagination{}, sourceMapOptions),
                  diagnostics, "artifact.write-hir-source-map");
      }
      if (request.debugIR && openglComputeSource) {
        backendSourceMapPath =
            opengl.sourcePath.parent_path() /
            (backendHIR.name + ".backend-source-map.json");
        const SourceRemap *backendSourceMapRemap =
            sourceMapOptions.sourceRemap ? &*sourceMapOptions.sourceRemap
                                         : nullptr;
        std::optional<SourceRemap> packageLocalSourceRemap;
        if (sourceMapOptions.sourceRemap && sourceRemapProvenancePath) {
          packageLocalSourceRemap = packageLocalBackendSourceMapRemap(
              *sourceMapOptions.sourceRemap, packageDir,
              *sourceRemapProvenancePath);
          backendSourceMapRemap = &*packageLocalSourceRemap;
        }
        if (!writeText(*backendSourceMapPath,
                       generateOpenGLBackendSourceMapJson(
                           backendHIR, legalization.resourceBindings,
                           backendSourceMapRemap),
                       diagnostics, "artifact.write-backend-source-map")) {
          assignDiagnostics();
          return result;
        }
      }
      const SourcePackageArtifact artifact{opengl.sourcePath,
                                           opengl.nativeBinaryPath,
                                           opengl.nativeBinaryStatus};
      if (finalizeSourcePackageBuild(
              backendHIR, target, sourceHash, packageDir,
              admission->decision.projection, artifact,
              request.optimizationLevel, nullptr, opengl.validatorTool,
              admission->decision.contract, debugMetadataPath, hirSourceMapPath,
              backendSourceMapPath, sourceRemapProvenancePath,
              targetExplanationPath, request.inputPath, stagedPackage,
              diagnostics,
              &opengl.validationDiagnostics)) {
        result.artifactPath = request.outputPath;
        result.success = true;
      } else {
        assignDiagnostics();
        return result;
      }
    }
  }

  assignDiagnostics();
  return result;
}

} // namespace crossgl
