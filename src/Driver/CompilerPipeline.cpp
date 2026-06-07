#include "crossgl/Driver/CompilerPipeline.h"

#include "crossgl/Frontend/Lexer.h"
#include "crossgl/Frontend/Parser.h"

#include <fstream>
#include <iomanip>
#include <sstream>
#include <utility>
#include <vector>

namespace crossgl {
namespace {

struct InvalidSourceByte {
  std::size_t offset = 0;
  std::string message;
};

SourceLocation sourceStartLocation(const std::filesystem::path &path) {
  SourceLocation location;
  location.file = path.lexically_normal().generic_string();
  return location;
}

std::filesystem::path normalizedLogicalPath(const std::filesystem::path &path) {
  if (path.empty()) {
    return "<memory>";
  }
  return path.lexically_normal();
}

SourceLocation sourceByteLocation(const std::filesystem::path &path,
                                  std::string_view source, std::size_t offset) {
  SourceLocation location = sourceStartLocation(path);
  std::size_t line = 1;
  std::size_t column = 1;
  for (std::size_t index = 0; index < offset && index < source.size(); ++index) {
    if (source[index] == '\n') {
      ++line;
      column = 1;
    } else {
      ++column;
    }
  }

  location.line = line;
  location.column = column;
  location.offset = offset;
  location.length = offset < source.size() ? 1 : 0;
  location.endLine = line;
  location.endColumn = column + location.length;
  location.endOffset = offset + location.length;
  return location;
}

bool isUtf8Continuation(unsigned char byte) { return (byte & 0xc0) == 0x80; }

bool hasUtf8Continuation(std::string_view source, std::size_t offset) {
  return offset < source.size() &&
         isUtf8Continuation(static_cast<unsigned char>(source[offset]));
}

bool hasUtf8ByteInRange(std::string_view source, std::size_t offset,
                        unsigned char lower, unsigned char upper) {
  if (offset >= source.size()) {
    return false;
  }
  const unsigned char byte = static_cast<unsigned char>(source[offset]);
  return byte >= lower && byte <= upper;
}

std::string sourceByteHex(unsigned char byte) {
  std::ostringstream out;
  out << "0x" << std::uppercase << std::hex << std::setw(2)
      << std::setfill('0') << static_cast<int>(byte);
  return out.str();
}

std::optional<InvalidSourceByte> findInvalidSourceByte(std::string_view source) {
  std::size_t offset = 0;
  while (offset < source.size()) {
    const unsigned char byte = static_cast<unsigned char>(source[offset]);
    if (byte == 0) {
      return InvalidSourceByte{offset,
                               "source contains an embedded NUL byte"};
    }
    if (byte < 0x80) {
      ++offset;
      continue;
    }

    const auto invalidByte = [&]() {
      return InvalidSourceByte{
          offset, "source contains invalid UTF-8 byte " + sourceByteHex(byte)};
    };
    const auto invalidSequence = [&]() {
      return InvalidSourceByte{offset,
                               "source contains an invalid UTF-8 byte sequence"};
    };

    if (byte >= 0xc2 && byte <= 0xdf) {
      if (!hasUtf8Continuation(source, offset + 1)) {
        return invalidSequence();
      }
      offset += 2;
      continue;
    }
    if (byte == 0xe0) {
      if (!hasUtf8ByteInRange(source, offset + 1, 0xa0, 0xbf) ||
          !hasUtf8Continuation(source, offset + 2)) {
        return invalidSequence();
      }
      offset += 3;
      continue;
    }
    if (byte >= 0xe1 && byte <= 0xec) {
      if (!hasUtf8Continuation(source, offset + 1) ||
          !hasUtf8Continuation(source, offset + 2)) {
        return invalidSequence();
      }
      offset += 3;
      continue;
    }
    if (byte == 0xed) {
      if (!hasUtf8ByteInRange(source, offset + 1, 0x80, 0x9f) ||
          !hasUtf8Continuation(source, offset + 2)) {
        return invalidSequence();
      }
      offset += 3;
      continue;
    }
    if (byte >= 0xee && byte <= 0xef) {
      if (!hasUtf8Continuation(source, offset + 1) ||
          !hasUtf8Continuation(source, offset + 2)) {
        return invalidSequence();
      }
      offset += 3;
      continue;
    }
    if (byte == 0xf0) {
      if (!hasUtf8ByteInRange(source, offset + 1, 0x90, 0xbf) ||
          !hasUtf8Continuation(source, offset + 2) ||
          !hasUtf8Continuation(source, offset + 3)) {
        return invalidSequence();
      }
      offset += 4;
      continue;
    }
    if (byte >= 0xf1 && byte <= 0xf3) {
      if (!hasUtf8Continuation(source, offset + 1) ||
          !hasUtf8Continuation(source, offset + 2) ||
          !hasUtf8Continuation(source, offset + 3)) {
        return invalidSequence();
      }
      offset += 4;
      continue;
    }
    if (byte == 0xf4) {
      if (!hasUtf8ByteInRange(source, offset + 1, 0x80, 0x8f) ||
          !hasUtf8Continuation(source, offset + 2) ||
          !hasUtf8Continuation(source, offset + 3)) {
        return invalidSequence();
      }
      offset += 4;
      continue;
    }

    return invalidByte();
  }
  return std::nullopt;
}

std::optional<std::string> readTextFile(const std::filesystem::path &path,
                                        DiagnosticEngine &diagnostics) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    diagnostics.error("io.read-failed", "failed to read '" + path.string() + "'",
                      sourceStartLocation(path));
    return std::nullopt;
  }
  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    diagnostics.error("io.read-failed", "failed to read '" + path.string() + "'",
                      sourceStartLocation(path));
    return std::nullopt;
  }
  return buffer.str();
}

bool validateSourceBytes(const std::filesystem::path &path,
                         std::string_view source,
                         DiagnosticEngine &diagnostics) {
  const std::optional<InvalidSourceByte> invalid = findInvalidSourceByte(source);
  if (!invalid) {
    return true;
  }
  diagnostics.error("io.invalid-source-byte", invalid->message,
                    sourceByteLocation(path, source, invalid->offset));
  return false;
}

std::optional<CompilerModule>
loadCompilerModuleFromSourceBuffer(std::filesystem::path logicalPath,
                                   std::string source,
                                   DiagnosticEngine &diagnostics,
                                   CompilerModuleOptions options) {
  logicalPath = normalizedLogicalPath(logicalPath);
  if (!validateSourceBytes(logicalPath, source, diagnostics)) {
    return std::nullopt;
  }

  Lexer lexer(logicalPath.generic_string(), source, diagnostics);
  std::vector<Token> tokens = lexer.lex();
  if (diagnostics.hasErrors()) {
    return std::nullopt;
  }

  Parser parser(tokens, diagnostics);
  std::optional<ShaderModule> ast = parser.parseModule();
  if (!ast || diagnostics.hasErrors()) {
    return std::nullopt;
  }

  std::optional<HIRModule> hir = buildHIR(*ast, diagnostics);
  if (!hir || diagnostics.hasErrors()) {
    return std::nullopt;
  }
  HIRPassPipelineConfig passConfig;
  passConfig.optimizationLevel = options.optimizationLevel;
  passConfig.validateBackendInput = options.validateBackendInput;
  HIRPassPipelineResult optimization =
      runHIRPassPipeline(*hir, diagnostics, passConfig);
  if (diagnostics.hasErrors()) {
    return std::nullopt;
  }

  return CompilerModule{std::move(logicalPath), std::move(source),
                        std::move(*ast), std::move(*hir), optimization};
}

} // namespace

std::optional<CompilerModule>
loadCompilerModule(const std::filesystem::path &inputPath,
                   DiagnosticEngine &diagnostics) {
  return loadCompilerModule(inputPath, diagnostics, CompilerModuleOptions{});
}

std::optional<CompilerModule>
loadCompilerModule(const std::filesystem::path &inputPath,
                   DiagnosticEngine &diagnostics,
                   CompilerModuleOptions options) {
  auto source = readTextFile(inputPath, diagnostics);
  if (!source) {
    return std::nullopt;
  }
  return loadCompilerModuleFromSourceBuffer(
      options.logicalPath.value_or(inputPath), std::move(*source), diagnostics,
      options);
}

std::optional<CompilerModule>
loadCompilerModuleFromSource(const SourceInput &input,
                             DiagnosticEngine &diagnostics) {
  return loadCompilerModuleFromSource(input, diagnostics,
                                      CompilerModuleOptions{});
}

std::optional<CompilerModule>
loadCompilerModuleFromSource(const SourceInput &input,
                             DiagnosticEngine &diagnostics,
                             CompilerModuleOptions options) {
  return loadCompilerModuleFromSourceBuffer(input.logicalPath, input.source,
                                            diagnostics, options);
}

} // namespace crossgl
