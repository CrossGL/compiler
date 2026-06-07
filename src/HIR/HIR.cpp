#include "crossgl/HIR/HIR.h"
#include "crossgl/Frontend/Lexer.h"
#include "crossgl/HIR/BuiltinEffects.h"
#include "crossgl/HIR/ConstantFolding.h"
#include "crossgl/HIR/Intrinsics.h"
#include "crossgl/HIR/SideEffects.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <limits>
#include <set>
#include <sstream>
#include <string_view>
#include <unordered_map>

namespace crossgl {
namespace {

HIRType makeType(std::string name) { return HIRType{std::move(name), std::nullopt}; }

SourceLocation sourceSpan(SourceLocation begin, const SourceLocation &end) {
  begin.endLine = end.endLine;
  begin.endColumn = end.endColumn;
  begin.endOffset = end.endOffset;
  begin.length = begin.endOffset >= begin.offset ? begin.endOffset - begin.offset
                                                 : begin.length;
  return begin;
}

SourceLocation tokenSpan(const std::vector<Token> &tokens) {
  return tokens.empty() ? SourceLocation{}
                        : sourceSpan(tokens.front().location,
                                     tokens.back().location);
}

bool isNameToken(TokenKind kind) {
  return kind == TokenKind::Identifier || kind == TokenKind::KeywordInput ||
         kind == TokenKind::KeywordOutput;
}

bool isVarToken(const Token &token) {
  return token.kind == TokenKind::KeywordVar ||
         (token.kind == TokenKind::Identifier && token.text == "var");
}

bool isWorkgroupBarrierCallName(std::string_view name) {
  return name == "workgroupBarrier" || name == "barrier";
}

HIRExpression makeBoolLiteral(std::string value, SourceLocation location) {
  HIRExpression literal;
  literal.kind = HIRExpressionKind::Literal;
  literal.value = std::move(value);
  literal.location = std::move(location);
  literal.type = makeType("bool");
  return literal;
}

HIRType convertType(const TypeRef &type) {
  return HIRType{type.name, type.arraySize, type.location};
}

void addComputeInvocationBuiltinTypes(
    std::unordered_map<std::string, HIRType> &variables,
    std::string_view stage) {
  if (stage != "compute") {
    return;
  }
  variables.emplace("gl_GlobalInvocationID", makeType("uvec3"));
  variables.emplace("gl_LocalInvocationID", makeType("uvec3"));
  variables.emplace("gl_WorkGroupID", makeType("uvec3"));
}

HIRType typeFromTokens(const std::vector<Token> &tokens, std::size_t begin,
                       std::size_t end) {
  HIRType type;
  if (begin < end) {
    type.location = sourceSpan(tokens[begin].location, tokens[end - 1].location);
  }
  for (std::size_t i = begin; i < end; ++i) {
    const Token &token = tokens[i];
    if ((token.kind == TokenKind::KeywordUniform ||
         token.kind == TokenKind::KeywordBuffer ||
         token.kind == TokenKind::KeywordShared) &&
        i + 1 < end) {
      type.name += token.text;
      type.name += ' ';
      continue;
    }
    type.name += token.text;
  }
  return type;
}

void appendArrayDimension(HIRType &type, std::string dimension) {
  if (!type.arraySize.has_value()) {
    type.arraySize = std::move(dimension);
    return;
  }
  *type.arraySize += "][";
  *type.arraySize += dimension;
}

std::optional<std::vector<std::size_t>>
swizzleComponentIndices(const HIRType &base, std::string_view member) {
  const std::string baseName = baseTypeName(base);
  const std::optional<std::size_t> width = vectorWidthFromName(baseName);
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

HIRType swizzleType(const HIRType &base, std::string_view member) {
  const std::string baseName = baseTypeName(base);
  const std::optional<std::vector<std::size_t>> indices =
      swizzleComponentIndices(base, member);
  if (!isVectorType(baseName) || !indices.has_value()) {
    return {};
  }
  if (indices->size() == 1) {
    return scalarTypeForVector(baseName);
  }
  if (indices->size() >= 2 && indices->size() <= 4) {
    if (baseName.rfind("ivec", 0) == 0) {
      return makeType("ivec" + std::to_string(indices->size()));
    }
    if (baseName.rfind("uvec", 0) == 0) {
      return makeType("uvec" + std::to_string(indices->size()));
    }
    if (baseName.rfind("bvec", 0) == 0) {
      return makeType("bvec" + std::to_string(indices->size()));
    }
    return makeType("vec" + std::to_string(indices->size()));
  }
  return {};
}

HIRType inferSelectType(const HIRType &thenType, const HIRType &elseType) {
  if (thenType.name == elseType.name && thenType.arraySize == elseType.arraySize) {
    return thenType;
  }
  return thenType.name.empty() ? elseType : thenType;
}

bool isTextureType(const HIRType &type) {
  return isTextureResourceType(baseTypeName(type));
}

bool isStorageImageType(const HIRType &type) {
  return isStorageImageObjectType(type);
}

bool isSamplerType(const HIRType &type) {
  return isSamplerResourceType(baseTypeName(type));
}

bool isRawSamplerType(const HIRType &type) {
  return isRawSamplerResourceType(baseTypeName(type));
}

bool isShadowTextureType(const HIRType &type) {
  return isComparisonTextureResourceType(baseTypeName(type));
}

HIRType textureSampleResultType(const HIRType &textureType) {
  const std::string name = baseTypeName(textureType);
  if (!isTextureResourceType(name)) {
    return {};
  }
  if (isShadowTextureType(textureType)) {
    return makeType("float");
  }
  if (name.rfind("isampler", 0) == 0) {
    return makeType("ivec4");
  }
  if (name.rfind("usampler", 0) == 0) {
    return makeType("uvec4");
  }
  return makeType("vec4");
}

bool isImageLoadCallName(std::string_view name) { return name == "imageLoad"; }

bool isImageStoreCallName(std::string_view name) {
  return name == "imageStore";
}

bool isImageAtomicCallName(std::string_view name) {
  return name == "imageAtomicAdd" || name == "imageAtomicExchange" ||
         name == "imageAtomicMin" || name == "imageAtomicMax" ||
         name == "imageAtomicAnd" || name == "imageAtomicOr" ||
         name == "imageAtomicXor";
}

bool isImageAccessCallName(std::string_view name) {
  return isImageLoadCallName(name) || isImageStoreCallName(name) ||
         isImageAtomicCallName(name);
}

HIRType imageLoadResultType(const HIRType &imageType,
                            SourceLocation location = {}) {
  HIRType result = storageImagePayloadVectorType(imageType);
  result.location = std::move(location);
  return result;
}

HIRType imageAtomicResultType(const HIRType &imageType,
                              SourceLocation location = {}) {
  HIRType result = storageImageAtomicPayloadType(imageType);
  result.location = std::move(location);
  return result;
}

HIRType inferImageAccessCallType(std::string_view name,
                                 const std::vector<HIRExpression> &arguments,
                                 SourceLocation location) {
  if (isImageStoreCallName(name)) {
    return HIRType{"void", std::nullopt, std::move(location)};
  }
  if (isImageLoadCallName(name) && arguments.size() == 2 &&
      isStorageImageType(arguments.front().type)) {
    return imageLoadResultType(arguments.front().type, std::move(location));
  }
  if (isImageAtomicCallName(name) && arguments.size() == 3 &&
      isStorageImageType(arguments.front().type)) {
    return imageAtomicResultType(arguments.front().type, std::move(location));
  }
  return {};
}

bool isReadModifyWriteOldValueCallName(std::string_view name) {
  return isHIRAtomicIntegerReadModifyWriteIntrinsic(name) ||
         isImageAtomicCallName(name);
}

std::string readModifyWriteOldValueDiagnosticStem(std::string_view name) {
  if (isImageAtomicCallName(name)) {
    if (name == "imageAtomicAdd") {
      return "image-atomic-add";
    }
    if (name == "imageAtomicExchange") {
      return "image-atomic-exchange";
    }
    if (name == "imageAtomicMin") {
      return "image-atomic-min";
    }
    if (name == "imageAtomicMax") {
      return "image-atomic-max";
    }
    if (name == "imageAtomicAnd") {
      return "image-atomic-and";
    }
    if (name == "imageAtomicOr") {
      return "image-atomic-or";
    }
    if (name == "imageAtomicXor") {
      return "image-atomic-xor";
    }
  }
  return std::string(hirAtomicIntegerReadModifyWriteDiagnosticStem(name));
}

std::string readModifyWriteOldValueTerm(std::string_view name) {
  if (isImageAtomicCallName(name)) {
    return "value";
  }
  return std::string(hirAtomicIntegerReadModifyWriteValueTerm(name));
}

bool isReadModifyWriteOldValueCall(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::Call &&
         isReadModifyWriteOldValueCallName(expression.value);
}

bool isStorageImageAtomicImageType(const HIRType &type) {
  const std::string name = baseTypeName(type);
  return isSignedIntegerStorageImageResourceType(name) ||
         isUnsignedIntegerStorageImageResourceType(name);
}

std::string storageImageAtomicExpectedFormatName(const HIRType &type) {
  const std::string name = baseTypeName(type);
  if (isSignedIntegerStorageImageResourceType(name)) {
    return "r32i";
  }
  if (isUnsignedIntegerStorageImageResourceType(name)) {
    return "r32ui";
  }
  return {};
}

bool isExplicitLodTextureSample(std::string_view sampleName) {
  return sampleName == "textureLod";
}

bool textureSampleHasExplicitSampler(std::size_t argumentCount, bool explicitLod) {
  return explicitLod ? argumentCount == 4 : argumentCount == 3;
}

std::size_t textureSampleCoordinateIndex(std::size_t argumentCount,
                                         bool explicitLod) {
  return textureSampleHasExplicitSampler(argumentCount, explicitLod) ? 2 : 1;
}

std::optional<std::size_t> textureSampleLodIndex(std::size_t argumentCount,
                                                 bool explicitLod) {
  if (!explicitLod) {
    return std::nullopt;
  }
  return textureSampleHasExplicitSampler(argumentCount, explicitLod) ? 3 : 2;
}

bool isScalarNumericType(const HIRType &type) {
  return !type.arraySize.has_value() &&
         (isFloatLike(baseTypeName(type)) || baseTypeName(type) == "int" ||
          baseTypeName(type) == "uint");
}

bool isFloatScalarType(const HIRType &type) {
  return !type.arraySize.has_value() && baseTypeName(type) == "float";
}

bool isScalarNumericConstructorType(const HIRType &type) {
  const std::string name = baseTypeName(type);
  return !type.arraySize.has_value() &&
         (name == "float" || name == "int" || name == "uint");
}

bool isSignedUnsignedScalarPair(const HIRType &left, const HIRType &right) {
  const std::string leftName = baseTypeName(left);
  const std::string rightName = baseTypeName(right);
  return !left.arraySize.has_value() && !right.arraySize.has_value() &&
         ((leftName == "int" && rightName == "uint") ||
          (leftName == "uint" && rightName == "int"));
}

bool isComputeInvocationBuiltinName(std::string_view name) {
  return name == "gl_GlobalInvocationID" || name == "gl_LocalInvocationID" ||
         name == "gl_WorkGroupID";
}

bool isComputeInvocationBuiltinComponentAccess(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::MemberAccess &&
         expression.type.name == "uint" && expression.children.size() == 1 &&
         expression.children.front().kind == HIRExpressionKind::Identifier &&
         isComputeInvocationBuiltinName(expression.children.front().value);
}

bool isComputeInvocationBuiltinIntConversion(const HIRExpression &expression,
                                             const HIRType &sourceType) {
  return baseTypeName(expression.type) == "int" &&
         baseTypeName(sourceType) == "uint" && expression.children.size() == 1 &&
         isComputeInvocationBuiltinComponentAccess(expression.children.front());
}

bool isFloatVectorType(const HIRType &type) {
  const std::string name = baseTypeName(type);
  return !type.arraySize.has_value() &&
         (name == "vec2" || name == "vec3" || name == "vec4");
}

bool isArithmeticBinaryOperator(std::string_view op) {
  return op == "+" || op == "-" || op == "*" || op == "/";
}

HIRType inferTextureSampleType(const std::vector<HIRExpression> &arguments,
                               bool explicitLod) {
  if (arguments.empty() || !isTextureType(arguments.front().type)) {
    return {};
  }
  if (explicitLod) {
    if (arguments.size() != 3 && arguments.size() != 4) {
      return {};
    }
  } else if (arguments.size() != 2 && arguments.size() != 3) {
    return {};
  }
  const bool hasExplicitSampler =
      textureSampleHasExplicitSampler(arguments.size(), explicitLod);
  if (hasExplicitSampler && !arguments[1].type.name.empty() &&
      !isRawSamplerType(arguments[1].type)) {
    return {};
  }
  const std::optional<std::size_t> lodIndex =
      textureSampleLodIndex(arguments.size(), explicitLod);
  if (lodIndex.has_value() && !arguments[*lodIndex].type.name.empty() &&
      !isScalarNumericType(arguments[*lodIndex].type)) {
    return {};
  }
  return textureSampleResultType(arguments.front().type);
}

bool isExplicitLodTextureCompare(std::string_view sampleName) {
  return sampleName == "textureCompareLod";
}

bool isManualLodTextureCompare(std::string_view sampleName) {
  return sampleName == "textureCompareLodManual" ||
         sampleName == "textureCompareLodManualOffset" ||
         sampleName == "textureCompareLodManualGather2x2" ||
         sampleName == "textureCompareLodManualKernel" ||
         sampleName == "textureCompareLodManualKernel4" ||
         sampleName == "textureCompareLodManualKernel8";
}

bool isManualOffsetLodTextureCompare(std::string_view sampleName) {
  return sampleName == "textureCompareLodManualOffset";
}

bool isManualGather2x2LodTextureCompare(std::string_view sampleName) {
  return sampleName == "textureCompareLodManualGather2x2";
}

bool isManualKernelListLodTextureCompare(std::string_view sampleName) {
  return sampleName == "textureCompareLodManualKernel";
}

bool isManualKernel4LodTextureCompare(std::string_view sampleName) {
  return sampleName == "textureCompareLodManualKernel4";
}

bool isManualKernel8LodTextureCompare(std::string_view sampleName) {
  return sampleName == "textureCompareLodManualKernel8";
}

std::optional<std::size_t>
manualKernelTextureCompareTapCount(std::string_view sampleName) {
  if (isManualKernel4LodTextureCompare(sampleName)) {
    return 4;
  }
  if (isManualKernel8LodTextureCompare(sampleName)) {
    return 8;
  }
  return std::nullopt;
}

bool isTextureCompareOperation(std::string_view sampleName) {
  return sampleName == "textureCompare" ||
         isExplicitLodTextureCompare(sampleName) ||
         isManualLodTextureCompare(sampleName);
}

std::size_t expectedTextureCompareArgumentCount(std::string_view sampleName) {
  if (isManualOffsetLodTextureCompare(sampleName)) {
    return 7;
  }
  if (const std::optional<std::size_t> tapCount =
          manualKernelTextureCompareTapCount(sampleName)) {
    return 6 + *tapCount * 2;
  }
  if (isManualKernelListLodTextureCompare(sampleName)) {
    return 7;
  }
  if (isManualLodTextureCompare(sampleName)) {
    return 6;
  }
  return isExplicitLodTextureCompare(sampleName) ? 5 : 4;
}

std::optional<std::size_t>
textureCompareLodIndex(std::size_t argumentCount, std::string_view sampleName) {
  if (!isExplicitLodTextureCompare(sampleName) &&
      !isManualLodTextureCompare(sampleName)) {
    return std::nullopt;
  }
  const std::size_t expectedArguments =
      expectedTextureCompareArgumentCount(sampleName);
  return argumentCount == expectedArguments ? std::optional<std::size_t>{4}
                                            : std::nullopt;
}

std::optional<std::size_t>
textureCompareManualCompareOpIndex(std::size_t argumentCount,
                                   std::string_view sampleName) {
  if (!isManualLodTextureCompare(sampleName) ||
      argumentCount != expectedTextureCompareArgumentCount(sampleName)) {
    return std::nullopt;
  }
  return 5;
}

std::optional<std::size_t>
textureCompareManualOffsetIndex(std::size_t argumentCount,
                                std::string_view sampleName) {
  if (!isManualOffsetLodTextureCompare(sampleName) ||
      argumentCount != expectedTextureCompareArgumentCount(sampleName)) {
    return std::nullopt;
  }
  return 6;
}

std::string textureCompareFunctionName(std::string_view sampleName) {
  return std::string(sampleName.empty() ? "textureCompare" : sampleName);
}

bool isManualCompareOffsetTextureType(const HIRType &textureType) {
  const std::string name = baseTypeName(textureType);
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

bool isStaticIntegerOffsetComponent(const HIRExpression &expression) {
  if (expression.kind == HIRExpressionKind::Group &&
      !expression.children.empty()) {
    return isStaticIntegerOffsetComponent(expression.children.front());
  }
  if (expression.kind == HIRExpressionKind::Unary &&
      (expression.value == "-" || expression.value == "+") &&
      expression.children.size() == 1) {
    return isStaticIntegerOffsetComponent(expression.children.front());
  }
  return expression.kind == HIRExpressionKind::Literal &&
         baseTypeName(expression.type) == "int" &&
         !expression.type.arraySize.has_value() &&
         isIntegerLiteralText(expression.value);
}

bool isStaticIvec2OffsetExpression(const HIRExpression &expression) {
  if (baseTypeName(expression.type) != "ivec2" ||
      expression.type.arraySize.has_value()) {
    return false;
  }
  if (expression.kind == HIRExpressionKind::Group &&
      !expression.children.empty()) {
    return isStaticIvec2OffsetExpression(expression.children.front());
  }
  if (expression.kind != HIRExpressionKind::Constructor ||
      expression.value != "ivec2" || expression.children.size() != 2) {
    return false;
  }
  return isStaticIntegerOffsetComponent(expression.children[0]) &&
         isStaticIntegerOffsetComponent(expression.children[1]);
}

bool isManualTextureCompareOpName(std::string_view name) {
  return name == "never" || name == "always" || name == "less" ||
         name == "less_equal" || name == "equal" || name == "not_equal" ||
         name == "greater_equal" || name == "greater";
}

std::string manualTextureCompareOpList() {
  return "never, always, less, less_equal, equal, not_equal, "
         "greater_equal, or greater";
}

HIRType inferTextureCompareType(const std::vector<HIRExpression> &arguments,
                                std::string_view sampleName) {
  const std::size_t expectedArguments =
      expectedTextureCompareArgumentCount(sampleName);
  if (arguments.empty() || arguments.size() != expectedArguments ||
      !isShadowTextureType(arguments.front().type)) {
    return {};
  }
  if (!arguments[1].type.name.empty()) {
    const bool validSampler = isManualLodTextureCompare(sampleName)
                                  ? isRawSamplerType(arguments[1].type)
                                  : isSamplerType(arguments[1].type);
    if (!validSampler) {
      return {};
    }
  }
  if (!arguments[3].type.name.empty() &&
      !isScalarNumericType(arguments[3].type)) {
    return {};
  }
  const std::optional<std::size_t> lodIndex =
      textureCompareLodIndex(arguments.size(), sampleName);
  if (lodIndex.has_value() && !arguments[*lodIndex].type.name.empty() &&
      !isScalarNumericType(arguments[*lodIndex].type)) {
    return {};
  }
  const std::optional<std::size_t> compareOpIndex =
      textureCompareManualCompareOpIndex(arguments.size(), sampleName);
  if (compareOpIndex.has_value() &&
      (arguments[*compareOpIndex].kind != HIRExpressionKind::Identifier ||
       !arguments[*compareOpIndex].type.name.empty() ||
       arguments[*compareOpIndex].type.arraySize.has_value() ||
       !isManualTextureCompareOpName(arguments[*compareOpIndex].value))) {
    return {};
  }
  const std::optional<std::size_t> offsetIndex =
      textureCompareManualOffsetIndex(arguments.size(), sampleName);
  if (offsetIndex.has_value()) {
    if (!isManualCompareOffsetTextureType(arguments.front().type) ||
        !isStaticIvec2OffsetExpression(arguments[*offsetIndex])) {
      return {};
    }
  }
  if (isManualGather2x2LodTextureCompare(sampleName) &&
      !isManualCompareOffsetTextureType(arguments.front().type)) {
    return {};
  }
  if (manualKernelTextureCompareTapCount(sampleName).has_value() ||
      isManualKernelListLodTextureCompare(sampleName)) {
    if (!isManualCompareOffsetTextureType(arguments.front().type)) {
      return {};
    }
    HIRExpression kernelExpression;
    kernelExpression.kind = HIRExpressionKind::TextureCompareLodManual;
    kernelExpression.value = std::string(sampleName);
    kernelExpression.children = arguments;
    const std::optional<std::vector<ManualTextureCompareKernelTap>> taps =
        manualTextureCompareKernelTaps(kernelExpression);
    if (!taps.has_value()) {
      return {};
    }
    for (const ManualTextureCompareKernelTap &tap : *taps) {
      const HIRExpression &offset = *tap.offset;
      const HIRExpression &weight = *tap.weight;
      if (!isStaticIvec2OffsetExpression(offset) ||
          (!weight.type.name.empty() && !isScalarNumericType(weight.type))) {
        return {};
      }
    }
  }
  return makeType("float");
}

std::size_t expectedTextureCoordinateComponents(const HIRType &textureType) {
  const std::string name = baseTypeName(textureType);
  if (name == "sampler2D" || name == "sampler2DShadow" ||
      name == "isampler2D" || name == "usampler2D" || name == "texture2D") {
    return 2;
  }
  if (name == "sampler2DArray" || name == "sampler2DArrayShadow" ||
      name == "isampler2DArray" || name == "usampler2DArray" ||
      name == "texture2DArray") {
    return 3;
  }
  if (name == "sampler3D" || name == "isampler3D" ||
      name == "usampler3D" || name == "texture3D" ||
      name == "samplerCube" || name == "samplerCubeShadow" ||
      name == "isamplerCube" || name == "usamplerCube" ||
      name == "textureCube") {
    return 3;
  }
  if (name == "samplerCubeArray" || name == "samplerCubeArrayShadow" ||
      name == "isamplerCubeArray" || name == "usamplerCubeArray" ||
      name == "textureCubeArray") {
    return 4;
  }
  return 0;
}

std::optional<std::size_t> vectorComponentCount(const HIRType &type) {
  const std::string name = baseTypeName(type);
  if (name.size() == 4 && name.rfind("vec", 0) == 0 && name[3] >= '0' &&
      name[3] <= '9') {
    return static_cast<std::size_t>(name[3] - '0');
  }
  if (name.size() == 5 &&
      (name.rfind("ivec", 0) == 0 || name.rfind("uvec", 0) == 0 ||
       name.rfind("bvec", 0) == 0) &&
      name[4] >= '0' && name[4] <= '9') {
    return static_cast<std::size_t>(name[4] - '0');
  }
  return std::nullopt;
}

class ExpressionParser {
public:
  ExpressionParser(std::vector<Token> tokens,
                   const std::set<std::string> &knownTypeNames,
                   const std::unordered_map<std::string, HIRStruct> &structs,
                   const std::unordered_map<std::string, HIRType> &variables,
                   DiagnosticEngine *diagnostics = nullptr)
      : tokens_(std::move(tokens)), knownTypeNames_(knownTypeNames),
        structs_(structs), variables_(variables), diagnostics_(diagnostics) {}

  HIRExpression parse() {
    HIRExpression expression = parseConditional();
    if (failed_) {
      return {};
    }
    if (!atEnd()) {
      fail("unexpected trailing token '" + current().text + "' in expression",
           current().location);
      return {};
    }
    return expression;
  }
  bool consumedAll() const { return atEnd(); }

private:
  bool atEnd() const { return index_ >= tokens_.size(); }

  const Token &current() const { return tokens_[index_]; }

  const Token &previous() const { return tokens_[index_ - 1]; }

  bool check(TokenKind kind) const { return !atEnd() && current().kind == kind; }

  bool match(TokenKind kind) {
    if (!check(kind)) {
      return false;
    }
    ++index_;
    return true;
  }

  bool matchOperator(std::string_view op) {
    if (!check(TokenKind::Operator) || current().text != op) {
      return false;
    }
    ++index_;
    return true;
  }

  static bool isHexDigit(char character) {
    return (character >= '0' && character <= '9') ||
           (character >= 'a' && character <= 'f') ||
           (character >= 'A' && character <= 'F');
  }

  static bool isSplitHexLiteralSuffix(std::string_view text) {
    if (text.size() < 2 || (text.front() != 'x' && text.front() != 'X')) {
      return false;
    }

    const bool hasUnsignedSuffix = text.back() == 'u' || text.back() == 'U';
    const std::size_t hexEnd = hasUnsignedSuffix ? text.size() - 1 : text.size();
    if (hexEnd <= 1) {
      return false;
    }

    for (std::size_t index = 1; index < hexEnd; ++index) {
      if (!isHexDigit(text[index])) {
        return false;
      }
    }
    return true;
  }

  static bool hasUnsignedIntegerSuffix(std::string_view text) {
    return !text.empty() && (text.back() == 'u' || text.back() == 'U');
  }

  static bool isFloatLiteralText(std::string_view text) {
    return text.find('.') != std::string_view::npos ||
           text.find('e') != std::string_view::npos ||
           text.find('E') != std::string_view::npos ||
           text.find('p') != std::string_view::npos ||
           text.find('P') != std::string_view::npos ||
           (!text.empty() && (text.back() == 'f' || text.back() == 'F'));
  }

  void fail(std::string message, SourceLocation location = {}) {
    if (!failed_ && diagnostics_ != nullptr) {
      diagnostics_->error("sema.expression-parse", std::move(message),
                          std::move(location));
    }
    failed_ = true;
  }

  static int precedence(const Token &token) {
    if (token.kind != TokenKind::Operator) {
      return -1;
    }
    if (token.text == "||") {
      return 1;
    }
    if (token.text == "&&") {
      return 2;
    }
    if (token.text == "==" || token.text == "!=") {
      return 3;
    }
    if (token.text == "<" || token.text == "<=" || token.text == ">" ||
        token.text == ">=") {
      return 4;
    }
    if (token.text == "+" || token.text == "-") {
      return 5;
    }
    if (token.text == "*" || token.text == "/" || token.text == "%") {
      return 6;
    }
    return -1;
  }

  HIRExpression parseConditional() {
    HIRExpression condition = parseBinary(0);
    if (failed_) {
      return {};
    }
    if (!check(TokenKind::Operator) || current().text != "?") {
      return condition;
    }
    const SourceLocation questionLocation = current().location;
    ++index_;

    HIRExpression trueValue = parseConditional();
    if (!match(TokenKind::Colon)) {
      fail("expected ':' in conditional expression", questionLocation);
      return {};
    }

    HIRExpression falseValue = parseConditional();
    HIRExpression select;
    select.kind = HIRExpressionKind::Select;
    select.location = questionLocation;
    select.children.push_back(std::move(condition));
    select.children.push_back(std::move(trueValue));
    select.children.push_back(std::move(falseValue));
    select.type = inferSelectType(select.children[1].type, select.children[2].type);
    return select;
  }

  HIRExpression parseBinary(int minPrecedence) {
    HIRExpression left = parseUnary();
    if (failed_) {
      return {};
    }
    while (!atEnd()) {
      const int opPrecedence = precedence(current());
      if (opPrecedence < minPrecedence) {
        break;
      }
      const std::string op = current().text;
      const SourceLocation opLocation = current().location;
      ++index_;
      HIRExpression right = parseBinary(opPrecedence + 1);
      if (failed_) {
        return {};
      }
      HIRExpression binary;
      binary.kind = HIRExpressionKind::Binary;
      binary.value = op;
      binary.location = opLocation;
      binary.children.push_back(std::move(left));
      binary.children.push_back(std::move(right));
      binary.type = inferBinaryType(binary.children[0].type, binary.children[1].type, op);
      left = std::move(binary);
    }
    return left;
  }

  HIRExpression parseUnary() {
    if (check(TokenKind::Operator) &&
        (current().text == "-" || current().text == "!" || current().text == "+")) {
      const std::string op = current().text;
      const SourceLocation opLocation = current().location;
      ++index_;
      HIRExpression unary;
      unary.kind = HIRExpressionKind::Unary;
      unary.value = op;
      unary.location = opLocation;
      unary.children.push_back(parseUnary());
      if (failed_) {
        return {};
      }
      unary.type = op == "!" ? makeType("bool") : unary.children.front().type;
      return unary;
    }
    return parsePostfix(parsePrimary());
  }

  HIRExpression parsePrimary() {
    if (match(TokenKind::Number)) {
      HIRExpression literal;
      literal.kind = HIRExpressionKind::Literal;
      literal.value = previous().text;
      literal.location = previous().location;
      const bool isIntegerLiteral = !isFloatLiteralText(literal.value);
      if (isIntegerLiteral && literal.value == "0" &&
          check(TokenKind::Identifier) &&
          literal.location.endOffset == current().location.offset &&
          isSplitHexLiteralSuffix(current().text)) {
        literal.value += current().text;
        literal.location = sourceSpan(literal.location, current().location);
        literal.type = hasUnsignedIntegerSuffix(current().text) ? makeType("uint")
                                                                : makeType("int");
        ++index_;
      } else if (isIntegerLiteral &&
          check(TokenKind::Identifier) &&
          (current().text == "u" || current().text == "U") &&
          literal.location.endOffset == current().location.offset) {
        literal.location = sourceSpan(literal.location, current().location);
        literal.type = makeType("uint");
        ++index_;
      } else {
        literal.type = isIntegerLiteral ? makeType("int") : makeType("float");
      }
      return literal;
    }

    if (match(TokenKind::String)) {
      HIRExpression literal;
      literal.kind = HIRExpressionKind::Literal;
      literal.value = previous().text;
      literal.location = previous().location;
      literal.type = makeType("str");
      return literal;
    }

    if (!atEnd() && isNameToken(current().kind)) {
      HIRExpression identifier;
      identifier.kind = HIRExpressionKind::Identifier;
      identifier.value = current().text;
      identifier.location = current().location;
      if (identifier.value == "true" || identifier.value == "false") {
        identifier.type = makeType("bool");
      } else if (auto it = variables_.find(identifier.value); it != variables_.end()) {
        identifier.type = it->second;
      } else if (knownTypeNames_.contains(identifier.value)) {
        identifier.type = makeType(identifier.value);
      }
      ++index_;
      return identifier;
    }

    if (match(TokenKind::LParen)) {
      const SourceLocation groupLocation = previous().location;
      HIRExpression group;
      group.kind = HIRExpressionKind::Group;
      group.location = groupLocation;
      group.children.push_back(parseConditional());
      if (failed_) {
        return {};
      }
      group.type = group.children.front().type;
      if (!match(TokenKind::RParen)) {
        fail("expected ')' to close grouped expression", groupLocation);
        return {};
      }
      return parsePostfix(std::move(group));
    }

    if (!atEnd()) {
      fail("unexpected token '" + current().text + "' in expression",
           current().location);
      ++index_;
      return {};
    }

    const SourceLocation location =
        index_ > 0 ? previous().location : SourceLocation{};
    fail("expected expression operand before end of expression", location);
    return {};
  }

  HIRExpression parsePostfix(HIRExpression expression) {
    while (!atEnd()) {
      if (match(TokenKind::Dot)) {
        if (atEnd() || !isNameToken(current().kind)) {
          fail("expected member name after '.' in expression",
               previous().location);
          return {};
        }
        const std::string member = current().text;
        const SourceLocation memberLocation = current().location;
        ++index_;
        HIRExpression access;
        access.kind = HIRExpressionKind::MemberAccess;
        access.value = member;
        access.location = memberLocation;
        access.type = inferMemberType(expression.type, member);
        access.children.push_back(std::move(expression));
        expression = std::move(access);
        continue;
      }

      if (match(TokenKind::LBracket)) {
        const SourceLocation bracketLocation = previous().location;
        bool foundClosingBracket = false;
        std::vector<Token> indexTokens =
            collectUntilMatching(TokenKind::RBracket, &foundClosingBracket);
        if (!foundClosingBracket) {
          fail("expected ']' to close index expression", bracketLocation);
          return {};
        }
        HIRExpression indexExpression =
            ExpressionParser(std::move(indexTokens), knownTypeNames_, structs_,
                             variables_, diagnostics_)
                .parse();
        if (failed_ || indexExpression.kind == HIRExpressionKind::Empty) {
          failed_ = true;
          return {};
        }
        HIRExpression access;
        access.kind = HIRExpressionKind::IndexAccess;
        access.location = bracketLocation;
        access.type = inferIndexType(expression.type);
        access.children.push_back(std::move(expression));
        access.children.push_back(std::move(indexExpression));
        expression = std::move(access);
        continue;
      }

      if (match(TokenKind::LParen)) {
        std::vector<HIRExpression> arguments;
        while (!atEnd() && !check(TokenKind::RParen)) {
          std::vector<Token> argumentTokens =
              collectUntilTopLevelCommaOr(TokenKind::RParen);
          HIRExpression argument =
              ExpressionParser(std::move(argumentTokens), knownTypeNames_,
                               structs_, variables_, diagnostics_)
                  .parse();
          if (failed_ || argument.kind == HIRExpressionKind::Empty) {
            failed_ = true;
            return {};
          }
          arguments.push_back(std::move(argument));
          if (!match(TokenKind::Comma)) {
            break;
          }
        }
        if (!match(TokenKind::RParen)) {
          fail("expected ')' to close call expression", expression.location);
          return {};
        }

        if (expression.kind == HIRExpressionKind::Identifier &&
            (expression.value == "texture" || expression.value == "textureLod" ||
             isTextureCompareOperation(expression.value))) {
          if (isTextureCompareOperation(expression.value)) {
            HIRExpression compare;
            compare.kind = isManualLodTextureCompare(expression.value)
                               ? HIRExpressionKind::TextureCompareLodManual
                               : HIRExpressionKind::TextureCompare;
            compare.value = expression.value;
            compare.location = expression.location;
            compare.children = std::move(arguments);
            compare.type = inferTextureCompareType(compare.children,
                                                   compare.value);
            expression = std::move(compare);
            continue;
          }

          HIRExpression sample;
          sample.kind = HIRExpressionKind::TextureSample;
          sample.value = expression.value;
          sample.location = expression.location;
          sample.children = std::move(arguments);
          sample.type = inferTextureSampleType(
              sample.children, isExplicitLodTextureSample(sample.value));
          expression = std::move(sample);
          continue;
        }

        if (expression.kind == HIRExpressionKind::MemberAccess &&
            expression.value == "sample" && !expression.children.empty()) {
          HIRExpression sample;
          sample.kind = HIRExpressionKind::TextureSample;
          sample.value = "sample";
          sample.location = expression.location;
          sample.children.push_back(std::move(expression.children.front()));
          for (HIRExpression &argument : arguments) {
            sample.children.push_back(std::move(argument));
          }
          sample.type = inferTextureSampleType(sample.children, false);
          expression = std::move(sample);
          continue;
        }

        if (expression.kind == HIRExpressionKind::Identifier &&
            expression.value == "nonuniform") {
          HIRExpression marker;
          marker.kind = HIRExpressionKind::NonUniform;
          marker.value = "nonuniform";
          marker.location = expression.location;
          marker.children = std::move(arguments);
          if (!marker.children.empty()) {
            marker.type = marker.children.front().type;
          }
          expression = std::move(marker);
          continue;
        }

        HIRExpression call;
        call.kind = expression.kind == HIRExpressionKind::Identifier &&
                            knownTypeNames_.contains(expression.value)
                        ? HIRExpressionKind::Constructor
                        : HIRExpressionKind::Call;
        call.value = expression.value;
        call.location = expression.location;
        call.children = std::move(arguments);
        call.type = inferCallType(expression, call.children, call.kind);
        if (call.value.empty()) {
          call.children.insert(call.children.begin(), std::move(expression));
        }
        expression = std::move(call);
        continue;
      }

      break;
    }
    return expression;
  }

  std::vector<Token> collectUntilMatching(TokenKind closing, bool *foundClosing) {
    std::vector<Token> collected;
    int parenDepth = 0;
    int bracketDepth = 0;
    while (!atEnd()) {
      if (check(closing) && parenDepth == 0 && bracketDepth == 0) {
        ++index_;
        if (foundClosing != nullptr) {
          *foundClosing = true;
        }
        break;
      }
      if (check(TokenKind::LParen)) {
        ++parenDepth;
      } else if (check(TokenKind::RParen)) {
        --parenDepth;
      } else if (check(TokenKind::LBracket)) {
        ++bracketDepth;
      } else if (check(TokenKind::RBracket)) {
        --bracketDepth;
      }
      collected.push_back(current());
      ++index_;
    }
    return collected;
  }

  std::vector<Token> collectUntilTopLevelCommaOr(TokenKind closing) {
    std::vector<Token> collected;
    int parenDepth = 0;
    int bracketDepth = 0;
    while (!atEnd()) {
      if (parenDepth == 0 && bracketDepth == 0 &&
          (check(TokenKind::Comma) || check(closing))) {
        break;
      }
      if (check(TokenKind::LParen)) {
        ++parenDepth;
      } else if (check(TokenKind::RParen)) {
        --parenDepth;
      } else if (check(TokenKind::LBracket)) {
        ++bracketDepth;
      } else if (check(TokenKind::RBracket)) {
        --bracketDepth;
      }
      collected.push_back(current());
      ++index_;
    }
    return collected;
  }

  HIRType inferMemberType(const HIRType &base, std::string_view member) const {
    if (HIRType swizzle = swizzleType(base, member); !swizzle.name.empty()) {
      return swizzle;
    }

    const std::string structName = baseTypeName(base);
    auto structure = structs_.find(structName);
    if (structure == structs_.end()) {
      return {};
    }
    for (const HIRField &field : structure->second.fields) {
      if (field.name == member) {
        return field.type;
      }
    }
    return {};
  }

  static HIRType inferIndexType(HIRType base) {
    base = stripTypeQualifier(std::move(base));
    if (!base.name.empty() && base.name.back() == '*') {
      return pointerlessType(std::move(base));
    }
    if (base.arraySize.has_value()) {
      return arrayElementType(std::move(base));
    }
    const std::string name = baseTypeName(base);
    if (isVectorType(name)) {
      return scalarTypeForVector(name);
    }
    return base;
  }

  HIRType inferCallType(const HIRExpression &callee,
                        const std::vector<HIRExpression> &arguments,
                        HIRExpressionKind kind) const {
    if (kind == HIRExpressionKind::Constructor && !callee.value.empty()) {
      return makeType(callee.value);
    }
    if (kind == HIRExpressionKind::Call &&
        isWorkgroupBarrierCallName(callee.value) && arguments.empty()) {
      return HIRType{"void", std::nullopt, callee.location};
    }
    if (kind == HIRExpressionKind::Call &&
        isImageAccessCallName(callee.value)) {
      return inferImageAccessCallType(callee.value, arguments,
                                      callee.location);
    }
    if (const std::optional<HIRType> intrinsicType =
            inferHIRIntrinsicResultType(callee.value, arguments,
                                        callee.location)) {
      return *intrinsicType;
    }
    return {};
  }

  static HIRType inferBinaryType(const HIRType &left, const HIRType &right,
                                 std::string_view op) {
    if (op == "<" || op == "<=" || op == ">" || op == ">=" || op == "==" ||
        op == "!=" || op == "&&" || op == "||") {
      return makeType("bool");
    }

    const std::string leftName = baseTypeName(left);
    const std::string rightName = baseTypeName(right);
    if (isVectorType(leftName)) {
      return left;
    }
    if (isVectorType(rightName)) {
      return right;
    }
    if (isFloatLike(leftName)) {
      return left;
    }
    if (isFloatLike(rightName)) {
      return right;
    }
    return !left.name.empty() ? left : right;
  }

  std::vector<Token> tokens_;
  const std::set<std::string> &knownTypeNames_;
  const std::unordered_map<std::string, HIRStruct> &structs_;
  const std::unordered_map<std::string, HIRType> &variables_;
  DiagnosticEngine *diagnostics_ = nullptr;
  std::size_t index_ = 0;
  bool failed_ = false;
};

std::optional<std::size_t> parsePositiveArraySize(std::string_view text) {
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

std::optional<std::size_t>
positiveArraySizeFromFoldedScalar(const FoldedHIRScalar &folded) {
  if (folded.isBool || !folded.isInteger || !std::isfinite(folded.number)) {
    return std::nullopt;
  }

  const double rounded = std::round(folded.number);
  if (std::fabs(folded.number - rounded) > 0.000000001 || rounded <= 0.0 ||
      rounded > static_cast<double>(std::numeric_limits<std::size_t>::max())) {
    return std::nullopt;
  }

  return static_cast<std::size_t>(rounded);
}

std::optional<std::size_t> resolveFoldedArrayElementCount(
    std::string_view arraySize,
    const std::unordered_map<std::string, HIRType> &constantTypes,
    const HIRScalarConstantMap &constantValues) {
  const std::string source(arraySize);
  DiagnosticEngine lexDiagnostics;
  Lexer lexer("<array-dimension>", source, lexDiagnostics);
  std::vector<Token> tokens = lexer.lex();
  if (lexDiagnostics.hasErrors() || tokens.empty()) {
    return std::nullopt;
  }
  if (!tokens.empty() && tokens.back().kind == TokenKind::End) {
    tokens.pop_back();
  }
  if (tokens.empty()) {
    return std::nullopt;
  }

  static const std::set<std::string> dimensionTypeNames = {
      "bool", "float", "int", "uint"};
  const std::unordered_map<std::string, HIRStruct> noStructs;
  ExpressionParser parser(std::move(tokens), dimensionTypeNames, noStructs,
                          constantTypes);
  HIRExpression expression = parser.parse();
  const std::string expressionType = baseTypeName(expression.type);
  if (!parser.consumedAll() || expression.type.arraySize.has_value() ||
      (expressionType != "int" && expressionType != "uint") ||
      !isKnownPureHIRExpression(expression)) {
    return std::nullopt;
  }

  const std::optional<FoldedHIRScalar> folded =
      foldHIRScalarExpression(expression, constantValues);
  if (!folded.has_value()) {
    return std::nullopt;
  }
  return positiveArraySizeFromFoldedScalar(*folded);
}

std::optional<std::size_t> resolveArrayElementCount(
    std::string_view arraySize,
    const std::unordered_map<std::string, HIRType> &constantTypes,
    const HIRScalarConstantMap &constantValues) {
  if (const std::optional<std::size_t> literal =
          parsePositiveArraySize(arraySize)) {
    return literal;
  }

  const std::string constantName(arraySize);
  const auto constantType = constantTypes.find(constantName);
  const auto constantValue = constantValues.find(constantName);
  if (constantType != constantTypes.end() &&
      constantValue != constantValues.end() &&
      !constantType->second.arraySize.has_value() &&
      (constantType->second.name == "int" ||
       constantType->second.name == "uint")) {
    if (const std::optional<std::size_t> foldedConstant =
            positiveArraySizeFromFoldedScalar(constantValue->second)) {
      return foldedConstant;
    }
  }

  return resolveFoldedArrayElementCount(arraySize, constantTypes,
                                        constantValues);
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

bool isResolvedFixedArraySize(
    std::string_view arraySize,
    const std::unordered_map<std::string, HIRType> &constantTypes,
    const HIRScalarConstantMap &constantValues) {
  for (std::string_view dimension : splitArrayDimensions(arraySize)) {
    if (!resolveArrayElementCount(dimension, constantTypes, constantValues)
             .has_value()) {
      return false;
    }
  }
  return true;
}

void validateArraySize(
    const std::optional<std::string> &arraySize,
    std::string_view context,
    SourceLocation location,
    const std::unordered_map<std::string, HIRType> &constantTypes,
    const HIRScalarConstantMap &constantValues,
    DiagnosticEngine &diagnostics) {
  if (!arraySize.has_value()) {
    return;
  }

  if (arraySize->empty() ||
      isResolvedFixedArraySize(*arraySize, constantTypes, constantValues)) {
    return;
  }

  diagnostics.error(
      "sema.array-size",
      "array size for " + std::string(context) +
          " must be an unsized array or use positive integer literals and "
          "pure folded top-level int/uint constant expressions for every fixed "
          "dimension, got '" +
          *arraySize + "'",
      location);
}

void validateFunctionParameterArraySizes(
    const std::vector<FunctionDecl> &functions, const std::string &functionContext,
    const std::unordered_map<std::string, HIRType> &constantTypes,
    const HIRScalarConstantMap &constantValues,
    DiagnosticEngine &diagnostics) {
  for (const FunctionDecl &function : functions) {
    for (const Parameter &parameter : function.parameters) {
      validateArraySize(parameter.type.arraySize,
                        "parameter '" + parameter.name + "' in " +
                            functionContext + " '" + function.name + "'",
                        parameter.location, constantTypes, constantValues,
                        diagnostics);
    }
  }
}

void validateArraySizePolicy(
    const std::vector<StructDecl> &structs,
    const std::vector<FunctionDecl> &functions,
    const std::vector<StageDecl> &stages,
    const std::unordered_map<std::string, HIRType> &constantTypes,
    const HIRScalarConstantMap &constantValues,
    DiagnosticEngine &diagnostics) {
  for (const StructDecl &decl : structs) {
    for (const StructField &field : decl.fields) {
      validateArraySize(field.type.arraySize,
                        "field '" + field.name + "' in struct '" +
                            decl.name + "'",
                        field.location, constantTypes, constantValues,
                        diagnostics);
    }
  }

  validateFunctionParameterArraySizes(functions, "function", constantTypes,
                                      constantValues, diagnostics);

  for (const StageDecl &stage : stages) {
    for (const ResourceDecl &resource : stage.resources) {
      validateArraySize(resource.type.arraySize,
                        "resource '" + resource.name + "' in stage '" +
                            stage.stage + "'",
                        resource.location, constantTypes, constantValues,
                        diagnostics);
    }
    validateFunctionParameterArraySizes(
        stage.functions, "stage '" + stage.stage + "' function", constantTypes,
        constantValues, diagnostics);
  }
}

bool isScalarAtomicIntegerStorageType(const HIRType &type) {
  HIRType normalized = stripTypeQualifier(type);
  normalized.name = stripPointerSuffix(std::move(normalized.name));
  return normalized.name == "atomic<int>" || normalized.name == "atomic<uint>";
}

std::optional<FoldedHIRScalar> foldExpression(
    const HIRExpression &expression,
    const HIRScalarConstantMap &constantValues) {
  return foldHIRScalarExpression(expression, constantValues);
}

std::optional<std::string> foldExpressionToString(
    const HIRExpression &expression,
    const HIRScalarConstantMap &constantValues) {
  std::optional<FoldedHIRScalar> folded = foldExpression(expression, constantValues);
  if (!folded) {
    return std::nullopt;
  }
  return formatFoldedHIRScalar(*folded);
}

class BodyParser {
public:
  BodyParser(const std::vector<Token> &tokens,
             const std::set<std::string> &knownTypeNames,
             const std::unordered_map<std::string, HIRStruct> &structs,
             std::unordered_map<std::string, HIRType> variables,
             DiagnosticEngine &diagnostics,
             std::set<std::string> mutableLocals = {})
      : tokens_(tokens), knownTypeNames_(knownTypeNames), structs_(structs),
        variables_(std::move(variables)), diagnostics_(diagnostics),
        mutableLocals_(std::move(mutableLocals)) {}

  std::vector<HIRStatement> parse() {
    std::vector<HIRStatement> statements;
    while (index_ < tokens_.size()) {
      std::vector<Token> statementTokens = collectStatement();
      if (statementTokens.empty()) {
        continue;
      }
      HIRStatement statement = parseStatement(std::move(statementTokens));
      if (statement.kind == HIRStatementKind::Raw && statement.rawTokens.empty()) {
        continue;
      }
      statements.push_back(std::move(statement));
    }
    return statements;
  }

private:
  struct DeclarationDeclarator {
    std::size_t nameIndex = 0;
    HIRType type;
  };

  struct IncrementDecrementUpdate {
    std::string name;
    std::string op;
    SourceLocation nameLocation;
    SourceLocation opLocation;
  };

  struct ControlConditionSpan {
    std::size_t begin = 0;
    std::size_t end = 0;
    std::size_t bodyBegin = 0;
  };

  struct SwitchSection {
    bool isDefault = false;
    HIRExpression label;
    std::vector<HIRStatement> body;
    SourceLocation location;
  };

  std::vector<Token> collectStatement() {
    std::vector<Token> statement;
    int braceDepth = 0;
    int parenDepth = 0;
    int bracketDepth = 0;
    const bool controlBlock =
        index_ < tokens_.size() && tokens_[index_].kind == TokenKind::Identifier &&
        (tokens_[index_].text == "if" || tokens_[index_].text == "for" ||
         tokens_[index_].text == "while" || tokens_[index_].text == "loop" ||
         tokens_[index_].text == "switch");
    const bool standaloneBlock =
        index_ < tokens_.size() && tokens_[index_].kind == TokenKind::LBrace;

    while (index_ < tokens_.size()) {
      const Token &token = tokens_[index_++];
      statement.push_back(token);
      if (token.kind == TokenKind::LBrace) {
        ++braceDepth;
      } else if (token.kind == TokenKind::RBrace) {
        --braceDepth;
        if ((controlBlock || standaloneBlock) && braceDepth == 0) {
          if (controlBlock) {
            collectOptionalElse(statement);
          }
          break;
        }
      } else if (token.kind == TokenKind::LParen) {
        ++parenDepth;
      } else if (token.kind == TokenKind::RParen) {
        --parenDepth;
      } else if (token.kind == TokenKind::LBracket) {
        ++bracketDepth;
      } else if (token.kind == TokenKind::RBracket) {
        --bracketDepth;
      } else if (token.kind == TokenKind::Semicolon && braceDepth == 0 &&
                 parenDepth == 0 && bracketDepth == 0) {
        break;
      }
    }
    return statement;
  }

  void collectOptionalElse(std::vector<Token> &statement) {
    if (index_ >= tokens_.size() || tokens_[index_].kind != TokenKind::Identifier ||
        tokens_[index_].text != "else") {
      return;
    }
    statement.push_back(tokens_[index_++]);
    if (index_ >= tokens_.size()) {
      return;
    }

    std::vector<Token> elseStatement = collectStatement();
    statement.insert(statement.end(), elseStatement.begin(), elseStatement.end());
    if (index_ < tokens_.size() && !elseStatement.empty() &&
        elseStatement.front().kind == TokenKind::Identifier &&
        elseStatement.front().text == "if") {
      collectOptionalElse(statement);
    }
  }

  HIRStatement parseStatement(std::vector<Token> tokens) {
    const SourceLocation statementLocation = tokenSpan(tokens);
    if (!tokens.empty() && tokens.back().kind == TokenKind::Semicolon) {
      tokens.pop_back();
    }

    HIRStatement statement;
    statement.rawTokens = tokens;
    statement.location = statementLocation;
    if (tokens.empty()) {
      return statement;
    }

    if (tokens.front().kind == TokenKind::LBrace) {
      return parseBlockStatement(std::move(statement), tokens);
    }

    if (tokens.front().kind == TokenKind::KeywordReturn) {
      statement.kind = HIRStatementKind::Return;
      statement.value = parseExpression(tokens, 1, tokens.size());
      statement.rawTokens.clear();
      return statement;
    }

    if (tokens.front().kind == TokenKind::Identifier && tokens.front().text == "if") {
      return parseIfStatement(std::move(statement), tokens);
    }

    if (tokens.front().kind == TokenKind::Identifier && tokens.front().text == "for") {
      return parseForStatement(std::move(statement), tokens);
    }

    if (tokens.front().kind == TokenKind::Identifier && tokens.front().text == "while") {
      return parseWhileStatement(std::move(statement), tokens);
    }

    if (tokens.front().kind == TokenKind::Identifier && tokens.front().text == "do") {
      return parseDoWhileStatement(std::move(statement), tokens);
    }

    if (tokens.front().kind == TokenKind::Identifier && tokens.front().text == "loop") {
      return parseLoopStatement(std::move(statement), tokens);
    }

    if (tokens.front().kind == TokenKind::Identifier &&
        tokens.front().text == "switch") {
      return parseSwitchStatement(std::move(statement), tokens);
    }

    if (tokens.size() == 1 && tokens.front().kind == TokenKind::Identifier) {
      if (tokens.front().text == "break") {
        statement.kind = HIRStatementKind::Break;
        statement.location = tokens.front().location;
        statement.rawTokens.clear();
        return statement;
      }
      if (tokens.front().text == "continue") {
        statement.kind = HIRStatementKind::Continue;
        statement.location = tokens.front().location;
        statement.rawTokens.clear();
        return statement;
      }
      if (tokens.front().text == "discard") {
        statement.kind = HIRStatementKind::Discard;
        statement.location = tokens.front().location;
        statement.rawTokens.clear();
        return statement;
      }
    }

    if (std::optional<HIRStatement> update =
            parseIncrementDecrementStatement(tokens, statementLocation)) {
      return std::move(*update);
    }

    const std::optional<std::size_t> equal = topLevelEqual(tokens);
    if (equal.has_value()) {
      if (std::optional<HIRStatement> letMut =
              parseLetMutDeclarationStatement(tokens, *equal,
                                              statementLocation)) {
        return std::move(*letMut);
      }

      if (isLetMutDeclarationStart(tokens)) {
        return makeRawFallback(std::move(statement));
      }

      if (std::optional<DeclarationDeclarator> declaration =
              parseColonStyleVarDeclarator(tokens, *equal)) {
        if (hasUnsupportedExpressionToken(tokens, *equal + 1, tokens.size())) {
          diagnoseUnsupportedIncrementDecrementTokens(tokens, *equal + 1,
                                                      tokens.size());
          return makeRawFallback(std::move(statement));
        }
        statement.kind = HIRStatementKind::Declaration;
        statement.name = tokens[declaration->nameIndex].text;
        statement.declaredType = declaration->type;
        statement.value = parseExpression(tokens, *equal + 1, tokens.size());
        variables_[statement.name] = statement.declaredType;
        mutableLocals_.insert(statement.name);
        statement.rawTokens.clear();
        return statement;
      }

      if (std::optional<DeclarationDeclarator> declaration =
              parseDeclarationDeclarator(tokens, *equal)) {
        if (hasUnsupportedExpressionToken(tokens, *equal + 1, tokens.size())) {
          diagnoseUnsupportedIncrementDecrementTokens(tokens, *equal + 1,
                                                      tokens.size());
          return makeRawFallback(std::move(statement));
        }
        statement.kind = HIRStatementKind::Declaration;
        statement.name = tokens[declaration->nameIndex].text;
        statement.declaredType = declaration->type;
        statement.value = parseExpression(tokens, *equal + 1, tokens.size());
        variables_[statement.name] = statement.declaredType;
        mutableLocals_.insert(statement.name);
        statement.rawTokens.clear();
        return statement;
      }

      if (hasUnsupportedExpressionToken(tokens, 0, tokens.size())) {
        diagnoseUnsupportedIncrementDecrementTokens(tokens, 0, tokens.size());
        return makeRawFallback(std::move(statement));
      }

      statement.kind = HIRStatementKind::Assignment;
      if (*equal >= 1 && tokens[*equal - 1].kind == TokenKind::Operator &&
          isCompoundAssignmentOperator(tokens[*equal - 1].text)) {
        const std::size_t opIndex = *equal - 1;
        statement.target = parseExpression(tokens, 0, opIndex);
        HIRExpression rhs = parseExpression(tokens, *equal + 1, tokens.size());
        HIRExpression value;
        value.kind = HIRExpressionKind::Binary;
        value.value = tokens[opIndex].text;
        value.location = tokens[opIndex].location;
        value.children.push_back(statement.target);
        value.children.push_back(std::move(rhs));
        value.type = statement.target.type.name.empty() ? value.children.back().type
                                                        : statement.target.type;
        statement.value = std::move(value);
      } else {
        statement.target = parseExpression(tokens, 0, *equal);
        statement.value = parseExpression(tokens, *equal + 1, tokens.size());
      }
      statement.rawTokens.clear();
      return statement;
    }

    if (std::optional<DeclarationDeclarator> declaration =
            parseColonStyleVarDeclarator(tokens, tokens.size())) {
      statement.kind = HIRStatementKind::Declaration;
      statement.name = tokens[declaration->nameIndex].text;
      statement.declaredType = declaration->type;
      variables_[statement.name] = statement.declaredType;
      mutableLocals_.insert(statement.name);
      statement.rawTokens.clear();
      return statement;
    }

    if (std::optional<DeclarationDeclarator> declaration =
            parseDeclarationDeclarator(tokens, tokens.size())) {
      statement.kind = HIRStatementKind::Declaration;
      statement.name = tokens[declaration->nameIndex].text;
      statement.declaredType = declaration->type;
      variables_[statement.name] = statement.declaredType;
      mutableLocals_.insert(statement.name);
      statement.rawTokens.clear();
      return statement;
    }

    if (hasUnsupportedExpressionToken(tokens, 0, tokens.size())) {
      diagnoseUnsupportedIncrementDecrementTokens(tokens, 0, tokens.size());
      return makeRawFallback(std::move(statement));
    }

    statement.kind = HIRStatementKind::Expression;
    statement.value = parseExpression(tokens, 0, tokens.size());
    statement.rawTokens.clear();
    return statement;
  }

  HIRStatement parseBlockStatement(HIRStatement statement,
                                   const std::vector<Token> &tokens) const {
    statement.kind = HIRStatementKind::Block;
    const std::optional<std::size_t> close =
        findMatching(tokens, 0, TokenKind::LBrace, TokenKind::RBrace);
    if (!close.has_value() || *close + 1 != tokens.size()) {
      return makeRawFallback(std::move(statement));
    }

    statement.body = parseStatementBody(tokens, 0, tokens.size());
    statement.rawTokens.clear();
    return statement;
  }

  HIRStatement parseForStatement(HIRStatement statement,
                                 const std::vector<Token> &tokens) {
    statement.kind = HIRStatementKind::For;
    const std::optional<std::size_t> headerOpen =
        findToken(tokens, TokenKind::LParen, 1);
    if (!headerOpen.has_value()) {
      return makeRawFallback(std::move(statement));
    }
    const std::optional<std::size_t> headerClose =
        findMatching(tokens, *headerOpen, TokenKind::LParen, TokenKind::RParen);
    if (!headerClose.has_value()) {
      return makeRawFallback(std::move(statement));
    }

    std::vector<std::vector<Token>> headerParts =
        splitTopLevelSemicolons(tokens, *headerOpen + 1, *headerClose);
    if (headerParts.size() != 3) {
      return makeRawFallback(std::move(statement));
    }

    if (!headerParts[1].empty() &&
        hasUnsupportedExpressionToken(headerParts[1], 0, headerParts[1].size())) {
      return makeRawFallback(std::move(statement));
    }

    const std::unordered_map<std::string, HIRType> outerVariables = variables_;
    const std::set<std::string> outerMutableLocals = mutableLocals_;
    if (!headerParts[0].empty()) {
      statement.initializer.push_back(parseStatement(headerParts[0]));
    }
    if (headerParts[1].empty()) {
      statement.value = makeBoolLiteral("true", tokens.front().location);
    } else {
      statement.value = parseExpression(headerParts[1], 0, headerParts[1].size());
    }
    statement.updateTokens = headerParts[2];
    if (!headerParts[2].empty()) {
      HIRStatement update = parseStatement(headerParts[2]);
      if (update.kind != HIRStatementKind::Raw) {
        statement.update.push_back(std::move(update));
      }
    }

    std::size_t bodyBegin = *headerClose + 1;
    statement.body = parseStatementBody(tokens, bodyBegin, tokens.size());
    variables_ = outerVariables;
    mutableLocals_ = outerMutableLocals;
    statement.rawTokens.clear();
    return statement;
  }

  HIRStatement parseWhileStatement(HIRStatement statement,
                                   const std::vector<Token> &tokens) {
    statement.kind = HIRStatementKind::For;
    const std::optional<ControlConditionSpan> condition =
        parseControlConditionSpan(tokens);
    if (!condition.has_value()) {
      return makeRawFallback(std::move(statement));
    }

    if (hasUnsupportedExpressionToken(tokens, condition->begin,
                                      condition->end)) {
      return makeRawFallback(std::move(statement));
    }
    statement.value = parseExpression(tokens, condition->begin, condition->end);

    std::size_t bodyBegin = condition->bodyBegin;
    while (bodyBegin < tokens.size() &&
           tokens[bodyBegin].kind == TokenKind::Semicolon) {
      ++bodyBegin;
    }
    if (bodyBegin < tokens.size() &&
        tokens[bodyBegin].kind == TokenKind::LBrace) {
      const std::optional<std::size_t> bodyClose =
          findMatching(tokens, bodyBegin, TokenKind::LBrace, TokenKind::RBrace);
      if (!bodyClose.has_value() || *bodyClose + 1 != tokens.size()) {
        return makeRawFallback(std::move(statement));
      }
    }

    statement.body = parseStatementBody(tokens, bodyBegin, tokens.size());
    statement.rawTokens.clear();
    return statement;
  }

  HIRStatement parseDoWhileStatement(HIRStatement statement,
                                     const std::vector<Token> &tokens) {
    statement.kind = HIRStatementKind::For;
    if (tokens.size() < 5 || tokens[1].kind != TokenKind::LBrace) {
      return makeRawFallback(std::move(statement));
    }

    const std::optional<std::size_t> bodyClose =
        findMatching(tokens, 1, TokenKind::LBrace, TokenKind::RBrace);
    if (!bodyClose.has_value() || *bodyClose + 1 >= tokens.size()) {
      return makeRawFallback(std::move(statement));
    }

    std::vector<Token> conditionTokens(
        tokens.begin() + static_cast<std::ptrdiff_t>(*bodyClose + 1),
        tokens.end());
    if (conditionTokens.empty() ||
        conditionTokens.front().kind != TokenKind::Identifier ||
        conditionTokens.front().text != "while") {
      return makeRawFallback(std::move(statement));
    }

    const std::optional<ControlConditionSpan> condition =
        parseControlConditionSpan(conditionTokens);
    if (!condition.has_value() || condition->bodyBegin != conditionTokens.size()) {
      return makeRawFallback(std::move(statement));
    }
    if (hasUnsupportedExpressionToken(conditionTokens, condition->begin,
                                      condition->end)) {
      return makeRawFallback(std::move(statement));
    }

    const HIRExpression conditionExpression =
        parseExpression(conditionTokens, condition->begin, condition->end);
    statement.value = makeBoolLiteral("true", tokens.front().location);
    statement.body = parseStatementBody(tokens, 1, *bodyClose + 1);
    rewriteDoWhileContinues(statement.body, conditionExpression);
    statement.body.push_back(
        makeConditionBreakStatement(conditionExpression,
                                    conditionTokens.front().location));
    statement.rawTokens.clear();
    return statement;
  }

  HIRStatement parseIfStatement(HIRStatement statement,
                                const std::vector<Token> &tokens) {
    statement.kind = HIRStatementKind::If;
    const std::optional<ControlConditionSpan> condition =
        parseControlConditionSpan(tokens);
    if (!condition.has_value()) {
      return makeRawFallback(std::move(statement));
    }

    if (hasUnsupportedExpressionToken(tokens, condition->begin, condition->end)) {
      return makeRawFallback(std::move(statement));
    }
    statement.value = parseExpression(tokens, condition->begin, condition->end);

    std::size_t thenBegin = condition->bodyBegin;
    while (thenBegin < tokens.size() && tokens[thenBegin].kind == TokenKind::Semicolon) {
      ++thenBegin;
    }
    std::size_t thenEnd = tokens.size();
    std::optional<std::size_t> elseIndex;
    if (thenBegin < tokens.size() && tokens[thenBegin].kind == TokenKind::LBrace) {
      const std::optional<std::size_t> thenClose =
          findMatching(tokens, thenBegin, TokenKind::LBrace, TokenKind::RBrace);
      if (!thenClose.has_value()) {
        return makeRawFallback(std::move(statement));
      }
      thenEnd = *thenClose + 1;
      if (thenEnd < tokens.size() && tokens[thenEnd].kind == TokenKind::Identifier &&
          tokens[thenEnd].text == "else") {
        elseIndex = thenEnd;
      }
    } else {
      for (std::size_t i = thenBegin; i < tokens.size(); ++i) {
        if (tokens[i].kind == TokenKind::Identifier && tokens[i].text == "else") {
          elseIndex = i;
          thenEnd = i;
          break;
        }
      }
    }

    statement.body = parseStatementBody(tokens, thenBegin, thenEnd);
    if (elseIndex.has_value() && *elseIndex + 1 < tokens.size()) {
      const std::size_t elseBegin = *elseIndex + 1;
      if (tokens[elseBegin].kind == TokenKind::Identifier &&
          tokens[elseBegin].text == "if") {
        std::vector<Token> nested(tokens.begin() + static_cast<std::ptrdiff_t>(elseBegin),
                                  tokens.end());
        statement.elseBody.push_back(parseStatement(std::move(nested)));
      } else {
        statement.elseBody = parseStatementBody(tokens, elseBegin, tokens.size());
      }
    }
    statement.rawTokens.clear();
    return statement;
  }

  HIRStatement parseLoopStatement(HIRStatement statement,
                                  const std::vector<Token> &tokens) {
    statement.kind = HIRStatementKind::For;
    if (tokens.size() < 2 || tokens[1].kind != TokenKind::LBrace) {
      return makeRawFallback(std::move(statement));
    }
    const std::optional<std::size_t> bodyClose =
        findMatching(tokens, 1, TokenKind::LBrace, TokenKind::RBrace);
    if (!bodyClose.has_value() || *bodyClose + 1 != tokens.size()) {
      return makeRawFallback(std::move(statement));
    }

    statement.value = makeBoolLiteral("true", tokens.front().location);
    statement.body = parseStatementBody(tokens, 1, tokens.size());
    statement.rawTokens.clear();
    return statement;
  }

  HIRStatement parseSwitchStatement(HIRStatement statement,
                                    const std::vector<Token> &tokens) {
    if (tokens.size() < 6) {
      return makeRawFallback(std::move(statement));
    }

    const std::optional<ControlConditionSpan> selectorSpan =
        parseControlConditionSpan(tokens);
    if (!selectorSpan.has_value() ||
        hasUnsupportedExpressionToken(tokens, selectorSpan->begin,
                                      selectorSpan->end)) {
      return makeRawFallback(std::move(statement));
    }
    std::size_t bodyBegin = selectorSpan->bodyBegin;
    while (bodyBegin < tokens.size() &&
           tokens[bodyBegin].kind == TokenKind::Semicolon) {
      ++bodyBegin;
    }
    if (bodyBegin >= tokens.size() || tokens[bodyBegin].kind != TokenKind::LBrace) {
      return makeRawFallback(std::move(statement));
    }
    const std::optional<std::size_t> bodyClose =
        findMatching(tokens, bodyBegin, TokenKind::LBrace, TokenKind::RBrace);
    if (!bodyClose.has_value() || *bodyClose + 1 != tokens.size()) {
      return makeRawFallback(std::move(statement));
    }

    std::optional<std::vector<SwitchSection>> sections =
        parseSwitchSections(tokens, bodyBegin + 1, *bodyClose);
    if (!sections.has_value() || sections->empty()) {
      return makeRawFallback(std::move(statement));
    }

    HIRExpression selector =
        parseExpression(tokens, selectorSpan->begin, selectorSpan->end);
    if (!isSwitchComparableType(selector.type) ||
        !switchLabelsMatchSelector(selector.type, *sections)) {
      return makeRawFallback(std::move(statement));
    }

    const std::unordered_map<std::string, HIRType> outerVariables = variables_;
    const std::set<std::string> outerMutableLocals = mutableLocals_;
    const std::string selectorName = makeUniqueLocalName("__crossgl_selector",
                                                         selector.type);
    HIRStatement selectorDeclaration;
    selectorDeclaration.kind = HIRStatementKind::Declaration;
    selectorDeclaration.location = selector.location;
    selectorDeclaration.declaredType = selector.type;
    selectorDeclaration.name = selectorName;
    selectorDeclaration.value = std::move(selector);

    const HIRExpression selectorReference = makeIdentifierExpression(
        selectorName, selectorDeclaration.declaredType,
        selectorDeclaration.location);
    std::optional<std::vector<HIRStatement>> lowered =
        lowerSwitchSections(selectorReference, std::move(*sections));
    if (!lowered.has_value() || lowered->empty()) {
      variables_ = outerVariables;
      mutableLocals_ = outerMutableLocals;
      return makeRawFallback(std::move(statement));
    }

    statement.kind = HIRStatementKind::Block;
    statement.body = std::move(*lowered);
    statement.body.insert(statement.body.begin(), std::move(selectorDeclaration));
    variables_ = outerVariables;
    mutableLocals_ = outerMutableLocals;
    statement.rawTokens.clear();
    return statement;
  }

  HIRExpression makeGroupedExpression(HIRExpression expression) const {
    HIRExpression group;
    group.kind = HIRExpressionKind::Group;
    group.type = expression.type;
    group.location = expression.location;
    group.children.push_back(std::move(expression));
    return group;
  }

  HIRExpression makeNegatedCondition(HIRExpression condition,
                                     SourceLocation location) const {
    HIRExpression negated;
    negated.kind = HIRExpressionKind::Unary;
    negated.value = "!";
    negated.type = makeType("bool");
    negated.location = std::move(location);
    negated.children.push_back(makeGroupedExpression(std::move(condition)));
    return negated;
  }

  HIRStatement makeBreakStatement(SourceLocation location) const {
    HIRStatement statement;
    statement.kind = HIRStatementKind::Break;
    statement.location = std::move(location);
    return statement;
  }

  HIRStatement makeContinueStatement(SourceLocation location) const {
    HIRStatement statement;
    statement.kind = HIRStatementKind::Continue;
    statement.location = std::move(location);
    return statement;
  }

  HIRExpression makeIdentifierExpression(std::string name, HIRType type,
                                         SourceLocation location) const {
    HIRExpression expression;
    expression.kind = HIRExpressionKind::Identifier;
    expression.value = std::move(name);
    expression.type = std::move(type);
    expression.location = std::move(location);
    return expression;
  }

  std::string makeUniqueLocalName(std::string_view base, const HIRType &type) {
    std::string name(base);
    std::size_t suffix = 0;
    while (variables_.contains(name)) {
      name = std::string(base) + std::to_string(++suffix);
    }
    variables_[name] = type;
    mutableLocals_.insert(name);
    return name;
  }

  bool isSwitchComparableType(const HIRType &type) const {
    if (type.name.empty() || type.arraySize.has_value()) {
      return false;
    }
    const std::string base = baseTypeName(type);
    return base == "bool" || isNumericScalarTypeName(base);
  }

  bool switchLabelsMatchSelector(
      const HIRType &selectorType,
      const std::vector<SwitchSection> &sections) const {
    const HIRType strippedSelector = stripTypeQualifier(selectorType);
    for (const SwitchSection &section : sections) {
      if (section.isDefault) {
        continue;
      }
      if (!isSwitchComparableType(section.label.type) ||
          !sameType(strippedSelector, stripTypeQualifier(section.label.type))) {
        return false;
      }
    }
    return true;
  }

  HIRStatement makeConditionBreakStatement(HIRExpression condition,
                                           SourceLocation location) const {
    HIRStatement statement;
    statement.kind = HIRStatementKind::If;
    statement.location = location;
    statement.value = makeNegatedCondition(std::move(condition), location);
    statement.body.push_back(makeBreakStatement(std::move(location)));
    return statement;
  }

  HIRStatement makeDoWhileContinueReplacement(const HIRExpression &condition,
                                              SourceLocation location) const {
    HIRStatement block;
    block.kind = HIRStatementKind::Block;
    block.location = location;
    block.body.push_back(makeConditionBreakStatement(condition, location));
    block.body.push_back(makeContinueStatement(std::move(location)));
    return block;
  }

  bool isSwitchLabelToken(const Token &token) const {
    return token.kind == TokenKind::Identifier &&
           (token.text == "case" || token.text == "default");
  }

  std::optional<std::size_t> findSwitchLabelColon(
      const std::vector<Token> &tokens, std::size_t begin,
      std::size_t end) const {
    int parenDepth = 0;
    int bracketDepth = 0;
    int braceDepth = 0;
    for (std::size_t cursor = begin; cursor < end; ++cursor) {
      const Token &token = tokens[cursor];
      if (token.kind == TokenKind::LParen) {
        ++parenDepth;
      } else if (token.kind == TokenKind::RParen) {
        --parenDepth;
      } else if (token.kind == TokenKind::LBracket) {
        ++bracketDepth;
      } else if (token.kind == TokenKind::RBracket) {
        --bracketDepth;
      } else if (token.kind == TokenKind::LBrace) {
        ++braceDepth;
      } else if (token.kind == TokenKind::RBrace) {
        --braceDepth;
      } else if (token.kind == TokenKind::Colon && parenDepth == 0 &&
                 bracketDepth == 0 && braceDepth == 0) {
        return cursor;
      } else if ((token.kind == TokenKind::Semicolon ||
                  isSwitchLabelToken(token)) &&
                 parenDepth == 0 && bracketDepth == 0 && braceDepth == 0) {
        return std::nullopt;
      }
    }
    return std::nullopt;
  }

  bool hasTopLevelSwitchLabel(const std::vector<Token> &tokens,
                              std::size_t begin, std::size_t end) const {
    int parenDepth = 0;
    int bracketDepth = 0;
    int braceDepth = 0;
    for (std::size_t cursor = begin; cursor < end; ++cursor) {
      const Token &token = tokens[cursor];
      if (token.kind == TokenKind::LParen) {
        ++parenDepth;
      } else if (token.kind == TokenKind::RParen) {
        --parenDepth;
      } else if (token.kind == TokenKind::LBracket) {
        ++bracketDepth;
      } else if (token.kind == TokenKind::RBracket) {
        --bracketDepth;
      } else if (token.kind == TokenKind::LBrace) {
        ++braceDepth;
      } else if (token.kind == TokenKind::RBrace) {
        --braceDepth;
      } else if (isSwitchLabelToken(token) && parenDepth == 0 &&
                 bracketDepth == 0 && braceDepth == 0) {
        return true;
      }
    }
    return false;
  }

  std::optional<std::vector<SwitchSection>> parseSwitchSections(
      const std::vector<Token> &tokens, std::size_t begin, std::size_t end) const {
    std::vector<SwitchSection> sections;
    std::size_t cursor = begin;
    bool sawDefault = false;

    while (cursor < end) {
      if (!isSwitchLabelToken(tokens[cursor])) {
        return std::nullopt;
      }

      SwitchSection section;
      section.isDefault = tokens[cursor].text == "default";
      section.location = tokens[cursor].location;
      if (section.isDefault) {
        if (sawDefault) {
          return std::nullopt;
        }
        sawDefault = true;
      } else if (sawDefault) {
        return std::nullopt;
      }

      const std::optional<std::size_t> colon =
          findSwitchLabelColon(tokens, cursor + 1, end);
      if (!colon.has_value()) {
        return std::nullopt;
      }
      if (section.isDefault) {
        if (*colon != cursor + 1) {
          return std::nullopt;
        }
      } else {
        if (*colon == cursor + 1 ||
            hasUnsupportedExpressionToken(tokens, cursor + 1, *colon)) {
          return std::nullopt;
        }
        section.label = parseExpression(tokens, cursor + 1, *colon);
      }

      std::size_t bodyEnd = *colon + 1;
      while (bodyEnd < end) {
        if (isSwitchLabelToken(tokens[bodyEnd])) {
          break;
        }
        if (tokens[bodyEnd].kind == TokenKind::LBrace) {
          const std::optional<std::size_t> close =
              findMatching(tokens, bodyEnd, TokenKind::LBrace, TokenKind::RBrace);
          if (!close.has_value() || *close >= end) {
            return std::nullopt;
          }
          bodyEnd = *close + 1;
          continue;
        }
        ++bodyEnd;
      }
      if (hasTopLevelSwitchLabel(tokens, *colon + 1, bodyEnd)) {
        return std::nullopt;
      }

      section.body = parseStatementsInRange(tokens, *colon + 1, bodyEnd);
      if (section.body.empty() ||
          section.body.back().kind != HIRStatementKind::Break) {
        return std::nullopt;
      }
      section.body.pop_back();
      if (containsRawStatement(section.body) ||
          containsBreakOutsideLoop(section.body)) {
        return std::nullopt;
      }
      sections.push_back(std::move(section));
      cursor = bodyEnd;
    }

    return sections;
  }

  HIRExpression makeSwitchCaseCondition(const HIRExpression &selector,
                                        HIRExpression label,
                                        SourceLocation location) const {
    HIRExpression condition;
    condition.kind = HIRExpressionKind::Binary;
    condition.value = "==";
    condition.type = makeType("bool");
    condition.location = std::move(location);
    condition.children.push_back(selector);
    condition.children.push_back(std::move(label));
    return condition;
  }

  std::optional<std::vector<HIRStatement>>
  lowerSwitchSections(const HIRExpression &selector,
                      std::vector<SwitchSection> sections) const {
    std::vector<HIRStatement> elseBody;
    if (!sections.empty() && sections.back().isDefault) {
      elseBody = std::move(sections.back().body);
      sections.pop_back();
    }

    for (std::size_t reverseIndex = sections.size(); reverseIndex > 0;
         --reverseIndex) {
      SwitchSection &section = sections[reverseIndex - 1];
      if (section.isDefault) {
        return std::nullopt;
      }
      HIRStatement branch;
      branch.kind = HIRStatementKind::If;
      branch.location = section.location;
      branch.value = makeSwitchCaseCondition(selector, std::move(section.label),
                                             section.location);
      branch.body = std::move(section.body);
      branch.elseBody = std::move(elseBody);
      elseBody.clear();
      elseBody.push_back(std::move(branch));
    }

    if (elseBody.empty()) {
      return std::nullopt;
    }
    return elseBody;
  }

  bool containsRawStatement(const std::vector<HIRStatement> &body) const {
    for (const HIRStatement &statement : body) {
      if (statement.kind == HIRStatementKind::Raw) {
        return true;
      }
      if (containsRawStatement(statement.initializer) ||
          containsRawStatement(statement.update) ||
          containsRawStatement(statement.body) ||
          containsRawStatement(statement.elseBody)) {
        return true;
      }
    }
    return false;
  }

  bool containsBreakOutsideLoop(const std::vector<HIRStatement> &body,
                                std::size_t loopDepth = 0) const {
    for (const HIRStatement &statement : body) {
      if (statement.kind == HIRStatementKind::Break && loopDepth == 0) {
        return true;
      }
      const std::size_t childLoopDepth =
          statement.kind == HIRStatementKind::For ? loopDepth + 1 : loopDepth;
      if (containsBreakOutsideLoop(statement.body, childLoopDepth) ||
          containsBreakOutsideLoop(statement.elseBody, loopDepth)) {
        return true;
      }
    }
    return false;
  }

  void rewriteDoWhileContinues(std::vector<HIRStatement> &body,
                               const HIRExpression &condition) const {
    for (HIRStatement &statement : body) {
      if (statement.kind == HIRStatementKind::Continue) {
        statement = makeDoWhileContinueReplacement(condition, statement.location);
        continue;
      }
      if (statement.kind == HIRStatementKind::For) {
        continue;
      }
      if (statement.kind == HIRStatementKind::Block) {
        rewriteDoWhileContinues(statement.body, condition);
      } else if (statement.kind == HIRStatementKind::If) {
        rewriteDoWhileContinues(statement.body, condition);
        rewriteDoWhileContinues(statement.elseBody, condition);
      }
    }
  }

  std::optional<ControlConditionSpan>
  parseControlConditionSpan(const std::vector<Token> &tokens) const {
    constexpr std::size_t controlTokenIndex = 0;
    const std::size_t headerBegin = controlTokenIndex + 1;
    if (headerBegin >= tokens.size()) {
      return std::nullopt;
    }

    if (tokens[headerBegin].kind == TokenKind::LParen) {
      const std::optional<std::size_t> close =
          findMatching(tokens, headerBegin, TokenKind::LParen,
                       TokenKind::RParen);
      if (!close.has_value()) {
        return std::nullopt;
      }
      return ControlConditionSpan{headerBegin + 1, *close, *close + 1};
    }

    int parenDepth = 0;
    int bracketDepth = 0;
    for (std::size_t cursor = headerBegin; cursor < tokens.size(); ++cursor) {
      const Token &token = tokens[cursor];
      if (token.kind == TokenKind::LParen) {
        ++parenDepth;
      } else if (token.kind == TokenKind::RParen) {
        --parenDepth;
      } else if (token.kind == TokenKind::LBracket) {
        ++bracketDepth;
      } else if (token.kind == TokenKind::RBracket) {
        --bracketDepth;
      } else if (token.kind == TokenKind::LBrace && parenDepth == 0 &&
                 bracketDepth == 0) {
        if (cursor == headerBegin) {
          return std::nullopt;
        }
        return ControlConditionSpan{headerBegin, cursor, cursor};
      } else if ((token.kind == TokenKind::Semicolon ||
                  token.kind == TokenKind::RBrace) &&
                 parenDepth == 0 && bracketDepth == 0) {
        return std::nullopt;
      }
    }
    return std::nullopt;
  }

  HIRStatement makeRawFallback(HIRStatement statement) const {
    std::vector<Token> rawTokens = std::move(statement.rawTokens);
    SourceLocation location = std::move(statement.location);
    HIRStatement raw;
    raw.kind = HIRStatementKind::Raw;
    raw.rawTokens = std::move(rawTokens);
    raw.location = std::move(location);
    return raw;
  }

  std::optional<std::size_t> findToken(const std::vector<Token> &tokens,
                                       TokenKind kind, std::size_t begin) const {
    for (std::size_t i = begin; i < tokens.size(); ++i) {
      if (tokens[i].kind == kind) {
        return i;
      }
    }
    return std::nullopt;
  }

  bool isCompoundAssignmentOperator(std::string_view op) const {
    return op == "+" || op == "-" || op == "*" || op == "/" || op == "%";
  }

  bool isIncrementDecrementOperator(std::string_view op) const {
    return op == "++" || op == "--";
  }

  bool isLetMutDeclarationStart(const std::vector<Token> &tokens) const {
    return tokens.size() >= 4 &&
           tokens[0].kind == TokenKind::Identifier && tokens[0].text == "let" &&
           tokens[1].kind == TokenKind::Identifier && tokens[1].text == "mut" &&
           isNameToken(tokens[2].kind);
  }

  std::optional<HIRStatement>
  parseLetMutDeclarationStatement(const std::vector<Token> &tokens,
                                  std::size_t equal,
                                  SourceLocation statementLocation) {
    if (!isLetMutDeclarationStart(tokens) || equal != 3) {
      return std::nullopt;
    }

    HIRStatement statement;
    statement.kind = HIRStatementKind::Declaration;
    statement.location = std::move(statementLocation);
    statement.name = tokens[2].text;
    if (hasUnsupportedExpressionToken(tokens, equal + 1, tokens.size())) {
      diagnoseUnsupportedIncrementDecrementTokens(tokens, equal + 1,
                                                  tokens.size());
      return std::nullopt;
    }
    statement.value = parseExpression(tokens, equal + 1, tokens.size());
    if (statement.value.type.name.empty()) {
      diagnostics_.error(
          "sema.let-mut-inferred-type",
          "let mut declarations require an initializer with an inferable type",
          tokens[0].location);
      return std::nullopt;
    }
    statement.declaredType = statement.value.type;
    statement.declaredType.location = tokens[2].location;
    variables_[statement.name] = statement.declaredType;
    mutableLocals_.insert(statement.name);
    return statement;
  }

  std::optional<IncrementDecrementUpdate>
  parseIncrementDecrementUpdate(const std::vector<Token> &tokens) const {
    if (tokens.size() != 2) {
      return std::nullopt;
    }

    if (tokens[0].kind == TokenKind::Identifier &&
        tokens[1].kind == TokenKind::Operator &&
        isIncrementDecrementOperator(tokens[1].text)) {
      return IncrementDecrementUpdate{tokens[0].text, tokens[1].text,
                                      tokens[0].location, tokens[1].location};
    }

    if (tokens[0].kind == TokenKind::Operator &&
        isIncrementDecrementOperator(tokens[0].text) &&
        tokens[1].kind == TokenKind::Identifier) {
      return IncrementDecrementUpdate{tokens[1].text, tokens[0].text,
                                      tokens[1].location, tokens[0].location};
    }

    return std::nullopt;
  }

  std::optional<HIRStatement>
  parseIncrementDecrementStatement(const std::vector<Token> &tokens,
                                   SourceLocation statementLocation) {
    std::optional<IncrementDecrementUpdate> update =
        parseIncrementDecrementUpdate(tokens);
    if (!update.has_value()) {
      return std::nullopt;
    }

    HIRType type;
    if (auto variable = variables_.find(update->name);
        variable != variables_.end()) {
      type = variable->second;
    }

    bool valid = true;
    if (!mutableLocals_.contains(update->name)) {
      diagnostics_.error(
          "sema.increment-decrement-local",
          "increment/decrement updates require a mutable local scalar variable "
          "operand; got '" +
              update->name + "'",
          update->nameLocation);
      valid = false;
    } else if (!isScalarNumericType(type)) {
      diagnostics_.error(
          "sema.increment-decrement-operand",
          "increment/decrement updates require a scalar numeric local variable "
          "operand, got '" +
              formatType(type) + "'",
          update->nameLocation);
      valid = false;
    }

    if (!valid) {
      HIRStatement raw;
      raw.kind = HIRStatementKind::Raw;
      raw.location = statementLocation;
      raw.rawTokens = tokens;
      return raw;
    }

    HIRExpression target;
    target.kind = HIRExpressionKind::Identifier;
    target.value = update->name;
    target.location = update->nameLocation;
    target.type = type;

    HIRExpression one;
    one.kind = HIRExpressionKind::Literal;
    one.value = "1";
    one.location = update->opLocation;
    one.type = makeType("int");

    HIRExpression value;
    value.kind = HIRExpressionKind::Binary;
    value.value = update->op == "++" ? "+" : "-";
    value.location = update->opLocation;
    value.children.push_back(target);
    value.children.push_back(std::move(one));
    value.type = type;

    HIRStatement statement;
    statement.kind = HIRStatementKind::Assignment;
    statement.location = statementLocation;
    statement.target = std::move(target);
    statement.value = std::move(value);
    return statement;
  }

  void diagnoseUnsupportedIncrementDecrementTokens(
      const std::vector<Token> &tokens, std::size_t begin, std::size_t end) const {
    for (std::size_t i = begin; i < end && i < tokens.size(); ++i) {
      if (tokens[i].kind == TokenKind::Operator &&
          isIncrementDecrementOperator(tokens[i].text)) {
        diagnostics_.error(
            "sema.increment-decrement-update-form",
            "increment/decrement is only defined as a standalone update of a "
            "mutable local scalar variable; expression-valued uses are not "
            "defined",
            tokens[i].location);
        return;
      }
    }
  }

  bool hasUnsupportedExpressionToken(const std::vector<Token> &tokens,
                                     std::size_t begin,
                                     std::size_t end) const {
    for (std::size_t i = begin; i < end && i < tokens.size(); ++i) {
      if (tokens[i].kind == TokenKind::Operator &&
          isIncrementDecrementOperator(tokens[i].text)) {
        return true;
      }
    }
    return false;
  }

  std::optional<std::size_t> findMatching(const std::vector<Token> &tokens,
                                          std::size_t openIndex,
                                          TokenKind openKind,
                                          TokenKind closeKind) const {
    if (openIndex >= tokens.size() || tokens[openIndex].kind != openKind) {
      return std::nullopt;
    }
    int depth = 0;
    for (std::size_t i = openIndex; i < tokens.size(); ++i) {
      if (tokens[i].kind == openKind) {
        ++depth;
      } else if (tokens[i].kind == closeKind) {
        --depth;
        if (depth == 0) {
          return i;
        }
      }
    }
    return std::nullopt;
  }

  std::vector<std::vector<Token>> splitTopLevelSemicolons(
      const std::vector<Token> &tokens, std::size_t begin, std::size_t end) const {
    std::vector<std::vector<Token>> parts;
    std::vector<Token> currentPart;
    int parenDepth = 0;
    int bracketDepth = 0;
    for (std::size_t i = begin; i < end; ++i) {
      const Token &token = tokens[i];
      if (token.kind == TokenKind::LParen) {
        ++parenDepth;
      } else if (token.kind == TokenKind::RParen) {
        --parenDepth;
      } else if (token.kind == TokenKind::LBracket) {
        ++bracketDepth;
      } else if (token.kind == TokenKind::RBracket) {
        --bracketDepth;
      }
      if (token.kind == TokenKind::Semicolon && parenDepth == 0 &&
          bracketDepth == 0) {
        parts.push_back(std::move(currentPart));
        currentPart = {};
        continue;
      }
      currentPart.push_back(token);
    }
    parts.push_back(std::move(currentPart));
    return parts;
  }

  std::optional<std::size_t>
  findArrayDeclaratorOpen(const std::vector<Token> &tokens,
                          std::size_t closeIndex) const {
    if (closeIndex >= tokens.size() ||
        tokens[closeIndex].kind != TokenKind::RBracket) {
      return std::nullopt;
    }

    int depth = 0;
    std::size_t cursor = closeIndex + 1;
    while (cursor > 0) {
      --cursor;
      if (tokens[cursor].kind == TokenKind::RBracket) {
        ++depth;
      } else if (tokens[cursor].kind == TokenKind::LBracket) {
        --depth;
        if (depth == 0) {
          return cursor;
        }
      }
    }
    return std::nullopt;
  }

  std::string arrayDimensionText(const std::vector<Token> &tokens,
                                 std::size_t begin,
                                 std::size_t end) const {
    std::string text;
    for (std::size_t i = begin; i < end; ++i) {
      text += tokens[i].text;
    }
    return text;
  }

  std::optional<DeclarationDeclarator>
  parseDeclarationDeclarator(const std::vector<Token> &tokens,
                             std::size_t end) const {
    if (end < 2 || end > tokens.size()) {
      return std::nullopt;
    }

    std::size_t cursor = end;
    std::vector<std::string> dimensions;
    while (cursor > 0 && tokens[cursor - 1].kind == TokenKind::RBracket) {
      std::optional<std::size_t> open =
          findArrayDeclaratorOpen(tokens, cursor - 1);
      if (!open.has_value()) {
        return std::nullopt;
      }
      dimensions.insert(dimensions.begin(),
                        arrayDimensionText(tokens, *open + 1, cursor - 1));
      cursor = *open;
    }

    if (cursor < 2) {
      return std::nullopt;
    }

    const std::size_t nameIndex = cursor - 1;
    if (!isNameToken(tokens[nameIndex].kind)) {
      return std::nullopt;
    }

    for (std::size_t i = 0; i < nameIndex; ++i) {
      if (tokens[i].kind == TokenKind::Dot || tokens[i].kind == TokenKind::LParen ||
          tokens[i].kind == TokenKind::RParen || tokens[i].kind == TokenKind::Equal ||
          tokens[i].kind == TokenKind::Comma || tokens[i].kind == TokenKind::LBracket ||
          tokens[i].kind == TokenKind::RBracket) {
        return std::nullopt;
      }
    }

    HIRType type = typeFromTokens(tokens, 0, nameIndex);
    if (!knownTypeNames_.contains(baseTypeName(type)) &&
        resourceKindFromName(type.name) == HIRResourceKind::Value) {
      return std::nullopt;
    }

    for (const std::string &dimension : dimensions) {
      appendArrayDimension(type, dimension);
    }
    if (!dimensions.empty()) {
      type.location = sourceSpan(tokens.front().location, tokens[end - 1].location);
    }

    return DeclarationDeclarator{nameIndex, std::move(type)};
  }

  std::optional<DeclarationDeclarator>
  parseColonStyleVarDeclarator(const std::vector<Token> &tokens,
                               std::size_t end) const {
    if (end < 4 || end > tokens.size() || !isVarToken(tokens[0]) ||
        !isNameToken(tokens[1].kind) || tokens[2].kind != TokenKind::Colon) {
      return std::nullopt;
    }

    for (std::size_t i = 3; i < end; ++i) {
      if (tokens[i].kind == TokenKind::Dot ||
          tokens[i].kind == TokenKind::LParen ||
          tokens[i].kind == TokenKind::RParen ||
          tokens[i].kind == TokenKind::Equal ||
          tokens[i].kind == TokenKind::Semicolon) {
        return std::nullopt;
      }
    }

    HIRType type = typeFromTokens(tokens, 3, end);
    if (!knownTypeNames_.contains(baseTypeName(type)) &&
        resourceKindFromName(type.name) == HIRResourceKind::Value) {
      return std::nullopt;
    }

    return DeclarationDeclarator{1, std::move(type)};
  }

  std::vector<HIRStatement> parseStatementBody(const std::vector<Token> &tokens,
                                               std::size_t begin,
                                               std::size_t end) const {
    if (begin >= end || begin >= tokens.size()) {
      return {};
    }
    if (tokens[begin].kind == TokenKind::LBrace) {
      const std::optional<std::size_t> close =
          findMatching(tokens, begin, TokenKind::LBrace, TokenKind::RBrace);
      if (!close.has_value() || *close > end) {
        return {};
      }
      begin += 1;
      end = *close;
    }
    if (begin >= end) {
      return {};
    }
    return parseStatementsInRange(tokens, begin, end);
  }

  std::vector<HIRStatement> parseStatementsInRange(const std::vector<Token> &tokens,
                                                   std::size_t begin,
                                                   std::size_t end) const {
    std::vector<Token> bodyTokens(tokens.begin() + static_cast<std::ptrdiff_t>(begin),
                                  tokens.begin() + static_cast<std::ptrdiff_t>(end));
    return BodyParser(bodyTokens, knownTypeNames_, structs_, variables_,
                      diagnostics_, mutableLocals_)
        .parse();
  }

  std::optional<std::size_t> topLevelEqual(const std::vector<Token> &tokens) const {
    int braceDepth = 0;
    int parenDepth = 0;
    int bracketDepth = 0;
    for (std::size_t i = 0; i < tokens.size(); ++i) {
      const Token &token = tokens[i];
      if (token.kind == TokenKind::LBrace) {
        ++braceDepth;
      } else if (token.kind == TokenKind::RBrace) {
        --braceDepth;
      } else if (token.kind == TokenKind::LParen) {
        ++parenDepth;
      } else if (token.kind == TokenKind::RParen) {
        --parenDepth;
      } else if (token.kind == TokenKind::LBracket) {
        ++bracketDepth;
      } else if (token.kind == TokenKind::RBracket) {
        --bracketDepth;
      } else if (token.kind == TokenKind::Equal && braceDepth == 0 &&
                 parenDepth == 0 && bracketDepth == 0) {
        return i;
      }
    }
    return std::nullopt;
  }

  HIRExpression parseExpression(const std::vector<Token> &tokens, std::size_t begin,
                                std::size_t end) const {
    if (begin >= end) {
      return {};
    }
    std::vector<Token> expressionTokens(tokens.begin() + static_cast<std::ptrdiff_t>(begin),
                                        tokens.begin() + static_cast<std::ptrdiff_t>(end));
    return ExpressionParser(std::move(expressionTokens), knownTypeNames_, structs_,
                            variables_, &diagnostics_)
        .parse();
  }

  const std::vector<Token> &tokens_;
  const std::set<std::string> &knownTypeNames_;
  const std::unordered_map<std::string, HIRStruct> &structs_;
  std::unordered_map<std::string, HIRType> variables_;
  DiagnosticEngine &diagnostics_;
  std::set<std::string> mutableLocals_;
  std::size_t index_ = 0;
};

HIRResource convertResource(const ResourceDecl &resource, std::size_t set,
                            std::size_t binding) {
  HIRResource hir;
  hir.kind = resourceKindFromName(resource.type.name);
  hir.type = stripTypeQualifier(convertType(resource.type));
  hir.name = resource.name;
  hir.set = set;
  hir.binding = binding;
  hir.explicitSet = resource.set.has_value();
  hir.explicitBinding = resource.binding.has_value();
  if (resource.storageImageAccessQualifier == "readonly") {
    hir.storageImageAccess = HIRStorageImageAccess::ReadOnly;
  } else if (resource.storageImageAccessQualifier == "writeonly") {
    hir.storageImageAccess = HIRStorageImageAccess::WriteOnly;
  } else if (resource.storageImageAccessQualifier == "readwrite") {
    hir.storageImageAccess = HIRStorageImageAccess::ReadWrite;
  }
  hir.storageImageFormat = resource.storageImageFormat;
  hir.declarationSpan = resource.declarationSpan;
  hir.nameSpan = resource.nameSpan;
  hir.layoutSpan = resource.layoutSpan;
  hir.setSpan = resource.setSpan;
  hir.bindingSpan = resource.bindingSpan;
  return hir;
}

HIRResource convertCBufferResource(const StructDecl &cbuffer, std::size_t set,
                                   std::size_t binding) {
  HIRResource hir;
  hir.kind = HIRResourceKind::Uniform;
  hir.type = HIRType{cbuffer.name, std::nullopt, cbuffer.nameSpan};
  hir.name = cbuffer.name;
  hir.set = set;
  hir.binding = binding;
  hir.declarationSpan = cbuffer.declarationSpan;
  hir.nameSpan = cbuffer.nameSpan;
  return hir;
}

std::unordered_map<std::string, HIRType>
collectCBufferFieldTypes(const std::vector<StructDecl> &cbuffers,
                         DiagnosticEngine &diagnostics) {
  std::unordered_map<std::string, HIRType> fieldTypes;
  for (const StructDecl &cbuffer : cbuffers) {
    for (const StructField &field : cbuffer.fields) {
      auto [_, inserted] = fieldTypes.emplace(field.name, convertType(field.type));
      if (!inserted) {
        diagnostics.error("sema.duplicate-cbuffer-field",
                          "duplicate cbuffer field '" + field.name +
                              "' is ambiguous when referenced without a block name",
                          field.location);
      }
    }
  }
  return fieldTypes;
}

HIRExpression parseExpressionTokens(
    const std::vector<Token> &tokens, const std::set<std::string> &knownTypeNames,
    const std::unordered_map<std::string, HIRStruct> &structs,
    const std::unordered_map<std::string, HIRType> &variables,
    DiagnosticEngine *diagnostics = nullptr) {
  return ExpressionParser(tokens, knownTypeNames, structs, variables,
                          diagnostics)
      .parse();
}

HIRConstant convertConstant(
    const ConstantDecl &constant, const std::set<std::string> &knownTypeNames,
    const std::unordered_map<std::string, HIRStruct> &structs,
    const std::unordered_map<std::string, HIRType> &constantTypes,
    const HIRScalarConstantMap &constantValues,
    DiagnosticEngine &diagnostics) {
  HIRConstant hir;
  hir.type = convertType(constant.type);
  hir.name = constant.name;
  hir.value = parseExpressionTokens(constant.valueTokens, knownTypeNames, structs,
                                    constantTypes, &diagnostics);
  hir.value.type = hir.type;
  hir.foldedValue = foldExpressionToString(hir.value, constantValues);
  return hir;
}

std::string resolveWorkgroupComponent(
    const std::vector<Token> &tokens, std::string fallback,
    const std::set<std::string> &knownTypeNames,
    const std::unordered_map<std::string, HIRStruct> &structs,
    const std::unordered_map<std::string, HIRType> &constantTypes,
    const HIRScalarConstantMap &constantValues) {
  if (tokens.empty()) {
    return fallback;
  }
  HIRExpression expression =
      parseExpressionTokens(tokens, knownTypeNames, structs, constantTypes);
  if (std::optional<std::string> folded =
          foldExpressionToString(expression, constantValues)) {
    return *folded;
  }
  return fallback;
}

HIRWorkgroupSize convertWorkgroupSize(
    const WorkgroupSizeDecl &layout, const std::set<std::string> &knownTypeNames,
    const std::unordered_map<std::string, HIRStruct> &structs,
    const std::unordered_map<std::string, HIRType> &constantTypes,
    const HIRScalarConstantMap &constantValues) {
  HIRWorkgroupSize size;
  size.sourceX = layout.x;
  size.sourceY = layout.y;
  size.sourceZ = layout.z;
  size.x = resolveWorkgroupComponent(layout.xTokens, layout.x, knownTypeNames,
                                     structs, constantTypes, constantValues);
  size.y = resolveWorkgroupComponent(layout.yTokens, layout.y, knownTypeNames,
                                     structs, constantTypes, constantValues);
  size.z = resolveWorkgroupComponent(layout.zTokens, layout.z, knownTypeNames,
                                     structs, constantTypes, constantValues);
  return size;
}

HIRFunction convertFunction(
    const FunctionDecl &function, const std::set<std::string> &knownTypeNames,
    const std::unordered_map<std::string, HIRStruct> &structs,
    const std::vector<HIRResource> &resources,
    std::string_view stage,
    const std::unordered_map<std::string, HIRType> &constantTypes,
    const std::unordered_map<std::string, HIRType> &cbufferFieldTypes,
    DiagnosticEngine &diagnostics) {
  HIRFunction hir;
  hir.returnType = convertType(function.returnType);
  hir.name = function.name;
  hir.bodyTokens = function.bodyTokens;
  hir.declarationSpan = function.location;
  hir.nameSpan = function.location;

  std::unordered_map<std::string, HIRType> variables;
  for (const auto &[name, type] : constantTypes) {
    variables[name] = type;
  }
  for (const auto &[name, type] : cbufferFieldTypes) {
    variables[name] = type;
  }
  for (const HIRResource &resource : resources) {
    variables[resource.name] = resource.type;
  }
  addComputeInvocationBuiltinTypes(variables, stage);
  for (const Parameter &parameter : function.parameters) {
    HIRParameter hirParameter{convertType(parameter.type), parameter.name,
                              parameter.location};
    variables[hirParameter.name] = hirParameter.type;
    hir.parameters.push_back(std::move(hirParameter));
  }

  hir.body =
      BodyParser(function.bodyTokens, knownTypeNames, structs,
                 std::move(variables), diagnostics)
          .parse();
  return hir;
}

void validateLocalArrayDeclaration(
    const HIRStatement &statement,
    std::string_view functionContext,
    const std::unordered_map<std::string, HIRType> &constantTypes,
    const HIRScalarConstantMap &constantValues,
    DiagnosticEngine &diagnostics) {
  if (statement.kind != HIRStatementKind::Declaration ||
      !statement.declaredType.arraySize.has_value()) {
    return;
  }

  const std::string &arraySize = *statement.declaredType.arraySize;
  if (!arraySize.empty() &&
      isResolvedFixedArraySize(arraySize, constantTypes, constantValues)) {
    return;
  }

  diagnostics.error(
      "sema.array-size",
      "array size for local declaration '" + statement.name + "' in " +
          std::string(functionContext) +
          " must use positive integer literals and pure folded top-level "
          "int/uint constant expressions for every fixed dimension, got '" +
          (arraySize.empty() ? std::string("[]") : arraySize) + "'",
      statement.declaredType.location);
}

void validateStatementLocalArrayDeclarations(
    const std::vector<HIRStatement> &statements,
    std::string_view functionContext,
    const std::unordered_map<std::string, HIRType> &constantTypes,
    const HIRScalarConstantMap &constantValues,
    DiagnosticEngine &diagnostics) {
  for (const HIRStatement &statement : statements) {
    validateLocalArrayDeclaration(statement, functionContext, constantTypes,
                                  constantValues, diagnostics);
    validateStatementLocalArrayDeclarations(statement.initializer, functionContext,
                                            constantTypes, constantValues,
                                            diagnostics);
    validateStatementLocalArrayDeclarations(statement.update, functionContext,
                                            constantTypes, constantValues,
                                            diagnostics);
    validateStatementLocalArrayDeclarations(statement.body, functionContext,
                                            constantTypes, constantValues,
                                            diagnostics);
    validateStatementLocalArrayDeclarations(statement.elseBody, functionContext,
                                            constantTypes, constantValues,
                                            diagnostics);
  }
}

void validateFunctionLocalArrayDeclarations(
    const HIRFunction &function,
    std::string_view functionContext,
    const std::unordered_map<std::string, HIRType> &constantTypes,
    const HIRScalarConstantMap &constantValues,
    DiagnosticEngine &diagnostics) {
  validateStatementLocalArrayDeclarations(function.body, functionContext,
                                          constantTypes, constantValues,
                                          diagnostics);
}

void validateFunctionTypes(const HIRFunction &function,
                           const std::set<std::string> &structNames,
                           DiagnosticEngine &diagnostics,
                           std::string_view functionLabel,
                           SourceLocation returnLocation) {
  if (!isKnownType(function.returnType, structNames)) {
    diagnostics.warning("sema.unknown-return-type",
                        "unknown return type '" + function.returnType.name +
                            "' for " + std::string(functionLabel),
                        returnLocation);
  }
  for (const HIRParameter &parameter : function.parameters) {
    if (!isKnownType(parameter.type, structNames)) {
      diagnostics.warning("sema.unknown-parameter-type",
                          "unknown parameter type '" + parameter.type.name +
                              "' for " + std::string(functionLabel),
                          parameter.type.location);
    }
  }
}

bool stageAllowsTextureSampling(std::string_view stage) {
  return stage.empty() || stage == "vertex" || stage == "fragment" ||
         stage == "compute";
}

void validateTextureSampleExpression(const HIRExpression &expression,
                                     std::string_view stage,
                                     DiagnosticEngine &diagnostics) {
  if (expression.kind == HIRExpressionKind::TextureSample) {
    const bool explicitLod = isExplicitLodTextureSample(expression.value);
    bool valid = true;
    if (!stageAllowsTextureSampling(stage)) {
      diagnostics.error("sema.texture-sample-stage",
                        "texture sampling is not legal in stage '" +
                            std::string(stage) + "'",
                        expression.location);
      valid = false;
    }

    const bool validArity =
        explicitLod ? (expression.children.size() == 3 ||
                       expression.children.size() == 4)
                    : (expression.children.size() == 2 ||
                       expression.children.size() == 3);
    if (!validArity) {
      diagnostics.error("sema.texture-sample-arity",
                        explicitLod
                            ? "textureLod expects texture, coordinates, and "
                              "lod or texture, sampler, coordinates, and lod; got " +
                                  std::to_string(expression.children.size()) +
                                  " operand(s)"
                            : "texture sample expects either texture and "
                              "coordinates or texture, sampler, and coordinates; got " +
                            std::to_string(expression.children.size()) +
                                  " operand(s)",
                        expression.location);
      valid = false;
    }

    if (!expression.children.empty() &&
        !expression.children.front().type.name.empty() &&
        !isTextureType(expression.children.front().type)) {
      diagnostics.error("sema.texture-sample-texture",
                        "texture sample first operand must be a texture, got '" +
                            formatType(expression.children.front().type) + "'",
                        expression.children.front().location);
      valid = false;
    }

    if (!expression.children.empty() &&
        isShadowTextureType(expression.children.front().type)) {
      diagnostics.error("sema.texture-sample-shadow",
                        "comparison texture '" +
                            formatType(expression.children.front().type) +
                            "' must be sampled with textureCompare",
                        expression.children.front().location);
      valid = false;
    }

    const bool hasExplicitSampler =
        validArity &&
        textureSampleHasExplicitSampler(expression.children.size(), explicitLod);
    if (hasExplicitSampler &&
        !expression.children[1].type.name.empty() &&
        !isRawSamplerType(expression.children[1].type)) {
      diagnostics.error("sema.texture-sample-sampler",
                        "texture sample second operand must be a raw sampler "
                        "in the explicit sampler form, got '" +
                            formatType(expression.children[1].type) + "'",
                        expression.children[1].location);
      valid = false;
    }

    if (validArity) {
      const HIRExpression &texture = expression.children[0];
      const HIRExpression &coordinates =
          expression.children[textureSampleCoordinateIndex(expression.children.size(),
                                                          explicitLod)];
      const std::size_t expectedComponents =
          expectedTextureCoordinateComponents(texture.type);
      if (expectedComponents != 0 && !coordinates.type.name.empty()) {
        const std::optional<std::size_t> actualComponents =
            vectorComponentCount(coordinates.type);
        if (!actualComponents || *actualComponents != expectedComponents) {
          diagnostics.error(
              "sema.texture-sample-coordinates",
              "texture sample coordinates for '" + formatType(texture.type) +
                  "' must be vec" + std::to_string(expectedComponents) +
                  ", got '" + formatType(coordinates.type) + "'",
              coordinates.location);
          valid = false;
        }
      }
    }

    const std::optional<std::size_t> lodIndex =
        validArity ? textureSampleLodIndex(expression.children.size(), explicitLod)
                   : std::nullopt;
    if (lodIndex.has_value() && !expression.children[*lodIndex].type.name.empty() &&
        !isScalarNumericType(expression.children[*lodIndex].type)) {
      diagnostics.error("sema.texture-sample-lod",
                        "textureLod lod operand must be a scalar numeric value, got '" +
                            formatType(expression.children[*lodIndex].type) + "'",
                        expression.children[*lodIndex].location);
      valid = false;
    }

    const HIRType expectedResult =
        !expression.children.empty()
            ? textureSampleResultType(expression.children.front().type)
            : HIRType{};
    if (valid && !expectedResult.name.empty() &&
        (expression.type.name != expectedResult.name ||
         expression.type.arraySize != expectedResult.arraySize)) {
      diagnostics.error("sema.texture-sample-result",
                        "texture sample result for '" +
                            formatType(expression.children.front().type) +
                            "' must be '" + formatType(expectedResult) +
                            "', got '" + formatType(expression.type) + "'",
                        expression.location);
    }
  }

  for (const HIRExpression &child : expression.children) {
    validateTextureSampleExpression(child, stage, diagnostics);
  }
}

bool validateManualTextureCompareKernelTaps(
    const std::vector<ManualTextureCompareKernelTap> &taps,
    std::string_view kernelName, DiagnosticEngine &diagnostics) {
  bool valid = true;
  for (std::size_t index = 0; index < taps.size(); ++index) {
    const HIRExpression *offset = taps[index].offset;
    const HIRExpression *weight = taps[index].weight;
    if (offset == nullptr || weight == nullptr) {
      valid = false;
      continue;
    }
    if (!offset->type.name.empty() &&
        (baseTypeName(offset->type) != "ivec2" ||
         offset->type.arraySize.has_value())) {
      diagnostics.error("sema.texture-compare-kernel-offset",
                        std::string(kernelName) + " offset operand " +
                            std::to_string(index) +
                            " must be ivec2, got '" +
                            formatType(offset->type) + "'",
                        offset->location);
      valid = false;
    } else if (!offset->type.name.empty() &&
               !isStaticIvec2OffsetExpression(*offset)) {
      diagnostics.error(
          "sema.texture-compare-kernel-offset-static",
          std::string(kernelName) + " offset operand " +
              std::to_string(index) +
              " must be a static ivec2 integer literal constructor",
          offset->location);
      valid = false;
    }
    if (!weight->type.name.empty() && !isScalarNumericType(weight->type)) {
      diagnostics.error("sema.texture-compare-kernel-weight",
                        std::string(kernelName) + " weight operand " +
                            std::to_string(index) +
                            " must be a scalar numeric value, got '" +
                            formatType(weight->type) + "'",
                        weight->location);
      valid = false;
    }
  }
  return valid;
}

std::string formatManualKernelWeightSum(double value) {
  std::ostringstream out;
  out << std::setprecision(12) << value;
  return out.str();
}

void diagnoseManualTextureCompareKernelWeights(
    const HIRExpression &expression, DiagnosticEngine &diagnostics) {
  const std::optional<ManualTextureCompareKernelWeightSummary> summary =
      manualTextureCompareKernelWeightSummary(expression);
  if (!summary.has_value() || !summary->allWeightsStatic) {
    return;
  }
  if (summary->zeroSum) {
    diagnostics.warning(
        "sema.texture-compare-kernel-weight-zero-sum",
        expression.value +
            " literal weights sum to zero; the compiler preserves exact user "
            "weights and does not normalize manual shadow kernels",
        expression.location);
    return;
  }
  if (!summary->normalized) {
    diagnostics.warning(
        "sema.texture-compare-kernel-weight-not-normalized",
        expression.value + " literal weights sum to " +
            formatManualKernelWeightSum(summary->sum) +
            "; the compiler preserves exact user weights and does not "
            "normalize manual shadow kernels",
        expression.location);
  }
}

void validateTextureCompareExpression(const HIRExpression &expression,
                                      std::string_view stage,
                                      DiagnosticEngine &diagnostics) {
  if (expression.kind == HIRExpressionKind::TextureCompare ||
      expression.kind == HIRExpressionKind::TextureCompareLodManual) {
    const bool explicitLod = isExplicitLodTextureCompare(expression.value);
    const bool manualLod = isManualLodTextureCompare(expression.value);
    const bool manualOffsetLod =
        isManualOffsetLodTextureCompare(expression.value);
    const bool manualGather2x2Lod =
        isManualGather2x2LodTextureCompare(expression.value);
    const bool manualKernelListLod =
        isManualKernelListLodTextureCompare(expression.value);
    const bool manualKernel4Lod =
        isManualKernel4LodTextureCompare(expression.value);
    const bool manualKernel8Lod =
        isManualKernel8LodTextureCompare(expression.value);
    const std::optional<std::size_t> manualKernelTapCount =
        manualKernelTextureCompareTapCount(expression.value);
    const std::string functionName =
        textureCompareFunctionName(expression.value);
    bool valid = true;
    if (!stageAllowsTextureSampling(stage)) {
      diagnostics.error("sema.texture-compare-stage",
                        "texture comparison sampling is not legal in stage '" +
                            std::string(stage) + "'",
                        expression.location);
      valid = false;
    }

    const std::size_t expectedArguments =
        expectedTextureCompareArgumentCount(expression.value);
    if (expression.children.size() != expectedArguments) {
      const std::string message =
          manualOffsetLod
              ? "textureCompareLodManualOffset expects texture, raw sampler, "
                "coordinates, depth, lod, compareOp, and ivec2 offset; got " +
                    std::to_string(expression.children.size()) + " operand(s)"
          : manualGather2x2Lod
              ? "textureCompareLodManualGather2x2 expects texture, raw "
                "sampler, coordinates, depth, lod, and compareOp; got " +
                    std::to_string(expression.children.size()) + " operand(s)"
          : manualKernelListLod
              ? "textureCompareLodManualKernel expects texture, raw sampler, "
                "coordinates, depth, lod, compareOp, and a "
                "textureCompareKernel tap list; got " +
                    std::to_string(expression.children.size()) + " operand(s)"
          : manualKernel4Lod
              ? "textureCompareLodManualKernel4 expects texture, raw sampler, "
                "coordinates, depth, lod, compareOp, and four ivec2/weight "
                "tap pairs; got " +
                    std::to_string(expression.children.size()) + " operand(s)"
          : manualKernel8Lod
              ? "textureCompareLodManualKernel8 expects texture, raw sampler, "
                "coordinates, depth, lod, compareOp, and eight ivec2/weight "
                "tap pairs; got " +
                    std::to_string(expression.children.size()) + " operand(s)"
          : manualLod
              ? "textureCompareLodManual expects texture, raw sampler, "
                "coordinates, depth, lod, and compareOp; got " +
                    std::to_string(expression.children.size()) + " operand(s)"
          : explicitLod
              ? "textureCompareLod expects texture, sampler, coordinates, "
                "depth, and lod; got " +
                    std::to_string(expression.children.size()) + " operand(s)"
              : "textureCompare expects texture, sampler, coordinates, and "
                "depth; got " +
                    std::to_string(expression.children.size()) + " operand(s)";
      diagnostics.error("sema.texture-compare-arity", message,
                        expression.location);
      valid = false;
    }

    if (!expression.children.empty() &&
        !expression.children.front().type.name.empty() &&
        !isShadowTextureType(expression.children.front().type)) {
      diagnostics.error(
          "sema.texture-compare-texture",
          functionName + " first operand must be a comparison texture, got '" +
              formatType(expression.children.front().type) + "'",
          expression.children.front().location);
      valid = false;
    }

    if ((manualOffsetLod || manualGather2x2Lod ||
         manualKernelListLod || manualKernelTapCount.has_value()) &&
        !expression.children.empty() &&
        !expression.children.front().type.name.empty() &&
        isShadowTextureType(expression.children.front().type) &&
        !isManualCompareOffsetTextureType(expression.children.front().type)) {
      const std::string diagnostic =
          manualOffsetLod
              ? "sema.texture-compare-offset-texture"
              : manualGather2x2Lod ? "sema.texture-compare-gather-texture"
                                   : "sema.texture-compare-kernel-texture";
      const std::string operation =
          manualOffsetLod
              ? "offset sampling"
              : manualGather2x2Lod ? "2x2 gather sampling"
                                   : "kernel sampling";
      diagnostics.error(diagnostic,
                        functionName + " supports " + operation + " only for "
                            "sampler2DShadow and sampler2DArrayShadow "
                            "textures, got '" +
                            formatType(expression.children.front().type) + "'",
                        expression.children.front().location);
      valid = false;
    }

    if (expression.children.size() > 1 &&
        !expression.children[1].type.name.empty()) {
      const bool validSampler = manualLod
                                    ? isRawSamplerType(expression.children[1].type)
                                    : isSamplerType(expression.children[1].type);
      if (!validSampler) {
        diagnostics.error(
            "sema.texture-compare-sampler",
            functionName +
                (manualLod
                     ? " second operand must be a raw sampler, got '"
                     : " second operand must be a sampler or "
                       "comparison_sampler, got '") +
                formatType(expression.children[1].type) + "'",
            expression.children[1].location);
        valid = false;
      }
    }

    if (expression.children.size() > 2 && !expression.children[2].type.name.empty()) {
      const std::size_t expectedComponents =
          expression.children.empty()
              ? 0
              : expectedTextureCoordinateComponents(expression.children[0].type);
      const std::optional<std::size_t> actualComponents =
          vectorComponentCount(expression.children[2].type);
      if (expectedComponents != 0 &&
          (!actualComponents || *actualComponents != expectedComponents)) {
        diagnostics.error(
            "sema.texture-compare-coordinates",
            functionName + " coordinates for '" +
                formatType(expression.children[0].type) + "' must be vec" +
                std::to_string(expectedComponents) + ", got '" +
                formatType(expression.children[2].type) + "'",
            expression.children[2].location);
        valid = false;
      }
    }

    if (expression.children.size() > 3 &&
        !expression.children[3].type.name.empty() &&
        !isScalarNumericType(expression.children[3].type)) {
      diagnostics.error(
          "sema.texture-compare-depth",
          functionName + " depth operand must be a scalar numeric value, got '" +
              formatType(expression.children[3].type) + "'",
          expression.children[3].location);
      valid = false;
    }

    const std::optional<std::size_t> lodIndex =
        textureCompareLodIndex(expression.children.size(), expression.value);
    if (lodIndex.has_value() && !expression.children[*lodIndex].type.name.empty() &&
        !isScalarNumericType(expression.children[*lodIndex].type)) {
      diagnostics.error(
          "sema.texture-compare-lod",
          functionName + " lod operand must be a scalar numeric value, got '" +
              formatType(expression.children[*lodIndex].type) + "'",
          expression.children[*lodIndex].location);
      valid = false;
    }

    const std::optional<std::size_t> compareOpIndex =
        textureCompareManualCompareOpIndex(expression.children.size(),
                                          expression.value);
    if (compareOpIndex.has_value()) {
      const HIRExpression &compareOp = expression.children[*compareOpIndex];
      if (compareOp.kind != HIRExpressionKind::Identifier ||
          !compareOp.type.name.empty() || compareOp.type.arraySize.has_value() ||
          !isManualTextureCompareOpName(compareOp.value)) {
        const std::string got =
            compareOp.value.empty() ? expressionKindName(compareOp.kind)
                                    : compareOp.value;
        diagnostics.error(
            "sema.texture-compare-compare-op",
            functionName +
                " compareOp operand must be a symbolic "
            "identifier naming one of " +
                manualTextureCompareOpList() + "; got '" + got + "'",
            compareOp.location);
        valid = false;
      }
    }

    const std::optional<std::size_t> offsetIndex =
        textureCompareManualOffsetIndex(expression.children.size(),
                                        expression.value);
    if (offsetIndex.has_value()) {
      const HIRExpression &offset = expression.children[*offsetIndex];
      if (!offset.type.name.empty() &&
          (baseTypeName(offset.type) != "ivec2" ||
           offset.type.arraySize.has_value())) {
        diagnostics.error(
            "sema.texture-compare-offset",
            "textureCompareLodManualOffset offset operand must be ivec2, got '" +
                formatType(offset.type) + "'",
            offset.location);
        valid = false;
      } else if (!offset.type.name.empty() &&
                 !isStaticIvec2OffsetExpression(offset)) {
        diagnostics.error(
            "sema.texture-compare-offset-static",
            "textureCompareLodManualOffset offset operand must be a static "
            "ivec2 integer literal constructor",
            offset.location);
        valid = false;
      }
    }

    bool manualKernelListShapeValid = true;
    if (manualKernelListLod &&
        expression.children.size() == expectedTextureCompareArgumentCount(
                                          expression.value)) {
      const HIRExpression &kernelList = expression.children[6];
      const ManualTextureCompareKernelListShape listShape =
          manualTextureCompareKernelListShape(kernelList);
      if (listShape != ManualTextureCompareKernelListShape::Valid) {
        switch (listShape) {
        case ManualTextureCompareKernelListShape::NotTextureCompareKernelCall:
          diagnostics.error(
              "sema.texture-compare-kernel-list-builder",
              "textureCompareLodManualKernel tap list must be a "
              "textureCompareKernel(...) call",
              kernelList.location);
          break;
        case ManualTextureCompareKernelListShape::Empty:
          diagnostics.error(
              "sema.texture-compare-kernel-list-empty",
              "textureCompareLodManualKernel tap list must contain at least "
              "one ivec2/weight pair",
              kernelList.location);
          break;
        case ManualTextureCompareKernelListShape::OddOperandCount:
          diagnostics.error(
              "sema.texture-compare-kernel-list-pairs",
              "textureCompareLodManualKernel tap list must contain complete "
              "ivec2/weight pairs",
              kernelList.location);
          break;
        case ManualTextureCompareKernelListShape::TooManyTaps:
          diagnostics.error(
              "sema.texture-compare-kernel-list-size",
              "textureCompareLodManualKernel tap list supports at most " +
                  std::to_string(kMaxManualTextureCompareKernelTaps) +
                  " taps",
              kernelList.location);
          break;
        case ManualTextureCompareKernelListShape::Valid:
          break;
        }
        manualKernelListShapeValid = false;
        valid = false;
      }
    }

    if ((manualKernelTapCount.has_value() || manualKernelListLod) &&
        manualKernelListShapeValid &&
        expression.children.size() == expectedTextureCompareArgumentCount(
                                          expression.value)) {
      const std::optional<std::vector<ManualTextureCompareKernelTap>> taps =
          manualTextureCompareKernelTaps(expression);
      if (taps.has_value()) {
        if (!validateManualTextureCompareKernelTaps(*taps, expression.value,
                                                    diagnostics)) {
          valid = false;
        } else {
          diagnoseManualTextureCompareKernelWeights(expression, diagnostics);
        }
      }
    }

    if (valid && (expression.type.name != "float" ||
                  expression.type.arraySize.has_value())) {
      diagnostics.error("sema.texture-compare-result",
                        functionName + " result must be float, got '" +
                            formatType(expression.type) + "'",
                        expression.location);
    }
  }

  for (const HIRExpression &child : expression.children) {
    validateTextureCompareExpression(child, stage, diagnostics);
  }
}

const HIRResource *storageImageOperandResource(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRResource> &resources) {
  auto unwrapTransparentExpression = [](const HIRExpression &expression) {
    const HIRExpression *current = &expression;
    while ((current->kind == HIRExpressionKind::Group ||
            current->kind == HIRExpressionKind::NonUniform) &&
           current->children.size() == 1) {
      current = &current->children.front();
    }
    return current;
  };

  const HIRExpression *current = unwrapTransparentExpression(expression);
  while (current->kind == HIRExpressionKind::IndexAccess &&
         !current->children.empty()) {
    current = unwrapTransparentExpression(current->children.front());
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

void validateImageAccessExpression(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRResource> &resources,
    DiagnosticEngine &diagnostics) {
  if (expression.kind == HIRExpressionKind::Call &&
      isImageAccessCallName(expression.value)) {
    const bool load = isImageLoadCallName(expression.value);
    const bool store = isImageStoreCallName(expression.value);
    const bool atomic = isImageAtomicCallName(expression.value);
    const std::size_t expectedArity = load ? 2 : 3;
    const std::string operation = expression.value;
    bool valid = true;

    if (expression.children.size() != expectedArity) {
      diagnostics.error(
          load ? "sema.image-load-arity"
               : atomic ? "sema.storage-image-atomic-arity"
                        : "sema.image-store-arity",
          operation + " expects " +
              (load ? std::string("storage image and coordinates")
                    : std::string("storage image, coordinates, and value")) +
              "; got " + std::to_string(expression.children.size()) +
              " operand(s)",
          expression.location);
      valid = false;
    }

    const HIRExpression *image = expression.children.empty()
                                     ? nullptr
                                     : &expression.children.front();
    const bool concreteImage =
        image != nullptr && !image->type.name.empty();
    const bool storageImage = concreteImage && isStorageImageType(image->type);
    if (concreteImage && !storageImage) {
      diagnostics.error(
          load ? "sema.image-load-image"
               : atomic ? "sema.storage-image-atomic-image"
                        : "sema.image-store-image",
          operation + " first operand must be a storage image, got '" +
              formatType(image->type) + "'",
          image->location);
      valid = false;
    }

    if (atomic && storageImage && image != nullptr &&
        !isStorageImageAtomicImageType(image->type)) {
      diagnostics.error(
          "sema.storage-image-atomic-image-type",
          operation +
              " first operand must be a signed or unsigned integer storage "
          "image, got '" +
              formatType(image->type) + "'",
          image->location);
      valid = false;
    }

    if (storageImage && image != nullptr) {
      if (const HIRResource *resource =
              storageImageOperandResource(*image, resources)) {
        if (load &&
            !storageImageAccessAllowsRead(resource->storageImageAccess)) {
          diagnostics.error(
              "sema.storage-image-write-only-load",
              "imageLoad cannot read from write-only storage image '" +
                  resource->name + "'",
              image->location);
          valid = false;
        } else if (store &&
                   !storageImageAccessAllowsWrite(
                       resource->storageImageAccess)) {
          diagnostics.error(
              "sema.storage-image-read-only-store",
              "imageStore cannot write to read-only storage image '" +
                  resource->name + "'",
              image->location);
          valid = false;
        } else if (atomic &&
                   (!storageImageAccessAllowsRead(
                        resource->storageImageAccess) ||
                    !storageImageAccessAllowsWrite(
                        resource->storageImageAccess))) {
          diagnostics.error(
              "sema.storage-image-atomic-access",
              operation +
                  " requires read-write storage image '" + resource->name +
                  "'",
              image->location);
          valid = false;
        }

        if (atomic && isStorageImageAtomicImageType(image->type)) {
          const std::string format = resolvedStorageImageFormatName(*resource);
          if (!storageImageFormatSupportsAtomics(format,
                                                 baseTypeName(image->type))) {
            const std::string expectedFormat =
                storageImageAtomicExpectedFormatName(image->type);
            diagnostics.error(
                "sema.storage-image-atomic-format",
                operation + " requires format '" + expectedFormat +
                    "' for storage image '" + resource->name + "', got '" +
                    format + "'",
                image->location);
            valid = false;
          }
        }
      }
    }

    if (expression.children.size() > 1 && storageImage) {
      const HIRType expectedCoordinates =
          storageImageCoordinateType(image->type);
      const HIRExpression &coordinates = expression.children[1];
      if (!coordinates.type.name.empty() &&
          !sameType(coordinates.type, expectedCoordinates)) {
        diagnostics.error(
            load ? "sema.image-load-coordinates"
                 : atomic ? "sema.storage-image-atomic-coordinates"
                          : "sema.image-store-coordinates",
            operation + " coordinates for '" + formatType(image->type) +
                "' must be '" + formatType(expectedCoordinates) + "', got '" +
                formatType(coordinates.type) + "'",
            coordinates.location);
        valid = false;
      }
    }

    if (store && expression.children.size() > 2 && storageImage) {
      const HIRType expectedValue = storageImagePayloadVectorType(image->type);
      const HIRExpression &value = expression.children[2];
      if (!value.type.name.empty() && !sameType(value.type, expectedValue)) {
        diagnostics.error(
            "sema.image-store-value",
            "imageStore value for '" + formatType(image->type) +
                "' must be '" + formatType(expectedValue) + "', got '" +
                formatType(value.type) + "'",
            value.location);
        valid = false;
      }
    }

    if (atomic && expression.children.size() > 2 && storageImage &&
        isStorageImageAtomicImageType(image->type)) {
      const HIRType expectedValue = storageImageAtomicPayloadType(image->type);
      const HIRExpression &value = expression.children[2];
      if (!value.type.name.empty() && !sameType(value.type, expectedValue)) {
        diagnostics.error(
            "sema.storage-image-atomic-value",
            operation + " value for '" + formatType(image->type) +
                "' must be '" + formatType(expectedValue) + "', got '" +
                formatType(value.type) + "'",
            value.location);
        valid = false;
      }
    }

    if (valid && storageImage) {
      if (load) {
        const HIRType expectedResult =
            imageLoadResultType(image->type, expression.location);
        if (!sameType(expression.type, expectedResult)) {
          diagnostics.error(
              "sema.image-load-result",
              "imageLoad result for '" + formatType(image->type) +
                  "' must be '" + formatType(expectedResult) + "', got '" +
                  formatType(expression.type) + "'",
              expression.location);
        }
      } else if (store && !isVoidType(expression.type)) {
        diagnostics.error(
            "sema.image-store-result",
            "imageStore result must be void, got '" +
                formatType(expression.type) + "'",
            expression.location);
      } else if (atomic && isStorageImageAtomicImageType(image->type)) {
        const HIRType expectedResult =
            imageAtomicResultType(image->type, expression.location);
        if (!sameType(expression.type, expectedResult)) {
          diagnostics.error(
              "sema.storage-image-atomic-result",
              operation + " result for '" + formatType(image->type) +
                  "' must be '" + formatType(expectedResult) + "', got '" +
                  formatType(expression.type) + "'",
              expression.location);
        }
      }
    }
  }

  for (const HIRExpression &child : expression.children) {
    validateImageAccessExpression(child, resources, diagnostics);
  }
}

void validateVectorSwizzleExpression(const HIRExpression &expression,
                                     DiagnosticEngine &diagnostics) {
  if (expression.kind == HIRExpressionKind::MemberAccess &&
      !expression.children.empty()) {
    const HIRType &baseType = expression.children.front().type;
    if (isVectorType(baseTypeName(baseType)) &&
        !swizzleComponentIndices(baseType, expression.value).has_value()) {
      diagnostics.error("sema.invalid-swizzle",
                        "invalid vector swizzle '" + expression.value +
                            "' for type '" + formatType(baseType) +
                            "'; use components from one of xyzw, rgba, or stpq "
                            "within the vector width",
                        expression.location);
    }
  }

  for (const HIRExpression &child : expression.children) {
    validateVectorSwizzleExpression(child, diagnostics);
  }
}

void validateVectorScalarArithmeticExpression(const HIRExpression &expression,
                                              DiagnosticEngine &diagnostics) {
  if (expression.kind == HIRExpressionKind::Binary &&
      isArithmeticBinaryOperator(expression.value) &&
      expression.children.size() >= 2) {
    const HIRType &left = expression.children[0].type;
    const HIRType &right = expression.children[1].type;
    if (isFloatVectorType(left) && isScalarNumericType(right) &&
        !isFloatScalarType(right)) {
      diagnostics.error(
          "sema.vector-scalar-arithmetic",
          "float vector-scalar arithmetic requires the scalar operand to be "
          "float; got '" +
              formatType(left) + " " + expression.value + " " +
              formatType(right) + "'",
          expression.children[1].location);
    }
    if (isScalarNumericType(left) && !isFloatScalarType(left) &&
        isFloatVectorType(right)) {
      diagnostics.error(
          "sema.vector-scalar-arithmetic",
          "float vector-scalar arithmetic requires the scalar operand to be "
          "float; got '" +
              formatType(left) + " " + expression.value + " " +
              formatType(right) + "'",
          expression.children[0].location);
    }
  }

  for (const HIRExpression &child : expression.children) {
    validateVectorScalarArithmeticExpression(child, diagnostics);
  }
}

void validateScalarConstructorExpression(const HIRExpression &expression,
                                         DiagnosticEngine &diagnostics) {
  if (expression.kind == HIRExpressionKind::Constructor &&
      isScalarNumericConstructorType(expression.type)) {
    bool valid = true;
    if (expression.children.size() != 1) {
      diagnostics.error("sema.scalar-constructor",
                        "scalar numeric constructor '" + expression.value +
                            "' expects exactly one operand, got " +
                            std::to_string(expression.children.size()),
                        expression.location);
      valid = false;
    }

    if (valid && !expression.children.front().type.name.empty()) {
      const HIRType &sourceType = expression.children.front().type;
      if (!isScalarNumericType(sourceType)) {
        diagnostics.error(
            "sema.scalar-constructor",
            "scalar numeric constructor '" + expression.value +
                "' requires a scalar numeric operand, got '" +
                formatType(sourceType) + "'",
            expression.children.front().location);
      } else if (isSignedUnsignedScalarPair(expression.type, sourceType)) {
        if (!isComputeInvocationBuiltinIntConversion(expression, sourceType)) {
          diagnostics.error(
              "sema.scalar-constructor",
              "signed/unsigned integer scalar constructors are not defined yet; "
              "use an explicit bitcast operation once CrossGL adds one",
              expression.children.front().location);
        }
      }
    }
  }

  for (const HIRExpression &child : expression.children) {
    validateScalarConstructorExpression(child, diagnostics);
  }
}

bool isDescriptorResourceArrayIndex(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRResource> &resources) {
  if (expression.kind != HIRExpressionKind::IndexAccess ||
      expression.children.size() < 2 ||
      expression.children[0].kind != HIRExpressionKind::Identifier) {
    return false;
  }

  const auto resource = resources.find(expression.children[0].value);
  return resource != resources.end() &&
         resource->second.kind != HIRResourceKind::Shared &&
         resource->second.kind != HIRResourceKind::Value &&
         resource->second.type.arraySize.has_value();
}

void validateNonUniformIndexExpression(
    const HIRExpression &expression,
    const std::unordered_map<std::string, HIRResource> &resources,
    DiagnosticEngine &diagnostics,
    const HIRExpression *parent = nullptr,
    std::size_t childIndex = 0) {
  if (expression.kind == HIRExpressionKind::NonUniform) {
    bool valid = true;
    if (expression.children.size() != 1) {
      diagnostics.error("sema.nonuniform-index-arity",
                        "nonuniform expects exactly one descriptor index operand",
                        expression.location);
      valid = false;
    }

    if (parent == nullptr || parent->kind != HIRExpressionKind::IndexAccess ||
        childIndex != 1 || !isDescriptorResourceArrayIndex(*parent, resources)) {
      diagnostics.error("sema.nonuniform-index-placement",
                        "nonuniform can only annotate the index operand of a "
                        "descriptor resource array access",
                        expression.location);
      valid = false;
    }

    if (valid) {
      const HIRType &indexType = expression.children.front().type;
      if (!isIntegerScalarType(indexType)) {
        diagnostics.error("sema.nonuniform-index-type",
                          "nonuniform descriptor indices must be scalar int "
                          "or uint values, got '" +
                              formatType(indexType) + "'",
                          expression.children.front().location);
      }
    }
  }

  for (std::size_t index = 0; index < expression.children.size(); ++index) {
    validateNonUniformIndexExpression(expression.children[index], resources,
                                      diagnostics, &expression, index);
  }
}

bool isAtomicReadModifyWriteCallName(std::string_view name) {
  return isHIRAtomicIntegerReadModifyWriteIntrinsic(name);
}

bool isAtomicReadModifyWriteCall(const HIRExpression &expression) {
  return expression.kind == HIRExpressionKind::Call &&
         isAtomicReadModifyWriteCallName(expression.value);
}

std::string atomicReadModifyWriteDiagnosticStem(std::string_view name) {
  return readModifyWriteOldValueDiagnosticStem(name);
}

std::string atomicReadModifyWriteValueTerm(std::string_view name) {
  return readModifyWriteOldValueTerm(name);
}

std::optional<std::string> atomicIntegerElementType(const HIRType &type) {
  if (isAtomicIntegerScalarType(type)) {
    const std::optional<HIRType> payload = atomicPayloadType(type);
    if (payload.has_value()) {
      return payload->name;
    }
  }
  if (isIntegerScalarType(type)) {
    return stripTypeQualifier(type).name;
  }
  return std::nullopt;
}

bool isAtomicReadModifyWriteValueType(const HIRType &type,
                                      std::string_view expected) {
  HIRType normalized = stripTypeQualifier(type);
  if (normalized.arraySize.has_value() ||
      (!normalized.name.empty() && normalized.name.back() == '*')) {
    return false;
  }
  return normalized.name == expected;
}

const HIRExpression &unwrapAtomicTargetExpression(
    const HIRExpression &expression) {
  const HIRExpression *current = &expression;
  while ((current->kind == HIRExpressionKind::Group ||
          current->kind == HIRExpressionKind::NonUniform) &&
         current->children.size() == 1) {
    current = &current->children.front();
  }
  return *current;
}

bool isAtomicReadModifyWriteAssignableTarget(const HIRExpression &expression) {
  const HIRExpression &target = unwrapAtomicTargetExpression(expression);
  return target.kind == HIRExpressionKind::Identifier ||
         target.kind == HIRExpressionKind::IndexAccess ||
         target.kind == HIRExpressionKind::MemberAccess;
}

void validateAtomicReadModifyWriteExpression(const HIRExpression &expression,
                                             DiagnosticEngine &diagnostics) {
  if (isAtomicReadModifyWriteCall(expression)) {
    const std::string diagnosticStem =
        atomicReadModifyWriteDiagnosticStem(expression.value);
    const std::string valueTerm =
        atomicReadModifyWriteValueTerm(expression.value);
    if (expression.children.size() != 2) {
      diagnostics.error(
          "sema." + diagnosticStem + "-arity",
          expression.value + " expects exactly 2 arguments (target, " +
              valueTerm + "), got " +
              std::to_string(expression.children.size()),
          expression.location);
    } else {
      const HIRExpression &target = expression.children[0];
      const HIRExpression &value = expression.children[1];
      if (!target.type.name.empty()) {
        if (!isAtomicReadModifyWriteAssignableTarget(target)) {
          diagnostics.error("sema." + diagnosticStem + "-target-lvalue",
                            expression.value +
                                " target must be an assignable scalar "
                            "integer or atomic integer storage location",
                            target.location);
        }

        const std::optional<std::string> elementType =
            atomicIntegerElementType(target.type);
        if (!elementType.has_value()) {
          diagnostics.error(
              "sema." + diagnosticStem + "-target-type",
              expression.value +
                  " target must be scalar atomic<int>, atomic<uint>, "
              "int, or uint storage, got '" +
                  formatType(target.type) + "'",
              target.location);
        } else if (!isAtomicReadModifyWriteValueType(value.type,
                                                     *elementType)) {
          diagnostics.error(
              "sema." + diagnosticStem + "-" + valueTerm + "-type",
              expression.value + " " + valueTerm + " for target type '" +
                  formatType(target.type) + "' must be scalar " +
                  *elementType + ", got '" + formatType(value.type) + "'",
              value.location);
        }
      }
    }
  }

  for (const HIRExpression &child : expression.children) {
    validateAtomicReadModifyWriteExpression(child, diagnostics);
  }
}

void validateAtomicReadModifyWriteValueType(const HIRExpression &expression,
                                            const HIRType &expectedType,
                                            std::string_view context,
                                            DiagnosticEngine &diagnostics) {
  if (!isReadModifyWriteOldValueCall(expression) || expectedType.name.empty() ||
      expression.type.name.empty()) {
    return;
  }
  if (!sameType(stripTypeQualifier(expectedType),
                stripTypeQualifier(expression.type))) {
    diagnostics.error(
        "sema." + readModifyWriteOldValueDiagnosticStem(expression.value) +
            "-capture-type",
        expression.value + " returned old value in " + std::string(context) +
            " must match scalar payload type '" + formatType(expression.type) +
            "', got '" + formatType(expectedType) + "'",
        expression.location);
  }
}

void validateAtomicReadModifyWriteValueUseInExpression(
    const HIRExpression &expression, bool allowRootAtomicReadModifyWrite,
    DiagnosticEngine &diagnostics) {
  if (expression.kind == HIRExpressionKind::Empty) {
    return;
  }
  if (isReadModifyWriteOldValueCall(expression) &&
      !allowRootAtomicReadModifyWrite) {
    diagnostics.error(
        "sema." + readModifyWriteOldValueDiagnosticStem(expression.value) +
            "-value-context",
        expression.value +
            " returned old value is supported only as the whole "
        "declaration initializer or assignment RHS expression",
        expression.location);
  }
  for (const HIRExpression &child : expression.children) {
    validateAtomicReadModifyWriteValueUseInExpression(child, false,
                                                      diagnostics);
  }
}

void validateAtomicReadModifyWriteValueUse(const HIRStatement &statement,
                                           DiagnosticEngine &diagnostics) {
  validateAtomicReadModifyWriteValueUseInExpression(statement.target, false,
                                                    diagnostics);
  const bool allowRootAtomicReadModifyWrite =
      isReadModifyWriteOldValueCall(statement.value) &&
      (statement.kind == HIRStatementKind::Expression ||
       statement.kind == HIRStatementKind::Declaration ||
       statement.kind == HIRStatementKind::Assignment);
  validateAtomicReadModifyWriteValueUseInExpression(
      statement.value, allowRootAtomicReadModifyWrite, diagnostics);
  if (statement.kind == HIRStatementKind::Declaration) {
    validateAtomicReadModifyWriteValueType(
        statement.value, statement.declaredType, "declaration initializer",
        diagnostics);
  } else if (statement.kind == HIRStatementKind::Assignment) {
    validateAtomicReadModifyWriteValueType(
        statement.value, statement.target.type, "assignment RHS", diagnostics);
  }
}

void validateExpressionSemantics(const HIRExpression &expression,
                                 std::string_view stage,
                                 const std::unordered_map<std::string, HIRResource>
                                     &resources,
                                 DiagnosticEngine &diagnostics) {
  validateTextureSampleExpression(expression, stage, diagnostics);
  validateTextureCompareExpression(expression, stage, diagnostics);
  validateImageAccessExpression(expression, resources, diagnostics);
  validateVectorSwizzleExpression(expression, diagnostics);
  validateVectorScalarArithmeticExpression(expression, diagnostics);
  validateScalarConstructorExpression(expression, diagnostics);
  validateNonUniformIndexExpression(expression, resources, diagnostics);
  validateAtomicReadModifyWriteExpression(expression, diagnostics);
}

void validateControlTransferStatement(const HIRStatement &statement,
                                      std::string_view stage,
                                      std::size_t loopDepth,
                                      DiagnosticEngine &diagnostics) {
  switch (statement.kind) {
  case HIRStatementKind::Break:
    if (loopDepth == 0) {
      diagnostics.error("sema.break-placement",
                        "break statement is only legal inside a loop",
                        statement.location);
    }
    break;
  case HIRStatementKind::Continue:
    if (loopDepth == 0) {
      diagnostics.error("sema.continue-placement",
                        "continue statement is only legal inside a loop",
                        statement.location);
    }
    break;
  case HIRStatementKind::Discard:
    if (stage != "fragment") {
      std::string message =
          "discard statement is only legal in fragment stage functions";
      if (stage.empty()) {
        message += "; top-level functions have no fragment stage context";
      } else {
        message += ", not stage '" + std::string(stage) + "'";
      }
      diagnostics.error("sema.discard-stage", message, statement.location);
    }
    break;
  default:
    break;
  }
}

void validateStatementSemantics(const HIRStatement &statement,
                                std::string_view stage,
                                const std::unordered_map<std::string, HIRResource>
                                    &resources,
                                DiagnosticEngine &diagnostics,
                                std::size_t loopDepth = 0) {
  validateControlTransferStatement(statement, stage, loopDepth, diagnostics);
  validateAtomicReadModifyWriteValueUse(statement, diagnostics);
  validateExpressionSemantics(statement.target, stage, resources, diagnostics);
  validateExpressionSemantics(statement.value, stage, resources, diagnostics);
  for (const HIRStatement &initializer : statement.initializer) {
    validateStatementSemantics(initializer, stage, resources, diagnostics,
                               loopDepth);
  }
  for (const HIRStatement &update : statement.update) {
    validateStatementSemantics(update, stage, resources, diagnostics, loopDepth);
  }
  const std::size_t childLoopDepth =
      statement.kind == HIRStatementKind::For ? loopDepth + 1 : loopDepth;
  for (const HIRStatement &child : statement.body) {
    validateStatementSemantics(child, stage, resources, diagnostics,
                               childLoopDepth);
  }
  for (const HIRStatement &child : statement.elseBody) {
    validateStatementSemantics(child, stage, resources, diagnostics, loopDepth);
  }
}

void validateFunctionExpressions(const HIRFunction &function,
                                 std::string_view stage,
                                 const std::vector<HIRResource> &resources,
                                 DiagnosticEngine &diagnostics) {
  std::unordered_map<std::string, HIRResource> resourceMap;
  for (const HIRResource &resource : resources) {
    resourceMap[resource.name] = resource;
  }
  for (const HIRStatement &statement : function.body) {
    validateStatementSemantics(statement, stage, resourceMap, diagnostics);
  }
}

template <typename Visitor>
void visitHIRExpressionTree(const HIRExpression &expression, Visitor &visitor) {
  visitor(expression);
  for (const HIRExpression &child : expression.children) {
    visitHIRExpressionTree(child, visitor);
  }
}

template <typename Visitor>
void visitHIRStatementExpressions(const HIRStatement &statement,
                                  Visitor &visitor) {
  visitHIRExpressionTree(statement.target, visitor);
  visitHIRExpressionTree(statement.value, visitor);
  for (const HIRStatement &initializer : statement.initializer) {
    visitHIRStatementExpressions(initializer, visitor);
  }
  for (const HIRStatement &update : statement.update) {
    visitHIRStatementExpressions(update, visitor);
  }
  for (const HIRStatement &child : statement.body) {
    visitHIRStatementExpressions(child, visitor);
  }
  for (const HIRStatement &child : statement.elseBody) {
    visitHIRStatementExpressions(child, visitor);
  }
}

template <typename Visitor>
void visitHIRFunctionExpressions(const HIRFunction &function,
                                 Visitor &visitor) {
  for (const HIRStatement &statement : function.body) {
    visitHIRStatementExpressions(statement, visitor);
  }
}

} // namespace

std::optional<std::size_t>
manualTextureCompareKernelListTapCount(const HIRExpression &kernelList) {
  if (manualTextureCompareKernelListShape(kernelList) !=
      ManualTextureCompareKernelListShape::Valid) {
    return std::nullopt;
  }
  return kernelList.children.size() / 2;
}

ManualTextureCompareKernelListShape
manualTextureCompareKernelListShape(const HIRExpression &kernelList) {
  if (kernelList.kind != HIRExpressionKind::Call ||
      !isHIRTextureCompareKernelBuiltinCall(kernelList.value)) {
    return ManualTextureCompareKernelListShape::NotTextureCompareKernelCall;
  }
  if (kernelList.children.empty()) {
    return ManualTextureCompareKernelListShape::Empty;
  }
  if (kernelList.children.size() % 2 != 0) {
    return ManualTextureCompareKernelListShape::OddOperandCount;
  }
  if (kernelList.children.size() / 2 > kMaxManualTextureCompareKernelTaps) {
    return ManualTextureCompareKernelListShape::TooManyTaps;
  }
  return ManualTextureCompareKernelListShape::Valid;
}

std::optional<std::vector<ManualTextureCompareKernelTap>>
manualTextureCompareKernelTaps(const HIRExpression &expression) {
  if (expression.kind != HIRExpressionKind::TextureCompareLodManual) {
    return std::nullopt;
  }

  std::vector<ManualTextureCompareKernelTap> taps;
  if (expression.value == "textureCompareLodManualKernel4" &&
      expression.children.size() == 14) {
    taps.reserve(4);
    for (std::size_t index = 0; index < 4; ++index) {
      taps.push_back(ManualTextureCompareKernelTap{
          &expression.children[6 + index * 2],
          &expression.children[7 + index * 2],
      });
    }
    return taps;
  }
  if (expression.value == "textureCompareLodManualKernel8" &&
      expression.children.size() == 22) {
    taps.reserve(8);
    for (std::size_t index = 0; index < 8; ++index) {
      taps.push_back(ManualTextureCompareKernelTap{
          &expression.children[6 + index * 2],
          &expression.children[7 + index * 2],
      });
    }
    return taps;
  }
  if (expression.value == "textureCompareLodManualKernel" &&
      expression.children.size() == 7) {
    const HIRExpression &kernelList = expression.children[6];
    const std::optional<std::size_t> tapCount =
        manualTextureCompareKernelListTapCount(kernelList);
    if (!tapCount.has_value()) {
      return std::nullopt;
    }
    taps.reserve(*tapCount);
    for (std::size_t index = 0; index < *tapCount; ++index) {
      taps.push_back(ManualTextureCompareKernelTap{
          &kernelList.children[index * 2],
          &kernelList.children[index * 2 + 1],
      });
    }
    return taps;
  }
  return std::nullopt;
}

std::optional<ManualTextureCompareKernelWeightSummary>
manualTextureCompareKernelWeightSummary(const HIRExpression &expression) {
  const std::optional<std::vector<ManualTextureCompareKernelTap>> taps =
      manualTextureCompareKernelTaps(expression);
  if (!taps.has_value()) {
    return std::nullopt;
  }

  ManualTextureCompareKernelWeightSummary summary;
  summary.tapCount = taps->size();
  summary.allWeightsStatic = true;
  const HIRScalarConstantMap noConstants;
  for (const ManualTextureCompareKernelTap &tap : *taps) {
    if (tap.weight == nullptr) {
      return std::nullopt;
    }
    const std::optional<FoldedHIRScalar> folded =
        foldExpression(*tap.weight, noConstants);
    if (!folded.has_value() || folded->isBool) {
      summary.allWeightsStatic = false;
      summary.sum = 0.0;
      summary.zeroSum = false;
      summary.normalized = false;
      return summary;
    }
    summary.sum += folded->number;
  }

  summary.zeroSum =
      std::fabs(summary.sum) <= kManualTextureCompareKernelWeightSumTolerance;
  summary.normalized =
      std::fabs(summary.sum - 1.0) <=
      kManualTextureCompareKernelWeightSumTolerance;
  return summary;
}

std::optional<ManualTextureCompareKernelAnalysis>
manualTextureCompareKernelAnalysis(const HIRExpression &expression) {
  const std::optional<ManualTextureCompareKernelWeightSummary> summary =
      manualTextureCompareKernelWeightSummary(expression);
  if (!summary.has_value()) {
    return std::nullopt;
  }

  ManualTextureCompareKernelAnalysis analysis;
  analysis.sourceOperation = expression.value;
  analysis.canonicalOperation = "textureCompareLodManualKernel";
  analysis.weights = *summary;

  if (expression.value == "textureCompareLodManualKernel4") {
    analysis.form = ManualTextureCompareKernelForm::Fixed4;
    analysis.compatibilityAlias = true;
  } else if (expression.value == "textureCompareLodManualKernel8") {
    analysis.form = ManualTextureCompareKernelForm::Fixed8;
    analysis.compatibilityAlias = true;
  } else if (expression.value == "textureCompareLodManualKernel") {
    analysis.form = ManualTextureCompareKernelForm::TapList;
  } else {
    return std::nullopt;
  }

  return analysis;
}

ManualTextureCompareKernelWeightClass manualTextureCompareKernelWeightClass(
    const ManualTextureCompareKernelWeightSummary &summary) {
  if (!summary.allWeightsStatic) {
    return ManualTextureCompareKernelWeightClass::Dynamic;
  }
  if (summary.zeroSum) {
    return ManualTextureCompareKernelWeightClass::StaticZeroSum;
  }
  if (summary.normalized) {
    return ManualTextureCompareKernelWeightClass::StaticNormalized;
  }
  return ManualTextureCompareKernelWeightClass::StaticNonNormalized;
}

ManualTextureCompareKernelModuleAnalysis
manualTextureCompareKernelModuleAnalysis(const HIRModule &module) {
  ManualTextureCompareKernelModuleAnalysis moduleAnalysis;

  auto recordOccurrence =
      [&](std::string stage, std::string entryPoint, std::string function,
          const HIRExpression &expression) {
        std::optional<ManualTextureCompareKernelAnalysis> analysis =
            manualTextureCompareKernelAnalysis(expression);
        if (!analysis.has_value()) {
          return;
        }

        ManualTextureCompareKernelOccurrence occurrence;
        occurrence.stage = std::move(stage);
        occurrence.entryPoint = std::move(entryPoint);
        occurrence.function = std::move(function);
        occurrence.weightClass =
            manualTextureCompareKernelWeightClass(analysis->weights);
        occurrence.analysis = std::move(*analysis);

        const std::size_t index = moduleAnalysis.kernels.size();
        moduleAnalysis.kernels.push_back(std::move(occurrence));
        switch (moduleAnalysis.kernels.back().weightClass) {
        case ManualTextureCompareKernelWeightClass::StaticNormalized:
          moduleAnalysis.staticNormalized.push_back(index);
          break;
        case ManualTextureCompareKernelWeightClass::StaticNonNormalized:
          moduleAnalysis.staticNonNormalized.push_back(index);
          break;
        case ManualTextureCompareKernelWeightClass::StaticZeroSum:
          moduleAnalysis.staticZeroSum.push_back(index);
          break;
        case ManualTextureCompareKernelWeightClass::Dynamic:
          moduleAnalysis.dynamic.push_back(index);
          break;
        }
      };

  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &function : stage.functions) {
      auto visitor = [&](const HIRExpression &expression) {
        recordOccurrence(stage.stage, stage.entryPointName, function.name,
                         expression);
      };
      visitHIRFunctionExpressions(function, visitor);
    }
  }

  for (const HIRFunction &function : module.functions) {
    auto visitor = [&](const HIRExpression &expression) {
      recordOccurrence("", "", function.name, expression);
    };
    visitHIRFunctionExpressions(function, visitor);
  }

  return moduleAnalysis;
}

std::optional<std::size_t>
manualTextureCompareKernelTapCount(const HIRExpression &expression) {
  const std::optional<std::vector<ManualTextureCompareKernelTap>> taps =
      manualTextureCompareKernelTaps(expression);
  if (!taps.has_value()) {
    return std::nullopt;
  }
  return taps->size();
}

std::optional<HIRModule> buildHIR(const ShaderModule &module,
                                  DiagnosticEngine &diagnostics) {
  HIRModule hir;
  hir.name = module.name;

  std::vector<StructDecl> allStructs = module.structs;
  allStructs.insert(allStructs.end(), module.cbuffers.begin(),
                    module.cbuffers.end());
  for (const StageDecl &stage : module.stages) {
    allStructs.insert(allStructs.end(), stage.structs.begin(), stage.structs.end());
  }

  std::set<std::string> structNames;
  std::set<std::string> knownTypeNames;
  for (std::string_view type :
       {"void",      "bool",      "int",       "uint",      "float",
        "double",    "half",      "vec2",      "vec3",      "vec4",
        "ivec2",     "ivec3",     "ivec4",     "uvec2",     "uvec3",
        "uvec4",     "bvec2",     "bvec3",     "bvec4",     "mat2",
        "mat3",      "mat4",      "mat2x2",    "mat3x3",    "mat4x4",
        "sampler",              "comparison_sampler",
        "sampler2D",            "sampler2DArray",
        "sampler3D",            "samplerCube",
        "samplerCubeArray",     "sampler2DShadow",
        "sampler2DArrayShadow", "samplerCubeShadow",
        "samplerCubeArrayShadow",
        "isampler2D",           "isampler2DArray",
        "isampler3D",           "isamplerCube",
        "isamplerCubeArray",    "usampler2D",
        "usampler2DArray",      "usampler3D",
        "usamplerCube",         "usamplerCubeArray",
        "texture2D",            "texture2DArray",
        "texture3D",            "textureCube",
        "textureCubeArray",
        "image2D",              "iimage2D",
        "uimage2D",             "image2DArray",
        "iimage2DArray",        "uimage2DArray"}) {
    knownTypeNames.insert(std::string(type));
  }

  for (const StructDecl &decl : allStructs) {
    structNames.insert(decl.name);
    knownTypeNames.insert(decl.name);
  }

  std::unordered_map<std::string, HIRStruct> structMap;
  std::set<std::string> emittedStructNames;
  for (const StructDecl &decl : allStructs) {
    if (!emittedStructNames.insert(decl.name).second) {
      diagnostics.warning("sema.duplicate-struct",
                          "duplicate struct declaration '" + decl.name +
                              "'; using the first declaration for this iteration",
                          decl.location);
      continue;
    }

    HIRStruct hirStruct;
    hirStruct.name = decl.name;
    std::set<std::string> fieldNames;
    for (const StructField &field : decl.fields) {
      if (!fieldNames.insert(field.name).second) {
        diagnostics.error("sema.duplicate-field",
                          "duplicate field '" + field.name + "' in struct '" +
                              decl.name + "'",
                          field.location);
      }
      hirStruct.fields.push_back(
          HIRField{convertType(field.type), field.name, field.location});
    }
    structMap[hirStruct.name] = hirStruct;
    hir.structs.push_back(std::move(hirStruct));
  }

  for (const HIRStruct &decl : hir.structs) {
    for (const HIRField &field : decl.fields) {
      if (!isKnownType(field.type, structNames)) {
        diagnostics.warning("sema.unknown-type",
                            "unknown type '" + field.type.name + "' in struct '" +
                                decl.name + "'",
                            field.type.location);
      }
    }
  }

  std::unordered_map<std::string, HIRType> constantTypes;
  HIRScalarConstantMap constantValues;
  std::set<std::string> constantNames;
  for (const ConstantDecl &constant : module.constants) {
    if (!constantNames.insert(constant.name).second) {
      diagnostics.error("sema.duplicate-constant",
                        "duplicate constant '" + constant.name + "'",
                        constant.location);
      continue;
    }

    HIRConstant hirConstant = convertConstant(
        constant, knownTypeNames, structMap, constantTypes, constantValues,
        diagnostics);
    if (!isKnownType(hirConstant.type, structNames)) {
      diagnostics.warning("sema.unknown-constant-type",
                          "unknown type '" + hirConstant.type.name +
                              "' for constant '" + constant.name + "'",
                          constant.type.location);
    }
    if (std::optional<FoldedHIRScalar> folded =
            foldExpression(hirConstant.value, constantValues)) {
      constantValues[hirConstant.name] = *folded;
      hirConstant.foldedValue = formatFoldedHIRScalar(*folded);
    }
    constantTypes[hirConstant.name] = hirConstant.type;
    hir.constants.push_back(std::move(hirConstant));
  }

  validateArraySizePolicy(allStructs, module.functions, module.stages,
                          constantTypes, constantValues, diagnostics);

  const std::unordered_map<std::string, HIRType> cbufferFieldTypes =
      collectCBufferFieldTypes(module.cbuffers, diagnostics);

  std::unordered_map<std::string, bool> topLevelFunctions;
  for (const FunctionDecl &function : module.functions) {
    const bool hasBody = !function.bodyTokens.empty();
    auto duplicate = topLevelFunctions.find(function.name);
    if (duplicate != topLevelFunctions.end() && duplicate->second && hasBody) {
      diagnostics.error("sema.duplicate-function",
                        "duplicate top-level function '" + function.name + "'",
                        function.location);
    }
    topLevelFunctions[function.name] = topLevelFunctions[function.name] || hasBody;
    HIRFunction hirFunction =
        convertFunction(function, knownTypeNames, structMap, {}, "",
                        constantTypes, cbufferFieldTypes, diagnostics);
    validateFunctionLocalArrayDeclarations(
        hirFunction, "function '" + function.name + "'", constantTypes,
        constantValues, diagnostics);
    validateFunctionTypes(hirFunction, structNames, diagnostics,
                          "function '" + function.name + "'",
                          function.returnType.location);
    validateFunctionExpressions(hirFunction, "", {}, diagnostics);
    hir.functions.push_back(std::move(hirFunction));
  }

  for (const StageDecl &stage : module.stages) {
    HIRStage hirStage;
    hirStage.stage = stage.stage;
    hirStage.declarationSpan = stage.location;
    hirStage.nameSpan = stage.location;
    if (stage.workgroupSize.has_value()) {
      hirStage.workgroupSize =
          convertWorkgroupSize(*stage.workgroupSize, knownTypeNames, structMap,
                               constantTypes, constantValues);
    }

    std::unordered_map<std::size_t, std::size_t> nextBindingBySet;
    std::unordered_map<std::size_t, std::set<std::size_t>> usedBindingsBySet;
    std::set<std::string> resourceNames;
    for (const StructDecl &cbuffer : module.cbuffers) {
      if (!resourceNames.insert(cbuffer.name).second) {
        diagnostics.error("sema.duplicate-resource",
                          "duplicate resource '" + cbuffer.name + "' in stage '" +
                              stage.stage + "'",
                          cbuffer.location);
        continue;
      }

      std::size_t &nextBinding = nextBindingBySet[0];
      std::set<std::size_t> &usedBindings = usedBindingsBySet[0];
      while (usedBindings.contains(nextBinding)) {
        ++nextBinding;
      }
      const std::size_t binding = nextBinding;
      usedBindings.insert(binding);
      ++nextBinding;
      hirStage.resources.push_back(convertCBufferResource(cbuffer, 0, binding));
    }

    for (const ResourceDecl &resource : stage.resources) {
      if (!resourceNames.insert(resource.name).second) {
        diagnostics.error("sema.duplicate-resource",
                          "duplicate resource '" + resource.name + "' in stage '" +
                              stage.stage + "'",
                          resource.location);
        continue;
      }
      const HIRResourceKind kind = resourceKindFromName(resource.type.name);
      const std::size_t set = resource.set.value_or(0);
      std::size_t binding = resource.binding.value_or(0);
      if (kind != HIRResourceKind::Shared) {
        std::size_t &nextBinding = nextBindingBySet[set];
        std::set<std::size_t> &usedBindings = usedBindingsBySet[set];
        if (resource.binding.has_value()) {
          if (usedBindings.contains(*resource.binding)) {
            diagnostics.error("sema.duplicate-resource-binding",
                              "duplicate resource binding " +
                                  std::to_string(*resource.binding) +
                                  " in set " + std::to_string(set) +
                                  " for stage '" + stage.stage + "'",
                              resource.bindingLocation);
            continue;
          }
        } else {
          while (usedBindings.contains(nextBinding)) {
            ++nextBinding;
          }
          binding = nextBinding;
        }
        usedBindings.insert(binding);
        if (!resource.binding.has_value() && binding == nextBinding) {
          ++nextBinding;
        }
      } else if (resource.binding.has_value() || resource.set.has_value()) {
        diagnostics.error("sema.shared-resource-binding",
                          "shared resource '" + resource.name +
                              "' cannot use descriptor set or binding layout",
                          resource.bindingLocation);
        continue;
      }

      HIRResource hirResource = convertResource(resource, set, binding);
      if (resource.storageImageAccessQualifier.has_value() &&
          hirResource.kind != HIRResourceKind::StorageImage) {
        diagnostics.error(
            "sema.storage-image-access-qualifier",
            "storage-image access qualifier '" +
                *resource.storageImageAccessQualifier +
                "' can only be used with storage-image resources; resource '" +
                resource.name + "' has type '" + formatType(hirResource.type) +
                "'",
            resource.storageImageAccessLocation);
        continue;
      }
      if (resource.storageImageFormat.has_value()) {
        if (hirResource.kind != HIRResourceKind::StorageImage) {
          diagnostics.error(
              "sema.storage-image-format-layout",
              "storage-image layout format '" + *resource.storageImageFormat +
                  "' can only be used with storage-image resources; resource '" +
                  resource.name + "' has type '" + formatType(hirResource.type) +
                  "'",
              resource.storageImageFormatLocation);
          continue;
        }
        if (!storageImageFormatCompatibleWithType(*resource.storageImageFormat,
                                                  baseTypeName(hirResource.type))) {
          diagnostics.error(
              "sema.storage-image-format-layout",
              "storage-image layout format '" + *resource.storageImageFormat +
                  "' is incompatible with storage-image resource '" +
                  resource.name + "' of type '" + formatType(hirResource.type) +
                  "'; expected '" +
                  storageImageFormatName(baseTypeName(hirResource.type)) + "'",
              resource.storageImageFormatLocation);
          continue;
        }
      }
      if (hirResource.kind == HIRResourceKind::StorageImage &&
          hirResource.type.arraySize.has_value() &&
          hirResource.type.arraySize->empty()) {
        diagnostics.error(
            "sema.storage-image-runtime-descriptor-array",
            "runtime/unsized storage-image descriptor arrays are not "
            "supported for resource '" +
                resource.name + "'",
            resource.type.location);
        continue;
      }
      if (!isKnownType(hirResource.type, structNames) &&
          !isScalarAtomicIntegerStorageType(hirResource.type)) {
        diagnostics.warning("sema.unknown-resource-type",
                            "unknown resource type '" + hirResource.type.name +
                                "' for resource '" + resource.name + "'",
                            resource.type.location);
      }
      hirStage.resources.push_back(std::move(hirResource));
    }

    std::unordered_map<std::string, bool> stageFunctions;
    for (const FunctionDecl &function : stage.functions) {
      const bool hasBody = !function.bodyTokens.empty();
      auto duplicate = stageFunctions.find(function.name);
      if (duplicate != stageFunctions.end() && duplicate->second && hasBody) {
        diagnostics.error("sema.duplicate-stage-function",
                          "duplicate function '" + function.name +
                              "' in stage '" + stage.stage + "'",
                          function.location);
      }
      stageFunctions[function.name] = stageFunctions[function.name] || hasBody;
      HIRFunction hirFunction =
          convertFunction(function, knownTypeNames, structMap, hirStage.resources,
                          stage.stage, constantTypes, cbufferFieldTypes,
                          diagnostics);
      validateFunctionLocalArrayDeclarations(
          hirFunction,
          "stage '" + stage.stage + "' function '" + function.name + "'",
          constantTypes, constantValues, diagnostics);
      validateFunctionTypes(hirFunction, structNames, diagnostics,
                            "stage function '" + function.name + "'",
                            function.returnType.location);
      validateFunctionExpressions(hirFunction, stage.stage, hirStage.resources,
                                  diagnostics);
      if (function.name == "main" && hirStage.entryPointName.empty()) {
        hirStage.entryPointName = function.name;
      }
      hirStage.functions.push_back(std::move(hirFunction));
    }

    if (hirStage.entryPointName.empty() && !hirStage.functions.empty()) {
      hirStage.entryPointName = hirStage.functions.front().name;
      diagnostics.warning("sema.inferred-entry-point",
                          "stage '" + stage.stage + "' has no main function; using '" +
                              hirStage.entryPointName + "'",
                          stage.location);
    }
    if (hirStage.functions.empty()) {
      diagnostics.error("sema.empty-stage",
                        "stage '" + stage.stage + "' has no functions",
                        stage.location);
    }
    hir.stages.push_back(std::move(hirStage));
  }

  if (hir.stages.empty()) {
    diagnostics.error("sema.no-stages", "shader has no compileable stages",
                      module.location);
  }

  if (diagnostics.hasErrors()) {
    return std::nullopt;
  }
  return hir;
}

std::string formatType(const HIRType &type) {
  if (!type.arraySize.has_value()) {
    return type.name;
  }
  return type.name + "[" + *type.arraySize + "]";
}

std::string typeToIR(const HIRType &type) {
  HIRType normalized = stripTypeQualifier(type);
  const bool pointer = !normalized.name.empty() && normalized.name.back() == '*';
  normalized.name = stripPointerSuffix(normalized.name);

  std::string base;
  if (normalized.name == "void") {
    base = "!crossgl.void";
  } else if (normalized.name == "bool") {
    base = "!crossgl.i1";
  } else if (normalized.name == "int") {
    base = "!crossgl.i32";
  } else if (normalized.name == "uint") {
    base = "!crossgl.u32";
  } else if (normalized.name == "float") {
    base = "!crossgl.f32";
  } else if (normalized.name == "double") {
    base = "!crossgl.f64";
  } else if (normalized.name == "sampler") {
    base = "!crossgl.sampler";
  } else if (normalized.name == "comparison_sampler") {
    base = "!crossgl.comparison_sampler";
  } else if (normalized.name == "sampler2D" || normalized.name == "texture2D") {
    base = "!crossgl.texture<2d, f32>";
  } else if (normalized.name == "sampler2DArray" ||
             normalized.name == "texture2DArray") {
    base = "!crossgl.texture<2d_array, f32>";
  } else if (normalized.name == "sampler2DShadow") {
    base = "!crossgl.texture<2d, depth_compare>";
  } else if (normalized.name == "sampler2DArrayShadow") {
    base = "!crossgl.texture<2d_array, depth_compare>";
  } else if (normalized.name == "isampler2D") {
    base = "!crossgl.texture<2d, i32>";
  } else if (normalized.name == "isampler2DArray") {
    base = "!crossgl.texture<2d_array, i32>";
  } else if (normalized.name == "usampler2D") {
    base = "!crossgl.texture<2d, u32>";
  } else if (normalized.name == "usampler2DArray") {
    base = "!crossgl.texture<2d_array, u32>";
  } else if (normalized.name == "sampler3D" || normalized.name == "texture3D") {
    base = "!crossgl.texture<3d, f32>";
  } else if (normalized.name == "isampler3D") {
    base = "!crossgl.texture<3d, i32>";
  } else if (normalized.name == "usampler3D") {
    base = "!crossgl.texture<3d, u32>";
  } else if (normalized.name == "samplerCube" ||
             normalized.name == "textureCube") {
    base = "!crossgl.texture<cube, f32>";
  } else if (normalized.name == "samplerCubeArray" ||
             normalized.name == "textureCubeArray") {
    base = "!crossgl.texture<cube_array, f32>";
  } else if (normalized.name == "samplerCubeShadow") {
    base = "!crossgl.texture<cube, depth_compare>";
  } else if (normalized.name == "samplerCubeArrayShadow") {
    base = "!crossgl.texture<cube_array, depth_compare>";
  } else if (normalized.name == "isamplerCube") {
    base = "!crossgl.texture<cube, i32>";
  } else if (normalized.name == "isamplerCubeArray") {
    base = "!crossgl.texture<cube_array, i32>";
  } else if (normalized.name == "usamplerCube") {
    base = "!crossgl.texture<cube, u32>";
  } else if (normalized.name == "usamplerCubeArray") {
    base = "!crossgl.texture<cube_array, u32>";
  } else if (isStorageImageResourceType(normalized.name)) {
    base = "!crossgl.storage_image<" +
           storageImageDimensionName(normalized.name) + ", " +
           storageImageFormatName(normalized.name) + ">";
  } else if (normalized.name.rfind("vec", 0) == 0 && normalized.name.size() == 4) {
    base = "!crossgl.vec<" + std::string(1, normalized.name[3]) + "xf32>";
  } else if (normalized.name.rfind("ivec", 0) == 0 &&
             normalized.name.size() == 5) {
    base = "!crossgl.vec<" + std::string(1, normalized.name[4]) + "xi32>";
  } else if (normalized.name.rfind("uvec", 0) == 0 &&
             normalized.name.size() == 5) {
    base = "!crossgl.vec<" + std::string(1, normalized.name[4]) + "xu32>";
  } else if (normalized.name.rfind("mat", 0) == 0 && normalized.name.size() == 4) {
    base = "!crossgl.mat<" + std::string(1, normalized.name[3]) + "x" +
           std::string(1, normalized.name[3]) + "xf32>";
  } else {
    base = "!crossgl.struct<" + normalized.name + ">";
  }

  if (normalized.arraySize.has_value()) {
    base = "!crossgl.array<" + base + ", " + *normalized.arraySize + ">";
  }
  if (pointer) {
    base = "!crossgl.ptr<" + base + ">";
  }
  return base;
}

std::string resourceKindName(HIRResourceKind kind) {
  switch (kind) {
  case HIRResourceKind::Uniform:
    return "uniform";
  case HIRResourceKind::Buffer:
    return "buffer";
  case HIRResourceKind::Shared:
    return "shared";
  case HIRResourceKind::Texture:
    return "texture";
  case HIRResourceKind::StorageImage:
    return "storage_image";
  case HIRResourceKind::Sampler:
    return "sampler";
  case HIRResourceKind::Value:
    return "value";
  }
  return "unknown";
}

std::string storageImageAccessName(HIRStorageImageAccess access) {
  switch (access) {
  case HIRStorageImageAccess::ReadWrite:
    return "read_write";
  case HIRStorageImageAccess::ReadOnly:
    return "read";
  case HIRStorageImageAccess::WriteOnly:
    return "write";
  }
  return "unknown";
}

bool storageImageAccessAllowsRead(HIRStorageImageAccess access) {
  return access == HIRStorageImageAccess::ReadWrite ||
         access == HIRStorageImageAccess::ReadOnly;
}

bool storageImageAccessAllowsWrite(HIRStorageImageAccess access) {
  return access == HIRStorageImageAccess::ReadWrite ||
         access == HIRStorageImageAccess::WriteOnly;
}

std::string resolvedStorageImageFormatName(const HIRResource &resource) {
  if (resource.storageImageFormat.has_value()) {
    return *resource.storageImageFormat;
  }
  return storageImageFormatName(baseTypeName(resource.type));
}

std::string
manualTextureCompareKernelFormName(ManualTextureCompareKernelForm form) {
  switch (form) {
  case ManualTextureCompareKernelForm::Fixed4:
    return "fixed4";
  case ManualTextureCompareKernelForm::Fixed8:
    return "fixed8";
  case ManualTextureCompareKernelForm::TapList:
    return "tap-list";
  }
  return "unknown";
}

std::string manualTextureCompareKernelWeightClassName(
    ManualTextureCompareKernelWeightClass weightClass) {
  switch (weightClass) {
  case ManualTextureCompareKernelWeightClass::StaticNormalized:
    return "static-normalized";
  case ManualTextureCompareKernelWeightClass::StaticNonNormalized:
    return "static-non-normalized";
  case ManualTextureCompareKernelWeightClass::StaticZeroSum:
    return "static-zero-sum";
  case ManualTextureCompareKernelWeightClass::Dynamic:
    return "dynamic";
  }
  return "unknown";
}

std::string expressionKindName(HIRExpressionKind kind) {
  switch (kind) {
  case HIRExpressionKind::Empty:
    return "empty";
  case HIRExpressionKind::Identifier:
    return "identifier";
  case HIRExpressionKind::Literal:
    return "literal";
  case HIRExpressionKind::Group:
    return "group";
  case HIRExpressionKind::MemberAccess:
    return "member";
  case HIRExpressionKind::IndexAccess:
    return "index";
  case HIRExpressionKind::NonUniform:
    return "nonuniform";
  case HIRExpressionKind::Call:
    return "call";
  case HIRExpressionKind::Constructor:
    return "construct";
  case HIRExpressionKind::Unary:
    return "unary";
  case HIRExpressionKind::Binary:
    return "binary";
  case HIRExpressionKind::Select:
    return "select";
  case HIRExpressionKind::TextureSample:
    return "texture_sample";
  case HIRExpressionKind::TextureCompare:
    return "texture_compare";
  case HIRExpressionKind::TextureCompareLodManual:
    return "texture_compare_lod_manual";
  }
  return "unknown";
}

std::string statementKindName(HIRStatementKind kind) {
  switch (kind) {
  case HIRStatementKind::Declaration:
    return "decl";
  case HIRStatementKind::Assignment:
    return "assign";
  case HIRStatementKind::Return:
    return "return";
  case HIRStatementKind::Expression:
    return "expr";
  case HIRStatementKind::Block:
    return "block";
  case HIRStatementKind::If:
    return "if";
  case HIRStatementKind::For:
    return "for";
  case HIRStatementKind::Break:
    return "break";
  case HIRStatementKind::Continue:
    return "continue";
  case HIRStatementKind::Discard:
    return "discard";
  case HIRStatementKind::Raw:
    return "raw";
  }
  return "unknown";
}

} // namespace crossgl
