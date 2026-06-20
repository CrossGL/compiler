#include "crossgl/HIR/StorageShape.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <set>
#include <unordered_map>

namespace crossgl {
namespace {

using HIRStructMap = std::unordered_map<std::string, const HIRStruct *>;

HIRStructMap buildStructMap(std::span<const HIRStruct> structs) {
  HIRStructMap structMap;
  for (const HIRStruct &structure : structs) {
    if (!structure.name.empty()) {
      structMap[structure.name] = &structure;
    }
  }
  return structMap;
}

std::string appendHIRStoragePath(std::string_view base,
                                 std::string_view child) {
  if (base.empty()) {
    return std::string(child);
  }
  return std::string(base) + "." + std::string(child);
}

HIRStorageBufferShapeIssue
makeIssue(HIRStorageBufferShapeIssueKind kind, const HIRType &type,
          std::string_view path) {
  HIRStorageBufferShapeIssue issue;
  issue.kind = kind;
  issue.type = type;
  issue.path = std::string(path);
  return issue;
}

bool hasRuntimeArrayDimension(const HIRType &type) {
  if (!type.arraySize.has_value()) {
    return false;
  }

  std::string_view dimensions = *type.arraySize;
  std::size_t begin = 0;
  while (begin <= dimensions.size()) {
    const std::size_t separator = dimensions.find("][", begin);
    const std::string_view dimension =
        separator == std::string_view::npos
            ? dimensions.substr(begin)
            : dimensions.substr(begin, separator - begin);
    if (dimension.empty()) {
      return true;
    }
    if (separator == std::string_view::npos) {
      break;
    }
    begin = separator + 2;
  }
  return false;
}

void collectHIRStorageBufferShapeIssuesImpl(
    const HIRType &type, const std::string &path, bool allowRuntimeArrayTail,
    const HIRStructLookup &findStruct, std::set<std::string> &visiting,
    std::vector<HIRStorageBufferShapeIssue> &issues) {
  if (type.arraySize.has_value()) {
    if (hasRuntimeArrayDimension(type) &&
        (!allowRuntimeArrayTail || !isRuntimeArrayType(type))) {
      issues.push_back(makeIssue(HIRStorageBufferShapeIssueKind::RuntimeArrayField,
                                 type, path));
    }
    collectHIRStorageBufferShapeIssuesImpl(arrayElementType(type), path, false,
                                           findStruct, visiting, issues);
    return;
  }

  const std::string structName = baseTypeName(type);
  const HIRStruct *structure = findStruct(structName);
  if (structure == nullptr) {
    return;
  }
  if (!visiting.insert(structName).second) {
    issues.push_back(makeIssue(HIRStorageBufferShapeIssueKind::RecursiveStruct,
                               type, path));
    return;
  }

  for (std::size_t index = 0; index < structure->fields.size(); ++index) {
    const HIRField &field = structure->fields[index];
    const bool allowFieldRuntimeTail =
        allowRuntimeArrayTail && index + 1 == structure->fields.size() &&
        isRuntimeArrayType(field.type);
    collectHIRStorageBufferShapeIssuesImpl(
        field.type, appendHIRStoragePath(path, field.name),
        allowFieldRuntimeTail, findStruct, visiting, issues);
  }

  visiting.erase(structName);
}

} // namespace

std::vector<HIRStorageBufferShapeIssue>
collectHIRStorageBufferShapeIssues(const HIRType &elementType,
                                   const HIRStructLookup &findStruct,
                                   std::string_view resourcePath) {
  std::set<std::string> visiting;
  std::vector<HIRStorageBufferShapeIssue> issues;
  if (!findStruct) {
    return issues;
  }
  collectHIRStorageBufferShapeIssuesImpl(elementType, std::string(resourcePath),
                                         true, findStruct, visiting, issues);
  return issues;
}

std::vector<HIRStorageBufferShapeIssue>
collectHIRStorageBufferShapeIssues(const HIRType &elementType,
                                   std::span<const HIRStruct> structs,
                                   std::string_view resourcePath) {
  const HIRStructMap structMap = buildStructMap(structs);
  const HIRStructLookup findStruct =
      [&structMap](std::string_view name) -> const HIRStruct * {
        const auto structure = structMap.find(std::string(name));
        if (structure == structMap.end()) {
          return nullptr;
        }
        return structure->second;
      };
  return collectHIRStorageBufferShapeIssues(elementType, findStruct,
                                            resourcePath);
}

} // namespace crossgl
