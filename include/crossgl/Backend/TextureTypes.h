#pragma once

#include <string_view>

namespace crossgl {

bool isFloatTextureTypeName(std::string_view name);
bool isSignedIntegerTextureTypeName(std::string_view name);
bool isUnsignedIntegerTextureTypeName(std::string_view name);
bool isComparisonTextureTypeName(std::string_view name);
bool isSupportedTextureTypeName(std::string_view name);

} // namespace crossgl
