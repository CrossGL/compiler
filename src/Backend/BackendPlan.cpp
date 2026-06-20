#include "crossgl/Backend/BackendPlan.h"

#include "crossgl/Backend/ResourceArrays.h"

#include <utility>

namespace crossgl {
namespace {

constexpr std::size_t kOpenGLBindingSlotsPerSet = 1024;

std::string backendEntryPointName(const HIRStage &stage) {
  return stage.stage + "_" + stage.entryPointName;
}

bool typeHasNestedArray(const HIRType &type) {
  return type.arraySize.has_value() &&
         type.arraySize->find("][") != std::string::npos;
}

BackendPlanResource planResource(const HIRStage &stage,
                                 std::string_view backendEntryPoint,
                                 const HIRResource &resource) {
  BackendPlanResource planned;
  planned.source = &resource;
  planned.stage = stage.stage;
  planned.entryPoint = stage.entryPointName;
  planned.backendEntryPoint = std::string(backendEntryPoint);
  planned.name = resource.name;
  planned.kind = resource.kind;
  planned.family = backendPlanResourceFamily(resource.kind);
  planned.type = resource.type;
  planned.sourceType = formatType(resource.type);
  planned.kindName = resourceKindName(resource.kind);
  planned.set = resource.set;
  planned.binding = resource.binding;
  planned.explicitSet = resource.explicitSet;
  planned.explicitBinding = resource.explicitBinding;
  planned.hasInterfaceBinding = resource.kind != HIRResourceKind::Shared;
  planned.emitsTargetBinding = resource.kind != HIRResourceKind::Value;
  planned.arraySize = resource.type.arraySize;
  planned.hasArray = resource.type.arraySize.has_value();
  planned.hasRuntimeArray = isRuntimeDescriptorArray(resource);
  planned.hasNestedArray = typeHasNestedArray(resource.type);
  planned.storageImageAccess = resource.storageImageAccess;
  if (resource.kind == HIRResourceKind::StorageImage) {
    planned.storageImageFormat = resolvedStorageImageFormatName(resource);
  }
  if (backendPlanResourceHasTargetBindingSlot(resource.kind)) {
    planned.directxRegisterIndex = backendPlanDirectXRegisterIndex(resource);
    planned.openglBindingIndex = backendPlanOpenGLBindingIndex(resource);
  }
  return planned;
}

} // namespace

BackendPlanResourceFamily backendPlanResourceFamily(HIRResourceKind kind) {
  switch (kind) {
  case HIRResourceKind::Uniform:
    return BackendPlanResourceFamily::UniformBuffer;
  case HIRResourceKind::Buffer:
    return BackendPlanResourceFamily::StorageBuffer;
  case HIRResourceKind::Shared:
    return BackendPlanResourceFamily::WorkgroupShared;
  case HIRResourceKind::Texture:
    return BackendPlanResourceFamily::SampledTexture;
  case HIRResourceKind::StorageImage:
    return BackendPlanResourceFamily::StorageImage;
  case HIRResourceKind::Sampler:
    return BackendPlanResourceFamily::SamplerState;
  case HIRResourceKind::Value:
    return BackendPlanResourceFamily::Value;
  }
  return BackendPlanResourceFamily::Value;
}

std::string_view
backendPlanResourceFamilyCapabilityName(BackendPlanResourceFamily family) {
  switch (family) {
  case BackendPlanResourceFamily::UniformBuffer:
    return "uniform-buffer";
  case BackendPlanResourceFamily::StorageBuffer:
    return "storage-buffer";
  case BackendPlanResourceFamily::WorkgroupShared:
    return "workgroup-shared-memory";
  case BackendPlanResourceFamily::SampledTexture:
    return "sampled-texture";
  case BackendPlanResourceFamily::StorageImage:
    return "storage-image";
  case BackendPlanResourceFamily::SamplerState:
    return "sampler-state";
  case BackendPlanResourceFamily::Value:
    return {};
  }
  return {};
}

bool backendPlanResourceHasTargetBindingSlot(HIRResourceKind kind) {
  return kind != HIRResourceKind::Shared && kind != HIRResourceKind::Value;
}

std::size_t backendPlanOpenGLBindingIndex(std::size_t set,
                                          std::size_t binding) {
  return set * kOpenGLBindingSlotsPerSet + binding;
}

std::optional<std::size_t>
backendPlanOpenGLBindingIndex(const HIRResource &resource) {
  if (!backendPlanResourceHasTargetBindingSlot(resource.kind)) {
    return std::nullopt;
  }
  return backendPlanOpenGLBindingIndex(resource.set, resource.binding);
}

std::optional<std::size_t>
backendPlanDirectXRegisterIndex(const HIRResource &resource) {
  if (!backendPlanResourceHasTargetBindingSlot(resource.kind)) {
    return std::nullopt;
  }
  return resource.binding;
}

BackendPlan buildBackendPlan(const HIRModule &module) {
  BackendPlan plan;
  plan.source = &module;
  plan.moduleName = module.name;
  plan.stages.reserve(module.stages.size());

  for (const HIRStage &stage : module.stages) {
    BackendPlanStageInterface plannedStage;
    plannedStage.source = &stage;
    plannedStage.stage = stage.stage;
    plannedStage.entryPoint = stage.entryPointName;
    plannedStage.backendEntryPoint = backendEntryPointName(stage);
    plannedStage.workgroupSize = stage.workgroupSize;
    plannedStage.resources.reserve(stage.resources.size());
    for (const HIRResource &resource : stage.resources) {
      plannedStage.resources.push_back(
          planResource(stage, plannedStage.backendEntryPoint, resource));
    }
    plan.stages.push_back(std::move(plannedStage));
  }

  return plan;
}

} // namespace crossgl
