#pragma once

#include "crossgl/HIR/HIR.h"

#include <optional>
#include <string>
#include <vector>

namespace crossgl {

// Storage/address-space qualifier carried as a prefix in the legacy HIRType
// spelling ("buffer "/"uniform "/"shared ").
enum class TypeQualifier { None, Buffer, Uniform, Shared };

// Coarse structural classification of a CrossGL type. This is the seam the
// rest of the compiler will eventually switch on instead of re-parsing the
// HIRType name string.
enum class TypeKind {
  Void,
  Bool,
  Scalar,       // int, uint, float, half, double
  Vector,       // vecN, ivecN, uvecN, bvecN
  Matrix,       // matN, matNxM
  Sampler,      // sampler, comparison_sampler
  Texture,      // samplerNN / textureNN (sampled image)
  StorageImage, // imageNN / iimageNN / uimageNN
  Atomic,       // atomic<...>
  Struct,       // user-defined aggregate
  Unknown,
};

// Scalar element class for Scalar types, Vector components, and Atomic
// payloads. None when not applicable.
enum class ScalarClass { None, Bool, Int, UInt, Float, Half, Double };

// A structured, round-trip-faithful view of an HIRType.
//
// PR 1 of the structured-type-system migration (issue #31): `internType` is the
// single canonical decoder of the overloaded HIRType name/arraySize grammar, and
// `toLegacyHIRType` is its exact inverse. The exact base spelling and array
// tokens are preserved so re-serialization is byte-identical to the legacy
// representation; the structured fields (kind/scalar/widths/dims) are the new
// capability that later PRs will switch on. No production code consumes Type yet.
struct Type {
  TypeQualifier qualifier = TypeQualifier::None;
  unsigned pointerDepth = 0;
  TypeKind kind = TypeKind::Unknown;

  // Element class for Scalar values, Vector components, and Atomic payloads.
  ScalarClass scalar = ScalarClass::None;
  // Lane count for Vector types (2..4); 0 otherwise.
  unsigned vectorWidth = 0;
  // Shape for Matrix types (rows/cols); 0 otherwise.
  unsigned matrixRows = 0;
  unsigned matrixCols = 0;

  // Exact base spelling between the qualifier prefix and the pointer/array
  // suffixes, e.g. "vec4", "mat2", "atomic<int>", "sampler2D", "MyStruct".
  // Preserved verbatim so serialization round-trips exactly.
  std::string core;

  // Array dimensions as raw tokens split on "][", mirroring HIRType::arraySize.
  // nullopt means "not an array"; a single empty token ({""}) is a
  // runtime-sized array.
  std::optional<std::vector<std::string>> arrayDims;

  bool isArray() const { return arrayDims.has_value(); }
  bool isRuntimeArray() const {
    return arrayDims.has_value() && arrayDims->size() == 1 &&
           arrayDims->front().empty();
  }
  bool isPointer() const { return pointerDepth > 0; }
};

// Decode an HIRType into the structured Type. Single source of truth for the
// HIRType name/arraySize grammar (qualifier prefix, atomic<> generic, pointer
// suffix, "][" array dimensions).
Type internType(const HIRType &type);

// Re-serialize a structured Type back into the legacy HIRType. Exact inverse of
// internType: toLegacyHIRType(internType(t)) == t for every t.
HIRType toLegacyHIRType(const Type &type);

} // namespace crossgl
