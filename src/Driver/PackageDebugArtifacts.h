#pragma once

#include "crossgl/Driver/PackageMetadata.h"

#include <cstdint>
#include <optional>
#include <string>

namespace crossgl {

struct PackageSourceRemapProvenanceChecks {
  std::optional<bool> identityMatchesContract;
  std::optional<bool> targetMatchesPackage;
  std::optional<bool> generatedFilePresent;
  std::optional<bool> mappingCountPositive;
  std::optional<bool> sourcePathPresent;
  std::optional<bool> sourceHashPresent;
  std::optional<bool> sourceSizeBytesPresent;
};

struct PackageSourceRemapProvenanceHealth {
  bool artifactPresent = false;
  bool exists = false;
  std::string health = "not-present";
  std::optional<std::string> path;
  std::optional<std::uintmax_t> schemaVersion;
  std::optional<std::string> kind;
  std::optional<std::string> contractVersion;
  std::optional<std::string> target;
  std::optional<std::string> generatedFile;
  std::optional<std::string> mappingGranularity;
  std::optional<std::uintmax_t> mappingCount;
  std::optional<std::string> sourcePath;
  std::optional<std::string> sourceSha256;
  std::optional<std::uintmax_t> sourceSizeBytes;
  PackageSourceRemapProvenanceChecks checks;
};

struct PackageDebugArtifactHealth {
  bool debugMetadataArtifactPresent = false;
  bool hirSourceMapArtifactPresent = false;
  bool debugMetadataExists = false;
  bool hirSourceMapExists = false;
  std::string health = "incomplete";
  PackageSourceRemapProvenanceHealth sourceRemap;
  std::optional<bool> hirSourceLocationsMatch;
  std::optional<bool> sourceMapUnfiltered;
  std::optional<bool> sourceMapUnpaged;
  std::optional<bool> sourceMapRecordsDisabled;
  std::optional<bool> sourceMapCategoryCountsConsistent;
  std::optional<bool> recordsTotalCountMatchesCategoryCounts;
};

struct PackageVulkanNativeProfileHealth {
  bool applicable = false;
  bool nativeProfileArtifactPresent = false;
  bool nativeProfileExists = false;
  std::string health = "not-applicable";
  std::optional<std::uintmax_t> schemaVersion;
  std::optional<std::string> api;
  std::optional<std::string> profileName;
  std::optional<std::string> vulkanVersion;
  std::optional<std::string> spirvVersion;
  std::optional<std::string> generator;
  std::optional<std::string> nativeBinary;
  std::optional<std::string> backendAssembly;
  std::optional<std::string> disassemblyStatus;
  std::optional<std::string> disassemblyPath;
  std::optional<bool> disassemblyExists;
  std::optional<bool> targetMatchesPackage;
  std::optional<bool> moduleMatchesPackage;
  std::optional<bool> nativeBinaryMatchesManifest;
  std::optional<bool> backendAssemblyMatchesManifest;
  std::optional<bool> emittedDisassemblyExists;
  std::optional<bool> spirvProfilePresent;
};

PackageDebugArtifactHealth
collectPackageDebugArtifactHealth(const PackageMetadata &metadata);

PackageVulkanNativeProfileHealth
collectPackageVulkanNativeProfileHealth(const PackageMetadata &metadata);

} // namespace crossgl
