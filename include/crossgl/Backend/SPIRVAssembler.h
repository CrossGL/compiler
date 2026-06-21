#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace crossgl {

// Optional in-process SPIR-V assembly backed by the SPIRV-Tools C API.
//
// When the project is built WITH SPIRV-Tools (CROSSGL_HAVE_SPIRV_TOOLS=1), the
// Vulkan backend can assemble the SPIR-V text it generates (.spvasm) into a real
// binary module (.spv) without shelling out to the spirv-as CLI. When SPIRV-Tools
// is absent these functions compile to stubs: spirvToolsAssemblyAvailable()
// returns false and assembleVulkanSpirvText() returns std::nullopt, so callers
// build and behave correctly either way.

// Returns true when SPIRV-Tools was linked in at build time.
bool spirvToolsAssemblyAvailable();

// Assembles SPIR-V assembly text into binary words for the Vulkan native target
// environment (SPV_ENV_VULKAN_1_2 -> SPIR-V 1.5, matching kVulkanNativeTargetEnv
// / kVulkanNativeSpirvVersion). On success returns the assembled words; on
// assembly failure (or when SPIRV-Tools is unavailable) returns std::nullopt and,
// when provided, writes a human-readable diagnostic to *error.
std::optional<std::vector<std::uint32_t>>
assembleVulkanSpirvText(std::string_view assembly, std::string *error = nullptr);

} // namespace crossgl
