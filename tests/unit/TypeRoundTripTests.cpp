// Differential round-trip + classification tests for the structured HIR type
// model (issue #31, PR 1). Verifies that internType()/toLegacyHIRType() preserve
// every legacy HIRType spelling exactly, and that core spellings classify into
// the right TypeKind/ScalarClass. No production code consumes Type yet, so this
// exe is the sole consumer and proves the foundation in isolation.

#include "crossgl/HIR/Type.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <iostream>
#include <optional>
#include <string>
#include <vector>

using namespace crossgl;

namespace {

int g_failures = 0;

void checkRoundTrip(const HIRType &original) {
  const Type structured = internType(original);
  const HIRType restored = toLegacyHIRType(structured);
  if (!sameType(restored, original)) {
    ++g_failures;
    std::cerr << "round-trip mismatch: name='" << original.name << "' arraySize="
              << (original.arraySize ? ("'" + *original.arraySize + "'")
                                     : std::string("<none>"))
              << " -> name='" << restored.name << "' arraySize="
              << (restored.arraySize ? ("'" + *restored.arraySize + "'")
                                     : std::string("<none>"))
              << "\n";
  }
}

void expect(bool condition, const std::string &what) {
  if (!condition) {
    ++g_failures;
    std::cerr << "classification check failed: " << what << "\n";
  }
}

} // namespace

int main() {
  const std::vector<std::string> builtins = {
      "void",          "bool",
      "int",           "uint",
      "float",         "double",
      "half",          "vec2",
      "vec3",          "vec4",
      "ivec2",         "ivec3",
      "ivec4",         "uvec2",
      "uvec3",         "uvec4",
      "bvec2",         "bvec3",
      "bvec4",         "mat2",
      "mat3",          "mat4",
      "mat2x2",        "mat3x3",
      "mat4x4",        "sampler",
      "comparison_sampler", "sampler2D",
      "sampler2DArray", "sampler3D",
      "samplerCube",   "samplerCubeArray",
      "sampler2DShadow", "sampler2DArrayShadow",
      "samplerCubeShadow", "samplerCubeArrayShadow",
      "isampler2D",    "isampler2DArray",
      "isampler3D",    "isamplerCube",
      "isamplerCubeArray", "usampler2D",
      "usampler2DArray", "usampler3D",
      "usamplerCube",  "usamplerCubeArray",
      "texture2D",     "texture2DArray",
      "texture3D",     "textureCube",
      "textureCubeArray", "image2D",
      "iimage2D",      "uimage2D",
      "image2DArray",  "iimage2DArray",
      "uimage2DArray",
  };

  std::vector<std::string> cores = builtins;
  cores.push_back("atomic<int>");
  cores.push_back("atomic<uint>");
  cores.push_back("MyStruct");
  cores.push_back("Material");

  const std::vector<std::string> qualifiers = {"", "buffer ", "uniform ",
                                               "shared "};
  const std::vector<unsigned> pointerDepths = {0, 1, 2};
  const std::vector<std::optional<std::string>> arrays = {
      std::nullopt, std::optional<std::string>(""),
      std::optional<std::string>("4"), std::optional<std::string>("4][8")};

  for (const std::string &qualifier : qualifiers) {
    for (const std::string &core : cores) {
      for (unsigned pointerDepth : pointerDepths) {
        for (const std::optional<std::string> &arraySize : arrays) {
          std::string name = qualifier + core + std::string(pointerDepth, '*');
          checkRoundTrip(HIRType{std::move(name), arraySize});
        }
      }
    }
  }

  // Structural classification spot-checks.
  expect(internType(HIRType{"void"}).kind == TypeKind::Void, "void -> Void");
  expect(internType(HIRType{"bool"}).kind == TypeKind::Bool, "bool -> Bool");
  {
    const Type t = internType(HIRType{"float"});
    expect(t.kind == TypeKind::Scalar && t.scalar == ScalarClass::Float,
           "float -> Scalar/Float");
  }
  {
    const Type t = internType(HIRType{"vec4"});
    expect(t.kind == TypeKind::Vector && t.vectorWidth == 4 &&
               t.scalar == ScalarClass::Float,
           "vec4 -> Vector(4)/Float");
  }
  {
    const Type t = internType(HIRType{"ivec3"});
    expect(t.kind == TypeKind::Vector && t.vectorWidth == 3 &&
               t.scalar == ScalarClass::Int,
           "ivec3 -> Vector(3)/Int");
  }
  {
    const Type t = internType(HIRType{"uvec2"});
    expect(t.kind == TypeKind::Vector && t.vectorWidth == 2 &&
               t.scalar == ScalarClass::UInt,
           "uvec2 -> Vector(2)/UInt");
  }
  {
    const Type t = internType(HIRType{"mat3"});
    expect(t.kind == TypeKind::Matrix && t.matrixRows == 3 &&
               t.matrixCols == 3,
           "mat3 -> Matrix(3x3)");
  }
  {
    const Type t = internType(HIRType{"mat4x4"});
    expect(t.kind == TypeKind::Matrix && t.matrixRows == 4, "mat4x4 -> Matrix");
  }
  expect(internType(HIRType{"sampler2D"}).kind == TypeKind::Texture,
         "sampler2D -> Texture");
  expect(internType(HIRType{"sampler"}).kind == TypeKind::Sampler,
         "sampler -> Sampler");
  expect(internType(HIRType{"image2D"}).kind == TypeKind::StorageImage,
         "image2D -> StorageImage");
  {
    const Type t = internType(HIRType{"atomic<uint>"});
    expect(t.kind == TypeKind::Atomic && t.scalar == ScalarClass::UInt,
           "atomic<uint> -> Atomic/UInt");
  }
  {
    const Type t = internType(HIRType{"buffer float*"});
    expect(t.qualifier == TypeQualifier::Buffer && t.pointerDepth == 1 &&
               t.kind == TypeKind::Scalar,
           "buffer float* -> Buffer/ptr1/Scalar");
  }
  expect(internType(HIRType{"MyStruct"}).kind == TypeKind::Struct,
         "MyStruct -> Struct");
  {
    const Type t = internType(HIRType{"float", std::optional<std::string>("4][8")});
    expect(t.isArray() && t.arrayDims->size() == 2, "float[4][8] -> 2 dims");
  }
  {
    const Type t = internType(HIRType{"float", std::optional<std::string>("")});
    expect(t.isRuntimeArray(), "float[] -> runtime array");
  }

  if (g_failures == 0) {
    std::cout << "all HIR type round-trip and classification checks passed\n";
    return 0;
  }
  std::cerr << g_failures << " HIR type check(s) failed\n";
  return 1;
}
