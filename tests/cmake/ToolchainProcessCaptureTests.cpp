#include "crossgl/Backend/Toolchain.h"

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace {

int failures = 0;

void expect(bool condition, const std::string &message) {
  if (!condition) {
    std::cerr << "FAIL: " << message << "\n";
    ++failures;
  }
}

bool contains(std::string_view text, std::string_view needle) {
  return text.find(needle) != std::string_view::npos;
}

char pathSeparator() {
#if defined(_WIN32)
  return ';';
#else
  return ':';
#endif
}

bool setEnvVar(const char *name, const std::string &value) {
#if defined(_WIN32)
  return _putenv_s(name, value.c_str()) == 0;
#else
  return setenv(name, value.c_str(), 1) == 0;
#endif
}

class ScopedPath {
public:
  explicit ScopedPath(std::string value) {
    const char *path = std::getenv("PATH");
    if (path != nullptr) {
      oldPath = path;
    }
    changed = setEnvVar("PATH", value);
  }

  ~ScopedPath() {
    if (changed && oldPath) {
      setEnvVar("PATH", *oldPath);
    }
  }

  bool ok() const { return changed; }

private:
  std::optional<std::string> oldPath;
  bool changed = false;
};

std::filesystem::path makeTempRoot() {
  const auto tick = std::chrono::steady_clock::now().time_since_epoch().count();
  return std::filesystem::temp_directory_path() /
         ("crossgl toolchain capture " + std::to_string(tick));
}

void writeScript(const std::filesystem::path &path, int exitCode) {
  std::ofstream script(path);
#if defined(_WIN32)
  script << "@echo off\r\n"
         << "echo stdout:%~1:%~2\r\n"
         << "echo stderr:%~1:%~2 1>&2\r\n"
         << "exit /b " << exitCode << "\r\n";
#else
  script << "#!/bin/sh\n"
         << "printf 'stdout:%s:%s\\n' \"$1\" \"$2\"\n"
         << "printf 'stderr:%s:%s\\n' \"$1\" \"$2\" >&2\n"
         << "exit " << exitCode << "\n";
  script.close();
  std::filesystem::permissions(
      path, std::filesystem::perms::owner_exec |
                std::filesystem::perms::owner_read |
                std::filesystem::perms::owner_write,
      std::filesystem::perm_options::add);
#endif
}

void writeIdentifiedScript(const std::filesystem::path &path,
                           std::string_view identity) {
  std::ofstream script(path);
#if defined(_WIN32)
  script << "@echo off\r\n"
         << "echo tool:" << identity << "\r\n"
         << "exit /b 0\r\n";
#else
  script << "#!/bin/sh\n"
         << "printf 'tool:" << identity << "\\n'\n"
         << "exit 0\n";
  script.close();
  std::filesystem::permissions(
      path, std::filesystem::perms::owner_exec |
                std::filesystem::perms::owner_read |
                std::filesystem::perms::owner_write,
      std::filesystem::perm_options::add);
#endif
}

void writeExitOnlyScript(const std::filesystem::path &path, int exitCode) {
  std::ofstream script(path);
#if defined(_WIN32)
  script << "@echo off\r\n"
         << "exit /b " << exitCode << "\r\n";
#else
  script << "#!/bin/sh\n"
         << "exit " << exitCode << "\n";
  script.close();
  std::filesystem::permissions(
      path, std::filesystem::perms::owner_exec |
                std::filesystem::perms::owner_read |
                std::filesystem::perms::owner_write,
      std::filesystem::perm_options::add);
#endif
}

std::filesystem::path scriptPath(const std::filesystem::path &directory,
                                 std::string_view commandName) {
#if defined(_WIN32)
  return directory / (std::string(commandName) + ".cmd");
#else
  return directory / std::string(commandName);
#endif
}

void testProcessCapture() {
  const std::filesystem::path root = makeTempRoot();
  const std::filesystem::path scriptDir = root / "fake tool dir";
#if defined(_WIN32)
  const std::filesystem::path failingScript = scriptDir / "capture fake.cmd";
  const std::filesystem::path successScript = scriptDir / "capture ok.cmd";
  const std::filesystem::path exitStatusScript = scriptDir / "exit status.cmd";
#else
  const std::filesystem::path failingScript = scriptDir / "capture fake.sh";
  const std::filesystem::path successScript = scriptDir / "capture ok.sh";
  const std::filesystem::path exitStatusScript = scriptDir / "exit status.sh";
#endif

  std::filesystem::create_directories(scriptDir);
  writeScript(failingScript, 7);
  writeScript(successScript, 0);
  writeExitOnlyScript(exitStatusScript, 7);

  crossgl::ProcessCaptureResult result =
      crossgl::runProcessCapture({failingScript.string(), "alpha",
                                  "beta gamma"});
  expect(result.started, "process capture starts local fake command");
  expect(result.exitCode == 7, "process capture records nonzero exit status");
  expect(contains(result.stdoutText, "stdout:alpha:beta gamma"),
         "process capture records stdout");
  expect(contains(result.stderrText, "stderr:alpha:beta gamma"),
         "process capture records stderr");
  expect(result.error.empty(), "process capture leaves launch error empty");

  std::optional<std::string> stdoutOnly =
      crossgl::runAndCapture({successScript.string(), "one", "two words"});
  expect(stdoutOnly.has_value(), "runAndCapture accepts successful command");
  expect(stdoutOnly &&
             contains(*stdoutOnly, "stdout:one:two words"),
         "runAndCapture returns stdout from argv-based helper");

  crossgl::ProcessCaptureResult empty = crossgl::runProcessCapture({});
  expect(!empty.started, "empty argv does not start a process");
  expect(empty.exitCode == -1, "empty argv keeps failure exit sentinel");
  expect(!empty.error.empty(), "empty argv reports a launch error");
  expect(empty.errorCategory == "invalid-argument",
         "empty argv reports invalid argument category");

  crossgl::ProcessCaptureResult missing =
      crossgl::runProcessCapture({"crossgl-missing-process-capture-tool"});
  expect(missing.exitCode != 0, "missing command exits unsuccessfully");
  expect(missing.errorCategory == "launch",
         "missing command reports launch failure category");
  expect(!missing.error.empty(), "missing command reports launch failure");

  expect(crossgl::runProcess({exitStatusScript.string()}) == 7,
         "runProcess returns the child exit code");

  std::filesystem::remove_all(root);
}

void testExecutableDiscoveryUsesPathOrder() {
  const std::filesystem::path root = makeTempRoot();
  const std::filesystem::path firstDir = root / "first tools";
  const std::filesystem::path secondDir = root / "second tools";
  const std::string commandName = "crossgl-toolchain-order-probe";
  std::filesystem::create_directories(firstDir);
  std::filesystem::create_directories(secondDir);
  writeIdentifiedScript(scriptPath(firstDir, commandName), "first");
  writeIdentifiedScript(scriptPath(secondDir, commandName), "second");

  std::string path = firstDir.string() + pathSeparator() + secondDir.string();
  if (const char *oldPath = std::getenv("PATH")) {
    path += pathSeparator();
    path += oldPath;
  }
  ScopedPath scopedPath(path);
  expect(scopedPath.ok(), "test can override PATH for discovery ordering");

  std::optional<std::string> found = crossgl::findExecutable(commandName);
  expect(found.has_value(), "findExecutable locates command on PATH");
  expect(found && std::filesystem::equivalent(*found,
                                              scriptPath(firstDir, commandName)),
         "findExecutable honors PATH search order");

  crossgl::ProcessCaptureResult result =
      crossgl::runProcessCapture({commandName});
  expect(result.started, "runProcessCapture starts command resolved from PATH");
  expect(result.exitCode == 0, "PATH-resolved command exits successfully");
  expect(contains(result.stdoutText, "tool:first"),
         "runProcessCapture executes first PATH match");

  std::filesystem::remove_all(root);
}

void testExecutableDiscoverySkipsDirectories() {
  const std::filesystem::path root = makeTempRoot();
  const std::filesystem::path firstDir = root / "first tools";
  const std::filesystem::path secondDir = root / "second tools";
  const std::string commandName = "crossgl-toolchain-dir-probe";
  std::filesystem::create_directories(firstDir / commandName);
  std::filesystem::create_directories(secondDir);
  writeIdentifiedScript(scriptPath(secondDir, commandName), "second");

  std::string path = firstDir.string() + pathSeparator() + secondDir.string();
  if (const char *oldPath = std::getenv("PATH")) {
    path += pathSeparator();
    path += oldPath;
  }
  ScopedPath scopedPath(path);
  expect(scopedPath.ok(), "test can override PATH for directory skip");

  std::optional<std::string> found = crossgl::findExecutable(commandName);
  expect(found.has_value(), "findExecutable locates real tool after directory");
  expect(found && std::filesystem::equivalent(*found,
                                              scriptPath(secondDir, commandName)),
         "findExecutable skips PATH entries that resolve to directories");

  std::filesystem::remove_all(root);
}

void testInvocationProvenanceCapturesCommandShape() {
  const std::filesystem::path root = makeTempRoot();
  const std::filesystem::path scriptDir = root / "fake tools";
  const std::string commandName = "crossgl-toolchain-provenance-probe";
  std::filesystem::create_directories(scriptDir);
  writeScript(scriptPath(scriptDir, commandName), 0);

  std::string path = scriptDir.string();
  if (const char *oldPath = std::getenv("PATH")) {
    path += pathSeparator();
    path += oldPath;
  }
  ScopedPath scopedPath(path);
  expect(scopedPath.ok(), "test can override PATH for provenance capture");

  const std::filesystem::path outputPath = root / "out.bin";
  const std::vector<std::string> command{
      commandName, "-Fo", outputPath.string(), root.string() + "/input.hlsl"};
  crossgl::ToolInvocationProvenance provenance =
      crossgl::captureToolInvocationProvenance(commandName, command,
                                               outputPath.string());
  expect(provenance.name == commandName,
         "invocation provenance records logical tool name");
  expect(provenance.executable == commandName,
         "invocation provenance records executable name");
  expect(provenance.executableSource == "PATH",
         "invocation provenance records executable source");
  expect(!provenance.versionProbeStatus.empty(),
         "invocation provenance records version probe status");
  expect(provenance.argumentsSha256.size() == 64,
         "invocation provenance records argv hash");
  expect(contains(provenance.commandShape, "-Fo <output> <path>"),
         "invocation provenance records portable command shape");
  expect(provenance.outputPath == outputPath.string(),
         "invocation provenance records output path");

  const crossgl::ProcessCaptureResult result =
      crossgl::runProcessCapture(command);
  crossgl::completeToolInvocationProvenance(provenance, result);
  expect(provenance.provenanceStatus == "succeeded",
         "successful command completes provenance");

  crossgl::ToolInvocationProvenance missing =
      crossgl::captureToolInvocationProvenance(
          "crossgl-missing-provenance-tool",
          {"crossgl-missing-provenance-tool"});
  expect(missing.provenanceStatus == "missing-tool",
         "missing tool records missing provenance status");
  expect(contains(missing.provenanceDetail, "command was not invoked"),
         "missing tool records unavailable diagnostic");

  std::filesystem::remove_all(root);
}

} // namespace

int main() {
  testProcessCapture();
  testExecutableDiscoveryUsesPathOrder();
  testExecutableDiscoverySkipsDirectories();
  testInvocationProvenanceCapturesCommandShape();
  if (failures != 0) {
    std::cerr << failures << " toolchain process capture test(s) failed\n";
    return 1;
  }
  return 0;
}
