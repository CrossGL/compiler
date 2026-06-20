#pragma once

#include "crossgl/HIR/HIR.h"

#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace crossgl {

struct FoldedHIRScalar {
  double number = 0.0;
  bool boolean = false;
  bool isBool = false;
  bool isInteger = true;
};

struct FoldedHIRValue {
  std::vector<FoldedHIRScalar> components;
};

struct HIRScalarFoldOptions {
  bool foldIntrinsicCalls = false;
};

using HIRScalarConstantMap =
    std::unordered_map<std::string, FoldedHIRScalar>;
using HIRValueConstantMap = std::unordered_map<std::string, FoldedHIRValue>;

bool isFoldableHIRScalarType(const HIRType &type);
bool isFoldableHIRVectorType(const HIRType &type);
std::optional<FoldedHIRScalar> parseFoldedHIRScalar(std::string_view text);
std::string formatFoldedHIRScalar(const FoldedHIRScalar &value);
std::optional<std::string>
formatFoldedHIRScalarForType(const FoldedHIRScalar &value,
                             const HIRType &type);

std::optional<std::string> foldHIRIntegerIndexExpression(
    const HIRExpression &expression, const HIRScalarConstantMap &constantValues,
    HIRScalarFoldOptions options = {},
    const HIRValueConstantMap *valueConstants = nullptr);

std::optional<FoldedHIRValue> foldHIRValueExpression(
    const HIRExpression &expression, const HIRScalarConstantMap &constantValues,
    HIRScalarFoldOptions options = {},
    const HIRValueConstantMap *valueConstants = nullptr);

std::optional<FoldedHIRScalar> foldHIRScalarExpression(
    const HIRExpression &expression, const HIRScalarConstantMap &constantValues,
    HIRScalarFoldOptions options = {},
    const HIRValueConstantMap *valueConstants = nullptr);

std::optional<FoldedHIRValue> foldHIRValueIntrinsicCall(
    const HIRExpression &expression, const HIRScalarConstantMap &constantValues,
    HIRScalarFoldOptions options = {},
    const HIRValueConstantMap *valueConstants = nullptr);

std::optional<FoldedHIRScalar> foldHIRScalarIntrinsicCall(
    const HIRExpression &expression, const HIRScalarConstantMap &constantValues,
    HIRScalarFoldOptions options = {},
    const HIRValueConstantMap *valueConstants = nullptr);

} // namespace crossgl
