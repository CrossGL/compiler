#pragma once

#include "crossgl/HIR/HIR.h"

#include <functional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace crossgl {

enum class HIRStorageBufferShapeIssueKind {
  RuntimeArrayField,
  RecursiveStruct,
};

struct HIRStorageBufferShapeIssue {
  HIRStorageBufferShapeIssueKind kind =
      HIRStorageBufferShapeIssueKind::RuntimeArrayField;
  HIRType type;
  std::string path;
};

using HIRStructLookup = std::function<const HIRStruct *(std::string_view)>;

std::vector<HIRStorageBufferShapeIssue>
collectHIRStorageBufferShapeIssues(const HIRType &elementType,
                                   const HIRStructLookup &findStruct,
                                   std::string_view resourcePath);
std::vector<HIRStorageBufferShapeIssue>
collectHIRStorageBufferShapeIssues(const HIRType &elementType,
                                   std::span<const HIRStruct> structs,
                                   std::string_view resourcePath);

} // namespace crossgl
