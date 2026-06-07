#pragma once

#include "crossgl/HIR/HIR.h"

#include <array>
#include <cstddef>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace crossgl {

inline constexpr std::size_t kMaxHIRIntrinsicArgumentDomains = 4;

enum class HIRIntrinsicResultRule {
  Void,
  FixedFloat,
  FirstArgument,
  AtomicIntegerReadModifyWriteOldValue,
};

enum class HIRIntrinsicArgumentDomain {
  Any,
  NumericValue,
  FloatValue,
  FloatScalar,
  NumericScalarOrVector,
  FloatScalarOrVector,
  FloatVector,
  FloatVector3,
  AtomicIntegerStorage,
  AtomicOrIntegerScalarStorage,
};

enum class HIRIntrinsicArgumentCompatibilityRule {
  None,
  DotVectorPairSameWidth,
  SameTypeAsFirst,
  SameTypeOrScalarComponentWithFirst,
  MixBlendCompatible,
  AtomicPayloadMatchesFirst,
  AtomicIntegerReadModifyWriteValueMatchesTarget,
};

enum class HIRIntrinsicEffect {
  Pure,
  Opaque,
};

struct HIRIntrinsicSignature {
  std::string_view name;
  HIRIntrinsicResultRule resultRule;
  std::size_t minimumArity = 0;
  std::optional<std::size_t> maximumArity;
  HIRIntrinsicArgumentDomain argumentDomain =
      HIRIntrinsicArgumentDomain::Any;
  HIRIntrinsicArgumentCompatibilityRule compatibilityRule =
      HIRIntrinsicArgumentCompatibilityRule::None;
  std::array<HIRIntrinsicArgumentDomain, kMaxHIRIntrinsicArgumentDomains>
      argumentDomains = {};
  std::size_t argumentDomainCount = 0;
  HIRIntrinsicEffect effect = HIRIntrinsicEffect::Pure;
};

struct HIRIntrinsicArgumentTypeIssue {
  std::size_t argumentIndex = 0;
  std::string expectation;
  HIRType actualType;
};

// Known intrinsic names may map to multiple candidate signatures. Use
// selectHIRIntrinsicSignature when concrete argument types are available.
std::span<const HIRIntrinsicSignature>
lookupHIRIntrinsicSignatures(std::string_view name);
const HIRIntrinsicSignature *lookupHIRIntrinsic(std::string_view name);
bool isKnownHIRIntrinsic(std::string_view name);
bool isPureHIRIntrinsic(const HIRIntrinsicSignature &signature);
bool isHIRAtomicIntegerReadModifyWriteIntrinsic(std::string_view name);
std::string_view
hirAtomicIntegerReadModifyWriteCapabilityName(std::string_view name);
std::string_view
hirAtomicIntegerReadModifyWriteDiagnosticStem(std::string_view name);
std::string_view
hirAtomicIntegerReadModifyWriteValueTerm(std::string_view name);
std::optional<HIRIntrinsicEffect>
resolveHIRIntrinsicEffect(std::string_view name,
                          const std::vector<HIRType> &argumentTypes);
std::optional<HIRIntrinsicEffect>
resolveHIRIntrinsicEffect(std::string_view name,
                          const std::vector<HIRExpression> &arguments);
bool isPureHIRIntrinsicCall(std::string_view name,
                            const std::vector<HIRType> &argumentTypes);
bool isPureHIRIntrinsicCall(std::string_view name,
                            const std::vector<HIRExpression> &arguments);
bool acceptsHIRIntrinsicArity(const HIRIntrinsicSignature &signature,
                              std::size_t arity);
bool acceptsHIRIntrinsicArity(
    std::span<const HIRIntrinsicSignature> signatures, std::size_t arity);
std::string
formatHIRIntrinsicArityExpectation(const HIRIntrinsicSignature &signature);
std::string formatHIRIntrinsicArityExpectation(
    std::span<const HIRIntrinsicSignature> signatures);
HIRIntrinsicArgumentDomain
hirIntrinsicArgumentDomainAt(const HIRIntrinsicSignature &signature,
                             std::size_t argumentIndex);
std::string formatHIRIntrinsicArgumentDomainExpectation(
    HIRIntrinsicArgumentDomain domain);
std::optional<HIRIntrinsicArgumentTypeIssue>
findHIRIntrinsicArgumentTypeIssue(const HIRIntrinsicSignature &signature,
                                  const std::vector<HIRType> &argumentTypes);
std::optional<HIRIntrinsicArgumentTypeIssue>
findHIRIntrinsicArgumentTypeIssue(
    std::span<const HIRIntrinsicSignature> signatures,
    const std::vector<HIRType> &argumentTypes);

const HIRIntrinsicSignature *selectHIRIntrinsicSignature(
    std::span<const HIRIntrinsicSignature> signatures,
    const std::vector<HIRType> &argumentTypes);
const HIRIntrinsicSignature *selectHIRIntrinsicSignature(
    std::string_view name, const std::vector<HIRType> &argumentTypes);

std::optional<HIRType>
inferHIRIntrinsicResultType(const HIRIntrinsicSignature &signature,
                            const std::vector<HIRType> &argumentTypes,
                            SourceLocation location = {});

std::optional<HIRType>
inferHIRIntrinsicResultType(std::string_view name,
                            const std::vector<HIRType> &argumentTypes,
                            SourceLocation location = {});

std::optional<HIRType>
inferHIRIntrinsicResultType(std::string_view name,
                            const std::vector<HIRExpression> &arguments,
                            SourceLocation location = {});

} // namespace crossgl
