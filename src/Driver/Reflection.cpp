#include "crossgl/Driver/Reflection.h"

#include "crossgl/Backend/BackendExpressions.h"
#include "crossgl/Backend/BackendPlan.h"
#include "crossgl/Backend/TextureCompare.h"
#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/Basic/Json.h"
#include "crossgl/Driver/StorageLayout.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <algorithm>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string_view>
#include <utility>

namespace crossgl {
namespace {

void writeReflectionParameterJson(std::ostringstream &out,
                                  const ReflectionParameter &parameter) {
  out << "{\"name\":\"" << escapeJson(parameter.name) << "\",\"type\":\""
      << escapeJson(parameter.type) << "\"}";
}

void writeJsonStringArray(std::ostringstream &out,
                          const std::vector<std::string> &values) {
  out << "[";
  for (std::size_t i = 0; i < values.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    out << "\"" << escapeJson(values[i]) << "\"";
  }
  out << "]";
}

void writeArrayDimensionsJson(
    std::ostringstream &out,
    const std::vector<ReflectionArrayDimension> &dimensions) {
  if (dimensions.empty()) {
    return;
  }

  out << ",\"arrayDimensions\":[";
  for (std::size_t i = 0; i < dimensions.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const ReflectionArrayDimension &dimension = dimensions[i];
    out << "{\"source\":\"" << escapeJson(dimension.source) << "\",\"kind\":\""
        << escapeJson(dimension.kind) << "\"";
    if (dimension.elementCount.has_value()) {
      out << ",\"elementCount\":" << *dimension.elementCount;
    }
    out << "}";
  }
  out << "]";
}

void writeReflectionFieldJson(std::ostringstream &out,
                              const ReflectionField &field) {
  out << "{\"name\":\"" << escapeJson(field.name) << "\",\"type\":\""
      << escapeJson(field.type) << "\"";
  writeArrayDimensionsJson(out, field.arrayDimensions);
  out << "}";
}

void writeStorageBufferLayoutJson(std::ostringstream &out,
                                  const ReflectionStorageBufferLayout &layout) {
  out << "{"
      << "\"elementType\":\"" << escapeJson(layout.elementType) << "\","
      << "\"elementSizeBytes\":" << layout.elementSizeBytes << ","
      << "\"arrayStrideBytes\":" << layout.arrayStrideBytes << ","
      << "\"layout\":\"" << escapeJson(layout.layout) << "\","
      << "\"alignmentBytes\":" << layout.alignmentBytes << ","
      << "\"supportsScalarLayout\":"
      << (layout.supportsScalarLayout ? "true" : "false");
  if (!layout.fields.empty()) {
    out << ",\"fields\":[";
    for (std::size_t i = 0; i < layout.fields.size(); ++i) {
      if (i != 0) {
        out << ",";
      }
      const ReflectionStorageBufferFieldLayout &field = layout.fields[i];
      out << "{"
          << "\"name\":\"" << escapeJson(field.name) << "\","
          << "\"type\":\"" << escapeJson(field.type) << "\","
          << "\"offsetBytes\":" << field.offsetBytes << ","
          << "\"sizeBytes\":" << field.sizeBytes << ","
          << "\"storageSizeBytes\":" << field.storageSizeBytes << ","
          << "\"alignmentBytes\":" << field.alignmentBytes;
      if (field.arrayElementCount.has_value()) {
        out << ",\"arrayElementCount\":" << *field.arrayElementCount;
      }
      if (field.arrayStrideBytes.has_value()) {
        out << ",\"arrayStrideBytes\":" << *field.arrayStrideBytes;
      }
      writeArrayDimensionsJson(out, field.arrayDimensions);
      out << "}";
    }
    out << "]";
  }
  out << "}";
}

std::vector<ReflectionArrayDimension> toReflectionArrayDimensions(
    const std::vector<StorageArrayDimension> &dimensions) {
  std::vector<ReflectionArrayDimension> reflected;
  reflected.reserve(dimensions.size());
  for (const StorageArrayDimension &dimension : dimensions) {
    reflected.push_back(ReflectionArrayDimension{
        dimension.source, dimension.kind, dimension.elementCount});
  }
  return reflected;
}

std::vector<ReflectionArrayDimension>
reflectionArrayDimensions(const HIRType &type,
                          const std::vector<HIRConstant> &constants) {
  return toReflectionArrayDimensions(storageArrayDimensions(type, constants));
}

std::optional<ReflectionStorageBufferLayout>
reflectionStorageBufferLayoutForResource(
    const HIRResource &resource, StorageLayoutKind layoutKind,
    const std::vector<HIRStruct> &structs,
    const std::vector<HIRConstant> &constants) {
  const std::optional<StorageBufferLayout> storageLayout =
      computeStorageBufferLayoutForResource(resource, layoutKind, structs,
                                            constants);
  if (!storageLayout.has_value()) {
    return std::nullopt;
  }

  ReflectionStorageBufferLayout layout;
  layout.elementType = formatType(storageLayout->elementType);
  layout.elementSizeBytes = storageLayout->elementSizeBytes;
  layout.arrayStrideBytes = storageLayout->arrayStrideBytes;
  layout.layout = storageLayout->layout;
  layout.alignmentBytes = storageLayout->alignmentBytes;
  layout.supportsScalarLayout = storageLayout->supportsScalarLayout;
  for (const StorageFieldLayout &field : storageLayout->fields) {
    layout.fields.push_back(ReflectionStorageBufferFieldLayout{
        field.name, formatType(field.type), field.offsetBytes, field.sizeBytes,
        field.storageSizeBytes, field.alignmentBytes, field.arrayElementCount,
        field.arrayStrideBytes,
        toReflectionArrayDimensions(field.arrayDimensions)});
  }
  return layout;
}

struct ManualTextureCompareUsage {
  std::set<std::string> depthTextures;
  std::set<std::string> rawSamplers;
};

std::optional<std::string>
resourceReferenceBaseName(const HIRExpression &expression) {
  if (expression.kind == HIRExpressionKind::Identifier &&
      !expression.value.empty()) {
    return expression.value;
  }
  if ((expression.kind == HIRExpressionKind::IndexAccess ||
       expression.kind == HIRExpressionKind::Group ||
       expression.kind == HIRExpressionKind::NonUniform) &&
      !expression.children.empty()) {
    return resourceReferenceBaseName(expression.children.front());
  }
  return std::nullopt;
}

ManualTextureCompareUsage manualTextureCompareUsage(const HIRModule &module) {
  ManualTextureCompareUsage usage;
  auto visitor = [&](const HIRExpression &expression) {
    const std::optional<TextureCompareManualOperands> operands =
        textureCompareManualOperands(expression);
    if (!operands.has_value()) {
      return;
    }
    const std::optional<std::string> textureName =
        resourceReferenceBaseName(*operands->texture);
    if (textureName.has_value()) {
      usage.depthTextures.insert(*textureName);
    }
    const std::optional<std::string> samplerName =
        resourceReferenceBaseName(*operands->sampler);
    if (samplerName.has_value()) {
      usage.rawSamplers.insert(*samplerName);
    }
  };
  visitModuleExpressions(module, visitor, true);
  return usage;
}

ReflectionManualTextureCompareKernelSummary manualTextureCompareKernelSummary(
    const ManualTextureCompareKernelModuleAnalysis &moduleAnalysis) {
  ReflectionManualTextureCompareKernelSummary summary;
  summary.totalCount = moduleAnalysis.kernels.size();
  summary.staticNormalizedCount = moduleAnalysis.staticNormalized.size();
  summary.staticNonNormalizedCount = moduleAnalysis.staticNonNormalized.size();
  summary.staticZeroSumCount = moduleAnalysis.staticZeroSum.size();
  summary.dynamicCount = moduleAnalysis.dynamic.size();
  return summary;
}

std::vector<ReflectionManualTextureCompareKernel> manualTextureCompareKernels(
    const ManualTextureCompareKernelModuleAnalysis &moduleAnalysis) {
  std::vector<ReflectionManualTextureCompareKernel> kernels;
  kernels.reserve(moduleAnalysis.kernels.size());
  for (const ManualTextureCompareKernelOccurrence &occurrence :
       moduleAnalysis.kernels) {
    ReflectionManualTextureCompareKernel kernel;
    kernel.stage = occurrence.stage;
    if (!occurrence.stage.empty() && !occurrence.entryPoint.empty()) {
      kernel.entryPoint = occurrence.stage + "_" + occurrence.entryPoint;
    }
    kernel.function = occurrence.function;
    kernel.operation = occurrence.analysis.sourceOperation;
    kernel.sourceKind =
        manualTextureCompareKernelFormName(occurrence.analysis.form);
    kernel.canonicalOperation = occurrence.analysis.canonicalOperation;
    kernel.compatibilityAlias = occurrence.analysis.compatibilityAlias;
    kernel.weightClass =
        manualTextureCompareKernelWeightClassName(occurrence.weightClass);
    kernel.tapCount = occurrence.analysis.weights.tapCount;
    kernel.weightsStatic = occurrence.analysis.weights.allWeightsStatic;
    if (occurrence.analysis.weights.allWeightsStatic) {
      kernel.weightSum = occurrence.analysis.weights.sum;
    }
    kernel.weightsZeroSum = occurrence.analysis.weights.zeroSum;
    kernel.weightsNormalized = occurrence.analysis.weights.normalized;
    kernels.push_back(std::move(kernel));
  }

  return kernels;
}

std::string reflectionFeatureKey(const ReflectionTargetFeature &feature) {
  return feature.target + "\n" + feature.kind + "\n" + feature.name;
}

bool isReflectionABIFactKind(std::string_view kind) {
  return kind == "addressingModel" || kind == "backend" ||
         kind == "binaryFormat" || kind == "capability" ||
         kind == "memoryModel" || kind == "sourceLanguage" ||
         kind == "targetEnv" || kind == "toolchain" || kind == "validation";
}

void appendReflectionFeature(std::vector<ReflectionTargetFeature> &features,
                             std::set<std::string> &seen,
                             ReflectionTargetFeature feature) {
  if (feature.target.empty() || feature.kind.empty() || feature.name.empty()) {
    return;
  }
  if (!seen.insert(reflectionFeatureKey(feature)).second) {
    return;
  }
  features.push_back(std::move(feature));
}

ReflectionTargetFeature
reflectionFeatureFromABIRecord(const TargetLegalizationABIRecord &record) {
  return ReflectionTargetFeature{targetName(record.target), record.kind,
                                 record.name};
}

std::optional<ReflectionTargetFeature>
reflectionFeatureFromCapabilityId(std::string_view capabilityId) {
  const std::size_t targetDelimiter = capabilityId.find('.');
  if (targetDelimiter == std::string_view::npos) {
    return std::nullopt;
  }
  const std::size_t kindBegin = targetDelimiter + 1;
  const std::size_t kindDelimiter = capabilityId.find('.', kindBegin);
  if (kindDelimiter == std::string_view::npos) {
    return std::nullopt;
  }

  ReflectionTargetFeature feature;
  feature.target = std::string(capabilityId.substr(0, targetDelimiter));
  feature.kind =
      std::string(capabilityId.substr(kindBegin, kindDelimiter - kindBegin));
  feature.name = std::string(capabilityId.substr(kindDelimiter + 1));
  return feature;
}

const TargetLegalizationABIRecord *findABIRecord(
    const std::vector<TargetLegalizationABIRecord> &records,
    const ReflectionTargetFeature &feature) {
  for (const TargetLegalizationABIRecord &record : records) {
    if (targetName(record.target) == feature.target &&
        record.kind == feature.kind && record.name == feature.name) {
      return &record;
    }
  }
  return nullptr;
}

void appendReflectionFeatureFromCapabilityId(
    std::vector<ReflectionTargetFeature> &features, std::set<std::string> &seen,
    std::string_view capabilityId,
    const std::vector<TargetLegalizationABIRecord> &abiRecords) {
  std::optional<ReflectionTargetFeature> feature =
      reflectionFeatureFromCapabilityId(capabilityId);
  if (!feature.has_value()) {
    return;
  }
  if (isReflectionABIFactKind(feature->kind)) {
    if (const TargetLegalizationABIRecord *record =
            findABIRecord(abiRecords, *feature)) {
      appendReflectionFeature(features, seen,
                              reflectionFeatureFromABIRecord(*record));
      return;
    }
  }
  appendReflectionFeature(features, seen, std::move(*feature));
}

void appendReflectionFeaturesFromABIRecords(
    std::vector<ReflectionTargetFeature> &features, std::set<std::string> &seen,
    const std::vector<TargetLegalizationABIRecord> &records) {
  for (const TargetLegalizationABIRecord &record : records) {
    appendReflectionFeature(features, seen,
                            reflectionFeatureFromABIRecord(record));
  }
}

void applyManualUsageRoles(ReflectionTargetResourceBinding &binding,
                           const ManualTextureCompareUsage &usage) {
  if (usage.depthTextures.count(binding.name) != 0) {
    binding.usageRoles.push_back("manual-depth-texture");
  }
  if (usage.rawSamplers.count(binding.name) != 0) {
    binding.usageRoles.push_back("manual-raw-sampler");
  }
}

void applyCommonTargetResourceBinding(
    ReflectionTargetResourceBinding &binding,
    const BackendPlanResource &resource,
    const std::vector<HIRConstant> &constants) {
  binding.stage = resource.stage;
  binding.entryPoint = resource.backendEntryPoint;
  binding.name = resource.name;
  binding.kind = resource.kindName;
  binding.sourceType = resource.sourceType;
  binding.storageImageFormat = resource.storageImageFormat;
  if (resource.kindName == "storage_image") {
    binding.storageImageAccess =
        storageImageAccessName(resource.storageImageAccess);
  }
  binding.arraySize = resource.arraySize;
  binding.arrayDimensions = reflectionArrayDimensions(resource.type, constants);
  if (resource.hasArray) {
    binding.arrayElementCount =
        storageArrayElementCount(resource.type, constants);
  }
}

std::string reflectionResourceBindingIdentity(TargetKind target,
                                              std::string_view stage,
                                              std::string_view entryPoint,
                                              std::string_view name) {
  std::ostringstream out;
  out << "target '" << targetName(target) << "' stage '" << stage
      << "' entryPoint '" << entryPoint << "' resource '" << name << "'";
  return out.str();
}

std::string reflectionResourceBindingIdentity(
    const BackendPlanResource &resource, TargetKind target) {
  return reflectionResourceBindingIdentity(
      target, resource.stage, resource.backendEntryPoint, resource.name);
}

std::string reflectionResourceBindingIdentity(
    const TargetLegalizationResourceBindingRecord &record) {
  return reflectionResourceBindingIdentity(record.target, record.stage,
                                           record.backendEntryPoint,
                                           record.name);
}

std::string optionalSizeForDiagnostic(std::optional<std::size_t> value) {
  if (!value.has_value()) {
    return "<none>";
  }
  return std::to_string(*value);
}

std::string optionalStringForDiagnostic(
    const std::optional<std::string> &value) {
  if (!value.has_value()) {
    return "<none>";
  }
  return "'" + *value + "'";
}

class ReflectionResourceBindingProjectionError : public std::runtime_error {
public:
  using std::runtime_error::runtime_error;
};

[[noreturn]] void throwReflectionResourceBindingProjectionError(
    std::string detail) {
  throw ReflectionResourceBindingProjectionError(
      "reflection target resource binding projection failed: " +
      std::move(detail));
}

bool legalizationResourceBindingMatchesPlanIdentity(
    const TargetLegalizationResourceBindingRecord &record,
    const BackendPlanResource &resource, TargetKind target) {
  return record.target == target && record.stage == resource.stage &&
         record.sourceEntryPoint == resource.entryPoint &&
         record.backendEntryPoint == resource.backendEntryPoint &&
         record.name == resource.name;
}

std::size_t countLegalizationResourceBindingMatches(
    const TargetLegalizationResourceBindingFacts &resourceBindings,
    const BackendPlanResource &resource, TargetKind target) {
  return static_cast<std::size_t>(std::count_if(
      resourceBindings.records.begin(), resourceBindings.records.end(),
      [&](const TargetLegalizationResourceBindingRecord &record) {
        return legalizationResourceBindingMatchesPlanIdentity(record, resource,
                                                              target);
      }));
}

const TargetLegalizationResourceBindingRecord *findLegalizationResourceBinding(
    const TargetLegalizationResourceBindingFacts &resourceBindings,
    const BackendPlanResource &resource, TargetKind target) {
  for (const TargetLegalizationResourceBindingRecord &record :
       resourceBindings.records) {
    if (legalizationResourceBindingMatchesPlanIdentity(record, resource,
                                                       target)) {
      return &record;
    }
  }
  return nullptr;
}

void requireLegalizationResourceBindingMatchesResource(
    const TargetLegalizationResourceBindingRecord &record,
    const BackendPlanResource &resource, TargetKind target) {
  const std::string identity = reflectionResourceBindingIdentity(resource, target);
  auto requireStringField = [&](std::string_view field,
                                std::string_view expected,
                                std::string_view actual) {
    if (expected != actual) {
      throwReflectionResourceBindingProjectionError(
          identity + " " + std::string(field) + " mismatch: expected '" +
          std::string(expected) + "', got '" + std::string(actual) + "'");
    }
  };
  requireStringField("kind", resource.kindName, record.kind);
  requireStringField("sourceType", resource.sourceType, record.sourceType);
  if (record.storageImageFormat != resource.storageImageFormat) {
    throwReflectionResourceBindingProjectionError(
        identity + " storageImageFormat mismatch: expected " +
        optionalStringForDiagnostic(resource.storageImageFormat) + ", got " +
        optionalStringForDiagnostic(record.storageImageFormat));
  }
  const std::optional<std::string> expectedStorageImageAccess =
      resource.kindName == "storage_image"
          ? std::optional<std::string>(
                storageImageAccessName(resource.storageImageAccess))
          : std::nullopt;
  if (record.storageImageAccess != expectedStorageImageAccess) {
    throwReflectionResourceBindingProjectionError(
        identity + " storageImageAccess mismatch: expected " +
        optionalStringForDiagnostic(expectedStorageImageAccess) + ", got " +
        optionalStringForDiagnostic(record.storageImageAccess));
  }
  if (resource.hasInterfaceBinding) {
    if (record.set != std::optional<std::size_t>{resource.set}) {
      throwReflectionResourceBindingProjectionError(
          identity + " set mismatch: expected " +
          std::to_string(resource.set) + ", got " +
          optionalSizeForDiagnostic(record.set));
    }
    if (record.binding != std::optional<std::size_t>{resource.binding}) {
      throwReflectionResourceBindingProjectionError(
          identity + " binding mismatch: expected " +
          std::to_string(resource.binding) + ", got " +
          optionalSizeForDiagnostic(record.binding));
    }
  } else if (record.set.has_value() || record.binding.has_value()) {
    throwReflectionResourceBindingProjectionError(
        identity + " source coordinate mismatch: expected no set/binding, got "
        "set " +
        optionalSizeForDiagnostic(record.set) + ", binding " +
        optionalSizeForDiagnostic(record.binding));
  }
}

void validateReflectionResourceBindingProjection(
    const BackendPlan &plan,
    const TargetLegalizationResourceBindingFacts &resourceBindings,
    TargetKind target) {
  if (target == TargetKind::Auto) {
    throwReflectionResourceBindingProjectionError(
        "resolved target is 'auto'");
  }
  if (resourceBindings.target != target) {
    throwReflectionResourceBindingProjectionError(
        "resource binding facts target mismatch: expected '" +
        std::string(targetName(target)) + "', got '" +
        std::string(targetName(resourceBindings.target)) + "'");
  }
  if (!resourceBindings.complete) {
    throwReflectionResourceBindingProjectionError(
        "resource binding facts incomplete for target '" +
        std::string(targetName(target)) + "'");
  }

  for (const BackendPlanStageInterface &plannedStage : plan.stages) {
    if (plannedStage.source == nullptr) {
      continue;
    }
    for (const BackendPlanResource &resource : plannedStage.resources) {
      if (resource.source == nullptr || !resource.emitsTargetBinding) {
        continue;
      }
      const std::size_t matchCount =
          countLegalizationResourceBindingMatches(resourceBindings, resource,
                                                  target);
      const std::string identity =
          reflectionResourceBindingIdentity(resource, target);
      if (matchCount == 0) {
        throwReflectionResourceBindingProjectionError(
            "missing legalization resource binding for " + identity);
      }
      if (matchCount > 1) {
        throwReflectionResourceBindingProjectionError(
            "duplicate legalization resource binding for " + identity);
      }
      const TargetLegalizationResourceBindingRecord *record =
          findLegalizationResourceBinding(resourceBindings, resource, target);
      if (record != nullptr) {
        requireLegalizationResourceBindingMatchesResource(*record, resource,
                                                          target);
      }
    }
  }

  for (const TargetLegalizationResourceBindingRecord &record :
       resourceBindings.records) {
    bool matchedPlanResource = false;
    for (const BackendPlanStageInterface &plannedStage : plan.stages) {
      if (plannedStage.source == nullptr) {
        continue;
      }
      for (const BackendPlanResource &resource : plannedStage.resources) {
        if (resource.source != nullptr && resource.emitsTargetBinding &&
            legalizationResourceBindingMatchesPlanIdentity(record, resource,
                                                           target)) {
          matchedPlanResource = true;
          break;
        }
      }
      if (matchedPlanResource) {
        break;
      }
    }
    if (!matchedPlanResource) {
      throwReflectionResourceBindingProjectionError(
          "orphan legalization resource binding for " +
          reflectionResourceBindingIdentity(record));
    }
  }
}

void writeReflectionJson(std::ostringstream &out,
                         const ReflectionDocument &document) {
  out << "{\n"
      << "  \"schemaVersion\": " << document.schemaVersion << ",\n"
      << "  \"module\": \"" << escapeJson(document.module) << "\",\n"
      << "  \"target\": \"" << escapeJson(document.target) << "\",\n"
      << "  \"nativeBinary\": \"" << escapeJson(document.nativeBinary)
      << "\",\n";
  if (!document.legalizationCoreEvidenceIds.empty()) {
    out << "  \"legalizationCoreEvidenceIds\": ";
    writeJsonStringArray(out, document.legalizationCoreEvidenceIds);
    out << ",\n";
  }

  out << "  \"entryPoints\": [";
  for (std::size_t i = 0; i < document.entryPoints.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const ReflectionEntryPoint &entry = document.entryPoints[i];
    out << "\n    {\n"
        << "      \"stage\": \"" << escapeJson(entry.stage) << "\",\n"
        << "      \"sourceName\": \"" << escapeJson(entry.sourceName) << "\",\n"
        << "      \"backendName\": \"" << escapeJson(entry.backendName)
        << "\",\n"
        << "      \"returnType\": \"" << escapeJson(entry.returnType) << "\",\n"
        << "      \"parameters\": [";
    for (std::size_t j = 0; j < entry.parameters.size(); ++j) {
      if (j != 0) {
        out << ",";
      }
      writeReflectionParameterJson(out, entry.parameters[j]);
    }
    out << "]\n    }";
  }
  if (!document.entryPoints.empty()) {
    out << "\n  ";
  }
  out << "],\n";

  out << "  \"structs\": [";
  for (std::size_t i = 0; i < document.structs.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const ReflectionStruct &structure = document.structs[i];
    out << "\n    {\"name\":\"" << escapeJson(structure.name)
        << "\",\"fields\":[";
    for (std::size_t j = 0; j < structure.fields.size(); ++j) {
      if (j != 0) {
        out << ",";
      }
      writeReflectionFieldJson(out, structure.fields[j]);
    }
    out << "]}";
  }
  if (!document.structs.empty()) {
    out << "\n  ";
  }
  out << "],\n";

  out << "  \"resources\": [";
  for (std::size_t i = 0; i < document.resources.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const ReflectionResource &resource = document.resources[i];
    out << "\n    {"
        << "\"stage\":\"" << escapeJson(resource.stage) << "\","
        << "\"name\":\"" << escapeJson(resource.name) << "\","
        << "\"kind\":\"" << escapeJson(resource.kind) << "\","
        << "\"type\":\"" << escapeJson(resource.type) << "\"";
    if (resource.addressSpace.has_value()) {
      out << ",\"addressSpace\":\"" << escapeJson(*resource.addressSpace)
          << "\"";
    }
    if (resource.storageImageFormat.has_value()) {
      out << ",\"storageImageFormat\":\""
          << escapeJson(*resource.storageImageFormat) << "\"";
    }
    if (resource.storageImageAccess.has_value()) {
      out << ",\"storageImageAccess\":\""
          << escapeJson(*resource.storageImageAccess) << "\"";
    }
    writeArrayDimensionsJson(out, resource.arrayDimensions);
    if (resource.set.has_value()) {
      out << ",\"set\":" << *resource.set;
    }
    if (resource.binding.has_value()) {
      out << ",\"binding\":" << *resource.binding;
    }
    out << "}";
  }
  if (!document.resources.empty()) {
    out << "\n  ";
  }
  out << "],\n";

  out << "  \"targetResourceBindings\": [";
  for (std::size_t i = 0; i < document.targetResourceBindings.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const ReflectionTargetResourceBinding &binding =
        document.targetResourceBindings[i];
    out << "\n    {"
        << "\"target\":\"" << escapeJson(binding.target) << "\","
        << "\"stage\":\"" << escapeJson(binding.stage) << "\","
        << "\"entryPoint\":\"" << escapeJson(binding.entryPoint) << "\","
        << "\"name\":\"" << escapeJson(binding.name) << "\","
        << "\"kind\":\"" << escapeJson(binding.kind) << "\","
        << "\"sourceType\":\"" << escapeJson(binding.sourceType) << "\",";
    if (binding.metalType.has_value()) {
      out << "\"metalType\":\"" << escapeJson(*binding.metalType) << "\",";
    }
    if (binding.hlslType.has_value()) {
      out << "\"hlslType\":\"" << escapeJson(*binding.hlslType) << "\",";
    }
    out << "\"addressSpace\":\"" << escapeJson(binding.addressSpace) << "\","
        << "\"abi\":\"" << escapeJson(binding.abi) << "\","
        << "\"bindingClass\":\"" << escapeJson(binding.bindingClass) << "\","
        << "\"evidenceId\":\"" << escapeJson(binding.evidenceId) << "\"";
    if (binding.descriptorType.has_value()) {
      out << ",\"descriptorType\":\"" << escapeJson(*binding.descriptorType)
          << "\"";
    }
    if (binding.storageClass.has_value()) {
      out << ",\"storageClass\":\"" << escapeJson(*binding.storageClass)
          << "\"";
    }
    if (binding.spirvType.has_value()) {
      out << ",\"spirvType\":\"" << escapeJson(*binding.spirvType) << "\"";
    }
    if (binding.storageImageFormat.has_value()) {
      out << ",\"storageImageFormat\":\""
          << escapeJson(*binding.storageImageFormat) << "\"";
    }
    if (binding.storageImageAccess.has_value()) {
      out << ",\"storageImageAccess\":\""
          << escapeJson(*binding.storageImageAccess) << "\"";
    }
    if (!binding.usageRoles.empty()) {
      out << ",\"usageRoles\":[";
      for (std::size_t roleIndex = 0; roleIndex < binding.usageRoles.size();
           ++roleIndex) {
        if (roleIndex != 0) {
          out << ",";
        }
        out << "\"" << escapeJson(binding.usageRoles[roleIndex]) << "\"";
      }
      out << "]";
    }
    if (binding.argumentIndex.has_value()) {
      out << ",\"argumentIndex\":" << *binding.argumentIndex;
    }
    if (binding.set.has_value()) {
      out << ",\"set\":" << *binding.set;
    }
    if (binding.binding.has_value()) {
      out << ",\"binding\":" << *binding.binding;
    }
    if (binding.arraySize.has_value()) {
      out << ",\"arraySize\":\"" << escapeJson(*binding.arraySize) << "\"";
    }
    if (binding.arrayElementCount.has_value()) {
      out << ",\"arrayElementCount\":" << *binding.arrayElementCount;
    }
    writeArrayDimensionsJson(out, binding.arrayDimensions);
    if (binding.storageBufferLayout.has_value()) {
      out << ",\"storageBufferLayout\":";
      writeStorageBufferLayoutJson(out, *binding.storageBufferLayout);
    }
    out << "}";
  }
  if (!document.targetResourceBindings.empty()) {
    out << "\n  ";
  }
  out << "],\n";

  out << "  \"pushConstants\": [],\n";
  out << "  \"functionConstants\": [";
  for (std::size_t i = 0; i < document.functionConstants.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const ReflectionFunctionConstant &constant = document.functionConstants[i];
    out << "\n    {\"name\":\"" << escapeJson(constant.name) << "\",\"type\":\""
        << escapeJson(constant.type) << "\"";
    if (constant.value.has_value()) {
      out << ",\"value\":\"" << escapeJson(*constant.value) << "\"";
    }
    out << "}";
  }
  if (!document.functionConstants.empty()) {
    out << "\n  ";
  }
  out << "],\n";

  out << "  \"vertexLayouts\": [";
  for (std::size_t i = 0; i < document.vertexLayouts.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const ReflectionVertexLayout &layout = document.vertexLayouts[i];
    out << "\n    {\"entryPoint\":\"" << escapeJson(layout.entryPoint)
        << "\",\"attributes\":[";
    for (std::size_t j = 0; j < layout.attributes.size(); ++j) {
      if (j != 0) {
        out << ",";
      }
      const ReflectionVertexAttribute &attribute = layout.attributes[j];
      out << "{\"name\":\"" << escapeJson(attribute.name) << "\",\"type\":\""
          << escapeJson(attribute.type)
          << "\",\"location\":" << attribute.location << "}";
    }
    out << "]}";
  }
  if (!document.vertexLayouts.empty()) {
    out << "\n  ";
  }
  out << "],\n";

  out << "  \"workgroupSizes\": [";
  for (std::size_t i = 0; i < document.workgroupSizes.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const ReflectionWorkgroupSize &size = document.workgroupSizes[i];
    out << "\n    {\"stage\":\"" << escapeJson(size.stage)
        << "\",\"entryPoint\":\"" << escapeJson(size.entryPoint)
        << "\",\"x\":\"" << escapeJson(size.x) << "\",\"y\":\""
        << escapeJson(size.y) << "\",\"z\":\"" << escapeJson(size.z)
        << "\",\"sourceX\":\"" << escapeJson(size.sourceX)
        << "\",\"sourceY\":\"" << escapeJson(size.sourceY)
        << "\",\"sourceZ\":\"" << escapeJson(size.sourceZ) << "\"}";
  }
  if (!document.workgroupSizes.empty()) {
    out << "\n  ";
  }
  out << "],\n";

  out << "  \"manualTextureCompareKernelSummary\": {"
      << "\"totalCount\":"
      << document.manualTextureCompareKernelSummary.totalCount
      << ",\"staticNormalizedCount\":"
      << document.manualTextureCompareKernelSummary.staticNormalizedCount
      << ",\"staticNonNormalizedCount\":"
      << document.manualTextureCompareKernelSummary.staticNonNormalizedCount
      << ",\"staticZeroSumCount\":"
      << document.manualTextureCompareKernelSummary.staticZeroSumCount
      << ",\"dynamicCount\":"
      << document.manualTextureCompareKernelSummary.dynamicCount << "},\n";

  out << "  \"manualTextureCompareKernels\": [";
  for (std::size_t i = 0; i < document.manualTextureCompareKernels.size();
       ++i) {
    if (i != 0) {
      out << ",";
    }
    const ReflectionManualTextureCompareKernel &kernel =
        document.manualTextureCompareKernels[i];
    out << "\n    {\"stage\":\"" << escapeJson(kernel.stage)
        << "\",\"entryPoint\":\"" << escapeJson(kernel.entryPoint)
        << "\",\"function\":\"" << escapeJson(kernel.function)
        << "\",\"operation\":\"" << escapeJson(kernel.operation)
        << "\",\"sourceKind\":\"" << escapeJson(kernel.sourceKind)
        << "\",\"canonicalOperation\":\""
        << escapeJson(kernel.canonicalOperation) << "\",\"compatibilityAlias\":"
        << (kernel.compatibilityAlias ? "true" : "false")
        << ",\"weightClass\":\"" << escapeJson(kernel.weightClass) << "\""
        << ",\"tapCount\":" << kernel.tapCount
        << ",\"weightsStatic\":" << (kernel.weightsStatic ? "true" : "false");
    if (kernel.weightSum.has_value()) {
      out << ",\"weightSum\":" << *kernel.weightSum;
    }
    out << ",\"weightsZeroSum\":" << (kernel.weightsZeroSum ? "true" : "false")
        << ",\"weightsNormalized\":"
        << (kernel.weightsNormalized ? "true" : "false") << "}";
  }
  if (!document.manualTextureCompareKernels.empty()) {
    out << "\n  ";
  }
  out << "],\n";

  out << "  \"targetFeatures\": [";
  for (std::size_t i = 0; i < document.targetFeatures.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const ReflectionTargetFeature &feature = document.targetFeatures[i];
    out << "\n    {\"target\":\"" << escapeJson(feature.target)
        << "\",\"kind\":\"" << escapeJson(feature.kind) << "\",\"name\":\""
        << escapeJson(feature.name) << "\"}";
  }
  if (!document.targetFeatures.empty()) {
    out << "\n  ";
  }
  out << "]\n";
  out << "}\n";
}

} // namespace

std::vector<ReflectionTargetFeature> reflectionTargetFeaturesFromLegalization(
    const TargetLegalizationResult &legalization) {
  return reflectionTargetFeaturesFromLegalization(
      targetLegalizationContract(legalization));
}

std::vector<ReflectionTargetFeature> reflectionTargetFeaturesFromLegalization(
    const TargetLegalizationContract &contract) {
  std::vector<ReflectionTargetFeature> features;
  features.reserve(contract.requiredCapabilityIds.size() +
                   contract.missingCapabilityIds.size() +
                   contract.abiFacts.requiredRecords.size() +
                   contract.abiFacts.missingRecords.size());
  std::set<std::string> seen;
  for (const std::string &capabilityId : contract.requiredCapabilityIds) {
    appendReflectionFeatureFromCapabilityId(
        features, seen, capabilityId, contract.abiFacts.requiredRecords);
  }
  for (const std::string &capabilityId : contract.missingCapabilityIds) {
    appendReflectionFeatureFromCapabilityId(
        features, seen, capabilityId, contract.abiFacts.missingRecords);
  }
  appendReflectionFeaturesFromABIRecords(features, seen,
                                         contract.abiFacts.requiredRecords);
  appendReflectionFeaturesFromABIRecords(features, seen,
                                         contract.abiFacts.missingRecords);
  return features;
}

ReflectionTargetResourceBinding reflectionTargetResourceBindingFromLegalization(
    const TargetLegalizationResourceBindingRecord &record) {
  ReflectionTargetResourceBinding binding;
  binding.target = targetName(record.target);
  binding.stage = record.stage;
  binding.entryPoint = record.backendEntryPoint;
  binding.name = record.name;
  binding.kind = record.kind;
  binding.sourceType = record.sourceType;
  binding.addressSpace = record.addressSpace;
  binding.abi = record.abi;
  binding.bindingClass = record.bindingClass;
  binding.evidenceId = record.evidenceId;
  binding.metalType = record.metalType;
  binding.hlslType = record.hlslType;
  binding.descriptorType = record.descriptorType;
  binding.storageClass = record.storageClass;
  binding.spirvType = record.spirvType;
  binding.storageImageFormat = record.storageImageFormat;
  binding.storageImageAccess = record.storageImageAccess;
  binding.argumentIndex = record.argumentIndex;
  binding.set = record.set;
  binding.binding = record.binding;
  return binding;
}

std::vector<ReflectionTargetResourceBinding>
reflectionTargetResourceBindingsFromLegalization(
    const TargetLegalizationResourceBindingFacts &resourceBindings) {
  std::vector<ReflectionTargetResourceBinding> bindings;
  bindings.reserve(resourceBindings.records.size());
  for (const TargetLegalizationResourceBindingRecord &record :
       resourceBindings.records) {
    bindings.push_back(reflectionTargetResourceBindingFromLegalization(record));
  }
  return bindings;
}

ReflectionDocument
buildReflectionDocument(const HIRModule &module, TargetKind target,
                        const std::filesystem::path &nativeBinaryPath) {
  const TargetLegalizationResult legalization = legalizeTarget(module, target);
  const TargetLegalizationContract contract =
      targetLegalizationContract(legalization);
  return buildReflectionDocument(module, contract, nativeBinaryPath);
}

ReflectionDocument
buildReflectionDocument(const HIRModule &module,
                        const TargetLegalizationContract &contract,
                        const std::filesystem::path &nativeBinaryPath) {
  const TargetKind target = contract.resolvedTarget;
  const std::vector<std::string> contractDiagnostics =
      targetLegalizationContractInvariantDiagnostics(contract);
  if (!contractDiagnostics.empty()) {
    throwReflectionResourceBindingProjectionError(
        "target legalization contract invariant drift: " +
        contractDiagnostics.front());
  }

  ReflectionDocument document;
  document.module = module.name;
  document.target = targetName(target);
  document.nativeBinary = nativeBinaryPath.generic_string();
  const TargetLegalizationContractProjection projection =
      targetLegalizationContractProjection(contract);
  document.legalizationCoreEvidenceIds = projection.coreEvidenceIds;
  document.targetFeatures = reflectionTargetFeaturesFromLegalization(contract);
  const ManualTextureCompareKernelModuleAnalysis manualKernelAnalysis =
      manualTextureCompareKernelModuleAnalysis(module);
  document.manualTextureCompareKernelSummary =
      manualTextureCompareKernelSummary(manualKernelAnalysis);
  document.manualTextureCompareKernels =
      manualTextureCompareKernels(manualKernelAnalysis);
  const ManualTextureCompareUsage manualUsage =
      manualTextureCompareUsage(module);
  const BackendPlan backendPlan = buildBackendPlan(module);
  validateReflectionResourceBindingProjection(backendPlan,
                                              contract.resourceBindings, target);

  for (const BackendPlanStageInterface &plannedStage : backendPlan.stages) {
    if (plannedStage.source == nullptr) {
      continue;
    }
    const HIRStage &stage = *plannedStage.source;
    const std::string &backendEntryPoint = plannedStage.backendEntryPoint;
    for (const HIRFunction &function : stage.functions) {
      if (function.name != stage.entryPointName) {
        continue;
      }
      ReflectionEntryPoint entry;
      entry.stage = stage.stage;
      entry.sourceName = function.name;
      entry.backendName = stage.stage + "_" + function.name;
      entry.returnType = formatType(function.returnType);
      for (const HIRParameter &parameter : function.parameters) {
        entry.parameters.push_back(
            ReflectionParameter{parameter.name, formatType(parameter.type)});
      }
      document.entryPoints.push_back(std::move(entry));
    }

    for (const BackendPlanResource &plannedResource : plannedStage.resources) {
      if (plannedResource.source == nullptr) {
        continue;
      }
      const HIRResource &resource = *plannedResource.source;
      ReflectionResource reflected;
      reflected.stage = plannedResource.stage;
      reflected.name = plannedResource.name;
      reflected.kind = plannedResource.kindName;
      reflected.type = plannedResource.sourceType;
      reflected.storageImageFormat = plannedResource.storageImageFormat;
      if (resource.kind == HIRResourceKind::StorageImage) {
        reflected.storageImageAccess =
            storageImageAccessName(resource.storageImageAccess);
      }
      reflected.arrayDimensions =
          reflectionArrayDimensions(plannedResource.type, module.constants);
      if (!plannedResource.hasInterfaceBinding) {
        reflected.addressSpace = "shared";
      } else {
        reflected.set = plannedResource.set;
        reflected.binding = plannedResource.binding;
      }
      document.resources.push_back(std::move(reflected));

      const TargetLegalizationResourceBindingRecord *bindingRecord =
          findLegalizationResourceBinding(contract.resourceBindings,
                                          plannedResource, target);
      if (bindingRecord != nullptr) {
        ReflectionTargetResourceBinding binding =
            reflectionTargetResourceBindingFromLegalization(*bindingRecord);
        applyCommonTargetResourceBinding(binding, plannedResource,
                                         module.constants);
        if (target == TargetKind::Metal &&
            bindingRecord->abi == "kernelArgument") {
          binding.storageBufferLayout =
              reflectionStorageBufferLayoutForResource(
                  resource, StorageLayoutKind::MetalDevice, module.structs,
                  module.constants);
        } else if (target == TargetKind::Vulkan &&
                   bindingRecord->abi == "descriptor") {
          binding.storageBufferLayout =
              reflectionStorageBufferLayoutForResource(
                  resource, StorageLayoutKind::Std430, module.structs,
                  module.constants);
        } else if (target == TargetKind::OpenGL &&
                   bindingRecord->abi == "programResourceBinding") {
          binding.storageBufferLayout =
              reflectionStorageBufferLayoutForResource(
                  resource, StorageLayoutKind::Std430, module.structs,
                  module.constants);
        }
        applyManualUsageRoles(binding, manualUsage);
        document.targetResourceBindings.push_back(std::move(binding));
      }
    }

    if (stage.workgroupSize.has_value()) {
      document.workgroupSizes.push_back(ReflectionWorkgroupSize{
          stage.stage, backendEntryPoint, stage.workgroupSize->x,
          stage.workgroupSize->y, stage.workgroupSize->z,
          stage.workgroupSize->sourceX, stage.workgroupSize->sourceY,
          stage.workgroupSize->sourceZ});
    }
  }

  for (const HIRStruct &structure : module.structs) {
    ReflectionStruct reflected;
    reflected.name = structure.name;
    for (const HIRField &field : structure.fields) {
      reflected.fields.push_back(ReflectionField{
          field.name, formatType(field.type),
          reflectionArrayDimensions(field.type, module.constants)});
    }
    document.structs.push_back(std::move(reflected));
  }

  for (const HIRConstant &constant : module.constants) {
    document.functionConstants.push_back(ReflectionFunctionConstant{
        constant.name, formatType(constant.type), constant.foldedValue});
  }

  for (const HIRStage &stage : module.stages) {
    if (stage.stage != "vertex") {
      continue;
    }
    for (const HIRFunction &function : stage.functions) {
      if (function.name != stage.entryPointName ||
          function.parameters.empty()) {
        continue;
      }
      const std::string inputType = function.parameters.front().type.name;
      auto structure =
          std::find_if(module.structs.begin(), module.structs.end(),
                       [&](const HIRStruct &candidate) {
                         return candidate.name == inputType;
                       });
      if (structure == module.structs.end()) {
        continue;
      }

      ReflectionVertexLayout layout;
      layout.entryPoint = stage.stage + "_" + function.name;
      for (std::size_t i = 0; i < structure->fields.size(); ++i) {
        layout.attributes.push_back(ReflectionVertexAttribute{
            structure->fields[i].name, formatType(structure->fields[i].type),
            i});
      }
      document.vertexLayouts.push_back(std::move(layout));
    }
  }

  return document;
}

std::optional<ReflectionDocument>
buildReflectionDocument(const HIRModule &module, TargetKind target,
                        const std::filesystem::path &nativeBinaryPath,
                        DiagnosticEngine &diagnostics) {
  try {
    return buildReflectionDocument(module, target, nativeBinaryPath);
  } catch (const ReflectionResourceBindingProjectionError &error) {
    diagnostics.error("artifact.reflection-target-resource-binding-projection",
                      error.what());
    return std::nullopt;
  }
}

std::optional<ReflectionDocument>
buildReflectionDocument(const HIRModule &module,
                        const TargetLegalizationContract &contract,
                        const std::filesystem::path &nativeBinaryPath,
                        DiagnosticEngine &diagnostics) {
  try {
    return buildReflectionDocument(module, contract, nativeBinaryPath);
  } catch (const ReflectionResourceBindingProjectionError &error) {
    diagnostics.error("artifact.reflection-target-resource-binding-projection",
                      error.what());
    return std::nullopt;
  }
}

std::string reflectionJson(const HIRModule &module, TargetKind target,
                           const std::filesystem::path &nativeBinaryPath) {
  return reflectionJson(
      buildReflectionDocument(module, target, nativeBinaryPath));
}

std::string reflectionJson(const ReflectionDocument &document) {
  std::ostringstream out;
  writeReflectionJson(out, document);
  return out.str();
}

} // namespace crossgl
