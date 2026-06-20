#include "crossgl/HIR/TypeSemantics.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <utility>

namespace crossgl {
namespace {

constexpr std::array<std::string_view, 57> kBuiltinTypeNames = {
    "void",
    "bool",
    "int",
    "uint",
    "float",
    "double",
    "half",
    "vec2",
    "vec3",
    "vec4",
    "ivec2",
    "ivec3",
    "ivec4",
    "uvec2",
    "uvec3",
    "uvec4",
    "bvec2",
    "bvec3",
    "bvec4",
    "mat2",
    "mat3",
    "mat4",
    "mat2x2",
    "mat3x3",
    "mat4x4",
    "sampler",
    "comparison_sampler",
    "sampler2D",
    "sampler2DArray",
    "sampler3D",
    "samplerCube",
    "samplerCubeArray",
    "sampler2DShadow",
    "sampler2DArrayShadow",
    "samplerCubeShadow",
    "samplerCubeArrayShadow",
    "isampler2D",
    "isampler2DArray",
    "isampler3D",
    "isamplerCube",
    "isamplerCubeArray",
    "usampler2D",
    "usampler2DArray",
    "usampler3D",
    "usamplerCube",
    "usamplerCubeArray",
    "texture2D",
    "texture2DArray",
    "texture3D",
    "textureCube",
    "textureCubeArray",
    "image2D",
    "iimage2D",
    "uimage2D",
    "image2DArray",
    "iimage2DArray",
    "uimage2DArray",
};

bool containsBuiltin(std::string_view name) {
  return std::find(kBuiltinTypeNames.begin(), kBuiltinTypeNames.end(), name) !=
         kBuiltinTypeNames.end();
}

std::string resourceBaseType(std::string_view name) {
  std::string base(name);
  base = stripTypeQualifier(std::move(base));
  return stripPointerSuffix(std::move(base));
}

std::string trim(std::string_view value) {
  std::size_t begin = 0;
  while (begin < value.size() &&
         std::isspace(static_cast<unsigned char>(value[begin]))) {
    ++begin;
  }
  std::size_t end = value.size();
  while (end > begin &&
         std::isspace(static_cast<unsigned char>(value[end - 1]))) {
    --end;
  }
  return std::string(value.substr(begin, end - begin));
}

} // namespace

std::string stripTypeQualifier(std::string name) {
  if (name.rfind("buffer ", 0) == 0) {
    return name.substr(7);
  }
  if (name.rfind("uniform ", 0) == 0) {
    return name.substr(8);
  }
  if (name.rfind("shared ", 0) == 0) {
    return name.substr(7);
  }
  return name;
}

HIRType stripTypeQualifier(HIRType type) {
  type.name = stripTypeQualifier(std::move(type.name));
  return type;
}

std::string stripPointerSuffix(std::string name) {
  while (!name.empty() && name.back() == '*') {
    name.pop_back();
  }
  return name;
}

std::string stripPointer(std::string name) {
  return stripPointerSuffix(std::move(name));
}

std::string baseTypeName(const HIRType &type) {
  const std::size_t genericStart = type.name.find('<');
  std::string baseName = genericStart == std::string::npos
                             ? type.name
                             : type.name.substr(0, genericStart);
  return stripPointerSuffix(stripTypeQualifier(std::move(baseName)));
}

HIRType pointerlessType(HIRType type) {
  type.name = stripPointerSuffix(std::move(type.name));
  return type;
}

HIRType arrayElementType(HIRType type) {
  if (!type.arraySize.has_value()) {
    return type;
  }

  const std::size_t separator = type.arraySize->find("][");
  if (separator == std::string::npos) {
    type.arraySize.reset();
  } else {
    type.arraySize = type.arraySize->substr(separator + 2);
  }
  return type;
}

HIRType bufferElementType(HIRType type) {
  return pointerlessType(arrayElementType(std::move(type)));
}

bool isArrayType(const HIRType &type) { return type.arraySize.has_value(); }

bool isRuntimeArrayType(const HIRType &type) {
  return isArrayType(type) && type.arraySize->empty();
}

std::optional<HIRType> atomicPayloadType(const HIRType &type) {
  std::string name = stripPointerSuffix(stripTypeQualifier(type.name));
  constexpr std::string_view prefix = "atomic<";
  if (name.rfind(prefix, 0) != 0 || name.size() <= prefix.size() + 1 ||
      name.back() != '>') {
    return std::nullopt;
  }

  std::string payload =
      trim(std::string_view{name}.substr(prefix.size(),
                                         name.size() - prefix.size() - 1));
  if (payload.empty()) {
    return std::nullopt;
  }
  return HIRType{std::move(payload), std::nullopt, type.location};
}

bool isAtomicType(const HIRType &type) {
  return atomicPayloadType(type).has_value();
}

bool isAtomicIntegerType(const HIRType &type) {
  const std::optional<HIRType> payload = atomicPayloadType(type);
  return payload.has_value() && !payload->arraySize.has_value() &&
         (payload->name == "int" || payload->name == "uint");
}

bool isAtomicIntegerScalarType(const HIRType &type) {
  const std::string unqualified = stripTypeQualifier(type.name);
  return !type.arraySize.has_value() &&
         (unqualified.empty() || unqualified.back() != '*') &&
         isAtomicIntegerType(type);
}

bool isIntegerScalarTypeName(std::string_view name) {
  return name == "int" || name == "uint";
}

bool isIntegerScalarType(const HIRType &type) {
  const std::string unqualified = stripTypeQualifier(type.name);
  return !type.arraySize.has_value() &&
         (unqualified.empty() || unqualified.back() != '*') &&
         isIntegerScalarTypeName(unqualified);
}

bool isBuiltinType(std::string_view name) { return containsBuiltin(name); }

bool isKnownType(const HIRType &type,
                 const std::set<std::string> &structNames) {
  if (isAtomicType(type)) {
    return isAtomicIntegerType(type);
  }
  const std::string baseName = baseTypeName(type);
  return isBuiltinType(baseName) || structNames.contains(baseName);
}

bool isFloatTextureResourceType(std::string_view name) {
  return name == "sampler2D" || name == "texture2D" ||
         name == "sampler2DArray" || name == "texture2DArray" ||
         name == "sampler3D" || name == "texture3D" || name == "samplerCube" ||
         name == "textureCube" || name == "samplerCubeArray" ||
         name == "textureCubeArray";
}

bool isSignedIntegerTextureResourceType(std::string_view name) {
  return name == "isampler2D" || name == "isampler2DArray" ||
         name == "isampler3D" || name == "isamplerCube" ||
         name == "isamplerCubeArray";
}

bool isUnsignedIntegerTextureResourceType(std::string_view name) {
  return name == "usampler2D" || name == "usampler2DArray" ||
         name == "usampler3D" || name == "usamplerCube" ||
         name == "usamplerCubeArray";
}

bool isComparisonTextureResourceType(std::string_view name) {
  return name == "sampler2DShadow" || name == "sampler2DArrayShadow" ||
         name == "samplerCubeShadow" || name == "samplerCubeArrayShadow";
}

bool isFloatStorageImageResourceType(std::string_view name) {
  return name == "image2D" || name == "image2DArray";
}

bool isSignedIntegerStorageImageResourceType(std::string_view name) {
  return name == "iimage2D" || name == "iimage2DArray";
}

bool isUnsignedIntegerStorageImageResourceType(std::string_view name) {
  return name == "uimage2D" || name == "uimage2DArray";
}

bool isStorageImageResourceType(std::string_view name) {
  return isFloatStorageImageResourceType(name) ||
         isSignedIntegerStorageImageResourceType(name) ||
         isUnsignedIntegerStorageImageResourceType(name);
}

bool isStorageImageObjectType(const HIRType &type) {
  return !type.arraySize.has_value() &&
         isStorageImageResourceType(baseTypeName(type));
}

bool isStorageImageDescriptorArrayType(const HIRType &type) {
  return type.arraySize.has_value() &&
         isStorageImageResourceType(baseTypeName(type));
}

bool isTextureResourceType(std::string_view name) {
  return isFloatTextureResourceType(name) ||
         isSignedIntegerTextureResourceType(name) ||
         isUnsignedIntegerTextureResourceType(name) ||
         isComparisonTextureResourceType(name);
}

bool isRawSamplerResourceType(std::string_view name) {
  return name == "sampler";
}

bool isComparisonSamplerResourceType(std::string_view name) {
  return name == "comparison_sampler";
}

bool isSamplerResourceType(std::string_view name) {
  return isRawSamplerResourceType(name) ||
         isComparisonSamplerResourceType(name);
}

HIRResourceKind resourceKindFromName(std::string_view name) {
  const std::string base = resourceBaseType(name);
  if (isStorageImageResourceType(base)) {
    return HIRResourceKind::StorageImage;
  }
  if (isTextureResourceType(base)) {
    return HIRResourceKind::Texture;
  }
  if (isSamplerResourceType(base)) {
    return HIRResourceKind::Sampler;
  }
  if (name.rfind("uniform ", 0) == 0) {
    return HIRResourceKind::Uniform;
  }
  if (name.rfind("buffer ", 0) == 0) {
    return HIRResourceKind::Buffer;
  }
  if (name.rfind("shared ", 0) == 0) {
    return HIRResourceKind::Shared;
  }
  return HIRResourceKind::Value;
}

std::string storageImageFormatName(std::string_view name) {
  if (isFloatStorageImageResourceType(name)) {
    return "rgba32f";
  }
  if (isSignedIntegerStorageImageResourceType(name)) {
    return "rgba32i";
  }
  if (isUnsignedIntegerStorageImageResourceType(name)) {
    return "rgba32ui";
  }
  return {};
}

bool isSupportedStorageImageFormatName(std::string_view format) {
  return format == "rgba32f" || format == "rgba32i" ||
         format == "rgba32ui" || format == "r32f" || format == "r32i" ||
         format == "r32ui";
}

bool storageImageFormatCompatibleWithType(std::string_view format,
                                          std::string_view imageType) {
  if (!isSupportedStorageImageFormatName(format)) {
    return false;
  }
  if (isFloatStorageImageResourceType(imageType)) {
    return format == "rgba32f" || format == "r32f";
  }
  if (isSignedIntegerStorageImageResourceType(imageType)) {
    return format == "rgba32i" || format == "r32i";
  }
  if (isUnsignedIntegerStorageImageResourceType(imageType)) {
    return format == "rgba32ui" || format == "r32ui";
  }
  return false;
}

bool storageImageFormatSupportsAtomics(std::string_view format,
                                        std::string_view imageType) {
  if (isSignedIntegerStorageImageResourceType(imageType)) {
    return format == "r32i";
  }
  if (isUnsignedIntegerStorageImageResourceType(imageType)) {
    return format == "r32ui";
  }
  return false;
}

std::string storageImageDimensionName(std::string_view name) {
  if (name == "image2D" || name == "iimage2D" || name == "uimage2D") {
    return "2d";
  }
  if (name == "image2DArray" || name == "iimage2DArray" ||
      name == "uimage2DArray") {
    return "2d_array";
  }
  return {};
}

std::string storageImagePayloadVectorTypeName(std::string_view name) {
  if (isFloatStorageImageResourceType(name)) {
    return "vec4";
  }
  if (isSignedIntegerStorageImageResourceType(name)) {
    return "ivec4";
  }
  if (isUnsignedIntegerStorageImageResourceType(name)) {
    return "uvec4";
  }
  return {};
}

std::string storageImageAtomicPayloadTypeName(std::string_view name) {
  if (isSignedIntegerStorageImageResourceType(name)) {
    return "int";
  }
  if (isUnsignedIntegerStorageImageResourceType(name)) {
    return "uint";
  }
  return {};
}

std::string storageImageCoordinateTypeName(std::string_view name) {
  if (name == "image2D" || name == "iimage2D" || name == "uimage2D") {
    return "ivec2";
  }
  if (name == "image2DArray" || name == "iimage2DArray" ||
      name == "uimage2DArray") {
    return "ivec3";
  }
  return {};
}

HIRType storageImagePayloadVectorType(const HIRType &type) {
  const std::string name = storageImagePayloadVectorTypeName(baseTypeName(type));
  return HIRType{name, std::nullopt, type.location};
}

HIRType storageImageAtomicPayloadType(const HIRType &type) {
  const std::string name =
      storageImageAtomicPayloadTypeName(baseTypeName(type));
  return HIRType{name, std::nullopt, type.location};
}

HIRType storageImageCoordinateType(const HIRType &type) {
  const std::string name = storageImageCoordinateTypeName(baseTypeName(type));
  return HIRType{name, std::nullopt, type.location};
}

bool sameType(const HIRType &left, const HIRType &right) {
  return left.name == right.name && left.arraySize == right.arraySize;
}

bool isVoidType(const HIRType &type) {
  return type.name == "void" && !type.arraySize.has_value();
}

bool isScalarBoolType(const HIRType &type) {
  return type.name == "bool" && !type.arraySize.has_value();
}

bool isNumericScalarTypeName(std::string_view name) {
  return name == "int" || name == "uint" || name == "float" || name == "half" ||
         name == "double";
}

bool isFloatLike(std::string_view name) {
  return name == "float" || name == "half" || name == "double";
}

bool isVectorType(std::string_view name) {
  return name == "vec2" || name == "vec3" || name == "vec4" ||
         name == "ivec2" || name == "ivec3" || name == "ivec4" ||
         name == "uvec2" || name == "uvec3" || name == "uvec4" ||
         name == "bvec2" || name == "bvec3" || name == "bvec4";
}

bool isMatrixType(std::string_view name) {
  return name == "mat2" || name == "mat3" || name == "mat4" ||
         name == "mat2x2" || name == "mat3x3" || name == "mat4x4";
}

bool isScalarAggregateTypePair(const HIRType &left, const HIRType &right) {
  if (left.arraySize.has_value() || right.arraySize.has_value()) {
    return false;
  }
  const std::string leftBase = baseTypeName(left);
  const std::string rightBase = baseTypeName(right);
  return (isNumericScalarTypeName(leftBase) &&
          (isVectorType(rightBase) || isMatrixType(rightBase))) ||
         (isNumericScalarTypeName(rightBase) &&
          (isVectorType(leftBase) || isMatrixType(leftBase)));
}

bool shouldDiagnoseTypeMismatch(const HIRType &expected,
                                const HIRType &actual) {
  if (expected.name.empty() || actual.name.empty() ||
      sameType(expected, actual)) {
    return false;
  }
  if (isScalarAggregateTypePair(expected, actual)) {
    return false;
  }
  return true;
}

HIRType scalarTypeForVector(std::string_view vectorType) {
  if (!vectorType.empty() && vectorType.front() == 'i') {
    return HIRType{"int", std::nullopt};
  }
  if (!vectorType.empty() && vectorType.front() == 'u') {
    return HIRType{"uint", std::nullopt};
  }
  if (!vectorType.empty() && vectorType.front() == 'b') {
    return HIRType{"bool", std::nullopt};
  }
  return HIRType{"float", std::nullopt};
}

std::optional<std::size_t> vectorWidthFromName(std::string_view name) {
  if ((name.size() == 4 && name.rfind("vec", 0) == 0) ||
      (name.size() == 5 &&
       (name.rfind("ivec", 0) == 0 || name.rfind("uvec", 0) == 0 ||
        name.rfind("bvec", 0) == 0))) {
    const char width = name.back();
    if (width >= '2' && width <= '4') {
      return static_cast<std::size_t>(width - '0');
    }
  }
  return std::nullopt;
}

std::optional<std::size_t> matrixElementCountFromName(std::string_view name) {
  if (name == "mat2" || name == "mat2x2") {
    return std::size_t{4};
  }
  if (name == "mat3" || name == "mat3x3") {
    return std::size_t{9};
  }
  if (name == "mat4" || name == "mat4x4") {
    return std::size_t{16};
  }
  return std::nullopt;
}

} // namespace crossgl
