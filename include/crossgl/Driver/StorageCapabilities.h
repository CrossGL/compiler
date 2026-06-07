#pragma once

#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "crossgl/Driver/StorageLayout.h"
#include "crossgl/HIR/HIR.h"

namespace crossgl {

enum class StorageCapabilityIssueKind {
  UnsupportedType,
  UnsupportedArrayField,
  UnsupportedRuntimeArrayField,
  UnsupportedLayout,
};

struct StorageCapabilityIssue {
  StorageCapabilityIssueKind kind = StorageCapabilityIssueKind::UnsupportedType;
  HIRType type;
  std::string path;
};

struct StorageCapabilityPolicy {
  StorageLayoutKind layoutKind = StorageLayoutKind::Std430;
  bool allowStructTypes = true;
  bool allowFixedArrays = true;
  bool allowRuntimeArrayTail = true;
  std::vector<std::string> supportedScalarTypes;
  std::vector<std::string> supportedVectorTypes;
};

std::optional<StorageCapabilityIssue>
checkStorageCapabilities(const HIRType &type,
                         const StorageLayoutContext &context,
                         const StorageCapabilityPolicy &policy,
                         bool allowRuntimeArrayTail,
                         std::string_view path);

} // namespace crossgl
