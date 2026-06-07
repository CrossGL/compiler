#pragma once

#include <string>
#include <string_view>
#include <vector>

namespace crossgl {

enum class TargetKind {
  Auto,
  Metal,
  Vulkan,
  DirectX,
  OpenGL,
};

struct TargetInfo {
  TargetKind kind = TargetKind::Auto;
  std::string name;
  std::string binaryExtension;
  std::string platform;
  bool implemented = false;
};

TargetKind targetFromString(std::string_view name);
std::string targetName(TargetKind target);
TargetKind defaultTargetForHost();
TargetInfo targetInfo(TargetKind target);
std::vector<TargetInfo> allTargets();

} // namespace crossgl
