#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include "crossgl/HIR/HIR.h"

namespace crossgl {

enum class StorageLayoutKind {
  Std430,
  MetalDevice,
};

struct StorageArrayDimension {
  std::string source;
  std::string kind;
  std::optional<std::size_t> elementCount;
};

struct StorageFieldLayout {
  HIRType type;
  std::string name;
  std::size_t index = 0;
  std::size_t offsetBytes = 0;
  std::size_t sizeBytes = 0;
  std::size_t storageSizeBytes = 0;
  std::size_t alignmentBytes = 0;
  std::optional<std::size_t> arrayElementCount;
  std::optional<std::size_t> arrayStrideBytes;
  std::vector<StorageArrayDimension> arrayDimensions;
};

struct StorageTypeLayout {
  std::size_t sizeBytes = 0;
  std::size_t alignmentBytes = 0;
  std::size_t arrayStrideBytes = 0;
  std::size_t arrayElementCount = 0;
  std::vector<StorageFieldLayout> fields;
  bool isStruct = false;
  bool isArray = false;
  bool isRuntimeArray = false;
  bool hasRuntimeArray = false;
};

struct StorageBufferLayout {
  HIRType elementType;
  std::size_t elementSizeBytes = 0;
  std::size_t arrayStrideBytes = 0;
  std::string layout;
  std::size_t alignmentBytes = 0;
  bool supportsScalarLayout = false;
  std::vector<StorageFieldLayout> fields;
};

class StorageLayoutContext {
public:
  StorageLayoutContext() = default;
  StorageLayoutContext(const std::vector<HIRStruct> &structs,
                       const std::vector<HIRConstant> &constants);

  void addStruct(const HIRStruct &structure);
  void addConstant(const HIRConstant &constant);

  const HIRStruct *findStruct(std::string_view name) const;
  const HIRConstant *findConstant(std::string_view name) const;

private:
  std::unordered_map<std::string, const HIRStruct *> structs_;
  std::unordered_map<std::string, const HIRConstant *> constants_;
};

std::string_view storageLayoutName(StorageLayoutKind kind);
std::size_t storageAlignTo(std::size_t value, std::size_t alignment);
HIRType storageBufferElementType(HIRType type);
const HIRStruct *findStructByName(const std::vector<HIRStruct> &structs,
                                  std::string_view name);

std::optional<std::size_t> parsePositiveStorageSize(std::string_view text);
std::optional<std::size_t>
storageArrayElementCount(const HIRType &type,
                         const StorageLayoutContext &context);
std::optional<std::size_t>
storageArrayElementCount(const HIRType &type,
                         const std::vector<HIRConstant> &constants);
std::vector<StorageArrayDimension>
storageArrayDimensions(const HIRType &type,
                       const StorageLayoutContext &context);
std::vector<StorageArrayDimension>
storageArrayDimensions(const HIRType &type,
                       const std::vector<HIRConstant> &constants);

std::optional<StorageTypeLayout>
computeStorageTypeLayout(const HIRType &type, StorageLayoutKind layout,
                         const StorageLayoutContext &context,
                         bool allowRuntimeArrayTail);
std::optional<StorageTypeLayout>
computeStorageTypeLayout(const HIRType &type, StorageLayoutKind layout,
                         const std::vector<HIRStruct> &structs,
                         const std::vector<HIRConstant> &constants,
                         bool allowRuntimeArrayTail);

std::optional<StorageBufferLayout>
computeStorageBufferLayoutForResource(
    const HIRResource &resource, StorageLayoutKind layout,
    const StorageLayoutContext &context);
std::optional<StorageBufferLayout>
computeStorageBufferLayoutForResource(
    const HIRResource &resource, StorageLayoutKind layout,
    const std::vector<HIRStruct> &structs,
    const std::vector<HIRConstant> &constants);

std::optional<std::size_t>
runtimeTailFieldOffset(const HIRStruct &structure, std::size_t fieldIndex,
                       StorageLayoutKind layout,
                       const StorageLayoutContext &context);
std::optional<std::size_t>
runtimeTailFieldOffset(const HIRStruct &structure, std::size_t fieldIndex,
                       StorageLayoutKind layout,
                       const std::vector<HIRStruct> &structs,
                       const std::vector<HIRConstant> &constants);

} // namespace crossgl
