#include "crossgl/Driver/StorageLayout.h"
#include "crossgl/HIR/TypeSemantics.h"

#include <algorithm>
#include <limits>
#include <set>
#include <utility>

namespace crossgl {
namespace {

std::optional<std::size_t> checkedStorageAdd(std::size_t left,
                                             std::size_t right) {
  if (left > std::numeric_limits<std::size_t>::max() - right) {
    return std::nullopt;
  }
  return left + right;
}

std::optional<std::size_t> checkedStorageMultiply(std::size_t left,
                                                  std::size_t right) {
  if (right != 0 && left > std::numeric_limits<std::size_t>::max() / right) {
    return std::nullopt;
  }
  return left * right;
}

std::optional<std::size_t> checkedStorageAlignTo(std::size_t value,
                                                 std::size_t alignment) {
  if (alignment == 0) {
    return std::nullopt;
  }
  const std::size_t remainder = value % alignment;
  if (remainder == 0) {
    return value;
  }
  return checkedStorageAdd(value, alignment - remainder);
}

std::vector<std::string_view> splitArrayDimensions(std::string_view arraySize);

std::optional<std::size_t> vectorStorageWidth(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return std::nullopt;
  }
  return vectorWidthFromName(type.name);
}

std::optional<std::size_t> matrixStorageDimension(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return std::nullopt;
  }
  if (type.name == "mat2" || type.name == "mat2x2") {
    return std::size_t{2};
  }
  if (type.name == "mat3" || type.name == "mat3x3") {
    return std::size_t{3};
  }
  if (type.name == "mat4" || type.name == "mat4x4") {
    return std::size_t{4};
  }
  return std::nullopt;
}

std::size_t matrixColumnAlignmentBytes(std::size_t dimension) {
  return dimension == 2 ? std::size_t{8} : std::size_t{16};
}

std::optional<std::size_t> storageElementSizeBytes(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return std::nullopt;
  }
  if (type.name == "int" || type.name == "uint" || type.name == "float" ||
      type.name == "bool") {
    return 4;
  }
  if (const std::optional<std::size_t> width = vectorStorageWidth(type)) {
    return *width * 4;
  }
  if (const std::optional<std::size_t> dimension =
          matrixStorageDimension(type)) {
    const std::size_t columnSize = *dimension * 4;
    const std::optional<std::size_t> columnStride =
        checkedStorageAlignTo(columnSize, matrixColumnAlignmentBytes(*dimension));
    if (!columnStride.has_value()) {
      return std::nullopt;
    }
    return checkedStorageMultiply(*columnStride, *dimension);
  }
  return std::nullopt;
}

std::optional<std::size_t> storageAlignmentBytes(const HIRType &type) {
  if (type.arraySize.has_value()) {
    return std::nullopt;
  }
  if (type.name == "int" || type.name == "uint" || type.name == "float" ||
      type.name == "bool") {
    return 4;
  }
  if (const std::optional<std::size_t> width = vectorStorageWidth(type)) {
    return *width == 2 ? 8 : 16;
  }
  if (const std::optional<std::size_t> dimension =
          matrixStorageDimension(type)) {
    return matrixColumnAlignmentBytes(*dimension);
  }
  return std::nullopt;
}

std::optional<std::size_t>
storageArrayDimensionElementCountImpl(std::string_view dimension,
                                      const StorageLayoutContext &context) {
  if (const std::optional<std::size_t> literalSize =
          parsePositiveStorageSize(dimension)) {
    return literalSize;
  }

  const HIRConstant *constant = context.findConstant(dimension);
  if (constant == nullptr || !constant->foldedValue.has_value() ||
      constant->type.arraySize.has_value() ||
      (constant->type.name != "int" && constant->type.name != "uint")) {
    return std::nullopt;
  }
  return parsePositiveStorageSize(*constant->foldedValue);
}

std::optional<std::size_t>
storageArrayElementCountImpl(const HIRType &type,
                             const StorageLayoutContext &context) {
  if (!type.arraySize.has_value()) {
    return std::nullopt;
  }

  std::size_t product = 1;
  for (std::string_view dimension : splitArrayDimensions(*type.arraySize)) {
    if (dimension.empty()) {
      return std::nullopt;
    }
    const std::optional<std::size_t> dimensionCount =
        storageArrayDimensionElementCountImpl(dimension, context);
    if (!dimensionCount.has_value()) {
      return std::nullopt;
    }
    const std::optional<std::size_t> nextProduct =
        checkedStorageMultiply(product, *dimensionCount);
    if (!nextProduct.has_value()) {
      return std::nullopt;
    }
    product = *nextProduct;
  }
  return product;
}

std::vector<std::string_view> splitArrayDimensions(std::string_view arraySize) {
  std::vector<std::string_view> dimensions;
  std::size_t begin = 0;
  while (begin <= arraySize.size()) {
    const std::size_t separator = arraySize.find("][", begin);
    if (separator == std::string_view::npos) {
      dimensions.push_back(arraySize.substr(begin));
      break;
    }
    dimensions.push_back(arraySize.substr(begin, separator - begin));
    begin = separator + 2;
  }
  return dimensions;
}

std::optional<std::size_t>
arrayDimensionElementCount(std::string_view dimension,
                           const StorageLayoutContext &context) {
  return storageArrayDimensionElementCountImpl(dimension, context);
}

std::vector<StorageArrayDimension>
storageArrayDimensionsImpl(const HIRType &type,
                           const StorageLayoutContext &context) {
  std::vector<StorageArrayDimension> dimensions;
  if (!type.arraySize.has_value()) {
    return dimensions;
  }

  for (std::string_view dimensionText : splitArrayDimensions(*type.arraySize)) {
    StorageArrayDimension dimension;
    dimension.source = std::string(dimensionText);
    if (dimensionText.empty()) {
      dimension.kind = "runtime";
    } else {
      dimension.kind = "fixed";
      dimension.elementCount =
          arrayDimensionElementCount(dimensionText, context);
      if (!dimension.elementCount.has_value()) {
        dimension.kind = "unresolved";
      }
    }
    dimensions.push_back(std::move(dimension));
  }
  return dimensions;
}

std::optional<std::size_t>
fieldStorageSizeBytes(const StorageTypeLayout &layout,
                      StorageLayoutKind layoutKind) {
  if (layout.isRuntimeArray) {
    return 0;
  }
  if (layout.isArray) {
    return layout.sizeBytes;
  }
  if (layout.isStruct) {
    return checkedStorageAlignTo(layout.sizeBytes, layout.alignmentBytes);
  }
  if (layoutKind == StorageLayoutKind::MetalDevice) {
    return checkedStorageAlignTo(layout.sizeBytes, layout.alignmentBytes);
  }
  return layout.sizeBytes;
}

HIRType flattenedArrayElementType(HIRType type) {
  type.arraySize.reset();
  return type;
}

std::optional<StorageTypeLayout>
storageTypeLayout(const HIRType &type, StorageLayoutKind layoutKind,
                  const StorageLayoutContext &context,
                  bool allowRuntimeArrayTail,
                  std::set<std::string> &visiting);

std::optional<StorageTypeLayout>
storageStructLayout(const HIRStruct &structure, StorageLayoutKind layoutKind,
                    const StorageLayoutContext &context,
                    bool allowRuntimeArrayTail,
                    std::set<std::string> &visiting) {
  StorageTypeLayout layout;
  layout.isStruct = true;
  std::size_t currentOffset = 0;
  std::size_t maxAlignment = 1;

  for (std::size_t index = 0; index < structure.fields.size(); ++index) {
    const HIRField &field = structure.fields[index];
    const bool isFinalField = index + 1 == structure.fields.size();
    const bool allowFieldRuntimeArray =
        allowRuntimeArrayTail && isFinalField && isRuntimeArrayType(field.type);
    std::optional<StorageTypeLayout> fieldLayout =
        storageTypeLayout(field.type, layoutKind, context,
                          allowFieldRuntimeArray, visiting);
    if (!fieldLayout.has_value()) {
      return std::nullopt;
    }
    if (fieldLayout->hasRuntimeArray &&
        (!allowFieldRuntimeArray || !fieldLayout->isRuntimeArray)) {
      return std::nullopt;
    }

    const std::optional<std::size_t> alignedOffset =
        checkedStorageAlignTo(currentOffset, fieldLayout->alignmentBytes);
    if (!alignedOffset.has_value()) {
      return std::nullopt;
    }
    currentOffset = *alignedOffset;
    const std::optional<std::size_t> storageSize =
        fieldStorageSizeBytes(*fieldLayout, layoutKind);
    if (!storageSize.has_value()) {
      return std::nullopt;
    }
    layout.fields.push_back(StorageFieldLayout{
        field.type,
        field.name,
        index,
        currentOffset,
        fieldLayout->sizeBytes,
        *storageSize,
        fieldLayout->alignmentBytes,
        fieldLayout->isArray && !fieldLayout->isRuntimeArray
            ? std::optional<std::size_t>(fieldLayout->arrayElementCount)
            : std::nullopt,
        fieldLayout->isArray
            ? std::optional<std::size_t>(fieldLayout->arrayStrideBytes)
            : std::nullopt,
        fieldLayout->isArray ? storageArrayDimensionsImpl(field.type, context)
                             : std::vector<StorageArrayDimension>{}});
    const std::optional<std::size_t> nextOffset =
        checkedStorageAdd(currentOffset, *storageSize);
    if (!nextOffset.has_value()) {
      return std::nullopt;
    }
    currentOffset = *nextOffset;
    maxAlignment = std::max(maxAlignment, fieldLayout->alignmentBytes);
    layout.hasRuntimeArray =
        layout.hasRuntimeArray || fieldLayout->hasRuntimeArray;
  }

  layout.sizeBytes = currentOffset;
  layout.alignmentBytes = maxAlignment;
  return layout;
}

std::optional<StorageTypeLayout>
storageTypeLayout(const HIRType &type, StorageLayoutKind layoutKind,
                  const StorageLayoutContext &context,
                  bool allowRuntimeArrayTail,
                  std::set<std::string> &visiting) {
  if (type.arraySize.has_value()) {
    HIRType elementType = flattenedArrayElementType(type);
    const std::optional<StorageTypeLayout> elementLayout =
        storageTypeLayout(elementType, layoutKind, context, false, visiting);
    if (!elementLayout.has_value() || elementLayout->hasRuntimeArray) {
      return std::nullopt;
    }

    if (type.arraySize->empty()) {
      if (!allowRuntimeArrayTail) {
        return std::nullopt;
      }
      StorageTypeLayout layout;
      layout.alignmentBytes = elementLayout->alignmentBytes;
      const std::optional<std::size_t> elementStorageSize =
          fieldStorageSizeBytes(*elementLayout, layoutKind);
      if (!elementStorageSize.has_value()) {
        return std::nullopt;
      }
      const std::optional<std::size_t> arrayStride =
          checkedStorageAlignTo(*elementStorageSize,
                                elementLayout->alignmentBytes);
      if (!arrayStride.has_value()) {
        return std::nullopt;
      }
      layout.arrayStrideBytes = *arrayStride;
      layout.isArray = true;
      layout.isRuntimeArray = true;
      layout.hasRuntimeArray = true;
      return layout;
    }

    const std::optional<std::size_t> elementCount =
        storageArrayElementCountImpl(type, context);
    if (!elementCount.has_value()) {
      return std::nullopt;
    }

    StorageTypeLayout layout;
    layout.alignmentBytes = elementLayout->alignmentBytes;
    const std::optional<std::size_t> elementStorageSize =
        fieldStorageSizeBytes(*elementLayout, layoutKind);
    if (!elementStorageSize.has_value()) {
      return std::nullopt;
    }
    const std::optional<std::size_t> arrayStride =
        checkedStorageAlignTo(*elementStorageSize,
                              elementLayout->alignmentBytes);
    if (!arrayStride.has_value()) {
      return std::nullopt;
    }
    layout.arrayStrideBytes = *arrayStride;
    layout.arrayElementCount = *elementCount;
    const std::optional<std::size_t> arraySize =
        checkedStorageMultiply(layout.arrayStrideBytes, *elementCount);
    if (!arraySize.has_value()) {
      return std::nullopt;
    }
    layout.sizeBytes = *arraySize;
    layout.isArray = true;
    return layout;
  }

  if (const std::optional<std::size_t> elementSize =
          storageElementSizeBytes(type)) {
    const std::optional<std::size_t> alignment =
        storageAlignmentBytes(type);
    if (!alignment.has_value()) {
      return std::nullopt;
    }
    StorageTypeLayout layout;
    layout.sizeBytes = *elementSize;
    layout.alignmentBytes = *alignment;
    return layout;
  }

  const HIRStruct *structure = context.findStruct(type.name);
  if (structure == nullptr) {
    return std::nullopt;
  }
  if (!visiting.insert(structure->name).second) {
    return std::nullopt;
  }
  std::optional<StorageTypeLayout> layout =
      storageStructLayout(*structure, layoutKind, context,
                          allowRuntimeArrayTail, visiting);
  visiting.erase(structure->name);
  return layout;
}

} // namespace

StorageLayoutContext::StorageLayoutContext(
    const std::vector<HIRStruct> &structs,
    const std::vector<HIRConstant> &constants) {
  for (const HIRStruct &structure : structs) {
    addStruct(structure);
  }
  for (const HIRConstant &constant : constants) {
    addConstant(constant);
  }
}

void StorageLayoutContext::addStruct(const HIRStruct &structure) {
  structs_[structure.name] = &structure;
}

void StorageLayoutContext::addConstant(const HIRConstant &constant) {
  constants_[constant.name] = &constant;
}

const HIRStruct *StorageLayoutContext::findStruct(std::string_view name) const {
  const auto structure = structs_.find(std::string(name));
  if (structure == structs_.end()) {
    return nullptr;
  }
  return structure->second;
}

const HIRConstant *
StorageLayoutContext::findConstant(std::string_view name) const {
  const auto constant = constants_.find(std::string(name));
  if (constant == constants_.end()) {
    return nullptr;
  }
  return constant->second;
}

std::string_view storageLayoutName(StorageLayoutKind kind) {
  switch (kind) {
  case StorageLayoutKind::Std430:
    return "std430";
  case StorageLayoutKind::MetalDevice:
    return "metal-device";
  }
  return "";
}

std::size_t storageAlignTo(std::size_t value, std::size_t alignment) {
  if (alignment == 0) {
    return value;
  }
  const std::size_t remainder = value % alignment;
  if (remainder == 0) {
    return value;
  }
  const std::size_t padding = alignment - remainder;
  if (value > std::numeric_limits<std::size_t>::max() - padding) {
    return std::numeric_limits<std::size_t>::max();
  }
  return value + padding;
}

HIRType storageBufferElementType(HIRType type) {
  return bufferElementType(std::move(type));
}

const HIRStruct *findStructByName(const std::vector<HIRStruct> &structs,
                                  std::string_view name) {
  for (const HIRStruct &structure : structs) {
    if (structure.name == name) {
      return &structure;
    }
  }
  return nullptr;
}

std::optional<std::size_t> parsePositiveStorageSize(std::string_view text) {
  if (text.empty()) {
    return std::nullopt;
  }

  std::size_t value = 0;
  for (const char character : text) {
    if (character < '0' || character > '9') {
      return std::nullopt;
    }
    const std::size_t digit = static_cast<std::size_t>(character - '0');
    if (value > (std::numeric_limits<std::size_t>::max() - digit) / 10) {
      return std::nullopt;
    }
    value = value * 10 + digit;
  }
  if (value == 0) {
    return std::nullopt;
  }
  return value;
}

std::optional<std::size_t>
storageArrayElementCount(const HIRType &type,
                         const StorageLayoutContext &context) {
  return storageArrayElementCountImpl(type, context);
}

std::optional<std::size_t>
storageArrayElementCount(const HIRType &type,
                         const std::vector<HIRConstant> &constants) {
  const StorageLayoutContext context({}, constants);
  return storageArrayElementCount(type, context);
}

std::vector<StorageArrayDimension>
storageArrayDimensions(const HIRType &type,
                       const StorageLayoutContext &context) {
  return storageArrayDimensionsImpl(type, context);
}

std::vector<StorageArrayDimension>
storageArrayDimensions(const HIRType &type,
                       const std::vector<HIRConstant> &constants) {
  const StorageLayoutContext context({}, constants);
  return storageArrayDimensions(type, context);
}

std::optional<StorageTypeLayout>
computeStorageTypeLayout(const HIRType &type, StorageLayoutKind layout,
                         const StorageLayoutContext &context,
                         bool allowRuntimeArrayTail) {
  std::set<std::string> visiting;
  return storageTypeLayout(type, layout, context, allowRuntimeArrayTail,
                           visiting);
}

std::optional<StorageTypeLayout>
computeStorageTypeLayout(const HIRType &type, StorageLayoutKind layout,
                         const std::vector<HIRStruct> &structs,
                         const std::vector<HIRConstant> &constants,
                         bool allowRuntimeArrayTail) {
  const StorageLayoutContext context(structs, constants);
  return computeStorageTypeLayout(type, layout, context, allowRuntimeArrayTail);
}

std::optional<StorageBufferLayout>
computeStorageBufferLayoutForResource(
    const HIRResource &resource, StorageLayoutKind layoutKind,
    const StorageLayoutContext &context) {
  if (resource.kind != HIRResourceKind::Buffer) {
    return std::nullopt;
  }

  const HIRType elementType = storageBufferElementType(resource.type);
  const std::optional<StorageTypeLayout> elementLayout =
      computeStorageTypeLayout(elementType, layoutKind, context, true);
  if (!elementLayout.has_value()) {
    return std::nullopt;
  }

  StorageBufferLayout layout;
  layout.elementType = elementType;
  layout.elementSizeBytes = elementLayout->sizeBytes;
  if (elementLayout->hasRuntimeArray) {
    layout.arrayStrideBytes = 0;
  } else {
    const std::optional<std::size_t> arrayStride =
        checkedStorageAlignTo(elementLayout->sizeBytes,
                              elementLayout->alignmentBytes);
    if (!arrayStride.has_value()) {
      return std::nullopt;
    }
    layout.arrayStrideBytes = *arrayStride;
  }
  layout.layout = std::string(storageLayoutName(layoutKind));
  layout.alignmentBytes = elementLayout->alignmentBytes;
  layout.supportsScalarLayout = false;
  layout.fields = elementLayout->fields;
  return layout;
}

std::optional<StorageBufferLayout>
computeStorageBufferLayoutForResource(
    const HIRResource &resource, StorageLayoutKind layoutKind,
    const std::vector<HIRStruct> &structs,
    const std::vector<HIRConstant> &constants) {
  const StorageLayoutContext context(structs, constants);
  return computeStorageBufferLayoutForResource(resource, layoutKind, context);
}

std::optional<std::size_t>
runtimeTailFieldOffset(const HIRStruct &structure, std::size_t fieldIndex,
                       StorageLayoutKind layout,
                       const StorageLayoutContext &context) {
  if (fieldIndex >= structure.fields.size()) {
    return std::nullopt;
  }

  std::size_t currentOffset = 0;
  for (std::size_t index = 0; index < structure.fields.size(); ++index) {
    const HIRField &field = structure.fields[index];
    const bool allowRuntimeTail =
        index + 1 == structure.fields.size() && isRuntimeArrayType(field.type);
    const std::optional<StorageTypeLayout> fieldLayout =
        computeStorageTypeLayout(field.type, layout, context, allowRuntimeTail);
    if (!fieldLayout.has_value()) {
      return std::nullopt;
    }
    const std::optional<std::size_t> alignedOffset =
        checkedStorageAlignTo(currentOffset, fieldLayout->alignmentBytes);
    if (!alignedOffset.has_value()) {
      return std::nullopt;
    }
    currentOffset = *alignedOffset;
    if (index == fieldIndex) {
      return currentOffset;
    }
    const std::optional<std::size_t> storageSize =
        fieldStorageSizeBytes(*fieldLayout, layout);
    if (!storageSize.has_value()) {
      return std::nullopt;
    }
    const std::optional<std::size_t> nextOffset =
        checkedStorageAdd(currentOffset, *storageSize);
    if (!nextOffset.has_value()) {
      return std::nullopt;
    }
    currentOffset = *nextOffset;
  }

  return std::nullopt;
}

std::optional<std::size_t>
runtimeTailFieldOffset(const HIRStruct &structure, std::size_t fieldIndex,
                       StorageLayoutKind layout,
                       const std::vector<HIRStruct> &structs,
                       const std::vector<HIRConstant> &constants) {
  const StorageLayoutContext context(structs, constants);
  return runtimeTailFieldOffset(structure, fieldIndex, layout, context);
}

} // namespace crossgl
