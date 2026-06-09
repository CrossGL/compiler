#include "crossgl/Driver/PackagePublication.h"

#include "crossgl/Driver/PackageJson.h"
#include "crossgl/Basic/Json.h"
#include "crossgl/Basic/SHA256.h"
#include "crossgl/Driver/PackageIntegrity.h"
#include "crossgl/Driver/PackageMetadata.h"
#include "crossgl/Driver/PackageTargetContracts.h"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <fstream>
#include <limits>
#include <map>
#include <ostream>
#include <sstream>
#include <string>
#include <system_error>
#include <tuple>
#include <utility>

namespace crossgl {
namespace {

struct SidecarMarker {
  std::size_t position = std::string::npos;
  std::string_view marker;
  std::string_view kind;
};

std::optional<std::uint64_t> parseUnsigned(std::string_view value) {
  if (value.empty()) {
    return std::nullopt;
  }

  std::uint64_t parsed = 0;
  for (char character : value) {
    if (!std::isdigit(static_cast<unsigned char>(character))) {
      return std::nullopt;
    }
    parsed = (parsed * 10) + static_cast<std::uint64_t>(character - '0');
  }
  return parsed;
}

std::string recoveryDiagnosticCode(std::string_view suffix) {
  return "package.recover." + std::string(suffix);
}

std::string maintenancePolicyDiagnosticCode(std::string_view suffix) {
  return "package.maintain.policy." + std::string(suffix);
}

std::string maintenanceScanDiagnosticCode(std::string_view suffix) {
  return "package.maintain.scan." + std::string(suffix);
}

std::string maintenanceSetDiagnosticCode(std::string_view suffix) {
  return "package.maintain.set." + std::string(suffix);
}

std::string maintenanceSetExportDiagnosticCode(std::string_view suffix) {
  return "package.maintain.set.export." + std::string(suffix);
}

std::string maintenanceSetVerificationDiagnosticCode(std::string_view suffix) {
  return "package.maintain.set.verify." + std::string(suffix);
}

std::string
maintenanceSetVerificationBatchDiagnosticCode(std::string_view suffix) {
  return "package.maintain.set.verify.batch." + std::string(suffix);
}

std::string
maintenanceSetVerificationBatchSummaryDiagnosticCode(std::string_view suffix) {
  return "package.maintain.set.verify.batch.summary." + std::string(suffix);
}

std::string releasePromotionDiagnosticCode(std::string_view suffix) {
  return "package.release.promotion." + std::string(suffix);
}

std::string releaseBundleDiagnosticCode(std::string_view suffix) {
  return "package.release.bundle." + std::string(suffix);
}

std::string releaseReportDiagnosticCode(std::string_view suffix) {
  return "package.release.report." + std::string(suffix);
}

std::string releasePublishDiagnosticCode(std::string_view suffix) {
  return "package.release.publish." + std::string(suffix);
}

bool releasePublishObjectNameEndsWithDestination(std::string_view objectName,
                                                 std::string_view destination) {
  const std::string expectedSuffix = "/" + std::string(destination);
  return objectName != destination && objectName.ends_with(expectedSuffix);
}

std::string recoveryActionName(PackageRecoveryAction action) {
  switch (action) {
  case PackageRecoveryAction::Promote:
    return "promote";
  case PackageRecoveryAction::Discard:
    return "discard";
  }
  return "promote";
}

SourceLocation pathLocation(const std::filesystem::path &path) {
  SourceLocation location;
  location.file = path.lexically_normal().generic_string();
  return location;
}

std::optional<SidecarMarker> findSidecarMarker(std::string_view filename) {
  if (filename.size() < 2 || filename.front() != '.') {
    return std::nullopt;
  }

  const SidecarMarker staging{filename.rfind(".staging-"), ".staging-",
                              "staging"};
  const SidecarMarker previous{filename.rfind(".previous-"), ".previous-",
                               "previous"};
  if (staging.position == std::string::npos &&
      previous.position == std::string::npos) {
    return std::nullopt;
  }
  if (staging.position == std::string::npos) {
    return previous;
  }
  if (previous.position == std::string::npos) {
    return staging;
  }
  if (staging.position > previous.position) {
    return staging;
  }
  return previous;
}

std::string
recoveryPromoteMessage(const std::filesystem::path &sidecarPath,
                       const std::filesystem::path &requestedPath,
                       const std::optional<std::filesystem::path> &backupPath) {
  std::ostringstream message;
  message << "promoted package sidecar " << sidecarPath.string() << " to "
          << requestedPath.string();
  if (backupPath) {
    message << "; previous package moved to " << backupPath->string();
  }
  return message.str();
}

void writeNullablePath(std::ostream &out, const std::filesystem::path &path) {
  if (path.empty()) {
    out << "null";
    return;
  }
  out << "\"" << escapeJson(path.lexically_normal().generic_string()) << "\"";
}

std::filesystem::path
releaseBundleVerificationBundlePathField(const std::filesystem::path &path) {
  const std::filesystem::path normalized = path.lexically_normal();
  if (normalized.empty() || !normalized.is_absolute()) {
    return normalized;
  }
  const std::filesystem::path filename = normalized.filename();
  if (!filename.empty()) {
    return filename;
  }
  return normalized.relative_path().lexically_normal();
}

void writeNullablePath(std::ostream &out,
                       const std::optional<std::filesystem::path> &path) {
  if (!path) {
    out << "null";
    return;
  }
  writeNullablePath(out, *path);
}

void writeNullableString(std::ostream &out,
                         const std::optional<std::string> &value) {
  if (value) {
    out << "\"" << escapeJson(*value) << "\"";
  } else {
    out << "null";
  }
}

void writeNullableUnsigned(std::ostream &out,
                           const std::optional<std::uint64_t> &value) {
  if (value) {
    out << *value;
  } else {
    out << "null";
  }
}

void writeSidecarRecord(std::ostream &out, const PackageSidecarRecord &record,
                        std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"path\": \""
      << escapeJson(record.path.lexically_normal().generic_string()) << "\",\n"
      << indent << "  \"kind\": \"" << escapeJson(record.kind) << "\",\n"
      << indent << "  \"token\": \"" << escapeJson(record.token) << "\",\n"
      << indent << "  \"attempt\": " << record.attempt << ",\n"
      << indent
      << "  \"directory\": " << (record.isDirectory ? "true" : "false") << "\n"
      << indent << "}";
}

void writePublicationInfo(std::ostream &out,
                          const PackagePublicationInfo &publication,
                          std::string_view indent) {
  std::optional<std::string> sidecarKind;
  std::optional<std::string> sidecarToken;
  std::optional<std::uint64_t> sidecarAttempt;
  if (publication.currentSidecar) {
    sidecarKind = publication.currentSidecar->kind;
    sidecarToken = publication.currentSidecar->token;
    sidecarAttempt = publication.currentSidecar->attempt;
  }

  out << "{\n"
      << indent << "  \"state\": \"" << escapeJson(publication.state) << "\",\n"
      << indent << "  \"requestedPath\": \""
      << escapeJson(
             publication.requestedPath.lexically_normal().generic_string())
      << "\",\n"
      << indent << "  \"sidecarKind\": ";
  writeNullableString(out, sidecarKind);
  out << ",\n" << indent << "  \"sidecarToken\": ";
  writeNullableString(out, sidecarToken);
  out << ",\n" << indent << "  \"sidecarAttempt\": ";
  writeNullableUnsigned(out, sidecarAttempt);
  out << ",\n"
      << indent
      << "  \"siblingSidecarCount\": " << publication.siblingSidecars.size()
      << ",\n"
      << indent << "  \"siblingSidecars\": [";
  for (std::size_t index = 0; index < publication.siblingSidecars.size();
       ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeSidecarRecord(out, publication.siblingSidecars[index],
                       std::string(indent) + "    ");
  }
  if (!publication.siblingSidecars.empty()) {
    out << "\n" << indent << "  ";
  }
  out << "]\n" << indent << "}";
}

void writeDiagnosticRecord(std::ostream &out, const Diagnostic &diagnostic,
                           std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"severity\": \""
      << escapeJson(toString(diagnostic.severity)) << "\",\n"
      << indent << "  \"code\": \"" << escapeJson(diagnostic.code) << "\",\n"
      << indent << "  \"message\": \"" << escapeJson(diagnostic.message)
      << "\",\n"
      << indent << "  \"location\": {\n"
      << indent << "    \"file\": \"" << escapeJson(diagnostic.location.file)
      << "\",\n"
      << indent << "    \"line\": " << diagnostic.location.line << ",\n"
      << indent << "    \"column\": " << diagnostic.location.column << ",\n"
      << indent << "    \"offset\": " << diagnostic.location.offset << ",\n"
      << indent << "    \"length\": " << diagnostic.location.length << ",\n"
      << indent << "    \"endLine\": " << diagnostic.location.endLine << ",\n"
      << indent << "    \"endColumn\": " << diagnostic.location.endColumn
      << ",\n"
      << indent << "    \"endOffset\": " << diagnostic.location.endOffset
      << "\n"
      << indent << "  }";
  if (!diagnostic.target.empty()) {
    out << ",\n"
        << indent << "  \"target\": \"" << escapeJson(diagnostic.target)
        << "\"";
  }
  if (!diagnostic.missingCapabilities.empty()) {
    out << ",\n" << indent << "  \"missingCapabilities\": [";
    for (std::size_t index = 0; index < diagnostic.missingCapabilities.size();
         ++index) {
      if (index != 0) {
        out << ", ";
      }
      out << "\"" << escapeJson(diagnostic.missingCapabilities[index]) << "\"";
    }
    out << "]";
  }
  out << "\n" << indent << "}";
}

void writeDiagnostics(std::ostream &out,
                      const std::vector<Diagnostic> &diagnostics,
                      std::string_view indent) {
  out << "[";
  for (std::size_t index = 0; index < diagnostics.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeDiagnosticRecord(out, diagnostics[index], std::string(indent) + "  ");
  }
  if (!diagnostics.empty()) {
    out << "\n" << indent;
  }
  out << "]";
}

void writeDiagnostics(std::ostream &out,
                      const std::vector<Diagnostic> &diagnostics) {
  writeDiagnostics(out, diagnostics, "  ");
}

std::size_t countDiagnostics(const std::vector<Diagnostic> &diagnostics,
                             DiagnosticSeverity severity) {
  std::size_t count = 0;
  for (const Diagnostic &diagnostic : diagnostics) {
    if (diagnostic.severity == severity) {
      ++count;
    }
  }
  return count;
}

void writeDiagnosticCounts(std::ostream &out,
                           const std::vector<Diagnostic> &diagnostics,
                           std::string_view indent) {
  out << "{\n"
      << indent << "  \"note\": "
      << countDiagnostics(diagnostics, DiagnosticSeverity::Note) << ",\n"
      << indent << "  \"warning\": "
      << countDiagnostics(diagnostics, DiagnosticSeverity::Warning) << ",\n"
      << indent << "  \"error\": "
      << countDiagnostics(diagnostics, DiagnosticSeverity::Error) << "\n"
      << indent << "}";
}

void writeDiagnosticCodeCounts(std::ostream &out,
                               const std::vector<Diagnostic> &diagnostics,
                               std::string_view indent) {
  std::map<std::string, std::size_t> counts;
  for (const Diagnostic &diagnostic : diagnostics) {
    ++counts[diagnostic.code];
  }

  out << "[";
  bool first = true;
  for (const auto &[code, count] : counts) {
    out << (first ? "\n" : ",\n") << indent << "  {\n"
        << indent << "    \"code\": \"" << escapeJson(code) << "\",\n"
        << indent << "    \"count\": " << count << "\n"
        << indent << "  }";
    first = false;
  }
  if (!counts.empty()) {
    out << "\n" << indent;
  }
  out << "]";
}

void writePathArray(std::ostream &out,
                    const std::vector<std::filesystem::path> &paths,
                    std::string_view indent) {
  out << "[";
  for (std::size_t index = 0; index < paths.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n") << indent << "  \""
        << escapeJson(paths[index].lexically_normal().generic_string()) << "\"";
  }
  if (!paths.empty()) {
    out << "\n" << indent;
  }
  out << "]";
}

bool isStaleSidecar(const PackageSidecarRecord &sidecar, bool requestedExists,
                    std::string &reason) {
  if (!sidecar.isDirectory) {
    reason = "not-directory";
    return true;
  }
  if (sidecar.kind == "previous") {
    reason = "previous-backup";
    return true;
  }
  if (sidecar.kind == "staging" && requestedExists) {
    reason = "staging-with-published-output";
    return true;
  }
  return false;
}

struct StaleSidecarSelection {
  PackageSidecarRecord sidecar;
  std::string reason;
  std::string retainedBy;
};

int compareSidecarTokens(std::string_view lhs, std::string_view rhs) {
  const std::optional<std::uint64_t> lhsNumeric = parseUnsigned(lhs);
  const std::optional<std::uint64_t> rhsNumeric = parseUnsigned(rhs);
  if (lhsNumeric && rhsNumeric) {
    if (*lhsNumeric < *rhsNumeric) {
      return -1;
    }
    if (*lhsNumeric > *rhsNumeric) {
      return 1;
    }
    return 0;
  }
  if (lhs < rhs) {
    return -1;
  }
  if (lhs > rhs) {
    return 1;
  }
  return 0;
}

bool isNewerSidecar(const PackageSidecarRecord &lhs,
                    const PackageSidecarRecord &rhs) {
  const int tokenComparison = compareSidecarTokens(lhs.token, rhs.token);
  if (tokenComparison != 0) {
    return tokenComparison > 0;
  }
  if (lhs.attempt != rhs.attempt) {
    return lhs.attempt > rhs.attempt;
  }
  return lhs.path.generic_string() > rhs.path.generic_string();
}

std::vector<bool>
retainedStaleSidecars(const std::vector<StaleSidecarSelection> &selections,
                      std::optional<std::size_t> keepLast) {
  std::vector<bool> retained(selections.size(), false);
  if (!keepLast || *keepLast == 0) {
    return retained;
  }

  std::vector<std::size_t> retainable;
  for (std::size_t index = 0; index < selections.size(); ++index) {
    if (selections[index].retainedBy.empty() &&
        selections[index].sidecar.isDirectory) {
      retainable.push_back(index);
    }
  }
  std::sort(retainable.begin(), retainable.end(),
            [&selections](std::size_t lhs, std::size_t rhs) {
              return isNewerSidecar(selections[lhs].sidecar,
                                    selections[rhs].sidecar);
            });
  const std::size_t retainCount = std::min(*keepLast, retainable.size());
  for (std::size_t index = 0; index < retainCount; ++index) {
    retained[retainable[index]] = true;
  }
  return retained;
}

PackageStaleSidecarCleanupRecord
makeCleanupRecord(const StaleSidecarSelection &selection,
                  std::string_view action) {
  PackageStaleSidecarCleanupRecord record;
  record.sidecar = selection.sidecar;
  record.reason = selection.reason;
  record.retainedBy = selection.retainedBy;
  record.action = std::string(action);
  return record;
}

std::optional<std::filesystem::file_time_type>
staleSidecarAgeCutoff(std::optional<std::uint64_t> olderThanSeconds) {
  if (!olderThanSeconds) {
    return std::nullopt;
  }
  const auto duration =
      std::chrono::duration_cast<std::filesystem::file_time_type::duration>(
          std::chrono::seconds(*olderThanSeconds));
  return std::filesystem::file_time_type::clock::now() - duration;
}

std::string
retainSidecarByAge(const PackageSidecarRecord &sidecar,
                   const std::optional<std::filesystem::file_time_type> &cutoff,
                   DiagnosticEngine &diagnostics) {
  if (!cutoff) {
    return "";
  }

  std::error_code error;
  const std::filesystem::file_time_type lastWriteTime =
      std::filesystem::last_write_time(sidecar.path, error);
  if (error) {
    diagnostics.warning(
        recoveryDiagnosticCode("retention-age-unknown"),
        "failed to inspect stale package sidecar age; retaining "
        "it: " +
            error.message(),
        pathLocation(sidecar.path));
    return "age-unknown";
  }
  return lastWriteTime > *cutoff ? "younger-than" : "";
}

std::size_t countCleanupRecords(
    const std::vector<PackageStaleSidecarCleanupRecord> &records,
    std::string_view action) {
  std::size_t count = 0;
  for (const PackageStaleSidecarCleanupRecord &record : records) {
    if (record.action == action) {
      ++count;
    }
  }
  return count;
}

std::size_t packageCleanupCandidateCount(
    const std::vector<PackageStaleSidecarCleanupResult> &packages) {
  std::size_t count = 0;
  for (const PackageStaleSidecarCleanupResult &package : packages) {
    count += package.candidates.size();
  }
  return count;
}

std::size_t packageCleanupRetainedCount(
    const std::vector<PackageStaleSidecarCleanupResult> &packages) {
  std::size_t count = 0;
  for (const PackageStaleSidecarCleanupResult &package : packages) {
    count += package.retained.size();
  }
  return count;
}

std::size_t packageCleanupRecordActionCount(
    const std::vector<PackageStaleSidecarCleanupResult> &packages,
    std::string_view action) {
  std::size_t count = 0;
  for (const PackageStaleSidecarCleanupResult &package : packages) {
    count += countCleanupRecords(package.candidates, action);
  }
  return count;
}

std::vector<Diagnostic> packageMaintenanceScanDiagnostics(
    const std::vector<Diagnostic> &scanDiagnostics,
    const std::vector<PackageStaleSidecarCleanupResult> &packages) {
  std::vector<Diagnostic> diagnostics = scanDiagnostics;
  for (const PackageStaleSidecarCleanupResult &package : packages) {
    diagnostics.insert(diagnostics.end(), package.diagnostics.begin(),
                       package.diagnostics.end());
  }
  return diagnostics;
}

bool packageMaintenanceAggregateSuccess(
    const std::vector<Diagnostic> &diagnostics,
    const std::vector<PackageStaleSidecarCleanupResult> &packages) {
  for (const Diagnostic &diagnostic : diagnostics) {
    if (diagnostic.severity == DiagnosticSeverity::Error) {
      return false;
    }
  }
  for (const PackageStaleSidecarCleanupResult &package : packages) {
    if (!package.success) {
      return false;
    }
  }
  return true;
}

bool isCandidatePackageOutputPath(const std::filesystem::path &path) {
  const std::string filename = path.filename().generic_string();
  return !filename.empty() && filename.front() != '.' &&
         path.extension() == ".cglb";
}

std::vector<std::filesystem::path>
discoverMaintenancePackageRoots(const std::filesystem::path &rootPath,
                                DiagnosticEngine &diagnostics) {
  std::vector<std::filesystem::path> packageRoots;
  std::error_code error;
  if (!std::filesystem::exists(rootPath, error) || error) {
    diagnostics.error(maintenanceScanDiagnosticCode("missing-root"),
                      "package maintenance scan root does not exist: " +
                          rootPath.string(),
                      pathLocation(rootPath));
    return packageRoots;
  }
  if (!std::filesystem::is_directory(rootPath, error) || error) {
    diagnostics.error(maintenanceScanDiagnosticCode("invalid-root"),
                      "package maintenance scan root is not a directory: " +
                          rootPath.string(),
                      pathLocation(rootPath));
    return packageRoots;
  }

  for (std::filesystem::directory_iterator entry(rootPath, error), end;
       !error && entry != end; entry.increment(error)) {
    const std::filesystem::path entryPath = entry->path().lexically_normal();
    if (std::optional<PackageSidecarRecord> sidecar =
            parsePackageSidecarPath(entryPath)) {
      packageRoots.push_back(sidecar->requestedPath.lexically_normal());
      continue;
    }
    if (isCandidatePackageOutputPath(entryPath)) {
      packageRoots.push_back(entryPath);
    }
  }
  if (error) {
    diagnostics.error(maintenanceScanDiagnosticCode("inspect-root"),
                      "failed to inspect package maintenance scan root: " +
                          error.message(),
                      pathLocation(rootPath));
    return packageRoots;
  }

  std::sort(
      packageRoots.begin(), packageRoots.end(),
      [](const std::filesystem::path &lhs, const std::filesystem::path &rhs) {
        return lhs.generic_string() < rhs.generic_string();
      });
  packageRoots.erase(std::unique(packageRoots.begin(), packageRoots.end(),
                                 [](const std::filesystem::path &lhs,
                                    const std::filesystem::path &rhs) {
                                   return lhs.generic_string() ==
                                          rhs.generic_string();
                                 }),
                     packageRoots.end());
  return packageRoots;
}

std::optional<std::string>
readMaintenanceSetFile(const std::filesystem::path &setPath,
                       DiagnosticEngine &diagnostics) {
  std::error_code statusError;
  if (std::filesystem::exists(setPath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(setPath, statusError)) {
    diagnostics.error(maintenanceSetDiagnosticCode("invalid-file"),
                      "package maintenance set is not a regular file: " +
                          setPath.string(),
                      pathLocation(setPath));
    return std::nullopt;
  }

  std::ifstream input(setPath, std::ios::binary);
  if (!input) {
    diagnostics.error(maintenanceSetDiagnosticCode("read-failed"),
                      "failed to read package maintenance set: " +
                          setPath.string(),
                      pathLocation(setPath));
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  std::string text = buffer.str();
  if (!isJsonObjectDocument(text)) {
    diagnostics.error(maintenanceSetDiagnosticCode("invalid-json"),
                      "package maintenance set is not a valid JSON object: " +
                          setPath.string(),
                      pathLocation(setPath));
    return std::nullopt;
  }
  if (const std::optional<DuplicateJsonKey> duplicate =
          findDuplicateJsonKey(text)) {
    diagnostics.error(
        maintenanceSetDiagnosticCode("duplicate-key"),
        "package maintenance set contains duplicate JSON object key: " +
            duplicate->path,
        pathLocation(setPath));
    return std::nullopt;
  }
  return text;
}

std::optional<std::string>
readMaintenanceSetVerificationBatchFile(const std::filesystem::path &batchPath,
                                        DiagnosticEngine &diagnostics) {
  std::error_code statusError;
  if (std::filesystem::exists(batchPath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(batchPath, statusError)) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("invalid-file"),
        "package maintenance set verification batch is not a regular file: " +
            batchPath.string(),
        pathLocation(batchPath));
    return std::nullopt;
  }

  std::ifstream input(batchPath, std::ios::binary);
  if (!input) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("read-failed"),
        "failed to read package maintenance set verification batch: " +
            batchPath.string(),
        pathLocation(batchPath));
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  std::string text = buffer.str();
  if (!isJsonObjectDocument(text)) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("invalid-json"),
        "package maintenance set verification batch is not a valid JSON "
        "object: " +
            batchPath.string(),
        pathLocation(batchPath));
    return std::nullopt;
  }
  if (const std::optional<DuplicateJsonKey> duplicate =
          findDuplicateJsonKey(text)) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("duplicate-key"),
        "package maintenance set verification batch contains duplicate JSON "
        "object key: " +
            duplicate->path,
        pathLocation(batchPath));
    return std::nullopt;
  }
  return text;
}

std::optional<std::string>
readReleasePromotionSummaryFile(const std::filesystem::path &summaryPath,
                                DiagnosticEngine &diagnostics) {
  std::error_code statusError;
  if (std::filesystem::exists(summaryPath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(summaryPath, statusError)) {
    diagnostics.error(releasePromotionDiagnosticCode("invalid-summary-file"),
                      "package release promotion summary is not a regular "
                      "file: " +
                          summaryPath.string(),
                      pathLocation(summaryPath));
    return std::nullopt;
  }

  std::ifstream input(summaryPath, std::ios::binary);
  if (!input) {
    diagnostics.error(releasePromotionDiagnosticCode("read-summary-failed"),
                      "failed to read package release promotion summary: " +
                          summaryPath.string(),
                      pathLocation(summaryPath));
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  std::string text = buffer.str();
  if (!isJsonObjectDocument(text)) {
    diagnostics.error(releasePromotionDiagnosticCode("invalid-summary-json"),
                      "package release promotion summary is not a valid JSON "
                      "object: " +
                          summaryPath.string(),
                      pathLocation(summaryPath));
    return std::nullopt;
  }
  if (const std::optional<DuplicateJsonKey> duplicate =
          findDuplicateJsonKey(text)) {
    diagnostics.error(releasePromotionDiagnosticCode("duplicate-summary-key"),
                      "package release promotion summary contains duplicate "
                      "JSON object key: " +
                          duplicate->path,
                      pathLocation(summaryPath));
    return std::nullopt;
  }
  return text;
}

std::optional<std::string>
readReleaseBundleManifestFile(const std::filesystem::path &bundlePath,
                              DiagnosticEngine &diagnostics) {
  std::error_code statusError;
  if (std::filesystem::exists(bundlePath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(bundlePath, statusError)) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-file"),
                      "package release bundle is not a regular file: " +
                          bundlePath.string(),
                      pathLocation(bundlePath));
    return std::nullopt;
  }

  std::ifstream input(bundlePath, std::ios::binary);
  if (!input) {
    diagnostics.error(releaseBundleDiagnosticCode("read-failed"),
                      "failed to read package release bundle: " +
                          bundlePath.string(),
                      pathLocation(bundlePath));
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  std::string text = buffer.str();
  if (!isJsonObjectDocument(text)) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-json"),
                      "package release bundle is not a valid JSON object: " +
                          bundlePath.string(),
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  if (const std::optional<DuplicateJsonKey> duplicate =
          findDuplicateJsonKey(text)) {
    diagnostics.error(releaseBundleDiagnosticCode("duplicate-key"),
                      "package release bundle contains duplicate JSON object "
                      "key: " +
                          duplicate->path,
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  return text;
}

std::optional<std::string>
readReleasePublishPlanFile(const std::filesystem::path &planPath,
                           DiagnosticEngine &diagnostics) {
  std::error_code statusError;
  if (std::filesystem::exists(planPath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(planPath, statusError)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-plan-file"),
                      "package release publish plan is not a regular file: " +
                          planPath.string(),
                      pathLocation(planPath));
    return std::nullopt;
  }

  std::ifstream input(planPath, std::ios::binary);
  if (!input) {
    diagnostics.error(releasePublishDiagnosticCode("plan-read-failed"),
                      "failed to read package release publish plan: " +
                          planPath.string(),
                      pathLocation(planPath));
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  std::string text = buffer.str();
  if (!isJsonObjectDocument(text)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-plan-json"),
                      "package release publish plan is not a valid JSON "
                      "object: " +
                          planPath.string(),
                      pathLocation(planPath));
    return std::nullopt;
  }
  if (const std::optional<DuplicateJsonKey> duplicate =
          findDuplicateJsonKey(text)) {
    diagnostics.error(releasePublishDiagnosticCode("duplicate-plan-key"),
                      "package release publish plan contains duplicate JSON "
                      "object key: " +
                          duplicate->path,
                      pathLocation(planPath));
    return std::nullopt;
  }
  return text;
}

std::optional<std::string>
readReleasePublishStageReportFile(const std::filesystem::path &reportPath,
                                  DiagnosticEngine &diagnostics) {
  std::error_code statusError;
  if (std::filesystem::exists(reportPath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(reportPath, statusError)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-stage-report-file"),
                      "package release publish stage report is not a regular "
                      "file: " +
                          reportPath.string(),
                      pathLocation(reportPath));
    return std::nullopt;
  }

  std::ifstream input(reportPath, std::ios::binary);
  if (!input) {
    diagnostics.error(releasePublishDiagnosticCode("stage-report-read-failed"),
                      "failed to read package release publish stage report: " +
                          reportPath.string(),
                      pathLocation(reportPath));
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  std::string text = buffer.str();
  if (!isJsonObjectDocument(text)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-stage-report-json"),
                      "package release publish stage report is not a valid "
                      "JSON object: " +
                          reportPath.string(),
                      pathLocation(reportPath));
    return std::nullopt;
  }
  if (const std::optional<DuplicateJsonKey> duplicate =
          findDuplicateJsonKey(text)) {
    diagnostics.error(
        releasePublishDiagnosticCode("duplicate-stage-report-key"),
        "package release publish stage report contains "
        "duplicate JSON object key: " +
            duplicate->path,
        pathLocation(reportPath));
    return std::nullopt;
  }
  return text;
}

std::optional<std::string>
readReleasePublishUploadManifestFile(const std::filesystem::path &manifestPath,
                                     DiagnosticEngine &diagnostics) {
  std::error_code statusError;
  if (std::filesystem::exists(manifestPath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(manifestPath, statusError)) {
    diagnostics.error(
        releasePublishDiagnosticCode("invalid-upload-manifest-file"),
        "package release publish upload manifest is not a regular file: " +
            manifestPath.string(),
        pathLocation(manifestPath));
    return std::nullopt;
  }

  std::ifstream input(manifestPath, std::ios::binary);
  if (!input) {
    diagnostics.error(
        releasePublishDiagnosticCode("upload-manifest-read-failed"),
        "failed to read package release publish upload manifest: " +
            manifestPath.string(),
        pathLocation(manifestPath));
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  std::string text = buffer.str();
  if (!isJsonObjectDocument(text)) {
    diagnostics.error(
        releasePublishDiagnosticCode("invalid-upload-manifest-json"),
        "package release publish upload manifest is not a valid JSON object: " +
            manifestPath.string(),
        pathLocation(manifestPath));
    return std::nullopt;
  }
  if (const std::optional<DuplicateJsonKey> duplicate =
          findDuplicateJsonKey(text)) {
    diagnostics.error(
        releasePublishDiagnosticCode("duplicate-upload-manifest-key"),
        "package release publish upload manifest contains duplicate JSON "
        "object key: " +
            duplicate->path,
        pathLocation(manifestPath));
    return std::nullopt;
  }
  return text;
}

std::optional<std::string> readReleasePublishTargetDescriptorFile(
    const std::filesystem::path &descriptorPath,
    std::vector<Diagnostic> &diagnostics) {
  const auto appendError = [&](std::string_view suffix, std::string message) {
    Diagnostic diagnostic;
    diagnostic.severity = DiagnosticSeverity::Error;
    diagnostic.code = releasePublishDiagnosticCode(suffix);
    diagnostic.message = std::move(message);
    diagnostic.location = pathLocation(descriptorPath);
    diagnostics.push_back(std::move(diagnostic));
  };

  std::error_code statusError;
  if (std::filesystem::exists(descriptorPath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(descriptorPath, statusError)) {
    appendError(
        "invalid-target-descriptor-file",
        "package release publish target descriptor is not a regular file: " +
            descriptorPath.string());
    return std::nullopt;
  }

  std::ifstream input(descriptorPath, std::ios::binary);
  if (!input) {
    appendError("target-descriptor-read-failed",
                "failed to read package release publish target descriptor: " +
                    descriptorPath.string());
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  std::string text = buffer.str();
  if (!isJsonObjectDocument(text)) {
    appendError("invalid-target-descriptor-json",
                "package release publish target descriptor is not a valid JSON "
                "object: " +
                    descriptorPath.string());
    return std::nullopt;
  }
  if (const std::optional<DuplicateJsonKey> duplicate =
          findDuplicateJsonKey(text)) {
    appendError(
        "duplicate-target-descriptor-key",
        "package release publish target descriptor contains duplicate JSON "
        "object key: " +
            duplicate->path);
    return std::nullopt;
  }
  return text;
}

bool parseMaintenanceSetVersion(std::string_view text,
                                const std::filesystem::path &setPath,
                                DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> versionText =
      findObjectMemberValue(text, "schemaVersion");
  if (!versionText) {
    diagnostics.error(maintenanceSetDiagnosticCode("missing-schema-version"),
                      "package maintenance set requires schemaVersion: 1",
                      pathLocation(setPath));
    return false;
  }

  const std::optional<std::uintmax_t> version =
      parseUnsignedInteger(*versionText);
  if (!version || *version != 1) {
    diagnostics.error(
        maintenanceSetDiagnosticCode("unsupported-schema-version"),
        "package maintenance set schemaVersion must be 1",
        pathLocation(setPath));
    return false;
  }
  return true;
}

bool parseReleasePromotionSummaryVersion(
    std::string_view text, const std::filesystem::path &summaryPath,
    DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> versionText =
      findObjectMemberValue(text, "schemaVersion");
  if (!versionText) {
    diagnostics.error(releasePromotionDiagnosticCode("missing-schema-version"),
                      "package release promotion summary requires "
                      "schemaVersion: 1",
                      pathLocation(summaryPath));
    return false;
  }

  const std::optional<std::uintmax_t> version =
      parseUnsignedInteger(*versionText);
  if (!version || *version != 1) {
    diagnostics.error(
        releasePromotionDiagnosticCode("unsupported-schema-version"),
        "package release promotion summary schemaVersion must "
        "be 1",
        pathLocation(summaryPath));
    return false;
  }
  return true;
}

std::optional<bool> parseRequiredReleasePromotionBoolMember(
    std::string_view text, std::string_view key,
    const std::filesystem::path &summaryPath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(text, key);
  if (!valueText) {
    diagnostics.error(releasePromotionDiagnosticCode("missing-summary-field"),
                      "package release promotion summary requires boolean "
                      "field: " +
                          std::string(key),
                      pathLocation(summaryPath));
    return std::nullopt;
  }

  const std::optional<bool> value = parseBool(*valueText);
  if (!value) {
    diagnostics.error(releasePromotionDiagnosticCode("invalid-summary-field"),
                      "package release promotion summary field must be "
                      "boolean: " +
                          std::string(key),
                      pathLocation(summaryPath));
    return std::nullopt;
  }
  return value;
}

std::optional<std::size_t> parseRequiredReleasePromotionCountMember(
    std::string_view text, std::string_view key,
    const std::filesystem::path &summaryPath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(text, key);
  if (!valueText) {
    diagnostics.error(releasePromotionDiagnosticCode("missing-summary-field"),
                      "package release promotion summary requires count "
                      "field: " +
                          std::string(key),
                      pathLocation(summaryPath));
    return std::nullopt;
  }

  const std::optional<std::uintmax_t> value = parseUnsignedInteger(*valueText);
  if (!value || *value > std::numeric_limits<std::size_t>::max()) {
    diagnostics.error(releasePromotionDiagnosticCode("invalid-summary-field"),
                      "package release promotion summary field must be a "
                      "non-negative integer: " +
                          std::string(key),
                      pathLocation(summaryPath));
    return std::nullopt;
  }
  return static_cast<std::size_t>(*value);
}

std::optional<PackageReleasePromotionDiagnosticCounts>
parseReleasePromotionDiagnosticCounts(std::string_view text,
                                      const std::filesystem::path &summaryPath,
                                      DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> countsText =
      findObjectMemberValue(text, "diagnosticCounts");
  if (!countsText) {
    diagnostics.error(releasePromotionDiagnosticCode("missing-summary-field"),
                      "package release promotion summary requires "
                      "diagnosticCounts",
                      pathLocation(summaryPath));
    return std::nullopt;
  }

  const std::optional<std::uintmax_t> note =
      objectUnsignedMember(*countsText, "note");
  const std::optional<std::uintmax_t> warning =
      objectUnsignedMember(*countsText, "warning");
  const std::optional<std::uintmax_t> error =
      objectUnsignedMember(*countsText, "error");
  if (!note || !warning || !error ||
      *note > std::numeric_limits<std::size_t>::max() ||
      *warning > std::numeric_limits<std::size_t>::max() ||
      *error > std::numeric_limits<std::size_t>::max()) {
    diagnostics.error(releasePromotionDiagnosticCode("invalid-summary-field"),
                      "package release promotion summary diagnosticCounts "
                      "must contain note, warning, and error counts",
                      pathLocation(summaryPath));
    return std::nullopt;
  }

  PackageReleasePromotionDiagnosticCounts counts;
  counts.note = static_cast<std::size_t>(*note);
  counts.warning = static_cast<std::size_t>(*warning);
  counts.error = static_cast<std::size_t>(*error);
  return counts;
}

std::filesystem::path releasePromotionReferencedPath(std::string_view value) {
  return std::filesystem::path(std::string(value)).lexically_normal();
}

std::optional<std::vector<std::filesystem::path>>
parseReleasePromotionSummarySetPaths(std::string_view text,
                                     const std::filesystem::path &summaryPath,
                                     DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> verifications =
      findObjectMemberValue(text, "verifications");
  if (!verifications) {
    diagnostics.error(releasePromotionDiagnosticCode("missing-summary-field"),
                      "package release promotion summary requires "
                      "verifications",
                      pathLocation(summaryPath));
    return std::nullopt;
  }

  std::vector<std::filesystem::path> setPaths;
  std::size_t position = 0;
  skipWhitespace(*verifications, position);
  if (position >= verifications->size() || (*verifications)[position] != '[') {
    diagnostics.error(releasePromotionDiagnosticCode("invalid-summary-field"),
                      "package release promotion summary verifications must "
                      "be a JSON array",
                      pathLocation(summaryPath));
    return std::nullopt;
  }

  ++position;
  skipWhitespace(*verifications, position);
  if (position < verifications->size() && (*verifications)[position] == ']') {
    return setPaths;
  }

  while (position < verifications->size()) {
    const std::size_t objectBegin = position;
    if (!skipJsonObject(*verifications, position)) {
      diagnostics.error(releasePromotionDiagnosticCode("invalid-summary-field"),
                        "package release promotion summary verifications "
                        "entries must be JSON objects",
                        pathLocation(summaryPath));
      return std::nullopt;
    }
    const std::string_view objectText =
        verifications->substr(objectBegin, position - objectBegin);
    const std::optional<StringMember> setPath =
        findStringMemberRecord(objectText, "setPath");
    if (!setPath) {
      diagnostics.error(releasePromotionDiagnosticCode("missing-summary-field"),
                        "package release promotion summary verification "
                        "entries require setPath",
                        pathLocation(summaryPath));
      return std::nullopt;
    }
    if (setPath->value.empty()) {
      diagnostics.error(releasePromotionDiagnosticCode("invalid-summary-field"),
                        "package release promotion summary verification "
                        "setPath must not be empty",
                        pathLocation(summaryPath));
      return std::nullopt;
    }
    setPaths.push_back(releasePromotionReferencedPath(setPath->value));

    skipWhitespace(*verifications, position);
    if (position < verifications->size() && (*verifications)[position] == ',') {
      ++position;
      skipWhitespace(*verifications, position);
      continue;
    }
    if (position < verifications->size() && (*verifications)[position] == ']') {
      ++position;
      skipWhitespace(*verifications, position);
      if (position == verifications->size()) {
        std::sort(setPaths.begin(), setPaths.end(),
                  [](const std::filesystem::path &lhs,
                     const std::filesystem::path &rhs) {
                    return lhs.generic_string() < rhs.generic_string();
                  });
        setPaths.erase(std::unique(setPaths.begin(), setPaths.end(),
                                   [](const std::filesystem::path &lhs,
                                      const std::filesystem::path &rhs) {
                                     return lhs.generic_string() ==
                                            rhs.generic_string();
                                   }),
                       setPaths.end());
        return setPaths;
      }
    }
    diagnostics.error(releasePromotionDiagnosticCode("invalid-summary-field"),
                      "package release promotion summary verifications is not "
                      "a valid JSON array",
                      pathLocation(summaryPath));
    return std::nullopt;
  }

  diagnostics.error(releasePromotionDiagnosticCode("invalid-summary-field"),
                    "package release promotion summary verifications is not a "
                    "valid JSON array",
                    pathLocation(summaryPath));
  return std::nullopt;
}

struct PackageReleasePromotionSummaryLoadResult {
  bool success = false;
  PackageReleasePromotionSummary summary;
  std::vector<std::filesystem::path> packageSetPaths;
  std::vector<Diagnostic> diagnostics;
};

PackageReleasePromotionSummaryLoadResult
loadPackageReleasePromotionSummary(const std::filesystem::path &summaryPath) {
  DiagnosticEngine diagnostics;
  PackageReleasePromotionSummaryLoadResult result;
  result.summary.summaryPath = summaryPath;

  const std::optional<std::string> text =
      readReleasePromotionSummaryFile(summaryPath, diagnostics);
  if (!text) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  const bool versionOk =
      parseReleasePromotionSummaryVersion(*text, summaryPath, diagnostics);
  const std::optional<std::string> batchPath =
      objectStringMember(*text, "batchPath");
  if (!batchPath) {
    diagnostics.error(releasePromotionDiagnosticCode("missing-summary-field"),
                      "package release promotion summary requires string "
                      "field: batchPath",
                      pathLocation(summaryPath));
  } else {
    result.summary.batchPath = *batchPath;
  }

  const std::optional<bool> success = parseRequiredReleasePromotionBoolMember(
      *text, "success", summaryPath, diagnostics);
  const std::optional<bool> matches = parseRequiredReleasePromotionBoolMember(
      *text, "matches", summaryPath, diagnostics);
  const std::optional<bool> releaseEligible =
      parseRequiredReleasePromotionBoolMember(*text, "releaseEligible",
                                              summaryPath, diagnostics);
  const std::optional<std::size_t> verificationCount =
      parseRequiredReleasePromotionCountMember(*text, "verificationCount",
                                               summaryPath, diagnostics);
  const std::optional<std::size_t> matchedCount =
      parseRequiredReleasePromotionCountMember(*text, "matchedCount",
                                               summaryPath, diagnostics);
  const std::optional<std::size_t> mismatchedCount =
      parseRequiredReleasePromotionCountMember(*text, "mismatchedCount",
                                               summaryPath, diagnostics);
  const std::optional<std::size_t> failedCount =
      parseRequiredReleasePromotionCountMember(*text, "failedCount",
                                               summaryPath, diagnostics);
  const std::optional<std::size_t> scannedPackageCount =
      parseRequiredReleasePromotionCountMember(*text, "scannedPackageCount",
                                               summaryPath, diagnostics);
  const std::optional<std::size_t> setPackageCount =
      parseRequiredReleasePromotionCountMember(*text, "setPackageCount",
                                               summaryPath, diagnostics);
  const std::optional<std::size_t> missingFromSetCount =
      parseRequiredReleasePromotionCountMember(*text, "missingFromSetCount",
                                               summaryPath, diagnostics);
  const std::optional<std::size_t> extraInSetCount =
      parseRequiredReleasePromotionCountMember(*text, "extraInSetCount",
                                               summaryPath, diagnostics);
  const std::optional<PackageReleasePromotionDiagnosticCounts>
      diagnosticCounts = parseReleasePromotionDiagnosticCounts(
          *text, summaryPath, diagnostics);
  const std::optional<std::vector<std::filesystem::path>> packageSetPaths =
      parseReleasePromotionSummarySetPaths(*text, summaryPath, diagnostics);

  if (success) {
    result.summary.success = *success;
  }
  if (matches) {
    result.summary.matches = *matches;
  }
  if (releaseEligible) {
    result.summary.releaseEligible = *releaseEligible;
  }
  if (verificationCount) {
    result.summary.verificationCount = *verificationCount;
  }
  if (matchedCount) {
    result.summary.matchedCount = *matchedCount;
  }
  if (mismatchedCount) {
    result.summary.mismatchedCount = *mismatchedCount;
  }
  if (failedCount) {
    result.summary.failedCount = *failedCount;
  }
  if (scannedPackageCount) {
    result.summary.scannedPackageCount = *scannedPackageCount;
  }
  if (setPackageCount) {
    result.summary.setPackageCount = *setPackageCount;
  }
  if (missingFromSetCount) {
    result.summary.missingFromSetCount = *missingFromSetCount;
  }
  if (extraInSetCount) {
    result.summary.extraInSetCount = *extraInSetCount;
  }
  if (diagnosticCounts) {
    result.summary.diagnosticCounts = *diagnosticCounts;
  }
  if (packageSetPaths) {
    result.packageSetPaths = *packageSetPaths;
  }

  if (versionOk && success && matches && releaseEligible &&
      *releaseEligible != (*success && *matches)) {
    diagnostics.error(
        releasePromotionDiagnosticCode("inconsistent-release-eligibility"),
        "package release promotion summary releaseEligible must equal success "
        "and matches",
        pathLocation(summaryPath));
  }

  if (verificationCount && matchedCount && mismatchedCount && failedCount &&
      *matchedCount + *mismatchedCount + *failedCount > *verificationCount) {
    diagnostics.error(releasePromotionDiagnosticCode("inconsistent-counts"),
                      "package release promotion summary verification counters "
                      "exceed verificationCount",
                      pathLocation(summaryPath));
  }

  if (releaseEligible && *releaseEligible && diagnosticCounts &&
      diagnosticCounts->error != 0) {
    diagnostics.error(releasePromotionDiagnosticCode("inconsistent-counts"),
                      "package release promotion summary cannot be release "
                      "eligible with error diagnostics",
                      pathLocation(summaryPath));
  }

  result.diagnostics = diagnostics.diagnostics();
  result.success =
      countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
  return result;
}

struct PackageReleaseBundleParsedPackage {
  PackageReleasePromotionPackage package;
  std::size_t artifactCount = 0;
  std::size_t existingArtifactCount = 0;
  std::size_t missingArtifactCount = 0;
  std::uintmax_t totalArtifactBytes = 0;
};

struct PackageReleaseBundleParsedDocument {
  std::filesystem::path bundlePath;
  std::filesystem::path promotionManifestPath;
  std::filesystem::path summaryPath;
  std::filesystem::path batchPath;
  std::string status;
  bool releaseEligible = false;
  std::size_t blockerCount = 0;
  std::vector<PackageReleasePromotionBlocker> blockers;
  std::size_t packageCount = 0;
  std::size_t artifactCount = 0;
  std::size_t existingArtifactCount = 0;
  std::size_t missingArtifactCount = 0;
  std::uintmax_t totalArtifactBytes = 0;
  std::vector<PackageReleaseBundleParsedPackage> packages;
};

struct PackageReleasePublishPlanParsedDocument {
  std::filesystem::path bundlePath;
  std::filesystem::path planPath;
  bool releaseEligible = false;
  std::size_t packageCount = 0;
  std::size_t artifactCount = 0;
  std::uintmax_t totalArtifactBytes = 0;
  std::vector<PackageReleasePublishPlanPackage> packages;
  std::vector<PackageReleasePublishPlanArtifact> artifacts;
};

struct PackageReleasePublishStageParsedDocument {
  std::filesystem::path planPath;
  std::filesystem::path stagePath;
  bool success = false;
  std::size_t packageCount = 0;
  std::size_t artifactCount = 0;
  std::uintmax_t totalArtifactBytes = 0;
  std::size_t stagedArtifactCount = 0;
  std::uintmax_t stagedArtifactBytes = 0;
  std::vector<PackageReleasePublishStageArtifact> artifacts;
};

struct PackageReleasePublishUploadManifestParsedDocument {
  std::size_t requestCount = 0;
  std::uintmax_t requestBytes = 0;
  std::vector<PackageReleasePublishUploadRequest> requests;
};

bool isJsonNullValue(std::string_view text) {
  return canonicalJson(text) == "null";
}

bool isSha256Digest(std::string_view value) {
  return value.size() == 64 &&
         std::all_of(value.begin(), value.end(), [](char ch) {
           return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
         });
}

bool isReleaseBundleTarget(std::string_view target) {
  return target == "metal" || target == "vulkan" || target == "directx" ||
         target == "opengl";
}

bool isReleaseBundleNativeBinaryStatus(std::string_view status) {
  return status == "planned" || status == "emitted" || status == "validated";
}

bool isReleasePackageArtifactRequirementMode(std::string_view mode) {
  return mode == "native" || mode == "source-package";
}

bool isReleasePackageArtifactRequirementName(std::string_view name) {
  return name == "backendSource" || name == "backendAssembly" ||
         name == "intermediate" || name == "nativeBinary";
}

bool isReleaseNativeReadyStatus(std::string_view status) {
  return status == "emitted" || status == "validated";
}

std::optional<std::vector<std::string>>
parseRequiredStringArrayMember(std::string_view object, std::string_view key,
                               const std::filesystem::path &documentPath,
                               DiagnosticEngine &diagnostics,
                               std::string_view missingCode,
                               std::string_view invalidCode,
                               std::string_view label) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(std::string(missingCode),
                      std::string(label) + " requires string array field: " +
                          std::string(key),
                      pathLocation(documentPath));
    return std::nullopt;
  }

  std::vector<std::string> values;
  std::size_t position = 0;
  skipWhitespace(*valueText, position);
  if (position >= valueText->size() || (*valueText)[position] != '[') {
    diagnostics.error(std::string(invalidCode),
                      std::string(label) + " field must be a string array: " +
                          std::string(key),
                      pathLocation(documentPath));
    return std::nullopt;
  }
  ++position;
  skipWhitespace(*valueText, position);
  if (position < valueText->size() && (*valueText)[position] == ']') {
    ++position;
    skipWhitespace(*valueText, position);
    if (position == valueText->size()) {
      return values;
    }
    diagnostics.error(std::string(invalidCode),
                      std::string(label) + " field is not a valid string "
                                           "array: " +
                          std::string(key),
                      pathLocation(documentPath));
    return std::nullopt;
  }

  while (position < valueText->size()) {
    std::string value;
    if (!parseJsonString(*valueText, position, value)) {
      diagnostics.error(std::string(invalidCode),
                        std::string(label) + " " + std::string(key) +
                            " entries must be strings",
                        pathLocation(documentPath));
      return std::nullopt;
    }
    values.push_back(std::move(value));
    skipWhitespace(*valueText, position);
    if (position < valueText->size() && (*valueText)[position] == ',') {
      ++position;
      skipWhitespace(*valueText, position);
      continue;
    }
    if (position < valueText->size() && (*valueText)[position] == ']') {
      ++position;
      skipWhitespace(*valueText, position);
      if (position == valueText->size()) {
        return values;
      }
    }
    diagnostics.error(std::string(invalidCode),
                      std::string(label) + " field is not a valid string "
                                           "array: " +
                          std::string(key),
                      pathLocation(documentPath));
    return std::nullopt;
  }

  diagnostics.error(std::string(invalidCode),
                    std::string(label) + " field is not a valid string "
                                         "array: " +
                        std::string(key),
                    pathLocation(documentPath));
  return std::nullopt;
}

std::optional<std::string> parseRequiredReleaseBundleStringMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &bundlePath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(releaseBundleDiagnosticCode("missing-field"),
                      "package release bundle requires string field: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  std::size_t position = 0;
  std::string parsed;
  if (!parseJsonString(*valueText, position, parsed)) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle field must be a string: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  skipWhitespace(*valueText, position);
  if (position != valueText->size()) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle field must be a string: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  return parsed;
}

std::optional<bool> parseRequiredReleaseBundleBoolMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &bundlePath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(releaseBundleDiagnosticCode("missing-field"),
                      "package release bundle requires boolean field: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  const std::optional<bool> parsed = parseBool(*valueText);
  if (!parsed) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle field must be boolean: " +
                          std::string(key),
                      pathLocation(bundlePath));
  }
  return parsed;
}

std::optional<std::size_t> parseRequiredReleaseBundleCountMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &bundlePath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(releaseBundleDiagnosticCode("missing-field"),
                      "package release bundle requires count field: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  const std::optional<std::uintmax_t> parsed = parseUnsignedInteger(*valueText);
  if (!parsed || *parsed > std::numeric_limits<std::size_t>::max()) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle field must be a non-negative "
                      "integer: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  return static_cast<std::size_t>(*parsed);
}

std::optional<std::uintmax_t> parseRequiredReleaseBundleByteCountMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &bundlePath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(releaseBundleDiagnosticCode("missing-field"),
                      "package release bundle requires count field: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  const std::optional<std::uintmax_t> parsed = parseUnsignedInteger(*valueText);
  if (!parsed) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle field must be a non-negative "
                      "integer: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  return *parsed;
}

bool parseRequiredNullableReleaseBundleCountMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &bundlePath, DiagnosticEngine &diagnostics,
    std::optional<std::uintmax_t> &out) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(releaseBundleDiagnosticCode("missing-field"),
                      "package release bundle requires nullable count field: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return false;
  }
  if (isJsonNullValue(*valueText)) {
    out = std::nullopt;
    return true;
  }
  const std::optional<std::uintmax_t> parsed = parseUnsignedInteger(*valueText);
  if (!parsed) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle field must be a non-negative "
                      "integer or null: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return false;
  }
  out = *parsed;
  return true;
}

bool parseRequiredNullableReleaseBundleStringMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &bundlePath, DiagnosticEngine &diagnostics,
    std::optional<std::string> &out) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(
        releaseBundleDiagnosticCode("missing-field"),
        "package release bundle requires nullable string field: " +
            std::string(key),
        pathLocation(bundlePath));
    return false;
  }
  if (isJsonNullValue(*valueText)) {
    out = std::nullopt;
    return true;
  }
  std::size_t position = 0;
  std::string parsed;
  if (!parseJsonString(*valueText, position, parsed)) {
    diagnostics.error(
        releaseBundleDiagnosticCode("invalid-field"),
        "package release bundle field must be a string or null: " +
            std::string(key),
        pathLocation(bundlePath));
    return false;
  }
  skipWhitespace(*valueText, position);
  if (position != valueText->size()) {
    diagnostics.error(
        releaseBundleDiagnosticCode("invalid-field"),
        "package release bundle field must be a string or null: " +
            std::string(key),
        pathLocation(bundlePath));
    return false;
  }
  out = std::move(parsed);
  return true;
}

std::optional<std::vector<std::string_view>>
parseReleaseBundleObjectArray(std::string_view arrayText, std::string_view key,
                              const std::filesystem::path &bundlePath,
                              DiagnosticEngine &diagnostics) {
  std::vector<std::string_view> elements;
  std::size_t position = 0;
  skipWhitespace(arrayText, position);
  if (position >= arrayText.size() || arrayText[position] != '[') {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle field must be an array: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  ++position;
  skipWhitespace(arrayText, position);
  if (position < arrayText.size() && arrayText[position] == ']') {
    ++position;
    skipWhitespace(arrayText, position);
    if (position == arrayText.size()) {
      return elements;
    }
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle field is not a valid array: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return std::nullopt;
  }

  while (position < arrayText.size()) {
    const std::size_t objectBegin = position;
    if (!skipJsonObject(arrayText, position)) {
      diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                        "package release bundle " + std::string(key) +
                            " entries must be JSON objects",
                        pathLocation(bundlePath));
      return std::nullopt;
    }
    elements.push_back(arrayText.substr(objectBegin, position - objectBegin));
    skipWhitespace(arrayText, position);
    if (position < arrayText.size() && arrayText[position] == ',') {
      ++position;
      skipWhitespace(arrayText, position);
      continue;
    }
    if (position < arrayText.size() && arrayText[position] == ']') {
      ++position;
      skipWhitespace(arrayText, position);
      if (position == arrayText.size()) {
        return elements;
      }
    }
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle field is not a valid array: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return std::nullopt;
  }

  diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                    "package release bundle field is not a valid array: " +
                        std::string(key),
                    pathLocation(bundlePath));
  return std::nullopt;
}

std::optional<std::vector<std::string_view>>
parseRequiredReleaseBundleObjectArrayMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &bundlePath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(releaseBundleDiagnosticCode("missing-field"),
                      "package release bundle requires array field: " +
                          std::string(key),
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  return parseReleaseBundleObjectArray(*valueText, key, bundlePath,
                                       diagnostics);
}

std::optional<std::string> parseRequiredReleasePublishStringMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &planPath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(releasePublishDiagnosticCode("missing-field"),
                      "package release publish document requires string "
                      "field: " +
                          std::string(key),
                      pathLocation(planPath));
    return std::nullopt;
  }
  std::size_t position = 0;
  std::string parsed;
  if (!parseJsonString(*valueText, position, parsed)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish document field must be a "
                      "string: " +
                          std::string(key),
                      pathLocation(planPath));
    return std::nullopt;
  }
  skipWhitespace(*valueText, position);
  if (position != valueText->size()) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish document field must be a "
                      "string: " +
                          std::string(key),
                      pathLocation(planPath));
    return std::nullopt;
  }
  return parsed;
}

bool parseRequiredNullableReleasePublishStringMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &planPath, DiagnosticEngine &diagnostics,
    std::optional<std::string> &out) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(
        releasePublishDiagnosticCode("missing-field"),
        "package release publish document requires nullable string field: " +
            std::string(key),
        pathLocation(planPath));
    return false;
  }
  if (isJsonNullValue(*valueText)) {
    out = std::nullopt;
    return true;
  }
  std::size_t position = 0;
  std::string parsed;
  if (!parseJsonString(*valueText, position, parsed)) {
    diagnostics.error(
        releasePublishDiagnosticCode("invalid-field"),
        "package release publish document field must be a string or null: " +
            std::string(key),
        pathLocation(planPath));
    return false;
  }
  skipWhitespace(*valueText, position);
  if (position != valueText->size()) {
    diagnostics.error(
        releasePublishDiagnosticCode("invalid-field"),
        "package release publish document field must be a string or null: " +
            std::string(key),
        pathLocation(planPath));
    return false;
  }
  out = std::move(parsed);
  return true;
}

void appendReleasePublishVectorError(std::vector<Diagnostic> &diagnostics,
                                     std::string_view suffix,
                                     std::string message,
                                     const std::filesystem::path &path) {
  Diagnostic diagnostic;
  diagnostic.severity = DiagnosticSeverity::Error;
  diagnostic.code = releasePublishDiagnosticCode(suffix);
  diagnostic.message = std::move(message);
  diagnostic.location = pathLocation(path);
  diagnostics.push_back(std::move(diagnostic));
}

bool parseOptionalReleasePublishStringMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &documentPath,
    std::vector<Diagnostic> &diagnostics, std::optional<std::string> &out) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    out = std::nullopt;
    return true;
  }
  std::size_t position = 0;
  std::string parsed;
  if (!parseJsonString(*valueText, position, parsed)) {
    appendReleasePublishVectorError(
        diagnostics, "invalid-field",
        "package release publish document field must be a string: " +
            std::string(key),
        documentPath);
    return false;
  }
  skipWhitespace(*valueText, position);
  if (position != valueText->size()) {
    appendReleasePublishVectorError(
        diagnostics, "invalid-field",
        "package release publish document field must be a string: " +
            std::string(key),
        documentPath);
    return false;
  }
  out = std::move(parsed);
  return true;
}

std::optional<bool> parseRequiredReleasePublishBoolMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &planPath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(releasePublishDiagnosticCode("missing-field"),
                      "package release publish document requires boolean "
                      "field: " +
                          std::string(key),
                      pathLocation(planPath));
    return std::nullopt;
  }
  const std::optional<bool> parsed = parseBool(*valueText);
  if (!parsed) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish document field must be "
                      "boolean: " +
                          std::string(key),
                      pathLocation(planPath));
  }
  return parsed;
}

std::optional<std::size_t> parseRequiredReleasePublishCountMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &planPath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(releasePublishDiagnosticCode("missing-field"),
                      "package release publish document requires count "
                      "field: " +
                          std::string(key),
                      pathLocation(planPath));
    return std::nullopt;
  }
  const std::optional<std::uintmax_t> parsed = parseUnsignedInteger(*valueText);
  if (!parsed || *parsed > std::numeric_limits<std::size_t>::max()) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish document field must be a "
                      "non-negative integer: " +
                          std::string(key),
                      pathLocation(planPath));
    return std::nullopt;
  }
  return static_cast<std::size_t>(*parsed);
}

std::optional<std::uintmax_t> parseRequiredReleasePublishByteCountMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &planPath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(releasePublishDiagnosticCode("missing-field"),
                      "package release publish document requires count "
                      "field: " +
                          std::string(key),
                      pathLocation(planPath));
    return std::nullopt;
  }
  const std::optional<std::uintmax_t> parsed = parseUnsignedInteger(*valueText);
  if (!parsed) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish document field must be a "
                      "non-negative integer: " +
                          std::string(key),
                      pathLocation(planPath));
    return std::nullopt;
  }
  return *parsed;
}

std::optional<std::vector<std::string_view>>
parseReleasePublishObjectArray(std::string_view arrayText, std::string_view key,
                               const std::filesystem::path &planPath,
                               DiagnosticEngine &diagnostics) {
  std::vector<std::string_view> elements;
  std::size_t position = 0;
  skipWhitespace(arrayText, position);
  if (position >= arrayText.size() || arrayText[position] != '[') {
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish document field must be an "
                      "array: " +
                          std::string(key),
                      pathLocation(planPath));
    return std::nullopt;
  }
  ++position;
  skipWhitespace(arrayText, position);
  if (position < arrayText.size() && arrayText[position] == ']') {
    ++position;
    skipWhitespace(arrayText, position);
    if (position == arrayText.size()) {
      return elements;
    }
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish document field is not a valid "
                      "array: " +
                          std::string(key),
                      pathLocation(planPath));
    return std::nullopt;
  }

  while (position < arrayText.size()) {
    const std::size_t objectBegin = position;
    if (!skipJsonObject(arrayText, position)) {
      diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                        "package release publish document " + std::string(key) +
                            " entries must be JSON objects",
                        pathLocation(planPath));
      return std::nullopt;
    }
    elements.push_back(arrayText.substr(objectBegin, position - objectBegin));
    skipWhitespace(arrayText, position);
    if (position < arrayText.size() && arrayText[position] == ',') {
      ++position;
      skipWhitespace(arrayText, position);
      continue;
    }
    if (position < arrayText.size() && arrayText[position] == ']') {
      ++position;
      skipWhitespace(arrayText, position);
      if (position == arrayText.size()) {
        return elements;
      }
    }
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish document field is not a valid "
                      "array: " +
                          std::string(key),
                      pathLocation(planPath));
    return std::nullopt;
  }

  diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                    "package release publish document field is not a valid "
                    "array: " +
                        std::string(key),
                    pathLocation(planPath));
  return std::nullopt;
}

std::optional<std::vector<std::string_view>>
parseRequiredReleasePublishObjectArrayMember(
    std::string_view object, std::string_view key,
    const std::filesystem::path &planPath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText) {
    diagnostics.error(releasePublishDiagnosticCode("missing-field"),
                      "package release publish document requires array "
                      "field: " +
                          std::string(key),
                      pathLocation(planPath));
    return std::nullopt;
  }
  return parseReleasePublishObjectArray(*valueText, key, planPath, diagnostics);
}

bool isReleasePublishRelativePath(std::string_view value) {
  if (value.empty()) {
    return false;
  }
  if (value.find('\\') != std::string_view::npos) {
    return false;
  }
  const std::filesystem::path path{std::string(value)};
  if (path.is_absolute()) {
    return false;
  }
  const std::string normalized = path.lexically_normal().generic_string();
  if (normalized.empty() || normalized == "." ||
      normalized != path.generic_string()) {
    return false;
  }
  for (const std::filesystem::path &part : path) {
    const std::string text = part.generic_string();
    if (text == "." || text == ".." || text.empty()) {
      return false;
    }
  }
  return true;
}

std::optional<PackageReleasePublishPlanArtifact>
parseReleasePublishPlanArtifact(std::string_view artifactObject,
                                const std::filesystem::path &planPath,
                                DiagnosticEngine &diagnostics) {
  const std::optional<std::string> name =
      parseRequiredReleasePublishStringMember(artifactObject, "name", planPath,
                                              diagnostics);
  const std::optional<std::string> packagePath =
      parseRequiredReleasePublishStringMember(artifactObject, "packagePath",
                                              planPath, diagnostics);
  const std::optional<std::string> module =
      parseRequiredReleasePublishStringMember(artifactObject, "module",
                                              planPath, diagnostics);
  const std::optional<std::string> target =
      parseRequiredReleasePublishStringMember(artifactObject, "target",
                                              planPath, diagnostics);
  const std::optional<std::string> sourcePath =
      parseRequiredReleasePublishStringMember(artifactObject, "sourcePath",
                                              planPath, diagnostics);
  const std::optional<std::string> packageArtifactPath =
      parseRequiredReleasePublishStringMember(
          artifactObject, "packageArtifactPath", planPath, diagnostics);
  const std::optional<std::string> destinationPath =
      parseRequiredReleasePublishStringMember(artifactObject, "destinationPath",
                                              planPath, diagnostics);
  const std::optional<std::uintmax_t> sizeBytes =
      parseRequiredReleasePublishByteCountMember(artifactObject, "sizeBytes",
                                                 planPath, diagnostics);
  const std::optional<std::string> sha256Digest =
      parseRequiredReleasePublishStringMember(artifactObject, "sha256",
                                              planPath, diagnostics);
  if (!name || !packagePath || !module || !target || !sourcePath ||
      !packageArtifactPath || !destinationPath || !sizeBytes || !sha256Digest) {
    return std::nullopt;
  }
  if (name->empty() || packagePath->empty() || module->empty() ||
      sourcePath->empty()) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-artifact"),
                      "package release publish artifacts require non-empty "
                      "name, packagePath, module, and sourcePath",
                      pathLocation(planPath));
    return std::nullopt;
  }
  if (!isReleaseBundleTarget(*target)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-artifact"),
                      "package release publish artifact target is not "
                      "recognized",
                      pathLocation(planPath));
    return std::nullopt;
  }
  if (!isReleasePublishRelativePath(*packageArtifactPath)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-artifact"),
                      "package release publish packageArtifactPath must be "
                      "normalized and package-relative",
                      pathLocation(planPath));
    return std::nullopt;
  }
  if (!isReleasePublishRelativePath(*destinationPath)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-artifact"),
                      "package release publish destinationPath must be "
                      "normalized and relative",
                      pathLocation(planPath));
    return std::nullopt;
  }
  if (!isSha256Digest(*sha256Digest)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-artifact"),
                      "package release publish artifact sha256 must be a "
                      "lowercase SHA-256 digest",
                      pathLocation(planPath));
    return std::nullopt;
  }

  PackageReleasePublishPlanArtifact artifact;
  artifact.name = *name;
  artifact.packagePath = releasePromotionReferencedPath(*packagePath);
  artifact.module = *module;
  artifact.target = *target;
  artifact.sourcePath = releasePromotionReferencedPath(*sourcePath);
  artifact.packageArtifactPath = *packageArtifactPath;
  artifact.destinationPath = *destinationPath;
  artifact.sizeBytes = *sizeBytes;
  artifact.sha256 = *sha256Digest;
  return artifact;
}

bool parseReleasePublishSourceHash(
    std::string_view packageObject, const std::filesystem::path &planPath,
    DiagnosticEngine &diagnostics,
    std::optional<PackageReleasePromotionSourceHash> &out) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(packageObject, "sourceHash");
  if (!valueText) {
    diagnostics.error(releasePublishDiagnosticCode("missing-field"),
                      "package release publish plan package requires "
                      "sourceHash",
                      pathLocation(planPath));
    return false;
  }
  if (isJsonNullValue(*valueText)) {
    out = std::nullopt;
    return true;
  }
  if (!isJsonObjectDocument(*valueText)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish plan package sourceHash must "
                      "be an object or null",
                      pathLocation(planPath));
    return false;
  }
  const std::optional<std::string> algorithm =
      objectStringMember(*valueText, "algorithm");
  const std::optional<std::string> value =
      objectStringMember(*valueText, "value");
  if (!algorithm || !value || *algorithm != "sha256" ||
      !isSha256Digest(*value)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish plan package sourceHash must "
                      "contain sha256 algorithm and digest",
                      pathLocation(planPath));
    return false;
  }
  out = PackageReleasePromotionSourceHash{*algorithm, *value};
  return true;
}

bool parseReleasePublishNativeBinaryStatus(
    std::string_view packageObject, const std::filesystem::path &planPath,
    DiagnosticEngine &diagnostics, std::optional<std::string> &status) {
  if (!parseRequiredNullableReleasePublishStringMember(
          packageObject, "nativeBinaryStatus", planPath, diagnostics,
          status)) {
    return false;
  }
  if (status && !isReleaseBundleNativeBinaryStatus(*status)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish plan nativeBinaryStatus is not "
                      "recognized",
                      pathLocation(planPath));
    return false;
  }
  return true;
}

std::optional<PackageReleasePackageArtifactRequirements>
parseReleasePublishArtifactRequirements(
    std::string_view packageObject, std::string_view packageTarget,
    const std::filesystem::path &planPath, DiagnosticEngine &diagnostics);

std::optional<PackageReleasePublishPlanPackage>
parseReleasePublishPlanPackage(std::string_view packageObject,
                               const std::filesystem::path &planPath,
                               DiagnosticEngine &diagnostics) {
  const std::optional<std::string> packagePath =
      parseRequiredReleasePublishStringMember(packageObject, "packagePath",
                                              planPath, diagnostics);
  const std::optional<std::string> module =
      parseRequiredReleasePublishStringMember(packageObject, "module", planPath,
                                              diagnostics);
  const std::optional<std::string> target =
      parseRequiredReleasePublishStringMember(packageObject, "target", planPath,
                                              diagnostics);
  const std::optional<std::size_t> artifactCount =
      parseRequiredReleasePublishCountMember(packageObject, "artifactCount",
                                             planPath, diagnostics);
  const std::optional<std::uintmax_t> totalArtifactBytes =
      parseRequiredReleasePublishByteCountMember(
          packageObject, "totalArtifactBytes", planPath, diagnostics);
  std::optional<PackageReleasePromotionSourceHash> sourceHash;
  const bool sourceHashOk =
      parseReleasePublishSourceHash(packageObject, planPath, diagnostics,
                                    sourceHash);
  std::optional<std::string> nativeBinaryStatus;
  const bool nativeStatusOk = parseReleasePublishNativeBinaryStatus(
      packageObject, planPath, diagnostics, nativeBinaryStatus);
  std::optional<PackageReleasePackageArtifactRequirements>
      artifactRequirements;
  if (target) {
    artifactRequirements = parseReleasePublishArtifactRequirements(
        packageObject, *target, planPath, diagnostics);
  }
  const std::optional<std::vector<std::string_view>> artifacts =
      parseRequiredReleasePublishObjectArrayMember(packageObject, "artifacts",
                                                   planPath, diagnostics);
  if (!packagePath || !module || !target || !artifactCount ||
      !totalArtifactBytes || !sourceHashOk || !nativeStatusOk ||
      !artifactRequirements || !artifacts) {
    return std::nullopt;
  }
  if (packagePath->empty() || module->empty()) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-package"),
                      "package release publish plan packages require "
                      "non-empty packagePath and module",
                      pathLocation(planPath));
    return std::nullopt;
  }
  if (!isReleaseBundleTarget(*target)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-package"),
                      "package release publish plan package target is not "
                      "recognized",
                      pathLocation(planPath));
    return std::nullopt;
  }

  PackageReleasePublishPlanPackage package;
  package.packagePath = releasePromotionReferencedPath(*packagePath);
  package.module = *module;
  package.target = *target;
  package.sourceHash = sourceHash;
  package.nativeBinaryStatus = nativeBinaryStatus;
  package.artifactRequirements = std::move(*artifactRequirements);
  package.totalArtifactBytes = *totalArtifactBytes;
  for (std::string_view artifactObject : *artifacts) {
    std::optional<PackageReleasePublishPlanArtifact> artifact =
        parseReleasePublishPlanArtifact(artifactObject, planPath, diagnostics);
    if (!artifact) {
      return std::nullopt;
    }
    package.artifacts.push_back(std::move(*artifact));
  }
  if (package.artifacts.size() != *artifactCount) {
    diagnostics.error(releasePublishDiagnosticCode("inconsistent-counts"),
                      "package release publish plan package artifactCount "
                      "must match artifacts",
                      pathLocation(planPath));
  }
  return package;
}

std::optional<PackageReleasePublishStageArtifact>
parseReleasePublishStageArtifact(std::string_view artifactObject,
                                 const std::filesystem::path &reportPath,
                                 DiagnosticEngine &diagnostics) {
  std::optional<PackageReleasePublishPlanArtifact> artifact =
      parseReleasePublishPlanArtifact(artifactObject, reportPath, diagnostics);
  const std::optional<std::string> stagedPath =
      parseRequiredReleasePublishStringMember(artifactObject, "stagedPath",
                                              reportPath, diagnostics);
  const std::optional<bool> staged = parseRequiredReleasePublishBoolMember(
      artifactObject, "staged", reportPath, diagnostics);
  if (!artifact || !stagedPath || !staged) {
    return std::nullopt;
  }
  if (stagedPath->empty()) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-artifact"),
                      "package release publish stagedPath must be non-empty",
                      pathLocation(reportPath));
    return std::nullopt;
  }

  PackageReleasePublishStageArtifact parsed;
  parsed.artifact = std::move(*artifact);
  parsed.stagedPath = releasePromotionReferencedPath(*stagedPath);
  parsed.staged = *staged;
  return parsed;
}

std::optional<PackageReleasePublishUploadRequest>
parseReleasePublishUploadRequest(std::string_view requestObject,
                                 const std::filesystem::path &manifestPath,
                                 DiagnosticEngine &diagnostics) {
  const std::optional<std::string> targetKind =
      parseRequiredReleasePublishStringMember(requestObject, "targetKind",
                                              manifestPath, diagnostics);
  const std::optional<std::string> stagedPath =
      parseRequiredReleasePublishStringMember(requestObject, "stagedPath",
                                              manifestPath, diagnostics);
  const std::optional<std::string> destinationPath =
      parseRequiredReleasePublishStringMember(requestObject, "destinationPath",
                                              manifestPath, diagnostics);
  const std::optional<std::string> bucket =
      parseRequiredReleasePublishStringMember(requestObject, "bucket",
                                              manifestPath, diagnostics);
  const std::optional<std::string> objectName =
      parseRequiredReleasePublishStringMember(requestObject, "objectName",
                                              manifestPath, diagnostics);
  const std::optional<std::string> uploadUri =
      parseRequiredReleasePublishStringMember(requestObject, "uploadUri",
                                              manifestPath, diagnostics);
  const std::optional<std::string> credentialsEnv =
      parseRequiredReleasePublishStringMember(requestObject, "credentialsEnv",
                                              manifestPath, diagnostics);
  const std::optional<std::uintmax_t> sizeBytes =
      parseRequiredReleasePublishByteCountMember(requestObject, "sizeBytes",
                                                 manifestPath, diagnostics);
  const std::optional<std::string> sha256Digest =
      parseRequiredReleasePublishStringMember(requestObject, "sha256",
                                              manifestPath, diagnostics);
  if (!targetKind || !stagedPath || !destinationPath || !bucket ||
      !objectName || !uploadUri || !credentialsEnv || !sizeBytes ||
      !sha256Digest) {
    return std::nullopt;
  }

  if (*targetKind != "gcs" || stagedPath->empty() || destinationPath->empty() ||
      uploadUri->empty()) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-upload-request"),
                      "package release publish upload request requires gcs "
                      "targetKind, stagedPath, destinationPath, and uploadUri",
                      pathLocation(manifestPath));
    return std::nullopt;
  }
  if (credentialsEnv->empty()) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-upload-request"),
                      "package release publish gcs upload request requires "
                      "credentialsEnv",
                      pathLocation(manifestPath));
    return std::nullopt;
  }
  if (bucket->empty() || objectName->empty()) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-upload-request"),
                      "package release publish gcs upload request requires "
                      "bucket and objectName",
                      pathLocation(manifestPath));
    return std::nullopt;
  }
  if (!isReleasePublishRelativePath(*destinationPath)) {
    diagnostics.error(
        releasePublishDiagnosticCode("invalid-upload-request"),
        "package release publish upload request destinationPath must be "
        "normalized and relative",
        pathLocation(manifestPath));
    return std::nullopt;
  }
  if (!isReleasePublishRelativePath(*objectName)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-upload-request"),
                      "package release publish upload request objectName must "
                      "be normalized and relative",
                      pathLocation(manifestPath));
    return std::nullopt;
  }
  if (*objectName == *destinationPath) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-upload-request"),
                      "package release publish upload request objectName must "
                      "include a non-root object prefix",
                      pathLocation(manifestPath));
    return std::nullopt;
  }
  if (!releasePublishObjectNameEndsWithDestination(*objectName,
                                                   *destinationPath)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-upload-request"),
                      "package release publish upload request objectName must "
                      "end with destinationPath",
                      pathLocation(manifestPath));
    return std::nullopt;
  }
  if (*uploadUri != "gs://" + *bucket + "/" + *objectName) {
    diagnostics.error(
        releasePublishDiagnosticCode("invalid-upload-request"),
        "package release publish upload request uploadUri must match "
        "gs://bucket/objectName",
        pathLocation(manifestPath));
    return std::nullopt;
  }
  if (!isSha256Digest(*sha256Digest)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-upload-request"),
                      "package release publish upload request sha256 must be "
                      "a lowercase SHA-256 digest",
                      pathLocation(manifestPath));
    return std::nullopt;
  }

  PackageReleasePublishUploadRequest request;
  request.targetKind = *targetKind;
  request.stagedPath = releasePromotionReferencedPath(*stagedPath);
  request.destinationPath = *destinationPath;
  request.bucket = *bucket;
  request.objectName = *objectName;
  request.uploadUri = *uploadUri;
  request.credentialsEnv = *credentialsEnv;
  request.sizeBytes = *sizeBytes;
  request.sha256 = *sha256Digest;
  return request;
}

bool parseReleaseBundleSourceHash(
    std::string_view packageObject, const std::filesystem::path &bundlePath,
    DiagnosticEngine &diagnostics,
    std::optional<PackageReleasePromotionSourceHash> &out) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(packageObject, "sourceHash");
  if (!valueText) {
    diagnostics.error(releaseBundleDiagnosticCode("missing-field"),
                      "package release bundle package requires sourceHash",
                      pathLocation(bundlePath));
    return false;
  }
  if (isJsonNullValue(*valueText)) {
    out = std::nullopt;
    return true;
  }
  if (!isJsonObjectDocument(*valueText)) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle package sourceHash must be an "
                      "object or null",
                      pathLocation(bundlePath));
    return false;
  }
  const std::optional<std::string> algorithm =
      objectStringMember(*valueText, "algorithm");
  const std::optional<std::string> value =
      objectStringMember(*valueText, "value");
  if (!algorithm || !value || *algorithm != "sha256" ||
      !isSha256Digest(*value)) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle package sourceHash must contain "
                      "sha256 algorithm and digest",
                      pathLocation(bundlePath));
    return false;
  }
  out = PackageReleasePromotionSourceHash{*algorithm, *value};
  return true;
}

bool parseReleaseBundleNativeBinaryStatus(
    std::string_view packageObject, const std::filesystem::path &bundlePath,
    DiagnosticEngine &diagnostics, std::optional<std::string> &status) {
  if (!parseRequiredNullableReleaseBundleStringMember(
          packageObject, "nativeBinaryStatus", bundlePath, diagnostics,
          status)) {
    return false;
  }
  if (status && !isReleaseBundleNativeBinaryStatus(*status)) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle nativeBinaryStatus is not "
                      "recognized",
                      pathLocation(bundlePath));
    return false;
  }
  return true;
}

bool validateReleasePackageArtifactRequirements(
    const PackageReleasePackageArtifactRequirements &requirements,
    std::string_view packageTarget, const std::filesystem::path &documentPath,
    DiagnosticEngine &diagnostics, std::string_view invalidCode,
    std::string_view label) {
  bool valid = true;
  if (requirements.target != packageTarget) {
    diagnostics.error(std::string(invalidCode),
                      std::string(label) +
                          " packageArtifactRequirements.target must match "
                          "package target",
                      pathLocation(documentPath));
    valid = false;
  }
  if (!isReleasePackageArtifactRequirementMode(requirements.packageMode)) {
    diagnostics.error(std::string(invalidCode),
                      std::string(label) +
                          " packageArtifactRequirements.packageMode is not "
                          "recognized",
                      pathLocation(documentPath));
    valid = false;
  }
  if (requirements.requiredPathArtifacts.empty()) {
    diagnostics.error(std::string(invalidCode),
                      std::string(label) +
                          " packageArtifactRequirements.requiredPathArtifacts "
                          "must not be empty",
                      pathLocation(documentPath));
    valid = false;
  }
  std::vector<std::string> sortedNames = requirements.requiredPathArtifacts;
  std::sort(sortedNames.begin(), sortedNames.end());
  for (std::size_t index = 0; index < sortedNames.size(); ++index) {
    if (!isReleasePackageArtifactRequirementName(sortedNames[index])) {
      diagnostics.error(std::string(invalidCode),
                        std::string(label) +
                            " packageArtifactRequirements contains unknown "
                            "required path artifact: " +
                            sortedNames[index],
                        pathLocation(documentPath));
      valid = false;
    }
    if (index != 0 && sortedNames[index - 1] == sortedNames[index]) {
      diagnostics.error(std::string(invalidCode),
                        std::string(label) +
                            " packageArtifactRequirements required path "
                            "artifacts must be unique",
                        pathLocation(documentPath));
      valid = false;
      break;
    }
  }
  if (requirements.allowsPlannedNativeSourceEvidence &&
      !requirements.allowsPlannedNativeBinary) {
    diagnostics.error(std::string(invalidCode),
                      std::string(label) +
                          " packageArtifactRequirements planned source "
                          "evidence requires planned native binary support",
                      pathLocation(documentPath));
    valid = false;
  }
  const PackageTargetContract *contract =
      packageTargetContractFor(packageTarget);
  if (contract != nullptr) {
    const std::string_view expectedMode =
        contract->allowsPlannedNativeBinary ? "source-package" : "native";
    if (requirements.packageMode != expectedMode) {
      diagnostics.error(
          std::string(invalidCode),
          std::string(label) +
              " packageArtifactRequirements.packageMode must match target "
              "contract",
          pathLocation(documentPath));
      valid = false;
    }
    bool artifactContractMatches =
        requirements.requiredPathArtifacts.size() ==
        contract->requiredArtifactCount;
    for (std::size_t index = 0;
         artifactContractMatches && index < contract->requiredArtifactCount;
         ++index) {
      artifactContractMatches =
          std::string_view(requirements.requiredPathArtifacts[index]) ==
          contract->requiredArtifacts[index];
    }
    if (!artifactContractMatches) {
      diagnostics.error(
          std::string(invalidCode),
          std::string(label) +
              " packageArtifactRequirements.requiredPathArtifacts must match "
              "target contract",
          pathLocation(documentPath));
      valid = false;
    }
    if (requirements.requiresNativeBinaryStatus !=
            contract->requiresNativeBinaryStatus ||
        requirements.allowsPlannedNativeBinary !=
            contract->allowsPlannedNativeBinary ||
        requirements.allowsPlannedNativeSourceEvidence !=
            contract->allowsPlannedNativeSourceEvidence) {
      diagnostics.error(std::string(invalidCode),
                        std::string(label) +
                            " packageArtifactRequirements native binary "
                            "policy must match target contract",
                        pathLocation(documentPath));
      valid = false;
    }
  }
  return valid;
}

std::optional<PackageReleasePackageArtifactRequirements>
parseReleaseBundleArtifactRequirements(
    std::string_view packageObject, std::string_view packageTarget,
    const std::filesystem::path &bundlePath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(packageObject, "packageArtifactRequirements");
  if (!valueText) {
    diagnostics.error(releaseBundleDiagnosticCode("missing-field"),
                      "package release bundle package requires "
                      "packageArtifactRequirements",
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  if (!isJsonObjectDocument(*valueText)) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle packageArtifactRequirements "
                      "must be an object",
                      pathLocation(bundlePath));
    return std::nullopt;
  }

  const std::optional<std::string> target =
      parseRequiredReleaseBundleStringMember(
          *valueText, "target", bundlePath, diagnostics);
  const std::optional<std::string> packageMode =
      parseRequiredReleaseBundleStringMember(
          *valueText, "packageMode", bundlePath, diagnostics);
  const std::optional<std::vector<std::string>> requiredPathArtifacts =
      parseRequiredStringArrayMember(
          *valueText, "requiredPathArtifacts", bundlePath, diagnostics,
          releaseBundleDiagnosticCode("missing-field"),
          releaseBundleDiagnosticCode("invalid-field"),
          "package release bundle packageArtifactRequirements");
  const std::optional<bool> requiresNativeBinaryStatus =
      parseRequiredReleaseBundleBoolMember(
          *valueText, "requiresNativeBinaryStatus", bundlePath, diagnostics);
  const std::optional<bool> allowsPlannedNativeBinary =
      parseRequiredReleaseBundleBoolMember(
          *valueText, "allowsPlannedNativeBinary", bundlePath, diagnostics);
  const std::optional<bool> allowsPlannedNativeSourceEvidence =
      parseRequiredReleaseBundleBoolMember(
          *valueText, "allowsPlannedNativeSourceEvidence", bundlePath,
          diagnostics);
  if (!target || !packageMode || !requiredPathArtifacts ||
      !requiresNativeBinaryStatus || !allowsPlannedNativeBinary ||
      !allowsPlannedNativeSourceEvidence) {
    return std::nullopt;
  }

  PackageReleasePackageArtifactRequirements requirements;
  requirements.target = *target;
  requirements.packageMode = *packageMode;
  requirements.requiredPathArtifacts = *requiredPathArtifacts;
  requirements.requiresNativeBinaryStatus = *requiresNativeBinaryStatus;
  requirements.allowsPlannedNativeBinary = *allowsPlannedNativeBinary;
  requirements.allowsPlannedNativeSourceEvidence =
      *allowsPlannedNativeSourceEvidence;
  if (!validateReleasePackageArtifactRequirements(
          requirements, packageTarget, bundlePath, diagnostics,
          releaseBundleDiagnosticCode("invalid-field"),
          "package release bundle")) {
    return std::nullopt;
  }
  return requirements;
}

std::optional<PackageReleasePackageArtifactRequirements>
parseReleasePublishArtifactRequirements(
    std::string_view packageObject, std::string_view packageTarget,
    const std::filesystem::path &planPath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(packageObject, "packageArtifactRequirements");
  if (!valueText) {
    diagnostics.error(releasePublishDiagnosticCode("missing-field"),
                      "package release publish plan package requires "
                      "packageArtifactRequirements",
                      pathLocation(planPath));
    return std::nullopt;
  }
  if (!isJsonObjectDocument(*valueText)) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish plan packageArtifactRequirements "
                      "must be an object",
                      pathLocation(planPath));
    return std::nullopt;
  }

  const std::optional<std::string> target =
      parseRequiredReleasePublishStringMember(
          *valueText, "target", planPath, diagnostics);
  const std::optional<std::string> packageMode =
      parseRequiredReleasePublishStringMember(
          *valueText, "packageMode", planPath, diagnostics);
  const std::optional<std::vector<std::string>> requiredPathArtifacts =
      parseRequiredStringArrayMember(
          *valueText, "requiredPathArtifacts", planPath, diagnostics,
          releasePublishDiagnosticCode("missing-field"),
          releasePublishDiagnosticCode("invalid-field"),
          "package release publish plan packageArtifactRequirements");
  const std::optional<bool> requiresNativeBinaryStatus =
      parseRequiredReleasePublishBoolMember(
          *valueText, "requiresNativeBinaryStatus", planPath, diagnostics);
  const std::optional<bool> allowsPlannedNativeBinary =
      parseRequiredReleasePublishBoolMember(
          *valueText, "allowsPlannedNativeBinary", planPath, diagnostics);
  const std::optional<bool> allowsPlannedNativeSourceEvidence =
      parseRequiredReleasePublishBoolMember(
          *valueText, "allowsPlannedNativeSourceEvidence", planPath,
          diagnostics);
  if (!target || !packageMode || !requiredPathArtifacts ||
      !requiresNativeBinaryStatus || !allowsPlannedNativeBinary ||
      !allowsPlannedNativeSourceEvidence) {
    return std::nullopt;
  }

  PackageReleasePackageArtifactRequirements requirements;
  requirements.target = *target;
  requirements.packageMode = *packageMode;
  requirements.requiredPathArtifacts = *requiredPathArtifacts;
  requirements.requiresNativeBinaryStatus = *requiresNativeBinaryStatus;
  requirements.allowsPlannedNativeBinary = *allowsPlannedNativeBinary;
  requirements.allowsPlannedNativeSourceEvidence =
      *allowsPlannedNativeSourceEvidence;
  if (!validateReleasePackageArtifactRequirements(
          requirements, packageTarget, planPath, diagnostics,
          releasePublishDiagnosticCode("invalid-field"),
          "package release publish plan")) {
    return std::nullopt;
  }
  return requirements;
}

std::optional<PackageReleasePromotionBlocker>
parseReleaseBundleBlocker(std::string_view blockerObject,
                          const std::filesystem::path &bundlePath,
                          DiagnosticEngine &diagnostics) {
  const std::optional<std::string> code =
      parseRequiredReleaseBundleStringMember(blockerObject, "code", bundlePath,
                                             diagnostics);
  const std::optional<std::string> message =
      parseRequiredReleaseBundleStringMember(blockerObject, "message",
                                             bundlePath, diagnostics);
  const std::optional<std::size_t> count =
      parseRequiredReleaseBundleCountMember(blockerObject, "count", bundlePath,
                                            diagnostics);
  if (!code || !message || !count) {
    return std::nullopt;
  }
  if (code->empty() || message->empty() || *count == 0) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-blocker"),
                      "package release bundle blockers require non-empty code, "
                      "message, and positive count",
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  return PackageReleasePromotionBlocker{*code, *message, *count};
}

std::optional<PackageReleasePromotionArtifact>
parseReleaseBundleArtifact(std::string_view artifactObject,
                           const std::filesystem::path &bundlePath,
                           DiagnosticEngine &diagnostics) {
  const std::optional<std::string> name =
      parseRequiredReleaseBundleStringMember(artifactObject, "name", bundlePath,
                                             diagnostics);
  const std::optional<std::string> path =
      parseRequiredReleaseBundleStringMember(artifactObject, "path", bundlePath,
                                             diagnostics);
  const std::optional<bool> exists = parseRequiredReleaseBundleBoolMember(
      artifactObject, "exists", bundlePath, diagnostics);
  std::optional<std::uintmax_t> sizeBytes;
  std::optional<std::string> sha256Digest;
  const bool sizeOk = parseRequiredNullableReleaseBundleCountMember(
      artifactObject, "sizeBytes", bundlePath, diagnostics, sizeBytes);
  const bool shaOk = parseRequiredNullableReleaseBundleStringMember(
      artifactObject, "sha256", bundlePath, diagnostics, sha256Digest);
  if (!name || !path || !exists || !sizeOk || !shaOk) {
    return std::nullopt;
  }
  if (name->empty() || path->empty()) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-artifact"),
                      "package release bundle artifacts require non-empty name "
                      "and path",
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  const std::filesystem::path artifactPath(*path);
  if (artifactPath.is_absolute()) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-artifact"),
                      "package release bundle artifact paths must be "
                      "package-relative",
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  for (const std::filesystem::path &part : artifactPath) {
    if (part.generic_string() == "..") {
      diagnostics.error(releaseBundleDiagnosticCode("invalid-artifact"),
                        "package release bundle artifact paths must not "
                        "traverse parent directories",
                        pathLocation(bundlePath));
      return std::nullopt;
    }
  }
  if (sha256Digest && !isSha256Digest(*sha256Digest)) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-artifact"),
                      "package release bundle artifact sha256 must be a "
                      "lowercase SHA-256 digest",
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  if (*exists && (!sizeBytes || !sha256Digest)) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-artifact"),
                      "package release bundle existing artifacts require size "
                      "and sha256",
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  if (!*exists && (sizeBytes || sha256Digest)) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-artifact"),
                      "package release bundle missing artifacts must use null "
                      "size and sha256",
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  PackageReleasePromotionArtifact artifact;
  artifact.name = *name;
  artifact.path = *path;
  artifact.exists = *exists;
  artifact.sizeBytes = sizeBytes;
  artifact.sha256 = sha256Digest;
  return artifact;
}

std::optional<PackageReleaseBundleParsedPackage>
parseReleaseBundlePackage(std::string_view packageObject,
                          const std::filesystem::path &bundlePath,
                          DiagnosticEngine &diagnostics) {
  PackageReleaseBundleParsedPackage parsed;
  const std::optional<std::string> packagePath =
      parseRequiredReleaseBundleStringMember(packageObject, "packagePath",
                                             bundlePath, diagnostics);
  const std::optional<std::string> module =
      parseRequiredReleaseBundleStringMember(packageObject, "module",
                                             bundlePath, diagnostics);
  const std::optional<std::string> target =
      parseRequiredReleaseBundleStringMember(packageObject, "target",
                                             bundlePath, diagnostics);
  const std::optional<std::size_t> artifactCount =
      parseRequiredReleaseBundleCountMember(packageObject, "artifactCount",
                                            bundlePath, diagnostics);
  const std::optional<std::size_t> existingArtifactCount =
      parseRequiredReleaseBundleCountMember(
          packageObject, "existingArtifactCount", bundlePath, diagnostics);
  const std::optional<std::size_t> missingArtifactCount =
      parseRequiredReleaseBundleCountMember(
          packageObject, "missingArtifactCount", bundlePath, diagnostics);
  const std::optional<std::uintmax_t> totalArtifactBytes =
      parseRequiredReleaseBundleByteCountMember(
          packageObject, "totalArtifactBytes", bundlePath, diagnostics);
  std::optional<PackageReleasePromotionSourceHash> sourceHash;
  const bool sourceHashOk = parseReleaseBundleSourceHash(
      packageObject, bundlePath, diagnostics, sourceHash);
  std::optional<std::string> nativeBinaryStatus;
  const bool nativeStatusOk = parseReleaseBundleNativeBinaryStatus(
      packageObject, bundlePath, diagnostics, nativeBinaryStatus);
  std::optional<PackageReleasePackageArtifactRequirements>
      artifactRequirements;
  if (target) {
    artifactRequirements = parseReleaseBundleArtifactRequirements(
        packageObject, *target, bundlePath, diagnostics);
  }
  const std::optional<std::vector<std::string_view>> artifacts =
      parseRequiredReleaseBundleObjectArrayMember(packageObject, "artifacts",
                                                  bundlePath, diagnostics);
  if (!packagePath || !module || !target || !artifactCount ||
      !existingArtifactCount || !missingArtifactCount || !totalArtifactBytes ||
      !sourceHashOk || !nativeStatusOk || !artifactRequirements || !artifacts) {
    return std::nullopt;
  }
  if (packagePath->empty() || module->empty()) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-package"),
                      "package release bundle packages require non-empty "
                      "packagePath and module",
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  if (!isReleaseBundleTarget(*target)) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-package"),
                      "package release bundle package target is not recognized",
                      pathLocation(bundlePath));
    return std::nullopt;
  }

  parsed.package.packagePath = releasePromotionReferencedPath(*packagePath);
  parsed.package.module = *module;
  parsed.package.target = *target;
  parsed.package.sourceHash = sourceHash;
  parsed.package.nativeBinaryStatus = nativeBinaryStatus;
  parsed.package.artifactRequirements = std::move(*artifactRequirements);
  parsed.artifactCount = *artifactCount;
  parsed.existingArtifactCount = *existingArtifactCount;
  parsed.missingArtifactCount = *missingArtifactCount;
  parsed.totalArtifactBytes = *totalArtifactBytes;
  for (std::string_view artifactObject : *artifacts) {
    std::optional<PackageReleasePromotionArtifact> artifact =
        parseReleaseBundleArtifact(artifactObject, bundlePath, diagnostics);
    if (!artifact) {
      return std::nullopt;
    }
    parsed.package.artifacts.push_back(std::move(*artifact));
  }
  return parsed;
}

const PackageReleasePromotionArtifact *findReleasePromotionArtifact(
    const PackageReleasePromotionPackage &package, std::string_view name) {
  for (const PackageReleasePromotionArtifact &artifact : package.artifacts) {
    if (artifact.name == name) {
      return &artifact;
    }
  }
  return nullptr;
}

const PackageReleasePublishPlanArtifact *findReleasePublishPlanArtifact(
    const PackageReleasePublishPlanPackage &package, std::string_view name) {
  for (const PackageReleasePublishPlanArtifact &artifact : package.artifacts) {
    if (artifact.name == name) {
      return &artifact;
    }
  }
  return nullptr;
}

bool releasePackageHasNativeMode(
    const std::optional<PackageReleasePackageArtifactRequirements>
        &requirements) {
  return requirements && requirements->packageMode == "native";
}

bool releasePackageClaimsNativeReadiness(
    const PackageReleasePromotionPackage &package) {
  if (package.nativeBinaryStatus &&
      isReleaseNativeReadyStatus(*package.nativeBinaryStatus)) {
    return true;
  }
  const PackageReleasePromotionArtifact *nativeBinary =
      findReleasePromotionArtifact(package, "nativeBinary");
  return releasePackageHasNativeMode(package.artifactRequirements) &&
         nativeBinary != nullptr && nativeBinary->exists;
}

bool releasePackageClaimsNativeReadiness(
    const PackageReleasePublishPlanPackage &package) {
  if (package.nativeBinaryStatus &&
      isReleaseNativeReadyStatus(*package.nativeBinaryStatus)) {
    return true;
  }
  return releasePackageHasNativeMode(package.artifactRequirements) &&
         findReleasePublishPlanArtifact(package, "nativeBinary") != nullptr;
}

bool releasePackageAllowsPlannedNativeBinary(
    const PackageReleasePackageArtifactRequirements &requirements,
    const std::optional<std::string> &nativeBinaryStatus,
    std::string_view artifactName) {
  return artifactName == "nativeBinary" &&
         requirements.allowsPlannedNativeBinary && nativeBinaryStatus &&
         *nativeBinaryStatus == "planned";
}

void validateReleasePackageNativeDescriptorArtifact(
    const PackageReleasePromotionPackage &package,
    const std::filesystem::path &documentPath, DiagnosticEngine &diagnostics,
    std::string_view diagnosticCode, std::string_view label) {
  if (!releasePackageClaimsNativeReadiness(package)) {
    return;
  }
  const PackageReleasePromotionArtifact *descriptor =
      findReleasePromotionArtifact(package, "nativeArtifactDescriptor");
  if (descriptor == nullptr) {
    diagnostics.error(std::string(diagnosticCode),
                      std::string(label) +
                          " package native readiness requires "
                          "nativeArtifactDescriptor artifact evidence",
                      pathLocation(documentPath));
    return;
  }
  if (!descriptor->exists) {
    diagnostics.error(std::string(diagnosticCode),
                      std::string(label) +
                          " package nativeArtifactDescriptor artifact must "
                          "exist when native readiness is recorded",
                      pathLocation(documentPath));
  }
}

void validateReleasePackageNativeDescriptorArtifact(
    const PackageReleasePublishPlanPackage &package,
    const std::filesystem::path &documentPath, DiagnosticEngine &diagnostics,
    std::string_view diagnosticCode, std::string_view label) {
  if (!releasePackageClaimsNativeReadiness(package)) {
    return;
  }
  if (findReleasePublishPlanArtifact(package, "nativeArtifactDescriptor") ==
      nullptr) {
    diagnostics.error(std::string(diagnosticCode),
                      std::string(label) +
                          " package native readiness requires "
                          "nativeArtifactDescriptor artifact evidence",
                      pathLocation(documentPath));
  }
}

void validateReleasePackageArtifactsAgainstRequirements(
    const PackageReleasePromotionPackage &package,
    const std::filesystem::path &documentPath, DiagnosticEngine &diagnostics,
    std::string_view diagnosticCode, std::string_view label) {
  if (!package.artifactRequirements) {
    diagnostics.error(std::string(diagnosticCode),
                      std::string(label) +
                          " package requires packageArtifactRequirements",
                      pathLocation(documentPath));
    return;
  }

  const PackageReleasePackageArtifactRequirements &requirements =
      *package.artifactRequirements;
  validateReleasePackageArtifactRequirements(requirements, package.target,
                                             documentPath, diagnostics,
                                             diagnosticCode, label);
  for (const std::string &name : requirements.requiredPathArtifacts) {
    const PackageReleasePromotionArtifact *artifact =
        findReleasePromotionArtifact(package, name);
    if (artifact == nullptr) {
      diagnostics.error(std::string(diagnosticCode),
                        std::string(label) +
                            " package is missing required artifact: " + name,
                        pathLocation(documentPath));
      continue;
    }
    if (!artifact->exists) {
      if (releasePackageAllowsPlannedNativeBinary(
              requirements, package.nativeBinaryStatus, name)) {
        continue;
      }
      diagnostics.error(std::string(diagnosticCode),
                        std::string(label) +
                            " package declares required artifact missing: " +
                            name,
                        pathLocation(documentPath));
    }
  }

  const bool hasNativeBinary =
      findReleasePromotionArtifact(package, "nativeBinary") != nullptr;
  if (package.nativeBinaryStatus &&
      !requirements.requiresNativeBinaryStatus) {
    diagnostics.error(std::string(diagnosticCode),
                      std::string(label) +
                          " package declares nativeBinaryStatus but recorded "
                          "requirements do not allow it",
                      pathLocation(documentPath));
  } else if (package.nativeBinaryStatus && !hasNativeBinary &&
             !releasePackageAllowsPlannedNativeBinary(
                 requirements, package.nativeBinaryStatus, "nativeBinary")) {
    diagnostics.error(std::string(diagnosticCode),
                      std::string(label) +
                          " package nativeBinaryStatus requires a "
                          "nativeBinary artifact",
                      pathLocation(documentPath));
  } else if (requirements.requiresNativeBinaryStatus &&
             !package.nativeBinaryStatus) {
    diagnostics.error(std::string(diagnosticCode),
                      std::string(label) +
                          " package requirements require nativeBinaryStatus",
                      pathLocation(documentPath));
  }

  validateReleasePackageNativeDescriptorArtifact(package, documentPath,
                                                 diagnostics, diagnosticCode,
                                                 label);
}

void validateReleasePackageArtifactsAgainstRequirements(
    const PackageReleasePublishPlanPackage &package,
    const std::filesystem::path &documentPath, DiagnosticEngine &diagnostics,
    std::string_view diagnosticCode, std::string_view label) {
  if (!package.artifactRequirements) {
    diagnostics.error(std::string(diagnosticCode),
                      std::string(label) +
                          " package requires packageArtifactRequirements",
                      pathLocation(documentPath));
    return;
  }

  const PackageReleasePackageArtifactRequirements &requirements =
      *package.artifactRequirements;
  validateReleasePackageArtifactRequirements(requirements, package.target,
                                             documentPath, diagnostics,
                                             diagnosticCode, label);
  for (const std::string &name : requirements.requiredPathArtifacts) {
    if (findReleasePublishPlanArtifact(package, name) == nullptr &&
        !releasePackageAllowsPlannedNativeBinary(
            requirements, package.nativeBinaryStatus, name)) {
      diagnostics.error(std::string(diagnosticCode),
                        std::string(label) +
                            " package is missing required artifact: " + name,
                        pathLocation(documentPath));
    }
  }

  const bool hasNativeBinary =
      findReleasePublishPlanArtifact(package, "nativeBinary") != nullptr;
  if (package.nativeBinaryStatus &&
      !requirements.requiresNativeBinaryStatus) {
    diagnostics.error(std::string(diagnosticCode),
                      std::string(label) +
                          " package declares nativeBinaryStatus but recorded "
                          "requirements do not allow it",
                      pathLocation(documentPath));
  } else if (package.nativeBinaryStatus && !hasNativeBinary &&
             !releasePackageAllowsPlannedNativeBinary(
                 requirements, package.nativeBinaryStatus, "nativeBinary")) {
    diagnostics.error(std::string(diagnosticCode),
                      std::string(label) +
                          " package nativeBinaryStatus requires a "
                          "nativeBinary artifact",
                      pathLocation(documentPath));
  } else if (requirements.requiresNativeBinaryStatus &&
             !package.nativeBinaryStatus) {
    diagnostics.error(std::string(diagnosticCode),
                      std::string(label) +
                          " package requirements require nativeBinaryStatus",
                      pathLocation(documentPath));
  }

  validateReleasePackageNativeDescriptorArtifact(package, documentPath,
                                                 diagnostics, diagnosticCode,
                                                 label);
}

void validateReleaseBundleDocument(
    const PackageReleaseBundleParsedDocument &document,
    const std::filesystem::path &bundlePath, DiagnosticEngine &diagnostics) {
  if (document.bundlePath.empty() || document.promotionManifestPath.empty() ||
      document.summaryPath.empty() || document.batchPath.empty()) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle paths must be non-empty",
                      pathLocation(bundlePath));
  }
  const std::string expectedStatus =
      document.releaseEligible ? "eligible" : "blocked";
  if (document.status != expectedStatus) {
    diagnostics.error(releaseBundleDiagnosticCode("inconsistent-status"),
                      "package release bundle status must match "
                      "releaseEligible",
                      pathLocation(bundlePath));
  }
  if (document.releaseEligible && !document.blockers.empty()) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-blockers"),
                      "release eligible bundle must not have blockers",
                      pathLocation(bundlePath));
  }
  if (!document.releaseEligible && document.blockers.empty()) {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-blockers"),
                      "blocked release bundle requires at least one blocker",
                      pathLocation(bundlePath));
  }
  if (document.blockerCount != document.blockers.size()) {
    diagnostics.error(releaseBundleDiagnosticCode("inconsistent-counts"),
                      "package release bundle blockerCount must match blockers",
                      pathLocation(bundlePath));
  }
  for (std::size_t index = 1; index < document.blockers.size(); ++index) {
    if (document.blockers[index - 1].code >= document.blockers[index].code) {
      diagnostics.error(releaseBundleDiagnosticCode("invalid-blockers"),
                        "package release bundle blocker codes must be sorted "
                        "and unique",
                        pathLocation(bundlePath));
      break;
    }
  }
  if (document.packageCount != document.packages.size()) {
    diagnostics.error(releaseBundleDiagnosticCode("inconsistent-counts"),
                      "package release bundle packageCount must match packages",
                      pathLocation(bundlePath));
  }

  std::size_t artifactCount = 0;
  std::size_t existingArtifactCount = 0;
  std::size_t missingArtifactCount = 0;
  std::uintmax_t totalArtifactBytes = 0;
  for (std::size_t packageIndex = 0; packageIndex < document.packages.size();
       ++packageIndex) {
    const PackageReleaseBundleParsedPackage &package =
        document.packages[packageIndex];
    if (packageIndex != 0 && document.packages[packageIndex - 1]
                                     .package.packagePath.generic_string() >=
                                 package.package.packagePath.generic_string()) {
      diagnostics.error(releaseBundleDiagnosticCode("invalid-packages"),
                        "package release bundle package paths must be sorted "
                        "and unique",
                        pathLocation(bundlePath));
      break;
    }
    if (document.releaseEligible && !package.package.sourceHash) {
      diagnostics.error(releaseBundleDiagnosticCode("missing-source-hash"),
                        "release eligible package release bundle packages "
                        "require sourceHash",
                        pathLocation(bundlePath));
    }
    validateReleasePackageArtifactsAgainstRequirements(
        package.package, bundlePath, diagnostics,
        releaseBundleDiagnosticCode("artifact-requirements-mismatch"),
        "package release bundle");

    std::size_t packageExisting = 0;
    std::size_t packageMissing = 0;
    std::uintmax_t packageBytes = 0;
    for (std::size_t artifactIndex = 0;
         artifactIndex < package.package.artifacts.size(); ++artifactIndex) {
      const PackageReleasePromotionArtifact &artifact =
          package.package.artifacts[artifactIndex];
      if (artifactIndex != 0 &&
          package.package.artifacts[artifactIndex - 1].name >= artifact.name) {
        diagnostics.error(releaseBundleDiagnosticCode("invalid-artifacts"),
                          "package release bundle artifact names must be "
                          "sorted and unique",
                          pathLocation(bundlePath));
        break;
      }
      if (artifact.exists) {
        ++packageExisting;
        if (artifact.sizeBytes) {
          packageBytes += *artifact.sizeBytes;
        }
      } else {
        ++packageMissing;
      }
    }

    if (package.artifactCount != package.package.artifacts.size() ||
        package.existingArtifactCount != packageExisting ||
        package.missingArtifactCount != packageMissing ||
        package.totalArtifactBytes != packageBytes) {
      diagnostics.error(releaseBundleDiagnosticCode("inconsistent-counts"),
                        "package release bundle package artifact totals must "
                        "match artifacts",
                        pathLocation(bundlePath));
    }
    artifactCount += package.package.artifacts.size();
    existingArtifactCount += packageExisting;
    missingArtifactCount += packageMissing;
    totalArtifactBytes += packageBytes;
  }

  if (document.artifactCount != artifactCount ||
      document.existingArtifactCount != existingArtifactCount ||
      document.missingArtifactCount != missingArtifactCount ||
      document.totalArtifactBytes != totalArtifactBytes) {
    diagnostics.error(releaseBundleDiagnosticCode("inconsistent-counts"),
                      "package release bundle aggregate artifact totals must "
                      "match packages",
                      pathLocation(bundlePath));
  }
}

std::optional<PackageReleaseBundleParsedDocument>
parseReleaseBundleDocument(std::string_view text,
                           const std::filesystem::path &bundlePath,
                           DiagnosticEngine &diagnostics) {
  PackageReleaseBundleParsedDocument document;
  const std::optional<std::uintmax_t> version =
      objectUnsignedMember(text, "schemaVersion");
  if (!version) {
    diagnostics.error(releaseBundleDiagnosticCode("missing-schema-version"),
                      "package release bundle requires schemaVersion: 1",
                      pathLocation(bundlePath));
    return std::nullopt;
  }
  if (*version != 1) {
    diagnostics.error(releaseBundleDiagnosticCode("unsupported-schema-version"),
                      "package release bundle schemaVersion must be 1",
                      pathLocation(bundlePath));
    return std::nullopt;
  }

  const std::optional<std::string> bundlePathField =
      parseRequiredReleaseBundleStringMember(text, "bundlePath", bundlePath,
                                             diagnostics);
  const std::optional<std::string> promotionManifestPath =
      parseRequiredReleaseBundleStringMember(text, "promotionManifestPath",
                                             bundlePath, diagnostics);
  const std::optional<std::string> summaryPath =
      parseRequiredReleaseBundleStringMember(text, "summaryPath", bundlePath,
                                             diagnostics);
  const std::optional<std::string> batchPath =
      parseRequiredReleaseBundleStringMember(text, "batchPath", bundlePath,
                                             diagnostics);
  const std::optional<std::string> status =
      parseRequiredReleaseBundleStringMember(text, "status", bundlePath,
                                             diagnostics);
  const std::optional<bool> releaseEligible =
      parseRequiredReleaseBundleBoolMember(text, "releaseEligible", bundlePath,
                                           diagnostics);
  const std::optional<std::size_t> blockerCount =
      parseRequiredReleaseBundleCountMember(text, "blockerCount", bundlePath,
                                            diagnostics);
  const std::optional<std::size_t> packageCount =
      parseRequiredReleaseBundleCountMember(text, "packageCount", bundlePath,
                                            diagnostics);
  const std::optional<std::size_t> artifactCount =
      parseRequiredReleaseBundleCountMember(text, "artifactCount", bundlePath,
                                            diagnostics);
  const std::optional<std::size_t> existingArtifactCount =
      parseRequiredReleaseBundleCountMember(text, "existingArtifactCount",
                                            bundlePath, diagnostics);
  const std::optional<std::size_t> missingArtifactCount =
      parseRequiredReleaseBundleCountMember(text, "missingArtifactCount",
                                            bundlePath, diagnostics);
  const std::optional<std::uintmax_t> totalArtifactBytes =
      parseRequiredReleaseBundleByteCountMember(text, "totalArtifactBytes",
                                                bundlePath, diagnostics);
  const std::optional<std::vector<std::string_view>> blockers =
      parseRequiredReleaseBundleObjectArrayMember(text, "blockers", bundlePath,
                                                  diagnostics);
  const std::optional<std::vector<std::string_view>> packages =
      parseRequiredReleaseBundleObjectArrayMember(text, "packages", bundlePath,
                                                  diagnostics);
  if (!bundlePathField || !promotionManifestPath || !summaryPath ||
      !batchPath || !status || !releaseEligible || !blockerCount ||
      !packageCount || !artifactCount || !existingArtifactCount ||
      !missingArtifactCount || !totalArtifactBytes || !blockers || !packages) {
    return std::nullopt;
  }
  if (*status != "eligible" && *status != "blocked") {
    diagnostics.error(releaseBundleDiagnosticCode("invalid-field"),
                      "package release bundle status must be eligible or "
                      "blocked",
                      pathLocation(bundlePath));
    return std::nullopt;
  }

  document.bundlePath = releasePromotionReferencedPath(*bundlePathField);
  document.promotionManifestPath =
      releasePromotionReferencedPath(*promotionManifestPath);
  document.summaryPath = releasePromotionReferencedPath(*summaryPath);
  document.batchPath = releasePromotionReferencedPath(*batchPath);
  document.status = *status;
  document.releaseEligible = *releaseEligible;
  document.blockerCount = *blockerCount;
  document.packageCount = *packageCount;
  document.artifactCount = *artifactCount;
  document.existingArtifactCount = *existingArtifactCount;
  document.missingArtifactCount = *missingArtifactCount;
  document.totalArtifactBytes = *totalArtifactBytes;

  for (std::string_view blockerObject : *blockers) {
    std::optional<PackageReleasePromotionBlocker> blocker =
        parseReleaseBundleBlocker(blockerObject, bundlePath, diagnostics);
    if (!blocker) {
      return std::nullopt;
    }
    document.blockers.push_back(std::move(*blocker));
  }
  for (std::string_view packageObject : *packages) {
    std::optional<PackageReleaseBundleParsedPackage> package =
        parseReleaseBundlePackage(packageObject, bundlePath, diagnostics);
    if (!package) {
      return std::nullopt;
    }
    document.packages.push_back(std::move(*package));
  }

  validateReleaseBundleDocument(document, bundlePath, diagnostics);
  return document;
}

void validateReleasePublishPlanDocument(
    const PackageReleasePublishPlanParsedDocument &document,
    const std::filesystem::path &planPath, DiagnosticEngine &diagnostics) {
  if (document.bundlePath.empty() || document.planPath.empty()) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish plan paths must be non-empty",
                      pathLocation(planPath));
  }
  if (!document.releaseEligible) {
    diagnostics.error(releasePublishDiagnosticCode("not-release-eligible"),
                      "package release publish plan must be release eligible",
                      pathLocation(planPath));
  }
  if (document.packageCount != document.packages.size()) {
    diagnostics.error(releasePublishDiagnosticCode("inconsistent-counts"),
                      "package release publish plan packageCount must match "
                      "packages",
                      pathLocation(planPath));
  }
  if (document.artifactCount != document.artifacts.size()) {
    diagnostics.error(releasePublishDiagnosticCode("inconsistent-counts"),
                      "package release publish plan artifactCount must match "
                      "artifacts",
                      pathLocation(planPath));
  }

  std::map<std::string, const PackageReleasePublishPlanArtifact *>
      flattenedByDestination;
  for (const PackageReleasePublishPlanArtifact &artifact :
       document.artifacts) {
    flattenedByDestination.emplace(artifact.destinationPath, &artifact);
  }

  std::uintmax_t nestedTotalBytes = 0;
  for (std::size_t packageIndex = 0; packageIndex < document.packages.size();
       ++packageIndex) {
    const PackageReleasePublishPlanPackage &package =
        document.packages[packageIndex];
    if (packageIndex != 0 && document.packages[packageIndex - 1]
                                     .packagePath.generic_string() >=
                                 package.packagePath.generic_string()) {
      diagnostics.error(releasePublishDiagnosticCode("invalid-packages"),
                        "package release publish plan package paths must be "
                        "sorted and unique",
                        pathLocation(planPath));
      break;
    }
    if (!package.sourceHash) {
      diagnostics.error(releasePublishDiagnosticCode("missing-source-hash"),
                        "package release publish plan packages require "
                        "sourceHash",
                        pathLocation(planPath));
    }
    validateReleasePackageArtifactsAgainstRequirements(
        package, planPath, diagnostics,
        releasePublishDiagnosticCode("artifact-requirements-mismatch"),
        "package release publish plan");

    std::uintmax_t packageBytes = 0;
    for (std::size_t artifactIndex = 0;
         artifactIndex < package.artifacts.size(); ++artifactIndex) {
      const PackageReleasePublishPlanArtifact &artifact =
          package.artifacts[artifactIndex];
      if (artifactIndex != 0 &&
          package.artifacts[artifactIndex - 1].destinationPath >=
              artifact.destinationPath) {
        diagnostics.error(
            releasePublishDiagnosticCode("invalid-artifacts"),
            "package release publish plan package destination paths must be "
            "sorted and unique",
            pathLocation(planPath));
        break;
      }
      if (artifact.packagePath != package.packagePath ||
          artifact.module != package.module || artifact.target != package.target) {
        diagnostics.error(releasePublishDiagnosticCode("invalid-artifact"),
                          "package release publish plan artifact package "
                          "identity must match containing package",
                          pathLocation(planPath));
      }
      const auto flattened =
          flattenedByDestination.find(artifact.destinationPath);
      if (flattened == flattenedByDestination.end() ||
          flattened->second->name != artifact.name ||
          flattened->second->packagePath != artifact.packagePath ||
          flattened->second->module != artifact.module ||
          flattened->second->target != artifact.target ||
          flattened->second->sourcePath != artifact.sourcePath ||
          flattened->second->packageArtifactPath !=
              artifact.packageArtifactPath ||
          flattened->second->sizeBytes != artifact.sizeBytes ||
          flattened->second->sha256 != artifact.sha256) {
        diagnostics.error(releasePublishDiagnosticCode("invalid-artifact"),
                          "package release publish plan nested artifact must "
                          "match flattened artifact",
                          pathLocation(planPath));
      }
      packageBytes += artifact.sizeBytes;
    }
    if (package.totalArtifactBytes != packageBytes) {
      diagnostics.error(releasePublishDiagnosticCode("inconsistent-counts"),
                        "package release publish plan package "
                        "totalArtifactBytes must match artifacts",
                        pathLocation(planPath));
    }
    nestedTotalBytes += packageBytes;
  }

  std::uintmax_t totalBytes = 0;
  for (std::size_t index = 0; index < document.artifacts.size(); ++index) {
    const PackageReleasePublishPlanArtifact &artifact =
        document.artifacts[index];
    if (index != 0 && document.artifacts[index - 1].destinationPath >=
                          artifact.destinationPath) {
      diagnostics.error(releasePublishDiagnosticCode("invalid-artifacts"),
                        "package release publish plan destination paths must "
                        "be sorted and unique",
                        pathLocation(planPath));
      break;
    }
    totalBytes += artifact.sizeBytes;
  }

  if (document.totalArtifactBytes != totalBytes) {
    diagnostics.error(releasePublishDiagnosticCode("inconsistent-counts"),
                      "package release publish plan totalArtifactBytes must "
                      "match artifacts",
                      pathLocation(planPath));
  }
  if (document.totalArtifactBytes != nestedTotalBytes) {
    diagnostics.error(releasePublishDiagnosticCode("inconsistent-counts"),
                      "package release publish plan totalArtifactBytes must "
                      "match package artifacts",
                      pathLocation(planPath));
  }
}

std::optional<PackageReleasePublishPlanParsedDocument>
parseReleasePublishPlanDocument(std::string_view text,
                                const std::filesystem::path &planPath,
                                DiagnosticEngine &diagnostics) {
  PackageReleasePublishPlanParsedDocument document;
  const std::optional<std::uintmax_t> version =
      objectUnsignedMember(text, "schemaVersion");
  if (!version) {
    diagnostics.error(releasePublishDiagnosticCode("missing-schema-version"),
                      "package release publish plan requires schemaVersion: 1",
                      pathLocation(planPath));
    return std::nullopt;
  }
  if (*version != 1) {
    diagnostics.error(
        releasePublishDiagnosticCode("unsupported-schema-version"),
        "package release publish plan schemaVersion must be 1",
        pathLocation(planPath));
    return std::nullopt;
  }

  const std::optional<std::string> bundlePath =
      parseRequiredReleasePublishStringMember(text, "bundlePath", planPath,
                                              diagnostics);
  const std::optional<std::string> planPathField =
      parseRequiredReleasePublishStringMember(text, "planPath", planPath,
                                              diagnostics);
  const std::optional<bool> releaseEligible =
      parseRequiredReleasePublishBoolMember(text, "releaseEligible", planPath,
                                            diagnostics);
  const std::optional<std::size_t> packageCount =
      parseRequiredReleasePublishCountMember(text, "packageCount", planPath,
                                             diagnostics);
  const std::optional<std::size_t> artifactCount =
      parseRequiredReleasePublishCountMember(text, "artifactCount", planPath,
                                             diagnostics);
  const std::optional<std::uintmax_t> totalArtifactBytes =
      parseRequiredReleasePublishByteCountMember(text, "totalArtifactBytes",
                                                 planPath, diagnostics);
  const std::optional<std::vector<std::string_view>> packages =
      parseRequiredReleasePublishObjectArrayMember(text, "packages", planPath,
                                                   diagnostics);
  const std::optional<std::vector<std::string_view>> artifacts =
      parseRequiredReleasePublishObjectArrayMember(text, "artifacts", planPath,
                                                   diagnostics);
  if (!bundlePath || !planPathField || !releaseEligible || !packageCount ||
      !artifactCount || !totalArtifactBytes || !packages || !artifacts) {
    return std::nullopt;
  }

  document.bundlePath = releasePromotionReferencedPath(*bundlePath);
  document.planPath = releasePromotionReferencedPath(*planPathField);
  document.releaseEligible = *releaseEligible;
  document.packageCount = *packageCount;
  document.artifactCount = *artifactCount;
  document.totalArtifactBytes = *totalArtifactBytes;

  for (std::string_view packageObject : *packages) {
    std::optional<PackageReleasePublishPlanPackage> package =
        parseReleasePublishPlanPackage(packageObject, planPath, diagnostics);
    if (!package) {
      return std::nullopt;
    }
    document.packages.push_back(std::move(*package));
  }
  for (std::string_view artifactObject : *artifacts) {
    std::optional<PackageReleasePublishPlanArtifact> artifact =
        parseReleasePublishPlanArtifact(artifactObject, planPath, diagnostics);
    if (!artifact) {
      return std::nullopt;
    }
    document.artifacts.push_back(std::move(*artifact));
  }

  validateReleasePublishPlanDocument(document, planPath, diagnostics);
  return document;
}

void validateReleasePublishStageDocument(
    const PackageReleasePublishStageParsedDocument &document,
    const std::filesystem::path &reportPath, DiagnosticEngine &diagnostics) {
  if (document.planPath.empty() || document.stagePath.empty()) {
    diagnostics.error(releasePublishDiagnosticCode("invalid-field"),
                      "package release publish stage report paths must be "
                      "non-empty",
                      pathLocation(reportPath));
  }
  if (!document.success) {
    diagnostics.error(releasePublishDiagnosticCode("stage-not-successful"),
                      "package release publish stage report must be "
                      "successful before publishing",
                      pathLocation(reportPath));
  }
  if (document.artifactCount != document.artifacts.size()) {
    diagnostics.error(releasePublishDiagnosticCode("inconsistent-counts"),
                      "package release publish stage report artifactCount "
                      "must match artifacts",
                      pathLocation(reportPath));
  }

  std::uintmax_t totalBytes = 0;
  std::uintmax_t stagedBytes = 0;
  std::size_t stagedCount = 0;
  for (std::size_t index = 0; index < document.artifacts.size(); ++index) {
    const PackageReleasePublishStageArtifact &staged =
        document.artifacts[index];
    if (index != 0 && document.artifacts[index - 1].artifact.destinationPath >=
                          staged.artifact.destinationPath) {
      diagnostics.error(releasePublishDiagnosticCode("invalid-artifacts"),
                        "package release publish stage report destination "
                        "paths must be sorted and unique",
                        pathLocation(reportPath));
      break;
    }

    const std::filesystem::path expectedStagedPath =
        (document.stagePath /
         std::filesystem::path(staged.artifact.destinationPath))
            .lexically_normal();
    if (staged.stagedPath != expectedStagedPath) {
      diagnostics.error(releasePublishDiagnosticCode("invalid-artifact"),
                        "package release publish stage report stagedPath "
                        "must match stagePath/destinationPath",
                        pathLocation(reportPath));
      break;
    }

    totalBytes += staged.artifact.sizeBytes;
    if (staged.staged) {
      ++stagedCount;
      stagedBytes += staged.artifact.sizeBytes;
    }
  }

  if (document.totalArtifactBytes != totalBytes) {
    diagnostics.error(releasePublishDiagnosticCode("inconsistent-counts"),
                      "package release publish stage report "
                      "totalArtifactBytes must match artifacts",
                      pathLocation(reportPath));
  }
  if (document.stagedArtifactCount != stagedCount ||
      document.stagedArtifactBytes != stagedBytes) {
    diagnostics.error(releasePublishDiagnosticCode("inconsistent-counts"),
                      "package release publish stage report staged counts "
                      "must match artifacts",
                      pathLocation(reportPath));
  }
  if (document.stagedArtifactCount != document.artifactCount) {
    diagnostics.error(releasePublishDiagnosticCode("stage-not-complete"),
                      "package release publish stage report must include every "
                      "artifact as staged",
                      pathLocation(reportPath));
  }
}

std::optional<PackageReleasePublishStageParsedDocument>
parseReleasePublishStageDocument(std::string_view text,
                                 const std::filesystem::path &reportPath,
                                 DiagnosticEngine &diagnostics) {
  PackageReleasePublishStageParsedDocument document;
  const std::optional<std::uintmax_t> version =
      objectUnsignedMember(text, "schemaVersion");
  if (!version) {
    diagnostics.error(releasePublishDiagnosticCode("missing-schema-version"),
                      "package release publish stage report requires "
                      "schemaVersion: 1",
                      pathLocation(reportPath));
    return std::nullopt;
  }
  if (*version != 1) {
    diagnostics.error(
        releasePublishDiagnosticCode("unsupported-schema-version"),
        "package release publish stage report schemaVersion "
        "must be 1",
        pathLocation(reportPath));
    return std::nullopt;
  }

  const std::optional<std::string> planPath =
      parseRequiredReleasePublishStringMember(text, "planPath", reportPath,
                                              diagnostics);
  const std::optional<std::string> stagePath =
      parseRequiredReleasePublishStringMember(text, "stagePath", reportPath,
                                              diagnostics);
  const std::optional<bool> success = parseRequiredReleasePublishBoolMember(
      text, "success", reportPath, diagnostics);
  const std::optional<std::size_t> packageCount =
      parseRequiredReleasePublishCountMember(text, "packageCount", reportPath,
                                             diagnostics);
  const std::optional<std::size_t> artifactCount =
      parseRequiredReleasePublishCountMember(text, "artifactCount", reportPath,
                                             diagnostics);
  const std::optional<std::uintmax_t> totalArtifactBytes =
      parseRequiredReleasePublishByteCountMember(text, "totalArtifactBytes",
                                                 reportPath, diagnostics);
  const std::optional<std::size_t> stagedArtifactCount =
      parseRequiredReleasePublishCountMember(text, "stagedArtifactCount",
                                             reportPath, diagnostics);
  const std::optional<std::uintmax_t> stagedArtifactBytes =
      parseRequiredReleasePublishByteCountMember(text, "stagedArtifactBytes",
                                                 reportPath, diagnostics);
  const std::optional<std::vector<std::string_view>> artifacts =
      parseRequiredReleasePublishObjectArrayMember(text, "artifacts",
                                                   reportPath, diagnostics);
  if (!planPath || !stagePath || !success || !packageCount || !artifactCount ||
      !totalArtifactBytes || !stagedArtifactCount || !stagedArtifactBytes ||
      !artifacts) {
    return std::nullopt;
  }

  document.planPath = releasePromotionReferencedPath(*planPath);
  document.stagePath = releasePromotionReferencedPath(*stagePath);
  document.success = *success;
  document.packageCount = *packageCount;
  document.artifactCount = *artifactCount;
  document.totalArtifactBytes = *totalArtifactBytes;
  document.stagedArtifactCount = *stagedArtifactCount;
  document.stagedArtifactBytes = *stagedArtifactBytes;

  for (std::string_view artifactObject : *artifacts) {
    std::optional<PackageReleasePublishStageArtifact> artifact =
        parseReleasePublishStageArtifact(artifactObject, reportPath,
                                         diagnostics);
    if (!artifact) {
      return std::nullopt;
    }
    document.artifacts.push_back(std::move(*artifact));
  }

  validateReleasePublishStageDocument(document, reportPath, diagnostics);
  return document;
}

void validateReleasePublishUploadManifestDocument(
    const PackageReleasePublishUploadManifestParsedDocument &document,
    const std::filesystem::path &manifestPath, DiagnosticEngine &diagnostics) {
  if (document.requestCount != document.requests.size()) {
    diagnostics.error(releasePublishDiagnosticCode("inconsistent-counts"),
                      "package release publish upload manifest requestCount "
                      "must match requests",
                      pathLocation(manifestPath));
  }

  std::uintmax_t requestBytes = 0;
  for (std::size_t index = 0; index < document.requests.size(); ++index) {
    const PackageReleasePublishUploadRequest &request =
        document.requests[index];
    if (index != 0 && document.requests[index - 1].destinationPath >=
                          request.destinationPath) {
      diagnostics.error(releasePublishDiagnosticCode("invalid-upload-request"),
                        "package release publish upload manifest destination "
                        "paths must be sorted and unique",
                        pathLocation(manifestPath));
      break;
    }
    requestBytes += request.sizeBytes;
  }

  if (document.requestBytes != requestBytes) {
    diagnostics.error(releasePublishDiagnosticCode("inconsistent-counts"),
                      "package release publish upload manifest requestBytes "
                      "must match requests",
                      pathLocation(manifestPath));
  }
}

std::optional<PackageReleasePublishUploadManifestParsedDocument>
parseReleasePublishUploadManifestDocument(
    std::string_view text, const std::filesystem::path &manifestPath,
    DiagnosticEngine &diagnostics) {
  PackageReleasePublishUploadManifestParsedDocument document;
  const std::optional<std::uintmax_t> version =
      objectUnsignedMember(text, "schemaVersion");
  if (!version) {
    diagnostics.error(
        releasePublishDiagnosticCode("missing-schema-version"),
        "package release publish upload manifest requires schemaVersion: 1",
        pathLocation(manifestPath));
    return std::nullopt;
  }
  if (*version != 1) {
    diagnostics.error(
        releasePublishDiagnosticCode("unsupported-schema-version"),
        "package release publish upload manifest schemaVersion must be 1",
        pathLocation(manifestPath));
    return std::nullopt;
  }

  const std::optional<std::size_t> requestCount =
      parseRequiredReleasePublishCountMember(text, "requestCount", manifestPath,
                                             diagnostics);
  const std::optional<std::uintmax_t> requestBytes =
      parseRequiredReleasePublishByteCountMember(text, "requestBytes",
                                                 manifestPath, diagnostics);
  const std::optional<std::vector<std::string_view>> requests =
      parseRequiredReleasePublishObjectArrayMember(text, "requests",
                                                   manifestPath, diagnostics);
  if (!requestCount || !requestBytes || !requests) {
    return std::nullopt;
  }

  document.requestCount = *requestCount;
  document.requestBytes = *requestBytes;
  for (std::string_view requestObject : *requests) {
    std::optional<PackageReleasePublishUploadRequest> request =
        parseReleasePublishUploadRequest(requestObject, manifestPath,
                                         diagnostics);
    if (!request) {
      return std::nullopt;
    }
    document.requests.push_back(std::move(*request));
  }

  validateReleasePublishUploadManifestDocument(document, manifestPath,
                                               diagnostics);
  return document;
}

bool parseMaintenanceSetVerificationBatchVersion(
    std::string_view text, const std::filesystem::path &batchPath,
    DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> versionText =
      findObjectMemberValue(text, "schemaVersion");
  if (!versionText) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("missing-schema-version"),
        "package maintenance set verification batch requires schemaVersion: 1",
        pathLocation(batchPath));
    return false;
  }

  const std::optional<std::uintmax_t> version =
      parseUnsignedInteger(*versionText);
  if (!version || *version != 1) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode(
            "unsupported-schema-version"),
        "package maintenance set verification batch schemaVersion must be 1",
        pathLocation(batchPath));
    return false;
  }
  return true;
}

std::optional<std::vector<std::string>>
parseMaintenanceSetPackageStrings(std::string_view arrayText,
                                  const std::filesystem::path &setPath,
                                  DiagnosticEngine &diagnostics) {
  std::vector<std::string> packages;
  std::size_t position = 0;
  skipWhitespace(arrayText, position);
  if (position >= arrayText.size() || arrayText[position] != '[') {
    diagnostics.error(maintenanceSetDiagnosticCode("invalid-packages"),
                      "package maintenance set packages must be a JSON array",
                      pathLocation(setPath));
    return std::nullopt;
  }

  ++position;
  skipWhitespace(arrayText, position);
  if (position < arrayText.size() && arrayText[position] == ']') {
    diagnostics.error(maintenanceSetDiagnosticCode("empty-packages"),
                      "package maintenance set packages must not be empty",
                      pathLocation(setPath));
    return std::nullopt;
  }

  while (position < arrayText.size()) {
    if (position >= arrayText.size() || arrayText[position] != '"') {
      diagnostics.error(
          maintenanceSetDiagnosticCode("invalid-package"),
          "package maintenance set package entries must be strings",
          pathLocation(setPath));
      return std::nullopt;
    }

    std::string packagePath;
    if (!parseJsonString(arrayText, position, packagePath)) {
      diagnostics.error(maintenanceSetDiagnosticCode("invalid-package"),
                        "package maintenance set package entry is not a valid "
                        "JSON string",
                        pathLocation(setPath));
      return std::nullopt;
    }
    if (packagePath.empty()) {
      diagnostics.error(maintenanceSetDiagnosticCode("empty-package"),
                        "package maintenance set package entries must not be "
                        "empty",
                        pathLocation(setPath));
      return std::nullopt;
    }
    packages.push_back(std::move(packagePath));

    skipWhitespace(arrayText, position);
    if (position < arrayText.size() && arrayText[position] == ',') {
      ++position;
      skipWhitespace(arrayText, position);
      continue;
    }
    if (position < arrayText.size() && arrayText[position] == ']') {
      ++position;
      skipWhitespace(arrayText, position);
      if (position == arrayText.size()) {
        return packages;
      }
    }
    diagnostics.error(maintenanceSetDiagnosticCode("invalid-packages"),
                      "package maintenance set packages is not a valid JSON "
                      "array",
                      pathLocation(setPath));
    return std::nullopt;
  }

  diagnostics.error(maintenanceSetDiagnosticCode("invalid-packages"),
                    "package maintenance set packages is not a valid JSON "
                    "array",
                    pathLocation(setPath));
  return std::nullopt;
}

std::filesystem::path resolveMaintenanceSetVerificationBatchPath(
    const std::filesystem::path &batchPath, const std::string &path) {
  const std::filesystem::path parsedPath(path);
  std::filesystem::path resolved;
  if (parsedPath.is_absolute()) {
    resolved = parsedPath.lexically_normal();
  } else {
    resolved = (packageParentPath(batchPath) / parsedPath).lexically_normal();
  }
  if (resolved.filename().empty() && resolved != resolved.root_path()) {
    return resolved.parent_path();
  }
  return resolved;
}

std::optional<PackageMaintenanceSetVerificationBatchEntry>
parseMaintenanceSetVerificationBatchEntry(
    std::string_view objectText, const std::filesystem::path &batchPath,
    DiagnosticEngine &diagnostics) {
  std::optional<PackageMaintenanceSetVerificationBatchEntry> entry;
  const std::optional<StringMember> rootPath =
      findStringMemberRecord(objectText, "rootPath");
  if (!rootPath) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("missing-root-path"),
        "package maintenance set verification entries require rootPath",
        pathLocation(batchPath));
    return std::nullopt;
  }
  if (rootPath->value.empty()) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("empty-root-path"),
        "package maintenance set verification rootPath must not be empty",
        pathLocation(batchPath));
    return std::nullopt;
  }

  const std::optional<StringMember> setPath =
      findStringMemberRecord(objectText, "setPath");
  if (!setPath) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("missing-set-path"),
        "package maintenance set verification entries require setPath",
        pathLocation(batchPath));
    return std::nullopt;
  }
  if (setPath->value.empty()) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("empty-set-path"),
        "package maintenance set verification setPath must not be empty",
        pathLocation(batchPath));
    return std::nullopt;
  }

  entry.emplace();
  entry->rootPath =
      resolveMaintenanceSetVerificationBatchPath(batchPath, rootPath->value);
  entry->setPath =
      resolveMaintenanceSetVerificationBatchPath(batchPath, setPath->value);
  return entry;
}

std::optional<std::vector<PackageMaintenanceSetVerificationBatchEntry>>
parseMaintenanceSetVerificationBatchEntries(
    std::string_view arrayText, const std::filesystem::path &batchPath,
    DiagnosticEngine &diagnostics) {
  std::vector<PackageMaintenanceSetVerificationBatchEntry> entries;
  std::vector<std::string> seen;
  std::size_t position = 0;
  skipWhitespace(arrayText, position);
  if (position >= arrayText.size() || arrayText[position] != '[') {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("invalid-verifications"),
        "package maintenance set verification batch verifications must be a "
        "JSON array",
        pathLocation(batchPath));
    return std::nullopt;
  }

  ++position;
  skipWhitespace(arrayText, position);
  if (position < arrayText.size() && arrayText[position] == ']') {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("empty-verifications"),
        "package maintenance set verification batch verifications must not be "
        "empty",
        pathLocation(batchPath));
    return std::nullopt;
  }

  while (position < arrayText.size()) {
    const std::size_t objectBegin = position;
    if (!skipJsonObject(arrayText, position)) {
      diagnostics.error(
          maintenanceSetVerificationBatchDiagnosticCode("invalid-verification"),
          "package maintenance set verification entries must be JSON objects",
          pathLocation(batchPath));
      return std::nullopt;
    }
    const std::string_view objectText =
        arrayText.substr(objectBegin, position - objectBegin);
    if (std::optional<PackageMaintenanceSetVerificationBatchEntry> entry =
            parseMaintenanceSetVerificationBatchEntry(objectText, batchPath,
                                                      diagnostics)) {
      const std::string key = entry->rootPath.generic_string() + "\n" +
                              entry->setPath.generic_string();
      if (std::find(seen.begin(), seen.end(), key) != seen.end()) {
        diagnostics.error(
            maintenanceSetVerificationBatchDiagnosticCode(
                "duplicate-verification"),
            "package maintenance set verification batch contains duplicate "
            "rootPath/setPath pair",
            pathLocation(batchPath));
      } else {
        seen.push_back(key);
        entries.push_back(std::move(*entry));
      }
    }

    skipWhitespace(arrayText, position);
    if (position < arrayText.size() && arrayText[position] == ',') {
      ++position;
      skipWhitespace(arrayText, position);
      continue;
    }
    if (position < arrayText.size() && arrayText[position] == ']') {
      ++position;
      skipWhitespace(arrayText, position);
      if (position == arrayText.size()) {
        return entries;
      }
    }
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("invalid-verifications"),
        "package maintenance set verification batch verifications is not a "
        "valid JSON array",
        pathLocation(batchPath));
    return std::nullopt;
  }

  diagnostics.error(
      maintenanceSetVerificationBatchDiagnosticCode("invalid-verifications"),
      "package maintenance set verification batch verifications is not a valid "
      "JSON array",
      pathLocation(batchPath));
  return std::nullopt;
}

std::filesystem::path
resolveMaintenanceSetPackagePath(const std::filesystem::path &setPath,
                                 const std::string &packagePath) {
  const std::filesystem::path parsedPath(packagePath);
  if (parsedPath.is_absolute()) {
    return parsedPath.lexically_normal();
  }
  const std::filesystem::path basePath = packageParentPath(setPath);
  return (basePath / parsedPath).lexically_normal();
}

std::vector<std::filesystem::path>
sortedUniqueMaintenanceSetPackagePaths(const std::filesystem::path &setPath,
                                       const std::vector<std::string> &packages,
                                       DiagnosticEngine &diagnostics) {
  std::vector<std::filesystem::path> packagePaths;
  std::vector<std::string> seen;
  for (const std::string &package : packages) {
    const std::filesystem::path resolved =
        resolveMaintenanceSetPackagePath(setPath, package);
    const std::string key = resolved.generic_string();
    if (std::find(seen.begin(), seen.end(), key) != seen.end()) {
      diagnostics.error(maintenanceSetDiagnosticCode("duplicate-package"),
                        "package maintenance set contains duplicate package "
                        "path: " +
                            key,
                        pathLocation(setPath));
      continue;
    }
    seen.push_back(key);
    packagePaths.push_back(resolved);
  }

  std::sort(
      packagePaths.begin(), packagePaths.end(),
      [](const std::filesystem::path &lhs, const std::filesystem::path &rhs) {
        return lhs.generic_string() < rhs.generic_string();
      });
  return packagePaths;
}

std::filesystem::path
packageSetDocumentPath(const std::filesystem::path &packagePath,
                       const std::filesystem::path &basePath) {
  std::error_code error;
  const std::filesystem::path relative =
      std::filesystem::relative(packagePath, basePath, error);
  if (!error && !relative.empty()) {
    return relative.lexically_normal();
  }
  return packagePath.lexically_normal();
}

std::filesystem::path
absoluteNormalizedPath(const std::filesystem::path &path) {
  if (path.is_absolute()) {
    return path.lexically_normal();
  }

  std::error_code error;
  const std::filesystem::path absolutePath =
      std::filesystem::absolute(path, error);
  if (error) {
    return path.lexically_normal();
  }
  return absolutePath.lexically_normal();
}

std::filesystem::path packageReleaseOutputEvidencePath(
    const std::filesystem::path &path, const std::filesystem::path &basePath) {
  return absoluteNormalizedPath(path)
      .lexically_relative(absoluteNormalizedPath(basePath))
      .lexically_normal();
}

std::string packageReleaseOutputEvidencePathString(
    const std::filesystem::path &path, const std::filesystem::path &basePath) {
  return packageReleaseOutputEvidencePath(path, basePath).generic_string();
}

std::filesystem::path
packageMaintenanceBatchExportPath(const std::filesystem::path &path) {
  if (path.is_absolute()) {
    return path.lexically_normal();
  }
  return std::filesystem::absolute(path).lexically_normal();
}

std::vector<PackageMaintenanceSetVerificationBatchEntry>
normalizedMaintenanceBatchExportEntries(
    const std::vector<PackageMaintenanceSetVerificationBatchEntry> &entries,
    DiagnosticEngine &diagnostics, const std::filesystem::path &batchPath) {
  std::vector<PackageMaintenanceSetVerificationBatchEntry> normalizedEntries;
  std::vector<std::string> seen;
  for (const PackageMaintenanceSetVerificationBatchEntry &entry : entries) {
    PackageMaintenanceSetVerificationBatchEntry normalized;
    normalized.rootPath = packageMaintenanceBatchExportPath(entry.rootPath);
    normalized.setPath = packageMaintenanceBatchExportPath(entry.setPath);

    const std::string key = normalized.rootPath.generic_string() + "\n" +
                            normalized.setPath.generic_string();
    if (std::find(seen.begin(), seen.end(), key) != seen.end()) {
      diagnostics.error(
          maintenanceSetVerificationBatchDiagnosticCode(
              "duplicate-verification"),
          "package maintenance set verification batch contains duplicate "
          "rootPath/setPath pair",
          pathLocation(batchPath));
      continue;
    }
    seen.push_back(key);
    normalizedEntries.push_back(std::move(normalized));
  }
  return normalizedEntries;
}

std::vector<std::filesystem::path>
packagePathSetDifference(const std::vector<std::filesystem::path> &lhs,
                         const std::vector<std::filesystem::path> &rhs) {
  std::vector<std::filesystem::path> difference;
  std::size_t lhsIndex = 0;
  std::size_t rhsIndex = 0;
  while (lhsIndex < lhs.size()) {
    if (rhsIndex >= rhs.size()) {
      difference.push_back(lhs[lhsIndex++]);
      continue;
    }
    const std::string lhsKey = lhs[lhsIndex].generic_string();
    const std::string rhsKey = rhs[rhsIndex].generic_string();
    if (lhsKey < rhsKey) {
      difference.push_back(lhs[lhsIndex++]);
      continue;
    }
    if (rhsKey < lhsKey) {
      ++rhsIndex;
      continue;
    }
    ++lhsIndex;
    ++rhsIndex;
  }
  return difference;
}

std::optional<std::string>
readMaintenancePolicyFile(const std::filesystem::path &policyPath,
                          DiagnosticEngine &diagnostics) {
  std::error_code statusError;
  if (std::filesystem::exists(policyPath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(policyPath, statusError)) {
    diagnostics.error(maintenancePolicyDiagnosticCode("invalid-file"),
                      "package maintenance policy is not a regular file: " +
                          policyPath.string(),
                      pathLocation(policyPath));
    return std::nullopt;
  }

  std::ifstream input(policyPath, std::ios::binary);
  if (!input) {
    diagnostics.error(maintenancePolicyDiagnosticCode("read-failed"),
                      "failed to read package maintenance policy: " +
                          policyPath.string(),
                      pathLocation(policyPath));
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  std::string text = buffer.str();
  if (!isJsonObjectDocument(text)) {
    diagnostics.error(
        maintenancePolicyDiagnosticCode("invalid-json"),
        "package maintenance policy is not a valid JSON object: " +
            policyPath.string(),
        pathLocation(policyPath));
    return std::nullopt;
  }
  if (const std::optional<DuplicateJsonKey> duplicate =
          findDuplicateJsonKey(text)) {
    diagnostics.error(
        maintenancePolicyDiagnosticCode("duplicate-key"),
        "package maintenance policy contains duplicate JSON object key: " +
            duplicate->path,
        pathLocation(policyPath));
    return std::nullopt;
  }
  return text;
}

bool parseMaintenancePolicyVersion(std::string_view text,
                                   const std::filesystem::path &policyPath,
                                   DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> versionText =
      findObjectMemberValue(text, "schemaVersion");
  if (!versionText) {
    diagnostics.error(maintenancePolicyDiagnosticCode("missing-schema-version"),
                      "package maintenance policy requires schemaVersion: 1",
                      pathLocation(policyPath));
    return false;
  }

  const std::optional<std::uintmax_t> version =
      parseUnsignedInteger(*versionText);
  if (!version || *version != 1) {
    diagnostics.error(
        maintenancePolicyDiagnosticCode("unsupported-schema-version"),
        "package maintenance policy schemaVersion must be 1",
        pathLocation(policyPath));
    return false;
  }
  return true;
}

std::optional<std::uintmax_t> parseNullableMaintenancePolicyUnsigned(
    std::string_view object, std::string_view key,
    const std::filesystem::path &policyPath, DiagnosticEngine &diagnostics) {
  const std::optional<std::string_view> valueText =
      findObjectMemberValue(object, key);
  if (!valueText || canonicalJson(*valueText) == "null") {
    return std::nullopt;
  }
  const std::optional<std::uintmax_t> value = parseUnsignedInteger(*valueText);
  if (!value) {
    diagnostics.error(
        maintenancePolicyDiagnosticCode(key == "keepLast"
                                            ? "invalid-keep-last"
                                            : "invalid-older-than-seconds"),
        "package maintenance policy staleSidecars." + std::string(key) +
            " must be a non-negative integer or null",
        pathLocation(policyPath));
    return std::nullopt;
  }
  return value;
}

std::optional<std::size_t>
policySizeValue(std::uintmax_t value, std::string_view key,
                const std::filesystem::path &policyPath,
                DiagnosticEngine &diagnostics) {
  if (value > std::numeric_limits<std::size_t>::max()) {
    diagnostics.error(maintenancePolicyDiagnosticCode("value-out-of-range"),
                      "package maintenance policy staleSidecars." +
                          std::string(key) + " is too large",
                      pathLocation(policyPath));
    return std::nullopt;
  }
  return static_cast<std::size_t>(value);
}

std::optional<std::uint64_t>
policyUInt64Value(std::uintmax_t value, std::string_view key,
                  const std::filesystem::path &policyPath,
                  DiagnosticEngine &diagnostics) {
  if (value > std::numeric_limits<std::uint64_t>::max()) {
    diagnostics.error(maintenancePolicyDiagnosticCode("value-out-of-range"),
                      "package maintenance policy staleSidecars." +
                          std::string(key) + " is too large",
                      pathLocation(policyPath));
    return std::nullopt;
  }
  return static_cast<std::uint64_t>(value);
}

void writeCleanupRecord(std::ostream &out,
                        const PackageStaleSidecarCleanupRecord &record,
                        std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"path\": \""
      << escapeJson(record.sidecar.path.lexically_normal().generic_string())
      << "\",\n"
      << indent << "  \"kind\": \"" << escapeJson(record.sidecar.kind)
      << "\",\n"
      << indent << "  \"token\": \"" << escapeJson(record.sidecar.token)
      << "\",\n"
      << indent << "  \"attempt\": " << record.sidecar.attempt << ",\n"
      << indent
      << "  \"directory\": " << (record.sidecar.isDirectory ? "true" : "false")
      << ",\n"
      << indent << "  \"reason\": \"" << escapeJson(record.reason) << "\",\n";
  if (!record.retainedBy.empty()) {
    out << indent << "  \"retainedBy\": \"" << escapeJson(record.retainedBy)
        << "\",\n";
  }
  out << indent << "  \"action\": \"" << escapeJson(record.action) << "\",\n"
      << indent << "  \"success\": " << (record.success ? "true" : "false")
      << "\n"
      << indent << "}";
}

void writeStaleSidecarCleanupResult(
    std::ostream &out, const PackageStaleSidecarCleanupResult &result,
    std::string_view indent) {
  const std::string childIndent = std::string(indent) + "  ";
  out << indent << "{\n"
      << childIndent << "\"schemaVersion\": 1,\n"
      << childIndent << "\"packagePath\": \""
      << escapeJson(result.packagePath.lexically_normal().generic_string())
      << "\",\n"
      << childIndent << "\"dryRun\": " << (result.dryRun ? "true" : "false")
      << ",\n"
      << childIndent
      << "\"requestedExists\": " << (result.requestedExists ? "true" : "false")
      << ",\n"
      << childIndent << "\"keepLast\": ";
  if (result.keepLast) {
    out << *result.keepLast;
  } else {
    out << "null";
  }
  out << ",\n" << childIndent << "\"olderThanSeconds\": ";
  if (result.olderThanSeconds) {
    out << *result.olderThanSeconds;
  } else {
    out << "null";
  }
  out << ",\n"
      << childIndent << "\"retainedCount\": " << result.retained.size() << ",\n"
      << childIndent << "\"success\": " << (result.success ? "true" : "false")
      << ",\n"
      << childIndent << "\"candidateCount\": " << result.candidates.size()
      << ",\n"
      << childIndent << "\"discardedCount\": "
      << countCleanupRecords(result.candidates, "discarded") << ",\n"
      << childIndent
      << "\"failedCount\": " << countCleanupRecords(result.candidates, "failed")
      << ",\n"
      << childIndent << "\"publication\": ";
  writePublicationInfo(out, result.publication, childIndent);
  out << ",\n" << childIndent << "\"candidates\": [";
  for (std::size_t index = 0; index < result.candidates.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeCleanupRecord(out, result.candidates[index], childIndent + "  ");
  }
  if (!result.candidates.empty()) {
    out << "\n" << childIndent;
  }
  out << "],\n" << childIndent << "\"retained\": [";
  for (std::size_t index = 0; index < result.retained.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeCleanupRecord(out, result.retained[index], childIndent + "  ");
  }
  if (!result.retained.empty()) {
    out << "\n" << childIndent;
  }
  out << "],\n" << childIndent << "\"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, childIndent);
  out << ",\n" << childIndent << "\"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics, childIndent);
  out << "\n" << indent << "}";
}

} // namespace

std::filesystem::path packageParentPath(const std::filesystem::path &path) {
  const std::filesystem::path parent = path.parent_path();
  return parent.empty() ? std::filesystem::path(".") : parent;
}

std::string packageSidecarPrefix(const std::filesystem::path &path) {
  std::string filename = path.filename().generic_string();
  if (filename.empty()) {
    filename = "package";
  }
  return "." + filename;
}

std::string packageSidecarToken() {
  const auto now = std::chrono::steady_clock::now().time_since_epoch().count();
  return std::to_string(now);
}

std::optional<std::filesystem::path> availablePackageSidecarPath(
    const std::filesystem::path &finalPath, std::string_view label,
    std::string_view diagnosticCode, DiagnosticEngine &diagnostics) {
  const std::filesystem::path parent = packageParentPath(finalPath);
  const std::string prefix = packageSidecarPrefix(finalPath);
  const std::string token = packageSidecarToken();
  for (std::size_t attempt = 0; attempt < 64; ++attempt) {
    const std::filesystem::path candidate =
        parent / (prefix + "." + std::string(label) + "-" + token + "-" +
                  std::to_string(attempt));
    std::error_code error;
    if (!std::filesystem::exists(candidate, error)) {
      if (error) {
        diagnostics.error(std::string(diagnosticCode),
                          "failed to inspect package sidecar path: " +
                              error.message());
        return std::nullopt;
      }
      return candidate;
    }
  }
  diagnostics.error(std::string(diagnosticCode),
                    "failed to reserve package sidecar path near '" +
                        finalPath.string() + "'");
  return std::nullopt;
}

std::optional<PackageSidecarRecord>
parsePackageSidecarPath(const std::filesystem::path &path) {
  const std::string filename = path.filename().generic_string();
  const std::optional<SidecarMarker> marker = findSidecarMarker(filename);
  if (!marker || marker->position <= 1) {
    return std::nullopt;
  }

  const std::size_t payloadOffset = marker->position + marker->marker.size();
  if (payloadOffset >= filename.size()) {
    return std::nullopt;
  }
  const std::size_t attemptSeparator = filename.rfind('-');
  if (attemptSeparator == std::string::npos ||
      attemptSeparator < payloadOffset ||
      attemptSeparator + 1 >= filename.size()) {
    return std::nullopt;
  }

  const std::string_view token(filename.data() + payloadOffset,
                               attemptSeparator - payloadOffset);
  const std::string_view attemptText(filename.data() + attemptSeparator + 1,
                                     filename.size() - attemptSeparator - 1);
  const std::optional<std::uint64_t> attempt = parseUnsigned(attemptText);
  if (token.empty() || !attempt) {
    return std::nullopt;
  }

  PackageSidecarRecord record;
  record.path = path;
  record.requestedPath =
      (packageParentPath(path) / filename.substr(1, marker->position - 1))
          .lexically_normal();
  record.kind = std::string(marker->kind);
  record.token = std::string(token);
  record.attempt = *attempt;
  std::error_code error;
  record.isDirectory = std::filesystem::is_directory(path, error) && !error;
  return record;
}

PackagePublicationInfo
collectPackagePublicationInfo(const std::filesystem::path &packagePath) {
  PackagePublicationInfo info;
  info.requestedPath = (packageParentPath(packagePath) / packagePath.filename())
                           .lexically_normal();
  info.state = "published";

  if (std::optional<PackageSidecarRecord> current =
          parsePackageSidecarPath(packagePath)) {
    info.requestedPath = current->requestedPath;
    info.state = current->kind == "staging" ? "staged" : current->kind;
    info.currentSidecar = std::move(*current);
  }

  const std::filesystem::path parent = packageParentPath(info.requestedPath);
  const std::string expectedPrefix = packageSidecarPrefix(info.requestedPath);
  std::error_code error;
  for (std::filesystem::directory_iterator entry(parent, error), end;
       !error && entry != end; entry.increment(error)) {
    const std::string siblingName = entry->path().filename().generic_string();
    if (siblingName.rfind(expectedPrefix + ".", 0) != 0) {
      continue;
    }
    std::optional<PackageSidecarRecord> sidecar =
        parsePackageSidecarPath(entry->path());
    if (!sidecar || sidecar->requestedPath != info.requestedPath) {
      continue;
    }
    info.siblingSidecars.push_back(std::move(*sidecar));
  }

  std::sort(
      info.siblingSidecars.begin(), info.siblingSidecars.end(),
      [](const PackageSidecarRecord &lhs, const PackageSidecarRecord &rhs) {
        return lhs.path.generic_string() < rhs.path.generic_string();
      });
  return info;
}

PackageSidecarListResult
listPackageSidecars(const std::filesystem::path &packagePath) {
  PackageSidecarListResult result;
  result.success = true;
  result.packagePath = packagePath;
  result.publication = collectPackagePublicationInfo(packagePath);
  std::error_code error;
  result.requestedExists =
      std::filesystem::exists(result.publication.requestedPath, error) &&
      !error;
  return result;
}

std::string packageSidecarListJson(const PackageSidecarListResult &result) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"packagePath\": \""
      << escapeJson(result.packagePath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"requestedExists\": "
      << (result.requestedExists ? "true" : "false") << ",\n"
      << "  \"publication\": ";
  writePublicationInfo(out, result.publication, "  ");
  out << "\n}\n";
  return out.str();
}

std::string packageSidecarListText(const PackageSidecarListResult &result) {
  std::ostringstream out;
  out << "package sidecars for "
      << result.publication.requestedPath.lexically_normal().generic_string()
      << " (" << result.publication.state
      << ", requestedExists=" << (result.requestedExists ? "true" : "false")
      << ")\n";
  if (result.publication.siblingSidecars.empty()) {
    out << "  no sidecars\n";
    return out.str();
  }
  for (const PackageSidecarRecord &sidecar :
       result.publication.siblingSidecars) {
    out << "  " << sidecar.kind << " "
        << sidecar.path.lexically_normal().generic_string()
        << " token=" << sidecar.token << " attempt=" << sidecar.attempt
        << " directory=" << (sidecar.isDirectory ? "true" : "false") << "\n";
  }
  return out.str();
}

PackageMaintenancePolicyResult
loadPackageMaintenancePolicy(const std::filesystem::path &policyPath) {
  DiagnosticEngine diagnostics;
  PackageMaintenancePolicyResult result;
  const std::optional<std::string> text =
      readMaintenancePolicyFile(policyPath, diagnostics);
  if (!text) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  if (!parseMaintenancePolicyVersion(*text, policyPath, diagnostics)) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  const std::optional<std::string_view> staleSidecars =
      findObjectMemberValue(*text, "staleSidecars");
  if (!staleSidecars) {
    diagnostics.error(
        maintenancePolicyDiagnosticCode("missing-stale-sidecars"),
        "package maintenance policy requires a staleSidecars object",
        pathLocation(policyPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }
  if (!isJsonObjectDocument(*staleSidecars)) {
    diagnostics.error(
        maintenancePolicyDiagnosticCode("invalid-stale-sidecars"),
        "package maintenance policy staleSidecars must be a JSON object",
        pathLocation(policyPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  const std::optional<std::uintmax_t> keepLast =
      parseNullableMaintenancePolicyUnsigned(*staleSidecars, "keepLast",
                                             policyPath, diagnostics);
  const std::optional<std::uintmax_t> olderThanSeconds =
      parseNullableMaintenancePolicyUnsigned(*staleSidecars, "olderThanSeconds",
                                             policyPath, diagnostics);
  if (diagnostics.hasErrors()) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }
  if (!keepLast && !olderThanSeconds) {
    diagnostics.error(
        maintenancePolicyDiagnosticCode("empty-stale-sidecars"),
        "package maintenance policy staleSidecars requires keepLast or "
        "olderThanSeconds",
        pathLocation(policyPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  if (keepLast) {
    result.options.keepLast =
        policySizeValue(*keepLast, "keepLast", policyPath, diagnostics);
  }
  if (olderThanSeconds) {
    result.options.olderThanSeconds = policyUInt64Value(
        *olderThanSeconds, "olderThanSeconds", policyPath, diagnostics);
  }
  result.diagnostics = diagnostics.diagnostics();
  result.success = !diagnostics.hasErrors();
  return result;
}

PackageMaintenanceSetLoadResult
loadPackageMaintenanceSet(const std::filesystem::path &setPath) {
  DiagnosticEngine diagnostics;
  PackageMaintenanceSetLoadResult result;
  result.setPath = setPath;

  const std::optional<std::string> text =
      readMaintenanceSetFile(setPath, diagnostics);
  if (!text) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  if (!parseMaintenanceSetVersion(*text, setPath, diagnostics)) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  const std::optional<std::string_view> packages =
      findObjectMemberValue(*text, "packages");
  if (!packages) {
    diagnostics.error(maintenanceSetDiagnosticCode("missing-packages"),
                      "package maintenance set requires a packages array",
                      pathLocation(setPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  const std::optional<std::vector<std::string>> packageStrings =
      parseMaintenanceSetPackageStrings(*packages, setPath, diagnostics);
  if (!packageStrings || diagnostics.hasErrors()) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  result.packagePaths = sortedUniqueMaintenanceSetPackagePaths(
      setPath, *packageStrings, diagnostics);
  result.diagnostics = diagnostics.diagnostics();
  result.success = !diagnostics.hasErrors();
  return result;
}

PackageMaintenanceSetVerificationBatchLoadResult
loadPackageMaintenanceSetVerificationBatch(
    const std::filesystem::path &batchPath) {
  DiagnosticEngine diagnostics;
  PackageMaintenanceSetVerificationBatchLoadResult result;
  result.batchPath = batchPath;

  const std::optional<std::string> text =
      readMaintenanceSetVerificationBatchFile(batchPath, diagnostics);
  if (!text) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  if (!parseMaintenanceSetVerificationBatchVersion(*text, batchPath,
                                                   diagnostics)) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  const std::optional<std::string_view> verifications =
      findObjectMemberValue(*text, "verifications");
  if (!verifications) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("missing-verifications"),
        "package maintenance set verification batch requires a verifications "
        "array",
        pathLocation(batchPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  const std::optional<std::vector<PackageMaintenanceSetVerificationBatchEntry>>
      entries = parseMaintenanceSetVerificationBatchEntries(
          *verifications, batchPath, diagnostics);
  if (!entries || diagnostics.hasErrors()) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  result.entries = *entries;
  result.diagnostics = diagnostics.diagnostics();
  result.success = !diagnostics.hasErrors();
  return result;
}

PackageStaleSidecarCleanupResult
cleanupStalePackageSidecars(const std::filesystem::path &packagePath,
                            const PackageStaleSidecarCleanupOptions &options) {
  DiagnosticEngine diagnostics;
  PackageStaleSidecarCleanupResult result;
  result.dryRun = options.dryRun;
  result.keepLast = options.keepLast;
  result.olderThanSeconds = options.olderThanSeconds;
  result.packagePath = packagePath;
  result.publication = collectPackagePublicationInfo(packagePath);
  std::error_code error;
  result.requestedExists =
      std::filesystem::exists(result.publication.requestedPath, error) &&
      !error;

  std::vector<StaleSidecarSelection> staleSidecars;
  const std::optional<std::filesystem::file_time_type> ageCutoff =
      staleSidecarAgeCutoff(options.olderThanSeconds);
  for (const PackageSidecarRecord &sidecar :
       result.publication.siblingSidecars) {
    std::string reason;
    if (!isStaleSidecar(sidecar, result.requestedExists, reason)) {
      continue;
    }

    StaleSidecarSelection selection;
    selection.sidecar = sidecar;
    selection.reason = std::move(reason);
    selection.retainedBy =
        retainSidecarByAge(selection.sidecar, ageCutoff, diagnostics);
    staleSidecars.push_back(std::move(selection));
  }

  const std::vector<bool> retained =
      retainedStaleSidecars(staleSidecars, options.keepLast);
  for (std::size_t index = 0; index < staleSidecars.size(); ++index) {
    if (!staleSidecars[index].retainedBy.empty() || retained[index]) {
      if (retained[index]) {
        staleSidecars[index].retainedBy = "keep-last";
      }
      result.retained.push_back(
          makeCleanupRecord(staleSidecars[index], "kept"));
      continue;
    }

    PackageStaleSidecarCleanupRecord record = makeCleanupRecord(
        staleSidecars[index], options.dryRun ? "would-discard" : "discarded");

    if (!options.dryRun) {
      std::filesystem::remove_all(record.sidecar.path, error);
      if (error) {
        record.action = "failed";
        record.success = false;
        diagnostics.error(recoveryDiagnosticCode("discard-stale-failed"),
                          "failed to discard stale package sidecar: " +
                              error.message(),
                          pathLocation(record.sidecar.path));
      }
    }
    result.candidates.push_back(std::move(record));
  }

  result.diagnostics = diagnostics.diagnostics();
  result.success = !diagnostics.hasErrors();
  return result;
}

PackageMaintenanceScanResult scanPackageMaintenanceDirectory(
    const std::filesystem::path &rootPath,
    const PackageStaleSidecarCleanupOptions &options) {
  DiagnosticEngine diagnostics;
  PackageMaintenanceScanResult result;
  result.dryRun = options.dryRun;
  result.keepLast = options.keepLast;
  result.olderThanSeconds = options.olderThanSeconds;
  result.rootPath = rootPath;

  const std::vector<std::filesystem::path> packageRoots =
      discoverMaintenancePackageRoots(rootPath, diagnostics);
  if (diagnostics.hasErrors()) {
    result.diagnostics = packageMaintenanceScanDiagnostics(
        diagnostics.diagnostics(), result.packages);
    return result;
  }

  for (const std::filesystem::path &packageRoot : packageRoots) {
    result.packages.push_back(
        cleanupStalePackageSidecars(packageRoot, options));
  }

  result.diagnostics = packageMaintenanceScanDiagnostics(
      diagnostics.diagnostics(), result.packages);
  result.success =
      packageMaintenanceAggregateSuccess(result.diagnostics, result.packages);
  return result;
}

PackageMaintenanceSetResult
maintainPackageSet(const std::filesystem::path &setPath,
                   const PackageStaleSidecarCleanupOptions &options) {
  PackageMaintenanceSetResult result;
  result.dryRun = options.dryRun;
  result.keepLast = options.keepLast;
  result.olderThanSeconds = options.olderThanSeconds;
  result.setPath = setPath;

  const PackageMaintenanceSetLoadResult packageSet =
      loadPackageMaintenanceSet(setPath);
  if (!packageSet.success) {
    result.diagnostics = packageSet.diagnostics;
    return result;
  }

  for (const std::filesystem::path &packagePath : packageSet.packagePaths) {
    result.packages.push_back(
        cleanupStalePackageSidecars(packagePath, options));
  }

  result.diagnostics = packageMaintenanceScanDiagnostics(packageSet.diagnostics,
                                                         result.packages);
  result.success =
      packageMaintenanceAggregateSuccess(result.diagnostics, result.packages);
  return result;
}

PackageMaintenanceSetExportResult
exportPackageMaintenanceSetFromScan(const std::filesystem::path &rootPath,
                                    const std::filesystem::path &setPath) {
  DiagnosticEngine diagnostics;
  PackageMaintenanceSetExportResult result;
  result.rootPath = rootPath;
  result.setPath = setPath;
  result.packagePaths = discoverMaintenancePackageRoots(rootPath, diagnostics);
  if (diagnostics.hasErrors()) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }
  if (result.packagePaths.empty()) {
    diagnostics.error(maintenanceSetExportDiagnosticCode("empty-scan"),
                      "package maintenance scan found no package outputs to "
                      "export",
                      pathLocation(rootPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  std::error_code statusError;
  if (std::filesystem::exists(setPath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(setPath, statusError)) {
    diagnostics.error(maintenanceSetExportDiagnosticCode("invalid-output"),
                      "package maintenance set export path is not a regular "
                      "file: " +
                          setPath.string(),
                      pathLocation(setPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  std::ofstream output(setPath, std::ios::binary | std::ios::trunc);
  if (!output) {
    diagnostics.error(maintenanceSetExportDiagnosticCode("write-failed"),
                      "failed to write package maintenance set: " +
                          setPath.string(),
                      pathLocation(setPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }
  output << packageMaintenanceSetDocumentJson(result.packagePaths,
                                              packageParentPath(setPath));
  if (!output) {
    diagnostics.error(maintenanceSetExportDiagnosticCode("write-failed"),
                      "failed to write package maintenance set: " +
                          setPath.string(),
                      pathLocation(setPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  result.diagnostics = diagnostics.diagnostics();
  result.success = !diagnostics.hasErrors();
  return result;
}

PackageMaintenanceSetVerificationBatchExportResult
exportPackageMaintenanceSetVerificationBatch(
    const std::filesystem::path &batchPath,
    const std::vector<PackageMaintenanceSetVerificationBatchEntry> &entries) {
  DiagnosticEngine diagnostics;
  PackageMaintenanceSetVerificationBatchExportResult result;
  result.batchPath = batchPath;

  if (entries.empty()) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("empty-verifications"),
        "package maintenance set verification batch verifications must not be "
        "empty",
        pathLocation(batchPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  result.entries =
      normalizedMaintenanceBatchExportEntries(entries, diagnostics, batchPath);
  if (diagnostics.hasErrors()) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  std::error_code statusError;
  if (std::filesystem::exists(batchPath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(batchPath, statusError)) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("invalid-output"),
        "package maintenance set verification batch export path is not a "
        "regular file: " +
            batchPath.string(),
        pathLocation(batchPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  std::ofstream output(batchPath, std::ios::binary | std::ios::trunc);
  if (!output) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("write-failed"),
        "failed to write package maintenance set verification batch: " +
            batchPath.string(),
        pathLocation(batchPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }
  output << packageMaintenanceSetVerificationBatchDocumentJson(
      result.entries, packageParentPath(batchPath));
  if (!output) {
    diagnostics.error(
        maintenanceSetVerificationBatchDiagnosticCode("write-failed"),
        "failed to write package maintenance set verification batch: " +
            batchPath.string(),
        pathLocation(batchPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  result.diagnostics = diagnostics.diagnostics();
  result.success = !diagnostics.hasErrors();
  return result;
}

PackageMaintenanceSetVerificationBatchSummaryExportResult
exportPackageMaintenanceSetVerificationBatchSummary(
    const PackageMaintenanceSetVerificationBatchResult &verificationResult,
    const std::filesystem::path &summaryPath) {
  DiagnosticEngine diagnostics;
  PackageMaintenanceSetVerificationBatchSummaryExportResult result;
  result.summaryPath = summaryPath;

  std::error_code statusError;
  if (std::filesystem::exists(summaryPath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(summaryPath, statusError)) {
    diagnostics.error(
        maintenanceSetVerificationBatchSummaryDiagnosticCode("invalid-output"),
        "package maintenance set verification batch summary output path is not "
        "a regular file: " +
            summaryPath.string(),
        pathLocation(summaryPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  std::ofstream output(summaryPath, std::ios::binary | std::ios::trunc);
  if (!output) {
    diagnostics.error(
        maintenanceSetVerificationBatchSummaryDiagnosticCode("write-failed"),
        "failed to write package maintenance set verification batch summary: " +
            summaryPath.string(),
        pathLocation(summaryPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }
  output << packageMaintenanceSetVerificationBatchSummaryJson(
      verificationResult);
  if (!output) {
    diagnostics.error(
        maintenanceSetVerificationBatchSummaryDiagnosticCode("write-failed"),
        "failed to write package maintenance set verification batch summary: " +
            summaryPath.string(),
        pathLocation(summaryPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  result.diagnostics = diagnostics.diagnostics();
  result.success = !diagnostics.hasErrors();
  return result;
}

std::vector<PackageReleasePromotionBlocker>
packageReleasePromotionBlockers(const PackageReleasePromotionSummary &summary) {
  std::vector<PackageReleasePromotionBlocker> blockers;
  if (!summary.success) {
    blockers.push_back({"verification-summary-failed",
                        "package maintenance verification summary did not "
                        "complete successfully",
                        1});
  }
  if (!summary.matches) {
    blockers.push_back({"verification-summary-mismatch",
                        "package maintenance verification summary contains "
                        "scan/set mismatches",
                        summary.mismatchedCount});
  }
  if (summary.failedCount != 0) {
    blockers.push_back({"verification-failed",
                        "package maintenance verification summary contains "
                        "operational verification failures",
                        summary.failedCount});
  }
  if (summary.missingFromSetCount != 0) {
    blockers.push_back({"missing-from-set",
                        "package maintenance set is missing scan-discovered "
                        "packages",
                        summary.missingFromSetCount});
  }
  if (summary.extraInSetCount != 0) {
    blockers.push_back({"extra-in-set",
                        "package maintenance set contains packages absent "
                        "from scan discovery",
                        summary.extraInSetCount});
  }
  if (summary.diagnosticCounts.error != 0) {
    blockers.push_back({"error-diagnostics",
                        "package maintenance verification summary contains "
                        "error diagnostics",
                        summary.diagnosticCounts.error});
  }
  if (!summary.releaseEligible && blockers.empty()) {
    blockers.push_back({"not-release-eligible",
                        "package maintenance verification summary is not "
                        "release eligible",
                        1});
  }
  std::sort(blockers.begin(), blockers.end(),
            [](const PackageReleasePromotionBlocker &lhs,
               const PackageReleasePromotionBlocker &rhs) {
              return lhs.code < rhs.code;
            });
  return blockers;
}

void sortPackageReleasePromotionBlockers(
    std::vector<PackageReleasePromotionBlocker> &blockers) {
  std::sort(blockers.begin(), blockers.end(),
            [](const PackageReleasePromotionBlocker &lhs,
               const PackageReleasePromotionBlocker &rhs) {
              return lhs.code < rhs.code;
            });
}

void appendDiagnostics(std::vector<Diagnostic> &target,
                       const std::vector<Diagnostic> &source) {
  target.insert(target.end(), source.begin(), source.end());
}

void appendReleaseReportInputDiagnostics(std::vector<Diagnostic> &target,
                                         const std::vector<Diagnostic> &source) {
  for (const Diagnostic &diagnostic : source) {
    Diagnostic wrapped = diagnostic;
    wrapped.code = releaseReportDiagnosticCode("source-diagnostic");
    if (!diagnostic.code.empty()) {
      wrapped.message = diagnostic.code + ": " + diagnostic.message;
    }
    target.push_back(std::move(wrapped));
  }
}

Diagnostic releasePromotionError(std::string_view suffix, std::string message,
                                 const std::filesystem::path &path) {
  Diagnostic diagnostic;
  diagnostic.severity = DiagnosticSeverity::Error;
  diagnostic.code = releasePromotionDiagnosticCode(suffix);
  diagnostic.message = std::move(message);
  diagnostic.location = pathLocation(path);
  return diagnostic;
}

Diagnostic releaseBundleError(std::string_view suffix, std::string message,
                              const std::filesystem::path &path) {
  Diagnostic diagnostic;
  diagnostic.severity = DiagnosticSeverity::Error;
  diagnostic.code = releaseBundleDiagnosticCode(suffix);
  diagnostic.message = std::move(message);
  diagnostic.location = pathLocation(path);
  return diagnostic;
}

Diagnostic releaseReportError(std::string_view suffix, std::string message,
                              const std::filesystem::path &path) {
  Diagnostic diagnostic;
  diagnostic.severity = DiagnosticSeverity::Error;
  diagnostic.code = releaseReportDiagnosticCode(suffix);
  diagnostic.message = std::move(message);
  diagnostic.location = pathLocation(path);
  return diagnostic;
}

Diagnostic releasePublishError(std::string_view suffix, std::string message,
                               const std::filesystem::path &path) {
  Diagnostic diagnostic;
  diagnostic.severity = DiagnosticSeverity::Error;
  diagnostic.code = releasePublishDiagnosticCode(suffix);
  diagnostic.message = std::move(message);
  diagnostic.location = pathLocation(path);
  return diagnostic;
}

void sortUniquePaths(std::vector<std::filesystem::path> &paths) {
  std::sort(
      paths.begin(), paths.end(),
      [](const std::filesystem::path &lhs, const std::filesystem::path &rhs) {
        return lhs.generic_string() < rhs.generic_string();
      });
  paths.erase(std::unique(paths.begin(), paths.end(),
                          [](const std::filesystem::path &lhs,
                             const std::filesystem::path &rhs) {
                            return lhs.generic_string() == rhs.generic_string();
                          }),
              paths.end());
}

struct PackageReleasePromotionInventoryLoadResult {
  std::vector<PackageReleasePromotionPackage> packages;
  std::vector<Diagnostic> diagnostics;
};

std::vector<std::filesystem::path> packagePathsForReleasePromotion(
    const std::vector<std::filesystem::path> &setPaths,
    std::vector<Diagnostic> &diagnostics) {
  std::vector<std::filesystem::path> packagePaths;
  if (setPaths.empty()) {
    diagnostics.push_back(releasePromotionError(
        "missing-package-sets",
        "package release promotion summary contains no package set paths",
        std::filesystem::path{}));
    return packagePaths;
  }

  for (const std::filesystem::path &setPath : setPaths) {
    const PackageMaintenanceSetLoadResult set =
        loadPackageMaintenanceSet(setPath);
    appendDiagnostics(diagnostics, set.diagnostics);
    if (!set.success) {
      continue;
    }
    packagePaths.insert(packagePaths.end(), set.packagePaths.begin(),
                        set.packagePaths.end());
  }
  sortUniquePaths(packagePaths);
  return packagePaths;
}

std::optional<std::string>
readReleasePromotionArtifactFile(const std::filesystem::path &path,
                                 std::vector<Diagnostic> &diagnostics) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    diagnostics.push_back(releasePromotionError(
        "artifact-read-failed",
        "failed to read package release artifact: " + path.string(), path));
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    diagnostics.push_back(releasePromotionError(
        "artifact-read-failed",
        "failed to read package release artifact: " + path.string(), path));
    return std::nullopt;
  }
  return buffer.str();
}

bool validateReleasePromotionSourceHash(
    const PackageMetadata &metadata, std::vector<Diagnostic> &diagnostics) {
  const std::filesystem::path manifestPath =
      metadata.packagePath / "manifest.json";
  if (!metadata.sourceHashAlgorithm || !metadata.sourceHashValue) {
    diagnostics.push_back(releasePromotionError(
        "invalid-source-hash",
        "package release promotion requires manifest sourceHash algorithm "
        "and value",
        manifestPath));
    return false;
  }
  if (*metadata.sourceHashAlgorithm != "sha256") {
    diagnostics.push_back(releasePromotionError(
        "invalid-source-hash",
        "package release promotion requires manifest sourceHash.algorithm "
        "to be sha256",
        manifestPath));
    return false;
  }
  if (!isSha256Digest(*metadata.sourceHashValue)) {
    diagnostics.push_back(releasePromotionError(
        "invalid-source-hash",
        "package release promotion requires manifest sourceHash.value to be "
        "a lowercase SHA-256 digest",
        manifestPath));
    return false;
  }
  return true;
}

std::optional<PackageReleasePackageArtifactRequirements>
packageReleaseArtifactRequirementsRecord(
    const PackageMetadata &metadata, std::vector<Diagnostic> &diagnostics) {
  const std::filesystem::path manifestPath =
      metadata.packagePath / "manifest.json";
  if (!metadata.artifactRequirements) {
    diagnostics.push_back(releasePromotionError(
        "missing-artifact-requirements",
        "package release promotion requires manifest "
        "packageArtifactRequirements",
        manifestPath));
    return std::nullopt;
  }

  const PackageArtifactRequirementsRecord &metadataRequirements =
      *metadata.artifactRequirements;
  PackageReleasePackageArtifactRequirements requirements;
  requirements.target = metadataRequirements.target;
  requirements.packageMode = metadataRequirements.packageMode;
  requirements.requiresNativeBinaryStatus =
      metadataRequirements.requiresNativeBinaryStatus;
  requirements.allowsPlannedNativeBinary =
      metadataRequirements.allowsPlannedNativeBinary;
  requirements.allowsPlannedNativeSourceEvidence =
      metadataRequirements.allowsPlannedNativeSourceEvidence;
  for (const PackageRequiredPathArtifactRecord &artifact :
       metadataRequirements.requiredPathArtifacts) {
    requirements.requiredPathArtifacts.push_back(artifact.name);
  }

  DiagnosticEngine requirementDiagnostics;
  if (!validateReleasePackageArtifactRequirements(
          requirements, metadata.target, manifestPath, requirementDiagnostics,
          releasePromotionDiagnosticCode("invalid-artifact-requirements"),
          "package release promotion")) {
    appendDiagnostics(diagnostics, requirementDiagnostics.diagnostics());
    return std::nullopt;
  }
  return requirements;
}

PackageReleasePromotionArtifact
packageReleasePromotionArtifactRecord(const PackageMetadata &metadata,
                                      const PackageArtifactRecord &artifact,
                                      std::vector<Diagnostic> &diagnostics) {
  PackageReleasePromotionArtifact record;
  record.name = artifact.name;
  record.path = artifact.path;
  record.exists = artifact.exists;
  record.sizeBytes = artifact.sizeBytes;
  if (artifact.exists && artifact.packageRelative) {
    const std::filesystem::path artifactPath =
        (metadata.packagePath / artifact.path).lexically_normal();
    const std::optional<std::string> contents =
        readReleasePromotionArtifactFile(artifactPath, diagnostics);
    if (contents) {
      record.sha256 = sha256(*contents);
    }
  }
  return record;
}

void validateReleasePromotionNativeArtifactDescriptorHealth(
    const PackageMetadata &metadata,
    const PackageReleasePromotionPackage &package,
    std::vector<Diagnostic> &diagnostics) {
  if (!releasePackageClaimsNativeReadiness(package)) {
    return;
  }

  const PackageNativeArtifactDescriptorHealth health =
      collectPackageNativeArtifactDescriptorHealth(metadata);
  if (!health.descriptorExists) {
    return;
  }
  if (health.health != "ok") {
    diagnostics.push_back(releasePromotionError(
        "invalid-native-artifact-descriptor",
        "package release promotion requires nativeArtifactDescriptor health "
        "ok when native readiness is recorded; got " +
            health.health,
        metadata.packagePath / health.path.value_or("manifest.json")));
  }
}

std::optional<PackageReleasePromotionPackage>
packageReleasePromotionPackageRecord(const std::filesystem::path &packagePath,
                                     std::vector<Diagnostic> &diagnostics) {
  std::error_code existsError;
  if (!std::filesystem::exists(packagePath, existsError) || existsError) {
    return std::nullopt;
  }

  DiagnosticEngine metadataDiagnostics;
  PackageMetadataLoadOptions metadataOptions;
  metadataOptions.diagnosticCodePrefix = "package.release.promotion.inventory";
  metadataOptions.commandName = "package release";
  std::optional<PackageMetadata> loadedMetadata =
      loadPackageMetadata(packagePath, metadataDiagnostics, metadataOptions);
  appendDiagnostics(diagnostics, metadataDiagnostics.diagnostics());
  if (!loadedMetadata) {
    return std::nullopt;
  }

  const PackageMetadata &metadata = *loadedMetadata;
  PackageReleasePromotionPackage record;
  record.packagePath = metadata.packagePath;
  record.module = metadata.module;
  record.target = metadata.target;
  if (validateReleasePromotionSourceHash(metadata, diagnostics)) {
    record.sourceHash = PackageReleasePromotionSourceHash{
        *metadata.sourceHashAlgorithm, *metadata.sourceHashValue};
  }
  record.nativeBinaryStatus = metadata.nativeBinaryStatus;
  record.artifactRequirements =
      packageReleaseArtifactRequirementsRecord(metadata, diagnostics);
  for (const PackageArtifactRecord &artifact : metadata.artifacts) {
    record.artifacts.push_back(
        packageReleasePromotionArtifactRecord(metadata, artifact, diagnostics));
  }
  std::sort(record.artifacts.begin(), record.artifacts.end(),
            [](const PackageReleasePromotionArtifact &lhs,
               const PackageReleasePromotionArtifact &rhs) {
              if (lhs.name != rhs.name) {
                return lhs.name < rhs.name;
              }
              return lhs.path < rhs.path;
            });
  DiagnosticEngine requirementDiagnostics;
  validateReleasePackageArtifactsAgainstRequirements(
      record, metadata.packagePath / "manifest.json", requirementDiagnostics,
      releasePromotionDiagnosticCode("artifact-requirements-mismatch"),
      "package release promotion");
  appendDiagnostics(diagnostics, requirementDiagnostics.diagnostics());
  validateReleasePromotionNativeArtifactDescriptorHealth(metadata, record,
                                                        diagnostics);
  return record;
}

PackageReleasePromotionInventoryLoadResult collectReleasePromotionInventory(
    const std::vector<std::filesystem::path> &setPaths) {
  PackageReleasePromotionInventoryLoadResult result;
  const std::vector<std::filesystem::path> packagePaths =
      packagePathsForReleasePromotion(setPaths, result.diagnostics);
  for (const std::filesystem::path &packagePath : packagePaths) {
    std::optional<PackageReleasePromotionPackage> package =
        packageReleasePromotionPackageRecord(packagePath, result.diagnostics);
    if (package) {
      result.packages.push_back(std::move(*package));
    }
  }
  std::sort(result.packages.begin(), result.packages.end(),
            [](const PackageReleasePromotionPackage &lhs,
               const PackageReleasePromotionPackage &rhs) {
              return lhs.packagePath.generic_string() <
                     rhs.packagePath.generic_string();
            });
  return result;
}

PackageReleasePromotionManifestResult exportPackageReleasePromotionManifest(
    const std::filesystem::path &summaryPath,
    const std::filesystem::path &manifestPath) {
  DiagnosticEngine diagnostics;
  PackageReleasePromotionManifestResult result;
  result.summaryPath = summaryPath;
  result.manifestPath = manifestPath;

  const PackageReleasePromotionSummaryLoadResult summary =
      loadPackageReleasePromotionSummary(summaryPath);
  result.diagnostics = summary.diagnostics;
  result.summary = summary.summary;
  result.releaseEligible = summary.success && summary.summary.releaseEligible &&
                           summary.summary.success && summary.summary.matches;
  result.blockers = packageReleasePromotionBlockers(result.summary);
  if (!summary.success) {
    return result;
  }

  if (result.releaseEligible && result.blockers.empty()) {
    const PackageReleasePromotionInventoryLoadResult inventory =
        collectReleasePromotionInventory(summary.packageSetPaths);
    result.packages = inventory.packages;
    appendDiagnostics(result.diagnostics, inventory.diagnostics);
    const std::size_t inventoryErrorCount =
        countDiagnostics(inventory.diagnostics, DiagnosticSeverity::Error);
    if (inventoryErrorCount != 0) {
      result.blockers.push_back(
          {"package-inventory-failed",
           "package release promotion package inventory could not be "
           "collected",
           inventoryErrorCount});
      sortPackageReleasePromotionBlockers(result.blockers);
      result.releaseEligible = false;
    }
  }

  std::error_code statusError;
  if (std::filesystem::exists(manifestPath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(manifestPath, statusError)) {
    diagnostics.error(releasePromotionDiagnosticCode("invalid-output"),
                      "package release promotion manifest output path is not "
                      "a regular file: " +
                          manifestPath.string(),
                      pathLocation(manifestPath));
    const std::vector<Diagnostic> manifestDiagnostics =
        diagnostics.diagnostics();
    result.diagnostics.insert(result.diagnostics.end(),
                              manifestDiagnostics.begin(),
                              manifestDiagnostics.end());
    return result;
  }

  std::ofstream output(manifestPath, std::ios::binary | std::ios::trunc);
  if (!output) {
    diagnostics.error(releasePromotionDiagnosticCode("write-failed"),
                      "failed to write package release promotion manifest: " +
                          manifestPath.string(),
                      pathLocation(manifestPath));
    const std::vector<Diagnostic> manifestDiagnostics =
        diagnostics.diagnostics();
    result.diagnostics.insert(result.diagnostics.end(),
                              manifestDiagnostics.begin(),
                              manifestDiagnostics.end());
    return result;
  }
  output << packageReleasePromotionManifestJson(result);
  if (!output) {
    diagnostics.error(releasePromotionDiagnosticCode("write-failed"),
                      "failed to write package release promotion manifest: " +
                          manifestPath.string(),
                      pathLocation(manifestPath));
    const std::vector<Diagnostic> manifestDiagnostics =
        diagnostics.diagnostics();
    result.diagnostics.insert(result.diagnostics.end(),
                              manifestDiagnostics.begin(),
                              manifestDiagnostics.end());
    return result;
  }

  const std::vector<Diagnostic> manifestDiagnostics = diagnostics.diagnostics();
  result.diagnostics.insert(result.diagnostics.end(),
                            manifestDiagnostics.begin(),
                            manifestDiagnostics.end());
  result.manifestWritten = true;
  result.success =
      result.releaseEligible &&
      countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
  return result;
}

PackageReleaseBundleManifestResult exportPackageReleaseBundleManifest(
    const PackageReleasePromotionManifestResult &promotion,
    const std::filesystem::path &bundlePath) {
  DiagnosticEngine diagnostics;
  PackageReleaseBundleManifestResult result;
  result.bundlePath = bundlePath;
  result.promotionManifestPath = promotion.manifestPath;
  result.promotion = promotion;
  result.releaseEligible = promotion.releaseEligible;

  if (!promotion.manifestWritten) {
    result.diagnostics.push_back(releasePromotionError(
        "missing-promotion-manifest",
        "package release bundle requires a written promotion manifest",
        promotion.manifestPath));
    return result;
  }

  std::error_code statusError;
  if (std::filesystem::exists(bundlePath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(bundlePath, statusError)) {
    diagnostics.error(releasePromotionDiagnosticCode("invalid-bundle-output"),
                      "package release bundle output path is not a regular "
                      "file: " +
                          bundlePath.string(),
                      pathLocation(bundlePath));
    const std::vector<Diagnostic> bundleDiagnostics = diagnostics.diagnostics();
    result.diagnostics.insert(result.diagnostics.end(),
                              bundleDiagnostics.begin(),
                              bundleDiagnostics.end());
    return result;
  }

  std::ofstream output(bundlePath, std::ios::binary | std::ios::trunc);
  if (!output) {
    diagnostics.error(releasePromotionDiagnosticCode("bundle-write-failed"),
                      "failed to write package release bundle: " +
                          bundlePath.string(),
                      pathLocation(bundlePath));
    const std::vector<Diagnostic> bundleDiagnostics = diagnostics.diagnostics();
    result.diagnostics.insert(result.diagnostics.end(),
                              bundleDiagnostics.begin(),
                              bundleDiagnostics.end());
    return result;
  }
  output << packageReleaseBundleManifestJson(result);
  if (!output) {
    diagnostics.error(releasePromotionDiagnosticCode("bundle-write-failed"),
                      "failed to write package release bundle: " +
                          bundlePath.string(),
                      pathLocation(bundlePath));
    const std::vector<Diagnostic> bundleDiagnostics = diagnostics.diagnostics();
    result.diagnostics.insert(result.diagnostics.end(),
                              bundleDiagnostics.begin(),
                              bundleDiagnostics.end());
    return result;
  }

  const std::vector<Diagnostic> bundleDiagnostics = diagnostics.diagnostics();
  result.diagnostics.insert(result.diagnostics.end(), bundleDiagnostics.begin(),
                            bundleDiagnostics.end());
  result.bundleWritten = true;
  result.success =
      countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
  return result;
}

std::optional<std::string>
readReleaseBundleArtifactFile(const std::filesystem::path &path,
                              std::vector<Diagnostic> &diagnostics) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    diagnostics.push_back(releaseBundleError(
        "artifact-read-failed",
        "failed to read package release bundle artifact: " + path.string(),
        path));
    return std::nullopt;
  }
  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    diagnostics.push_back(releaseBundleError(
        "artifact-read-failed",
        "failed to read package release bundle artifact: " + path.string(),
        path));
    return std::nullopt;
  }
  return buffer.str();
}

std::optional<std::string> readReleasePublishArtifactFile(
    const std::filesystem::path &path, std::vector<Diagnostic> &diagnostics,
    std::string_view suffix, std::string_view label) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    diagnostics.push_back(
        releasePublishError(suffix,
                            "failed to read package release publish " +
                                std::string(label) + ": " + path.string(),
                            path));
    return std::nullopt;
  }
  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    diagnostics.push_back(
        releasePublishError(suffix,
                            "failed to read package release publish " +
                                std::string(label) + ": " + path.string(),
                            path));
    return std::nullopt;
  }
  return buffer.str();
}

void verifyReleaseBundleNativeArtifactDescriptor(
    const PackageReleasePromotionPackage &package,
    PackageReleaseBundleVerificationResult &result) {
  if (!releasePackageClaimsNativeReadiness(package)) {
    return;
  }

  DiagnosticEngine metadataDiagnostics;
  PackageMetadataLoadOptions metadataOptions;
  metadataOptions.diagnosticCodePrefix =
      "package.release.bundle.native-artifact";
  metadataOptions.commandName = "package release bundle verification";
  std::optional<PackageMetadata> metadata =
      loadPackageMetadata(package.packagePath, metadataDiagnostics,
                          metadataOptions);
  appendDiagnostics(result.diagnostics, metadataDiagnostics.diagnostics());
  if (!metadata) {
    return;
  }

  const PackageNativeArtifactDescriptorHealth health =
      collectPackageNativeArtifactDescriptorHealth(*metadata);
  if (!health.descriptorExists) {
    result.diagnostics.push_back(releaseBundleError(
        "native-artifact-descriptor-missing",
        "package release bundle requires nativeArtifactDescriptor evidence "
        "when native readiness is recorded",
        package.packagePath / health.path.value_or("manifest.json")));
    return;
  }
  if (health.health != "ok") {
    result.diagnostics.push_back(releaseBundleError(
        "invalid-native-artifact-descriptor",
        "package release bundle requires nativeArtifactDescriptor health ok "
        "when native readiness is recorded; got " +
            health.health,
        package.packagePath / health.path.value_or("manifest.json")));
  }
}

void verifyReleaseBundleArtifacts(
    const PackageReleaseBundleParsedDocument &document,
    PackageReleaseBundleVerificationResult &result) {
  for (const PackageReleaseBundleParsedPackage &parsedPackage :
       document.packages) {
    const PackageReleasePromotionPackage &package = parsedPackage.package;
    std::error_code packageStatusError;
    const bool packageExists =
        std::filesystem::exists(package.packagePath, packageStatusError);
    if (packageStatusError || !packageExists) {
      result.diagnostics.push_back(releaseBundleError(
          "package-missing",
          "package release bundle package path does not exist: " +
              package.packagePath.string(),
          package.packagePath));
      continue;
    }
    if (!std::filesystem::is_directory(package.packagePath,
                                       packageStatusError) ||
        packageStatusError) {
      result.diagnostics.push_back(releaseBundleError(
          "package-not-directory",
          "package release bundle package path is not a directory: " +
              package.packagePath.string(),
          package.packagePath));
      continue;
    }

    verifyReleaseBundleNativeArtifactDescriptor(package, result);

    for (const PackageReleasePromotionArtifact &artifact : package.artifacts) {
      const std::filesystem::path artifactPath =
          (package.packagePath / artifact.path).lexically_normal();
      std::error_code artifactStatusError;
      const bool artifactExists =
          std::filesystem::exists(artifactPath, artifactStatusError);
      if (artifactStatusError) {
        result.diagnostics.push_back(releaseBundleError(
            "artifact-stat-failed",
            "failed to inspect package release bundle artifact: " +
                artifactPath.string(),
            artifactPath));
        continue;
      }

      if (!artifact.exists) {
        if (artifactExists) {
          result.diagnostics.push_back(releaseBundleError(
              "unexpected-artifact",
              "package release bundle artifact was declared missing but "
              "exists: " +
                  artifactPath.string(),
              artifactPath));
        }
        continue;
      }

      if (!artifactExists) {
        result.diagnostics.push_back(releaseBundleError(
            "artifact-missing",
            "package release bundle artifact does not exist: " +
                artifactPath.string(),
            artifactPath));
        continue;
      }
      if (!std::filesystem::is_regular_file(artifactPath,
                                            artifactStatusError) ||
          artifactStatusError) {
        result.diagnostics.push_back(releaseBundleError(
            "artifact-not-file",
            "package release bundle artifact is not a regular file: " +
                artifactPath.string(),
            artifactPath));
        continue;
      }

      const std::uintmax_t actualSize =
          std::filesystem::file_size(artifactPath, artifactStatusError);
      if (artifactStatusError) {
        result.diagnostics.push_back(releaseBundleError(
            "artifact-stat-failed",
            "failed to inspect package release bundle artifact: " +
                artifactPath.string(),
            artifactPath));
        continue;
      }
      if (!artifact.sizeBytes || actualSize != *artifact.sizeBytes) {
        result.diagnostics.push_back(releaseBundleError(
            "artifact-size-mismatch",
            "package release bundle artifact size does not match: " +
                artifactPath.string(),
            artifactPath));
        continue;
      }

      const std::optional<std::string> contents =
          readReleaseBundleArtifactFile(artifactPath, result.diagnostics);
      if (!contents) {
        continue;
      }
      const std::string actualHash = sha256(*contents);
      if (!artifact.sha256 || actualHash != *artifact.sha256) {
        result.diagnostics.push_back(releaseBundleError(
            "artifact-hash-mismatch",
            "package release bundle artifact sha256 does not match: " +
                artifactPath.string(),
            artifactPath));
        continue;
      }
      ++result.verifiedArtifactCount;
    }
  }
}

PackageReleaseBundleVerificationResult
verifyPackageReleaseBundleManifest(const std::filesystem::path &bundlePath) {
  DiagnosticEngine diagnostics;
  PackageReleaseBundleVerificationResult result;
  result.bundlePath = bundlePath;

  const std::optional<std::string> text =
      readReleaseBundleManifestFile(bundlePath, diagnostics);
  if (!text) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  const std::optional<PackageReleaseBundleParsedDocument> document =
      parseReleaseBundleDocument(*text, bundlePath, diagnostics);
  result.diagnostics = diagnostics.diagnostics();
  if (!document) {
    return result;
  }

  result.releaseEligible = document->releaseEligible;
  result.status = document->status;
  result.blockerCount = document->blockerCount;
  result.packageCount = document->packageCount;
  result.artifactCount = document->artifactCount;
  result.existingArtifactCount = document->existingArtifactCount;
  result.missingArtifactCount = document->missingArtifactCount;
  result.totalArtifactBytes = document->totalArtifactBytes;

  if (countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0 &&
      document->releaseEligible) {
    verifyReleaseBundleArtifacts(*document, result);
  }
  result.success =
      result.releaseEligible &&
      countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
  return result;
}

std::string releaseReportRecordIdentity(
    const PackageReleaseReportArtifactInventoryRecord &record) {
  return record.sourceRecordKind + "\n" +
         record.packagePath.lexically_normal().generic_string() + "\n" +
         std::filesystem::path(record.packageArtifactPath)
             .lexically_normal()
             .generic_string();
}

void appendReleaseReportRecord(
    PackageReleaseReportArtifactInventoryResult &result,
    std::map<std::string, std::filesystem::path> &identitySources,
    PackageReleaseReportArtifactInventoryRecord record,
    const std::filesystem::path &documentPath) {
  record.packagePath = record.packagePath.lexically_normal();
  record.packageArtifactPath =
      std::filesystem::path(record.packageArtifactPath)
          .lexically_normal()
          .generic_string();
  if (record.stagedPath) {
    record.stagedPath = record.stagedPath->lexically_normal();
  }
  const std::string identity = releaseReportRecordIdentity(record);
  const auto inserted = identitySources.emplace(identity, documentPath);
  if (!inserted.second) {
    result.diagnostics.push_back(releaseReportError(
        "duplicate-artifact-identity",
        "package release report artifact inventory contains duplicate "
        "artifact identity for " +
            record.sourceRecordKind + ": " +
            record.packagePath.lexically_normal().generic_string() + " " +
            record.packageArtifactPath,
        documentPath));
    return;
  }
  result.records.push_back(std::move(record));
}

void appendReleaseReportBundleRecords(
    PackageReleaseReportArtifactInventoryResult &result,
    std::map<std::string, std::filesystem::path> &identitySources,
    const PackageReleaseBundleParsedDocument &document,
    const std::filesystem::path &bundlePath) {
  for (const PackageReleaseBundleParsedPackage &parsedPackage :
       document.packages) {
    const PackageReleasePromotionPackage &package = parsedPackage.package;
    for (const PackageReleasePromotionArtifact &artifact : package.artifacts) {
      PackageReleaseReportArtifactInventoryRecord record;
      record.sourceRecordKind = "release-bundle";
      record.packagePath = package.packagePath;
      record.packageArtifactPath = artifact.path;
      record.sizeBytes = artifact.sizeBytes;
      record.sha256 = artifact.sha256;
      appendReleaseReportRecord(result, identitySources, std::move(record),
                                bundlePath);
    }
  }
}

void appendReleaseReportPlanRecords(
    PackageReleaseReportArtifactInventoryResult &result,
    std::map<std::string, std::filesystem::path> &identitySources,
    const PackageReleasePublishPlanParsedDocument &document,
    const std::filesystem::path &planPath) {
  for (const PackageReleasePublishPlanArtifact &artifact :
       document.artifacts) {
    PackageReleaseReportArtifactInventoryRecord record;
    record.sourceRecordKind = "publish-plan";
    record.packagePath = artifact.packagePath;
    record.packageArtifactPath = artifact.packageArtifactPath;
    record.destinationPath = artifact.destinationPath;
    record.sizeBytes = artifact.sizeBytes;
    record.sha256 = artifact.sha256;
    appendReleaseReportRecord(result, identitySources, std::move(record),
                              planPath);
  }
}

void appendReleaseReportStageRecords(
    PackageReleaseReportArtifactInventoryResult &result,
    std::map<std::string, std::filesystem::path> &identitySources,
    const PackageReleasePublishStageParsedDocument &document,
    const std::filesystem::path &stageReportPath) {
  for (const PackageReleasePublishStageArtifact &staged : document.artifacts) {
    const PackageReleasePublishPlanArtifact &artifact = staged.artifact;
    PackageReleaseReportArtifactInventoryRecord record;
    record.sourceRecordKind = "publish-stage";
    record.packagePath = artifact.packagePath;
    record.packageArtifactPath = artifact.packageArtifactPath;
    record.stagedPath = staged.stagedPath;
    record.destinationPath = artifact.destinationPath;
    record.sizeBytes = artifact.sizeBytes;
    record.sha256 = artifact.sha256;
    appendReleaseReportRecord(result, identitySources, std::move(record),
                              stageReportPath);
  }
}

void finalizeReleaseReportArtifactInventory(
    PackageReleaseReportArtifactInventoryResult &result) {
  std::sort(result.records.begin(), result.records.end(),
            [](const PackageReleaseReportArtifactInventoryRecord &lhs,
               const PackageReleaseReportArtifactInventoryRecord &rhs) {
              const auto key = [](const PackageReleaseReportArtifactInventoryRecord
                                      &record) {
                return std::tuple{
                    record.packagePath.lexically_normal().generic_string(),
                    record.packageArtifactPath, record.sourceRecordKind,
                    record.destinationPath.value_or(""),
                    record.stagedPath
                        ? record.stagedPath->lexically_normal()
                              .generic_string()
                        : std::string()};
              };
              return key(lhs) < key(rhs);
            });

  result.artifactRecordCount = result.records.size();
  result.bundleArtifactRecordCount = 0;
  result.publishPlanArtifactRecordCount = 0;
  result.publishStageArtifactRecordCount = 0;
  result.stagedArtifactRecordCount = 0;
  result.totalArtifactRecordBytes = 0;
  for (const PackageReleaseReportArtifactInventoryRecord &record :
       result.records) {
    if (record.sourceRecordKind == "release-bundle") {
      ++result.bundleArtifactRecordCount;
    } else if (record.sourceRecordKind == "publish-plan") {
      ++result.publishPlanArtifactRecordCount;
    } else if (record.sourceRecordKind == "publish-stage") {
      ++result.publishStageArtifactRecordCount;
    }
    if (record.stagedPath) {
      ++result.stagedArtifactRecordCount;
    }
    if (record.sizeBytes) {
      result.totalArtifactRecordBytes += *record.sizeBytes;
    }
  }
}

PackageReleaseReportArtifactInventoryResult
loadPackageReleaseReportArtifactInventory(
    const PackageReleaseReportArtifactInventoryOptions &options) {
  PackageReleaseReportArtifactInventoryResult result;
  result.bundlePath = options.bundlePath;
  result.publishPlanPath = options.publishPlanPath;
  result.stageReportPath = options.stageReportPath;

  if (!options.bundlePath && !options.publishPlanPath &&
      !options.stageReportPath) {
    result.diagnostics.push_back(releaseReportError(
        "missing-input",
        "package release report artifact inventory requires at least one "
        "release bundle, publish plan, or stage report path",
        {}));
    return result;
  }

  std::map<std::string, std::filesystem::path> identitySources;
  if (options.bundlePath) {
    DiagnosticEngine diagnostics;
    const std::optional<std::string> text =
        readReleaseBundleManifestFile(*options.bundlePath, diagnostics);
    if (text) {
      const std::optional<PackageReleaseBundleParsedDocument> document =
          parseReleaseBundleDocument(*text, *options.bundlePath, diagnostics);
      if (document) {
        appendReleaseReportBundleRecords(result, identitySources, *document,
                                         *options.bundlePath);
      }
    }
    appendReleaseReportInputDiagnostics(result.diagnostics,
                                        diagnostics.diagnostics());
  }

  if (options.publishPlanPath) {
    DiagnosticEngine diagnostics;
    const std::optional<std::string> text =
        readReleasePublishPlanFile(*options.publishPlanPath, diagnostics);
    if (text) {
      const std::optional<PackageReleasePublishPlanParsedDocument> document =
          parseReleasePublishPlanDocument(*text, *options.publishPlanPath,
                                          diagnostics);
      if (document) {
        appendReleaseReportPlanRecords(result, identitySources, *document,
                                       *options.publishPlanPath);
      }
    }
    appendReleaseReportInputDiagnostics(result.diagnostics,
                                        diagnostics.diagnostics());
  }

  if (options.stageReportPath) {
    DiagnosticEngine diagnostics;
    const std::optional<std::string> text =
        readReleasePublishStageReportFile(*options.stageReportPath,
                                          diagnostics);
    if (text) {
      const std::optional<PackageReleasePublishStageParsedDocument> document =
          parseReleasePublishStageDocument(*text, *options.stageReportPath,
                                           diagnostics);
      if (document) {
        appendReleaseReportStageRecords(result, identitySources, *document,
                                        *options.stageReportPath);
      }
    }
    appendReleaseReportInputDiagnostics(result.diagnostics,
                                        diagnostics.diagnostics());
  }

  finalizeReleaseReportArtifactInventory(result);
  result.success =
      countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
  return result;
}

std::string releasePublishSafeSegment(std::string_view value) {
  std::string segment;
  segment.reserve(value.size());
  for (char ch : value) {
    const unsigned char byte = static_cast<unsigned char>(ch);
    if (std::isalnum(byte) || ch == '.' || ch == '_' || ch == '-') {
      segment.push_back(ch);
    } else {
      segment.push_back('_');
    }
  }
  return segment.empty() ? "_" : segment;
}

std::string
releasePublishPackageSegment(const std::filesystem::path &packagePath) {
  std::string filename = packagePath.filename().generic_string();
  if (filename.empty()) {
    filename = "package";
  }
  const std::string digest =
      sha256(packagePath.lexically_normal().generic_string());
  return releasePublishSafeSegment(filename) + "-" + digest.substr(0, 16);
}

std::string
releasePublishDestinationPath(const PackageReleasePromotionPackage &package,
                              const PackageReleasePromotionArtifact &artifact) {
  const std::filesystem::path destination =
      std::filesystem::path("packages") /
      releasePublishSafeSegment(package.target) /
      releasePublishSafeSegment(package.module) /
      releasePublishPackageSegment(package.packagePath) /
      std::filesystem::path(artifact.path);
  return destination.lexically_normal().generic_string();
}

PackageReleasePublishPlanResult
exportPackageReleasePublishPlan(const std::filesystem::path &bundlePath,
                                const std::filesystem::path &planPath) {
  DiagnosticEngine diagnostics;
  PackageReleasePublishPlanResult result;
  result.bundlePath = bundlePath;
  result.planPath = planPath;
  result.verification = verifyPackageReleaseBundleManifest(bundlePath);
  result.releaseEligible = result.verification.releaseEligible;
  appendDiagnostics(result.diagnostics, result.verification.diagnostics);

  if (!result.verification.success) {
    if (countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0) {
      result.diagnostics.push_back(releasePublishError(
          "bundle-not-eligible",
          "package release publish plan requires an eligible verified bundle",
          bundlePath));
    }
    return result;
  }

  const std::optional<std::string> text =
      readReleaseBundleManifestFile(bundlePath, diagnostics);
  if (!text) {
    appendDiagnostics(result.diagnostics, diagnostics.diagnostics());
    return result;
  }
  const std::optional<PackageReleaseBundleParsedDocument> document =
      parseReleaseBundleDocument(*text, bundlePath, diagnostics);
  appendDiagnostics(result.diagnostics, diagnostics.diagnostics());
  if (!document) {
    return result;
  }

  std::map<std::string, std::filesystem::path> destinations;
  for (const PackageReleaseBundleParsedPackage &parsedPackage :
       document->packages) {
    const PackageReleasePromotionPackage &package = parsedPackage.package;
    PackageReleasePublishPlanPackage plannedPackage;
    plannedPackage.packagePath = package.packagePath;
    plannedPackage.module = package.module;
    plannedPackage.target = package.target;
    plannedPackage.sourceHash = package.sourceHash;
    plannedPackage.nativeBinaryStatus = package.nativeBinaryStatus;
    plannedPackage.artifactRequirements = package.artifactRequirements;

    for (const PackageReleasePromotionArtifact &artifact : package.artifacts) {
      if (!artifact.exists) {
        continue;
      }
      if (!artifact.sizeBytes || !artifact.sha256) {
        result.diagnostics.push_back(releasePublishError(
            "invalid-artifact",
            "package release publish plan requires verified artifact size and "
            "sha256: " +
                (package.packagePath / artifact.path)
                    .lexically_normal()
                    .string(),
            package.packagePath));
        continue;
      }

      PackageReleasePublishPlanArtifact plannedArtifact;
      plannedArtifact.name = artifact.name;
      plannedArtifact.packagePath = package.packagePath;
      plannedArtifact.module = package.module;
      plannedArtifact.target = package.target;
      plannedArtifact.packageArtifactPath = std::filesystem::path(artifact.path)
                                                .lexically_normal()
                                                .generic_string();
      plannedArtifact.sourcePath =
          (package.packagePath / artifact.path).lexically_normal();
      plannedArtifact.destinationPath =
          releasePublishDestinationPath(package, artifact);
      plannedArtifact.sizeBytes = *artifact.sizeBytes;
      plannedArtifact.sha256 = *artifact.sha256;

      const auto inserted = destinations.emplace(
          plannedArtifact.destinationPath, plannedArtifact.sourcePath);
      if (!inserted.second) {
        result.diagnostics.push_back(releasePublishError(
            "destination-collision",
            "package release publish destination is not unique: " +
                plannedArtifact.destinationPath,
            plannedArtifact.sourcePath));
      }

      plannedPackage.totalArtifactBytes += plannedArtifact.sizeBytes;
      result.totalArtifactBytes += plannedArtifact.sizeBytes;
      plannedPackage.artifacts.push_back(plannedArtifact);
      result.artifacts.push_back(std::move(plannedArtifact));
    }

    std::sort(plannedPackage.artifacts.begin(), plannedPackage.artifacts.end(),
              [](const PackageReleasePublishPlanArtifact &lhs,
                 const PackageReleasePublishPlanArtifact &rhs) {
                return lhs.destinationPath < rhs.destinationPath;
              });
    result.packages.push_back(std::move(plannedPackage));
  }

  std::sort(result.artifacts.begin(), result.artifacts.end(),
            [](const PackageReleasePublishPlanArtifact &lhs,
               const PackageReleasePublishPlanArtifact &rhs) {
              if (lhs.destinationPath == rhs.destinationPath) {
                return lhs.sourcePath.generic_string() <
                       rhs.sourcePath.generic_string();
              }
              return lhs.destinationPath < rhs.destinationPath;
            });

  if (countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) != 0) {
    return result;
  }

  std::error_code statusError;
  if (std::filesystem::exists(planPath, statusError) && !statusError &&
      !std::filesystem::is_regular_file(planPath, statusError)) {
    result.diagnostics.push_back(releasePublishError(
        "invalid-plan-output",
        "package release publish plan output path is not a regular file: " +
            planPath.string(),
        planPath));
    return result;
  }

  std::ofstream output(planPath, std::ios::binary | std::ios::trunc);
  if (!output) {
    result.diagnostics.push_back(releasePublishError(
        "plan-write-failed",
        "failed to write package release publish plan: " + planPath.string(),
        planPath));
    return result;
  }
  output << packageReleasePublishPlanJson(result);
  if (!output) {
    result.diagnostics.push_back(releasePublishError(
        "plan-write-failed",
        "failed to write package release publish plan: " + planPath.string(),
        planPath));
    return result;
  }

  result.planWritten = true;
  result.success =
      countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
  return result;
}

PackageReleasePublishStageResult
stagePackageReleasePublishPlan(const std::filesystem::path &planPath,
                               const std::filesystem::path &stagePath) {
  DiagnosticEngine diagnostics;
  PackageReleasePublishStageResult result;
  result.planPath = planPath;
  result.stagePath = stagePath;

  const std::optional<std::string> text =
      readReleasePublishPlanFile(planPath, diagnostics);
  if (!text) {
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }
  const std::optional<PackageReleasePublishPlanParsedDocument> document =
      parseReleasePublishPlanDocument(*text, planPath, diagnostics);
  result.diagnostics = diagnostics.diagnostics();
  if (!document) {
    return result;
  }

  result.packageCount = document->packageCount;
  result.artifactCount = document->artifactCount;
  result.totalArtifactBytes = document->totalArtifactBytes;
  for (const PackageReleasePublishPlanArtifact &artifact :
       document->artifacts) {
    PackageReleasePublishStageArtifact staged;
    staged.artifact = artifact;
    staged.stagedPath =
        (stagePath / std::filesystem::path(artifact.destinationPath))
            .lexically_normal();
    result.artifacts.push_back(std::move(staged));
  }

  if (countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) != 0) {
    return result;
  }

  for (const PackageReleasePublishStageArtifact &staged : result.artifacts) {
    const PackageReleasePublishPlanArtifact &artifact = staged.artifact;
    std::error_code statusError;
    const bool sourceExists =
        std::filesystem::exists(artifact.sourcePath, statusError);
    if (statusError || !sourceExists) {
      result.diagnostics.push_back(releasePublishError(
          "source-missing",
          "package release publish source artifact does not exist: " +
              artifact.sourcePath.string(),
          artifact.sourcePath));
      continue;
    }
    if (!std::filesystem::is_regular_file(artifact.sourcePath, statusError) ||
        statusError) {
      result.diagnostics.push_back(releasePublishError(
          "source-not-file",
          "package release publish source artifact is not a regular file: " +
              artifact.sourcePath.string(),
          artifact.sourcePath));
      continue;
    }

    const std::uintmax_t actualSize =
        std::filesystem::file_size(artifact.sourcePath, statusError);
    if (statusError) {
      result.diagnostics.push_back(releasePublishError(
          "source-stat-failed",
          "failed to inspect package release publish source artifact: " +
              artifact.sourcePath.string(),
          artifact.sourcePath));
      continue;
    }
    if (actualSize != artifact.sizeBytes) {
      result.diagnostics.push_back(releasePublishError(
          "source-size-mismatch",
          "package release publish source artifact size does not match plan: " +
              artifact.sourcePath.string(),
          artifact.sourcePath));
      continue;
    }

    const std::optional<std::string> contents =
        readReleasePublishArtifactFile(artifact.sourcePath, result.diagnostics,
                                       "source-read-failed", "source artifact");
    if (!contents) {
      continue;
    }
    const std::string actualHash = sha256(*contents);
    if (actualHash != artifact.sha256) {
      result.diagnostics.push_back(releasePublishError(
          "source-hash-mismatch",
          "package release publish source artifact sha256 does not match "
          "plan: " +
              artifact.sourcePath.string(),
          artifact.sourcePath));
    }
  }

  if (countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) != 0) {
    return result;
  }

  std::error_code statusError;
  if (std::filesystem::exists(stagePath, statusError) && !statusError &&
      !std::filesystem::is_directory(stagePath, statusError)) {
    result.diagnostics.push_back(releasePublishError(
        "invalid-stage-output",
        "package release publish stage output path is not a directory: " +
            stagePath.string(),
        stagePath));
    return result;
  }
  std::filesystem::create_directories(stagePath, statusError);
  if (statusError) {
    result.diagnostics.push_back(releasePublishError(
        "stage-create-failed",
        "failed to create package release publish stage output: " +
            stagePath.string(),
        stagePath));
    return result;
  }

  for (PackageReleasePublishStageArtifact &staged : result.artifacts) {
    const PackageReleasePublishPlanArtifact &artifact = staged.artifact;
    const std::filesystem::path parent = staged.stagedPath.parent_path();
    if (!parent.empty()) {
      std::filesystem::create_directories(parent, statusError);
      if (statusError) {
        result.diagnostics.push_back(releasePublishError(
            "stage-create-failed",
            "failed to create package release publish artifact directory: " +
                parent.string(),
            parent));
        continue;
      }
    }

    std::filesystem::copy_file(
        artifact.sourcePath, staged.stagedPath,
        std::filesystem::copy_options::overwrite_existing, statusError);
    if (statusError) {
      result.diagnostics.push_back(releasePublishError(
          "stage-copy-failed",
          "failed to copy package release publish artifact: " +
              staged.stagedPath.string(),
          staged.stagedPath));
      continue;
    }

    const std::uintmax_t stagedSize =
        std::filesystem::file_size(staged.stagedPath, statusError);
    if (statusError || stagedSize != artifact.sizeBytes) {
      result.diagnostics.push_back(releasePublishError(
          "stage-size-mismatch",
          "package release publish staged artifact size does not match plan: " +
              staged.stagedPath.string(),
          staged.stagedPath));
      continue;
    }
    const std::optional<std::string> stagedContents =
        readReleasePublishArtifactFile(staged.stagedPath, result.diagnostics,
                                       "stage-read-failed", "staged artifact");
    if (!stagedContents) {
      continue;
    }
    const std::string stagedHash = sha256(*stagedContents);
    if (stagedHash != artifact.sha256) {
      result.diagnostics.push_back(releasePublishError(
          "stage-hash-mismatch",
          "package release publish staged artifact sha256 does not match "
          "plan: " +
              staged.stagedPath.string(),
          staged.stagedPath));
      continue;
    }

    staged.staged = true;
    ++result.stagedArtifactCount;
    result.stagedArtifactBytes += artifact.sizeBytes;
  }

  result.success =
      result.stagedArtifactCount == result.artifactCount &&
      countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
  return result;
}

struct ReleasePublishTargetBackend;
struct ReleasePublishTargetDescriptor;

using ReleasePublishApplyDescriptorFn = void (*)(
    const ReleasePublishTargetDescriptor &, const std::filesystem::path &,
    PackageReleasePublishReceiptResult &);
using ReleasePublishResolveOptionsFn = void (*)(
    const ReleasePublishTargetBackend &, const PackageReleasePublishOptions &,
    PackageReleasePublishReceiptResult &);
using ReleasePublishPublishedPathFn = std::string (*)(
    const PackageReleasePublishReceiptResult &, std::string_view);
using ReleasePublishValidateStageFn =
    void (*)(const PackageReleasePublishStageParsedDocument &,
             PackageReleasePublishReceiptResult &);
using ReleasePublishBuildUploadRequestFn =
    std::optional<PackageReleasePublishUploadRequest> (*)(
        const PackageReleasePublishReceiptResult &,
        const PackageReleasePublishReceiptArtifact &);
using ReleasePublishApplyFn = bool (*)(PackageReleasePublishReceiptResult &);

struct ReleasePublishTargetBackend {
  std::string_view kind;
  bool descriptorRequired = false;
  bool dryRunRequired = false;
  bool disabledDescriptorRequired = false;
  bool defaultEnabled = false;
  bool uriTarget = false;
  ReleasePublishApplyDescriptorFn applyDescriptor = nullptr;
  ReleasePublishResolveOptionsFn resolveOptions = nullptr;
  ReleasePublishPublishedPathFn publishedPath = nullptr;
  ReleasePublishValidateStageFn validateStage = nullptr;
  ReleasePublishBuildUploadRequestFn buildUploadRequest = nullptr;
  ReleasePublishApplyFn apply = nullptr;
};

void applyLocalReleasePublishTargetDescriptor(
    const ReleasePublishTargetDescriptor &descriptor,
    const std::filesystem::path &descriptorPath,
    PackageReleasePublishReceiptResult &result);
void applyGcsReleasePublishTargetDescriptor(
    const ReleasePublishTargetDescriptor &descriptor,
    const std::filesystem::path &descriptorPath,
    PackageReleasePublishReceiptResult &result);
void resolveLocalReleasePublishTarget(
    const ReleasePublishTargetBackend &backend,
    const PackageReleasePublishOptions &options,
    PackageReleasePublishReceiptResult &result);
void resolvePlanOnlyReleasePublishTarget(
    const ReleasePublishTargetBackend &backend,
    const PackageReleasePublishOptions &options,
    PackageReleasePublishReceiptResult &result);
std::string localReleasePublishPublishedPath(
    const PackageReleasePublishReceiptResult &result,
    std::string_view destinationPath);
std::string
uriReleasePublishPublishedPath(const PackageReleasePublishReceiptResult &result,
                               std::string_view destinationPath);
void validateLocalReleasePublishStageTarget(
    const PackageReleasePublishStageParsedDocument &document,
    PackageReleasePublishReceiptResult &result);
void validatePlanOnlyReleasePublishStageTarget(
    const PackageReleasePublishStageParsedDocument &document,
    PackageReleasePublishReceiptResult &result);
std::optional<PackageReleasePublishUploadRequest>
buildNoopReleasePublishUploadRequest(
    const PackageReleasePublishReceiptResult &result,
    const PackageReleasePublishReceiptArtifact &artifact);
std::optional<PackageReleasePublishUploadRequest>
buildGcsReleasePublishUploadRequest(
    const PackageReleasePublishReceiptResult &result,
    const PackageReleasePublishReceiptArtifact &artifact);
bool applyLocalReleasePublish(PackageReleasePublishReceiptResult &result);
bool applyPlanOnlyReleasePublishTarget(
    PackageReleasePublishReceiptResult &result);

const ReleasePublishTargetBackend *
findReleasePublishTargetBackend(std::string_view targetKind) {
  static constexpr ReleasePublishTargetBackend kReleasePublishTargetBackends[] =
      {
          {"local-filesystem", false, false, false, true, false,
           applyLocalReleasePublishTargetDescriptor,
           resolveLocalReleasePublishTarget, localReleasePublishPublishedPath,
           validateLocalReleasePublishStageTarget,
           buildNoopReleasePublishUploadRequest, applyLocalReleasePublish},
          {"gcs", true, true, true, false, true,
           applyGcsReleasePublishTargetDescriptor,
           resolvePlanOnlyReleasePublishTarget, uriReleasePublishPublishedPath,
           validatePlanOnlyReleasePublishStageTarget,
           buildGcsReleasePublishUploadRequest,
           applyPlanOnlyReleasePublishTarget},
      };
  for (const ReleasePublishTargetBackend &backend :
       kReleasePublishTargetBackends) {
    if (backend.kind == targetKind) {
      return &backend;
    }
  }
  return nullptr;
}

bool looksLikeCloudReleasePublishTarget(const std::filesystem::path &path) {
  const std::string text = path.generic_string();
  return text.find("://") != std::string::npos;
}

std::string
normalizedReleasePublishPathString(const std::filesystem::path &path) {
  return path.lexically_normal().generic_string();
}

std::string joinReleasePublishUri(std::string_view base,
                                  std::string_view destinationPath) {
  std::string joined(base);
  while (!joined.empty() && joined.back() == '/') {
    joined.pop_back();
  }
  if (!destinationPath.empty()) {
    joined += "/";
    joined += destinationPath;
  }
  return joined;
}

std::string joinReleasePublishLocalPath(const std::filesystem::path &base,
                                        std::string_view destinationPath) {
  return normalizedReleasePublishPathString(
      base / std::filesystem::path(std::string(destinationPath)));
}

bool isReleasePublishGcsBucketName(std::string_view value) {
  if (value.size() < 3 || value.size() > 63) {
    return false;
  }
  const auto isLowercaseAlphaNumeric = [](char ch) {
    return (ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9');
  };
  if (!isLowercaseAlphaNumeric(value.front()) ||
      !isLowercaseAlphaNumeric(value.back())) {
    return false;
  }
  for (char ch : value) {
    if (!isLowercaseAlphaNumeric(ch) && ch != '-' && ch != '_' && ch != '.') {
      return false;
    }
  }
  return value.find('/') == std::string_view::npos &&
         value.find('\\') == std::string_view::npos;
}

std::string releasePublishGcsUri(std::string_view bucket,
                                 std::string_view prefix) {
  std::string uri = "gs://";
  uri += bucket;
  if (!prefix.empty()) {
    uri += "/";
    uri += prefix;
  }
  return uri;
}

std::string releasePublishGcsObjectName(std::string_view prefix,
                                        std::string_view destinationPath) {
  if (prefix.empty()) {
    return std::string(destinationPath);
  }
  std::string objectName(prefix);
  objectName += "/";
  objectName += destinationPath;
  return objectName;
}

struct ReleasePublishTargetDescriptor {
  std::string targetKind;
  bool enabled = false;
  std::optional<std::string> targetPath;
  std::optional<std::string> bucket;
  std::optional<std::string> prefix;
  std::optional<std::string> credentialsEnv;
};

std::optional<ReleasePublishTargetDescriptor>
parseReleasePublishTargetDescriptor(std::string_view text,
                                    const std::filesystem::path &descriptorPath,
                                    std::vector<Diagnostic> &diagnostics) {
  const std::size_t initialErrorCount =
      countDiagnostics(diagnostics, DiagnosticSeverity::Error);
  const std::optional<std::string_view> schemaVersionText =
      findObjectMemberValue(text, "schemaVersion");
  if (!schemaVersionText) {
    diagnostics.push_back(releasePublishError(
        "missing-field",
        "package release publish target descriptor requires schemaVersion: 1",
        descriptorPath));
  } else {
    const std::optional<std::uintmax_t> schemaVersion =
        parseUnsignedInteger(*schemaVersionText);
    if (!schemaVersion || *schemaVersion != 1) {
      diagnostics.push_back(releasePublishError(
          "invalid-schema-version",
          "package release publish target descriptor requires schemaVersion: 1",
          descriptorPath));
    }
  }

  ReleasePublishTargetDescriptor descriptor;
  if (const std::optional<std::string> targetKind =
          objectStringMember(text, "targetKind")) {
    descriptor.targetKind = *targetKind;
  } else {
    diagnostics.push_back(releasePublishError(
        findObjectMemberValue(text, "targetKind") ? "invalid-field"
                                                  : "missing-field",
        "package release publish target descriptor requires string field: "
        "targetKind",
        descriptorPath));
  }

  if (const std::optional<bool> enabled = objectBoolMember(text, "enabled")) {
    descriptor.enabled = *enabled;
  } else {
    diagnostics.push_back(releasePublishError(
        findObjectMemberValue(text, "enabled") ? "invalid-field"
                                               : "missing-field",
        "package release publish target descriptor requires boolean field: "
        "enabled",
        descriptorPath));
  }

  parseOptionalReleasePublishStringMember(text, "targetPath", descriptorPath,
                                          diagnostics, descriptor.targetPath);
  parseOptionalReleasePublishStringMember(text, "bucket", descriptorPath,
                                          diagnostics, descriptor.bucket);
  parseOptionalReleasePublishStringMember(text, "prefix", descriptorPath,
                                          diagnostics, descriptor.prefix);
  parseOptionalReleasePublishStringMember(text, "credentialsEnv",
                                          descriptorPath, diagnostics,
                                          descriptor.credentialsEnv);

  if (countDiagnostics(diagnostics, DiagnosticSeverity::Error) !=
      initialErrorCount) {
    return std::nullopt;
  }
  return descriptor;
}

void applyLocalReleasePublishTargetDescriptor(
    const ReleasePublishTargetDescriptor &descriptor,
    const std::filesystem::path &descriptorPath,
    PackageReleasePublishReceiptResult &result) {
  result.targetBucket.clear();
  result.targetPrefix.clear();
  result.targetCredentialsEnv.clear();
  if (!descriptor.targetPath || descriptor.targetPath->empty()) {
    result.diagnostics.push_back(releasePublishError(
        "invalid-target-descriptor",
        "package release publish local target descriptor requires non-empty "
        "targetPath",
        descriptorPath));
  }
  if (descriptor.bucket || descriptor.prefix || descriptor.credentialsEnv) {
    result.diagnostics.push_back(releasePublishError(
        "invalid-target-descriptor",
        "package release publish local target descriptor must not contain "
        "cloud fields",
        descriptorPath));
  }
  if (descriptor.targetPath && !descriptor.targetPath->empty()) {
    const std::filesystem::path descriptorTargetPath{*descriptor.targetPath};
    if (result.targetPath.empty()) {
      result.targetPath = descriptorTargetPath;
    } else if (result.targetPath.lexically_normal() !=
               descriptorTargetPath.lexically_normal()) {
      result.diagnostics.push_back(releasePublishError(
          "target-descriptor-mismatch",
          "package release publish target descriptor path does not match "
          "--target-output",
          descriptorPath));
    }
  }
}

void applyGcsReleasePublishTargetDescriptor(
    const ReleasePublishTargetDescriptor &descriptor,
    const std::filesystem::path &descriptorPath,
    PackageReleasePublishReceiptResult &result) {
  result.targetPath.clear();
  result.targetBucket.clear();
  result.targetPrefix.clear();
  result.targetCredentialsEnv.clear();
  if (descriptor.targetPath) {
    result.diagnostics.push_back(releasePublishError(
        "invalid-target-descriptor",
        "package release publish gcs target descriptor must not contain "
        "targetPath",
        descriptorPath));
  }
  if (!descriptor.bucket || descriptor.bucket->empty()) {
    result.diagnostics.push_back(releasePublishError(
        "invalid-target-descriptor",
        "package release publish gcs target descriptor requires bucket",
        descriptorPath));
  } else if (!isReleasePublishGcsBucketName(*descriptor.bucket)) {
    result.diagnostics.push_back(releasePublishError(
        "invalid-target-descriptor",
        "package release publish gcs target descriptor bucket is invalid",
        descriptorPath));
  }

  const std::string prefix = descriptor.prefix.value_or("");
  if (!descriptor.prefix || prefix.empty()) {
    result.diagnostics.push_back(releasePublishError(
        "invalid-target-descriptor",
        "package release publish gcs target descriptor requires a "
        "release-scoped prefix",
        descriptorPath));
  } else if (!prefix.empty() && !isReleasePublishRelativePath(prefix)) {
    result.diagnostics.push_back(releasePublishError(
        "invalid-target-descriptor",
        "package release publish gcs target descriptor prefix must be a "
        "normalized relative path",
        descriptorPath));
  }

  if (!descriptor.credentialsEnv || descriptor.credentialsEnv->empty()) {
    result.diagnostics.push_back(releasePublishError(
        "invalid-target-descriptor",
        "package release publish gcs target descriptor requires "
        "credentialsEnv",
        descriptorPath));
  }

  if (descriptor.bucket && isReleasePublishGcsBucketName(*descriptor.bucket) &&
      descriptor.prefix && !prefix.empty() &&
      isReleasePublishRelativePath(prefix) && descriptor.credentialsEnv &&
      !descriptor.credentialsEnv->empty()) {
    result.targetBucket = *descriptor.bucket;
    result.targetPrefix = prefix;
    result.targetCredentialsEnv = *descriptor.credentialsEnv;
    result.targetUri = releasePublishGcsUri(*descriptor.bucket, prefix);
  }
}

void applyReleasePublishTargetDescriptor(
    const ReleasePublishTargetBackend *backend,
    const ReleasePublishTargetDescriptor &descriptor,
    const std::filesystem::path &descriptorPath,
    PackageReleasePublishReceiptResult &result) {
  if (descriptor.targetKind != result.targetKind) {
    result.diagnostics.push_back(releasePublishError(
        "target-descriptor-mismatch",
        "package release publish target descriptor kind does not match "
        "--publish-target: " +
            descriptor.targetKind,
        descriptorPath));
    return;
  }

  result.targetEnabled = descriptor.enabled;
  if (!backend) {
    return;
  }
  if (backend->applyDescriptor) {
    backend->applyDescriptor(descriptor, descriptorPath, result);
  }
}

void resolveLocalReleasePublishTarget(
    const ReleasePublishTargetBackend &,
    const PackageReleasePublishOptions &options,
    PackageReleasePublishReceiptResult &result) {
  result.targetEnabled = result.targetEnabled || !options.targetDescriptorPath;
  if (result.targetPath.empty()) {
    result.diagnostics.push_back(releasePublishError(
        "invalid-target-output",
        "package release publish target output path must be non-empty",
        result.targetPath));
  } else if (looksLikeCloudReleasePublishTarget(result.targetPath)) {
    result.diagnostics.push_back(releasePublishError(
        "unsupported-target",
        "package release publish local target output must be a filesystem "
        "path",
        result.targetPath));
  } else {
    result.targetUri = normalizedReleasePublishPathString(result.targetPath);
  }
  if (options.targetDescriptorPath && !result.targetEnabled && !result.dryRun) {
    result.diagnostics.push_back(releasePublishError(
        "target-disabled",
        "package release publish target descriptor is disabled; use "
        "--dry-run or set enabled=true for local publishing",
        result.targetDescriptorPath));
  }
}

void resolvePlanOnlyReleasePublishTarget(
    const ReleasePublishTargetBackend &backend,
    const PackageReleasePublishOptions &options,
    PackageReleasePublishReceiptResult &result) {
  const bool requestedDryRun = result.dryRun;
  if (backend.descriptorRequired && !options.targetDescriptorPath) {
    result.diagnostics.push_back(
        releasePublishError("target-descriptor-required",
                            "package release publish " + result.targetKind +
                                " targets require --target-descriptor",
                            result.targetPath));
  }
  if (backend.dryRunRequired && !requestedDryRun) {
    result.diagnostics.push_back(releasePublishError(
        "dry-run-required",
        "package release publish " + result.targetKind +
            " targets are validation-only and require --dry-run",
        result.targetDescriptorPath));
  }
  if (backend.dryRunRequired) {
    result.dryRun = true;
  }
  if (backend.disabledDescriptorRequired && result.targetEnabled) {
    result.diagnostics.push_back(releasePublishError(
        "target-disabled-required",
        "package release publish " + result.targetKind +
            " target descriptors must set enabled=false until upload support "
            "is implemented",
        result.targetDescriptorPath));
  }
  if (backend.uriTarget && !options.targetDescriptorPath) {
    result.targetUri.clear();
  }
}

void resolveReleasePublishTarget(const PackageReleasePublishOptions &options,
                                 PackageReleasePublishReceiptResult &result) {
  result.dryRun = options.dryRun;
  result.targetKind = options.targetKind;
  result.targetPath = options.targetPath;
  result.targetDescriptorPath =
      options.targetDescriptorPath.value_or(std::filesystem::path{});
  result.receiptPath = options.receiptPath.value_or(std::filesystem::path{});
  const ReleasePublishTargetBackend *backend =
      findReleasePublishTargetBackend(result.targetKind);
  result.targetEnabled = backend && backend->defaultEnabled;

  if (options.targetDescriptorPath) {
    const std::optional<std::string> descriptorText =
        readReleasePublishTargetDescriptorFile(*options.targetDescriptorPath,
                                               result.diagnostics);
    if (descriptorText) {
      const std::optional<ReleasePublishTargetDescriptor> descriptor =
          parseReleasePublishTargetDescriptor(*descriptorText,
                                              *options.targetDescriptorPath,
                                              result.diagnostics);
      if (descriptor) {
        applyReleasePublishTargetDescriptor(
            backend, *descriptor, *options.targetDescriptorPath, result);
      }
    }
  }

  if (!backend) {
    result.diagnostics.push_back(releasePublishError(
        "unsupported-target",
        "package release publish target is not enabled: " + result.targetKind,
        result.targetPath));
    return;
  }

  if (backend->resolveOptions) {
    backend->resolveOptions(*backend, options, result);
  }
}

std::string localReleasePublishPublishedPath(
    const PackageReleasePublishReceiptResult &result,
    std::string_view destinationPath) {
  return joinReleasePublishLocalPath(result.targetPath, destinationPath);
}

std::string
uriReleasePublishPublishedPath(const PackageReleasePublishReceiptResult &result,
                               std::string_view destinationPath) {
  return joinReleasePublishUri(result.targetUri, destinationPath);
}

std::string releasePublishArtifactTargetPath(
    const ReleasePublishTargetBackend *backend,
    const PackageReleasePublishReceiptResult &result,
    std::string_view destinationPath) {
  if (backend && backend->publishedPath) {
    return backend->publishedPath(result, destinationPath);
  }
  return localReleasePublishPublishedPath(result, destinationPath);
}

void validateLocalReleasePublishStageTarget(
    const PackageReleasePublishStageParsedDocument &document,
    PackageReleasePublishReceiptResult &result) {
  if (!result.targetPath.empty() && result.targetPath.lexically_normal() ==
                                        document.stagePath.lexically_normal()) {
    result.diagnostics.push_back(releasePublishError(
        "invalid-target-output",
        "package release publish target output must differ from the stage "
        "directory",
        result.targetPath));
  }
}

void validatePlanOnlyReleasePublishStageTarget(
    const PackageReleasePublishStageParsedDocument &,
    PackageReleasePublishReceiptResult &) {}

std::optional<PackageReleasePublishUploadRequest>
buildNoopReleasePublishUploadRequest(
    const PackageReleasePublishReceiptResult &,
    const PackageReleasePublishReceiptArtifact &) {
  return std::nullopt;
}

std::optional<PackageReleasePublishUploadRequest>
buildGcsReleasePublishUploadRequest(
    const PackageReleasePublishReceiptResult &result,
    const PackageReleasePublishReceiptArtifact &published) {
  if (result.targetBucket.empty()) {
    return std::nullopt;
  }

  const PackageReleasePublishStageArtifact &staged = published.artifact;
  PackageReleasePublishUploadRequest request;
  request.targetKind = result.targetKind;
  request.stagedPath = staged.stagedPath;
  request.destinationPath = staged.artifact.destinationPath;
  request.bucket = result.targetBucket;
  request.objectName =
      releasePublishGcsObjectName(result.targetPrefix, request.destinationPath);
  request.uploadUri = published.publishedPath;
  request.credentialsEnv = result.targetCredentialsEnv;
  request.sizeBytes = staged.artifact.sizeBytes;
  request.sha256 = staged.artifact.sha256;
  return request;
}

void planReleasePublishReceiptArtifacts(
    const PackageReleasePublishStageParsedDocument &document,
    const ReleasePublishTargetBackend *backend,
    PackageReleasePublishReceiptResult &result) {
  result.packageCount = document.packageCount;
  result.artifactCount = document.artifactCount;
  result.totalArtifactBytes = document.totalArtifactBytes;
  for (const PackageReleasePublishStageArtifact &artifact :
       document.artifacts) {
    PackageReleasePublishReceiptArtifact published;
    published.artifact = artifact;
    published.publishedPath = releasePublishArtifactTargetPath(
        backend, result, artifact.artifact.destinationPath);
    result.artifacts.push_back(std::move(published));
  }

  if (backend && backend->validateStage) {
    backend->validateStage(document, result);
  }
}

void planReleasePublishUploadRequests(
    const ReleasePublishTargetBackend *backend,
    PackageReleasePublishReceiptResult &result) {
  result.uploadRequests.clear();
  if (!backend || !backend->buildUploadRequest) {
    return;
  }
  for (const PackageReleasePublishReceiptArtifact &published :
       result.artifacts) {
    if (!published.planned) {
      continue;
    }
    std::optional<PackageReleasePublishUploadRequest> request =
        backend->buildUploadRequest(result, published);
    if (request) {
      result.uploadRequests.push_back(std::move(*request));
    }
  }
}

void verifyReleasePublishStagedArtifacts(
    PackageReleasePublishReceiptResult &result) {
  for (PackageReleasePublishReceiptArtifact &published : result.artifacts) {
    const PackageReleasePublishStageArtifact &staged = published.artifact;
    std::error_code statusError;
    const bool stagedExists =
        std::filesystem::exists(staged.stagedPath, statusError);
    if (statusError || !stagedExists) {
      result.diagnostics.push_back(releasePublishError(
          "staged-artifact-missing",
          "package release publish staged artifact does not exist: " +
              staged.stagedPath.string(),
          staged.stagedPath));
      continue;
    }
    if (!std::filesystem::is_regular_file(staged.stagedPath, statusError) ||
        statusError) {
      result.diagnostics.push_back(releasePublishError(
          "staged-artifact-not-file",
          "package release publish staged artifact is not a regular file: " +
              staged.stagedPath.string(),
          staged.stagedPath));
      continue;
    }

    const std::uintmax_t actualSize =
        std::filesystem::file_size(staged.stagedPath, statusError);
    if (statusError || actualSize != staged.artifact.sizeBytes) {
      result.diagnostics.push_back(releasePublishError(
          "staged-size-mismatch",
          "package release publish staged artifact size does not match "
          "report: " +
              staged.stagedPath.string(),
          staged.stagedPath));
      continue;
    }
    const std::optional<std::string> contents =
        readReleasePublishArtifactFile(staged.stagedPath, result.diagnostics,
                                       "staged-read-failed", "staged artifact");
    if (!contents) {
      continue;
    }
    if (sha256(*contents) != staged.artifact.sha256) {
      result.diagnostics.push_back(releasePublishError(
          "staged-hash-mismatch",
          "package release publish staged artifact sha256 does not match "
          "report: " +
              staged.stagedPath.string(),
          staged.stagedPath));
      continue;
    }
    published.planned = true;
    ++result.plannedArtifactCount;
    result.plannedArtifactBytes += staged.artifact.sizeBytes;
  }
}

bool finalizeReleasePublishDryRun(PackageReleasePublishReceiptResult &result) {
  if (result.dryRun) {
    result.success =
        result.plannedArtifactCount == result.artifactCount &&
        countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
    return true;
  }
  return false;
}

bool applyLocalReleasePublish(PackageReleasePublishReceiptResult &result) {
  std::error_code statusError;
  if (std::filesystem::exists(result.targetPath, statusError) && !statusError &&
      !std::filesystem::is_directory(result.targetPath, statusError)) {
    result.diagnostics.push_back(releasePublishError(
        "target-not-directory",
        "package release publish target output path is not a directory: " +
            result.targetPath.string(),
        result.targetPath));
    return false;
  }
  std::filesystem::create_directories(result.targetPath, statusError);
  if (statusError) {
    result.diagnostics.push_back(releasePublishError(
        "target-create-failed",
        "failed to create package release publish target output: " +
            result.targetPath.string(),
        result.targetPath));
    return false;
  }

  for (PackageReleasePublishReceiptArtifact &published : result.artifacts) {
    const PackageReleasePublishStageArtifact &staged = published.artifact;
    const std::filesystem::path publishedPath{published.publishedPath};
    const std::filesystem::path parent = publishedPath.parent_path();
    if (!parent.empty()) {
      std::filesystem::create_directories(parent, statusError);
      if (statusError) {
        result.diagnostics.push_back(releasePublishError(
            "target-create-failed",
            "failed to create package release publish target directory: " +
                parent.string(),
            parent));
        continue;
      }
    }

    if (std::filesystem::exists(publishedPath, statusError) && !statusError) {
      result.diagnostics.push_back(releasePublishError(
          "destination-exists",
          "package release publish destination already exists: " +
              publishedPath.string(),
          publishedPath));
      continue;
    }
    if (statusError) {
      result.diagnostics.push_back(releasePublishError(
          "publish-stat-failed",
          "failed to inspect package release publish destination: " +
              publishedPath.string(),
          publishedPath));
      continue;
    }

    std::filesystem::copy_file(staged.stagedPath, publishedPath,
                               std::filesystem::copy_options::none,
                               statusError);
    if (statusError) {
      result.diagnostics.push_back(releasePublishError(
          "publish-copy-failed",
          "failed to copy package release publish artifact: " +
              publishedPath.string(),
          publishedPath));
      continue;
    }

    const std::uintmax_t publishedSize =
        std::filesystem::file_size(publishedPath, statusError);
    if (statusError || publishedSize != staged.artifact.sizeBytes) {
      result.diagnostics.push_back(releasePublishError(
          "publish-size-mismatch",
          "package release publish artifact size does not match report: " +
              publishedPath.string(),
          publishedPath));
      continue;
    }
    const std::optional<std::string> publishedContents =
        readReleasePublishArtifactFile(publishedPath, result.diagnostics,
                                       "publish-read-failed",
                                       "published artifact");
    if (!publishedContents) {
      continue;
    }
    if (sha256(*publishedContents) != staged.artifact.sha256) {
      result.diagnostics.push_back(releasePublishError(
          "publish-hash-mismatch",
          "package release publish artifact sha256 does not match report: " +
              publishedPath.string(),
          publishedPath));
      continue;
    }

    published.published = true;
    ++result.publishedArtifactCount;
    result.publishedArtifactBytes += staged.artifact.sizeBytes;
  }

  result.success =
      result.publishedArtifactCount == result.artifactCount &&
      countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
  return true;
}

bool applyPlanOnlyReleasePublishTarget(
    PackageReleasePublishReceiptResult &result) {
  result.diagnostics.push_back(releasePublishError(
      "unsupported-target",
      "package release publish target requires --dry-run until upload support "
      "is implemented: " +
          result.targetKind,
      result.targetDescriptorPath));
  result.success = false;
  return true;
}

bool applyReleasePublishTarget(const ReleasePublishTargetBackend *backend,
                               PackageReleasePublishReceiptResult &result) {
  if (!backend) {
    result.success = false;
    return true;
  }
  if (!backend->apply) {
    result.success = false;
    return true;
  }
  return backend->apply(result);
}

void writeReleasePublishReceiptIfRequested(
    const PackageReleasePublishOptions &options,
    PackageReleasePublishReceiptResult &result) {
  if (!options.receiptPath) {
    return;
  }

  std::ofstream output(*options.receiptPath,
                       std::ios::binary | std::ios::trunc);
  if (!output) {
    result.success = false;
    result.diagnostics.push_back(releasePublishError(
        "receipt-write-failed",
        "failed to write package release publish receipt: " +
            options.receiptPath->string(),
        *options.receiptPath));
    return;
  }
  result.receiptWritten = true;
  output << packageReleasePublishReceiptJson(result);
  if (!output) {
    result.receiptWritten = false;
    result.success = false;
    result.diagnostics.push_back(releasePublishError(
        "receipt-write-failed",
        "failed to write package release publish receipt: " +
            options.receiptPath->string(),
        *options.receiptPath));
  }
}

void writeReleasePublishUploadManifestIfRequested(
    const PackageReleasePublishOptions &options,
    PackageReleasePublishReceiptResult &result) {
  if (!options.uploadManifestPath) {
    return;
  }

  std::ofstream output(*options.uploadManifestPath,
                       std::ios::binary | std::ios::trunc);
  if (!output) {
    result.success = false;
    result.diagnostics.push_back(releasePublishError(
        "upload-manifest-write-failed",
        "failed to write package release publish upload manifest: " +
            options.uploadManifestPath->string(),
        *options.uploadManifestPath));
    return;
  }
  output << packageReleasePublishUploadManifestJson(result.uploadRequests);
  if (!output) {
    result.success = false;
    result.diagnostics.push_back(releasePublishError(
        "upload-manifest-write-failed",
        "failed to write package release publish upload manifest: " +
            options.uploadManifestPath->string(),
        *options.uploadManifestPath));
  }
}

PackageReleasePublishReceiptResult
publishPackageReleaseStage(const std::filesystem::path &stageReportPath,
                           const PackageReleasePublishOptions &options) {
  DiagnosticEngine diagnostics;
  PackageReleasePublishReceiptResult result;
  result.stageReportPath = stageReportPath;
  resolveReleasePublishTarget(options, result);

  const std::optional<std::string> text =
      readReleasePublishStageReportFile(stageReportPath, diagnostics);
  if (!text) {
    appendDiagnostics(result.diagnostics, diagnostics.diagnostics());
    return result;
  }
  const std::optional<PackageReleasePublishStageParsedDocument> document =
      parseReleasePublishStageDocument(*text, stageReportPath, diagnostics);
  appendDiagnostics(result.diagnostics, diagnostics.diagnostics());
  if (!document) {
    return result;
  }

  const ReleasePublishTargetBackend *backend =
      findReleasePublishTargetBackend(result.targetKind);
  planReleasePublishReceiptArtifacts(*document, backend, result);
  if (countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) != 0) {
    return result;
  }

  verifyReleasePublishStagedArtifacts(result);
  if (countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) != 0) {
    return result;
  }
  planReleasePublishUploadRequests(backend, result);

  if (!finalizeReleasePublishDryRun(result) &&
      !applyReleasePublishTarget(backend, result)) {
    return result;
  }

  writeReleasePublishUploadManifestIfRequested(options, result);
  writeReleasePublishReceiptIfRequested(options, result);

  return result;
}

bool validatePackageReleasePublishUploadRequest(
    const PackageReleasePublishUploadRequest &request,
    std::vector<Diagnostic> &diagnostics) {
  const std::size_t initialErrorCount =
      countDiagnostics(diagnostics, DiagnosticSeverity::Error);
  const std::filesystem::path diagnosticPath =
      request.stagedPath.empty() ? std::filesystem::path{} : request.stagedPath;

  if (request.targetKind.empty() || request.destinationPath.empty() ||
      request.uploadUri.empty()) {
    diagnostics.push_back(releasePublishError(
        "invalid-upload-request",
        "package release publish upload request requires targetKind, "
        "destinationPath, and uploadUri",
        diagnosticPath));
  }
  if (request.targetKind == "gcs" &&
      (request.bucket.empty() || request.objectName.empty())) {
    diagnostics.push_back(releasePublishError(
        "invalid-upload-request",
        "package release publish gcs upload request requires bucket and "
        "objectName",
        diagnosticPath));
  }
  if (request.targetKind == "gcs" && !request.destinationPath.empty() &&
      !request.objectName.empty()) {
    if (request.objectName == request.destinationPath) {
      diagnostics.push_back(releasePublishError(
          "invalid-upload-request",
          "package release publish upload request objectName must include a "
          "non-root object prefix",
          diagnosticPath));
    } else if (!releasePublishObjectNameEndsWithDestination(
                   request.objectName, request.destinationPath)) {
      diagnostics.push_back(releasePublishError(
          "invalid-upload-request",
          "package release publish upload request objectName must end with "
          "destinationPath",
          diagnosticPath));
    }
  }
  if (request.stagedPath.empty()) {
    diagnostics.push_back(releasePublishError(
        "invalid-upload-request",
        "package release publish upload request requires stagedPath",
        diagnosticPath));
  }

  std::error_code statusError;
  const bool sourceExists =
      std::filesystem::exists(request.stagedPath, statusError);
  if (statusError || !sourceExists) {
    diagnostics.push_back(releasePublishError(
        "upload-source-missing",
        "package release publish upload source does not exist: " +
            request.stagedPath.string(),
        request.stagedPath));
    return false;
  }
  if (!std::filesystem::is_regular_file(request.stagedPath, statusError) ||
      statusError) {
    diagnostics.push_back(releasePublishError(
        "upload-source-not-file",
        "package release publish upload source is not a regular file: " +
            request.stagedPath.string(),
        request.stagedPath));
    return false;
  }

  const std::uintmax_t actualSize =
      std::filesystem::file_size(request.stagedPath, statusError);
  if (statusError || actualSize != request.sizeBytes) {
    diagnostics.push_back(releasePublishError(
        "upload-size-mismatch",
        "package release publish upload source size does not match request: " +
            request.stagedPath.string(),
        request.stagedPath));
    return false;
  }

  const std::optional<std::string> contents = readReleasePublishArtifactFile(
      request.stagedPath, diagnostics, "upload-read-failed", "upload source");
  if (!contents) {
    return false;
  }
  if (sha256(*contents) != request.sha256) {
    diagnostics.push_back(
        releasePublishError("upload-hash-mismatch",
                            "package release publish upload source sha256 does "
                            "not match request: " +
                                request.stagedPath.string(),
                            request.stagedPath));
  }

  return countDiagnostics(diagnostics, DiagnosticSeverity::Error) ==
         initialErrorCount;
}

PackageReleasePublishUploadAttempt
PackageReleasePublishUploader::uploadPackageReleaseArtifactDetailed(
    const PackageReleasePublishUploadRequest &request) {
  PackageReleasePublishUploadAttempt attempt;
  attempt.request = request;
  std::string errorMessage;
  if (uploadPackageReleaseArtifact(request, errorMessage)) {
    attempt.status = PackageReleasePublishUploadAttemptStatus::Uploaded;
  } else {
    attempt.status = PackageReleasePublishUploadAttemptStatus::Failed;
    attempt.errorMessage = std::move(errorMessage);
  }
  return attempt;
}

PackageReleasePublishUploadBatchResult uploadPackageReleaseArtifacts(
    const std::vector<PackageReleasePublishUploadRequest> &requests,
    PackageReleasePublishUploader &uploader) {
  PackageReleasePublishUploadBatchResult result;
  result.requestCount = requests.size();
  for (const PackageReleasePublishUploadRequest &request : requests) {
    result.requestBytes += request.sizeBytes;
    if (!validatePackageReleasePublishUploadRequest(request,
                                                    result.diagnostics)) {
      continue;
    }

    PackageReleasePublishUploadAttempt attempt =
        uploader.uploadPackageReleaseArtifactDetailed(request);
    attempt.request = request;
    result.attempts.push_back(std::move(attempt));
    const PackageReleasePublishUploadAttempt &recordedAttempt =
        result.attempts.back();
    if (recordedAttempt.status ==
        PackageReleasePublishUploadAttemptStatus::Failed) {
      std::string errorMessage = recordedAttempt.errorMessage.empty()
                                     ? "package release publish upload failed: " +
                                           request.uploadUri
                                     : recordedAttempt.errorMessage;
      result.diagnostics.push_back(releasePublishError(
          "upload-failed", std::move(errorMessage), request.stagedPath));
      continue;
    }

    ++result.uploadedArtifactCount;
    result.uploadedArtifactBytes += request.sizeBytes;
    result.uploadedRequests.push_back(request);
  }
  result.success =
      result.uploadedArtifactCount == result.requestCount &&
      countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
  return result;
}

void writeReleasePublishUploadReceiptIfRequested(
    const PackageReleasePublishUploadBatchOptions &options,
    PackageReleasePublishUploadBatchResult &result) {
  if (!options.receiptPath) {
    return;
  }

  std::ofstream output(*options.receiptPath,
                       std::ios::binary | std::ios::trunc);
  if (!output) {
    result.success = false;
    result.diagnostics.push_back(releasePublishError(
        "upload-receipt-write-failed",
        "failed to write package release publish upload receipt: " +
            options.receiptPath->string(),
        *options.receiptPath));
    return;
  }
  result.receiptWritten = true;
  output << packageReleasePublishUploadReceiptJson(result);
  if (!output) {
    result.receiptWritten = false;
    result.success = false;
    result.diagnostics.push_back(releasePublishError(
        "upload-receipt-write-failed",
        "failed to write package release publish upload receipt: " +
            options.receiptPath->string(),
        *options.receiptPath));
  }
}

void writeReleasePublishUploadBatchReportIfRequested(
    const PackageReleasePublishUploadBatchOptions &options,
    PackageReleasePublishUploadBatchResult &result) {
  if (!options.reportPath) {
    return;
  }

  std::ofstream output(*options.reportPath, std::ios::binary | std::ios::trunc);
  if (!output) {
    result.success = false;
    result.diagnostics.push_back(releasePublishError(
        "upload-batch-report-write-failed",
        "failed to write package release publish upload batch report: " +
            options.reportPath->string(),
        *options.reportPath));
    return;
  }
  result.reportWritten = true;
  output << packageReleasePublishUploadBatchJson(result);
  if (!output) {
    result.reportWritten = false;
    result.success = false;
    result.diagnostics.push_back(releasePublishError(
        "upload-batch-report-write-failed",
        "failed to write package release publish upload batch report: " +
            options.reportPath->string(),
        *options.reportPath));
  }
}

PackageReleasePublishUploadBatchResult uploadPackageReleaseManifest(
    const std::filesystem::path &manifestPath,
    const PackageReleasePublishUploadBatchOptions &options,
    PackageReleasePublishUploader &uploader) {
  DiagnosticEngine diagnostics;
  PackageReleasePublishUploadBatchResult result;
  result.manifestPath = manifestPath;
  result.reportPath = options.reportPath.value_or(std::filesystem::path{});
  result.receiptPath = options.receiptPath.value_or(std::filesystem::path{});
  result.uploadMode =
      options.uploadMode.empty() ? "custom" : options.uploadMode;

  const std::optional<std::string> text =
      readReleasePublishUploadManifestFile(manifestPath, diagnostics);
  if (text) {
    const std::optional<PackageReleasePublishUploadManifestParsedDocument>
        document = parseReleasePublishUploadManifestDocument(
            *text, manifestPath, diagnostics);
    appendDiagnostics(result.diagnostics, diagnostics.diagnostics());
    if (document) {
      result.requestCount = document->requestCount;
      result.requestBytes = document->requestBytes;
      if (countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) ==
          0) {
        PackageReleasePublishUploadBatchResult batch =
            uploadPackageReleaseArtifacts(document->requests, uploader);
        result.requestCount = batch.requestCount;
        result.requestBytes = batch.requestBytes;
        result.uploadedArtifactCount = batch.uploadedArtifactCount;
        result.uploadedArtifactBytes = batch.uploadedArtifactBytes;
        result.attempts = std::move(batch.attempts);
        result.uploadedRequests = std::move(batch.uploadedRequests);
        appendDiagnostics(result.diagnostics, batch.diagnostics);
        result.success = result.uploadedArtifactCount == result.requestCount &&
                         countDiagnostics(result.diagnostics,
                                          DiagnosticSeverity::Error) == 0;
      }
    }
  } else {
    appendDiagnostics(result.diagnostics, diagnostics.diagnostics());
  }

  writeReleasePublishUploadReceiptIfRequested(options, result);
  writeReleasePublishUploadBatchReportIfRequested(options, result);
  return result;
}

void writeReleasePublishUploadPreflightReportIfRequested(
    const PackageReleasePublishUploadPreflightOptions &options,
    PackageReleasePublishUploadPreflightResult &result) {
  if (!options.reportPath) {
    return;
  }

  std::ofstream output(*options.reportPath, std::ios::binary | std::ios::trunc);
  if (!output) {
    result.success = false;
    result.diagnostics.push_back(releasePublishError(
        "upload-preflight-report-write-failed",
        "failed to write package release publish upload preflight report: " +
            options.reportPath->string(),
        *options.reportPath));
    return;
  }
  result.reportWritten = true;
  output << packageReleasePublishUploadPreflightJson(result);
  if (!output) {
    result.reportWritten = false;
    result.success = false;
    result.diagnostics.push_back(releasePublishError(
        "upload-preflight-report-write-failed",
        "failed to write package release publish upload preflight report: " +
            options.reportPath->string(),
        *options.reportPath));
  }
}

PackageReleasePublishUploadPreflightResult
preflightPackageReleaseUploadManifest(
    const std::filesystem::path &manifestPath,
    const PackageReleasePublishUploadPreflightOptions &options) {
  DiagnosticEngine diagnostics;
  PackageReleasePublishUploadPreflightResult result;
  result.manifestPath = manifestPath;
  result.reportPath = options.reportPath.value_or(std::filesystem::path{});

  const std::optional<std::string> text =
      readReleasePublishUploadManifestFile(manifestPath, diagnostics);
  if (text) {
    const std::optional<PackageReleasePublishUploadManifestParsedDocument>
        document = parseReleasePublishUploadManifestDocument(
            *text, manifestPath, diagnostics);
    appendDiagnostics(result.diagnostics, diagnostics.diagnostics());
    if (document) {
      result.requestCount = document->requestCount;
      result.requestBytes = document->requestBytes;
      if (countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) ==
          0) {
        for (const PackageReleasePublishUploadRequest &request :
             document->requests) {
          if (!validatePackageReleasePublishUploadRequest(request,
                                                          result.diagnostics)) {
            continue;
          }
          ++result.validatedRequestCount;
          result.validatedRequestBytes += request.sizeBytes;
          result.validatedRequests.push_back(request);
        }
      }
    }
  } else {
    appendDiagnostics(result.diagnostics, diagnostics.diagnostics());
  }

  result.success =
      result.validatedRequestCount == result.requestCount &&
      countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
  writeReleasePublishUploadPreflightReportIfRequested(options, result);
  return result;
}

PackageMaintenanceSetVerificationResult
verifyPackageMaintenanceSetFromScan(const std::filesystem::path &rootPath,
                                    const std::filesystem::path &setPath) {
  DiagnosticEngine diagnostics;
  PackageMaintenanceSetVerificationResult result;
  result.rootPath = rootPath;
  result.setPath = setPath;
  result.scannedPackagePaths =
      discoverMaintenancePackageRoots(rootPath, diagnostics);

  const PackageMaintenanceSetLoadResult packageSet =
      loadPackageMaintenanceSet(setPath);
  result.setPackagePaths = packageSet.packagePaths;
  result.diagnostics = diagnostics.diagnostics();
  result.diagnostics.insert(result.diagnostics.end(),
                            packageSet.diagnostics.begin(),
                            packageSet.diagnostics.end());
  if (countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) != 0) {
    return result;
  }

  result.missingFromSet = packagePathSetDifference(result.scannedPackagePaths,
                                                   result.setPackagePaths);
  result.extraInSet = packagePathSetDifference(result.setPackagePaths,
                                               result.scannedPackagePaths);
  result.matches = result.missingFromSet.empty() && result.extraInSet.empty();
  if (!result.matches) {
    Diagnostic mismatch;
    mismatch.severity = DiagnosticSeverity::Error;
    mismatch.code = maintenanceSetVerificationDiagnosticCode("mismatch");
    mismatch.message = "package maintenance set does not match scan discovery";
    mismatch.location = pathLocation(setPath);
    result.diagnostics.push_back(std::move(mismatch));
  }

  result.success =
      result.matches &&
      countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
  return result;
}

PackageMaintenanceSetVerificationBatchResult
verifyPackageMaintenanceSetsFromBatch(const std::filesystem::path &batchPath) {
  PackageMaintenanceSetVerificationBatchResult result;
  result.batchPath = batchPath;

  const PackageMaintenanceSetVerificationBatchLoadResult batch =
      loadPackageMaintenanceSetVerificationBatch(batchPath);
  result.diagnostics = batch.diagnostics;
  if (!batch.success) {
    return result;
  }

  for (const PackageMaintenanceSetVerificationBatchEntry &entry :
       batch.entries) {
    result.verifications.push_back(
        verifyPackageMaintenanceSetFromScan(entry.rootPath, entry.setPath));
  }
  for (const PackageMaintenanceSetVerificationResult &verification :
       result.verifications) {
    result.diagnostics.insert(result.diagnostics.end(),
                              verification.diagnostics.begin(),
                              verification.diagnostics.end());
  }

  result.matches =
      !result.verifications.empty() &&
      countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
  result.success = result.matches;
  for (const PackageMaintenanceSetVerificationResult &verification :
       result.verifications) {
    if (!verification.matches) {
      result.matches = false;
    }
    if (!verification.success) {
      result.success = false;
    }
  }
  result.success =
      result.success &&
      countDiagnostics(result.diagnostics, DiagnosticSeverity::Error) == 0;
  result.matches = result.matches && result.success;
  return result;
}

std::string
packageStaleSidecarCleanupJson(const PackageStaleSidecarCleanupResult &result) {
  std::ostringstream out;
  writeStaleSidecarCleanupResult(out, result, "");
  out << "\n";
  return out.str();
}

std::string
packageStaleSidecarCleanupText(const PackageStaleSidecarCleanupResult &result) {
  std::ostringstream out;
  out << (result.dryRun ? "stale package sidecar dry run for "
                        : "discarded stale package sidecars for ")
      << result.publication.requestedPath.lexically_normal().generic_string()
      << "\n";
  if (result.keepLast) {
    out << "  keep-last=" << *result.keepLast << "\n";
  }
  if (result.olderThanSeconds) {
    out << "  older-than=" << *result.olderThanSeconds << "s\n";
  }
  if (result.candidates.empty() && result.retained.empty()) {
    out << "  no stale sidecars\n";
    return out.str();
  }
  for (const PackageStaleSidecarCleanupRecord &retained : result.retained) {
    out << "  kept "
        << retained.sidecar.path.lexically_normal().generic_string()
        << " reason=" << retained.reason;
    if (!retained.retainedBy.empty()) {
      out << " retained-by=" << retained.retainedBy;
    }
    out << "\n";
  }
  for (const PackageStaleSidecarCleanupRecord &candidate : result.candidates) {
    out << "  " << candidate.action << " "
        << candidate.sidecar.path.lexically_normal().generic_string()
        << " reason=" << candidate.reason << "\n";
  }
  return out.str();
}

std::string
packageMaintenanceScanJson(const PackageMaintenanceScanResult &result) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"rootPath\": \""
      << escapeJson(result.rootPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"dryRun\": " << (result.dryRun ? "true" : "false") << ",\n"
      << "  \"keepLast\": ";
  if (result.keepLast) {
    out << *result.keepLast;
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"olderThanSeconds\": ";
  if (result.olderThanSeconds) {
    out << *result.olderThanSeconds;
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"success\": " << (result.success ? "true" : "false") << ",\n"
      << "  \"packageCount\": " << result.packages.size() << ",\n"
      << "  \"retainedCount\": " << packageCleanupRetainedCount(result.packages)
      << ",\n"
      << "  \"candidateCount\": "
      << packageCleanupCandidateCount(result.packages) << ",\n"
      << "  \"discardedCount\": "
      << packageCleanupRecordActionCount(result.packages, "discarded") << ",\n"
      << "  \"failedCount\": "
      << packageCleanupRecordActionCount(result.packages, "failed") << ",\n"
      << "  \"packages\": [";
  for (std::size_t index = 0; index < result.packages.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeStaleSidecarCleanupResult(out, result.packages[index], "    ");
  }
  if (!result.packages.empty()) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, "  ");
  out << ",\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics);
  out << "\n}\n";
  return out.str();
}

std::string
packageMaintenanceScanText(const PackageMaintenanceScanResult &result) {
  std::ostringstream out;
  out << (result.dryRun ? "package maintenance scan dry run for "
                        : "package maintenance scan applied for ")
      << result.rootPath.lexically_normal().generic_string() << "\n"
      << "  packages=" << result.packages.size()
      << " retained=" << packageCleanupRetainedCount(result.packages)
      << " candidates=" << packageCleanupCandidateCount(result.packages)
      << " discarded="
      << packageCleanupRecordActionCount(result.packages, "discarded")
      << " failed="
      << packageCleanupRecordActionCount(result.packages, "failed") << "\n";
  if (result.keepLast) {
    out << "  keep-last=" << *result.keepLast << "\n";
  }
  if (result.olderThanSeconds) {
    out << "  older-than=" << *result.olderThanSeconds << "s\n";
  }
  if (result.packages.empty()) {
    out << "  no packages found\n";
    return out.str();
  }
  for (const PackageStaleSidecarCleanupResult &package : result.packages) {
    std::istringstream packageText(packageStaleSidecarCleanupText(package));
    std::string line;
    while (std::getline(packageText, line)) {
      out << "  " << line << "\n";
    }
  }
  return out.str();
}

std::string
packageMaintenanceSetJson(const PackageMaintenanceSetResult &result) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"setPath\": \""
      << escapeJson(result.setPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"dryRun\": " << (result.dryRun ? "true" : "false") << ",\n"
      << "  \"keepLast\": ";
  if (result.keepLast) {
    out << *result.keepLast;
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"olderThanSeconds\": ";
  if (result.olderThanSeconds) {
    out << *result.olderThanSeconds;
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"success\": " << (result.success ? "true" : "false") << ",\n"
      << "  \"packageCount\": " << result.packages.size() << ",\n"
      << "  \"retainedCount\": " << packageCleanupRetainedCount(result.packages)
      << ",\n"
      << "  \"candidateCount\": "
      << packageCleanupCandidateCount(result.packages) << ",\n"
      << "  \"discardedCount\": "
      << packageCleanupRecordActionCount(result.packages, "discarded") << ",\n"
      << "  \"failedCount\": "
      << packageCleanupRecordActionCount(result.packages, "failed") << ",\n"
      << "  \"packages\": [";
  for (std::size_t index = 0; index < result.packages.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeStaleSidecarCleanupResult(out, result.packages[index], "    ");
  }
  if (!result.packages.empty()) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, "  ");
  out << ",\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics);
  out << "\n}\n";
  return out.str();
}

std::string
packageMaintenanceSetText(const PackageMaintenanceSetResult &result) {
  std::ostringstream out;
  out << (result.dryRun ? "package maintenance set dry run for "
                        : "package maintenance set applied for ")
      << result.setPath.lexically_normal().generic_string() << "\n"
      << "  packages=" << result.packages.size()
      << " retained=" << packageCleanupRetainedCount(result.packages)
      << " candidates=" << packageCleanupCandidateCount(result.packages)
      << " discarded="
      << packageCleanupRecordActionCount(result.packages, "discarded")
      << " failed="
      << packageCleanupRecordActionCount(result.packages, "failed") << "\n";
  if (result.keepLast) {
    out << "  keep-last=" << *result.keepLast << "\n";
  }
  if (result.olderThanSeconds) {
    out << "  older-than=" << *result.olderThanSeconds << "s\n";
  }
  if (result.packages.empty()) {
    out << "  no packages found\n";
    return out.str();
  }
  for (const PackageStaleSidecarCleanupResult &package : result.packages) {
    std::istringstream packageText(packageStaleSidecarCleanupText(package));
    std::string line;
    while (std::getline(packageText, line)) {
      out << "  " << line << "\n";
    }
  }
  return out.str();
}

std::string packageMaintenanceSetDocumentJson(
    const std::vector<std::filesystem::path> &packagePaths,
    const std::filesystem::path &basePath) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"packages\": [";
  for (std::size_t index = 0; index < packagePaths.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    const std::filesystem::path documentPath =
        packageSetDocumentPath(packagePaths[index], basePath);
    out << "    \""
        << escapeJson(documentPath.lexically_normal().generic_string()) << "\"";
  }
  if (!packagePaths.empty()) {
    out << "\n  ";
  }
  out << "]\n"
      << "}\n";
  return out.str();
}

std::string packageMaintenanceSetVerificationBatchDocumentJson(
    const std::vector<PackageMaintenanceSetVerificationBatchEntry> &entries,
    const std::filesystem::path &basePath) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"verifications\": [";
  for (std::size_t index = 0; index < entries.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    const std::filesystem::path rootPath =
        packageSetDocumentPath(entries[index].rootPath, basePath);
    const std::filesystem::path setPath =
        packageSetDocumentPath(entries[index].setPath, basePath);
    out << "    {\n"
        << "      \"rootPath\": \""
        << escapeJson(rootPath.lexically_normal().generic_string()) << "\",\n"
        << "      \"setPath\": \""
        << escapeJson(setPath.lexically_normal().generic_string()) << "\"\n"
        << "    }";
  }
  if (!entries.empty()) {
    out << "\n  ";
  }
  out << "]\n"
      << "}\n";
  return out.str();
}

std::string packageMaintenanceSetExportText(
    const PackageMaintenanceSetExportResult &result) {
  std::ostringstream out;
  out << "exported package maintenance set "
      << result.setPath.lexically_normal().generic_string() << "\n"
      << "  root=" << result.rootPath.lexically_normal().generic_string()
      << "\n"
      << "  packages=" << result.packagePaths.size() << "\n";
  for (const std::filesystem::path &packagePath : result.packagePaths) {
    out << "  "
        << packageSetDocumentPath(packagePath,
                                  packageParentPath(result.setPath))
               .lexically_normal()
               .generic_string()
        << "\n";
  }
  return out.str();
}

std::string packageMaintenanceSetVerificationBatchExportText(
    const PackageMaintenanceSetVerificationBatchExportResult &result) {
  std::ostringstream out;
  out << "exported package maintenance set verification batch "
      << result.batchPath.lexically_normal().generic_string() << "\n"
      << "  verifications=" << result.entries.size() << "\n";
  for (const PackageMaintenanceSetVerificationBatchEntry &entry :
       result.entries) {
    out << "  root="
        << packageSetDocumentPath(entry.rootPath,
                                  packageParentPath(result.batchPath))
               .lexically_normal()
               .generic_string()
        << " set="
        << packageSetDocumentPath(entry.setPath,
                                  packageParentPath(result.batchPath))
               .lexically_normal()
               .generic_string()
        << "\n";
  }
  return out.str();
}

void writePackageMaintenanceSetVerificationResult(
    std::ostream &out, const PackageMaintenanceSetVerificationResult &result,
    std::string_view indent) {
  const std::string childIndent = std::string(indent) + "  ";
  out << indent << "{\n"
      << childIndent << "\"schemaVersion\": 1,\n"
      << childIndent << "\"rootPath\": \""
      << escapeJson(result.rootPath.lexically_normal().generic_string())
      << "\",\n"
      << childIndent << "\"setPath\": \""
      << escapeJson(result.setPath.lexically_normal().generic_string())
      << "\",\n"
      << childIndent << "\"success\": " << (result.success ? "true" : "false")
      << ",\n"
      << childIndent << "\"matches\": " << (result.matches ? "true" : "false")
      << ",\n"
      << childIndent
      << "\"scannedPackageCount\": " << result.scannedPackagePaths.size()
      << ",\n"
      << childIndent << "\"setPackageCount\": " << result.setPackagePaths.size()
      << ",\n"
      << childIndent
      << "\"missingFromSetCount\": " << result.missingFromSet.size() << ",\n"
      << childIndent << "\"extraInSetCount\": " << result.extraInSet.size()
      << ",\n"
      << childIndent << "\"scannedPackages\": ";
  writePathArray(out, result.scannedPackagePaths, childIndent);
  out << ",\n" << childIndent << "\"setPackages\": ";
  writePathArray(out, result.setPackagePaths, childIndent);
  out << ",\n" << childIndent << "\"missingFromSet\": ";
  writePathArray(out, result.missingFromSet, childIndent);
  out << ",\n" << childIndent << "\"extraInSet\": ";
  writePathArray(out, result.extraInSet, childIndent);
  out << ",\n" << childIndent << "\"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, childIndent);
  out << ",\n" << childIndent << "\"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics, childIndent);
  out << "\n" << indent << "}";
}

std::size_t packageSetVerificationMatchedCount(
    const std::vector<PackageMaintenanceSetVerificationResult> &verifications) {
  std::size_t count = 0;
  for (const PackageMaintenanceSetVerificationResult &verification :
       verifications) {
    if (verification.matches) {
      ++count;
    }
  }
  return count;
}

std::size_t packageSetVerificationMismatchedCount(
    const std::vector<PackageMaintenanceSetVerificationResult> &verifications) {
  std::size_t count = 0;
  for (const PackageMaintenanceSetVerificationResult &verification :
       verifications) {
    if (!verification.missingFromSet.empty() ||
        !verification.extraInSet.empty()) {
      ++count;
    }
  }
  return count;
}

std::size_t packageSetVerificationFailedCount(
    const std::vector<PackageMaintenanceSetVerificationResult> &verifications) {
  std::size_t count = 0;
  for (const PackageMaintenanceSetVerificationResult &verification :
       verifications) {
    const bool differs = !verification.missingFromSet.empty() ||
                         !verification.extraInSet.empty();
    if (!verification.success && !differs) {
      ++count;
    }
  }
  return count;
}

std::size_t packageSetVerificationScannedPackageCount(
    const std::vector<PackageMaintenanceSetVerificationResult> &verifications) {
  std::size_t count = 0;
  for (const PackageMaintenanceSetVerificationResult &verification :
       verifications) {
    count += verification.scannedPackagePaths.size();
  }
  return count;
}

std::size_t packageSetVerificationSetPackageCount(
    const std::vector<PackageMaintenanceSetVerificationResult> &verifications) {
  std::size_t count = 0;
  for (const PackageMaintenanceSetVerificationResult &verification :
       verifications) {
    count += verification.setPackagePaths.size();
  }
  return count;
}

std::size_t packageSetVerificationMissingFromSetCount(
    const std::vector<PackageMaintenanceSetVerificationResult> &verifications) {
  std::size_t count = 0;
  for (const PackageMaintenanceSetVerificationResult &verification :
       verifications) {
    count += verification.missingFromSet.size();
  }
  return count;
}

std::size_t packageSetVerificationExtraInSetCount(
    const std::vector<PackageMaintenanceSetVerificationResult> &verifications) {
  std::size_t count = 0;
  for (const PackageMaintenanceSetVerificationResult &verification :
       verifications) {
    count += verification.extraInSet.size();
  }
  return count;
}

std::string packageMaintenanceSetVerificationJson(
    const PackageMaintenanceSetVerificationResult &result) {
  std::ostringstream out;
  writePackageMaintenanceSetVerificationResult(out, result, "");
  out << "\n";
  return out.str();
}

std::string packageMaintenanceSetVerificationText(
    const PackageMaintenanceSetVerificationResult &result) {
  std::ostringstream out;
  if (result.matches) {
    out << "package maintenance set matches scan "
        << result.setPath.lexically_normal().generic_string() << "\n";
  } else {
    out << "package maintenance set differs from scan "
        << result.setPath.lexically_normal().generic_string() << "\n";
  }
  out << "  root=" << result.rootPath.lexically_normal().generic_string()
      << "\n"
      << "  scanned=" << result.scannedPackagePaths.size()
      << " set=" << result.setPackagePaths.size()
      << " missing-from-set=" << result.missingFromSet.size()
      << " extra-in-set=" << result.extraInSet.size() << "\n";
  for (const std::filesystem::path &packagePath : result.missingFromSet) {
    out << "  missing-from-set "
        << packagePath.lexically_normal().generic_string() << "\n";
  }
  for (const std::filesystem::path &packagePath : result.extraInSet) {
    out << "  extra-in-set " << packagePath.lexically_normal().generic_string()
        << "\n";
  }
  return out.str();
}

void writePackageMaintenanceSetVerificationSummary(
    std::ostream &out, const PackageMaintenanceSetVerificationResult &result,
    std::string_view indent) {
  const std::string childIndent = std::string(indent) + "  ";
  out << indent << "{\n"
      << childIndent << "\"rootPath\": \""
      << escapeJson(result.rootPath.lexically_normal().generic_string())
      << "\",\n"
      << childIndent << "\"setPath\": \""
      << escapeJson(result.setPath.lexically_normal().generic_string())
      << "\",\n"
      << childIndent << "\"success\": " << (result.success ? "true" : "false")
      << ",\n"
      << childIndent << "\"matches\": " << (result.matches ? "true" : "false")
      << ",\n"
      << childIndent
      << "\"scannedPackageCount\": " << result.scannedPackagePaths.size()
      << ",\n"
      << childIndent << "\"setPackageCount\": " << result.setPackagePaths.size()
      << ",\n"
      << childIndent
      << "\"missingFromSetCount\": " << result.missingFromSet.size() << ",\n"
      << childIndent << "\"extraInSetCount\": " << result.extraInSet.size()
      << ",\n"
      << childIndent << "\"missingFromSet\": ";
  writePathArray(out, result.missingFromSet, childIndent);
  out << ",\n" << childIndent << "\"extraInSet\": ";
  writePathArray(out, result.extraInSet, childIndent);
  out << ",\n" << childIndent << "\"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, childIndent);
  out << ",\n" << childIndent << "\"diagnosticCodeCounts\": ";
  writeDiagnosticCodeCounts(out, result.diagnostics, childIndent);
  out << "\n" << indent << "}";
}

std::string packageMaintenanceSetVerificationBatchSummaryJson(
    const PackageMaintenanceSetVerificationBatchResult &result) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"batchPath\": \""
      << escapeJson(result.batchPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"success\": " << (result.success ? "true" : "false") << ",\n"
      << "  \"matches\": " << (result.matches ? "true" : "false") << ",\n"
      << "  \"releaseEligible\": "
      << ((result.success && result.matches) ? "true" : "false") << ",\n"
      << "  \"verificationCount\": " << result.verifications.size() << ",\n"
      << "  \"matchedCount\": "
      << packageSetVerificationMatchedCount(result.verifications) << ",\n"
      << "  \"mismatchedCount\": "
      << packageSetVerificationMismatchedCount(result.verifications) << ",\n"
      << "  \"failedCount\": "
      << packageSetVerificationFailedCount(result.verifications) << ",\n"
      << "  \"scannedPackageCount\": "
      << packageSetVerificationScannedPackageCount(result.verifications)
      << ",\n"
      << "  \"setPackageCount\": "
      << packageSetVerificationSetPackageCount(result.verifications) << ",\n"
      << "  \"missingFromSetCount\": "
      << packageSetVerificationMissingFromSetCount(result.verifications)
      << ",\n"
      << "  \"extraInSetCount\": "
      << packageSetVerificationExtraInSetCount(result.verifications) << ",\n"
      << "  \"verifications\": [";
  for (std::size_t index = 0; index < result.verifications.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageMaintenanceSetVerificationSummary(
        out, result.verifications[index], "    ");
  }
  if (!result.verifications.empty()) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, "  ");
  out << ",\n"
      << "  \"diagnosticCodeCounts\": ";
  writeDiagnosticCodeCounts(out, result.diagnostics, "  ");
  out << "\n}\n";
  return out.str();
}

std::string packageMaintenanceSetVerificationBatchSummaryExportText(
    const PackageMaintenanceSetVerificationBatchSummaryExportResult &result) {
  std::ostringstream out;
  out << "exported package maintenance set verification batch summary "
      << result.summaryPath.lexically_normal().generic_string() << "\n";
  return out.str();
}

void writePackageReleasePromotionDiagnosticCounts(
    std::ostream &out, const PackageReleasePromotionDiagnosticCounts &counts,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"note\": " << counts.note << ",\n"
      << indent << "  \"warning\": " << counts.warning << ",\n"
      << indent << "  \"error\": " << counts.error << "\n"
      << indent << "}";
}

void writePackageReleasePromotionSummary(
    std::ostream &out, const PackageReleasePromotionSummary &summary,
    std::string_view indent, const std::filesystem::path &evidenceBasePath) {
  const std::string childIndent = std::string(indent) + "  ";
  out << indent << "{\n"
      << childIndent << "\"summaryPath\": \""
      << escapeJson(packageReleaseOutputEvidencePathString(
             summary.summaryPath, evidenceBasePath))
      << "\",\n"
      << childIndent << "\"batchPath\": \""
      << escapeJson(packageReleaseOutputEvidencePathString(
             summary.batchPath, evidenceBasePath))
      << "\",\n"
      << childIndent << "\"success\": " << (summary.success ? "true" : "false")
      << ",\n"
      << childIndent << "\"matches\": " << (summary.matches ? "true" : "false")
      << ",\n"
      << childIndent
      << "\"releaseEligible\": " << (summary.releaseEligible ? "true" : "false")
      << ",\n"
      << childIndent << "\"verificationCount\": " << summary.verificationCount
      << ",\n"
      << childIndent << "\"matchedCount\": " << summary.matchedCount << ",\n"
      << childIndent << "\"mismatchedCount\": " << summary.mismatchedCount
      << ",\n"
      << childIndent << "\"failedCount\": " << summary.failedCount << ",\n"
      << childIndent
      << "\"scannedPackageCount\": " << summary.scannedPackageCount << ",\n"
      << childIndent << "\"setPackageCount\": " << summary.setPackageCount
      << ",\n"
      << childIndent
      << "\"missingFromSetCount\": " << summary.missingFromSetCount << ",\n"
      << childIndent << "\"extraInSetCount\": " << summary.extraInSetCount
      << ",\n"
      << childIndent << "\"diagnosticCounts\": ";
  writePackageReleasePromotionDiagnosticCounts(out, summary.diagnosticCounts,
                                               childIndent);
  out << "\n" << indent << "}";
}

void writePackageReleasePromotionSourceHash(
    std::ostream &out,
    const std::optional<PackageReleasePromotionSourceHash> &sourceHash,
    std::string_view indent) {
  if (!sourceHash) {
    out << "null";
    return;
  }
  out << "{\n"
      << indent << "  \"algorithm\": \"" << escapeJson(sourceHash->algorithm)
      << "\",\n"
      << indent << "  \"value\": \"" << escapeJson(sourceHash->value) << "\"\n"
      << indent << "}";
}

void writePackageReleasePromotionArtifact(
    std::ostream &out, const PackageReleasePromotionArtifact &artifact,
    std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"name\": \"" << escapeJson(artifact.name) << "\",\n"
      << indent << "  \"path\": \"" << escapeJson(artifact.path) << "\",\n"
      << indent << "  \"exists\": " << (artifact.exists ? "true" : "false")
      << ",\n"
      << indent << "  \"sizeBytes\": ";
  if (artifact.sizeBytes) {
    out << *artifact.sizeBytes;
  } else {
    out << "null";
  }
  out << ",\n" << indent << "  \"sha256\": ";
  writeNullableString(out, artifact.sha256);
  out << "\n" << indent << "}";
}

void writePackageReleaseArtifactRequirements(
    std::ostream &out,
    const std::optional<PackageReleasePackageArtifactRequirements> &requirements,
    std::string_view indent) {
  if (!requirements) {
    out << "null";
    return;
  }
  const std::string childIndent = std::string(indent) + "  ";
  out << "{\n"
      << childIndent << "\"target\": \"" << escapeJson(requirements->target)
      << "\",\n"
      << childIndent << "\"packageMode\": \""
      << escapeJson(requirements->packageMode) << "\",\n"
      << childIndent << "\"requiredPathArtifacts\": [";
  for (std::size_t index = 0; index < requirements->requiredPathArtifacts.size();
       ++index) {
    out << (index == 0 ? "\n" : ",\n")
        << childIndent << "  \""
        << escapeJson(requirements->requiredPathArtifacts[index]) << "\"";
  }
  if (!requirements->requiredPathArtifacts.empty()) {
    out << "\n" << childIndent;
  }
  out << "],\n"
      << childIndent << "\"requiresNativeBinaryStatus\": "
      << (requirements->requiresNativeBinaryStatus ? "true" : "false")
      << ",\n"
      << childIndent << "\"allowsPlannedNativeBinary\": "
      << (requirements->allowsPlannedNativeBinary ? "true" : "false")
      << ",\n"
      << childIndent << "\"allowsPlannedNativeSourceEvidence\": "
      << (requirements->allowsPlannedNativeSourceEvidence ? "true" : "false")
      << "\n"
      << indent << "}";
}

void writePackageReleasePromotionPackage(
    std::ostream &out, const PackageReleasePromotionPackage &package,
    std::string_view indent) {
  const std::string childIndent = std::string(indent) + "  ";
  out << indent << "{\n"
      << childIndent << "\"packagePath\": \""
      << escapeJson(package.packagePath.lexically_normal().generic_string())
      << "\",\n"
      << childIndent << "\"module\": \"" << escapeJson(package.module)
      << "\",\n"
      << childIndent << "\"target\": \"" << escapeJson(package.target)
      << "\",\n"
      << childIndent << "\"sourceHash\": ";
  writePackageReleasePromotionSourceHash(out, package.sourceHash, childIndent);
  out << ",\n" << childIndent << "\"nativeBinaryStatus\": ";
  writeNullableString(out, package.nativeBinaryStatus);
  out << ",\n" << childIndent << "\"packageArtifactRequirements\": ";
  writePackageReleaseArtifactRequirements(out, package.artifactRequirements,
                                          childIndent);
  out << ",\n"
      << childIndent << "\"artifactCount\": " << package.artifacts.size()
      << ",\n"
      << childIndent << "\"artifacts\": [";
  for (std::size_t index = 0; index < package.artifacts.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageReleasePromotionArtifact(out, package.artifacts[index],
                                         childIndent + "  ");
  }
  if (!package.artifacts.empty()) {
    out << "\n" << childIndent;
  }
  out << "]\n" << indent << "}";
}

std::size_t packageReleaseArtifactCount(
    const std::vector<PackageReleasePromotionPackage> &packages) {
  std::size_t count = 0;
  for (const PackageReleasePromotionPackage &package : packages) {
    count += package.artifacts.size();
  }
  return count;
}

std::size_t packageReleaseExistingArtifactCount(
    const PackageReleasePromotionPackage &package) {
  return static_cast<std::size_t>(
      std::count_if(package.artifacts.begin(), package.artifacts.end(),
                    [](const PackageReleasePromotionArtifact &artifact) {
                      return artifact.exists;
                    }));
}

std::size_t packageReleaseExistingArtifactCount(
    const std::vector<PackageReleasePromotionPackage> &packages) {
  std::size_t count = 0;
  for (const PackageReleasePromotionPackage &package : packages) {
    count += packageReleaseExistingArtifactCount(package);
  }
  return count;
}

std::uintmax_t packageReleaseTotalArtifactBytes(
    const PackageReleasePromotionPackage &package) {
  std::uintmax_t bytes = 0;
  for (const PackageReleasePromotionArtifact &artifact : package.artifacts) {
    if (artifact.exists && artifact.sizeBytes) {
      bytes += *artifact.sizeBytes;
    }
  }
  return bytes;
}

std::uintmax_t packageReleaseTotalArtifactBytes(
    const std::vector<PackageReleasePromotionPackage> &packages) {
  std::uintmax_t bytes = 0;
  for (const PackageReleasePromotionPackage &package : packages) {
    bytes += packageReleaseTotalArtifactBytes(package);
  }
  return bytes;
}

void writePackageReleaseBundlePackage(
    std::ostream &out, const PackageReleasePromotionPackage &package,
    std::string_view indent) {
  const std::string childIndent = std::string(indent) + "  ";
  const std::size_t existingArtifactCount =
      packageReleaseExistingArtifactCount(package);
  const std::size_t missingArtifactCount =
      package.artifacts.size() - existingArtifactCount;
  out << indent << "{\n"
      << childIndent << "\"packagePath\": \""
      << escapeJson(package.packagePath.lexically_normal().generic_string())
      << "\",\n"
      << childIndent << "\"module\": \"" << escapeJson(package.module)
      << "\",\n"
      << childIndent << "\"target\": \"" << escapeJson(package.target)
      << "\",\n"
      << childIndent << "\"sourceHash\": ";
  writePackageReleasePromotionSourceHash(out, package.sourceHash, childIndent);
  out << ",\n" << childIndent << "\"nativeBinaryStatus\": ";
  writeNullableString(out, package.nativeBinaryStatus);
  out << ",\n" << childIndent << "\"packageArtifactRequirements\": ";
  writePackageReleaseArtifactRequirements(out, package.artifactRequirements,
                                          childIndent);
  out << ",\n"
      << childIndent << "\"artifactCount\": " << package.artifacts.size()
      << ",\n"
      << childIndent << "\"existingArtifactCount\": " << existingArtifactCount
      << ",\n"
      << childIndent << "\"missingArtifactCount\": " << missingArtifactCount
      << ",\n"
      << childIndent
      << "\"totalArtifactBytes\": " << packageReleaseTotalArtifactBytes(package)
      << ",\n"
      << childIndent << "\"artifacts\": [";
  for (std::size_t index = 0; index < package.artifacts.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageReleasePromotionArtifact(out, package.artifacts[index],
                                         childIndent + "  ");
  }
  if (!package.artifacts.empty()) {
    out << "\n" << childIndent;
  }
  out << "]\n" << indent << "}";
}

std::string packageReleasePromotionManifestJson(
    const PackageReleasePromotionManifestResult &result) {
  const std::filesystem::path evidenceBasePath =
      absoluteNormalizedPath(packageParentPath(result.manifestPath));
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"summaryPath\": \""
      << escapeJson(packageReleaseOutputEvidencePathString(result.summaryPath,
                                                           evidenceBasePath))
      << "\",\n"
      << "  \"manifestPath\": \""
      << escapeJson(packageReleaseOutputEvidencePathString(result.manifestPath,
                                                           evidenceBasePath))
      << "\",\n"
      << "  \"batchPath\": \""
      << escapeJson(packageReleaseOutputEvidencePathString(
             result.summary.batchPath, evidenceBasePath))
      << "\",\n"
      << "  \"status\": \"" << (result.releaseEligible ? "eligible" : "blocked")
      << "\",\n"
      << "  \"releaseEligible\": "
      << (result.releaseEligible ? "true" : "false") << ",\n"
      << "  \"blockerCount\": " << result.blockers.size() << ",\n"
      << "  \"blockers\": [";
  for (std::size_t index = 0; index < result.blockers.size(); ++index) {
    const PackageReleasePromotionBlocker &blocker = result.blockers[index];
    out << (index == 0 ? "\n" : ",\n") << "    {\n"
        << "      \"code\": \"" << escapeJson(blocker.code) << "\",\n"
        << "      \"message\": \"" << escapeJson(blocker.message) << "\",\n"
        << "      \"count\": " << blocker.count << "\n"
        << "    }";
  }
  if (!result.blockers.empty()) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"packageCount\": " << result.packages.size() << ",\n"
      << "  \"packages\": [";
  for (std::size_t index = 0; index < result.packages.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageReleasePromotionPackage(out, result.packages[index], "    ");
  }
  if (!result.packages.empty()) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"summary\": ";
  writePackageReleasePromotionSummary(out, result.summary, "  ",
                                      evidenceBasePath);
  out << ",\n"
      << "  \"diagnosticCounts\": ";
  writePackageReleasePromotionDiagnosticCounts(
      out, result.summary.diagnosticCounts, "  ");
  out << "\n}\n";
  return out.str();
}

std::string packageReleasePromotionManifestText(
    const PackageReleasePromotionManifestResult &result) {
  std::ostringstream out;
  out << "package release promotion "
      << (result.releaseEligible ? "eligible " : "blocked ")
      << result.manifestPath.lexically_normal().generic_string() << "\n"
      << "  summary=" << result.summaryPath.lexically_normal().generic_string()
      << "\n"
      << "  batch="
      << result.summary.batchPath.lexically_normal().generic_string() << "\n"
      << "  verifications=" << result.summary.verificationCount
      << " packages=" << result.packages.size()
      << " matched=" << result.summary.matchedCount
      << " mismatched=" << result.summary.mismatchedCount
      << " failed=" << result.summary.failedCount << "\n";
  for (const PackageReleasePromotionBlocker &blocker : result.blockers) {
    out << "  blocker " << blocker.code << " count=" << blocker.count << "\n";
  }
  return out.str();
}

std::string packageReleaseBundleManifestJson(
    const PackageReleaseBundleManifestResult &result) {
  const std::size_t artifactCount =
      packageReleaseArtifactCount(result.promotion.packages);
  const std::size_t existingArtifactCount =
      packageReleaseExistingArtifactCount(result.promotion.packages);
  const std::size_t missingArtifactCount =
      artifactCount - existingArtifactCount;
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"bundlePath\": \""
      << escapeJson(result.bundlePath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"promotionManifestPath\": \""
      << escapeJson(
             result.promotionManifestPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"summaryPath\": \""
      << escapeJson(
             result.promotion.summaryPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"batchPath\": \""
      << escapeJson(result.promotion.summary.batchPath.lexically_normal()
                        .generic_string())
      << "\",\n"
      << "  \"status\": \"" << (result.releaseEligible ? "eligible" : "blocked")
      << "\",\n"
      << "  \"releaseEligible\": "
      << (result.releaseEligible ? "true" : "false") << ",\n"
      << "  \"blockerCount\": " << result.promotion.blockers.size() << ",\n"
      << "  \"blockers\": [";
  for (std::size_t index = 0; index < result.promotion.blockers.size();
       ++index) {
    const PackageReleasePromotionBlocker &blocker =
        result.promotion.blockers[index];
    out << (index == 0 ? "\n" : ",\n") << "    {\n"
        << "      \"code\": \"" << escapeJson(blocker.code) << "\",\n"
        << "      \"message\": \"" << escapeJson(blocker.message) << "\",\n"
        << "      \"count\": " << blocker.count << "\n"
        << "    }";
  }
  if (!result.promotion.blockers.empty()) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"packageCount\": " << result.promotion.packages.size() << ",\n"
      << "  \"artifactCount\": " << artifactCount << ",\n"
      << "  \"existingArtifactCount\": " << existingArtifactCount << ",\n"
      << "  \"missingArtifactCount\": " << missingArtifactCount << ",\n"
      << "  \"totalArtifactBytes\": "
      << packageReleaseTotalArtifactBytes(result.promotion.packages) << ",\n"
      << "  \"packages\": [";
  for (std::size_t index = 0; index < result.promotion.packages.size();
       ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageReleaseBundlePackage(out, result.promotion.packages[index],
                                     "    ");
  }
  if (!result.promotion.packages.empty()) {
    out << "\n  ";
  }
  out << "]\n}\n";
  return out.str();
}

std::string packageReleaseBundleManifestText(
    const PackageReleaseBundleManifestResult &result) {
  const std::size_t artifactCount =
      packageReleaseArtifactCount(result.promotion.packages);
  const std::size_t existingArtifactCount =
      packageReleaseExistingArtifactCount(result.promotion.packages);
  const std::size_t missingArtifactCount =
      artifactCount - existingArtifactCount;
  std::ostringstream out;
  out << "package release bundle "
      << (result.releaseEligible ? "eligible " : "blocked ")
      << result.bundlePath.lexically_normal().generic_string() << "\n"
      << "  promotionManifest="
      << result.promotionManifestPath.lexically_normal().generic_string()
      << "\n"
      << "  summary="
      << result.promotion.summaryPath.lexically_normal().generic_string()
      << "\n"
      << "  batch="
      << result.promotion.summary.batchPath.lexically_normal().generic_string()
      << "\n"
      << "  packages=" << result.promotion.packages.size()
      << " artifacts=" << artifactCount
      << " existingArtifacts=" << existingArtifactCount
      << " missingArtifacts=" << missingArtifactCount << " bytes="
      << packageReleaseTotalArtifactBytes(result.promotion.packages) << "\n";
  for (const PackageReleasePromotionBlocker &blocker :
       result.promotion.blockers) {
    out << "  blocker " << blocker.code << " count=" << blocker.count << "\n";
  }
  return out.str();
}

std::string packageReleaseBundleVerificationJson(
    const PackageReleaseBundleVerificationResult &result) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"bundlePath\": \""
      << escapeJson(releaseBundleVerificationBundlePathField(result.bundlePath)
                        .generic_string())
      << "\",\n"
      << "  \"success\": " << (result.success ? "true" : "false") << ",\n"
      << "  \"status\": \""
      << escapeJson(result.status.empty() ? "invalid" : result.status)
      << "\",\n"
      << "  \"releaseEligible\": "
      << (result.releaseEligible ? "true" : "false") << ",\n"
      << "  \"blockerCount\": " << result.blockerCount << ",\n"
      << "  \"packageCount\": " << result.packageCount << ",\n"
      << "  \"artifactCount\": " << result.artifactCount << ",\n"
      << "  \"existingArtifactCount\": " << result.existingArtifactCount
      << ",\n"
      << "  \"missingArtifactCount\": " << result.missingArtifactCount << ",\n"
      << "  \"totalArtifactBytes\": " << result.totalArtifactBytes << ",\n"
      << "  \"verifiedArtifactCount\": " << result.verifiedArtifactCount
      << ",\n"
      << "  \"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, "  ");
  out << ",\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics);
  out << "\n}\n";
  return out.str();
}

std::string packageReleaseBundleVerificationText(
    const PackageReleaseBundleVerificationResult &result) {
  std::ostringstream out;
  out << "package release bundle verification "
      << (result.success ? "passed " : "failed ")
      << result.bundlePath.lexically_normal().generic_string() << "\n"
      << "  status=" << (result.status.empty() ? "invalid" : result.status)
      << " releaseEligible=" << (result.releaseEligible ? "true" : "false")
      << " blockers=" << result.blockerCount << "\n"
      << "  packages=" << result.packageCount
      << " artifacts=" << result.artifactCount
      << " existingArtifacts=" << result.existingArtifactCount
      << " missingArtifacts=" << result.missingArtifactCount
      << " verifiedArtifacts=" << result.verifiedArtifactCount
      << " bytes=" << result.totalArtifactBytes << "\n";
  return out.str();
}

void writePackageReleasePublishPlanArtifact(
    std::ostream &out, const PackageReleasePublishPlanArtifact &artifact,
    std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"name\": \"" << escapeJson(artifact.name) << "\",\n"
      << indent << "  \"packagePath\": \""
      << escapeJson(artifact.packagePath.lexically_normal().generic_string())
      << "\",\n"
      << indent << "  \"module\": \"" << escapeJson(artifact.module) << "\",\n"
      << indent << "  \"target\": \"" << escapeJson(artifact.target) << "\",\n"
      << indent << "  \"sourcePath\": \""
      << escapeJson(artifact.sourcePath.lexically_normal().generic_string())
      << "\",\n"
      << indent << "  \"packageArtifactPath\": \""
      << escapeJson(artifact.packageArtifactPath) << "\",\n"
      << indent << "  \"destinationPath\": \""
      << escapeJson(artifact.destinationPath) << "\",\n"
      << indent << "  \"sizeBytes\": " << artifact.sizeBytes << ",\n"
      << indent << "  \"sha256\": \"" << escapeJson(artifact.sha256) << "\"\n"
      << indent << "}";
}

void writePackageReleasePublishPlanPackage(
    std::ostream &out, const PackageReleasePublishPlanPackage &package,
    std::string_view indent) {
  const std::string childIndent = std::string(indent) + "  ";
  out << indent << "{\n"
      << childIndent << "\"packagePath\": \""
      << escapeJson(package.packagePath.lexically_normal().generic_string())
      << "\",\n"
      << childIndent << "\"module\": \"" << escapeJson(package.module)
      << "\",\n"
      << childIndent << "\"target\": \"" << escapeJson(package.target)
      << "\",\n"
      << childIndent << "\"sourceHash\": ";
  writePackageReleasePromotionSourceHash(out, package.sourceHash, childIndent);
  out << ",\n" << childIndent << "\"nativeBinaryStatus\": ";
  writeNullableString(out, package.nativeBinaryStatus);
  out << ",\n" << childIndent << "\"packageArtifactRequirements\": ";
  writePackageReleaseArtifactRequirements(out, package.artifactRequirements,
                                          childIndent);
  out << ",\n"
      << childIndent << "\"artifactCount\": " << package.artifacts.size()
      << ",\n"
      << childIndent << "\"totalArtifactBytes\": " << package.totalArtifactBytes
      << ",\n"
      << childIndent << "\"artifacts\": [";
  for (std::size_t index = 0; index < package.artifacts.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageReleasePublishPlanArtifact(out, package.artifacts[index],
                                           childIndent + "  ");
  }
  if (!package.artifacts.empty()) {
    out << "\n" << childIndent;
  }
  out << "]\n" << indent << "}";
}

std::string
packageReleasePublishPlanJson(const PackageReleasePublishPlanResult &result) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"bundlePath\": \""
      << escapeJson(result.bundlePath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"planPath\": \""
      << escapeJson(result.planPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"releaseEligible\": "
      << (result.releaseEligible ? "true" : "false") << ",\n"
      << "  \"packageCount\": " << result.packages.size() << ",\n"
      << "  \"artifactCount\": " << result.artifacts.size() << ",\n"
      << "  \"totalArtifactBytes\": " << result.totalArtifactBytes << ",\n"
      << "  \"packages\": [";
  for (std::size_t index = 0; index < result.packages.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageReleasePublishPlanPackage(out, result.packages[index], "    ");
  }
  if (!result.packages.empty()) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"artifacts\": [";
  for (std::size_t index = 0; index < result.artifacts.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageReleasePublishPlanArtifact(out, result.artifacts[index],
                                           "    ");
  }
  if (!result.artifacts.empty()) {
    out << "\n  ";
  }
  out << "]\n}\n";
  return out.str();
}

std::string
packageReleasePublishPlanText(const PackageReleasePublishPlanResult &result) {
  std::ostringstream out;
  out << "package release publish plan "
      << (result.success ? "written " : "failed ")
      << result.planPath.lexically_normal().generic_string() << "\n"
      << "  bundle=" << result.bundlePath.lexically_normal().generic_string()
      << "\n"
      << "  packages=" << result.packages.size()
      << " artifacts=" << result.artifacts.size()
      << " bytes=" << result.totalArtifactBytes << "\n";
  return out.str();
}

void writePackageReleasePublishStageArtifact(
    std::ostream &out, const PackageReleasePublishStageArtifact &staged,
    std::string_view indent) {
  const PackageReleasePublishPlanArtifact &artifact = staged.artifact;
  out << indent << "{\n"
      << indent << "  \"name\": \"" << escapeJson(artifact.name) << "\",\n"
      << indent << "  \"packagePath\": \""
      << escapeJson(artifact.packagePath.lexically_normal().generic_string())
      << "\",\n"
      << indent << "  \"module\": \"" << escapeJson(artifact.module) << "\",\n"
      << indent << "  \"target\": \"" << escapeJson(artifact.target) << "\",\n"
      << indent << "  \"sourcePath\": \""
      << escapeJson(artifact.sourcePath.lexically_normal().generic_string())
      << "\",\n"
      << indent << "  \"packageArtifactPath\": \""
      << escapeJson(artifact.packageArtifactPath) << "\",\n"
      << indent << "  \"destinationPath\": \""
      << escapeJson(artifact.destinationPath) << "\",\n"
      << indent << "  \"stagedPath\": \""
      << escapeJson(staged.stagedPath.lexically_normal().generic_string())
      << "\",\n"
      << indent << "  \"sizeBytes\": " << artifact.sizeBytes << ",\n"
      << indent << "  \"sha256\": \"" << escapeJson(artifact.sha256) << "\",\n"
      << indent << "  \"staged\": " << (staged.staged ? "true" : "false")
      << "\n"
      << indent << "}";
}

std::string
packageReleasePublishStageJson(const PackageReleasePublishStageResult &result) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"planPath\": \""
      << escapeJson(result.planPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"stagePath\": \""
      << escapeJson(result.stagePath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"success\": " << (result.success ? "true" : "false") << ",\n"
      << "  \"packageCount\": " << result.packageCount << ",\n"
      << "  \"artifactCount\": " << result.artifactCount << ",\n"
      << "  \"totalArtifactBytes\": " << result.totalArtifactBytes << ",\n"
      << "  \"stagedArtifactCount\": " << result.stagedArtifactCount << ",\n"
      << "  \"stagedArtifactBytes\": " << result.stagedArtifactBytes << ",\n"
      << "  \"artifacts\": [";
  for (std::size_t index = 0; index < result.artifacts.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageReleasePublishStageArtifact(out, result.artifacts[index],
                                            "    ");
  }
  if (!result.artifacts.empty()) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, "  ");
  out << ",\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics);
  out << "\n}\n";
  return out.str();
}

std::string
packageReleasePublishStageText(const PackageReleasePublishStageResult &result) {
  std::ostringstream out;
  out << "package release publish stage "
      << (result.success ? "completed " : "failed ")
      << result.stagePath.lexically_normal().generic_string() << "\n"
      << "  plan=" << result.planPath.lexically_normal().generic_string()
      << "\n"
      << "  packages=" << result.packageCount
      << " artifacts=" << result.artifactCount
      << " stagedArtifacts=" << result.stagedArtifactCount
      << " bytes=" << result.stagedArtifactBytes << "/"
      << result.totalArtifactBytes << "\n";
  return out.str();
}

void writePackageReleaseReportArtifactInventoryRecord(
    std::ostream &out, const PackageReleaseReportArtifactInventoryRecord &record,
    std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"sourceRecordKind\": \""
      << escapeJson(record.sourceRecordKind) << "\",\n"
      << indent << "  \"packagePath\": \""
      << escapeJson(record.packagePath.lexically_normal().generic_string())
      << "\",\n"
      << indent << "  \"packageArtifactPath\": \""
      << escapeJson(record.packageArtifactPath) << "\",\n"
      << indent << "  \"stagedPath\": ";
  writeNullablePath(out, record.stagedPath);
  out << ",\n" << indent << "  \"destinationPath\": ";
  writeNullableString(out, record.destinationPath);
  out << ",\n" << indent << "  \"sizeBytes\": ";
  if (record.sizeBytes) {
    out << *record.sizeBytes;
  } else {
    out << "null";
  }
  out << ",\n" << indent << "  \"sha256\": ";
  writeNullableString(out, record.sha256);
  out << "\n" << indent << "}";
}

std::string packageReleaseReportArtifactInventoryJson(
    const PackageReleaseReportArtifactInventoryResult &result) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"bundlePath\": ";
  writeNullablePath(out, result.bundlePath);
  out << ",\n"
      << "  \"publishPlanPath\": ";
  writeNullablePath(out, result.publishPlanPath);
  out << ",\n"
      << "  \"stageReportPath\": ";
  writeNullablePath(out, result.stageReportPath);
  out << ",\n"
      << "  \"success\": " << (result.success ? "true" : "false") << ",\n"
      << "  \"artifactRecordCount\": " << result.artifactRecordCount << ",\n"
      << "  \"bundleArtifactRecordCount\": "
      << result.bundleArtifactRecordCount << ",\n"
      << "  \"publishPlanArtifactRecordCount\": "
      << result.publishPlanArtifactRecordCount << ",\n"
      << "  \"publishStageArtifactRecordCount\": "
      << result.publishStageArtifactRecordCount << ",\n"
      << "  \"stagedArtifactRecordCount\": "
      << result.stagedArtifactRecordCount << ",\n"
      << "  \"totalArtifactRecordBytes\": "
      << result.totalArtifactRecordBytes << ",\n"
      << "  \"records\": [";
  for (std::size_t index = 0; index < result.records.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageReleaseReportArtifactInventoryRecord(out,
                                                     result.records[index],
                                                     "    ");
  }
  if (!result.records.empty()) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, "  ");
  out << ",\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics);
  out << "\n}\n";
  return out.str();
}

std::string packageReleaseReportArtifactInventoryText(
    const PackageReleaseReportArtifactInventoryResult &result) {
  std::ostringstream out;
  out << "package release report artifact inventory "
      << (result.success ? "loaded" : "failed") << "\n"
      << "  records=" << result.artifactRecordCount
      << " bundleRecords=" << result.bundleArtifactRecordCount
      << " publishPlanRecords=" << result.publishPlanArtifactRecordCount
      << " publishStageRecords=" << result.publishStageArtifactRecordCount
      << " stagedRecords=" << result.stagedArtifactRecordCount
      << " bytes=" << result.totalArtifactRecordBytes << "\n";
  return out.str();
}

void writePackageReleasePublishReceiptArtifact(
    std::ostream &out, const PackageReleasePublishReceiptArtifact &published,
    std::string_view indent) {
  const PackageReleasePublishStageArtifact &staged = published.artifact;
  const PackageReleasePublishPlanArtifact &artifact = staged.artifact;
  out << indent << "{\n"
      << indent << "  \"name\": \"" << escapeJson(artifact.name) << "\",\n"
      << indent << "  \"packagePath\": \""
      << escapeJson(artifact.packagePath.lexically_normal().generic_string())
      << "\",\n"
      << indent << "  \"module\": \"" << escapeJson(artifact.module) << "\",\n"
      << indent << "  \"target\": \"" << escapeJson(artifact.target) << "\",\n"
      << indent << "  \"sourcePath\": \""
      << escapeJson(artifact.sourcePath.lexically_normal().generic_string())
      << "\",\n"
      << indent << "  \"packageArtifactPath\": \""
      << escapeJson(artifact.packageArtifactPath) << "\",\n"
      << indent << "  \"destinationPath\": \""
      << escapeJson(artifact.destinationPath) << "\",\n"
      << indent << "  \"stagedPath\": \""
      << escapeJson(staged.stagedPath.lexically_normal().generic_string())
      << "\",\n"
      << indent << "  \"publishedPath\": \""
      << escapeJson(published.publishedPath) << "\",\n"
      << indent << "  \"sizeBytes\": " << artifact.sizeBytes << ",\n"
      << indent << "  \"sha256\": \"" << escapeJson(artifact.sha256) << "\",\n"
      << indent << "  \"staged\": " << (staged.staged ? "true" : "false")
      << ",\n"
      << indent << "  \"planned\": " << (published.planned ? "true" : "false")
      << ",\n"
      << indent
      << "  \"published\": " << (published.published ? "true" : "false") << "\n"
      << indent << "}";
}

std::string packageReleasePublishReceiptJson(
    const PackageReleasePublishReceiptResult &result) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 2,\n"
      << "  \"stageReportPath\": \""
      << escapeJson(result.stageReportPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"targetDescriptorPath\": \""
      << escapeJson(
             result.targetDescriptorPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"receiptPath\": \""
      << escapeJson(result.receiptPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"receiptWritten\": " << (result.receiptWritten ? "true" : "false")
      << ",\n"
      << "  \"dryRun\": " << (result.dryRun ? "true" : "false") << ",\n"
      << "  \"targetKind\": \"" << escapeJson(result.targetKind) << "\",\n"
      << "  \"targetPath\": \""
      << escapeJson(result.targetPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"targetUri\": \"" << escapeJson(result.targetUri) << "\",\n"
      << "  \"targetEnabled\": " << (result.targetEnabled ? "true" : "false")
      << ",\n"
      << "  \"success\": " << (result.success ? "true" : "false") << ",\n"
      << "  \"packageCount\": " << result.packageCount << ",\n"
      << "  \"artifactCount\": " << result.artifactCount << ",\n"
      << "  \"totalArtifactBytes\": " << result.totalArtifactBytes << ",\n"
      << "  \"plannedArtifactCount\": " << result.plannedArtifactCount << ",\n"
      << "  \"plannedArtifactBytes\": " << result.plannedArtifactBytes << ",\n"
      << "  \"publishedArtifactCount\": " << result.publishedArtifactCount
      << ",\n"
      << "  \"publishedArtifactBytes\": " << result.publishedArtifactBytes
      << ",\n"
      << "  \"artifacts\": [";
  for (std::size_t index = 0; index < result.artifacts.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageReleasePublishReceiptArtifact(out, result.artifacts[index],
                                              "    ");
  }
  if (!result.artifacts.empty()) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, "  ");
  out << ",\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics);
  out << "\n}\n";
  return out.str();
}

std::string packageReleasePublishReceiptText(
    const PackageReleasePublishReceiptResult &result) {
  std::ostringstream out;
  out << "package release publish "
      << (result.success ? "completed " : "failed ")
      << result.targetPath.lexically_normal().generic_string() << "\n"
      << "  stageReport="
      << result.stageReportPath.lexically_normal().generic_string() << "\n"
      << "  targetKind=" << result.targetKind
      << " dryRun=" << (result.dryRun ? "true" : "false")
      << " artifacts=" << result.artifactCount
      << " plannedArtifacts=" << result.plannedArtifactCount
      << " publishedArtifacts=" << result.publishedArtifactCount
      << " bytes=" << result.publishedArtifactBytes << "/"
      << result.totalArtifactBytes << "\n";
  if (!result.targetUri.empty()) {
    out << "  targetUri=" << result.targetUri
        << " enabled=" << (result.targetEnabled ? "true" : "false") << "\n";
  }
  if (!result.targetDescriptorPath.empty()) {
    out << "  targetDescriptor="
        << result.targetDescriptorPath.lexically_normal().generic_string()
        << "\n";
  }
  if (!result.receiptPath.empty()) {
    out << "  receipt="
        << result.receiptPath.lexically_normal().generic_string()
        << " written=" << (result.receiptWritten ? "true" : "false") << "\n";
  }
  return out.str();
}

std::uintmax_t packageReleasePublishUploadRequestBytes(
    const std::vector<PackageReleasePublishUploadRequest> &requests) {
  std::uintmax_t total = 0;
  for (const PackageReleasePublishUploadRequest &request : requests) {
    total += request.sizeBytes;
  }
  return total;
}

std::string packageReleasePublishUploadAttemptStatusName(
    PackageReleasePublishUploadAttemptStatus status) {
  switch (status) {
  case PackageReleasePublishUploadAttemptStatus::Uploaded:
    return "uploaded";
  case PackageReleasePublishUploadAttemptStatus::AlreadyPresent:
    return "already-present";
  case PackageReleasePublishUploadAttemptStatus::Failed:
    return "failed";
  }
  return "failed";
}

bool packageReleasePublishUploadAttemptCompleted(
    const PackageReleasePublishUploadAttempt &attempt) {
  return attempt.status != PackageReleasePublishUploadAttemptStatus::Failed;
}

std::size_t packageReleasePublishUploadCompletedAttemptCount(
    const PackageReleasePublishUploadBatchResult &result) {
  return static_cast<std::size_t>(std::count_if(
      result.attempts.begin(), result.attempts.end(),
      [](const PackageReleasePublishUploadAttempt &attempt) {
        return packageReleasePublishUploadAttemptCompleted(attempt);
      }));
}

std::uintmax_t packageReleasePublishUploadAttemptBytes(
    const PackageReleasePublishUploadBatchResult &result) {
  std::uintmax_t total = 0;
  for (const PackageReleasePublishUploadAttempt &attempt : result.attempts) {
    total += attempt.request.sizeBytes;
  }
  return total;
}

std::uintmax_t packageReleasePublishUploadCompletedAttemptBytes(
    const PackageReleasePublishUploadBatchResult &result) {
  std::uintmax_t total = 0;
  for (const PackageReleasePublishUploadAttempt &attempt : result.attempts) {
    if (packageReleasePublishUploadAttemptCompleted(attempt)) {
      total += attempt.request.sizeBytes;
    }
  }
  return total;
}

void writePackageReleasePublishUploadRequest(
    std::ostream &out, const PackageReleasePublishUploadRequest &request,
    std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"targetKind\": \"" << escapeJson(request.targetKind)
      << "\",\n"
      << indent << "  \"stagedPath\": \""
      << escapeJson(request.stagedPath.lexically_normal().generic_string())
      << "\",\n"
      << indent << "  \"destinationPath\": \""
      << escapeJson(request.destinationPath) << "\",\n"
      << indent << "  \"bucket\": \"" << escapeJson(request.bucket) << "\",\n"
      << indent << "  \"objectName\": \"" << escapeJson(request.objectName)
      << "\",\n"
      << indent << "  \"uploadUri\": \"" << escapeJson(request.uploadUri)
      << "\",\n"
      << indent << "  \"credentialsEnv\": \""
      << escapeJson(request.credentialsEnv) << "\",\n"
      << indent << "  \"sizeBytes\": " << request.sizeBytes << ",\n"
      << indent << "  \"sha256\": \"" << escapeJson(request.sha256) << "\"\n"
      << indent << "}";
}

void writePackageReleasePublishUploadRequests(
    std::ostream &out,
    const std::vector<PackageReleasePublishUploadRequest> &requests,
    std::string_view indent) {
  out << "[";
  for (std::size_t index = 0; index < requests.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageReleasePublishUploadRequest(out, requests[index],
                                            std::string(indent) + "  ");
  }
  if (!requests.empty()) {
    out << "\n" << indent;
  }
  out << "]";
}

void writePackageReleasePublishUploadAttempt(
    std::ostream &out, const PackageReleasePublishUploadAttempt &attempt,
    std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"status\": \""
      << packageReleasePublishUploadAttemptStatusName(attempt.status)
      << "\",\n"
      << indent << "  \"provider\": \"" << escapeJson(attempt.provider)
      << "\",\n"
      << indent << "  \"overwrite\": "
      << (attempt.overwrite ? "true" : "false") << ",\n"
      << indent << "  \"idempotencyKey\": \""
      << escapeJson(attempt.idempotencyKey) << "\",\n"
      << indent << "  \"preconditionKind\": \""
      << escapeJson(attempt.preconditionKind) << "\",\n"
      << indent << "  \"preconditionValue\": \""
      << escapeJson(attempt.preconditionValue) << "\",\n"
      << indent << "  \"generation\": \"" << escapeJson(attempt.generation)
      << "\",\n"
      << indent << "  \"metageneration\": \""
      << escapeJson(attempt.metageneration) << "\",\n"
      << indent << "  \"crc32c\": \"" << escapeJson(attempt.crc32c)
      << "\",\n"
      << indent << "  \"md5Hash\": \"" << escapeJson(attempt.md5Hash)
      << "\",\n"
      << indent << "  \"errorMessage\": \""
      << escapeJson(attempt.errorMessage) << "\",\n"
      << indent << "  \"request\":\n";
  writePackageReleasePublishUploadRequest(out, attempt.request,
                                          std::string(indent) + "  ");
  out << "\n" << indent << "}";
}

void writePackageReleasePublishUploadAttempts(
    std::ostream &out,
    const std::vector<PackageReleasePublishUploadAttempt> &attempts,
    std::string_view indent) {
  out << "[";
  for (std::size_t index = 0; index < attempts.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageReleasePublishUploadAttempt(out, attempts[index],
                                            std::string(indent) + "  ");
  }
  if (!attempts.empty()) {
    out << "\n" << indent;
  }
  out << "]";
}

std::string packageReleasePublishUploadManifestJson(
    const std::vector<PackageReleasePublishUploadRequest> &requests) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"requestCount\": " << requests.size() << ",\n"
      << "  \"requestBytes\": "
      << packageReleasePublishUploadRequestBytes(requests) << ",\n"
      << "  \"requests\": ";
  writePackageReleasePublishUploadRequests(out, requests, "  ");
  out << "\n}\n";
  return out.str();
}

std::string packageReleasePublishUploadReceiptJson(
    const PackageReleasePublishUploadBatchResult &result) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"manifestPath\": \""
      << escapeJson(result.manifestPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"receiptPath\": \""
      << escapeJson(result.receiptPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"receiptWritten\": "
      << (result.receiptWritten ? "true" : "false") << ",\n"
      << "  \"uploadMode\": \"" << escapeJson(result.uploadMode) << "\",\n"
      << "  \"success\": " << (result.success ? "true" : "false") << ",\n"
      << "  \"requestCount\": " << result.requestCount << ",\n"
      << "  \"requestBytes\": " << result.requestBytes << ",\n"
      << "  \"attemptCount\": " << result.attempts.size() << ",\n"
      << "  \"attemptBytes\": "
      << packageReleasePublishUploadAttemptBytes(result) << ",\n"
      << "  \"completedAttemptCount\": "
      << packageReleasePublishUploadCompletedAttemptCount(result) << ",\n"
      << "  \"completedAttemptBytes\": "
      << packageReleasePublishUploadCompletedAttemptBytes(result) << ",\n"
      << "  \"attempts\": ";
  writePackageReleasePublishUploadAttempts(out, result.attempts, "  ");
  out << ",\n"
      << "  \"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, "  ");
  out << ",\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics);
  out << "\n}\n";
  return out.str();
}

std::string packageReleasePublishUploadBatchJson(
    const PackageReleasePublishUploadBatchResult &result) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"manifestPath\": \""
      << escapeJson(result.manifestPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"reportPath\": \""
      << escapeJson(result.reportPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"reportWritten\": " << (result.reportWritten ? "true" : "false")
      << ",\n"
      << "  \"uploadMode\": \"" << escapeJson(result.uploadMode) << "\",\n"
      << "  \"success\": " << (result.success ? "true" : "false") << ",\n"
      << "  \"requestCount\": " << result.requestCount << ",\n"
      << "  \"requestBytes\": " << result.requestBytes << ",\n"
      << "  \"uploadedArtifactCount\": " << result.uploadedArtifactCount
      << ",\n"
      << "  \"uploadedArtifactBytes\": " << result.uploadedArtifactBytes
      << ",\n"
      << "  \"uploadedRequests\": ";
  writePackageReleasePublishUploadRequests(out, result.uploadedRequests, "  ");
  out << ",\n"
      << "  \"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, "  ");
  out << ",\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics);
  out << "\n}\n";
  return out.str();
}

std::string packageReleasePublishUploadBatchText(
    const PackageReleasePublishUploadBatchResult &result) {
  std::ostringstream out;
  out << "package release upload batch "
      << (result.success ? "completed " : "failed ");
  if (!result.manifestPath.empty()) {
    out << result.manifestPath.lexically_normal().generic_string();
  } else {
    out << "requests";
  }
  out << "\n"
      << "  mode=" << (result.uploadMode.empty() ? "custom" : result.uploadMode)
      << " uploads=" << result.uploadedArtifactCount << "/"
      << result.requestCount << " bytes=" << result.uploadedArtifactBytes << "/"
      << result.requestBytes << "\n";
  if (!result.reportPath.empty()) {
    out << "  report=" << result.reportPath.lexically_normal().generic_string()
        << " written=" << (result.reportWritten ? "true" : "false") << "\n";
  }
  return out.str();
}

std::string packageReleasePublishUploadPreflightJson(
    const PackageReleasePublishUploadPreflightResult &result) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"manifestPath\": \""
      << escapeJson(result.manifestPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"reportPath\": \""
      << escapeJson(result.reportPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"reportWritten\": " << (result.reportWritten ? "true" : "false")
      << ",\n"
      << "  \"dryRun\": " << (result.dryRun ? "true" : "false") << ",\n"
      << "  \"success\": " << (result.success ? "true" : "false") << ",\n"
      << "  \"requestCount\": " << result.requestCount << ",\n"
      << "  \"requestBytes\": " << result.requestBytes << ",\n"
      << "  \"validatedRequestCount\": " << result.validatedRequestCount
      << ",\n"
      << "  \"validatedRequestBytes\": " << result.validatedRequestBytes
      << ",\n"
      << "  \"validatedRequests\": ";
  writePackageReleasePublishUploadRequests(out, result.validatedRequests, "  ");
  out << ",\n"
      << "  \"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, "  ");
  out << ",\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics);
  out << "\n}\n";
  return out.str();
}

std::string packageReleasePublishUploadPreflightText(
    const PackageReleasePublishUploadPreflightResult &result) {
  std::ostringstream out;
  out << "package release upload preflight "
      << (result.success ? "completed " : "failed ")
      << result.manifestPath.lexically_normal().generic_string() << "\n"
      << "  dryRun=" << (result.dryRun ? "true" : "false")
      << " requests=" << result.validatedRequestCount << "/"
      << result.requestCount << " bytes=" << result.validatedRequestBytes << "/"
      << result.requestBytes << "\n";
  if (!result.reportPath.empty()) {
    out << "  report=" << result.reportPath.lexically_normal().generic_string()
        << " written=" << (result.reportWritten ? "true" : "false") << "\n";
  }
  return out.str();
}

std::string packageMaintenanceSetVerificationBatchJson(
    const PackageMaintenanceSetVerificationBatchResult &result) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"batchPath\": \""
      << escapeJson(result.batchPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"success\": " << (result.success ? "true" : "false") << ",\n"
      << "  \"matches\": " << (result.matches ? "true" : "false") << ",\n"
      << "  \"verificationCount\": " << result.verifications.size() << ",\n"
      << "  \"matchedCount\": "
      << packageSetVerificationMatchedCount(result.verifications) << ",\n"
      << "  \"mismatchedCount\": "
      << packageSetVerificationMismatchedCount(result.verifications) << ",\n"
      << "  \"failedCount\": "
      << packageSetVerificationFailedCount(result.verifications) << ",\n"
      << "  \"verifications\": [";
  for (std::size_t index = 0; index < result.verifications.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writePackageMaintenanceSetVerificationResult(
        out, result.verifications[index], "    ");
  }
  if (!result.verifications.empty()) {
    out << "\n  ";
  }
  out << "],\n"
      << "  \"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, "  ");
  out << ",\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics);
  out << "\n}\n";
  return out.str();
}

std::string packageMaintenanceSetVerificationBatchText(
    const PackageMaintenanceSetVerificationBatchResult &result) {
  std::ostringstream out;
  out << (result.success ? "package maintenance set verification batch passed "
                         : "package maintenance set verification batch failed ")
      << result.batchPath.lexically_normal().generic_string() << "\n"
      << "  verifications=" << result.verifications.size()
      << " matched=" << packageSetVerificationMatchedCount(result.verifications)
      << " mismatched="
      << packageSetVerificationMismatchedCount(result.verifications)
      << " failed=" << packageSetVerificationFailedCount(result.verifications)
      << "\n";
  if (result.verifications.empty()) {
    out << "  no verifications\n";
    return out.str();
  }
  for (const PackageMaintenanceSetVerificationResult &verification :
       result.verifications) {
    std::istringstream verificationText(
        packageMaintenanceSetVerificationText(verification));
    std::string line;
    while (std::getline(verificationText, line)) {
      out << "  " << line << "\n";
    }
  }
  return out.str();
}

PackageRecoveryResult
recoverPackageSidecar(const std::filesystem::path &sidecarPath,
                      const PackageRecoveryOptions &options) {
  DiagnosticEngine diagnostics;
  PackageRecoveryResult result;
  result.sidecarPath = sidecarPath;

  const std::optional<PackageSidecarRecord> sidecar =
      parsePackageSidecarPath(sidecarPath);
  if (!sidecar) {
    diagnostics.error(
        recoveryDiagnosticCode("invalid-sidecar"),
        "package recover expects a staging or previous sidecar path",
        pathLocation(sidecarPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }
  result.requestedPath = sidecar->requestedPath;

  std::error_code error;
  if (!std::filesystem::exists(sidecarPath, error) || error) {
    diagnostics.error(recoveryDiagnosticCode("missing-sidecar"),
                      "package sidecar path does not exist: " +
                          sidecarPath.string(),
                      pathLocation(sidecarPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  if (options.action == PackageRecoveryAction::Discard) {
    std::filesystem::remove_all(sidecarPath, error);
    if (error) {
      diagnostics.error(recoveryDiagnosticCode("discard-failed"),
                        "failed to discard package sidecar: " + error.message(),
                        pathLocation(sidecarPath));
      result.diagnostics = diagnostics.diagnostics();
      return result;
    }

    result.success = true;
    result.message = "discarded package sidecar " + sidecarPath.string();
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  if (!std::filesystem::is_directory(sidecarPath, error) || error) {
    diagnostics.error(recoveryDiagnosticCode("invalid-sidecar"),
                      "package sidecar is not a directory: " +
                          sidecarPath.string(),
                      pathLocation(sidecarPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  const bool outputExists =
      std::filesystem::exists(sidecar->requestedPath, error);
  if (error) {
    diagnostics.error(recoveryDiagnosticCode("inspect-output"),
                      "failed to inspect requested package output path: " +
                          error.message(),
                      pathLocation(sidecar->requestedPath));
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  std::optional<std::filesystem::path> backupPath;
  if (outputExists) {
    if (!options.replace) {
      diagnostics.error(
          recoveryDiagnosticCode("output-exists"),
          "requested package output already exists; pass --replace "
          "to move it to a previous sidecar",
          pathLocation(sidecar->requestedPath));
      result.diagnostics = diagnostics.diagnostics();
      return result;
    }
  }

  PackageIntegrityResult verification =
      verifyPackage(sidecarPath, options.sourcePath);
  if (!verification.success) {
    diagnostics.error(recoveryDiagnosticCode("verify-failed"),
                      "package sidecar failed integrity verification",
                      pathLocation(sidecarPath));
    for (Diagnostic diagnostic : verification.diagnostics) {
      diagnostics.report(std::move(diagnostic));
    }
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  if (outputExists) {
    if (!std::filesystem::is_directory(sidecar->requestedPath, error) ||
        error) {
      diagnostics.error(recoveryDiagnosticCode("output-not-directory"),
                        "requested package output exists and is not a "
                        "directory: " +
                            sidecar->requestedPath.string(),
                        pathLocation(sidecar->requestedPath));
      result.diagnostics = diagnostics.diagnostics();
      return result;
    }

    backupPath = availablePackageSidecarPath(
        sidecar->requestedPath, "previous",
        recoveryDiagnosticCode("backup-path"), diagnostics);
    if (!backupPath) {
      result.diagnostics = diagnostics.diagnostics();
      return result;
    }
    std::filesystem::rename(sidecar->requestedPath, *backupPath, error);
    if (error) {
      diagnostics.error(recoveryDiagnosticCode("backup-failed"),
                        "failed to move requested package output to backup: " +
                            error.message(),
                        pathLocation(sidecar->requestedPath));
      result.diagnostics = diagnostics.diagnostics();
      return result;
    }
  }

  std::filesystem::rename(sidecarPath, sidecar->requestedPath, error);
  if (error) {
    diagnostics.error(recoveryDiagnosticCode("promote-failed"),
                      "failed to promote package sidecar: " + error.message(),
                      pathLocation(sidecarPath));
    if (backupPath) {
      std::error_code restoreError;
      std::filesystem::rename(*backupPath, sidecar->requestedPath,
                              restoreError);
      if (restoreError) {
        diagnostics.error(recoveryDiagnosticCode("restore-failed"),
                          "failed to restore previous package output: " +
                              restoreError.message(),
                          pathLocation(sidecar->requestedPath));
      }
    }
    result.diagnostics = diagnostics.diagnostics();
    return result;
  }

  result.success = true;
  result.backupPath = backupPath;
  result.message =
      recoveryPromoteMessage(sidecarPath, sidecar->requestedPath, backupPath);
  result.diagnostics = diagnostics.diagnostics();
  return result;
}

std::string packageRecoveryJson(const PackageRecoveryResult &result,
                                const PackageRecoveryOptions &options) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"action\": \"" << recoveryActionName(options.action) << "\",\n"
      << "  \"sidecarPath\": \""
      << escapeJson(result.sidecarPath.lexically_normal().generic_string())
      << "\",\n"
      << "  \"requestedPath\": ";
  writeNullablePath(out, result.requestedPath);
  out << ",\n"
      << "  \"backupPath\": ";
  writeNullablePath(out, result.backupPath);
  out << ",\n"
      << "  \"success\": " << (result.success ? "true" : "false") << ",\n"
      << "  \"replacedExisting\": "
      << (result.backupPath.has_value() ? "true" : "false") << ",\n"
      << "  \"message\": ";
  if (result.message.empty()) {
    out << "null";
  } else {
    out << "\"" << escapeJson(result.message) << "\"";
  }
  out << ",\n"
      << "  \"diagnosticCounts\": ";
  writeDiagnosticCounts(out, result.diagnostics, "  ");
  out << ",\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, result.diagnostics);
  out << "\n}\n";
  return out.str();
}

} // namespace crossgl
