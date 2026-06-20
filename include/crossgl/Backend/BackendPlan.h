#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "crossgl/HIR/HIR.h"

namespace crossgl {

enum class BackendPlanResourceFamily {
  UniformBuffer,
  StorageBuffer,
  WorkgroupShared,
  SampledTexture,
  StorageImage,
  SamplerState,
  Value,
};

struct BackendPlanResource {
  const HIRResource *source = nullptr;
  std::string stage;
  std::string entryPoint;
  std::string backendEntryPoint;
  std::string name;
  HIRResourceKind kind = HIRResourceKind::Value;
  BackendPlanResourceFamily family = BackendPlanResourceFamily::Value;
  HIRType type;
  std::string sourceType;
  std::string kindName;
  std::size_t set = 0;
  std::size_t binding = 0;
  bool explicitSet = false;
  bool explicitBinding = false;
  bool hasInterfaceBinding = false;
  bool emitsTargetBinding = false;
  std::optional<std::string> arraySize;
  bool hasArray = false;
  bool hasRuntimeArray = false;
  bool hasNestedArray = false;
  HIRStorageImageAccess storageImageAccess = HIRStorageImageAccess::ReadWrite;
  std::optional<std::string> storageImageFormat;
  std::optional<std::size_t> directxRegisterIndex;
  std::optional<std::size_t> openglBindingIndex;
};

struct BackendPlanStageInterface {
  const HIRStage *source = nullptr;
  std::string stage;
  std::string entryPoint;
  std::string backendEntryPoint;
  std::optional<HIRWorkgroupSize> workgroupSize;
  std::vector<BackendPlanResource> resources;
};

struct BackendPlan {
  const HIRModule *source = nullptr;
  std::string moduleName;
  std::vector<BackendPlanStageInterface> stages;
};

BackendPlanResourceFamily backendPlanResourceFamily(HIRResourceKind kind);
std::string_view
backendPlanResourceFamilyCapabilityName(BackendPlanResourceFamily family);
bool backendPlanResourceHasTargetBindingSlot(HIRResourceKind kind);
std::size_t backendPlanOpenGLBindingIndex(std::size_t set,
                                          std::size_t binding);
std::optional<std::size_t>
backendPlanOpenGLBindingIndex(const HIRResource &resource);
std::optional<std::size_t>
backendPlanDirectXRegisterIndex(const HIRResource &resource);
BackendPlan buildBackendPlan(const HIRModule &module);

} // namespace crossgl
