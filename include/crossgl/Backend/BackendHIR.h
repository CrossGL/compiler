#pragma once

#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "crossgl/HIR/HIR.h"

namespace crossgl {

struct HIRModule;
struct HIRFunction;
struct HIRStage;
struct HIRStruct;
struct HIRType;
struct HIRExpression;
enum class TargetKind;

inline constexpr std::string_view kHIRBackendInputContractId =
    "crossgl.hir.backend-input";
inline constexpr std::string_view kHIRBackendInputContractVersion = "v1";
inline constexpr std::string_view kHIRBackendInputValidationPassId =
    "hir.validate.backend-input";
inline constexpr std::string_view kHIRBackendInputValidationMode =
    "backend-input-validation";

enum class HIRBackendInputValidationState {
  Unvalidated,
  Validated,
};

struct HIRBackendInputDescriptor {
  std::string contractId = std::string(kHIRBackendInputContractId);
  std::string contractVersion =
      std::string(kHIRBackendInputContractVersion);
  HIRBackendInputValidationState validationState =
      HIRBackendInputValidationState::Unvalidated;
  std::string validationPassId =
      std::string(kHIRBackendInputValidationPassId);
  std::string backendInputMode;
  std::string optimizationPolicyId;
};

struct HIRBackendInput {
  const HIRModule *module = nullptr;
  HIRBackendInputDescriptor descriptor;
};

inline std::string_view hirBackendInputValidationStateName(
    HIRBackendInputValidationState state) {
  switch (state) {
  case HIRBackendInputValidationState::Unvalidated:
    return "unvalidated";
  case HIRBackendInputValidationState::Validated:
    return "validated";
  }
  return "unknown";
}

inline bool hirBackendInputDescriptorHasStableContract(
    const HIRBackendInputDescriptor &descriptor) {
  return descriptor.contractId == kHIRBackendInputContractId &&
         descriptor.contractVersion == kHIRBackendInputContractVersion &&
         descriptor.validationPassId == kHIRBackendInputValidationPassId;
}

inline bool hirBackendInputDescriptorIsValidated(
    const HIRBackendInputDescriptor &descriptor) {
  return hirBackendInputDescriptorHasStableContract(descriptor) &&
         descriptor.validationState ==
             HIRBackendInputValidationState::Validated &&
         descriptor.backendInputMode == kHIRBackendInputValidationMode;
}

inline HIRBackendInput
makeHIRBackendInput(const HIRModule &module,
                    HIRBackendInputDescriptor descriptor) {
  HIRBackendInput input;
  input.module = &module;
  input.descriptor = std::move(descriptor);
  return input;
}

inline bool hirBackendInputIsValidated(const HIRBackendInput &input) {
  return input.module != nullptr &&
         hirBackendInputDescriptorIsValidated(input.descriptor);
}

enum class HIRFunctionParameterArrayShape {
  None,
  FixedSize,
  RuntimeSize,
  UnresolvedSize,
};

enum class HIRFunctionParameterArrayTargetSupport {
  Supported,
  UnsupportedEntryPoint,
  UnsupportedRuntimeSize,
  UnsupportedUnresolvedSize,
  UnsupportedTarget,
};

enum class HIRFunctionParameterArrayCallSemantics {
  ValueCopyReadOnly,
};

enum class HIRFunctionParameterArrayCallFeature {
  ScalarVectorElements,
  MatrixElements,
  FixedNestedArrays,
  FoldedConstantDimensions,
  DynamicNestedArrayIndices,
  StructElements,
  LocalArrayArguments,
  FunctionParameterArguments,
  StorageBufferFieldArguments,
  NestedStructFieldArguments,
  DirectResourceArrayArguments,
};

enum class HIRFunctionParameterArrayCallFeatureSupport {
  Supported,
  Unsupported,
};

enum class HIRFunctionParameterArrayWriteTarget {
  None,
  MutableLocalArray,
  ReadOnlyParameterArray,
  OtherArray,
};

enum class HIRNonUniformDescriptorResourceFamily {
  UniformBuffer,
  StorageBuffer,
  StorageImage,
  Texture,
  Sampler,
  Other,
};

struct HIRFunctionParameterArray {
  std::string stage;
  std::string function;
  std::string parameter;
  HIRType type;
  HIRFunctionParameterArrayShape shape =
      HIRFunctionParameterArrayShape::None;
  bool entryPoint = false;
};

struct HIRNonUniformDescriptorIndexUse {
  std::string stage;
  std::string function;
  std::string resource;
  HIRResourceKind resourceKind = HIRResourceKind::Value;
  HIRNonUniformDescriptorResourceFamily resourceFamily =
      HIRNonUniformDescriptorResourceFamily::Other;
  HIRType resourceType;
};

const HIRStruct *findStruct(const HIRModule &module, std::string_view name);
const HIRStage *singleComputeStage(const HIRModule &module);
const HIRFunction *entryFunction(const HIRStage &stage);
bool isResourceReferenceExpression(const HIRExpression &expression);
HIRNonUniformDescriptorResourceFamily
nonUniformDescriptorResourceFamily(HIRResourceKind kind);
std::string nonUniformDescriptorResourceFamilyName(
    HIRNonUniformDescriptorResourceFamily family);
std::vector<HIRNonUniformDescriptorIndexUse>
collectNonUniformDescriptorIndexUses(const HIRModule &module);
HIRFunctionParameterArrayShape
functionParameterArrayShape(const HIRModule &module, const HIRType &type);
std::vector<HIRFunctionParameterArray>
collectFunctionParameterArrays(const HIRModule &module);
std::string functionParameterArrayShapeName(
    HIRFunctionParameterArrayShape shape);
HIRFunctionParameterArrayTargetSupport functionParameterArrayTargetSupport(
    TargetKind target, const HIRFunctionParameterArray &array);
std::string functionParameterArrayTargetSupportName(
    HIRFunctionParameterArrayTargetSupport support);
HIRFunctionParameterArrayCallSemantics functionParameterArrayCallSemantics();
std::string functionParameterArrayCallSemanticsName(
    HIRFunctionParameterArrayCallSemantics semantics);
bool functionParameterArrayWritesVisibleToCaller(
    HIRFunctionParameterArrayCallSemantics semantics);
HIRFunctionParameterArrayWriteTarget functionParameterArrayWriteTarget(
    const HIRModule &module, const HIRFunction &function,
    const HIRExpression &target, const HIRStage *stage = nullptr);
std::string functionParameterArrayWriteTargetName(
    HIRFunctionParameterArrayWriteTarget target);
HIRFunctionParameterArrayCallFeatureSupport
functionParameterArrayCallFeatureSupport(
    HIRFunctionParameterArrayCallFeature feature);
HIRFunctionParameterArrayCallFeatureSupport
functionParameterArrayCallFeaturesSupport(
    std::span<const HIRFunctionParameterArrayCallFeature> features);
std::vector<HIRFunctionParameterArrayCallFeature>
functionParameterArrayCallUnsupportedFeatures(
    std::span<const HIRFunctionParameterArrayCallFeature> features);
bool functionParameterArrayCallRequiresRejection(
    std::span<const HIRFunctionParameterArrayCallFeature> features);
std::string functionParameterArrayCallFeatureSupportSummary(
    std::span<const HIRFunctionParameterArrayCallFeature> features);
std::vector<HIRFunctionParameterArrayCallFeature>
functionParameterArrayCallTypeFeatures(const HIRModule &module,
                                       const HIRType &type);
std::vector<HIRFunctionParameterArrayCallFeature>
functionParameterArrayCallArgumentFeatures(const HIRModule &module,
                                           const HIRFunction &function,
                                           const HIRExpression &argument,
                                           const HIRStage *stage = nullptr);
std::vector<HIRFunctionParameterArrayCallFeature>
functionParameterArrayReadFeatures(const HIRModule &module,
                                   const HIRFunction &function,
                                   const HIRExpression &expression);
std::vector<HIRFunctionParameterArrayCallFeature>
functionParameterArrayBodyReadFeatures(const HIRModule &module,
                                       const HIRFunction &function);
std::string functionParameterArrayCallFeatureName(
    HIRFunctionParameterArrayCallFeature feature);
std::string functionParameterArrayCallFeatureSupportName(
    HIRFunctionParameterArrayCallFeatureSupport support);

} // namespace crossgl
