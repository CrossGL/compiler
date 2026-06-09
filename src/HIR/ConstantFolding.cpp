#include "crossgl/HIR/ConstantFolding.h"
#include "crossgl/HIR/Intrinsics.h"
#include "crossgl/HIR/SideEffects.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <sstream>
#include <utility>
#include <vector>

namespace crossgl {
namespace {

bool isFloatFoldedHIRScalarType(const HIRType &type) {
  return !type.name.empty() && !type.arraySize.has_value() &&
         isFloatLike(baseTypeName(type));
}

bool isFloatFoldedHIRVectorType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  return isVectorType(baseName) &&
         isFloatLike(baseTypeName(scalarTypeForVector(baseName)));
}

bool isFoldedHIRScalarValue(const FoldedHIRValue &value) {
  return value.components.size() == 1;
}

bool isFoldedHIRVectorValue(const FoldedHIRValue &value) {
  return value.components.size() > 1;
}

double numericValue(const FoldedHIRScalar &value) {
  return value.isBool ? (value.boolean ? 1.0 : 0.0) : value.number;
}

bool truthValue(const FoldedHIRScalar &value) {
  return value.isBool ? value.boolean : value.number != 0.0;
}

FoldedHIRValue makeFoldedHIRScalarValue(FoldedHIRScalar scalar) {
  FoldedHIRValue value;
  value.components.push_back(std::move(scalar));
  return value;
}

std::optional<FoldedHIRScalar> foldedHIRValueAsScalar(
    const FoldedHIRValue &value) {
  if (!isFoldedHIRScalarValue(value)) {
    return std::nullopt;
  }
  return value.components.front();
}

std::optional<FoldedHIRValue> foldHIRConstructorValue(
    const HIRExpression &expression, const HIRScalarConstantMap &constantValues,
    HIRScalarFoldOptions options,
    const HIRValueConstantMap *valueConstants) {
  if (expression.kind != HIRExpressionKind::Constructor ||
      !isFoldableHIRVectorType(expression.type)) {
    return std::nullopt;
  }

  const std::optional<std::size_t> width =
      vectorWidthFromName(baseTypeName(expression.type));
  if (!width.has_value() || expression.children.empty()) {
    return std::nullopt;
  }

  FoldedHIRValue folded;
  for (const HIRExpression &child : expression.children) {
    std::optional<FoldedHIRValue> childValue =
        foldHIRValueExpression(child, constantValues, options, valueConstants);
    if (!childValue.has_value()) {
      return std::nullopt;
    }
    for (const FoldedHIRScalar &component : childValue->components) {
      if (component.isBool) {
        return std::nullopt;
      }
      folded.components.push_back(component);
    }
  }

  if (folded.components.size() != *width) {
    return std::nullopt;
  }
  return folded;
}

std::optional<std::vector<std::size_t>>
foldedHIRSwizzleComponentIndices(const HIRType &base,
                                 std::string_view member) {
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

std::optional<FoldedHIRValue> foldHIRMemberAccessValue(
    const HIRExpression &expression, const HIRScalarConstantMap &constantValues,
    HIRScalarFoldOptions options,
    const HIRValueConstantMap *valueConstants) {
  if (expression.kind != HIRExpressionKind::MemberAccess ||
      expression.children.empty()) {
    return std::nullopt;
  }

  const HIRExpression &base = expression.children.front();
  const std::optional<std::vector<std::size_t>> indices =
      foldedHIRSwizzleComponentIndices(base.type, expression.value);
  if (!indices.has_value()) {
    return std::nullopt;
  }

  std::optional<FoldedHIRValue> baseValue =
      foldHIRValueExpression(base, constantValues, options, valueConstants);
  if (!baseValue.has_value() || !isFoldedHIRVectorValue(*baseValue)) {
    return std::nullopt;
  }

  FoldedHIRValue folded;
  folded.components.reserve(indices->size());
  for (const std::size_t index : *indices) {
    if (index >= baseValue->components.size()) {
      return std::nullopt;
    }
    folded.components.push_back(baseValue->components[index]);
  }

  if (folded.components.size() == 1) {
    return isFoldableHIRScalarType(expression.type)
               ? std::optional<FoldedHIRValue>{std::move(folded)}
               : std::nullopt;
  }
  return isFoldableHIRVectorType(expression.type)
             ? std::optional<FoldedHIRValue>{std::move(folded)}
             : std::nullopt;
}

} // namespace

bool isFoldableHIRScalarType(const HIRType &type) {
  return !type.name.empty() && !type.arraySize.has_value() &&
         isNumericScalarTypeName(baseTypeName(type));
}

bool isFoldableHIRVectorType(const HIRType &type) {
  if (type.name.empty() || type.arraySize.has_value()) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  return isVectorType(baseName) &&
         isNumericScalarTypeName(baseTypeName(scalarTypeForVector(baseName)));
}

bool isFoldedScalarIntegerLiteral(std::string_view text) {
  return text.find('.') == std::string_view::npos &&
         text.find('e') == std::string_view::npos &&
         text.find('E') == std::string_view::npos &&
         text.find('p') == std::string_view::npos &&
         text.find('P') == std::string_view::npos &&
         (text.empty() || (text.back() != 'f' && text.back() != 'F'));
}

std::optional<FoldedHIRScalar> parseFoldedHIRScalar(std::string_view text) {
  if (text == "true") {
    return FoldedHIRScalar{0.0, true, true, true};
  }
  if (text == "false") {
    return FoldedHIRScalar{0.0, false, true, true};
  }

  try {
    const std::string value(text);
    std::size_t parsed = 0;
    const double number = std::stod(value, &parsed);
    if (parsed != value.size() || !std::isfinite(number)) {
      return std::nullopt;
    }
    return FoldedHIRScalar{number, false, false,
                           isFoldedScalarIntegerLiteral(text)};
  } catch (...) {
    return std::nullopt;
  }
}

std::string formatFoldedHIRScalar(const FoldedHIRScalar &value) {
  if (value.isBool) {
    return value.boolean ? "true" : "false";
  }

  double number = std::fabs(value.number) < 0.000000001 ? 0.0 : value.number;
  const double rounded = std::round(number);
  if (value.isInteger || std::fabs(number - rounded) < 0.000000001) {
    return std::to_string(static_cast<long long>(rounded));
  }

  std::ostringstream out;
  out << std::setprecision(12) << number;
  std::string text = out.str();
  if (text.find('.') != std::string::npos) {
    while (!text.empty() && text.back() == '0') {
      text.pop_back();
    }
    if (!text.empty() && text.back() == '.') {
      text.pop_back();
    }
  }
  return text;
}

std::optional<std::string>
formatFoldedHIRScalarForType(const FoldedHIRScalar &value,
                             const HIRType &type) {
  const std::string baseName = baseTypeName(type);
  if (value.isBool) {
    if (baseName == "bool" && !type.arraySize.has_value()) {
      return formatFoldedHIRScalar(value);
    }
    return std::nullopt;
  }

  if (!isFoldableHIRScalarType(type) || !std::isfinite(value.number)) {
    return std::nullopt;
  }

  if (baseName == "int" || baseName == "uint") {
    const double rounded = std::round(value.number);
    if (std::fabs(value.number - rounded) > 0.000000001 ||
        (baseName == "uint" && rounded < 0.0)) {
      return std::nullopt;
    }
    return std::to_string(static_cast<long long>(rounded));
  }

  return formatFoldedHIRScalar(value);
}

std::optional<FoldedHIRValue> foldHIRValueIntrinsicCall(
    const HIRExpression &expression, const HIRScalarConstantMap &constantValues,
    HIRScalarFoldOptions options,
    const HIRValueConstantMap *valueConstants) {
  if (!options.foldIntrinsicCalls || expression.kind != HIRExpressionKind::Call ||
      (!isFoldableHIRScalarType(expression.type) &&
       !isFoldableHIRVectorType(expression.type))) {
    return std::nullopt;
  }

  std::vector<HIRType> argumentTypes;
  argumentTypes.reserve(expression.children.size());
  std::vector<FoldedHIRValue> arguments;
  arguments.reserve(expression.children.size());
  for (const HIRExpression &child : expression.children) {
    argumentTypes.push_back(child.type);
    std::optional<FoldedHIRValue> folded =
        foldHIRValueExpression(child, constantValues, options, valueConstants);
    if (!folded.has_value()) {
      return std::nullopt;
    }
    arguments.push_back(*folded);
  }
  const HIRIntrinsicSignature *signature =
      selectHIRIntrinsicSignature(expression.value, argumentTypes);
  if (signature == nullptr) {
    return std::nullopt;
  }
  std::optional<HIRType> inferredType =
      inferHIRIntrinsicResultType(*signature, argumentTypes,
                                  expression.location);
  if (!inferredType.has_value() || !sameType(*inferredType, expression.type)) {
    return std::nullopt;
  }

  const std::string_view name = expression.value;
  auto scalarValue = [](double number,
                        bool isInteger) -> std::optional<FoldedHIRScalar> {
    if (!std::isfinite(number)) {
      return std::nullopt;
    }
    return FoldedHIRScalar{number, false, false, isInteger};
  };
  auto foldedScalarValue =
      [&](double number, bool isInteger) -> std::optional<FoldedHIRValue> {
    std::optional<FoldedHIRScalar> scalar = scalarValue(number, isInteger);
    return scalar.has_value()
               ? std::optional<FoldedHIRValue>(
                     makeFoldedHIRScalarValue(*scalar))
               : std::nullopt;
  };
  auto foldedVectorValue =
      [&](const std::vector<double> &numbers,
          bool isInteger) -> std::optional<FoldedHIRValue> {
    FoldedHIRValue value;
    value.components.reserve(numbers.size());
    for (const double number : numbers) {
      std::optional<FoldedHIRScalar> component =
          scalarValue(number, isInteger);
      if (!component.has_value()) {
        return std::nullopt;
      }
      value.components.push_back(*component);
    }
    return value;
  };
  auto allArgumentComponentsInteger = [&]() {
    for (const FoldedHIRValue &value : arguments) {
      for (const FoldedHIRScalar &component : value.components) {
        if (!component.isInteger) {
          return false;
        }
      }
    }
    return true;
  };
  auto scalarFloatValue = [&](double number) -> std::optional<FoldedHIRValue> {
    if (!std::isfinite(number)) {
      return std::nullopt;
    }
    return makeFoldedHIRScalarValue(
        FoldedHIRScalar{number, false, false, false});
  };
  auto scalarArgument = [&](std::size_t index)
      -> std::optional<FoldedHIRScalar> {
    if (index >= arguments.size()) {
      return std::nullopt;
    }
    std::optional<FoldedHIRScalar> scalar =
        foldedHIRValueAsScalar(arguments[index]);
    if (!scalar.has_value() || scalar->isBool) {
      return std::nullopt;
    }
    return scalar;
  };
  auto floatVectorArgument =
      [&](std::size_t index) -> std::optional<std::vector<FoldedHIRScalar>> {
        if (index >= arguments.size() ||
            !isFloatFoldedHIRVectorType(argumentTypes[index]) ||
            !isFoldedHIRVectorValue(arguments[index])) {
          return std::nullopt;
        }
        for (const FoldedHIRScalar &component : arguments[index].components) {
          if (component.isBool) {
            return std::nullopt;
          }
        }
        return arguments[index].components;
      };

  if (isFoldableHIRScalarType(expression.type)) {
    const bool floatResult = isFloatFoldedHIRScalarType(expression.type);
    const bool integerResult =
        !floatResult &&
        std::all_of(arguments.begin(), arguments.end(),
                    [](const FoldedHIRValue &value) {
                      return isFoldedHIRScalarValue(value) &&
                             value.components.front().isInteger;
                    });
    auto result = [&](double number) -> std::optional<FoldedHIRValue> {
      return foldedScalarValue(number, integerResult);
    };

    if (name == "abs" && arguments.size() == 1) {
      std::optional<FoldedHIRScalar> value = scalarArgument(0);
      return value.has_value() ? result(std::fabs(value->number))
                               : std::nullopt;
    }
    if (name == "min" && arguments.size() == 2) {
      std::optional<FoldedHIRScalar> left = scalarArgument(0);
      std::optional<FoldedHIRScalar> right = scalarArgument(1);
      return left.has_value() && right.has_value()
                 ? result(std::min(left->number, right->number))
                 : std::nullopt;
    }
    if (name == "max" && arguments.size() == 2) {
      std::optional<FoldedHIRScalar> left = scalarArgument(0);
      std::optional<FoldedHIRScalar> right = scalarArgument(1);
      return left.has_value() && right.has_value()
                 ? result(std::max(left->number, right->number))
                 : std::nullopt;
    }
    if (name == "clamp" && arguments.size() == 3) {
      std::optional<FoldedHIRScalar> value = scalarArgument(0);
      std::optional<FoldedHIRScalar> lower = scalarArgument(1);
      std::optional<FoldedHIRScalar> upper = scalarArgument(2);
      return value.has_value() && lower.has_value() && upper.has_value()
                 ? result(std::min(std::max(value->number, lower->number),
                                   upper->number))
                 : std::nullopt;
    }
    if (name == "cos" && arguments.size() == 1) {
      std::optional<FoldedHIRScalar> value = scalarArgument(0);
      return value.has_value() ? scalarFloatValue(std::cos(value->number))
                               : std::nullopt;
    }
    if (name == "sin" && arguments.size() == 1) {
      std::optional<FoldedHIRScalar> value = scalarArgument(0);
      return value.has_value() ? scalarFloatValue(std::sin(value->number))
                               : std::nullopt;
    }
    if (name == "tan" && arguments.size() == 1) {
      std::optional<FoldedHIRScalar> value = scalarArgument(0);
      return value.has_value() ? scalarFloatValue(std::tan(value->number))
                               : std::nullopt;
    }
    if (name == "sqrt" && arguments.size() == 1) {
      std::optional<FoldedHIRScalar> value = scalarArgument(0);
      if (!value.has_value() || value->number < 0.0) {
        return std::nullopt;
      }
      return scalarFloatValue(std::sqrt(value->number));
    }
    if (name == "pow" && arguments.size() == 2) {
      std::optional<FoldedHIRScalar> left = scalarArgument(0);
      std::optional<FoldedHIRScalar> right = scalarArgument(1);
      return left.has_value() && right.has_value()
                 ? scalarFloatValue(std::pow(left->number, right->number))
                 : std::nullopt;
    }
    if (name == "fract" && arguments.size() == 1) {
      std::optional<FoldedHIRScalar> value = scalarArgument(0);
      if (!value.has_value()) {
        return std::nullopt;
      }
      const double number = value->number;
      return scalarFloatValue(number - std::floor(number));
    }
    if (name == "floor" && arguments.size() == 1) {
      std::optional<FoldedHIRScalar> value = scalarArgument(0);
      return value.has_value() ? scalarFloatValue(std::floor(value->number))
                               : std::nullopt;
    }
    if (name == "ceil" && arguments.size() == 1) {
      std::optional<FoldedHIRScalar> value = scalarArgument(0);
      return value.has_value() ? scalarFloatValue(std::ceil(value->number))
                               : std::nullopt;
    }
    if (name == "length" && arguments.size() == 1) {
      if (std::optional<FoldedHIRScalar> value = scalarArgument(0)) {
        return scalarFloatValue(std::fabs(value->number));
      }
      std::optional<std::vector<FoldedHIRScalar>> vector =
          floatVectorArgument(0);
      if (!vector.has_value()) {
        return std::nullopt;
      }
      double sumSquares = 0.0;
      for (const FoldedHIRScalar &component : *vector) {
        sumSquares += component.number * component.number;
      }
      return scalarFloatValue(std::sqrt(sumSquares));
    }
    if (name == "atan" && arguments.size() == 1) {
      std::optional<FoldedHIRScalar> value = scalarArgument(0);
      return value.has_value() ? scalarFloatValue(std::atan(value->number))
                               : std::nullopt;
    }
    if (name == "atan" && arguments.size() == 2) {
      std::optional<FoldedHIRScalar> y = scalarArgument(0);
      std::optional<FoldedHIRScalar> x = scalarArgument(1);
      return y.has_value() && x.has_value()
                 ? scalarFloatValue(std::atan2(y->number, x->number))
                 : std::nullopt;
    }
    if (name == "distance" && arguments.size() == 2) {
      std::optional<FoldedHIRScalar> left = scalarArgument(0);
      std::optional<FoldedHIRScalar> right = scalarArgument(1);
      if (left.has_value() && right.has_value()) {
        return scalarFloatValue(std::fabs(left->number - right->number));
      }

      std::optional<std::vector<FoldedHIRScalar>> leftVector =
          floatVectorArgument(0);
      std::optional<std::vector<FoldedHIRScalar>> rightVector =
          floatVectorArgument(1);
      if (!leftVector.has_value() || !rightVector.has_value() ||
          leftVector->size() != rightVector->size()) {
        return std::nullopt;
      }
      double sumSquares = 0.0;
      for (std::size_t index = 0; index < leftVector->size(); ++index) {
        const double difference =
            (*leftVector)[index].number - (*rightVector)[index].number;
        sumSquares += difference * difference;
      }
      return scalarFloatValue(std::sqrt(sumSquares));
    }
    if (name == "mix" && arguments.size() == 3) {
      std::optional<FoldedHIRScalar> x = scalarArgument(0);
      std::optional<FoldedHIRScalar> y = scalarArgument(1);
      std::optional<FoldedHIRScalar> a = scalarArgument(2);
      return x.has_value() && y.has_value() && a.has_value()
                 ? scalarFloatValue(x->number * (1.0 - a->number) +
                                    y->number * a->number)
                 : std::nullopt;
    }
    if (name == "smoothstep" && arguments.size() == 3) {
      std::optional<FoldedHIRScalar> edge0 = scalarArgument(0);
      std::optional<FoldedHIRScalar> edge1 = scalarArgument(1);
      std::optional<FoldedHIRScalar> x = scalarArgument(2);
      if (!edge0.has_value() || !edge1.has_value() || !x.has_value() ||
          edge0->number >= edge1->number) {
        return std::nullopt;
      }
      const double t = std::clamp((x->number - edge0->number) /
                                      (edge1->number - edge0->number),
                                  0.0, 1.0);
      return scalarFloatValue(t * t * (3.0 - 2.0 * t));
    }
    if (name == "normalize" && arguments.size() == 1) {
      std::optional<FoldedHIRScalar> value = scalarArgument(0);
      if (!value.has_value() || value->number == 0.0) {
        return std::nullopt;
      }
      return scalarFloatValue(value->number > 0.0 ? 1.0 : -1.0);
    }
    if (name == "reflect" && arguments.size() == 2) {
      std::optional<FoldedHIRScalar> incident = scalarArgument(0);
      std::optional<FoldedHIRScalar> normal = scalarArgument(1);
      return incident.has_value() && normal.has_value()
                 ? scalarFloatValue(incident->number -
                                    2.0 * normal->number *
                                        incident->number * normal->number)
                 : std::nullopt;
    }
    if (name == "dot" && arguments.size() == 2) {
      std::optional<std::vector<FoldedHIRScalar>> left =
          floatVectorArgument(0);
      std::optional<std::vector<FoldedHIRScalar>> right =
          floatVectorArgument(1);
      if (!left.has_value() || !right.has_value() ||
          left->size() != right->size()) {
        return std::nullopt;
      }
      double dot = 0.0;
      for (std::size_t index = 0; index < left->size(); ++index) {
        dot += (*left)[index].number * (*right)[index].number;
      }
      return scalarFloatValue(dot);
    }
    return std::nullopt;
  }

  const std::optional<std::size_t> vectorWidth =
      vectorWidthFromName(baseTypeName(expression.type));
  if (!vectorWidth.has_value()) {
    return std::nullopt;
  }
  const bool integerVectorResult =
      !isFloatFoldedHIRVectorType(expression.type) &&
      allArgumentComponentsInteger();
  auto vectorComponent = [&](std::size_t argumentIndex,
                             std::size_t componentIndex)
      -> std::optional<FoldedHIRScalar> {
    if (argumentIndex >= arguments.size() ||
        componentIndex >= *vectorWidth) {
      return std::nullopt;
    }
    const FoldedHIRValue &argument = arguments[argumentIndex];
    if (isFoldedHIRScalarValue(argument)) {
      const FoldedHIRScalar &component = argument.components.front();
      return component.isBool ? std::nullopt
                              : std::optional<FoldedHIRScalar>{component};
    }
    if (argument.components.size() != *vectorWidth) {
      return std::nullopt;
    }
    const FoldedHIRScalar &component = argument.components[componentIndex];
    return component.isBool ? std::nullopt
                            : std::optional<FoldedHIRScalar>{component};
  };
  auto fullVectorArgument =
      [&](std::size_t argumentIndex)
          -> std::optional<std::vector<FoldedHIRScalar>> {
    if (argumentIndex >= arguments.size() ||
        arguments[argumentIndex].components.size() != *vectorWidth) {
      return std::nullopt;
    }
    for (const FoldedHIRScalar &component :
         arguments[argumentIndex].components) {
      if (component.isBool) {
        return std::nullopt;
      }
    }
    return arguments[argumentIndex].components;
  };
  auto foldUnaryVector =
      [&](auto operation, bool integerResult)
          -> std::optional<FoldedHIRValue> {
    std::vector<double> numbers;
    numbers.reserve(*vectorWidth);
    for (std::size_t index = 0; index < *vectorWidth; ++index) {
      std::optional<FoldedHIRScalar> value = vectorComponent(0, index);
      if (!value.has_value()) {
        return std::nullopt;
      }
      numbers.push_back(operation(value->number));
    }
    return foldedVectorValue(numbers, integerResult);
  };
  auto foldBinaryVector =
      [&](auto operation, bool integerResult)
          -> std::optional<FoldedHIRValue> {
    std::vector<double> numbers;
    numbers.reserve(*vectorWidth);
    for (std::size_t index = 0; index < *vectorWidth; ++index) {
      std::optional<FoldedHIRScalar> left = vectorComponent(0, index);
      std::optional<FoldedHIRScalar> right = vectorComponent(1, index);
      if (!left.has_value() || !right.has_value()) {
        return std::nullopt;
      }
      numbers.push_back(operation(left->number, right->number));
    }
    return foldedVectorValue(numbers, integerResult);
  };

  if (name == "abs" && arguments.size() == 1) {
    return foldUnaryVector(
        [](double value) { return std::fabs(value); }, integerVectorResult);
  }
  if (name == "min" && arguments.size() == 2) {
    return foldBinaryVector(
        [](double left, double right) { return std::min(left, right); },
        integerVectorResult);
  }
  if (name == "max" && arguments.size() == 2) {
    return foldBinaryVector(
        [](double left, double right) { return std::max(left, right); },
        integerVectorResult);
  }
  if (name == "clamp" && arguments.size() == 3) {
    std::vector<double> numbers;
    numbers.reserve(*vectorWidth);
    for (std::size_t index = 0; index < *vectorWidth; ++index) {
      std::optional<FoldedHIRScalar> value = vectorComponent(0, index);
      std::optional<FoldedHIRScalar> lower = vectorComponent(1, index);
      std::optional<FoldedHIRScalar> upper = vectorComponent(2, index);
      if (!value.has_value() || !lower.has_value() || !upper.has_value()) {
        return std::nullopt;
      }
      numbers.push_back(std::min(std::max(value->number, lower->number),
                                 upper->number));
    }
    return foldedVectorValue(numbers, integerVectorResult);
  }
  if (name == "cos" && arguments.size() == 1) {
    return foldUnaryVector([](double value) { return std::cos(value); },
                           false);
  }
  if (name == "sin" && arguments.size() == 1) {
    return foldUnaryVector([](double value) { return std::sin(value); },
                           false);
  }
  if (name == "tan" && arguments.size() == 1) {
    return foldUnaryVector([](double value) { return std::tan(value); },
                           false);
  }
  if (name == "sqrt" && arguments.size() == 1) {
    std::vector<double> numbers;
    numbers.reserve(*vectorWidth);
    for (std::size_t index = 0; index < *vectorWidth; ++index) {
      std::optional<FoldedHIRScalar> value = vectorComponent(0, index);
      if (!value.has_value() || value->number < 0.0) {
        return std::nullopt;
      }
      numbers.push_back(std::sqrt(value->number));
    }
    return foldedVectorValue(numbers, false);
  }
  if (name == "pow" && arguments.size() == 2) {
    return foldBinaryVector(
        [](double left, double right) { return std::pow(left, right); },
        false);
  }
  if (name == "fract" && arguments.size() == 1) {
    return foldUnaryVector(
        [](double value) { return value - std::floor(value); }, false);
  }
  if (name == "floor" && arguments.size() == 1) {
    return foldUnaryVector([](double value) { return std::floor(value); },
                           false);
  }
  if (name == "ceil" && arguments.size() == 1) {
    return foldUnaryVector([](double value) { return std::ceil(value); },
                           false);
  }
  if (name == "atan" && arguments.size() == 1) {
    return foldUnaryVector([](double value) { return std::atan(value); },
                           false);
  }
  if (name == "atan" && arguments.size() == 2) {
    return foldBinaryVector(
        [](double y, double x) { return std::atan2(y, x); }, false);
  }
  if (name == "mix" && arguments.size() == 3) {
    std::vector<double> numbers;
    numbers.reserve(*vectorWidth);
    for (std::size_t index = 0; index < *vectorWidth; ++index) {
      std::optional<FoldedHIRScalar> x = vectorComponent(0, index);
      std::optional<FoldedHIRScalar> y = vectorComponent(1, index);
      std::optional<FoldedHIRScalar> a = vectorComponent(2, index);
      if (!x.has_value() || !y.has_value() || !a.has_value()) {
        return std::nullopt;
      }
      numbers.push_back(x->number * (1.0 - a->number) +
                        y->number * a->number);
    }
    return foldedVectorValue(numbers, false);
  }
  if (name == "smoothstep" && arguments.size() == 3) {
    std::vector<double> numbers;
    numbers.reserve(*vectorWidth);
    for (std::size_t index = 0; index < *vectorWidth; ++index) {
      std::optional<FoldedHIRScalar> edge0 = vectorComponent(0, index);
      std::optional<FoldedHIRScalar> edge1 = vectorComponent(1, index);
      std::optional<FoldedHIRScalar> x = vectorComponent(2, index);
      if (!edge0.has_value() || !edge1.has_value() || !x.has_value() ||
          edge0->number >= edge1->number) {
        return std::nullopt;
      }
      const double t = std::clamp((x->number - edge0->number) /
                                      (edge1->number - edge0->number),
                                  0.0, 1.0);
      numbers.push_back(t * t * (3.0 - 2.0 * t));
    }
    return foldedVectorValue(numbers, false);
  }
  if (name == "cross" && arguments.size() == 2) {
    if (*vectorWidth != 3) {
      return std::nullopt;
    }
    std::optional<std::vector<FoldedHIRScalar>> left =
        fullVectorArgument(0);
    std::optional<std::vector<FoldedHIRScalar>> right =
        fullVectorArgument(1);
    if (!left.has_value() || !right.has_value()) {
      return std::nullopt;
    }
    return foldedVectorValue(
        {(*left)[1].number * (*right)[2].number -
             (*left)[2].number * (*right)[1].number,
         (*left)[2].number * (*right)[0].number -
             (*left)[0].number * (*right)[2].number,
         (*left)[0].number * (*right)[1].number -
             (*left)[1].number * (*right)[0].number},
        false);
  }
  if (name == "normalize" && arguments.size() == 1) {
    std::optional<std::vector<FoldedHIRScalar>> vector =
        fullVectorArgument(0);
    if (!vector.has_value()) {
      return std::nullopt;
    }
    double sumSquares = 0.0;
    for (const FoldedHIRScalar &component : *vector) {
      sumSquares += component.number * component.number;
    }
    if (sumSquares <= 0.0) {
      return std::nullopt;
    }
    const double length = std::sqrt(sumSquares);
    std::vector<double> numbers;
    numbers.reserve(vector->size());
    for (const FoldedHIRScalar &component : *vector) {
      numbers.push_back(component.number / length);
    }
    return foldedVectorValue(numbers, false);
  }
  if (name == "reflect" && arguments.size() == 2) {
    std::optional<std::vector<FoldedHIRScalar>> incident =
        fullVectorArgument(0);
    std::optional<std::vector<FoldedHIRScalar>> normal =
        fullVectorArgument(1);
    if (!incident.has_value() || !normal.has_value()) {
      return std::nullopt;
    }
    double dot = 0.0;
    for (std::size_t index = 0; index < *vectorWidth; ++index) {
      dot += (*incident)[index].number * (*normal)[index].number;
    }
    std::vector<double> numbers;
    numbers.reserve(*vectorWidth);
    for (std::size_t index = 0; index < *vectorWidth; ++index) {
      numbers.push_back((*incident)[index].number -
                        2.0 * dot * (*normal)[index].number);
    }
    return foldedVectorValue(numbers, false);
  }
  return std::nullopt;
}

std::optional<FoldedHIRScalar> foldHIRScalarIntrinsicCall(
    const HIRExpression &expression, const HIRScalarConstantMap &constantValues,
    HIRScalarFoldOptions options,
    const HIRValueConstantMap *valueConstants) {
  std::optional<FoldedHIRValue> folded =
      foldHIRValueIntrinsicCall(expression, constantValues, options,
                                valueConstants);
  if (!folded.has_value()) {
    return std::nullopt;
  }
  return foldedHIRValueAsScalar(*folded);
}

std::optional<FoldedHIRValue> foldHIRValueExpression(
    const HIRExpression &expression, const HIRScalarConstantMap &constantValues,
    HIRScalarFoldOptions options,
    const HIRValueConstantMap *valueConstants) {
  switch (expression.kind) {
  case HIRExpressionKind::Literal: {
    std::optional<FoldedHIRScalar> scalar =
        parseFoldedHIRScalar(expression.value);
    return scalar.has_value() ? std::optional<FoldedHIRValue>(
                                    makeFoldedHIRScalarValue(*scalar))
                              : std::nullopt;
  }
  case HIRExpressionKind::Identifier:
    if (valueConstants != nullptr) {
      if (auto value = valueConstants->find(expression.value);
          value != valueConstants->end()) {
        return value->second;
      }
    }
    if (auto constant = constantValues.find(expression.value);
        constant != constantValues.end()) {
      return makeFoldedHIRScalarValue(constant->second);
    }
    if (std::optional<FoldedHIRScalar> scalar =
            parseFoldedHIRScalar(expression.value)) {
      return makeFoldedHIRScalarValue(*scalar);
    }
    return std::nullopt;
  case HIRExpressionKind::Group:
    if (expression.children.empty()) {
      return std::nullopt;
    }
    return foldHIRValueExpression(expression.children.front(), constantValues,
                                  options, valueConstants);
  case HIRExpressionKind::Unary: {
    if (expression.children.empty()) {
      return std::nullopt;
    }
    std::optional<FoldedHIRScalar> operand = foldHIRScalarExpression(
        expression.children.front(), constantValues, options, valueConstants);
    if (!operand.has_value()) {
      return std::nullopt;
    }
    if (expression.value == "-") {
      operand->number = -operand->number;
      return makeFoldedHIRScalarValue(*operand);
    }
    if (expression.value == "+") {
      return makeFoldedHIRScalarValue(*operand);
    }
    if (expression.value == "!") {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{0.0, operand->isBool ? !operand->boolean
                                               : operand->number == 0.0,
                          true, true});
    }
    return std::nullopt;
  }
  case HIRExpressionKind::Binary: {
    if (expression.children.size() < 2) {
      return std::nullopt;
    }
    const std::optional<FoldedHIRScalar> left =
        foldHIRScalarExpression(expression.children[0], constantValues,
                                options, valueConstants);
    if (!left.has_value()) {
      return std::nullopt;
    }

    const double lhs = numericValue(*left);
    if (expression.value == "&&" && !truthValue(*left)) {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{0.0, false, true, true});
    }
    if (expression.value == "||" && truthValue(*left)) {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{0.0, true, true, true});
    }

    const std::optional<FoldedHIRScalar> right =
        foldHIRScalarExpression(expression.children[1], constantValues,
                                options, valueConstants);
    if (!right.has_value()) {
      return std::nullopt;
    }

    const double rhs = numericValue(*right);
    const bool integerResult = left->isInteger && right->isInteger;
    if (expression.value == "+") {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{lhs + rhs, false, false, integerResult});
    }
    if (expression.value == "-") {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{lhs - rhs, false, false, integerResult});
    }
    if (expression.value == "*") {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{lhs * rhs, false, false, integerResult});
    }
    if (expression.value == "/" && rhs != 0.0) {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{lhs / rhs, false, false, false});
    }
    if (expression.value == "%" && rhs != 0.0) {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{std::fmod(lhs, rhs), false, false, integerResult});
    }
    if (expression.value == "==") {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{0.0, lhs == rhs, true, true});
    }
    if (expression.value == "!=") {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{0.0, lhs != rhs, true, true});
    }
    if (expression.value == "<") {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{0.0, lhs < rhs, true, true});
    }
    if (expression.value == "<=") {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{0.0, lhs <= rhs, true, true});
    }
    if (expression.value == ">") {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{0.0, lhs > rhs, true, true});
    }
    if (expression.value == ">=") {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{0.0, lhs >= rhs, true, true});
    }
    if (expression.value == "&&") {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{0.0, truthValue(*left) && truthValue(*right), true,
                          true});
    }
    if (expression.value == "||") {
      return makeFoldedHIRScalarValue(
          FoldedHIRScalar{0.0, truthValue(*left) || truthValue(*right), true,
                          true});
    }
    return std::nullopt;
  }
  case HIRExpressionKind::Select: {
    if (expression.children.size() < 3) {
      return std::nullopt;
    }
    const std::optional<FoldedHIRScalar> condition =
        foldHIRScalarExpression(expression.children[0], constantValues,
                                options, valueConstants);
    if (!condition.has_value()) {
      return std::nullopt;
    }
    const bool chooseThen = truthValue(*condition);
    return foldHIRValueExpression(expression.children[chooseThen ? 1 : 2],
                                  constantValues, options, valueConstants);
  }
  case HIRExpressionKind::Constructor:
    return foldHIRConstructorValue(expression, constantValues, options,
                                   valueConstants);
  case HIRExpressionKind::Call: {
    return foldHIRValueIntrinsicCall(expression, constantValues, options,
                                     valueConstants);
  }
  case HIRExpressionKind::MemberAccess:
    return foldHIRMemberAccessValue(expression, constantValues, options,
                                    valueConstants);
  case HIRExpressionKind::Empty:
  case HIRExpressionKind::IndexAccess:
  case HIRExpressionKind::NonUniform:
  case HIRExpressionKind::TextureSample:
  case HIRExpressionKind::TextureCompare:
  case HIRExpressionKind::TextureCompareLodManual:
    return std::nullopt;
  }
  return std::nullopt;
}

std::optional<FoldedHIRScalar> foldHIRScalarExpression(
    const HIRExpression &expression, const HIRScalarConstantMap &constantValues,
    HIRScalarFoldOptions options,
    const HIRValueConstantMap *valueConstants) {
  std::optional<FoldedHIRValue> folded =
      foldHIRValueExpression(expression, constantValues, options,
                             valueConstants);
  if (!folded.has_value()) {
    return std::nullopt;
  }
  return foldedHIRValueAsScalar(*folded);
}

std::optional<std::string> foldHIRIntegerIndexExpression(
    const HIRExpression &expression, const HIRScalarConstantMap &constantValues,
    HIRScalarFoldOptions options,
    const HIRValueConstantMap *valueConstants) {
  const std::string baseName = baseTypeName(expression.type);
  if ((baseName != "int" && baseName != "uint") ||
      expression.type.arraySize.has_value() ||
      !isKnownPureHIRExpression(expression)) {
    return std::nullopt;
  }

  std::optional<FoldedHIRScalar> folded =
      foldHIRScalarExpression(expression, constantValues, options,
                              valueConstants);
  if (!folded.has_value() || folded->isBool || !folded->isInteger) {
    return std::nullopt;
  }

  return formatFoldedHIRScalarForType(*folded, expression.type);
}

} // namespace crossgl
