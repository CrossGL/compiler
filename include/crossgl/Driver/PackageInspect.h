#pragma once

#include <filesystem>
#include <string>
#include <vector>

#include "crossgl/Basic/Diagnostic.h"

namespace crossgl {

struct PackageInspectResult {
  bool success = false;
  std::string json;
  std::vector<Diagnostic> diagnostics;
};

PackageInspectResult inspectPackage(const std::filesystem::path &packagePath);

} // namespace crossgl
