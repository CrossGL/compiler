#include "crossgl/HIR/HIRDialect.h"

#include <algorithm>
#include <array>
#include <string>

namespace crossgl {
namespace {

using OpKind = HIRDialectOperationKind;
using OpCategory = HIRDialectOperationCategory;
using Effect = HIRDialectEffectKind;
using TypeCategory = HIRDialectTypeCategory;
using Scalar = HIRDialectScalarKind;
using IntrinsicCategory = HIRDialectIntrinsicCategory;

constexpr std::array<HIRDialectOperationRecord, 57> kHIRDialectOperations = {{
    {"hir.empty", "Empty", OpKind::ExpressionNode, OpCategory::Core,
     Effect::Pure, "hir.empty"},
    {"hir.identifier", "Identifier", OpKind::ExpressionNode,
     OpCategory::DataFlow, Effect::Pure, "hir.identifier"},
    {"hir.literal", "Literal", OpKind::ExpressionNode, OpCategory::Core,
     Effect::Pure, "hir.literal"},
    {"hir.group", "Group", OpKind::ExpressionNode, OpCategory::Core,
     Effect::Pure, "hir.group"},
    {"hir.member_access", "MemberAccess", OpKind::ExpressionNode,
     OpCategory::DataFlow, Effect::Pure, "hir.member_access"},
    {"hir.index_access", "IndexAccess", OpKind::ExpressionNode,
     OpCategory::DataFlow, Effect::Pure, "hir.index_access"},
    {"hir.non_uniform", "NonUniform", OpKind::ExpressionNode,
     OpCategory::DataFlow, Effect::Pure, "hir.non_uniform"},
    {"hir.call", "Call", OpKind::ExpressionNode, OpCategory::Core,
     Effect::Unknown, "hir.call"},
    {"hir.construct", "Constructor", OpKind::ExpressionNode,
     OpCategory::DataFlow, Effect::Pure, "hir.construct"},
    {"hir.unary", "Unary", OpKind::ExpressionNode, OpCategory::DataFlow,
     Effect::Pure, "hir.unary"},
    {"hir.binary", "Binary", OpKind::ExpressionNode, OpCategory::DataFlow,
     Effect::Pure, "hir.binary"},
    {"hir.select", "Select", OpKind::ExpressionNode, OpCategory::DataFlow,
     Effect::Pure, "hir.select"},
    {"hir.texture_sample", "TextureSample", OpKind::ExpressionNode,
     OpCategory::Texture, Effect::ResourceRead, "hir.texture_sample"},
    {"hir.texture_compare", "TextureCompare", OpKind::ExpressionNode,
     OpCategory::Texture, Effect::ResourceRead, "hir.texture_compare"},
    {"hir.texture_compare_lod_manual", "TextureCompareLodManual",
     OpKind::ExpressionNode, OpCategory::Texture, Effect::ResourceRead,
     "hir.texture_compare_lod_manual"},
    {"hir.declare", "Declaration", OpKind::StatementNode,
     OpCategory::DataFlow, Effect::Pure, "hir.declare"},
    {"hir.assign", "Assignment", OpKind::StatementNode, OpCategory::DataFlow,
     Effect::Store, "hir.assign"},
    {"hir.return", "Return", OpKind::StatementNode, OpCategory::ControlFlow,
     Effect::ControlTransfer, "hir.return"},
    {"hir.expr_stmt", "Expression", OpKind::StatementNode, OpCategory::Core,
     Effect::Unknown, "hir.expr_stmt"},
    {"hir.block", "Block", OpKind::StatementNode, OpCategory::ControlFlow,
     Effect::Pure, "hir.block"},
    {"hir.if", "If", OpKind::StatementNode, OpCategory::ControlFlow,
     Effect::Pure, "hir.if"},
    {"hir.for", "For", OpKind::StatementNode, OpCategory::ControlFlow,
     Effect::Pure, "hir.for"},
    {"hir.break", "Break", OpKind::StatementNode, OpCategory::ControlFlow,
     Effect::ControlTransfer, "hir.break"},
    {"hir.continue", "Continue", OpKind::StatementNode,
     OpCategory::ControlFlow, Effect::ControlTransfer, "hir.continue"},
    {"hir.discard", "Discard", OpKind::StatementNode,
     OpCategory::ControlFlow, Effect::ControlTransfer, "hir.discard"},
    {"hir.raw", "Raw", OpKind::StatementNode, OpCategory::Core,
     Effect::Unknown, "hir.raw"},
    {"hir.atomic_add", "atomicAdd", OpKind::BuiltinCall, OpCategory::Atomic,
     Effect::ResourceReadWrite, "hir.atomic_add"},
    {"hir.atomic_and", "atomicAnd", OpKind::BuiltinCall, OpCategory::Atomic,
     Effect::ResourceReadWrite, "hir.atomic_and"},
    {"hir.atomic_exchange", "atomicExchange", OpKind::BuiltinCall,
     OpCategory::Atomic, Effect::ResourceReadWrite, "hir.atomic_exchange"},
    {"hir.atomic_max", "atomicMax", OpKind::BuiltinCall, OpCategory::Atomic,
     Effect::ResourceReadWrite, "hir.atomic_max"},
    {"hir.atomic_min", "atomicMin", OpKind::BuiltinCall, OpCategory::Atomic,
     Effect::ResourceReadWrite, "hir.atomic_min"},
    {"hir.atomic_or", "atomicOr", OpKind::BuiltinCall, OpCategory::Atomic,
     Effect::ResourceReadWrite, "hir.atomic_or"},
    {"hir.atomic_xor", "atomicXor", OpKind::BuiltinCall, OpCategory::Atomic,
     Effect::ResourceReadWrite, "hir.atomic_xor"},
    {"hir.image_load", "imageLoad", OpKind::BuiltinCall, OpCategory::Image,
     Effect::ResourceRead, "hir.image_load"},
    {"hir.image_store", "imageStore", OpKind::BuiltinCall, OpCategory::Image,
     Effect::ResourceWrite, "hir.image_store"},
    {"hir.image_atomic_add", "imageAtomicAdd", OpKind::BuiltinCall,
     OpCategory::Image, Effect::ResourceReadWrite, "hir.image_atomic_add"},
    {"hir.image_atomic_and", "imageAtomicAnd", OpKind::BuiltinCall,
     OpCategory::Image, Effect::ResourceReadWrite, "hir.image_atomic_and"},
    {"hir.image_atomic_exchange", "imageAtomicExchange", OpKind::BuiltinCall,
     OpCategory::Image, Effect::ResourceReadWrite,
     "hir.image_atomic_exchange"},
    {"hir.image_atomic_max", "imageAtomicMax", OpKind::BuiltinCall,
     OpCategory::Image, Effect::ResourceReadWrite, "hir.image_atomic_max"},
    {"hir.image_atomic_min", "imageAtomicMin", OpKind::BuiltinCall,
     OpCategory::Image, Effect::ResourceReadWrite, "hir.image_atomic_min"},
    {"hir.image_atomic_or", "imageAtomicOr", OpKind::BuiltinCall,
     OpCategory::Image, Effect::ResourceReadWrite, "hir.image_atomic_or"},
    {"hir.image_atomic_xor", "imageAtomicXor", OpKind::BuiltinCall,
     OpCategory::Image, Effect::ResourceReadWrite, "hir.image_atomic_xor"},
    {"hir.sample", "sample", OpKind::BuiltinCall, OpCategory::Texture,
     Effect::ResourceRead, "hir.sample"},
    {"hir.texture", "texture", OpKind::BuiltinCall, OpCategory::Texture,
     Effect::ResourceRead, "hir.texture"},
    {"hir.texture_gather", "textureGather", OpKind::BuiltinCall,
     OpCategory::Texture, Effect::ResourceRead, "hir.texture_gather"},
    {"hir.texture_lod", "textureLod", OpKind::BuiltinCall,
     OpCategory::Texture, Effect::ResourceRead, "hir.texture_lod"},
    {"hir.texture_compare_call", "textureCompare", OpKind::BuiltinCall,
     OpCategory::Texture, Effect::ResourceRead, "hir.texture_compare_call"},
    {"hir.texture_compare_lod", "textureCompareLod", OpKind::BuiltinCall,
     OpCategory::Texture, Effect::ResourceRead, "hir.texture_compare_lod"},
    {"hir.texture_compare_kernel", "textureCompareKernel",
     OpKind::BuiltinCall, OpCategory::Structural, Effect::Structural,
     "hir.texture_compare_kernel"},
    {"hir.texture_compare_lod_manual_call", "textureCompareLodManual",
     OpKind::BuiltinCall, OpCategory::Texture, Effect::ResourceRead,
     "hir.texture_compare_lod_manual_call"},
    {"hir.texture_compare_lod_manual_gather2x2",
     "textureCompareLodManualGather2x2", OpKind::BuiltinCall,
     OpCategory::Texture, Effect::ResourceRead,
     "hir.texture_compare_lod_manual_gather2x2"},
    {"hir.texture_compare_lod_manual_kernel",
     "textureCompareLodManualKernel", OpKind::BuiltinCall,
     OpCategory::Texture, Effect::ResourceRead,
     "hir.texture_compare_lod_manual_kernel"},
    {"hir.texture_compare_lod_manual_kernel4",
     "textureCompareLodManualKernel4", OpKind::BuiltinCall,
     OpCategory::Texture, Effect::ResourceRead,
     "hir.texture_compare_lod_manual_kernel4"},
    {"hir.texture_compare_lod_manual_kernel8",
     "textureCompareLodManualKernel8", OpKind::BuiltinCall,
     OpCategory::Texture, Effect::ResourceRead,
     "hir.texture_compare_lod_manual_kernel8"},
    {"hir.texture_compare_lod_manual_offset",
     "textureCompareLodManualOffset", OpKind::BuiltinCall,
     OpCategory::Texture, Effect::ResourceRead,
     "hir.texture_compare_lod_manual_offset"},
    {"hir.workgroup_barrier", "workgroupBarrier", OpKind::BuiltinCall,
     OpCategory::Synchronization, Effect::Opaque, "hir.workgroup_barrier"},
    {"hir.barrier", "barrier", OpKind::BuiltinCall,
     OpCategory::Synchronization, Effect::Opaque, "hir.workgroup_barrier"},
}};

constexpr std::array<HIRDialectTypeRecord, 59> kHIRDialectTypes = {{
    {"void", TypeCategory::Void, Scalar::None, 0, 0, 0, "!hir.void"},
    {"bool", TypeCategory::Scalar, Scalar::Bool, 1, 0, 0, "!hir.bool"},
    {"int", TypeCategory::Scalar, Scalar::SignedInteger, 1, 0, 0, "!hir.i32"},
    {"uint", TypeCategory::Scalar, Scalar::UnsignedInteger, 1, 0, 0,
     "!hir.ui32"},
    {"float", TypeCategory::Scalar, Scalar::Float, 1, 0, 0, "!hir.f32"},
    {"double", TypeCategory::Scalar, Scalar::Float, 1, 0, 0, "!hir.f64"},
    {"half", TypeCategory::Scalar, Scalar::Float, 1, 0, 0, "!hir.f16"},
    {"vec2", TypeCategory::Vector, Scalar::Float, 2, 0, 0,
     "!hir.vector<2xf32>"},
    {"vec3", TypeCategory::Vector, Scalar::Float, 3, 0, 0,
     "!hir.vector<3xf32>"},
    {"vec4", TypeCategory::Vector, Scalar::Float, 4, 0, 0,
     "!hir.vector<4xf32>"},
    {"ivec2", TypeCategory::Vector, Scalar::SignedInteger, 2, 0, 0,
     "!hir.vector<2xi32>"},
    {"ivec3", TypeCategory::Vector, Scalar::SignedInteger, 3, 0, 0,
     "!hir.vector<3xi32>"},
    {"ivec4", TypeCategory::Vector, Scalar::SignedInteger, 4, 0, 0,
     "!hir.vector<4xi32>"},
    {"uvec2", TypeCategory::Vector, Scalar::UnsignedInteger, 2, 0, 0,
     "!hir.vector<2xui32>"},
    {"uvec3", TypeCategory::Vector, Scalar::UnsignedInteger, 3, 0, 0,
     "!hir.vector<3xui32>"},
    {"uvec4", TypeCategory::Vector, Scalar::UnsignedInteger, 4, 0, 0,
     "!hir.vector<4xui32>"},
    {"bvec2", TypeCategory::Vector, Scalar::Bool, 2, 0, 0,
     "!hir.vector<2xi1>"},
    {"bvec3", TypeCategory::Vector, Scalar::Bool, 3, 0, 0,
     "!hir.vector<3xi1>"},
    {"bvec4", TypeCategory::Vector, Scalar::Bool, 4, 0, 0,
     "!hir.vector<4xi1>"},
    {"mat2", TypeCategory::Matrix, Scalar::Float, 0, 2, 2,
     "!hir.matrix<2x2xf32>"},
    {"mat3", TypeCategory::Matrix, Scalar::Float, 0, 3, 3,
     "!hir.matrix<3x3xf32>"},
    {"mat4", TypeCategory::Matrix, Scalar::Float, 0, 4, 4,
     "!hir.matrix<4x4xf32>"},
    {"mat2x2", TypeCategory::Matrix, Scalar::Float, 0, 2, 2,
     "!hir.matrix<2x2xf32>"},
    {"mat3x3", TypeCategory::Matrix, Scalar::Float, 0, 3, 3,
     "!hir.matrix<3x3xf32>"},
    {"mat4x4", TypeCategory::Matrix, Scalar::Float, 0, 4, 4,
     "!hir.matrix<4x4xf32>"},
    {"sampler", TypeCategory::Sampler, Scalar::None, 0, 0, 0,
     "!hir.sampler"},
    {"comparison_sampler", TypeCategory::Sampler, Scalar::None, 0, 0, 0,
     "!hir.comparison_sampler"},
    {"sampler2D", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<2d, sampled, f32>"},
    {"sampler2DArray", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<2d_array, sampled, f32>"},
    {"sampler3D", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<3d, sampled, f32>"},
    {"samplerCube", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<cube, sampled, f32>"},
    {"samplerCubeArray", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<cube_array, sampled, f32>"},
    {"sampler2DShadow", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<2d, comparison, f32>"},
    {"sampler2DArrayShadow", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<2d_array, comparison, f32>"},
    {"samplerCubeShadow", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<cube, comparison, f32>"},
    {"samplerCubeArrayShadow", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<cube_array, comparison, f32>"},
    {"isampler2D", TypeCategory::Texture, Scalar::SignedInteger, 0, 0, 0,
     "!hir.texture<2d, sampled, i32>"},
    {"isampler2DArray", TypeCategory::Texture, Scalar::SignedInteger, 0, 0,
     0, "!hir.texture<2d_array, sampled, i32>"},
    {"isampler3D", TypeCategory::Texture, Scalar::SignedInteger, 0, 0, 0,
     "!hir.texture<3d, sampled, i32>"},
    {"isamplerCube", TypeCategory::Texture, Scalar::SignedInteger, 0, 0, 0,
     "!hir.texture<cube, sampled, i32>"},
    {"isamplerCubeArray", TypeCategory::Texture, Scalar::SignedInteger, 0, 0,
     0, "!hir.texture<cube_array, sampled, i32>"},
    {"usampler2D", TypeCategory::Texture, Scalar::UnsignedInteger, 0, 0, 0,
     "!hir.texture<2d, sampled, ui32>"},
    {"usampler2DArray", TypeCategory::Texture, Scalar::UnsignedInteger, 0, 0,
     0, "!hir.texture<2d_array, sampled, ui32>"},
    {"usampler3D", TypeCategory::Texture, Scalar::UnsignedInteger, 0, 0, 0,
     "!hir.texture<3d, sampled, ui32>"},
    {"usamplerCube", TypeCategory::Texture, Scalar::UnsignedInteger, 0, 0, 0,
     "!hir.texture<cube, sampled, ui32>"},
    {"usamplerCubeArray", TypeCategory::Texture, Scalar::UnsignedInteger, 0,
     0, 0, "!hir.texture<cube_array, sampled, ui32>"},
    {"texture2D", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<2d, separate, f32>"},
    {"texture2DArray", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<2d_array, separate, f32>"},
    {"texture3D", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<3d, separate, f32>"},
    {"textureCube", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<cube, separate, f32>"},
    {"textureCubeArray", TypeCategory::Texture, Scalar::Float, 0, 0, 0,
     "!hir.texture<cube_array, separate, f32>"},
    {"image2D", TypeCategory::StorageImage, Scalar::Float, 0, 0, 0,
     "!hir.image<2d, f32>"},
    {"iimage2D", TypeCategory::StorageImage, Scalar::SignedInteger, 0, 0, 0,
     "!hir.image<2d, i32>"},
    {"uimage2D", TypeCategory::StorageImage, Scalar::UnsignedInteger, 0, 0, 0,
     "!hir.image<2d, ui32>"},
    {"image2DArray", TypeCategory::StorageImage, Scalar::Float, 0, 0, 0,
     "!hir.image<2d_array, f32>"},
    {"iimage2DArray", TypeCategory::StorageImage, Scalar::SignedInteger, 0, 0,
     0, "!hir.image<2d_array, i32>"},
    {"uimage2DArray", TypeCategory::StorageImage, Scalar::UnsignedInteger, 0,
     0, 0, "!hir.image<2d_array, ui32>"},
    {"atomic<int>", TypeCategory::Atomic, Scalar::SignedInteger, 0, 0, 0,
     "!hir.atomic<i32>"},
    {"atomic<uint>", TypeCategory::Atomic, Scalar::UnsignedInteger, 0, 0, 0,
     "!hir.atomic<ui32>"},
}};

constexpr std::array<HIRDialectIntrinsicRecord, 29> kHIRDialectIntrinsics = {{
    {"abs", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1}, false, ""},
    {"atomicAdd", IntrinsicCategory::Atomic, Effect::ResourceReadWrite,
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2}, false, "atomic-add"},
    {"atomicAnd", IntrinsicCategory::Atomic, Effect::ResourceReadWrite,
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2}, false, "atomic-and"},
    {"atomicExchange", IntrinsicCategory::Atomic, Effect::ResourceReadWrite,
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2}, false, "atomic-exchange"},
    {"atomicMax", IntrinsicCategory::Atomic, Effect::ResourceReadWrite,
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2}, false, "atomic-max"},
    {"atomicMin", IntrinsicCategory::Atomic, Effect::ResourceReadWrite,
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2}, false, "atomic-min"},
    {"atomicOr", IntrinsicCategory::Atomic, Effect::ResourceReadWrite,
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2}, false, "atomic-or"},
    {"atomicXor", IntrinsicCategory::Atomic, Effect::ResourceReadWrite,
     HIRIntrinsicResultRule::AtomicIntegerReadModifyWriteOldValue, 2,
     std::size_t{2}, false, "atomic-xor"},
    {"atan", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{2}, true, ""},
    {"barrier", IntrinsicCategory::Synchronization, Effect::Opaque,
     HIRIntrinsicResultRule::Void, 0, std::size_t{0}, false, ""},
    {"ceil", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1}, false, ""},
    {"clamp", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 3, std::size_t{3}, false, ""},
    {"cos", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1}, false, ""},
    {"cross", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 2, std::size_t{2}, false, ""},
    {"distance", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FixedFloat, 2, std::size_t{2}, false, ""},
    {"dot", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FixedFloat, 2, std::size_t{2}, false, ""},
    {"floor", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1}, false, ""},
    {"fract", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1}, false, ""},
    {"length", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FixedFloat, 1, std::size_t{1}, true, ""},
    {"max", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 2, std::size_t{2}, false, ""},
    {"min", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 2, std::size_t{2}, false, ""},
    {"mix", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 3, std::size_t{3}, false, ""},
    {"normalize", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1}, false, ""},
    {"pow", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 2, std::size_t{2}, false, ""},
    {"reflect", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 2, std::size_t{2}, false, ""},
    {"sin", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1}, false, ""},
    {"sqrt", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1}, false, ""},
    {"tan", IntrinsicCategory::Math, Effect::Pure,
     HIRIntrinsicResultRule::FirstArgument, 1, std::size_t{1}, false, ""},
    {"workgroupBarrier", IntrinsicCategory::Synchronization, Effect::Opaque,
     HIRIntrinsicResultRule::Void, 0, std::size_t{0}, false, ""},
}};

template <typename Record, typename Name>
std::optional<HIRDialectDuplicateName>
findDuplicateName(std::span<const Record> records, Name name) {
  for (std::size_t index = 0; index < records.size(); ++index) {
    for (std::size_t other = index + 1; other < records.size(); ++other) {
      if (name(records[index]) == name(records[other])) {
        return HIRDialectDuplicateName{name(records[index]), index, other};
      }
    }
  }
  return std::nullopt;
}

template <typename Record, typename Name>
const Record *lookupByName(std::span<const Record> records,
                           std::string_view value, Name name) {
  const auto found =
      std::find_if(records.begin(), records.end(),
                   [value, name](const Record &record) {
                     return name(record) == value;
                   });
  return found == records.end() ? nullptr : &*found;
}

} // namespace

std::string_view
hirDialectOperationKindName(HIRDialectOperationKind kind) {
  switch (kind) {
  case HIRDialectOperationKind::ExpressionNode:
    return "expression-node";
  case HIRDialectOperationKind::StatementNode:
    return "statement-node";
  case HIRDialectOperationKind::BuiltinCall:
    return "builtin-call";
  }
  return "unknown";
}

std::string_view
hirDialectOperationCategoryName(HIRDialectOperationCategory category) {
  switch (category) {
  case HIRDialectOperationCategory::Core:
    return "core";
  case HIRDialectOperationCategory::ControlFlow:
    return "control-flow";
  case HIRDialectOperationCategory::DataFlow:
    return "data-flow";
  case HIRDialectOperationCategory::Texture:
    return "texture";
  case HIRDialectOperationCategory::Image:
    return "image";
  case HIRDialectOperationCategory::Atomic:
    return "atomic";
  case HIRDialectOperationCategory::Synchronization:
    return "synchronization";
  case HIRDialectOperationCategory::Structural:
    return "structural";
  }
  return "unknown";
}

std::string_view hirDialectEffectKindName(HIRDialectEffectKind effect) {
  switch (effect) {
  case HIRDialectEffectKind::Pure:
    return "pure";
  case HIRDialectEffectKind::Store:
    return "store";
  case HIRDialectEffectKind::ResourceRead:
    return "resource-read";
  case HIRDialectEffectKind::ResourceWrite:
    return "resource-write";
  case HIRDialectEffectKind::ResourceReadWrite:
    return "resource-read-write";
  case HIRDialectEffectKind::ControlTransfer:
    return "control-transfer";
  case HIRDialectEffectKind::Opaque:
    return "opaque";
  case HIRDialectEffectKind::Structural:
    return "structural";
  case HIRDialectEffectKind::Unknown:
    return "unknown";
  }
  return "unknown";
}

std::string_view hirDialectTypeCategoryName(HIRDialectTypeCategory category) {
  switch (category) {
  case HIRDialectTypeCategory::Void:
    return "void";
  case HIRDialectTypeCategory::Scalar:
    return "scalar";
  case HIRDialectTypeCategory::Vector:
    return "vector";
  case HIRDialectTypeCategory::Matrix:
    return "matrix";
  case HIRDialectTypeCategory::Sampler:
    return "sampler";
  case HIRDialectTypeCategory::Texture:
    return "texture";
  case HIRDialectTypeCategory::StorageImage:
    return "storage-image";
  case HIRDialectTypeCategory::Atomic:
    return "atomic";
  }
  return "unknown";
}

std::string_view hirDialectScalarKindName(HIRDialectScalarKind scalar) {
  switch (scalar) {
  case HIRDialectScalarKind::None:
    return "none";
  case HIRDialectScalarKind::Bool:
    return "bool";
  case HIRDialectScalarKind::SignedInteger:
    return "signed-integer";
  case HIRDialectScalarKind::UnsignedInteger:
    return "unsigned-integer";
  case HIRDialectScalarKind::Float:
    return "float";
  }
  return "unknown";
}

std::string_view
hirDialectIntrinsicCategoryName(HIRDialectIntrinsicCategory category) {
  switch (category) {
  case HIRDialectIntrinsicCategory::Math:
    return "math";
  case HIRDialectIntrinsicCategory::Atomic:
    return "atomic";
  case HIRDialectIntrinsicCategory::Synchronization:
    return "synchronization";
  }
  return "unknown";
}

std::span<const HIRDialectOperationRecord> hirDialectOperations() {
  return kHIRDialectOperations;
}

std::span<const HIRDialectTypeRecord> hirDialectTypes() {
  return kHIRDialectTypes;
}

std::span<const HIRDialectIntrinsicRecord> hirDialectIntrinsics() {
  return kHIRDialectIntrinsics;
}

const HIRDialectOperationRecord *
lookupHIRDialectOperation(std::string_view name) {
  return lookupByName<HIRDialectOperationRecord>(
      hirDialectOperations(), name,
      [](const HIRDialectOperationRecord &record) { return record.name; });
}

const HIRDialectOperationRecord *
lookupHIRDialectOperationBySourceName(std::string_view sourceName) {
  return lookupByName<HIRDialectOperationRecord>(
      hirDialectOperations(), sourceName,
      [](const HIRDialectOperationRecord &record) {
        return record.sourceName;
      });
}

const HIRDialectTypeRecord *lookupHIRDialectType(std::string_view name) {
  return lookupByName<HIRDialectTypeRecord>(
      hirDialectTypes(), name,
      [](const HIRDialectTypeRecord &record) { return record.name; });
}

const HIRDialectIntrinsicRecord *
lookupHIRDialectIntrinsic(std::string_view name) {
  return lookupByName<HIRDialectIntrinsicRecord>(
      hirDialectIntrinsics(), name,
      [](const HIRDialectIntrinsicRecord &record) { return record.name; });
}

std::optional<HIRDialectDuplicateName>
findDuplicateHIRDialectOperationName(
    std::span<const HIRDialectOperationRecord> records) {
  return findDuplicateName<HIRDialectOperationRecord>(
      records,
      [](const HIRDialectOperationRecord &record) { return record.name; });
}

std::optional<HIRDialectDuplicateName>
findDuplicateHIRDialectTypeName(
    std::span<const HIRDialectTypeRecord> records) {
  return findDuplicateName<HIRDialectTypeRecord>(
      records, [](const HIRDialectTypeRecord &record) { return record.name; });
}

std::optional<HIRDialectDuplicateName>
findDuplicateHIRDialectIntrinsicName(
    std::span<const HIRDialectIntrinsicRecord> records) {
  return findDuplicateName<HIRDialectIntrinsicRecord>(
      records,
      [](const HIRDialectIntrinsicRecord &record) { return record.name; });
}

bool validateHIRDialectCatalog(std::string *diagnostic) {
  if (const std::optional<HIRDialectDuplicateName> duplicate =
          findDuplicateHIRDialectOperationName(hirDialectOperations())) {
    if (diagnostic != nullptr) {
      *diagnostic = "duplicate HIR dialect operation name '" +
                    std::string(duplicate->name) + "'";
    }
    return false;
  }
  if (const std::optional<HIRDialectDuplicateName> duplicate =
          findDuplicateHIRDialectTypeName(hirDialectTypes())) {
    if (diagnostic != nullptr) {
      *diagnostic = "duplicate HIR dialect type name '" +
                    std::string(duplicate->name) + "'";
    }
    return false;
  }
  if (const std::optional<HIRDialectDuplicateName> duplicate =
          findDuplicateHIRDialectIntrinsicName(hirDialectIntrinsics())) {
    if (diagnostic != nullptr) {
      *diagnostic = "duplicate HIR dialect intrinsic name '" +
                    std::string(duplicate->name) + "'";
    }
    return false;
  }
  if (diagnostic != nullptr) {
    diagnostic->clear();
  }
  return true;
}

} // namespace crossgl
