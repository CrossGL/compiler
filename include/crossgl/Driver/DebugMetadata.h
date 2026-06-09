#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

#include "crossgl/Backend/Target.h"
#include "crossgl/Driver/SourceRemap.h"
#include "crossgl/HIR/HIR.h"

namespace crossgl {

struct DebugMetadataManualTextureCompareKernelSummary {
  std::size_t totalCount = 0;
  std::size_t staticNormalizedCount = 0;
  std::size_t staticNonNormalizedCount = 0;
  std::size_t staticZeroSumCount = 0;
  std::size_t dynamicCount = 0;
};

struct DebugMetadataManualTextureCompareKernelBuckets {
  std::vector<std::size_t> staticNormalized;
  std::vector<std::size_t> staticNonNormalized;
  std::vector<std::size_t> staticZeroSum;
  std::vector<std::size_t> dynamic;
};

struct DebugMetadataManualTextureCompareKernel {
  std::size_t index = 0;
  std::string stage;
  std::string entryPoint;
  std::string function;
  std::string operation;
  std::string sourceKind;
  std::string canonicalOperation;
  bool compatibilityAlias = false;
  std::string weightClass;
  std::size_t tapCount = 0;
  bool weightsStatic = false;
  std::optional<double> weightSum;
  bool weightsZeroSum = false;
  bool weightsNormalized = false;
};

struct DebugMetadataTargetCapabilityGroup {
  std::string kind;
  std::size_t count = 0;
  std::vector<std::string> capabilities;
};

struct DebugMetadataTargetCapabilitySummary {
  std::string target;
  bool nativeImplemented = false;
  bool sourcePackageSupported = false;
  bool packageBuildSupported = false;
  std::string packageMode;
  std::string packageDecisionReason;
  std::vector<std::string> decisionReasonCodes;
  std::size_t packageRankScore = 0;
  std::size_t requiredCapabilityCount = 0;
  std::size_t missingCapabilityCount = 0;
  std::size_t requiredToolCount = 0;
  std::size_t missingToolCount = 0;
  std::vector<std::string> requiredCapabilities;
  std::vector<std::string> missingCapabilities;
  std::vector<std::string> legalizationCoreEvidenceIds;
  std::vector<std::string> requiredToolIds;
  std::vector<std::string> missingToolIds;
  bool optionalNativeToolMissing = false;
  std::string optionalNativeToolStatus;
  std::vector<std::string> toolRequirementEvidenceIds;
  std::vector<DebugMetadataTargetCapabilityGroup> requiredCapabilityGroups;
  std::vector<DebugMetadataTargetCapabilityGroup> missingCapabilityGroups;
};

struct DebugMetadataTargetCapabilities {
  std::string defaultTarget;
  std::vector<DebugMetadataTargetCapabilitySummary> summaries;
};

struct DebugMetadataTargetDecisionDiagnostic {
  std::string code;
  std::string severity;
  std::string target;
  std::string message;
  std::vector<std::string> capabilities;
  std::vector<std::string> legalizationCoreEvidenceIds;
  std::vector<DebugMetadataTargetCapabilityGroup> capabilityGroups;
};

struct DebugMetadataTargetFallback {
  std::size_t rank = 0;
  std::string target;
  std::string packageMode;
  std::string rankReason;
  bool nativeImplemented = false;
  bool sourcePackageSupported = false;
  bool packageBuildSupported = false;
  std::size_t missingCapabilityCount = 0;
  std::size_t requiredToolCount = 0;
  std::size_t missingToolCount = 0;
  std::vector<std::string> missingCapabilities;
  std::vector<std::string> legalizationCoreEvidenceIds;
  std::vector<std::string> requiredToolIds;
  std::vector<std::string> missingToolIds;
  bool optionalNativeToolMissing = false;
  std::string optionalNativeToolStatus;
  std::vector<std::string> toolRequirementEvidenceIds;
  std::vector<DebugMetadataTargetCapabilityGroup> missingCapabilityGroups;
};

struct DebugMetadataTargetDecision {
  std::string requestedTarget;
  std::string selectedTarget;
  std::string selectionReason;
  bool selectedTargetNativeImplemented = false;
  bool selectedTargetSourcePackageSupported = false;
  bool selectedTargetPackageBuildSupported = false;
  std::string selectedTargetPackageMode;
  std::size_t selectedTargetMissingCapabilityCount = 0;
  std::size_t selectedTargetRequiredToolCount = 0;
  std::size_t selectedTargetMissingToolCount = 0;
  std::vector<std::string> selectedTargetMissingCapabilities;
  std::vector<std::string> selectedTargetLegalizationCoreEvidenceIds;
  std::vector<std::string> selectedTargetRequiredToolIds;
  std::vector<std::string> selectedTargetMissingToolIds;
  bool selectedTargetOptionalNativeToolMissing = false;
  std::string selectedTargetOptionalNativeToolStatus;
  std::vector<std::string> selectedTargetToolRequirementEvidenceIds;
  std::vector<DebugMetadataTargetCapabilityGroup>
      selectedTargetMissingCapabilityGroups;
  std::size_t selectedTargetDiagnosticCount = 0;
  std::vector<DebugMetadataTargetDecisionDiagnostic> diagnostics;
  std::vector<std::string> viableTargets;
  std::vector<std::string> fallbackTargets;
  std::size_t fallbackTargetRecordCount = 0;
  std::vector<DebugMetadataTargetFallback> fallbackTargetRecords;
  std::vector<std::string> nonViableTargets;
};

struct DebugMetadataSourcePackageValidation {
  std::string target;
  std::string tool;
  std::string policy;
  std::string status;
};

struct DebugMetadataSourceLocation {
  std::string file;
  std::size_t line = 1;
  std::size_t column = 1;
  std::size_t offset = 0;
  std::size_t length = 0;
  std::size_t endLine = 1;
  std::size_t endColumn = 1;
  std::size_t endOffset = 0;
};

struct DebugMetadataHIRExpressionSourceLocation {
  std::size_t index = 0;
  std::string stage;
  std::string entryPoint;
  std::string function;
  std::string statementKind;
  std::string kind;
  std::string value;
  std::string type;
  DebugMetadataSourceLocation location;
  std::optional<DebugMetadataSourceLocation> originalLocation;
};

struct DebugMetadataHIRTypeSourceLocation {
  std::size_t index = 0;
  std::string stage;
  std::string entryPoint;
  std::string function;
  std::string ownerKind;
  std::string ownerName;
  std::string type;
  DebugMetadataSourceLocation location;
  std::optional<DebugMetadataSourceLocation> originalLocation;
};

struct DebugMetadataHIRStatementSourceLocation {
  std::size_t index = 0;
  std::string stage;
  std::string entryPoint;
  std::string function;
  std::string statementKind;
  std::string name;
  DebugMetadataSourceLocation location;
  std::optional<DebugMetadataSourceLocation> originalLocation;
};

struct DebugMetadataHIRResourceSourceLocation {
  std::size_t index = 0;
  std::string resourceRecordKind;
  std::string stage;
  std::string entryPoint;
  std::string function;
  std::string ownerKind;
  std::string ownerName;
  std::string resourceName;
  std::string resourceKind;
  std::string type;
  std::string accessKind;
  std::string accessPath;
  std::string operation;
  std::string memberName;
  std::string indexExpression;
  std::optional<std::size_t> bindingSet;
  std::optional<std::size_t> binding;
  DebugMetadataSourceLocation location;
  std::optional<DebugMetadataSourceLocation> originalLocation;
};

struct DebugMetadataHIRSourceLocationSummary {
  std::size_t expressionCount = 0;
  std::size_t expressionWithLocationCount = 0;
  std::size_t typeCount = 0;
  std::size_t typeWithLocationCount = 0;
  std::size_t statementCount = 0;
  std::size_t statementWithLocationCount = 0;
  std::size_t resourceCount = 0;
  std::size_t resourceWithLocationCount = 0;
};

struct DebugMetadataHIRSourceLocations {
  DebugMetadataHIRSourceLocationSummary summary;
  std::vector<DebugMetadataHIRExpressionSourceLocation> expressions;
  std::vector<DebugMetadataHIRTypeSourceLocation> types;
  std::vector<DebugMetadataHIRStatementSourceLocation> statements;
  std::vector<DebugMetadataHIRResourceSourceLocation> resources;
};

struct DebugMetadataHIRSourceMapFilter {
  std::optional<std::string> stage;
  std::optional<std::string> entryPoint;
  std::optional<std::string> function;
  std::optional<std::string> statementKind;
  std::optional<std::string> expressionKind;
  std::optional<std::string> expressionValue;
  std::optional<std::string> ownerKind;
  std::optional<std::string> ownerName;
  std::optional<std::string> resourceRecordKind;
  std::optional<std::string> resourceName;
  std::optional<std::string> resourceKind;
};

struct DebugMetadataHIRSourceMapPagination {
  std::size_t expressionOffset = 0;
  std::optional<std::size_t> expressionLimit;
  std::size_t typeOffset = 0;
  std::optional<std::size_t> typeLimit;
  std::size_t statementOffset = 0;
  std::optional<std::size_t> statementLimit;
  std::size_t resourceOffset = 0;
  std::optional<std::size_t> resourceLimit;
  bool recordsEnabled = false;
  std::size_t recordOffset = 0;
  std::optional<std::size_t> recordLimit;
};

struct DebugMetadataHIRSourceMapPage {
  DebugMetadataHIRSourceMapPagination request;
  std::size_t expressionTotalCount = 0;
  std::size_t expressionEmittedCount = 0;
  bool expressionHasMore = false;
  std::size_t expressionNextOffset = 0;
  std::size_t typeTotalCount = 0;
  std::size_t typeEmittedCount = 0;
  bool typeHasMore = false;
  std::size_t typeNextOffset = 0;
  std::size_t statementTotalCount = 0;
  std::size_t statementEmittedCount = 0;
  bool statementHasMore = false;
  std::size_t statementNextOffset = 0;
  std::size_t resourceTotalCount = 0;
  std::size_t resourceEmittedCount = 0;
  bool resourceHasMore = false;
  std::size_t resourceNextOffset = 0;
};

struct DebugMetadataHIRSourceMapCategoryCount {
  std::string name;
  std::size_t count = 0;
};

struct DebugMetadataHIRSourceMapCategoryCounts {
  std::size_t expressionTotalCount = 0;
  std::size_t typeTotalCount = 0;
  std::size_t statementTotalCount = 0;
  std::size_t resourceTotalCount = 0;
  std::size_t recordTotalCount = 0;
  std::vector<DebugMetadataHIRSourceMapCategoryCount> expressionKinds;
  std::vector<DebugMetadataHIRSourceMapCategoryCount> statementKinds;
  std::vector<DebugMetadataHIRSourceMapCategoryCount> typeOwnerKinds;
  std::vector<DebugMetadataHIRSourceMapCategoryCount> resourceRecordKinds;
  std::vector<DebugMetadataHIRSourceMapCategoryCount> resourceKinds;
};

struct DebugMetadataHIRSourceMapRecord {
  std::size_t cursor = 0;
  std::string recordKind;
  DebugMetadataHIRExpressionSourceLocation expression;
  DebugMetadataHIRTypeSourceLocation type;
  DebugMetadataHIRStatementSourceLocation statement;
  DebugMetadataHIRResourceSourceLocation resource;
};

struct DebugMetadataHIRSourceMapRecords {
  bool enabled = false;
  std::size_t activeCount = 0;
  std::size_t offset = 0;
  std::optional<std::size_t> limit;
  std::size_t totalCount = 0;
  std::size_t emittedCount = 0;
  bool hasMore = false;
  std::size_t nextOffset = 0;
  std::vector<DebugMetadataHIRSourceMapRecord> items;
};

struct DebugMetadataHIRSourceMapDocument {
  int schemaVersion = 7;
  DebugMetadataHIRSourceMapFilter filters;
  DebugMetadataHIRSourceMapPage pagination;
  DebugMetadataHIRSourceMapCategoryCounts categoryCounts;
  DebugMetadataHIRSourceMapRecords records;
  DebugMetadataHIRSourceLocations hirSourceLocations;
};

struct DebugMetadataHIRSourceMapOptions {
  int schemaVersion = 7;
  std::optional<SourceRemap> sourceRemap;
};

struct DebugMetadataOptions {
  std::optional<SourceRemap> sourceRemap;
};

struct DebugMetadataDocument {
  int schemaVersion = 11;
  DebugMetadataTargetDecision targetDecision;
  DebugMetadataTargetCapabilities targetCapabilities;
  std::optional<DebugMetadataSourcePackageValidation> sourcePackageValidation;
  DebugMetadataHIRSourceLocations hirSourceLocations;
  DebugMetadataManualTextureCompareKernelSummary
      manualTextureCompareKernelSummary;
  DebugMetadataManualTextureCompareKernelBuckets manualTextureCompareKernelBuckets;
  std::vector<DebugMetadataManualTextureCompareKernel>
      manualTextureCompareKernels;
};

DebugMetadataDocument buildDebugMetadataDocument(
    const HIRModule &module, TargetKind requestedTarget = TargetKind::Auto,
    const std::optional<DebugMetadataSourcePackageValidation>
        &sourcePackageValidation = std::nullopt);
DebugMetadataDocument buildDebugMetadataDocument(
    const HIRModule &module, TargetKind requestedTarget,
    const std::optional<DebugMetadataSourcePackageValidation>
        &sourcePackageValidation,
    const DebugMetadataOptions &options);
DebugMetadataHIRSourceMapDocument buildHIRSourceMapDocument(
    const HIRModule &module,
    const DebugMetadataHIRSourceMapFilter &filters = {},
    const DebugMetadataHIRSourceMapPagination &pagination = {});
DebugMetadataHIRSourceMapDocument buildHIRSourceMapDocument(
    const HIRModule &module, const DebugMetadataHIRSourceMapFilter &filters,
    const DebugMetadataHIRSourceMapPagination &pagination,
    const DebugMetadataHIRSourceMapOptions &options);
std::string debugMetadataJson(
    const HIRModule &module, TargetKind requestedTarget = TargetKind::Auto,
    const std::optional<DebugMetadataSourcePackageValidation>
        &sourcePackageValidation = std::nullopt);
std::string debugMetadataJson(
    const HIRModule &module, TargetKind requestedTarget,
    const std::optional<DebugMetadataSourcePackageValidation>
        &sourcePackageValidation,
    const DebugMetadataOptions &options);
std::string debugMetadataJson(const DebugMetadataDocument &document);
std::string hirSourceMapJson(
    const HIRModule &module,
    const DebugMetadataHIRSourceMapFilter &filters = {},
    const DebugMetadataHIRSourceMapPagination &pagination = {});
std::string hirSourceMapJson(
    const HIRModule &module, const DebugMetadataHIRSourceMapFilter &filters,
    const DebugMetadataHIRSourceMapPagination &pagination,
    const DebugMetadataHIRSourceMapOptions &options);
std::string hirSourceMapJson(const DebugMetadataHIRSourceMapDocument &document);

} // namespace crossgl
