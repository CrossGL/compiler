#include "crossgl/Driver/StorageCapabilities.h"
#include "crossgl/HIR/StorageShape.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <algorithm>
#include <set>

namespace crossgl {
namespace {

bool containsTypeName(const std::vector<std::string> &names,
                      std::string_view typeName) {
  return std::find(names.begin(), names.end(), typeName) != names.end();
}

StorageCapabilityIssue makeIssue(StorageCapabilityIssueKind kind,
                                 const HIRType &type,
                                 std::string_view path) {
  StorageCapabilityIssue issue;
  issue.kind = kind;
  issue.type = type;
  issue.path = std::string(path);
  return issue;
}

std::string childPath(std::string_view parent, std::string_view child) {
  if (parent.empty()) {
    return std::string(child);
  }
  return std::string(parent) + "." + std::string(child);
}

StorageCapabilityIssue
capabilityIssueForStorageShapeIssue(const HIRStorageBufferShapeIssue &issue) {
  switch (issue.kind) {
  case HIRStorageBufferShapeIssueKind::RuntimeArrayField:
    return makeIssue(StorageCapabilityIssueKind::UnsupportedRuntimeArrayField,
                     issue.type, issue.path);
  case HIRStorageBufferShapeIssueKind::RecursiveStruct:
    return makeIssue(StorageCapabilityIssueKind::UnsupportedLayout, issue.type,
                     issue.path);
  }
  return makeIssue(StorageCapabilityIssueKind::UnsupportedLayout, issue.type,
                   issue.path);
}

std::optional<StorageCapabilityIssue> checkStorageCapabilitiesImpl(
    const HIRType &type, const StorageLayoutContext &context,
    const StorageCapabilityPolicy &policy, bool allowRuntimeArrayTail,
    std::string_view path, std::set<std::string> &visiting) {
  if (type.arraySize.has_value()) {
    if (type.arraySize->empty()) {
      if (!policy.allowRuntimeArrayTail || !allowRuntimeArrayTail) {
        return makeIssue(StorageCapabilityIssueKind::UnsupportedRuntimeArrayField,
                         type, path);
      }
      HIRType elementType = arrayElementType(type);
      if (std::optional<StorageCapabilityIssue> issue =
              checkStorageCapabilitiesImpl(elementType, context, policy, false,
                                           path, visiting)) {
        return issue;
      }
      if (!computeStorageTypeLayout(type, policy.layoutKind, context,
                                    allowRuntimeArrayTail)
               .has_value()) {
        return makeIssue(StorageCapabilityIssueKind::UnsupportedLayout, type,
                         path);
      }
      return std::nullopt;
    }

    if (!policy.allowFixedArrays ||
        !storageArrayElementCount(type, context).has_value()) {
      return makeIssue(StorageCapabilityIssueKind::UnsupportedArrayField, type,
                       path);
    }
    HIRType elementType = arrayElementType(type);
    if (std::optional<StorageCapabilityIssue> issue =
            checkStorageCapabilitiesImpl(elementType, context, policy, false,
                                         path, visiting)) {
      return issue;
    }
    if (!computeStorageTypeLayout(type, policy.layoutKind, context,
                                  allowRuntimeArrayTail)
             .has_value()) {
      return makeIssue(StorageCapabilityIssueKind::UnsupportedLayout, type,
                       path);
    }
    return std::nullopt;
  }

  if (containsTypeName(policy.supportedScalarTypes, type.name) ||
      containsTypeName(policy.supportedVectorTypes, type.name)) {
    return std::nullopt;
  }

  const std::string structName = baseTypeName(type);
  const HIRStruct *structure = context.findStruct(structName);
  if (structure == nullptr || !policy.allowStructTypes) {
    return makeIssue(StorageCapabilityIssueKind::UnsupportedType, type, path);
  }
  if (!visiting.insert(structName).second) {
    return makeIssue(StorageCapabilityIssueKind::UnsupportedLayout, type, path);
  }

  for (std::size_t index = 0; index < structure->fields.size(); ++index) {
    const HIRField &field = structure->fields[index];
    const bool allowFieldRuntimeTail =
        allowRuntimeArrayTail && index + 1 == structure->fields.size() &&
        isRuntimeArrayType(field.type);
    const std::string fieldPath = childPath(path, field.name);
    if (std::optional<StorageCapabilityIssue> issue =
            checkStorageCapabilitiesImpl(field.type, context, policy,
                                         allowFieldRuntimeTail, fieldPath,
                                         visiting)) {
      visiting.erase(structName);
      return issue;
    }
  }
  visiting.erase(structName);

  if (!computeStorageTypeLayout(type, policy.layoutKind, context,
                                allowRuntimeArrayTail)
           .has_value()) {
    return makeIssue(StorageCapabilityIssueKind::UnsupportedLayout, type, path);
  }
  return std::nullopt;
}

} // namespace

std::optional<StorageCapabilityIssue>
checkStorageCapabilities(const HIRType &type,
                         const StorageLayoutContext &context,
                         const StorageCapabilityPolicy &policy,
                         bool allowRuntimeArrayTail,
                         std::string_view path) {
  if (policy.allowStructTypes) {
    const HIRStructLookup findStruct =
        [&context](std::string_view name) -> const HIRStruct * {
          return context.findStruct(name);
        };
    const std::vector<HIRStorageBufferShapeIssue> shapeIssues =
        collectHIRStorageBufferShapeIssues(type, findStruct, path);
    if (!shapeIssues.empty()) {
      return capabilityIssueForStorageShapeIssue(shapeIssues.front());
    }
  }

  std::set<std::string> visiting;
  return checkStorageCapabilitiesImpl(type, context, policy,
                                      allowRuntimeArrayTail, path, visiting);
}

} // namespace crossgl
