#include "crossgl/Backend/Target.h"
#include "crossgl/Backend/Toolchain.h"
#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/Basic/Json.h"
#include "crossgl/Basic/SHA256.h"
#include "crossgl/Driver/Compiler.h"
#include "crossgl/Driver/CompilerPipeline.h"
#include "crossgl/Driver/DebugMetadata.h"
#include "crossgl/Driver/LanguageFeatureReport.h"
#include "crossgl/Driver/PackageInspect.h"
#include "crossgl/Driver/PackageIntegrity.h"
#include "crossgl/Driver/PackageJson.h"
#include "crossgl/Driver/PackagePublication.h"
#include "crossgl/Driver/SourceRemap.h"

#include <charconv>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <fstream>
#include <initializer_list>
#include <iostream>
#include <limits>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

void printUsage() {
  std::cout
      << "CrossGL native compiler\n\n"
      << "Usage:\n"
      << "  cglc doctor [--json] [input.cgl]\n"
      << "  cglc targets\n"
      << "  cglc check <input.cgl> [--opt-level O0|O1|O2] "
         "[--logical-input <path>] [--source-remap <remap.json>] "
         "[--diagnostics-json]\n"
      << "  cglc check --source-manifest <sources.json> "
         "[--opt-level O0|O1|O2] [--diagnostics-json]\n"
      << "  cglc explain-targets <input.cgl> [--logical-input <path>]\n"
      << "  cglc language-feature-report <input.cgl> [--root <repo>]\n"
      << "  cglc dump-ir <input.cgl> --stage "
         "hir|crossgl|pseudo-mlir|backend|backend-source-map|debug|"
         "hir-source-map|hir-pass-trace "
         "[--target auto|metal|vulkan|directx|opengl] "
         "[--opt-level O0|O1|O2] [--logical-input <path>] "
         "[--source-remap <remap.json>]\n"
      << "      --stage mlir is a compatibility alias for pseudo-mlir; the "
         "output is not real MLIR.\n"
      << "      Real MLIR remains reserved for a future "
         "CROSSGL_ENABLE_MLIR_EXPERIMENTAL path.\n"
      << "      [--source-map-stage <stage>] [--source-map-entry <entry>] "
         "[--source-map-function <function>]\n"
      << "      [--source-map-schema-version 7|8] "
         "[--hir-source-map-schema-version 7|8]\n"
      << "      [--source-map-statement-kind <kind>] "
         "[--source-map-expression-kind <kind>]\n"
      << "      [--source-map-operation <operation>] [--source-map-owner-kind "
         "<kind>] [--source-map-owner-name <name>]\n"
      << "      [--source-map-resource-record-kind <kind>] "
         "[--source-map-resource-name <name>] "
         "[--source-map-resource-kind <kind>]\n"
      << "      [--source-map-offset <n>] [--source-map-limit <n>]\n"
      << "      [--source-map-expression-offset <n>] "
         "[--source-map-expression-limit <n>]\n"
      << "      [--source-map-type-offset <n>] [--source-map-type-limit <n>]\n"
      << "      [--source-map-statement-offset <n>] "
         "[--source-map-statement-limit <n>]\n"
      << "      [--source-map-resource-offset <n>] "
         "[--source-map-resource-limit <n>]\n"
      << "      [--source-map-records] [--source-map-record-offset <n>] "
         "[--source-map-record-limit <n>]\n"
      << "  cglc build <input.cgl> --target auto|metal|vulkan|directx|opengl "
         "--output <out.cglb> [--opt-level O0|O1|O2] [--debug-ir] "
         "[--logical-input <path>] [--source-remap <remap.json>] "
         "[--diagnostics-json]\n"
      << "  cglc build --source-manifest <sources.json> "
         "[--target auto|metal|vulkan|directx|opengl] "
         "[--opt-level O0|O1|O2] [--debug-ir] [--diagnostics-json]\n"
      << "  cglc package inspect <out.cglb> --json\n"
      << "  cglc package verify <out.cglb> [--source <input.cgl>] [--json]\n"
      << "  cglc package recover <package-or-sidecar.cglb> --list [--json]\n"
      << "  cglc package recover <package-or-sidecar.cglb> --discard-stale "
         "[--dry-run|--apply] [--keep-last <n>] [--older-than <duration>] "
         "[--policy <policy.json>] [--json]\n"
      << "  cglc package recover <sidecar.cglb> --promote|--discard "
         "[--replace] [--source <input.cgl>] [--json]\n"
      << "  cglc package release --promotion-summary <summary.json> "
         "--manifest-output <manifest.json> [--bundle-output <bundle.json>] "
         "[--json]\n"
      << "  cglc package release --verify-bundle <bundle.json> [--json]\n"
      << "  cglc package release --plan-publish <bundle.json> --plan-output "
         "<plan.json> [--json]\n"
      << "  cglc package release --stage-publish <plan.json> --stage-output "
         "<dir> [--json]\n"
      << "  cglc package release --report-artifact-inventory "
         "[--report-bundle <bundle.json>] [--report-publish-plan "
         "<plan.json>] [--report-publish-stage <stage-report.json>] "
         "[--json]\n"
      << "  cglc package release --publish-stage <stage-report.json> "
         "--publish-target <local-filesystem|gcs> [--target-output <dir>] "
         "[--target-descriptor <target.json>] [--receipt-output "
         "<receipt.json>] [--upload-manifest-output <manifest.json>] "
         "[--dry-run] [--json]\n"
      << "  cglc package release --upload-manifest <manifest.json> --dry-run "
         "[--upload-report-output <report.json>] [--json]\n"
      << "  cglc package release --upload-manifest <manifest.json> "
         "--mock-upload [--upload-report-output <report.json>] "
         "[--upload-receipt-output <receipt.json>] [--json]\n"
      << "  cglc package release --upload-manifest <manifest.json> "
         "--gcs-upload [--gcs-upload-overwrite] [--upload-report-output "
         "<report.json>] [--upload-receipt-output <receipt.json>] [--json]\n"
      << "  cglc package maintain <package-or-sidecar.cglb> "
         "[--dry-run|--apply] [--keep-last <n>] [--older-than <duration>] "
         "[--policy <policy.json>] [--json]\n"
      << "  cglc package maintain --scan <dir> [--dry-run|--apply] "
         "[--keep-last <n>] [--older-than <duration>] [--policy <policy.json>] "
         "[--json]\n"
      << "  cglc package maintain --scan <dir> --export-package-set <set.json> "
         "[--json]\n"
      << "  cglc package maintain --scan <dir> --verify-package-set <set.json> "
         "[--json]\n"
      << "  cglc package maintain --export-package-set-verification-batch "
         "<batch.json> --verification <root> <set.json> [--verification <root> "
         "<set.json> ...] [--json]\n"
      << "  cglc package maintain --verify-package-set-batch <batch.json> "
         "[--summary-output <summary.json>] [--json]\n"
      << "  cglc package maintain --package-set <set.json> [--dry-run|--apply] "
         "[--keep-last <n>] [--older-than <duration>] [--policy <policy.json>] "
         "[--json]\n";
}

std::string argValue(const std::vector<std::string> &args,
                     std::string_view name, std::string fallback = "") {
  for (std::size_t i = 0; i + 1 < args.size(); ++i) {
    if (args[i] == name) {
      return args[i + 1];
    }
  }
  return fallback;
}

bool hasArg(const std::vector<std::string> &args, std::string_view name) {
  for (const std::string &arg : args) {
    if (arg == name) {
      return true;
    }
  }
  return false;
}

bool isDeferredSourceBatchManifestFlag(std::string_view name) {
  return name == "--source-manifest" || name == "--batch-manifest" ||
         name == "--source-batch" || name == "--batch" || name == "--manifest";
}

bool isSourceInputCommand(std::string_view command) {
  return command == "doctor" || command == "check" ||
         command == "explain-targets" ||
         command == "language-feature-report" || command == "dump-ir" ||
         command == "build";
}

struct SourceBatchManifestFlag {
  bool present = false;
  bool valid = true;
  std::string flag;
  std::filesystem::path path;
  std::size_t flagIndex = 0;
  std::size_t valueIndex = 0;
};

SourceBatchManifestFlag
parseSourceBatchManifestFlag(const std::vector<std::string> &args) {
  SourceBatchManifestFlag parsed;
  for (std::size_t index = 0; index < args.size(); ++index) {
    if (!isDeferredSourceBatchManifestFlag(args[index])) {
      continue;
    }
    if (parsed.present) {
      parsed.valid = false;
      parsed.flag = args[index];
      std::cerr << "error: source manifest mode accepts exactly one batch "
                   "manifest flag\n";
      return parsed;
    }
    parsed.present = true;
    parsed.flag = args[index];
    parsed.flagIndex = index;
    if (index + 1 >= args.size() || args[index + 1].empty() ||
        args[index + 1][0] == '-') {
      parsed.valid = false;
      std::cerr << "error: " << parsed.flag << " requires a path\n";
      return parsed;
    }
    parsed.valueIndex = index + 1;
    parsed.path = args[index + 1];
  }
  return parsed;
}

int rejectUnsupportedSourceBatchManifestCommand(std::string_view command,
                                                std::string_view flag) {
  std::cerr << "error: " << flag << " source manifest mode is supported for "
            << "check and build; " << command
            << " must still be invoked per source in this compiler version\n";
  return 2;
}

crossgl::SourceLocation cliSourceLocation(const std::filesystem::path &path) {
  crossgl::SourceLocation location;
  location.file = path.lexically_normal().generic_string();
  return location;
}

std::optional<crossgl::SourceInput>
readLogicalSourceInput(const std::filesystem::path &physicalPath,
                       const std::filesystem::path &logicalPath,
                       crossgl::DiagnosticEngine &diagnostics) {
  std::ifstream input(physicalPath, std::ios::binary);
  if (!input) {
    diagnostics.error("io.read-failed",
                      "failed to read '" + physicalPath.string() + "'",
                      cliSourceLocation(physicalPath));
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    diagnostics.error("io.read-failed",
                      "failed to read '" + physicalPath.string() + "'",
                      cliSourceLocation(physicalPath));
    return std::nullopt;
  }

  return crossgl::SourceInput{logicalPath, buffer.str()};
}

void setOptionalArg(std::optional<std::string> &slot,
                    const std::vector<std::string> &args,
                    std::string_view name) {
  const std::string value = argValue(args, name);
  if (!value.empty()) {
    slot = value;
  }
}

std::optional<std::size_t> optionalSizeArg(const std::vector<std::string> &args,
                                           std::string_view name) {
  const std::string value = argValue(args, name);
  if (value.empty()) {
    return std::nullopt;
  }

  std::size_t parsed = 0;
  const char *begin = value.data();
  const char *end = value.data() + value.size();
  const std::from_chars_result result = std::from_chars(begin, end, parsed);
  if (result.ec != std::errc{} || result.ptr != end) {
    throw std::runtime_error("expected non-negative integer for " +
                             std::string(name));
  }
  return parsed;
}

crossgl::OptimizationLevel
optimizationLevelArg(const std::vector<std::string> &args) {
  if (!hasArg(args, "--opt-level")) {
    return crossgl::OptimizationLevel::O1;
  }

  const std::string value = argValue(args, "--opt-level");
  if (value.empty()) {
    throw std::runtime_error("--opt-level requires O0, O1, or O2");
  }

  if (std::optional<crossgl::OptimizationLevel> level =
          crossgl::parseOptimizationLevel(value)) {
    return *level;
  }

  throw std::runtime_error("unknown optimization level '" + value +
                           "'; expected O0, O1, or O2");
}

void setSizeArg(std::size_t &slot, const std::vector<std::string> &args,
                std::string_view name) {
  if (std::optional<std::size_t> value = optionalSizeArg(args, name)) {
    slot = *value;
  }
}

void setOptionalSizeArg(std::optional<std::size_t> &slot,
                        const std::vector<std::string> &args,
                        std::string_view name) {
  if (std::optional<std::size_t> value = optionalSizeArg(args, name)) {
    slot = *value;
  }
}

std::optional<int>
optionalHIRSourceMapSchemaVersionArg(const std::vector<std::string> &args,
                                     std::string_view name) {
  if (!hasArg(args, name)) {
    return std::nullopt;
  }
  const std::string value = argValue(args, name);
  if (value.empty()) {
    throw std::runtime_error(std::string(name) + " requires 7 or 8");
  }

  int parsed = 0;
  const char *begin = value.data();
  const char *end = value.data() + value.size();
  const std::from_chars_result result = std::from_chars(begin, end, parsed);
  if (result.ec != std::errc{} || result.ptr != end ||
      (parsed != 7 && parsed != 8)) {
    throw std::runtime_error("expected 7 or 8 for " + std::string(name));
  }
  return parsed;
}

std::optional<std::uint64_t>
optionalDurationSecondsArg(const std::vector<std::string> &args,
                           std::string_view name) {
  const std::string value = argValue(args, name);
  if (value.empty()) {
    return std::nullopt;
  }

  std::string_view text(value);
  std::uint64_t multiplier = 1;
  const char suffix = text.back();
  if (suffix < '0' || suffix > '9') {
    switch (suffix) {
    case 's':
      multiplier = 1;
      break;
    case 'm':
      multiplier = 60;
      break;
    case 'h':
      multiplier = 60 * 60;
      break;
    case 'd':
      multiplier = 24 * 60 * 60;
      break;
    default:
      throw std::runtime_error("expected duration for " + std::string(name) +
                               " (for example 30s, 15m, 2h, or 7d)");
    }
    text.remove_suffix(1);
  }
  if (text.empty()) {
    throw std::runtime_error("expected duration for " + std::string(name));
  }

  std::uint64_t parsed = 0;
  const char *begin = text.data();
  const char *end = text.data() + text.size();
  const std::from_chars_result result = std::from_chars(begin, end, parsed);
  if (result.ec != std::errc{} || result.ptr != end ||
      parsed > std::numeric_limits<std::int64_t>::max() / multiplier) {
    throw std::runtime_error("expected duration for " + std::string(name) +
                             " (for example 30s, 15m, 2h, or 7d)");
  }
  return parsed * multiplier;
}

std::string firstNonFlagArg(const std::vector<std::string> &args) {
  for (std::size_t index = 1; index < args.size(); ++index) {
    if (!args[index].empty() && args[index][0] == '-') {
      continue;
    }
    return args[index];
  }
  return "";
}

std::string trimTrailingNewlines(std::string text) {
  while (!text.empty() && (text.back() == '\n' || text.back() == '\r')) {
    text.pop_back();
  }
  return text;
}

std::string processCaptureFailureDetail(
    const crossgl::ProcessCaptureResult &result) {
  if (!result.error.empty()) {
    return result.error;
  }
  std::string stderrText = trimTrailingNewlines(result.stderrText);
  if (!stderrText.empty()) {
    return stderrText;
  }
  std::string stdoutText = trimTrailingNewlines(result.stdoutText);
  if (!stdoutText.empty()) {
    return stdoutText;
  }
  return "";
}

void printIndentedJsonValue(std::string text, std::string_view indent) {
  text = trimTrailingNewlines(std::move(text));
  for (std::size_t index = 0; index < text.size(); ++index) {
    std::cout << text[index];
    if (text[index] == '\n' && index + 1 < text.size()) {
      std::cout << indent;
    }
  }
}

void printDiagnostics(const std::vector<crossgl::Diagnostic> &diagnostics) {
  for (const crossgl::Diagnostic &diagnostic : diagnostics) {
    const crossgl::SourceLocation &displayLocation =
        diagnostic.originalLocation.value_or(diagnostic.location);
    std::cerr << displayLocation.file;
    if (!displayLocation.file.empty()) {
      std::cerr << ":" << displayLocation.line << ":"
                << displayLocation.column;
    }
    std::cerr << ": " << crossgl::toString(diagnostic.severity) << " "
              << diagnostic.code << ": " << diagnostic.message << "\n";
  }
}

struct SourceBatchDefaults {
  crossgl::TargetKind target = crossgl::TargetKind::Auto;
  crossgl::OptimizationLevel optimizationLevel = crossgl::OptimizationLevel::O1;
  bool debugIR = false;
};

struct SourceBatchEntry {
  std::string id;
  std::filesystem::path path;
  std::optional<std::filesystem::path> logicalInput;
  std::optional<std::filesystem::path> output;
  std::optional<crossgl::TargetKind> target;
  std::optional<crossgl::OptimizationLevel> optimizationLevel;
  std::optional<bool> debugIR;
  std::optional<std::filesystem::path> sourceRemap;
};

struct SourceBatchManifest {
  std::filesystem::path path;
  std::filesystem::path root;
  SourceBatchDefaults defaults;
  std::vector<SourceBatchEntry> sources;
};

struct SourceBatchEntryResult {
  std::string id;
  std::filesystem::path inputPath;
  std::optional<std::filesystem::path> logicalInputPath;
  std::optional<std::filesystem::path> sourceRemapPath;
  std::optional<std::filesystem::path> outputPath;
  std::optional<std::filesystem::path> artifactPath;
  crossgl::TargetKind target = crossgl::TargetKind::Auto;
  bool success = false;
};

std::optional<std::string>
readTextDocument(const std::filesystem::path &path,
                 crossgl::DiagnosticEngine &diagnostics) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    diagnostics.error("io.read-failed",
                      "failed to read '" + path.string() + "'",
                      cliSourceLocation(path));
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    diagnostics.error("io.read-failed",
                      "failed to read '" + path.string() + "'",
                      cliSourceLocation(path));
    return std::nullopt;
  }
  return buffer.str();
}

void sourceBatchManifestError(crossgl::DiagnosticEngine &diagnostics,
                              const std::filesystem::path &path,
                              std::string message) {
  diagnostics.error("project.source-batch.invalid-manifest",
                    std::move(message), cliSourceLocation(path));
}

struct SourceBatchJsonMember {
  std::string key;
};

std::optional<std::vector<SourceBatchJsonMember>>
collectSourceBatchJsonObjectMembers(std::string_view object) {
  std::vector<SourceBatchJsonMember> members;
  std::size_t position = 0;
  crossgl::skipWhitespace(object, position);
  if (position >= object.size() || object[position] != '{') {
    return std::nullopt;
  }
  ++position;
  crossgl::skipWhitespace(object, position);
  if (position < object.size() && object[position] == '}') {
    ++position;
    crossgl::skipWhitespace(object, position);
    return position == object.size()
               ? std::optional<std::vector<SourceBatchJsonMember>>(
                     std::move(members))
               : std::nullopt;
  }
  while (position < object.size()) {
    std::string key;
    if (!crossgl::parseJsonString(object, position, key)) {
      return std::nullopt;
    }
    crossgl::skipWhitespace(object, position);
    if (position >= object.size() || object[position] != ':') {
      return std::nullopt;
    }
    ++position;
    crossgl::skipWhitespace(object, position);
    if (!crossgl::skipJsonValue(object, position)) {
      return std::nullopt;
    }
    members.push_back({std::move(key)});
    crossgl::skipWhitespace(object, position);
    if (position < object.size() && object[position] == ',') {
      ++position;
      crossgl::skipWhitespace(object, position);
      continue;
    }
    if (position < object.size() && object[position] == '}') {
      ++position;
      crossgl::skipWhitespace(object, position);
      return position == object.size()
                 ? std::optional<std::vector<SourceBatchJsonMember>>(
                       std::move(members))
                 : std::nullopt;
    }
    return std::nullopt;
  }
  return std::nullopt;
}

bool sourceBatchMemberAllowed(
    std::string_view key, std::initializer_list<std::string_view> allowed) {
  for (std::string_view candidate : allowed) {
    if (key == candidate) {
      return true;
    }
  }
  return false;
}

bool validateSourceBatchAllowedMembers(
    std::string_view object, std::initializer_list<std::string_view> allowed,
    std::string_view context, const std::filesystem::path &manifestPath,
    crossgl::DiagnosticEngine &diagnostics) {
  std::optional<std::vector<SourceBatchJsonMember>> members =
      collectSourceBatchJsonObjectMembers(object);
  if (!members) {
    sourceBatchManifestError(diagnostics, manifestPath,
                             std::string(context) +
                                 " must be a valid JSON object");
    return false;
  }
  for (const SourceBatchJsonMember &member : *members) {
    if (!sourceBatchMemberAllowed(member.key, allowed)) {
      sourceBatchManifestError(diagnostics, manifestPath,
                               std::string(context) +
                                   " has unexpected property '" + member.key +
                                   "'");
      return false;
    }
  }
  return true;
}

bool parseSourceBatchStringMemberValue(std::string_view valueText,
                                       std::string &value) {
  std::size_t position = 0;
  if (!crossgl::parseJsonString(valueText, position, value)) {
    return false;
  }
  crossgl::skipWhitespace(valueText, position);
  return position == valueText.size();
}

bool parseOptionalSourceBatchStringMember(
    std::string_view object, std::string_view key, std::string_view context,
    const std::filesystem::path &manifestPath,
    crossgl::DiagnosticEngine &diagnostics, std::optional<std::string> &value,
    bool requireNonEmpty = true) {
  const std::optional<std::string_view> valueText =
      crossgl::findObjectMemberValue(object, key);
  if (!valueText) {
    return true;
  }
  std::string parsed;
  if (!parseSourceBatchStringMemberValue(*valueText, parsed)) {
    sourceBatchManifestError(diagnostics, manifestPath,
                             std::string(context) + "." + std::string(key) +
                                 " must be a string");
    return false;
  }
  if (requireNonEmpty && parsed.empty()) {
    sourceBatchManifestError(diagnostics, manifestPath,
                             std::string(context) + "." + std::string(key) +
                                 " must be a non-empty string");
    return false;
  }
  value = std::move(parsed);
  return true;
}

bool isAsciiLetter(char value) {
  return (value >= 'A' && value <= 'Z') || (value >= 'a' && value <= 'z');
}

bool isSourceBatchStableRelativePath(std::string_view path) {
  if (path.empty() || path.front() == '/') {
    return false;
  }
  if (path.size() >= 2 && isAsciiLetter(path[0]) && path[1] == ':') {
    return false;
  }
  if (path.find('\\') != std::string_view::npos) {
    return false;
  }

  std::size_t segmentBegin = 0;
  for (std::size_t index = 0; index <= path.size(); ++index) {
    if (index < path.size() && path[index] != '/') {
      continue;
    }
    if (index == segmentBegin) {
      return false;
    }
    std::string_view segment =
        path.substr(segmentBegin, index - segmentBegin);
    if (segment == "." || segment == "..") {
      return false;
    }
    segmentBegin = index + 1;
  }
  return true;
}

bool parseOptionalSourceBatchStableRelativePathMember(
    std::string_view object, std::string_view key, std::string_view context,
    const std::filesystem::path &manifestPath,
    crossgl::DiagnosticEngine &diagnostics, std::optional<std::string> &value) {
  if (!parseOptionalSourceBatchStringMember(object, key, context, manifestPath,
                                            diagnostics, value)) {
    return false;
  }
  if (!value || isSourceBatchStableRelativePath(*value)) {
    return true;
  }
  sourceBatchManifestError(
      diagnostics, manifestPath,
      std::string(context) + "." + std::string(key) +
          " must be a stable relative path without drive prefixes, "
          "backslashes, empty segments, or . or .. segments");
  return false;
}

bool parseOptionalSourceBatchBoolMember(
    std::string_view object, std::string_view key, std::string_view context,
    const std::filesystem::path &manifestPath,
    crossgl::DiagnosticEngine &diagnostics, std::optional<bool> &value) {
  const std::optional<std::string_view> valueText =
      crossgl::findObjectMemberValue(object, key);
  if (!valueText) {
    return true;
  }
  const std::optional<bool> parsed = crossgl::parseBool(*valueText);
  if (!parsed) {
    sourceBatchManifestError(diagnostics, manifestPath,
                             std::string(context) + "." + std::string(key) +
                                 " must be a boolean");
    return false;
  }
  value = *parsed;
  return true;
}

bool parseOptionalSourceBatchUnsignedMember(
    std::string_view object, std::string_view key, std::string_view context,
    const std::filesystem::path &manifestPath,
    crossgl::DiagnosticEngine &diagnostics,
    std::optional<std::uintmax_t> &value) {
  const std::optional<std::string_view> valueText =
      crossgl::findObjectMemberValue(object, key);
  if (!valueText) {
    return true;
  }
  const std::optional<std::uintmax_t> parsed =
      crossgl::objectUnsignedMember(object, key);
  if (!parsed) {
    sourceBatchManifestError(diagnostics, manifestPath,
                             std::string(context) + "." + std::string(key) +
                                 " must be a non-negative integer");
    return false;
  }
  value = *parsed;
  return true;
}

std::filesystem::path resolveManifestPath(const std::filesystem::path &base,
                                          const std::filesystem::path &path) {
  if (path.is_absolute()) {
    return path.lexically_normal();
  }
  return (base / path).lexically_normal();
}

std::optional<crossgl::TargetKind>
parseManifestTarget(std::string_view value,
                    const std::filesystem::path &manifestPath,
                    crossgl::DiagnosticEngine &diagnostics) {
  try {
    return crossgl::targetFromString(value);
  } catch (const std::exception &error) {
    sourceBatchManifestError(diagnostics, manifestPath, error.what());
    return std::nullopt;
  }
}

std::optional<crossgl::OptimizationLevel>
parseManifestOptimizationLevel(std::string_view value,
                               const std::filesystem::path &manifestPath,
                               crossgl::DiagnosticEngine &diagnostics) {
  if (std::optional<crossgl::OptimizationLevel> level =
          crossgl::parseOptimizationLevel(value)) {
    return *level;
  }
  sourceBatchManifestError(
      diagnostics, manifestPath,
      "unknown optimization level '" + std::string(value) +
          "'; expected O0, O1, or O2");
  return std::nullopt;
}

bool parseSourceBatchDefaults(std::string_view defaultsText,
                              SourceBatchDefaults &defaults,
                              const std::filesystem::path &manifestPath,
                              crossgl::DiagnosticEngine &diagnostics) {
  if (!crossgl::isJsonObjectDocument(defaultsText)) {
    sourceBatchManifestError(diagnostics, manifestPath,
                             "source batch manifest defaults must be an object");
    return false;
  }
  if (!validateSourceBatchAllowedMembers(
          defaultsText, {"target", "optLevel", "debugIR"},
          "source batch manifest defaults", manifestPath, diagnostics)) {
    return false;
  }
  std::optional<std::string> target;
  if (!parseOptionalSourceBatchStringMember(
          defaultsText, "target", "source batch manifest defaults",
          manifestPath, diagnostics, target)) {
    return false;
  }
  if (target) {
    if (std::optional<crossgl::TargetKind> parsed =
            parseManifestTarget(*target, manifestPath, diagnostics)) {
      defaults.target = *parsed;
    } else {
      return false;
    }
  }
  std::optional<std::string> optLevel;
  if (!parseOptionalSourceBatchStringMember(
          defaultsText, "optLevel", "source batch manifest defaults",
          manifestPath, diagnostics, optLevel)) {
    return false;
  }
  if (optLevel) {
    if (std::optional<crossgl::OptimizationLevel> parsed =
            parseManifestOptimizationLevel(*optLevel, manifestPath,
                                           diagnostics)) {
      defaults.optimizationLevel = *parsed;
    } else {
      return false;
    }
  }
  std::optional<bool> debugIR;
  if (!parseOptionalSourceBatchBoolMember(
          defaultsText, "debugIR", "source batch manifest defaults",
          manifestPath, diagnostics, debugIR)) {
    return false;
  }
  if (debugIR) {
    defaults.debugIR = *debugIR;
  }
  return true;
}

std::optional<SourceBatchEntry>
parseSourceBatchEntryObject(std::string_view entryText,
                            std::size_t sourceIndex,
                            const std::filesystem::path &root,
                            const std::filesystem::path &manifestPath,
                            crossgl::DiagnosticEngine &diagnostics) {
  if (!crossgl::isJsonObjectDocument(entryText)) {
    sourceBatchManifestError(
        diagnostics, manifestPath,
        "source batch manifest sources[" + std::to_string(sourceIndex) +
            "] must be an object or string");
    return std::nullopt;
  }

  const std::string context =
      "source batch manifest sources[" + std::to_string(sourceIndex) + "]";
  if (!validateSourceBatchAllowedMembers(
          entryText,
          {"id", "path", "logicalInput", "logicalPath", "output",
           "sourceRemap", "target", "optLevel", "debugIR"},
          context, manifestPath, diagnostics)) {
    return std::nullopt;
  }

  std::optional<std::string> path;
  if (!parseOptionalSourceBatchStringMember(entryText, "path", context,
                                            manifestPath, diagnostics, path)) {
    return std::nullopt;
  }
  if (!path || path->empty()) {
    sourceBatchManifestError(
        diagnostics, manifestPath,
        "source batch manifest sources[" + std::to_string(sourceIndex) +
            "] requires a non-empty path");
    return std::nullopt;
  }

  SourceBatchEntry entry;
  std::optional<std::string> id;
  if (!parseOptionalSourceBatchStringMember(entryText, "id", context,
                                            manifestPath, diagnostics, id)) {
    return std::nullopt;
  }
  entry.id = id.value_or("source-" + std::to_string(sourceIndex));
  entry.path = resolveManifestPath(root, *path);
  std::optional<std::string> logicalInput;
  if (!parseOptionalSourceBatchStableRelativePathMember(
          entryText, "logicalInput", context, manifestPath, diagnostics,
          logicalInput)) {
    return std::nullopt;
  }
  std::optional<std::string> logicalPath;
  if (!parseOptionalSourceBatchStableRelativePathMember(
          entryText, "logicalPath", context, manifestPath, diagnostics,
          logicalPath)) {
    return std::nullopt;
  }
  if (logicalInput) {
    entry.logicalInput = std::filesystem::path(*logicalInput);
  } else if (logicalPath) {
    entry.logicalInput = std::filesystem::path(*logicalPath);
  }
  std::optional<std::string> output;
  if (!parseOptionalSourceBatchStringMember(entryText, "output", context,
                                            manifestPath, diagnostics,
                                            output)) {
    return std::nullopt;
  }
  if (output) {
    entry.output = resolveManifestPath(root, *output);
  }
  std::optional<std::string> sourceRemap;
  if (!parseOptionalSourceBatchStringMember(entryText, "sourceRemap", context,
                                            manifestPath, diagnostics,
                                            sourceRemap)) {
    return std::nullopt;
  }
  if (sourceRemap) {
    entry.sourceRemap = resolveManifestPath(root, *sourceRemap);
  }
  std::optional<std::string> target;
  if (!parseOptionalSourceBatchStringMember(entryText, "target", context,
                                            manifestPath, diagnostics,
                                            target)) {
    return std::nullopt;
  }
  if (target) {
    std::optional<crossgl::TargetKind> parsed =
        parseManifestTarget(*target, manifestPath, diagnostics);
    if (!parsed) {
      return std::nullopt;
    }
    entry.target = *parsed;
  }
  std::optional<std::string> optLevel;
  if (!parseOptionalSourceBatchStringMember(entryText, "optLevel", context,
                                            manifestPath, diagnostics,
                                            optLevel)) {
    return std::nullopt;
  }
  if (optLevel) {
    std::optional<crossgl::OptimizationLevel> parsed =
        parseManifestOptimizationLevel(*optLevel, manifestPath, diagnostics);
    if (!parsed) {
      return std::nullopt;
    }
    entry.optimizationLevel = *parsed;
  }
  std::optional<bool> debugIR;
  if (!parseOptionalSourceBatchBoolMember(entryText, "debugIR", context,
                                          manifestPath, diagnostics, debugIR)) {
    return std::nullopt;
  }
  if (debugIR) {
    entry.debugIR = *debugIR;
  }
  return entry;
}

bool parseSourceBatchSources(std::string_view sourcesText,
                             SourceBatchManifest &manifest,
                             crossgl::DiagnosticEngine &diagnostics) {
  std::size_t position = 0;
  crossgl::skipWhitespace(sourcesText, position);
  if (position >= sourcesText.size() || sourcesText[position] != '[') {
    sourceBatchManifestError(diagnostics, manifest.path,
                             "source batch manifest sources must be an array");
    return false;
  }
  ++position;
  crossgl::skipWhitespace(sourcesText, position);
  if (position < sourcesText.size() && sourcesText[position] == ']') {
    sourceBatchManifestError(
        diagnostics, manifest.path,
        "source batch manifest sources array must contain at least one source");
    return false;
  }

  std::size_t sourceIndex = 0;
  while (position < sourcesText.size()) {
    crossgl::skipWhitespace(sourcesText, position);
    const std::size_t valueBegin = position;
    if (position < sourcesText.size() && sourcesText[position] == '"') {
      std::string path;
      if (!crossgl::parseJsonString(sourcesText, position, path) ||
          path.empty()) {
        sourceBatchManifestError(
            diagnostics, manifest.path,
            "source batch manifest sources[" + std::to_string(sourceIndex) +
                "] must be a non-empty string path");
        return false;
      }
      SourceBatchEntry entry;
      entry.id = "source-" + std::to_string(sourceIndex);
      entry.path = resolveManifestPath(manifest.root, path);
      manifest.sources.push_back(std::move(entry));
    } else {
      if (!crossgl::skipJsonValue(sourcesText, position)) {
        sourceBatchManifestError(
            diagnostics, manifest.path,
            "source batch manifest sources[" + std::to_string(sourceIndex) +
                "] is not valid JSON");
        return false;
      }
      std::string_view entryText =
          sourcesText.substr(valueBegin, position - valueBegin);
      std::optional<SourceBatchEntry> entry = parseSourceBatchEntryObject(
          entryText, sourceIndex, manifest.root, manifest.path, diagnostics);
      if (!entry) {
        return false;
      }
      manifest.sources.push_back(std::move(*entry));
    }

    ++sourceIndex;
    crossgl::skipWhitespace(sourcesText, position);
    if (position < sourcesText.size() && sourcesText[position] == ',') {
      ++position;
      continue;
    }
    if (position < sourcesText.size() && sourcesText[position] == ']') {
      ++position;
      crossgl::skipWhitespace(sourcesText, position);
      if (position == sourcesText.size()) {
        return true;
      }
    }
    sourceBatchManifestError(diagnostics, manifest.path,
                             "source batch manifest sources array is malformed");
    return false;
  }

  sourceBatchManifestError(diagnostics, manifest.path,
                           "source batch manifest sources array is malformed");
  return false;
}

template <typename Callback>
bool forEachSourceBatchJsonArrayElement(std::string_view arrayText,
                                        Callback callback) {
  std::size_t position = 0;
  crossgl::skipWhitespace(arrayText, position);
  if (position >= arrayText.size() || arrayText[position] != '[') {
    return false;
  }
  ++position;
  crossgl::skipWhitespace(arrayText, position);
  if (position < arrayText.size() && arrayText[position] == ']') {
    ++position;
    crossgl::skipWhitespace(arrayText, position);
    return position == arrayText.size();
  }

  std::size_t index = 0;
  while (position < arrayText.size()) {
    crossgl::skipWhitespace(arrayText, position);
    const std::size_t valueBegin = position;
    if (!crossgl::skipJsonValue(arrayText, position)) {
      return false;
    }
    if (!callback(index, arrayText.substr(valueBegin, position - valueBegin))) {
      return false;
    }
    ++index;
    crossgl::skipWhitespace(arrayText, position);
    if (position < arrayText.size() && arrayText[position] == ',') {
      ++position;
      continue;
    }
    if (position < arrayText.size() && arrayText[position] == ']') {
      ++position;
      crossgl::skipWhitespace(arrayText, position);
      return position == arrayText.size();
    }
    return false;
  }
  return false;
}

bool sourceBatchIdAlreadyUsed(const SourceBatchManifest &manifest,
                              std::string_view id) {
  for (const SourceBatchEntry &entry : manifest.sources) {
    if (entry.id == id) {
      return true;
    }
  }
  return false;
}

std::string uniqueCrossTLProjectReportEntryId(const SourceBatchManifest &manifest,
                                              std::optional<std::string> source,
                                              std::size_t artifactIndex) {
  if (source && !source->empty() &&
      !sourceBatchIdAlreadyUsed(manifest, *source)) {
    return *source;
  }

  std::string candidate = "artifact-" + std::to_string(artifactIndex);
  if (!sourceBatchIdAlreadyUsed(manifest, candidate)) {
    return candidate;
  }
  std::size_t suffix = 1;
  do {
    candidate = "artifact-" + std::to_string(artifactIndex) + "-" +
                std::to_string(suffix++);
  } while (sourceBatchIdAlreadyUsed(manifest, candidate));
  return candidate;
}

bool isLowercaseSha256Digest(std::string_view value) {
  if (value.size() != 64) {
    return false;
  }
  for (const char c : value) {
    if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) {
      return false;
    }
  }
  return true;
}

bool parseCrossTLProjectReportSourceRemapHash(
    std::string_view sourceRemap, const std::string &context,
    const std::filesystem::path &manifestPath,
    crossgl::DiagnosticEngine &diagnostics, std::string &digest) {
  const std::optional<std::string_view> hash =
      crossgl::findObjectMemberValue(sourceRemap, "hash");
  const std::string hashContext = context + ".hash";
  const std::string hashError =
      hashContext +
      " must contain sha256 algorithm and 64 lowercase hexadecimal value";
  if (!hash || !crossgl::isJsonObjectDocument(*hash)) {
    sourceBatchManifestError(diagnostics, manifestPath, hashError);
    return false;
  }

  std::optional<std::string> algorithm;
  if (!parseOptionalSourceBatchStringMember(*hash, "algorithm", hashContext,
                                            manifestPath, diagnostics,
                                            algorithm)) {
    return false;
  }
  std::optional<std::string> value;
  if (!parseOptionalSourceBatchStringMember(*hash, "value", hashContext,
                                            manifestPath, diagnostics, value)) {
    return false;
  }
  if (!algorithm || *algorithm != "sha256" || !value ||
      !isLowercaseSha256Digest(*value)) {
    sourceBatchManifestError(diagnostics, manifestPath, hashError);
    return false;
  }

  digest = *value;
  return true;
}

bool validateCrossTLProjectReportSourceRemapSidecarIntegrity(
    const std::filesystem::path &sidecarPath, std::uintmax_t expectedSizeBytes,
    std::string_view expectedSha256, const std::string &context,
    const std::filesystem::path &manifestPath,
    crossgl::DiagnosticEngine &diagnostics) {
  std::optional<std::string> sidecarText = readTextDocument(sidecarPath, diagnostics);
  if (!sidecarText) {
    return false;
  }

  if (sidecarText->size() != expectedSizeBytes) {
    sourceBatchManifestError(
        diagnostics, manifestPath,
        context + ".sizeBytes does not match referenced sidecar '" +
            sidecarPath.generic_string() + "'");
    return false;
  }
  const std::string actualSha256 = crossgl::sha256(*sidecarText);
  if (actualSha256 != expectedSha256) {
    sourceBatchManifestError(
        diagnostics, manifestPath,
        context + ".hash.value does not match referenced sidecar '" +
            sidecarPath.generic_string() + "'");
    return false;
  }
  return true;
}

bool parseCrossTLProjectReportArtifact(
    std::string_view artifactText, std::size_t artifactIndex,
    const std::filesystem::path &projectRoot, SourceBatchManifest &manifest,
    crossgl::DiagnosticEngine &diagnostics) {
  const std::string context =
      "CrossTL project report artifacts[" + std::to_string(artifactIndex) + "]";
  if (!crossgl::isJsonObjectDocument(artifactText)) {
    sourceBatchManifestError(diagnostics, manifest.path,
                             context + " must be a JSON object");
    return false;
  }

  std::optional<std::string> status;
  if (!parseOptionalSourceBatchStringMember(artifactText, "status", context,
                                            manifest.path, diagnostics,
                                            status)) {
    return false;
  }
  if (!status || *status != "translated") {
    return true;
  }

  std::optional<std::string> target;
  if (!parseOptionalSourceBatchStringMember(artifactText, "target", context,
                                            manifest.path, diagnostics,
                                            target)) {
    return false;
  }
  if (!target || *target != "cgl") {
    return true;
  }

  std::optional<std::string> path;
  if (!parseOptionalSourceBatchStableRelativePathMember(
          artifactText, "path", context, manifest.path, diagnostics, path)) {
    return false;
  }
  if (!path) {
    sourceBatchManifestError(diagnostics, manifest.path,
                             context + ".path must be a stable relative path");
    return false;
  }

  std::optional<std::string> source;
  if (!parseOptionalSourceBatchStringMember(artifactText, "source", context,
                                            manifest.path, diagnostics, source,
                                            /*requireNonEmpty=*/false)) {
    return false;
  }

  std::optional<std::string> logicalInput = path;
  std::optional<std::string> sourceRemapPath;
  const std::optional<std::string_view> sourceRemap =
      crossgl::findObjectMemberValue(artifactText, "sourceRemap");
  if (!sourceRemap) {
    sourceBatchManifestError(
        diagnostics, manifest.path,
        context +
            ".sourceRemap expected translated cgl artifact to record metadata");
    return false;
  }
  if (!crossgl::isJsonObjectDocument(*sourceRemap)) {
    sourceBatchManifestError(diagnostics, manifest.path,
                             context + ".sourceRemap must be a JSON object");
    return false;
  }

  std::optional<std::string> sourceRemapTarget;
  if (!parseOptionalSourceBatchStringMember(
          *sourceRemap, "target", context + ".sourceRemap", manifest.path,
          diagnostics, sourceRemapTarget)) {
    return false;
  }
  if (!sourceRemapTarget || *sourceRemapTarget != *target) {
    sourceBatchManifestError(
        diagnostics, manifest.path,
        context + ".sourceRemap.target must match artifact target '" + *target +
            "'");
    return false;
  }

  if (!parseOptionalSourceBatchStableRelativePathMember(
          *sourceRemap, "generatedFile", context + ".sourceRemap", manifest.path,
          diagnostics, logicalInput)) {
    return false;
  }
  if (!logicalInput || *logicalInput != *path) {
    sourceBatchManifestError(
        diagnostics, manifest.path,
        context + ".sourceRemap.generatedFile must match artifact path '" +
            *path + "'");
    return false;
  }

  if (!parseOptionalSourceBatchStableRelativePathMember(
          *sourceRemap, "path", context + ".sourceRemap", manifest.path,
          diagnostics, sourceRemapPath)) {
    return false;
  }
  if (!sourceRemapPath) {
    sourceBatchManifestError(
        diagnostics, manifest.path,
        context + ".sourceRemap.path must be a stable relative path");
    return false;
  }
  if (*sourceRemapPath == *path) {
    sourceBatchManifestError(
        diagnostics, manifest.path,
        context +
            ".sourceRemap.path must reference a sidecar path, not artifact path");
    return false;
  }

  std::optional<std::uintmax_t> mappingCount;
  if (!parseOptionalSourceBatchUnsignedMember(
          *sourceRemap, "mappingCount", context + ".sourceRemap", manifest.path,
          diagnostics, mappingCount)) {
    return false;
  }
  if (!mappingCount || *mappingCount == 0) {
    sourceBatchManifestError(diagnostics, manifest.path,
                             context +
                                 ".sourceRemap.mappingCount must be positive");
    return false;
  }

  std::optional<std::uintmax_t> sourceRemapSizeBytes;
  if (!parseOptionalSourceBatchUnsignedMember(
          *sourceRemap, "sizeBytes", context + ".sourceRemap", manifest.path,
          diagnostics, sourceRemapSizeBytes)) {
    return false;
  }
  if (!sourceRemapSizeBytes) {
    sourceBatchManifestError(diagnostics, manifest.path,
                             context +
                                 ".sourceRemap.sizeBytes must be recorded");
    return false;
  }

  std::string sourceRemapSha256;
  if (!parseCrossTLProjectReportSourceRemapHash(
          *sourceRemap, context + ".sourceRemap", manifest.path, diagnostics,
          sourceRemapSha256)) {
    return false;
  }
  const std::filesystem::path resolvedSourceRemapPath =
      resolveManifestPath(projectRoot, *sourceRemapPath);
  if (!validateCrossTLProjectReportSourceRemapSidecarIntegrity(
          resolvedSourceRemapPath, *sourceRemapSizeBytes, sourceRemapSha256,
          context + ".sourceRemap", manifest.path, diagnostics)) {
    return false;
  }

  SourceBatchEntry entry;
  entry.id =
      uniqueCrossTLProjectReportEntryId(manifest, std::move(source), artifactIndex);
  entry.path = resolveManifestPath(projectRoot, *path);
  entry.logicalInput = std::filesystem::path(*logicalInput);
  entry.sourceRemap = resolvedSourceRemapPath;
  manifest.sources.push_back(std::move(entry));
  return true;
}

std::optional<SourceBatchManifest> loadCrossTLProjectReportSourceBatchManifest(
    std::string_view document, const std::filesystem::path &manifestPath,
    crossgl::DiagnosticEngine &diagnostics) {
  SourceBatchManifest manifest;
  manifest.path = manifestPath;

  std::filesystem::path reportBase = manifestPath.parent_path();
  if (reportBase.empty()) {
    reportBase = ".";
  }
  manifest.root = reportBase.lexically_normal();
  std::filesystem::path projectRoot = manifest.root;
  if (const std::optional<std::string_view> project =
          crossgl::findObjectMemberValue(document, "project")) {
    if (!crossgl::isJsonObjectDocument(*project)) {
      sourceBatchManifestError(
          diagnostics, manifestPath,
          "CrossTL project report project must be a JSON object");
      return std::nullopt;
    }
    std::optional<std::string> root;
    if (!parseOptionalSourceBatchStringMember(
            *project, "root", "CrossTL project report project", manifestPath,
            diagnostics, root, /*requireNonEmpty=*/false)) {
      return std::nullopt;
    }
    if (root && !root->empty()) {
      projectRoot = resolveManifestPath(reportBase, *root);
    }
  }

  const std::optional<std::string_view> artifacts =
      crossgl::findObjectMemberValue(document, "artifacts");
  if (!artifacts) {
    sourceBatchManifestError(diagnostics, manifestPath,
                             "CrossTL project report requires artifacts array");
    return std::nullopt;
  }

  bool valid = true;
  const bool parsedArtifacts = forEachSourceBatchJsonArrayElement(
      *artifacts, [&](std::size_t index, std::string_view artifactText) {
        if (!valid) {
          return false;
        }
        valid = parseCrossTLProjectReportArtifact(
            artifactText, index, projectRoot, manifest, diagnostics);
        return valid;
      });
  if (!parsedArtifacts || !valid) {
    if (!parsedArtifacts && valid) {
      sourceBatchManifestError(
          diagnostics, manifestPath,
          "CrossTL project report artifacts must be a JSON array");
    }
    return std::nullopt;
  }
  if (manifest.sources.empty()) {
    sourceBatchManifestError(
        diagnostics, manifestPath,
        "CrossTL project report contains no translated cgl artifacts");
    return std::nullopt;
  }
  return manifest;
}

std::optional<SourceBatchManifest>
loadSourceBatchManifest(const std::filesystem::path &manifestPath,
                        crossgl::DiagnosticEngine &diagnostics) {
  std::optional<std::string> document =
      readTextDocument(manifestPath, diagnostics);
  if (!document) {
    return std::nullopt;
  }

  if (!crossgl::isJsonObjectDocument(*document)) {
    sourceBatchManifestError(
        diagnostics, manifestPath,
        "source batch manifest must be a JSON object document");
    return std::nullopt;
  }
  if (std::optional<crossgl::DuplicateJsonKey> duplicate =
          crossgl::findDuplicateJsonKey(*document)) {
    sourceBatchManifestError(diagnostics, manifestPath,
                             "source batch manifest contains duplicate key '" +
                                 duplicate->path + "'");
    return std::nullopt;
  }

  const std::optional<std::uintmax_t> schemaVersion =
      crossgl::objectUnsignedMember(*document, "schemaVersion");
  if (!schemaVersion || *schemaVersion != 1) {
    sourceBatchManifestError(
        diagnostics, manifestPath,
        "source batch manifest requires schemaVersion 1");
    return std::nullopt;
  }
  std::optional<std::string> kind;
  if (!parseOptionalSourceBatchStringMember(*document, "kind",
                                            "source batch manifest",
                                            manifestPath, diagnostics, kind)) {
    return std::nullopt;
  }
  if (kind && *kind == "crosstl-project-portability-report") {
    return loadCrossTLProjectReportSourceBatchManifest(*document, manifestPath,
                                                       diagnostics);
  }

  if (!validateSourceBatchAllowedMembers(
          *document, {"schemaVersion", "kind", "root", "defaults", "sources"},
          "source batch manifest", manifestPath, diagnostics)) {
    return std::nullopt;
  }
  if (!kind || *kind != "crossgl.sourceBatchManifest") {
    sourceBatchManifestError(
        diagnostics, manifestPath,
        "source batch manifest kind must be crossgl.sourceBatchManifest");
    return std::nullopt;
  }

  SourceBatchManifest manifest;
  manifest.path = manifestPath;
  manifest.root = manifestPath.parent_path();
  if (manifest.root.empty()) {
    manifest.root = ".";
  }
  std::optional<std::string> root;
  if (!parseOptionalSourceBatchStringMember(*document, "root",
                                            "source batch manifest",
                                            manifestPath, diagnostics, root)) {
    return std::nullopt;
  }
  if (root) {
    manifest.root = resolveManifestPath(manifest.root, *root);
  } else {
    manifest.root = manifest.root.lexically_normal();
  }

  if (std::optional<std::string_view> defaults =
          crossgl::findObjectMemberValue(*document, "defaults")) {
    if (!parseSourceBatchDefaults(*defaults, manifest.defaults, manifestPath,
                                  diagnostics)) {
      return std::nullopt;
    }
  }

  std::optional<std::string_view> sources =
      crossgl::findObjectMemberValue(*document, "sources");
  if (!sources) {
    sourceBatchManifestError(diagnostics, manifestPath,
                             "source batch manifest requires sources array");
    return std::nullopt;
  }
  if (!parseSourceBatchSources(*sources, manifest, diagnostics)) {
    return std::nullopt;
  }
  return manifest;
}

void appendDiagnostics(std::vector<crossgl::Diagnostic> &target,
                       const std::vector<crossgl::Diagnostic> &source) {
  target.insert(target.end(), source.begin(), source.end());
}

crossgl::SourceLocation
sourceRemapDocumentLocation(const std::filesystem::path &requestedPath,
                            const crossgl::SourceRemap &sourceRemap) {
  if (sourceRemap.documentPath) {
    return cliSourceLocation(*sourceRemap.documentPath);
  }
  return cliSourceLocation(requestedPath);
}

std::vector<crossgl::Diagnostic> loadAndValidateSourceRemapDiagnostics(
    const std::filesystem::path &sourceRemapPath,
    const std::filesystem::path &compilerInputPath,
    std::optional<crossgl::SourceRemap> &sourceRemap) {
  crossgl::DiagnosticEngine remapDiagnostics;
  sourceRemap = crossgl::loadSourceRemap(sourceRemapPath, remapDiagnostics);
  if (!sourceRemap) {
    return remapDiagnostics.diagnostics();
  }
  (void)crossgl::validateSourceRemapGeneratedFile(
      *sourceRemap, compilerInputPath, remapDiagnostics,
      sourceRemapDocumentLocation(sourceRemapPath, *sourceRemap));
  return remapDiagnostics.diagnostics();
}

bool hasErrorDiagnostics(const std::vector<crossgl::Diagnostic> &diagnostics) {
  for (const crossgl::Diagnostic &diagnostic : diagnostics) {
    if (diagnostic.severity == crossgl::DiagnosticSeverity::Error) {
      return true;
    }
  }
  return false;
}

bool sourceBatchSucceeded(
    const std::vector<SourceBatchEntryResult> &entries,
    const std::vector<crossgl::Diagnostic> &diagnostics) {
  if (hasErrorDiagnostics(diagnostics)) {
    return false;
  }
  for (const SourceBatchEntryResult &entry : entries) {
    if (!entry.success) {
      return false;
    }
  }
  return true;
}

std::string sourceBatchResultJson(
    const SourceBatchManifest &manifest,
    const std::vector<SourceBatchEntryResult> &entries,
    const std::vector<crossgl::Diagnostic> &diagnostics) {
  const bool success = sourceBatchSucceeded(entries, diagnostics);
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"kind\": \"crossgl.sourceBatchResult\",\n"
      << "  \"manifest\": \""
      << crossgl::escapeJson(manifest.path.lexically_normal().generic_string())
      << "\",\n"
      << "  \"success\": " << (success ? "true" : "false") << ",\n"
      << "  \"entryCount\": " << entries.size() << ",\n"
      << "  \"entries\": [\n";
  for (std::size_t index = 0; index < entries.size(); ++index) {
    const SourceBatchEntryResult &entry = entries[index];
    out << "    {\n"
        << "      \"id\": \"" << crossgl::escapeJson(entry.id) << "\",\n"
        << "      \"path\": \""
        << crossgl::escapeJson(entry.inputPath.generic_string()) << "\",\n";
    if (entry.logicalInputPath) {
      out << "      \"logicalInput\": \""
          << crossgl::escapeJson(entry.logicalInputPath->generic_string())
          << "\",\n";
    }
    if (entry.sourceRemapPath) {
      out << "      \"sourceRemap\": \""
          << crossgl::escapeJson(entry.sourceRemapPath->generic_string())
          << "\",\n";
    }
    if (entry.outputPath) {
      out << "      \"output\": \""
          << crossgl::escapeJson(entry.outputPath->generic_string())
          << "\",\n";
    }
    if (entry.artifactPath) {
      out << "      \"artifact\": \""
          << crossgl::escapeJson(entry.artifactPath->generic_string())
          << "\",\n";
    }
    out << "      \"target\": \"" << crossgl::targetName(entry.target)
        << "\",\n"
        << "      \"success\": " << (entry.success ? "true" : "false")
        << "\n"
        << "    }";
    if (index + 1 < entries.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << "  ],\n"
      << "  \"diagnosticReport\": "
      << crossgl::diagnosticsToJson(diagnostics) << "}\n";
  return out.str();
}

int validateSourceBatchCommandArgs(const std::vector<std::string> &args,
                                   const SourceBatchManifestFlag &manifestFlag,
                                   std::string_view command) {
  for (std::size_t index = 1; index < args.size(); ++index) {
    if (index == manifestFlag.flagIndex) {
      ++index;
      continue;
    }
    const std::string &arg = args[index];
    if (arg == "--diagnostics-json") {
      continue;
    }
    if (arg == "--opt-level") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --opt-level requires O0, O1, or O2\n";
        return 2;
      }
      ++index;
      continue;
    }
    if (command == "build" && arg == "--target") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --target requires a target name\n";
        return 2;
      }
      ++index;
      continue;
    }
    if (command == "build" && arg == "--debug-ir") {
      continue;
    }
    if (arg == "--logical-input" || arg == "--source-remap" ||
        arg == "--output") {
      std::cerr << "error: " << arg
                << " is per-source in source manifest mode; set it on each "
                   "sources[] entry instead\n";
      return 2;
    }
    if (!arg.empty() && arg[0] == '-') {
      std::cerr << "error: unknown " << command
                << " source manifest option: " << arg << "\n";
      return 2;
    }
    std::cerr << "error: " << command
              << " source manifest mode does not accept positional input "
                 "paths\n";
    return 2;
  }
  return 0;
}

std::optional<crossgl::OptimizationLevel>
sourceBatchOptimizationOverride(const std::vector<std::string> &args) {
  if (!hasArg(args, "--opt-level")) {
    return std::nullopt;
  }
  return optimizationLevelArg(args);
}

std::optional<crossgl::TargetKind>
sourceBatchTargetOverride(const std::vector<std::string> &args) {
  if (!hasArg(args, "--target")) {
    return std::nullopt;
  }
  return crossgl::targetFromString(argValue(args, "--target"));
}

crossgl::OptimizationLevel resolveSourceBatchOptimizationLevel(
    const SourceBatchEntry &entry,
    const std::optional<crossgl::OptimizationLevel> &commandOverride,
    const SourceBatchDefaults &defaults) {
  if (entry.optimizationLevel) {
    return *entry.optimizationLevel;
  }
  if (commandOverride) {
    return *commandOverride;
  }
  return defaults.optimizationLevel;
}

crossgl::TargetKind
resolveSourceBatchTarget(const SourceBatchEntry &entry,
                         const std::optional<crossgl::TargetKind> &commandOverride,
                         const SourceBatchDefaults &defaults) {
  if (entry.target) {
    return *entry.target;
  }
  if (commandOverride) {
    return *commandOverride;
  }
  return defaults.target;
}

bool resolveSourceBatchDebugIR(const SourceBatchEntry &entry,
                               bool commandDebugIR,
                               const SourceBatchDefaults &defaults) {
  if (entry.debugIR) {
    return *entry.debugIR;
  }
  if (commandDebugIR) {
    return true;
  }
  return defaults.debugIR;
}

int commandCheckSourceBatch(const std::vector<std::string> &args,
                            const SourceBatchManifestFlag &manifestFlag) {
  if (const int status =
          validateSourceBatchCommandArgs(args, manifestFlag, "check")) {
    return status;
  }
  const bool diagnosticsJson = hasArg(args, "--diagnostics-json");
  std::optional<crossgl::OptimizationLevel> optimizationOverride;
  try {
    optimizationOverride = sourceBatchOptimizationOverride(args);
  } catch (const std::exception &error) {
    std::cerr << "error: " << error.what() << "\n";
    return 2;
  }

  crossgl::DiagnosticEngine manifestDiagnostics;
  std::optional<SourceBatchManifest> manifest =
      loadSourceBatchManifest(manifestFlag.path, manifestDiagnostics);
  if (!manifest) {
    printDiagnostics(manifestDiagnostics.diagnostics());
    if (diagnosticsJson) {
      std::cout << crossgl::diagnosticsToJson(manifestDiagnostics.diagnostics());
    }
    return 1;
  }

  std::vector<crossgl::Diagnostic> allDiagnostics;
  std::vector<SourceBatchEntryResult> entryResults;
  for (const SourceBatchEntry &entry : manifest->sources) {
    SourceBatchEntryResult entryResult;
    entryResult.id = entry.id;
    entryResult.inputPath = entry.path;
    entryResult.logicalInputPath = entry.logicalInput;
    entryResult.sourceRemapPath = entry.sourceRemap;
    entryResult.target =
        resolveSourceBatchTarget(entry, std::nullopt, manifest->defaults);

    crossgl::DiagnosticEngine diagnostics;
    crossgl::CompilerModuleOptions options;
    options.optimizationLevel = resolveSourceBatchOptimizationLevel(
        entry, optimizationOverride, manifest->defaults);
    options.validateBackendInput = false;
    if (entry.logicalInput) {
      options.logicalPath = *entry.logicalInput;
    }
    (void)crossgl::loadCompilerModule(entry.path, diagnostics, options);
    std::vector<crossgl::Diagnostic> entryDiagnostics =
        diagnostics.diagnostics();

    if (entry.sourceRemap) {
      std::optional<crossgl::SourceRemap> sourceRemap;
      const std::filesystem::path compilerInputPath =
          entry.logicalInput.value_or(entry.path);
      std::vector<crossgl::Diagnostic> remapDiagnostics =
          loadAndValidateSourceRemapDiagnostics(*entry.sourceRemap,
                                                compilerInputPath, sourceRemap);
      if (hasErrorDiagnostics(remapDiagnostics)) {
        entryDiagnostics = std::move(remapDiagnostics);
      } else if (sourceRemap) {
        entryDiagnostics =
            crossgl::diagnosticsWithOriginalSourceLocations(entryDiagnostics,
                                                            *sourceRemap);
        appendDiagnostics(entryDiagnostics, remapDiagnostics);
      }
    }

    entryResult.success = !hasErrorDiagnostics(entryDiagnostics);
    appendDiagnostics(allDiagnostics, entryDiagnostics);
    entryResults.push_back(std::move(entryResult));
  }

  printDiagnostics(allDiagnostics);
  if (diagnosticsJson) {
    std::cout << sourceBatchResultJson(*manifest, entryResults, allDiagnostics);
  } else if (sourceBatchSucceeded(entryResults, allDiagnostics)) {
    for (const SourceBatchEntryResult &entry : entryResults) {
      std::cout << "check passed: " << entry.inputPath.string() << "\n";
    }
    std::cout << "batch check passed: " << entryResults.size()
              << " sources from " << manifest->path.string() << "\n";
  }
  return sourceBatchSucceeded(entryResults, allDiagnostics) ? 0 : 1;
}

int commandBuildSourceBatch(const std::vector<std::string> &args,
                            const SourceBatchManifestFlag &manifestFlag) {
  if (const int status =
          validateSourceBatchCommandArgs(args, manifestFlag, "build")) {
    return status;
  }
  const bool diagnosticsJson = hasArg(args, "--diagnostics-json");
  std::optional<crossgl::OptimizationLevel> optimizationOverride;
  std::optional<crossgl::TargetKind> targetOverride;
  try {
    optimizationOverride = sourceBatchOptimizationOverride(args);
    targetOverride = sourceBatchTargetOverride(args);
  } catch (const std::exception &error) {
    std::cerr << "error: " << error.what() << "\n";
    return 2;
  }

  crossgl::DiagnosticEngine manifestDiagnostics;
  std::optional<SourceBatchManifest> manifest =
      loadSourceBatchManifest(manifestFlag.path, manifestDiagnostics);
  if (!manifest) {
    printDiagnostics(manifestDiagnostics.diagnostics());
    if (diagnosticsJson) {
      std::cout << crossgl::diagnosticsToJson(manifestDiagnostics.diagnostics());
    }
    return 1;
  }

  std::vector<crossgl::Diagnostic> allDiagnostics;
  std::vector<SourceBatchEntryResult> entryResults;
  for (std::size_t index = 0; index < manifest->sources.size(); ++index) {
    const SourceBatchEntry &entry = manifest->sources[index];
    SourceBatchEntryResult entryResult;
    entryResult.id = entry.id;
    entryResult.inputPath = entry.path;
    entryResult.logicalInputPath = entry.logicalInput;
    entryResult.sourceRemapPath = entry.sourceRemap;
    entryResult.outputPath = entry.output;
    entryResult.target =
        resolveSourceBatchTarget(entry, targetOverride, manifest->defaults);

    if (!entry.output) {
      crossgl::DiagnosticEngine diagnostics;
      sourceBatchManifestError(
          diagnostics, manifest->path,
          "source batch manifest sources[" + std::to_string(index) +
              "] requires output for build");
      appendDiagnostics(allDiagnostics, diagnostics.diagnostics());
      entryResults.push_back(std::move(entryResult));
      continue;
    }

    crossgl::CompileRequest request;
    request.inputPath = entry.path;
    request.outputPath = *entry.output;
    request.target = entryResult.target;
    request.optimizationLevel = resolveSourceBatchOptimizationLevel(
        entry, optimizationOverride, manifest->defaults);
    request.debugIR =
        resolveSourceBatchDebugIR(entry, hasArg(args, "--debug-ir"),
                                  manifest->defaults);
    if (entry.logicalInput) {
      request.logicalInputPath = *entry.logicalInput;
    }

    if (entry.sourceRemap) {
      std::optional<crossgl::SourceRemap> sourceRemap;
      const std::filesystem::path compilerInputPath =
          entry.logicalInput.value_or(entry.path);
      std::vector<crossgl::Diagnostic> remapDiagnostics =
          loadAndValidateSourceRemapDiagnostics(*entry.sourceRemap,
                                                compilerInputPath, sourceRemap);
      if (hasErrorDiagnostics(remapDiagnostics)) {
        appendDiagnostics(allDiagnostics, remapDiagnostics);
        entryResults.push_back(std::move(entryResult));
        continue;
      }
      appendDiagnostics(allDiagnostics, remapDiagnostics);
      if (sourceRemap) {
        request.sourceRemap = std::move(*sourceRemap);
      }
    }

    crossgl::CompileResult result = crossgl::compile(request);
    entryResult.success = result.success;
    if (!result.artifactPath.empty()) {
      entryResult.artifactPath = result.artifactPath;
    }
    entryResult.target = result.resolvedTarget;
    appendDiagnostics(allDiagnostics, result.diagnostics);
    entryResults.push_back(std::move(entryResult));
  }

  printDiagnostics(allDiagnostics);
  if (diagnosticsJson) {
    std::cout << sourceBatchResultJson(*manifest, entryResults, allDiagnostics);
  } else if (sourceBatchSucceeded(entryResults, allDiagnostics)) {
    for (const SourceBatchEntryResult &entry : entryResults) {
      if (entry.artifactPath) {
        std::cout << "built " << entry.artifactPath->string() << " for "
                  << crossgl::targetName(entry.target) << "\n";
      }
    }
    std::cout << "batch build passed: " << entryResults.size()
              << " sources from " << manifest->path.string() << "\n";
  }
  return sourceBatchSucceeded(entryResults, allDiagnostics) ? 0 : 1;
}

std::string packageReleaseUploadFingerprint(
    const crossgl::PackageReleasePublishUploadRequest &request) {
  std::string fingerprintInput;
  fingerprintInput += request.targetKind;
  fingerprintInput.push_back('\n');
  fingerprintInput += request.uploadUri;
  fingerprintInput.push_back('\n');
  fingerprintInput += std::to_string(request.sizeBytes);
  fingerprintInput.push_back('\n');
  fingerprintInput += request.sha256;
  return crossgl::sha256(fingerprintInput);
}

std::optional<std::string>
findJsonStringOrUnsignedMember(std::string_view text, std::string_view key) {
  if (std::optional<std::string> value = crossgl::objectStringMember(text, key)) {
    return value;
  }
  if (std::optional<std::uintmax_t> value =
          crossgl::objectUnsignedMember(text, key)) {
    return std::to_string(*value);
  }
  return std::nullopt;
}

std::optional<std::string>
firstJsonStringOrUnsignedMember(std::string_view text,
                                std::initializer_list<std::string_view> keys) {
  for (std::string_view key : keys) {
    if (std::optional<std::string> value =
            findJsonStringOrUnsignedMember(text, key)) {
      return value;
    }
  }
  return std::nullopt;
}

void populateGcsObjectMetadataFromJson(
    crossgl::PackageReleasePublishUploadAttempt &attempt,
    std::string_view json) {
  if (!crossgl::isJsonObjectDocument(json)) {
    return;
  }
  if (std::optional<std::string> generation =
          firstJsonStringOrUnsignedMember(json, {"generation"})) {
    attempt.generation = std::move(*generation);
  }
  if (std::optional<std::string> metageneration =
          firstJsonStringOrUnsignedMember(json, {"metageneration"})) {
    attempt.metageneration = std::move(*metageneration);
  }
  if (std::optional<std::string> crc32c = firstJsonStringOrUnsignedMember(
          json, {"crc32c", "crc32cHash", "crc32c_hash"})) {
    attempt.crc32c = std::move(*crc32c);
  }
  if (std::optional<std::string> md5Hash = firstJsonStringOrUnsignedMember(
          json, {"md5Hash", "md5_hash", "md5HashBase64"})) {
    attempt.md5Hash = std::move(*md5Hash);
  }
}

class MockPackageReleasePublishUploader final
    : public crossgl::PackageReleasePublishUploader {
public:
  bool uploadPackageReleaseArtifact(
      const crossgl::PackageReleasePublishUploadRequest &request,
      std::string &errorMessage) override {
    if (request.targetKind != "gcs") {
      errorMessage =
          "mock package release upload supports only gcs upload requests";
      return false;
    }
    return true;
  }

  crossgl::PackageReleasePublishUploadAttempt
  uploadPackageReleaseArtifactDetailed(
      const crossgl::PackageReleasePublishUploadRequest &request) override {
    crossgl::PackageReleasePublishUploadAttempt attempt;
    attempt.request = request;
    attempt.provider = "mock";
    attempt.idempotencyKey = packageReleaseUploadFingerprint(request);

    std::string errorMessage;
    if (uploadPackageReleaseArtifact(request, errorMessage)) {
      attempt.status =
          crossgl::PackageReleasePublishUploadAttemptStatus::Uploaded;
    } else {
      attempt.status =
          crossgl::PackageReleasePublishUploadAttemptStatus::Failed;
      attempt.errorMessage = std::move(errorMessage);
    }
    return attempt;
  }
};

class GcsPackageReleasePublishUploader final
    : public crossgl::PackageReleasePublishUploader {
public:
  GcsPackageReleasePublishUploader(bool overwrite, bool captureMetadata)
      : overwrite_(overwrite), captureMetadata_(captureMetadata) {}

  bool uploadPackageReleaseArtifact(
      const crossgl::PackageReleasePublishUploadRequest &request,
      std::string &errorMessage) override {
    return uploadPackageReleaseArtifactImpl(request, errorMessage);
  }

  crossgl::PackageReleasePublishUploadAttempt
  uploadPackageReleaseArtifactDetailed(
      const crossgl::PackageReleasePublishUploadRequest &request) override {
    crossgl::PackageReleasePublishUploadAttempt attempt;
    attempt.request = request;
    attempt.provider = "gcs";
    attempt.overwrite = overwrite_;
    attempt.idempotencyKey = packageReleaseUploadFingerprint(request);
    if (!overwrite_) {
      attempt.preconditionKind = "ifGenerationMatch";
      attempt.preconditionValue = "0";
    }

    std::string errorMessage;
    if (uploadPackageReleaseArtifactImpl(request, errorMessage)) {
      attempt.status =
          crossgl::PackageReleasePublishUploadAttemptStatus::Uploaded;
      describeUploadedObject(request, attempt);
    } else {
      attempt.status =
          crossgl::PackageReleasePublishUploadAttemptStatus::Failed;
      attempt.errorMessage = std::move(errorMessage);
    }
    return attempt;
  }

private:
  bool uploadPackageReleaseArtifactImpl(
      const crossgl::PackageReleasePublishUploadRequest &request,
      std::string &errorMessage) {
    if (request.targetKind != "gcs") {
      errorMessage = "GCS package release upload accepts only gcs requests";
      return false;
    }
    if (request.credentialsEnv.empty()) {
      errorMessage =
          "GCS package release upload requires a credentialsEnv request field";
      return false;
    }

    const char *credentialsValue = std::getenv(request.credentialsEnv.c_str());
    if (credentialsValue == nullptr ||
        std::string_view(credentialsValue).empty()) {
      errorMessage =
          "GCS package release upload credentials environment variable is not "
          "set: " +
          request.credentialsEnv;
      return false;
    }

    const std::string customMetadata =
        "crossgl-sha256=" + request.sha256 +
        ",crossgl-size-bytes=" + std::to_string(request.sizeBytes) +
        ",crossgl-upload-fingerprint=" +
        packageReleaseUploadFingerprint(request);

    std::vector<std::string> command = {"gcloud", "--quiet", "storage", "cp"};
    if (!overwrite_) {
      command.push_back("--if-generation-match=0");
    }
    command.push_back("--custom-metadata=" + customMetadata);
    command.push_back(request.stagedPath.string());
    command.push_back(request.uploadUri);
    const crossgl::ProcessCaptureResult result =
        crossgl::runProcessCapture(command);
    if (!result.started || result.exitCode != 0) {
      errorMessage = "gcloud storage cp failed for " + request.uploadUri +
                     " with status " + std::to_string(result.exitCode);
      const std::string detail = processCaptureFailureDetail(result);
      if (!detail.empty()) {
        errorMessage += ": " + detail;
      }
      return false;
    }
    return true;
  }

  void describeUploadedObject(
      const crossgl::PackageReleasePublishUploadRequest &request,
      crossgl::PackageReleasePublishUploadAttempt &attempt) {
    if (!captureMetadata_) {
      return;
    }

    const crossgl::ProcessCaptureResult result =
        crossgl::runProcessCapture({"gcloud", "--quiet", "storage", "objects",
                                    "describe", request.uploadUri,
                                    "--format=json"});
    if (result.started && result.exitCode == 0) {
      populateGcsObjectMetadataFromJson(attempt, result.stdoutText);
    }
  }

  bool overwrite_ = false;
  bool captureMetadata_ = false;
};

int commandDoctorJson(const std::string &inputPath) {
  std::optional<std::string> targetExplanation;
  crossgl::DiagnosticEngine diagnostics;
  if (!inputPath.empty()) {
    targetExplanation = crossgl::explainTargets(inputPath, diagnostics);
    printDiagnostics(diagnostics.diagnostics());
    if (!targetExplanation) {
      return 1;
    }
  }

  std::cout << "{\n"
            << "  \"schemaVersion\": 1,\n"
            << "  \"toolchain\": ";
  printIndentedJsonValue(
      crossgl::toolchainStatusToJson(crossgl::detectToolchain()), "  ");
  std::cout << ",\n"
            << "  \"targetExplanation\": ";
  if (targetExplanation) {
    printIndentedJsonValue(*targetExplanation, "  ");
  } else {
    std::cout << "null";
  }
  std::cout << "\n}\n";
  return 0;
}

int commandDoctor(const std::vector<std::string> &args) {
  const std::string inputPath = firstNonFlagArg(args);
  if (hasArg(args, "--json")) {
    return commandDoctorJson(inputPath);
  }

  std::cout << crossgl::toolchainStatusToText(crossgl::detectToolchain());
  if (!inputPath.empty()) {
    crossgl::DiagnosticEngine diagnostics;
    auto explanation = crossgl::explainTargetsText(inputPath, diagnostics);
    printDiagnostics(diagnostics.diagnostics());
    if (!explanation) {
      return 1;
    }
    std::cout << "\n" << *explanation;
  }
  return 0;
}

int commandTargets() {
  std::cout << "Targets:\n";
  const crossgl::TargetKind defaultTarget = crossgl::defaultTargetForHost();
  for (const crossgl::TargetInfo &target : crossgl::allTargets()) {
    std::cout << "  " << target.name;
    if (target.kind == defaultTarget) {
      std::cout << " (default)";
    }
    std::cout << " -> " << target.binaryExtension << " on " << target.platform
              << " [" << (target.implemented ? "implemented" : "planned")
              << "]\n";
  }
  return 0;
}

int commandCheck(const std::vector<std::string> &args) {
  const SourceBatchManifestFlag manifestFlag =
      parseSourceBatchManifestFlag(args);
  if (manifestFlag.present) {
    if (!manifestFlag.valid) {
      return 2;
    }
    return commandCheckSourceBatch(args, manifestFlag);
  }

  const std::string inputPath = firstNonFlagArg(args);
  if (inputPath.empty()) {
    printUsage();
    return 2;
  }
  const bool diagnosticsJson = hasArg(args, "--diagnostics-json");
  const std::string logicalInputPath = argValue(args, "--logical-input");
  if (hasArg(args, "--logical-input") && logicalInputPath.empty()) {
    std::cerr << "error: --logical-input requires a path\n";
    return 2;
  }
  const std::string sourceRemapPath = argValue(args, "--source-remap");
  if (hasArg(args, "--source-remap") && sourceRemapPath.empty()) {
    std::cerr << "error: --source-remap requires a path\n";
    return 2;
  }

  crossgl::OptimizationLevel optimizationLevel;
  try {
    optimizationLevel = optimizationLevelArg(args);
  } catch (const std::exception &error) {
    std::cerr << "error: " << error.what() << "\n";
    return 2;
  }

  crossgl::DiagnosticEngine diagnostics;
  crossgl::CompilerModuleOptions options;
  options.optimizationLevel = optimizationLevel;
  options.validateBackendInput = false;
  if (!logicalInputPath.empty()) {
    options.logicalPath = logicalInputPath;
  }
  (void)crossgl::loadCompilerModule(inputPath, diagnostics, options);
  std::vector<crossgl::Diagnostic> resultDiagnostics = diagnostics.diagnostics();
  if (!sourceRemapPath.empty()) {
    crossgl::DiagnosticEngine remapDiagnostics;
    std::optional<crossgl::SourceRemap> sourceRemap =
        crossgl::loadSourceRemap(sourceRemapPath, remapDiagnostics);
    if (!sourceRemap) {
      printDiagnostics(remapDiagnostics.diagnostics());
      if (diagnosticsJson) {
        std::cout << crossgl::diagnosticsToJson(remapDiagnostics.diagnostics());
      }
      return 1;
    }
    const std::filesystem::path compilerInputPath =
        logicalInputPath.empty() ? std::filesystem::path(inputPath)
                                 : std::filesystem::path(logicalInputPath);
    if (!crossgl::validateSourceRemapGeneratedFile(
            *sourceRemap, compilerInputPath, remapDiagnostics,
            sourceRemapDocumentLocation(sourceRemapPath, *sourceRemap))) {
      printDiagnostics(remapDiagnostics.diagnostics());
      if (diagnosticsJson) {
        std::cout << crossgl::diagnosticsToJson(remapDiagnostics.diagnostics());
      }
      return 1;
    }
    resultDiagnostics =
        crossgl::diagnosticsWithOriginalSourceLocations(resultDiagnostics,
                                                        *sourceRemap);
  }
  printDiagnostics(resultDiagnostics);
  if (diagnosticsJson) {
    std::cout << crossgl::diagnosticsToJson(resultDiagnostics);
  }
  if (!diagnostics.hasErrors()) {
    if (!diagnosticsJson) {
      std::cout << "check passed: " << inputPath << "\n";
    }
    return 0;
  }
  return 1;
}

int commandExplainTargets(const std::vector<std::string> &args) {
  std::string inputPath;
  std::string logicalInputPath;
  for (std::size_t index = 1; index < args.size(); ++index) {
    if (args[index] == "--logical-input") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --logical-input requires a path\n";
        return 2;
      }
      logicalInputPath = args[index + 1];
      ++index;
      continue;
    }
    if (!args[index].empty() && args[index][0] == '-') {
      std::cerr << "error: explain-targets accepts only --logical-input\n";
      return 2;
    }
    if (!inputPath.empty()) {
      std::cerr << "error: explain-targets accepts exactly one input path\n";
      return 2;
    }
    inputPath = args[index];
  }

  if (inputPath.empty()) {
    printUsage();
    return 2;
  }

  crossgl::DiagnosticEngine diagnostics;
  std::optional<std::string> explanation;
  if (logicalInputPath.empty()) {
    explanation = crossgl::explainTargets(inputPath, diagnostics);
  } else if (std::optional<crossgl::SourceInput> input =
                 readLogicalSourceInput(inputPath, logicalInputPath,
                                        diagnostics)) {
    explanation = crossgl::explainTargets(*input, diagnostics);
  }
  printDiagnostics(diagnostics.diagnostics());
  if (!explanation) {
    return 1;
  }
  std::cout << *explanation;
  return 0;
}

int commandLanguageFeatureReport(const std::vector<std::string> &args) {
  std::string inputPath;
  crossgl::LanguageFeatureReportOptions options;
  options.commandLine.push_back("cglc");
  options.commandLine.insert(options.commandLine.end(), args.begin(),
                             args.end());

  for (std::size_t index = 1; index < args.size(); ++index) {
    if (args[index] == "--root") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: language-feature-report --root requires a path\n";
        return 2;
      }
      options.repositoryRoot = args[index + 1];
      ++index;
      continue;
    }
    if (!args[index].empty() && args[index][0] == '-') {
      std::cerr << "error: language-feature-report accepts only --root\n";
      return 2;
    }
    if (!inputPath.empty()) {
      std::cerr
          << "error: language-feature-report accepts exactly one input path\n";
      return 2;
    }
    inputPath = args[index];
  }

  if (inputPath.empty()) {
    printUsage();
    return 2;
  }

  crossgl::DiagnosticEngine diagnostics;
  std::optional<std::string> report =
      crossgl::languageFeatureReportJson(inputPath, diagnostics, options);
  printDiagnostics(diagnostics.diagnostics());
  if (!report) {
    return 1;
  }
  std::cout << *report;
  return 0;
}

int commandDumpIR(const std::vector<std::string> &args) {
  if (args.size() < 2) {
    printUsage();
    return 2;
  }

  const std::string stageName = argValue(args, "--stage", "hir");
  const std::string targetName = argValue(args, "--target", "auto");
  const std::string logicalInputPath = argValue(args, "--logical-input");
  if (hasArg(args, "--logical-input") && logicalInputPath.empty()) {
    std::cerr << "error: --logical-input requires a path\n";
    return 2;
  }
  const std::string sourceRemapPath = argValue(args, "--source-remap");
  if (hasArg(args, "--source-remap") && sourceRemapPath.empty()) {
    std::cerr << "error: --source-remap requires a path\n";
    return 2;
  }
  crossgl::DebugMetadataHIRSourceMapFilter sourceMapFilter;
  setOptionalArg(sourceMapFilter.stage, args, "--source-map-stage");
  setOptionalArg(sourceMapFilter.entryPoint, args, "--source-map-entry");
  setOptionalArg(sourceMapFilter.function, args, "--source-map-function");
  setOptionalArg(sourceMapFilter.statementKind, args,
                 "--source-map-statement-kind");
  setOptionalArg(sourceMapFilter.expressionKind, args,
                 "--source-map-expression-kind");
  setOptionalArg(sourceMapFilter.expressionValue, args,
                 "--source-map-operation");
  setOptionalArg(sourceMapFilter.expressionValue, args,
                 "--source-map-expression-value");
  setOptionalArg(sourceMapFilter.ownerKind, args, "--source-map-owner-kind");
  setOptionalArg(sourceMapFilter.ownerName, args, "--source-map-owner-name");
  setOptionalArg(sourceMapFilter.resourceRecordKind, args,
                 "--source-map-resource-record-kind");
  setOptionalArg(sourceMapFilter.resourceName, args, "--source-map-resource-name");
  setOptionalArg(sourceMapFilter.resourceKind, args, "--source-map-resource-kind");
  crossgl::DebugMetadataHIRSourceMapPagination sourceMapPagination;
  setSizeArg(sourceMapPagination.expressionOffset, args, "--source-map-offset");
  setSizeArg(sourceMapPagination.typeOffset, args, "--source-map-offset");
  setSizeArg(sourceMapPagination.statementOffset, args, "--source-map-offset");
  setSizeArg(sourceMapPagination.resourceOffset, args, "--source-map-offset");
  setOptionalSizeArg(sourceMapPagination.expressionLimit, args,
                     "--source-map-limit");
  setOptionalSizeArg(sourceMapPagination.typeLimit, args, "--source-map-limit");
  setOptionalSizeArg(sourceMapPagination.statementLimit, args,
                     "--source-map-limit");
  setOptionalSizeArg(sourceMapPagination.resourceLimit, args,
                     "--source-map-limit");
  setSizeArg(sourceMapPagination.expressionOffset, args,
             "--source-map-expression-offset");
  setOptionalSizeArg(sourceMapPagination.expressionLimit, args,
                     "--source-map-expression-limit");
  setSizeArg(sourceMapPagination.typeOffset, args, "--source-map-type-offset");
  setOptionalSizeArg(sourceMapPagination.typeLimit, args,
                     "--source-map-type-limit");
  setSizeArg(sourceMapPagination.statementOffset, args,
             "--source-map-statement-offset");
  setOptionalSizeArg(sourceMapPagination.statementLimit, args,
                     "--source-map-statement-limit");
  setSizeArg(sourceMapPagination.resourceOffset, args,
             "--source-map-resource-offset");
  setOptionalSizeArg(sourceMapPagination.resourceLimit, args,
                     "--source-map-resource-limit");
  sourceMapPagination.recordsEnabled = hasArg(args, "--source-map-records");
  if (std::optional<std::size_t> recordOffset =
          optionalSizeArg(args, "--source-map-record-offset")) {
    sourceMapPagination.recordsEnabled = true;
    sourceMapPagination.recordOffset = *recordOffset;
  }
  if (std::optional<std::size_t> recordLimit =
          optionalSizeArg(args, "--source-map-record-limit")) {
    sourceMapPagination.recordsEnabled = true;
    sourceMapPagination.recordLimit = *recordLimit;
  }
  crossgl::DebugMetadataHIRSourceMapOptions sourceMapOptions;
  const std::optional<int> sourceMapSchemaVersion =
      optionalHIRSourceMapSchemaVersionArg(args, "--source-map-schema-version");
  const std::optional<int> hirSourceMapSchemaVersion =
      optionalHIRSourceMapSchemaVersionArg(args,
                                           "--hir-source-map-schema-version");
  if (sourceMapSchemaVersion && hirSourceMapSchemaVersion &&
      *sourceMapSchemaVersion != *hirSourceMapSchemaVersion) {
    std::cerr << "error: source-map schema version aliases disagree\n";
    return 2;
  }
  if (sourceMapSchemaVersion || hirSourceMapSchemaVersion) {
    sourceMapOptions.schemaVersion = sourceMapSchemaVersion
                                         ? *sourceMapSchemaVersion
                                         : *hirSourceMapSchemaVersion;
  }
  if (!sourceRemapPath.empty()) {
    crossgl::DiagnosticEngine remapDiagnostics;
    std::optional<crossgl::SourceRemap> sourceRemap =
        crossgl::loadSourceRemap(sourceRemapPath, remapDiagnostics);
    if (!sourceRemap) {
      printDiagnostics(remapDiagnostics.diagnostics());
      return 1;
    }
    const std::filesystem::path compilerInputPath =
        logicalInputPath.empty() ? std::filesystem::path(args[1])
                                 : std::filesystem::path(logicalInputPath);
    if (!crossgl::validateSourceRemapGeneratedFile(
            *sourceRemap, compilerInputPath, remapDiagnostics,
            sourceRemapDocumentLocation(sourceRemapPath, *sourceRemap))) {
      printDiagnostics(remapDiagnostics.diagnostics());
      return 1;
    }
    sourceMapOptions.sourceRemap = std::move(*sourceRemap);
  }

  crossgl::DiagnosticEngine diagnostics;
  try {
    const crossgl::DumpStage stage = crossgl::dumpStageFromString(stageName);
    const crossgl::TargetKind target = crossgl::targetFromString(targetName);
    const crossgl::OptimizationLevel optimizationLevel =
        optimizationLevelArg(args);
    if (crossgl::isLegacyMLIRDumpStageName(stageName)) {
      std::cerr << "warning: --stage mlir is a compatibility alias for "
                   "--stage pseudo-mlir; output is pseudo-MLIR, not real "
                   "MLIR. Real MLIR is reserved for "
                   "CROSSGL_ENABLE_MLIR_EXPERIMENTAL.\n";
    }

    std::optional<std::string> dump;
    if (logicalInputPath.empty()) {
      dump = crossgl::dumpIR(args[1], stage, target, optimizationLevel,
                             diagnostics, sourceMapFilter,
                             sourceMapPagination, sourceMapOptions);
    } else if (std::optional<crossgl::SourceInput> sourceInput =
                   readLogicalSourceInput(args[1], logicalInputPath,
                                          diagnostics)) {
      dump = crossgl::dumpIR(*sourceInput, stage, target, optimizationLevel,
                             diagnostics, sourceMapFilter,
                             sourceMapPagination, sourceMapOptions);
    }
    printDiagnostics(diagnostics.diagnostics());
    if (!dump) {
      return 1;
    }
    std::cout << *dump;
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "error: " << error.what() << "\n";
    return 2;
  }
}

int commandBuild(const std::vector<std::string> &args) {
  const SourceBatchManifestFlag manifestFlag =
      parseSourceBatchManifestFlag(args);
  if (manifestFlag.present) {
    if (!manifestFlag.valid) {
      return 2;
    }
    return commandBuildSourceBatch(args, manifestFlag);
  }

  if (args.size() < 2) {
    printUsage();
    return 2;
  }

  crossgl::CompileRequest request;
  request.inputPath = args[1];
  request.target =
      crossgl::targetFromString(argValue(args, "--target", "auto"));
  request.debugIR = hasArg(args, "--debug-ir");
  const std::string logicalInputPath = argValue(args, "--logical-input");
  if (hasArg(args, "--logical-input") && logicalInputPath.empty()) {
    std::cerr << "error: --logical-input requires a path\n";
    return 2;
  }
  if (!logicalInputPath.empty()) {
    request.logicalInputPath = logicalInputPath;
  }
  const std::string sourceRemapPath = argValue(args, "--source-remap");
  if (hasArg(args, "--source-remap") && sourceRemapPath.empty()) {
    std::cerr << "error: --source-remap requires a path\n";
    return 2;
  }
  try {
    request.optimizationLevel = optimizationLevelArg(args);
  } catch (const std::exception &error) {
    std::cerr << "error: " << error.what() << "\n";
    return 2;
  }
  const bool diagnosticsJson = hasArg(args, "--diagnostics-json");

  std::string output = argValue(args, "--output");
  if (output.empty()) {
    std::filesystem::path inputPath(args[1]);
    output = (inputPath.stem().string() + ".cglb");
  }
  request.outputPath = output;

  if (!sourceRemapPath.empty()) {
    crossgl::DiagnosticEngine remapDiagnostics;
    std::optional<crossgl::SourceRemap> sourceRemap =
        crossgl::loadSourceRemap(sourceRemapPath, remapDiagnostics);
    if (!sourceRemap) {
      printDiagnostics(remapDiagnostics.diagnostics());
      if (diagnosticsJson) {
        std::cout << crossgl::diagnosticsToJson(remapDiagnostics.diagnostics());
      }
      return 1;
    }
    const std::filesystem::path compilerInputPath =
        logicalInputPath.empty() ? request.inputPath
                                 : std::filesystem::path(logicalInputPath);
    if (!crossgl::validateSourceRemapGeneratedFile(
            *sourceRemap, compilerInputPath, remapDiagnostics,
            sourceRemapDocumentLocation(sourceRemapPath, *sourceRemap))) {
      printDiagnostics(remapDiagnostics.diagnostics());
      if (diagnosticsJson) {
        std::cout << crossgl::diagnosticsToJson(remapDiagnostics.diagnostics());
      }
      return 1;
    }
    request.sourceRemap = std::move(*sourceRemap);
  }

  crossgl::CompileResult result = crossgl::compile(request);
  printDiagnostics(result.diagnostics);
  if (diagnosticsJson) {
    std::cout << crossgl::diagnosticsToJson(result.diagnostics);
  }
  if (!result.success) {
    return 1;
  }

  if (!diagnosticsJson) {
    std::cout << "built " << result.artifactPath.string() << " for "
              << crossgl::targetName(result.resolvedTarget) << "\n";
  }
  return 0;
}

struct ParsedMaintenanceOptions {
  bool success = false;
  int exitCode = 2;
  crossgl::PackageStaleSidecarCleanupOptions options;
};

ParsedMaintenanceOptions parsePackageMaintenanceOptions(
    const std::vector<std::string> &args,
    const std::optional<std::filesystem::path> &policyPath,
    std::string_view commandLabel) {
  const bool dryRun = hasArg(args, "--dry-run");
  const bool apply = hasArg(args, "--apply");
  std::optional<std::size_t> keepLast;
  std::optional<std::uint64_t> olderThanSeconds;
  ParsedMaintenanceOptions parsed;
  if (dryRun && apply) {
    std::cerr << "error: " << commandLabel
              << " accepts only one of --dry-run or --apply\n";
    return parsed;
  }
  if (hasArg(args, "--keep-last")) {
    keepLast = optionalSizeArg(args, "--keep-last");
    if (!keepLast) {
      std::cerr << "error: " << commandLabel
                << " --keep-last requires a non-negative integer\n";
      return parsed;
    }
  }
  if (hasArg(args, "--older-than")) {
    olderThanSeconds = optionalDurationSecondsArg(args, "--older-than");
    if (!olderThanSeconds) {
      std::cerr << "error: " << commandLabel
                << " --older-than requires a duration\n";
      return parsed;
    }
  }

  if (policyPath) {
    crossgl::PackageMaintenancePolicyResult policy =
        crossgl::loadPackageMaintenancePolicy(*policyPath);
    if (!policy.success) {
      printDiagnostics(policy.diagnostics);
      return parsed;
    }
    parsed.options.keepLast = policy.options.keepLast;
    parsed.options.olderThanSeconds = policy.options.olderThanSeconds;
  }
  parsed.options.dryRun = !apply;
  if (keepLast) {
    parsed.options.keepLast = keepLast;
  }
  if (olderThanSeconds) {
    parsed.options.olderThanSeconds = olderThanSeconds;
  }
  parsed.success = true;
  parsed.exitCode = 0;
  return parsed;
}

int commandPackageStaleSidecarCleanup(
    const std::vector<std::string> &args, const std::string &packagePath,
    const std::optional<std::filesystem::path> &policyPath,
    std::string_view commandLabel) {
  const bool jsonOutput = hasArg(args, "--json");
  ParsedMaintenanceOptions parsed =
      parsePackageMaintenanceOptions(args, policyPath, commandLabel);
  if (!parsed.success) {
    return parsed.exitCode;
  }
  crossgl::PackageStaleSidecarCleanupResult result =
      crossgl::cleanupStalePackageSidecars(packagePath, parsed.options);
  if (jsonOutput) {
    std::cout << crossgl::packageStaleSidecarCleanupJson(result);
  } else {
    printDiagnostics(result.diagnostics);
    std::cout << crossgl::packageStaleSidecarCleanupText(result);
  }
  return result.success ? 0 : 1;
}

int commandPackageMaintenanceScan(
    const std::vector<std::string> &args, const std::filesystem::path &scanPath,
    const std::optional<std::filesystem::path> &policyPath,
    const std::optional<std::filesystem::path> &exportPackageSetPath,
    const std::optional<std::filesystem::path> &verifyPackageSetPath) {
  const bool jsonOutput = hasArg(args, "--json");
  if (exportPackageSetPath && verifyPackageSetPath) {
    std::cerr << "error: package maintain --scan accepts only one of "
                 "--export-package-set or --verify-package-set\n";
    return 2;
  }
  if (exportPackageSetPath) {
    if (hasArg(args, "--dry-run") || hasArg(args, "--apply") ||
        hasArg(args, "--keep-last") || hasArg(args, "--older-than") ||
        policyPath) {
      std::cerr << "error: package maintain --scan --export-package-set does "
                   "not accept --dry-run, --apply, --keep-last, "
                   "--older-than, or --policy\n";
      return 2;
    }

    crossgl::PackageMaintenanceSetExportResult result =
        crossgl::exportPackageMaintenanceSetFromScan(scanPath,
                                                     *exportPackageSetPath);
    if (jsonOutput && result.success) {
      std::cout << crossgl::packageMaintenanceSetDocumentJson(
          result.packagePaths,
          crossgl::packageParentPath(*exportPackageSetPath));
    } else {
      printDiagnostics(result.diagnostics);
      if (result.success) {
        std::cout << crossgl::packageMaintenanceSetExportText(result);
      }
    }
    return result.success ? 0 : 1;
  }
  if (verifyPackageSetPath) {
    if (hasArg(args, "--dry-run") || hasArg(args, "--apply") ||
        hasArg(args, "--keep-last") || hasArg(args, "--older-than") ||
        policyPath) {
      std::cerr << "error: package maintain --scan --verify-package-set does "
                   "not accept --dry-run, --apply, --keep-last, "
                   "--older-than, or --policy\n";
      return 2;
    }

    crossgl::PackageMaintenanceSetVerificationResult result =
        crossgl::verifyPackageMaintenanceSetFromScan(scanPath,
                                                     *verifyPackageSetPath);
    if (jsonOutput) {
      std::cout << crossgl::packageMaintenanceSetVerificationJson(result);
    } else {
      printDiagnostics(result.diagnostics);
      std::cout << crossgl::packageMaintenanceSetVerificationText(result);
    }
    return result.success ? 0 : 1;
  }

  ParsedMaintenanceOptions parsed = parsePackageMaintenanceOptions(
      args, policyPath, "package maintain --scan");
  if (!parsed.success) {
    return parsed.exitCode;
  }
  crossgl::PackageMaintenanceScanResult result =
      crossgl::scanPackageMaintenanceDirectory(scanPath, parsed.options);
  if (jsonOutput) {
    std::cout << crossgl::packageMaintenanceScanJson(result);
  } else {
    printDiagnostics(result.diagnostics);
    std::cout << crossgl::packageMaintenanceScanText(result);
  }
  return result.success ? 0 : 1;
}

int commandPackageMaintenanceSet(
    const std::vector<std::string> &args, const std::filesystem::path &setPath,
    const std::optional<std::filesystem::path> &policyPath) {
  const bool jsonOutput = hasArg(args, "--json");
  ParsedMaintenanceOptions parsed = parsePackageMaintenanceOptions(
      args, policyPath, "package maintain --package-set");
  if (!parsed.success) {
    return parsed.exitCode;
  }
  crossgl::PackageMaintenanceSetResult result =
      crossgl::maintainPackageSet(setPath, parsed.options);
  if (jsonOutput) {
    std::cout << crossgl::packageMaintenanceSetJson(result);
  } else {
    printDiagnostics(result.diagnostics);
    std::cout << crossgl::packageMaintenanceSetText(result);
  }
  return result.success ? 0 : 1;
}

int commandPackageMaintenanceSetVerificationBatchExport(
    const std::vector<std::string> &args,
    const std::filesystem::path &batchPath,
    const std::vector<crossgl::PackageMaintenanceSetVerificationBatchEntry>
        &entries,
    const std::optional<std::filesystem::path> &policyPath) {
  const bool jsonOutput = hasArg(args, "--json");
  if (hasArg(args, "--dry-run") || hasArg(args, "--apply") ||
      hasArg(args, "--keep-last") || hasArg(args, "--older-than") ||
      policyPath) {
    std::cerr << "error: package maintain "
                 "--export-package-set-verification-batch does not accept "
                 "--dry-run, --apply, --keep-last, --older-than, or "
                 "--policy\n";
    return 2;
  }

  crossgl::PackageMaintenanceSetVerificationBatchExportResult result =
      crossgl::exportPackageMaintenanceSetVerificationBatch(batchPath, entries);
  if (jsonOutput && result.success) {
    std::cout << crossgl::packageMaintenanceSetVerificationBatchDocumentJson(
        result.entries, crossgl::packageParentPath(batchPath));
  } else {
    printDiagnostics(result.diagnostics);
    if (result.success) {
      std::cout << crossgl::packageMaintenanceSetVerificationBatchExportText(
          result);
    }
  }
  return result.success ? 0 : 1;
}

int commandPackageMaintenanceSetVerificationBatch(
    const std::vector<std::string> &args,
    const std::filesystem::path &batchPath,
    const std::optional<std::filesystem::path> &summaryOutputPath,
    const std::optional<std::filesystem::path> &policyPath) {
  const bool jsonOutput = hasArg(args, "--json");
  if (hasArg(args, "--dry-run") || hasArg(args, "--apply") ||
      hasArg(args, "--keep-last") || hasArg(args, "--older-than") ||
      policyPath) {
    std::cerr << "error: package maintain --verify-package-set-batch does "
                 "not accept --dry-run, --apply, --keep-last, "
                 "--older-than, or --policy\n";
    return 2;
  }

  crossgl::PackageMaintenanceSetVerificationBatchResult result =
      crossgl::verifyPackageMaintenanceSetsFromBatch(batchPath);
  std::optional<
      crossgl::PackageMaintenanceSetVerificationBatchSummaryExportResult>
      summaryExport;
  if (summaryOutputPath) {
    summaryExport =
        crossgl::exportPackageMaintenanceSetVerificationBatchSummary(
            result, *summaryOutputPath);
  }
  if (jsonOutput) {
    std::cout << crossgl::packageMaintenanceSetVerificationBatchJson(result);
  } else {
    printDiagnostics(result.diagnostics);
    std::cout << crossgl::packageMaintenanceSetVerificationBatchText(result);
    if (summaryExport && summaryExport->success) {
      std::cout
          << crossgl::packageMaintenanceSetVerificationBatchSummaryExportText(
                 *summaryExport);
    }
  }
  if (summaryExport && !summaryExport->success) {
    printDiagnostics(summaryExport->diagnostics);
  }
  return result.success && (!summaryExport || summaryExport->success) ? 0 : 1;
}

int commandPackageReleasePromotion(
    const std::vector<std::string> &args,
    const std::optional<std::filesystem::path> &summaryPath,
    const std::optional<std::filesystem::path> &manifestPath,
    const std::optional<std::filesystem::path> &bundlePath,
    const std::optional<std::filesystem::path> &policyPath,
    const std::optional<std::filesystem::path> &sourcePath,
    const std::string &packagePath) {
  const bool jsonOutput = hasArg(args, "--json");
  for (std::size_t index = 2; index < args.size(); ++index) {
    if (args[index] == "--promotion-summary" ||
        args[index] == "--manifest-output" ||
        args[index] == "--bundle-output") {
      ++index;
      continue;
    }
    if (args[index] == "--json") {
      continue;
    }
    if (!args[index].empty() && args[index][0] == '-') {
      std::cerr << "error: package release accepts only --promotion-summary, "
                   "--manifest-output, --bundle-output, and --json\n";
      return 2;
    }
  }
  if (!packagePath.empty() || sourcePath || policyPath ||
      hasArg(args, "--dry-run") || hasArg(args, "--apply") ||
      hasArg(args, "--keep-last") || hasArg(args, "--older-than") ||
      hasArg(args, "--list") || hasArg(args, "--discard-stale") ||
      hasArg(args, "--promote") || hasArg(args, "--discard") ||
      hasArg(args, "--replace") || hasArg(args, "--summary-output")) {
    std::cerr << "error: package release accepts only --promotion-summary, "
                 "--manifest-output, --bundle-output, and --json\n";
    return 2;
  }
  if (!summaryPath) {
    std::cerr << "error: package release requires --promotion-summary\n";
    return 2;
  }
  if (!manifestPath) {
    std::cerr << "error: package release requires --manifest-output\n";
    return 2;
  }

  crossgl::PackageReleasePromotionManifestResult result =
      crossgl::exportPackageReleasePromotionManifest(*summaryPath,
                                                     *manifestPath);
  std::optional<crossgl::PackageReleaseBundleManifestResult> bundle;
  if (bundlePath && result.manifestWritten) {
    bundle = crossgl::exportPackageReleaseBundleManifest(result, *bundlePath);
  }

  std::vector<crossgl::Diagnostic> diagnostics = result.diagnostics;
  if (bundle) {
    diagnostics.insert(diagnostics.end(), bundle->diagnostics.begin(),
                       bundle->diagnostics.end());
  }

  if (jsonOutput && diagnostics.empty()) {
    std::cout << crossgl::packageReleasePromotionManifestJson(result);
  } else {
    printDiagnostics(diagnostics);
    if (diagnostics.empty()) {
      std::cout << crossgl::packageReleasePromotionManifestText(result);
      if (bundle) {
        std::cout << crossgl::packageReleaseBundleManifestText(*bundle);
      }
    }
  }
  if (!diagnostics.empty()) {
    return 1;
  }
  return result.releaseEligible && (!bundle || bundle->success) ? 0 : 1;
}

int commandPackageReleaseBundleVerification(
    const std::vector<std::string> &args,
    const std::filesystem::path &bundlePath,
    const std::optional<std::filesystem::path> &summaryPath,
    const std::optional<std::filesystem::path> &manifestPath,
    const std::optional<std::filesystem::path> &bundleOutputPath,
    const std::optional<std::filesystem::path> &policyPath,
    const std::optional<std::filesystem::path> &sourcePath,
    const std::string &packagePath) {
  const bool jsonOutput = hasArg(args, "--json");
  for (std::size_t index = 2; index < args.size(); ++index) {
    if (args[index] == "--verify-bundle") {
      ++index;
      continue;
    }
    if (args[index] == "--json") {
      continue;
    }
    if (!args[index].empty() && args[index][0] == '-') {
      std::cerr << "error: package release --verify-bundle accepts only "
                   "--verify-bundle and --json\n";
      return 2;
    }
  }
  if (!packagePath.empty() || sourcePath || policyPath || summaryPath ||
      manifestPath || bundleOutputPath || hasArg(args, "--dry-run") ||
      hasArg(args, "--apply") || hasArg(args, "--keep-last") ||
      hasArg(args, "--older-than") || hasArg(args, "--list") ||
      hasArg(args, "--discard-stale") || hasArg(args, "--promote") ||
      hasArg(args, "--discard") || hasArg(args, "--replace") ||
      hasArg(args, "--summary-output")) {
    std::cerr << "error: package release --verify-bundle accepts only "
                 "--verify-bundle and --json\n";
    return 2;
  }

  crossgl::PackageReleaseBundleVerificationResult result =
      crossgl::verifyPackageReleaseBundleManifest(bundlePath);
  if (jsonOutput) {
    std::cout << crossgl::packageReleaseBundleVerificationJson(result);
  } else {
    printDiagnostics(result.diagnostics);
    std::cout << crossgl::packageReleaseBundleVerificationText(result);
  }
  return result.success ? 0 : 1;
}

int commandPackageReleasePublishPlan(
    const std::vector<std::string> &args,
    const std::filesystem::path &bundlePath,
    const std::optional<std::filesystem::path> &planPath,
    const std::optional<std::filesystem::path> &summaryPath,
    const std::optional<std::filesystem::path> &manifestPath,
    const std::optional<std::filesystem::path> &bundleOutputPath,
    const std::optional<std::filesystem::path> &verifyBundlePath,
    const std::optional<std::filesystem::path> &policyPath,
    const std::optional<std::filesystem::path> &sourcePath,
    const std::string &packagePath) {
  const bool jsonOutput = hasArg(args, "--json");
  for (std::size_t index = 2; index < args.size(); ++index) {
    if (args[index] == "--plan-publish" || args[index] == "--plan-output") {
      ++index;
      continue;
    }
    if (args[index] == "--json") {
      continue;
    }
    if (!args[index].empty() && args[index][0] == '-') {
      std::cerr << "error: package release --plan-publish accepts only "
                   "--plan-publish, --plan-output, and --json\n";
      return 2;
    }
  }
  if (!packagePath.empty() || sourcePath || policyPath || summaryPath ||
      manifestPath || bundleOutputPath || verifyBundlePath ||
      hasArg(args, "--dry-run") || hasArg(args, "--apply") ||
      hasArg(args, "--keep-last") || hasArg(args, "--older-than") ||
      hasArg(args, "--list") || hasArg(args, "--discard-stale") ||
      hasArg(args, "--promote") || hasArg(args, "--discard") ||
      hasArg(args, "--replace") || hasArg(args, "--summary-output")) {
    std::cerr << "error: package release --plan-publish accepts only "
                 "--plan-publish, --plan-output, and --json\n";
    return 2;
  }
  if (!planPath) {
    std::cerr << "error: package release --plan-publish requires "
                 "--plan-output\n";
    return 2;
  }

  crossgl::PackageReleasePublishPlanResult result =
      crossgl::exportPackageReleasePublishPlan(bundlePath, *planPath);
  if (jsonOutput && result.success) {
    std::cout << crossgl::packageReleasePublishPlanJson(result);
  } else {
    printDiagnostics(result.diagnostics);
    if (result.success) {
      std::cout << crossgl::packageReleasePublishPlanText(result);
    } else if (!jsonOutput && result.diagnostics.empty()) {
      std::cout << crossgl::packageReleaseBundleVerificationText(
          result.verification);
    }
  }
  return result.success ? 0 : 1;
}

int commandPackageReleasePublishStage(
    const std::vector<std::string> &args, const std::filesystem::path &planPath,
    const std::optional<std::filesystem::path> &stagePath,
    const std::optional<std::filesystem::path> &summaryPath,
    const std::optional<std::filesystem::path> &manifestPath,
    const std::optional<std::filesystem::path> &bundleOutputPath,
    const std::optional<std::filesystem::path> &verifyBundlePath,
    const std::optional<std::filesystem::path> &planPublishPath,
    const std::optional<std::filesystem::path> &planOutputPath,
    const std::optional<std::filesystem::path> &policyPath,
    const std::optional<std::filesystem::path> &sourcePath,
    const std::string &packagePath) {
  const bool jsonOutput = hasArg(args, "--json");
  for (std::size_t index = 2; index < args.size(); ++index) {
    if (args[index] == "--stage-publish" || args[index] == "--stage-output") {
      ++index;
      continue;
    }
    if (args[index] == "--json") {
      continue;
    }
    if (!args[index].empty() && args[index][0] == '-') {
      std::cerr << "error: package release --stage-publish accepts only "
                   "--stage-publish, --stage-output, and --json\n";
      return 2;
    }
  }
  if (!packagePath.empty() || sourcePath || policyPath || summaryPath ||
      manifestPath || bundleOutputPath || verifyBundlePath || planPublishPath ||
      planOutputPath || hasArg(args, "--dry-run") || hasArg(args, "--apply") ||
      hasArg(args, "--keep-last") || hasArg(args, "--older-than") ||
      hasArg(args, "--list") || hasArg(args, "--discard-stale") ||
      hasArg(args, "--promote") || hasArg(args, "--discard") ||
      hasArg(args, "--replace") || hasArg(args, "--summary-output")) {
    std::cerr << "error: package release --stage-publish accepts only "
                 "--stage-publish, --stage-output, and --json\n";
    return 2;
  }
  if (!stagePath) {
    std::cerr << "error: package release --stage-publish requires "
                 "--stage-output\n";
    return 2;
  }

  crossgl::PackageReleasePublishStageResult result =
      crossgl::stagePackageReleasePublishPlan(planPath, *stagePath);
  if (jsonOutput) {
    std::cout << crossgl::packageReleasePublishStageJson(result);
  } else {
    printDiagnostics(result.diagnostics);
    std::cout << crossgl::packageReleasePublishStageText(result);
  }
  return result.success ? 0 : 1;
}

int commandPackageReleaseReportArtifactInventory(
    const std::vector<std::string> &args,
    const crossgl::PackageReleaseReportArtifactInventoryOptions &options) {
  const bool jsonOutput = hasArg(args, "--json");
  for (std::size_t index = 2; index < args.size(); ++index) {
    if (args[index] == "--report-bundle" ||
        args[index] == "--report-publish-plan" ||
        args[index] == "--report-publish-stage") {
      ++index;
      continue;
    }
    if (args[index] == "--report-artifact-inventory" ||
        args[index] == "--json") {
      continue;
    }
    if (!args[index].empty() && args[index][0] == '-') {
      std::cerr
          << "error: package release --report-artifact-inventory accepts only "
             "--report-artifact-inventory, --report-bundle, "
             "--report-publish-plan, --report-publish-stage, and --json\n";
      return 2;
    }
  }
  if (!options.bundlePath && !options.publishPlanPath &&
      !options.stageReportPath) {
    std::cerr << "error: package release --report-artifact-inventory requires "
                 "at least one report input\n";
    return 2;
  }

  crossgl::PackageReleaseReportArtifactInventoryResult result =
      crossgl::loadPackageReleaseReportArtifactInventory(options);
  if (jsonOutput) {
    std::cout << crossgl::packageReleaseReportArtifactInventoryJson(result);
  } else {
    printDiagnostics(result.diagnostics);
    std::cout << crossgl::packageReleaseReportArtifactInventoryText(result);
  }
  return result.success ? 0 : 1;
}

int commandPackageReleaseUploadPreflight(
    const std::vector<std::string> &args,
    const std::filesystem::path &uploadManifestPath,
    const std::optional<std::filesystem::path> &uploadReportOutputPath,
    const std::optional<std::filesystem::path> &summaryPath,
    const std::optional<std::filesystem::path> &manifestPath,
    const std::optional<std::filesystem::path> &bundleOutputPath,
    const std::optional<std::filesystem::path> &verifyBundlePath,
    const std::optional<std::filesystem::path> &planPublishPath,
    const std::optional<std::filesystem::path> &planOutputPath,
    const std::optional<std::filesystem::path> &stagePublishPath,
    const std::optional<std::filesystem::path> &stageOutputPath,
    const std::optional<std::filesystem::path> &publishStagePath,
    const std::optional<std::string> &publishTarget,
    const std::optional<std::filesystem::path> &targetOutputPath,
    const std::optional<std::filesystem::path> &targetDescriptorPath,
    const std::optional<std::filesystem::path> &receiptOutputPath,
    const std::optional<std::filesystem::path> &uploadManifestOutputPath,
    const std::optional<std::filesystem::path> &policyPath,
    const std::optional<std::filesystem::path> &sourcePath,
    const std::string &packagePath) {
  const bool jsonOutput = hasArg(args, "--json");
  const bool dryRun = hasArg(args, "--dry-run");
  for (std::size_t index = 2; index < args.size(); ++index) {
    if (args[index] == "--upload-manifest" ||
        args[index] == "--upload-report-output") {
      ++index;
      continue;
    }
    if (args[index] == "--json" || args[index] == "--dry-run") {
      continue;
    }
    if (!args[index].empty() && args[index][0] == '-') {
      std::cerr << "error: package release --upload-manifest accepts only "
                   "--upload-manifest, --upload-report-output, --dry-run, "
                   "and --json\n";
      return 2;
    }
  }
  if (!packagePath.empty() || sourcePath || policyPath || summaryPath ||
      manifestPath || bundleOutputPath || verifyBundlePath || planPublishPath ||
      planOutputPath || stagePublishPath || stageOutputPath ||
      publishStagePath || publishTarget || targetOutputPath ||
      targetDescriptorPath || receiptOutputPath || uploadManifestOutputPath ||
      hasArg(args, "--apply") || hasArg(args, "--keep-last") ||
      hasArg(args, "--older-than") || hasArg(args, "--list") ||
      hasArg(args, "--discard-stale") || hasArg(args, "--promote") ||
      hasArg(args, "--discard") || hasArg(args, "--replace") ||
      hasArg(args, "--summary-output")) {
    std::cerr << "error: package release --upload-manifest accepts only "
                 "--upload-manifest, --upload-report-output, --dry-run, "
                 "and --json\n";
    return 2;
  }
  if (!dryRun) {
    std::cerr << "error: package release --upload-manifest requires "
                 "--dry-run, --mock-upload, or --gcs-upload\n";
    return 2;
  }

  crossgl::PackageReleasePublishUploadPreflightOptions options;
  options.reportPath = uploadReportOutputPath;
  crossgl::PackageReleasePublishUploadPreflightResult result =
      crossgl::preflightPackageReleaseUploadManifest(uploadManifestPath,
                                                     options);
  if (jsonOutput) {
    std::cout << crossgl::packageReleasePublishUploadPreflightJson(result);
  } else {
    printDiagnostics(result.diagnostics);
    std::cout << crossgl::packageReleasePublishUploadPreflightText(result);
  }
  return result.success ? 0 : 1;
}

int commandPackageReleaseMockUpload(
    const std::vector<std::string> &args,
    const std::filesystem::path &uploadManifestPath,
    const std::optional<std::filesystem::path> &uploadReportOutputPath,
    const std::optional<std::filesystem::path> &uploadReceiptOutputPath,
    const std::optional<std::filesystem::path> &summaryPath,
    const std::optional<std::filesystem::path> &manifestPath,
    const std::optional<std::filesystem::path> &bundleOutputPath,
    const std::optional<std::filesystem::path> &verifyBundlePath,
    const std::optional<std::filesystem::path> &planPublishPath,
    const std::optional<std::filesystem::path> &planOutputPath,
    const std::optional<std::filesystem::path> &stagePublishPath,
    const std::optional<std::filesystem::path> &stageOutputPath,
    const std::optional<std::filesystem::path> &publishStagePath,
    const std::optional<std::string> &publishTarget,
    const std::optional<std::filesystem::path> &targetOutputPath,
    const std::optional<std::filesystem::path> &targetDescriptorPath,
    const std::optional<std::filesystem::path> &receiptOutputPath,
    const std::optional<std::filesystem::path> &uploadManifestOutputPath,
    const std::optional<std::filesystem::path> &policyPath,
    const std::optional<std::filesystem::path> &sourcePath,
    const std::string &packagePath) {
  const bool jsonOutput = hasArg(args, "--json");
  for (std::size_t index = 2; index < args.size(); ++index) {
    if (args[index] == "--upload-manifest" ||
        args[index] == "--upload-report-output" ||
        args[index] == "--upload-receipt-output") {
      ++index;
      continue;
    }
    if (args[index] == "--json" || args[index] == "--mock-upload") {
      continue;
    }
    if (!args[index].empty() && args[index][0] == '-') {
      std::cerr << "error: package release --upload-manifest --mock-upload "
                   "accepts only --upload-manifest, --upload-report-output, "
                   "--upload-receipt-output, --mock-upload, and --json\n";
      return 2;
    }
  }
  if (!packagePath.empty() || sourcePath || policyPath || summaryPath ||
      manifestPath || bundleOutputPath || verifyBundlePath || planPublishPath ||
      planOutputPath || stagePublishPath || stageOutputPath ||
      publishStagePath || publishTarget || targetOutputPath ||
      targetDescriptorPath || receiptOutputPath || uploadManifestOutputPath ||
      hasArg(args, "--dry-run") || hasArg(args, "--apply") ||
      hasArg(args, "--keep-last") || hasArg(args, "--older-than") ||
      hasArg(args, "--list") || hasArg(args, "--discard-stale") ||
      hasArg(args, "--promote") || hasArg(args, "--discard") ||
      hasArg(args, "--replace") || hasArg(args, "--summary-output")) {
    std::cerr << "error: package release --upload-manifest --mock-upload "
                 "accepts only --upload-manifest, --upload-report-output, "
                 "--upload-receipt-output, --mock-upload, and --json\n";
    return 2;
  }

  crossgl::PackageReleasePublishUploadBatchOptions options;
  options.reportPath = uploadReportOutputPath;
  options.receiptPath = uploadReceiptOutputPath;
  options.uploadMode = "mock";
  MockPackageReleasePublishUploader uploader;
  crossgl::PackageReleasePublishUploadBatchResult result =
      crossgl::uploadPackageReleaseManifest(uploadManifestPath, options,
                                            uploader);
  if (jsonOutput) {
    std::cout << crossgl::packageReleasePublishUploadBatchJson(result);
  } else {
    printDiagnostics(result.diagnostics);
    std::cout << crossgl::packageReleasePublishUploadBatchText(result);
  }
  return result.success ? 0 : 1;
}

int commandPackageReleaseGcsUpload(
    const std::vector<std::string> &args,
    const std::filesystem::path &uploadManifestPath,
    const std::optional<std::filesystem::path> &uploadReportOutputPath,
    const std::optional<std::filesystem::path> &uploadReceiptOutputPath,
    bool gcsUploadOverwrite,
    const std::optional<std::filesystem::path> &summaryPath,
    const std::optional<std::filesystem::path> &manifestPath,
    const std::optional<std::filesystem::path> &bundleOutputPath,
    const std::optional<std::filesystem::path> &verifyBundlePath,
    const std::optional<std::filesystem::path> &planPublishPath,
    const std::optional<std::filesystem::path> &planOutputPath,
    const std::optional<std::filesystem::path> &stagePublishPath,
    const std::optional<std::filesystem::path> &stageOutputPath,
    const std::optional<std::filesystem::path> &publishStagePath,
    const std::optional<std::string> &publishTarget,
    const std::optional<std::filesystem::path> &targetOutputPath,
    const std::optional<std::filesystem::path> &targetDescriptorPath,
    const std::optional<std::filesystem::path> &receiptOutputPath,
    const std::optional<std::filesystem::path> &uploadManifestOutputPath,
    const std::optional<std::filesystem::path> &policyPath,
    const std::optional<std::filesystem::path> &sourcePath,
    const std::string &packagePath) {
  const bool jsonOutput = hasArg(args, "--json");
  for (std::size_t index = 2; index < args.size(); ++index) {
    if (args[index] == "--upload-manifest" ||
        args[index] == "--upload-report-output" ||
        args[index] == "--upload-receipt-output") {
      ++index;
      continue;
    }
    if (args[index] == "--json" || args[index] == "--gcs-upload" ||
        args[index] == "--gcs-upload-overwrite") {
      continue;
    }
    if (!args[index].empty() && args[index][0] == '-') {
      std::cerr << "error: package release --upload-manifest --gcs-upload "
                   "accepts only --upload-manifest, --upload-report-output, "
                   "--upload-receipt-output, --gcs-upload, "
                   "--gcs-upload-overwrite, and --json\n";
      return 2;
    }
  }
  if (!packagePath.empty() || sourcePath || policyPath || summaryPath ||
      manifestPath || bundleOutputPath || verifyBundlePath || planPublishPath ||
      planOutputPath || stagePublishPath || stageOutputPath ||
      publishStagePath || publishTarget || targetOutputPath ||
      targetDescriptorPath || receiptOutputPath || uploadManifestOutputPath ||
      hasArg(args, "--dry-run") || hasArg(args, "--mock-upload") ||
      hasArg(args, "--apply") || hasArg(args, "--keep-last") ||
      hasArg(args, "--older-than") || hasArg(args, "--list") ||
      hasArg(args, "--discard-stale") || hasArg(args, "--promote") ||
      hasArg(args, "--discard") || hasArg(args, "--replace") ||
      hasArg(args, "--summary-output")) {
    std::cerr << "error: package release --upload-manifest --gcs-upload "
                 "accepts only --upload-manifest, --upload-report-output, "
                 "--upload-receipt-output, --gcs-upload, "
                 "--gcs-upload-overwrite, and --json\n";
    return 2;
  }

  crossgl::PackageReleasePublishUploadBatchOptions options;
  options.reportPath = uploadReportOutputPath;
  options.receiptPath = uploadReceiptOutputPath;
  options.uploadMode = "gcs";
  GcsPackageReleasePublishUploader uploader(
      gcsUploadOverwrite, uploadReceiptOutputPath.has_value());
  crossgl::PackageReleasePublishUploadBatchResult result =
      crossgl::uploadPackageReleaseManifest(uploadManifestPath, options,
                                            uploader);
  if (jsonOutput) {
    std::cout << crossgl::packageReleasePublishUploadBatchJson(result);
  } else {
    printDiagnostics(result.diagnostics);
    std::cout << crossgl::packageReleasePublishUploadBatchText(result);
  }
  return result.success ? 0 : 1;
}

int commandPackageReleasePublishReceipt(
    const std::vector<std::string> &args,
    const std::filesystem::path &stageReportPath,
    const std::optional<std::string> &publishTarget,
    const std::optional<std::filesystem::path> &targetOutputPath,
    const std::optional<std::filesystem::path> &targetDescriptorPath,
    const std::optional<std::filesystem::path> &receiptOutputPath,
    const std::optional<std::filesystem::path> &uploadManifestOutputPath,
    const std::optional<std::filesystem::path> &summaryPath,
    const std::optional<std::filesystem::path> &manifestPath,
    const std::optional<std::filesystem::path> &bundleOutputPath,
    const std::optional<std::filesystem::path> &verifyBundlePath,
    const std::optional<std::filesystem::path> &planPublishPath,
    const std::optional<std::filesystem::path> &planOutputPath,
    const std::optional<std::filesystem::path> &stagePublishPath,
    const std::optional<std::filesystem::path> &stageOutputPath,
    const std::optional<std::filesystem::path> &policyPath,
    const std::optional<std::filesystem::path> &sourcePath,
    const std::string &packagePath) {
  const bool jsonOutput = hasArg(args, "--json");
  const bool dryRun = hasArg(args, "--dry-run");
  for (std::size_t index = 2; index < args.size(); ++index) {
    if (args[index] == "--publish-stage" || args[index] == "--publish-target" ||
        args[index] == "--target-output" ||
        args[index] == "--target-descriptor" ||
        args[index] == "--receipt-output" ||
        args[index] == "--upload-manifest-output") {
      ++index;
      continue;
    }
    if (args[index] == "--json" || args[index] == "--dry-run") {
      continue;
    }
    if (!args[index].empty() && args[index][0] == '-') {
      std::cerr << "error: package release --publish-stage accepts only "
                   "--publish-stage, --publish-target, --target-output, "
                   "--target-descriptor, --receipt-output, "
                   "--upload-manifest-output, --dry-run, and --json\n";
      return 2;
    }
  }
  if (!packagePath.empty() || sourcePath || policyPath || summaryPath ||
      manifestPath || bundleOutputPath || verifyBundlePath || planPublishPath ||
      planOutputPath || stagePublishPath || stageOutputPath ||
      hasArg(args, "--apply") || hasArg(args, "--keep-last") ||
      hasArg(args, "--older-than") || hasArg(args, "--list") ||
      hasArg(args, "--discard-stale") || hasArg(args, "--promote") ||
      hasArg(args, "--discard") || hasArg(args, "--replace") ||
      hasArg(args, "--summary-output")) {
    std::cerr << "error: package release --publish-stage accepts only "
                 "--publish-stage, --publish-target, --target-output, "
                 "--target-descriptor, --receipt-output, "
                 "--upload-manifest-output, --dry-run, and --json\n";
    return 2;
  }
  if (!publishTarget) {
    std::cerr << "error: package release --publish-stage requires "
                 "--publish-target\n";
    return 2;
  }
  if (!targetOutputPath && !targetDescriptorPath) {
    std::cerr << "error: package release --publish-stage requires "
                 "--target-output or --target-descriptor\n";
    return 2;
  }

  crossgl::PackageReleasePublishOptions options;
  options.targetKind = *publishTarget;
  options.targetPath = targetOutputPath.value_or(std::filesystem::path{});
  options.targetDescriptorPath = targetDescriptorPath;
  options.receiptPath = receiptOutputPath;
  options.uploadManifestPath = uploadManifestOutputPath;
  options.dryRun = dryRun;
  crossgl::PackageReleasePublishReceiptResult result =
      crossgl::publishPackageReleaseStage(stageReportPath, options);
  if (jsonOutput) {
    std::cout << crossgl::packageReleasePublishReceiptJson(result);
  } else {
    printDiagnostics(result.diagnostics);
    std::cout << crossgl::packageReleasePublishReceiptText(result);
  }
  return result.success ? 0 : 1;
}

int commandPackage(const std::vector<std::string> &args) {
  if (args.size() < 2 || args[1] == "--help" || args[1] == "-h") {
    printUsage();
    return 2;
  }

  const std::string subcommand = args[1];
  if (subcommand != "inspect" && subcommand != "verify" &&
      subcommand != "recover" && subcommand != "release" &&
      subcommand != "maintain") {
    std::cerr << "unknown package command: " << args[1] << "\n";
    printUsage();
    return 2;
  }

  if (subcommand == "inspect" && !hasArg(args, "--json")) {
    std::cerr << "error: package inspect currently requires --json\n";
    return 2;
  }

  std::string packagePath;
  std::optional<std::filesystem::path> sourcePath;
  std::optional<std::filesystem::path> policyPath;
  std::optional<std::filesystem::path> scanPath;
  std::optional<std::filesystem::path> packageSetPath;
  std::optional<std::filesystem::path> exportPackageSetPath;
  std::optional<std::filesystem::path> verifyPackageSetPath;
  std::optional<std::filesystem::path> exportPackageSetVerificationBatchPath;
  std::optional<std::filesystem::path> verifyPackageSetBatchPath;
  std::optional<std::filesystem::path> summaryOutputPath;
  std::optional<std::filesystem::path> promotionSummaryPath;
  std::optional<std::filesystem::path> manifestOutputPath;
  std::optional<std::filesystem::path> bundleOutputPath;
  std::optional<std::filesystem::path> verifyBundlePath;
  std::optional<std::filesystem::path> planPublishPath;
  std::optional<std::filesystem::path> planOutputPath;
  std::optional<std::filesystem::path> stagePublishPath;
  std::optional<std::filesystem::path> stageOutputPath;
  std::optional<std::filesystem::path> reportBundlePath;
  std::optional<std::filesystem::path> reportPublishPlanPath;
  std::optional<std::filesystem::path> reportPublishStagePath;
  std::optional<std::filesystem::path> publishStagePath;
  std::optional<std::string> publishTarget;
  std::optional<std::filesystem::path> targetOutputPath;
  std::optional<std::filesystem::path> targetDescriptorPath;
  std::optional<std::filesystem::path> receiptOutputPath;
  std::optional<std::filesystem::path> uploadManifestOutputPath;
  std::optional<std::filesystem::path> uploadManifestPath;
  std::optional<std::filesystem::path> uploadReportOutputPath;
  std::optional<std::filesystem::path> uploadReceiptOutputPath;
  bool reportArtifactInventory = false;
  bool mockUpload = false;
  bool gcsUpload = false;
  bool gcsUploadOverwrite = false;
  std::vector<crossgl::PackageMaintenanceSetVerificationBatchEntry>
      exportPackageSetVerificationEntries;
  for (std::size_t index = 2; index < args.size(); ++index) {
    if (args[index] == "--source") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --source requires a path\n";
        return 2;
      }
      sourcePath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--policy") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --policy requires a path\n";
        return 2;
      }
      policyPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--scan") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --scan requires a directory\n";
        return 2;
      }
      scanPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--package-set") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --package-set requires a path\n";
        return 2;
      }
      packageSetPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--export-package-set") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --export-package-set requires a path\n";
        return 2;
      }
      exportPackageSetPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--verify-package-set") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --verify-package-set requires a path\n";
        return 2;
      }
      verifyPackageSetPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--export-package-set-verification-batch") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr
            << "error: --export-package-set-verification-batch requires a "
               "path\n";
        return 2;
      }
      exportPackageSetVerificationBatchPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--verify-package-set-batch") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --verify-package-set-batch requires a path\n";
        return 2;
      }
      verifyPackageSetBatchPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--summary-output") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --summary-output requires a path\n";
        return 2;
      }
      summaryOutputPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--promotion-summary") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --promotion-summary requires a path\n";
        return 2;
      }
      promotionSummaryPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--manifest-output") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --manifest-output requires a path\n";
        return 2;
      }
      manifestOutputPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--bundle-output") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --bundle-output requires a path\n";
        return 2;
      }
      bundleOutputPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--verify-bundle") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --verify-bundle requires a path\n";
        return 2;
      }
      verifyBundlePath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--plan-publish") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --plan-publish requires a path\n";
        return 2;
      }
      planPublishPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--plan-output") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --plan-output requires a path\n";
        return 2;
      }
      planOutputPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--stage-publish") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --stage-publish requires a path\n";
        return 2;
      }
      stagePublishPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--stage-output") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --stage-output requires a path\n";
        return 2;
      }
      stageOutputPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--report-artifact-inventory") {
      reportArtifactInventory = true;
      continue;
    }
    if (args[index] == "--report-bundle") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --report-bundle requires a path\n";
        return 2;
      }
      reportBundlePath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--report-publish-plan") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --report-publish-plan requires a path\n";
        return 2;
      }
      reportPublishPlanPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--report-publish-stage") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --report-publish-stage requires a path\n";
        return 2;
      }
      reportPublishStagePath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--publish-stage") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --publish-stage requires a path\n";
        return 2;
      }
      publishStagePath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--publish-target") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --publish-target requires a target\n";
        return 2;
      }
      publishTarget = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--target-output") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --target-output requires a path\n";
        return 2;
      }
      targetOutputPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--target-descriptor") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --target-descriptor requires a path\n";
        return 2;
      }
      targetDescriptorPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--receipt-output") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --receipt-output requires a path\n";
        return 2;
      }
      receiptOutputPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--upload-manifest-output") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --upload-manifest-output requires a path\n";
        return 2;
      }
      uploadManifestOutputPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--upload-manifest") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --upload-manifest requires a path\n";
        return 2;
      }
      uploadManifestPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--upload-report-output") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --upload-report-output requires a path\n";
        return 2;
      }
      uploadReportOutputPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--upload-receipt-output") {
      if (index + 1 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-') {
        std::cerr << "error: --upload-receipt-output requires a path\n";
        return 2;
      }
      uploadReceiptOutputPath = args[index + 1];
      ++index;
      continue;
    }
    if (args[index] == "--mock-upload") {
      mockUpload = true;
      continue;
    }
    if (args[index] == "--gcs-upload") {
      gcsUpload = true;
      continue;
    }
    if (args[index] == "--gcs-upload-overwrite") {
      gcsUploadOverwrite = true;
      continue;
    }
    if (args[index] == "--verification") {
      if (index + 2 >= args.size() || args[index + 1].empty() ||
          args[index + 1][0] == '-' || args[index + 2].empty() ||
          args[index + 2][0] == '-') {
        std::cerr
            << "error: --verification requires a root path and set path\n";
        return 2;
      }
      crossgl::PackageMaintenanceSetVerificationBatchEntry entry;
      entry.rootPath = args[index + 1];
      entry.setPath = args[index + 2];
      exportPackageSetVerificationEntries.push_back(std::move(entry));
      index += 2;
      continue;
    }
    if (args[index] == "--keep-last") {
      if (index + 1 < args.size()) {
        ++index;
      }
      continue;
    }
    if (args[index] == "--older-than") {
      if (index + 1 < args.size()) {
        ++index;
      }
      continue;
    }
    if (!args[index].empty() && args[index][0] == '-') {
      continue;
    }
    if (packagePath.empty()) {
      packagePath = args[index];
    }
  }
  if (scanPath && subcommand != "maintain") {
    std::cerr << "error: package " << subcommand << " does not accept --scan\n";
    return 2;
  }
  if (packageSetPath && subcommand != "maintain") {
    std::cerr << "error: package " << subcommand
              << " does not accept --package-set\n";
    return 2;
  }
  if (exportPackageSetPath && subcommand != "maintain") {
    std::cerr << "error: package " << subcommand
              << " does not accept --export-package-set\n";
    return 2;
  }
  if (verifyPackageSetPath && subcommand != "maintain") {
    std::cerr << "error: package " << subcommand
              << " does not accept --verify-package-set\n";
    return 2;
  }
  if (exportPackageSetVerificationBatchPath && subcommand != "maintain") {
    std::cerr << "error: package " << subcommand
              << " does not accept "
                 "--export-package-set-verification-batch\n";
    return 2;
  }
  if (verifyPackageSetBatchPath && subcommand != "maintain") {
    std::cerr << "error: package " << subcommand
              << " does not accept --verify-package-set-batch\n";
    return 2;
  }
  if (summaryOutputPath && subcommand != "maintain") {
    std::cerr << "error: package " << subcommand
              << " does not accept --summary-output\n";
    return 2;
  }
  if (promotionSummaryPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --promotion-summary\n";
    return 2;
  }
  if (manifestOutputPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --manifest-output\n";
    return 2;
  }
  if (bundleOutputPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --bundle-output\n";
    return 2;
  }
  if (verifyBundlePath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --verify-bundle\n";
    return 2;
  }
  if (planPublishPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --plan-publish\n";
    return 2;
  }
  if (planOutputPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --plan-output\n";
    return 2;
  }
  if (stagePublishPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --stage-publish\n";
    return 2;
  }
  if (stageOutputPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --stage-output\n";
    return 2;
  }
  if (reportArtifactInventory && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --report-artifact-inventory\n";
    return 2;
  }
  if (reportBundlePath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --report-bundle\n";
    return 2;
  }
  if (reportPublishPlanPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --report-publish-plan\n";
    return 2;
  }
  if (reportPublishStagePath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --report-publish-stage\n";
    return 2;
  }
  if (publishStagePath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --publish-stage\n";
    return 2;
  }
  if (publishTarget && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --publish-target\n";
    return 2;
  }
  if (targetOutputPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --target-output\n";
    return 2;
  }
  if (targetDescriptorPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --target-descriptor\n";
    return 2;
  }
  if (receiptOutputPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --receipt-output\n";
    return 2;
  }
  if (uploadManifestOutputPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --upload-manifest-output\n";
    return 2;
  }
  if (uploadManifestPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --upload-manifest\n";
    return 2;
  }
  if (uploadReportOutputPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --upload-report-output\n";
    return 2;
  }
  if (uploadReceiptOutputPath && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --upload-receipt-output\n";
    return 2;
  }
  if (mockUpload && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --mock-upload\n";
    return 2;
  }
  if (gcsUpload && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --gcs-upload\n";
    return 2;
  }
  if (gcsUploadOverwrite && subcommand != "release") {
    std::cerr << "error: package " << subcommand
              << " does not accept --gcs-upload-overwrite\n";
    return 2;
  }
  if (!exportPackageSetVerificationEntries.empty() &&
      subcommand != "maintain") {
    std::cerr << "error: package " << subcommand
              << " does not accept --verification\n";
    return 2;
  }
  if (subcommand == "maintain" && exportPackageSetPath && !scanPath) {
    std::cerr << "error: package maintain --export-package-set requires "
                 "--scan\n";
    return 2;
  }
  if (subcommand == "maintain" && verifyPackageSetPath && !scanPath) {
    std::cerr << "error: package maintain --verify-package-set requires "
                 "--scan\n";
    return 2;
  }
  if (subcommand == "maintain" &&
      !exportPackageSetVerificationEntries.empty() &&
      !exportPackageSetVerificationBatchPath) {
    std::cerr << "error: package maintain --verification requires "
                 "--export-package-set-verification-batch\n";
    return 2;
  }
  if (subcommand == "maintain" && summaryOutputPath &&
      !verifyPackageSetBatchPath) {
    std::cerr << "error: package maintain --summary-output requires "
                 "--verify-package-set-batch\n";
    return 2;
  }

  if (packagePath.empty() &&
      !(subcommand == "maintain" &&
        (scanPath || packageSetPath || exportPackageSetVerificationBatchPath ||
         verifyPackageSetBatchPath)) &&
      !(subcommand == "release" &&
        (promotionSummaryPath || manifestOutputPath || bundleOutputPath ||
         verifyBundlePath || planPublishPath || planOutputPath ||
         stagePublishPath || stageOutputPath || reportArtifactInventory ||
         reportBundlePath || reportPublishPlanPath || reportPublishStagePath ||
         publishStagePath || publishTarget || targetOutputPath ||
         receiptOutputPath || uploadManifestOutputPath || uploadManifestPath ||
         uploadReportOutputPath || uploadReceiptOutputPath || mockUpload ||
         gcsUpload ||
         gcsUploadOverwrite))) {
    printUsage();
    return 2;
  }

  if (subcommand == "inspect") {
    crossgl::PackageInspectResult result = crossgl::inspectPackage(packagePath);
    if (!result.success) {
      std::cout << result.json;
      return 1;
    }
    std::cout << result.json;
    return 0;
  }

  if (subcommand == "recover") {
    const bool list = hasArg(args, "--list");
    const bool discardStale = hasArg(args, "--discard-stale");
    const bool promote = hasArg(args, "--promote");
    const bool discard = hasArg(args, "--discard");
    const bool jsonOutput = hasArg(args, "--json");
    if (list || discardStale) {
      if (list && discardStale) {
        std::cerr << "error: package recover --list cannot be combined with "
                     "--discard-stale\n";
        return 2;
      }
      if (promote || discard) {
        std::cerr << "error: package recover "
                  << (list ? "--list" : "--discard-stale")
                  << " cannot be combined with --promote or --discard\n";
        return 2;
      }
      if (hasArg(args, "--replace") || sourcePath) {
        std::cerr << "error: package recover "
                  << (list ? "--list" : "--discard-stale")
                  << " does not accept --replace or --source\n";
        return 2;
      }

      if (list) {
        if (hasArg(args, "--dry-run") || hasArg(args, "--apply") ||
            hasArg(args, "--keep-last") || hasArg(args, "--older-than") ||
            policyPath) {
          std::cerr << "error: package recover --list does not accept "
                       "--dry-run, --apply, --keep-last, --older-than, or "
                       "--policy\n";
          return 2;
        }
        crossgl::PackageSidecarListResult result =
            crossgl::listPackageSidecars(packagePath);
        if (jsonOutput) {
          std::cout << crossgl::packageSidecarListJson(result);
        } else {
          printDiagnostics(result.diagnostics);
          std::cout << crossgl::packageSidecarListText(result);
        }
        return result.success ? 0 : 1;
      }

      return commandPackageStaleSidecarCleanup(
          args, packagePath, policyPath, "package recover --discard-stale");
    }

    if (hasArg(args, "--dry-run") || hasArg(args, "--apply") ||
        hasArg(args, "--keep-last") || hasArg(args, "--older-than") ||
        policyPath) {
      std::cerr << "error: package recover --dry-run, --apply, --keep-last, "
                   "--older-than, and --policy require --discard-stale\n";
      return 2;
    }

    if (promote == discard) {
      std::cerr << "error: package recover requires exactly one of --promote "
                   "or --discard\n";
      return 2;
    }

    crossgl::PackageRecoveryOptions options;
    options.action = promote ? crossgl::PackageRecoveryAction::Promote
                             : crossgl::PackageRecoveryAction::Discard;
    options.replace = hasArg(args, "--replace");
    options.sourcePath = sourcePath;
    crossgl::PackageRecoveryResult result =
        crossgl::recoverPackageSidecar(packagePath, options);
    if (jsonOutput) {
      std::cout << crossgl::packageRecoveryJson(result, options);
    } else {
      printDiagnostics(result.diagnostics);
    }
    if (!result.success) {
      return 1;
    }
    if (!jsonOutput) {
      std::cout << result.message << "\n";
    }
    return 0;
  }

  if (subcommand == "release") {
    if (scanPath || packageSetPath || exportPackageSetPath ||
        verifyPackageSetPath || exportPackageSetVerificationBatchPath ||
        verifyPackageSetBatchPath ||
        !exportPackageSetVerificationEntries.empty()) {
      std::cerr << "error: package release does not accept maintenance set "
                   "options\n";
      return 2;
    }
    if ((reportBundlePath || reportPublishPlanPath || reportPublishStagePath) &&
        !reportArtifactInventory) {
      std::cerr << "error: package release report input options require "
                   "--report-artifact-inventory\n";
      return 2;
    }
    if (reportArtifactInventory) {
      if (promotionSummaryPath || manifestOutputPath || bundleOutputPath ||
          verifyBundlePath || planPublishPath || planOutputPath ||
          stagePublishPath || stageOutputPath || publishStagePath ||
          publishTarget || targetOutputPath || targetDescriptorPath ||
          receiptOutputPath || uploadManifestOutputPath || uploadManifestPath ||
          uploadReportOutputPath || uploadReceiptOutputPath || mockUpload ||
          gcsUpload || gcsUploadOverwrite || policyPath || sourcePath ||
          !packagePath.empty()) {
        std::cerr
            << "error: package release --report-artifact-inventory accepts only "
               "--report-artifact-inventory, --report-bundle, "
               "--report-publish-plan, --report-publish-stage, and --json\n";
        return 2;
      }
      crossgl::PackageReleaseReportArtifactInventoryOptions options;
      options.bundlePath = reportBundlePath;
      options.publishPlanPath = reportPublishPlanPath;
      options.stageReportPath = reportPublishStagePath;
      return commandPackageReleaseReportArtifactInventory(args, options);
    }
    if (planOutputPath && !planPublishPath) {
      std::cerr << "error: package release --plan-output requires "
                   "--plan-publish\n";
      return 2;
    }
    if (stageOutputPath && !stagePublishPath) {
      std::cerr << "error: package release --stage-output requires "
                   "--stage-publish\n";
      return 2;
    }
    if (uploadReportOutputPath && !uploadManifestPath) {
      std::cerr << "error: package release --upload-report-output requires "
                   "--upload-manifest\n";
      return 2;
    }
    if (uploadReceiptOutputPath && !uploadManifestPath) {
      std::cerr << "error: package release --upload-receipt-output requires "
                   "--upload-manifest\n";
      return 2;
    }
    if (uploadReceiptOutputPath && !mockUpload && !gcsUpload) {
      std::cerr << "error: package release --upload-receipt-output requires "
                   "--mock-upload or --gcs-upload\n";
      return 2;
    }
    if (mockUpload && !uploadManifestPath) {
      std::cerr << "error: package release --mock-upload requires "
                   "--upload-manifest\n";
      return 2;
    }
    if (gcsUpload && !uploadManifestPath) {
      std::cerr << "error: package release --gcs-upload requires "
                   "--upload-manifest\n";
      return 2;
    }
    if (gcsUploadOverwrite && !gcsUpload) {
      std::cerr << "error: package release --gcs-upload-overwrite requires "
                   "--gcs-upload\n";
      return 2;
    }
    if (mockUpload && gcsUpload) {
      std::cerr << "error: package release --mock-upload cannot be combined "
                   "with --gcs-upload\n";
      return 2;
    }
    if (mockUpload && hasArg(args, "--dry-run")) {
      std::cerr << "error: package release --mock-upload does not accept "
                   "--dry-run\n";
      return 2;
    }
    if (gcsUpload && hasArg(args, "--dry-run")) {
      std::cerr << "error: package release --gcs-upload does not accept "
                   "--dry-run\n";
      return 2;
    }
    if ((publishTarget || targetOutputPath || targetDescriptorPath ||
         receiptOutputPath || uploadManifestOutputPath) &&
        !publishStagePath) {
      std::cerr << "error: package release publish target options require "
                   "--publish-stage\n";
      return 2;
    }
    if (uploadManifestPath) {
      if (mockUpload) {
        return commandPackageReleaseMockUpload(
            args, *uploadManifestPath, uploadReportOutputPath,
            uploadReceiptOutputPath,
            promotionSummaryPath, manifestOutputPath, bundleOutputPath,
            verifyBundlePath, planPublishPath, planOutputPath, stagePublishPath,
            stageOutputPath, publishStagePath, publishTarget, targetOutputPath,
            targetDescriptorPath, receiptOutputPath, uploadManifestOutputPath,
            policyPath, sourcePath, packagePath);
      }
      if (gcsUpload) {
        return commandPackageReleaseGcsUpload(
            args, *uploadManifestPath, uploadReportOutputPath,
            uploadReceiptOutputPath,
            gcsUploadOverwrite,
            promotionSummaryPath, manifestOutputPath, bundleOutputPath,
            verifyBundlePath, planPublishPath, planOutputPath, stagePublishPath,
            stageOutputPath, publishStagePath, publishTarget, targetOutputPath,
            targetDescriptorPath, receiptOutputPath, uploadManifestOutputPath,
            policyPath, sourcePath, packagePath);
      }
      return commandPackageReleaseUploadPreflight(
          args, *uploadManifestPath, uploadReportOutputPath,
          promotionSummaryPath, manifestOutputPath, bundleOutputPath,
          verifyBundlePath, planPublishPath, planOutputPath, stagePublishPath,
          stageOutputPath, publishStagePath, publishTarget, targetOutputPath,
          targetDescriptorPath, receiptOutputPath, uploadManifestOutputPath,
          policyPath, sourcePath, packagePath);
    }
    if (verifyBundlePath) {
      return commandPackageReleaseBundleVerification(
          args, *verifyBundlePath, promotionSummaryPath, manifestOutputPath,
          bundleOutputPath, policyPath, sourcePath, packagePath);
    }
    if (publishStagePath) {
      return commandPackageReleasePublishReceipt(
          args, *publishStagePath, publishTarget, targetOutputPath,
          targetDescriptorPath, receiptOutputPath, uploadManifestOutputPath,
          promotionSummaryPath, manifestOutputPath, bundleOutputPath,
          verifyBundlePath, planPublishPath, planOutputPath, stagePublishPath,
          stageOutputPath, policyPath, sourcePath, packagePath);
    }
    if (stagePublishPath) {
      return commandPackageReleasePublishStage(
          args, *stagePublishPath, stageOutputPath, promotionSummaryPath,
          manifestOutputPath, bundleOutputPath, verifyBundlePath,
          planPublishPath, planOutputPath, policyPath, sourcePath, packagePath);
    }
    if (planPublishPath) {
      return commandPackageReleasePublishPlan(
          args, *planPublishPath, planOutputPath, promotionSummaryPath,
          manifestOutputPath, bundleOutputPath, verifyBundlePath, policyPath,
          sourcePath, packagePath);
    }
    return commandPackageReleasePromotion(args, promotionSummaryPath,
                                          manifestOutputPath, bundleOutputPath,
                                          policyPath, sourcePath, packagePath);
  }

  if (subcommand == "maintain") {
    if (hasArg(args, "--list") || hasArg(args, "--discard-stale") ||
        hasArg(args, "--promote") || hasArg(args, "--discard") ||
        hasArg(args, "--replace") || sourcePath) {
      std::cerr << "error: package maintain does not accept --list, "
                   "--discard-stale, --promote, --discard, --replace, or "
                   "--source\n";
      return 2;
    }
    const std::size_t maintenanceModeCount =
        (packagePath.empty() ? 0 : 1) + (scanPath ? 1 : 0) +
        (packageSetPath ? 1 : 0) +
        (exportPackageSetVerificationBatchPath ? 1 : 0) +
        (verifyPackageSetBatchPath ? 1 : 0);
    if (maintenanceModeCount != 1) {
      std::cerr << "error: package maintain accepts exactly one of a package "
                   "path, --scan, --package-set, "
                   "--export-package-set-verification-batch, or "
                   "--verify-package-set-batch\n";
      return 2;
    }
    if (scanPath) {
      return commandPackageMaintenanceScan(args, *scanPath, policyPath,
                                           exportPackageSetPath,
                                           verifyPackageSetPath);
    }
    if (packageSetPath) {
      return commandPackageMaintenanceSet(args, *packageSetPath, policyPath);
    }
    if (exportPackageSetVerificationBatchPath) {
      return commandPackageMaintenanceSetVerificationBatchExport(
          args, *exportPackageSetVerificationBatchPath,
          exportPackageSetVerificationEntries, policyPath);
    }
    if (verifyPackageSetBatchPath) {
      return commandPackageMaintenanceSetVerificationBatch(
          args, *verifyPackageSetBatchPath, summaryOutputPath, policyPath);
    }
    return commandPackageStaleSidecarCleanup(args, packagePath, policyPath,
                                             "package maintain");
  }

  const bool jsonOutput = hasArg(args, "--json");
  crossgl::PackageIntegrityResult result =
      crossgl::verifyPackage(packagePath, sourcePath);
  if (jsonOutput) {
    std::cout << crossgl::packageVerifyJson(result, packagePath);
  } else {
    printDiagnostics(result.diagnostics);
  }
  if (!result.success) {
    return 1;
  }
  if (jsonOutput) {
    return 0;
  }
  if (result.metadata) {
    std::cout << "verified package " << packagePath << ": "
              << result.metadata->module << " for " << result.metadata->target
              << " (" << result.metadata->artifacts.size() << " artifacts)\n";
  } else {
    std::cout << "verified package " << packagePath << "\n";
  }
  return 0;
}

} // namespace

int main(int argc, char **argv) {
  std::vector<std::string> args;
  for (int i = 0; i < argc; ++i) {
    args.emplace_back(argv[i]);
  }

  if (args.size() < 2 || args[1] == "--help" || args[1] == "-h") {
    printUsage();
    return args.size() < 2 ? 2 : 0;
  }

  const std::string command = args[1];
  std::vector<std::string> commandArgs(args.begin() + 1, args.end());

  try {
    if (isSourceInputCommand(command)) {
      const SourceBatchManifestFlag manifestFlag =
          parseSourceBatchManifestFlag(commandArgs);
      if (manifestFlag.present) {
        if (!manifestFlag.valid) {
          return 2;
        }
        if (command != "check" && command != "build") {
          return rejectUnsupportedSourceBatchManifestCommand(command,
                                                            manifestFlag.flag);
        }
      }
    }
    if (command == "doctor") {
      return commandDoctor(commandArgs);
    }
    if (command == "targets") {
      return commandTargets();
    }
    if (command == "check") {
      return commandCheck(commandArgs);
    }
    if (command == "explain-targets") {
      return commandExplainTargets(commandArgs);
    }
    if (command == "language-feature-report") {
      return commandLanguageFeatureReport(commandArgs);
    }
    if (command == "dump-ir") {
      return commandDumpIR(commandArgs);
    }
    if (command == "build") {
      return commandBuild(commandArgs);
    }
    if (command == "package") {
      return commandPackage(commandArgs);
    }
  } catch (const std::exception &error) {
    std::cerr << "error: " << error.what() << "\n";
    return 2;
  }

  std::cerr << "unknown command: " << command << "\n";
  printUsage();
  return 2;
}
