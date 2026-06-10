#pragma once

#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "crossgl/Basic/Diagnostic.h"

namespace crossgl {

struct SourceRemapEntry {
  SourceLocation generated;
  SourceLocation original;
};

struct SourceRemap {
  int schemaVersion = 1;
  std::string generatedFile;
  std::vector<SourceRemapEntry> mappings;
  std::optional<std::string> documentPath;
  std::optional<std::string> documentSha256;
  std::optional<std::uintmax_t> documentSizeBytes;
};

std::optional<SourceRemap> parseSourceRemap(std::string_view text,
                                            DiagnosticEngine &diagnostics,
                                            SourceLocation documentLocation = {});
std::optional<SourceRemap> loadSourceRemapMetadata(
    std::string_view metadata, const std::filesystem::path &baseDirectory,
    SourceLocation metadataLocation, DiagnosticEngine &diagnostics);
std::optional<SourceRemap> loadSourceRemap(const std::filesystem::path &path,
                                           DiagnosticEngine &diagnostics);
bool validateSourceRemapGeneratedFile(const SourceRemap &remap,
                                      const std::filesystem::path &inputPath,
                                      DiagnosticEngine &diagnostics,
                                      SourceLocation documentLocation = {});
std::optional<SourceLocation> remapSourceLocation(const SourceRemap &remap,
                                                  const SourceLocation &location);
std::vector<Diagnostic>
diagnosticsWithOriginalSourceLocations(const std::vector<Diagnostic> &diagnostics,
                                       const SourceRemap &remap);

} // namespace crossgl
