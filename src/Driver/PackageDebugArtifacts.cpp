#include "PackageDebugArtifacts.h"

#include "crossgl/Driver/PackageJson.h"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <map>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <tuple>
#include <vector>

namespace crossgl {
namespace {

using NameCounts = std::map<std::string, std::uintmax_t>;

bool isLowercaseSha256(std::string_view value) {
  if (value.size() != 64) {
    return false;
  }
  return std::all_of(value.begin(), value.end(), [](char c) {
    const unsigned char ch = static_cast<unsigned char>(c);
    return std::isdigit(ch) || (c >= 'a' && c <= 'f');
  });
}

std::optional<NameCounts> parseNamedCountArray(std::string_view arrayText) {
  std::size_t position = 0;
  skipWhitespace(arrayText, position);
  if (position >= arrayText.size() || arrayText[position] != '[') {
    return std::nullopt;
  }
  ++position;
  skipWhitespace(arrayText, position);
  NameCounts counts;
  if (position < arrayText.size() && arrayText[position] == ']') {
    ++position;
    skipWhitespace(arrayText, position);
    return position == arrayText.size() ? std::optional<NameCounts>(counts)
                                        : std::nullopt;
  }
  while (position < arrayText.size()) {
    const std::size_t objectBegin = position;
    if (!skipJsonObject(arrayText, position)) {
      return std::nullopt;
    }
    const std::string_view object =
        arrayText.substr(objectBegin, position - objectBegin);
    const std::optional<std::string> name = objectStringMember(object, "name");
    const std::optional<std::uintmax_t> count =
        objectUnsignedMember(object, "count");
    if (!name || !count || counts.find(*name) != counts.end()) {
      return std::nullopt;
    }
    counts[*name] = *count;
    skipWhitespace(arrayText, position);
    if (position < arrayText.size() && arrayText[position] == ',') {
      ++position;
      skipWhitespace(arrayText, position);
      continue;
    }
    if (position < arrayText.size() && arrayText[position] == ']') {
      ++position;
      skipWhitespace(arrayText, position);
      return position == arrayText.size() ? std::optional<NameCounts>(counts)
                                          : std::nullopt;
    }
    return std::nullopt;
  }
  return std::nullopt;
}

std::optional<NameCounts> countRecordCategories(std::string_view arrayText,
                                                std::string_view field) {
  std::size_t position = 0;
  skipWhitespace(arrayText, position);
  if (position >= arrayText.size() || arrayText[position] != '[') {
    return std::nullopt;
  }
  ++position;
  skipWhitespace(arrayText, position);
  NameCounts counts;
  if (position < arrayText.size() && arrayText[position] == ']') {
    ++position;
    skipWhitespace(arrayText, position);
    return position == arrayText.size() ? std::optional<NameCounts>(counts)
                                        : std::nullopt;
  }
  while (position < arrayText.size()) {
    const std::size_t objectBegin = position;
    if (!skipJsonObject(arrayText, position)) {
      return std::nullopt;
    }
    const std::string_view object =
        arrayText.substr(objectBegin, position - objectBegin);
    const std::optional<std::string> name = objectStringMember(object, field);
    if (!name) {
      return std::nullopt;
    }
    ++counts[*name];
    skipWhitespace(arrayText, position);
    if (position < arrayText.size() && arrayText[position] == ',') {
      ++position;
      skipWhitespace(arrayText, position);
      continue;
    }
    if (position < arrayText.size() && arrayText[position] == ']') {
      ++position;
      skipWhitespace(arrayText, position);
      return position == arrayText.size() ? std::optional<NameCounts>(counts)
                                          : std::nullopt;
    }
    return std::nullopt;
  }
  return std::nullopt;
}

std::optional<std::uintmax_t> countJsonArrayElements(std::string_view arrayText) {
  std::size_t position = 0;
  skipWhitespace(arrayText, position);
  if (position >= arrayText.size() || arrayText[position] != '[') {
    return std::nullopt;
  }
  ++position;
  skipWhitespace(arrayText, position);
  std::uintmax_t count = 0;
  if (position < arrayText.size() && arrayText[position] == ']') {
    ++position;
    skipWhitespace(arrayText, position);
    return position == arrayText.size()
               ? std::optional<std::uintmax_t>(count)
               : std::nullopt;
  }
  while (position < arrayText.size()) {
    if (!skipJsonValue(arrayText, position)) {
      return std::nullopt;
    }
    ++count;
    skipWhitespace(arrayText, position);
    if (position < arrayText.size() && arrayText[position] == ',') {
      ++position;
      skipWhitespace(arrayText, position);
      continue;
    }
    if (position < arrayText.size() && arrayText[position] == ']') {
      ++position;
      skipWhitespace(arrayText, position);
      return position == arrayText.size()
                 ? std::optional<std::uintmax_t>(count)
                 : std::nullopt;
    }
    return std::nullopt;
  }
  return std::nullopt;
}

std::optional<std::string> readRegularFile(const std::filesystem::path &path) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return std::nullopt;
  }
  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    return std::nullopt;
  }
  return buffer.str();
}

const PackageArtifactRecord *
findArtifact(const PackageMetadata &metadata, std::string_view name) {
  for (const PackageArtifactRecord &artifact : metadata.artifacts) {
    if (artifact.name == name) {
      return &artifact;
    }
  }
  return nullptr;
}

std::optional<std::string>
readArtifactDocument(const PackageMetadata &metadata,
                     const PackageArtifactRecord *artifact) {
  if (!artifact || !artifact->packageRelative || !artifact->exists) {
    return std::nullopt;
  }
  return readRegularFile(metadata.packagePath / artifact->path);
}

std::optional<bool>
packageRelativeRegularFileExists(const PackageMetadata &metadata,
                                 const std::optional<std::string> &path) {
  if (!path || path->empty()) {
    return std::nullopt;
  }
  const std::filesystem::path relativePath(*path);
  if (relativePath.is_absolute()) {
    return false;
  }
  for (const std::filesystem::path &part : relativePath) {
    if (part == "..") {
      return false;
    }
  }

  std::error_code error;
  const bool exists =
      std::filesystem::is_regular_file(metadata.packagePath / relativePath,
                                       error);
  if (error) {
    return false;
  }
  return exists;
}

std::optional<bool> compareHirSourceLocations(std::string_view debugMetadata,
                                              std::string_view hirSourceMap) {
  const std::optional<std::string_view> debugLocations =
      findObjectMemberValue(debugMetadata, "hirSourceLocations");
  const std::optional<std::string_view> sourceMapLocations =
      findObjectMemberValue(hirSourceMap, "hirSourceLocations");
  if (!debugLocations || !sourceMapLocations) {
    return false;
  }
  return canonicalJson(*debugLocations) == canonicalJson(*sourceMapLocations);
}

std::optional<bool> sourceMapIsUnpaged(std::string_view hirSourceMap) {
  const std::optional<std::string_view> pagination =
      findObjectMemberValue(hirSourceMap, "pagination");
  const std::optional<std::string_view> locations =
      findObjectMemberValue(hirSourceMap, "hirSourceLocations");
  if (!pagination || !locations) {
    return false;
  }
  const std::optional<std::uintmax_t> activeCount =
      objectUnsignedMember(*pagination, "activeCount");
  if (!activeCount || *activeCount != 0 ||
      objectHasMemberEndingWith(*pagination, "Limit")) {
    return false;
  }

  for (const auto &[kind, arrayField] : {
           std::pair<std::string_view, std::string_view>{"expression",
                                                         "expressions"},
           std::pair<std::string_view, std::string_view>{"type", "types"},
           std::pair<std::string_view, std::string_view>{"statement",
                                                         "statements"},
       }) {
    const std::optional<std::string_view> array =
        findObjectMemberValue(*locations, arrayField);
    if (!array) {
      return false;
    }
    const std::optional<std::size_t> total = arrayLength(*array);
    if (!total) {
      return false;
    }
    const std::string prefix(kind);
    const std::optional<std::uintmax_t> offset =
        objectUnsignedMember(*pagination, prefix + "Offset");
    const std::optional<std::uintmax_t> totalCount =
        objectUnsignedMember(*pagination, prefix + "TotalCount");
    const std::optional<std::uintmax_t> emittedCount =
        objectUnsignedMember(*pagination, prefix + "EmittedCount");
    const std::optional<bool> hasMore =
        objectBoolMember(*pagination, prefix + "HasMore");
    const std::optional<std::uintmax_t> nextOffset =
        objectUnsignedMember(*pagination, prefix + "NextOffset");
    if (!offset || !totalCount || !emittedCount || !hasMore || !nextOffset ||
        *offset != 0 || *totalCount != *total || *emittedCount != *total ||
        *hasMore || *nextOffset != *total) {
      return false;
    }
  }

  return true;
}

std::optional<bool> sourceMapRecordsAreDisabled(std::string_view hirSourceMap) {
  const std::optional<std::string_view> records =
      findObjectMemberValue(hirSourceMap, "records");
  if (!records) {
    return false;
  }
  const std::optional<bool> enabled = objectBoolMember(*records, "enabled");
  const std::optional<std::uintmax_t> activeCount =
      objectUnsignedMember(*records, "activeCount");
  const std::optional<std::uintmax_t> offset =
      objectUnsignedMember(*records, "offset");
  const std::optional<std::uintmax_t> emittedCount =
      objectUnsignedMember(*records, "emittedCount");
  const std::optional<bool> hasMore = objectBoolMember(*records, "hasMore");
  const std::optional<std::uintmax_t> nextOffset =
      objectUnsignedMember(*records, "nextOffset");
  return enabled && activeCount && offset && emittedCount && hasMore &&
         nextOffset && !*enabled && *activeCount == 0 && *offset == 0 &&
         !findObjectMemberValue(*records, "limit") && *emittedCount == 0 &&
         !*hasMore && *nextOffset == 0 &&
         canonicalMemberEquals(*records, "items", "[]");
}

std::optional<bool>
sourceMapCategoryCountsAreConsistent(std::string_view hirSourceMap) {
  const std::optional<std::string_view> categories =
      findObjectMemberValue(hirSourceMap, "categoryCounts");
  const std::optional<std::string_view> locations =
      findObjectMemberValue(hirSourceMap, "hirSourceLocations");
  if (!categories || !locations) {
    return false;
  }

  bool ok = true;
  std::uintmax_t total = 0;
  for (const auto &[arrayField, totalField, categoryField, recordField] : {
           std::tuple<std::string_view, std::string_view, std::string_view,
                      std::string_view>{"expressions", "expressionTotalCount",
                                        "expressionKinds", "kind"},
           std::tuple<std::string_view, std::string_view, std::string_view,
                      std::string_view>{"types", "typeTotalCount",
                                        "typeOwnerKinds", "ownerKind"},
           std::tuple<std::string_view, std::string_view, std::string_view,
                      std::string_view>{"statements", "statementTotalCount",
                                        "statementKinds", "statementKind"},
       }) {
    const std::optional<std::string_view> records =
        findObjectMemberValue(*locations, arrayField);
    const std::optional<std::string_view> categoryEntries =
        findObjectMemberValue(*categories, categoryField);
    const std::optional<std::uintmax_t> categoryTotal =
        objectUnsignedMember(*categories, totalField);
    if (!records || !categoryEntries || !categoryTotal) {
      return false;
    }
    const std::optional<std::size_t> recordCount = arrayLength(*records);
    const std::optional<NameCounts> expected =
        countRecordCategories(*records, recordField);
    const std::optional<NameCounts> actual =
        parseNamedCountArray(*categoryEntries);
    if (!recordCount || !expected || !actual) {
      return false;
    }
    total += *recordCount;
    if (*categoryTotal != *recordCount || *actual != *expected) {
      ok = false;
    }
  }
  const std::optional<std::uintmax_t> recordTotal =
      objectUnsignedMember(*categories, "recordTotalCount");
  if (!recordTotal || *recordTotal != total) {
    ok = false;
  }
  return ok;
}

std::optional<bool>
recordsTotalMatchesCategoryCounts(std::string_view hirSourceMap) {
  const std::optional<std::string_view> categories =
      findObjectMemberValue(hirSourceMap, "categoryCounts");
  const std::optional<std::string_view> records =
      findObjectMemberValue(hirSourceMap, "records");
  if (!categories || !records) {
    return false;
  }
  const std::optional<std::uintmax_t> categoryTotal =
      objectUnsignedMember(*categories, "recordTotalCount");
  const std::optional<std::uintmax_t> recordsTotal =
      objectUnsignedMember(*records, "totalCount");
  if (!categoryTotal || !recordsTotal) {
    return false;
  }
  return *recordsTotal == *categoryTotal;
}

std::optional<std::string>
sourceRemapProvenanceHash(std::string_view sourceRemap) {
  const std::optional<std::string_view> sha256 =
      findObjectMemberValue(sourceRemap, "sha256");
  if (!sha256) {
    return std::nullopt;
  }
  const std::optional<std::string> algorithm =
      objectStringMember(*sha256, "algorithm");
  const std::optional<std::string> value = objectStringMember(*sha256, "value");
  if (!algorithm || *algorithm != "sha256" || !value) {
    return std::nullopt;
  }
  return value;
}

PackageSourceRemapProvenanceHealth
collectSourceRemapProvenanceHealth(const PackageMetadata &metadata) {
  PackageSourceRemapProvenanceHealth health;
  health.artifactPresent = metadata.sourceRemapArtifactPresent;
  const PackageArtifactRecord *artifact = findArtifact(metadata, "sourceRemap");
  if (artifact != nullptr) {
    health.path = artifact->path;
  }
  health.exists = artifact != nullptr && artifact->exists;

  if (!health.artifactPresent) {
    return health;
  }
  if (!health.exists) {
    health.health = "incomplete";
    return health;
  }

  const std::optional<std::string> document =
      readArtifactDocument(metadata, artifact);
  if (!document) {
    health.health = "incomplete";
    return health;
  }

  health.schemaVersion = objectUnsignedMember(*document, "schemaVersion");
  health.kind = objectStringMember(*document, "kind");
  health.contractVersion = objectStringMember(*document, "contractVersion");
  health.target = objectStringMember(*document, "target");
  health.generatedFile = objectStringMember(*document, "generatedFile");
  health.mappingGranularity =
      objectStringMember(*document, "mappingGranularity");
  health.mappingCount = objectUnsignedMember(*document, "mappingCount");
  const std::optional<std::string_view> sourceRemap =
      findObjectMemberValue(*document, "sourceRemap");
  if (sourceRemap) {
    health.sourcePath = objectStringMember(*sourceRemap, "path");
    health.sourceSha256 = sourceRemapProvenanceHash(*sourceRemap);
    health.sourceSizeBytes = objectUnsignedMember(*sourceRemap, "sizeBytes");
  }

  health.checks.identityMatchesContract =
      health.schemaVersion && *health.schemaVersion == 1 && health.kind &&
      *health.kind == "crossgl.sourceRemapProvenance" &&
      health.contractVersion &&
      *health.contractVersion == "source-remap-provenance-v1";
  health.checks.targetMatchesPackage =
      health.target && *health.target == metadata.target;
  health.checks.generatedFilePresent =
      health.generatedFile && !health.generatedFile->empty();
  health.checks.mappingGranularityMatchesContract =
      health.mappingGranularity && *health.mappingGranularity == "source-span";
  health.checks.mappingCountPositive =
      health.mappingCount && *health.mappingCount > 0;
  health.checks.sourcePathPresent =
      health.sourcePath && !health.sourcePath->empty();
  health.checks.sourceHashPresent =
      health.sourceSha256 && isLowercaseSha256(*health.sourceSha256);
  health.checks.sourceSizeBytesPresent = health.sourceSizeBytes.has_value();

  const std::vector<std::optional<bool>> checks = {
      health.checks.identityMatchesContract,
      health.checks.targetMatchesPackage,
      health.checks.generatedFilePresent,
      health.checks.mappingGranularityMatchesContract,
      health.checks.mappingCountPositive,
      health.checks.sourcePathPresent,
      health.checks.sourceHashPresent,
      health.checks.sourceSizeBytesPresent,
  };
  const bool allTrue = std::all_of(checks.begin(), checks.end(), [](auto value) {
    return value.has_value() && *value;
  });
  health.health = allTrue ? "ok" : "drift";
  return health;
}

PackageBackendSourceMapHealth
collectBackendSourceMapHealth(const PackageMetadata &metadata) {
  PackageBackendSourceMapHealth health;
  health.artifactPresent = metadata.backendSourceMapArtifactPresent;
  const PackageArtifactRecord *artifact = findArtifact(metadata, "backendSourceMap");
  if (artifact != nullptr) {
    health.path = artifact->path;
  }
  health.exists = artifact != nullptr && artifact->exists;

  if (!health.artifactPresent) {
    return health;
  }
  if (!health.exists) {
    health.health = "incomplete";
    return health;
  }

  const std::optional<std::string> document =
      readArtifactDocument(metadata, artifact);
  if (!document) {
    health.health = "incomplete";
    return health;
  }

  health.schemaVersion = objectUnsignedMember(*document, "schemaVersion");
  health.kind = objectStringMember(*document, "kind");
  health.target = objectStringMember(*document, "target");
  health.module = objectStringMember(*document, "module");
  health.mappingCount = objectUnsignedMember(*document, "mappingCount");
  const std::optional<std::string_view> backend =
      findObjectMemberValue(*document, "backend");
  if (backend) {
    health.backendLanguage = objectStringMember(*backend, "language");
    health.backendLineCount = objectUnsignedMember(*backend, "lineCount");
  }
  const std::optional<std::string_view> mappings =
      findObjectMemberValue(*document, "mappings");
  if (mappings) {
    health.mappingRecordCount = countJsonArrayElements(*mappings);
  }

  health.checks.identityMatchesContract =
      health.schemaVersion && *health.schemaVersion == 1 && health.kind &&
      *health.kind == "crossgl.backendSourceMap";
  health.checks.targetMatchesPackage =
      health.target && *health.target == metadata.target;
  health.checks.moduleMatchesPackage =
      health.module && *health.module == metadata.module;
  health.checks.backendLanguagePresent =
      health.backendLanguage && !health.backendLanguage->empty();
  health.checks.backendLineCountPresent = health.backendLineCount.has_value();
  health.checks.mappingCountMatchesMappings =
      health.mappingCount && health.mappingRecordCount &&
      *health.mappingCount == *health.mappingRecordCount;

  const std::vector<std::optional<bool>> checks = {
      health.checks.identityMatchesContract,
      health.checks.targetMatchesPackage,
      health.checks.moduleMatchesPackage,
      health.checks.backendLanguagePresent,
      health.checks.backendLineCountPresent,
      health.checks.mappingCountMatchesMappings,
  };
  const bool allTrue = std::all_of(checks.begin(), checks.end(), [](auto value) {
    return value.has_value() && *value;
  });
  health.health = allTrue ? "ok" : "drift";
  return health;
}

} // namespace

PackageDebugArtifactHealth
collectPackageDebugArtifactHealth(const PackageMetadata &metadata) {
  PackageDebugArtifactHealth health;
  health.debugMetadataArtifactPresent = metadata.debugMetadataArtifactPresent;
  health.hirSourceMapArtifactPresent = metadata.hirSourceMapArtifactPresent;
  health.sourceRemap = collectSourceRemapProvenanceHealth(metadata);
  health.backendSourceMap = collectBackendSourceMapHealth(metadata);

  const PackageArtifactRecord *debugMetadata =
      findArtifact(metadata, "debugMetadata");
  const PackageArtifactRecord *hirSourceMap = findArtifact(metadata, "hirSourceMap");
  health.debugMetadataExists = debugMetadata != nullptr && debugMetadata->exists;
  health.hirSourceMapExists = hirSourceMap != nullptr && hirSourceMap->exists;

  const std::optional<std::string> debugMetadataDocument =
      readArtifactDocument(metadata, debugMetadata);
  const std::optional<std::string> hirSourceMapDocument =
      readArtifactDocument(metadata, hirSourceMap);
  if (!debugMetadataDocument || !hirSourceMapDocument) {
    return health;
  }

  health.hirSourceLocationsMatch =
      compareHirSourceLocations(*debugMetadataDocument, *hirSourceMapDocument);
  health.sourceMapUnfiltered =
      canonicalMemberEquals(*hirSourceMapDocument, "filters", "{\"activeCount\":0}");
  health.sourceMapUnpaged = sourceMapIsUnpaged(*hirSourceMapDocument);
  health.sourceMapRecordsDisabled =
      sourceMapRecordsAreDisabled(*hirSourceMapDocument);
  health.sourceMapCategoryCountsConsistent =
      sourceMapCategoryCountsAreConsistent(*hirSourceMapDocument);
  health.recordsTotalCountMatchesCategoryCounts =
      recordsTotalMatchesCategoryCounts(*hirSourceMapDocument);

  const std::vector<std::optional<bool>> checks = {
      health.hirSourceLocationsMatch,
      health.sourceMapUnfiltered,
      health.sourceMapUnpaged,
      health.sourceMapRecordsDisabled,
      health.sourceMapCategoryCountsConsistent,
      health.recordsTotalCountMatchesCategoryCounts,
  };
  const bool allTrue = std::all_of(checks.begin(), checks.end(), [](auto value) {
    return value.has_value() && *value;
  }) && (!health.sourceRemap.artifactPresent ||
         health.sourceRemap.health == "ok") &&
         (!health.backendSourceMap.artifactPresent ||
          health.backendSourceMap.health == "ok");
  health.health = allTrue ? "ok" : "drift";
  return health;
}

PackageVulkanNativeProfileHealth
collectPackageVulkanNativeProfileHealth(const PackageMetadata &metadata) {
  PackageVulkanNativeProfileHealth health;
  health.applicable = metadata.target == "vulkan";
  health.nativeProfileArtifactPresent = metadata.nativeProfileArtifactPresent;
  if (!health.applicable) {
    return health;
  }

  health.health = "incomplete";
  const PackageArtifactRecord *nativeProfile =
      findArtifact(metadata, "nativeProfile");
  health.nativeProfileExists =
      nativeProfile != nullptr && nativeProfile->exists;
  const std::optional<std::string> nativeProfileDocument =
      readArtifactDocument(metadata, nativeProfile);
  if (!nativeProfileDocument) {
    return health;
  }

  const std::optional<std::string_view> profile =
      findObjectMemberValue(*nativeProfileDocument, "profile");
  const std::optional<std::string_view> artifacts =
      findObjectMemberValue(*nativeProfileDocument, "artifacts");
  const std::optional<std::string_view> debug =
      findObjectMemberValue(*nativeProfileDocument, "debug");
  const std::optional<std::string_view> disassembly =
      debug ? findObjectMemberValue(*debug, "disassembly") : std::nullopt;
  health.schemaVersion =
      objectUnsignedMember(*nativeProfileDocument, "schemaVersion");
  health.api = objectStringMember(*nativeProfileDocument, "api");
  health.generator = objectStringMember(*nativeProfileDocument, "generator");
  health.nativeBinary =
      artifacts ? objectStringMember(*artifacts, "nativeBinary") : std::nullopt;
  health.backendAssembly =
      artifacts ? objectStringMember(*artifacts, "backendAssembly")
                : std::nullopt;
  if (disassembly) {
    health.disassemblyStatus = objectStringMember(*disassembly, "status");
    health.disassemblyPath = objectStringMember(*disassembly, "path");
    health.disassemblyExists =
        packageRelativeRegularFileExists(metadata, health.disassemblyPath);
  }
  if (profile) {
    health.profileName = objectStringMember(*profile, "name");
    health.vulkanVersion = objectStringMember(*profile, "vulkanVersion");
    health.spirvVersion = objectStringMember(*profile, "spirvVersion");
  }

  const std::optional<std::string> target =
      objectStringMember(*nativeProfileDocument, "target");
  const std::optional<std::string> module =
      objectStringMember(*nativeProfileDocument, "module");
  const PackageArtifactRecord *nativeBinary =
      findArtifact(metadata, "nativeBinary");
  const PackageArtifactRecord *backendAssembly =
      findArtifact(metadata, "backendAssembly");
  health.targetMatchesPackage = target && *target == metadata.target;
  health.moduleMatchesPackage = module && *module == metadata.module;
  health.nativeBinaryMatchesManifest =
      health.nativeBinary && nativeBinary &&
      *health.nativeBinary == nativeBinary->path;
  health.backendAssemblyMatchesManifest =
      health.backendAssembly && backendAssembly &&
      *health.backendAssembly == backendAssembly->path;
  if (health.disassemblyStatus && *health.disassemblyStatus == "emitted") {
    health.emittedDisassemblyExists =
        health.disassemblyPath && health.disassemblyExists &&
        *health.disassemblyExists;
  } else if (health.disassemblyStatus &&
             (*health.disassemblyStatus == "failed" ||
              *health.disassemblyStatus == "skipped-tool-missing")) {
    health.emittedDisassemblyExists = std::nullopt;
  } else if (health.disassemblyStatus) {
    health.emittedDisassemblyExists = false;
  }
  health.spirvProfilePresent =
      health.api && *health.api == "vulkan" && health.profileName &&
      *health.profileName == "vulkan-prototype" && health.vulkanVersion &&
      health.spirvVersion && health.generator;

  std::vector<std::optional<bool>> checks = {
      health.targetMatchesPackage,
      health.moduleMatchesPackage,
      health.nativeBinaryMatchesManifest,
      health.backendAssemblyMatchesManifest,
      health.spirvProfilePresent,
  };
  if (health.emittedDisassemblyExists.has_value()) {
    checks.push_back(health.emittedDisassemblyExists);
  }
  const bool allTrue = std::all_of(checks.begin(), checks.end(), [](auto value) {
    return value.has_value() && *value;
  });
  health.health = allTrue ? "ok" : "drift";
  return health;
}

} // namespace crossgl
