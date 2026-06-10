#pragma once

#include <optional>
#include <span>

#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/Frontend/AST.h"
#include "crossgl/Frontend/Token.h"

namespace crossgl {

class Parser {
public:
  Parser(std::span<const Token> tokens, DiagnosticEngine &diagnostics);

  std::optional<ShaderModule> parseModule();

private:
  bool atEnd() const;
  const Token &current() const;
  const Token &peek(std::size_t lookahead = 1) const;
  bool check(TokenKind kind) const;
  bool match(TokenKind kind);
  bool expect(TokenKind kind, std::string_view message);
  const Token &previous() const;
  void advance();
  void synchronize();

  std::optional<TypeRef> parseType();
  std::optional<StructDecl> parseStruct();
  std::optional<StructDecl> parseCBuffer();
  void skipGenericClause();
  std::optional<ConstantDecl>
  parseConstant(std::optional<ConstantDecl> layout = std::nullopt);
  std::optional<ConstantDecl> parseSpecializationConstantLayout();
  std::optional<FunctionDecl> parseFunction();
  std::optional<FunctionDecl> parseFnStyleFunction();
  std::optional<ResourceDecl> parseResource(std::optional<ResourceLayoutDecl> layout = std::nullopt);
  std::optional<ResourceLayoutDecl> parseResourceLayout();
  std::optional<WorkgroupSizeDecl> parseStageLayout();
  std::vector<Parameter> parseParameters(bool allowColonStyle = false);
  void parseArrayDeclaratorSuffix(TypeRef &type, std::string_view message);
  std::vector<Token> parseBalancedBody();
  void diagnoseUnsupportedFunctionBodyForms(const std::vector<Token> &tokens);
  std::optional<StageDecl> parseStage();

  bool looksLikeFunction() const;
  bool looksLikeDeclaration() const;
  bool layoutIntroducesConstant() const;
  bool layoutContainsKey(std::string_view key) const;
  bool layoutIntroducesResource() const;
  void diagnoseUnsupportedNativeV0(std::string_view form,
                                   SourceLocation location);
  bool diagnoseAndSkipUnsupportedPreambleItem();
  bool diagnoseAndSkipUnsupportedShaderItem();
  bool diagnoseAndSkipUnsupportedStageItem();
  bool diagnoseAndSkipUnsupportedStructItem();
  void skipPreprocessorDirective();
  void skipDeclarationOrBlock();

  std::span<const Token> tokens_;
  DiagnosticEngine &diagnostics_;
  std::size_t index_ = 0;
};

} // namespace crossgl
