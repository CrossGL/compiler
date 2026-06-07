#pragma once

#include <filesystem>
#include <string>

namespace crossgl {

struct SourceInput {
  std::filesystem::path logicalPath;
  std::string source;
};

} // namespace crossgl
