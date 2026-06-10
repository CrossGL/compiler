#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/Frontend/Token.h"

namespace crossgl {

struct TypeRef {
  std::string name;
  std::optional<std::string> arraySize;
  SourceLocation location;
};

struct StructField {
  TypeRef type;
  std::string name;
  SourceLocation location;
};

struct StructDecl {
  std::string name;
  std::vector<StructField> fields;
  SourceLocation location;
  SourceLocation declarationSpan;
  SourceLocation nameSpan;
};

struct Parameter {
  TypeRef type;
  std::string name;
  SourceLocation location;
};

struct FunctionDecl {
  TypeRef returnType;
  std::string name;
  std::vector<Parameter> parameters;
  std::vector<Token> bodyTokens;
  SourceLocation location;
};

struct ResourceLayoutDecl {
  std::optional<std::size_t> set;
  std::optional<std::size_t> binding;
  std::optional<std::string> storageImageFormat;
  SourceLocation location;
  SourceLocation bindingLocation;
  SourceLocation storageImageFormatLocation;
  SourceLocation layoutSpan;
  SourceLocation setSpan;
  SourceLocation bindingSpan;
};

struct ResourceDecl {
  TypeRef type;
  std::string name;
  std::optional<std::size_t> set;
  std::optional<std::size_t> binding;
  std::optional<std::string> storageImageAccessQualifier;
  std::optional<std::string> storageImageFormat;
  SourceLocation location;
  SourceLocation bindingLocation;
  SourceLocation storageImageAccessLocation;
  SourceLocation storageImageFormatLocation;
  SourceLocation declarationSpan;
  SourceLocation nameSpan;
  SourceLocation layoutSpan;
  SourceLocation setSpan;
  SourceLocation bindingSpan;
};

struct WorkgroupSizeDecl {
  std::string x = "1";
  std::string y = "1";
  std::string z = "1";
  std::vector<Token> xTokens;
  std::vector<Token> yTokens;
  std::vector<Token> zTokens;
  SourceLocation location;
};

struct StageDecl {
  std::string stage;
  std::string name;
  std::vector<StructDecl> structs;
  std::vector<ResourceDecl> resources;
  std::optional<WorkgroupSizeDecl> workgroupSize;
  std::vector<FunctionDecl> functions;
  SourceLocation location;
};

struct ConstantDecl {
  TypeRef type;
  std::string name;
  std::vector<Token> valueTokens;
  std::optional<std::size_t> specializationId;
  SourceLocation location;
  SourceLocation specializationIdSpan;
};

struct ShaderModule {
  std::string name;
  std::vector<StructDecl> structs;
  std::vector<StructDecl> cbuffers;
  std::vector<ConstantDecl> constants;
  std::vector<FunctionDecl> functions;
  std::vector<StageDecl> stages;
  SourceLocation location;
};

} // namespace crossgl
