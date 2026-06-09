#pragma once

#include "crossgl/Backend/TargetCapabilities.h"
#include "crossgl/Basic/Diagnostic.h"

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace crossgl {

enum class TargetLegalizationSupportStatus {
  Unsupported,
  SourcePackage,
  NativePackage,
};

enum class TargetLegalizationState {
  Rejected,
  Legalized,
};

enum class TargetLegalizationPackageMode {
  Unsupported,
  SourcePackage,
  Native,
};

enum class TargetLegalizationPackageDecisionProvenance {
  Unsupported,
  NativePackageAvailable,
  SourcePackageOnly,
  UnsupportedSourceForm,
  UnsupportedNativeForm,
  UnsupportedRawHIR,
};

enum class TargetLegalizationOptionalNativeToolStatus {
  NotRequired,
  Available,
  Missing,
};

enum class TargetLegalizationABIState {
  Empty,
  Present,
  Unsupported,
};

enum class TargetLegalizationRewriteState {
  Empty,
  Unchanged,
  Rewritten,
  Unsupported,
};

enum class TargetSourcePackageDescriptorOptimizationLevelMode {
  Unknown,
  RequestedLevel,
};

enum class TargetSourcePackageDescriptorToolProvenanceMode {
  Planned,
  NativeCompiler,
  NativeValidator,
};

enum class TargetSourcePackageDescriptorOptimizationEvidenceMode {
  None,
  DirectXDxc,
};

enum class TargetNativePackageDescriptorOptimizationEvidenceMode {
  None,
  DirectXDxc,
  MetalXcrunMetal,
  VulkanSpirvOpt,
};

struct TargetNativePackageToolPolicy {
  std::string requirementKind;
  std::string name;
  std::string role;
  std::string executable;
  std::string probeName;
  std::string requirementName;
};

struct TargetLegalizationABIRecord {
  TargetKind target = TargetKind::Auto;
  std::string kind;
  std::string name;
  std::string evidenceId;
};

struct TargetLegalizationABIFacts {
  TargetKind target = TargetKind::Auto;
  TargetLegalizationABIState state = TargetLegalizationABIState::Empty;
  bool complete = false;
  std::vector<TargetLegalizationABIRecord> requiredRecords;
  std::vector<TargetLegalizationABIRecord> missingRecords;
  std::vector<std::string> evidenceIds;
  std::vector<std::string> requiredFacts;
  std::vector<std::string> missingFacts;
};

struct TargetLegalizationResourceBindingRecord {
  TargetKind target = TargetKind::Auto;
  std::string stage;
  std::string sourceEntryPoint;
  std::string backendEntryPoint;
  std::string name;
  std::string kind;
  std::string sourceType;
  std::string addressSpace;
  std::string abi;
  std::string bindingClass;
  std::optional<std::string> metalType;
  std::optional<std::string> hlslType;
  std::optional<std::string> descriptorType;
  std::optional<std::string> storageClass;
  std::optional<std::string> spirvType;
  std::optional<std::string> storageImageFormat;
  std::optional<std::string> storageImageAccess;
  std::optional<std::size_t> argumentIndex;
  std::optional<std::size_t> set;
  std::optional<std::size_t> binding;
  std::string evidenceId;
};

struct TargetLegalizationResourceBindingFacts {
  TargetKind target = TargetKind::Auto;
  bool complete = false;
  std::size_t requiredRecordCount = 0;
  std::vector<TargetLegalizationResourceBindingRecord> records;
  std::vector<std::string> evidenceIds;
};

struct TargetLegalizationToolRequirementRecord {
  TargetKind target = TargetKind::Auto;
  std::string kind;
  std::string name;
  std::string evidenceId;
};

struct TargetLegalizationToolRequirementSummary {
  TargetKind target = TargetKind::Auto;
  std::size_t requiredToolCount = 0;
  std::size_t missingToolCount = 0;
  std::vector<TargetLegalizationToolRequirementRecord> requiredRecords;
  std::vector<TargetLegalizationToolRequirementRecord> missingRecords;
  std::vector<std::string> evidenceIds;
  std::vector<std::string> requiredToolIds;
  std::vector<std::string> missingToolIds;
};

struct TargetLegalizationDiagnostic {
  std::string evidenceId;
  DiagnosticSeverity severity = DiagnosticSeverity::Note;
  std::string code;
  std::string message;
  std::optional<SourceLocation> location;
  TargetKind target = TargetKind::Auto;
  std::vector<TargetCapability> capabilities;
};

struct TargetLegalizationRewriteRecord {
  TargetKind target = TargetKind::Auto;
  TargetLegalizationRewriteState state = TargetLegalizationRewriteState::Empty;
  std::string evidenceId;
  std::string kind;
  std::string name;
  std::string description;
  bool applied = false;
};

struct TargetLegalizationRewriteCollection {
  TargetKind target = TargetKind::Auto;
  TargetLegalizationRewriteState state = TargetLegalizationRewriteState::Empty;
  bool complete = false;
  std::vector<TargetLegalizationRewriteRecord> records;
  std::vector<std::string> evidenceIds;
};

struct TargetLegalizationProfile {
  TargetKind preferredTarget = TargetKind::Auto;
};

struct TargetLegalizationTargetProfile {
  TargetKind requestedTarget = TargetKind::Auto;
  std::string requestedTargetName;
  TargetKind preferredTarget = TargetKind::Auto;
  std::string preferredTargetName;
  TargetKind resolvedTarget = TargetKind::Auto;
  std::string resolvedTargetName;
  TargetKind selectedTarget = TargetKind::Auto;
  std::string selectedTargetName;
  bool autoRequested = false;
  bool selectedTargetBuildable = false;
};

struct TargetLegalizationCapabilitySummary {
  std::size_t requiredCapabilityCount = 0;
  std::size_t missingCapabilityCount = 0;
  std::vector<std::string> requiredCapabilityIds;
  std::vector<std::string> missingCapabilityIds;
};

struct TargetLegalizationDiagnosticSummary {
  std::size_t diagnosticCount = 0;
  std::size_t noteCount = 0;
  std::size_t warningCount = 0;
  std::size_t errorCount = 0;
  bool hasErrors = false;
  std::vector<std::string> severities;
  std::vector<std::string> codes;
  std::vector<std::string> evidenceIds;
};

struct TargetLegalizationConsumerAuditReference {
  std::string consumer;
  std::string auditPath;
  std::string auditSection;
};

struct TargetPackageArtifactRequirements {
  TargetKind target = TargetKind::Auto;
  std::string targetName;
  TargetLegalizationPackageMode packageMode =
      TargetLegalizationPackageMode::Unsupported;
  std::string packageModeName;
  std::vector<std::string> requiredPathArtifactKeys;
  bool requiresNativeBinaryStatus = false;
  bool allowsPlannedNativeBinary = false;
  bool allowsPlannedNativeSourceEvidence = false;
  std::vector<std::string> evidenceIds;
};

struct TargetSourcePackageDescriptorPolicy {
  TargetKind target = TargetKind::Auto;
  std::string targetName;
  bool supported = false;
  std::string binaryKind;
  std::string sourceArtifactKey = "backendSource";
  std::string nativeBinaryArtifactKey = "nativeBinary";
  std::string descriptorArtifactKey = "nativeArtifactDescriptor";
  std::string nativeBinaryStatus;
  bool includesNativeBinaryStatus = false;
  bool requiresProducedNativeArtifact = false;
  std::string validationStatus = "unavailable";
  TargetSourcePackageDescriptorOptimizationLevelMode optimizationLevelMode =
      TargetSourcePackageDescriptorOptimizationLevelMode::Unknown;
  std::string fixedOptimizationLevel = "unknown";
  TargetSourcePackageDescriptorOptimizationEvidenceMode
      optimizationEvidenceMode =
          TargetSourcePackageDescriptorOptimizationEvidenceMode::None;
  std::string optimizationEvidenceModeName = "none";
  TargetSourcePackageDescriptorToolProvenanceMode toolProvenanceMode =
      TargetSourcePackageDescriptorToolProvenanceMode::Planned;
  std::string toolProvenanceModeName = "planned";
  std::string nativeToolName;
  std::string nativeToolRole;
  std::string nativeToolExecutable;
  std::string nativeToolProbeName;
};

struct TargetNativePackageDescriptorPolicy {
  TargetKind target = TargetKind::Auto;
  std::string targetName;
  bool supported = false;
  std::string binaryKind;
  std::string sourceArtifactKey = "backendAssembly";
  std::string nativeBinaryArtifactKey = "nativeBinary";
  std::string descriptorArtifactKey = "nativeArtifactDescriptor";
  std::string profileArtifactKey = "nativeProfile";
  std::string validationStatus;
  TargetNativePackageDescriptorOptimizationEvidenceMode
      optimizationEvidenceMode =
          TargetNativePackageDescriptorOptimizationEvidenceMode::None;
  std::string optimizationEvidenceModeName = "none";
  std::string optimizationToolName;
  std::string disassemblyToolName;
  std::string disassemblyPolicy;
  std::string profileApi;
  std::string profileName;
  std::string vulkanVersion;
  std::string spirvVersion;
  std::string generatorName;
  std::string binaryFormat;
  std::string assemblyFormat;
  std::vector<TargetNativePackageToolPolicy> requiredTools;
};

struct TargetLegalizationContract {
  std::size_t version = 0;
  TargetLegalizationTargetProfile targetProfile;
  TargetKind requestedTarget = TargetKind::Auto;
  TargetKind resolvedTarget = TargetKind::Auto;
  std::string resolvedTargetName;
  bool nativeImplemented = false;
  bool sourcePackageSupported = false;
  bool supportsPackage = false;
  TargetLegalizationSupportStatus supportStatus =
      TargetLegalizationSupportStatus::Unsupported;
  std::string supportStatusName;
  TargetLegalizationState state = TargetLegalizationState::Rejected;
  std::string stateName;
  TargetLegalizationPackageMode packageMode =
      TargetLegalizationPackageMode::Unsupported;
  std::string packageModeName;
  TargetLegalizationPackageDecisionProvenance packageDecisionProvenance =
      TargetLegalizationPackageDecisionProvenance::Unsupported;
  std::string packageDecisionProvenanceName;
  bool optionalNativeToolMissing = false;
  TargetLegalizationOptionalNativeToolStatus optionalNativeToolStatus =
      TargetLegalizationOptionalNativeToolStatus::NotRequired;
  std::string optionalNativeToolStatusName;
  std::string reason;
  std::size_t packageRankScore = 0;
  std::size_t requiredCapabilityCount = 0;
  std::size_t missingCapabilityCount = 0;
  std::vector<std::string> requiredCapabilityIds;
  std::vector<std::string> missingCapabilityIds;
  TargetLegalizationDiagnosticSummary diagnosticSummary;
  std::vector<TargetLegalizationDiagnostic> diagnostics;
  TargetLegalizationABIFacts abiFacts;
  TargetLegalizationResourceBindingFacts resourceBindings;
  TargetLegalizationToolRequirementSummary toolRequirements;
  TargetPackageArtifactRequirements packageArtifactRequirements;
  TargetSourcePackageDescriptorPolicy sourcePackageDescriptorPolicy;
  TargetNativePackageDescriptorPolicy nativePackageDescriptorPolicy;
  TargetLegalizationRewriteCollection rewrites;
  std::vector<std::string> evidenceIds;
};

struct TargetLegalizationContractProjection {
  std::size_t version = 0;
  TargetLegalizationTargetProfile targetProfile;
  bool nativeImplemented = false;
  bool sourcePackageSupported = false;
  bool supportsPackage = false;
  TargetLegalizationSupportStatus supportStatus =
      TargetLegalizationSupportStatus::Unsupported;
  std::string supportStatusName;
  TargetLegalizationState state = TargetLegalizationState::Rejected;
  std::string stateName;
  TargetLegalizationPackageMode packageMode =
      TargetLegalizationPackageMode::Unsupported;
  std::string packageModeName;
  TargetLegalizationPackageDecisionProvenance packageDecisionProvenance =
      TargetLegalizationPackageDecisionProvenance::Unsupported;
  std::string packageDecisionProvenanceName;
  bool optionalNativeToolMissing = false;
  TargetLegalizationOptionalNativeToolStatus optionalNativeToolStatus =
      TargetLegalizationOptionalNativeToolStatus::NotRequired;
  std::string optionalNativeToolStatusName;
  std::string reason;
  std::vector<std::string> consumerDecisionReasonCodes;
  std::size_t packageRankScore = 0;
  std::size_t requiredCapabilityCount = 0;
  std::size_t missingCapabilityCount = 0;
  std::vector<std::string> requiredCapabilityIds;
  std::vector<std::string> missingCapabilityIds;
  TargetLegalizationDiagnosticSummary diagnosticSummary;
  std::vector<std::string> diagnosticEvidenceIds;
  std::size_t requiredToolCount = 0;
  std::size_t missingToolCount = 0;
  std::vector<std::string> requiredToolIds;
  std::vector<std::string> missingToolIds;
  std::vector<TargetLegalizationToolRequirementRecord> requiredToolRecords;
  std::vector<TargetLegalizationToolRequirementRecord> missingToolRecords;
  std::vector<std::string> toolRequirementEvidenceIds;
  TargetLegalizationABIState abiState = TargetLegalizationABIState::Empty;
  std::string abiStateName;
  bool abiComplete = false;
  std::size_t abiRequiredRecordCount = 0;
  std::size_t abiMissingRecordCount = 0;
  std::vector<std::string> requiredABIFacts;
  std::vector<std::string> missingABIFacts;
  std::vector<std::string> abiEvidenceIds;
  bool resourceBindingComplete = false;
  std::size_t resourceBindingRequiredRecordCount = 0;
  std::size_t resourceBindingRecordCount = 0;
  std::vector<std::string> resourceBindingEvidenceIds;
  TargetPackageArtifactRequirements packageArtifactRequirements;
  std::vector<std::string> packageArtifactRequirementEvidenceIds;
  TargetSourcePackageDescriptorPolicy sourcePackageDescriptorPolicy;
  TargetNativePackageDescriptorPolicy nativePackageDescriptorPolicy;
  TargetLegalizationRewriteState rewriteState =
      TargetLegalizationRewriteState::Empty;
  std::string rewriteStateName;
  bool rewriteComplete = false;
  std::size_t rewriteRecordCount = 0;
  std::vector<std::string> rewriteEvidenceIds;
  std::vector<std::string> coreEvidenceIds;
  std::vector<std::string> evidenceIds;
  std::vector<TargetLegalizationConsumerAuditReference> consumerAuditReferences;
};

struct TargetLegalizationResult {
  TargetKind requestedTarget = TargetKind::Auto;
  TargetKind target = TargetKind::Auto;
  std::string targetName;
  TargetPackageSelection packageSelection;
  TargetPackageDecision packageDecision;
  bool nativeImplemented = false;
  bool sourcePackageSupported = false;
  bool packageBuildSupported = false;
  std::string packageMode;
  std::string packageDecisionReason;
  std::size_t packageRankScore = 0;
  std::vector<TargetCapability> requiredCapabilities;
  std::vector<TargetCapability> missingCapabilities;
  TargetLegalizationSupportStatus supportStatus =
      TargetLegalizationSupportStatus::Unsupported;
  TargetLegalizationState state = TargetLegalizationState::Rejected;
  TargetLegalizationPackageMode packageModeKind =
      TargetLegalizationPackageMode::Unsupported;
  TargetLegalizationPackageDecisionProvenance packageDecisionProvenance =
      TargetLegalizationPackageDecisionProvenance::Unsupported;
  bool optionalNativeToolMissing = false;
  TargetLegalizationOptionalNativeToolStatus optionalNativeToolStatus =
      TargetLegalizationOptionalNativeToolStatus::NotRequired;
  std::string optionalNativeToolStatusName;
  std::vector<TargetLegalizationDiagnostic> diagnostics;
  std::vector<TargetLegalizationRewriteRecord> rewriteRecords;
  TargetLegalizationRewriteCollection rewrites;
  TargetLegalizationABIFacts abiFacts;
  TargetLegalizationResourceBindingFacts resourceBindings;
  TargetLegalizationToolRequirementSummary toolRequirements;
  TargetPackageArtifactRequirements packageArtifactRequirements;
  TargetSourcePackageDescriptorPolicy sourcePackageDescriptorPolicy;
  TargetNativePackageDescriptorPolicy nativePackageDescriptorPolicy;
  std::vector<std::string> evidenceIds;
};

struct TargetLegalizationAdmissionDecision {
  TargetLegalizationContract contract;
  TargetLegalizationContractProjection projection;
  bool admitted = false;
  std::vector<std::string> coreEvidenceIds;
  std::vector<std::string> diagnosticEvidenceIds;
  std::vector<std::string> evidenceIds;
};

const char *
targetLegalizationSupportStatusName(TargetLegalizationSupportStatus status);
TargetLegalizationSupportStatus
targetLegalizationSupportStatusFromName(std::string_view name);
const char *targetLegalizationStateName(TargetLegalizationState state);
TargetLegalizationState targetLegalizationStateFromName(std::string_view name);
const char *
targetLegalizationPackageModeName(TargetLegalizationPackageMode mode);
TargetLegalizationPackageMode
targetLegalizationPackageModeFromName(std::string_view name);
const char *targetLegalizationPackageDecisionProvenanceName(
    TargetLegalizationPackageDecisionProvenance provenance);
TargetLegalizationPackageDecisionProvenance
targetLegalizationPackageDecisionProvenanceFromName(std::string_view name);
const char *targetLegalizationOptionalNativeToolStatusName(
    TargetLegalizationOptionalNativeToolStatus status);
TargetLegalizationOptionalNativeToolStatus
targetLegalizationOptionalNativeToolStatusFromName(std::string_view name);
const char *targetLegalizationABIStateName(TargetLegalizationABIState state);
TargetLegalizationABIState
targetLegalizationABIStateFromName(std::string_view name);
const char *
targetLegalizationRewriteStateName(TargetLegalizationRewriteState state);
TargetLegalizationRewriteState
targetLegalizationRewriteStateFromName(std::string_view name);
bool targetPackageArtifactRequirementsAllowNativeBinaryStatus(
    const TargetPackageArtifactRequirements &requirements,
    std::string_view nativeBinaryStatus);
bool targetLegalizationProjectionAllowsSourcePackageNativeBinaryStatus(
    const TargetLegalizationContractProjection &projection,
    std::string_view nativeBinaryStatus);
bool targetPackageArtifactRequirementsRequireNativeBinaryArtifact(
    const TargetPackageArtifactRequirements &requirements,
    std::string_view nativeBinaryStatus);
bool targetLegalizationProjectionRequiresSourcePackageNativeBinaryArtifact(
    const TargetLegalizationContractProjection &projection,
    std::string_view nativeBinaryStatus);
const char *targetSourcePackageDescriptorOptimizationLevelModeName(
    TargetSourcePackageDescriptorOptimizationLevelMode mode);
const char *targetSourcePackageDescriptorToolProvenanceModeName(
    TargetSourcePackageDescriptorToolProvenanceMode mode);
const char *targetSourcePackageDescriptorOptimizationEvidenceModeName(
    TargetSourcePackageDescriptorOptimizationEvidenceMode mode);
const char *targetNativePackageDescriptorOptimizationEvidenceModeName(
    TargetNativePackageDescriptorOptimizationEvidenceMode mode);
TargetSourcePackageDescriptorPolicy targetSourcePackageDescriptorPolicy(
    const TargetPackageArtifactRequirements &requirements,
    std::string_view nativeBinaryStatus, TargetKind target,
    std::string_view nativeToolName = {});
TargetSourcePackageDescriptorPolicy targetSourcePackageDescriptorPolicy(
    const TargetPackageArtifactRequirements &requirements,
    TargetKind target = TargetKind::Auto);
TargetSourcePackageDescriptorPolicy targetSourcePackageDescriptorPolicy(
    const TargetLegalizationContractProjection &projection,
    std::string_view nativeBinaryStatus, std::string_view nativeToolName = {});
TargetSourcePackageDescriptorPolicy targetSourcePackageDescriptorPolicy(
    const TargetLegalizationContractProjection &projection);
TargetNativePackageDescriptorPolicy targetNativePackageDescriptorPolicy(
    const TargetPackageArtifactRequirements &requirements,
    TargetKind target = TargetKind::Auto);
TargetNativePackageDescriptorPolicy targetNativePackageDescriptorPolicy(
    const TargetLegalizationContractProjection &projection);
bool targetLegalizationSucceeded(const TargetLegalizationResult &result);
TargetLegalizationCapabilitySummary
targetLegalizationCapabilitySummary(const TargetLegalizationResult &result);
TargetLegalizationDiagnosticSummary
targetLegalizationDiagnosticSummary(const TargetLegalizationResult &result);
Diagnostic
targetLegalizationDiagnostic(const TargetLegalizationDiagnostic &diagnostic);
std::vector<Diagnostic>
targetLegalizationDiagnostics(const TargetLegalizationContract &contract);
std::vector<Diagnostic>
targetLegalizationDiagnostics(const TargetLegalizationResult &result);
std::vector<std::string>
targetLegalizationCoreEvidenceIds(const TargetLegalizationContract &contract);
std::vector<std::string>
targetLegalizationCoreEvidenceIds(const TargetLegalizationResult &result);
TargetLegalizationContract
targetLegalizationContract(const TargetLegalizationResult &result);
const std::vector<TargetLegalizationConsumerAuditReference> &
targetLegalizationConsumerAuditReferences();
TargetLegalizationContractProjection targetLegalizationContractProjection(
    const TargetLegalizationContract &contract);
TargetLegalizationContractProjection
targetLegalizationContractProjection(const TargetLegalizationResult &result);
TargetLegalizationContractProjection
targetLegalizationSourcePackageFallbackProjection(const HIRModule &module,
                                                  TargetKind target);
TargetLegalizationAdmissionDecision
targetLegalizationAdmissionDecision(const TargetLegalizationContract &contract);
TargetLegalizationAdmissionDecision
targetLegalizationAdmissionDecision(const TargetLegalizationResult &result);
std::string targetLegalizationContractProjectionJson(
    const TargetLegalizationContractProjection &projection);
std::string targetLegalizationContractProjectionJson(
    const TargetLegalizationContract &contract);
std::string targetLegalizationContractProjectionJson(
    const TargetLegalizationResult &result);
std::string
targetLegalizationResultV0Json(const TargetLegalizationContract &contract);
std::string
targetLegalizationResultV0Json(const TargetLegalizationResult &result);
std::vector<std::string> targetLegalizationContractInvariantDiagnostics(
    const TargetLegalizationContract &contract);
bool targetLegalizationContractSatisfiesInvariants(
    const TargetLegalizationContract &contract);
bool targetLegalizationSupportsPackage(
    const TargetLegalizationContract &contract);
bool targetLegalizationSupportsPackage(const TargetLegalizationResult &result);
bool targetLegalizationProjectionSupportsPackage(
    const TargetLegalizationContractProjection &projection);

TargetLegalizationResult
legalizeTarget(const HIRModule &module,
               TargetKind preferredTarget = TargetKind::Auto);
TargetLegalizationResult
legalizeTarget(const HIRModule &module,
               const TargetLegalizationProfile &profile);
std::vector<TargetLegalizationResult>
legalizeTargets(const HIRModule &module,
                TargetKind preferredTarget = TargetKind::Auto);
std::vector<TargetLegalizationResult>
legalizeTargets(const HIRModule &module,
                const TargetLegalizationProfile &profile);

} // namespace crossgl
