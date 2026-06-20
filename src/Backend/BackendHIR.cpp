#include "crossgl/Backend/BackendHIR.h"

#include "crossgl/Backend/Target.h"
#include "crossgl/HIR/HIR.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <algorithm>
#include <limits>
#include <optional>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace crossgl {
namespace {

std::optional<std::size_t> parsePositiveArrayDimension(
    std::string_view text) {
  if (text.empty()) {
    return std::nullopt;
  }

  std::size_t value = 0;
  for (const char character : text) {
    if (character < '0' || character > '9') {
      return std::nullopt;
    }
    const std::size_t digit = static_cast<std::size_t>(character - '0');
    if (value > (std::numeric_limits<std::size_t>::max() - digit) / 10) {
      return std::nullopt;
    }
    value = value * 10 + digit;
  }
  if (value == 0) {
    return std::nullopt;
  }
  return value;
}

std::optional<std::size_t> parseNonNegativeArrayIndex(std::string_view text) {
  if (text.empty()) {
    return std::nullopt;
  }

  std::size_t value = 0;
  for (const char character : text) {
    if (character < '0' || character > '9') {
      return std::nullopt;
    }
    const std::size_t digit = static_cast<std::size_t>(character - '0');
    if (value > (std::numeric_limits<std::size_t>::max() - digit) / 10) {
      return std::nullopt;
    }
    value = value * 10 + digit;
  }
  return value;
}

std::vector<std::string_view> splitArrayDimensions(std::string_view arraySize) {
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

const HIRConstant *findConstant(const HIRModule &module,
                                std::string_view name) {
  for (const HIRConstant &constant : module.constants) {
    if (constant.name == name) {
      return &constant;
    }
  }
  return nullptr;
}

bool isFixedArrayDimension(const HIRModule &module,
                           std::string_view dimension) {
  if (parsePositiveArrayDimension(dimension).has_value()) {
    return true;
  }

  const HIRConstant *constant = findConstant(module, dimension);
  return constant != nullptr && constant->foldedValue.has_value() &&
         !constant->type.arraySize.has_value() &&
         (constant->type.name == "int" || constant->type.name == "uint") &&
         parsePositiveArrayDimension(*constant->foldedValue).has_value();
}

void collectFunctionParameterArraysForFunction(
    const HIRModule &module, std::string_view stageName,
    const HIRFunction &function, bool entryPoint,
    std::vector<HIRFunctionParameterArray> &arrays) {
  for (const HIRParameter &parameter : function.parameters) {
    const HIRFunctionParameterArrayShape shape =
        functionParameterArrayShape(module, parameter.type);
    if (shape == HIRFunctionParameterArrayShape::None) {
      continue;
    }
    arrays.push_back(HIRFunctionParameterArray{
        std::string(stageName), function.name, parameter.name, parameter.type,
        shape, entryPoint});
  }
}

void appendFunctionParameterArrayCallFeature(
    std::vector<HIRFunctionParameterArrayCallFeature> &features,
    HIRFunctionParameterArrayCallFeature feature) {
  if (std::find(features.begin(), features.end(), feature) == features.end()) {
    features.push_back(feature);
  }
}

bool isFunctionParameterArrayScalarVectorElementType(std::string_view name) {
  return name == "bool" || isNumericScalarTypeName(name) ||
         isVectorType(name);
}

bool functionParameterArrayHasFoldedConstantDimension(
    const HIRModule &module, const HIRType &type) {
  if (!type.arraySize.has_value()) {
    return false;
  }
  for (std::string_view dimension : splitArrayDimensions(*type.arraySize)) {
    if (!parsePositiveArrayDimension(dimension).has_value() &&
        isFixedArrayDimension(module, dimension)) {
      return true;
    }
  }
  return false;
}

const HIRExpression *
unwrapFunctionParameterArrayTransparentExpression(
    const HIRExpression &expression);

bool functionParameterArrayIndexIsStatic(const HIRModule &module,
                                         const HIRExpression &expression) {
  const HIRExpression *unwrapped =
      unwrapFunctionParameterArrayTransparentExpression(expression);
  if (unwrapped->kind == HIRExpressionKind::Literal) {
    return parseNonNegativeArrayIndex(unwrapped->value).has_value();
  }
  if (unwrapped->kind == HIRExpressionKind::Identifier) {
    const HIRConstant *constant = findConstant(module, unwrapped->value);
    return constant != nullptr && constant->foldedValue.has_value() &&
           !constant->type.arraySize.has_value() &&
           (constant->type.name == "int" || constant->type.name == "uint") &&
           parseNonNegativeArrayIndex(*constant->foldedValue).has_value();
  }
  return false;
}

const HIRExpression *
unwrapFunctionParameterArrayTransparentExpression(
    const HIRExpression &expression) {
  const HIRExpression *current = &expression;
  while ((current->kind == HIRExpressionKind::Group ||
          current->kind == HIRExpressionKind::NonUniform) &&
         current->children.size() == 1) {
    current = &current->children.front();
  }
  return current;
}

const HIRExpression *
functionParameterArrayCallArgumentRoot(const HIRExpression &expression) {
  const HIRExpression *current =
      unwrapFunctionParameterArrayTransparentExpression(expression);
  while ((current->kind == HIRExpressionKind::MemberAccess ||
          current->kind == HIRExpressionKind::IndexAccess) &&
         !current->children.empty()) {
    current =
        unwrapFunctionParameterArrayTransparentExpression(current->children[0]);
  }
  return current;
}

bool functionParameterArrayExpressionContainsFixedArray(
    const HIRModule &module, const HIRExpression &expression) {
  if (functionParameterArrayShape(module, expression.type) ==
      HIRFunctionParameterArrayShape::FixedSize) {
    return true;
  }
  for (const HIRExpression &child : expression.children) {
    if (functionParameterArrayExpressionContainsFixedArray(module, child)) {
      return true;
    }
  }
  return false;
}

std::size_t
functionParameterArrayCallArgumentMemberDepth(const HIRExpression &expression) {
  const HIRExpression *current =
      unwrapFunctionParameterArrayTransparentExpression(expression);
  if (current->children.empty()) {
    return 0;
  }
  if (current->kind == HIRExpressionKind::MemberAccess) {
    return 1 +
           functionParameterArrayCallArgumentMemberDepth(current->children[0]);
  }
  if (current->kind == HIRExpressionKind::IndexAccess) {
    return functionParameterArrayCallArgumentMemberDepth(current->children[0]);
  }
  return 0;
}

void collectFunctionParameterArrayIndexExpressions(
    const HIRExpression &expression,
    std::vector<const HIRExpression *> &indices) {
  const HIRExpression *current =
      unwrapFunctionParameterArrayTransparentExpression(expression);
  if (current->kind != HIRExpressionKind::IndexAccess ||
      current->children.size() < 2) {
    return;
  }
  collectFunctionParameterArrayIndexExpressions(current->children[0], indices);
  indices.push_back(&current->children[1]);
}

bool functionParameterArrayHasDynamicNestedIndex(
    const HIRModule &module, const HIRExpression &expression) {
  std::vector<const HIRExpression *> indices;
  collectFunctionParameterArrayIndexExpressions(expression, indices);
  if (indices.size() <= 1) {
    return false;
  }
  for (const HIRExpression *index : indices) {
    if (index == nullptr ||
        !functionParameterArrayIndexIsStatic(module, *index)) {
      return true;
    }
  }
  return false;
}

const HIRParameter *findFunctionParameter(const HIRFunction &function,
                                          std::string_view name) {
  for (const HIRParameter &parameter : function.parameters) {
    if (parameter.name == name) {
      return &parameter;
    }
  }
  return nullptr;
}

void appendFunctionParameterArrayReadFeaturesInExpression(
    const HIRModule &module, const HIRFunction &function,
    const HIRExpression &expression,
    std::vector<HIRFunctionParameterArrayCallFeature> &features) {
  for (HIRFunctionParameterArrayCallFeature feature :
       functionParameterArrayReadFeatures(module, function, expression)) {
    appendFunctionParameterArrayCallFeature(features, feature);
  }
  for (const HIRExpression &child : expression.children) {
    appendFunctionParameterArrayReadFeaturesInExpression(module, function, child,
                                                        features);
  }
}

void appendFunctionParameterArrayReadFeaturesInStatements(
    const HIRModule &module, const HIRFunction &function,
    std::span<const HIRStatement> statements,
    std::vector<HIRFunctionParameterArrayCallFeature> &features) {
  for (const HIRStatement &statement : statements) {
    appendFunctionParameterArrayReadFeaturesInExpression(
        module, function, statement.value, features);
    for (const HIRStatement &child : statement.initializer) {
      appendFunctionParameterArrayReadFeaturesInStatements(module, function,
                                                           {&child, 1},
                                                           features);
    }
    for (const HIRStatement &child : statement.update) {
      appendFunctionParameterArrayReadFeaturesInStatements(module, function,
                                                           {&child, 1},
                                                           features);
    }
    appendFunctionParameterArrayReadFeaturesInStatements(
        module, function,
        std::span<const HIRStatement>{statement.body.data(),
                                      statement.body.size()},
        features);
    appendFunctionParameterArrayReadFeaturesInStatements(
        module, function,
        std::span<const HIRStatement>{statement.elseBody.data(),
                                      statement.elseBody.size()},
        features);
  }
}

const HIRResource *findStageResource(const HIRStage *stage,
                                     std::string_view name) {
  if (stage == nullptr) {
    return nullptr;
  }
  for (const HIRResource &resource : stage->resources) {
    if (resource.name == name) {
      return &resource;
    }
  }
  return nullptr;
}

bool expressionContainsNonUniformDescriptorMarker(
    const HIRExpression &expression) {
  if (expression.kind == HIRExpressionKind::NonUniform) {
    return true;
  }
  for (const HIRExpression &child : expression.children) {
    if (expressionContainsNonUniformDescriptorMarker(child)) {
      return true;
    }
  }
  return false;
}

void appendNonUniformDescriptorIndexUsesInExpression(
    std::string_view stageName, std::string_view functionName,
    const std::unordered_map<std::string, HIRResource> &resources,
    const HIRExpression &expression,
    std::vector<HIRNonUniformDescriptorIndexUse> &uses) {
  if (expression.kind == HIRExpressionKind::IndexAccess &&
      expression.children.size() >= 2 &&
      expression.children[0].kind == HIRExpressionKind::Identifier &&
      expressionContainsNonUniformDescriptorMarker(expression.children[1])) {
    const auto resource = resources.find(expression.children[0].value);
    if (resource != resources.end() &&
        resource->second.type.arraySize.has_value() &&
        resource->second.kind != HIRResourceKind::Shared &&
        resource->second.kind != HIRResourceKind::Value) {
      uses.push_back(HIRNonUniformDescriptorIndexUse{
          std::string(stageName),
          std::string(functionName),
          resource->second.name,
          resource->second.kind,
          nonUniformDescriptorResourceFamily(resource->second.kind),
          resource->second.type,
      });
    }
  }

  for (const HIRExpression &child : expression.children) {
    appendNonUniformDescriptorIndexUsesInExpression(stageName, functionName,
                                                    resources, child, uses);
  }
}

void appendNonUniformDescriptorIndexUsesInStatement(
    std::string_view stageName, std::string_view functionName,
    const std::unordered_map<std::string, HIRResource> &resources,
    const HIRStatement &statement,
    std::vector<HIRNonUniformDescriptorIndexUse> &uses) {
  appendNonUniformDescriptorIndexUsesInExpression(stageName, functionName,
                                                  resources, statement.target,
                                                  uses);
  appendNonUniformDescriptorIndexUsesInExpression(stageName, functionName,
                                                  resources, statement.value,
                                                  uses);
  for (const HIRStatement &initializer : statement.initializer) {
    appendNonUniformDescriptorIndexUsesInStatement(
        stageName, functionName, resources, initializer, uses);
  }
  for (const HIRStatement &update : statement.update) {
    appendNonUniformDescriptorIndexUsesInStatement(stageName, functionName,
                                                   resources, update, uses);
  }
  for (const HIRStatement &child : statement.body) {
    appendNonUniformDescriptorIndexUsesInStatement(stageName, functionName,
                                                   resources, child, uses);
  }
  for (const HIRStatement &child : statement.elseBody) {
    appendNonUniformDescriptorIndexUsesInStatement(stageName, functionName,
                                                   resources, child, uses);
  }
}

void appendNonUniformDescriptorIndexUsesInFunction(
    std::string_view stageName, const HIRFunction &function,
    const std::unordered_map<std::string, HIRResource> &resources,
    std::vector<HIRNonUniformDescriptorIndexUse> &uses) {
  for (const HIRStatement &statement : function.body) {
    appendNonUniformDescriptorIndexUsesInStatement(
        stageName, function.name, resources, statement, uses);
  }
}

} // namespace

const HIRStruct *findStruct(const HIRModule &module, std::string_view name) {
  for (const HIRStruct &structure : module.structs) {
    if (structure.name == name) {
      return &structure;
    }
  }
  return nullptr;
}

const HIRStage *singleComputeStage(const HIRModule &module) {
  if (module.stages.size() != 1 || module.stages.front().stage != "compute") {
    return nullptr;
  }
  return &module.stages.front();
}

const HIRFunction *entryFunction(const HIRStage &stage) {
  for (const HIRFunction &function : stage.functions) {
    if (function.name == stage.entryPointName) {
      return &function;
    }
  }
  return nullptr;
}

bool isResourceReferenceExpression(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::Identifier ||
         expression.kind == HIRExpressionKind::IndexAccess;
}

HIRNonUniformDescriptorResourceFamily
nonUniformDescriptorResourceFamily(HIRResourceKind kind) {
  switch (kind) {
  case HIRResourceKind::Uniform:
    return HIRNonUniformDescriptorResourceFamily::UniformBuffer;
  case HIRResourceKind::Buffer:
    return HIRNonUniformDescriptorResourceFamily::StorageBuffer;
  case HIRResourceKind::Texture:
    return HIRNonUniformDescriptorResourceFamily::Texture;
  case HIRResourceKind::Sampler:
    return HIRNonUniformDescriptorResourceFamily::Sampler;
  case HIRResourceKind::StorageImage:
    return HIRNonUniformDescriptorResourceFamily::StorageImage;
  case HIRResourceKind::Shared:
  case HIRResourceKind::Value:
    return HIRNonUniformDescriptorResourceFamily::Other;
  }
  return HIRNonUniformDescriptorResourceFamily::Other;
}

std::string nonUniformDescriptorResourceFamilyName(
    HIRNonUniformDescriptorResourceFamily family) {
  switch (family) {
  case HIRNonUniformDescriptorResourceFamily::UniformBuffer:
    return "uniform-buffer";
  case HIRNonUniformDescriptorResourceFamily::StorageBuffer:
    return "storage-buffer";
  case HIRNonUniformDescriptorResourceFamily::StorageImage:
    return "storage-image";
  case HIRNonUniformDescriptorResourceFamily::Texture:
    return "texture";
  case HIRNonUniformDescriptorResourceFamily::Sampler:
    return "sampler";
  case HIRNonUniformDescriptorResourceFamily::Other:
    return "other";
  }
  return "other";
}

std::vector<HIRNonUniformDescriptorIndexUse>
collectNonUniformDescriptorIndexUses(const HIRModule &module) {
  std::vector<HIRNonUniformDescriptorIndexUse> uses;
  for (const HIRStage &stage : module.stages) {
    std::unordered_map<std::string, HIRResource> resources;
    for (const HIRResource &resource : stage.resources) {
      resources.emplace(resource.name, resource);
    }
    for (const HIRFunction &function : stage.functions) {
      appendNonUniformDescriptorIndexUsesInFunction(stage.stage, function,
                                                    resources, uses);
    }
  }
  return uses;
}

HIRFunctionParameterArrayShape
functionParameterArrayShape(const HIRModule &module, const HIRType &type) {
  if (!type.arraySize.has_value()) {
    return HIRFunctionParameterArrayShape::None;
  }
  if (type.arraySize->empty()) {
    return HIRFunctionParameterArrayShape::RuntimeSize;
  }
  for (std::string_view dimension : splitArrayDimensions(*type.arraySize)) {
    if (!isFixedArrayDimension(module, dimension)) {
      return HIRFunctionParameterArrayShape::UnresolvedSize;
    }
  }
  return HIRFunctionParameterArrayShape::FixedSize;
}

std::vector<HIRFunctionParameterArray>
collectFunctionParameterArrays(const HIRModule &module) {
  std::vector<HIRFunctionParameterArray> arrays;
  for (const HIRFunction &function : module.functions) {
    collectFunctionParameterArraysForFunction(module, "", function, false,
                                              arrays);
  }
  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &function : stage.functions) {
      const bool isEntryPoint = function.name == stage.entryPointName;
      collectFunctionParameterArraysForFunction(module, stage.stage, function,
                                                isEntryPoint, arrays);
    }
  }
  return arrays;
}

std::string functionParameterArrayShapeName(
    HIRFunctionParameterArrayShape shape) {
  switch (shape) {
  case HIRFunctionParameterArrayShape::None:
    return "none";
  case HIRFunctionParameterArrayShape::FixedSize:
    return "fixed-size";
  case HIRFunctionParameterArrayShape::RuntimeSize:
    return "runtime-size";
  case HIRFunctionParameterArrayShape::UnresolvedSize:
    return "unresolved-size";
  }
  return "unknown";
}

HIRFunctionParameterArrayTargetSupport functionParameterArrayTargetSupport(
    TargetKind target, const HIRFunctionParameterArray &array) {
  switch (array.shape) {
  case HIRFunctionParameterArrayShape::None:
    return HIRFunctionParameterArrayTargetSupport::Supported;
  case HIRFunctionParameterArrayShape::RuntimeSize:
    return HIRFunctionParameterArrayTargetSupport::UnsupportedRuntimeSize;
  case HIRFunctionParameterArrayShape::UnresolvedSize:
    return HIRFunctionParameterArrayTargetSupport::UnsupportedUnresolvedSize;
  case HIRFunctionParameterArrayShape::FixedSize:
    break;
  }

  const TargetKind resolvedTarget =
      target == TargetKind::Auto ? defaultTargetForHost() : target;
  switch (resolvedTarget) {
  case TargetKind::DirectX:
  case TargetKind::OpenGL:
  case TargetKind::Metal:
    return array.entryPoint
               ? HIRFunctionParameterArrayTargetSupport::UnsupportedEntryPoint
               : HIRFunctionParameterArrayTargetSupport::Supported;
  case TargetKind::Vulkan:
    return HIRFunctionParameterArrayTargetSupport::UnsupportedTarget;
  case TargetKind::WGSL:
    return HIRFunctionParameterArrayTargetSupport::UnsupportedTarget;
  case TargetKind::Auto:
    break;
  }
  return HIRFunctionParameterArrayTargetSupport::UnsupportedTarget;
}

std::string functionParameterArrayTargetSupportName(
    HIRFunctionParameterArrayTargetSupport support) {
  switch (support) {
  case HIRFunctionParameterArrayTargetSupport::Supported:
    return "supported";
  case HIRFunctionParameterArrayTargetSupport::UnsupportedEntryPoint:
    return "unsupported-entry-point";
  case HIRFunctionParameterArrayTargetSupport::UnsupportedRuntimeSize:
    return "unsupported-runtime-size";
  case HIRFunctionParameterArrayTargetSupport::UnsupportedUnresolvedSize:
    return "unsupported-unresolved-size";
  case HIRFunctionParameterArrayTargetSupport::UnsupportedTarget:
    return "unsupported-target";
  }
  return "unknown";
}

HIRFunctionParameterArrayCallSemantics functionParameterArrayCallSemantics() {
  return HIRFunctionParameterArrayCallSemantics::ValueCopyReadOnly;
}

std::string functionParameterArrayCallSemanticsName(
    HIRFunctionParameterArrayCallSemantics semantics) {
  switch (semantics) {
  case HIRFunctionParameterArrayCallSemantics::ValueCopyReadOnly:
    return "value-copy-read-only";
  }
  return "unknown";
}

bool functionParameterArrayWritesVisibleToCaller(
    HIRFunctionParameterArrayCallSemantics semantics) {
  switch (semantics) {
  case HIRFunctionParameterArrayCallSemantics::ValueCopyReadOnly:
    return false;
  }
  return false;
}

HIRFunctionParameterArrayWriteTarget functionParameterArrayWriteTarget(
    const HIRModule &module, const HIRFunction &function,
    const HIRExpression &target, const HIRStage *stage) {
  const HIRExpression *root = functionParameterArrayCallArgumentRoot(target);
  if (root == nullptr || root->kind != HIRExpressionKind::Identifier) {
    return HIRFunctionParameterArrayWriteTarget::None;
  }

  const bool touchesFixedArray =
      functionParameterArrayExpressionContainsFixedArray(module, target);
  if (const HIRParameter *parameter =
          findFunctionParameter(function, root->value);
      parameter != nullptr) {
    if (functionParameterArrayShape(module, parameter->type) !=
        HIRFunctionParameterArrayShape::None) {
      return HIRFunctionParameterArrayWriteTarget::ReadOnlyParameterArray;
    }
    return touchesFixedArray ? HIRFunctionParameterArrayWriteTarget::OtherArray
                             : HIRFunctionParameterArrayWriteTarget::None;
  }

  if (findStageResource(stage, root->value) != nullptr) {
    return touchesFixedArray ? HIRFunctionParameterArrayWriteTarget::OtherArray
                             : HIRFunctionParameterArrayWriteTarget::None;
  }

  return touchesFixedArray
             ? HIRFunctionParameterArrayWriteTarget::MutableLocalArray
             : HIRFunctionParameterArrayWriteTarget::None;
}

std::string functionParameterArrayWriteTargetName(
    HIRFunctionParameterArrayWriteTarget target) {
  switch (target) {
  case HIRFunctionParameterArrayWriteTarget::None:
    return "none";
  case HIRFunctionParameterArrayWriteTarget::MutableLocalArray:
    return "mutable-local-array";
  case HIRFunctionParameterArrayWriteTarget::ReadOnlyParameterArray:
    return "read-only-parameter-array";
  case HIRFunctionParameterArrayWriteTarget::OtherArray:
    return "other-array";
  }
  return "unknown";
}

HIRFunctionParameterArrayCallFeatureSupport
functionParameterArrayCallFeatureSupport(
    HIRFunctionParameterArrayCallFeature feature) {
  switch (feature) {
  case HIRFunctionParameterArrayCallFeature::ScalarVectorElements:
  case HIRFunctionParameterArrayCallFeature::MatrixElements:
  case HIRFunctionParameterArrayCallFeature::FixedNestedArrays:
  case HIRFunctionParameterArrayCallFeature::FoldedConstantDimensions:
  case HIRFunctionParameterArrayCallFeature::LocalArrayArguments:
  case HIRFunctionParameterArrayCallFeature::FunctionParameterArguments:
  case HIRFunctionParameterArrayCallFeature::StorageBufferFieldArguments:
  case HIRFunctionParameterArrayCallFeature::NestedStructFieldArguments:
    return HIRFunctionParameterArrayCallFeatureSupport::Supported;
  case HIRFunctionParameterArrayCallFeature::DynamicNestedArrayIndices:
  case HIRFunctionParameterArrayCallFeature::StructElements:
  case HIRFunctionParameterArrayCallFeature::DirectResourceArrayArguments:
    return HIRFunctionParameterArrayCallFeatureSupport::Unsupported;
  }
  return HIRFunctionParameterArrayCallFeatureSupport::Unsupported;
}

HIRFunctionParameterArrayCallFeatureSupport
functionParameterArrayCallFeaturesSupport(
    std::span<const HIRFunctionParameterArrayCallFeature> features) {
  for (HIRFunctionParameterArrayCallFeature feature : features) {
    if (functionParameterArrayCallFeatureSupport(feature) ==
        HIRFunctionParameterArrayCallFeatureSupport::Unsupported) {
      return HIRFunctionParameterArrayCallFeatureSupport::Unsupported;
    }
  }
  return HIRFunctionParameterArrayCallFeatureSupport::Supported;
}

std::vector<HIRFunctionParameterArrayCallFeature>
functionParameterArrayCallUnsupportedFeatures(
    std::span<const HIRFunctionParameterArrayCallFeature> features) {
  std::vector<HIRFunctionParameterArrayCallFeature> unsupported;
  for (HIRFunctionParameterArrayCallFeature feature : features) {
    if (functionParameterArrayCallFeatureSupport(feature) ==
        HIRFunctionParameterArrayCallFeatureSupport::Unsupported) {
      appendFunctionParameterArrayCallFeature(unsupported, feature);
    }
  }
  return unsupported;
}

bool functionParameterArrayCallRequiresRejection(
    std::span<const HIRFunctionParameterArrayCallFeature> features) {
  return !functionParameterArrayCallUnsupportedFeatures(features).empty();
}

std::string functionParameterArrayCallFeatureSupportSummary(
    std::span<const HIRFunctionParameterArrayCallFeature> features) {
  std::vector<HIRFunctionParameterArrayCallFeature> uniqueFeatures;
  for (HIRFunctionParameterArrayCallFeature feature : features) {
    appendFunctionParameterArrayCallFeature(uniqueFeatures, feature);
  }

  const std::span<const HIRFunctionParameterArrayCallFeature> uniqueFeatureSpan{
      uniqueFeatures.data(), uniqueFeatures.size()};
  const HIRFunctionParameterArrayCallFeatureSupport aggregateSupport =
      functionParameterArrayCallFeaturesSupport(uniqueFeatureSpan);
  std::string summary =
      functionParameterArrayCallFeatureSupportName(aggregateSupport) + ": ";
  if (uniqueFeatures.empty()) {
    summary += "none";
    return summary;
  }

  for (std::size_t index = 0; index < uniqueFeatures.size(); ++index) {
    if (index > 0) {
      summary += ", ";
    }
    const HIRFunctionParameterArrayCallFeature feature = uniqueFeatures[index];
    summary += functionParameterArrayCallFeatureName(feature);
    summary += "=";
    summary += functionParameterArrayCallFeatureSupportName(
        functionParameterArrayCallFeatureSupport(feature));
  }
  return summary;
}

std::vector<HIRFunctionParameterArrayCallFeature>
functionParameterArrayCallTypeFeatures(const HIRModule &module,
                                       const HIRType &type) {
  std::vector<HIRFunctionParameterArrayCallFeature> features;
  if (functionParameterArrayShape(module, type) !=
      HIRFunctionParameterArrayShape::FixedSize) {
    return features;
  }

  const std::string baseName = baseTypeName(type);
  if (isMatrixType(baseName)) {
    appendFunctionParameterArrayCallFeature(
        features, HIRFunctionParameterArrayCallFeature::MatrixElements);
  } else if (findStruct(module, baseName) != nullptr) {
    appendFunctionParameterArrayCallFeature(
        features, HIRFunctionParameterArrayCallFeature::StructElements);
  } else if (isFunctionParameterArrayScalarVectorElementType(baseName)) {
    appendFunctionParameterArrayCallFeature(
        features, HIRFunctionParameterArrayCallFeature::ScalarVectorElements);
  }

  if (type.arraySize.has_value() &&
      splitArrayDimensions(*type.arraySize).size() > 1) {
    appendFunctionParameterArrayCallFeature(
        features, HIRFunctionParameterArrayCallFeature::FixedNestedArrays);
  }
  if (functionParameterArrayHasFoldedConstantDimension(module, type)) {
    appendFunctionParameterArrayCallFeature(
        features,
        HIRFunctionParameterArrayCallFeature::FoldedConstantDimensions);
  }
  return features;
}

std::vector<HIRFunctionParameterArrayCallFeature>
functionParameterArrayCallArgumentFeatures(const HIRModule &module,
                                           const HIRFunction &function,
                                           const HIRExpression &argument,
                                           const HIRStage *stage) {
  const HIRExpression *unwrapped =
      unwrapFunctionParameterArrayTransparentExpression(argument);
  const HIRExpression *root = functionParameterArrayCallArgumentRoot(argument);
  const HIRResource *rootResource =
      root->kind == HIRExpressionKind::Identifier
          ? findStageResource(stage, root->value)
          : nullptr;

  std::vector<HIRFunctionParameterArrayCallFeature> features;
  if (unwrapped->kind == HIRExpressionKind::Identifier && rootResource != nullptr &&
      rootResource->kind != HIRResourceKind::Shared &&
      rootResource->kind != HIRResourceKind::Value &&
      rootResource->type.arraySize.has_value()) {
    appendFunctionParameterArrayCallFeature(
        features,
        HIRFunctionParameterArrayCallFeature::DirectResourceArrayArguments);
    return features;
  }

  features = functionParameterArrayCallTypeFeatures(module, argument.type);
  if (functionParameterArrayShape(module, argument.type) !=
      HIRFunctionParameterArrayShape::FixedSize) {
    return features;
  }

  if (unwrapped->kind == HIRExpressionKind::Identifier) {
    if (const HIRParameter *parameter =
            findFunctionParameter(function, unwrapped->value);
        parameter != nullptr && parameter->type.arraySize.has_value()) {
      appendFunctionParameterArrayCallFeature(
          features,
          HIRFunctionParameterArrayCallFeature::FunctionParameterArguments);
    } else if (rootResource == nullptr) {
      appendFunctionParameterArrayCallFeature(
          features, HIRFunctionParameterArrayCallFeature::LocalArrayArguments);
    }
  }

  const std::size_t memberDepth =
      functionParameterArrayCallArgumentMemberDepth(argument);
  if (memberDepth > 0 && rootResource != nullptr &&
      rootResource->kind == HIRResourceKind::Buffer) {
    appendFunctionParameterArrayCallFeature(
        features,
        HIRFunctionParameterArrayCallFeature::StorageBufferFieldArguments);
  }
  if (memberDepth > 1) {
    appendFunctionParameterArrayCallFeature(
        features,
        HIRFunctionParameterArrayCallFeature::NestedStructFieldArguments);
  }

  return features;
}

std::vector<HIRFunctionParameterArrayCallFeature>
functionParameterArrayReadFeatures(const HIRModule &module,
                                   const HIRFunction &function,
                                   const HIRExpression &expression) {
  const HIRExpression *root = functionParameterArrayCallArgumentRoot(expression);
  if (root == nullptr || root->kind != HIRExpressionKind::Identifier) {
    return {};
  }
  const HIRParameter *parameter = findFunctionParameter(function, root->value);
  if (parameter == nullptr ||
      functionParameterArrayShape(module, parameter->type) !=
          HIRFunctionParameterArrayShape::FixedSize) {
    return {};
  }

  std::vector<HIRFunctionParameterArrayCallFeature> features =
      functionParameterArrayCallTypeFeatures(module, parameter->type);
  appendFunctionParameterArrayCallFeature(
      features,
      HIRFunctionParameterArrayCallFeature::FunctionParameterArguments);
  if (functionParameterArrayHasDynamicNestedIndex(module, expression)) {
    appendFunctionParameterArrayCallFeature(
        features,
        HIRFunctionParameterArrayCallFeature::DynamicNestedArrayIndices);
  }
  return features;
}

std::vector<HIRFunctionParameterArrayCallFeature>
functionParameterArrayBodyReadFeatures(const HIRModule &module,
                                       const HIRFunction &function) {
  std::vector<HIRFunctionParameterArrayCallFeature> features;
  appendFunctionParameterArrayReadFeaturesInStatements(
      module, function,
      std::span<const HIRStatement>{function.body.data(),
                                    function.body.size()},
      features);
  return features;
}

std::string functionParameterArrayCallFeatureName(
    HIRFunctionParameterArrayCallFeature feature) {
  switch (feature) {
  case HIRFunctionParameterArrayCallFeature::ScalarVectorElements:
    return "scalar-vector-elements";
  case HIRFunctionParameterArrayCallFeature::MatrixElements:
    return "matrix-elements";
  case HIRFunctionParameterArrayCallFeature::FixedNestedArrays:
    return "fixed-nested-arrays";
  case HIRFunctionParameterArrayCallFeature::FoldedConstantDimensions:
    return "folded-constant-dimensions";
  case HIRFunctionParameterArrayCallFeature::DynamicNestedArrayIndices:
    return "dynamic-nested-array-indices";
  case HIRFunctionParameterArrayCallFeature::StructElements:
    return "struct-elements";
  case HIRFunctionParameterArrayCallFeature::LocalArrayArguments:
    return "local-array-arguments";
  case HIRFunctionParameterArrayCallFeature::FunctionParameterArguments:
    return "function-parameter-arguments";
  case HIRFunctionParameterArrayCallFeature::StorageBufferFieldArguments:
    return "storage-buffer-field-arguments";
  case HIRFunctionParameterArrayCallFeature::NestedStructFieldArguments:
    return "nested-struct-field-arguments";
  case HIRFunctionParameterArrayCallFeature::DirectResourceArrayArguments:
    return "direct-resource-array-arguments";
  }
  return "unknown";
}

std::string functionParameterArrayCallFeatureSupportName(
    HIRFunctionParameterArrayCallFeatureSupport support) {
  switch (support) {
  case HIRFunctionParameterArrayCallFeatureSupport::Supported:
    return "supported";
  case HIRFunctionParameterArrayCallFeatureSupport::Unsupported:
    return "unsupported";
  }
  return "unknown";
}

} // namespace crossgl
