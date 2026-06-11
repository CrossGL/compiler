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
  std::optional<bool> mappingGranularityMatchesContract;
  std::optional<bool> mappingCountPositive;
  std::optional<bool> sourcePathPresent;
  std::optional<bool> sourceHashPresent;
  std::optional<bool> sourceSizeBytesPresent;
  std::optional<bool> sourceRemapTargetMatchesContract;
  std::optional<bool> sourceRemapMappingGranularityMatchesContract;
  std::optional<bool> sourceRemapSourceBackendValid;
  std::optional<bool> sourceRemapVariantValid;
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
  std::optional<std::string> sourceRemapTarget;
  std::optional<std::string> sourceRemapMappingGranularity;
  std::optional<std::string> sourceRemapSourceBackend;
  std::optional<std::string> sourceRemapVariant;
  PackageSourceRemapProvenanceChecks checks;
};

struct PackageBackendSourceMapChecks {
  std::optional<bool> identityMatchesContract;
  std::optional<bool> targetMatchesPackage;
  std::optional<bool> moduleMatchesPackage;
  std::optional<bool> mappingGranularityMatchesContract;
  std::optional<bool> sourceBackendPresent;
  std::optional<bool> targetBackendMatchesBackendLanguage;
  std::optional<bool> backendLanguagePresent;
  std::optional<bool> backendLineCountPresent;
  std::optional<bool> backendLineCountMatchesSource;
  std::optional<bool> backendSpansWithinSource;
  std::optional<bool> mappingCountMatchesMappings;
  std::optional<bool> sourceRemapPathPackageRelative;
  std::optional<bool> sourceRemapGeneratedFilePackageRelative;
  std::optional<bool> sourceRemapHashPresent;
  std::optional<bool> sourceRemapMappingCountPositive;
  std::optional<bool> sourceRemapTargetMatchesContract;
  std::optional<bool> sourceRemapMappingGranularityMatchesContract;
  std::optional<bool> sourceRemapSourceBackendValid;
  std::optional<bool> sourceRemapVariantValid;
  std::optional<bool> sourceRemapMatchesProvenance;
};

struct PackageBackendSourceMapHealth {
  bool artifactPresent = false;
  bool exists = false;
  std::string health = "not-present";
  std::optional<std::string> path;
  std::optional<std::uintmax_t> schemaVersion;
  std::optional<std::string> kind;
  std::optional<std::string> target;
  std::optional<std::string> module;
  std::optional<std::string> mappingGranularity;
  std::optional<std::string> sourceBackend;
  std::optional<std::string> targetBackend;
  std::optional<std::string> backendLanguage;
  std::optional<std::uintmax_t> backendLineCount;
  std::optional<std::uintmax_t> backendSourceLineCount;
  std::optional<std::uintmax_t> mappingCount;
  std::optional<std::uintmax_t> mappingRecordCount;
  std::optional<std::uintmax_t> backendMaxMappedLine;
  bool sourceRemapPresent = false;
  std::optional<std::string> sourceRemapPath;
  std::optional<std::string> sourceRemapGeneratedFile;
  std::optional<std::string> sourceRemapTarget;
  std::optional<std::string> sourceRemapMappingGranularity;
  std::optional<std::uintmax_t> sourceRemapMappingCount;
  std::optional<std::string> sourceRemapSourceBackend;
  std::optional<std::string> sourceRemapVariant;
  std::optional<std::string> sourceRemapSha256;
  std::optional<std::uintmax_t> sourceRemapSizeBytes;
  PackageBackendSourceMapChecks checks;
};

struct PackageDebugArtifactHealth {
  bool debugMetadataArtifactPresent = false;
  bool hirSourceMapArtifactPresent = false;
  bool debugMetadataExists = false;
  bool hirSourceMapExists = false;
  std::string health = "incomplete";
  PackageSourceRemapProvenanceHealth sourceRemap;
  PackageBackendSourceMapHealth backendSourceMap;
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
