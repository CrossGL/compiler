#include "crossgl/Backend/VulkanBackend.h"

#include "crossgl/Backend/BackendExpressions.h"
#include "crossgl/Backend/BackendPlan.h"
#include "crossgl/Backend/BackendHIR.h"
#include "crossgl/Backend/ResourceArrays.h"
#include "crossgl/Backend/SPIRVModule.h"
#include "crossgl/Backend/TargetLegalization.h"
#include "crossgl/Backend/TextureCompare.h"
#include "crossgl/Backend/Toolchain.h"
#include "crossgl/Driver/StorageCapabilities.h"
#include "crossgl/Driver/StorageLayout.h"
#include "crossgl/HIR/Intrinsics.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <optional>
#include <set>
#include <sstream>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace crossgl {
namespace {

constexpr std::string_view kRawStatementBackendInputDiagnostic =
    "opt.hir-raw-statement-backend-input";

using PrototypeTextureOffset = std::array<int, 2>;

const std::unordered_set<std::string> kEmptyStringSet;

enum class VulkanStorageImageAccessDecoration {
  None,
  NonWritable,
  NonReadable,
};

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
      "Vulkan prototype backend input cannot contain HIR raw statements; "
      "lower them to structured HIR before backend emission");
  return true;
}

template <typename Resource>
VulkanStorageImageAccessDecoration
vulkanStorageImageAccessDecoration(const Resource &resource) {
  if constexpr (requires { resource.storageImageAccess; }) {
    if (resource.kind != HIRResourceKind::StorageImage) {
      return VulkanStorageImageAccessDecoration::None;
    }

    // HIRStorageImageAccess is provided by the shared frontend/HIR patch as
    // ReadWrite, ReadOnly, WriteOnly in that order.
    switch (static_cast<int>(resource.storageImageAccess)) {
    case 1:
      return VulkanStorageImageAccessDecoration::NonWritable;
    case 2:
      return VulkanStorageImageAccessDecoration::NonReadable;
    default:
      break;
    }
  }
  return VulkanStorageImageAccessDecoration::None;
}

std::string_view
vulkanStorageImageAccessDecorationName(
    VulkanStorageImageAccessDecoration decoration) {
  switch (decoration) {
  case VulkanStorageImageAccessDecoration::NonWritable:
    return "NonWritable";
  case VulkanStorageImageAccessDecoration::NonReadable:
    return "NonReadable";
  case VulkanStorageImageAccessDecoration::None:
    break;
  }
  return "";
}

std::string_view vulkanStorageImageAccessName(
    VulkanStorageImageAccessDecoration decoration) {
  switch (decoration) {
  case VulkanStorageImageAccessDecoration::NonWritable:
    return "read_only";
  case VulkanStorageImageAccessDecoration::NonReadable:
    return "write_only";
  case VulkanStorageImageAccessDecoration::None:
    break;
  }
  return "";
}

std::string textureDimension(std::string_view name) {
  if (name == "sampler3D" || name == "isampler3D" ||
      name == "usampler3D" || name == "texture3D") {
    return "3D";
  }
  if (name == "samplerCube" || name == "samplerCubeArray" ||
      name == "samplerCubeShadow" || name == "samplerCubeArrayShadow" ||
      name == "isamplerCube" || name == "isamplerCubeArray" ||
      name == "usamplerCube" || name == "usamplerCubeArray" ||
      name == "textureCube" || name == "textureCubeArray") {
    return "Cube";
  }
  return "2D";
}

bool isArrayTextureType(std::string_view name) {
  return name == "sampler2DArray" || name == "sampler2DArrayShadow" ||
         name == "isampler2DArray" || name == "usampler2DArray" ||
         name == "texture2DArray" || name == "samplerCubeArray" ||
         name == "samplerCubeArrayShadow" || name == "isamplerCubeArray" ||
         name == "usamplerCubeArray" || name == "textureCubeArray" ||
         name == "image2DArray" || name == "iimage2DArray" ||
         name == "uimage2DArray";
}

std::string textureIRDimension(std::string_view name) {
  const std::string dimension = textureDimension(name);
  return isArrayTextureType(name) ? dimension + "Array" : dimension;
}

bool isComparisonTextureType(std::string_view name) {
  return name == "sampler2DShadow" || name == "sampler2DArrayShadow" ||
         name == "samplerCubeShadow" || name == "samplerCubeArrayShadow";
}

bool isManualCompareOffsetTextureType(std::string_view name) {
  return name == "sampler2DShadow" || name == "sampler2DArrayShadow";
}

bool isIntegerLiteralText(std::string_view text) {
  if (text.empty()) {
    return false;
  }
  std::size_t index = 0;
  if (text[index] == '+' || text[index] == '-') {
    ++index;
  }
  if (index == text.size()) {
    return false;
  }
  for (; index < text.size(); ++index) {
    if (text[index] < '0' || text[index] > '9') {
      return false;
    }
  }
  return true;
}

std::optional<int> staticIntegerOffsetComponent(
    const HIRExpression &expression) {
  if (expression.kind == HIRExpressionKind::Group &&
      !expression.children.empty()) {
    return staticIntegerOffsetComponent(expression.children.front());
  }
  if (expression.kind == HIRExpressionKind::Unary &&
      (expression.value == "-" || expression.value == "+") &&
      expression.children.size() == 1) {
    const std::optional<int> child =
        staticIntegerOffsetComponent(expression.children.front());
    if (!child.has_value()) {
      return std::nullopt;
    }
    return expression.value == "-" ? -*child : *child;
  }
  if (expression.kind != HIRExpressionKind::Literal ||
      expression.type.name != "int" || expression.type.arraySize.has_value() ||
      !isIntegerLiteralText(expression.value)) {
    return std::nullopt;
  }
  try {
    return std::stoi(expression.value);
  } catch (...) {
    return std::nullopt;
  }
}

std::optional<PrototypeTextureOffset>
staticIvec2TextureOffset(const HIRExpression &expression) {
  if (expression.type.name != "ivec2" || expression.type.arraySize.has_value()) {
    return std::nullopt;
  }
  if (expression.kind == HIRExpressionKind::Group &&
      !expression.children.empty()) {
    return staticIvec2TextureOffset(expression.children.front());
  }
  if (expression.kind != HIRExpressionKind::Constructor ||
      expression.value != "ivec2" || expression.children.size() != 2) {
    return std::nullopt;
  }
  const std::optional<int> x =
      staticIntegerOffsetComponent(expression.children[0]);
  const std::optional<int> y =
      staticIntegerOffsetComponent(expression.children[1]);
  if (!x.has_value() || !y.has_value()) {
    return std::nullopt;
  }
  return PrototypeTextureOffset{*x, *y};
}

std::string textureSampledScalarTypeName(std::string_view name) {
  if (name.rfind("isampler", 0) == 0 || name.rfind("iimage", 0) == 0) {
    return "int";
  }
  if (name.rfind("usampler", 0) == 0 || name.rfind("uimage", 0) == 0) {
    return "uint";
  }
  return "float";
}

std::string storageImageSPIRVFormatNameFromFormat(std::string_view format) {
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
  return "Unknown";
}

HIRType textureSampleResultType(const HIRType &textureType) {
  if (isComparisonTextureType(textureType.name)) {
    return HIRType{"float", std::nullopt};
  }
  const std::string component =
      textureSampledScalarTypeName(textureType.name);
  if (component == "int") {
    return HIRType{"ivec4", std::nullopt};
  }
  if (component == "uint") {
    return HIRType{"uvec4", std::nullopt};
  }
  return HIRType{"vec4", std::nullopt};
}

std::string spirvExecutionModel(std::string_view stage) {
  if (stage == "compute") {
    return "GLCompute";
  }
  if (stage == "vertex") {
    return "Vertex";
  }
  if (stage == "fragment") {
    return "Fragment";
  }
  return "Unknown";
}

std::optional<HIRType> prototypeAtomicStorageValueType(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return std::nullopt;
  }

  const std::string scalarName =
      stripPointerSuffix(stripTypeQualifier(type.name));
  if (scalarName == "atomic<int>") {
    return HIRType{"int", std::nullopt, type.location};
  }
  if (scalarName == "atomic<uint>") {
    return HIRType{"uint", std::nullopt, type.location};
  }
  return std::nullopt;
}

std::optional<HIRType> prototypePlainAtomicValueType(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return std::nullopt;
  }
  const std::string scalarName =
      stripPointerSuffix(stripTypeQualifier(type.name));
  if (scalarName == "int") {
    return HIRType{"int", std::nullopt, type.location};
  }
  if (scalarName == "uint") {
    return HIRType{"uint", std::nullopt, type.location};
  }
  return std::nullopt;
}

std::optional<HIRType> prototypeAtomicStoredValueType(const HIRType &type,
                                                      bool allowPlainInteger) {
  if (const std::optional<HIRType> valueType =
          prototypeAtomicStorageValueType(type)) {
    return valueType;
  }
  if (allowPlainInteger) {
    return prototypePlainAtomicValueType(type);
  }
  return std::nullopt;
}

bool isPrototypeAtomicIntegerType(const HIRType &type) {
  return prototypeAtomicStorageValueType(type).has_value();
}

HIRType prototypeAtomicStorageBackingType(HIRType type) {
  HIRType scalar = type;
  scalar.arraySize.reset();
  if (const std::optional<HIRType> valueType =
          prototypeAtomicStorageValueType(scalar)) {
    type.name = valueType->name;
  }
  return type;
}

std::string spirvType(const HIRType &type) {
  if (type.arraySize.has_value()) {
    if (type.arraySize->empty()) {
      return "!spirv.runtime_array<" +
             spirvType(HIRType{type.name, std::nullopt}) + ">";
    }
    return "!spirv.array<" + spirvType(HIRType{type.name, std::nullopt}) + ", " +
           *type.arraySize + ">";
  }
  if (const std::optional<HIRType> atomicValueType =
          prototypeAtomicStorageValueType(type)) {
    return spirvType(*atomicValueType);
  }
  if (type.name == "void") {
    return "!spirv.void";
  }
  if (type.name == "bool") {
    return "!spirv.bool";
  }
  if (type.name == "int") {
    return "!spirv.i32";
  }
  if (type.name == "uint") {
    return "!spirv.u32";
  }
  if (type.name == "float") {
    return "!spirv.f32";
  }
  if (type.name == "vec2") {
    return "!spirv.vec<2xf32>";
  }
  if (type.name == "vec3") {
    return "!spirv.vec<3xf32>";
  }
  if (type.name == "vec4") {
    return "!spirv.vec<4xf32>";
  }
  if (type.name == "ivec2") {
    return "!spirv.vec<2xi32>";
  }
  if (type.name == "ivec3") {
    return "!spirv.vec<3xi32>";
  }
  if (type.name == "ivec4") {
    return "!spirv.vec<4xi32>";
  }
  if (type.name == "uvec2") {
    return "!spirv.vec<2xu32>";
  }
  if (type.name == "uvec3") {
    return "!spirv.vec<3xu32>";
  }
  if (type.name == "uvec4") {
    return "!spirv.vec<4xu32>";
  }
  return "!spirv.struct<" + type.name + ">";
}

std::string spirvArrayType(std::string element, const HIRType &type) {
  if (type.arraySize.has_value()) {
    if (type.arraySize->empty()) {
      return "!spirv.runtime_array<" + std::move(element) + ">";
    }
    return "!spirv.array<" + std::move(element) + ", " + *type.arraySize + ">";
  }
  return element;
}

std::string spirvGlobalType(const HIRResource &resource) {
  switch (resource.kind) {
  case HIRResourceKind::Uniform:
    return "!spirv.ptr<" + spirvType(resource.type) + ", Uniform>";
  case HIRResourceKind::Buffer: {
    const HIRType element =
        prototypeAtomicStorageBackingType(bufferElementType(resource.type));
    return "!spirv.ptr<" +
           spirvArrayType("!spirv.runtime_array<" + spirvType(element) + ">",
                          resource.type) +
           ", StorageBuffer>";
  }
  case HIRResourceKind::Texture: {
    const HIRType textureElement = arrayElementType(resource.type);
    const std::string sampledScalar =
        isComparisonTextureType(textureElement.name)
            ? "depth_compare"
            : textureSampledScalarTypeName(textureElement.name);
    const std::string spirvScalar =
        sampledScalar == "depth_compare"
            ? "depth_compare"
            : sampledScalar == "int" ? "i32"
            : sampledScalar == "uint" ? "u32"
                                      : "f32";
    const std::string imageType =
        "!spirv.image<" + spirvScalar + ", " +
        textureIRDimension(textureElement.name) + ", sampled>";
    return "!spirv.ptr<" + spirvArrayType(imageType, resource.type) +
           ", UniformConstant>";
  }
  case HIRResourceKind::StorageImage: {
    const HIRType imageElement = arrayElementType(resource.type);
    const std::string sampledScalar =
        textureSampledScalarTypeName(imageElement.name);
    const std::string spirvScalar =
        sampledScalar == "int" ? "i32"
        : sampledScalar == "uint" ? "u32"
                                  : "f32";
    const std::string imageType =
        "!spirv.image<" + spirvScalar + ", " +
        textureIRDimension(imageElement.name) + ", storage, " +
        storageImageSPIRVFormatNameFromFormat(
            resolvedStorageImageFormatName(resource)) +
        ">";
    return "!spirv.ptr<" + spirvArrayType(imageType, resource.type) +
           ", UniformConstant>";
  }
  case HIRResourceKind::Sampler:
    return "!spirv.ptr<" +
           spirvArrayType("!spirv.sampler", resource.type) + ", UniformConstant>";
  case HIRResourceKind::Shared:
    return "!spirv.ptr<" +
           spirvType(prototypeAtomicStorageBackingType(resource.type)) +
           ", Workgroup>";
  case HIRResourceKind::Value:
    break;
  }
  return "!spirv.unknown";
}

std::string renderVulkanResourceLine(const HIRResource &resource) {
  std::ostringstream out;
  if (vulkanResourceUsesDescriptor(resource.kind)) {
    const VulkanStorageImageAccessDecoration accessDecoration =
        vulkanStorageImageAccessDecoration(resource);
    out << "      vulkan.descriptor @" << resource.name << " set "
        << resource.set << " binding " << resource.binding
        << " descriptor_type \"" << vulkanDescriptorType(resource.kind) << "\""
        << " storage_class \"" << vulkanResourceStorageClass(resource.kind) << "\""
        << " binding_class \"" << vulkanResourceBindingClass(resource.kind) << "\""
        << " spirv_type \"" << vulkanResourceSPIRVType(resource) << "\"";
    if (resource.type.arraySize.has_value()) {
      out << " descriptor_array_size \"" << *resource.type.arraySize << "\"";
    }
    if (accessDecoration != VulkanStorageImageAccessDecoration::None) {
      out << " storage_image_access \""
          << vulkanStorageImageAccessName(accessDecoration) << "\""
          << " spirv_access_decoration \""
          << vulkanStorageImageAccessDecorationName(accessDecoration) << "\"";
    }
    out << "\n";
    return out.str();
  }

  if (resource.kind == HIRResourceKind::Shared) {
    out << "      vulkan.workgroup @" << resource.name
        << " storage_class \"" << vulkanResourceStorageClass(resource.kind) << "\""
        << " spirv_type \"" << vulkanResourceSPIRVType(resource) << "\"\n";
  }
  return out.str();
}

void renderSpirvResourceSkeleton(std::ostringstream &out,
                                 const HIRResource &resource) {
  if (vulkanResourceUsesDescriptor(resource.kind)) {
    out << "    spirv.Decorate @" << resource.name << " DescriptorSet "
        << resource.set << "\n";
    out << "    spirv.Decorate @" << resource.name << " Binding "
        << resource.binding << "\n";
    const VulkanStorageImageAccessDecoration accessDecoration =
        vulkanStorageImageAccessDecoration(resource);
    if (accessDecoration != VulkanStorageImageAccessDecoration::None) {
      out << "    spirv.Decorate @" << resource.name << " "
          << vulkanStorageImageAccessDecorationName(accessDecoration) << "\n";
    }
  }
  out << "    spirv.GlobalVariable @" << resource.name << " : "
      << spirvGlobalType(resource) << " attributes {storage_class = \""
      << vulkanResourceStorageClass(resource.kind) << "\"";
  if (vulkanResourceUsesDescriptor(resource.kind)) {
    out << ", descriptor_type = \"" << vulkanDescriptorType(resource.kind) << "\"";
    if (resource.type.arraySize.has_value()) {
      out << ", descriptor_array_size = \"" << *resource.type.arraySize << "\"";
    }
  }
  out << "}\n";
}

void renderSpirvFunctionSkeleton(std::ostringstream &out, const HIRStage &stage) {
  const std::string entryPoint = stage.stage + "_" + stage.entryPointName;
  out << "    spirv.func @" << entryPoint << "() -> !spirv.void "
      << "attributes {crossgl.stage = \"" << stage.stage << "\"} {\n"
      << "      spirv.Return\n"
      << "    }\n";
}

void renderSpirvModuleSkeleton(std::ostringstream &out, const HIRModule &module) {
  out << "spirv.module @" << module.name
      << " attributes {addressing_model = \"Logical\", memory_model = \"GLSL450\", "
      << "target_env = \"" << kVulkanNativeTargetEnv << "\"} {\n";
  out << "  spirv.Capability Shader\n";
  out << "  spirv.MemoryModel Logical GLSL450\n";
  for (const HIRStage &stage : module.stages) {
    const std::string entryPoint = stage.stage + "_" + stage.entryPointName;
    out << "  spirv.EntryPoint " << spirvExecutionModel(stage.stage) << " @"
        << entryPoint << " \"" << stage.entryPointName << "\"\n";
    if (stage.stage == "compute" && stage.workgroupSize.has_value()) {
      out << "  spirv.ExecutionMode @" << entryPoint << " LocalSize "
          << stage.workgroupSize->x << " " << stage.workgroupSize->y << " "
          << stage.workgroupSize->z << "\n";
    }
  }
  for (const HIRStage &stage : module.stages) {
    out << "  spirv.resource_scope @" << stage.stage << " {\n";
    for (const HIRResource &resource : stage.resources) {
      renderSpirvResourceSkeleton(out, resource);
    }
    renderSpirvFunctionSkeleton(out, stage);
    out << "  }\n";
  }
  out << "}\n";
}

const HIRStage *prototypeComputeStage(const HIRModule &module) {
  const HIRStage *candidate = nullptr;
  for (const HIRStage &stage : module.stages) {
    if (stage.stage != "compute") {
      return nullptr;
    }
    if (candidate != nullptr) {
      return nullptr;
    }
    candidate = &stage;
  }
  return candidate;
}

std::string entryPointName(const HIRStage &stage) {
  return stage.stage + "_" + stage.entryPointName;
}

bool isPrototypeScalarType(const HIRType &type) {
  return !type.arraySize.has_value() &&
         (type.name == "int" || type.name == "uint" ||
          type.name == "float" || type.name == "bool");
}

std::optional<std::size_t> prototypeVectorWidth(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return std::nullopt;
  }
  if (type.name == "vec2" || type.name == "ivec2" || type.name == "uvec2") {
    return 2;
  }
  if (type.name == "vec3" || type.name == "ivec3" || type.name == "uvec3") {
    return 3;
  }
  if (type.name == "vec4" || type.name == "ivec4" || type.name == "uvec4") {
    return 4;
  }
  return std::nullopt;
}

HIRType prototypeVectorComponentType(const HIRType &type) {
  if (type.name.rfind("ivec", 0) == 0) {
    return HIRType{"int", std::nullopt};
  }
  if (type.name.rfind("uvec", 0) == 0) {
    return HIRType{"uint", std::nullopt};
  }
  return HIRType{"float", std::nullopt};
}

bool isPrototypeVectorType(const HIRType &type) {
  return prototypeVectorWidth(type).has_value();
}

std::optional<std::size_t> prototypeMatrixDimension(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return std::nullopt;
  }
  if (type.name == "mat2" || type.name == "mat2x2") {
    return std::size_t{2};
  }
  if (type.name == "mat3" || type.name == "mat3x3") {
    return std::size_t{3};
  }
  if (type.name == "mat4" || type.name == "mat4x4") {
    return std::size_t{4};
  }
  return std::nullopt;
}

bool isPrototypeMatrixType(const HIRType &type) {
  return prototypeMatrixDimension(type).has_value();
}

HIRType prototypeMatrixColumnType(const HIRType &type) {
  const std::optional<std::size_t> dimension = prototypeMatrixDimension(type);
  if (dimension == std::size_t{2}) {
    return HIRType{"vec2", std::nullopt};
  }
  if (dimension == std::size_t{3}) {
    return HIRType{"vec3", std::nullopt};
  }
  return HIRType{"vec4", std::nullopt};
}

bool isPrototypeLocalType(const HIRType &type) {
  return isPrototypeScalarType(type) || isPrototypeVectorType(type) ||
         isPrototypeMatrixType(type);
}

struct PrototypeComputeBuiltinInfo {
  std::string_view name;
  std::string_view spirvBuiltin;
};

const PrototypeComputeBuiltinInfo *
prototypeComputeBuiltinInfo(std::string_view name) {
  static constexpr PrototypeComputeBuiltinInfo builtins[] = {
      {"gl_GlobalInvocationID", "GlobalInvocationId"},
      {"gl_LocalInvocationID", "LocalInvocationId"},
      {"gl_WorkGroupID", "WorkgroupId"},
  };
  for (const PrototypeComputeBuiltinInfo &builtin : builtins) {
    if (builtin.name == name) {
      return &builtin;
    }
  }
  return nullptr;
}

bool isPrototypeComputeBuiltinIdentifier(std::string_view name) {
  return prototypeComputeBuiltinInfo(name) != nullptr;
}

HIRType prototypeComputeBuiltinType() {
  return HIRType{"uvec3", std::nullopt};
}

bool isPrototypeWorkgroupBarrierName(std::string_view name) {
  return name == "workgroupBarrier" || name == "barrier";
}

bool isPrototypeWorkgroupBarrierCall(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::Call &&
         isPrototypeWorkgroupBarrierName(expression.value);
}

bool isPrototypeImageLoadCall(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::Call &&
         expression.value == "imageLoad";
}

bool isPrototypeImageStoreCall(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::Call &&
         expression.value == "imageStore";
}

enum class PrototypeAtomicIntegerOp {
  Add,
  Exchange,
  And,
  Or,
  Xor,
  Min,
  Max,
};

std::optional<PrototypeAtomicIntegerOp>
prototypeAtomicIntegerOpForCall(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Call) {
    return std::nullopt;
  }
  if (expression.value == "atomicAdd") {
    return PrototypeAtomicIntegerOp::Add;
  }
  if (expression.value == "atomicExchange") {
    return PrototypeAtomicIntegerOp::Exchange;
  }
  if (expression.value == "atomicAnd") {
    return PrototypeAtomicIntegerOp::And;
  }
  if (expression.value == "atomicOr") {
    return PrototypeAtomicIntegerOp::Or;
  }
  if (expression.value == "atomicXor") {
    return PrototypeAtomicIntegerOp::Xor;
  }
  if (expression.value == "atomicMin") {
    return PrototypeAtomicIntegerOp::Min;
  }
  if (expression.value == "atomicMax") {
    return PrototypeAtomicIntegerOp::Max;
  }
  return std::nullopt;
}

bool isPrototypeAtomicIntegerCall(const HIRExpression &expression) {
  return prototypeAtomicIntegerOpForCall(expression).has_value();
}

std::optional<PrototypeAtomicIntegerOp>
prototypeStorageImageAtomicOpForCall(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Call) {
    return std::nullopt;
  }
  if (expression.value == "imageAtomicAdd") {
    return PrototypeAtomicIntegerOp::Add;
  }
  if (expression.value == "imageAtomicExchange") {
    return PrototypeAtomicIntegerOp::Exchange;
  }
  if (expression.value == "imageAtomicMin") {
    return PrototypeAtomicIntegerOp::Min;
  }
  if (expression.value == "imageAtomicMax") {
    return PrototypeAtomicIntegerOp::Max;
  }
  if (expression.value == "imageAtomicAnd") {
    return PrototypeAtomicIntegerOp::And;
  }
  if (expression.value == "imageAtomicOr") {
    return PrototypeAtomicIntegerOp::Or;
  }
  if (expression.value == "imageAtomicXor") {
    return PrototypeAtomicIntegerOp::Xor;
  }
  return std::nullopt;
}

bool isPrototypeStorageImageAtomicCall(const HIRExpression &expression) {
  return prototypeStorageImageAtomicOpForCall(expression).has_value();
}

bool prototypeWorkgroupBarrierCallSupported(const HIRExpression &expression,
                                            DiagnosticEngine &diagnostics) {
  if (!isPrototypeWorkgroupBarrierCall(expression)) {
    return false;
  }
  if (!expression.children.empty()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype workgroup barrier calls require zero "
                      "arguments");
    return false;
  }
  if (!expression.type.name.empty() && expression.type.name != "void") {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype workgroup barrier calls must not "
                      "produce a value");
    return false;
  }
  return true;
}

bool isPrototypeArithmeticType(const HIRType &type) {
  return !type.arraySize.has_value() &&
         (type.name == "int" || type.name == "uint" || type.name == "float" ||
          isPrototypeVectorType(type));
}

bool isPrototypeArithmeticOperator(std::string_view op) {
  return op == "+" || op == "-" || op == "*" || op == "/";
}

bool isPrototypeComparisonOperator(std::string_view op) {
  return op == "<" || op == "<=" || op == ">" || op == ">=" ||
         op == "==" || op == "!=";
}

bool isPrototypeExplicitLodTextureSample(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::TextureSample &&
         expression.value == "textureLod";
}

bool isPrototypeImplicitSamplerTextureSample(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::TextureSample &&
         (expression.value == "sample" || expression.value == "texture") &&
         expression.children.size() == 3;
}

bool isPrototypeExplicitLodTextureCompare(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::TextureCompare &&
         expression.value == "textureCompareLod";
}

std::string prototypeTextureCoordinateType(const HIRType &textureType) {
  const std::string dimension = textureDimension(textureType.name);
  if (dimension == "2D" && !isArrayTextureType(textureType.name)) {
    return "vec2";
  }
  if (dimension == "2D" && isArrayTextureType(textureType.name)) {
    return "vec3";
  }
  if (dimension == "3D" || (dimension == "Cube" &&
                            !isArrayTextureType(textureType.name))) {
    return "vec3";
  }
  if (dimension == "Cube" && isArrayTextureType(textureType.name)) {
    return "vec4";
  }
  return "";
}

HIRType prototypeBufferElementType(const HIRResource &resource) {
  return bufferElementType(resource.type);
}

bool isModuleStructType(const HIRModule &module, const HIRType &type) {
  for (const HIRStruct &structure : module.structs) {
    if (structure.name == type.name) {
      return true;
    }
  }
  return false;
}

bool isPrototypeStructStorageBufferResource(const HIRModule &module,
                                            const HIRResource &resource) {
  return resource.kind == HIRResourceKind::Buffer &&
         isModuleStructType(module, prototypeBufferElementType(resource));
}

HIRType prototypeUniformBufferElementType(const HIRResource &resource) {
  if (resource.type.arraySize.has_value()) {
    return arrayElementType(resource.type);
  }
  return resource.type;
}

bool isPrototypeStructUniformBufferResource(const HIRModule &module,
                                            const HIRResource &resource) {
  return resource.kind == HIRResourceKind::Uniform &&
         isModuleStructType(module, prototypeUniformBufferElementType(resource));
}

bool isPrototypeStorageBufferResource(const HIRResource &resource) {
  if (resource.kind != HIRResourceKind::Buffer) {
    return false;
  }
  const HIRType elementType = prototypeBufferElementType(resource);
  return isPrototypeArithmeticType(elementType) ||
         isPrototypeAtomicIntegerType(elementType);
}

bool isPrototypeWorkgroupSharedResource(const HIRResource &resource) {
  if (resource.kind != HIRResourceKind::Shared) {
    return false;
  }
  const HIRType elementType = arrayElementType(resource.type);
  return isPrototypeArithmeticType(elementType) ||
         isPrototypeAtomicIntegerType(elementType);
}

bool isPrototypeUniformConstantDescriptorResource(const HIRResource &resource) {
  return resource.kind == HIRResourceKind::Texture ||
         resource.kind == HIRResourceKind::StorageImage ||
         resource.kind == HIRResourceKind::Sampler;
}

std::span<const HIRResourceKind> vulkanRuntimeTextureSamplerDescriptorKinds() {
  static constexpr std::array<HIRResourceKind, 2> kinds = {
      HIRResourceKind::Texture, HIRResourceKind::Sampler};
  return kinds;
}

std::span<const HIRResourceKind>
vulkanRuntimeDescriptorBindingClassKinds(HIRResourceKind kind) {
  static constexpr std::array<HIRResourceKind, 1> textureKinds = {
      HIRResourceKind::Texture};
  static constexpr std::array<HIRResourceKind, 1> samplerKinds = {
      HIRResourceKind::Sampler};

  switch (kind) {
  case HIRResourceKind::Texture:
    return textureKinds;
  case HIRResourceKind::Sampler:
    return samplerKinds;
  case HIRResourceKind::Uniform:
  case HIRResourceKind::Buffer:
  case HIRResourceKind::StorageImage:
  case HIRResourceKind::Shared:
  case HIRResourceKind::Value:
    break;
  }
  return {};
}

bool vulkanRuntimeTextureSamplerDescriptorArraySupported(
    const HIRModule &module, const HIRResource &resource) {
  if (!isRuntimeDescriptorArray(resource)) {
    return true;
  }
  if (resource.kind != HIRResourceKind::Texture &&
      resource.kind != HIRResourceKind::Sampler) {
    return false;
  }
  return runtimeDescriptorArraySupportedByPolicy(
      module, resource,
      RuntimeDescriptorArrayPolicy::AllowSingleUnboundedDescriptorArray,
      vulkanRuntimeDescriptorBindingClassKinds(resource.kind));
}

std::string vulkanRuntimeDescriptorArrayUnsupportedMessage(
    const HIRModule &module, const HIRResource &resource) {
  const std::span<const HIRResourceKind> bindingClassKinds =
      vulkanRuntimeDescriptorBindingClassKinds(resource.kind);
  const std::set<std::string> unsupportedArrays =
      bindingClassKinds.empty()
          ? runtimeDescriptorArrayLabels(
                module, vulkanRuntimeTextureSamplerDescriptorKinds())
          : runtimeDescriptorArrayLabels(module, bindingClassKinds);
  return "Vulkan prototype descriptor lowering requires fixed-size descriptor "
         "arrays when multiple unbounded texture/sampler arrays share a "
         "Vulkan descriptor binding class or the descriptor shape is "
         "ambiguous; unsupported unsized/runtime resource array(s): " +
         joinNames(unsupportedArrays) +
         "; use a fixed descriptor array size or keep only one unbounded "
         "descriptor array per Vulkan descriptor binding class";
}

bool isPrototypeStructStorageBufferResourceForSupport(
    const HIRResource &resource) {
  return resource.kind == HIRResourceKind::Buffer &&
         !isPrototypeArithmeticType(prototypeBufferElementType(resource));
}

bool isPrototypeStructUniformBufferResourceForSupport(
    const HIRResource &resource,
    const std::unordered_map<std::string, const HIRStruct *> &structs) {
  if (resource.kind != HIRResourceKind::Uniform) {
    return false;
  }
  const HIRType elementType = prototypeUniformBufferElementType(resource);
  return structs.find(elementType.name) != structs.end();
}

bool samePrototypeType(const HIRType &left, const HIRType &right) {
  return left.name == right.name && left.arraySize == right.arraySize;
}

std::optional<std::size_t>
prototypeVectorConstructorConstituentWidth(const HIRType &type,
                                           const HIRType &componentType) {
  if (samePrototypeType(type, componentType)) {
    return 1;
  }
  const std::optional<std::size_t> width = prototypeVectorWidth(type);
  if (!width.has_value() ||
      !samePrototypeType(prototypeVectorComponentType(type), componentType)) {
    return std::nullopt;
  }
  return width;
}

bool prototypeVectorConstructorSupported(const HIRExpression &expression,
                                         DiagnosticEngine &diagnostics) {
  const std::optional<std::size_t> width =
      prototypeVectorWidth(expression.type);
  if (!width.has_value() || expression.value != expression.type.name ||
      expression.children.empty()) {
    diagnostics.error(
        "vulkan.prototype-unsupported-expression",
        "Vulkan prototype vector constructors require a vec2/vec3/vec4, "
        "ivec2/ivec3/ivec4, or uvec2/uvec3/uvec4 constructor name matching "
        "the result type");
    return false;
  }

  if (expression.children.size() == 1 &&
      samePrototypeType(expression.children.front().type, expression.type)) {
    return true;
  }

  const HIRType componentType = prototypeVectorComponentType(expression.type);
  std::size_t constituentWidth = 0;
  for (const HIRExpression &child : expression.children) {
    const std::optional<std::size_t> childWidth =
        prototypeVectorConstructorConstituentWidth(child.type, componentType);
    if (!childWidth.has_value()) {
      diagnostics.error(
          "vulkan.prototype-unsupported-expression",
          "Vulkan prototype vector constructors require scalar/vector "
          "constituents matching the result component type");
      return false;
    }
    constituentWidth += *childWidth;
  }

  if (expression.children.size() == 1 && constituentWidth == 1) {
    return true;
  }
  if (constituentWidth != *width) {
    diagnostics.error(
        "vulkan.prototype-unsupported-expression",
        "Vulkan prototype vector constructors require one scalar splat value "
        "or constituents matching the result vector width");
    return false;
  }
  return true;
}

bool isPrototypeNumericScalarType(const HIRType &type) {
  return !type.arraySize.has_value() &&
         (type.name == "float" || type.name == "int" ||
          type.name == "uint");
}

std::optional<std::size_t>
prototypeMatrixConstructorConstituentWidth(const HIRType &type) {
  if (isPrototypeNumericScalarType(type)) {
    return std::size_t{1};
  }
  if (!isPrototypeVectorType(type) ||
      !isPrototypeNumericScalarType(prototypeVectorComponentType(type))) {
    return std::nullopt;
  }
  return prototypeVectorWidth(type);
}

bool prototypeMatrixConstructorSupported(const HIRExpression &expression,
                                         DiagnosticEngine &diagnostics) {
  const std::optional<std::size_t> dimension =
      prototypeMatrixDimension(expression.type);
  if (!dimension.has_value() ||
      expression.value != baseTypeName(expression.type) ||
      expression.children.empty()) {
    diagnostics.error(
        "vulkan.prototype-unsupported-expression",
        "Vulkan prototype matrix constructors require a mat2/mat3/mat4 "
        "constructor name matching the result type");
    return false;
  }

  if (expression.children.size() == 1) {
    const HIRType &sourceType = expression.children.front().type;
    if (samePrototypeType(sourceType, expression.type) ||
        isPrototypeMatrixType(sourceType) ||
        isPrototypeNumericScalarType(sourceType)) {
      return true;
    }
  }

  std::size_t constituentWidth = 0;
  for (const HIRExpression &child : expression.children) {
    const std::optional<std::size_t> childWidth =
        prototypeMatrixConstructorConstituentWidth(child.type);
    if (!childWidth.has_value()) {
      diagnostics.error(
          "vulkan.prototype-unsupported-expression",
          "Vulkan prototype matrix constructors require numeric scalar/vector "
          "constituents or a single scalar/matrix operand");
      return false;
    }
    constituentWidth += *childWidth;
  }

  if (constituentWidth != (*dimension * *dimension)) {
    diagnostics.error(
        "vulkan.prototype-unsupported-expression",
        "Vulkan prototype matrix constructors require constituents matching "
        "the result matrix element count");
    return false;
  }
  return true;
}

bool isPrototypeFloatScalarType(const HIRType &type) {
  return type.name == "float" && !type.arraySize.has_value();
}

bool isPrototypeFloatVectorType(const HIRType &type) {
  return !type.arraySize.has_value() &&
         (type.name == "vec2" || type.name == "vec3" ||
          type.name == "vec4");
}

bool isPrototypeFloatMatrixVectorMultiplyOperandPair(
    const HIRType &matrixType, const HIRType &vectorType,
    const HIRType &resultType) {
  const std::optional<std::size_t> matrixDimension =
      prototypeMatrixDimension(matrixType);
  const std::optional<std::size_t> vectorWidth =
      prototypeVectorWidth(vectorType);
  return matrixDimension.has_value() && vectorWidth.has_value() &&
         *matrixDimension == *vectorWidth &&
         isPrototypeFloatVectorType(vectorType) &&
         samePrototypeType(vectorType, resultType);
}

bool isPrototypeFloatMatrixScalarMultiplyOperandPair(
    const HIRType &matrixType, const HIRType &scalarType,
    const HIRType &resultType) {
  return prototypeMatrixDimension(matrixType).has_value() &&
         isPrototypeFloatScalarType(scalarType) &&
         samePrototypeType(matrixType, resultType);
}

struct PrototypeMatrixMultiplyLowering {
  std::string_view opcode;
  bool swapOperands = false;
};

std::optional<PrototypeMatrixMultiplyLowering>
prototypeMatrixMultiplyLowering(const HIRType &leftType,
                                const HIRType &rightType,
                                const HIRType &resultType) {
  if (isPrototypeFloatMatrixVectorMultiplyOperandPair(leftType, rightType,
                                                      resultType)) {
    return PrototypeMatrixMultiplyLowering{"OpMatrixTimesVector", false};
  }
  if (isPrototypeFloatMatrixVectorMultiplyOperandPair(rightType, leftType,
                                                      resultType)) {
    return PrototypeMatrixMultiplyLowering{"OpVectorTimesMatrix", false};
  }
  if (isPrototypeFloatMatrixScalarMultiplyOperandPair(leftType, rightType,
                                                      resultType)) {
    return PrototypeMatrixMultiplyLowering{"OpMatrixTimesScalar", false};
  }
  if (isPrototypeFloatMatrixScalarMultiplyOperandPair(rightType, leftType,
                                                      resultType)) {
    return PrototypeMatrixMultiplyLowering{"OpMatrixTimesScalar", true};
  }
  if (prototypeMatrixDimension(leftType).has_value() &&
      samePrototypeType(leftType, rightType) &&
      samePrototypeType(leftType, resultType)) {
    return PrototypeMatrixMultiplyLowering{"OpMatrixTimesMatrix", false};
  }
  return std::nullopt;
}

bool isPrototypeFloatScalarOrVectorType(const HIRType &type) {
  return isPrototypeFloatScalarType(type) || isPrototypeFloatVectorType(type);
}

bool isPrototypeSignedIntegerScalarOrVectorType(const HIRType &type) {
  return !type.arraySize.has_value() &&
         (type.name == "int" || type.name == "ivec2" ||
          type.name == "ivec3" || type.name == "ivec4");
}

bool isPrototypeUnsignedIntegerScalarOrVectorType(const HIRType &type) {
  return !type.arraySize.has_value() &&
         (type.name == "uint" || type.name == "uvec2" ||
          type.name == "uvec3" || type.name == "uvec4");
}

bool isPrototypeFloatVectorScalarArithmetic(const HIRType &left,
                                            const HIRType &right,
                                            const HIRType &result) {
  if (isPrototypeFloatVectorType(left) && isPrototypeFloatScalarType(right)) {
    return samePrototypeType(left, result);
  }
  if (isPrototypeFloatScalarType(left) && isPrototypeFloatVectorType(right)) {
    return samePrototypeType(right, result);
  }
  return false;
}

std::string prototypeScalarConversionOpcode(const HIRType &source,
                                            const HIRType &target) {
  if (!isPrototypeNumericScalarType(source) ||
      !isPrototypeNumericScalarType(target)) {
    return "";
  }
  if (samePrototypeType(source, target)) {
    return "identity";
  }
  if (target.name == "float" && source.name == "int") {
    return "OpConvertSToF";
  }
  if (target.name == "float" && source.name == "uint") {
    return "OpConvertUToF";
  }
  if (target.name == "int" && source.name == "float") {
    return "OpConvertFToS";
  }
  if (target.name == "uint" && source.name == "float") {
    return "OpConvertFToU";
  }
  return "";
}

std::string prototypeTypeKey(const HIRType &type) {
  return formatType(type);
}

using PrototypeConstantMap = std::unordered_map<std::string, HIRConstant>;

StorageLayoutContext
prototypeStorageLayoutContext(const PrototypeConstantMap &constants) {
  StorageLayoutContext context;
  for (const auto &[name, constant] : constants) {
    (void)name;
    context.addConstant(constant);
  }
  return context;
}

std::optional<std::size_t>
prototypeArrayElementCount(const HIRType &type,
                           const StorageLayoutContext &layoutContext) {
  if (!type.arraySize.has_value() || type.arraySize->empty()) {
    return std::nullopt;
  }
  return storageArrayElementCount(type, layoutContext);
}

std::optional<std::size_t>
prototypeArrayElementCount(const HIRType &type,
                           const PrototypeConstantMap &constants) {
  if (!type.arraySize.has_value() || type.arraySize->empty()) {
    return std::nullopt;
  }
  const StorageLayoutContext layoutContext =
      prototypeStorageLayoutContext(constants);
  return prototypeArrayElementCount(type, layoutContext);
}

std::vector<std::string_view>
prototypeArrayDimensions(std::string_view arraySize) {
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

std::string joinPrototypeArrayDimensions(
    std::vector<std::string_view>::const_iterator begin,
    std::vector<std::string_view>::const_iterator end) {
  std::string joined;
  for (auto current = begin; current != end; ++current) {
    if (!joined.empty()) {
      joined += "][";
    }
    joined += *current;
  }
  return joined;
}

std::optional<std::size_t> prototypeArrayDimensionElementCount(
    std::string_view dimension, const PrototypeConstantMap &constants) {
  if (dimension.empty()) {
    return std::nullopt;
  }
  return prototypeArrayElementCount(
      HIRType{"float", std::string(dimension)}, constants);
}

std::optional<std::size_t> prototypeArrayDimensionElementCount(
    std::string_view dimension, const StorageLayoutContext &layoutContext) {
  if (dimension.empty()) {
    return std::nullopt;
  }
  return prototypeArrayElementCount(
      HIRType{"float", std::string(dimension)}, layoutContext);
}

std::optional<std::size_t>
prototypeArrayFirstDimensionElementCount(
    const HIRType &type, const PrototypeConstantMap &constants) {
  if (!type.arraySize.has_value() || type.arraySize->empty()) {
    return std::nullopt;
  }
  const std::vector<std::string_view> dimensions =
      prototypeArrayDimensions(*type.arraySize);
  if (dimensions.empty()) {
    return std::nullopt;
  }
  return prototypeArrayDimensionElementCount(dimensions.front(), constants);
}

HIRType prototypeArrayElementTypeOneDimension(HIRType type) {
  if (!type.arraySize.has_value()) {
    return type;
  }
  const std::vector<std::string_view> dimensions =
      prototypeArrayDimensions(*type.arraySize);
  if (dimensions.size() <= 1) {
    type.arraySize.reset();
    return type;
  }
  type.arraySize = joinPrototypeArrayDimensions(dimensions.begin() + 1,
                                                dimensions.end());
  return type;
}

HIRType prototypeArrayInnermostElementType(HIRType type) {
  type.arraySize.reset();
  return type;
}

std::optional<HIRType>
prototypeArrayTypeAfterIndexCount(HIRType type, std::size_t indexCount) {
  if (!type.arraySize.has_value()) {
    return indexCount == 0 ? std::optional<HIRType>{std::move(type)}
                           : std::nullopt;
  }
  const std::vector<std::string_view> dimensions =
      prototypeArrayDimensions(*type.arraySize);
  if (indexCount > dimensions.size()) {
    return std::nullopt;
  }
  if (indexCount == dimensions.size()) {
    type.arraySize.reset();
  } else {
    using DimensionOffset =
        std::vector<std::string_view>::difference_type;
    type.arraySize = joinPrototypeArrayDimensions(
        dimensions.begin() + static_cast<DimensionOffset>(indexCount),
        dimensions.end());
  }
  return type;
}

bool prototypeArrayTypeHasFixedDimensions(
    const HIRType &type, const PrototypeConstantMap &constants) {
  if (!type.arraySize.has_value() || type.arraySize->empty()) {
    return false;
  }
  const std::vector<std::string_view> dimensions =
      prototypeArrayDimensions(*type.arraySize);
  if (dimensions.empty()) {
    return false;
  }
  for (std::string_view dimension : dimensions) {
    if (!prototypeArrayDimensionElementCount(dimension, constants).has_value()) {
      return false;
    }
  }
  return true;
}

bool isPrototypeFunctionArrayParameterType(
    const HIRType &type, const PrototypeConstantMap &constants) {
  if (!prototypeArrayTypeHasFixedDimensions(type, constants)) {
    return false;
  }
  return isPrototypeArithmeticType(prototypeArrayInnermostElementType(type));
}

std::optional<HIRResourceKind> vulkanPrototypeResourceArrayParameterKind(
    const HIRType &type, const PrototypeConstantMap &constants) {
  if (!prototypeArrayTypeHasFixedDimensions(type, constants)) {
    return std::nullopt;
  }
  const std::vector<std::string_view> dimensions =
      prototypeArrayDimensions(*type.arraySize);
  if (dimensions.size() != 1) {
    return std::nullopt;
  }
  const HIRType elementType = arrayElementType(type);
  const std::string elementName = baseTypeName(elementType);
  if (isTextureResourceType(elementName)) {
    return HIRResourceKind::Texture;
  }
  if (isSamplerResourceType(elementName)) {
    return HIRResourceKind::Sampler;
  }
  return std::nullopt;
}

bool isVulkanPrototypeResourceArrayParameterType(
    const HIRType &type, const PrototypeConstantMap &constants) {
  return vulkanPrototypeResourceArrayParameterKind(type, constants).has_value();
}

bool isVulkanPrototypeErasedResourceArrayParameter(
    const HIRParameter &parameter, const PrototypeConstantMap &constants,
    bool entryPoint) {
  return !entryPoint &&
         isVulkanPrototypeResourceArrayParameterType(parameter.type, constants);
}

std::optional<HIRResource> vulkanPrototypePseudoResourceForParameter(
    const HIRParameter &parameter, const PrototypeConstantMap &constants) {
  const std::optional<HIRResourceKind> kind =
      vulkanPrototypeResourceArrayParameterKind(parameter.type, constants);
  if (!kind.has_value()) {
    return std::nullopt;
  }
  HIRResource resource;
  resource.name = parameter.name;
  resource.kind = *kind;
  resource.type = parameter.type;
  return resource;
}

std::string prototypeFunctionArrayParameterUnsupportedDetail(
    const HIRType &type, const PrototypeConstantMap &constants) {
  if (!type.arraySize.has_value()) {
    return "not an array";
  }
  if (type.arraySize->empty()) {
    return "runtime-sized arrays";
  }
  if (!prototypeArrayTypeHasFixedDimensions(type, constants)) {
    return "unresolved array sizes";
  }
  if (!isPrototypeArithmeticType(prototypeArrayInnermostElementType(type))) {
    return "non-numeric or aggregate array elements";
  }
  return "unsupported array shape";
}

std::optional<std::vector<std::size_t>>
prototypeVectorMemberIndices(const HIRType &type, std::string_view member) {
  const std::optional<std::size_t> width = prototypeVectorWidth(type);
  if (!width.has_value() || member.empty() || member.size() > 4) {
    return std::nullopt;
  }

  static constexpr std::string_view sets[] = {"xyzw", "rgba", "stpq"};
  const std::string_view *selectedSet = nullptr;
  for (const std::string_view &set : sets) {
    if (set.find(member.front()) != std::string_view::npos) {
      selectedSet = &set;
      break;
    }
  }
  if (selectedSet == nullptr) {
    return std::nullopt;
  }

  std::vector<std::size_t> indices;
  indices.reserve(member.size());
  for (const char component : member) {
    const std::size_t index = selectedSet->find(component);
    if (index == std::string_view::npos || index >= *width) {
      return std::nullopt;
    }
    indices.push_back(index);
  }
  return indices;
}

struct PrototypeBlockSupport {
  bool supported = false;
  bool terminated = false;
};

using PrototypeStorageFieldLayout = StorageFieldLayout;
using PrototypeStorageTypeLayout = StorageTypeLayout;

using PrototypeStructMap = std::unordered_map<std::string, const HIRStruct *>;

struct PrototypeStructAccessStep {
  enum class Kind { Field, ArrayIndex };
  Kind kind = Kind::Field;
  std::string fieldName;
  const HIRExpression *indexExpression = nullptr;
};

struct PrototypeStructMemberChain {
  const HIRExpression *indexAccess = nullptr;
  const HIRExpression *baseIdentifier = nullptr;
  std::vector<PrototypeStructAccessStep> steps;
};

struct PrototypeStructStorageBufferAccess {
  const HIRExpression *descriptorIndex = nullptr;
  const HIRExpression *elementIndex = nullptr;
  const HIRExpression *runtimeBlockIndex = nullptr;
  std::vector<PrototypeStructAccessStep> fieldSteps;
};

struct PrototypeStructUniformBufferAccess {
  const HIRExpression *descriptorIndex = nullptr;
  std::vector<PrototypeStructAccessStep> fieldSteps;
};

struct PrototypeStorageBufferIndexAccess {
  std::string resourceName;
  const HIRExpression *descriptorIndex = nullptr;
  const HIRExpression *elementIndex = nullptr;
};

struct PrototypeResolvedAccessIndex {
  std::optional<std::size_t> constantIndex;
  const HIRExpression *dynamicIndex = nullptr;
};

struct PrototypeResolvedStructFieldPath {
  HIRType valueType;
  std::vector<PrototypeStorageFieldLayout> fields;
  std::vector<PrototypeResolvedAccessIndex> indices;
};

struct PrototypeIndexedIdentifierAccess {
  std::string baseName;
  std::vector<const HIRExpression *> indices;
};

struct PrototypeLocalArrayElementAccess {
  std::string localName;
  HIRType localType;
  std::vector<const HIRExpression *> indices;
};

PrototypeConstantMap prototypeConstants(const HIRModule &module) {
  PrototypeConstantMap constants;
  for (const HIRConstant &constant : module.constants) {
    constants[constant.name] = constant;
  }
  return constants;
}

PrototypeStructMap prototypeStructs(const HIRModule &module) {
  PrototypeStructMap structs;
  for (const HIRStruct &structure : module.structs) {
    structs[structure.name] = &structure;
  }
  return structs;
}

StorageLayoutContext prototypeStorageLayoutContext(
    const PrototypeStructMap &structs, const PrototypeConstantMap &constants) {
  StorageLayoutContext context;
  for (const auto &[name, structure] : structs) {
    (void)name;
    context.addStruct(*structure);
  }
  for (const auto &[name, constant] : constants) {
    (void)name;
    context.addConstant(constant);
  }
  return context;
}

std::optional<PrototypeStorageTypeLayout>
prototypeStorageTypeLayout(const HIRType &type,
                           const StorageLayoutContext &layoutContext,
                           bool allowRuntimeArrayTail) {
  if (type.arraySize.has_value() && !type.arraySize->empty() &&
      type.arraySize->find("][") != std::string::npos) {
    const HIRType elementType = prototypeArrayElementTypeOneDimension(type);
    const std::optional<PrototypeStorageTypeLayout> elementLayout =
        prototypeStorageTypeLayout(elementType, layoutContext, false);
    if (!elementLayout.has_value() || elementLayout->hasRuntimeArray) {
      return std::nullopt;
    }
    const std::vector<std::string_view> dimensions =
        prototypeArrayDimensions(*type.arraySize);
    if (dimensions.empty()) {
      return std::nullopt;
    }
    const std::optional<std::size_t> elementCount =
        prototypeArrayDimensionElementCount(dimensions.front(), layoutContext);
    if (!elementCount.has_value()) {
      return std::nullopt;
    }

    PrototypeStorageTypeLayout layout;
    layout.alignmentBytes = elementLayout->alignmentBytes;
    layout.arrayStrideBytes =
        storageAlignTo(elementLayout->sizeBytes, elementLayout->alignmentBytes);
    layout.arrayElementCount = *elementCount;
    layout.sizeBytes = layout.arrayStrideBytes * *elementCount;
    layout.isArray = true;
    return layout;
  }
  if (type.arraySize.has_value() &&
      isPrototypeAtomicIntegerType(arrayElementType(type))) {
    if (type.arraySize->empty()) {
      if (!allowRuntimeArrayTail) {
        return std::nullopt;
      }
      PrototypeStorageTypeLayout layout;
      layout.alignmentBytes = 4;
      layout.arrayStrideBytes = 4;
      layout.isArray = true;
      layout.isRuntimeArray = true;
      layout.hasRuntimeArray = true;
      return layout;
    }

    const std::optional<std::size_t> elementCount =
        prototypeArrayElementCount(type, layoutContext);
    if (!elementCount.has_value()) {
      return std::nullopt;
    }
    PrototypeStorageTypeLayout layout;
    layout.alignmentBytes = 4;
    layout.arrayStrideBytes = 4;
    layout.arrayElementCount = *elementCount;
    layout.sizeBytes = 4 * *elementCount;
    layout.isArray = true;
    return layout;
  }
  if (isPrototypeAtomicIntegerType(type)) {
    PrototypeStorageTypeLayout layout;
    layout.sizeBytes = 4;
    layout.alignmentBytes = 4;
    return layout;
  }
  return computeStorageTypeLayout(type, StorageLayoutKind::Std430,
                                  layoutContext, allowRuntimeArrayTail);
}

std::optional<PrototypeStorageTypeLayout>
prototypeStorageTypeLayout(const HIRType &type,
                           const PrototypeStructMap &structs,
                           const PrototypeConstantMap &constants,
                           bool allowRuntimeArrayTail) {
  const StorageLayoutContext layoutContext =
      prototypeStorageLayoutContext(structs, constants);
  return prototypeStorageTypeLayout(type, layoutContext, allowRuntimeArrayTail);
}

StorageCapabilityPolicy prototypeStorageCapabilityPolicy() {
  StorageCapabilityPolicy policy;
  policy.layoutKind = StorageLayoutKind::Std430;
  policy.allowStructTypes = true;
  policy.allowFixedArrays = true;
  policy.allowRuntimeArrayTail = true;
  policy.supportedScalarTypes = {"int", "uint", "float"};
  policy.supportedVectorTypes = {"vec2",  "vec3",  "vec4",
                                 "ivec2", "ivec3", "ivec4",
                                 "uvec2", "uvec3", "uvec4"};
  return policy;
}

std::optional<PrototypeStructMemberChain>
prototypeStructMemberChain(const HIRExpression &expression) {
  PrototypeStructMemberChain chain;
  const HIRExpression *current = &expression;
  while (true) {
    if (current->kind == HIRExpressionKind::MemberAccess &&
        !current->children.empty()) {
      chain.steps.push_back(PrototypeStructAccessStep{
          PrototypeStructAccessStep::Kind::Field, current->value, nullptr});
      current = &current->children.front();
      continue;
    }
    if (current->kind == HIRExpressionKind::IndexAccess &&
        current->children.size() >= 2 &&
        current->children[0].kind != HIRExpressionKind::Identifier) {
      chain.steps.push_back(PrototypeStructAccessStep{
          PrototypeStructAccessStep::Kind::ArrayIndex, "",
          &current->children[1]});
      current = &current->children.front();
      continue;
    }
    break;
  }

  if (chain.steps.empty()) {
    return std::nullopt;
  }

  std::reverse(chain.steps.begin(), chain.steps.end());
  if (current->kind == HIRExpressionKind::IndexAccess &&
      current->children.size() >= 2 &&
      current->children[0].kind == HIRExpressionKind::Identifier) {
    chain.indexAccess = current;
    return chain;
  }
  if (current->kind == HIRExpressionKind::Identifier) {
    chain.baseIdentifier = current;
    return chain;
  }

  return std::nullopt;
}

const HIRExpression *prototypeStructMemberChainBase(
    const PrototypeStructMemberChain &chain) {
  if (chain.indexAccess != nullptr && chain.indexAccess->children.size() >= 2) {
    return &chain.indexAccess->children[0];
  }
  return chain.baseIdentifier;
}

std::optional<PrototypeStructStorageBufferAccess>
prototypeStructStorageBufferAccess(
    const PrototypeStructMemberChain &chain, const HIRType &resourceType,
    bool isRuntimeArrayBlock, std::string_view resourceName,
    DiagnosticEngine *diagnostics) {
  PrototypeStructStorageBufferAccess access;
  access.fieldSteps = chain.steps;
  const bool resourceIsDescriptorArray = resourceType.arraySize.has_value();

  if (resourceIsDescriptorArray) {
    if (chain.indexAccess == nullptr || chain.indexAccess->children.size() < 2) {
      if (diagnostics != nullptr) {
        diagnostics->error(
            "vulkan.prototype-unsupported-struct-buffer",
            "Vulkan prototype struct storage-buffer descriptor array '" +
                std::string(resourceName) +
                "' requires a descriptor index before field access");
      }
      return std::nullopt;
    }
    access.descriptorIndex = &chain.indexAccess->children[1];

    if (!isRuntimeArrayBlock) {
      if (access.fieldSteps.empty() ||
          access.fieldSteps.front().kind !=
              PrototypeStructAccessStep::Kind::ArrayIndex) {
        if (diagnostics != nullptr) {
          diagnostics->error(
              "vulkan.prototype-unsupported-struct-buffer",
              "Vulkan prototype struct storage-buffer descriptor arrays "
              "require descriptor and element indices, such as " +
                  std::string(resourceName) + "[0][1].field");
        }
        return std::nullopt;
      }
      access.elementIndex = access.fieldSteps.front().indexExpression;
      access.fieldSteps.erase(access.fieldSteps.begin());
    } else if (!access.fieldSteps.empty() &&
               access.fieldSteps.front().kind ==
                   PrototypeStructAccessStep::Kind::ArrayIndex) {
      access.runtimeBlockIndex = access.fieldSteps.front().indexExpression;
      access.fieldSteps.erase(access.fieldSteps.begin());
    }

    return access;
  }

  if (isRuntimeArrayBlock) {
    if (chain.indexAccess != nullptr && chain.indexAccess->children.size() >= 2) {
      access.runtimeBlockIndex = &chain.indexAccess->children[1];
    }
    return access;
  }

  if (chain.indexAccess == nullptr || chain.indexAccess->children.size() < 2) {
    if (diagnostics != nullptr) {
      diagnostics->error("vulkan.prototype-unsupported-struct-buffer",
                         "Vulkan prototype direct storage-buffer member "
                         "access is available only for runtime-tail singleton "
                         "blocks; index ordinary struct storage buffers first");
    }
    return std::nullopt;
  }

  access.elementIndex = &chain.indexAccess->children[1];
  return access;
}

std::optional<PrototypeStructUniformBufferAccess>
prototypeStructUniformBufferAccess(const PrototypeStructMemberChain &chain,
                                   const HIRType &resourceType,
                                   std::string_view resourceName,
                                   DiagnosticEngine *diagnostics) {
  PrototypeStructUniformBufferAccess access;
  access.fieldSteps = chain.steps;
  if (access.fieldSteps.empty()) {
    if (diagnostics != nullptr) {
      diagnostics->error("vulkan.prototype-unsupported-uniform-buffer",
                         "Vulkan prototype uniform-buffer access requires a "
                         "direct struct field on resource '" +
                             std::string(resourceName) + "'");
    }
    return std::nullopt;
  }

  const bool resourceIsDescriptorArray = resourceType.arraySize.has_value();
  if (resourceIsDescriptorArray) {
    if (resourceType.arraySize->empty()) {
      if (diagnostics != nullptr) {
        diagnostics->error(
            "vulkan.prototype-unsupported-runtime-resource-array",
            "Vulkan prototype uniform-buffer descriptor arrays require "
            "fixed-size resource arrays for '" +
                std::string(resourceName) + "'");
      }
      return std::nullopt;
    }
    if (chain.indexAccess == nullptr || chain.indexAccess->children.size() < 2) {
      if (diagnostics != nullptr) {
        diagnostics->error(
            "vulkan.prototype-unsupported-uniform-buffer",
            "Vulkan prototype uniform-buffer descriptor array '" +
                std::string(resourceName) +
                "' requires a descriptor index before field access");
      }
      return std::nullopt;
    }
    access.descriptorIndex = &chain.indexAccess->children[1];
    return access;
  }

  if (chain.indexAccess != nullptr) {
    if (diagnostics != nullptr) {
      diagnostics->error(
          "vulkan.prototype-unsupported-uniform-buffer",
          "Vulkan prototype non-array uniform buffer '" +
              std::string(resourceName) +
              "' does not support descriptor-array indexing");
    }
    return std::nullopt;
  }

  return access;
}

std::optional<PrototypeStorageTypeLayout>
prototypeStorageBufferElementLayout(const HIRResource &resource,
                                    const PrototypeStructMap &structs,
                                    const PrototypeConstantMap &constants) {
  return prototypeStorageTypeLayout(prototypeBufferElementType(resource), structs,
                                    constants, true);
}

bool prototypeStorageBufferIsRuntimeArrayBlock(
    const HIRResource &resource,
    const PrototypeStructMap &structs,
    const PrototypeConstantMap &constants) {
  const std::optional<PrototypeStorageTypeLayout> layout =
      prototypeStorageBufferElementLayout(resource, structs, constants);
  return layout.has_value() && layout->hasRuntimeArray;
}

std::optional<PrototypeResolvedStructFieldPath>
resolvePrototypeStructFieldPath(const HIRType &rootType,
                                const std::vector<PrototypeStructAccessStep> &steps,
                                const PrototypeStructMap &structs,
                                const PrototypeConstantMap &constants,
                                DiagnosticEngine *diagnostics,
                                bool allowArrayLeaf = false) {
  if (steps.empty()) {
    return std::nullopt;
  }

  PrototypeResolvedStructFieldPath path;
  HIRType currentType = rootType;
  for (const PrototypeStructAccessStep &step : steps) {
    if (step.kind == PrototypeStructAccessStep::Kind::ArrayIndex) {
      if (!currentType.arraySize.has_value()) {
        if (diagnostics != nullptr) {
          diagnostics->error(
              "vulkan.prototype-unsupported-struct-buffer",
              "Vulkan prototype struct storage-buffer field access cannot "
              "index non-array type '" +
                  formatType(currentType) + "'");
        }
        return std::nullopt;
      }
      if (!currentType.arraySize->empty() &&
          !prototypeArrayElementCount(currentType, constants).has_value()) {
        if (diagnostics != nullptr) {
          diagnostics->error(
              "vulkan.prototype-unsupported-struct-array-field",
              "Vulkan prototype struct storage-buffer field access requires "
              "fixed-size numeric or folded-constant array fields");
        }
        return std::nullopt;
      }

      path.indices.push_back(PrototypeResolvedAccessIndex{
          std::nullopt, step.indexExpression});
      currentType = arrayElementType(currentType);
      continue;
    }

    if (currentType.arraySize.has_value()) {
      if (diagnostics != nullptr) {
        diagnostics->error(
            "vulkan.prototype-unsupported-struct-array-field",
            "Vulkan prototype struct storage-buffer field access does not "
            "support array field '" +
                step.fieldName + "' without an element index");
      }
      return std::nullopt;
    }

    const auto structure = structs.find(currentType.name);
    if (structure == structs.end()) {
      return std::nullopt;
    }

    const std::optional<PrototypeStorageTypeLayout> layout =
        prototypeStorageTypeLayout(currentType, structs, constants, true);
    if (!layout.has_value()) {
      if (diagnostics != nullptr) {
        diagnostics->error("vulkan.prototype-unsupported-struct-buffer",
                           "Vulkan prototype cannot compute storage layout "
                           "for struct type '" +
                               currentType.name + "'");
      }
      return std::nullopt;
    }

    auto field = std::find_if(
        layout->fields.begin(), layout->fields.end(),
        [&](const PrototypeStorageFieldLayout &candidate) {
          return candidate.name == step.fieldName;
        });
    if (field == layout->fields.end()) {
      if (diagnostics != nullptr) {
        diagnostics->error("vulkan.prototype-unsupported-struct-buffer",
                           "Vulkan prototype cannot resolve struct "
                           "storage-buffer field '" +
                               step.fieldName + "'");
      }
      return std::nullopt;
    }

    path.fields.push_back(*field);
    path.indices.push_back(PrototypeResolvedAccessIndex{
        field->index, nullptr});
    currentType = field->type;
  }

  if (currentType.arraySize.has_value() && !allowArrayLeaf) {
    if (diagnostics != nullptr) {
      diagnostics->error(
          "vulkan.prototype-unsupported-struct-array-field",
          "Vulkan prototype struct storage-buffer field access does not "
          "support array leaf fields yet");
    }
    return std::nullopt;
  }
  const HIRType valueType =
      currentType.arraySize.has_value() ? arrayElementType(currentType)
                                        : currentType;
  if (!isPrototypeArithmeticType(valueType)) {
    if (diagnostics != nullptr) {
      diagnostics->error(
          "vulkan.prototype-unsupported-nested-struct-field",
          "Vulkan prototype struct storage-buffer field access supports only "
          "scalar/vector leaf fields; aggregate field '" +
              currentType.name + "' is not supported as a value yet");
    }
    return std::nullopt;
  }

  path.valueType = currentType;
  return path;
}

bool emitUnsupportedStorageCapabilityDiagnostic(
    const HIRType &type, const StorageLayoutContext &layoutContext,
    DiagnosticEngine &diagnostics, std::string_view contextName) {
  const std::optional<StorageCapabilityIssue> issue = checkStorageCapabilities(
      type, layoutContext, prototypeStorageCapabilityPolicy(), true,
      contextName);
  if (!issue.has_value()) {
    return false;
  }

  switch (issue->kind) {
  case StorageCapabilityIssueKind::UnsupportedRuntimeArrayField:
    diagnostics.error(
        "vulkan.prototype-unsupported-runtime-array-field",
        "Vulkan prototype struct storage-buffer lowering supports "
        "unsized/runtime array field '" +
            issue->path +
            "' only as a direct final field of a storage-buffer block");
    return true;
  case StorageCapabilityIssueKind::UnsupportedArrayField:
    diagnostics.error(
        "vulkan.prototype-unsupported-struct-array-field",
        "Vulkan prototype struct storage-buffer lowering requires fixed-size "
        "numeric or folded-constant array field '" +
            issue->path + "'");
    return true;
  case StorageCapabilityIssueKind::UnsupportedType:
  case StorageCapabilityIssueKind::UnsupportedLayout:
    diagnostics.error(
        "vulkan.prototype-unsupported-struct-buffer",
        "Vulkan prototype struct storage-buffer lowering does not support "
        "field '" +
            issue->path + "' of type '" + formatType(issue->type) + "'");
    return true;
  }
  return false;
}

bool isPrototypeConstantSupported(const HIRConstant &constant) {
  return constant.foldedValue.has_value() && isPrototypeScalarType(constant.type);
}

std::string prototypeNumericConstantLiteral(const HIRType &type,
                                            std::string value) {
  if (type.name == "float" && value.find('.') == std::string::npos &&
      value.find('e') == std::string::npos &&
      value.find('E') == std::string::npos) {
    value += ".0";
  }
  return value;
}

std::optional<std::size_t>
prototypeStaticArrayIndexValue(const HIRExpression &expression,
                               const PrototypeConstantMap &constants) {
  if (expression.kind == HIRExpressionKind::Group &&
      !expression.children.empty()) {
    return prototypeStaticArrayIndexValue(expression.children.front(),
                                          constants);
  }
  if (expression.kind == HIRExpressionKind::Unary && expression.value == "+" &&
      expression.children.size() == 1) {
    return prototypeStaticArrayIndexValue(expression.children.front(),
                                          constants);
  }

  auto parseIndex = [](std::string_view text) -> std::optional<std::size_t> {
    if (!isIntegerLiteralText(text) || text.empty() || text.front() == '-') {
      return std::nullopt;
    }
    try {
      return static_cast<std::size_t>(std::stoull(std::string(text)));
    } catch (...) {
      return std::nullopt;
    }
  };

  if (expression.kind == HIRExpressionKind::Literal &&
      !expression.type.arraySize.has_value() &&
      (expression.type.name == "int" || expression.type.name == "uint")) {
    return parseIndex(expression.value);
  }
  if (expression.kind == HIRExpressionKind::Identifier) {
    const auto constant = constants.find(expression.value);
    if (constant != constants.end() && constant->second.foldedValue.has_value() &&
        !constant->second.type.arraySize.has_value() &&
        (constant->second.type.name == "int" ||
         constant->second.type.name == "uint")) {
      return parseIndex(*constant->second.foldedValue);
    }
  }
  return std::nullopt;
}

HIRType prototypeExpressionType(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants) {
  if (expression.kind == HIRExpressionKind::NonUniform &&
      expression.children.size() == 1) {
    return prototypeExpressionType(expression.children.front(), locals, resources,
                                   constants);
  }
  if (expression.kind == HIRExpressionKind::Identifier) {
    if (auto local = locals.find(expression.value); local != locals.end()) {
      return local->second;
    }
    if (isPrototypeComputeBuiltinIdentifier(expression.value)) {
      return prototypeComputeBuiltinType();
    }
    if (auto constant = constants.find(expression.value);
        constant != constants.end()) {
      return constant->second.type;
    }
  }
  if (expression.kind == HIRExpressionKind::IndexAccess &&
      expression.children.size() >= 2 &&
      expression.children[0].kind == HIRExpressionKind::Identifier) {
    if (auto resource = resources.find(expression.children[0].value);
        resource != resources.end() &&
        isPrototypeStorageBufferResource(resource->second)) {
      return prototypeBufferElementType(resource->second);
    }
  }
  return expression.type;
}

std::optional<PrototypeIndexedIdentifierAccess>
prototypeIndexedIdentifierAccess(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::IndexAccess ||
      expression.children.size() < 2) {
    return std::nullopt;
  }

  PrototypeIndexedIdentifierAccess access;
  const HIRExpression *current = &expression;
  while (current->kind == HIRExpressionKind::IndexAccess &&
         current->children.size() >= 2) {
    access.indices.push_back(&current->children[1]);
    current = &current->children[0];
  }
  if (current->kind != HIRExpressionKind::Identifier) {
    return std::nullopt;
  }
  access.baseName = current->value;
  std::reverse(access.indices.begin(), access.indices.end());
  return access;
}

std::optional<PrototypeLocalArrayElementAccess>
prototypeLocalArrayElementAccess(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals) {
  std::optional<PrototypeIndexedIdentifierAccess> indexed =
      prototypeIndexedIdentifierAccess(expression);
  if (!indexed.has_value()) {
    return std::nullopt;
  }
  const auto local = locals.find(indexed->baseName);
  if (local == locals.end() || !local->second.arraySize.has_value()) {
    return std::nullopt;
  }
  return PrototypeLocalArrayElementAccess{
      indexed->baseName, local->second, std::move(indexed->indices)};
}

std::optional<PrototypeStorageBufferIndexAccess>
prototypeStorageBufferIndexAccess(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::IndexAccess ||
      expression.children.size() < 2) {
    return std::nullopt;
  }

  if (expression.children[0].kind == HIRExpressionKind::Identifier) {
    return PrototypeStorageBufferIndexAccess{
        expression.children[0].value, nullptr, &expression.children[1]};
  }

  if (expression.children[0].kind == HIRExpressionKind::IndexAccess &&
      expression.children[0].children.size() >= 2 &&
      expression.children[0].children[0].kind == HIRExpressionKind::Identifier) {
    return PrototypeStorageBufferIndexAccess{
        expression.children[0].children[0].value,
        &expression.children[0].children[1], &expression.children[1]};
  }

  return std::nullopt;
}

bool prototypeExpressionSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics);

bool prototypeAtomicIntegerStatementSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics);

bool prototypeResourceIndexSupported(
    const HIRExpression &target,
    const std::unordered_map<std::string, HIRResource> &resources,
    const std::unordered_map<std::string, HIRType> &locals,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics);

bool prototypeStorageBufferMemberAccessSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRResource> &resources,
    const std::unordered_map<std::string, HIRType> &locals,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics,
    bool allowArrayLeaf = false);

bool prototypeUniformBufferMemberAccessSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRResource> &resources,
    const std::unordered_map<std::string, HIRType> &locals,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics,
    bool allowArrayLeaf = false);

bool prototypeTextureSampleSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics);

bool prototypeAssignmentSupported(
    const HIRStatement &statement,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_set<std::string> &readOnlyArrayLocals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics);

bool prototypeDeclarationSupported(
    const HIRStatement &statement,
    std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics);

bool prototypeIfStatementSupported(
    const HIRStatement &statement,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_set<std::string> &readOnlyArrayLocals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics,
    const HIRType &returnType,
    bool &terminates,
    bool allowReturn = true,
    bool allowLoopControl = false);

bool prototypeForStatementSupported(
    const HIRStatement &statement,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_set<std::string> &readOnlyArrayLocals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics);

std::vector<HIRType> prototypeCallArgumentTypes(const HIRExpression &expression) {
  std::vector<HIRType> types;
  types.reserve(expression.children.size());
  for (const HIRExpression &child : expression.children) {
    types.push_back(child.type);
  }
  return types;
}

enum class PrototypeIntrinsicLoweringKind {
  GLSLStd450,
  CoreInstruction,
  Identity,
};

struct PrototypeIntrinsicLowering {
  PrototypeIntrinsicLoweringKind kind =
      PrototypeIntrinsicLoweringKind::GLSLStd450;
  std::string opcode;
  bool operandsUseResultType = true;
};

bool prototypeCanUseResultTypeOperand(const HIRType &operandType,
                                      const HIRType &resultType) {
  if (samePrototypeType(operandType, resultType)) {
    return true;
  }
  if (!isPrototypeVectorType(resultType)) {
    return false;
  }
  return samePrototypeType(operandType, prototypeVectorComponentType(resultType));
}

bool prototypeOperandsCanUseResultType(const HIRExpression &expression) {
  for (const HIRExpression &child : expression.children) {
    if (!prototypeCanUseResultTypeOperand(child.type, expression.type)) {
      return false;
    }
  }
  return true;
}

std::string prototypeMinMaxIntrinsicOpcode(std::string_view name,
                                           const HIRType &type) {
  if (isPrototypeFloatScalarOrVectorType(type)) {
    return name == "min" ? "FMin" : "FMax";
  }
  if (isPrototypeSignedIntegerScalarOrVectorType(type)) {
    return name == "min" ? "SMin" : "SMax";
  }
  if (isPrototypeUnsignedIntegerScalarOrVectorType(type)) {
    return name == "min" ? "UMin" : "UMax";
  }
  return "";
}

std::optional<PrototypeIntrinsicLowering>
prototypeIntrinsicLoweringForCall(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::Call || expression.value.empty()) {
    return std::nullopt;
  }

  const std::vector<HIRType> argumentTypes =
      prototypeCallArgumentTypes(expression);
  if (selectHIRIntrinsicSignature(expression.value, argumentTypes) == nullptr) {
    return std::nullopt;
  }

  const std::string_view name = expression.value;
  const HIRType &firstArgumentType = expression.children.front().type;
  auto sameFloatResult = [&]() {
    return isPrototypeFloatScalarOrVectorType(firstArgumentType) &&
           samePrototypeType(firstArgumentType, expression.type);
  };

  if (name == "abs" && expression.children.size() == 1 &&
      samePrototypeType(firstArgumentType, expression.type)) {
    if (isPrototypeFloatScalarOrVectorType(expression.type)) {
      return PrototypeIntrinsicLowering{
          PrototypeIntrinsicLoweringKind::GLSLStd450, "FAbs"};
    }
    if (isPrototypeSignedIntegerScalarOrVectorType(expression.type)) {
      return PrototypeIntrinsicLowering{
          PrototypeIntrinsicLoweringKind::GLSLStd450, "SAbs"};
    }
    if (isPrototypeUnsignedIntegerScalarOrVectorType(expression.type)) {
      return PrototypeIntrinsicLowering{
          PrototypeIntrinsicLoweringKind::Identity, ""};
    }
    return std::nullopt;
  }

  if (name == "atan" && sameFloatResult()) {
    if (expression.children.size() == 1) {
      return PrototypeIntrinsicLowering{
          PrototypeIntrinsicLoweringKind::GLSLStd450, "Atan"};
    }
    if (expression.children.size() == 2 &&
        prototypeOperandsCanUseResultType(expression)) {
      return PrototypeIntrinsicLowering{
          PrototypeIntrinsicLoweringKind::GLSLStd450, "Atan2"};
    }
    return std::nullopt;
  }

  if (name == "dot" && expression.children.size() == 2 &&
      expression.type.name == "float" &&
      !expression.type.arraySize.has_value() &&
      isPrototypeFloatVectorType(expression.children[0].type) &&
      samePrototypeType(expression.children[0].type,
                        expression.children[1].type)) {
    return PrototypeIntrinsicLowering{
        PrototypeIntrinsicLoweringKind::CoreInstruction, "OpDot", false};
  }

  if ((name == "fract" || name == "sin" || name == "sqrt" ||
       name == "normalize") &&
      expression.children.size() == 1 && sameFloatResult()) {
    std::string opcode;
    if (name == "fract") {
      opcode = "Fract";
    } else if (name == "sin") {
      opcode = "Sin";
    } else if (name == "sqrt") {
      opcode = "Sqrt";
    } else {
      opcode = "Normalize";
    }
    return PrototypeIntrinsicLowering{
        PrototypeIntrinsicLoweringKind::GLSLStd450, std::move(opcode)};
  }

  if (name == "length" && expression.children.size() == 1 &&
      expression.type.name == "float" && !expression.type.arraySize.has_value() &&
      isPrototypeFloatScalarOrVectorType(firstArgumentType)) {
    return PrototypeIntrinsicLowering{
        PrototypeIntrinsicLoweringKind::GLSLStd450, "Length", false};
  }

  if ((name == "min" || name == "max") && expression.children.size() == 2 &&
      prototypeOperandsCanUseResultType(expression)) {
    const std::string opcode =
        prototypeMinMaxIntrinsicOpcode(name, expression.type);
    if (!opcode.empty()) {
      return PrototypeIntrinsicLowering{
          PrototypeIntrinsicLoweringKind::GLSLStd450, opcode};
    }
    return std::nullopt;
  }

  if (name == "mix" && expression.children.size() == 3 &&
      isPrototypeFloatScalarOrVectorType(expression.type) &&
      prototypeOperandsCanUseResultType(expression)) {
    return PrototypeIntrinsicLowering{
        PrototypeIntrinsicLoweringKind::GLSLStd450, "FMix"};
  }

  if (name == "pow" && expression.children.size() == 2 &&
      isPrototypeFloatScalarOrVectorType(expression.type) &&
      samePrototypeType(firstArgumentType, expression.type) &&
      prototypeOperandsCanUseResultType(expression)) {
    return PrototypeIntrinsicLowering{
        PrototypeIntrinsicLoweringKind::GLSLStd450, "Pow"};
  }

  if (name == "reflect" && expression.children.size() == 2 &&
      isPrototypeFloatScalarOrVectorType(expression.type) &&
      samePrototypeType(firstArgumentType, expression.type) &&
      samePrototypeType(expression.children[1].type, expression.type)) {
    return PrototypeIntrinsicLowering{
        PrototypeIntrinsicLoweringKind::GLSLStd450, "Reflect"};
  }

  return std::nullopt;
}

bool isPrototypeDeferredUserCallType(const HIRExpression &expression,
                                     const HIRType &type) {
  return expression.kind == HIRExpressionKind::Call &&
         !isPrototypeWorkgroupBarrierCall(expression) &&
         !prototypeIntrinsicLoweringForCall(expression).has_value() &&
         type.name.empty() && !type.arraySize.has_value();
}

bool isPrototypeDirectResourceArrayArgument(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRResource> &resources) {
  if (expression.kind != HIRExpressionKind::Identifier) {
    return false;
  }
  const auto resource = resources.find(expression.value);
  return resource != resources.end() &&
         resource->second.kind != HIRResourceKind::Shared &&
         resource->second.kind != HIRResourceKind::Value &&
         resource->second.type.arraySize.has_value();
}

using VulkanPrototypeResourceArrayParameterAliasMap =
    std::unordered_map<std::string, std::unordered_map<std::string, std::string>>;
using VulkanPrototypeArrayWriteBackParameterMap =
    std::unordered_map<std::string, std::unordered_set<std::string>>;

const HIRFunction *findVulkanPrototypeCallableFunction(const HIRModule &module,
                                                       const HIRStage &stage,
                                                       std::string_view name) {
  for (const HIRFunction &function : stage.functions) {
    if (function.name == name) {
      return &function;
    }
  }
  for (const HIRFunction &function : module.functions) {
    if (function.name == name) {
      return &function;
    }
  }
  return nullptr;
}

const HIRResource *findVulkanPrototypeStageResource(const HIRStage &stage,
                                                   std::string_view name) {
  for (const HIRResource &resource : stage.resources) {
    if (resource.name == name) {
      return &resource;
    }
  }
  return nullptr;
}

HIRFunctionParameterArrayCallFeatureSupport
vulkanPrototypeFunctionParameterArrayCallFeatureSupport(
    const HIRParameter &parameter,
    HIRFunctionParameterArrayCallFeature feature,
    const PrototypeConstantMap &constants) {
  if (feature ==
      HIRFunctionParameterArrayCallFeature::DirectResourceArrayArguments) {
    return isVulkanPrototypeResourceArrayParameterType(parameter.type, constants)
               ? HIRFunctionParameterArrayCallFeatureSupport::Supported
               : HIRFunctionParameterArrayCallFeatureSupport::Unsupported;
  }
  if (isVulkanPrototypeResourceArrayParameterType(parameter.type, constants) &&
      feature ==
          HIRFunctionParameterArrayCallFeature::FunctionParameterArguments) {
    return HIRFunctionParameterArrayCallFeatureSupport::Unsupported;
  }
  return functionParameterArrayCallFeatureSupport(feature);
}

bool collectVulkanPrototypeResourceArrayParameterAliases(
    const HIRModule &module, const HIRStage &stage,
    VulkanPrototypeResourceArrayParameterAliasMap &aliases,
    DiagnosticEngine *diagnostics) {
  const PrototypeConstantMap constants = prototypeConstants(module);
  std::set<std::string> unsupportedLabels;

  auto visitor = [&](const HIRFunction &caller, const HIRExpression &expression) {
    if (expression.kind != HIRExpressionKind::Call) {
      return;
    }
    const HIRFunction *callee =
        findVulkanPrototypeCallableFunction(module, stage, expression.value);
    if (callee == nullptr) {
      return;
    }
    const std::size_t argumentCount =
        std::min(expression.children.size(), callee->parameters.size());
    for (std::size_t index = 0; index < argumentCount; ++index) {
      const HIRParameter &parameter = callee->parameters[index];
      const std::optional<HIRResourceKind> parameterKind =
          vulkanPrototypeResourceArrayParameterKind(parameter.type, constants);
      if (!parameterKind.has_value()) {
        continue;
      }
      const HIRExpression &argument = expression.children[index];
      if (argument.kind != HIRExpressionKind::Identifier) {
        unsupportedLabels.insert(
            "caller '" + caller.name + "' -> callee '" + callee->name +
            "' parameter '" + parameter.name +
            "': requires a direct descriptor-array argument");
        continue;
      }
      const HIRResource *resource =
          findVulkanPrototypeStageResource(stage, argument.value);
      if (resource == nullptr || resource->kind != *parameterKind ||
          !resource->type.arraySize.has_value() ||
          !samePrototypeType(resource->type, parameter.type)) {
        unsupportedLabels.insert(
            "caller '" + caller.name + "' -> callee '" + callee->name +
            "' parameter '" + parameter.name +
            "': direct argument '" + argument.value +
            "' is not a matching fixed-size descriptor array");
        continue;
      }
      std::string &alias = aliases[callee->name][parameter.name];
      if (alias.empty()) {
        alias = resource->name;
      } else if (alias != resource->name) {
        unsupportedLabels.insert(
            "callee '" + callee->name + "' parameter '" + parameter.name +
            "': multiple descriptor-array sources are not supported");
      }
    }
  };

  for (const HIRFunction &function : module.functions) {
    auto expressionVisitor = [&](const HIRExpression &expression) {
      visitor(function, expression);
    };
    visitFunctionExpressions(function, expressionVisitor);
  }
  for (const HIRFunction &function : stage.functions) {
    auto expressionVisitor = [&](const HIRExpression &expression) {
      visitor(function, expression);
    };
    visitFunctionExpressions(function, expressionVisitor);
  }

  for (const HIRFunction &function : module.functions) {
    for (const HIRParameter &parameter : function.parameters) {
      if (isVulkanPrototypeResourceArrayParameterType(parameter.type,
                                                     constants) &&
          aliases[function.name].find(parameter.name) ==
              aliases[function.name].end()) {
        unsupportedLabels.insert("callee '" + function.name + "' parameter '" +
                                 parameter.name +
                                 "': no direct descriptor-array call source");
      }
    }
  }
  for (const HIRFunction &function : stage.functions) {
    for (const HIRParameter &parameter : function.parameters) {
      if (isVulkanPrototypeResourceArrayParameterType(parameter.type,
                                                     constants) &&
          aliases[function.name].find(parameter.name) ==
              aliases[function.name].end()) {
        unsupportedLabels.insert("callee '" + function.name + "' parameter '" +
                                 parameter.name +
                                 "': no direct descriptor-array call source");
      }
    }
  }

  if (!unsupportedLabels.empty()) {
    if (diagnostics != nullptr) {
      diagnostics->error(
          "vulkan.prototype-unsupported-function-parameter-resource-array",
          "Vulkan prototype helper resource array parameters require one "
          "matching direct descriptor-array source per helper parameter; "
          "unsupported resource-array helper call(s): " +
              joinNames(unsupportedLabels));
    }
    return false;
  }
  return true;
}

const HIRExpression *
vulkanFunctionParameterArrayRootIdentifier(const HIRExpression &expression) {
  const HIRExpression *current = &expression;
  while (current != nullptr) {
    if ((current->kind == HIRExpressionKind::Group ||
         (current->kind == HIRExpressionKind::Unary &&
          current->value == "+")) &&
        !current->children.empty()) {
      current = &current->children.front();
      continue;
    }
    if ((current->kind == HIRExpressionKind::IndexAccess ||
         current->kind == HIRExpressionKind::MemberAccess) &&
        !current->children.empty()) {
      current = &current->children.front();
      continue;
    }
    return current->kind == HIRExpressionKind::Identifier ? current : nullptr;
  }
  return nullptr;
}

bool vulkanFunctionParameterArrayHasCallFeature(
    const std::vector<HIRFunctionParameterArrayCallFeature> &features,
    HIRFunctionParameterArrayCallFeature expected) {
  return std::find(features.begin(), features.end(), expected) !=
         features.end();
}

bool vulkanStorageBufferFieldArrayWriteBackArgument(
    const HIRModule &module, const HIRFunction &caller,
    const HIRExpression &argument, const HIRStage *stage) {
  if (functionParameterArrayShape(module, argument.type) !=
          HIRFunctionParameterArrayShape::FixedSize ||
      !argument.type.arraySize.has_value()) {
    return false;
  }
  if (prototypeArrayDimensions(*argument.type.arraySize).size() != 1) {
    return false;
  }

  const std::vector<HIRFunctionParameterArrayCallFeature> features =
      functionParameterArrayCallArgumentFeatures(module, caller, argument,
                                                 stage);
  return vulkanFunctionParameterArrayHasCallFeature(
             features, HIRFunctionParameterArrayCallFeature::
                           StorageBufferFieldArguments) &&
         !vulkanFunctionParameterArrayHasCallFeature(
             features, HIRFunctionParameterArrayCallFeature::
                           LocalArrayArguments) &&
         !vulkanFunctionParameterArrayHasCallFeature(
             features, HIRFunctionParameterArrayCallFeature::
                           FunctionParameterArguments) &&
         !vulkanFunctionParameterArrayHasCallFeature(
             features, HIRFunctionParameterArrayCallFeature::
                           NestedStructFieldArguments) &&
         !vulkanFunctionParameterArrayHasCallFeature(
             features, HIRFunctionParameterArrayCallFeature::
                           DirectResourceArrayArguments);
}

void collectVulkanFunctionParameterArrayWritesInStatement(
    const HIRModule &module, const HIRFunction &function,
    const std::unordered_set<std::string> &parameterArrays,
    const HIRStatement &statement, std::unordered_set<std::string> &written) {
  if (statement.kind == HIRStatementKind::Assignment &&
      functionParameterArrayWriteTarget(module, function, statement.target,
                                        nullptr) ==
          HIRFunctionParameterArrayWriteTarget::ReadOnlyParameterArray) {
    if (const HIRExpression *root =
            vulkanFunctionParameterArrayRootIdentifier(statement.target);
        root != nullptr && parameterArrays.count(root->value) != 0) {
      written.insert(root->value);
    }
  }

  for (const HIRStatement &child : statement.initializer) {
    collectVulkanFunctionParameterArrayWritesInStatement(
        module, function, parameterArrays, child, written);
  }
  for (const HIRStatement &child : statement.update) {
    collectVulkanFunctionParameterArrayWritesInStatement(
        module, function, parameterArrays, child, written);
  }
  for (const HIRStatement &child : statement.body) {
    collectVulkanFunctionParameterArrayWritesInStatement(
        module, function, parameterArrays, child, written);
  }
  for (const HIRStatement &child : statement.elseBody) {
    collectVulkanFunctionParameterArrayWritesInStatement(
        module, function, parameterArrays, child, written);
  }
}

std::unordered_set<std::string>
writtenVulkanFunctionParameterArrayNames(const HIRModule &module,
                                         const HIRFunction &function) {
  std::unordered_set<std::string> parameterArrays;
  for (const HIRParameter &parameter : function.parameters) {
    if (functionParameterArrayShape(module, parameter.type) ==
        HIRFunctionParameterArrayShape::FixedSize) {
      parameterArrays.insert(parameter.name);
    }
  }

  std::unordered_set<std::string> written;
  if (parameterArrays.empty()) {
    return written;
  }
  for (const HIRStatement &statement : function.body) {
    collectVulkanFunctionParameterArrayWritesInStatement(
        module, function, parameterArrays, statement, written);
  }
  return written;
}

VulkanPrototypeArrayWriteBackParameterMap
collectVulkanFunctionParameterArrayWriteBackParameters(
    const HIRModule &module, const HIRStage &stage) {
  VulkanPrototypeArrayWriteBackParameterMap parameters;
  auto collect = [&](const HIRFunction &function) {
    std::unordered_set<std::string> written =
        writtenVulkanFunctionParameterArrayNames(module, function);
    if (!written.empty()) {
      parameters[function.name] = std::move(written);
    }
  };
  for (const HIRFunction &function : module.functions) {
    collect(function);
  }
  for (const HIRFunction &function : stage.functions) {
    collect(function);
  }
  return parameters;
}

bool vulkanFunctionParameterArrayWriteArgumentAliases(
    const HIRFunction &callee, const HIRExpression &call,
    std::size_t parameterIndex) {
  if (call.children.size() <= parameterIndex) {
    return false;
  }
  const HIRExpression *writtenRoot =
      vulkanFunctionParameterArrayRootIdentifier(call.children[parameterIndex]);
  if (writtenRoot == nullptr) {
    return false;
  }

  for (std::size_t index = 0; index < callee.parameters.size(); ++index) {
    if (index == parameterIndex || call.children.size() <= index ||
        !callee.parameters[index].type.arraySize.has_value()) {
      continue;
    }
    const HIRExpression *otherRoot =
        vulkanFunctionParameterArrayRootIdentifier(call.children[index]);
    if (otherRoot != nullptr && otherRoot->value == writtenRoot->value) {
      return true;
    }
  }
  return false;
}

void collectUnsupportedVulkanPrototypeFunctionParameterArrayWriteLabels(
    const HIRModule &module, const HIRStage &stage, const HIRFunction &caller,
    const VulkanPrototypeArrayWriteBackParameterMap &writeBackParameters,
    std::set<std::string> &labels) {
  auto visitor = [&](const HIRExpression &expression) {
    if (expression.kind != HIRExpressionKind::Call) {
      return;
    }
    const HIRFunction *callee =
        findVulkanPrototypeCallableFunction(module, stage, expression.value);
    if (callee == nullptr) {
      return;
    }
    const auto written = writeBackParameters.find(callee->name);
    if (written == writeBackParameters.end()) {
      return;
    }

    const std::size_t argumentCount =
        std::min(expression.children.size(), callee->parameters.size());
    for (std::size_t index = 0; index < callee->parameters.size(); ++index) {
      const HIRParameter &parameter = callee->parameters[index];
      if (written->second.count(parameter.name) == 0) {
        continue;
      }
      const bool supportedArgument =
          index < argumentCount &&
          !vulkanFunctionParameterArrayWriteArgumentAliases(
              *callee, expression, index) &&
          vulkanStorageBufferFieldArrayWriteBackArgument(
              module, caller, expression.children[index], &stage);
      if (!supportedArgument) {
        labels.insert("caller '" + caller.name + "' -> callee '" +
                      callee->name + "' parameter '" + parameter.name +
                      "': written helper array parameters require a direct "
                      "non-aliased storage-buffer field array argument");
      }
    }
  };
  visitFunctionExpressions(caller, visitor);
}

bool diagnoseUnsupportedVulkanPrototypeFunctionParameterArrayWrites(
    const HIRModule &module, const HIRStage &stage,
    const VulkanPrototypeArrayWriteBackParameterMap &writeBackParameters,
    DiagnosticEngine &diagnostics) {
  if (writeBackParameters.empty()) {
    return false;
  }
  std::set<std::string> unsupportedLabels;
  for (const HIRFunction &function : module.functions) {
    collectUnsupportedVulkanPrototypeFunctionParameterArrayWriteLabels(
        module, stage, function, writeBackParameters, unsupportedLabels);
  }
  for (const HIRFunction &function : stage.functions) {
    collectUnsupportedVulkanPrototypeFunctionParameterArrayWriteLabels(
        module, stage, function, writeBackParameters, unsupportedLabels);
  }
  if (unsupportedLabels.empty()) {
    return false;
  }
  diagnostics.error(
      "vulkan.prototype-unsupported-function-parameter-array",
      "Vulkan prototype helper array parameter writes support only "
      "copy-in/copy-out for direct storage-buffer field array arguments; "
      "unsupported helper array write call(s): " +
          joinNames(unsupportedLabels));
  return true;
}

void appendUnsupportedVulkanPrototypeFunctionArrayCallFeatureLabels(
    std::set<std::string> &labels, std::string_view caller,
    std::string_view callee, std::string_view parameter,
    const HIRParameter &calleeParameter,
    const std::vector<HIRFunctionParameterArrayCallFeature> &features,
    const PrototypeConstantMap &constants) {
  for (HIRFunctionParameterArrayCallFeature feature : features) {
    const HIRFunctionParameterArrayCallFeatureSupport support =
        vulkanPrototypeFunctionParameterArrayCallFeatureSupport(
            calleeParameter, feature, constants);
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

void collectUnsupportedVulkanPrototypeFunctionArrayCallFeatureLabels(
    const HIRModule &module, const HIRStage &stage, const HIRFunction &caller,
    std::set<std::string> &labels) {
  const PrototypeConstantMap constants = prototypeConstants(module);
  auto visitor = [&](const HIRExpression &expression) {
    if (expression.kind != HIRExpressionKind::Call) {
      return;
    }
    const HIRFunction *callee =
        findVulkanPrototypeCallableFunction(module, stage, expression.value);
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
      const std::vector<HIRFunctionParameterArrayCallFeature> features =
          functionParameterArrayCallArgumentFeatures(
              module, caller, expression.children[index], &stage);
      appendUnsupportedVulkanPrototypeFunctionArrayCallFeatureLabels(
          labels, caller.name, callee->name, parameter.name, parameter,
          features, constants);
    }
  };
  visitFunctionExpressions(caller, visitor);
}

bool diagnoseUnsupportedVulkanPrototypeFunctionArrayCallFeatures(
    const HIRModule &module, const HIRStage &stage,
    DiagnosticEngine &diagnostics) {
  VulkanPrototypeResourceArrayParameterAliasMap aliases;
  if (!collectVulkanPrototypeResourceArrayParameterAliases(module, stage,
                                                          aliases,
                                                          &diagnostics)) {
    return true;
  }
  std::set<std::string> unsupportedLabels;
  for (const HIRFunction &function : module.functions) {
    collectUnsupportedVulkanPrototypeFunctionArrayCallFeatureLabels(
        module, stage, function, unsupportedLabels);
  }
  for (const HIRFunction &function : stage.functions) {
    collectUnsupportedVulkanPrototypeFunctionArrayCallFeatureLabels(
        module, stage, function, unsupportedLabels);
  }
  if (unsupportedLabels.empty()) {
    return false;
  }
  diagnostics.error(
      "vulkan.prototype-unsupported-function-parameter-array",
      "Vulkan prototype helper array calls do not support unsupported "
      "fixed-size helper array call feature(s): " +
          joinNames(unsupportedLabels) +
          "; the shared function-parameter array call ABI is value-copy "
          "read-only");
  return true;
}

bool prototypeLocalArrayElementAccessSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics,
    bool requireFoldedIndices) {
  const std::optional<PrototypeLocalArrayElementAccess> access =
      prototypeLocalArrayElementAccess(expression, locals);
  if (!access.has_value()) {
    return false;
  }

  if (!isPrototypeFunctionArrayParameterType(access->localType, constants)) {
    diagnostics.error(
        "vulkan.prototype-unsupported-function-parameter-array",
        "Vulkan prototype helper array indexing currently supports only "
        "fixed-size scalar/vector numeric arrays with folded dimensions, got '" +
            formatType(access->localType) + "'");
    return false;
  }

  const std::optional<HIRType> resultType =
      prototypeArrayTypeAfterIndexCount(access->localType,
                                        access->indices.size());
  if (!resultType.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-function-parameter-array",
                      "Vulkan prototype helper array indexing uses more "
                      "indices than array dimensions for '" +
                          formatType(access->localType) + "'");
    return false;
  }
  if (!samePrototypeType(expression.type, *resultType)) {
    diagnostics.error("vulkan.prototype-unsupported-type",
                      "Vulkan prototype helper array index result type does "
                      "not match the array element type");
    return false;
  }

  const std::vector<std::string_view> dimensions =
      prototypeArrayDimensions(*access->localType.arraySize);
  std::size_t dynamicIndexCount = 0;
  for (std::size_t index = 0; index < access->indices.size(); ++index) {
    const HIRExpression &indexExpression = *access->indices[index];
    if (!prototypeExpressionSupported(indexExpression, locals, resources,
                                      constants, structs, diagnostics)) {
      return false;
    }
    const HIRType indexType =
        prototypeExpressionType(indexExpression, locals, resources, constants);
    if (indexType.name != "int" || indexType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-function-parameter-array",
                        "Vulkan prototype helper array indices must be scalar "
                        "int values");
      return false;
    }
    const std::optional<std::size_t> staticIndex =
        prototypeStaticArrayIndexValue(indexExpression, constants);
    if (!staticIndex.has_value()) {
      ++dynamicIndexCount;
      if (!requireFoldedIndices) {
        continue;
      }
      diagnostics.error("vulkan.prototype-unsupported-function-parameter-array",
                        "Vulkan prototype helper array indexing in this native "
                        "slice requires folded constant indices");
      return false;
    }
    const std::optional<std::size_t> elementCount =
        prototypeArrayDimensionElementCount(dimensions[index], constants);
    if (elementCount.has_value() && *staticIndex >= *elementCount) {
      diagnostics.error("vulkan.prototype-unsupported-function-parameter-array",
                        "Vulkan prototype helper array index is out of bounds "
                        "for '" +
                            formatType(access->localType) + "'");
      return false;
    }
  }
  if (dynamicIndexCount > 0 &&
      (dynamicIndexCount != 1 || access->indices.size() <= 1 ||
       resultType->arraySize.has_value())) {
    diagnostics.error(
        "vulkan.prototype-unsupported-function-parameter-array",
        "Vulkan prototype dynamic helper array reads currently support only "
        "nested scalar or vector element results with one dynamic index");
    return false;
  }
  return true;
}

bool prototypeGLSLStd450IntrinsicCallSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  const std::optional<PrototypeIntrinsicLowering> lowering =
      prototypeIntrinsicLoweringForCall(expression);
  if (!lowering.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype intrinsic lowering currently supports "
                      "only the scalar/vector HIR math intrinsic subset");
    return false;
  }
  for (const HIRExpression &child : expression.children) {
    if (!prototypeExpressionSupported(child, locals, resources, constants,
                                      structs, diagnostics)) {
      return false;
    }
  }
  return true;
}

std::optional<HIRType> prototypeAtomicTargetValueType(
    const HIRExpression &target,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  auto checkTargetType = [&](const HIRType &atomicType)
      -> std::optional<HIRType> {
    const std::optional<HIRType> valueType =
        prototypeAtomicStorageValueType(atomicType);
    if (!valueType.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                        "Vulkan prototype atomicAdd targets must be "
                        "atomic<int> or atomic<uint> storage");
      return std::nullopt;
    }
    if (!target.type.name.empty() && !samePrototypeType(target.type, atomicType)) {
      diagnostics.error("vulkan.prototype-unsupported-type",
                        "Vulkan prototype atomicAdd target type '" +
                            formatType(target.type) +
                            "' does not match storage type '" +
                            formatType(atomicType) + "'");
      return std::nullopt;
    }
    return valueType;
  };

  auto checkPlainStorageBufferMemberTargetType =
      [&](const HIRType &fieldType) -> std::optional<HIRType> {
    const std::optional<HIRType> valueType =
        prototypeAtomicStoredValueType(fieldType, true);
    if (!valueType.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                        "Vulkan prototype storage-buffer member atomicAdd "
                        "targets must be int, uint, atomic<int>, or "
                        "atomic<uint>");
      return std::nullopt;
    }
    return valueType;
  };

  if (target.kind == HIRExpressionKind::Identifier) {
    const auto resource = resources.find(target.value);
    if (resource != resources.end() &&
        resource->second.kind == HIRResourceKind::Shared &&
        !resource->second.type.arraySize.has_value()) {
      return checkTargetType(resource->second.type);
    }
  }

  if (prototypeStorageBufferMemberAccessSupported(
          target, resources, locals, constants, structs, diagnostics)) {
    return checkPlainStorageBufferMemberTargetType(target.type);
  }
  if (diagnostics.hasErrors()) {
    return std::nullopt;
  }

  const std::optional<PrototypeStorageBufferIndexAccess> access =
      prototypeStorageBufferIndexAccess(target);
  if (!access.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                      "Vulkan prototype atomicAdd targets must be direct "
                      "storage-buffer or workgroup atomic elements");
    return std::nullopt;
  }

  const auto resource = resources.find(access->resourceName);
  if (resource == resources.end()) {
    diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                      "Vulkan prototype atomicAdd cannot resolve target "
                      "resource '" +
                          access->resourceName + "'");
    return std::nullopt;
  }

  HIRType atomicType;
  if (resource->second.kind == HIRResourceKind::Buffer) {
    atomicType = prototypeBufferElementType(resource->second);
    const bool resourceIsDescriptorArray =
        resource->second.type.arraySize.has_value();
    if (resourceIsDescriptorArray && access->descriptorIndex == nullptr) {
      diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                        "Vulkan prototype atomicAdd storage-buffer descriptor "
                        "arrays require descriptor and element indices");
      return std::nullopt;
    }
    if (!resourceIsDescriptorArray && access->descriptorIndex != nullptr) {
      diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                        "Vulkan prototype atomicAdd non-array storage buffers "
                        "support only one element index");
      return std::nullopt;
    }
    if (access->descriptorIndex != nullptr) {
      if (!prototypeExpressionSupported(*access->descriptorIndex, locals,
                                        resources, constants, structs,
                                        diagnostics)) {
        return std::nullopt;
      }
      const HIRType descriptorIndexType = prototypeExpressionType(
          *access->descriptorIndex, locals, resources, constants);
      if (descriptorIndexType.name != "int" ||
          descriptorIndexType.arraySize.has_value()) {
        diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                          "Vulkan prototype atomicAdd descriptor indices must "
                          "be scalar int values");
        return std::nullopt;
      }
    }
  } else if (resource->second.kind == HIRResourceKind::Shared) {
    if (access->descriptorIndex != nullptr) {
      diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                        "Vulkan prototype atomicAdd workgroup targets do not "
                        "use descriptor indices");
      return std::nullopt;
    }
    if (!resource->second.type.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                        "Vulkan prototype scalar workgroup atomicAdd targets "
                        "must be referenced by identifier");
      return std::nullopt;
    }
    atomicType = arrayElementType(resource->second.type);
  } else {
    diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                      "Vulkan prototype atomicAdd targets must be storage "
                      "buffer or workgroup storage");
    return std::nullopt;
  }

  if (access->elementIndex == nullptr ||
      !prototypeExpressionSupported(*access->elementIndex, locals, resources,
                                    constants, structs, diagnostics)) {
    return std::nullopt;
  }
  const HIRType indexType =
      prototypeExpressionType(*access->elementIndex, locals, resources,
                              constants);
  if (indexType.name != "int" || indexType.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                      "Vulkan prototype atomicAdd element indices must be "
                      "scalar int values");
    return std::nullopt;
  }

  return checkTargetType(atomicType);
}

bool prototypeAtomicIntegerStatementSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  if (!isPrototypeAtomicIntegerCall(expression)) {
    return false;
  }
  if (expression.children.size() != 2) {
    diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                      "Vulkan prototype integer atomic expects target and "
                      "value arguments");
    return false;
  }

  const std::optional<HIRType> valueType = prototypeAtomicTargetValueType(
      expression.children[0], locals, resources, constants, structs,
      diagnostics);
  if (!valueType.has_value()) {
    return false;
  }
  if (!expression.type.name.empty() && expression.type.name != "void" &&
      !samePrototypeType(expression.type, *valueType)) {
    diagnostics.error("vulkan.prototype-unsupported-type",
                      "Vulkan prototype integer atomic expression type '" +
                          formatType(expression.type) +
                          "' must match returned old-value type '" +
                          formatType(*valueType) + "'");
    return false;
  }
  if (!prototypeExpressionSupported(expression.children[1], locals, resources,
                                    constants, structs, diagnostics)) {
    return false;
  }
  const HIRType deltaType =
      prototypeExpressionType(expression.children[1], locals, resources,
                              constants);
  if (!samePrototypeType(deltaType, *valueType)) {
    diagnostics.error("vulkan.prototype-unsupported-type",
                      "Vulkan prototype integer atomic value type '" +
                          formatType(deltaType) +
                          "' must match atomic value type '" +
                          formatType(*valueType) + "'");
    return false;
  }
  return true;
}

bool prototypeAtomicIntegerCaptureSupported(
    const HIRExpression &expression, const HIRType &expectedValueType,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  if (!isPrototypeAtomicIntegerCall(expression)) {
    return false;
  }
  if (expression.children.size() != 2) {
    diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                      "Vulkan prototype integer atomic expects target and "
                      "value arguments");
    return false;
  }
  const std::optional<HIRType> valueType = prototypeAtomicTargetValueType(
      expression.children[0], locals, resources, constants, structs,
      diagnostics);
  if (!valueType.has_value()) {
    return false;
  }
  if (!samePrototypeType(expectedValueType, *valueType)) {
    diagnostics.error("vulkan.prototype-unsupported-type",
                      "Vulkan prototype integer atomic returned old-value "
                      "type '" +
                          formatType(*valueType) +
                          "' must match capture target type '" +
                          formatType(expectedValueType) + "'");
    return false;
  }
  if (!expression.type.name.empty() && expression.type.name != "void" &&
      !samePrototypeType(expression.type, *valueType)) {
    diagnostics.error("vulkan.prototype-unsupported-type",
                      "Vulkan prototype integer atomic expression type '" +
                          formatType(expression.type) +
                          "' must match returned old-value type '" +
                          formatType(*valueType) + "'");
    return false;
  }
  if (!prototypeExpressionSupported(expression.children[1], locals, resources,
                                    constants, structs, diagnostics)) {
    return false;
  }
  const HIRType deltaType =
      prototypeExpressionType(expression.children[1], locals, resources,
                              constants);
  if (!samePrototypeType(deltaType, *valueType)) {
    diagnostics.error("vulkan.prototype-unsupported-type",
                      "Vulkan prototype integer atomic value type '" +
                          formatType(deltaType) +
                          "' must match atomic value type '" +
                          formatType(*valueType) + "'");
    return false;
  }
  return true;
}

bool prototypeDescriptorExpressionSupported(
    const HIRExpression &expression,
    HIRResourceKind expectedKind,
    const std::unordered_map<std::string, HIRResource> &resources,
    const std::unordered_map<std::string, HIRType> &locals,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  if (expression.kind == HIRExpressionKind::Identifier) {
    const auto resource = resources.find(expression.value);
    if (resource == resources.end() || resource->second.kind != expectedKind) {
      diagnostics.error("vulkan.prototype-unsupported-resource",
                        "Vulkan prototype texture sampling cannot resolve "
                        "descriptor resource '" +
                            expression.value + "'");
      return false;
    }
    if (resource->second.type.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-resource",
                        "Vulkan prototype texture sampling requires indexed "
                        "access for descriptor array resource '" +
                            expression.value + "'");
      return false;
    }
    return true;
  }

  if (expression.kind == HIRExpressionKind::IndexAccess &&
      expression.children.size() >= 2 &&
      expression.children[0].kind == HIRExpressionKind::Identifier) {
    const std::string &resourceName = expression.children[0].value;
    const auto resource = resources.find(resourceName);
    if (resource == resources.end() || resource->second.kind != expectedKind) {
      diagnostics.error("vulkan.prototype-unsupported-resource",
                        "Vulkan prototype texture sampling cannot resolve "
                        "descriptor array resource '" +
                            resourceName + "'");
      return false;
    }
    if (!resource->second.type.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-resource",
                        "Vulkan prototype texture sampling cannot index "
                        "non-array descriptor resource '" +
                            resourceName + "'");
      return false;
    }
    if (!resource->second.type.arraySize->empty() &&
        !prototypeArrayElementCount(resource->second.type, constants)
             .has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-resource",
                        "Vulkan prototype texture sampling requires "
                        "fixed-size numeric or folded-constant descriptor "
                        "array sizes");
      return false;
    }
    if (!prototypeExpressionSupported(expression.children[1], locals, resources,
                                      constants, structs, diagnostics)) {
      return false;
    }
    const HIRType indexType =
        prototypeExpressionType(expression.children[1], locals, resources,
                                constants);
    if (indexType.name != "int" || indexType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-assignment-target",
                        "Vulkan prototype descriptor array indices must be "
                        "scalar int values");
      return false;
    }
    if (const auto local = locals.find(resourceName);
        local != locals.end() &&
        isVulkanPrototypeResourceArrayParameterType(local->second,
                                                    constants) &&
        !prototypeStaticArrayIndexValue(expression.children[1], constants)
             .has_value()) {
      diagnostics.error(
          "vulkan.prototype-unsupported-function-parameter-resource-array",
          "Vulkan prototype helper resource array indexing in this native "
          "slice requires literal or folded constant indices");
      return false;
    }
    return true;
  }

  diagnostics.error("vulkan.prototype-unsupported-resource",
                    "Vulkan prototype texture sampling supports only direct "
                    "descriptor resources or indexed descriptor arrays");
  return false;
}

bool prototypeStorageImageResourceSupported(
    const HIRExpression &imageExpression,
    const std::unordered_map<std::string, HIRResource> &resources,
    const std::unordered_map<std::string, HIRType> &locals,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  if (imageExpression.kind == HIRExpressionKind::Identifier) {
    const auto resource = resources.find(imageExpression.value);
    if (resource == resources.end() ||
        resource->second.kind != HIRResourceKind::StorageImage) {
      diagnostics.error("vulkan.prototype-unsupported-resource",
                        "Vulkan prototype storage image access cannot resolve "
                        "storage image resource '" +
                            imageExpression.value + "'");
      return false;
    }
    if (resource->second.type.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-resource",
                        "Vulkan prototype storage image access requires "
                        "indexed access for descriptor array resource '" +
                            imageExpression.value + "'");
      return false;
    }
    return true;
  }

  if (imageExpression.kind == HIRExpressionKind::IndexAccess &&
      imageExpression.children.size() >= 2 &&
      imageExpression.children[0].kind == HIRExpressionKind::Identifier) {
    const std::string &resourceName = imageExpression.children[0].value;
    const auto resource = resources.find(resourceName);
    if (resource == resources.end() ||
        resource->second.kind != HIRResourceKind::StorageImage) {
      diagnostics.error("vulkan.prototype-unsupported-resource",
                        "Vulkan prototype storage image access cannot resolve "
                        "storage image descriptor array resource '" +
                            resourceName + "'");
      return false;
    }
    if (!resource->second.type.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-resource",
                        "Vulkan prototype storage image access cannot index "
                        "non-array descriptor resource '" +
                            resourceName + "'");
      return false;
    }
    if (resource->second.type.arraySize->empty()) {
      diagnostics.error(
          "vulkan.prototype-unsupported-runtime-resource-array",
          "Vulkan prototype storage image descriptor arrays require "
          "fixed-size numeric or folded-constant resource array sizes");
      return false;
    }
    if (!prototypeArrayElementCount(resource->second.type, constants).has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-resource",
                        "Vulkan prototype storage image descriptor arrays "
                        "require fixed-size numeric or folded-constant "
                        "resource array sizes");
      return false;
    }
    if (!prototypeExpressionSupported(imageExpression.children[1], locals,
                                      resources, constants, structs,
                                      diagnostics)) {
      return false;
    }
    const HIRType indexType =
        prototypeExpressionType(imageExpression.children[1], locals, resources,
                                constants);
    if (indexType.name != "int" || indexType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-assignment-target",
                        "Vulkan prototype storage image descriptor array "
                        "indices must be scalar int values");
      return false;
    }
    return true;
  }

  diagnostics.error("vulkan.prototype-unsupported-resource",
                    "Vulkan prototype storage image access supports only "
                    "direct storage image resources or indexed descriptor "
                    "arrays");
  return false;
}

const HIRResource *prototypeStorageImageResource(
    const HIRExpression &imageExpression,
    const std::unordered_map<std::string, HIRResource> &resources) {
  const HIRExpression *current = &imageExpression;
  while ((current->kind == HIRExpressionKind::Group ||
          current->kind == HIRExpressionKind::NonUniform) &&
         current->children.size() == 1) {
    current = &current->children.front();
  }
  while (current->kind == HIRExpressionKind::IndexAccess &&
         !current->children.empty()) {
    current = &current->children.front();
    while ((current->kind == HIRExpressionKind::Group ||
            current->kind == HIRExpressionKind::NonUniform) &&
           current->children.size() == 1) {
      current = &current->children.front();
    }
  }
  if (current->kind != HIRExpressionKind::Identifier) {
    return nullptr;
  }
  const auto resource = resources.find(current->value);
  if (resource == resources.end() ||
      resource->second.kind != HIRResourceKind::StorageImage) {
    return nullptr;
  }
  return &resource->second;
}

bool prototypeStorageImageLoadSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  if (expression.children.size() != 2) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype imageLoad lowering requires image "
                      "and coordinate operands");
    return false;
  }
  const HIRExpression &image = expression.children[0];
  const HIRExpression &coordinates = expression.children[1];
  if (!prototypeStorageImageResourceSupported(image, resources, locals,
                                             constants, structs, diagnostics) ||
      !prototypeExpressionSupported(coordinates, locals, resources, constants,
                                    structs, diagnostics)) {
    return false;
  }

  const HIRType expectedCoordinateType =
      storageImageCoordinateType(image.type);
  const HIRType coordinateType =
      prototypeExpressionType(coordinates, locals, resources, constants);
  if (!samePrototypeType(coordinateType, expectedCoordinateType)) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype imageLoad coordinates for '" +
                          formatType(image.type) + "' must be " +
                          formatType(expectedCoordinateType));
    return false;
  }

  const HIRType expectedResultType = storageImagePayloadVectorType(image.type);
  if (!samePrototypeType(expression.type, expectedResultType)) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype imageLoad result for '" +
                          formatType(image.type) + "' must be " +
                          formatType(expectedResultType));
    return false;
  }
  return true;
}

bool prototypeStorageImageStoreSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  if (expression.children.size() != 3) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype imageStore lowering requires image, "
                      "coordinate, and value operands");
    return false;
  }
  if (!expression.type.name.empty() && expression.type.name != "void") {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype imageStore result must be void");
    return false;
  }

  const HIRExpression &image = expression.children[0];
  const HIRExpression &coordinates = expression.children[1];
  const HIRExpression &value = expression.children[2];
  if (!prototypeStorageImageResourceSupported(image, resources, locals,
                                             constants, structs, diagnostics) ||
      !prototypeExpressionSupported(coordinates, locals, resources, constants,
                                    structs, diagnostics) ||
      !prototypeExpressionSupported(value, locals, resources, constants,
                                    structs, diagnostics)) {
    return false;
  }

  const HIRType expectedCoordinateType =
      storageImageCoordinateType(image.type);
  const HIRType coordinateType =
      prototypeExpressionType(coordinates, locals, resources, constants);
  if (!samePrototypeType(coordinateType, expectedCoordinateType)) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype imageStore coordinates for '" +
                          formatType(image.type) + "' must be " +
                          formatType(expectedCoordinateType));
    return false;
  }

  const HIRType expectedValueType = storageImagePayloadVectorType(image.type);
  const HIRType valueType =
      prototypeExpressionType(value, locals, resources, constants);
  if (!samePrototypeType(valueType, expectedValueType)) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype imageStore value for '" +
                          formatType(image.type) + "' must be " +
                          formatType(expectedValueType));
    return false;
  }
  return true;
}

bool prototypeStorageImageAtomicSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  const std::optional<PrototypeAtomicIntegerOp> op =
      prototypeStorageImageAtomicOpForCall(expression);
  if (!op.has_value()) {
    return false;
  }
  if (expression.children.size() != 3) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype " + expression.value +
                          " lowering requires image, coordinate, and value "
                          "operands");
    return false;
  }

  const HIRExpression &image = expression.children[0];
  const HIRExpression &coordinates = expression.children[1];
  const HIRExpression &value = expression.children[2];
  if (!prototypeStorageImageResourceSupported(image, resources, locals,
                                             constants, structs, diagnostics) ||
      !prototypeExpressionSupported(coordinates, locals, resources, constants,
                                    structs, diagnostics) ||
      !prototypeExpressionSupported(value, locals, resources, constants,
                                    structs, diagnostics)) {
    return false;
  }

  const std::string imageTypeName = baseTypeName(image.type);
  if (!isSignedIntegerStorageImageResourceType(imageTypeName) &&
      !isUnsignedIntegerStorageImageResourceType(imageTypeName)) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype " + expression.value +
                          " requires a signed or unsigned integer storage "
                          "image");
    return false;
  }

  const HIRResource *resource = prototypeStorageImageResource(image, resources);
  if (resource == nullptr) {
    diagnostics.error("vulkan.prototype-unsupported-resource",
                      "Vulkan prototype storage image atomic cannot resolve "
                      "storage image resource");
    return false;
  }
  const std::string format = resolvedStorageImageFormatName(*resource);
  if (!storageImageAccessAllowsRead(resource->storageImageAccess) ||
      !storageImageAccessAllowsWrite(resource->storageImageAccess) ||
      !storageImageFormatSupportsAtomics(format, imageTypeName)) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype " + expression.value +
                          " requires read-write r32i/r32ui storage images");
    return false;
  }

  const HIRType expectedCoordinateType = storageImageCoordinateType(image.type);
  const HIRType coordinateType =
      prototypeExpressionType(coordinates, locals, resources, constants);
  if (!samePrototypeType(coordinateType, expectedCoordinateType)) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype " + expression.value +
                          " coordinates for '" + formatType(image.type) +
                          "' must be " + formatType(expectedCoordinateType));
    return false;
  }

  const HIRType expectedValueType = storageImageAtomicPayloadType(image.type);
  const HIRType valueType =
      prototypeExpressionType(value, locals, resources, constants);
  if (!samePrototypeType(valueType, expectedValueType)) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype " + expression.value +
                          " value for '" + formatType(image.type) +
                          "' must be " + formatType(expectedValueType));
    return false;
  }

  if (!samePrototypeType(expression.type, expectedValueType)) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype " + expression.value +
                          " result for '" + formatType(image.type) +
                          "' must be " + formatType(expectedValueType));
    return false;
  }
  return true;
}

bool prototypeStorageImageAtomicCaptureSupported(
    const HIRExpression &expression, const HIRType &expectedValueType,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  if (!prototypeStorageImageAtomicSupported(expression, locals, resources,
                                           constants, structs, diagnostics)) {
    return false;
  }
  if (!samePrototypeType(expectedValueType, expression.type)) {
    diagnostics.error("vulkan.prototype-unsupported-type",
                      "Vulkan prototype storage image atomic returned "
                      "old-value type '" +
                          formatType(expression.type) +
                          "' must match capture target type '" +
                          formatType(expectedValueType) + "'");
    return false;
  }
  return true;
}

bool prototypeTextureSampleSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  const bool explicitLod = isPrototypeExplicitLodTextureSample(expression);
  const bool implicitSamplerSample =
      isPrototypeImplicitSamplerTextureSample(expression);
  if (!explicitLod && !implicitSamplerSample) {
    diagnostics.error("vulkan.prototype-implicit-lod-compute",
                      "Vulkan compute texture sampling requires explicit lod; "
                      "use textureLod(texture, sampler, coordinates, lod)");
    return false;
  }
  const std::size_t expectedOperands = explicitLod ? 4 : 3;
  if (expression.children.size() != expectedOperands) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      explicitLod
                          ? "Vulkan prototype textureLod lowering currently "
                            "requires texture, sampler, coordinates, and lod "
                            "operands"
                          : "Vulkan prototype .sample lowering currently "
                            "requires texture, sampler, and coordinates "
                            "operands");
    return false;
  }
  if (!prototypeDescriptorExpressionSupported(
          expression.children[0], HIRResourceKind::Texture, resources, locals,
          constants, structs, diagnostics) ||
      !prototypeDescriptorExpressionSupported(
          expression.children[1], HIRResourceKind::Sampler, resources, locals,
          constants, structs, diagnostics)) {
    return false;
  }
  if (!prototypeExpressionSupported(expression.children[2], locals, resources,
                                    constants, structs, diagnostics) ||
      (explicitLod &&
       !prototypeExpressionSupported(expression.children[3], locals, resources,
                                     constants, structs, diagnostics))) {
    return false;
  }
  const HIRType coordinateType =
      prototypeExpressionType(expression.children[2], locals, resources,
                              constants);
  const std::string expectedCoordinateType =
      prototypeTextureCoordinateType(expression.children[0].type);
  if (expectedCoordinateType.empty()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureLod currently supports only "
                      "2D, 3D, and cube texture coordinates");
    return false;
  }
  if (coordinateType.name != expectedCoordinateType ||
      coordinateType.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureLod coordinates for '" +
                          formatType(expression.children[0].type) +
                          "' must be " + expectedCoordinateType);
    return false;
  }
  if (explicitLod) {
    const HIRType lodType =
        prototypeExpressionType(expression.children[3], locals, resources,
                                constants);
    if (lodType.name != "float" || lodType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype textureLod lod operand must be a "
                        "scalar float");
      return false;
    }
  }
  const HIRType expectedResult =
      textureSampleResultType(expression.children[0].type);
  if (!samePrototypeType(expression.type, expectedResult)) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype texture sample result for '" +
                          formatType(expression.children[0].type) +
                          "' must be " + formatType(expectedResult));
    return false;
  }
  return true;
}

bool prototypeTextureCompareSupported(const HIRExpression &expression,
                                      const std::unordered_map<std::string, HIRType> &locals,
                                      const std::unordered_map<std::string, HIRResource> &resources,
                                      const PrototypeConstantMap &constants,
                                      const PrototypeStructMap &structs,
                                      DiagnosticEngine &diagnostics) {
  const bool explicitLod = isPrototypeExplicitLodTextureCompare(expression);
  const std::size_t expectedOperands = explicitLod ? 5 : 4;
  if (expression.children.size() != expectedOperands) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      explicitLod
                          ? "Vulkan prototype textureCompareLod lowering "
                            "requires texture, sampler, coordinates, depth, "
                            "and lod operands"
                          : "Vulkan prototype textureCompare lowering "
                            "requires texture, sampler, coordinates, and "
                            "depth operands");
    return false;
  }
  if (!isComparisonTextureType(expression.children[0].type.name)) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureCompare requires a comparison "
                      "texture operand");
    return false;
  }
  if (!prototypeDescriptorExpressionSupported(
          expression.children[0], HIRResourceKind::Texture, resources, locals,
          constants, structs, diagnostics) ||
      !prototypeDescriptorExpressionSupported(
          expression.children[1], HIRResourceKind::Sampler, resources, locals,
          constants, structs, diagnostics)) {
    return false;
  }
  if (!prototypeExpressionSupported(expression.children[2], locals, resources,
                                    constants, structs, diagnostics) ||
      !prototypeExpressionSupported(expression.children[3], locals, resources,
                                    constants, structs, diagnostics) ||
      (explicitLod &&
       !prototypeExpressionSupported(expression.children[4], locals, resources,
                                     constants, structs, diagnostics))) {
    return false;
  }
  const HIRType coordinateType =
      prototypeExpressionType(expression.children[2], locals, resources,
                              constants);
  const std::string expectedCoordinateType =
      prototypeTextureCoordinateType(expression.children[0].type);
  if (expectedCoordinateType.empty()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureCompare currently supports "
                      "2D, 2D-array, cube, and cube-array coordinates");
    return false;
  }
  if (coordinateType.name != expectedCoordinateType ||
      coordinateType.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureCompare coordinates for '" +
                          formatType(expression.children[0].type) +
                          "' must be " + expectedCoordinateType);
    return false;
  }
  const HIRType depthType =
      prototypeExpressionType(expression.children[3], locals, resources,
                              constants);
  if (depthType.name != "float" || depthType.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureCompare depth operand must be "
                      "a scalar float");
    return false;
  }
  if (explicitLod) {
    const HIRType lodType =
        prototypeExpressionType(expression.children[4], locals, resources,
                                constants);
    if (lodType.name != "float" || lodType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype textureCompareLod lod operand must "
                        "be a scalar float");
      return false;
    }
  }
  if (expression.type.name != "float" || expression.type.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureCompare result must be float");
    return false;
  }
  return true;
}

bool prototypeTextureCompareManualSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  const std::optional<TextureCompareManualOperands> operands =
      textureCompareManualOperands(expression);
  if (!operands.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureCompareLodManual lowering "
                      "requires texture, sampler, coordinates, depth, lod, "
                      "and compare-op operands");
    return false;
  }
  if (!isComparisonTextureType(operands->texture->type.name)) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureCompareLodManual requires a "
                      "comparison texture operand");
    return false;
  }
  if (!prototypeDescriptorExpressionSupported(
          *operands->texture, HIRResourceKind::Texture, resources, locals,
          constants, structs, diagnostics) ||
      !prototypeDescriptorExpressionSupported(
          *operands->sampler, HIRResourceKind::Sampler, resources, locals,
          constants, structs, diagnostics)) {
    return false;
  }
  if (!prototypeExpressionSupported(*operands->coordinate, locals, resources,
                                    constants, structs, diagnostics) ||
      !prototypeExpressionSupported(*operands->depth, locals, resources,
                                    constants, structs, diagnostics) ||
      !prototypeExpressionSupported(*operands->lod, locals, resources,
                                    constants, structs, diagnostics)) {
    return false;
  }

  const HIRType coordinateType =
      prototypeExpressionType(*operands->coordinate, locals, resources,
                              constants);
  const std::string expectedCoordinateType =
      prototypeTextureCoordinateType(operands->texture->type);
  if (expectedCoordinateType.empty()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureCompareLodManual currently "
                      "supports 2D, 2D-array, cube, and cube-array coordinates");
    return false;
  }
  if (coordinateType.name != expectedCoordinateType ||
      coordinateType.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureCompareLodManual coordinates "
                      "for '" +
                          formatType(operands->texture->type) +
                          "' must be " + expectedCoordinateType);
    return false;
  }

  const HIRType depthType =
      prototypeExpressionType(*operands->depth, locals, resources, constants);
  if (depthType.name != "float" || depthType.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureCompareLodManual depth operand "
                      "must be a scalar float");
    return false;
  }

  const HIRType lodType =
      prototypeExpressionType(*operands->lod, locals, resources, constants);
  if (lodType.name != "float" || lodType.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureCompareLodManual lod operand "
                      "must be a scalar float");
    return false;
  }

  if (operands->offset != nullptr || operands->gather2x2 ||
      operands->kernelTapCount != 0) {
    if (!isManualCompareOffsetTextureType(operands->texture->type.name)) {
      const std::string operation =
          textureCompareManualOperationName(*operands);
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype " + operation +
                            " currently supports only sampler2DShadow and "
                            "sampler2DArrayShadow textures");
      return false;
    }
  }
  if (operands->offset != nullptr) {
    if (!staticIvec2TextureOffset(*operands->offset).has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype textureCompareLodManualOffset "
                        "requires a static ivec2 integer literal offset");
      return false;
    }
  }
  if (operands->kernelTapCount != 0) {
    const std::string operation =
        textureCompareManualOperationName(*operands);
    for (std::size_t index = 0; index < operands->kernelTapCount; ++index) {
      if (!staticIvec2TextureOffset(*operands->kernelOffsets[index])
               .has_value()) {
        diagnostics.error("vulkan.prototype-unsupported-expression",
                          "Vulkan prototype " + operation +
                              " requires static ivec2 integer literal offsets");
        return false;
      }
      if (!prototypeExpressionSupported(*operands->kernelWeights[index],
                                        locals, resources, constants, structs,
                                        diagnostics)) {
        return false;
      }
      const HIRType weightType =
          prototypeExpressionType(*operands->kernelWeights[index], locals,
                                  resources, constants);
      if (weightType.name != "float" || weightType.arraySize.has_value()) {
        diagnostics.error("vulkan.prototype-unsupported-expression",
                          "Vulkan prototype " + operation +
                              " weight operands must be scalar float values");
        return false;
      }
    }
  }

  if (expression.type.name != "float" || expression.type.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureCompareLodManual result must "
                      "be float");
    return false;
  }

  if (!textureCompareOperatorFromExpression(*operands->compareOp)
           .has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype textureCompareLodManual compare-op "
                      "operand must be one of " +
                          std::string(textureCompareOperatorList()));
    return false;
  }
  return true;
}

bool prototypeExpressionSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  switch (expression.kind) {
  case HIRExpressionKind::Literal:
    if (!expression.type.arraySize.has_value() &&
        expression.type.name == "bool" &&
        (expression.value == "true" || expression.value == "false")) {
      return true;
    }
    if (isPrototypeArithmeticType(expression.type)) {
      return true;
    }
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype binary emission supports only scalar "
                      "int/float/bool literals");
    return false;
  case HIRExpressionKind::Identifier:
    if (expression.value == "true" || expression.value == "false") {
      return true;
    }
    if (locals.contains(expression.value)) {
      return true;
    }
    if (isPrototypeComputeBuiltinIdentifier(expression.value)) {
      const HIRType builtinType = prototypeComputeBuiltinType();
      if (expression.type.name.empty() ||
          samePrototypeType(expression.type, builtinType)) {
        return true;
      }
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype compute invocation builtin '" +
                            expression.value + "' must have type '" +
                            formatType(builtinType) + "'");
      return false;
    }
    if (auto constant = constants.find(expression.value);
        constant != constants.end()) {
      if (isPrototypeConstantSupported(constant->second)) {
        return true;
      }
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype binary emission supports only "
                        "folded scalar constants");
      return false;
    }
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype binary emission cannot resolve local "
                      "value '" +
                          expression.value + "'");
    return false;
  case HIRExpressionKind::Group:
    if (expression.children.empty()) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype binary emission does not support "
                        "empty grouped expressions");
      return false;
    }
    return prototypeExpressionSupported(expression.children.front(), locals,
                                        resources, constants, structs,
                                        diagnostics);
  case HIRExpressionKind::Unary: {
    if (expression.children.empty() ||
        (expression.value != "+" && expression.value != "-")) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype binary emission supports only unary "
                        "+ and -");
      return false;
    }
    if (!prototypeExpressionSupported(expression.children.front(), locals,
                                      resources, constants, structs,
                                      diagnostics)) {
      return false;
    }
    const HIRType operandType =
        prototypeExpressionType(expression.children.front(), locals, resources,
                                constants);
    if (!isPrototypeArithmeticType(operandType)) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype binary emission supports unary "
                        "operations only on int/float values");
      return false;
    }
    return true;
  }
  case HIRExpressionKind::Binary: {
    if (expression.children.size() < 2 ||
        (!isPrototypeArithmeticOperator(expression.value) &&
         !isPrototypeComparisonOperator(expression.value))) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype binary emission supports only scalar/vector "
                        "arithmetic and comparison expressions");
      return false;
    }
    if (!prototypeExpressionSupported(expression.children[0], locals, resources,
                                      constants, structs, diagnostics) ||
        !prototypeExpressionSupported(expression.children[1], locals, resources,
                                      constants, structs, diagnostics)) {
      return false;
    }
    const HIRType leftType =
        prototypeExpressionType(expression.children[0], locals, resources,
                                constants);
    const HIRType rightType =
        prototypeExpressionType(expression.children[1], locals, resources,
                                constants);
    const std::optional<PrototypeMatrixMultiplyLowering> matrixMultiply =
        expression.value == "*"
            ? prototypeMatrixMultiplyLowering(leftType, rightType,
                                              expression.type)
            : std::nullopt;
    if (!matrixMultiply.has_value() &&
        (!isPrototypeArithmeticType(leftType) ||
         !isPrototypeArithmeticType(rightType))) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype binary emission supports only "
                        "numeric operands or float matrix multiplication");
      return false;
    }
    if (isPrototypeArithmeticOperator(expression.value)) {
      if (matrixMultiply.has_value()) {
        return true;
      }
      if (samePrototypeType(leftType, rightType)) {
        if (!samePrototypeType(leftType, expression.type)) {
          diagnostics.error("vulkan.prototype-unsupported-expression",
                            "Vulkan prototype binary emission arithmetic "
                            "result type does not match operand type");
          return false;
        }
      } else if (!isPrototypeFloatVectorScalarArithmetic(leftType, rightType,
                                                        expression.type)) {
        diagnostics.error(
            "vulkan.prototype-unsupported-expression",
            "Vulkan prototype vector-scalar arithmetic supports only float "
            "vec2/vec3/vec4 with scalar float operands; explicit numeric casts "
            "are not inserted yet");
        return false;
      }
    } else {
      if (!samePrototypeType(leftType, rightType)) {
        diagnostics.error("vulkan.prototype-unsupported-expression",
                          "Vulkan prototype binary comparison operands must "
                          "have matching numeric types");
        return false;
      }
      if (isPrototypeVectorType(leftType) || expression.type.name != "bool") {
        diagnostics.error("vulkan.prototype-unsupported-expression",
                          "Vulkan prototype binary emission supports "
                          "comparisons only for scalar numeric values");
        return false;
      }
    }
    return true;
  }
  case HIRExpressionKind::IndexAccess:
    if (prototypeLocalArrayElementAccessSupported(
            expression, locals, resources, constants, structs, diagnostics,
            false)) {
      return true;
    }
    if (diagnostics.hasErrors()) {
      return false;
    }
    if (prototypeStorageBufferMemberAccessSupported(
            expression, resources, locals, constants, structs, diagnostics,
            expression.type.arraySize.has_value())) {
      return true;
    }
    if (diagnostics.hasErrors()) {
      return false;
    }
    return prototypeResourceIndexSupported(expression, resources, locals,
                                          constants, structs, diagnostics);
  case HIRExpressionKind::MemberAccess: {
    if (prototypeUniformBufferMemberAccessSupported(
            expression, resources, locals, constants, structs, diagnostics,
            expression.type.arraySize.has_value())) {
      return true;
    }
    if (diagnostics.hasErrors()) {
      return false;
    }
    if (prototypeStorageBufferMemberAccessSupported(
            expression, resources, locals, constants, structs, diagnostics,
            expression.type.arraySize.has_value())) {
      return true;
    }
    if (diagnostics.hasErrors()) {
      return false;
    }
    if (expression.children.empty()) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype member access requires a base "
                        "expression");
      return false;
    }
    if (!prototypeExpressionSupported(expression.children.front(), locals,
                                      resources, constants, structs,
                                      diagnostics)) {
      return false;
    }
    const HIRType baseType =
        prototypeExpressionType(expression.children.front(), locals, resources,
                                constants);
    const std::optional<std::vector<std::size_t>> indices =
        prototypeVectorMemberIndices(baseType, expression.value);
    if (!indices.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype member access supports only float-vector "
                        "swizzles using xyzw/rgba/stpq components");
      return false;
    }
    if (indices->size() == 1) {
      const HIRType componentType = prototypeVectorComponentType(baseType);
      if (!samePrototypeType(expression.type, componentType)) {
        diagnostics.error("vulkan.prototype-unsupported-expression",
                          "Vulkan prototype single-component vector swizzles "
                          "must produce the vector component type");
        return false;
      }
      return true;
    }
    const std::optional<std::size_t> resultWidth =
        prototypeVectorWidth(expression.type);
    if (!resultWidth.has_value() || *resultWidth != indices->size() ||
        !samePrototypeType(prototypeVectorComponentType(expression.type),
                           prototypeVectorComponentType(baseType))) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype multi-component vector swizzles "
                        "must produce matching vector values");
      return false;
    }
    return true;
  }
  case HIRExpressionKind::Constructor: {
    if (isPrototypeNumericScalarType(expression.type)) {
      if (expression.value != expression.type.name ||
          expression.children.size() != 1) {
        diagnostics.error(
            "vulkan.prototype-unsupported-expression",
            "Vulkan prototype scalar numeric constructors require exactly one "
            "operand and a constructor name matching the result type");
        return false;
      }
      if (!prototypeExpressionSupported(expression.children.front(), locals,
                                        resources, constants, structs,
                                        diagnostics)) {
        return false;
      }
      const HIRType sourceType =
          prototypeExpressionType(expression.children.front(), locals,
                                  resources, constants);
      if (prototypeScalarConversionOpcode(sourceType, expression.type).empty()) {
        diagnostics.error(
            "vulkan.prototype-unsupported-expression",
            "Vulkan prototype scalar numeric constructors currently support "
            "same-type values plus int/uint-to-float and float-to-int/uint "
            "conversions");
        return false;
      }
      return true;
    }

    for (const HIRExpression &child : expression.children) {
      if (!prototypeExpressionSupported(child, locals, resources, constants,
                                        structs, diagnostics)) {
        return false;
      }
    }
    if (isPrototypeMatrixType(expression.type)) {
      return prototypeMatrixConstructorSupported(expression, diagnostics);
    }
    return prototypeVectorConstructorSupported(expression, diagnostics);
  }
  case HIRExpressionKind::NonUniform: {
    if (expression.children.size() != 1) {
      diagnostics.error("vulkan.prototype-unsupported-nonuniform-index",
                        "Vulkan prototype nonuniform descriptor index markers "
                        "require exactly one operand");
      return false;
    }
    if (!prototypeExpressionSupported(expression.children.front(), locals,
                                      resources, constants, structs,
                                      diagnostics)) {
      return false;
    }
    const HIRType indexType =
        prototypeExpressionType(expression.children.front(), locals, resources,
                                constants);
    if (indexType.name != "int" || indexType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-nonuniform-index",
                        "Vulkan prototype nonuniform descriptor indices must "
                        "be scalar int values");
      return false;
    }
    return true;
  }
  case HIRExpressionKind::Call:
    if (isPrototypeImageLoadCall(expression)) {
      return prototypeStorageImageLoadSupported(
          expression, locals, resources, constants, structs, diagnostics);
    }
    if (isPrototypeImageStoreCall(expression)) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype imageStore can be lowered only as "
                        "an expression statement");
      return false;
    }
    if (isPrototypeStorageImageAtomicCall(expression)) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype storage image atomics can be "
                        "lowered only as expression statements or as exact "
                        "declaration/assignment RHS captures");
      return false;
    }
    if (isPrototypeAtomicIntegerCall(expression)) {
      diagnostics.error("vulkan.prototype-unsupported-atomic-add",
                        "Vulkan prototype integer atomics can be lowered only "
                        "as expression statements or as exact declaration/"
                        "assignment RHS captures");
      return false;
    }
    if (isPrototypeWorkgroupBarrierCall(expression)) {
      return prototypeWorkgroupBarrierCallSupported(expression, diagnostics);
    }
    if (prototypeIntrinsicLoweringForCall(expression).has_value()) {
      return prototypeGLSLStd450IntrinsicCallSupported(
          expression, locals, resources, constants, structs, diagnostics);
    }
    for (const HIRExpression &child : expression.children) {
      if (isPrototypeDirectResourceArrayArgument(child, resources)) {
        continue;
      }
      if (!prototypeExpressionSupported(child, locals, resources, constants,
                                        structs, diagnostics)) {
        return false;
      }
    }
    if (expression.type.name == "void" || expression.type.name.empty() ||
        isPrototypeLocalType(expression.type)) {
      return true;
    }
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype helper calls currently return only "
                      "void or scalar/vector numeric values");
    return false;
  case HIRExpressionKind::Select: {
    if (expression.children.size() != 3) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype select expressions require a "
                        "condition plus true and false values");
      return false;
    }
    if (!isPrototypeLocalType(expression.type)) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype select expressions support only "
                        "scalar and vector result types");
      return false;
    }
    for (const HIRExpression &child : expression.children) {
      if (!prototypeExpressionSupported(child, locals, resources, constants,
                                        structs, diagnostics)) {
        return false;
      }
    }

    const HIRType conditionType =
        prototypeExpressionType(expression.children[0], locals, resources,
                                constants);
    if (conditionType.name != "bool" || conditionType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-expression",
                        "Vulkan prototype select conditions must be scalar "
                        "bool values");
      return false;
    }

    const HIRType trueType =
        prototypeExpressionType(expression.children[1], locals, resources,
                                constants);
    const HIRType falseType =
        prototypeExpressionType(expression.children[2], locals, resources,
                                constants);
    if (!samePrototypeType(expression.type, trueType) ||
        !samePrototypeType(expression.type, falseType)) {
      diagnostics.error("vulkan.prototype-unsupported-type",
                        "Vulkan prototype select arms must match the result "
                        "type");
      return false;
    }
    return true;
  }
  case HIRExpressionKind::Empty:
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype binary emission does not lower '" +
                          expressionKindName(expression.kind) +
                          "' expressions yet");
    return false;
  case HIRExpressionKind::TextureSample:
    return prototypeTextureSampleSupported(expression, locals, resources,
                                           constants, structs, diagnostics);
  case HIRExpressionKind::TextureCompare:
    return prototypeTextureCompareSupported(expression, locals, resources,
                                           constants, structs, diagnostics);
  case HIRExpressionKind::TextureCompareLodManual:
    return prototypeTextureCompareManualSupported(
        expression, locals, resources, constants, structs, diagnostics);
  }
  return false;
}

bool prototypeStorageBufferMemberAccessSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRResource> &resources,
    const std::unordered_map<std::string, HIRType> &locals,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics,
    bool allowArrayLeaf) {
  const std::optional<PrototypeStructMemberChain> chain =
      prototypeStructMemberChain(expression);
  if (!chain.has_value()) {
    return false;
  }

  const HIRExpression *base = prototypeStructMemberChainBase(*chain);
  if (base == nullptr || base->kind != HIRExpressionKind::Identifier) {
    return false;
  }

  const std::string &resourceName = base->value;
  const auto resource = resources.find(resourceName);
  if (resource == resources.end() ||
      !isPrototypeStructStorageBufferResourceForSupport(resource->second)) {
    return false;
  }
  const bool isRuntimeArrayBlock = prototypeStorageBufferIsRuntimeArrayBlock(
      resource->second, structs, constants);
  const std::optional<PrototypeStructStorageBufferAccess> access =
      prototypeStructStorageBufferAccess(*chain, resource->second.type,
                                         isRuntimeArrayBlock, resourceName,
                                         &diagnostics);
  if (!access.has_value()) {
    return false;
  }

  const std::optional<PrototypeResolvedStructFieldPath> fieldPath =
      resolvePrototypeStructFieldPath(prototypeBufferElementType(resource->second),
                                      access->fieldSteps, structs, constants,
                                      &diagnostics, allowArrayLeaf);
  if (!fieldPath.has_value()) {
    return false;
  }
  if (!samePrototypeType(fieldPath->valueType, expression.type)) {
    diagnostics.error("vulkan.prototype-unsupported-type",
                      "Vulkan prototype struct storage-buffer field access "
                      "resolved to type '" +
                          formatType(fieldPath->valueType) +
                          "' but HIR expected '" + formatType(expression.type) +
                          "'");
    return false;
  }
  if (access->descriptorIndex != nullptr) {
    if (!prototypeExpressionSupported(*access->descriptorIndex, locals,
                                      resources, constants, structs,
                                      diagnostics)) {
      return false;
    }
    const HIRType descriptorIndexType =
        prototypeExpressionType(*access->descriptorIndex, locals, resources,
                                constants);
    if (descriptorIndexType.name != "int" ||
        descriptorIndexType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-struct-buffer",
                        "Vulkan prototype struct storage-buffer descriptor "
                        "indices must be scalar int values");
      return false;
    }
  }
  if (access->elementIndex != nullptr) {
    if (!prototypeExpressionSupported(*access->elementIndex, locals, resources,
                                      constants, structs, diagnostics)) {
      return false;
    }
    const HIRType elementIndexType =
        prototypeExpressionType(*access->elementIndex, locals, resources,
                                constants);
    if (elementIndexType.name != "int" ||
        elementIndexType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-struct-buffer",
                        "Vulkan prototype struct storage-buffer element "
                        "indices must be scalar int values");
      return false;
    }
  }
  if (access->runtimeBlockIndex != nullptr) {
    if (!prototypeExpressionSupported(*access->runtimeBlockIndex, locals,
                                      resources, constants, structs,
                                      diagnostics)) {
      return false;
    }
    const HIRType runtimeBlockIndexType =
        prototypeExpressionType(*access->runtimeBlockIndex, locals, resources,
                                constants);
    if (runtimeBlockIndexType.name != "int" ||
        runtimeBlockIndexType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-struct-buffer",
                        "Vulkan prototype runtime-array storage-buffer block "
                        "indices must be scalar int values");
      return false;
    }
  }
  for (const PrototypeResolvedAccessIndex &accessIndex : fieldPath->indices) {
    if (accessIndex.dynamicIndex == nullptr) {
      continue;
    }
    if (!prototypeExpressionSupported(*accessIndex.dynamicIndex, locals, resources,
                                      constants, structs, diagnostics)) {
      return false;
    }
    const HIRType accessIndexType = prototypeExpressionType(
        *accessIndex.dynamicIndex, locals, resources, constants);
    if (accessIndexType.name != "int" || accessIndexType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-struct-array-field",
                        "Vulkan prototype struct storage-buffer array indices "
                        "must be scalar int values");
      return false;
    }
  }
  return true;
}

bool prototypeUniformBufferMemberAccessSupported(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRResource> &resources,
    const std::unordered_map<std::string, HIRType> &locals,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics,
    bool allowArrayLeaf) {
  const std::optional<PrototypeStructMemberChain> chain =
      prototypeStructMemberChain(expression);
  if (!chain.has_value()) {
    return false;
  }

  const HIRExpression *base = prototypeStructMemberChainBase(*chain);
  if (base == nullptr || base->kind != HIRExpressionKind::Identifier) {
    return false;
  }

  const std::string &resourceName = base->value;
  const auto resource = resources.find(resourceName);
  if (resource == resources.end() ||
      !isPrototypeStructUniformBufferResourceForSupport(resource->second,
                                                        structs)) {
    return false;
  }

  const std::optional<PrototypeStructUniformBufferAccess> access =
      prototypeStructUniformBufferAccess(*chain, resource->second.type,
                                         resourceName, &diagnostics);
  if (!access.has_value()) {
    return false;
  }

  const std::optional<PrototypeResolvedStructFieldPath> fieldPath =
      resolvePrototypeStructFieldPath(
          prototypeUniformBufferElementType(resource->second),
          access->fieldSteps, structs, constants, &diagnostics,
          allowArrayLeaf);
  if (!fieldPath.has_value()) {
    return false;
  }
  if (!samePrototypeType(fieldPath->valueType, expression.type)) {
    diagnostics.error("vulkan.prototype-unsupported-type",
                      "Vulkan prototype uniform-buffer field access resolved "
                      "to type '" +
                          formatType(fieldPath->valueType) +
                          "' but HIR expected '" +
                          formatType(expression.type) + "'");
    return false;
  }

  if (access->descriptorIndex != nullptr) {
    if (access->descriptorIndex->kind == HIRExpressionKind::NonUniform) {
      diagnostics.error(
          "vulkan.prototype-unsupported-nonuniform-index",
          "Vulkan prototype uniform-buffer descriptor arrays do not yet "
          "support nonuniform descriptor indices");
      return false;
    }
    if (!prototypeExpressionSupported(*access->descriptorIndex, locals,
                                      resources, constants, structs,
                                      diagnostics)) {
      return false;
    }
    const HIRType descriptorIndexType =
        prototypeExpressionType(*access->descriptorIndex, locals, resources,
                                constants);
    if (descriptorIndexType.name != "int" ||
        descriptorIndexType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-uniform-buffer",
                        "Vulkan prototype uniform-buffer descriptor indices "
                        "must be scalar int values");
      return false;
    }
  }

  for (const PrototypeResolvedAccessIndex &accessIndex : fieldPath->indices) {
    if (accessIndex.dynamicIndex == nullptr) {
      continue;
    }
    if (!prototypeExpressionSupported(*accessIndex.dynamicIndex, locals,
                                      resources, constants, structs,
                                      diagnostics)) {
      return false;
    }
    const HIRType accessIndexType = prototypeExpressionType(
        *accessIndex.dynamicIndex, locals, resources, constants);
    if (accessIndexType.name != "int" || accessIndexType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-struct-array-field",
                        "Vulkan prototype uniform-buffer array indices must "
                        "be scalar int values");
      return false;
    }
  }
  return true;
}

bool prototypeResourceIndexSupported(
    const HIRExpression &target,
    const std::unordered_map<std::string, HIRResource> &resources,
    const std::unordered_map<std::string, HIRType> &locals,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  const std::optional<PrototypeStorageBufferIndexAccess> access =
      prototypeStorageBufferIndexAccess(target);
  if (!access.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-assignment-target",
                      "Vulkan prototype binary emission currently supports "
                      "only direct storage buffer index targets");
    return false;
  }

  const std::string &resourceName = access->resourceName;
  const auto resource = resources.find(resourceName);
  if (resource == resources.end()) {
    diagnostics.error("vulkan.prototype-unsupported-assignment-target",
                      "Vulkan prototype binary emission cannot resolve storage "
                      "buffer resource '" +
                          resourceName + "'");
    return false;
  }
  if (!isPrototypeStorageBufferResource(resource->second)) {
    diagnostics.error("vulkan.prototype-unsupported-resource",
                      "Vulkan prototype binary emission supports only "
                      "scalar/vector arithmetic storage buffer resources");
    return false;
  }
  const bool resourceIsDescriptorArray = resource->second.type.arraySize.has_value();
  if (resourceIsDescriptorArray && access->descriptorIndex == nullptr) {
    diagnostics.error("vulkan.prototype-unsupported-assignment-target",
                      "Vulkan prototype storage-buffer descriptor arrays "
                      "require descriptor and element indices, such as "
                      "values[0][1]");
    return false;
  }
  if (!resourceIsDescriptorArray && access->descriptorIndex != nullptr) {
    diagnostics.error("vulkan.prototype-unsupported-assignment-target",
                      "Vulkan prototype non-array storage buffers support "
                      "only one element index");
    return false;
  }
  if (access->descriptorIndex != nullptr) {
    if (!prototypeExpressionSupported(*access->descriptorIndex, locals, resources,
                                      constants, structs, diagnostics)) {
      return false;
    }
    const HIRType descriptorIndexType =
        prototypeExpressionType(*access->descriptorIndex, locals, resources,
                                constants);
    if (descriptorIndexType.name != "int" ||
        descriptorIndexType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-assignment-target",
                        "Vulkan prototype storage-buffer descriptor indices "
                        "must be scalar int values");
      return false;
    }
  }
  if (access->elementIndex == nullptr ||
      !prototypeExpressionSupported(*access->elementIndex, locals, resources,
                                    constants, structs, diagnostics)) {
    return false;
  }
  const HIRType indexType =
      prototypeExpressionType(*access->elementIndex, locals, resources,
                              constants);
  if (indexType.name != "int" || indexType.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-assignment-target",
                      "Vulkan prototype storage buffer indices must be scalar "
                      "int values");
    return false;
  }
  if (!samePrototypeType(target.type, prototypeBufferElementType(resource->second))) {
    diagnostics.error("vulkan.prototype-unsupported-type",
                      "Vulkan prototype storage buffer target type does not "
                      "match the buffer element type");
    return false;
  }
  return true;
}

bool prototypeAssignmentValueSupported(
    const HIRExpression &value, const HIRType &targetType,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics,
    std::string_view castDiagnosticMessage) {
  if (isPrototypeAtomicIntegerCall(value)) {
    return prototypeAtomicIntegerCaptureSupported(
        value, targetType, locals, resources, constants, structs, diagnostics);
  }
  if (isPrototypeStorageImageAtomicCall(value)) {
    return prototypeStorageImageAtomicCaptureSupported(
        value, targetType, locals, resources, constants, structs, diagnostics);
  }
  if (!prototypeExpressionSupported(value, locals, resources, constants,
                                    structs, diagnostics)) {
    return false;
  }
  const HIRType valueType =
      prototypeExpressionType(value, locals, resources, constants);
  if (!samePrototypeType(targetType, valueType) &&
      !isPrototypeDeferredUserCallType(value, valueType)) {
    diagnostics.error("vulkan.prototype-unsupported-type",
                      std::string(castDiagnosticMessage));
    return false;
  }
  return true;
}

bool prototypeAssignmentSupported(
    const HIRStatement &statement,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_set<std::string> &readOnlyArrayLocals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  if (statement.target.kind == HIRExpressionKind::Identifier) {
    if (auto local = locals.find(statement.target.value); local == locals.end()) {
      diagnostics.error("vulkan.prototype-unsupported-assignment-target",
                        "Vulkan prototype binary emission cannot assign to "
                        "unknown local '" +
                            statement.target.value + "'");
      return false;
    } else {
      if (!prototypeAssignmentValueSupported(
              statement.value, local->second, locals, resources, constants,
              structs, diagnostics,
              "Vulkan prototype binary emission does not insert assignment "
              "casts yet")) {
        return false;
      }
    }
    return true;
  }

  if (statement.target.kind == HIRExpressionKind::IndexAccess) {
    if (const std::optional<PrototypeLocalArrayElementAccess> localAccess =
            prototypeLocalArrayElementAccess(statement.target, locals)) {
      if (readOnlyArrayLocals.find(localAccess->localName) !=
          readOnlyArrayLocals.end()) {
        diagnostics.error(
            "vulkan.prototype-unsupported-function-parameter-array",
            "Vulkan prototype helper function array parameters use the shared "
            "read-only value-copy ABI; writes through parameter array '" +
                localAccess->localName + "' are not supported");
        return false;
      }
      if (!prototypeLocalArrayElementAccessSupported(
              statement.target, locals, resources, constants, structs,
              diagnostics, true)) {
        return false;
      }
      if (!prototypeAssignmentValueSupported(
              statement.value, statement.target.type, locals, resources,
              constants, structs, diagnostics,
              "Vulkan prototype binary emission does not insert local array "
              "element assignment casts yet")) {
        return false;
      }
      return true;
    }
    if (prototypeStorageBufferMemberAccessSupported(
            statement.target, resources, locals, constants, structs,
            diagnostics)) {
      if (!prototypeAssignmentValueSupported(
              statement.value, statement.target.type, locals, resources,
              constants, structs, diagnostics,
              "Vulkan prototype binary emission does not insert struct "
              "storage-buffer field store casts yet")) {
        return false;
      }
      return true;
    }
    if (diagnostics.hasErrors()) {
      return false;
    }
    if (!prototypeResourceIndexSupported(statement.target, resources, locals,
                                         constants, structs, diagnostics)) {
      return false;
    }
    if (!prototypeAssignmentValueSupported(
            statement.value, statement.target.type, locals, resources,
            constants, structs, diagnostics,
            "Vulkan prototype binary emission does not insert storage buffer "
            "store casts yet")) {
      return false;
    }
    return true;
  }

  if (statement.target.kind == HIRExpressionKind::MemberAccess) {
    if (!prototypeStorageBufferMemberAccessSupported(
            statement.target, resources, locals, constants, structs,
            diagnostics)) {
      diagnostics.error("vulkan.prototype-unsupported-assignment-target",
                        "Vulkan prototype binary emission currently assigns "
                        "member targets only for struct storage-buffer fields");
      return false;
    }
    if (!prototypeAssignmentValueSupported(
            statement.value, statement.target.type, locals, resources,
            constants, structs, diagnostics,
            "Vulkan prototype binary emission does not insert struct "
            "storage-buffer field store casts yet")) {
      return false;
    }
    return true;
  }

  diagnostics.error("vulkan.prototype-unsupported-assignment-target",
                    "Vulkan prototype binary emission currently assigns "
                    "only to local identifiers or storage buffer indices");
  return false;
}

bool prototypeDeclarationSupported(
    const HIRStatement &statement,
    std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  if (!isPrototypeLocalType(statement.declaredType) &&
      !isPrototypeFunctionArrayParameterType(statement.declaredType,
                                             constants)) {
    diagnostics.error("vulkan.prototype-unsupported-type",
                      "Vulkan prototype binary emission supports only "
                      "scalar int/float/bool, vec2/vec3/vec4, "
                      "mat2/mat3/mat4, and fixed-size numeric array locals");
    return false;
  }
  if (statement.value.kind != HIRExpressionKind::Empty) {
    if (!prototypeAssignmentValueSupported(
            statement.value, statement.declaredType, locals, resources,
            constants, structs, diagnostics,
            "Vulkan prototype binary emission does not insert local "
            "initializer casts yet")) {
      return false;
    }
  }
  locals[statement.name] = statement.declaredType;
  return true;
}

bool prototypeLoopUpdateSupported(
    const std::vector<Token> &tokens,
    const std::unordered_map<std::string, HIRType> &locals,
    DiagnosticEngine &diagnostics) {
  std::string variableName;
  if (tokens.size() == 2 && tokens[0].kind == TokenKind::Identifier &&
      tokens[1].kind == TokenKind::Operator &&
      (tokens[1].text == "++" || tokens[1].text == "--")) {
    variableName = tokens[0].text;
  } else if (tokens.size() == 2 && tokens[0].kind == TokenKind::Operator &&
             (tokens[0].text == "++" || tokens[0].text == "--") &&
             tokens[1].kind == TokenKind::Identifier) {
    variableName = tokens[1].text;
  } else if (tokens.size() == 4 && tokens[0].kind == TokenKind::Identifier &&
             tokens[1].kind == TokenKind::Operator &&
             (tokens[1].text == "+" || tokens[1].text == "-") &&
             tokens[2].kind == TokenKind::Equal &&
             tokens[3].kind == TokenKind::Number &&
             tokens[3].text.find('.') == std::string::npos) {
    variableName = tokens[0].text;
  } else {
    diagnostics.error("vulkan.prototype-unsupported-loop",
                      "Vulkan prototype for loops support only ++/-- or "
                      "+=/-= integer-literal counter updates");
    return false;
  }

  const auto local = locals.find(variableName);
  if (local == locals.end()) {
    diagnostics.error("vulkan.prototype-unsupported-loop",
                      "Vulkan prototype for loop update cannot resolve local "
                      "counter '" +
                          variableName + "'");
    return false;
  }
  if (local->second.name != "int" || local->second.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-loop",
                      "Vulkan prototype for loop counters must be scalar int "
                      "values");
    return false;
  }
  return true;
}

bool prototypeParsedLoopUpdateSupported(
    const HIRStatement &statement,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  if (statement.kind != HIRStatementKind::Assignment ||
      statement.target.kind != HIRExpressionKind::Identifier) {
    diagnostics.error("vulkan.prototype-unsupported-loop",
                      "Vulkan prototype for loops require assignment-style "
                      "counter updates");
    return false;
  }

  const std::string &counterName = statement.target.value;
  const auto local = locals.find(counterName);
  if (local == locals.end()) {
    diagnostics.error("vulkan.prototype-unsupported-loop",
                      "Vulkan prototype for loop update cannot resolve local "
                      "counter '" +
                          counterName + "'");
    return false;
  }
  if (local->second.name != "int" || local->second.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-loop",
                      "Vulkan prototype for loop counters must be scalar int "
                      "values");
    return false;
  }

  if (statement.value.kind != HIRExpressionKind::Binary ||
      (statement.value.value != "+" && statement.value.value != "-") ||
      statement.value.children.size() < 2 ||
      statement.value.children[0].kind != HIRExpressionKind::Identifier ||
      statement.value.children[0].value != counterName) {
    diagnostics.error("vulkan.prototype-unsupported-loop",
                      "Vulkan prototype parsed for loop updates must be "
                      "counter +/- expression");
    return false;
  }

  if (!prototypeExpressionSupported(statement.value, locals, resources,
                                    constants, structs, diagnostics)) {
    return false;
  }
  const HIRType updateType =
      prototypeExpressionType(statement.value, locals, resources, constants);
  if (!samePrototypeType(local->second, updateType)) {
    diagnostics.error("vulkan.prototype-unsupported-loop",
                      "Vulkan prototype for loop update type must match the "
                      "counter type");
    return false;
  }
  return true;
}

PrototypeBlockSupport prototypeBranchBodySupported(
    const std::vector<HIRStatement> &body,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_set<std::string> &readOnlyArrayLocals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics,
    const HIRType &returnType,
    bool allowReturn = true,
    bool allowLoopControl = false) {
  std::unordered_map<std::string, HIRType> branchLocals = locals;
  bool terminated = false;
  for (const HIRStatement &statement : body) {
    if (terminated) {
      diagnostics.error("vulkan.prototype-unsupported-body",
                        "Vulkan prototype binary emission requires a "
                        "terminating branch statement to be final");
      return {};
    }
    if (statement.kind == HIRStatementKind::Declaration) {
      if (!prototypeDeclarationSupported(statement, branchLocals, resources,
                                         constants, structs, diagnostics)) {
        return {};
      }
      continue;
    }
    if (statement.kind == HIRStatementKind::Assignment) {
      if (!prototypeAssignmentSupported(statement, branchLocals,
                                        readOnlyArrayLocals, resources,
                                        constants, structs, diagnostics)) {
        return {};
      }
      continue;
    }
    if (statement.kind == HIRStatementKind::Block) {
      const PrototypeBlockSupport block =
          prototypeBranchBodySupported(
              statement.body, branchLocals, readOnlyArrayLocals, resources,
              constants, structs, diagnostics, returnType, allowReturn,
              allowLoopControl);
      if (!block.supported) {
        return {};
      }
      terminated = block.terminated;
      continue;
    }
    if (statement.kind == HIRStatementKind::If) {
      bool ifTerminates = false;
      if (!prototypeIfStatementSupported(
              statement, branchLocals, readOnlyArrayLocals, resources,
              constants, structs, diagnostics, returnType, ifTerminates,
              allowReturn, allowLoopControl)) {
        return {};
      }
      terminated = ifTerminates;
      continue;
    }
    if (statement.kind == HIRStatementKind::For) {
      if (!prototypeForStatementSupported(statement, branchLocals,
                                          readOnlyArrayLocals, resources,
                                          constants, structs, diagnostics)) {
        return {};
      }
      continue;
    }
    if (statement.kind == HIRStatementKind::Break ||
        statement.kind == HIRStatementKind::Continue) {
      if (!allowLoopControl) {
        diagnostics.error("vulkan.prototype-unsupported-statement",
                          "Vulkan prototype break/continue statements are "
                          "supported only inside for or while loop bodies");
        return {};
      }
      terminated = true;
      continue;
    }
    if (statement.kind == HIRStatementKind::Expression &&
        isPrototypeImageStoreCall(statement.value)) {
      if (!prototypeStorageImageStoreSupported(
              statement.value, branchLocals, resources, constants, structs,
              diagnostics)) {
        return {};
      }
      continue;
    }
    if (statement.kind == HIRStatementKind::Expression &&
        isPrototypeStorageImageAtomicCall(statement.value)) {
      if (!prototypeStorageImageAtomicSupported(
              statement.value, branchLocals, resources, constants, structs,
              diagnostics)) {
        return {};
      }
      continue;
    }
    if (statement.kind == HIRStatementKind::Expression &&
        isPrototypeAtomicIntegerCall(statement.value)) {
      if (!prototypeAtomicIntegerStatementSupported(
              statement.value, branchLocals, resources, constants, structs,
              diagnostics)) {
        return {};
      }
      continue;
    }
    if (statement.kind == HIRStatementKind::Expression &&
        statement.value.kind == HIRExpressionKind::Call &&
        !prototypeIntrinsicLoweringForCall(statement.value).has_value()) {
      if (!prototypeExpressionSupported(statement.value, branchLocals,
                                        resources, constants, structs,
                                        diagnostics)) {
        return {};
      }
      continue;
    }
    if (statement.kind == HIRStatementKind::Return) {
      if (!allowReturn) {
        diagnostics.error("vulkan.prototype-unsupported-loop",
                          "Vulkan prototype for loop bodies do not support "
                          "returns yet");
        return {};
      }
      const bool returnsVoid =
          returnType.name == "void" && !returnType.arraySize.has_value();
      if (returnsVoid) {
        if (statement.value.kind != HIRExpressionKind::Empty) {
          diagnostics.error(
              "vulkan.prototype-unsupported-body",
              "Vulkan prototype void functions cannot return a value");
          return {};
        }
      } else {
        if (statement.value.kind == HIRExpressionKind::Empty) {
          diagnostics.error("vulkan.prototype-unsupported-body",
                            "Vulkan prototype non-void functions must return "
                            "a value");
          return {};
        }
        if (!prototypeExpressionSupported(statement.value, branchLocals,
                                          resources, constants, structs,
                                          diagnostics)) {
          return {};
        }
        const HIRType valueType = prototypeExpressionType(
            statement.value, branchLocals, resources, constants);
        if (!samePrototypeType(returnType, valueType) &&
            !isPrototypeDeferredUserCallType(statement.value, valueType)) {
          diagnostics.error("vulkan.prototype-unsupported-type",
                            "Vulkan prototype return value type does not "
                            "match the function return type");
          return {};
        }
      }
      terminated = true;
      continue;
    }

    {
      diagnostics.error("vulkan.prototype-unsupported-statement",
                        "Vulkan prototype binary emission currently supports "
                        "only declarations, assignments, nested if/for "
                        "statements, or void returns inside if branches");
      return {};
    }
  }
  return PrototypeBlockSupport{true, terminated};
}

bool prototypeIfStatementSupported(
    const HIRStatement &statement,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_set<std::string> &readOnlyArrayLocals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics,
    const HIRType &returnType,
    bool &terminates,
    bool allowReturn,
    bool allowLoopControl) {
  terminates = false;
  if (!prototypeExpressionSupported(statement.value, locals, resources,
                                    constants, structs, diagnostics)) {
    return false;
  }

  const HIRType conditionType =
      prototypeExpressionType(statement.value, locals, resources, constants);
  if (conditionType.name != "bool" || conditionType.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-expression",
                      "Vulkan prototype if conditions must be scalar bool "
                      "values");
    return false;
  }

  const PrototypeBlockSupport thenBlock =
      prototypeBranchBodySupported(statement.body, locals, readOnlyArrayLocals,
                                   resources, constants, structs, diagnostics,
                                   returnType, allowReturn, allowLoopControl);
  if (!thenBlock.supported) {
    return false;
  }
  const PrototypeBlockSupport elseBlock =
      prototypeBranchBodySupported(statement.elseBody, locals,
                                   readOnlyArrayLocals, resources, constants,
                                   structs, diagnostics, returnType,
                                   allowReturn, allowLoopControl);
  if (!elseBlock.supported) {
    return false;
  }

  terminates = !statement.elseBody.empty() && thenBlock.terminated &&
               elseBlock.terminated;
  return true;
}

bool isWhileLoweredForStatement(const HIRStatement &statement) {
  return statement.kind == HIRStatementKind::For &&
         statement.initializer.empty() && statement.update.empty() &&
         statement.updateTokens.empty();
}

bool prototypeForStatementSupported(
    const HIRStatement &statement,
    const std::unordered_map<std::string, HIRType> &locals,
    const std::unordered_set<std::string> &readOnlyArrayLocals,
    const std::unordered_map<std::string, HIRResource> &resources,
    const PrototypeConstantMap &constants,
    const PrototypeStructMap &structs,
    DiagnosticEngine &diagnostics) {
  std::unordered_map<std::string, HIRType> loopLocals = locals;
  const bool whileLowered = isWhileLoweredForStatement(statement);
  if (!whileLowered) {
    if (statement.initializer.size() != 1 ||
        statement.initializer.front().kind != HIRStatementKind::Declaration) {
      diagnostics.error("vulkan.prototype-unsupported-loop",
                        "Vulkan prototype for loops require a single scalar "
                        "int declaration initializer");
      return false;
    }

    const HIRStatement &initializer = statement.initializer.front();
    if (initializer.declaredType.name != "int" ||
        initializer.declaredType.arraySize.has_value()) {
      diagnostics.error("vulkan.prototype-unsupported-loop",
                        "Vulkan prototype for loop counters must be scalar int "
                        "values");
      return false;
    }
    if (!prototypeDeclarationSupported(initializer, loopLocals, resources,
                                       constants, structs, diagnostics)) {
      return false;
    }
  }

  if (!prototypeExpressionSupported(statement.value, loopLocals, resources,
                                    constants, structs, diagnostics)) {
    return false;
  }
  const HIRType conditionType =
      prototypeExpressionType(statement.value, loopLocals, resources, constants);
  if (conditionType.name != "bool" || conditionType.arraySize.has_value()) {
    diagnostics.error("vulkan.prototype-unsupported-loop",
                      "Vulkan prototype for loop conditions must be scalar bool "
                      "values");
    return false;
  }

  if (!whileLowered) {
    if (!statement.update.empty()) {
      if (statement.update.size() != 1 ||
          !prototypeParsedLoopUpdateSupported(statement.update.front(),
                                              loopLocals, resources, constants,
                                              structs, diagnostics)) {
        return false;
      }
    } else {
      if (!prototypeLoopUpdateSupported(statement.updateTokens, loopLocals,
                                        diagnostics)) {
        return false;
      }
    }
  }

  const PrototypeBlockSupport bodyBlock =
      prototypeBranchBodySupported(statement.body, loopLocals,
                                   readOnlyArrayLocals, resources, constants,
                                   structs, diagnostics,
                                   HIRType{"void", std::nullopt}, false, true);
  return bodyBlock.supported;
}

bool prototypeBodySupported(const HIRFunction &function,
                            const std::vector<HIRResource> &stageResources,
                            const PrototypeConstantMap &constants,
                            const PrototypeStructMap &structs,
                            DiagnosticEngine &diagnostics,
                            const std::unordered_set<std::string>
                                &mutableArrayParameters = {}) {
  std::unordered_map<std::string, HIRType> locals;
  std::unordered_set<std::string> readOnlyArrayLocals;
  std::unordered_map<std::string, HIRResource> resources;
  for (const HIRResource &resource : stageResources) {
    resources[resource.name] = resource;
  }
  if (function.returnType.name != "void" &&
      !isPrototypeLocalType(function.returnType)) {
    diagnostics.error("vulkan.prototype-unsupported-signature",
                      "Vulkan prototype helper functions currently return "
                      "only void or scalar/vector numeric values");
    return false;
  }
  for (const HIRParameter &parameter : function.parameters) {
    if (parameter.type.arraySize.has_value()) {
      if (const std::optional<HIRResource> resource =
              vulkanPrototypePseudoResourceForParameter(parameter, constants);
          resource.has_value()) {
        resources[parameter.name] = *resource;
      } else if (!isPrototypeFunctionArrayParameterType(parameter.type,
                                                       constants)) {
        diagnostics.error(
            "vulkan.prototype-unsupported-function-parameter-array",
            "Vulkan prototype helper function parameter array '" +
                parameter.name + "' of type '" + formatType(parameter.type) +
                "' is not in the native slice; supported shape is a "
                "one-dimensional fixed-size scalar/vector numeric array or "
                "sampled texture/sampler descriptor array, but this parameter "
                "uses " +
                prototypeFunctionArrayParameterUnsupportedDetail(
                    parameter.type, constants));
        return false;
      }
    } else if (!isPrototypeLocalType(parameter.type)) {
      diagnostics.error("vulkan.prototype-unsupported-signature",
                        "Vulkan prototype helper function parameters "
                        "currently support only scalar/vector numeric values");
      return false;
    }
    locals[parameter.name] = parameter.type;
    if (parameter.type.arraySize.has_value() &&
        mutableArrayParameters.count(parameter.name) == 0) {
      readOnlyArrayLocals.insert(parameter.name);
    }
  }
  bool terminated = false;

  for (const HIRStatement &statement : function.body) {
    if (terminated) {
      diagnostics.error("vulkan.prototype-unsupported-body",
                        "Vulkan prototype binary emission requires a "
                        "terminating statement to be final");
      return false;
    }

    switch (statement.kind) {
    case HIRStatementKind::Declaration:
      if (!prototypeDeclarationSupported(statement, locals, resources,
                                         constants, structs, diagnostics)) {
        return false;
      }
      break;
    case HIRStatementKind::Assignment:
      if (!prototypeAssignmentSupported(statement, locals, readOnlyArrayLocals,
                                        resources, constants, structs,
                                        diagnostics)) {
        return false;
      }
      break;
    case HIRStatementKind::Block: {
      const PrototypeBlockSupport block =
          prototypeBranchBodySupported(
              statement.body, locals, readOnlyArrayLocals, resources, constants,
              structs, diagnostics, function.returnType);
      if (!block.supported) {
        return false;
      }
      terminated = block.terminated;
      break;
    }
    case HIRStatementKind::If:
      if (!prototypeIfStatementSupported(
              statement, locals, readOnlyArrayLocals, resources, constants,
              structs, diagnostics, function.returnType, terminated)) {
        return false;
      }
      break;
    case HIRStatementKind::For:
      if (!prototypeForStatementSupported(statement, locals,
                                          readOnlyArrayLocals, resources,
                                          constants, structs, diagnostics)) {
        return false;
      }
      break;
    case HIRStatementKind::Expression:
      if (isPrototypeImageStoreCall(statement.value)) {
        if (!prototypeStorageImageStoreSupported(
                statement.value, locals, resources, constants, structs,
                diagnostics)) {
          return false;
        }
        break;
      }
      if (isPrototypeStorageImageAtomicCall(statement.value)) {
        if (!prototypeStorageImageAtomicSupported(
                statement.value, locals, resources, constants, structs,
                diagnostics)) {
          return false;
        }
        break;
      }
      if (isPrototypeAtomicIntegerCall(statement.value)) {
        if (!prototypeAtomicIntegerStatementSupported(
                statement.value, locals, resources, constants, structs,
                diagnostics)) {
          return false;
        }
        break;
      }
      if (statement.value.kind == HIRExpressionKind::Call &&
          !prototypeIntrinsicLoweringForCall(statement.value).has_value()) {
        if (!prototypeExpressionSupported(statement.value, locals, resources,
                                          constants, structs, diagnostics)) {
          return false;
        }
        break;
      }
      diagnostics.error("vulkan.prototype-unsupported-statement",
                        "Vulkan prototype binary emission does not lower '" +
                            statementKindName(statement.kind) +
                            "' statements yet");
      return false;
    case HIRStatementKind::Return:
      if (function.returnType.name == "void" &&
          !function.returnType.arraySize.has_value()) {
        if (statement.value.kind != HIRExpressionKind::Empty) {
          diagnostics.error(
              "vulkan.prototype-unsupported-body",
              "Vulkan prototype void functions cannot return a value");
          return false;
        }
      } else {
        if (statement.value.kind == HIRExpressionKind::Empty) {
          diagnostics.error("vulkan.prototype-unsupported-body",
                            "Vulkan prototype non-void functions must return "
                            "a value");
          return false;
        }
        if (!prototypeExpressionSupported(statement.value, locals, resources,
                                          constants, structs, diagnostics)) {
          return false;
        }
        const HIRType valueType = prototypeExpressionType(
            statement.value, locals, resources, constants);
        if (!samePrototypeType(function.returnType, valueType) &&
            !isPrototypeDeferredUserCallType(statement.value, valueType)) {
          diagnostics.error("vulkan.prototype-unsupported-type",
                            "Vulkan prototype return value type does not "
                            "match the function return type");
          return false;
        }
      }
      terminated = true;
      break;
    case HIRStatementKind::Break:
    case HIRStatementKind::Continue:
    case HIRStatementKind::Discard:
    case HIRStatementKind::Raw:
      diagnostics.error("vulkan.prototype-unsupported-statement",
                        "Vulkan prototype binary emission does not lower '" +
                            statementKindName(statement.kind) +
                            "' statements yet");
      return false;
    }
  }

  if (function.returnType.name != "void" &&
      !function.returnType.arraySize.has_value() && !terminated) {
    diagnostics.error("vulkan.prototype-unsupported-body",
                      "Vulkan prototype non-void functions require an "
                      "explicit final return");
    return false;
  }

  return true;
}

bool prototypeFunctionParameterArraysSupported(const HIRFunction &function,
                                               std::string_view context,
                                               bool entryPoint,
                                               const PrototypeConstantMap &constants,
                                               DiagnosticEngine &diagnostics) {
  for (const HIRParameter &parameter : function.parameters) {
    if (!parameter.type.arraySize.has_value()) {
      continue;
    }
    if (!entryPoint &&
        (isPrototypeFunctionArrayParameterType(parameter.type, constants) ||
         isVulkanPrototypeResourceArrayParameterType(parameter.type,
                                                    constants))) {
      continue;
    }
    const std::string arrayKind =
        parameter.type.arraySize->empty() ? "runtime-sized" : "fixed-size";
    const std::string detail =
        entryPoint
            ? "entry-point array parameters remain outside the Vulkan "
              "prototype ABI"
            : "supported native shape is a one-dimensional fixed-size "
              "scalar/vector numeric helper array or sampled texture/sampler "
              "descriptor helper array, but this parameter uses " +
                  prototypeFunctionArrayParameterUnsupportedDetail(
                      parameter.type, constants);
    const char *diagnosticCode =
        entryPoint
            ? "vulkan.prototype-unsupported-entry-point-function-parameter-array"
            : "vulkan.prototype-unsupported-function-parameter-array";
    diagnostics.error(diagnosticCode,
                      "Vulkan prototype SPIR-V lowering does not support " +
                          arrayKind + " function parameter array '" +
                          parameter.name + "' of type '" +
                          formatType(parameter.type) + "' in " +
                          std::string(context) + " function '" +
                          function.name + "'; " + detail);
    return false;
  }
  return true;
}

bool prototypeFunctionParameterArraysSupported(const HIRModule &module,
                                               const HIRStage &stage,
                                               DiagnosticEngine &diagnostics) {
  const PrototypeConstantMap constants = prototypeConstants(module);
  for (const HIRFunction &function : module.functions) {
    if (!prototypeFunctionParameterArraysSupported(function, "top-level",
                                                   false, constants,
                                                   diagnostics)) {
      return false;
    }
  }
  const std::string stageContext = "stage '" + stage.stage + "'";
  for (const HIRFunction &function : stage.functions) {
    const bool entryPoint = function.name == stage.entryPointName;
    if (!prototypeFunctionParameterArraysSupported(function, stageContext,
                                                   entryPoint, constants,
                                                   diagnostics)) {
      return false;
    }
  }
  return true;
}

std::string sanitizeIdFragment(std::string_view text) {
  std::string result;
  for (const char character : text) {
    const bool isAlpha = (character >= 'a' && character <= 'z') ||
                         (character >= 'A' && character <= 'Z');
    const bool isDigit = character >= '0' && character <= '9';
    result.push_back(isAlpha || isDigit ? character : '_');
  }
  if (result.empty()) {
    return "value";
  }
  if (result.front() >= '0' && result.front() <= '9') {
    result.insert(result.begin(), '_');
  }
  return result;
}

std::string sanitizeNumericConstantIdFragment(std::string_view value) {
  if (!value.empty() && value.front() == '-') {
    return "neg" + sanitizeIdFragment(value.substr(1));
  }
  return sanitizeIdFragment(value);
}

std::string sanitizeIntegerConstantIdFragment(int value) {
  if (value < 0) {
    return "neg" + std::to_string(-value);
  }
  return std::to_string(value);
}

struct PrototypeSPIRVValue {
  HIRType type;
  std::string id;
  bool nonUniformDescriptor = false;
};

struct PrototypeSPIRVLocal {
  HIRType type;
  std::string pointerTypeId;
  std::string variableId;
  std::string valueId;
  bool readOnly = false;
  bool knownZeroIndex = false;
};

struct PrototypeSPIRVStorageBuffer {
  HIRType resourceType;
  HIRType elementType;
  std::string elementPointerTypeId;
  std::string variableId;
  bool isRuntimeArrayBlock = false;
};

struct PrototypeSPIRVWorkgroupShared {
  HIRType type;
  std::string variableId;
};

struct PrototypeSPIRVUniformBuffer {
  HIRType resourceType;
  HIRType elementType;
  std::string variableId;
};

struct PrototypeSPIRVDescriptorResource {
  HIRResourceKind kind = HIRResourceKind::Value;
  HIRType type;
  std::optional<std::string> storageImageFormat;
  std::string variableId;
};

struct PrototypeSPIRVStorageImageDescriptorPointer {
  HIRType type;
  std::string pointerId;
  std::optional<std::string> storageImageFormat;
  bool nonUniformDescriptor = false;
};

struct PrototypeEmitResult {
  bool success = false;
  bool terminated = false;
};

struct PrototypeLoopUpdate {
  std::string variableName;
  bool increment = true;
  std::string amount = "1";
};

struct PrototypeLoopLabels {
  std::string continueLabel;
  std::string mergeLabel;
};

enum class PrototypeSPIRVAtomicStorageClass {
  StorageBuffer,
  Workgroup,
};

struct PrototypeSPIRVAtomicTarget {
  HIRType valueType;
  std::string pointerId;
  PrototypeSPIRVAtomicStorageClass storageClass =
      PrototypeSPIRVAtomicStorageClass::StorageBuffer;
};

struct PrototypeSPIRVFunctionInfo {
  const HIRFunction *function = nullptr;
  std::string id;
  std::string functionTypeId;
  HIRType returnType;
  std::vector<HIRType> parameterTypes;
  std::vector<bool> pointerParameters;
  std::vector<bool> erasedResourceArrayParameters;
  bool entry = false;
};

struct PrototypeSPIRVArrayWriteBackCopy {
  HIRType type;
  std::string temporaryPointerId;
  std::string storagePointerId;
};

bool isPrototypeZeroLiteral(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::Literal &&
         (expression.value == "0" || expression.value == "0u");
}

enum class PrototypeNonUniformDescriptorUse {
  SampledImage,
  StorageImage,
  StorageBuffer,
};

class PrototypeSPIRVBuilder {
public:
  PrototypeSPIRVBuilder(const HIRModule &module, const HIRStage &stage,
                        DiagnosticEngine &diagnostics)
      : diagnostics_(diagnostics),
        layoutContext_(module.structs, module.constants),
        structs_(prototypeStructs(module)), constants_(prototypeConstants(module)) {
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind == HIRResourceKind::Buffer) {
        registerStorageBuffer(resource);
      } else if (resource.kind == HIRResourceKind::Uniform) {
        registerUniformBuffer(resource);
      } else if (resource.kind == HIRResourceKind::Shared) {
        registerWorkgroupSharedResource(resource);
      } else if (isPrototypeUniformConstantDescriptorResource(resource)) {
        registerUniformConstantDescriptor(resource);
      }
    }
    collectVulkanPrototypeResourceArrayParameterAliases(
        module, stage, resourceArrayParameterAliases_, nullptr);
    arrayWriteBackParameters_ =
        collectVulkanFunctionParameterArrayWriteBackParameters(module, stage);
    registerFunctionSignatures(module, stage);
  }

  bool emit(const HIRModule &module, const HIRStage &stage,
            const HIRFunction &entryFunction) {
    for (const HIRFunction &function : module.functions) {
      if (!emitFunction(function)) {
        return false;
      }
    }
    for (const HIRFunction &function : stage.functions) {
      if (function.name == stage.entryPointName) {
        continue;
      }
      if (!emitFunction(function)) {
        return false;
      }
    }
    return emitFunction(entryFunction);
  }

  std::string render(const HIRModule &module, const HIRStage &stage) {
    const HIRWorkgroupSize &workgroup = *stage.workgroupSize;
    const std::string entry = entryPointName(stage);
    const SPIRVId entryId = SPIRVModule::id("%" + entry);
    std::vector<SPIRVId> interfaceIds;
    interfaceIds.reserve(entryPointInterfaces_.size());
    for (const std::string &interfaceId : entryPointInterfaces_) {
      interfaceIds.push_back(SPIRVModule::id(interfaceId));
    }

    module_.addCapability(SPIRVCapability::Shader);
    if (usesRuntimeDescriptorArray_) {
      module_.addCapability(SPIRVCapability::RuntimeDescriptorArrayEXT);
    }
    if (usesNonUniformDescriptorIndex_) {
      module_.addCapability(SPIRVCapability::ShaderNonUniformEXT);
      if (usesSampledImageArrayNonUniformIndexing_) {
        module_.addCapability(
            SPIRVCapability::SampledImageArrayNonUniformIndexingEXT);
      }
      if (usesStorageImageArrayNonUniformIndexing_) {
        module_.addCapability(
            SPIRVCapability::StorageImageArrayNonUniformIndexingEXT);
      }
      if (usesStorageBufferArrayNonUniformIndexing_) {
        module_.addCapability(
            SPIRVCapability::StorageBufferArrayNonUniformIndexingEXT);
      }
    }
    if (usesRuntimeDescriptorArray_ || usesNonUniformDescriptorIndex_) {
      module_.addExtension(SPIRVExtension::SPV_EXT_descriptor_indexing);
    }
    module_.setMemoryModel(SPIRVAddressingModel::Logical,
                           SPIRVMemoryModel::GLSL450);
    module_.addEntryPoint(SPIRVExecutionModel::GLCompute, entryId,
                          stage.entryPointName, interfaceIds);
    module_.addExecutionMode(entryId, "LocalSize",
                             {workgroup.x, workgroup.y, workgroup.z});
    (void)module;
    return module_.render();
  }

private:
  void registerFunctionSignatures(const HIRModule &module,
                                  const HIRStage &stage) {
    for (const HIRFunction &function : module.functions) {
      registerFunctionSignature(function, false,
                                "%func_" + sanitizeIdFragment(function.name));
    }
    for (const HIRFunction &function : stage.functions) {
      const bool isEntry = function.name == stage.entryPointName;
      const std::string id = isEntry
                                 ? "%" + entryPointName(stage)
                                 : "%func_" + sanitizeIdFragment(function.name);
      registerFunctionSignature(function, isEntry, id);
    }
  }

  void registerFunctionSignature(const HIRFunction &function, bool isEntry,
                                 std::string id) {
    PrototypeSPIRVFunctionInfo info;
    info.function = &function;
    info.id = std::move(id);
    info.returnType = function.returnType;
    info.entry = isEntry;
    info.parameterTypes.reserve(function.parameters.size());
    info.pointerParameters.reserve(function.parameters.size());
    info.erasedResourceArrayParameters.reserve(function.parameters.size());
    const auto writeBackParameters =
        arrayWriteBackParameters_.find(function.name);
    for (const HIRParameter &parameter : function.parameters) {
      const bool erased = isVulkanPrototypeErasedResourceArrayParameter(
          parameter, constants_, isEntry);
      info.erasedResourceArrayParameters.push_back(erased);
      if (!erased) {
        const bool pointerParameter =
            writeBackParameters != arrayWriteBackParameters_.end() &&
            writeBackParameters->second.count(parameter.name) != 0;
        info.parameterTypes.push_back(parameter.type);
        info.pointerParameters.push_back(pointerParameter);
      }
    }
    info.functionTypeId =
        ensureFunctionType(info.returnType, info.parameterTypes,
                           info.pointerParameters);
    functions_[function.name] = std::move(info);
  }

  bool emitFunction(const HIRFunction &function) {
    const auto functionInfo = functions_.find(function.name);
    if (functionInfo == functions_.end()) {
      diagnostics_.error("vulkan.prototype-unsupported-function",
                         "Vulkan prototype cannot resolve function '" +
                             function.name + "'");
      return false;
    }

    locals_.clear();
    loopLabels_.clear();
    variableLines_.clear();
    instructionLines_.clear();
    currentReturnType_ = function.returnType;
    currentFunctionName_ = function.name;
    bool terminated = false;

    const std::string returnTypeId = ensureType(function.returnType);
    const std::string functionTypeId = functionInfo->second.functionTypeId;
    if (returnTypeId.empty() || functionTypeId.empty()) {
      return false;
    }
    SPIRVFunctionDefinition output;
    output.id = SPIRVModule::id(functionInfo->second.id);
    output.returnType = SPIRVModule::id(returnTypeId);
    output.functionType = SPIRVModule::id(functionTypeId);
    output.entryLabel =
        "%entry_" + sanitizeIdFragment(functionInfo->second.id.substr(1));

    std::size_t abiParameterIndex = 0;
    for (std::size_t index = 0; index < function.parameters.size(); ++index) {
      const HIRParameter &parameter = function.parameters[index];
      if (index < functionInfo->second.erasedResourceArrayParameters.size() &&
          functionInfo->second.erasedResourceArrayParameters[index]) {
        continue;
      }
      const bool pointerParameter =
          abiParameterIndex < functionInfo->second.pointerParameters.size() &&
          functionInfo->second.pointerParameters[abiParameterIndex];
      const std::string parameterTypeId =
          pointerParameter ? ensureFunctionPointerType(parameter.type)
                           : ensureType(parameter.type);
      if (parameterTypeId.empty()) {
        return false;
      }
      PrototypeSPIRVLocal local;
      local.type = parameter.type;
      const std::string parameterId =
          "%param_" + sanitizeIdFragment(function.name) + "_" +
          sanitizeIdFragment(parameter.name);
      if (pointerParameter) {
        local.pointerTypeId = parameterTypeId;
        local.variableId = parameterId;
      } else {
        local.valueId = parameterId;
        local.readOnly = parameter.type.arraySize.has_value();
      }
      locals_[parameter.name] = local;
      output.parameterLines.push_back(parameterId +
                                      " = OpFunctionParameter " +
                                      parameterTypeId);
      ++abiParameterIndex;
    }

    for (const HIRStatement &statement : function.body) {
      if (terminated) {
        diagnostics_.error("vulkan.prototype-unsupported-body",
                           "Vulkan prototype binary emission requires a "
                           "terminating statement to be final");
        return false;
      }
      const PrototypeEmitResult result = emitStatement(statement);
      if (!result.success) {
        return false;
      }
      terminated = result.terminated;
    }

    if (function.returnType.name != "void" &&
        !function.returnType.arraySize.has_value() && !terminated) {
      diagnostics_.error("vulkan.prototype-unsupported-body",
                         "Vulkan prototype non-void functions require an "
                         "explicit final return");
      return false;
    }

    output.variableLines = variableLines_;
    output.instructionLines = instructionLines_;
    output.hasTerminator = terminated;
    module_.addFunction(std::move(output));
    locals_.clear();
    currentFunctionName_.clear();
    variableLines_.clear();
    instructionLines_.clear();
    return true;
  }

  std::string ensureType(const HIRType &type) {
    const std::string key = prototypeTypeKey(type);
    if (auto existing = typeIds_.find(key); existing != typeIds_.end()) {
      return existing->second;
    }

    std::string id;
    std::string line;
    if (type.arraySize.has_value()) {
      HIRType elementType = prototypeArrayElementTypeOneDimension(type);
      const std::string elementTypeId = ensureType(elementType);
      if (elementTypeId.empty()) {
        return "";
      }

      const std::optional<PrototypeStorageTypeLayout> layout =
          prototypeStorageTypeLayout(type, layoutContext_, true);
      if (!layout.has_value() || !layout->isArray) {
        diagnostics_.error("vulkan.prototype-unsupported-type",
                           "Vulkan prototype cannot compute array layout for '" +
                               formatType(type) + "'");
        return "";
      }

      if (type.arraySize->empty()) {
        id = "%runtimearr_" + sanitizeIdFragment(formatType(type));
        typeIds_[key] = id;
        module_.addDecoration(SPIRVModule::id(id), "ArrayStride",
                              {std::to_string(layout->arrayStrideBytes)});
        module_.addTypeInstruction(id + " = OpTypeRuntimeArray " + elementTypeId);
        return id;
      }

      const std::optional<std::size_t> elementCount =
          prototypeArrayFirstDimensionElementCount(type, constants_);
      if (!elementCount.has_value()) {
        diagnostics_.error("vulkan.prototype-unsupported-type",
                           "Vulkan prototype binary emission requires "
                           "fixed-size numeric or folded-constant arrays, got '" +
                               formatType(type) + "'");
        return "";
      }
      id = "%arr_" + sanitizeIdFragment(formatType(type));
      typeIds_[key] = id;
      module_.addDecoration(SPIRVModule::id(id), "ArrayStride",
                            {std::to_string(layout->arrayStrideBytes)});
      const std::string lengthId = ensureArrayLengthConstant(*elementCount);
      module_.addTypeInstruction(id + " = OpTypeArray " + elementTypeId + " " +
                           lengthId);
      return id;
    }

    if (type.name == "void") {
      id = "%void";
      line = id + " = OpTypeVoid";
    } else if (type.name == "bool") {
      id = "%bool";
      line = id + " = OpTypeBool";
    } else if (type.name == "int") {
      id = "%int";
      line = id + " = OpTypeInt 32 1";
    } else if (type.name == "uint") {
      id = "%uint";
      line = id + " = OpTypeInt 32 0";
    } else if (type.name == "float") {
      id = "%float";
      line = id + " = OpTypeFloat 32";
    } else if (const std::optional<HIRType> atomicValueType =
                   prototypeAtomicStorageValueType(type)) {
      const std::string valueTypeId = ensureType(*atomicValueType);
      if (valueTypeId.empty()) {
        return "";
      }
      typeIds_[key] = valueTypeId;
      return valueTypeId;
    } else if (const std::optional<std::size_t> width =
                   prototypeVectorWidth(type);
               width.has_value()) {
      const std::string componentType =
          ensureType(prototypeVectorComponentType(type));
      id = "%" + sanitizeIdFragment(type.name);
      line = id + " = OpTypeVector " + componentType + " " +
             std::to_string(*width);
    } else if (const std::optional<std::size_t> dimension =
                   prototypeMatrixDimension(type);
               dimension.has_value()) {
      const std::string columnType = ensureType(prototypeMatrixColumnType(type));
      if (columnType.empty()) {
        return "";
      }
      id = "%" + sanitizeIdFragment(type.name);
      line = id + " = OpTypeMatrix " + columnType + " " +
             std::to_string(*dimension);
    } else if (const auto structure = structs_.find(type.name);
               structure != structs_.end()) {
      id = "%struct_" + sanitizeIdFragment(type.name);
      typeIds_[key] = id;

      std::vector<std::string> fieldTypeIds;
      fieldTypeIds.reserve(structure->second->fields.size());
      for (const HIRField &field : structure->second->fields) {
        const std::string fieldTypeId = ensureType(field.type);
        if (fieldTypeId.empty()) {
          return "";
        }
        fieldTypeIds.push_back(fieldTypeId);
      }

      const std::optional<PrototypeStorageTypeLayout> layout =
          prototypeStorageTypeLayout(type, layoutContext_, true);
      if (!layout.has_value()) {
        diagnostics_.error("vulkan.prototype-unsupported-struct-buffer",
                           "Vulkan prototype cannot compute storage layout "
                           "for struct type '" +
                               type.name + "'");
        return "";
      }
      for (const PrototypeStorageFieldLayout &field : layout->fields) {
        module_.addMemberDecoration(SPIRVModule::id(id), field.index, "Offset",
                                    {std::to_string(field.offsetBytes)});
      }

      line = id + " = OpTypeStruct";
      for (const std::string &fieldTypeId : fieldTypeIds) {
        line += " " + fieldTypeId;
      }
      module_.addTypeInstruction(line);
      return id;
    } else {
      diagnostics_.error("vulkan.prototype-unsupported-type",
                         "Vulkan prototype binary emission does not lower type '" +
                             type.name + "'");
      return "";
    }

    typeIds_[key] = id;
    module_.addTypeInstruction(line);
    return id;
  }

  std::string ensurePointerType(const HIRType &type) {
    const std::string key = "Function:" + prototypeTypeKey(type);
    if (auto existing = pointerTypeIds_.find(key);
        existing != pointerTypeIds_.end()) {
      return existing->second;
    }

    const std::string valueType = ensureType(type);
    if (valueType.empty()) {
      return "";
    }
    const std::string id =
        "%ptr_Function_" + sanitizeIdFragment(formatType(type));
    pointerTypeIds_[key] = id;
    module_.addTypeInstruction(id + " = OpTypePointer Function " + valueType);
    return id;
  }

  std::string ensureFunctionValueType(const HIRType &type) {
    if (!type.arraySize.has_value()) {
      return ensureType(type);
    }

    const std::string key = prototypeTypeKey(type);
    if (auto existing = functionValueTypeIds_.find(key);
        existing != functionValueTypeIds_.end()) {
      return existing->second;
    }

    HIRType elementType = prototypeArrayElementTypeOneDimension(type);
    const std::string elementTypeId = ensureFunctionValueType(elementType);
    if (elementTypeId.empty()) {
      return "";
    }
    const std::optional<std::size_t> elementCount =
        prototypeArrayFirstDimensionElementCount(type, constants_);
    if (!elementCount.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-type",
                         "Vulkan prototype Function array temporaries require "
                         "fixed-size numeric or folded-constant arrays, got '" +
                             formatType(type) + "'");
      return "";
    }

    const std::string id =
        "%fnarr_" + sanitizeIdFragment(formatType(type));
    functionValueTypeIds_[key] = id;
    const std::string lengthId = ensureArrayLengthConstant(*elementCount);
    module_.addTypeInstruction(id + " = OpTypeArray " + elementTypeId + " " +
                               lengthId);
    return id;
  }

  std::string ensureFunctionPointerType(const HIRType &type) {
    const std::string key = prototypeTypeKey(type);
    if (auto existing = functionPointerTypeIds_.find(key);
        existing != functionPointerTypeIds_.end()) {
      return existing->second;
    }

    const std::string valueTypeId = ensureFunctionValueType(type);
    if (valueTypeId.empty()) {
      return "";
    }
    const std::string id =
        "%ptr_Function_" + sanitizeIdFragment(formatType(type));
    functionPointerTypeIds_[key] = id;
    module_.addTypeInstruction(id + " = OpTypePointer Function " +
                               valueTypeId);
    return id;
  }

  std::string ensureFunctionElementPointerType(const HIRType &type) {
    return type.arraySize.has_value() ? ensureFunctionPointerType(type)
                                      : ensurePointerType(type);
  }

  std::string ensureInputPointerType(const HIRType &type) {
    const std::string key = "Input:" + prototypeTypeKey(type);
    if (auto existing = inputPointerTypeIds_.find(key);
        existing != inputPointerTypeIds_.end()) {
      return existing->second;
    }

    const std::string valueType = ensureType(type);
    if (valueType.empty()) {
      return "";
    }
    const std::string id = "%ptr_Input_" + sanitizeIdFragment(formatType(type));
    inputPointerTypeIds_[key] = id;
    module_.addTypeInstruction(id + " = OpTypePointer Input " + valueType);
    return id;
  }

  std::string ensureComputeBuiltinVariable(
      const PrototypeComputeBuiltinInfo &builtin) {
    const std::string name(builtin.name);
    if (auto existing = computeBuiltinVariableIds_.find(name);
        existing != computeBuiltinVariableIds_.end()) {
      return existing->second;
    }

    const HIRType builtinType = prototypeComputeBuiltinType();
    const std::string pointerTypeId = ensureInputPointerType(builtinType);
    if (pointerTypeId.empty()) {
      return "";
    }

    const std::string variableId =
        "%builtin_" + sanitizeIdFragment(builtin.name);
    computeBuiltinVariableIds_[name] = variableId;
    entryPointInterfaces_.push_back(variableId);
    module_.addDecoration(SPIRVModule::id(variableId), "BuiltIn",
                          {std::string(builtin.spirvBuiltin)});
    module_.addGlobalInstruction(variableId + " = OpVariable " +
                                   pointerTypeId + " Input");
    return variableId;
  }

  std::string ensureWorkgroupValueType(const HIRType &type) {
    const std::string key = "WorkgroupValue:" + prototypeTypeKey(type);
    if (auto existing = workgroupTypeIds_.find(key);
        existing != workgroupTypeIds_.end()) {
      return existing->second;
    }

    if (!type.arraySize.has_value()) {
      return ensureType(type);
    }

    const HIRType elementType = prototypeArrayElementTypeOneDimension(type);
    const std::string elementTypeId = ensureWorkgroupValueType(elementType);
    if (elementTypeId.empty()) {
      return "";
    }
    const std::optional<std::size_t> elementCount =
        prototypeArrayFirstDimensionElementCount(type, constants_);
    if (!elementCount.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-resource",
                         "Vulkan prototype Workgroup shared declarations "
                         "require fixed-size numeric or folded-constant "
                         "array sizes, got '" +
                             formatType(type) + "'");
      return "";
    }

    const std::string id =
        "%workgrouparr_" + sanitizeIdFragment(formatType(type));
    workgroupTypeIds_[key] = id;
    const std::string lengthId = ensureArrayLengthConstant(*elementCount);
    module_.addTypeInstruction(id + " = OpTypeArray " + elementTypeId + " " +
                         lengthId);
    return id;
  }

  std::string ensureWorkgroupPointerType(const HIRType &type) {
    const std::string key = "Workgroup:" + prototypeTypeKey(type);
    if (auto existing = workgroupPointerTypeIds_.find(key);
        existing != workgroupPointerTypeIds_.end()) {
      return existing->second;
    }

    const std::string valueType = ensureWorkgroupValueType(type);
    if (valueType.empty()) {
      return "";
    }
    const std::string id =
        "%ptr_Workgroup_" + sanitizeIdFragment(formatType(type));
    workgroupPointerTypeIds_[key] = id;
    module_.addTypeInstruction(id + " = OpTypePointer Workgroup " + valueType);
    return id;
  }

  std::string ensureStorageBufferRuntimeArrayType(const HIRType &elementType) {
    const std::string key = prototypeTypeKey(elementType);
    if (auto existing = storageRuntimeArrayTypeIds_.find(key);
        existing != storageRuntimeArrayTypeIds_.end()) {
      return existing->second;
    }

    const std::string elementTypeId = ensureType(elementType);
    if (elementTypeId.empty()) {
      return "";
    }
    const std::string id =
        "%runtimearr_" + sanitizeIdFragment(elementType.name);
    storageRuntimeArrayTypeIds_[key] = id;
    module_.decorateArrayStride(SPIRVModule::id(id),
                                storageBufferArrayStride(elementType));
    module_.defineRuntimeArrayType(SPIRVModule::id(id),
                                   SPIRVModule::id(elementTypeId));
    return id;
  }

  std::string ensureStorageBufferStructType(const HIRType &elementType) {
    const std::string key = prototypeTypeKey(elementType);
    if (auto existing = storageStructTypeIds_.find(key);
        existing != storageStructTypeIds_.end()) {
      return existing->second;
    }

    const std::optional<PrototypeStorageTypeLayout> layout =
        prototypeStorageTypeLayout(elementType, layoutContext_, true);
    if (layout.has_value() && layout->hasRuntimeArray) {
      const std::string blockTypeId = ensureType(elementType);
      if (blockTypeId.empty()) {
        return "";
      }
      storageStructTypeIds_[key] = blockTypeId;
      module_.decorateBlock(SPIRVModule::id(blockTypeId));
      return blockTypeId;
    }

    const std::string arrayTypeId =
        ensureStorageBufferRuntimeArrayType(elementType);
    if (arrayTypeId.empty()) {
      return "";
    }
    const std::string id =
        "%StorageBuffer_" + sanitizeIdFragment(elementType.name);
    storageStructTypeIds_[key] = id;
    module_.decorateMemberOffset(SPIRVModule::id(id), 0, 0);
    module_.decorateBlock(SPIRVModule::id(id));
    module_.defineStructType(SPIRVModule::id(id),
                             {SPIRVModule::id(arrayTypeId)});
    return id;
  }

  std::string ensureStorageBufferStructPointerType(const HIRType &elementType) {
    const std::string key = prototypeTypeKey(elementType);
    if (auto existing = storageStructPointerTypeIds_.find(key);
        existing != storageStructPointerTypeIds_.end()) {
      return existing->second;
    }

    const std::string structTypeId = ensureStorageBufferStructType(elementType);
    if (structTypeId.empty()) {
      return "";
    }
    const std::string id =
        "%ptr_StorageBuffer_StorageBuffer_" + sanitizeIdFragment(elementType.name);
    storageStructPointerTypeIds_[key] = id;
    module_.definePointerType(SPIRVModule::id(id),
                              SPIRVStorageClass::StorageBuffer,
                              SPIRVModule::id(structTypeId));
    return id;
  }

  std::string ensureStorageBufferDescriptorArrayType(
      const HIRType &resourceType, const HIRType &elementType) {
    if (!resourceType.arraySize.has_value()) {
      return ensureStorageBufferStructType(elementType);
    }

    const std::optional<std::size_t> elementCount =
        prototypeArrayElementCount(resourceType, layoutContext_);
    if (!elementCount.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-storage-buffer-array",
                         "Vulkan prototype storage-buffer descriptor arrays "
                         "require fixed-size numeric or folded-constant "
                         "resource array sizes, got '" +
                             formatType(resourceType) + "'");
      return "";
    }

    const std::string key = prototypeTypeKey(resourceType);
    if (auto existing = storageDescriptorArrayTypeIds_.find(key);
        existing != storageDescriptorArrayTypeIds_.end()) {
      return existing->second;
    }

    const std::string structTypeId = ensureStorageBufferStructType(elementType);
    if (structTypeId.empty()) {
      return "";
    }
    const std::string id =
        "%arr_StorageBuffer_" + sanitizeIdFragment(formatType(resourceType));
    storageDescriptorArrayTypeIds_[key] = id;
    const std::string lengthId = ensureArrayLengthConstant(*elementCount);
    module_.defineArrayType(SPIRVModule::id(id), SPIRVModule::id(structTypeId),
                            SPIRVModule::id(lengthId));
    return id;
  }

  std::string ensureStorageBufferResourcePointerType(
      const HIRType &resourceType, const HIRType &elementType) {
    if (!resourceType.arraySize.has_value()) {
      return ensureStorageBufferStructPointerType(elementType);
    }

    const std::string key = prototypeTypeKey(resourceType);
    if (auto existing = storageDescriptorArrayPointerTypeIds_.find(key);
        existing != storageDescriptorArrayPointerTypeIds_.end()) {
      return existing->second;
    }

    const std::string arrayTypeId =
        ensureStorageBufferDescriptorArrayType(resourceType, elementType);
    if (arrayTypeId.empty()) {
      return "";
    }
    const std::string id = "%ptr_StorageBuffer_StorageBufferArray_" +
                           sanitizeIdFragment(formatType(resourceType));
    storageDescriptorArrayPointerTypeIds_[key] = id;
    module_.definePointerType(SPIRVModule::id(id),
                              SPIRVStorageClass::StorageBuffer,
                              SPIRVModule::id(arrayTypeId));
    return id;
  }

  std::string ensureStorageBufferElementPointerType(const HIRType &elementType) {
    const std::string key = prototypeTypeKey(elementType);
    if (auto existing = storageElementPointerTypeIds_.find(key);
        existing != storageElementPointerTypeIds_.end()) {
      return existing->second;
    }

    const std::string elementTypeId = ensureType(elementType);
    if (elementTypeId.empty()) {
      return "";
    }
    const std::string id =
        "%ptr_StorageBuffer_" + sanitizeIdFragment(formatType(elementType));
    storageElementPointerTypeIds_[key] = id;
    module_.definePointerType(SPIRVModule::id(id),
                              SPIRVStorageClass::StorageBuffer,
                              SPIRVModule::id(elementTypeId));
    return id;
  }

  std::string ensureUniformBufferBlockType(const HIRType &elementType) {
    const std::string key = prototypeTypeKey(elementType);
    if (auto existing = uniformBlockTypeIds_.find(key);
        existing != uniformBlockTypeIds_.end()) {
      return existing->second;
    }

    const std::string blockTypeId = ensureType(elementType);
    if (blockTypeId.empty()) {
      return "";
    }
    uniformBlockTypeIds_[key] = blockTypeId;
    module_.addDecoration(SPIRVModule::id(blockTypeId), "Block");
    return blockTypeId;
  }

  std::string ensureUniformBufferDescriptorArrayType(
      const HIRType &resourceType, const HIRType &elementType) {
    if (!resourceType.arraySize.has_value()) {
      return ensureUniformBufferBlockType(elementType);
    }

    const std::optional<std::size_t> elementCount =
        prototypeArrayElementCount(resourceType, layoutContext_);
    if (!elementCount.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-uniform-buffer",
                         "Vulkan prototype uniform-buffer descriptor arrays "
                         "require fixed-size numeric or folded-constant "
                         "resource array sizes, got '" +
                             formatType(resourceType) + "'");
      return "";
    }

    const std::string key = prototypeTypeKey(resourceType);
    if (auto existing = uniformDescriptorArrayTypeIds_.find(key);
        existing != uniformDescriptorArrayTypeIds_.end()) {
      return existing->second;
    }

    const std::string blockTypeId = ensureUniformBufferBlockType(elementType);
    if (blockTypeId.empty()) {
      return "";
    }
    const std::string id =
        "%arr_UniformBuffer_" + sanitizeIdFragment(formatType(resourceType));
    uniformDescriptorArrayTypeIds_[key] = id;
    const std::string lengthId = ensureArrayLengthConstant(*elementCount);
    module_.addTypeInstruction(id + " = OpTypeArray " + blockTypeId + " " +
                         lengthId);
    return id;
  }

  std::string ensureUniformBufferResourcePointerType(
      const HIRType &resourceType, const HIRType &elementType) {
    const std::string key = prototypeTypeKey(resourceType);
    if (auto existing = uniformResourcePointerTypeIds_.find(key);
        existing != uniformResourcePointerTypeIds_.end()) {
      return existing->second;
    }

    const std::string resourceValueTypeId =
        ensureUniformBufferDescriptorArrayType(resourceType, elementType);
    if (resourceValueTypeId.empty()) {
      return "";
    }
    const std::string id = "%ptr_Uniform_UniformBuffer_" +
                           sanitizeIdFragment(formatType(resourceType));
    uniformResourcePointerTypeIds_[key] = id;
    module_.addTypeInstruction(id + " = OpTypePointer Uniform " +
                         resourceValueTypeId);
    return id;
  }

  std::string ensureUniformBufferElementPointerType(const HIRType &elementType) {
    const std::string key = prototypeTypeKey(elementType);
    if (auto existing = uniformElementPointerTypeIds_.find(key);
        existing != uniformElementPointerTypeIds_.end()) {
      return existing->second;
    }

    const std::string elementTypeId = ensureType(elementType);
    if (elementTypeId.empty()) {
      return "";
    }
    const std::string id =
        "%ptr_Uniform_" + sanitizeIdFragment(formatType(elementType));
    uniformElementPointerTypeIds_[key] = id;
    module_.addTypeInstruction(id + " = OpTypePointer Uniform " + elementTypeId);
    return id;
  }

  std::string ensureImageType(const HIRType &textureType) {
    const std::string sampledScalar =
        textureSampledScalarTypeName(textureType.name);
    const std::string dimension = textureDimension(textureType.name);
    const bool arrayed = isArrayTextureType(textureType.name);
    const bool depthComparison = isComparisonTextureType(textureType.name);
    const std::string key =
        "image:" + sampledScalar + ":" + dimension + ":" +
        (arrayed ? "arrayed" : "single") + ":" +
        (depthComparison ? "depth" : "color");
    if (auto existing = imageTypeIds_.find(key); existing != imageTypeIds_.end()) {
      return existing->second;
    }

    const std::string sampledTypeId =
        ensureType(HIRType{sampledScalar, std::nullopt});
    if (sampledTypeId.empty()) {
      return "";
    }
    std::string imageName = "image_";
    if (depthComparison) {
      imageName += "depth_";
    } else if (sampledScalar != "float") {
      imageName += sampledScalar + "_";
    }
    imageName += textureIRDimension(textureType.name);
    const std::string id = "%" + sanitizeIdFragment(imageName);
    imageTypeIds_[key] = id;
    module_.addTypeInstruction(id + " = OpTypeImage " + sampledTypeId + " " +
                         dimension + " " + (depthComparison ? "1" : "0") +
                         " " + (arrayed ? "1" : "0") +
                         " 0 1 Unknown");
    return id;
  }

  std::string ensureStorageImageType(
      const HIRType &imageType,
      const std::optional<std::string> &explicitFormat = std::nullopt) {
    const HIRType imageElementType = arrayElementType(imageType);
    const std::string sampledScalar =
        textureSampledScalarTypeName(imageElementType.name);
    const std::string dimension = textureDimension(imageElementType.name);
    const bool arrayed = isArrayTextureType(imageElementType.name);
    const std::string format =
        storageImageSPIRVFormatNameFromFormat(
            explicitFormat.value_or(storageImageFormatName(imageElementType.name)));
    const std::string key = "storage_image:" + sampledScalar + ":" +
                            dimension + ":" +
                            (arrayed ? "arrayed" : "single") + ":" + format;
    if (auto existing = imageTypeIds_.find(key); existing != imageTypeIds_.end()) {
      return existing->second;
    }

    const std::string sampledTypeId =
        ensureType(HIRType{sampledScalar, std::nullopt});
    if (sampledTypeId.empty()) {
      return "";
    }
    std::string idStem = formatType(imageElementType);
    if (explicitFormat.has_value()) {
      idStem += "_" + format;
    }
    const std::string id = "%storage_image_" + sanitizeIdFragment(idStem);
    imageTypeIds_[key] = id;
    module_.addTypeInstruction(id + " = OpTypeImage " + sampledTypeId + " " +
                         dimension + " 0 " + (arrayed ? "1" : "0") +
                         " 0 2 " + format);
    return id;
  }

  std::string ensureImagePointerType(const HIRType &valueType) {
    const std::string key = "Image:" + prototypeTypeKey(valueType);
    if (auto existing = imagePointerTypeIds_.find(key);
        existing != imagePointerTypeIds_.end()) {
      return existing->second;
    }

    const std::string valueTypeId = ensureType(valueType);
    if (valueTypeId.empty()) {
      return "";
    }
    const std::string id =
        "%ptr_Image_" + sanitizeIdFragment(formatType(valueType));
    imagePointerTypeIds_[key] = id;
    module_.addTypeInstruction(id + " = OpTypePointer Image " + valueTypeId);
    return id;
  }

  std::string ensureSamplerType() {
    if (!samplerTypeId_.empty()) {
      return samplerTypeId_;
    }
    samplerTypeId_ = "%sampler";
    module_.addTypeInstruction(samplerTypeId_ + " = OpTypeSampler");
    return samplerTypeId_;
  }

  std::string ensureBoolVectorType(std::size_t width) {
    if (auto existing = boolVectorTypeIds_.find(width);
        existing != boolVectorTypeIds_.end()) {
      return existing->second;
    }

    const std::string boolTypeId = ensureType(HIRType{"bool", std::nullopt});
    const std::string id = "%v" + std::to_string(width) + "bool";
    boolVectorTypeIds_[width] = id;
    module_.addTypeInstruction(id + " = OpTypeVector " + boolTypeId + " " +
                         std::to_string(width));
    return id;
  }

  std::string ensureDescriptorArrayType(const HIRType &resourceType,
                                        const std::string &elementTypeId,
                                        std::string_view prefix,
                                        std::string_view idSuffix = {}) {
    if (!resourceType.arraySize.has_value()) {
      return elementTypeId;
    }

    const std::string key = std::string(prefix) + ":" + formatType(resourceType) +
                            ":" + elementTypeId;
    if (auto existing = descriptorArrayTypeIds_.find(key);
        existing != descriptorArrayTypeIds_.end()) {
      return existing->second;
    }

    std::string idStem = std::string(prefix) + ":" + formatType(resourceType);
    if (!idSuffix.empty()) {
      idStem += ":";
      idStem += idSuffix;
    }
    if (resourceType.arraySize->empty()) {
      const std::string id = "%runtimearr_" + sanitizeIdFragment(idStem);
      descriptorArrayTypeIds_[key] = id;
      module_.addTypeInstruction(id + " = OpTypeRuntimeArray " + elementTypeId);
      return id;
    }

    const std::optional<std::size_t> elementCount =
        prototypeArrayElementCount(resourceType, layoutContext_);
    if (!elementCount.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-resource",
                         "Vulkan prototype descriptor arrays require "
                         "fixed-size numeric or folded-constant resource "
                         "array sizes, got '" +
                             formatType(resourceType) + "'");
      return "";
    }

    const std::string id = "%arr_" + sanitizeIdFragment(idStem);
    descriptorArrayTypeIds_[key] = id;
    const std::string lengthId = ensureArrayLengthConstant(*elementCount);
    module_.addTypeInstruction(id + " = OpTypeArray " + elementTypeId + " " +
                         lengthId);
    return id;
  }

  std::string ensureUniformConstantPointerType(const HIRType &resourceType,
                                               const std::string &valueTypeId,
                                               std::string_view prefix,
                                               std::string_view idSuffix = {}) {
    const std::string key =
        "UniformConstant:" + std::string(prefix) + ":" +
        formatType(resourceType) + ":" + valueTypeId;
    if (auto existing = uniformConstantPointerTypeIds_.find(key);
        existing != uniformConstantPointerTypeIds_.end()) {
      return existing->second;
    }

    std::string idStem = std::string(prefix) + "_" + formatType(resourceType);
    if (!idSuffix.empty()) {
      idStem += "_";
      idStem += idSuffix;
    }
    const std::string id =
        "%ptr_UniformConstant_" + sanitizeIdFragment(idStem);
    uniformConstantPointerTypeIds_[key] = id;
    module_.addTypeInstruction(id + " = OpTypePointer UniformConstant " +
                         valueTypeId);
    return id;
  }

  std::string ensureUniformConstantElementPointerType(
      HIRResourceKind kind, const HIRType &elementType,
      const std::optional<std::string> &storageImageFormat = std::nullopt) {
    const std::string prefix = vulkanResourceBindingClass(kind);
    std::string valueTypeId;
    if (kind == HIRResourceKind::Texture) {
      valueTypeId = ensureImageType(elementType);
    } else if (kind == HIRResourceKind::StorageImage) {
      valueTypeId = ensureStorageImageType(elementType, storageImageFormat);
    } else if (kind == HIRResourceKind::Sampler) {
      valueTypeId = ensureSamplerType();
    }
    if (valueTypeId.empty()) {
      diagnostics_.error("vulkan.prototype-unsupported-resource",
                         "Vulkan prototype cannot compute UniformConstant "
                         "element pointer type for '" +
                             formatType(elementType) + "'");
      return "";
    }

    const std::string idSuffix =
        kind == HIRResourceKind::StorageImage && storageImageFormat.has_value()
            ? valueTypeId
            : std::string{};
    return ensureUniformConstantPointerType(elementType, valueTypeId, prefix,
                                            idSuffix);
  }

  std::string ensureUniformConstantDescriptorType(const HIRResource &resource) {
    if (resource.kind == HIRResourceKind::Texture) {
      const HIRType textureElementType = arrayElementType(resource.type);
      const std::string imageTypeId = ensureImageType(textureElementType);
      if (imageTypeId.empty()) {
        return "";
      }
      return ensureDescriptorArrayType(resource.type, imageTypeId, "image");
    }
    if (resource.kind == HIRResourceKind::StorageImage) {
      const HIRType imageElementType = arrayElementType(resource.type);
      const std::string imageTypeId =
          ensureStorageImageType(imageElementType, resource.storageImageFormat);
      if (imageTypeId.empty()) {
        return "";
      }
      const std::string idSuffix =
          resource.storageImageFormat.has_value() ? imageTypeId : std::string{};
      return ensureDescriptorArrayType(resource.type, imageTypeId,
                                       "storageImage", idSuffix);
    }
    if (resource.kind == HIRResourceKind::Sampler) {
      const std::string samplerTypeId = ensureSamplerType();
      if (samplerTypeId.empty()) {
        return "";
      }
      return ensureDescriptorArrayType(resource.type, samplerTypeId, "sampler");
    }

    diagnostics_.error("vulkan.prototype-unsupported-resource",
                       "Vulkan prototype UniformConstant descriptors currently "
                       "support only texture, storage image, and sampler "
                       "resources");
    return "";
  }

  std::string ensureSampledImageType(const HIRType &textureType) {
    const HIRType textureElementType = arrayElementType(textureType);
    const std::string key = formatType(textureElementType);
    if (auto existing = sampledImageTypeIds_.find(key);
        existing != sampledImageTypeIds_.end()) {
      return existing->second;
    }

    const std::string imageTypeId = ensureImageType(textureElementType);
    if (imageTypeId.empty()) {
      return "";
    }
    const std::string id =
        "%sampled_" + sanitizeIdFragment(formatType(textureElementType));
    sampledImageTypeIds_[key] = id;
    module_.addTypeInstruction(id + " = OpTypeSampledImage " + imageTypeId);
    return id;
  }

  std::size_t storageBufferArrayStride(const HIRType &elementType) {
    const std::optional<PrototypeStorageTypeLayout> layout =
        prototypeStorageTypeLayout(elementType, layoutContext_, false);
    if (!layout.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-struct-buffer",
                         "Vulkan prototype cannot compute storage-buffer "
                         "array stride for type '" +
                             elementType.name + "'");
      return 4;
    }
    return storageAlignTo(layout->sizeBytes, layout->alignmentBytes);
  }

  void registerStorageBuffer(const HIRResource &resource) {
    const HIRType elementType = prototypeBufferElementType(resource);
    PrototypeSPIRVStorageBuffer buffer;
    buffer.resourceType = resource.type;
    buffer.elementType = elementType;
    if (const std::optional<PrototypeStorageTypeLayout> layout =
            prototypeStorageTypeLayout(elementType, layoutContext_, true);
        layout.has_value()) {
      buffer.isRuntimeArrayBlock = layout->hasRuntimeArray;
    }
    buffer.elementPointerTypeId = ensureStorageBufferElementPointerType(elementType);
    const std::string structPointerTypeId =
        ensureStorageBufferResourcePointerType(resource.type, elementType);
    if (buffer.elementPointerTypeId.empty() || structPointerTypeId.empty()) {
      return;
    }
    buffer.variableId = "%resource_" + sanitizeIdFragment(resource.name);
    storageBuffers_[resource.name] = buffer;
    entryPointInterfaces_.push_back(buffer.variableId);
    module_.decorateDescriptorSetBinding(SPIRVModule::id(buffer.variableId),
                                         resource.set, resource.binding);
    module_.defineGlobalVariable(SPIRVModule::id(buffer.variableId),
                                 SPIRVModule::id(structPointerTypeId),
                                 SPIRVStorageClass::StorageBuffer);
  }

  void registerUniformBuffer(const HIRResource &resource) {
    const HIRType elementType = prototypeUniformBufferElementType(resource);
    PrototypeSPIRVUniformBuffer buffer;
    buffer.resourceType = resource.type;
    buffer.elementType = elementType;
    const std::string pointerTypeId =
        ensureUniformBufferResourcePointerType(resource.type, elementType);
    if (pointerTypeId.empty()) {
      return;
    }
    buffer.variableId = "%resource_" + sanitizeIdFragment(resource.name);
    uniformBuffers_[resource.name] = buffer;
    entryPointInterfaces_.push_back(buffer.variableId);
    module_.addDecoration(SPIRVModule::id(buffer.variableId), "DescriptorSet",
                          {std::to_string(resource.set)});
    module_.addDecoration(SPIRVModule::id(buffer.variableId), "Binding",
                          {std::to_string(resource.binding)});
    module_.addGlobalInstruction(buffer.variableId + " = OpVariable " +
                                   pointerTypeId + " Uniform");
  }

  void registerWorkgroupSharedResource(const HIRResource &resource) {
    const std::string pointerTypeId = ensureWorkgroupPointerType(resource.type);
    if (pointerTypeId.empty()) {
      return;
    }
    const std::string variableId =
        "%resource_" + sanitizeIdFragment(resource.name);
    workgroupShared_[resource.name] =
        PrototypeSPIRVWorkgroupShared{resource.type, variableId};
    module_.addGlobalInstruction(variableId + " = OpVariable " +
                                   pointerTypeId + " Workgroup");
  }

  void registerUniformConstantDescriptor(const HIRResource &resource) {
    PrototypeSPIRVDescriptorResource descriptor;
    descriptor.kind = resource.kind;
    descriptor.type = resource.type;
    descriptor.storageImageFormat = resource.storageImageFormat;
    if (isRuntimeDescriptorArray(resource) &&
        (resource.kind == HIRResourceKind::Texture ||
         resource.kind == HIRResourceKind::Sampler)) {
      usesRuntimeDescriptorArray_ = true;
    }
    const std::string valueTypeId = ensureUniformConstantDescriptorType(resource);
    if (valueTypeId.empty()) {
      return;
    }
    const std::string idSuffix =
        resource.kind == HIRResourceKind::StorageImage &&
                resource.storageImageFormat.has_value()
            ? valueTypeId
            : std::string{};
    const std::string pointerTypeId =
        ensureUniformConstantPointerType(resource.type, valueTypeId,
                                         vulkanResourceBindingClass(resource.kind),
                                         idSuffix);
    if (pointerTypeId.empty()) {
      return;
    }
    descriptor.variableId = "%resource_" + sanitizeIdFragment(resource.name);
    uniformConstantDescriptors_[resource.name] = descriptor;
    entryPointInterfaces_.push_back(descriptor.variableId);
    module_.addDecoration(SPIRVModule::id(descriptor.variableId),
                          "DescriptorSet", {std::to_string(resource.set)});
    module_.addDecoration(SPIRVModule::id(descriptor.variableId), "Binding",
                          {std::to_string(resource.binding)});
    const VulkanStorageImageAccessDecoration accessDecoration =
        vulkanStorageImageAccessDecoration(resource);
    if (accessDecoration != VulkanStorageImageAccessDecoration::None) {
      module_.addDecoration(
          SPIRVModule::id(descriptor.variableId),
          vulkanStorageImageAccessDecorationName(accessDecoration));
    }
    module_.addGlobalInstruction(descriptor.variableId + " = OpVariable " +
                                   pointerTypeId + " UniformConstant");
  }

  void requireNonUniformDescriptorIndex(PrototypeNonUniformDescriptorUse use) {
    usesNonUniformDescriptorIndex_ = true;
    switch (use) {
    case PrototypeNonUniformDescriptorUse::SampledImage:
      usesSampledImageArrayNonUniformIndexing_ = true;
      break;
    case PrototypeNonUniformDescriptorUse::StorageImage:
      usesStorageImageArrayNonUniformIndexing_ = true;
      break;
    case PrototypeNonUniformDescriptorUse::StorageBuffer:
      usesStorageBufferArrayNonUniformIndexing_ = true;
      break;
    }
  }

  void decorateNonUniform(const std::string &id) {
    if (id.empty() || !nonUniformDecorationIds_.insert(id).second) {
      return;
    }
    module_.addDecoration(SPIRVModule::id(id), "NonUniformEXT");
  }

  void addEntryPointInterface(const std::string &id) {
    if (id.empty() || !entryPointInterfaceIds_.insert(id).second) {
      return;
    }
    entryPointInterfaces_.push_back(id);
  }

  std::optional<PrototypeSPIRVValue> emitDescriptorIndexExpression(
      const HIRExpression &expression, PrototypeNonUniformDescriptorUse use) {
    bool nonUniform = false;
    const HIRExpression *indexExpression = &expression;
    if (expression.kind == HIRExpressionKind::NonUniform) {
      if (expression.children.size() != 1) {
        diagnostics_.error("vulkan.prototype-unsupported-nonuniform-index",
                           "Vulkan prototype nonuniform descriptor index "
                           "markers require exactly one operand");
        return std::nullopt;
      }
      nonUniform = true;
      indexExpression = &expression.children.front();
    }

    std::optional<PrototypeSPIRVValue> value = emitExpression(*indexExpression);
    if (!value.has_value()) {
      return std::nullopt;
    }
    if (nonUniform) {
      requireNonUniformDescriptorIndex(use);
      decorateNonUniform(value->id);
      value->nonUniformDescriptor = true;
    }
    return value;
  }

  std::string ensureFunctionType(
      const HIRType &returnType, const std::vector<HIRType> &parameterTypes,
      const std::vector<bool> &pointerParameters = {}) {
    std::string key = prototypeTypeKey(returnType) + "(";
    for (std::size_t index = 0; index < parameterTypes.size(); ++index) {
      if (index < pointerParameters.size() && pointerParameters[index]) {
        key += "ptr:";
      }
      const HIRType &parameterType = parameterTypes[index];
      key += prototypeTypeKey(parameterType) + ";";
    }
    key += ")";
    if (auto existing = functionTypeIds_.find(key);
        existing != functionTypeIds_.end()) {
      return existing->second;
    }

    const std::string returnTypeId = ensureType(returnType);
    if (returnTypeId.empty()) {
      return "";
    }
    std::vector<std::string> parameterTypeIds;
    parameterTypeIds.reserve(parameterTypes.size());
    for (std::size_t index = 0; index < parameterTypes.size(); ++index) {
      const HIRType &parameterType = parameterTypes[index];
      const bool pointerParameter =
          index < pointerParameters.size() && pointerParameters[index];
      const std::string parameterTypeId =
          pointerParameter ? ensureFunctionPointerType(parameterType)
                           : ensureType(parameterType);
      if (parameterTypeId.empty()) {
        return "";
      }
      parameterTypeIds.push_back(parameterTypeId);
    }

    const std::string id = "%fn_" + sanitizeIdFragment(key);
    functionTypeIds_[key] = id;
    std::string line = id + " = OpTypeFunction " + returnTypeId;
    for (const std::string &parameterTypeId : parameterTypeIds) {
      line += " " + parameterTypeId;
    }
    module_.addTypeInstruction(std::move(line));
    return id;
  }

  std::string ensureGLSLStd450Import() {
    const SPIRVId importId = module_.addExtInstImport(
        SPIRVModule::id("%glsl_std_450"),
        SPIRVExtInstInstructionSet::GLSLStd450);
    return importId.str();
  }

  std::string ensureNumericConstant(const HIRType &type, std::string_view value) {
    const std::string key = type.name + ":" + std::string(value);
    if (auto existing = constantIds_.find(key); existing != constantIds_.end()) {
      return existing->second;
    }

    const std::string typeId = ensureType(type);
    const std::string id = "%const_" + sanitizeIdFragment(type.name) + "_" +
                           sanitizeNumericConstantIdFragment(value);
    constantIds_[key] = id;
    module_.addConstantInstruction(id + " = OpConstant " + typeId + " " +
                             std::string(value));
    return id;
  }

  std::string ensureArrayLengthConstant(std::size_t value) {
    const std::string text = std::to_string(value);
    const std::string key = "uint:" + text;
    if (auto existing = constantIds_.find(key); existing != constantIds_.end()) {
      return existing->second;
    }

    const std::string typeId = ensureType(HIRType{"uint", std::nullopt});
    const std::string id = "%const_uint_" + text;
    constantIds_[key] = id;
    module_.addTypeInstruction(id + " = OpConstant " + typeId + " " + text);
    return id;
  }

  std::string ensureBoolConstant(bool value) {
    const std::string key = value ? "bool:true" : "bool:false";
    if (auto existing = constantIds_.find(key); existing != constantIds_.end()) {
      return existing->second;
    }

    const std::string typeId = ensureType(HIRType{"bool", std::nullopt});
    const std::string id = value ? "%const_bool_true" : "%const_bool_false";
    constantIds_[key] = id;
    module_.addConstantInstruction(id + std::string(value ? " = OpConstantTrue "
                                                   : " = OpConstantFalse ") +
                             typeId);
    return id;
  }

  std::string ensureIvec2Constant(const PrototypeTextureOffset &offset) {
    const std::string key = "ivec2:" + std::to_string(offset[0]) + "," +
                            std::to_string(offset[1]);
    if (auto existing = constantIds_.find(key); existing != constantIds_.end()) {
      return existing->second;
    }

    const std::string typeId = ensureType(HIRType{"ivec2", std::nullopt});
    const std::string x =
        ensureNumericConstant(HIRType{"int", std::nullopt},
                              std::to_string(offset[0]));
    const std::string y =
        ensureNumericConstant(HIRType{"int", std::nullopt},
                              std::to_string(offset[1]));
    const std::string id = "%const_ivec2_" +
                           sanitizeIntegerConstantIdFragment(offset[0]) + "_" +
                           sanitizeIntegerConstantIdFragment(offset[1]);
    constantIds_[key] = id;
    module_.addConstantInstruction(id + " = OpConstantComposite " + typeId + " " +
                             x + " " + y);
    return id;
  }

  std::string nextTemp() {
    return module_.nextResultId("tmp").str();
  }

  std::string nextLabel(std::string_view prefix) {
    return module_.nextLabelId(prefix).str();
  }

  std::string makeVariableId(std::string_view name) {
    const std::string base = "%var_" + sanitizeIdFragment(name);
    if (variableIds_.insert(base).second) {
      return base;
    }
    for (std::size_t index = 0;; ++index) {
      const std::string candidate = base + "_" + std::to_string(index);
      if (variableIds_.insert(candidate).second) {
        return candidate;
      }
    }
  }

  std::optional<PrototypeSPIRVValue> emitVectorConstructor(
      const HIRExpression &expression) {
    const std::optional<std::size_t> width = prototypeVectorWidth(expression.type);
    if (!width.has_value() || expression.value != expression.type.name ||
        expression.children.empty()) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype vector constructors require a "
                         "constructor name matching the result type");
      return std::nullopt;
    }

    if (expression.children.size() == 1 &&
        samePrototypeType(expression.children.front().type, expression.type)) {
      return emitExpression(expression.children.front());
    }

    const HIRType componentType = prototypeVectorComponentType(expression.type);
    const std::string componentTypeId = ensureType(componentType);
    if (componentTypeId.empty()) {
      return std::nullopt;
    }

    std::vector<std::string> constituents;
    constituents.reserve(*width);
    for (const HIRExpression &child : expression.children) {
      std::optional<PrototypeSPIRVValue> value = emitExpression(child);
      if (!value.has_value()) {
        return std::nullopt;
      }
      if (samePrototypeType(value->type, componentType)) {
        constituents.push_back(value->id);
        continue;
      }

      const std::optional<std::size_t> childWidth =
          prototypeVectorConstructorConstituentWidth(value->type,
                                                     componentType);
      if (!childWidth.has_value()) {
        diagnostics_.error("vulkan.prototype-unsupported-expression",
                           "Vulkan prototype vector constructors require "
                           "scalar/vector constituents matching the result "
                           "component type");
        return std::nullopt;
      }
      for (std::size_t index = 0; index < *childWidth; ++index) {
        const std::string componentId = nextTemp();
        instructionLines_.push_back(componentId + " = OpCompositeExtract " +
                                    componentTypeId + " " + value->id + " " +
                                    std::to_string(index));
        constituents.push_back(componentId);
      }
    }

    if (constituents.size() == 1) {
      constituents.resize(*width, constituents.front());
    }
    if (constituents.size() != *width) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype vector constructors require one "
                         "scalar splat value or constituents matching the "
                         "result vector width");
      return std::nullopt;
    }

    const std::string resultId = nextTemp();
    const std::string typeId = ensureType(expression.type);
    std::ostringstream instruction;
    instruction << resultId << " = OpCompositeConstruct " << typeId;
    for (const std::string &constituent : constituents) {
      instruction << " " << constituent;
    }
    instructionLines_.push_back(instruction.str());
    return PrototypeSPIRVValue{expression.type, resultId};
  }

  std::optional<PrototypeSPIRVValue> emitScalarConstructor(
      const HIRExpression &expression) {
    if (!isPrototypeNumericScalarType(expression.type) ||
        expression.children.size() != 1) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype scalar constructors require one "
                         "numeric scalar operand");
      return std::nullopt;
    }

    std::optional<PrototypeSPIRVValue> value =
        emitExpression(expression.children.front());
    if (!value.has_value()) {
      return std::nullopt;
    }

    const std::string opcode =
        prototypeScalarConversionOpcode(value->type, expression.type);
    if (opcode.empty()) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-expression",
          "Vulkan prototype scalar numeric constructors currently support "
          "same-type values plus int/uint-to-float and float-to-int/uint "
          "conversions");
      return std::nullopt;
    }
    if (opcode == "identity") {
      return PrototypeSPIRVValue{expression.type, value->id};
    }

    const std::string typeId = ensureType(expression.type);
    if (typeId.empty()) {
      return std::nullopt;
    }
    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = " + opcode + " " + typeId +
                                " " + value->id);
    return PrototypeSPIRVValue{expression.type, resultId};
  }

  std::optional<PrototypeSPIRVValue>
  emitFloatScalarValue(const PrototypeSPIRVValue &value) {
    const HIRType floatType{"float", std::nullopt};
    if (samePrototypeType(value.type, floatType)) {
      return value;
    }
    const std::string opcode = prototypeScalarConversionOpcode(value.type,
                                                               floatType);
    if (opcode.empty() || opcode == "identity") {
      diagnostics_.error(
          "vulkan.prototype-unsupported-expression",
          "Vulkan prototype matrix constructors require numeric scalar "
          "constituents convertible to float");
      return std::nullopt;
    }
    const std::string typeId = ensureType(floatType);
    if (typeId.empty()) {
      return std::nullopt;
    }
    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = " + opcode + " " + typeId +
                                " " + value.id);
    return PrototypeSPIRVValue{floatType, resultId};
  }

  bool appendMatrixConstructorScalars(const HIRExpression &expression,
                                      std::vector<std::string> &scalars) {
    std::optional<PrototypeSPIRVValue> value = emitExpression(expression);
    if (!value.has_value()) {
      return false;
    }

    if (isPrototypeNumericScalarType(value->type)) {
      std::optional<PrototypeSPIRVValue> scalar = emitFloatScalarValue(*value);
      if (!scalar.has_value()) {
        return false;
      }
      scalars.push_back(scalar->id);
      return true;
    }

    if (!isPrototypeVectorType(value->type) ||
        !isPrototypeNumericScalarType(prototypeVectorComponentType(value->type))) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-expression",
          "Vulkan prototype matrix constructors require numeric scalar/vector "
          "constituents or a single scalar/matrix operand");
      return false;
    }

    const HIRType componentType = prototypeVectorComponentType(value->type);
    const std::string componentTypeId = ensureType(componentType);
    if (componentTypeId.empty()) {
      return false;
    }
    const std::optional<std::size_t> width = prototypeVectorWidth(value->type);
    if (!width.has_value()) {
      return false;
    }

    for (std::size_t index = 0; index < *width; ++index) {
      const std::string componentId = nextTemp();
      instructionLines_.push_back(componentId + " = OpCompositeExtract " +
                                  componentTypeId + " " + value->id + " " +
                                  std::to_string(index));
      std::optional<PrototypeSPIRVValue> scalar =
          emitFloatScalarValue(PrototypeSPIRVValue{componentType, componentId});
      if (!scalar.has_value()) {
        return false;
      }
      scalars.push_back(scalar->id);
    }
    return true;
  }

  std::optional<std::string>
  emitMatrixColumn(const HIRType &matrixType,
                   std::span<const std::string> scalars) {
    const std::optional<std::size_t> dimension =
        prototypeMatrixDimension(matrixType);
    if (!dimension.has_value() || scalars.size() != *dimension) {
      return std::nullopt;
    }
    const HIRType columnType = prototypeMatrixColumnType(matrixType);
    const std::string columnTypeId = ensureType(columnType);
    if (columnTypeId.empty()) {
      return std::nullopt;
    }

    const std::string columnId = nextTemp();
    std::ostringstream instruction;
    instruction << columnId << " = OpCompositeConstruct " << columnTypeId;
    for (const std::string &scalar : scalars) {
      instruction << " " << scalar;
    }
    instructionLines_.push_back(instruction.str());
    return columnId;
  }

  std::optional<PrototypeSPIRVValue>
  emitMatrixFromScalars(const HIRType &matrixType,
                        const std::vector<std::string> &scalars) {
    const std::optional<std::size_t> dimension =
        prototypeMatrixDimension(matrixType);
    if (!dimension.has_value() || scalars.size() != (*dimension * *dimension)) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-expression",
          "Vulkan prototype matrix constructors require constituents matching "
          "the result matrix element count");
      return std::nullopt;
    }

    std::vector<std::string> columns;
    columns.reserve(*dimension);
    for (std::size_t column = 0; column < *dimension; ++column) {
      const std::size_t begin = column * *dimension;
      const std::optional<std::string> columnId =
          emitMatrixColumn(matrixType, std::span<const std::string>(
                                           scalars.data() + begin, *dimension));
      if (!columnId.has_value()) {
        return std::nullopt;
      }
      columns.push_back(*columnId);
    }

    const std::string typeId = ensureType(matrixType);
    if (typeId.empty()) {
      return std::nullopt;
    }
    const std::string resultId = nextTemp();
    std::ostringstream instruction;
    instruction << resultId << " = OpCompositeConstruct " << typeId;
    for (const std::string &column : columns) {
      instruction << " " << column;
    }
    instructionLines_.push_back(instruction.str());
    return PrototypeSPIRVValue{matrixType, resultId};
  }

  std::optional<PrototypeSPIRVValue>
  emitMatrixFromScalar(const HIRType &matrixType,
                       const PrototypeSPIRVValue &value) {
    const std::optional<PrototypeSPIRVValue> diagonal =
        emitFloatScalarValue(value);
    if (!diagonal.has_value()) {
      return std::nullopt;
    }
    const std::optional<std::size_t> dimension =
        prototypeMatrixDimension(matrixType);
    if (!dimension.has_value()) {
      return std::nullopt;
    }

    const std::string zero =
        ensureNumericConstant(HIRType{"float", std::nullopt}, "0.0");
    std::vector<std::string> scalars;
    scalars.reserve(*dimension * *dimension);
    for (std::size_t column = 0; column < *dimension; ++column) {
      for (std::size_t row = 0; row < *dimension; ++row) {
        scalars.push_back(column == row ? diagonal->id : zero);
      }
    }
    return emitMatrixFromScalars(matrixType, scalars);
  }

  std::optional<PrototypeSPIRVValue>
  emitMatrixFromMatrix(const HIRType &matrixType,
                       const PrototypeSPIRVValue &value) {
    if (samePrototypeType(matrixType, value.type)) {
      return value;
    }
    const std::optional<std::size_t> targetDimension =
        prototypeMatrixDimension(matrixType);
    const std::optional<std::size_t> sourceDimension =
        prototypeMatrixDimension(value.type);
    if (!targetDimension.has_value() || !sourceDimension.has_value()) {
      return std::nullopt;
    }

    const HIRType floatType{"float", std::nullopt};
    const std::string floatTypeId = ensureType(floatType);
    if (floatTypeId.empty()) {
      return std::nullopt;
    }
    const std::string zero = ensureNumericConstant(floatType, "0.0");
    const std::string one = ensureNumericConstant(floatType, "1.0");

    std::vector<std::string> scalars;
    scalars.reserve(*targetDimension * *targetDimension);
    for (std::size_t column = 0; column < *targetDimension; ++column) {
      for (std::size_t row = 0; row < *targetDimension; ++row) {
        if (column < *sourceDimension && row < *sourceDimension) {
          const std::string componentId = nextTemp();
          instructionLines_.push_back(
              componentId + " = OpCompositeExtract " + floatTypeId + " " +
              value.id + " " + std::to_string(column) + " " +
              std::to_string(row));
          scalars.push_back(componentId);
        } else {
          scalars.push_back(column == row ? one : zero);
        }
      }
    }
    return emitMatrixFromScalars(matrixType, scalars);
  }

  std::optional<PrototypeSPIRVValue> emitMatrixConstructor(
      const HIRExpression &expression) {
    if (!prototypeMatrixDimension(expression.type).has_value() ||
        expression.children.empty()) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype matrix constructors require a "
                         "mat2/mat3/mat4 result type and operands");
      return std::nullopt;
    }

    if (expression.children.size() == 1) {
      std::optional<PrototypeSPIRVValue> value =
          emitExpression(expression.children.front());
      if (!value.has_value()) {
        return std::nullopt;
      }
      if (isPrototypeMatrixType(value->type)) {
        return emitMatrixFromMatrix(expression.type, *value);
      }
      if (isPrototypeNumericScalarType(value->type)) {
        return emitMatrixFromScalar(expression.type, *value);
      }
    }

    std::vector<std::string> scalars;
    const std::optional<std::size_t> dimension =
        prototypeMatrixDimension(expression.type);
    scalars.reserve(dimension.value_or(0) * dimension.value_or(0));
    for (const HIRExpression &child : expression.children) {
      if (!appendMatrixConstructorScalars(child, scalars)) {
        return std::nullopt;
      }
    }
    return emitMatrixFromScalars(expression.type, scalars);
  }

  std::optional<PrototypeSPIRVValue>
  emitVectorSplat(const HIRType &vectorType,
                  const PrototypeSPIRVValue &scalar) {
    const std::optional<std::size_t> width = prototypeVectorWidth(vectorType);
    if (!width.has_value() ||
        !samePrototypeType(scalar.type,
                           prototypeVectorComponentType(vectorType))) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-expression",
          "Vulkan prototype scalar splats require a scalar operand matching "
          "the vector component type");
      return std::nullopt;
    }

    const std::string resultId = nextTemp();
    const std::string typeId = ensureType(vectorType);
    if (typeId.empty()) {
      return std::nullopt;
    }

    std::ostringstream instruction;
    instruction << resultId << " = OpCompositeConstruct " << typeId;
    for (std::size_t index = 0; index < *width; ++index) {
      instruction << " " << scalar.id;
    }
    instructionLines_.push_back(instruction.str());
    return PrototypeSPIRVValue{vectorType, resultId};
  }

  std::optional<PrototypeSPIRVValue> emitVectorMemberAccess(
      const HIRExpression &expression) {
    if (expression.children.empty()) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype member access requires a base "
                         "expression");
      return std::nullopt;
    }

    std::optional<PrototypeSPIRVValue> base =
        emitExpression(expression.children.front());
    if (!base.has_value()) {
      return std::nullopt;
    }

    const std::optional<std::vector<std::size_t>> indices =
        prototypeVectorMemberIndices(base->type, expression.value);
    if (!indices.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype member access supports only float-vector "
                         "swizzles using xyzw/rgba/stpq components");
      return std::nullopt;
    }

    if (indices->size() == 1) {
      const HIRType resultType = expression.type;
      if (!samePrototypeType(resultType, prototypeVectorComponentType(base->type))) {
        diagnostics_.error("vulkan.prototype-unsupported-expression",
                           "Vulkan prototype single-component vector swizzles "
                           "must produce the vector component type");
        return std::nullopt;
      }
      const std::string resultId = nextTemp();
      const std::string typeId = ensureType(resultType);
      instructionLines_.push_back(resultId + " = OpCompositeExtract " + typeId +
                                  " " + base->id + " " +
                                  std::to_string(indices->front()));
      return PrototypeSPIRVValue{resultType, resultId};
    }

    const HIRType resultType = expression.type;
    const std::optional<std::size_t> resultWidth =
        prototypeVectorWidth(resultType);
    if (!resultWidth.has_value() || *resultWidth != indices->size() ||
        !samePrototypeType(prototypeVectorComponentType(resultType),
                           prototypeVectorComponentType(base->type))) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype multi-component vector swizzles "
                         "must produce matching vector values");
      return std::nullopt;
    }

    const std::string resultId = nextTemp();
    const std::string typeId = ensureType(resultType);
    std::ostringstream instruction;
    instruction << resultId << " = OpVectorShuffle " << typeId << " "
                << base->id << " " << base->id;
    for (const std::size_t index : *indices) {
      instruction << " " << index;
    }
    instructionLines_.push_back(instruction.str());
    return PrototypeSPIRVValue{resultType, resultId};
  }

  bool isStructStorageBufferMemberAccess(
      const HIRExpression &expression, bool allowArrayLeaf = false) const {
    const std::optional<PrototypeStructMemberChain> chain =
        prototypeStructMemberChain(expression);
    if (!chain.has_value()) {
      return false;
    }
    const HIRExpression *base = prototypeStructMemberChainBase(*chain);
    if (base == nullptr || base->kind != HIRExpressionKind::Identifier) {
      return false;
    }
    const auto buffer = storageBuffers_.find(base->value);
    if (buffer == storageBuffers_.end() ||
        isPrototypeArithmeticType(buffer->second.elementType)) {
      return false;
    }
    const std::optional<PrototypeStructStorageBufferAccess> access =
        prototypeStructStorageBufferAccess(
            *chain, buffer->second.resourceType, buffer->second.isRuntimeArrayBlock,
            base->value, nullptr);
    if (!access.has_value()) {
      return false;
    }
    return resolvePrototypeStructFieldPath(buffer->second.elementType,
                                           access->fieldSteps, structs_,
                                           constants_, nullptr, allowArrayLeaf)
        .has_value();
  }

  bool isKnownZeroIndexExpression(const HIRExpression &expression) const {
    if (isPrototypeZeroLiteral(expression)) {
      return true;
    }
    if (expression.kind == HIRExpressionKind::Group &&
        !expression.children.empty()) {
      return isKnownZeroIndexExpression(expression.children.front());
    }
    if (expression.kind == HIRExpressionKind::Unary &&
        expression.value == "+" && expression.children.size() == 1) {
      return isKnownZeroIndexExpression(expression.children.front());
    }
    if (expression.kind == HIRExpressionKind::Identifier) {
      const auto local = locals_.find(expression.value);
      return local != locals_.end() && local->second.knownZeroIndex;
    }
    return false;
  }

  std::optional<std::string> emitStorageBufferMemberPointer(
      const HIRExpression &memberAccess, bool allowArrayLeaf = false) {
    const std::optional<PrototypeStructMemberChain> chain =
        prototypeStructMemberChain(memberAccess);
    if (!chain.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-assignment-target",
                         "Vulkan prototype struct storage-buffer field "
                         "access requires a storage-buffer resource base");
      return std::nullopt;
    }

    const HIRExpression *base = prototypeStructMemberChainBase(*chain);
    if (base == nullptr || base->kind != HIRExpressionKind::Identifier) {
      diagnostics_.error("vulkan.prototype-unsupported-assignment-target",
                         "Vulkan prototype struct storage-buffer field "
                         "access requires an identifier resource base");
      return std::nullopt;
    }
    const std::string &resourceName = base->value;
    const auto buffer = storageBuffers_.find(resourceName);
    if (buffer == storageBuffers_.end()) {
      diagnostics_.error("vulkan.prototype-unsupported-assignment-target",
                         "Vulkan prototype binary emission cannot resolve "
                         "storage buffer resource '" +
                             resourceName + "'");
      return std::nullopt;
    }

    const std::optional<PrototypeStructStorageBufferAccess> access =
        prototypeStructStorageBufferAccess(
            *chain, buffer->second.resourceType,
            buffer->second.isRuntimeArrayBlock, resourceName, &diagnostics_);
    if (!access.has_value()) {
      return std::nullopt;
    }

    const std::optional<PrototypeResolvedStructFieldPath> fieldPath =
        resolvePrototypeStructFieldPath(buffer->second.elementType,
                                        access->fieldSteps, structs_,
                                        constants_, &diagnostics_,
                                        allowArrayLeaf);
    if (!fieldPath.has_value()) {
      return std::nullopt;
    }

    const std::string zero =
        ensureNumericConstant(HIRType{"int", std::nullopt}, "0");
    const std::string pointerTypeId =
        ensureStorageBufferElementPointerType(fieldPath->valueType);
    if (pointerTypeId.empty()) {
      return std::nullopt;
    }

    const std::string pointer = nextTemp();
    std::ostringstream accessChain;
    accessChain << pointer << " = OpAccessChain " << pointerTypeId << " "
                << buffer->second.variableId;
    if (access->descriptorIndex != nullptr) {
      std::optional<PrototypeSPIRVValue> descriptorIndex =
          emitDescriptorIndexExpression(
              *access->descriptorIndex,
              PrototypeNonUniformDescriptorUse::StorageBuffer);
      if (!descriptorIndex.has_value()) {
        return std::nullopt;
      }
      accessChain << " " << descriptorIndex->id;
    }
    if (access->runtimeBlockIndex != nullptr) {
      if (!isKnownZeroIndexExpression(*access->runtimeBlockIndex)) {
        diagnostics_.error(
            "vulkan.prototype-unsupported-runtime-array-block-index",
            "Vulkan prototype runtime-array storage-buffer blocks require "
            "a literal or provably local-zero outer resource index; index the "
            "runtime array field instead");
        return std::nullopt;
      }
    }
    if (access->elementIndex != nullptr) {
      std::optional<PrototypeSPIRVValue> elementIndex =
          emitExpression(*access->elementIndex);
      if (!elementIndex.has_value()) {
        return std::nullopt;
      }
      accessChain << " " << zero << " " << elementIndex->id;
    } else if (!buffer->second.isRuntimeArrayBlock) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-struct-buffer",
          "Vulkan prototype direct storage-buffer member access is available "
          "only for runtime-tail singleton blocks");
      return std::nullopt;
    }
    for (const PrototypeResolvedAccessIndex &accessIndex : fieldPath->indices) {
      if (accessIndex.constantIndex.has_value()) {
        accessChain << " "
                    << ensureNumericConstant(
                           HIRType{"int", std::nullopt},
                           std::to_string(*accessIndex.constantIndex));
        continue;
      }
      if (accessIndex.dynamicIndex == nullptr) {
        diagnostics_.error("vulkan.prototype-unsupported-struct-buffer",
                           "Vulkan prototype cannot emit an empty struct "
                           "storage-buffer access-chain index");
        return std::nullopt;
      }
      std::optional<PrototypeSPIRVValue> dynamicIndex =
          emitExpression(*accessIndex.dynamicIndex);
      if (!dynamicIndex.has_value()) {
        return std::nullopt;
      }
      accessChain << " " << dynamicIndex->id;
    }

    instructionLines_.push_back(accessChain.str());
    if (access->descriptorIndex != nullptr) {
      const HIRExpression &descriptorIndex = *access->descriptorIndex;
      if (descriptorIndex.kind == HIRExpressionKind::NonUniform) {
        decorateNonUniform(pointer);
      }
    }
    return pointer;
  }

  std::optional<PrototypeSPIRVValue> emitStorageBufferMemberLoad(
      const HIRExpression &memberAccess, bool allowArrayLeaf = false) {
    std::optional<std::string> pointer =
        emitStorageBufferMemberPointer(memberAccess, allowArrayLeaf);
    if (!pointer.has_value()) {
      return std::nullopt;
    }
    const std::string typeId = ensureType(memberAccess.type);
    if (typeId.empty()) {
      return std::nullopt;
    }
    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = OpLoad " + typeId + " " +
                                *pointer);
    return PrototypeSPIRVValue{memberAccess.type, resultId};
  }

  bool isStructUniformBufferMemberAccess(
      const HIRExpression &expression, bool allowArrayLeaf = false) const {
    const std::optional<PrototypeStructMemberChain> chain =
        prototypeStructMemberChain(expression);
    if (!chain.has_value()) {
      return false;
    }
    const HIRExpression *base = prototypeStructMemberChainBase(*chain);
    if (base == nullptr || base->kind != HIRExpressionKind::Identifier) {
      return false;
    }
    const auto buffer = uniformBuffers_.find(base->value);
    if (buffer == uniformBuffers_.end()) {
      return false;
    }
    const std::optional<PrototypeStructUniformBufferAccess> access =
        prototypeStructUniformBufferAccess(
            *chain, buffer->second.resourceType, base->value, nullptr);
    if (!access.has_value()) {
      return false;
    }
    return resolvePrototypeStructFieldPath(buffer->second.elementType,
                                           access->fieldSteps, structs_,
                                           constants_, nullptr, allowArrayLeaf)
        .has_value();
  }

  std::optional<std::string> emitUniformBufferMemberPointer(
      const HIRExpression &memberAccess, bool allowArrayLeaf = false) {
    const std::optional<PrototypeStructMemberChain> chain =
        prototypeStructMemberChain(memberAccess);
    if (!chain.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-uniform-buffer",
                         "Vulkan prototype uniform-buffer field access "
                         "requires a uniform resource base");
      return std::nullopt;
    }

    const HIRExpression *base = prototypeStructMemberChainBase(*chain);
    if (base == nullptr || base->kind != HIRExpressionKind::Identifier) {
      diagnostics_.error("vulkan.prototype-unsupported-uniform-buffer",
                         "Vulkan prototype uniform-buffer field access "
                         "requires an identifier resource base");
      return std::nullopt;
    }
    const std::string &resourceName = base->value;
    const auto buffer = uniformBuffers_.find(resourceName);
    if (buffer == uniformBuffers_.end()) {
      diagnostics_.error("vulkan.prototype-unsupported-uniform-buffer",
                         "Vulkan prototype binary emission cannot resolve "
                         "uniform-buffer resource '" +
                             resourceName + "'");
      return std::nullopt;
    }

    const std::optional<PrototypeStructUniformBufferAccess> access =
        prototypeStructUniformBufferAccess(*chain, buffer->second.resourceType,
                                           resourceName, &diagnostics_);
    if (!access.has_value()) {
      return std::nullopt;
    }

    const std::optional<PrototypeResolvedStructFieldPath> fieldPath =
        resolvePrototypeStructFieldPath(buffer->second.elementType,
                                        access->fieldSteps, structs_,
                                        constants_, &diagnostics_,
                                        allowArrayLeaf);
    if (!fieldPath.has_value()) {
      return std::nullopt;
    }

    const std::string pointerTypeId =
        ensureUniformBufferElementPointerType(fieldPath->valueType);
    if (pointerTypeId.empty()) {
      return std::nullopt;
    }

    const std::string pointer = nextTemp();
    std::ostringstream accessChain;
    accessChain << pointer << " = OpAccessChain " << pointerTypeId << " "
                << buffer->second.variableId;
    if (access->descriptorIndex != nullptr) {
      if (access->descriptorIndex->kind == HIRExpressionKind::NonUniform) {
        diagnostics_.error(
            "vulkan.prototype-unsupported-nonuniform-index",
            "Vulkan prototype uniform-buffer descriptor arrays do not yet "
            "support nonuniform descriptor indices");
        return std::nullopt;
      }
      std::optional<PrototypeSPIRVValue> descriptorIndex =
          emitExpression(*access->descriptorIndex);
      if (!descriptorIndex.has_value()) {
        return std::nullopt;
      }
      accessChain << " " << descriptorIndex->id;
    }
    for (const PrototypeResolvedAccessIndex &accessIndex : fieldPath->indices) {
      if (accessIndex.constantIndex.has_value()) {
        accessChain << " "
                    << ensureNumericConstant(
                           HIRType{"int", std::nullopt},
                           std::to_string(*accessIndex.constantIndex));
        continue;
      }
      if (accessIndex.dynamicIndex == nullptr) {
        diagnostics_.error("vulkan.prototype-unsupported-uniform-buffer",
                           "Vulkan prototype cannot emit an empty "
                           "uniform-buffer access-chain index");
        return std::nullopt;
      }
      std::optional<PrototypeSPIRVValue> dynamicIndex =
          emitExpression(*accessIndex.dynamicIndex);
      if (!dynamicIndex.has_value()) {
        return std::nullopt;
      }
      accessChain << " " << dynamicIndex->id;
    }

    instructionLines_.push_back(accessChain.str());
    return pointer;
  }

  std::optional<PrototypeSPIRVValue> emitUniformBufferMemberLoad(
      const HIRExpression &memberAccess, bool allowArrayLeaf = false) {
    std::optional<std::string> pointer =
        emitUniformBufferMemberPointer(memberAccess, allowArrayLeaf);
    if (!pointer.has_value()) {
      return std::nullopt;
    }
    const std::string typeId = ensureType(memberAccess.type);
    if (typeId.empty()) {
      return std::nullopt;
    }
    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = OpLoad " + typeId + " " +
                                *pointer);
    return PrototypeSPIRVValue{memberAccess.type, resultId};
  }

  bool isLocalArrayElementAccess(const HIRExpression &indexAccess) const {
    return localArrayElementAccess(indexAccess).has_value();
  }

  std::optional<PrototypeLocalArrayElementAccess>
  localArrayElementAccess(const HIRExpression &indexAccess) const {
    std::optional<PrototypeIndexedIdentifierAccess> indexed =
        prototypeIndexedIdentifierAccess(indexAccess);
    if (!indexed.has_value()) {
      return std::nullopt;
    }
    const auto local = locals_.find(indexed->baseName);
    if (local == locals_.end() ||
        !local->second.type.arraySize.has_value()) {
      return std::nullopt;
    }
    return PrototypeLocalArrayElementAccess{
        indexed->baseName, local->second.type, std::move(indexed->indices)};
  }

  bool localArrayElementAccessUsesDynamicIndex(
      const PrototypeLocalArrayElementAccess &access) const {
    for (const HIRExpression *index : access.indices) {
      if (!prototypeStaticArrayIndexValue(*index, constants_).has_value()) {
        return true;
      }
    }
    return false;
  }

  std::optional<PrototypeSPIRVValue> emitLocalArrayCompositeExtract(
      const HIRType &type, const std::string &valueId,
      const std::vector<std::size_t> &staticIndices) {
    const std::string typeId = ensureType(type);
    if (typeId.empty()) {
      return std::nullopt;
    }
    const std::string resultId = nextTemp();
    std::ostringstream instruction;
    instruction << resultId << " = OpCompositeExtract " << typeId << " "
                << valueId;
    for (std::size_t staticIndex : staticIndices) {
      instruction << " " << staticIndex;
    }
    instructionLines_.push_back(instruction.str());
    return PrototypeSPIRVValue{type, resultId};
  }

  std::optional<PrototypeSPIRVValue> emitSelectValue(
      const HIRType &type, const std::string &conditionId,
      const PrototypeSPIRVValue &trueValue,
      const PrototypeSPIRVValue &falseValue) {
    const std::string typeId = ensureType(type);
    if (typeId.empty()) {
      return std::nullopt;
    }
    std::string selectedConditionId = conditionId;
    if (const std::optional<std::size_t> width = prototypeVectorWidth(type);
        width.has_value()) {
      const std::string conditionTypeId = ensureBoolVectorType(*width);
      selectedConditionId = nextTemp();
      std::ostringstream condition;
      condition << selectedConditionId << " = OpCompositeConstruct "
                << conditionTypeId;
      for (std::size_t index = 0; index < *width; ++index) {
        condition << " " << conditionId;
      }
      instructionLines_.push_back(condition.str());
    }
    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = OpSelect " + typeId + " " +
                                selectedConditionId + " " + trueValue.id +
                                " " + falseValue.id);
    return PrototypeSPIRVValue{type, resultId};
  }

  std::optional<PrototypeSPIRVValue>
  emitComputeBuiltinLoad(const HIRExpression &expression) {
    const PrototypeComputeBuiltinInfo *builtin =
        prototypeComputeBuiltinInfo(expression.value);
    if (builtin == nullptr) {
      return std::nullopt;
    }

    const HIRType builtinType = prototypeComputeBuiltinType();
    const std::string variableId = ensureComputeBuiltinVariable(*builtin);
    const std::string typeId = ensureType(builtinType);
    if (variableId.empty() || typeId.empty()) {
      return std::nullopt;
    }

    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = OpLoad " + typeId + " " +
                                variableId);
    return PrototypeSPIRVValue{builtinType, resultId};
  }

  std::optional<std::string> emitFunctionLocalArrayElementPointer(
      const HIRExpression &indexAccess,
      const PrototypeLocalArrayElementAccess &access,
      const PrototypeSPIRVLocal &local) {
    const std::string pointerTypeId =
        ensureFunctionElementPointerType(indexAccess.type);
    if (pointerTypeId.empty()) {
      return std::nullopt;
    }

    std::ostringstream accessChain;
    const std::string pointer = nextTemp();
    accessChain << pointer << " = OpAccessChain " << pointerTypeId << " "
                << local.variableId;
    for (const HIRExpression *index : access.indices) {
      const std::optional<std::size_t> staticIndex =
          prototypeStaticArrayIndexValue(*index, constants_);
      if (!staticIndex.has_value()) {
        diagnostics_.error(
            "vulkan.prototype-unsupported-function-parameter-array",
            "Vulkan prototype helper array writeback currently requires "
            "folded constant helper array indices");
        return std::nullopt;
      }
      accessChain << " "
                  << ensureNumericConstant(HIRType{"int", std::nullopt},
                                           std::to_string(*staticIndex));
    }
    instructionLines_.push_back(accessChain.str());
    return pointer;
  }

  bool emitWorkgroupControlBarrier() {
    const HIRType uintType{"uint", std::nullopt};
    // SPIR-V: Workgroup scope = 2, AcquireRelease | WorkgroupMemory = 0x108.
    constexpr std::string_view kWorkgroupScope = "2";
    constexpr std::string_view kWorkgroupAcquireReleaseMemorySemantics = "264";
    const std::string workgroupScope =
        ensureNumericConstant(uintType, kWorkgroupScope);
    const std::string workgroupMemorySemantics =
        ensureNumericConstant(uintType, kWorkgroupAcquireReleaseMemorySemantics);
    if (workgroupScope.empty() || workgroupMemorySemantics.empty()) {
      return false;
    }
    instructionLines_.push_back("OpControlBarrier " + workgroupScope + " " +
                                workgroupScope + " " +
                                workgroupMemorySemantics);
    return true;
  }

  std::optional<std::string> emitWorkgroupSharedElementPointer(
      const HIRExpression &indexAccess) {
    const std::optional<PrototypeStorageBufferIndexAccess> access =
        prototypeStorageBufferIndexAccess(indexAccess);
    if (!access.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-atomic-add",
                         "Vulkan prototype workgroup atomicAdd targets must "
                         "be direct indexed shared resources");
      return std::nullopt;
    }
    if (access->descriptorIndex != nullptr) {
      diagnostics_.error("vulkan.prototype-unsupported-atomic-add",
                         "Vulkan prototype workgroup atomicAdd targets do not "
                         "use descriptor indices");
      return std::nullopt;
    }

    const auto resource = workgroupShared_.find(access->resourceName);
    if (resource == workgroupShared_.end() ||
        !resource->second.type.arraySize.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-atomic-add",
                         "Vulkan prototype workgroup atomicAdd cannot resolve "
                         "indexed shared resource '" +
                             access->resourceName + "'");
      return std::nullopt;
    }
    const HIRType elementType = arrayElementType(resource->second.type);
    const std::string pointerTypeId = ensureWorkgroupPointerType(elementType);
    if (pointerTypeId.empty()) {
      return std::nullopt;
    }
    if (access->elementIndex == nullptr) {
      diagnostics_.error("vulkan.prototype-unsupported-atomic-add",
                         "Vulkan prototype workgroup atomicAdd requires an "
                         "element index");
      return std::nullopt;
    }
    std::optional<PrototypeSPIRVValue> elementIndex =
        emitExpression(*access->elementIndex);
    if (!elementIndex.has_value()) {
      return std::nullopt;
    }

    addEntryPointInterface(resource->second.variableId);
    const std::string pointer = nextTemp();
    instructionLines_.push_back(pointer + " = OpAccessChain " +
                                pointerTypeId + " " +
                                resource->second.variableId + " " +
                                elementIndex->id);
    return pointer;
  }

  std::optional<PrototypeSPIRVAtomicTarget>
  emitAtomicTargetPointer(const HIRExpression &target) {
    if (target.kind == HIRExpressionKind::Identifier) {
      const auto resource = workgroupShared_.find(target.value);
      if (resource != workgroupShared_.end() &&
          !resource->second.type.arraySize.has_value()) {
        const std::optional<HIRType> valueType =
            prototypeAtomicStorageValueType(resource->second.type);
        if (!valueType.has_value()) {
          diagnostics_.error("vulkan.prototype-unsupported-atomic-add",
                             "Vulkan prototype atomicAdd targets must be "
                             "atomic<int> or atomic<uint> storage");
          return std::nullopt;
        }
        addEntryPointInterface(resource->second.variableId);
        return PrototypeSPIRVAtomicTarget{
            *valueType, resource->second.variableId,
            PrototypeSPIRVAtomicStorageClass::Workgroup};
      }
    }

    if (isStructStorageBufferMemberAccess(target)) {
      const std::optional<HIRType> valueType =
          prototypeAtomicStoredValueType(target.type, true);
      if (!valueType.has_value()) {
        diagnostics_.error("vulkan.prototype-unsupported-atomic-add",
                           "Vulkan prototype storage-buffer member atomicAdd "
                           "targets must be int, uint, atomic<int>, or "
                           "atomic<uint>");
        return std::nullopt;
      }
      std::optional<std::string> pointer =
          emitStorageBufferMemberPointer(target);
      if (!pointer.has_value()) {
        return std::nullopt;
      }
      return PrototypeSPIRVAtomicTarget{
          *valueType, *pointer,
          PrototypeSPIRVAtomicStorageClass::StorageBuffer};
    }

    const std::optional<PrototypeStorageBufferIndexAccess> access =
        prototypeStorageBufferIndexAccess(target);
    if (!access.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-atomic-add",
                         "Vulkan prototype atomicAdd targets must be direct "
                         "storage-buffer or workgroup atomic elements");
      return std::nullopt;
    }

    if (const auto buffer = storageBuffers_.find(access->resourceName);
        buffer != storageBuffers_.end()) {
      const std::optional<HIRType> valueType =
          prototypeAtomicStorageValueType(buffer->second.elementType);
      if (!valueType.has_value()) {
        diagnostics_.error("vulkan.prototype-unsupported-atomic-add",
                           "Vulkan prototype atomicAdd storage-buffer targets "
                           "must be atomic<int> or atomic<uint>");
        return std::nullopt;
      }
      std::optional<std::string> pointer =
          emitStorageBufferElementPointer(target);
      if (!pointer.has_value()) {
        return std::nullopt;
      }
      return PrototypeSPIRVAtomicTarget{
          *valueType, *pointer,
          PrototypeSPIRVAtomicStorageClass::StorageBuffer};
    }

    if (const auto shared = workgroupShared_.find(access->resourceName);
        shared != workgroupShared_.end()) {
      const HIRType elementType = arrayElementType(shared->second.type);
      const std::optional<HIRType> valueType =
          prototypeAtomicStorageValueType(elementType);
      if (!valueType.has_value()) {
        diagnostics_.error("vulkan.prototype-unsupported-atomic-add",
                           "Vulkan prototype atomicAdd workgroup targets must "
                           "be atomic<int> or atomic<uint>");
        return std::nullopt;
      }
      std::optional<std::string> pointer =
          emitWorkgroupSharedElementPointer(target);
      if (!pointer.has_value()) {
        return std::nullopt;
      }
      return PrototypeSPIRVAtomicTarget{
          *valueType, *pointer, PrototypeSPIRVAtomicStorageClass::Workgroup};
    }

    diagnostics_.error("vulkan.prototype-unsupported-atomic-add",
                       "Vulkan prototype atomicAdd cannot resolve target "
                       "resource '" +
                           access->resourceName + "'");
    return std::nullopt;
  }

  std::string atomicIntegerOpcode(PrototypeAtomicIntegerOp op,
                                  const HIRType &valueType) const {
    switch (op) {
    case PrototypeAtomicIntegerOp::Add:
      return "OpAtomicIAdd";
    case PrototypeAtomicIntegerOp::Exchange:
      return "OpAtomicExchange";
    case PrototypeAtomicIntegerOp::And:
      return "OpAtomicAnd";
    case PrototypeAtomicIntegerOp::Or:
      return "OpAtomicOr";
    case PrototypeAtomicIntegerOp::Xor:
      return "OpAtomicXor";
    case PrototypeAtomicIntegerOp::Min:
      if (valueType.name == "int") {
        return "OpAtomicSMin";
      }
      if (valueType.name == "uint") {
        return "OpAtomicUMin";
      }
      break;
    case PrototypeAtomicIntegerOp::Max:
      if (valueType.name == "int") {
        return "OpAtomicSMax";
      }
      if (valueType.name == "uint") {
        return "OpAtomicUMax";
      }
      break;
    }
    return "";
  }

  std::optional<PrototypeSPIRVValue>
  emitAtomicIntegerValue(const HIRExpression &expression) {
    const std::optional<PrototypeAtomicIntegerOp> op =
        prototypeAtomicIntegerOpForCall(expression);
    if (!op.has_value()) {
      return std::nullopt;
    }
    if (expression.children.size() != 2) {
      diagnostics_.error("vulkan.prototype-unsupported-atomic-add",
                         "Vulkan prototype integer atomic expects target and "
                         "value arguments");
      return std::nullopt;
    }

    std::optional<PrototypeSPIRVAtomicTarget> target =
        emitAtomicTargetPointer(expression.children[0]);
    std::optional<PrototypeSPIRVValue> delta =
        emitExpression(expression.children[1]);
    if (!target.has_value() || !delta.has_value()) {
      return std::nullopt;
    }
    if (!samePrototypeType(delta->type, target->valueType)) {
      diagnostics_.error("vulkan.prototype-unsupported-type",
                         "Vulkan prototype integer atomic value type '" +
                             formatType(delta->type) +
                             "' must match atomic value type '" +
                             formatType(target->valueType) + "'");
      return std::nullopt;
    }

    const HIRType uintType{"uint", std::nullopt};
    // Scope: Device=1 for storage buffers, Workgroup=2 for workgroup memory.
    // Semantics: Relaxed=None=0.
    const std::string scope = ensureNumericConstant(
        uintType,
        target->storageClass == PrototypeSPIRVAtomicStorageClass::StorageBuffer
            ? "1"
            : "2");
    const std::string semantics = ensureNumericConstant(uintType, "0");
    const std::string typeId = ensureType(target->valueType);
    const std::string opcode = atomicIntegerOpcode(*op, target->valueType);
    if (scope.empty() || semantics.empty() || typeId.empty() ||
        opcode.empty()) {
      return std::nullopt;
    }
    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = " + opcode + " " + typeId +
                                " " + target->pointerId + " " + scope + " " +
                                semantics + " " + delta->id);
    return PrototypeSPIRVValue{target->valueType, resultId};
  }

  bool emitAtomicIntegerStatement(const HIRExpression &expression) {
    // SPIR-V integer atomics return the old value. Statement form deliberately
    // leaves that result id unused.
    return emitAtomicIntegerValue(expression).has_value();
  }

  std::optional<PrototypeSPIRVValue> emitDynamicLocalArrayElementLoad(
      const HIRExpression &indexAccess,
      const PrototypeLocalArrayElementAccess &access,
      const std::string &valueId,
      std::size_t indexOffset,
      std::vector<std::size_t> &staticIndices) {
    if (indexOffset == access.indices.size()) {
      return emitLocalArrayCompositeExtract(indexAccess.type, valueId,
                                            staticIndices);
    }

    const HIRExpression &indexExpression = *access.indices[indexOffset];
    if (const std::optional<std::size_t> staticIndex =
            prototypeStaticArrayIndexValue(indexExpression, constants_);
        staticIndex.has_value()) {
      staticIndices.push_back(*staticIndex);
      std::optional<PrototypeSPIRVValue> value =
          emitDynamicLocalArrayElementLoad(indexAccess, access, valueId,
                                           indexOffset + 1, staticIndices);
      staticIndices.pop_back();
      return value;
    }

    std::optional<PrototypeSPIRVValue> dynamicIndex =
        emitExpression(indexExpression);
    if (!dynamicIndex.has_value()) {
      return std::nullopt;
    }
    if (dynamicIndex->type.name != "int" ||
        dynamicIndex->type.arraySize.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-function-parameter-array",
                         "Vulkan prototype helper array indices must be "
                         "scalar int values");
      return std::nullopt;
    }

    const std::vector<std::string_view> dimensions =
        prototypeArrayDimensions(*access.localType.arraySize);
    const std::optional<std::size_t> elementCount =
        prototypeArrayDimensionElementCount(dimensions[indexOffset], constants_);
    if (!elementCount.has_value() || *elementCount == 0) {
      diagnostics_.error("vulkan.prototype-unsupported-function-parameter-array",
                         "Vulkan prototype dynamic helper array reads require "
                         "fixed-size folded array dimensions");
      return std::nullopt;
    }

    std::vector<PrototypeSPIRVValue> cases;
    cases.reserve(*elementCount);
    for (std::size_t elementIndex = 0; elementIndex < *elementCount;
         ++elementIndex) {
      staticIndices.push_back(elementIndex);
      std::optional<PrototypeSPIRVValue> value =
          emitDynamicLocalArrayElementLoad(indexAccess, access, valueId,
                                           indexOffset + 1, staticIndices);
      staticIndices.pop_back();
      if (!value.has_value()) {
        return std::nullopt;
      }
      cases.push_back(*value);
    }

    PrototypeSPIRVValue selected = cases.front();
    for (std::size_t elementIndex = 1; elementIndex < cases.size();
         ++elementIndex) {
      const std::string boolTypeId = ensureType(HIRType{"bool", std::nullopt});
      const std::string constantId =
          ensureNumericConstant(HIRType{"int", std::nullopt},
                                std::to_string(elementIndex));
      const std::string conditionId = nextTemp();
      instructionLines_.push_back(conditionId + " = OpIEqual " + boolTypeId +
                                  " " + dynamicIndex->id + " " + constantId);
      std::optional<PrototypeSPIRVValue> nextSelected =
          emitSelectValue(indexAccess.type, conditionId, cases[elementIndex],
                          selected);
      if (!nextSelected.has_value()) {
        return std::nullopt;
      }
      selected = *nextSelected;
    }
    return selected;
  }

  std::optional<PrototypeSPIRVValue> emitLocalArrayElementLoad(
      const HIRExpression &indexAccess) {
    const std::optional<PrototypeLocalArrayElementAccess> access =
        localArrayElementAccess(indexAccess);
    if (!access.has_value()) {
      return std::nullopt;
    }
    const auto local = locals_.find(access->localName);
    if (local == locals_.end() ||
        (local->second.valueId.empty() && local->second.variableId.empty())) {
      diagnostics_.error("vulkan.prototype-unsupported-function-parameter-array",
                         "Vulkan prototype helper array indexing requires an "
                         "array value");
      return std::nullopt;
    }
    if (local->second.valueId.empty()) {
      std::optional<std::string> pointer =
          emitFunctionLocalArrayElementPointer(indexAccess, *access,
                                               local->second);
      if (!pointer.has_value()) {
        return std::nullopt;
      }
      const std::string typeId = ensureType(indexAccess.type);
      if (typeId.empty()) {
        return std::nullopt;
      }
      const std::string resultId = nextTemp();
      instructionLines_.push_back(resultId + " = OpLoad " + typeId + " " +
                                  *pointer);
      return PrototypeSPIRVValue{indexAccess.type, resultId};
    }
    std::string arrayValueId = local->second.valueId;
    std::vector<std::size_t> staticIndices;
    staticIndices.reserve(access->indices.size());
    if (localArrayElementAccessUsesDynamicIndex(*access)) {
      return emitDynamicLocalArrayElementLoad(indexAccess, *access,
                                              arrayValueId, 0,
                                              staticIndices);
    }
    for (const HIRExpression *index : access->indices) {
      const std::optional<std::size_t> staticIndex =
          prototypeStaticArrayIndexValue(*index, constants_);
      if (!staticIndex.has_value()) {
        diagnostics_.error(
            "vulkan.prototype-unsupported-function-parameter-array",
            "Vulkan prototype helper array indexing in this native slice "
            "requires folded constant indices");
        return std::nullopt;
      }
      staticIndices.push_back(*staticIndex);
    }
    return emitLocalArrayCompositeExtract(indexAccess.type,
                                          arrayValueId, staticIndices);
  }

  bool emitLocalArrayElementStore(const HIRStatement &statement) {
    const HIRExpression &indexAccess = statement.target;
    const std::optional<PrototypeLocalArrayElementAccess> access =
        localArrayElementAccess(indexAccess);
    if (!access.has_value()) {
      return false;
    }
    auto local = locals_.find(access->localName);
    if (local == locals_.end() ||
        (local->second.valueId.empty() && local->second.variableId.empty())) {
      diagnostics_.error("vulkan.prototype-unsupported-function-parameter-array",
                         "Vulkan prototype local array element writes require "
                         "an array value");
      return false;
    }
    if (local->second.readOnly) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-function-parameter-array",
          "Vulkan prototype helper function array parameters use the shared "
          "read-only value-copy ABI; writes through parameter array '" +
              access->localName + "' are not supported");
      return false;
    }
    if (local->second.valueId.empty()) {
      std::optional<PrototypeSPIRVValue> value =
          emitStatementAssignmentValue(statement.value);
      if (!value.has_value()) {
        return false;
      }
      if (!samePrototypeType(indexAccess.type, value->type) &&
          !isPrototypeDeferredUserCallType(statement.value, value->type)) {
        diagnostics_.error(
            "vulkan.prototype-unsupported-type",
            "Vulkan prototype binary emission does not insert local array "
            "element assignment casts yet");
        return false;
      }
      std::optional<std::string> pointer =
          emitFunctionLocalArrayElementPointer(indexAccess, *access,
                                               local->second);
      if (!pointer.has_value()) {
        return false;
      }
      instructionLines_.push_back("OpStore " + *pointer + " " + value->id);
      return true;
    }
    std::vector<std::size_t> staticIndices;
    staticIndices.reserve(access->indices.size());
    for (const HIRExpression *index : access->indices) {
      const std::optional<std::size_t> staticIndex =
          prototypeStaticArrayIndexValue(*index, constants_);
      if (!staticIndex.has_value()) {
        diagnostics_.error(
            "vulkan.prototype-unsupported-function-parameter-array",
            "Vulkan prototype helper array indexing in this native slice "
            "requires folded constant indices");
        return false;
      }
      staticIndices.push_back(*staticIndex);
    }

    std::optional<PrototypeSPIRVValue> value =
        emitStatementAssignmentValue(statement.value);
    if (!value.has_value()) {
      return false;
    }
    if (!samePrototypeType(indexAccess.type, value->type) &&
        !isPrototypeDeferredUserCallType(statement.value, value->type)) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-type",
          "Vulkan prototype binary emission does not insert local array "
          "element assignment casts yet");
      return false;
    }

    const std::string arrayTypeId = ensureType(local->second.type);
    if (arrayTypeId.empty()) {
      return false;
    }
    const std::string resultId = nextTemp();
    std::ostringstream instruction;
    instruction << resultId << " = OpCompositeInsert " << arrayTypeId << " "
                << value->id << " " << local->second.valueId;
    for (std::size_t staticIndex : staticIndices) {
      instruction << " " << staticIndex;
    }
    instructionLines_.push_back(instruction.str());
    local->second.valueId = resultId;
    return true;
  }

  std::string uniformConstantValueTypeId(
      HIRResourceKind kind, const HIRType &type,
      const std::optional<std::string> &storageImageFormat = std::nullopt) {
    if (kind == HIRResourceKind::Texture) {
      return ensureImageType(arrayElementType(type));
    }
    if (kind == HIRResourceKind::StorageImage) {
      return ensureStorageImageType(arrayElementType(type), storageImageFormat);
    }
    if (kind == HIRResourceKind::Sampler) {
      return ensureSamplerType();
    }
    return "";
  }

  std::string resolveDescriptorResourceName(std::string_view name) const {
    if (!currentFunctionName_.empty()) {
      if (const auto functionAliases =
              resourceArrayParameterAliases_.find(currentFunctionName_);
          functionAliases != resourceArrayParameterAliases_.end()) {
        if (const auto alias = functionAliases->second.find(std::string(name));
            alias != functionAliases->second.end()) {
          return alias->second;
        }
      }
    }
    return std::string(name);
  }

  std::optional<PrototypeSPIRVValue> emitUniformConstantDescriptorLoad(
      const HIRExpression &expression, HIRResourceKind expectedKind) {
    if (expression.kind == HIRExpressionKind::Identifier) {
      const std::string resourceName =
          resolveDescriptorResourceName(expression.value);
      const auto descriptor = uniformConstantDescriptors_.find(resourceName);
      if (descriptor == uniformConstantDescriptors_.end() ||
          descriptor->second.kind != expectedKind) {
        diagnostics_.error("vulkan.prototype-unsupported-resource",
                           "Vulkan prototype texture sampling cannot resolve "
                           "descriptor resource '" +
                               expression.value + "'");
        return std::nullopt;
      }
      if (descriptor->second.type.arraySize.has_value()) {
        diagnostics_.error("vulkan.prototype-unsupported-resource",
                           "Vulkan prototype texture sampling requires indexed "
                           "access for descriptor array resource '" +
                               expression.value + "'");
        return std::nullopt;
      }
      const std::string typeId =
          uniformConstantValueTypeId(expectedKind, descriptor->second.type,
                                     descriptor->second.storageImageFormat);
      if (typeId.empty()) {
        return std::nullopt;
      }
      const std::string resultId = nextTemp();
      instructionLines_.push_back(resultId + " = OpLoad " + typeId + " " +
                                  descriptor->second.variableId);
      return PrototypeSPIRVValue{expression.type, resultId};
    }

    if (expression.kind != HIRExpressionKind::IndexAccess ||
        expression.children.size() < 2 ||
        expression.children[0].kind != HIRExpressionKind::Identifier) {
      diagnostics_.error("vulkan.prototype-unsupported-resource",
                         "Vulkan prototype texture sampling supports only "
                         "direct descriptor resources or indexed descriptor "
                         "arrays");
      return std::nullopt;
    }

    const std::string resourceName =
        resolveDescriptorResourceName(expression.children[0].value);
    const auto descriptor = uniformConstantDescriptors_.find(resourceName);
    if (descriptor == uniformConstantDescriptors_.end() ||
        descriptor->second.kind != expectedKind) {
      diagnostics_.error("vulkan.prototype-unsupported-resource",
                         "Vulkan prototype texture sampling cannot resolve "
                         "descriptor array resource '" +
                             resourceName + "'");
      return std::nullopt;
    }
    if (!descriptor->second.type.arraySize.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-resource",
                         "Vulkan prototype texture sampling cannot index "
                         "non-array descriptor resource '" +
                             resourceName + "'");
      return std::nullopt;
    }

    std::optional<PrototypeSPIRVValue> index = emitDescriptorIndexExpression(
        expression.children[1], PrototypeNonUniformDescriptorUse::SampledImage);
    if (!index.has_value()) {
      return std::nullopt;
    }

    HIRType element = arrayElementType(descriptor->second.type);
    const std::string pointerTypeId =
        ensureUniformConstantElementPointerType(
            expectedKind, element, descriptor->second.storageImageFormat);
    const std::string valueTypeId =
        uniformConstantValueTypeId(expectedKind, element,
                                   descriptor->second.storageImageFormat);
    if (pointerTypeId.empty() || valueTypeId.empty()) {
      return std::nullopt;
    }

    const std::string pointer = nextTemp();
    instructionLines_.push_back(pointer + " = OpAccessChain " + pointerTypeId +
                                " " + descriptor->second.variableId + " " +
                                index->id);
    if (index->nonUniformDescriptor) {
      decorateNonUniform(pointer);
    }
    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = OpLoad " + valueTypeId + " " +
                                pointer);
    if (index->nonUniformDescriptor) {
      decorateNonUniform(resultId);
    }
    return PrototypeSPIRVValue{expression.type, resultId,
                               index->nonUniformDescriptor};
  }

  std::optional<PrototypeSPIRVStorageImageDescriptorPointer>
  emitStorageImageDescriptorPointer(const HIRExpression &expression) {
    if (expression.kind == HIRExpressionKind::Identifier) {
      const auto descriptor = uniformConstantDescriptors_.find(expression.value);
      if (descriptor == uniformConstantDescriptors_.end() ||
          descriptor->second.kind != HIRResourceKind::StorageImage) {
        diagnostics_.error("vulkan.prototype-unsupported-resource",
                           "Vulkan prototype storage image access cannot "
                           "resolve storage image resource '" +
                               expression.value + "'");
        return std::nullopt;
      }
      if (descriptor->second.type.arraySize.has_value()) {
        diagnostics_.error("vulkan.prototype-unsupported-resource",
                           "Vulkan prototype storage image access requires "
                           "indexed access for descriptor array resource '" +
                               expression.value + "'");
        return std::nullopt;
      }

      return PrototypeSPIRVStorageImageDescriptorPointer{
          descriptor->second.type, descriptor->second.variableId,
          descriptor->second.storageImageFormat};
    }

    if (expression.kind != HIRExpressionKind::IndexAccess ||
        expression.children.size() < 2 ||
        expression.children[0].kind != HIRExpressionKind::Identifier) {
      diagnostics_.error("vulkan.prototype-unsupported-resource",
                         "Vulkan prototype storage image access supports only "
                         "direct storage image resources or indexed descriptor "
                         "arrays");
      return std::nullopt;
    }

    const std::string &resourceName = expression.children[0].value;
    const auto descriptor = uniformConstantDescriptors_.find(resourceName);
    if (descriptor == uniformConstantDescriptors_.end() ||
        descriptor->second.kind != HIRResourceKind::StorageImage) {
      diagnostics_.error("vulkan.prototype-unsupported-resource",
                         "Vulkan prototype storage image access cannot resolve "
                         "storage image descriptor array resource '" +
                             resourceName + "'");
      return std::nullopt;
    }
    if (!descriptor->second.type.arraySize.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-resource",
                         "Vulkan prototype storage image access cannot index "
                         "non-array descriptor resource '" +
                             resourceName + "'");
      return std::nullopt;
    }
    std::optional<PrototypeSPIRVValue> index = emitDescriptorIndexExpression(
        expression.children[1], PrototypeNonUniformDescriptorUse::StorageImage);
    if (!index.has_value()) {
      return std::nullopt;
    }

    HIRType element = arrayElementType(descriptor->second.type);
    const std::string pointerTypeId = ensureUniformConstantElementPointerType(
        HIRResourceKind::StorageImage, element,
        descriptor->second.storageImageFormat);
    const std::string valueTypeId =
        uniformConstantValueTypeId(HIRResourceKind::StorageImage, element,
                                   descriptor->second.storageImageFormat);
    if (pointerTypeId.empty() || valueTypeId.empty()) {
      return std::nullopt;
    }

    const std::string pointer = nextTemp();
    instructionLines_.push_back(pointer + " = OpAccessChain " + pointerTypeId +
                                " " + descriptor->second.variableId + " " +
                                index->id);
    if (index->nonUniformDescriptor) {
      decorateNonUniform(pointer);
    }
    return PrototypeSPIRVStorageImageDescriptorPointer{
        element, pointer, descriptor->second.storageImageFormat,
        index->nonUniformDescriptor};
  }

  std::optional<PrototypeSPIRVValue> emitStorageImageDescriptorLoad(
      const HIRExpression &expression) {
    std::optional<PrototypeSPIRVStorageImageDescriptorPointer> pointer =
        emitStorageImageDescriptorPointer(expression);
    if (!pointer.has_value()) {
      return std::nullopt;
    }
    const std::string valueTypeId = uniformConstantValueTypeId(
        HIRResourceKind::StorageImage, pointer->type,
        pointer->storageImageFormat);
    if (valueTypeId.empty()) {
      return std::nullopt;
    }
    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = OpLoad " + valueTypeId + " " +
                                pointer->pointerId);
    if (pointer->nonUniformDescriptor) {
      decorateNonUniform(resultId);
    }
    return PrototypeSPIRVValue{expression.type, resultId,
                               pointer->nonUniformDescriptor};
  }

  std::optional<PrototypeSPIRVValue>
  emitStorageImageLoad(const HIRExpression &expression) {
    if (expression.children.size() != 2) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype imageLoad lowering requires image "
                         "and coordinate operands");
      return std::nullopt;
    }

    std::optional<PrototypeSPIRVValue> image =
        emitStorageImageDescriptorLoad(expression.children[0]);
    std::optional<PrototypeSPIRVValue> coordinates =
        emitExpression(expression.children[1]);
    if (!image.has_value() || !coordinates.has_value()) {
      return std::nullopt;
    }

    const std::string resultTypeId = ensureType(expression.type);
    if (resultTypeId.empty()) {
      return std::nullopt;
    }
    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = OpImageRead " + resultTypeId +
                                " " + image->id + " " + coordinates->id);
    return PrototypeSPIRVValue{expression.type, resultId};
  }

  bool emitStorageImageStore(const HIRExpression &expression) {
    if (expression.children.size() != 3) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype imageStore lowering requires image, "
                         "coordinate, and value operands");
      return false;
    }

    std::optional<PrototypeSPIRVValue> image =
        emitStorageImageDescriptorLoad(expression.children[0]);
    std::optional<PrototypeSPIRVValue> coordinates =
        emitExpression(expression.children[1]);
    std::optional<PrototypeSPIRVValue> value =
        emitExpression(expression.children[2]);
    if (!image.has_value() || !coordinates.has_value() || !value.has_value()) {
      return false;
    }

    instructionLines_.push_back("OpImageWrite " + image->id + " " +
                                coordinates->id + " " + value->id);
    return true;
  }

  std::optional<PrototypeSPIRVValue>
  emitStorageImageAtomicValue(const HIRExpression &expression) {
    const std::optional<PrototypeAtomicIntegerOp> op =
        prototypeStorageImageAtomicOpForCall(expression);
    if (!op.has_value()) {
      return std::nullopt;
    }
    if (expression.children.size() != 3) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype " + expression.value +
                             " lowering requires image, coordinate, and value "
                             "operands");
      return std::nullopt;
    }

    const HIRExpression &imageExpression = expression.children[0];
    std::optional<PrototypeSPIRVStorageImageDescriptorPointer> image =
        emitStorageImageDescriptorPointer(imageExpression);
    std::optional<PrototypeSPIRVValue> coordinates =
        emitExpression(expression.children[1]);
    std::optional<PrototypeSPIRVValue> value =
        emitExpression(expression.children[2]);
    if (!image.has_value() || !coordinates.has_value() || !value.has_value()) {
      return std::nullopt;
    }

    const HIRType valueType = storageImageAtomicPayloadType(imageExpression.type);
    if (!samePrototypeType(value->type, valueType) ||
        !samePrototypeType(expression.type, valueType)) {
      diagnostics_.error("vulkan.prototype-unsupported-type",
                         "Vulkan prototype " + expression.value +
                             " value and result types must match the image "
                             "atomic scalar payload type");
      return std::nullopt;
    }

    const HIRType intType{"int", std::nullopt};
    const HIRType uintType{"uint", std::nullopt};
    const std::string pointerTypeId = ensureImagePointerType(valueType);
    const std::string valueTypeId = ensureType(valueType);
    const std::string sample = ensureNumericConstant(intType, "0");
    const std::string scope = ensureNumericConstant(uintType, "1");
    const std::string semantics = ensureNumericConstant(uintType, "0");
    const std::string opcode = atomicIntegerOpcode(*op, valueType);
    if (pointerTypeId.empty() || valueTypeId.empty() || sample.empty() ||
        scope.empty() || semantics.empty() || opcode.empty()) {
      return std::nullopt;
    }

    const std::string texelPointer = nextTemp();
    instructionLines_.push_back(texelPointer + " = OpImageTexelPointer " +
                                pointerTypeId + " " + image->pointerId + " " +
                                coordinates->id + " " + sample);
    if (image->nonUniformDescriptor) {
      decorateNonUniform(texelPointer);
    }

    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = " + opcode + " " +
                                valueTypeId + " " + texelPointer + " " +
                                scope + " " + semantics + " " + value->id);
    return PrototypeSPIRVValue{valueType, resultId};
  }

  bool emitStorageImageAtomicStatement(const HIRExpression &expression) {
    return emitStorageImageAtomicValue(expression).has_value();
  }

  std::string emitSampledImageValue(const PrototypeSPIRVValue &texture,
                                    const PrototypeSPIRVValue &sampler,
                                    const std::string &sampledImageTypeId) {
    const std::string sampledImage = nextTemp();
    instructionLines_.push_back(sampledImage + " = OpSampledImage " +
                                sampledImageTypeId + " " + texture.id + " " +
                                sampler.id);
    if (texture.nonUniformDescriptor || sampler.nonUniformDescriptor) {
      requireNonUniformDescriptorIndex(
          PrototypeNonUniformDescriptorUse::SampledImage);
      decorateNonUniform(sampledImage);
    }
    return sampledImage;
  }

  std::optional<PrototypeSPIRVValue> emitTextureSample(
      const HIRExpression &expression) {
    const bool explicitLod = isPrototypeExplicitLodTextureSample(expression);
    const bool implicitSamplerSample =
        isPrototypeImplicitSamplerTextureSample(expression);
    if (!explicitLod && !implicitSamplerSample) {
      diagnostics_.error("vulkan.prototype-implicit-lod-compute",
                         "Vulkan compute texture sampling requires explicit "
                         "lod; use textureLod(texture, sampler, coordinates, "
                         "lod)");
      return std::nullopt;
    }
    const std::size_t expectedOperands = explicitLod ? 4 : 3;
    if (expression.children.size() != expectedOperands) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         explicitLod
                             ? "Vulkan prototype textureLod lowering "
                               "currently requires texture, sampler, "
                               "coordinates, and lod operands"
                             : "Vulkan prototype .sample lowering currently "
                               "requires texture, sampler, and coordinates "
                               "operands");
      return std::nullopt;
    }

    std::optional<PrototypeSPIRVValue> texture =
        emitUniformConstantDescriptorLoad(expression.children[0],
                                          HIRResourceKind::Texture);
    std::optional<PrototypeSPIRVValue> sampler =
        emitUniformConstantDescriptorLoad(expression.children[1],
                                          HIRResourceKind::Sampler);
    std::optional<PrototypeSPIRVValue> coordinates =
        emitExpression(expression.children[2]);
    std::optional<PrototypeSPIRVValue> explicitLodValue =
        explicitLod ? emitExpression(expression.children[3]) : std::nullopt;
    if (!texture.has_value() || !sampler.has_value() ||
        !coordinates.has_value() ||
        (explicitLod && !explicitLodValue.has_value())) {
      return std::nullopt;
    }

    const std::string sampledImageTypeId =
        ensureSampledImageType(texture->type);
    const std::string resultTypeId = ensureType(expression.type);
    if (sampledImageTypeId.empty() || resultTypeId.empty()) {
      return std::nullopt;
    }

    const std::string sampledImage =
        emitSampledImageValue(*texture, *sampler, sampledImageTypeId);
    const std::string lod =
        explicitLod ? explicitLodValue->id
                    : ensureNumericConstant(HIRType{"float", std::nullopt}, "0.0");
    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = OpImageSampleExplicitLod " +
                                resultTypeId + " " + sampledImage + " " +
                                coordinates->id + " Lod " + lod);
    return PrototypeSPIRVValue{expression.type, resultId};
  }

  std::optional<PrototypeSPIRVValue> emitTextureCompare(
      const HIRExpression &expression) {
    const bool explicitLod = isPrototypeExplicitLodTextureCompare(expression);
    const std::size_t expectedOperands = explicitLod ? 5 : 4;
    if (expression.children.size() != expectedOperands) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         explicitLod
                             ? "Vulkan prototype textureCompareLod lowering "
                               "requires texture, sampler, coordinates, "
                               "depth, and lod operands"
                             : "Vulkan prototype textureCompare lowering "
                               "requires texture, sampler, coordinates, and "
                               "depth operands");
      return std::nullopt;
    }

    std::optional<PrototypeSPIRVValue> texture =
        emitUniformConstantDescriptorLoad(expression.children[0],
                                          HIRResourceKind::Texture);
    std::optional<PrototypeSPIRVValue> sampler =
        emitUniformConstantDescriptorLoad(expression.children[1],
                                          HIRResourceKind::Sampler);
    std::optional<PrototypeSPIRVValue> coordinates =
        emitExpression(expression.children[2]);
    std::optional<PrototypeSPIRVValue> depth =
        emitExpression(expression.children[3]);
    std::optional<PrototypeSPIRVValue> explicitLodValue =
        explicitLod ? emitExpression(expression.children[4]) : std::nullopt;
    if (!texture.has_value() || !sampler.has_value() ||
        !coordinates.has_value() || !depth.has_value() ||
        (explicitLod && !explicitLodValue.has_value())) {
      return std::nullopt;
    }

    const std::string sampledImageTypeId =
        ensureSampledImageType(texture->type);
    const std::string resultTypeId = ensureType(expression.type);
    if (sampledImageTypeId.empty() || resultTypeId.empty()) {
      return std::nullopt;
    }

    const std::string sampledImage =
        emitSampledImageValue(*texture, *sampler, sampledImageTypeId);
    const std::string lod =
        explicitLod ? explicitLodValue->id
                    : ensureNumericConstant(HIRType{"float", std::nullopt}, "0.0");
    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = OpImageSampleDrefExplicitLod " +
                                resultTypeId + " " + sampledImage + " " +
                                coordinates->id + " " + depth->id +
                                " Lod " + lod);
    return PrototypeSPIRVValue{expression.type, resultId};
  }

  std::optional<PrototypeSPIRVValue> emitTextureCompareManual(
      const HIRExpression &expression) {
    const std::optional<TextureCompareManualOperands> operands =
        textureCompareManualOperands(expression);
    if (!operands.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype textureCompareLodManual lowering "
                         "requires texture, sampler, coordinates, depth, lod, "
                         "and compare-op operands");
      return std::nullopt;
    }

    const std::optional<TextureCompareOperator> compareOperator =
        textureCompareOperatorFromExpression(*operands->compareOp);
    if (!compareOperator.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype textureCompareLodManual compare-op "
                         "operand must be a static compare symbol");
      return std::nullopt;
    }

    const HIRType floatType{"float", std::nullopt};
    if (*compareOperator == TextureCompareOperator::Never) {
      return PrototypeSPIRVValue{expression.type,
                                ensureNumericConstant(floatType, "0.0")};
    }
    if (operands->kernelTapCount == 0 &&
        *compareOperator == TextureCompareOperator::Always) {
      return PrototypeSPIRVValue{expression.type,
                                ensureNumericConstant(floatType, "1.0")};
    }

    std::optional<PrototypeSPIRVValue> texture =
        emitUniformConstantDescriptorLoad(*operands->texture,
                                          HIRResourceKind::Texture);
    std::optional<PrototypeSPIRVValue> sampler =
        emitUniformConstantDescriptorLoad(*operands->sampler,
                                          HIRResourceKind::Sampler);
    std::optional<PrototypeSPIRVValue> coordinates =
        emitExpression(*operands->coordinate);
    std::optional<PrototypeSPIRVValue> depth =
        emitExpression(*operands->depth);
    std::optional<PrototypeSPIRVValue> lod = emitExpression(*operands->lod);
    if (!texture.has_value() || !sampler.has_value() ||
        !coordinates.has_value() || !depth.has_value() || !lod.has_value()) {
      return std::nullopt;
    }

    const std::string sampledImageTypeId =
        ensureSampledImageType(texture->type);
    const std::string floatTypeId = ensureType(floatType);
    const std::string rawSampleTypeId = ensureType(HIRType{"vec4", std::nullopt});
    const std::string boolTypeId = ensureType(HIRType{"bool", std::nullopt});
    if (sampledImageTypeId.empty() || floatTypeId.empty() ||
        rawSampleTypeId.empty() ||
        boolTypeId.empty()) {
      return std::nullopt;
    }

    const std::string sampledImage =
        emitSampledImageValue(*texture, *sampler, sampledImageTypeId);

    const std::optional<std::string_view> compareSymbol =
        textureCompareOperatorBinarySymbol(*compareOperator);
    const std::string opcode =
        *compareOperator == TextureCompareOperator::Always
            ? ""
            : (compareSymbol.has_value()
                   ? binaryOpcode(*compareSymbol, floatType,
                                  HIRType{"bool", std::nullopt})
                   : "");
    if (*compareOperator != TextureCompareOperator::Always && opcode.empty()) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype textureCompareLodManual cannot "
                         "lower compare-op '" +
                             textureCompareOperatorName(*compareOperator) +
                             "'");
      return std::nullopt;
    }

    const std::string one = ensureNumericConstant(floatType, "1.0");
    const std::string zero = ensureNumericConstant(floatType, "0.0");
    const auto emitTap =
        [&](std::string imageOperands) -> std::optional<std::string> {
      if (*compareOperator == TextureCompareOperator::Always) {
        return one;
      }
      const std::string rawSample = nextTemp();
      instructionLines_.push_back(rawSample +
                                  " = OpImageSampleExplicitLod " +
                                  rawSampleTypeId + " " + sampledImage + " " +
                                  coordinates->id + imageOperands);
      const std::string sampledDepth = nextTemp();
      instructionLines_.push_back(sampledDepth + " = OpCompositeExtract " +
                                  floatTypeId + " " + rawSample + " 0");
      const std::string condition = nextTemp();
      instructionLines_.push_back(condition + " = " + opcode + " " +
                                  boolTypeId + " " + depth->id + " " +
                                  sampledDepth);
      const std::string resultId = nextTemp();
      instructionLines_.push_back(resultId + " = OpSelect " + floatTypeId +
                                  " " + condition + " " + one + " " + zero);
      return resultId;
    };

    if (operands->gather2x2) {
      const std::array<PrototypeTextureOffset, 4> offsets = {
          PrototypeTextureOffset{0, 0}, PrototypeTextureOffset{1, 0},
          PrototypeTextureOffset{0, 1}, PrototypeTextureOffset{1, 1}};
      std::string sum;
      for (const PrototypeTextureOffset &offset : offsets) {
        const std::optional<std::string> tap =
            emitTap(" Lod|ConstOffset " + lod->id + " " +
                    ensureIvec2Constant(offset));
        if (!tap.has_value()) {
          return std::nullopt;
        }
        if (sum.empty()) {
          sum = *tap;
          continue;
        }
        const std::string nextSum = nextTemp();
        instructionLines_.push_back(nextSum + " = OpFAdd " + floatTypeId +
                                    " " + sum + " " + *tap);
        sum = nextSum;
      }
      const std::string quarter = ensureNumericConstant(floatType, "0.25");
      const std::string resultId = nextTemp();
      instructionLines_.push_back(resultId + " = OpFMul " + floatTypeId +
                                  " " + sum + " " + quarter);
      return PrototypeSPIRVValue{expression.type, resultId};
    }

    if (operands->kernelTapCount != 0) {
      std::string sum;
      for (std::size_t index = 0; index < operands->kernelTapCount;
           ++index) {
        const std::optional<PrototypeTextureOffset> offset =
            staticIvec2TextureOffset(*operands->kernelOffsets[index]);
        if (!offset.has_value()) {
          diagnostics_.error("vulkan.prototype-unsupported-expression",
                             std::string("Vulkan prototype ") +
                                 textureCompareManualOperationName(*operands) +
                                 " " +
                                 "requires static ivec2 integer literal "
                                 "offsets");
          return std::nullopt;
        }
        const std::optional<PrototypeSPIRVValue> weight =
            emitExpression(*operands->kernelWeights[index]);
        if (!weight.has_value()) {
          return std::nullopt;
        }
        const std::optional<std::string> tap =
            emitTap(" Lod|ConstOffset " + lod->id + " " +
                    ensureIvec2Constant(*offset));
        if (!tap.has_value()) {
          return std::nullopt;
        }
        const std::string weighted = nextTemp();
        instructionLines_.push_back(weighted + " = OpFMul " + floatTypeId +
                                    " " + *tap + " " + weight->id);
        if (sum.empty()) {
          sum = weighted;
          continue;
        }
        const std::string nextSum = nextTemp();
        instructionLines_.push_back(nextSum + " = OpFAdd " + floatTypeId +
                                    " " + sum + " " + weighted);
        sum = nextSum;
      }
      return PrototypeSPIRVValue{expression.type, sum};
    }

    std::string imageOperands = " Lod " + lod->id;
    if (operands->offset != nullptr) {
      const std::optional<PrototypeTextureOffset> offset =
          staticIvec2TextureOffset(*operands->offset);
      if (!offset.has_value()) {
        diagnostics_.error("vulkan.prototype-unsupported-expression",
                           "Vulkan prototype textureCompareLodManualOffset "
                           "requires a static ivec2 integer literal offset");
        return std::nullopt;
      }
      imageOperands = " Lod|ConstOffset " + lod->id + " " +
                      ensureIvec2Constant(*offset);
    }
    const std::optional<std::string> resultId = emitTap(imageOperands);
    if (!resultId.has_value()) {
      return std::nullopt;
    }
    return PrototypeSPIRVValue{expression.type, *resultId};
  }

  std::optional<PrototypeSPIRVValue> emitIntrinsicCall(
      const HIRExpression &expression) {
    const std::optional<PrototypeIntrinsicLowering> lowering =
        prototypeIntrinsicLoweringForCall(expression);
    if (!lowering.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype intrinsic lowering currently "
                         "supports only the scalar/vector HIR math intrinsic "
                         "subset");
      return std::nullopt;
    }

    std::vector<PrototypeSPIRVValue> operands;
    operands.reserve(expression.children.size());
    for (const HIRExpression &child : expression.children) {
      std::optional<PrototypeSPIRVValue> value = emitExpression(child);
      if (!value.has_value()) {
        return std::nullopt;
      }
      if (lowering->operandsUseResultType &&
          !samePrototypeType(value->type, expression.type)) {
        value = emitVectorSplat(expression.type, *value);
        if (!value.has_value()) {
          return std::nullopt;
        }
      }
      operands.push_back(*value);
    }

    if (lowering->kind == PrototypeIntrinsicLoweringKind::Identity) {
      if (operands.size() != 1) {
        return std::nullopt;
      }
      return PrototypeSPIRVValue{expression.type, operands.front().id};
    }

    const std::string typeId = ensureType(expression.type);
    if (typeId.empty()) {
      return std::nullopt;
    }
    const std::string resultId = nextTemp();
    std::ostringstream instruction;
    if (lowering->kind == PrototypeIntrinsicLoweringKind::CoreInstruction) {
      instruction << resultId << " = " << lowering->opcode << " " << typeId;
    } else {
      instruction << resultId << " = OpExtInst " << typeId << " "
                  << ensureGLSLStd450Import() << " " << lowering->opcode;
    }
    for (const PrototypeSPIRVValue &operand : operands) {
      instruction << " " << operand.id;
    }
    instructionLines_.push_back(instruction.str());
    return PrototypeSPIRVValue{expression.type, resultId};
  }

  std::optional<std::string> emitArrayWriteBackPointerArgument(
      const HIRExpression &argument, const HIRParameter &parameter,
      const PrototypeSPIRVFunctionInfo &callee,
      std::vector<PrototypeSPIRVArrayWriteBackCopy> &copyBacks) {
    if (!isStructStorageBufferMemberAccess(argument, true)) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-function-parameter-array",
          "Vulkan prototype helper array parameter writeback requires a "
          "direct storage-buffer field array argument");
      return std::nullopt;
    }

    std::optional<std::string> storagePointer =
        emitStorageBufferMemberPointer(argument, true);
    if (!storagePointer.has_value()) {
      return std::nullopt;
    }
    const std::string pointerTypeId = ensureFunctionPointerType(parameter.type);
    if (pointerTypeId.empty()) {
      return std::nullopt;
    }

    const std::string temporaryPointer =
        makeVariableId("param_array_writeback_" +
                       (callee.function != nullptr ? callee.function->name
                                                   : std::string{"helper"}) +
                       "_" + parameter.name);
    variableLines_.push_back(temporaryPointer + " = OpVariable " +
                             pointerTypeId + " Function");

    const std::optional<std::size_t> elementCount =
        prototypeArrayFirstDimensionElementCount(parameter.type, constants_);
    if (!elementCount.has_value()) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-function-parameter-array",
          "Vulkan prototype helper array parameter writeback requires "
          "fixed-size folded array dimensions");
      return std::nullopt;
    }
    const HIRType elementType =
        prototypeArrayElementTypeOneDimension(parameter.type);
    const std::string storageElementPointerType =
        ensureStorageBufferElementPointerType(elementType);
    const std::string functionElementPointerType =
        ensureFunctionElementPointerType(elementType);
    const std::string elementTypeId = ensureType(elementType);
    if (storageElementPointerType.empty() ||
        functionElementPointerType.empty() || elementTypeId.empty()) {
      return std::nullopt;
    }

    for (std::size_t index = 0; index < *elementCount; ++index) {
      const std::string indexId =
          ensureNumericConstant(HIRType{"int", std::nullopt},
                                std::to_string(index));
      const std::string storageElementPointer = nextTemp();
      instructionLines_.push_back(storageElementPointer + " = OpAccessChain " +
                                  storageElementPointerType + " " +
                                  *storagePointer + " " + indexId);
      const std::string functionElementPointer = nextTemp();
      instructionLines_.push_back(functionElementPointer + " = OpAccessChain " +
                                  functionElementPointerType + " " +
                                  temporaryPointer + " " + indexId);
      const std::string loaded = nextTemp();
      instructionLines_.push_back(loaded + " = OpLoad " + elementTypeId + " " +
                                  storageElementPointer);
      instructionLines_.push_back("OpStore " + functionElementPointer + " " +
                                  loaded);
    }
    copyBacks.push_back(PrototypeSPIRVArrayWriteBackCopy{
        parameter.type, temporaryPointer, *storagePointer});
    return temporaryPointer;
  }

  bool emitArrayWriteBackCopies(
      const std::vector<PrototypeSPIRVArrayWriteBackCopy> &copyBacks) {
    for (const PrototypeSPIRVArrayWriteBackCopy &copyBack : copyBacks) {
      const std::optional<std::size_t> elementCount =
          prototypeArrayFirstDimensionElementCount(copyBack.type, constants_);
      if (!elementCount.has_value()) {
        diagnostics_.error(
            "vulkan.prototype-unsupported-function-parameter-array",
            "Vulkan prototype helper array parameter writeback requires "
            "fixed-size folded array dimensions");
        return false;
      }
      const HIRType elementType =
          prototypeArrayElementTypeOneDimension(copyBack.type);
      const std::string storageElementPointerType =
          ensureStorageBufferElementPointerType(elementType);
      const std::string functionElementPointerType =
          ensureFunctionElementPointerType(elementType);
      const std::string elementTypeId = ensureType(elementType);
      if (storageElementPointerType.empty() ||
          functionElementPointerType.empty() || elementTypeId.empty()) {
        return false;
      }

      for (std::size_t index = 0; index < *elementCount; ++index) {
        const std::string indexId =
            ensureNumericConstant(HIRType{"int", std::nullopt},
                                  std::to_string(index));
        const std::string functionElementPointer = nextTemp();
        instructionLines_.push_back(functionElementPointer +
                                    " = OpAccessChain " +
                                    functionElementPointerType + " " +
                                    copyBack.temporaryPointerId + " " +
                                    indexId);
        const std::string storageElementPointer = nextTemp();
        instructionLines_.push_back(storageElementPointer +
                                    " = OpAccessChain " +
                                    storageElementPointerType + " " +
                                    copyBack.storagePointerId + " " +
                                    indexId);
        const std::string updated = nextTemp();
        instructionLines_.push_back(updated + " = OpLoad " + elementTypeId +
                                    " " + functionElementPointer);
        instructionLines_.push_back("OpStore " + storageElementPointer + " " +
                                    updated);
      }
    }
    return true;
  }

  std::optional<PrototypeSPIRVValue> emitUserFunctionCall(
      const HIRExpression &expression) {
    const auto function = functions_.find(expression.value);
    if (function == functions_.end() || function->second.entry) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype function calls can target only "
                         "same-stage or top-level helper functions");
      return std::nullopt;
    }
    const PrototypeSPIRVFunctionInfo &info = function->second;
    if (info.function == nullptr ||
        expression.children.size() != info.function->parameters.size()) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype helper call argument count does "
                         "not match helper signature");
      return std::nullopt;
    }

    std::vector<std::string> argumentIds;
    argumentIds.reserve(info.parameterTypes.size());
    std::vector<PrototypeSPIRVArrayWriteBackCopy> copyBacks;
    std::size_t abiParameterIndex = 0;
    for (std::size_t index = 0; index < expression.children.size(); ++index) {
      const HIRParameter &parameter = info.function->parameters[index];
      if (index < info.erasedResourceArrayParameters.size() &&
          info.erasedResourceArrayParameters[index]) {
        const HIRExpression &argumentExpression = expression.children[index];
        if (argumentExpression.kind != HIRExpressionKind::Identifier) {
          diagnostics_.error(
              "vulkan.prototype-unsupported-function-parameter-resource-array",
              "Vulkan prototype helper resource array parameters require "
              "direct descriptor-array arguments");
          return std::nullopt;
        }
        const std::string expectedAlias =
            resourceArrayParameterAliases_[info.function->name][parameter.name];
        if (argumentExpression.value != expectedAlias) {
          diagnostics_.error(
              "vulkan.prototype-unsupported-function-parameter-resource-array",
              "Vulkan prototype helper resource array parameter '" +
                  parameter.name +
                  "' is specialized to descriptor array '" + expectedAlias +
                  "'");
          return std::nullopt;
        }
        continue;
      }
      const bool pointerParameter =
          abiParameterIndex < info.pointerParameters.size() &&
          info.pointerParameters[abiParameterIndex];
      if (pointerParameter) {
        if (abiParameterIndex >= info.parameterTypes.size() ||
            !samePrototypeType(expression.children[index].type,
                               info.parameterTypes[abiParameterIndex])) {
          diagnostics_.error("vulkan.prototype-unsupported-type",
                             "Vulkan prototype helper calls do not insert "
                             "argument casts");
          return std::nullopt;
        }
        std::optional<std::string> pointerArgument =
            emitArrayWriteBackPointerArgument(expression.children[index],
                                              parameter, info, copyBacks);
        if (!pointerArgument.has_value()) {
          return std::nullopt;
        }
        argumentIds.push_back(*pointerArgument);
        ++abiParameterIndex;
        continue;
      }
      std::optional<PrototypeSPIRVValue> argument =
          emitExpression(expression.children[index]);
      if (!argument.has_value()) {
        return std::nullopt;
      }
      if (abiParameterIndex >= info.parameterTypes.size() ||
          !samePrototypeType(argument->type,
                             info.parameterTypes[abiParameterIndex])) {
        diagnostics_.error("vulkan.prototype-unsupported-type",
                           "Vulkan prototype helper calls do not insert "
                           "argument casts");
        return std::nullopt;
      }
      argumentIds.push_back(argument->id);
      ++abiParameterIndex;
    }

    const std::string returnTypeId = ensureType(info.returnType);
    if (returnTypeId.empty()) {
      return std::nullopt;
    }
    if (!samePrototypeType(expression.type, info.returnType) &&
        !expression.type.name.empty() &&
        !(info.returnType.name == "void" && expression.type.name.empty())) {
      diagnostics_.error("vulkan.prototype-unsupported-type",
                         "Vulkan prototype helper call result type does not "
                         "match helper return type");
      return std::nullopt;
    }

    const std::string resultId = nextTemp();
    std::ostringstream instruction;
    instruction << resultId << " = OpFunctionCall " << returnTypeId << " "
                << info.id;
    for (const std::string &argumentId : argumentIds) {
      instruction << " " << argumentId;
    }
    instructionLines_.push_back(instruction.str());
    if (!emitArrayWriteBackCopies(copyBacks)) {
      return std::nullopt;
    }
    return PrototypeSPIRVValue{info.returnType, resultId};
  }

  std::optional<PrototypeSPIRVValue> emitSelectExpression(
      const HIRExpression &expression) {
    if (expression.children.size() != 3) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype select expressions require a "
                         "condition plus true and false values");
      return std::nullopt;
    }

    std::optional<PrototypeSPIRVValue> condition =
        emitExpression(expression.children[0]);
    std::optional<PrototypeSPIRVValue> trueValue =
        emitExpression(expression.children[1]);
    std::optional<PrototypeSPIRVValue> falseValue =
        emitExpression(expression.children[2]);
    if (!condition.has_value() || !trueValue.has_value() ||
        !falseValue.has_value()) {
      return std::nullopt;
    }

    if (condition->type.name != "bool" ||
        condition->type.arraySize.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype select conditions must be scalar "
                         "bool values");
      return std::nullopt;
    }
    if (!samePrototypeType(expression.type, trueValue->type) ||
        !samePrototypeType(expression.type, falseValue->type)) {
      diagnostics_.error("vulkan.prototype-unsupported-type",
                         "Vulkan prototype select arms must match the result "
                         "type");
      return std::nullopt;
    }

    const std::string typeId = ensureType(expression.type);
    if (typeId.empty()) {
      return std::nullopt;
    }
    std::string conditionId = condition->id;
    if (const std::optional<std::size_t> width =
            prototypeVectorWidth(expression.type);
        width.has_value()) {
      const std::string conditionTypeId = ensureBoolVectorType(*width);
      conditionId = nextTemp();
      std::ostringstream instruction;
      instruction << conditionId << " = OpCompositeConstruct "
                  << conditionTypeId;
      for (std::size_t index = 0; index < *width; ++index) {
        instruction << " " << condition->id;
      }
      instructionLines_.push_back(instruction.str());
    }
    const std::string resultId = nextTemp();
    instructionLines_.push_back(resultId + " = OpSelect " + typeId + " " +
                                conditionId + " " + trueValue->id + " " +
                                falseValue->id);
    return PrototypeSPIRVValue{expression.type, resultId};
  }

  std::optional<PrototypeSPIRVValue> emitExpression(
      const HIRExpression &expression) {
    switch (expression.kind) {
    case HIRExpressionKind::Literal:
      if (!expression.type.arraySize.has_value() &&
          expression.type.name == "bool" &&
          (expression.value == "true" || expression.value == "false")) {
        return PrototypeSPIRVValue{
            expression.type, ensureBoolConstant(expression.value == "true")};
      }
      return PrototypeSPIRVValue{
          expression.type, ensureNumericConstant(expression.type, expression.value)};
    case HIRExpressionKind::Identifier:
      if (expression.value == "true" || expression.value == "false") {
        return PrototypeSPIRVValue{HIRType{"bool", std::nullopt},
                                  ensureBoolConstant(expression.value == "true")};
      }
      if (auto local = locals_.find(expression.value); local != locals_.end()) {
        if (!local->second.valueId.empty()) {
          return PrototypeSPIRVValue{local->second.type,
                                     local->second.valueId};
        }
        const std::string typeId = ensureType(local->second.type);
        const std::string resultId = nextTemp();
        instructionLines_.push_back(resultId + " = OpLoad " + typeId + " " +
                                    local->second.variableId);
        return PrototypeSPIRVValue{local->second.type, resultId};
      }
      if (isPrototypeComputeBuiltinIdentifier(expression.value)) {
        return emitComputeBuiltinLoad(expression);
      }
      if (auto constant = constants_.find(expression.value);
          constant != constants_.end()) {
        if (!isPrototypeConstantSupported(constant->second)) {
          diagnostics_.error("vulkan.prototype-unsupported-expression",
                             "Vulkan prototype binary emission supports only "
                             "folded scalar constants");
          return std::nullopt;
        }
        if (constant->second.type.name == "bool") {
          return PrototypeSPIRVValue{
              constant->second.type,
              ensureBoolConstant(*constant->second.foldedValue == "true")};
        }
        const std::string literal = prototypeNumericConstantLiteral(
            constant->second.type, *constant->second.foldedValue);
        return PrototypeSPIRVValue{
            constant->second.type,
            ensureNumericConstant(constant->second.type, literal)};
      }
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype binary emission cannot resolve local "
                         "value '" +
                             expression.value + "'");
      return std::nullopt;
    case HIRExpressionKind::Group:
      if (expression.children.empty()) {
        diagnostics_.error("vulkan.prototype-unsupported-expression",
                           "Vulkan prototype binary emission does not support "
                           "empty grouped expressions");
        return std::nullopt;
      }
      return emitExpression(expression.children.front());
    case HIRExpressionKind::Unary: {
      if (expression.children.empty()) {
        return std::nullopt;
      }
      std::optional<PrototypeSPIRVValue> operand =
          emitExpression(expression.children.front());
      if (!operand.has_value()) {
        return std::nullopt;
      }
      if (expression.value == "+") {
        return operand;
      }

      const std::string resultId = nextTemp();
      const std::string typeId = ensureType(operand->type);
      const std::string opcode =
          operand->type.name == "float" ? "OpFNegate" : "OpSNegate";
      instructionLines_.push_back(resultId + " = " + opcode + " " + typeId +
                                  " " + operand->id);
      return PrototypeSPIRVValue{operand->type, resultId};
    }
    case HIRExpressionKind::Binary: {
      if (expression.children.size() < 2) {
        return std::nullopt;
      }
      std::optional<PrototypeSPIRVValue> left =
          emitExpression(expression.children[0]);
      std::optional<PrototypeSPIRVValue> right =
          emitExpression(expression.children[1]);
      if (!left.has_value() || !right.has_value()) {
        return std::nullopt;
      }

      PrototypeSPIRVValue leftValue = *left;
      PrototypeSPIRVValue rightValue = *right;
      const std::optional<PrototypeMatrixMultiplyLowering> matrixMultiply =
          expression.value == "*"
              ? prototypeMatrixMultiplyLowering(leftValue.type, rightValue.type,
                                                expression.type)
              : std::nullopt;
      if (matrixMultiply.has_value()) {
        const std::string typeId = ensureType(expression.type);
        if (typeId.empty()) {
          return std::nullopt;
        }
        const PrototypeSPIRVValue &firstValue =
            matrixMultiply->swapOperands ? rightValue : leftValue;
        const PrototypeSPIRVValue &secondValue =
            matrixMultiply->swapOperands ? leftValue : rightValue;
        const std::string resultId = nextTemp();
        instructionLines_.push_back(resultId + " = " +
                                    std::string(matrixMultiply->opcode) + " " +
                                    typeId + " " + firstValue.id + " " +
                                    secondValue.id);
        return PrototypeSPIRVValue{expression.type, resultId};
      }

      if (isPrototypeFloatVectorScalarArithmetic(leftValue.type, rightValue.type,
                                                 expression.type)) {
        if (expression.value == "*") {
          const PrototypeSPIRVValue &vectorValue =
              isPrototypeFloatVectorType(leftValue.type) ? leftValue
                                                         : rightValue;
          const PrototypeSPIRVValue &scalarValue =
              isPrototypeFloatVectorType(leftValue.type) ? rightValue
                                                         : leftValue;
          const std::string typeId = ensureType(expression.type);
          if (typeId.empty()) {
            return std::nullopt;
          }
          const std::string resultId = nextTemp();
          instructionLines_.push_back(resultId + " = OpVectorTimesScalar " +
                                      typeId + " " + vectorValue.id + " " +
                                      scalarValue.id);
          return PrototypeSPIRVValue{expression.type, resultId};
        }

        if (isPrototypeFloatVectorType(leftValue.type)) {
          std::optional<PrototypeSPIRVValue> splat =
              emitVectorSplat(expression.type, rightValue);
          if (!splat.has_value()) {
            return std::nullopt;
          }
          rightValue = *splat;
        } else {
          std::optional<PrototypeSPIRVValue> splat =
              emitVectorSplat(expression.type, leftValue);
          if (!splat.has_value()) {
            return std::nullopt;
          }
          leftValue = *splat;
        }
      }

      const std::string opcode =
          binaryOpcode(expression.value, leftValue.type, expression.type);
      if (opcode.empty()) {
        diagnostics_.error("vulkan.prototype-unsupported-expression",
                           "Vulkan prototype binary emission cannot lower "
                           "binary operator '" +
                               expression.value + "'");
        return std::nullopt;
      }

      const std::string typeId = ensureType(expression.type);
      const std::string resultId = nextTemp();
      instructionLines_.push_back(resultId + " = " + opcode + " " + typeId +
                                  " " + leftValue.id + " " + rightValue.id);
      return PrototypeSPIRVValue{expression.type, resultId};
    }
    case HIRExpressionKind::IndexAccess: {
      if (isLocalArrayElementAccess(expression)) {
        return emitLocalArrayElementLoad(expression);
      }
      if (isStructStorageBufferMemberAccess(
              expression, expression.type.arraySize.has_value())) {
        return emitStorageBufferMemberLoad(
            expression, expression.type.arraySize.has_value());
      }
      std::optional<std::string> pointer =
          emitStorageBufferElementPointer(expression);
      if (!pointer.has_value()) {
        return std::nullopt;
      }
      const HIRType elementType = expression.type;
      const std::string typeId = ensureType(elementType);
      const std::string resultId = nextTemp();
      instructionLines_.push_back(resultId + " = OpLoad " + typeId + " " +
                                  *pointer);
      return PrototypeSPIRVValue{elementType, resultId};
    }
    case HIRExpressionKind::MemberAccess:
      if (isStructUniformBufferMemberAccess(
              expression, expression.type.arraySize.has_value())) {
        return emitUniformBufferMemberLoad(
            expression, expression.type.arraySize.has_value());
      }
      if (isStructStorageBufferMemberAccess(
              expression, expression.type.arraySize.has_value())) {
        return emitStorageBufferMemberLoad(
            expression, expression.type.arraySize.has_value());
      }
      return emitVectorMemberAccess(expression);
    case HIRExpressionKind::Constructor:
      if (isPrototypeNumericScalarType(expression.type)) {
        return emitScalarConstructor(expression);
      }
      if (isPrototypeMatrixType(expression.type)) {
        return emitMatrixConstructor(expression);
      }
      return emitVectorConstructor(expression);
    case HIRExpressionKind::NonUniform:
      diagnostics_.error("vulkan.prototype-unsupported-nonuniform-index",
                         "Vulkan prototype lowers nonuniform only when it "
                         "annotates a descriptor array index operand");
      return std::nullopt;
    case HIRExpressionKind::Call:
      if (isPrototypeImageLoadCall(expression)) {
        return emitStorageImageLoad(expression);
      }
      if (isPrototypeImageStoreCall(expression)) {
        diagnostics_.error("vulkan.prototype-unsupported-expression",
                           "Vulkan prototype imageStore can be lowered only "
                           "as an expression statement");
        return std::nullopt;
      }
      if (isPrototypeStorageImageAtomicCall(expression)) {
        diagnostics_.error("vulkan.prototype-unsupported-expression",
                           "Vulkan prototype storage image atomics can be "
                           "lowered only as expression statements or as exact "
                           "declaration/assignment RHS captures");
        return std::nullopt;
      }
      if (isPrototypeAtomicIntegerCall(expression)) {
        diagnostics_.error("vulkan.prototype-unsupported-atomic-add",
                           "Vulkan prototype integer atomics can be lowered "
                           "only as expression statements or as exact "
                           "declaration/assignment RHS captures");
        return std::nullopt;
      }
      if (isPrototypeWorkgroupBarrierCall(expression)) {
        diagnostics_.error("vulkan.prototype-unsupported-expression",
                           "Vulkan prototype workgroup barriers can be "
                           "lowered only as expression statements");
        return std::nullopt;
      }
      if (prototypeIntrinsicLoweringForCall(expression).has_value()) {
        return emitIntrinsicCall(expression);
      }
      return emitUserFunctionCall(expression);
    case HIRExpressionKind::Select:
      return emitSelectExpression(expression);
    case HIRExpressionKind::Empty:
      diagnostics_.error("vulkan.prototype-unsupported-expression",
                         "Vulkan prototype binary emission does not lower '" +
                             expressionKindName(expression.kind) +
                             "' expressions yet");
      return std::nullopt;
    case HIRExpressionKind::TextureSample:
      return emitTextureSample(expression);
    case HIRExpressionKind::TextureCompare:
      return emitTextureCompare(expression);
    case HIRExpressionKind::TextureCompareLodManual:
      return emitTextureCompareManual(expression);
    }
    return std::nullopt;
  }

  static std::string binaryOpcode(std::string_view op, const HIRType &operandType,
                                  const HIRType &resultType) {
    if ((operandType.name == "float" ||
         isPrototypeVectorType(operandType)) &&
        samePrototypeType(operandType, resultType)) {
      if (op == "+") {
        return "OpFAdd";
      }
      if (op == "-") {
        return "OpFSub";
      }
      if (op == "*") {
        return "OpFMul";
      }
      if (op == "/") {
        return "OpFDiv";
      }
      return "";
    }

    if (operandType.name == "int" && resultType.name == "int") {
      if (op == "+") {
        return "OpIAdd";
      }
      if (op == "-") {
        return "OpISub";
      }
      if (op == "*") {
        return "OpIMul";
      }
      if (op == "/") {
        return "OpSDiv";
      }
    }

    if (operandType.name == "float" && resultType.name == "bool") {
      if (op == "<") {
        return "OpFOrdLessThan";
      }
      if (op == "<=") {
        return "OpFOrdLessThanEqual";
      }
      if (op == ">") {
        return "OpFOrdGreaterThan";
      }
      if (op == ">=") {
        return "OpFOrdGreaterThanEqual";
      }
      if (op == "==") {
        return "OpFOrdEqual";
      }
      if (op == "!=") {
        return "OpFUnordNotEqual";
      }
    }

    if (operandType.name == "int" && resultType.name == "bool") {
      if (op == "<") {
        return "OpSLessThan";
      }
      if (op == "<=") {
        return "OpSLessThanEqual";
      }
      if (op == ">") {
        return "OpSGreaterThan";
      }
      if (op == ">=") {
        return "OpSGreaterThanEqual";
      }
      if (op == "==") {
        return "OpIEqual";
      }
      if (op == "!=") {
        return "OpINotEqual";
      }
    }
    return "";
  }

  std::optional<PrototypeSPIRVValue>
  emitStatementAssignmentValue(const HIRExpression &expression) {
    if (isPrototypeAtomicIntegerCall(expression)) {
      return emitAtomicIntegerValue(expression);
    }
    if (isPrototypeStorageImageAtomicCall(expression)) {
      return emitStorageImageAtomicValue(expression);
    }
    return emitExpression(expression);
  }

  PrototypeEmitResult emitReturnStatement(const HIRStatement &statement) {
    const bool returnsVoid = currentReturnType_.name == "void" &&
                             !currentReturnType_.arraySize.has_value();
    if (returnsVoid) {
      if (statement.value.kind != HIRExpressionKind::Empty) {
        diagnostics_.error("vulkan.prototype-unsupported-body",
                           "Vulkan prototype void functions cannot return a "
                           "value");
        return {};
      }
      instructionLines_.push_back("OpReturn");
      return PrototypeEmitResult{true, true};
    }

    if (statement.value.kind == HIRExpressionKind::Empty) {
      diagnostics_.error("vulkan.prototype-unsupported-body",
                         "Vulkan prototype non-void functions must return a "
                         "value");
      return {};
    }
    std::optional<PrototypeSPIRVValue> value =
        emitExpression(statement.value);
    if (!value.has_value()) {
      return {};
    }
    if (!samePrototypeType(currentReturnType_, value->type)) {
      diagnostics_.error("vulkan.prototype-unsupported-type",
                         "Vulkan prototype return value type does not match "
                         "the function return type");
      return {};
    }
    instructionLines_.push_back("OpReturnValue " + value->id);
    return PrototypeEmitResult{true, true};
  }

  PrototypeEmitResult emitBreakStatement() {
    if (loopLabels_.empty()) {
      diagnostics_.error("vulkan.prototype-unsupported-statement",
                         "Vulkan prototype break statements are supported only "
                         "inside for or while loop bodies");
      return {};
    }
    instructionLines_.push_back("OpBranch " + loopLabels_.back().mergeLabel);
    return PrototypeEmitResult{true, true};
  }

  PrototypeEmitResult emitContinueStatement() {
    if (loopLabels_.empty()) {
      diagnostics_.error("vulkan.prototype-unsupported-statement",
                         "Vulkan prototype continue statements are supported "
                         "only inside for or while loop bodies");
      return {};
    }
    instructionLines_.push_back("OpBranch " + loopLabels_.back().continueLabel);
    return PrototypeEmitResult{true, true};
  }

  PrototypeEmitResult emitStatement(const HIRStatement &statement) {
    switch (statement.kind) {
    case HIRStatementKind::Declaration:
      return PrototypeEmitResult{emitDeclaration(statement), false};
    case HIRStatementKind::Assignment:
      return PrototypeEmitResult{emitAssignment(statement), false};
    case HIRStatementKind::Block:
      return emitBlockStatement(statement);
    case HIRStatementKind::If:
      return emitIfStatement(statement);
    case HIRStatementKind::For:
      return emitForStatement(statement);
    case HIRStatementKind::Return:
      return emitReturnStatement(statement);
    case HIRStatementKind::Break:
      return emitBreakStatement();
    case HIRStatementKind::Continue:
      return emitContinueStatement();
    case HIRStatementKind::Expression:
      if (isPrototypeImageStoreCall(statement.value)) {
        return PrototypeEmitResult{emitStorageImageStore(statement.value),
                                   false};
      }
      if (isPrototypeStorageImageAtomicCall(statement.value)) {
        return PrototypeEmitResult{
            emitStorageImageAtomicStatement(statement.value), false};
      }
      if (isPrototypeAtomicIntegerCall(statement.value)) {
        return PrototypeEmitResult{emitAtomicIntegerStatement(statement.value),
                                   false};
      }
      if (isPrototypeWorkgroupBarrierCall(statement.value)) {
        return PrototypeEmitResult{emitWorkgroupControlBarrier(), false};
      }
      if (statement.value.kind == HIRExpressionKind::Call &&
          !prototypeIntrinsicLoweringForCall(statement.value).has_value()) {
        std::optional<PrototypeSPIRVValue> value =
            emitExpression(statement.value);
        return PrototypeEmitResult{value.has_value(), false};
      }
      [[fallthrough]];
    case HIRStatementKind::Discard:
    case HIRStatementKind::Raw:
      diagnostics_.error("vulkan.prototype-unsupported-statement",
                         "Vulkan prototype binary emission does not lower '" +
                             statementKindName(statement.kind) +
                             "' statements yet");
      return {};
    }
    return {};
  }

  PrototypeEmitResult emitBranchStatement(const HIRStatement &statement,
                                          bool allowReturn = true) {
    if (statement.kind == HIRStatementKind::Declaration) {
      return PrototypeEmitResult{emitDeclaration(statement), false};
    }
    if (statement.kind == HIRStatementKind::Assignment) {
      return PrototypeEmitResult{emitAssignment(statement), false};
    }
    if (statement.kind == HIRStatementKind::Block) {
      return emitBlockStatement(statement, allowReturn);
    }
    if (statement.kind == HIRStatementKind::If) {
      return emitIfStatement(statement, allowReturn);
    }
    if (statement.kind == HIRStatementKind::For) {
      return emitForStatement(statement);
    }
    if (statement.kind == HIRStatementKind::Return) {
      if (!allowReturn) {
        diagnostics_.error("vulkan.prototype-unsupported-loop",
                           "Vulkan prototype for loop bodies do not support "
                           "returns yet");
        return {};
      }
      return emitReturnStatement(statement);
    }
    if (statement.kind == HIRStatementKind::Break) {
      return emitBreakStatement();
    }
    if (statement.kind == HIRStatementKind::Continue) {
      return emitContinueStatement();
    }
    if (statement.kind == HIRStatementKind::Expression &&
        isPrototypeImageStoreCall(statement.value)) {
      return PrototypeEmitResult{emitStorageImageStore(statement.value), false};
    }
    if (statement.kind == HIRStatementKind::Expression &&
        isPrototypeStorageImageAtomicCall(statement.value)) {
      return PrototypeEmitResult{
          emitStorageImageAtomicStatement(statement.value), false};
    }
    if (statement.kind == HIRStatementKind::Expression &&
        isPrototypeAtomicIntegerCall(statement.value)) {
      return PrototypeEmitResult{emitAtomicIntegerStatement(statement.value),
                                 false};
    }
    if (statement.kind == HIRStatementKind::Expression &&
        isPrototypeWorkgroupBarrierCall(statement.value)) {
      return PrototypeEmitResult{emitWorkgroupControlBarrier(), false};
    }
    if (statement.kind == HIRStatementKind::Expression &&
        statement.value.kind == HIRExpressionKind::Call &&
        !prototypeIntrinsicLoweringForCall(statement.value).has_value()) {
      std::optional<PrototypeSPIRVValue> value =
          emitExpression(statement.value);
      return PrototypeEmitResult{value.has_value(), false};
    }

    diagnostics_.error("vulkan.prototype-unsupported-statement",
                       "Vulkan prototype binary emission currently supports "
                       "only declarations, assignments, nested if/for "
                       "statements, or void returns inside if branches");
    return {};
  }

  PrototypeEmitResult emitBlockStatement(const HIRStatement &statement,
                                         bool allowReturn = true) {
    return emitBranchBody(statement.body, allowReturn);
  }

  PrototypeEmitResult emitBranchBody(const std::vector<HIRStatement> &body,
                                     bool allowReturn = true) {
    std::unordered_map<std::string, PrototypeSPIRVLocal> outerLocals = locals_;
    bool terminated = false;
    for (const HIRStatement &child : body) {
      if (terminated) {
        diagnostics_.error("vulkan.prototype-unsupported-body",
                           "Vulkan prototype binary emission requires a "
                           "terminating branch statement to be final");
        locals_ = std::move(outerLocals);
        return {};
      }
      const PrototypeEmitResult result = emitBranchStatement(child, allowReturn);
      if (!result.success) {
        locals_ = std::move(outerLocals);
        return {};
      }
      terminated = result.terminated;
    }
    locals_ = std::move(outerLocals);
    return PrototypeEmitResult{true, terminated};
  }

  PrototypeEmitResult emitIfStatement(const HIRStatement &statement,
                                      bool allowReturn = true) {
    std::optional<PrototypeSPIRVValue> condition =
        emitExpression(statement.value);
    if (!condition.has_value()) {
      return {};
    }

    const std::string thenLabel = nextLabel("if_then");
    const bool hasElse = !statement.elseBody.empty();
    const std::string elseLabel =
        hasElse ? nextLabel("if_else") : std::string{};
    const std::string mergeLabel = nextLabel("if_merge");

    instructionLines_.push_back("OpSelectionMerge " + mergeLabel + " None");
    instructionLines_.push_back("OpBranchConditional " + condition->id + " " +
                                thenLabel + " " +
                                (hasElse ? elseLabel : mergeLabel));

    instructionLines_.push_back(thenLabel + " = OpLabel");
    const PrototypeEmitResult thenBlock =
        emitBranchBody(statement.body, allowReturn);
    if (!thenBlock.success) {
      return {};
    }
    if (!thenBlock.terminated) {
      instructionLines_.push_back("OpBranch " + mergeLabel);
    }

    PrototypeEmitResult elseBlock{true, false};
    if (hasElse) {
      instructionLines_.push_back(elseLabel + " = OpLabel");
      elseBlock = emitBranchBody(statement.elseBody, allowReturn);
      if (!elseBlock.success) {
        return {};
      }
      if (!elseBlock.terminated) {
        instructionLines_.push_back("OpBranch " + mergeLabel);
      }
    }

    instructionLines_.push_back(mergeLabel + " = OpLabel");
    const bool allPathsTerminate =
        hasElse && thenBlock.terminated && elseBlock.terminated;
    if (allPathsTerminate) {
      instructionLines_.push_back("OpUnreachable");
    }
    return PrototypeEmitResult{true, allPathsTerminate};
  }

  std::optional<PrototypeLoopUpdate> parseLoopUpdate(
      const std::vector<Token> &tokens) {
    PrototypeLoopUpdate update;
    if (tokens.size() == 2 && tokens[0].kind == TokenKind::Identifier &&
        tokens[1].kind == TokenKind::Operator &&
        (tokens[1].text == "++" || tokens[1].text == "--")) {
      update.variableName = tokens[0].text;
      update.increment = tokens[1].text == "++";
      return update;
    }

    if (tokens.size() == 2 && tokens[0].kind == TokenKind::Operator &&
        (tokens[0].text == "++" || tokens[0].text == "--") &&
        tokens[1].kind == TokenKind::Identifier) {
      update.variableName = tokens[1].text;
      update.increment = tokens[0].text == "++";
      return update;
    }

    if (tokens.size() == 4 && tokens[0].kind == TokenKind::Identifier &&
        tokens[1].kind == TokenKind::Operator &&
        (tokens[1].text == "+" || tokens[1].text == "-") &&
        tokens[2].kind == TokenKind::Equal &&
        tokens[3].kind == TokenKind::Number &&
        tokens[3].text.find('.') == std::string::npos) {
      update.variableName = tokens[0].text;
      update.increment = tokens[1].text == "+";
      update.amount = tokens[3].text;
      return update;
    }

    diagnostics_.error("vulkan.prototype-unsupported-loop",
                       "Vulkan prototype for loops support only ++/-- or "
                       "+=/-= integer-literal counter updates");
    return std::nullopt;
  }

  bool emitLoopUpdate(const std::vector<Token> &tokens) {
    std::optional<PrototypeLoopUpdate> update = parseLoopUpdate(tokens);
    if (!update.has_value()) {
      return false;
    }

    const auto local = locals_.find(update->variableName);
    if (local == locals_.end()) {
      diagnostics_.error("vulkan.prototype-unsupported-loop",
                         "Vulkan prototype for loop update cannot resolve "
                         "local counter '" +
                             update->variableName + "'");
      return false;
    }
    if (local->second.variableId.empty()) {
      diagnostics_.error("vulkan.prototype-unsupported-loop",
                         "Vulkan prototype for loop counters must be mutable "
                         "local variables");
      return false;
    }

    const std::string typeId = ensureType(local->second.type);
    const std::string loaded = nextTemp();
    instructionLines_.push_back(loaded + " = OpLoad " + typeId + " " +
                                local->second.variableId);
    const std::string amount =
        ensureNumericConstant(HIRType{"int", std::nullopt}, update->amount);
    const std::string updated = nextTemp();
    const std::string opcode = update->increment ? "OpIAdd" : "OpISub";
    instructionLines_.push_back(updated + " = " + opcode + " " + typeId +
                                " " + loaded + " " + amount);
    instructionLines_.push_back("OpStore " + local->second.variableId + " " +
                                updated);
    return true;
  }

  bool emitParsedLoopUpdate(const HIRStatement &statement) {
    if (statement.kind != HIRStatementKind::Assignment) {
      diagnostics_.error("vulkan.prototype-unsupported-loop",
                         "Vulkan prototype for loops require assignment-style "
                         "counter updates");
      return false;
    }
    return emitAssignment(statement);
  }

  PrototypeEmitResult emitForStatement(const HIRStatement &statement) {
    const bool whileLowered = isWhileLoweredForStatement(statement);
    std::unordered_map<std::string, PrototypeSPIRVLocal> outerLocals = locals_;
    if (!whileLowered) {
      if (statement.initializer.size() != 1 ||
          statement.initializer.front().kind != HIRStatementKind::Declaration) {
        diagnostics_.error("vulkan.prototype-unsupported-loop",
                           "Vulkan prototype for loops require a single scalar "
                           "int declaration initializer");
        return {};
      }

      if (!emitDeclaration(statement.initializer.front())) {
        locals_ = std::move(outerLocals);
        return {};
      }
    }

    const std::string headerLabel = nextLabel("loop_header");
    const std::string bodyLabel = nextLabel("loop_body");
    const std::string continueLabel = nextLabel("loop_continue");
    const std::string mergeLabel = nextLabel("loop_merge");

    instructionLines_.push_back("OpBranch " + headerLabel);
    instructionLines_.push_back(headerLabel + " = OpLabel");

    std::optional<PrototypeSPIRVValue> condition =
        emitExpression(statement.value);
    if (!condition.has_value()) {
      locals_ = std::move(outerLocals);
      return {};
    }

    instructionLines_.push_back("OpLoopMerge " + mergeLabel + " " +
                                continueLabel + " None");
    instructionLines_.push_back("OpBranchConditional " + condition->id + " " +
                                bodyLabel + " " + mergeLabel);

    instructionLines_.push_back(bodyLabel + " = OpLabel");
    loopLabels_.push_back(PrototypeLoopLabels{continueLabel, mergeLabel});
    const PrototypeEmitResult bodyBlock = emitBranchBody(statement.body, false);
    loopLabels_.pop_back();
    if (!bodyBlock.success) {
      locals_ = std::move(outerLocals);
      return {};
    }
    if (!bodyBlock.terminated) {
      instructionLines_.push_back("OpBranch " + continueLabel);
    }

    instructionLines_.push_back(continueLabel + " = OpLabel");
    if (!whileLowered) {
      if (!statement.update.empty()) {
        if (statement.update.size() != 1 ||
            !emitParsedLoopUpdate(statement.update.front())) {
          locals_ = std::move(outerLocals);
          return {};
        }
      } else {
        if (!emitLoopUpdate(statement.updateTokens)) {
          locals_ = std::move(outerLocals);
          return {};
        }
      }
    }
    instructionLines_.push_back("OpBranch " + headerLabel);

    instructionLines_.push_back(mergeLabel + " = OpLabel");
    locals_ = std::move(outerLocals);
    return PrototypeEmitResult{true, false};
  }

  bool emitDeclaration(const HIRStatement &statement) {
    if (statement.declaredType.arraySize.has_value()) {
      PrototypeSPIRVLocal local;
      local.type = statement.declaredType;
      if (statement.value.kind == HIRExpressionKind::Empty) {
        const std::string typeId = ensureType(statement.declaredType);
        if (typeId.empty()) {
          return false;
        }
        local.valueId = makeVariableId(statement.name);
        instructionLines_.push_back(local.valueId + " = OpUndef " + typeId);
      } else {
        std::optional<PrototypeSPIRVValue> value =
            emitStatementAssignmentValue(statement.value);
        if (!value.has_value()) {
          return false;
        }
        local.valueId = value->id;
      }
      locals_[statement.name] = local;
      return true;
    }

    PrototypeSPIRVLocal local;
    local.type = statement.declaredType;
    local.pointerTypeId = ensurePointerType(statement.declaredType);
    local.variableId = makeVariableId(statement.name);
    local.knownZeroIndex =
        statement.declaredType.name == "int" &&
        !statement.declaredType.arraySize.has_value() &&
        isPrototypeZeroLiteral(statement.value);
    locals_[statement.name] = local;
    variableLines_.push_back(local.variableId + " = OpVariable " +
                             local.pointerTypeId + " Function");

    if (statement.value.kind == HIRExpressionKind::Empty) {
      return true;
    }

    std::optional<PrototypeSPIRVValue> value =
        emitStatementAssignmentValue(statement.value);
    if (!value.has_value()) {
      return false;
    }
    instructionLines_.push_back("OpStore " + local.variableId + " " + value->id);
    return true;
  }

  bool emitAssignment(const HIRStatement &statement) {
    if (statement.target.kind == HIRExpressionKind::IndexAccess &&
        isLocalArrayElementAccess(statement.target)) {
      return emitLocalArrayElementStore(statement);
    }
    if (statement.target.kind == HIRExpressionKind::IndexAccess ||
        statement.target.kind == HIRExpressionKind::MemberAccess) {
      return emitStorageBufferStore(statement);
    }

    if (statement.target.kind != HIRExpressionKind::Identifier) {
      diagnostics_.error("vulkan.prototype-unsupported-assignment-target",
                         "Vulkan prototype binary emission currently assigns "
                         "only to local identifiers or storage buffer indices");
      return false;
    }
    const auto local = locals_.find(statement.target.value);
    if (local == locals_.end()) {
      diagnostics_.error("vulkan.prototype-unsupported-assignment-target",
                         "Vulkan prototype binary emission cannot assign to "
                         "unknown local '" +
                             statement.target.value + "'");
      return false;
    }
    if (local->second.variableId.empty() || local->second.readOnly) {
      diagnostics_.error("vulkan.prototype-unsupported-assignment-target",
                         "Vulkan prototype binary emission cannot assign to "
                         "read-only function parameter '" +
                             statement.target.value + "'");
      return false;
    }

    std::optional<PrototypeSPIRVValue> value =
        emitStatementAssignmentValue(statement.value);
    if (!value.has_value()) {
      return false;
    }
    instructionLines_.push_back("OpStore " + local->second.variableId + " " +
                                value->id);
    local->second.knownZeroIndex =
        local->second.type.name == "int" &&
        !local->second.type.arraySize.has_value() &&
        isPrototypeZeroLiteral(statement.value);
    return true;
  }

  bool emitStorageBufferStore(const HIRStatement &statement) {
    std::optional<std::string> pointer;
    if (isStructStorageBufferMemberAccess(statement.target)) {
      pointer = emitStorageBufferMemberPointer(statement.target);
    } else {
      pointer = emitStorageBufferElementPointer(statement.target);
    }
    if (!pointer.has_value()) {
      return false;
    }

    std::optional<PrototypeSPIRVValue> value =
        emitStatementAssignmentValue(statement.value);
    if (!value.has_value()) {
      return false;
    }

    instructionLines_.push_back("OpStore " + *pointer + " " + value->id);
    return true;
  }

  std::optional<std::string> emitStorageBufferElementPointer(
      const HIRExpression &indexAccess) {
    const std::optional<PrototypeStorageBufferIndexAccess> access =
        prototypeStorageBufferIndexAccess(indexAccess);
    if (!access.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-assignment-target",
                         "Vulkan prototype binary emission currently supports "
                         "only direct storage buffer index targets");
      return std::nullopt;
    }

    const std::string &resourceName = access->resourceName;
    const auto buffer = storageBuffers_.find(resourceName);
    if (buffer == storageBuffers_.end()) {
      diagnostics_.error("vulkan.prototype-unsupported-assignment-target",
                         "Vulkan prototype binary emission cannot resolve "
                         "storage buffer resource '" +
                             resourceName + "'");
      return std::nullopt;
    }
    if (buffer->second.isRuntimeArrayBlock) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-runtime-array-block-index",
          "Vulkan prototype runtime-array storage-buffer blocks require "
          "member access through literal index zero, such as buffer[0].field");
      return std::nullopt;
    }

    const bool bufferIsDescriptorArray =
        buffer->second.resourceType.arraySize.has_value();
    if (bufferIsDescriptorArray && access->descriptorIndex == nullptr) {
      diagnostics_.error("vulkan.prototype-unsupported-assignment-target",
                         "Vulkan prototype storage-buffer descriptor arrays "
                         "require descriptor and element indices, such as "
                         "values[0][1]");
      return std::nullopt;
    }
    if (!bufferIsDescriptorArray && access->descriptorIndex != nullptr) {
      diagnostics_.error("vulkan.prototype-unsupported-assignment-target",
                         "Vulkan prototype non-array storage buffers support "
                         "only one element index");
      return std::nullopt;
    }

    std::optional<PrototypeSPIRVValue> descriptorIndex;
    if (access->descriptorIndex != nullptr) {
      descriptorIndex = emitDescriptorIndexExpression(
          *access->descriptorIndex, PrototypeNonUniformDescriptorUse::StorageBuffer);
      if (!descriptorIndex.has_value()) {
        return std::nullopt;
      }
    }

    if (access->elementIndex == nullptr) {
      diagnostics_.error("vulkan.prototype-unsupported-assignment-target",
                         "Vulkan prototype storage-buffer access requires an "
                         "element index");
      return std::nullopt;
    }
    std::optional<PrototypeSPIRVValue> elementIndex =
        emitExpression(*access->elementIndex);
    if (!elementIndex.has_value()) {
      return std::nullopt;
    }

    const std::string zero = ensureNumericConstant(HIRType{"int", std::nullopt}, "0");
    const std::string pointer = nextTemp();
    std::ostringstream accessChain;
    accessChain << pointer << " = OpAccessChain "
                << buffer->second.elementPointerTypeId << " "
                << buffer->second.variableId;
    if (descriptorIndex.has_value()) {
      accessChain << " " << descriptorIndex->id;
    }
    accessChain << " " << zero << " " << elementIndex->id;
    instructionLines_.push_back(accessChain.str());
    if (descriptorIndex.has_value() && descriptorIndex->nonUniformDescriptor) {
      decorateNonUniform(pointer);
    }
    return pointer;
  }

  DiagnosticEngine &diagnostics_;
  SPIRVModule module_;
  std::vector<std::string> variableLines_;
  std::vector<std::string> instructionLines_;
  std::vector<std::string> entryPointInterfaces_;
  std::unordered_map<std::string, std::string> typeIds_;
  std::unordered_map<std::string, std::string> pointerTypeIds_;
  std::unordered_map<std::string, std::string> functionValueTypeIds_;
  std::unordered_map<std::string, std::string> functionPointerTypeIds_;
  std::unordered_map<std::string, std::string> inputPointerTypeIds_;
  std::unordered_map<std::string, std::string> computeBuiltinVariableIds_;
  std::unordered_map<std::string, std::string> workgroupTypeIds_;
  std::unordered_map<std::string, std::string> workgroupPointerTypeIds_;
  std::unordered_map<std::string, std::string> storageRuntimeArrayTypeIds_;
  std::unordered_map<std::string, std::string> storageStructTypeIds_;
  std::unordered_map<std::string, std::string> storageStructPointerTypeIds_;
  std::unordered_map<std::string, std::string> storageDescriptorArrayTypeIds_;
  std::unordered_map<std::string, std::string>
      storageDescriptorArrayPointerTypeIds_;
  std::unordered_map<std::string, std::string> storageElementPointerTypeIds_;
  std::unordered_map<std::string, std::string> uniformBlockTypeIds_;
  std::unordered_map<std::string, std::string> uniformDescriptorArrayTypeIds_;
  std::unordered_map<std::string, std::string> uniformResourcePointerTypeIds_;
  std::unordered_map<std::string, std::string> uniformElementPointerTypeIds_;
  std::unordered_map<std::string, std::string> imageTypeIds_;
  std::unordered_map<std::string, std::string> imagePointerTypeIds_;
  std::unordered_map<std::size_t, std::string> boolVectorTypeIds_;
  std::unordered_map<std::string, std::string> descriptorArrayTypeIds_;
  std::unordered_map<std::string, std::string> uniformConstantPointerTypeIds_;
  std::unordered_map<std::string, std::string> sampledImageTypeIds_;
  std::unordered_map<std::string, std::string> constantIds_;
  std::unordered_map<std::string, PrototypeSPIRVLocal> locals_;
  std::vector<PrototypeLoopLabels> loopLabels_;
  std::unordered_map<std::string, PrototypeSPIRVFunctionInfo> functions_;
  VulkanPrototypeResourceArrayParameterAliasMap resourceArrayParameterAliases_;
  VulkanPrototypeArrayWriteBackParameterMap arrayWriteBackParameters_;
  HIRType currentReturnType_;
  std::string currentFunctionName_;
  StorageLayoutContext layoutContext_;
  PrototypeStructMap structs_;
  PrototypeConstantMap constants_;
  std::unordered_map<std::string, PrototypeSPIRVStorageBuffer> storageBuffers_;
  std::unordered_map<std::string, PrototypeSPIRVWorkgroupShared>
      workgroupShared_;
  std::unordered_map<std::string, PrototypeSPIRVUniformBuffer> uniformBuffers_;
  std::unordered_map<std::string, PrototypeSPIRVDescriptorResource>
      uniformConstantDescriptors_;
  std::unordered_set<std::string> variableIds_;
  std::unordered_set<std::string> entryPointInterfaceIds_;
  std::unordered_set<std::string> nonUniformDecorationIds_;
  std::unordered_map<std::string, std::string> functionTypeIds_;
  std::string samplerTypeId_;
  bool usesRuntimeDescriptorArray_ = false;
  bool usesNonUniformDescriptorIndex_ = false;
  bool usesSampledImageArrayNonUniformIndexing_ = false;
  bool usesStorageImageArrayNonUniformIndexing_ = false;
  bool usesStorageBufferArrayNonUniformIndexing_ = false;
};

bool vulkanGraphicsTypeEquals(const HIRType &lhs, const HIRType &rhs) {
  return lhs.name == rhs.name && lhs.arraySize == rhs.arraySize;
}

bool vulkanGraphicsScalarVectorTypeSupported(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return false;
  }
  return type.name == "float" || type.name == "int" || type.name == "uint" ||
         type.name == "bool" || type.name == "vec2" || type.name == "vec3" ||
         type.name == "vec4" || type.name == "ivec2" ||
         type.name == "ivec3" || type.name == "ivec4" ||
         type.name == "uvec2" || type.name == "uvec3" ||
         type.name == "uvec4" || type.name == "bvec2" ||
         type.name == "bvec3" || type.name == "bvec4";
}

bool vulkanGraphicsMatrixTypeSupported(const HIRType &type) {
  return prototypeMatrixDimension(type).has_value();
}

const HIRField *vulkanGraphicsFindField(const HIRStruct &structure,
                                        std::string_view name) {
  for (const HIRField &field : structure.fields) {
    if (field.name == name) {
      return &field;
    }
  }
  return nullptr;
}

std::optional<std::size_t>
vulkanGraphicsFieldIndex(const HIRStruct &structure, std::string_view name) {
  for (std::size_t index = 0; index < structure.fields.size(); ++index) {
    if (structure.fields[index].name == name) {
      return index;
    }
  }
  return std::nullopt;
}

const HIRStruct *vulkanGraphicsStructType(const HIRModule &module,
                                          const HIRType &type) {
  if (type.arraySize.has_value() || type.name.empty() ||
      type.name.back() == '*') {
    return nullptr;
  }
  return findStruct(module, type.name);
}

bool vulkanGraphicsStructSupported(const HIRStruct &structure) {
  if (structure.fields.empty()) {
    return false;
  }
  for (const HIRField &field : structure.fields) {
    if (!vulkanGraphicsScalarVectorTypeSupported(field.type)) {
      return false;
    }
  }
  return true;
}

bool vulkanGraphicsUniformFieldTypeSupported(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return false;
  }
  return type.name == "float" || type.name == "int" || type.name == "uint" ||
         type.name == "vec2" || type.name == "vec3" ||
         type.name == "vec4" || type.name == "ivec2" ||
         type.name == "ivec3" || type.name == "ivec4" ||
         type.name == "uvec2" || type.name == "uvec3" ||
         type.name == "uvec4";
}

bool vulkanGraphicsUniformStructSupported(const HIRStruct &structure) {
  if (structure.fields.empty()) {
    return false;
  }
  for (const HIRField &field : structure.fields) {
    if (!vulkanGraphicsUniformFieldTypeSupported(field.type)) {
      return false;
    }
  }
  return true;
}

bool vulkanGraphicsUniformResourceSupported(const HIRModule &module,
                                            const HIRResource &resource) {
  if (resource.kind != HIRResourceKind::Uniform ||
      resource.type.arraySize.has_value()) {
    return false;
  }
  const HIRStruct *structure = vulkanGraphicsStructType(module, resource.type);
  return structure != nullptr &&
         vulkanGraphicsUniformStructSupported(*structure);
}

bool vulkanGraphicsDescriptorArraySizeSupported(const HIRModule &module,
                                                const HIRResource &resource) {
  if (!resource.type.arraySize.has_value()) {
    return true;
  }
  if (resource.type.arraySize->empty()) {
    return vulkanRuntimeTextureSamplerDescriptorArraySupported(module,
                                                               resource);
  }
  const StorageLayoutContext layoutContext(module.structs, module.constants);
  return prototypeArrayElementCount(resource.type, layoutContext).has_value();
}

bool vulkanGraphicsSampledTextureResourceSupported(const HIRModule &module,
                                                   const HIRResource &resource) {
  const HIRType elementType = arrayElementType(resource.type);
  return resource.kind == HIRResourceKind::Texture &&
         vulkanGraphicsDescriptorArraySizeSupported(module, resource) &&
         (elementType.name == "sampler2D" ||
          elementType.name == "sampler2DShadow" ||
          elementType.name == "sampler2DArrayShadow");
}

bool vulkanGraphicsSamplerResourceSupported(const HIRModule &module,
                                            const HIRResource &resource) {
  const HIRType elementType = arrayElementType(resource.type);
  return resource.kind == HIRResourceKind::Sampler &&
         vulkanGraphicsDescriptorArraySizeSupported(module, resource) &&
         (elementType.name == "sampler" ||
          elementType.name == "comparison_sampler");
}

bool vulkanGraphicsStageResourceSupported(const HIRModule &module,
                                          const HIRStage &stage,
                                          const HIRResource &resource) {
  if (vulkanGraphicsUniformResourceSupported(module, resource)) {
    return true;
  }
  if (stage.stage != "vertex" && stage.stage != "fragment") {
    return false;
  }
  return vulkanGraphicsSampledTextureResourceSupported(module, resource) ||
         vulkanGraphicsSamplerResourceSupported(module, resource);
}

const HIRField *vulkanGraphicsPositionField(const HIRStruct &structure) {
  if (const HIRField *position =
          vulkanGraphicsFindField(structure, "position")) {
    if (!position->type.arraySize.has_value() &&
        position->type.name == "vec4") {
      return position;
    }
  }
  if (const HIRField *clipPosition =
          vulkanGraphicsFindField(structure, "clipPosition")) {
    if (!clipPosition->type.arraySize.has_value() &&
        clipPosition->type.name == "vec4") {
      return clipPosition;
    }
  }
  return nullptr;
}

bool vulkanGraphicsIsPositionField(const HIRField &field) {
  return (field.name == "position" || field.name == "clipPosition") &&
         !field.type.arraySize.has_value() && field.type.name == "vec4";
}

const HIRStage *findVulkanGraphicsStage(const HIRModule &module,
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

bool vulkanGraphicsStagePair(const HIRModule &module, const HIRStage *&vertex,
                             const HIRStage *&fragment) {
  vertex = nullptr;
  fragment = nullptr;
  if (module.stages.size() != 2) {
    return false;
  }
  vertex = findVulkanGraphicsStage(module, "vertex");
  fragment = findVulkanGraphicsStage(module, "fragment");
  return vertex != nullptr && fragment != nullptr;
}

bool vulkanGraphicsEntrySignatureSupported(const HIRModule &module,
                                           const HIRStage &stage,
                                           const HIRFunction &function) {
  if (stage.stage != "vertex" && stage.stage != "fragment") {
    return false;
  }
  if (function.parameters.size() != 1) {
    return false;
  }
  const HIRStruct *input =
      vulkanGraphicsStructType(module, function.parameters.front().type);
  const HIRStruct *output =
      vulkanGraphicsStructType(module, function.returnType);
  if (input == nullptr || output == nullptr ||
      !vulkanGraphicsStructSupported(*input) ||
      !vulkanGraphicsStructSupported(*output)) {
    return false;
  }
  if (stage.stage == "vertex" &&
      vulkanGraphicsPositionField(*output) == nullptr) {
    return false;
  }
  return true;
}

bool vulkanGraphicsVaryingsSupported(const HIRModule &module,
                                     const HIRFunction &vertexEntry,
                                     const HIRFunction &fragmentEntry) {
  const HIRStruct *vertexOutput =
      vulkanGraphicsStructType(module, vertexEntry.returnType);
  const HIRStruct *fragmentInput =
      vulkanGraphicsStructType(module, fragmentEntry.parameters.front().type);
  if (vertexOutput == nullptr || fragmentInput == nullptr) {
    return false;
  }
  for (const HIRField &field : fragmentInput->fields) {
    const HIRField *source = vulkanGraphicsFindField(*vertexOutput, field.name);
    if (source == nullptr || vulkanGraphicsIsPositionField(*source) ||
        !vulkanGraphicsTypeEquals(source->type, field.type)) {
      return false;
    }
  }
  return true;
}

bool vulkanGraphicsValueTypeSupported(const HIRModule &module,
                                      const HIRType &type) {
  return vulkanGraphicsScalarVectorTypeSupported(type) ||
         vulkanGraphicsMatrixTypeSupported(type) ||
         (type.name != "void" && !type.arraySize.has_value() &&
          vulkanGraphicsStructType(module, type) != nullptr);
}

bool vulkanGraphicsExpressionSupported(const HIRModule &module,
                                       const HIRStage &stage,
                                       const HIRExpression &expression,
                                       bool allowStageHelpers = true);
bool vulkanGraphicsConstructorSupported(const HIRModule &module,
                                        const HIRStage &stage,
                                        const HIRExpression &expression,
                                        bool allowStageHelpers);
std::optional<std::vector<std::size_t>>
vulkanGraphicsSwizzleIndices(const HIRType &type, std::string_view member);
bool vulkanGraphicsSwizzleResultTypeSupported(
    const HIRType &baseType, const HIRType &resultType,
    const std::vector<std::size_t> &indices);

const HIRFunction *
vulkanGraphicsStageHelperFunction(const HIRStage &stage,
                                  std::string_view functionName) {
  for (const HIRFunction &function : stage.functions) {
    if (function.name == functionName &&
        function.name != stage.entryPointName) {
      return &function;
    }
  }
  return nullptr;
}

const HIRFunction *
vulkanGraphicsTopLevelHelperFunction(const HIRModule &module,
                                     std::string_view functionName) {
  for (const HIRFunction &function : module.functions) {
    if (function.name == functionName) {
      return &function;
    }
  }
  return nullptr;
}

const HIRFunction *vulkanGraphicsHelperFunction(const HIRModule &module,
                                                const HIRStage &stage,
                                                std::string_view functionName,
                                                bool allowStageHelpers) {
  if (allowStageHelpers) {
    if (const HIRFunction *function =
            vulkanGraphicsStageHelperFunction(stage, functionName)) {
      return function;
    }
  }
  return vulkanGraphicsTopLevelHelperFunction(module, functionName);
}

bool vulkanGraphicsHelperSignatureSupported(
    const HIRModule &module, const HIRFunction &function,
    DiagnosticEngine *diagnostics = nullptr) {
  auto diagnose = [&](const std::string &message) {
    if (diagnostics != nullptr) {
      diagnostics->error("vulkan.prototype-unsupported-graphics-helper",
                         message);
    }
  };

  if (!vulkanGraphicsValueTypeSupported(module, function.returnType)) {
    diagnose("Vulkan graphics prototype helper function '" + function.name +
             "' must return a supported scalar, vector, or struct value");
    return false;
  }

  for (const HIRParameter &parameter : function.parameters) {
    if (!vulkanGraphicsValueTypeSupported(module, parameter.type)) {
      diagnose("Vulkan graphics prototype helper function '" + function.name +
               "' parameter '" + parameter.name +
               "' must use a supported scalar, vector, or struct value type");
      return false;
    }
  }
  return true;
}

bool vulkanGraphicsHelperCallSupported(const HIRModule &module,
                                       const HIRStage &stage,
                                       const HIRExpression &expression,
                                       bool allowStageHelpers) {
  const HIRFunction *function = vulkanGraphicsHelperFunction(
      module, stage, expression.value, allowStageHelpers);
  if (function == nullptr ||
      !vulkanGraphicsHelperSignatureSupported(module, *function) ||
      expression.children.size() != function->parameters.size() ||
      (!expression.type.name.empty() &&
       !vulkanGraphicsTypeEquals(expression.type, function->returnType))) {
    return false;
  }

  for (std::size_t index = 0; index < expression.children.size(); ++index) {
    if (!vulkanGraphicsTypeEquals(expression.children[index].type,
                                  function->parameters[index].type) ||
        !vulkanGraphicsExpressionSupported(module, stage,
                                           expression.children[index],
                                           allowStageHelpers)) {
      return false;
    }
  }
  return true;
}

bool vulkanGraphicsDescriptorOperandSupported(const HIRModule &module,
                                              const HIRStage &stage,
                                              const HIRExpression &expression,
                                              std::string_view elementTypeName) {
  if (expression.kind == HIRExpressionKind::Identifier) {
    return !expression.type.arraySize.has_value() &&
           expression.type.name == elementTypeName;
  }
  if (expression.kind != HIRExpressionKind::IndexAccess ||
      expression.children.size() != 2 ||
      expression.children[0].kind != HIRExpressionKind::Identifier ||
      !expression.children[0].type.arraySize.has_value() ||
      arrayElementType(expression.children[0].type).name != elementTypeName ||
      expression.type.arraySize.has_value() ||
      expression.type.name != elementTypeName) {
    return false;
  }
  const HIRExpression &index = expression.children[1];
  if (index.kind == HIRExpressionKind::NonUniform) {
    return index.children.size() == 1 &&
           !index.children.front().type.arraySize.has_value() &&
           index.children.front().type.name == "int" &&
           vulkanGraphicsExpressionSupported(module, stage,
                                             index.children.front());
  }
  return !index.type.arraySize.has_value() && index.type.name == "int" &&
         vulkanGraphicsExpressionSupported(module, stage, index);
}

bool vulkanGraphicsTextureSampleSupported(const HIRModule &module,
                                          const HIRStage &stage,
                                          const HIRExpression &expression) {
  const bool explicitLod = isPrototypeExplicitLodTextureSample(expression);
  const bool implicitSample = isPrototypeImplicitSamplerTextureSample(expression);
  if (!explicitLod && !implicitSample) {
    return false;
  }
  if (stage.stage == "vertex" && !explicitLod) {
    return false;
  }
  if (expression.children.size() != (explicitLod ? 4 : 3)) {
    return false;
  }
  const HIRExpression &texture = expression.children[0];
  const HIRExpression &sampler = expression.children[1];
  const HIRExpression &coordinates = expression.children[2];
  if (!vulkanGraphicsDescriptorOperandSupported(module, stage, texture,
                                                "sampler2D") ||
      !vulkanGraphicsDescriptorOperandSupported(module, stage, sampler,
                                                "sampler") ||
      coordinates.type.arraySize.has_value() ||
      coordinates.type.name != "vec2" ||
      expression.type.arraySize.has_value() || expression.type.name != "vec4") {
    return false;
  }
  if (!vulkanGraphicsExpressionSupported(module, stage, coordinates)) {
    return false;
  }
  return !explicitLod ||
         (!expression.children[3].type.arraySize.has_value() &&
          expression.children[3].type.name == "float" &&
          vulkanGraphicsExpressionSupported(module, stage,
                                            expression.children[3]));
}

bool vulkanGraphicsTextureCompareSupported(const HIRModule &module,
                                           const HIRStage &stage,
                                           const HIRExpression &expression) {
  const bool explicitLod = isPrototypeExplicitLodTextureCompare(expression);
  if ((expression.value != "textureCompare" && !explicitLod) ||
      expression.children.size() != (explicitLod ? 5 : 4) ||
      expression.type.arraySize.has_value() || expression.type.name != "float") {
    return false;
  }
  if (stage.stage == "vertex" && !explicitLod) {
    return false;
  }
  const HIRExpression &texture = expression.children[0];
  const HIRExpression &sampler = expression.children[1];
  const HIRExpression &coordinates = expression.children[2];
  const HIRExpression &depth = expression.children[3];
  const HIRExpression *lod = explicitLod ? &expression.children[4] : nullptr;
  const HIRType textureElementType = arrayElementType(texture.type);
  const std::string expectedCoordinateType =
      prototypeTextureCoordinateType(textureElementType);
  if (!vulkanGraphicsDescriptorOperandSupported(module, stage, texture,
                                                textureElementType.name) ||
      (textureElementType.name != "sampler2DShadow" &&
       textureElementType.name != "sampler2DArrayShadow") ||
      expectedCoordinateType.empty() ||
      !vulkanGraphicsDescriptorOperandSupported(module, stage, sampler,
                                                "comparison_sampler") ||
      coordinates.type.arraySize.has_value() ||
      coordinates.type.name != expectedCoordinateType ||
      depth.type.arraySize.has_value() ||
      depth.type.name != "float") {
    return false;
  }
  return vulkanGraphicsExpressionSupported(module, stage, coordinates) &&
         vulkanGraphicsExpressionSupported(module, stage, depth) &&
         (!explicitLod ||
          (!lod->type.arraySize.has_value() && lod->type.name == "float" &&
           vulkanGraphicsExpressionSupported(module, stage, *lod)));
}

std::string
vulkanGraphicsUnsupportedStatementMessage(const HIRStatement &statement) {
  switch (statement.kind) {
  case HIRStatementKind::For:
    return "Vulkan graphics prototype emission lowers only conservative "
           "scalar-int for loops and lowered while loops with scalar bool "
           "conditions";
  case HIRStatementKind::If:
    return "Vulkan graphics prototype emission does not yet lower 'If' "
           "statements; graphics selection lowering still needs structured "
           "OpSelectionMerge codegen. Compute-stage if lowering is "
           "unaffected.";
  case HIRStatementKind::Raw:
    return "Vulkan graphics prototype emission cannot lower 'Raw' statements; "
           "raw source fallback must be parsed into supported HIR before "
           "native Vulkan graphics codegen.";
  case HIRStatementKind::Expression:
    return "Vulkan graphics prototype emission does not yet lower standalone "
           "'Expression' statements; use declarations, assignments, and "
           "returns in the supported graphics subset.";
  case HIRStatementKind::Break:
    return "Vulkan graphics prototype emission lowers 'Break' statements only "
           "inside conservative structured loop bodies";
  case HIRStatementKind::Continue:
    return "Vulkan graphics prototype emission lowers 'Continue' statements "
           "only inside conservative structured loop bodies";
  case HIRStatementKind::Discard:
    return "Vulkan graphics prototype emission lowers 'Discard' only in "
           "fragment stages; vertex-stage discard is invalid.";
  case HIRStatementKind::Declaration:
  case HIRStatementKind::Assignment:
  case HIRStatementKind::Return:
  case HIRStatementKind::Block:
    break;
  }
  return "unsupported statement in Vulkan graphics prototype";
}

std::optional<std::string> vulkanGraphicsLoopUpdateCounterName(
    const std::vector<Token> &tokens,
    DiagnosticEngine *diagnostics = nullptr) {
  if (tokens.size() == 2 && tokens[0].kind == TokenKind::Identifier &&
      tokens[1].kind == TokenKind::Operator &&
      (tokens[1].text == "++" || tokens[1].text == "--")) {
    return tokens[0].text;
  }
  if (tokens.size() == 2 && tokens[0].kind == TokenKind::Operator &&
      (tokens[0].text == "++" || tokens[0].text == "--") &&
      tokens[1].kind == TokenKind::Identifier) {
    return tokens[1].text;
  }
  if (tokens.size() == 4 && tokens[0].kind == TokenKind::Identifier &&
      tokens[1].kind == TokenKind::Operator &&
      (tokens[1].text == "+" || tokens[1].text == "-") &&
      tokens[2].kind == TokenKind::Equal &&
      tokens[3].kind == TokenKind::Number &&
      tokens[3].text.find('.') == std::string::npos) {
    return tokens[0].text;
  }

  if (diagnostics != nullptr) {
    diagnostics->error("vulkan.prototype-unsupported-graphics-body",
                       "Vulkan graphics prototype for loops support only "
                       "++/-- or +=/-= integer-literal counter updates");
  }
  return std::nullopt;
}

bool vulkanGraphicsParsedLoopUpdateSupported(
    const HIRStatement &statement, std::string_view counterName,
    DiagnosticEngine *diagnostics = nullptr) {
  auto diagnose = [&](std::string_view message) {
    if (diagnostics != nullptr) {
      diagnostics->error("vulkan.prototype-unsupported-graphics-body",
                         std::string(message));
    }
  };

  if (statement.kind != HIRStatementKind::Assignment ||
      statement.target.kind != HIRExpressionKind::Identifier ||
      statement.target.value != counterName) {
    diagnose("Vulkan graphics prototype for loops require assignment-style "
             "updates to the scalar int counter");
    return false;
  }
  if (statement.target.type.arraySize.has_value() ||
      statement.target.type.name != "int") {
    diagnose("Vulkan graphics prototype for loop counters must be scalar int "
             "values");
    return false;
  }
  if (statement.value.kind != HIRExpressionKind::Binary ||
      (statement.value.value != "+" && statement.value.value != "-") ||
      statement.value.children.size() < 2 ||
      statement.value.children[0].kind != HIRExpressionKind::Identifier ||
      statement.value.children[0].value != counterName) {
    diagnose("Vulkan graphics prototype parsed for loop updates must be "
             "counter +/- expression");
    return false;
  }
  if (statement.value.type.arraySize.has_value() ||
      statement.value.type.name != "int") {
    diagnose("Vulkan graphics prototype for loop update type must match the "
             "scalar int counter type");
    return false;
  }
  return true;
}

bool vulkanGraphicsLoopHeaderSupported(
    const HIRModule &module, const HIRStage &stage,
    const HIRStatement &statement, DiagnosticEngine *diagnostics = nullptr,
    bool allowStageHelpers = true) {
  auto diagnose = [&](std::string_view message) {
    if (diagnostics != nullptr) {
      diagnostics->error("vulkan.prototype-unsupported-graphics-body",
                         std::string(message));
    }
  };

  const bool whileLowered = isWhileLoweredForStatement(statement);
  std::string counterName;
  if (!whileLowered) {
    if (statement.initializer.size() != 1 ||
        statement.initializer.front().kind != HIRStatementKind::Declaration) {
      diagnose("Vulkan graphics prototype for loops require a single scalar int "
               "declaration initializer");
      return false;
    }

    const HIRStatement &initializer = statement.initializer.front();
    if (initializer.declaredType.arraySize.has_value() ||
        initializer.declaredType.name != "int") {
      diagnose("Vulkan graphics prototype for loop counters must be scalar int "
               "values");
      return false;
    }
    if (!vulkanGraphicsValueTypeSupported(module, initializer.declaredType) ||
        (initializer.value.kind != HIRExpressionKind::Empty &&
         !vulkanGraphicsExpressionSupported(module, stage, initializer.value,
                                            allowStageHelpers))) {
      diagnose("Vulkan graphics prototype for loop initializers must use the "
               "supported graphics scalar/vector expression subset");
      return false;
    }
    counterName = initializer.name;
  }

  if (statement.value.kind == HIRExpressionKind::Empty ||
      statement.value.type.arraySize.has_value() ||
      statement.value.type.name != "bool" ||
      !vulkanGraphicsExpressionSupported(module, stage, statement.value,
                                         allowStageHelpers)) {
    diagnose("Vulkan graphics prototype loop conditions must be scalar bool "
             "values");
    return false;
  }

  if (whileLowered) {
    return true;
  }

  if (!statement.update.empty()) {
    if (statement.update.size() != 1 ||
        !vulkanGraphicsParsedLoopUpdateSupported(statement.update.front(),
                                                 counterName, diagnostics)) {
      return false;
    }
    return true;
  }

  const std::optional<std::string> updateCounter =
      vulkanGraphicsLoopUpdateCounterName(statement.updateTokens, diagnostics);
  if (!updateCounter.has_value()) {
    return false;
  }
  if (*updateCounter != counterName) {
    diagnose("Vulkan graphics prototype for loop updates must target the loop "
             "counter");
    return false;
  }
  return true;
}

PrototypeBlockSupport
vulkanGraphicsStatementSupported(const HIRModule &module, const HIRStage &stage,
                                 const HIRStatement &statement,
                                 DiagnosticEngine *diagnostics = nullptr,
                                 bool allowLoopControl = false,
                                 bool allowStageHelpers = true) {
  auto diagnoseUnsupportedBody = [&]() {
    if (diagnostics != nullptr) {
      diagnostics->error("vulkan.prototype-unsupported-graphics-body",
                         vulkanGraphicsUnsupportedStatementMessage(statement));
    }
  };

  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    if (vulkanGraphicsValueTypeSupported(module, statement.declaredType) &&
        (statement.value.kind == HIRExpressionKind::Empty ||
         vulkanGraphicsExpressionSupported(module, stage, statement.value,
                                           allowStageHelpers))) {
      return PrototypeBlockSupport{true, false};
    }
    diagnoseUnsupportedBody();
    return {};
  case HIRStatementKind::Assignment:
    if (vulkanGraphicsExpressionSupported(module, stage, statement.target,
                                          allowStageHelpers) &&
        vulkanGraphicsExpressionSupported(module, stage, statement.value,
                                          allowStageHelpers)) {
      return PrototypeBlockSupport{true, false};
    }
    diagnoseUnsupportedBody();
    return {};
  case HIRStatementKind::Return:
    if (statement.value.kind != HIRExpressionKind::Empty &&
        vulkanGraphicsExpressionSupported(module, stage, statement.value,
                                          allowStageHelpers)) {
      return PrototypeBlockSupport{true, true};
    }
    diagnoseUnsupportedBody();
    return {};
  case HIRStatementKind::Block: {
    bool terminated = false;
    for (const HIRStatement &child : statement.body) {
      if (terminated) {
        if (diagnostics != nullptr) {
          diagnostics->error("vulkan.prototype-unsupported-graphics-body",
                             "Vulkan graphics prototype emission requires a "
                             "terminating return/discard statement to be final");
        }
        return {};
      }
      const PrototypeBlockSupport childSupport =
          vulkanGraphicsStatementSupported(module, stage, child, diagnostics,
                                           allowLoopControl,
                                           allowStageHelpers);
      if (!childSupport.supported) {
        return {};
      }
      terminated = childSupport.terminated;
    }
    return PrototypeBlockSupport{true, terminated};
  }
  case HIRStatementKind::If: {
    if (statement.value.kind == HIRExpressionKind::Empty ||
        !vulkanGraphicsExpressionSupported(module, stage, statement.value,
                                           allowStageHelpers)) {
      diagnoseUnsupportedBody();
      return {};
    }
    auto bodySupported = [&](const std::vector<HIRStatement> &body)
        -> PrototypeBlockSupport {
      bool terminated = false;
      for (const HIRStatement &child : body) {
        if (terminated) {
          if (diagnostics != nullptr) {
            diagnostics->error(
                "vulkan.prototype-unsupported-graphics-body",
                "Vulkan graphics prototype emission requires a terminating "
                "return/discard statement to be final");
          }
          return {};
        }
        const PrototypeBlockSupport childSupport =
            vulkanGraphicsStatementSupported(module, stage, child, diagnostics,
                                             allowLoopControl,
                                             allowStageHelpers);
        if (!childSupport.supported) {
          return {};
        }
        terminated = childSupport.terminated;
      }
      return PrototypeBlockSupport{true, terminated};
    };
    const PrototypeBlockSupport thenSupport = bodySupported(statement.body);
    if (!thenSupport.supported) {
      return {};
    }
    PrototypeBlockSupport elseSupport{true, false};
    if (!statement.elseBody.empty()) {
      elseSupport = bodySupported(statement.elseBody);
      if (!elseSupport.supported) {
        return {};
      }
    }
    return PrototypeBlockSupport{
        true, !statement.elseBody.empty() && thenSupport.terminated &&
                  elseSupport.terminated};
  }
  case HIRStatementKind::For: {
    if (!vulkanGraphicsLoopHeaderSupported(module, stage, statement,
                                           diagnostics, allowStageHelpers)) {
      return {};
    }
    bool terminated = false;
    for (const HIRStatement &child : statement.body) {
      if (terminated) {
        if (diagnostics != nullptr) {
          diagnostics->error(
              "vulkan.prototype-unsupported-graphics-body",
              "Vulkan graphics prototype emission requires a terminating "
              "return/discard statement to be final");
        }
        return {};
      }
      const PrototypeBlockSupport childSupport =
          vulkanGraphicsStatementSupported(module, stage, child, diagnostics,
                                           true, allowStageHelpers);
      if (!childSupport.supported) {
        return {};
      }
      terminated = childSupport.terminated;
    }
    return PrototypeBlockSupport{true, false};
  }
  case HIRStatementKind::Discard:
    if (stage.stage == "fragment") {
      return PrototypeBlockSupport{true, true};
    }
    diagnoseUnsupportedBody();
    return {};
  case HIRStatementKind::Expression:
  case HIRStatementKind::Raw:
    diagnoseUnsupportedBody();
    return {};
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
    if (allowLoopControl) {
      return PrototypeBlockSupport{true, true};
    }
    diagnoseUnsupportedBody();
    return {};
  }
  return {};
}

bool vulkanGraphicsExpressionSupported(const HIRModule &module,
                                       const HIRStage &stage,
                                       const HIRExpression &expression,
                                       bool allowStageHelpers) {
  switch (expression.kind) {
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::Literal:
    return true;
  case HIRExpressionKind::Group:
  case HIRExpressionKind::Unary:
    return expression.children.size() == 1 &&
           vulkanGraphicsExpressionSupported(module, stage,
                                             expression.children.front(),
                                             allowStageHelpers);
  case HIRExpressionKind::MemberAccess:
    if (expression.children.size() != 1 ||
        !vulkanGraphicsExpressionSupported(module, stage,
                                           expression.children.front(),
                                           allowStageHelpers)) {
      return false;
    }
    if (vulkanGraphicsScalarVectorTypeSupported(
            expression.children.front().type)) {
      const std::optional<std::vector<std::size_t>> indices =
          vulkanGraphicsSwizzleIndices(expression.children.front().type,
                                       expression.value);
      return indices.has_value() &&
             vulkanGraphicsSwizzleResultTypeSupported(
                 expression.children.front().type, expression.type, *indices);
    }
    return vulkanGraphicsValueTypeSupported(module, expression.type);
  case HIRExpressionKind::Constructor:
    return vulkanGraphicsConstructorSupported(module, stage, expression,
                                              allowStageHelpers);
  case HIRExpressionKind::Binary:
    return expression.children.size() == 2 &&
           vulkanGraphicsExpressionSupported(module, stage,
                                             expression.children[0],
                                             allowStageHelpers) &&
           vulkanGraphicsExpressionSupported(module, stage,
                                             expression.children[1],
                                             allowStageHelpers);
  case HIRExpressionKind::Select:
    return expression.children.size() == 3 &&
           expression.children[0].type.name == "bool" &&
           !expression.children[0].type.arraySize.has_value() &&
           vulkanGraphicsScalarVectorTypeSupported(expression.type) &&
           vulkanGraphicsTypeEquals(expression.type,
                                    expression.children[1].type) &&
           vulkanGraphicsTypeEquals(expression.type,
                                    expression.children[2].type) &&
           vulkanGraphicsExpressionSupported(module, stage,
                                             expression.children[0],
                                             allowStageHelpers) &&
           vulkanGraphicsExpressionSupported(module, stage,
                                             expression.children[1],
                                             allowStageHelpers) &&
           vulkanGraphicsExpressionSupported(module, stage,
                                             expression.children[2],
                                             allowStageHelpers);
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::TextureCompareLodManual:
    return false;
  case HIRExpressionKind::Call:
    if (prototypeIntrinsicLoweringForCall(expression).has_value()) {
      for (const HIRExpression &child : expression.children) {
        if (!vulkanGraphicsExpressionSupported(module, stage, child,
                                               allowStageHelpers)) {
          return false;
        }
      }
      return true;
    }
    return vulkanGraphicsHelperCallSupported(module, stage, expression,
                                             allowStageHelpers);
  case HIRExpressionKind::TextureCompare:
    return allowStageHelpers &&
           vulkanGraphicsTextureCompareSupported(module, stage, expression);
  case HIRExpressionKind::TextureSample:
    return allowStageHelpers &&
           vulkanGraphicsTextureSampleSupported(module, stage, expression);
  }
  return false;
}

bool vulkanGraphicsFunctionSupported(const HIRModule &module,
                                     const HIRStage &stage,
                                     const HIRFunction &function,
                                     DiagnosticEngine *diagnostics = nullptr,
                                     bool allowStageHelpers = true,
                                     bool requireFinalReturn = false) {
  bool terminated = false;
  for (const HIRStatement &statement : function.body) {
    if (terminated) {
      if (diagnostics != nullptr) {
        diagnostics->error("vulkan.prototype-unsupported-graphics-body",
                           "Vulkan graphics prototype emission requires a "
                           "terminating return/discard statement to be final");
      }
      return false;
    }
    const PrototypeBlockSupport support =
        vulkanGraphicsStatementSupported(module, stage, statement, diagnostics,
                                         false, allowStageHelpers);
    if (!support.supported) {
      return false;
    }
    terminated = support.terminated;
  }
  if (requireFinalReturn && !terminated) {
    if (diagnostics != nullptr) {
      diagnostics->error("vulkan.prototype-unsupported-graphics-helper",
                         "Vulkan graphics prototype helper function '" +
                             function.name +
                             "' requires an explicit final return");
    }
    return false;
  }
  return true;
}

std::string vulkanGraphicsStageResourceUnsupportedReason(
    const HIRModule &module, const HIRStage &stage,
    const HIRResource &resource);

std::string
vulkanGraphicsUnsupportedStageResourcesMessage(const HIRStage &vertex,
                                               const HIRStage &fragment,
                                               const HIRModule &module) {
  std::ostringstream message;
  message << "Vulkan graphics prototype emission does not yet support "
             "some vertex/fragment stage resources; compute-stage resource "
             "lowering is unaffected. Unsupported resources:";
  bool first = true;
  auto appendStageResources = [&](const HIRStage &stage) {
    for (const HIRResource &resource : stage.resources) {
      if (vulkanGraphicsStageResourceSupported(module, stage, resource)) {
        continue;
      }
      message << (first ? " " : ", ");
      first = false;
      message << stage.stage << "." << resource.name << " ("
              << resourceKindLabel(resource.kind)
              << ", type " << formatType(resource.type);
      if (vulkanResourceUsesDescriptor(resource.kind)) {
        message << ", set " << resource.set << " binding "
                << resource.binding;
      }
      message << "; reason: "
              << vulkanGraphicsStageResourceUnsupportedReason(module, stage,
                                                              resource)
              << ")";
    }
  };
  appendStageResources(vertex);
  appendStageResources(fragment);
  return message.str();
}

bool vulkanGraphicsStageResourcesSupported(const HIRModule &module,
                                           const HIRStage &vertex,
                                           const HIRStage &fragment) {
  auto stageSupported = [&](const HIRStage &stage) {
    for (const HIRResource &resource : stage.resources) {
      if (!vulkanGraphicsStageResourceSupported(module, stage, resource)) {
        return false;
      }
    }
    return true;
  };
  return stageSupported(vertex) && stageSupported(fragment);
}

std::string vulkanGraphicsStageResourceUnsupportedReason(
    const HIRModule &module, const HIRStage &stage,
    const HIRResource &resource) {
  if (resource.kind == HIRResourceKind::Uniform) {
    if (resource.type.arraySize.has_value()) {
      return "uniform-buffer descriptor arrays are not supported in the "
             "graphics prototype";
    }
    return "uniform buffers must be supported struct uniform resources";
  }
  if (resource.kind != HIRResourceKind::Texture &&
      resource.kind != HIRResourceKind::Sampler) {
    return "only struct uniform buffers and graphics texture/sampler "
           "descriptors are supported";
  }
  if (stage.stage != "vertex" && stage.stage != "fragment") {
    return "texture/sampler descriptors are supported only in graphics stages";
  }
  if (resource.type.arraySize.has_value() &&
      !vulkanGraphicsDescriptorArraySizeSupported(module, resource)) {
    if (resource.type.arraySize->empty()) {
      return vulkanRuntimeDescriptorArrayUnsupportedMessage(module, resource);
    }
    return "descriptor arrays require fixed-size numeric resource array "
           "sizes";
  }
  if (resource.kind == HIRResourceKind::Texture) {
    return "graphics sampled textures currently support sampler2D, "
           "sampler2DShadow, and sampler2DArrayShadow resources, including "
           "descriptor arrays";
  }
  return "graphics samplers currently support sampler and comparison_sampler "
         "resources, including descriptor arrays";
}

bool vulkanGraphicsPrototypeSupported(const HIRModule &module,
                                      DiagnosticEngine &diagnostics) {
  const HIRStage *vertex = nullptr;
  const HIRStage *fragment = nullptr;
  if (!vulkanGraphicsStagePair(module, vertex, fragment)) {
    diagnostics.error("vulkan.prototype-unsupported-stage",
                      "Vulkan graphics prototype emission currently supports "
                      "exactly one vertex stage and one fragment stage");
    return false;
  }
  if (!module.constants.empty()) {
    diagnostics.error("vulkan.prototype-unsupported-graphics-constant",
                      "Vulkan graphics prototype emission does not yet "
                      "support module constants");
    return false;
  }
  if (!vulkanGraphicsStageResourcesSupported(module, *vertex, *fragment)) {
    diagnostics.error(
        "vulkan.prototype-unsupported-graphics-stage-resource",
        vulkanGraphicsUnsupportedStageResourcesMessage(*vertex, *fragment,
                                                       module));
    return false;
  }
  const HIRFunction *vertexEntry = entryFunction(*vertex);
  const HIRFunction *fragmentEntry = entryFunction(*fragment);
  if (vertexEntry == nullptr || fragmentEntry == nullptr) {
    diagnostics.error("vulkan.prototype-missing-entry",
                      "Vulkan graphics prototype emission requires vertex and "
                      "fragment entry functions");
    return false;
  }
  if (!vulkanGraphicsEntrySignatureSupported(module, *vertex, *vertexEntry) ||
      !vulkanGraphicsEntrySignatureSupported(module, *fragment, *fragmentEntry)) {
    diagnostics.error("vulkan.prototype-unsupported-graphics-signature",
                      "Vulkan graphics prototype emission requires each stage "
                      "entry to take one struct parameter and return one "
                      "struct with scalar/vector fields; the vertex return "
                      "struct must include vec4 position or clipPosition");
    return false;
  }
  if (!vulkanGraphicsVaryingsSupported(module, *vertexEntry, *fragmentEntry)) {
    diagnostics.error("vulkan.prototype-unsupported-graphics-varying",
                      "Vulkan graphics prototype emission requires fragment "
                      "inputs to match vertex non-position outputs by name and "
                      "type");
    return false;
  }
  for (const HIRFunction &function : module.functions) {
    if (!vulkanGraphicsHelperSignatureSupported(module, function,
                                                &diagnostics) ||
        !vulkanGraphicsFunctionSupported(module, *vertex, function,
                                         &diagnostics, false, true) ||
        !vulkanGraphicsFunctionSupported(module, *fragment, function,
                                         &diagnostics, false, true)) {
      return false;
    }
  }
  auto stageHelpersSupported = [&](const HIRStage &stage,
                                   const HIRFunction &stageEntry) {
    for (const HIRFunction &function : stage.functions) {
      if (&function == &stageEntry) {
        continue;
      }
      if (!vulkanGraphicsHelperSignatureSupported(module, function,
                                                  &diagnostics) ||
          !vulkanGraphicsFunctionSupported(module, stage, function,
                                           &diagnostics, true, true)) {
        return false;
      }
    }
    return true;
  };
  if (!stageHelpersSupported(*vertex, *vertexEntry) ||
      !stageHelpersSupported(*fragment, *fragmentEntry)) {
    return false;
  }
  if (!vulkanGraphicsFunctionSupported(module, *vertex, *vertexEntry,
                                       &diagnostics) ||
      !vulkanGraphicsFunctionSupported(module, *fragment, *fragmentEntry,
                                       &diagnostics)) {
    if (!diagnostics.hasErrors()) {
      diagnostics.error(
          "vulkan.prototype-unsupported-graphics-body",
          "Vulkan graphics prototype emission currently supports declarations, "
          "assignments, struct/vector member accesses, scalar/vector "
          "constructors, simple arithmetic expressions, fragment sampler2D "
          "sampling, fixed-size fragment sampler2D/sampler descriptor arrays, "
          "direct or fixed-size fragment sampler2DShadow comparison descriptor "
          "arrays, direct fragment sampler2DArrayShadow comparison resources "
          "with optional explicit LOD, and returns");
    }
    return false;
  }
  return true;
}

std::size_t vulkanGraphicsVectorSize(std::string_view name) {
  if (name == "vec2" || name == "ivec2" || name == "uvec2" ||
      name == "bvec2") {
    return 2;
  }
  if (name == "vec3" || name == "ivec3" || name == "uvec3" ||
      name == "bvec3") {
    return 3;
  }
  if (name == "vec4" || name == "ivec4" || name == "uvec4" ||
      name == "bvec4") {
    return 4;
  }
  return 1;
}

std::string vulkanGraphicsScalarTypeName(std::string_view name) {
  if (name == "vec2" || name == "vec3" || name == "vec4") {
    return "float";
  }
  if (name == "ivec2" || name == "ivec3" || name == "ivec4") {
    return "int";
  }
  if (name == "uvec2" || name == "uvec3" || name == "uvec4") {
    return "uint";
  }
  if (name == "bvec2" || name == "bvec3" || name == "bvec4") {
    return "bool";
  }
  return std::string(name);
}

bool vulkanGraphicsIsVector(std::string_view name) {
  return vulkanGraphicsVectorSize(name) > 1;
}

HIRType vulkanGraphicsVectorComponentType(const HIRType &type) {
  return HIRType{vulkanGraphicsScalarTypeName(type.name), std::nullopt};
}

std::optional<std::size_t>
vulkanGraphicsConstructorConstituentWidth(const HIRType &type,
                                          const HIRType &componentType) {
  if (type.arraySize.has_value()) {
    return std::nullopt;
  }
  if (vulkanGraphicsTypeEquals(type, componentType)) {
    return std::size_t{1};
  }
  if (!vulkanGraphicsIsVector(type.name)) {
    return std::nullopt;
  }
  const HIRType childComponentType = vulkanGraphicsVectorComponentType(type);
  if (!vulkanGraphicsTypeEquals(childComponentType, componentType)) {
    return std::nullopt;
  }
  return vulkanGraphicsVectorSize(type.name);
}

std::optional<std::size_t>
vulkanGraphicsMatrixConstructorConstituentWidth(const HIRType &type) {
  if (isPrototypeNumericScalarType(type)) {
    return std::size_t{1};
  }
  if (!vulkanGraphicsScalarVectorTypeSupported(type) ||
      !vulkanGraphicsIsVector(type.name)) {
    return std::nullopt;
  }
  const HIRType componentType = vulkanGraphicsVectorComponentType(type);
  if (!isPrototypeNumericScalarType(componentType)) {
    return std::nullopt;
  }
  return vulkanGraphicsVectorSize(type.name);
}

bool vulkanGraphicsMatrixConstructorSupported(
    const HIRExpression &expression) {
  const std::optional<std::size_t> dimension =
      prototypeMatrixDimension(expression.type);
  if (!dimension.has_value() ||
      expression.value != baseTypeName(expression.type) ||
      expression.children.empty()) {
    return false;
  }

  if (expression.children.size() == 1) {
    const HIRType &sourceType = expression.children.front().type;
    if (vulkanGraphicsTypeEquals(sourceType, expression.type) ||
        vulkanGraphicsMatrixTypeSupported(sourceType) ||
        isPrototypeNumericScalarType(sourceType)) {
      return true;
    }
  }

  std::size_t constituentWidth = 0;
  for (const HIRExpression &child : expression.children) {
    const std::optional<std::size_t> childWidth =
        vulkanGraphicsMatrixConstructorConstituentWidth(child.type);
    if (!childWidth.has_value()) {
      return false;
    }
    constituentWidth += *childWidth;
  }
  return constituentWidth == (*dimension * *dimension);
}

bool vulkanGraphicsConstructorSupported(const HIRModule &module,
                                        const HIRStage &stage,
                                        const HIRExpression &expression,
                                        bool allowStageHelpers) {
  if (expression.children.empty()) {
    return false;
  }

  for (const HIRExpression &child : expression.children) {
    if (!vulkanGraphicsExpressionSupported(module, stage, child,
                                           allowStageHelpers)) {
      return false;
    }
  }

  if (vulkanGraphicsMatrixTypeSupported(expression.type)) {
    return vulkanGraphicsMatrixConstructorSupported(expression);
  }

  if (!vulkanGraphicsScalarVectorTypeSupported(expression.type) ||
      expression.value != expression.type.name) {
    return false;
  }

  const std::size_t targetWidth = vulkanGraphicsVectorSize(expression.type.name);
  if (targetWidth == 1) {
    return expression.children.size() == 1 &&
           vulkanGraphicsVectorSize(expression.children.front().type.name) ==
               1;
  }

  if (expression.children.size() == 1 &&
      vulkanGraphicsTypeEquals(expression.children.front().type,
                               expression.type)) {
    return true;
  }

  const HIRType componentType =
      vulkanGraphicsVectorComponentType(expression.type);
  std::size_t constituentWidth = 0;
  for (const HIRExpression &child : expression.children) {
    const std::optional<std::size_t> childWidth =
        vulkanGraphicsConstructorConstituentWidth(child.type, componentType);
    if (!childWidth.has_value()) {
      return false;
    }
    constituentWidth += *childWidth;
  }

  if (expression.children.size() == 1 && constituentWidth == 1) {
    return true;
  }
  return constituentWidth == targetWidth;
}

std::optional<std::vector<std::size_t>>
vulkanGraphicsSwizzleIndices(const HIRType &type, std::string_view member) {
  if (type.arraySize.has_value() || member.empty() || member.size() > 4) {
    return std::nullopt;
  }

  const std::size_t width = vulkanGraphicsVectorSize(type.name);
  if (width <= 1) {
    return std::nullopt;
  }

  static constexpr std::string_view sets[] = {"xyzw", "rgba", "stpq"};
  const std::string_view *selectedSet = nullptr;
  for (const std::string_view &set : sets) {
    if (set.find(member.front()) != std::string_view::npos) {
      selectedSet = &set;
      break;
    }
  }
  if (selectedSet == nullptr) {
    return std::nullopt;
  }

  std::vector<std::size_t> indices;
  indices.reserve(member.size());
  for (const char component : member) {
    const std::size_t index = selectedSet->find(component);
    if (index == std::string_view::npos || index >= width) {
      return std::nullopt;
    }
    indices.push_back(index);
  }
  return indices;
}

bool vulkanGraphicsSwizzleResultTypeSupported(
    const HIRType &baseType, const HIRType &resultType,
    const std::vector<std::size_t> &indices) {
  if (indices.empty() || resultType.arraySize.has_value()) {
    return false;
  }

  const HIRType componentType = vulkanGraphicsVectorComponentType(baseType);
  if (indices.size() == 1) {
    return vulkanGraphicsTypeEquals(resultType, componentType);
  }

  return vulkanGraphicsVectorSize(resultType.name) == indices.size() &&
         vulkanGraphicsScalarTypeName(resultType.name) == componentType.name;
}

std::string vulkanGraphicsStorageClassName(std::string_view storageClass) {
  return std::string(storageClass);
}

class VulkanGraphicsSPIRVBuilder {
public:
  VulkanGraphicsSPIRVBuilder(const HIRModule &module,
                             DiagnosticEngine &diagnostics)
      : module_(module), diagnostics_(diagnostics),
        layoutContext_(module.structs, module.constants) {}

  std::string render() {
    if (!vulkanGraphicsPrototypeSupported(module_, diagnostics_)) {
      return "";
    }
    const HIRStage *vertexStage = nullptr;
    const HIRStage *fragmentStage = nullptr;
    (void)vulkanGraphicsStagePair(module_, vertexStage, fragmentStage);
    const HIRFunction &vertexEntry = *entryFunction(*vertexStage);
    const HIRFunction &fragmentEntry = *entryFunction(*fragmentStage);
    const HIRStruct &vertexInput = *vulkanGraphicsStructType(
        module_, vertexEntry.parameters.front().type);
    const HIRStruct &vertexOutput =
        *vulkanGraphicsStructType(module_, vertexEntry.returnType);
    const HIRStruct &fragmentInput = *vulkanGraphicsStructType(
        module_, fragmentEntry.parameters.front().type);
    const HIRStruct &fragmentOutput =
        *vulkanGraphicsStructType(module_, fragmentEntry.returnType);
    const HIRField &position = *vulkanGraphicsPositionField(vertexOutput);

    declareVertexInterface(*vertexStage, vertexInput, fragmentInput, position);
    declareFragmentInterface(*fragmentStage, fragmentInput, fragmentOutput);
    registerFunctionSignatures(*vertexStage, vertexEntry, *fragmentStage,
                               fragmentEntry);
    if (!emitHelperFunctions(*vertexStage, vertexEntry, *fragmentStage,
                             fragmentEntry) ||
        !emitEntryFunction(*vertexStage, vertexEntry, vertexInput,
                           vertexOutput) ||
        !emitEntryFunction(*fragmentStage, fragmentEntry, fragmentInput,
                           fragmentOutput)) {
      return "";
    }

    std::ostringstream out;
    out << "; SPIR-V\n";
    out << "; Version: 1.0\n";
    out << "; Generator: CrossGL Vulkan graphics prototype\n";
    out << "; Bound: " << (nextId_ + 1) << "\n";
    out << "; Schema: 0\n";
    out << "OpCapability Shader\n";
    if (usesRuntimeDescriptorArray_) {
      out << "OpCapability RuntimeDescriptorArrayEXT\n";
    }
    if (usesNonUniformDescriptorIndex_) {
      out << "OpCapability ShaderNonUniformEXT\n";
      if (usesSampledImageArrayNonUniformIndexing_) {
        out << "OpCapability SampledImageArrayNonUniformIndexingEXT\n";
      }
    }
    if (usesRuntimeDescriptorArray_ || usesNonUniformDescriptorIndex_) {
      out << "OpExtension \"SPV_EXT_descriptor_indexing\"\n";
    }
    out << imports_.str();
    out << "OpMemoryModel Logical GLSL450\n";
    out << entryPoints_.str();
    out << "OpExecutionMode " << fragmentFunctionId_ << " OriginUpperLeft\n";
    out << "OpSource GLSL 450\n";
    out << names_.str();
    out << decorations_.str();
    out << types_.str();
    out << globals_.str();
    out << functions_.str();
    return out.str();
  }

private:
  struct PointerInfo {
    HIRType type;
    std::string pointerTypeId;
    std::string pointerId;
    std::string storageClass = "Function";
    HIRResourceKind kind = HIRResourceKind::Value;
    bool nonUniformDescriptor = false;
  };

  struct EmitValue {
    HIRType type;
    std::string id;
    bool nonUniformDescriptor = false;
  };

  struct FunctionContext {
    const HIRStage *stage = nullptr;
    const HIRFunction *function = nullptr;
    const HIRStruct *inputStruct = nullptr;
    const HIRStruct *outputStruct = nullptr;
    const std::unordered_map<std::string, PointerInfo> *uniforms = nullptr;
    const std::unordered_map<std::string, PointerInfo> *descriptors = nullptr;
    std::unordered_map<std::string, PointerInfo> locals;
    std::ostringstream variableLines;
    bool entry = false;
  };

  struct GraphicsFunctionInfo {
    const HIRFunction *function = nullptr;
    const HIRStage *stage = nullptr;
    std::string id;
    HIRType returnType;
    std::vector<HIRType> parameterTypes;
    std::string functionTypeId;
    bool entry = false;
  };

  std::string freshId() {
    return "%g" + std::to_string(nextId_++);
  }

  std::string ensureGLSLStd450Import() {
    if (!glslStd450ImportId_.empty()) {
      return glslStd450ImportId_;
    }
    glslStd450ImportId_ = freshId();
    imports_ << glslStd450ImportId_ << " = OpExtInstImport \"GLSL.std.450\"\n";
    return glslStd450ImportId_;
  }

  void requireSampledImageNonUniformDescriptorIndex() {
    usesNonUniformDescriptorIndex_ = true;
    usesSampledImageArrayNonUniformIndexing_ = true;
  }

  void decorateNonUniform(const std::string &id) {
    if (id.empty() || !nonUniformDecorationIds_.insert(id).second) {
      return;
    }
    decorations_ << "OpDecorate " << id << " NonUniformEXT\n";
  }

  std::string typeKey(const HIRType &type) const {
    return type.name + (type.arraySize.has_value() ? "[" + *type.arraySize + "]"
                                                   : "");
  }

  std::string typeId(const HIRType &type) {
    const std::string key = typeKey(type);
    if (const auto found = typeIds_.find(key); found != typeIds_.end()) {
      return found->second;
    }

    std::string id = freshId();
    typeIds_[key] = id;
    if (type.name == "void") {
      types_ << id << " = OpTypeVoid\n";
    } else if (type.name == "bool") {
      types_ << id << " = OpTypeBool\n";
    } else if (type.name == "int") {
      types_ << id << " = OpTypeInt 32 1\n";
    } else if (type.name == "uint") {
      types_ << id << " = OpTypeInt 32 0\n";
    } else if (type.name == "float") {
      types_ << id << " = OpTypeFloat 32\n";
    } else if (vulkanGraphicsIsVector(type.name)) {
      const HIRType scalar{vulkanGraphicsScalarTypeName(type.name),
                           std::nullopt};
      const std::string scalarId = typeId(scalar);
      types_ << id << " = OpTypeVector " << scalarId << " "
             << vulkanGraphicsVectorSize(type.name) << "\n";
    } else if (vulkanGraphicsMatrixTypeSupported(type)) {
      const std::string columnType = typeId(prototypeMatrixColumnType(type));
      types_ << id << " = OpTypeMatrix " << columnType << " "
             << *prototypeMatrixDimension(type) << "\n";
    } else if (const HIRStruct *structure =
                   vulkanGraphicsStructType(module_, type)) {
      std::vector<std::string> memberTypes;
      memberTypes.reserve(structure->fields.size());
      for (const HIRField &field : structure->fields) {
        memberTypes.push_back(typeId(field.type));
      }
      types_ << id << " = OpTypeStruct";
      for (const std::string &memberType : memberTypes) {
        types_ << " " << memberType;
      }
      types_ << "\n";
      names_ << "OpName " << id << " \"" << structure->name << "\"\n";
      for (std::size_t index = 0; index < structure->fields.size(); ++index) {
        names_ << "OpMemberName " << id << " " << index << " \""
               << structure->fields[index].name << "\"\n";
      }
    } else {
      diagnostics_.error("vulkan.prototype-internal-type",
                         "unsupported Vulkan graphics SPIR-V type '" +
                             type.name + "'");
    }
    return id;
  }

  std::string pointerTypeId(std::string_view storageClass,
                            const HIRType &type) {
    const std::string key = std::string(storageClass) + "|" + typeKey(type);
    if (const auto found = pointerTypeIds_.find(key);
        found != pointerTypeIds_.end()) {
      return found->second;
    }
    const std::string id = freshId();
    pointerTypeIds_[key] = id;
    const std::string pointeeType = typeId(type);
    types_ << id << " = OpTypePointer "
           << vulkanGraphicsStorageClassName(storageClass) << " "
           << pointeeType << "\n";
    return id;
  }

  std::string uniformBlockTypeId(const HIRType &type) {
    const std::string key = typeKey(type);
    if (const auto found = uniformBlockTypeIds_.find(key);
        found != uniformBlockTypeIds_.end()) {
      return found->second;
    }

    const HIRStruct *structure = vulkanGraphicsStructType(module_, type);
    if (structure == nullptr) {
      diagnostics_.error("vulkan.prototype-internal-type",
                         "unsupported Vulkan graphics uniform block type '" +
                             type.name + "'");
      return typeId(type);
    }

    std::vector<std::string> memberTypes;
    memberTypes.reserve(structure->fields.size());
    for (const HIRField &field : structure->fields) {
      memberTypes.push_back(typeId(field.type));
    }

    const std::string id = freshId();
    uniformBlockTypeIds_[key] = id;
    const std::optional<StorageTypeLayout> layout =
        computeStorageTypeLayout(type, StorageLayoutKind::Std430,
                                 layoutContext_, false);
    if (!layout.has_value()) {
      diagnostics_.error("vulkan.prototype-internal-type",
                         "Vulkan graphics prototype cannot compute uniform "
                         "buffer layout for '" +
                             type.name + "'");
      return id;
    }
    for (const StorageFieldLayout &field : layout->fields) {
      decorations_ << "OpMemberDecorate " << id << " " << field.index
                   << " Offset " << field.offsetBytes << "\n";
    }
    decorations_ << "OpDecorate " << id << " Block\n";
    types_ << id << " = OpTypeStruct";
    for (const std::string &memberType : memberTypes) {
      types_ << " " << memberType;
    }
    types_ << "\n";
    names_ << "OpName " << id << " \"" << structure->name << "\"\n";
    for (std::size_t index = 0; index < structure->fields.size(); ++index) {
      names_ << "OpMemberName " << id << " " << index << " \""
             << structure->fields[index].name << "\"\n";
    }
    return id;
  }

  std::string uniformBlockPointerTypeId(const HIRType &type) {
    const std::string key = "UniformBlock|" + typeKey(type);
    if (const auto found = pointerTypeIds_.find(key);
        found != pointerTypeIds_.end()) {
      return found->second;
    }
    const std::string id = freshId();
    pointerTypeIds_[key] = id;
    const std::string blockType = uniformBlockTypeId(type);
    types_ << id << " = OpTypePointer Uniform " << blockType << "\n";
    return id;
  }

  std::string graphicsImageTypeId(const HIRType &type) {
    const HIRType elementType = arrayElementType(type);
    const std::string key = "Image|" + typeKey(elementType);
    if (const auto found = imageTypeIds_.find(key); found != imageTypeIds_.end()) {
      return found->second;
    }
    const std::string sampledType = typeId(HIRType{"float", std::nullopt});
    const bool depthComparison = isComparisonTextureType(elementType.name);
    const bool arrayed = isArrayTextureType(elementType.name);
    const std::string id = freshId();
    imageTypeIds_[key] = id;
    types_ << id << " = OpTypeImage " << sampledType << " "
           << textureDimension(elementType.name) << " "
           << (depthComparison ? "1" : "0") << " " << (arrayed ? "1" : "0")
           << " 0 1 Unknown\n";
    return id;
  }

  std::string samplerTypeId() {
    if (!samplerTypeId_.empty()) {
      return samplerTypeId_;
    }
    samplerTypeId_ = freshId();
    types_ << samplerTypeId_ << " = OpTypeSampler\n";
    return samplerTypeId_;
  }

  std::string sampledImageTypeId(const HIRType &textureType) {
    const HIRType textureElementType = arrayElementType(textureType);
    const std::string key = "SampledImage|" + typeKey(textureElementType);
    if (const auto found = sampledImageTypeIds_.find(key);
        found != sampledImageTypeIds_.end()) {
      return found->second;
    }
    const std::string imageType = graphicsImageTypeId(textureElementType);
    const std::string id = freshId();
    sampledImageTypeIds_[key] = id;
    types_ << id << " = OpTypeSampledImage " << imageType << "\n";
    return id;
  }

  std::string descriptorArrayTypeId(const HIRType &resourceType,
                                    const std::string &elementTypeId,
                                    std::string_view prefix) {
    if (!resourceType.arraySize.has_value()) {
      return elementTypeId;
    }
    const std::string key = std::string(prefix) + "|" + typeKey(resourceType) +
                            "|" + elementTypeId;
    if (const auto found = descriptorArrayTypeIds_.find(key);
        found != descriptorArrayTypeIds_.end()) {
      return found->second;
    }
    if (resourceType.arraySize->empty()) {
      const std::string id = freshId();
      descriptorArrayTypeIds_[key] = id;
      usesRuntimeDescriptorArray_ = true;
      types_ << id << " = OpTypeRuntimeArray " << elementTypeId << "\n";
      return id;
    }
    const StorageLayoutContext layoutContext(module_.structs,
                                             module_.constants);
    const std::optional<std::size_t> elementCount =
        prototypeArrayElementCount(resourceType, layoutContext);
    if (!elementCount.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-stage-resource",
                         "Vulkan graphics descriptor arrays require "
                         "fixed-size numeric resource array sizes, got '" +
                             formatType(resourceType) + "'");
      return "";
    }
    const std::string id = freshId();
    descriptorArrayTypeIds_[key] = id;
    const std::string lengthId =
        uintConstant(static_cast<unsigned int>(*elementCount));
    types_ << id << " = OpTypeArray " << elementTypeId << " " << lengthId
           << "\n";
    return id;
  }

  std::string resourceValueTypeId(const HIRResource &resource) {
    if (resource.kind == HIRResourceKind::Texture) {
      const HIRType elementType = arrayElementType(resource.type);
      return descriptorArrayTypeId(resource.type, graphicsImageTypeId(elementType),
                                   "image");
    }
    if (resource.kind == HIRResourceKind::Sampler) {
      return descriptorArrayTypeId(resource.type, samplerTypeId(), "sampler");
    }
    return typeId(resource.type);
  }

  std::string uniformConstantPointerTypeId(const HIRResource &resource) {
    const std::string valueType = resourceValueTypeId(resource);
    const std::string key = "UniformConstant|" + resourceKindLabel(resource.kind) +
                            "|" + typeKey(resource.type) + "|" + valueType;
    if (const auto found = pointerTypeIds_.find(key);
        found != pointerTypeIds_.end()) {
      return found->second;
    }
    const std::string id = freshId();
    pointerTypeIds_[key] = id;
    types_ << id << " = OpTypePointer UniformConstant " << valueType << "\n";
    return id;
  }

  std::string uniformConstantElementPointerTypeId(HIRResourceKind kind,
                                                  const HIRType &elementType) {
    std::string valueType;
    std::string keyPrefix;
    if (kind == HIRResourceKind::Texture) {
      valueType = graphicsImageTypeId(elementType);
      keyPrefix = "image";
    } else if (kind == HIRResourceKind::Sampler) {
      valueType = samplerTypeId();
      keyPrefix = "sampler";
    } else {
      return "";
    }

    const std::string key =
        "UniformConstantElement|" + keyPrefix + "|" + typeKey(elementType) +
        "|" + valueType;
    if (const auto found = pointerTypeIds_.find(key);
        found != pointerTypeIds_.end()) {
      return found->second;
    }
    const std::string id = freshId();
    pointerTypeIds_[key] = id;
    types_ << id << " = OpTypePointer UniformConstant " << valueType << "\n";
    return id;
  }

  std::string functionTypeId(const HIRType &returnType,
                             const std::vector<HIRType> &parameterTypes) {
    std::string key = typeKey(returnType) + "(";
    for (const HIRType &parameterType : parameterTypes) {
      key += typeKey(parameterType) + ";";
    }
    key += ")";
    if (const auto found = functionTypeIds_.find(key);
        found != functionTypeIds_.end()) {
      return found->second;
    }

    std::vector<std::string> parameterTypeIds;
    parameterTypeIds.reserve(parameterTypes.size());
    for (const HIRType &parameterType : parameterTypes) {
      parameterTypeIds.push_back(typeId(parameterType));
    }

    const std::string returnTypeId = typeId(returnType);
    const std::string id = freshId();
    functionTypeIds_[key] = id;
    types_ << id << " = OpTypeFunction " << returnTypeId;
    for (const std::string &parameterTypeId : parameterTypeIds) {
      types_ << " " << parameterTypeId;
    }
    types_ << "\n";
    return id;
  }

  std::string intConstant(int value) {
    const std::string key = std::to_string(value);
    if (const auto found = intConstants_.find(key);
        found != intConstants_.end()) {
      return found->second;
    }
    const std::string id = freshId();
    intConstants_[key] = id;
    const std::string intType = typeId(HIRType{"int", std::nullopt});
    types_ << id << " = OpConstant " << intType << " " << value << "\n";
    return id;
  }

  std::string uintConstant(unsigned int value) {
    const std::string key = std::to_string(value);
    if (const auto found = uintConstants_.find(key);
        found != uintConstants_.end()) {
      return found->second;
    }
    const std::string id = freshId();
    uintConstants_[key] = id;
    const std::string uintType = typeId(HIRType{"uint", std::nullopt});
    types_ << id << " = OpConstant " << uintType << " " << value << "\n";
    return id;
  }

  std::string floatConstant(std::string_view value) {
    const std::string key = "float|" + std::string(value);
    if (const auto found = literalConstants_.find(key);
        found != literalConstants_.end()) {
      return found->second;
    }
    const std::string id = freshId();
    literalConstants_[key] = id;
    types_ << id << " = OpConstant " << typeId(HIRType{"float", std::nullopt})
           << " " << value << "\n";
    return id;
  }

  std::string constantForLiteral(const HIRExpression &expression) {
    const std::string key = typeKey(expression.type) + "|" + expression.value;
    if (const auto found = literalConstants_.find(key);
        found != literalConstants_.end()) {
      return found->second;
    }
    const std::string id = freshId();
    literalConstants_[key] = id;
    const std::string literalType = typeId(expression.type);
    if (expression.type.name == "bool") {
      types_ << id << " = "
             << (expression.value == "true" ? "OpConstantTrue "
                                             : "OpConstantFalse ")
             << literalType << "\n";
    } else {
      types_ << id << " = OpConstant " << literalType << " "
             << expression.value << "\n";
    }
    return id;
  }

  PointerInfo declareGlobal(std::string_view storageClass, const HIRType &type,
                            std::string_view debugName) {
    PointerInfo info{type, pointerTypeId(storageClass, type), freshId(),
                     std::string(storageClass), HIRResourceKind::Value};
    globals_ << info.pointerId << " = OpVariable " << info.pointerTypeId
             << " " << storageClass << "\n";
    names_ << "OpName " << info.pointerId << " \"" << debugName << "\"\n";
    return info;
  }

  PointerInfo declareUniformResource(const HIRStage &stage,
                                     const HIRResource &resource) {
    PointerInfo info{resource.type, uniformBlockPointerTypeId(resource.type),
                     "%resource_" + sanitizeIdFragment(stage.stage) + "_" +
                         sanitizeIdFragment(resource.name),
                     "Uniform", HIRResourceKind::Uniform};
    globals_ << info.pointerId << " = OpVariable " << info.pointerTypeId
             << " Uniform\n";
    names_ << "OpName " << info.pointerId << " \"" << resource.name
           << "\"\n";
    decorations_ << "OpDecorate " << info.pointerId << " DescriptorSet "
                 << resource.set << "\n";
    decorations_ << "OpDecorate " << info.pointerId << " Binding "
                 << resource.binding << "\n";
    return info;
  }

  PointerInfo declareUniformConstantResource(const HIRStage &stage,
                                             const HIRResource &resource) {
    PointerInfo info{resource.type, uniformConstantPointerTypeId(resource),
                     "%resource_" + sanitizeIdFragment(stage.stage) + "_" +
                         sanitizeIdFragment(resource.name),
                     "UniformConstant", resource.kind};
    globals_ << info.pointerId << " = OpVariable " << info.pointerTypeId
             << " UniformConstant\n";
    names_ << "OpName " << info.pointerId << " \"" << resource.name
           << "\"\n";
    decorations_ << "OpDecorate " << info.pointerId << " DescriptorSet "
                 << resource.set << "\n";
    decorations_ << "OpDecorate " << info.pointerId << " Binding "
                 << resource.binding << "\n";
    return info;
  }

  void declareStageResources(
      const HIRStage &stage, std::vector<std::string> &interfaceIds) {
    std::unordered_map<std::string, PointerInfo> &uniforms =
      stage.stage == "vertex" ? vertexUniforms_ : fragmentUniforms_;
    std::unordered_map<std::string, PointerInfo> &descriptors =
        stage.stage == "vertex" ? vertexDescriptors_ : fragmentDescriptors_;
    for (const HIRResource &resource : stage.resources) {
      if (!vulkanGraphicsUniformResourceSupported(module_, resource)) {
        if (!vulkanGraphicsStageResourceSupported(module_, stage, resource)) {
          continue;
        }
        PointerInfo descriptor = declareUniformConstantResource(stage, resource);
        interfaceIds.push_back(descriptor.pointerId);
        descriptors[resource.name] = std::move(descriptor);
        continue;
      }
      PointerInfo uniform = declareUniformResource(stage, resource);
      interfaceIds.push_back(uniform.pointerId);
      uniforms[resource.name] = std::move(uniform);
    }
  }

  void declareVertexInterface(const HIRStage &vertexStage,
                              const HIRStruct &vertexInput,
                              const HIRStruct &fragmentInput,
                              const HIRField &position) {
    std::vector<std::string> interfaceIds;
    for (std::size_t index = 0; index < vertexInput.fields.size(); ++index) {
      const HIRField &field = vertexInput.fields[index];
      PointerInfo variable = declareGlobal(
          "Input", field.type, "crossgl_attr_" + field.name);
      vertexInputs_[field.name] = variable;
      decorations_ << "OpDecorate " << variable.pointerId << " Location "
                   << index << "\n";
      interfaceIds.push_back(variable.pointerId);
    }
    for (std::size_t index = 0; index < fragmentInput.fields.size(); ++index) {
      const HIRField &field = fragmentInput.fields[index];
      PointerInfo variable = declareGlobal(
          "Output", field.type, "crossgl_varying_" + field.name);
      vertexOutputs_[field.name] = variable;
      decorations_ << "OpDecorate " << variable.pointerId << " Location "
                   << index << "\n";
      interfaceIds.push_back(variable.pointerId);
    }
    vertexPosition_ =
        declareGlobal("Output", position.type, "crossgl_position");
    decorations_ << "OpDecorate " << vertexPosition_.pointerId
                 << " BuiltIn Position\n";
    interfaceIds.push_back(vertexPosition_.pointerId);
    declareStageResources(vertexStage, interfaceIds);

    vertexFunctionId_ = freshId();
    entryPoints_ << "OpEntryPoint Vertex " << vertexFunctionId_
                 << " \"vertex_main\"";
    for (const std::string &id : interfaceIds) {
      entryPoints_ << " " << id;
    }
    entryPoints_ << "\n";
  }

  void declareFragmentInterface(const HIRStage &fragmentStage,
                                const HIRStruct &fragmentInput,
                                const HIRStruct &fragmentOutput) {
    std::vector<std::string> interfaceIds;
    for (std::size_t index = 0; index < fragmentInput.fields.size(); ++index) {
      const HIRField &field = fragmentInput.fields[index];
      PointerInfo variable = declareGlobal(
          "Input", field.type, "crossgl_varying_" + field.name);
      fragmentInputs_[field.name] = variable;
      decorations_ << "OpDecorate " << variable.pointerId << " Location "
                   << index << "\n";
      interfaceIds.push_back(variable.pointerId);
    }
    for (std::size_t index = 0; index < fragmentOutput.fields.size(); ++index) {
      const HIRField &field = fragmentOutput.fields[index];
      PointerInfo variable = declareGlobal(
          "Output", field.type, "crossgl_out_" + field.name);
      fragmentOutputs_[field.name] = variable;
      decorations_ << "OpDecorate " << variable.pointerId << " Location "
                   << index << "\n";
      interfaceIds.push_back(variable.pointerId);
    }
    declareStageResources(fragmentStage, interfaceIds);

    fragmentFunctionId_ = freshId();
    entryPoints_ << "OpEntryPoint Fragment " << fragmentFunctionId_
                 << " \"fragment_main\"";
    for (const std::string &id : interfaceIds) {
      entryPoints_ << " " << id;
    }
    entryPoints_ << "\n";
  }

  std::string functionKey(const HIRStage *stage,
                          std::string_view functionName) const {
    if (stage == nullptr) {
      return "module::" + std::string(functionName);
    }
    return stage->stage + "::" + std::string(functionName);
  }

  std::string helperFunctionId(const HIRStage *stage,
                               std::string_view functionName) const {
    if (stage == nullptr) {
      return "%func_" + sanitizeIdFragment(functionName);
    }
    return "%func_" + sanitizeIdFragment(stage->stage) + "_" +
           sanitizeIdFragment(functionName);
  }

  void registerFunctionSignature(const HIRStage *stage,
                                 const HIRFunction &function, bool entry,
                                 std::string id) {
    GraphicsFunctionInfo info;
    info.function = &function;
    info.stage = stage;
    info.id = std::move(id);
    info.entry = entry;
    info.returnType = entry ? HIRType{"void", std::nullopt}
                            : function.returnType;
    if (!entry) {
      info.parameterTypes.reserve(function.parameters.size());
      for (const HIRParameter &parameter : function.parameters) {
        info.parameterTypes.push_back(parameter.type);
      }
    }
    info.functionTypeId = functionTypeId(info.returnType, info.parameterTypes);
    functionsByKey_[functionKey(stage, function.name)] = std::move(info);
  }

  void registerFunctionSignatures(const HIRStage &vertexStage,
                                  const HIRFunction &vertexEntry,
                                  const HIRStage &fragmentStage,
                                  const HIRFunction &fragmentEntry) {
    for (const HIRFunction &function : module_.functions) {
      registerFunctionSignature(nullptr, function, false,
                                helperFunctionId(nullptr, function.name));
    }
    for (const HIRFunction &function : vertexStage.functions) {
      const bool entry = &function == &vertexEntry;
      registerFunctionSignature(&vertexStage, function, entry,
                                entry ? vertexFunctionId_
                                      : helperFunctionId(&vertexStage,
                                                         function.name));
    }
    for (const HIRFunction &function : fragmentStage.functions) {
      const bool entry = &function == &fragmentEntry;
      registerFunctionSignature(&fragmentStage, function, entry,
                                entry ? fragmentFunctionId_
                                      : helperFunctionId(&fragmentStage,
                                                         function.name));
    }
  }

  const GraphicsFunctionInfo *
  helperFunctionInfo(const FunctionContext &context,
                     std::string_view functionName) const {
    if (context.stage != nullptr) {
      if (const auto found =
              functionsByKey_.find(functionKey(context.stage, functionName));
          found != functionsByKey_.end() && !found->second.entry) {
        return &found->second;
      }
    }
    if (const auto found =
            functionsByKey_.find(functionKey(nullptr, functionName));
        found != functionsByKey_.end() && !found->second.entry) {
      return &found->second;
    }
    return nullptr;
  }

  void collectDeclarations(FunctionContext &context,
                           const std::vector<HIRStatement> &statements) {
    for (const HIRStatement &statement : statements) {
      if (statement.kind == HIRStatementKind::Declaration) {
        declareLocal(context, statement.declaredType, statement.name);
      }
      if (statement.kind == HIRStatementKind::Block) {
        collectDeclarations(context, statement.body);
      }
      if (statement.kind == HIRStatementKind::If) {
        collectDeclarations(context, statement.body);
        collectDeclarations(context, statement.elseBody);
      }
      if (statement.kind == HIRStatementKind::For) {
        collectDeclarations(context, statement.initializer);
        collectDeclarations(context, statement.body);
      }
    }
  }

  PointerInfo declareLocal(FunctionContext &context, const HIRType &type,
                           std::string_view name) {
    PointerInfo info{type, pointerTypeId("Function", type), freshId(),
                     "Function", HIRResourceKind::Value};
    context.locals[std::string(name)] = info;
    context.variableLines << info.pointerId << " = OpVariable "
                          << info.pointerTypeId << " Function\n";
    names_ << "OpName " << info.pointerId << " \"" << name << "\"\n";
    return info;
  }

  void configureStageContext(FunctionContext &context, const HIRStage *stage) {
    context.stage = stage;
    if (stage == nullptr) {
      return;
    }
    context.uniforms =
        stage->stage == "vertex" ? &vertexUniforms_ : &fragmentUniforms_;
    context.descriptors =
        stage->stage == "vertex" ? &vertexDescriptors_ : &fragmentDescriptors_;
  }

  bool emitEntryFunction(const HIRStage &stage, const HIRFunction &function,
                         const HIRStruct &inputStruct,
                         const HIRStruct &outputStruct) {
    FunctionContext context;
    configureStageContext(context, &stage);
    context.function = &function;
    context.inputStruct = &inputStruct;
    context.outputStruct = &outputStruct;
    context.entry = true;
    declareLocal(context, function.parameters.front().type,
                 function.parameters.front().name);
    collectDeclarations(context, function.body);

    const std::string functionId =
        stage.stage == "vertex" ? vertexFunctionId_ : fragmentFunctionId_;
    const auto functionInfo = functionsByKey_.find(functionKey(&stage,
                                                               function.name));
    if (functionInfo == functionsByKey_.end()) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-helper",
                         "Vulkan graphics prototype cannot resolve entry "
                         "function '" +
                             function.name + "'");
      return false;
    }
    names_ << "OpName " << functionId << " \"" << stage.stage << "_main\"\n";
    functions_ << functionId << " = OpFunction "
               << typeId(HIRType{"void", std::nullopt}) << " None "
               << functionInfo->second.functionTypeId << "\n";
    functions_ << freshId() << " = OpLabel\n";
    functions_ << context.variableLines.str();
    emitInputStructStores(context);
    bool emittedTerminator = false;
    for (const HIRStatement &statement : function.body) {
      if (emittedTerminator) {
        break;
      }
      emittedTerminator = emitStatement(context, statement);
    }
    if (!emittedTerminator) {
      functions_ << "OpReturn\n";
    }
    functions_ << "OpFunctionEnd\n";
    return !diagnostics_.hasErrors();
  }

  bool emitHelperFunction(const HIRStage *stage, const HIRFunction &function) {
    const auto functionInfo =
        functionsByKey_.find(functionKey(stage, function.name));
    if (functionInfo == functionsByKey_.end()) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-helper",
                         "Vulkan graphics prototype cannot resolve helper "
                         "function '" +
                             function.name + "'");
      return false;
    }

    FunctionContext context;
    configureStageContext(context, stage);
    context.function = &function;

    std::ostringstream parameterLines;
    std::vector<std::pair<PointerInfo, std::string>> parameterStores;
    parameterStores.reserve(function.parameters.size());
    for (const HIRParameter &parameter : function.parameters) {
      PointerInfo local = declareLocal(context, parameter.type, parameter.name);
      const std::string parameterId = freshId();
      parameterLines << parameterId << " = OpFunctionParameter "
                     << typeId(parameter.type) << "\n";
      names_ << "OpName " << parameterId << " \"" << parameter.name
             << "\"\n";
      parameterStores.push_back({std::move(local), parameterId});
    }
    collectDeclarations(context, function.body);

    names_ << "OpName " << functionInfo->second.id << " \""
           << function.name << "\"\n";
    functions_ << functionInfo->second.id << " = OpFunction "
               << typeId(function.returnType) << " None "
               << functionInfo->second.functionTypeId << "\n";
    functions_ << parameterLines.str();
    functions_ << freshId() << " = OpLabel\n";
    functions_ << context.variableLines.str();
    for (const auto &store : parameterStores) {
      functions_ << "OpStore " << store.first.pointerId << " " << store.second
                 << "\n";
    }

    bool emittedTerminator = false;
    for (const HIRStatement &statement : function.body) {
      if (emittedTerminator) {
        break;
      }
      emittedTerminator = emitStatement(context, statement);
    }
    if (!emittedTerminator) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-helper",
                         "Vulkan graphics prototype helper function '" +
                             function.name +
                             "' requires an explicit final return");
      functions_ << "OpUnreachable\n";
    }
    functions_ << "OpFunctionEnd\n";
    return !diagnostics_.hasErrors();
  }

  bool emitHelperFunctions(const HIRStage &vertexStage,
                           const HIRFunction &vertexEntry,
                           const HIRStage &fragmentStage,
                           const HIRFunction &fragmentEntry) {
    for (const HIRFunction &function : module_.functions) {
      if (!emitHelperFunction(nullptr, function)) {
        return false;
      }
    }
    for (const HIRFunction &function : vertexStage.functions) {
      if (&function != &vertexEntry && !emitHelperFunction(&vertexStage,
                                                           function)) {
        return false;
      }
    }
    for (const HIRFunction &function : fragmentStage.functions) {
      if (&function != &fragmentEntry &&
          !emitHelperFunction(&fragmentStage, function)) {
        return false;
      }
    }
    return true;
  }

  void emitInputStructStores(FunctionContext &context) {
    const HIRParameter &parameter = context.function->parameters.front();
    const PointerInfo &inputVariable = context.locals[parameter.name];
    for (std::size_t index = 0; index < context.inputStruct->fields.size();
         ++index) {
      const HIRField &field = context.inputStruct->fields[index];
      const PointerInfo *source = nullptr;
      if (context.stage->stage == "vertex") {
        source = &vertexInputs_.at(field.name);
      } else {
        source = &fragmentInputs_.at(field.name);
      }
      const EmitValue loaded = emitLoad(*source);
      const std::string targetPointer =
          emitStructFieldPointer(inputVariable, *context.inputStruct, index);
      functions_ << "OpStore " << targetPointer << " " << loaded.id << "\n";
    }
  }

  EmitValue emitLoad(const PointerInfo &pointer) {
    const std::string id = freshId();
    std::string valueType;
    if (pointer.kind == HIRResourceKind::Texture) {
      valueType = graphicsImageTypeId(pointer.type);
    } else if (pointer.kind == HIRResourceKind::Sampler) {
      valueType = samplerTypeId();
    } else {
      valueType = typeId(pointer.type);
    }
    functions_ << id << " = OpLoad " << valueType << " " << pointer.pointerId
               << "\n";
    if (pointer.nonUniformDescriptor) {
      decorateNonUniform(id);
    }
    return EmitValue{pointer.type, id, pointer.nonUniformDescriptor};
  }

  std::string emitStructFieldPointer(const PointerInfo &base,
                                     const HIRStruct &structure,
                                     std::size_t fieldIndex) {
    const HIRType &fieldType = structure.fields[fieldIndex].type;
    const std::string id = freshId();
    functions_ << id << " = OpAccessChain "
               << pointerTypeId(base.storageClass, fieldType) << " "
               << base.pointerId << " " << intConstant(static_cast<int>(fieldIndex))
               << "\n";
    return id;
  }

  std::optional<PointerInfo> emitAccessPointer(FunctionContext &context,
                                               const HIRExpression &expression) {
    if (expression.kind == HIRExpressionKind::Identifier) {
      if (const auto found = context.locals.find(expression.value);
          found != context.locals.end()) {
        return found->second;
      }
      if (context.uniforms != nullptr) {
        if (const auto found = context.uniforms->find(expression.value);
            found != context.uniforms->end()) {
          return found->second;
        }
      }
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "unknown Vulkan graphics local '" + expression.value +
                             "'");
      return std::nullopt;
    }
    if (expression.kind == HIRExpressionKind::MemberAccess &&
        expression.children.size() == 1) {
      std::optional<PointerInfo> base =
          emitAccessPointer(context, expression.children.front());
      if (!base.has_value()) {
        return std::nullopt;
      }
      const HIRStruct *structure = vulkanGraphicsStructType(module_, base->type);
      if (structure == nullptr) {
        return std::nullopt;
      }
      const std::optional<std::size_t> fieldIndex =
          vulkanGraphicsFieldIndex(*structure, expression.value);
      if (!fieldIndex.has_value()) {
        return std::nullopt;
      }
      const HIRType &fieldType = structure->fields[*fieldIndex].type;
      PointerInfo result{fieldType,
                         pointerTypeId(base->storageClass, fieldType),
                         freshId(), base->storageClass};
      functions_ << result.pointerId << " = OpAccessChain "
                 << result.pointerTypeId << " " << base->pointerId << " "
                 << intConstant(static_cast<int>(*fieldIndex)) << "\n";
      return result;
    }
    return std::nullopt;
  }

  bool emitBreakStatement() {
    if (loopLabels_.empty()) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "Vulkan graphics prototype break statements are "
                         "supported only inside structured loop bodies");
      return false;
    }
    functions_ << "OpBranch " << loopLabels_.back().mergeLabel << "\n";
    return true;
  }

  bool emitContinueStatement() {
    if (loopLabels_.empty()) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "Vulkan graphics prototype continue statements are "
                         "supported only inside structured loop bodies");
      return false;
    }
    functions_ << "OpBranch " << loopLabels_.back().continueLabel << "\n";
    return true;
  }

  bool emitReturnStatement(FunctionContext &context,
                           const HIRStatement &statement) {
    if (context.entry) {
      emitReturnValue(context, statement.value);
      functions_ << "OpReturn\n";
      return true;
    }

    if (statement.value.kind == HIRExpressionKind::Empty) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-helper",
                         "Vulkan graphics prototype helper functions require "
                         "value returns");
      functions_ << "OpReturn\n";
      return true;
    }

    const EmitValue value = emitExpression(context, statement.value);
    if (!vulkanGraphicsTypeEquals(value.type, context.function->returnType)) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-helper",
                         "Vulkan graphics prototype helper function '" +
                             context.function->name +
                             "' return type does not match its signature");
    }
    functions_ << "OpReturnValue " << value.id << "\n";
    return true;
  }

  bool emitStatement(FunctionContext &context, const HIRStatement &statement) {
    switch (statement.kind) {
    case HIRStatementKind::Declaration:
      if (statement.value.kind != HIRExpressionKind::Empty) {
        const auto local = context.locals.find(statement.name);
        const EmitValue value = emitExpression(context, statement.value);
        if (local != context.locals.end()) {
          functions_ << "OpStore " << local->second.pointerId << " "
                     << value.id << "\n";
        }
      }
      return false;
    case HIRStatementKind::Assignment: {
      std::optional<PointerInfo> target =
          emitAccessPointer(context, statement.target);
      const EmitValue value = emitExpression(context, statement.value);
      if (target.has_value()) {
        functions_ << "OpStore " << target->pointerId << " " << value.id
                   << "\n";
      }
      return false;
    }
    case HIRStatementKind::Return:
      return emitReturnStatement(context, statement);
    case HIRStatementKind::Block:
      for (const HIRStatement &child : statement.body) {
        if (emitStatement(context, child)) {
          return true;
        }
      }
      return false;
    case HIRStatementKind::If:
      return emitIfStatement(context, statement);
    case HIRStatementKind::For:
      return emitForStatement(context, statement);
    case HIRStatementKind::Discard:
      functions_ << "OpKill\n";
      return true;
    case HIRStatementKind::Break:
      return emitBreakStatement();
    case HIRStatementKind::Continue:
      return emitContinueStatement();
    case HIRStatementKind::Expression:
    case HIRStatementKind::Raw:
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         vulkanGraphicsUnsupportedStatementMessage(statement));
      return false;
    }
    return false;
  }

  bool emitIfStatement(FunctionContext &context, const HIRStatement &statement) {
    const EmitValue condition = emitExpression(context, statement.value);
    const std::string thenLabel = freshId();
    const bool hasElse = !statement.elseBody.empty();
    const std::string elseLabel = hasElse ? freshId() : std::string{};
    const std::string mergeLabel = freshId();

    functions_ << "OpSelectionMerge " << mergeLabel << " None\n";
    functions_ << "OpBranchConditional " << condition.id << " " << thenLabel
               << " " << (hasElse ? elseLabel : mergeLabel) << "\n";

    functions_ << thenLabel << " = OpLabel\n";
    bool thenTerminated = false;
    for (const HIRStatement &child : statement.body) {
      if (thenTerminated) {
        break;
      }
      thenTerminated = emitStatement(context, child);
    }
    if (!thenTerminated) {
      functions_ << "OpBranch " << mergeLabel << "\n";
    }

    bool elseTerminated = false;
    if (hasElse) {
      functions_ << elseLabel << " = OpLabel\n";
      for (const HIRStatement &child : statement.elseBody) {
        if (elseTerminated) {
          break;
        }
        elseTerminated = emitStatement(context, child);
      }
      if (!elseTerminated) {
        functions_ << "OpBranch " << mergeLabel << "\n";
      }
    }

    functions_ << mergeLabel << " = OpLabel\n";
    const bool allPathsTerminate =
        hasElse && thenTerminated && elseTerminated;
    if (allPathsTerminate) {
      functions_ << "OpUnreachable\n";
    }
    return allPathsTerminate;
  }

  std::optional<PrototypeLoopUpdate>
  parseLoopUpdate(const std::vector<Token> &tokens) {
    const std::optional<std::string> counterName =
        vulkanGraphicsLoopUpdateCounterName(tokens, &diagnostics_);
    if (!counterName.has_value()) {
      return std::nullopt;
    }

    PrototypeLoopUpdate update;
    update.variableName = *counterName;
    if (tokens.size() == 2) {
      if (tokens[0].kind == TokenKind::Identifier) {
        update.increment = tokens[1].text == "++";
      } else {
        update.increment = tokens[0].text == "++";
      }
      return update;
    }

    update.increment = tokens[1].text == "+";
    update.amount = tokens[3].text;
    return update;
  }

  bool emitLoopUpdate(FunctionContext &context,
                      const std::vector<Token> &tokens) {
    const std::optional<PrototypeLoopUpdate> update = parseLoopUpdate(tokens);
    if (!update.has_value()) {
      return false;
    }

    const auto local = context.locals.find(update->variableName);
    if (local == context.locals.end()) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-graphics-body",
          "Vulkan graphics prototype for loop update cannot resolve local "
          "counter '" +
              update->variableName + "'");
      return false;
    }
    if (local->second.type.arraySize.has_value() ||
        local->second.type.name != "int") {
      diagnostics_.error(
          "vulkan.prototype-unsupported-graphics-body",
          "Vulkan graphics prototype for loop counters must be scalar int "
          "values");
      return false;
    }

    const EmitValue loaded = emitLoad(local->second);
    const std::string amount = intConstant(std::stoi(update->amount));
    const std::string updated = freshId();
    functions_ << updated << " = " << (update->increment ? "OpIAdd" : "OpISub")
               << " " << typeId(local->second.type) << " " << loaded.id << " "
               << amount << "\n";
    functions_ << "OpStore " << local->second.pointerId << " " << updated
               << "\n";
    return true;
  }

  bool emitParsedLoopUpdate(FunctionContext &context,
                            const HIRStatement &statement) {
    if (statement.kind != HIRStatementKind::Assignment) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "Vulkan graphics prototype for loops require "
                         "assignment-style counter updates");
      return false;
    }
    std::optional<PointerInfo> target =
        emitAccessPointer(context, statement.target);
    const EmitValue value = emitExpression(context, statement.value);
    if (!target.has_value()) {
      return false;
    }
    functions_ << "OpStore " << target->pointerId << " " << value.id << "\n";
    return true;
  }

  bool emitForStatement(FunctionContext &context, const HIRStatement &statement) {
    const bool whileLowered = isWhileLoweredForStatement(statement);
    if (!whileLowered) {
      if (statement.initializer.size() != 1 ||
          statement.initializer.front().kind != HIRStatementKind::Declaration) {
        diagnostics_.error(
            "vulkan.prototype-unsupported-graphics-body",
            "Vulkan graphics prototype for loops require a single scalar int "
            "declaration initializer");
        return false;
      }
      if (emitStatement(context, statement.initializer.front())) {
        diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                           "Vulkan graphics prototype for loop initializers "
                           "must not terminate control flow");
        return false;
      }
    }

    const std::string headerLabel = freshId();
    const std::string bodyLabel = freshId();
    const std::string continueLabel = freshId();
    const std::string mergeLabel = freshId();

    functions_ << "OpBranch " << headerLabel << "\n";
    functions_ << headerLabel << " = OpLabel\n";
    const EmitValue condition = emitExpression(context, statement.value);
    functions_ << "OpLoopMerge " << mergeLabel << " " << continueLabel
               << " None\n";
    functions_ << "OpBranchConditional " << condition.id << " " << bodyLabel
               << " " << mergeLabel << "\n";

    functions_ << bodyLabel << " = OpLabel\n";
    bool bodyTerminated = false;
    loopLabels_.push_back(PrototypeLoopLabels{continueLabel, mergeLabel});
    for (const HIRStatement &child : statement.body) {
      if (bodyTerminated) {
        break;
      }
      bodyTerminated = emitStatement(context, child);
    }
    loopLabels_.pop_back();
    if (!bodyTerminated) {
      functions_ << "OpBranch " << continueLabel << "\n";
    }

    functions_ << continueLabel << " = OpLabel\n";
    if (!whileLowered) {
      if (!statement.update.empty()) {
        if (statement.update.size() != 1 ||
            !emitParsedLoopUpdate(context, statement.update.front())) {
          return false;
        }
      } else if (!emitLoopUpdate(context, statement.updateTokens)) {
        return false;
      }
    }
    functions_ << "OpBranch " << headerLabel << "\n";

    functions_ << mergeLabel << " = OpLabel\n";
    return false;
  }

  void emitReturnValue(FunctionContext &context, const HIRExpression &value) {
    const EmitValue returned = emitExpression(context, value);
    for (std::size_t index = 0; index < context.outputStruct->fields.size();
         ++index) {
      const HIRField &field = context.outputStruct->fields[index];
      const std::string extracted = freshId();
      functions_ << extracted << " = OpCompositeExtract "
                 << typeId(field.type) << " " << returned.id << " " << index
                 << "\n";
      const PointerInfo *target = nullptr;
      if (context.stage->stage == "vertex" &&
          vulkanGraphicsIsPositionField(field)) {
        target = &vertexPosition_;
      } else if (context.stage->stage == "vertex") {
        if (const auto found = vertexOutputs_.find(field.name);
            found != vertexOutputs_.end()) {
          target = &found->second;
        }
      } else {
        if (const auto found = fragmentOutputs_.find(field.name);
            found != fragmentOutputs_.end()) {
          target = &found->second;
        }
      }
      if (target != nullptr) {
        functions_ << "OpStore " << target->pointerId << " " << extracted
                   << "\n";
      }
    }
  }

  EmitValue emitExpression(FunctionContext &context,
                           const HIRExpression &expression) {
    switch (expression.kind) {
    case HIRExpressionKind::Identifier: {
      if (const auto found = context.locals.find(expression.value);
          found != context.locals.end()) {
        return emitLoad(found->second);
      }
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "unknown Vulkan graphics identifier '" +
                             expression.value + "'");
      return EmitValue{expression.type, intConstant(0)};
    }
    case HIRExpressionKind::Literal:
      return EmitValue{expression.type, constantForLiteral(expression)};
    case HIRExpressionKind::Group:
      return emitExpression(context, expression.children.front());
    case HIRExpressionKind::Unary: {
      const EmitValue child = emitExpression(context, expression.children.front());
      if (expression.value == "+") {
        return child;
      }
      if (expression.value == "-") {
        const std::string id = freshId();
        const bool floatLike =
            vulkanGraphicsScalarTypeName(expression.type.name) == "float";
        functions_ << id << " = "
                   << (floatLike ? "OpFNegate " : "OpSNegate ")
                   << typeId(expression.type) << " " << child.id << "\n";
        return EmitValue{expression.type, id};
      }
      return child;
    }
    case HIRExpressionKind::MemberAccess:
      return emitMemberAccess(context, expression);
    case HIRExpressionKind::Constructor:
      return emitConstructor(context, expression);
    case HIRExpressionKind::Binary:
      return emitBinary(context, expression);
    case HIRExpressionKind::Select:
      return emitSelectExpression(context, expression);
    case HIRExpressionKind::TextureSample:
      return emitTextureSample(context, expression);
    case HIRExpressionKind::TextureCompare:
      return emitTextureCompare(context, expression);
    case HIRExpressionKind::Empty:
    case HIRExpressionKind::IndexAccess:
    case HIRExpressionKind::NonUniform:
    case HIRExpressionKind::TextureCompareLodManual:
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "unsupported expression in Vulkan graphics prototype");
      return EmitValue{expression.type, intConstant(0)};
    case HIRExpressionKind::Call:
      if (prototypeIntrinsicLoweringForCall(expression).has_value()) {
        return emitIntrinsicCall(context, expression);
      }
      return emitUserFunctionCall(context, expression);
    }
    return EmitValue{expression.type, intConstant(0)};
  }

  EmitValue emitMemberAccess(FunctionContext &context,
                             const HIRExpression &expression) {
    const HIRExpression &baseExpression = expression.children.front();
    if (vulkanGraphicsIsVector(baseExpression.type.name)) {
      const std::optional<std::vector<std::size_t>> indices =
          vulkanGraphicsSwizzleIndices(baseExpression.type, expression.value);
      if (!indices.has_value() ||
          !vulkanGraphicsSwizzleResultTypeSupported(
              baseExpression.type, expression.type, *indices)) {
        diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                           "unsupported vector swizzle in Vulkan graphics "
                           "prototype");
        return EmitValue{expression.type, intConstant(0)};
      }

      const EmitValue base = emitExpression(context, baseExpression);
      if (indices->size() == 1) {
        const std::string id = freshId();
        functions_ << id << " = OpCompositeExtract "
                   << typeId(expression.type) << " " << base.id << " "
                   << indices->front() << "\n";
        return EmitValue{expression.type, id};
      }

      const std::string id = freshId();
      functions_ << id << " = OpVectorShuffle " << typeId(expression.type)
                 << " " << base.id << " " << base.id;
      for (const std::size_t index : *indices) {
        functions_ << " " << index;
      }
      functions_ << "\n";
      return EmitValue{expression.type, id};
    }

    std::optional<PointerInfo> pointer = emitAccessPointer(context, expression);
    if (pointer.has_value()) {
      return emitLoad(*pointer);
    }
    diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                       "unsupported member access in Vulkan graphics prototype");
    return EmitValue{expression.type, intConstant(0)};
  }

  std::optional<EmitValue> emitGraphicsFloatScalarValue(const EmitValue &value) {
    const HIRType floatType{"float", std::nullopt};
    if (vulkanGraphicsTypeEquals(value.type, floatType)) {
      return value;
    }
    const std::string opcode =
        prototypeScalarConversionOpcode(value.type, floatType);
    if (opcode.empty() || opcode == "identity") {
      diagnostics_.error(
          "vulkan.prototype-unsupported-graphics-body",
          "Vulkan graphics prototype matrix constructors require numeric "
          "scalar constituents convertible to float");
      return std::nullopt;
    }
    const std::string id = freshId();
    functions_ << id << " = " << opcode << " " << typeId(floatType) << " "
               << value.id << "\n";
    return EmitValue{floatType, id};
  }

  bool appendGraphicsMatrixConstructorScalars(
      FunctionContext &context, const HIRExpression &expression,
      std::vector<std::string> &scalars) {
    const EmitValue value = emitExpression(context, expression);
    if (isPrototypeNumericScalarType(value.type)) {
      const std::optional<EmitValue> scalar =
          emitGraphicsFloatScalarValue(value);
      if (!scalar.has_value()) {
        return false;
      }
      scalars.push_back(scalar->id);
      return true;
    }

    if (!vulkanGraphicsScalarVectorTypeSupported(value.type) ||
        !vulkanGraphicsIsVector(value.type.name)) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-graphics-body",
          "Vulkan graphics prototype matrix constructors require numeric "
          "scalar/vector constituents or a single scalar/matrix operand");
      return false;
    }

    const HIRType componentType = vulkanGraphicsVectorComponentType(value.type);
    if (!isPrototypeNumericScalarType(componentType)) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-graphics-body",
          "Vulkan graphics prototype matrix constructors require numeric "
          "scalar/vector constituents");
      return false;
    }

    const std::size_t width = vulkanGraphicsVectorSize(value.type.name);
    for (std::size_t index = 0; index < width; ++index) {
      const std::string component = freshId();
      functions_ << component << " = OpCompositeExtract "
                 << typeId(componentType) << " " << value.id << " " << index
                 << "\n";
      const std::optional<EmitValue> scalar =
          emitGraphicsFloatScalarValue(EmitValue{componentType, component});
      if (!scalar.has_value()) {
        return false;
      }
      scalars.push_back(scalar->id);
    }
    return true;
  }

  std::optional<EmitValue>
  emitGraphicsMatrixColumn(const HIRType &columnType,
                           const std::vector<std::string> &scalars,
                           std::size_t firstScalar) {
    const std::size_t width = vulkanGraphicsVectorSize(columnType.name);
    if (firstScalar + width > scalars.size()) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "Vulkan graphics prototype matrix constructor "
                         "column has too few scalar constituents");
      return std::nullopt;
    }
    const std::string id = freshId();
    functions_ << id << " = OpCompositeConstruct " << typeId(columnType);
    for (std::size_t index = 0; index < width; ++index) {
      functions_ << " " << scalars[firstScalar + index];
    }
    functions_ << "\n";
    return EmitValue{columnType, id};
  }

  std::optional<EmitValue>
  emitGraphicsMatrixFromScalars(const HIRType &matrixType,
                                const std::vector<std::string> &scalars) {
    const std::optional<std::size_t> dimension =
        prototypeMatrixDimension(matrixType);
    if (!dimension.has_value() || scalars.size() != (*dimension * *dimension)) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-graphics-body",
          "Vulkan graphics prototype matrix constructors require constituents "
          "matching the result matrix element count");
      return std::nullopt;
    }

    const HIRType columnType = prototypeMatrixColumnType(matrixType);
    std::vector<std::string> columns;
    columns.reserve(*dimension);
    for (std::size_t column = 0; column < *dimension; ++column) {
      const std::optional<EmitValue> columnValue =
          emitGraphicsMatrixColumn(columnType, scalars, column * *dimension);
      if (!columnValue.has_value()) {
        return std::nullopt;
      }
      columns.push_back(columnValue->id);
    }

    const std::string id = freshId();
    functions_ << id << " = OpCompositeConstruct " << typeId(matrixType);
    for (const std::string &column : columns) {
      functions_ << " " << column;
    }
    functions_ << "\n";
    return EmitValue{matrixType, id};
  }

  std::optional<EmitValue> emitGraphicsMatrixFromScalar(
      const HIRType &matrixType, const EmitValue &sourceScalar) {
    const std::optional<EmitValue> diagonal =
        emitGraphicsFloatScalarValue(sourceScalar);
    if (!diagonal.has_value()) {
      return std::nullopt;
    }

    const std::optional<std::size_t> dimension =
        prototypeMatrixDimension(matrixType);
    if (!dimension.has_value()) {
      return std::nullopt;
    }

    std::vector<std::string> scalars;
    scalars.reserve(*dimension * *dimension);
    const std::string zero = floatConstant("0.0");
    for (std::size_t column = 0; column < *dimension; ++column) {
      for (std::size_t row = 0; row < *dimension; ++row) {
        scalars.push_back(column == row ? diagonal->id : zero);
      }
    }
    return emitGraphicsMatrixFromScalars(matrixType, scalars);
  }

  std::optional<EmitValue>
  emitGraphicsMatrixFromMatrix(const HIRType &matrixType,
                               const EmitValue &sourceMatrix) {
    if (vulkanGraphicsTypeEquals(matrixType, sourceMatrix.type)) {
      return sourceMatrix;
    }
    const std::optional<std::size_t> targetDimension =
        prototypeMatrixDimension(matrixType);
    const std::optional<std::size_t> sourceDimension =
        prototypeMatrixDimension(sourceMatrix.type);
    if (!targetDimension.has_value() || !sourceDimension.has_value()) {
      return std::nullopt;
    }

    std::vector<std::string> scalars;
    scalars.reserve(*targetDimension * *targetDimension);
    const std::string zero = floatConstant("0.0");
    const std::string one = floatConstant("1.0");
    const std::string floatType = typeId(HIRType{"float", std::nullopt});
    for (std::size_t column = 0; column < *targetDimension; ++column) {
      for (std::size_t row = 0; row < *targetDimension; ++row) {
        if (column < *sourceDimension && row < *sourceDimension) {
          const std::string component = freshId();
          functions_ << component << " = OpCompositeExtract " << floatType
                     << " " << sourceMatrix.id << " " << column << " " << row
                     << "\n";
          scalars.push_back(component);
        } else {
          scalars.push_back(column == row ? one : zero);
        }
      }
    }
    return emitGraphicsMatrixFromScalars(matrixType, scalars);
  }

  EmitValue emitGraphicsMatrixConstructor(FunctionContext &context,
                                          const HIRExpression &expression) {
    if (expression.children.size() == 1) {
      const EmitValue child =
          emitExpression(context, expression.children.front());
      if (isPrototypeNumericScalarType(child.type)) {
        const std::optional<EmitValue> matrix =
            emitGraphicsMatrixFromScalar(expression.type, child);
        if (matrix.has_value()) {
          return *matrix;
        }
      }
      if (vulkanGraphicsMatrixTypeSupported(child.type)) {
        const std::optional<EmitValue> matrix =
            emitGraphicsMatrixFromMatrix(expression.type, child);
        if (matrix.has_value()) {
          return *matrix;
        }
      }
    }

    std::vector<std::string> scalars;
    const std::optional<std::size_t> dimension =
        prototypeMatrixDimension(expression.type);
    if (dimension.has_value()) {
      scalars.reserve(*dimension * *dimension);
    }
    for (const HIRExpression &child : expression.children) {
      if (!appendGraphicsMatrixConstructorScalars(context, child, scalars)) {
        return EmitValue{expression.type, intConstant(0)};
      }
    }
    const std::optional<EmitValue> matrix =
        emitGraphicsMatrixFromScalars(expression.type, scalars);
    if (matrix.has_value()) {
      return *matrix;
    }
    return EmitValue{expression.type, intConstant(0)};
  }

  EmitValue emitConstructor(FunctionContext &context,
                            const HIRExpression &expression) {
    if (vulkanGraphicsMatrixTypeSupported(expression.type)) {
      return emitGraphicsMatrixConstructor(context, expression);
    }

    std::vector<std::string> constituents;
    const std::size_t expectedComponents =
        vulkanGraphicsVectorSize(expression.type.name);
    for (const HIRExpression &childExpression : expression.children) {
      const EmitValue child = emitExpression(context, childExpression);
      const std::size_t childComponents =
          vulkanGraphicsVectorSize(child.type.name);
      if (childComponents == 1) {
        constituents.push_back(child.id);
      } else {
        const HIRType scalar{vulkanGraphicsScalarTypeName(child.type.name),
                             std::nullopt};
        for (std::size_t index = 0; index < childComponents; ++index) {
          const std::string component = freshId();
          functions_ << component << " = OpCompositeExtract "
                     << typeId(scalar) << " " << child.id << " " << index
                     << "\n";
          constituents.push_back(component);
        }
      }
    }
    while (constituents.size() > expectedComponents) {
      constituents.pop_back();
    }
    const std::string id = freshId();
    functions_ << id << " = OpCompositeConstruct " << typeId(expression.type);
    for (const std::string &constituent : constituents) {
      functions_ << " " << constituent;
    }
    functions_ << "\n";
    return EmitValue{expression.type, id};
  }

  EmitValue emitBinary(FunctionContext &context, const HIRExpression &expression) {
    const EmitValue lhs = emitExpression(context, expression.children[0]);
    const EmitValue rhs = emitExpression(context, expression.children[1]);
    std::string opcode;
    const std::string resultScalar =
        vulkanGraphicsScalarTypeName(expression.type.name);
    const std::string operandScalar =
        vulkanGraphicsScalarTypeName(lhs.type.name);
    if (resultScalar == "bool") {
      if (operandScalar == "float") {
        if (expression.value == "<") {
          opcode = "OpFOrdLessThan";
        } else if (expression.value == "<=") {
          opcode = "OpFOrdLessThanEqual";
        } else if (expression.value == ">") {
          opcode = "OpFOrdGreaterThan";
        } else if (expression.value == ">=") {
          opcode = "OpFOrdGreaterThanEqual";
        } else if (expression.value == "==") {
          opcode = "OpFOrdEqual";
        } else if (expression.value == "!=") {
          opcode = "OpFUnordNotEqual";
        }
      } else if (operandScalar == "uint") {
        if (expression.value == "<") {
          opcode = "OpULessThan";
        } else if (expression.value == "<=") {
          opcode = "OpULessThanEqual";
        } else if (expression.value == ">") {
          opcode = "OpUGreaterThan";
        } else if (expression.value == ">=") {
          opcode = "OpUGreaterThanEqual";
        } else if (expression.value == "==") {
          opcode = "OpIEqual";
        } else if (expression.value == "!=") {
          opcode = "OpINotEqual";
        }
      } else {
        if (expression.value == "<") {
          opcode = "OpSLessThan";
        } else if (expression.value == "<=") {
          opcode = "OpSLessThanEqual";
        } else if (expression.value == ">") {
          opcode = "OpSGreaterThan";
        } else if (expression.value == ">=") {
          opcode = "OpSGreaterThanEqual";
        } else if (expression.value == "==") {
          opcode = "OpIEqual";
        } else if (expression.value == "!=") {
          opcode = "OpINotEqual";
        }
      }
    } else {
      const bool floatLike = resultScalar == "float";
      if (expression.value == "+") {
        opcode = floatLike ? "OpFAdd" : "OpIAdd";
      } else if (expression.value == "-") {
        opcode = floatLike ? "OpFSub" : "OpISub";
      } else if (expression.value == "*") {
        opcode = floatLike ? "OpFMul" : "OpIMul";
      } else if (expression.value == "/") {
        opcode = floatLike ? "OpFDiv" : "OpSDiv";
      }
    }
    if (opcode.empty()) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "unsupported binary operator in Vulkan graphics "
                         "prototype");
      opcode = resultScalar == "float" ? "OpFAdd" : "OpIAdd";
    }
    const std::string id = freshId();
    functions_ << id << " = " << opcode << " " << typeId(expression.type)
               << " " << lhs.id << " " << rhs.id << "\n";
    return EmitValue{expression.type, id};
  }

  EmitValue emitSelectExpression(FunctionContext &context,
                                 const HIRExpression &expression) {
    const EmitValue condition = emitExpression(context, expression.children[0]);
    const EmitValue trueValue = emitExpression(context, expression.children[1]);
    const EmitValue falseValue = emitExpression(context, expression.children[2]);

    if (condition.type.name != "bool" ||
        condition.type.arraySize.has_value() ||
        !vulkanGraphicsTypeEquals(expression.type, trueValue.type) ||
        !vulkanGraphicsTypeEquals(expression.type, falseValue.type)) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "unsupported select expression in Vulkan graphics "
                         "prototype");
      return EmitValue{expression.type, intConstant(0)};
    }

    std::string conditionId = condition.id;
    const std::size_t resultWidth =
        vulkanGraphicsVectorSize(expression.type.name);
    if (resultWidth > 1) {
      const HIRType conditionType{
          "bvec" + std::to_string(resultWidth), std::nullopt};
      conditionId = freshId();
      functions_ << conditionId << " = OpCompositeConstruct "
                 << typeId(conditionType);
      for (std::size_t index = 0; index < resultWidth; ++index) {
        functions_ << " " << condition.id;
      }
      functions_ << "\n";
    }

    const std::string id = freshId();
    functions_ << id << " = OpSelect " << typeId(expression.type) << " "
               << conditionId << " " << trueValue.id << " " << falseValue.id
               << "\n";
    return EmitValue{expression.type, id};
  }

  EmitValue emitVectorSplat(const HIRType &targetType,
                            const EmitValue &value) {
    if (vulkanGraphicsTypeEquals(targetType, value.type)) {
      return value;
    }

    const std::size_t width = vulkanGraphicsVectorSize(targetType.name);
    const HIRType componentType = vulkanGraphicsVectorComponentType(targetType);
    if (width <= 1 || !vulkanGraphicsTypeEquals(value.type, componentType)) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "unsupported intrinsic operand splat in Vulkan "
                         "graphics prototype");
      return EmitValue{targetType, intConstant(0)};
    }

    const std::string id = freshId();
    functions_ << id << " = OpCompositeConstruct " << typeId(targetType);
    for (std::size_t index = 0; index < width; ++index) {
      functions_ << " " << value.id;
    }
    functions_ << "\n";
    return EmitValue{targetType, id};
  }

  EmitValue emitIntrinsicCall(FunctionContext &context,
                              const HIRExpression &expression) {
    const std::optional<PrototypeIntrinsicLowering> lowering =
        prototypeIntrinsicLoweringForCall(expression);
    if (!lowering.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "Vulkan graphics prototype intrinsic lowering "
                         "currently supports only the scalar/vector HIR math "
                         "intrinsic subset");
      return EmitValue{expression.type, intConstant(0)};
    }

    std::vector<EmitValue> operands;
    operands.reserve(expression.children.size());
    for (const HIRExpression &child : expression.children) {
      EmitValue value = emitExpression(context, child);
      if (lowering->operandsUseResultType &&
          !vulkanGraphicsTypeEquals(value.type, expression.type)) {
        value = emitVectorSplat(expression.type, value);
      }
      operands.push_back(value);
    }

    if (lowering->kind == PrototypeIntrinsicLoweringKind::Identity) {
      if (operands.size() != 1) {
        diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                           "unsupported identity intrinsic in Vulkan graphics "
                           "prototype");
        return EmitValue{expression.type, intConstant(0)};
      }
      return EmitValue{expression.type, operands.front().id};
    }

    const std::string id = freshId();
    if (lowering->kind == PrototypeIntrinsicLoweringKind::CoreInstruction) {
      functions_ << id << " = " << lowering->opcode << " "
                 << typeId(expression.type);
    } else {
      functions_ << id << " = OpExtInst " << typeId(expression.type) << " "
                 << ensureGLSLStd450Import() << " " << lowering->opcode;
    }
    for (const EmitValue &operand : operands) {
      functions_ << " " << operand.id;
    }
    functions_ << "\n";
    return EmitValue{expression.type, id};
  }

  EmitValue emitUserFunctionCall(FunctionContext &context,
                                 const HIRExpression &expression) {
    const GraphicsFunctionInfo *info =
        helperFunctionInfo(context, expression.value);
    if (info == nullptr || info->function == nullptr) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "Vulkan graphics prototype function calls can target "
                         "only same-stage or top-level helper functions");
      return EmitValue{expression.type, intConstant(0)};
    }
    if (context.function == info->function) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-helper",
                         "Vulkan graphics prototype helper functions cannot "
                         "call themselves directly");
      return EmitValue{expression.type, intConstant(0)};
    }
    if (expression.children.size() != info->parameterTypes.size()) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "Vulkan graphics prototype helper call argument "
                         "count does not match helper signature");
      return EmitValue{expression.type, intConstant(0)};
    }

    std::vector<EmitValue> arguments;
    arguments.reserve(expression.children.size());
    for (std::size_t index = 0; index < expression.children.size(); ++index) {
      const EmitValue argument = emitExpression(context,
                                                expression.children[index]);
      if (!vulkanGraphicsTypeEquals(argument.type,
                                    info->parameterTypes[index])) {
        diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                           "Vulkan graphics prototype helper calls do not "
                           "insert argument casts");
        return EmitValue{expression.type, intConstant(0)};
      }
      arguments.push_back(argument);
    }

    if (!expression.type.name.empty() &&
        !vulkanGraphicsTypeEquals(expression.type, info->returnType)) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "Vulkan graphics prototype helper call result type "
                         "does not match helper return type");
      return EmitValue{expression.type, intConstant(0)};
    }

    const std::string id = freshId();
    functions_ << id << " = OpFunctionCall " << typeId(info->returnType)
               << " " << info->id;
    for (const EmitValue &argument : arguments) {
      functions_ << " " << argument.id;
    }
    functions_ << "\n";
    return EmitValue{info->returnType, id};
  }

  std::optional<PointerInfo> descriptorResource(FunctionContext &context,
                                                const HIRExpression &expression,
                                                HIRResourceKind kind) {
    if (context.descriptors == nullptr) {
      diagnostics_.error(
          "vulkan.prototype-unsupported-graphics-body",
          "Vulkan graphics texture sampling requires descriptor resources");
      return std::nullopt;
    }

    if (expression.kind == HIRExpressionKind::Identifier) {
      const auto found = context.descriptors->find(expression.value);
      if (found == context.descriptors->end() || found->second.kind != kind) {
        diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                           "Vulkan graphics texture sampling cannot resolve "
                           "descriptor resource '" +
                               expression.value + "'");
        return std::nullopt;
      }
      if (found->second.type.arraySize.has_value()) {
        diagnostics_.error(
            "vulkan.prototype-unsupported-graphics-body",
            "Vulkan graphics texture sampling requires indexed access for "
            "descriptor array resource '" +
                expression.value + "'");
        return std::nullopt;
      }
      return found->second;
    }

    if (expression.kind != HIRExpressionKind::IndexAccess ||
        expression.children.size() != 2 ||
        expression.children[0].kind != HIRExpressionKind::Identifier) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "Vulkan graphics texture sampling supports only "
                         "direct descriptor resources or indexed descriptor "
                         "arrays");
      return std::nullopt;
    }

    const std::string &resourceName = expression.children[0].value;
    const auto found = context.descriptors->find(resourceName);
    if (found == context.descriptors->end() || found->second.kind != kind) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "Vulkan graphics texture sampling cannot resolve "
                         "descriptor array resource '" +
                             resourceName + "'");
      return std::nullopt;
    }
    if (!found->second.type.arraySize.has_value()) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "Vulkan graphics texture sampling cannot index "
                         "non-array descriptor resource '" +
                             resourceName + "'");
      return std::nullopt;
    }

    const HIRExpression *indexExpression = &expression.children[1];
    bool nonUniformDescriptor = false;
    if (indexExpression->kind == HIRExpressionKind::NonUniform) {
      if (indexExpression->children.size() != 1) {
        diagnostics_.error(
            "vulkan.prototype-unsupported-nonuniform-index",
            "Vulkan graphics nonuniform descriptor index markers require "
            "exactly one operand");
        return std::nullopt;
      }
      nonUniformDescriptor = true;
      indexExpression = &indexExpression->children.front();
    }

    const EmitValue index = emitExpression(context, *indexExpression);
    if (index.type.arraySize.has_value() || index.type.name != "int") {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "Vulkan graphics descriptor array indices must be "
                         "scalar int values");
      return std::nullopt;
    }

    const HIRType elementType = arrayElementType(found->second.type);
    const std::string pointerType =
        uniformConstantElementPointerTypeId(kind, elementType);
    if (pointerType.empty()) {
      diagnostics_.error("vulkan.prototype-unsupported-graphics-body",
                         "Vulkan graphics texture sampling cannot compute "
                         "descriptor array element pointer type");
      return std::nullopt;
    }
    if (nonUniformDescriptor) {
      requireSampledImageNonUniformDescriptorIndex();
      decorateNonUniform(index.id);
    }

    PointerInfo result{elementType, pointerType, freshId(), "UniformConstant",
                       kind, nonUniformDescriptor};
    functions_ << result.pointerId << " = OpAccessChain "
               << result.pointerTypeId << " " << found->second.pointerId
               << " " << index.id << "\n";
    if (result.nonUniformDescriptor) {
      decorateNonUniform(result.pointerId);
    }
    return result;
  }

  EmitValue emitTextureSample(FunctionContext &context,
                              const HIRExpression &expression) {
    const bool explicitLod = isPrototypeExplicitLodTextureSample(expression);
    const std::optional<PointerInfo> texture =
        descriptorResource(context, expression.children[0], HIRResourceKind::Texture);
    const std::optional<PointerInfo> sampler =
        descriptorResource(context, expression.children[1], HIRResourceKind::Sampler);
    const EmitValue coordinates = emitExpression(context, expression.children[2]);
    const std::optional<EmitValue> lod =
        explicitLod ? std::optional<EmitValue>(
                          emitExpression(context, expression.children[3]))
                    : std::nullopt;
    if (!texture.has_value() || !sampler.has_value()) {
      return EmitValue{expression.type, intConstant(0)};
    }
    const EmitValue textureValue = emitLoad(*texture);
    const EmitValue samplerValue = emitLoad(*sampler);
    const std::string sampledImage = freshId();
    functions_ << sampledImage << " = OpSampledImage "
               << sampledImageTypeId(texture->type) << " " << textureValue.id
               << " " << samplerValue.id << "\n";
    if (textureValue.nonUniformDescriptor ||
        samplerValue.nonUniformDescriptor) {
      requireSampledImageNonUniformDescriptorIndex();
      decorateNonUniform(sampledImage);
    }

    const std::string id = freshId();
    if (explicitLod) {
      functions_ << id << " = OpImageSampleExplicitLod "
                 << typeId(expression.type) << " " << sampledImage << " "
                 << coordinates.id << " Lod " << lod->id << "\n";
    } else {
      functions_ << id << " = OpImageSampleImplicitLod "
                 << typeId(expression.type) << " " << sampledImage << " "
                 << coordinates.id << "\n";
    }
    return EmitValue{expression.type, id};
  }

  EmitValue emitTextureCompare(FunctionContext &context,
                               const HIRExpression &expression) {
    const bool explicitLod = isPrototypeExplicitLodTextureCompare(expression);
    const std::optional<PointerInfo> texture =
        descriptorResource(context, expression.children[0],
                           HIRResourceKind::Texture);
    const std::optional<PointerInfo> sampler =
        descriptorResource(context, expression.children[1],
                           HIRResourceKind::Sampler);
    const EmitValue coordinates = emitExpression(context, expression.children[2]);
    const EmitValue depth = emitExpression(context, expression.children[3]);
    const std::optional<EmitValue> lod =
        explicitLod ? std::optional<EmitValue>(
                          emitExpression(context, expression.children[4]))
                    : std::nullopt;
    if (!texture.has_value() || !sampler.has_value()) {
      return EmitValue{expression.type, intConstant(0)};
    }
    const EmitValue textureValue = emitLoad(*texture);
    const EmitValue samplerValue = emitLoad(*sampler);
    const std::string sampledImage = freshId();
    functions_ << sampledImage << " = OpSampledImage "
               << sampledImageTypeId(texture->type) << " " << textureValue.id
               << " " << samplerValue.id << "\n";
    if (textureValue.nonUniformDescriptor ||
        samplerValue.nonUniformDescriptor) {
      requireSampledImageNonUniformDescriptorIndex();
      decorateNonUniform(sampledImage);
    }

    const std::string id = freshId();
    if (explicitLod) {
      functions_ << id << " = OpImageSampleDrefExplicitLod "
                 << typeId(expression.type) << " " << sampledImage << " "
                 << coordinates.id << " " << depth.id << " Lod " << lod->id
                 << "\n";
    } else {
      functions_ << id << " = OpImageSampleDrefImplicitLod "
                 << typeId(expression.type) << " " << sampledImage << " "
                 << coordinates.id << " " << depth.id << "\n";
    }
    return EmitValue{expression.type, id};
  }

  const HIRModule &module_;
  DiagnosticEngine &diagnostics_;
  StorageLayoutContext layoutContext_;
  std::size_t nextId_ = 1;
  std::ostringstream entryPoints_;
  std::ostringstream imports_;
  std::ostringstream names_;
  std::ostringstream decorations_;
  std::ostringstream types_;
  std::ostringstream globals_;
  std::ostringstream functions_;
  std::unordered_map<std::string, std::string> typeIds_;
  std::unordered_map<std::string, std::string> pointerTypeIds_;
  std::unordered_map<std::string, std::string> uniformBlockTypeIds_;
  std::unordered_map<std::string, std::string> imageTypeIds_;
  std::unordered_map<std::string, std::string> descriptorArrayTypeIds_;
  std::unordered_map<std::string, std::string> sampledImageTypeIds_;
  std::unordered_map<std::string, std::string> functionTypeIds_;
  std::unordered_map<std::string, std::string> intConstants_;
  std::unordered_map<std::string, std::string> uintConstants_;
  std::unordered_map<std::string, std::string> literalConstants_;
  std::unordered_map<std::string, PointerInfo> vertexInputs_;
  std::unordered_map<std::string, PointerInfo> vertexOutputs_;
  std::unordered_map<std::string, PointerInfo> fragmentInputs_;
  std::unordered_map<std::string, PointerInfo> fragmentOutputs_;
  std::unordered_map<std::string, PointerInfo> vertexUniforms_;
  std::unordered_map<std::string, PointerInfo> fragmentUniforms_;
  std::unordered_map<std::string, PointerInfo> vertexDescriptors_;
  std::unordered_map<std::string, PointerInfo> fragmentDescriptors_;
  PointerInfo vertexPosition_;
  std::string vertexFunctionId_;
  std::string fragmentFunctionId_;
  std::unordered_map<std::string, GraphicsFunctionInfo> functionsByKey_;
  std::string samplerTypeId_;
  std::string glslStd450ImportId_;
  std::vector<PrototypeLoopLabels> loopLabels_;
  bool usesRuntimeDescriptorArray_ = false;
  bool usesNonUniformDescriptorIndex_ = false;
  bool usesSampledImageArrayNonUniformIndexing_ = false;
  std::unordered_set<std::string> nonUniformDecorationIds_;
};

std::string generateVulkanGraphicsPrototypeAssembly(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  VulkanGraphicsSPIRVBuilder builder(module, diagnostics);
  return builder.render();
}

bool writeTextFile(const std::filesystem::path &path, std::string_view text,
                   DiagnosticEngine &diagnostics, std::string_view code) {
  std::ofstream output(path, std::ios::binary);
  if (!output) {
    diagnostics.error(std::string(code), "failed to write '" + path.string() + "'");
    return false;
  }
  output << text;
  return true;
}

} // namespace

bool vulkanResourceUsesDescriptor(HIRResourceKind kind) {
  return kind == HIRResourceKind::Uniform || kind == HIRResourceKind::Buffer ||
         kind == HIRResourceKind::Texture ||
         kind == HIRResourceKind::StorageImage ||
         kind == HIRResourceKind::Sampler;
}

std::string vulkanDescriptorType(HIRResourceKind kind) {
  switch (kind) {
  case HIRResourceKind::Uniform:
    return "VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER";
  case HIRResourceKind::Buffer:
    return "VK_DESCRIPTOR_TYPE_STORAGE_BUFFER";
  case HIRResourceKind::Texture:
    return "VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE";
  case HIRResourceKind::StorageImage:
    return "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE";
  case HIRResourceKind::Sampler:
    return "VK_DESCRIPTOR_TYPE_SAMPLER";
  case HIRResourceKind::Shared:
  case HIRResourceKind::Value:
    break;
  }
  return "";
}

std::string vulkanResourceStorageClass(HIRResourceKind kind) {
  switch (kind) {
  case HIRResourceKind::Uniform:
    return "Uniform";
  case HIRResourceKind::Buffer:
    return "StorageBuffer";
  case HIRResourceKind::Texture:
  case HIRResourceKind::StorageImage:
  case HIRResourceKind::Sampler:
    return "UniformConstant";
  case HIRResourceKind::Shared:
    return "Workgroup";
  case HIRResourceKind::Value:
    break;
  }
  return "";
}

std::string vulkanResourceBindingClass(HIRResourceKind kind) {
  switch (kind) {
  case HIRResourceKind::Uniform:
    return "uniformBuffer";
  case HIRResourceKind::Buffer:
    return "storageBuffer";
  case HIRResourceKind::Texture:
    return "sampledImage";
  case HIRResourceKind::StorageImage:
    return "storageImage";
  case HIRResourceKind::Sampler:
    return "sampler";
  case HIRResourceKind::Shared:
    return "workgroup";
  case HIRResourceKind::Value:
    break;
  }
  return "";
}

std::string vulkanResourceSPIRVType(const HIRResource &resource) {
  auto wrapArray = [&resource](std::string elementType) {
    if (resource.type.arraySize.has_value()) {
      if (resource.type.arraySize->empty()) {
        return "OpTypeRuntimeArray<" + std::move(elementType) + ">";
      }
      return "OpTypeArray<" + std::move(elementType) + ", " +
             *resource.type.arraySize + ">";
    }
    return elementType;
  };

  switch (resource.kind) {
  case HIRResourceKind::Uniform: {
    const HIRType element = arrayElementType(resource.type);
    return wrapArray("OpTypeStruct<" + formatType(element) + ">");
  }
  case HIRResourceKind::Buffer: {
    const HIRType element =
        prototypeAtomicStorageBackingType(bufferElementType(resource.type));
    return wrapArray("OpTypeRuntimeArray<" + formatType(element) + ">");
  }
  case HIRResourceKind::Texture: {
    const HIRType textureElement = arrayElementType(resource.type);
    const std::string sampledType =
        isComparisonTextureType(textureElement.name)
            ? "depth_compare"
            : textureSampledScalarTypeName(textureElement.name);
    return wrapArray("OpTypeImage<" + sampledType + ", " +
                     textureIRDimension(textureElement.name) +
                     ", sampled=1>");
  }
  case HIRResourceKind::StorageImage: {
    const HIRType imageElement = arrayElementType(resource.type);
    const std::string sampledType =
        textureSampledScalarTypeName(imageElement.name);
    return wrapArray("OpTypeImage<" + sampledType + ", " +
                     textureIRDimension(imageElement.name) +
                     ", sampled=2, format=" +
                     storageImageSPIRVFormatNameFromFormat(
                         resolvedStorageImageFormatName(resource)) +
                     ">");
  }
  case HIRResourceKind::Sampler:
    return wrapArray("OpTypeSampler");
  case HIRResourceKind::Shared:
    return "OpVariable<Workgroup, " +
           formatType(prototypeAtomicStorageBackingType(resource.type)) + ">";
  case HIRResourceKind::Value:
    break;
  }
  return "";
}

bool vulkanResourceRequiresLegalizedBinding(
    const BackendPlanResource &resource) {
  return resource.source != nullptr && resource.emitsTargetBinding;
}

bool vulkanResourceBindingRecordMatchesIdentity(
    const TargetLegalizationResourceBindingRecord &record,
    const BackendPlanResource &resource) {
  return record.target == TargetKind::Vulkan &&
         record.stage == resource.stage &&
         record.sourceEntryPoint == resource.entryPoint &&
         record.backendEntryPoint == resource.backendEntryPoint &&
         record.name == resource.name;
}

std::vector<const TargetLegalizationResourceBindingRecord *>
vulkanResourceBindingRecordsForResource(
    const TargetLegalizationResourceBindingFacts *resourceBindings,
    const BackendPlanResource &resource) {
  std::vector<const TargetLegalizationResourceBindingRecord *> records;
  if (resourceBindings == nullptr ||
      resourceBindings->target != TargetKind::Vulkan) {
    return records;
  }
  for (const TargetLegalizationResourceBindingRecord &record :
       resourceBindings->records) {
    if (vulkanResourceBindingRecordMatchesIdentity(record, resource)) {
      records.push_back(&record);
    }
  }
  return records;
}

std::string
vulkanDeclarationResourceLabel(const BackendPlanResource &resource) {
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

void appendVulkanDeclarationRecordMismatch(
    std::vector<std::string> &mismatches, std::string_view field,
    std::string_view expected, std::string_view actual) {
  mismatches.push_back(std::string(field) + " expected '" +
                       std::string(expected) + "', got '" +
                       std::string(actual) + "'");
}

void appendVulkanDeclarationRecordMismatch(
    std::vector<std::string> &mismatches, std::string_view field,
    std::size_t expected, std::size_t actual) {
  appendVulkanDeclarationRecordMismatch(
      mismatches, field, std::to_string(expected), std::to_string(actual));
}

std::string optionalVulkanStringForDiagnostic(
    const std::optional<std::string> &value) {
  if (!value.has_value()) {
    return "<absent>";
  }
  return *value;
}

std::string joinVulkanDeclarationMismatches(
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

std::vector<std::string> vulkanDeclarationRecordMismatches(
    const BackendPlanResource &resource,
    const TargetLegalizationResourceBindingRecord &record) {
  std::vector<std::string> mismatches;
  if (resource.source == nullptr) {
    return mismatches;
  }
  const HIRResource &source = *resource.source;
  const bool descriptor = vulkanResourceUsesDescriptor(source.kind);
  const std::string expectedAbi = descriptor ? "descriptor" : "workgroupLocal";

  if (record.abi != expectedAbi) {
    appendVulkanDeclarationRecordMismatch(mismatches, "abi", expectedAbi,
                                          record.abi);
  }
  if (record.kind != resource.kindName) {
    appendVulkanDeclarationRecordMismatch(mismatches, "kind",
                                          resource.kindName, record.kind);
  }
  if (record.sourceType != resource.sourceType) {
    appendVulkanDeclarationRecordMismatch(
        mismatches, "sourceType", resource.sourceType, record.sourceType);
  }
  if (record.storageImageFormat != resource.storageImageFormat) {
    appendVulkanDeclarationRecordMismatch(
        mismatches, "storageImageFormat",
        optionalVulkanStringForDiagnostic(resource.storageImageFormat),
        optionalVulkanStringForDiagnostic(record.storageImageFormat));
  }
  const std::string expectedStorageClass =
      vulkanResourceStorageClass(source.kind);
  if (record.addressSpace != expectedStorageClass) {
    appendVulkanDeclarationRecordMismatch(
        mismatches, "addressSpace", expectedStorageClass, record.addressSpace);
  }
  if (!record.storageClass.has_value()) {
    appendVulkanDeclarationRecordMismatch(mismatches, "storageClass",
                                          expectedStorageClass, "<missing>");
  } else if (*record.storageClass != expectedStorageClass) {
    appendVulkanDeclarationRecordMismatch(
        mismatches, "storageClass", expectedStorageClass,
        *record.storageClass);
  }
  const std::string expectedBindingClass =
      vulkanResourceBindingClass(source.kind);
  if (record.bindingClass != expectedBindingClass) {
    appendVulkanDeclarationRecordMismatch(
        mismatches, "bindingClass", expectedBindingClass, record.bindingClass);
  }
  const std::string expectedSPIRVType = vulkanResourceSPIRVType(source);
  if (!record.spirvType.has_value()) {
    appendVulkanDeclarationRecordMismatch(mismatches, "spirvType",
                                          expectedSPIRVType, "<missing>");
  } else if (*record.spirvType != expectedSPIRVType) {
    appendVulkanDeclarationRecordMismatch(
        mismatches, "spirvType", expectedSPIRVType, *record.spirvType);
  }

  if (descriptor) {
    const std::string expectedDescriptorType =
        vulkanDescriptorType(source.kind);
    if (!record.descriptorType.has_value()) {
      appendVulkanDeclarationRecordMismatch(
          mismatches, "descriptorType", expectedDescriptorType, "<missing>");
    } else if (*record.descriptorType != expectedDescriptorType) {
      appendVulkanDeclarationRecordMismatch(
          mismatches, "descriptorType", expectedDescriptorType,
          *record.descriptorType);
    }
    if (!record.set.has_value()) {
      appendVulkanDeclarationRecordMismatch(
          mismatches, "set", std::to_string(source.set), "<missing>");
    } else if (*record.set != source.set) {
      appendVulkanDeclarationRecordMismatch(mismatches, "set", source.set,
                                            *record.set);
    }
    if (!record.binding.has_value()) {
      appendVulkanDeclarationRecordMismatch(
          mismatches, "binding", std::to_string(source.binding), "<missing>");
    } else if (*record.binding != source.binding) {
      appendVulkanDeclarationRecordMismatch(mismatches, "binding",
                                            source.binding, *record.binding);
    }
  } else {
    if (record.descriptorType.has_value()) {
      appendVulkanDeclarationRecordMismatch(
          mismatches, "descriptorType", "<absent>",
          optionalVulkanStringForDiagnostic(record.descriptorType));
    }
    if (record.set.has_value()) {
      appendVulkanDeclarationRecordMismatch(mismatches, "set", "<absent>",
                                            std::to_string(*record.set));
    }
    if (record.binding.has_value()) {
      appendVulkanDeclarationRecordMismatch(mismatches, "binding", "<absent>",
                                            std::to_string(*record.binding));
    }
  }
  if (record.argumentIndex.has_value()) {
    appendVulkanDeclarationRecordMismatch(
        mismatches, "argumentIndex", "<absent>",
        std::to_string(*record.argumentIndex));
  }
  return mismatches;
}

bool diagnoseVulkanLegalizedResourceDeclarationMismatches(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts *resourceBindings,
    DiagnosticEngine &diagnostics) {
  if (resourceBindings == nullptr ||
      resourceBindings->target != TargetKind::Vulkan ||
      !resourceBindings->complete) {
    diagnostics.error(
        "vulkan.legalized-resource-binding-missing",
        "Vulkan native package requires complete legalized "
        "descriptor/workgroupLocal records before SPIR-V resource emission; "
        "missing binding record(s): resource-bindings");
    return true;
  }

  bool failed = false;
  std::set<std::string> matchedEvidenceIds;
  const BackendPlan plan = buildBackendPlan(module);
  for (const BackendPlanStageInterface &stage : plan.stages) {
    for (const BackendPlanResource &resource : stage.resources) {
      if (!vulkanResourceRequiresLegalizedBinding(resource)) {
        continue;
      }
      const std::vector<const TargetLegalizationResourceBindingRecord *> records =
          vulkanResourceBindingRecordsForResource(resourceBindings, resource);
      if (records.empty()) {
        diagnostics.error(
            "vulkan.legalized-resource-binding-missing",
            "missing Vulkan legalized resource-binding record for " +
                vulkanDeclarationResourceLabel(resource));
        failed = true;
        continue;
      }
      if (records.size() > 1) {
        diagnostics.error(
            "vulkan.legalized-resource-binding-mismatch",
            "duplicate Vulkan legalized resource-binding records for " +
                vulkanDeclarationResourceLabel(resource));
        failed = true;
      }
      for (const TargetLegalizationResourceBindingRecord *record : records) {
        matchedEvidenceIds.insert(record->evidenceId);
        const std::vector<std::string> mismatches =
            vulkanDeclarationRecordMismatches(resource, *record);
        if (mismatches.empty()) {
          continue;
        }
        diagnostics.error(
            "vulkan.legalized-resource-binding-mismatch",
            "Vulkan SPIR-V declaration metadata disagrees with legalization "
            "record '" +
                record->evidenceId + "' for " +
                vulkanDeclarationResourceLabel(resource) + ": " +
                joinVulkanDeclarationMismatches(mismatches));
        failed = true;
      }
    }
  }

  for (const TargetLegalizationResourceBindingRecord &record :
       resourceBindings->records) {
    if (record.target == TargetKind::Vulkan &&
        matchedEvidenceIds.count(record.evidenceId) == 0) {
      diagnostics.error(
          "vulkan.legalized-resource-binding-mismatch",
          "stale Vulkan legalized resource-binding record '" +
              record.evidenceId + "' for resource '" + record.name +
              "' has no matching SPIR-V declaration input");
      failed = true;
    }
  }
  return failed;
}

std::string generateVulkanBackendIR(const HIRModule &module) {
  std::ostringstream out;
  out << "; backend lowering for vulkan is planned; descriptor ABI and textual "
         "SPIR-V scaffolding only\n";
  if (moduleContainsRawStatement(module)) {
    out << "; error: " << kRawStatementBackendInputDiagnostic
        << ": Vulkan backend input cannot contain HIR raw statements; lower "
           "them to structured HIR before backend emission\n";
    return out.str();
  }
  out << "vulkan.module @" << module.name << " {\n";
  for (const HIRStage &stage : module.stages) {
    out << "  vulkan.stage @" << stage.stage << " entry @"
        << stage.stage << "_" << stage.entryPointName << " {\n";
    for (const HIRResource &resource : stage.resources) {
      out << renderVulkanResourceLine(resource);
    }
    out << "  }\n";
  }
  out << "}\n\n";
  out << "; textual SPIR-V skeleton follows; not assembled or validated yet\n";
  renderSpirvModuleSkeleton(out, module);
  out << "\n";
  out << "; source CrossGL IR follows\n";
  return out.str();
}

bool vulkanPrototypeBinarySupported(const HIRModule &module,
                                    DiagnosticEngine &diagnostics) {
  if (diagnoseRawStatementBackendInput(module, diagnostics)) {
    return false;
  }
  const HIRStage *stage = prototypeComputeStage(module);
  if (stage == nullptr) {
    return vulkanGraphicsPrototypeSupported(module, diagnostics);
  }
  const PrototypeConstantMap constants = prototypeConstants(module);
  const PrototypeStructMap structs = prototypeStructs(module);
  const StorageLayoutContext layoutContext(module.structs, module.constants);
  for (const HIRResource &resource : stage->resources) {
    if (resource.kind == HIRResourceKind::Shared) {
      if (!isPrototypeWorkgroupSharedResource(resource)) {
        diagnostics.error("vulkan.prototype-unsupported-resource",
                          "Vulkan prototype Workgroup shared declarations "
                          "currently support only scalar/vector resources");
        return false;
      }
      if (resource.type.arraySize.has_value()) {
        if (resource.type.arraySize->empty()) {
          diagnostics.error(
              "vulkan.prototype-unsupported-resource",
              "Vulkan prototype Workgroup shared declarations require "
              "fixed-size arrays");
          return false;
        }
        if (!prototypeArrayElementCount(resource.type, layoutContext).has_value()) {
          diagnostics.error(
              "vulkan.prototype-unsupported-resource",
              "Vulkan prototype Workgroup shared declarations require "
              "fixed-size numeric or folded-constant array sizes");
          return false;
        }
      }
      continue;
    }
    if (resource.kind == HIRResourceKind::Uniform) {
      if (!isPrototypeStructUniformBufferResource(module, resource)) {
        diagnostics.error("vulkan.prototype-unsupported-resource",
                          "Vulkan prototype uniform-buffer lowering supports "
                          "only struct uniform resources");
        return false;
      }
      if (resource.type.arraySize.has_value()) {
        if (resource.type.arraySize->empty()) {
          diagnostics.error(
              "vulkan.prototype-unsupported-runtime-resource-array",
              "Vulkan prototype uniform-buffer descriptor lowering does not "
              "yet support unsized/runtime resource array '" +
                  resource.name + "'");
          return false;
        }
        if (!prototypeArrayElementCount(resource.type, layoutContext).has_value()) {
          diagnostics.error(
              "vulkan.prototype-unsupported-uniform-buffer",
              "Vulkan prototype uniform-buffer descriptor arrays require "
              "fixed-size numeric or folded-constant resource array sizes");
          return false;
        }
      }
      if (emitUnsupportedStorageCapabilityDiagnostic(
              prototypeUniformBufferElementType(resource), layoutContext,
              diagnostics, resource.name)) {
        return false;
      }
      continue;
    }
    if (resource.kind == HIRResourceKind::Buffer &&
        resource.type.arraySize.has_value()) {
      if (resource.type.arraySize->empty()) {
        diagnostics.error(
            "vulkan.prototype-unsupported-runtime-resource-array",
            "Vulkan prototype storage-buffer descriptor lowering does not yet "
            "support unsized/runtime resource array '" +
                resource.name + "'");
        return false;
      }
      if (!prototypeArrayElementCount(resource.type, layoutContext).has_value()) {
        diagnostics.error(
            "vulkan.prototype-unsupported-storage-buffer-array",
            "Vulkan prototype storage-buffer descriptor arrays require "
            "fixed-size numeric or folded-constant resource array sizes");
        return false;
      }
      if (isPrototypeStructStorageBufferResource(module, resource)) {
        if (emitUnsupportedStorageCapabilityDiagnostic(
                prototypeBufferElementType(resource), layoutContext, diagnostics,
                resource.name)) {
          return false;
        }
        continue;
      }
      continue;
    }
    if (isPrototypeStructStorageBufferResource(module, resource)) {
      if (emitUnsupportedStorageCapabilityDiagnostic(
              prototypeBufferElementType(resource), layoutContext, diagnostics,
              resource.name)) {
        return false;
      }
      continue;
    }
    if (resource.kind == HIRResourceKind::StorageImage) {
      if (resource.type.arraySize.has_value()) {
        if (resource.type.arraySize->empty()) {
          diagnostics.error(
              "vulkan.prototype-unsupported-runtime-resource-array",
              "Vulkan prototype storage image descriptor lowering does not "
              "yet support unsized/runtime resource array '" +
                  resource.name + "'");
          return false;
        }
        if (!prototypeArrayElementCount(resource.type, layoutContext).has_value()) {
          diagnostics.error(
              "vulkan.prototype-unsupported-storage-image",
              "Vulkan prototype storage image descriptor arrays require "
              "fixed-size numeric or folded-constant resource array sizes");
          return false;
        }
      }
      continue;
    }
    if (isPrototypeUniformConstantDescriptorResource(resource)) {
      if (resource.type.arraySize.has_value() &&
          resource.type.arraySize->empty()) {
        if (!vulkanRuntimeTextureSamplerDescriptorArraySupported(module,
                                                                 resource)) {
          diagnostics.error(
              "vulkan.prototype-unsupported-runtime-resource-array",
              vulkanRuntimeDescriptorArrayUnsupportedMessage(module, resource));
          return false;
        }
        continue;
      }
      if (resource.type.arraySize.has_value() &&
          !prototypeArrayElementCount(resource.type, layoutContext).has_value()) {
        diagnostics.error("vulkan.prototype-unsupported-resource",
                          "Vulkan prototype texture/sampler descriptor arrays "
                          "require fixed-size numeric or folded-constant "
                          "array sizes");
        return false;
      }
      continue;
    }
    if (!isPrototypeStorageBufferResource(resource)) {
      diagnostics.error("vulkan.prototype-unsupported-resource",
                        "Vulkan prototype binary emission currently supports "
                        "only scalar/vector arithmetic storage buffers plus "
                        "texture, storage image, and sampler descriptor "
                        "declarations");
      return false;
    }
  }
  if (!stage->workgroupSize.has_value()) {
    diagnostics.error("vulkan.prototype-missing-workgroup-size",
                      "Vulkan prototype compute binaries require an explicit "
                      "workgroup size");
    return false;
  }
  const HIRFunction *entry = entryFunction(*stage);
  if (entry == nullptr) {
    diagnostics.error("vulkan.prototype-missing-entry",
                      "Vulkan prototype binary emission requires a compute "
                      "entry function");
    return false;
  }
  if (diagnoseUnsupportedVulkanPrototypeFunctionArrayCallFeatures(
          module, *stage, diagnostics)) {
    return false;
  }
  const VulkanPrototypeArrayWriteBackParameterMap writeBackParameters =
      collectVulkanFunctionParameterArrayWriteBackParameters(module, *stage);
  if (diagnoseUnsupportedVulkanPrototypeFunctionParameterArrayWrites(
          module, *stage, writeBackParameters, diagnostics)) {
    return false;
  }
  if (!prototypeFunctionParameterArraysSupported(module, *stage, diagnostics)) {
    return false;
  }
  for (const HIRFunction &function : module.functions) {
    const auto writeBack = writeBackParameters.find(function.name);
    const std::unordered_set<std::string> &mutableArrayParameters =
        writeBack != writeBackParameters.end() ? writeBack->second
                                               : kEmptyStringSet;
    if (!prototypeBodySupported(function, stage->resources, constants, structs,
                                diagnostics, mutableArrayParameters)) {
      return false;
    }
  }
  for (const HIRFunction &function : stage->functions) {
    if (function.name == stage->entryPointName) {
      continue;
    }
    const auto writeBack = writeBackParameters.find(function.name);
    const std::unordered_set<std::string> &mutableArrayParameters =
        writeBack != writeBackParameters.end() ? writeBack->second
                                               : kEmptyStringSet;
    if (!prototypeBodySupported(function, stage->resources, constants, structs,
                                diagnostics, mutableArrayParameters)) {
      return false;
    }
  }
  if (entry->returnType.name != "void" || !entry->parameters.empty()) {
    diagnostics.error("vulkan.prototype-unsupported-signature",
                      "Vulkan prototype binary emission currently requires a "
                      "void entry function with no parameters");
    return false;
  }
  const auto entryWriteBack = writeBackParameters.find(entry->name);
  const std::unordered_set<std::string> &entryMutableArrayParameters =
      entryWriteBack != writeBackParameters.end() ? entryWriteBack->second
                                                  : kEmptyStringSet;
  if (!prototypeBodySupported(*entry, stage->resources, constants, structs,
                              diagnostics, entryMutableArrayParameters)) {
    return false;
  }
  return true;
}

std::string generateVulkanPrototypeAssembly(const HIRModule &module,
                                            DiagnosticEngine &diagnostics) {
  const HIRStage *graphicsVertex = nullptr;
  const HIRStage *graphicsFragment = nullptr;
  if (vulkanGraphicsStagePair(module, graphicsVertex, graphicsFragment)) {
    return generateVulkanGraphicsPrototypeAssembly(module, diagnostics);
  }

  if (!vulkanPrototypeBinarySupported(module, diagnostics)) {
    return "";
  }

  const HIRStage &stage = *prototypeComputeStage(module);
  const HIRWorkgroupSize &workgroup = *stage.workgroupSize;
  (void)workgroup;
  PrototypeSPIRVBuilder builder(module, stage, diagnostics);
  const HIRFunction &entry = *entryFunction(stage);
  if (!builder.emit(module, stage, entry)) {
    return "";
  }
  return builder.render(module, stage);
}

VulkanBuildResult buildVulkanPrototypeBinary(
    const HIRModule &module, const std::filesystem::path &packageDir,
    DiagnosticEngine &diagnostics,
    const TargetLegalizationResourceBindingFacts *resourceBindings,
    OptimizationLevel optimizationLevel) {
  VulkanBuildResult result;
  result.optimizationRequestedLevel =
      std::string(optimizationLevelName(optimizationLevel));
  const std::string assembly =
      generateVulkanPrototypeAssembly(module, diagnostics);
  if (diagnostics.hasErrors()) {
    return result;
  }
  if (diagnoseVulkanLegalizedResourceDeclarationMismatches(
          module, resourceBindings, diagnostics)) {
    return result;
  }

  if (!findExecutable("spirv-as")) {
    diagnostics.error("vulkan.spirv-as-missing",
                      "spirv-as is required to assemble Vulkan prototype binaries");
    return result;
  }
  if (!findExecutable("spirv-val")) {
    diagnostics.error("vulkan.spirv-val-missing",
                      "spirv-val is required to validate Vulkan prototype binaries");
    return result;
  }

  const auto backendDir = packageDir / "backend" / "vulkan";
  std::error_code error;
  std::filesystem::create_directories(backendDir, error);
  if (error) {
    diagnostics.error("artifact.create-directory",
                      "failed to create Vulkan backend directory: " +
                          error.message());
    return result;
  }

  result.assemblyPath = backendDir / (module.name + ".spvasm");
  result.spvPath = backendDir / (module.name + ".spv");
  if (!writeTextFile(result.assemblyPath, assembly, diagnostics,
                     "artifact.write-vulkan-assembly")) {
    return result;
  }

  int status = runProcess({"spirv-as", "--target-env", kVulkanNativeTargetEnv,
                           result.assemblyPath.string(), "-o",
                           result.spvPath.string()});
  if (status != 0) {
    diagnostics.error("vulkan.assemble-failed",
                      "spirv-as failed for generated Vulkan prototype assembly");
    return result;
  }

  std::optional<std::string> spirvOpt;
  if (optimizationLevel == OptimizationLevel::O2) {
    result.optimizationPolicy = "use-when-available";
    result.optimizationLevel = "-O";
    result.optimizationStatus = "skipped-tool-missing";
    result.optimizationToolStatus = "missing";
    spirvOpt = findExecutable("spirv-opt");
    if (spirvOpt) {
      result.optimizationToolStatus = "available";
    }
  }

  if (spirvOpt) {
    const std::filesystem::path optimizedPath =
        backendDir / (module.name + ".opt.spv");
    std::filesystem::remove(optimizedPath, error);
    status = runProcess({*spirvOpt,
                         std::string("--target-env=") + kVulkanNativeTargetEnv,
                         "-O",
                         result.spvPath.string(), "-o",
                         optimizedPath.string()});
    if (status != 0) {
      diagnostics.error("vulkan.optimize-failed",
                        "spirv-opt failed for generated Vulkan prototype "
                        "binary at requested optimization level " +
                            std::string(optimizationLevelName(
                                optimizationLevel)) +
                            "; no package was emitted");
      std::filesystem::remove(optimizedPath, error);
      return result;
    }
    std::error_code copyError;
    std::filesystem::copy_file(
        optimizedPath, result.spvPath,
        std::filesystem::copy_options::overwrite_existing, copyError);
    std::filesystem::remove(optimizedPath, error);
    if (copyError) {
      diagnostics.error("vulkan.optimize-write-failed",
                        "failed to replace Vulkan prototype binary with "
                        "spirv-opt output: " +
                            copyError.message());
      return result;
    }
    result.optimizationStatus = "applied";
  }

  status = runProcess({"spirv-val", "--target-env", kVulkanNativeTargetEnv,
                       result.spvPath.string()});
  if (status != 0) {
    diagnostics.error("vulkan.validate-failed",
                      "spirv-val failed for generated Vulkan prototype binary");
    return result;
  }

  if (findExecutable("spirv-dis")) {
    result.disassemblyPath =
        backendDir / (module.name + ".disassembly.spvasm");
    status = runProcess({"spirv-dis", result.spvPath.string(), "-o",
                         result.disassemblyPath.string()});
    if (status == 0) {
      result.disassemblyStatus = "emitted";
    } else {
      std::filesystem::remove(result.disassemblyPath, error);
      result.disassemblyPath.clear();
      result.disassemblyStatus = "failed";
      diagnostics.warning(
          "vulkan.disassemble-failed",
          "spirv-dis failed for generated Vulkan prototype binary; "
          "continuing without a disassembly sidecar");
    }
  }

  result.success = true;
  return result;
}

VulkanBuildResult buildVulkanPrototypeBinary(
    const HIRModule &module, const std::filesystem::path &packageDir,
    DiagnosticEngine &diagnostics, OptimizationLevel optimizationLevel) {
  const TargetLegalizationResult legalization =
      legalizeTarget(module, TargetKind::Vulkan);
  return buildVulkanPrototypeBinary(module, packageDir, diagnostics,
                                    &legalization.resourceBindings,
                                    optimizationLevel);
}

VulkanBuildResult buildVulkanPrototypeBinary(
    const HIRModule &module, const std::filesystem::path &packageDir,
    DiagnosticEngine &diagnostics,
    const TargetLegalizationResourceBindingFacts &resourceBindings,
    OptimizationLevel optimizationLevel) {
  return buildVulkanPrototypeBinary(module, packageDir, diagnostics,
                                    &resourceBindings, optimizationLevel);
}

} // namespace crossgl
