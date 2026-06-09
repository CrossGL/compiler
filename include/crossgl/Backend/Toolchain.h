#pragma once

#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace crossgl {

struct ToolStatus {
  std::string name;
  std::string path;
  bool available = false;
  std::string evidenceStatus;
  std::string detail;
  std::string source;
  std::string resolvedPath;
  std::string probeStatus;
  std::string version;
  std::string versionDetail;
};

struct ToolchainStatus {
  std::string hostPlatform;
  std::string hostArch;
  std::string defaultTarget;
  std::string llvmVersion;
  bool hasLLVM = false;
  bool llvmConfigured = false;
  bool hasMLIR = false;
  bool mlirConfigured = false;
  bool mlirNativePipelineAvailable = false;
  std::vector<ToolStatus> tools;
};

struct ProcessCaptureResult {
  bool started = false;
  int exitCode = -1;
  std::string stdoutText;
  std::string stderrText;
  std::string error;
  std::string errorCategory;
};

struct ToolInvocationProvenance {
  std::string name;
  std::string executable;
  std::string resolvedExecutable;
  std::string executableSource;
  std::string version = "unknown";
  std::string versionProbeStatus;
  std::string versionDetail;
  std::string argumentsSha256;
  std::string commandShape;
  std::string responseFilePath;
  std::string outputPath;
  std::string provenanceStatus;
  std::string provenanceDetail;
};

std::optional<std::string> findExecutable(std::string_view name);
ToolStatus detectTool(std::string_view name);
ProcessCaptureResult runProcessCapture(const std::vector<std::string> &args);
std::optional<std::string> runAndCapture(const std::vector<std::string> &args);
int runProcess(const std::vector<std::string> &args);
ToolInvocationProvenance captureToolInvocationProvenance(
    std::string_view toolName, const std::vector<std::string> &args,
    std::string_view outputPath = {}, std::string_view responseFilePath = {},
    std::string_view probeToolName = {});
void completeToolInvocationProvenance(ToolInvocationProvenance &provenance,
                                      const ProcessCaptureResult &result);
void completeToolInvocationProvenance(ToolInvocationProvenance &provenance,
                                      int exitCode);
std::string toolchainOptimizationPolicyDetail(std::string_view toolName);
ToolchainStatus detectToolchain();
std::string toolchainStatusToJson(const ToolchainStatus &status);
std::string toolchainStatusToText(const ToolchainStatus &status);

} // namespace crossgl
