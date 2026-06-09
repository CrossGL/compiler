#include "crossgl/Driver/SourceRemap.h"

#include "crossgl/Basic/SHA256.h"
#include "crossgl/Driver/PackageJson.h"

#include <cctype>
#include <cstdint>
#include <fstream>
#include <initializer_list>
#include <limits>
#include <sstream>
#include <utility>

namespace crossgl {
namespace {

SourceLocation documentStartLocation(const std::filesystem::path &path) {
  SourceLocation location;
  location.file = path.lexically_normal().generic_string();
  return location;
}

std::string normalizedSourcePath(const std::filesystem::path &path) {
  if (path.empty()) {
    return "<memory>";
  }
  return path.lexically_normal().generic_string();
}

void reportInvalidRemap(DiagnosticEngine &diagnostics, std::string message,
                        SourceLocation location) {
  diagnostics.error("io.invalid-source-remap", std::move(message),
                    std::move(location));
}

bool hasWindowsDrivePrefix(std::string_view path) {
  return path.size() >= 2 &&
         std::isalpha(static_cast<unsigned char>(path[0])) && path[1] == ':';
}

bool isStableRelativePath(std::string_view path) {
  if (path.empty() || path.starts_with("/") || path.starts_with("\\") ||
      hasWindowsDrivePrefix(path) || path.find('\\') != std::string_view::npos) {
    return false;
  }
  std::size_t segmentBegin = 0;
  while (segmentBegin <= path.size()) {
    const std::size_t segmentEnd = path.find('/', segmentBegin);
    const std::string_view segment =
        segmentEnd == std::string_view::npos
            ? path.substr(segmentBegin)
            : path.substr(segmentBegin, segmentEnd - segmentBegin);
    if (segment.empty() || segment == "." || segment == "..") {
      return false;
    }
    if (segmentEnd == std::string_view::npos) {
      break;
    }
    segmentBegin = segmentEnd + 1;
  }
  return true;
}

bool sourceSpanIsCoherent(const SourceLocation &location) {
  if (location.line == 0 || location.column == 0 || location.endLine == 0 ||
      location.endColumn == 0 || location.length == 0) {
    return false;
  }
  if (location.endOffset != location.offset + location.length) {
    return false;
  }
  if (location.endLine < location.line) {
    return false;
  }
  return location.endLine != location.line ||
         location.endColumn > location.column;
}

bool objectHasOnlyMembers(std::string_view object,
                          std::initializer_list<std::string_view> allowed,
                          std::string &unexpectedKey) {
  std::size_t position = 0;
  skipWhitespace(object, position);
  if (position >= object.size() || object[position] != '{') {
    return false;
  }
  ++position;
  skipWhitespace(object, position);
  if (position < object.size() && object[position] == '}') {
    ++position;
    skipWhitespace(object, position);
    return position == object.size();
  }

  while (position < object.size()) {
    std::string key;
    if (!parseJsonString(object, position, key)) {
      return false;
    }
    bool allowedMember = false;
    for (const std::string_view allowedKey : allowed) {
      if (key == allowedKey) {
        allowedMember = true;
        break;
      }
    }
    if (!allowedMember) {
      unexpectedKey = std::move(key);
      return false;
    }
    skipWhitespace(object, position);
    if (position >= object.size() || object[position] != ':') {
      return false;
    }
    ++position;
    skipWhitespace(object, position);
    if (!skipJsonValue(object, position)) {
      return false;
    }
    skipWhitespace(object, position);
    if (position < object.size() && object[position] == ',') {
      ++position;
      skipWhitespace(object, position);
      continue;
    }
    if (position < object.size() && object[position] == '}') {
      ++position;
      skipWhitespace(object, position);
      return position == object.size();
    }
    return false;
  }
  return false;
}

bool looksLikeProjectReportSourceRemapMetadata(std::string_view object) {
  return findObjectMemberValue(object, "path").has_value() &&
         findObjectMemberValue(object, "target").has_value() &&
         findObjectMemberValue(object, "mappingGranularity").has_value() &&
         findObjectMemberValue(object, "mappingCount").has_value();
}

std::optional<std::size_t> sourceRemapSizeMember(std::string_view object,
                                                 std::string_view field) {
  const std::optional<std::uintmax_t> value = objectUnsignedMember(object, field);
  if (!value ||
      *value > static_cast<std::uintmax_t>(std::numeric_limits<std::size_t>::max())) {
    return std::nullopt;
  }
  return static_cast<std::size_t>(*value);
}

std::optional<SourceLocation>
parseSourceRemapLocation(std::string_view object, std::string_view path,
                         DiagnosticEngine &diagnostics,
                         const SourceLocation &documentLocation) {
  if (!isJsonObjectDocument(object)) {
    reportInvalidRemap(diagnostics,
                       std::string(path) + " must be a JSON object",
                       documentLocation);
    return std::nullopt;
  }

  std::string unexpectedKey;
  if (!objectHasOnlyMembers(object,
                            {"file", "line", "column", "offset", "length",
                             "endLine", "endColumn", "endOffset"},
                            unexpectedKey)) {
    reportInvalidRemap(
        diagnostics,
        unexpectedKey.empty()
            ? std::string(path) + " must be a JSON object"
            : std::string(path) + " contains unknown member " + unexpectedKey,
        documentLocation);
    return std::nullopt;
  }

  SourceLocation location;
  if (std::optional<std::string> file = objectStringMember(object, "file")) {
    location.file = *file;
  } else {
    reportInvalidRemap(diagnostics,
                       std::string(path) + ".file must be a string",
                       documentLocation);
    return std::nullopt;
  }

  if (!isStableRelativePath(location.file)) {
    reportInvalidRemap(
        diagnostics,
        std::string(path) +
            ".file must be a stable relative POSIX source path",
        documentLocation);
    return std::nullopt;
  }

  const auto parseSize = [&](std::string_view field)
      -> std::optional<std::size_t> {
    std::optional<std::size_t> value = sourceRemapSizeMember(object, field);
    if (!value) {
      reportInvalidRemap(diagnostics,
                         std::string(path) + "." + std::string(field) +
                             " must be a non-negative integer",
                         documentLocation);
    }
    return value;
  };

  std::optional<std::size_t> line = parseSize("line");
  std::optional<std::size_t> column = parseSize("column");
  std::optional<std::size_t> offset = parseSize("offset");
  std::optional<std::size_t> length = parseSize("length");
  std::optional<std::size_t> endLine = parseSize("endLine");
  std::optional<std::size_t> endColumn = parseSize("endColumn");
  std::optional<std::size_t> endOffset = parseSize("endOffset");
  if (!line || !column || !offset || !length || !endLine || !endColumn ||
      !endOffset) {
    return std::nullopt;
  }

  location.line = *line;
  location.column = *column;
  location.offset = *offset;
  location.length = *length;
  location.endLine = *endLine;
  location.endColumn = *endColumn;
  location.endOffset = *endOffset;
  if (!sourceSpanIsCoherent(location)) {
    reportInvalidRemap(
        diagnostics,
        std::string(path) +
            " must satisfy endOffset == offset + length and ordered line/column spans",
        documentLocation);
    return std::nullopt;
  }

  return location;
}

template <typename Callback>
bool forEachJsonArrayElement(std::string_view arrayText, Callback callback) {
  std::size_t position = 0;
  skipWhitespace(arrayText, position);
  if (position >= arrayText.size() || arrayText[position] != '[') {
    return false;
  }
  ++position;
  skipWhitespace(arrayText, position);
  if (position < arrayText.size() && arrayText[position] == ']') {
    ++position;
    skipWhitespace(arrayText, position);
    return position == arrayText.size();
  }

  std::size_t index = 0;
  while (position < arrayText.size()) {
    const std::size_t valueBegin = position;
    if (!skipJsonValue(arrayText, position)) {
      return false;
    }
    callback(index, arrayText.substr(valueBegin, position - valueBegin));
    ++index;
    skipWhitespace(arrayText, position);
    if (position < arrayText.size() && arrayText[position] == ',') {
      ++position;
      skipWhitespace(arrayText, position);
      continue;
    }
    if (position < arrayText.size() && arrayText[position] == ']') {
      ++position;
      skipWhitespace(arrayText, position);
      return position == arrayText.size();
    }
    return false;
  }
  return false;
}

bool sourcePointBefore(std::size_t line, std::size_t column,
                       std::size_t otherLine, std::size_t otherColumn) {
  return line < otherLine || (line == otherLine && column < otherColumn);
}

bool sourcePointAfter(std::size_t line, std::size_t column,
                      std::size_t otherLine, std::size_t otherColumn) {
  return line > otherLine || (line == otherLine && column > otherColumn);
}

bool generatedSpanContains(const SourceLocation &range,
                           const SourceLocation &location) {
  if (range.file != location.file || location.endOffset < location.offset ||
      location.offset < range.offset || location.endOffset > range.endOffset) {
    return false;
  }
  if (sourcePointBefore(location.line, location.column, range.line,
                        range.column)) {
    return false;
  }
  return !sourcePointAfter(location.endLine, location.endColumn, range.endLine,
                           range.endColumn);
}

std::size_t translateLine(const SourceLocation &generated,
                          const SourceLocation &original, std::size_t line) {
  return original.line + (line - generated.line);
}

std::size_t translateColumn(const SourceLocation &generated,
                            const SourceLocation &original, std::size_t line,
                            std::size_t column) {
  if (line == generated.line) {
    return original.column + (column - generated.column);
  }
  return column;
}

SourceLocation remapInsideEntry(const SourceRemapEntry &entry,
                                const SourceLocation &location) {
  SourceLocation remapped = entry.original;
  remapped.line =
      translateLine(entry.generated, entry.original, location.line);
  remapped.column =
      translateColumn(entry.generated, entry.original, location.line,
                      location.column);
  remapped.offset =
      entry.original.offset + (location.offset - entry.generated.offset);
  remapped.endLine =
      translateLine(entry.generated, entry.original, location.endLine);
  remapped.endColumn =
      translateColumn(entry.generated, entry.original, location.endLine,
                      location.endColumn);
  remapped.endOffset =
      entry.original.offset + (location.endOffset - entry.generated.offset);
  remapped.length = remapped.endOffset - remapped.offset;
  return remapped;
}

} // namespace

std::optional<SourceRemap> parseSourceRemap(std::string_view text,
                                            DiagnosticEngine &diagnostics,
                                            SourceLocation documentLocation) {
  if (!isJsonObjectDocument(text)) {
    reportInvalidRemap(diagnostics,
                       "source remap document must be a JSON object",
                       std::move(documentLocation));
    return std::nullopt;
  }
  if (std::optional<DuplicateJsonKey> duplicate = findDuplicateJsonKey(text)) {
    reportInvalidRemap(diagnostics,
                       "source remap document has duplicate JSON key " +
                           duplicate->path,
                       documentLocation);
    return std::nullopt;
  }
  std::string unexpectedKey;
  if (!objectHasOnlyMembers(text, {"schemaVersion", "generatedFile", "mappings"},
                            unexpectedKey)) {
    if (looksLikeProjectReportSourceRemapMetadata(text)) {
      reportInvalidRemap(
          diagnostics,
          "source remap document appears to be CrossTL project report "
          "sourceRemap metadata; pass the compiler sidecar JSON referenced by "
          "sourceRemap.path instead",
          documentLocation);
      return std::nullopt;
    }
    reportInvalidRemap(
        diagnostics,
        unexpectedKey.empty()
            ? "source remap document must be a JSON object"
            : "source remap document contains unknown member " + unexpectedKey,
        documentLocation);
    return std::nullopt;
  }

  const std::optional<std::uintmax_t> schemaVersion =
      objectUnsignedMember(text, "schemaVersion");
  if (!schemaVersion || *schemaVersion != 1) {
    reportInvalidRemap(diagnostics,
                       "source remap schemaVersion must be 1",
                       documentLocation);
    return std::nullopt;
  }

  SourceRemap remap;
  remap.schemaVersion = 1;
  if (std::optional<std::string> generatedFile =
          objectStringMember(text, "generatedFile")) {
    remap.generatedFile = *generatedFile;
  } else {
    reportInvalidRemap(diagnostics,
                       "source remap generatedFile must be a string",
                       documentLocation);
    return std::nullopt;
  }
  if (!isStableRelativePath(remap.generatedFile)) {
    reportInvalidRemap(
        diagnostics,
        "source remap generatedFile must be a stable relative POSIX path",
        documentLocation);
    return std::nullopt;
  }

  const std::optional<std::string_view> mappingsValue =
      findObjectMemberValue(text, "mappings");
  if (!mappingsValue) {
    reportInvalidRemap(diagnostics,
                       "source remap mappings must be an array",
                       documentLocation);
    return std::nullopt;
  }

  bool validMappings = true;
  bool sawMapping = false;
  const bool parsedMappings =
      forEachJsonArrayElement(*mappingsValue,
                              [&](std::size_t index, std::string_view entryText) {
                                sawMapping = true;
                                if (!isJsonObjectDocument(entryText)) {
                                  validMappings = false;
                                  reportInvalidRemap(
                                      diagnostics,
                                      "source remap mappings[" +
                                          std::to_string(index) +
                                          "] must be an object",
                                      documentLocation);
                                  return;
                                }
                                std::string unexpectedKey;
                                if (!objectHasOnlyMembers(
                                        entryText, {"generated", "original"},
                                        unexpectedKey)) {
                                  validMappings = false;
                                  reportInvalidRemap(
                                      diagnostics,
                                      unexpectedKey.empty()
                                          ? "source remap mappings[" +
                                                std::to_string(index) +
                                                "] must be an object"
                                          : "source remap mappings[" +
                                                std::to_string(index) +
                                                "] contains unknown member " +
                                                unexpectedKey,
                                      documentLocation);
                                  return;
                                }
                                const std::string path =
                                    "mappings[" + std::to_string(index) + "]";
                                const std::optional<std::string_view>
                                    generatedValue =
                                        findObjectMemberValue(entryText,
                                                              "generated");
                                const std::optional<std::string_view>
                                    originalValue =
                                        findObjectMemberValue(entryText,
                                                              "original");
                                if (!generatedValue || !originalValue) {
                                  validMappings = false;
                                  reportInvalidRemap(
                                      diagnostics,
                                      "source remap " + path +
                                          " must contain generated and original spans",
                                      documentLocation);
                                  return;
                                }
                                std::optional<SourceLocation> generated =
                                    parseSourceRemapLocation(
                                        *generatedValue, path + ".generated",
                                        diagnostics, documentLocation);
                                std::optional<SourceLocation> original =
                                    parseSourceRemapLocation(
                                        *originalValue, path + ".original",
                                        diagnostics, documentLocation);
                                if (!generated || !original) {
                                  validMappings = false;
                                  return;
                                }
                                if (generated->file != remap.generatedFile) {
                                  validMappings = false;
                                  reportInvalidRemap(
                                      diagnostics,
                                      "source remap " + path +
                                          ".generated.file must match generatedFile",
                                      documentLocation);
                                  return;
                                }
                                remap.mappings.push_back(
                                    SourceRemapEntry{std::move(*generated),
                                                     std::move(*original)});
                              });

  if (!parsedMappings || !validMappings) {
    if (!parsedMappings) {
      reportInvalidRemap(diagnostics,
                         "source remap mappings must be a JSON array",
                         documentLocation);
    }
    return std::nullopt;
  }
  if (!sawMapping) {
    reportInvalidRemap(diagnostics,
                       "source remap mappings must contain at least one entry",
                       documentLocation);
    return std::nullopt;
  }
  return remap;
}

std::optional<SourceRemap> loadSourceRemap(const std::filesystem::path &path,
                                           DiagnosticEngine &diagnostics) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    diagnostics.error("io.read-failed",
                      "failed to read source remap '" + path.string() + "'",
                      documentStartLocation(path));
    return std::nullopt;
  }
  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    diagnostics.error("io.read-failed",
                      "failed to read source remap '" + path.string() + "'",
                      documentStartLocation(path));
    return std::nullopt;
  }
  const std::string text = buffer.str();
  std::optional<SourceRemap> remap =
      parseSourceRemap(text, diagnostics, documentStartLocation(path));
  if (remap) {
    remap->documentPath = path.lexically_normal().generic_string();
    remap->documentSha256 = sha256(text);
    remap->documentSizeBytes = text.size();
  }
  return remap;
}

bool validateSourceRemapGeneratedFile(const SourceRemap &remap,
                                      const std::filesystem::path &inputPath,
                                      DiagnosticEngine &diagnostics,
                                      SourceLocation documentLocation) {
  const std::string normalizedInputPath = normalizedSourcePath(inputPath);
  if (remap.generatedFile == normalizedInputPath) {
    return true;
  }
  reportInvalidRemap(
      diagnostics,
      "source remap generatedFile '" + remap.generatedFile +
          "' must match compiler input path '" + normalizedInputPath + "'",
      std::move(documentLocation));
  return false;
}

std::optional<SourceLocation> remapSourceLocation(const SourceRemap &remap,
                                                  const SourceLocation &location) {
  for (const SourceRemapEntry &entry : remap.mappings) {
    if (generatedSpanContains(entry.generated, location)) {
      return remapInsideEntry(entry, location);
    }
  }
  return std::nullopt;
}

std::vector<Diagnostic>
diagnosticsWithOriginalSourceLocations(const std::vector<Diagnostic> &diagnostics,
                                       const SourceRemap &remap) {
  std::vector<Diagnostic> remapped = diagnostics;
  for (Diagnostic &diagnostic : remapped) {
    diagnostic.originalLocation =
        remapSourceLocation(remap, diagnostic.location);
  }
  return remapped;
}

} // namespace crossgl
