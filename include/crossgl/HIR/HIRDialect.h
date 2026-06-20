#pragma once

#include "crossgl/HIR/HIR.h"
#include "crossgl/HIR/Intrinsics.h"

#include <cstddef>
#include <optional>
#include <span>
#include <string>
#include <string_view>

namespace crossgl {

enum class HIRDialectOperationKind {
  ExpressionNode,
  StatementNode,
  BuiltinCall,
};

enum class HIRDialectOperationCategory {
  Core,
  ControlFlow,
  DataFlow,
  Texture,
  Image,
  Atomic,
  Synchronization,
  Structural,
};

enum class HIRDialectEffectKind {
  Pure,
  Store,
  ResourceRead,
  ResourceWrite,
  ResourceReadWrite,
  ControlTransfer,
  Opaque,
  Structural,
  Unknown,
};

enum class HIRDialectTypeCategory {
  Void,
  Scalar,
  Vector,
  Matrix,
  Sampler,
  Texture,
  StorageImage,
  Atomic,
};

enum class HIRDialectScalarKind {
  None,
  Bool,
  SignedInteger,
  UnsignedInteger,
  Float,
};

enum class HIRDialectIntrinsicCategory {
  Math,
  Atomic,
  Synchronization,
};

struct HIRDialectOperationRecord {
  std::string_view name;
  std::string_view sourceName;
  HIRDialectOperationKind kind = HIRDialectOperationKind::ExpressionNode;
  HIRDialectOperationCategory category = HIRDialectOperationCategory::Core;
  HIRDialectEffectKind effect = HIRDialectEffectKind::Pure;
  std::string_view mlirMnemonic;
};

struct HIRDialectTypeRecord {
  std::string_view name;
  HIRDialectTypeCategory category = HIRDialectTypeCategory::Scalar;
  HIRDialectScalarKind scalar = HIRDialectScalarKind::None;
  std::size_t lanes = 0;
  std::size_t rows = 0;
  std::size_t columns = 0;
  std::string_view mlirType;
};

struct HIRDialectIntrinsicRecord {
  std::string_view name;
  HIRDialectIntrinsicCategory category = HIRDialectIntrinsicCategory::Math;
  HIRDialectEffectKind effect = HIRDialectEffectKind::Pure;
  HIRIntrinsicResultRule resultRule = HIRIntrinsicResultRule::FirstArgument;
  std::size_t minimumArity = 0;
  std::optional<std::size_t> maximumArity;
  bool overloaded = false;
  std::string_view capabilityName;
};

struct HIRDialectDuplicateName {
  std::string_view name;
  std::size_t firstIndex = 0;
  std::size_t duplicateIndex = 0;
};

std::string_view
hirDialectOperationKindName(HIRDialectOperationKind kind);
std::string_view
hirDialectOperationCategoryName(HIRDialectOperationCategory category);
std::string_view hirDialectEffectKindName(HIRDialectEffectKind effect);
std::string_view hirDialectTypeCategoryName(HIRDialectTypeCategory category);
std::string_view hirDialectScalarKindName(HIRDialectScalarKind scalar);
std::string_view
hirDialectIntrinsicCategoryName(HIRDialectIntrinsicCategory category);

std::span<const HIRDialectOperationRecord> hirDialectOperations();
std::span<const HIRDialectTypeRecord> hirDialectTypes();
std::span<const HIRDialectIntrinsicRecord> hirDialectIntrinsics();

const HIRDialectOperationRecord *
lookupHIRDialectOperation(std::string_view name);
const HIRDialectOperationRecord *
lookupHIRDialectOperationBySourceName(std::string_view sourceName);
const HIRDialectTypeRecord *lookupHIRDialectType(std::string_view name);
const HIRDialectIntrinsicRecord *
lookupHIRDialectIntrinsic(std::string_view name);

std::optional<HIRDialectDuplicateName>
findDuplicateHIRDialectOperationName(
    std::span<const HIRDialectOperationRecord> records);
std::optional<HIRDialectDuplicateName>
findDuplicateHIRDialectTypeName(std::span<const HIRDialectTypeRecord> records);
std::optional<HIRDialectDuplicateName>
findDuplicateHIRDialectIntrinsicName(
    std::span<const HIRDialectIntrinsicRecord> records);

bool validateHIRDialectCatalog(std::string *diagnostic = nullptr);

} // namespace crossgl
