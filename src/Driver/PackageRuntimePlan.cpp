#include "crossgl/Driver/PackageRuntimePlan.h"

#include "crossgl/Basic/Json.h"
#include "crossgl/Driver/PackageJson.h"
#include "crossgl/Driver/PackageMetadata.h"
#include "crossgl/Driver/PackageTargetContracts.h"

#include "PackageDebugArtifacts.h"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <optional>
#include <ostream>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

namespace crossgl {
namespace {

constexpr std::string_view kNativeBinaryArtifact = "nativeBinary";
constexpr std::string_view kBackendSourceArtifact = "backendSource";
constexpr std::string_view kSourceRemapArtifact = "sourceRemap";
constexpr std::string_view kBackendSourceMapArtifact = "backendSourceMap";

void writeNullableString(std::ostream &out,
                         const std::optional<std::string> &value) {
  if (value) {
    out << "\"" << escapeJson(*value) << "\"";
  } else {
    out << "null";
  }
}

void writeNullableString(std::ostream &out, const std::string *value) {
  if (value != nullptr) {
    out << "\"" << escapeJson(*value) << "\"";
  } else {
    out << "null";
  }
}

void writeNullableUnsigned(std::ostream &out,
                           const std::optional<std::uintmax_t> &value) {
  if (value) {
    out << *value;
  } else {
    out << "null";
  }
}

bool sourceRemapProvenanceAvailable(
    const PackageSourceRemapProvenanceHealth &health) {
  return health.schemaVersion || health.kind || health.contractVersion ||
         health.target || health.generatedFile || health.mappingGranularity ||
         health.mappingCount || health.sourcePath || health.sourceSha256 ||
         health.sourceSizeBytes;
}

bool backendSourceMapProvenanceAvailable(
    const PackageBackendSourceMapHealth &health) {
  return health.schemaVersion || health.kind || health.target || health.module ||
         health.mappingGranularity || health.sourceBackend ||
         health.targetBackend || health.backendLanguage ||
         health.backendLineCount || health.mappingCount ||
         health.mappingRecordCount || health.sourceRemapPresent;
}

void writeSourceRemapProvenanceSummary(
    std::ostream &out, const PackageSourceRemapProvenanceHealth &health,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"available\": "
      << (sourceRemapProvenanceAvailable(health) ? "true" : "false") << ",\n"
      << indent << "  \"health\": \"" << escapeJson(health.health) << "\",\n"
      << indent << "  \"schemaVersion\": ";
  writeNullableUnsigned(out, health.schemaVersion);
  out << ",\n" << indent << "  \"kind\": ";
  writeNullableString(out, health.kind);
  out << ",\n" << indent << "  \"contractVersion\": ";
  writeNullableString(out, health.contractVersion);
  out << ",\n" << indent << "  \"target\": ";
  writeNullableString(out, health.target);
  out << ",\n" << indent << "  \"generatedFile\": ";
  writeNullableString(out, health.generatedFile);
  out << ",\n" << indent << "  \"mappingGranularity\": ";
  writeNullableString(out, health.mappingGranularity);
  out << ",\n" << indent << "  \"mappingCount\": ";
  writeNullableUnsigned(out, health.mappingCount);
  out << ",\n" << indent << "  \"sourcePath\": ";
  writeNullableString(out, health.sourcePath);
  out << ",\n" << indent << "  \"sourceSha256\": ";
  writeNullableString(out, health.sourceSha256);
  out << ",\n" << indent << "  \"sourceSizeBytes\": ";
  writeNullableUnsigned(out, health.sourceSizeBytes);
  out << ",\n" << indent << "  \"sourceRemapTarget\": ";
  writeNullableString(out, health.sourceRemapTarget);
  out << ",\n" << indent << "  \"sourceRemapMappingGranularity\": ";
  writeNullableString(out, health.sourceRemapMappingGranularity);
  out << ",\n" << indent << "  \"sourceRemapSourceBackend\": ";
  writeNullableString(out, health.sourceRemapSourceBackend);
  out << ",\n" << indent << "  \"sourceRemapVariant\": ";
  writeNullableString(out, health.sourceRemapVariant);
  out << "\n" << indent << "}";
}

void writeBackendSourceMapProvenanceSummary(
    std::ostream &out, const PackageBackendSourceMapHealth &health,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"available\": "
      << (backendSourceMapProvenanceAvailable(health) ? "true" : "false")
      << ",\n"
      << indent << "  \"health\": \"" << escapeJson(health.health) << "\",\n"
      << indent << "  \"schemaVersion\": ";
  writeNullableUnsigned(out, health.schemaVersion);
  out << ",\n" << indent << "  \"kind\": ";
  writeNullableString(out, health.kind);
  out << ",\n" << indent << "  \"target\": ";
  writeNullableString(out, health.target);
  out << ",\n" << indent << "  \"module\": ";
  writeNullableString(out, health.module);
  out << ",\n" << indent << "  \"mappingGranularity\": ";
  writeNullableString(out, health.mappingGranularity);
  out << ",\n" << indent << "  \"sourceBackend\": ";
  writeNullableString(out, health.sourceBackend);
  out << ",\n" << indent << "  \"targetBackend\": ";
  writeNullableString(out, health.targetBackend);
  out << ",\n" << indent << "  \"backendLanguage\": ";
  writeNullableString(out, health.backendLanguage);
  out << ",\n" << indent << "  \"backendLineCount\": ";
  writeNullableUnsigned(out, health.backendLineCount);
  out << ",\n" << indent << "  \"mappingCount\": ";
  writeNullableUnsigned(out, health.mappingCount);
  out << ",\n" << indent << "  \"mappingRecordCount\": ";
  writeNullableUnsigned(out, health.mappingRecordCount);
  out << ",\n" << indent << "  \"sourceRemapPresent\": "
      << (health.sourceRemapPresent ? "true" : "false") << ",\n"
      << indent << "  \"sourceRemapPath\": ";
  writeNullableString(out, health.sourceRemapPath);
  out << ",\n" << indent << "  \"sourceRemapGeneratedFile\": ";
  writeNullableString(out, health.sourceRemapGeneratedFile);
  out << ",\n" << indent << "  \"sourceRemapTarget\": ";
  writeNullableString(out, health.sourceRemapTarget);
  out << ",\n" << indent << "  \"sourceRemapMappingGranularity\": ";
  writeNullableString(out, health.sourceRemapMappingGranularity);
  out << ",\n" << indent << "  \"sourceRemapMappingCount\": ";
  writeNullableUnsigned(out, health.sourceRemapMappingCount);
  out << ",\n" << indent << "  \"sourceRemapSourceBackend\": ";
  writeNullableString(out, health.sourceRemapSourceBackend);
  out << ",\n" << indent << "  \"sourceRemapVariant\": ";
  writeNullableString(out, health.sourceRemapVariant);
  out << ",\n" << indent << "  \"sourceRemapSha256\": ";
  writeNullableString(out, health.sourceRemapSha256);
  out << ",\n" << indent << "  \"sourceRemapSizeBytes\": ";
  writeNullableUnsigned(out, health.sourceRemapSizeBytes);
  out << "\n" << indent << "}";
}

void writeHostLoaderLoadStepProvenancePointer(std::ostream &out,
                                              std::string_view source,
                                              bool available,
                                              std::string_view health,
                                              std::string_view indent) {
  out << "{\n"
      << indent << "  \"source\": \"" << escapeJson(source) << "\",\n"
      << indent << "  \"available\": " << (available ? "true" : "false")
      << ",\n"
      << indent << "  \"health\": \"" << escapeJson(health) << "\"\n"
      << indent << "}";
}

void writeStringArray(std::ostream &out,
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

void writeJsonArrayMemberOrEmpty(std::ostream &out, std::string_view object,
                                 std::string_view key) {
  const std::optional<std::string_view> value = findObjectMemberValue(object, key);
  if (value && !value->empty() && value->front() == '[') {
    out << *value;
  } else {
    out << "[]";
  }
}

void writeSourceLocation(std::ostream &out, const SourceLocation &location,
                         std::string_view indent) {
  out << "{\n"
      << indent << "  \"file\": \"" << escapeJson(location.file) << "\",\n"
      << indent << "  \"line\": " << location.line << ",\n"
      << indent << "  \"column\": " << location.column << ",\n"
      << indent << "  \"offset\": " << location.offset << ",\n"
      << indent << "  \"length\": " << location.length << ",\n"
      << indent << "  \"endLine\": " << location.endLine << ",\n"
      << indent << "  \"endColumn\": " << location.endColumn << ",\n"
      << indent << "  \"endOffset\": " << location.endOffset << "\n"
      << indent << "}";
}

void writeDiagnosticRecord(std::ostream &out, const Diagnostic &diagnostic,
                           std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"severity\": \""
      << escapeJson(toString(diagnostic.severity)) << "\",\n"
      << indent << "  \"code\": \"" << escapeJson(diagnostic.code) << "\",\n"
      << indent << "  \"message\": \"" << escapeJson(diagnostic.message)
      << "\",\n"
      << indent << "  \"location\": ";
  writeSourceLocation(out, diagnostic.location, std::string(indent) + "  ");
  if (!diagnostic.target.empty()) {
    out << ",\n"
        << indent << "  \"target\": \"" << escapeJson(diagnostic.target)
        << "\"";
  }
  if (!diagnostic.missingCapabilities.empty()) {
    out << ",\n" << indent << "  \"missingCapabilities\": ";
    writeStringArray(out, diagnostic.missingCapabilities);
  }
  out << "\n" << indent << "}";
}

void writeDiagnostics(std::ostream &out,
                      const std::vector<Diagnostic> &diagnostics,
                      std::string_view indent) {
  out << "[";
  for (std::size_t index = 0; index < diagnostics.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeDiagnosticRecord(out, diagnostics[index], std::string(indent) + "  ");
  }
  if (!diagnostics.empty()) {
    out << "\n" << indent;
  }
  out << "]";
}

std::size_t countDiagnostics(const std::vector<Diagnostic> &diagnostics,
                             DiagnosticSeverity severity) {
  return std::count_if(diagnostics.begin(), diagnostics.end(),
                       [severity](const Diagnostic &diagnostic) {
                         return diagnostic.severity == severity;
                       });
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

bool nativeStatusIsReady(const std::optional<std::string> &status) {
  return status == "emitted" || status == "validated";
}

bool artifactUsable(const PackageArtifactRecord *artifact) {
  return artifact != nullptr && artifact->packageRelative && artifact->exists;
}

bool targetSupportsSourcePackage(const PackageTargetContract &contract) {
  return contract.allowsPlannedNativeBinary ||
         contract.allowsPlannedNativeSourceEvidence;
}

struct RuntimeArtifactPolicy {
  bool requiresNativeBinaryStatus = false;
  bool supportsSourcePackage = false;
};

RuntimeArtifactPolicy runtimeArtifactPolicy(
    const PackageMetadata &metadata, const PackageTargetContract &contract) {
  if (metadata.artifactRequirements) {
    return RuntimeArtifactPolicy{
        metadata.artifactRequirements->requiresNativeBinaryStatus,
        metadata.artifactRequirements->packageMode == "source-package"};
  }

  return RuntimeArtifactPolicy{contract.requiresNativeBinaryStatus,
                               targetSupportsSourcePackage(contract)};
}

bool nativeArtifactReady(const PackageMetadata &metadata,
                         const RuntimeArtifactPolicy &policy,
                         const PackageArtifactRecord *nativeArtifact) {
  if (!artifactUsable(nativeArtifact)) {
    return false;
  }
  if (!policy.requiresNativeBinaryStatus) {
    return true;
  }
  return nativeStatusIsReady(effectivePackageNativeBinaryStatus(metadata));
}

std::optional<std::size_t> jsonArraySize(std::string_view object,
                                         std::string_view key) {
  const std::optional<std::string_view> array = findObjectMemberValue(object, key);
  if (!array) {
    return std::nullopt;
  }
  return arrayLength(*array);
}

std::size_t jsonArrayObjectMemberCount(std::string_view object,
                                       std::string_view arrayKey,
                                       std::string_view memberKey) {
  const std::optional<std::string_view> array =
      findObjectMemberValue(object, arrayKey);
  if (!array) {
    return 0;
  }

  std::size_t position = 0;
  skipWhitespace(*array, position);
  if (position >= array->size() || (*array)[position] != '[') {
    return 0;
  }
  ++position;

  std::size_t count = 0;
  while (position < array->size()) {
    skipWhitespace(*array, position);
    if (position < array->size() && (*array)[position] == ']') {
      break;
    }

    const std::size_t valueBegin = position;
    if (!skipJsonValue(*array, position)) {
      break;
    }
    const std::string_view value(array->data() + valueBegin,
                                 position - valueBegin);
    if (!value.empty() && value.front() == '{' &&
        findObjectMemberValue(value, memberKey)) {
      ++count;
    }

    skipWhitespace(*array, position);
    if (position < array->size() && (*array)[position] == ',') {
      ++position;
    }
  }

  return count;
}

struct Selection {
  std::optional<std::string> mode;
  const PackageArtifactRecord *artifact = nullptr;
};

Selection selectArtifact(const PackageMetadata &metadata,
                         const PackageTargetContract &contract,
                         RuntimeLoaderPackageMode requestedMode,
                         std::vector<Diagnostic> &diagnostics) {
  const RuntimeArtifactPolicy policy = runtimeArtifactPolicy(metadata, contract);
  const PackageArtifactRecord *nativeArtifact =
      findArtifact(metadata, kNativeBinaryArtifact);
  const PackageArtifactRecord *sourceArtifact =
      findArtifact(metadata, kBackendSourceArtifact);
  const bool nativeReady =
      nativeArtifactReady(metadata, policy, nativeArtifact);
  const bool sourceReady =
      policy.supportsSourcePackage && artifactUsable(sourceArtifact);

  if (requestedMode == RuntimeLoaderPackageMode::Native) {
    if (!nativeReady) {
      Diagnostic diagnostic;
      diagnostic.severity = DiagnosticSeverity::Error;
      diagnostic.code = "package.runtime-plan.native-artifact-unavailable";
      diagnostic.message =
          "runtime loader plan requires an available nativeBinary artifact";
      diagnostic.target = metadata.target;
      diagnostics.push_back(std::move(diagnostic));
      return {};
    }
    return Selection{"native", nativeArtifact};
  }

  if (requestedMode == RuntimeLoaderPackageMode::SourcePackage) {
    if (!sourceReady) {
      Diagnostic diagnostic;
      diagnostic.severity = DiagnosticSeverity::Error;
      diagnostic.code = "package.runtime-plan.source-artifact-unavailable";
      diagnostic.message =
          "runtime loader plan requires an available backendSource artifact";
      diagnostic.target = metadata.target;
      diagnostics.push_back(std::move(diagnostic));
      return {};
    }
    return Selection{"source-package", sourceArtifact};
  }

  if (nativeReady) {
    return Selection{"native", nativeArtifact};
  }
  if (sourceReady) {
    return Selection{"source-package", sourceArtifact};
  }

  Diagnostic diagnostic;
  diagnostic.severity = DiagnosticSeverity::Error;
  diagnostic.code = "package.runtime-plan.artifact-unavailable";
  diagnostic.message =
      "runtime loader plan could not select a native or source-package artifact";
  diagnostic.target = metadata.target;
  diagnostics.push_back(std::move(diagnostic));
  return {};
}

std::optional<std::uintmax_t>
packageManifestSchemaVersion(const PackageMetadata *metadata) {
  if (metadata == nullptr) {
    return std::nullopt;
  }
  return objectUnsignedMember(metadata->documents.manifest, "schemaVersion");
}

std::vector<std::string>
requiredArtifactNames(const PackageMetadata *metadata,
                      const PackageTargetContract *contract) {
  std::vector<std::string> names;
  if (metadata != nullptr && metadata->artifactRequirements) {
    names.reserve(metadata->artifactRequirements->requiredPathArtifacts.size());
    for (const PackageRequiredPathArtifactRecord &artifact :
         metadata->artifactRequirements->requiredPathArtifacts) {
      names.push_back(artifact.name);
    }
    return names;
  }

  if (contract != nullptr) {
    names.reserve(contract->requiredArtifactCount);
    for (std::size_t index = 0; index < contract->requiredArtifactCount; ++index) {
      names.emplace_back(contract->requiredArtifacts[index]);
    }
  }
  return names;
}

void writeRequiredArtifactPaths(std::ostream &out,
                                const PackageMetadata *metadata,
                                const std::vector<std::string> &names,
                                std::string_view indent) {
  out << "{";
  for (std::size_t index = 0; index < names.size(); ++index) {
    const PackageArtifactRecord *artifact =
        metadata != nullptr ? findArtifact(*metadata, names[index]) : nullptr;
    out << (index == 0 ? "\n" : ",\n")
        << indent << "  \"" << escapeJson(names[index]) << "\": ";
    if (artifact != nullptr && !artifact->path.empty()) {
      out << "\"" << escapeJson(artifact->path) << "\"";
    } else {
      out << "null";
    }
  }
  if (!names.empty()) {
    out << "\n" << indent;
  }
  out << "}";
}

void writePackageArtifactRequirements(
    std::ostream &out, const PackageArtifactRequirementsRecord &requirements,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"target\": \"" << escapeJson(requirements.target)
      << "\",\n"
      << indent << "  \"packageMode\": \""
      << escapeJson(requirements.packageMode) << "\",\n"
      << indent << "  \"requiredPathArtifacts\": [";
  for (std::size_t index = 0; index < requirements.requiredPathArtifacts.size();
       ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << "\"" << escapeJson(requirements.requiredPathArtifacts[index].name)
        << "\"";
  }
  out << "],\n"
      << indent << "  \"requiresNativeBinaryStatus\": "
      << (requirements.requiresNativeBinaryStatus ? "true" : "false") << ",\n"
      << indent << "  \"allowsPlannedNativeBinary\": "
      << (requirements.allowsPlannedNativeBinary ? "true" : "false") << ",\n"
      << indent << "  \"allowsPlannedNativeSourceEvidence\": "
      << (requirements.allowsPlannedNativeSourceEvidence ? "true" : "false")
      << ",\n"
      << indent << "  \"evidenceIds\": ";
  writeStringArray(out, requirements.evidenceIds);
  out << "\n" << indent << "}";
}

void writeContractRequirements(std::ostream &out,
                               const PackageTargetContract &contract,
                               std::string_view indent) {
  out << "{\n"
      << indent << "  \"target\": \"" << escapeJson(contract.target)
      << "\",\n"
      << indent << "  \"packageMode\": \""
      << (targetSupportsSourcePackage(contract) ? "source-package" : "native")
      << "\",\n"
      << indent << "  \"requiredPathArtifacts\": [";
  for (std::size_t index = 0; index < contract.requiredArtifactCount; ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << "\"" << escapeJson(contract.requiredArtifacts[index]) << "\"";
  }
  out << "],\n"
      << indent << "  \"requiresNativeBinaryStatus\": "
      << (contract.requiresNativeBinaryStatus ? "true" : "false") << ",\n"
      << indent << "  \"allowsPlannedNativeBinary\": "
      << (contract.allowsPlannedNativeBinary ? "true" : "false") << ",\n"
      << indent << "  \"allowsPlannedNativeSourceEvidence\": "
      << (contract.allowsPlannedNativeSourceEvidence ? "true" : "false")
      << ",\n"
      << indent << "  \"evidenceIds\": []\n"
      << indent << "}";
}

void writeSelectedArtifact(std::ostream &out,
                           const PackageArtifactRecord *artifact,
                           const std::optional<std::string> &mode,
                           std::string_view indent) {
  if (artifact == nullptr || !mode) {
    out << "null";
    return;
  }
  out << "{\n"
      << indent << "  \"name\": \"" << escapeJson(artifact->name) << "\",\n"
      << indent << "  \"path\": \"" << escapeJson(artifact->path) << "\",\n"
      << indent << "  \"packageMode\": \"" << escapeJson(*mode) << "\",\n"
      << indent << "  \"packageRelative\": "
      << (artifact->packageRelative ? "true" : "false") << ",\n"
      << indent << "  \"exists\": " << (artifact->exists ? "true" : "false")
      << "\n"
      << indent << "}";
}

void writeRuntimeArtifactSelection(
    std::ostream &out, const PackageRuntimePlanOptions &options,
    const PackageMetadata *metadata, const Selection &selection, bool success,
    std::string_view indent) {
  const std::string *packageTarget = metadata ? &metadata->target : nullptr;
  const std::string *requestedLoaderTarget =
      isKnownPackageTarget(options.requestedTarget) ? &options.requestedTarget
                                                   : nullptr;
  const std::optional<std::string> selectedTarget =
      success && requestedLoaderTarget != nullptr
          ? std::optional<std::string>(*requestedLoaderTarget)
          : std::nullopt;
  out << "{\n"
      << indent << "  \"schemaVersion\": 1,\n"
      << indent << "  \"requestedTarget\": ";
  writeNullableString(out, requestedLoaderTarget);
  out << ",\n" << indent << "  \"requestedPackageMode\": \""
      << escapeJson(toString(options.packageMode)) << "\",\n"
      << indent << "  \"packageTarget\": ";
  writeNullableString(out, packageTarget);
  out << ",\n" << indent << "  \"selectedTarget\": ";
  writeNullableString(out, selectedTarget);
  out << ",\n" << indent << "  \"selected\": "
      << (success ? "true" : "false") << ",\n"
      << indent << "  \"selectedPackageMode\": ";
  writeNullableString(out, selection.mode);
  out << ",\n"
      << indent << "  \"sourceParsingRequired\": false,\n"
      << indent << "  \"compilerInvocationRequired\": false,\n"
      << indent << "  \"deviceExecutionRequired\": false,\n"
      << indent << "  \"sourceInputs\": [],\n"
      << indent << "  \"artifact\": ";
  writeSelectedArtifact(out, selection.artifact, selection.mode,
                        std::string(indent) + "  ");
  out << "\n" << indent << "}";
}

void writeTargetLegalizationEvidenceSummary(std::ostream &out,
                                            const PackageMetadata &metadata,
                                            std::string_view indent) {
  out << "{\n"
      << indent << "  \"toolRequirementsPresent\": "
      << (metadata.targetLegalizationToolRequirements ? "true" : "false")
      << ",\n"
      << indent << "  \"target\": ";
  if (metadata.targetLegalizationToolRequirements) {
    out << "\""
        << escapeJson(metadata.targetLegalizationToolRequirements->target)
        << "\"";
  } else {
    out << "null";
  }
  out << ",\n" << indent << "  \"packageMode\": ";
  if (metadata.targetLegalizationToolRequirements) {
    out << "\""
        << escapeJson(metadata.targetLegalizationToolRequirements->packageMode)
        << "\"";
  } else {
    out << "null";
  }
  out << ",\n" << indent << "  \"requiredToolCount\": "
      << (metadata.targetLegalizationToolRequirements
              ? metadata.targetLegalizationToolRequirements->requiredToolCount
              : 0)
      << ",\n"
      << indent << "  \"missingToolCount\": "
      << (metadata.targetLegalizationToolRequirements
              ? metadata.targetLegalizationToolRequirements->missingToolCount
              : 0)
      << ",\n"
      << indent << "  \"requiredToolIds\": ";
  if (metadata.targetLegalizationToolRequirements) {
    writeStringArray(
        out, metadata.targetLegalizationToolRequirements->requiredToolIds);
  } else {
    out << "[]";
  }
  out << ",\n" << indent << "  \"missingToolIds\": ";
  if (metadata.targetLegalizationToolRequirements) {
    writeStringArray(out,
                     metadata.targetLegalizationToolRequirements->missingToolIds);
  } else {
    out << "[]";
  }
  out << ",\n" << indent << "  \"toolRequirementEvidenceIds\": ";
  if (metadata.targetLegalizationToolRequirements) {
    writeStringArray(
        out,
        metadata.targetLegalizationToolRequirements->toolRequirementEvidenceIds);
  } else {
    out << "[]";
  }
  out << "\n" << indent << "}";
}

std::size_t selectedTargetBindingCount(const PackageMetadata &metadata,
                                       std::string_view target) {
  return std::count_if(metadata.reflectionTargetResourceBindings.begin(),
                       metadata.reflectionTargetResourceBindings.end(),
                       [&](const PackageReflectionTargetResourceBindingRecord
                               &binding) {
                         return binding.target == target;
                       });
}

std::size_t selectedTargetFeatureCount(const PackageMetadata &metadata,
                                       std::string_view target) {
  return std::count_if(
      metadata.reflectionTargetFeatures.begin(),
      metadata.reflectionTargetFeatures.end(),
      [&](const PackageReflectionTargetFeatureRecord &feature) {
        return feature.target == target;
      });
}

void writeReflectionResourceRecord(
    std::ostream &out, const PackageReflectionResourceRecord &resource,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"stage\": \"" << escapeJson(resource.stage) << "\",\n"
      << indent << "  \"name\": \"" << escapeJson(resource.name) << "\",\n"
      << indent << "  \"kind\": \"" << escapeJson(resource.kind) << "\",\n"
      << indent << "  \"type\": \"" << escapeJson(resource.type) << "\",\n"
      << indent << "  \"storageImageFormat\": ";
  writeNullableString(out, resource.storageImageFormat);
  out << ",\n" << indent << "  \"storageImageAccess\": ";
  writeNullableString(out, resource.storageImageAccess);
  out << ",\n" << indent << "  \"arrayDimensions\": "
      << resource.arrayDimensionsJson << ",\n"
      << indent << "  \"arrayElementCount\": ";
  writeNullableUnsigned(out, resource.arrayElementCount);
  out << ",\n" << indent << "  \"set\": ";
  writeNullableUnsigned(out, resource.set);
  out << ",\n" << indent << "  \"binding\": ";
  writeNullableUnsigned(out, resource.binding);
  out << "\n" << indent << "}";
}

void writeReflectionResourceRecords(
    std::ostream &out,
    const std::vector<PackageReflectionResourceRecord> &resources,
    std::string_view indent) {
  out << "[";
  for (std::size_t index = 0; index < resources.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeReflectionResourceRecord(out, resources[index],
                                  std::string(indent) + "  ");
  }
  if (!resources.empty()) {
    out << "\n" << indent;
  }
  out << "]";
}

void writeReflectionInputTargetBindingRecord(
    std::ostream &out,
    const PackageReflectionTargetResourceBindingRecord &binding,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"target\": \"" << escapeJson(binding.target) << "\",\n"
      << indent << "  \"stage\": \"" << escapeJson(binding.stage) << "\",\n"
      << indent << "  \"entryPoint\": \"" << escapeJson(binding.entryPoint)
      << "\",\n"
      << indent << "  \"name\": \"" << escapeJson(binding.name) << "\",\n"
      << indent << "  \"kind\": \"" << escapeJson(binding.kind) << "\",\n"
      << indent << "  \"bindingClass\": ";
  writeNullableString(out, binding.bindingClass);
  out << ",\n" << indent << "  \"descriptorType\": ";
  writeNullableString(out, binding.descriptorType);
  out << ",\n" << indent << "  \"set\": ";
  writeNullableUnsigned(out, binding.set);
  out << ",\n" << indent << "  \"binding\": ";
  writeNullableUnsigned(out, binding.binding);
  out << ",\n" << indent << "  \"argumentIndex\": ";
  writeNullableUnsigned(out, binding.argumentIndex);
  out << ",\n" << indent << "  \"storageImageFormat\": ";
  writeNullableString(out, binding.storageImageFormat);
  out << ",\n" << indent << "  \"storageImageAccess\": ";
  writeNullableString(out, binding.storageImageAccess);
  out << ",\n" << indent << "  \"arrayDimensions\": "
      << binding.arrayDimensionsJson << ",\n"
      << indent << "  \"arrayElementCount\": ";
  writeNullableUnsigned(out, binding.arrayElementCount);
  out << ",\n" << indent << "  \"abi\": " << binding.abiJson;
  if (binding.evidenceId) {
    out << ",\n" << indent << "  \"evidenceId\": \""
        << escapeJson(*binding.evidenceId) << "\"";
  }
  out << "\n" << indent << "}";
}

void writeSelectedTargetBindingRecords(
    std::ostream &out,
    const std::vector<PackageReflectionTargetResourceBindingRecord> &bindings,
    std::string_view target, std::string_view indent) {
  out << "[";
  std::size_t emitted = 0;
  for (const PackageReflectionTargetResourceBindingRecord &binding : bindings) {
    if (binding.target != target) {
      continue;
    }
    out << (emitted == 0 ? "\n" : ",\n");
    writeReflectionInputTargetBindingRecord(out, binding,
                                            std::string(indent) + "  ");
    ++emitted;
  }
  if (emitted != 0) {
    out << "\n" << indent;
  }
  out << "]";
}

void writeSelectedTargetFeatures(
    std::ostream &out,
    const std::vector<PackageReflectionTargetFeatureRecord> &features,
    std::string_view target, std::string_view indent) {
  out << "[";
  std::size_t emitted = 0;
  for (const PackageReflectionTargetFeatureRecord &feature : features) {
    if (feature.target != target) {
      continue;
    }
    out << (emitted == 0 ? "\n" : ",\n")
        << std::string(indent) + "  " << "{\n"
        << std::string(indent) + "  " << "  \"target\": \""
        << escapeJson(feature.target) << "\",\n"
        << std::string(indent) + "  " << "  \"kind\": \""
        << escapeJson(feature.kind) << "\",\n"
        << std::string(indent) + "  " << "  \"name\": \""
        << escapeJson(feature.name) << "\",\n"
        << std::string(indent) + "  " << "  \"evidenceIds\": ";
    writeStringArray(out, feature.evidenceIds);
    out << "\n" << std::string(indent) + "  " << "}";
    ++emitted;
  }
  if (emitted != 0) {
    out << "\n" << indent;
  }
  out << "]";
}

void writeTargetResourceBindingMetadataRecord(
    std::ostream &out,
    const PackageReflectionTargetResourceBindingRecord &binding,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"target\": \"" << escapeJson(binding.target) << "\",\n"
      << indent << "  \"stage\": \"" << escapeJson(binding.stage) << "\",\n"
      << indent << "  \"entryPoint\": \"" << escapeJson(binding.entryPoint)
      << "\",\n"
      << indent << "  \"name\": \"" << escapeJson(binding.name) << "\",\n"
      << indent << "  \"kind\": \"" << escapeJson(binding.kind) << "\",\n"
      << indent << "  \"bindingClass\": ";
  writeNullableString(out, binding.bindingClass);
  out << ",\n" << indent << "  \"descriptorType\": ";
  writeNullableString(out, binding.descriptorType);
  out << ",\n" << indent << "  \"set\": ";
  writeNullableUnsigned(out, binding.set);
  out << ",\n" << indent << "  \"binding\": ";
  writeNullableUnsigned(out, binding.binding);
  out << ",\n" << indent << "  \"argumentIndex\": ";
  writeNullableUnsigned(out, binding.argumentIndex);
  out << ",\n" << indent << "  \"abi\": " << binding.abiJson << ",\n"
      << indent << "  \"identity\": {\n"
      << indent << "    \"target\": \"" << escapeJson(binding.target) << "\",\n"
      << indent << "    \"stage\": \"" << escapeJson(binding.stage) << "\",\n"
      << indent << "    \"entryPoint\": \"" << escapeJson(binding.entryPoint)
      << "\",\n"
      << indent << "    \"name\": \"" << escapeJson(binding.name) << "\",\n"
      << indent << "    \"kind\": \"" << escapeJson(binding.kind) << "\"\n"
      << indent << "  }";
  if (binding.evidenceId) {
    out << ",\n" << indent << "  \"evidenceId\": \""
        << escapeJson(*binding.evidenceId) << "\"";
  }
  out << ",\n" << indent << "  \"arrayDimensions\": "
      << binding.arrayDimensionsJson << ",\n"
      << indent << "  \"arrayElementCount\": ";
  writeNullableUnsigned(out, binding.arrayElementCount);
  out << ",\n" << indent << "  \"storageImageFormat\": ";
  writeNullableString(out, binding.storageImageFormat);
  out << ",\n" << indent << "  \"storageImageAccess\": ";
  writeNullableString(out, binding.storageImageAccess);
  out << "\n" << indent << "}";
}

void writeTargetResourceBindingMetadataRecords(
    std::ostream &out,
    const std::vector<PackageReflectionTargetResourceBindingRecord> &bindings,
    std::string_view target, std::string_view indent) {
  out << "[";
  std::size_t emitted = 0;
  for (const PackageReflectionTargetResourceBindingRecord &binding : bindings) {
    if (binding.target != target) {
      continue;
    }
    out << (emitted == 0 ? "\n" : ",\n");
    writeTargetResourceBindingMetadataRecord(out, binding,
                                             std::string(indent) + "  ");
    ++emitted;
  }
  if (emitted != 0) {
    out << "\n" << indent;
  }
  out << "]";
}

std::string loaderReflectionTarget(const PackageMetadata &metadata,
                                   const std::string *requestedLoaderTarget) {
  if (requestedLoaderTarget != nullptr) {
    return *requestedLoaderTarget;
  }
  return metadata.target;
}

void writeReflectionSummary(std::ostream &out, const PackageMetadata &metadata,
                            std::string_view target, std::string_view indent) {
  const std::optional<std::size_t> workgroupSizeCount =
      jsonArraySize(metadata.documents.reflection, "workgroupSizes");
  const std::optional<std::size_t> functionConstantCount =
      jsonArraySize(metadata.documents.reflection, "functionConstants");
  const std::size_t specializationConstantCount =
      jsonArrayObjectMemberCount(metadata.documents.reflection,
                                 "functionConstants", "specializationId");
  const std::optional<std::size_t> entryPointCount =
      jsonArraySize(metadata.documents.reflection, "entryPoints");
  out << "{\n"
      << indent << "  \"resourceCount\": "
      << metadata.reflectionResources.size() << ",\n"
      << indent << "  \"targetResourceBindingCount\": "
      << selectedTargetBindingCount(metadata, target) << ",\n"
      << indent << "  \"targetFeatureCount\": "
      << selectedTargetFeatureCount(metadata, target) << ",\n"
      << indent << "  \"entryPointCount\": ";
  if (entryPointCount) {
    out << *entryPointCount;
  } else {
    out << "null";
  }
  out << ",\n" << indent << "  \"workgroupSizeCount\": ";
  if (workgroupSizeCount) {
    out << *workgroupSizeCount;
  } else {
    out << "null";
  }
  out << ",\n" << indent << "  \"functionConstantCount\": ";
  if (functionConstantCount) {
    out << *functionConstantCount;
  } else {
    out << "null";
  }
  out << ",\n" << indent << "  \"specializationConstantCount\": ";
  if (functionConstantCount) {
    out << specializationConstantCount;
  } else {
    out << "null";
  }
  out << ",\n"
      << indent << "  \"threadgroupShapeSource\": \"reflection.workgroupSizes\""
      << "\n"
      << indent << "}";
}

void writeReflectionInputs(std::ostream &out, const PackageMetadata &metadata,
                           const std::optional<std::string> &selectedTarget,
                           std::string_view filterTarget,
                           std::string_view indent) {
  const std::optional<std::size_t> workgroupSizeCount =
      jsonArraySize(metadata.documents.reflection, "workgroupSizes");
  const std::optional<std::size_t> functionConstantCount =
      jsonArraySize(metadata.documents.reflection, "functionConstants");
  const std::size_t specializationConstantCount =
      jsonArrayObjectMemberCount(metadata.documents.reflection,
                                 "functionConstants", "specializationId");
  const std::optional<std::size_t> entryPointCount =
      jsonArraySize(metadata.documents.reflection, "entryPoints");
  const std::size_t targetBindingCount =
      selectedTargetBindingCount(metadata, filterTarget);
  const std::size_t targetFeatureCount =
      selectedTargetFeatureCount(metadata, filterTarget);

  out << "{\n"
      << indent << "  \"schemaVersion\": 1,\n"
      << indent << "  \"selectedTarget\": ";
  writeNullableString(out, selectedTarget);
  out << ",\n"
      << indent << "  \"entryPointCount\": " << entryPointCount.value_or(0)
      << ",\n"
      << indent << "  \"resourceCount\": "
      << metadata.reflectionResources.size() << ",\n"
      << indent << "  \"targetResourceBindingCount\": " << targetBindingCount
      << ",\n"
      << indent << "  \"targetFeatureCount\": " << targetFeatureCount << ",\n"
      << indent << "  \"workgroupSizeCount\": "
      << workgroupSizeCount.value_or(0) << ",\n"
      << indent << "  \"functionConstantCount\": "
      << functionConstantCount.value_or(0) << ",\n"
      << indent << "  \"specializationConstantCount\": "
      << specializationConstantCount << ",\n"
      << indent << "  \"workgroupSizesAvailable\": "
      << (workgroupSizeCount.value_or(0) != 0 ? "true" : "false") << ",\n"
      << indent << "  \"functionConstantsAvailable\": "
      << (functionConstantCount.value_or(0) != 0 ? "true" : "false")
      << ",\n"
      << indent << "  \"skippedTargetResourceBindingCount\": "
      << (metadata.reflectionTargetResourceBindings.size() - targetBindingCount)
      << ",\n"
      << indent << "  \"skippedTargetFeatureCount\": "
      << (metadata.reflectionTargetFeatures.size() - targetFeatureCount)
      << ",\n"
      << indent << "  \"entryPoints\": ";
  writeJsonArrayMemberOrEmpty(out, metadata.documents.reflection, "entryPoints");
  out << ",\n" << indent << "  \"resources\": ";
  writeReflectionResourceRecords(out, metadata.reflectionResources,
                                 std::string(indent) + "  ");
  out << ",\n" << indent << "  \"targetResourceBindings\": ";
  writeSelectedTargetBindingRecords(
      out, metadata.reflectionTargetResourceBindings, filterTarget,
      std::string(indent) + "  ");
  out << ",\n" << indent << "  \"targetFeatures\": ";
  writeSelectedTargetFeatures(out, metadata.reflectionTargetFeatures,
                              filterTarget, std::string(indent) + "  ");
  out << ",\n" << indent << "  \"workgroupSizes\": ";
  writeJsonArrayMemberOrEmpty(out, metadata.documents.reflection,
                              "workgroupSizes");
  out << ",\n" << indent << "  \"functionConstants\": ";
  writeJsonArrayMemberOrEmpty(out, metadata.documents.reflection,
                              "functionConstants");
  out << "\n" << indent << "}";
}

void writeTargetResourceBindingMetadata(
    std::ostream &out, const PackageMetadata &metadata,
    const std::string *requestedLoaderTarget,
    const std::optional<std::string> &selectedTarget, std::string_view indent) {
  const std::string filterTarget =
      loaderReflectionTarget(metadata, requestedLoaderTarget);
  const std::size_t bindingCount =
      selectedTargetBindingCount(metadata, filterTarget);

  out << "{\n"
      << indent << "  \"schemaVersion\": 1,\n"
      << indent << "  \"selectedTarget\": ";
  writeNullableString(out, selectedTarget);
  out << ",\n" << indent << "  \"loaderTarget\": ";
  writeNullableString(out, requestedLoaderTarget);
  out << ",\n"
      << indent << "  \"packageTarget\": \"" << escapeJson(metadata.target)
      << "\",\n"
      << indent << "  \"bindingCount\": " << bindingCount << ",\n"
      << indent << "  \"skippedBindingCount\": "
      << (metadata.reflectionTargetResourceBindings.size() - bindingCount)
      << ",\n"
      << indent << "  \"bindings\": ";
  writeTargetResourceBindingMetadataRecords(
      out, metadata.reflectionTargetResourceBindings, filterTarget,
      std::string(indent) + "  ");
  out << "\n" << indent << "}";
}

std::string_view artifactFormatForHostLoader(
    const PackageArtifactRecord *artifact) {
  if (artifact == nullptr) {
    return "unknown";
  }
  if (artifact->name == kNativeBinaryArtifact) {
    return "native-binary";
  }
  if (artifact->name == kBackendSourceArtifact) {
    return "backend-source";
  }
  return artifact->name;
}

std::string_view adapterKindForHostLoader(const PackageArtifactRecord &artifact) {
  if (artifact.name == kNativeBinaryArtifact) {
    return "native-binary-loader";
  }
  return "backend-source-loader";
}

bool jsonValueHasKind(std::string_view value, char kind) {
  std::size_t position = 0;
  skipWhitespace(value, position);
  return position < value.size() && value[position] == kind;
}

std::string rawObjectMemberOr(std::string_view object, std::string_view key,
                              std::string_view fallback) {
  const std::optional<std::string_view> value = findObjectMemberValue(object, key);
  if (value && jsonValueHasKind(*value, '{')) {
    return std::string(*value);
  }
  return std::string(fallback);
}

std::vector<std::string_view> jsonArrayValues(std::string_view arrayText) {
  std::vector<std::string_view> values;
  std::size_t position = 0;
  skipWhitespace(arrayText, position);
  if (position >= arrayText.size() || arrayText[position] != '[') {
    return values;
  }
  ++position;
  while (position < arrayText.size()) {
    skipWhitespace(arrayText, position);
    if (position < arrayText.size() && arrayText[position] == ']') {
      break;
    }
    const std::size_t valueBegin = position;
    if (!skipJsonValue(arrayText, position)) {
      values.clear();
      return values;
    }
    values.emplace_back(arrayText.data() + valueBegin, position - valueBegin);
    skipWhitespace(arrayText, position);
    if (position < arrayText.size() && arrayText[position] == ',') {
      ++position;
      continue;
    }
    if (position < arrayText.size() && arrayText[position] == ']') {
      break;
    }
  }
  return values;
}

std::vector<std::string> jsonStringArrayValues(std::string_view arrayText) {
  std::vector<std::string> values;
  for (std::string_view value : jsonArrayValues(arrayText)) {
    std::size_t position = 0;
    std::string parsed;
    if (parseJsonString(value, position, parsed)) {
      skipWhitespace(value, position);
      if (position == value.size()) {
        values.push_back(std::move(parsed));
      }
    }
  }
  return values;
}

std::vector<std::string> objectStringArrayMember(std::string_view object,
                                                 std::string_view key) {
  const std::optional<std::string_view> array = findObjectMemberValue(object, key);
  if (!array || !jsonValueHasKind(*array, '[')) {
    return {};
  }
  return jsonStringArrayValues(*array);
}

std::optional<std::string>
stringMemberFromRecordOrDocument(std::string_view record,
                                 std::string_view document,
                                 std::string_view key) {
  std::optional<std::string> value = objectStringMember(record, key);
  if (value && !value->empty()) {
    return value;
  }
  value = objectStringMember(document, key);
  if (value && !value->empty()) {
    return value;
  }
  return std::nullopt;
}

std::string normalizeArtifactFormatAlias(std::string_view value) {
  std::string normalized;
  bool pendingSpace = false;
  for (const char ch : value) {
    if (std::isspace(static_cast<unsigned char>(ch))) {
      pendingSpace = !normalized.empty();
      continue;
    }
    if (pendingSpace) {
      normalized.push_back(' ');
      pendingSpace = false;
    }
    normalized.push_back(static_cast<char>(
        std::tolower(static_cast<unsigned char>(ch))));
  }
  return normalized;
}

std::optional<std::string>
compilerArtifactFormat(std::string_view producerArtifactFormat) {
  const std::string normalized =
      normalizeArtifactFormatAlias(producerArtifactFormat);
  if (normalized == "backend-source" || normalized == "glsl source" ||
      normalized == "glsl-source" || normalized == "hlsl source" ||
      normalized == "hlsl-source" || normalized == "metal source" ||
      normalized == "msl source" || normalized == "msl-source" ||
      normalized == "spir-v source" || normalized == "spirv source" ||
      normalized == "vulkan-targeted shader source" ||
      normalized == "wgsl source" || normalized == "wgsl-source") {
    return std::string("backend-source");
  }
  if (normalized == "dxbc" || normalized == "dxil" ||
      normalized == "dxil binary" || normalized == "metallib" ||
      normalized == "metallib binary" || normalized == "native-binary" ||
      normalized == "spir-v" || normalized == "spir-v binary" ||
      normalized == "spir-v module" || normalized == "spirv" ||
      normalized == "spirv binary" || normalized == "spirv module") {
    return std::string("native-binary");
  }
  return std::nullopt;
}

std::string runtimeLoaderMemberName(std::string_view value) {
  std::vector<std::string> parts;
  std::string current;
  for (const char ch : value) {
    if (std::isalnum(static_cast<unsigned char>(ch))) {
      current.push_back(ch);
    } else if (!current.empty()) {
      parts.push_back(std::move(current));
      current.clear();
    }
  }
  if (!current.empty()) {
    parts.push_back(std::move(current));
  }

  std::string member;
  for (std::string &part : parts) {
    part.front() =
        static_cast<char>(std::toupper(static_cast<unsigned char>(part.front())));
    member += part;
  }
  if (member.empty()) {
    return "Adapter";
  }
  if (!std::isalpha(static_cast<unsigned char>(member.front()))) {
    member.insert(0, "Adapter");
  }
  return member;
}

std::optional<std::string>
readJsonObjectFile(const std::filesystem::path &path) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return std::nullopt;
  }
  std::ostringstream contents;
  contents << input.rdbuf();
  std::string text = contents.str();
  if (!isJsonObjectDocument(text)) {
    return std::nullopt;
  }
  return text;
}

std::optional<std::filesystem::path>
findCrossTLRuntimeAdapterManifest(const std::filesystem::path &packagePath) {
  std::error_code error;
  if (!std::filesystem::is_directory(packagePath, error) || error) {
    return std::nullopt;
  }

  const std::filesystem::path rootManifest =
      packagePath / "runtime-adapters.json";
  if (std::filesystem::is_regular_file(rootManifest, error) && !error) {
    return rootManifest;
  }
  error.clear();

  const std::filesystem::path nestedManifest =
      packagePath / "runtime-adapters" / "runtime-adapters.json";
  if (std::filesystem::is_regular_file(nestedManifest, error) && !error) {
    return nestedManifest;
  }
  error.clear();

  std::vector<std::filesystem::path> discovered;
  std::filesystem::recursive_directory_iterator iterator(
      packagePath, std::filesystem::directory_options::skip_permission_denied,
      error);
  const std::filesystem::recursive_directory_iterator end;
  while (!error && iterator != end) {
    const std::filesystem::path candidate = iterator->path();
    if (candidate.filename() == "runtime-adapters.json" &&
        std::filesystem::is_regular_file(candidate, error) && !error) {
      discovered.push_back(candidate);
    }
    iterator.increment(error);
  }
  if (discovered.empty()) {
    return std::nullopt;
  }
  std::sort(discovered.begin(), discovered.end(),
            [](const std::filesystem::path &lhs,
               const std::filesystem::path &rhs) {
              return lhs.generic_string() < rhs.generic_string();
            });
  return discovered.front();
}

std::optional<std::string>
sourceRemapPackagePath(std::string_view sourceRemapJson) {
  if (!jsonValueHasKind(sourceRemapJson, '{')) {
    return std::nullopt;
  }
  std::optional<std::string> path =
      objectStringMember(sourceRemapJson, "packagePath");
  if (path && !path->empty()) {
    return path;
  }
  path = objectStringMember(sourceRemapJson, "path");
  if (path && !path->empty()) {
    return path;
  }
  return std::nullopt;
}

struct CrossTLRuntimeAdapterLoadUnit {
  std::string id;
  std::string target;
  std::string adapterKind;
  std::string artifactFormat;
  std::string packagePath;
  std::optional<std::string> sourcePath;
  std::optional<std::string> sourceBackend;
  std::optional<std::string> stage;
  std::optional<std::string> variant;
  std::string definesJson = "{}";
  std::string sourceRemapJson = "null";
  std::string hostInterfaceJson = "null";
  std::vector<std::string> requiredTools;
  std::vector<std::string> hostResponsibilities;
  std::string hostInterfaceStatus = "not-inspected";
  std::string artifactName;
  std::string producerAdapterKind;
  std::string producerArtifactFormat;
  bool candidateLoadReady = false;
  bool validationLoadReady = false;
  std::optional<std::string> sourceRemapPackagePath;
  std::size_t entryPointCount = 0;
  std::size_t resourceCount = 0;
  std::size_t constantCount = 0;
};

std::optional<CrossTLRuntimeAdapterLoadUnit>
crossTLRuntimeAdapterLoadUnitFromDescriptor(std::string_view record,
                                            std::string_view document) {
  const std::optional<std::string> target =
      stringMemberFromRecordOrDocument(record, document, "target");
  const std::optional<std::string> packagePath =
      stringMemberFromRecordOrDocument(record, document, "packagePath");
  const std::optional<std::string> producerAdapterKind =
      stringMemberFromRecordOrDocument(record, document, "adapterKind");
  const std::optional<std::string> producerArtifactFormat =
      stringMemberFromRecordOrDocument(record, document, "artifactFormat");
  if (!target || !isKnownPackageTarget(*target) || !packagePath ||
      !isPackageRelativePath(*packagePath) || !producerAdapterKind ||
      !producerArtifactFormat) {
    return std::nullopt;
  }

  const std::optional<std::string> artifactFormat =
      compilerArtifactFormat(*producerArtifactFormat);
  if (!artifactFormat) {
    return std::nullopt;
  }

  CrossTLRuntimeAdapterLoadUnit unit;
  unit.target = *target;
  unit.adapterKind =
      *artifactFormat == "native-binary" ? "native-binary-loader"
                                         : "backend-source-loader";
  unit.artifactName =
      *artifactFormat == "native-binary" ? std::string(kNativeBinaryArtifact)
                                         : std::string(kBackendSourceArtifact);
  unit.artifactFormat = *artifactFormat;
  unit.packagePath = *packagePath;
  unit.producerAdapterKind = *producerAdapterKind;
  unit.producerArtifactFormat = *producerArtifactFormat;

  const std::optional<std::string> descriptorId =
      stringMemberFromRecordOrDocument(record, document, "id");
  const std::string idSeed =
      descriptorId ? *descriptorId
                   : (packagePath ? *packagePath
                                  : objectStringMember(record, "descriptorPath")
                                        .value_or("adapter"));
  unit.id = "runtime-loader." + unit.target + "." +
            runtimeLoaderMemberName(idSeed);

  unit.sourcePath = stringMemberFromRecordOrDocument(record, document,
                                                     "sourcePath");
  unit.sourceBackend =
      stringMemberFromRecordOrDocument(record, document, "sourceBackend");
  unit.stage = stringMemberFromRecordOrDocument(record, document, "stage");
  unit.variant = stringMemberFromRecordOrDocument(record, document, "variant");
  unit.definesJson = rawObjectMemberOr(document, "defines", "{}");
  unit.sourceRemapJson = rawObjectMemberOr(document, "sourceRemap", "null");
  unit.hostInterfaceJson = rawObjectMemberOr(document, "hostInterface", "null");
  unit.sourceRemapPackagePath =
      sourceRemapPackagePath(unit.sourceRemapJson);

  unit.requiredTools = objectStringArrayMember(record, "requiredTools");
  if (unit.requiredTools.empty()) {
    unit.requiredTools = objectStringArrayMember(document, "requiredTools");
  }
  unit.hostResponsibilities =
      objectStringArrayMember(document, "hostResponsibilities");

  if (jsonValueHasKind(unit.hostInterfaceJson, '{')) {
    unit.hostInterfaceStatus =
        objectStringMember(unit.hostInterfaceJson, "status")
            .value_or(unit.hostInterfaceStatus);
    unit.entryPointCount =
        jsonArraySize(unit.hostInterfaceJson, "entryPoints").value_or(0);
    unit.resourceCount =
        jsonArraySize(unit.hostInterfaceJson, "resources").value_or(0);
    unit.constantCount =
        jsonArraySize(unit.hostInterfaceJson, "constants").value_or(0);
  }
  if (unit.hostInterfaceStatus == "not-inspected") {
    unit.hostInterfaceStatus =
        stringMemberFromRecordOrDocument(record, document, "hostInterfaceStatus")
            .value_or(unit.hostInterfaceStatus);
  }

  const std::string validationJson =
      rawObjectMemberOr(document, "validation", "{}");
  const std::optional<bool> descriptorLoadReady =
      objectBoolMember(validationJson, "loadReady");
  const bool hostInterfaceReady = unit.hostInterfaceStatus == "ready";
  unit.candidateLoadReady =
      descriptorLoadReady ? (*descriptorLoadReady && hostInterfaceReady)
                          : hostInterfaceReady;
  unit.validationLoadReady =
      hostInterfaceReady && unit.candidateLoadReady;
  return unit;
}

std::vector<CrossTLRuntimeAdapterLoadUnit>
readCrossTLRuntimeAdapterLoadUnits(const PackageMetadata *metadata,
                                   const Selection &selection,
                                   const std::optional<std::string>
                                       &selectedTarget) {
  if (metadata == nullptr || metadata->packageFormat != "directory" ||
      selection.artifact == nullptr || !selectedTarget) {
    return {};
  }

  const std::string selectedArtifactFormat =
      std::string(artifactFormatForHostLoader(selection.artifact));
  if (selectedArtifactFormat != "backend-source" &&
      selectedArtifactFormat != "native-binary") {
    return {};
  }

  const std::optional<std::filesystem::path> manifestPath =
      findCrossTLRuntimeAdapterManifest(metadata->packagePath);
  if (!manifestPath) {
    return {};
  }
  const std::optional<std::string> manifest = readJsonObjectFile(*manifestPath);
  if (!manifest ||
      objectUnsignedMember(*manifest, "schemaVersion").value_or(0) != 1 ||
      objectStringMember(*manifest, "kind") !=
          "crosstl-runtime-adapter-package") {
    return {};
  }

  const std::optional<std::string_view> descriptors =
      findObjectMemberValue(*manifest, "descriptors");
  if (!descriptors || !jsonValueHasKind(*descriptors, '[')) {
    return {};
  }

  std::vector<CrossTLRuntimeAdapterLoadUnit> loadUnits;
  const std::filesystem::path descriptorRoot = manifestPath->parent_path();
  for (const std::string_view record : jsonArrayValues(*descriptors)) {
    if (!jsonValueHasKind(record, '{')) {
      continue;
    }
    const std::optional<std::string> descriptorPath =
        objectStringMember(record, "descriptorPath");
    if (!descriptorPath || !isPackageRelativePath(*descriptorPath)) {
      continue;
    }
    const std::optional<std::string> descriptor =
        readJsonObjectFile(descriptorRoot / *descriptorPath);
    if (!descriptor ||
        objectStringMember(*descriptor, "kind") !=
            "crosstl-runtime-adapter-descriptor") {
      continue;
    }
    std::optional<CrossTLRuntimeAdapterLoadUnit> unit =
        crossTLRuntimeAdapterLoadUnitFromDescriptor(record, *descriptor);
    if (!unit || unit->target != *selectedTarget ||
        unit->packagePath != selection.artifact->path ||
        unit->artifactFormat != selectedArtifactFormat) {
      continue;
    }
    loadUnits.push_back(std::move(*unit));
  }

  std::sort(loadUnits.begin(), loadUnits.end(),
            [](const CrossTLRuntimeAdapterLoadUnit &lhs,
               const CrossTLRuntimeAdapterLoadUnit &rhs) {
              if (lhs.target != rhs.target) {
                return lhs.target < rhs.target;
              }
              if (lhs.packagePath != rhs.packagePath) {
                return lhs.packagePath < rhs.packagePath;
              }
              return lhs.id < rhs.id;
            });
  return loadUnits;
}

void writeHostLoaderLoadStepMetadataSource(std::ostream &out,
                                           std::string_view field,
                                           const std::string *path,
                                           std::string_view indent) {
  out << "{\n" << indent << "  \"field\": \"" << escapeJson(field) << "\"";
  if (path != nullptr) {
    out << ",\n" << indent << "  \"path\": \"" << escapeJson(*path) << "\"";
  }
  out << "\n" << indent << "}";
}

const PackageArtifactRecord *
findExistingArtifact(const PackageMetadata *metadata, std::string_view name) {
  if (metadata == nullptr) {
    return nullptr;
  }
  const PackageArtifactRecord *artifact = findArtifact(*metadata, name);
  if (artifact == nullptr || !artifact->exists) {
    return nullptr;
  }
  return artifact;
}

std::vector<std::string>
hostLoaderRequiredTools(const PackageMetadata *metadata) {
  if (metadata == nullptr || !metadata->targetLegalizationToolRequirements) {
    return {};
  }
  return metadata->targetLegalizationToolRequirements->requiredToolIds;
}

std::vector<std::string>
hostLoaderResponsibilities(const PackageArtifactRecord *sourceRemapArtifact,
                           const PackageArtifactRecord *backendSourceMapArtifact,
                           const std::vector<std::string> &requiredTools,
                           std::size_t workgroupSizeCount) {
  std::vector<std::string> responsibilities = {
      "load-package-artifact",
      "bind-reflected-entry-points",
      "bind-reflected-resources",
  };
  auto sidecarInsert = responsibilities.begin() + 1;
  if (sourceRemapArtifact != nullptr) {
    sidecarInsert =
        responsibilities.insert(sidecarInsert, "load-source-remap") + 1;
  }
  if (backendSourceMapArtifact != nullptr) {
    responsibilities.insert(sidecarInsert, "load-backend-source-map");
  }
  if (workgroupSizeCount > 0) {
    responsibilities.push_back("bind-workgroup-shape");
  }
  if (!requiredTools.empty()) {
    responsibilities.push_back("review-target-tool-requirements");
  }
  return responsibilities;
}

void writeHostLoaderManifestArtifactReference(
    std::ostream &out, const PackageArtifactRecord *artifact,
    std::string_view manifestSource,
    const PackageSourceRemapProvenanceHealth *sourceRemapHealth,
    const PackageBackendSourceMapHealth *backendSourceMapHealth,
    std::string_view indent) {
  if (artifact == nullptr) {
    out << "null";
    return;
  }
  out << "{\n"
      << indent << "  \"source\": \"" << escapeJson(manifestSource) << "\",\n"
      << indent << "  \"packagePath\": \"" << escapeJson(artifact->path)
      << "\",\n"
      << indent << "  \"exists\": true,\n"
      << indent << "  \"provenance\": ";
  if (sourceRemapHealth != nullptr) {
    writeSourceRemapProvenanceSummary(out, *sourceRemapHealth,
                                      std::string(indent) + "  ");
  } else if (backendSourceMapHealth != nullptr) {
    writeBackendSourceMapProvenanceSummary(out, *backendSourceMapHealth,
                                           std::string(indent) + "  ");
  } else {
    out << "null";
  }
  out << "\n"
      << indent << "}";
}

void writeHostLoaderLoadStepHeader(
    std::ostream &out, std::string_view kind, std::string_view message,
    const std::optional<std::string> &selectedTarget,
    std::string_view packagePath, bool hostInterfaceReady,
    std::string_view indent) {
  out << indent << "  {\n"
      << indent << "    \"kind\": \"" << escapeJson(kind) << "\",\n"
      << indent << "    \"message\": \"" << escapeJson(message) << "\",\n"
      << indent << "    \"target\": ";
  writeNullableString(out, selectedTarget);
  out << ",\n"
      << indent << "    \"packagePath\": \"" << escapeJson(packagePath)
      << "\",\n"
      << indent << "    \"hostInterfaceStatus\": \""
      << (hostInterfaceReady ? "ready" : "unavailable") << "\",\n"
      << indent << "    \"command\": null,\n"
      << indent << "    \"tools\": [],\n";
}

void writeHostLoaderLoadSteps(std::ostream &out,
                              const PackageArtifactRecord &artifact,
                              const PackageArtifactRecord *sourceRemapArtifact,
                              const PackageArtifactRecord *backendSourceMapArtifact,
                              const PackageDebugArtifactHealth *debugArtifacts,
                              const std::optional<std::string> &mode,
                              const std::optional<std::string> &selectedTarget,
                              bool hostInterfaceReady,
                              std::size_t entryPointCount,
                              std::size_t resourceBindingCount,
                              std::size_t workgroupSizeCount,
                              std::size_t functionConstantCount,
                              std::size_t specializationConstantCount,
                              std::string_view indent) {
  out << "[\n";
  writeHostLoaderLoadStepHeader(
      out, "load-package-artifact",
      "Load the selected runtime package artifact.", selectedTarget,
      artifact.path, hostInterfaceReady, indent);
  out << indent << "    \"metadata\": {\n"
      << indent << "      \"source\": ";
  writeHostLoaderLoadStepMetadataSource(out, "selectedArtifact.path",
                                        &artifact.path,
                                        std::string(indent) + "      ");
  out << ",\n"
      << indent << "      \"artifact\": {\n"
      << indent << "        \"name\": \"" << escapeJson(artifact.name)
      << "\",\n"
      << indent << "        \"packageMode\": ";
  writeNullableString(out, mode);
  out << ",\n"
      << indent << "        \"artifactFormat\": \""
      << escapeJson(artifactFormatForHostLoader(&artifact)) << "\"\n"
      << indent << "      }\n"
      << indent << "    }\n"
      << indent << "  }";

  if (sourceRemapArtifact != nullptr) {
    out << ",\n";
    writeHostLoaderLoadStepHeader(
        out, "load-source-remap",
        "Load source remap provenance for diagnostics.", selectedTarget,
        sourceRemapArtifact->path, hostInterfaceReady, indent);
    out << indent << "    \"metadata\": {\n"
        << indent << "      \"source\": ";
    writeHostLoaderLoadStepMetadataSource(
        out, "manifest.artifacts.sourceRemap", &sourceRemapArtifact->path,
        std::string(indent) + "      ");
    out << ",\n" << indent << "      \"provenance\": ";
    const PackageSourceRemapProvenanceHealth *health =
        debugArtifacts != nullptr ? &debugArtifacts->sourceRemap : nullptr;
    writeHostLoaderLoadStepProvenancePointer(
        out, "loadUnit.sourceRemap.provenance",
        health != nullptr && sourceRemapProvenanceAvailable(*health),
        health != nullptr ? health->health : "not-present",
        std::string(indent) + "      ");
    out << "\n" << indent << "    }\n" << indent << "  }";
  }

  if (backendSourceMapArtifact != nullptr) {
    out << ",\n";
    writeHostLoaderLoadStepHeader(
        out, "load-backend-source-map",
        "Load backend source map metadata for diagnostics.", selectedTarget,
        backendSourceMapArtifact->path, hostInterfaceReady, indent);
    out << indent << "    \"metadata\": {\n"
        << indent << "      \"source\": ";
    writeHostLoaderLoadStepMetadataSource(
        out, "manifest.artifacts.backendSourceMap",
        &backendSourceMapArtifact->path, std::string(indent) + "      ");
    out << ",\n" << indent << "      \"provenance\": ";
    const PackageBackendSourceMapHealth *health =
        debugArtifacts != nullptr ? &debugArtifacts->backendSourceMap : nullptr;
    writeHostLoaderLoadStepProvenancePointer(
        out, "loadUnit.backendSourceMap.provenance",
        health != nullptr && backendSourceMapProvenanceAvailable(*health),
        health != nullptr ? health->health : "not-present",
        std::string(indent) + "      ");
    out << "\n" << indent << "    }\n" << indent << "  }";
  }

  if (hostInterfaceReady) {
    out << ",\n";
    writeHostLoaderLoadStepHeader(
        out, "bind-host-interface", "Bind reflected host interface metadata.",
        selectedTarget, artifact.path, hostInterfaceReady, indent);
    out << indent << "    \"metadata\": {\n"
        << indent << "      \"source\": ";
    writeHostLoaderLoadStepMetadataSource(out, "reflectionInputs", nullptr,
                                          std::string(indent) + "      ");
    out << ",\n"
        << indent << "      \"entryPointCount\": " << entryPointCount << ",\n"
        << indent << "      \"resourceBindingCount\": " << resourceBindingCount
        << ",\n"
        << indent << "      \"workgroupSizeCount\": " << workgroupSizeCount
        << ",\n"
        << indent << "      \"functionConstantCount\": "
        << functionConstantCount << ",\n"
        << indent << "      \"specializationConstantCount\": "
        << specializationConstantCount
        << "\n"
        << indent << "    }\n"
        << indent << "  }";
  }

  out << "\n" << indent << "]";
}

void writeHostLoaderBlockers(std::ostream &out, bool hostInterfaceReady,
                             std::string_view indent) {
  if (hostInterfaceReady) {
    out << "[]";
    return;
  }
  out << "[\n"
      << indent << "  {\n"
      << indent << "    \"kind\": \"resolve-host-interface-metadata\",\n"
      << indent << "    \"severity\": \"warning\",\n"
      << indent << "    \"source\": \"reflectionInputs.entryPoints\",\n"
      << indent
      << "    \"message\": \"runtime loader plan requires reflection entry "
         "point metadata before host loader scaffolding\"\n"
      << indent << "  }\n"
      << indent << "]";
}

void writeHostLoaderLoadUnit(
    std::ostream &out, const PackageArtifactRecord &artifact,
    const PackageArtifactRecord *sourceRemapArtifact,
    const PackageArtifactRecord *backendSourceMapArtifact,
    const PackageDebugArtifactHealth *debugArtifacts,
    const std::optional<std::string> &mode,
    const std::optional<std::string> &selectedTarget,
    const std::vector<std::string> &requiredTools,
    bool hostInterfaceReady, std::size_t entryPointCount,
    std::size_t resourceBindingCount, std::size_t workgroupSizeCount,
    std::size_t functionConstantCount,
    std::size_t specializationConstantCount,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"id\": \"runtime-loader.";
  if (selectedTarget) {
    out << escapeJson(*selectedTarget);
  } else {
    out << "unselected";
  }
  out << "." << escapeJson(artifact.name) << "\",\n"
      << indent << "  \"target\": ";
  writeNullableString(out, selectedTarget);
  out << ",\n"
      << indent << "  \"packageMode\": ";
  writeNullableString(out, mode);
  out << ",\n"
      << indent << "  \"artifact\": ";
  writeSelectedArtifact(out, &artifact, mode, std::string(indent) + "  ");
  out << ",\n"
      << indent << "  \"packagePath\": \"" << escapeJson(artifact.path)
      << "\",\n"
      << indent << "  \"artifactFormat\": \""
      << escapeJson(artifactFormatForHostLoader(&artifact)) << "\",\n"
      << indent << "  \"adapterKind\": \""
      << escapeJson(adapterKindForHostLoader(artifact)) << "\",\n"
      << indent << "  \"status\": \""
      << (hostInterfaceReady ? "ready" : "blocked") << "\",\n"
      << indent << "  \"sourceRemap\": ";
  const PackageSourceRemapProvenanceHealth *sourceRemapHealth =
      debugArtifacts != nullptr ? &debugArtifacts->sourceRemap : nullptr;
  writeHostLoaderManifestArtifactReference(out, sourceRemapArtifact,
                                           "manifest.artifacts.sourceRemap",
                                           sourceRemapHealth, nullptr,
                                           std::string(indent) + "  ");
  out << ",\n"
      << indent << "  \"backendSourceMap\": ";
  const PackageBackendSourceMapHealth *backendSourceMapHealth =
      debugArtifacts != nullptr ? &debugArtifacts->backendSourceMap : nullptr;
  writeHostLoaderManifestArtifactReference(
      out, backendSourceMapArtifact, "manifest.artifacts.backendSourceMap",
      nullptr, backendSourceMapHealth, std::string(indent) + "  ");
  out << ",\n"
      << indent << "  \"requiredTools\": ";
  writeStringArray(out, requiredTools);
  out << ",\n"
      << indent << "  \"hostResponsibilities\": ";
  writeStringArray(out, hostLoaderResponsibilities(sourceRemapArtifact,
                                                   backendSourceMapArtifact,
                                                   requiredTools,
                                                   workgroupSizeCount));
  out << ",\n"
      << indent << "  \"hostInterface\": {\n"
      << indent << "    \"status\": \""
      << (hostInterfaceReady ? "ready" : "unavailable") << "\",\n"
      << indent << "    \"source\": \"reflectionInputs\",\n"
      << indent << "    \"entryPointCount\": " << entryPointCount << ",\n"
      << indent << "    \"resourceBindingCount\": " << resourceBindingCount
      << ",\n"
      << indent << "    \"workgroupSizeCount\": " << workgroupSizeCount
      << ",\n"
      << indent << "    \"functionConstantCount\": " << functionConstantCount
      << ",\n"
      << indent << "    \"specializationConstantCount\": "
      << specializationConstantCount
      << "\n"
      << indent << "  },\n"
      << indent << "  \"validation\": {\n"
      << indent << "    \"loadReady\": "
      << (hostInterfaceReady ? "true" : "false") << ",\n"
      << indent << "    \"metadataOnly\": true,\n"
      << indent << "    \"sourceParsingRequired\": false,\n"
      << indent << "    \"compilerInvocationRequired\": false,\n"
      << indent << "    \"deviceExecutionRequired\": false\n"
      << indent << "  },\n"
      << indent << "  \"loadSteps\": ";
  writeHostLoaderLoadSteps(out, artifact, sourceRemapArtifact,
                           backendSourceMapArtifact, debugArtifacts, mode,
                           selectedTarget, hostInterfaceReady, entryPointCount,
                           resourceBindingCount, workgroupSizeCount,
                           functionConstantCount, specializationConstantCount,
                           std::string(indent) + "  ");
  out << ",\n" << indent << "  \"blockers\": ";
  writeHostLoaderBlockers(out, hostInterfaceReady,
                          std::string(indent) + "  ");
  out << "\n" << indent << "}";
}

void writeHostLoaderIntegration(std::ostream &out, const PackageMetadata *metadata,
                                const Selection &selection,
                                const std::optional<std::string> &selectedTarget,
                                const std::optional<std::string> &filterTarget,
                                bool success, std::string_view indent) {
  const bool hasLoadUnit = metadata != nullptr && selection.artifact != nullptr;
  const std::size_t entryPointCount =
      metadata != nullptr
          ? jsonArraySize(metadata->documents.reflection, "entryPoints")
                .value_or(0)
          : 0;
  const std::size_t resourceBindingCount =
      metadata != nullptr && filterTarget
          ? selectedTargetBindingCount(*metadata, *filterTarget)
          : 0;
  const std::size_t workgroupSizeCount =
      metadata != nullptr
          ? jsonArraySize(metadata->documents.reflection, "workgroupSizes")
                .value_or(0)
          : 0;
  const std::size_t functionConstantCount =
      metadata != nullptr
          ? jsonArraySize(metadata->documents.reflection, "functionConstants")
                .value_or(0)
          : 0;
  const std::size_t specializationConstantCount =
      metadata != nullptr
          ? jsonArrayObjectMemberCount(metadata->documents.reflection,
                                       "functionConstants", "specializationId")
          : 0;
  const bool hostInterfaceReady =
      success && hasLoadUnit && entryPointCount != 0;
  const PackageArtifactRecord *sourceRemapArtifact =
      findExistingArtifact(metadata, kSourceRemapArtifact);
  const PackageArtifactRecord *backendSourceMapArtifact =
      findExistingArtifact(metadata, kBackendSourceMapArtifact);
  const std::optional<PackageDebugArtifactHealth> debugArtifacts =
      metadata != nullptr
          ? std::optional<PackageDebugArtifactHealth>(
                collectPackageDebugArtifactHealth(*metadata))
          : std::nullopt;
  const std::vector<std::string> requiredTools =
      hostLoaderRequiredTools(metadata);
  const std::size_t readyLoadUnitCount = hostInterfaceReady ? 1 : 0;
  const std::size_t blockedLoadUnitCount =
      hasLoadUnit && !hostInterfaceReady ? 1 : 0;
  const char *status = hostInterfaceReady
                           ? "ready"
                           : (hasLoadUnit ? "blocked" : "unavailable");

  out << "{\n"
      << indent << "  \"schemaVersion\": 1,\n"
      << indent
      << "  \"kind\": \"crossgl-runtime-host-loader-integration\",\n"
      << indent << "  \"status\": \"" << status << "\",\n"
      << indent << "  \"scope\": \"host-loader-scaffold-generation\",\n"
      << indent << "  \"nonGoals\": [\"host-code-rewriting\", "
         "\"device-execution\", \"runtime-framework-generation\", "
         "\"target-sdk-installation\"],\n"
      << indent << "  \"summary\": {\n"
      << indent << "    \"targetCount\": " << (hasLoadUnit ? 1 : 0) << ",\n"
      << indent << "    \"loadUnitCount\": " << (hasLoadUnit ? 1 : 0)
      << ",\n"
      << indent << "    \"readyLoadUnitCount\": " << readyLoadUnitCount
      << ",\n"
      << indent << "    \"blockedLoadUnitCount\": " << blockedLoadUnitCount
      << ",\n"
      << indent << "    \"entryPointCount\": " << entryPointCount << ",\n"
      << indent << "    \"resourceBindingCount\": " << resourceBindingCount
      << ",\n"
      << indent << "    \"workgroupSizeCount\": " << workgroupSizeCount
      << ",\n"
      << indent << "    \"functionConstantCount\": " << functionConstantCount
      << ",\n"
      << indent << "    \"specializationConstantCount\": "
      << specializationConstantCount
      << "\n"
      << indent << "  },\n"
      << indent << "  \"loadUnits\": ";
  if (!hasLoadUnit) {
    out << "[]";
  } else {
    out << "[\n" << indent << "    ";
    writeHostLoaderLoadUnit(out, *selection.artifact, sourceRemapArtifact,
                            backendSourceMapArtifact,
                            debugArtifacts ? &*debugArtifacts : nullptr,
                            selection.mode, selectedTarget, requiredTools,
                            hostInterfaceReady,
                            entryPointCount, resourceBindingCount,
                            workgroupSizeCount, functionConstantCount,
                            specializationConstantCount,
                            std::string(indent) + "    ");
    out << "\n" << indent << "  ]";
  }
  out << "\n" << indent << "}";
}

void writeCrossTLRuntimeAdapterLoadStepHeader(
    std::ostream &out, std::string_view kind, std::string_view message,
    std::string_view target, std::string_view packagePath,
    std::string_view hostInterfaceStatus,
    const std::vector<std::string> &tools, std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"kind\": \"" << escapeJson(kind) << "\",\n"
      << indent << "  \"message\": \"" << escapeJson(message) << "\",\n"
      << indent << "  \"target\": \"" << escapeJson(target) << "\",\n"
      << indent << "  \"packagePath\": \"" << escapeJson(packagePath)
      << "\",\n"
      << indent << "  \"tools\": ";
  writeStringArray(out, tools);
  out << ",\n"
      << indent << "  \"command\": null,\n"
      << indent << "  \"hostInterfaceStatus\": \""
      << escapeJson(hostInterfaceStatus) << "\",\n";
}

void writeCrossTLRuntimeAdapterLoadSteps(
    std::ostream &out, const CrossTLRuntimeAdapterLoadUnit &unit,
    std::string_view indent) {
  out << "[\n";
  const std::string loadMessage = "Load " + unit.artifactFormat + " artifact " +
                                  unit.packagePath + " for target " +
                                  unit.target + ".";
  writeCrossTLRuntimeAdapterLoadStepHeader(
      out, "load-package-artifact", loadMessage, unit.target, unit.packagePath,
      unit.hostInterfaceStatus, {}, std::string(indent) + "  ");
  out << std::string(indent) + "  " << "  \"metadata\": {\n"
      << std::string(indent) + "  " << "    \"source\": {\n"
      << std::string(indent) + "  " << "      \"field\": "
      << "\"descriptor.packagePath\",\n"
      << std::string(indent) + "  " << "      \"path\": \""
      << escapeJson(unit.packagePath) << "\"\n"
      << std::string(indent) + "  " << "    },\n"
      << std::string(indent) + "  " << "    \"artifact\": {\n"
      << std::string(indent) + "  " << "      \"name\": \""
      << escapeJson(unit.artifactName) << "\",\n"
      << std::string(indent) + "  "
      << "      \"producerArtifactFormat\": \""
      << escapeJson(unit.producerArtifactFormat) << "\",\n"
      << std::string(indent) + "  " << "      \"producerAdapterKind\": \""
      << escapeJson(unit.producerAdapterKind) << "\"\n"
      << std::string(indent) + "  " << "    }\n"
      << std::string(indent) + "  " << "  }\n"
      << std::string(indent) + "  " << "}";

  if (unit.sourceRemapPackagePath) {
    const std::string sourceRemapMessage =
        "Load source-remap metadata " + *unit.sourceRemapPackagePath +
        " for diagnostics and provenance.";
    out << ",\n";
    writeCrossTLRuntimeAdapterLoadStepHeader(
        out, "load-source-remap", sourceRemapMessage, unit.target,
        *unit.sourceRemapPackagePath, unit.hostInterfaceStatus, {},
        std::string(indent) + "  ");
    out << std::string(indent) + "  " << "  \"metadata\": {\n"
        << std::string(indent) + "  " << "    \"source\": {\n"
        << std::string(indent) + "  " << "      \"field\": "
        << "\"descriptor.sourceRemap.packagePath\",\n"
        << std::string(indent) + "  " << "      \"path\": \""
        << escapeJson(*unit.sourceRemapPackagePath) << "\"\n"
        << std::string(indent) + "  " << "    }\n"
        << std::string(indent) + "  " << "  }\n"
        << std::string(indent) + "  " << "}";
  }

  if (unit.hostInterfaceStatus == "ready") {
    const std::string hostMessage =
        "Bind " + std::to_string(unit.entryPointCount) +
        " entry points and " + std::to_string(unit.resourceCount) +
        " resources from CrossTL host-interface metadata.";
    out << ",\n";
    writeCrossTLRuntimeAdapterLoadStepHeader(
        out, "bind-host-interface", hostMessage, unit.target, unit.packagePath,
        unit.hostInterfaceStatus, {}, std::string(indent) + "  ");
    out << std::string(indent) + "  " << "  \"metadata\": {\n"
        << std::string(indent) + "  " << "    \"hostInterface\": {\n"
        << std::string(indent) + "  " << "      \"entryPointCount\": "
        << unit.entryPointCount << ",\n"
        << std::string(indent) + "  " << "      \"resourceCount\": "
        << unit.resourceCount << ",\n"
        << std::string(indent) + "  " << "      \"constantCount\": "
        << unit.constantCount << ",\n"
        << std::string(indent) + "  "
        << "      \"targetResourceBindingMetadataCount\": "
        << unit.resourceCount << "\n"
        << std::string(indent) + "  " << "    }\n"
        << std::string(indent) + "  " << "  }\n"
        << std::string(indent) + "  " << "}";
  }

  if (!unit.requiredTools.empty()) {
    std::ostringstream toolMessage;
    toolMessage << "Validate the loaded artifact with available target tools: ";
    for (std::size_t index = 0; index < unit.requiredTools.size(); ++index) {
      if (index != 0) {
        toolMessage << ", ";
      }
      toolMessage << unit.requiredTools[index];
    }
    toolMessage << ".";
    out << ",\n";
    writeCrossTLRuntimeAdapterLoadStepHeader(
        out, "validate-target-toolchain", toolMessage.str(), unit.target,
        unit.packagePath, unit.hostInterfaceStatus, unit.requiredTools,
        std::string(indent) + "  ");
    out << std::string(indent) + "  " << "  \"metadata\": {\n"
        << std::string(indent) + "  "
        << "    \"toolRequirementSource\": \"descriptor.requiredTools\"\n"
        << std::string(indent) + "  " << "  }\n"
        << std::string(indent) + "  " << "}";
  }

  out << "\n" << indent << "]";
}

void writeCrossTLRuntimeAdapterBlocker(
    std::ostream &out, std::string_view kind, std::string_view source,
    std::string_view message, const CrossTLRuntimeAdapterLoadUnit &unit,
    std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"kind\": \"" << escapeJson(kind) << "\",\n"
      << indent << "  \"severity\": \"warning\",\n"
      << indent << "  \"source\": \"" << escapeJson(source) << "\",\n"
      << indent << "  \"message\": \"" << escapeJson(message) << "\",\n"
      << indent << "  \"target\": \"" << escapeJson(unit.target) << "\",\n"
      << indent << "  \"adapter\": \"" << escapeJson(unit.id) << "\",\n"
      << indent << "  \"packagePath\": \"" << escapeJson(unit.packagePath)
      << "\"\n"
      << indent << "}";
}

void writeCrossTLRuntimeAdapterBlockers(
    std::ostream &out, const CrossTLRuntimeAdapterLoadUnit &unit,
    std::string_view indent) {
  const bool hostBlocked = unit.hostInterfaceStatus != "ready";
  const bool validationBlocked = !unit.candidateLoadReady;
  if (!hostBlocked && !validationBlocked) {
    out << "[]";
    return;
  }
  out << "[\n";
  bool emitted = false;
  if (hostBlocked) {
    const std::string message =
        "CrossTL runtime adapter host-interface metadata is not ready for " +
        unit.packagePath + ".";
    writeCrossTLRuntimeAdapterBlocker(
        out, "resolve-host-interface-metadata", "descriptor.hostInterface",
        message, unit, std::string(indent) + "  ");
    emitted = true;
  }
  if (validationBlocked) {
    if (emitted) {
      out << ",\n";
    }
    const std::string message =
        "CrossTL runtime adapter validation did not mark the load unit ready "
        "for " +
        unit.packagePath + ".";
    writeCrossTLRuntimeAdapterBlocker(
        out, "resolve-runtime-adapter-validation",
        "descriptor.validation.loadReady", message, unit,
        std::string(indent) + "  ");
  }
  out << "\n" << indent << "]";
}

void writeCrossTLRuntimeAdapterLoadUnit(
    std::ostream &out, const CrossTLRuntimeAdapterLoadUnit &unit,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"id\": \"" << escapeJson(unit.id) << "\",\n"
      << indent << "  \"target\": \"" << escapeJson(unit.target) << "\",\n"
      << indent << "  \"adapterKind\": \"" << escapeJson(unit.adapterKind)
      << "\",\n"
      << indent << "  \"artifactFormat\": \""
      << escapeJson(unit.artifactFormat) << "\",\n"
      << indent << "  \"packagePath\": \"" << escapeJson(unit.packagePath)
      << "\",\n"
      << indent << "  \"sourcePath\": ";
  writeNullableString(out, unit.sourcePath);
  out << ",\n" << indent << "  \"sourceBackend\": ";
  writeNullableString(out, unit.sourceBackend);
  out << ",\n" << indent << "  \"stage\": ";
  writeNullableString(out, unit.stage);
  out << ",\n" << indent << "  \"variant\": ";
  writeNullableString(out, unit.variant);
  out << ",\n"
      << indent << "  \"defines\": " << unit.definesJson << ",\n"
      << indent << "  \"sourceRemap\": " << unit.sourceRemapJson << ",\n"
      << indent << "  \"hostInterface\": " << unit.hostInterfaceJson << ",\n"
      << indent << "  \"requiredTools\": ";
  writeStringArray(out, unit.requiredTools);
  out << ",\n" << indent << "  \"hostResponsibilities\": ";
  writeStringArray(out, unit.hostResponsibilities);
  out << ",\n" << indent << "  \"loadSteps\": ";
  writeCrossTLRuntimeAdapterLoadSteps(out, unit, std::string(indent) + "  ");
  out << ",\n" << indent << "  \"blockers\": ";
  writeCrossTLRuntimeAdapterBlockers(out, unit, std::string(indent) + "  ");
  out << ",\n"
      << indent << "  \"validation\": {\n"
      << indent << "    \"hostInterface\": \""
      << escapeJson(unit.hostInterfaceStatus) << "\",\n"
      << indent << "    \"loadReady\": "
      << (unit.validationLoadReady ? "true" : "false") << ",\n"
      << indent << "    \"metadataOnly\": true,\n"
      << indent << "    \"sourceParsingRequired\": false,\n"
      << indent << "    \"compilerInvocationRequired\": false,\n"
      << indent << "    \"deviceExecutionRequired\": false\n"
      << indent << "  }\n"
      << indent << "}";
}

void writeCrossTLRuntimeAdapters(
    std::ostream &out, const PackageMetadata *metadata, const Selection &selection,
    const std::optional<std::string> &selectedTarget, std::string_view indent) {
  const std::vector<CrossTLRuntimeAdapterLoadUnit> loadUnits =
      readCrossTLRuntimeAdapterLoadUnits(metadata, selection, selectedTarget);
  const std::size_t readyLoadUnitCount =
      std::count_if(loadUnits.begin(), loadUnits.end(),
                    [](const CrossTLRuntimeAdapterLoadUnit &unit) {
                      return unit.validationLoadReady;
                    });
  std::vector<std::string> targets;
  for (const CrossTLRuntimeAdapterLoadUnit &unit : loadUnits) {
    if (std::find(targets.begin(), targets.end(), unit.target) == targets.end()) {
      targets.push_back(unit.target);
    }
  }
  std::sort(targets.begin(), targets.end());

  out << "{\n" << indent << "  \"target\": ";
  writeNullableString(out, selectedTarget);
  out << ",\n" << indent << "  \"runtimeArtifactPath\": ";
  if (selection.artifact != nullptr && !selection.artifact->path.empty()) {
    out << "\"" << escapeJson(selection.artifact->path) << "\"";
  } else {
    out << "null";
  }
  out << ",\n"
      << indent << "  \"loadUnitCount\": " << loadUnits.size() << ",\n"
      << indent << "  \"readyLoadUnitCount\": " << readyLoadUnitCount << ",\n"
      << indent << "  \"blockedLoadUnitCount\": "
      << (loadUnits.size() - readyLoadUnitCount) << ",\n"
      << indent << "  \"targets\": ";
  writeStringArray(out, targets);
  out << ",\n" << indent << "  \"loadUnits\": ";
  if (loadUnits.empty()) {
    out << "[]";
  } else {
    out << "[";
    for (std::size_t index = 0; index < loadUnits.size(); ++index) {
      out << (index == 0 ? "\n" : ",\n");
      writeCrossTLRuntimeAdapterLoadUnit(out, loadUnits[index],
                                         std::string(indent) + "    ");
    }
    out << "\n" << indent << "  ]";
  }
  out << "\n"
      << indent << "}";
}

void writePlanJson(std::ostream &out, const PackageRuntimePlanOptions &options,
                   const PackageMetadata *metadata,
                   const PackageTargetContract *contract,
                   const std::optional<std::string> &packageFormat,
                   const Selection &selection,
                   const std::vector<Diagnostic> &diagnostics,
                   bool success) {
  const std::string *packageTarget = metadata ? &metadata->target : nullptr;
  const std::string *requestedLoaderTarget =
      isKnownPackageTarget(options.requestedTarget) ? &options.requestedTarget
                                                   : nullptr;
  const bool targetMatchesPackage =
      metadata != nullptr && metadata->target == options.requestedTarget;
  const std::optional<std::uintmax_t> packageVersion =
      packageManifestSchemaVersion(metadata);
  const std::optional<std::string> selectedTarget =
      success && requestedLoaderTarget != nullptr
          ? std::optional<std::string>(*requestedLoaderTarget)
          : std::nullopt;
  const std::optional<std::string> reflectionFilterTarget =
      metadata != nullptr
          ? std::optional<std::string>(
                loaderReflectionTarget(*metadata, requestedLoaderTarget))
          : std::nullopt;
  const std::vector<std::string> requiredArtifacts =
      requiredArtifactNames(metadata, contract);
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"kind\": \"crossgl-runtime-loader-plan\",\n"
      << "  \"success\": " << (success ? "true" : "false") << ",\n"
      << "  \"metadataOnly\": true,\n"
      << "  \"sourceParsingRequired\": false,\n"
      << "  \"compilerInvocationRequired\": false,\n"
      << "  \"deviceExecutionRequired\": false,\n"
      << "  \"packageFormat\": ";
  writeNullableString(out, packageFormat);
  out << ",\n"
      << "  \"packageVersion\": ";
  if (packageVersion) {
    out << *packageVersion;
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"packageTarget\": ";
  writeNullableString(out, packageTarget);
  out << ",\n"
      << "  \"requestedLoaderTarget\": ";
  writeNullableString(out, requestedLoaderTarget);
  out << ",\n"
      << "  \"selectedTarget\": ";
  writeNullableString(out, selectedTarget);
  out << ",\n"
      << "  \"targetMatchesPackage\": "
      << (targetMatchesPackage ? "true" : "false") << ",\n"
      << "  \"loadable\": " << (success ? "true" : "false") << ",\n"
      << "  \"requestedPackageMode\": \""
      << escapeJson(toString(options.packageMode)) << "\",\n"
      << "  \"selectedPackageMode\": ";
  writeNullableString(out, selection.mode);
  out << ",\n"
      << "  \"selectedArtifact\": ";
  writeSelectedArtifact(out, selection.artifact, selection.mode, "  ");
  out << ",\n"
      << "  \"requiredArtifacts\": ";
  writeStringArray(out, requiredArtifacts);
  out << ",\n"
      << "  \"requiredArtifactPaths\": ";
  writeRequiredArtifactPaths(out, metadata, requiredArtifacts, "  ");
  out << ",\n"
      << "  \"runtimeArtifactPath\": ";
  if (selection.artifact != nullptr && !selection.artifact->path.empty()) {
    out << "\"" << escapeJson(selection.artifact->path) << "\"";
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"runtimeArtifactSelection\": ";
  writeRuntimeArtifactSelection(out, options, metadata, selection, success, "  ");
  out << ",\n"
      << "  \"requiredMetadataInputs\": [\"manifest.json\", "
         "\"reflection.json\", \"diagnostics.json\"],\n"
      << "  \"packageArtifactRequirementsSource\": ";
  if (metadata && metadata->artifactRequirements) {
    out << "\"manifest.packageArtifactRequirements\"";
  } else if (contract) {
    out << "\"generated-package-target-contract\"";
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"packageArtifactRequirements\": ";
  if (metadata && metadata->artifactRequirements) {
    writePackageArtifactRequirements(out, *metadata->artifactRequirements, "  ");
  } else if (contract) {
    writeContractRequirements(out, *contract, "  ");
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"targetLegalizationEvidenceSummary\": ";
  if (metadata) {
    writeTargetLegalizationEvidenceSummary(out, *metadata, "  ");
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"reflectionSummary\": ";
  if (metadata) {
    writeReflectionSummary(out, *metadata, *reflectionFilterTarget, "  ");
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"reflectionInputs\": ";
  if (metadata) {
    writeReflectionInputs(out, *metadata, selectedTarget, *reflectionFilterTarget,
                          "  ");
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"targetResourceBindingMetadata\": ";
  if (metadata) {
    writeTargetResourceBindingMetadata(out, *metadata, requestedLoaderTarget,
                                       selectedTarget, "  ");
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"hostLoaderIntegration\": ";
  writeHostLoaderIntegration(out, metadata, selection, selectedTarget,
                             reflectionFilterTarget, success, "  ");
  out << ",\n"
      << "  \"crosstlRuntimeAdapters\": ";
  writeCrossTLRuntimeAdapters(out, metadata, selection, selectedTarget, "  ");
  out << ",\n"
      << "  \"diagnosticCounts\": {\n"
      << "    \"note\": " << countDiagnostics(diagnostics, DiagnosticSeverity::Note)
      << ",\n"
      << "    \"warning\": "
      << countDiagnostics(diagnostics, DiagnosticSeverity::Warning) << ",\n"
      << "    \"error\": "
      << countDiagnostics(diagnostics, DiagnosticSeverity::Error) << "\n"
      << "  },\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, diagnostics, "  ");
  out << "\n}\n";
}

} // namespace

std::string toString(RuntimeLoaderPackageMode mode) {
  switch (mode) {
  case RuntimeLoaderPackageMode::Auto:
    return "auto";
  case RuntimeLoaderPackageMode::Native:
    return "native";
  case RuntimeLoaderPackageMode::SourcePackage:
    return "source-package";
  }
  return "auto";
}

bool parseRuntimeLoaderPackageMode(std::string_view text,
                                   RuntimeLoaderPackageMode &mode) {
  if (text == "auto") {
    mode = RuntimeLoaderPackageMode::Auto;
    return true;
  }
  if (text == "native") {
    mode = RuntimeLoaderPackageMode::Native;
    return true;
  }
  if (text == "source-package" || text == "source") {
    mode = RuntimeLoaderPackageMode::SourcePackage;
    return true;
  }
  return false;
}

PackageRuntimePlanResult
planPackageRuntimeLoader(const PackageRuntimePlanOptions &options) {
  DiagnosticEngine diagnostics;
  std::optional<std::string> packageFormat =
      detectPackageMetadataFormat(options.packagePath);
  PackageMetadataLoadOptions metadataOptions;
  metadataOptions.diagnosticCodePrefix = "package.runtime-plan";
  metadataOptions.commandName = "package plan-runtime";
  metadataOptions.allowStoredZipPackages = true;
  std::optional<PackageMetadata> metadata =
      loadPackageMetadata(options.packagePath, diagnostics, metadataOptions);

  std::vector<Diagnostic> allDiagnostics = diagnostics.diagnostics();
  const PackageTargetContract *contract = nullptr;
  Selection selection;

  if (metadata) {
    contract = packageTargetContractFor(metadata->target);
    if (options.requestedTarget.empty()) {
      Diagnostic diagnostic;
      diagnostic.severity = DiagnosticSeverity::Error;
      diagnostic.code = "package.runtime-plan.missing-target";
      diagnostic.message = "runtime loader plan requires --target";
      allDiagnostics.push_back(std::move(diagnostic));
    } else if (!isKnownPackageTarget(options.requestedTarget)) {
      Diagnostic diagnostic;
      diagnostic.severity = DiagnosticSeverity::Error;
      diagnostic.code = "package.runtime-plan.unknown-target";
      diagnostic.message =
          "runtime loader plan requested an unknown loader target";
      diagnostic.target = options.requestedTarget;
      allDiagnostics.push_back(std::move(diagnostic));
    } else if (metadata->target != options.requestedTarget) {
      Diagnostic diagnostic;
      diagnostic.severity = DiagnosticSeverity::Error;
      diagnostic.code = "package.runtime-plan.target-mismatch";
      diagnostic.message = "package target does not match requested loader target";
      diagnostic.target = metadata->target;
      allDiagnostics.push_back(std::move(diagnostic));
    } else if (contract == nullptr) {
      Diagnostic diagnostic;
      diagnostic.severity = DiagnosticSeverity::Error;
      diagnostic.code = "package.runtime-plan.unsupported-target";
      diagnostic.message =
          "runtime loader plan has no package target contract for target";
      diagnostic.target = metadata->target;
      allDiagnostics.push_back(std::move(diagnostic));
    } else {
      selection =
          selectArtifact(*metadata, *contract, options.packageMode, allDiagnostics);
    }
  }

  const bool success =
      metadata.has_value() && selection.artifact != nullptr &&
      countDiagnostics(allDiagnostics, DiagnosticSeverity::Error) == 0;

  std::ostringstream json;
  writePlanJson(json, options, metadata ? &*metadata : nullptr, contract,
                packageFormat, selection, allDiagnostics, success);
  return PackageRuntimePlanResult{success, json.str(), std::move(allDiagnostics)};
}

} // namespace crossgl
