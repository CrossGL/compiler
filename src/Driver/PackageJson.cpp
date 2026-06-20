#include "crossgl/Driver/PackageJson.h"

#include <algorithm>
#include <cctype>
#include <limits>
#include <utility>

namespace crossgl {
namespace {

int hexDigitValue(char ch) {
  if (ch >= '0' && ch <= '9') {
    return ch - '0';
  }
  if (ch >= 'a' && ch <= 'f') {
    return ch - 'a' + 10;
  }
  if (ch >= 'A' && ch <= 'F') {
    return ch - 'A' + 10;
  }
  return -1;
}

std::optional<std::uint32_t> parseHexCodeUnit(std::string_view text,
                                              std::size_t &position) {
  if (position + 4 > text.size()) {
    return std::nullopt;
  }
  std::uint32_t value = 0;
  for (std::size_t index = 0; index < 4; ++index) {
    const int digit = hexDigitValue(text[position + index]);
    if (digit < 0) {
      return std::nullopt;
    }
    value = (value << 4U) | static_cast<std::uint32_t>(digit);
  }
  position += 4;
  return value;
}

void appendUtf8(std::uint32_t codePoint, std::string &out) {
  if (codePoint <= 0x7F) {
    out.push_back(static_cast<char>(codePoint));
  } else if (codePoint <= 0x7FF) {
    out.push_back(static_cast<char>(0xC0 | (codePoint >> 6U)));
    out.push_back(static_cast<char>(0x80 | (codePoint & 0x3FU)));
  } else if (codePoint <= 0xFFFF) {
    out.push_back(static_cast<char>(0xE0 | (codePoint >> 12U)));
    out.push_back(static_cast<char>(0x80 | ((codePoint >> 6U) & 0x3FU)));
    out.push_back(static_cast<char>(0x80 | (codePoint & 0x3FU)));
  } else {
    out.push_back(static_cast<char>(0xF0 | (codePoint >> 18U)));
    out.push_back(static_cast<char>(0x80 | ((codePoint >> 12U) & 0x3FU)));
    out.push_back(static_cast<char>(0x80 | ((codePoint >> 6U) & 0x3FU)));
    out.push_back(static_cast<char>(0x80 | (codePoint & 0x3FU)));
  }
}

bool parseUnicodeEscape(std::string_view text, std::size_t &position,
                        std::string &out) {
  const std::optional<std::uint32_t> first = parseHexCodeUnit(text, position);
  if (!first) {
    return false;
  }

  constexpr std::uint32_t highSurrogateBegin = 0xD800;
  constexpr std::uint32_t highSurrogateEnd = 0xDBFF;
  constexpr std::uint32_t lowSurrogateBegin = 0xDC00;
  constexpr std::uint32_t lowSurrogateEnd = 0xDFFF;

  std::uint32_t codePoint = *first;
  if (codePoint >= highSurrogateBegin && codePoint <= highSurrogateEnd) {
    if (position + 2 > text.size() || text[position] != '\\' ||
        text[position + 1] != 'u') {
      return false;
    }
    position += 2;
    const std::optional<std::uint32_t> second =
        parseHexCodeUnit(text, position);
    if (!second || *second < lowSurrogateBegin || *second > lowSurrogateEnd) {
      return false;
    }
    codePoint = 0x10000 +
                ((codePoint - highSurrogateBegin) << 10U) +
                (*second - lowSurrogateBegin);
  } else if (codePoint >= lowSurrogateBegin && codePoint <= lowSurrogateEnd) {
    return false;
  }

  appendUtf8(codePoint, out);
  return true;
}

bool skipJsonString(std::string_view text, std::size_t &position) {
  std::string ignored;
  return parseJsonString(text, position, ignored);
}

bool consumeLiteral(std::string_view text, std::size_t &position,
                    std::string_view literal) {
  if (text.substr(position, literal.size()) != literal) {
    return false;
  }
  position += literal.size();
  return true;
}

template <typename Callback>
bool forEachObjectMember(std::string_view text, Callback callback) {
  std::size_t position = 0;
  skipWhitespace(text, position);
  if (position >= text.size() || text[position] != '{') {
    return false;
  }
  ++position;
  skipWhitespace(text, position);
  if (position < text.size() && text[position] == '}') {
    ++position;
    skipWhitespace(text, position);
    return position == text.size();
  }
  while (position < text.size()) {
    std::string key;
    if (!parseJsonString(text, position, key)) {
      return false;
    }
    skipWhitespace(text, position);
    if (position >= text.size() || text[position] != ':') {
      return false;
    }
    ++position;
    skipWhitespace(text, position);
    const std::size_t valueBegin = position;
    if (!skipJsonValue(text, position)) {
      return false;
    }
    const std::size_t valueEnd = position;
    callback(key, JsonRange{valueBegin, valueEnd});
    skipWhitespace(text, position);
    if (position < text.size() && text[position] == ',') {
      ++position;
      skipWhitespace(text, position);
      continue;
    }
    if (position < text.size() && text[position] == '}') {
      ++position;
      skipWhitespace(text, position);
      return position == text.size();
    }
    return false;
  }
  return false;
}

bool findDuplicateJsonKeyInValue(std::string_view text, std::size_t &position,
                                 std::string_view path,
                                 DuplicateJsonKey &duplicate);

bool findDuplicateJsonKeyInArray(std::string_view text, std::size_t &position,
                                 std::string_view path,
                                 DuplicateJsonKey &duplicate) {
  if (position >= text.size() || text[position] != '[') {
    return false;
  }
  ++position;
  skipWhitespace(text, position);
  if (position < text.size() && text[position] == ']') {
    ++position;
    return false;
  }

  std::size_t index = 0;
  while (position < text.size()) {
    const std::string elementPath =
        std::string(path) + "[" + std::to_string(index) + "]";
    if (findDuplicateJsonKeyInValue(text, position, elementPath, duplicate)) {
      return true;
    }
    ++index;
    skipWhitespace(text, position);
    if (position < text.size() && text[position] == ',') {
      ++position;
      skipWhitespace(text, position);
      continue;
    }
    if (position < text.size() && text[position] == ']') {
      ++position;
    }
    return false;
  }
  return false;
}

bool findDuplicateJsonKeyInObject(std::string_view text, std::size_t &position,
                                  std::string_view path,
                                  DuplicateJsonKey &duplicate) {
  if (position >= text.size() || text[position] != '{') {
    return false;
  }
  ++position;
  skipWhitespace(text, position);
  if (position < text.size() && text[position] == '}') {
    ++position;
    return false;
  }

  std::vector<std::string> seenKeys;
  while (position < text.size()) {
    const std::size_t keyBegin = position;
    std::string key;
    if (!parseJsonString(text, position, key)) {
      return false;
    }
    const std::size_t keyEnd = position;
    const std::string memberPath = jsonPathForMember(path, key);
    if (std::find(seenKeys.begin(), seenKeys.end(), key) != seenKeys.end()) {
      duplicate = DuplicateJsonKey{memberPath, JsonRange{keyBegin, keyEnd}};
      return true;
    }
    seenKeys.push_back(std::move(key));

    skipWhitespace(text, position);
    if (position >= text.size() || text[position] != ':') {
      return false;
    }
    ++position;
    if (findDuplicateJsonKeyInValue(text, position, memberPath, duplicate)) {
      return true;
    }
    skipWhitespace(text, position);
    if (position < text.size() && text[position] == ',') {
      ++position;
      skipWhitespace(text, position);
      continue;
    }
    if (position < text.size() && text[position] == '}') {
      ++position;
    }
    return false;
  }
  return false;
}

bool findDuplicateJsonKeyInValue(std::string_view text, std::size_t &position,
                                 std::string_view path,
                                 DuplicateJsonKey &duplicate) {
  skipWhitespace(text, position);
  if (position >= text.size()) {
    return false;
  }
  if (text[position] == '{') {
    return findDuplicateJsonKeyInObject(text, position, path, duplicate);
  }
  if (text[position] == '[') {
    return findDuplicateJsonKeyInArray(text, position, path, duplicate);
  }
  skipJsonValue(text, position);
  return false;
}

} // namespace

void skipWhitespace(std::string_view text, std::size_t &position) {
  while (position < text.size()) {
    const char ch = text[position];
    if (ch != ' ' && ch != '\n' && ch != '\r' && ch != '\t') {
      break;
    }
    ++position;
  }
}

bool parseJsonString(std::string_view text, std::size_t &position,
                     std::string &out) {
  if (position >= text.size() || text[position] != '"') {
    return false;
  }
  ++position;
  while (position < text.size()) {
    const char ch = text[position++];
    if (ch == '"') {
      return true;
    }
    if (ch == '\\') {
      if (position >= text.size()) {
        return false;
      }
      const char escaped = text[position++];
      switch (escaped) {
      case '"':
      case '\\':
      case '/':
        out.push_back(escaped);
        break;
      case 'b':
        out.push_back('\b');
        break;
      case 'f':
        out.push_back('\f');
        break;
      case 'n':
        out.push_back('\n');
        break;
      case 'r':
        out.push_back('\r');
        break;
      case 't':
        out.push_back('\t');
        break;
      case 'u':
        if (!parseUnicodeEscape(text, position, out)) {
          return false;
        }
        break;
      default:
        return false;
      }
      continue;
    }
    if (static_cast<unsigned char>(ch) < 0x20) {
      return false;
    }
    out.push_back(ch);
  }
  return false;
}

bool skipJsonArray(std::string_view text, std::size_t &position) {
  if (position >= text.size() || text[position] != '[') {
    return false;
  }
  ++position;
  skipWhitespace(text, position);
  if (position < text.size() && text[position] == ']') {
    ++position;
    return true;
  }
  while (position < text.size()) {
    if (!skipJsonValue(text, position)) {
      return false;
    }
    skipWhitespace(text, position);
    if (position < text.size() && text[position] == ',') {
      ++position;
      skipWhitespace(text, position);
      continue;
    }
    if (position < text.size() && text[position] == ']') {
      ++position;
      return true;
    }
    return false;
  }
  return false;
}

bool skipJsonObject(std::string_view text, std::size_t &position) {
  if (position >= text.size() || text[position] != '{') {
    return false;
  }
  ++position;
  skipWhitespace(text, position);
  if (position < text.size() && text[position] == '}') {
    ++position;
    return true;
  }
  while (position < text.size()) {
    if (!skipJsonString(text, position)) {
      return false;
    }
    skipWhitespace(text, position);
    if (position >= text.size() || text[position] != ':') {
      return false;
    }
    ++position;
    if (!skipJsonValue(text, position)) {
      return false;
    }
    skipWhitespace(text, position);
    if (position < text.size() && text[position] == ',') {
      ++position;
      skipWhitespace(text, position);
      continue;
    }
    if (position < text.size() && text[position] == '}') {
      ++position;
      return true;
    }
    return false;
  }
  return false;
}

bool skipJsonNumber(std::string_view text, std::size_t &position) {
  const std::size_t start = position;
  if (position < text.size() && text[position] == '-') {
    ++position;
  }
  if (position >= text.size()) {
    return false;
  }
  if (text[position] == '0') {
    ++position;
  } else if (text[position] >= '1' && text[position] <= '9') {
    while (position < text.size() && text[position] >= '0' &&
           text[position] <= '9') {
      ++position;
    }
  } else {
    return false;
  }
  if (position < text.size() && text[position] == '.') {
    ++position;
    const std::size_t digitsBegin = position;
    while (position < text.size() && text[position] >= '0' &&
           text[position] <= '9') {
      ++position;
    }
    if (position == digitsBegin) {
      return false;
    }
  }
  if (position < text.size() &&
      (text[position] == 'e' || text[position] == 'E')) {
    ++position;
    if (position < text.size() &&
        (text[position] == '+' || text[position] == '-')) {
      ++position;
    }
    const std::size_t digitsBegin = position;
    while (position < text.size() && text[position] >= '0' &&
           text[position] <= '9') {
      ++position;
    }
    if (position == digitsBegin) {
      return false;
    }
  }
  return position > start;
}

bool skipJsonValue(std::string_view text, std::size_t &position) {
  skipWhitespace(text, position);
  if (position >= text.size()) {
    return false;
  }
  switch (text[position]) {
  case '{':
    return skipJsonObject(text, position);
  case '[':
    return skipJsonArray(text, position);
  case '"':
    return skipJsonString(text, position);
  case 't':
    return consumeLiteral(text, position, "true");
  case 'f':
    return consumeLiteral(text, position, "false");
  case 'n':
    return consumeLiteral(text, position, "null");
  default:
    return skipJsonNumber(text, position);
  }
}

bool isJsonObjectDocument(std::string_view text) {
  std::size_t position = 0;
  skipWhitespace(text, position);
  if (position >= text.size() || text[position] != '{') {
    return false;
  }
  if (!skipJsonValue(text, position)) {
    return false;
  }
  skipWhitespace(text, position);
  return position == text.size();
}

std::string jsonPathForMember(std::string_view parent, std::string_view key) {
  const auto isFirst = [](char ch) {
    return std::isalpha(static_cast<unsigned char>(ch)) || ch == '_';
  };
  const auto isRest = [](char ch) {
    return std::isalnum(static_cast<unsigned char>(ch)) || ch == '_';
  };

  const bool simple = !key.empty() && isFirst(key.front()) &&
                      std::all_of(key.begin() + 1, key.end(), isRest);
  std::string path(parent);
  if (simple) {
    path += ".";
    path += key;
    return path;
  }

  path += "[\"";
  for (const char ch : key) {
    if (ch == '"' || ch == '\\') {
      path += '\\';
    }
    path += ch;
  }
  path += "\"]";
  return path;
}

std::optional<DuplicateJsonKey> findDuplicateJsonKey(std::string_view text) {
  std::size_t position = 0;
  DuplicateJsonKey duplicate;
  if (findDuplicateJsonKeyInValue(text, position, "$", duplicate)) {
    return duplicate;
  }
  return std::nullopt;
}

std::optional<JsonRange> findObjectMember(std::string_view text,
                                          std::string_view wantedKey) {
  std::size_t position = 0;
  skipWhitespace(text, position);
  if (position >= text.size() || text[position] != '{') {
    return std::nullopt;
  }
  ++position;
  skipWhitespace(text, position);
  while (position < text.size() && text[position] != '}') {
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
    const std::size_t valueEnd = position;
    if (key == wantedKey) {
      return JsonRange{valueBegin, valueEnd};
    }
    skipWhitespace(text, position);
    if (position < text.size() && text[position] == ',') {
      ++position;
      skipWhitespace(text, position);
      continue;
    }
    if (position < text.size() && text[position] == '}') {
      break;
    }
    return std::nullopt;
  }
  return std::nullopt;
}

std::optional<std::string_view> findObjectMemberValue(std::string_view text,
                                                      std::string_view key) {
  std::optional<JsonRange> range;
  const bool valid = forEachObjectMember(
      text, [&](const std::string &member, JsonRange valueRange) {
        if (member == key && !range) {
          range = valueRange;
        }
      });
  if (!valid || !range) {
    return std::nullopt;
  }
  return text.substr(range->begin, range->end - range->begin);
}

std::optional<StringMember> findStringMemberRecord(std::string_view text,
                                                   std::string_view key) {
  const std::optional<JsonRange> range = findObjectMember(text, key);
  if (!range) {
    return std::nullopt;
  }
  std::size_t position = range->begin;
  std::string value;
  if (!parseJsonString(text, position, value)) {
    return std::nullopt;
  }
  if (position != range->end) {
    return std::nullopt;
  }
  return StringMember{std::move(value), *range};
}

StringObjectMembers collectStringObjectMembers(std::string_view text) {
  StringObjectMembers result;
  std::size_t position = 0;
  skipWhitespace(text, position);
  if (position >= text.size() || text[position] != '{') {
    return result;
  }
  ++position;
  skipWhitespace(text, position);
  while (position < text.size() && text[position] != '}') {
    std::string key;
    if (!parseJsonString(text, position, key)) {
      return {};
    }
    skipWhitespace(text, position);
    if (position >= text.size() || text[position] != ':') {
      return {};
    }
    ++position;
    skipWhitespace(text, position);
    if (position < text.size() && text[position] == '"') {
      const std::size_t valueBegin = position;
      std::string value;
      if (!parseJsonString(text, position, value)) {
        return {};
      }
      result.members.push_back(
          {std::move(key), std::move(value), JsonRange{valueBegin, position}});
    } else {
      return {};
    }
    skipWhitespace(text, position);
    if (position < text.size() && text[position] == ',') {
      ++position;
      skipWhitespace(text, position);
      continue;
    }
    if (position < text.size() && text[position] == '}') {
      break;
    }
    return {};
  }
  result.valid = true;
  return result;
}

std::optional<std::uintmax_t> parseUnsignedInteger(std::string_view text) {
  std::size_t position = 0;
  skipWhitespace(text, position);
  if (position >= text.size() ||
      !std::isdigit(static_cast<unsigned char>(text[position]))) {
    return std::nullopt;
  }
  std::uintmax_t value = 0;
  while (position < text.size() &&
         std::isdigit(static_cast<unsigned char>(text[position]))) {
    const std::uintmax_t digit =
        static_cast<std::uintmax_t>(text[position] - '0');
    if (value > (std::numeric_limits<std::uintmax_t>::max() - digit) / 10) {
      return std::nullopt;
    }
    value = value * 10 + digit;
    ++position;
  }
  skipWhitespace(text, position);
  if (position != text.size()) {
    return std::nullopt;
  }
  return value;
}

std::optional<bool> parseBool(std::string_view text) {
  std::size_t position = 0;
  skipWhitespace(text, position);
  if (text.substr(position, 4) == "true") {
    position += 4;
    skipWhitespace(text, position);
    return position == text.size() ? std::optional<bool>(true) : std::nullopt;
  }
  if (text.substr(position, 5) == "false") {
    position += 5;
    skipWhitespace(text, position);
    return position == text.size() ? std::optional<bool>(false) : std::nullopt;
  }
  return std::nullopt;
}

std::optional<std::uintmax_t> objectUnsignedMember(std::string_view object,
                                                  std::string_view key) {
  const std::optional<std::string_view> value =
      findObjectMemberValue(object, key);
  if (!value) {
    return std::nullopt;
  }
  return parseUnsignedInteger(*value);
}

std::optional<bool> objectBoolMember(std::string_view object,
                                     std::string_view key) {
  const std::optional<std::string_view> value =
      findObjectMemberValue(object, key);
  if (!value) {
    return std::nullopt;
  }
  return parseBool(*value);
}

std::optional<std::string> objectStringMember(std::string_view object,
                                              std::string_view key) {
  const std::optional<std::string_view> value =
      findObjectMemberValue(object, key);
  if (!value) {
    return std::nullopt;
  }
  std::size_t position = 0;
  std::string parsed;
  if (!parseJsonString(*value, position, parsed)) {
    return std::nullopt;
  }
  skipWhitespace(*value, position);
  if (position != value->size()) {
    return std::nullopt;
  }
  return parsed;
}

bool objectHasMemberEndingWith(std::string_view object,
                               std::string_view suffix) {
  bool found = false;
  forEachObjectMember(object, [&](const std::string &key, JsonRange) {
    if (key.size() >= suffix.size() &&
        key.compare(key.size() - suffix.size(), suffix.size(), suffix) == 0) {
      found = true;
    }
  });
  return found;
}

std::optional<std::size_t> arrayLength(std::string_view arrayText) {
  std::size_t position = 0;
  skipWhitespace(arrayText, position);
  if (position >= arrayText.size() || arrayText[position] != '[') {
    return std::nullopt;
  }
  ++position;
  skipWhitespace(arrayText, position);
  if (position < arrayText.size() && arrayText[position] == ']') {
    ++position;
    skipWhitespace(arrayText, position);
    return position == arrayText.size() ? std::optional<std::size_t>(0)
                                        : std::nullopt;
  }
  std::size_t count = 0;
  while (position < arrayText.size()) {
    if (!skipJsonValue(arrayText, position)) {
      return std::nullopt;
    }
    ++count;
    skipWhitespace(arrayText, position);
    if (position < arrayText.size() && arrayText[position] == ',') {
      ++position;
      skipWhitespace(arrayText, position);
      continue;
    }
    if (position < arrayText.size() && arrayText[position] == ']') {
      ++position;
      skipWhitespace(arrayText, position);
      return position == arrayText.size() ? std::optional<std::size_t>(count)
                                          : std::nullopt;
    }
    return std::nullopt;
  }
  return std::nullopt;
}

std::string canonicalJson(std::string_view text) {
  std::string result;
  bool inString = false;
  bool escaped = false;
  for (char ch : text) {
    if (inString) {
      result.push_back(ch);
      if (escaped) {
        escaped = false;
      } else if (ch == '\\') {
        escaped = true;
      } else if (ch == '"') {
        inString = false;
      }
      continue;
    }
    if (ch == '"') {
      inString = true;
      result.push_back(ch);
      continue;
    }
    if (ch != ' ' && ch != '\n' && ch != '\r' && ch != '\t') {
      result.push_back(ch);
    }
  }
  return result;
}

bool canonicalMemberEquals(std::string_view object, std::string_view key,
                           std::string_view expected) {
  const std::optional<std::string_view> value = findObjectMemberValue(object, key);
  return value && canonicalJson(*value) == expected;
}

} // namespace crossgl
