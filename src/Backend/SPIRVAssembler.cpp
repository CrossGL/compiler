#include "crossgl/Backend/SPIRVAssembler.h"

#ifdef CROSSGL_HAVE_SPIRV_TOOLS
#include <spirv-tools/libspirv.h>

#include <string>
#endif

namespace crossgl {

#ifdef CROSSGL_HAVE_SPIRV_TOOLS

bool spirvToolsAssemblyAvailable() { return true; }

std::optional<std::vector<std::uint32_t>>
assembleVulkanSpirvText(std::string_view assembly, std::string *error) {
  // The Vulkan native target environment is vulkan1.2, which SPIRV-Tools maps to
  // SPIR-V 1.5 -- matching kVulkanNativeTargetEnv / kVulkanNativeSpirvVersion.
  spv_context context = spvContextCreate(SPV_ENV_VULKAN_1_2);
  if (context == nullptr) {
    if (error != nullptr) {
      *error = "failed to create SPIRV-Tools context";
    }
    return std::nullopt;
  }

  spv_binary binary = nullptr;
  spv_diagnostic diagnostic = nullptr;
  const spv_result_t status =
      spvTextToBinary(context, assembly.data(), assembly.size(), &binary,
                      &diagnostic);

  std::optional<std::vector<std::uint32_t>> result;
  if (status == SPV_SUCCESS && binary != nullptr) {
    result.emplace(binary->code, binary->code + binary->wordCount);
  } else if (error != nullptr) {
    if (diagnostic != nullptr && diagnostic->error != nullptr) {
      *error = diagnostic->error;
    } else {
      *error = "spvTextToBinary failed with status " + std::to_string(status);
    }
  }

  spvBinaryDestroy(binary);
  spvDiagnosticDestroy(diagnostic);
  spvContextDestroy(context);
  return result;
}

#else

bool spirvToolsAssemblyAvailable() { return false; }

std::optional<std::vector<std::uint32_t>>
assembleVulkanSpirvText(std::string_view assembly, std::string *error) {
  (void)assembly;
  if (error != nullptr) {
    *error = "SPIRV-Tools support was not compiled in";
  }
  return std::nullopt;
}

#endif

} // namespace crossgl
