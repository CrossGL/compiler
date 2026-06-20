#include "crossgl/Driver/PackageMetadata.h"

#include "crossgl/Basic/SHA256.h"
#include "crossgl/Driver/PackageJson.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <system_error>
#include <utility>

namespace crossgl {
namespace {

constexpr std::string_view kNativeArtifactDescriptorArtifact =
    "nativeArtifactDescriptor";
constexpr std::string_view kGraphicsAbiArtifact = "graphicsAbi";
constexpr std::string_view kNativeArtifactKind = "crossgl.nativeArtifact";
constexpr std::string_view kNativeArtifactContractVersion =
    "native-artifact-v0";
constexpr std::string_view kPackageArtifactRequirements =
    "packageArtifactRequirements";
constexpr std::string_view kTargetLegalizationToolRequirements =
    "targetLegalizationToolRequirements";

struct JsonObjectMemberRange {
  std::string name;
  JsonRange valueRange;
};

struct NativeArtifactToolRecord {
  std::string name;
  std::string role;
};

struct ZipMemberRecord {
  std::string path;
  std::string normalizedPath;
  std::uint16_t compressionMethod = 0;
  std::uint32_t compressedSize = 0;
  std::uint32_t uncompressedSize = 0;
  std::uint32_t localHeaderOffset = 0;
  bool directory = false;
};

struct PackageSource {
  std::filesystem::path packagePath;
  std::string format = "directory";
  std::map<std::string, ZipMemberRecord> zipMembers;
};

std::string diagnosticCode(const PackageMetadataLoadOptions &options,
                           std::string_view suffix) {
  return options.diagnosticCodePrefix + "." + std::string(suffix);
}

SourceLocation fileStartLocation(const std::filesystem::path &path) {
  SourceLocation location;
  location.file = path.lexically_normal().generic_string();
  return location;
}

SourceLocation archiveMemberStartLocation(const std::filesystem::path &archivePath,
                                          std::string_view memberPath) {
  SourceLocation location;
  location.file = archivePath.lexically_normal().generic_string() + "!/" +
                  std::string(memberPath);
  return location;
}

SourceLocation sourceStartLocation(const PackageSource &source,
                                   std::string_view relativePath) {
  if (source.format == "zip") {
    return archiveMemberStartLocation(source.packagePath, relativePath);
  }
  return fileStartLocation(source.packagePath / std::string(relativePath));
}

SourceLocation sourceLocationForRange(const std::filesystem::path &path,
                                      std::string_view text, JsonRange range) {
  SourceLocation location = fileStartLocation(path);
  range.begin = std::min(range.begin, text.size());
  range.end = std::min(range.end, text.size());
  if (range.end < range.begin) {
    range.end = range.begin;
  }

  std::size_t line = 1;
  std::size_t column = 1;
  for (std::size_t index = 0; index < range.begin; ++index) {
    if (text[index] == '\n') {
      ++line;
      column = 1;
    } else {
      ++column;
    }
  }

  location.line = line;
  location.column = column;
  location.offset = range.begin;
  location.length = range.end - range.begin;

  for (std::size_t index = range.begin; index < range.end; ++index) {
    if (text[index] == '\n') {
      ++line;
      column = 1;
    } else {
      ++column;
    }
  }

  location.endLine = line;
  location.endColumn = column;
  location.endOffset = range.end;
  return location;
}

JsonRange offsetRange(JsonRange range, std::size_t offset) {
  return JsonRange{range.begin + offset, range.end + offset};
}

std::uint16_t readLe16(std::string_view data, std::size_t offset) {
  return static_cast<std::uint16_t>(
      static_cast<unsigned char>(data[offset]) |
      (static_cast<unsigned char>(data[offset + 1]) << 8));
}

std::uint32_t readLe32(std::string_view data, std::size_t offset) {
  return static_cast<std::uint32_t>(static_cast<unsigned char>(data[offset])) |
         (static_cast<std::uint32_t>(
              static_cast<unsigned char>(data[offset + 1]))
          << 8) |
         (static_cast<std::uint32_t>(
              static_cast<unsigned char>(data[offset + 2]))
          << 16) |
         (static_cast<std::uint32_t>(
              static_cast<unsigned char>(data[offset + 3]))
          << 24);
}

bool fileHasZipSignature(const std::filesystem::path &path) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return false;
  }
  char signature[4] = {};
  input.read(signature, sizeof(signature));
  if (input.gcount() != sizeof(signature)) {
    return false;
  }
  const auto third = static_cast<unsigned char>(signature[2]);
  const auto fourth = static_cast<unsigned char>(signature[3]);
  return signature[0] == 'P' && signature[1] == 'K' &&
         ((third == 0x03 && fourth == 0x04) ||
          (third == 0x05 && fourth == 0x06) ||
          (third == 0x07 && fourth == 0x08));
}

std::optional<std::string> readFileSlice(const std::filesystem::path &path,
                                         std::uintmax_t offset,
                                         std::size_t size) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return std::nullopt;
  }
  input.seekg(static_cast<std::streamoff>(offset), std::ios::beg);
  if (!input) {
    return std::nullopt;
  }
  std::string data(size, '\0');
  input.read(data.data(), static_cast<std::streamsize>(data.size()));
  if (input.gcount() != static_cast<std::streamsize>(data.size())) {
    return std::nullopt;
  }
  return data;
}

bool isPackageRootMetadataFile(std::string_view path) {
  return path == "manifest.json" || path == "reflection.json" ||
         path == "diagnostics.json";
}

std::optional<std::string> normalizeZipMemberName(std::string_view path) {
  if (path.empty() || path.find('\\') != std::string_view::npos ||
      path.front() == '/') {
    return std::nullopt;
  }
  if (path.size() >= 2 && std::isalpha(static_cast<unsigned char>(path[0])) &&
      path[1] == ':') {
    return std::nullopt;
  }

  std::vector<std::string> parts;
  std::size_t start = 0;
  while (start <= path.size()) {
    const std::size_t slash = path.find('/', start);
    const std::size_t end =
        slash == std::string_view::npos ? path.size() : slash;
    const std::string_view part = path.substr(start, end - start);
    if (part == "..") {
      return std::nullopt;
    }
    if (!part.empty() && part != ".") {
      parts.emplace_back(part);
    }
    if (slash == std::string_view::npos) {
      break;
    }
    start = slash + 1;
  }
  if (parts.empty()) {
    return std::nullopt;
  }

  std::ostringstream normalized;
  for (std::size_t index = 0; index < parts.size(); ++index) {
    if (index > 0) {
      normalized << '/';
    }
    normalized << parts[index];
  }
  return normalized.str();
}

std::string zipMetadataRootLabel(std::string_view root) {
  if (root.empty()) {
    return "archive root";
  }
  std::string label(root);
  if (!label.empty() && label.back() == '/') {
    label.pop_back();
  }
  return label;
}

std::optional<std::string>
detectZipPackagePrefix(const std::vector<std::string> &paths,
                       const std::filesystem::path &archivePath,
                       DiagnosticEngine &diagnostics,
                       const PackageMetadataLoadOptions &options) {
  std::map<std::string, std::set<std::string>> metadataByRoot;
  std::set<std::string> topLevelDirectories;
  for (const std::string &path : paths) {
    if (isPackageRootMetadataFile(path)) {
      metadataByRoot[""].insert(path);
    }
    const std::size_t slash = path.find('/');
    if (slash == std::string::npos || slash == 0) {
      continue;
    }
    topLevelDirectories.insert(path.substr(0, slash));
    const std::string stripped = path.substr(slash + 1);
    if (isPackageRootMetadataFile(stripped)) {
      metadataByRoot[path.substr(0, slash + 1)].insert(stripped);
    }
  }

  std::vector<std::string> completeRoots;
  for (const auto &[root, names] : metadataByRoot) {
    if (names.count("manifest.json") != 0 &&
        names.count("reflection.json") != 0 &&
        names.count("diagnostics.json") != 0) {
      completeRoots.push_back(root);
    }
  }
  if (completeRoots.size() > 1) {
    std::ostringstream roots;
    for (std::size_t index = 0; index < completeRoots.size(); ++index) {
      if (index > 0) {
        roots << ", ";
      }
      roots << zipMetadataRootLabel(completeRoots[index]);
    }
    diagnostics.error(diagnosticCode(options, "archive-ambiguous-root"),
                      "package archive contains ambiguous package metadata "
                      "roots: " +
                          roots.str(),
                      fileStartLocation(archivePath));
    return std::nullopt;
  }
  if (completeRoots.empty()) {
    return "";
  }

  const std::string prefix = completeRoots.front();
  if (prefix.empty()) {
    return prefix;
  }
  const std::string topLevel = prefix.substr(0, prefix.size() - 1);
  if (topLevelDirectories != std::set<std::string>{topLevel}) {
    return "";
  }
  if (metadataByRoot.count("") != 0) {
    diagnostics.error(diagnosticCode(options, "archive-ambiguous-root"),
                      "package archive contains ambiguous package metadata "
                      "roots: archive root, " +
                          zipMetadataRootLabel(prefix),
                      fileStartLocation(archivePath));
    return std::nullopt;
  }
  return prefix;
}

std::optional<std::map<std::string, ZipMemberRecord>>
readStoredZipMemberIndex(const std::filesystem::path &archivePath,
                         DiagnosticEngine &diagnostics,
                         const PackageMetadataLoadOptions &options) {
  std::error_code error;
  const std::uintmax_t archiveSize = std::filesystem::file_size(archivePath, error);
  if (error) {
    diagnostics.error(diagnosticCode(options, "archive-read-failed"),
                      "failed to inspect package archive: " + archivePath.string(),
                      fileStartLocation(archivePath));
    return std::nullopt;
  }

  constexpr std::uint32_t eocdSignature = 0x06054b50;
  constexpr std::uint32_t centralDirectorySignature = 0x02014b50;
  constexpr std::size_t eocdMinimumSize = 22;
  constexpr std::size_t eocdMaximumCommentSize = 0xffff;
  const std::size_t tailSize = static_cast<std::size_t>(
      std::min<std::uintmax_t>(archiveSize, eocdMinimumSize + eocdMaximumCommentSize));
  const std::uintmax_t tailOffset = archiveSize - tailSize;
  std::optional<std::string> tail = readFileSlice(archivePath, tailOffset, tailSize);
  if (!tail) {
    diagnostics.error(diagnosticCode(options, "archive-read-failed"),
                      "failed to read package archive directory: " +
                          archivePath.string(),
                      fileStartLocation(archivePath));
    return std::nullopt;
  }
  if (tail->size() < eocdMinimumSize) {
    diagnostics.error(diagnosticCode(options, "archive-invalid"),
                      "package archive is missing a ZIP central directory: " +
                          archivePath.string(),
                      fileStartLocation(archivePath));
    return std::nullopt;
  }

  std::optional<std::size_t> eocdOffsetInTail;
  for (std::size_t offset = tail->size() - eocdMinimumSize;
       offset != static_cast<std::size_t>(-1); --offset) {
    if (readLe32(*tail, offset) == eocdSignature) {
      eocdOffsetInTail = offset;
      break;
    }
    if (offset == 0) {
      break;
    }
  }
  if (!eocdOffsetInTail) {
    diagnostics.error(diagnosticCode(options, "archive-invalid"),
                      "package archive is missing a ZIP central directory: " +
                          archivePath.string(),
                      fileStartLocation(archivePath));
    return std::nullopt;
  }

  const std::size_t eocd = *eocdOffsetInTail;
  const std::uint16_t diskNumber = readLe16(*tail, eocd + 4);
  const std::uint16_t centralDirectoryDisk = readLe16(*tail, eocd + 6);
  const std::uint16_t entryCount = readLe16(*tail, eocd + 10);
  const std::uint32_t centralDirectorySize = readLe32(*tail, eocd + 12);
  const std::uint32_t centralDirectoryOffset = readLe32(*tail, eocd + 16);
  if (diskNumber != 0 || centralDirectoryDisk != 0 ||
      centralDirectoryOffset == 0xffffffff ||
      centralDirectorySize == 0xffffffff) {
    diagnostics.error(diagnosticCode(options, "archive-unsupported"),
                      "package archive uses unsupported ZIP64 or multi-disk layout: " +
                          archivePath.string(),
                      fileStartLocation(archivePath));
    return std::nullopt;
  }
  if (static_cast<std::uintmax_t>(centralDirectoryOffset) +
          centralDirectorySize >
      archiveSize) {
    diagnostics.error(diagnosticCode(options, "archive-invalid"),
                      "package archive central directory is out of bounds: " +
                          archivePath.string(),
                      fileStartLocation(archivePath));
    return std::nullopt;
  }

  std::optional<std::string> centralDirectory =
      readFileSlice(archivePath, centralDirectoryOffset, centralDirectorySize);
  if (!centralDirectory) {
    diagnostics.error(diagnosticCode(options, "archive-read-failed"),
                      "failed to read package archive central directory: " +
                          archivePath.string(),
                      fileStartLocation(archivePath));
    return std::nullopt;
  }

  std::vector<ZipMemberRecord> members;
  std::vector<std::string> memberPaths;
  std::size_t cursor = 0;
  for (std::uint16_t index = 0; index < entryCount; ++index) {
    if (cursor + 46 > centralDirectory->size() ||
        readLe32(*centralDirectory, cursor) != centralDirectorySignature) {
      diagnostics.error(diagnosticCode(options, "archive-invalid"),
                        "package archive has a malformed central directory entry: " +
                            archivePath.string(),
                        fileStartLocation(archivePath));
      return std::nullopt;
    }
    const std::uint16_t method = readLe16(*centralDirectory, cursor + 10);
    const std::uint32_t compressedSize = readLe32(*centralDirectory, cursor + 20);
    const std::uint32_t uncompressedSize = readLe32(*centralDirectory, cursor + 24);
    const std::uint16_t nameLength = readLe16(*centralDirectory, cursor + 28);
    const std::uint16_t extraLength = readLe16(*centralDirectory, cursor + 30);
    const std::uint16_t commentLength = readLe16(*centralDirectory, cursor + 32);
    const std::uint32_t localHeaderOffset =
        readLe32(*centralDirectory, cursor + 42);
    const std::size_t recordSize =
        46u + nameLength + extraLength + commentLength;
    if (cursor + recordSize > centralDirectory->size()) {
      diagnostics.error(diagnosticCode(options, "archive-invalid"),
                        "package archive has a truncated central directory entry: " +
                            archivePath.string(),
                        fileStartLocation(archivePath));
      return std::nullopt;
    }
    std::string path(centralDirectory->data() + cursor + 46, nameLength);
    cursor += recordSize;
    if (path.empty()) {
      continue;
    }
    ZipMemberRecord member;
    member.path = path;
    member.compressionMethod = method;
    member.compressedSize = compressedSize;
    member.uncompressedSize = uncompressedSize;
    member.localHeaderOffset = localHeaderOffset;
    member.directory = !path.empty() && path.back() == '/';
    if (!member.directory) {
      std::optional<std::string> normalized = normalizeZipMemberName(member.path);
      if (!normalized) {
        diagnostics.error(diagnosticCode(options, "archive-invalid-member"),
                          "package archive member is not package-relative: " +
                              member.path,
                          archiveMemberStartLocation(archivePath, member.path));
        return std::nullopt;
      }
      member.normalizedPath = std::move(*normalized);
      if (member.compressionMethod != 0) {
        diagnostics.error(diagnosticCode(options, "unsupported-compression"),
                          "package archive member uses unsupported compression "
                          "method " +
                              std::to_string(member.compressionMethod) + ": " +
                              member.path,
                          archiveMemberStartLocation(archivePath, member.path));
        return std::nullopt;
      }
      memberPaths.push_back(member.normalizedPath);
    }
    members.push_back(std::move(member));
  }

  std::optional<std::string> prefix =
      detectZipPackagePrefix(memberPaths, archivePath, diagnostics, options);
  if (!prefix) {
    return std::nullopt;
  }
  std::map<std::string, ZipMemberRecord> index;
  for (ZipMemberRecord member : members) {
    std::string normalized = member.normalizedPath;
    if (!prefix->empty()) {
      if (!normalized.starts_with(*prefix)) {
        continue;
      }
      normalized.erase(0, prefix->size());
    }
    if (normalized.empty() || normalized.ends_with('/')) {
      continue;
    }
    if (packagePathIssue(normalized) != PackagePathIssue::None) {
      diagnostics.error(diagnosticCode(options, "archive-invalid-member"),
                        "package archive member is not package-relative: " +
                            member.path,
                        archiveMemberStartLocation(archivePath, member.path));
      return std::nullopt;
    }
    if (!index.emplace(normalized, member).second) {
      diagnostics.error(diagnosticCode(options, "duplicate-archive-member"),
                        "package archive contains duplicate normalized member: " +
                            normalized,
                        archiveMemberStartLocation(archivePath, normalized));
      return std::nullopt;
    }
  }
  return index;
}

std::optional<std::string>
readStoredZipMember(const PackageSource &source, const ZipMemberRecord &member,
                    DiagnosticEngine &diagnostics,
                    const PackageMetadataLoadOptions &options) {
  if (member.compressionMethod != 0) {
    diagnostics.error(diagnosticCode(options, "unsupported-compression"),
                      "package archive member uses unsupported compression method " +
                          std::to_string(member.compressionMethod) + ": " +
                          member.path,
                      archiveMemberStartLocation(source.packagePath, member.path));
    return std::nullopt;
  }

  std::optional<std::string> localHeader =
      readFileSlice(source.packagePath, member.localHeaderOffset, 30);
  if (!localHeader || readLe32(*localHeader, 0) != 0x04034b50) {
    diagnostics.error(diagnosticCode(options, "archive-invalid"),
                      "package archive member has a malformed local header: " +
                          member.path,
                      archiveMemberStartLocation(source.packagePath, member.path));
    return std::nullopt;
  }
  const std::uint16_t nameLength = readLe16(*localHeader, 26);
  const std::uint16_t extraLength = readLe16(*localHeader, 28);
  const std::uintmax_t dataOffset =
      static_cast<std::uintmax_t>(member.localHeaderOffset) + 30u + nameLength +
      extraLength;
  std::optional<std::string> data =
      readFileSlice(source.packagePath, dataOffset, member.compressedSize);
  if (!data || data->size() != member.uncompressedSize) {
    diagnostics.error(diagnosticCode(options, "archive-read-failed"),
                      "failed to read package archive member: " + member.path,
                      archiveMemberStartLocation(source.packagePath, member.path));
    return std::nullopt;
  }
  return data;
}

std::optional<PackageSource>
loadPackageSource(const std::filesystem::path &packagePath,
                  DiagnosticEngine &diagnostics,
                  const PackageMetadataLoadOptions &options) {
  std::error_code error;
  if (!std::filesystem::exists(packagePath, error) || error) {
    diagnostics.error(diagnosticCode(options, "missing-package"),
                      "package path does not exist: " + packagePath.string());
    return std::nullopt;
  }
  if (std::filesystem::is_directory(packagePath, error) && !error) {
    PackageSource source;
    source.packagePath = packagePath;
    source.format = "directory";
    return source;
  }
  error.clear();
  if (options.allowStoredZipPackages &&
      std::filesystem::is_regular_file(packagePath, error) && !error &&
      fileHasZipSignature(packagePath)) {
    PackageSource source;
    source.packagePath = packagePath;
    source.format = "zip";
    std::optional<std::map<std::string, ZipMemberRecord>> members =
        readStoredZipMemberIndex(packagePath, diagnostics, options);
    if (!members) {
      return std::nullopt;
    }
    source.zipMembers = std::move(*members);
    return source;
  }

  diagnostics.error(
      diagnosticCode(options, "unsupported-format"),
      options.commandName +
          " currently expects a .cglb directory: " + packagePath.string());
  return std::nullopt;
}

std::optional<std::string>
validateJsonObjectText(std::string text, const SourceLocation &location,
                       std::string_view label, DiagnosticEngine &diagnostics,
                       const PackageMetadataLoadOptions &options) {
  if (!isJsonObjectDocument(text)) {
    diagnostics.error(diagnosticCode(options, "invalid-json"),
                      "package " + std::string(label) +
                          " is not a valid JSON object: " + location.file,
                      location);
    return std::nullopt;
  }
  if (const std::optional<DuplicateJsonKey> duplicate =
          findDuplicateJsonKey(text)) {
    diagnostics.error(
        diagnosticCode(options, "duplicate-key"),
        "package " + std::string(label) +
            " contains duplicate JSON object key: " + duplicate->path,
        sourceLocationForRange(std::filesystem::path(location.file), text,
                               duplicate->keyRange));
    return std::nullopt;
  }
  return text;
}

std::optional<std::string>
readJsonObjectFile(const std::filesystem::path &path, std::string_view label,
                   DiagnosticEngine &diagnostics,
                   const PackageMetadataLoadOptions &options) {
  std::error_code statusError;
  if (std::filesystem::exists(path, statusError) && !statusError &&
      !std::filesystem::is_regular_file(path, statusError)) {
    diagnostics.error(diagnosticCode(options, "invalid-root-file"),
                      "package " + std::string(label) +
                          " is not a regular file: " + path.string(),
                      fileStartLocation(path));
    return std::nullopt;
  }

  std::ifstream input(path, std::ios::binary);
  if (!input) {
    diagnostics.error(diagnosticCode(options, "read-failed"),
                      "failed to read package " + std::string(label) + " at '" +
                          path.string() + "'",
                      fileStartLocation(path));
    return std::nullopt;
  }
  std::ostringstream buffer;
  buffer << input.rdbuf();
  std::string text = buffer.str();
  return validateJsonObjectText(std::move(text), fileStartLocation(path), label,
                                diagnostics, options);
}

std::optional<std::string>
readJsonObjectFromSource(const PackageSource &source, std::string_view path,
                         std::string_view label, DiagnosticEngine &diagnostics,
                         const PackageMetadataLoadOptions &options) {
  if (source.format == "directory") {
    return readJsonObjectFile(source.packagePath / std::string(path), label,
                              diagnostics, options);
  }

  const auto member = source.zipMembers.find(std::string(path));
  if (member == source.zipMembers.end()) {
    diagnostics.error(diagnosticCode(options, "read-failed"),
                      "failed to read package " + std::string(label) + " at '" +
                          source.packagePath.string() + "!/" + std::string(path) +
                          "'",
                      sourceStartLocation(source, path));
    return std::nullopt;
  }
  std::optional<std::string> text =
      readStoredZipMember(source, member->second, diagnostics, options);
  if (!text) {
    return std::nullopt;
  }
  return validateJsonObjectText(std::move(*text), sourceStartLocation(source, path),
                                label, diagnostics, options);
}

std::optional<std::uintmax_t>
fileSizeIfRegular(const std::filesystem::path &path) {
  std::error_code error;
  if (!std::filesystem::is_regular_file(path, error) || error) {
    return std::nullopt;
  }
  const std::uintmax_t size = std::filesystem::file_size(path, error);
  if (error) {
    return std::nullopt;
  }
  return size;
}

std::optional<std::string>
fileSha256IfRegular(const std::filesystem::path &path) {
  std::error_code error;
  if (!std::filesystem::is_regular_file(path, error) || error) {
    return std::nullopt;
  }

  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return std::nullopt;
  }
  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    return std::nullopt;
  }
  return sha256(buffer.str());
}

PackageRootFileRecord rootFileRecord(const std::filesystem::path &packagePath,
                                     std::string name, std::string path) {
  const std::filesystem::path fullPath = packagePath / path;
  std::error_code error;
  PackageRootFileRecord record;
  record.name = std::move(name);
  record.path = std::move(path);
  record.location = fileStartLocation(fullPath);
  record.pathExists = std::filesystem::exists(fullPath, error) && !error;
  record.exists = std::filesystem::is_regular_file(fullPath, error) && !error;
  if (record.exists) {
    record.sizeBytes = fileSizeIfRegular(fullPath);
  }
  return record;
}

PackageRootFileRecord rootFileRecord(const PackageSource &source,
                                     std::string name, std::string path) {
  if (source.format == "directory") {
    return rootFileRecord(source.packagePath, std::move(name), std::move(path));
  }
  PackageRootFileRecord record;
  record.name = std::move(name);
  record.path = std::move(path);
  record.location = sourceStartLocation(source, record.path);
  const auto member = source.zipMembers.find(record.path);
  record.pathExists = member != source.zipMembers.end();
  record.exists = record.pathExists && !member->second.directory;
  if (record.exists) {
    record.sizeBytes = member->second.uncompressedSize;
  }
  return record;
}

PackageArtifactRecord artifactRecord(const std::filesystem::path &packagePath,
                                     std::string name, std::string path,
                                     std::optional<SourceLocation> location) {
  PackageArtifactRecord record;
  record.name = std::move(name);
  record.path = std::move(path);
  record.location = std::move(location);
  record.pathIssue = packagePathIssue(record.path);
  record.packageRelative = record.pathIssue == PackagePathIssue::None;
  if (record.packageRelative) {
    const std::filesystem::path fullPath = packagePath / record.path;
    std::error_code error;
    record.pathExists = std::filesystem::exists(fullPath, error) && !error;
    record.exists = std::filesystem::is_regular_file(fullPath, error) && !error;
    if (record.exists) {
      record.sizeBytes = fileSizeIfRegular(fullPath);
    }
  }
  return record;
}

PackageArtifactRecord artifactRecord(const PackageSource &source,
                                     std::string name, std::string path,
                                     std::optional<SourceLocation> location) {
  if (source.format == "directory") {
    return artifactRecord(source.packagePath, std::move(name), std::move(path),
                          std::move(location));
  }
  PackageArtifactRecord record;
  record.name = std::move(name);
  record.path = std::move(path);
  record.location = std::move(location);
  record.pathIssue = packagePathIssue(record.path);
  record.packageRelative = record.pathIssue == PackagePathIssue::None;
  if (record.packageRelative) {
    const auto member = source.zipMembers.find(record.path);
    record.pathExists = member != source.zipMembers.end();
    record.exists = record.pathExists && !member->second.directory;
    if (record.exists) {
      record.sizeBytes = member->second.uncompressedSize;
    }
  }
  return record;
}

void setRootFileRecordLocation(std::vector<PackageRootFileRecord> &records,
                               std::string_view name,
                               const std::filesystem::path &path,
                               std::string_view text) {
  for (PackageRootFileRecord &record : records) {
    if (record.name == name) {
      record.location =
          sourceLocationForRange(path, text, JsonRange{0, text.size()});
      return;
    }
  }
}

const PackageArtifactRecord *findArtifact(const PackageMetadata &metadata,
                                          std::string_view name) {
  for (const PackageArtifactRecord &artifact : metadata.artifacts) {
    if (artifact.name == name) {
      return &artifact;
    }
  }
  return nullptr;
}

std::optional<std::string>
readRegularTextFile(const std::filesystem::path &path) {
  std::error_code error;
  if (!std::filesystem::is_regular_file(path, error) || error) {
    return std::nullopt;
  }

  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return std::nullopt;
  }
  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    return std::nullopt;
  }
  return buffer.str();
}

std::optional<std::string> objectHashValue(std::string_view object,
                                           std::string_view key) {
  const std::optional<std::string_view> hashObject =
      findObjectMemberValue(object, key);
  if (!hashObject) {
    return std::nullopt;
  }
  return objectStringMember(*hashObject, "value");
}

std::optional<std::vector<JsonObjectMemberRange>>
collectObjectMemberRanges(std::string_view text) {
  std::vector<JsonObjectMemberRange> members;
  std::size_t position = 0;
  skipWhitespace(text, position);
  if (position >= text.size() || text[position] != '{') {
    return std::nullopt;
  }
  ++position;
  skipWhitespace(text, position);
  if (position < text.size() && text[position] == '}') {
    ++position;
    skipWhitespace(text, position);
    return position == text.size()
               ? std::optional<std::vector<JsonObjectMemberRange>>(
                     std::move(members))
               : std::nullopt;
  }

  while (position < text.size()) {
    std::string key;
    if (!parseJsonString(text, position, key)) {
      return std::nullopt;
    }
    skipWhitespace(text, position);
    if (position >= text.size() || text[position] != ':') {
      return std::nullopt;
    }
    ++position;
    skipWhitespace(text, position);
    const std::size_t valueBegin = position;
    if (!skipJsonValue(text, position)) {
      return std::nullopt;
    }
    members.push_back({std::move(key), JsonRange{valueBegin, position}});
    skipWhitespace(text, position);
    if (position < text.size() && text[position] == ',') {
      ++position;
      skipWhitespace(text, position);
      continue;
    }
    if (position < text.size() && text[position] == '}') {
      ++position;
      skipWhitespace(text, position);
      return position == text.size()
                 ? std::optional<std::vector<JsonObjectMemberRange>>(
                       std::move(members))
                 : std::nullopt;
    }
    return std::nullopt;
  }
  return std::nullopt;
}

std::optional<std::vector<JsonRange>>
collectArrayElementRanges(std::string_view text) {
  std::vector<JsonRange> elements;
  std::size_t position = 0;
  skipWhitespace(text, position);
  if (position >= text.size() || text[position] != '[') {
    return std::nullopt;
  }
  ++position;
  skipWhitespace(text, position);
  if (position < text.size() && text[position] == ']') {
    ++position;
    skipWhitespace(text, position);
    return position == text.size()
               ? std::optional<std::vector<JsonRange>>(std::move(elements))
               : std::nullopt;
  }

  while (position < text.size()) {
    const std::size_t elementBegin = position;
    if (!skipJsonValue(text, position)) {
      return std::nullopt;
    }
    elements.push_back(JsonRange{elementBegin, position});
    skipWhitespace(text, position);
    if (position < text.size() && text[position] == ',') {
      ++position;
      skipWhitespace(text, position);
      continue;
    }
    if (position < text.size() && text[position] == ']') {
      ++position;
      skipWhitespace(text, position);
      return position == text.size()
                 ? std::optional<std::vector<JsonRange>>(std::move(elements))
                 : std::nullopt;
    }
    return std::nullopt;
  }
  return std::nullopt;
}

std::optional<std::string> optionalStringMemberValue(std::string_view object,
                                                     std::string_view key) {
  const std::optional<StringMember> member = findStringMemberRecord(object, key);
  if (!member) {
    return std::nullopt;
  }
  return member->value;
}

std::string stringMemberValueOrEmpty(std::string_view object,
                                     std::string_view key) {
  const std::optional<std::string> value = optionalStringMemberValue(object, key);
  return value.value_or(std::string());
}

std::string canonicalMemberJsonOrDefault(std::string_view object,
                                         std::string_view key,
                                         std::string_view defaultValue) {
  const std::optional<std::string_view> value =
      findObjectMemberValue(object, key);
  if (!value) {
    return std::string(defaultValue);
  }
  return canonicalJson(*value);
}

std::vector<std::string> stringArrayMemberValues(std::string_view object,
                                                 std::string_view key) {
  const std::optional<std::string_view> value =
      findObjectMemberValue(object, key);
  if (!value) {
    return {};
  }

  const std::optional<std::vector<JsonRange>> elementRanges =
      collectArrayElementRanges(*value);
  if (!elementRanges) {
    return {};
  }

  std::vector<std::string> values;
  for (const JsonRange &elementRange : *elementRanges) {
    const std::string_view element(
        value->data() + elementRange.begin,
        elementRange.end - elementRange.begin);
    std::string parsed;
    std::size_t position = 0;
    if (!parseJsonString(element, position, parsed)) {
      continue;
    }
    skipWhitespace(element, position);
    if (position == element.size()) {
      values.push_back(std::move(parsed));
    }
  }
  return values;
}

void collectReflectionResources(
    const std::filesystem::path &reflectionPath, std::string_view reflection,
    std::vector<PackageReflectionResourceRecord> &resourcesOut) {
  const std::optional<JsonRange> resourcesRange =
      findObjectMember(reflection, "resources");
  if (!resourcesRange) {
    return;
  }
  const std::string_view resourcesArray(
      reflection.data() + resourcesRange->begin,
      resourcesRange->end - resourcesRange->begin);
  const std::optional<std::vector<JsonRange>> elementRanges =
      collectArrayElementRanges(resourcesArray);
  if (!elementRanges) {
    return;
  }

  for (const JsonRange &elementRange : *elementRanges) {
    const JsonRange absoluteRange{
        resourcesRange->begin + elementRange.begin,
        resourcesRange->begin + elementRange.end};
    const std::string_view resourceObject(
        reflection.data() + absoluteRange.begin,
        absoluteRange.end - absoluteRange.begin);

    PackageReflectionResourceRecord record;
    record.location =
        sourceLocationForRange(reflectionPath, reflection, absoluteRange);
    record.stage = stringMemberValueOrEmpty(resourceObject, "stage");
    record.name = stringMemberValueOrEmpty(resourceObject, "name");
    record.kind = stringMemberValueOrEmpty(resourceObject, "kind");
    record.type = stringMemberValueOrEmpty(resourceObject, "type");
    record.set = objectUnsignedMember(resourceObject, "set");
    record.binding = objectUnsignedMember(resourceObject, "binding");
    record.addressSpace =
        optionalStringMemberValue(resourceObject, "addressSpace");
    record.storageImageFormat =
        optionalStringMemberValue(resourceObject, "storageImageFormat");
    record.storageImageAccess =
        optionalStringMemberValue(resourceObject, "storageImageAccess");
    record.arrayElementCount =
        objectUnsignedMember(resourceObject, "arrayElementCount");
    record.arrayDimensionsJson =
        canonicalMemberJsonOrDefault(resourceObject, "arrayDimensions", "[]");
    resourcesOut.push_back(std::move(record));
  }
}

void collectReflectionTargetResourceBindings(
    const std::filesystem::path &reflectionPath, std::string_view reflection,
    std::vector<PackageReflectionTargetResourceBindingRecord> &bindingsOut) {
  const std::optional<JsonRange> bindingsRange =
      findObjectMember(reflection, "targetResourceBindings");
  if (!bindingsRange) {
    return;
  }
  const std::string_view bindingsArray(
      reflection.data() + bindingsRange->begin,
      bindingsRange->end - bindingsRange->begin);
  const std::optional<std::vector<JsonRange>> elementRanges =
      collectArrayElementRanges(bindingsArray);
  if (!elementRanges) {
    return;
  }

  for (const JsonRange &elementRange : *elementRanges) {
    const JsonRange absoluteRange{
        bindingsRange->begin + elementRange.begin,
        bindingsRange->begin + elementRange.end};
    const std::string_view bindingObject(
        reflection.data() + absoluteRange.begin,
        absoluteRange.end - absoluteRange.begin);

    PackageReflectionTargetResourceBindingRecord record;
    record.location =
        sourceLocationForRange(reflectionPath, reflection, absoluteRange);
    record.target = stringMemberValueOrEmpty(bindingObject, "target");
    record.stage = stringMemberValueOrEmpty(bindingObject, "stage");
    record.entryPoint = stringMemberValueOrEmpty(bindingObject, "entryPoint");
    record.name = stringMemberValueOrEmpty(bindingObject, "name");
    record.kind = stringMemberValueOrEmpty(bindingObject, "kind");
    record.sourceType = stringMemberValueOrEmpty(bindingObject, "sourceType");
    record.bindingClass =
        optionalStringMemberValue(bindingObject, "bindingClass");
    record.descriptorType =
        optionalStringMemberValue(bindingObject, "descriptorType");
    record.set = objectUnsignedMember(bindingObject, "set");
    record.binding = objectUnsignedMember(bindingObject, "binding");
    record.argumentIndex =
        objectUnsignedMember(bindingObject, "argumentIndex");
    record.addressSpace =
        optionalStringMemberValue(bindingObject, "addressSpace");
    record.storageImageFormat =
        optionalStringMemberValue(bindingObject, "storageImageFormat");
    record.storageImageAccess =
        optionalStringMemberValue(bindingObject, "storageImageAccess");
    record.arrayElementCount =
        objectUnsignedMember(bindingObject, "arrayElementCount");
    if (const std::optional<JsonRange> evidenceIdRange =
            findObjectMember(bindingObject, "evidenceId")) {
      record.evidenceIdLocation = sourceLocationForRange(
          reflectionPath, reflection,
          JsonRange{absoluteRange.begin + evidenceIdRange->begin,
                    absoluteRange.begin + evidenceIdRange->end});
    }
    record.evidenceId = optionalStringMemberValue(bindingObject, "evidenceId");
    record.abiJson = canonicalMemberJsonOrDefault(bindingObject, "abi", "null");
    record.arrayDimensionsJson =
        canonicalMemberJsonOrDefault(bindingObject, "arrayDimensions", "[]");
    bindingsOut.push_back(std::move(record));
  }
}

void collectReflectionTargetFeatures(
    const std::filesystem::path &reflectionPath, std::string_view reflection,
    std::vector<PackageReflectionTargetFeatureRecord> &featuresOut) {
  const std::optional<JsonRange> featuresRange =
      findObjectMember(reflection, "targetFeatures");
  if (!featuresRange) {
    return;
  }
  const std::string_view featuresArray(
      reflection.data() + featuresRange->begin,
      featuresRange->end - featuresRange->begin);
  const std::optional<std::vector<JsonRange>> elementRanges =
      collectArrayElementRanges(featuresArray);
  if (!elementRanges) {
    return;
  }

  for (const JsonRange &elementRange : *elementRanges) {
    const JsonRange absoluteRange{
        featuresRange->begin + elementRange.begin,
        featuresRange->begin + elementRange.end};
    const std::string_view featureObject(
        reflection.data() + absoluteRange.begin,
        absoluteRange.end - absoluteRange.begin);

    PackageReflectionTargetFeatureRecord record;
    record.location =
        sourceLocationForRange(reflectionPath, reflection, absoluteRange);
    record.target = stringMemberValueOrEmpty(featureObject, "target");
    record.kind = stringMemberValueOrEmpty(featureObject, "kind");
    record.name = stringMemberValueOrEmpty(featureObject, "name");
    record.evidenceIds = stringArrayMemberValues(featureObject, "evidenceIds");
    featuresOut.push_back(std::move(record));
  }
}

bool hasMember(const std::vector<JsonObjectMemberRange> &members,
               std::string_view name) {
  return std::any_of(
      members.begin(), members.end(),
      [&](const JsonObjectMemberRange &member) { return member.name == name; });
}

bool membersAreAllowed(const std::vector<JsonObjectMemberRange> &members,
                       const std::vector<std::string_view> &allowed) {
  for (const JsonObjectMemberRange &member : members) {
    if (std::find(allowed.begin(), allowed.end(), member.name) ==
        allowed.end()) {
      return false;
    }
  }
  return true;
}

bool hasAllMembers(const std::vector<JsonObjectMemberRange> &members,
                   const std::vector<std::string_view> &required) {
  for (std::string_view name : required) {
    if (!hasMember(members, name)) {
      return false;
    }
  }
  return true;
}

bool isKnownPackageArtifactRequirementMode(std::string_view mode) {
  return mode == "native" || mode == "source-package";
}

bool isKnownPackageArtifactRequirementPathKey(std::string_view artifactKey) {
  return artifactKey == "backendSource" || artifactKey == "backendAssembly" ||
         artifactKey == "intermediate" || artifactKey == "nativeBinary";
}

bool parseJsonStringValue(std::string_view text, std::string &out) {
  std::size_t position = 0;
  skipWhitespace(text, position);
  if (!parseJsonString(text, position, out)) {
    return false;
  }
  skipWhitespace(text, position);
  return position == text.size();
}

bool isKnownOptionalNativeToolStatus(std::string_view status) {
  return status == "available" || status == "missing" ||
         status == "not-required";
}

bool isKnownToolRequirementKind(std::string_view kind) {
  return kind == "native-tool" || kind == "toolchain" ||
         kind == "validation";
}

bool isToolRequirementIdNameChar(char ch) {
  const unsigned char value = static_cast<unsigned char>(ch);
  return std::isalnum(value) || ch == '_' || ch == '.' || ch == '-';
}

std::optional<std::string_view>
toolRequirementTarget(std::string_view toolId) {
  const std::size_t firstDot = toolId.find('.');
  if (firstDot == std::string_view::npos || firstDot == 0) {
    return std::nullopt;
  }
  const std::size_t secondDot = toolId.find('.', firstDot + 1);
  if (secondDot == std::string_view::npos || secondDot == firstDot + 1 ||
      secondDot + 1 >= toolId.size()) {
    return std::nullopt;
  }

  const std::string_view target = toolId.substr(0, firstDot);
  const std::string_view kind =
      toolId.substr(firstDot + 1, secondDot - firstDot - 1);
  const std::string_view name = toolId.substr(secondDot + 1);
  if (!isKnownPackageTargetName(target) || !isKnownToolRequirementKind(kind) ||
      name.empty()) {
    return std::nullopt;
  }
  for (char ch : name) {
    if (!isToolRequirementIdNameChar(ch)) {
      return std::nullopt;
    }
  }
  return target;
}

bool toolRequirementIdMatchesTarget(std::string_view toolId,
                                    std::string_view target) {
  const std::optional<std::string_view> idTarget =
      toolRequirementTarget(toolId);
  return idTarget && *idTarget == target;
}

bool hasPrefix(std::string_view value, std::string_view prefix) {
  return value.size() >= prefix.size() &&
         value.substr(0, prefix.size()) == prefix;
}

std::string toolRequirementEvidenceId(std::string_view target,
                                      std::string_view status,
                                      std::string_view toolId) {
  const std::size_t firstDot = toolId.find('.');
  const std::size_t secondDot = firstDot == std::string_view::npos
                                    ? std::string_view::npos
                                    : toolId.find('.', firstDot + 1);
  if (firstDot == std::string_view::npos ||
      secondDot == std::string_view::npos || secondDot + 1 >= toolId.size()) {
    return {};
  }
  return "target-legalization.v1." + std::string(target) +
         ".tool-requirement." + std::string(status) + "." +
         std::string(toolId.substr(firstDot + 1, secondDot - firstDot - 1)) +
         "." + std::string(toolId.substr(secondDot + 1));
}

std::vector<std::string> expectedToolRequirementEvidenceIds(
    std::string_view target, const std::vector<std::string> &requiredToolIds,
    const std::vector<std::string> &missingToolIds) {
  std::vector<std::string> expected;
  const std::string state =
      requiredToolIds.empty() && missingToolIds.empty() ? "empty" : "present";
  expected.push_back("target-legalization.v1." + std::string(target) +
                     ".tool-requirements." + state);
  for (const std::string &toolId : requiredToolIds) {
    expected.push_back(toolRequirementEvidenceId(target, "required", toolId));
  }
  for (const std::string &toolId : missingToolIds) {
    expected.push_back(toolRequirementEvidenceId(target, "missing", toolId));
  }
  return expected;
}

std::string expectedOptionalNativeToolStatus(
    std::string_view packageMode, const std::vector<std::string> &requiredToolIds,
    const std::vector<std::string> &missingToolIds) {
  if (packageMode != "source-package") {
    return "not-required";
  }
  if (!missingToolIds.empty()) {
    return "missing";
  }
  if (!requiredToolIds.empty()) {
    return "available";
  }
  return "not-required";
}

bool parseUniqueStringArrayMember(
    const std::filesystem::path &manifestPath, std::string_view manifest,
    std::string_view object, JsonRange objectRange, std::string_view key,
    bool allowEmpty, std::string_view emptyMessage,
    std::string_view invalidMessage, const SourceLocation &fallbackLocation,
    DiagnosticEngine &diagnostics, const PackageMetadataLoadOptions &options,
    std::optional<SourceLocation> &locationOut,
    std::vector<std::string> &valuesOut) {
  const std::optional<JsonRange> arrayRange = findObjectMember(object, key);
  if (!arrayRange) {
    diagnostics.error(diagnosticCode(options, "invalid-manifest"),
                      std::string(invalidMessage), fallbackLocation);
    return false;
  }
  locationOut = sourceLocationForRange(
      manifestPath, manifest, offsetRange(*arrayRange, objectRange.begin));
  const std::string_view arrayText(object.data() + arrayRange->begin,
                                   arrayRange->end - arrayRange->begin);
  const std::optional<std::vector<JsonRange>> elementRanges =
      collectArrayElementRanges(arrayText);
  if (!elementRanges || (!allowEmpty && elementRanges->empty())) {
    diagnostics.error(diagnosticCode(options, "invalid-manifest"),
                      std::string(emptyMessage),
                      locationOut.value_or(fallbackLocation));
    return false;
  }

  std::vector<std::string> seen;
  for (const JsonRange &elementRange : *elementRanges) {
    std::string value;
    const std::string_view elementValue(
        arrayText.data() + elementRange.begin,
        elementRange.end - elementRange.begin);
    if (!parseJsonStringValue(elementValue, value) || value.empty() ||
        std::find(seen.begin(), seen.end(), value) != seen.end()) {
      diagnostics.error(
          diagnosticCode(options, "invalid-manifest"),
          std::string(invalidMessage),
          sourceLocationForRange(
              manifestPath, manifest,
              JsonRange{objectRange.begin + arrayRange->begin +
                            elementRange.begin,
                        objectRange.begin + arrayRange->begin +
                            elementRange.end}));
      return false;
    }
    seen.push_back(value);
    valuesOut.push_back(std::move(value));
  }
  return true;
}

bool parsePackageArtifactRequirements(
    const std::filesystem::path &manifestPath, std::string_view manifest,
    DiagnosticEngine &diagnostics, const PackageMetadataLoadOptions &options,
    std::optional<PackageArtifactRequirementsRecord> &requirementsOut) {
  const std::optional<JsonRange> requirementsRange =
      findObjectMember(manifest, kPackageArtifactRequirements);
  if (!requirementsRange) {
    return true;
  }

  PackageArtifactRequirementsRecord requirements;
  requirements.location =
      sourceLocationForRange(manifestPath, manifest, *requirementsRange);
  const std::string_view requirementsObject(
      manifest.data() + requirementsRange->begin,
      requirementsRange->end - requirementsRange->begin);
  const std::optional<std::vector<JsonObjectMemberRange>> members =
      collectObjectMemberRanges(requirementsObject);
  if (!members ||
      !membersAreAllowed(
          *members, {"target", "packageMode", "requiredPathArtifacts",
                     "requiresNativeBinaryStatus", "allowsPlannedNativeBinary",
                     "allowsPlannedNativeSourceEvidence", "evidenceIds"}) ||
      !hasAllMembers(*members,
                     {"target", "packageMode", "requiredPathArtifacts",
                      "requiresNativeBinaryStatus", "allowsPlannedNativeBinary",
                      "allowsPlannedNativeSourceEvidence"})) {
    diagnostics.error(diagnosticCode(options, "invalid-manifest"),
                      "package manifest packageArtifactRequirements is invalid",
                      requirements.location);
    return false;
  }

  const std::optional<StringMember> target =
      findStringMemberRecord(requirementsObject, "target");
  const std::optional<StringMember> packageMode =
      findStringMemberRecord(requirementsObject, "packageMode");
  const std::optional<bool> requiresNativeBinaryStatus =
      objectBoolMember(requirementsObject, "requiresNativeBinaryStatus");
  const std::optional<bool> allowsPlannedNativeBinary =
      objectBoolMember(requirementsObject, "allowsPlannedNativeBinary");
  const std::optional<bool> allowsPlannedNativeSourceEvidence =
      objectBoolMember(requirementsObject, "allowsPlannedNativeSourceEvidence");
  if (!target || !packageMode ||
      !isKnownPackageArtifactRequirementMode(packageMode->value) ||
      !requiresNativeBinaryStatus || !allowsPlannedNativeBinary ||
      !allowsPlannedNativeSourceEvidence ||
      (*allowsPlannedNativeSourceEvidence && !*allowsPlannedNativeBinary)) {
    diagnostics.error(diagnosticCode(options, "invalid-manifest"),
                      "package manifest packageArtifactRequirements is invalid",
                      requirements.location);
    return false;
  }

  requirements.target = target->value;
  requirements.packageMode = packageMode->value;
  requirements.targetLocation = sourceLocationForRange(
      manifestPath, manifest,
      offsetRange(target->valueRange, requirementsRange->begin));
  requirements.packageModeLocation = sourceLocationForRange(
      manifestPath, manifest,
      offsetRange(packageMode->valueRange, requirementsRange->begin));
  requirements.requiresNativeBinaryStatus = *requiresNativeBinaryStatus;
  requirements.allowsPlannedNativeBinary = *allowsPlannedNativeBinary;
  requirements.allowsPlannedNativeSourceEvidence =
      *allowsPlannedNativeSourceEvidence;

  const std::optional<JsonRange> artifactsRange =
      findObjectMember(requirementsObject, "requiredPathArtifacts");
  if (!artifactsRange) {
    diagnostics.error(diagnosticCode(options, "invalid-manifest"),
                      "package manifest packageArtifactRequirements is invalid",
                      requirements.location);
    return false;
  }
  requirements.requiredPathArtifactsLocation = sourceLocationForRange(
      manifestPath, manifest,
      offsetRange(*artifactsRange, requirementsRange->begin));
  const std::string_view artifactArray(
      requirementsObject.data() + artifactsRange->begin,
      artifactsRange->end - artifactsRange->begin);
  const std::optional<std::vector<JsonRange>> artifactRanges =
      collectArrayElementRanges(artifactArray);
  if (!artifactRanges || artifactRanges->empty()) {
    diagnostics.error(
        diagnosticCode(options, "invalid-manifest"),
        "package manifest packageArtifactRequirements.requiredPathArtifacts "
        "must contain at least one artifact key",
        requirements.requiredPathArtifactsLocation.value_or(
            requirements.location));
    return false;
  }

  std::vector<std::string> seenArtifactKeys;
  for (const JsonRange &artifactRange : *artifactRanges) {
    std::string artifactKey;
    const std::string_view artifactValue(
        artifactArray.data() + artifactRange.begin,
        artifactRange.end - artifactRange.begin);
    if (!parseJsonStringValue(artifactValue, artifactKey) ||
        !isKnownPackageArtifactRequirementPathKey(artifactKey) ||
        std::find(seenArtifactKeys.begin(), seenArtifactKeys.end(),
                  artifactKey) != seenArtifactKeys.end()) {
      diagnostics.error(
          diagnosticCode(options, "invalid-manifest"),
          "package manifest packageArtifactRequirements.requiredPathArtifacts "
          "must contain known unique path artifact keys",
          sourceLocationForRange(
              manifestPath, manifest,
              JsonRange{requirementsRange->begin + artifactsRange->begin +
                            artifactRange.begin,
                        requirementsRange->begin + artifactsRange->begin +
                            artifactRange.end}));
      return false;
    }
    seenArtifactKeys.push_back(artifactKey);
    requirements.requiredPathArtifacts.push_back(
        {std::move(artifactKey),
         sourceLocationForRange(
             manifestPath, manifest,
             JsonRange{requirementsRange->begin + artifactsRange->begin +
                           artifactRange.begin,
                       requirementsRange->begin + artifactsRange->begin +
                           artifactRange.end})});
  }

  const std::optional<JsonRange> evidenceIdsRange =
      findObjectMember(requirementsObject, "evidenceIds");
  if (evidenceIdsRange) {
    requirements.evidenceIdsLocation = sourceLocationForRange(
        manifestPath, manifest,
        offsetRange(*evidenceIdsRange, requirementsRange->begin));
    const std::string_view evidenceIdsArray(
        requirementsObject.data() + evidenceIdsRange->begin,
        evidenceIdsRange->end - evidenceIdsRange->begin);
    const std::optional<std::vector<JsonRange>> evidenceIdRanges =
        collectArrayElementRanges(evidenceIdsArray);
    if (!evidenceIdRanges || evidenceIdRanges->empty()) {
      diagnostics.error(
          diagnosticCode(options, "invalid-manifest"),
          "package manifest packageArtifactRequirements.evidenceIds "
          "must contain at least one evidence ID",
          requirements.evidenceIdsLocation.value_or(requirements.location));
      return false;
    }

    std::vector<std::string> seenEvidenceIds;
    for (const JsonRange &evidenceIdRange : *evidenceIdRanges) {
      std::string evidenceId;
      const std::string_view evidenceIdValue(
          evidenceIdsArray.data() + evidenceIdRange.begin,
          evidenceIdRange.end - evidenceIdRange.begin);
      if (!parseJsonStringValue(evidenceIdValue, evidenceId) ||
          evidenceId.empty() ||
          std::find(seenEvidenceIds.begin(), seenEvidenceIds.end(),
                    evidenceId) != seenEvidenceIds.end()) {
        diagnostics.error(
            diagnosticCode(options, "invalid-manifest"),
            "package manifest packageArtifactRequirements.evidenceIds "
            "must contain non-empty unique evidence IDs",
            sourceLocationForRange(
                manifestPath, manifest,
                JsonRange{requirementsRange->begin + evidenceIdsRange->begin +
                              evidenceIdRange.begin,
                          requirementsRange->begin + evidenceIdsRange->begin +
                              evidenceIdRange.end}));
        return false;
      }
      seenEvidenceIds.push_back(evidenceId);
      requirements.evidenceIds.push_back(std::move(evidenceId));
    }
  }

  requirementsOut = std::move(requirements);
  return true;
}

bool parseTargetLegalizationToolRequirements(
    const std::filesystem::path &manifestPath, std::string_view manifest,
    DiagnosticEngine &diagnostics, const PackageMetadataLoadOptions &options,
    std::optional<PackageTargetLegalizationToolRequirementsRecord>
        &requirementsOut) {
  const std::optional<JsonRange> requirementsRange =
      findObjectMember(manifest, kTargetLegalizationToolRequirements);
  if (!requirementsRange) {
    return true;
  }

  PackageTargetLegalizationToolRequirementsRecord requirements;
  requirements.location =
      sourceLocationForRange(manifestPath, manifest, *requirementsRange);
  const std::string_view requirementsObject(
      manifest.data() + requirementsRange->begin,
      requirementsRange->end - requirementsRange->begin);
  const std::optional<std::vector<JsonObjectMemberRange>> members =
      collectObjectMemberRanges(requirementsObject);
  if (!members ||
      !membersAreAllowed(
          *members, {"target", "packageMode", "requiredToolCount",
                     "missingToolCount", "requiredToolIds", "missingToolIds",
                     "optionalNativeToolMissing", "optionalNativeToolStatus",
                     "toolRequirementEvidenceIds"}) ||
      !hasAllMembers(
          *members, {"target", "packageMode", "requiredToolCount",
                     "missingToolCount", "requiredToolIds", "missingToolIds",
                     "optionalNativeToolMissing", "optionalNativeToolStatus",
                     "toolRequirementEvidenceIds"})) {
    diagnostics.error(
        diagnosticCode(options, "invalid-manifest"),
        "package manifest targetLegalizationToolRequirements is invalid",
        requirements.location);
    return false;
  }

  const std::optional<StringMember> target =
      findStringMemberRecord(requirementsObject, "target");
  const std::optional<StringMember> packageMode =
      findStringMemberRecord(requirementsObject, "packageMode");
  const std::optional<std::uintmax_t> requiredToolCount =
      objectUnsignedMember(requirementsObject, "requiredToolCount");
  const std::optional<std::uintmax_t> missingToolCount =
      objectUnsignedMember(requirementsObject, "missingToolCount");
  const std::optional<bool> optionalNativeToolMissing =
      objectBoolMember(requirementsObject, "optionalNativeToolMissing");
  const std::optional<std::string> optionalNativeToolStatus =
      objectStringMember(requirementsObject, "optionalNativeToolStatus");
  if (!target || !isKnownPackageTargetName(target->value) || !packageMode ||
      !isKnownPackageArtifactRequirementMode(packageMode->value) ||
      !requiredToolCount || !missingToolCount ||
      !optionalNativeToolMissing || !optionalNativeToolStatus ||
      !isKnownOptionalNativeToolStatus(*optionalNativeToolStatus)) {
    diagnostics.error(
        diagnosticCode(options, "invalid-manifest"),
        "package manifest targetLegalizationToolRequirements is invalid",
        requirements.location);
    return false;
  }

  requirements.target = target->value;
  requirements.packageMode = packageMode->value;
  requirements.targetLocation = sourceLocationForRange(
      manifestPath, manifest,
      offsetRange(target->valueRange, requirementsRange->begin));
  requirements.packageModeLocation = sourceLocationForRange(
      manifestPath, manifest,
      offsetRange(packageMode->valueRange, requirementsRange->begin));
  requirements.requiredToolCount = *requiredToolCount;
  requirements.missingToolCount = *missingToolCount;
  requirements.optionalNativeToolMissing = *optionalNativeToolMissing;
  requirements.optionalNativeToolStatus = *optionalNativeToolStatus;

  if (!parseUniqueStringArrayMember(
          manifestPath, manifest, requirementsObject, *requirementsRange,
          "requiredToolIds", true,
          "package manifest "
          "targetLegalizationToolRequirements.requiredToolIds is invalid",
          "package manifest "
          "targetLegalizationToolRequirements.requiredToolIds must contain "
          "non-empty unique tool IDs",
          requirements.location, diagnostics, options,
          requirements.requiredToolIdsLocation,
          requirements.requiredToolIds) ||
      !parseUniqueStringArrayMember(
          manifestPath, manifest, requirementsObject, *requirementsRange,
          "missingToolIds", true,
          "package manifest "
          "targetLegalizationToolRequirements.missingToolIds is invalid",
          "package manifest "
          "targetLegalizationToolRequirements.missingToolIds must contain "
          "non-empty unique tool IDs",
          requirements.location, diagnostics, options,
          requirements.missingToolIdsLocation, requirements.missingToolIds) ||
      !parseUniqueStringArrayMember(
          manifestPath, manifest, requirementsObject, *requirementsRange,
          "toolRequirementEvidenceIds", false,
          "package manifest targetLegalizationToolRequirements."
          "toolRequirementEvidenceIds must contain at least one evidence ID",
          "package manifest targetLegalizationToolRequirements."
          "toolRequirementEvidenceIds must contain non-empty unique evidence "
          "IDs",
          requirements.location, diagnostics, options,
          requirements.toolRequirementEvidenceIdsLocation,
          requirements.toolRequirementEvidenceIds)) {
    return false;
  }

  if (requirements.requiredToolCount != requirements.requiredToolIds.size() ||
      requirements.missingToolCount != requirements.missingToolIds.size()) {
    diagnostics.error(
        diagnosticCode(options, "invalid-manifest"),
        "package manifest targetLegalizationToolRequirements tool counts "
        "must match tool ID arrays",
        requirements.location);
    return false;
  }

  for (const std::string &toolId : requirements.requiredToolIds) {
    if (!toolRequirementIdMatchesTarget(toolId, requirements.target)) {
      diagnostics.error(
          diagnosticCode(options, "invalid-manifest"),
          "package manifest targetLegalizationToolRequirements.requiredToolIds "
          "must contain tool IDs for its target",
          requirements.requiredToolIdsLocation.value_or(requirements.location));
      return false;
    }
  }
  for (const std::string &toolId : requirements.missingToolIds) {
    if (!toolRequirementIdMatchesTarget(toolId, requirements.target) ||
        std::find(requirements.requiredToolIds.begin(),
                  requirements.requiredToolIds.end(),
                  toolId) == requirements.requiredToolIds.end()) {
      diagnostics.error(
          diagnosticCode(options, "invalid-manifest"),
          "package manifest targetLegalizationToolRequirements.missingToolIds "
          "must be a subset of requiredToolIds for its target",
          requirements.missingToolIdsLocation.value_or(requirements.location));
      return false;
    }
  }

  const bool expectedOptionalMissing =
      requirements.packageMode == "source-package" &&
      !requirements.missingToolIds.empty();
  const std::string expectedOptionalStatus = expectedOptionalNativeToolStatus(
      requirements.packageMode, requirements.requiredToolIds,
      requirements.missingToolIds);
  if (requirements.optionalNativeToolMissing != expectedOptionalMissing ||
      requirements.optionalNativeToolStatus != expectedOptionalStatus) {
    diagnostics.error(
        diagnosticCode(options, "invalid-manifest"),
        "package manifest targetLegalizationToolRequirements optional native "
        "tool status is inconsistent",
        requirements.location);
    return false;
  }

  const std::string expectedEvidencePrefix =
      "target-legalization.v1." + requirements.target + ".";
  for (const std::string &evidenceId :
       requirements.toolRequirementEvidenceIds) {
    if (!hasPrefix(evidenceId, expectedEvidencePrefix)) {
      diagnostics.error(
          diagnosticCode(options, "invalid-manifest"),
          "package manifest targetLegalizationToolRequirements."
          "toolRequirementEvidenceIds must match its target",
          requirements.toolRequirementEvidenceIdsLocation.value_or(
              requirements.location));
      return false;
    }
  }
  if (requirements.toolRequirementEvidenceIds !=
      expectedToolRequirementEvidenceIds(
          requirements.target, requirements.requiredToolIds,
          requirements.missingToolIds)) {
    diagnostics.error(
        diagnosticCode(options, "invalid-manifest"),
        "package manifest targetLegalizationToolRequirements."
        "toolRequirementEvidenceIds must match recorded tool IDs",
        requirements.toolRequirementEvidenceIdsLocation.value_or(
            requirements.location));
    return false;
  }

  requirementsOut = std::move(requirements);
  return true;
}

bool validatePackageArtifactRequirementsManifestTarget(
    const PackageMetadata &metadata, DiagnosticEngine &diagnostics,
    const PackageMetadataLoadOptions &options) {
  if (!metadata.artifactRequirements) {
    return true;
  }

  const PackageArtifactRequirementsRecord &requirements =
      *metadata.artifactRequirements;
  if (requirements.target != metadata.target) {
    diagnostics.error(
        diagnosticCode(options, "invalid-manifest"),
        "package manifest packageArtifactRequirements target must match "
        "manifest target",
        requirements.targetLocation.value_or(requirements.location));
    return false;
  }
  return true;
}

bool validateTargetLegalizationToolRequirementsManifestTarget(
    const PackageMetadata &metadata, DiagnosticEngine &diagnostics,
    const PackageMetadataLoadOptions &options) {
  if (!metadata.targetLegalizationToolRequirements) {
    return true;
  }

  const PackageTargetLegalizationToolRequirementsRecord &requirements =
      *metadata.targetLegalizationToolRequirements;
  if (requirements.target != metadata.target) {
    diagnostics.error(
        diagnosticCode(options, "invalid-manifest"),
        "package manifest targetLegalizationToolRequirements target must match "
        "manifest target",
        requirements.targetLocation.value_or(requirements.location));
    return false;
  }

  if (!metadata.artifactRequirements) {
    diagnostics.error(
        diagnosticCode(options, "invalid-manifest"),
        "package manifest targetLegalizationToolRequirements requires "
        "packageArtifactRequirements",
        requirements.location);
    return false;
  }

  if (requirements.packageMode != metadata.artifactRequirements->packageMode) {
    diagnostics.error(
        diagnosticCode(options, "invalid-manifest"),
        "package manifest targetLegalizationToolRequirements.packageMode must "
        "match packageArtifactRequirements.packageMode",
        requirements.packageModeLocation.value_or(requirements.location));
    return false;
  }
  return true;
}

bool isLowercaseSha256(std::string_view value) {
  if (value.size() != 64) {
    return false;
  }
  for (char ch : value) {
    const bool digit = ch >= '0' && ch <= '9';
    const bool lowerHex = ch >= 'a' && ch <= 'f';
    if (!digit && !lowerHex) {
      return false;
    }
  }
  return true;
}

bool validateHashObject(std::string_view object, std::string_view key) {
  const std::optional<std::string_view> hashObject =
      findObjectMemberValue(object, key);
  if (!hashObject) {
    return false;
  }
  const std::optional<std::vector<JsonObjectMemberRange>> members =
      collectObjectMemberRanges(*hashObject);
  if (!members || !membersAreAllowed(*members, {"algorithm", "value"}) ||
      !hasAllMembers(*members, {"algorithm", "value"})) {
    return false;
  }
  const std::optional<std::string> algorithm =
      objectStringMember(*hashObject, "algorithm");
  const std::optional<std::string> value =
      objectStringMember(*hashObject, "value");
  return algorithm && *algorithm == "sha256" && value &&
         isLowercaseSha256(*value);
}

bool isKnownNativeArtifactBinaryKind(std::string_view binaryKind) {
  return binaryKind == "metal.metallib" ||
         binaryKind == "vulkan.spirv-module" || binaryKind == "directx.dxil" ||
         binaryKind == "directx.dxbc" || binaryKind == "opengl.source" ||
         binaryKind == "opengl.package";
}

bool isKnownNativeOptimizationLevel(std::string_view level) {
  return level == "none" || level == "debug" || level == "O0" ||
         level == "O1" || level == "O2" || level == "O3" || level == "Os" ||
         level == "Oz" || level == "unknown";
}

bool isKnownNativeEffectiveOptimizationLevel(std::string_view level) {
  return level == "O0" || level == "O2" || level == "O3" ||
         level == "none" || level == "unknown";
}

bool isKnownNativeOptimizationEvidenceStatus(std::string_view status) {
  return status == "applied" || status == "metadata-only" ||
         status == "skipped-disabled" ||
         status == "skipped-tool-missing" || status == "not-run" ||
         status == "unavailable";
}

bool isKnownNativeOptimizationEvidenceSourceKind(std::string_view kind) {
  return kind == "native-profile" || kind == "toolchain-provenance" ||
         kind == "compiler-policy" || kind == "descriptor";
}

bool isKnownNativeValidationStatus(std::string_view status) {
  return status == "not-run" || status == "validated" || status == "failed" ||
         status == "unavailable";
}

bool parseJsonStringDocument(std::string_view value, std::string &parsed) {
  std::size_t position = 0;
  if (!parseJsonString(value, position, parsed)) {
    return false;
  }
  skipWhitespace(value, position);
  return position == value.size();
}

bool validateOptionalStringMember(
    std::string_view object,
    const std::vector<JsonObjectMemberRange> &members, std::string_view key) {
  if (!hasMember(members, key)) {
    return true;
  }
  const std::optional<std::string> value = objectStringMember(object, key);
  return value && !value->empty();
}

bool validateStringArray(std::string_view value) {
  const std::optional<std::vector<JsonRange>> elements =
      collectArrayElementRanges(value);
  if (!elements) {
    return false;
  }
  for (JsonRange range : *elements) {
    std::string parsed;
    if (!parseJsonStringDocument(
            value.substr(range.begin, range.end - range.begin), parsed) ||
        parsed.empty()) {
      return false;
    }
  }
  return true;
}

bool validateOptimizationEvidenceSource(std::string_view value) {
  const std::optional<std::vector<JsonObjectMemberRange>> members =
      collectObjectMemberRanges(value);
  if (!members || !membersAreAllowed(*members, {"kind", "path"}) ||
      !hasAllMembers(*members, {"kind"})) {
    return false;
  }

  const std::optional<std::string> kind = objectStringMember(value, "kind");
  if (!kind || !isKnownNativeOptimizationEvidenceSourceKind(*kind)) {
    return false;
  }
  if (hasMember(*members, "path")) {
    const std::optional<std::string> path = objectStringMember(value, "path");
    if (!path || !isPackageRelativePath(*path)) {
      return false;
    }
  }
  return true;
}

bool validateNativeOptimizationEvidence(std::string_view value) {
  const std::optional<std::vector<JsonObjectMemberRange>> members =
      collectObjectMemberRanges(value);
  if (!members ||
      !membersAreAllowed(*members,
                         {"requestedLevel", "effectiveLevel", "policy",
                          "status", "tool", "toolFlag", "evidenceSource",
                          "debugInfo", "profile", "flags"}) ||
      !hasAllMembers(*members, {"requestedLevel", "effectiveLevel", "policy",
                                "status"})) {
    return false;
  }

  const std::optional<std::string> requestedLevel =
      objectStringMember(value, "requestedLevel");
  const std::optional<std::string> effectiveLevel =
      objectStringMember(value, "effectiveLevel");
  const std::optional<std::string> policy = objectStringMember(value, "policy");
  const std::optional<std::string> status = objectStringMember(value, "status");
  if (!requestedLevel || !isKnownNativeOptimizationLevel(*requestedLevel) ||
      !effectiveLevel ||
      !isKnownNativeEffectiveOptimizationLevel(*effectiveLevel) || !policy ||
      policy->empty() || !status ||
      !isKnownNativeOptimizationEvidenceStatus(*status)) {
    return false;
  }
  if (!validateOptionalStringMember(value, *members, "tool") ||
      !validateOptionalStringMember(value, *members, "toolFlag") ||
      !validateOptionalStringMember(value, *members, "profile")) {
    return false;
  }
  if (hasMember(*members, "debugInfo") &&
      !objectBoolMember(value, "debugInfo")) {
    return false;
  }
  if (hasMember(*members, "flags")) {
    const std::optional<std::string_view> flags =
        findObjectMemberValue(value, "flags");
    if (!flags || !validateStringArray(*flags)) {
      return false;
    }
  }
  if (hasMember(*members, "evidenceSource")) {
    const std::optional<std::string_view> evidenceSource =
        findObjectMemberValue(value, "evidenceSource");
    if (!evidenceSource ||
        !validateOptimizationEvidenceSource(*evidenceSource)) {
      return false;
    }
  }
  return true;
}

bool isValidSPIRVResultId(std::string_view value) {
  if (value.size() < 2 || value.front() != '%') {
    return false;
  }
  for (const char character : value) {
    if (std::isspace(static_cast<unsigned char>(character))) {
      return false;
    }
  }
  return true;
}

bool validateSPIRVExtendedInstructionSetImport(
    std::string_view value, std::string &resultId,
    std::string &instructionSet) {
  const std::optional<std::vector<JsonObjectMemberRange>> members =
      collectObjectMemberRanges(value);
  if (!members ||
      !membersAreAllowed(*members, {"resultId", "instructionSet"}) ||
      !hasAllMembers(*members, {"resultId", "instructionSet"})) {
    return false;
  }
  const std::optional<std::string> parsedResultId =
      objectStringMember(value, "resultId");
  const std::optional<std::string> parsedInstructionSet =
      objectStringMember(value, "instructionSet");
  if (!parsedResultId || !isValidSPIRVResultId(*parsedResultId) ||
      !parsedInstructionSet || parsedInstructionSet->empty()) {
    return false;
  }
  resultId = *parsedResultId;
  instructionSet = *parsedInstructionSet;
  return true;
}

bool validateSPIRVDependencies(std::string_view value) {
  const std::optional<std::vector<JsonObjectMemberRange>> members =
      collectObjectMemberRanges(value);
  if (!members || !membersAreAllowed(*members, {"extendedInstructionSets"}) ||
      !hasAllMembers(*members, {"extendedInstructionSets"})) {
    return false;
  }
  const std::optional<std::string_view> importsValue =
      findObjectMemberValue(value, "extendedInstructionSets");
  if (!importsValue) {
    return false;
  }
  const std::optional<std::vector<JsonRange>> importRanges =
      collectArrayElementRanges(*importsValue);
  if (!importRanges || importRanges->empty()) {
    return false;
  }

  std::vector<std::string> seenResultIds;
  std::vector<std::string> seenInstructionSets;
  std::optional<std::pair<std::string, std::string>> previousKey;
  for (JsonRange range : *importRanges) {
    std::string resultId;
    std::string instructionSet;
    if (!validateSPIRVExtendedInstructionSetImport(
            importsValue->substr(range.begin, range.end - range.begin),
            resultId, instructionSet)) {
      return false;
    }

    const std::pair<std::string, std::string> key{instructionSet, resultId};
    if (previousKey && key < *previousKey) {
      return false;
    }
    previousKey = key;
    if (std::find(seenResultIds.begin(), seenResultIds.end(), resultId) !=
            seenResultIds.end() ||
        std::find(seenInstructionSets.begin(), seenInstructionSets.end(),
                  instructionSet) != seenInstructionSets.end()) {
      return false;
    }
    seenResultIds.push_back(std::move(resultId));
    seenInstructionSets.push_back(std::move(instructionSet));
  }
  return true;
}

bool isKnownNativeToolRole(std::string_view role) {
  return role == "generator" || role == "compiler" || role == "assembler" ||
         role == "linker" || role == "validator" || role == "packager";
}

bool oldManifestSourcePackageTargetRequiresNativeBinaryStatus(
    std::string_view target) {
  return target == "directx" || target == "opengl";
}

bool metadataRequiresNativeBinaryStatus(const PackageMetadata &metadata) {
  if (metadata.artifactRequirements) {
    return metadata.artifactRequirements->requiresNativeBinaryStatus;
  }
  return oldManifestSourcePackageTargetRequiresNativeBinaryStatus(
      metadata.target);
}

bool targetAllowsBinaryKind(std::string_view target,
                            std::string_view binaryKind) {
  if (target == "metal") {
    return binaryKind == "metal.metallib";
  }
  if (target == "vulkan") {
    return binaryKind == "vulkan.spirv-module";
  }
  if (target == "directx") {
    return binaryKind == "directx.dxil" || binaryKind == "directx.dxbc";
  }
  if (target == "opengl") {
    return binaryKind == "opengl.source" || binaryKind == "opengl.package";
  }
  return false;
}

bool endsWith(std::string_view value, std::string_view suffix) {
  return value.size() >= suffix.size() &&
         value.substr(value.size() - suffix.size()) == suffix;
}

bool artifactPathExtensionMatchesBinaryKind(std::string_view binaryKind,
                                            std::string_view artifactPath) {
  if (binaryKind == "metal.metallib") {
    return endsWith(artifactPath, ".metallib");
  }
  if (binaryKind == "vulkan.spirv-module") {
    return endsWith(artifactPath, ".spv");
  }
  if (binaryKind == "directx.dxil") {
    return endsWith(artifactPath, ".dxil");
  }
  if (binaryKind == "directx.dxbc") {
    return endsWith(artifactPath, ".dxbc");
  }
  if (binaryKind == "opengl.source") {
    return endsWith(artifactPath, ".glsl");
  }
  if (binaryKind == "opengl.package") {
    return endsWith(artifactPath, ".cglb") || endsWith(artifactPath, ".zip") ||
           endsWith(artifactPath, ".tar") || endsWith(artifactPath, ".tar.gz");
  }
  return false;
}

bool hasToolRole(const std::vector<NativeArtifactToolRecord> &tools,
                 std::string_view role) {
  return std::any_of(
      tools.begin(), tools.end(),
      [&](const NativeArtifactToolRecord &tool) { return tool.role == role; });
}

std::size_t countToolRole(const std::vector<NativeArtifactToolRecord> &tools,
                          std::string_view role) {
  return static_cast<std::size_t>(std::count_if(
      tools.begin(), tools.end(),
      [&](const NativeArtifactToolRecord &tool) { return tool.role == role; }));
}

bool hasUnexpectedToolRole(const std::vector<NativeArtifactToolRecord> &tools,
                           std::string_view expectedRole) {
  return std::any_of(tools.begin(), tools.end(),
                     [&](const NativeArtifactToolRecord &tool) {
                       return tool.role != expectedRole;
                     });
}

std::optional<std::string_view>
plannedSourcePackageGeneratorName(std::string_view target) {
  if (target == "directx") {
    return std::string_view("CrossGL DirectX backend");
  }
  if (target == "opengl") {
    return std::string_view("CrossGL OpenGL backend");
  }
  return std::nullopt;
}

bool plannedSourcePackageGeneratorMatches(
    std::string_view target,
    const std::vector<NativeArtifactToolRecord> &tools) {
  const std::optional<std::string_view> expectedGenerator =
      plannedSourcePackageGeneratorName(target);
  if (!expectedGenerator || countToolRole(tools, "generator") != 1) {
    return false;
  }
  return std::any_of(tools.begin(), tools.end(),
                     [&](const NativeArtifactToolRecord &tool) {
                       return tool.role == "generator" &&
                              tool.name == *expectedGenerator;
                     });
}

bool openglPlannedValidationFailureToolsMatch(
    const std::vector<NativeArtifactToolRecord> &tools) {
  if (tools.size() != 2 || countToolRole(tools, "generator") != 1 ||
      countToolRole(tools, "validator") != 1) {
    return false;
  }
  return std::any_of(tools.begin(), tools.end(),
                     [](const NativeArtifactToolRecord &tool) {
                       return tool.role == "generator" &&
                              tool.name == "CrossGL-Compiler";
                     }) &&
         std::any_of(tools.begin(), tools.end(),
                     [](const NativeArtifactToolRecord &tool) {
                       return tool.role == "validator" &&
                              tool.name == "glslangValidator";
                     });
}

bool directxPlannedDxcToolsMatch(
    const std::vector<NativeArtifactToolRecord> &tools) {
  if (tools.size() != 2 || countToolRole(tools, "generator") != 1 ||
      countToolRole(tools, "compiler") != 1) {
    return false;
  }
  return std::any_of(tools.begin(), tools.end(),
                     [](const NativeArtifactToolRecord &tool) {
                       return tool.role == "generator" &&
                              tool.name == "CrossGL-Compiler";
                     }) &&
         std::any_of(tools.begin(), tools.end(),
                     [](const NativeArtifactToolRecord &tool) {
                       return tool.role == "compiler" &&
                              tool.name == "dxc";
                     });
}

bool metalNativeToolFailureToolsMatch(
    const std::vector<NativeArtifactToolRecord> &tools) {
  if (tools.size() != 3 || countToolRole(tools, "generator") != 1 ||
      countToolRole(tools, "compiler") != 1 ||
      countToolRole(tools, "linker") != 1) {
    return false;
  }
  return std::any_of(tools.begin(), tools.end(),
                     [](const NativeArtifactToolRecord &tool) {
                       return tool.role == "generator" &&
                              tool.name == "CrossGL-Compiler";
                     }) &&
         std::any_of(tools.begin(), tools.end(),
                     [](const NativeArtifactToolRecord &tool) {
                       return tool.role == "compiler" &&
                              tool.name == "xcrun metal";
                     }) &&
         std::any_of(tools.begin(), tools.end(),
                     [](const NativeArtifactToolRecord &tool) {
                       return tool.role == "linker" &&
                              tool.name == "xcrun metallib";
                     });
}

bool directxPlannedOptimizationEvidenceMatches(
    std::string_view descriptorText, std::string_view optimizationLevel) {
  const std::optional<std::string_view> evidence =
      findObjectMemberValue(descriptorText, "optimizationEvidence");
  if (!evidence) {
    return false;
  }
  const std::optional<std::string> requestedLevel =
      objectStringMember(*evidence, "requestedLevel");
  const std::optional<std::string> effectiveLevel =
      objectStringMember(*evidence, "effectiveLevel");
  const std::optional<std::string> policy =
      objectStringMember(*evidence, "policy");
  const std::optional<std::string> status =
      objectStringMember(*evidence, "status");
  const std::optional<std::string> tool = objectStringMember(*evidence, "tool");
  const std::optional<std::string> toolFlag =
      objectStringMember(*evidence, "toolFlag");
  const std::optional<std::string> profile =
      objectStringMember(*evidence, "profile");
  return requestedLevel && *requestedLevel == optimizationLevel &&
         effectiveLevel && *effectiveLevel == "unknown" && policy &&
         *policy == "crossgl-to-dxc-optimization-map" && status &&
         (*status == "not-run" || *status == "unavailable") && tool &&
         *tool == "dxc" && toolFlag && !toolFlag->empty() && profile &&
         !profile->empty();
}

bool hasDuplicateToolRoleRecord(
    const std::vector<NativeArtifactToolRecord> &tools) {
  for (std::size_t index = 0; index < tools.size(); ++index) {
    for (std::size_t compare = index + 1; compare < tools.size(); ++compare) {
      if (tools[index].name == tools[compare].name &&
          tools[index].role == tools[compare].role) {
        return true;
      }
    }
  }
  return false;
}

bool validateInvocationObject(std::string_view value) {
  const std::optional<std::vector<JsonObjectMemberRange>> members =
      collectObjectMemberRanges(value);
  if (!members ||
      !membersAreAllowed(*members,
                         {"commandLineSha256", "environmentSha256"}) ||
      !hasAllMembers(*members, {"commandLineSha256", "environmentSha256"})) {
    return false;
  }
  const std::optional<std::string> commandLineSha256 =
      objectStringMember(value, "commandLineSha256");
  const std::optional<std::string> environmentSha256 =
      objectStringMember(value, "environmentSha256");
  return commandLineSha256 && isLowercaseSha256(*commandLineSha256) &&
         environmentSha256 && isLowercaseSha256(*environmentSha256);
}

bool isKnownNativeArtifactDiagnosticSeverity(std::string_view severity) {
  return severity == "note" || severity == "warning" || severity == "error";
}

bool validateNativeArtifactDiagnosticLocation(std::string_view value) {
  const std::optional<std::vector<JsonObjectMemberRange>> members =
      collectObjectMemberRanges(value);
  if (!members ||
      !membersAreAllowed(
          *members, {"file", "line", "column", "offset", "length", "endLine",
                     "endColumn", "endOffset"}) ||
      !hasAllMembers(*members, {"file", "line", "column", "offset", "length",
                                "endLine", "endColumn", "endOffset"})) {
    return false;
  }
  const std::optional<std::string> file = objectStringMember(value, "file");
  const std::optional<std::uintmax_t> line =
      objectUnsignedMember(value, "line");
  const std::optional<std::uintmax_t> column =
      objectUnsignedMember(value, "column");
  const std::optional<std::uintmax_t> offset =
      objectUnsignedMember(value, "offset");
  const std::optional<std::uintmax_t> length =
      objectUnsignedMember(value, "length");
  const std::optional<std::uintmax_t> endLine =
      objectUnsignedMember(value, "endLine");
  const std::optional<std::uintmax_t> endColumn =
      objectUnsignedMember(value, "endColumn");
  const std::optional<std::uintmax_t> endOffset =
      objectUnsignedMember(value, "endOffset");
  if (!file || !isPackageRelativePath(*file) || !line || *line == 0 ||
      !column || *column == 0 || !offset || !length || !endLine ||
      *endLine == 0 || !endColumn || *endColumn == 0 || !endOffset) {
    return false;
  }
  if (*endLine < *line || (*endLine == *line && *endColumn < *column)) {
    return false;
  }
  return *endOffset >= *offset;
}

bool validateDiagnosticObject(std::string_view value) {
  const std::optional<std::vector<JsonObjectMemberRange>> members =
      collectObjectMemberRanges(value);
  if (!members ||
      !membersAreAllowed(*members, {"severity", "code", "message", "location",
                                    "originalLocation", "target",
                                    "missingCapabilities"}) ||
      !hasAllMembers(*members, {"code", "message"})) {
    return false;
  }
  const std::optional<std::string> code = objectStringMember(value, "code");
  const std::optional<std::string> message =
      objectStringMember(value, "message");
  if (!code || !isValidDiagnosticCode(*code) || !message || message->empty()) {
    return false;
  }
  if (hasMember(*members, "severity")) {
    const std::optional<std::string> severity =
        objectStringMember(value, "severity");
    if (!severity || !isKnownNativeArtifactDiagnosticSeverity(*severity)) {
      return false;
    }
  }
  if (hasMember(*members, "location")) {
    const std::optional<std::string_view> location =
        findObjectMemberValue(value, "location");
    if (!location || !validateNativeArtifactDiagnosticLocation(*location)) {
      return false;
    }
  }
  if (hasMember(*members, "originalLocation")) {
    const std::optional<std::string_view> originalLocation =
        findObjectMemberValue(value, "originalLocation");
    if (!originalLocation ||
        !validateNativeArtifactDiagnosticLocation(*originalLocation)) {
      return false;
    }
  }
  if (hasMember(*members, "target")) {
    const std::optional<std::string> target =
        objectStringMember(value, "target");
    if (!target || !isKnownPackageTargetName(*target)) {
      return false;
    }
  }
  if (hasMember(*members, "missingCapabilities")) {
    const std::optional<std::string_view> missingCapabilities =
        findObjectMemberValue(value, "missingCapabilities");
    if (!missingCapabilities || !validateStringArray(*missingCapabilities) ||
        arrayLength(*missingCapabilities).value_or(0) == 0) {
      return false;
    }
  }
  return true;
}

bool validateToolRecord(std::string_view value,
                        NativeArtifactToolRecord &toolRecord) {
  const std::optional<std::vector<JsonObjectMemberRange>> members =
      collectObjectMemberRanges(value);
  if (!members ||
      !membersAreAllowed(*members, {"name", "role", "version", "executable",
                                    "resolvedExecutable", "executableSource",
                                    "versionProbeStatus", "versionDetail",
                                    "argumentsSha256", "commandShape",
                                    "responseFilePath", "outputPath",
                                    "outputSha256", "outputSizeBytes",
                                    "provenanceStatus",
                                    "provenanceDetail"}) ||
      !hasAllMembers(*members, {"name", "role", "version", "executable"})) {
    return false;
  }
  const std::optional<std::string> name = objectStringMember(value, "name");
  const std::optional<std::string> role = objectStringMember(value, "role");
  const std::optional<std::string> version =
      objectStringMember(value, "version");
  const std::optional<std::string> executable =
      objectStringMember(value, "executable");
  if (!name || name->empty() || !role || !isKnownNativeToolRole(*role) ||
      !version || version->empty() || !executable || executable->empty()) {
    return false;
  }
  if (hasMember(*members, "argumentsSha256")) {
    const std::optional<std::string> argumentsSha256 =
        objectStringMember(value, "argumentsSha256");
    if (!argumentsSha256 || !isLowercaseSha256(*argumentsSha256)) {
      return false;
    }
  }
  if (hasMember(*members, "commandShape")) {
    const std::optional<std::string> commandShape =
        objectStringMember(value, "commandShape");
    if (!commandShape || commandShape->empty()) {
      return false;
    }
  }
  if (hasMember(*members, "responseFilePath")) {
    const std::optional<std::string> responseFilePath =
        objectStringMember(value, "responseFilePath");
    if (!responseFilePath || !isPackageRelativePath(*responseFilePath)) {
      return false;
    }
  }
  if (hasMember(*members, "outputPath")) {
    const std::optional<std::string> outputPath =
        objectStringMember(value, "outputPath");
    if (!outputPath || !isPackageRelativePath(*outputPath)) {
      return false;
    }
  }
  if (hasMember(*members, "outputSha256")) {
    const std::optional<std::string> outputSha256 =
        objectStringMember(value, "outputSha256");
    if (!outputSha256 || !isLowercaseSha256(*outputSha256)) {
      return false;
    }
  }
  if (hasMember(*members, "outputSizeBytes") &&
      !objectUnsignedMember(value, "outputSizeBytes")) {
    return false;
  }
  if (hasMember(*members, "provenanceStatus")) {
    const std::optional<std::string> provenanceStatus =
        objectStringMember(value, "provenanceStatus");
    if (!provenanceStatus ||
        (*provenanceStatus != "captured" &&
         *provenanceStatus != "succeeded" &&
         *provenanceStatus != "failed" &&
         *provenanceStatus != "missing-tool" &&
         *provenanceStatus != "not-started" &&
         *provenanceStatus != "incomplete")) {
      return false;
    }
  }
  if (hasMember(*members, "provenanceDetail")) {
    const std::optional<std::string> provenanceDetail =
        objectStringMember(value, "provenanceDetail");
    if (!provenanceDetail || provenanceDetail->empty()) {
      return false;
    }
  }
  if (hasMember(*members, "resolvedExecutable")) {
    const std::optional<std::string> resolvedExecutable =
        objectStringMember(value, "resolvedExecutable");
    if (!resolvedExecutable || resolvedExecutable->empty()) {
      return false;
    }
  }
  if (hasMember(*members, "executableSource")) {
    const std::optional<std::string> executableSource =
        objectStringMember(value, "executableSource");
    if (!executableSource ||
        (*executableSource != "PATH" && *executableSource != "direct" &&
         *executableSource != "fallback" &&
         *executableSource != "xcrun" &&
         *executableSource != "not-found")) {
      return false;
    }
  }
  if (hasMember(*members, "versionProbeStatus")) {
    const std::optional<std::string> versionProbeStatus =
        objectStringMember(value, "versionProbeStatus");
    if (!versionProbeStatus ||
        (*versionProbeStatus != "succeeded" &&
         *versionProbeStatus != "failed" &&
         *versionProbeStatus != "not-started" &&
         *versionProbeStatus != "version-unknown" &&
         *versionProbeStatus != "unavailable")) {
      return false;
    }
  }
  if (hasMember(*members, "versionDetail")) {
    const std::optional<std::string> versionDetail =
        objectStringMember(value, "versionDetail");
    if (!versionDetail || versionDetail->empty()) {
      return false;
    }
  }
  toolRecord = NativeArtifactToolRecord{*name, *role};
  return true;
}

bool validateToolchainProvenance(std::string_view value,
                                 std::vector<NativeArtifactToolRecord> &tools) {
  const std::optional<std::vector<JsonObjectMemberRange>> members =
      collectObjectMemberRanges(value);
  if (!members ||
      !membersAreAllowed(*members, {"producer", "tools", "invocation"}) ||
      !hasAllMembers(*members, {"producer", "tools", "invocation"})) {
    return false;
  }
  const std::optional<std::string> producer =
      objectStringMember(value, "producer");
  if (!producer || producer->empty()) {
    return false;
  }
  const std::optional<std::string_view> toolsValue =
      findObjectMemberValue(value, "tools");
  const std::optional<std::string_view> invocationValue =
      findObjectMemberValue(value, "invocation");
  if (!toolsValue || !invocationValue ||
      !validateInvocationObject(*invocationValue)) {
    return false;
  }
  const std::optional<std::vector<JsonRange>> toolRanges =
      collectArrayElementRanges(*toolsValue);
  if (!toolRanges || toolRanges->empty()) {
    return false;
  }
  for (JsonRange range : *toolRanges) {
    NativeArtifactToolRecord record;
    if (!validateToolRecord(
            toolsValue->substr(range.begin, range.end - range.begin), record)) {
      return false;
    }
    tools.push_back(std::move(record));
  }
  return true;
}

bool validateValidationDiagnostics(std::string_view value,
                                   std::size_t &diagnosticCount) {
  const std::optional<std::vector<JsonRange>> diagnosticRanges =
      collectArrayElementRanges(value);
  if (!diagnosticRanges) {
    return false;
  }
  diagnosticCount = diagnosticRanges->size();
  for (JsonRange range : *diagnosticRanges) {
    if (!validateDiagnosticObject(
            value.substr(range.begin, range.end - range.begin))) {
      return false;
    }
  }
  return true;
}

bool requiredNativeArtifactRolesPresent(
    std::string_view binaryKind,
    const std::vector<NativeArtifactToolRecord> &tools) {
  if (binaryKind == "metal.metallib") {
    return hasToolRole(tools, "compiler") && hasToolRole(tools, "linker");
  }
  if (binaryKind == "vulkan.spirv-module") {
    return hasToolRole(tools, "assembler");
  }
  if (binaryKind == "directx.dxil" || binaryKind == "directx.dxbc") {
    return hasToolRole(tools, "compiler");
  }
  if (binaryKind == "opengl.source") {
    return hasToolRole(tools, "generator");
  }
  if (binaryKind == "opengl.package") {
    return hasToolRole(tools, "packager");
  }
  return false;
}

bool nativeArtifactDescriptorMatchesContract(
    std::string_view descriptorText,
    const PackageNativeArtifactDescriptorHealth &health,
    bool requiresNativeBinaryStatus) {
  const std::optional<std::vector<JsonObjectMemberRange>> members =
      collectObjectMemberRanges(descriptorText);
  if (!members) {
    return false;
  }
  if (!membersAreAllowed(
          *members, {"schemaVersion", "kind", "contractVersion", "target",
                     "binaryKind", "artifactPath", "artifactHash", "sizeBytes",
                     "spirvDependencies", "sourcePath", "sourceHash",
                     "toolchainProvenance", "optimizationLevel",
                     "optimizationEvidence",
                     "validationStatus", "nativeBinaryStatus",
                     "validationDiagnostics"}) ||
      !hasAllMembers(*members,
                     {"schemaVersion", "kind", "contractVersion", "target",
                      "binaryKind", "sourcePath", "sourceHash",
                      "toolchainProvenance", "optimizationLevel",
                      "validationStatus", "validationDiagnostics"})) {
    return false;
  }

  if (!health.schemaVersion || *health.schemaVersion != 1 || !health.kind ||
      *health.kind != kNativeArtifactKind || !health.contractVersion ||
      *health.contractVersion != kNativeArtifactContractVersion ||
      !health.target || !isKnownPackageTargetName(*health.target) ||
      !health.binaryKind ||
      !isKnownNativeArtifactBinaryKind(*health.binaryKind) ||
      !targetAllowsBinaryKind(*health.target, *health.binaryKind) ||
      !health.sourcePath || !isPackageRelativePath(*health.sourcePath) ||
      !health.sourceHash || !validateHashObject(descriptorText, "sourceHash") ||
      !health.optimizationLevel ||
      !isKnownNativeOptimizationLevel(*health.optimizationLevel) ||
      !health.validationStatus ||
      !isKnownNativeValidationStatus(*health.validationStatus)) {
    return false;
  }

  const bool hasArtifactPath = hasMember(*members, "artifactPath");
  const bool hasArtifactHash = hasMember(*members, "artifactHash");
  const bool hasSizeBytes = hasMember(*members, "sizeBytes");
  if (hasArtifactPath != hasArtifactHash || hasArtifactPath != hasSizeBytes) {
    return false;
  }
  if (hasArtifactPath) {
    if (!health.artifactPath || !isPackageRelativePath(*health.artifactPath) ||
        !artifactPathExtensionMatchesBinaryKind(*health.binaryKind,
                                                *health.artifactPath) ||
        !health.artifactHash ||
        !validateHashObject(descriptorText, "artifactHash") ||
        !health.sizeBytes) {
      return false;
    }
  }

  const std::optional<std::string_view> optimizationEvidence =
      findObjectMemberValue(descriptorText, "optimizationEvidence");
  if (optimizationEvidence &&
      !validateNativeOptimizationEvidence(*optimizationEvidence)) {
    return false;
  }
  const std::optional<std::string_view> spirvDependencies =
      findObjectMemberValue(descriptorText, "spirvDependencies");
  if (spirvDependencies &&
      (*health.binaryKind != "vulkan.spirv-module" ||
       !validateSPIRVDependencies(*spirvDependencies))) {
    return false;
  }

  std::vector<NativeArtifactToolRecord> tools;
  const std::optional<std::string_view> provenanceValue =
      findObjectMemberValue(descriptorText, "toolchainProvenance");
  if (!provenanceValue ||
      !validateToolchainProvenance(*provenanceValue, tools) ||
      hasDuplicateToolRoleRecord(tools)) {
    return false;
  }

  std::size_t validationDiagnosticCount = 0;
  const std::optional<std::string_view> diagnosticsValue =
      findObjectMemberValue(descriptorText, "validationDiagnostics");
  if (!diagnosticsValue || !validateValidationDiagnostics(
                               *diagnosticsValue, validationDiagnosticCount)) {
    return false;
  }

  if ((*health.validationStatus == "not-run" ||
       *health.validationStatus == "unavailable") &&
      hasToolRole(tools, "validator")) {
    return false;
  }

  if (requiresNativeBinaryStatus) {
    if (!health.nativeBinaryStatus ||
        !isKnownPackageNativeBinaryStatus(*health.nativeBinaryStatus)) {
      return false;
    }
    if (*health.nativeBinaryStatus == "planned") {
      const bool directxPlannedDxcEvidence =
          *health.target == "directx" && *health.binaryKind == "directx.dxil" &&
          directxPlannedDxcToolsMatch(tools) &&
          directxPlannedOptimizationEvidenceMatches(
              descriptorText, *health.optimizationLevel);
      if (hasArtifactPath ||
          (!directxPlannedDxcEvidence &&
           *health.optimizationLevel != "unknown")) {
        return false;
      }
      if (*health.validationStatus == "unavailable") {
        if (!directxPlannedDxcEvidence &&
            (hasUnexpectedToolRole(tools, "generator") ||
             !plannedSourcePackageGeneratorMatches(*health.target, tools))) {
          return false;
        }
      } else if (*health.validationStatus == "failed" &&
                 *health.binaryKind == "opengl.source") {
        if (!openglPlannedValidationFailureToolsMatch(tools)) {
          return false;
        }
      } else if (*health.validationStatus == "failed" &&
                 directxPlannedDxcEvidence) {
        if (validationDiagnosticCount == 0) {
          return false;
        }
      } else {
        return false;
      }
    } else if (!hasArtifactPath) {
      return false;
    }
    if (*health.validationStatus == "validated" &&
        *health.nativeBinaryStatus != "validated") {
      return false;
    }
    if (*health.nativeBinaryStatus == "validated" &&
        *health.validationStatus != "validated") {
      return false;
    }
  } else if (health.nativeBinaryStatus || !hasArtifactPath) {
    return false;
  }

  if (health.nativeBinaryStatus && *health.nativeBinaryStatus != "planned" &&
      !requiredNativeArtifactRolesPresent(*health.binaryKind, tools)) {
    return false;
  }
  if (!health.nativeBinaryStatus &&
      !requiredNativeArtifactRolesPresent(*health.binaryKind, tools)) {
    return false;
  }
  const bool directxPlannedCompilerFailure =
      health.nativeBinaryStatus && *health.nativeBinaryStatus == "planned" &&
      *health.validationStatus == "failed" && *health.target == "directx" &&
      *health.binaryKind == "directx.dxil" &&
      directxPlannedDxcToolsMatch(tools);
  const bool metalNativeToolFailure =
      !health.nativeBinaryStatus && *health.validationStatus == "failed" &&
      *health.target == "metal" && *health.binaryKind == "metal.metallib" &&
      metalNativeToolFailureToolsMatch(tools);
  if ((*health.validationStatus == "validated" ||
       *health.validationStatus == "failed") &&
      !directxPlannedCompilerFailure &&
      !metalNativeToolFailure &&
      !hasToolRole(tools, "validator")) {
    return false;
  }
  if (*health.validationStatus == "failed" && validationDiagnosticCount == 0) {
    return false;
  }
  if (*health.validationStatus != "failed" && validationDiagnosticCount != 0) {
    return false;
  }

  return true;
}

const PackageArtifactRecord *expectedNativeArtifactSourceRecord(
    const PackageMetadata &metadata,
    const std::optional<std::string> &binaryKind) {
  if (!binaryKind) {
    return nullptr;
  }
  if (*binaryKind == "vulkan.spirv-module") {
    return findArtifact(metadata, "backendAssembly");
  }
  if (*binaryKind == "metal.metallib" || *binaryKind == "directx.dxil" ||
      *binaryKind == "directx.dxbc" || *binaryKind == "opengl.source" ||
      *binaryKind == "opengl.package") {
    return findArtifact(metadata, "backendSource");
  }
  return nullptr;
}

bool optionalCheckFailed(const std::optional<bool> &check) {
  return check && !*check;
}

bool anyNativeArtifactDescriptorCheckFailed(
    const PackageNativeArtifactDescriptorChecks &checks) {
  return optionalCheckFailed(checks.descriptorIdentityMatchesContract) ||
         optionalCheckFailed(checks.targetMatchesPackage) ||
         optionalCheckFailed(checks.nativeBinaryStatusMatchesPackage) ||
         optionalCheckFailed(checks.sourcePathMatchesManifest) ||
         optionalCheckFailed(checks.sourceHashMatchesFile) ||
         optionalCheckFailed(checks.artifactPathMatchesManifest) ||
         optionalCheckFailed(checks.artifactHashMatchesFile) ||
         optionalCheckFailed(checks.sizeBytesMatchesFile) ||
         optionalCheckFailed(checks.validationStatusMatchesNativeStatus);
}

std::string graphicsAbiDiagnosticCode(std::string_view suffix) {
  return "package.graphicsAbi." + std::string(suffix);
}

void addGraphicsAbiDiagnostic(PackageGraphicsAbiHealth &health,
                              std::string_view codeSuffix,
                              std::string message) {
  health.diagnostics.push_back(
      {graphicsAbiDiagnosticCode(codeSuffix), std::move(message)});
}

std::string graphicsAbiPathIssueMessage(PackagePathIssue issue) {
  switch (issue) {
  case PackagePathIssue::None:
    return "";
  case PackagePathIssue::Empty:
    return "path must not be empty";
  case PackagePathIssue::BackslashSeparator:
    return "artifact paths must use '/' separators";
  case PackagePathIssue::Absolute:
    return "path must be package-relative";
  case PackagePathIssue::ParentTraversal:
    return "path must stay inside package";
  }
  return "path is invalid";
}

std::optional<std::uintmax_t>
graphicsAbiArrayCount(std::string_view document, std::string_view key,
                      PackageGraphicsAbiHealth &health) {
  const std::optional<std::string_view> value =
      findObjectMemberValue(document, key);
  if (!value) {
    addGraphicsAbiDiagnostic(
        health, "invalid-contract",
        "graphics ABI sidecar is missing required array '" +
            std::string(key) + "'");
    return std::nullopt;
  }
  const std::optional<std::size_t> count = arrayLength(*value);
  if (!count) {
    addGraphicsAbiDiagnostic(
        health, "invalid-contract",
        "graphics ABI sidecar member '" + std::string(key) +
            "' must be an array");
    return std::nullopt;
  }
  return static_cast<std::uintmax_t>(*count);
}

} // namespace

PackagePathIssue packagePathIssue(std::string_view path) {
  if (path.empty()) {
    return PackagePathIssue::Empty;
  }
  if (path.find('\\') != std::string_view::npos) {
    return PackagePathIssue::BackslashSeparator;
  }
  if (path.front() == '/') {
    return PackagePathIssue::Absolute;
  }
  if (path.size() >= 2 && std::isalpha(static_cast<unsigned char>(path[0])) &&
      path[1] == ':') {
    return PackagePathIssue::Absolute;
  }
  const std::filesystem::path artifactPath{std::string(path)};
  if (artifactPath.is_absolute()) {
    return PackagePathIssue::Absolute;
  }
  for (const auto &part : artifactPath) {
    if (part.generic_string() == "..") {
      return PackagePathIssue::ParentTraversal;
    }
  }
  return PackagePathIssue::None;
}

bool isPackageRelativePath(std::string_view path) {
  return packagePathIssue(path) == PackagePathIssue::None;
}

bool isKnownPackageTargetName(std::string_view target) {
  return target == "metal" || target == "vulkan" || target == "directx" ||
         target == "opengl";
}

bool isKnownPackageNativeBinaryStatus(std::string_view status) {
  return status == "planned" || status == "emitted" || status == "validated";
}

bool packageNativeBinaryStatusMatchesRequirements(
    const PackageArtifactRequirementsRecord &requirements,
    const std::optional<std::string> &nativeBinaryStatus) {
  if (!nativeBinaryStatus) {
    return !requirements.requiresNativeBinaryStatus;
  }
  if (!requirements.requiresNativeBinaryStatus) {
    return false;
  }
  if (*nativeBinaryStatus == "planned" &&
      !requirements.allowsPlannedNativeBinary) {
    return false;
  }
  return true;
}

std::optional<std::string>
effectivePackageNativeBinaryStatus(const PackageMetadata &metadata) {
  if (metadata.nativeBinaryStatus) {
    return metadata.nativeBinaryStatus;
  }
  if (metadata.target != "metal") {
    return std::nullopt;
  }

  bool hasProducedIntermediate = false;
  bool hasProducedNativeBinary = false;
  for (const PackageArtifactRecord &artifact : metadata.artifacts) {
    if (artifact.name == "intermediate" && artifact.exists) {
      hasProducedIntermediate = true;
    } else if (artifact.name == "nativeBinary" && artifact.exists) {
      hasProducedNativeBinary = true;
    }
  }
  if (hasProducedIntermediate && hasProducedNativeBinary) {
    return "emitted";
  }
  return std::nullopt;
}

std::optional<std::string>
detectPackageMetadataFormat(const std::filesystem::path &packagePath) {
  std::error_code error;
  if (!std::filesystem::exists(packagePath, error) || error) {
    return std::nullopt;
  }
  if (std::filesystem::is_directory(packagePath, error) && !error) {
    return "directory";
  }
  error.clear();
  if (std::filesystem::is_regular_file(packagePath, error) && !error &&
      fileHasZipSignature(packagePath)) {
    return "zip";
  }
  return std::nullopt;
}

std::optional<std::string>
readPackageArtifactText(const PackageMetadata &metadata,
                        const PackageArtifactRecord &artifact) {
  if (!artifact.packageRelative || !artifact.exists) {
    return std::nullopt;
  }
  if (metadata.packageFormat == "directory") {
    return readRegularTextFile(metadata.packagePath / artifact.path);
  }

  DiagnosticEngine diagnostics;
  PackageMetadataLoadOptions options;
  options.diagnosticCodePrefix = "package.artifact";
  options.commandName = "package artifact";
  options.allowStoredZipPackages = true;
  std::optional<PackageSource> source =
      loadPackageSource(metadata.packagePath, diagnostics, options);
  if (!source || source->format != "zip") {
    return std::nullopt;
  }
  const auto member = source->zipMembers.find(artifact.path);
  if (member == source->zipMembers.end() || member->second.directory) {
    return std::nullopt;
  }
  return readStoredZipMember(*source, member->second, diagnostics, options);
}

PackageNativeArtifactDescriptorHealth
collectPackageNativeArtifactDescriptorHealth(const PackageMetadata &metadata) {
  PackageNativeArtifactDescriptorHealth health;
  const PackageArtifactRecord *descriptor =
      findArtifact(metadata, kNativeArtifactDescriptorArtifact);
  if (descriptor == nullptr) {
    return health;
  }

  health.artifactPresent = true;
  health.path = descriptor->path;
  if (!descriptor->packageRelative || !descriptor->exists) {
    health.health = "incomplete";
    return health;
  }

  const std::filesystem::path descriptorPath =
      metadata.packagePath / descriptor->path;
  const std::optional<std::string> descriptorText =
      readRegularTextFile(descriptorPath);
  if (!descriptorText || !isJsonObjectDocument(*descriptorText) ||
      findDuplicateJsonKey(*descriptorText)) {
    health.descriptorExists = true;
    health.health = "invalid";
    return health;
  }

  health.descriptorExists = true;
  health.schemaVersion = objectUnsignedMember(*descriptorText, "schemaVersion");
  health.kind = objectStringMember(*descriptorText, "kind");
  health.contractVersion =
      objectStringMember(*descriptorText, "contractVersion");
  health.target = objectStringMember(*descriptorText, "target");
  health.binaryKind = objectStringMember(*descriptorText, "binaryKind");
  health.sourcePath = objectStringMember(*descriptorText, "sourcePath");
  health.sourceHash = objectHashValue(*descriptorText, "sourceHash");
  health.artifactPath = objectStringMember(*descriptorText, "artifactPath");
  health.artifactHash = objectHashValue(*descriptorText, "artifactHash");
  health.sizeBytes = objectUnsignedMember(*descriptorText, "sizeBytes");
  health.optimizationLevel =
      objectStringMember(*descriptorText, "optimizationLevel");
  if (const std::optional<std::string_view> optimizationEvidence =
          findObjectMemberValue(*descriptorText, "optimizationEvidence")) {
    health.optimizationEvidence = canonicalJson(*optimizationEvidence);
  }
  health.validationStatus =
      objectStringMember(*descriptorText, "validationStatus");
  health.nativeBinaryStatus =
      objectStringMember(*descriptorText, "nativeBinaryStatus");

  PackageNativeArtifactDescriptorChecks &checks = health.checks;
  checks.descriptorIdentityMatchesContract =
      health.schemaVersion && *health.schemaVersion == 1 && health.kind &&
      *health.kind == kNativeArtifactKind && health.contractVersion &&
      *health.contractVersion == kNativeArtifactContractVersion;
  checks.targetMatchesPackage =
      health.target && *health.target == metadata.target;

  const bool requiresNativeBinaryStatus =
      metadataRequiresNativeBinaryStatus(metadata);
  const std::optional<std::string> expectedNativeStatus =
      effectivePackageNativeBinaryStatus(metadata);
  checks.nativeBinaryStatusMatchesPackage =
      requiresNativeBinaryStatus && expectedNativeStatus
          ? (health.nativeBinaryStatus &&
             *health.nativeBinaryStatus == *expectedNativeStatus)
          : !health.nativeBinaryStatus;

  const PackageArtifactRecord *expectedSource =
      expectedNativeArtifactSourceRecord(metadata, health.binaryKind);
  if (expectedSource != nullptr && health.sourcePath) {
    checks.sourcePathMatchesManifest =
        *health.sourcePath == expectedSource->path;
    if (expectedSource->packageRelative && expectedSource->exists &&
        health.sourceHash) {
      checks.sourceHashMatchesFile =
          fileSha256IfRegular(metadata.packagePath / expectedSource->path) ==
          health.sourceHash;
    }
  } else if (health.sourcePath || health.binaryKind) {
    checks.sourcePathMatchesManifest = false;
  }

  const PackageArtifactRecord *nativeBinary =
      findArtifact(metadata, "nativeBinary");
  const bool plannedNativeBinary =
      expectedNativeStatus && *expectedNativeStatus == "planned";
  if (plannedNativeBinary) {
    checks.artifactPathMatchesManifest = !health.artifactPath;
  } else if (nativeBinary != nullptr && health.artifactPath) {
    checks.artifactPathMatchesManifest =
        *health.artifactPath == nativeBinary->path;
    if (nativeBinary->packageRelative && nativeBinary->exists) {
      if (health.artifactHash) {
        checks.artifactHashMatchesFile =
            fileSha256IfRegular(metadata.packagePath / nativeBinary->path) ==
            health.artifactHash;
      }
      if (health.sizeBytes) {
        checks.sizeBytesMatchesFile =
            fileSizeIfRegular(metadata.packagePath / nativeBinary->path) ==
            health.sizeBytes;
      }
    }
  } else if (nativeBinary != nullptr || health.artifactPath) {
    checks.artifactPathMatchesManifest = false;
  }

  if (health.validationStatus) {
    const bool descriptorValidated = *health.validationStatus == "validated";
    if (requiresNativeBinaryStatus || health.nativeBinaryStatus) {
      const bool nativeValidated = health.nativeBinaryStatus &&
                                   *health.nativeBinaryStatus == "validated";
      checks.validationStatusMatchesNativeStatus =
          descriptorValidated == nativeValidated;
    } else {
      checks.validationStatusMatchesNativeStatus = true;
    }
  }

  health.health =
      anyNativeArtifactDescriptorCheckFailed(checks) ? "drift" : "ok";
  if (!nativeArtifactDescriptorMatchesContract(
          *descriptorText, health, requiresNativeBinaryStatus)) {
    health.health = "invalid";
  }
  return health;
}

PackageGraphicsAbiHealth
collectPackageGraphicsAbiHealth(const PackageMetadata &metadata) {
  PackageGraphicsAbiHealth health;
  const PackageArtifactRecord *graphicsAbi =
      findArtifact(metadata, kGraphicsAbiArtifact);
  if (graphicsAbi == nullptr) {
    return health;
  }

  health.artifactPresent = true;
  health.path = graphicsAbi->path;
  if (graphicsAbi->pathIssue != PackagePathIssue::None) {
    health.health = "missing";
    addGraphicsAbiDiagnostic(health, "invalid-artifact-path",
                             "graphics ABI artifact " +
                                 graphicsAbiPathIssueMessage(
                                     graphicsAbi->pathIssue) +
                                 ": " + graphicsAbi->path);
    return health;
  }
  if (!graphicsAbi->pathExists) {
    health.health = "missing";
    addGraphicsAbiDiagnostic(health, "missing-artifact",
                             "graphics ABI artifact does not exist: " +
                                 graphicsAbi->path);
    return health;
  }
  if (!graphicsAbi->exists) {
    health.health = "missing";
    addGraphicsAbiDiagnostic(health, "artifact-not-file",
                             "graphics ABI artifact is not a file: " +
                                 graphicsAbi->path);
    return health;
  }

  health.exists = true;
  const std::optional<std::string> document =
      readRegularTextFile(metadata.packagePath / graphicsAbi->path);
  if (!document) {
    health.health = "invalid";
    addGraphicsAbiDiagnostic(health, "read-failed",
                             "failed to read graphics ABI artifact: " +
                                 graphicsAbi->path);
    return health;
  }
  if (!isJsonObjectDocument(*document)) {
    health.health = "invalid";
    addGraphicsAbiDiagnostic(
        health, "invalid-json",
        "graphics ABI artifact is not a valid JSON object: " +
            graphicsAbi->path);
    return health;
  }
  if (const std::optional<DuplicateJsonKey> duplicate =
          findDuplicateJsonKey(*document)) {
    health.health = "invalid";
    addGraphicsAbiDiagnostic(
        health, "duplicate-key",
        "graphics ABI artifact contains duplicate JSON object key: " +
            duplicate->path);
    return health;
  }

  health.schemaVersion = objectUnsignedMember(*document, "schemaVersion");
  PackageGraphicsAbiSummary summary;
  const std::optional<std::string> module =
      objectStringMember(*document, "module");
  const std::optional<std::string> target =
      objectStringMember(*document, "target");
  if (!health.schemaVersion || *health.schemaVersion != 1) {
    addGraphicsAbiDiagnostic(
        health, "invalid-contract",
        "graphics ABI sidecar schemaVersion must be 1");
  }
  if (!module || module->empty()) {
    addGraphicsAbiDiagnostic(health, "invalid-contract",
                             "graphics ABI sidecar module must be a string");
  } else {
    summary.module = *module;
  }
  if (!target || !isKnownPackageTargetName(*target)) {
    addGraphicsAbiDiagnostic(
        health, "invalid-contract",
        "graphics ABI sidecar target must be a supported target string");
  } else {
    summary.target = *target;
  }

  if (const std::optional<std::uintmax_t> count =
          graphicsAbiArrayCount(*document, "entryPoints", health)) {
    summary.entryPointCount = *count;
  }
  if (const std::optional<std::uintmax_t> count =
          graphicsAbiArrayCount(*document, "vertexInputs", health)) {
    summary.vertexInputCount = *count;
  }
  if (const std::optional<std::uintmax_t> count =
          graphicsAbiArrayCount(*document, "varyings", health)) {
    summary.varyingCount = *count;
  }
  if (const std::optional<std::uintmax_t> count =
          graphicsAbiArrayCount(*document, "fragmentOutputs", health)) {
    summary.fragmentOutputCount = *count;
  }
  if (const std::optional<std::uintmax_t> count =
          graphicsAbiArrayCount(*document, "builtins", health)) {
    summary.builtinCount = *count;
  }
  if (const std::optional<std::uintmax_t> count =
          graphicsAbiArrayCount(*document, "resources", health)) {
    summary.resourceCount = *count;
  }
  if (const std::optional<std::uintmax_t> count =
          graphicsAbiArrayCount(*document, "abiRecords", health)) {
    summary.abiRecordCount = *count;
  }

  if (!health.diagnostics.empty()) {
    health.health = "invalid";
    return health;
  }
  if (summary.module != metadata.module) {
    addGraphicsAbiDiagnostic(
        health, "package-metadata-mismatch",
        "graphics ABI sidecar module must match package module '" +
            metadata.module + "'");
  }
  if (summary.target != metadata.target) {
    addGraphicsAbiDiagnostic(
        health, "package-metadata-mismatch",
        "graphics ABI sidecar target must match package target '" +
            metadata.target + "'");
  }
  if (!health.diagnostics.empty()) {
    health.health = "drift";
    return health;
  }

  health.health = "ok";
  health.summary = std::move(summary);
  return health;
}

std::optional<PackageMetadata>
loadPackageMetadata(const std::filesystem::path &packagePath,
                    DiagnosticEngine &diagnostics,
                    const PackageMetadataLoadOptions &options) {
  std::optional<PackageSource> source =
      loadPackageSource(packagePath, diagnostics, options);
  if (!source) {
    return std::nullopt;
  }

  PackageMetadata metadata;
  metadata.packagePath = packagePath;
  metadata.packageFormat = source->format;
  const std::filesystem::path manifestPath =
      source->format == "directory"
          ? packagePath / "manifest.json"
          : std::filesystem::path(packagePath.string() + "!/manifest.json");
  const std::filesystem::path reflectionPath =
      source->format == "directory"
          ? packagePath / "reflection.json"
          : std::filesystem::path(packagePath.string() + "!/reflection.json");
  const std::filesystem::path diagnosticsPath =
      source->format == "directory"
          ? packagePath / "diagnostics.json"
          : std::filesystem::path(packagePath.string() + "!/diagnostics.json");
  metadata.manifestLocation = sourceStartLocation(*source, "manifest.json");
  metadata.reflectionLocation = sourceStartLocation(*source, "reflection.json");
  metadata.diagnosticsLocation =
      sourceStartLocation(*source, "diagnostics.json");
  metadata.rootFiles.push_back(
      rootFileRecord(*source, "manifest", "manifest.json"));
  metadata.rootFiles.push_back(
      rootFileRecord(*source, "reflection", "reflection.json"));
  metadata.rootFiles.push_back(
      rootFileRecord(*source, "diagnostics", "diagnostics.json"));

  auto manifest = readJsonObjectFromSource(*source, "manifest.json", "manifest",
                                           diagnostics, options);
  auto reflection = readJsonObjectFromSource(
      *source, "reflection.json", "reflection", diagnostics, options);
  auto packageDiagnostics = readJsonObjectFromSource(
      *source, "diagnostics.json", "diagnostics", diagnostics, options);
  if (!manifest || !reflection || !packageDiagnostics) {
    return std::nullopt;
  }
  metadata.documents.manifest = std::move(*manifest);
  metadata.documents.reflection = std::move(*reflection);
  metadata.documents.diagnostics = std::move(*packageDiagnostics);
  setRootFileRecordLocation(metadata.rootFiles, "manifest", manifestPath,
                            metadata.documents.manifest);
  setRootFileRecordLocation(metadata.rootFiles, "reflection", reflectionPath,
                            metadata.documents.reflection);
  setRootFileRecordLocation(metadata.rootFiles, "diagnostics", diagnosticsPath,
                            metadata.documents.diagnostics);

  if (!parsePackageArtifactRequirements(
          manifestPath, metadata.documents.manifest, diagnostics, options,
          metadata.artifactRequirements)) {
    return std::nullopt;
  }
  if (!parseTargetLegalizationToolRequirements(
          manifestPath, metadata.documents.manifest, diagnostics, options,
          metadata.targetLegalizationToolRequirements)) {
    return std::nullopt;
  }

  const std::optional<JsonRange> artifactsRange =
      findObjectMember(metadata.documents.manifest, "artifacts");
  if (!artifactsRange) {
    diagnostics.error(diagnosticCode(options, "missing-artifacts"),
                      "package manifest is missing artifacts object",
                      metadata.manifestLocation);
    return std::nullopt;
  }
  metadata.artifactsLocation = sourceLocationForRange(
      manifestPath, metadata.documents.manifest, *artifactsRange);
  const std::string_view artifactsObject(
      metadata.documents.manifest.data() + artifactsRange->begin,
      artifactsRange->end - artifactsRange->begin);
  StringObjectMembers artifactValues =
      collectStringObjectMembers(artifactsObject);
  if (!artifactValues.valid || artifactValues.members.empty()) {
    diagnostics.error(
        diagnosticCode(options, "invalid-artifacts"),
        "package manifest artifacts must be a JSON object with string values",
        *metadata.artifactsLocation);
    return std::nullopt;
  }

  for (const StringObjectMember &member : artifactValues.members) {
    SourceLocation memberLocation = sourceLocationForRange(
        manifestPath, metadata.documents.manifest,
        offsetRange(member.valueRange, artifactsRange->begin));
    if (member.name == "nativeBinaryStatus") {
      metadata.nativeBinaryStatus = member.value;
      metadata.nativeBinaryStatusLocation = std::move(memberLocation);
      continue;
    }
    if (member.name == "debugMetadata") {
      metadata.debugMetadataArtifactPresent = true;
    }
    if (member.name == "hirSourceMap") {
      metadata.hirSourceMapArtifactPresent = true;
    }
    if (member.name == "sourceRemap") {
      metadata.sourceRemapArtifactPresent = true;
    }
    if (member.name == "backendSourceMap") {
      metadata.backendSourceMapArtifactPresent = true;
    }
    if (member.name == "nativeProfile") {
      metadata.nativeProfileArtifactPresent = true;
    }
    if (member.name == kNativeArtifactDescriptorArtifact) {
      metadata.nativeArtifactDescriptorArtifactPresent = true;
    }
    metadata.artifacts.push_back(artifactRecord(
        *source, member.name, member.value, std::move(memberLocation)));
  }
  metadata.debugArtifactsPresent = metadata.debugMetadataArtifactPresent &&
                                   metadata.hirSourceMapArtifactPresent;

  const std::optional<StringMember> module =
      findStringMemberRecord(metadata.documents.manifest, "module");
  const std::optional<StringMember> target =
      findStringMemberRecord(metadata.documents.manifest, "target");
  if (!module || !target) {
    diagnostics.error(
        diagnosticCode(options, "invalid-manifest"),
        "package manifest must contain string module and target fields",
        metadata.manifestLocation);
    return std::nullopt;
  }
  if (!isKnownPackageTargetName(target->value)) {
    diagnostics.error(diagnosticCode(options, "invalid-manifest"),
                      "package manifest target is not supported by " +
                          options.commandName + ": " + target->value,
                      sourceLocationForRange(manifestPath,
                                             metadata.documents.manifest,
                                             target->valueRange));
    return std::nullopt;
  }
  metadata.module = module->value;
  metadata.target = target->value;
  if (!validatePackageArtifactRequirementsManifestTarget(metadata, diagnostics,
                                                        options)) {
    return std::nullopt;
  }
  if (!validateTargetLegalizationToolRequirementsManifestTarget(
          metadata, diagnostics, options)) {
    return std::nullopt;
  }
  if (metadata.nativeBinaryStatus &&
      !isKnownPackageNativeBinaryStatus(*metadata.nativeBinaryStatus)) {
    diagnostics.error(diagnosticCode(options, "invalid-manifest"),
                      "package manifest nativeBinaryStatus is invalid: " +
                          *metadata.nativeBinaryStatus,
                      metadata.nativeBinaryStatusLocation.value_or(
                          *metadata.artifactsLocation));
    return std::nullopt;
  }

  const std::optional<JsonRange> sourceHashRange =
      findObjectMember(metadata.documents.manifest, "sourceHash");
  if (sourceHashRange) {
    metadata.sourceHashLocation = sourceLocationForRange(
        manifestPath, metadata.documents.manifest, *sourceHashRange);
    const std::string_view sourceHashObject(
        metadata.documents.manifest.data() + sourceHashRange->begin,
        sourceHashRange->end - sourceHashRange->begin);
    const StringObjectMembers sourceHashValues =
        collectStringObjectMembers(sourceHashObject);
    if (sourceHashValues.valid) {
      for (const StringObjectMember &member : sourceHashValues.members) {
        SourceLocation memberLocation = sourceLocationForRange(
            manifestPath, metadata.documents.manifest,
            offsetRange(member.valueRange, sourceHashRange->begin));
        if (member.name == "algorithm") {
          metadata.sourceHashAlgorithm = member.value;
          metadata.sourceHashAlgorithmLocation = std::move(memberLocation);
        } else if (member.name == "value") {
          metadata.sourceHashValue = member.value;
          metadata.sourceHashValueLocation = std::move(memberLocation);
        }
      }
    }
  }

  const std::optional<StringMember> reflectionNativeBinary =
      findStringMemberRecord(metadata.documents.reflection, "nativeBinary");
  if (reflectionNativeBinary) {
    metadata.reflectionNativeBinary = reflectionNativeBinary->value;
    metadata.reflectionNativeBinaryLocation =
        sourceLocationForRange(reflectionPath, metadata.documents.reflection,
                               reflectionNativeBinary->valueRange);
  }
  collectReflectionResources(reflectionPath, metadata.documents.reflection,
                             metadata.reflectionResources);
  collectReflectionTargetResourceBindings(
      reflectionPath, metadata.documents.reflection,
      metadata.reflectionTargetResourceBindings);
  collectReflectionTargetFeatures(reflectionPath, metadata.documents.reflection,
                                  metadata.reflectionTargetFeatures);
  return metadata;
}

} // namespace crossgl
