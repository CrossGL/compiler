#include "crossgl/Driver/PackageIntegrity.h"

#include "PackageDebugArtifacts.h"
#include "crossgl/Basic/Json.h"
#include "crossgl/Basic/SHA256.h"
#include "crossgl/Driver/PackageJson.h"
#include "crossgl/Driver/PackageTargetContracts.h"

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <limits>
#include <ostream>
#include <sstream>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace crossgl {
namespace {

std::string diagnosticCode(std::string_view suffix) {
  return "package.verify." + std::string(suffix);
}

const PackageArtifactRecord *findArtifact(const PackageMetadata &metadata,
                                          std::string_view name) {
  for (const PackageArtifactRecord &artifact : metadata.artifacts) {
    if (artifact.name == name) {
      return &artifact;
    }
  }
  return nullptr;
}

SourceLocation locationOr(const std::optional<SourceLocation> &location,
                          const SourceLocation &fallback) {
  if (location) {
    return *location;
  }
  return fallback;
}

SourceLocation artifactsLocation(const PackageMetadata &metadata) {
  return locationOr(metadata.artifactsLocation, metadata.manifestLocation);
}

SourceLocation artifactLocation(const PackageMetadata &metadata,
                                const PackageArtifactRecord &artifact) {
  return locationOr(artifact.location, artifactsLocation(metadata));
}

std::string artifactLabel(std::string_view name,
                          const PackageArtifactRecord *artifact) {
  std::string label(name);
  if (artifact && !artifact->path.empty()) {
    label += " '" + artifact->path + "'";
  }
  return label;
}

SourceLocation sourceHashLocation(const PackageMetadata &metadata) {
  return locationOr(metadata.sourceHashLocation, metadata.manifestLocation);
}

SourceLocation sourceHashAlgorithmLocation(const PackageMetadata &metadata) {
  return locationOr(metadata.sourceHashAlgorithmLocation,
                    sourceHashLocation(metadata));
}

SourceLocation sourceHashValueLocation(const PackageMetadata &metadata) {
  return locationOr(metadata.sourceHashValueLocation,
                    sourceHashLocation(metadata));
}

SourceLocation sourcePathLocation(const std::filesystem::path &path) {
  SourceLocation location;
  location.file = path.lexically_normal().generic_string();
  return location;
}

void addRequiredPathArtifact(PackageArtifactRequirementsRecord &requirements,
                             std::string name) {
  requirements.requiredPathArtifacts.push_back({std::move(name), std::nullopt});
}

PackageArtifactRequirementsRecord
legacyPackageArtifactRequirements(const PackageMetadata &metadata) {
  PackageArtifactRequirementsRecord requirements;
  requirements.location = metadata.manifestLocation;
  requirements.target = metadata.target;
  if (metadata.target == "metal") {
    requirements.packageMode = "native";
    addRequiredPathArtifact(requirements, "backendSource");
    addRequiredPathArtifact(requirements, "intermediate");
    addRequiredPathArtifact(requirements, "nativeBinary");
  } else if (metadata.target == "vulkan") {
    requirements.packageMode = "native";
    addRequiredPathArtifact(requirements, "backendAssembly");
    addRequiredPathArtifact(requirements, "nativeBinary");
  } else if (metadata.target == "directx" || metadata.target == "opengl") {
    requirements.packageMode = "source-package";
    addRequiredPathArtifact(requirements, "backendSource");
    addRequiredPathArtifact(requirements, "nativeBinary");
    requirements.requiresNativeBinaryStatus = true;
    requirements.allowsPlannedNativeBinary = true;
    requirements.allowsPlannedNativeSourceEvidence = true;
  }
  return requirements;
}

PackageArtifactRequirementsRecord
packageArtifactRequirementsForVerification(const PackageMetadata &metadata) {
  if (metadata.artifactRequirements) {
    return *metadata.artifactRequirements;
  }
  return legacyPackageArtifactRequirements(metadata);
}

std::optional<std::string>
packageVerifyNativeBinaryStatus(const PackageMetadata &metadata) {
  if (metadata.artifactRequirements) {
    return metadata.nativeBinaryStatus;
  }
  return effectivePackageNativeBinaryStatus(metadata);
}

void noteLegacyArtifactRequirementsFallback(const PackageMetadata &metadata,
                                            DiagnosticEngine &diagnostics) {
  if (metadata.artifactRequirements) {
    return;
  }
  diagnostics.note(
      diagnosticCode("legacy-artifact-requirements-fallback"),
      "manifest is missing packageArtifactRequirements and is using "
      "legacy compatibility defaults for package verification only",
      metadata.manifestLocation);
}

std::string_view
expectedPackageArtifactRequirementMode(const PackageTargetContract &contract) {
  return contract.allowsPlannedNativeBinary ? "source-package" : "native";
}

std::string formatRequiredPathArtifacts(
    const PackageArtifactRequirementsRecord &requirements) {
  std::ostringstream out;
  out << "[";
  for (std::size_t index = 0;
       index < requirements.requiredPathArtifacts.size(); ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << requirements.requiredPathArtifacts[index].name;
  }
  out << "]";
  return out.str();
}

std::string formatRequiredPathArtifacts(const PackageTargetContract &contract) {
  std::ostringstream out;
  out << "[";
  for (std::size_t index = 0; index < contract.requiredArtifactCount; ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << contract.requiredArtifacts[index];
  }
  out << "]";
  return out.str();
}

bool requiredPathArtifactsMatchTargetContract(
    const PackageArtifactRequirementsRecord &requirements,
    const PackageTargetContract &contract) {
  if (requirements.requiredPathArtifacts.size() !=
      contract.requiredArtifactCount) {
    return false;
  }

  for (std::size_t index = 0; index < contract.requiredArtifactCount; ++index) {
    if (std::string_view(requirements.requiredPathArtifacts[index].name) !=
        contract.requiredArtifacts[index]) {
      return false;
    }
  }
  return true;
}

std::string packageArtifactEvidenceId(std::string_view target,
                                      std::string_view suffix) {
  return "target-legalization.v1." + std::string(target) + "." +
         std::string(suffix);
}

std::vector<std::string> expectedPackageArtifactRequirementEvidenceIds(
    const PackageArtifactRequirementsRecord &requirements) {
  std::vector<std::string> evidenceIds;
  evidenceIds.push_back(packageArtifactEvidenceId(
      requirements.target, "package-artifacts." + requirements.packageMode));
  for (const PackageRequiredPathArtifactRecord &artifact :
       requirements.requiredPathArtifacts) {
    evidenceIds.push_back(packageArtifactEvidenceId(
        requirements.target, "package-artifact.required." + artifact.name));
  }
  if (requirements.requiresNativeBinaryStatus) {
    evidenceIds.push_back(packageArtifactEvidenceId(
        requirements.target, "package-artifact.native-binary-status.required"));
  }
  if (requirements.allowsPlannedNativeBinary) {
    evidenceIds.push_back(packageArtifactEvidenceId(
        requirements.target, "package-artifact.planned-native-binary.allowed"));
  }
  if (requirements.allowsPlannedNativeSourceEvidence) {
    evidenceIds.push_back(packageArtifactEvidenceId(
        requirements.target,
        "package-artifact.planned-native-source-evidence.allowed"));
  }
  return evidenceIds;
}

bool verifyArtifactRequirementsForVerification(
    const PackageMetadata &metadata,
    const PackageArtifactRequirementsRecord &requirements,
    DiagnosticEngine &diagnostics) {
  bool valid = true;
  if (requirements.target != metadata.target) {
    diagnostics.error(
        diagnosticCode("invalid-manifest"),
        "package manifest packageArtifactRequirements target must match "
        "manifest target",
        requirements.targetLocation.value_or(requirements.location));
    valid = false;
  }

  const PackageTargetContract *contract =
      packageTargetContractFor(metadata.target);
  if (contract != nullptr) {
    const std::string_view expectedPackageMode =
        expectedPackageArtifactRequirementMode(*contract);
    if (requirements.packageMode != expectedPackageMode) {
      diagnostics.error(
          diagnosticCode("invalid-manifest"),
          "package manifest packageArtifactRequirements.packageMode must match "
          "manifest target contract: expected '" +
              std::string(expectedPackageMode) + "', got '" +
              requirements.packageMode + "'",
          requirements.packageModeLocation.value_or(requirements.location));
      valid = false;
    }

    if (!requiredPathArtifactsMatchTargetContract(requirements, *contract)) {
      diagnostics.error(
          diagnosticCode("invalid-manifest"),
          "package manifest "
          "packageArtifactRequirements.requiredPathArtifacts must match manifest "
          "target contract: expected " +
              formatRequiredPathArtifacts(*contract) + ", got " +
              formatRequiredPathArtifacts(requirements),
          requirements.requiredPathArtifactsLocation.value_or(
              requirements.location));
      valid = false;
    }

    const bool expectedRequiresNativeBinaryStatus =
        contract->requiresNativeBinaryStatus;
    const bool expectedAllowsPlannedNativeBinary =
        contract->allowsPlannedNativeBinary;
    const bool expectedAllowsPlannedNativeSourceEvidence =
        contract->allowsPlannedNativeSourceEvidence;
    if (requirements.requiresNativeBinaryStatus !=
            expectedRequiresNativeBinaryStatus ||
        requirements.allowsPlannedNativeBinary !=
            expectedAllowsPlannedNativeBinary ||
        requirements.allowsPlannedNativeSourceEvidence !=
            expectedAllowsPlannedNativeSourceEvidence) {
      diagnostics.error(
          diagnosticCode("invalid-manifest"),
          "package manifest packageArtifactRequirements native binary policy "
          "must match manifest target contract",
          requirements.location);
      valid = false;
    }
  }

  if (metadata.artifactRequirements) {
    const std::vector<std::string> expectedEvidenceIds =
        expectedPackageArtifactRequirementEvidenceIds(requirements);
    if (requirements.evidenceIds.empty()) {
      diagnostics.error(
          diagnosticCode(
              "target-legalization-package-artifact-requirement-evidence-"
              "missing"),
          "package manifest packageArtifactRequirements.evidenceIds must "
          "record target legalization package artifact requirement evidence",
          requirements.evidenceIdsLocation.value_or(requirements.location));
      valid = false;
    } else if (requirements.evidenceIds != expectedEvidenceIds) {
      diagnostics.error(
          diagnosticCode(
              "target-legalization-package-artifact-requirement-evidence-"
              "mismatch"),
          "package manifest packageArtifactRequirements.evidenceIds must "
          "match recorded packageArtifactRequirements",
          requirements.evidenceIdsLocation.value_or(requirements.location));
      valid = false;
    }
    return valid;
  }

  return valid;
}

bool allowsPlannedNativeBinary(
    const PackageMetadata &metadata, const PackageArtifactRecord &artifact,
    const PackageArtifactRequirementsRecord &requirements) {
  return artifact.name == "nativeBinary" &&
         requirements.allowsPlannedNativeBinary &&
         metadata.nativeBinaryStatus &&
         *metadata.nativeBinaryStatus == "planned";
}

struct PackageTargetLegalizationSidecarEvidence {
  bool artifactPresent = false;
  bool artifactExists = false;
  std::optional<std::string> target;
  std::optional<std::string> packageMode;
  std::optional<std::string> packageDecisionReason;
  std::optional<bool> packageBuildSupported;
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

std::optional<std::vector<std::string_view>>
jsonArrayElements(std::string_view value) {
  std::vector<std::string_view> elements;
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
               ? std::optional<std::vector<std::string_view>>(std::move(elements))
               : std::nullopt;
  }

  while (position < value.size()) {
    const std::size_t elementBegin = position;
    if (!skipJsonValue(value, position)) {
      return std::nullopt;
    }
    elements.push_back(value.substr(elementBegin, position - elementBegin));
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
                 ? std::optional<std::vector<std::string_view>>(
                       std::move(elements))
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

bool hasEvidenceIds(
    const std::optional<std::vector<std::string>> &evidenceIds) {
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

bool sidecarRequirementEvidenceIdsDrift(
    const PackageTargetLegalizationSidecarEvidence &sidecar,
    const std::optional<std::vector<std::string>> &expectedEvidenceIds) {
  return sidecar.packageArtifactRequirementEvidenceIds &&
         (!expectedEvidenceIds ||
          *sidecar.packageArtifactRequirementEvidenceIds !=
              *expectedEvidenceIds);
}

bool sidecarProjectionIncomplete(
    const PackageTargetLegalizationSidecarEvidence &evidence) {
  return evidence.artifactPresent &&
         (!evidence.artifactExists || !evidence.target ||
          !evidence.packageMode || !evidence.packageBuildSupported ||
          !hasEvidenceIds(evidence.legalizationCoreEvidenceIds));
}

std::optional<std::string_view> findTargetRecord(std::string_view arrayText,
                                                 std::string_view target) {
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
  evidence.packageBuildSupported =
      objectBoolMember(*decision, "selectedTargetPackageBuildSupported");
  evidence.legalizationCoreEvidenceIds =
      stringArrayMember(*decision, "selectedTargetLegalizationCoreEvidenceIds");
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
        evidence.packageArtifactRequirementEvidenceIds = stringArrayMember(
            *summary, "packageArtifactRequirementEvidenceIds");
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
  evidence.packageBuildSupported =
      objectBoolMember(*record, "packageBuildSupported");
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
  evidence.packageArtifactRequirementEvidenceIds = firstEvidenceIds(
      manifestPackageArtifactRequirementEvidenceIds(metadata),
      evidence.debugMetadata.packageArtifactRequirementEvidenceIds,
      evidence.targetExplanation.packageArtifactRequirementEvidenceIds);

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
    appendMissingEvidence(evidence.missingEvidence,
                          "debugMetadata.targetDecision."
                          "selectedTargetLegalizationCoreEvidenceIds");
  }
  if (evidence.targetExplanation.artifactExists &&
      !hasEvidenceIds(evidence.targetExplanation.legalizationCoreEvidenceIds)) {
    appendMissingEvidence(
        evidence.missingEvidence,
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

  const bool applicable = metadata.artifactRequirements.has_value() ||
                          evidence.manifestToolRequirements.present ||
                          evidence.debugMetadata.artifactPresent ||
                          evidence.targetExplanation.artifactPresent;
  const bool incomplete =
      sidecarProjectionIncomplete(evidence.debugMetadata) ||
      sidecarProjectionIncomplete(evidence.targetExplanation);
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
      (metadata.artifactRequirements &&
       (sidecarRequirementEvidenceIdsDrift(
            evidence.debugMetadata,
            evidence.packageArtifactRequirementEvidenceIds) ||
        sidecarRequirementEvidenceIdsDrift(
            evidence.targetExplanation,
            evidence.packageArtifactRequirementEvidenceIds))) ||
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

std::string artifactPathIssueMessage(PackagePathIssue issue) {
  switch (issue) {
  case PackagePathIssue::None:
    return "";
  case PackagePathIssue::Empty:
    return "path must not be empty";
  case PackagePathIssue::BackslashSeparator:
    return "artifact paths must use '/' separators";
  case PackagePathIssue::Absolute:
    return "path must be package-relative";
  case PackagePathIssue::ParentTraversal:
    return "path must stay inside package";
  }
  return "path is invalid";
}

std::string reflectionNativeBinaryPathIssueMessage(PackagePathIssue issue) {
  switch (issue) {
  case PackagePathIssue::None:
    return "";
  case PackagePathIssue::Empty:
    return "path must not be empty";
  case PackagePathIssue::BackslashSeparator:
    return "path must use '/' separators";
  case PackagePathIssue::Absolute:
    return "path must be package-relative";
  case PackagePathIssue::ParentTraversal:
    return "path must stay inside package";
  }
  return "path is invalid";
}

void verifyRequiredArtifacts(
    const PackageMetadata &metadata,
    const PackageArtifactRequirementsRecord &requirements,
    DiagnosticEngine &diagnostics) {
  for (const PackageRequiredPathArtifactRecord &artifactRequirement :
       requirements.requiredPathArtifacts) {
    if (!findArtifact(metadata, artifactRequirement.name)) {
      diagnostics.error(diagnosticCode("missing-required-artifact"),
                        metadata.target + " packages require " +
                            artifactRequirement.name,
                        artifactsLocation(metadata));
    }
  }

  if (requirements.requiresNativeBinaryStatus &&
      !metadata.nativeBinaryStatus.has_value()) {
    diagnostics.error(diagnosticCode("missing-native-status"),
                      metadata.target + " packages require nativeBinaryStatus",
                      artifactsLocation(metadata));
  }
}

void verifyNativeBinaryStatus(
    const PackageMetadata &metadata,
    const PackageArtifactRequirementsRecord &requirements,
    DiagnosticEngine &diagnostics) {
  if (!metadata.nativeBinaryStatus) {
    return;
  }

  if (!requirements.requiresNativeBinaryStatus) {
    diagnostics.error(diagnosticCode("unexpected-native-status"),
                      metadata.target +
                          " packages must not declare nativeBinaryStatus",
                      locationOr(metadata.nativeBinaryStatusLocation,
                                 artifactsLocation(metadata)));
    return;
  }

  if (*metadata.nativeBinaryStatus == "planned" &&
      !requirements.allowsPlannedNativeBinary) {
    diagnostics.error(
        diagnosticCode("planned-native-status-disallowed"),
        "package manifest packageArtifactRequirements does not allow "
        "nativeBinaryStatus planned",
        locationOr(metadata.nativeBinaryStatusLocation,
                   artifactsLocation(metadata)));
  }

  const PackageArtifactRecord *nativeBinary =
      findArtifact(metadata, "nativeBinary");
  if (!nativeBinary) {
    diagnostics.error(diagnosticCode("native-status-without-native"),
                      "nativeBinaryStatus requires nativeBinary",
                      locationOr(metadata.nativeBinaryStatusLocation,
                                 artifactsLocation(metadata)));
    return;
  }

  if (*metadata.nativeBinaryStatus == "planned" && nativeBinary->exists) {
    diagnostics.error(
        diagnosticCode("planned-native-status-with-produced-native"),
        "nativeBinaryStatus planned requires the nativeBinary artifact path to "
        "be declared but not produced",
        artifactLocation(metadata, *nativeBinary));
  }
}

void verifyDebugArtifacts(const PackageMetadata &metadata,
                          DiagnosticEngine &diagnostics) {
  const PackageArtifactRecord *sourceRemap =
      findArtifact(metadata, "sourceRemap");
  if (sourceRemap &&
      !(metadata.debugMetadataArtifactPresent &&
        metadata.hirSourceMapArtifactPresent)) {
    diagnostics.error(
        diagnosticCode("source-remap-without-debug-artifacts"),
        artifactLabel("sourceRemap", sourceRemap) +
            " requires debugMetadata and hirSourceMap",
        artifactLocation(metadata, *sourceRemap));
  }

  if (metadata.debugMetadataArtifactPresent !=
      metadata.hirSourceMapArtifactPresent) {
    const PackageArtifactRecord *debugMetadata =
        findArtifact(metadata, "debugMetadata");
    const PackageArtifactRecord *hirSourceMap =
        findArtifact(metadata, "hirSourceMap");
    SourceLocation location = artifactsLocation(metadata);
    if (debugMetadata) {
      location = artifactLocation(metadata, *debugMetadata);
    } else if (hirSourceMap) {
      location = artifactLocation(metadata, *hirSourceMap);
    }
    std::string message =
        "debugMetadata and hirSourceMap must be emitted together";
    if (debugMetadata && !hirSourceMap) {
      message = "debug artifact pair mismatch: " +
                artifactLabel("debugMetadata", debugMetadata) +
                " requires hirSourceMap";
    } else if (hirSourceMap && !debugMetadata) {
      message = "debug artifact pair mismatch: " +
                artifactLabel("hirSourceMap", hirSourceMap) +
                " requires debugMetadata";
    }
    diagnostics.error(diagnosticCode("debug-artifact-pair"), std::move(message),
                      std::move(location));
  }
}

void verifyDebugArtifactHealth(const PackageMetadata &metadata,
                               DiagnosticEngine &diagnostics) {
  if (!metadata.debugMetadataArtifactPresent ||
      !metadata.hirSourceMapArtifactPresent) {
    return;
  }

  const PackageDebugArtifactHealth health =
      collectPackageDebugArtifactHealth(metadata);
  if (health.health != "drift") {
    return;
  }

  const PackageArtifactRecord *debugMetadata =
      findArtifact(metadata, "debugMetadata");
  const PackageArtifactRecord *hirSourceMap =
      findArtifact(metadata, "hirSourceMap");
  const SourceLocation sourceMapLocation =
      hirSourceMap ? artifactLocation(metadata, *hirSourceMap)
                   : artifactsLocation(metadata);
  const std::string debugMetadataName =
      artifactLabel("debugMetadata", debugMetadata);
  const std::string hirSourceMapName =
      artifactLabel("hirSourceMap", hirSourceMap);

  if (health.hirSourceLocationsMatch && !*health.hirSourceLocationsMatch) {
    diagnostics.error(diagnosticCode("debug-source-locations-mismatch"),
                      hirSourceMapName + " hirSourceLocations must match " +
                          debugMetadataName,
                      sourceMapLocation);
  }
  if (health.sourceMapUnfiltered && !*health.sourceMapUnfiltered) {
    diagnostics.error(diagnosticCode("debug-source-map-filtered"),
                      hirSourceMapName + " must be unfiltered",
                      sourceMapLocation);
  }
  if (health.sourceMapUnpaged && !*health.sourceMapUnpaged) {
    diagnostics.error(diagnosticCode("debug-source-map-paged"),
                      hirSourceMapName + " pagination must be inactive",
                      sourceMapLocation);
  }
  if (health.sourceMapRecordsDisabled && !*health.sourceMapRecordsDisabled) {
    diagnostics.error(diagnosticCode("debug-source-map-records-enabled"),
                      hirSourceMapName + " records must be disabled",
                      sourceMapLocation);
  }
  if (health.sourceMapCategoryCountsConsistent &&
      !*health.sourceMapCategoryCountsConsistent) {
    diagnostics.error(diagnosticCode("debug-source-map-category-counts"),
                      hirSourceMapName +
                          " categoryCounts must match hirSourceLocations",
                      sourceMapLocation);
  }
  if (health.recordsTotalCountMatchesCategoryCounts &&
      !*health.recordsTotalCountMatchesCategoryCounts) {
    diagnostics.error(
        diagnosticCode("debug-source-map-record-total"),
        hirSourceMapName +
            " records.totalCount must match categoryCounts.recordTotalCount",
        sourceMapLocation);
  }
  if (health.sourceRemap.artifactPresent &&
      health.sourceRemap.health != "ok") {
    const PackageArtifactRecord *sourceRemap =
        findArtifact(metadata, "sourceRemap");
    diagnostics.error(diagnosticCode("source-remap-provenance-invalid"),
                      artifactLabel("sourceRemap", sourceRemap) +
                          " provenance health must be ok",
                      sourceRemap ? artifactLocation(metadata, *sourceRemap)
                                  : artifactsLocation(metadata));
  }
}

void verifyNativeArtifactDescriptor(
    const PackageMetadata &metadata,
    const PackageArtifactRequirementsRecord &requirements,
    DiagnosticEngine &diagnostics) {
  const PackageArtifactRecord *descriptor =
      findArtifact(metadata, "nativeArtifactDescriptor");
  if (descriptor == nullptr) {
    const std::optional<std::string> nativeBinaryStatus =
        packageVerifyNativeBinaryStatus(metadata);
    const bool nativeReady =
        requirements.packageMode == "native" ||
        (nativeBinaryStatus && *nativeBinaryStatus != "planned");
    if (nativeReady) {
      diagnostics.error(
          diagnosticCode("native-artifact-descriptor-required"),
          metadata.target +
              " native-ready package verification requires "
              "nativeArtifactDescriptor artifact evidence",
          artifactsLocation(metadata));
    }
    return;
  }

  const SourceLocation location = artifactLocation(metadata, *descriptor);
  const PackageNativeArtifactDescriptorHealth health =
      collectPackageNativeArtifactDescriptorHealth(metadata);
  if (!health.descriptorExists) {
    diagnostics.error(diagnosticCode("native-artifact-descriptor-missing"),
                      "native artifact descriptor does not exist: " +
                          descriptor->path,
                      location);
    return;
  }

  if (health.health == "invalid") {
    diagnostics.error(
        diagnosticCode("native-artifact-descriptor-invalid"),
        "native artifact descriptor must use the native-artifact-v0 contract",
        location);
  }

  const PackageNativeArtifactDescriptorChecks &checks = health.checks;
  if (checks.targetMatchesPackage && !*checks.targetMatchesPackage) {
    diagnostics.error(diagnosticCode("native-artifact-target-mismatch"),
                      "native artifact descriptor target must match package "
                      "target '" +
                          metadata.target + "'",
                      location);
  }
  if (checks.nativeBinaryStatusMatchesPackage &&
      !*checks.nativeBinaryStatusMatchesPackage) {
    const std::optional<std::string> expected =
        packageVerifyNativeBinaryStatus(metadata);
    diagnostics.error(diagnosticCode("native-artifact-status-mismatch"),
                      "native artifact descriptor nativeBinaryStatus must "
                      "match package status '" +
                          (expected ? *expected : std::string("null")) + "'",
                      location);
  }
  if (checks.sourcePathMatchesManifest && !*checks.sourcePathMatchesManifest) {
    diagnostics.error(
        diagnosticCode("native-artifact-source-path-mismatch"),
        "native artifact descriptor sourcePath must match manifest source "
        "artifact",
        location);
  }
  if (checks.sourceHashMatchesFile && !*checks.sourceHashMatchesFile) {
    diagnostics.error(
        diagnosticCode("native-artifact-source-hash-mismatch"),
        "native artifact descriptor sourceHash must match sourcePath '" +
            health.sourcePath.value_or(std::string()) + "'",
        location);
  }
  if (checks.artifactPathMatchesManifest &&
      !*checks.artifactPathMatchesManifest) {
    diagnostics.error(
        diagnosticCode("native-artifact-path-mismatch"),
        "native artifact descriptor artifactPath must match manifest "
        "artifacts.nativeBinary",
        location);
  }
  if (checks.artifactHashMatchesFile && !*checks.artifactHashMatchesFile) {
    diagnostics.error(
        diagnosticCode("native-artifact-hash-mismatch"),
        "native artifact descriptor artifactHash must match artifactPath '" +
            health.artifactPath.value_or(std::string()) + "'",
        location);
  }
  if (checks.sizeBytesMatchesFile && !*checks.sizeBytesMatchesFile) {
    diagnostics.error(
        diagnosticCode("native-artifact-size-mismatch"),
        "native artifact descriptor sizeBytes must match artifactPath '" +
            health.artifactPath.value_or(std::string()) + "'",
        location);
  }
  if (checks.validationStatusMatchesNativeStatus &&
      !*checks.validationStatusMatchesNativeStatus) {
    diagnostics.error(
        diagnosticCode("native-artifact-validation-status-mismatch"),
        "native artifact descriptor validationStatus and nativeBinaryStatus "
        "must agree on validated state",
        location);
  }
}

void verifyTargetLegalizationEvidence(const PackageMetadata &metadata,
                                      DiagnosticEngine &diagnostics) {
  const PackageTargetLegalizationEvidence evidence =
      collectPackageTargetLegalizationEvidence(metadata);

  if (evidence.manifestToolRequirementsTargetMatchesPackage &&
      !*evidence.manifestToolRequirementsTargetMatchesPackage &&
      metadata.targetLegalizationToolRequirements) {
    diagnostics.error(
        diagnosticCode("target-legalization-manifest-tool-target-mismatch"),
        "targetLegalizationToolRequirements target must match package target '" +
            metadata.target + "'",
        metadata.targetLegalizationToolRequirements->targetLocation.value_or(
            metadata.targetLegalizationToolRequirements->location));
  }

  if (evidence.manifestToolRequirementsPackageModeMatchesRequirements &&
      !*evidence.manifestToolRequirementsPackageModeMatchesRequirements &&
      metadata.targetLegalizationToolRequirements) {
    diagnostics.error(
        diagnosticCode(
            "target-legalization-manifest-tool-package-mode-mismatch"),
        "targetLegalizationToolRequirements.packageMode must match "
        "packageArtifactRequirements.packageMode",
        metadata.targetLegalizationToolRequirements->packageModeLocation
            .value_or(metadata.targetLegalizationToolRequirements->location));
  }

  if (evidence.manifestToolRequirementEvidenceIdsPresent &&
      !*evidence.manifestToolRequirementEvidenceIdsPresent &&
      metadata.targetLegalizationToolRequirements) {
    diagnostics.error(
        diagnosticCode("target-legalization-manifest-tool-evidence-missing"),
        "targetLegalizationToolRequirements.toolRequirementEvidenceIds must "
        "record tool requirement evidence",
        metadata.targetLegalizationToolRequirements
            ->toolRequirementEvidenceIdsLocation.value_or(
                metadata.targetLegalizationToolRequirements->location));
  }

  if (evidence.debugMetadataTargetMatchesPackage &&
      !*evidence.debugMetadataTargetMatchesPackage) {
    const PackageArtifactRecord *debugMetadata =
        findArtifact(metadata, "debugMetadata");
    diagnostics.error(
        diagnosticCode("target-legalization-debug-metadata-target-mismatch"),
        "debugMetadata target legalization evidence target must match package "
        "target '" +
            metadata.target + "'",
        debugMetadata ? artifactLocation(metadata, *debugMetadata)
                      : artifactsLocation(metadata));
  }

  if (sidecarProjectionIncomplete(evidence.debugMetadata)) {
    const PackageArtifactRecord *debugMetadata =
        findArtifact(metadata, "debugMetadata");
    diagnostics.error(
        diagnosticCode("target-legalization-debug-metadata-incomplete"),
        "debugMetadata target legalization projection evidence must include "
        "selected target, supported package state, packageMode, and "
        "legalizationCoreEvidenceIds",
        debugMetadata ? artifactLocation(metadata, *debugMetadata)
                      : artifactsLocation(metadata));
  }

  if (evidence.debugMetadata.packageBuildSupported &&
      !*evidence.debugMetadata.packageBuildSupported) {
    const PackageArtifactRecord *debugMetadata =
        findArtifact(metadata, "debugMetadata");
    diagnostics.error(
        diagnosticCode("target-legalization-debug-metadata-unsupported"),
        "debugMetadata target legalization projection rejects package target "
        "'" +
            metadata.target + "'",
        debugMetadata ? artifactLocation(metadata, *debugMetadata)
                      : artifactsLocation(metadata));
  }

  if (evidence.targetExplanationTargetMatchesPackage &&
      !*evidence.targetExplanationTargetMatchesPackage) {
    const PackageArtifactRecord *targetExplanation =
        findArtifact(metadata, "targetExplanation");
    diagnostics.error(
        diagnosticCode(
            "target-legalization-target-explanation-target-mismatch"),
        "targetExplanation target legalization evidence target must match "
        "package target '" +
            metadata.target + "'",
        targetExplanation ? artifactLocation(metadata, *targetExplanation)
                          : artifactsLocation(metadata));
  }

  if (sidecarProjectionIncomplete(evidence.targetExplanation)) {
    const PackageArtifactRecord *targetExplanation =
        findArtifact(metadata, "targetExplanation");
    diagnostics.error(
        diagnosticCode("target-legalization-target-explanation-incomplete"),
        "targetExplanation target legalization projection evidence must "
        "include target, supported package state, packageMode, and "
        "legalizationCoreEvidenceIds",
        targetExplanation ? artifactLocation(metadata, *targetExplanation)
                          : artifactsLocation(metadata));
  }

  if (evidence.targetExplanation.packageBuildSupported &&
      !*evidence.targetExplanation.packageBuildSupported) {
    const PackageArtifactRecord *targetExplanation =
        findArtifact(metadata, "targetExplanation");
    diagnostics.error(
        diagnosticCode("target-legalization-target-explanation-unsupported"),
        "targetExplanation target legalization projection rejects package "
        "target '" +
            metadata.target + "'",
        targetExplanation ? artifactLocation(metadata, *targetExplanation)
                          : artifactsLocation(metadata));
  }

  if (evidence.debugMetadataPackageModeMatchesRequirements &&
      !*evidence.debugMetadataPackageModeMatchesRequirements) {
    const PackageArtifactRecord *debugMetadata =
        findArtifact(metadata, "debugMetadata");
    const std::string expected =
        metadata.artifactRequirements
            ? metadata.artifactRequirements->packageMode
            : std::string("unknown");
    diagnostics.error(
        diagnosticCode(
            "target-legalization-debug-metadata-package-mode-mismatch"),
        "debugMetadata target legalization packageMode must match "
        "packageArtifactRequirements.packageMode '" +
            expected + "'",
        debugMetadata ? artifactLocation(metadata, *debugMetadata)
                      : artifactsLocation(metadata));
  }

  if (metadata.artifactRequirements &&
      sidecarRequirementEvidenceIdsDrift(
          evidence.debugMetadata,
          evidence.packageArtifactRequirementEvidenceIds)) {
    const PackageArtifactRecord *debugMetadata =
        findArtifact(metadata, "debugMetadata");
    diagnostics.error(
        diagnosticCode(
            "target-legalization-debug-metadata-requirement-evidence-mismatch"),
        "debugMetadata target legalization "
        "packageArtifactRequirementEvidenceIds must match recorded "
        "packageArtifactRequirements.evidenceIds",
        debugMetadata ? artifactLocation(metadata, *debugMetadata)
                      : artifactsLocation(metadata));
  }

  if (evidence.debugMetadataToolRequirementsMatchManifest &&
      !*evidence.debugMetadataToolRequirementsMatchManifest) {
    const PackageArtifactRecord *debugMetadata =
        findArtifact(metadata, "debugMetadata");
    diagnostics.error(
        diagnosticCode(
            "target-legalization-debug-metadata-tool-requirements-mismatch"),
        "debugMetadata target legalization tool requirements must match "
        "manifest targetLegalizationToolRequirements",
        debugMetadata ? artifactLocation(metadata, *debugMetadata)
                      : artifactsLocation(metadata));
  }

  if (evidence.targetExplanationPackageModeMatchesRequirements &&
      !*evidence.targetExplanationPackageModeMatchesRequirements) {
    const PackageArtifactRecord *targetExplanation =
        findArtifact(metadata, "targetExplanation");
    const std::string expected =
        metadata.artifactRequirements
            ? metadata.artifactRequirements->packageMode
            : std::string("unknown");
    diagnostics.error(
        diagnosticCode(
            "target-legalization-target-explanation-package-mode-mismatch"),
        "targetExplanation target legalization packageMode must match "
        "packageArtifactRequirements.packageMode '" +
            expected + "'",
        targetExplanation ? artifactLocation(metadata, *targetExplanation)
                          : artifactsLocation(metadata));
  }

  if (evidence.targetExplanationToolRequirementsMatchManifest &&
      !*evidence.targetExplanationToolRequirementsMatchManifest) {
    const PackageArtifactRecord *targetExplanation =
        findArtifact(metadata, "targetExplanation");
    diagnostics.error(
        diagnosticCode("target-legalization-target-explanation-"
                       "tool-requirements-mismatch"),
        "targetExplanation target legalization tool requirements must match "
        "manifest targetLegalizationToolRequirements",
        targetExplanation ? artifactLocation(metadata, *targetExplanation)
                          : artifactsLocation(metadata));
  }

  if (metadata.artifactRequirements &&
      sidecarRequirementEvidenceIdsDrift(
          evidence.targetExplanation,
          evidence.packageArtifactRequirementEvidenceIds)) {
    const PackageArtifactRecord *targetExplanation =
        findArtifact(metadata, "targetExplanation");
    diagnostics.error(
        diagnosticCode("target-legalization-target-explanation-"
                       "requirement-evidence-mismatch"),
        "targetExplanation target legalization "
        "packageArtifactRequirementEvidenceIds must match recorded "
        "packageArtifactRequirements.evidenceIds",
        targetExplanation ? artifactLocation(metadata, *targetExplanation)
                          : artifactsLocation(metadata));
  }
}

void verifyArtifacts(const PackageMetadata &metadata,
                     const PackageArtifactRequirementsRecord &requirements,
                     DiagnosticEngine &diagnostics) {
  for (const PackageArtifactRecord &artifact : metadata.artifacts) {
    if (artifact.pathIssue != PackagePathIssue::None) {
      std::string message = "package artifact '" + artifact.name + "' " +
                            artifactPathIssueMessage(artifact.pathIssue);
      if (!artifact.path.empty()) {
        message += ": " + artifact.path;
      }
      diagnostics.error(diagnosticCode("invalid-artifact-path"),
                        std::move(message),
                        artifactLocation(metadata, artifact));
      continue;
    }

    if (!artifact.pathExists &&
        !allowsPlannedNativeBinary(metadata, artifact, requirements)) {
      diagnostics.error(diagnosticCode("missing-artifact"),
                        "package artifact '" + artifact.name +
                            "' does not exist: " + artifact.path,
                        artifactLocation(metadata, artifact));
      continue;
    }

    if (!artifact.exists &&
        !allowsPlannedNativeBinary(metadata, artifact, requirements)) {
      diagnostics.error(diagnosticCode("artifact-not-file"),
                        "package artifact '" + artifact.name +
                            "' is not a file: " + artifact.path,
                        artifactLocation(metadata, artifact));
    }
  }
}

void verifyReflectionNativeBinary(const PackageMetadata &metadata,
                                  DiagnosticEngine &diagnostics) {
  if (!metadata.reflectionNativeBinary ||
      metadata.reflectionNativeBinary->empty()) {
    return;
  }

  const PackagePathIssue pathIssue =
      packagePathIssue(*metadata.reflectionNativeBinary);
  if (pathIssue != PackagePathIssue::None) {
    diagnostics.error(diagnosticCode("invalid-reflection-native-binary"),
                      "reflection nativeBinary " +
                          reflectionNativeBinaryPathIssueMessage(pathIssue) +
                          ": " + *metadata.reflectionNativeBinary,
                      locationOr(metadata.reflectionNativeBinaryLocation,
                                 metadata.reflectionLocation));
    return;
  }

  const PackageArtifactRecord *nativeBinary =
      findArtifact(metadata, "nativeBinary");
  if (nativeBinary && nativeBinary->path != *metadata.reflectionNativeBinary) {
    diagnostics.error(diagnosticCode("reflection-native-binary-mismatch"),
                      "reflection nativeBinary must match manifest "
                      "artifacts.nativeBinary: expected '" +
                          nativeBinary->path + "', got '" +
                          *metadata.reflectionNativeBinary + "'",
                      locationOr(metadata.reflectionNativeBinaryLocation,
                                 metadata.reflectionLocation));
  }
}

bool hasReflectionResourceIdentity(
    const PackageReflectionResourceRecord &resource) {
  return !resource.stage.empty() && !resource.name.empty() &&
         !resource.kind.empty();
}

bool hasReflectionTargetResourceBindingIdentity(
    const PackageReflectionTargetResourceBindingRecord &binding) {
  return !binding.stage.empty() && !binding.name.empty() &&
         !binding.kind.empty();
}

bool hasReflectionTargetResourceBindingDuplicateIdentity(
    const PackageReflectionTargetResourceBindingRecord &binding) {
  return !binding.stage.empty() && !binding.entryPoint.empty() &&
         !binding.name.empty();
}

bool reflectionIdentityMatches(
    const PackageReflectionResourceRecord &resource,
    const PackageReflectionTargetResourceBindingRecord &binding) {
  return resource.stage == binding.stage && resource.name == binding.name &&
         resource.kind == binding.kind;
}

bool reflectionTargetBindingDuplicateIdentityMatches(
    const PackageReflectionTargetResourceBindingRecord &left,
    const PackageReflectionTargetResourceBindingRecord &right) {
  return left.target == right.target && left.stage == right.stage &&
         left.entryPoint == right.entryPoint && left.name == right.name &&
         left.kind == right.kind;
}

std::string reflectionIdentityLabel(std::string_view stage,
                                    std::string_view name,
                                    std::string_view kind) {
  return "stage '" + std::string(stage) + "' name '" + std::string(name) +
         "' kind '" + std::string(kind) + "'";
}

std::string reflectionTargetBindingDuplicateIdentityLabel(
    const PackageReflectionTargetResourceBindingRecord &binding) {
  return "stage '" + binding.stage + "' entryPoint '" + binding.entryPoint +
         "' name '" + binding.name + "' kind '" + binding.kind + "'";
}

std::string reflectionResourceLabel(
    const PackageReflectionResourceRecord &resource) {
  if (!resource.name.empty()) {
    return "'" + resource.name + "'";
  }
  return reflectionIdentityLabel(resource.stage, resource.name, resource.kind);
}

std::string reflectionTargetBindingLabel(
    const PackageReflectionTargetResourceBindingRecord &binding) {
  if (!binding.name.empty()) {
    return "'" + binding.name + "'";
  }
  return reflectionIdentityLabel(binding.stage, binding.name, binding.kind);
}

const PackageReflectionTargetResourceBindingRecord *
findSelectedTargetBindingForResource(
    const PackageMetadata &metadata,
    const PackageReflectionResourceRecord &resource) {
  for (const PackageReflectionTargetResourceBindingRecord &binding :
       metadata.reflectionTargetResourceBindings) {
    if (binding.target == metadata.target &&
        hasReflectionTargetResourceBindingIdentity(binding) &&
        reflectionIdentityMatches(resource, binding)) {
      return &binding;
    }
  }
  return nullptr;
}

const PackageReflectionResourceRecord *findReflectionResourceForBinding(
    const PackageMetadata &metadata,
    const PackageReflectionTargetResourceBindingRecord &binding) {
  for (const PackageReflectionResourceRecord &resource :
       metadata.reflectionResources) {
    if (hasReflectionResourceIdentity(resource) &&
        reflectionIdentityMatches(resource, binding)) {
      return &resource;
    }
  }
  return nullptr;
}

const PackageReflectionResourceRecord *findReflectionResourceByName(
    const PackageMetadata &metadata,
    const PackageReflectionTargetResourceBindingRecord &binding) {
  if (binding.name.empty()) {
    return nullptr;
  }
  for (const PackageReflectionResourceRecord &resource :
       metadata.reflectionResources) {
    if (hasReflectionResourceIdentity(resource) &&
        resource.name == binding.name) {
      return &resource;
    }
  }
  return nullptr;
}

std::string optionalUnsignedLabel(std::optional<std::uintmax_t> value) {
  if (!value) {
    return "<missing>";
  }
  return std::to_string(*value);
}

std::string optionalStringLabel(const std::optional<std::string> &value) {
  if (!value) {
    return "<missing>";
  }
  return "'" + *value + "'";
}

std::string canonicalReflectionAddressSpace(std::string_view addressSpace) {
  if (addressSpace == "shared" || addressSpace == "groupshared" ||
      addressSpace == "threadgroup" || addressSpace == "Workgroup") {
    return "workgroup-shared";
  }
  return std::string(addressSpace);
}

bool reflectionAddressSpacesMatch(
    const std::optional<std::string> &resourceAddressSpace,
    const std::optional<std::string> &bindingAddressSpace) {
  if (!resourceAddressSpace || !bindingAddressSpace) {
    return resourceAddressSpace == bindingAddressSpace;
  }
  return canonicalReflectionAddressSpace(*resourceAddressSpace) ==
         canonicalReflectionAddressSpace(*bindingAddressSpace);
}

std::optional<std::uintmax_t>
fixedArrayElementCountFromDimensions(std::string_view arrayDimensionsJson) {
  const std::optional<std::vector<std::string_view>> dimensions =
      jsonArrayElements(arrayDimensionsJson);
  if (!dimensions || dimensions->empty()) {
    return std::nullopt;
  }

  std::uintmax_t product = 1;
  for (std::string_view dimension : *dimensions) {
    const std::optional<std::string> kind = objectStringMember(dimension, "kind");
    if (!kind || *kind != "fixed") {
      return std::nullopt;
    }
    const std::optional<std::uintmax_t> elementCount =
        objectUnsignedMember(dimension, "elementCount");
    if (!elementCount) {
      return std::nullopt;
    }
    if (*elementCount != 0 &&
        product > std::numeric_limits<std::uintmax_t>::max() / *elementCount) {
      return std::nullopt;
    }
    product *= *elementCount;
  }
  return product;
}

void diagnoseReflectionBindingMismatch(
    const PackageReflectionTargetResourceBindingRecord &binding,
    std::string field, std::string expected, std::string actual,
    DiagnosticEngine &diagnostics) {
  diagnostics.error(diagnosticCode("reflection-target-resource-identity-"
                                   "mismatch"),
                    "reflection target resource binding " +
                        reflectionTargetBindingLabel(binding) + " " + field +
                        " must match reflected resource: expected " + expected +
                        ", got " + actual,
                    binding.location);
}

void diagnoseReflectionBindingArrayMismatch(
    const PackageReflectionTargetResourceBindingRecord &binding,
    std::string field, std::string expected, std::string actual,
    DiagnosticEngine &diagnostics) {
  diagnostics.error(diagnosticCode("reflection-target-resource-binding-array-"
                                   "mismatch"),
                    "reflection selected-target resource binding " +
                        reflectionTargetBindingLabel(binding) + " " + field +
                        " must match reflected resource array metadata: expected " +
                        expected + ", got " + actual,
                    binding.location);
}

void verifyReflectionBindingResourceFields(
    const PackageReflectionResourceRecord &resource,
    const PackageReflectionTargetResourceBindingRecord &binding,
    DiagnosticEngine &diagnostics) {
  if (binding.sourceType != resource.type) {
    diagnoseReflectionBindingMismatch(
        binding, "sourceType", "'" + resource.type + "'",
        "'" + binding.sourceType + "'", diagnostics);
  }
  if (binding.arrayDimensionsJson != resource.arrayDimensionsJson) {
    diagnoseReflectionBindingArrayMismatch(binding, "arrayDimensions",
                                           resource.arrayDimensionsJson,
                                           binding.arrayDimensionsJson,
                                           diagnostics);
  }
  const std::optional<std::uintmax_t> resourceFixedArrayElementCount =
      fixedArrayElementCountFromDimensions(resource.arrayDimensionsJson);
  if (resourceFixedArrayElementCount && !binding.arrayElementCount) {
    diagnoseReflectionBindingArrayMismatch(
        binding, "arrayElementCount",
        std::to_string(*resourceFixedArrayElementCount), "<missing>",
        diagnostics);
  } else if (resourceFixedArrayElementCount &&
             *resourceFixedArrayElementCount != *binding.arrayElementCount) {
    diagnoseReflectionBindingArrayMismatch(
        binding, "arrayElementCount",
        std::to_string(*resourceFixedArrayElementCount),
        std::to_string(*binding.arrayElementCount), diagnostics);
  }
  if (binding.set != resource.set) {
    diagnoseReflectionBindingMismatch(binding, "set",
                                      optionalUnsignedLabel(resource.set),
                                      optionalUnsignedLabel(binding.set),
                                      diagnostics);
  }
  if (binding.binding != resource.binding) {
    diagnoseReflectionBindingMismatch(binding, "binding",
                                      optionalUnsignedLabel(resource.binding),
                                      optionalUnsignedLabel(binding.binding),
                                      diagnostics);
  }
  if (resource.addressSpace &&
      !reflectionAddressSpacesMatch(resource.addressSpace,
                                    binding.addressSpace)) {
    diagnoseReflectionBindingMismatch(
        binding, "addressSpace", optionalStringLabel(resource.addressSpace),
        optionalStringLabel(binding.addressSpace), diagnostics);
  }
  if ((resource.storageImageFormat || binding.storageImageFormat) &&
      binding.storageImageFormat != resource.storageImageFormat) {
    diagnoseReflectionBindingMismatch(
        binding, "storageImageFormat",
        optionalStringLabel(resource.storageImageFormat),
        optionalStringLabel(binding.storageImageFormat), diagnostics);
  }
  if ((resource.storageImageAccess || binding.storageImageAccess) &&
      binding.storageImageAccess != resource.storageImageAccess) {
    diagnoseReflectionBindingMismatch(
        binding, "storageImageAccess",
        optionalStringLabel(resource.storageImageAccess),
        optionalStringLabel(binding.storageImageAccess), diagnostics);
  }
}

void verifyReflectionTargetResourceBindings(const PackageMetadata &metadata,
                                            DiagnosticEngine &diagnostics) {
  for (auto binding = metadata.reflectionTargetResourceBindings.begin();
       binding != metadata.reflectionTargetResourceBindings.end(); ++binding) {
    if (binding->target != metadata.target ||
        !hasReflectionTargetResourceBindingDuplicateIdentity(*binding)) {
      continue;
    }
    const auto duplicate =
        std::find_if(metadata.reflectionTargetResourceBindings.begin(), binding,
                     [&](const PackageReflectionTargetResourceBindingRecord
                             &candidate) {
                       return candidate.target == metadata.target &&
                              hasReflectionTargetResourceBindingDuplicateIdentity(
                                  candidate) &&
                              reflectionTargetBindingDuplicateIdentityMatches(
                                  candidate, *binding);
                     });
    if (duplicate == binding) {
      continue;
    }
    diagnostics.error(
        diagnosticCode("reflection-target-resource-binding-duplicate"),
        "reflection selected-target resource binding " +
            reflectionTargetBindingDuplicateIdentityLabel(*binding) +
            " duplicates an earlier binding for target '" + metadata.target +
            "'",
        binding->location);
  }

  for (const PackageReflectionResourceRecord &resource :
       metadata.reflectionResources) {
    if (!hasReflectionResourceIdentity(resource)) {
      continue;
    }
    if (findSelectedTargetBindingForResource(metadata, resource) == nullptr) {
      diagnostics.error(
          diagnosticCode("reflection-resource-target-binding-missing"),
          "reflection resource " + reflectionResourceLabel(resource) +
              " is missing selected-target resource binding for target '" +
              metadata.target + "'",
          resource.location);
    }
  }

  for (const PackageReflectionTargetResourceBindingRecord &binding :
       metadata.reflectionTargetResourceBindings) {
    if (binding.target != metadata.target ||
        !hasReflectionTargetResourceBindingIdentity(binding)) {
      continue;
    }

    const PackageReflectionResourceRecord *resource =
        findReflectionResourceForBinding(metadata, binding);
    if (resource != nullptr) {
      verifyReflectionBindingResourceFields(*resource, binding, diagnostics);
      continue;
    }

    const PackageReflectionResourceRecord *sameNameResource =
        findReflectionResourceByName(metadata, binding);
    if (sameNameResource != nullptr) {
      diagnostics.error(
          diagnosticCode("reflection-target-resource-identity-mismatch"),
          "reflection target resource binding " +
              reflectionTargetBindingLabel(binding) +
              " identity must match reflected resource: expected " +
              reflectionIdentityLabel(sameNameResource->stage,
                                      sameNameResource->name,
                                      sameNameResource->kind) +
              ", got " +
              reflectionIdentityLabel(binding.stage, binding.name,
                                      binding.kind),
          binding.location);
      continue;
    }

    diagnostics.error(
        diagnosticCode("reflection-target-binding-source-missing"),
        "reflection selected-target resource binding " +
            reflectionTargetBindingLabel(binding) +
            " has no reflected source resource for target '" + metadata.target +
            "'",
        binding.location);
  }
}

bool isLowercaseSha256(std::string_view value) {
  if (value.size() != 64) {
    return false;
  }
  for (const char ch : value) {
    const bool digit = ch >= '0' && ch <= '9';
    const bool lowerHex = ch >= 'a' && ch <= 'f';
    if (!digit && !lowerHex) {
      return false;
    }
  }
  return true;
}

bool verifySourceHashMetadata(const PackageMetadata &metadata,
                              DiagnosticEngine &diagnostics) {
  if (!metadata.sourceHashAlgorithm || !metadata.sourceHashValue) {
    diagnostics.error(diagnosticCode("missing-source-hash"),
                      "package manifest sourceHash must contain string "
                      "algorithm and value fields",
                      sourceHashLocation(metadata));
    return false;
  }

  if (*metadata.sourceHashAlgorithm != "sha256") {
    diagnostics.error(diagnosticCode("unsupported-source-hash"),
                      "package manifest sourceHash.algorithm must be sha256",
                      sourceHashAlgorithmLocation(metadata));
    return false;
  }

  if (!isLowercaseSha256(*metadata.sourceHashValue)) {
    diagnostics.error(diagnosticCode("invalid-source-hash"),
                      "package manifest sourceHash.value must be 64 "
                      "lowercase hexadecimal sha256",
                      sourceHashValueLocation(metadata));
    return false;
  }

  return true;
}

void writeNullableString(std::ostream &out,
                         const std::optional<std::string> &value) {
  if (value) {
    out << "\"" << escapeJson(*value) << "\"";
  } else {
    out << "null";
  }
}

void writeNullableBool(std::ostream &out, const std::optional<bool> &value) {
  if (value) {
    out << (*value ? "true" : "false");
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

void writeNullableStringArray(
    std::ostream &out, const std::optional<std::vector<std::string>> &values) {
  if (values) {
    writeStringArray(out, *values);
  } else {
    out << "null";
  }
}

void writeNativeArtifactDescriptorSummary(
    std::ostream &out, const PackageNativeArtifactDescriptorHealth &health) {
  out << "{\n"
      << "      \"artifactPresent\": "
      << (health.artifactPresent ? "true" : "false") << ",\n"
      << "      \"descriptorExists\": "
      << (health.descriptorExists ? "true" : "false") << ",\n"
      << "      \"health\": \"" << escapeJson(health.health) << "\",\n"
      << "      \"path\": ";
  writeNullableString(out, health.path);
  out << ",\n"
      << "      \"optimizationLevel\": ";
  writeNullableString(out, health.optimizationLevel);
  out << ",\n"
      << "      \"optimizationEvidence\": ";
  if (health.optimizationEvidence && !health.optimizationEvidence->empty() &&
      health.optimizationEvidence->front() == '{') {
    out << *health.optimizationEvidence;
  } else {
    out << "null";
  }
  out << "\n"
      << "    }";
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
      << indent << "  \"health\": \"" << escapeJson(evidence.health) << "\",\n"
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
  out << ",\n" << indent << "  \"packageArtifactRequirementEvidenceIds\": ";
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
  out << ",\n" << indent << "    \"targetExplanationTargetMatchesPackage\": ";
  writeNullableBool(out, evidence.targetExplanationTargetMatchesPackage);
  out << ",\n"
      << indent << "    \"debugMetadataPackageModeMatchesRequirements\": ";
  writeNullableBool(out, evidence.debugMetadataPackageModeMatchesRequirements);
  out << ",\n"
      << indent << "    \"targetExplanationPackageModeMatchesRequirements\": ";
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
      << indent << "    \"packageArtifactRequirementEvidenceIdsPresent\": ";
  writeNullableBool(out, evidence.packageArtifactRequirementEvidenceIdsPresent);
  out << "\n" << indent << "  }\n" << indent << "}";
}

std::optional<std::string> readSourceFile(const std::filesystem::path &path,
                                          DiagnosticEngine &diagnostics) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    diagnostics.error(diagnosticCode("source-read-failed"),
                      "failed to read source file: " + path.string(),
                      sourcePathLocation(path));
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    diagnostics.error(diagnosticCode("source-read-failed"),
                      "failed to read source file: " + path.string(),
                      sourcePathLocation(path));
    return std::nullopt;
  }
  return buffer.str();
}

void verifySourceHashValue(const PackageMetadata &metadata,
                           const std::filesystem::path &sourcePath,
                           DiagnosticEngine &diagnostics) {
  const std::optional<std::string> source =
      readSourceFile(sourcePath, diagnostics);
  if (!source) {
    return;
  }

  const std::string expected = sha256(*source);
  if (*metadata.sourceHashValue != expected) {
    diagnostics.error(diagnosticCode("source-hash-mismatch"),
                      "expected source hash " + expected + ", got '" +
                          *metadata.sourceHashValue + "'",
                      sourceHashValueLocation(metadata));
  }
}

void verifyPlannedNativeSourceEvidence(
    const PackageMetadata &metadata,
    const PackageArtifactRequirementsRecord &requirements,
    const std::optional<std::filesystem::path> &sourcePath,
    DiagnosticEngine &diagnostics) {
  if (sourcePath || !metadata.nativeBinaryStatus ||
      *metadata.nativeBinaryStatus != "planned") {
    return;
  }

  if (!requirements.requiresNativeBinaryStatus ||
      !requirements.allowsPlannedNativeSourceEvidence) {
    return;
  }

  diagnostics.error(
      diagnosticCode("source-required-for-planned-native"),
      metadata.target +
          " packages with nativeBinaryStatus planned require --source to "
          "verify sourceHash",
      locationOr(metadata.nativeBinaryStatusLocation,
                 artifactsLocation(metadata)));
}

void verifyPackageMetadata(
    const PackageMetadata &metadata,
    const std::optional<std::filesystem::path> &sourcePath,
    DiagnosticEngine &diagnostics) {
  const PackageArtifactRequirementsRecord requirements =
      packageArtifactRequirementsForVerification(metadata);
  noteLegacyArtifactRequirementsFallback(metadata, diagnostics);
  if (!verifyArtifactRequirementsForVerification(metadata, requirements,
                                                 diagnostics)) {
    return;
  }
  verifyRequiredArtifacts(metadata, requirements, diagnostics);
  verifyNativeBinaryStatus(metadata, requirements, diagnostics);
  verifyDebugArtifacts(metadata, diagnostics);
  verifyArtifacts(metadata, requirements, diagnostics);
  verifyDebugArtifactHealth(metadata, diagnostics);
  verifyNativeArtifactDescriptor(metadata, requirements, diagnostics);
  verifyTargetLegalizationEvidence(metadata, diagnostics);
  verifyReflectionNativeBinary(metadata, diagnostics);
  verifyReflectionTargetResourceBindings(metadata, diagnostics);
  verifyPlannedNativeSourceEvidence(metadata, requirements, sourcePath,
                                    diagnostics);
  const bool sourceHashMetadataValid =
      verifySourceHashMetadata(metadata, diagnostics);
  if (sourcePath && sourceHashMetadataValid) {
    verifySourceHashValue(metadata, *sourcePath, diagnostics);
  }
}

void writeSummary(std::ostream &out, const PackageMetadata &metadata) {
  const PackageNativeArtifactDescriptorHealth nativeArtifactDescriptor =
      collectPackageNativeArtifactDescriptorHealth(metadata);
  const PackageTargetLegalizationEvidence targetLegalizationEvidence =
      collectPackageTargetLegalizationEvidence(metadata);
  out << "{\n"
      << "    \"module\": \"" << escapeJson(metadata.module) << "\",\n"
      << "    \"target\": \"" << escapeJson(metadata.target) << "\",\n"
      << "    \"nativeBinaryStatus\": ";
  if (const std::optional<std::string> nativeBinaryStatus =
          packageVerifyNativeBinaryStatus(metadata)) {
    out << "\"" << escapeJson(*nativeBinaryStatus) << "\"";
  } else {
    out << "null";
  }
  out << ",\n"
      << "    \"artifactCount\": " << metadata.artifacts.size() << ",\n"
      << "    \"debugArtifactsPresent\": "
      << (metadata.debugArtifactsPresent ? "true" : "false") << ",\n"
      << "    \"nativeArtifactDescriptor\": ";
  writeNativeArtifactDescriptorSummary(out, nativeArtifactDescriptor);
  if (targetLegalizationEvidence.health != "not-present") {
    out << ",\n"
        << "    \"targetLegalizationEvidence\": ";
    writeTargetLegalizationEvidence(out, targetLegalizationEvidence, "    ");
  }
  out << "\n"
      << "  }";
}

void writeDiagnosticRecord(std::ostream &out, const Diagnostic &diagnostic,
                           std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"severity\": \""
      << escapeJson(toString(diagnostic.severity)) << "\",\n"
      << indent << "  \"code\": \"" << escapeJson(diagnostic.code) << "\",\n"
      << indent << "  \"message\": \"" << escapeJson(diagnostic.message)
      << "\",\n"
      << indent << "  \"location\": {\n"
      << indent << "    \"file\": \"" << escapeJson(diagnostic.location.file)
      << "\",\n"
      << indent << "    \"line\": " << diagnostic.location.line << ",\n"
      << indent << "    \"column\": " << diagnostic.location.column << ",\n"
      << indent << "    \"offset\": " << diagnostic.location.offset << ",\n"
      << indent << "    \"length\": " << diagnostic.location.length << ",\n"
      << indent << "    \"endLine\": " << diagnostic.location.endLine << ",\n"
      << indent << "    \"endColumn\": " << diagnostic.location.endColumn
      << ",\n"
      << indent << "    \"endOffset\": " << diagnostic.location.endOffset
      << "\n"
      << indent << "  }";
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

} // namespace

PackageIntegrityResult
verifyPackage(const std::filesystem::path &packagePath,
              std::optional<std::filesystem::path> sourcePath) {
  DiagnosticEngine diagnostics;
  PackageIntegrityResult result;

  PackageMetadataLoadOptions options;
  options.diagnosticCodePrefix = "package.verify";
  options.commandName = "package verify";

  std::optional<PackageMetadata> metadata =
      loadPackageMetadata(packagePath, diagnostics, options);
  if (!metadata) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  verifyPackageMetadata(*metadata, sourcePath, diagnostics);
  result.success = !diagnostics.hasErrors();
  result.metadata = std::move(*metadata);
  result.diagnostics = diagnostics.diagnostics();
  return result;
}

std::string packageVerifyJson(const PackageIntegrityResult &result,
                              const std::filesystem::path &packagePath) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"packagePath\": \""
      << escapeJson(packagePath.lexically_normal().generic_string()) << "\",\n"
      << "  \"success\": " << (result.success ? "true" : "false") << ",\n"
      << "  \"summary\": ";
  if (result.metadata) {
    writeSummary(out, *result.metadata);
  } else {
    out << "null";
  }
  if (result.metadata) {
    const PackageGraphicsAbiHealth graphicsAbi =
        collectPackageGraphicsAbiHealth(*result.metadata);
    if (graphicsAbi.artifactPresent) {
      out << ",\n"
          << "  \"graphicsAbi\": ";
      writeGraphicsAbiHealth(out, graphicsAbi, "  ");
    }
  }
  out << ",\n"
      << "  \"diagnosticCounts\": {\n"
      << "    \"note\": "
      << countDiagnostics(result.diagnostics, DiagnosticSeverity::Note) << ",\n"
      << "    \"warning\": "
      << countDiagnostics(result.diagnostics, DiagnosticSeverity::Warning)
      << ",\n"
      << "    \"error\": "
      << countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) << "\n"
      << "  },\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics);
  out << "\n}\n";
  return out.str();
}

} // namespace crossgl
