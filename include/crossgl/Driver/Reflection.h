#pragma once

#include <cstddef>
#include <filesystem>
#include <optional>
#include <string>
#include <vector>

#include "crossgl/Backend/TargetLegalization.h"
#include "crossgl/HIR/HIR.h"

namespace crossgl {

struct ReflectionParameter {
  std::string name;
  std::string type;
};

struct ReflectionArrayDimension {
  std::string source;
  std::string kind;
  std::optional<std::size_t> elementCount;
};

struct ReflectionEntryPoint {
  std::string stage;
  std::string sourceName;
  std::string backendName;
  std::string returnType;
  std::vector<ReflectionParameter> parameters;
};

struct ReflectionField {
  std::string name;
  std::string type;
  std::vector<ReflectionArrayDimension> arrayDimensions;
};

struct ReflectionStruct {
  std::string name;
  std::vector<ReflectionField> fields;
};

struct ReflectionResource {
  std::string stage;
  std::string name;
  std::string kind;
  std::string type;
  std::vector<ReflectionArrayDimension> arrayDimensions;
  std::optional<std::size_t> set;
  std::optional<std::size_t> binding;
  std::optional<std::string> addressSpace;
  std::optional<std::string> storageImageFormat;
};

struct ReflectionStorageBufferFieldLayout {
  std::string name;
  std::string type;
  std::size_t offsetBytes = 0;
  std::size_t sizeBytes = 0;
  std::size_t storageSizeBytes = 0;
  std::size_t alignmentBytes = 0;
  std::optional<std::size_t> arrayElementCount;
  std::optional<std::size_t> arrayStrideBytes;
  std::vector<ReflectionArrayDimension> arrayDimensions;
};

struct ReflectionStorageBufferLayout {
  std::string elementType;
  std::size_t elementSizeBytes = 0;
  std::size_t arrayStrideBytes = 0;
  std::string layout;
  std::size_t alignmentBytes = 0;
  bool supportsScalarLayout = false;
  std::vector<ReflectionStorageBufferFieldLayout> fields;
};

struct ReflectionTargetResourceBinding {
  std::string target;
  std::string stage;
  std::string entryPoint;
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
  std::optional<std::size_t> argumentIndex;
  std::optional<std::size_t> set;
  std::optional<std::size_t> binding;
  std::optional<std::string> arraySize;
  std::optional<std::size_t> arrayElementCount;
  std::vector<ReflectionArrayDimension> arrayDimensions;
  std::optional<ReflectionStorageBufferLayout> storageBufferLayout;
  std::vector<std::string> usageRoles;
};

struct ReflectionFunctionConstant {
  std::string name;
  std::string type;
  std::optional<std::string> value;
};

struct ReflectionVertexAttribute {
  std::string name;
  std::string type;
  std::size_t location = 0;
};

struct ReflectionVertexLayout {
  std::string entryPoint;
  std::vector<ReflectionVertexAttribute> attributes;
};

struct ReflectionWorkgroupSize {
  std::string stage;
  std::string entryPoint;
  std::string x;
  std::string y;
  std::string z;
  std::string sourceX;
  std::string sourceY;
  std::string sourceZ;
};

struct ReflectionManualTextureCompareKernel {
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

struct ReflectionManualTextureCompareKernelSummary {
  std::size_t totalCount = 0;
  std::size_t staticNormalizedCount = 0;
  std::size_t staticNonNormalizedCount = 0;
  std::size_t staticZeroSumCount = 0;
  std::size_t dynamicCount = 0;
};

struct ReflectionTargetFeature {
  std::string target;
  std::string kind;
  std::string name;
};

struct ReflectionDocument {
  int schemaVersion = 1;
  std::string module;
  std::string target;
  std::string nativeBinary;
  std::vector<std::string> legalizationCoreEvidenceIds;
  std::vector<ReflectionEntryPoint> entryPoints;
  std::vector<ReflectionStruct> structs;
  std::vector<ReflectionResource> resources;
  std::vector<ReflectionTargetResourceBinding> targetResourceBindings;
  std::vector<ReflectionFunctionConstant> functionConstants;
  std::vector<ReflectionVertexLayout> vertexLayouts;
  std::vector<ReflectionWorkgroupSize> workgroupSizes;
  ReflectionManualTextureCompareKernelSummary manualTextureCompareKernelSummary;
  std::vector<ReflectionManualTextureCompareKernel> manualTextureCompareKernels;
  std::vector<ReflectionTargetFeature> targetFeatures;
};

std::vector<ReflectionTargetFeature>
reflectionTargetFeaturesFromLegalization(
    const TargetLegalizationResult &legalization);
std::vector<ReflectionTargetFeature>
reflectionTargetFeaturesFromLegalization(
    const TargetLegalizationContract &contract);
ReflectionTargetResourceBinding reflectionTargetResourceBindingFromLegalization(
    const TargetLegalizationResourceBindingRecord &record);
std::vector<ReflectionTargetResourceBinding>
reflectionTargetResourceBindingsFromLegalization(
    const TargetLegalizationResourceBindingFacts &resourceBindings);

ReflectionDocument buildReflectionDocument(
    const HIRModule &module, TargetKind target,
    const std::filesystem::path &nativeBinaryPath);
ReflectionDocument buildReflectionDocument(
    const HIRModule &module, const TargetLegalizationContract &contract,
    const std::filesystem::path &nativeBinaryPath);

std::string reflectionJson(const HIRModule &module, TargetKind target,
                           const std::filesystem::path &nativeBinaryPath);
std::string reflectionJson(const ReflectionDocument &document);

} // namespace crossgl
