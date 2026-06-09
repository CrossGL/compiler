#include "crossgl/Backend/TargetCapabilities.h"

#include "crossgl/Backend/BackendHIR.h"
#include "crossgl/Backend/BackendPlan.h"
#include "crossgl/Backend/DirectXBackend.h"
#include "crossgl/Backend/MetalBackend.h"
#include "crossgl/Backend/OpenGLBackend.h"
#include "crossgl/Backend/ResourceArrays.h"
#include "crossgl/Backend/TargetCapabilityInventory.h"
#include "crossgl/Backend/VulkanBackend.h"
#include "crossgl/HIR/Intrinsics.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <array>
#include <sstream>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <utility>

namespace crossgl {
namespace {

constexpr std::string_view kRawStatementBackendInputDiagnostic =
    "opt.hir-raw-statement-backend-input";

static constexpr std::array<TargetCapabilityRegistryContract, 4>
    kTargetCapabilityRegistryContracts = {{
        TargetCapabilityRegistryContract{
            TargetKind::Metal, "native", "native", "native-metal-package",
            "metal.native-artifact.metallib", true, false},
        TargetCapabilityRegistryContract{
            TargetKind::Vulkan, "native", "prototype-native",
            "vulkan-prototype-package", "vulkan.native-artifact.spirv", true,
            false},
        TargetCapabilityRegistryContract{
            TargetKind::DirectX, "source-package", "native",
            "native-dxil-package", "directx.native-artifact.dxil", true, true},
        TargetCapabilityRegistryContract{
            TargetKind::OpenGL, "source-package", "planned-native",
            "glsl-lowering", "opengl.native-artifact.glsl-source", false, true},
    }};

const TargetCapabilityRegistryContract *registryContractFor(TargetKind target) {
  const TargetKind resolvedTarget =
      target == TargetKind::Auto ? defaultTargetForHost() : target;
  for (const TargetCapabilityRegistryContract &contract :
       kTargetCapabilityRegistryContracts) {
    if (contract.target == resolvedTarget) {
      return &contract;
    }
  }
  return nullptr;
}

struct CapabilityCollector {
  TargetKind target = TargetKind::Auto;
  std::vector<TargetCapability> capabilities;
  std::unordered_set<std::string> seen;

  explicit CapabilityCollector(TargetKind requestedTarget)
      : target(requestedTarget == TargetKind::Auto ? defaultTargetForHost()
                                                   : requestedTarget) {}

  void add(std::string_view kind, std::string_view name) {
    std::string key;
    key.reserve(kind.size() + name.size() + 1);
    key.append(kind);
    key.push_back('\n');
    key.append(name);
    if (!seen.insert(key).second) {
      return;
    }
    capabilities.push_back(
        TargetCapability{target, std::string(kind), std::string(name)});
  }
};

bool typeHasArray(const HIRType &type) { return type.arraySize.has_value(); }

bool typeHasRuntimeArray(const HIRType &type) {
  return type.arraySize.has_value() && type.arraySize->empty();
}

bool typeHasNestedArray(const HIRType &type) {
  return type.arraySize.has_value() &&
         type.arraySize->find("][") != std::string::npos;
}

bool typeNameContains(std::string_view name, std::string_view needle) {
  return name.find(needle) != std::string_view::npos;
}

TargetCapability rawStatementBackendInputCapability(TargetKind target) {
  const TargetKind resolvedTarget =
      target == TargetKind::Auto ? defaultTargetForHost() : target;
  return TargetCapability{resolvedTarget, "diagnostic",
                          std::string(kRawStatementBackendInputDiagnostic)};
}

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

std::span<const HIRResourceKind> directxRuntimeDescriptorResourceKinds() {
  static constexpr std::array<HIRResourceKind, 4> kinds = {
      HIRResourceKind::Uniform, HIRResourceKind::Buffer,
      HIRResourceKind::Texture, HIRResourceKind::Sampler};
  return kinds;
}

std::span<const HIRResourceKind> openGLRuntimeDescriptorResourceKinds() {
  static constexpr std::array<HIRResourceKind, 3> kinds = {
      HIRResourceKind::Buffer, HIRResourceKind::Texture,
      HIRResourceKind::Sampler};
  return kinds;
}

std::span<const HIRResourceKind> openGLRuntimeStorageBufferKinds() {
  static constexpr std::array<HIRResourceKind, 1> kinds = {
      HIRResourceKind::Buffer};
  return kinds;
}

std::span<const HIRResourceKind> openGLRuntimeTextureKinds() {
  static constexpr std::array<HIRResourceKind, 1> kinds = {
      HIRResourceKind::Texture};
  return kinds;
}

std::span<const HIRResourceKind> openGLRuntimeSamplerKinds() {
  static constexpr std::array<HIRResourceKind, 1> kinds = {
      HIRResourceKind::Sampler};
  return kinds;
}

std::string runtimeDescriptorArrayCapabilityName(const HIRResource &resource) {
  return "runtime-" + resourceKindLabel(resource.kind) + "-descriptor-array";
}

bool isRuntimeDescriptorArrayCapabilityName(std::string_view name) {
  return name == "runtime-descriptor-array" ||
         name == "runtime-storage-buffer-descriptor-array" ||
         name == "runtime-texture-descriptor-array" ||
         name == "runtime-sampler-descriptor-array" ||
         name == "runtime-uniform-descriptor-array";
}

bool directxRuntimeDescriptorArrayCapabilitiesSatisfied(
    const HIRModule &module) {
  return !runtimeDescriptorArrayLabels(module,
                                       directxRuntimeDescriptorResourceKinds())
              .empty() &&
         !directxHasUnsupportedStorageBufferArray(module) &&
         !directxHasUnsupportedRuntimeResourceArray(module);
}

bool openGLRuntimeDescriptorArrayCapabilitySatisfied(
    const HIRModule &module, std::string_view capabilityName) {
  if (openglHasUnsupportedStorageBufferArray(module) ||
      openglHasUnsupportedRuntimeResourceArray(module)) {
    return false;
  }
  if (capabilityName == "runtime-descriptor-array") {
    return !runtimeDescriptorArrayLabels(module,
                                         openGLRuntimeDescriptorResourceKinds())
                .empty();
  }
  if (capabilityName == "runtime-storage-buffer-descriptor-array") {
    return !runtimeDescriptorArrayLabels(module,
                                         openGLRuntimeStorageBufferKinds())
                .empty();
  }
  if (capabilityName == "runtime-texture-descriptor-array") {
    return !runtimeDescriptorArrayLabels(module, openGLRuntimeTextureKinds())
                .empty();
  }
  if (capabilityName == "runtime-sampler-descriptor-array") {
    return !runtimeDescriptorArrayLabels(module, openGLRuntimeSamplerKinds())
                .empty();
  }
  return false;
}

bool isVectorTypeName(std::string_view name) {
  return name == "vec2" || name == "vec3" || name == "vec4" ||
         name == "ivec2" || name == "ivec3" || name == "ivec4" ||
         name == "uvec2" || name == "uvec3" || name == "uvec4" ||
         name == "bvec2" || name == "bvec3" || name == "bvec4";
}

bool isScalarTypeName(std::string_view name) {
  return name == "float" || name == "int" || name == "uint" || name == "bool";
}

bool isMatrixTypeName(std::string_view name) {
  return name == "mat2" || name == "mat3" || name == "mat4" ||
         name == "mat2x2" || name == "mat3x3" || name == "mat4x4";
}

bool isComparisonOperator(std::string_view op) {
  return op == "<" || op == "<=" || op == ">" || op == ">=" || op == "==" ||
         op == "!=";
}

bool isLogicalOperator(std::string_view op) { return op == "&&" || op == "||"; }

bool containsNonUniformIndex(const HIRExpression &expression) {
  if (expression.kind == HIRExpressionKind::NonUniform) {
    return true;
  }
  for (const HIRExpression &child : expression.children) {
    if (containsNonUniformIndex(child)) {
      return true;
    }
  }
  return false;
}

const HIRExpression *
unwrapTargetFeatureTransparentExpression(const HIRExpression &expression) {
  const HIRExpression *current = &expression;
  while ((current->kind == HIRExpressionKind::Group ||
          current->kind == HIRExpressionKind::NonUniform) &&
         current->children.size() == 1) {
    current = &current->children.front();
  }
  return current;
}

const HIRExpression *accessRootExpression(const HIRExpression &expression) {
  const HIRExpression *current =
      unwrapTargetFeatureTransparentExpression(expression);
  while ((current->kind == HIRExpressionKind::IndexAccess ||
          current->kind == HIRExpressionKind::MemberAccess) &&
         !current->children.empty()) {
    current = unwrapTargetFeatureTransparentExpression(current->children[0]);
  }
  return current;
}

bool expressionRootIsStorageBuffer(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRResource> &resources) {
  const HIRExpression *root = accessRootExpression(expression);
  if (root->kind != HIRExpressionKind::Identifier) {
    return false;
  }
  const auto resource = resources.find(root->value);
  return resource != resources.end() &&
         resource->second.kind == HIRResourceKind::Buffer;
}

bool containsStorageBufferAccessExpression(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRResource> &resources) {
  const HIRExpression *current =
      unwrapTargetFeatureTransparentExpression(expression);
  if ((current->kind == HIRExpressionKind::IndexAccess ||
       current->kind == HIRExpressionKind::MemberAccess) &&
      expressionRootIsStorageBuffer(*current, resources)) {
    return true;
  }
  for (const HIRExpression &child : expression.children) {
    if (containsStorageBufferAccessExpression(child, resources)) {
      return true;
    }
  }
  return false;
}

std::string_view storageImageAtomicCapabilityName(std::string_view name) {
  if (name == "imageAtomicAdd") {
    return "storage-image-atomic-add";
  }
  if (name == "imageAtomicExchange") {
    return "storage-image-atomic-exchange";
  }
  if (name == "imageAtomicMin") {
    return "storage-image-atomic-min";
  }
  if (name == "imageAtomicMax") {
    return "storage-image-atomic-max";
  }
  if (name == "imageAtomicAnd") {
    return "storage-image-atomic-and";
  }
  if (name == "imageAtomicOr") {
    return "storage-image-atomic-or";
  }
  if (name == "imageAtomicXor") {
    return "storage-image-atomic-xor";
  }
  return {};
}

void addBaselineCapabilities(CapabilityCollector &collector) {
  switch (collector.target) {
  case TargetKind::Metal:
    collector.add("backend", "native-metal-package");
    collector.add("sourceLanguage", "MSL");
    collector.add("binaryFormat", "metallib");
    collector.add("toolchain", "xcrun-metal");
    collector.add("toolchain", "xcrun-metallib");
    return;
  case TargetKind::Vulkan:
    collector.add("capability", "Shader");
    collector.add("addressingModel", "Logical");
    collector.add("memoryModel", "GLSL450");
    collector.add("targetEnv", "vulkan1.2");
    collector.add("backend", "vulkan-prototype-package");
    return;
  case TargetKind::DirectX:
    collector.add("backend", "hlsl-lowering");
    collector.add("backend", "native-dxil-package");
    collector.add("toolchain", "dxc");
    collector.add("validation", "dxil-validator");
    return;
  case TargetKind::OpenGL:
    collector.add("backend", "glsl-lowering");
    collector.add("backend", "native-glsl-package");
    collector.add("toolchain", "opengl-driver");
    collector.add("validation", "glsl-program-validation");
    return;
  case TargetKind::Auto:
    break;
  }
}

void addTypeCapabilities(CapabilityCollector &collector, const HIRType &type,
                         std::string_view context) {
  if (isAtomicIntegerType(type)) {
    collector.add("type", "atomic-integer");
  }

  if (!typeHasArray(type)) {
    return;
  }
  if (typeHasRuntimeArray(type)) {
    collector.add("layout", "runtime-array");
  } else {
    collector.add("layout", "fixed-array");
  }

  if (context == "resource") {
    collector.add("resource", "descriptor-array");
  } else if (context == "struct-field") {
    collector.add("layout", typeHasRuntimeArray(type) ? "runtime-array-field"
                                                      : "fixed-array-field");
  } else if (context == "function-parameter") {
    collector.add("array", "function-parameter-array");
  } else if (context == "local") {
    collector.add("array", "local-array");
  }

  if (typeHasNestedArray(type)) {
    collector.add("array", "fixed-nested-arrays");
  }
  if (isScalarTypeName(type.name) || isVectorTypeName(type.name)) {
    collector.add("array", "scalar-vector-elements");
  } else if (isMatrixTypeName(type.name)) {
    collector.add("array", "matrix-elements");
  }
}

void addResourceCapabilities(CapabilityCollector &collector,
                             const BackendPlanResource &resource) {
  const std::string_view resourceCapability =
      backendPlanResourceFamilyCapabilityName(resource.family);
  if (!resourceCapability.empty()) {
    collector.add("resource", resourceCapability);
  }

  switch (resource.kind) {
  case HIRResourceKind::StorageImage:
    switch (resource.storageImageAccess) {
    case HIRStorageImageAccess::ReadWrite:
      collector.add("storageImage", "read-write");
      break;
    case HIRStorageImageAccess::ReadOnly:
      collector.add("storageImage", "read-only");
      break;
    case HIRStorageImageAccess::WriteOnly:
      collector.add("storageImage", "write-only");
      break;
    }
    collector.add("storageImage",
                  storageImageDimensionName(resource.type.name) + "-dimension");
    if (resource.storageImageFormat.has_value()) {
      collector.add("storageImage", *resource.storageImageFormat + "-format");
    }
    break;
  case HIRResourceKind::Uniform:
  case HIRResourceKind::Buffer:
  case HIRResourceKind::Shared:
  case HIRResourceKind::Texture:
  case HIRResourceKind::Sampler:
  case HIRResourceKind::Value:
    break;
  }

  addTypeCapabilities(collector, resource.type, "resource");
  if (resource.hasRuntimeArray) {
    collector.add("resource", "runtime-descriptor-array");
    if (resource.source != nullptr) {
      collector.add("resource",
                    runtimeDescriptorArrayCapabilityName(*resource.source));
    }
  }
  if (resource.kind == HIRResourceKind::Texture &&
      typeNameContains(resource.type.name, "Array")) {
    collector.add("texture", "array-dimension");
  }
  if (resource.kind == HIRResourceKind::StorageImage &&
      typeNameContains(resource.type.name, "Array")) {
    collector.add("storageImage", "array-dimension");
  }
  if (resource.kind == HIRResourceKind::Texture &&
      typeNameContains(resource.type.name, "Cube")) {
    collector.add("texture", "cube-dimension");
  }
  if (resource.kind == HIRResourceKind::Texture &&
      typeNameContains(resource.type.name, "3D")) {
    collector.add("texture", "3d-dimension");
  }
  if (resource.kind == HIRResourceKind::Texture &&
      typeNameContains(resource.type.name, "Shadow")) {
    collector.add("texture", "depth-compare-format");
  }
  if (resource.kind == HIRResourceKind::Buffer &&
      typeNameContains(resource.type.name, "vec")) {
    collector.add("layout", "vector-storage-buffer");
  }
}

void addNonUniformDescriptorIndexCapabilities(CapabilityCollector &collector,
                                              const HIRResource &resource) {
  const HIRNonUniformDescriptorResourceFamily family =
      nonUniformDescriptorResourceFamily(resource.kind);
  if (family == HIRNonUniformDescriptorResourceFamily::Other) {
    return;
  }
  collector.add("operation", "nonuniform-descriptor-index");
  collector.add("operation",
                "nonuniform-" + nonUniformDescriptorResourceFamilyName(family) +
                    "-descriptor-index");
}

void addExpressionCapabilities(
    CapabilityCollector &collector, const HIRExpression &expression,
    const std::unordered_map<std::string, HIRResource> &resources) {
  switch (expression.kind) {
  case HIRExpressionKind::IndexAccess:
    collector.add("operation", "index-access");
    if (expression.children.size() >= 2 &&
        containsNonUniformIndex(expression.children[1]) &&
        expression.children[0].kind == HIRExpressionKind::Identifier) {
      const auto resource = resources.find(expression.children[0].value);
      if (resource != resources.end() &&
          resource->second.type.arraySize.has_value() &&
          nonUniformDescriptorResourceFamily(resource->second.kind) !=
              HIRNonUniformDescriptorResourceFamily::Other) {
        addNonUniformDescriptorIndexCapabilities(collector, resource->second);
        if (collector.target == TargetKind::Vulkan) {
          collector.add("extension", "SPV_EXT_descriptor_indexing");
          collector.add("capability", "ShaderNonUniformEXT");
          if (resource->second.kind == HIRResourceKind::Texture ||
              resource->second.kind == HIRResourceKind::Sampler) {
            collector.add("capability",
                          "SampledImageArrayNonUniformIndexingEXT");
          } else if (resource->second.kind == HIRResourceKind::Buffer) {
            collector.add("capability",
                          "StorageBufferArrayNonUniformIndexingEXT");
          } else if (resource->second.kind == HIRResourceKind::StorageImage) {
            collector.add("capability",
                          "StorageImageArrayNonUniformIndexingEXT");
          }
        } else if (collector.target == TargetKind::DirectX) {
          collector.add("intrinsic", "NonUniformResourceIndex");
        } else if (collector.target == TargetKind::OpenGL) {
          collector.add("extension", "GL_EXT_nonuniform_qualifier");
        }
      }
    }
    break;
  case HIRExpressionKind::NonUniform:
    collector.add("operation", "nonuniform-descriptor-index");
    break;
  case HIRExpressionKind::Call:
    if (expression.value == "workgroupBarrier" ||
        expression.value == "barrier") {
      collector.add("operation", "workgroup-barrier");
    } else if (expression.value == "imageLoad") {
      collector.add("operation", "storage-image-read");
    } else if (expression.value == "imageStore") {
      collector.add("operation", "storage-image-write");
    } else if (const std::string_view imageAtomicCapability =
                   storageImageAtomicCapabilityName(expression.value);
               !imageAtomicCapability.empty()) {
      collector.add("operation", "storage-image-read");
      collector.add("operation", "storage-image-write");
      collector.add("operation", imageAtomicCapability);
    } else if (isHIRAtomicIntegerReadModifyWriteIntrinsic(expression.value)) {
      collector.add("operation", hirAtomicIntegerReadModifyWriteCapabilityName(
                                     expression.value));
      if (!expression.children.empty() &&
          isAtomicIntegerType(expression.children.front().type)) {
        collector.add("type", "atomic-integer");
      }
    }
    break;
  case HIRExpressionKind::Constructor:
    if (isVectorTypeName(expression.type.name)) {
      collector.add("operation", "vector-constructor");
    } else if (isMatrixTypeName(expression.type.name)) {
      collector.add("operation", "matrix-constructor");
    } else if (isScalarTypeName(expression.type.name)) {
      collector.add("operation", "scalar-constructor");
    }
    break;
  case HIRExpressionKind::Unary:
    if (expression.value == "!") {
      collector.add("operation", "scalar-logical");
    }
    break;
  case HIRExpressionKind::Binary:
    // Preserve the original binary-operation feature ABI: every binary
    // expression is classified as scalar/vector arithmetic by result type.
    if (isVectorTypeName(expression.type.name)) {
      collector.add("operation", "vector-arithmetic");
    } else {
      collector.add("operation", "scalar-arithmetic");
    }
    if (isComparisonOperator(expression.value)) {
      const bool vectorOperand =
          expression.children.size() >= 2 &&
          (isVectorTypeName(expression.children[0].type.name) ||
           isVectorTypeName(expression.children[1].type.name));
      collector.add("operation",
                    vectorOperand ? "vector-comparison" : "scalar-comparison");
    } else if (isLogicalOperator(expression.value)) {
      collector.add("operation", "scalar-logical");
    }
    break;
  case HIRExpressionKind::Select:
    collector.add("operation", "select-expression");
    break;
  case HIRExpressionKind::TextureSample:
    collector.add("operation", "texture-sample");
    if (expression.value == "textureLod") {
      collector.add("operation", "texture-explicit-lod");
    }
    break;
  case HIRExpressionKind::TextureCompare:
    collector.add("operation", "texture-shadow-compare");
    if (expression.value == "textureCompareLod") {
      collector.add("operation", "texture-shadow-compare-explicit-lod");
    }
    break;
  case HIRExpressionKind::TextureCompareLodManual:
    collector.add("operation", "texture-shadow-compare-explicit-lod-manual");
    if (expression.value == "textureCompareLodManualOffset") {
      collector.add("operation",
                    "texture-shadow-compare-explicit-lod-manual-offset");
    } else if (expression.value == "textureCompareLodManualGather2x2") {
      collector.add("operation",
                    "texture-shadow-compare-explicit-lod-manual-gather-2x2");
    } else if (manualTextureCompareKernelAnalysis(expression).has_value()) {
      collector.add("operation",
                    "texture-shadow-compare-explicit-lod-manual-kernel-list");
    }
    break;
  default:
    break;
  }

  for (const HIRExpression &child : expression.children) {
    addExpressionCapabilities(collector, child, resources);
  }
}

void addStatementCapabilities(
    CapabilityCollector &collector, const HIRStatement &statement,
    const std::unordered_map<std::string, HIRResource> &resources) {
  if (statement.kind == HIRStatementKind::Declaration) {
    collector.add("operation", "local-declaration");
    addTypeCapabilities(collector, statement.declaredType, "local");
    if (containsStorageBufferAccessExpression(statement.value, resources)) {
      collector.add("operation", "storage-buffer-read");
    }
  } else if (statement.kind == HIRStatementKind::Assignment) {
    if (containsStorageBufferAccessExpression(statement.target, resources)) {
      collector.add("operation", "storage-buffer-write");
    }
    if (containsStorageBufferAccessExpression(statement.value, resources)) {
      collector.add("operation", "storage-buffer-read");
    }
  } else if (statement.kind == HIRStatementKind::If) {
    collector.add("controlFlow", "structured-selection");
  } else if (statement.kind == HIRStatementKind::For) {
    collector.add("controlFlow", "structured-loop");
  } else if (statement.kind == HIRStatementKind::Raw) {
    collector.add("diagnostic", kRawStatementBackendInputDiagnostic);
  }

  addExpressionCapabilities(collector, statement.target, resources);
  addExpressionCapabilities(collector, statement.value, resources);
  for (const HIRStatement &child : statement.initializer) {
    addStatementCapabilities(collector, child, resources);
  }
  for (const HIRStatement &child : statement.update) {
    addStatementCapabilities(collector, child, resources);
  }
  for (const HIRStatement &child : statement.body) {
    addStatementCapabilities(collector, child, resources);
  }
  for (const HIRStatement &child : statement.elseBody) {
    addStatementCapabilities(collector, child, resources);
  }
}

void addFunctionCapabilities(
    CapabilityCollector &collector, const HIRFunction &function,
    const std::unordered_map<std::string, HIRResource> &resources) {
  for (const HIRParameter &parameter : function.parameters) {
    addTypeCapabilities(collector, parameter.type, "function-parameter");
  }
  for (const HIRStatement &statement : function.body) {
    addStatementCapabilities(collector, statement, resources);
  }
}

void addStageCapabilities(CapabilityCollector &collector,
                          const BackendPlanStageInterface &stage) {
  if (stage.stage == "vertex") {
    collector.add("stage", "vertex-shader");
  } else if (stage.stage == "fragment") {
    collector.add("stage", "fragment-shader");
  } else if (stage.stage == "compute") {
    collector.add("stage", "compute-kernel");
  } else {
    collector.add("stage", stage.stage);
  }

  if (stage.workgroupSize.has_value()) {
    collector.add("execution", "workgroup-size");
  }
  for (const BackendPlanResource &resource : stage.resources) {
    addResourceCapabilities(collector, resource);
  }
  std::unordered_map<std::string, HIRResource> resources;
  for (const BackendPlanResource &resource : stage.resources) {
    if (resource.source != nullptr) {
      resources[resource.name] = *resource.source;
    }
  }
  if (stage.source != nullptr) {
    for (const HIRFunction &function : stage.source->functions) {
      addFunctionCapabilities(collector, function, resources);
    }
  }
}

void addStructCapabilities(CapabilityCollector &collector,
                           const HIRStruct &structure) {
  for (const HIRField &field : structure.fields) {
    addTypeCapabilities(collector, field.type, "struct-field");
  }
}

bool capabilitySatisfiedByTextualScaffold(const HIRModule &module,
                                          const TargetCapability &capability) {
  const bool isDirectXScaffold = capability.target == TargetKind::DirectX &&
                                 directxTextualBackendSupported(module);
  const bool isOpenGLScaffold = capability.target == TargetKind::OpenGL &&
                                openglTextualBackendSupported(module);
  if (!isDirectXScaffold && !isOpenGLScaffold) {
    return false;
  }

  if (capability.kind == "backend") {
    return (capability.target == TargetKind::DirectX &&
            capability.name == "hlsl-lowering") ||
           (capability.target == TargetKind::OpenGL &&
            capability.name == "glsl-lowering");
  }
  if (capability.kind == "stage") {
    return capability.name == "compute-kernel" ||
           capability.name == "vertex-shader" ||
           capability.name == "fragment-shader";
  }
  if (capability.kind == "execution") {
    return capability.name == "workgroup-size";
  }
  if (capability.kind == "resource") {
    if (isRuntimeDescriptorArrayCapabilityName(capability.name)) {
      if (capability.target == TargetKind::DirectX) {
        return directxRuntimeDescriptorArrayCapabilitiesSatisfied(module);
      }
      if (capability.target == TargetKind::OpenGL) {
        return openGLRuntimeDescriptorArrayCapabilitySatisfied(module,
                                                               capability.name);
      }
      return false;
    }
    return capability.name == "storage-buffer" ||
           capability.name == "uniform-buffer" ||
           capability.name == "sampled-texture" ||
           capability.name == "storage-image" ||
           capability.name == "sampler-state" ||
           capability.name == "descriptor-array";
  }
  if (capability.kind == "texture") {
    return capability.name == "3d-dimension" ||
           capability.name == "cube-dimension" ||
           capability.name == "array-dimension" ||
           capability.name == "depth-compare-format";
  }
  if (capability.kind == "layout") {
    if (capability.name == "runtime-array") {
      if (capability.target == TargetKind::DirectX) {
        return directxRuntimeDescriptorArrayCapabilitiesSatisfied(module);
      }
      if (capability.target == TargetKind::OpenGL) {
        return openGLRuntimeDescriptorArrayCapabilitySatisfied(
            module, "runtime-descriptor-array");
      }
      return false;
    }
    return capability.name == "vector-storage-buffer" ||
           capability.name == "fixed-array" ||
           capability.name == "fixed-array-field";
  }
  if (capability.kind == "array") {
    return capability.name == "function-parameter-array" ||
           capability.name == "local-array" ||
           capability.name == "fixed-nested-arrays" ||
           capability.name == "scalar-vector-elements" ||
           capability.name == "matrix-elements";
  }
  if (capability.kind == "operation") {
    return capability.name == "local-declaration" ||
           capability.name == "atomic-add" || capability.name == "atomic-max" ||
           capability.name == "atomic-min" ||
           capability.name == "workgroup-barrier" ||
           capability.name == "storage-buffer-read" ||
           capability.name == "storage-buffer-write" ||
           capability.name == "storage-image-read" ||
           capability.name == "storage-image-write" ||
           capability.name == "storage-image-atomic-add" ||
           capability.name == "storage-image-atomic-exchange" ||
           capability.name == "storage-image-atomic-min" ||
           capability.name == "storage-image-atomic-max" ||
           capability.name == "storage-image-atomic-and" ||
           capability.name == "storage-image-atomic-or" ||
           capability.name == "storage-image-atomic-xor" ||
           capability.name == "index-access" ||
           capability.name == "scalar-arithmetic" ||
           capability.name == "vector-arithmetic" ||
           capability.name == "scalar-comparison" ||
           capability.name == "vector-comparison" ||
           capability.name == "scalar-logical" ||
           capability.name == "select-expression" ||
           capability.name == "scalar-constructor" ||
           capability.name == "vector-constructor" ||
           capability.name == "matrix-constructor" ||
           capability.name == "nonuniform-descriptor-index" ||
           capability.name == "nonuniform-uniform-buffer-descriptor-index" ||
           capability.name == "nonuniform-texture-descriptor-index" ||
           capability.name == "nonuniform-sampler-descriptor-index" ||
           capability.name == "nonuniform-storage-image-descriptor-index" ||
           capability.name == "nonuniform-storage-buffer-descriptor-index" ||
           capability.name == "texture-sample" ||
           capability.name == "texture-explicit-lod" ||
           capability.name == "texture-shadow-compare" ||
           capability.name == "texture-shadow-compare-explicit-lod" ||
           capability.name == "texture-shadow-compare-explicit-lod-manual" ||
           capability.name ==
               "texture-shadow-compare-explicit-lod-manual-offset" ||
           capability.name ==
               "texture-shadow-compare-explicit-lod-manual-gather-2x2" ||
           capability.name ==
               "texture-shadow-compare-explicit-lod-manual-kernel-list" ||
           capability.name ==
               "texture-shadow-compare-explicit-lod-manual-kernel-4" ||
           capability.name ==
               "texture-shadow-compare-explicit-lod-manual-kernel-8";
  }
  if (capability.kind == "storageImage") {
    return capability.name == "read-write" || capability.name == "read-only" ||
           capability.name == "write-only" ||
           capability.name == "2d-dimension" ||
           capability.name == "2d_array-dimension" ||
           capability.name == "array-dimension" ||
           capability.name == "rgba32f-format" ||
           capability.name == "rgba32i-format" ||
           capability.name == "rgba32ui-format" ||
           capability.name == "r32f-format" ||
           capability.name == "r32i-format" ||
           capability.name == "r32ui-format";
  }
  if (capability.kind == "intrinsic") {
    return capability.target == TargetKind::DirectX &&
           capability.name == "NonUniformResourceIndex";
  }
  if (capability.kind == "type") {
    return capability.name == "atomic-integer";
  }
  if (capability.kind == "extension") {
    return capability.target == TargetKind::OpenGL &&
           capability.name == "GL_EXT_nonuniform_qualifier";
  }
  if (capability.kind == "controlFlow") {
    return capability.name == "structured-selection" ||
           capability.name == "structured-loop";
  }
  return false;
}

bool sourcePackageSupported(const HIRModule &module, TargetKind target,
                            DiagnosticEngine *diagnostics = nullptr) {
  const TargetCapabilityRegistryContract *contract =
      registryContractFor(target);
  if (contract == nullptr || !contract->sourcePackageSelectable) {
    return false;
  }

  DiagnosticEngine discardDiagnostics;
  DiagnosticEngine &sourceDiagnostics =
      diagnostics == nullptr ? discardDiagnostics : *diagnostics;
  switch (contract->target) {
  case TargetKind::DirectX:
    return directxSourcePackageSupported(module, sourceDiagnostics);
  case TargetKind::OpenGL:
    return openGLSourcePackageSupported(module, sourceDiagnostics);
  case TargetKind::Auto:
  case TargetKind::Metal:
  case TargetKind::Vulkan:
    return false;
  }
  return false;
}

bool nativePackageSupported(const HIRModule &module, TargetKind target,
                            DiagnosticEngine *diagnostics = nullptr) {
  const TargetKind resolvedTarget =
      target == TargetKind::Auto ? defaultTargetForHost() : target;
  const TargetCapabilityRegistryContract *contract =
      registryContractFor(resolvedTarget);
  if (contract == nullptr || !contract->nativeImplemented) {
    return false;
  }

  DiagnosticEngine discardDiagnostics;
  DiagnosticEngine &nativeDiagnostics =
      diagnostics == nullptr ? discardDiagnostics : *diagnostics;
  switch (resolvedTarget) {
  case TargetKind::Metal:
    return metalNativeBackendSupported(module, nativeDiagnostics);
  case TargetKind::Vulkan:
    return vulkanPrototypeBinarySupported(module, nativeDiagnostics);
  case TargetKind::DirectX:
    directxSourcePackageSupported(module, nativeDiagnostics);
    return false;
  case TargetKind::OpenGL:
    return true;
  case TargetKind::Auto:
    break;
  }
  return false;
}

std::vector<TargetCapability>
nativePredicateMissingCapabilities(TargetKind target,
                                   const DiagnosticEngine &diagnostics) {
  CapabilityCollector collector(target);
  const TargetCapabilityRegistryContract *contract =
      registryContractFor(collector.target);
  if (contract != nullptr && !contract->baselineBackendCapability.empty()) {
    collector.add("backend", contract->baselineBackendCapability);
  }
  if (collector.target == TargetKind::DirectX) {
    collector.add("toolchain", "dxc");
    collector.add("validation", "dxil-validator");
  }
  for (const Diagnostic &diagnostic : diagnostics.diagnostics()) {
    if (!diagnostic.code.empty()) {
      collector.add("diagnostic", diagnostic.code);
    }
  }
  return std::move(collector.capabilities);
}

std::vector<TargetCapability>
sourcePredicateMissingCapabilities(TargetKind target,
                                   const DiagnosticEngine &diagnostics) {
  CapabilityCollector collector(target);
  const TargetCapabilityRegistryContract *contract =
      registryContractFor(collector.target);
  if (contract == nullptr || !contract->sourcePackageSelectable ||
      contract->baselineBackendCapability.empty()) {
    return {};
  }
  collector.add("backend", contract->baselineBackendCapability);
  for (const Diagnostic &diagnostic : diagnostics.diagnostics()) {
    if (!diagnostic.code.empty()) {
      collector.add("diagnostic", diagnostic.code);
    }
  }
  return std::move(collector.capabilities);
}

bool isSourcePackageTarget(TargetKind target) {
  if (target == TargetKind::DirectX || target == TargetKind::OpenGL) {
    const TargetCapabilityRegistryContract *contract =
        registryContractFor(target);
    return contract != nullptr && contract->sourcePackageSelectable;
  }
  return false;
}

std::vector<TargetCapability>
nativePredicateMissingCapabilities(const HIRModule &module, TargetKind target) {
  const TargetKind resolvedTarget =
      target == TargetKind::Auto ? defaultTargetForHost() : target;
  const TargetCapabilityRegistryContract *contract =
      registryContractFor(resolvedTarget);
  if (contract == nullptr || !contract->nativeImplemented) {
    return {};
  }

  DiagnosticEngine diagnostics;
  if (nativePackageSupported(module, resolvedTarget, &diagnostics)) {
    return {};
  }
  return nativePredicateMissingCapabilities(resolvedTarget, diagnostics);
}

std::string packageModeForDecision(bool nativeSupported, bool sourceSupported) {
  if (nativeSupported) {
    return "native";
  }
  if (sourceSupported) {
    return "source-package";
  }
  return "unsupported";
}

std::string packageReasonForDecision(bool nativeSupported, bool sourceSupported,
                                     bool packageBuildSupported) {
  if (nativeSupported) {
    return "native-package-available";
  }
  if (sourceSupported) {
    return "source-package-available";
  }
  if (packageBuildSupported) {
    return "package-build-available";
  }
  return "unsupported";
}

std::size_t packageRankScoreForDecision(bool nativeSupported,
                                        bool sourceSupported) {
  if (nativeSupported) {
    return 0;
  }
  if (sourceSupported) {
    return 1;
  }
  return 2;
}

TargetKind concretePreferredTarget(TargetKind preferredTarget) {
  return preferredTarget == TargetKind::Auto ? defaultTargetForHost()
                                             : preferredTarget;
}

} // namespace

std::string targetCapabilityId(const TargetCapability &capability) {
  return targetName(capability.target) + "." + capability.kind + "." +
         capability.name;
}

std::span<const TargetCapabilityRegistryContract>
targetCapabilityRegistryContracts() {
  return kTargetCapabilityRegistryContracts;
}

const TargetCapabilityRegistryContract *
targetCapabilityRegistryContract(TargetKind target) {
  return registryContractFor(target);
}

std::vector<TargetCapability> targetBaselineCapabilities(TargetKind target) {
  CapabilityCollector collector(target);
  addBaselineCapabilities(collector);
  return std::move(collector.capabilities);
}

TargetCapabilityInventory
collectTargetCapabilityInventory(const HIRModule &module, TargetKind target) {
  CapabilityCollector collector(target);
  const BackendPlan plan = buildBackendPlan(module);
  addBaselineCapabilities(collector);
  for (const HIRStruct &structure : module.structs) {
    addStructCapabilities(collector, structure);
  }
  for (const BackendPlanStageInterface &stage : plan.stages) {
    addStageCapabilities(collector, stage);
  }
  const std::unordered_map<std::string, HIRResource> noResources;
  for (const HIRFunction &function : module.functions) {
    addFunctionCapabilities(collector, function, noResources);
  }

  TargetCapabilityInventory inventory;
  inventory.target = collector.target;
  inventory.requiredCapabilities = std::move(collector.capabilities);
  return inventory;
}

std::vector<TargetCapability> targetFeatureRequirements(const HIRModule &module,
                                                        TargetKind target) {
  return collectTargetCapabilityInventory(module, target).requiredCapabilities;
}

std::vector<TargetCapability> missingTargetCapabilities(const HIRModule &module,
                                                        TargetKind target) {
  const TargetKind resolvedTarget =
      target == TargetKind::Auto ? defaultTargetForHost() : target;
  const TargetCapabilityRegistryContract *contract =
      registryContractFor(resolvedTarget);
  const bool nativeImplemented = contract == nullptr
                                     ? targetInfo(resolvedTarget).implemented
                                     : contract->nativeImplemented;
  if (moduleContainsRawStatement(module)) {
    return {rawStatementBackendInputCapability(resolvedTarget)};
  }
  if (nativeImplemented) {
    return nativePredicateMissingCapabilities(module, resolvedTarget);
  }
  if (isSourcePackageTarget(resolvedTarget)) {
    DiagnosticEngine sourceDiagnostics;
    if (!sourcePackageSupported(module, resolvedTarget, &sourceDiagnostics)) {
      return sourcePredicateMissingCapabilities(resolvedTarget,
                                                sourceDiagnostics);
    }
  }
  std::vector<TargetCapability> missing;
  for (const TargetCapability &capability :
       targetFeatureRequirements(module, resolvedTarget)) {
    if (!capabilitySatisfiedByTextualScaffold(module, capability)) {
      missing.push_back(capability);
    }
  }
  return missing;
}

TargetPackageDecision targetPackageDecision(const HIRModule &module,
                                            TargetKind target) {
  const TargetKind resolvedTarget =
      target == TargetKind::Auto ? defaultTargetForHost() : target;
  const TargetInfo info = targetInfo(resolvedTarget);
  const TargetCapabilityRegistryContract *contract =
      registryContractFor(resolvedTarget);
  const bool nativeImplemented =
      contract == nullptr ? info.implemented : contract->nativeImplemented;
  const std::vector<TargetCapability> requiredCapabilities =
      targetFeatureRequirements(module, resolvedTarget);
  if (moduleContainsRawStatement(module)) {
    TargetPackageDecision decision;
    decision.target = resolvedTarget;
    decision.targetName = info.name;
    decision.nativeImplemented = nativeImplemented;
    decision.sourcePackageSupported = false;
    decision.packageBuildSupported = false;
    decision.packageMode = "unsupported";
    decision.packageDecisionReason = "unsupported";
    decision.packageRankScore = 2;
    decision.requiredCapabilities = requiredCapabilities;
    decision.missingCapabilities = {
        rawStatementBackendInputCapability(resolvedTarget)};
    return decision;
  }

  DiagnosticEngine nativeDiagnostics;
  const bool supportsNativePackage =
      nativePackageSupported(module, resolvedTarget, &nativeDiagnostics);
  DiagnosticEngine sourceDiagnostics;
  const bool supportsSourcePackage =
      sourcePackageSupported(module, resolvedTarget, &sourceDiagnostics);

  TargetPackageDecision decision;
  decision.target = resolvedTarget;
  decision.targetName = info.name;
  decision.nativeImplemented = nativeImplemented;
  decision.sourcePackageSupported = supportsSourcePackage;
  decision.packageBuildSupported =
      supportsNativePackage || supportsSourcePackage;
  decision.packageMode =
      packageModeForDecision(supportsNativePackage, supportsSourcePackage);
  decision.packageDecisionReason =
      packageReasonForDecision(supportsNativePackage, supportsSourcePackage,
                               decision.packageBuildSupported);
  decision.packageRankScore =
      packageRankScoreForDecision(supportsNativePackage, supportsSourcePackage);
  decision.requiredCapabilities = requiredCapabilities;
  if (nativeImplemented && !supportsNativePackage) {
    decision.missingCapabilities =
        nativePredicateMissingCapabilities(resolvedTarget, nativeDiagnostics);
    if (isSourcePackageTarget(resolvedTarget) && !supportsSourcePackage) {
      decision.diagnostics = sourceDiagnostics.diagnostics();
    }
  } else if (isSourcePackageTarget(resolvedTarget) && !supportsSourcePackage) {
    decision.missingCapabilities =
        sourcePredicateMissingCapabilities(resolvedTarget, sourceDiagnostics);
    decision.diagnostics = sourceDiagnostics.diagnostics();
  } else {
    decision.missingCapabilities =
        missingTargetCapabilities(module, resolvedTarget);
  }
  return decision;
}

std::vector<TargetPackageDecision>
targetPackageDecisions(const HIRModule &module) {
  std::vector<TargetPackageDecision> decisions;
  for (const TargetInfo &target : allTargets()) {
    decisions.push_back(targetPackageDecision(module, target.kind));
  }
  return decisions;
}

TargetPackageSelection selectRecommendedPackageTarget(
    const std::vector<TargetPackageDecision> &decisions,
    TargetKind preferredTarget) {
  const TargetKind preferred = concretePreferredTarget(preferredTarget);
  TargetPackageSelection selection;
  selection.preferredTarget = preferred;
  selection.selectedTarget = preferred;

  const TargetPackageDecision *selected = nullptr;
  for (const TargetPackageDecision &decision : decisions) {
    if (!decision.packageBuildSupported) {
      continue;
    }
    if (selected == nullptr ||
        decision.packageRankScore < selected->packageRankScore ||
        (decision.packageRankScore == selected->packageRankScore &&
         decision.target == preferred && selected->target != preferred)) {
      selected = &decision;
    }
  }

  if (selected != nullptr) {
    selection.selectedTarget = selected->target;
    selection.selectedTargetBuildable = true;
  }
  return selection;
}

TargetPackageSelection
selectRecommendedPackageTarget(const HIRModule &module,
                               TargetKind preferredTarget) {
  return selectRecommendedPackageTarget(targetPackageDecisions(module),
                                        preferredTarget);
}

std::string
formatTargetCapabilityList(const std::vector<TargetCapability> &capabilities,
                           std::size_t maxItems) {
  std::ostringstream out;
  const std::size_t count = maxItems == 0 || maxItems > capabilities.size()
                                ? capabilities.size()
                                : maxItems;
  for (std::size_t index = 0; index < count; ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << targetCapabilityId(capabilities[index]);
  }
  if (count < capabilities.size()) {
    out << ", +" << (capabilities.size() - count) << " more";
  }
  return out.str();
}

} // namespace crossgl
