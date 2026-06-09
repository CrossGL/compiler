#include "crossgl/Backend/MetalBackend.h"

#include "crossgl/Backend/BackendExpressions.h"
#include "crossgl/Backend/BackendHIR.h"
#include "crossgl/Backend/BackendIntrinsics.h"
#include "crossgl/Backend/BackendPlan.h"
#include "crossgl/Backend/ResourceArrays.h"
#include "crossgl/Backend/TargetLegalization.h"
#include "crossgl/Backend/TextureCompare.h"
#include "crossgl/Basic/Json.h"
#include "crossgl/Driver/StorageLayout.h"
#include "crossgl/Frontend/TokenText.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <string_view>
#include <type_traits>
#include <unordered_map>
#include <vector>

namespace crossgl {
namespace {

constexpr std::string_view kRawStatementBackendInputDiagnostic =
    "opt.hir-raw-statement-backend-input";
constexpr std::string_view kMetalRuntimeResourceDescriptorArrayTableTypePrefix =
    "CrossGLMetalRuntimeResourceDescriptorArrayTable_";
constexpr std::size_t kMetalRuntimeResourceDescriptorArrayTableCapacity = 1024;

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
      "Metal native backend input cannot contain HIR raw statements; "
      "lower them to structured HIR before backend emission");
  return true;
}

bool verifyMetalToolOutput(const std::filesystem::path &path,
                           std::string_view diagnosticCode,
                           std::string_view toolName,
                           std::string_view artifactName,
                           DiagnosticEngine &diagnostics) {
  std::error_code error;
  if (!std::filesystem::is_regular_file(path, error) || error) {
    diagnostics.error(
        std::string(diagnosticCode),
        std::string(toolName) +
            " reported success but did not produce a regular " +
            std::string(artifactName) + " artifact");
    return false;
  }

  const std::uintmax_t size = std::filesystem::file_size(path, error);
  if (error || size == 0) {
    diagnostics.error(std::string(diagnosticCode),
                      std::string(toolName) +
                          " reported success but produced an empty " +
                          std::string(artifactName) + " artifact");
    return false;
  }

  return true;
}

std::string jsonStringArray(const std::vector<std::string> &values) {
  std::ostringstream out;
  out << "[";
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << "\"" << escapeJson(values[index]) << "\"";
  }
  out << "]";
  return out.str();
}

std::string metalCompileOptionsJson(const HIRModule &module,
                                    const MetalCompileOptions &options) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"target\": \"metal\",\n"
      << "  \"module\": \"" << escapeJson(module.name) << "\",\n"
      << "  \"policy\": {\n"
      << "    \"name\": \"" << escapeJson(options.policyName) << "\",\n"
      << "    \"profile\": \"" << escapeJson(options.profileName) << "\",\n"
      << "    \"requestedOptimizationLevel\": \""
      << escapeJson(options.requestedOptimizationLevel) << "\",\n"
      << "    \"optimizationLevel\": \""
      << escapeJson(options.optimizationLevel) << "\",\n"
      << "    \"debugInfo\": " << (options.debugInfo ? "true" : "false")
      << ",\n"
      << "    \"description\": \"" << escapeJson(options.description)
      << "\"\n"
      << "  },\n"
      << "  \"compile\": {\n"
      << "    \"tool\": \"xcrun metal\",\n"
      << "    \"sdk\": \"macosx\",\n"
      << "    \"flags\": " << jsonStringArray(options.metalFlags) << "\n"
      << "  },\n"
      << "  \"library\": {\n"
      << "    \"tool\": \"xcrun metallib\",\n"
      << "    \"flags\": " << jsonStringArray(options.metallibFlags) << "\n"
      << "  }\n"
      << "}\n";
  return out.str();
}

std::vector<std::string>
metalCompileCommand(const MetalCompileOptions &options,
                    const std::filesystem::path &sourcePath,
                    const std::filesystem::path &airPath) {
  std::vector<std::string> command{"xcrun", "-sdk", "macosx", "metal"};
  command.insert(command.end(), options.metalFlags.begin(),
                 options.metalFlags.end());
  command.push_back("-c");
  command.push_back(sourcePath.string());
  command.push_back("-o");
  command.push_back(airPath.string());
  return command;
}

std::vector<std::string>
metalLibraryCommand(const MetalCompileOptions &options,
                    const std::filesystem::path &airPath,
                    const std::filesystem::path &metallibPath) {
  std::vector<std::string> command{"xcrun", "-sdk", "macosx", "metallib"};
  command.insert(command.end(), options.metallibFlags.begin(),
                 options.metallibFlags.end());
  command.push_back(airPath.string());
  command.push_back("-o");
  command.push_back(metallibPath.string());
  return command;
}

std::vector<std::string_view>
splitMetalArrayDimensions(std::string_view arraySize) {
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

std::string mapMetalFixedArrayType(std::string elementType,
                                   std::string_view arraySize) {
  const std::vector<std::string_view> dimensions =
      splitMetalArrayDimensions(arraySize);
  for (auto dimension = dimensions.rbegin(); dimension != dimensions.rend();
       ++dimension) {
    elementType = "array<" + elementType + ", " + std::string(*dimension) + ">";
  }
  return elementType;
}

std::optional<std::string> mapMetalAtomicType(std::string_view name) {
  if (name == "atomic<int>") {
    return "atomic_int";
  }
  if (name == "atomic<uint>") {
    return "atomic_uint";
  }
  return std::nullopt;
}

std::optional<std::string>
metalStorageImageScalarType(std::string_view imageName) {
  const std::string payload = storageImagePayloadVectorTypeName(imageName);
  if (payload == "ivec4") {
    return "int";
  }
  if (payload == "uvec4") {
    return "uint";
  }
  if (payload == "vec4") {
    return "float";
  }
  return std::nullopt;
}

template <typename Resource>
std::string metalStorageImageAccessMode(const Resource &resource) {
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

std::optional<std::string>
mapMetalStorageImageType(const HIRType &type,
                         std::string_view accessMode = "read_write") {
  const std::string imageName = baseTypeName(type);
  const std::optional<std::string> scalarType =
      metalStorageImageScalarType(imageName);
  if (!scalarType.has_value()) {
    return std::nullopt;
  }

  const std::string dimension = storageImageDimensionName(imageName);
  std::string mapped;
  if (dimension == "2d_array") {
    mapped = "texture2d_array<" + *scalarType +
             ", access::" + std::string(accessMode) + ">";
  } else if (dimension == "2d") {
    mapped = "texture2d<" + *scalarType +
             ", access::" + std::string(accessMode) + ">";
  } else {
    return std::nullopt;
  }
  if (type.arraySize.has_value() && !type.arraySize->empty()) {
    return mapMetalFixedArrayType(std::move(mapped), *type.arraySize);
  }
  return mapped;
}

std::string mapMetalType(const HIRType &type) {
  static const std::unordered_map<std::string, std::string> types = {
      {"void", "void"},
      {"bool", "bool"},
      {"int", "int"},
      {"uint", "uint"},
      {"float", "float"},
      {"double", "double"},
      {"half", "half"},
      {"vec2", "float2"},
      {"vec3", "float3"},
      {"vec4", "float4"},
      {"ivec2", "int2"},
      {"ivec3", "int3"},
      {"ivec4", "int4"},
      {"uvec2", "uint2"},
      {"uvec3", "uint3"},
      {"uvec4", "uint4"},
      {"bvec2", "bool2"},
      {"bvec3", "bool3"},
      {"bvec4", "bool4"},
      {"mat2", "float2x2"},
      {"mat2x2", "float2x2"},
      {"mat3", "float3x3"},
      {"mat3x3", "float3x3"},
      {"mat4", "float4x4"},
      {"mat4x4", "float4x4"},
      {"sampler", "sampler"},
      {"comparison_sampler", "sampler"},
      {"sampler2D", "texture2d<float>"},
      {"sampler2DArray", "texture2d_array<float>"},
      {"sampler3D", "texture3d<float>"},
      {"samplerCube", "texturecube<float>"},
      {"samplerCubeArray", "texturecube_array<float>"},
      {"sampler2DShadow", "depth2d<float>"},
      {"sampler2DArrayShadow", "depth2d_array<float>"},
      {"samplerCubeShadow", "depthcube<float>"},
      {"samplerCubeArrayShadow", "depthcube_array<float>"},
      {"isampler2D", "texture2d<int>"},
      {"isampler2DArray", "texture2d_array<int>"},
      {"isampler3D", "texture3d<int>"},
      {"isamplerCube", "texturecube<int>"},
      {"isamplerCubeArray", "texturecube_array<int>"},
      {"usampler2D", "texture2d<uint>"},
      {"usampler2DArray", "texture2d_array<uint>"},
      {"usampler3D", "texture3d<uint>"},
      {"usamplerCube", "texturecube<uint>"},
      {"usamplerCubeArray", "texturecube_array<uint>"},
      {"texture2D", "texture2d<float>"},
      {"texture2DArray", "texture2d_array<float>"},
      {"texture3D", "texture3d<float>"},
      {"textureCube", "texturecube<float>"},
      {"textureCubeArray", "texturecube_array<float>"},
  };

  std::string name = type.name;
  if (name.rfind("buffer ", 0) == 0) {
    HIRType pointee{name.substr(7), type.arraySize};
    pointee = pointerlessType(std::move(pointee));
    return "device " + mapMetalType(pointee) + "*";
  }
  if (name.rfind("uniform ", 0) == 0) {
    HIRType pointee{name.substr(8), type.arraySize};
    return "constant " + mapMetalType(pointee) + "&";
  }
  if (name.rfind("shared ", 0) == 0) {
    HIRType pointee{name.substr(7), type.arraySize};
    return "threadgroup " + mapMetalType(pointee);
  }
  const bool pointer = !name.empty() && name.back() == '*';
  name = stripPointer(std::move(name));

  HIRType scalarType{name, type.arraySize, type.location};
  if (const std::optional<std::string> storageImageType =
          mapMetalStorageImageType(scalarType)) {
    return *storageImageType;
  }

  auto it = types.find(name);
  const std::optional<std::string> atomicType = mapMetalAtomicType(name);
  std::string mapped = atomicType.has_value()
                           ? *atomicType
                           : (it == types.end() ? name : it->second);
  if (type.arraySize.has_value()) {
    if (type.arraySize->empty()) {
      return "device " + mapped + "*";
    }
    return mapMetalFixedArrayType(std::move(mapped), *type.arraySize);
  }
  if (pointer) {
    return "device " + mapped + "*";
  }
  return mapped;
}

std::string metalBaseTypeName(HIRType type) { return baseTypeName(type); }

bool isMetal2DArrayTexture(std::string_view name) {
  return name == "sampler2DArray" || name == "isampler2DArray" ||
         name == "usampler2DArray" || name == "texture2DArray" ||
         name == "sampler2DArrayShadow";
}

bool isMetalCubeArrayTexture(std::string_view name) {
  return name == "samplerCubeArray" || name == "isamplerCubeArray" ||
         name == "usamplerCubeArray" || name == "textureCubeArray" ||
         name == "samplerCubeArrayShadow";
}

bool isMetalRuntimeResourceDescriptorArray(const HIRResource &resource) {
  return (resource.kind == HIRResourceKind::Texture ||
          resource.kind == HIRResourceKind::Sampler) &&
         isRuntimeArrayType(resource.type);
}

std::string metalRuntimeResourceDescriptorArrayElementType(
    const HIRResource &resource) {
  HIRType elementType = pointerlessType(resource.type);
  elementType.arraySize.reset();
  return mapMetalType(elementType);
}

std::string metalIdentifierSuffix(std::string_view text) {
  std::string suffix;
  bool previousWasUnderscore = false;
  for (const char character : text) {
    const bool alnum = (character >= 'a' && character <= 'z') ||
                       (character >= 'A' && character <= 'Z') ||
                       (character >= '0' && character <= '9');
    if (alnum) {
      suffix.push_back(character);
      previousWasUnderscore = false;
    } else if (!previousWasUnderscore) {
      suffix.push_back('_');
      previousWasUnderscore = true;
    }
  }
  while (!suffix.empty() && suffix.back() == '_') {
    suffix.pop_back();
  }
  if (suffix.empty()) {
    return "resource";
  }
  if (suffix.front() >= '0' && suffix.front() <= '9') {
    suffix.insert(suffix.begin(), '_');
  }
  return suffix;
}

std::string metalRuntimeResourceDescriptorArrayTableTypeName(
    const HIRResource &resource) {
  return std::string(kMetalRuntimeResourceDescriptorArrayTableTypePrefix) +
         metalIdentifierSuffix(
             metalRuntimeResourceDescriptorArrayElementType(resource));
}

std::string metalRuntimeResourceDescriptorArrayTableParameterType(
    const HIRResource &resource) {
  return "constant " +
         metalRuntimeResourceDescriptorArrayTableTypeName(resource) + "&";
}

std::string mapMetalResourceType(const HIRResource &resource) {
  if (isMetalRuntimeResourceDescriptorArray(resource)) {
    return metalRuntimeResourceDescriptorArrayTableParameterType(resource);
  }

  switch (resource.kind) {
  case HIRResourceKind::Uniform:
    return "constant " + mapMetalType(pointerlessType(resource.type)) + "&";
  case HIRResourceKind::Buffer:
    return "device " + mapMetalType(bufferElementType(resource.type)) + "*";
  case HIRResourceKind::Shared:
    return "threadgroup " + mapMetalType(bufferElementType(resource.type));
  case HIRResourceKind::Texture:
    return mapMetalType(pointerlessType(resource.type));
  case HIRResourceKind::StorageImage:
    if (const std::optional<std::string> storageImageType =
            mapMetalStorageImageType(resource.type,
                                     metalStorageImageAccessMode(resource))) {
      return *storageImageType;
    }
    return mapMetalType(pointerlessType(resource.type));
  case HIRResourceKind::Sampler:
    return mapMetalType(pointerlessType(resource.type));
  case HIRResourceKind::Value:
    return mapMetalType(resource.type);
  }
  return mapMetalType(resource.type);
}

bool isMetalParameterResource(HIRResourceKind kind) {
  return kind == HIRResourceKind::Uniform || kind == HIRResourceKind::Buffer ||
         kind == HIRResourceKind::Texture ||
         kind == HIRResourceKind::StorageImage ||
         kind == HIRResourceKind::Sampler;
}

std::string metalResourceAttributeName(HIRResourceKind kind) {
  if (kind == HIRResourceKind::Texture ||
      kind == HIRResourceKind::StorageImage) {
    return "texture";
  }
  if (kind == HIRResourceKind::Sampler) {
    return "sampler";
  }
  return "buffer";
}

std::string metalResourceAttributeName(const HIRResource &resource) {
  if (isMetalRuntimeResourceDescriptorArray(resource)) {
    return "buffer";
  }
  return metalResourceAttributeName(resource.kind);
}

std::optional<std::string>
metalResourceAttributeNamespace(const HIRResource &resource) {
  if (!isMetalParameterResource(resource.kind)) {
    return std::nullopt;
  }
  return metalResourceAttributeName(resource);
}

using MetalFunctionResourceParameterMap =
    std::map<std::string, std::vector<const HIRResource *>>;

struct MetalRenderContext {
  const std::vector<HIRStruct> *structs = nullptr;
  const std::vector<HIRConstant> *constants = nullptr;
  const std::vector<HIRResource> *resources = nullptr;
  const MetalFunctionResourceParameterMap *functionResourceParameters = nullptr;
  std::string_view stageName;
  std::set<std::string> localIdentifiers;
  std::set<std::string> localZeroIndexIdentifiers;
};

const HIRResource *findMetalResource(const MetalRenderContext &context,
                                     std::string_view name) {
  if (context.resources == nullptr) {
    return nullptr;
  }
  for (const HIRResource &resource : *context.resources) {
    if (resource.name == name) {
      return &resource;
    }
  }
  return nullptr;
}

std::optional<std::size_t>
metalRuntimeTailFieldIndex(const HIRStruct &structure,
                           std::string_view fieldName) {
  for (std::size_t index = 0; index < structure.fields.size(); ++index) {
    if (structure.fields[index].name == fieldName) {
      return index;
    }
  }
  return std::nullopt;
}

bool isMetalRuntimeTailField(const HIRStruct &structure,
                             std::size_t fieldIndex) {
  return fieldIndex + 1 == structure.fields.size() &&
         isRuntimeArrayType(structure.fields[fieldIndex].type);
}

bool shouldOmitMetalStructField(const HIRStruct &structure,
                                std::size_t fieldIndex) {
  return isMetalRuntimeTailField(structure, fieldIndex);
}

bool metalStructHasRuntimeTail(const HIRStruct &structure) {
  if (structure.fields.empty()) {
    return false;
  }
  return isMetalRuntimeTailField(structure, structure.fields.size() - 1);
}

std::optional<std::size_t>
metalArrayElementCount(const HIRType &type,
                       const std::vector<HIRConstant> *constants) {
  if (!type.arraySize.has_value()) {
    return std::nullopt;
  }
  if (constants != nullptr) {
    return storageArrayElementCount(type, *constants);
  }
  return parsePositiveStorageSize(*type.arraySize);
}

std::string metalStorageBufferArrayElementName(std::string_view name,
                                               std::size_t index);

std::vector<std::string>
metalResourceParameterNames(const HIRResource &resource,
                            const std::vector<HIRConstant> *constants) {
  const std::optional<std::size_t> bufferArrayCount =
      resource.kind == HIRResourceKind::Buffer
          ? metalArrayElementCount(resource.type, constants)
          : std::nullopt;
  if (!bufferArrayCount.has_value()) {
    return {resource.name};
  }

  std::vector<std::string> names;
  names.reserve(*bufferArrayCount);
  for (std::size_t arrayIndex = 0; arrayIndex < *bufferArrayCount;
       ++arrayIndex) {
    names.push_back(metalStorageBufferArrayElementName(resource.name,
                                                       arrayIndex));
  }
  return names;
}

std::size_t
metalResourceArgumentSlotCount(const HIRResource &resource,
                               const std::vector<HIRConstant> *constants) {
  if ((resource.kind != HIRResourceKind::Texture &&
       resource.kind != HIRResourceKind::StorageImage &&
       resource.kind != HIRResourceKind::Sampler &&
       resource.kind != HIRResourceKind::Buffer) ||
      !resource.type.arraySize.has_value()) {
    return 1;
  }

  return metalArrayElementCount(resource.type, constants).value_or(1);
}

void reserveMetalArgumentSlots(std::set<std::size_t> &usedIndices,
                               std::size_t firstIndex, std::size_t slotCount) {
  for (std::size_t offset = 0; offset < slotCount; ++offset) {
    usedIndices.insert(firstIndex + offset);
  }
}

bool metalArgumentRangeIsFree(const std::set<std::size_t> &usedIndices,
                              std::size_t firstIndex, std::size_t slotCount) {
  for (std::size_t offset = 0; offset < slotCount; ++offset) {
    if (usedIndices.contains(firstIndex + offset)) {
      return false;
    }
  }
  return true;
}

std::size_t firstFreeMetalArgumentRangeAtOrAfter(
    const std::set<std::size_t> &usedIndices, std::size_t firstIndex,
    std::size_t slotCount) {
  while (!metalArgumentRangeIsFree(usedIndices, firstIndex, slotCount)) {
    ++firstIndex;
  }
  return firstIndex;
}

std::map<std::string, std::size_t> assignMetalSetZeroArgumentSlots(
    const HIRStage &stage, std::string_view attributeNamespace,
    const std::vector<HIRConstant> *constants) {
  std::map<std::string, std::size_t> assignedIndices;
  std::set<std::size_t> usedIndices;
  for (const HIRResource &resource : stage.resources) {
    if (resource.set != 0 ||
        metalResourceAttributeNamespace(resource) != attributeNamespace) {
      continue;
    }

    const std::size_t slotCount =
        metalResourceArgumentSlotCount(resource, constants);
    const std::size_t argumentIndex = firstFreeMetalArgumentRangeAtOrAfter(
        usedIndices, resource.binding, slotCount);
    reserveMetalArgumentSlots(usedIndices, argumentIndex, slotCount);
    assignedIndices.emplace(resource.name, argumentIndex);
  }
  return assignedIndices;
}

std::string renderSharedResourceDeclaration(const HIRResource &resource) {
  std::ostringstream out;
  out << mapMetalResourceType(resource) << " " << resource.name;
  if (resource.type.arraySize.has_value()) {
    out << "[" << *resource.type.arraySize << "]";
  }
  out << ";";
  return out.str();
}

std::string mapMetalIdentifier(std::string_view text) {
  static const std::unordered_map<std::string_view, std::string> names = {
      {"vec2", "float2"},   {"vec3", "float3"},   {"vec4", "float4"},
      {"ivec2", "int2"},    {"ivec3", "int3"},    {"ivec4", "int4"},
      {"uvec2", "uint2"},   {"uvec3", "uint3"},   {"uvec4", "uint4"},
      {"bvec2", "bool2"},   {"bvec3", "bool3"},   {"bvec4", "bool4"},
      {"mat2", "float2x2"}, {"mat3", "float3x3"}, {"mat4", "float4x4"},
      {"mat2x2", "float2x2"},
      {"mat3x3", "float3x3"},
      {"mat4x4", "float4x4"},
  };
  auto it = names.find(text);
  return it == names.end() ? std::string(text) : it->second;
}

bool isMetalWorkgroupBarrierCall(const HIRExpression &expression,
                                 const MetalRenderContext &context) {
  return expression.kind == HIRExpressionKind::Call &&
         expression.children.empty() && context.stageName == "compute" &&
         (expression.value == "workgroupBarrier" ||
          expression.value == "barrier");
}

std::string metalStorageBufferArrayElementName(std::string_view name,
                                               std::size_t index) {
  return mapMetalIdentifier(name) + "_" + std::to_string(index);
}

std::string
metalStorageBufferDescriptorSelectorName(std::string_view stageName,
                                         std::string_view resourceName) {
  std::string name = "cgl_select_";
  if (!stageName.empty()) {
    name += mapMetalIdentifier(stageName);
    name += "_";
  }
  name += mapMetalIdentifier(resourceName);
  return name;
}

std::string renderMetalTokens(const std::vector<Token> &tokens) {
  std::ostringstream out;
  TokenKind previousKind = TokenKind::End;
  for (const Token &token : tokens) {
    std::string text = token.kind == TokenKind::Identifier
                           ? mapMetalIdentifier(token.text)
                           : token.text;
    if (isWordLikeToken(previousKind) && isWordLikeToken(token.kind)) {
      out << ' ';
    }
    out << text;
    if (token.kind == TokenKind::Semicolon || token.kind == TokenKind::LBrace ||
        token.kind == TokenKind::RBrace) {
      out << '\n';
    } else if (token.kind == TokenKind::Comma) {
      out << ' ';
    }
    previousKind = token.kind;
  }
  return out.str();
}

struct MetalComputeBuiltinParameter {
  std::string_view name;
  std::string_view attribute;
};

constexpr MetalComputeBuiltinParameter kMetalComputeBuiltinParameters[] = {
    {"gl_GlobalInvocationID", "thread_position_in_grid"},
    {"gl_LocalInvocationID", "thread_position_in_threadgroup"},
    {"gl_WorkGroupID", "threadgroup_position_in_grid"},
};

enum class MetalGraphicsIORole : unsigned {
  VertexInput = 1u << 0,
  VertexOutput = 1u << 1,
  FragmentInput = 1u << 2,
  FragmentOutput = 1u << 3,
};

using MetalGraphicsIORoleMask = unsigned;

struct MetalGraphicsIORoles {
  std::unordered_map<std::string, MetalGraphicsIORoleMask> structRoles;
};

MetalGraphicsIORoleMask metalGraphicsIORoleBit(MetalGraphicsIORole role) {
  return static_cast<MetalGraphicsIORoleMask>(role);
}

bool metalGraphicsIORoleMaskHas(MetalGraphicsIORoleMask mask,
                                MetalGraphicsIORole role) {
  return (mask & metalGraphicsIORoleBit(role)) != 0;
}

void addMetalGraphicsIORole(MetalGraphicsIORoles &roles,
                            const HIRModule &module, const HIRType &type,
                            MetalGraphicsIORole role) {
  const std::string structName = baseTypeName(type);
  if (structName.empty() || structName == "void" ||
      findStructByName(module.structs, structName) == nullptr) {
    return;
  }
  roles.structRoles[structName] |= metalGraphicsIORoleBit(role);
}

MetalGraphicsIORoles deriveMetalGraphicsIORoles(const HIRModule &module) {
  MetalGraphicsIORoles roles;
  for (const HIRStage &stage : module.stages) {
    const HIRFunction *entry = entryFunction(stage);
    if (entry == nullptr) {
      continue;
    }
    if (stage.stage == "vertex") {
      if (!entry->parameters.empty()) {
        addMetalGraphicsIORole(roles, module, entry->parameters.front().type,
                               MetalGraphicsIORole::VertexInput);
      }
      addMetalGraphicsIORole(roles, module, entry->returnType,
                             MetalGraphicsIORole::VertexOutput);
    } else if (stage.stage == "fragment") {
      if (!entry->parameters.empty()) {
        addMetalGraphicsIORole(roles, module, entry->parameters.front().type,
                               MetalGraphicsIORole::FragmentInput);
      }
      addMetalGraphicsIORole(roles, module, entry->returnType,
                             MetalGraphicsIORole::FragmentOutput);
    }
  }
  return roles;
}

MetalGraphicsIORoleMask
legacyMetalGraphicsIORoleMask(std::string_view structName) {
  MetalGraphicsIORoleMask mask = 0;
  if (structName == "VertexInput") {
    mask |= metalGraphicsIORoleBit(MetalGraphicsIORole::VertexInput);
  }
  if (structName == "VertexOutput") {
    mask |= metalGraphicsIORoleBit(MetalGraphicsIORole::VertexOutput);
  }
  if (structName == "FragmentInput") {
    mask |= metalGraphicsIORoleBit(MetalGraphicsIORole::FragmentInput);
  }
  if (structName == "FragmentOutput") {
    mask |= metalGraphicsIORoleBit(MetalGraphicsIORole::FragmentOutput);
  }
  return mask;
}

MetalGraphicsIORoleMask
metalGraphicsIORoleMaskForStruct(const MetalGraphicsIORoles &roles,
                                 std::string_view structName) {
  const auto role = roles.structRoles.find(std::string(structName));
  if (role != roles.structRoles.end()) {
    return role->second;
  }
  return legacyMetalGraphicsIORoleMask(structName);
}

bool metalGraphicsStructHasRole(const MetalGraphicsIORoles &roles,
                                std::string_view structName,
                                MetalGraphicsIORole role) {
  return metalGraphicsIORoleMaskHas(
      metalGraphicsIORoleMaskForStruct(roles, structName), role);
}

bool metalGraphicsTypeHasRole(const MetalGraphicsIORoles &roles,
                              const HIRType &type, MetalGraphicsIORole role) {
  return metalGraphicsStructHasRole(roles, baseTypeName(type), role);
}

bool metalTokensContainIdentifier(const std::vector<Token> &tokens,
                                  std::string_view name) {
  for (const Token &token : tokens) {
    if (token.kind == TokenKind::Identifier && token.text == name) {
      return true;
    }
  }
  return false;
}

bool metalStatementTokensContainIdentifier(const HIRStatement &statement,
                                           std::string_view name) {
  if (metalTokensContainIdentifier(statement.rawTokens, name) ||
      metalTokensContainIdentifier(statement.updateTokens, name)) {
    return true;
  }
  for (const HIRStatement &initializer : statement.initializer) {
    if (metalStatementTokensContainIdentifier(initializer, name)) {
      return true;
    }
  }
  for (const HIRStatement &update : statement.update) {
    if (metalStatementTokensContainIdentifier(update, name)) {
      return true;
    }
  }
  for (const HIRStatement &child : statement.body) {
    if (metalStatementTokensContainIdentifier(child, name)) {
      return true;
    }
  }
  for (const HIRStatement &child : statement.elseBody) {
    if (metalStatementTokensContainIdentifier(child, name)) {
      return true;
    }
  }
  return false;
}

bool metalFunctionUsesIdentifier(const HIRFunction &function,
                                 std::string_view name) {
  const bool expressionUse = functionExpressionsContain(
      function, [name](const HIRExpression &expression) {
        return expression.kind == HIRExpressionKind::Identifier &&
               expression.value == name;
      });
  if (expressionUse ||
      metalTokensContainIdentifier(function.bodyTokens, name)) {
    return true;
  }
  for (const HIRStatement &statement : function.body) {
    if (metalStatementTokensContainIdentifier(statement, name)) {
      return true;
    }
  }
  return false;
}

bool metalResourceParameterListContains(
    const std::vector<const HIRResource *> &resources,
    const HIRResource &resource) {
  for (const HIRResource *candidate : resources) {
    if (candidate == &resource || candidate->name == resource.name) {
      return true;
    }
  }
  return false;
}

bool appendMetalResourceParameter(std::vector<const HIRResource *> &resources,
                                  const HIRResource &resource) {
  if (metalResourceParameterListContains(resources, resource)) {
    return false;
  }
  resources.push_back(&resource);
  return true;
}

std::set<std::string> metalFunctionCallNames(const HIRFunction &function) {
  std::set<std::string> names;
  auto visitor = [&](const HIRExpression &expression) {
    if (expression.kind == HIRExpressionKind::Call) {
      names.insert(expression.value);
    }
  };
  visitFunctionExpressions(function, visitor);
  return names;
}

MetalFunctionResourceParameterMap
metalStageFunctionResourceParameters(const HIRStage &stage) {
  MetalFunctionResourceParameterMap parameters;
  std::map<std::string, std::set<std::string>> callsByFunction;

  for (const HIRFunction &function : stage.functions) {
    if (function.name == stage.entryPointName) {
      continue;
    }

    std::vector<const HIRResource *> &functionParameters =
        parameters[function.name];
    for (const HIRResource &resource : stage.resources) {
      if (isMetalParameterResource(resource.kind) &&
          metalFunctionUsesIdentifier(function, resource.name)) {
        appendMetalResourceParameter(functionParameters, resource);
      }
    }
    callsByFunction.emplace(function.name, metalFunctionCallNames(function));
  }

  bool changed = true;
  while (changed) {
    changed = false;
    for (const HIRFunction &function : stage.functions) {
      if (function.name == stage.entryPointName) {
        continue;
      }

      std::vector<const HIRResource *> &functionParameters =
          parameters[function.name];
      const auto callsIt = callsByFunction.find(function.name);
      if (callsIt == callsByFunction.end()) {
        continue;
      }
      for (const std::string &calleeName : callsIt->second) {
        const auto calleeIt = parameters.find(calleeName);
        if (calleeIt == parameters.end()) {
          continue;
        }
        for (const HIRResource *resource : calleeIt->second) {
          changed |= appendMetalResourceParameter(functionParameters,
                                                  *resource);
        }
      }
    }
  }

  return parameters;
}

bool metalComputeEntryUsesBuiltin(const HIRStage *stage,
                                  const HIRFunction &function,
                                  std::string_view name, bool entryPoint) {
  return entryPoint && stage != nullptr && stage->stage == "compute" &&
         metalFunctionUsesIdentifier(function, name);
}

std::string indentMetalTokenLines(const std::string &text,
                                  std::size_t indentation) {
  if (indentation == 0 || text.empty()) {
    return text;
  }

  const std::string spaces(indentation, ' ');
  std::ostringstream out;
  bool atLineStart = true;
  for (const char character : text) {
    if (atLineStart && character != '\n') {
      out << spaces;
    }
    out << character;
    atLineStart = character == '\n';
  }
  return out.str();
}

std::string renderMetalExpression(const HIRExpression &expression,
                                  const MetalRenderContext &context);

std::optional<std::string> metalAtomicScalarTypeName(const HIRType &type) {
  std::string name = stripPointer(type.name);
  if (const std::optional<std::string> atomicType = mapMetalAtomicType(name)) {
    return atomicType;
  }
  if (name == "int") {
    return "atomic_int";
  }
  if (name == "uint") {
    return "atomic_uint";
  }
  return std::nullopt;
}

bool isMetalAtomicType(const HIRType &type) {
  return mapMetalAtomicType(stripPointer(type.name)).has_value();
}

std::optional<HIRResourceKind>
metalAtomicTargetResourceKind(const HIRExpression &expression,
                              const MetalRenderContext &context) {
  const HIRExpression *current = &expression;
  while ((current->kind == HIRExpressionKind::Group ||
          current->kind == HIRExpressionKind::NonUniform ||
          current->kind == HIRExpressionKind::MemberAccess ||
          current->kind == HIRExpressionKind::IndexAccess) &&
         !current->children.empty()) {
    current = &current->children.front();
  }
  if (current->kind != HIRExpressionKind::Identifier) {
    return std::nullopt;
  }
  const HIRResource *resource = findMetalResource(context, current->value);
  if (resource == nullptr) {
    return std::nullopt;
  }
  return resource->kind;
}

std::string renderMetalAddressOfExpression(const HIRExpression &expression,
                                           const std::string &rendered) {
  switch (expression.kind) {
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::MemberAccess:
  case HIRExpressionKind::IndexAccess:
    return "&" + rendered;
  case HIRExpressionKind::Group:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Literal:
  case HIRExpressionKind::Call:
  case HIRExpressionKind::Constructor:
  case HIRExpressionKind::Unary:
  case HIRExpressionKind::Binary:
  case HIRExpressionKind::Select:
  case HIRExpressionKind::TextureSample:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    return "&(" + rendered + ")";
  }
  return "&(" + rendered + ")";
}

std::string renderMetalAtomicTargetAddress(const HIRExpression &target,
                                           const MetalRenderContext &context) {
  const std::string renderedTarget = renderMetalExpression(target, context);
  const std::string address =
      renderMetalAddressOfExpression(target, renderedTarget);
  if (isMetalAtomicType(target.type)) {
    return address;
  }

  const std::optional<std::string> atomicType =
      metalAtomicScalarTypeName(target.type);
  const std::optional<HIRResourceKind> resourceKind =
      metalAtomicTargetResourceKind(target, context);
  if (!atomicType.has_value() || !resourceKind.has_value()) {
    return address;
  }

  std::string addressSpace;
  switch (*resourceKind) {
  case HIRResourceKind::Buffer:
    addressSpace = "device";
    break;
  case HIRResourceKind::Shared:
    addressSpace = "threadgroup";
    break;
  case HIRResourceKind::Uniform:
  case HIRResourceKind::Texture:
  case HIRResourceKind::StorageImage:
  case HIRResourceKind::Sampler:
  case HIRResourceKind::Value:
    return address;
  }

  return "reinterpret_cast<" + addressSpace + " " + *atomicType + "*>(" +
         address + ")";
}

std::optional<std::string>
metalAtomicReadModifyWriteFunctionName(std::string_view operation) {
  if (operation == "atomicAdd") {
    return "atomic_fetch_add_explicit";
  }
  if (operation == "atomicExchange") {
    return "atomic_exchange_explicit";
  }
  if (operation == "atomicAnd") {
    return "atomic_fetch_and_explicit";
  }
  if (operation == "atomicOr") {
    return "atomic_fetch_or_explicit";
  }
  if (operation == "atomicXor") {
    return "atomic_fetch_xor_explicit";
  }
  if (operation == "atomicMin") {
    return "atomic_fetch_min_explicit";
  }
  if (operation == "atomicMax") {
    return "atomic_fetch_max_explicit";
  }
  return std::nullopt;
}

std::optional<std::string>
renderMetalAtomicReadModifyWriteCall(const HIRExpression &expression,
                                     const MetalRenderContext &context) {
  if (expression.kind != HIRExpressionKind::Call ||
      expression.children.size() != 2) {
    return std::nullopt;
  }

  const std::optional<std::string> functionName =
      metalAtomicReadModifyWriteFunctionName(expression.value);
  if (!functionName.has_value()) {
    return std::nullopt;
  }

  const HIRExpression &target = expression.children[0];
  const std::string targetAddress =
      renderMetalAtomicTargetAddress(target, context);

  return *functionName + "(" + targetAddress + ", " +
         renderMetalExpression(expression.children[1], context) +
         ", memory_order_relaxed)";
}

bool isMetalExplicitLodTextureSample(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::TextureSample &&
         expression.value == "textureLod";
}

bool isMetalExplicitLodTextureCompare(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::TextureCompare &&
         expression.value == "textureCompareLod";
}

bool metalTextureSampleHasExplicitSampler(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::TextureSample) {
    return false;
  }
  return isMetalExplicitLodTextureSample(expression)
             ? expression.children.size() >= 4
             : expression.children.size() >= 3;
}

bool isImplicitSamplerTextureSample(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::TextureSample &&
         !metalTextureSampleHasExplicitSampler(expression);
}

bool moduleUsesImplicitSampler(const HIRModule &module) {
  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &function : stage.functions) {
      if (functionExpressionsContain(function,
                                     isImplicitSamplerTextureSample)) {
        return true;
      }
    }
  }
  return false;
}

std::string
renderMetalArrayTextureCoordinate(const HIRExpression &coordinates,
                                  std::size_t coordinateWidth,
                                  const MetalRenderContext &context) {
  if (coordinates.kind == HIRExpressionKind::Constructor &&
      coordinates.children.size() > coordinateWidth) {
    std::ostringstream out;
    out << (coordinateWidth == 2 ? "float2(" : "float3(");
    for (std::size_t i = 0; i < coordinateWidth; ++i) {
      if (i != 0) {
        out << ", ";
      }
      out << renderMetalExpression(coordinates.children[i], context);
    }
    out << ")";
    return out.str();
  }

  return renderMetalExpression(coordinates, context) +
         (coordinateWidth == 2 ? ".xy" : ".xyz");
}

std::string renderMetalArrayTextureLayer(const HIRExpression &coordinates,
                                         std::size_t layerIndex,
                                         const MetalRenderContext &context) {
  if (coordinates.kind == HIRExpressionKind::Constructor &&
      coordinates.children.size() > layerIndex) {
    return "uint(" +
           renderMetalExpression(coordinates.children[layerIndex], context) +
           ")";
  }

  return "uint(" + renderMetalExpression(coordinates, context) +
         (layerIndex == 2 ? ".z" : ".w") + ")";
}

std::string renderMetalTextureSample(const HIRExpression &expression,
                                     const MetalRenderContext &context) {
  if (expression.children.size() < 2) {
    return "";
  }

  const HIRExpression &texture = expression.children[0];
  const bool explicitLod = isMetalExplicitLodTextureSample(expression);
  const bool hasExplicitSampler =
      metalTextureSampleHasExplicitSampler(expression);
  const std::size_t coordinateIndex = hasExplicitSampler ? 2 : 1;
  if (expression.children.size() <= coordinateIndex) {
    return "";
  }
  const HIRExpression &coordinates = expression.children[coordinateIndex];
  const std::string textureBaseType = metalBaseTypeName(texture.type);
  const bool is2DArrayTexture = isMetal2DArrayTexture(textureBaseType);
  const bool isCubeArrayTexture = isMetalCubeArrayTexture(textureBaseType);

  std::ostringstream out;
  out << renderMetalExpression(texture, context) << ".sample(";
  if (hasExplicitSampler) {
    out << renderMetalExpression(expression.children[1], context);
  } else {
    out << "crossgl_default_sampler";
  }
  if (is2DArrayTexture) {
    out << ", " << renderMetalArrayTextureCoordinate(coordinates, 2, context)
        << ", " << renderMetalArrayTextureLayer(coordinates, 2, context);
  } else if (isCubeArrayTexture) {
    out << ", " << renderMetalArrayTextureCoordinate(coordinates, 3, context)
        << ", " << renderMetalArrayTextureLayer(coordinates, 3, context);
  } else {
    out << ", " << renderMetalExpression(coordinates, context);
  }
  if (explicitLod) {
    const std::size_t lodIndex = hasExplicitSampler ? 3 : 2;
    if (expression.children.size() > lodIndex) {
      out << ", level("
          << renderMetalExpression(expression.children[lodIndex], context)
          << ")";
    }
  } else {
    for (std::size_t i = hasExplicitSampler ? 3 : 2;
         i < expression.children.size(); ++i) {
      out << ", " << renderMetalExpression(expression.children[i], context);
    }
  }
  out << ")";
  return out.str();
}

bool metalCanAppendSwizzleToRenderedExpression(
    const HIRExpression &expression) {
  switch (expression.kind) {
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::MemberAccess:
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::Call:
  case HIRExpressionKind::Constructor:
  case HIRExpressionKind::Group:
    return true;
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::Literal:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::Unary:
  case HIRExpressionKind::Binary:
  case HIRExpressionKind::Select:
  case HIRExpressionKind::TextureSample:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    return false;
  }
  return false;
}

std::string
renderMetalStorageImageCoordinateComponent(const HIRExpression &coordinates,
                                           std::string_view swizzle,
                                           const MetalRenderContext &context) {
  const std::string rendered = renderMetalExpression(coordinates, context);
  if (metalCanAppendSwizzleToRenderedExpression(coordinates)) {
    return rendered + std::string(swizzle);
  }
  return "(" + rendered + ")" + std::string(swizzle);
}

std::optional<std::string>
renderMetalStorageImageCoordinates(const HIRExpression &image,
                                   const HIRExpression &coordinates,
                                   const MetalRenderContext &context) {
  const std::string dimension =
      storageImageDimensionName(metalBaseTypeName(image.type));
  if (dimension == "2d_array") {
    return "uint2(" +
           renderMetalStorageImageCoordinateComponent(coordinates, ".xy",
                                                      context) +
           "), uint(" +
           renderMetalStorageImageCoordinateComponent(coordinates, ".z",
                                                      context) +
           ")";
  }
  if (dimension == "2d") {
    return "uint2(" + renderMetalExpression(coordinates, context) + ")";
  }
  return std::nullopt;
}

std::optional<std::string>
renderMetalImageAccessCall(const HIRExpression &expression,
                           const MetalRenderContext &context) {
  if (expression.kind != HIRExpressionKind::Call) {
    return std::nullopt;
  }

  const bool load = expression.value == "imageLoad";
  const bool store = expression.value == "imageStore";
  if ((!load && !store) ||
      expression.children.size() != (load ? std::size_t{2} : std::size_t{3})) {
    return std::nullopt;
  }

  const HIRExpression &image = expression.children[0];
  if (!isStorageImageResourceType(metalBaseTypeName(image.type))) {
    return std::nullopt;
  }

  const std::optional<std::string> coordinates =
      renderMetalStorageImageCoordinates(image, expression.children[1],
                                         context);
  if (!coordinates.has_value()) {
    return std::nullopt;
  }

  if (load) {
    return renderMetalExpression(image, context) + ".read(" + *coordinates +
           ")";
  }
  return renderMetalExpression(image, context) + ".write(" +
         renderMetalExpression(expression.children[2], context) + ", " +
         *coordinates + ")";
}

std::optional<std::string_view>
metalImageAtomicFunctionName(std::string_view operation) {
  if (operation == "imageAtomicAdd") {
    return "atomic_fetch_add";
  }
  if (operation == "imageAtomicExchange") {
    return "atomic_exchange";
  }
  if (operation == "imageAtomicMin") {
    return "atomic_fetch_min";
  }
  if (operation == "imageAtomicMax") {
    return "atomic_fetch_max";
  }
  if (operation == "imageAtomicAnd") {
    return "atomic_fetch_and";
  }
  if (operation == "imageAtomicOr") {
    return "atomic_fetch_or";
  }
  if (operation == "imageAtomicXor") {
    return "atomic_fetch_xor";
  }
  return std::nullopt;
}

std::optional<std::string>
renderMetalImageAtomicPayload(const HIRExpression &image,
                              const HIRExpression &value,
                              const MetalRenderContext &context) {
  const std::optional<std::string> scalarType =
      metalStorageImageScalarType(metalBaseTypeName(image.type));
  if (!scalarType.has_value()) {
    return std::nullopt;
  }
  if (*scalarType == "int") {
    return "int4(" + renderMetalExpression(value, context) + ")";
  }
  if (*scalarType == "uint") {
    return "uint4(" + renderMetalExpression(value, context) + ")";
  }
  return std::nullopt;
}

std::optional<std::string>
renderMetalImageAtomicCall(const HIRExpression &expression,
                           const MetalRenderContext &context) {
  if (expression.kind != HIRExpressionKind::Call ||
      expression.children.size() != 3) {
    return std::nullopt;
  }

  const std::optional<std::string_view> functionName =
      metalImageAtomicFunctionName(expression.value);
  if (!functionName.has_value()) {
    return std::nullopt;
  }

  const HIRExpression &image = expression.children[0];
  if (!isStorageImageResourceType(metalBaseTypeName(image.type))) {
    return std::nullopt;
  }

  const std::optional<std::string> coordinates =
      renderMetalStorageImageCoordinates(image, expression.children[1],
                                         context);
  const std::optional<std::string> payload =
      renderMetalImageAtomicPayload(image, expression.children[2], context);
  if (!coordinates.has_value() || !payload.has_value()) {
    return std::nullopt;
  }

  return renderMetalExpression(image, context) + "." +
         std::string(*functionName) + "(" + *coordinates + ", " + *payload +
         ").x";
}

std::string renderMetalTextureCompare(const HIRExpression &expression,
                                      const MetalRenderContext &context) {
  const std::optional<TextureCompareManualOperands> manualOperands =
      textureCompareManualOperands(expression);
  if (manualOperands.has_value()) {
    const std::optional<TextureCompareOperator> compareOperator =
        textureCompareOperatorFromExpression(*manualOperands->compareOp);
    if (!compareOperator.has_value()) {
      return "";
    }
    const std::string compareConstant(
        textureCompareOperatorConstantName(*compareOperator));

    const HIRExpression &texture = *manualOperands->texture;
    const HIRExpression &coordinates = *manualOperands->coordinate;
    const std::string textureBaseType = metalBaseTypeName(texture.type);
    const bool is2DArrayTexture = isMetal2DArrayTexture(textureBaseType);
    const bool isCubeArrayTexture = isMetalCubeArrayTexture(textureBaseType);

    const auto rawSample = [&](std::string_view offset) {
      std::ostringstream sample;
      sample << renderMetalExpression(texture, context) << ".sample("
             << renderMetalExpression(*manualOperands->sampler, context);
      if (is2DArrayTexture) {
        sample << ", "
               << renderMetalArrayTextureCoordinate(coordinates, 2, context)
               << ", " << renderMetalArrayTextureLayer(coordinates, 2, context);
      } else if (isCubeArrayTexture) {
        sample << ", "
               << renderMetalArrayTextureCoordinate(coordinates, 3, context)
               << ", " << renderMetalArrayTextureLayer(coordinates, 3, context);
      } else {
        sample << ", " << renderMetalExpression(coordinates, context);
      }
      sample << ", level("
             << renderMetalExpression(*manualOperands->lod, context) << ")";
      if (!offset.empty()) {
        sample << ", " << offset;
      }
      sample << ")";
      return sample.str();
    };
    const auto compareTap = [&](std::string_view offset) {
      return "cglCompareDepth(" + rawSample(offset) + ", " +
             renderMetalExpression(*manualOperands->depth, context) + ", " +
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
        result += "(" +
                  compareTap(renderMetalExpression(
                      *manualOperands->kernelOffsets[index], context)) +
                  " * " +
                  renderMetalExpression(*manualOperands->kernelWeights[index],
                                        context) +
                  ")";
      }
      result += ")";
      return result;
    }

    const std::string offset =
        manualOperands->offset != nullptr
            ? renderMetalExpression(*manualOperands->offset, context)
            : "";
    return compareTap(offset);
  }

  const bool explicitLod = isMetalExplicitLodTextureCompare(expression);
  if ((!explicitLod && expression.children.size() != 4) ||
      (explicitLod && expression.children.size() != 5)) {
    return "";
  }

  const HIRExpression &texture = expression.children[0];
  const HIRExpression &sampler = expression.children[1];
  const HIRExpression &coordinates = expression.children[2];
  const HIRExpression &depth = expression.children[3];
  const std::string textureBaseType = metalBaseTypeName(texture.type);
  const bool is2DArrayTexture = isMetal2DArrayTexture(textureBaseType);
  const bool isCubeArrayTexture = isMetalCubeArrayTexture(textureBaseType);

  std::ostringstream out;
  out << renderMetalExpression(texture, context) << ".sample_compare("
      << renderMetalExpression(sampler, context);
  if (is2DArrayTexture) {
    out << ", " << renderMetalArrayTextureCoordinate(coordinates, 2, context)
        << ", " << renderMetalArrayTextureLayer(coordinates, 2, context);
  } else if (isCubeArrayTexture) {
    out << ", " << renderMetalArrayTextureCoordinate(coordinates, 3, context)
        << ", " << renderMetalArrayTextureLayer(coordinates, 3, context);
  } else {
    out << ", " << renderMetalExpression(coordinates, context);
  }
  out << ", " << renderMetalExpression(depth, context);
  if (explicitLod) {
    out << ", level(" << renderMetalExpression(expression.children[4], context)
        << ")";
  }
  out << ")";
  return out.str();
}

struct MetalRuntimeTailMember {
  std::string resourceName;
  const HIRStruct *structure = nullptr;
  const HIRField *field = nullptr;
  std::size_t fieldIndex = 0;
};

const HIRStruct *metalBufferResourceStruct(const HIRResource &resource,
                                           const MetalRenderContext &context) {
  if (resource.kind != HIRResourceKind::Buffer || context.structs == nullptr) {
    return nullptr;
  }
  const HIRType elementType = bufferElementType(resource.type);
  return findStructByName(*context.structs, elementType.name);
}

std::optional<std::size_t> parseMetalNonNegativeIndex(std::string_view text) {
  if (text.empty()) {
    return std::nullopt;
  }
  if (text.back() == 'u' || text.back() == 'U') {
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

std::optional<std::int64_t> parseMetalSignedIndex(std::string_view text) {
  if (text.empty()) {
    return std::nullopt;
  }
  if (text.back() == 'u' || text.back() == 'U') {
    text.remove_suffix(1);
  }
  if (text.empty()) {
    return std::nullopt;
  }

  bool negative = false;
  if (text.front() == '+' || text.front() == '-') {
    negative = text.front() == '-';
    text.remove_prefix(1);
  }
  if (text.empty()) {
    return std::nullopt;
  }

  std::uint64_t magnitude = 0;
  const std::uint64_t maxMagnitude =
      negative
          ? static_cast<std::uint64_t>(
                std::numeric_limits<std::int64_t>::max()) +
                1u
          : static_cast<std::uint64_t>(
                std::numeric_limits<std::int64_t>::max());
  for (const char character : text) {
    if (character < '0' || character > '9') {
      return std::nullopt;
    }
    const std::uint64_t digit =
        static_cast<std::uint64_t>(character - '0');
    if (magnitude > (maxMagnitude - digit) / 10u) {
      return std::nullopt;
    }
    magnitude = magnitude * 10u + digit;
  }
  if (negative) {
    if (magnitude == maxMagnitude) {
      return std::numeric_limits<std::int64_t>::min();
    }
    return -static_cast<std::int64_t>(magnitude);
  }
  return static_cast<std::int64_t>(magnitude);
}

std::optional<std::int64_t>
metalDescriptorArraySignedIndexValue(const HIRExpression &expression,
                                     const MetalRenderContext &context) {
  if ((expression.kind == HIRExpressionKind::Group ||
       expression.kind == HIRExpressionKind::NonUniform) &&
      expression.children.size() == 1) {
    return metalDescriptorArraySignedIndexValue(expression.children.front(),
                                               context);
  }
  if (expression.kind == HIRExpressionKind::Unary &&
      expression.children.size() == 1 &&
      (expression.value == "+" || expression.value == "-")) {
    const std::optional<std::int64_t> childIndex =
        metalDescriptorArraySignedIndexValue(expression.children.front(),
                                            context);
    if (!childIndex.has_value()) {
      return std::nullopt;
    }
    if (expression.value == "+") {
      return childIndex;
    }
    if (*childIndex == std::numeric_limits<std::int64_t>::min()) {
      return std::nullopt;
    }
    return -*childIndex;
  }
  if (expression.kind == HIRExpressionKind::Literal) {
    return parseMetalSignedIndex(expression.value);
  }
  if (expression.kind == HIRExpressionKind::Identifier &&
      context.constants != nullptr) {
    if (context.localIdentifiers.count(expression.value) != 0) {
      return std::nullopt;
    }
    for (const HIRConstant &constant : *context.constants) {
      if (constant.name == expression.value &&
          constant.foldedValue.has_value()) {
        return parseMetalSignedIndex(*constant.foldedValue);
      }
    }
  }
  return std::nullopt;
}

std::optional<std::size_t>
metalDescriptorArrayIndexValue(const HIRExpression &expression,
                               const MetalRenderContext &context) {
  const std::optional<std::int64_t> signedIndex =
      metalDescriptorArraySignedIndexValue(expression, context);
  if (signedIndex.has_value() && *signedIndex >= 0) {
    return static_cast<std::size_t>(*signedIndex);
  }
  if (signedIndex.has_value()) {
    return std::nullopt;
  }
  if ((expression.kind == HIRExpressionKind::Group ||
       expression.kind == HIRExpressionKind::NonUniform) &&
      expression.children.size() == 1) {
    return metalDescriptorArrayIndexValue(expression.children.front(), context);
  }
  if (expression.kind == HIRExpressionKind::Literal) {
    return parseMetalNonNegativeIndex(expression.value);
  }
  if (expression.kind == HIRExpressionKind::Identifier &&
      context.constants != nullptr) {
    if (context.localIdentifiers.count(expression.value) != 0) {
      return std::nullopt;
    }
    for (const HIRConstant &constant : *context.constants) {
      if (constant.name == expression.value &&
          constant.foldedValue.has_value()) {
        return parseMetalNonNegativeIndex(*constant.foldedValue);
      }
    }
  }
  return std::nullopt;
}

bool isMetalStaticZeroIndexExpression(
    const HIRExpression &expression,
    const std::vector<HIRConstant> *constants) {
  if ((expression.kind == HIRExpressionKind::Group ||
       expression.kind == HIRExpressionKind::NonUniform) &&
      expression.children.size() == 1) {
    return isMetalStaticZeroIndexExpression(expression.children.front(),
                                           constants);
  }
  if (expression.kind == HIRExpressionKind::Unary && expression.value == "+" &&
      expression.children.size() == 1) {
    return isMetalStaticZeroIndexExpression(expression.children.front(),
                                           constants);
  }
  if (expression.kind == HIRExpressionKind::Literal) {
    const std::optional<std::size_t> index =
        parseMetalNonNegativeIndex(expression.value);
    return index.has_value() && *index == 0;
  }
  if (expression.kind != HIRExpressionKind::Identifier ||
      constants == nullptr) {
    return false;
  }
  for (const HIRConstant &constant : *constants) {
    if (constant.name != expression.value || !constant.foldedValue.has_value() ||
        constant.type.arraySize.has_value() ||
        (constant.type.name != "int" && constant.type.name != "uint")) {
      continue;
    }
    const std::optional<std::size_t> index =
        parseMetalNonNegativeIndex(*constant.foldedValue);
    return index.has_value() && *index == 0;
  }
  return false;
}

const HIRResource *
metalStorageBufferDescriptorArrayResource(const HIRExpression &expression,
                                          const MetalRenderContext &context) {
  if (expression.kind != HIRExpressionKind::IndexAccess ||
      expression.children.size() < 2 ||
      expression.children[0].kind != HIRExpressionKind::Identifier) {
    return nullptr;
  }
  const HIRResource *resource =
      findMetalResource(context, expression.children[0].value);
  if (resource == nullptr || resource->kind != HIRResourceKind::Buffer ||
      !resource->type.arraySize.has_value()) {
    return nullptr;
  }
  return resource;
}

std::optional<std::string> renderMetalStorageBufferDescriptorArrayIndexAccess(
    const HIRExpression &expression, const MetalRenderContext &context) {
  const HIRResource *resource =
      metalStorageBufferDescriptorArrayResource(expression, context);
  if (resource == nullptr || expression.children.size() < 2) {
    return std::nullopt;
  }
  const std::optional<std::size_t> descriptorIndex =
      metalDescriptorArrayIndexValue(expression.children[1], context);
  const std::optional<std::size_t> descriptorCount =
      metalArrayElementCount(resource->type, context.constants);
  if (!descriptorCount.has_value()) {
    return std::nullopt;
  }
  if (descriptorIndex.has_value()) {
    if (*descriptorIndex >= *descriptorCount) {
      return std::nullopt;
    }
    return metalStorageBufferArrayElementName(resource->name, *descriptorIndex);
  }

  std::ostringstream out;
  out << metalStorageBufferDescriptorSelectorName(context.stageName,
                                                  resource->name)
      << "(" << renderMetalExpression(expression.children[1], context);
  for (std::size_t arrayIndex = 0; arrayIndex < *descriptorCount;
       ++arrayIndex) {
    out << ", "
        << metalStorageBufferArrayElementName(resource->name, arrayIndex);
  }
  out << ")";
  return out.str();
}

std::optional<std::string> renderMetalRuntimeResourceDescriptorArrayIndexAccess(
    const HIRExpression &expression, const MetalRenderContext &context) {
  if (expression.kind != HIRExpressionKind::IndexAccess ||
      expression.children.size() < 2) {
    return std::nullopt;
  }

  const HIRExpression *base = &expression.children[0];
  while ((base->kind == HIRExpressionKind::Group ||
          base->kind == HIRExpressionKind::NonUniform) &&
         base->children.size() == 1) {
    base = &base->children.front();
  }
  if (base->kind != HIRExpressionKind::Identifier) {
    return std::nullopt;
  }
  const HIRResource *resource = findMetalResource(context, base->value);
  if (resource == nullptr ||
      !isMetalRuntimeResourceDescriptorArray(*resource)) {
    return std::nullopt;
  }

  return mapMetalIdentifier(resource->name) + ".descriptors[" +
         renderMetalExpression(expression.children[1], context) + "]";
}

bool isMetalZeroIndexExpression(const HIRExpression &expression,
                                const MetalRenderContext &context) {
  if ((expression.kind == HIRExpressionKind::Group ||
       expression.kind == HIRExpressionKind::NonUniform) &&
      expression.children.size() == 1) {
    return isMetalZeroIndexExpression(expression.children.front(), context);
  }
  if (expression.kind == HIRExpressionKind::Unary && expression.value == "+" &&
      expression.children.size() == 1) {
    return isMetalZeroIndexExpression(expression.children.front(), context);
  }
  if (expression.kind == HIRExpressionKind::Identifier &&
      context.localZeroIndexIdentifiers.count(expression.value) != 0) {
    return true;
  }
  const std::optional<std::size_t> index =
      metalDescriptorArrayIndexValue(expression, context);
  return index.has_value() && *index == 0;
}

template <typename Visitor>
void visitMetalValidationStatementExpressionsRenderedSource(
    const HIRStatement &statement, Visitor &visitor) {
  visitExpressionTree(statement.target, visitor);
  visitExpressionTree(statement.value, visitor);
  for (const HIRStatement &initializer : statement.initializer) {
    visitMetalValidationStatementExpressionsRenderedSource(initializer,
                                                           visitor);
  }
  if (statement.updateTokens.empty()) {
    for (const HIRStatement &update : statement.update) {
      visitMetalValidationStatementExpressionsRenderedSource(update, visitor);
    }
  }
  for (const HIRStatement &child : statement.body) {
    visitMetalValidationStatementExpressionsRenderedSource(child, visitor);
  }
  for (const HIRStatement &child : statement.elseBody) {
    visitMetalValidationStatementExpressionsRenderedSource(child, visitor);
  }
}

std::optional<std::string>
metalResourceNameFromMemberBase(const HIRExpression &base,
                                const MetalRenderContext &context,
                                bool allowZeroOuterIndex) {
  if (base.kind == HIRExpressionKind::Identifier) {
    return base.value;
  }
  if (!allowZeroOuterIndex || base.kind != HIRExpressionKind::IndexAccess ||
      base.children.size() < 2 ||
      base.children[0].kind != HIRExpressionKind::Identifier ||
      !isMetalZeroIndexExpression(base.children[1], context)) {
    return std::nullopt;
  }
  return base.children[0].value;
}

std::optional<MetalRuntimeTailMember>
resolveMetalRuntimeTailMember(const HIRExpression &expression,
                              const MetalRenderContext &context) {
  if (expression.kind != HIRExpressionKind::MemberAccess ||
      expression.children.empty()) {
    return std::nullopt;
  }

  const std::optional<std::string> resourceName =
      metalResourceNameFromMemberBase(expression.children.front(), context,
                                      true);
  if (!resourceName.has_value()) {
    return std::nullopt;
  }
  const HIRResource *resource = findMetalResource(context, *resourceName);
  if (resource == nullptr) {
    return std::nullopt;
  }
  const HIRStruct *structure = metalBufferResourceStruct(*resource, context);
  if (structure == nullptr) {
    return std::nullopt;
  }
  const std::optional<std::size_t> fieldIndex =
      metalRuntimeTailFieldIndex(*structure, expression.value);
  if (!fieldIndex.has_value() ||
      !isMetalRuntimeTailField(*structure, *fieldIndex)) {
    return std::nullopt;
  }

  return MetalRuntimeTailMember{*resourceName, structure,
                                &structure->fields[*fieldIndex], *fieldIndex};
}

std::optional<std::string>
metalRuntimeTailPointerExpression(const MetalRuntimeTailMember &member,
                                  const MetalRenderContext &context) {
  if (context.structs == nullptr || context.constants == nullptr ||
      member.structure == nullptr || member.field == nullptr) {
    return std::nullopt;
  }
  const std::optional<std::size_t> offset = runtimeTailFieldOffset(
      *member.structure, member.fieldIndex, StorageLayoutKind::MetalDevice,
      *context.structs, *context.constants);
  if (!offset.has_value()) {
    return std::nullopt;
  }

  HIRType elementType = arrayElementType(member.field->type);
  std::ostringstream out;
  out << "reinterpret_cast<device " << mapMetalType(elementType)
      << "*>(reinterpret_cast<device char*>("
      << mapMetalIdentifier(member.resourceName) << ") + " << *offset << ")";
  return out.str();
}

std::optional<std::string>
renderMetalRuntimeTailIndexAccess(const HIRExpression &expression,
                                  const MetalRenderContext &context) {
  if (expression.kind != HIRExpressionKind::IndexAccess ||
      expression.children.size() < 2) {
    return std::nullopt;
  }
  const std::optional<MetalRuntimeTailMember> tail =
      resolveMetalRuntimeTailMember(expression.children[0], context);
  if (!tail.has_value()) {
    return std::nullopt;
  }
  const std::optional<std::string> pointer =
      metalRuntimeTailPointerExpression(*tail, context);
  if (!pointer.has_value()) {
    return std::nullopt;
  }
  return "(" + *pointer + ")[" +
         renderMetalExpression(expression.children[1], context) + "]";
}

std::optional<std::string>
renderMetalResourceMemberAccess(const HIRExpression &expression,
                                const MetalRenderContext &context) {
  if (expression.kind != HIRExpressionKind::MemberAccess ||
      expression.children.empty()) {
    return std::nullopt;
  }
  if (const std::optional<MetalRuntimeTailMember> tail =
          resolveMetalRuntimeTailMember(expression, context)) {
    return metalRuntimeTailPointerExpression(*tail, context);
  }

  const HIRExpression &base = expression.children.front();
  if (base.kind != HIRExpressionKind::Identifier) {
    return std::nullopt;
  }
  const HIRResource *resource = findMetalResource(context, base.value);
  if (resource == nullptr) {
    return std::nullopt;
  }
  const HIRStruct *structure = metalBufferResourceStruct(*resource, context);
  if (structure == nullptr) {
    return std::nullopt;
  }
  const std::optional<std::size_t> fieldIndex =
      metalRuntimeTailFieldIndex(*structure, expression.value);
  if (!fieldIndex.has_value() ||
      isMetalRuntimeTailField(*structure, *fieldIndex)) {
    return std::nullopt;
  }

  return mapMetalIdentifier(base.value) + "->" + expression.value;
}

void appendMetalHelperResourceArguments(std::ostringstream &out,
                                        const HIRExpression &expression,
                                        const MetalRenderContext &context,
                                        bool &firstArgument) {
  if (context.functionResourceParameters == nullptr) {
    return;
  }
  const auto helperIt =
      context.functionResourceParameters->find(expression.value);
  if (helperIt == context.functionResourceParameters->end()) {
    return;
  }

  for (const HIRResource *resource : helperIt->second) {
    for (const std::string &name :
         metalResourceParameterNames(*resource, context.constants)) {
      if (!firstArgument) {
        out << ", ";
      }
      firstArgument = false;
      out << name;
    }
  }
}

std::string renderMetalExpression(const HIRExpression &expression,
                                  const MetalRenderContext &context) {
  switch (expression.kind) {
  case HIRExpressionKind::Empty:
    return "";
  case HIRExpressionKind::Identifier:
    return mapMetalIdentifier(expression.value);
  case HIRExpressionKind::Literal:
    return expression.value;
  case HIRExpressionKind::Group:
    return expression.children.empty()
               ? "()"
               : "(" +
                     renderMetalExpression(expression.children.front(),
                                           context) +
                     ")";
  case HIRExpressionKind::MemberAccess:
    if (const std::optional<std::string> resourceMember =
            renderMetalResourceMemberAccess(expression, context)) {
      return *resourceMember;
    }
    return expression.children.empty()
               ? expression.value
               : renderMetalExpression(expression.children.front(), context) +
                     "." + expression.value;
  case HIRExpressionKind::IndexAccess:
    if (expression.children.size() < 2) {
      return "";
    }
    if (const std::optional<std::string> descriptorElement =
            renderMetalStorageBufferDescriptorArrayIndexAccess(expression,
                                                               context)) {
      return *descriptorElement;
    }
    if (const std::optional<std::string> descriptorElement =
            renderMetalRuntimeResourceDescriptorArrayIndexAccess(expression,
                                                                 context)) {
      return *descriptorElement;
    }
    if (const std::optional<std::string> tailIndex =
            renderMetalRuntimeTailIndexAccess(expression, context)) {
      return *tailIndex;
    }
    return renderMetalExpression(expression.children[0], context) + "[" +
           renderMetalExpression(expression.children[1], context) + "]";
  case HIRExpressionKind::NonUniform:
    return expression.children.empty()
               ? ""
               : renderMetalExpression(expression.children.front(), context);
  case HIRExpressionKind::Call: {
    if (const std::optional<std::string> atomicCall =
            renderMetalAtomicReadModifyWriteCall(expression, context)) {
      return *atomicCall;
    }
    if (isMetalWorkgroupBarrierCall(expression, context)) {
      return "threadgroup_barrier(mem_flags::mem_threadgroup)";
    }
    if (const std::optional<std::string> imageAccess =
            renderMetalImageAccessCall(expression, context)) {
      return *imageAccess;
    }
    if (const std::optional<std::string> imageAtomic =
            renderMetalImageAtomicCall(expression, context)) {
      return *imageAtomic;
    }
    const std::optional<std::string> intrinsicName =
        backendIntrinsicNameForCall(TargetKind::Metal, expression);
    if (intrinsicName == "length" && expression.children.size() == 1 &&
        !expression.children.front().type.arraySize.has_value() &&
        isFloatLike(baseTypeName(expression.children.front().type))) {
      return "abs(" +
             renderMetalExpression(expression.children.front(), context) + ")";
    }

    std::ostringstream out;
    out << intrinsicName.value_or(mapMetalIdentifier(expression.value)) << "(";
    bool firstArgument = true;
    for (std::size_t i = 0; i < expression.children.size(); ++i) {
      if (!firstArgument) {
        out << ", ";
      }
      firstArgument = false;
      out << renderMetalExpression(expression.children[i], context);
    }
    if (!intrinsicName.has_value()) {
      appendMetalHelperResourceArguments(out, expression, context,
                                         firstArgument);
    }
    out << ")";
    return out.str();
  }
  case HIRExpressionKind::Constructor: {
    std::ostringstream out;
    out << mapMetalIdentifier(expression.value) << "(";
    for (std::size_t i = 0; i < expression.children.size(); ++i) {
      if (i != 0) {
        out << ", ";
      }
      out << renderMetalExpression(expression.children[i], context);
    }
    out << ")";
    return out.str();
  }
  case HIRExpressionKind::Unary:
    return expression.value +
           (expression.children.empty()
                ? ""
                : renderMetalExpression(expression.children[0], context));
  case HIRExpressionKind::Binary:
    if (expression.children.size() < 2) {
      return expression.value;
    }
    return renderMetalExpression(expression.children[0], context) + " " +
           expression.value + " " +
           renderMetalExpression(expression.children[1], context);
  case HIRExpressionKind::Select:
    if (expression.children.size() < 3) {
      return "";
    }
    return renderMetalExpression(expression.children[0], context) + " ? " +
           renderMetalExpression(expression.children[1], context) + " : " +
           renderMetalExpression(expression.children[2], context);
  case HIRExpressionKind::TextureSample:
    return renderMetalTextureSample(expression, context);
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    return renderMetalTextureCompare(expression, context);
  }
  return "";
}

std::string renderMetalStatementInline(const HIRStatement &statement,
                                       const MetalRenderContext &context) {
  switch (statement.kind) {
  case HIRStatementKind::Declaration: {
    std::ostringstream out;
    out << mapMetalType(statement.declaredType) << " " << statement.name;
    if (statement.value.kind != HIRExpressionKind::Empty) {
      out << " = " << renderMetalExpression(statement.value, context);
    }
    return out.str();
  }
  case HIRStatementKind::Assignment:
    return renderMetalExpression(statement.target, context) + " = " +
           renderMetalExpression(statement.value, context);
  case HIRStatementKind::Expression:
    return renderMetalExpression(statement.value, context);
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
    break;
  case HIRStatementKind::Raw:
    return "/* error: opt.hir-raw-statement-backend-input: raw HIR "
           "statement must be lowered to structured HIR */";
  case HIRStatementKind::Return:
  case HIRStatementKind::Block:
  case HIRStatementKind::If:
  case HIRStatementKind::For:
    break;
  }
  return "";
}

std::string renderMetalForUpdate(const HIRStatement &statement,
                                 const MetalRenderContext &context) {
  if (!statement.updateTokens.empty()) {
    return renderMetalTokens(statement.updateTokens);
  }
  return statement.update.empty()
             ? ""
             : renderMetalStatementInline(statement.update.front(), context);
}

std::string renderMetalStatement(const HIRStatement &statement,
                                 const MetalRenderContext &context,
                                 std::size_t indentation) {
  const std::string spaces(indentation, ' ');
  std::ostringstream out;
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    out << spaces << mapMetalType(statement.declaredType) << " "
        << statement.name;
    if (statement.value.kind != HIRExpressionKind::Empty) {
      out << " = " << renderMetalExpression(statement.value, context);
    }
    out << ";";
    break;
  case HIRStatementKind::Assignment:
    out << spaces << renderMetalExpression(statement.target, context) << " = ";
    out << renderMetalExpression(statement.value, context);
    out << ";";
    break;
  case HIRStatementKind::Return:
    out << spaces << "return";
    if (statement.value.kind != HIRExpressionKind::Empty) {
      out << " " << renderMetalExpression(statement.value, context);
    }
    out << ";";
    break;
  case HIRStatementKind::Expression:
    out << spaces << renderMetalExpression(statement.value, context) << ";";
    break;
  case HIRStatementKind::Break:
    out << spaces << "break;";
    break;
  case HIRStatementKind::Continue:
    out << spaces << "continue;";
    break;
  case HIRStatementKind::Discard:
    out << spaces << "discard_fragment();";
    break;
  case HIRStatementKind::Block:
    out << spaces << "{\n";
    for (const HIRStatement &child : statement.body) {
      out << renderMetalStatement(child, context, indentation + 2) << "\n";
    }
    out << spaces << "}";
    break;
  case HIRStatementKind::If:
    out << spaces << "if (" << renderMetalExpression(statement.value, context)
        << ") {\n";
    for (const HIRStatement &child : statement.body) {
      out << renderMetalStatement(child, context, indentation + 2) << "\n";
    }
    if (!statement.elseBody.empty()) {
      out << spaces << "} else {\n";
      for (const HIRStatement &child : statement.elseBody) {
        out << renderMetalStatement(child, context, indentation + 2) << "\n";
      }
    }
    out << spaces << "}";
    break;
  case HIRStatementKind::For: {
    std::string initializer;
    if (!statement.initializer.empty()) {
      initializer =
          renderMetalStatementInline(statement.initializer.front(), context);
    }
    out << spaces << "for (" << initializer << "; "
        << renderMetalExpression(statement.value, context) << "; "
        << renderMetalForUpdate(statement, context) << ") {\n";
    for (const HIRStatement &child : statement.body) {
      out << renderMetalStatement(child, context, indentation + 2) << "\n";
    }
    out << spaces << "}";
    break;
  }
  case HIRStatementKind::Raw:
    out << spaces
        << "/* error: opt.hir-raw-statement-backend-input: raw HIR "
           "statement must be lowered to structured HIR */";
    break;
  }
  return out.str();
}

std::string renderMetalBody(const HIRStage *stage, const HIRFunction &function,
                            const MetalRenderContext &context,
                            bool entryPoint) {
  std::ostringstream out;
  constexpr std::size_t bodyIndentation = 2;
  if (entryPoint && stage != nullptr && stage->stage == "compute") {
    for (const HIRResource &resource : stage->resources) {
      if (resource.kind == HIRResourceKind::Shared) {
        out << std::string(bodyIndentation, ' ')
            << renderSharedResourceDeclaration(resource) << "\n";
      }
    }
  }

  if (function.body.empty()) {
    out << indentMetalTokenLines(renderMetalTokens(function.bodyTokens),
                                 bodyIndentation);
    return out.str();
  }

  for (const HIRStatement &statement : function.body) {
    out << renderMetalStatement(statement, context, bodyIndentation) << "\n";
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

void renderMetalManualCompareHelper(std::ostringstream &out) {
  out << "enum CGLCompareOp {\n";
  out << "  CGL_COMPARE_NEVER = 0,\n";
  out << "  CGL_COMPARE_ALWAYS = 1,\n";
  out << "  CGL_COMPARE_LESS = 2,\n";
  out << "  CGL_COMPARE_LESS_EQUAL = 3,\n";
  out << "  CGL_COMPARE_EQUAL = 4,\n";
  out << "  CGL_COMPARE_NOT_EQUAL = 5,\n";
  out << "  CGL_COMPARE_GREATER_EQUAL = 6,\n";
  out << "  CGL_COMPARE_GREATER = 7,\n";
  out << "};\n\n";
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

std::string fieldAttribute(const HIRStruct &structure, const HIRField &field,
                           std::size_t index,
                           const MetalGraphicsIORoles &graphicsIORoles) {
  if (metalGraphicsStructHasRole(graphicsIORoles, structure.name,
                                 MetalGraphicsIORole::VertexInput)) {
    return " [[attribute(" + std::to_string(index) + ")]]";
  }
  if (metalGraphicsStructHasRole(graphicsIORoles, structure.name,
                                 MetalGraphicsIORole::VertexOutput) &&
      (field.name == "position" || field.name == "clipPosition")) {
    return " [[position]]";
  }
  if (metalGraphicsStructHasRole(graphicsIORoles, structure.name,
                                 MetalGraphicsIORole::FragmentOutput)) {
    return " [[color(" + std::to_string(index) + ")]]";
  }
  return "";
}

std::string stagePrefix(const std::string &stage) {
  if (stage == "vertex") {
    return "vertex";
  }
  if (stage == "fragment") {
    return "fragment";
  }
  if (stage == "compute") {
    return "kernel";
  }
  return stage;
}

std::string stageFunctionName(const std::string &stage,
                              const HIRFunction &function) {
  return stage + "_" + function.name;
}

bool metalEntryParameterUsesStageIn(const HIRStage &stage,
                                    const HIRParameter &parameter,
                                    const MetalGraphicsIORoles &graphicsIORoles,
                                    std::size_t index) {
  if (index != 0) {
    return false;
  }
  if (stage.stage == "vertex") {
    return metalGraphicsTypeHasRole(graphicsIORoles, parameter.type,
                                    MetalGraphicsIORole::VertexInput);
  }
  if (stage.stage == "fragment") {
    return metalGraphicsTypeHasRole(graphicsIORoles, parameter.type,
                                    MetalGraphicsIORole::FragmentInput);
  }
  return false;
}

void appendMetalHelperResourceParameters(
    std::ostringstream &out,
    const std::vector<const HIRResource *> &resourceParameters,
    const std::vector<HIRConstant> *constants, bool &firstParameter) {
  for (const HIRResource *resource : resourceParameters) {
    for (const std::string &name :
         metalResourceParameterNames(*resource, constants)) {
      if (!firstParameter) {
        out << ", ";
      }
      firstParameter = false;
      out << mapMetalResourceType(*resource) << " " << name;
    }
  }
}

bool isMetalIntegerIndexType(const HIRType &type) {
  return !type.arraySize.has_value() &&
         (type.name == "int" || type.name == "uint");
}

void collectMetalTokenIdentifierNames(const std::vector<Token> &tokens,
                                      std::set<std::string> &names) {
  for (const Token &token : tokens) {
    if (token.kind == TokenKind::Identifier) {
      names.insert(std::string(token.text));
    }
  }
}

void collectMetalAssignedLocalIdentifiers(const HIRExpression &target,
                                          std::set<std::string> &identifiers) {
  if (target.kind == HIRExpressionKind::Identifier) {
    identifiers.insert(target.value);
  }
}

void collectMetalLocalZeroIndexMetadata(
    const HIRStatement &statement, const std::vector<HIRConstant> *constants,
    std::set<std::string> &localIdentifiers,
    std::set<std::string> &zeroCandidates,
    std::set<std::string> &invalidatedIdentifiers) {
  if (statement.kind == HIRStatementKind::Declaration) {
    if (localIdentifiers.count(statement.name) != 0) {
      invalidatedIdentifiers.insert(statement.name);
    }
    localIdentifiers.insert(statement.name);
    if (isMetalIntegerIndexType(statement.declaredType) &&
        isMetalStaticZeroIndexExpression(statement.value, constants)) {
      zeroCandidates.insert(statement.name);
    }
  } else if (statement.kind == HIRStatementKind::Assignment) {
    collectMetalAssignedLocalIdentifiers(statement.target, invalidatedIdentifiers);
  } else if (statement.kind == HIRStatementKind::Raw) {
    collectMetalTokenIdentifierNames(statement.rawTokens, invalidatedIdentifiers);
  }

  collectMetalTokenIdentifierNames(statement.updateTokens,
                                   invalidatedIdentifiers);
  for (const HIRStatement &initializer : statement.initializer) {
    collectMetalLocalZeroIndexMetadata(initializer, constants, localIdentifiers,
                                       zeroCandidates, invalidatedIdentifiers);
  }
  for (const HIRStatement &update : statement.update) {
    collectMetalLocalZeroIndexMetadata(update, constants, localIdentifiers,
                                       zeroCandidates, invalidatedIdentifiers);
  }
  for (const HIRStatement &child : statement.body) {
    collectMetalLocalZeroIndexMetadata(child, constants, localIdentifiers,
                                       zeroCandidates, invalidatedIdentifiers);
  }
  for (const HIRStatement &child : statement.elseBody) {
    collectMetalLocalZeroIndexMetadata(child, constants, localIdentifiers,
                                       zeroCandidates, invalidatedIdentifiers);
  }
}

MetalRenderContext metalFunctionRenderContext(
    const MetalRenderContext &baseContext, const HIRFunction &function) {
  MetalRenderContext context = baseContext;
  for (const HIRParameter &parameter : function.parameters) {
    context.localIdentifiers.insert(parameter.name);
  }

  std::set<std::string> zeroCandidates;
  std::set<std::string> invalidatedIdentifiers;
  for (const HIRStatement &statement : function.body) {
    collectMetalLocalZeroIndexMetadata(
        statement, context.constants, context.localIdentifiers, zeroCandidates,
        invalidatedIdentifiers);
  }
  for (const std::string &candidate : zeroCandidates) {
    if (invalidatedIdentifiers.count(candidate) == 0) {
      context.localZeroIndexIdentifiers.insert(candidate);
    }
  }
  return context;
}

std::string renderFunction(const HIRStage *stage, const HIRFunction &function,
                           const HIRModule &module,
                           const MetalGraphicsIORoles &graphicsIORoles,
                           bool entryPoint,
                           const MetalFunctionResourceParameterMap
                               *functionResourceParameters = nullptr) {
  const std::vector<HIRResource> *resources =
      stage == nullptr ? nullptr : &stage->resources;
  const MetalRenderContext context{
      &module.structs, &module.constants, resources, functionResourceParameters,
      stage == nullptr ? std::string_view{} : std::string_view{stage->stage},
      {}, {}};
  const MetalRenderContext functionContext =
      metalFunctionRenderContext(context, function);
  std::ostringstream out;
  if (entryPoint && stage != nullptr) {
    out << stagePrefix(stage->stage) << " ";
  }
  out << mapMetalType(function.returnType) << " "
      << (entryPoint && stage != nullptr
              ? stageFunctionName(stage->stage, function)
              : function.name)
      << "(";
  bool firstParameter = true;
  for (std::size_t i = 0; i < function.parameters.size(); ++i) {
    if (!firstParameter) {
      out << ", ";
    }
    firstParameter = false;
    const HIRParameter &parameter = function.parameters[i];
    out << mapMetalType(parameter.type) << " " << parameter.name;
    if (entryPoint && stage != nullptr &&
        metalEntryParameterUsesStageIn(*stage, parameter, graphicsIORoles, i)) {
      out << " [[stage_in]]";
    }
  }
  if (entryPoint && stage != nullptr) {
    for (const MetalComputeBuiltinParameter &builtin :
         kMetalComputeBuiltinParameters) {
      if (!metalComputeEntryUsesBuiltin(stage, function, builtin.name,
                                        entryPoint)) {
        continue;
      }
      if (!firstParameter) {
        out << ", ";
      }
      firstParameter = false;
      out << "uint3 " << builtin.name << " [[" << builtin.attribute << "]]";
    }
    for (const HIRResource &resource : stage->resources) {
      if (!isMetalParameterResource(resource.kind)) {
        continue;
      }
      const std::size_t argumentIndex =
          metalResourceArgumentIndex(*stage, resource.name, &module.constants)
              .value_or(resource.binding);
      const std::optional<std::size_t> bufferArrayCount =
          resource.kind == HIRResourceKind::Buffer
              ? metalArrayElementCount(resource.type, &module.constants)
              : std::nullopt;
      if (bufferArrayCount.has_value()) {
        for (std::size_t arrayIndex = 0; arrayIndex < *bufferArrayCount;
             ++arrayIndex) {
          if (!firstParameter) {
            out << ", ";
          }
          firstParameter = false;
          out << mapMetalResourceType(resource) << " "
              << metalStorageBufferArrayElementName(resource.name, arrayIndex)
              << " [[" << metalResourceAttributeName(resource) << "("
              << (argumentIndex + arrayIndex) << ")]]";
        }
        continue;
      }
      if (!firstParameter) {
        out << ", ";
      }
      firstParameter = false;
      out << mapMetalResourceType(resource) << " " << resource.name << " [["
          << metalResourceAttributeName(resource) << "(" << argumentIndex
          << ")]]";
    }
  } else if (stage != nullptr && functionResourceParameters != nullptr) {
    const auto resourceParametersIt =
        functionResourceParameters->find(function.name);
    if (resourceParametersIt != functionResourceParameters->end()) {
      appendMetalHelperResourceParameters(out, resourceParametersIt->second,
                                          &module.constants, firstParameter);
    }
  }
  out << ") {\n"
      << renderMetalBody(stage, function, functionContext, entryPoint)
      << "}\n\n";
  return out.str();
}

void renderMetalStorageBufferDescriptorSelector(
    std::ostringstream &out, const HIRStage &stage, const HIRResource &resource,
    const std::vector<HIRConstant> &constants) {
  const std::optional<std::size_t> descriptorCount =
      metalArrayElementCount(resource.type, &constants);
  if (!descriptorCount.has_value()) {
    return;
  }

  const std::string resourceType = mapMetalResourceType(resource);
  out << resourceType << " "
      << metalStorageBufferDescriptorSelectorName(stage.stage, resource.name)
      << "(int descriptorIndex";
  for (std::size_t arrayIndex = 0; arrayIndex < *descriptorCount;
       ++arrayIndex) {
    out << ", " << resourceType << " "
        << metalStorageBufferArrayElementName(resource.name, arrayIndex);
  }
  out << ") {\n";
  out << "  if (descriptorIndex < 0 || descriptorIndex >= "
      << *descriptorCount << ") {\n";
  out << "    return " << metalStorageBufferArrayElementName(resource.name, 0)
      << ";\n";
  out << "  }\n";
  out << "  switch (descriptorIndex) {\n";
  for (std::size_t arrayIndex = 0; arrayIndex < *descriptorCount;
       ++arrayIndex) {
    out << "  case " << arrayIndex << ":\n";
    out << "    return "
        << metalStorageBufferArrayElementName(resource.name, arrayIndex)
        << ";\n";
  }
  out << "  default:\n";
  out << "    return " << metalStorageBufferArrayElementName(resource.name, 0)
      << ";\n";
  out << "  }\n";
  out << "}\n\n";
}

std::map<std::string, std::string>
metalRuntimeResourceDescriptorArrayTableDefinitions(const HIRModule &module) {
  std::map<std::string, std::string> definitions;
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (isMetalRuntimeResourceDescriptorArray(resource)) {
        definitions.emplace(
            metalRuntimeResourceDescriptorArrayTableTypeName(resource),
            metalRuntimeResourceDescriptorArrayElementType(resource));
      }
    }
  }
  return definitions;
}

} // namespace

MetalCompileOptions metalCompileOptionsForProfile(MetalBuildProfile profile) {
  MetalCompileOptions options;
  options.policyName = "metal-conservative-native-package-v1";
  switch (profile) {
  case MetalBuildProfile::Debug:
    options.profileName = "debug";
    options.requestedOptimizationLevel = "O0";
    options.optimizationLevel = "-O0";
    options.debugInfo = true;
    options.description =
        "Disable Metal source optimization and retain line-table debug info "
        "for package debugging.";
    options.metalFlags = {"-O0", "-gline-tables-only"};
    break;
  case MetalBuildProfile::Release:
    options.profileName = "release";
    options.requestedOptimizationLevel = "O2";
    options.optimizationLevel = "-O2";
    options.debugInfo = false;
    options.description =
        "Use a conservative explicit Metal release optimization request while "
        "leaving metallib linking at its default behavior.";
    options.metalFlags = {"-O2"};
    break;
  }
  return options;
}

MetalCompileOptions
metalCompileOptionsForOptimizationLevel(OptimizationLevel level) {
  MetalCompileOptions options;
  switch (level) {
  case OptimizationLevel::O0:
    options = metalCompileOptionsForProfile(MetalBuildProfile::Debug);
    break;
  case OptimizationLevel::O1:
    options = metalCompileOptionsForProfile(MetalBuildProfile::Release);
    break;
  case OptimizationLevel::O2:
    options = metalCompileOptionsForProfile(MetalBuildProfile::Release);
    break;
  }
  options.requestedOptimizationLevel =
      std::string(optimizationLevelName(level));
  return options;
}

std::string generateMetalSource(const HIRModule &module) {
  if (moduleContainsRawStatement(module)) {
    return "// error: opt.hir-raw-statement-backend-input: Metal backend "
           "input cannot contain HIR raw statements; lower them to "
           "structured HIR before backend emission\n";
  }

  std::ostringstream out;
  const MetalGraphicsIORoles graphicsIORoles =
      deriveMetalGraphicsIORoles(module);
  out << "#include <metal_stdlib>\n";
  out << "using namespace metal;\n\n";
  const std::map<std::string, std::string> descriptorTableDefinitions =
      metalRuntimeResourceDescriptorArrayTableDefinitions(module);
  for (const auto &[tableType, elementType] : descriptorTableDefinitions) {
    out << "struct " << tableType << " {\n"
        << "  array<" << elementType << ", "
        << kMetalRuntimeResourceDescriptorArrayTableCapacity
        << "> descriptors [[id(0)]];\n"
        << "};\n\n";
  }
  if (moduleUsesImplicitSampler(module)) {
    out << "constexpr sampler crossgl_default_sampler(coord::normalized, "
           "address::clamp_to_edge, filter::linear);\n\n";
  }
  if (moduleUsesManualTextureCompare(module)) {
    renderMetalManualCompareHelper(out);
  }

  const MetalRenderContext moduleContext{
      &module.structs, &module.constants, nullptr, nullptr, {}, {}, {}};
  for (const HIRConstant &constant : module.constants) {
    out << "constant " << mapMetalType(constant.type) << " " << constant.name
        << " = " << renderMetalExpression(constant.value, moduleContext)
        << ";\n";
  }
  if (!module.constants.empty()) {
    out << "\n";
  }

  for (const HIRStruct &structure : module.structs) {
    out << "struct " << structure.name << " {\n";
    for (std::size_t i = 0; i < structure.fields.size(); ++i) {
      if (shouldOmitMetalStructField(structure, i)) {
        continue;
      }
      const HIRField &field = structure.fields[i];
      out << "  " << mapMetalType(field.type) << " " << field.name
          << fieldAttribute(structure, field, i, graphicsIORoles) << ";\n";
    }
    out << "};\n\n";
  }

  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind == HIRResourceKind::Buffer &&
          resource.type.arraySize.has_value()) {
        renderMetalStorageBufferDescriptorSelector(out, stage, resource,
                                                   module.constants);
      }
    }
  }

  for (const HIRFunction &function : module.functions) {
    out << renderFunction(nullptr, function, module, graphicsIORoles, false);
  }

  for (const HIRStage &stage : module.stages) {
    const MetalFunctionResourceParameterMap functionResourceParameters =
        metalStageFunctionResourceParameters(stage);
    for (const HIRFunction &function : stage.functions) {
      if (function.name != stage.entryPointName) {
        out << renderFunction(&stage, function, module, graphicsIORoles, false,
                              &functionResourceParameters);
      }
    }
    const HIRFunction *entry = entryFunction(stage);
    if (entry != nullptr) {
      out << renderFunction(&stage, *entry, module, graphicsIORoles, true,
                            &functionResourceParameters);
    }
  }

  return out.str();
}

std::string metalResourceABIType(const HIRResource &resource) {
  if (isMetalRuntimeResourceDescriptorArray(resource)) {
    return metalRuntimeResourceDescriptorArrayTableParameterType(resource);
  }
  return mapMetalResourceType(resource);
}

std::string metalResourceAddressSpace(const HIRResource &resource) {
  if (isMetalRuntimeResourceDescriptorArray(resource)) {
    return "constant";
  }
  switch (resource.kind) {
  case HIRResourceKind::Uniform:
    return "constant";
  case HIRResourceKind::Buffer:
    return "device";
  case HIRResourceKind::Shared:
    return "threadgroup";
  case HIRResourceKind::Texture:
    return "texture";
  case HIRResourceKind::StorageImage:
    return "texture";
  case HIRResourceKind::Sampler:
    return "sampler";
  case HIRResourceKind::Value:
    break;
  }
  return "";
}

std::string metalResourceBindingClass(HIRResourceKind kind) {
  return metalResourceAttributeName(kind);
}

std::string metalResourceBindingClass(const HIRResource &resource) {
  return metalResourceAttributeName(resource);
}

bool metalResourceIsKernelParameter(HIRResourceKind kind) {
  return isMetalParameterResource(kind);
}

std::optional<std::size_t>
metalResourceArgumentIndex(const HIRStage &stage, std::string_view resourceName,
                           const std::vector<HIRConstant> *constants) {
  const HIRResource *target = nullptr;
  for (const HIRResource &resource : stage.resources) {
    if (resource.name == resourceName) {
      target = &resource;
      break;
    }
  }
  if (target == nullptr || !isMetalParameterResource(target->kind)) {
    return std::nullopt;
  }

  const std::optional<std::string> targetAttribute =
      metalResourceAttributeNamespace(*target);
  if (!targetAttribute.has_value()) {
    return std::nullopt;
  }

  const std::map<std::string, std::size_t> setZeroArgumentIndices =
      assignMetalSetZeroArgumentSlots(stage, *targetAttribute, constants);
  std::set<std::size_t> usedIndices;
  for (const HIRResource &resource : stage.resources) {
    if (resource.set != 0 ||
        metalResourceAttributeNamespace(resource) != targetAttribute) {
      continue;
    }
    const auto assigned = setZeroArgumentIndices.find(resource.name);
    if (assigned != setZeroArgumentIndices.end()) {
      reserveMetalArgumentSlots(usedIndices, assigned->second,
                                metalResourceArgumentSlotCount(resource,
                                                               constants));
    }
  }

  std::size_t nextPackedIndex = 0;
  auto nextFreePackedIndex = [&](std::size_t slotCount) {
    nextPackedIndex = firstFreeMetalArgumentRangeAtOrAfter(
        usedIndices, nextPackedIndex, slotCount);
    const std::size_t index = nextPackedIndex;
    reserveMetalArgumentSlots(usedIndices, index, slotCount);
    nextPackedIndex += slotCount;
    return index;
  };

  for (const HIRResource &resource : stage.resources) {
    if (metalResourceAttributeNamespace(resource) != targetAttribute) {
      continue;
    }
    const std::size_t slotCount =
        metalResourceArgumentSlotCount(resource, constants);
    const auto assignedSetZeroIndex = setZeroArgumentIndices.find(resource.name);
    const std::size_t argumentIndex =
        resource.set == 0 && assignedSetZeroIndex != setZeroArgumentIndices.end()
            ? assignedSetZeroIndex->second
            : nextFreePackedIndex(slotCount);
    if (resource.name == resourceName) {
      return argumentIndex;
    }
  }

  return std::nullopt;
}

bool metalResourceRequiresLegalizedBinding(
    const BackendPlanResource &resource) {
  return resource.source != nullptr && resource.emitsTargetBinding;
}

bool metalResourceBindingRecordMatchesIdentity(
    const TargetLegalizationResourceBindingRecord &record,
    const BackendPlanResource &resource) {
  return record.target == TargetKind::Metal && record.stage == resource.stage &&
         record.sourceEntryPoint == resource.entryPoint &&
         record.backendEntryPoint == resource.backendEntryPoint &&
         record.name == resource.name;
}

std::vector<const TargetLegalizationResourceBindingRecord *>
metalResourceBindingRecordsForResource(
    const TargetLegalizationResourceBindingFacts *resourceBindings,
    const BackendPlanResource &resource) {
  std::vector<const TargetLegalizationResourceBindingRecord *> records;
  if (resourceBindings == nullptr ||
      resourceBindings->target != TargetKind::Metal) {
    return records;
  }
  for (const TargetLegalizationResourceBindingRecord &record :
       resourceBindings->records) {
    if (metalResourceBindingRecordMatchesIdentity(record, resource)) {
      records.push_back(&record);
    }
  }
  return records;
}

std::string metalDeclarationResourceLabel(const BackendPlanResource &resource) {
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

void appendMetalDeclarationRecordMismatch(
    std::vector<std::string> &mismatches, std::string_view field,
    std::string_view expected, std::string_view actual) {
  mismatches.push_back(std::string(field) + " expected '" +
                       std::string(expected) + "', got '" +
                       std::string(actual) + "'");
}

void appendMetalDeclarationRecordMismatch(std::vector<std::string> &mismatches,
                                          std::string_view field,
                                          std::size_t expected,
                                          std::size_t actual) {
  appendMetalDeclarationRecordMismatch(
      mismatches, field, std::to_string(expected), std::to_string(actual));
}

std::string optionalMetalStringForDiagnostic(
    const std::optional<std::string> &value) {
  if (!value.has_value()) {
    return "<absent>";
  }
  return *value;
}

std::string joinMetalDeclarationMismatches(
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

std::vector<std::string> metalDeclarationRecordMismatches(
    const HIRModule &module, const BackendPlanStageInterface &stage,
    const BackendPlanResource &resource,
    const TargetLegalizationResourceBindingRecord &record) {
  std::vector<std::string> mismatches;
  if (resource.source == nullptr) {
    return mismatches;
  }
  const HIRResource &source = *resource.source;
  const bool kernelArgument = metalResourceIsKernelParameter(source.kind);
  const std::string expectedAbi =
      kernelArgument ? "kernelArgument" : "threadgroupLocal";

  if (record.abi != expectedAbi) {
    appendMetalDeclarationRecordMismatch(mismatches, "abi", expectedAbi,
                                         record.abi);
  }
  if (record.kind != resource.kindName) {
    appendMetalDeclarationRecordMismatch(mismatches, "kind", resource.kindName,
                                         record.kind);
  }
  if (record.sourceType != resource.sourceType) {
    appendMetalDeclarationRecordMismatch(mismatches, "sourceType",
                                         resource.sourceType,
                                         record.sourceType);
  }
  if (record.storageImageFormat != resource.storageImageFormat) {
    appendMetalDeclarationRecordMismatch(
        mismatches, "storageImageFormat",
        optionalMetalStringForDiagnostic(resource.storageImageFormat),
        optionalMetalStringForDiagnostic(record.storageImageFormat));
  }
  const std::string expectedMetalType = metalResourceABIType(source);
  if (!record.metalType.has_value()) {
    appendMetalDeclarationRecordMismatch(mismatches, "metalType",
                                         expectedMetalType, "<missing>");
  } else if (*record.metalType != expectedMetalType) {
    appendMetalDeclarationRecordMismatch(mismatches, "metalType",
                                         expectedMetalType, *record.metalType);
  }
  const std::string expectedAddressSpace = metalResourceAddressSpace(source);
  if (record.addressSpace != expectedAddressSpace) {
    appendMetalDeclarationRecordMismatch(
        mismatches, "addressSpace", expectedAddressSpace, record.addressSpace);
  }
  const std::string expectedBindingClass =
      kernelArgument ? metalResourceBindingClass(source) : "threadgroup";
  if (record.bindingClass != expectedBindingClass) {
    appendMetalDeclarationRecordMismatch(mismatches, "bindingClass",
                                         expectedBindingClass,
                                         record.bindingClass);
  }

  if (kernelArgument && stage.source != nullptr) {
    const std::size_t expectedArgumentIndex =
        metalResourceArgumentIndex(*stage.source, source.name,
                                   &module.constants)
            .value_or(source.binding);
    if (!record.argumentIndex.has_value()) {
      appendMetalDeclarationRecordMismatch(
          mismatches, "argumentIndex", std::to_string(expectedArgumentIndex),
          "<missing>");
    } else if (*record.argumentIndex != expectedArgumentIndex) {
      appendMetalDeclarationRecordMismatch(mismatches, "argumentIndex",
                                           expectedArgumentIndex,
                                           *record.argumentIndex);
    }
    if (!record.set.has_value()) {
      appendMetalDeclarationRecordMismatch(
          mismatches, "set", std::to_string(source.set), "<missing>");
    } else if (*record.set != source.set) {
      appendMetalDeclarationRecordMismatch(mismatches, "set", source.set,
                                           *record.set);
    }
    if (!record.binding.has_value()) {
      appendMetalDeclarationRecordMismatch(
          mismatches, "binding", std::to_string(source.binding), "<missing>");
    } else if (*record.binding != source.binding) {
      appendMetalDeclarationRecordMismatch(mismatches, "binding",
                                           source.binding, *record.binding);
    }
  } else {
    if (record.argumentIndex.has_value()) {
      appendMetalDeclarationRecordMismatch(
          mismatches, "argumentIndex", "<absent>",
          std::to_string(*record.argumentIndex));
    }
    if (record.set.has_value()) {
      appendMetalDeclarationRecordMismatch(mismatches, "set", "<absent>",
                                           std::to_string(*record.set));
    }
    if (record.binding.has_value()) {
      appendMetalDeclarationRecordMismatch(mismatches, "binding", "<absent>",
                                           std::to_string(*record.binding));
    }
  }
  if (record.descriptorType.has_value()) {
    appendMetalDeclarationRecordMismatch(
        mismatches, "descriptorType", "<absent>",
        optionalMetalStringForDiagnostic(record.descriptorType));
  }
  return mismatches;
}

bool diagnoseMetalLegalizedResourceDeclarationMismatches(
    const HIRModule &module,
    const TargetLegalizationResourceBindingFacts *resourceBindings,
    DiagnosticEngine &diagnostics) {
  if (resourceBindings == nullptr ||
      resourceBindings->target != TargetKind::Metal ||
      !resourceBindings->complete) {
    diagnostics.error(
        "metal.legalized-resource-binding-missing",
        "Metal native package requires complete legalized "
        "kernelArgument/threadgroupLocal records before MSL resource emission; "
        "missing binding record(s): resource-bindings");
    return true;
  }

  bool failed = false;
  std::set<std::string> matchedEvidenceIds;
  const BackendPlan plan = buildBackendPlan(module);
  for (const BackendPlanStageInterface &stage : plan.stages) {
    for (const BackendPlanResource &resource : stage.resources) {
      if (!metalResourceRequiresLegalizedBinding(resource)) {
        continue;
      }
      const std::vector<const TargetLegalizationResourceBindingRecord *> records =
          metalResourceBindingRecordsForResource(resourceBindings, resource);
      if (records.empty()) {
        diagnostics.error(
            "metal.legalized-resource-binding-missing",
            "missing Metal legalized resource-binding record for " +
                metalDeclarationResourceLabel(resource));
        failed = true;
        continue;
      }
      if (records.size() > 1) {
        diagnostics.error(
            "metal.legalized-resource-binding-mismatch",
            "duplicate Metal legalized resource-binding records for " +
                metalDeclarationResourceLabel(resource));
        failed = true;
      }
      for (const TargetLegalizationResourceBindingRecord *record : records) {
        matchedEvidenceIds.insert(record->evidenceId);
        const std::vector<std::string> mismatches =
            metalDeclarationRecordMismatches(module, stage, resource, *record);
        if (mismatches.empty()) {
          continue;
        }
        diagnostics.error(
            "metal.legalized-resource-binding-mismatch",
            "Metal MSL declaration metadata disagrees with legalization "
            "record '" +
                record->evidenceId + "' for " +
                metalDeclarationResourceLabel(resource) + ": " +
                joinMetalDeclarationMismatches(mismatches));
        failed = true;
      }
    }
  }

  for (const TargetLegalizationResourceBindingRecord &record :
       resourceBindings->records) {
    if (record.target == TargetKind::Metal &&
        matchedEvidenceIds.count(record.evidenceId) == 0) {
      diagnostics.error(
          "metal.legalized-resource-binding-mismatch",
          "stale Metal legalized resource-binding record '" +
              record.evidenceId + "' for resource '" + record.name +
              "' has no matching MSL declaration input");
      failed = true;
    }
  }
  return failed;
}

bool validateMetalRuntimeTailBlockIndexExpression(
    const HIRExpression &expression, const MetalRenderContext &context,
    const std::set<std::string> &runtimeTailResources,
    DiagnosticEngine &diagnostics) {
  if (expression.kind == HIRExpressionKind::IndexAccess &&
      expression.children.size() >= 2 &&
      expression.children[0].kind == HIRExpressionKind::Identifier &&
      runtimeTailResources.contains(expression.children[0].value) &&
      !isMetalZeroIndexExpression(expression.children[1], context)) {
    diagnostics.error(
        "metal.unsupported-runtime-array-block-index",
        "Metal backend only supports direct singleton, literal-zero, or "
        "folded-zero access for runtime-tail storage-buffer block '" +
            expression.children[0].value + "'");
    return false;
  }
  return true;
}

bool validateMetalRuntimeTailBlockIndexStatement(
    const HIRStatement &statement, const MetalRenderContext &context,
    const std::set<std::string> &runtimeTailResources,
    DiagnosticEngine &diagnostics) {
  bool valid = true;
  auto visitor = [&](const HIRExpression &expression) {
    valid = validateMetalRuntimeTailBlockIndexExpression(
                expression, context, runtimeTailResources, diagnostics) &&
            valid;
  };
  visitMetalValidationStatementExpressionsRenderedSource(statement, visitor);
  return valid;
}

bool validateMetalRuntimeTailBlockIndexes(const HIRModule &module,
                                          DiagnosticEngine &diagnostics) {
  bool valid = true;
  for (const HIRStage &stage : module.stages) {
    std::set<std::string> runtimeTailResources;
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind != HIRResourceKind::Buffer) {
        continue;
      }
      const HIRType elementType = bufferElementType(resource.type);
      const HIRStruct *structure =
          findStructByName(module.structs, elementType.name);
      if (structure != nullptr && metalStructHasRuntimeTail(*structure)) {
        runtimeTailResources.insert(resource.name);
      }
    }
    if (runtimeTailResources.empty()) {
      continue;
    }
    const MetalRenderContext context{&module.structs, &module.constants,
                                     &stage.resources, nullptr, stage.stage,
                                     {}, {}};
    for (const HIRFunction &function : stage.functions) {
      const MetalRenderContext functionContext =
          metalFunctionRenderContext(context, function);
      for (const HIRStatement &statement : function.body) {
        valid = validateMetalRuntimeTailBlockIndexStatement(
                    statement, functionContext, runtimeTailResources,
                    diagnostics) &&
                valid;
      }
    }
  }
  return valid;
}

bool validateMetalStorageBufferArrayIndexExpression(
    const HIRExpression &expression, const MetalRenderContext &context,
    DiagnosticEngine &diagnostics) {
  const HIRResource *resource =
      metalStorageBufferDescriptorArrayResource(expression, context);
  if (resource != nullptr && expression.children.size() >= 2) {
    const std::optional<std::size_t> descriptorCount =
        metalArrayElementCount(resource->type, context.constants);
    const std::optional<std::size_t> descriptorIndex =
        metalDescriptorArrayIndexValue(expression.children[1], context);
    const std::optional<std::int64_t> signedDescriptorIndex =
        metalDescriptorArraySignedIndexValue(expression.children[1], context);
    if (expression.children[1].kind == HIRExpressionKind::NonUniform) {
      // Target-specific nonuniform policy is reported separately.
    } else if (!descriptorCount.has_value()) {
      diagnostics.error("metal.unsupported-storage-buffer-array-index",
                        "Metal expanded storage-buffer descriptor array '" +
                            resource->name +
                            "' requires a fixed descriptor count");
      return false;
    } else if (descriptorIndex.has_value() &&
               *descriptorIndex >= *descriptorCount) {
      diagnostics.error("metal.unsupported-storage-buffer-array-index",
                        "Metal expanded storage-buffer descriptor array '" +
                            resource->name + "' index " +
                            std::to_string(*descriptorIndex) +
                            " is outside the fixed descriptor count");
      return false;
    } else if (signedDescriptorIndex.has_value() &&
               *signedDescriptorIndex < 0) {
      diagnostics.error("metal.unsupported-storage-buffer-array-index",
                        "Metal expanded storage-buffer descriptor array '" +
                            resource->name + "' index " +
                            std::to_string(*signedDescriptorIndex) +
                            " is outside the fixed descriptor count");
      return false;
    }
  }
  return true;
}

bool validateMetalStorageBufferArrayIndexStatement(
    const HIRStatement &statement, const MetalRenderContext &context,
    DiagnosticEngine &diagnostics) {
  bool valid = true;
  auto visitor = [&](const HIRExpression &expression) {
    valid = validateMetalStorageBufferArrayIndexExpression(expression, context,
                                                           diagnostics) &&
            valid;
  };
  visitMetalValidationStatementExpressionsRenderedSource(statement, visitor);
  return valid;
}

bool validateMetalStorageBufferArrayIndexes(const HIRModule &module,
                                            DiagnosticEngine &diagnostics) {
  bool valid = true;
  for (const HIRStage &stage : module.stages) {
    const MetalRenderContext context{&module.structs, &module.constants,
                                     &stage.resources, nullptr, stage.stage,
                                     {}, {}};
    for (const HIRFunction &function : stage.functions) {
      const MetalRenderContext functionContext =
          metalFunctionRenderContext(context, function);
      for (const HIRStatement &statement : function.body) {
        valid = validateMetalStorageBufferArrayIndexStatement(
                    statement, functionContext, diagnostics) &&
                valid;
      }
    }
  }
  return valid;
}

std::string metalArgumentSlotName(std::string_view bindingClass,
                                  std::size_t argumentIndex) {
  return std::string(bindingClass) + "(" + std::to_string(argumentIndex) + ")";
}

bool validateMetalArgumentSlots(const HIRModule &module,
                                DiagnosticEngine &diagnostics) {
  bool valid = true;
  for (const HIRStage &stage : module.stages) {
    std::map<std::pair<std::string, std::size_t>, std::string> usedSlots;
    for (const HIRResource &resource : stage.resources) {
      if (!isMetalParameterResource(resource.kind)) {
        continue;
      }
      const std::optional<std::size_t> firstIndex =
          metalResourceArgumentIndex(stage, resource.name, &module.constants);
      if (!firstIndex.has_value()) {
        continue;
      }

      const std::string bindingClass = metalResourceBindingClass(resource);
      const std::size_t slotCount =
          metalResourceArgumentSlotCount(resource, &module.constants);
      for (std::size_t offset = 0; offset < slotCount; ++offset) {
        const std::size_t argumentIndex = *firstIndex + offset;
        const auto key = std::make_pair(bindingClass, argumentIndex);
        const auto [it, inserted] = usedSlots.emplace(key, resource.name);
        if (!inserted) {
          diagnostics.error(
              "metal.argument-slot-collision",
              "Metal " + stage.stage + " resource '" + resource.name +
                  "' maps to " +
                  metalArgumentSlotName(bindingClass, argumentIndex) +
                  ", which overlaps resource '" + it->second + "'");
          valid = false;
        }
      }
    }
  }
  return valid;
}

bool validateMetalEntryParameterArrays(const HIRModule &module,
                                       DiagnosticEngine &diagnostics) {
  bool valid = true;
  for (const HIRStage &stage : module.stages) {
    const HIRFunction *entry = entryFunction(stage);
    if (entry == nullptr) {
      continue;
    }
    for (const HIRParameter &parameter : entry->parameters) {
      if (!parameter.type.arraySize.has_value()) {
        continue;
      }
      const std::string arrayKind =
          parameter.type.arraySize->empty() ? "runtime-sized" : "fixed-size";
      diagnostics.error(
          "metal.unsupported-entry-parameter-array",
          "Metal backend cannot lower " + arrayKind + " array parameter '" +
              parameter.name + "' on " + stage.stage + " entry point '" +
              entry->name +
              "' because MSL kernel parameters cannot be metal::array values; "
              "pass array data through a storage buffer or keep fixed arrays "
              "inside helper functions");
      valid = false;
    }
  }
  return valid;
}

std::set<std::string>
metalFixedArrayParameterNames(const HIRModule &module,
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

bool metalTypeHasNestedArray(const HIRType &type) {
  return type.arraySize.has_value() &&
         splitMetalArrayDimensions(*type.arraySize).size() > 1;
}

bool metalSupportsDynamicNestedHelperArrayRead(const HIRModule &module,
                                               const HIRType &type) {
  const std::string baseName = baseTypeName(type);
  return baseName == "bool" || isNumericScalarTypeName(baseName) ||
         isVectorType(baseName) || isMatrixType(baseName) ||
         findStructByName(module.structs, baseName) != nullptr;
}

bool metalSupportsDynamicNestedHelperArrayWrite(const HIRModule &module,
                                                const HIRType &type) {
  const std::string baseName = baseTypeName(type);
  return baseName == "bool" || isNumericScalarTypeName(baseName) ||
         isVectorType(baseName) || isMatrixType(baseName) ||
         findStructByName(module.structs, baseName) != nullptr;
}

std::set<std::string>
metalUnsupportedDynamicNestedArrayParameterNames(
    const HIRModule &module, const HIRFunction &function,
    bool (*isSupported)(const HIRModule &, const HIRType &)) {
  std::set<std::string> names;
  for (const HIRParameter &parameter : function.parameters) {
    if (functionParameterArrayShape(module, parameter.type) ==
            HIRFunctionParameterArrayShape::FixedSize &&
        metalTypeHasNestedArray(parameter.type) &&
        !isSupported(module, parameter.type)) {
      names.insert(parameter.name);
    }
  }
  return names;
}

const HIRExpression *
metalTransparentExpression(const HIRExpression &expression) {
  const HIRExpression *current = &expression;
  while ((current->kind == HIRExpressionKind::Group ||
          current->kind == HIRExpressionKind::NonUniform) &&
         current->children.size() == 1) {
    current = &current->children.front();
  }
  return current;
}

std::string joinMetalLabels(const std::set<std::string> &labels) {
  std::string result;
  for (const std::string &label : labels) {
    if (!result.empty()) {
      result += ", ";
    }
    result += label;
  }
  return result;
}

bool metalIsStaticArrayIndexExpression(const HIRModule &module,
                                       const HIRExpression &expression) {
  const MetalRenderContext context{nullptr, &module.constants, nullptr, nullptr,
                                   {}, {}, {}};
  return metalDescriptorArrayIndexValue(expression, context).has_value();
}

bool metalDynamicNestedParameterArrayAccess(
    const HIRModule &module, const HIRExpression &expression,
    const std::set<std::string> &parameterArrays, std::string &parameterName) {
  const HIRExpression *current = &expression;
  std::vector<const HIRExpression *> indices;
  while (true) {
    current = metalTransparentExpression(*current);
    if (current->kind != HIRExpressionKind::IndexAccess ||
        current->children.size() < 2) {
      break;
    }
    indices.push_back(&current->children[1]);
    current = &current->children[0];
  }

  current = metalTransparentExpression(*current);
  if (current->kind != HIRExpressionKind::Identifier ||
      !parameterArrays.contains(current->value) || indices.size() < 2) {
    return false;
  }

  for (const HIRExpression *index : indices) {
    if (!metalIsStaticArrayIndexExpression(module, *index)) {
      parameterName = current->value;
      return true;
    }
  }
  return false;
}

void collectMetalDynamicNestedFunctionParameterArrayReadsInStatement(
    const HIRModule &module, const HIRFunction &function,
    const std::set<std::string> &parameterArrays, const HIRStatement &statement,
    std::set<std::string> &labels) {
  auto visitor = [&](const HIRExpression &expression) {
    std::string parameterName;
    if (metalDynamicNestedParameterArrayAccess(module, expression,
                                               parameterArrays,
                                               parameterName)) {
      labels.insert("function '" + function.name + "' parameter '" +
                    parameterName + "'");
    }
  };
  visitExpressionTree(statement.value, visitor);

  for (const HIRStatement &child : statement.initializer) {
    collectMetalDynamicNestedFunctionParameterArrayReadsInStatement(
        module, function, parameterArrays, child, labels);
  }
  for (const HIRStatement &child : statement.update) {
    collectMetalDynamicNestedFunctionParameterArrayReadsInStatement(
        module, function, parameterArrays, child, labels);
  }
  for (const HIRStatement &child : statement.body) {
    collectMetalDynamicNestedFunctionParameterArrayReadsInStatement(
        module, function, parameterArrays, child, labels);
  }
  for (const HIRStatement &child : statement.elseBody) {
    collectMetalDynamicNestedFunctionParameterArrayReadsInStatement(
        module, function, parameterArrays, child, labels);
  }
}

void collectMetalDynamicNestedFunctionParameterArrayWritesInStatement(
    const HIRModule &module, const HIRFunction &function,
    const std::set<std::string> &parameterArrays, const HIRStatement &statement,
    std::set<std::string> &labels) {
  if (statement.kind == HIRStatementKind::Assignment) {
    std::string parameterName;
    if (metalDynamicNestedParameterArrayAccess(module, statement.target,
                                               parameterArrays,
                                               parameterName)) {
      labels.insert("function '" + function.name + "' parameter '" +
                    parameterName + "'");
    }
  }

  for (const HIRStatement &child : statement.initializer) {
    collectMetalDynamicNestedFunctionParameterArrayWritesInStatement(
        module, function, parameterArrays, child, labels);
  }
  for (const HIRStatement &child : statement.update) {
    collectMetalDynamicNestedFunctionParameterArrayWritesInStatement(
        module, function, parameterArrays, child, labels);
  }
  for (const HIRStatement &child : statement.body) {
    collectMetalDynamicNestedFunctionParameterArrayWritesInStatement(
        module, function, parameterArrays, child, labels);
  }
  for (const HIRStatement &child : statement.elseBody) {
    collectMetalDynamicNestedFunctionParameterArrayWritesInStatement(
        module, function, parameterArrays, child, labels);
  }
}

void collectMetalDynamicNestedFunctionParameterArrayReads(
    const HIRModule &module, const HIRFunction &function,
    std::set<std::string> &labels) {
  const std::set<std::string> parameterArrays =
      metalUnsupportedDynamicNestedArrayParameterNames(
          module, function, metalSupportsDynamicNestedHelperArrayRead);
  if (parameterArrays.empty()) {
    return;
  }
  for (const HIRStatement &statement : function.body) {
    collectMetalDynamicNestedFunctionParameterArrayReadsInStatement(
        module, function, parameterArrays, statement, labels);
  }
}

void collectMetalDynamicNestedFunctionParameterArrayWrites(
    const HIRModule &module, const HIRFunction &function,
    std::set<std::string> &labels) {
  const std::set<std::string> parameterArrays =
      metalUnsupportedDynamicNestedArrayParameterNames(
          module, function, metalSupportsDynamicNestedHelperArrayWrite);
  if (parameterArrays.empty()) {
    return;
  }
  for (const HIRStatement &statement : function.body) {
    collectMetalDynamicNestedFunctionParameterArrayWritesInStatement(
        module, function, parameterArrays, statement, labels);
  }
}

bool validateMetalDynamicNestedFunctionParameterArrayReads(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  std::set<std::string> labels;
  for (const HIRFunction &function : module.functions) {
    collectMetalDynamicNestedFunctionParameterArrayReads(module, function,
                                                         labels);
  }
  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &function : stage.functions) {
      collectMetalDynamicNestedFunctionParameterArrayReads(module, function,
                                                           labels);
    }
  }
  if (labels.empty()) {
    return true;
  }

  diagnostics.error(
      "metal.unsupported-dynamic-nested-helper-array-read",
      "Metal backend supports dynamic nested helper-array reads only for "
      "fixed-size scalar/vector/matrix/struct helper array parameter(s); "
      "unsupported parameter(s): " +
          joinMetalLabels(labels) +
          "; use literal or folded constant indices for other nested helper "
          "array element types in Metal source packages");
  return false;
}

bool validateMetalDynamicNestedFunctionParameterArrayWrites(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  std::set<std::string> labels;
  for (const HIRFunction &function : module.functions) {
    collectMetalDynamicNestedFunctionParameterArrayWrites(module, function,
                                                          labels);
  }
  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &function : stage.functions) {
      collectMetalDynamicNestedFunctionParameterArrayWrites(module, function,
                                                            labels);
    }
  }
  if (labels.empty()) {
    return true;
  }

  diagnostics.error(
      "metal.unsupported-dynamic-nested-helper-array-write",
      "Metal backend supports dynamic nested helper-array writes only for "
      "fixed-size scalar/vector/matrix/struct helper array parameter(s); "
      "unsupported parameter(s): " +
          joinMetalLabels(labels) +
          "; use literal or folded constant indices for other nested helper "
          "array element types in Metal source packages");
  return false;
}

const HIRFunction *findMetalCallableFunction(const HIRModule &module,
                                             const HIRStage *stage,
                                             std::string_view name) {
  if (stage != nullptr) {
    for (const HIRFunction &function : stage->functions) {
      if (function.name == name) {
        return &function;
      }
    }
  }
  for (const HIRFunction &function : module.functions) {
    if (function.name == name) {
      return &function;
    }
  }
  return nullptr;
}

HIRFunctionParameterArrayCallFeatureSupport
metalFunctionParameterArrayCallFeatureSupport(
    HIRFunctionParameterArrayCallFeature feature) {
  if (feature ==
          HIRFunctionParameterArrayCallFeature::DirectResourceArrayArguments ||
      feature == HIRFunctionParameterArrayCallFeature::StructElements) {
    return HIRFunctionParameterArrayCallFeatureSupport::Supported;
  }
  return functionParameterArrayCallFeatureSupport(feature);
}

bool metalSampledTextureOrSamplerArrayParameterSupported(const HIRModule &module,
                                                         const HIRType &type) {
  return functionParameterArrayShape(module, type) ==
             HIRFunctionParameterArrayShape::FixedSize &&
         (isTextureResourceType(type.name) || isSamplerResourceType(type.name));
}

HIRFunctionParameterArrayCallFeatureSupport
metalFunctionParameterArrayCallFeatureSupport(
    const HIRModule &module, const HIRType &parameterType,
    HIRFunctionParameterArrayCallFeature feature) {
  if (feature ==
          HIRFunctionParameterArrayCallFeature::DirectResourceArrayArguments &&
      !metalSampledTextureOrSamplerArrayParameterSupported(module,
                                                           parameterType)) {
    return HIRFunctionParameterArrayCallFeatureSupport::Unsupported;
  }
  return metalFunctionParameterArrayCallFeatureSupport(feature);
}

HIRFunctionParameterArrayCallFeatureSupport
metalFunctionParameterArrayCallFeaturesSupport(
    const HIRModule &module, const HIRType &parameterType,
    std::span<const HIRFunctionParameterArrayCallFeature> features) {
  for (HIRFunctionParameterArrayCallFeature feature : features) {
    if (metalFunctionParameterArrayCallFeatureSupport(module, parameterType,
                                                      feature) ==
        HIRFunctionParameterArrayCallFeatureSupport::Unsupported) {
      return HIRFunctionParameterArrayCallFeatureSupport::Unsupported;
    }
  }
  return HIRFunctionParameterArrayCallFeatureSupport::Supported;
}

std::string unsupportedMetalFunctionParameterArrayCallFeatures(
    const HIRModule &module, const HIRType &parameterType,
    const std::vector<HIRFunctionParameterArrayCallFeature> &features) {
  std::string result;
  for (const HIRFunctionParameterArrayCallFeature feature : features) {
    if (metalFunctionParameterArrayCallFeatureSupport(module, parameterType,
                                                      feature) !=
        HIRFunctionParameterArrayCallFeatureSupport::Unsupported) {
      continue;
    }
    if (!result.empty()) {
      result += ", ";
    }
    result += functionParameterArrayCallFeatureName(feature);
  }
  return result.empty() ? "unknown" : result;
}

bool validateMetalFunctionParameterArrayCallExpression(
    const HIRModule &module, const HIRStage *stage, const HIRFunction &caller,
    const HIRExpression &expression, DiagnosticEngine &diagnostics) {
  if (expression.kind != HIRExpressionKind::Call) {
    return true;
  }

  const HIRFunction *callee =
      findMetalCallableFunction(module, stage, expression.value);
  if (callee == nullptr) {
    return true;
  }

  bool valid = true;
  if (expression.children.size() != callee->parameters.size()) {
    diagnostics.error(
        "metal.function-call-arity",
        "Metal backend cannot lower call to helper function '" + callee->name +
            "' from function '" + caller.name + "' because it expects " +
            std::to_string(callee->parameters.size()) + " argument(s), got " +
            std::to_string(expression.children.size()) + " argument(s)");
    valid = false;
  }

  const std::size_t argumentCount =
      expression.children.size() < callee->parameters.size()
          ? expression.children.size()
          : callee->parameters.size();
  for (std::size_t argumentIndex = 0; argumentIndex < argumentCount;
       ++argumentIndex) {
    const HIRParameter &parameter = callee->parameters[argumentIndex];
    if (functionParameterArrayShape(module, parameter.type) !=
        HIRFunctionParameterArrayShape::FixedSize) {
      continue;
    }

    const std::vector<HIRFunctionParameterArrayCallFeature> features =
        functionParameterArrayCallArgumentFeatures(
            module, caller, expression.children[argumentIndex], stage);
    if (metalFunctionParameterArrayCallFeaturesSupport(
            module, parameter.type,
            std::span<const HIRFunctionParameterArrayCallFeature>{
                features.data(), features.size()}) ==
        HIRFunctionParameterArrayCallFeatureSupport::Supported) {
      continue;
    }

    diagnostics.error(
        "metal.unsupported-function-parameter-array-call-feature",
        "Metal backend cannot lower fixed-size array argument " +
            std::to_string(argumentIndex) + " passed to helper function '" +
            callee->name + "' from function '" + caller.name +
            "' because function-parameter array feature(s) " +
            unsupportedMetalFunctionParameterArrayCallFeatures(
                module, parameter.type, features) +
            " are unsupported for Metal's value-copy helper-array "
            "ABI");
    valid = false;
  }
  return valid;
}

bool validateMetalFunctionParameterArrayCallsInFunction(
    const HIRModule &module, const HIRStage *stage, const HIRFunction &function,
    DiagnosticEngine &diagnostics) {
  bool valid = true;
  auto visitor = [&](const HIRExpression &expression) {
    valid = validateMetalFunctionParameterArrayCallExpression(
                module, stage, function, expression, diagnostics) &&
            valid;
  };
  visitFunctionExpressions(function, visitor);
  return valid;
}

bool validateMetalFunctionParameterArrayCalls(const HIRModule &module,
                                              DiagnosticEngine &diagnostics) {
  bool valid = true;
  for (const HIRFunction &function : module.functions) {
    valid = validateMetalFunctionParameterArrayCallsInFunction(
                module, nullptr, function, diagnostics) &&
            valid;
  }
  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &function : stage.functions) {
      valid = validateMetalFunctionParameterArrayCallsInFunction(
                  module, &stage, function, diagnostics) &&
              valid;
    }
  }
  return valid;
}

bool metalTextureOrSamplerDescriptorArrayIndexAccess(
    const HIRExpression &expression, const MetalRenderContext &context) {
  if (expression.kind != HIRExpressionKind::IndexAccess ||
      expression.children.size() < 2) {
    return false;
  }

  const HIRExpression *base =
      metalTransparentExpression(expression.children[0]);
  if (base->kind != HIRExpressionKind::Identifier) {
    return false;
  }
  const HIRResource *resource = findMetalResource(context, base->value);
  return resource != nullptr &&
         (resource->kind == HIRResourceKind::Texture ||
          resource->kind == HIRResourceKind::Sampler) &&
         resource->type.arraySize.has_value();
}

bool metalStorageBufferDescriptorArrayIndexAccess(
    const HIRExpression &expression, const MetalRenderContext &context) {
  return metalStorageBufferDescriptorArrayResource(expression, context) !=
         nullptr;
}

bool metalStorageImageDescriptorArrayIndexAccess(
    const HIRExpression &expression, const MetalRenderContext &context) {
  if (expression.kind != HIRExpressionKind::IndexAccess ||
      expression.children.size() < 2) {
    return false;
  }

  const HIRExpression *base =
      metalTransparentExpression(expression.children[0]);
  if (base->kind != HIRExpressionKind::Identifier) {
    return false;
  }
  const HIRResource *resource = findMetalResource(context, base->value);
  return resource != nullptr &&
         resource->kind == HIRResourceKind::StorageImage &&
         resource->type.arraySize.has_value();
}

void reportUnsupportedMetalNonUniformDescriptorIndex(
    DiagnosticEngine &diagnostics, bool &reported) {
  if (reported) {
    return;
  }
  diagnostics.error(
      "metal.unsupported-nonuniform-descriptor-index",
      "Metal backend only supports nonuniform(...) for texture, sampler, or "
      "storage-image descriptor-array operands of texture sampling, texture "
      "comparison, manual comparison, or storage-image access operations; "
      "storage-buffer descriptor arrays still use expanded Metal buffer "
      "arguments");
  reported = true;
}

bool validateMetalNonUniformDescriptorIndexExpression(
    const HIRExpression &expression, const MetalRenderContext &context,
    DiagnosticEngine &diagnostics, bool &reported,
    bool allowTextureSamplerDescriptorArrayOperand,
    bool allowStorageImageDescriptorArrayOperand,
    bool allowNonUniformDescriptorArrayIndex) {
  if (expression.kind == HIRExpressionKind::NonUniform) {
    if (!allowNonUniformDescriptorArrayIndex) {
      reportUnsupportedMetalNonUniformDescriptorIndex(diagnostics, reported);
      return false;
    }
    bool valid = true;
    for (const HIRExpression &child : expression.children) {
      valid = validateMetalNonUniformDescriptorIndexExpression(
                  child, context, diagnostics, reported, false, false, false) &&
              valid;
    }
    return valid;
  }

  if (expression.kind == HIRExpressionKind::IndexAccess) {
    bool valid = true;
    if (!expression.children.empty()) {
      valid = validateMetalNonUniformDescriptorIndexExpression(
                  expression.children[0], context, diagnostics, reported, false,
                  false, allowNonUniformDescriptorArrayIndex) &&
              valid;
    }
    const bool allowDescriptorIndex =
        allowTextureSamplerDescriptorArrayOperand &&
        metalTextureOrSamplerDescriptorArrayIndexAccess(expression, context);
    const bool allowStorageImageDescriptorIndex =
        allowStorageImageDescriptorArrayOperand &&
        metalStorageImageDescriptorArrayIndexAccess(expression, context);
    const bool allowStorageBufferDescriptorIndex =
        metalStorageBufferDescriptorArrayIndexAccess(expression, context);
    if (expression.children.size() >= 2) {
      valid = validateMetalNonUniformDescriptorIndexExpression(
                  expression.children[1], context, diagnostics, reported, false,
                  false,
                  allowDescriptorIndex || allowStorageImageDescriptorIndex ||
                      allowStorageBufferDescriptorIndex ||
                      allowNonUniformDescriptorArrayIndex) &&
              valid;
    }
    for (std::size_t i = 2; i < expression.children.size(); ++i) {
      valid = validateMetalNonUniformDescriptorIndexExpression(
                  expression.children[i], context, diagnostics, reported, false,
                  false, allowNonUniformDescriptorArrayIndex) &&
              valid;
    }
    return valid;
  }

  if (expression.kind == HIRExpressionKind::TextureSample) {
    bool valid = true;
    const bool hasExplicitSampler =
        metalTextureSampleHasExplicitSampler(expression);
    for (std::size_t i = 0; i < expression.children.size(); ++i) {
      const bool allowDescriptorIndex =
          i == 0 || (hasExplicitSampler && i == 1);
      valid = validateMetalNonUniformDescriptorIndexExpression(
                  expression.children[i], context, diagnostics, reported,
                  allowDescriptorIndex, false, false) &&
              valid;
    }
    return valid;
  }

  if (expression.kind == HIRExpressionKind::TextureCompare) {
    bool valid = true;
    for (std::size_t i = 0; i < expression.children.size(); ++i) {
      const bool allowDescriptorIndex = i == 0 || i == 1;
      valid = validateMetalNonUniformDescriptorIndexExpression(
                  expression.children[i], context, diagnostics, reported,
                  allowDescriptorIndex, false, false) &&
              valid;
    }
    return valid;
  }

  if (expression.kind == HIRExpressionKind::TextureCompareLodManual) {
    bool valid = true;
    const std::optional<TextureCompareManualOperands> manualOperands =
        textureCompareManualOperands(expression);
    for (const HIRExpression &child : expression.children) {
      const bool allowDescriptorIndex =
          manualOperands.has_value() && (&child == manualOperands->texture ||
                                         &child == manualOperands->sampler);
      valid = validateMetalNonUniformDescriptorIndexExpression(
                  child, context, diagnostics, reported, allowDescriptorIndex,
                  false, false) &&
              valid;
    }
    return valid;
  }

  if (expression.kind == HIRExpressionKind::Call &&
      (expression.value == "imageLoad" || expression.value == "imageStore" ||
       metalImageAtomicFunctionName(expression.value).has_value())) {
    bool valid = true;
    for (std::size_t i = 0; i < expression.children.size(); ++i) {
      valid = validateMetalNonUniformDescriptorIndexExpression(
                  expression.children[i], context, diagnostics, reported, false,
                  i == 0, false) &&
              valid;
    }
    return valid;
  }

  bool valid = true;
  for (const HIRExpression &child : expression.children) {
    valid = validateMetalNonUniformDescriptorIndexExpression(
                child, context, diagnostics, reported, false, false,
                allowNonUniformDescriptorArrayIndex) &&
            valid;
  }
  return valid;
}

bool validateMetalNonUniformDescriptorIndexStatement(
    const HIRStatement &statement, const MetalRenderContext &context,
    DiagnosticEngine &diagnostics, bool &reported) {
  bool valid = true;
  valid = validateMetalNonUniformDescriptorIndexExpression(
              statement.target, context, diagnostics, reported, false, false,
              false) &&
          valid;
  valid = validateMetalNonUniformDescriptorIndexExpression(
              statement.value, context, diagnostics, reported, false, false,
              false) &&
          valid;
  for (const HIRStatement &initializer : statement.initializer) {
    valid = validateMetalNonUniformDescriptorIndexStatement(
                initializer, context, diagnostics, reported) &&
            valid;
  }
  for (const HIRStatement &update : statement.update) {
    valid = validateMetalNonUniformDescriptorIndexStatement(
                update, context, diagnostics, reported) &&
            valid;
  }
  for (const HIRStatement &child : statement.body) {
    valid = validateMetalNonUniformDescriptorIndexStatement(
                child, context, diagnostics, reported) &&
            valid;
  }
  for (const HIRStatement &child : statement.elseBody) {
    valid = validateMetalNonUniformDescriptorIndexStatement(
                child, context, diagnostics, reported) &&
            valid;
  }
  return valid;
}

bool validateMetalNonUniformDescriptorIndexFunction(
    const HIRFunction &function, const MetalRenderContext &context,
    DiagnosticEngine &diagnostics, bool &reported) {
  bool valid = true;
  for (const HIRStatement &statement : function.body) {
    valid = validateMetalNonUniformDescriptorIndexStatement(
                statement, context, diagnostics, reported) &&
            valid;
  }
  return valid;
}

bool validateMetalNonUniformDescriptorIndexes(const HIRModule &module,
                                              DiagnosticEngine &diagnostics) {
  bool valid = true;
  bool reported = false;
  const MetalRenderContext moduleContext{
      &module.structs, &module.constants, nullptr, nullptr, {}, {}, {}};
  for (const HIRConstant &constant : module.constants) {
    valid = validateMetalNonUniformDescriptorIndexExpression(
                constant.value, moduleContext, diagnostics, reported, false,
                false, false) &&
            valid;
  }
  for (const HIRFunction &function : module.functions) {
    valid = validateMetalNonUniformDescriptorIndexFunction(
                function, moduleContext, diagnostics, reported) &&
            valid;
  }
  for (const HIRStage &stage : module.stages) {
    const MetalRenderContext stageContext{&module.structs, &module.constants,
                                          &stage.resources, nullptr,
                                          stage.stage, {}, {}};
    for (const HIRFunction &function : stage.functions) {
      valid = validateMetalNonUniformDescriptorIndexFunction(
                  function, stageContext, diagnostics, reported) &&
              valid;
    }
  }
  return valid;
}

bool isMetalConstructorTypeSupported(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  return baseName == "bool" || isNumericScalarTypeName(baseName) ||
         isVectorType(baseName) || isMatrixType(baseName);
}

bool validateMetalConstructorExpressions(const HIRModule &module,
                                         DiagnosticEngine &diagnostics) {
  bool valid = true;
  auto visitor = [&](const HIRExpression &expression) {
    if (expression.kind != HIRExpressionKind::Constructor ||
        backendConstructorShapeSupported(
            expression, isMetalConstructorTypeSupported,
            [](const HIRExpression &) { return true; })) {
      return;
    }
    diagnostics.error(
        "metal.unsupported-constructor",
        "Metal backend cannot emit constructor '" + expression.value +
            "' with result type '" + formatType(expression.type) +
            "' and " + std::to_string(expression.children.size()) +
            " operand(s)");
    valid = false;
  };
  visitModuleExpressions(module, visitor, true);
  return valid;
}

bool validateMetalRuntimeResourceDescriptorArrayPolicy(
    const HIRModule &module, DiagnosticEngine &diagnostics) {
  bool valid = true;
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (!isMetalRuntimeResourceDescriptorArray(resource)) {
        continue;
      }
      const std::string elementType =
          metalRuntimeResourceDescriptorArrayElementType(resource);
      if (elementType.empty()) {
        diagnostics.error(
            "metal.unsupported-runtime-resource-array",
            "Metal backend cannot derive a typed argument-buffer descriptor "
            "table for runtime texture/sampler descriptor array '" +
                resource.name + "'");
        valid = false;
      }
    }
  }

  return valid;
}

bool validateMetalResources(const HIRModule &module,
                            DiagnosticEngine &diagnostics) {
  bool valid = true;
  std::set<std::string> storageBufferBlockStructs;
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind != HIRResourceKind::Buffer) {
        continue;
      }
      const HIRType elementType = bufferElementType(resource.type);
      if (findStructByName(module.structs, elementType.name) != nullptr) {
        storageBufferBlockStructs.insert(elementType.name);
      }
    }
  }

  for (const HIRStruct &structure : module.structs) {
    for (std::size_t fieldIndex = 0; fieldIndex < structure.fields.size();
         ++fieldIndex) {
      const HIRField &field = structure.fields[fieldIndex];
      if (isRuntimeArrayType(field.type)) {
        const bool isSupportedTail =
            isMetalRuntimeTailField(structure, fieldIndex) &&
            storageBufferBlockStructs.contains(structure.name) &&
            runtimeTailFieldOffset(structure, fieldIndex,
                                   StorageLayoutKind::MetalDevice,
                                   module.structs, module.constants)
                .has_value();
        if (!isSupportedTail) {
          diagnostics.error(
              "metal.unsupported-runtime-array-field",
              "Metal backend only supports unsized/runtime array field '" +
                  structure.name + "." + field.name +
                  "' when it is the final field of a storage-buffer block");
          valid = false;
        }
      }
    }
  }
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind == HIRResourceKind::Buffer &&
          resource.type.arraySize.has_value()) {
        const std::optional<std::size_t> descriptorCount =
            metalArrayElementCount(resource.type, &module.constants);
        if (!descriptorCount.has_value()) {
          diagnostics.error(
              "metal.unsupported-storage-buffer-array",
              "Metal backend supports storage-buffer descriptor array '" +
                  resource.name +
                  "' only with a positive numeric or folded-constant size");
          valid = false;
        }
        continue;
      }
      if (isRuntimeArrayType(resource.type)) {
        if (isMetalRuntimeResourceDescriptorArray(resource)) {
          continue;
        }
        diagnostics.error(
            "metal.unsupported-runtime-resource-array",
            "Metal backend does not yet support unsized/runtime resource array "
            "'" +
                resource.name +
                "'; use a fixed descriptor array size for native Metal "
                "builds");
        valid = false;
        continue;
      }
    }
  }
  valid = validateMetalEntryParameterArrays(module, diagnostics) && valid;
  valid = validateMetalDynamicNestedFunctionParameterArrayReads(module,
                                                                diagnostics) &&
          valid;
  valid = validateMetalDynamicNestedFunctionParameterArrayWrites(
              module, diagnostics) &&
          valid;
  valid =
      validateMetalFunctionParameterArrayCalls(module, diagnostics) && valid;
  valid =
      validateMetalNonUniformDescriptorIndexes(module, diagnostics) && valid;
  valid = validateMetalConstructorExpressions(module, diagnostics) && valid;
  valid = validateMetalStorageBufferArrayIndexes(module, diagnostics) && valid;
  valid = validateMetalRuntimeTailBlockIndexes(module, diagnostics) && valid;
  valid = validateMetalRuntimeResourceDescriptorArrayPolicy(module,
                                                           diagnostics) &&
          valid;
  if (!valid) {
    return false;
  }
  return validateMetalArgumentSlots(module, diagnostics);
}

bool metalNativeBackendSupported(const HIRModule &module,
                                 DiagnosticEngine &diagnostics) {
  if (diagnoseRawStatementBackendInput(module, diagnostics)) {
    return false;
  }
  return validateMetalResources(module, diagnostics);
}

MetalBuildResult
buildMetalBinary(const HIRModule &module,
                 const std::filesystem::path &packageDir,
                 DiagnosticEngine &diagnostics,
                 const TargetLegalizationResourceBindingFacts *resourceBindings,
                 OptimizationLevel optimizationLevel) {
  MetalBuildResult result;

  if (!metalNativeBackendSupported(module, diagnostics)) {
    return result;
  }
  if (diagnoseMetalLegalizedResourceDeclarationMismatches(
          module, resourceBindings, diagnostics)) {
    return result;
  }

  const auto backendDir = packageDir / "backend" / "metal";
  std::error_code error;
  std::filesystem::create_directories(backendDir, error);
  if (error) {
    diagnostics.error("artifact.create-directory",
                      "failed to create Metal backend directory: " +
                          error.message());
    return result;
  }

  result.sourcePath = backendDir / (module.name + ".metal");
  result.airPath = backendDir / (module.name + ".air");
  result.metallibPath = backendDir / (module.name + ".metallib");
  result.compileOptionsPath =
      backendDir / (module.name + ".metal-compile-options.json");

  const MetalCompileOptions compileOptions =
      metalCompileOptionsForOptimizationLevel(optimizationLevel);
  result.optimizationRequestedLevel = compileOptions.requestedOptimizationLevel;
  result.optimizationPolicy = compileOptions.policyName;
  result.optimizationProfile = compileOptions.profileName;
  result.optimizationLevel = compileOptions.optimizationLevel;
  result.optimizationDebugInfo = compileOptions.debugInfo;
  result.optimizationFlags = compileOptions.metalFlags;

  {
    std::ofstream source(result.sourcePath);
    if (!source) {
      diagnostics.error("artifact.write-metal-source",
                        "failed to write generated Metal source");
      return result;
    }
    source << generateMetalSource(module);
  }

  if (!findExecutable("xcrun")) {
    diagnostics.error("metal.xcrun-missing",
                      "xcrun is required to compile Metal binaries on macOS");
    return result;
  }

  {
    std::ofstream metadata(result.compileOptionsPath);
    if (!metadata) {
      diagnostics.error("artifact.write-metal-compile-options",
                        "failed to write Metal compile option metadata");
      return result;
    }
    metadata << metalCompileOptionsJson(module, compileOptions);
  }

  const std::vector<std::string> metalCommand =
      metalCompileCommand(compileOptions, result.sourcePath, result.airPath);
  result.metalCompilerProvenance = captureToolInvocationProvenance(
      "xcrun metal", metalCommand, result.airPath.string(), {}, "metal");
  int status = runProcess(metalCommand);
  completeToolInvocationProvenance(*result.metalCompilerProvenance, status);
  if (status != 0) {
    diagnostics.error("metal.compile-failed",
                      "Apple metal compiler failed for generated source");
    return result;
  }
  if (!verifyMetalToolOutput(result.airPath, "metal.air-missing",
                             "xcrun metal", "AIR", diagnostics)) {
    return result;
  }

  const std::vector<std::string> metallibCommand =
      metalLibraryCommand(compileOptions, result.airPath, result.metallibPath);
  result.metallibProvenance = captureToolInvocationProvenance(
      "xcrun metallib", metallibCommand, result.metallibPath.string(), {},
      "metallib");
  status = runProcess(metallibCommand);
  completeToolInvocationProvenance(*result.metallibProvenance, status);
  if (status != 0) {
    diagnostics.error("metal.library-failed",
                      "metallib failed for generated AIR");
    return result;
  }
  if (!verifyMetalToolOutput(result.metallibPath, "metal.metallib-missing",
                             "xcrun metallib", "metallib", diagnostics)) {
    return result;
  }

  result.success = true;
  return result;
}

MetalBuildResult buildMetalBinary(const HIRModule &module,
                                  const std::filesystem::path &packageDir,
                                  DiagnosticEngine &diagnostics,
                                  OptimizationLevel optimizationLevel) {
  const TargetLegalizationResult legalization =
      legalizeTarget(module, TargetKind::Metal);
  return buildMetalBinary(module, packageDir, diagnostics,
                          &legalization.resourceBindings, optimizationLevel);
}

MetalBuildResult buildMetalBinary(
    const HIRModule &module, const std::filesystem::path &packageDir,
    DiagnosticEngine &diagnostics,
    const TargetLegalizationResourceBindingFacts &resourceBindings,
    OptimizationLevel optimizationLevel) {
  return buildMetalBinary(module, packageDir, diagnostics, &resourceBindings,
                          optimizationLevel);
}

} // namespace crossgl
