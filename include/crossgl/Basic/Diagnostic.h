#pragma once

#include <cstddef>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace crossgl {

enum class DiagnosticSeverity {
  Note,
  Warning,
  Error,
};

struct SourceLocation {
  std::string file;
  std::size_t line = 1;
  std::size_t column = 1;
  std::size_t offset = 0;
  std::size_t length = 0;
  std::size_t endLine = 1;
  std::size_t endColumn = 1;
  std::size_t endOffset = 0;
};

struct Diagnostic {
  DiagnosticSeverity severity = DiagnosticSeverity::Note;
  std::string code;
  std::string message;
  SourceLocation location;
  std::optional<SourceLocation> originalLocation;
  std::string target;
  std::vector<std::string> missingCapabilities;
};

class DiagnosticEngine {
public:
  void report(Diagnostic diagnostic);
  void report(DiagnosticSeverity severity, std::string code, std::string message,
              SourceLocation location = {});

  void note(std::string code, std::string message,
            SourceLocation location = {});
  void warning(std::string code, std::string message,
               SourceLocation location = {});
  void error(std::string code, std::string message,
             SourceLocation location = {});

  bool hasErrors() const;
  bool empty() const { return diagnostics_.empty(); }
  const std::vector<Diagnostic> &diagnostics() const { return diagnostics_; }

private:
  std::vector<Diagnostic> diagnostics_;
};

std::string toString(DiagnosticSeverity severity);
std::span<const std::string_view> diagnosticCodePrefixes();
bool isKnownDiagnosticCodePrefix(std::string_view code);
bool isValidDiagnosticCode(std::string_view code);

} // namespace crossgl
