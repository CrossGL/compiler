#pragma once

#include <filesystem>
#include <optional>
#include <string>
#include <vector>

#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/Driver/PackageMetadata.h"

namespace crossgl {

struct PackageIntegrityResult {
  bool success = false;
  std::optional<PackageMetadata> metadata;
  std::vector<Diagnostic> diagnostics;
};

PackageIntegrityResult
verifyPackage(const std::filesystem::path &packagePath,
              std::optional<std::filesystem::path> sourcePath = std::nullopt);
std::string packageVerifyJson(const PackageIntegrityResult &result,
                              const std::filesystem::path &packagePath);

} // namespace crossgl
