#pragma once

#include "crossgl/HIR/HIR.h"

#include <cstddef>
#include <optional>
#include <set>
#include <string>
#include <string_view>

namespace crossgl {

std::string stripTypeQualifier(std::string name);
HIRType stripTypeQualifier(HIRType type);
std::string stripPointerSuffix(std::string name);
std::string stripPointer(std::string name);
std::string baseTypeName(const HIRType &type);
HIRType pointerlessType(HIRType type);
HIRType arrayElementType(HIRType type);
HIRType bufferElementType(HIRType type);
bool isArrayType(const HIRType &type);
bool isRuntimeArrayType(const HIRType &type);
std::optional<HIRType> atomicPayloadType(const HIRType &type);
bool isAtomicType(const HIRType &type);
bool isAtomicIntegerType(const HIRType &type);
bool isAtomicIntegerScalarType(const HIRType &type);
bool isIntegerScalarTypeName(std::string_view name);
bool isIntegerScalarType(const HIRType &type);

bool isBuiltinType(std::string_view name);
bool isKnownType(const HIRType &type, const std::set<std::string> &structNames);

bool isTextureResourceType(std::string_view name);
bool isFloatTextureResourceType(std::string_view name);
bool isSignedIntegerTextureResourceType(std::string_view name);
bool isUnsignedIntegerTextureResourceType(std::string_view name);
bool isComparisonTextureResourceType(std::string_view name);
bool isStorageImageResourceType(std::string_view name);
bool isFloatStorageImageResourceType(std::string_view name);
bool isSignedIntegerStorageImageResourceType(std::string_view name);
bool isUnsignedIntegerStorageImageResourceType(std::string_view name);
bool isStorageImageObjectType(const HIRType &type);
bool isStorageImageDescriptorArrayType(const HIRType &type);
bool isRawSamplerResourceType(std::string_view name);
bool isComparisonSamplerResourceType(std::string_view name);
bool isSamplerResourceType(std::string_view name);
HIRResourceKind resourceKindFromName(std::string_view name);
std::string storageImageFormatName(std::string_view name);
bool isSupportedStorageImageFormatName(std::string_view format);
bool storageImageFormatCompatibleWithType(std::string_view format,
                                          std::string_view imageType);
bool storageImageFormatSupportsAtomics(std::string_view format,
                                        std::string_view imageType);
std::string storageImageDimensionName(std::string_view name);
std::string storageImagePayloadVectorTypeName(std::string_view name);
std::string storageImageAtomicPayloadTypeName(std::string_view name);
std::string storageImageCoordinateTypeName(std::string_view name);
HIRType storageImagePayloadVectorType(const HIRType &type);
HIRType storageImageAtomicPayloadType(const HIRType &type);
HIRType storageImageCoordinateType(const HIRType &type);

bool sameType(const HIRType &left, const HIRType &right);
bool isVoidType(const HIRType &type);
bool isScalarBoolType(const HIRType &type);
bool isNumericScalarTypeName(std::string_view name);
bool isFloatLike(std::string_view name);
bool isVectorType(std::string_view name);
bool isNumericVectorTypeName(std::string_view name);
bool isFloatVectorType(std::string_view name);
bool isFloatVectorType(const HIRType &type);
bool isMatrixType(std::string_view name);
bool isScalarAggregateTypePair(const HIRType &left, const HIRType &right);
bool shouldDiagnoseTypeMismatch(const HIRType &expected, const HIRType &actual);

HIRType scalarTypeForVector(std::string_view vectorType);
std::optional<std::size_t> vectorWidthFromName(std::string_view name);
std::optional<std::size_t> matrixElementCountFromName(std::string_view name);

} // namespace crossgl
