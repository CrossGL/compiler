#include "crossgl/Backend/TextureTypes.h"
#include "crossgl/HIR/TypeSemantics.h"

namespace crossgl {

bool isFloatTextureTypeName(std::string_view name) {
  return isFloatTextureResourceType(name);
}

bool isSignedIntegerTextureTypeName(std::string_view name) {
  return isSignedIntegerTextureResourceType(name);
}

bool isUnsignedIntegerTextureTypeName(std::string_view name) {
  return isUnsignedIntegerTextureResourceType(name);
}

bool isComparisonTextureTypeName(std::string_view name) {
  return isComparisonTextureResourceType(name);
}

bool isSupportedTextureTypeName(std::string_view name) {
  return isTextureResourceType(name);
}

} // namespace crossgl
