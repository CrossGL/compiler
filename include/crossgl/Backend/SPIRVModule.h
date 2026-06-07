#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace crossgl {

class SPIRVId {
public:
  SPIRVId() = default;
  explicit SPIRVId(std::string text);

  [[nodiscard]] const std::string &str() const { return text_; }
  [[nodiscard]] bool empty() const { return text_.empty(); }

private:
  std::string text_;
};

enum class SPIRVExecutionModel {
  Vertex,
  Fragment,
  GLCompute,
};

enum class SPIRVAddressingModel {
  Logical,
};

enum class SPIRVMemoryModel {
  GLSL450,
};

enum class SPIRVStorageClass {
  Function,
  Input,
  Output,
  Uniform,
  UniformConstant,
  StorageBuffer,
  Workgroup,
  Image,
};

enum class SPIRVCapability {
  Shader,
  RuntimeDescriptorArrayEXT,
  ShaderNonUniformEXT,
  SampledImageArrayNonUniformIndexingEXT,
  StorageImageArrayNonUniformIndexingEXT,
  StorageBufferArrayNonUniformIndexingEXT,
};

enum class SPIRVExtension {
  SPV_EXT_descriptor_indexing,
};

enum class SPIRVExtInstInstructionSet {
  GLSLStd450,
};

enum class SPIRVDecoration {
  ArrayStride,
  Binding,
  Block,
  DescriptorSet,
  Offset,
};

struct SPIRVFunctionDefinition {
  SPIRVId id;
  SPIRVId returnType;
  SPIRVId functionType;
  std::string functionControl = "None";
  std::string entryLabel;
  std::vector<std::string> parameterLines;
  std::vector<std::string> variableLines;
  std::vector<std::string> instructionLines;
  bool hasTerminator = false;
  std::string defaultTerminator = "OpReturn";
};

struct SPIRVCapabilityDeclaration {
  std::string capability;
};

struct SPIRVExtensionDeclaration {
  std::string extension;
};

struct SPIRVExtInstImportDefinition {
  SPIRVId result;
  std::string instructionSet;
};

struct SPIRVMemoryModelDefinition {
  SPIRVAddressingModel addressingModel = SPIRVAddressingModel::Logical;
  SPIRVMemoryModel memoryModel = SPIRVMemoryModel::GLSL450;
};

struct SPIRVEntryPointDefinition {
  SPIRVExecutionModel executionModel = SPIRVExecutionModel::GLCompute;
  SPIRVId functionId;
  std::string name;
  std::vector<SPIRVId> interfaces;
};

struct SPIRVExecutionModeDefinition {
  SPIRVId entryPoint;
  std::string mode;
  std::vector<std::string> operands;
};

struct SPIRVRenderOptions {
  bool emitDisassemblyHeader = false;
  std::string version = "1.0";
  std::string generator;
  std::optional<std::size_t> bound;
  bool emitSchema = true;
  bool validateReferences = true;
};

std::string_view spirvExecutionModelName(SPIRVExecutionModel model);
std::string_view spirvAddressingModelName(SPIRVAddressingModel model);
std::string_view spirvMemoryModelName(SPIRVMemoryModel model);
std::string_view spirvStorageClassName(SPIRVStorageClass storageClass);
std::string_view spirvCapabilityName(SPIRVCapability capability);
std::string_view spirvExtensionName(SPIRVExtension extension);
std::string_view
spirvExtInstInstructionSetName(SPIRVExtInstInstructionSet instructionSet);
std::string_view spirvDecorationName(SPIRVDecoration decoration);

class SPIRVModule {
public:
  [[nodiscard]] static SPIRVId id(std::string text);

  [[nodiscard]] SPIRVId nextResultId(std::string_view prefix = "tmp");
  [[nodiscard]] SPIRVId nextLabelId(std::string_view prefix);

  void addCapability(std::string_view capability);
  void addCapability(SPIRVCapability capability);
  void addExtension(std::string_view extension);
  void addExtension(SPIRVExtension extension);
  SPIRVId addExtInstImport(const SPIRVId &result,
                           std::string_view instructionSet);
  SPIRVId addExtInstImport(const SPIRVId &result,
                           SPIRVExtInstInstructionSet instructionSet);
  void setMemoryModel(SPIRVAddressingModel addressingModel,
                      SPIRVMemoryModel memoryModel);
  void addEntryPoint(SPIRVExecutionModel executionModel,
                     const SPIRVId &functionId, std::string_view name,
                     const std::vector<SPIRVId> &interfaces);
  void addExecutionMode(const SPIRVId &entryPoint, std::string_view mode,
                        const std::vector<std::string> &operands);

  void addName(const SPIRVId &target, std::string_view name);
  void addMemberName(const SPIRVId &target, std::size_t member,
                     std::string_view name);
  void addName(std::string line);
  void addDecoration(const SPIRVId &target, std::string_view decoration,
                     const std::vector<std::string> &operands = {});
  void addDecoration(const SPIRVId &target, SPIRVDecoration decoration,
                     const std::vector<std::string> &operands = {});
  void addMemberDecoration(const SPIRVId &target, std::size_t member,
                           std::string_view decoration,
                           const std::vector<std::string> &operands = {});
  void addMemberDecoration(const SPIRVId &target, std::size_t member,
                           SPIRVDecoration decoration,
                           const std::vector<std::string> &operands = {});
  void decorateArrayStride(const SPIRVId &target, std::size_t strideBytes);
  void decorateBlock(const SPIRVId &target);
  void decorateDescriptorSetBinding(const SPIRVId &target, std::size_t set,
                                    std::size_t binding);
  void decorateMemberOffset(const SPIRVId &target, std::size_t member,
                            std::size_t offsetBytes);
  void addAnnotation(std::string line);
  void addTypeInstruction(std::string line);
  void addConstantInstruction(std::string line);
  void addGlobalInstruction(std::string line);
  void addFunction(SPIRVFunctionDefinition function);

  void defineType(const SPIRVId &result, std::string_view opcode,
                  const std::vector<std::string> &operands = {});
  void defineRuntimeArrayType(const SPIRVId &result,
                              const SPIRVId &elementType);
  void defineArrayType(const SPIRVId &result, const SPIRVId &elementType,
                       const SPIRVId &length);
  void defineStructType(const SPIRVId &result,
                        const std::vector<SPIRVId> &memberTypes);
  void definePointerType(const SPIRVId &result,
                         SPIRVStorageClass storageClass,
                         const SPIRVId &pointeeType);
  void defineConstant(const SPIRVId &result, const SPIRVId &type,
                      std::string_view literal);
  void defineBoolConstant(const SPIRVId &result, const SPIRVId &type,
                          bool value);
  void defineGlobalVariable(const SPIRVId &result, const SPIRVId &pointerType,
                            SPIRVStorageClass storageClass);

  [[nodiscard]] std::string render(
      const SPIRVRenderOptions &options = SPIRVRenderOptions{}) const;

private:
  static std::string sanitizePrefix(std::string_view prefix);
  [[nodiscard]] SPIRVId allocateId(std::string_view prefix,
                                   std::size_t &nextIndex);
  void reserveIdReference(const SPIRVId &id);
  void reserveDefinedId(const SPIRVId &id, std::string_view context);
  void reserveDefinedIdText(std::string_view id, std::string_view context);
  void reserveDefinedIdFromInstruction(std::string_view line,
                                        std::string_view context);
  void validateStructuredReferences() const;
  void validateReferencedIds() const;

  std::size_t nextResultIndex_ = 0;
  std::size_t nextLabelIndex_ = 0;
  std::vector<SPIRVCapabilityDeclaration> capabilities_;
  std::vector<SPIRVExtensionDeclaration> extensions_;
  std::vector<SPIRVExtInstImportDefinition> imports_;
  std::optional<SPIRVMemoryModelDefinition> memoryModel_;
  std::vector<SPIRVEntryPointDefinition> entryPoints_;
  std::vector<SPIRVExecutionModeDefinition> executionModes_;
  std::vector<std::string> names_;
  std::vector<std::string> annotations_;
  std::vector<std::string> types_;
  std::vector<std::string> constants_;
  std::vector<std::string> globals_;
  std::vector<SPIRVFunctionDefinition> functions_;
  std::unordered_set<std::string> capabilitySet_;
  std::unordered_set<std::string> extensionSet_;
  std::unordered_map<std::string, std::string> importInstructionSetById_;
  std::unordered_map<std::string, std::string> importIdByInstructionSet_;
  std::unordered_set<std::string> allocatedIds_;
  std::unordered_set<std::string> definedIds_;
  std::unordered_set<std::string> entryPointIds_;
  std::unordered_set<std::string> referencedIdSet_;
  std::vector<std::string> referencedIds_;
};

} // namespace crossgl
