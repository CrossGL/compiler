#include "crossgl/Backend/DirectXBackend.h"

#include "crossgl/Backend/BackendExpressions.h"
#include "crossgl/Backend/BackendHIR.h"
#include "crossgl/Backend/BackendIntrinsics.h"
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
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <map>
#include <optional>
#include <set>
#include <span>
#include <sstream>
#include <string>
#include <string_view>
#include <system_error>
#include <utility>
#include <vector>

namespace crossgl {
namespace {

constexpr std::string_view kRawStatementBackendInputDiagnostic =
    "opt.hir-raw-statement-backend-input";

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
      "DirectX source package input cannot contain HIR raw statements; "
      "lower them to structured HIR before backend emission");
  return true;
}

} // namespace

DirectXDxcOptimizationProfile
directxDxcOptimizationProfile(OptimizationLevel level) {
  switch (level) {
  case OptimizationLevel::O0:
    return {"O0", "-O0"};
  case OptimizationLevel::O1:
    return {"O1", "-O3"};
  case OptimizationLevel::O2:
    return {"O2", "-O3"};
  }
  return {"O1", "-O3"};
}

namespace {

std::string_view directxDxcOptimizationFlag(OptimizationLevel level) {
  return directxDxcOptimizationProfile(level).dxcFlag;
}

std::string directxDxcOptimizationEvidence(OptimizationLevel level) {
  const DirectXDxcOptimizationProfile profile =
      directxDxcOptimizationProfile(level);
  return "CrossGL opt-level " + std::string(profile.requestedLevel) +
         " maps to DXC " + std::string(profile.dxcFlag);
}

std::string hlslTypeName(std::string_view name) {
  if (name == "float" || name == "int" || name == "uint" || name == "bool" ||
      name == "void") {
    return std::string(name);
  }
  if (name == "vec2") {
    return "float2";
  }
  if (name == "vec3") {
    return "float3";
  }
  if (name == "vec4") {
    return "float4";
  }
  if (name == "ivec2") {
    return "int2";
  }
  if (name == "ivec3") {
    return "int3";
  }
  if (name == "ivec4") {
    return "int4";
  }
  if (name == "uvec2") {
    return "uint2";
  }
  if (name == "uvec3") {
    return "uint3";
  }
  if (name == "uvec4") {
    return "uint4";
  }
  if (name == "bvec2") {
    return "bool2";
  }
  if (name == "bvec3") {
    return "bool3";
  }
  if (name == "bvec4") {
    return "bool4";
  }
  if (name == "mat2" || name == "mat2x2") {
    return "float2x2";
  }
  if (name == "mat3" || name == "mat3x3") {
    return "float3x3";
  }
  if (name == "mat4" || name == "mat4x4") {
    return "float4x4";
  }
  return "";
}

std::string directxAtomicScalarStorageType(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return "";
  }
  const std::string name = stripTypeQualifier(type.name);
  if (name == "atomic<int>") {
    return "int";
  }
  if (name == "atomic<uint>") {
    return "uint";
  }
  return "";
}

std::string hlslType(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return "";
  }
  return hlslTypeName(stripPointer(type.name));
}

bool isSupportedValueType(const HIRType &type) {
  return !type.arraySize.has_value() && !hlslType(type).empty();
}

bool isNumericScalarOrVectorType(std::string_view name) {
  if (isNumericScalarTypeName(name)) {
    return true;
  }
  if (!isVectorType(name)) {
    return false;
  }
  return isNumericScalarTypeName(scalarTypeForVector(name).name);
}

bool isNumericScalarVectorOrMatrixType(std::string_view name) {
  return isNumericScalarOrVectorType(name) || isMatrixType(name);
}

std::optional<std::size_t> matrixDimensionFromName(std::string_view name) {
  if (name == "mat2" || name == "mat2x2") {
    return std::size_t{2};
  }
  if (name == "mat3" || name == "mat3x3") {
    return std::size_t{3};
  }
  if (name == "mat4" || name == "mat4x4") {
    return std::size_t{4};
  }
  return std::nullopt;
}

bool isDirectXFloatVectorType(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  return vectorWidthFromName(baseName).has_value() &&
         baseTypeName(scalarTypeForVector(baseName)) == "float";
}

bool isDirectXMatrixVectorMultiplyOperandPair(const HIRType &matrixType,
                                              const HIRType &vectorType,
                                              const HIRType &resultType) {
  const std::optional<std::size_t> matrixDimension =
      matrixDimensionFromName(baseTypeName(matrixType));
  const std::optional<std::size_t> vectorWidth =
      vectorWidthFromName(baseTypeName(vectorType));
  return matrixDimension.has_value() && vectorWidth.has_value() &&
         *matrixDimension == *vectorWidth &&
         isDirectXFloatVectorType(vectorType) &&
         baseTypeName(vectorType) == baseTypeName(resultType) &&
         !resultType.arraySize.has_value();
}

bool isDirectXMatrixProductExpression(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Binary || expression.value != "*" ||
      expression.children.size() != 2) {
    return false;
  }

  const HIRType &leftType = expression.children[0].type;
  const HIRType &rightType = expression.children[1].type;
  if (isDirectXMatrixVectorMultiplyOperandPair(leftType, rightType,
                                               expression.type) ||
      isDirectXMatrixVectorMultiplyOperandPair(rightType, leftType,
                                               expression.type)) {
    return true;
  }

  const std::optional<std::size_t> leftDimension =
      matrixDimensionFromName(baseTypeName(leftType));
  const std::optional<std::size_t> rightDimension =
      matrixDimensionFromName(baseTypeName(rightType));
  const std::optional<std::size_t> resultDimension =
      matrixDimensionFromName(baseTypeName(expression.type));
  return leftDimension.has_value() && rightDimension.has_value() &&
         resultDimension.has_value() && *leftDimension == *rightDimension &&
         *leftDimension == *resultDimension && !leftType.arraySize.has_value() &&
         !rightType.arraySize.has_value() && !expression.type.arraySize.has_value();
}

bool isSupportedLocalArrayType(const HIRModule &module, const HIRType &type) {
  if (!type.arraySize.has_value() ||
      functionParameterArrayShape(module, type) !=
          HIRFunctionParameterArrayShape::FixedSize) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  return !hlslTypeName(baseName).empty() &&
         isNumericScalarVectorOrMatrixType(baseName);
}

std::string hlslValueType(const HIRModule *module, const HIRType &type) {
  const std::string scalarVectorType = hlslType(type);
  if (!scalarVectorType.empty()) {
    return scalarVectorType;
  }
  if (module == nullptr || type.arraySize.has_value()) {
    return "";
  }
  const HIRStruct *structure = findStruct(*module, stripPointer(type.name));
  return structure != nullptr ? structure->name : "";
}

std::string hlslDeclarator(const HIRModule *module, const HIRType &type,
                           std::string_view name) {
  std::string baseType = type.arraySize.has_value()
                             ? hlslTypeName(stripPointer(type.name))
                             : hlslValueType(module, type);
  if (baseType.empty() && module != nullptr && type.arraySize.has_value()) {
    if (const HIRStruct *structure = findStruct(*module, stripPointer(type.name))) {
      baseType = structure->name;
    }
  }
  if (baseType.empty()) {
    return "";
  }
  std::string declarator = baseType + " " + std::string(name);
  if (type.arraySize.has_value()) {
    declarator += "[" + *type.arraySize + "]";
  }
  return declarator;
}

std::vector<std::string_view>
directxArrayDimensions(std::string_view arraySize) {
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

std::string hlslStructFieldType(const HIRModule &module, const HIRType &type) {
  const std::string baseName = stripPointer(type.name);
  const std::string valueType = hlslTypeName(baseName);
  if (!valueType.empty()) {
    return valueType;
  }
  const HIRStruct *structure = findStruct(module, baseName);
  return structure != nullptr ? structure->name : "";
}

bool hlslStorageBufferScalarTypeSupported(std::string_view name) {
  return isNumericScalarVectorOrMatrixType(name) && !hlslTypeName(name).empty();
}

bool hlslUniformBufferScalarTypeSupported(std::string_view name) {
  return isNumericScalarVectorOrMatrixType(name) && !hlslTypeName(name).empty();
}

bool directxStructStorageBufferElementSupported(const HIRModule &module,
                                                const HIRStruct &structure) {
  return structStorageBufferElementSupported(
      module, structure, hlslStorageBufferScalarTypeSupported);
}

bool directxStructUniformBufferElementSupported(const HIRModule &module,
                                                const HIRStruct &structure) {
  return structStorageBufferElementSupported(
      module, structure, hlslUniformBufferScalarTypeSupported);
}

bool isSupportedStorageBufferElementType(const HIRModule &module,
                                         const HIRType &type) {
  if (!directxAtomicScalarStorageType(type).empty()) {
    return true;
  }
  return storageBufferElementTypeSupported(
      module, type, hlslStorageBufferScalarTypeSupported);
}

bool isDirectXDescriptorResourceKind(HIRResourceKind kind) {
  return kind == HIRResourceKind::Uniform || kind == HIRResourceKind::Buffer ||
         kind == HIRResourceKind::Texture ||
         kind == HIRResourceKind::Sampler;
}

std::string directxResourceRegisterClass(const HIRResource &resource) {
  switch (resource.kind) {
  case HIRResourceKind::Uniform:
    return "b";
  case HIRResourceKind::Buffer:
  case HIRResourceKind::StorageImage:
    return "u";
  case HIRResourceKind::Texture:
    return "t";
  case HIRResourceKind::Sampler:
    return "s";
  case HIRResourceKind::Shared:
  case HIRResourceKind::Value:
    break;
  }
  return "";
}

std::span<const HIRResourceKind>
directxRuntimeDescriptorRegisterClassKinds(HIRResourceKind kind) {
  static constexpr std::array<HIRResourceKind, 1> uniformKinds = {
      HIRResourceKind::Uniform};
  static constexpr std::array<HIRResourceKind, 1> bufferKinds = {
      HIRResourceKind::Buffer};
  static constexpr std::array<HIRResourceKind, 1> textureKinds = {
      HIRResourceKind::Texture};
  static constexpr std::array<HIRResourceKind, 1> samplerKinds = {
      HIRResourceKind::Sampler};

  switch (kind) {
  case HIRResourceKind::Uniform:
    return uniformKinds;
  case HIRResourceKind::Buffer:
    return bufferKinds;
  case HIRResourceKind::Texture:
    return textureKinds;
  case HIRResourceKind::Sampler:
    return samplerKinds;
  case HIRResourceKind::StorageImage:
  case HIRResourceKind::Shared:
  case HIRResourceKind::Value:
    break;
  }
  return {};
}

bool directxSameResourceDeclaration(const HIRResource &lhs,
                                    const HIRResource &rhs) {
  return lhs.kind == rhs.kind && lhs.type.name == rhs.type.name &&
         lhs.type.arraySize == rhs.type.arraySize && lhs.name == rhs.name &&
         lhs.set == rhs.set && lhs.binding == rhs.binding &&
         lhs.storageImageAccess == rhs.storageImageAccess &&
         lhs.storageImageFormat == rhs.storageImageFormat;
}

bool directxResourcesShareRegisterSpace(const HIRResource &lhs,
                                        const HIRResource &rhs) {
  const std::string lhsRegisterClass = directxResourceRegisterClass(lhs);
  return !lhsRegisterClass.empty() &&
         lhsRegisterClass == directxResourceRegisterClass(rhs) &&
         lhs.set == rhs.set;
}

std::optional<std::size_t>
directxParseLiteralDescriptorCount(std::string_view text) {
  if (!text.empty() && (text.back() == 'u' || text.back() == 'U')) {
    text.remove_suffix(1);
  }
  if (text.empty()) {
    return std::nullopt;
  }
  std::size_t value = 0;
  for (const char character : text) {
    if (character < '0' || character > '9') {
      return std::nullopt;
    }
    value = value * 10 + static_cast<std::size_t>(character - '0');
  }
  return value;
}

std::optional<std::size_t>
directxFixedDescriptorCount(const HIRResource &resource) {
  if (!resource.type.arraySize.has_value()) {
    return 1;
  }
  if (resource.type.arraySize->empty()) {
    return std::nullopt;
  }
  return directxParseLiteralDescriptorCount(*resource.type.arraySize);
}

bool directxRuntimeDescriptorArrayOverlapsResource(
    const HIRResource &runtimeArray, const HIRResource &resource) {
  if (!isRuntimeDescriptorArray(runtimeArray) ||
      directxSameResourceDeclaration(runtimeArray, resource) ||
      !directxResourcesShareRegisterSpace(runtimeArray, resource)) {
    return false;
  }
  if (resource.binding >= runtimeArray.binding) {
    return true;
  }
  const std::optional<std::size_t> descriptorCount =
      directxFixedDescriptorCount(resource);
  return !descriptorCount.has_value() ||
         *descriptorCount > runtimeArray.binding - resource.binding;
}

std::string directxResourceRegisterLabel(const HIRResource &resource) {
  return "register(" + directxResourceRegisterClass(resource) +
         std::to_string(resource.binding) + ", space" +
         std::to_string(resource.set) + ")";
}

std::string directxRuntimeDescriptorArrayConflictLabel(
    const HIRResource &runtimeArray, const HIRResource &resource) {
  const HIRResource *rangeStart = &runtimeArray;
  const HIRResource *overlapped = &resource;
  if (isRuntimeDescriptorArray(resource) &&
      (resource.binding < runtimeArray.binding ||
       (resource.binding == runtimeArray.binding &&
        resource.name < runtimeArray.name))) {
    rangeStart = &resource;
    overlapped = &runtimeArray;
  }
  return "runtime descriptor array '" + rangeStart->name + "' (" +
         resourceKindLabel(rangeStart->kind) + ") at " +
         directxResourceRegisterLabel(*rangeStart) + " overlaps resource '" +
         overlapped->name + "' (" + resourceKindLabel(overlapped->kind) +
         ") at " + directxResourceRegisterLabel(*overlapped);
}

std::optional<std::string> directxDescriptorRangeConflictLabel(
    const HIRResource &lhs, const HIRResource &rhs) {
  if (directxRuntimeDescriptorArrayOverlapsResource(lhs, rhs)) {
    return directxRuntimeDescriptorArrayConflictLabel(lhs, rhs);
  }
  if (directxRuntimeDescriptorArrayOverlapsResource(rhs, lhs)) {
    return directxRuntimeDescriptorArrayConflictLabel(rhs, lhs);
  }
  return std::nullopt;
}

std::set<std::string>
directxDescriptorRangeConflictLabels(const HIRModule &module,
                                     const HIRResource &resource) {
  std::set<std::string> conflicts;
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &candidate : stage.resources) {
      if (!isDirectXDescriptorResourceKind(candidate.kind)) {
        continue;
      }
      const std::optional<std::string> conflict =
          directxDescriptorRangeConflictLabel(resource, candidate);
      if (conflict.has_value()) {
        conflicts.insert(*conflict);
      }
    }
  }
  return conflicts;
}

bool directxRuntimeDescriptorArrayPolicySupported(const HIRModule &module,
                                                  const HIRResource &resource) {
  if (!isRuntimeDescriptorArray(resource)) {
    return true;
  }
  if (resource.kind == HIRResourceKind::Texture) {
    return true;
  }
  return runtimeDescriptorArraySupportedByPolicy(
      module, resource,
      RuntimeDescriptorArrayPolicy::AllowSingleUnboundedDescriptorArray,
      directxRuntimeDescriptorRegisterClassKinds(resource.kind));
}

bool directxResourceArrayShapeSupported(const HIRModule &module,
                                        const HIRResource &resource) {
  if (!isDirectXDescriptorResourceKind(resource.kind)) {
    return false;
  }
  return directxRuntimeDescriptorArrayPolicySupported(module, resource) &&
         directxDescriptorRangeConflictLabels(module, resource).empty();
}

std::string hlslStorageBufferElementType(const HIRModule &module,
                                         const HIRType &type) {
  const std::string atomicType = directxAtomicScalarStorageType(type);
  if (!atomicType.empty()) {
    return atomicType;
  }
  const std::string baseName = baseTypeName(type);
  if (!type.arraySize.has_value() &&
      isNumericScalarVectorOrMatrixType(baseName)) {
    const std::string valueType = hlslType(type);
    if (!valueType.empty()) {
      return valueType;
    }
  }
  const HIRStruct *structure = findStruct(module, type.name);
  if (structure != nullptr &&
      directxStructStorageBufferElementSupported(module, *structure)) {
    return structure->name;
  }
  return "";
}

std::string hlslUniformBufferElementType(const HIRModule &module,
                                         const HIRType &type) {
  HIRType elementType = type;
  elementType.arraySize.reset();
  const std::string baseName = baseTypeName(elementType);
  if (hlslUniformBufferScalarTypeSupported(baseName)) {
    return hlslTypeName(baseName);
  }
  const HIRStruct *structure = findStruct(module, elementType.name);
  if (structure != nullptr &&
      directxStructUniformBufferElementSupported(module, *structure)) {
    return structure->name;
  }
  return "";
}

std::string hlslUniformBufferDeclarator(const HIRModule &module,
                                        const HIRResource &resource) {
  const std::string elementType =
      hlslUniformBufferElementType(module, resource.type);
  if (elementType.empty()) {
    return "";
  }
  std::string declarator = elementType + " " + resource.name;
  if (resource.type.arraySize.has_value()) {
    declarator += "[" + *resource.type.arraySize + "]";
  }
  return declarator;
}

bool isSupportedUniformBufferResource(const HIRModule &module,
                                      const HIRResource &resource) {
  return resource.kind == HIRResourceKind::Uniform &&
         directxResourceArrayShapeSupported(module, resource) &&
         !hlslUniformBufferElementType(module, resource.type).empty();
}

std::string hlslUniformBufferDescriptorArrayType(const HIRModule &module,
                                                 const HIRResource &resource) {
  const std::string elementType =
      hlslUniformBufferElementType(module, resource.type);
  return elementType.empty() ? "" : "ConstantBuffer<" + elementType + ">";
}

std::string hlslSharedResourceElementType(const HIRType &type) {
  HIRType elementType = type;
  elementType.arraySize.reset();
  const std::string atomicType = directxAtomicScalarStorageType(elementType);
  if (!atomicType.empty()) {
    return atomicType;
  }
  return hlslTypeName(stripPointer(elementType.name));
}

std::string hlslTextureType(const HIRType &type) {
  if (!isSupportedTextureTypeName(type.name)) {
    return "";
  }
  if (type.name == "sampler2DShadow") {
    return "Texture2D<float>";
  }
  if (type.name == "sampler2DArrayShadow") {
    return "Texture2DArray<float>";
  }
  if (type.name == "samplerCubeShadow") {
    return "TextureCube<float>";
  }
  if (type.name == "samplerCubeArrayShadow") {
    return "TextureCubeArray<float>";
  }
  std::string sampleType = "float4";
  if (isSignedIntegerTextureTypeName(type.name)) {
    sampleType = "int4";
  } else if (isUnsignedIntegerTextureTypeName(type.name)) {
    sampleType = "uint4";
  }
  if (type.name == "sampler2DArray" || type.name == "texture2DArray" ||
      type.name == "isampler2DArray" || type.name == "usampler2DArray") {
    return "Texture2DArray<" + sampleType + ">";
  }
  if (type.name == "samplerCubeArray" || type.name == "textureCubeArray" ||
      type.name == "isamplerCubeArray" || type.name == "usamplerCubeArray") {
    return "TextureCubeArray<" + sampleType + ">";
  }
  if (type.name == "samplerCube" || type.name == "textureCube" ||
      type.name == "isamplerCube" || type.name == "usamplerCube") {
    return "TextureCube<" + sampleType + ">";
  }
  if (type.name == "sampler3D" || type.name == "texture3D" ||
      type.name == "isampler3D" || type.name == "usampler3D") {
    return "Texture3D<" + sampleType + ">";
  }
  return "Texture2D<" + sampleType + ">";
}

std::string hlslStorageImagePayloadType(const HIRType &type,
                                        bool scalarAtomicPayload = false) {
  const HIRType elementType = arrayElementType(type);
  const std::string payloadType =
      scalarAtomicPayload
          ? storageImageAtomicPayloadTypeName(baseTypeName(elementType))
          : storageImagePayloadVectorTypeName(baseTypeName(elementType));
  return hlslTypeName(payloadType);
}

std::string hlslStorageImageType(const HIRType &type,
                                 bool scalarAtomicPayload = false) {
  const HIRType elementType = arrayElementType(type);
  const std::string payloadType =
      hlslStorageImagePayloadType(elementType, scalarAtomicPayload);
  if (payloadType.empty()) {
    return "";
  }
  const std::string dimension =
      storageImageDimensionName(baseTypeName(elementType));
  if (dimension == "2d_array") {
    return "RWTexture2DArray<" + payloadType + ">";
  }
  if (dimension == "2d") {
    return "RWTexture2D<" + payloadType + ">";
  }
  return "";
}

std::string hlslFunctionParameterResourceType(const HIRModule &module,
                                              const HIRType &type) {
  if (functionParameterArrayShape(module, type) !=
      HIRFunctionParameterArrayShape::FixedSize) {
    return "";
  }
  if (isSupportedTextureTypeName(type.name)) {
    return hlslTextureType(type);
  }
  if (type.name == "sampler") {
    return "SamplerState";
  }
  if (type.name == "comparison_sampler") {
    return "SamplerComparisonState";
  }
  return "";
}

std::string hlslFunctionParameterDeclarator(const HIRModule *module,
                                            const HIRType &type,
                                            std::string_view name) {
  if (module != nullptr) {
    const std::string resourceType =
        hlslFunctionParameterResourceType(*module, type);
    if (!resourceType.empty()) {
      return resourceType + " " + std::string(name) + "[" + *type.arraySize +
             "]";
    }
  }
  return hlslDeclarator(module, type, name);
}

bool isSupportedTextureResource(const HIRResource &resource) {
  return resource.kind == HIRResourceKind::Texture &&
         !hlslTextureType(resource.type).empty();
}

bool isSupportedStorageImageResource(const HIRResource &resource) {
  return resource.kind == HIRResourceKind::StorageImage &&
         supportedResourceArraySize(resource.type) &&
         !hlslStorageImageType(resource.type).empty();
}

bool isSupportedSamplerResource(const HIRResource &resource) {
  return resource.kind == HIRResourceKind::Sampler &&
         (resource.type.name == "sampler" ||
          resource.type.name == "comparison_sampler");
}

bool expressionSupported(const HIRExpression &expression);

struct DirectXTextualSupportContext {
  const HIRModule *module = nullptr;
  std::set<std::string> callableFunctions;
  const HIRStage *stage = nullptr;
};

struct DirectXEmitContext {
  const HIRModule *module = nullptr;
  std::set<std::string> mixedSamplerStateResources;
  bool rewriteComputeInvocationBuiltins = false;
  const HIRStage *stage = nullptr;
  const HIRFunction *function = nullptr;
  std::size_t *nextTemporaryIndex = nullptr;
};

struct DirectXComputeInvocationBuiltin {
  std::string_view sourceName;
  std::string_view parameterName;
  std::string_view semantic;
};

constexpr std::array<DirectXComputeInvocationBuiltin, 3>
    kDirectXComputeInvocationBuiltins = {
        {{"gl_GlobalInvocationID", "crossgl_GlobalInvocationID",
          "SV_DispatchThreadID"},
         {"gl_LocalInvocationID", "crossgl_LocalInvocationID",
          "SV_GroupThreadID"},
         {"gl_WorkGroupID", "crossgl_WorkGroupID", "SV_GroupID"}}};

std::optional<std::string_view>
directxComputeInvocationParameterName(std::string_view sourceName) {
  for (const DirectXComputeInvocationBuiltin &builtin :
       kDirectXComputeInvocationBuiltins) {
    if (builtin.sourceName == sourceName) {
      return builtin.parameterName;
    }
  }
  return std::nullopt;
}

const HIRStage *findDirectXStage(const HIRModule &module,
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

const HIRStruct *directxStructType(const HIRModule &module,
                                   const HIRType &type) {
  if (type.arraySize.has_value() || type.name.empty() ||
      type.name.back() == '*') {
    return nullptr;
  }
  return findStruct(module, type.name);
}

bool isDirectXGraphicsScalarFieldType(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  return baseName == "float" || baseName == "int" || baseName == "uint" ||
         baseName == "bool" || isVectorType(baseName);
}

bool directxGraphicsStructSupported(const HIRStruct &structure) {
  if (structure.fields.empty()) {
    return false;
  }
  for (const HIRField &field : structure.fields) {
    if (!isDirectXGraphicsScalarFieldType(field.type)) {
      return false;
    }
  }
  return true;
}

const HIRField *directxGraphicsPositionField(const HIRStruct &structure) {
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

bool isDirectXGraphicsPositionField(const HIRField &field) {
  return (field.name == "position" || field.name == "clipPosition") &&
         !field.type.arraySize.has_value() && field.type.name == "vec4";
}

bool isSupportedGraphicsLocalDeclarationType(const HIRModule &module,
                                             const HIRType &type) {
  if (isSupportedValueType(type) || isSupportedLocalArrayType(module, type)) {
    return true;
  }
  return !type.arraySize.has_value() &&
         findStruct(module, stripPointer(type.name)) != nullptr;
}

bool directxGraphicsEntrySignatureSupported(const HIRModule &module,
                                            const HIRStage &stage,
                                            const HIRFunction &function) {
  if (stage.stage != "vertex" && stage.stage != "fragment") {
    return false;
  }
  if (function.parameters.size() != 1) {
    return false;
  }
  const HIRStruct *input =
      directxStructType(module, function.parameters.front().type);
  const HIRStruct *output = directxStructType(module, function.returnType);
  if (input == nullptr || output == nullptr ||
      !directxGraphicsStructSupported(*input) ||
      !directxGraphicsStructSupported(*output)) {
    return false;
  }
  if (stage.stage == "vertex" &&
      directxGraphicsPositionField(*output) == nullptr) {
    return false;
  }
  return true;
}

bool directxGraphicsVaryingsSupported(const HIRModule &module,
                                      const HIRFunction &vertexEntry,
                                      const HIRFunction &fragmentEntry) {
  const HIRStruct *vertexOutput =
      directxStructType(module, vertexEntry.returnType);
  const HIRStruct *fragmentInput =
      directxStructType(module, fragmentEntry.parameters.front().type);
  if (vertexOutput == nullptr || fragmentInput == nullptr) {
    return false;
  }
  for (const HIRField &field : fragmentInput->fields) {
    const HIRField *source = findField(*vertexOutput, field.name);
    if (source == nullptr || isDirectXGraphicsPositionField(*source) ||
        !typeEquals(source->type, field.type)) {
      return false;
    }
  }
  return true;
}

bool directxGraphicsStagePair(const HIRModule &module, const HIRStage *&vertex,
                              const HIRStage *&fragment) {
  vertex = nullptr;
  fragment = nullptr;
  if (module.stages.size() != 2) {
    return false;
  }
  vertex = findDirectXStage(module, "vertex");
  fragment = findDirectXStage(module, "fragment");
  return vertex != nullptr && fragment != nullptr;
}

bool isDirectXWorkgroupBarrierCall(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::Call &&
         expression.children.empty() &&
         (expression.value == "workgroupBarrier" ||
          expression.value == "barrier");
}

bool expressionSupported(const HIRExpression &expression,
                         const DirectXTextualSupportContext &context);

struct DirectXTextureSampleOperands {
  const HIRExpression *texture = nullptr;
  const HIRExpression *sampler = nullptr;
  const HIRExpression *coordinate = nullptr;
  const HIRExpression *lod = nullptr;
};

std::optional<DirectXTextureSampleOperands>
directxTextureSampleOperands(const HIRExpression &expression) {
  if (const std::optional<TextureSampleOperands> explicitLodOperands =
          textureSampleOperands(expression)) {
    return DirectXTextureSampleOperands{explicitLodOperands->texture,
                                        explicitLodOperands->sampler,
                                        explicitLodOperands->coordinate,
                                        explicitLodOperands->lod};
  }
  if (expression.kind != HIRExpressionKind::TextureSample ||
      (expression.value != "sample" && expression.value != "texture") ||
      expression.children.size() != 3) {
    return std::nullopt;
  }
  return DirectXTextureSampleOperands{&expression.children[0],
                                      &expression.children[1],
                                      &expression.children[2], nullptr};
}

bool textureOperandSupported(const HIRExpression &expression,
                             const DirectXTextualSupportContext &context) {
  if (!isResourceReferenceExpression(expression)) {
    return false;
  }
  return !isComparisonTextureTypeName(expression.type.name) &&
         !hlslTextureType(expression.type).empty() &&
         expressionSupported(expression, context);
}

bool comparisonTextureOperandSupported(
    const HIRExpression &expression,
    const DirectXTextualSupportContext &context) {
  if (!isResourceReferenceExpression(expression)) {
    return false;
  }
  return isComparisonTextureTypeName(expression.type.name) &&
         !hlslTextureType(expression.type).empty() &&
         expressionSupported(expression, context);
}

bool samplerOperandSupported(const HIRExpression &expression,
                             const DirectXTextualSupportContext &context) {
  if (!isResourceReferenceExpression(expression)) {
    return false;
  }
  return (expression.type.name == "sampler" ||
          expression.type.name == "comparison_sampler") &&
         !expression.type.arraySize.has_value() &&
         expressionSupported(expression, context);
}

bool rawSamplerOperandSupported(const HIRExpression &expression,
                                const DirectXTextualSupportContext &context) {
  if (!isResourceReferenceExpression(expression)) {
    return false;
  }
  return expression.type.name == "sampler" &&
         !expression.type.arraySize.has_value() &&
         expressionSupported(expression, context);
}

bool storageImageReferenceSupported(const HIRExpression &expression) {
  return isResourceReferenceExpression(expression) &&
         !expression.type.arraySize.has_value() &&
         isStorageImageResourceType(baseTypeName(expression.type));
}

bool storageImageCoordinatesSupported(
    const HIRExpression &image, const HIRExpression &coordinates,
    const DirectXTextualSupportContext &context) {
  const HIRType coordinateType = storageImageCoordinateType(image.type);
  return !coordinateType.name.empty() &&
         sameType(stripTypeQualifier(coordinates.type), coordinateType) &&
         expressionSupported(coordinates, context);
}

bool storageImagePayloadMatches(const HIRType &valueType,
                                const HIRType &imageType) {
  const HIRType payloadType = storageImagePayloadVectorType(imageType);
  return !payloadType.name.empty() &&
         sameType(stripTypeQualifier(valueType), payloadType);
}

bool storageImageLoadSupported(const HIRExpression &expression,
                               const DirectXTextualSupportContext &context) {
  if (expression.kind != HIRExpressionKind::Call ||
      expression.value != "imageLoad" || expression.children.size() != 2) {
    return false;
  }
  const HIRExpression &image = expression.children[0];
  return storageImageReferenceSupported(image) &&
         expressionSupported(image, context) &&
         storageImageCoordinatesSupported(image, expression.children[1],
                                          context) &&
         (expression.type.name.empty() ||
          storageImagePayloadMatches(expression.type, image.type));
}

bool storageImageStoreSupported(const HIRExpression &expression,
                                const DirectXTextualSupportContext &context) {
  if (expression.kind != HIRExpressionKind::Call ||
      expression.value != "imageStore" || expression.children.size() != 3) {
    return false;
  }
  const HIRExpression &image = expression.children[0];
  const HIRExpression &value = expression.children[2];
  return storageImageReferenceSupported(image) &&
         expressionSupported(image, context) &&
         storageImageCoordinatesSupported(image, expression.children[1],
                                          context) &&
         storageImagePayloadMatches(value.type, image.type) &&
         expressionSupported(value, context) &&
         (expression.type.name.empty() || isVoidType(expression.type));
}

bool storageImageCallSupported(const HIRExpression &expression,
                               const DirectXTextualSupportContext &context) {
  return storageImageLoadSupported(expression, context) ||
         storageImageStoreSupported(expression, context);
}

bool textureSampleSupported(const HIRExpression &expression,
                            const DirectXTextualSupportContext &context) {
  const std::optional<DirectXTextureSampleOperands> operands =
      directxTextureSampleOperands(expression);
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
                             const DirectXTextualSupportContext &context) {
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
      [](const HIRExpression &) { return true; });
}

bool isDirectXInterlockedAtomicCall(const HIRExpression &expression);

bool intrinsicCallSupported(const HIRExpression &expression,
                            const DirectXTextualSupportContext &context) {
  if (isDirectXInterlockedAtomicCall(expression)) {
    return false;
  }
  if (!backendIntrinsicCallSupported(TargetKind::DirectX, expression) ||
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

bool userFunctionCallSupported(const HIRExpression &expression,
                               const DirectXTextualSupportContext &context) {
  if (expression.value.empty() ||
      context.callableFunctions.count(expression.value) == 0) {
    return false;
  }
  for (const HIRExpression &argument : expression.children) {
    if (!expressionSupported(argument, context)) {
      return false;
    }
  }
  return true;
}

bool callExpressionSupported(const HIRExpression &expression,
                             const DirectXTextualSupportContext &context) {
  return storageImageCallSupported(expression, context) ||
         intrinsicCallSupported(expression, context) ||
         userFunctionCallSupported(expression, context);
}

bool selectExpressionSupported(const HIRExpression &expression,
                               const DirectXTextualSupportContext &context) {
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
                         const DirectXTextualSupportContext &context) {
  if (expression.kind == HIRExpressionKind::Call) {
    return callExpressionSupported(expression, context);
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
  return expressionSupported(expression, DirectXTextualSupportContext{});
}

bool constantSupported(const HIRConstant &constant) {
  return isSupportedValueType(constant.type) &&
         (expressionSupported(constant.value) ||
          constant.foldedValue.has_value());
}

bool declarationTypeSupported(const HIRType &type,
                              const DirectXTextualSupportContext &context) {
  if (isSupportedValueType(type)) {
    return true;
  }
  if (context.module == nullptr) {
    return false;
  }
  if (isSupportedLocalArrayType(*context.module, type)) {
    return true;
  }
  return context.stage != nullptr &&
         (context.stage->stage == "vertex" ||
          context.stage->stage == "fragment") &&
         isSupportedGraphicsLocalDeclarationType(*context.module, type);
}

std::set<std::string> fixedArrayParameterNames(const HIRModule &module,
                                               const HIRFunction &function) {
  std::set<std::string> names;
  for (const HIRParameter &parameter : function.parameters) {
    if (functionParameterArrayShape(module, parameter.type) ==
        HIRFunctionParameterArrayShape::FixedSize) {
      names.insert(parameter.name);
    }
  }
  return names;
}

const HIRResource *stageResourceByName(const HIRStage &stage,
                                       std::string_view name);

bool directxStorageImageResourceUsesAtomic(const HIRModule &module,
                                           const HIRResource &resource);

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

std::optional<std::string_view>
directxInterlockedAtomicIntrinsic(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Call) {
    return std::nullopt;
  }
  const bool scalarAtomic = expression.children.size() == 2;
  const bool imageAtomic = expression.children.size() == 3;
  if (expression.value == "atomicAdd") {
    return scalarAtomic ? std::optional<std::string_view>("InterlockedAdd")
                        : std::nullopt;
  }
  if (expression.value == "atomicExchange") {
    return scalarAtomic ? std::optional<std::string_view>("InterlockedExchange")
                        : std::nullopt;
  }
  if (expression.value == "atomicAnd") {
    return scalarAtomic ? std::optional<std::string_view>("InterlockedAnd")
                        : std::nullopt;
  }
  if (expression.value == "atomicMin") {
    return scalarAtomic ? std::optional<std::string_view>("InterlockedMin")
                        : std::nullopt;
  }
  if (expression.value == "atomicMax") {
    return scalarAtomic ? std::optional<std::string_view>("InterlockedMax")
                        : std::nullopt;
  }
  if (expression.value == "atomicOr") {
    return scalarAtomic ? std::optional<std::string_view>("InterlockedOr")
                        : std::nullopt;
  }
  if (expression.value == "atomicXor") {
    return scalarAtomic ? std::optional<std::string_view>("InterlockedXor")
                        : std::nullopt;
  }
  if (expression.value == "imageAtomicAdd") {
    return imageAtomic ? std::optional<std::string_view>("InterlockedAdd")
                       : std::nullopt;
  }
  if (expression.value == "imageAtomicExchange") {
    return imageAtomic ? std::optional<std::string_view>("InterlockedExchange")
                       : std::nullopt;
  }
  if (expression.value == "imageAtomicAnd") {
    return imageAtomic ? std::optional<std::string_view>("InterlockedAnd")
                       : std::nullopt;
  }
  if (expression.value == "imageAtomicMin") {
    return imageAtomic ? std::optional<std::string_view>("InterlockedMin")
                       : std::nullopt;
  }
  if (expression.value == "imageAtomicMax") {
    return imageAtomic ? std::optional<std::string_view>("InterlockedMax")
                       : std::nullopt;
  }
  if (expression.value == "imageAtomicOr") {
    return imageAtomic ? std::optional<std::string_view>("InterlockedOr")
                       : std::nullopt;
  }
  if (expression.value == "imageAtomicXor") {
    return imageAtomic ? std::optional<std::string_view>("InterlockedXor")
                       : std::nullopt;
  }
  return std::nullopt;
}

bool isDirectXInterlockedAtomicCall(const HIRExpression &expression) {
  return directxInterlockedAtomicIntrinsic(expression).has_value();
}

bool isDirectXStorageImageAtomicCall(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::Call &&
         expression.children.size() == 3 &&
         (expression.value == "imageAtomicAdd" ||
          expression.value == "imageAtomicExchange" ||
          expression.value == "imageAtomicAnd" ||
          expression.value == "imageAtomicMin" ||
          expression.value == "imageAtomicMax" ||
          expression.value == "imageAtomicOr" ||
          expression.value == "imageAtomicXor");
}

const HIRExpression &
directxInterlockedAtomicTarget(const HIRExpression &expression) {
  return expression.children.front();
}

const HIRExpression &
directxInterlockedAtomicValue(const HIRExpression &expression) {
  return expression
      .children[isDirectXStorageImageAtomicCall(expression) ? 2 : 1];
}

bool directxInterlockedAtomicStatementRequiresOriginalValue(
    const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::Call &&
         (expression.value == "atomicExchange" ||
          expression.value == "imageAtomicExchange");
}

bool directxAtomicCaptureResultTargetSupported(
    const HIRExpression &expression) {
  if (!isSupportedValueType(expression.type)) {
    return false;
  }
  if (expression.kind == HIRExpressionKind::Identifier) {
    return true;
  }
  return expression.kind == HIRExpressionKind::Group &&
         expression.children.size() == 1 &&
         directxAtomicCaptureResultTargetSupported(expression.children.front());
}

const HIRResource *
directxAtomicTargetRootResource(const HIRExpression &expression,
                                const DirectXTextualSupportContext &context) {
  if (context.stage == nullptr) {
    return nullptr;
  }
  const HIRExpression *root = rootIdentifierExpression(expression);
  if (root == nullptr) {
    return nullptr;
  }
  return stageResourceByName(*context.stage, root->value);
}

bool directxAtomicTargetSupported(const HIRExpression &expression,
                                  const DirectXTextualSupportContext &context) {
  if (directxAtomicScalarStorageType(expression.type).empty()) {
    return false;
  }

  const HIRResource *resource =
      directxAtomicTargetRootResource(expression, context);
  if (resource == nullptr || (resource->kind != HIRResourceKind::Buffer &&
                              resource->kind != HIRResourceKind::Shared)) {
    return false;
  }

  switch (expression.kind) {
  case HIRExpressionKind::Identifier:
    return resource->kind == HIRResourceKind::Shared;
  case HIRExpressionKind::Group:
    return expression.children.size() == 1 &&
           directxAtomicTargetSupported(expression.children.front(), context);
  case HIRExpressionKind::IndexAccess:
    return expression.children.size() == 2 &&
           expressionSupported(expression.children[1], context);
  default:
    return false;
  }
}

std::string directxStorageImageAtomicPayloadTypeName(const HIRType &type) {
  const std::string payloadType =
      storageImageAtomicPayloadTypeName(baseTypeName(type));
  return hlslTypeName(payloadType);
}

bool directxStorageImageAtomicResourceSupported(const HIRResource &resource) {
  if (resource.kind != HIRResourceKind::StorageImage ||
      resource.storageImageAccess != HIRStorageImageAccess::ReadWrite) {
    return false;
  }
  const HIRType elementType = arrayElementType(resource.type);
  const std::string format = resource.storageImageFormat.value_or(
      storageImageFormatName(baseTypeName(elementType)));
  return storageImageFormatSupportsAtomics(format, baseTypeName(elementType));
}

bool directxStorageImageAtomicSupported(
    const HIRExpression &expression,
    const DirectXTextualSupportContext &context) {
  if (!isDirectXStorageImageAtomicCall(expression)) {
    return false;
  }
  const HIRExpression &image = expression.children[0];
  const HIRExpression &coordinates = expression.children[1];
  const HIRExpression &value = expression.children[2];
  const HIRResource *resource = directxAtomicTargetRootResource(image, context);
  if (resource == nullptr ||
      !directxStorageImageAtomicResourceSupported(*resource) ||
      !storageImageReferenceSupported(image) ||
      !expressionSupported(image, context) ||
      !storageImageCoordinatesSupported(image, coordinates, context) ||
      !expressionSupported(value, context)) {
    return false;
  }
  const std::string payloadType =
      directxStorageImageAtomicPayloadTypeName(image.type);
  return !payloadType.empty() && !value.type.arraySize.has_value() &&
         baseTypeName(value.type) == payloadType &&
         (expression.type.name.empty() ||
          baseTypeName(expression.type) == payloadType);
}

bool directxInterlockedAtomicStatementSupported(
    const HIRExpression &expression,
    const DirectXTextualSupportContext &context) {
  if (!isDirectXInterlockedAtomicCall(expression)) {
    return false;
  }
  if (isDirectXStorageImageAtomicCall(expression)) {
    return directxStorageImageAtomicSupported(expression, context);
  }
  const HIRExpression &target = directxInterlockedAtomicTarget(expression);
  const HIRExpression &delta = directxInterlockedAtomicValue(expression);
  const std::string targetType = directxAtomicScalarStorageType(target.type);
  if (targetType.empty() || !directxAtomicTargetSupported(target, context) ||
      delta.type.arraySize.has_value() ||
      baseTypeName(delta.type) != targetType) {
    return false;
  }
  return expressionSupported(delta, context);
}

bool directxInterlockedAtomicCaptureSupported(
    const HIRExpression &expression, const HIRType &resultType,
    const DirectXTextualSupportContext &context) {
  if (!directxInterlockedAtomicStatementSupported(expression, context) ||
      !isSupportedValueType(resultType)) {
    return false;
  }
  const HIRExpression &target = directxInterlockedAtomicTarget(expression);
  const std::string targetType =
      isDirectXStorageImageAtomicCall(expression)
          ? directxStorageImageAtomicPayloadTypeName(target.type)
          : directxAtomicScalarStorageType(target.type);
  return !targetType.empty() && baseTypeName(resultType) == targetType;
}

bool statementSupported(const HIRStatement &statement,
                        const DirectXTextualSupportContext &context) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    if (!declarationTypeSupported(statement.declaredType, context)) {
      return false;
    }
    if (statement.value.kind == HIRExpressionKind::Empty) {
      return true;
    }
    if (isDirectXInterlockedAtomicCall(statement.value)) {
      return directxInterlockedAtomicCaptureSupported(
          statement.value, statement.declaredType, context);
    }
    return expressionSupported(statement.value, context);
  case HIRStatementKind::Assignment:
    if (isDirectXInterlockedAtomicCall(statement.value)) {
      return directxAtomicCaptureResultTargetSupported(statement.target) &&
             directxInterlockedAtomicCaptureSupported(
                 statement.value, statement.target.type, context);
    }
    return expressionSupported(statement.target, context) &&
           expressionSupported(statement.value, context);
  case HIRStatementKind::Return:
    return statement.value.kind == HIRExpressionKind::Empty ||
           expressionSupported(statement.value, context);
  case HIRStatementKind::Expression:
    return isDirectXWorkgroupBarrierCall(statement.value) ||
           directxInterlockedAtomicStatementSupported(statement.value,
                                                      context) ||
           expressionSupported(statement.value, context);
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
      if (!loopHeaderStatementSupportedByPolicy(
              initializer,
              [&](const HIRType &type) {
                return declarationTypeSupported(type, context);
              },
              [&](const HIRExpression &expression) {
                return expressionSupported(expression, context);
              })) {
        return false;
      }
    }
    if (!statement.update.empty()) {
      if (statement.update.size() > 1) {
        return false;
      }
      for (const HIRStatement &update : statement.update) {
        if (!loopHeaderStatementSupportedByPolicy(
                update,
                [&](const HIRType &type) {
                  return declarationTypeSupported(type, context);
                },
                [&](const HIRExpression &expression) {
                  return expressionSupported(expression, context);
                })) {
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

std::string emitExpression(const HIRExpression &expression,
                           const DirectXEmitContext &context = {});
std::optional<std::string> samplerBaseName(const HIRExpression &sampler);

std::string comparisonSamplerAliasName(std::string_view name) {
  return std::string(name) + "_cglComparison";
}

std::string emitExpressionWithIdentifierAlias(
    const HIRExpression &expression, std::string_view identifier,
    std::string_view alias, const DirectXEmitContext &context) {
  switch (expression.kind) {
  case HIRExpressionKind::Identifier:
    return expression.value == identifier ? std::string(alias)
                                          : expression.value;
  case HIRExpressionKind::Group:
    return expression.children.empty() ? "()"
                                       : "(" +
                                             emitExpressionWithIdentifierAlias(
                                                 expression.children.front(),
                                                 identifier, alias, context) +
                                             ")";
  case HIRExpressionKind::IndexAccess:
    if (expression.children.size() < 2) {
      return "/* unsupported */";
    }
    return emitExpressionWithIdentifierAlias(expression.children[0], identifier,
                                             alias, context) +
           "[" + emitExpression(expression.children[1], context) + "]";
  case HIRExpressionKind::NonUniform:
    return expression.children.empty()
               ? "NonUniformResourceIndex(/* unsupported */)"
               : "NonUniformResourceIndex(" +
                     emitExpressionWithIdentifierAlias(
                         expression.children.front(), identifier, alias,
                         context) +
                     ")";
  default:
    return emitExpression(expression, context);
  }
}

std::string emitComparisonSamplerExpression(const HIRExpression &expression,
                                            const DirectXEmitContext &context) {
  const std::optional<std::string> samplerName = samplerBaseName(expression);
  if (!samplerName.has_value() ||
      context.mixedSamplerStateResources.count(*samplerName) == 0) {
    return emitExpression(expression, context);
  }
  return emitExpressionWithIdentifierAlias(
      expression, *samplerName, comparisonSamplerAliasName(*samplerName),
      context);
}

const HIRResource *
directxExpressionRootResource(const HIRModule *module,
                              const HIRExpression &expression) {
  if (module == nullptr) {
    return nullptr;
  }
  const HIRExpression *root = rootIdentifierExpression(expression);
  if (root == nullptr) {
    return nullptr;
  }
  for (const HIRStage &stage : module->stages) {
    const HIRResource *resource = stageResourceByName(stage, root->value);
    if (resource != nullptr) {
      return resource;
    }
  }
  return nullptr;
}

bool directxStorageImageExpressionUsesAtomicPayload(
    const DirectXEmitContext &context, const HIRExpression &expression) {
  const HIRResource *resource =
      directxExpressionRootResource(context.module, expression);
  return resource != nullptr && resource->kind == HIRResourceKind::StorageImage &&
         directxStorageImageResourceUsesAtomic(*context.module, *resource);
}

std::string directxStorageImageScalarLoadAsVector(const HIRType &type,
                                                  std::string loadExpression) {
  const std::string vectorType = hlslType(type);
  if (vectorType == "int4") {
    return "int4(" + loadExpression + ", 0, 0, 1)";
  }
  if (vectorType == "uint4") {
    return "uint4(" + loadExpression + ", 0u, 0u, 1u)";
  }
  return loadExpression;
}

std::string emitStorageImageLoad(const HIRExpression &expression,
                                 const DirectXEmitContext &context) {
  if (expression.children.size() != 2) {
    return "/* unsupported */";
  }
  const std::string loadExpression =
      emitExpression(expression.children[0], context) + ".Load(" +
      emitExpression(expression.children[1], context) + ")";
  if (!directxStorageImageExpressionUsesAtomicPayload(context,
                                                      expression.children[0])) {
    return loadExpression;
  }
  return directxStorageImageScalarLoadAsVector(expression.type, loadExpression);
}

std::string emitStorageImageStore(const HIRExpression &expression,
                                  const DirectXEmitContext &context) {
  if (expression.children.size() != 3) {
    return "/* unsupported */";
  }
  std::string valueExpression = emitExpression(expression.children[2], context);
  if (directxStorageImageExpressionUsesAtomicPayload(context,
                                                     expression.children[0])) {
    valueExpression = "(" + valueExpression + ").x";
  }
  return emitExpression(expression.children[0], context) + "[" +
         emitExpression(expression.children[1], context) +
         "] = " + valueExpression;
}

std::optional<std::string> directxCallArgumentOverride(
    std::size_t index,
    const std::vector<std::pair<std::size_t, std::string>> &overrides) {
  for (const auto &[overrideIndex, value] : overrides) {
    if (overrideIndex == index) {
      return value;
    }
  }
  return std::nullopt;
}

std::string emitCallWithArgumentOverrides(
    const HIRExpression &expression, const DirectXEmitContext &context,
    const std::vector<std::pair<std::size_t, std::string>> &overrides) {
  if (isDirectXWorkgroupBarrierCall(expression)) {
    return "GroupMemoryBarrierWithGroupSync()";
  }
  if (expression.value == "imageLoad") {
    return emitStorageImageLoad(expression, context);
  }
  if (expression.value == "imageStore") {
    return emitStorageImageStore(expression, context);
  }
  const std::optional<std::string> callee =
      backendIntrinsicNameForCall(TargetKind::DirectX, expression);
  const std::string functionName = callee.value_or(expression.value);
  if (functionName.empty()) {
    return "/* unsupported */";
  }
  std::ostringstream out;
  out << functionName << "(";
  for (std::size_t index = 0; index < expression.children.size(); ++index) {
    if (index != 0) {
      out << ", ";
    }
    if (const std::optional<std::string> override =
            directxCallArgumentOverride(index, overrides)) {
      out << *override;
    } else {
      out << emitExpression(expression.children[index], context);
    }
  }
  out << ")";
  return out.str();
}

std::string emitCall(const HIRExpression &expression,
                     const DirectXEmitContext &context) {
  return emitCallWithArgumentOverrides(expression, context, {});
}

std::string emitInterlockedAtomicStatement(const HIRExpression &expression,
                                           const DirectXEmitContext &context) {
  const std::optional<std::string_view> intrinsic =
      directxInterlockedAtomicIntrinsic(expression);
  if (!intrinsic.has_value()) {
    return "/* unsupported */";
  }
  const HIRExpression &target = directxInterlockedAtomicTarget(expression);
  const HIRExpression &value = directxInterlockedAtomicValue(expression);
  const std::string targetText =
      isDirectXStorageImageAtomicCall(expression)
          ? emitExpression(target, context) + "[" +
                emitExpression(expression.children[1], context) + "]"
          : emitExpression(target, context);
  return std::string(*intrinsic) + "(" + targetText + ", " +
         emitExpression(value, context) + ")";
}

std::string
emitInterlockedAtomicCaptureStatement(const HIRExpression &expression,
                                      std::string_view result,
                                      const DirectXEmitContext &context) {
  const std::optional<std::string_view> intrinsic =
      directxInterlockedAtomicIntrinsic(expression);
  if (!intrinsic.has_value()) {
    return "/* unsupported */";
  }
  const HIRExpression &target = directxInterlockedAtomicTarget(expression);
  const HIRExpression &value = directxInterlockedAtomicValue(expression);
  const std::string targetText =
      isDirectXStorageImageAtomicCall(expression)
          ? emitExpression(target, context) + "[" +
                emitExpression(expression.children[1], context) + "]"
          : emitExpression(target, context);
  return std::string(*intrinsic) + "(" + targetText + ", " +
         emitExpression(value, context) + ", " + std::string(result) + ")";
}

void emitInterlockedAtomicStatement(std::ostringstream &out,
                                    const HIRExpression &expression,
                                    std::size_t indentation,
                                    const DirectXEmitContext &context) {
  const std::string spaces(indentation, ' ');
  if (!directxInterlockedAtomicStatementRequiresOriginalValue(expression)) {
    out << spaces << emitInterlockedAtomicStatement(expression, context)
        << ";\n";
    return;
  }

  const std::string scratchType =
      isDirectXStorageImageAtomicCall(expression)
          ? directxStorageImageAtomicPayloadTypeName(
                directxInterlockedAtomicTarget(expression).type)
          : directxAtomicScalarStorageType(
                directxInterlockedAtomicTarget(expression).type);
  out << spaces << "{\n"
      << spaces << "  " << (scratchType.empty() ? "int" : scratchType)
      << " crossgl_atomic_exchange_old_value;\n"
      << spaces << "  "
      << emitInterlockedAtomicCaptureStatement(
             expression, "crossgl_atomic_exchange_old_value", context)
      << ";\n"
      << spaces << "}\n";
}

std::string emitTextureSample(const HIRExpression &expression,
                              const DirectXEmitContext &context) {
  const std::optional<DirectXTextureSampleOperands> operands =
      directxTextureSampleOperands(expression);
  if (!operands.has_value()) {
    return "/* unsupported */";
  }
  return emitExpression(*operands->texture, context) + ".SampleLevel(" +
         emitExpression(*operands->sampler, context) + ", " +
         emitExpression(*operands->coordinate, context) + ", " +
         (operands->lod == nullptr ? "0.0"
                                   : emitExpression(*operands->lod, context)) +
         ")";
}

std::string emitTextureCompare(const HIRExpression &expression,
                               const DirectXEmitContext &context) {
  const std::optional<TextureCompareManualOperands> manualOperands =
      textureCompareManualOperands(expression);
  if (manualOperands.has_value()) {
    const std::optional<TextureCompareOperator> compareOperator =
        textureCompareOperatorFromExpression(*manualOperands->compareOp);
    if (!compareOperator.has_value()) {
      return "/* unsupported */";
    }

    const std::string compareConstant(
        textureCompareOperatorConstantName(*compareOperator));

    const auto rawSample = [&](std::string_view offset) {
      std::string sample =
          emitExpression(*manualOperands->texture, context) + ".SampleLevel(" +
          emitExpression(*manualOperands->sampler, context) + ", " +
          emitExpression(*manualOperands->coordinate, context) + ", " +
          emitExpression(*manualOperands->lod, context);
      if (!offset.empty()) {
        sample += ", " + std::string(offset);
      }
      sample += ")";
      return sample;
    };
    const auto compareTap = [&](std::string_view offset) {
      return "cglCompareDepth(" + rawSample(offset) + ", " +
             emitExpression(*manualOperands->depth, context) + ", " +
             compareConstant + ")";
    };

    if (manualOperands->gather2x2) {
      return "((" + compareTap("int2(0, 0)") + " + " +
             compareTap("int2(1, 0)") + " + " + compareTap("int2(0, 1)") +
             " + " + compareTap("int2(1, 1)") + ") * 0.25)";
    }

    if (manualOperands->kernelTapCount != 0) {
      std::string result = "(";
      for (std::size_t index = 0; index < manualOperands->kernelTapCount;
           ++index) {
        if (index != 0) {
          result += " + ";
        }
        result +=
            "(" +
            compareTap(emitExpression(*manualOperands->kernelOffsets[index],
                                      context)) +
            " * " +
            emitExpression(*manualOperands->kernelWeights[index], context) +
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
  if (operands->explicitLod) {
    return emitExpression(*operands->texture, context) + ".SampleCmpLevel(" +
           emitComparisonSamplerExpression(*operands->sampler, context) + ", " +
           emitExpression(*operands->coordinate, context) + ", " +
           emitExpression(*operands->depth, context) + ", " +
           emitExpression(*operands->lod, context) + ")";
  }
  return emitExpression(*operands->texture, context) + ".SampleCmpLevelZero(" +
         emitComparisonSamplerExpression(*operands->sampler, context) + ", " +
         emitExpression(*operands->coordinate, context) + ", " +
         emitExpression(*operands->depth, context) + ")";
}

std::string emitDirectXFloatMatrixScalar(std::string expression,
                                         const HIRType &type) {
  const std::string baseName = baseTypeName(type);
  if (baseName == "int" || baseName == "uint") {
    return "float(" + expression + ")";
  }
  return expression;
}

std::string hlslSubscriptBase(std::string expression) {
  if (expression.find_first_of(" \t+-*/?:,()") == std::string::npos) {
    return expression;
  }
  return "(" + expression + ")";
}

bool appendDirectXMatrixConstructorScalars(
    const HIRExpression &expression, const DirectXEmitContext &context,
    std::vector<std::string> &scalars) {
  const std::string baseName = baseTypeName(expression.type);
  if (isNumericScalarTypeName(baseName)) {
    scalars.push_back(emitDirectXFloatMatrixScalar(
        emitExpression(expression, context), expression.type));
    return true;
  }

  const std::optional<std::size_t> width = vectorWidthFromName(baseName);
  if (!width.has_value()) {
    return false;
  }
  const HIRType componentType = scalarTypeForVector(baseName);
  if (!isNumericScalarTypeName(baseTypeName(componentType))) {
    return false;
  }

  const std::string vectorExpression =
      hlslSubscriptBase(emitExpression(expression, context));
  for (std::size_t index = 0; index < *width; ++index) {
    scalars.push_back(emitDirectXFloatMatrixScalar(
        vectorExpression + "[" + std::to_string(index) + "]", componentType));
  }
  return true;
}

std::string emitDirectXMatrixFromColumnMajorScalars(
    const HIRType &matrixType, const std::vector<std::string> &scalars) {
  const std::optional<std::size_t> dimension =
      matrixDimensionFromName(baseTypeName(matrixType));
  if (!dimension.has_value() || scalars.size() != (*dimension * *dimension)) {
    return hlslType(matrixType) + "(/* unsupported */)";
  }

  std::ostringstream out;
  out << hlslType(matrixType) << "(";
  bool first = true;
  for (std::size_t row = 0; row < *dimension; ++row) {
    for (std::size_t column = 0; column < *dimension; ++column) {
      if (!first) {
        out << ", ";
      }
      first = false;
      out << scalars[column * *dimension + row];
    }
  }
  out << ")";
  return out.str();
}

std::string emitDirectXMatrixFromScalar(const HIRExpression &expression,
                                        const DirectXEmitContext &context) {
  const std::optional<std::size_t> dimension =
      matrixDimensionFromName(baseTypeName(expression.type));
  if (!dimension.has_value() || expression.children.empty()) {
    return hlslType(expression.type) + "(/* unsupported */)";
  }

  const std::string diagonal = emitDirectXFloatMatrixScalar(
      emitExpression(expression.children.front(), context),
      expression.children.front().type);
  std::vector<std::string> scalars;
  scalars.reserve(*dimension * *dimension);
  for (std::size_t column = 0; column < *dimension; ++column) {
    for (std::size_t row = 0; row < *dimension; ++row) {
      scalars.push_back(column == row ? diagonal : "0.0");
    }
  }
  return emitDirectXMatrixFromColumnMajorScalars(expression.type, scalars);
}

std::string emitDirectXMatrixFromMatrix(const HIRExpression &expression,
                                        const DirectXEmitContext &context) {
  if (expression.children.empty()) {
    return hlslType(expression.type) + "(/* unsupported */)";
  }
  const HIRExpression &source = expression.children.front();
  if (sameType(expression.type, source.type)) {
    return emitExpression(source, context);
  }

  const std::optional<std::size_t> targetDimension =
      matrixDimensionFromName(baseTypeName(expression.type));
  const std::optional<std::size_t> sourceDimension =
      matrixDimensionFromName(baseTypeName(source.type));
  if (!targetDimension.has_value() || !sourceDimension.has_value()) {
    return hlslType(expression.type) + "(/* unsupported */)";
  }

  const std::string sourceExpression =
      hlslSubscriptBase(emitExpression(source, context));
  std::vector<std::string> scalars;
  scalars.reserve(*targetDimension * *targetDimension);
  for (std::size_t column = 0; column < *targetDimension; ++column) {
    for (std::size_t row = 0; row < *targetDimension; ++row) {
      if (column < *sourceDimension && row < *sourceDimension) {
        scalars.push_back(sourceExpression + "[" + std::to_string(row) + "][" +
                          std::to_string(column) + "]");
      } else {
        scalars.push_back(column == row ? "1.0" : "0.0");
      }
    }
  }
  return emitDirectXMatrixFromColumnMajorScalars(expression.type, scalars);
}

std::string emitDirectXMatrixConstructor(const HIRExpression &expression,
                                         const DirectXEmitContext &context) {
  if (expression.children.size() == 1) {
    const std::string sourceBaseName =
        baseTypeName(expression.children.front().type);
    if (isNumericScalarTypeName(sourceBaseName)) {
      return emitDirectXMatrixFromScalar(expression, context);
    }
    if (isMatrixType(sourceBaseName)) {
      return emitDirectXMatrixFromMatrix(expression, context);
    }
  }

  std::vector<std::string> scalars;
  const std::optional<std::size_t> dimension =
      matrixDimensionFromName(baseTypeName(expression.type));
  if (dimension.has_value()) {
    scalars.reserve(*dimension * *dimension);
  }
  for (const HIRExpression &child : expression.children) {
    if (!appendDirectXMatrixConstructorScalars(child, context, scalars)) {
      return hlslType(expression.type) + "(/* unsupported */)";
    }
  }
  return emitDirectXMatrixFromColumnMajorScalars(expression.type, scalars);
}

std::string emitDirectXBinaryExpression(const HIRExpression &expression,
                                        const DirectXEmitContext &context) {
  if (isDirectXMatrixProductExpression(expression)) {
    return "mul(" + emitExpression(expression.children[0], context) + ", " +
           emitExpression(expression.children[1], context) + ")";
  }
  return emitExpression(expression.children[0], context) + " " +
         expression.value + " " + emitExpression(expression.children[1], context);
}

std::string emitExpression(const HIRExpression &expression,
                           const DirectXEmitContext &context) {
  switch (expression.kind) {
  case HIRExpressionKind::Empty:
    return "";
  case HIRExpressionKind::Identifier:
    if (context.rewriteComputeInvocationBuiltins) {
      const std::optional<std::string_view> parameterName =
          directxComputeInvocationParameterName(expression.value);
      if (parameterName.has_value()) {
        return std::string(*parameterName);
      }
    }
    return expression.value;
  case HIRExpressionKind::Literal:
    return expression.value;
  case HIRExpressionKind::Group:
    return expression.children.empty()
               ? "()"
               : "(" + emitExpression(expression.children.front(), context) +
                     ")";
  case HIRExpressionKind::MemberAccess:
    return expression.children.empty()
               ? expression.value
               : emitExpression(expression.children.front(), context) + "." +
                     expression.value;
  case HIRExpressionKind::IndexAccess:
    return emitExpression(expression.children[0], context) + "[" +
           emitExpression(expression.children[1], context) + "]";
  case HIRExpressionKind::NonUniform:
    return expression.children.empty()
               ? "NonUniformResourceIndex(/* unsupported */)"
               : "NonUniformResourceIndex(" +
                     emitExpression(expression.children.front(), context) + ")";
  case HIRExpressionKind::Constructor: {
    if (isMatrixType(baseTypeName(expression.type))) {
      return emitDirectXMatrixConstructor(expression, context);
    }
    std::ostringstream out;
    out << hlslType(expression.type) << "(";
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
    return expression.value +
           emitExpression(expression.children.front(), context);
  case HIRExpressionKind::Binary:
    return emitDirectXBinaryExpression(expression, context);
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

std::string emitConstantValue(const HIRConstant &constant) {
  if (constant.value.kind == HIRExpressionKind::Select &&
      constant.foldedValue.has_value()) {
    return *constant.foldedValue;
  }
  if (expressionSupported(constant.value)) {
    return emitExpression(constant.value);
  }
  return constant.foldedValue.value_or("/* unsupported */");
}

std::string emitStatementInline(const HIRStatement &statement,
                                const DirectXEmitContext &context = {}) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration: {
    std::ostringstream out;
    out << hlslDeclarator(context.module, statement.declaredType,
                          statement.name);
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
                               const DirectXEmitContext &context) {
  return statement.initializer.empty()
             ? ""
             : emitStatementInline(statement.initializer.front(), context);
}

std::string emitForUpdate(const HIRStatement &statement,
                          const DirectXEmitContext &context) {
  if (!statement.updateTokens.empty()) {
    return tokensToText(statement.updateTokens);
  }
  return statement.update.empty()
             ? ""
             : emitStatementInline(statement.update.front(), context);
}

const HIRExpression *directxStatementDirectCallValue(
    const HIRStatement &statement);

bool directxStorageBufferFieldArrayWriteBackArgument(
    const HIRModule &module, const HIRFunction &caller,
    const HIRExpression &argument, const HIRStage *stage);

bool directxFunctionParameterArrayWriteArgumentAliases(
    const HIRModule &module, const HIRFunction &callee,
    const HIRExpression &call, std::size_t parameterIndex);

std::set<std::string>
writtenFunctionParameterArrayNames(const HIRModule &module,
                                   const HIRFunction &function);

struct DirectXArrayWriteBackArgument {
  std::size_t argumentIndex = 0;
  HIRType type;
  const HIRExpression *argument = nullptr;
  std::string temporaryName;
};

struct DirectXArrayWriteBackRewrite {
  const HIRExpression *call = nullptr;
  std::vector<DirectXArrayWriteBackArgument> arguments;
  std::vector<std::pair<std::size_t, std::string>> argumentOverrides;
  bool materializeNestedCallResult = false;
};

std::string directxInternalIdentifierFragment(std::string_view value) {
  std::string fragment;
  fragment.reserve(value.size());
  for (const char character : value) {
    const bool alnum =
        (character >= 'a' && character <= 'z') ||
        (character >= 'A' && character <= 'Z') ||
        (character >= '0' && character <= '9');
    fragment.push_back(alnum ? character : '_');
  }
  return fragment.empty() ? "value" : fragment;
}

std::size_t nextDirectXTemporaryIndex(const DirectXEmitContext &context) {
  if (context.nextTemporaryIndex == nullptr) {
    return 0;
  }
  const std::size_t index = *context.nextTemporaryIndex;
  ++(*context.nextTemporaryIndex);
  return index;
}

std::string directxArrayWriteBackTemporaryName(
    const HIRExpression &call, const HIRParameter &parameter,
    const DirectXEmitContext &context) {
  return "crossgl_param_array_writeback_" +
         std::to_string(nextDirectXTemporaryIndex(context)) + "_" +
         directxInternalIdentifierFragment(call.value) + "_" +
         directxInternalIdentifierFragment(parameter.name);
}

const HIRFunction *findDirectXEmitFunction(const DirectXEmitContext &context,
                                           std::string_view name) {
  if (context.module == nullptr || context.stage == nullptr) {
    return nullptr;
  }
  for (const HIRFunction &function : context.module->functions) {
    if (function.name == name) {
      return &function;
    }
  }
  for (const HIRFunction &function : context.stage->functions) {
    if (function.name == name) {
      return &function;
    }
  }
  return nullptr;
}

const HIRExpression *directxTransparentExpression(
    const HIRExpression &expression) {
  const HIRExpression *current = &expression;
  while (current->kind == HIRExpressionKind::Group &&
         current->children.size() == 1) {
    current = &current->children.front();
  }
  return current;
}

bool directxExpressionContainsNode(const HIRExpression &expression,
                                   const HIRExpression &node) {
  if (&expression == &node) {
    return true;
  }
  for (const HIRExpression &child : expression.children) {
    if (directxExpressionContainsNode(child, node)) {
      return true;
    }
  }
  return false;
}

bool directxExpressionContainsCallLikeEvaluation(
    const HIRExpression &expression) {
  switch (expression.kind) {
  case HIRExpressionKind::Call:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
  case HIRExpressionKind::TextureSample:
    return true;
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::Literal:
  case HIRExpressionKind::Group:
  case HIRExpressionKind::MemberAccess:
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::Constructor:
  case HIRExpressionKind::Unary:
  case HIRExpressionKind::Binary:
  case HIRExpressionKind::Select:
    break;
  }
  for (const HIRExpression &child : expression.children) {
    if (directxExpressionContainsCallLikeEvaluation(child)) {
      return true;
    }
  }
  return false;
}

const HIRExpression *directxNestedArrayWriteBackBinaryOperandCall(
    const HIRExpression &candidateExpression,
    const HIRExpression &otherExpression) {
  if (directxExpressionContainsCallLikeEvaluation(otherExpression)) {
    return nullptr;
  }

  const HIRExpression *candidate =
      directxTransparentExpression(candidateExpression);
  if (candidate->kind != HIRExpressionKind::Call ||
      candidate->type.name == "void" || candidate->type.arraySize.has_value()) {
    return nullptr;
  }
  return candidate;
}

const HIRExpression *directxNestedArrayWriteBackStatementCall(
    const HIRStatement &statement) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
  case HIRStatementKind::Assignment:
    break;
  case HIRStatementKind::Expression:
  case HIRStatementKind::Return:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Block:
  case HIRStatementKind::If:
  case HIRStatementKind::For:
  case HIRStatementKind::Raw:
    return nullptr;
  }

  const HIRExpression *value = directxTransparentExpression(statement.value);
  if (value->kind != HIRExpressionKind::Binary ||
      value->children.size() != 2) {
    return nullptr;
  }
  if (statement.kind == HIRStatementKind::Assignment &&
      directxExpressionContainsCallLikeEvaluation(statement.target)) {
    return nullptr;
  }

  if (const HIRExpression *left =
          directxNestedArrayWriteBackBinaryOperandCall(value->children[0],
                                                      value->children[1])) {
    return left;
  }
  if (value->value == "&&" || value->value == "||") {
    return nullptr;
  }
  return directxNestedArrayWriteBackBinaryOperandCall(value->children[1],
                                                     value->children[0]);
}

const HIRExpression *directxNestedArrayWriteBackRhsSibling(
    const HIRStatement &statement, const HIRExpression &call) {
  const HIRExpression *value = directxTransparentExpression(statement.value);
  if (value->kind != HIRExpressionKind::Binary ||
      value->children.size() != 2) {
    return nullptr;
  }

  const HIRExpression *right = directxTransparentExpression(value->children[1]);
  return right == &call ? &value->children[0] : nullptr;
}

bool directxExpressionCanReevaluateAfterWriteBack(
    const HIRExpression &expression) {
  const HIRExpression *transparent = directxTransparentExpression(expression);
  return transparent->kind == HIRExpressionKind::Literal;
}

std::optional<DirectXArrayWriteBackRewrite> directxArrayWriteBackRewriteForCall(
    const HIRExpression &call, const DirectXEmitContext &context) {
  if (context.module == nullptr || context.stage == nullptr ||
      context.function == nullptr) {
    return std::nullopt;
  }
  const HIRFunction *callee = findDirectXEmitFunction(context, call.value);
  if (callee == nullptr || call.children.size() != callee->parameters.size()) {
    return std::nullopt;
  }

  const std::set<std::string> writtenParameters =
      writtenFunctionParameterArrayNames(*context.module, *callee);
  if (writtenParameters.empty()) {
    return std::nullopt;
  }

  DirectXArrayWriteBackRewrite rewrite;
  rewrite.call = &call;
  for (std::size_t index = 0; index < callee->parameters.size(); ++index) {
    const HIRParameter &parameter = callee->parameters[index];
    if (writtenParameters.count(parameter.name) == 0 ||
        index >= call.children.size() ||
        directxFunctionParameterArrayWriteArgumentAliases(
            *context.module, *callee, call, index) ||
        !directxStorageBufferFieldArrayWriteBackArgument(
            *context.module, *context.function, call.children[index],
            context.stage)) {
      continue;
    }

    DirectXArrayWriteBackArgument argument;
    argument.argumentIndex = index;
    argument.type = parameter.type;
    argument.argument = &call.children[index];
    argument.temporaryName =
        directxArrayWriteBackTemporaryName(call, parameter, context);
    rewrite.argumentOverrides.emplace_back(argument.argumentIndex,
                                           argument.temporaryName);
    rewrite.arguments.push_back(std::move(argument));
  }

  if (rewrite.arguments.empty()) {
    return std::nullopt;
  }
  return rewrite;
}

std::optional<DirectXArrayWriteBackRewrite> directxArrayWriteBackRewrite(
    const HIRStatement &statement, const DirectXEmitContext &context) {
  if (const HIRExpression *call = directxStatementDirectCallValue(statement)) {
    return directxArrayWriteBackRewriteForCall(*call, context);
  }

  const HIRExpression *nestedCall =
      directxNestedArrayWriteBackStatementCall(statement);
  if (nestedCall == nullptr) {
    return std::nullopt;
  }
  std::optional<DirectXArrayWriteBackRewrite> rewrite =
      directxArrayWriteBackRewriteForCall(*nestedCall, context);
  if (rewrite.has_value()) {
    rewrite->materializeNestedCallResult = true;
  }
  return rewrite;
}

std::vector<std::pair<std::size_t, std::string>>
directxArrayWriteBackArgumentOverrides(
    const DirectXArrayWriteBackRewrite &rewrite) {
  std::vector<std::pair<std::size_t, std::string>> overrides =
      rewrite.argumentOverrides;
  std::sort(overrides.begin(), overrides.end(),
            [](const auto &left, const auto &right) {
              return left.first < right.first ||
                     (left.first == right.first && left.second < right.second);
            });
  overrides.erase(std::unique(overrides.begin(), overrides.end()),
                  overrides.end());
  return overrides;
}

void emitDirectXArrayElementCopyLoop(std::ostringstream &out,
                                     std::string_view destination,
                                     std::string_view source,
                                     const HIRType &type,
                                     std::size_t indentation,
                                     std::string_view indexName) {
  if (!type.arraySize.has_value()) {
    return;
  }
  const std::vector<std::string_view> dimensions =
      directxArrayDimensions(*type.arraySize);
  if (dimensions.empty()) {
    return;
  }
  std::vector<std::string> indices;
  indices.reserve(dimensions.size());
  auto emitLoop = [&](auto &self, std::size_t depth,
                      std::size_t currentIndentation) -> void {
    const std::string loopIndex =
        dimensions.size() == 1
            ? std::string(indexName)
            : std::string(indexName) + std::to_string(depth);
    const std::string spaces(currentIndentation, ' ');
    out << spaces << "for (int " << loopIndex << " = 0; " << loopIndex
        << " < " << dimensions[depth] << "; ++" << loopIndex << ") {\n";
    indices.push_back(loopIndex);
    if (depth + 1 == dimensions.size()) {
      const std::string innerSpaces(currentIndentation + 2, ' ');
      out << innerSpaces << destination;
      for (const std::string &index : indices) {
        out << "[" << index << "]";
      }
      out << " = " << source;
      for (const std::string &index : indices) {
        out << "[" << index << "]";
      }
      out << ";\n";
    } else {
      self(self, depth + 1, currentIndentation + 2);
    }
    indices.pop_back();
    out << spaces << "}\n";
  };
  emitLoop(emitLoop, 0, indentation);
}

void emitDirectXArrayWriteBackCopiesBefore(
    std::ostringstream &out, const DirectXArrayWriteBackRewrite &rewrite,
    std::size_t indentation, const DirectXEmitContext &context) {
  const std::string spaces(indentation, ' ');
  for (const DirectXArrayWriteBackArgument &argument : rewrite.arguments) {
    out << spaces << hlslDeclarator(context.module, argument.type,
                                    argument.temporaryName)
        << ";\n";
    const std::string source = emitExpression(*argument.argument, context);
    emitDirectXArrayElementCopyLoop(out, argument.temporaryName, source,
                                    argument.type, indentation,
                                    argument.temporaryName + "_i");
  }
}

void emitDirectXArrayWriteBackCopiesAfter(
    std::ostringstream &out, const DirectXArrayWriteBackRewrite &rewrite,
    std::size_t indentation, const DirectXEmitContext &context) {
  for (const DirectXArrayWriteBackArgument &argument : rewrite.arguments) {
    const std::string destination = emitExpression(*argument.argument, context);
    emitDirectXArrayElementCopyLoop(out, destination, argument.temporaryName,
                                    argument.type, indentation,
                                    argument.temporaryName + "_i");
  }
}

std::string emitDirectXExpressionWithReplacements(
    const HIRExpression &expression,
    const std::vector<std::pair<const HIRExpression *, std::string>>
        &replacements,
    const DirectXEmitContext &context) {
  for (const auto &[node, replacement] : replacements) {
    if (&expression == node) {
      return replacement;
    }
  }
  bool containsReplacement = false;
  for (const auto &[node, replacement] : replacements) {
    (void)replacement;
    if (directxExpressionContainsNode(expression, *node)) {
      containsReplacement = true;
      break;
    }
  }
  if (!containsReplacement) {
    return emitExpression(expression, context);
  }

  switch (expression.kind) {
  case HIRExpressionKind::Group:
    return expression.children.empty()
               ? "()"
               : "(" + emitDirectXExpressionWithReplacements(
                           expression.children.front(), replacements, context) +
                     ")";
  case HIRExpressionKind::Binary:
    if (expression.children.size() != 2) {
      return "/* unsupported */";
    }
    return emitDirectXExpressionWithReplacements(
               expression.children[0], replacements, context) +
           " " + expression.value + " " +
           emitDirectXExpressionWithReplacements(
               expression.children[1], replacements, context);
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::Literal:
  case HIRExpressionKind::MemberAccess:
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::Constructor:
  case HIRExpressionKind::Unary:
  case HIRExpressionKind::Call:
  case HIRExpressionKind::Select:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
  case HIRExpressionKind::TextureSample:
    break;
  }
  return "/* unsupported */";
}

void emitDirectXNestedExpressionWithArrayWriteBack(
    std::ostringstream &out, const HIRStatement &statement,
    std::size_t indentation, const DirectXEmitContext &context,
    const DirectXArrayWriteBackRewrite &rewrite) {
  const std::string spaces(indentation, ' ');
  const std::vector<std::pair<std::size_t, std::string>> overrides =
      directxArrayWriteBackArgumentOverrides(rewrite);
  const HIRExpression *rhsSibling =
      directxNestedArrayWriteBackRhsSibling(statement, *rewrite.call);
  if (rhsSibling != nullptr &&
      directxExpressionCanReevaluateAfterWriteBack(*rhsSibling)) {
    rhsSibling = nullptr;
  }
  std::string rhsSiblingName;
  if (rhsSibling != nullptr) {
    rhsSiblingName = "crossgl_param_array_writeback_" +
                     std::to_string(nextDirectXTemporaryIndex(context)) +
                     "_lhs";
    out << spaces << hlslDeclarator(context.module, rhsSibling->type,
                                    rhsSiblingName)
        << " = " << emitExpression(*rhsSibling, context) << ";\n";
  }
  const std::string resultName =
      "crossgl_param_array_writeback_" +
      std::to_string(nextDirectXTemporaryIndex(context)) + "_result";

  emitDirectXArrayWriteBackCopiesBefore(out, rewrite, indentation, context);
  out << spaces << hlslDeclarator(context.module, rewrite.call->type,
                                  resultName)
      << " = " << emitCallWithArgumentOverrides(*rewrite.call, context,
                                                overrides)
      << ";\n";
  emitDirectXArrayWriteBackCopiesAfter(out, rewrite, indentation, context);

  std::vector<std::pair<const HIRExpression *, std::string>> replacements = {
      {rewrite.call, resultName}};
  if (rhsSibling != nullptr) {
    replacements.emplace_back(rhsSibling, rhsSiblingName);
  }
  const std::string value =
      emitDirectXExpressionWithReplacements(statement.value, replacements,
                                            context);
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    out << spaces << hlslDeclarator(context.module, statement.declaredType,
                                    statement.name)
        << " = " << value << ";\n";
    return;
  case HIRStatementKind::Assignment:
    out << spaces << emitExpression(statement.target, context) << " = "
        << value << ";\n";
    return;
  case HIRStatementKind::Expression:
  case HIRStatementKind::Return:
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Block:
  case HIRStatementKind::If:
  case HIRStatementKind::For:
  case HIRStatementKind::Raw:
    break;
  }
}

void emitDirectXStatementWithArrayWriteBack(
    std::ostringstream &out, const HIRStatement &statement,
    std::size_t indentation, const DirectXEmitContext &context,
    const DirectXArrayWriteBackRewrite &rewrite) {
  if (rewrite.materializeNestedCallResult) {
    emitDirectXNestedExpressionWithArrayWriteBack(out, statement, indentation,
                                                 context, rewrite);
    return;
  }

  const std::string spaces(indentation, ' ');
  const std::vector<std::pair<std::size_t, std::string>> overrides =
      directxArrayWriteBackArgumentOverrides(rewrite);
  emitDirectXArrayWriteBackCopiesBefore(out, rewrite, indentation, context);
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    out << spaces
        << hlslDeclarator(context.module, statement.declaredType,
                          statement.name)
        << " = " << emitCallWithArgumentOverrides(*rewrite.call, context,
                                                  overrides)
        << ";\n";
    break;
  case HIRStatementKind::Assignment: {
    const std::string resultName =
        "crossgl_param_array_writeback_" +
        std::to_string(nextDirectXTemporaryIndex(context)) + "_result";
    out << spaces << hlslDeclarator(context.module, statement.value.type,
                                    resultName)
        << " = " << emitCallWithArgumentOverrides(*rewrite.call, context,
                                                  overrides)
        << ";\n";
    emitDirectXArrayWriteBackCopiesAfter(out, rewrite, indentation, context);
    out << spaces << emitExpression(statement.target, context) << " = "
        << resultName << ";\n";
    return;
  }
  case HIRStatementKind::Expression:
    out << spaces << emitCallWithArgumentOverrides(*rewrite.call, context,
                                                   overrides)
        << ";\n";
    break;
  case HIRStatementKind::Return: {
    if (statement.value.type.name == "void" &&
        !statement.value.type.arraySize.has_value()) {
      out << spaces << emitCallWithArgumentOverrides(*rewrite.call, context,
                                                     overrides)
          << ";\n";
      emitDirectXArrayWriteBackCopiesAfter(out, rewrite, indentation, context);
      out << spaces << "return;\n";
      return;
    }
    const std::string resultName =
        "crossgl_param_array_writeback_" +
        std::to_string(nextDirectXTemporaryIndex(context)) + "_return";
    out << spaces << hlslDeclarator(context.module, statement.value.type,
                                    resultName)
        << " = " << emitCallWithArgumentOverrides(*rewrite.call, context,
                                                  overrides)
        << ";\n";
    emitDirectXArrayWriteBackCopiesAfter(out, rewrite, indentation, context);
    out << spaces << "return " << resultName << ";\n";
    return;
  }
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Block:
  case HIRStatementKind::If:
  case HIRStatementKind::For:
  case HIRStatementKind::Raw:
    break;
  }
  emitDirectXArrayWriteBackCopiesAfter(out, rewrite, indentation, context);
}

void emitStatement(std::ostringstream &out, const HIRStatement &statement,
                   std::size_t indentation,
                   const DirectXEmitContext &context = {}) {
  const std::string spaces(indentation, ' ');
  if (const std::optional<DirectXArrayWriteBackRewrite> rewrite =
          directxArrayWriteBackRewrite(statement, context)) {
    emitDirectXStatementWithArrayWriteBack(out, statement, indentation, context,
                                           *rewrite);
    return;
  }
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    out << spaces
        << hlslDeclarator(context.module, statement.declaredType,
                          statement.name);
    if (statement.value.kind != HIRExpressionKind::Empty) {
      if (isDirectXInterlockedAtomicCall(statement.value)) {
        out << ";\n"
            << spaces
            << emitInterlockedAtomicCaptureStatement(statement.value,
                                                     statement.name, context)
            << ";\n";
        return;
      }
      out << " = " << emitExpression(statement.value, context);
    }
    out << ";\n";
    return;
  case HIRStatementKind::Assignment:
    if (isDirectXInterlockedAtomicCall(statement.value)) {
      out << spaces
          << emitInterlockedAtomicCaptureStatement(
                 statement.value, emitExpression(statement.target, context),
                 context)
          << ";\n";
      return;
    }
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
    if (isDirectXInterlockedAtomicCall(statement.value)) {
      emitInterlockedAtomicStatement(out, statement.value, indentation,
                                     context);
      return;
    }
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

std::optional<std::string> samplerBaseName(const HIRExpression &sampler) {
  const HIRExpression *current = &sampler;
  while ((current->kind == HIRExpressionKind::Group ||
          current->kind == HIRExpressionKind::IndexAccess ||
          current->kind == HIRExpressionKind::NonUniform) &&
         !current->children.empty()) {
    current = &current->children.front();
  }
  if (current->kind == HIRExpressionKind::Identifier) {
    return current->value;
  }
  return std::nullopt;
}

void recordSamplerUsage(const HIRExpression &expression,
                        std::set<std::string> &ordinarySamplers,
                        std::set<std::string> &comparisonSamplers) {
  if ((expression.kind == HIRExpressionKind::TextureSample ||
       expression.kind == HIRExpressionKind::TextureCompare ||
       expression.kind == HIRExpressionKind::TextureCompareLodManual) &&
      expression.children.size() >= 2) {
    const std::optional<std::string> samplerName =
        samplerBaseName(expression.children[1]);
    if (samplerName.has_value() &&
        expression.kind == HIRExpressionKind::TextureCompare) {
      comparisonSamplers.insert(*samplerName);
    } else if (samplerName.has_value()) {
      ordinarySamplers.insert(*samplerName);
    }
  }
}

void collectSamplerUsage(const HIRFunction &function,
                         std::set<std::string> &ordinarySamplers,
                         std::set<std::string> &comparisonSamplers) {
  auto visitor = [&](const HIRExpression &expression) {
    recordSamplerUsage(expression, ordinarySamplers, comparisonSamplers);
  };
  visitFunctionExpressions(function, visitor);
}

std::set<std::string> comparisonSamplerNames(const HIRFunction &function) {
  std::set<std::string> ordinarySamplers;
  std::set<std::string> comparisonSamplers;
  collectSamplerUsage(function, ordinarySamplers, comparisonSamplers);
  return comparisonSamplers;
}

std::set<std::string> comparisonSamplerNames(const HIRModule &module) {
  const HIRStage *stage = singleComputeStage(module);
  if (stage == nullptr) {
    return {};
  }
  std::set<std::string> comparisonSamplers;
  for (const HIRFunction &function : module.functions) {
    const std::set<std::string> functionComparisonSamplers =
        comparisonSamplerNames(function);
    comparisonSamplers.insert(functionComparisonSamplers.begin(),
                              functionComparisonSamplers.end());
  }
  for (const HIRFunction &function : stage->functions) {
    const std::set<std::string> functionComparisonSamplers =
        comparisonSamplerNames(function);
    comparisonSamplers.insert(functionComparisonSamplers.begin(),
                              functionComparisonSamplers.end());
  }
  return comparisonSamplers;
}

std::set<std::string> mixedSamplerStateUsageNames(const HIRFunction &function) {
  std::set<std::string> ordinarySamplers;
  std::set<std::string> comparisonSamplers;
  std::set<std::string> mixedSamplers;
  collectSamplerUsage(function, ordinarySamplers, comparisonSamplers);
  for (const std::string &samplerName : comparisonSamplers) {
    if (ordinarySamplers.count(samplerName) != 0) {
      mixedSamplers.insert(samplerName);
    }
  }
  return mixedSamplers;
}

std::set<std::string> mixedSamplerStateUsageNames(const HIRModule &module) {
  const HIRStage *stage = singleComputeStage(module);
  if (stage == nullptr) {
    return {};
  }
  std::set<std::string> mixedSamplers;
  for (const HIRFunction &function : module.functions) {
    const std::set<std::string> functionMixedSamplers =
        mixedSamplerStateUsageNames(function);
    mixedSamplers.insert(functionMixedSamplers.begin(),
                         functionMixedSamplers.end());
  }
  for (const HIRFunction &function : stage->functions) {
    const std::set<std::string> functionMixedSamplers =
        mixedSamplerStateUsageNames(function);
    mixedSamplers.insert(functionMixedSamplers.begin(),
                         functionMixedSamplers.end());
  }
  return mixedSamplers;
}

const HIRResource *stageResourceByName(const HIRStage &stage,
                                       std::string_view name) {
  for (const HIRResource &resource : stage.resources) {
    if (resource.name == name) {
      return &resource;
    }
  }
  return nullptr;
}

std::set<std::string>
unsupportedMixedSamplerStateUsageLabels(const HIRModule &module) {
  const HIRStage *stage = singleComputeStage(module);
  if (stage == nullptr) {
    return {};
  }
  const std::set<std::string> mixedSamplers =
      mixedSamplerStateUsageNames(module);
  std::set<std::string> unsupported;
  for (const std::string &samplerName : mixedSamplers) {
    const HIRResource *resource = stageResourceByName(*stage, samplerName);
    if (resource == nullptr || resource->kind != HIRResourceKind::Sampler ||
        !supportedResourceArraySize(resource->type)) {
      unsupported.insert(samplerName);
    }
  }
  return unsupported;
}

bool mixedSamplerStateUsageSupported(const HIRModule &module) {
  return unsupportedMixedSamplerStateUsageLabels(module).empty();
}

bool isExplicitLodTextureCompare(const HIRExpression &expression) {
  if (expression.kind == HIRExpressionKind::TextureCompare &&
      expression.value == "textureCompareLod") {
    return true;
  }
  return false;
}

bool usesExplicitLodTextureCompare(const HIRModule &module) {
  return moduleExpressionsContain(module, isExplicitLodTextureCompare, false);
}

std::string directxShaderModel(const HIRModule &module) {
  return usesExplicitLodTextureCompare(module) ? "6_7" : "6_0";
}

std::string directxProfilePrefix(std::string_view stage) {
  if (stage == "compute") {
    return "cs";
  }
  if (stage == "vertex") {
    return "vs";
  }
  if (stage == "fragment") {
    return "ps";
  }
  return std::string(stage);
}

std::string directxShaderProfile(const HIRModule &module,
                                 const HIRStage &stage) {
  return directxProfilePrefix(stage.stage) + "_" + directxShaderModel(module);
}

std::string directxShaderProfileSummary(const HIRModule &module) {
  std::ostringstream out;
  bool first = true;
  for (const HIRStage &stage : module.stages) {
    if (!first) {
      out << ", ";
    }
    first = false;
    out << stage.stage << "=" << directxShaderProfile(module, stage);
  }
  return out.str();
}

bool expressionIsManualTextureCompare(const HIRExpression &expression) {
  return textureCompareManualOperands(expression).has_value();
}

bool moduleUsesManualTextureCompare(const HIRModule &module) {
  return moduleExpressionsContain(module, expressionIsManualTextureCompare,
                                  true);
}

bool constantsSupported(const HIRModule &module) {
  return constantsSupportedByPolicy(module, constantSupported);
}

bool directxStorageImageResourceUsesAtomic(const HIRModule &module,
                                           const HIRResource &resource) {
  bool usesAtomic = false;
  auto visitor = [&](const HIRExpression &expression) {
    if (usesAtomic || !isDirectXStorageImageAtomicCall(expression)) {
      return;
    }
    const HIRExpression *root =
        rootIdentifierExpression(expression.children[0]);
    usesAtomic = root != nullptr && root->value == resource.name;
  };
  visitModuleExpressions(module, visitor, true);
  return usesAtomic;
}

std::string hlslStorageImageType(const HIRModule &module,
                                 const HIRResource &resource) {
  return hlslStorageImageType(
      resource.type, directxStorageImageResourceUsesAtomic(module, resource));
}

bool resourceSupported(const HIRModule &module, const HIRResource &resource) {
  if (resource.kind == HIRResourceKind::Shared) {
    return supportedResourceArraySize(resource.type) &&
           !hlslSharedResourceElementType(resource.type).empty();
  }
  if (resource.kind == HIRResourceKind::StorageImage) {
    return isSupportedStorageImageResource(resource);
  }
  if (resource.kind == HIRResourceKind::Uniform) {
    return isSupportedUniformBufferResource(module, resource);
  }
  if (!directxResourceArrayShapeSupported(module, resource)) {
    return false;
  }
  if (resource.kind == HIRResourceKind::Buffer) {
    return isSupportedStorageBufferElementType(
        module, bufferElementType(resource.type));
  }
  if (resource.kind == HIRResourceKind::Texture) {
    return isSupportedTextureResource(resource);
  }
  if (resource.kind == HIRResourceKind::Sampler) {
    return isSupportedSamplerResource(resource);
  }
  return false;
}

bool resourcesSupported(const HIRModule &module, const HIRStage &stage) {
  for (const HIRResource &resource : stage.resources) {
    if (!resourceSupported(module, resource)) {
      return false;
    }
  }
  return true;
}

bool directxGraphicsResourceSupported(const HIRModule &module,
                                      const HIRResource &resource) {
  if (resource.kind == HIRResourceKind::Uniform) {
    return isSupportedUniformBufferResource(module, resource);
  }
  if (resource.kind == HIRResourceKind::Buffer) {
    return !resource.type.arraySize.has_value() &&
           isSupportedStorageBufferElementType(
               module, bufferElementType(resource.type));
  }
  if (resource.kind == HIRResourceKind::Texture) {
    return supportedResourceArraySize(resource.type) &&
           directxResourceArrayShapeSupported(module, resource) &&
           isSupportedTextureResource(resource);
  }
  if (resource.kind == HIRResourceKind::Sampler) {
    return supportedResourceArraySize(resource.type) &&
           directxResourceArrayShapeSupported(module, resource) &&
           isSupportedSamplerResource(resource);
  }
  return false;
}

std::string directxGraphicsResourceTypeLabel(const HIRResource &resource) {
  std::string type = resource.type.name;
  if (resource.type.arraySize.has_value()) {
    type += "[" + *resource.type.arraySize + "]";
  }
  return type;
}

std::string directxGraphicsResourceDiagnosticLabel(std::string_view stage,
                                                   const HIRResource &resource) {
  return "stage '" + std::string(stage) + "' resource '" + resource.name +
         "' (kind " + resourceKindLabel(resource.kind) + ", type " +
         directxGraphicsResourceTypeLabel(resource) + ", set " +
         std::to_string(resource.set) + ", binding " +
         std::to_string(resource.binding) + ")";
}

std::string
directxGraphicsUnsupportedResourceReason(const HIRModule &module,
                                         const HIRResource &resource) {
  if (resource.kind != HIRResourceKind::Uniform &&
      resource.kind != HIRResourceKind::Buffer &&
      resource.kind != HIRResourceKind::Texture &&
      resource.kind != HIRResourceKind::Sampler) {
    return "unsupported graphics-stage resource kind '" +
           resourceKindLabel(resource.kind) + "'";
  }
  if (resource.kind == HIRResourceKind::Buffer) {
    if (resource.type.arraySize.has_value()) {
      if (resource.type.arraySize->empty()) {
        return "runtime storage-buffer descriptor arrays are not supported in "
               "DirectX graphics source packages";
      }
      return "storage-buffer descriptor arrays are not supported in DirectX "
             "graphics source packages";
    }
    const HIRType elementType = bufferElementType(resource.type);
    if (!isSupportedStorageBufferElementType(module, elementType)) {
      return "unsupported storage-buffer element type '" +
             elementType.name + "'";
    }
    return "unsupported storage-buffer resource";
  }
  if (!supportedResourceArraySize(resource.type)) {
    return "unsupported descriptor array size";
  }
  if (resource.kind == HIRResourceKind::Uniform) {
    if (hlslUniformBufferElementType(module, resource.type).empty()) {
      return "unsupported uniform-buffer element type '" +
             directxGraphicsResourceTypeLabel(resource) + "'";
    }
    return "unsupported uniform-buffer resource";
  }
  if (!directxResourceArrayShapeSupported(module, resource)) {
    return "unsupported descriptor array shape";
  }
  if (resource.kind == HIRResourceKind::Texture) {
    if (hlslTextureType(resource.type).empty()) {
      return "unsupported texture type '" +
             directxGraphicsResourceTypeLabel(resource) + "'";
    }
    return "unsupported texture resource";
  }
  if (resource.type.name != "sampler" &&
      resource.type.name != "comparison_sampler") {
    return "unsupported sampler type '" +
           directxGraphicsResourceTypeLabel(resource) + "'";
  }
  return "unsupported sampler resource";
}

struct DirectXGraphicsResourceRef {
  std::string_view stage;
  const HIRResource *resource = nullptr;
};

std::vector<DirectXGraphicsResourceRef>
directxGraphicsStageResourceRefs(const HIRStage &vertex,
                                 const HIRStage &fragment) {
  std::vector<DirectXGraphicsResourceRef> resources;
  for (const HIRResource &resource : vertex.resources) {
    resources.push_back(DirectXGraphicsResourceRef{vertex.stage, &resource});
  }
  for (const HIRResource &resource : fragment.resources) {
    resources.push_back(DirectXGraphicsResourceRef{fragment.stage, &resource});
  }
  return resources;
}

bool directxSameGraphicsResource(const HIRResource &lhs,
                                 const HIRResource &rhs) {
  return lhs.kind == rhs.kind && typeEquals(lhs.type, rhs.type) &&
         lhs.name == rhs.name && lhs.set == rhs.set &&
         lhs.binding == rhs.binding &&
         lhs.storageImageAccess == rhs.storageImageAccess &&
         lhs.storageImageFormat == rhs.storageImageFormat;
}

std::vector<const HIRResource *>
directxGraphicsStageResources(const HIRStage &vertex,
                              const HIRStage &fragment) {
  std::vector<const HIRResource *> resources;
  for (const DirectXGraphicsResourceRef &resource :
       directxGraphicsStageResourceRefs(vertex, fragment)) {
    resources.push_back(resource.resource);
  }
  return resources;
}

std::set<std::string>
directxGraphicsResourceConflictLabels(const HIRStage &vertex,
                                      const HIRStage &fragment) {
  std::map<std::string, DirectXGraphicsResourceRef> resourcesByName;
  std::map<std::string, DirectXGraphicsResourceRef> resourcesByRegister;
  std::set<std::string> conflicts;
  for (const DirectXGraphicsResourceRef &resourceRef :
       directxGraphicsStageResourceRefs(vertex, fragment)) {
    const HIRResource *resource = resourceRef.resource;
    auto [nameIt, insertedName] =
        resourcesByName.emplace(resource->name, resourceRef);
    if (!insertedName &&
        !directxSameGraphicsResource(*nameIt->second.resource, *resource)) {
      conflicts.insert(
          "name conflict for resource '" + resource->name + "': " +
          directxGraphicsResourceDiagnosticLabel(nameIt->second.stage,
                                                *nameIt->second.resource) +
          " vs " +
          directxGraphicsResourceDiagnosticLabel(resourceRef.stage, *resource));
    }

    const std::string registerClass = directxResourceRegisterClass(*resource);
    if (registerClass.empty()) {
      continue;
    }
    const std::string registerKey = registerClass + ":" +
                                    std::to_string(resource->set) + ":" +
                                    std::to_string(resource->binding);
    auto [registerIt, insertedRegister] =
        resourcesByRegister.emplace(registerKey, resourceRef);
    if (!insertedRegister &&
        !directxSameGraphicsResource(*registerIt->second.resource, *resource)) {
      conflicts.insert(
          "register conflict for register(" + registerClass +
          std::to_string(resource->binding) + ", space" +
          std::to_string(resource->set) + "): " +
          directxGraphicsResourceDiagnosticLabel(registerIt->second.stage,
                                                *registerIt->second.resource) +
          " vs " +
          directxGraphicsResourceDiagnosticLabel(resourceRef.stage, *resource));
    }
  }
  return conflicts;
}

bool directxGraphicsResourcesCompatible(const HIRStage &vertex,
                                        const HIRStage &fragment) {
  if (!directxGraphicsResourceConflictLabels(vertex, fragment).empty()) {
    return false;
  }
  for (const DirectXGraphicsResourceRef &resourceRef :
       directxGraphicsStageResourceRefs(vertex, fragment)) {
    if (directxResourceRegisterClass(*resourceRef.resource).empty()) {
      return false;
    }
  }
  return true;
}

std::set<std::string>
directxUnsupportedGraphicsResourceLabels(const HIRModule &module) {
  const HIRStage *vertex = nullptr;
  const HIRStage *fragment = nullptr;
  if (!directxGraphicsStagePair(module, vertex, fragment)) {
    return {};
  }
  std::set<std::string> unsupportedResources;
  for (const DirectXGraphicsResourceRef &resourceRef :
       directxGraphicsStageResourceRefs(*vertex, *fragment)) {
    const HIRResource &resource = *resourceRef.resource;
    if (!directxGraphicsResourceSupported(module, resource)) {
      unsupportedResources.insert(directxGraphicsResourceDiagnosticLabel(
                                      resourceRef.stage, resource) +
                                  ": " +
                                  directxGraphicsUnsupportedResourceReason(
                                      module, resource));
    }
  }
  return unsupportedResources;
}

std::set<std::string>
directxGraphicsResourceConflictLabels(const HIRModule &module) {
  const HIRStage *vertex = nullptr;
  const HIRStage *fragment = nullptr;
  if (!directxGraphicsStagePair(module, vertex, fragment)) {
    return {};
  }
  return directxGraphicsResourceConflictLabels(*vertex, *fragment);
}

bool directxGraphicsResourcesSupported(const HIRModule &module,
                                       const HIRStage &vertex,
                                       const HIRStage &fragment) {
  if (!directxGraphicsResourcesCompatible(vertex, fragment)) {
    return false;
  }
  for (const HIRResource *resource :
       directxGraphicsStageResources(vertex, fragment)) {
    if (!directxGraphicsResourceSupported(module, *resource)) {
      return false;
    }
  }
  return true;
}

struct DirectXResourceDeclarationMetadata {
  std::string hlslType;
  std::string bindingClass;
  std::string descriptorType;
  std::string registerClass;
  std::size_t registerIndex = 0;
  std::size_t space = 0;
  bool hasRegister = false;
  const TargetLegalizationResourceBindingRecord *record = nullptr;
};

bool directxResourceHasRegisterBinding(HIRResourceKind kind) {
  return kind != HIRResourceKind::Shared && kind != HIRResourceKind::Value;
}

std::string
directxRegisterClassForBindingRecord(std::string_view bindingClass,
                                      std::string_view descriptorType) {
  if (bindingClass == "constant-buffer" && descriptorType == "CBV") {
    return "b";
  }
  if (bindingClass == "uav" && descriptorType == "UAV") {
    return "u";
  }
  if (bindingClass == "srv" && descriptorType == "SRV") {
    return "t";
  }
  if (bindingClass == "sampler" && descriptorType == "Sampler") {
    return "s";
  }
  return "";
}

DirectXResourceDeclarationMetadata
fallbackDirectXResourceDeclarationMetadata(const HIRModule &module,
                                           const HIRResource &resource) {
  DirectXResourceDeclarationMetadata metadata;
  metadata.hlslType = directxResourceHLSLType(module, resource).value_or("");
  metadata.bindingClass = directxResourceBindingClass(resource.kind);

  if (directxResourceHasRegisterBinding(resource.kind)) {
    metadata.descriptorType = directxResourceDescriptorType(resource.kind);
    metadata.registerClass = directxResourceRegisterClass(resource);
    metadata.registerIndex = directxResourceRegisterIndex(resource);
    metadata.space = resource.set;
    metadata.hasRegister = !metadata.registerClass.empty();
  }
  return metadata;
}

bool directxResourceBindingRecordMatches(
    const TargetLegalizationResourceBindingRecord &record,
    const HIRResource &resource, std::string_view stageName = {}) {
  if (record.target != TargetKind::DirectX || record.name != resource.name ||
      record.kind != resourceKindName(resource.kind) ||
      record.sourceType != formatType(resource.type)) {
    return false;
  }
  if (!stageName.empty() && record.stage != stageName) {
    return false;
  }
  return true;
}

std::vector<const TargetLegalizationResourceBindingRecord *>
directxResourceBindingRecordsForResource(
    const TargetLegalizationResourceBindingFacts *resourceBindings,
    const HIRResource &resource, std::string_view stageName = {}) {
  std::vector<const TargetLegalizationResourceBindingRecord *> records;
  if (resourceBindings == nullptr ||
      resourceBindings->target != TargetKind::DirectX) {
    return records;
  }
  for (const TargetLegalizationResourceBindingRecord &record :
       resourceBindings->records) {
    if (directxResourceBindingRecordMatches(record, resource, stageName)) {
      records.push_back(&record);
    }
  }
  return records;
}

DirectXResourceDeclarationMetadata directxResourceDeclarationMetadataFromRecord(
    const HIRModule &module, const HIRResource &resource,
    const TargetLegalizationResourceBindingRecord &record) {
  DirectXResourceDeclarationMetadata metadata =
      fallbackDirectXResourceDeclarationMetadata(module, resource);
  metadata.record = &record;
  if (!record.bindingClass.empty()) {
    metadata.bindingClass = record.bindingClass;
  }
  if (record.descriptorType.has_value()) {
    metadata.descriptorType = *record.descriptorType;
  }
  if (record.hlslType.has_value()) {
    metadata.hlslType = *record.hlslType;
  }

  if (!directxResourceHasRegisterBinding(resource.kind)) {
    metadata.hasRegister = false;
    metadata.registerClass.clear();
    return metadata;
  }

  const std::string registerClass = directxRegisterClassForBindingRecord(
      metadata.bindingClass, metadata.descriptorType);
  if (!registerClass.empty()) {
    metadata.registerClass = registerClass;
  }
  if (record.argumentIndex.has_value()) {
    metadata.registerIndex = *record.argumentIndex;
  }
  if (record.set.has_value()) {
    metadata.space = *record.set;
  }
  metadata.hasRegister = !metadata.registerClass.empty();
  return metadata;
}

DirectXResourceDeclarationMetadata directxResourceDeclarationMetadata(
    const HIRModule &module, const HIRResource &resource,
    const TargetLegalizationResourceBindingFacts *resourceBindings,
    std::string_view stageName = {}) {
  const std::vector<const TargetLegalizationResourceBindingRecord *> records =
      directxResourceBindingRecordsForResource(resourceBindings, resource,
                                               stageName);
  if (records.empty()) {
    return fallbackDirectXResourceDeclarationMetadata(module, resource);
  }
  return directxResourceDeclarationMetadataFromRecord(module, resource,
                                                     *records.front());
}

std::string
directxRegisterAnnotation(const DirectXResourceDeclarationMetadata &metadata) {
  if (!metadata.hasRegister || metadata.registerClass.empty()) {
    return "";
  }
  return " : register(" + metadata.registerClass +
         std::to_string(metadata.registerIndex) + ", space" +
         std::to_string(metadata.space) + ")";
}

std::string directxDeclarationResourceLabel(std::string_view stageName,
                                            const HIRResource &resource) {
  std::string label = "stage '" + std::string(stageName) + "' resource '" +
                      resource.name + "'";
  label += " (" + resourceKindName(resource.kind) + " " +
           formatType(resource.type);
  if (directxResourceHasRegisterBinding(resource.kind)) {
    label += ", set " + std::to_string(resource.set) + ", binding " +
             std::to_string(resource.binding);
  }
  label += ")";
  return label;
}

void appendDirectXDeclarationRecordMismatch(std::vector<std::string> &mismatches,
                                            std::string_view field,
                                            std::string_view expected,
                                            std::string_view actual) {
  mismatches.push_back(std::string(field) + " expected '" +
                       std::string(expected) + "', got '" +
                       std::string(actual) + "'");
}

void appendDirectXDeclarationRecordMismatch(std::vector<std::string> &mismatches,
                                            std::string_view field,
                                            std::size_t expected,
                                            std::size_t actual) {
  appendDirectXDeclarationRecordMismatch(
      mismatches, field, std::to_string(expected), std::to_string(actual));
}

std::vector<std::string> directxDeclarationRecordMismatches(
    const HIRModule &module, const HIRResource &resource,
    const TargetLegalizationResourceBindingRecord &record) {
  const DirectXResourceDeclarationMetadata expected =
      fallbackDirectXResourceDeclarationMetadata(module, resource);
  std::vector<std::string> mismatches;

  if (record.bindingClass != expected.bindingClass) {
    appendDirectXDeclarationRecordMismatch(mismatches, "bindingClass",
                                           expected.bindingClass,
                                           record.bindingClass);
  }

  if (!expected.hlslType.empty()) {
    if (!record.hlslType.has_value()) {
      appendDirectXDeclarationRecordMismatch(mismatches, "hlslType",
                                             expected.hlslType, "<missing>");
    } else if (*record.hlslType != expected.hlslType) {
      appendDirectXDeclarationRecordMismatch(mismatches, "hlslType",
                                             expected.hlslType, *record.hlslType);
    }
  } else if (record.hlslType.has_value()) {
    appendDirectXDeclarationRecordMismatch(mismatches, "hlslType", "<absent>",
                                           *record.hlslType);
  }

  if (!directxResourceHasRegisterBinding(resource.kind)) {
    if (record.descriptorType.has_value()) {
      appendDirectXDeclarationRecordMismatch(mismatches, "descriptorType",
                                             "<absent>",
                                             *record.descriptorType);
    }
    if (record.argumentIndex.has_value()) {
      appendDirectXDeclarationRecordMismatch(
          mismatches, "argumentIndex", "<absent>",
          std::to_string(*record.argumentIndex));
    }
    return mismatches;
  }

  if (!record.descriptorType.has_value()) {
    appendDirectXDeclarationRecordMismatch(mismatches, "descriptorType",
                                           expected.descriptorType,
                                           "<missing>");
  } else if (*record.descriptorType != expected.descriptorType) {
    appendDirectXDeclarationRecordMismatch(mismatches, "descriptorType",
                                           expected.descriptorType,
                                           *record.descriptorType);
  }

  const std::string recordRegisterClass = directxRegisterClassForBindingRecord(
      record.bindingClass, record.descriptorType.value_or(""));
  if (recordRegisterClass != expected.registerClass) {
    appendDirectXDeclarationRecordMismatch(mismatches, "registerClass",
                                           expected.registerClass,
                                           recordRegisterClass.empty()
                                               ? "<unresolved>"
                                               : recordRegisterClass);
  }

  if (!record.argumentIndex.has_value()) {
    appendDirectXDeclarationRecordMismatch(mismatches, "argumentIndex",
                                           std::to_string(expected.registerIndex),
                                           "<missing>");
  } else if (*record.argumentIndex != expected.registerIndex) {
    appendDirectXDeclarationRecordMismatch(
        mismatches, "argumentIndex", expected.registerIndex,
        *record.argumentIndex);
  }
  if (!record.set.has_value()) {
    appendDirectXDeclarationRecordMismatch(mismatches, "space",
                                           std::to_string(expected.space),
                                           "<missing>");
  } else if (*record.set != expected.space) {
    appendDirectXDeclarationRecordMismatch(mismatches, "space", expected.space,
                                           *record.set);
  }
  if (!record.binding.has_value()) {
    appendDirectXDeclarationRecordMismatch(
        mismatches, "binding", std::to_string(resource.binding), "<missing>");
  } else if (*record.binding != resource.binding) {
    appendDirectXDeclarationRecordMismatch(mismatches, "binding",
                                           resource.binding, *record.binding);
  }
  return mismatches;
}

std::string joinDirectXDeclarationMismatches(
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

bool diagnoseDirectXLegalizedResourceDeclarationMismatches(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts *resourceBindings,
    DiagnosticEngine &diagnostics) {
  if (resourceBindings == nullptr) {
    diagnostics.error(
        "directx.legalized-resource-binding-missing",
        "DirectX source package requires complete legalized registerBinding "
        "records before HLSL register(...) emission; missing binding "
        "record(s): resource-bindings");
    return true;
  }
  if (resourceBindings->target != TargetKind::DirectX ||
      !resourceBindings->complete) {
    diagnostics.error(
        "directx.legalized-resource-binding-missing",
        "DirectX source package requires complete legalized registerBinding "
        "records before HLSL register(...) emission; missing binding "
        "record(s): resource-bindings");
    return true;
  }

  bool failed = false;
  std::set<std::string> matchedEvidenceIds;
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind == HIRResourceKind::Value) {
        continue;
      }
      const std::vector<const TargetLegalizationResourceBindingRecord *> records =
          directxResourceBindingRecordsForResource(resourceBindings, resource,
                                                   stage.stage);
      if (records.empty()) {
        diagnostics.error(
            "directx.legalized-resource-binding-missing",
            "missing DirectX legalized resource-binding record for " +
                directxDeclarationResourceLabel(stage.stage, resource));
        failed = true;
        continue;
      }
      for (const TargetLegalizationResourceBindingRecord *record : records) {
        matchedEvidenceIds.insert(record->evidenceId);
        const std::vector<std::string> mismatches =
            directxDeclarationRecordMismatches(module, resource, *record);
        if (mismatches.empty()) {
          continue;
        }
        diagnostics.error(
            "directx.legalized-resource-binding-mismatch",
            "DirectX HLSL declaration metadata disagrees with legalization "
            "record '" +
                record->evidenceId + "' for " +
                directxDeclarationResourceLabel(stage.stage, resource) + ": " +
                joinDirectXDeclarationMismatches(mismatches));
        failed = true;
      }
    }
  }

  for (const TargetLegalizationResourceBindingRecord &record :
       resourceBindings->records) {
    if (record.target == TargetKind::DirectX &&
        matchedEvidenceIds.count(record.evidenceId) == 0) {
      diagnostics.error(
          "directx.legalized-resource-binding-mismatch",
          "stale DirectX legalized resource-binding record '" +
              record.evidenceId + "' for resource '" + record.name +
              "' has no matching HLSL declaration input");
      failed = true;
    }
  }
  return failed;
}

void emitResourceDeclaration(std::ostringstream &out, const HIRModule &module,
                             const HIRResource &resource,
                             std::string_view stageName,
                             const TargetLegalizationResourceBindingFacts
                                 *resourceBindings,
                             const std::set<std::string> &mixedSamplers) {
  const DirectXResourceDeclarationMetadata metadata =
      directxResourceDeclarationMetadata(module, resource, resourceBindings,
                                         stageName);
  if (resource.kind == HIRResourceKind::Uniform) {
    if (resource.type.arraySize.has_value()) {
      out << metadata.hlslType << " " << resource.name
          << resourceArraySuffix(resource.type)
          << directxRegisterAnnotation(metadata) << ";\n";
      return;
    }
    out << "cbuffer " << resource.name << "_Buffer"
        << directxRegisterAnnotation(metadata) << " {\n";
    out << "  " << hlslUniformBufferDeclarator(module, resource) << ";\n";
    out << "};\n";
    return;
  }
  if (resource.kind == HIRResourceKind::StorageImage) {
    out << metadata.hlslType << " " << resource.name
        << resourceArraySuffix(resource.type)
        << directxRegisterAnnotation(metadata) << ";\n";
    return;
  }
  if (resource.kind == HIRResourceKind::Buffer) {
    out << metadata.hlslType << " " << resource.name
        << resourceArraySuffix(resource.type)
        << directxRegisterAnnotation(metadata) << ";\n";
    return;
  }
  if (resource.kind == HIRResourceKind::Texture) {
    out << metadata.hlslType << " " << resource.name
        << resourceArraySuffix(resource.type)
        << directxRegisterAnnotation(metadata) << ";\n";
    return;
  }
  if (resource.kind == HIRResourceKind::Sampler) {
    if (mixedSamplers.count(resource.name) != 0) {
      const std::string samplerStateType =
          metadata.hlslType.empty() ? "SamplerState" : metadata.hlslType;
      out << samplerStateType << " " << resource.name
          << resourceArraySuffix(resource.type)
          << directxRegisterAnnotation(metadata) << ";\n";
      out << "SamplerComparisonState "
          << comparisonSamplerAliasName(resource.name)
          << resourceArraySuffix(resource.type)
          << directxRegisterAnnotation(metadata) << ";\n";
      return;
    }
    out << metadata.hlslType << " " << resource.name
        << resourceArraySuffix(resource.type)
        << directxRegisterAnnotation(metadata) << ";\n";
    return;
  }
  if (resource.kind == HIRResourceKind::Shared) {
    out << "groupshared " << metadata.hlslType << " " << resource.name
        << resourceArraySuffix(resource.type) << ";\n";
    return;
  }
}

void emitManualCompareHelper(std::ostringstream &out) {
  out << "static const int CGL_COMPARE_NEVER = 0;\n";
  out << "static const int CGL_COMPARE_ALWAYS = 1;\n";
  out << "static const int CGL_COMPARE_LESS = 2;\n";
  out << "static const int CGL_COMPARE_LESS_EQUAL = 3;\n";
  out << "static const int CGL_COMPARE_EQUAL = 4;\n";
  out << "static const int CGL_COMPARE_NOT_EQUAL = 5;\n";
  out << "static const int CGL_COMPARE_GREATER_EQUAL = 6;\n";
  out << "static const int CGL_COMPARE_GREATER = 7;\n\n";
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

bool hasResources(const HIRStage &stage) {
  for (const HIRResource &resource : stage.resources) {
    if (resource.kind != HIRResourceKind::Value) {
      return true;
    }
  }
  return false;
}

std::set<std::string> callableFunctionNames(const HIRModule &module,
                                            const HIRStage &stage) {
  std::set<std::string> names;
  for (const HIRFunction &function : module.functions) {
    names.insert(function.name);
  }
  for (const HIRFunction &function : stage.functions) {
    if (function.name != stage.entryPointName) {
      names.insert(function.name);
    }
  }
  return names;
}

std::vector<const HIRFunction *>
callableFunctionDefinitions(const HIRModule &module, const HIRStage &stage) {
  std::vector<const HIRFunction *> functions;
  for (const HIRFunction &function : module.functions) {
    functions.push_back(&function);
  }
  for (const HIRFunction &function : stage.functions) {
    functions.push_back(&function);
  }
  return functions;
}

const HIRFunction *
findCallableFunction(const std::vector<const HIRFunction *> &functions,
                     std::string_view name) {
  for (const HIRFunction *function : functions) {
    if (function != nullptr && function->name == name) {
      return function;
    }
  }
  return nullptr;
}

HIRFunctionParameterArrayCallFeatureSupport
directxFunctionParameterArrayCallFeatureSupport(
    HIRFunctionParameterArrayCallFeature feature) {
  if (feature ==
          HIRFunctionParameterArrayCallFeature::DirectResourceArrayArguments ||
      feature == HIRFunctionParameterArrayCallFeature::StructElements) {
    return HIRFunctionParameterArrayCallFeatureSupport::Supported;
  }
  return functionParameterArrayCallFeatureSupport(feature);
}

HIRFunctionParameterArrayCallFeatureSupport
directxFunctionParameterArrayCallFeaturesSupport(
    std::span<const HIRFunctionParameterArrayCallFeature> features) {
  for (HIRFunctionParameterArrayCallFeature feature : features) {
    if (directxFunctionParameterArrayCallFeatureSupport(feature) ==
        HIRFunctionParameterArrayCallFeatureSupport::Unsupported) {
      return HIRFunctionParameterArrayCallFeatureSupport::Unsupported;
    }
  }
  return HIRFunctionParameterArrayCallFeatureSupport::Supported;
}

void appendUnsupportedFunctionParameterArrayCallFeatures(
    std::set<std::string> &labels, std::string_view caller,
    std::string_view callee, std::string_view parameter,
    std::span<const HIRFunctionParameterArrayCallFeature> features) {
  for (HIRFunctionParameterArrayCallFeature feature : features) {
    const HIRFunctionParameterArrayCallFeatureSupport support =
        directxFunctionParameterArrayCallFeatureSupport(feature);
    if (support == HIRFunctionParameterArrayCallFeatureSupport::Supported) {
      continue;
    }
    labels.insert("caller '" + std::string(caller) + "' -> callee '" +
                  std::string(callee) + "' parameter '" +
                  std::string(parameter) +
                  "': " + functionParameterArrayCallFeatureName(feature) + "=" +
                  functionParameterArrayCallFeatureSupportName(support));
  }
}

void collectUnsupportedFunctionParameterArrayCallFeatures(
    const HIRModule &module, const HIRFunction &function, const HIRStage *stage,
    const std::vector<const HIRFunction *> &callables,
    std::set<std::string> &labels) {
  auto visitor = [&](const HIRExpression &expression) {
    if (expression.kind != HIRExpressionKind::Call) {
      return;
    }
    const HIRFunction *callee =
        findCallableFunction(callables, expression.value);
    if (callee == nullptr) {
      return;
    }
    const std::size_t argumentCount =
        std::min(expression.children.size(), callee->parameters.size());
    for (std::size_t index = 0; index < argumentCount; ++index) {
      const HIRParameter &parameter = callee->parameters[index];
      if (functionParameterArrayShape(module, parameter.type) !=
          HIRFunctionParameterArrayShape::FixedSize) {
        continue;
      }
      const std::vector<HIRFunctionParameterArrayCallFeature> typeFeatures =
          functionParameterArrayCallTypeFeatures(module, parameter.type);
      appendUnsupportedFunctionParameterArrayCallFeatures(
          labels, function.name, callee->name, parameter.name, typeFeatures);

      const std::vector<HIRFunctionParameterArrayCallFeature> argumentFeatures =
          functionParameterArrayCallArgumentFeatures(
              module, function, expression.children[index], stage);
      appendUnsupportedFunctionParameterArrayCallFeatures(
          labels, function.name, callee->name, parameter.name,
          argumentFeatures);

      const auto hasFeature =
          [](std::span<const HIRFunctionParameterArrayCallFeature> features,
             HIRFunctionParameterArrayCallFeature feature) {
            return std::find(features.begin(), features.end(), feature) !=
                   features.end();
          };
      const std::span<const HIRFunctionParameterArrayCallFeature> typeSpan{
          typeFeatures.data(), typeFeatures.size()};
      const std::span<const HIRFunctionParameterArrayCallFeature> argumentSpan{
          argumentFeatures.data(), argumentFeatures.size()};
      if (hasFeature(typeSpan,
                     HIRFunctionParameterArrayCallFeature::StructElements) &&
          hasFeature(argumentSpan, HIRFunctionParameterArrayCallFeature::
                                       FunctionParameterArguments)) {
        labels.insert("caller '" + function.name + "' -> callee '" +
                      callee->name + "' parameter '" + parameter.name +
                      "': struct-array-forwarding=unsupported");
      }
    }
  };
  visitFunctionExpressions(function, visitor);
}

std::set<std::string>
unsupportedFunctionParameterArrayCallFeatureLabels(const HIRModule &module) {
  const HIRStage *stage = singleComputeStage(module);
  if (stage == nullptr) {
    return {};
  }
  const std::vector<const HIRFunction *> callables =
      callableFunctionDefinitions(module, *stage);
  std::set<std::string> labels;
  for (const HIRFunction &function : module.functions) {
    collectUnsupportedFunctionParameterArrayCallFeatures(
        module, function, nullptr, callables, labels);
  }
  for (const HIRFunction &function : stage->functions) {
    collectUnsupportedFunctionParameterArrayCallFeatures(
        module, function, stage, callables, labels);
  }
  return labels;
}

std::optional<std::size_t>
fixedArrayParameterIndex(const HIRModule &module, const HIRFunction &function,
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

void collectFunctionParameterArrayWritesInStatement(
    const HIRFunction &function, const std::set<std::string> &parameterArrays,
    const HIRStatement &statement, std::set<std::string> &parameterNames) {
  if (statement.kind == HIRStatementKind::Assignment) {
    const HIRExpression *root = rootIdentifierExpression(statement.target);
    if (root != nullptr && parameterArrays.count(root->value) != 0) {
      parameterNames.insert(root->value);
    }
  }

  for (const HIRStatement &child : statement.initializer) {
    collectFunctionParameterArrayWritesInStatement(function, parameterArrays,
                                                   child, parameterNames);
  }
  for (const HIRStatement &child : statement.update) {
    collectFunctionParameterArrayWritesInStatement(function, parameterArrays,
                                                   child, parameterNames);
  }
  for (const HIRStatement &child : statement.body) {
    collectFunctionParameterArrayWritesInStatement(function, parameterArrays,
                                                   child, parameterNames);
  }
  for (const HIRStatement &child : statement.elseBody) {
    collectFunctionParameterArrayWritesInStatement(function, parameterArrays,
                                                   child, parameterNames);
  }
}

std::set<std::string>
writtenFunctionParameterArrayNames(const HIRModule &module,
                                   const HIRFunction &function) {
  std::set<std::string> parameterNames;
  const std::set<std::string> parameterArrays =
      fixedArrayParameterNames(module, function);
  if (parameterArrays.empty()) {
    return parameterNames;
  }
  for (const HIRStatement &statement : function.body) {
    collectFunctionParameterArrayWritesInStatement(function, parameterArrays,
                                                   statement, parameterNames);
  }
  return parameterNames;
}

bool hasFunctionParameterArrayCallFeature(
    std::span<const HIRFunctionParameterArrayCallFeature> features,
    HIRFunctionParameterArrayCallFeature expected) {
  return std::find(features.begin(), features.end(), expected) !=
         features.end();
}

bool directxLocalArrayCopyArgument(const HIRModule &module,
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
  const std::span<const HIRFunctionParameterArrayCallFeature> featureSpan{
      features.data(), features.size()};
  if (directxFunctionParameterArrayCallFeaturesSupport(featureSpan) !=
      HIRFunctionParameterArrayCallFeatureSupport::Supported) {
    return false;
  }
  return hasFunctionParameterArrayCallFeature(
             featureSpan,
             HIRFunctionParameterArrayCallFeature::LocalArrayArguments) &&
         !hasFunctionParameterArrayCallFeature(
             featureSpan,
             HIRFunctionParameterArrayCallFeature::StructElements) &&
         !hasFunctionParameterArrayCallFeature(
             featureSpan, HIRFunctionParameterArrayCallFeature::
                              FunctionParameterArguments) &&
         !hasFunctionParameterArrayCallFeature(
             featureSpan, HIRFunctionParameterArrayCallFeature::
                              StorageBufferFieldArguments) &&
         !hasFunctionParameterArrayCallFeature(
             featureSpan, HIRFunctionParameterArrayCallFeature::
                              NestedStructFieldArguments) &&
         !hasFunctionParameterArrayCallFeature(
             featureSpan, HIRFunctionParameterArrayCallFeature::
                              DirectResourceArrayArguments);
}

bool directxStorageBufferFieldArrayWriteBackArgument(
    const HIRModule &module, const HIRFunction &caller,
    const HIRExpression &argument, const HIRStage *stage) {
  if (functionParameterArrayShape(module, argument.type) !=
          HIRFunctionParameterArrayShape::FixedSize ||
      !argument.type.arraySize.has_value() ||
      directxArrayDimensions(*argument.type.arraySize).size() != 1) {
    return false;
  }

  const std::vector<HIRFunctionParameterArrayCallFeature> features =
      functionParameterArrayCallArgumentFeatures(module, caller, argument,
                                                 stage);
  const std::span<const HIRFunctionParameterArrayCallFeature> featureSpan{
      features.data(), features.size()};
  if (directxFunctionParameterArrayCallFeaturesSupport(featureSpan) !=
      HIRFunctionParameterArrayCallFeatureSupport::Supported) {
    return false;
  }
  return hasFunctionParameterArrayCallFeature(
             featureSpan,
             HIRFunctionParameterArrayCallFeature::
                 StorageBufferFieldArguments) &&
         !hasFunctionParameterArrayCallFeature(
             featureSpan,
             HIRFunctionParameterArrayCallFeature::StructElements) &&
         !hasFunctionParameterArrayCallFeature(
             featureSpan,
             HIRFunctionParameterArrayCallFeature::FixedNestedArrays) &&
         !hasFunctionParameterArrayCallFeature(
             featureSpan,
             HIRFunctionParameterArrayCallFeature::LocalArrayArguments) &&
         !hasFunctionParameterArrayCallFeature(
             featureSpan, HIRFunctionParameterArrayCallFeature::
                              FunctionParameterArguments) &&
         !hasFunctionParameterArrayCallFeature(
             featureSpan, HIRFunctionParameterArrayCallFeature::
                              NestedStructFieldArguments) &&
         !hasFunctionParameterArrayCallFeature(
             featureSpan, HIRFunctionParameterArrayCallFeature::
                              DirectResourceArrayArguments);
}

bool directxFunctionParameterArrayWriteArgumentAliases(
    const HIRModule &module, const HIRFunction &callee,
    const HIRExpression &call, std::size_t parameterIndex) {
  if (call.children.size() <= parameterIndex) {
    return false;
  }
  const HIRExpression *writtenRoot =
      rootIdentifierExpression(call.children[parameterIndex]);
  if (writtenRoot == nullptr) {
    return false;
  }

  for (std::size_t index = 0; index < callee.parameters.size(); ++index) {
    if (index == parameterIndex || call.children.size() <= index ||
        functionParameterArrayShape(module, callee.parameters[index].type) !=
            HIRFunctionParameterArrayShape::FixedSize) {
      continue;
    }
    const HIRExpression *otherRoot =
        rootIdentifierExpression(call.children[index]);
    if (otherRoot != nullptr && otherRoot->value == writtenRoot->value) {
      return true;
    }
  }
  return false;
}

const HIRExpression *directxStatementDirectCallValue(
    const HIRStatement &statement) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
  case HIRStatementKind::Assignment:
  case HIRStatementKind::Expression:
  case HIRStatementKind::Return:
    return statement.value.kind == HIRExpressionKind::Call ? &statement.value
                                                           : nullptr;
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
  case HIRStatementKind::Block:
  case HIRStatementKind::If:
  case HIRStatementKind::For:
  case HIRStatementKind::Raw:
    return nullptr;
  }
  return nullptr;
}

bool directxFunctionParameterArrayWriteCallSupportedInContext(
    const HIRModule &module, const HIRFunction &caller,
    const HIRFunction &callee, const HIRExpression &call,
    std::size_t parameterIndex, const HIRStage *stage,
    bool allowDirectStatementWriteBack) {
  if (call.children.size() <= parameterIndex ||
      directxFunctionParameterArrayWriteArgumentAliases(module, callee, call,
                                                       parameterIndex)) {
    return false;
  }
  if (directxLocalArrayCopyArgument(module, caller,
                                    call.children[parameterIndex], stage)) {
    return true;
  }
  return allowDirectStatementWriteBack &&
         directxStorageBufferFieldArrayWriteBackArgument(
             module, caller, call.children[parameterIndex], stage);
}

bool directxExpressionTreeSupportsFunctionArrayWriteCalls(
    const HIRModule &module, const HIRFunction &caller,
    const HIRFunction &callee, const HIRExpression &expression,
    const HIRExpression *directCall, std::size_t parameterIndex,
    const HIRStage *stage) {
  bool supported = true;
  auto visitor = [&](const HIRExpression &candidate) {
    if (&candidate != directCall && candidate.kind == HIRExpressionKind::Call &&
        candidate.value == callee.name &&
        !directxFunctionParameterArrayWriteCallSupportedInContext(
            module, caller, callee, candidate, parameterIndex, stage, false)) {
      supported = false;
    }
  };
  visitExpressionTree(expression, visitor);
  return supported;
}

bool directxFunctionParameterArrayWriteStatementSupported(
    const HIRModule &module, const HIRFunction &caller,
    const HIRFunction &callee, const HIRStatement &statement,
    std::size_t parameterIndex, const HIRStage *stage,
    bool allowDirectStatementWriteBack) {
  const HIRExpression *supportedWriteBackCall =
      directxStatementDirectCallValue(statement);
  if (supportedWriteBackCall != nullptr &&
      supportedWriteBackCall->value != callee.name) {
    supportedWriteBackCall = nullptr;
  }
  if (supportedWriteBackCall != nullptr) {
    if (!directxFunctionParameterArrayWriteCallSupportedInContext(
            module, caller, callee, *supportedWriteBackCall, parameterIndex,
            stage, allowDirectStatementWriteBack)) {
      return false;
    }
  } else if (allowDirectStatementWriteBack) {
    const HIRExpression *nestedCall =
        directxNestedArrayWriteBackStatementCall(statement);
    if (nestedCall != nullptr && nestedCall->value == callee.name) {
      if (!directxFunctionParameterArrayWriteCallSupportedInContext(
              module, caller, callee, *nestedCall, parameterIndex, stage,
              true)) {
        return false;
      }
      supportedWriteBackCall = nestedCall;
    }
  }
  if (!directxExpressionTreeSupportsFunctionArrayWriteCalls(
          module, caller, callee, statement.target, supportedWriteBackCall,
          parameterIndex, stage) ||
      !directxExpressionTreeSupportsFunctionArrayWriteCalls(
          module, caller, callee, statement.value, supportedWriteBackCall,
          parameterIndex, stage)) {
    return false;
  }

  for (const HIRStatement &child : statement.initializer) {
    if (!directxFunctionParameterArrayWriteStatementSupported(
            module, caller, callee, child, parameterIndex, stage, false)) {
      return false;
    }
  }
  for (const HIRStatement &child : statement.update) {
    if (!directxFunctionParameterArrayWriteStatementSupported(
            module, caller, callee, child, parameterIndex, stage, false)) {
      return false;
    }
  }
  for (const HIRStatement &child : statement.body) {
    if (!directxFunctionParameterArrayWriteStatementSupported(
            module, caller, callee, child, parameterIndex, stage, true)) {
      return false;
    }
  }
  for (const HIRStatement &child : statement.elseBody) {
    if (!directxFunctionParameterArrayWriteStatementSupported(
            module, caller, callee, child, parameterIndex, stage, true)) {
      return false;
    }
  }
  return true;
}

bool functionParameterArrayWriteUsesSupportedArguments(
    const HIRModule &module, const HIRFunction &function,
    std::size_t parameterIndex) {
  const HIRStage *stage = singleComputeStage(module);
  bool supported = true;
  const auto inspectCaller = [&](const HIRFunction &caller,
                                 const HIRStage *callerStage) {
    for (const HIRStatement &statement : caller.body) {
      if (!supported) {
        break;
      }
      if (!directxFunctionParameterArrayWriteStatementSupported(
              module, caller, function, statement, parameterIndex, callerStage,
              true)) {
        supported = false;
      }
    }
  };

  for (const HIRFunction &caller : module.functions) {
    inspectCaller(caller, stage);
  }
  if (stage != nullptr) {
    for (const HIRFunction &caller : stage->functions) {
      inspectCaller(caller, stage);
    }
  }
  return supported;
}

void collectUnsupportedFunctionParameterArrayWrites(
    const HIRModule &module, const HIRFunction &function,
    std::set<std::string> &labels) {
  for (const std::string &parameterName :
       writtenFunctionParameterArrayNames(module, function)) {
    const std::optional<std::size_t> parameterIndex =
        fixedArrayParameterIndex(module, function, parameterName);
    if (!parameterIndex.has_value() ||
        !functionParameterArrayWriteUsesSupportedArguments(module, function,
                                                           *parameterIndex)) {
      labels.insert("function '" + function.name + "' parameter '" +
                    parameterName + "'");
    }
  }
}

std::set<std::string>
unsupportedFunctionParameterArrayWriteLabels(const HIRModule &module) {
  std::set<std::string> labels;
  for (const HIRFunction &function : module.functions) {
    collectUnsupportedFunctionParameterArrayWrites(module, function, labels);
  }
  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &function : stage.functions) {
      collectUnsupportedFunctionParameterArrayWrites(module, function, labels);
    }
  }
  return labels;
}

bool isSupportedFunctionValueType(const HIRModule &module,
                                  const HIRType &type) {
  if (!hlslFunctionParameterResourceType(module, type).empty()) {
    return true;
  }
  if (type.name == "void" || (!type.name.empty() && type.name.back() == '*')) {
    return false;
  }
  if (!type.arraySize.has_value()) {
    return isSupportedValueType(type) ||
           directxStructType(module, type) != nullptr;
  }
  return !type.arraySize->empty() &&
         (!hlslTypeName(stripPointer(type.name)).empty() ||
          findStruct(module, stripPointer(type.name)) != nullptr);
}

bool isSupportedFunctionReturnType(const HIRModule &module,
                                   const HIRType &type) {
  if (type.name == "void" && !type.arraySize.has_value()) {
    return true;
  }
  return !type.arraySize.has_value() &&
         isSupportedFunctionValueType(module, type);
}

bool functionParametersSupported(const HIRModule &module,
                                 const HIRFunction &function) {
  for (const HIRParameter &parameter : function.parameters) {
    if (!isSupportedFunctionValueType(module, parameter.type)) {
      return false;
    }
  }
  return true;
}

bool entryFunctionSupported(const HIRFunction &function,
                            const DirectXTextualSupportContext &context);

bool helperFunctionSupported(const HIRFunction &function,
                             const DirectXTextualSupportContext &context) {
  if (context.module == nullptr ||
      !isSupportedFunctionReturnType(*context.module, function.returnType) ||
      !functionParametersSupported(*context.module, function)) {
    return false;
  }
  return functionBodySupportedByPolicy(
      function, [&](const HIRStatement &statement) {
        return statementSupported(statement, context);
      });
}

bool stageFunctionSupported(const HIRModule &module, const HIRStage &stage,
                            const HIRFunction &function, bool entry,
                            const DirectXTextualSupportContext &context) {
  if (entry) {
    if (stage.stage == "compute") {
      return entryFunctionSupported(function, context);
    }
    if (!directxGraphicsEntrySignatureSupported(module, stage, function)) {
      return false;
    }
  } else if (!isSupportedFunctionReturnType(module, function.returnType) ||
             !functionParametersSupported(module, function)) {
    return false;
  }

  return functionBodySupportedByPolicy(
      function, [&](const HIRStatement &statement) {
        return statementSupported(statement, context);
      });
}

bool stageFunctionsSupported(const HIRModule &module, const HIRStage &stage,
                             const DirectXTextualSupportContext &context) {
  const HIRFunction *entry = entryFunction(stage);
  if (entry == nullptr) {
    return false;
  }
  for (const HIRFunction &function : stage.functions) {
    if (!stageFunctionSupported(module, stage, function, &function == entry,
                                context)) {
      return false;
    }
  }
  return true;
}

bool entryFunctionSupported(const HIRFunction &function,
                            const DirectXTextualSupportContext &context) {
  if (function.returnType.name != "void" || function.returnType.arraySize ||
      !function.parameters.empty()) {
    return false;
  }
  return functionBodySupportedByPolicy(
      function, [&](const HIRStatement &statement) {
        return statementSupported(statement, context);
      });
}

bool functionsSupported(const HIRModule &module, const HIRStage &stage,
                        const HIRFunction &entry,
                        const DirectXTextualSupportContext &context) {
  for (const HIRFunction &function : module.functions) {
    if (!helperFunctionSupported(function, context)) {
      return false;
    }
  }
  for (const HIRFunction &function : stage.functions) {
    const bool isEntry = &function == &entry;
    if (isEntry) {
      if (!entryFunctionSupported(function, context)) {
        return false;
      }
      continue;
    }
    if (!stageFunctionSupported(module, stage, function, false, context)) {
      return false;
    }
  }
  return true;
}

std::string directxEntryPointName(const HIRStage &stage) {
  return stage.stage + "_" + stage.entryPointName;
}

std::set<std::string>
directxUnsupportedStorageBufferArrayNames(const HIRModule &module) {
  std::set<std::string> bufferArrays;
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind == HIRResourceKind::Buffer &&
          isRuntimeDescriptorArray(resource) &&
          !directxResourceArrayShapeSupported(module, resource)) {
        bufferArrays.insert(resource.name);
      }
    }
  }
  return bufferArrays;
}

std::set<std::string>
directxUnsupportedRuntimeResourceArrayLabels(const HIRModule &module) {
  std::set<std::string> resourceArrays;
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind == HIRResourceKind::Buffer ||
          !isDirectXDescriptorResourceKind(resource.kind)) {
        continue;
      }
      const std::set<std::string> conflicts =
          directxDescriptorRangeConflictLabels(module, resource);
      resourceArrays.insert(conflicts.begin(), conflicts.end());
      if (isRuntimeDescriptorArray(resource) &&
          !directxRuntimeDescriptorArrayPolicySupported(module, resource)) {
        resourceArrays.insert(resourceArrayLabel(resource));
      }
    }
  }
  return resourceArrays;
}

std::set<std::string>
directxUnsupportedStorageBufferElementTypeLabels(const HIRModule &module) {
  std::set<std::string> elementTypes;
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind != HIRResourceKind::Buffer) {
        continue;
      }
      const HIRType elementType = bufferElementType(resource.type);
      if (!isSupportedStorageBufferElementType(module, elementType)) {
        elementTypes.insert(resource.name + " (" + elementType.name + ")");
      }
    }
  }
  return elementTypes;
}

} // namespace

bool directxTextualBackendSupported(const HIRModule &module) {
  const HIRStage *stage = singleComputeStage(module);
  if (stage != nullptr) {
    if (!stage->workgroupSize.has_value() || !constantsSupported(module) ||
        !resourcesSupported(module, *stage) ||
        !mixedSamplerStateUsageSupported(module) ||
        !unsupportedFunctionParameterArrayCallFeatureLabels(module).empty() ||
        !unsupportedFunctionParameterArrayWriteLabels(module).empty()) {
      return false;
    }
    const HIRFunction *entry = entryFunction(*stage);
    if (entry == nullptr) {
      return false;
    }
    const DirectXTextualSupportContext context{
        &module, callableFunctionNames(module, *stage), stage};
    return functionsSupported(module, *stage, *entry, context);
  }

  const HIRStage *vertex = nullptr;
  const HIRStage *fragment = nullptr;
  if (!directxGraphicsStagePair(module, vertex, fragment) ||
      !constantsSupported(module) || !module.functions.empty() ||
      !directxGraphicsResourcesSupported(module, *vertex, *fragment) ||
      !mixedSamplerStateUsageSupported(module) ||
      !unsupportedFunctionParameterArrayWriteLabels(module).empty()) {
    return false;
  }

  const DirectXTextualSupportContext vertexContext{
      &module, callableFunctionNames(module, *vertex), vertex};
  const DirectXTextualSupportContext fragmentContext{
      &module, callableFunctionNames(module, *fragment), fragment};
  if (!stageFunctionsSupported(module, *vertex, vertexContext) ||
      !stageFunctionsSupported(module, *fragment, fragmentContext)) {
    return false;
  }

  const HIRFunction *vertexEntry = entryFunction(*vertex);
  const HIRFunction *fragmentEntry = entryFunction(*fragment);
  return vertexEntry != nullptr && fragmentEntry != nullptr &&
         directxGraphicsVaryingsSupported(module, *vertexEntry, *fragmentEntry);
}

bool directxHasMixedSamplerStateUsage(const HIRModule &module) {
  return !mixedSamplerStateUsageNames(module).empty();
}

bool diagnoseDirectXMixedSamplerStateUsage(const HIRModule &module,
                                           DiagnosticEngine &diagnostics) {
  const std::set<std::string> unsupportedSamplers =
      unsupportedMixedSamplerStateUsageLabels(module);
  if (unsupportedSamplers.empty()) {
    return false;
  }
  diagnostics.error(
      "directx.mixed-sampler-state-usage",
      "DirectX source package cannot lower sampler-array resource(s) used for "
      "both ordinary texture sampling and comparison sampling: " +
          joinNames(unsupportedSamplers) +
          "; split them into distinct sampler resources because HLSL requires "
          "SamplerState and SamplerComparisonState declarations for "
          "descriptor-array state");
  return true;
}

bool directxHasUnsupportedStorageBufferArray(const HIRModule &module) {
  return !directxUnsupportedStorageBufferArrayNames(module).empty();
}

bool directxHasUnsupportedRuntimeResourceArray(const HIRModule &module) {
  return !directxUnsupportedRuntimeResourceArrayLabels(module).empty();
}

bool diagnoseDirectXUnsupportedGraphicsResources(const HIRModule &module,
                                                 DiagnosticEngine &diagnostics) {
  const std::set<std::string> unsupportedResources =
      directxUnsupportedGraphicsResourceLabels(module);
  const std::set<std::string> resourceConflicts =
      directxGraphicsResourceConflictLabels(module);
  if (unsupportedResources.empty() && resourceConflicts.empty()) {
    return false;
  }

  std::string details;
  if (!unsupportedResources.empty()) {
    details +=
        "unsupported resource(s): " + joinNames(unsupportedResources);
  }
  if (!resourceConflicts.empty()) {
    if (!details.empty()) {
      details += "; ";
    }
    details += "resource conflict(s): " + joinNames(resourceConflicts);
  }

  diagnostics.error(
      "directx.unsupported-graphics-resource",
      "DirectX graphics source package supports only fixed-size uniform "
      "buffers, non-array storage buffers, and texture/sampler resources, and "
      "vertex/fragment resources must have compatible names and HLSL register "
      "class/set/binding pairs; " +
          details +
          "; use supported uniform, storage-buffer, texture, or sampler "
          "graphics resources, or make resources shared by both graphics "
          "stages match exactly");
  return true;
}

bool diagnoseDirectXUnsupportedRuntimeResourceArray(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  const std::set<std::string> resourceArrays =
      directxUnsupportedRuntimeResourceArrayLabels(module);
  if (resourceArrays.empty()) {
    return false;
  }
  diagnostics.error(
      "directx.unsupported-runtime-resource-array",
      "DirectX source package requires fixed-size descriptor arrays when "
      "multiple unbounded descriptor arrays share an HLSL register class, an "
      "unbounded descriptor array overlaps another resource in the same HLSL "
      "register class/space, or the descriptor shape is ambiguous; "
      "unsupported unsized/runtime resource array(s): " +
          joinNames(resourceArrays) +
          "; use a fixed descriptor array size or keep only one unbounded "
          "descriptor array per register class/space without later descriptors "
          "in that class/space");
  return true;
}

bool diagnoseDirectXUnsupportedStorageBufferArray(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  const std::set<std::string> bufferArrays =
      directxUnsupportedStorageBufferArrayNames(module);
  if (bufferArrays.empty()) {
    return false;
  }
  diagnostics.error(
      "directx.unsupported-storage-buffer-array",
      "DirectX source package requires fixed-size storage-buffer descriptor "
      "array(s) when multiple unbounded storage-buffer descriptor arrays share "
      "the UAV register class or the descriptor shape is ambiguous; unsupported "
      "unsized array(s): " +
          joinNames(bufferArrays) +
          "; use a fixed descriptor array size or keep only one unbounded "
          "storage-buffer descriptor array");
  return true;
}

bool directxHasUnsupportedStorageBufferElementType(const HIRModule &module) {
  return !directxUnsupportedStorageBufferElementTypeLabels(module).empty();
}

bool diagnoseDirectXUnsupportedStorageBufferElementType(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  const std::set<std::string> elementTypes =
      directxUnsupportedStorageBufferElementTypeLabels(module);
  if (elementTypes.empty()) {
    return false;
  }
  diagnostics.error(
      "directx.unsupported-storage-buffer-element-type",
      "DirectX source package does not yet support storage-buffer element "
      "type(s): " +
          joinNames(elementTypes) +
          "; supported storage-buffer elements are scalar/vector/matrix "
          "types, top-level atomic<int>/atomic<uint> scalar elements, and "
          "structs with supported leaf fields, including nested structs and "
          "fixed-size supported leaf or nested-struct array fields");
  return true;
}

bool directxHasUnsupportedFunctionParameterArrayCallFeature(
    const HIRModule &module) {
  return !unsupportedFunctionParameterArrayCallFeatureLabels(module).empty();
}

bool diagnoseDirectXUnsupportedFunctionParameterArrayCallFeature(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  const std::set<std::string> unsupportedFeatures =
      unsupportedFunctionParameterArrayCallFeatureLabels(module);
  if (unsupportedFeatures.empty()) {
    return false;
  }
  diagnostics.error(
      "directx.unsupported-function-parameter-array-call-feature",
      "DirectX source package cannot lower unsupported fixed-size helper array "
      "call feature(s): " +
          joinNames(unsupportedFeatures) +
          "; the shared function-parameter array call ABI is " +
          functionParameterArrayCallSemanticsName(
              functionParameterArrayCallSemantics()) +
          ", and DirectX currently gates unsupported ABI shapes before HLSL "
          "emission");
  return true;
}

bool directxHasUnsupportedFunctionParameterArrayDynamicNestedRead(
    const HIRModule &module) {
  (void)module;
  return false;
}

bool diagnoseDirectXUnsupportedFunctionParameterArrayDynamicNestedRead(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  (void)module;
  (void)diagnostics;
  return false;
}

bool directxHasUnsupportedFunctionParameterArrayWrite(const HIRModule &module) {
  return !unsupportedFunctionParameterArrayWriteLabels(module).empty();
}

bool diagnoseDirectXUnsupportedFunctionParameterArrayWrite(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  const std::set<std::string> unsupportedWrites =
      unsupportedFunctionParameterArrayWriteLabels(module);
  if (unsupportedWrites.empty()) {
    return false;
  }
  diagnostics.error(
      "directx.unsupported-function-parameter-array-write",
      "DirectX source package cannot lower writes through fixed-size helper "
      "array parameter(s): " +
          joinNames(unsupportedWrites) +
          "; the shared function-parameter array call ABI is " +
          functionParameterArrayCallSemanticsName(
              functionParameterArrayCallSemantics()) +
          "; DirectX currently lowers callee-local helper array writes for "
          "fixed-size local array copies and direct non-aliased "
          "storage-buffer field array arguments used as a statement's direct "
          "helper-call value or as either binary expression operand when the "
          "other operand has no call-like evaluation");
  return true;
}

bool directxSourcePackageSupported(const HIRModule &module,
                                   DiagnosticEngine &diagnostics) {
  if (diagnoseRawStatementBackendInput(module, diagnostics)) {
    return false;
  }
  if (directxTextualBackendSupported(module)) {
    return true;
  }
  if (diagnoseDirectXMixedSamplerStateUsage(module, diagnostics)) {
    return false;
  }
  if (diagnoseDirectXUnsupportedGraphicsResources(module, diagnostics)) {
    return false;
  }
  if (diagnoseDirectXUnsupportedStorageBufferArray(module, diagnostics)) {
    return false;
  }
  if (diagnoseDirectXUnsupportedRuntimeResourceArray(module, diagnostics)) {
    return false;
  }
  if (diagnoseDirectXUnsupportedStorageBufferElementType(module, diagnostics)) {
    return false;
  }
  if (diagnoseDirectXUnsupportedFunctionParameterArrayCallFeature(
          module, diagnostics)) {
    return false;
  }
  if (diagnoseDirectXUnsupportedFunctionParameterArrayDynamicNestedRead(
          module, diagnostics)) {
    return false;
  }
  if (diagnoseDirectXUnsupportedFunctionParameterArrayWrite(module,
                                                            diagnostics)) {
    return false;
  }
  diagnostics.error(
      "directx.source-unsupported",
      "DirectX source package currently supports one compute stage, storage "
      "buffers, fixed-size uniform-buffer descriptor arrays, scalar/vector "
      "expressions, structured if blocks, structured "
      "for loops, 2D/2D-array/3D/cube/cube-array float and integer texture "
      "sampling with direct or indexed texture/sampler descriptors, including "
      "explicit-lod samples and ordinary compute samples lowered at LOD 0, "
      "2D and 2D-array storage images using imageLoad/imageStore, "
      "r32 integer storage-image atomics, "
      "fixed-size storage-image descriptor arrays with static, ordinary "
      "dynamic uniform, or nonuniform indices, "
      "mixed ordinary/comparison sampler resources lowered with "
      "paired HLSL sampler-state aliases, non-lod shadow texture comparison "
      "sampling, SM 6.7 explicit-lod shadow texture comparison sampling, "
      "manual explicit-lod shadow compare fallback sampling, scalar constants, "
      "fixed-size descriptor arrays, one unbounded descriptor array per HLSL "
      "register class/space when no later descriptor in that class/space "
      "overlaps it, helper "
      "functions with fixed-size scalar/vector/matrix array parameters and "
      "read-only fixed-size direct texture/sampler resource-array parameters, "
      "fixed-size numeric "
      "scalar/vector/matrix local arrays, including fixed nested local "
      "arrays, workgroup/shared memory declarations, statement-form and "
      "top-level declaration/assignment capture atomicAdd/atomicExchange/"
      "atomicAnd/atomicMin/atomicMax/atomicOr/atomicXor over scalar integer "
      "storage-buffer and groupshared atomic "
      "storage, dynamic nested "
      "helper-array reads, callee-local writes to helper array copies from "
      "local array arguments, direct non-aliased storage-buffer field array "
      "arguments with statement-form copy-in/write-back, and void entry "
      "functions, or one vertex stage "
      "plus one fragment stage with struct input/output signatures, "
      "scalar/vector stage IO fields, matched non-position varyings, no global "
      "helper functions, fixed-size uniform buffers, non-array storage "
      "buffers, and explicit-lod texture/sampler graphics resources");
  return false;
}

std::optional<std::string>
directxSamplerStateType(const HIRModule &module, const HIRResource &resource) {
  if (resource.kind != HIRResourceKind::Sampler ||
      !directxResourceArrayShapeSupported(module, resource)) {
    return std::nullopt;
  }
  if (resource.type.name != "sampler" &&
      resource.type.name != "comparison_sampler") {
    return std::nullopt;
  }
  const std::set<std::string> mixedSamplers =
      mixedSamplerStateUsageNames(module);
  if (mixedSamplers.count(resource.name) != 0) {
    if (resource.type.arraySize.has_value()) {
      return std::nullopt;
    }
    return "SamplerState";
  }
  const std::set<std::string> comparisonSamplers =
      comparisonSamplerNames(module);
  if (resource.type.name == "comparison_sampler" ||
      comparisonSamplers.count(resource.name) != 0) {
    return "SamplerComparisonState";
  }
  return "SamplerState";
}

std::optional<std::string>
directxResourceHLSLType(const HIRModule &module, const HIRResource &resource) {
  if (resource.kind == HIRResourceKind::Uniform) {
    if (!isSupportedUniformBufferResource(module, resource)) {
      return std::nullopt;
    }
    const std::string descriptorArrayType =
        hlslUniformBufferDescriptorArrayType(module, resource);
    if (!descriptorArrayType.empty()) {
      return descriptorArrayType;
    }
    return std::nullopt;
  }
  if (resource.kind == HIRResourceKind::Shared) {
    const std::string valueType = hlslSharedResourceElementType(resource.type);
    if (!valueType.empty()) {
      return valueType;
    }
    return std::nullopt;
  }
  if (resource.kind == HIRResourceKind::StorageImage) {
    if (isSupportedStorageImageResource(resource)) {
      return hlslStorageImageType(module, resource);
    }
    return std::nullopt;
  }
  if (resource.kind == HIRResourceKind::Buffer) {
    if (!directxResourceArrayShapeSupported(module, resource)) {
      return std::nullopt;
    }
    const std::string elementType =
        hlslStorageBufferElementType(module, bufferElementType(resource.type));
    if (!elementType.empty()) {
      return "RWStructuredBuffer<" + elementType + ">";
    }
    return std::nullopt;
  }
  if (resource.kind == HIRResourceKind::Texture) {
    if (!directxResourceArrayShapeSupported(module, resource)) {
      return std::nullopt;
    }
    const std::string textureType = hlslTextureType(resource.type);
    if (!textureType.empty()) {
      return textureType;
    }
    return std::nullopt;
  }
  if (resource.kind == HIRResourceKind::Sampler) {
    return directxSamplerStateType(module, resource);
  }
  return std::nullopt;
}

std::size_t directxResourceRegisterIndex(const HIRResource &resource) {
  return resource.binding;
}

std::string directxResourceAddressSpace(HIRResourceKind kind) {
  switch (kind) {
  case HIRResourceKind::Uniform:
    return "constant-buffer";
  case HIRResourceKind::Buffer:
    return "unordered-access";
  case HIRResourceKind::StorageImage:
    return "unordered-access";
  case HIRResourceKind::Texture:
    return "shader-resource";
  case HIRResourceKind::Sampler:
    return "sampler";
  case HIRResourceKind::Shared:
    return "groupshared";
  case HIRResourceKind::Value:
    break;
  }
  return "unknown";
}

std::string directxResourceBindingClass(HIRResourceKind kind) {
  switch (kind) {
  case HIRResourceKind::Uniform:
    return "constant-buffer";
  case HIRResourceKind::Buffer:
    return "uav";
  case HIRResourceKind::StorageImage:
    return "uav";
  case HIRResourceKind::Texture:
    return "srv";
  case HIRResourceKind::Sampler:
    return "sampler";
  case HIRResourceKind::Shared:
    return "groupshared";
  case HIRResourceKind::Value:
    break;
  }
  return "unknown";
}

std::string directxResourceDescriptorType(HIRResourceKind kind) {
  switch (kind) {
  case HIRResourceKind::Uniform:
    return "CBV";
  case HIRResourceKind::Buffer:
  case HIRResourceKind::StorageImage:
    return "UAV";
  case HIRResourceKind::Texture:
    return "SRV";
  case HIRResourceKind::Sampler:
    return "Sampler";
  case HIRResourceKind::Shared:
  case HIRResourceKind::Value:
    break;
  }
  return "unknown";
}

void emitStructDeclaration(std::ostringstream &out, const HIRModule &module,
                           const HIRStruct &structure) {
  out << "struct " << structure.name << " {\n";
  for (const HIRField &field : structure.fields) {
    out << "  " << hlslStructFieldType(module, field.type) << " " << field.name;
    if (field.type.arraySize.has_value()) {
      out << "[" << *field.type.arraySize << "]";
    }
    out << ";\n";
  }
  out << "};\n";
}

void appendDirectXStructDeclaration(const HIRModule &module,
                                    const HIRStruct *structure,
                                    std::set<std::string> &emitted,
                                    std::vector<const HIRStruct *> &ordered) {
  if (structure == nullptr || emitted.count(structure->name) != 0) {
    return;
  }
  emitted.insert(structure->name);
  for (const HIRField &field : structure->fields) {
    appendDirectXStructDeclaration(
        module, findStruct(module, baseTypeName(field.type)), emitted, ordered);
  }
  ordered.push_back(structure);
}

void emitFunction(std::ostringstream &out, const HIRFunction &function,
                  std::string_view functionName,
                  const DirectXEmitContext &context) {
  out << hlslValueType(context.module, function.returnType) << " "
      << functionName << "(";
  for (std::size_t index = 0; index < function.parameters.size(); ++index) {
    if (index != 0) {
      out << ", ";
    }
    const HIRParameter &parameter = function.parameters[index];
    out << hlslFunctionParameterDeclarator(context.module, parameter.type,
                                           parameter.name);
  }
  out << ") {\n";
  for (const HIRStatement &statement : function.body) {
    emitStatement(out, statement, 2, context);
  }
  out << "}\n";
}

bool expressionUsesIdentifier(const HIRExpression &expression,
                              std::string_view identifier) {
  if (expression.kind == HIRExpressionKind::Identifier &&
      expression.value == identifier) {
    return true;
  }
  for (const HIRExpression &child : expression.children) {
    if (expressionUsesIdentifier(child, identifier)) {
      return true;
    }
  }
  return false;
}

bool statementUsesIdentifier(const HIRStatement &statement,
                             std::string_view identifier) {
  if (expressionUsesIdentifier(statement.target, identifier) ||
      expressionUsesIdentifier(statement.value, identifier)) {
    return true;
  }
  for (const HIRStatement &child : statement.initializer) {
    if (statementUsesIdentifier(child, identifier)) {
      return true;
    }
  }
  for (const HIRStatement &child : statement.update) {
    if (statementUsesIdentifier(child, identifier)) {
      return true;
    }
  }
  for (const HIRStatement &child : statement.body) {
    if (statementUsesIdentifier(child, identifier)) {
      return true;
    }
  }
  for (const HIRStatement &child : statement.elseBody) {
    if (statementUsesIdentifier(child, identifier)) {
      return true;
    }
  }
  return false;
}

bool functionUsesIdentifier(const HIRFunction &function,
                            std::string_view identifier) {
  for (const HIRStatement &statement : function.body) {
    if (statementUsesIdentifier(statement, identifier)) {
      return true;
    }
  }
  return false;
}

void emitComputeInvocationParameter(std::ostringstream &out,
                                    const DirectXComputeInvocationBuiltin &id) {
  out << "uint3 " << id.parameterName << " : " << id.semantic;
}

std::string generateDirectXComputeSource(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts *resourceBindings) {
  std::ostringstream out;
  const HIRStage *computeStage = singleComputeStage(module);
  if (computeStage == nullptr || !directxTextualBackendSupported(module)) {
    return out.str();
  }

  const HIRStage &stage = *computeStage;
  const HIRFunction &entry = *entryFunction(stage);
  const std::set<std::string> mixedSamplers =
      mixedSamplerStateUsageNames(module);
  std::size_t nextTemporaryIndex = 0;
  DirectXEmitContext emitContext{&module, mixedSamplers};
  emitContext.stage = &stage;
  emitContext.nextTemporaryIndex = &nextTemporaryIndex;
  for (const HIRConstant &constant : module.constants) {
    out << "static const " << hlslType(constant.type) << " " << constant.name
        << " = " << emitConstantValue(constant) << ";\n";
  }
  if (!module.constants.empty()) {
    out << "\n";
  }

  std::vector<const HIRStruct *> resourceStructs =
      storageBufferStructDeclarations(
          module, stage, directxStructStorageBufferElementSupported);
  std::set<std::string> emittedStructs;
  for (const HIRStruct *structure : resourceStructs) {
    if (structure != nullptr) {
      emittedStructs.insert(structure->name);
    }
  }
  for (const HIRResource &resource : stage.resources) {
    if (resource.kind != HIRResourceKind::Uniform) {
      continue;
    }
    HIRType elementType = resource.type;
    elementType.arraySize.reset();
    appendDirectXStructDeclaration(module, findStruct(module, elementType.name),
                                   emittedStructs, resourceStructs);
  }
  for (const HIRStruct *structure : resourceStructs) {
    emitStructDeclaration(out, module, *structure);
  }
  if (!resourceStructs.empty()) {
    out << "\n";
  }
  for (const HIRResource &resource : stage.resources) {
    emitResourceDeclaration(out, module, resource, stage.stage, resourceBindings,
                            mixedSamplers);
  }
  if (hasResources(stage)) {
    out << "\n";
  }
  if (moduleUsesManualTextureCompare(module)) {
    emitManualCompareHelper(out);
  }

  for (const HIRFunction &function : module.functions) {
    DirectXEmitContext functionContext = emitContext;
    functionContext.function = &function;
    emitFunction(out, function, function.name, functionContext);
    out << "\n";
  }
  for (const HIRFunction &function : stage.functions) {
    if (function.name == stage.entryPointName) {
      continue;
    }
    DirectXEmitContext functionContext = emitContext;
    functionContext.function = &function;
    emitFunction(out, function, function.name, functionContext);
    out << "\n";
  }

  const HIRWorkgroupSize &workgroup = *stage.workgroupSize;
  out << "[numthreads(" << workgroup.x << ", " << workgroup.y << ", "
      << workgroup.z << ")]\n";
  out << "void " << directxEntryPointName(stage) << "(";
  emitComputeInvocationParameter(out, kDirectXComputeInvocationBuiltins[0]);
  for (std::size_t index = 1; index < kDirectXComputeInvocationBuiltins.size();
       ++index) {
    if (!functionUsesIdentifier(
            entry, kDirectXComputeInvocationBuiltins[index].sourceName)) {
      continue;
    }
    out << ", ";
    emitComputeInvocationParameter(out,
                                   kDirectXComputeInvocationBuiltins[index]);
  }
  out << ") {\n";
  DirectXEmitContext entryEmitContext = emitContext;
  entryEmitContext.rewriteComputeInvocationBuiltins = true;
  entryEmitContext.function = &entry;
  for (const HIRStatement &statement : entry.body) {
    emitStatement(out, statement, 2, entryEmitContext);
  }
  out << "}\n";
  return out.str();
}

std::string directxUserEntryPointName(const HIRStage &stage) {
  return "crossgl_user_" + directxEntryPointName(stage);
}

std::string directxGraphicsWrapperStructName(std::string_view stage,
                                             std::string_view role) {
  return "crossgl_" + std::string(stage) + "_" + std::string(role);
}

std::string directxVertexInputSemantic(const HIRField &field,
                                       std::size_t index) {
  if (field.name == "position") {
    return "POSITION0";
  }
  return "TEXCOORD" + std::to_string(index);
}

std::string directxVaryingSemantic(std::size_t index) {
  return "TEXCOORD" + std::to_string(index);
}

std::optional<std::size_t>
directxFragmentInputSemanticIndex(const HIRStruct &fragmentInput,
                                  std::string_view fieldName) {
  for (std::size_t index = 0; index < fragmentInput.fields.size(); ++index) {
    if (fragmentInput.fields[index].name == fieldName) {
      return index;
    }
  }
  return std::nullopt;
}

void emitDirectXGraphicsWrapperStruct(std::ostringstream &out,
                                      std::string_view name,
                                      const HIRStruct &structure,
                                      const HIRStruct *fragmentInput,
                                      const HIRField *positionField,
                                      bool vertexInput, bool fragmentOutput) {
  out << "struct " << name << " {\n";
  std::size_t extraVaryingIndex =
      fragmentInput == nullptr ? 0 : fragmentInput->fields.size();
  for (std::size_t index = 0; index < structure.fields.size(); ++index) {
    const HIRField &field = structure.fields[index];
    std::string semantic;
    if (positionField != nullptr && &field == positionField) {
      semantic = "SV_Position";
    } else if (fragmentOutput) {
      semantic = "SV_Target" + std::to_string(index);
    } else if (vertexInput) {
      semantic = directxVertexInputSemantic(field, index);
    } else if (fragmentInput != nullptr) {
      const std::optional<std::size_t> varyingIndex =
          directxFragmentInputSemanticIndex(*fragmentInput, field.name);
      semantic =
          directxVaryingSemantic(varyingIndex.value_or(extraVaryingIndex++));
    } else {
      semantic = directxVaryingSemantic(index);
    }
    out << "  " << hlslType(field.type) << " " << field.name << " : "
        << semantic << ";\n";
  }
  out << "};\n";
}

std::vector<const HIRStruct *> directxGraphicsStructDeclarations(
    const HIRModule &module, const HIRStage &vertexStage,
    const HIRStage &fragmentStage, const HIRFunction &vertexEntry,
    const HIRFunction &fragmentEntry) {
  std::vector<const HIRStruct *> ordered;
  std::set<std::string> emitted;
  const auto append = [&](const HIRStruct *structure) {
    appendDirectXStructDeclaration(module, structure, emitted, ordered);
  };
  for (const HIRResource *resource :
       directxGraphicsStageResources(vertexStage, fragmentStage)) {
    if (resource->kind == HIRResourceKind::Uniform) {
      HIRType elementType = resource->type;
      elementType.arraySize.reset();
      append(findStruct(module, elementType.name));
    } else if (resource->kind == HIRResourceKind::Buffer) {
      const HIRType elementType = bufferElementType(resource->type);
      append(findStruct(module, elementType.name));
    }
  }
  append(directxStructType(module, vertexEntry.parameters.front().type));
  append(directxStructType(module, vertexEntry.returnType));
  append(directxStructType(module, fragmentEntry.parameters.front().type));
  append(directxStructType(module, fragmentEntry.returnType));
  return ordered;
}

std::vector<DirectXGraphicsResourceRef>
directxGraphicsResourceDeclarations(const HIRStage &vertexStage,
                                    const HIRStage &fragmentStage) {
  std::vector<DirectXGraphicsResourceRef> ordered;
  for (const DirectXGraphicsResourceRef &resourceRef :
       directxGraphicsStageResourceRefs(vertexStage, fragmentStage)) {
    bool alreadyEmitted = false;
    for (const DirectXGraphicsResourceRef &emitted : ordered) {
      if (directxSameGraphicsResource(*emitted.resource,
                                      *resourceRef.resource)) {
        alreadyEmitted = true;
        break;
      }
    }
    if (!alreadyEmitted) {
      ordered.push_back(resourceRef);
    }
  }
  return ordered;
}

void emitDirectXStageFunctionDefinitions(std::ostringstream &out,
                                         const HIRStage &stage,
                                         const HIRFunction &entry,
                                         const DirectXEmitContext &context) {
  for (const HIRFunction &function : stage.functions) {
    if (&function == &entry) {
      continue;
    }
    DirectXEmitContext functionContext = context;
    functionContext.function = &function;
    emitFunction(out, function, function.name, functionContext);
    out << "\n";
  }
  DirectXEmitContext entryContext = context;
  entryContext.function = &entry;
  emitFunction(out, entry, directxUserEntryPointName(stage), entryContext);
  out << "\n";
}

std::string generateDirectXGraphicsSource(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts *resourceBindings) {
  std::ostringstream out;
  const HIRStage *vertexStage = nullptr;
  const HIRStage *fragmentStage = nullptr;
  if (!directxGraphicsStagePair(module, vertexStage, fragmentStage) ||
      !directxTextualBackendSupported(module)) {
    return out.str();
  }

  const HIRFunction &vertexEntry = *entryFunction(*vertexStage);
  const HIRFunction &fragmentEntry = *entryFunction(*fragmentStage);
  const HIRStruct &vertexInput =
      *directxStructType(module, vertexEntry.parameters.front().type);
  const HIRStruct &vertexOutput =
      *directxStructType(module, vertexEntry.returnType);
  const HIRStruct &fragmentInput =
      *directxStructType(module, fragmentEntry.parameters.front().type);
  const HIRStruct &fragmentOutput =
      *directxStructType(module, fragmentEntry.returnType);
  const HIRField &position = *directxGraphicsPositionField(vertexOutput);

  for (const HIRConstant &constant : module.constants) {
    out << "static const " << hlslType(constant.type) << " " << constant.name
        << " = " << emitConstantValue(constant) << ";\n";
  }
  if (!module.constants.empty()) {
    out << "\n";
  }

  for (const HIRStruct *structure : directxGraphicsStructDeclarations(
           module, *vertexStage, *fragmentStage, vertexEntry, fragmentEntry)) {
    emitStructDeclaration(out, module, *structure);
  }
  out << "\n";

  const std::set<std::string> mixedSamplers =
      mixedSamplerStateUsageNames(module);
  for (const DirectXGraphicsResourceRef &resourceRef :
       directxGraphicsResourceDeclarations(*vertexStage, *fragmentStage)) {
    emitResourceDeclaration(out, module, *resourceRef.resource,
                            resourceRef.stage, resourceBindings,
                            mixedSamplers);
  }
  if (!vertexStage->resources.empty() || !fragmentStage->resources.empty()) {
    out << "\n";
  }
  if (moduleUsesManualTextureCompare(module)) {
    emitManualCompareHelper(out);
  }

  const std::string vertexInputWrapper =
      directxGraphicsWrapperStructName("vertex", "input");
  const std::string vertexOutputWrapper =
      directxGraphicsWrapperStructName("vertex", "output");
  const std::string fragmentInputWrapper =
      directxGraphicsWrapperStructName("fragment", "input");
  const std::string fragmentOutputWrapper =
      directxGraphicsWrapperStructName("fragment", "output");
  emitDirectXGraphicsWrapperStruct(out, vertexInputWrapper, vertexInput,
                                   nullptr, nullptr, true, false);
  emitDirectXGraphicsWrapperStruct(out, vertexOutputWrapper, vertexOutput,
                                   &fragmentInput, &position, false, false);
  emitDirectXGraphicsWrapperStruct(out, fragmentInputWrapper, fragmentInput,
                                   nullptr, nullptr, false, false);
  emitDirectXGraphicsWrapperStruct(out, fragmentOutputWrapper, fragmentOutput,
                                   nullptr, nullptr, false, true);
  out << "\n";

  std::size_t nextTemporaryIndex = 0;
  DirectXEmitContext vertexContext{&module, mixedSamplers, false};
  vertexContext.stage = vertexStage;
  vertexContext.nextTemporaryIndex = &nextTemporaryIndex;
  DirectXEmitContext fragmentContext{&module, mixedSamplers, false};
  fragmentContext.stage = fragmentStage;
  fragmentContext.nextTemporaryIndex = &nextTemporaryIndex;
  emitDirectXStageFunctionDefinitions(out, *vertexStage, vertexEntry,
                                      vertexContext);
  emitDirectXStageFunctionDefinitions(out, *fragmentStage, fragmentEntry,
                                      fragmentContext);

  out << vertexOutputWrapper << " " << directxEntryPointName(*vertexStage)
      << "(" << vertexInputWrapper << " crossgl_input) {\n";
  out << "  " << vertexInput.name << " crossgl_user_input;\n";
  for (const HIRField &field : vertexInput.fields) {
    out << "  crossgl_user_input." << field.name << " = crossgl_input."
        << field.name << ";\n";
  }
  out << "  " << vertexOutput.name
      << " crossgl_user_output = " << directxUserEntryPointName(*vertexStage)
      << "(crossgl_user_input);\n";
  out << "  " << vertexOutputWrapper << " crossgl_output;\n";
  for (const HIRField &field : vertexOutput.fields) {
    out << "  crossgl_output." << field.name << " = crossgl_user_output."
        << field.name << ";\n";
  }
  out << "  return crossgl_output;\n";
  out << "}\n\n";

  out << fragmentOutputWrapper << " " << directxEntryPointName(*fragmentStage)
      << "(" << fragmentInputWrapper << " crossgl_input) {\n";
  out << "  " << fragmentInput.name << " crossgl_user_input;\n";
  for (const HIRField &field : fragmentInput.fields) {
    out << "  crossgl_user_input." << field.name << " = crossgl_input."
        << field.name << ";\n";
  }
  out << "  " << fragmentOutput.name
      << " crossgl_user_output = " << directxUserEntryPointName(*fragmentStage)
      << "(crossgl_user_input);\n";
  out << "  " << fragmentOutputWrapper << " crossgl_output;\n";
  for (const HIRField &field : fragmentOutput.fields) {
    out << "  crossgl_output." << field.name << " = crossgl_user_output."
        << field.name << ";\n";
  }
  out << "  return crossgl_output;\n";
  out << "}\n";
  return out.str();
}

std::string generateDirectXSource(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts *resourceBindings) {
  if (singleComputeStage(module) != nullptr) {
    return generateDirectXComputeSource(module, resourceBindings);
  }
  return generateDirectXGraphicsSource(module, resourceBindings);
}

std::optional<TargetLegalizationResourceBindingFacts>
directxLegalizedResourceBindingsForEmission(const HIRModule &module) {
  TargetLegalizationResult legalization =
      legalizeTarget(module, TargetKind::DirectX);
  if (legalization.target != TargetKind::DirectX ||
      legalization.resourceBindings.target != TargetKind::DirectX ||
      !legalization.resourceBindings.complete) {
    return std::nullopt;
  }
  return legalization.resourceBindings;
}

std::string generateDirectXSource(const HIRModule &module) {
  const std::optional<TargetLegalizationResourceBindingFacts> resourceBindings =
      directxLegalizedResourceBindingsForEmission(module);
  return generateDirectXSource(
      module, resourceBindings.has_value() ? &*resourceBindings : nullptr);
}

std::string generateDirectXSource(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts &resourceBindings) {
  return generateDirectXSource(module, &resourceBindings);
}

std::string generateDirectXBackendIR(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts *resourceBindings) {
  std::ostringstream out;
  out << "// backend lowering for directx: textual HLSL compute/graphics "
         "scaffold; source packages are emitted and DXIL is produced or "
         "validated when dxc is available\n";
  out << "// directx dxc shader profile plan: "
      << directxShaderProfileSummary(module) << "\n";
  if (moduleContainsRawStatement(module)) {
    out << "// error: " << kRawStatementBackendInputDiagnostic
        << ": DirectX backend input cannot contain HIR raw statements; lower "
           "them to structured HIR before backend emission\n";
    return out.str();
  }

  if (!directxTextualBackendSupported(module)) {
    const std::set<std::string> bufferArrays =
        directxUnsupportedStorageBufferArrayNames(module);
    if (!bufferArrays.empty()) {
      out << "// directx textual scaffold does not yet support ambiguous "
             "storage-buffer descriptor arrays with unsized descriptor counts ("
          << joinNames(bufferArrays)
          << "); use a fixed descriptor array size or keep only one unbounded "
             "storage-buffer descriptor array\n";
    }
    const std::set<std::string> resourceArrays =
        directxUnsupportedRuntimeResourceArrayLabels(module);
    if (!resourceArrays.empty()) {
      out << "// directx textual scaffold does not yet support ambiguous "
             "or overlapping descriptor arrays with unsized/runtime "
             "descriptor counts ("
          << joinNames(resourceArrays)
          << "); use a fixed descriptor array size or keep only one unbounded "
             "descriptor array per register class/space without later "
             "descriptors in that class/space\n";
    }
    const std::set<std::string> bufferElementTypes =
        directxUnsupportedStorageBufferElementTypeLabels(module);
    if (!bufferElementTypes.empty()) {
      out << "// directx textual scaffold does not yet support storage-buffer "
             "element types ("
          << joinNames(bufferElementTypes)
          << "); scalar/vector/matrix storage-buffer elements, top-level "
             "atomic<int>/atomic<uint> scalar elements, and structs with "
             "supported leaf fields, including fixed-size array fields, are "
             "supported\n";
    }
    const std::set<std::string> unsupportedMixedSamplers =
        unsupportedMixedSamplerStateUsageLabels(module);
    if (!unsupportedMixedSamplers.empty()) {
      out << "// directx textual scaffold rejects sampler arrays used for both "
             "ordinary and comparison sampling ("
          << joinNames(unsupportedMixedSamplers)
          << "); split them into distinct sampler resources for HLSL "
             "SamplerState/SamplerComparisonState descriptor-array lowering\n";
    }
    const std::set<std::string> unsupportedArrayCallFeatures =
        unsupportedFunctionParameterArrayCallFeatureLabels(module);
    if (!unsupportedArrayCallFeatures.empty()) {
      out << "// directx textual scaffold rejects unsupported fixed-size "
             "helper array call feature(s) ("
          << joinNames(unsupportedArrayCallFeatures) << "); the shared ABI is "
          << functionParameterArrayCallSemanticsName(
                 functionParameterArrayCallSemantics())
          << "\n";
    }
    const std::set<std::string> unsupportedArrayWrites =
        unsupportedFunctionParameterArrayWriteLabels(module);
    if (!unsupportedArrayWrites.empty()) {
      out << "// directx textual scaffold rejects writes through fixed-size "
             "helper array parameter(s) ("
          << joinNames(unsupportedArrayWrites) << "); the shared ABI is "
          << functionParameterArrayCallSemanticsName(
                 functionParameterArrayCallSemantics())
          << "\n";
    }
    out << "// directx textual scaffold currently supports one compute stage, "
           "storage buffers, scalar/vector expressions, scalar/vector math "
           "intrinsics, structured if blocks, structured for loops, "
           "2D/2D-array/3D/cube/cube-array float and integer texture sampling "
           "with direct or indexed texture/sampler descriptors, including "
           "explicit-lod samples and ordinary compute samples lowered at "
           "LOD 0, 2D and 2D-array storage images using imageLoad/imageStore, "
           "r32 integer storage-image atomics, "
           "fixed-size storage-image descriptor arrays with static, ordinary "
           "dynamic uniform, or nonuniform indices, "
           "ordinary/comparison sampler resources lowered with paired HLSL "
           "sampler-state aliases, non-lod shadow "
           "texture comparison sampling, SM 6.7 explicit-lod shadow texture "
           "comparison sampling, manual explicit-lod shadow compare fallback "
           "sampling, scalar constants, fixed-size descriptor arrays, one "
           "unbounded descriptor array per HLSL register class/space when no "
           "later descriptor in that class/space overlaps it, helper functions "
           "with fixed-size "
           "scalar/vector/matrix array parameters, fixed-size numeric "
           "scalar/vector/matrix local arrays, including fixed nested local "
           "arrays, workgroup/shared memory declarations, statement-form and "
           "top-level declaration/assignment capture atomicAdd/"
           "atomicExchange/atomicAnd/atomicMin/atomicMax/atomicOr/atomicXor "
           "over scalar integer storage-buffer and groupshared "
           "atomic storage, dynamic nested helper-array reads, callee-local "
           "writes to helper array copies from local array arguments, direct "
           "non-aliased storage-buffer field array arguments with "
           "statement-form copy-in/write-back, and void entry functions, or "
           "one vertex stage plus one fragment stage "
           "with struct input/output signatures, scalar/vector stage IO "
           "fields, matched non-position varyings, no global helper functions, "
           "fixed-size uniform buffers, non-array storage buffers, and "
           "explicit-lod texture/sampler graphics resources\n\n";
    out << "// source CrossGL IR follows\n";
    return out.str();
  }

  out << generateDirectXSource(module, resourceBindings) << "\n\n";
  out << "// source CrossGL IR follows\n";
  return out.str();
}

std::string generateDirectXBackendIR(const HIRModule &module) {
  const std::optional<TargetLegalizationResourceBindingFacts> resourceBindings =
      directxLegalizedResourceBindingsForEmission(module);
  return generateDirectXBackendIR(
      module, resourceBindings.has_value() ? &*resourceBindings : nullptr);
}

std::string generateDirectXBackendIR(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts &resourceBindings) {
  return generateDirectXBackendIR(module, &resourceBindings);
}

bool appendDirectXDxilBundleStage(std::ofstream &bundle,
                                  std::string_view stage,
                                  const std::filesystem::path &path,
                                  DiagnosticEngine &diagnostics) {
  std::error_code error;
  const std::uintmax_t size = std::filesystem::file_size(path, error);
  if (error) {
    diagnostics.error("directx.read-dxil",
                      "failed to inspect '" + path.string() + "': " +
                          error.message());
    return false;
  }

  std::ifstream input(path, std::ios::binary);
  if (!input) {
    diagnostics.error("directx.read-dxil",
                      "failed to read '" + path.string() + "'");
    return false;
  }

  bundle << "stage " << stage << " file " << path.filename().generic_string()
         << " size " << size << "\n";
  bundle << input.rdbuf();
  if (input.bad() || !bundle) {
    diagnostics.error("directx.write-dxil-bundle",
                      "failed to append '" + path.string() + "'");
    return false;
  }
  bundle << "\n";
  return static_cast<bool>(bundle);
}

bool writeDirectXGraphicsDxilBundle(const std::filesystem::path &bundlePath,
                                    const std::filesystem::path &vertexPath,
                                    const std::filesystem::path &fragmentPath,
                                    DiagnosticEngine &diagnostics) {
  std::ofstream bundle(bundlePath, std::ios::binary);
  if (!bundle) {
    diagnostics.error("directx.write-dxil-bundle",
                      "failed to write '" + bundlePath.string() + "'");
    return false;
  }

  bundle << "CrossGL DirectX graphics DXIL bundle v1\n";
  if (!appendDirectXDxilBundleStage(bundle, "vertex", vertexPath,
                                    diagnostics) ||
      !appendDirectXDxilBundleStage(bundle, "fragment", fragmentPath,
                                    diagnostics)) {
    return false;
  }
  return static_cast<bool>(bundle);
}

std::vector<std::string>
directxDxcCommand(const std::string &dxc,
                  const std::filesystem::path &sourcePath,
                  const std::filesystem::path &outputPath,
                  std::string_view targetProfile,
                  std::string_view entryPoint,
                  OptimizationLevel optimizationLevel) {
  return {dxc,
          std::string(directxDxcOptimizationFlag(optimizationLevel)),
          "-T",
          std::string(targetProfile),
          "-E",
          std::string(entryPoint),
          "-Fo",
          outputPath.string(),
          sourcePath.string()};
}

std::string
directxDxcCommandProfile(std::string_view targetProfile,
                         std::string_view entryPoint,
                         const std::filesystem::path &packageRelativeOutput,
                         const std::filesystem::path &packageRelativeSource,
                         OptimizationLevel optimizationLevel) {
  std::ostringstream out;
  out << "dxc " << directxDxcOptimizationFlag(optimizationLevel) << " -T "
      << targetProfile << " -E " << entryPoint << " -Fo "
      << packageRelativeOutput.generic_string() << " "
      << packageRelativeSource.generic_string();
  return out.str();
}

std::filesystem::path
directxPackageRelativePath(const std::filesystem::path &path,
                           const std::filesystem::path &packageDir) {
  std::error_code error;
  std::filesystem::path relative =
      std::filesystem::relative(path, packageDir, error);
  if (error) {
    return path.filename();
  }
  return relative;
}

std::string directxTrimCapturedText(std::string text) {
  while (!text.empty() &&
         (text.back() == '\n' || text.back() == '\r' ||
          text.back() == ' ' || text.back() == '\t')) {
    text.pop_back();
  }
  std::size_t start = 0;
  while (start < text.size() &&
         (text[start] == '\n' || text[start] == '\r' ||
          text[start] == ' ' || text[start] == '\t')) {
    ++start;
  }
  if (start != 0) {
    text.erase(0, start);
  }
  for (char &ch : text) {
    if (ch == '\n' || ch == '\r') {
      ch = ' ';
    }
  }
  constexpr std::size_t maxCapturedDiagnosticLength = 1200;
  if (text.size() > maxCapturedDiagnosticLength) {
    text.resize(maxCapturedDiagnosticLength);
    text += "...";
  }
  return text;
}

std::string directxDxcExitStatus(const ProcessCaptureResult &result) {
  if (result.started) {
    return std::to_string(result.exitCode);
  }
  if (!result.error.empty()) {
    return "not-started: " + result.error;
  }
  return "not-started";
}

std::string directxDxcDiagnostics(const ProcessCaptureResult &result) {
  std::vector<std::string> parts;
  if (!result.stderrText.empty()) {
    parts.push_back("stderr: " + directxTrimCapturedText(result.stderrText));
  }
  if (!result.stdoutText.empty()) {
    parts.push_back("stdout: " + directxTrimCapturedText(result.stdoutText));
  }
  if (!result.error.empty()) {
    parts.push_back("error: " + result.error);
  }
  if (parts.empty()) {
    return "no dxc diagnostic output captured";
  }

  std::ostringstream out;
  for (std::size_t index = 0; index < parts.size(); ++index) {
    if (index != 0) {
      out << "; ";
    }
    out << parts[index];
  }
  return out.str();
}

DirectXSourcePackageResult
buildDirectXSourcePackage(const HIRModule &module,
                          const std::filesystem::path &packageDir,
                          DiagnosticEngine &diagnostics,
                          const TargetLegalizationResourceBindingFacts
                              *resourceBindings,
                          OptimizationLevel optimizationLevel) {
  DirectXSourcePackageResult result;
  const DirectXDxcOptimizationProfile optimizationProfile =
      directxDxcOptimizationProfile(optimizationLevel);
  result.optimizationRequestedLevel =
      std::string(optimizationProfile.requestedLevel);
  result.optimizationLevel = std::string(optimizationProfile.dxcFlag);
  if (!directxSourcePackageSupported(module, diagnostics)) {
    return result;
  }
  if (diagnoseDirectXLegalizedResourceDeclarationMismatches(
          module, resourceBindings, diagnostics)) {
    return result;
  }

  const std::filesystem::path directxDir = packageDir / "backend" / "directx";
  std::error_code error;
  std::filesystem::create_directories(directxDir, error);
  if (error) {
    diagnostics.error("directx.source-package-directory",
                      "failed to create DirectX backend directory: " +
                          error.message());
    return result;
  }

  const HIRStage *vertexStage = nullptr;
  const HIRStage *fragmentStage = nullptr;
  const bool graphicsSource =
      directxGraphicsStagePair(module, vertexStage, fragmentStage);
  const std::string sourceSuffix = graphicsSource ? ".graphics.hlsl" : ".hlsl";
  result.sourcePath = directxDir / (module.name + sourceSuffix);
  result.nativeBinaryPath = directxDir / (module.name + ".dxil");
  const std::filesystem::path packageRelativeSource =
      directxPackageRelativePath(result.sourcePath, packageDir);
  const std::filesystem::path packageRelativeNativeBinary =
      directxPackageRelativePath(result.nativeBinaryPath, packageDir);
  std::filesystem::remove(result.nativeBinaryPath, error);

  const std::string sourceText = generateDirectXSource(module, resourceBindings);
  std::ofstream source(result.sourcePath, std::ios::binary);
  if (!source) {
    diagnostics.error("directx.write-source",
                      "failed to write '" + result.sourcePath.string() + "'");
    return result;
  }
  source << sourceText;
  source.close();

  const std::string profileSummary = directxShaderProfileSummary(module);
  result.shaderProfileSummary = profileSummary;
  const std::string optimizationEvidence =
      directxDxcOptimizationEvidence(optimizationLevel);
  diagnostics.note("directx.source-package-emitted",
                   "emitted HLSL source package; DXIL emission with dxc uses " +
                       std::string(directxDxcOptimizationFlag(
                           optimizationLevel)) +
                       "; optimization profile: " + optimizationEvidence +
                       "; shader profile(s): " + profileSummary);

  const std::optional<std::string> dxc = findExecutable("dxc");
  if (!dxc.has_value()) {
    diagnostics.warning("directx.source-package-only",
                        "emitted HLSL source package; native DXIL package "
                        "emission is planned because dxc was not found; no "
                        "dxc command was invoked; "
                        "optimization profile: " +
                            optimizationEvidence + "; "
                        "planned shader profile(s): " +
                            profileSummary);
    result.success = !diagnostics.hasErrors();
    return result;
  }

  if (graphicsSource) {
    const std::filesystem::path vertexDxil =
        directxDir / (module.name + ".vertex.dxil");
    const std::filesystem::path fragmentDxil =
        directxDir / (module.name + ".fragment.dxil");
    const std::filesystem::path packageRelativeVertexDxil =
        directxPackageRelativePath(vertexDxil, packageDir);
    const std::filesystem::path packageRelativeFragmentDxil =
        directxPackageRelativePath(fragmentDxil, packageDir);
    std::filesystem::remove(vertexDxil, error);
    std::filesystem::remove(fragmentDxil, error);
    const std::string vertexProfile =
        directxShaderProfile(module, *vertexStage);
    const std::string fragmentProfile =
        directxShaderProfile(module, *fragmentStage);
    const std::string vertexEntryPoint = directxEntryPointName(*vertexStage);
    const std::string fragmentEntryPoint =
        directxEntryPointName(*fragmentStage);
    const std::vector<std::string> vertexCommand =
        directxDxcCommand(*dxc, result.sourcePath, vertexDxil, vertexProfile,
                          vertexEntryPoint, optimizationLevel);
    const std::vector<std::string> fragmentCommand =
        directxDxcCommand(*dxc, result.sourcePath, fragmentDxil,
                          fragmentProfile, fragmentEntryPoint,
                          optimizationLevel);
    const std::string vertexCommandProfile = directxDxcCommandProfile(
        vertexProfile, vertexEntryPoint, packageRelativeVertexDxil,
        packageRelativeSource, optimizationLevel);
    const std::string fragmentCommandProfile = directxDxcCommandProfile(
        fragmentProfile, fragmentEntryPoint, packageRelativeFragmentDxil,
        packageRelativeSource, optimizationLevel);
    const ProcessCaptureResult vertexResult = runProcessCapture(vertexCommand);
    const ProcessCaptureResult fragmentResult =
        runProcessCapture(fragmentCommand);
    if (vertexResult.started && vertexResult.exitCode == 0 &&
        fragmentResult.started && fragmentResult.exitCode == 0 &&
        std::filesystem::exists(vertexDxil) &&
        std::filesystem::exists(fragmentDxil)) {
      if (!writeDirectXGraphicsDxilBundle(result.nativeBinaryPath, vertexDxil,
                                          fragmentDxil, diagnostics)) {
        return result;
      }
      diagnostics.note("directx.dxil-emitted",
                       "compiled HLSL graphics source to vertex and fragment "
                       "DXIL with dxc; shader profile(s): " +
                           profileSummary + "; optimization profile: " +
                           optimizationEvidence + "; vertex command profile: " +
                           vertexCommandProfile +
                           "; fragment command profile: " +
                           fragmentCommandProfile);
      result.nativeBinaryProduced = true;
      result.nativeBinaryStatus = "emitted";
      result.optimizationStatus = "applied";
      result.success = !diagnostics.hasErrors();
      return result;
    }
    std::filesystem::remove(vertexDxil, error);
    std::filesystem::remove(fragmentDxil, error);
    diagnostics.warning("directx.dxc-failed",
                        "dxc was found but failed to validate generated HLSL "
                        "graphics source with shader profile(s): " +
                            profileSummary + "; vertex exit status: " +
                            directxDxcExitStatus(vertexResult) +
                            "; fragment exit status: " +
                            directxDxcExitStatus(fragmentResult) +
                            "; optimization profile: " + optimizationEvidence +
                            "; vertex command profile: " +
                            vertexCommandProfile +
                            "; fragment command profile: " +
                            fragmentCommandProfile +
                            "; vertex dxc diagnostics: " +
                            directxDxcDiagnostics(vertexResult) +
                            "; fragment dxc diagnostics: " +
                            directxDxcDiagnostics(fragmentResult) +
                            "; partial DXIL outputs were discarded");
    diagnostics.warning(
        "directx.source-package-only",
        "kept HLSL graphics source package; native DirectX graphics pipeline "
        "package emission remains planned until dxc accepts shader profile(s): " +
            profileSummary + "; planned native binary artifact: " +
            packageRelativeNativeBinary.generic_string());
    result.optimizationStatus = "not-run";
    result.success = !diagnostics.hasErrors();
    return result;
  }

  const HIRStage &stage = *singleComputeStage(module);
  const std::string profile = directxShaderProfile(module, stage);
  const std::string entryPoint = directxEntryPointName(stage);
  const std::vector<std::string> command =
      directxDxcCommand(*dxc, result.sourcePath, result.nativeBinaryPath,
                        profile, entryPoint, optimizationLevel);
  const std::string commandProfile = directxDxcCommandProfile(
      profile, entryPoint, packageRelativeNativeBinary, packageRelativeSource,
      optimizationLevel);
  const ProcessCaptureResult dxcResult = runProcessCapture(command);
  if (dxcResult.started && dxcResult.exitCode == 0 &&
      std::filesystem::exists(result.nativeBinaryPath)) {
    diagnostics.note("directx.dxil-emitted",
                     "compiled HLSL source to DXIL with dxc; shader "
                     "profile(s): " +
                         profileSummary +
                         "; optimization profile: " + optimizationEvidence +
                         "; command profile: " + commandProfile);
    result.nativeBinaryProduced = true;
    result.nativeBinaryStatus = "emitted";
    result.optimizationStatus = "applied";
    result.success = !diagnostics.hasErrors();
    return result;
  }

  diagnostics.warning("directx.dxc-failed",
                      "dxc was found but failed to emit DXIL for generated "
                      "HLSL source with shader profile(s): " + profileSummary +
                          "; exit status: " +
                          directxDxcExitStatus(dxcResult) +
                          "; optimization profile: " + optimizationEvidence +
                          "; command profile: " + commandProfile +
                          "; dxc diagnostics: " +
                          directxDxcDiagnostics(dxcResult) +
                          "; partial DXIL output was discarded");
  std::filesystem::remove(result.nativeBinaryPath, error);
  diagnostics.warning("directx.source-package-only",
                      "kept HLSL source package; native DXIL package emission "
                      "remains planned until dxc accepts shader profile(s): " +
                          profileSummary + "; planned native binary artifact: " +
                          packageRelativeNativeBinary.generic_string());
  result.optimizationStatus = "not-run";
  result.success = !diagnostics.hasErrors();
  return result;
}

DirectXSourcePackageResult
buildDirectXSourcePackage(const HIRModule &module,
                          const std::filesystem::path &packageDir,
                          DiagnosticEngine &diagnostics,
                          OptimizationLevel optimizationLevel) {
  const std::optional<TargetLegalizationResourceBindingFacts> resourceBindings =
      directxLegalizedResourceBindingsForEmission(module);
  return buildDirectXSourcePackage(
      module, packageDir, diagnostics,
      resourceBindings.has_value() ? &*resourceBindings : nullptr,
      optimizationLevel);
}

DirectXSourcePackageResult buildDirectXSourcePackage(
    const HIRModule &module, const std::filesystem::path &packageDir,
    DiagnosticEngine &diagnostics,
    const TargetLegalizationResourceBindingFacts &resourceBindings,
    OptimizationLevel optimizationLevel) {
  return buildDirectXSourcePackage(module, packageDir, diagnostics,
                                   &resourceBindings, optimizationLevel);
}

} // namespace crossgl
