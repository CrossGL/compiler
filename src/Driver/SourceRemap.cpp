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

bool looksLikeCrossTLProjectPortabilityReport(std::string_view object) {
  return objectStringMember(object, "kind") ==
         "crosstl-project-portability-report";
}

bool looksLikeCrossTLArtifactSourceMap(std::string_view object) {
  return objectStringMember(object, "kind") == "crosstl-artifact-source-map";
}

bool looksLikeCrossGLBackendSourceMap(std::string_view object) {
  return objectStringMember(object, "kind") == "crossgl.backendSourceMap";
}

bool looksLikeCrossGLSourceRemapProvenance(std::string_view object) {
  return objectStringMember(object, "kind") ==
             "crossgl.sourceRemapProvenance" ||
         objectStringMember(object, "contractVersion") ==
             "source-remap-provenance-v1";
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

std::optional<std::size_t> sourceRemapSizeMember(std::string_view object,
                                                 std::string_view field) {
  const std::optional<std::uintmax_t> value = objectUnsignedMember(object, field);
  if (!value ||
      *value > static_cast<std::uintmax_t>(std::numeric_limits<std::size_t>::max())) {
    return std::nullopt;
  }
  return static_cast<std::size_t>(*value);
}

std::optional<std::string>
sourceRemapMetadataHash(std::string_view metadata,
                        DiagnosticEngine &diagnostics,
                        const SourceLocation &metadataLocation) {
  const std::optional<std::string_view> hash =
      findObjectMemberValue(metadata, "hash");
  if (!hash) {
    return std::nullopt;
  }
  if (!isJsonObjectDocument(*hash)) {
    reportInvalidRemap(diagnostics,
                       "sourceRemap.hash must be a JSON object",
                       metadataLocation);
    return std::nullopt;
  }
  const std::optional<std::string> algorithm =
      objectStringMember(*hash, "algorithm");
  const std::optional<std::string> value = objectStringMember(*hash, "value");
  if (!algorithm || *algorithm != "sha256" || !value ||
      !isLowercaseSha256(*value)) {
    reportInvalidRemap(
        diagnostics,
        "sourceRemap.hash must contain sha256 algorithm and 64 lowercase "
        "hexadecimal value",
        metadataLocation);
    return std::nullopt;
  }
  return value;
}

std::optional<std::string>
requiredSourceRemapMetadataHash(std::string_view metadata,
                                DiagnosticEngine &diagnostics,
                                const SourceLocation &metadataLocation) {
  if (!findObjectMemberValue(metadata, "hash")) {
    reportInvalidRemap(
        diagnostics,
        "sourceRemap.hash must contain sha256 algorithm and 64 lowercase "
        "hexadecimal value",
        metadataLocation);
    return std::nullopt;
  }
  return sourceRemapMetadataHash(metadata, diagnostics, metadataLocation);
}

std::optional<std::uintmax_t>
sourceRemapMetadataSizeBytes(std::string_view metadata,
                             DiagnosticEngine &diagnostics,
                             const SourceLocation &metadataLocation) {
  if (!findObjectMemberValue(metadata, "sizeBytes")) {
    return std::nullopt;
  }
  const std::optional<std::uintmax_t> sizeBytes =
      objectUnsignedMember(metadata, "sizeBytes");
  if (!sizeBytes) {
    reportInvalidRemap(diagnostics,
                       "sourceRemap.sizeBytes must be a non-negative integer",
                       metadataLocation);
    return std::nullopt;
  }
  return sizeBytes;
}

std::optional<std::uintmax_t>
requiredSourceRemapMetadataSizeBytes(std::string_view metadata,
                                     DiagnosticEngine &diagnostics,
                                     const SourceLocation &metadataLocation) {
  if (!findObjectMemberValue(metadata, "sizeBytes")) {
    reportInvalidRemap(diagnostics,
                       "sourceRemap.sizeBytes must be recorded",
                       metadataLocation);
    return std::nullopt;
  }
  return sourceRemapMetadataSizeBytes(metadata, diagnostics, metadataLocation);
}

bool validateSourceRemapMetadataSchemaVersion(
    std::string_view metadata, DiagnosticEngine &diagnostics,
    const SourceLocation &metadataLocation) {
  const std::optional<std::uintmax_t> schemaVersion =
      objectUnsignedMember(metadata, "schemaVersion");
  if (!schemaVersion || *schemaVersion != 1) {
    reportInvalidRemap(diagnostics,
                       "sourceRemap.schemaVersion must be 1",
                       metadataLocation);
    return false;
  }
  return true;
}

bool validateSourceRemapMetadataGranularity(
    std::string_view metadata, DiagnosticEngine &diagnostics,
    const SourceLocation &metadataLocation) {
  const std::optional<std::string> granularity =
      objectStringMember(metadata, "mappingGranularity");
  if (!granularity ||
      (*granularity != "file" && *granularity != "line" &&
       *granularity != "statement" && *granularity != "token")) {
    reportInvalidRemap(
        diagnostics,
        "sourceRemap.mappingGranularity must be file, line, statement, or "
        "token",
        metadataLocation);
    return false;
  }
  return true;
}

bool sourceRemapSpanIsSingleLine(const SourceLocation &location) {
  return location.line == location.endLine;
}

bool validateSourceRemapMetadataGranularityContract(
    std::string_view metadata, const SourceRemap &remap,
    DiagnosticEngine &diagnostics, const SourceLocation &metadataLocation) {
  const std::optional<std::string> granularity =
      objectStringMember(metadata, "mappingGranularity");
  if (!granularity) {
    return true;
  }

  if (*granularity == "file") {
    if (remap.mappings.size() == 1) {
      return true;
    }
    reportInvalidRemap(
        diagnostics,
        "sourceRemap.mappingGranularity file requires exactly one referenced "
        "sidecar mapping",
        metadataLocation);
    return false;
  }

  if (*granularity == "line") {
    for (std::size_t index = 0; index < remap.mappings.size(); ++index) {
      const SourceRemapEntry &mapping = remap.mappings[index];
      if (sourceRemapSpanIsSingleLine(mapping.generated) &&
          sourceRemapSpanIsSingleLine(mapping.original)) {
        continue;
      }
      reportInvalidRemap(
          diagnostics,
          "sourceRemap.mappings[" + std::to_string(index) +
              "] must stay within one generated and original line for line "
              "granularity",
          metadataLocation);
      return false;
    }
  }

  return true;
}

bool validateOptionalSourceRemapMetadataString(
    std::string_view metadata, std::string_view field,
    DiagnosticEngine &diagnostics, const SourceLocation &metadataLocation) {
  if (!findObjectMemberValue(metadata, field)) {
    return true;
  }
  if (objectStringMember(metadata, field)) {
    return true;
  }
  reportInvalidRemap(diagnostics,
                     "sourceRemap." + std::string(field) + " must be a string",
                     metadataLocation);
  return false;
}

bool validateOptionalSourceRemapMetadataTarget(
    std::string_view metadata, DiagnosticEngine &diagnostics,
    const SourceLocation &metadataLocation) {
  const std::optional<std::string> target =
      objectStringMember(metadata, "target");
  if (!target) {
    return true;
  }
  if (*target == "cgl" || *target == "crossgl") {
    return true;
  }
  reportInvalidRemap(diagnostics,
                     "sourceRemap.target expected only for CrossGL target "
                     "artifacts",
                     metadataLocation);
  return false;
}

std::optional<std::string>
readSourceRemapFileText(const std::filesystem::path &path,
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
  return buffer.str();
}

std::optional<SourceRemap>
parseLoadedSourceRemap(std::string text, const std::filesystem::path &path,
                       DiagnosticEngine &diagnostics) {
  std::optional<SourceRemap> remap =
      parseSourceRemap(text, diagnostics, documentStartLocation(path));
  if (remap) {
    remap->documentPath = path.lexically_normal().generic_string();
    remap->documentSha256 = sha256(text);
    remap->documentSizeBytes = text.size();
  }
  return remap;
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

bool generatedSpansOverlap(const SourceLocation &left,
                           const SourceLocation &right) {
  if (left.file != right.file) {
    return false;
  }
  return left.offset < right.endOffset && right.offset < left.endOffset;
}

bool generatedSpanOrderDrifts(const SourceLocation &previous,
                              const SourceLocation &current) {
  if (previous.file != current.file) {
    return false;
  }
  return current.offset < previous.endOffset;
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

std::optional<SourceRemap> loadSourceRemapMetadata(
    std::string_view metadata, const std::filesystem::path &baseDirectory,
    SourceLocation metadataLocation, DiagnosticEngine &diagnostics) {
  if (!validateSourceRemapMetadataSchemaVersion(metadata, diagnostics,
                                                metadataLocation) ||
      !validateSourceRemapMetadataGranularity(metadata, diagnostics,
                                              metadataLocation)) {
    return std::nullopt;
  }

  const std::optional<std::string> sidecarPath =
      objectStringMember(metadata, "path");
  if (!sidecarPath || !isStableRelativePath(*sidecarPath)) {
    reportInvalidRemap(diagnostics,
                       "sourceRemap.path must be a stable relative POSIX path",
                       std::move(metadataLocation));
    return std::nullopt;
  }

  const std::optional<std::uintmax_t> expectedSize =
      requiredSourceRemapMetadataSizeBytes(metadata, diagnostics,
                                           metadataLocation);
  const std::optional<std::string> expectedHash =
      requiredSourceRemapMetadataHash(metadata, diagnostics, metadataLocation);
  if (!expectedSize || !expectedHash) {
    return std::nullopt;
  }

  const std::filesystem::path resolvedSidecarPath =
      (baseDirectory / *sidecarPath).lexically_normal();
  std::optional<std::string> sidecarText =
      readSourceRemapFileText(resolvedSidecarPath, diagnostics);
  if (!sidecarText) {
    return std::nullopt;
  }

  if (*expectedSize != sidecarText->size()) {
    reportInvalidRemap(
        diagnostics,
        "sourceRemap.sizeBytes " + std::to_string(*expectedSize) +
            " does not match referenced sidecar '" +
            resolvedSidecarPath.generic_string() + "' size " +
            std::to_string(sidecarText->size()),
        metadataLocation);
    return std::nullopt;
  }
  const std::string actualHash = sha256(*sidecarText);
  if (*expectedHash != actualHash) {
    reportInvalidRemap(
        diagnostics,
        "sourceRemap.hash.value '" + *expectedHash +
            "' does not match referenced sidecar '" +
            resolvedSidecarPath.generic_string() + "' sha256 '" + actualHash +
            "'",
        metadataLocation);
    return std::nullopt;
  }

  std::optional<SourceRemap> remap =
      parseLoadedSourceRemap(std::move(*sidecarText), resolvedSidecarPath,
                             diagnostics);
  if (!remap) {
    return std::nullopt;
  }
  const bool hasGeneratedFile =
      findObjectMemberValue(metadata, "generatedFile").has_value();
  const std::optional<std::string> generatedFile =
      objectStringMember(metadata, "generatedFile");
  if (hasGeneratedFile && !generatedFile) {
    reportInvalidRemap(diagnostics,
                       "sourceRemap.generatedFile must be a string",
                       metadataLocation);
    return std::nullopt;
  }
  if (generatedFile && *generatedFile != remap->generatedFile) {
    reportInvalidRemap(
        diagnostics,
        "sourceRemap.generatedFile '" + *generatedFile +
            "' must match referenced sidecar generatedFile '" +
            remap->generatedFile + "'",
        metadataLocation);
    return std::nullopt;
  }
  const bool hasMappingCount =
      findObjectMemberValue(metadata, "mappingCount").has_value();
  const std::optional<std::uintmax_t> mappingCount =
      objectUnsignedMember(metadata, "mappingCount");
  if (hasMappingCount && !mappingCount) {
    reportInvalidRemap(diagnostics,
                       "sourceRemap.mappingCount must be a non-negative integer",
                       metadataLocation);
    return std::nullopt;
  }
  if (mappingCount && *mappingCount != remap->mappings.size()) {
    reportInvalidRemap(
        diagnostics,
        "sourceRemap.mappingCount " + std::to_string(*mappingCount) +
            " must match referenced sidecar mapping count " +
            std::to_string(remap->mappings.size()),
        metadataLocation);
    return std::nullopt;
  }
  if (!validateSourceRemapMetadataGranularityContract(
          metadata, *remap, diagnostics, metadataLocation)) {
    return std::nullopt;
  }
  if (!validateOptionalSourceRemapMetadataString(
          metadata, "target", diagnostics, metadataLocation) ||
      !validateOptionalSourceRemapMetadataTarget(metadata, diagnostics,
                                                 metadataLocation) ||
      !validateOptionalSourceRemapMetadataString(
          metadata, "sourceBackend", diagnostics, metadataLocation) ||
      !validateOptionalSourceRemapMetadataString(
          metadata, "variant", diagnostics, metadataLocation)) {
    return std::nullopt;
  }
  remap->metadataTarget = objectStringMember(metadata, "target");
  remap->metadataSourceBackend = objectStringMember(metadata, "sourceBackend");
  remap->metadataVariant = objectStringMember(metadata, "variant");
  remap->metadataMappingGranularity =
      objectStringMember(metadata, "mappingGranularity");
  return remap;
}

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
    if (looksLikeCrossTLProjectPortabilityReport(text)) {
      reportInvalidRemap(
          diagnostics,
          "source remap document appears to be a CrossTL project portability "
          "report; pass the compiler sidecar JSON referenced by "
          "artifacts[].sourceRemap.path instead",
          documentLocation);
      return std::nullopt;
    }
    if (looksLikeCrossTLArtifactSourceMap(text)) {
      reportInvalidRemap(
          diagnostics,
          "source remap document appears to be a CrossTL artifact source map; "
          "pass the compiler sidecar JSON referenced by "
          "artifacts[].sourceRemap.path instead",
          documentLocation);
      return std::nullopt;
    }
    if (looksLikeCrossGLBackendSourceMap(text)) {
      reportInvalidRemap(
          diagnostics,
          "source remap document appears to be a CrossGL backend source map; "
          "pass the source-remap-v1 sidecar JSON instead",
          documentLocation);
      return std::nullopt;
    }
    if (looksLikeCrossGLSourceRemapProvenance(text)) {
      reportInvalidRemap(
          diagnostics,
          "source remap document appears to be source-remap provenance; pass "
          "the source-remap-v1 sidecar JSON referenced by sourceRemap.path "
          "instead",
          documentLocation);
      return std::nullopt;
    }
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
                                for (std::size_t priorIndex = 0;
                                     priorIndex < remap.mappings.size();
                                     ++priorIndex) {
                                  if (generatedSpansOverlap(
                                          remap.mappings[priorIndex].generated,
                                          *generated)) {
                                    validMappings = false;
                                    reportInvalidRemap(
                                        diagnostics,
                                        "source remap " + path +
                                            ".generated overlaps mappings[" +
                                            std::to_string(priorIndex) +
                                            "].generated",
                                        documentLocation);
                                    return;
                                  }
                                }
                                if (!remap.mappings.empty()) {
                                  const SourceRemapEntry &previous =
                                      remap.mappings.back();
                                  if (generatedSpanOrderDrifts(
                                          previous.generated, *generated)) {
                                    validMappings = false;
                                    reportInvalidRemap(
                                        diagnostics,
                                        "source remap " + path +
                                            ".generated.offset must be >= "
                                            "mappings[" +
                                            std::to_string(
                                                remap.mappings.size() - 1) +
                                            "].generated.endOffset",
                                        documentLocation);
                                    return;
                                  }
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
  std::optional<std::string> text = readSourceRemapFileText(path, diagnostics);
  if (!text) {
    return std::nullopt;
  }
  if (isJsonObjectDocument(*text) && !findDuplicateJsonKey(*text) &&
      looksLikeProjectReportSourceRemapMetadata(*text)) {
    std::filesystem::path baseDirectory = path.parent_path();
    if (baseDirectory.empty()) {
      baseDirectory = ".";
    }
    return loadSourceRemapMetadata(*text, baseDirectory,
                                   documentStartLocation(path), diagnostics);
  }
  return parseLoadedSourceRemap(std::move(*text), path, diagnostics);
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
