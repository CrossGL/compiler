#include "crossgl/Basic/Json.h"

#include <iomanip>
#include <sstream>

namespace crossgl {

namespace {

void appendSourceLocationJson(std::ostringstream &out,
                              const SourceLocation &location,
                              std::string_view indent) {
  out << "{\n"
      << indent << "  \"file\": \"" << escapeJson(location.file) << "\",\n"
      << indent << "  \"line\": " << location.line << ",\n"
      << indent << "  \"column\": " << location.column << ",\n"
      << indent << "  \"offset\": " << location.offset << ",\n"
      << indent << "  \"length\": " << location.length << ",\n"
      << indent << "  \"endLine\": " << location.endLine << ",\n"
      << indent << "  \"endColumn\": " << location.endColumn << ",\n"
      << indent << "  \"endOffset\": " << location.endOffset << "\n"
      << indent << "}";
}

} // namespace

std::string escapeJson(std::string_view text) {
  std::ostringstream out;
  for (unsigned char ch : text) {
    switch (ch) {
    case '"':
      out << "\\\"";
      break;
    case '\\':
      out << "\\\\";
      break;
    case '\b':
      out << "\\b";
      break;
    case '\f':
      out << "\\f";
      break;
    case '\n':
      out << "\\n";
      break;
    case '\r':
      out << "\\r";
      break;
    case '\t':
      out << "\\t";
      break;
    default:
      if (ch < 0x20) {
        out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
            << static_cast<int>(ch) << std::dec;
      } else {
        out << static_cast<char>(ch);
      }
      break;
    }
  }
  return out.str();
}

std::string diagnosticsToJson(const std::vector<Diagnostic> &diagnostics) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"diagnostics\": [";
  for (std::size_t i = 0; i < diagnostics.size(); ++i) {
    const Diagnostic &diagnostic = diagnostics[i];
    if (i != 0) {
      out << ",";
    }
    out << "\n    {\n"
        << "      \"severity\": \"" << escapeJson(toString(diagnostic.severity))
        << "\",\n"
        << "      \"code\": \"" << escapeJson(diagnostic.code) << "\",\n"
        << "      \"message\": \"" << escapeJson(diagnostic.message) << "\",\n"
        << "      \"location\": ";
    appendSourceLocationJson(out, diagnostic.location, "      ");
    if (diagnostic.originalLocation) {
      out << ",\n"
          << "      \"originalLocation\": ";
      appendSourceLocationJson(out, *diagnostic.originalLocation, "      ");
    }
    if (!diagnostic.target.empty()) {
      out << ",\n"
          << "      \"target\": \"" << escapeJson(diagnostic.target) << "\"";
    }
    if (!diagnostic.missingCapabilities.empty()) {
      out << ",\n"
          << "      \"missingCapabilities\": [";
      for (std::size_t capabilityIndex = 0;
           capabilityIndex < diagnostic.missingCapabilities.size();
           ++capabilityIndex) {
        if (capabilityIndex != 0) {
          out << ", ";
        }
        out << "\"" << escapeJson(diagnostic.missingCapabilities[capabilityIndex])
            << "\"";
      }
      out << "]";
    }
    out << "\n"
        << "    }";
  }
  if (!diagnostics.empty()) {
    out << "\n  ";
  }
  out << "]\n}\n";
  return out.str();
}

} // namespace crossgl
