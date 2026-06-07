#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace crossgl {

struct JsonRange {
  std::size_t begin = 0;
  std::size_t end = 0;
};

struct StringObjectMember {
  std::string name;
  std::string value;
  JsonRange valueRange;
};

struct StringObjectMembers {
  bool valid = false;
  std::vector<StringObjectMember> members;
};

struct StringMember {
  std::string value;
  JsonRange valueRange;
};

struct DuplicateJsonKey {
  std::string path;
  JsonRange keyRange;
};

void skipWhitespace(std::string_view text, std::size_t &position);
bool parseJsonString(std::string_view text, std::size_t &position,
                     std::string &out);
bool skipJsonValue(std::string_view text, std::size_t &position);
bool skipJsonArray(std::string_view text, std::size_t &position);
bool skipJsonObject(std::string_view text, std::size_t &position);

bool isJsonObjectDocument(std::string_view text);
std::string jsonPathForMember(std::string_view parent, std::string_view key);
std::optional<DuplicateJsonKey> findDuplicateJsonKey(std::string_view text);

std::optional<JsonRange> findObjectMember(std::string_view text,
                                          std::string_view wantedKey);
std::optional<std::string_view> findObjectMemberValue(std::string_view text,
                                                      std::string_view key);
std::optional<StringMember> findStringMemberRecord(std::string_view text,
                                                   std::string_view key);
StringObjectMembers collectStringObjectMembers(std::string_view text);

std::optional<std::uintmax_t> parseUnsignedInteger(std::string_view text);
std::optional<bool> parseBool(std::string_view text);
std::optional<std::uintmax_t> objectUnsignedMember(std::string_view object,
                                                  std::string_view key);
std::optional<bool> objectBoolMember(std::string_view object,
                                     std::string_view key);
std::optional<std::string> objectStringMember(std::string_view object,
                                              std::string_view key);
bool objectHasMemberEndingWith(std::string_view object,
                               std::string_view suffix);

std::optional<std::size_t> arrayLength(std::string_view arrayText);
std::string canonicalJson(std::string_view text);
bool canonicalMemberEquals(std::string_view object, std::string_view key,
                           std::string_view expected);

} // namespace crossgl
