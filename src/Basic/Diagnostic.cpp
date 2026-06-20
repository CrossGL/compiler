#include "crossgl/Basic/Diagnostic.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <optional>
#include <string>
#include <utility>

namespace crossgl {
namespace {

constexpr std::array<std::string_view, 14> kDiagnosticCodePrefixes = {
    "artifact.", "directx.", "io.",     "lex.",    "metal.",  "opengl.",
    "opt.",      "package.", "parse.",  "project.", "sema.",   "spec.",
    "target.",   "vulkan.",
};

bool isDiagnosticCodeSeparator(char character) {
  return character == '.' || character == '-';
}

bool isDiagnosticCodeTokenCharacter(char character) {
  const auto byte = static_cast<unsigned char>(character);
  return std::islower(byte) || std::isdigit(byte);
}

bool hasWindowsDrivePrefix(std::string_view path) {
  return path.size() >= 2 &&
         std::isalpha(static_cast<unsigned char>(path[0])) && path[1] == ':';
}

bool isAbsoluteDiagnosticPath(std::string_view path) {
  return path.starts_with("/") || path.starts_with("\\") ||
         hasWindowsDrivePrefix(path);
}

std::string slashNormalizedPath(std::string_view path) {
  std::string normalized(path);
  std::replace(normalized.begin(), normalized.end(), '\\', '/');
  return normalized;
}

std::optional<std::string> anchoredDiagnosticPath(std::string_view path) {
  constexpr std::array<std::string_view, 6> anchors = {
      "docs/", "include/", "runtime/", "src/", "tests/", "tools/",
  };
  for (std::string_view anchor : anchors) {
    std::size_t position = path.find(anchor);
    while (position != std::string_view::npos) {
      if (position == 0 || path[position - 1] == '/') {
        return std::string(path.substr(position));
      }
      position = path.find(anchor, position + 1);
    }
  }
  return std::nullopt;
}

std::string basenamePath(std::string_view path) {
  const std::size_t lastSlash = path.find_last_of('/');
  if (lastSlash == std::string_view::npos) {
    return std::string(path);
  }
  if (lastSlash + 1 >= path.size()) {
    return {};
  }
  return std::string(path.substr(lastSlash + 1));
}

std::string deterministicDiagnosticPath(std::string_view path) {
  if (path.empty()) {
    return {};
  }

  std::string normalized = slashNormalizedPath(path);
  if (std::optional<std::string> anchored =
          anchoredDiagnosticPath(normalized)) {
    return *anchored;
  }
  if (!isAbsoluteDiagnosticPath(path)) {
    return normalized;
  }
  return basenamePath(normalized);
}

} // namespace

void DiagnosticEngine::report(Diagnostic diagnostic) {
  diagnostic.location.file =
      deterministicDiagnosticPath(diagnostic.location.file);
  if (diagnostic.originalLocation) {
    diagnostic.originalLocation->file =
        deterministicDiagnosticPath(diagnostic.originalLocation->file);
  }
  diagnostics_.push_back(std::move(diagnostic));
}

void DiagnosticEngine::report(DiagnosticSeverity severity, std::string code,
                              std::string message, SourceLocation location) {
  Diagnostic diagnostic;
  diagnostic.severity = severity;
  diagnostic.code = std::move(code);
  diagnostic.message = std::move(message);
  diagnostic.location = std::move(location);
  report(std::move(diagnostic));
}

void DiagnosticEngine::note(std::string code, std::string message,
                            SourceLocation location) {
  report(DiagnosticSeverity::Note, std::move(code), std::move(message),
         std::move(location));
}

void DiagnosticEngine::warning(std::string code, std::string message,
                               SourceLocation location) {
  report(DiagnosticSeverity::Warning, std::move(code), std::move(message),
         std::move(location));
}

void DiagnosticEngine::error(std::string code, std::string message,
                             SourceLocation location) {
  report(DiagnosticSeverity::Error, std::move(code), std::move(message),
         std::move(location));
}

bool DiagnosticEngine::hasErrors() const {
  return std::any_of(diagnostics_.begin(), diagnostics_.end(),
                     [](const Diagnostic &diagnostic) {
                       return diagnostic.severity == DiagnosticSeverity::Error;
                     });
}

std::string toString(DiagnosticSeverity severity) {
  switch (severity) {
  case DiagnosticSeverity::Note:
    return "note";
  case DiagnosticSeverity::Warning:
    return "warning";
  case DiagnosticSeverity::Error:
    return "error";
  }
  return "unknown";
}

std::span<const std::string_view> diagnosticCodePrefixes() {
  return kDiagnosticCodePrefixes;
}

bool isKnownDiagnosticCodePrefix(std::string_view code) {
  return std::any_of(kDiagnosticCodePrefixes.begin(),
                     kDiagnosticCodePrefixes.end(),
                     [code](std::string_view prefix) {
                       return code.starts_with(prefix);
                     });
}

bool isValidDiagnosticCode(std::string_view code) {
  if (code.empty() || !isKnownDiagnosticCodePrefix(code)) {
    return false;
  }

  bool previousWasSeparator = false;
  for (char character : code) {
    if (isDiagnosticCodeTokenCharacter(character)) {
      previousWasSeparator = false;
      continue;
    }
    if (!isDiagnosticCodeSeparator(character) || previousWasSeparator) {
      return false;
    }
    previousWasSeparator = true;
  }
  return !previousWasSeparator;
}

} // namespace crossgl
