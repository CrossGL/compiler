#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/Frontend/AST.h"

namespace crossgl {

inline constexpr std::size_t kMaxManualTextureCompareKernelTaps = 16;
inline constexpr double kManualTextureCompareKernelWeightSumTolerance =
    0.000001;

enum class ManualTextureCompareKernelListShape {
  Valid,
  NotTextureCompareKernelCall,
  Empty,
  OddOperandCount,
  TooManyTaps,
};

enum class ManualTextureCompareKernelForm {
  Fixed4,
  Fixed8,
  TapList,
};

enum class ManualTextureCompareKernelWeightClass {
  StaticNormalized,
  StaticNonNormalized,
  StaticZeroSum,
  Dynamic,
};

struct HIRType {
  HIRType() = default;
  HIRType(std::string name, std::optional<std::string> arraySize = std::nullopt,
          SourceLocation location = {})
      : name(std::move(name)), arraySize(std::move(arraySize)),
        location(std::move(location)) {}

  std::string name;
  std::optional<std::string> arraySize;
  SourceLocation location;
};

struct HIRField {
  HIRType type;
  std::string name;
  SourceLocation nameSpan;
};

struct HIRStruct {
  std::string name;
  std::vector<HIRField> fields;
};

struct HIRParameter {
  HIRType type;
  std::string name;
  SourceLocation nameSpan;
};

enum class HIRResourceKind {
  Uniform,
  Buffer,
  Shared,
  Texture,
  StorageImage,
  Sampler,
  Value,
};

enum class HIRStorageImageAccess {
  ReadWrite,
  ReadOnly,
  WriteOnly,
};

struct HIRResource {
  HIRResourceKind kind = HIRResourceKind::Value;
  HIRType type;
  std::string name;
  std::size_t set = 0;
  std::size_t binding = 0;
  bool explicitSet = false;
  bool explicitBinding = false;
  HIRStorageImageAccess storageImageAccess = HIRStorageImageAccess::ReadWrite;
  std::optional<std::string> storageImageFormat;
  SourceLocation declarationSpan;
  SourceLocation nameSpan;
  SourceLocation layoutSpan;
  SourceLocation setSpan;
  SourceLocation bindingSpan;
};

struct HIRWorkgroupSize {
  std::string x = "1";
  std::string y = "1";
  std::string z = "1";
  std::string sourceX = "1";
  std::string sourceY = "1";
  std::string sourceZ = "1";
};

enum class HIRExpressionKind {
  Empty,
  Identifier,
  Literal,
  Group,
  MemberAccess,
  IndexAccess,
  NonUniform,
  Call,
  Constructor,
  Unary,
  Binary,
  Select,
  TextureSample,
  TextureCompare,
  TextureCompareLodManual,
};

struct HIRExpression {
  HIRExpressionKind kind = HIRExpressionKind::Empty;
  HIRType type;
  std::string value;
  std::vector<HIRExpression> children;
  SourceLocation location;
};

struct ManualTextureCompareKernelTap {
  const HIRExpression *offset = nullptr;
  const HIRExpression *weight = nullptr;
};

struct ManualTextureCompareKernelWeightSummary {
  std::size_t tapCount = 0;
  bool allWeightsStatic = false;
  double sum = 0.0;
  bool zeroSum = false;
  bool normalized = false;
};

struct ManualTextureCompareKernelAnalysis {
  ManualTextureCompareKernelForm form =
      ManualTextureCompareKernelForm::TapList;
  std::string sourceOperation;
  std::string canonicalOperation;
  bool compatibilityAlias = false;
  ManualTextureCompareKernelWeightSummary weights;
};

struct ManualTextureCompareKernelOccurrence {
  std::string stage;
  std::string entryPoint;
  std::string function;
  ManualTextureCompareKernelAnalysis analysis;
  ManualTextureCompareKernelWeightClass weightClass =
      ManualTextureCompareKernelWeightClass::Dynamic;
};

struct ManualTextureCompareKernelModuleAnalysis {
  std::vector<ManualTextureCompareKernelOccurrence> kernels;
  std::vector<std::size_t> staticNormalized;
  std::vector<std::size_t> staticNonNormalized;
  std::vector<std::size_t> staticZeroSum;
  std::vector<std::size_t> dynamic;
};

struct HIRConstant {
  HIRType type;
  std::string name;
  HIRExpression value;
  std::optional<std::string> foldedValue;
};

enum class HIRStatementKind {
  Declaration,
  Assignment,
  Return,
  Expression,
  Block,
  If,
  For,
  Break,
  Continue,
  Discard,
  Raw,
};

struct HIRStatement {
  HIRStatementKind kind = HIRStatementKind::Raw;
  HIRType declaredType;
  std::string name;
  HIRExpression target;
  HIRExpression value;
  std::vector<HIRStatement> initializer;
  std::vector<HIRStatement> update;
  std::vector<Token> updateTokens;
  std::vector<HIRStatement> body;
  std::vector<HIRStatement> elseBody;
  std::vector<Token> rawTokens;
  SourceLocation location;
};

struct HIRFunction {
  HIRType returnType;
  std::string name;
  std::vector<HIRParameter> parameters;
  std::vector<Token> bodyTokens;
  std::vector<HIRStatement> body;
  SourceLocation declarationSpan;
  SourceLocation nameSpan;
};

struct HIRStage {
  std::string stage;
  std::string entryPointName;
  std::optional<HIRWorkgroupSize> workgroupSize;
  std::vector<HIRResource> resources;
  std::vector<HIRFunction> functions;
  SourceLocation declarationSpan;
  SourceLocation nameSpan;
};

struct HIRModule {
  std::string name;
  std::vector<HIRStruct> structs;
  std::vector<HIRConstant> constants;
  std::vector<HIRStage> stages;
  std::vector<HIRFunction> functions;
};

std::optional<HIRModule> buildHIR(const ShaderModule &module,
                                  DiagnosticEngine &diagnostics);

std::optional<std::size_t>
manualTextureCompareKernelListTapCount(const HIRExpression &kernelList);
ManualTextureCompareKernelListShape
manualTextureCompareKernelListShape(const HIRExpression &kernelList);
std::optional<std::vector<ManualTextureCompareKernelTap>>
manualTextureCompareKernelTaps(const HIRExpression &expression);
std::optional<ManualTextureCompareKernelWeightSummary>
manualTextureCompareKernelWeightSummary(const HIRExpression &expression);
std::optional<ManualTextureCompareKernelAnalysis>
manualTextureCompareKernelAnalysis(const HIRExpression &expression);
ManualTextureCompareKernelWeightClass manualTextureCompareKernelWeightClass(
    const ManualTextureCompareKernelWeightSummary &summary);
ManualTextureCompareKernelModuleAnalysis
manualTextureCompareKernelModuleAnalysis(const HIRModule &module);
std::optional<std::size_t>
manualTextureCompareKernelTapCount(const HIRExpression &expression);

std::string formatType(const HIRType &type);
std::string typeToIR(const HIRType &type);
std::string resourceKindName(HIRResourceKind kind);
std::string storageImageAccessName(HIRStorageImageAccess access);
bool storageImageAccessAllowsRead(HIRStorageImageAccess access);
bool storageImageAccessAllowsWrite(HIRStorageImageAccess access);
std::string resolvedStorageImageFormatName(const HIRResource &resource);
std::string manualTextureCompareKernelFormName(
    ManualTextureCompareKernelForm form);
std::string manualTextureCompareKernelWeightClassName(
    ManualTextureCompareKernelWeightClass weightClass);
std::string expressionKindName(HIRExpressionKind kind);
std::string statementKindName(HIRStatementKind kind);

} // namespace crossgl
