#pragma once

#include <set>
#include <string>
#include <string_view>
#include <vector>

namespace crossgl {

class DiagnosticEngine;
struct HIRModule;
struct HIRStage;
struct HIRStruct;
struct HIRType;

using StorageBufferScalarTypeSupported = bool (*)(std::string_view name);
using StorageBufferStructSupported = bool (*)(const HIRModule &module,
                                             const HIRStruct &structure);

bool structStorageBufferElementSupported(
    const HIRModule &module, const HIRStruct &structure,
    StorageBufferScalarTypeSupported scalarTypeSupported);
bool storageBufferElementTypeSupported(
    const HIRModule &module, const HIRType &type,
    StorageBufferScalarTypeSupported scalarTypeSupported);
std::set<std::string> unsupportedStorageBufferElementTypeLabels(
    const HIRModule &module,
    StorageBufferScalarTypeSupported scalarTypeSupported);
bool hasUnsupportedStorageBufferElementType(
    const HIRModule &module,
    StorageBufferScalarTypeSupported scalarTypeSupported);
bool diagnoseUnsupportedStorageBufferElementType(
    const HIRModule &module, DiagnosticEngine &diagnostics,
    StorageBufferScalarTypeSupported scalarTypeSupported,
    std::string_view diagnosticCode, std::string_view targetName);
std::vector<const HIRStruct *> storageBufferStructDeclarations(
    const HIRModule &module, const HIRStage &stage,
    StorageBufferStructSupported structSupported);

} // namespace crossgl
