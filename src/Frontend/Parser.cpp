#include "crossgl/Frontend/Parser.h"

#include <cctype>
#include <sstream>
#include <utility>

namespace crossgl {
namespace {

constexpr std::string_view kSpecUnsupportedForNativeV0 =
    "spec.unsupported-for-native-v0";

bool isNameToken(TokenKind kind) {
  return kind == TokenKind::Identifier || kind == TokenKind::KeywordInput ||
         kind == TokenKind::KeywordOutput;
}

bool isVoidIdentifier(const Token &token) {
  return token.kind == TokenKind::Identifier && token.text == "void";
}

std::string joinTokenText(const std::vector<Token> &tokens) {
  std::ostringstream out;
  for (const Token &token : tokens) {
    out << token.text;
  }
  return out.str();
}

SourceLocation sourceSpan(SourceLocation begin, const SourceLocation &end) {
  begin.endLine = end.endLine;
  begin.endColumn = end.endColumn;
  begin.endOffset = end.endOffset;
  begin.length = begin.endOffset >= begin.offset ? begin.endOffset - begin.offset
                                                 : begin.length;
  return begin;
}

std::optional<std::size_t> parseSizeLiteral(std::string_view text) {
  if (text.empty()) {
    return std::nullopt;
  }
  std::size_t value = 0;
  for (char ch : text) {
    if (!std::isdigit(static_cast<unsigned char>(ch))) {
      return std::nullopt;
    }
    value = value * 10 + static_cast<std::size_t>(ch - '0');
  }
  return value;
}

bool isOperatorToken(const Token &token, std::string_view text) {
  return token.kind == TokenKind::Operator && token.text == text;
}

bool isVarToken(const Token &token) {
  return token.kind == TokenKind::KeywordVar ||
         (token.kind == TokenKind::Identifier && token.text == "var");
}

bool isVarResourceStart(const Token &token, const Token &next) {
  return isVarToken(token) && isOperatorToken(next, "<");
}

bool isColonStyleVarDeclarationStart(const Token &token, const Token &next,
                                     const Token &third) {
  return isVarToken(token) && isNameToken(next.kind) &&
         third.kind == TokenKind::Colon;
}

bool isStorageImageAccessQualifier(TokenKind kind) {
  return kind == TokenKind::KeywordReadonly ||
         kind == TokenKind::KeywordWriteonly ||
         kind == TokenKind::KeywordReadwrite;
}

bool isWorkgroupAddressSpace(std::string_view text) {
  return text == "workgroup" || text == "shared" || text == "threadgroup" ||
         text == "groupshared";
}

std::string unsupportedVarAddressSpaceName(
    const std::vector<std::string> &addressSpaceNames) {
  if (addressSpaceNames.empty()) {
    return "<empty>";
  }
  return addressSpaceNames.front();
}

std::string normalizeVarResourceTypeName(std::string name) {
  if (name == "f32") {
    return "float";
  }
  if (name == "i32") {
    return "int";
  }
  if (name == "u32") {
    return "uint";
  }
  return name;
}

void appendArrayDimension(TypeRef &type, std::string dimension) {
  if (type.arraySize.has_value()) {
    *type.arraySize += "][" + dimension;
  } else {
    type.arraySize = std::move(dimension);
  }
}

bool isUnsupportedExtendedStageName(std::string_view text) {
  return text == "geometry" || text == "tessellation" ||
         text == "tessellation_control" ||
         text == "tessellation_evaluation" || text == "hull" ||
         text == "domain" || text == "mesh" || text == "task" ||
         text == "ray_generation" || text == "ray_intersection" ||
         text == "ray_closest_hit" || text == "ray_miss" ||
         text == "ray_any_hit" || text == "ray_callable" ||
         text == "raygen" || text == "raygeneration" ||
         text == "closesthit" || text == "anyhit" || text == "miss" ||
         text == "intersection" || text == "callable";
}

bool isUnsupportedImportName(std::string_view text) {
  return text == "import" || text == "from" || text == "use";
}

bool isUnsupportedNominalName(std::string_view text) {
  return text == "enum" || text == "generic" || text == "trait" ||
         text == "impl";
}

bool isIdentifierText(const Token &token, std::string_view text) {
  return token.kind == TokenKind::Identifier && token.text == text;
}

bool isStatementStart(const std::vector<Token> &tokens, std::size_t index) {
  if (index == 0) {
    return true;
  }

  const Token &previous = tokens[index - 1];
  if (previous.kind == TokenKind::LBrace ||
      previous.kind == TokenKind::RBrace ||
      previous.kind == TokenKind::Semicolon ||
      previous.kind == TokenKind::Colon) {
    return true;
  }

  return isIdentifierText(previous, "else");
}

std::optional<std::size_t>
findMatchingBodyToken(const std::vector<Token> &tokens, std::size_t openIndex,
                      TokenKind openKind, TokenKind closeKind) {
  if (openIndex >= tokens.size() || tokens[openIndex].kind != openKind) {
    return std::nullopt;
  }

  int depth = 0;
  for (std::size_t index = openIndex; index < tokens.size(); ++index) {
    if (tokens[index].kind == openKind) {
      ++depth;
    } else if (tokens[index].kind == closeKind) {
      --depth;
      if (depth == 0) {
        return index;
      }
    }
  }
  return std::nullopt;
}

std::size_t countTopLevelBodyTokens(const std::vector<Token> &tokens,
                                    std::size_t begin, std::size_t end,
                                    TokenKind kind) {
  std::size_t count = 0;
  int parenDepth = 0;
  int bracketDepth = 0;
  int braceDepth = 0;
  for (std::size_t index = begin; index < end && index < tokens.size(); ++index) {
    const Token &token = tokens[index];
    if (token.kind == TokenKind::LParen) {
      ++parenDepth;
    } else if (token.kind == TokenKind::RParen) {
      --parenDepth;
    } else if (token.kind == TokenKind::LBracket) {
      ++bracketDepth;
    } else if (token.kind == TokenKind::RBracket) {
      --bracketDepth;
    } else if (token.kind == TokenKind::LBrace) {
      ++braceDepth;
    } else if (token.kind == TokenKind::RBrace) {
      --braceDepth;
    } else if (token.kind == kind && parenDepth == 0 && bracketDepth == 0 &&
               braceDepth == 0) {
      ++count;
    }
  }
  return count;
}

std::optional<std::string> unsupportedShaderItemForm(const Token &token) {
  if (token.kind != TokenKind::Identifier) {
    return std::nullopt;
  }

  const std::string &text = token.text;
  if (isUnsupportedExtendedStageName(text)) {
    return "stage '" + text + "'";
  }
  if (text == "fn") {
    return "fn-style function declarations";
  }
  if (isUnsupportedImportName(text)) {
    return "source import declarations";
  }
  if (isUnsupportedNominalName(text)) {
    return text + " declarations";
  }
  return std::nullopt;
}

std::optional<std::string> unsupportedStructItemForm(const Token &token) {
  if (token.kind != TokenKind::Identifier ||
      !isUnsupportedNominalName(token.text)) {
    return std::nullopt;
  }
  return token.text + " declarations";
}

std::string unsupportedPatternControlForm(std::string_view text) {
  if (text == "match") {
    return "match/pattern control statements";
  }
  if (text == "switch" || text == "case" || text == "default") {
    return "switch/case/default statements";
  }
  if (text == "do") {
    return "do while statements";
  }
  return std::string(text) + " statements";
}

bool isForInStatement(const std::vector<Token> &tokens, std::size_t index) {
  if (!isIdentifierText(tokens[index], "for")) {
    return false;
  }

  if (index + 1 < tokens.size() && tokens[index + 1].kind == TokenKind::LParen) {
    return false;
  }

  std::size_t cursor = index + 1;
  while (cursor < tokens.size() && tokens[cursor].kind != TokenKind::LBrace &&
         tokens[cursor].kind != TokenKind::Semicolon &&
         tokens[cursor].kind != TokenKind::RBrace) {
    if (tokens[cursor].kind == TokenKind::KeywordIn) {
      return true;
    }
    ++cursor;
  }
  return false;
}

bool isLetMutDeclaration(const std::vector<Token> &tokens, std::size_t index) {
  return isIdentifierText(tokens[index], "let") && index + 1 < tokens.size() &&
         isIdentifierText(tokens[index + 1], "mut");
}

bool hasMalformedControlHeader(const std::vector<Token> &tokens,
                               std::size_t index) {
  if (!isIdentifierText(tokens[index], "if") &&
      !isIdentifierText(tokens[index], "while") &&
      !isIdentifierText(tokens[index], "for")) {
    return false;
  }

  if (isForInStatement(tokens, index)) {
    return false;
  }

  const std::size_t openIndex = index + 1;
  if (openIndex >= tokens.size() || tokens[openIndex].kind != TokenKind::LParen) {
    return true;
  }

  std::optional<std::size_t> closeIndex = findMatchingBodyToken(
      tokens, openIndex, TokenKind::LParen, TokenKind::RParen);
  if (!closeIndex.has_value()) {
    return true;
  }

  if (isIdentifierText(tokens[index], "for") &&
      countTopLevelBodyTokens(tokens, openIndex + 1, *closeIndex,
                              TokenKind::Semicolon) != 2) {
    return true;
  }

  return false;
}

} // namespace

Parser::Parser(std::span<const Token> tokens, DiagnosticEngine &diagnostics)
    : tokens_(tokens), diagnostics_(diagnostics) {}

std::optional<ShaderModule> Parser::parseModule() {
  while (diagnoseAndSkipUnsupportedPreambleItem()) {
  }

  if (!expect(TokenKind::KeywordShader, "expected 'shader' module declaration")) {
    return std::nullopt;
  }

  if (!check(TokenKind::Identifier)) {
    diagnostics_.error("parse.expected-shader-name", "expected shader name",
                       current().location);
    return std::nullopt;
  }

  ShaderModule module;
  module.name = current().text;
  module.location = current().location;
  advance();

  if (!expect(TokenKind::LBrace, "expected '{' after shader name")) {
    return std::nullopt;
  }

  while (!atEnd() && !check(TokenKind::RBrace)) {
    if (check(TokenKind::KeywordStruct)) {
      if (auto decl = parseStruct()) {
        module.structs.push_back(std::move(*decl));
      }
      continue;
    }
    if (check(TokenKind::Identifier) && current().text == "cbuffer") {
      if (auto decl = parseCBuffer()) {
        module.cbuffers.push_back(std::move(*decl));
      }
      continue;
    }
    if (diagnoseAndSkipUnsupportedShaderItem()) {
      continue;
    }
    if (check(TokenKind::KeywordConst)) {
      if (auto constant = parseConstant()) {
        module.constants.push_back(std::move(*constant));
      }
      continue;
    }
    if (isStageKeyword(current().kind)) {
      if (auto stage = parseStage()) {
        module.stages.push_back(std::move(*stage));
      }
      continue;
    }
    if (looksLikeFunction()) {
      if (auto function = parseFunction()) {
        module.functions.push_back(std::move(*function));
      }
      continue;
    }

    diagnostics_.warning("parse.skipped-token",
                         "skipping unsupported shader item '" + current().text + "'",
                         current().location);
    skipDeclarationOrBlock();
  }

  expect(TokenKind::RBrace, "expected '}' after shader body");
  return module;
}

bool Parser::atEnd() const { return check(TokenKind::End); }

const Token &Parser::current() const { return tokens_[index_]; }

const Token &Parser::peek(std::size_t lookahead) const {
  const std::size_t index = index_ + lookahead;
  return index < tokens_.size() ? tokens_[index] : tokens_.back();
}

bool Parser::check(TokenKind kind) const { return current().kind == kind; }

bool Parser::match(TokenKind kind) {
  if (!check(kind)) {
    return false;
  }
  advance();
  return true;
}

bool Parser::expect(TokenKind kind, std::string_view message) {
  if (match(kind)) {
    return true;
  }
  diagnostics_.error("parse.expected-token", std::string(message) + ", got " +
                                                 tokenKindName(current().kind),
                     current().location);
  return false;
}

const Token &Parser::previous() const { return tokens_[index_ - 1]; }

void Parser::advance() {
  if (!atEnd()) {
    ++index_;
  }
}

void Parser::synchronize() {
  const std::size_t start = index_;
  while (!atEnd()) {
    if (index_ != start && index_ > 0 && previous().kind == TokenKind::Semicolon) {
      return;
    }
    if (check(TokenKind::KeywordStruct) || isStageKeyword(current().kind)) {
      return;
    }
    advance();
  }
  if (index_ == start && !atEnd()) {
    advance();
  }
}

std::optional<TypeRef> Parser::parseType() {
  std::string qualifier;
  SourceLocation qualifierLocation;
  if (check(TokenKind::KeywordUniform) || check(TokenKind::KeywordBuffer) ||
      check(TokenKind::KeywordShared)) {
    qualifier = current().text + " ";
    qualifierLocation = current().location;
    advance();
  }

  if (!check(TokenKind::Identifier)) {
    diagnostics_.error("parse.expected-type", "expected type name",
                       current().location);
    return std::nullopt;
  }

  TypeRef type;
  type.name = qualifier + current().text;
  type.location = qualifier.empty() ? current().location : qualifierLocation;
  SourceLocation typeEndLocation = current().location;
  advance();

  if (check(TokenKind::Operator) && current().text == "<") {
    int depth = 0;
    do {
      if (check(TokenKind::Operator) && current().text == "<") {
        ++depth;
      } else if (check(TokenKind::Operator) && current().text == ">") {
        --depth;
      }
      type.name += current().text;
      typeEndLocation = current().location;
      advance();
    } while (!atEnd() && depth > 0);
  }

  if (match(TokenKind::LBracket)) {
    typeEndLocation = previous().location;
    if (!check(TokenKind::RBracket)) {
      std::ostringstream size;
      while (!atEnd() && !check(TokenKind::RBracket)) {
        size << current().text;
        typeEndLocation = current().location;
        advance();
      }
      type.arraySize = size.str();
    } else {
      type.arraySize = "";
    }
    if (expect(TokenKind::RBracket, "expected ']' after array type")) {
      typeEndLocation = previous().location;
    }
  }

  while (check(TokenKind::Operator) && current().text == "*") {
    type.name += "*";
    typeEndLocation = current().location;
    advance();
  }

  type.location = sourceSpan(type.location, typeEndLocation);
  return type;
}

std::optional<StructDecl> Parser::parseStruct() {
  const SourceLocation loc = current().location;
  expect(TokenKind::KeywordStruct, "expected 'struct'");
  if (!check(TokenKind::Identifier)) {
    diagnostics_.error("parse.expected-struct-name", "expected struct name",
                       current().location);
    synchronize();
    return std::nullopt;
  }

  StructDecl decl;
  decl.name = current().text;
  decl.location = loc;
  decl.nameSpan = current().location;
  advance();

  if (check(TokenKind::Operator) && current().text == "<") {
    diagnoseUnsupportedNativeV0("generic struct declarations",
                                current().location);
    skipGenericClause();
  }

  if (!expect(TokenKind::LBrace, "expected '{' after struct name")) {
    synchronize();
    return std::nullopt;
  }

  while (!atEnd() && !check(TokenKind::RBrace)) {
    if (diagnoseAndSkipUnsupportedStructItem()) {
      continue;
    }

    if (check(TokenKind::KeywordStruct) ||
        (check(TokenKind::Identifier) &&
         (current().text == "enum" || current().text == "trait"))) {
      skipDeclarationOrBlock();
      continue;
    }

    if (isNameToken(current().kind) && peek().kind == TokenKind::Colon) {
      StructField field;
      field.name = current().text;
      field.location = current().location;
      advance();
      expect(TokenKind::Colon, "expected ':' after struct field name");
      auto fieldType = parseType();
      if (!fieldType) {
        synchronize();
        continue;
      }
      field.type = std::move(*fieldType);
      if (!match(TokenKind::Semicolon) && !match(TokenKind::Comma) &&
          !check(TokenKind::RBrace)) {
        diagnostics_.error("parse.expected-field-terminator",
                           "expected ';' or ',' after struct field",
                           current().location);
        synchronize();
      }
      decl.fields.push_back(std::move(field));
      continue;
    }

    auto type = parseType();
    if (!type || !isNameToken(current().kind)) {
      synchronize();
      continue;
    }

    StructField field;
    field.type = std::move(*type);
    field.name = current().text;
    field.location = current().location;
    advance();

    parseArrayDeclaratorSuffix(field.type,
                               "expected ']' after field array size");

    if (!match(TokenKind::Semicolon) && !match(TokenKind::Comma) &&
        !check(TokenKind::RBrace)) {
      diagnostics_.error("parse.expected-field-terminator",
                         "expected ';' or ',' after struct field",
                         current().location);
      synchronize();
    }
    decl.fields.push_back(std::move(field));
  }

  expect(TokenKind::RBrace, "expected '}' after struct body");
  match(TokenKind::Semicolon);
  decl.declarationSpan = sourceSpan(loc, previous().location);
  return decl;
}

std::optional<StructDecl> Parser::parseCBuffer() {
  const SourceLocation loc = current().location;
  advance();
  if (!check(TokenKind::Identifier)) {
    diagnostics_.error("parse.expected-cbuffer-name", "expected cbuffer name",
                       current().location);
    synchronize();
    return std::nullopt;
  }

  StructDecl decl;
  decl.name = current().text;
  decl.location = loc;
  decl.nameSpan = current().location;
  advance();

  if (!expect(TokenKind::LBrace, "expected '{' after cbuffer name")) {
    synchronize();
    return std::nullopt;
  }

  while (!atEnd() && !check(TokenKind::RBrace)) {
    auto type = parseType();
    if (!type || !isNameToken(current().kind)) {
      synchronize();
      continue;
    }

    StructField field;
    field.type = std::move(*type);
    field.name = current().text;
    field.location = current().location;
    advance();

    parseArrayDeclaratorSuffix(field.type,
                               "expected ']' after cbuffer field array size");

    if (!expect(TokenKind::Semicolon, "expected ';' after cbuffer field")) {
      synchronize();
    }
    decl.fields.push_back(std::move(field));
  }

  expect(TokenKind::RBrace, "expected '}' after cbuffer body");
  match(TokenKind::Semicolon);
  decl.declarationSpan = sourceSpan(loc, previous().location);
  return decl;
}

void Parser::skipGenericClause() {
  if (!(check(TokenKind::Operator) && current().text == "<")) {
    return;
  }

  int depth = 0;
  do {
    if (check(TokenKind::Operator) && current().text == "<") {
      ++depth;
    } else if (check(TokenKind::Operator) && current().text == ">") {
      --depth;
    }
    advance();
  } while (!atEnd() && depth > 0);
}

std::optional<ConstantDecl> Parser::parseConstant() {
  const SourceLocation loc = current().location;
  expect(TokenKind::KeywordConst, "expected 'const'");
  auto type = parseType();
  if (!type || !isNameToken(current().kind)) {
    synchronize();
    return std::nullopt;
  }

  ConstantDecl constant;
  constant.type = std::move(*type);
  constant.name = current().text;
  constant.location = loc;
  advance();
  expect(TokenKind::Equal, "expected '=' in constant declaration");

  while (!atEnd() && !check(TokenKind::Semicolon)) {
    constant.valueTokens.push_back(current());
    advance();
  }
  expect(TokenKind::Semicolon, "expected ';' after constant declaration");
  return constant;
}

std::optional<FunctionDecl> Parser::parseFunction() {
  auto returnType = parseType();
  if (!returnType || !check(TokenKind::Identifier)) {
    synchronize();
    return std::nullopt;
  }

  FunctionDecl function;
  function.returnType = std::move(*returnType);
  function.name = current().text;
  function.location = current().location;
  advance();

  if (check(TokenKind::Operator) && current().text == "<") {
    diagnoseUnsupportedNativeV0("generic function declarations",
                                current().location);
    skipDeclarationOrBlock();
    return std::nullopt;
  }

  expect(TokenKind::LParen, "expected '(' after function name");
  function.parameters = parseParameters();
  expect(TokenKind::RParen, "expected ')' after parameters");
  if (check(TokenKind::Operator) && current().text == "-" &&
      peek().kind == TokenKind::Operator && peek().text == ">") {
    advance();
    advance();
    if (auto trailingReturn = parseType()) {
      function.returnType = std::move(*trailingReturn);
    }
  }
  if (match(TokenKind::Semicolon)) {
    return function;
  }
  function.bodyTokens = parseBalancedBody();
  diagnoseUnsupportedFunctionBodyForms(function.bodyTokens);
  return function;
}

std::optional<ResourceDecl> Parser::parseResource(
    std::optional<ResourceLayoutDecl> layout) {
  std::optional<std::string> storageImageAccessQualifier;
  SourceLocation storageImageAccessLocation;
  if (isStorageImageAccessQualifier(current().kind)) {
    storageImageAccessQualifier = current().text;
    storageImageAccessLocation = current().location;
    advance();
  }

  if (isVarResourceStart(current(), peek())) {
    const SourceLocation varLocation = current().location;
    advance();

    auto expectOperator = [&](std::string_view op,
                              std::string_view message) -> bool {
      if (isOperatorToken(current(), op)) {
        advance();
        return true;
      }
      diagnostics_.error("parse.expected-token",
                         std::string(message) + ", got " +
                             tokenKindName(current().kind),
                         current().location);
      return false;
    };

    if (!expectOperator("<", "expected '<' after var")) {
      synchronize();
      return std::nullopt;
    }

    std::vector<std::string> addressSpaceNames;
    while (!atEnd() && !isOperatorToken(current(), ">")) {
      if (current().kind == TokenKind::Identifier) {
        addressSpaceNames.push_back(current().text);
      }
      advance();
    }

    if (!expectOperator(">", "expected '>' after var address space")) {
      synchronize();
      return std::nullopt;
    }

    const std::string addressSpace =
        unsupportedVarAddressSpaceName(addressSpaceNames);
    const bool workgroupAddressSpace =
        !addressSpaceNames.empty() &&
        isWorkgroupAddressSpace(addressSpaceNames.front());
    if (!workgroupAddressSpace) {
      diagnostics_.error("parse.unsupported-var-address-space",
                         "stage-scope var<" + addressSpace +
                             "> declarations are unsupported for native v0; "
                             "use var<workgroup> for shared storage "
                             "(compatibility id resource.var-address-space)",
                         varLocation);
      synchronize();
      return std::nullopt;
    }

    if (!isNameToken(current().kind)) {
      diagnostics_.error("parse.expected-resource-name",
                         "expected resource name after var<workgroup>",
                         current().location);
      synchronize();
      return std::nullopt;
    }

    ResourceDecl resource;
    resource.name = current().text;
    resource.location = current().location;
    resource.nameSpan = current().location;
    resource.storageImageAccessQualifier = storageImageAccessQualifier;
    resource.storageImageAccessLocation = storageImageAccessLocation;
    if (layout.has_value()) {
      resource.set = layout->set;
      resource.binding = layout->binding;
      resource.bindingLocation = layout->bindingLocation;
      resource.storageImageFormat = layout->storageImageFormat;
      resource.storageImageFormatLocation = layout->storageImageFormatLocation;
      resource.layoutSpan = layout->layoutSpan;
      resource.setSpan = layout->setSpan;
      resource.bindingSpan = layout->bindingSpan;
    }
    advance();

    if (!expect(TokenKind::Colon,
                "expected ':' after var<workgroup> resource name")) {
      synchronize();
      return std::nullopt;
    }

    TypeRef type;
    if (check(TokenKind::Identifier) && current().text == "array" &&
        isOperatorToken(peek(), "<")) {
      advance();
      if (!expectOperator("<", "expected '<' after array")) {
        synchronize();
        return std::nullopt;
      }

      std::vector<Token> elementTokens;
      int elementGenericDepth = 0;
      while (!atEnd()) {
        if (elementGenericDepth == 0 &&
            (check(TokenKind::Comma) || isOperatorToken(current(), ">"))) {
          break;
        }
        if (isOperatorToken(current(), "<")) {
          ++elementGenericDepth;
        } else if (isOperatorToken(current(), ">") &&
                   elementGenericDepth > 0) {
          --elementGenericDepth;
        }
        elementTokens.push_back(current());
        advance();
      }
      if (!expect(TokenKind::Comma,
                  "expected ',' after var<workgroup> array element type")) {
        synchronize();
        return std::nullopt;
      }

      std::vector<Token> sizeTokens;
      while (!atEnd() && !isOperatorToken(current(), ">")) {
        sizeTokens.push_back(current());
        advance();
      }
      if (!expectOperator(">", "expected '>' after var<workgroup> array type")) {
        synchronize();
        return std::nullopt;
      }
      type.name = "shared " +
                  normalizeVarResourceTypeName(joinTokenText(elementTokens));
      type.arraySize = joinTokenText(sizeTokens);
      type.location = sourceSpan(varLocation, previous().location);
    } else if (auto parsedType = parseType()) {
      type = std::move(*parsedType);
      type.name = "shared " + normalizeVarResourceTypeName(std::move(type.name));
      type.location = sourceSpan(varLocation, type.location);
    } else {
      synchronize();
      return std::nullopt;
    }
    resource.type = std::move(type);

    const SourceLocation declarationStart =
        layout.has_value() ? layout->layoutSpan : varLocation;
    if (expect(TokenKind::Semicolon,
               "expected ';' after var<workgroup> resource declaration")) {
      resource.declarationSpan = sourceSpan(declarationStart, previous().location);
    } else {
      resource.declarationSpan = sourceSpan(declarationStart, previous().location);
      synchronize();
    }
    return resource;
  }

  auto type = parseType();
  if (!type || !isNameToken(current().kind)) {
    synchronize();
    return std::nullopt;
  }

  ResourceDecl resource;
  resource.type = std::move(*type);
  resource.name = current().text;
  resource.location = current().location;
  resource.nameSpan = current().location;
  resource.storageImageAccessQualifier = storageImageAccessQualifier;
  resource.storageImageAccessLocation = storageImageAccessLocation;
  if (layout.has_value()) {
    resource.set = layout->set;
    resource.binding = layout->binding;
    resource.bindingLocation = layout->bindingLocation;
    resource.storageImageFormat = layout->storageImageFormat;
    resource.storageImageFormatLocation = layout->storageImageFormatLocation;
    resource.layoutSpan = layout->layoutSpan;
    resource.setSpan = layout->setSpan;
    resource.bindingSpan = layout->bindingSpan;
  }
  advance();

  parseArrayDeclaratorSuffix(resource.type,
                             "expected ']' after resource array size");

  const SourceLocation declarationStart =
      layout.has_value() ? layout->layoutSpan : resource.type.location;
  if (expect(TokenKind::Semicolon, "expected ';' after resource declaration")) {
    resource.declarationSpan = sourceSpan(declarationStart, previous().location);
  } else {
    resource.declarationSpan = sourceSpan(declarationStart, previous().location);
    synchronize();
  }
  return resource;
}

std::optional<ResourceLayoutDecl> Parser::parseResourceLayout() {
  ResourceLayoutDecl layout;
  layout.location = current().location;
  layout.bindingLocation = current().location;
  std::optional<std::string> bindingKey;
  expect(TokenKind::KeywordLayout, "expected 'layout'");
  if (!expect(TokenKind::LParen, "expected '(' after layout")) {
    synchronize();
    return std::nullopt;
  }

  while (!atEnd() && !check(TokenKind::RParen)) {
    if (!check(TokenKind::Identifier)) {
      diagnostics_.warning("parse.unsupported-resource-layout-item",
                           "skipping unsupported resource layout item",
                           current().location);
      advance();
      match(TokenKind::Comma);
      continue;
    }

    const std::string key = current().text;
    const SourceLocation keyLocation = current().location;
    advance();
    expect(TokenKind::Equal, "expected '=' in resource layout item");
    std::vector<Token> valueTokens;
    int parenDepth = 0;
    int bracketDepth = 0;
    while (!atEnd() && !(parenDepth == 0 && bracketDepth == 0 &&
                         (check(TokenKind::Comma) || check(TokenKind::RParen)))) {
      if (check(TokenKind::LParen)) {
        ++parenDepth;
      } else if (check(TokenKind::RParen)) {
        --parenDepth;
      } else if (check(TokenKind::LBracket)) {
        ++bracketDepth;
      } else if (check(TokenKind::RBracket)) {
        --bracketDepth;
      }
      valueTokens.push_back(current());
      advance();
    }

    const std::string value = joinTokenText(valueTokens);
    const std::optional<std::size_t> parsedValue = parseSizeLiteral(value);
    if (key == "set" || key == "group") {
      if (parsedValue.has_value()) {
        layout.set = *parsedValue;
        if (!valueTokens.empty()) {
          layout.setSpan = sourceSpan(keyLocation, valueTokens.back().location);
        }
      } else {
        diagnostics_.error("parse.invalid-resource-set",
                           "resource layout set must be a non-negative integer",
                           keyLocation);
      }
    } else if (key == "binding" || key == "register") {
      if (parsedValue.has_value()) {
        if (layout.binding.has_value() && *layout.binding != *parsedValue &&
            bindingKey.has_value() && *bindingKey != key) {
          diagnostics_.error(
              "parse.conflicting-resource-binding",
              "resource layout '" + key +
                  "' conflicts with an existing binding/register value; both "
                  "spellings map to resource binding",
              keyLocation);
        } else if (!layout.binding.has_value() ||
                   (bindingKey.has_value() && *bindingKey == key &&
                    *layout.binding != *parsedValue)) {
          layout.binding = *parsedValue;
          layout.bindingLocation = keyLocation;
          bindingKey = key;
          if (!valueTokens.empty()) {
            layout.bindingSpan =
                sourceSpan(keyLocation, valueTokens.back().location);
          }
        }
      } else {
        const std::string label = key == "register" ? "register" : "binding";
        diagnostics_.error(
            "parse.invalid-resource-binding",
            "resource layout " + label + " must be a non-negative integer",
            keyLocation);
      }
    } else if (key == "format") {
      if (!value.empty()) {
        layout.storageImageFormat = value;
        layout.storageImageFormatLocation = keyLocation;
      } else {
        diagnostics_.error("parse.invalid-resource-format",
                           "resource layout format must be a storage-image "
                           "format name",
                           keyLocation);
      }
    } else {
      diagnostics_.warning("parse.unsupported-resource-layout-key",
                           "ignoring unsupported resource layout key '" + key + "'",
                           keyLocation);
    }
    match(TokenKind::Comma);
  }

  if (expect(TokenKind::RParen, "expected ')' after resource layout items")) {
    layout.layoutSpan = sourceSpan(layout.location, previous().location);
  } else {
    layout.layoutSpan = layout.location;
  }
  return layout;
}

std::optional<WorkgroupSizeDecl> Parser::parseStageLayout() {
  WorkgroupSizeDecl layout;
  layout.location = current().location;
  expect(TokenKind::KeywordLayout, "expected 'layout'");
  if (!expect(TokenKind::LParen, "expected '(' after layout")) {
    synchronize();
    return std::nullopt;
  }

  while (!atEnd() && !check(TokenKind::RParen)) {
    if (!check(TokenKind::Identifier)) {
      diagnostics_.warning("parse.unsupported-layout-item",
                           "skipping unsupported layout item", current().location);
      advance();
      match(TokenKind::Comma);
      continue;
    }

    const std::string key = current().text;
    advance();
    expect(TokenKind::Equal, "expected '=' in layout item");
    std::vector<Token> valueTokens;
    int parenDepth = 0;
    int bracketDepth = 0;
    while (!atEnd() && !(parenDepth == 0 && bracketDepth == 0 &&
                         (check(TokenKind::Comma) || check(TokenKind::RParen)))) {
      if (check(TokenKind::LParen)) {
        ++parenDepth;
      } else if (check(TokenKind::RParen)) {
        --parenDepth;
      } else if (check(TokenKind::LBracket)) {
        ++bracketDepth;
      } else if (check(TokenKind::RBracket)) {
        --bracketDepth;
      }
      valueTokens.push_back(current());
      advance();
    }

    const std::string value = joinTokenText(valueTokens);
    if (key == "local_size_x") {
      layout.x = value;
      layout.xTokens = std::move(valueTokens);
    } else if (key == "local_size_y") {
      layout.y = value;
      layout.yTokens = std::move(valueTokens);
    } else if (key == "local_size_z") {
      layout.z = value;
      layout.zTokens = std::move(valueTokens);
    } else {
      diagnostics_.warning("parse.unsupported-layout-key",
                           "ignoring unsupported layout key '" + key + "'",
                           layout.location);
    }
    match(TokenKind::Comma);
  }

  expect(TokenKind::RParen, "expected ')' after layout items");
  if (check(TokenKind::KeywordIn)) {
    advance();
  }
  expect(TokenKind::Semicolon, "expected ';' after layout declaration");
  return layout;
}

std::vector<Parameter> Parser::parseParameters() {
  std::vector<Parameter> parameters;
  auto rejectInvalidVoidParameter = [&](SourceLocation location) {
    diagnostics_.error("parse.invalid-void-parameter",
                       "void parameter list must be exactly 'void'",
                       location);
    while (!atEnd() && !check(TokenKind::RParen)) {
      advance();
    }
  };

  while (!atEnd() && !check(TokenKind::RParen)) {
    if (isVoidIdentifier(current())) {
      const SourceLocation voidLocation = current().location;
      if (parameters.empty() && peek().kind == TokenKind::RParen) {
        advance();
        return parameters;
      }
      if (peek().kind == TokenKind::Comma || isNameToken(peek().kind)) {
        rejectInvalidVoidParameter(voidLocation);
        return parameters;
      }
    }

    auto type = parseType();
    if (!type) {
      synchronize();
      break;
    }
    if (type->name == "void") {
      rejectInvalidVoidParameter(type->location);
      return parameters;
    }
    if (!isNameToken(current().kind)) {
      synchronize();
      break;
    }
    Parameter parameter;
    parameter.type = std::move(*type);
    parameter.name = current().text;
    parameter.location = current().location;
    advance();
    parseArrayDeclaratorSuffix(parameter.type,
                               "expected ']' after parameter array size");
    parameters.push_back(std::move(parameter));
    if (!match(TokenKind::Comma)) {
      break;
    }
  }
  return parameters;
}

void Parser::parseArrayDeclaratorSuffix(TypeRef &type, std::string_view message) {
  while (match(TokenKind::LBracket)) {
    std::ostringstream size;
    while (!atEnd() && !check(TokenKind::RBracket)) {
      size << current().text;
      advance();
    }
    appendArrayDimension(type, size.str());
    expect(TokenKind::RBracket, message);
  }
}

std::vector<Token> Parser::parseBalancedBody() {
  std::vector<Token> body;
  if (!expect(TokenKind::LBrace, "expected function body")) {
    return body;
  }

  int depth = 1;
  while (!atEnd() && depth > 0) {
    if (check(TokenKind::LBrace)) {
      ++depth;
      body.push_back(current());
      advance();
      continue;
    }
    if (check(TokenKind::RBrace)) {
      --depth;
      if (depth == 0) {
        advance();
        break;
      }
      body.push_back(current());
      advance();
      continue;
    }
    body.push_back(current());
    advance();
  }
  return body;
}

std::optional<StageDecl> Parser::parseStage() {
  StageDecl stage;
  stage.stage = stageName(current().kind);
  stage.location = current().location;
  advance();

  if (check(TokenKind::Identifier)) {
    stage.name = current().text;
    advance();
  }

  if (!expect(TokenKind::LBrace, "expected '{' after stage declaration")) {
    synchronize();
    return std::nullopt;
  }

  while (!atEnd() && !check(TokenKind::RBrace)) {
    if (check(TokenKind::KeywordStruct)) {
      if (auto decl = parseStruct()) {
        stage.structs.push_back(std::move(*decl));
      }
      continue;
    }
    if (diagnoseAndSkipUnsupportedStageItem()) {
      continue;
    }
    if (check(TokenKind::KeywordLayout)) {
      if (layoutIntroducesResource()) {
        auto layout = parseResourceLayout();
        if (auto resource = parseResource(std::move(layout))) {
          stage.resources.push_back(std::move(*resource));
        }
        continue;
      }
      if (auto layout = parseStageLayout()) {
        stage.workgroupSize = std::move(*layout);
      }
      continue;
    }
    if (looksLikeFunction()) {
      if (auto function = parseFunction()) {
        stage.functions.push_back(std::move(*function));
      }
      continue;
    }
    if (looksLikeDeclaration()) {
      if (auto resource = parseResource()) {
        stage.resources.push_back(std::move(*resource));
      }
      continue;
    }
    skipDeclarationOrBlock();
  }

  expect(TokenKind::RBrace, "expected '}' after stage body");
  return stage;
}

bool Parser::looksLikeFunction() const {
  return (current().kind == TokenKind::Identifier ||
          current().kind == TokenKind::KeywordUniform ||
          current().kind == TokenKind::KeywordBuffer ||
          current().kind == TokenKind::KeywordShared) &&
         peek().kind == TokenKind::Identifier &&
         peek(2).kind == TokenKind::LParen;
}

bool Parser::looksLikeDeclaration() const {
  if (isVarResourceStart(current(), peek())) {
    return true;
  }
  if (isStorageImageAccessQualifier(current().kind)) {
    return peek().kind == TokenKind::KeywordUniform &&
           peek(2).kind == TokenKind::Identifier;
  }
  return (current().kind == TokenKind::Identifier ||
          current().kind == TokenKind::KeywordUniform ||
          current().kind == TokenKind::KeywordBuffer ||
          current().kind == TokenKind::KeywordShared) &&
         peek().kind == TokenKind::Identifier;
}

bool Parser::layoutIntroducesResource() const {
  if (!check(TokenKind::KeywordLayout) || peek().kind != TokenKind::LParen) {
    return false;
  }

  int depth = 0;
  for (std::size_t lookahead = 1; index_ + lookahead < tokens_.size(); ++lookahead) {
    const Token &token = peek(lookahead);
    if (token.kind == TokenKind::LParen) {
      ++depth;
    } else if (token.kind == TokenKind::RParen) {
      --depth;
      if (depth == 0) {
        TokenKind next = peek(lookahead + 1).kind;
        if (isStorageImageAccessQualifier(next)) {
          return peek(lookahead + 2).kind == TokenKind::KeywordUniform;
        }
        return next == TokenKind::KeywordUniform ||
               next == TokenKind::KeywordBuffer ||
               next == TokenKind::KeywordShared ||
               next == TokenKind::Identifier;
      }
    }
  }
  return false;
}

void Parser::diagnoseUnsupportedNativeV0(std::string_view form,
                                         SourceLocation location) {
  diagnostics_.error(std::string(kSpecUnsupportedForNativeV0),
                     "CrossTL/CrossGL native v0 does not support " +
                         std::string(form),
                     std::move(location));
}

bool Parser::diagnoseAndSkipUnsupportedPreambleItem() {
  if (check(TokenKind::Hash)) {
    diagnoseUnsupportedNativeV0("preprocessor directives", current().location);
    skipPreprocessorDirective();
    return true;
  }
  if (current().kind == TokenKind::Identifier &&
      isUnsupportedImportName(current().text)) {
    diagnoseUnsupportedNativeV0("source import declarations",
                                current().location);
    skipDeclarationOrBlock();
    return true;
  }
  return false;
}

bool Parser::diagnoseAndSkipUnsupportedShaderItem() {
  if (check(TokenKind::Hash)) {
    diagnoseUnsupportedNativeV0("preprocessor directives", current().location);
    skipPreprocessorDirective();
    return true;
  }
  if (isColonStyleVarDeclarationStart(current(), peek(), peek(2))) {
    diagnoseUnsupportedNativeV0(
        "colon-style variable declarations (compatibility id decl.colon-var)",
        current().location);
    skipDeclarationOrBlock();
    return true;
  }
  if (auto form = unsupportedShaderItemForm(current())) {
    diagnoseUnsupportedNativeV0(*form, current().location);
    skipDeclarationOrBlock();
    return true;
  }
  return false;
}

bool Parser::diagnoseAndSkipUnsupportedStageItem() {
  if (check(TokenKind::Hash)) {
    diagnoseUnsupportedNativeV0("preprocessor directives", current().location);
    skipPreprocessorDirective();
    return true;
  }
  if (isColonStyleVarDeclarationStart(current(), peek(), peek(2))) {
    diagnoseUnsupportedNativeV0(
        "colon-style variable declarations (compatibility id decl.colon-var)",
        current().location);
    skipDeclarationOrBlock();
    return true;
  }
  if (auto form = unsupportedShaderItemForm(current())) {
    diagnoseUnsupportedNativeV0(*form, current().location);
    skipDeclarationOrBlock();
    return true;
  }
  return false;
}

bool Parser::diagnoseAndSkipUnsupportedStructItem() {
  if (check(TokenKind::Hash)) {
    diagnoseUnsupportedNativeV0("preprocessor directives", current().location);
    skipPreprocessorDirective();
    return true;
  }
  if (auto form = unsupportedStructItemForm(current())) {
    diagnoseUnsupportedNativeV0(*form, current().location);
    skipDeclarationOrBlock();
    return true;
  }
  return false;
}

void Parser::skipPreprocessorDirective() {
  const std::size_t line = current().location.line;
  while (!atEnd() && current().location.line == line) {
    advance();
  }
}

void Parser::diagnoseUnsupportedFunctionBodyForms(
    const std::vector<Token> &tokens) {
  for (std::size_t index = 0; index < tokens.size(); ++index) {
    const Token &token = tokens[index];
    if (token.kind == TokenKind::Hash) {
      diagnoseUnsupportedNativeV0("preprocessor directives", token.location);
      return;
    }
    if (!isStatementStart(tokens, index)) {
      continue;
    }
    if (token.kind != TokenKind::Identifier) {
      continue;
    }

    if (token.text == "match" || token.text == "switch" ||
        token.text == "case" || token.text == "default" ||
        token.text == "loop" || token.text == "do") {
      diagnoseUnsupportedNativeV0(unsupportedPatternControlForm(token.text),
                                  token.location);
      return;
    }
    if (isForInStatement(tokens, index)) {
      diagnoseUnsupportedNativeV0("for-in loop statements", token.location);
      return;
    }
    if (isLetMutDeclaration(tokens, index)) {
      diagnoseUnsupportedNativeV0("let mut declarations", token.location);
      return;
    }
    if (hasMalformedControlHeader(tokens, index)) {
      diagnoseUnsupportedNativeV0("malformed control headers", token.location);
      return;
    }
  }
}

void Parser::skipDeclarationOrBlock() {
  if (check(TokenKind::LBrace)) {
    parseBalancedBody();
    return;
  }
  while (!atEnd() && !check(TokenKind::Semicolon) && !check(TokenKind::RBrace)) {
    if (check(TokenKind::LBrace)) {
      parseBalancedBody();
      return;
    }
    advance();
  }
  match(TokenKind::Semicolon);
}

} // namespace crossgl
