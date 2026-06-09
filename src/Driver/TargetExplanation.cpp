#include "crossgl/Driver/TargetExplanation.h"

#include "crossgl/Backend/Target.h"
#include "crossgl/Backend/TargetLegalization.h"
#include "crossgl/Basic/Json.h"
#include "crossgl/HIR/HIR.h"

#include <algorithm>
#include <sstream>
#include <string_view>
#include <utility>

namespace crossgl {
namespace {

const char *jsonBool(bool value) { return value ? "true" : "false"; }

void appendStringArray(std::ostringstream &out,
                       const std::vector<std::string> &values,
                       std::string_view indent) {
  out << "[";
  if (values.empty()) {
    out << "]";
    return;
  }

  out << "\n";
  for (std::size_t index = 0; index < values.size(); ++index) {
    out << indent << "  \"" << escapeJson(values[index]) << "\"";
    if (index + 1 != values.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << indent << "]";
}

std::string formatStringList(const std::vector<std::string> &values,
                             std::size_t maxItems) {
  std::ostringstream out;
  const std::size_t count =
      maxItems == 0 || maxItems > values.size() ? values.size() : maxItems;
  for (std::size_t index = 0; index < count; ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << values[index];
  }
  if (count < values.size()) {
    out << ", +" << (values.size() - count) << " more";
  }
  return out.str();
}

std::string projectionTargetName(
    const TargetLegalizationContractProjection &projection) {
  if (!projection.targetProfile.resolvedTargetName.empty()) {
    return projection.targetProfile.resolvedTargetName;
  }
  return targetName(projection.targetProfile.resolvedTarget);
}

bool containsString(const std::vector<std::string> &values,
                    std::string_view value) {
  return std::find(values.begin(), values.end(), value) != values.end();
}

bool projectionDiagnosticEvidenceIsNormalized(
    const TargetLegalizationContractProjection &projection) {
  if (projection.diagnosticEvidenceIds !=
      projection.diagnosticSummary.evidenceIds) {
    return false;
  }
  for (const std::string &evidenceId : projection.diagnosticEvidenceIds) {
    if (evidenceId.empty() ||
        !containsString(projection.evidenceIds, evidenceId)) {
      return false;
    }
  }
  return true;
}

bool isProjectionBackedBuildableRecord(
    const TargetExplanationTargetRecord &record) {
  return record.packageBuildSupported &&
         !record.legalizationCoreEvidenceIds.empty();
}

std::string remediationForRecord(const TargetExplanationTargetRecord &record) {
  if (record.packageMode == "native") {
    return "No remediation required; native package output is available.";
  }
  if (record.packageMode == "source-package") {
    if (record.missingCapabilities.empty()) {
      return "No remediation required; source package output is available.";
    }
    return "Source package output is available; native artifact remediation "
           "requires satisfying: " +
           formatStringList(record.missingCapabilities, 0) + ".";
  }
  if (record.missingCapabilities.empty()) {
    return "Select a buildable target or enable missing target capabilities.";
  }
  return "Select a buildable target or satisfy missing target capabilities: " +
         formatStringList(record.missingCapabilities, 0) + ".";
}

void populateConsumerContext(TargetExplanationTargetRecord &record) {
  record.targetBackend = record.target;
  record.artifactLinks = {"ir/target-explanation.json#targets/" +
                          record.target};
  record.reportLinks = {"target-explanation-v1#targets/" + record.target};
  record.remediation = remediationForRecord(record);
}

const TargetExplanationTargetRecord *selectRecommendedTargetRecord(
    const std::vector<TargetExplanationTargetRecord> &records,
    std::string_view defaultTarget) {
  const TargetExplanationTargetRecord *recommended = nullptr;
  for (const TargetExplanationTargetRecord &record : records) {
    if (!isProjectionBackedBuildableRecord(record)) {
      continue;
    }
    if (recommended == nullptr ||
        record.packageRankScore < recommended->packageRankScore ||
        (record.packageRankScore == recommended->packageRankScore &&
         record.target == defaultTarget &&
         recommended->target != defaultTarget)) {
      recommended = &record;
    }
  }
  return recommended;
}

TargetExplanationTargetRecord targetRecordFromLegalizationProjection(
    const TargetLegalizationContractProjection &projection) {
  TargetExplanationTargetRecord record;
  record.target = projectionTargetName(projection);
  record.nativeImplemented = projection.nativeImplemented;
  record.sourcePackageSupported = projection.sourcePackageSupported;
  // Audit anchors: targetLegalizationSupportsPackage and
  // targetLegalizationCoreEvidenceIds are consumed through the projection here.
  // Legacy projection-adoption token:
  // record.packageBuildSupported = projection.supportsPackage is centralized in
  // targetLegalizationProjectionSupportsPackage.
  record.packageBuildSupported =
      targetLegalizationProjectionSupportsPackage(projection) &&
      projectionDiagnosticEvidenceIsNormalized(projection);
  record.supportStatus = projection.supportStatusName;
  record.legalizationState = projection.stateName;
  record.packageMode = projection.packageModeName;
  record.packageDecisionProvenance =
      projection.packageDecisionProvenanceName;
  record.packageDecisionReason = projection.reason;
  record.decisionReasonCodes = projection.consumerDecisionReasonCodes;
  record.packageRankScore = projection.packageRankScore;
  record.requiredCapabilities = projection.requiredCapabilityIds;
  record.missingCapabilities = projection.missingCapabilityIds;
  record.requiredCapabilityCount = projection.requiredCapabilityCount;
  record.missingCapabilityCount = projection.missingCapabilityCount;
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
  std::sort(record.requiredCapabilities.begin(),
            record.requiredCapabilities.end());
  std::sort(record.missingCapabilities.begin(),
            record.missingCapabilities.end());
  std::sort(record.requiredToolIds.begin(), record.requiredToolIds.end());
  std::sort(record.missingToolIds.begin(), record.missingToolIds.end());
  populateConsumerContext(record);
  return record;
}

TargetExplanationTargetRecord
targetRecordFromLegalization(const TargetLegalizationResult &legalization) {
  return targetRecordFromLegalizationProjection(
      targetLegalizationContractProjection(legalization));
}

} // namespace

TargetExplanationTargetRecord targetExplanationTargetRecordFromLegalizationContract(
    const TargetLegalizationContract &contract) {
  return targetRecordFromLegalizationProjection(
      targetLegalizationContractProjection(contract));
}

TargetExplanationDocument
buildTargetExplanationDocument(const HIRModule &module) {
  const TargetKind defaultTarget = defaultTargetForHost();
  const std::vector<TargetLegalizationResult> legalizations =
      legalizeTargets(module, defaultTarget);

  TargetExplanationDocument document;
  document.module = module.name;
  document.defaultTarget = targetName(defaultTarget);
  document.targets.reserve(legalizations.size());

  for (const TargetLegalizationResult &legalization : legalizations) {
    TargetExplanationTargetRecord record =
        targetRecordFromLegalization(legalization);
    if (isProjectionBackedBuildableRecord(record)) {
      ++document.buildableTargetCount;
    }
    document.targets.push_back(std::move(record));
  }
  if (const TargetExplanationTargetRecord *recommended =
          selectRecommendedTargetRecord(document.targets,
                                        document.defaultTarget)) {
    document.recommendedTarget = recommended->target;
    document.recommendedPackageMode = recommended->packageMode;
  }
  return document;
}

std::string targetExplanationJson(const TargetExplanationDocument &document) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": " << document.schemaVersion << ",\n"
      << "  \"module\": \"" << escapeJson(document.module) << "\",\n"
      << "  \"defaultTarget\": \"" << escapeJson(document.defaultTarget)
      << "\",\n"
      << "  \"buildableTargetCount\": " << document.buildableTargetCount
      << ",\n"
      << "  \"recommendedTarget\": ";
  if (document.recommendedTarget.has_value()) {
    out << "\"" << escapeJson(*document.recommendedTarget) << "\"";
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"recommendedPackageMode\": ";
  if (document.recommendedPackageMode.has_value()) {
    out << "\"" << escapeJson(*document.recommendedPackageMode) << "\"";
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"targets\": [\n";
  for (std::size_t index = 0; index < document.targets.size(); ++index) {
    const TargetExplanationTargetRecord &target = document.targets[index];
    out << "    {\n"
        << "      \"target\": \"" << escapeJson(target.target) << "\",\n"
        << "      \"targetBackend\": \"" << escapeJson(target.targetBackend)
        << "\",\n"
        << "      \"nativeImplemented\": " << jsonBool(target.nativeImplemented)
        << ",\n"
        << "      \"sourcePackageSupported\": "
        << jsonBool(target.sourcePackageSupported) << ",\n"
        << "      \"packageBuildSupported\": "
        << jsonBool(target.packageBuildSupported) << ",\n"
        << "      \"supportStatus\": \"" << escapeJson(target.supportStatus)
        << "\",\n"
        << "      \"legalizationState\": \""
        << escapeJson(target.legalizationState) << "\",\n"
        << "      \"packageMode\": \"" << escapeJson(target.packageMode)
        << "\",\n"
        << "      \"packageDecisionProvenance\": \""
        << escapeJson(target.packageDecisionProvenance) << "\",\n"
        << "      \"packageDecisionReason\": \""
        << escapeJson(target.packageDecisionReason) << "\",\n"
        << "      \"decisionReasonCodes\": ";
    appendStringArray(out, target.decisionReasonCodes, "      ");
    out << ",\n"
        << "      \"packageRankScore\": " << target.packageRankScore << ",\n"
        << "      \"artifactLinks\": ";
    appendStringArray(out, target.artifactLinks, "      ");
    out << ",\n"
        << "      \"reportLinks\": ";
    appendStringArray(out, target.reportLinks, "      ");
    out << ",\n"
        << "      \"remediation\": \"" << escapeJson(target.remediation)
        << "\",\n"
        << "      \"requiredCapabilityCount\": "
        << target.requiredCapabilityCount << ",\n"
        << "      \"missingCapabilityCount\": " << target.missingCapabilityCount
        << ",\n"
        << "      \"legalizationCoreEvidenceIds\": ";
    appendStringArray(out, target.legalizationCoreEvidenceIds, "      ");
    out << ",\n"
        << "      \"diagnosticEvidenceIds\": ";
    appendStringArray(out, target.diagnosticEvidenceIds, "      ");
    out << ",\n"
        << "      \"requiredToolCount\": " << target.requiredToolCount
        << ",\n"
        << "      \"missingToolCount\": " << target.missingToolCount << ",\n"
        << "      \"optionalNativeToolMissing\": "
        << jsonBool(target.optionalNativeToolMissing) << ",\n"
        << "      \"optionalNativeToolStatus\": \""
        << escapeJson(target.optionalNativeToolStatus) << "\",\n"
        << "      \"toolRequirementEvidenceIds\": ";
    appendStringArray(out, target.toolRequirementEvidenceIds, "      ");
    out << ",\n"
        << "      \"packageArtifactRequirementEvidenceIds\": ";
    appendStringArray(out, target.packageArtifactRequirementEvidenceIds,
                      "      ");
    out << ",\n"
        << "      \"requiredToolIds\": ";
    appendStringArray(out, target.requiredToolIds, "      ");
    out << ",\n"
        << "      \"missingToolIds\": ";
    appendStringArray(out, target.missingToolIds, "      ");
    out << ",\n"
        << "      \"requiredCapabilities\": ";
    appendStringArray(out, target.requiredCapabilities, "      ");
    out << ",\n"
        << "      \"missingCapabilities\": ";
    appendStringArray(out, target.missingCapabilities, "      ");
    out << "\n"
        << "    }";
    if (index + 1 != document.targets.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << "  ]\n"
      << "}\n";
  return out.str();
}

std::string targetExplanationText(const TargetExplanationDocument &document) {
  std::ostringstream out;
  out << "Target package decisions for " << document.module << ":\n";
  out << "  default target: " << document.defaultTarget << "\n";
  out << "  buildable targets: " << document.buildableTargetCount << "/"
      << document.targets.size() << "\n";
  out << "  recommended: ";
  if (document.recommendedTarget.has_value()) {
    out << *document.recommendedTarget << " ("
        << document.recommendedPackageMode.value_or("") << ")";
  } else {
    out << "none";
  }
  out << "\n";
  out << "  targets:\n";
  for (const TargetExplanationTargetRecord &target : document.targets) {
    out << "    " << target.target << ": "
        << (target.packageBuildSupported ? "buildable" : "blocked")
        << ", mode=" << target.packageMode
        << ", reason=" << target.packageDecisionReason
        << ", missing=" << target.missingCapabilityCount
        << ", missingTools=" << target.missingToolCount
        << ", diagnostics=" << target.diagnosticEvidenceIds.size();
    if (!target.missingCapabilities.empty()) {
      out << " (" << formatStringList(target.missingCapabilities, 8) << ")";
    }
    out << "\n";
  }
  return out.str();
}

} // namespace crossgl
