#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

namespace crossgl {

struct HIRModule;
struct TargetLegalizationContract;

struct TargetExplanationTargetRecord {
  std::string target;
  bool nativeImplemented = false;
  bool sourcePackageSupported = false;
  bool packageBuildSupported = false;
  std::string supportStatus;
  std::string legalizationState;
  std::string packageMode;
  std::string packageDecisionProvenance;
  std::string packageDecisionReason;
  std::vector<std::string> decisionReasonCodes;
  std::size_t packageRankScore = 0;
  std::string targetBackend;
  std::vector<std::string> artifactLinks;
  std::vector<std::string> reportLinks;
  std::string remediation;
  std::size_t requiredCapabilityCount = 0;
  std::size_t missingCapabilityCount = 0;
  std::vector<std::string> requiredCapabilities;
  std::vector<std::string> missingCapabilities;
  std::vector<std::string> legalizationCoreEvidenceIds;
  std::vector<std::string> diagnosticEvidenceIds;
  std::size_t requiredToolCount = 0;
  std::size_t missingToolCount = 0;
  std::vector<std::string> requiredToolIds;
  std::vector<std::string> missingToolIds;
  bool optionalNativeToolMissing = false;
  std::string optionalNativeToolStatus;
  std::vector<std::string> toolRequirementEvidenceIds;
  std::vector<std::string> packageArtifactRequirementEvidenceIds;
};

struct TargetExplanationDocument {
  std::size_t schemaVersion = 1;
  std::string module;
  std::string defaultTarget;
  std::size_t buildableTargetCount = 0;
  std::optional<std::string> recommendedTarget;
  std::optional<std::string> recommendedPackageMode;
  std::vector<TargetExplanationTargetRecord> targets;
};

TargetExplanationDocument
buildTargetExplanationDocument(const HIRModule &module);
TargetExplanationTargetRecord targetExplanationTargetRecordFromLegalizationContract(
    const TargetLegalizationContract &contract);
std::string targetExplanationJson(const TargetExplanationDocument &document);
std::string targetExplanationText(const TargetExplanationDocument &document);

} // namespace crossgl
