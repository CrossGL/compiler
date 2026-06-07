#include "crossgl/Backend/Toolchain.h"

#include "crossgl/Backend/Target.h"
#include "crossgl/Basic/Json.h"

#include <algorithm>
#include <array>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <sstream>
#include <system_error>

#if defined(_WIN32)
#include <thread>
#include <windows.h>
#else
#include <sys/select.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <unistd.h>
#endif

namespace crossgl {
namespace {

#if defined(_WIN32)
bool equalAsciiCaseInsensitive(std::string_view lhs, std::string_view rhs) {
  if (lhs.size() != rhs.size()) {
    return false;
  }
  for (std::size_t index = 0; index < lhs.size(); ++index) {
    char left = lhs[index];
    char right = rhs[index];
    if (left >= 'A' && left <= 'Z') {
      left = static_cast<char>(left - 'A' + 'a');
    }
    if (right >= 'A' && right <= 'Z') {
      right = static_cast<char>(right - 'A' + 'a');
    }
    if (left != right) {
      return false;
    }
  }
  return true;
}

bool isWindowsBatchFile(const std::filesystem::path &path) {
  const std::string extension = path.extension().string();
  return equalAsciiCaseInsensitive(extension, ".bat") ||
         equalAsciiCaseInsensitive(extension, ".cmd");
}
#endif

std::string shellQuote(std::string_view text) {
#if defined(_WIN32)
  std::string quoted = "\"";
  for (char ch : text) {
    if (ch == '"') {
      quoted += "\\\"";
    } else {
      quoted += ch;
    }
  }
  quoted += "\"";
  return quoted;
#else
  std::string quoted = "'";
  for (char ch : text) {
    if (ch == '\'') {
      quoted += "'\\''";
    } else {
      quoted += ch;
    }
  }
  quoted += "'";
  return quoted;
#endif
}

std::string joinCommand(const std::vector<std::string> &args) {
  std::ostringstream command;
  for (std::size_t i = 0; i < args.size(); ++i) {
    if (i != 0) {
      command << ' ';
    }
    command << shellQuote(args[i]);
  }
  return command.str();
}

#if defined(_WIN32)
std::string windowsQuoteArgument(std::string_view text) {
  if (text.empty()) {
    return "\"\"";
  }

  bool needsQuoting = false;
  for (const char ch : text) {
    if (ch == ' ' || ch == '\t' || ch == '\n' || ch == '\v' || ch == '"') {
      needsQuoting = true;
      break;
    }
  }
  if (!needsQuoting) {
    return std::string(text);
  }

  std::string quoted = "\"";
  std::size_t backslashes = 0;
  for (const char ch : text) {
    if (ch == '\\') {
      ++backslashes;
      continue;
    }
    if (ch == '"') {
      quoted.append(backslashes * 2 + 1, '\\');
      quoted.push_back('"');
      backslashes = 0;
      continue;
    }
    quoted.append(backslashes, '\\');
    backslashes = 0;
    quoted.push_back(ch);
  }
  quoted.append(backslashes * 2, '\\');
  quoted.push_back('"');
  return quoted;
}

std::wstring widenUtf8(std::string_view text) {
  if (text.empty()) {
    return {};
  }
  const int size = MultiByteToWideChar(CP_UTF8, 0, text.data(),
                                      static_cast<int>(text.size()), nullptr, 0);
  if (size <= 0) {
    return std::wstring(text.begin(), text.end());
  }
  std::wstring wide(static_cast<std::size_t>(size), L'\0');
  MultiByteToWideChar(CP_UTF8, 0, text.data(), static_cast<int>(text.size()),
                      wide.data(), size);
  return wide;
}

std::wstring windowsCommandLine(const std::vector<std::string> &args) {
  std::string command;
  for (std::size_t i = 0; i < args.size(); ++i) {
    if (i != 0) {
      command.push_back(' ');
    }
    command += windowsQuoteArgument(args[i]);
  }
  return widenUtf8(command);
}

std::wstring windowsBatchCommandLine(const std::vector<std::string> &args) {
  std::string command = "cmd.exe /d /s /c call";
  for (const std::string &arg : args) {
    command.push_back(' ');
    command += windowsQuoteArgument(arg);
  }
  return widenUtf8(command);
}

void closeHandleIfValid(HANDLE handle) {
  if (handle != nullptr && handle != INVALID_HANDLE_VALUE) {
    CloseHandle(handle);
  }
}

std::string readPipeToString(HANDLE pipe) {
  std::array<char, 4096> buffer = {};
  std::string result;
  DWORD bytesRead = 0;
  while (ReadFile(pipe, buffer.data(), static_cast<DWORD>(buffer.size()),
                  &bytesRead, nullptr) &&
         bytesRead > 0) {
    result.append(buffer.data(), buffer.data() + bytesRead);
  }
  return result;
}

std::string windowsLastErrorMessage(std::string_view action,
                                    DWORD errorCode = GetLastError()) {
  std::ostringstream out;
  out << action << " failed with Windows error " << errorCode;
  return out.str();
}
#else
void closeFdIfValid(int fd) {
  if (fd >= 0) {
    close(fd);
  }
}

void setCloseOnExec(int fd) {
  if (fd < 0) {
    return;
  }
  const int flags = fcntl(fd, F_GETFD);
  if (flags >= 0) {
    fcntl(fd, F_SETFD, flags | FD_CLOEXEC);
  }
}

std::string errnoMessage(int errorNumber) {
  return std::strerror(errorNumber);
}

bool readReadyFd(int fd, std::string &target) {
  std::array<char, 4096> buffer = {};
  const ssize_t bytesRead = read(fd, buffer.data(), buffer.size());
  if (bytesRead > 0) {
    target.append(buffer.data(),
                  buffer.data() + static_cast<std::size_t>(bytesRead));
    return true;
  }
  if (bytesRead == 0) {
    return false;
  }
  return errno == EINTR;
}

void readProcessPipes(int stdoutFd, int stderrFd, std::string &stdoutText,
                      std::string &stderrText) {
  bool stdoutOpen = stdoutFd >= 0;
  bool stderrOpen = stderrFd >= 0;
  while (stdoutOpen || stderrOpen) {
    fd_set readSet;
    FD_ZERO(&readSet);
    int maxFd = -1;
    if (stdoutOpen) {
      FD_SET(stdoutFd, &readSet);
      maxFd = std::max(maxFd, stdoutFd);
    }
    if (stderrOpen) {
      FD_SET(stderrFd, &readSet);
      maxFd = std::max(maxFd, stderrFd);
    }

    const int ready = select(maxFd + 1, &readSet, nullptr, nullptr, nullptr);
    if (ready < 0) {
      if (errno == EINTR) {
        continue;
      }
      break;
    }

    if (stdoutOpen && FD_ISSET(stdoutFd, &readSet)) {
      stdoutOpen = readReadyFd(stdoutFd, stdoutText);
      if (!stdoutOpen) {
        closeFdIfValid(stdoutFd);
      }
    }
    if (stderrOpen && FD_ISSET(stderrFd, &readSet)) {
      stderrOpen = readReadyFd(stderrFd, stderrText);
      if (!stderrOpen) {
        closeFdIfValid(stderrFd);
      }
    }
  }

  if (stdoutOpen) {
    closeFdIfValid(stdoutFd);
  }
  if (stderrOpen) {
    closeFdIfValid(stderrFd);
  }
}

std::optional<int> readExecFailureErrno(int fd) {
  int errorNumber = 0;
  char *cursor = reinterpret_cast<char *>(&errorNumber);
  std::size_t remaining = sizeof(errorNumber);
  while (remaining > 0) {
    const ssize_t bytesRead = read(fd, cursor, remaining);
    if (bytesRead > 0) {
      cursor += bytesRead;
      remaining -= static_cast<std::size_t>(bytesRead);
      continue;
    }
    if (bytesRead == 0) {
      break;
    }
    if (errno == EINTR) {
      continue;
    }
    break;
  }
  if (remaining == 0) {
    return errorNumber;
  }
  return std::nullopt;
}

int decodeSystemStatus(int status) {
  if (status == -1) {
    return 1;
  }
  if (WIFEXITED(status)) {
    return WEXITSTATUS(status);
  }
  if (WIFSIGNALED(status)) {
    return 128 + WTERMSIG(status);
  }
  return 1;
}
#endif

std::vector<std::filesystem::path> pathEntries() {
  std::vector<std::filesystem::path> entries;
  const char *pathEnv = std::getenv("PATH");
  if (!pathEnv) {
    return entries;
  }
  std::string path(pathEnv);
#if defined(_WIN32)
  const char separator = ';';
#else
  const char separator = ':';
#endif
  std::size_t start = 0;
  while (start <= path.size()) {
    const std::size_t end = path.find(separator, start);
    entries.emplace_back(path.substr(start, end == std::string::npos ? end : end - start));
    if (end == std::string::npos) {
      break;
    }
    start = end + 1;
  }
  return entries;
}

bool isExecutableFile(const std::filesystem::path &path) {
  std::error_code error;
  if (!std::filesystem::is_regular_file(path, error)) {
    return false;
  }
#if defined(_WIN32)
  return true;
#else
  return access(path.c_str(), X_OK) == 0;
#endif
}

struct ExecutableSearchResult {
  std::string path;
  std::string source;
};

std::string trimProbeOutput(std::string text) {
  while (!text.empty() &&
         (text.back() == '\n' || text.back() == '\r' ||
          text.back() == ' ' || text.back() == '\t')) {
    text.pop_back();
  }
  std::size_t start = 0;
  while (start < text.size() &&
         (text[start] == '\n' || text[start] == '\r' ||
          text[start] == ' ' || text[start] == '\t')) {
    ++start;
  }
  if (start != 0) {
    text.erase(0, start);
  }
  return text;
}

std::string firstProbeLine(std::string text) {
  text = trimProbeOutput(std::move(text));
  const std::size_t newline = text.find_first_of("\r\n");
  if (newline != std::string::npos) {
    text.erase(newline);
  }
  constexpr std::size_t maxProbeLineLength = 240;
  if (text.size() > maxProbeLineLength) {
    text.resize(maxProbeLineLength);
  }
  return text;
}

std::optional<ExecutableSearchResult>
findExecutableWithSource(std::string_view name) {
  const std::filesystem::path requested(name);
  if (requested.has_parent_path() && isExecutableFile(requested)) {
    return ExecutableSearchResult{requested.string(), "direct"};
  }

  for (const std::filesystem::path &entry : pathEntries()) {
    std::filesystem::path candidate = entry / std::string(name);
    if (isExecutableFile(candidate)) {
      return ExecutableSearchResult{candidate.string(), "PATH"};
    }
#if defined(_WIN32)
    for (std::string_view extension : {".exe", ".cmd", ".bat", ".com"}) {
      candidate = entry / (std::string(name) + std::string(extension));
      if (isExecutableFile(candidate)) {
        return ExecutableSearchResult{candidate.string(), "PATH"};
      }
    }
#endif
  }

  if (const char *disableFallbacks =
          std::getenv("CROSSGL_DISABLE_TOOLCHAIN_FALLBACKS")) {
    if (std::string_view(disableFallbacks) == "1") {
      return std::nullopt;
    }
  }

  const std::array<std::filesystem::path, 4> fallbackDirs = {
      "/opt/homebrew/opt/llvm/bin", "/opt/homebrew/bin", "/usr/local/bin",
      "/usr/bin"};
  for (const std::filesystem::path &entry : fallbackDirs) {
    std::filesystem::path candidate = entry / std::string(name);
    if (isExecutableFile(candidate)) {
      return ExecutableSearchResult{candidate.string(), "fallback"};
    }
  }

  return std::nullopt;
}

void populateVersionProbe(ToolStatus &status) {
  if (!status.available || status.resolvedPath.empty()) {
    status.evidenceStatus = "tool-missing";
    status.probeStatus = "unavailable";
    return;
  }

  const ProcessCaptureResult probe =
      runProcessCapture({status.resolvedPath, "--version"});
  if (probe.errorCategory == "launch") {
    status.evidenceStatus = "probe-failed";
    status.probeStatus = "failed";
    status.versionDetail = probe.error;
    return;
  }
  if (!probe.started) {
    status.evidenceStatus = "probe-failed";
    status.probeStatus = "not-started";
    status.versionDetail = probe.error;
    return;
  }

  if (probe.exitCode == 0) {
    const std::string version = firstProbeLine(
        probe.stdoutText.empty() ? probe.stderrText : probe.stdoutText);
    if (version.empty()) {
      status.evidenceStatus = "version-unknown";
      status.probeStatus = "version-unknown";
      status.versionDetail = "version probe produced no output";
      return;
    }
    status.evidenceStatus = "version-captured";
    status.probeStatus = "succeeded";
    status.version = version;
    return;
  }

  status.evidenceStatus = "probe-failed";
  status.probeStatus = "failed";
  std::ostringstream detail;
  detail << "exit " << probe.exitCode;
  const std::string probeOutput = firstProbeLine(
      probe.stderrText.empty() ? probe.stdoutText : probe.stderrText);
  if (!probeOutput.empty()) {
    detail << ": " << probeOutput;
  }
  status.versionDetail = detail.str();
}

ToolStatus executableStatus(std::string name, std::string displayName = "") {
  ToolStatus status;
  status.name = displayName.empty() ? name : std::move(displayName);
  if (auto result = findExecutableWithSource(name)) {
    status.path = result->path;
    status.resolvedPath = result->path;
    status.source = result->source;
    status.available = true;
  } else {
    status.source = "not-found";
  }
  populateVersionProbe(status);
  return status;
}

void appendToolDetail(ToolStatus &status, std::string_view detail) {
  if (detail.empty()) {
    return;
  }
  if (!status.detail.empty()) {
    status.detail += "; ";
  }
  status.detail.append(detail.data(), detail.size());
}

ToolStatus spirvOptStatus() {
  ToolStatus status = executableStatus("spirv-opt");
  appendToolDetail(status, toolchainOptimizationPolicyDetail("spirv-opt"));
  return status;
}

ToolStatus dxcStatus() {
  ToolStatus status = executableStatus("dxc");
  appendToolDetail(status, toolchainOptimizationPolicyDetail("dxc"));
  return status;
}

ToolStatus xcrunToolStatus(std::string name) {
  ToolStatus status;
  status.name = name;
  if (!findExecutable("xcrun")) {
    status.detail = "xcrun not found";
    status.source = "not-found";
    populateVersionProbe(status);
    return status;
  }
  auto output = runAndCapture({"xcrun", "-find", name});
  if (!output || output->empty()) {
    status.detail = "xcrun could not locate " + name;
    status.source = "xcrun";
    populateVersionProbe(status);
    return status;
  }
  status.path = *output;
  while (!status.path.empty() &&
         (status.path.back() == '\n' || status.path.back() == '\r')) {
    status.path.pop_back();
  }
  status.resolvedPath = status.path;
  status.source = "xcrun";
  status.available = !status.resolvedPath.empty();
  populateVersionProbe(status);
  return status;
}

ToolStatus metalToolStatus() {
  ToolStatus status = xcrunToolStatus("metal");
  appendToolDetail(status, toolchainOptimizationPolicyDetail("metal"));
  return status;
}

ToolStatus metallibToolStatus() {
  ToolStatus status = xcrunToolStatus("metallib");
  appendToolDetail(status, toolchainOptimizationPolicyDetail("metallib"));
  return status;
}

#if !defined(__APPLE__)
ToolStatus fallbackMetalToolStatus(std::string name) {
  ToolStatus status = executableStatus(name);
  appendToolDetail(status, toolchainOptimizationPolicyDetail(name));
  return status;
}
#endif

std::string hostPlatform() {
#if defined(__APPLE__)
  return "macos";
#elif defined(_WIN32)
  return "windows";
#elif defined(__linux__)
  return "linux";
#else
  return "unknown";
#endif
}

std::string hostArch() {
#if defined(__aarch64__) || defined(_M_ARM64)
  return "arm64";
#elif defined(__x86_64__) || defined(_M_X64)
  return "x86_64";
#else
  return "unknown";
#endif
}

} // namespace

std::optional<std::string> findExecutable(std::string_view name) {
  if (auto result = findExecutableWithSource(name)) {
    return result->path;
  }
  return std::nullopt;
}

ToolStatus detectTool(std::string_view name) {
#if defined(__APPLE__)
  if (name == "metal" || name == "metallib") {
    return name == "metal" ? metalToolStatus() : metallibToolStatus();
  }
#else
  if (name == "metal" || name == "metallib") {
    return fallbackMetalToolStatus(std::string(name));
  }
#endif
  if (name == "dxc") {
    return dxcStatus();
  }
  if (name == "spirv-opt") {
    return spirvOptStatus();
  }
  return executableStatus(std::string(name));
}

ProcessCaptureResult runProcessCapture(const std::vector<std::string> &args) {
  ProcessCaptureResult result;
  if (args.empty()) {
    result.error = "no command specified";
    result.errorCategory = "invalid-argument";
    return result;
  }
#if defined(_WIN32)
  std::vector<std::string> commandArgs = args;
  if (std::optional<std::string> executable = findExecutable(commandArgs[0])) {
    commandArgs[0] = std::move(*executable);
  }
  std::wstring command = isWindowsBatchFile(commandArgs[0])
                             ? windowsBatchCommandLine(commandArgs)
                             : windowsCommandLine(commandArgs);

  SECURITY_ATTRIBUTES securityAttributes = {};
  securityAttributes.nLength = sizeof(securityAttributes);
  securityAttributes.bInheritHandle = TRUE;

  HANDLE stdoutRead = nullptr;
  HANDLE stdoutWrite = nullptr;
  HANDLE stderrRead = nullptr;
  HANDLE stderrWrite = nullptr;
  if (!CreatePipe(&stdoutRead, &stdoutWrite, &securityAttributes, 0)) {
    result.error = windowsLastErrorMessage("CreatePipe(stdout)");
    result.errorCategory = "capture-setup";
    return result;
  }
  if (!SetHandleInformation(stdoutRead, HANDLE_FLAG_INHERIT, 0)) {
    result.error = windowsLastErrorMessage("SetHandleInformation(stdout)");
    result.errorCategory = "capture-setup";
    closeHandleIfValid(stdoutRead);
    closeHandleIfValid(stdoutWrite);
    return result;
  }
  if (!CreatePipe(&stderrRead, &stderrWrite, &securityAttributes, 0)) {
    result.error = windowsLastErrorMessage("CreatePipe(stderr)");
    result.errorCategory = "capture-setup";
    closeHandleIfValid(stdoutRead);
    closeHandleIfValid(stdoutWrite);
    return result;
  }
  if (!SetHandleInformation(stderrRead, HANDLE_FLAG_INHERIT, 0)) {
    result.error = windowsLastErrorMessage("SetHandleInformation(stderr)");
    result.errorCategory = "capture-setup";
    closeHandleIfValid(stdoutRead);
    closeHandleIfValid(stdoutWrite);
    closeHandleIfValid(stderrRead);
    closeHandleIfValid(stderrWrite);
    return result;
  }

  STARTUPINFOW startupInfo = {};
  startupInfo.cb = sizeof(startupInfo);
  startupInfo.dwFlags = STARTF_USESTDHANDLES;
  startupInfo.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
  startupInfo.hStdOutput = stdoutWrite;
  startupInfo.hStdError = stderrWrite;
  PROCESS_INFORMATION processInfo = {};
  if (!CreateProcessW(nullptr, command.data(), nullptr, nullptr, TRUE, 0,
                      nullptr, nullptr, &startupInfo, &processInfo)) {
    result.error = windowsLastErrorMessage("CreateProcessW");
    result.errorCategory = "launch";
    closeHandleIfValid(stdoutRead);
    closeHandleIfValid(stdoutWrite);
    closeHandleIfValid(stderrRead);
    closeHandleIfValid(stderrWrite);
    return result;
  }

  closeHandleIfValid(stdoutWrite);
  closeHandleIfValid(stderrWrite);

  std::thread stdoutThread([&] {
    result.stdoutText = readPipeToString(stdoutRead);
    closeHandleIfValid(stdoutRead);
  });
  std::thread stderrThread([&] {
    result.stderrText = readPipeToString(stderrRead);
    closeHandleIfValid(stderrRead);
  });

  WaitForSingleObject(processInfo.hProcess, INFINITE);
  DWORD exitCode = 1;
  GetExitCodeProcess(processInfo.hProcess, &exitCode);
  stdoutThread.join();
  stderrThread.join();
  CloseHandle(processInfo.hThread);
  CloseHandle(processInfo.hProcess);

  result.started = true;
  result.exitCode = static_cast<int>(exitCode);
#else
  int stdoutPipe[2] = {-1, -1};
  int stderrPipe[2] = {-1, -1};
  int execErrorPipe[2] = {-1, -1};
  if (pipe(stdoutPipe) != 0) {
    result.error = std::string("pipe(stdout) failed: ") + std::strerror(errno);
    result.errorCategory = "capture-setup";
    return result;
  }
  if (pipe(stderrPipe) != 0) {
    result.error = std::string("pipe(stderr) failed: ") + std::strerror(errno);
    result.errorCategory = "capture-setup";
    closeFdIfValid(stdoutPipe[0]);
    closeFdIfValid(stdoutPipe[1]);
    return result;
  }
  if (pipe(execErrorPipe) != 0) {
    result.error =
        std::string("pipe(exec error) failed: ") + std::strerror(errno);
    result.errorCategory = "capture-setup";
    closeFdIfValid(stdoutPipe[0]);
    closeFdIfValid(stdoutPipe[1]);
    closeFdIfValid(stderrPipe[0]);
    closeFdIfValid(stderrPipe[1]);
    return result;
  }
  setCloseOnExec(execErrorPipe[1]);

  const pid_t child = fork();
  if (child < 0) {
    result.error = std::string("fork failed: ") + std::strerror(errno);
    result.errorCategory = "launch";
    closeFdIfValid(stdoutPipe[0]);
    closeFdIfValid(stdoutPipe[1]);
    closeFdIfValid(stderrPipe[0]);
    closeFdIfValid(stderrPipe[1]);
    closeFdIfValid(execErrorPipe[0]);
    closeFdIfValid(execErrorPipe[1]);
    return result;
  }

  if (child == 0) {
    closeFdIfValid(stdoutPipe[0]);
    closeFdIfValid(stderrPipe[0]);
    closeFdIfValid(execErrorPipe[0]);
    dup2(stdoutPipe[1], STDOUT_FILENO);
    dup2(stderrPipe[1], STDERR_FILENO);
    closeFdIfValid(stdoutPipe[1]);
    closeFdIfValid(stderrPipe[1]);

    std::vector<char *> argv;
    argv.reserve(args.size() + 1);
    for (const std::string &arg : args) {
      argv.push_back(const_cast<char *>(arg.c_str()));
    }
    argv.push_back(nullptr);
    execvp(argv[0], argv.data());

    const int execError = errno;
    const std::string error = "failed to execute " + args[0] + ": " +
                              errnoMessage(execError) + "\n";
    write(execErrorPipe[1], &execError, sizeof(execError));
    closeFdIfValid(execErrorPipe[1]);
    write(STDERR_FILENO, error.data(), error.size());
    _exit(127);
  }

  closeFdIfValid(stdoutPipe[1]);
  closeFdIfValid(stderrPipe[1]);
  closeFdIfValid(execErrorPipe[1]);
  readProcessPipes(stdoutPipe[0], stderrPipe[0], result.stdoutText,
                   result.stderrText);
  const std::optional<int> execFailureErrno =
      readExecFailureErrno(execErrorPipe[0]);
  closeFdIfValid(execErrorPipe[0]);

  int childStatus = 0;
  while (waitpid(child, &childStatus, 0) < 0) {
    if (errno != EINTR) {
      result.error = std::string("waitpid failed: ") + std::strerror(errno);
      result.errorCategory = "wait";
      break;
    }
  }

  result.started = true;
  if (execFailureErrno) {
    result.error = "failed to execute " + args[0] + ": " +
                   errnoMessage(*execFailureErrno);
    result.errorCategory = "launch";
  }
  if (WIFEXITED(childStatus)) {
    result.exitCode = WEXITSTATUS(childStatus);
  } else if (WIFSIGNALED(childStatus)) {
    result.exitCode = 128 + WTERMSIG(childStatus);
  } else {
    result.exitCode = 1;
  }
#endif

  return result;
}

std::optional<std::string> runAndCapture(const std::vector<std::string> &args) {
  ProcessCaptureResult result = runProcessCapture(args);
  if (!result.started || result.exitCode != 0) {
    return std::nullopt;
  }
  return result.stdoutText;
}

int runProcess(const std::vector<std::string> &args) {
  if (args.empty()) {
    return 1;
  }
#if defined(_WIN32)
  std::vector<std::string> commandArgs = args;
  if (std::optional<std::string> executable = findExecutable(commandArgs[0])) {
    commandArgs[0] = std::move(*executable);
  }
  if (isWindowsBatchFile(commandArgs[0])) {
    const std::string command = "call " + joinCommand(commandArgs);
    return std::system(command.c_str());
  }

  std::wstring command = windowsCommandLine(commandArgs);
  STARTUPINFOW startupInfo = {};
  startupInfo.cb = sizeof(startupInfo);
  PROCESS_INFORMATION processInfo = {};
  if (!CreateProcessW(nullptr, command.data(), nullptr, nullptr, FALSE, 0,
                      nullptr, nullptr, &startupInfo, &processInfo)) {
    return static_cast<int>(GetLastError());
  }
  WaitForSingleObject(processInfo.hProcess, INFINITE);
  DWORD exitCode = 1;
  GetExitCodeProcess(processInfo.hProcess, &exitCode);
  CloseHandle(processInfo.hThread);
  CloseHandle(processInfo.hProcess);
  return static_cast<int>(exitCode);
#else
  const std::string command = joinCommand(args);
  return decodeSystemStatus(std::system(command.c_str()));
#endif
}

std::string toolchainOptimizationPolicyDetail(std::string_view toolName) {
  if (toolName == "spirv-opt") {
    return "Vulkan optimizer policy: O0/O1 record skipped-disabled and do not "
           "invoke spirv-opt; O2 invokes spirv-opt --target-env=vulkan1.2 -O "
           "when found and records skipped-tool-missing when absent";
  }
  if (toolName == "dxc") {
    return "DirectX DXIL policy: O0 invokes dxc -O0; O1/O2 invoke dxc -O3; "
           "missing or failing dxc keeps nativeBinaryStatus planned";
  }
  if (toolName == "metal" || toolName == "xcrun metal") {
    return "Metal compiler policy: O0 invokes xcrun -sdk macosx metal -O0 "
           "-gline-tables-only; O1/O2 invoke xcrun -sdk macosx metal -O2";
  }
  if (toolName == "metallib" || toolName == "xcrun metallib") {
    return "Metal library policy: xcrun -sdk macosx metallib uses default "
           "link behavior for O0/O1/O2";
  }
  return "";
}

ToolchainStatus detectToolchain() {
  ToolchainStatus status;
  status.hostPlatform = hostPlatform();
  status.hostArch = hostArch();
  status.defaultTarget = targetName(defaultTargetForHost());
  status.llvmVersion = CROSSGL_LLVM_VERSION;
  status.hasLLVM = CROSSGL_HAS_LLVM != 0;
  status.llvmConfigured = status.hasLLVM;
  status.hasMLIR = CROSSGL_HAS_MLIR != 0;
  status.mlirConfigured = status.hasMLIR;
  status.mlirNativePipelineAvailable =
      status.mlirConfigured && CROSSGL_ENABLE_MLIR_EXPERIMENTAL != 0;

  status.tools.push_back(executableStatus("cmake"));
  status.tools.push_back(executableStatus("ninja"));
  status.tools.push_back(executableStatus("clang++"));
  status.tools.push_back(executableStatus("llvm-config"));
  status.tools.push_back(executableStatus("opt"));
  status.tools.push_back(executableStatus("llc"));
  status.tools.push_back(executableStatus("mlir-opt"));
  status.tools.push_back(executableStatus("spirv-as"));
  status.tools.push_back(executableStatus("spirv-val"));
  status.tools.push_back(spirvOptStatus());
  status.tools.push_back(executableStatus("spirv-dis"));
  status.tools.push_back(dxcStatus());
  status.tools.push_back(executableStatus("glslangValidator"));
#if defined(__APPLE__)
  status.tools.push_back(metalToolStatus());
  status.tools.push_back(metallibToolStatus());
#else
  status.tools.push_back(fallbackMetalToolStatus("metal"));
  status.tools.push_back(fallbackMetalToolStatus("metallib"));
#endif

  return status;
}

std::string toolchainStatusToJson(const ToolchainStatus &status) {
  std::ostringstream out;
  out << "{\n"
      << "  \"hostPlatform\": \"" << escapeJson(status.hostPlatform) << "\",\n"
      << "  \"hostArch\": \"" << escapeJson(status.hostArch) << "\",\n"
      << "  \"defaultTarget\": \"" << escapeJson(status.defaultTarget) << "\",\n"
      << "  \"llvmVersion\": \"" << escapeJson(status.llvmVersion) << "\",\n"
      << "  \"hasLLVM\": " << (status.hasLLVM ? "true" : "false") << ",\n"
      << "  \"llvmConfigured\": "
      << (status.llvmConfigured ? "true" : "false") << ",\n"
      << "  \"hasMLIR\": " << (status.hasMLIR ? "true" : "false") << ",\n"
      << "  \"mlirConfigured\": "
      << (status.mlirConfigured ? "true" : "false") << ",\n"
      << "  \"mlirNativePipelineAvailable\": "
      << (status.mlirNativePipelineAvailable ? "true" : "false") << ",\n"
      << "  \"tools\": [";
  for (std::size_t i = 0; i < status.tools.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const ToolStatus &tool = status.tools[i];
    out << "\n    {"
        << "\"name\": \"" << escapeJson(tool.name) << "\", "
        << "\"available\": " << (tool.available ? "true" : "false") << ", "
        << "\"evidenceStatus\": \"" << escapeJson(tool.evidenceStatus)
        << "\", "
        << "\"path\": \"" << escapeJson(tool.path) << "\", "
        << "\"detail\": \"" << escapeJson(tool.detail) << "\", "
        << "\"source\": \"" << escapeJson(tool.source) << "\", "
        << "\"resolvedPath\": \"" << escapeJson(tool.resolvedPath) << "\", "
        << "\"probeStatus\": \"" << escapeJson(tool.probeStatus) << "\", "
        << "\"version\": \"" << escapeJson(tool.version) << "\", "
        << "\"versionDetail\": \"" << escapeJson(tool.versionDetail) << "\""
        << "}";
  }
  if (!status.tools.empty()) {
    out << "\n  ";
  }
  out << "]\n}\n";
  return out.str();
}

std::string toolchainStatusToText(const ToolchainStatus &status) {
  std::ostringstream out;
  out << "Host: " << status.hostPlatform << " " << status.hostArch << "\n";
  out << "Default target: " << status.defaultTarget << "\n";
  out << "LLVM: " << (status.llvmConfigured ? "configured" : "not configured")
      << " (" << status.llvmVersion << ")\n";
  out << "MLIR: " << (status.mlirConfigured ? "configured" : "not configured")
      << " for detection/reporting only\n";
  out << "MLIR native pipeline: "
      << (status.mlirNativePipelineAvailable ? "available" : "unavailable")
      << " (requires MLIR configured and CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON)\n";
  out << "Tools:\n";
  for (const ToolStatus &tool : status.tools) {
    out << "  " << (tool.available ? "[ok]   " : "[miss] ") << tool.name;
    if (!tool.evidenceStatus.empty()) {
      out << " evidence=" << tool.evidenceStatus;
    }
    if (!tool.path.empty()) {
      out << " -> " << tool.path;
    }
    if (!tool.source.empty()) {
      out << " [" << tool.source << "]";
    }
    if (!tool.probeStatus.empty()) {
      out << " probe=" << tool.probeStatus;
    }
    if (!tool.version.empty()) {
      out << " version=\"" << tool.version << "\"";
    }
    if (!tool.detail.empty()) {
      out << " (" << tool.detail << ")";
    }
    if (!tool.versionDetail.empty()) {
      out << " (" << tool.versionDetail << ")";
    }
    out << "\n";
  }
  return out.str();
}

} // namespace crossgl
