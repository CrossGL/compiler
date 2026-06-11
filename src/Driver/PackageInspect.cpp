#include "crossgl/Driver/PackageInspect.h"

#include "PackageDebugArtifacts.h"
#include "crossgl/Basic/Json.h"
#include "crossgl/Basic/SHA256.h"
#include "crossgl/Driver/PackageJson.h"
#include "crossgl/Driver/PackageMetadata.h"
#include "crossgl/Driver/PackagePublication.h"

#include <algorithm>
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

void writeNullableSize(std::ostream &out,
                       const std::optional<std::uintmax_t> &sizeBytes) {
  if (sizeBytes) {
    out << *sizeBytes;
  } else {
    out << "null";
  }
}

void writeNullableString(std::ostream &out,
                         const std::optional<std::string> &value) {
  if (value) {
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

std::optional<std::string>
fileSha256IfRegular(const std::filesystem::path &path) {
  std::error_code error;
  if (!std::filesystem::is_regular_file(path, error) || error) {
    return std::nullopt;
  }

  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return std::nullopt;
  }
  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    return std::nullopt;
  }
  return sha256(buffer.str());
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
    out << ",\n" << indent << "  \"missingCapabilities\": [";
    for (std::size_t index = 0; index < diagnostic.missingCapabilities.size();
         ++index) {
      if (index != 0) {
        out << ", ";
      }
      out << "\"" << escapeJson(diagnostic.missingCapabilities[index]) << "\"";
    }
    out << "]";
  }
  out << "\n" << indent << "}";
}

void writeDiagnostics(std::ostream &out,
                      const std::vector<Diagnostic> &diagnostics) {
  out << "[";
  for (std::size_t index = 0; index < diagnostics.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeDiagnosticRecord(out, diagnostics[index], "    ");
  }
  if (!diagnostics.empty()) {
    out << "\n  ";
  }
  out << "]";
}

std::size_t countDiagnostics(const std::vector<Diagnostic> &diagnostics,
                             DiagnosticSeverity severity) {
  std::size_t count = 0;
  for (const Diagnostic &diagnostic : diagnostics) {
    if (diagnostic.severity == severity) {
      ++count;
    }
  }
  return count;
}

void writeRootFileRecord(std::ostream &out,
                         const std::filesystem::path &packagePath,
                         const PackageRootFileRecord &record,
                         std::string_view indent) {
  const std::string locationIndent = std::string(indent) + "  ";
  const std::optional<std::string> digest =
      fileSha256IfRegular(packagePath / record.path);
  out << indent << "{\n"
      << indent << "  \"name\": \"" << escapeJson(record.name) << "\",\n"
      << indent << "  \"path\": \"" << escapeJson(record.path) << "\",\n"
      << indent << "  \"provenance\": {\n"
      << indent << "    \"kind\": \"packageRootFile\",\n"
      << indent << "    \"source\": \"packageRoot\"\n"
      << indent << "  },\n"
      << indent << "  \"exists\": " << (record.exists ? "true" : "false")
      << ",\n"
      << indent << "  \"sizeBytes\": ";
  writeNullableSize(out, record.sizeBytes);
  out << ",\n" << indent << "  \"sha256\": ";
  writeNullableString(out, digest);
  out << ",\n" << indent << "  \"location\": ";
  writeSourceLocation(out, record.location, locationIndent);
  out << "\n" << indent << "}";
}

void writeArtifactRecord(std::ostream &out,
                         const std::filesystem::path &packagePath,
                         const PackageArtifactRecord &record,
                         std::string_view indent) {
  const std::string locationIndent = std::string(indent) + "  ";
  const std::optional<std::string> digest =
      record.packageRelative ? fileSha256IfRegular(packagePath / record.path)
                             : std::nullopt;
  out << indent << "{\n"
      << indent << "  \"name\": \"" << escapeJson(record.name) << "\",\n"
      << indent << "  \"path\": \"" << escapeJson(record.path) << "\",\n"
      << indent << "  \"provenance\": {\n"
      << indent << "    \"kind\": \"manifestArtifact\",\n"
      << indent << "    \"source\": \"manifest.artifacts\",\n"
      << indent << "    \"manifestKey\": \"" << escapeJson(record.name)
      << "\"\n"
      << indent << "  },\n"
      << indent << "  \"packageRelative\": "
      << (record.packageRelative ? "true" : "false") << ",\n"
      << indent << "  \"exists\": " << (record.exists ? "true" : "false")
      << ",\n"
      << indent << "  \"sizeBytes\": ";
  writeNullableSize(out, record.sizeBytes);
  out << ",\n" << indent << "  \"sha256\": ";
  writeNullableString(out, digest);
  if (record.location) {
    out << ",\n" << indent << "  \"location\": ";
    writeSourceLocation(out, *record.location, locationIndent);
  }
  out << "\n" << indent << "}";
}

void writeNullableBool(std::ostream &out, const std::optional<bool> &value) {
  if (value) {
    out << (*value ? "true" : "false");
  } else {
    out << "null";
  }
}

struct PackageTargetLegalizationSidecarEvidence {
  bool artifactPresent = false;
  bool artifactExists = false;
  std::optional<std::string> target;
  std::optional<std::string> packageMode;
  std::optional<std::string> packageDecisionReason;
  std::optional<std::uintmax_t> requiredToolCount;
  std::optional<std::uintmax_t> missingToolCount;
  std::optional<std::vector<std::string>> requiredToolIds;
  std::optional<std::vector<std::string>> missingToolIds;
  std::optional<bool> optionalNativeToolMissing;
  std::optional<std::string> optionalNativeToolStatus;
  std::optional<std::vector<std::string>> toolRequirementEvidenceIds;
  std::optional<std::vector<std::string>> legalizationCoreEvidenceIds;
  std::optional<std::vector<std::string>> packageArtifactRequirementEvidenceIds;
};

struct PackageTargetLegalizationManifestToolRequirements {
  bool present = false;
  std::optional<std::string> target;
  std::optional<std::string> packageMode;
  std::optional<std::uintmax_t> requiredToolCount;
  std::optional<std::uintmax_t> missingToolCount;
  std::optional<std::vector<std::string>> requiredToolIds;
  std::optional<std::vector<std::string>> missingToolIds;
  std::optional<bool> optionalNativeToolMissing;
  std::optional<std::string> optionalNativeToolStatus;
  std::optional<std::vector<std::string>> toolRequirementEvidenceIds;
};

struct PackageTargetLegalizationEvidence {
  std::string health = "not-present";
  std::optional<std::string> packageMode;
  std::optional<std::string> packageModeSource;
  PackageTargetLegalizationManifestToolRequirements manifestToolRequirements;
  PackageTargetLegalizationSidecarEvidence debugMetadata;
  PackageTargetLegalizationSidecarEvidence targetExplanation;
  std::optional<std::vector<std::string>> packageArtifactRequirementEvidenceIds;
  std::vector<std::string> missingEvidence;
  std::optional<bool> manifestToolRequirementsTargetMatchesPackage;
  std::optional<bool> manifestToolRequirementsPackageModeMatchesRequirements;
  std::optional<bool> manifestToolRequirementEvidenceIdsPresent;
  std::optional<bool> debugMetadataTargetMatchesPackage;
  std::optional<bool> targetExplanationTargetMatchesPackage;
  std::optional<bool> debugMetadataPackageModeMatchesRequirements;
  std::optional<bool> targetExplanationPackageModeMatchesRequirements;
  std::optional<bool> debugMetadataToolRequirementsMatchManifest;
  std::optional<bool> targetExplanationToolRequirementsMatchManifest;
  std::optional<bool> packageArtifactRequirementEvidenceIdsPresent;
};

const PackageArtifactRecord *
findArtifact(const PackageMetadata &metadata, std::string_view name) {
  for (const PackageArtifactRecord &artifact : metadata.artifacts) {
    if (artifact.name == name) {
      return &artifact;
    }
  }
  return nullptr;
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

std::optional<std::string>
readArtifactDocument(const PackageMetadata &metadata,
                     const PackageArtifactRecord *artifact) {
  if (!artifact || !artifact->packageRelative || !artifact->exists) {
    return std::nullopt;
  }
  return readRegularFile(metadata.packagePath / artifact->path);
}

std::optional<std::vector<std::string>>
parseJsonStringArray(std::string_view value) {
  std::vector<std::string> strings;
  std::size_t position = 0;
  skipWhitespace(value, position);
  if (position >= value.size() || value[position] != '[') {
    return std::nullopt;
  }
  ++position;
  skipWhitespace(value, position);
  if (position < value.size() && value[position] == ']') {
    ++position;
    skipWhitespace(value, position);
    return position == value.size()
               ? std::optional<std::vector<std::string>>(std::move(strings))
               : std::nullopt;
  }

  while (position < value.size()) {
    std::string element;
    if (!parseJsonString(value, position, element)) {
      return std::nullopt;
    }
    strings.push_back(std::move(element));
    skipWhitespace(value, position);
    if (position < value.size() && value[position] == ',') {
      ++position;
      skipWhitespace(value, position);
      continue;
    }
    if (position < value.size() && value[position] == ']') {
      ++position;
      skipWhitespace(value, position);
      return position == value.size()
                 ? std::optional<std::vector<std::string>>(std::move(strings))
                 : std::nullopt;
    }
    return std::nullopt;
  }
  return std::nullopt;
}

std::optional<std::vector<std::string>>
stringArrayMember(std::string_view object, std::string_view key) {
  const std::optional<std::string_view> value =
      findObjectMemberValue(object, key);
  if (!value) {
    return std::nullopt;
  }
  return parseJsonStringArray(*value);
}

bool hasEvidenceIds(const std::optional<std::vector<std::string>> &evidenceIds) {
  return evidenceIds && !evidenceIds->empty();
}

template <typename T>
bool optionalFieldDrift(const std::optional<T> &left,
                        const std::optional<T> &right) {
  return left && right && *left != *right;
}

bool sidecarToolRequirementsDrift(
    const PackageTargetLegalizationSidecarEvidence &left,
    const PackageTargetLegalizationSidecarEvidence &right) {
  return optionalFieldDrift(left.requiredToolCount, right.requiredToolCount) ||
         optionalFieldDrift(left.missingToolCount, right.missingToolCount) ||
         optionalFieldDrift(left.requiredToolIds, right.requiredToolIds) ||
         optionalFieldDrift(left.missingToolIds, right.missingToolIds) ||
         optionalFieldDrift(left.optionalNativeToolMissing,
                            right.optionalNativeToolMissing) ||
         optionalFieldDrift(left.optionalNativeToolStatus,
                            right.optionalNativeToolStatus) ||
         optionalFieldDrift(left.toolRequirementEvidenceIds,
                            right.toolRequirementEvidenceIds);
}

bool sidecarHasToolRequirements(
    const PackageTargetLegalizationSidecarEvidence &evidence) {
  return evidence.requiredToolCount && evidence.missingToolCount &&
         evidence.requiredToolIds && evidence.missingToolIds &&
         evidence.optionalNativeToolMissing &&
         evidence.optionalNativeToolStatus &&
         evidence.toolRequirementEvidenceIds;
}

bool manifestToolRequirementsDrift(
    const PackageTargetLegalizationManifestToolRequirements &manifest,
    const PackageTargetLegalizationSidecarEvidence &sidecar) {
  return optionalFieldDrift(manifest.requiredToolCount,
                            sidecar.requiredToolCount) ||
         optionalFieldDrift(manifest.missingToolCount,
                            sidecar.missingToolCount) ||
         optionalFieldDrift(manifest.requiredToolIds, sidecar.requiredToolIds) ||
         optionalFieldDrift(manifest.missingToolIds, sidecar.missingToolIds) ||
         optionalFieldDrift(manifest.optionalNativeToolMissing,
                            sidecar.optionalNativeToolMissing) ||
         optionalFieldDrift(manifest.optionalNativeToolStatus,
                            sidecar.optionalNativeToolStatus) ||
         optionalFieldDrift(manifest.toolRequirementEvidenceIds,
                            sidecar.toolRequirementEvidenceIds);
}

std::optional<bool> sidecarToolRequirementsMatchManifest(
    const PackageTargetLegalizationManifestToolRequirements &manifest,
    const PackageTargetLegalizationSidecarEvidence &sidecar) {
  if (!manifest.present || !sidecar.artifactExists) {
    return std::nullopt;
  }
  return sidecarHasToolRequirements(sidecar) &&
         !manifestToolRequirementsDrift(manifest, sidecar);
}

std::optional<std::string_view>
findTargetRecord(std::string_view arrayText, std::string_view target) {
  std::size_t position = 0;
  skipWhitespace(arrayText, position);
  if (position >= arrayText.size() || arrayText[position] != '[') {
    return std::nullopt;
  }
  ++position;
  skipWhitespace(arrayText, position);
  while (position < arrayText.size() && arrayText[position] != ']') {
    const std::size_t recordBegin = position;
    if (!skipJsonObject(arrayText, position)) {
      return std::nullopt;
    }
    const std::string_view record =
        arrayText.substr(recordBegin, position - recordBegin);
    const std::optional<std::string> recordTarget =
        objectStringMember(record, "target");
    if (recordTarget && *recordTarget == target) {
      return record;
    }
    skipWhitespace(arrayText, position);
    if (position < arrayText.size() && arrayText[position] == ',') {
      ++position;
      skipWhitespace(arrayText, position);
      continue;
    }
  }
  return std::nullopt;
}

std::optional<std::string_view>
findTargetCapabilitySummary(std::string_view debugMetadata,
                            std::string_view target) {
  const std::optional<std::string_view> capabilities =
      findObjectMemberValue(debugMetadata, "targetCapabilities");
  const std::optional<std::string_view> summaries =
      capabilities ? findObjectMemberValue(*capabilities, "summaries")
                   : std::nullopt;
  if (!summaries) {
    return std::nullopt;
  }
  return findTargetRecord(*summaries, target);
}

PackageTargetLegalizationSidecarEvidence
debugMetadataLegalizationEvidence(const PackageMetadata &metadata) {
  PackageTargetLegalizationSidecarEvidence evidence;
  evidence.artifactPresent = metadata.debugMetadataArtifactPresent;
  const PackageArtifactRecord *debugMetadata =
      findArtifact(metadata, "debugMetadata");
  evidence.artifactExists = debugMetadata != nullptr && debugMetadata->exists;

  const std::optional<std::string> document =
      readArtifactDocument(metadata, debugMetadata);
  if (!document) {
    return evidence;
  }

  const std::optional<std::string_view> decision =
      findObjectMemberValue(*document, "targetDecision");
  if (!decision) {
    return evidence;
  }

  evidence.target = objectStringMember(*decision, "selectedTarget");
  evidence.packageMode =
      objectStringMember(*decision, "selectedTargetPackageMode");
  evidence.legalizationCoreEvidenceIds = stringArrayMember(
      *decision, "selectedTargetLegalizationCoreEvidenceIds");
  evidence.packageArtifactRequirementEvidenceIds =
      stringArrayMember(*decision, "packageArtifactRequirementEvidenceIds");
  evidence.requiredToolCount =
      objectUnsignedMember(*decision, "selectedTargetRequiredToolCount");
  evidence.missingToolCount =
      objectUnsignedMember(*decision, "selectedTargetMissingToolCount");
  evidence.requiredToolIds =
      stringArrayMember(*decision, "selectedTargetRequiredToolIds");
  evidence.missingToolIds =
      stringArrayMember(*decision, "selectedTargetMissingToolIds");
  evidence.optionalNativeToolMissing =
      objectBoolMember(*decision, "selectedTargetOptionalNativeToolMissing");
  evidence.optionalNativeToolStatus =
      objectStringMember(*decision, "selectedTargetOptionalNativeToolStatus");
  evidence.toolRequirementEvidenceIds =
      stringArrayMember(*decision, "selectedTargetToolRequirementEvidenceIds");

  if (evidence.target) {
    const std::optional<std::string_view> summary =
        findTargetCapabilitySummary(*document, *evidence.target);
    if (summary) {
      evidence.packageDecisionReason =
          objectStringMember(*summary, "packageDecisionReason");
      if (!evidence.requiredToolCount) {
        evidence.requiredToolCount =
            objectUnsignedMember(*summary, "requiredToolCount");
      }
      if (!evidence.missingToolCount) {
        evidence.missingToolCount =
            objectUnsignedMember(*summary, "missingToolCount");
      }
      if (!evidence.requiredToolIds) {
        evidence.requiredToolIds = stringArrayMember(*summary, "requiredToolIds");
      }
      if (!evidence.missingToolIds) {
        evidence.missingToolIds = stringArrayMember(*summary, "missingToolIds");
      }
      if (!evidence.optionalNativeToolMissing) {
        evidence.optionalNativeToolMissing =
            objectBoolMember(*summary, "optionalNativeToolMissing");
      }
      if (!evidence.optionalNativeToolStatus) {
        evidence.optionalNativeToolStatus =
            objectStringMember(*summary, "optionalNativeToolStatus");
      }
      if (!evidence.toolRequirementEvidenceIds) {
        evidence.toolRequirementEvidenceIds =
            stringArrayMember(*summary, "toolRequirementEvidenceIds");
      }
      if (!evidence.packageArtifactRequirementEvidenceIds) {
        evidence.packageArtifactRequirementEvidenceIds =
            stringArrayMember(*summary, "packageArtifactRequirementEvidenceIds");
      }
    }
  }
  return evidence;
}

PackageTargetLegalizationSidecarEvidence
targetExplanationLegalizationEvidence(const PackageMetadata &metadata) {
  PackageTargetLegalizationSidecarEvidence evidence;
  const PackageArtifactRecord *targetExplanation =
      findArtifact(metadata, "targetExplanation");
  evidence.artifactPresent = targetExplanation != nullptr;
  evidence.artifactExists =
      targetExplanation != nullptr && targetExplanation->exists;

  const std::optional<std::string> document =
      readArtifactDocument(metadata, targetExplanation);
  if (!document) {
    return evidence;
  }

  const std::optional<std::string_view> targets =
      findObjectMemberValue(*document, "targets");
  const std::optional<std::string_view> record =
      targets ? findTargetRecord(*targets, metadata.target) : std::nullopt;
  if (!record) {
    return evidence;
  }

  evidence.target = objectStringMember(*record, "target");
  evidence.packageMode = objectStringMember(*record, "packageMode");
  evidence.packageDecisionReason =
      objectStringMember(*record, "packageDecisionReason");
  evidence.requiredToolCount = objectUnsignedMember(*record, "requiredToolCount");
  evidence.missingToolCount = objectUnsignedMember(*record, "missingToolCount");
  evidence.requiredToolIds = stringArrayMember(*record, "requiredToolIds");
  evidence.missingToolIds = stringArrayMember(*record, "missingToolIds");
  evidence.optionalNativeToolMissing =
      objectBoolMember(*record, "optionalNativeToolMissing");
  evidence.optionalNativeToolStatus =
      objectStringMember(*record, "optionalNativeToolStatus");
  evidence.toolRequirementEvidenceIds =
      stringArrayMember(*record, "toolRequirementEvidenceIds");
  evidence.legalizationCoreEvidenceIds =
      stringArrayMember(*record, "legalizationCoreEvidenceIds");
  evidence.packageArtifactRequirementEvidenceIds =
      stringArrayMember(*record, "packageArtifactRequirementEvidenceIds");
  return evidence;
}

std::optional<std::vector<std::string>>
manifestPackageArtifactRequirementEvidenceIds(const PackageMetadata &metadata) {
  if (metadata.artifactRequirements &&
      !metadata.artifactRequirements->evidenceIds.empty()) {
    return metadata.artifactRequirements->evidenceIds;
  }
  return std::nullopt;
}

PackageTargetLegalizationManifestToolRequirements
manifestToolRequirementsEvidence(const PackageMetadata &metadata) {
  PackageTargetLegalizationManifestToolRequirements evidence;
  if (!metadata.targetLegalizationToolRequirements) {
    return evidence;
  }

  const PackageTargetLegalizationToolRequirementsRecord &requirements =
      *metadata.targetLegalizationToolRequirements;
  evidence.present = true;
  evidence.target = requirements.target;
  evidence.packageMode = requirements.packageMode;
  evidence.requiredToolCount = requirements.requiredToolCount;
  evidence.missingToolCount = requirements.missingToolCount;
  evidence.requiredToolIds = requirements.requiredToolIds;
  evidence.missingToolIds = requirements.missingToolIds;
  evidence.optionalNativeToolMissing = requirements.optionalNativeToolMissing;
  evidence.optionalNativeToolStatus = requirements.optionalNativeToolStatus;
  evidence.toolRequirementEvidenceIds = requirements.toolRequirementEvidenceIds;
  return evidence;
}

std::optional<std::vector<std::string>>
firstEvidenceIds(const std::optional<std::vector<std::string>> &first,
                 const std::optional<std::vector<std::string>> &second,
                 const std::optional<std::vector<std::string>> &third) {
  if (hasEvidenceIds(first)) {
    return first;
  }
  if (hasEvidenceIds(second)) {
    return second;
  }
  if (hasEvidenceIds(third)) {
    return third;
  }
  return std::nullopt;
}

void appendMissingEvidence(std::vector<std::string> &missingEvidence,
                           std::string value) {
  missingEvidence.push_back(std::move(value));
}

PackageTargetLegalizationEvidence
collectPackageTargetLegalizationEvidence(const PackageMetadata &metadata) {
  PackageTargetLegalizationEvidence evidence;
  evidence.manifestToolRequirements = manifestToolRequirementsEvidence(metadata);
  evidence.debugMetadata = debugMetadataLegalizationEvidence(metadata);
  evidence.targetExplanation = targetExplanationLegalizationEvidence(metadata);
  if (metadata.artifactRequirements) {
    evidence.packageArtifactRequirementEvidenceIds = firstEvidenceIds(
        manifestPackageArtifactRequirementEvidenceIds(metadata),
        evidence.debugMetadata.packageArtifactRequirementEvidenceIds,
        evidence.targetExplanation.packageArtifactRequirementEvidenceIds);
  }

  if (metadata.artifactRequirements) {
    evidence.packageMode = metadata.artifactRequirements->packageMode;
    evidence.packageModeSource = "manifest.packageArtifactRequirements";
  } else if (evidence.debugMetadata.packageMode) {
    evidence.packageMode = evidence.debugMetadata.packageMode;
    evidence.packageModeSource =
        "debugMetadata.targetDecision.selectedTargetPackageMode";
  } else if (evidence.targetExplanation.packageMode) {
    evidence.packageMode = evidence.targetExplanation.packageMode;
    evidence.packageModeSource = "targetExplanation.targets[].packageMode";
  }

  if (evidence.debugMetadata.target) {
    evidence.debugMetadataTargetMatchesPackage =
        *evidence.debugMetadata.target == metadata.target;
  }
  if (evidence.targetExplanation.target) {
    evidence.targetExplanationTargetMatchesPackage =
        *evidence.targetExplanation.target == metadata.target;
  }
  if (metadata.artifactRequirements && evidence.debugMetadata.packageMode) {
    evidence.debugMetadataPackageModeMatchesRequirements =
        *evidence.debugMetadata.packageMode ==
        metadata.artifactRequirements->packageMode;
  }
  if (metadata.artifactRequirements && evidence.targetExplanation.packageMode) {
    evidence.targetExplanationPackageModeMatchesRequirements =
        *evidence.targetExplanation.packageMode ==
        metadata.artifactRequirements->packageMode;
  }
  if (metadata.artifactRequirements) {
    evidence.packageArtifactRequirementEvidenceIdsPresent =
        hasEvidenceIds(evidence.packageArtifactRequirementEvidenceIds);
  }
  if (evidence.manifestToolRequirements.present) {
    evidence.manifestToolRequirementsTargetMatchesPackage =
        evidence.manifestToolRequirements.target &&
        *evidence.manifestToolRequirements.target == metadata.target;
    if (metadata.artifactRequirements) {
      evidence.manifestToolRequirementsPackageModeMatchesRequirements =
          evidence.manifestToolRequirements.packageMode &&
          *evidence.manifestToolRequirements.packageMode ==
              metadata.artifactRequirements->packageMode;
    }
    evidence.manifestToolRequirementEvidenceIdsPresent =
        hasEvidenceIds(evidence.manifestToolRequirements
                           .toolRequirementEvidenceIds);
    evidence.debugMetadataToolRequirementsMatchManifest =
        sidecarToolRequirementsMatchManifest(evidence.manifestToolRequirements,
                                             evidence.debugMetadata);
    evidence.targetExplanationToolRequirementsMatchManifest =
        sidecarToolRequirementsMatchManifest(evidence.manifestToolRequirements,
                                             evidence.targetExplanation);
  }

  if (evidence.debugMetadata.artifactExists &&
      !hasEvidenceIds(evidence.debugMetadata.legalizationCoreEvidenceIds)) {
    appendMissingEvidence(
        evidence.missingEvidence,
        "debugMetadata.targetDecision.selectedTargetLegalizationCoreEvidenceIds");
  }
  if (evidence.targetExplanation.artifactExists &&
      !hasEvidenceIds(evidence.targetExplanation.legalizationCoreEvidenceIds)) {
    appendMissingEvidence(evidence.missingEvidence,
                          "targetExplanation.targets[].legalizationCoreEvidenceIds");
  }
  if (metadata.artifactRequirements &&
      !hasEvidenceIds(evidence.packageArtifactRequirementEvidenceIds)) {
    appendMissingEvidence(evidence.missingEvidence,
                          "packageArtifactRequirementEvidenceIds");
  }
  if (evidence.manifestToolRequirements.present &&
      !hasEvidenceIds(
          evidence.manifestToolRequirements.toolRequirementEvidenceIds)) {
    appendMissingEvidence(
        evidence.missingEvidence,
        "manifest.targetLegalizationToolRequirements.toolRequirementEvidenceIds");
  }

  const bool applicable =
      metadata.artifactRequirements.has_value() ||
      evidence.manifestToolRequirements.present ||
      evidence.debugMetadata.artifactPresent ||
      evidence.targetExplanation.artifactPresent;
  const bool incomplete =
      (evidence.debugMetadata.artifactPresent &&
       (!evidence.debugMetadata.artifactExists ||
        !evidence.debugMetadata.target || !evidence.debugMetadata.packageMode ||
        !hasEvidenceIds(evidence.debugMetadata.legalizationCoreEvidenceIds))) ||
      (evidence.targetExplanation.artifactPresent &&
       (!evidence.targetExplanation.artifactExists ||
        !evidence.targetExplanation.target ||
        !evidence.targetExplanation.packageMode ||
        !hasEvidenceIds(
            evidence.targetExplanation.legalizationCoreEvidenceIds)));
  const bool drift =
      (evidence.manifestToolRequirementsTargetMatchesPackage &&
       !*evidence.manifestToolRequirementsTargetMatchesPackage) ||
      (evidence.manifestToolRequirementsPackageModeMatchesRequirements &&
       !*evidence.manifestToolRequirementsPackageModeMatchesRequirements) ||
      (evidence.debugMetadataTargetMatchesPackage &&
       !*evidence.debugMetadataTargetMatchesPackage) ||
      (evidence.targetExplanationTargetMatchesPackage &&
       !*evidence.targetExplanationTargetMatchesPackage) ||
      (evidence.debugMetadataPackageModeMatchesRequirements &&
       !*evidence.debugMetadataPackageModeMatchesRequirements) ||
      (evidence.targetExplanationPackageModeMatchesRequirements &&
       !*evidence.targetExplanationPackageModeMatchesRequirements) ||
      (evidence.debugMetadataToolRequirementsMatchManifest &&
       !*evidence.debugMetadataToolRequirementsMatchManifest) ||
      (evidence.targetExplanationToolRequirementsMatchManifest &&
       !*evidence.targetExplanationToolRequirementsMatchManifest) ||
      sidecarToolRequirementsDrift(evidence.debugMetadata,
                                   evidence.targetExplanation);
  const bool partial =
      (evidence.packageArtifactRequirementEvidenceIdsPresent &&
       !*evidence.packageArtifactRequirementEvidenceIdsPresent) ||
      (evidence.manifestToolRequirementEvidenceIdsPresent &&
       !*evidence.manifestToolRequirementEvidenceIdsPresent);

  if (!applicable) {
    evidence.health = "not-present";
  } else if (drift) {
    evidence.health = "drift";
  } else if (incomplete) {
    evidence.health = "incomplete";
  } else if (partial) {
    evidence.health = "partial";
  } else {
    evidence.health = "ok";
  }
  return evidence;
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

void appendUniqueString(std::vector<std::string> &values,
                        const std::string &value) {
  if (value.empty() ||
      std::find(values.begin(), values.end(), value) != values.end()) {
    return;
  }
  values.push_back(value);
}

void writeNullableStringArray(
    std::ostream &out,
    const std::optional<std::vector<std::string>> &values) {
  if (values) {
    writeStringArray(out, *values);
  } else {
    out << "null";
  }
}

void writeTargetLegalizationSidecarEvidence(
    std::ostream &out, const PackageTargetLegalizationSidecarEvidence &evidence,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"artifactPresent\": "
      << (evidence.artifactPresent ? "true" : "false") << ",\n"
      << indent << "  \"artifactExists\": "
      << (evidence.artifactExists ? "true" : "false") << ",\n"
      << indent << "  \"target\": ";
  writeNullableString(out, evidence.target);
  out << ",\n" << indent << "  \"packageMode\": ";
  writeNullableString(out, evidence.packageMode);
  out << ",\n" << indent << "  \"packageDecisionReason\": ";
  writeNullableString(out, evidence.packageDecisionReason);
  out << ",\n" << indent << "  \"requiredToolCount\": ";
  writeNullableUnsigned(out, evidence.requiredToolCount);
  out << ",\n" << indent << "  \"missingToolCount\": ";
  writeNullableUnsigned(out, evidence.missingToolCount);
  out << ",\n" << indent << "  \"requiredToolIds\": ";
  writeNullableStringArray(out, evidence.requiredToolIds);
  out << ",\n" << indent << "  \"missingToolIds\": ";
  writeNullableStringArray(out, evidence.missingToolIds);
  out << ",\n" << indent << "  \"optionalNativeToolMissing\": ";
  writeNullableBool(out, evidence.optionalNativeToolMissing);
  out << ",\n" << indent << "  \"optionalNativeToolStatus\": ";
  writeNullableString(out, evidence.optionalNativeToolStatus);
  out << ",\n" << indent << "  \"toolRequirementEvidenceIds\": ";
  writeNullableStringArray(out, evidence.toolRequirementEvidenceIds);
  out << ",\n" << indent << "  \"legalizationCoreEvidenceIds\": ";
  writeNullableStringArray(out, evidence.legalizationCoreEvidenceIds);
  out << ",\n" << indent << "  \"packageArtifactRequirementEvidenceIds\": ";
  writeNullableStringArray(out, evidence.packageArtifactRequirementEvidenceIds);
  out << "\n" << indent << "}";
}

void writeTargetLegalizationManifestToolRequirements(
    std::ostream &out,
    const PackageTargetLegalizationManifestToolRequirements &evidence,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"present\": " << (evidence.present ? "true" : "false")
      << ",\n"
      << indent << "  \"target\": ";
  writeNullableString(out, evidence.target);
  out << ",\n" << indent << "  \"packageMode\": ";
  writeNullableString(out, evidence.packageMode);
  out << ",\n" << indent << "  \"requiredToolCount\": ";
  writeNullableUnsigned(out, evidence.requiredToolCount);
  out << ",\n" << indent << "  \"missingToolCount\": ";
  writeNullableUnsigned(out, evidence.missingToolCount);
  out << ",\n" << indent << "  \"requiredToolIds\": ";
  writeNullableStringArray(out, evidence.requiredToolIds);
  out << ",\n" << indent << "  \"missingToolIds\": ";
  writeNullableStringArray(out, evidence.missingToolIds);
  out << ",\n" << indent << "  \"optionalNativeToolMissing\": ";
  writeNullableBool(out, evidence.optionalNativeToolMissing);
  out << ",\n" << indent << "  \"optionalNativeToolStatus\": ";
  writeNullableString(out, evidence.optionalNativeToolStatus);
  out << ",\n" << indent << "  \"toolRequirementEvidenceIds\": ";
  writeNullableStringArray(out, evidence.toolRequirementEvidenceIds);
  out << "\n" << indent << "}";
}

void writeTargetLegalizationEvidence(
    std::ostream &out, const PackageTargetLegalizationEvidence &evidence,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"health\": \"" << escapeJson(evidence.health)
      << "\",\n"
      << indent << "  \"packageMode\": ";
  writeNullableString(out, evidence.packageMode);
  out << ",\n" << indent << "  \"packageModeSource\": ";
  writeNullableString(out, evidence.packageModeSource);
  out << ",\n" << indent << "  \"manifestToolRequirements\": ";
  writeTargetLegalizationManifestToolRequirements(
      out, evidence.manifestToolRequirements, std::string(indent) + "  ");
  out << ",\n" << indent << "  \"debugMetadata\": ";
  writeTargetLegalizationSidecarEvidence(out, evidence.debugMetadata,
                                         std::string(indent) + "  ");
  out << ",\n" << indent << "  \"targetExplanation\": ";
  writeTargetLegalizationSidecarEvidence(out, evidence.targetExplanation,
                                         std::string(indent) + "  ");
  out << ",\n"
      << indent << "  \"packageArtifactRequirementEvidenceIds\": ";
  writeNullableStringArray(out, evidence.packageArtifactRequirementEvidenceIds);
  out << ",\n" << indent << "  \"missingEvidence\": ";
  writeStringArray(out, evidence.missingEvidence);
  out << ",\n"
      << indent << "  \"checks\": {\n"
      << indent << "    \"manifestToolRequirementsTargetMatchesPackage\": ";
  writeNullableBool(out,
                    evidence.manifestToolRequirementsTargetMatchesPackage);
  out << ",\n"
      << indent
      << "    \"manifestToolRequirementsPackageModeMatchesRequirements\": ";
  writeNullableBool(
      out, evidence.manifestToolRequirementsPackageModeMatchesRequirements);
  out << ",\n"
      << indent << "    \"manifestToolRequirementEvidenceIdsPresent\": ";
  writeNullableBool(out,
                    evidence.manifestToolRequirementEvidenceIdsPresent);
  out << ",\n" << indent << "    \"debugMetadataTargetMatchesPackage\": ";
  writeNullableBool(out, evidence.debugMetadataTargetMatchesPackage);
  out << ",\n"
      << indent << "    \"targetExplanationTargetMatchesPackage\": ";
  writeNullableBool(out, evidence.targetExplanationTargetMatchesPackage);
  out << ",\n"
      << indent
      << "    \"debugMetadataPackageModeMatchesRequirements\": ";
  writeNullableBool(out,
                    evidence.debugMetadataPackageModeMatchesRequirements);
  out << ",\n"
      << indent
      << "    \"targetExplanationPackageModeMatchesRequirements\": ";
  writeNullableBool(out,
                    evidence.targetExplanationPackageModeMatchesRequirements);
  out << ",\n"
      << indent << "    \"debugMetadataToolRequirementsMatchManifest\": ";
  writeNullableBool(out,
                    evidence.debugMetadataToolRequirementsMatchManifest);
  out << ",\n"
      << indent << "    \"targetExplanationToolRequirementsMatchManifest\": ";
  writeNullableBool(out,
                    evidence.targetExplanationToolRequirementsMatchManifest);
  out << ",\n"
      << indent
      << "    \"packageArtifactRequirementEvidenceIdsPresent\": ";
  writeNullableBool(out,
                    evidence.packageArtifactRequirementEvidenceIdsPresent);
  out << "\n" << indent << "  }\n" << indent << "}";
}

void writeDebugArtifactHealth(std::ostream &out,
                              const PackageDebugArtifactHealth &health,
                              std::string_view indent) {
  const PackageSourceRemapProvenanceHealth &sourceRemap = health.sourceRemap;
  const PackageBackendSourceMapHealth &backendSourceMap =
      health.backendSourceMap;
  out << "{\n"
      << indent << "  \"debugMetadataArtifactPresent\": "
      << (health.debugMetadataArtifactPresent ? "true" : "false") << ",\n"
      << indent << "  \"hirSourceMapArtifactPresent\": "
      << (health.hirSourceMapArtifactPresent ? "true" : "false") << ",\n"
      << indent << "  \"debugMetadataExists\": "
      << (health.debugMetadataExists ? "true" : "false") << ",\n"
      << indent << "  \"hirSourceMapExists\": "
      << (health.hirSourceMapExists ? "true" : "false") << ",\n"
      << indent << "  \"health\": \"" << escapeJson(health.health) << "\",\n"
      << indent << "  \"sourceRemap\": {\n"
      << indent << "    \"artifactPresent\": "
      << (sourceRemap.artifactPresent ? "true" : "false") << ",\n"
      << indent << "    \"exists\": "
      << (sourceRemap.exists ? "true" : "false") << ",\n"
      << indent << "    \"health\": \"" << escapeJson(sourceRemap.health)
      << "\",\n"
      << indent << "    \"path\": ";
  writeNullableString(out, sourceRemap.path);
  out << ",\n" << indent << "    \"schemaVersion\": ";
  writeNullableUnsigned(out, sourceRemap.schemaVersion);
  out << ",\n" << indent << "    \"kind\": ";
  writeNullableString(out, sourceRemap.kind);
  out << ",\n" << indent << "    \"contractVersion\": ";
  writeNullableString(out, sourceRemap.contractVersion);
  out << ",\n" << indent << "    \"target\": ";
  writeNullableString(out, sourceRemap.target);
  out << ",\n" << indent << "    \"generatedFile\": ";
  writeNullableString(out, sourceRemap.generatedFile);
  out << ",\n" << indent << "    \"mappingGranularity\": ";
  writeNullableString(out, sourceRemap.mappingGranularity);
  out << ",\n" << indent << "    \"mappingCount\": ";
  writeNullableUnsigned(out, sourceRemap.mappingCount);
  out << ",\n" << indent << "    \"sourcePath\": ";
  writeNullableString(out, sourceRemap.sourcePath);
  out << ",\n" << indent << "    \"sourceSha256\": ";
  writeNullableString(out, sourceRemap.sourceSha256);
  out << ",\n" << indent << "    \"sourceSizeBytes\": ";
  writeNullableUnsigned(out, sourceRemap.sourceSizeBytes);
  out << ",\n"
      << indent << "    \"checks\": {\n"
      << indent << "      \"identityMatchesContract\": ";
  writeNullableBool(out, sourceRemap.checks.identityMatchesContract);
  out << ",\n" << indent << "      \"targetMatchesPackage\": ";
  writeNullableBool(out, sourceRemap.checks.targetMatchesPackage);
  out << ",\n" << indent << "      \"generatedFilePresent\": ";
  writeNullableBool(out, sourceRemap.checks.generatedFilePresent);
  out << ",\n" << indent << "      \"mappingGranularityMatchesContract\": ";
  writeNullableBool(out,
                    sourceRemap.checks.mappingGranularityMatchesContract);
  out << ",\n" << indent << "      \"mappingCountPositive\": ";
  writeNullableBool(out, sourceRemap.checks.mappingCountPositive);
  out << ",\n" << indent << "      \"sourcePathPresent\": ";
  writeNullableBool(out, sourceRemap.checks.sourcePathPresent);
  out << ",\n" << indent << "      \"sourceHashPresent\": ";
  writeNullableBool(out, sourceRemap.checks.sourceHashPresent);
  out << ",\n" << indent << "      \"sourceSizeBytesPresent\": ";
  writeNullableBool(out, sourceRemap.checks.sourceSizeBytesPresent);
  out << "\n" << indent << "    }\n" << indent << "  },\n"
      << indent << "  \"backendSourceMap\": {\n"
      << indent << "    \"artifactPresent\": "
      << (backendSourceMap.artifactPresent ? "true" : "false") << ",\n"
      << indent << "    \"exists\": "
      << (backendSourceMap.exists ? "true" : "false") << ",\n"
      << indent << "    \"health\": \""
      << escapeJson(backendSourceMap.health) << "\",\n"
      << indent << "    \"path\": ";
  writeNullableString(out, backendSourceMap.path);
  out << ",\n" << indent << "    \"schemaVersion\": ";
  writeNullableUnsigned(out, backendSourceMap.schemaVersion);
  out << ",\n" << indent << "    \"kind\": ";
  writeNullableString(out, backendSourceMap.kind);
  out << ",\n" << indent << "    \"target\": ";
  writeNullableString(out, backendSourceMap.target);
  out << ",\n" << indent << "    \"module\": ";
  writeNullableString(out, backendSourceMap.module);
  out << ",\n" << indent << "    \"mappingGranularity\": ";
  writeNullableString(out, backendSourceMap.mappingGranularity);
  out << ",\n" << indent << "    \"sourceBackend\": ";
  writeNullableString(out, backendSourceMap.sourceBackend);
  out << ",\n" << indent << "    \"targetBackend\": ";
  writeNullableString(out, backendSourceMap.targetBackend);
  out << ",\n" << indent << "    \"backendLanguage\": ";
  writeNullableString(out, backendSourceMap.backendLanguage);
  out << ",\n" << indent << "    \"backendLineCount\": ";
  writeNullableUnsigned(out, backendSourceMap.backendLineCount);
  out << ",\n" << indent << "    \"backendSourceLineCount\": ";
  writeNullableUnsigned(out, backendSourceMap.backendSourceLineCount);
  out << ",\n" << indent << "    \"mappingCount\": ";
  writeNullableUnsigned(out, backendSourceMap.mappingCount);
  out << ",\n" << indent << "    \"mappingRecordCount\": ";
  writeNullableUnsigned(out, backendSourceMap.mappingRecordCount);
  out << ",\n" << indent << "    \"backendMaxMappedLine\": ";
  writeNullableUnsigned(out, backendSourceMap.backendMaxMappedLine);
  out << ",\n" << indent << "    \"sourceRemapPresent\": "
      << (backendSourceMap.sourceRemapPresent ? "true" : "false");
  out << ",\n" << indent << "    \"sourceRemapPath\": ";
  writeNullableString(out, backendSourceMap.sourceRemapPath);
  out << ",\n" << indent << "    \"sourceRemapGeneratedFile\": ";
  writeNullableString(out, backendSourceMap.sourceRemapGeneratedFile);
  out << ",\n" << indent << "    \"sourceRemapTarget\": ";
  writeNullableString(out, backendSourceMap.sourceRemapTarget);
  out << ",\n" << indent << "    \"sourceRemapMappingGranularity\": ";
  writeNullableString(out, backendSourceMap.sourceRemapMappingGranularity);
  out << ",\n" << indent << "    \"sourceRemapMappingCount\": ";
  writeNullableUnsigned(out, backendSourceMap.sourceRemapMappingCount);
  out << ",\n" << indent << "    \"sourceRemapSourceBackend\": ";
  writeNullableString(out, backendSourceMap.sourceRemapSourceBackend);
  out << ",\n" << indent << "    \"sourceRemapVariant\": ";
  writeNullableString(out, backendSourceMap.sourceRemapVariant);
  out << ",\n" << indent << "    \"sourceRemapSha256\": ";
  writeNullableString(out, backendSourceMap.sourceRemapSha256);
  out << ",\n" << indent << "    \"sourceRemapSizeBytes\": ";
  writeNullableUnsigned(out, backendSourceMap.sourceRemapSizeBytes);
  out << ",\n"
      << indent << "    \"checks\": {\n"
      << indent << "      \"identityMatchesContract\": ";
  writeNullableBool(out, backendSourceMap.checks.identityMatchesContract);
  out << ",\n" << indent << "      \"targetMatchesPackage\": ";
  writeNullableBool(out, backendSourceMap.checks.targetMatchesPackage);
  out << ",\n" << indent << "      \"moduleMatchesPackage\": ";
  writeNullableBool(out, backendSourceMap.checks.moduleMatchesPackage);
  out << ",\n" << indent << "      \"mappingGranularityMatchesContract\": ";
  writeNullableBool(
      out, backendSourceMap.checks.mappingGranularityMatchesContract);
  out << ",\n" << indent << "      \"sourceBackendPresent\": ";
  writeNullableBool(out, backendSourceMap.checks.sourceBackendPresent);
  out << ",\n"
      << indent << "      \"targetBackendMatchesBackendLanguage\": ";
  writeNullableBool(
      out, backendSourceMap.checks.targetBackendMatchesBackendLanguage);
  out << ",\n" << indent << "      \"backendLanguagePresent\": ";
  writeNullableBool(out, backendSourceMap.checks.backendLanguagePresent);
  out << ",\n" << indent << "      \"backendLineCountPresent\": ";
  writeNullableBool(out, backendSourceMap.checks.backendLineCountPresent);
  out << ",\n" << indent << "      \"backendLineCountMatchesSource\": ";
  writeNullableBool(out,
                    backendSourceMap.checks.backendLineCountMatchesSource);
  out << ",\n" << indent << "      \"backendSpansWithinSource\": ";
  writeNullableBool(out, backendSourceMap.checks.backendSpansWithinSource);
  out << ",\n" << indent << "      \"mappingCountMatchesMappings\": ";
  writeNullableBool(out, backendSourceMap.checks.mappingCountMatchesMappings);
  out << ",\n" << indent << "      \"sourceRemapHashPresent\": ";
  writeNullableBool(out, backendSourceMap.checks.sourceRemapHashPresent);
  out << ",\n" << indent << "      \"sourceRemapMappingCountPositive\": ";
  writeNullableBool(out,
                    backendSourceMap.checks.sourceRemapMappingCountPositive);
  out << ",\n" << indent << "      \"sourceRemapMatchesProvenance\": ";
  writeNullableBool(out, backendSourceMap.checks.sourceRemapMatchesProvenance);
  out << "\n" << indent << "    }\n" << indent << "  },\n"
      << indent << "  \"checks\": {\n"
      << indent << "    \"hirSourceLocationsMatch\": ";
  writeNullableBool(out, health.hirSourceLocationsMatch);
  out << ",\n" << indent << "    \"sourceMapUnfiltered\": ";
  writeNullableBool(out, health.sourceMapUnfiltered);
  out << ",\n" << indent << "    \"sourceMapUnpaged\": ";
  writeNullableBool(out, health.sourceMapUnpaged);
  out << ",\n" << indent << "    \"sourceMapRecordsDisabled\": ";
  writeNullableBool(out, health.sourceMapRecordsDisabled);
  out << ",\n" << indent << "    \"sourceMapCategoryCountsConsistent\": ";
  writeNullableBool(out, health.sourceMapCategoryCountsConsistent);
  out << ",\n" << indent << "    \"recordsTotalCountMatchesCategoryCounts\": ";
  writeNullableBool(out, health.recordsTotalCountMatchesCategoryCounts);
  out << "\n" << indent << "  }\n" << indent << "}";
}

void writeSidecarRecord(std::ostream &out, const PackageSidecarRecord &record,
                        std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"path\": \""
      << escapeJson(record.path.lexically_normal().generic_string()) << "\",\n"
      << indent << "  \"kind\": \"" << escapeJson(record.kind) << "\",\n"
      << indent << "  \"token\": \"" << escapeJson(record.token) << "\",\n"
      << indent << "  \"attempt\": " << record.attempt << ",\n"
      << indent
      << "  \"directory\": " << (record.isDirectory ? "true" : "false") << "\n"
      << indent << "}";
}

void writeVulkanNativeProfileHealth(
    std::ostream &out, const PackageVulkanNativeProfileHealth &health,
    std::string_view indent) {
  out << "{\n"
      << indent
      << "  \"applicable\": " << (health.applicable ? "true" : "false") << ",\n"
      << indent << "  \"nativeProfileArtifactPresent\": "
      << (health.nativeProfileArtifactPresent ? "true" : "false") << ",\n"
      << indent << "  \"nativeProfileExists\": "
      << (health.nativeProfileExists ? "true" : "false") << ",\n"
      << indent << "  \"health\": \"" << escapeJson(health.health) << "\",\n"
      << indent << "  \"schemaVersion\": ";
  writeNullableUnsigned(out, health.schemaVersion);
  out << ",\n" << indent << "  \"api\": ";
  writeNullableString(out, health.api);
  out << ",\n" << indent << "  \"profileName\": ";
  writeNullableString(out, health.profileName);
  out << ",\n" << indent << "  \"vulkanVersion\": ";
  writeNullableString(out, health.vulkanVersion);
  out << ",\n" << indent << "  \"spirvVersion\": ";
  writeNullableString(out, health.spirvVersion);
  out << ",\n" << indent << "  \"generator\": ";
  writeNullableString(out, health.generator);
  out << ",\n" << indent << "  \"nativeBinary\": ";
  writeNullableString(out, health.nativeBinary);
  out << ",\n" << indent << "  \"backendAssembly\": ";
  writeNullableString(out, health.backendAssembly);
  out << ",\n" << indent << "  \"disassemblyStatus\": ";
  writeNullableString(out, health.disassemblyStatus);
  out << ",\n" << indent << "  \"disassemblyPath\": ";
  writeNullableString(out, health.disassemblyPath);
  out << ",\n" << indent << "  \"disassemblyExists\": ";
  writeNullableBool(out, health.disassemblyExists);
  out << ",\n"
      << indent << "  \"checks\": {\n"
      << indent << "    \"targetMatchesPackage\": ";
  writeNullableBool(out, health.targetMatchesPackage);
  out << ",\n" << indent << "    \"moduleMatchesPackage\": ";
  writeNullableBool(out, health.moduleMatchesPackage);
  out << ",\n" << indent << "    \"nativeBinaryMatchesManifest\": ";
  writeNullableBool(out, health.nativeBinaryMatchesManifest);
  out << ",\n" << indent << "    \"backendAssemblyMatchesManifest\": ";
  writeNullableBool(out, health.backendAssemblyMatchesManifest);
  out << ",\n" << indent << "    \"emittedDisassemblyExists\": ";
  writeNullableBool(out, health.emittedDisassemblyExists);
  out << ",\n" << indent << "    \"spirvProfilePresent\": ";
  writeNullableBool(out, health.spirvProfilePresent);
  out << "\n" << indent << "  }\n" << indent << "}";
}

std::string artifactRequirementsProjectionBasis(
    const PackageMetadata &metadata,
    const PackageNativeArtifactDescriptorHealth &nativeArtifactDescriptor) {
  if (metadata.artifactRequirements) {
    return "recorded-packageArtifactRequirements";
  }
  if (nativeArtifactDescriptor.artifactPresent) {
    return "recorded-nativeArtifactDescriptor-health";
  }
  return "legacy-missing-packageArtifactRequirements";
}

std::optional<std::string>
packageInspectNativeBinaryStatus(const PackageMetadata &metadata) {
  if (metadata.artifactRequirements) {
    return metadata.nativeBinaryStatus;
  }
  return effectivePackageNativeBinaryStatus(metadata);
}

std::optional<bool>
recordedNativeBinaryStatusMatchesRequirements(const PackageMetadata &metadata) {
  if (!metadata.artifactRequirements) {
    return std::nullopt;
  }
  return packageNativeBinaryStatusMatchesRequirements(
      *metadata.artifactRequirements, metadata.nativeBinaryStatus);
}

void writeArtifactRequirementsProjection(
    std::ostream &out, const PackageMetadata &metadata,
    const PackageNativeArtifactDescriptorHealth &nativeArtifactDescriptor,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"basis\": \""
      << escapeJson(
             artifactRequirementsProjectionBasis(metadata,
                                                 nativeArtifactDescriptor))
      << "\",\n"
      << indent << "  \"reportOnly\": true,\n"
      << indent << "  \"packageArtifactRequirementsPresent\": "
      << (metadata.artifactRequirements ? "true" : "false") << ",\n"
      << indent << "  \"packageArtifactRequirementsSource\": ";
  if (metadata.artifactRequirements) {
    out << "\"manifest.packageArtifactRequirements\"";
  } else {
    out << "null";
  }
  out << ",\n" << indent << "  \"nativeBinaryStatusMatchesRequirements\": ";
  writeNullableBool(out,
                    recordedNativeBinaryStatusMatchesRequirements(metadata));
  out << ",\n"
      << indent << "  \"legacyManifestAbsence\": "
      << (metadata.artifactRequirements ? "false" : "true") << ",\n"
      << indent << "  \"nativeArtifactDescriptorArtifactPresent\": "
      << (nativeArtifactDescriptor.artifactPresent ? "true" : "false")
      << ",\n"
      << indent << "  \"nativeArtifactDescriptorHealth\": \""
      << escapeJson(nativeArtifactDescriptor.health) << "\",\n"
      << indent << "  \"nativeArtifactDescriptorPath\": ";
  writeNullableString(out, nativeArtifactDescriptor.path);
  out << "\n" << indent << "}";
}

std::vector<std::string>
selectedTargetFeatureEvidenceIds(const PackageMetadata &metadata) {
  std::vector<std::string> evidenceIds;
  for (const PackageReflectionTargetFeatureRecord &feature :
       metadata.reflectionTargetFeatures) {
    if (feature.target != metadata.target) {
      continue;
    }
    for (const std::string &evidenceId : feature.evidenceIds) {
      appendUniqueString(evidenceIds, evidenceId);
    }
  }
  return evidenceIds;
}

std::size_t selectedTargetFeatureCount(const PackageMetadata &metadata) {
  return std::count_if(
      metadata.reflectionTargetFeatures.begin(),
      metadata.reflectionTargetFeatures.end(),
      [&](const PackageReflectionTargetFeatureRecord &feature) {
        return feature.target == metadata.target;
      });
}

void writeReflectionSummary(std::ostream &out, const PackageMetadata &metadata,
                            std::string_view indent) {
  out << "{\n"
      << indent << "  \"targetFeatureCount\": "
      << selectedTargetFeatureCount(metadata) << ",\n"
      << indent << "  \"targetFeatureEvidenceIds\": ";
  writeStringArray(out, selectedTargetFeatureEvidenceIds(metadata));
  out << "\n" << indent << "}";
}

void writeNativeArtifactDescriptorChecks(
    std::ostream &out, const PackageNativeArtifactDescriptorChecks &checks,
    std::string_view indent) {
  out << "{\n" << indent << "  \"descriptorIdentityMatchesContract\": ";
  writeNullableBool(out, checks.descriptorIdentityMatchesContract);
  out << ",\n" << indent << "  \"targetMatchesPackage\": ";
  writeNullableBool(out, checks.targetMatchesPackage);
  out << ",\n" << indent << "  \"nativeBinaryStatusMatchesPackage\": ";
  writeNullableBool(out, checks.nativeBinaryStatusMatchesPackage);
  out << ",\n" << indent << "  \"sourcePathMatchesManifest\": ";
  writeNullableBool(out, checks.sourcePathMatchesManifest);
  out << ",\n" << indent << "  \"sourceHashMatchesFile\": ";
  writeNullableBool(out, checks.sourceHashMatchesFile);
  out << ",\n" << indent << "  \"artifactPathMatchesManifest\": ";
  writeNullableBool(out, checks.artifactPathMatchesManifest);
  out << ",\n" << indent << "  \"artifactHashMatchesFile\": ";
  writeNullableBool(out, checks.artifactHashMatchesFile);
  out << ",\n" << indent << "  \"sizeBytesMatchesFile\": ";
  writeNullableBool(out, checks.sizeBytesMatchesFile);
  out << ",\n" << indent << "  \"validationStatusMatchesNativeStatus\": ";
  writeNullableBool(out, checks.validationStatusMatchesNativeStatus);
  out << "\n" << indent << "}";
}

void writeNativeArtifactDescriptorHealth(
    std::ostream &out, const PackageNativeArtifactDescriptorHealth &health,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"artifactPresent\": "
      << (health.artifactPresent ? "true" : "false") << ",\n"
      << indent << "  \"descriptorExists\": "
      << (health.descriptorExists ? "true" : "false") << ",\n"
      << indent << "  \"health\": \"" << escapeJson(health.health) << "\",\n"
      << indent << "  \"path\": ";
  writeNullableString(out, health.path);
  out << ",\n" << indent << "  \"schemaVersion\": ";
  writeNullableUnsigned(out, health.schemaVersion);
  out << ",\n" << indent << "  \"kind\": ";
  writeNullableString(out, health.kind);
  out << ",\n" << indent << "  \"contractVersion\": ";
  writeNullableString(out, health.contractVersion);
  out << ",\n" << indent << "  \"target\": ";
  writeNullableString(out, health.target);
  out << ",\n" << indent << "  \"binaryKind\": ";
  writeNullableString(out, health.binaryKind);
  out << ",\n" << indent << "  \"sourcePath\": ";
  writeNullableString(out, health.sourcePath);
  out << ",\n" << indent << "  \"sourceHash\": ";
  writeNullableString(out, health.sourceHash);
  out << ",\n" << indent << "  \"artifactPath\": ";
  writeNullableString(out, health.artifactPath);
  out << ",\n" << indent << "  \"artifactHash\": ";
  writeNullableString(out, health.artifactHash);
  out << ",\n" << indent << "  \"sizeBytes\": ";
  writeNullableUnsigned(out, health.sizeBytes);
  out << ",\n" << indent << "  \"optimizationLevel\": ";
  writeNullableString(out, health.optimizationLevel);
  out << ",\n" << indent << "  \"optimizationEvidence\": ";
  if (health.optimizationEvidence) {
    out << *health.optimizationEvidence;
  } else {
    out << "null";
  }
  out << ",\n" << indent << "  \"validationStatus\": ";
  writeNullableString(out, health.validationStatus);
  out << ",\n" << indent << "  \"nativeBinaryStatus\": ";
  writeNullableString(out, health.nativeBinaryStatus);
  out << ",\n" << indent << "  \"checks\": ";
  writeNativeArtifactDescriptorChecks(out, health.checks,
                                      std::string(indent) + "  ");
  out << "\n" << indent << "}";
}

void writeGraphicsAbiSummary(std::ostream &out,
                             const PackageGraphicsAbiSummary &summary,
                             std::string_view indent) {
  out << "{\n"
      << indent << "  \"module\": \"" << escapeJson(summary.module)
      << "\",\n"
      << indent << "  \"target\": \"" << escapeJson(summary.target)
      << "\",\n"
      << indent << "  \"entryPointCount\": " << summary.entryPointCount
      << ",\n"
      << indent << "  \"vertexInputCount\": " << summary.vertexInputCount
      << ",\n"
      << indent << "  \"varyingCount\": " << summary.varyingCount << ",\n"
      << indent << "  \"fragmentOutputCount\": "
      << summary.fragmentOutputCount << ",\n"
      << indent << "  \"builtinCount\": " << summary.builtinCount << ",\n"
      << indent << "  \"resourceCount\": " << summary.resourceCount << ",\n"
      << indent << "  \"abiRecordCount\": " << summary.abiRecordCount << "\n"
      << indent << "}";
}

void writeGraphicsAbiDiagnostics(
    std::ostream &out,
    const std::vector<PackageGraphicsAbiDiagnostic> &diagnostics,
    std::string_view indent) {
  out << "[";
  for (std::size_t index = 0; index < diagnostics.size(); ++index) {
    const PackageGraphicsAbiDiagnostic &diagnostic = diagnostics[index];
    out << (index == 0 ? "\n" : ",\n")
        << indent << "{\n"
        << indent << "  \"severity\": \"error\",\n"
        << indent << "  \"code\": \"" << escapeJson(diagnostic.code)
        << "\",\n"
        << indent << "  \"message\": \""
        << escapeJson(diagnostic.message) << "\"\n"
        << indent << "}";
  }
  if (!diagnostics.empty()) {
    std::string closingIndent(indent);
    if (closingIndent.size() >= 2) {
      closingIndent.resize(closingIndent.size() - 2);
    }
    out << "\n" << closingIndent;
  }
  out << "]";
}

void writeGraphicsAbiHealth(std::ostream &out,
                            const PackageGraphicsAbiHealth &health,
                            std::string_view indent) {
  out << "{\n"
      << indent << "  \"artifactPresent\": "
      << (health.artifactPresent ? "true" : "false") << ",\n"
      << indent << "  \"path\": ";
  writeNullableString(out, health.path);
  out << ",\n"
      << indent << "  \"exists\": " << (health.exists ? "true" : "false")
      << ",\n"
      << indent << "  \"health\": \"" << escapeJson(health.health)
      << "\",\n"
      << indent << "  \"validation\": \"lightweight-structural\",\n"
      << indent << "  \"schemaVersion\": ";
  writeNullableUnsigned(out, health.schemaVersion);
  out << ",\n" << indent << "  \"summary\": ";
  if (health.summary) {
    writeGraphicsAbiSummary(out, *health.summary, std::string(indent) + "  ");
  } else {
    out << "null";
  }
  out << ",\n"
      << indent << "  \"diagnosticCounts\": {\n"
      << indent << "    \"note\": 0,\n"
      << indent << "    \"warning\": 0,\n"
      << indent << "    \"error\": " << health.diagnostics.size() << "\n"
      << indent << "  },\n"
      << indent << "  \"diagnostics\": ";
  writeGraphicsAbiDiagnostics(out, health.diagnostics,
                              std::string(indent) + "    ");
  out << "\n" << indent << "}";
}

void writePackageArtifactRequirements(
    std::ostream &out, const PackageArtifactRequirementsRecord &requirements,
    std::string_view indent) {
  const std::string locationIndent = std::string(indent) + "  ";
  out << "{\n"
      << indent << "  \"target\": \"" << escapeJson(requirements.target)
      << "\",\n"
      << indent << "  \"packageMode\": \""
      << escapeJson(requirements.packageMode) << "\",\n"
      << indent << "  \"requiredPathArtifacts\": [";
  for (std::size_t index = 0; index < requirements.requiredPathArtifacts.size();
       ++index) {
    const PackageRequiredPathArtifactRecord &artifact =
        requirements.requiredPathArtifacts[index];
    out << (index == 0 ? "\n" : ",\n") << indent << "    {\n"
        << indent << "      \"name\": \"" << escapeJson(artifact.name) << "\"";
    if (artifact.location) {
      out << ",\n" << indent << "      \"location\": ";
      writeSourceLocation(out, *artifact.location,
                          std::string(indent) + "      ");
    }
    out << "\n" << indent << "    }";
  }
  if (!requirements.requiredPathArtifacts.empty()) {
    out << "\n" << indent << "  ";
  }
  out << "]";
  if (!requirements.evidenceIds.empty()) {
    out << ",\n" << indent << "  \"evidenceIds\": ";
    writeStringArray(out, requirements.evidenceIds);
  }
  out << ",\n"
      << indent << "  \"requiresNativeBinaryStatus\": "
      << (requirements.requiresNativeBinaryStatus ? "true" : "false") << ",\n"
      << indent << "  \"allowsPlannedNativeBinary\": "
      << (requirements.allowsPlannedNativeBinary ? "true" : "false") << ",\n"
      << indent << "  \"allowsPlannedNativeSourceEvidence\": "
      << (requirements.allowsPlannedNativeSourceEvidence ? "true" : "false")
      << ",\n"
      << indent << "  \"location\": ";
  writeSourceLocation(out, requirements.location, locationIndent);
  if (requirements.targetLocation) {
    out << ",\n" << indent << "  \"targetLocation\": ";
    writeSourceLocation(out, *requirements.targetLocation, locationIndent);
  }
  if (requirements.packageModeLocation) {
    out << ",\n" << indent << "  \"packageModeLocation\": ";
    writeSourceLocation(out, *requirements.packageModeLocation, locationIndent);
  }
  if (requirements.requiredPathArtifactsLocation) {
    out << ",\n" << indent << "  \"requiredPathArtifactsLocation\": ";
    writeSourceLocation(out, *requirements.requiredPathArtifactsLocation,
                        locationIndent);
  }
  if (requirements.evidenceIdsLocation) {
    out << ",\n" << indent << "  \"evidenceIdsLocation\": ";
    writeSourceLocation(out, *requirements.evidenceIdsLocation, locationIndent);
  }
  out << "\n" << indent << "}";
}

void writePublicationInfo(std::ostream &out,
                          const PackagePublicationInfo &publication,
                          std::string_view indent) {
  std::optional<std::string> sidecarKind;
  std::optional<std::string> sidecarToken;
  std::optional<std::uint64_t> sidecarAttempt;
  if (publication.currentSidecar) {
    sidecarKind = publication.currentSidecar->kind;
    sidecarToken = publication.currentSidecar->token;
    sidecarAttempt = publication.currentSidecar->attempt;
  }

  out << "{\n"
      << indent << "  \"state\": \"" << escapeJson(publication.state) << "\",\n"
      << indent << "  \"requestedPath\": \""
      << escapeJson(
             publication.requestedPath.lexically_normal().generic_string())
      << "\",\n"
      << indent << "  \"sidecarKind\": ";
  writeNullableString(out, sidecarKind);
  out << ",\n" << indent << "  \"sidecarToken\": ";
  writeNullableString(out, sidecarToken);
  out << ",\n" << indent << "  \"sidecarAttempt\": ";
  if (sidecarAttempt) {
    out << *sidecarAttempt;
  } else {
    out << "null";
  }
  out << ",\n"
      << indent
      << "  \"siblingSidecarCount\": " << publication.siblingSidecars.size()
      << ",\n"
      << indent << "  \"siblingSidecars\": [";
  for (std::size_t index = 0; index < publication.siblingSidecars.size();
       ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeSidecarRecord(out, publication.siblingSidecars[index],
                       std::string(indent) + "    ");
  }
  if (!publication.siblingSidecars.empty()) {
    out << "\n" << indent << "  ";
  }
  out << "]\n" << indent << "}";
}

void writeRawJson(std::ostream &out, std::string_view json) {
  out << json;
  if (!json.empty() && json.back() != '\n') {
    out << "\n";
  }
}

std::string packageInspectJson(const PackageMetadata &metadata) {
  const PackageDebugArtifactHealth debugArtifactHealth =
      collectPackageDebugArtifactHealth(metadata);
  const PackageVulkanNativeProfileHealth vulkanNativeProfile =
      collectPackageVulkanNativeProfileHealth(metadata);
  const PackageNativeArtifactDescriptorHealth nativeArtifactDescriptor =
      collectPackageNativeArtifactDescriptorHealth(metadata);
  const PackageGraphicsAbiHealth graphicsAbi =
      collectPackageGraphicsAbiHealth(metadata);
  const PackageTargetLegalizationEvidence targetLegalizationEvidence =
      collectPackageTargetLegalizationEvidence(metadata);
  const PackagePublicationInfo publication =
      collectPackagePublicationInfo(metadata.packagePath);
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"packagePath\": \""
      << escapeJson(metadata.packagePath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"packageFormat\": \"directory\",\n"
      << "  \"summary\": {\n"
      << "    \"module\": \"" << escapeJson(metadata.module) << "\",\n"
      << "    \"target\": \"" << escapeJson(metadata.target) << "\",\n"
      << "    \"nativeBinaryStatus\": ";
  if (const std::optional<std::string> nativeBinaryStatus =
          packageInspectNativeBinaryStatus(metadata)) {
    out << "\"" << escapeJson(*nativeBinaryStatus) << "\"";
  } else {
    out << "null";
  }
  out << ",\n"
      << "    \"artifactCount\": " << metadata.artifacts.size() << ",\n"
      << "    \"debugArtifactsPresent\": "
      << (metadata.debugArtifactsPresent ? "true" : "false") << ",\n"
      << "    \"reflection\": ";
  writeReflectionSummary(out, metadata, "    ");
  out << "\n"
      << "  },\n"
      << "  \"debugArtifacts\": ";
  writeDebugArtifactHealth(out, debugArtifactHealth, "  ");
  out << ",\n"
      << "  \"vulkanNativeProfile\": ";
  writeVulkanNativeProfileHealth(out, vulkanNativeProfile, "  ");
  out << ",\n"
      << "  \"nativeArtifactDescriptor\": ";
  writeNativeArtifactDescriptorHealth(out, nativeArtifactDescriptor, "  ");
  if (graphicsAbi.artifactPresent) {
    out << ",\n"
        << "  \"graphicsAbi\": ";
    writeGraphicsAbiHealth(out, graphicsAbi, "  ");
  }
  out << ",\n"
      << "  \"artifactRequirementsProjection\": ";
  writeArtifactRequirementsProjection(out, metadata, nativeArtifactDescriptor,
                                      "  ");
  if (targetLegalizationEvidence.health != "not-present") {
    out << ",\n"
        << "  \"targetLegalizationEvidence\": ";
    writeTargetLegalizationEvidence(out, targetLegalizationEvidence, "  ");
  }
  out << ",\n"
      << "  \"publication\": ";
  writePublicationInfo(out, publication, "  ");
  out << ",\n";
  if (metadata.artifactRequirements) {
    out << "  \"packageArtifactRequirements\": ";
    writePackageArtifactRequirements(out, *metadata.artifactRequirements, "  ");
    out << ",\n";
  }
  out << "  \"rootFiles\": [";
  for (std::size_t index = 0; index < metadata.rootFiles.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeRootFileRecord(out, metadata.packagePath, metadata.rootFiles[index],
                        "    ");
  }
  if (!metadata.rootFiles.empty()) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"artifacts\": [";
  for (std::size_t index = 0; index < metadata.artifacts.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeArtifactRecord(out, metadata.packagePath, metadata.artifacts[index],
                        "    ");
  }
  if (!metadata.artifacts.empty()) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"manifest\": ";
  writeRawJson(out, metadata.documents.manifest);
  out << ",\n"
      << "  \"reflection\": ";
  writeRawJson(out, metadata.documents.reflection);
  out << ",\n"
      << "  \"diagnostics\": ";
  writeRawJson(out, metadata.documents.diagnostics);
  out << "}\n";
  return out.str();
}

std::string
packageInspectFailureJson(const std::filesystem::path &packagePath,
                          const std::vector<Diagnostic> &diagnostics) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"packagePath\": \""
      << escapeJson(packagePath.lexically_normal().generic_string()) << "\",\n"
      << "  \"success\": false,\n"
      << "  \"packageFormat\": null,\n"
      << "  \"summary\": null,\n"
      << "  \"diagnosticCounts\": {\n"
      << "    \"note\": "
      << countDiagnostics(diagnostics, DiagnosticSeverity::Note) << ",\n"
      << "    \"warning\": "
      << countDiagnostics(diagnostics, DiagnosticSeverity::Warning) << ",\n"
      << "    \"error\": "
      << countDiagnostics(diagnostics, DiagnosticSeverity::Error) << "\n"
      << "  },\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, diagnostics);
  out << "\n}\n";
  return out.str();
}

} // namespace

PackageInspectResult inspectPackage(const std::filesystem::path &packagePath) {
  DiagnosticEngine diagnostics;
  PackageInspectResult result;

  PackageMetadataLoadOptions options;
  options.diagnosticCodePrefix = "package.inspect";
  options.commandName = "package inspect";

  std::optional<PackageMetadata> metadata =
      loadPackageMetadata(packagePath, diagnostics, options);
  if (!metadata) {
    result.diagnostics = diagnostics.diagnostics();
    result.json = packageInspectFailureJson(packagePath, result.diagnostics);
    return result;
  }

  result.json = packageInspectJson(*metadata);
  result.success = true;
  result.diagnostics = diagnostics.diagnostics();
  return result;
}

} // namespace crossgl
