#include "crossgl/Backend/OpenGLBackend.h"

#include "crossgl/Backend/BackendExpressions.h"
#include "crossgl/Backend/BackendHIR.h"
#include "crossgl/Backend/BackendIntrinsics.h"
#include "crossgl/Backend/BackendPlan.h"
#include "crossgl/Backend/BackendResources.h"
#include "crossgl/Backend/BackendStatements.h"
#include "crossgl/Backend/ResourceArrays.h"
#include "crossgl/Backend/StorageBufferSupport.h"
#include "crossgl/Backend/TargetLegalization.h"
#include "crossgl/Backend/TextureCompare.h"
#include "crossgl/Backend/TextureSample.h"
#include "crossgl/Backend/TextureTypes.h"
#include "crossgl/Backend/Toolchain.h"
#include "crossgl/Frontend/TokenText.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <optional>
#include <set>
#include <sstream>
#include <string_view>
#include <system_error>
#include <unordered_map>
#include <utility>
#include <vector>

namespace crossgl {
namespace {

constexpr std::string_view kRawStatementBackendInputDiagnostic =
    "opt.hir-raw-statement-backend-input";
constexpr std::string_view kOpenGLGLSLVersion = "450";

bool containsRawStatement(const std::vector<HIRStatement> &statements) {
  for (const HIRStatement &statement : statements) {
    if (statement.kind == HIRStatementKind::Raw ||
        containsRawStatement(statement.initializer) ||
        containsRawStatement(statement.update) ||
        containsRawStatement(statement.body) ||
        containsRawStatement(statement.elseBody)) {
      return true;
    }
  }
  return false;
}

bool moduleContainsRawStatement(const HIRModule &module) {
  for (const HIRFunction &function : module.functions) {
    if (containsRawStatement(function.body)) {
      return true;
    }
  }
  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &function : stage.functions) {
      if (containsRawStatement(function.body)) {
        return true;
      }
    }
  }
  return false;
}

bool diagnoseRawStatementBackendInput(const HIRModule &module,
                                      DiagnosticEngine &diagnostics) {
  if (!moduleContainsRawStatement(module)) {
    return false;
  }
  diagnostics.error(
      std::string(kRawStatementBackendInputDiagnostic),
      "OpenGL source package input cannot contain HIR raw statements; "
      "lower them to structured HIR before backend emission");
  return true;
}

std::string glslTypeName(std::string_view name) {
  if (name == "float" || name == "int" || name == "uint" || name == "bool" ||
      name == "void" || name == "vec2" || name == "vec3" ||
      name == "vec4" || name == "ivec2" || name == "ivec3" ||
      name == "ivec4" || name == "uvec2" || name == "uvec3" ||
      name == "uvec4" || name == "bvec2" || name == "bvec3" ||
      name == "bvec4") {
    return std::string(name);
  }
  return "";
}

std::optional<std::string>
glslAtomicIntegerStorageTypeName(std::string_view name) {
  const std::string storageName =
      stripPointerSuffix(stripTypeQualifier(std::string(name)));
  constexpr std::string_view prefix = "atomic<";
  if (storageName.rfind(prefix, 0) != 0 || storageName.size() <= prefix.size() ||
      storageName.back() != '>') {
    return std::nullopt;
  }
  const std::string elementType =
      storageName.substr(prefix.size(), storageName.size() - prefix.size() - 1);
  if (elementType == "int" || elementType == "uint") {
    return elementType;
  }
  return std::nullopt;
}

std::optional<std::string> glslAtomicIntegerStorageType(const HIRType &type) {
  return glslAtomicIntegerStorageTypeName(type.name);
}

std::string glslType(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return "";
  }
  return glslTypeName(stripPointer(type.name));
}

bool isSupportedValueType(const HIRType &type) {
  return !type.arraySize.has_value() && !glslType(type).empty();
}

bool isSupportedFixedSizeLocalArrayValueType(const HIRType &type) {
  if (!type.arraySize.has_value() || type.arraySize->empty()) {
    return false;
  }
  const std::string baseName = stripPointer(type.name);
  return baseName == "float" || baseName == "int" || baseName == "uint" ||
         baseName == "vec2" || baseName == "vec3" || baseName == "vec4" ||
         baseName == "ivec2" || baseName == "ivec3" ||
         baseName == "ivec4" || baseName == "uvec2" ||
         baseName == "uvec3" || baseName == "uvec4";
}

bool isSupportedLocalDeclarationType(const HIRType &type) {
  return isSupportedValueType(type) ||
         isSupportedFixedSizeLocalArrayValueType(type);
}

bool isSupportedGraphicsLocalDeclarationType(const HIRModule &module,
                                             const HIRType &type) {
  if (isSupportedLocalDeclarationType(type)) {
    return true;
  }
  return !type.arraySize.has_value() &&
         findStruct(module, stripPointer(type.name)) != nullptr;
}

bool isSupportedSharedResourceType(const HIRType &type) {
  return isSupportedValueType(type) ||
         isSupportedFixedSizeLocalArrayValueType(type) ||
         (glslAtomicIntegerStorageType(type).has_value() &&
          (!type.arraySize.has_value() || !type.arraySize->empty()));
}

std::string glslValueType(const HIRModule &module, const HIRType &type) {
  const std::string baseName = stripPointer(type.name);
  const std::string valueType = glslTypeName(baseName);
  if (!valueType.empty()) {
    return valueType;
  }
  const HIRStruct *structure = findStruct(module, baseName);
  return structure != nullptr ? structure->name : "";
}

std::string glslArraySuffix(const HIRType &type) {
  return type.arraySize.has_value() ? "[" + *type.arraySize + "]" : "";
}

bool isSupportedFunctionValueType(const HIRModule &module,
                                  const HIRType &type) {
  if (type.name == "void" || (!type.name.empty() && type.name.back() == '*')) {
    return false;
  }
  if (glslValueType(module, type).empty()) {
    return false;
  }
  return !type.arraySize.has_value() || !type.arraySize->empty();
}

bool isSupportedFunctionReturnType(const HIRModule &module,
                                   const HIRType &type) {
  if (type.name == "void" && !type.arraySize.has_value()) {
    return true;
  }
  return !type.arraySize.has_value() && isSupportedFunctionValueType(module, type);
}

std::string glslFunctionReturnType(const HIRModule &module,
                                   const HIRType &type) {
  if (type.name == "void" && !type.arraySize.has_value()) {
    return "void";
  }
  return glslValueType(module, type);
}

std::string glslDeclarator(const HIRModule &module, const HIRType &type,
                           std::string_view name) {
  return glslValueType(module, type) + " " + std::string(name) +
         glslArraySuffix(type);
}

std::string glslStructFieldType(const HIRModule &module, const HIRType &type) {
  const std::string baseName = stripPointer(type.name);
  const std::string valueType = glslTypeName(baseName);
  if (!valueType.empty()) {
    return valueType;
  }
  const HIRStruct *structure = findStruct(module, baseName);
  return structure != nullptr ? structure->name : "";
}

bool glslStorageBufferScalarTypeSupported(std::string_view name) {
  return !glslTypeName(name).empty();
}

bool openglStructStorageBufferElementSupported(const HIRModule &module,
                                               const HIRStruct &structure) {
  return structStorageBufferElementSupported(
      module, structure, glslStorageBufferScalarTypeSupported);
}

bool isOpenGLRuntimeTailField(const HIRStruct &structure,
                              std::size_t fieldIndex) {
  return fieldIndex + 1 == structure.fields.size() &&
         isRuntimeArrayType(structure.fields[fieldIndex].type);
}

bool openGLRuntimeTailElementTypeSupported(const HIRModule &module,
                                           const HIRType &type) {
  const HIRType elementType = arrayElementType(type);
  const std::string baseName = baseTypeName(elementType);
  if (!elementType.arraySize.has_value() &&
      glslStorageBufferScalarTypeSupported(baseName)) {
    return true;
  }
  if (elementType.arraySize.has_value()) {
    return false;
  }
  const HIRStruct *structure = findStruct(module, elementType.name);
  return structure != nullptr &&
         openglStructStorageBufferElementSupported(module, *structure);
}

bool openGLRuntimeTailBlockStructSupported(const HIRModule &module,
                                           const HIRStruct &structure) {
  if (structure.fields.empty()) {
    return false;
  }
  const std::size_t tailIndex = structure.fields.size() - 1;
  if (!isOpenGLRuntimeTailField(structure, tailIndex) ||
      !openGLRuntimeTailElementTypeSupported(module,
                                             structure.fields[tailIndex].type)) {
    return false;
  }

  HIRStruct fixedHeader{structure.name, {}};
  fixedHeader.fields.assign(structure.fields.begin(),
                            structure.fields.begin() + tailIndex);
  return openglStructStorageBufferElementSupported(module, fixedHeader);
}

bool isSupportedStorageBufferElementType(const HIRModule &module,
                                         const HIRType &type) {
  if (!type.arraySize.has_value() &&
      glslAtomicIntegerStorageType(type).has_value()) {
    return true;
  }
  if (storageBufferElementTypeSupported(
          module, type, glslStorageBufferScalarTypeSupported)) {
    return true;
  }
  if (type.arraySize.has_value()) {
    return false;
  }
  const HIRStruct *structure = findStruct(module, type.name);
  return structure != nullptr &&
         openGLRuntimeTailBlockStructSupported(module, *structure);
}

std::string glslStorageBufferElementType(const HIRModule &module,
                                         const HIRType &type) {
  if (const std::optional<std::string> atomicType =
          glslAtomicIntegerStorageType(type)) {
    return *atomicType;
  }
  const std::string valueType = glslType(type);
  if (!valueType.empty()) {
    return valueType;
  }
  const HIRStruct *structure = findStruct(module, type.name);
  if (structure != nullptr &&
      openglStructStorageBufferElementSupported(module, *structure)) {
    return structure->name;
  }
  return "";
}

const HIRStruct *openGLRuntimeTailBlockStruct(const HIRModule &module,
                                              const HIRResource &resource) {
  if (resource.kind != HIRResourceKind::Buffer ||
      resource.type.arraySize.has_value()) {
    return nullptr;
  }
  const HIRType elementType = bufferElementType(resource.type);
  if (elementType.arraySize.has_value()) {
    return nullptr;
  }
  const HIRStruct *structure = findStruct(module, elementType.name);
  if (structure == nullptr ||
      !openGLRuntimeTailBlockStructSupported(module, *structure)) {
    return nullptr;
  }
  return structure;
}

std::string glslTexturePrefix(const HIRType &type) {
  if (isSignedIntegerTextureTypeName(type.name)) {
    return "itexture";
  }
  if (isUnsignedIntegerTextureTypeName(type.name)) {
    return "utexture";
  }
  return "texture";
}

std::string glslCombinedSamplerPrefix(const HIRType &type) {
  if (isSignedIntegerTextureTypeName(type.name)) {
    return "isampler";
  }
  if (isUnsignedIntegerTextureTypeName(type.name)) {
    return "usampler";
  }
  return "sampler";
}

std::string glslTextureType(const HIRType &type) {
  if (!isSupportedTextureTypeName(type.name)) {
    return "";
  }
  if (type.name == "sampler2DShadow") {
    return "texture2D";
  }
  if (type.name == "sampler2DArrayShadow") {
    return "texture2DArray";
  }
  if (type.name == "samplerCubeShadow") {
    return "textureCube";
  }
  if (type.name == "samplerCubeArrayShadow") {
    return "textureCubeArray";
  }
  const std::string prefix = glslTexturePrefix(type);
  if (type.name == "sampler2DArray" || type.name == "texture2DArray" ||
      type.name == "isampler2DArray" || type.name == "usampler2DArray") {
    return prefix + "2DArray";
  }
  if (type.name == "samplerCubeArray" || type.name == "textureCubeArray" ||
      type.name == "isamplerCubeArray" ||
      type.name == "usamplerCubeArray") {
    return prefix + "CubeArray";
  }
  if (type.name == "sampler3D" || type.name == "texture3D" ||
      type.name == "isampler3D" || type.name == "usampler3D") {
    return prefix + "3D";
  }
  if (type.name == "samplerCube" || type.name == "textureCube" ||
      type.name == "isamplerCube" || type.name == "usamplerCube") {
    return prefix + "Cube";
  }
  return prefix + "2D";
}

std::string glslStorageImageType(const HIRType &type) {
  const std::string name = baseTypeName(type);
  return isStorageImageResourceType(name) ? name : "";
}

std::string glslStorageImageFormat(const HIRResource &resource) {
  return resolvedStorageImageFormatName(resource);
}

std::string glslStorageImagePayloadType(const HIRType &type) {
  return storageImagePayloadVectorTypeName(baseTypeName(type));
}

std::string glslStorageImageAtomicPayloadType(const HIRType &type) {
  return storageImageAtomicPayloadTypeName(baseTypeName(type));
}

std::string glslStorageImageCoordinateType(const HIRType &type) {
  return storageImageCoordinateTypeName(baseTypeName(type));
}

template <typename Resource>
std::string glslStorageImageAccessQualifier(const Resource &resource) {
  if constexpr (requires { resource.storageImageAccess; }) {
    switch (static_cast<int>(resource.storageImageAccess)) {
    case 1:
      return "readonly ";
    case 2:
      return "writeonly ";
    default:
      break;
    }
  }
  return "";
}

std::string glslCombinedSamplerType(const HIRType &textureType) {
  if (!isSupportedTextureTypeName(textureType.name)) {
    return "";
  }
  if (textureType.name == "sampler2DShadow" ||
      textureType.name == "sampler2DArrayShadow" ||
      textureType.name == "samplerCubeShadow" ||
      textureType.name == "samplerCubeArrayShadow") {
    return std::string(textureType.name);
  }
  const std::string prefix = glslCombinedSamplerPrefix(textureType);
  if (textureType.name == "sampler2DArray" ||
      textureType.name == "texture2DArray" ||
      textureType.name == "isampler2DArray" ||
      textureType.name == "usampler2DArray") {
    return prefix + "2DArray";
  }
  if (textureType.name == "samplerCubeArray" ||
      textureType.name == "textureCubeArray" ||
      textureType.name == "isamplerCubeArray" ||
      textureType.name == "usamplerCubeArray") {
    return prefix + "CubeArray";
  }
  if (textureType.name == "sampler3D" || textureType.name == "texture3D" ||
      textureType.name == "isampler3D" || textureType.name == "usampler3D") {
    return prefix + "3D";
  }
  if (textureType.name == "samplerCube" ||
      textureType.name == "textureCube" ||
      textureType.name == "isamplerCube" ||
      textureType.name == "usamplerCube") {
    return prefix + "Cube";
  }
  return prefix + "2D";
}

std::string glslManualCompareCombinedSamplerType(const HIRType &textureType) {
  switch (textureCompareShape(textureType)) {
  case TextureCompareShape::Shadow2D:
    return "sampler2D";
  case TextureCompareShape::Shadow2DArray:
    return "sampler2DArray";
  case TextureCompareShape::ShadowCube:
    return "samplerCube";
  case TextureCompareShape::ShadowCubeArray:
    return "samplerCubeArray";
  case TextureCompareShape::Unknown:
    break;
  }
  return "";
}

std::string storageBufferArrayInstanceName(std::string_view resourceName) {
  return std::string(resourceName) + "_Buffers";
}

bool isSupportedTextureResource(const HIRResource &resource) {
  return resource.kind == HIRResourceKind::Texture &&
         supportedResourceArraySize(resource.type) &&
         !glslTextureType(resource.type).empty();
}

bool isSupportedStorageImageResource(const HIRResource &resource) {
  return resource.kind == HIRResourceKind::StorageImage &&
         supportedResourceArraySize(resource.type) &&
         !glslStorageImageType(resource.type).empty();
}

bool isSupportedSamplerResource(const HIRResource &resource) {
  return resource.kind == HIRResourceKind::Sampler &&
         supportedResourceArraySize(resource.type) &&
         (resource.type.name == "sampler" ||
          resource.type.name == "comparison_sampler");
}

bool expressionSupported(const HIRExpression &expression);
bool constantSupported(const HIRConstant &constant);

bool expressionUsesNonUniform(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::NonUniform;
}

bool moduleUsesNonUniform(const HIRModule &module) {
  return moduleExpressionsContain(module, expressionUsesNonUniform, true);
}

bool expressionUsesShadowCompareExplicitLod(const HIRExpression &expression) {
  const std::optional<TextureCompareOperands> operands =
      textureCompareOperands(expression);
  return operands.has_value() && operands->explicitLod &&
         operands->texture != nullptr &&
         textureCompareShape(operands->texture->type) !=
             TextureCompareShape::Unknown;
}

bool moduleUsesShadowCompareExplicitLod(const HIRModule &module) {
  return moduleExpressionsContain(module, expressionUsesShadowCompareExplicitLod,
                                  true);
}

std::optional<std::string>
resourceReferenceBaseName(const HIRExpression &expression) {
  if (expression.kind == HIRExpressionKind::Identifier) {
    if (expression.value.empty()) {
      return std::nullopt;
    }
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

std::string
shadowCompareExplicitLodShapeLabel(const HIRExpression &texture) {
  const std::optional<std::string> name = resourceReferenceBaseName(texture);
  if (!name.has_value()) {
    return textureCompareShapeName(textureCompareShape(texture.type));
  }
  const std::string shapeName =
      textureCompareShapeName(textureCompareShape(texture.type));
  if (shapeName == "unknown") {
    return *name;
  }
  return *name + " (" + shapeName + ")";
}

struct OpenGLSupportContext {
  const HIRModule *module = nullptr;
  const HIRStage *stage = nullptr;
  const HIRFunction *function = nullptr;
};

const HIRResource *findOpenGLStageResource(const OpenGLSupportContext &context,
                                           std::string_view name);

bool openGLExplicitLodShadowCompareTextureSupported(
    const HIRExpression &texture, const OpenGLSupportContext &context);

bool openGLExplicitLodShadowCompareOperandsSupported(
    const TextureCompareOperands &operands,
    const OpenGLSupportContext &context);

bool expressionHasUnsupportedShadowCompareExplicitLodShape(
    const HIRExpression &expression, const OpenGLSupportContext &context);

std::set<std::string>
unsupportedShadowCompareExplicitLodShapeLabels(const HIRModule &module);

const HIRFunction *findStageFunction(const OpenGLSupportContext &context,
                                     std::string_view name) {
  if (context.stage == nullptr) {
    return nullptr;
  }
  for (const HIRFunction &function : context.stage->functions) {
    if (function.name == name) {
      return &function;
    }
  }
  return nullptr;
}

const HIRStage *findOpenGLStage(const HIRModule &module,
                                std::string_view stageName) {
  const HIRStage *result = nullptr;
  for (const HIRStage &stage : module.stages) {
    if (stage.stage != stageName) {
      continue;
    }
    if (result != nullptr) {
      return nullptr;
    }
    result = &stage;
  }
  return result;
}

bool typeEquals(const HIRType &lhs, const HIRType &rhs) {
  return lhs.name == rhs.name && lhs.arraySize == rhs.arraySize;
}

const HIRField *findField(const HIRStruct &structure, std::string_view name) {
  for (const HIRField &field : structure.fields) {
    if (field.name == name) {
      return &field;
    }
  }
  return nullptr;
}

bool isOpenGLGraphicsScalarFieldType(const HIRType &type) {
  return !type.arraySize.has_value() && !glslType(type).empty();
}

bool openGLGraphicsStructSupported(const HIRStruct &structure) {
  if (structure.fields.empty()) {
    return false;
  }
  for (const HIRField &field : structure.fields) {
    if (!isOpenGLGraphicsScalarFieldType(field.type)) {
      return false;
    }
  }
  return true;
}

const HIRStruct *openGLStructType(const HIRModule &module,
                                  const HIRType &type) {
  if (type.arraySize.has_value() || type.name.empty() ||
      type.name.back() == '*') {
    return nullptr;
  }
  return findStruct(module, type.name);
}

const HIRField *openGLGraphicsPositionField(const HIRStruct &structure) {
  if (const HIRField *position = findField(structure, "position")) {
    if (!position->type.arraySize.has_value() &&
        position->type.name == "vec4") {
      return position;
    }
  }
  if (const HIRField *clipPosition = findField(structure, "clipPosition")) {
    if (!clipPosition->type.arraySize.has_value() &&
        clipPosition->type.name == "vec4") {
      return clipPosition;
    }
  }
  return nullptr;
}

bool isOpenGLGraphicsPositionField(const HIRField &field) {
  return (field.name == "position" || field.name == "clipPosition") &&
         !field.type.arraySize.has_value() && field.type.name == "vec4";
}

bool openGLGraphicsEntrySignatureSupported(const HIRModule &module,
                                           const HIRStage &stage,
                                           const HIRFunction &function) {
  if (stage.stage != "vertex" && stage.stage != "fragment") {
    return false;
  }
  if (function.parameters.size() != 1) {
    return false;
  }
  const HIRStruct *input =
      openGLStructType(module, function.parameters.front().type);
  const HIRStruct *output = openGLStructType(module, function.returnType);
  if (input == nullptr || output == nullptr ||
      !openGLGraphicsStructSupported(*input) ||
      !openGLGraphicsStructSupported(*output)) {
    return false;
  }
  if (stage.stage == "vertex" &&
      openGLGraphicsPositionField(*output) == nullptr) {
    return false;
  }
  return true;
}

bool openGLGraphicsVaryingsSupported(const HIRModule &module,
                                     const HIRFunction &vertexEntry,
                                     const HIRFunction &fragmentEntry) {
  const HIRStruct *vertexOutput =
      openGLStructType(module, vertexEntry.returnType);
  const HIRStruct *fragmentInput =
      openGLStructType(module, fragmentEntry.parameters.front().type);
  if (vertexOutput == nullptr || fragmentInput == nullptr) {
    return false;
  }
  for (const HIRField &field : fragmentInput->fields) {
    const HIRField *source = findField(*vertexOutput, field.name);
    if (source == nullptr || isOpenGLGraphicsPositionField(*source) ||
        !typeEquals(source->type, field.type)) {
      return false;
    }
  }
  return true;
}

bool openGLGraphicsStagePair(const HIRModule &module, const HIRStage *&vertex,
                             const HIRStage *&fragment) {
  vertex = nullptr;
  fragment = nullptr;
  if (module.stages.size() != 2) {
    return false;
  }
  vertex = findOpenGLStage(module, "vertex");
  fragment = findOpenGLStage(module, "fragment");
  return vertex != nullptr && fragment != nullptr;
}

bool openGLLocalDeclarationTypeSupported(const OpenGLSupportContext &context,
                                         const HIRType &type) {
  if (isSupportedLocalDeclarationType(type)) {
    return true;
  }
  if (context.module == nullptr || context.stage == nullptr ||
      (context.stage->stage != "vertex" && context.stage->stage != "fragment")) {
    return false;
  }
  return isSupportedGraphicsLocalDeclarationType(*context.module, type);
}

void appendOpenGLFunctionParameterArrayCallFeature(
    std::vector<HIRFunctionParameterArrayCallFeature> &features,
    HIRFunctionParameterArrayCallFeature feature) {
  if (std::find(features.begin(), features.end(), feature) == features.end()) {
    features.push_back(feature);
  }
}

HIRFunctionParameterArrayCallFeatureSupport
openGLFunctionParameterArrayCallFeatureSupport(
    HIRFunctionParameterArrayCallFeature feature) {
  if (feature == HIRFunctionParameterArrayCallFeature::StructElements) {
    return HIRFunctionParameterArrayCallFeatureSupport::Supported;
  }
  return functionParameterArrayCallFeatureSupport(feature);
}

HIRFunctionParameterArrayCallFeatureSupport
openGLFunctionParameterArrayCallFeaturesSupport(
    const std::vector<HIRFunctionParameterArrayCallFeature> &features) {
  for (HIRFunctionParameterArrayCallFeature feature : features) {
    if (openGLFunctionParameterArrayCallFeatureSupport(feature) ==
        HIRFunctionParameterArrayCallFeatureSupport::Unsupported) {
      return HIRFunctionParameterArrayCallFeatureSupport::Unsupported;
    }
  }
  return HIRFunctionParameterArrayCallFeatureSupport::Supported;
}

void appendUnsupportedOpenGLFunctionArrayFeatureLabels(
    std::set<std::string> &labels, std::string_view functionName,
    std::string_view parameterName,
    const std::vector<HIRFunctionParameterArrayCallFeature> &features) {
  for (HIRFunctionParameterArrayCallFeature feature : features) {
    if (openGLFunctionParameterArrayCallFeatureSupport(feature) !=
        HIRFunctionParameterArrayCallFeatureSupport::Unsupported) {
      continue;
    }
    labels.insert(std::string(functionName) + "." +
                  std::string(parameterName) + " (" +
                  functionParameterArrayCallFeatureName(feature) + ")");
  }
}

bool openGLFunctionParameterArrayCallFeaturesSupported(
    const HIRModule &module, const HIRFunction &caller,
    const HIRFunction &callee, const HIRExpression &expression,
    const HIRStage *stage,
    std::set<std::string> *unsupportedLabels = nullptr) {
  if (expression.children.size() != callee.parameters.size()) {
    return true;
  }

  bool supported = true;
  for (std::size_t index = 0; index < callee.parameters.size(); ++index) {
    const HIRParameter &parameter = callee.parameters[index];
    if (functionParameterArrayShape(module, parameter.type) !=
        HIRFunctionParameterArrayShape::FixedSize) {
      continue;
    }

    std::vector<HIRFunctionParameterArrayCallFeature> features =
        functionParameterArrayCallTypeFeatures(module, parameter.type);
    const std::vector<HIRFunctionParameterArrayCallFeature> argumentFeatures =
        functionParameterArrayCallArgumentFeatures(
            module, caller, expression.children[index], stage);
    for (HIRFunctionParameterArrayCallFeature feature : argumentFeatures) {
      appendOpenGLFunctionParameterArrayCallFeature(features, feature);
    }

    if (openGLFunctionParameterArrayCallFeaturesSupport(features) ==
        HIRFunctionParameterArrayCallFeatureSupport::Unsupported) {
      supported = false;
      if (unsupportedLabels != nullptr) {
        appendUnsupportedOpenGLFunctionArrayFeatureLabels(
            *unsupportedLabels, callee.name, parameter.name, features);
      }
    }
  }
  return supported;
}

std::set<std::string>
unsupportedOpenGLFunctionParameterArrayCallFeatureLabels(
    const HIRModule &module) {
  std::set<std::string> labels;
  const HIRStage *stage = singleComputeStage(module);
  if (stage == nullptr) {
    return labels;
  }

  for (const HIRFunction &function : stage->functions) {
    OpenGLSupportContext context{&module, stage, &function};
    auto visitor = [&](const HIRExpression &expression) {
      if (expression.kind != HIRExpressionKind::Call) {
        return;
      }
      const HIRFunction *callee = findStageFunction(context, expression.value);
      if (callee == nullptr) {
        return;
      }
      (void)openGLFunctionParameterArrayCallFeaturesSupported(
          module, function, *callee, expression, stage, &labels);
    };
    visitFunctionExpressions(function, visitor);
  }
  return labels;
}

bool isOpenGLStaticZeroExpression(
    const HIRExpression &expression, const HIRModule &module,
    const std::set<std::string> &localIdentifiers);

std::set<std::string>
unsupportedOpenGLStorageBufferElementTypeLabels(const HIRModule &module) {
  std::set<std::string> elementTypes;
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind != HIRResourceKind::Buffer) {
        continue;
      }
      const HIRType elementType = bufferElementType(resource.type);
      if (!elementType.arraySize.has_value() &&
          glslAtomicIntegerStorageType(elementType).has_value()) {
        continue;
      }
      if (storageBufferElementTypeSupported(
              module, elementType, glslStorageBufferScalarTypeSupported)) {
        continue;
      }
      if (openGLRuntimeTailBlockStruct(module, resource) != nullptr) {
        continue;
      }
      elementTypes.insert(resource.name + " (" + elementType.name + ")");
    }
  }
  return elementTypes;
}

std::set<std::string> openGLRuntimeTailBlockResourceNames(
    const HIRModule &module, const HIRStage &stage) {
  std::set<std::string> names;
  for (const HIRResource &resource : stage.resources) {
    if (openGLRuntimeTailBlockStruct(module, resource) != nullptr) {
      names.insert(resource.name);
    }
  }
  return names;
}

void collectUnsupportedOpenGLRuntimeTailBlockIndexesInStatement(
    const HIRStatement &statement, const HIRModule &module,
    const std::set<std::string> &resources,
    const std::set<std::string> &localIdentifiers,
    std::set<std::string> &labels) {
  auto visitor = [&](const HIRExpression &expression) {
    if (expression.kind == HIRExpressionKind::IndexAccess &&
        expression.children.size() == 2 &&
        expression.children[0].kind == HIRExpressionKind::Identifier &&
        resources.count(expression.children[0].value) != 0 &&
        !isOpenGLStaticZeroExpression(expression.children[1], module,
                                      localIdentifiers)) {
      labels.insert(expression.children[0].value);
    }
  };
  visitStatementExpressions(statement, visitor);
}

void collectOpenGLLocalIdentifiers(const HIRStatement &statement,
                                   std::set<std::string> &identifiers) {
  if (statement.kind == HIRStatementKind::Declaration) {
    identifiers.insert(statement.name);
  }
  for (const HIRStatement &initializer : statement.initializer) {
    collectOpenGLLocalIdentifiers(initializer, identifiers);
  }
  for (const HIRStatement &update : statement.update) {
    collectOpenGLLocalIdentifiers(update, identifiers);
  }
  for (const HIRStatement &child : statement.body) {
    collectOpenGLLocalIdentifiers(child, identifiers);
  }
  for (const HIRStatement &child : statement.elseBody) {
    collectOpenGLLocalIdentifiers(child, identifiers);
  }
}

std::set<std::string> openGLFunctionLocalIdentifiers(
    const HIRFunction &function) {
  std::set<std::string> identifiers;
  for (const HIRParameter &parameter : function.parameters) {
    identifiers.insert(parameter.name);
  }
  for (const HIRStatement &statement : function.body) {
    collectOpenGLLocalIdentifiers(statement, identifiers);
  }
  return identifiers;
}

std::set<std::string>
unsupportedOpenGLRuntimeTailBlockIndexLabels(const HIRModule &module) {
  std::set<std::string> labels;
  const HIRStage *stage = singleComputeStage(module);
  if (stage == nullptr) {
    return labels;
  }
  const std::set<std::string> resources =
      openGLRuntimeTailBlockResourceNames(module, *stage);
  if (resources.empty()) {
    return labels;
  }
  for (const HIRFunction &function : stage->functions) {
    const std::set<std::string> localIdentifiers =
        openGLFunctionLocalIdentifiers(function);
    for (const HIRStatement &statement : function.body) {
      collectUnsupportedOpenGLRuntimeTailBlockIndexesInStatement(
          statement, module, resources, localIdentifiers, labels);
    }
  }
  return labels;
}

struct OpenGLEmitContext {
  const HIRModule *module = nullptr;
  const TargetLegalizationResourceBindingFacts *resourceBindings = nullptr;
  std::string stage;
  std::string backendEntryPoint;
  bool useCombinedSamplerResources = false;
  std::set<std::string> storageBufferArrays;
  std::set<std::string> runtimeTailBlocks;
  std::set<std::string> combinedShadowCompareLodTextures;
  std::set<std::string> combinedShadowCompareLodSamplers;
  std::unordered_map<std::string, std::string> identifierRemaps;
  std::set<std::string> localIdentifiers;
};

std::string emitExpression(const HIRExpression &expression,
                           const OpenGLEmitContext &context);

bool isOpenGLWorkgroupBarrierCallName(std::string_view name) {
  return name == "workgroupBarrier" || name == "barrier";
}

bool isOpenGLWorkgroupBarrierCall(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::Call &&
         expression.children.empty() &&
         isOpenGLWorkgroupBarrierCallName(expression.value);
}

bool isOpenGLAtomicIntegerCallName(std::string_view name) {
  return name == "atomicAdd" || name == "atomicMin" || name == "atomicMax" ||
         name == "atomicExchange" || name == "atomicAnd" ||
         name == "atomicOr" || name == "atomicXor";
}

bool isOpenGLReservedIdentifier(std::string_view name) {
  static constexpr std::string_view reserved[] = {
      "active",
      "asm",
      "atomic_uint",
      "attribute",
      "bool",
      "break",
      "buffer",
      "case",
      "cast",
      "centroid",
      "class",
      "coherent",
      "common",
      "const",
      "continue",
      "default",
      "discard",
      "do",
      "double",
      "dvec2",
      "dvec3",
      "dvec4",
      "else",
      "enum",
      "extern",
      "external",
      "false",
      "filter",
      "fixed",
      "flat",
      "float",
      "for",
      "fvec2",
      "fvec3",
      "fvec4",
      "goto",
      "half",
      "highp",
      "hvec2",
      "hvec3",
      "hvec4",
      "if",
      "image1D",
      "image1DArray",
      "image2D",
      "image2DArray",
      "image2DMS",
      "image2DMSArray",
      "image2DRect",
      "image3D",
      "imageBuffer",
      "imageCube",
      "imageCubeArray",
      "in",
      "inline",
      "inout",
      "input",
      "int",
      "interface",
      "invariant",
      "isampler1D",
      "isampler1DArray",
      "isampler2D",
      "isampler2DArray",
      "isampler2DMS",
      "isampler2DMSArray",
      "isampler2DRect",
      "isampler3D",
      "isamplerBuffer",
      "isamplerCube",
      "isamplerCubeArray",
      "layout",
      "long",
      "lowp",
      "mat2",
      "mat2x2",
      "mat2x3",
      "mat2x4",
      "mat3",
      "mat3x2",
      "mat3x3",
      "mat3x4",
      "mat4",
      "mat4x2",
      "mat4x3",
      "mat4x4",
      "mediump",
      "namespace",
      "noinline",
      "noperspective",
      "out",
      "output",
      "packed",
      "patch",
      "precision",
      "precise",
      "public",
      "readonly",
      "restrict",
      "return",
      "sample",
      "sampler1D",
      "sampler1DArray",
      "sampler1DArrayShadow",
      "sampler1DShadow",
      "sampler2D",
      "sampler2DArray",
      "sampler2DArrayShadow",
      "sampler2DMS",
      "sampler2DMSArray",
      "sampler2DRect",
      "sampler2DRectShadow",
      "sampler2DShadow",
      "sampler3D",
      "samplerBuffer",
      "samplerCube",
      "samplerCubeArray",
      "samplerCubeArrayShadow",
      "samplerCubeShadow",
      "short",
      "sizeof",
      "smooth",
      "static",
      "struct",
      "subroutine",
      "superp",
      "switch",
      "template",
      "this",
      "true",
      "typedef",
      "uimage1D",
      "uimage1DArray",
      "uimage2D",
      "uimage2DArray",
      "uimage2DMS",
      "uimage2DMSArray",
      "uimage2DRect",
      "uimage3D",
      "uimageBuffer",
      "uimageCube",
      "uimageCubeArray",
      "uint",
      "uniform",
      "union",
      "unsigned",
      "usampler1D",
      "usampler1DArray",
      "usampler2D",
      "usampler2DArray",
      "usampler2DMS",
      "usampler2DMSArray",
      "usampler2DRect",
      "usampler3D",
      "usamplerBuffer",
      "usamplerCube",
      "usamplerCubeArray",
      "using",
      "varying",
      "vec2",
      "vec3",
      "vec4",
      "void",
      "volatile",
      "while",
      "writeonly",
  };
  for (const std::string_view reservedName : reserved) {
    if (name == reservedName) {
      return true;
    }
  }
  return false;
}

std::string openGLSafeIdentifierName(std::string_view name) {
  return "crossgl_user_" + std::string(name);
}

void registerOpenGLIdentifierRemap(OpenGLEmitContext &context,
                                   std::string_view name) {
  if (isOpenGLReservedIdentifier(name)) {
    context.identifierRemaps.emplace(std::string(name),
                                     openGLSafeIdentifierName(name));
  }
}

void collectOpenGLIdentifierRemaps(const HIRStatement &statement,
                                   OpenGLEmitContext &context) {
  if (statement.kind == HIRStatementKind::Declaration) {
    registerOpenGLIdentifierRemap(context, statement.name);
  }
  for (const HIRStatement &initializer : statement.initializer) {
    collectOpenGLIdentifierRemaps(initializer, context);
  }
  for (const HIRStatement &update : statement.update) {
    collectOpenGLIdentifierRemaps(update, context);
  }
  for (const HIRStatement &child : statement.body) {
    collectOpenGLIdentifierRemaps(child, context);
  }
  for (const HIRStatement &child : statement.elseBody) {
    collectOpenGLIdentifierRemaps(child, context);
  }
}

OpenGLEmitContext makeOpenGLFunctionEmitContext(
    const OpenGLEmitContext &baseContext, const HIRFunction &function) {
  OpenGLEmitContext context = baseContext;
  context.localIdentifiers = openGLFunctionLocalIdentifiers(function);
  for (const HIRParameter &parameter : function.parameters) {
    registerOpenGLIdentifierRemap(context, parameter.name);
  }
  for (const HIRStatement &statement : function.body) {
    collectOpenGLIdentifierRemaps(statement, context);
  }
  return context;
}

std::string emitIdentifierName(std::string_view name,
                               const OpenGLEmitContext &context) {
  const auto mapped = context.identifierRemaps.find(std::string(name));
  return mapped == context.identifierRemaps.end() ? std::string(name)
                                                  : mapped->second;
}

std::string emitFieldName(std::string_view name,
                          const OpenGLEmitContext &context) {
  return emitIdentifierName(name, context);
}

std::string emitCall(const HIRExpression &expression,
                     const OpenGLEmitContext &context) {
  if (isOpenGLWorkgroupBarrierCall(expression)) {
    return "barrier()";
  }
  const std::optional<std::string> callee =
      backendIntrinsicNameForCall(TargetKind::OpenGL, expression);
  const std::string calleeName = callee.value_or(expression.value);
  if (calleeName.empty()) {
    return "/* unsupported */";
  }
  if (!callee.has_value()) {
    std::ostringstream out;
    out << calleeName << "(";
    for (std::size_t index = 0; index < expression.children.size(); ++index) {
      if (index != 0) {
        out << ", ";
      }
      out << emitExpression(expression.children[index], context);
    }
    out << ")";
    return out.str();
  }
  std::ostringstream out;
  out << calleeName << "(";
  for (std::size_t index = 0; index < expression.children.size(); ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << emitExpression(expression.children[index], context);
  }
  out << ")";
  return out.str();
}

struct OpenGLTextureSampleOperands {
  const HIRExpression *texture = nullptr;
  const HIRExpression *sampler = nullptr;
  const HIRExpression *coordinate = nullptr;
  const HIRExpression *lod = nullptr;
};

std::optional<OpenGLTextureSampleOperands>
openGLTextureSampleOperands(const HIRExpression &expression) {
  if (const std::optional<TextureSampleOperands> explicitLodOperands =
          textureSampleOperands(expression)) {
    return OpenGLTextureSampleOperands{explicitLodOperands->texture,
                                       explicitLodOperands->sampler,
                                       explicitLodOperands->coordinate,
                                       explicitLodOperands->lod};
  }
  if (expression.kind != HIRExpressionKind::TextureSample ||
      (expression.value != "sample" && expression.value != "texture") ||
      expression.children.size() != 3) {
    return std::nullopt;
  }
  return OpenGLTextureSampleOperands{&expression.children[0],
                                     &expression.children[1],
                                     &expression.children[2], nullptr};
}

std::string emitTextureSample(const HIRExpression &expression,
                              const OpenGLEmitContext &context) {
  const std::optional<OpenGLTextureSampleOperands> operands =
      openGLTextureSampleOperands(expression);
  if (!operands.has_value()) {
    return "/* unsupported */";
  }
  const std::string combinedSampler =
      glslCombinedSamplerType(operands->texture->type);
  if (combinedSampler.empty()) {
    return "/* unsupported */";
  }
  if (context.useCombinedSamplerResources) {
    return "textureLod(" + emitExpression(*operands->texture, context) + ", " +
           emitExpression(*operands->coordinate, context) + ", " +
           (operands->lod == nullptr ? "0.0"
                                     : emitExpression(*operands->lod, context)) +
           ")";
  }
  return "textureLod(" + combinedSampler + "(" +
         emitExpression(*operands->texture, context) + ", " +
         emitExpression(*operands->sampler, context) + "), " +
         emitExpression(*operands->coordinate, context) + ", " +
         (operands->lod == nullptr ? "0.0"
                                   : emitExpression(*operands->lod, context)) +
         ")";
}

std::string glslShadowCompareArguments(const HIRType &textureType,
                                       const std::string &coordinate,
                                       const std::string &depth,
                                       bool explicitLod) {
  if (explicitLod) {
    if (textureType.name == "sampler2DShadow") {
      return "vec3(" + coordinate + ", " + depth + ")";
    }
    if (textureType.name == "sampler2DArrayShadow" ||
        textureType.name == "samplerCubeShadow") {
      return "vec4(" + coordinate + ", " + depth + ")";
    }
    if (textureType.name == "samplerCubeArrayShadow") {
      return coordinate + ", " + depth;
    }
    return "";
  }

  if (textureType.name == "sampler2DShadow" ||
      textureType.name == "sampler2DArrayShadow" ||
      textureType.name == "samplerCubeShadow") {
    const std::string constructor =
        textureType.name == "sampler2DShadow" ? "vec3" : "vec4";
    return constructor + "(" + coordinate + ", " + depth + ")";
  }
  if (textureType.name == "samplerCubeArrayShadow") {
    return coordinate + ", " + depth;
  }
  return "";
}

std::string emitTextureCompare(const HIRExpression &expression,
                               const OpenGLEmitContext &context) {
  const std::optional<TextureCompareManualOperands> manualOperands =
      textureCompareManualOperands(expression);
  if (manualOperands.has_value()) {
    const HIRExpression &texture = *manualOperands->texture;
    const std::string combinedSampler =
        glslManualCompareCombinedSamplerType(texture.type);
    const std::optional<TextureCompareOperator> compareOperator =
        textureCompareOperatorFromExpression(*manualOperands->compareOp);
    if (combinedSampler.empty() || !compareOperator.has_value()) {
      return "/* unsupported */";
    }

    const std::string compareConstant(
        textureCompareOperatorConstantName(*compareOperator));

    const auto rawSample = [&](std::string_view offset) {
      std::string sample =
          std::string(offset.empty() ? "textureLod(" : "textureLodOffset(") +
          combinedSampler + "(" + emitExpression(texture, context) + ", " +
          emitExpression(*manualOperands->sampler, context) + "), " +
          emitExpression(*manualOperands->coordinate, context) + ", " +
          emitExpression(*manualOperands->lod, context);
      if (!offset.empty()) {
        sample += ", " + std::string(offset);
      }
      sample += ").r";
      return sample;
    };
    const auto compareTap = [&](std::string_view offset) {
      return "cglCompareDepth(" + rawSample(offset) + ", " +
             emitExpression(*manualOperands->depth, context) + ", " +
             compareConstant + ")";
    };

    if (manualOperands->gather2x2) {
      return "((" + compareTap("ivec2(0, 0)") + " + " +
             compareTap("ivec2(1, 0)") + " + " +
             compareTap("ivec2(0, 1)") + " + " +
             compareTap("ivec2(1, 1)") + ") * 0.25)";
    }

    if (manualOperands->kernelTapCount != 0) {
      std::string result = "(";
      for (std::size_t index = 0; index < manualOperands->kernelTapCount;
           ++index) {
        if (index != 0) {
          result += " + ";
        }
        result += "(" +
                  compareTap(emitExpression(
                      *manualOperands->kernelOffsets[index], context)) +
                  " * " +
                  emitExpression(*manualOperands->kernelWeights[index],
                                 context) +
                  ")";
      }
      result += ")";
      return result;
    }

    const std::string offset =
        manualOperands->offset != nullptr
            ? emitExpression(*manualOperands->offset, context)
            : "";
    return compareTap(offset);
  }

  const std::optional<TextureCompareOperands> operands =
      textureCompareOperands(expression);
  if (!operands.has_value()) {
    return "/* unsupported */";
  }
  const HIRExpression &texture = *operands->texture;
  const std::string combinedSampler = glslCombinedSamplerType(texture.type);
  if (combinedSampler.empty()) {
    return "/* unsupported */";
  }
  const std::string textureName = emitExpression(texture, context);
  const std::string samplerName = emitExpression(*operands->sampler, context);
  const std::string coordinate = emitExpression(*operands->coordinate, context);
  const std::string depth = emitExpression(*operands->depth, context);
  const std::string compareArguments = glslShadowCompareArguments(
      texture.type, coordinate, depth, operands->explicitLod);
  if (compareArguments.empty()) {
    return "/* unsupported */";
  }

  const std::optional<std::string> textureResourceName =
      resourceReferenceBaseName(texture);
  const bool useCombinedTexture =
      context.useCombinedSamplerResources ||
      (operands->explicitLod && textureResourceName.has_value() &&
       context.combinedShadowCompareLodTextures.count(*textureResourceName) !=
           0);
  const std::string combined =
      useCombinedTexture
          ? textureName
          : combinedSampler + "(" + textureName + ", " + samplerName + ")";
  if (operands->explicitLod) {
    return "textureLod(" + combined + ", " + compareArguments + ", " +
           emitExpression(*operands->lod, context) +
           ")";
  }

  return "texture(" + combined + ", " + compareArguments + ")";
}

bool expressionIsManualTextureCompare(const HIRExpression &expression) {
  return textureCompareManualOperands(expression).has_value();
}

bool isStorageBufferArrayDescriptorIndex(const HIRExpression &expression,
                                         const OpenGLEmitContext &context) {
  return expression.kind == HIRExpressionKind::IndexAccess &&
         expression.children.size() == 2 &&
         expression.children[0].kind == HIRExpressionKind::Identifier &&
         context.storageBufferArrays.count(expression.children[0].value) != 0;
}

bool isOpenGLStaticZeroExpression(
    const HIRExpression &expression, const HIRModule &module,
    const std::set<std::string> &localIdentifiers) {
  if (expression.kind == HIRExpressionKind::Identifier &&
      localIdentifiers.count(expression.value) != 0) {
    return false;
  }
  if ((expression.kind == HIRExpressionKind::Group ||
       (expression.kind == HIRExpressionKind::Unary &&
        expression.value == "+")) &&
      expression.children.size() == 1) {
    return isOpenGLStaticZeroExpression(expression.children.front(), module,
                                        localIdentifiers);
  }
  const std::optional<std::size_t> index =
      staticResourceArrayIndexValue(expression, &module.constants);
  return index.has_value() && *index == 0;
}

std::optional<std::string>
renderOpenGLRuntimeTailBlockIndexAccess(const HIRExpression &expression,
                                        const OpenGLEmitContext &context) {
  if (expression.kind != HIRExpressionKind::IndexAccess ||
      expression.children.size() != 2 ||
      expression.children[0].kind != HIRExpressionKind::Identifier ||
      context.runtimeTailBlocks.count(expression.children[0].value) == 0 ||
      context.module == nullptr ||
      !isOpenGLStaticZeroExpression(expression.children[1], *context.module,
                                    context.localIdentifiers)) {
    return std::nullopt;
  }
  return emitExpression(expression.children[0], context);
}

std::string emitExpression(const HIRExpression &expression,
                           const OpenGLEmitContext &context) {
  switch (expression.kind) {
  case HIRExpressionKind::Empty:
    return "";
  case HIRExpressionKind::Identifier:
    return emitIdentifierName(expression.value, context);
  case HIRExpressionKind::Literal:
    return expression.value;
  case HIRExpressionKind::Group:
    return expression.children.empty()
               ? "()"
               : "(" + emitExpression(expression.children.front(), context) +
                     ")";
  case HIRExpressionKind::MemberAccess:
    return expression.children.empty()
               ? emitFieldName(expression.value, context)
               : emitExpression(expression.children.front(), context) + "." +
                     emitFieldName(expression.value, context);
  case HIRExpressionKind::IndexAccess:
    if (expression.children.size() == 2 &&
        isStorageBufferArrayDescriptorIndex(expression.children[0], context)) {
      const HIRExpression &descriptor = expression.children[0];
      const std::string resourceName = descriptor.children[0].value;
      return storageBufferArrayInstanceName(resourceName) + "[" +
             emitExpression(descriptor.children[1], context) + "]." +
             resourceName + "[" + emitExpression(expression.children[1], context) +
             "]";
    }
    if (const std::optional<std::string> runtimeTailBlock =
            renderOpenGLRuntimeTailBlockIndexAccess(expression, context)) {
      return *runtimeTailBlock;
    }
    return emitExpression(expression.children[0], context) + "[" +
           emitExpression(expression.children[1], context) + "]";
  case HIRExpressionKind::NonUniform:
    return expression.children.empty()
               ? "nonuniformEXT(/* unsupported */)"
               : "nonuniformEXT(" +
                     emitExpression(expression.children.front(), context) + ")";
  case HIRExpressionKind::Constructor: {
    std::ostringstream out;
    out << glslType(expression.type) << "(";
    for (std::size_t index = 0; index < expression.children.size(); ++index) {
      if (index != 0) {
        out << ", ";
      }
      out << emitExpression(expression.children[index], context);
    }
    out << ")";
    return out.str();
  }
  case HIRExpressionKind::Unary:
    return expression.value + emitExpression(expression.children.front(), context);
  case HIRExpressionKind::Binary:
    return emitExpression(expression.children[0], context) + " " +
           expression.value + " " + emitExpression(expression.children[1], context);
  case HIRExpressionKind::Call:
    return emitCall(expression, context);
  case HIRExpressionKind::Select:
    if (expression.children.size() < 3) {
      return "/* unsupported */";
    }
    return "(" + emitExpression(expression.children[0], context) + " ? " +
           emitExpression(expression.children[1], context) + " : " +
           emitExpression(expression.children[2], context) + ")";
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    return emitTextureCompare(expression, context);
  case HIRExpressionKind::TextureSample:
    return emitTextureSample(expression, context);
  }
  return "/* unsupported */";
}

std::string emitConstantValue(const HIRConstant &constant,
                              const OpenGLEmitContext &context) {
  if (constant.value.kind == HIRExpressionKind::Select &&
      constant.foldedValue.has_value()) {
    return *constant.foldedValue;
  }
  if (expressionSupported(constant.value)) {
    return emitExpression(constant.value, context);
  }
  return constant.foldedValue.value_or("/* unsupported */");
}

std::string emitStatementInline(const HIRStatement &statement,
                                const OpenGLEmitContext &context) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration: {
    std::ostringstream out;
    out << glslDeclarator(*context.module, statement.declaredType,
                          emitIdentifierName(statement.name, context));
    if (statement.value.kind != HIRExpressionKind::Empty) {
      out << " = " << emitExpression(statement.value, context);
    }
    return out.str();
  }
  case HIRStatementKind::Assignment:
    return emitExpression(statement.target, context) + " = " +
           emitExpression(statement.value, context);
  case HIRStatementKind::Expression:
    return emitExpression(statement.value, context);
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
    break;
  case HIRStatementKind::Return:
  case HIRStatementKind::Block:
  case HIRStatementKind::If:
  case HIRStatementKind::For:
  case HIRStatementKind::Raw:
    break;
  }
  return "";
}

std::string emitForInitializer(const HIRStatement &statement,
                               const OpenGLEmitContext &context) {
  return statement.initializer.empty()
             ? ""
             : emitStatementInline(statement.initializer.front(), context);
}

std::string emitForUpdate(const HIRStatement &statement,
                          const OpenGLEmitContext &context) {
  if (!statement.updateTokens.empty()) {
    return tokensToText(statement.updateTokens);
  }
  return statement.update.empty() ? ""
                                  : emitStatementInline(statement.update.front(),
                                                        context);
}

void emitStatement(std::ostringstream &out, const HIRStatement &statement,
                   std::size_t indentation,
                   const OpenGLEmitContext &context) {
  const std::string spaces(indentation, ' ');
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    out << spaces << glslDeclarator(*context.module, statement.declaredType,
                                    emitIdentifierName(statement.name, context));
    if (statement.value.kind != HIRExpressionKind::Empty) {
      out << " = " << emitExpression(statement.value, context);
    }
    out << ";\n";
    return;
  case HIRStatementKind::Assignment:
    out << spaces << emitExpression(statement.target, context) << " = "
        << emitExpression(statement.value, context) << ";\n";
    return;
  case HIRStatementKind::Return:
    out << spaces << "return";
    if (statement.value.kind != HIRExpressionKind::Empty) {
      out << " " << emitExpression(statement.value, context);
    }
    out << ";\n";
    return;
  case HIRStatementKind::Expression:
    out << spaces << emitExpression(statement.value, context) << ";\n";
    return;
  case HIRStatementKind::Break:
    out << spaces << "break;\n";
    return;
  case HIRStatementKind::Continue:
    out << spaces << "continue;\n";
    return;
  case HIRStatementKind::Discard:
    out << spaces << "discard;\n";
    return;
  case HIRStatementKind::Block:
    out << spaces << "{\n";
    for (const HIRStatement &child : statement.body) {
      emitStatement(out, child, indentation + 2, context);
    }
    out << spaces << "}\n";
    return;
  case HIRStatementKind::If:
    out << spaces << "if (" << emitExpression(statement.value, context)
        << ") {\n";
    for (const HIRStatement &child : statement.body) {
      emitStatement(out, child, indentation + 2, context);
    }
    if (!statement.elseBody.empty()) {
      out << spaces << "} else {\n";
      for (const HIRStatement &child : statement.elseBody) {
        emitStatement(out, child, indentation + 2, context);
      }
    }
    out << spaces << "}\n";
    return;
  case HIRStatementKind::For:
    out << spaces << "for (" << emitForInitializer(statement, context) << "; "
        << emitExpression(statement.value, context) << "; "
        << emitForUpdate(statement, context) << ") {\n";
    for (const HIRStatement &child : statement.body) {
      emitStatement(out, child, indentation + 2, context);
    }
    out << spaces << "}\n";
    return;
  case HIRStatementKind::Raw:
    out << spaces << "/* unsupported statement */\n";
    return;
  }
}

bool constantsSupported(const HIRModule &module) {
  return constantsSupportedByPolicy(module, constantSupported);
}

bool isSupportedUniformBufferResource(const HIRModule &module,
                                      const HIRResource &resource);

bool resourcesSupported(const HIRModule &module, const HIRStage &stage) {
  for (const HIRResource &resource : stage.resources) {
    if (resource.kind == HIRResourceKind::Shared) {
      if (!isSupportedSharedResourceType(resource.type)) {
        return false;
      }
      continue;
    }
    if (isSupportedStorageImageResource(resource)) {
      continue;
    }
    if (isSupportedUniformBufferResource(module, resource)) {
      continue;
    }
    if (!resourceSupportedByPolicy(module, resource,
                                   isSupportedStorageBufferElementType,
                                   isSupportedTextureResource,
                                   isSupportedSamplerResource)) {
      return false;
    }
  }
  return true;
}

bool isSupportedUniformBufferResource(const HIRModule &module,
                                      const HIRResource &resource) {
  if (resource.kind != HIRResourceKind::Uniform ||
      !supportedResourceArraySize(resource.type)) {
    return false;
  }
  const HIRStruct *structure = findStruct(module, resource.type.name);
  return structure != nullptr && openGLGraphicsStructSupported(*structure);
}

bool isOpenGLGraphicsStage(std::string_view stageName) {
  return stageName == "vertex" || stageName == "fragment";
}

bool openGLGraphicsResourceSupported(const HIRModule &module,
                                     const HIRStage &stage,
                                     const HIRResource &resource) {
  if (isSupportedUniformBufferResource(module, resource)) {
    return true;
  }
  if (!isOpenGLGraphicsStage(stage.stage)) {
    return false;
  }
  const HIRType elementType = arrayElementType(resource.type);
  if (isSupportedTextureResource(resource) &&
      (!isComparisonTextureTypeName(resource.type.name) ||
       textureCompareShape(elementType) != TextureCompareShape::Unknown)) {
    return true;
  }
  if (isSupportedSamplerResource(resource) &&
      (elementType.name == "sampler" ||
       elementType.name == "comparison_sampler")) {
    return true;
  }
  return false;
}

bool openGLGraphicsStageResourcesSupported(const HIRModule &module,
                                           const HIRStage &stage) {
  for (const HIRResource &resource : stage.resources) {
    if (!openGLGraphicsResourceSupported(module, stage, resource)) {
      return false;
    }
  }
  return true;
}

bool openGLGraphicsResourceBindingIdentityMatches(const HIRResource &lhs,
                                                  const HIRResource &rhs) {
  return lhs.kind == rhs.kind && lhs.name == rhs.name &&
         typeEquals(lhs.type, rhs.type);
}

bool openGLGraphicsResourceHasProgramBinding(const HIRModule &module,
                                             const HIRResource &resource) {
  return isSupportedUniformBufferResource(module, resource) ||
         isSupportedTextureResource(resource) ||
         isSupportedSamplerResource(resource);
}

std::size_t openGLGraphicsResourceBindingKey(const HIRResource &resource) {
  return backendPlanOpenGLBindingIndex(resource.set, resource.binding);
}

std::string openGLGraphicsBindingLabel(std::string_view stageName,
                                       const HIRResource &resource) {
  return std::string(stageName) + "." + resource.name + " (" +
         resourceKindLabel(resource.kind) + ", type " +
         formatType(resource.type) + ", set " + std::to_string(resource.set) +
         ", binding " + std::to_string(resource.binding) + ")";
}

std::set<std::string> ambiguousOpenGLGraphicsResourceBindingLabels(
    const HIRModule &module, const HIRStage &vertex,
    const HIRStage &fragment) {
  std::set<std::string> labels;
  for (const HIRResource &vertexResource : vertex.resources) {
    if (!openGLGraphicsResourceHasProgramBinding(module, vertexResource)) {
      continue;
    }
    for (const HIRResource &fragmentResource : fragment.resources) {
      if (!openGLGraphicsResourceHasProgramBinding(module, fragmentResource) ||
          vertexResource.kind != fragmentResource.kind ||
          openGLGraphicsResourceBindingKey(vertexResource) !=
              openGLGraphicsResourceBindingKey(fragmentResource) ||
          openGLGraphicsResourceBindingIdentityMatches(vertexResource,
                                                       fragmentResource)) {
        continue;
      }
      labels.insert(openGLGraphicsBindingLabel(vertex.stage, vertexResource) +
                    " conflicts with " +
                    openGLGraphicsBindingLabel(fragment.stage,
                                               fragmentResource));
    }
  }
  return labels;
}

bool openGLGraphicsResourceBindingsSupported(const HIRModule &module,
                                             const HIRStage &vertex,
                                             const HIRStage &fragment) {
  return ambiguousOpenGLGraphicsResourceBindingLabels(module, vertex, fragment)
      .empty();
}

const TargetLegalizationResourceBindingRecord *
findOpenGLProgramResourceBindingRecord(const OpenGLEmitContext &context,
                                       const HIRResource &resource) {
  if (context.resourceBindings == nullptr) {
    return nullptr;
  }
  const std::string kind = resourceKindName(resource.kind);
  for (const TargetLegalizationResourceBindingRecord &record :
       context.resourceBindings->records) {
    if (record.target == TargetKind::OpenGL &&
        record.abi == "programResourceBinding" &&
        record.stage == context.stage &&
        record.backendEntryPoint == context.backendEntryPoint &&
        record.name == resource.name && record.kind == kind) {
      return &record;
    }
  }
  return nullptr;
}

std::optional<std::size_t>
legalizedOpenGLResourceBindingIndex(const OpenGLEmitContext &context,
                                    const HIRResource &resource) {
  const TargetLegalizationResourceBindingRecord *record =
      findOpenGLProgramResourceBindingRecord(context, resource);
  if (record != nullptr) {
    return record->argumentIndex;
  }
  if (context.resourceBindings != nullptr) {
    return std::nullopt;
  }
  return openglResourceBindingIndex(resource);
}

std::size_t openGLResourceBindingIndexForEmission(
    const OpenGLEmitContext &context, const HIRResource &resource) {
  const std::optional<std::size_t> bindingIndex =
      legalizedOpenGLResourceBindingIndex(context, resource);
  return bindingIndex.value_or(openglResourceBindingIndex(resource));
}

void emitResourceDeclaration(std::ostringstream &out,
                             const HIRModule &module,
                             const HIRResource &resource,
                             const OpenGLEmitContext &context) {
  const std::size_t bindingIndex =
      openGLResourceBindingIndexForEmission(context, resource);
  if (isSupportedUniformBufferResource(module, resource)) {
    const HIRStruct &structure = *findStruct(module, resource.type.name);
    out << "// CrossGL set " << resource.set << ", binding "
        << resource.binding << "\n";
    out << "layout(binding = " << bindingIndex << ", std140) uniform "
        << resource.name << "_Uniform {\n";
    for (const HIRField &field : structure.fields) {
      out << "  " << glslStructFieldType(module, field.type) << " "
          << emitFieldName(field.name, context) << ";\n";
    }
    out << "} " << resource.name << resourceArraySuffix(resource.type)
        << ";\n\n";
    return;
  }
  if (isSupportedStorageImageResource(resource)) {
    out << "// CrossGL set " << resource.set << ", binding "
        << resource.binding << "\n";
    out << "layout(binding = " << bindingIndex << ", "
        << glslStorageImageFormat(resource) << ") "
        << glslStorageImageAccessQualifier(resource) << "uniform "
        << glslStorageImageType(resource.type) << " " << resource.name
        << resourceArraySuffix(resource.type) << ";\n\n";
    return;
  }
  if (resource.kind == HIRResourceKind::Buffer) {
    if (const HIRStruct *runtimeTailBlock =
            openGLRuntimeTailBlockStruct(module, resource)) {
      out << "// CrossGL set " << resource.set << ", binding "
          << resource.binding << "\n";
      out << "layout(binding = " << bindingIndex << ", std430) buffer "
          << resource.name << "_Buffer {\n";
      for (const HIRField &field : runtimeTailBlock->fields) {
        out << "  " << glslStructFieldType(module, field.type) << " "
            << field.name;
        if (field.type.arraySize.has_value()) {
          out << "[" << *field.type.arraySize << "]";
        }
        out << ";\n";
      }
      out << "} " << resource.name << ";\n\n";
      return;
    }
    out << "// CrossGL set " << resource.set << ", binding "
        << resource.binding << "\n";
    out << "layout(binding = " << bindingIndex << ", std430) buffer "
        << resource.name << "_Buffer {\n";
    out << "  "
        << glslStorageBufferElementType(module, bufferElementType(resource.type))
        << " " << resource.name << "[];\n";
    out << "}";
    if (resource.type.arraySize.has_value()) {
      out << " " << storageBufferArrayInstanceName(resource.name)
          << resourceArraySuffix(resource.type);
    }
    out << ";\n\n";
    return;
  }
  if (resource.kind == HIRResourceKind::Texture) {
    out << "// CrossGL set " << resource.set << ", binding "
        << resource.binding << "\n";
    if (context.useCombinedSamplerResources ||
        context.combinedShadowCompareLodTextures.count(resource.name) != 0) {
      out << "layout(binding = " << bindingIndex << ") uniform "
          << glslCombinedSamplerType(resource.type) << " "
          << resource.name << resourceArraySuffix(resource.type) << ";\n\n";
      return;
    }
    out << "layout(binding = " << bindingIndex << ") uniform "
        << glslTextureType(resource.type) << " "
        << resource.name << resourceArraySuffix(resource.type) << ";\n\n";
    return;
  }
  if (resource.kind == HIRResourceKind::Sampler) {
    out << "// CrossGL set " << resource.set << ", binding "
        << resource.binding << "\n";
    if (context.useCombinedSamplerResources ||
        context.combinedShadowCompareLodSamplers.count(resource.name) != 0) {
      out << "// sampler " << resource.name
          << " is represented by OpenGL combined sampler uniforms.\n\n";
      return;
    }
    out << "layout(binding = " << bindingIndex << ") uniform sampler "
        << resource.name
        << resourceArraySuffix(resource.type) << ";\n\n";
    return;
  }
  if (resource.kind == HIRResourceKind::Shared) {
    if (const std::optional<std::string> atomicType =
            glslAtomicIntegerStorageType(resource.type)) {
      out << "shared " << *atomicType << " " << resource.name
          << glslArraySuffix(resource.type) << ";\n\n";
      return;
    }
    out << "shared " << glslDeclarator(module, resource.type, resource.name)
        << ";\n\n";
    return;
  }
}

void emitManualCompareHelper(std::ostringstream &out) {
  out << "const int CGL_COMPARE_NEVER = 0;\n";
  out << "const int CGL_COMPARE_ALWAYS = 1;\n";
  out << "const int CGL_COMPARE_LESS = 2;\n";
  out << "const int CGL_COMPARE_LESS_EQUAL = 3;\n";
  out << "const int CGL_COMPARE_EQUAL = 4;\n";
  out << "const int CGL_COMPARE_NOT_EQUAL = 5;\n";
  out << "const int CGL_COMPARE_GREATER_EQUAL = 6;\n";
  out << "const int CGL_COMPARE_GREATER = 7;\n\n";
  out << "float cglCompareDepth(float sampledDepth, float referenceDepth, "
         "int compareOp) {\n";
  out << "  if (compareOp == CGL_COMPARE_NEVER) {\n";
  out << "    return 0.0;\n";
  out << "  }\n";
  out << "  if (compareOp == CGL_COMPARE_ALWAYS) {\n";
  out << "    return 1.0;\n";
  out << "  }\n";
  out << "  if (compareOp == CGL_COMPARE_LESS) {\n";
  out << "    return referenceDepth < sampledDepth ? 1.0 : 0.0;\n";
  out << "  }\n";
  out << "  if (compareOp == CGL_COMPARE_LESS_EQUAL) {\n";
  out << "    return referenceDepth <= sampledDepth ? 1.0 : 0.0;\n";
  out << "  }\n";
  out << "  if (compareOp == CGL_COMPARE_EQUAL) {\n";
  out << "    return referenceDepth == sampledDepth ? 1.0 : 0.0;\n";
  out << "  }\n";
  out << "  if (compareOp == CGL_COMPARE_NOT_EQUAL) {\n";
  out << "    return referenceDepth != sampledDepth ? 1.0 : 0.0;\n";
  out << "  }\n";
  out << "  if (compareOp == CGL_COMPARE_GREATER_EQUAL) {\n";
  out << "    return referenceDepth >= sampledDepth ? 1.0 : 0.0;\n";
  out << "  }\n";
  out << "  return referenceDepth > sampledDepth ? 1.0 : 0.0;\n";
  out << "}\n\n";
}

bool moduleUsesManualTextureCompare(const HIRModule &module) {
  return moduleExpressionsContain(module, expressionIsManualTextureCompare,
                                  true);
}

void emitStructDeclaration(std::ostringstream &out,
                           const HIRModule &module,
                           const HIRStruct &structure,
                           const OpenGLEmitContext &context) {
  out << "struct " << structure.name << " {\n";
  for (const HIRField &field : structure.fields) {
    out << "  " << glslStructFieldType(module, field.type) << " "
        << emitFieldName(field.name, context);
    if (field.type.arraySize.has_value()) {
      out << "[" << *field.type.arraySize << "]";
    }
    out << ";\n";
  }
  out << "};\n";
}

void collectOpenGLStructDeclaration(const HIRModule &module,
                                    const HIRStruct &structure,
                                    std::set<std::string> &emitted,
                                    std::set<std::string> &visiting,
                                    std::vector<const HIRStruct *> &ordered,
                                    bool includeSelf) {
  if (emitted.count(structure.name) != 0 ||
      !visiting.insert(structure.name).second) {
    return;
  }
  for (const HIRField &field : structure.fields) {
    const HIRStruct *nested = findStruct(module, baseTypeName(field.type));
    if (nested != nullptr) {
      collectOpenGLStructDeclaration(module, *nested, emitted, visiting,
                                     ordered, true);
    }
  }
  visiting.erase(structure.name);
  if (includeSelf && emitted.insert(structure.name).second) {
    ordered.push_back(&structure);
  }
}

std::vector<const HIRStruct *>
openGLStorageBufferStructDeclarations(const HIRModule &module,
                                      const HIRStage &stage) {
  std::vector<const HIRStruct *> ordered;
  std::set<std::string> emitted;
  std::set<std::string> visiting;
  for (const HIRResource &resource : stage.resources) {
    if (resource.kind != HIRResourceKind::Buffer ||
        !supportedResourceArraySize(resource.type)) {
      continue;
    }
    const HIRType elementType = bufferElementType(resource.type);
    const HIRStruct *structure = findStruct(module, elementType.name);
    if (structure == nullptr) {
      continue;
    }
    if (openGLRuntimeTailBlockStruct(module, resource) != nullptr) {
      collectOpenGLStructDeclaration(module, *structure, emitted, visiting,
                                     ordered, false);
      continue;
    }
    if (openglStructStorageBufferElementSupported(module, *structure)) {
      collectOpenGLStructDeclaration(module, *structure, emitted, visiting,
                                     ordered, true);
    }
  }
  return ordered;
}

void appendOpenGLGraphicsStructDeclaration(const HIRModule &module,
                                           const HIRStruct *structure,
                                           std::set<std::string> &emitted,
                                           std::set<std::string> &visiting,
                                           std::vector<const HIRStruct *> &ordered) {
  if (structure != nullptr) {
    collectOpenGLStructDeclaration(module, *structure, emitted, visiting, ordered,
                                   true);
  }
}

std::vector<const HIRStruct *>
openGLGraphicsStructDeclarations(const HIRModule &module,
                                 const HIRFunction &vertexEntry,
                                 const HIRFunction &fragmentEntry) {
  std::vector<const HIRStruct *> ordered;
  std::set<std::string> emitted;
  std::set<std::string> visiting;
  appendOpenGLGraphicsStructDeclaration(
      module, openGLStructType(module, vertexEntry.parameters.front().type),
      emitted, visiting, ordered);
  appendOpenGLGraphicsStructDeclaration(
      module, openGLStructType(module, vertexEntry.returnType), emitted,
      visiting, ordered);
  appendOpenGLGraphicsStructDeclaration(
      module, openGLStructType(module, fragmentEntry.parameters.front().type),
      emitted, visiting, ordered);
  appendOpenGLGraphicsStructDeclaration(
      module, openGLStructType(module, fragmentEntry.returnType), emitted,
      visiting, ordered);
  return ordered;
}

bool expressionSupported(const HIRExpression &expression,
                         const OpenGLSupportContext &context);

bool textureOperandSupported(const HIRExpression &expression,
                             const OpenGLSupportContext &context) {
  if (!isResourceReferenceExpression(expression)) {
    return false;
  }
  return !isComparisonTextureTypeName(expression.type.name) &&
         !glslCombinedSamplerType(expression.type).empty() &&
         expressionSupported(expression, context);
}

bool comparisonTextureOperandSupported(const HIRExpression &expression,
                                       const OpenGLSupportContext &context) {
  if (!isResourceReferenceExpression(expression)) {
    return false;
  }
  return isComparisonTextureTypeName(expression.type.name) &&
         !glslCombinedSamplerType(expression.type).empty() &&
         expressionSupported(expression, context);
}

bool samplerOperandSupported(const HIRExpression &expression,
                             const OpenGLSupportContext &context) {
  if (!isResourceReferenceExpression(expression)) {
    return false;
  }
  return (expression.type.name == "sampler" ||
          expression.type.name == "comparison_sampler") &&
         !expression.type.arraySize.has_value() &&
         expressionSupported(expression, context);
}

bool rawSamplerOperandSupported(const HIRExpression &expression,
                                const OpenGLSupportContext &context) {
  if (!isResourceReferenceExpression(expression)) {
    return false;
  }
  return expression.type.name == "sampler" &&
         !expression.type.arraySize.has_value() &&
         expressionSupported(expression, context);
}

bool textureSampleSupported(const HIRExpression &expression,
                            const OpenGLSupportContext &context) {
  const std::optional<OpenGLTextureSampleOperands> operands =
      openGLTextureSampleOperands(expression);
  if (!operands.has_value() || !isSupportedValueType(expression.type) ||
      !textureOperandSupported(*operands->texture, context) ||
      !rawSamplerOperandSupported(*operands->sampler, context) ||
      !expressionSupported(*operands->coordinate, context)) {
    return false;
  }
  if (operands->lod == nullptr) {
    return context.stage != nullptr && context.stage->stage == "compute";
  }
  return expressionSupported(*operands->lod, context);
}

bool textureCompareSupported(const HIRExpression &expression,
                             const OpenGLSupportContext &context) {
  if (textureCompareManualOperands(expression).has_value()) {
    return textureCompareManualSupportedByPolicy(
        expression,
        [&](const HIRExpression &operand) {
          return comparisonTextureOperandSupported(operand, context);
        },
        [&](const HIRExpression &operand) {
          return rawSamplerOperandSupported(operand, context);
        },
        [&](const HIRExpression &child) {
          return expressionSupported(child, context);
        });
  }
  const std::optional<TextureCompareOperands> operands =
      textureCompareOperands(expression);
  if (operands.has_value() && operands->explicitLod &&
      !openGLExplicitLodShadowCompareOperandsSupported(*operands, context)) {
    return false;
  }
  return textureCompareSupportedByPolicy(
      expression,
      [&](const HIRExpression &operand) {
        return comparisonTextureOperandSupported(operand, context);
      },
      [&](const HIRExpression &operand) {
        return samplerOperandSupported(operand, context);
      },
      [&](const HIRExpression &child) {
        return expressionSupported(child, context);
      },
      [&](const HIRExpression &texture) {
        return openGLExplicitLodShadowCompareTextureSupported(texture, context);
      });
}

bool isOpenGLStorageImageCallName(std::string_view name) {
  return name == "imageLoad" || name == "imageStore" ||
         name == "imageAtomicAdd" || name == "imageAtomicExchange" ||
         name == "imageAtomicMin" || name == "imageAtomicMax" ||
         name == "imageAtomicAnd" || name == "imageAtomicOr" ||
         name == "imageAtomicXor";
}

bool openGLStorageImageOperandSupported(const HIRExpression &expression,
                                        const OpenGLSupportContext &context) {
  return isResourceReferenceExpression(expression) &&
         !expression.type.arraySize.has_value() &&
         !glslStorageImageType(expression.type).empty() &&
         expressionSupported(expression, context);
}

bool openGLStorageImageCoordinateSupported(
    const HIRExpression &image, const HIRExpression &coordinate,
    const OpenGLSupportContext &context) {
  const std::string coordinateType = glslStorageImageCoordinateType(image.type);
  return !coordinateType.empty() && !coordinate.type.arraySize.has_value() &&
         coordinate.type.name == coordinateType &&
         expressionSupported(coordinate, context);
}

bool openGLStorageImageLoadSupported(const HIRExpression &expression,
                                     const OpenGLSupportContext &context) {
  if (expression.value != "imageLoad" || expression.children.size() != 2) {
    return false;
  }
  const HIRExpression &image = expression.children[0];
  const std::string payloadType = glslStorageImagePayloadType(image.type);
  if (payloadType.empty() ||
      (!expression.type.name.empty() &&
       (expression.type.arraySize.has_value() ||
        expression.type.name != payloadType))) {
    return false;
  }
  return openGLStorageImageOperandSupported(image, context) &&
         openGLStorageImageCoordinateSupported(image, expression.children[1],
                                              context);
}

bool openGLStorageImageStoreSupported(const HIRExpression &expression,
                                      const OpenGLSupportContext &context) {
  if (expression.value != "imageStore" || expression.children.size() != 3 ||
      (!expression.type.name.empty() &&
       (expression.type.arraySize.has_value() ||
        expression.type.name != "void"))) {
    return false;
  }
  const HIRExpression &image = expression.children[0];
  const HIRExpression &value = expression.children[2];
  const std::string payloadType = glslStorageImagePayloadType(image.type);
  if (payloadType.empty() || value.type.arraySize.has_value() ||
      value.type.name != payloadType) {
    return false;
  }
  return openGLStorageImageOperandSupported(image, context) &&
         openGLStorageImageCoordinateSupported(image, expression.children[1],
                                              context) &&
         expressionSupported(value, context);
}

bool openGLStorageImageAtomicSupported(const HIRExpression &expression,
                                       const OpenGLSupportContext &context) {
  if ((expression.value != "imageAtomicAdd" &&
       expression.value != "imageAtomicExchange" &&
       expression.value != "imageAtomicMin" &&
       expression.value != "imageAtomicMax" &&
       expression.value != "imageAtomicAnd" &&
       expression.value != "imageAtomicOr" &&
       expression.value != "imageAtomicXor") ||
      expression.children.size() != 3) {
    return false;
  }

  const HIRExpression &image = expression.children[0];
  const HIRExpression &value = expression.children[2];
  const std::string payloadType = glslStorageImageAtomicPayloadType(image.type);
  if (payloadType.empty() || expression.type.arraySize.has_value() ||
      (!expression.type.name.empty() && expression.type.name != payloadType) ||
      value.type.arraySize.has_value() || value.type.name != payloadType) {
    return false;
  }

  const std::optional<std::string> resourceName =
      resourceReferenceBaseName(image);
  const HIRResource *resource =
      resourceName.has_value() ? findOpenGLStageResource(context, *resourceName)
                               : nullptr;
  if (resource == nullptr || resource->kind != HIRResourceKind::StorageImage ||
      !storageImageAccessAllowsRead(resource->storageImageAccess) ||
      !storageImageAccessAllowsWrite(resource->storageImageAccess) ||
      !storageImageFormatSupportsAtomics(resolvedStorageImageFormatName(*resource),
                                         baseTypeName(image.type))) {
    return false;
  }

  return openGLStorageImageOperandSupported(image, context) &&
         openGLStorageImageCoordinateSupported(image, expression.children[1],
                                              context) &&
         expressionSupported(value, context);
}

bool openGLStorageImageCallSupported(const HIRExpression &expression,
                                     const OpenGLSupportContext &context) {
  if (expression.kind != HIRExpressionKind::Call ||
      !isOpenGLStorageImageCallName(expression.value)) {
    return false;
  }
  return openGLStorageImageLoadSupported(expression, context) ||
         openGLStorageImageStoreSupported(expression, context) ||
         openGLStorageImageAtomicSupported(expression, context);
}

bool intrinsicCallSupported(const HIRExpression &expression,
                            const OpenGLSupportContext &context) {
  if (isOpenGLWorkgroupBarrierCall(expression)) {
    return true;
  }
  if (openGLStorageImageCallSupported(expression, context)) {
    return true;
  }
  if (isOpenGLAtomicIntegerCallName(expression.value)) {
    return false;
  }
  if (!backendIntrinsicCallSupported(TargetKind::OpenGL, expression) ||
      !isSupportedValueType(expression.type)) {
    return false;
  }
  for (const HIRExpression &argument : expression.children) {
    if (!expressionSupported(argument, context)) {
      return false;
    }
  }
  return true;
}

bool argumentTypeMatchesParameter(const HIRType &argument,
                                  const HIRType &parameter) {
  if (parameter.arraySize.has_value()) {
    return argument.name == parameter.name &&
           argument.arraySize == parameter.arraySize;
  }
  return argument.name.empty() ||
         (argument.name == parameter.name &&
          argument.arraySize == parameter.arraySize);
}

bool userFunctionCallSupported(const HIRExpression &expression,
                               const OpenGLSupportContext &context) {
  if (context.module == nullptr || expression.value.empty()) {
    return false;
  }
  const HIRFunction *function = findStageFunction(context, expression.value);
  if (function == nullptr ||
      !isSupportedFunctionReturnType(*context.module, function->returnType) ||
      expression.children.size() != function->parameters.size()) {
    return false;
  }
  if (context.function == nullptr ||
      !openGLFunctionParameterArrayCallFeaturesSupported(
          *context.module, *context.function, *function, expression,
          context.stage)) {
    return false;
  }
  for (std::size_t index = 0; index < function->parameters.size(); ++index) {
    const HIRParameter &parameter = function->parameters[index];
    const HIRExpression &argument = expression.children[index];
    if (!isSupportedFunctionValueType(*context.module, parameter.type) ||
        !argumentTypeMatchesParameter(argument.type, parameter.type) ||
        !expressionSupported(argument, context)) {
      return false;
    }
  }
  return true;
}

bool selectExpressionSupported(const HIRExpression &expression,
                               const OpenGLSupportContext &context) {
  if (expression.children.size() != 3 ||
      !isSupportedValueType(expression.type)) {
    return false;
  }
  const HIRExpression &condition = expression.children[0];
  if (condition.type.name != "bool" || condition.type.arraySize.has_value()) {
    return false;
  }
  return expressionSupported(condition, context) &&
         expressionSupported(expression.children[1], context) &&
         expressionSupported(expression.children[2], context);
}

bool expressionSupported(const HIRExpression &expression,
                         const OpenGLSupportContext &context) {
  if (expression.kind == HIRExpressionKind::Call) {
    return intrinsicCallSupported(expression, context) ||
           userFunctionCallSupported(expression, context);
  }
  if (expression.kind == HIRExpressionKind::Select) {
    return selectExpressionSupported(expression, context);
  }
  return expressionSupportedByPolicy(
      expression,
      [&](const HIRExpression &child) {
        return expressionSupported(child, context);
      },
      [&](const HIRExpression &sample) {
        return textureSampleSupported(sample, context);
      },
      [&](const HIRExpression &compare) {
        return textureCompareSupported(compare, context);
      },
      [&](const HIRExpression &constructor) {
        return backendConstructorShapeSupported(
            constructor, isSupportedValueType, [&](const HIRExpression &child) {
              return expressionSupported(child, context);
            });
      });
}

bool expressionSupported(const HIRExpression &expression) {
  return expressionSupported(expression, OpenGLSupportContext{});
}

bool constantSupported(const HIRConstant &constant) {
  return isSupportedValueType(constant.type) &&
         (expressionSupported(constant.value) || constant.foldedValue.has_value());
}

const HIRExpression *rootIdentifierExpression(const HIRExpression &expression) {
  const HIRExpression *current = &expression;
  while ((current->kind == HIRExpressionKind::Group ||
          current->kind == HIRExpressionKind::NonUniform ||
          current->kind == HIRExpressionKind::MemberAccess ||
          current->kind == HIRExpressionKind::IndexAccess) &&
         !current->children.empty()) {
    current = &current->children.front();
  }
  return current->kind == HIRExpressionKind::Identifier ? current : nullptr;
}

std::set<std::string> fixedOpenGLArrayParameterNames(
    const HIRModule &module, const HIRFunction &function) {
  std::set<std::string> names;
  for (const HIRParameter &parameter : function.parameters) {
    if (functionParameterArrayShape(module, parameter.type) ==
        HIRFunctionParameterArrayShape::FixedSize) {
      names.insert(parameter.name);
    }
  }
  return names;
}

std::optional<std::size_t>
fixedOpenGLArrayParameterIndex(const HIRModule &module,
                               const HIRFunction &function,
                               std::string_view parameterName) {
  for (std::size_t index = 0; index < function.parameters.size(); ++index) {
    const HIRParameter &parameter = function.parameters[index];
    if (parameter.name == parameterName &&
        functionParameterArrayShape(module, parameter.type) ==
            HIRFunctionParameterArrayShape::FixedSize) {
      return index;
    }
  }
  return std::nullopt;
}

void collectOpenGLFunctionParameterArrayWritesInStatement(
    const HIRFunction &function, const std::set<std::string> &parameterArrays,
    const HIRStatement &statement, std::set<std::string> &parameterNames) {
  (void)function;
  if (statement.kind == HIRStatementKind::Assignment) {
    const HIRExpression *root = rootIdentifierExpression(statement.target);
    if (root != nullptr && parameterArrays.count(root->value) != 0) {
      parameterNames.insert(root->value);
    }
  }

  for (const HIRStatement &child : statement.initializer) {
    collectOpenGLFunctionParameterArrayWritesInStatement(
        function, parameterArrays, child, parameterNames);
  }
  for (const HIRStatement &child : statement.update) {
    collectOpenGLFunctionParameterArrayWritesInStatement(
        function, parameterArrays, child, parameterNames);
  }
  for (const HIRStatement &child : statement.body) {
    collectOpenGLFunctionParameterArrayWritesInStatement(
        function, parameterArrays, child, parameterNames);
  }
  for (const HIRStatement &child : statement.elseBody) {
    collectOpenGLFunctionParameterArrayWritesInStatement(
        function, parameterArrays, child, parameterNames);
  }
}

std::set<std::string>
writtenOpenGLFunctionParameterArrayNames(const HIRModule &module,
                                         const HIRFunction &function) {
  std::set<std::string> parameterNames;
  const std::set<std::string> parameterArrays =
      fixedOpenGLArrayParameterNames(module, function);
  if (parameterArrays.empty()) {
    return parameterNames;
  }
  for (const HIRStatement &statement : function.body) {
    collectOpenGLFunctionParameterArrayWritesInStatement(
        function, parameterArrays, statement, parameterNames);
  }
  return parameterNames;
}

bool openGLFunctionParameterArrayHasCallFeature(
    const std::vector<HIRFunctionParameterArrayCallFeature> &features,
    HIRFunctionParameterArrayCallFeature expected) {
  return std::find(features.begin(), features.end(), expected) !=
         features.end();
}

bool openGLLocalArrayCopyArgument(const HIRModule &module,
                                  const HIRFunction &caller,
                                  const HIRExpression &argument,
                                  const HIRStage *stage) {
  if (functionParameterArrayShape(module, argument.type) !=
      HIRFunctionParameterArrayShape::FixedSize) {
    return false;
  }

  const std::vector<HIRFunctionParameterArrayCallFeature> features =
      functionParameterArrayCallArgumentFeatures(module, caller, argument,
                                                 stage);
  if (openGLFunctionParameterArrayCallFeaturesSupport(features) !=
      HIRFunctionParameterArrayCallFeatureSupport::Supported) {
    return false;
  }
  return openGLFunctionParameterArrayHasCallFeature(
             features, HIRFunctionParameterArrayCallFeature::
                           LocalArrayArguments) &&
         !openGLFunctionParameterArrayHasCallFeature(
             features, HIRFunctionParameterArrayCallFeature::
                           FunctionParameterArguments) &&
         !openGLFunctionParameterArrayHasCallFeature(
             features, HIRFunctionParameterArrayCallFeature::
                           StorageBufferFieldArguments) &&
         !openGLFunctionParameterArrayHasCallFeature(
             features, HIRFunctionParameterArrayCallFeature::
                           NestedStructFieldArguments) &&
         !openGLFunctionParameterArrayHasCallFeature(
             features, HIRFunctionParameterArrayCallFeature::
                           DirectResourceArrayArguments);
}

bool openGLFunctionParameterArrayWriteArgumentAliases(
    const HIRModule &module, const HIRFunction &function,
    const HIRExpression &call, std::size_t parameterIndex) {
  if (call.children.size() <= parameterIndex) {
    return false;
  }
  const HIRExpression *writtenRoot =
      rootIdentifierExpression(call.children[parameterIndex]);
  if (writtenRoot == nullptr) {
    return false;
  }

  for (std::size_t index = 0; index < function.parameters.size(); ++index) {
    if (index == parameterIndex || call.children.size() <= index ||
        functionParameterArrayShape(module, function.parameters[index].type) !=
            HIRFunctionParameterArrayShape::FixedSize) {
      continue;
    }
    const HIRExpression *otherRoot = rootIdentifierExpression(
        call.children[index]);
    if (otherRoot != nullptr && otherRoot->value == writtenRoot->value) {
      return true;
    }
  }
  return false;
}

bool openGLFunctionParameterArrayWriteUsesOnlyLocalCopyArguments(
    const HIRModule &module, const HIRFunction &function,
    std::size_t parameterIndex) {
  bool supported = true;
  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &caller : stage.functions) {
      auto visitor = [&](const HIRExpression &expression) {
        if (!supported || expression.kind != HIRExpressionKind::Call ||
            expression.value != function.name) {
          return;
        }
        if (expression.children.size() <= parameterIndex ||
            !openGLLocalArrayCopyArgument(module, caller,
                                          expression.children[parameterIndex],
                                          &stage) ||
            openGLFunctionParameterArrayWriteArgumentAliases(
                module, function, expression, parameterIndex)) {
          supported = false;
        }
      };
      visitFunctionExpressions(caller, visitor);
    }
  }
  return supported;
}

void collectUnsupportedOpenGLFunctionParameterArrayWrites(
    const HIRModule &module, const HIRFunction &function,
    std::set<std::string> &labels) {
  for (const std::string &parameterName :
       writtenOpenGLFunctionParameterArrayNames(module, function)) {
    const std::optional<std::size_t> parameterIndex =
        fixedOpenGLArrayParameterIndex(module, function, parameterName);
    if (!parameterIndex.has_value() ||
        !openGLFunctionParameterArrayWriteUsesOnlyLocalCopyArguments(
            module, function, *parameterIndex)) {
      labels.insert(function.name + "." + parameterName);
    }
  }
}

std::set<std::string>
unsupportedOpenGLFunctionParameterArrayWriteLabels(const HIRModule &module) {
  std::set<std::string> labels;
  for (const HIRFunction &function : module.functions) {
    collectUnsupportedOpenGLFunctionParameterArrayWrites(module, function,
                                                        labels);
  }
  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &function : stage.functions) {
      collectUnsupportedOpenGLFunctionParameterArrayWrites(module, function,
                                                          labels);
    }
  }
  return labels;
}

const HIRResource *findOpenGLStageResource(const OpenGLSupportContext &context,
                                           std::string_view name) {
  if (context.stage == nullptr) {
    return nullptr;
  }
  for (const HIRResource &resource : context.stage->resources) {
    if (resource.name == name) {
      return &resource;
    }
  }
  return nullptr;
}

bool openGLResourceReferenceHasArrayBase(
    const HIRExpression &expression, const OpenGLSupportContext &context) {
  const std::optional<std::string> resourceName =
      resourceReferenceBaseName(expression);
  if (!resourceName.has_value()) {
    return false;
  }
  const HIRResource *resource = findOpenGLStageResource(context, *resourceName);
  return resource != nullptr && resource->type.arraySize.has_value();
}

bool openGLExplicitLodShadowCompareTextureSupported(
    const HIRExpression &texture, const OpenGLSupportContext &context) {
  (void)context;
  const TextureCompareShape shape = textureCompareShape(texture.type);
  return shape != TextureCompareShape::Unknown;
}

bool openGLExplicitLodShadowCompareOperandsSupported(
    const TextureCompareOperands &operands,
    const OpenGLSupportContext &context) {
  return operands.texture != nullptr &&
         openGLExplicitLodShadowCompareTextureSupported(*operands.texture,
                                                        context);
}

bool expressionHasUnsupportedShadowCompareExplicitLodShape(
    const HIRExpression &expression, const OpenGLSupportContext &context) {
  const std::optional<TextureCompareOperands> operands =
      textureCompareOperands(expression);
  if (!operands.has_value() || !operands->explicitLod ||
      operands->texture == nullptr) {
    return false;
  }
  const TextureCompareShape shape = textureCompareShape(operands->texture->type);
  return shape != TextureCompareShape::Unknown &&
         !openGLExplicitLodShadowCompareOperandsSupported(*operands, context);
}

std::set<std::string>
unsupportedShadowCompareExplicitLodShapeLabels(const HIRModule &module) {
  std::set<std::string> labels;
  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &function : stage.functions) {
      const OpenGLSupportContext context{&module, &stage, &function};
      auto visitor = [&](const HIRExpression &expression) {
        if (!expressionHasUnsupportedShadowCompareExplicitLodShape(expression,
                                                                   context)) {
          return;
        }
        const std::optional<TextureCompareOperands> operands =
            textureCompareOperands(expression);
        if (operands.has_value() && operands->texture != nullptr) {
          labels.insert(shadowCompareExplicitLodShapeLabel(*operands->texture));
        }
      };
      visitFunctionExpressions(function, visitor);
    }
  }
  for (const HIRFunction &function : module.functions) {
    const OpenGLSupportContext context{&module, nullptr, &function};
    auto visitor = [&](const HIRExpression &expression) {
      if (!expressionHasUnsupportedShadowCompareExplicitLodShape(expression,
                                                                 context)) {
        return;
      }
      const std::optional<TextureCompareOperands> operands =
          textureCompareOperands(expression);
      if (operands.has_value() && operands->texture != nullptr) {
        labels.insert(shadowCompareExplicitLodShapeLabel(*operands->texture));
      }
    };
    visitFunctionExpressions(function, visitor);
  }
  return labels;
}

std::optional<std::string>
glslAtomicIntegerStorageTypeForResource(const HIRResource &resource) {
  if (resource.kind == HIRResourceKind::Buffer) {
    if (resource.type.arraySize.has_value()) {
      return std::nullopt;
    }
    return glslAtomicIntegerStorageType(bufferElementType(resource.type));
  }
  if (resource.kind == HIRResourceKind::Shared) {
    return glslAtomicIntegerStorageType(resource.type);
  }
  return std::nullopt;
}

bool openGLAtomicIntegerTargetSupported(const HIRExpression &target,
                                        const OpenGLSupportContext &context,
                                        std::string &storageType) {
  const std::optional<std::string> targetType =
      glslAtomicIntegerStorageType(target.type);
  if (!targetType.has_value()) {
    return false;
  }

  if (target.kind == HIRExpressionKind::Identifier) {
    const HIRResource *resource =
        findOpenGLStageResource(context, target.value);
    if (resource == nullptr || resource->kind != HIRResourceKind::Shared ||
        resource->type.arraySize.has_value()) {
      return false;
    }
    const std::optional<std::string> resourceType =
        glslAtomicIntegerStorageTypeForResource(*resource);
    if (resourceType != targetType) {
      return false;
    }
    storageType = *targetType;
    return true;
  }

  if (target.kind != HIRExpressionKind::IndexAccess ||
      target.children.size() != 2 ||
      target.children[0].kind != HIRExpressionKind::Identifier) {
    return false;
  }

  const HIRResource *resource =
      findOpenGLStageResource(context, target.children[0].value);
  if (resource == nullptr ||
      (resource->kind != HIRResourceKind::Buffer &&
       resource->kind != HIRResourceKind::Shared)) {
    return false;
  }
  if (resource->kind == HIRResourceKind::Shared &&
      !resource->type.arraySize.has_value()) {
    return false;
  }

  const std::optional<std::string> resourceType =
      glslAtomicIntegerStorageTypeForResource(*resource);
  if (resourceType != targetType ||
      !expressionSupported(target.children[1], context)) {
    return false;
  }
  storageType = *targetType;
  return true;
}

bool openGLIntegerCounterAtomicTargetSupported(
    const HIRExpression &target, const OpenGLSupportContext &context,
    std::string &storageType) {
  if (target.type.arraySize.has_value() ||
      (target.type.name != "int" && target.type.name != "uint") ||
      !expressionSupported(target, context)) {
    return false;
  }
  const HIRExpression *root = rootIdentifierExpression(target);
  if (root == nullptr) {
    return false;
  }
  const HIRResource *resource = findOpenGLStageResource(context, root->value);
  if (resource == nullptr ||
      (resource->kind != HIRResourceKind::Buffer &&
       resource->kind != HIRResourceKind::Shared)) {
    return false;
  }
  storageType = target.type.name;
  return true;
}

bool openGLAtomicIntegerCallSupported(const HIRExpression &expression,
                                      const OpenGLSupportContext &context) {
  if (expression.kind != HIRExpressionKind::Call ||
      !isOpenGLAtomicIntegerCallName(expression.value) ||
      expression.children.size() != 2) {
    return false;
  }

  std::string storageType;
  if (!openGLAtomicIntegerTargetSupported(expression.children[0], context,
                                         storageType) &&
      !openGLIntegerCounterAtomicTargetSupported(expression.children[0],
                                                context, storageType)) {
    return false;
  }

  const HIRExpression &delta = expression.children[1];
  return !expression.type.arraySize.has_value() &&
         (expression.type.name.empty() || expression.type.name == storageType) &&
         !delta.type.arraySize.has_value() && delta.type.name == storageType &&
         expressionSupported(delta, context);
}

bool openGLAtomicIntegerCaptureSupported(const HIRExpression &expression,
                                         const OpenGLSupportContext &context,
                                         const HIRType &resultType) {
  if (!openGLAtomicIntegerCallSupported(expression, context) ||
      resultType.arraySize.has_value()) {
    return false;
  }
  return resultType.name == expression.children[1].type.name &&
         (expression.type.name.empty() ||
          expression.type.name == resultType.name);
}

bool openGLLoopHeaderStatementSupported(const HIRStatement &statement,
                                        const OpenGLSupportContext &context) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    if (statement.declaredType.arraySize.has_value() &&
        statement.value.kind != HIRExpressionKind::Empty) {
      return false;
    }
    return openGLLocalDeclarationTypeSupported(context, statement.declaredType) &&
           (expressionSupported(statement.value, context) ||
            openGLAtomicIntegerCaptureSupported(statement.value, context,
                                                statement.declaredType));
  case HIRStatementKind::Assignment:
    return expressionSupported(statement.target, context) &&
           (expressionSupported(statement.value, context) ||
            openGLAtomicIntegerCaptureSupported(statement.value, context,
                                                statement.target.type));
  case HIRStatementKind::Expression:
    return expressionSupported(statement.value, context);
  case HIRStatementKind::Return:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Block:
  case HIRStatementKind::If:
  case HIRStatementKind::For:
  case HIRStatementKind::Raw:
    return false;
  }
  return false;
}

bool statementSupported(const HIRStatement &statement,
                        const OpenGLSupportContext &context) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    if (statement.declaredType.arraySize.has_value() &&
        statement.value.kind != HIRExpressionKind::Empty) {
      return false;
    }
    return openGLLocalDeclarationTypeSupported(context, statement.declaredType) &&
           (expressionSupported(statement.value, context) ||
            openGLAtomicIntegerCaptureSupported(statement.value, context,
                                                statement.declaredType));
  case HIRStatementKind::Assignment:
    return expressionSupported(statement.target, context) &&
           (expressionSupported(statement.value, context) ||
            openGLAtomicIntegerCaptureSupported(statement.value, context,
                                                statement.target.type));
  case HIRStatementKind::Return:
    return statement.value.kind == HIRExpressionKind::Empty ||
           expressionSupported(statement.value, context);
  case HIRStatementKind::Expression:
    return expressionSupported(statement.value, context) ||
           openGLAtomicIntegerCallSupported(statement.value, context);
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
    return true;
  case HIRStatementKind::Block:
    for (const HIRStatement &child : statement.body) {
      if (!statementSupported(child, context)) {
        return false;
      }
    }
    return true;
  case HIRStatementKind::If:
    if (!expressionSupported(statement.value, context)) {
      return false;
    }
    for (const HIRStatement &child : statement.body) {
      if (!statementSupported(child, context)) {
        return false;
      }
    }
    for (const HIRStatement &child : statement.elseBody) {
      if (!statementSupported(child, context)) {
        return false;
      }
    }
    return true;
  case HIRStatementKind::For:
    if (!expressionSupported(statement.value, context) ||
        statement.initializer.size() > 1) {
      return false;
    }
    for (const HIRStatement &initializer : statement.initializer) {
      if (!openGLLoopHeaderStatementSupported(initializer, context)) {
        return false;
      }
    }
    if (!statement.update.empty()) {
      if (statement.update.size() > 1) {
        return false;
      }
      for (const HIRStatement &update : statement.update) {
        if (!openGLLoopHeaderStatementSupported(update, context)) {
          return false;
        }
      }
    } else if (!statement.updateTokens.empty() &&
               !rawLoopUpdateSupported(statement.updateTokens)) {
      return false;
    }
    for (const HIRStatement &child : statement.body) {
      if (!statementSupported(child, context)) {
        return false;
      }
    }
    return true;
  case HIRStatementKind::Raw:
    return false;
  }
  return false;
}

bool functionSupported(const HIRModule &module, const HIRStage &stage,
                       const HIRFunction &function, bool entry) {
  if (!isSupportedFunctionReturnType(module, function.returnType)) {
    return false;
  }
  if (entry) {
    if (stage.stage == "compute") {
      if (function.returnType.name != "void" ||
          function.returnType.arraySize.has_value() ||
          !function.parameters.empty()) {
        return false;
      }
    } else if (!openGLGraphicsEntrySignatureSupported(module, stage, function)) {
      return false;
    }
  }
  for (const HIRParameter &parameter : function.parameters) {
    if (!isSupportedFunctionValueType(module, parameter.type)) {
      return false;
    }
  }
  const OpenGLSupportContext context{&module, &stage, &function};
  return functionBodySupportedByPolicy(
      function, [&](const HIRStatement &statement) {
        return statementSupported(statement, context);
      });
}

bool stageFunctionsSupported(const HIRModule &module, const HIRStage &stage) {
  const HIRFunction *entry = entryFunction(stage);
  if (entry == nullptr) {
    return false;
  }
  for (const HIRFunction &function : stage.functions) {
    if (!functionSupported(module, stage, function, &function == entry)) {
      return false;
    }
  }
  return true;
}

bool openGLComputeTextualBackendSupported(const HIRModule &module) {
  const HIRStage *stage = singleComputeStage(module);
  return stage != nullptr && stage->workgroupSize.has_value() &&
         constantsSupported(module) && resourcesSupported(module, *stage) &&
         unsupportedOpenGLRuntimeTailBlockIndexLabels(module).empty() &&
         unsupportedOpenGLFunctionParameterArrayWriteLabels(module).empty() &&
         stageFunctionsSupported(module, *stage);
}

bool openGLGraphicsTextualBackendSupported(const HIRModule &module) {
  const HIRStage *vertex = nullptr;
  const HIRStage *fragment = nullptr;
  if (!openGLGraphicsStagePair(module, vertex, fragment) ||
      !constantsSupported(module) ||
      !openGLGraphicsStageResourcesSupported(module, *vertex) ||
      !openGLGraphicsStageResourcesSupported(module, *fragment) ||
      !unsupportedOpenGLFunctionParameterArrayWriteLabels(module).empty() ||
      !openGLGraphicsResourceBindingsSupported(module, *vertex, *fragment) ||
      !stageFunctionsSupported(module, *vertex) ||
      !stageFunctionsSupported(module, *fragment)) {
    return false;
  }

  const HIRFunction *vertexEntry = entryFunction(*vertex);
  const HIRFunction *fragmentEntry = entryFunction(*fragment);
  return vertexEntry != nullptr && fragmentEntry != nullptr &&
         openGLGraphicsVaryingsSupported(module, *vertexEntry, *fragmentEntry);
}

void emitFunctionSignature(std::ostringstream &out, const HIRModule &module,
                           const HIRFunction &function,
                           std::string_view emittedName,
                           const OpenGLEmitContext &context) {
  out << glslFunctionReturnType(module, function.returnType) << " "
      << emittedName << "(";
  for (std::size_t index = 0; index < function.parameters.size(); ++index) {
    if (index != 0) {
      out << ", ";
    }
    const HIRParameter &parameter = function.parameters[index];
    out << glslDeclarator(module, parameter.type,
                          emitIdentifierName(parameter.name, context));
  }
  out << ")";
}

void emitFunctionDefinition(std::ostringstream &out, const HIRModule &module,
                            const HIRFunction &function,
                            const OpenGLEmitContext &context,
                            std::string_view emittedName) {
  const OpenGLEmitContext functionContext =
      makeOpenGLFunctionEmitContext(context, function);
  emitFunctionSignature(out, module, function, emittedName, functionContext);
  out << " {\n";
  for (const HIRStatement &statement : function.body) {
    emitStatement(out, statement, 2, functionContext);
  }
  out << "}\n\n";
}

void emitStageFunctionDefinitions(std::ostringstream &out,
                                  const HIRModule &module,
                                  const HIRStage &stage,
                                  const HIRFunction &entry,
                                  const OpenGLEmitContext &context,
                                  std::string_view entryName) {
  bool emittedPrototype = false;
  for (const HIRFunction &function : stage.functions) {
    if (&function == &entry) {
      continue;
    }
    const OpenGLEmitContext functionContext =
        makeOpenGLFunctionEmitContext(context, function);
    emitFunctionSignature(out, module, function, function.name,
                          functionContext);
    out << ";\n";
    emittedPrototype = true;
  }
  if (emittedPrototype) {
    out << "\n";
  }
  for (const HIRFunction &function : stage.functions) {
    if (&function == &entry) {
      continue;
    }
    emitFunctionDefinition(out, module, function, context, function.name);
  }
  emitFunctionDefinition(out, module, entry, context, entryName);
}

OpenGLEmitContext makeOpenGLEmitContext(
    const HIRModule &module, const HIRStage &stage,
    bool useCombinedSamplerResources = false,
    const TargetLegalizationResourceBindingFacts *resourceBindings = nullptr) {
  OpenGLEmitContext context;
  context.module = &module;
  context.resourceBindings = resourceBindings;
  context.stage = stage.stage;
  context.backendEntryPoint = stage.stage + "_" + stage.entryPointName;
  context.useCombinedSamplerResources = useCombinedSamplerResources;
  const OpenGLSupportContext supportContext{&module, &stage, nullptr};
  std::set<std::string> combinedSamplerCandidates;
  std::set<std::string> nonCombinedSamplerUses;
  for (const HIRFunction &function : stage.functions) {
    auto visitor = [&](const HIRExpression &expression) {
      const std::optional<TextureCompareOperands> operands =
          textureCompareOperands(expression);
      if (!operands.has_value() || !operands->explicitLod ||
          operands->texture == nullptr || operands->sampler == nullptr ||
          !openGLExplicitLodShadowCompareOperandsSupported(*operands,
                                                           supportContext)) {
        return;
      }
      if (openGLResourceReferenceHasArrayBase(*operands->sampler,
                                              supportContext)) {
        return;
      }
      const std::optional<std::string> textureName =
          resourceReferenceBaseName(*operands->texture);
      if (!textureName.has_value() ||
          openGLResourceReferenceHasArrayBase(*operands->texture,
                                              supportContext)) {
        return;
      }
      context.combinedShadowCompareLodTextures.insert(*textureName);
      const std::optional<std::string> samplerName =
          resourceReferenceBaseName(*operands->sampler);
      if (samplerName.has_value()) {
        combinedSamplerCandidates.insert(*samplerName);
      }
    };
    visitFunctionExpressions(function, visitor);
  }
  for (const HIRFunction &function : stage.functions) {
    auto visitor = [&](const HIRExpression &expression) {
      if (const std::optional<TextureSampleOperands> sampleOperands =
              textureSampleOperands(expression)) {
        if (const std::optional<std::string> samplerName =
                resourceReferenceBaseName(*sampleOperands->sampler)) {
          nonCombinedSamplerUses.insert(*samplerName);
        }
        return;
      }
      if (const std::optional<TextureCompareManualOperands> manualOperands =
              textureCompareManualOperands(expression)) {
        if (const std::optional<std::string> samplerName =
                resourceReferenceBaseName(*manualOperands->sampler)) {
          nonCombinedSamplerUses.insert(*samplerName);
        }
        return;
      }
      const std::optional<TextureCompareOperands> compareOperands =
          textureCompareOperands(expression);
      if (!compareOperands.has_value() || compareOperands->sampler == nullptr) {
        return;
      }
      const std::optional<std::string> samplerName =
          resourceReferenceBaseName(*compareOperands->sampler);
      if (!samplerName.has_value()) {
        return;
      }
      if (!compareOperands->explicitLod || compareOperands->texture == nullptr ||
          !openGLExplicitLodShadowCompareOperandsSupported(*compareOperands,
                                                           supportContext) ||
          openGLResourceReferenceHasArrayBase(*compareOperands->texture,
                                              supportContext)) {
        nonCombinedSamplerUses.insert(*samplerName);
      }
    };
    visitFunctionExpressions(function, visitor);
  }
  for (const std::string &samplerName : combinedSamplerCandidates) {
    if (nonCombinedSamplerUses.count(samplerName) == 0) {
      context.combinedShadowCompareLodSamplers.insert(samplerName);
    }
  }
  for (const HIRStruct &structure : module.structs) {
    for (const HIRField &field : structure.fields) {
      registerOpenGLIdentifierRemap(context, field.name);
    }
  }
  for (const HIRResource &resource : stage.resources) {
    if (openGLRuntimeTailBlockStruct(module, resource) != nullptr) {
      context.runtimeTailBlocks.insert(resource.name);
      continue;
    }
    if (resource.kind == HIRResourceKind::Buffer &&
        resource.type.arraySize.has_value() &&
        !resource.type.arraySize->empty()) {
      context.storageBufferArrays.insert(resource.name);
    }
  }
  return context;
}

void diagnoseOpenGLSourceUnsupported(DiagnosticEngine &diagnostics) {
  diagnostics.error(
      "opengl.source-unsupported",
      "OpenGL source package currently supports either one compute stage, "
      "storage "
      "buffers, scalar/vector expressions, structured if blocks, structured "
      "for loops, implicit compute LOD-0 plus explicit-lod 2D/2D-array/3D/"
      "cube/cube-array float and integer texture sampling with direct or "
      "indexed texture/sampler descriptors, 2D and 2D-array "
      "float/signed/unsigned storage images "
      "with direct or indexed fixed-size image descriptors and direct "
      "imageLoad/imageStore calls plus r32 integer storage-image atomic "
      "calls, non-lod shadow texture "
      "comparison sampling, explicit-lod 2D/2D-array/cube/cube-array "
      "shadow texture comparison sampling, scalar constants, fixed-size "
      "uniform-buffer descriptor arrays, simple struct storage-buffer "
      "elements, fixed-size storage-buffer descriptor arrays, direct final "
      "runtime-array storage-buffer tails on singleton blocks, fixed-size "
      "numeric workgroup shared-memory declarations, "
      "scalar integer storage-buffer and workgroup shared-memory atomic "
      "expression statements and declaration/assignment captures, compute "
      "workgroup barrier expression statements, "
      "fixed-size function parameter arrays, fixed-size numeric local arrays "
      "(including fixed nested arrays with literal/folded or dynamic helper "
      "read indices) passed to helper array parameters with callee-local "
      "parameter writes, fixed-size struct-element helper arrays, same-stage "
      "helper functions, and void entry functions with no parameters, or one "
      "vertex stage plus one "
      "fragment stage with struct input/output signatures, scalar/vector stage "
      "IO fields, non-array struct uniform buffers, and fixed-size sampled "
      "texture/comparison texture plus sampler/comparison-sampler descriptor "
      "arrays from vertex or fragment stages");
}

} // namespace

bool openglTextualBackendSupported(const HIRModule &module) {
  return openGLComputeTextualBackendSupported(module) ||
         openGLGraphicsTextualBackendSupported(module);
}

bool openglHasUnsupportedShadowCompareExplicitLodShape(
    const HIRModule &module) {
  return !unsupportedShadowCompareExplicitLodShapeLabels(module).empty();
}

bool diagnoseOpenGLUnsupportedShadowCompareExplicitLodShape(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  const std::set<std::string> unsupportedOperands =
      unsupportedShadowCompareExplicitLodShapeLabels(module);
  if (unsupportedOperands.empty()) {
    return false;
  }
  diagnostics.error(
      "opengl.unsupported-shadow-compare-explicit-lod-shape",
      "OpenGL source package supports textureCompareLod for recognized "
      "2D/2D-array/cube/cube-array shadow texture resources with "
      "GL_EXT_texture_shadow_lod; unsupported explicit-lod shadow compare "
      "operand(s): " +
          joinNames(unsupportedOperands) +
          "; check texture and sampler operand shapes for this target");
  return true;
}

bool openglHasUnsupportedStorageBufferArray(const HIRModule &module) {
  return hasUnsupportedStorageBufferArray(module);
}

bool openglHasUnsupportedRuntimeResourceArray(const HIRModule &module) {
  return hasUnsupportedRuntimeResourceArray(module);
}

bool diagnoseOpenGLUnsupportedRuntimeResourceArray(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  return diagnoseUnsupportedRuntimeResourceArray(
      module, diagnostics, "opengl.unsupported-runtime-resource-array",
      "OpenGL");
}

bool diagnoseOpenGLUnsupportedStorageBufferArray(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  return diagnoseUnsupportedStorageBufferArray(
      module, diagnostics, "opengl.unsupported-storage-buffer-array",
      "OpenGL");
}

bool openglHasUnsupportedStorageBufferElementType(const HIRModule &module) {
  return !unsupportedOpenGLStorageBufferElementTypeLabels(module).empty();
}

bool diagnoseOpenGLUnsupportedStorageBufferElementType(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  const std::set<std::string> elementTypes =
      unsupportedOpenGLStorageBufferElementTypeLabels(module);
  if (elementTypes.empty()) {
    return false;
  }
  diagnostics.error(
      "opengl.unsupported-storage-buffer-element-type",
      "OpenGL source package does not yet support storage-buffer element "
      "type(s): " +
          joinNames(elementTypes) +
          "; supported storage-buffer elements are scalar/vector types, "
          "structs with scalar/vector leaf fields, and direct final "
          "runtime-array tail fields on singleton storage-buffer blocks");
  return true;
}

bool openglHasUnsupportedRuntimeTailBlockIndex(const HIRModule &module) {
  return !unsupportedOpenGLRuntimeTailBlockIndexLabels(module).empty();
}

bool diagnoseOpenGLUnsupportedRuntimeTailBlockIndex(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  const std::set<std::string> unsupportedBlocks =
      unsupportedOpenGLRuntimeTailBlockIndexLabels(module);
  if (unsupportedBlocks.empty()) {
    return false;
  }
  diagnostics.error(
      "opengl.unsupported-runtime-array-block-index",
      "OpenGL source package supports direct singleton, literal-zero, or "
      "folded-zero access for runtime-tail storage-buffer block(s): " +
          joinNames(unsupportedBlocks) +
          "; index the runtime array field instead of the outer block");
  return true;
}

bool openglHasUnsupportedFunctionParameterArrayCallFeatures(
    const HIRModule &module) {
  return !unsupportedOpenGLFunctionParameterArrayCallFeatureLabels(module)
              .empty();
}

bool diagnoseOpenGLUnsupportedFunctionParameterArrayCallFeatures(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  const std::set<std::string> unsupportedFeatures =
      unsupportedOpenGLFunctionParameterArrayCallFeatureLabels(module);
  if (unsupportedFeatures.empty()) {
    return false;
  }
  diagnostics.error(
      "opengl.unsupported-function-parameter-array-call-feature",
      "OpenGL source package cannot lower unsupported function parameter "
      "array call feature(s): " +
          joinNames(unsupportedFeatures) +
          "; supported helper array calls use scalar/vector or matrix element "
          "arrays, fixed nested/folded dimensions, and local, function "
          "parameter, storage-buffer field, nested struct-field, or "
          "struct-element array arguments");
  return true;
}

bool diagnoseOpenGLAmbiguousGraphicsResourceBindings(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  const HIRStage *vertex = nullptr;
  const HIRStage *fragment = nullptr;
  if (!openGLGraphicsStagePair(module, vertex, fragment)) {
    return false;
  }
  const std::set<std::string> ambiguousBindings =
      ambiguousOpenGLGraphicsResourceBindingLabels(module, *vertex, *fragment);
  if (ambiguousBindings.empty()) {
    return false;
  }
  diagnostics.error(
      "opengl.ambiguous-graphics-resource-binding",
      "OpenGL graphics source package requires same-kind vertex/fragment "
      "resources that share a set/binding to refer to the same resource; "
      "ambiguous binding(s): " +
          joinNames(ambiguousBindings) +
          "; use distinct bindings or matching resource names and types across "
          "stages");
  return true;
}

bool openglHasUnsupportedDynamicNestedHelperArrayRead(
    const HIRModule &module) {
  (void)module;
  return false;
}

bool diagnoseOpenGLUnsupportedDynamicNestedHelperArrayRead(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  (void)module;
  (void)diagnostics;
  return false;
}

bool openglHasUnsupportedFunctionParameterArrayWrite(const HIRModule &module) {
  return !unsupportedOpenGLFunctionParameterArrayWriteLabels(module).empty();
}

bool diagnoseOpenGLUnsupportedFunctionParameterArrayWrite(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  const std::set<std::string> unsupportedWrites =
      unsupportedOpenGLFunctionParameterArrayWriteLabels(module);
  if (unsupportedWrites.empty()) {
    return false;
  }
  diagnostics.error(
      "opengl.unsupported-function-parameter-array-write",
      "OpenGL source package cannot lower writes through fixed-size helper "
      "array parameter(s) unless every caller passes a fixed-size local array "
      "copy: " +
          joinNames(unsupportedWrites) +
          "; storage-buffer field, resource array, forwarded helper "
          "parameter, and aliased helper array arguments would require caller "
          "write-through or alias semantics that the OpenGL source-package ABI "
          "does not provide");
  return true;
}

std::size_t openglResourceBindingIndex(const HIRResource &resource) {
  return backendPlanOpenGLBindingIndex(resource.set, resource.binding);
}

std::string openglResourceAddressSpace(HIRResourceKind kind) {
  switch (kind) {
  case HIRResourceKind::Uniform:
    return "uniform";
  case HIRResourceKind::Buffer:
    return "shader-storage";
  case HIRResourceKind::Texture:
    return "texture";
  case HIRResourceKind::StorageImage:
    return "image";
  case HIRResourceKind::Sampler:
    return "sampler";
  case HIRResourceKind::Shared:
    return "shared";
  case HIRResourceKind::Value:
    break;
  }
  return "unknown";
}

std::string openglResourceBindingClass(HIRResourceKind kind) {
  switch (kind) {
  case HIRResourceKind::Uniform:
    return "uniform-buffer";
  case HIRResourceKind::Buffer:
    return "storage-buffer";
  case HIRResourceKind::Texture:
    return "texture";
  case HIRResourceKind::StorageImage:
    return "image";
  case HIRResourceKind::Sampler:
    return "sampler";
  case HIRResourceKind::Shared:
    return "shared";
  case HIRResourceKind::Value:
    break;
  }
  return "unknown";
}

bool openGLSourcePackageSupported(const HIRModule &module,
                                  DiagnosticEngine &diagnostics) {
  if (diagnoseRawStatementBackendInput(module, diagnostics)) {
    return false;
  }
  if (openglTextualBackendSupported(module)) {
    return true;
  }
  if (diagnoseOpenGLUnsupportedShadowCompareExplicitLodShape(module,
                                                             diagnostics)) {
    return false;
  }
  if (diagnoseOpenGLUnsupportedStorageBufferArray(module, diagnostics)) {
    return false;
  }
  if (diagnoseOpenGLUnsupportedRuntimeResourceArray(module, diagnostics)) {
    return false;
  }
  if (diagnoseOpenGLUnsupportedRuntimeTailBlockIndex(module, diagnostics)) {
    return false;
  }
  if (diagnoseOpenGLUnsupportedStorageBufferElementType(module, diagnostics)) {
    return false;
  }
  if (diagnoseOpenGLUnsupportedFunctionParameterArrayCallFeatures(
          module, diagnostics)) {
    return false;
  }
  if (diagnoseOpenGLAmbiguousGraphicsResourceBindings(module, diagnostics)) {
    return false;
  }
  if (diagnoseOpenGLUnsupportedDynamicNestedHelperArrayRead(module,
                                                           diagnostics)) {
    return false;
  }
  if (diagnoseOpenGLUnsupportedFunctionParameterArrayWrite(module,
                                                          diagnostics)) {
    return false;
  }
  diagnoseOpenGLSourceUnsupported(diagnostics);
  return false;
}

std::string openGLVertexAttributeName(std::string_view name) {
  return "crossgl_attr_" + std::string(name);
}

std::string openGLVaryingName(std::string_view name) {
  return "crossgl_varying_" + std::string(name);
}

std::string openGLFragmentOutputName(std::string_view name) {
  return "crossgl_out_" + std::string(name);
}

std::vector<std::string> openGLRequiredGLSLExtensions(
    const HIRModule &module) {
  std::vector<std::string> extensions;
  if (moduleUsesShadowCompareExplicitLod(module)) {
    extensions.push_back("GL_EXT_texture_shadow_lod");
  }
  if (moduleUsesNonUniform(module)) {
    extensions.push_back("GL_EXT_nonuniform_qualifier");
  }
  return extensions;
}

std::string openGLGLSLEvidenceSummary(const HIRModule &module) {
  std::ostringstream summary;
  summary << "GLSL " << kOpenGLGLSLVersion << "; extensions: ";
  const std::vector<std::string> extensions =
      openGLRequiredGLSLExtensions(module);
  if (extensions.empty()) {
    summary << "none";
    return summary.str();
  }
  for (std::size_t index = 0; index < extensions.size(); ++index) {
    if (index != 0) {
      summary << ", ";
    }
    summary << extensions[index];
  }
  return summary.str();
}

void emitOpenGLSourcePreamble(std::ostringstream &out, const HIRModule &module,
                              const OpenGLEmitContext &context) {
  out << "#version " << kOpenGLGLSLVersion << "\n";
  for (const std::string &extension : openGLRequiredGLSLExtensions(module)) {
    out << "#extension " << extension << " : require\n";
  }
  for (const HIRConstant &constant : module.constants) {
    out << "const " << glslType(constant.type) << " " << constant.name << " = "
        << emitConstantValue(constant, context) << ";\n";
  }
  if (!module.constants.empty()) {
    out << "\n";
  }
}

void emitOpenGLStructDeclarations(
    std::ostringstream &out, const HIRModule &module,
    const std::vector<const HIRStruct *> &structures,
    const OpenGLEmitContext &context) {
  for (const HIRStruct *structure : structures) {
    emitStructDeclaration(out, module, *structure, context);
  }
  if (!structures.empty()) {
    out << "\n";
  }
}

std::string generateOpenGLComputeSource(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts *resourceBindings = nullptr) {
  std::ostringstream out;
  if (!openGLComputeTextualBackendSupported(module)) {
    return out.str();
  }

  const HIRStage &stage = module.stages.front();
  const HIRFunction &entry = *entryFunction(stage);
  const HIRWorkgroupSize &workgroup = *stage.workgroupSize;
  const OpenGLEmitContext context =
      makeOpenGLEmitContext(module, stage, false, resourceBindings);
  emitOpenGLSourcePreamble(out, module, context);

  const std::vector<const HIRStruct *> storageBufferStructs =
      openGLStorageBufferStructDeclarations(module, stage);
  emitOpenGLStructDeclarations(out, module, storageBufferStructs, context);

  out << "layout(local_size_x = " << workgroup.x
      << ", local_size_y = " << workgroup.y
      << ", local_size_z = " << workgroup.z << ") in;\n\n";

  for (const HIRResource &resource : stage.resources) {
    emitResourceDeclaration(out, module, resource, context);
  }

  if (moduleUsesManualTextureCompare(module)) {
    emitManualCompareHelper(out);
  }

  emitStageFunctionDefinitions(out, module, stage, entry, context, "main");
  return out.str();
}

std::string generateOpenGLGraphicsSource(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts *resourceBindings = nullptr) {
  std::ostringstream out;
  if (!openGLGraphicsTextualBackendSupported(module)) {
    return out.str();
  }

  const HIRStage *vertexStage = nullptr;
  const HIRStage *fragmentStage = nullptr;
  (void)openGLGraphicsStagePair(module, vertexStage, fragmentStage);
  const HIRFunction &vertexEntry = *entryFunction(*vertexStage);
  const HIRFunction &fragmentEntry = *entryFunction(*fragmentStage);
  const HIRStruct &vertexInput =
      *openGLStructType(module, vertexEntry.parameters.front().type);
  const HIRStruct &vertexOutput =
      *openGLStructType(module, vertexEntry.returnType);
  const HIRStruct &fragmentInput =
      *openGLStructType(module, fragmentEntry.parameters.front().type);
  const HIRStruct &fragmentOutput =
      *openGLStructType(module, fragmentEntry.returnType);
  const HIRField &position = *openGLGraphicsPositionField(vertexOutput);

  const OpenGLEmitContext vertexContext =
      makeOpenGLEmitContext(module, *vertexStage, true, resourceBindings);
  const OpenGLEmitContext fragmentContext =
      makeOpenGLEmitContext(module, *fragmentStage, true, resourceBindings);

  emitOpenGLSourcePreamble(out, module, vertexContext);
  emitOpenGLStructDeclarations(
      out, module,
      openGLGraphicsStructDeclarations(module, vertexEntry, fragmentEntry),
      vertexContext);

  out << "#if defined(CROSSGL_STAGE_VERTEX)\n";
  for (const HIRResource &resource : vertexStage->resources) {
    emitResourceDeclaration(out, module, resource, vertexContext);
  }
  if (moduleUsesManualTextureCompare(module)) {
    emitManualCompareHelper(out);
  }
  for (std::size_t index = 0; index < vertexInput.fields.size(); ++index) {
    const HIRField &field = vertexInput.fields[index];
    out << "layout(location = " << index << ") in " << glslType(field.type)
        << " " << openGLVertexAttributeName(field.name) << ";\n";
  }
  for (std::size_t index = 0; index < fragmentInput.fields.size(); ++index) {
    const HIRField &field = fragmentInput.fields[index];
    out << "layout(location = " << index << ") out " << glslType(field.type)
        << " " << openGLVaryingName(field.name) << ";\n";
  }
  out << "\n";
  emitStageFunctionDefinitions(out, module, *vertexStage, vertexEntry,
                               vertexContext, "vertex_main");
  out << "void main() {\n";
  out << "  " << vertexInput.name << " crossgl_vertex_input;\n";
  for (const HIRField &field : vertexInput.fields) {
    out << "  crossgl_vertex_input." << emitFieldName(field.name, vertexContext)
        << " = "
        << openGLVertexAttributeName(field.name) << ";\n";
  }
  out << "  " << vertexOutput.name
      << " crossgl_vertex_output = vertex_main(crossgl_vertex_input);\n";
  for (const HIRField &field : fragmentInput.fields) {
    out << "  " << openGLVaryingName(field.name) << " = crossgl_vertex_output."
        << emitFieldName(field.name, vertexContext) << ";\n";
  }
  out << "  gl_Position = crossgl_vertex_output."
      << emitFieldName(position.name, vertexContext) << ";\n";
  out << "}\n";
  out << "#endif\n\n";

  out << "#if defined(CROSSGL_STAGE_FRAGMENT)\n";
  for (const HIRResource &resource : fragmentStage->resources) {
    emitResourceDeclaration(out, module, resource, fragmentContext);
  }
  if (moduleUsesManualTextureCompare(module)) {
    emitManualCompareHelper(out);
  }
  for (std::size_t index = 0; index < fragmentInput.fields.size(); ++index) {
    const HIRField &field = fragmentInput.fields[index];
    out << "layout(location = " << index << ") in " << glslType(field.type)
        << " " << openGLVaryingName(field.name) << ";\n";
  }
  for (std::size_t index = 0; index < fragmentOutput.fields.size(); ++index) {
    const HIRField &field = fragmentOutput.fields[index];
    out << "layout(location = " << index << ") out " << glslType(field.type)
        << " " << openGLFragmentOutputName(field.name) << ";\n";
  }
  out << "\n";
  emitStageFunctionDefinitions(out, module, *fragmentStage, fragmentEntry,
                               fragmentContext, "fragment_main");
  out << "void main() {\n";
  out << "  " << fragmentInput.name << " crossgl_fragment_input;\n";
  for (const HIRField &field : fragmentInput.fields) {
    out << "  crossgl_fragment_input."
        << emitFieldName(field.name, fragmentContext) << " = "
        << openGLVaryingName(field.name) << ";\n";
  }
  out << "  " << fragmentOutput.name
      << " crossgl_fragment_output = fragment_main(crossgl_fragment_input);\n";
  for (const HIRField &field : fragmentOutput.fields) {
    out << "  " << openGLFragmentOutputName(field.name)
        << " = crossgl_fragment_output."
        << emitFieldName(field.name, fragmentContext) << ";\n";
  }
  out << "}\n";
  out << "#endif\n";
  return out.str();
}

std::string generateOpenGLSource(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts *resourceBindings) {
  if (openGLComputeTextualBackendSupported(module)) {
    return generateOpenGLComputeSource(module, resourceBindings);
  }
  if (openGLGraphicsTextualBackendSupported(module)) {
    return generateOpenGLGraphicsSource(module, resourceBindings);
  }
  return "";
}

std::string generateOpenGLSource(const HIRModule &module) {
  return generateOpenGLSource(module, nullptr);
}

bool openGLProgramResourceRequiresLayoutBinding(
    const BackendPlanResource &resource) {
  return resource.source != nullptr && resource.emitsTargetBinding &&
         resource.hasInterfaceBinding;
}

bool openGLProgramResourceBindingRecordMatchesIdentity(
    const TargetLegalizationResourceBindingRecord &record,
    const BackendPlanResource &resource) {
  return record.target == TargetKind::OpenGL &&
         record.stage == resource.stage &&
         record.sourceEntryPoint == resource.entryPoint &&
         record.backendEntryPoint == resource.backendEntryPoint &&
         record.name == resource.name;
}

std::vector<const TargetLegalizationResourceBindingRecord *>
openGLProgramResourceBindingRecordsForResource(
    const TargetLegalizationResourceBindingFacts *resourceBindings,
    const BackendPlanResource &resource) {
  std::vector<const TargetLegalizationResourceBindingRecord *> records;
  if (resourceBindings == nullptr ||
      resourceBindings->target != TargetKind::OpenGL) {
    return records;
  }
  for (const TargetLegalizationResourceBindingRecord &record :
       resourceBindings->records) {
    if (openGLProgramResourceBindingRecordMatchesIdentity(record, resource)) {
      records.push_back(&record);
    }
  }
  return records;
}

std::string openGLDeclarationResourceLabel(const BackendPlanResource &resource) {
  std::string label = "stage '" + resource.stage + "' resource '" +
                      resource.name + "' (" + resource.kindName + " " +
                      resource.sourceType;
  if (resource.hasInterfaceBinding) {
    label += ", set " + std::to_string(resource.set) + ", binding " +
             std::to_string(resource.binding);
  }
  label += ")";
  return label;
}

void appendOpenGLDeclarationRecordMismatch(
    std::vector<std::string> &mismatches, std::string_view field,
    std::string_view expected, std::string_view actual) {
  mismatches.push_back(std::string(field) + " expected '" +
                       std::string(expected) + "', got '" +
                       std::string(actual) + "'");
}

void appendOpenGLDeclarationRecordMismatch(
    std::vector<std::string> &mismatches, std::string_view field,
    std::size_t expected, std::size_t actual) {
  appendOpenGLDeclarationRecordMismatch(
      mismatches, field, std::to_string(expected), std::to_string(actual));
}

std::string optionalStringForOpenGLDiagnostic(
    const std::optional<std::string> &value) {
  if (!value.has_value()) {
    return "<absent>";
  }
  return *value;
}

std::string joinOpenGLDeclarationMismatches(
    const std::vector<std::string> &mismatches) {
  std::ostringstream out;
  for (std::size_t index = 0; index < mismatches.size(); ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << mismatches[index];
  }
  return out.str();
}

std::vector<std::string> openGLDeclarationRecordMismatches(
    const BackendPlanResource &resource,
    const TargetLegalizationResourceBindingRecord &record) {
  std::vector<std::string> mismatches;
  if (record.abi != "programResourceBinding") {
    appendOpenGLDeclarationRecordMismatch(mismatches, "abi",
                                          "programResourceBinding", record.abi);
  }
  if (record.kind != resource.kindName) {
    appendOpenGLDeclarationRecordMismatch(mismatches, "kind",
                                          resource.kindName, record.kind);
  }
  if (record.sourceType != resource.sourceType) {
    appendOpenGLDeclarationRecordMismatch(
        mismatches, "sourceType", resource.sourceType, record.sourceType);
  }
  if (record.storageImageFormat != resource.storageImageFormat) {
    appendOpenGLDeclarationRecordMismatch(
        mismatches, "storageImageFormat",
        optionalStringForOpenGLDiagnostic(resource.storageImageFormat),
        optionalStringForOpenGLDiagnostic(record.storageImageFormat));
  }
  const std::string expectedAddressSpace =
      openglResourceAddressSpace(resource.kind);
  if (record.addressSpace != expectedAddressSpace) {
    appendOpenGLDeclarationRecordMismatch(
        mismatches, "addressSpace", expectedAddressSpace, record.addressSpace);
  }
  const std::string expectedBindingClass =
      openglResourceBindingClass(resource.kind);
  if (record.bindingClass != expectedBindingClass) {
    appendOpenGLDeclarationRecordMismatch(
        mismatches, "bindingClass", expectedBindingClass, record.bindingClass);
  }

  const std::optional<std::size_t> expectedArgumentIndex =
      resource.openglBindingIndex;
  if (!expectedArgumentIndex.has_value()) {
    if (record.argumentIndex.has_value()) {
      appendOpenGLDeclarationRecordMismatch(
          mismatches, "argumentIndex", "<absent>",
          std::to_string(*record.argumentIndex));
    }
  } else if (!record.argumentIndex.has_value()) {
    appendOpenGLDeclarationRecordMismatch(
        mismatches, "argumentIndex", std::to_string(*expectedArgumentIndex),
        "<missing>");
  } else if (*record.argumentIndex != *expectedArgumentIndex) {
    appendOpenGLDeclarationRecordMismatch(mismatches, "argumentIndex",
                                          *expectedArgumentIndex,
                                          *record.argumentIndex);
  }

  if (!record.set.has_value()) {
    appendOpenGLDeclarationRecordMismatch(
        mismatches, "set", std::to_string(resource.set), "<missing>");
  } else if (*record.set != resource.set) {
    appendOpenGLDeclarationRecordMismatch(mismatches, "set", resource.set,
                                          *record.set);
  }
  if (!record.binding.has_value()) {
    appendOpenGLDeclarationRecordMismatch(
        mismatches, "binding", std::to_string(resource.binding), "<missing>");
  } else if (*record.binding != resource.binding) {
    appendOpenGLDeclarationRecordMismatch(mismatches, "binding",
                                          resource.binding, *record.binding);
  }
  return mismatches;
}

bool diagnoseOpenGLLegalizedResourceDeclarationMismatches(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts *resourceBindings,
    DiagnosticEngine &diagnostics) {
  if (resourceBindings == nullptr ||
      resourceBindings->target != TargetKind::OpenGL ||
      !resourceBindings->complete) {
    diagnostics.error(
        "opengl.legalized-resource-binding-missing",
        "OpenGL source package requires complete legalized "
        "programResourceBinding records before layout(binding=...) emission; "
        "missing binding record(s): resource-bindings");
    return true;
  }

  bool failed = false;
  std::set<std::string> matchedEvidenceIds;
  const BackendPlan plan = buildBackendPlan(module);
  for (const BackendPlanStageInterface &stage : plan.stages) {
    for (const BackendPlanResource &resource : stage.resources) {
      if (!openGLProgramResourceRequiresLayoutBinding(resource)) {
        continue;
      }
      const std::vector<const TargetLegalizationResourceBindingRecord *> records =
          openGLProgramResourceBindingRecordsForResource(resourceBindings,
                                                         resource);
      if (records.empty()) {
        diagnostics.error(
            "opengl.legalized-resource-binding-missing",
            "missing OpenGL legalized resource-binding record for " +
                openGLDeclarationResourceLabel(resource));
        failed = true;
        continue;
      }
      if (records.size() > 1) {
        diagnostics.error(
            "opengl.legalized-resource-binding-mismatch",
            "duplicate OpenGL legalized resource-binding records for " +
                openGLDeclarationResourceLabel(resource));
        failed = true;
      }
      for (const TargetLegalizationResourceBindingRecord *record : records) {
        matchedEvidenceIds.insert(record->evidenceId);
        const std::vector<std::string> mismatches =
            openGLDeclarationRecordMismatches(resource, *record);
        if (mismatches.empty()) {
          continue;
        }
        diagnostics.error(
            "opengl.legalized-resource-binding-mismatch",
            "OpenGL GLSL declaration metadata disagrees with legalization "
            "record '" +
                record->evidenceId + "' for " +
                openGLDeclarationResourceLabel(resource) + ": " +
                joinOpenGLDeclarationMismatches(mismatches));
        failed = true;
      }
    }
  }

  for (const TargetLegalizationResourceBindingRecord &record :
       resourceBindings->records) {
    if (record.target == TargetKind::OpenGL &&
        record.abi == "programResourceBinding" &&
        matchedEvidenceIds.count(record.evidenceId) == 0) {
      diagnostics.error(
          "opengl.legalized-resource-binding-mismatch",
          "stale OpenGL legalized resource-binding record '" +
              record.evidenceId + "' for resource '" + record.name +
              "' has no matching GLSL declaration input");
      failed = true;
    }
  }
  return failed;
}

std::string generateOpenGLBackendIR(const HIRModule &module) {
  std::ostringstream out;
  out << "// backend lowering for opengl: textual GLSL compute/graphics "
         "scaffold; "
         "source packages are emitted and validated when glslangValidator is available\n";
  if (moduleContainsRawStatement(module)) {
    out << "// error: " << kRawStatementBackendInputDiagnostic
        << ": OpenGL backend input cannot contain HIR raw statements; lower "
           "them to structured HIR before backend emission\n";
    return out.str();
  }

  if (!openglTextualBackendSupported(module)) {
    const std::set<std::string> unsupportedShadowCompareLod =
        unsupportedShadowCompareExplicitLodShapeLabels(module);
    if (!unsupportedShadowCompareLod.empty()) {
      out << "// opengl textual scaffold rejects textureCompareLod for "
             "the listed shadow texture resource shapes; supported shadow "
             "2D/2D-array/cube/cube-array resources use "
             "GL_EXT_texture_shadow_lod\n";
      out << "// unsupported textureCompareLod operand(s): "
          << joinNames(unsupportedShadowCompareLod) << "\n";
    }
    const std::set<std::string> bufferArrays =
        unsupportedStorageBufferArrayNames(module);
    if (!bufferArrays.empty()) {
      out << "// opengl textual scaffold does not yet support storage-buffer "
             "descriptor arrays with unsized descriptor counts: "
          << joinNames(bufferArrays) << "\n";
    }
    const std::set<std::string> resourceArrays =
        unsupportedRuntimeResourceArrayLabels(module);
    if (!resourceArrays.empty()) {
      out << "// opengl textual scaffold does not yet support descriptor arrays "
             "with unsized/runtime descriptor counts: "
          << joinNames(resourceArrays) << "\n";
    }
    const std::set<std::string> runtimeTailBlockIndexes =
        unsupportedOpenGLRuntimeTailBlockIndexLabels(module);
    if (!runtimeTailBlockIndexes.empty()) {
      out << "// opengl textual scaffold rejects nonzero or dynamic outer "
             "indexes for runtime-tail storage-buffer block(s): "
          << joinNames(runtimeTailBlockIndexes)
          << "; index the runtime array field instead\n";
    }
    const std::set<std::string> bufferElementTypes =
        unsupportedOpenGLStorageBufferElementTypeLabels(module);
    if (!bufferElementTypes.empty()) {
      out << "// opengl textual scaffold does not yet support storage-buffer "
             "element types: "
          << joinNames(bufferElementTypes) << "\n";
    }
    const std::set<std::string> functionArrayCallFeatures =
        unsupportedOpenGLFunctionParameterArrayCallFeatureLabels(module);
    if (!functionArrayCallFeatures.empty()) {
      out << "// opengl textual scaffold rejects unsupported function "
             "parameter array call feature(s): "
          << joinNames(functionArrayCallFeatures) << "\n";
    }
    const std::set<std::string> functionArrayWrites =
        unsupportedOpenGLFunctionParameterArrayWriteLabels(module);
    if (!functionArrayWrites.empty()) {
      out << "// opengl textual scaffold rejects writes through fixed-size "
             "helper array parameter(s) unless every caller passes a "
             "fixed-size local array copy: "
          << joinNames(functionArrayWrites) << "\n";
    }
    const HIRStage *vertex = nullptr;
    const HIRStage *fragment = nullptr;
    if (openGLGraphicsStagePair(module, vertex, fragment)) {
      const std::set<std::string> ambiguousBindings =
          ambiguousOpenGLGraphicsResourceBindingLabels(module, *vertex,
                                                       *fragment);
      if (!ambiguousBindings.empty()) {
        out << "// opengl textual scaffold rejects ambiguous same-kind "
               "cross-stage resource bindings: "
            << joinNames(ambiguousBindings) << "\n";
      }
    }
    out << "// opengl textual scaffold currently supports either one compute "
           "stage, "
           "storage buffers, scalar/vector expressions, scalar/vector math "
           "intrinsics, structured if blocks, structured for loops, implicit "
           "compute LOD-0 plus explicit-lod 2D/2D-array/3D/cube/cube-array "
           "float and integer texture sampling with direct or indexed "
           "texture/sampler descriptors, non-lod shadow texture comparison "
           "sampling, 2D and 2D-array "
           "float/signed/unsigned storage images with direct or indexed "
           "fixed-size image descriptors and direct imageLoad/imageStore "
           "calls, explicit-lod 2D shadow texture "
           "comparison sampling, scalar constants, fixed-size uniform-buffer "
           "descriptor arrays, simple struct storage-buffer elements, "
           "fixed-size storage-buffer descriptor arrays, fixed-size "
           "numeric workgroup shared-memory declarations, scalar integer "
           "storage-buffer and workgroup shared-memory atomic expression "
           "statements and declaration/assignment captures, fixed-size "
           "function parameter arrays, compute workgroup barrier expression "
           "statements, "
           "fixed-size numeric local arrays "
           "(including fixed nested arrays with literal/folded or dynamic "
           "helper read indices) passed to helper array parameters with "
           "callee-local parameter writes, fixed-size struct-element helper "
           "arrays, same-stage helper functions, and void entry functions "
           "with no parameters, or one "
           "vertex stage plus one fragment stage with struct input/output "
           "signatures, scalar/vector stage IO fields, non-array struct "
           "uniform buffers, and fixed-size sampled texture/comparison texture "
           "plus sampler/comparison-sampler descriptor arrays from vertex or "
           "fragment stages\n\n";
    out << "// source CrossGL IR follows\n";
    return out.str();
  }

  out << generateOpenGLSource(module) << "\n\n";
  out << "// source CrossGL IR follows\n";
  return out.str();
}

OpenGLSourcePackageResult
buildOpenGLSourcePackage(const HIRModule &module,
                         const std::filesystem::path &packageDir,
                         DiagnosticEngine &diagnostics,
                         const TargetLegalizationResourceBindingFacts
                             *resourceBindings) {
  OpenGLSourcePackageResult result;
  if (!openGLSourcePackageSupported(module, diagnostics)) {
    return result;
  }
  if (diagnoseOpenGLLegalizedResourceDeclarationMismatches(
          module, resourceBindings, diagnostics)) {
    return result;
  }

  const std::filesystem::path openglDir = packageDir / "backend" / "opengl";
  std::error_code error;
  std::filesystem::create_directories(openglDir, error);
  if (error) {
    diagnostics.error("opengl.source-package-directory",
                      "failed to create OpenGL backend directory: " +
                          error.message());
    return result;
  }

  const bool graphicsSource = openGLGraphicsTextualBackendSupported(module);
  const std::string sourceSuffix =
      graphicsSource ? ".graphics.glsl" : ".comp.glsl";
  const std::string sourceKind = graphicsSource ? "graphics" : "compute";
  result.sourcePath = openglDir / (module.name + sourceSuffix);
  result.nativeBinaryPath = openglDir / (module.name + ".glsl");
  std::filesystem::remove(result.nativeBinaryPath, error);

  const std::string sourceText = generateOpenGLSource(module, resourceBindings);
  const std::string glslEvidence = openGLGLSLEvidenceSummary(module);
  std::ofstream source(result.sourcePath, std::ios::binary);
  if (!source) {
    diagnostics.error("opengl.write-source",
                      "failed to write '" + result.sourcePath.string() + "'");
    return result;
  }
  source << sourceText;
  source.close();

  const std::optional<std::string> glslang = findExecutable("glslangValidator");
  if (!glslang.has_value()) {
    result.validatorStatus = "skipped-tool-missing";
    diagnostics.warning("opengl.source-package-only",
                        "emitted GLSL source package (" + glslEvidence +
                            "); validation is planned because "
                            "glslangValidator was not found");
    result.success = !diagnostics.hasErrors();
    return result;
  }

  int status = 0;
  if (graphicsSource) {
    const int vertexStatus =
        runProcess({*glslang, "-l", "-S", "vert",
                    "-DCROSSGL_STAGE_VERTEX=1", result.sourcePath.string()});
    const int fragmentStatus =
        runProcess({*glslang, "-l", "-S", "frag",
                    "-DCROSSGL_STAGE_FRAGMENT=1", result.sourcePath.string()});
    status = vertexStatus == 0 && fragmentStatus == 0 ? 0 : 1;
  } else {
    status = runProcess({*glslang, "-S", "comp", result.sourcePath.string()});
  }
  if (status == 0) {
    std::ofstream validated(result.nativeBinaryPath, std::ios::binary);
    if (!validated) {
      diagnostics.error(
          "opengl.write-validated-source",
          "failed to write '" + result.nativeBinaryPath.string() + "'");
      return result;
    }
    validated << sourceText;

    diagnostics.note("opengl.glsl-validated",
                     "validated generated GLSL " + sourceKind +
                         " source with glslangValidator (" + glslEvidence +
                         ")");
    result.sourceValidated = true;
    result.nativeBinaryStatus = "validated";
    result.validatorStatus = "validated";
    result.success = !diagnostics.hasErrors();
    return result;
  }

  std::filesystem::remove(result.nativeBinaryPath, error);
  result.validatorStatus = "failed";
  Diagnostic diagnostic;
  diagnostic.severity = DiagnosticSeverity::Warning;
  diagnostic.code = "opengl.glslang-failed";
  diagnostic.message =
      "glslangValidator was found but failed to validate generated GLSL " +
      sourceKind + " source (" + glslEvidence + ")";
  diagnostic.target = "opengl";
  diagnostic.missingCapabilities = {"opengl.backend.native-glsl-package",
                                    "opengl.validation.glsl-program-validation"};
  diagnostics.report(std::move(diagnostic));
  diagnostics.warning("opengl.source-package-only",
                      "kept GLSL source package; native OpenGL validation "
                      "remains planned");
  result.success = !diagnostics.hasErrors();
  return result;
}

OpenGLSourcePackageResult
buildOpenGLSourcePackage(const HIRModule &module,
                         const std::filesystem::path &packageDir,
                         DiagnosticEngine &diagnostics) {
  const TargetLegalizationResult legalization =
      legalizeTarget(module, TargetKind::OpenGL);
  return buildOpenGLSourcePackage(module, packageDir, diagnostics,
                                  &legalization.resourceBindings);
}

OpenGLSourcePackageResult buildOpenGLSourcePackage(
    const HIRModule &module, const std::filesystem::path &packageDir,
    DiagnosticEngine &diagnostics,
    const TargetLegalizationResourceBindingFacts &resourceBindings) {
  return buildOpenGLSourcePackage(module, packageDir, diagnostics,
                                  &resourceBindings);
}

} // namespace crossgl
