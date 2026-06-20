#include "crossgl/HIR/Type.h"

#include "crossgl/HIR/TypeSemantics.h"

#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace crossgl {
namespace {

ScalarClass scalarClassForName(std::string_view name) {
  if (name == "bool") {
    return ScalarClass::Bool;
  }
  if (name == "int") {
    return ScalarClass::Int;
  }
  if (name == "uint") {
    return ScalarClass::UInt;
  }
  if (name == "float") {
    return ScalarClass::Float;
  }
  if (name == "half") {
    return ScalarClass::Half;
  }
  if (name == "double") {
    return ScalarClass::Double;
  }
  return ScalarClass::None;
}

std::vector<std::string> splitArrayDimensions(const std::string &arraySize) {
  std::vector<std::string> dimensions;
  std::size_t start = 0;
  while (true) {
    const std::size_t separator = arraySize.find("][", start);
    if (separator == std::string::npos) {
      dimensions.push_back(arraySize.substr(start));
      break;
    }
    dimensions.push_back(arraySize.substr(start, separator - start));
    start = separator + 2;
  }
  return dimensions;
}

std::string joinArrayDimensions(const std::vector<std::string> &dimensions) {
  std::string arraySize;
  for (std::size_t index = 0; index < dimensions.size(); ++index) {
    if (index != 0) {
      arraySize += "][";
    }
    arraySize += dimensions[index];
  }
  return arraySize;
}

unsigned squareMatrixOrder(const std::string &core) {
  if (core == "mat2" || core == "mat2x2") {
    return 2;
  }
  if (core == "mat3" || core == "mat3x3") {
    return 3;
  }
  if (core == "mat4" || core == "mat4x4") {
    return 4;
  }
  return 0;
}

void classifyCore(const std::string &core, Type &type) {
  if (core == "void") {
    type.kind = TypeKind::Void;
    return;
  }
  if (core == "bool") {
    type.kind = TypeKind::Bool;
    type.scalar = ScalarClass::Bool;
    return;
  }
  if (isNumericScalarTypeName(core)) {
    type.kind = TypeKind::Scalar;
    type.scalar = scalarClassForName(core);
    return;
  }
  if (isVectorType(core)) {
    type.kind = TypeKind::Vector;
    if (const auto width = vectorWidthFromName(core)) {
      type.vectorWidth = static_cast<unsigned>(*width);
    }
    type.scalar = scalarClassForName(scalarTypeForVector(core).name);
    return;
  }
  if (isMatrixType(core)) {
    type.kind = TypeKind::Matrix;
    type.scalar = ScalarClass::Float;
    type.matrixRows = squareMatrixOrder(core);
    type.matrixCols = type.matrixRows;
    return;
  }
  if (isSamplerResourceType(core)) {
    type.kind = TypeKind::Sampler;
    return;
  }
  if (isTextureResourceType(core)) {
    type.kind = TypeKind::Texture;
    return;
  }
  if (isStorageImageResourceType(core)) {
    type.kind = TypeKind::StorageImage;
    return;
  }
  if (core.rfind("atomic<", 0) == 0 && core.back() == '>') {
    type.kind = TypeKind::Atomic;
    if (const auto payload = atomicPayloadType(HIRType{core})) {
      type.scalar = scalarClassForName(payload->name);
    }
    return;
  }
  if (!core.empty()) {
    type.kind = TypeKind::Struct;
    return;
  }
  type.kind = TypeKind::Unknown;
}

} // namespace

Type internType(const HIRType &type) {
  Type result;
  std::string name = type.name;

  // Storage/address-space qualifier prefix.
  if (name.rfind("buffer ", 0) == 0) {
    result.qualifier = TypeQualifier::Buffer;
    name.erase(0, 7);
  } else if (name.rfind("uniform ", 0) == 0) {
    result.qualifier = TypeQualifier::Uniform;
    name.erase(0, 8);
  } else if (name.rfind("shared ", 0) == 0) {
    result.qualifier = TypeQualifier::Shared;
    name.erase(0, 7);
  }

  // Pointer suffix (repeatable).
  while (!name.empty() && name.back() == '*') {
    ++result.pointerDepth;
    name.pop_back();
  }

  result.core = std::move(name);

  if (type.arraySize.has_value()) {
    result.arrayDims = splitArrayDimensions(*type.arraySize);
  }

  classifyCore(result.core, result);
  return result;
}

HIRType toLegacyHIRType(const Type &type) {
  std::string name;
  switch (type.qualifier) {
  case TypeQualifier::Buffer:
    name = "buffer ";
    break;
  case TypeQualifier::Uniform:
    name = "uniform ";
    break;
  case TypeQualifier::Shared:
    name = "shared ";
    break;
  case TypeQualifier::None:
    break;
  }
  name += type.core;
  name.append(type.pointerDepth, '*');

  std::optional<std::string> arraySize;
  if (type.arrayDims.has_value()) {
    arraySize = joinArrayDimensions(*type.arrayDims);
  }

  return HIRType{std::move(name), std::move(arraySize)};
}

} // namespace crossgl
