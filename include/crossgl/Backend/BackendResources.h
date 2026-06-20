#pragma once

#include "crossgl/Backend/ResourceArrays.h"
#include "crossgl/HIR/HIR.h"
#include "crossgl/HIR/TypeSemantics.h"

namespace crossgl {

template <typename StorageBufferElementTypeSupported,
          typename TextureResourceSupported, typename SamplerResourceSupported>
bool resourceSupportedByPolicy(
    const HIRModule &module, const HIRResource &resource,
    StorageBufferElementTypeSupported storageBufferElementTypeSupported,
    TextureResourceSupported textureResourceSupported,
    SamplerResourceSupported samplerResourceSupported) {
  if (resource.kind == HIRResourceKind::Buffer) {
    return supportedResourceArraySize(resource.type) &&
           storageBufferElementTypeSupported(
               module, bufferElementType(resource.type));
  }
  return textureResourceSupported(resource) || samplerResourceSupported(resource);
}

template <typename StorageBufferElementTypeSupported,
          typename TextureResourceSupported, typename SamplerResourceSupported>
bool stageResourcesSupportedByPolicy(
    const HIRModule &module, const HIRStage &stage,
    StorageBufferElementTypeSupported storageBufferElementTypeSupported,
    TextureResourceSupported textureResourceSupported,
    SamplerResourceSupported samplerResourceSupported) {
  for (const HIRResource &resource : stage.resources) {
    if (!resourceSupportedByPolicy(module, resource,
                                   storageBufferElementTypeSupported,
                                   textureResourceSupported,
                                   samplerResourceSupported)) {
      return false;
    }
  }
  return true;
}

} // namespace crossgl
