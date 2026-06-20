#include "crossgl/Backend/Target.h"

#include <algorithm>
#include <cctype>
#include <stdexcept>

namespace crossgl {
namespace {

std::string lower(std::string_view value) {
  std::string result(value);
  std::transform(result.begin(), result.end(), result.begin(), [](unsigned char ch) {
    return static_cast<char>(std::tolower(ch));
  });
  return result;
}

} // namespace

TargetKind targetFromString(std::string_view name) {
  const std::string value = lower(name);
  if (value == "auto") {
    return TargetKind::Auto;
  }
  if (value == "metal" || value == "msl" || value == "metallib") {
    return TargetKind::Metal;
  }
  if (value == "vulkan" || value == "spirv" || value == "spv") {
    return TargetKind::Vulkan;
  }
  if (value == "directx" || value == "dxil" || value == "hlsl" || value == "dx") {
    return TargetKind::DirectX;
  }
  if (value == "opengl" || value == "glsl" || value == "ogl") {
    return TargetKind::OpenGL;
  }
  if (value == "wgsl" || value == "webgpu" || value == "wgpu") {
    return TargetKind::WGSL;
  }
  throw std::invalid_argument("unknown target '" + std::string(name) + "'");
}

std::string targetName(TargetKind target) {
  switch (target) {
  case TargetKind::Auto:
    return "auto";
  case TargetKind::Metal:
    return "metal";
  case TargetKind::Vulkan:
    return "vulkan";
  case TargetKind::DirectX:
    return "directx";
  case TargetKind::OpenGL:
    return "opengl";
  case TargetKind::WGSL:
    return "wgsl";
  }
  return "unknown";
}

TargetKind defaultTargetForHost() {
#if defined(__APPLE__)
  return TargetKind::Metal;
#elif defined(_WIN32)
  return TargetKind::DirectX;
#else
  return TargetKind::Vulkan;
#endif
}

TargetInfo targetInfo(TargetKind target) {
  if (target == TargetKind::Auto) {
    target = defaultTargetForHost();
  }

  switch (target) {
  case TargetKind::Metal:
    return TargetInfo{TargetKind::Metal, "metal", ".metallib", "macos", true};
  case TargetKind::Vulkan:
    return TargetInfo{TargetKind::Vulkan, "vulkan", ".spv", "linux", true};
  case TargetKind::DirectX:
    return TargetInfo{TargetKind::DirectX, "directx", ".dxil", "windows", false};
  case TargetKind::OpenGL:
    return TargetInfo{TargetKind::OpenGL, "opengl", ".glsl", "cross-platform", false};
  case TargetKind::WGSL:
    return TargetInfo{TargetKind::WGSL, "wgsl", ".wgsl", "webgpu/cross-platform",
                      false};
  case TargetKind::Auto:
    break;
  }
  return TargetInfo{TargetKind::Auto, "auto", "", "host", false};
}

std::vector<TargetInfo> allTargets() {
  return {targetInfo(TargetKind::Metal), targetInfo(TargetKind::Vulkan),
          targetInfo(TargetKind::DirectX), targetInfo(TargetKind::OpenGL),
          targetInfo(TargetKind::WGSL)};
}

} // namespace crossgl
