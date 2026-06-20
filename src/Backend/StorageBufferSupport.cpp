#include "crossgl/Backend/StorageBufferSupport.h"

#include "crossgl/Backend/BackendHIR.h"
#include "crossgl/Backend/ResourceArrays.h"
#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/HIR/HIR.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <set>
#include <string>

namespace crossgl {
namespace {

bool structStorageBufferElementSupportedImpl(
    const HIRModule &module, const HIRStruct &structure,
    StorageBufferScalarTypeSupported scalarTypeSupported,
    std::set<std::string> &visiting);

void collectStorageBufferStructDeclaration(
    const HIRModule &module, const HIRStruct &structure,
    std::set<std::string> &emitted, std::vector<const HIRStruct *> &ordered) {
  if (!emitted.insert(structure.name).second) {
    return;
  }
  for (const HIRField &field : structure.fields) {
    const HIRStruct *nested = findStruct(module, baseTypeName(field.type));
    if (nested != nullptr) {
      collectStorageBufferStructDeclaration(module, *nested, emitted, ordered);
    }
  }
  ordered.push_back(&structure);
}

bool structFieldSupported(const HIRModule &module, const HIRField &field,
                          StorageBufferScalarTypeSupported scalarTypeSupported,
                          std::set<std::string> &visiting) {
  const std::string baseName = baseTypeName(field.type);
  if (scalarTypeSupported(baseName)) {
    return !isRuntimeArrayType(field.type);
  }

  if (isRuntimeArrayType(field.type)) {
    return false;
  }
  const HIRStruct *nested = findStruct(module, baseName);
  return nested != nullptr &&
         structStorageBufferElementSupportedImpl(module, *nested,
                                                 scalarTypeSupported, visiting);
}

bool structStorageBufferElementSupportedImpl(
    const HIRModule &module, const HIRStruct &structure,
    StorageBufferScalarTypeSupported scalarTypeSupported,
    std::set<std::string> &visiting) {
  if (!visiting.insert(structure.name).second) {
    return false;
  }
  for (const HIRField &field : structure.fields) {
    if (!structFieldSupported(module, field, scalarTypeSupported, visiting)) {
      visiting.erase(structure.name);
      return false;
    }
  }
  visiting.erase(structure.name);
  return true;
}

} // namespace

bool structStorageBufferElementSupported(
    const HIRModule &module, const HIRStruct &structure,
    StorageBufferScalarTypeSupported scalarTypeSupported) {
  if (scalarTypeSupported == nullptr) {
    return false;
  }
  std::set<std::string> visiting;
  return structStorageBufferElementSupportedImpl(module, structure,
                                                scalarTypeSupported, visiting);
}

bool storageBufferElementTypeSupported(
    const HIRModule &module, const HIRType &type,
    StorageBufferScalarTypeSupported scalarTypeSupported) {
  if (scalarTypeSupported == nullptr) {
    return false;
  }
  const std::string baseName = baseTypeName(type);
  if (!type.arraySize.has_value() && scalarTypeSupported(baseName)) {
    return true;
  }
  if (type.arraySize.has_value()) {
    return false;
  }
  const HIRStruct *structure = findStruct(module, type.name);
  return structure != nullptr &&
         structStorageBufferElementSupported(module, *structure,
                                             scalarTypeSupported);
}

std::set<std::string> unsupportedStorageBufferElementTypeLabels(
    const HIRModule &module,
    StorageBufferScalarTypeSupported scalarTypeSupported) {
  std::set<std::string> elementTypes;
  if (scalarTypeSupported == nullptr) {
    return elementTypes;
  }
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind != HIRResourceKind::Buffer) {
        continue;
      }
      const HIRType elementType = bufferElementType(resource.type);
      if (!storageBufferElementTypeSupported(module, elementType,
                                             scalarTypeSupported)) {
        elementTypes.insert(resource.name + " (" + elementType.name + ")");
      }
    }
  }
  return elementTypes;
}

bool hasUnsupportedStorageBufferElementType(
    const HIRModule &module,
    StorageBufferScalarTypeSupported scalarTypeSupported) {
  return !unsupportedStorageBufferElementTypeLabels(module, scalarTypeSupported)
              .empty();
}

bool diagnoseUnsupportedStorageBufferElementType(
    const HIRModule &module, DiagnosticEngine &diagnostics,
    StorageBufferScalarTypeSupported scalarTypeSupported,
    std::string_view diagnosticCode, std::string_view targetName) {
  const std::set<std::string> elementTypes =
      unsupportedStorageBufferElementTypeLabels(module, scalarTypeSupported);
  if (elementTypes.empty()) {
    return false;
  }
  diagnostics.error(
      std::string(diagnosticCode),
      std::string(targetName) +
          " source package does not yet support storage-buffer element "
          "type(s): " +
          joinNames(elementTypes) +
          "; supported storage-buffer elements are target-supported "
          "scalar/vector/matrix types and structs with supported leaf fields, "
          "including nested structs and fixed-size supported leaf or "
          "nested-struct array fields");
  return true;
}

std::vector<const HIRStruct *> storageBufferStructDeclarations(
    const HIRModule &module, const HIRStage &stage,
    StorageBufferStructSupported structSupported) {
  std::vector<const HIRStruct *> ordered;
  if (structSupported == nullptr) {
    return ordered;
  }

  std::set<std::string> emitted;
  for (const HIRResource &resource : stage.resources) {
    if (resource.kind != HIRResourceKind::Buffer ||
        !supportedResourceArraySize(resource.type)) {
      continue;
    }
    const HIRType elementType = bufferElementType(resource.type);
    const HIRStruct *structure = findStruct(module, elementType.name);
    if (structure != nullptr && structSupported(module, *structure)) {
      collectStorageBufferStructDeclaration(module, *structure, emitted, ordered);
    }
  }
  return ordered;
}

} // namespace crossgl
