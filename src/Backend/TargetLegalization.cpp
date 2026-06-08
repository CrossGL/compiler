#include "crossgl/Backend/TargetLegalization.h"

#include "crossgl/Backend/BackendPlan.h"
#include "crossgl/Backend/DirectXBackend.h"
#include "crossgl/Backend/MetalBackend.h"
#include "crossgl/Backend/OpenGLBackend.h"
#include "crossgl/Backend/VulkanBackend.h"
#include "crossgl/Basic/Json.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <algorithm>
#include <optional>
#include <ostream>
#include <sstream>
#include <string_view>
#include <tuple>
#include <type_traits>
#include <utility>

namespace crossgl {
namespace {

constexpr std::string_view kRawStatementBackendInputDiagnostic =
    "opt.hir-raw-statement-backend-input";
constexpr std::string_view kVulkanRuntimeResourceArrayDiagnostic =
    "vulkan.prototype-unsupported-runtime-resource-array";

bool containsString(const std::vector<std::string> &values,
                    std::string_view value) {
  return std::find(values.begin(), values.end(), value) != values.end();
}

bool sameStringVector(const std::vector<std::string> &lhs,
                      const std::vector<std::string> &rhs) {
  return lhs.size() == rhs.size() &&
         std::equal(lhs.begin(), lhs.end(), rhs.begin());
}

void appendJsonString(std::ostream &out, std::string_view value) {
  out << "\"" << escapeJson(value) << "\"";
}

void appendJsonStringField(std::ostream &out, std::string_view name,
                           std::string_view value) {
  appendJsonString(out, name);
  out << ":";
  appendJsonString(out, value);
}

void appendJsonBoolField(std::ostream &out, std::string_view name, bool value) {
  appendJsonString(out, name);
  out << ":" << (value ? "true" : "false");
}

void appendJsonSizeField(std::ostream &out, std::string_view name,
                         std::size_t value) {
  appendJsonString(out, name);
  out << ":" << value;
}

void appendJsonStringArray(std::ostream &out,
                           const std::vector<std::string> &values) {
  out << "[";
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (index != 0) {
      out << ",";
    }
    appendJsonString(out, values[index]);
  }
  out << "]";
}

void appendJsonStringArrayField(std::ostream &out, std::string_view name,
                                const std::vector<std::string> &values) {
  appendJsonString(out, name);
  out << ":";
  appendJsonStringArray(out, values);
}

void sortUniqueStrings(std::vector<std::string> &values) {
  std::sort(values.begin(), values.end());
  values.erase(std::unique(values.begin(), values.end()), values.end());
}

std::string targetProfileTargetName(TargetKind target,
                                    const std::string &storedName) {
  if (!storedName.empty()) {
    return storedName;
  }
  return targetName(target);
}

std::string projectionSupportStatusName(
    const TargetLegalizationContractProjection &projection) {
  if (!projection.supportStatusName.empty()) {
    return projection.supportStatusName;
  }
  return targetLegalizationSupportStatusName(projection.supportStatus);
}

std::string
projectionStateName(const TargetLegalizationContractProjection &projection) {
  if (!projection.stateName.empty()) {
    return projection.stateName;
  }
  return targetLegalizationStateName(projection.state);
}

std::string projectionPackageModeName(
    const TargetLegalizationContractProjection &projection) {
  if (!projection.packageModeName.empty()) {
    return projection.packageModeName;
  }
  return targetLegalizationPackageModeName(projection.packageMode);
}

std::string projectionPackageDecisionProvenanceName(
    const TargetLegalizationContractProjection &projection) {
  if (!projection.packageDecisionProvenanceName.empty()) {
    return projection.packageDecisionProvenanceName;
  }
  return targetLegalizationPackageDecisionProvenanceName(
      projection.packageDecisionProvenance);
}

std::string projectionOptionalNativeToolStatusName(
    const TargetLegalizationContractProjection &projection) {
  if (!projection.optionalNativeToolStatusName.empty()) {
    return projection.optionalNativeToolStatusName;
  }
  return targetLegalizationOptionalNativeToolStatusName(
      projection.optionalNativeToolStatus);
}

std::string contractPackageModeName(const TargetLegalizationContract &contract) {
  if (!contract.packageModeName.empty()) {
    return contract.packageModeName;
  }
  return targetLegalizationPackageModeName(contract.packageMode);
}

std::vector<std::string> consumerDecisionReasonCodesForContract(
    const TargetLegalizationContract &contract, bool supportsPackage) {
  std::vector<std::string> codes;
  codes.push_back("package-mode:" + contractPackageModeName(contract));
  codes.push_back("package-reason:" + contract.reason);
  if (contract.optionalNativeToolMissing) {
    codes.push_back("optional-native-tool:missing");
  }
  if (!supportsPackage) {
    codes.push_back("unsupported:missing-capabilities");
  }
  return codes;
}

std::string
projectionABIStateName(const TargetLegalizationContractProjection &projection) {
  if (!projection.abiStateName.empty()) {
    return projection.abiStateName;
  }
  return targetLegalizationABIStateName(projection.abiState);
}

std::string projectionRewriteStateName(
    const TargetLegalizationContractProjection &projection) {
  if (!projection.rewriteStateName.empty()) {
    return projection.rewriteStateName;
  }
  return targetLegalizationRewriteStateName(projection.rewriteState);
}

void appendTargetProfileJson(std::ostream &out,
                             const TargetLegalizationTargetProfile &profile) {
  out << "{";
  appendJsonStringField(out, "requestedTarget",
                        targetProfileTargetName(profile.requestedTarget,
                                                profile.requestedTargetName));
  out << ",";
  appendJsonStringField(out, "preferredTarget",
                        targetProfileTargetName(profile.preferredTarget,
                                                profile.preferredTargetName));
  out << ",";
  appendJsonStringField(out, "resolvedTarget",
                        targetProfileTargetName(profile.resolvedTarget,
                                                profile.resolvedTargetName));
  out << ",";
  appendJsonStringField(out, "selectedTarget",
                        targetProfileTargetName(profile.selectedTarget,
                                                profile.selectedTargetName));
  out << ",";
  appendJsonBoolField(out, "autoRequested", profile.autoRequested);
  out << ",";
  appendJsonBoolField(out, "selectedTargetBuildable",
                      profile.selectedTargetBuildable);
  out << "}";
}

void appendDiagnosticSummaryJson(
    std::ostream &out, const TargetLegalizationDiagnosticSummary &summary) {
  out << "{";
  appendJsonSizeField(out, "diagnosticCount", summary.diagnosticCount);
  out << ",";
  appendJsonSizeField(out, "noteCount", summary.noteCount);
  out << ",";
  appendJsonSizeField(out, "warningCount", summary.warningCount);
  out << ",";
  appendJsonSizeField(out, "errorCount", summary.errorCount);
  out << ",";
  appendJsonBoolField(out, "hasErrors", summary.hasErrors);
  out << ",";
  appendJsonStringArrayField(out, "severities", summary.severities);
  out << ",";
  appendJsonStringArrayField(out, "codes", summary.codes);
  out << ",";
  appendJsonStringArrayField(out, "evidenceIds", summary.evidenceIds);
  out << "}";
}

void appendConsumerAuditReferencesJson(
    std::ostream &out,
    const std::vector<TargetLegalizationConsumerAuditReference> &references) {
  out << "[";
  for (std::size_t index = 0; index < references.size(); ++index) {
    if (index != 0) {
      out << ",";
    }
    const TargetLegalizationConsumerAuditReference &reference =
        references[index];
    out << "{";
    appendJsonStringField(out, "consumer", reference.consumer);
    out << ",";
    appendJsonStringField(out, "auditPath", reference.auditPath);
    out << ",";
    appendJsonStringField(out, "auditSection", reference.auditSection);
    out << "}";
  }
  out << "]";
}

void appendPackageArtifactRequirementsJson(
    std::ostream &out, const TargetPackageArtifactRequirements &requirements) {
  out << "{";
  appendJsonStringField(
      out, "target",
      targetProfileTargetName(requirements.target, requirements.targetName));
  out << ",";
  appendJsonStringField(
      out, "packageMode",
      requirements.packageModeName.empty()
          ? targetLegalizationPackageModeName(requirements.packageMode)
          : requirements.packageModeName);
  out << ",";
  appendJsonStringArrayField(out, "requiredPathArtifactKeys",
                             requirements.requiredPathArtifactKeys);
  out << ",";
  appendJsonBoolField(out, "requiresNativeBinaryStatus",
                      requirements.requiresNativeBinaryStatus);
  out << ",";
  appendJsonBoolField(out, "allowsPlannedNativeBinary",
                      requirements.allowsPlannedNativeBinary);
  out << ",";
  appendJsonBoolField(out, "allowsPlannedNativeSourceEvidence",
                      requirements.allowsPlannedNativeSourceEvidence);
  out << ",";
  appendJsonStringArrayField(out, "evidenceIds", requirements.evidenceIds);
  out << "}";
}

std::string sourcePackageDescriptorOptimizationEvidenceModeName(
    const TargetSourcePackageDescriptorPolicy &policy) {
  if (!policy.optimizationEvidenceModeName.empty()) {
    return policy.optimizationEvidenceModeName;
  }
  return targetSourcePackageDescriptorOptimizationEvidenceModeName(
      policy.optimizationEvidenceMode);
}

std::string sourcePackageDescriptorToolProvenanceModeName(
    const TargetSourcePackageDescriptorPolicy &policy) {
  if (!policy.toolProvenanceModeName.empty()) {
    return policy.toolProvenanceModeName;
  }
  return targetSourcePackageDescriptorToolProvenanceModeName(
      policy.toolProvenanceMode);
}

void appendSourcePackageDescriptorPolicyJson(
    std::ostream &out, const TargetSourcePackageDescriptorPolicy &policy) {
  out << "{";
  appendJsonStringField(
      out, "target", targetProfileTargetName(policy.target, policy.targetName));
  out << ",";
  appendJsonBoolField(out, "supported", policy.supported);
  out << ",";
  appendJsonStringField(out, "binaryKind", policy.binaryKind);
  out << ",";
  appendJsonStringField(out, "sourceArtifactKey", policy.sourceArtifactKey);
  out << ",";
  appendJsonStringField(out, "nativeBinaryArtifactKey",
                        policy.nativeBinaryArtifactKey);
  out << ",";
  appendJsonStringField(out, "descriptorArtifactKey",
                        policy.descriptorArtifactKey);
  out << ",";
  appendJsonStringField(out, "nativeBinaryStatus",
                        policy.nativeBinaryStatus);
  out << ",";
  appendJsonBoolField(out, "includesNativeBinaryStatus",
                      policy.includesNativeBinaryStatus);
  out << ",";
  appendJsonBoolField(out, "requiresProducedNativeArtifact",
                      policy.requiresProducedNativeArtifact);
  out << ",";
  appendJsonStringField(out, "validationStatus", policy.validationStatus);
  out << ",";
  appendJsonStringField(
      out, "optimizationLevelMode",
      targetSourcePackageDescriptorOptimizationLevelModeName(
          policy.optimizationLevelMode));
  out << ",";
  appendJsonStringField(out, "fixedOptimizationLevel",
                        policy.fixedOptimizationLevel);
  out << ",";
  appendJsonStringField(
      out, "optimizationEvidenceMode",
      sourcePackageDescriptorOptimizationEvidenceModeName(policy));
  out << ",";
  appendJsonStringField(
      out, "toolProvenanceMode",
      sourcePackageDescriptorToolProvenanceModeName(policy));
  out << ",";
  appendJsonStringField(out, "nativeToolName", policy.nativeToolName);
  out << ",";
  appendJsonStringField(out, "nativeToolRole", policy.nativeToolRole);
  out << ",";
  appendJsonStringField(out, "nativeToolExecutable",
                        policy.nativeToolExecutable);
  out << ",";
  appendJsonStringField(out, "nativeToolProbeName",
                        policy.nativeToolProbeName);
  out << "}";
}

std::string evidenceId(TargetKind target, std::string_view suffix);
std::string abiFactId(const TargetLegalizationABIRecord &record);
std::string
toolRequirementId(const TargetLegalizationToolRequirementRecord &record);

std::string targetLegalizationCapabilityId(const TargetCapability &capability) {
  if (capability.kind == "nativeTool") {
    return targetName(capability.target) + ".native-tool." + capability.name;
  }
  return targetCapabilityId(capability);
}

std::vector<std::string>
targetCapabilityIds(const std::vector<TargetCapability> &capabilities) {
  std::vector<std::string> ids;
  ids.reserve(capabilities.size());
  for (const TargetCapability &capability : capabilities) {
    ids.push_back(targetLegalizationCapabilityId(capability));
  }
  sortUniqueStrings(ids);
  return ids;
}

std::vector<std::string>
v0RequiredCapabilityIds(const TargetLegalizationContract &contract) {
  std::vector<std::string> ids = contract.requiredCapabilityIds;
  sortUniqueStrings(ids);
  if (!targetLegalizationSupportsPackage(contract)) {
    return ids;
  }

  std::vector<std::string> missing = contract.missingCapabilityIds;
  sortUniqueStrings(missing);
  ids.erase(std::remove_if(ids.begin(), ids.end(),
                           [&missing](const std::string &id) {
                             return containsString(missing, id);
                           }),
            ids.end());
  return ids;
}

std::vector<std::string>
v0MissingCapabilityIds(const TargetLegalizationContract &contract) {
  if (targetLegalizationSupportsPackage(contract)) {
    return {};
  }
  std::vector<std::string> ids = contract.missingCapabilityIds;
  sortUniqueStrings(ids);
  return ids;
}

std::string v0DiagnosticSeverityName(DiagnosticSeverity severity) {
  switch (severity) {
  case DiagnosticSeverity::Note:
    return "info";
  case DiagnosticSeverity::Warning:
    return "warning";
  case DiagnosticSeverity::Error:
    return "error";
  }
  return "info";
}

void appendV0DiagnosticJson(std::ostream &out,
                            const TargetLegalizationDiagnostic &diagnostic) {
  out << "{";
  appendJsonStringField(out, "code", diagnostic.code);
  out << ",";
  appendJsonStringField(out, "severity",
                        v0DiagnosticSeverityName(diagnostic.severity));
  out << ",";
  appendJsonStringField(out, "message", diagnostic.message);
  out << ",";
  appendJsonStringField(out, "target", targetName(diagnostic.target));
  out << ",";
  appendJsonStringArrayField(out, "missingCapabilities",
                             targetCapabilityIds(diagnostic.capabilities));
  out << ",";
  appendJsonStringArrayField(out, "evidenceIds", {diagnostic.evidenceId});
  out << "}";
}

std::string v0RewriteStatusName(
    const TargetLegalizationRewriteRecord &record,
    TargetLegalizationRewriteState collectionState) {
  if (record.applied) {
    return "applied";
  }
  if (collectionState == TargetLegalizationRewriteState::Unsupported) {
    return "blocked";
  }
  return "not-required";
}

void appendV0RewritesJson(
    std::ostream &out, const TargetLegalizationRewriteCollection &rewrites) {
  out << "[";
  for (std::size_t index = 0; index < rewrites.records.size(); ++index) {
    if (index != 0) {
      out << ",";
    }
    const TargetLegalizationRewriteRecord &record = rewrites.records[index];
    out << "{";
    appendJsonStringField(out, "id",
                          record.name.empty() ? record.kind : record.name);
    out << ",";
    appendJsonSizeField(out, "order", index);
    out << ",";
    appendJsonStringField(out, "status",
                          v0RewriteStatusName(record, rewrites.state));
    out << ",";
    appendJsonStringField(out, "description", record.description);
    out << ",";
    appendJsonStringArrayField(out, "evidenceIds", {record.evidenceId});
    out << "}";
  }
  out << "]";
}

std::string v0ABIStateName(const TargetLegalizationContract &contract) {
  if (!targetLegalizationSupportsPackage(contract)) {
    return "unsupported";
  }
  if (contract.packageMode == TargetLegalizationPackageMode::SourcePackage) {
    return "not-required";
  }
  if (contract.abiFacts.state == TargetLegalizationABIState::Present &&
      !contract.abiFacts.complete) {
    return "partial";
  }
  if (contract.abiFacts.state == TargetLegalizationABIState::Unsupported) {
    return "unsupported";
  }
  return "complete";
}

std::vector<std::string> v0ABIEvidenceIds(
    const TargetLegalizationContract &contract, std::string_view abiState) {
  if (!contract.abiFacts.evidenceIds.empty()) {
    return contract.abiFacts.evidenceIds;
  }
  if (abiState == "not-required") {
    return {evidenceId(contract.resolvedTarget, "abi.not-required")};
  }
  if (abiState == "complete") {
    return {evidenceId(contract.resolvedTarget, "abi.complete")};
  }
  return contract.abiFacts.evidenceIds.empty()
             ? std::vector<std::string>{evidenceId(contract.resolvedTarget,
                                                   "abi.unsupported")}
             : contract.abiFacts.evidenceIds;
}

std::string v0ABIRecordKind(std::string_view kind) {
  if (kind == "entry-point" || kind == "entryPoint") {
    return "entry-point";
  }
  if (kind == "extension") {
    return "extension";
  }
  if (kind == "layout") {
    return "layout";
  }
  if (kind == "resource-binding" || kind == "resourceBinding") {
    return "resource-binding";
  }
  if (kind == "toolchain" || kind == "validation") {
    return "toolchain";
  }
  return "native-profile";
}

std::string v0ABIRecordStatus(std::string_view role, bool moduleSupported) {
  if (role == "missing" && moduleSupported) {
    return "not-required";
  }
  return role == "missing" ? "missing" : "provided";
}

void appendV0ABIRecordJson(std::ostream &out,
                           const TargetLegalizationABIRecord &record,
                           std::string_view role, bool moduleSupported) {
  out << "{";
  appendJsonStringField(out, "id", abiFactId(record));
  out << ",";
  appendJsonStringField(out, "kind", v0ABIRecordKind(record.kind));
  out << ",";
  appendJsonStringField(out, "status",
                        v0ABIRecordStatus(role, moduleSupported));
  out << ",";
  appendJsonStringField(out, "target", targetName(record.target));
  out << ",";
  appendJsonStringArrayField(out, "evidenceIds", {record.evidenceId});
  out << "}";
}

bool appendV0ABIRecordFactsJson(std::ostream &out,
                                const TargetLegalizationABIFacts &abiFacts,
                                bool moduleSupported) {
  bool wroteRecord = false;
  auto appendRecord =
      [&](const TargetLegalizationABIRecord &record, std::string_view role) {
        if (wroteRecord) {
          out << ",";
        }
        appendV0ABIRecordJson(out, record, role, moduleSupported);
        wroteRecord = true;
      };
  for (const TargetLegalizationABIRecord &record : abiFacts.requiredRecords) {
    appendRecord(record, "required");
  }
  for (const TargetLegalizationABIRecord &record : abiFacts.missingRecords) {
    appendRecord(record, "missing");
  }
  return wroteRecord;
}

void appendV0ABIFactsJson(std::ostream &out,
                          const TargetLegalizationContract &contract) {
  const bool moduleSupported = targetLegalizationSupportsPackage(contract);
  const std::string abiState = v0ABIStateName(contract);
  const std::vector<std::string> abiEvidenceIds =
      v0ABIEvidenceIds(contract, abiState);
  out << "{";
  appendJsonStringField(out, "state", abiState);
  out << ",\"facts\":";
  out << "[";
  if (!appendV0ABIRecordFactsJson(out, contract.abiFacts, moduleSupported) &&
      abiState == "complete") {
    out << "{";
    appendJsonStringField(out, "id", "target-profile.native");
    out << ",";
    appendJsonStringField(out, "kind", "native-profile");
    out << ",";
    appendJsonStringField(out, "status", "provided");
    out << ",";
    appendJsonStringField(out, "target", targetName(contract.resolvedTarget));
    out << ",";
    appendJsonStringArrayField(out, "evidenceIds", abiEvidenceIds);
    out << "}";
  } else if (contract.abiFacts.requiredRecords.empty() &&
             contract.abiFacts.missingRecords.empty() &&
             abiState == "unsupported") {
    out << "{";
    appendJsonStringField(out, "id", "target-profile.unsupported");
    out << ",";
    appendJsonStringField(out, "kind", "native-profile");
    out << ",";
    appendJsonStringField(out, "status", "missing");
    out << ",";
    appendJsonStringField(out, "target", targetName(contract.resolvedTarget));
    out << ",";
    appendJsonStringArrayField(out, "evidenceIds", abiEvidenceIds);
    out << "}";
  }
  out << "]";
  out << ",";
  appendJsonStringArrayField(out, "evidenceIds", abiEvidenceIds);
  out << "}";
}

std::vector<std::string> v0SortedStringIds(std::vector<std::string> ids) {
  sortUniqueStrings(ids);
  return ids;
}

std::vector<std::string>
v0ToolRequirementEvidenceIds(const TargetLegalizationContract &contract) {
  std::vector<std::string> ids = contract.toolRequirements.evidenceIds;
  if (contract.optionalNativeToolMissing) {
    ids.push_back(
        evidenceId(contract.resolvedTarget, "optional-native-tool.missing"));
  }
  sortUniqueStrings(ids);
  return ids;
}

std::string v0ToolRequirementKind(std::string_view kind) {
  if (kind == "nativeTool") {
    return "native-tool";
  }
  if (kind == "toolchain" || kind == "validation" || kind == "native-tool") {
    return std::string(kind);
  }
  return "native-tool";
}

void appendV0ToolRequirementRecordJson(
    std::ostream &out, const TargetLegalizationToolRequirementRecord &record,
    std::string_view status) {
  out << "{";
  appendJsonStringField(out, "id", toolRequirementId(record));
  out << ",";
  appendJsonStringField(out, "kind", v0ToolRequirementKind(record.kind));
  out << ",";
  appendJsonStringField(out, "name", record.name);
  out << ",";
  appendJsonStringField(out, "status", status);
  out << ",";
  appendJsonStringField(out, "target", targetName(record.target));
  out << ",";
  appendJsonStringArrayField(out, "evidenceIds", {record.evidenceId});
  out << "}";
}

void appendV0ToolRequirementRecordsJson(
    std::ostream &out,
    const TargetLegalizationToolRequirementSummary &toolRequirements) {
  out << "[";
  bool wroteRecord = false;
  auto appendRecord =
      [&](const TargetLegalizationToolRequirementRecord &record,
          std::string_view status) {
        if (wroteRecord) {
          out << ",";
        }
        appendV0ToolRequirementRecordJson(out, record, status);
        wroteRecord = true;
      };
  for (const TargetLegalizationToolRequirementRecord &record :
       toolRequirements.requiredRecords) {
    appendRecord(record, "required");
  }
  for (const TargetLegalizationToolRequirementRecord &record :
       toolRequirements.missingRecords) {
    appendRecord(record, "missing");
  }
  out << "]";
}

void appendV0ToolRequirementsJson(
    std::ostream &out,
    const TargetLegalizationToolRequirementSummary &toolRequirements,
    bool optionalNativeToolMissing,
    TargetLegalizationOptionalNativeToolStatus optionalNativeToolStatus,
    const std::vector<std::string> &toolRequirementEvidenceIds) {
  out << "{";
  appendJsonStringArrayField(
      out, "requiredToolIds",
      v0SortedStringIds(toolRequirements.requiredToolIds));
  out << ",";
  appendJsonStringArrayField(
      out, "missingToolIds",
      v0SortedStringIds(toolRequirements.missingToolIds));
  out << ",";
  appendJsonString(out, "records");
  out << ":";
  appendV0ToolRequirementRecordsJson(out, toolRequirements);
  out << ",";
  appendJsonBoolField(out, "optionalNativeToolMissing",
                      optionalNativeToolMissing);
  out << ",";
  appendJsonStringField(
      out, "optionalNativeToolStatus",
      targetLegalizationOptionalNativeToolStatusName(
          optionalNativeToolStatus));
  out << ",";
  appendJsonStringArrayField(out, "evidenceIds", toolRequirementEvidenceIds);
  out << "}";
}

std::vector<std::string>
v0TopLevelEvidenceIds(const TargetLegalizationContract &contract) {
  std::vector<std::string> ids = contract.evidenceIds;
  const std::vector<std::string> coreEvidenceIds =
      targetLegalizationCoreEvidenceIds(contract);
  ids.insert(ids.end(), coreEvidenceIds.begin(), coreEvidenceIds.end());
  const std::string abiState = v0ABIStateName(contract);
  const std::vector<std::string> abiEvidenceIds =
      v0ABIEvidenceIds(contract, abiState);
  ids.insert(ids.end(), abiEvidenceIds.begin(), abiEvidenceIds.end());
  for (const TargetLegalizationDiagnostic &diagnostic : contract.diagnostics) {
    ids.push_back(diagnostic.evidenceId);
  }
  for (const TargetLegalizationRewriteRecord &record :
       contract.rewrites.records) {
    ids.push_back(record.evidenceId);
  }
  const std::vector<std::string> toolRequirementEvidenceIds =
      v0ToolRequirementEvidenceIds(contract);
  ids.insert(ids.end(), toolRequirementEvidenceIds.begin(),
             toolRequirementEvidenceIds.end());
  ids.insert(ids.end(), contract.resourceBindings.evidenceIds.begin(),
             contract.resourceBindings.evidenceIds.end());
  ids.push_back(evidenceId(
      contract.resolvedTarget,
      "package-provenance." +
          std::string(targetLegalizationPackageDecisionProvenanceName(
              contract.packageDecisionProvenance))));
  sortUniqueStrings(ids);
  return ids;
}

std::vector<std::string>
v0ResourceBindingEvidenceIds(const TargetLegalizationContract &contract) {
  std::vector<std::string> ids = contract.resourceBindings.evidenceIds;
  sortUniqueStrings(ids);
  return ids;
}

bool isABIFactKind(std::string_view kind) {
  return kind == "addressingModel" || kind == "backend" ||
         kind == "binaryFormat" || kind == "capability" ||
         kind == "memoryModel" || kind == "sourceLanguage" ||
         kind == "targetEnv" || kind == "toolchain" || kind == "validation";
}

bool isToolRequirementKind(std::string_view kind) {
  return kind == "toolchain" || kind == "validation" || kind == "native-tool" ||
         kind == "nativeTool";
}

bool isNativePackageToolRequirementId(TargetKind target,
                                      std::string_view toolId) {
  switch (target) {
  case TargetKind::Metal:
    return toolId == "metal.toolchain.xcrun-metal" ||
           toolId == "metal.toolchain.xcrun-metallib";
  case TargetKind::Vulkan:
    return toolId == "vulkan.toolchain.spirv-as" ||
           toolId == "vulkan.validation.spirv-val";
  case TargetKind::DirectX:
  case TargetKind::OpenGL:
  case TargetKind::Auto:
    return false;
  }
  return false;
}

bool isABIFactId(std::string_view capabilityId) {
  const std::size_t targetDelimiter = capabilityId.find('.');
  if (targetDelimiter == std::string_view::npos) {
    return false;
  }
  const std::size_t kindBegin = targetDelimiter + 1;
  const std::size_t kindEnd = capabilityId.find('.', kindBegin);
  if (kindEnd == std::string_view::npos) {
    return false;
  }
  return isABIFactKind(capabilityId.substr(kindBegin, kindEnd - kindBegin));
}

bool isToolRequirementId(std::string_view capabilityId) {
  const std::size_t targetDelimiter = capabilityId.find('.');
  if (targetDelimiter == std::string_view::npos) {
    return false;
  }
  const std::size_t kindBegin = targetDelimiter + 1;
  const std::size_t kindEnd = capabilityId.find('.', kindBegin);
  if (kindEnd == std::string_view::npos) {
    return false;
  }
  return isToolRequirementKind(
      capabilityId.substr(kindBegin, kindEnd - kindBegin));
}

bool isSourcePackageDecisionTarget(TargetKind target) {
  return target == TargetKind::DirectX || target == TargetKind::OpenGL;
}

bool hasMissingDiagnosticCapability(const TargetPackageDecision &decision,
                                    std::string_view code) {
  return std::find_if(decision.missingCapabilities.begin(),
                      decision.missingCapabilities.end(),
                      [code](const TargetCapability &capability) {
                        return capability.kind == "diagnostic" &&
                               capability.name == code;
                      }) != decision.missingCapabilities.end();
}

bool hasMissingCapabilityId(const std::vector<std::string> &capabilityIds,
                            TargetKind target, std::string_view kind,
                            std::string_view name) {
  return containsString(capabilityIds, targetName(target) + "." +
                                           std::string(kind) + "." +
                                           std::string(name));
}

bool hasSourceLocation(const SourceLocation &location) {
  return !location.file.empty();
}

std::string abiFactId(const TargetLegalizationABIRecord &record) {
  return targetName(record.target) + "." + record.kind + "." + record.name;
}

std::string
toolRequirementId(const TargetLegalizationToolRequirementRecord &record) {
  return targetName(record.target) + "." + v0ToolRequirementKind(record.kind) +
         "." + record.name;
}

std::string diagnosticEvidenceSuffix(std::string_view code) {
  return code.empty() ? "diagnostic.target.unsupported"
                      : "diagnostic." + std::string(code);
}

std::vector<Diagnostic>
predicateDiagnosticsForDecision(const HIRModule &module,
                                const TargetPackageDecision &decision) {
  if (!decision.diagnostics.empty()) {
    return decision.diagnostics;
  }
  if (decision.packageBuildSupported ||
      hasMissingDiagnosticCapability(decision,
                                     kRawStatementBackendInputDiagnostic)) {
    return {};
  }

  DiagnosticEngine diagnostics;
  switch (decision.target) {
  case TargetKind::DirectX:
    if (!decision.sourcePackageSupported) {
      (void)directxSourcePackageSupported(module, diagnostics);
    }
    break;
  case TargetKind::OpenGL:
    if (!decision.sourcePackageSupported) {
      (void)openGLSourcePackageSupported(module, diagnostics);
    }
    break;
  case TargetKind::Metal:
    if (decision.nativeImplemented) {
      (void)metalNativeBackendSupported(module, diagnostics);
    }
    break;
  case TargetKind::Vulkan:
    if (decision.nativeImplemented) {
      (void)vulkanPrototypeBinarySupported(module, diagnostics);
    }
    break;
  case TargetKind::Auto:
    break;
  }
  return diagnostics.diagnostics();
}

bool resourceBindingRecordLess(
    const TargetLegalizationResourceBindingRecord &lhs,
    const TargetLegalizationResourceBindingRecord &rhs) {
  return std::tie(lhs.target, lhs.stage, lhs.sourceEntryPoint,
                  lhs.backendEntryPoint, lhs.set, lhs.binding, lhs.bindingClass,
                  lhs.argumentIndex, lhs.kind, lhs.name, lhs.sourceType,
                  lhs.addressSpace, lhs.abi, lhs.evidenceId) <
         std::tie(rhs.target, rhs.stage, rhs.sourceEntryPoint,
                  rhs.backendEntryPoint, rhs.set, rhs.binding, rhs.bindingClass,
                  rhs.argumentIndex, rhs.kind, rhs.name, rhs.sourceType,
                  rhs.addressSpace, rhs.abi, rhs.evidenceId);
}

std::string evidenceId(TargetKind target, std::string_view suffix);

std::vector<std::string_view>
splitLegalizationArrayDimensions(std::string_view arraySize) {
  std::vector<std::string_view> dimensions;
  std::size_t begin = 0;
  while (begin <= arraySize.size()) {
    const std::size_t separator = arraySize.find("][", begin);
    if (separator == std::string_view::npos) {
      dimensions.push_back(arraySize.substr(begin));
      break;
    }
    dimensions.push_back(arraySize.substr(begin, separator - begin));
    begin = separator + 2;
  }
  return dimensions;
}

std::string wrapLegalizationArrayType(std::string elementType,
                                      const HIRType &type,
                                      std::string_view wrapperName) {
  if (!type.arraySize.has_value() || type.arraySize->empty()) {
    return elementType;
  }

  const std::vector<std::string_view> dimensions =
      splitLegalizationArrayDimensions(*type.arraySize);
  for (auto dimension = dimensions.rbegin(); dimension != dimensions.rend();
       ++dimension) {
    elementType = std::string(wrapperName) + "<" + elementType + ", " +
                  std::string(*dimension) + ">";
  }
  return elementType;
}

std::string storageImageScalarElementType(const HIRType &type) {
  const std::string payload =
      storageImagePayloadVectorTypeName(baseTypeName(type));
  if (payload == "ivec4") {
    return "int";
  }
  if (payload == "uvec4") {
    return "uint";
  }
  if (payload == "vec4") {
    return "float";
  }
  return {};
}

template <typename Resource>
std::string storageImageMetalAccessMode(const Resource &resource) {
  if constexpr (requires(const Resource &value) { value.storageImageAccess; }) {
    using Access = std::remove_cvref_t<decltype(resource.storageImageAccess)>;
    if (resource.storageImageAccess == Access::ReadOnly) {
      return "read";
    }
    if (resource.storageImageAccess == Access::WriteOnly) {
      return "write";
    }
  }
  return "read_write";
}

std::string legalizationStorageImageMetalType(const HIRResource &resource) {
  const HIRType &type = resource.type;
  const std::string valueType = storageImageScalarElementType(type);
  if (valueType.empty()) {
    return {};
  }
  const std::string accessMode = storageImageMetalAccessMode(resource);
  const std::string dimension = storageImageDimensionName(baseTypeName(type));
  if (dimension == "2d_array") {
    return wrapLegalizationArrayType("texture2d_array<" + valueType +
                                         ", access::" + accessMode + ">",
                                     type, "array");
  }
  if (dimension == "2d") {
    return wrapLegalizationArrayType("texture2d<" + valueType +
                                         ", access::" + accessMode + ">",
                                     type, "array");
  }
  return {};
}

std::string
legalizationStorageImageSPIRVFormatName(const HIRResource &resource) {
  const std::string format = resolvedStorageImageFormatName(resource);
  if (format == "rgba32f") {
    return "Rgba32f";
  }
  if (format == "rgba32i") {
    return "Rgba32i";
  }
  if (format == "rgba32ui") {
    return "Rgba32ui";
  }
  if (format == "r32f") {
    return "R32f";
  }
  if (format == "r32i") {
    return "R32i";
  }
  if (format == "r32ui") {
    return "R32ui";
  }
  return {};
}

std::string legalizationStorageImageSPIRVDimensionName(const HIRType &type) {
  const std::string dimension = storageImageDimensionName(baseTypeName(type));
  if (dimension == "2d_array") {
    return "2DArray";
  }
  if (dimension == "2d") {
    return "2D";
  }
  return {};
}

std::string
legalizationStorageImageVulkanSPIRVType(const HIRResource &resource) {
  const HIRType imageElement = arrayElementType(resource.type);
  const std::string valueType = storageImageScalarElementType(imageElement);
  const std::string dimension =
      legalizationStorageImageSPIRVDimensionName(imageElement);
  const std::string format = legalizationStorageImageSPIRVFormatName(resource);
  if (valueType.empty() || dimension.empty() || format.empty()) {
    return {};
  }
  return wrapLegalizationArrayType("OpTypeImage<" + valueType + ", " +
                                       dimension +
                                       ", sampled=2, format=" + format + ">",
                                   resource.type, "OpTypeArray");
}

std::string legalizationMetalResourceABIType(const HIRResource &resource) {
  if (resource.kind == HIRResourceKind::StorageImage) {
    return legalizationStorageImageMetalType(resource);
  }
  return metalResourceABIType(resource);
}

std::string legalizationMetalResourceAddressSpace(const HIRResource &resource) {
  return metalResourceAddressSpace(resource);
}

std::string legalizationMetalResourceBindingClass(const HIRResource &resource) {
  return metalResourceBindingClass(resource);
}

bool legalizationMetalResourceIsKernelParameter(HIRResourceKind kind) {
  return metalResourceIsKernelParameter(kind);
}

std::string legalizationVulkanResourceStorageClass(HIRResourceKind kind) {
  return vulkanResourceStorageClass(kind);
}

std::string legalizationVulkanResourceBindingClass(HIRResourceKind kind) {
  return vulkanResourceBindingClass(kind);
}

bool legalizationVulkanResourceUsesDescriptor(HIRResourceKind kind) {
  return vulkanResourceUsesDescriptor(kind);
}

std::string legalizationVulkanDescriptorType(HIRResourceKind kind) {
  return vulkanDescriptorType(kind);
}

std::string legalizationVulkanResourceSPIRVType(const HIRResource &resource) {
  if (resource.kind == HIRResourceKind::StorageImage) {
    return legalizationStorageImageVulkanSPIRVType(resource);
  }
  return vulkanResourceSPIRVType(resource);
}

std::optional<TargetLegalizationResourceBindingRecord>
resourceBindingRecordForResource(const HIRModule &module,
                                 const BackendPlanStageInterface &stage,
                                 const BackendPlanResource &resource,
                                 TargetKind target) {
  if (target == TargetKind::Auto || !resource.emitsTargetBinding ||
      resource.source == nullptr || stage.source == nullptr) {
    return std::nullopt;
  }

  const HIRResource &source = *resource.source;
  TargetLegalizationResourceBindingRecord record;
  record.target = target;
  record.stage = resource.stage;
  record.sourceEntryPoint = resource.entryPoint;
  record.backendEntryPoint = resource.backendEntryPoint;
  record.name = resource.name;
  record.kind = resource.kindName;
  record.sourceType = resource.sourceType;
  record.storageImageFormat = resource.storageImageFormat;
  if (source.kind == HIRResourceKind::StorageImage) {
    record.storageImageAccess =
        storageImageAccessName(source.storageImageAccess);
  }
  record.evidenceId =
      evidenceId(target, "resource-binding." + resource.stage + "." +
                             resource.backendEntryPoint + "." + resource.name);

  if (target == TargetKind::Metal) {
    record.metalType = legalizationMetalResourceABIType(source);
    record.addressSpace = legalizationMetalResourceAddressSpace(source);
    if (legalizationMetalResourceIsKernelParameter(source.kind)) {
      record.abi = "kernelArgument";
      record.bindingClass = legalizationMetalResourceBindingClass(source);
      record.argumentIndex = metalResourceArgumentIndex(
                                 *stage.source, source.name, &module.constants)
                                 .value_or(source.binding);
      record.set = source.set;
      record.binding = source.binding;
    } else if (source.kind == HIRResourceKind::Shared) {
      record.abi = "threadgroupLocal";
      record.bindingClass = "threadgroup";
    } else {
      return std::nullopt;
    }
    return record;
  }

  if (target == TargetKind::Vulkan) {
    record.addressSpace = legalizationVulkanResourceStorageClass(source.kind);
    record.storageClass = legalizationVulkanResourceStorageClass(source.kind);
    record.spirvType = legalizationVulkanResourceSPIRVType(source);
    if (legalizationVulkanResourceUsesDescriptor(source.kind)) {
      record.abi = "descriptor";
      record.bindingClass = legalizationVulkanResourceBindingClass(source.kind);
      record.descriptorType = legalizationVulkanDescriptorType(source.kind);
      record.set = source.set;
      record.binding = source.binding;
    } else if (source.kind == HIRResourceKind::Shared) {
      record.abi = "workgroupLocal";
      record.bindingClass = legalizationVulkanResourceBindingClass(source.kind);
    } else {
      return std::nullopt;
    }
    return record;
  }

  if (target == TargetKind::DirectX) {
    record.addressSpace = directxResourceAddressSpace(source.kind);
    record.abi = source.kind == HIRResourceKind::Shared ? "groupsharedLocal"
                                                        : "registerBinding";
    record.bindingClass = directxResourceBindingClass(source.kind);
    record.hlslType = directxResourceHLSLType(module, source);
    if (source.kind != HIRResourceKind::Shared) {
      record.descriptorType = directxResourceDescriptorType(source.kind);
      record.set = source.set;
      record.binding = source.binding;
      record.argumentIndex = resource.directxRegisterIndex.value_or(
          directxResourceRegisterIndex(source));
    }
    return record;
  }

  if (target == TargetKind::OpenGL) {
    record.addressSpace = openglResourceAddressSpace(source.kind);
    record.abi = source.kind == HIRResourceKind::Shared
                     ? "workgroupLocal"
                     : "programResourceBinding";
    record.bindingClass = openglResourceBindingClass(source.kind);
    if (source.kind != HIRResourceKind::Shared) {
      record.set = source.set;
      record.binding = source.binding;
      record.argumentIndex = resource.openglBindingIndex.value_or(
          openglResourceBindingIndex(source));
    }
    return record;
  }

  return std::nullopt;
}

TargetLegalizationResourceBindingFacts
resourceBindingFactsForModule(const HIRModule &module, TargetKind target) {
  TargetLegalizationResourceBindingFacts facts;
  facts.target = target;
  if (target == TargetKind::Auto) {
    return facts;
  }

  const BackendPlan plan = buildBackendPlan(module);
  for (const BackendPlanStageInterface &stage : plan.stages) {
    for (const BackendPlanResource &resource : stage.resources) {
      if (resource.emitsTargetBinding && resource.source != nullptr &&
          stage.source != nullptr) {
        ++facts.requiredRecordCount;
      }
      std::optional<TargetLegalizationResourceBindingRecord> record =
          resourceBindingRecordForResource(module, stage, resource, target);
      if (!record.has_value()) {
        continue;
      }
      facts.records.push_back(std::move(*record));
    }
  }

  std::sort(facts.records.begin(), facts.records.end(),
            resourceBindingRecordLess);

  facts.complete = facts.records.size() == facts.requiredRecordCount;
  facts.evidenceIds.push_back(
      evidenceId(target, facts.records.empty() ? "resource-bindings.empty"
                                               : "resource-bindings.present"));
  for (const TargetLegalizationResourceBindingRecord &record : facts.records) {
    facts.evidenceIds.push_back(record.evidenceId);
  }
  return facts;
}

TargetLegalizationSupportStatus
supportStatusForDecision(const TargetPackageDecision &decision) {
  if (!decision.packageBuildSupported) {
    return TargetLegalizationSupportStatus::Unsupported;
  }
  switch (targetLegalizationPackageModeFromName(decision.packageMode)) {
  case TargetLegalizationPackageMode::Native:
    return TargetLegalizationSupportStatus::NativePackage;
  case TargetLegalizationPackageMode::SourcePackage:
    return TargetLegalizationSupportStatus::SourcePackage;
  case TargetLegalizationPackageMode::Unsupported:
    return TargetLegalizationSupportStatus::Unsupported;
  }
  return TargetLegalizationSupportStatus::Unsupported;
}

TargetLegalizationPackageMode
packageModeKindForDecision(const TargetPackageDecision &decision) {
  if (!decision.packageBuildSupported) {
    return TargetLegalizationPackageMode::Unsupported;
  }
  return targetLegalizationPackageModeFromName(decision.packageMode);
}

TargetLegalizationPackageDecisionProvenance
packageDecisionProvenanceForDecision(const TargetPackageDecision &decision,
                                     TargetLegalizationPackageMode mode) {
  if (mode == TargetLegalizationPackageMode::Native) {
    return TargetLegalizationPackageDecisionProvenance::NativePackageAvailable;
  }
  if (mode == TargetLegalizationPackageMode::SourcePackage) {
    return TargetLegalizationPackageDecisionProvenance::SourcePackageOnly;
  }
  if (hasMissingDiagnosticCapability(decision,
                                     kRawStatementBackendInputDiagnostic)) {
    return TargetLegalizationPackageDecisionProvenance::UnsupportedRawHIR;
  }
  if (isSourcePackageDecisionTarget(decision.target) &&
      !decision.sourcePackageSupported) {
    return TargetLegalizationPackageDecisionProvenance::UnsupportedSourceForm;
  }
  if (decision.nativeImplemented) {
    return TargetLegalizationPackageDecisionProvenance::UnsupportedNativeForm;
  }
  return TargetLegalizationPackageDecisionProvenance::Unsupported;
}

TargetLegalizationOptionalNativeToolStatus optionalNativeToolStatusForDecision(
    TargetLegalizationPackageMode mode,
    const TargetLegalizationToolRequirementSummary &toolRequirements) {
  if (mode != TargetLegalizationPackageMode::SourcePackage) {
    return TargetLegalizationOptionalNativeToolStatus::NotRequired;
  }
  if (toolRequirements.missingToolCount != 0) {
    return TargetLegalizationOptionalNativeToolStatus::Missing;
  }
  if (toolRequirements.requiredToolCount != 0) {
    return TargetLegalizationOptionalNativeToolStatus::Available;
  }
  return TargetLegalizationOptionalNativeToolStatus::NotRequired;
}

TargetPackageArtifactRequirements
packageArtifactRequirementsForDecision(const TargetPackageDecision &decision,
                                       TargetLegalizationPackageMode mode) {
  TargetPackageArtifactRequirements requirements;
  requirements.target = decision.target;
  requirements.targetName = decision.targetName;
  requirements.packageMode = mode;
  requirements.packageModeName = targetLegalizationPackageModeName(mode);
  requirements.evidenceIds.push_back(evidenceId(
      decision.target,
      "package-artifacts." + std::string(requirements.packageModeName)));

  if (!decision.packageBuildSupported ||
      mode == TargetLegalizationPackageMode::Unsupported) {
    return requirements;
  }

  switch (decision.target) {
  case TargetKind::Metal:
    requirements.requiredPathArtifactKeys = {"backendSource", "intermediate",
                                             "nativeBinary"};
    break;
  case TargetKind::Vulkan:
    requirements.requiredPathArtifactKeys = {"backendAssembly", "nativeBinary"};
    break;
  case TargetKind::DirectX:
  case TargetKind::OpenGL:
    requirements.requiredPathArtifactKeys = {"backendSource", "nativeBinary"};
    requirements.requiresNativeBinaryStatus = true;
    requirements.allowsPlannedNativeBinary = true;
    requirements.allowsPlannedNativeSourceEvidence = true;
    break;
  case TargetKind::Auto:
    break;
  }

  for (const std::string &key : requirements.requiredPathArtifactKeys) {
    requirements.evidenceIds.push_back(
        evidenceId(decision.target, "package-artifact.required." + key));
  }
  if (requirements.requiresNativeBinaryStatus) {
    requirements.evidenceIds.push_back(
        evidenceId(decision.target, "package-artifact.native-binary-status."
                                    "required"));
  }
  if (requirements.allowsPlannedNativeBinary) {
    requirements.evidenceIds.push_back(evidenceId(
        decision.target, "package-artifact.planned-native-binary.allowed"));
  }
  if (requirements.allowsPlannedNativeSourceEvidence) {
    requirements.evidenceIds.push_back(
        evidenceId(decision.target,
                   "package-artifact.planned-native-source-evidence.allowed"));
  }

  return requirements;
}

TargetLegalizationState
stateForDecision(const TargetPackageDecision &decision) {
  return packageModeKindForDecision(decision) ==
                 TargetLegalizationPackageMode::Unsupported
             ? TargetLegalizationState::Rejected
             : TargetLegalizationState::Legalized;
}

std::string evidenceId(TargetKind target, std::string_view suffix) {
  return "target-legalization.v1." + targetName(target) + "." +
         std::string(suffix);
}

void appendCapabilityEvidenceIds(std::vector<std::string> &evidenceIds,
                                 TargetKind target, std::string_view role,
                                 const std::vector<TargetCapability> &caps) {
  for (const TargetCapability &capability : caps) {
    evidenceIds.push_back(
        evidenceId(target, "capability." + std::string(role) + "." +
                               targetLegalizationCapabilityId(capability)));
  }
}

bool isABIFactCapability(const TargetCapability &capability) {
  return isABIFactKind(capability.kind);
}

bool isToolRequirementCapability(const TargetCapability &capability) {
  return isToolRequirementKind(capability.kind);
}

TargetLegalizationABIRecord
abiRecordFromCapability(const TargetCapability &capability,
                        std::string_view role) {
  TargetLegalizationABIRecord record;
  record.target = capability.target;
  record.kind = capability.kind;
  record.name = capability.name;
  record.evidenceId = evidenceId(capability.target, "abi." + std::string(role) +
                                                        "." + capability.kind +
                                                        "." + capability.name);
  return record;
}

TargetLegalizationToolRequirementRecord
toolRequirementRecordFromCapability(const TargetCapability &capability,
                                    std::string_view role) {
  TargetLegalizationToolRequirementRecord record;
  record.target = capability.target;
  record.kind = v0ToolRequirementKind(capability.kind);
  record.name = capability.name;
  record.evidenceId = evidenceId(capability.target,
                                 "tool-requirement." + std::string(role) + "." +
                                     record.kind + "." + capability.name);
  return record;
}

void appendToolRequirementRecord(
    TargetLegalizationToolRequirementSummary &summary,
    const TargetCapability &capability, std::string_view role) {
  TargetLegalizationToolRequirementRecord record =
      toolRequirementRecordFromCapability(capability, role);
  const std::string toolId = toolRequirementId(record);
  if (role == "missing") {
    if (containsString(summary.missingToolIds, toolId)) {
      return;
    }
    summary.missingToolIds.push_back(toolId);
    summary.evidenceIds.push_back(record.evidenceId);
    summary.missingRecords.push_back(std::move(record));
    return;
  }

  if (containsString(summary.requiredToolIds, toolId)) {
    return;
  }
  summary.requiredToolIds.push_back(toolId);
  summary.evidenceIds.push_back(record.evidenceId);
  summary.requiredRecords.push_back(std::move(record));
}

void appendRequiredNativePackageToolRequirement(
    TargetLegalizationToolRequirementSummary &summary, TargetKind target,
    std::string_view kind, std::string_view name) {
  appendToolRequirementRecord(
      summary,
      TargetCapability{target, std::string(kind), std::string(name)},
      "required");
}

void appendNativePackageToolRequirements(
    TargetLegalizationToolRequirementSummary &summary,
    const TargetPackageDecision &decision,
    const TargetNativePackageDescriptorPolicy &nativePackagePolicy) {
  if (decision.packageMode != "native") {
    return;
  }

  switch (decision.target) {
  case TargetKind::Metal:
  case TargetKind::Vulkan:
    for (const TargetNativePackageToolPolicy &tool :
         nativePackagePolicy.requiredTools) {
      appendRequiredNativePackageToolRequirement(summary, decision.target,
                                                 tool.requirementKind,
                                                 tool.requirementName.empty()
                                                     ? tool.name
                                                     : tool.requirementName);
    }
    return;
  case TargetKind::DirectX:
  case TargetKind::OpenGL:
  case TargetKind::Auto:
    return;
  }
}

TargetLegalizationDiagnostic
unsupportedDiagnosticForDecision(const HIRModule &module,
                                 const TargetPackageDecision &decision) {
  TargetLegalizationDiagnostic diagnostic;
  diagnostic.severity = DiagnosticSeverity::Error;
  diagnostic.target = decision.target;
  diagnostic.capabilities = decision.missingCapabilities;

  const std::vector<Diagnostic> predicateDiagnostics =
      predicateDiagnosticsForDecision(module, decision);
  if (!predicateDiagnostics.empty() && !decision.diagnostics.empty()) {
    const Diagnostic &projected = predicateDiagnostics.front();
    diagnostic.severity = projected.severity;
    diagnostic.evidenceId =
        evidenceId(decision.target, diagnosticEvidenceSuffix(projected.code));
    diagnostic.code = projected.code;
    diagnostic.message = projected.message;
    if (hasSourceLocation(projected.location)) {
      diagnostic.location = projected.location;
    }
    return diagnostic;
  }

  std::optional<SourceLocation> predicateLocation;
  if (!predicateDiagnostics.empty() &&
      hasSourceLocation(predicateDiagnostics.front().location)) {
    predicateLocation = predicateDiagnostics.front().location;
  }

  if (hasMissingDiagnosticCapability(decision,
                                     kRawStatementBackendInputDiagnostic)) {
    diagnostic.evidenceId =
        evidenceId(decision.target, "diagnostic.raw-statement.unsupported");
    diagnostic.code = std::string(kRawStatementBackendInputDiagnostic);
    diagnostic.message =
        "target '" + decision.targetName +
        "' cannot build a package while HIR contains raw statements that have "
        "not been explicitly backend-legalized";
    return diagnostic;
  }

  if (decision.target == TargetKind::Vulkan &&
      hasMissingDiagnosticCapability(decision,
                                     kVulkanRuntimeResourceArrayDiagnostic) &&
      !predicateDiagnostics.empty() &&
      predicateDiagnostics.front().message.find("texture/sampler") !=
          std::string::npos) {
    diagnostic.evidenceId =
        evidenceId(decision.target, "diagnostic.target.unsupported");
    diagnostic.code = "target.unsupported";
    diagnostic.message = "target '" + decision.targetName +
                         "' cannot build a package for this module: " +
                         predicateDiagnostics.front().message;
    diagnostic.location = std::move(predicateLocation);
    return diagnostic;
  }

  diagnostic.evidenceId =
      evidenceId(decision.target, "diagnostic.target.unsupported");
  diagnostic.code = "target.unsupported";
  diagnostic.message = "target '" + decision.targetName +
                       "' cannot build a package for this module";
  diagnostic.location = std::move(predicateLocation);
  return diagnostic;
}

TargetLegalizationABIFacts
abiFactsForDecision(const TargetPackageDecision &decision) {
  TargetLegalizationABIFacts facts;
  facts.target = decision.target;
  for (const TargetCapability &capability : decision.requiredCapabilities) {
    if (!isABIFactCapability(capability)) {
      continue;
    }
    TargetLegalizationABIRecord record =
        abiRecordFromCapability(capability, "required");
    facts.requiredFacts.push_back(targetCapabilityId(capability));
    facts.evidenceIds.push_back(record.evidenceId);
    facts.requiredRecords.push_back(std::move(record));
  }
  for (const TargetCapability &capability : decision.missingCapabilities) {
    if (!isABIFactCapability(capability)) {
      continue;
    }
    TargetLegalizationABIRecord record =
        abiRecordFromCapability(capability, "missing");
    facts.missingFacts.push_back(targetCapabilityId(capability));
    facts.evidenceIds.push_back(record.evidenceId);
    facts.missingRecords.push_back(std::move(record));
  }
  if (!decision.packageBuildSupported) {
    facts.state = TargetLegalizationABIState::Unsupported;
  } else if (!facts.requiredRecords.empty() || !facts.missingRecords.empty()) {
    facts.state = TargetLegalizationABIState::Present;
  } else {
    facts.state = TargetLegalizationABIState::Empty;
  }
  facts.complete = facts.state != TargetLegalizationABIState::Unsupported;
  facts.evidenceIds.insert(
      facts.evidenceIds.begin(),
      evidenceId(decision.target,
                 "abi." +
                     std::string(targetLegalizationABIStateName(facts.state))));
  return facts;
}

TargetLegalizationToolRequirementSummary
toolRequirementsForDecision(
    const TargetPackageDecision &decision,
    const TargetNativePackageDescriptorPolicy &nativePackagePolicy) {
  TargetLegalizationToolRequirementSummary summary;
  summary.target = decision.target;
  for (const TargetCapability &capability : decision.requiredCapabilities) {
    if (!isToolRequirementCapability(capability)) {
      continue;
    }
    appendToolRequirementRecord(summary, capability, "required");
  }
  for (const TargetCapability &capability : decision.missingCapabilities) {
    if (!isToolRequirementCapability(capability)) {
      continue;
    }
    appendToolRequirementRecord(summary, capability, "missing");
  }
  appendNativePackageToolRequirements(summary, decision, nativePackagePolicy);
  summary.requiredToolCount = summary.requiredRecords.size();
  summary.missingToolCount = summary.missingRecords.size();
  summary.evidenceIds.insert(
      summary.evidenceIds.begin(),
      evidenceId(decision.target, summary.requiredRecords.empty() &&
                                          summary.missingRecords.empty()
                                      ? "tool-requirements.empty"
                                      : "tool-requirements.present"));
  return summary;
}

TargetLegalizationRewriteCollection
rewriteCollectionForDecision(
    const TargetPackageDecision &decision,
    const TargetLegalizationResourceBindingFacts &resourceBindings) {
  TargetLegalizationRewriteCollection collection;
  collection.target = decision.target;
  collection.state = decision.packageBuildSupported
                         ? TargetLegalizationRewriteState::Unchanged
                         : TargetLegalizationRewriteState::Unsupported;
  collection.complete = decision.packageBuildSupported;

  if (decision.packageBuildSupported) {
    auto appendAppliedResourceBindingRewrite =
        [&](std::string name, std::string description) {
          collection.state = TargetLegalizationRewriteState::Rewritten;
          TargetLegalizationRewriteRecord record;
          record.target = decision.target;
          record.state = collection.state;
          record.applied = true;
          record.kind = "resource-binding";
          record.name = std::move(name);
          record.description = std::move(description);
          record.evidenceId =
              evidenceId(decision.target,
                         "rewrite.applied.resource-binding." + record.name);
          collection.records.push_back(std::move(record));
        };

    const bool rewritesOpenGLBindingSlots =
        decision.target == TargetKind::OpenGL &&
        std::any_of(resourceBindings.records.begin(),
                    resourceBindings.records.end(),
                    [](const TargetLegalizationResourceBindingRecord &binding) {
                      return binding.argumentIndex.has_value() &&
                             binding.binding.has_value() &&
                             *binding.argumentIndex != *binding.binding;
                    });
    if (rewritesOpenGLBindingSlots) {
      appendAppliedResourceBindingRewrite(
          "program-resource-binding-normalization",
          "OpenGL source package emission canonicalized descriptor "
          "set/binding pairs to program resource binding slots");
    }

    const bool rewritesMetalArgumentSlots =
        decision.target == TargetKind::Metal &&
        std::any_of(resourceBindings.records.begin(),
                    resourceBindings.records.end(),
                    [](const TargetLegalizationResourceBindingRecord &binding) {
                      return binding.argumentIndex.has_value() &&
                             ((binding.binding.has_value() &&
                               *binding.argumentIndex != *binding.binding) ||
                              (binding.set.has_value() && *binding.set != 0));
                    });
    if (rewritesMetalArgumentSlots) {
      appendAppliedResourceBindingRewrite(
          "metal-argument-slot-packing",
          "Metal native emission canonicalized descriptor set/binding "
          "coordinates to packed kernel argument slots");
    }

    if (collection.records.empty()) {
      TargetLegalizationRewriteRecord record;
      record.target = decision.target;
      record.state = collection.state;
      record.applied = false;
      record.kind = "none";
      record.name = "no-op";
      record.description =
          "no target legalization rewrites were required or applied";
      record.evidenceId =
          evidenceId(decision.target, "rewrite.unchanged.no-op");
      collection.records.push_back(std::move(record));
    }
  } else {
    const bool hasRawStatementDiagnostic = hasMissingDiagnosticCapability(
        decision, kRawStatementBackendInputDiagnostic);
    TargetLegalizationRewriteRecord record;
    record.target = decision.target;
    record.state = collection.state;
    record.applied = false;
    record.kind = "unsupported";
    record.name =
        hasRawStatementDiagnostic ? "raw-statement-blocked" : "target-blocked";
    record.description =
        hasRawStatementDiagnostic
            ? "raw HIR statements must be legalized before target rewrites can "
              "be applied"
            : "target package support is unavailable, so no target rewrites "
              "were applied";
    record.evidenceId =
        evidenceId(decision.target, hasRawStatementDiagnostic
                                        ? "rewrite.unsupported.raw-statement"
                                        : "rewrite.unsupported.target");
    collection.records.push_back(std::move(record));
  }
  collection.complete =
      collection.state != TargetLegalizationRewriteState::Unsupported;
  collection.evidenceIds.push_back(evidenceId(
      decision.target,
      "rewrite." +
          std::string(targetLegalizationRewriteStateName(collection.state))));
  for (const TargetLegalizationRewriteRecord &record : collection.records) {
    collection.evidenceIds.push_back(record.evidenceId);
  }
  return collection;
}

TargetLegalizationResult resultFromDecision(
    const HIRModule &module, const TargetPackageDecision &decision,
    const TargetPackageSelection &selection, TargetKind requestedTarget) {
  TargetLegalizationResult result;
  result.requestedTarget = requestedTarget;
  result.target = decision.target;
  result.targetName = decision.targetName;
  result.packageSelection = selection;
  result.packageDecision = decision;
  result.nativeImplemented = decision.nativeImplemented;
  result.sourcePackageSupported = decision.sourcePackageSupported;
  result.packageBuildSupported = decision.packageBuildSupported;
  result.packageMode = decision.packageMode;
  result.packageDecisionReason = decision.packageDecisionReason;
  result.packageRankScore = decision.packageRankScore;
  result.requiredCapabilities = decision.requiredCapabilities;
  result.missingCapabilities = decision.missingCapabilities;
  result.supportStatus = supportStatusForDecision(decision);
  result.state = stateForDecision(decision);
  result.packageModeKind = packageModeKindForDecision(decision);
  result.packageArtifactRequirements =
      packageArtifactRequirementsForDecision(decision, result.packageModeKind);
  result.sourcePackageDescriptorPolicy =
      targetSourcePackageDescriptorPolicy(result.packageArtifactRequirements,
                                          decision.target);
  result.nativePackageDescriptorPolicy =
      targetNativePackageDescriptorPolicy(result.packageArtifactRequirements,
                                          decision.target);
  result.abiFacts = abiFactsForDecision(decision);
  result.resourceBindings =
      resourceBindingFactsForModule(module, decision.target);
  result.toolRequirements =
      toolRequirementsForDecision(decision, result.nativePackageDescriptorPolicy);
  result.packageDecisionProvenance =
      packageDecisionProvenanceForDecision(decision, result.packageModeKind);
  result.optionalNativeToolStatus = optionalNativeToolStatusForDecision(
      result.packageModeKind, result.toolRequirements);
  result.optionalNativeToolStatusName =
      targetLegalizationOptionalNativeToolStatusName(
          result.optionalNativeToolStatus);
  result.optionalNativeToolMissing =
      result.optionalNativeToolStatus ==
      TargetLegalizationOptionalNativeToolStatus::Missing;
  result.rewrites =
      rewriteCollectionForDecision(decision, result.resourceBindings);
  result.rewriteRecords = result.rewrites.records;

  result.evidenceIds.push_back(evidenceId(decision.target, "decision"));
  result.evidenceIds.push_back(evidenceId(
      decision.target,
      "state." + std::string(targetLegalizationStateName(result.state))));
  result.evidenceIds.push_back(
      evidenceId(decision.target,
                 "support." + std::string(targetLegalizationSupportStatusName(
                                  result.supportStatus))));
  result.evidenceIds.push_back(evidenceId(
      decision.target,
      "package-mode." + std::string(targetLegalizationPackageModeName(
                            result.packageModeKind))));
  result.evidenceIds.push_back(evidenceId(
      decision.target,
      "package-provenance." +
          std::string(targetLegalizationPackageDecisionProvenanceName(
              result.packageDecisionProvenance))));
  if (result.optionalNativeToolMissing) {
    result.evidenceIds.push_back(
        evidenceId(decision.target, "optional-native-tool.missing"));
  }
  result.evidenceIds.push_back(evidenceId(
      decision.target, "package-reason." + result.packageDecisionReason));
  appendCapabilityEvidenceIds(result.evidenceIds, decision.target, "required",
                              result.requiredCapabilities);
  appendCapabilityEvidenceIds(result.evidenceIds, decision.target, "missing",
                              result.missingCapabilities);

  if (!decision.packageBuildSupported) {
    result.diagnostics.push_back(unsupportedDiagnosticForDecision(module,
                                                                  decision));
    result.evidenceIds.push_back(result.diagnostics.back().evidenceId);
  }
  result.evidenceIds.insert(result.evidenceIds.end(),
                            result.abiFacts.evidenceIds.begin(),
                            result.abiFacts.evidenceIds.end());
  result.evidenceIds.insert(result.evidenceIds.end(),
                            result.resourceBindings.evidenceIds.begin(),
                            result.resourceBindings.evidenceIds.end());
  result.evidenceIds.insert(result.evidenceIds.end(),
                            result.toolRequirements.evidenceIds.begin(),
                            result.toolRequirements.evidenceIds.end());
  result.evidenceIds.insert(
      result.evidenceIds.end(),
      result.packageArtifactRequirements.evidenceIds.begin(),
      result.packageArtifactRequirements.evidenceIds.end());
  result.evidenceIds.insert(result.evidenceIds.end(),
                            result.rewrites.evidenceIds.begin(),
                            result.rewrites.evidenceIds.end());
  return result;
}

TargetLegalizationDiagnosticSummary diagnosticSummaryForDiagnostics(
    const std::vector<TargetLegalizationDiagnostic> &diagnostics) {
  TargetLegalizationDiagnosticSummary summary;
  summary.diagnosticCount = diagnostics.size();
  summary.severities.reserve(diagnostics.size());
  summary.codes.reserve(diagnostics.size());
  summary.evidenceIds.reserve(diagnostics.size());
  for (const TargetLegalizationDiagnostic &diagnostic : diagnostics) {
    summary.severities.push_back(toString(diagnostic.severity));
    switch (diagnostic.severity) {
    case DiagnosticSeverity::Note:
      ++summary.noteCount;
      break;
    case DiagnosticSeverity::Warning:
      ++summary.warningCount;
      break;
    case DiagnosticSeverity::Error:
      ++summary.errorCount;
      break;
    }
    summary.codes.push_back(diagnostic.code);
    summary.evidenceIds.push_back(diagnostic.evidenceId);
  }
  summary.hasErrors = summary.errorCount != 0;
  return summary;
}

bool sameDiagnosticSummary(const TargetLegalizationDiagnosticSummary &lhs,
                           const TargetLegalizationDiagnosticSummary &rhs) {
  return lhs.diagnosticCount == rhs.diagnosticCount &&
         lhs.noteCount == rhs.noteCount &&
         lhs.warningCount == rhs.warningCount &&
         lhs.errorCount == rhs.errorCount && lhs.hasErrors == rhs.hasErrors &&
         sameStringVector(lhs.severities, rhs.severities) &&
         sameStringVector(lhs.codes, rhs.codes) &&
         sameStringVector(lhs.evidenceIds, rhs.evidenceIds);
}

void appendABIRecordInvariantDiagnostics(
    std::vector<std::string> &diagnostics,
    const std::vector<TargetLegalizationABIRecord> &records,
    const std::vector<std::string> &facts,
    const std::vector<std::string> &evidenceIds, TargetKind resolvedTarget,
    std::string_view role) {
  if (records.size() != facts.size()) {
    diagnostics.push_back(std::string("ABI ") + std::string(role) +
                          " record/fact count mismatch");
  }

  for (std::size_t index = 0; index < records.size(); ++index) {
    const TargetLegalizationABIRecord &record = records[index];
    if (record.target != resolvedTarget) {
      diagnostics.push_back(std::string("ABI ") + std::string(role) +
                            " record target mismatch");
    }
    if (record.evidenceId.empty()) {
      diagnostics.push_back(std::string("ABI ") + std::string(role) +
                            " record evidence id is empty");
    } else if (!containsString(evidenceIds, record.evidenceId)) {
      diagnostics.push_back(std::string("ABI ") + std::string(role) +
                            " record evidence missing from ABI evidenceIds: " +
                            record.evidenceId);
    }

    const std::string expectedFact = abiFactId(record);
    if (index < facts.size() && facts[index] != expectedFact) {
      diagnostics.push_back(std::string("ABI ") + std::string(role) +
                            " fact mismatch");
    }
  }
}

void appendToolRequirementRecordInvariantDiagnostics(
    std::vector<std::string> &diagnostics,
    const std::vector<TargetLegalizationToolRequirementRecord> &records,
    const std::vector<std::string> &toolIds,
    const std::vector<std::string> &evidenceIds, TargetKind resolvedTarget,
    std::string_view role) {
  if (records.size() != toolIds.size()) {
    diagnostics.push_back(std::string("tool requirement ") + std::string(role) +
                          " record/tool id count mismatch");
  }

  for (std::size_t index = 0; index < records.size(); ++index) {
    const TargetLegalizationToolRequirementRecord &record = records[index];
    if (record.target != resolvedTarget) {
      diagnostics.push_back(std::string("tool requirement ") +
                            std::string(role) + " record target mismatch");
    }
    if (!isToolRequirementKind(record.kind)) {
      diagnostics.push_back(std::string("tool requirement ") +
                            std::string(role) + " record kind mismatch");
    }
    if (record.evidenceId.empty()) {
      diagnostics.push_back(std::string("tool requirement ") +
                            std::string(role) + " record evidence id is empty");
    } else if (!containsString(evidenceIds, record.evidenceId)) {
      diagnostics.push_back(
          std::string("tool requirement ") + std::string(role) +
          " record evidence missing from tool requirement evidenceIds: " +
          record.evidenceId);
    }

    const std::string expectedToolId = toolRequirementId(record);
    if (index < toolIds.size() && toolIds[index] != expectedToolId) {
      diagnostics.push_back(std::string("tool requirement ") +
                            std::string(role) + " id mismatch");
    }
  }
}

void appendToolRequirementCapabilityInvariantDiagnostics(
    std::vector<std::string> &diagnostics,
    const std::vector<std::string> &toolIds,
    const std::vector<std::string> &capabilityIds, TargetKind target,
    TargetLegalizationPackageMode packageMode, std::string_view role) {
  for (const std::string &toolId : toolIds) {
    if (containsString(capabilityIds, toolId)) {
      continue;
    }
    const bool allowedReportOnlyNativePackageTool =
        role == "required" &&
        packageMode == TargetLegalizationPackageMode::Native &&
        isNativePackageToolRequirementId(target, toolId);
    if (!allowedReportOnlyNativePackageTool) {
      diagnostics.push_back(std::string("tool requirement ") +
                            std::string(role) + " id missing from " +
                            std::string(role) + "CapabilityIds: " + toolId);
    }
  }

  for (const std::string &capabilityId : capabilityIds) {
    if (isToolRequirementId(capabilityId) &&
        !containsString(toolIds, capabilityId)) {
      diagnostics.push_back(std::string(role) +
                            "CapabilityIds tool requirement missing from "
                            "tool requirements: " +
                            capabilityId);
    }
  }
}

void appendABIFactCapabilityInvariantDiagnostics(
    std::vector<std::string> &diagnostics,
    const std::vector<std::string> &facts,
    const std::vector<std::string> &capabilityIds, std::string_view role) {
  for (const std::string &fact : facts) {
    if (!containsString(capabilityIds, fact)) {
      diagnostics.push_back(std::string("ABI ") + std::string(role) +
                            " fact missing from " + std::string(role) +
                            "CapabilityIds: " + fact);
    }
  }

  for (const std::string &capabilityId : capabilityIds) {
    if (isABIFactId(capabilityId) && !containsString(facts, capabilityId)) {
      diagnostics.push_back(std::string(role) +
                            "CapabilityIds ABI fact missing from ABI " +
                            std::string(role) + "Facts: " + capabilityId);
    }
  }
}

void appendEvidenceIdShapeDiagnostics(std::vector<std::string> &diagnostics,
                                      const std::vector<std::string> &ids,
                                      TargetKind resolvedTarget,
                                      std::string_view group,
                                      std::vector<std::string> &seenNestedIds) {
  const std::string targetPrefix = "target-legalization.v1." +
                                   std::string(targetName(resolvedTarget)) +
                                   ".";
  std::vector<std::string> seenInGroup;
  for (const std::string &id : ids) {
    if (id.empty()) {
      continue;
    }
    if (containsString(seenInGroup, id)) {
      diagnostics.push_back(std::string(group) +
                            " evidence id is duplicated: " + id);
    }
    seenInGroup.push_back(id);
    if (resolvedTarget != TargetKind::Auto && id.rfind(targetPrefix, 0) != 0) {
      diagnostics.push_back(std::string(group) +
                            " evidence id target mismatch: " + id);
    }
    if (containsString(seenNestedIds, id)) {
      diagnostics.push_back(
          "nested evidence id is duplicated across groups: " + id);
    }
    seenNestedIds.push_back(id);
  }
}

void appendResourceBindingRecordInvariantDiagnostics(
    std::vector<std::string> &diagnostics,
    const TargetLegalizationResourceBindingFacts &resourceBindings,
    TargetKind resolvedTarget) {
  for (const TargetLegalizationResourceBindingRecord &record :
       resourceBindings.records) {
    if (record.target != resolvedTarget) {
      diagnostics.push_back("resource binding record target mismatch");
    }
    if (record.stage.empty()) {
      diagnostics.push_back("resource binding record stage is empty");
    }
    if (record.sourceEntryPoint.empty()) {
      diagnostics.push_back("resource binding record source entry point is "
                            "empty");
    }
    if (record.backendEntryPoint.empty()) {
      diagnostics.push_back("resource binding record backend entry point is "
                            "empty");
    }
    if (record.name.empty()) {
      diagnostics.push_back("resource binding record name is empty");
    }
    if (record.kind.empty()) {
      diagnostics.push_back("resource binding record kind is empty");
    }
    if (record.sourceType.empty()) {
      diagnostics.push_back("resource binding record sourceType is empty");
    }
    if (record.addressSpace.empty()) {
      diagnostics.push_back("resource binding record addressSpace is empty");
    }
    if (record.abi.empty()) {
      diagnostics.push_back("resource binding record ABI is empty");
    }
    if (record.bindingClass.empty()) {
      diagnostics.push_back("resource binding record bindingClass is empty");
    }
    if (record.kind == "storage_image") {
      if (!record.storageImageAccess.has_value()) {
        diagnostics.push_back(
            "resource binding record storage-image access is empty");
      } else if (*record.storageImageAccess != "read" &&
                 *record.storageImageAccess != "write" &&
                 *record.storageImageAccess != "read_write") {
        diagnostics.push_back(
            "resource binding record storage-image access is invalid");
      }
    } else if (record.storageImageAccess.has_value()) {
      diagnostics.push_back(
          "resource binding non-storage-image record storageImageAccess is set");
    }
    if (record.set.has_value() != record.binding.has_value()) {
      diagnostics.push_back("resource binding record set/binding mismatch");
    }
    if (record.evidenceId.empty()) {
      diagnostics.push_back("resource binding record evidence id is empty");
    } else if (!containsString(resourceBindings.evidenceIds,
                               record.evidenceId)) {
      diagnostics.push_back(
          "resource binding record evidence missing from resource binding "
          "evidenceIds: " +
          record.evidenceId);
    }
  }
}

std::vector<std::string>
expectedPackageArtifactKeys(TargetKind target,
                            TargetLegalizationPackageMode packageMode) {
  if (packageMode == TargetLegalizationPackageMode::Unsupported) {
    return {};
  }

  switch (target) {
  case TargetKind::Metal:
    return {"backendSource", "intermediate", "nativeBinary"};
  case TargetKind::Vulkan:
    return {"backendAssembly", "nativeBinary"};
  case TargetKind::DirectX:
  case TargetKind::OpenGL:
    return {"backendSource", "nativeBinary"};
  case TargetKind::Auto:
    return {};
  }
  return {};
}

bool expectedPackageArtifactRequiresNativeBinaryStatus(
    TargetKind target, TargetLegalizationPackageMode packageMode) {
  return packageMode != TargetLegalizationPackageMode::Unsupported &&
         (target == TargetKind::DirectX || target == TargetKind::OpenGL);
}

std::vector<std::string> expectedPackageArtifactEvidenceIds(
    const TargetPackageArtifactRequirements &requirements) {
  std::vector<std::string> evidenceIds;
  if (requirements.target == TargetKind::Auto) {
    return evidenceIds;
  }

  evidenceIds.push_back(evidenceId(
      requirements.target,
      "package-artifacts." + std::string(targetLegalizationPackageModeName(
                                 requirements.packageMode))));
  for (const std::string &key : requirements.requiredPathArtifactKeys) {
    evidenceIds.push_back(
        evidenceId(requirements.target, "package-artifact.required." + key));
  }
  if (requirements.requiresNativeBinaryStatus) {
    evidenceIds.push_back(evidenceId(requirements.target,
                                     "package-artifact."
                                     "native-binary-status.required"));
  }
  if (requirements.allowsPlannedNativeBinary) {
    evidenceIds.push_back(evidenceId(
        requirements.target, "package-artifact.planned-native-binary.allowed"));
  }
  if (requirements.allowsPlannedNativeSourceEvidence) {
    evidenceIds.push_back(
        evidenceId(requirements.target,
                   "package-artifact.planned-native-source-evidence.allowed"));
  }
  return evidenceIds;
}

TargetLegalizationPackageDecisionProvenance
packageDecisionProvenanceForContract(
    const TargetLegalizationContract &contract) {
  if (contract.state == TargetLegalizationState::Legalized &&
      contract.packageMode == TargetLegalizationPackageMode::Native) {
    return TargetLegalizationPackageDecisionProvenance::NativePackageAvailable;
  }
  if (contract.state == TargetLegalizationState::Legalized &&
      contract.packageMode == TargetLegalizationPackageMode::SourcePackage) {
    return TargetLegalizationPackageDecisionProvenance::SourcePackageOnly;
  }
  if (hasMissingCapabilityId(contract.missingCapabilityIds,
                             contract.resolvedTarget, "diagnostic",
                             kRawStatementBackendInputDiagnostic)) {
    return TargetLegalizationPackageDecisionProvenance::UnsupportedRawHIR;
  }
  if (isSourcePackageDecisionTarget(contract.resolvedTarget) &&
      !contract.sourcePackageSupported) {
    return TargetLegalizationPackageDecisionProvenance::UnsupportedSourceForm;
  }
  if (contract.nativeImplemented) {
    return TargetLegalizationPackageDecisionProvenance::UnsupportedNativeForm;
  }
  return TargetLegalizationPackageDecisionProvenance::Unsupported;
}

TargetLegalizationOptionalNativeToolStatus optionalNativeToolStatusForContract(
    const TargetLegalizationContract &contract) {
  return optionalNativeToolStatusForDecision(contract.packageMode,
                                             contract.toolRequirements);
}

bool optionalNativeToolMissingForContract(
    const TargetLegalizationContract &contract) {
  return optionalNativeToolStatusForContract(contract) ==
         TargetLegalizationOptionalNativeToolStatus::Missing;
}

TargetLegalizationSupportStatus
expectedSupportStatusForContract(const TargetLegalizationContract &contract) {
  if (contract.state != TargetLegalizationState::Legalized) {
    return TargetLegalizationSupportStatus::Unsupported;
  }
  switch (contract.packageMode) {
  case TargetLegalizationPackageMode::Native:
    return TargetLegalizationSupportStatus::NativePackage;
  case TargetLegalizationPackageMode::SourcePackage:
    return TargetLegalizationSupportStatus::SourcePackage;
  case TargetLegalizationPackageMode::Unsupported:
    return TargetLegalizationSupportStatus::Unsupported;
  }
  return TargetLegalizationSupportStatus::Unsupported;
}

TargetLegalizationTargetProfile
targetProfileForResult(const TargetLegalizationResult &result) {
  TargetLegalizationTargetProfile profile;
  profile.requestedTarget = result.requestedTarget;
  profile.requestedTargetName = targetName(result.requestedTarget);
  profile.preferredTarget = result.packageSelection.preferredTarget;
  profile.preferredTargetName =
      targetName(result.packageSelection.preferredTarget);
  profile.resolvedTarget = result.target;
  profile.resolvedTargetName =
      result.targetName.empty() ? targetName(result.target) : result.targetName;
  profile.selectedTarget = result.packageSelection.selectedTarget;
  profile.selectedTargetName =
      targetName(result.packageSelection.selectedTarget);
  profile.autoRequested = result.requestedTarget == TargetKind::Auto;
  profile.selectedTargetBuildable =
      result.packageSelection.selectedTargetBuildable;
  return profile;
}

} // namespace

const char *
targetLegalizationSupportStatusName(TargetLegalizationSupportStatus status) {
  switch (status) {
  case TargetLegalizationSupportStatus::Unsupported:
    return "unsupported";
  case TargetLegalizationSupportStatus::SourcePackage:
    return "source-package";
  case TargetLegalizationSupportStatus::NativePackage:
    return "native";
  }
  return "unsupported";
}

TargetLegalizationSupportStatus
targetLegalizationSupportStatusFromName(std::string_view name) {
  if (name == "native") {
    return TargetLegalizationSupportStatus::NativePackage;
  }
  if (name == "source-package") {
    return TargetLegalizationSupportStatus::SourcePackage;
  }
  return TargetLegalizationSupportStatus::Unsupported;
}

const char *targetLegalizationStateName(TargetLegalizationState state) {
  switch (state) {
  case TargetLegalizationState::Rejected:
    return "rejected";
  case TargetLegalizationState::Legalized:
    return "legalized";
  }
  return "rejected";
}

TargetLegalizationState targetLegalizationStateFromName(std::string_view name) {
  if (name == "legalized") {
    return TargetLegalizationState::Legalized;
  }
  return TargetLegalizationState::Rejected;
}

const char *
targetLegalizationPackageModeName(TargetLegalizationPackageMode mode) {
  switch (mode) {
  case TargetLegalizationPackageMode::Unsupported:
    return "unsupported";
  case TargetLegalizationPackageMode::SourcePackage:
    return "source-package";
  case TargetLegalizationPackageMode::Native:
    return "native";
  }
  return "unsupported";
}

TargetLegalizationPackageMode
targetLegalizationPackageModeFromName(std::string_view name) {
  if (name == "native") {
    return TargetLegalizationPackageMode::Native;
  }
  if (name == "source-package") {
    return TargetLegalizationPackageMode::SourcePackage;
  }
  return TargetLegalizationPackageMode::Unsupported;
}

const char *targetLegalizationPackageDecisionProvenanceName(
    TargetLegalizationPackageDecisionProvenance provenance) {
  switch (provenance) {
  case TargetLegalizationPackageDecisionProvenance::Unsupported:
    return "unsupported";
  case TargetLegalizationPackageDecisionProvenance::NativePackageAvailable:
    return "native-package-available";
  case TargetLegalizationPackageDecisionProvenance::SourcePackageOnly:
    return "source-package-only";
  case TargetLegalizationPackageDecisionProvenance::UnsupportedSourceForm:
    return "unsupported-source-form";
  case TargetLegalizationPackageDecisionProvenance::UnsupportedNativeForm:
    return "unsupported-native-form";
  case TargetLegalizationPackageDecisionProvenance::UnsupportedRawHIR:
    return "unsupported-raw-hir";
  }
  return "unsupported";
}

TargetLegalizationPackageDecisionProvenance
targetLegalizationPackageDecisionProvenanceFromName(std::string_view name) {
  if (name == "native-package-available") {
    return TargetLegalizationPackageDecisionProvenance::NativePackageAvailable;
  }
  if (name == "source-package-only") {
    return TargetLegalizationPackageDecisionProvenance::SourcePackageOnly;
  }
  if (name == "unsupported-source-form") {
    return TargetLegalizationPackageDecisionProvenance::UnsupportedSourceForm;
  }
  if (name == "unsupported-native-form") {
    return TargetLegalizationPackageDecisionProvenance::UnsupportedNativeForm;
  }
  if (name == "unsupported-raw-hir") {
    return TargetLegalizationPackageDecisionProvenance::UnsupportedRawHIR;
  }
  return TargetLegalizationPackageDecisionProvenance::Unsupported;
}

const char *targetLegalizationOptionalNativeToolStatusName(
    TargetLegalizationOptionalNativeToolStatus status) {
  switch (status) {
  case TargetLegalizationOptionalNativeToolStatus::NotRequired:
    return "not-required";
  case TargetLegalizationOptionalNativeToolStatus::Available:
    return "available";
  case TargetLegalizationOptionalNativeToolStatus::Missing:
    return "missing";
  }
  return "not-required";
}

TargetLegalizationOptionalNativeToolStatus
targetLegalizationOptionalNativeToolStatusFromName(std::string_view name) {
  if (name == "available") {
    return TargetLegalizationOptionalNativeToolStatus::Available;
  }
  if (name == "missing") {
    return TargetLegalizationOptionalNativeToolStatus::Missing;
  }
  return TargetLegalizationOptionalNativeToolStatus::NotRequired;
}

const char *targetLegalizationABIStateName(TargetLegalizationABIState state) {
  switch (state) {
  case TargetLegalizationABIState::Empty:
    return "empty";
  case TargetLegalizationABIState::Present:
    return "present";
  case TargetLegalizationABIState::Unsupported:
    return "unsupported";
  }
  return "empty";
}

TargetLegalizationABIState
targetLegalizationABIStateFromName(std::string_view name) {
  if (name == "present") {
    return TargetLegalizationABIState::Present;
  }
  if (name == "unsupported") {
    return TargetLegalizationABIState::Unsupported;
  }
  return TargetLegalizationABIState::Empty;
}

const char *
targetLegalizationRewriteStateName(TargetLegalizationRewriteState state) {
  switch (state) {
  case TargetLegalizationRewriteState::Empty:
    return "empty";
  case TargetLegalizationRewriteState::Unchanged:
    return "unchanged";
  case TargetLegalizationRewriteState::Rewritten:
    return "rewritten";
  case TargetLegalizationRewriteState::Unsupported:
    return "unsupported";
  }
  return "empty";
}

TargetLegalizationRewriteState
targetLegalizationRewriteStateFromName(std::string_view name) {
  if (name == "unchanged") {
    return TargetLegalizationRewriteState::Unchanged;
  }
  if (name == "rewritten") {
    return TargetLegalizationRewriteState::Rewritten;
  }
  if (name == "unsupported") {
    return TargetLegalizationRewriteState::Unsupported;
  }
  return TargetLegalizationRewriteState::Empty;
}

bool targetPackageArtifactRequirementsAllowNativeBinaryStatus(
    const TargetPackageArtifactRequirements &requirements,
    std::string_view nativeBinaryStatus) {
  if (!requirements.requiresNativeBinaryStatus) {
    return nativeBinaryStatus.empty();
  }
  if (nativeBinaryStatus == "planned") {
    return requirements.allowsPlannedNativeBinary &&
           requirements.allowsPlannedNativeSourceEvidence;
  }
  return nativeBinaryStatus == "emitted" || nativeBinaryStatus == "validated";
}

bool targetLegalizationProjectionAllowsSourcePackageNativeBinaryStatus(
    const TargetLegalizationContractProjection &projection,
    std::string_view nativeBinaryStatus) {
  if (!targetLegalizationProjectionSupportsPackage(projection) ||
      projection.packageMode != TargetLegalizationPackageMode::SourcePackage ||
      projection.supportStatus !=
          TargetLegalizationSupportStatus::SourcePackage) {
    return false;
  }
  return targetPackageArtifactRequirementsAllowNativeBinaryStatus(
      projection.packageArtifactRequirements, nativeBinaryStatus);
}

bool targetPackageArtifactRequirementsRequireNativeBinaryArtifact(
    const TargetPackageArtifactRequirements &requirements,
    std::string_view nativeBinaryStatus) {
  if (!containsString(requirements.requiredPathArtifactKeys, "nativeBinary")) {
    return false;
  }
  if (requirements.requiresNativeBinaryStatus &&
      nativeBinaryStatus == "planned" &&
      targetPackageArtifactRequirementsAllowNativeBinaryStatus(
          requirements, nativeBinaryStatus)) {
    return false;
  }
  return true;
}

bool targetLegalizationProjectionRequiresSourcePackageNativeBinaryArtifact(
    const TargetLegalizationContractProjection &projection,
    std::string_view nativeBinaryStatus) {
  if (!targetLegalizationProjectionAllowsSourcePackageNativeBinaryStatus(
          projection, nativeBinaryStatus)) {
    return false;
  }
  return targetPackageArtifactRequirementsRequireNativeBinaryArtifact(
      projection.packageArtifactRequirements, nativeBinaryStatus);
}

const char *targetSourcePackageDescriptorOptimizationLevelModeName(
    TargetSourcePackageDescriptorOptimizationLevelMode mode) {
  switch (mode) {
  case TargetSourcePackageDescriptorOptimizationLevelMode::Unknown:
    return "unknown";
  case TargetSourcePackageDescriptorOptimizationLevelMode::RequestedLevel:
    return "requested-level";
  }
  return "unknown";
}

const char *targetSourcePackageDescriptorToolProvenanceModeName(
    TargetSourcePackageDescriptorToolProvenanceMode mode) {
  switch (mode) {
  case TargetSourcePackageDescriptorToolProvenanceMode::Planned:
    return "planned";
  case TargetSourcePackageDescriptorToolProvenanceMode::NativeCompiler:
    return "native-compiler";
  case TargetSourcePackageDescriptorToolProvenanceMode::NativeValidator:
    return "native-validator";
  }
  return "planned";
}

const char *targetSourcePackageDescriptorOptimizationEvidenceModeName(
    TargetSourcePackageDescriptorOptimizationEvidenceMode mode) {
  switch (mode) {
  case TargetSourcePackageDescriptorOptimizationEvidenceMode::None:
    return "none";
  case TargetSourcePackageDescriptorOptimizationEvidenceMode::DirectXDxc:
    return "directx-dxc";
  }
  return "none";
}

const char *targetNativePackageDescriptorOptimizationEvidenceModeName(
    TargetNativePackageDescriptorOptimizationEvidenceMode mode) {
  switch (mode) {
  case TargetNativePackageDescriptorOptimizationEvidenceMode::None:
    return "none";
  case TargetNativePackageDescriptorOptimizationEvidenceMode::MetalXcrunMetal:
    return "metal-xcrun-metal";
  case TargetNativePackageDescriptorOptimizationEvidenceMode::VulkanSpirvOpt:
    return "vulkan-spirv-opt";
  }
  return "none";
}

TargetSourcePackageDescriptorPolicy targetSourcePackageDescriptorPolicy(
    const TargetPackageArtifactRequirements &requirements,
    std::string_view nativeBinaryStatus, TargetKind target,
    std::string_view nativeToolName) {
  const TargetKind resolvedTarget =
      target == TargetKind::Auto ? requirements.target : target;
  TargetSourcePackageDescriptorPolicy policy;
  policy.target = resolvedTarget;
  policy.targetName = requirements.targetName.empty()
                          ? std::string(targetName(resolvedTarget))
                          : requirements.targetName;
  policy.nativeBinaryStatus = std::string(nativeBinaryStatus);

  if (requirements.packageMode !=
      TargetLegalizationPackageMode::SourcePackage) {
    return policy;
  }
  if (!targetPackageArtifactRequirementsAllowNativeBinaryStatus(
          requirements, nativeBinaryStatus)) {
    return policy;
  }

  switch (resolvedTarget) {
  case TargetKind::DirectX:
    policy.binaryKind = "directx.dxil";
    policy.optimizationEvidenceMode =
        TargetSourcePackageDescriptorOptimizationEvidenceMode::DirectXDxc;
    if (nativeBinaryStatus != "planned") {
      policy.validationStatus = "not-run";
      policy.optimizationLevelMode =
          TargetSourcePackageDescriptorOptimizationLevelMode::RequestedLevel;
      policy.toolProvenanceMode =
          TargetSourcePackageDescriptorToolProvenanceMode::NativeCompiler;
      policy.nativeToolName = "dxc";
      policy.nativeToolRole = "compiler";
      policy.nativeToolExecutable = "dxc";
      policy.nativeToolProbeName = "dxc";
    }
    break;
  case TargetKind::OpenGL:
    policy.binaryKind = "opengl.source";
    if (nativeBinaryStatus == "validated") {
      policy.validationStatus = "validated";
      policy.toolProvenanceMode =
          TargetSourcePackageDescriptorToolProvenanceMode::NativeValidator;
      policy.nativeToolName =
          nativeToolName.empty() ? "glslangValidator" : std::string(nativeToolName);
      policy.nativeToolRole = "validator";
      policy.nativeToolExecutable = policy.nativeToolName;
      policy.nativeToolProbeName = policy.nativeToolName;
    }
    break;
  case TargetKind::Auto:
  case TargetKind::Metal:
  case TargetKind::Vulkan:
    break;
  }

  if (!policy.binaryKind.empty()) {
    policy.supported = true;
    policy.includesNativeBinaryStatus = requirements.requiresNativeBinaryStatus;
    policy.requiresProducedNativeArtifact =
        targetPackageArtifactRequirementsRequireNativeBinaryArtifact(
            requirements, nativeBinaryStatus);
  }
  policy.toolProvenanceModeName =
      targetSourcePackageDescriptorToolProvenanceModeName(
          policy.toolProvenanceMode);
  policy.optimizationEvidenceModeName =
      targetSourcePackageDescriptorOptimizationEvidenceModeName(
          policy.optimizationEvidenceMode);
  return policy;
}

TargetSourcePackageDescriptorPolicy targetSourcePackageDescriptorPolicy(
    const TargetPackageArtifactRequirements &requirements, TargetKind target) {
  const TargetKind resolvedTarget =
      target == TargetKind::Auto ? requirements.target : target;
  if (requirements.packageMode !=
      TargetLegalizationPackageMode::SourcePackage) {
    return targetSourcePackageDescriptorPolicy(requirements, "", resolvedTarget);
  }
  return targetSourcePackageDescriptorPolicy(requirements, "planned",
                                             resolvedTarget);
}

TargetSourcePackageDescriptorPolicy targetSourcePackageDescriptorPolicy(
    const TargetLegalizationContractProjection &projection,
    std::string_view nativeBinaryStatus, std::string_view nativeToolName) {
  const TargetKind target = projection.targetProfile.resolvedTarget ==
                                    TargetKind::Auto
                                ? projection.packageArtifactRequirements.target
                                : projection.targetProfile.resolvedTarget;
  if (!targetLegalizationProjectionAllowsSourcePackageNativeBinaryStatus(
          projection, nativeBinaryStatus)) {
    TargetSourcePackageDescriptorPolicy policy;
    policy.target = target;
    policy.targetName =
        projection.packageArtifactRequirements.targetName.empty()
            ? std::string(targetName(target))
            : projection.packageArtifactRequirements.targetName;
    policy.nativeBinaryStatus = std::string(nativeBinaryStatus);
    return policy;
  }
  return targetSourcePackageDescriptorPolicy(
      projection.packageArtifactRequirements, nativeBinaryStatus, target,
      nativeToolName);
}

TargetSourcePackageDescriptorPolicy targetSourcePackageDescriptorPolicy(
    const TargetLegalizationContractProjection &projection) {
  const TargetKind target = projection.targetProfile.resolvedTarget ==
                                    TargetKind::Auto
                                ? projection.packageArtifactRequirements.target
                                : projection.targetProfile.resolvedTarget;
  if (!targetLegalizationProjectionSupportsPackage(projection) ||
      projection.packageMode != TargetLegalizationPackageMode::SourcePackage ||
      projection.supportStatus !=
          TargetLegalizationSupportStatus::SourcePackage) {
    return targetSourcePackageDescriptorPolicy(
        projection.packageArtifactRequirements, "", target);
  }
  return targetSourcePackageDescriptorPolicy(
      projection.packageArtifactRequirements, target);
}

TargetNativePackageDescriptorPolicy targetNativePackageDescriptorPolicy(
    const TargetPackageArtifactRequirements &requirements, TargetKind target) {
  const TargetKind resolvedTarget =
      target == TargetKind::Auto ? requirements.target : target;
  TargetNativePackageDescriptorPolicy policy;
  policy.target = resolvedTarget;
  policy.targetName = requirements.targetName.empty()
                          ? std::string(targetName(resolvedTarget))
                          : requirements.targetName;
  policy.optimizationEvidenceModeName =
      targetNativePackageDescriptorOptimizationEvidenceModeName(
          policy.optimizationEvidenceMode);

  if (requirements.target != resolvedTarget ||
      requirements.packageMode != TargetLegalizationPackageMode::Native ||
      !containsString(requirements.requiredPathArtifactKeys, "nativeBinary")) {
    return policy;
  }

  switch (resolvedTarget) {
  case TargetKind::Metal:
    if (!containsString(requirements.requiredPathArtifactKeys, "backendSource") ||
        !containsString(requirements.requiredPathArtifactKeys, "intermediate")) {
      return policy;
    }
    policy.supported = true;
    policy.binaryKind = "metal.metallib";
    policy.sourceArtifactKey = "backendSource";
    policy.nativeBinaryArtifactKey = "nativeBinary";
    policy.descriptorArtifactKey = "nativeArtifactDescriptor";
    policy.profileArtifactKey = "nativeProfile";
    policy.validationStatus = "not-run";
    policy.optimizationEvidenceMode =
        TargetNativePackageDescriptorOptimizationEvidenceMode::MetalXcrunMetal;
    policy.optimizationToolName = "xcrun metal";
    policy.profileApi = "metal";
    policy.profileName = "metal-native";
    policy.generatorName = "CrossGL Metal backend";
    policy.binaryFormat = "metallib";
    policy.assemblyFormat = "Metal AIR";
    policy.requiredTools = {
        TargetNativePackageToolPolicy{"toolchain", "xcrun metal", "compiler",
                                      "xcrun", "metal", "xcrun-metal"},
        TargetNativePackageToolPolicy{"toolchain", "xcrun metallib", "linker",
                                      "xcrun", "metallib", "xcrun-metallib"}};
    break;
  case TargetKind::Vulkan:
    if (!containsString(requirements.requiredPathArtifactKeys,
                        "backendAssembly")) {
      return policy;
    }
    policy.supported = true;
    policy.binaryKind = "vulkan.spirv-module";
    policy.sourceArtifactKey = "backendAssembly";
    policy.nativeBinaryArtifactKey = "nativeBinary";
    policy.descriptorArtifactKey = "nativeArtifactDescriptor";
    policy.profileArtifactKey = "nativeProfile";
    policy.validationStatus = "validated";
    policy.optimizationEvidenceMode =
        TargetNativePackageDescriptorOptimizationEvidenceMode::VulkanSpirvOpt;
    policy.optimizationToolName = "spirv-opt";
    policy.disassemblyToolName = "spirv-dis";
    policy.disassemblyPolicy = "use-when-available";
    policy.profileApi = "vulkan";
    policy.profileName = "vulkan-prototype";
    policy.vulkanVersion = "1.2";
    policy.spirvVersion = "1.0";
    policy.generatorName = "CrossGL Vulkan prototype backend";
    policy.binaryFormat = "SPIR-V";
    policy.assemblyFormat = "SPIR-V assembly";
    policy.requiredTools = {
        TargetNativePackageToolPolicy{"toolchain", "spirv-as", "assembler",
                                      "spirv-as", "spirv-as", ""},
        TargetNativePackageToolPolicy{"validation", "spirv-val", "validator",
                                      "spirv-val", "spirv-val", ""}};
    break;
  case TargetKind::DirectX:
  case TargetKind::OpenGL:
  case TargetKind::Auto:
    return policy;
  }
  policy.optimizationEvidenceModeName =
      targetNativePackageDescriptorOptimizationEvidenceModeName(
          policy.optimizationEvidenceMode);
  return policy;
}

TargetNativePackageDescriptorPolicy targetNativePackageDescriptorPolicy(
    const TargetLegalizationContractProjection &projection) {
  const TargetKind target = projection.targetProfile.resolvedTarget ==
                                    TargetKind::Auto
                                ? projection.packageArtifactRequirements.target
                                : projection.targetProfile.resolvedTarget;
  if (!targetLegalizationProjectionSupportsPackage(projection) ||
      projection.packageMode != TargetLegalizationPackageMode::Native ||
      projection.supportStatus !=
          TargetLegalizationSupportStatus::NativePackage) {
    TargetNativePackageDescriptorPolicy policy;
    policy.target = target;
    policy.targetName =
        projection.packageArtifactRequirements.targetName.empty()
            ? std::string(targetName(target))
            : projection.packageArtifactRequirements.targetName;
    policy.optimizationEvidenceModeName =
        targetNativePackageDescriptorOptimizationEvidenceModeName(
            policy.optimizationEvidenceMode);
    return policy;
  }
  return targetNativePackageDescriptorPolicy(
      projection.packageArtifactRequirements, target);
}

bool targetLegalizationSucceeded(const TargetLegalizationResult &result) {
  if (!result.packageBuildSupported ||
      result.supportStatus == TargetLegalizationSupportStatus::Unsupported ||
      result.state != TargetLegalizationState::Legalized ||
      result.packageModeKind == TargetLegalizationPackageMode::Unsupported) {
    return false;
  }
  return !targetLegalizationDiagnosticSummary(result).hasErrors;
}

TargetLegalizationCapabilitySummary
targetLegalizationCapabilitySummary(const TargetLegalizationResult &result) {
  TargetLegalizationCapabilitySummary summary;
  summary.requiredCapabilityCount = result.requiredCapabilities.size();
  summary.missingCapabilityCount = result.missingCapabilities.size();
  summary.requiredCapabilityIds.reserve(result.requiredCapabilities.size());
  for (const TargetCapability &capability : result.requiredCapabilities) {
    summary.requiredCapabilityIds.push_back(
        targetLegalizationCapabilityId(capability));
  }
  summary.missingCapabilityIds.reserve(result.missingCapabilities.size());
  for (const TargetCapability &capability : result.missingCapabilities) {
    summary.missingCapabilityIds.push_back(
        targetLegalizationCapabilityId(capability));
  }
  return summary;
}

TargetLegalizationDiagnosticSummary
targetLegalizationDiagnosticSummary(const TargetLegalizationResult &result) {
  return diagnosticSummaryForDiagnostics(result.diagnostics);
}

Diagnostic
targetLegalizationDiagnostic(const TargetLegalizationDiagnostic &diagnostic) {
  Diagnostic projected;
  projected.severity = diagnostic.severity;
  projected.code = diagnostic.code;
  projected.message = diagnostic.message;
  if (diagnostic.location.has_value()) {
    projected.location = *diagnostic.location;
  }
  if (diagnostic.target != TargetKind::Auto) {
    projected.target = targetName(diagnostic.target);
  }
  projected.missingCapabilities.reserve(diagnostic.capabilities.size());
  for (const TargetCapability &capability : diagnostic.capabilities) {
    projected.missingCapabilities.push_back(
        targetLegalizationCapabilityId(capability));
  }
  return projected;
}

std::vector<Diagnostic>
targetLegalizationDiagnostics(const TargetLegalizationContract &contract) {
  std::vector<Diagnostic> diagnostics;
  diagnostics.reserve(contract.diagnostics.size());
  for (const TargetLegalizationDiagnostic &diagnostic :
       contract.diagnostics) {
    diagnostics.push_back(targetLegalizationDiagnostic(diagnostic));
  }
  return diagnostics;
}

std::vector<Diagnostic>
targetLegalizationDiagnostics(const TargetLegalizationResult &result) {
  return targetLegalizationDiagnostics(targetLegalizationContract(result));
}

std::vector<std::string>
targetLegalizationCoreEvidenceIds(const TargetLegalizationContract &contract) {
  std::vector<std::string> evidenceIds;
  if (contract.resolvedTarget == TargetKind::Auto) {
    return evidenceIds;
  }

  evidenceIds.push_back(evidenceId(contract.resolvedTarget, "decision"));
  evidenceIds.push_back(evidenceId(
      contract.resolvedTarget,
      "state." + std::string(targetLegalizationStateName(contract.state))));
  evidenceIds.push_back(
      evidenceId(contract.resolvedTarget,
                 "support." + std::string(targetLegalizationSupportStatusName(
                                  contract.supportStatus))));
  evidenceIds.push_back(evidenceId(
      contract.resolvedTarget,
      "package-mode." + std::string(targetLegalizationPackageModeName(
                            contract.packageMode))));
  evidenceIds.push_back(evidenceId(
      contract.resolvedTarget,
      "package-provenance." +
          std::string(targetLegalizationPackageDecisionProvenanceName(
              contract.packageDecisionProvenance))));
  if (contract.optionalNativeToolMissing) {
    evidenceIds.push_back(
        evidenceId(contract.resolvedTarget, "optional-native-tool.missing"));
  }
  if (!contract.reason.empty()) {
    evidenceIds.push_back(evidenceId(contract.resolvedTarget,
                                     "package-reason." + contract.reason));
  }
  return evidenceIds;
}

std::vector<std::string>
targetLegalizationCoreEvidenceIds(const TargetLegalizationResult &result) {
  return targetLegalizationCoreEvidenceIds(targetLegalizationContract(result));
}

TargetLegalizationContract
targetLegalizationContract(const TargetLegalizationResult &result) {
  const TargetLegalizationCapabilitySummary capabilitySummary =
      targetLegalizationCapabilitySummary(result);

  TargetLegalizationContract contract;
  contract.targetProfile = targetProfileForResult(result);
  contract.requestedTarget = contract.targetProfile.requestedTarget;
  contract.resolvedTarget = contract.targetProfile.resolvedTarget;
  contract.resolvedTargetName = contract.targetProfile.resolvedTargetName;
  contract.nativeImplemented = result.nativeImplemented;
  contract.sourcePackageSupported = result.sourcePackageSupported;
  contract.supportStatus = result.supportStatus;
  contract.supportStatusName =
      targetLegalizationSupportStatusName(result.supportStatus);
  contract.state = result.state;
  contract.stateName = targetLegalizationStateName(result.state);
  contract.packageMode = result.packageModeKind;
  contract.packageModeName =
      targetLegalizationPackageModeName(result.packageModeKind);
  contract.packageDecisionProvenance = result.packageDecisionProvenance;
  contract.packageDecisionProvenanceName =
      targetLegalizationPackageDecisionProvenanceName(
          result.packageDecisionProvenance);
  contract.optionalNativeToolMissing = result.optionalNativeToolMissing;
  contract.optionalNativeToolStatus = result.optionalNativeToolStatus;
  contract.optionalNativeToolStatusName =
      result.optionalNativeToolStatusName.empty()
          ? targetLegalizationOptionalNativeToolStatusName(
                result.optionalNativeToolStatus)
          : result.optionalNativeToolStatusName;
  contract.reason = result.packageDecisionReason;
  contract.packageRankScore = result.packageRankScore;
  contract.requiredCapabilityCount = capabilitySummary.requiredCapabilityCount;
  contract.missingCapabilityCount = capabilitySummary.missingCapabilityCount;
  contract.requiredCapabilityIds = capabilitySummary.requiredCapabilityIds;
  contract.missingCapabilityIds = capabilitySummary.missingCapabilityIds;
  contract.diagnosticSummary = targetLegalizationDiagnosticSummary(result);
  contract.diagnostics = result.diagnostics;
  contract.abiFacts = result.abiFacts;
  contract.resourceBindings = result.resourceBindings;
  contract.toolRequirements = result.toolRequirements;
  contract.packageArtifactRequirements = result.packageArtifactRequirements;
  contract.sourcePackageDescriptorPolicy = result.sourcePackageDescriptorPolicy;
  contract.nativePackageDescriptorPolicy = result.nativePackageDescriptorPolicy;
  contract.rewrites = result.rewrites;
  contract.evidenceIds = result.evidenceIds;
  contract.supportsPackage = targetLegalizationSucceeded(result);
  return contract;
}

const std::vector<TargetLegalizationConsumerAuditReference> &
targetLegalizationConsumerAuditReferences() {
  static const std::vector<TargetLegalizationConsumerAuditReference>
      references = {
          {"explain-targets",
           "src/Backend/TargetLegalization.cpp",
           "targetLegalizationConsumerAuditReferences"},
          {"Language feature report",
           "src/Backend/TargetLegalization.cpp",
           "targetLegalizationConsumerAuditReferences"},
          {"doctor --json",
           "src/Backend/TargetLegalization.cpp",
           "targetLegalizationConsumerAuditReferences"},
          {"Package build",
           "src/Backend/TargetLegalization.cpp",
           "targetLegalizationConsumerAuditReferences"},
          {"Package release and publication",
           "src/Backend/TargetLegalization.cpp",
           "targetLegalizationConsumerAuditReferences"},
          {"Debug metadata",
           "src/Backend/TargetLegalization.cpp",
           "targetLegalizationConsumerAuditReferences"},
          {"Reflection and target feature records",
           "src/Backend/TargetLegalization.cpp",
           "targetLegalizationConsumerAuditReferences"},
          {"Package verification",
           "src/Backend/TargetLegalization.cpp",
           "targetLegalizationConsumerAuditReferences"},
          {"Package inspect",
           "src/Backend/TargetLegalization.cpp",
           "targetLegalizationConsumerAuditReferences"},
      };
  return references;
}

TargetLegalizationContractProjection targetLegalizationContractProjection(
    const TargetLegalizationContract &contract) {
  TargetLegalizationContractProjection projection;
  projection.version = contract.version;
  projection.targetProfile = contract.targetProfile;
  projection.nativeImplemented = contract.nativeImplemented;
  projection.sourcePackageSupported = contract.sourcePackageSupported;
  projection.supportsPackage = targetLegalizationSupportsPackage(contract);
  projection.supportStatus = contract.supportStatus;
  projection.supportStatusName = contract.supportStatusName;
  projection.state = contract.state;
  projection.stateName = contract.stateName;
  projection.packageMode = contract.packageMode;
  projection.packageModeName = contract.packageModeName;
  projection.packageDecisionProvenance = contract.packageDecisionProvenance;
  projection.packageDecisionProvenanceName =
      contract.packageDecisionProvenanceName;
  projection.optionalNativeToolMissing = contract.optionalNativeToolMissing;
  projection.optionalNativeToolStatus =
      optionalNativeToolStatusForContract(contract);
  projection.optionalNativeToolStatusName =
      targetLegalizationOptionalNativeToolStatusName(
          projection.optionalNativeToolStatus);
  projection.reason = contract.reason;
  projection.consumerDecisionReasonCodes =
      consumerDecisionReasonCodesForContract(contract,
                                             projection.supportsPackage);
  projection.packageRankScore = contract.packageRankScore;
  projection.requiredCapabilityCount = contract.requiredCapabilityCount;
  projection.missingCapabilityCount = contract.missingCapabilityCount;
  projection.requiredCapabilityIds = contract.requiredCapabilityIds;
  projection.missingCapabilityIds = contract.missingCapabilityIds;
  projection.diagnosticSummary = contract.diagnosticSummary;
  projection.diagnosticEvidenceIds = contract.diagnosticSummary.evidenceIds;
  projection.requiredToolCount = contract.toolRequirements.requiredToolCount;
  projection.missingToolCount = contract.toolRequirements.missingToolCount;
  projection.requiredToolIds = contract.toolRequirements.requiredToolIds;
  projection.missingToolIds = contract.toolRequirements.missingToolIds;
  projection.requiredToolRecords = contract.toolRequirements.requiredRecords;
  projection.missingToolRecords = contract.toolRequirements.missingRecords;
  projection.toolRequirementEvidenceIds = contract.toolRequirements.evidenceIds;
  projection.abiState = contract.abiFacts.state;
  projection.abiStateName =
      targetLegalizationABIStateName(contract.abiFacts.state);
  projection.abiComplete = contract.abiFacts.complete;
  projection.abiRequiredRecordCount = contract.abiFacts.requiredRecords.size();
  projection.abiMissingRecordCount = contract.abiFacts.missingRecords.size();
  projection.requiredABIFacts = contract.abiFacts.requiredFacts;
  projection.missingABIFacts = contract.abiFacts.missingFacts;
  projection.abiEvidenceIds = contract.abiFacts.evidenceIds;
  projection.resourceBindingComplete = contract.resourceBindings.complete;
  projection.resourceBindingRequiredRecordCount =
      contract.resourceBindings.requiredRecordCount;
  projection.resourceBindingRecordCount =
      contract.resourceBindings.records.size();
  projection.resourceBindingEvidenceIds = contract.resourceBindings.evidenceIds;
  projection.packageArtifactRequirements = contract.packageArtifactRequirements;
  projection.packageArtifactRequirementEvidenceIds =
      contract.packageArtifactRequirements.evidenceIds;
  projection.rewriteState = contract.rewrites.state;
  projection.rewriteStateName =
      targetLegalizationRewriteStateName(contract.rewrites.state);
  projection.rewriteComplete = contract.rewrites.complete;
  projection.rewriteRecordCount = contract.rewrites.records.size();
  projection.rewriteEvidenceIds = contract.rewrites.evidenceIds;
  projection.coreEvidenceIds = targetLegalizationCoreEvidenceIds(contract);
  projection.sourcePackageDescriptorPolicy =
      targetSourcePackageDescriptorPolicy(projection);
  projection.nativePackageDescriptorPolicy =
      targetNativePackageDescriptorPolicy(projection);
  projection.evidenceIds = contract.evidenceIds;
  projection.consumerAuditReferences =
      targetLegalizationConsumerAuditReferences();
  return projection;
}

TargetLegalizationContractProjection
targetLegalizationContractProjection(const TargetLegalizationResult &result) {
  return targetLegalizationContractProjection(
      targetLegalizationContract(result));
}

TargetLegalizationAdmissionDecision targetLegalizationAdmissionDecision(
    const TargetLegalizationContract &contract) {
  TargetLegalizationAdmissionDecision decision;
  decision.contract = contract;
  decision.projection = targetLegalizationContractProjection(decision.contract);
  decision.admitted =
      targetLegalizationProjectionSupportsPackage(decision.projection);
  decision.coreEvidenceIds = decision.projection.coreEvidenceIds;
  decision.diagnosticEvidenceIds = decision.projection.diagnosticEvidenceIds;
  decision.evidenceIds = decision.projection.evidenceIds;
  return decision;
}

TargetLegalizationAdmissionDecision targetLegalizationAdmissionDecision(
    const TargetLegalizationResult &result) {
  return targetLegalizationAdmissionDecision(targetLegalizationContract(result));
}

std::string targetLegalizationContractProjectionJson(
    const TargetLegalizationContractProjection &projection) {
  std::ostringstream out;
  out << "{";
  appendJsonSizeField(out, "version", projection.version);
  out << ",\"targetProfile\":";
  appendTargetProfileJson(out, projection.targetProfile);
  out << ",";
  appendJsonBoolField(out, "nativeImplemented", projection.nativeImplemented);
  out << ",";
  appendJsonBoolField(out, "sourcePackageSupported",
                      projection.sourcePackageSupported);
  out << ",";
  appendJsonBoolField(out, "supportsPackage", projection.supportsPackage);
  out << ",";
  appendJsonStringField(out, "supportStatus",
                        projectionSupportStatusName(projection));
  out << ",";
  appendJsonStringField(out, "state", projectionStateName(projection));
  out << ",";
  appendJsonStringField(out, "packageMode",
                        projectionPackageModeName(projection));
  out << ",";
  appendJsonStringField(out, "packageDecisionProvenance",
                        projectionPackageDecisionProvenanceName(projection));
  out << ",";
  appendJsonBoolField(out, "optionalNativeToolMissing",
                      projection.optionalNativeToolMissing);
  out << ",";
  appendJsonStringField(out, "optionalNativeToolStatus",
                        projectionOptionalNativeToolStatusName(projection));
  out << ",";
  appendJsonStringField(out, "reason", projection.reason);
  out << ",";
  appendJsonStringArrayField(out, "consumerDecisionReasonCodes",
                             projection.consumerDecisionReasonCodes);
  out << ",";
  appendJsonSizeField(out, "packageRankScore", projection.packageRankScore);
  out << ",";
  appendJsonSizeField(out, "requiredCapabilityCount",
                      projection.requiredCapabilityCount);
  out << ",";
  appendJsonSizeField(out, "missingCapabilityCount",
                      projection.missingCapabilityCount);
  out << ",";
  appendJsonStringArrayField(out, "requiredCapabilityIds",
                             projection.requiredCapabilityIds);
  out << ",";
  appendJsonStringArrayField(out, "missingCapabilityIds",
                             projection.missingCapabilityIds);
  out << ",\"diagnosticSummary\":";
  appendDiagnosticSummaryJson(out, projection.diagnosticSummary);
  out << ",";
  appendJsonStringArrayField(out, "diagnosticEvidenceIds",
                             projection.diagnosticEvidenceIds);
  out << ",";
  appendJsonSizeField(out, "requiredToolCount", projection.requiredToolCount);
  out << ",";
  appendJsonSizeField(out, "missingToolCount", projection.missingToolCount);
  out << ",";
  appendJsonStringArrayField(out, "requiredToolIds",
                             projection.requiredToolIds);
  out << ",";
  appendJsonStringArrayField(out, "missingToolIds", projection.missingToolIds);
  out << ",";
  appendJsonString(out, "requiredToolRecords");
  out << ":";
  out << "[";
  for (std::size_t index = 0; index < projection.requiredToolRecords.size();
       ++index) {
    if (index != 0) {
      out << ",";
    }
    appendV0ToolRequirementRecordJson(out, projection.requiredToolRecords[index],
                                      "required");
  }
  out << "]";
  out << ",";
  appendJsonString(out, "missingToolRecords");
  out << ":";
  out << "[";
  for (std::size_t index = 0; index < projection.missingToolRecords.size();
       ++index) {
    if (index != 0) {
      out << ",";
    }
    appendV0ToolRequirementRecordJson(out, projection.missingToolRecords[index],
                                      "missing");
  }
  out << "]";
  out << ",";
  appendJsonStringArrayField(out, "toolRequirementEvidenceIds",
                             projection.toolRequirementEvidenceIds);
  out << ",";
  appendJsonStringField(out, "abiState", projectionABIStateName(projection));
  out << ",";
  appendJsonBoolField(out, "abiComplete", projection.abiComplete);
  out << ",";
  appendJsonSizeField(out, "abiRequiredRecordCount",
                      projection.abiRequiredRecordCount);
  out << ",";
  appendJsonSizeField(out, "abiMissingRecordCount",
                      projection.abiMissingRecordCount);
  out << ",";
  appendJsonStringArrayField(out, "requiredABIFacts",
                             projection.requiredABIFacts);
  out << ",";
  appendJsonStringArrayField(out, "missingABIFacts",
                             projection.missingABIFacts);
  out << ",";
  appendJsonStringArrayField(out, "abiEvidenceIds", projection.abiEvidenceIds);
  out << ",";
  appendJsonBoolField(out, "resourceBindingComplete",
                      projection.resourceBindingComplete);
  out << ",";
  appendJsonSizeField(out, "resourceBindingRequiredRecordCount",
                      projection.resourceBindingRequiredRecordCount);
  out << ",";
  appendJsonSizeField(out, "resourceBindingRecordCount",
                      projection.resourceBindingRecordCount);
  out << ",";
  appendJsonStringArrayField(out, "resourceBindingEvidenceIds",
                             projection.resourceBindingEvidenceIds);
  out << ",\"packageArtifactRequirements\":";
  appendPackageArtifactRequirementsJson(out,
                                        projection.packageArtifactRequirements);
  out << ",";
  appendJsonStringArrayField(out, "packageArtifactRequirementEvidenceIds",
                             projection.packageArtifactRequirementEvidenceIds);
  out << ",\"sourcePackageDescriptorPolicy\":";
  appendSourcePackageDescriptorPolicyJson(
      out, projection.sourcePackageDescriptorPolicy);
  out << ",";
  appendJsonStringField(out, "rewriteState",
                        projectionRewriteStateName(projection));
  out << ",";
  appendJsonBoolField(out, "rewriteComplete", projection.rewriteComplete);
  out << ",";
  appendJsonSizeField(out, "rewriteRecordCount", projection.rewriteRecordCount);
  out << ",";
  appendJsonStringArrayField(out, "rewriteEvidenceIds",
                             projection.rewriteEvidenceIds);
  out << ",";
  appendJsonStringArrayField(out, "coreEvidenceIds",
                             projection.coreEvidenceIds);
  out << ",";
  appendJsonStringArrayField(out, "evidenceIds", projection.evidenceIds);
  out << ",";
  appendJsonSizeField(out, "consumerAuditReferenceCount",
                      projection.consumerAuditReferences.size());
  out << ",\"consumerAuditReferences\":";
  appendConsumerAuditReferencesJson(out, projection.consumerAuditReferences);
  out << "}";
  return out.str();
}

std::string targetLegalizationContractProjectionJson(
    const TargetLegalizationContract &contract) {
  return targetLegalizationContractProjectionJson(
      targetLegalizationContractProjection(contract));
}

std::string targetLegalizationContractProjectionJson(
    const TargetLegalizationResult &result) {
  return targetLegalizationContractProjectionJson(
      targetLegalizationContractProjection(result));
}

std::string
targetLegalizationResultV0Json(const TargetLegalizationContract &contract) {
  const bool moduleSupported = targetLegalizationSupportsPackage(contract);
  const std::string target =
      targetProfileTargetName(contract.resolvedTarget,
                              contract.resolvedTargetName);
  const std::string packageMode =
      targetLegalizationPackageModeName(contract.packageMode);
  std::vector<TargetLegalizationDiagnostic> diagnostics = contract.diagnostics;
  std::sort(diagnostics.begin(), diagnostics.end(),
            [](const TargetLegalizationDiagnostic &lhs,
               const TargetLegalizationDiagnostic &rhs) {
              return std::tie(lhs.code, lhs.evidenceId, lhs.message) <
                     std::tie(rhs.code, rhs.evidenceId, rhs.message);
            });

  std::ostringstream out;
  out << "{";
  appendJsonStringField(out, "contract",
                        "crossgl.target-legalization-result.v0");
  out << ",";
  appendJsonSizeField(out, "schemaVersion", 0);
  out << ",\"policy\":{";
  appendJsonStringField(out, "mode", "report-only");
  out << ",";
  appendJsonStringField(out, "decisionAuthority",
                        "current-compiler-behavior");
  out << ",";
  appendJsonStringField(out, "consumerMigration", "pending");
  out << ",";
  appendJsonStringField(out, "productionBehavior", "unchanged");
  out << "},\"result\":{";
  appendJsonStringField(out, "target", target);
  out << ",\"targetProfile\":{";
  appendJsonStringField(out, "target", target);
  out << ",";
  appendJsonStringField(out, "profile",
                        target + ".v0." + std::string(packageMode));
  out << ",";
  appendJsonStringField(out, "packageMode", packageMode);
  out << "},";
  appendJsonStringField(out, "packageMode", packageMode);
  out << ",";
  appendJsonStringField(
      out, "packageDecisionProvenance",
      targetLegalizationPackageDecisionProvenanceName(
          contract.packageDecisionProvenance));
  out << ",";
  appendJsonStringField(out, "supportStatus",
                        targetLegalizationSupportStatusName(
                            contract.supportStatus));
  out << ",";
  appendJsonBoolField(out, "moduleSupported", moduleSupported);
  out << ",";
  appendJsonStringArrayField(out, "requiredCapabilities",
                             v0RequiredCapabilityIds(contract));
  out << ",";
  appendJsonStringArrayField(out, "missingCapabilities",
                             v0MissingCapabilityIds(contract));
  out << ",\"toolRequirements\":";
  appendV0ToolRequirementsJson(out, contract.toolRequirements,
                               contract.optionalNativeToolMissing,
                               optionalNativeToolStatusForContract(contract),
                               v0ToolRequirementEvidenceIds(contract));
  out << ",\"diagnostics\":[";
  for (std::size_t index = 0; index < diagnostics.size(); ++index) {
    if (index != 0) {
      out << ",";
    }
    appendV0DiagnosticJson(out, diagnostics[index]);
  }
  out << "],\"rewrites\":";
  appendV0RewritesJson(out, contract.rewrites);
  out << ",\"abiFacts\":";
  appendV0ABIFactsJson(out, contract);
  out << ",";
  appendJsonStringArrayField(out, "resourceBindingEvidenceIds",
                             v0ResourceBindingEvidenceIds(contract));
  out << ",";
  appendJsonStringArrayField(out, "evidenceIds",
                             v0TopLevelEvidenceIds(contract));
  out << "}}";
  return out.str();
}

std::string
targetLegalizationResultV0Json(const TargetLegalizationResult &result) {
  return targetLegalizationResultV0Json(targetLegalizationContract(result));
}

std::vector<std::string> targetLegalizationContractInvariantDiagnostics(
    const TargetLegalizationContract &contract) {
  std::vector<std::string> diagnostics;

  if (contract.version != 0) {
    diagnostics.push_back("contract version mismatch");
  }
  if (contract.resolvedTarget != TargetKind::Auto &&
      contract.resolvedTargetName != targetName(contract.resolvedTarget)) {
    diagnostics.push_back("resolved target name mismatch");
  }
  const TargetLegalizationTargetProfile &targetProfile = contract.targetProfile;
  if (targetProfile.requestedTarget != contract.requestedTarget) {
    diagnostics.push_back("target profile requested target mismatch");
  }
  if (targetProfile.resolvedTarget != contract.resolvedTarget) {
    diagnostics.push_back("target profile resolved target mismatch");
  }
  if (targetProfile.resolvedTargetName != contract.resolvedTargetName) {
    diagnostics.push_back("target profile resolved target name mismatch");
  }
  if (targetProfile.requestedTargetName !=
      targetName(targetProfile.requestedTarget)) {
    diagnostics.push_back("target profile requested target name mismatch");
  }
  if (targetProfile.preferredTargetName !=
      targetName(targetProfile.preferredTarget)) {
    diagnostics.push_back("target profile preferred target name mismatch");
  }
  if (targetProfile.resolvedTarget != TargetKind::Auto &&
      targetProfile.resolvedTargetName !=
          targetName(targetProfile.resolvedTarget)) {
    diagnostics.push_back("target profile resolved target name mismatch");
  }
  if (targetProfile.selectedTargetName !=
      targetName(targetProfile.selectedTarget)) {
    diagnostics.push_back("target profile selected target name mismatch");
  }
  if (targetProfile.autoRequested !=
      (targetProfile.requestedTarget == TargetKind::Auto)) {
    diagnostics.push_back("target profile autoRequested mismatch");
  }
  if (targetProfile.selectedTargetBuildable &&
      targetProfile.selectedTarget == TargetKind::Auto) {
    diagnostics.push_back("target profile buildable selection is auto");
  }
  if (targetProfile.selectedTargetBuildable &&
      contract.packageMode == TargetLegalizationPackageMode::Unsupported &&
      contract.resolvedTarget == targetProfile.selectedTarget) {
    diagnostics.push_back(
        "target profile buildable selection conflicts with package mode");
  }
  if (contract.supportStatusName !=
      targetLegalizationSupportStatusName(contract.supportStatus)) {
    diagnostics.push_back("supportStatusName mismatch");
  }
  if (contract.stateName != targetLegalizationStateName(contract.state)) {
    diagnostics.push_back("stateName mismatch");
  }
  if (contract.packageModeName !=
      targetLegalizationPackageModeName(contract.packageMode)) {
    diagnostics.push_back("packageModeName mismatch");
  }
  if (contract.packageDecisionProvenanceName !=
      targetLegalizationPackageDecisionProvenanceName(
          contract.packageDecisionProvenance)) {
    diagnostics.push_back("packageDecisionProvenanceName mismatch");
  }
  if (contract.optionalNativeToolStatusName !=
      targetLegalizationOptionalNativeToolStatusName(
          contract.optionalNativeToolStatus)) {
    diagnostics.push_back("optionalNativeToolStatusName mismatch");
  }
  if (contract.supportStatus != expectedSupportStatusForContract(contract)) {
    diagnostics.push_back("supportStatus mismatch");
  }
  const TargetLegalizationPackageDecisionProvenance expectedProvenance =
      packageDecisionProvenanceForContract(contract);
  if (contract.packageDecisionProvenance != expectedProvenance) {
    diagnostics.push_back("packageDecisionProvenance mismatch");
  }
  if (contract.optionalNativeToolMissing !=
      optionalNativeToolMissingForContract(contract)) {
    diagnostics.push_back("optionalNativeToolMissing mismatch");
  }
  if (contract.optionalNativeToolStatus !=
      optionalNativeToolStatusForContract(contract)) {
    diagnostics.push_back("optionalNativeToolStatus mismatch");
  }

  const bool normalizedSupportsPackage =
      contract.supportStatus != TargetLegalizationSupportStatus::Unsupported &&
      contract.state == TargetLegalizationState::Legalized &&
      contract.packageMode != TargetLegalizationPackageMode::Unsupported &&
      !contract.diagnosticSummary.hasErrors;
  if (contract.supportsPackage != normalizedSupportsPackage) {
    diagnostics.push_back("supportsPackage mismatch");
  }
  if (contract.requiredCapabilityCount !=
      contract.requiredCapabilityIds.size()) {
    diagnostics.push_back("requiredCapabilityCount mismatch");
  }
  if (contract.missingCapabilityCount != contract.missingCapabilityIds.size()) {
    diagnostics.push_back("missingCapabilityCount mismatch");
  }
  std::vector<std::string> seenTopLevelEvidenceIds;
  for (const std::string &evidenceId : contract.evidenceIds) {
    if (evidenceId.empty()) {
      diagnostics.push_back("contract evidence id is empty");
    } else if (containsString(seenTopLevelEvidenceIds, evidenceId)) {
      diagnostics.push_back("contract evidence id is duplicated: " +
                            evidenceId);
    }
    seenTopLevelEvidenceIds.push_back(evidenceId);
  }
  std::vector<std::string> seenNestedEvidenceIds;
  const std::vector<std::string> expectedCoreEvidenceIds =
      targetLegalizationCoreEvidenceIds(contract);
  if (contract.evidenceIds.size() < expectedCoreEvidenceIds.size()) {
    diagnostics.push_back("contract core evidence prefix incomplete");
  } else {
    for (std::size_t index = 0; index < expectedCoreEvidenceIds.size();
         ++index) {
      if (contract.evidenceIds[index] != expectedCoreEvidenceIds[index]) {
        diagnostics.push_back("contract core evidence prefix mismatch at "
                              "index " +
                              std::to_string(index));
        break;
      }
    }
  }

  const TargetLegalizationDiagnosticSummary expectedDiagnosticSummary =
      diagnosticSummaryForDiagnostics(contract.diagnostics);
  if (!sameDiagnosticSummary(contract.diagnosticSummary,
                             expectedDiagnosticSummary)) {
    diagnostics.push_back("diagnosticSummary mismatch");
  }
  for (const std::string &evidenceId : expectedDiagnosticSummary.evidenceIds) {
    if (evidenceId.empty()) {
      diagnostics.push_back("diagnostic evidence id is empty");
    } else if (!containsString(contract.evidenceIds, evidenceId)) {
      diagnostics.push_back(
          "diagnostic evidence missing from contract evidenceIds: " +
          evidenceId);
    }
  }
  appendEvidenceIdShapeDiagnostics(diagnostics,
                                   expectedDiagnosticSummary.evidenceIds,
                                   contract.resolvedTarget, "diagnostic",
                                   seenNestedEvidenceIds);

  const TargetLegalizationABIFacts &abiFacts = contract.abiFacts;
  if (abiFacts.target != TargetKind::Auto &&
      abiFacts.target != contract.resolvedTarget) {
    diagnostics.push_back("ABI target mismatch");
  }
  const bool defaultABIPlaceholder =
      abiFacts.target == TargetKind::Auto &&
      abiFacts.state == TargetLegalizationABIState::Empty &&
      abiFacts.requiredRecords.empty() && abiFacts.missingRecords.empty() &&
      abiFacts.evidenceIds.empty() && abiFacts.requiredFacts.empty() &&
      abiFacts.missingFacts.empty();
  const bool abiFactsHaveShape =
      !abiFacts.requiredRecords.empty() || !abiFacts.missingRecords.empty() ||
      !abiFacts.requiredFacts.empty() || !abiFacts.missingFacts.empty();
  if (abiFacts.state == TargetLegalizationABIState::Empty &&
      abiFactsHaveShape) {
    diagnostics.push_back("ABI empty state carries facts");
  }
  if (abiFacts.state == TargetLegalizationABIState::Present &&
      !abiFactsHaveShape) {
    diagnostics.push_back("ABI present state has no facts");
  }
  if (!defaultABIPlaceholder) {
    const std::string expectedABIStateEvidence = evidenceId(
        abiFacts.target,
        "abi." + std::string(targetLegalizationABIStateName(abiFacts.state)));
    if (!containsString(abiFacts.evidenceIds, expectedABIStateEvidence)) {
      diagnostics.push_back(
          "ABI state evidence missing from ABI evidenceIds: " +
          expectedABIStateEvidence);
    }
  }
  const bool expectedABIComplete =
      defaultABIPlaceholder
          ? false
          : abiFacts.state != TargetLegalizationABIState::Unsupported;
  if (abiFacts.complete != expectedABIComplete) {
    diagnostics.push_back("ABI complete mismatch");
  }
  appendABIRecordInvariantDiagnostics(
      diagnostics, abiFacts.requiredRecords, abiFacts.requiredFacts,
      abiFacts.evidenceIds, contract.resolvedTarget, "required");
  appendABIRecordInvariantDiagnostics(
      diagnostics, abiFacts.missingRecords, abiFacts.missingFacts,
      abiFacts.evidenceIds, contract.resolvedTarget, "missing");
  appendABIFactCapabilityInvariantDiagnostics(
      diagnostics, abiFacts.requiredFacts, contract.requiredCapabilityIds,
      "required");
  appendABIFactCapabilityInvariantDiagnostics(
      diagnostics, abiFacts.missingFacts, contract.missingCapabilityIds,
      "missing");
  for (const std::string &evidenceId : abiFacts.evidenceIds) {
    if (evidenceId.empty()) {
      diagnostics.push_back("ABI evidence id is empty");
    } else if (!containsString(contract.evidenceIds, evidenceId)) {
      diagnostics.push_back("ABI evidence missing from contract evidenceIds: " +
                            evidenceId);
    }
  }
  appendEvidenceIdShapeDiagnostics(diagnostics, abiFacts.evidenceIds,
                                   contract.resolvedTarget, "ABI",
                                   seenNestedEvidenceIds);

  const TargetLegalizationResourceBindingFacts &resourceBindings =
      contract.resourceBindings;
  if (resourceBindings.target != TargetKind::Auto &&
      resourceBindings.target != contract.resolvedTarget) {
    diagnostics.push_back("resource binding target mismatch");
  }
  const bool defaultResourceBindingPlaceholder =
      resourceBindings.target == TargetKind::Auto &&
      !resourceBindings.complete && resourceBindings.requiredRecordCount == 0 &&
      resourceBindings.records.empty() &&
      resourceBindings.evidenceIds.empty();
  if (!defaultResourceBindingPlaceholder) {
    const std::string expectedResourceBindingEvidence =
        evidenceId(resourceBindings.target, resourceBindings.records.empty()
                                                ? "resource-bindings.empty"
                                                : "resource-bindings.present");
    if (!containsString(resourceBindings.evidenceIds,
                        expectedResourceBindingEvidence)) {
      diagnostics.push_back(
          "resource binding summary evidence missing from resource binding "
          "evidenceIds: " +
          expectedResourceBindingEvidence);
    }
  }
  if (!defaultResourceBindingPlaceholder && !resourceBindings.complete) {
    diagnostics.push_back("resource binding facts incomplete");
  }
  if (!defaultResourceBindingPlaceholder &&
      resourceBindings.records.size() !=
          resourceBindings.requiredRecordCount) {
    diagnostics.push_back("resource binding required record count mismatch");
  }
  if (!defaultResourceBindingPlaceholder &&
      resourceBindings.complete != (resourceBindings.records.size() ==
                                    resourceBindings.requiredRecordCount)) {
    diagnostics.push_back("resource binding complete mismatch");
  }
  for (std::size_t index = 1; index < resourceBindings.records.size();
       ++index) {
    if (resourceBindingRecordLess(resourceBindings.records[index],
                                  resourceBindings.records[index - 1])) {
      diagnostics.push_back("resource binding records are not sorted");
      break;
    }
  }
  if (!defaultResourceBindingPlaceholder) {
    const std::size_t expectedEvidenceCount =
        resourceBindings.records.size() + 1;
    if (resourceBindings.evidenceIds.size() != expectedEvidenceCount) {
      diagnostics.push_back("resource binding evidence count mismatch");
    } else {
      for (std::size_t index = 0; index < resourceBindings.records.size();
           ++index) {
        const std::string &expectedEvidence =
            resourceBindings.records[index].evidenceId;
        const std::string &actualEvidence =
            resourceBindings.evidenceIds[index + 1];
        if (actualEvidence != expectedEvidence) {
          diagnostics.push_back("resource binding evidence order mismatch");
          break;
        }
      }
    }
  }
  appendResourceBindingRecordInvariantDiagnostics(diagnostics, resourceBindings,
                                                  contract.resolvedTarget);
  for (const std::string &evidenceId : resourceBindings.evidenceIds) {
    if (evidenceId.empty()) {
      diagnostics.push_back("resource binding evidence id is empty");
    } else if (!containsString(contract.evidenceIds, evidenceId)) {
      diagnostics.push_back(
          "resource binding evidence missing from contract evidenceIds: " +
          evidenceId);
    }
  }
  appendEvidenceIdShapeDiagnostics(diagnostics, resourceBindings.evidenceIds,
                                   contract.resolvedTarget, "resource binding",
                                   seenNestedEvidenceIds);

  const TargetPackageArtifactRequirements &packageArtifacts =
      contract.packageArtifactRequirements;
  const bool defaultPackageArtifactPlaceholder =
      packageArtifacts.target == TargetKind::Auto &&
      packageArtifacts.targetName.empty() &&
      packageArtifacts.packageMode ==
          TargetLegalizationPackageMode::Unsupported &&
      packageArtifacts.packageModeName.empty() &&
      packageArtifacts.requiredPathArtifactKeys.empty() &&
      !packageArtifacts.requiresNativeBinaryStatus &&
      !packageArtifacts.allowsPlannedNativeBinary &&
      !packageArtifacts.allowsPlannedNativeSourceEvidence &&
      packageArtifacts.evidenceIds.empty();
  if (!defaultPackageArtifactPlaceholder) {
    if (packageArtifacts.target != contract.resolvedTarget) {
      diagnostics.push_back("package artifact requirements target mismatch");
    }
    if (packageArtifacts.targetName != targetName(packageArtifacts.target)) {
      diagnostics.push_back(
          "package artifact requirements targetName mismatch");
    }
    if (packageArtifacts.packageMode != contract.packageMode) {
      diagnostics.push_back(
          "package artifact requirements packageMode mismatch");
    }
    if (packageArtifacts.packageModeName !=
        targetLegalizationPackageModeName(packageArtifacts.packageMode)) {
      diagnostics.push_back(
          "package artifact requirements packageModeName mismatch");
    }

    const std::vector<std::string> expectedArtifactKeys =
        expectedPackageArtifactKeys(packageArtifacts.target,
                                    packageArtifacts.packageMode);
    if (!sameStringVector(packageArtifacts.requiredPathArtifactKeys,
                          expectedArtifactKeys)) {
      diagnostics.push_back(
          "package artifact requirements requiredPathArtifactKeys mismatch");
    }
    const bool expectedNativeStatus =
        expectedPackageArtifactRequiresNativeBinaryStatus(
            packageArtifacts.target, packageArtifacts.packageMode);
    if (packageArtifacts.requiresNativeBinaryStatus != expectedNativeStatus) {
      diagnostics.push_back(
          "package artifact requirements native binary status mismatch");
    }
    if (packageArtifacts.allowsPlannedNativeBinary != expectedNativeStatus) {
      diagnostics.push_back(
          "package artifact requirements planned native binary mismatch");
    }
    if (packageArtifacts.allowsPlannedNativeSourceEvidence !=
        expectedNativeStatus) {
      diagnostics.push_back(
          "package artifact requirements planned native source evidence "
          "mismatch");
    }
    const std::vector<std::string> expectedArtifactEvidenceIds =
        expectedPackageArtifactEvidenceIds(packageArtifacts);
    if (!sameStringVector(packageArtifacts.evidenceIds,
                          expectedArtifactEvidenceIds)) {
      diagnostics.push_back(
          "package artifact requirements evidenceIds mismatch");
    }
  }
  for (const std::string &evidenceId : packageArtifacts.evidenceIds) {
    if (evidenceId.empty()) {
      diagnostics.push_back(
          "package artifact requirements evidence id is empty");
    } else if (!containsString(contract.evidenceIds, evidenceId)) {
      diagnostics.push_back(
          "package artifact requirements evidence missing from contract "
          "evidenceIds: " +
          evidenceId);
    }
  }
  appendEvidenceIdShapeDiagnostics(diagnostics, packageArtifacts.evidenceIds,
                                   contract.resolvedTarget,
                                   "package artifact requirements",
                                   seenNestedEvidenceIds);

  const TargetLegalizationToolRequirementSummary &toolRequirements =
      contract.toolRequirements;
  if (toolRequirements.target != TargetKind::Auto &&
      toolRequirements.target != contract.resolvedTarget) {
    diagnostics.push_back("tool requirement target mismatch");
  }
  if (toolRequirements.requiredToolCount !=
      toolRequirements.requiredRecords.size()) {
    diagnostics.push_back("requiredToolCount mismatch");
  }
  if (toolRequirements.requiredToolCount !=
      toolRequirements.requiredToolIds.size()) {
    diagnostics.push_back("requiredToolIds count mismatch");
  }
  if (toolRequirements.missingToolCount !=
      toolRequirements.missingRecords.size()) {
    diagnostics.push_back("missingToolCount mismatch");
  }
  if (toolRequirements.missingToolCount !=
      toolRequirements.missingToolIds.size()) {
    diagnostics.push_back("missingToolIds count mismatch");
  }
  appendToolRequirementRecordInvariantDiagnostics(
      diagnostics, toolRequirements.requiredRecords,
      toolRequirements.requiredToolIds, toolRequirements.evidenceIds,
      contract.resolvedTarget, "required");
  appendToolRequirementRecordInvariantDiagnostics(
      diagnostics, toolRequirements.missingRecords,
      toolRequirements.missingToolIds, toolRequirements.evidenceIds,
      contract.resolvedTarget, "missing");
  appendToolRequirementCapabilityInvariantDiagnostics(
      diagnostics, toolRequirements.requiredToolIds,
      contract.requiredCapabilityIds, contract.resolvedTarget,
      contract.packageMode, "required");
  appendToolRequirementCapabilityInvariantDiagnostics(
      diagnostics, toolRequirements.missingToolIds,
      contract.missingCapabilityIds, contract.resolvedTarget,
      contract.packageMode, "missing");
  for (const std::string &evidenceId : toolRequirements.evidenceIds) {
    if (evidenceId.empty()) {
      diagnostics.push_back("tool requirement evidence id is empty");
    } else if (!containsString(contract.evidenceIds, evidenceId)) {
      diagnostics.push_back(
          "tool requirement evidence missing from contract evidenceIds: " +
          evidenceId);
    }
  }
  appendEvidenceIdShapeDiagnostics(diagnostics, toolRequirements.evidenceIds,
                                   contract.resolvedTarget, "tool requirement",
                                   seenNestedEvidenceIds);

  const TargetLegalizationRewriteCollection &rewrites = contract.rewrites;
  if (rewrites.target != TargetKind::Auto &&
      rewrites.target != contract.resolvedTarget) {
    diagnostics.push_back("rewrite target mismatch");
  }
  const bool expectedRewriteComplete =
      rewrites.state != TargetLegalizationRewriteState::Empty &&
      rewrites.state != TargetLegalizationRewriteState::Unsupported;
  if (rewrites.complete != expectedRewriteComplete) {
    diagnostics.push_back("rewrite complete mismatch");
  }
  for (const TargetLegalizationRewriteRecord &record : rewrites.records) {
    if (record.target != rewrites.target) {
      diagnostics.push_back("rewrite record target mismatch");
    }
    if (record.state != rewrites.state) {
      diagnostics.push_back("rewrite record state mismatch");
    }
    if (record.evidenceId.empty()) {
      diagnostics.push_back("rewrite record evidence id is empty");
    } else if (!containsString(rewrites.evidenceIds, record.evidenceId)) {
      diagnostics.push_back(
          "rewrite record evidence missing from rewrite evidenceIds: " +
          record.evidenceId);
    }
  }
  for (const std::string &evidenceId : rewrites.evidenceIds) {
    if (evidenceId.empty()) {
      diagnostics.push_back("rewrite evidence id is empty");
    } else if (!containsString(contract.evidenceIds, evidenceId)) {
      diagnostics.push_back(
          "rewrite evidence missing from contract evidenceIds: " + evidenceId);
    }
  }
  appendEvidenceIdShapeDiagnostics(diagnostics, rewrites.evidenceIds,
                                   contract.resolvedTarget, "rewrite",
                                   seenNestedEvidenceIds);

  return diagnostics;
}

bool targetLegalizationContractSatisfiesInvariants(
    const TargetLegalizationContract &contract) {
  return targetLegalizationContractInvariantDiagnostics(contract).empty();
}

bool targetLegalizationSupportsPackage(
    const TargetLegalizationContract &contract) {
  if (!contract.supportsPackage ||
      contract.supportStatus == TargetLegalizationSupportStatus::Unsupported ||
      contract.state != TargetLegalizationState::Legalized ||
      contract.packageMode == TargetLegalizationPackageMode::Unsupported) {
    return false;
  }
  return !contract.diagnosticSummary.hasErrors &&
         targetLegalizationContractSatisfiesInvariants(contract);
}

bool targetLegalizationSupportsPackage(const TargetLegalizationResult &result) {
  return targetLegalizationSupportsPackage(targetLegalizationContract(result));
}

bool targetLegalizationProjectionSupportsPackage(
    const TargetLegalizationContractProjection &projection) {
  return projection.supportsPackage && !projection.coreEvidenceIds.empty();
}

TargetLegalizationResult legalizeTarget(const HIRModule &module,
                                        TargetKind preferredTarget) {
  return legalizeTarget(module, TargetLegalizationProfile{preferredTarget});
}

TargetLegalizationResult
legalizeTarget(const HIRModule &module,
               const TargetLegalizationProfile &profile) {
  std::vector<TargetLegalizationResult> results =
      legalizeTargets(module, profile);
  const TargetPackageSelection selection =
      results.empty()
          ? selectRecommendedPackageTarget(std::vector<TargetPackageDecision>{},
                                           profile.preferredTarget)
          : results.front().packageSelection;
  const TargetKind target = profile.preferredTarget == TargetKind::Auto
                                ? selection.selectedTarget
                                : profile.preferredTarget;

  const auto it =
      std::find_if(results.begin(), results.end(),
                   [target](const TargetLegalizationResult &result) {
                     return result.target == target;
                   });
  if (it != results.end()) {
    return *it;
  }

  return resultFromDecision(module, targetPackageDecision(module, target),
                            selection, profile.preferredTarget);
}

std::vector<TargetLegalizationResult>
legalizeTargets(const HIRModule &module, TargetKind preferredTarget) {
  return legalizeTargets(module, TargetLegalizationProfile{preferredTarget});
}

std::vector<TargetLegalizationResult>
legalizeTargets(const HIRModule &module,
                const TargetLegalizationProfile &profile) {
  std::vector<TargetPackageDecision> decisions = targetPackageDecisions(module);
  const TargetPackageSelection selection =
      selectRecommendedPackageTarget(decisions, profile.preferredTarget);

  std::vector<TargetLegalizationResult> results;
  results.reserve(decisions.size());
  for (const TargetPackageDecision &decision : decisions) {
    results.push_back(resultFromDecision(module, decision, selection,
                                         profile.preferredTarget));
  }
  return results;
}

} // namespace crossgl
