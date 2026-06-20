#pragma once

#include "crossgl/Basic/Diagnostic.h"

#include <filesystem>
#include <optional>
#include <string>
#include <vector>

namespace crossgl {

struct LanguageFeatureReportOptions {
  std::optional<std::filesystem::path> repositoryRoot;
  std::vector<std::string> commandLine;
};

std::optional<std::string>
languageFeatureReportJson(const std::filesystem::path &inputPath,
                          DiagnosticEngine &diagnostics,
                          const LanguageFeatureReportOptions &options = {});

} // namespace crossgl
