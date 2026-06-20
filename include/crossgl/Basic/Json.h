#pragma once

#include <string>
#include <string_view>
#include <vector>

#include "crossgl/Basic/Diagnostic.h"

namespace crossgl {

std::string escapeJson(std::string_view text);
std::string diagnosticsToJson(const std::vector<Diagnostic> &diagnostics);

} // namespace crossgl
