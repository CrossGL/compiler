#pragma once

#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "crossgl/Basic/Diagnostic.h"

namespace crossgl {

struct PackageRootFileRecord {
  std::string name;
  std::string path;
  SourceLocation location;
  bool pathExists = false;
  bool exists = false;
  std::optional<std::uintmax_t> sizeBytes;
};

enum class PackagePathIssue {
  None,
  Empty,
  BackslashSeparator,
  Absolute,
  ParentTraversal,
};

struct PackageArtifactRecord {
  std::string name;
  std::string path;
  std::optional<SourceLocation> location;
  PackagePathIssue pathIssue = PackagePathIssue::None;
  bool packageRelative = false;
  bool pathExists = false;
  bool exists = false;
  std::optional<std::uintmax_t> sizeBytes;
};

struct PackageRequiredPathArtifactRecord {
  std::string name;
  std::optional<SourceLocation> location;
};

struct PackageArtifactRequirementsRecord {
  SourceLocation location;
  std::string target;
  std::string packageMode;
  std::optional<SourceLocation> targetLocation;
  std::optional<SourceLocation> packageModeLocation;
  std::optional<SourceLocation> requiredPathArtifactsLocation;
  std::optional<SourceLocation> evidenceIdsLocation;
  std::vector<PackageRequiredPathArtifactRecord> requiredPathArtifacts;
  std::vector<std::string> evidenceIds;
  bool requiresNativeBinaryStatus = false;
  bool allowsPlannedNativeBinary = false;
  bool allowsPlannedNativeSourceEvidence = false;
};

struct PackageTargetLegalizationToolRequirementsRecord {
  SourceLocation location;
  std::string target;
  std::string packageMode;
  std::optional<SourceLocation> targetLocation;
  std::optional<SourceLocation> packageModeLocation;
  std::optional<SourceLocation> requiredToolIdsLocation;
  std::optional<SourceLocation> missingToolIdsLocation;
  std::optional<SourceLocation> toolRequirementEvidenceIdsLocation;
  std::uintmax_t requiredToolCount = 0;
  std::uintmax_t missingToolCount = 0;
  std::vector<std::string> requiredToolIds;
  std::vector<std::string> missingToolIds;
  bool optionalNativeToolMissing = false;
  std::string optionalNativeToolStatus;
  std::vector<std::string> toolRequirementEvidenceIds;
};

struct PackageNativeArtifactDescriptorChecks {
  std::optional<bool> descriptorIdentityMatchesContract;
  std::optional<bool> targetMatchesPackage;
  std::optional<bool> nativeBinaryStatusMatchesPackage;
  std::optional<bool> sourcePathMatchesManifest;
  std::optional<bool> sourceHashMatchesFile;
  std::optional<bool> artifactPathMatchesManifest;
  std::optional<bool> artifactHashMatchesFile;
  std::optional<bool> sizeBytesMatchesFile;
  std::optional<bool> validationStatusMatchesNativeStatus;
};

struct PackageNativeArtifactDescriptorHealth {
  bool artifactPresent = false;
  bool descriptorExists = false;
  std::string health = "not-present";
  std::optional<std::string> path;
  std::optional<std::uintmax_t> schemaVersion;
  std::optional<std::string> kind;
  std::optional<std::string> contractVersion;
  std::optional<std::string> target;
  std::optional<std::string> binaryKind;
  std::optional<std::string> sourcePath;
  std::optional<std::string> sourceHash;
  std::optional<std::string> artifactPath;
  std::optional<std::string> artifactHash;
  std::optional<std::uintmax_t> sizeBytes;
  std::optional<std::string> optimizationLevel;
  std::optional<std::string> optimizationEvidence;
  std::optional<std::string> validationStatus;
  std::optional<std::string> nativeBinaryStatus;
  PackageNativeArtifactDescriptorChecks checks;
};

struct PackageGraphicsAbiDiagnostic {
  std::string code;
  std::string message;
};

struct PackageGraphicsAbiSummary {
  std::string module;
  std::string target;
  std::uintmax_t entryPointCount = 0;
  std::uintmax_t vertexInputCount = 0;
  std::uintmax_t varyingCount = 0;
  std::uintmax_t fragmentOutputCount = 0;
  std::uintmax_t builtinCount = 0;
  std::uintmax_t resourceCount = 0;
  std::uintmax_t abiRecordCount = 0;
};

struct PackageGraphicsAbiHealth {
  bool artifactPresent = false;
  bool exists = false;
  std::string health = "not-present";
  std::optional<std::string> path;
  std::optional<std::uintmax_t> schemaVersion;
  std::optional<PackageGraphicsAbiSummary> summary;
  std::vector<PackageGraphicsAbiDiagnostic> diagnostics;
};

struct PackageDocuments {
  std::string manifest;
  std::string reflection;
  std::string diagnostics;
};

struct PackageReflectionResourceRecord {
  SourceLocation location;
  std::string stage;
  std::string name;
  std::string kind;
  std::string type;
  std::optional<std::uintmax_t> set;
  std::optional<std::uintmax_t> binding;
  std::optional<std::string> addressSpace;
  std::optional<std::string> storageImageFormat;
  std::string arrayDimensionsJson = "[]";
};

struct PackageReflectionTargetResourceBindingRecord {
  SourceLocation location;
  std::string target;
  std::string stage;
  std::string entryPoint;
  std::string name;
  std::string kind;
  std::string sourceType;
  std::optional<std::uintmax_t> set;
  std::optional<std::uintmax_t> binding;
  std::optional<std::string> addressSpace;
  std::optional<std::string> storageImageFormat;
  std::string arrayDimensionsJson = "[]";
};

struct PackageMetadata {
  std::filesystem::path packagePath;
  PackageDocuments documents;
  SourceLocation manifestLocation;
  SourceLocation reflectionLocation;
  SourceLocation diagnosticsLocation;
  std::optional<SourceLocation> artifactsLocation;
  std::vector<PackageRootFileRecord> rootFiles;
  std::vector<PackageArtifactRecord> artifacts;
  std::vector<PackageReflectionResourceRecord> reflectionResources;
  std::vector<PackageReflectionTargetResourceBindingRecord>
      reflectionTargetResourceBindings;
  std::optional<PackageArtifactRequirementsRecord> artifactRequirements;
  std::optional<PackageTargetLegalizationToolRequirementsRecord>
      targetLegalizationToolRequirements;
  std::string module;
  std::string target;
  std::optional<std::string> sourceHashAlgorithm;
  std::optional<std::string> sourceHashValue;
  std::optional<std::string> nativeBinaryStatus;
  std::optional<std::string> reflectionNativeBinary;
  std::optional<SourceLocation> sourceHashLocation;
  std::optional<SourceLocation> sourceHashAlgorithmLocation;
  std::optional<SourceLocation> sourceHashValueLocation;
  std::optional<SourceLocation> nativeBinaryStatusLocation;
  std::optional<SourceLocation> reflectionNativeBinaryLocation;
  bool debugMetadataArtifactPresent = false;
  bool hirSourceMapArtifactPresent = false;
  bool debugArtifactsPresent = false;
  bool sourceRemapArtifactPresent = false;
  bool nativeProfileArtifactPresent = false;
  bool nativeArtifactDescriptorArtifactPresent = false;
};

struct PackageMetadataLoadOptions {
  std::string diagnosticCodePrefix = "package.metadata";
  std::string commandName = "package metadata";
};

PackagePathIssue packagePathIssue(std::string_view path);
bool isPackageRelativePath(std::string_view path);
bool isKnownPackageTargetName(std::string_view target);
bool isKnownPackageNativeBinaryStatus(std::string_view status);
bool packageNativeBinaryStatusMatchesRequirements(
    const PackageArtifactRequirementsRecord &requirements,
    const std::optional<std::string> &nativeBinaryStatus);
std::optional<std::string>
effectivePackageNativeBinaryStatus(const PackageMetadata &metadata);

PackageNativeArtifactDescriptorHealth
collectPackageNativeArtifactDescriptorHealth(const PackageMetadata &metadata);
PackageGraphicsAbiHealth
collectPackageGraphicsAbiHealth(const PackageMetadata &metadata);

std::optional<PackageMetadata>
loadPackageMetadata(const std::filesystem::path &packagePath,
                    DiagnosticEngine &diagnostics,
                    const PackageMetadataLoadOptions &options = {});

} // namespace crossgl
