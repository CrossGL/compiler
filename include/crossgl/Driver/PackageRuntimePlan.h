#pragma once

#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

#include "crossgl/Basic/Diagnostic.h"

namespace crossgl {

enum class RuntimeLoaderPackageMode {
  Auto,
  Native,
  SourcePackage,
};

struct PackageRuntimePlanOptions {
  std::filesystem::path packagePath;
  std::string requestedTarget;
  RuntimeLoaderPackageMode packageMode = RuntimeLoaderPackageMode::Auto;
};

struct PackageRuntimePlanResult {
  bool success = false;
  std::string json;
  std::vector<Diagnostic> diagnostics;
};

std::string toString(RuntimeLoaderPackageMode mode);
bool parseRuntimeLoaderPackageMode(std::string_view text,
                                   RuntimeLoaderPackageMode &mode);

PackageRuntimePlanResult
planPackageRuntimeLoader(const PackageRuntimePlanOptions &options);

} // namespace crossgl
