#include "crossgl/HIR/Intrinsics.h"

#include "crossgl/HIR/TypeSemantics.h"

#include <algorithm>
#include <array>
#include <iterator>
#include <span>
#include <string>
#include <utility>
#include <vector>

namespace crossgl {
namespace {

// Same-name signatures must stay contiguous for overload-set lookup.
constexpr std::array<HIRIntrinsicSignature, 34> kHIRIntrinsics = {{
    {"abs", HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::NumericScalarOrVector},
    {"atomicAdd",
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2},
     HIRIntrinsicArgumentDomain::Any,
     HIRIntrinsicArgumentCompatibilityRule::
         AtomicIntegerReadModifyWriteValueMatchesTarget,
     std::array<HIRIntrinsicArgumentDomain, kMaxHIRIntrinsicArgumentDomains>{
         HIRIntrinsicArgumentDomain::AtomicOrIntegerScalarStorage,
         HIRIntrinsicArgumentDomain::Any},
     2, HIRIntrinsicEffect::Opaque},
    {"atomicAnd",
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2},
     HIRIntrinsicArgumentDomain::Any,
     HIRIntrinsicArgumentCompatibilityRule::
         AtomicIntegerReadModifyWriteValueMatchesTarget,
     std::array<HIRIntrinsicArgumentDomain, kMaxHIRIntrinsicArgumentDomains>{
         HIRIntrinsicArgumentDomain::AtomicOrIntegerScalarStorage,
         HIRIntrinsicArgumentDomain::Any},
     2, HIRIntrinsicEffect::Opaque},
    {"atomicExchange",
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2},
     HIRIntrinsicArgumentDomain::Any,
     HIRIntrinsicArgumentCompatibilityRule::
         AtomicIntegerReadModifyWriteValueMatchesTarget,
     std::array<HIRIntrinsicArgumentDomain, kMaxHIRIntrinsicArgumentDomains>{
         HIRIntrinsicArgumentDomain::AtomicOrIntegerScalarStorage,
         HIRIntrinsicArgumentDomain::Any},
     2, HIRIntrinsicEffect::Opaque},
    {"atomicMax",
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2},
     HIRIntrinsicArgumentDomain::Any,
     HIRIntrinsicArgumentCompatibilityRule::
         AtomicIntegerReadModifyWriteValueMatchesTarget,
     std::array<HIRIntrinsicArgumentDomain, kMaxHIRIntrinsicArgumentDomains>{
         HIRIntrinsicArgumentDomain::AtomicOrIntegerScalarStorage,
         HIRIntrinsicArgumentDomain::Any},
     2, HIRIntrinsicEffect::Opaque},
    {"atomicMin",
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2},
     HIRIntrinsicArgumentDomain::Any,
     HIRIntrinsicArgumentCompatibilityRule::
         AtomicIntegerReadModifyWriteValueMatchesTarget,
     std::array<HIRIntrinsicArgumentDomain, kMaxHIRIntrinsicArgumentDomains>{
         HIRIntrinsicArgumentDomain::AtomicOrIntegerScalarStorage,
         HIRIntrinsicArgumentDomain::Any},
     2, HIRIntrinsicEffect::Opaque},
    {"atomicOr",
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2},
     HIRIntrinsicArgumentDomain::Any,
     HIRIntrinsicArgumentCompatibilityRule::
         AtomicIntegerReadModifyWriteValueMatchesTarget,
     std::array<HIRIntrinsicArgumentDomain, kMaxHIRIntrinsicArgumentDomains>{
         HIRIntrinsicArgumentDomain::AtomicOrIntegerScalarStorage,
         HIRIntrinsicArgumentDomain::Any},
     2, HIRIntrinsicEffect::Opaque},
    {"atomicXor",
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2},
     HIRIntrinsicArgumentDomain::Any,
     HIRIntrinsicArgumentCompatibilityRule::
         AtomicIntegerReadModifyWriteValueMatchesTarget,
     std::array<HIRIntrinsicArgumentDomain, kMaxHIRIntrinsicArgumentDomains>{
         HIRIntrinsicArgumentDomain::AtomicOrIntegerScalarStorage,
         HIRIntrinsicArgumentDomain::Any},
     2, HIRIntrinsicEffect::Opaque},
    {"atan", HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector},
    {"atan", HIRIntrinsicResultRule::FirstArgument, 2, std::size_t{2},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector,
     HIRIntrinsicArgumentCompatibilityRule::SameTypeAsFirst},
    // Workgroup barriers are synchronization points: void and opaque so
    // cleanup/constant-folding passes cannot treat them as pure values.
    {"barrier", HIRIntrinsicResultRule::Void, 0, std::size_t{0},
     HIRIntrinsicArgumentDomain::Any,
     HIRIntrinsicArgumentCompatibilityRule::None, {}, 0,
     HIRIntrinsicEffect::Opaque},
    {"ceil", HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector},
    {"clamp", HIRIntrinsicResultRule::FirstArgument, 3, std::size_t{3},
     HIRIntrinsicArgumentDomain::NumericScalarOrVector,
     HIRIntrinsicArgumentCompatibilityRule::
         SameTypeOrScalarComponentWithFirst},
    {"cos", HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector},
    {"cross", HIRIntrinsicResultRule::FirstArgument, 2, std::size_t{2},
     HIRIntrinsicArgumentDomain::FloatVector3,
     HIRIntrinsicArgumentCompatibilityRule::SameTypeAsFirst},
    {"distance", HIRIntrinsicResultRule::FixedFloat, 2, std::size_t{2},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector,
     HIRIntrinsicArgumentCompatibilityRule::SameTypeAsFirst},
    {"dot", HIRIntrinsicResultRule::FixedFloat, 2, std::size_t{2},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector,
     HIRIntrinsicArgumentCompatibilityRule::DotVectorPairSameWidth,
     std::array<HIRIntrinsicArgumentDomain, kMaxHIRIntrinsicArgumentDomains>{
         HIRIntrinsicArgumentDomain::FloatVector,
         HIRIntrinsicArgumentDomain::FloatVector},
     2},
    {"floor", HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector},
    {"fract", HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector},
    {"inverse", HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::FloatMatrix},
    {"length", HIRIntrinsicResultRule::FixedFloat, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::FloatScalar},
    {"length", HIRIntrinsicResultRule::FixedFloat, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::FloatVector},
    {"max", HIRIntrinsicResultRule::FirstArgument, 2, std::size_t{2},
     HIRIntrinsicArgumentDomain::NumericScalarOrVector,
     HIRIntrinsicArgumentCompatibilityRule::SameTypeOrScalarComponentWithFirst},
    {"min", HIRIntrinsicResultRule::FirstArgument, 2, std::size_t{2},
     HIRIntrinsicArgumentDomain::NumericScalarOrVector,
     HIRIntrinsicArgumentCompatibilityRule::SameTypeOrScalarComponentWithFirst},
    {"mix", HIRIntrinsicResultRule::FirstArgument, 3, std::size_t{3},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector,
     HIRIntrinsicArgumentCompatibilityRule::MixBlendCompatible,
     std::array<HIRIntrinsicArgumentDomain, kMaxHIRIntrinsicArgumentDomains>{
         HIRIntrinsicArgumentDomain::FloatScalarOrVector,
         HIRIntrinsicArgumentDomain::FloatScalarOrVector,
         HIRIntrinsicArgumentDomain::FloatScalarOrVector},
     3},
    {"normalize", HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector},
    {"pow", HIRIntrinsicResultRule::FirstArgument, 2, std::size_t{2},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector,
     HIRIntrinsicArgumentCompatibilityRule::SameTypeOrScalarComponentWithFirst},
    {"reflect", HIRIntrinsicResultRule::FirstArgument, 2, std::size_t{2},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector,
     HIRIntrinsicArgumentCompatibilityRule::SameTypeAsFirst},
    {"sin", HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector},
    {"smoothstep", HIRIntrinsicResultRule::FirstArgument, 3, std::size_t{3},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector,
     HIRIntrinsicArgumentCompatibilityRule::
         SameTypeOrScalarComponentWithFirst},
    {"sqrt", HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector},
    {"tan", HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::FloatScalarOrVector},
    {"transpose", HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1},
     HIRIntrinsicArgumentDomain::FloatMatrix},
    {"workgroupBarrier", HIRIntrinsicResultRule::Void, 0, std::size_t{0},
     HIRIntrinsicArgumentDomain::Any,
     HIRIntrinsicArgumentCompatibilityRule::None, {}, 0,
     HIRIntrinsicEffect::Opaque},
}};

HIRType fixedType(std::string name, SourceLocation location) {
  return HIRType{std::move(name), std::nullopt, std::move(location)};
}

std::string formatArgumentCount(std::size_t count) {
  return std::to_string(count) + (count == 1 ? " argument" : " arguments");
}

bool isFloatVectorType(std::string_view baseName) {
  if (!isVectorType(baseName)) {
    return false;
  }
  return isFloatLike(baseTypeName(scalarTypeForVector(baseName)));
}

bool isNumericValueType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  return isNumericScalarTypeName(baseName) || isNumericVectorTypeName(baseName) ||
         isMatrixType(baseName);
}

bool isNumericScalarOrVectorType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  return isNumericScalarTypeName(baseName) || isNumericVectorTypeName(baseName);
}

bool isFloatValueType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  return isFloatLike(baseName) || isFloatVectorType(baseName) ||
         isMatrixType(baseName);
}

bool isFloatScalarType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return false;
  }
  return isFloatLike(baseTypeName(type));
}

bool isFloatMatrixType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return false;
  }
  return isMatrixType(baseTypeName(type));
}

bool isFloatScalarOrVectorType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  return isFloatLike(baseName) || isFloatVectorType(baseName);
}

bool isFloatVectorType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  return isFloatVectorType(std::string_view{baseName});
}

bool isFloatVector3Type(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  const std::optional<std::size_t> width = vectorWidthFromName(baseName);
  return width.has_value() && *width == 3 &&
         isFloatVectorType(std::string_view{baseName});
}

bool acceptsArgumentDomain(HIRIntrinsicArgumentDomain domain,
                           const HIRType &type) {
  if (type.name.empty()) {
    return true;
  }
  switch (domain) {
  case HIRIntrinsicArgumentDomain::Any:
    return true;
  case HIRIntrinsicArgumentDomain::NumericValue:
    return isNumericValueType(type);
  case HIRIntrinsicArgumentDomain::FloatValue:
    return isFloatValueType(type);
  case HIRIntrinsicArgumentDomain::FloatScalar:
    return isFloatScalarType(type);
  case HIRIntrinsicArgumentDomain::FloatMatrix:
    return isFloatMatrixType(type);
  case HIRIntrinsicArgumentDomain::NumericScalarOrVector:
    return isNumericScalarOrVectorType(type);
  case HIRIntrinsicArgumentDomain::FloatScalarOrVector:
    return isFloatScalarOrVectorType(type);
  case HIRIntrinsicArgumentDomain::FloatVector:
    return isFloatVectorType(type);
  case HIRIntrinsicArgumentDomain::FloatVector3:
    return isFloatVector3Type(type);
  case HIRIntrinsicArgumentDomain::AtomicIntegerStorage:
    return isAtomicIntegerScalarType(type);
  case HIRIntrinsicArgumentDomain::AtomicOrIntegerScalarStorage:
    return isAtomicIntegerScalarType(type) || isIntegerScalarType(type);
  }
  return true;
}

std::optional<std::size_t> floatingVectorWidth(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return std::nullopt;
  }
  const std::string baseName = baseTypeName(type);
  if (!isFloatVectorType(std::string_view{baseName})) {
    return std::nullopt;
  }
  return vectorWidthFromName(baseName);
}

std::string formatArgumentTypeExpectation(const HIRType &type) {
  return "'" + formatType(type) + "'";
}

bool isScalarComponentTypeOf(const HIRType &scalar, const HIRType &aggregate) {
  if (scalar.name.empty() || aggregate.name.empty() ||
      scalar.arraySize.has_value() || aggregate.arraySize.has_value()) {
    return false;
  }
  const std::string aggregateBaseName = baseTypeName(aggregate);
  if (!isVectorType(aggregateBaseName)) {
    return false;
  }
  return sameType(scalar, scalarTypeForVector(aggregateBaseName));
}

std::string formatFirstArgumentResultCompatibilityExpectation(
    const HIRType &firstArgumentType) {
  std::string expectation =
      "argument 0 result type " +
      formatArgumentTypeExpectation(firstArgumentType);
  if (firstArgumentType.name.empty() || firstArgumentType.arraySize.has_value()) {
    return expectation;
  }
  const std::string firstBaseName = baseTypeName(firstArgumentType);
  if (!isVectorType(firstBaseName)) {
    return expectation;
  }
  return expectation + " or scalar component type " +
         formatArgumentTypeExpectation(scalarTypeForVector(firstBaseName));
}

std::optional<HIRIntrinsicArgumentTypeIssue> checkDotVectorPairSameWidth(
    const std::vector<HIRType> &argumentTypes) {
  if (argumentTypes.size() < 2) {
    return std::nullopt;
  }
  const std::optional<std::size_t> leftWidth =
      floatingVectorWidth(argumentTypes[0]);
  if (!leftWidth.has_value()) {
    if (argumentTypes[0].name.empty()) {
      return std::nullopt;
    }
    return HIRIntrinsicArgumentTypeIssue{
        0, "a floating-point vector type", argumentTypes[0]};
  }
  const std::optional<std::size_t> rightWidth =
      floatingVectorWidth(argumentTypes[1]);
  if (!rightWidth.has_value()) {
    if (argumentTypes[1].name.empty()) {
      return std::nullopt;
    }
    return HIRIntrinsicArgumentTypeIssue{
        1, "a floating-point vector type", argumentTypes[1]};
  }
  if (*leftWidth != *rightWidth) {
    return HIRIntrinsicArgumentTypeIssue{
        1, "a floating-point vector with width " +
               std::to_string(*leftWidth),
        argumentTypes[1]};
  }
  return std::nullopt;
}

std::optional<HIRIntrinsicArgumentTypeIssue>
checkSameTypeOrScalarComponentWithFirst(
    const std::vector<HIRType> &argumentTypes) {
  for (std::size_t index = 1; index < argumentTypes.size(); ++index) {
    if (argumentTypes[0].name.empty() || argumentTypes[index].name.empty()) {
      continue;
    }
    if (sameType(argumentTypes[0], argumentTypes[index]) ||
        isScalarComponentTypeOf(argumentTypes[index], argumentTypes[0])) {
      continue;
    }
    return HIRIntrinsicArgumentTypeIssue{
        index,
        "a type matching " +
            formatFirstArgumentResultCompatibilityExpectation(argumentTypes[0]),
        argumentTypes[index]};
  }
  return std::nullopt;
}

std::optional<HIRIntrinsicArgumentTypeIssue>
checkSameTypeAsFirst(const std::vector<HIRType> &argumentTypes) {
  for (std::size_t index = 1; index < argumentTypes.size(); ++index) {
    if (argumentTypes[0].name.empty() || argumentTypes[index].name.empty()) {
      continue;
    }
    if (sameType(argumentTypes[0], argumentTypes[index])) {
      continue;
    }
    return HIRIntrinsicArgumentTypeIssue{
        index,
        "a type matching argument 0 type " +
            formatArgumentTypeExpectation(argumentTypes[0]),
        argumentTypes[index]};
  }
  return std::nullopt;
}

std::optional<HIRIntrinsicArgumentTypeIssue>
checkMixBlendCompatible(const std::vector<HIRType> &argumentTypes) {
  if (argumentTypes.size() > 1 && !argumentTypes[0].name.empty() &&
      !argumentTypes[1].name.empty() && !sameType(argumentTypes[0],
                                                  argumentTypes[1]) &&
      !isScalarComponentTypeOf(argumentTypes[1], argumentTypes[0])) {
    return HIRIntrinsicArgumentTypeIssue{
        1,
        "a value matching " +
            formatFirstArgumentResultCompatibilityExpectation(argumentTypes[0]),
        argumentTypes[1]};
  }
  if (argumentTypes.size() > 2 && !argumentTypes[0].name.empty() &&
      !argumentTypes[2].name.empty() && !sameType(argumentTypes[0],
                                                  argumentTypes[2]) &&
      !isScalarComponentTypeOf(argumentTypes[2], argumentTypes[0])) {
    return HIRIntrinsicArgumentTypeIssue{
        2,
        "a blend factor matching " +
            formatFirstArgumentResultCompatibilityExpectation(argumentTypes[0]),
        argumentTypes[2]};
  }
  return std::nullopt;
}

std::optional<HIRIntrinsicArgumentTypeIssue>
checkAtomicPayloadMatchesFirst(const std::vector<HIRType> &argumentTypes) {
  if (argumentTypes.size() < 2) {
    return std::nullopt;
  }
  if (argumentTypes[0].name.empty()) {
    return std::nullopt;
  }
  const std::optional<HIRType> payload = atomicPayloadType(argumentTypes[0]);
  if (!payload.has_value() || !isAtomicIntegerScalarType(argumentTypes[0])) {
    return HIRIntrinsicArgumentTypeIssue{
        0, "an atomic<int> or atomic<uint> scalar storage type",
        argumentTypes[0]};
  }
  if (argumentTypes[1].name.empty()) {
    return std::nullopt;
  }
  if (!sameType(*payload, argumentTypes[1])) {
    return HIRIntrinsicArgumentTypeIssue{
        1, "the atomic payload type " + formatArgumentTypeExpectation(*payload),
        argumentTypes[1]};
  }
  return std::nullopt;
}

std::optional<HIRType> atomicIntegerReadModifyWriteValueType(
    const HIRType &targetType) {
  if (isAtomicIntegerScalarType(targetType)) {
    return atomicPayloadType(targetType);
  }
  if (isIntegerScalarType(targetType)) {
    return stripTypeQualifier(targetType);
  }
  return std::nullopt;
}

std::optional<HIRType> atomicIntegerReadModifyWriteOldValueType(
    const HIRType &targetType, SourceLocation location) {
  std::optional<HIRType> result =
      atomicIntegerReadModifyWriteValueType(targetType);
  if (!result.has_value()) {
    return std::nullopt;
  }
  result->location = std::move(location);
  return result;
}

std::optional<HIRIntrinsicArgumentTypeIssue>
checkAtomicIntegerReadModifyWriteValueMatchesTarget(
    const std::vector<HIRType> &argumentTypes) {
  if (argumentTypes.size() < 2) {
    return std::nullopt;
  }
  if (argumentTypes[0].name.empty()) {
    return std::nullopt;
  }
  const std::optional<HIRType> valueType =
      atomicIntegerReadModifyWriteValueType(argumentTypes[0]);
  if (!valueType.has_value()) {
    return HIRIntrinsicArgumentTypeIssue{
        0,
        "an atomic<int>, atomic<uint>, int, or uint scalar storage type",
        argumentTypes[0]};
  }
  if (argumentTypes[1].name.empty()) {
    return std::nullopt;
  }
  if (!sameType(*valueType, argumentTypes[1])) {
    return HIRIntrinsicArgumentTypeIssue{
        1, "the atomic target payload type " +
               formatArgumentTypeExpectation(*valueType),
        argumentTypes[1]};
  }
  return std::nullopt;
}

std::optional<HIRIntrinsicArgumentTypeIssue> findCompatibilityIssue(
    HIRIntrinsicArgumentCompatibilityRule rule,
    const std::vector<HIRType> &argumentTypes) {
  switch (rule) {
  case HIRIntrinsicArgumentCompatibilityRule::None:
    return std::nullopt;
  case HIRIntrinsicArgumentCompatibilityRule::DotVectorPairSameWidth:
    return checkDotVectorPairSameWidth(argumentTypes);
  case HIRIntrinsicArgumentCompatibilityRule::SameTypeAsFirst:
    return checkSameTypeAsFirst(argumentTypes);
  case HIRIntrinsicArgumentCompatibilityRule::SameTypeOrScalarComponentWithFirst:
    return checkSameTypeOrScalarComponentWithFirst(argumentTypes);
  case HIRIntrinsicArgumentCompatibilityRule::MixBlendCompatible:
    return checkMixBlendCompatible(argumentTypes);
  case HIRIntrinsicArgumentCompatibilityRule::AtomicPayloadMatchesFirst:
    return checkAtomicPayloadMatchesFirst(argumentTypes);
  case HIRIntrinsicArgumentCompatibilityRule::
      AtomicIntegerReadModifyWriteValueMatchesTarget:
    return checkAtomicIntegerReadModifyWriteValueMatchesTarget(argumentTypes);
  }
  return std::nullopt;
}

std::string joinExpectations(const std::vector<std::string> &expectations) {
  std::string result;
  for (std::size_t index = 0; index < expectations.size(); ++index) {
    if (index != 0) {
      result += index + 1 == expectations.size() ? " or " : ", ";
    }
    result += expectations[index];
  }
  return result;
}

void addUniqueExpectation(std::vector<std::string> &expectations,
                          const std::string &expectation) {
  if (std::find(expectations.begin(), expectations.end(), expectation) ==
      expectations.end()) {
    expectations.push_back(expectation);
  }
}

bool hasConcreteHIRIntrinsicArgumentType(const HIRType &type) {
  return !type.name.empty() || type.arraySize.has_value();
}

} // namespace

std::span<const HIRIntrinsicSignature>
lookupHIRIntrinsicSignatures(std::string_view name) {
  const auto first = std::find_if(
      kHIRIntrinsics.begin(), kHIRIntrinsics.end(),
      [name](const HIRIntrinsicSignature &signature) {
        return signature.name == name;
      });
  if (first == kHIRIntrinsics.end()) {
    return {};
  }
  const auto last = std::find_if(
      first, kHIRIntrinsics.end(),
      [name](const HIRIntrinsicSignature &signature) {
        return signature.name != name;
      });
  return std::span<const HIRIntrinsicSignature>{
      &*first, static_cast<std::size_t>(std::distance(first, last))};
}

const HIRIntrinsicSignature *lookupHIRIntrinsic(std::string_view name) {
  const std::span<const HIRIntrinsicSignature> signatures =
      lookupHIRIntrinsicSignatures(name);
  return signatures.empty() ? nullptr : &signatures.front();
}

bool isKnownHIRIntrinsic(std::string_view name) {
  return !lookupHIRIntrinsicSignatures(name).empty();
}

bool isPureHIRIntrinsic(const HIRIntrinsicSignature &signature) {
  return signature.effect == HIRIntrinsicEffect::Pure;
}

bool isHIRAtomicIntegerReadModifyWriteIntrinsic(std::string_view name) {
  return name == "atomicAdd" || name == "atomicAnd" ||
         name == "atomicExchange" || name == "atomicMax" ||
         name == "atomicMin" || name == "atomicOr" || name == "atomicXor";
}

std::string_view
hirAtomicIntegerReadModifyWriteCapabilityName(std::string_view name) {
  if (name == "atomicAdd") {
    return "atomic-add";
  }
  if (name == "atomicAnd") {
    return "atomic-and";
  }
  if (name == "atomicExchange") {
    return "atomic-exchange";
  }
  if (name == "atomicMax") {
    return "atomic-max";
  }
  if (name == "atomicMin") {
    return "atomic-min";
  }
  if (name == "atomicOr") {
    return "atomic-or";
  }
  if (name == "atomicXor") {
    return "atomic-xor";
  }
  return {};
}

std::string_view
hirAtomicIntegerReadModifyWriteDiagnosticStem(std::string_view name) {
  return hirAtomicIntegerReadModifyWriteCapabilityName(name);
}

std::string_view
hirAtomicIntegerReadModifyWriteValueTerm(std::string_view name) {
  return name == "atomicAdd" ? "delta" : "value";
}

std::optional<HIRIntrinsicEffect>
resolveHIRIntrinsicEffect(std::string_view name,
                          const std::vector<HIRType> &argumentTypes) {
  if (!std::all_of(argumentTypes.begin(), argumentTypes.end(),
                   hasConcreteHIRIntrinsicArgumentType)) {
    return std::nullopt;
  }
  const HIRIntrinsicSignature *signature =
      selectHIRIntrinsicSignature(name, argumentTypes);
  if (signature == nullptr) {
    return std::nullopt;
  }
  return signature->effect;
}

std::optional<HIRIntrinsicEffect>
resolveHIRIntrinsicEffect(std::string_view name,
                          const std::vector<HIRExpression> &arguments) {
  std::vector<HIRType> argumentTypes;
  argumentTypes.reserve(arguments.size());
  for (const HIRExpression &argument : arguments) {
    argumentTypes.push_back(argument.type);
  }
  return resolveHIRIntrinsicEffect(name, argumentTypes);
}

bool isPureHIRIntrinsicCall(std::string_view name,
                            const std::vector<HIRType> &argumentTypes) {
  const std::optional<HIRIntrinsicEffect> effect =
      resolveHIRIntrinsicEffect(name, argumentTypes);
  return effect.has_value() && *effect == HIRIntrinsicEffect::Pure;
}

bool isPureHIRIntrinsicCall(std::string_view name,
                            const std::vector<HIRExpression> &arguments) {
  const std::optional<HIRIntrinsicEffect> effect =
      resolveHIRIntrinsicEffect(name, arguments);
  return effect.has_value() && *effect == HIRIntrinsicEffect::Pure;
}

bool acceptsHIRIntrinsicArity(const HIRIntrinsicSignature &signature,
                              std::size_t arity) {
  if (arity < signature.minimumArity) {
    return false;
  }
  return !signature.maximumArity.has_value() ||
         arity <= *signature.maximumArity;
}

bool acceptsHIRIntrinsicArity(
    std::span<const HIRIntrinsicSignature> signatures, std::size_t arity) {
  return std::any_of(signatures.begin(), signatures.end(),
                     [arity](const HIRIntrinsicSignature &signature) {
                       return acceptsHIRIntrinsicArity(signature, arity);
                     });
}

std::string
formatHIRIntrinsicArityExpectation(const HIRIntrinsicSignature &signature) {
  if (signature.maximumArity.has_value() &&
      *signature.maximumArity == signature.minimumArity) {
    return "exactly " + formatArgumentCount(signature.minimumArity);
  }
  if (signature.maximumArity.has_value()) {
    return "between " + formatArgumentCount(signature.minimumArity) + " and " +
           formatArgumentCount(*signature.maximumArity);
  }
  return "at least " + formatArgumentCount(signature.minimumArity);
}

std::string formatHIRIntrinsicArityExpectation(
    std::span<const HIRIntrinsicSignature> signatures) {
  std::vector<std::string> expectations;
  for (const HIRIntrinsicSignature &signature : signatures) {
    addUniqueExpectation(expectations,
                         formatHIRIntrinsicArityExpectation(signature));
  }
  if (expectations.empty()) {
    return "a supported argument count";
  }
  return joinExpectations(expectations);
}

HIRIntrinsicArgumentDomain
hirIntrinsicArgumentDomainAt(const HIRIntrinsicSignature &signature,
                             std::size_t argumentIndex) {
  if (argumentIndex < signature.argumentDomainCount &&
      argumentIndex < signature.argumentDomains.size()) {
    return signature.argumentDomains[argumentIndex];
  }
  return signature.argumentDomain;
}

std::string formatHIRIntrinsicArgumentDomainExpectation(
    HIRIntrinsicArgumentDomain domain) {
  switch (domain) {
  case HIRIntrinsicArgumentDomain::Any:
    return "any argument type";
  case HIRIntrinsicArgumentDomain::NumericValue:
    return "a numeric scalar, vector, or matrix type";
  case HIRIntrinsicArgumentDomain::FloatValue:
    return "a floating-point scalar, vector, or matrix type";
  case HIRIntrinsicArgumentDomain::FloatScalar:
    return "a floating-point scalar type";
  case HIRIntrinsicArgumentDomain::FloatMatrix:
    return "a floating-point matrix type";
  case HIRIntrinsicArgumentDomain::NumericScalarOrVector:
    return "a numeric scalar or vector type";
  case HIRIntrinsicArgumentDomain::FloatScalarOrVector:
    return "a floating-point scalar or vector type";
  case HIRIntrinsicArgumentDomain::FloatVector:
    return "a floating-point vector type";
  case HIRIntrinsicArgumentDomain::FloatVector3:
    return "a 3-component floating-point vector type";
  case HIRIntrinsicArgumentDomain::AtomicIntegerStorage:
    return "an atomic<int> or atomic<uint> scalar storage type";
  case HIRIntrinsicArgumentDomain::AtomicOrIntegerScalarStorage:
    return "an atomic<int>, atomic<uint>, int, or uint scalar storage type";
  }
  return "a supported argument type";
}

std::optional<HIRIntrinsicArgumentTypeIssue>
findHIRIntrinsicArgumentTypeIssue(const HIRIntrinsicSignature &signature,
                                  const std::vector<HIRType> &argumentTypes) {
  for (std::size_t index = 0; index < argumentTypes.size(); ++index) {
    const HIRIntrinsicArgumentDomain domain =
        hirIntrinsicArgumentDomainAt(signature, index);
    if (domain == HIRIntrinsicArgumentDomain::Any ||
        acceptsArgumentDomain(domain, argumentTypes[index])) {
      continue;
    }
    return HIRIntrinsicArgumentTypeIssue{
        index, formatHIRIntrinsicArgumentDomainExpectation(domain),
        argumentTypes[index]};
  }
  return findCompatibilityIssue(signature.compatibilityRule, argumentTypes);
}

std::optional<HIRIntrinsicArgumentTypeIssue>
findHIRIntrinsicArgumentTypeIssue(
    std::span<const HIRIntrinsicSignature> signatures,
    const std::vector<HIRType> &argumentTypes) {
  std::optional<HIRIntrinsicArgumentTypeIssue> firstIssue;
  std::vector<std::string> expectations;
  for (const HIRIntrinsicSignature &signature : signatures) {
    if (!acceptsHIRIntrinsicArity(signature, argumentTypes.size())) {
      continue;
    }
    const std::optional<HIRIntrinsicArgumentTypeIssue> issue =
        findHIRIntrinsicArgumentTypeIssue(signature, argumentTypes);
    if (!issue.has_value()) {
      return std::nullopt;
    }
    if (!firstIssue.has_value()) {
      firstIssue = issue;
      expectations.push_back(issue->expectation);
      continue;
    }
    if (issue->argumentIndex == firstIssue->argumentIndex) {
      addUniqueExpectation(expectations, issue->expectation);
    }
  }
  if (firstIssue.has_value() && expectations.size() > 1) {
    firstIssue->expectation = joinExpectations(expectations);
  }
  return firstIssue;
}

const HIRIntrinsicSignature *selectHIRIntrinsicSignature(
    std::span<const HIRIntrinsicSignature> signatures,
    const std::vector<HIRType> &argumentTypes) {
  for (const HIRIntrinsicSignature &signature : signatures) {
    if (!acceptsHIRIntrinsicArity(signature, argumentTypes.size())) {
      continue;
    }
    if (!findHIRIntrinsicArgumentTypeIssue(signature, argumentTypes)
             .has_value()) {
      return &signature;
    }
  }
  return nullptr;
}

const HIRIntrinsicSignature *selectHIRIntrinsicSignature(
    std::string_view name, const std::vector<HIRType> &argumentTypes) {
  return selectHIRIntrinsicSignature(lookupHIRIntrinsicSignatures(name),
                                     argumentTypes);
}

std::optional<HIRType>
inferHIRIntrinsicResultType(const HIRIntrinsicSignature &signature,
                            const std::vector<HIRType> &argumentTypes,
                            SourceLocation location) {
  switch (signature.resultRule) {
  case HIRIntrinsicResultRule::Void:
    return fixedType("void", std::move(location));
  case HIRIntrinsicResultRule::FixedFloat:
    return fixedType("float", std::move(location));
  case HIRIntrinsicResultRule::FirstArgument:
    if (argumentTypes.empty()) {
      return std::nullopt;
    }
    return argumentTypes.front();
  case HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue:
    if (argumentTypes.empty()) {
      return std::nullopt;
    }
    return atomicIntegerReadModifyWriteOldValueType(argumentTypes.front(),
                                                    std::move(location));
  }
  return std::nullopt;
}

std::optional<HIRType>
inferHIRIntrinsicResultType(std::string_view name,
                            const std::vector<HIRType> &argumentTypes,
                            SourceLocation location) {
  const HIRIntrinsicSignature *signature =
      selectHIRIntrinsicSignature(name, argumentTypes);
  if (signature == nullptr) {
    return std::nullopt;
  }
  return inferHIRIntrinsicResultType(*signature, argumentTypes,
                                     std::move(location));
}

std::optional<HIRType>
inferHIRIntrinsicResultType(std::string_view name,
                            const std::vector<HIRExpression> &arguments,
                            SourceLocation location) {
  std::vector<HIRType> argumentTypes;
  argumentTypes.reserve(arguments.size());
  for (const HIRExpression &argument : arguments) {
    argumentTypes.push_back(argument.type);
  }
  return inferHIRIntrinsicResultType(name, argumentTypes, std::move(location));
}

} // namespace crossgl
