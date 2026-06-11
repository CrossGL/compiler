#include "crossgl/Backend/SPIRVModule.h"

#include <stdexcept>
#include <sstream>
#include <utility>

namespace crossgl {
namespace {

std::string quoteSPIRVString(std::string_view text) {
  std::string result = "\"";
  for (const char character : text) {
    if (character == '\\' || character == '"') {
      result.push_back('\\');
    }
    result.push_back(character);
  }
  result.push_back('"');
  return result;
}

bool appendLine(std::ostringstream &out, const std::string &line,
                std::size_t *lineNumber = nullptr) {
  if (!line.empty()) {
    out << line << "\n";
    if (lineNumber != nullptr) {
      ++*lineNumber;
    }
    return true;
  }
  return false;
}

void appendSection(std::ostringstream &out,
                   const std::vector<std::string> &section,
                   std::size_t *lineNumber = nullptr) {
  for (const std::string &line : section) {
    appendLine(out, line, lineNumber);
  }
}

std::string joinInstruction(std::string lhs, std::string_view opcode,
                            const std::vector<std::string> &operands) {
  lhs += " = ";
  lhs += opcode;
  for (const std::string &operand : operands) {
    lhs += " ";
    lhs += operand;
  }
  return lhs;
}

void appendOperands(std::string &line,
                    const std::vector<std::string> &operands) {
  for (const std::string &operand : operands) {
    line += " ";
    line += operand;
  }
}

std::string leadingResultId(std::string_view line) {
  if (line.empty() || line.front() != '%') {
    return {};
  }
  const std::size_t separator = line.find(" = ");
  if (separator == std::string_view::npos) {
    return {};
  }
  return std::string(line.substr(0, separator));
}

void requireNonEmpty(std::string_view value, std::string_view context) {
  if (value.empty()) {
    throw std::logic_error("SPIR-V " + std::string(context) +
                           " must not be empty");
  }
}

std::string renderCapability(const SPIRVCapabilityDeclaration &capability) {
  return "OpCapability " + capability.capability;
}

std::string renderExtension(const SPIRVExtensionDeclaration &extension) {
  return "OpExtension " + quoteSPIRVString(extension.extension);
}

std::string
renderExtInstImport(const SPIRVExtInstImportDefinition &importDefinition) {
  return importDefinition.result.str() + " = OpExtInstImport " +
         quoteSPIRVString(importDefinition.instructionSet);
}

std::string renderMemoryModel(const SPIRVMemoryModelDefinition &memoryModel) {
  return "OpMemoryModel " +
         std::string(spirvAddressingModelName(memoryModel.addressingModel)) +
         " " + std::string(spirvMemoryModelName(memoryModel.memoryModel));
}

std::string renderEntryPoint(const SPIRVEntryPointDefinition &entryPoint) {
  std::string line = "OpEntryPoint ";
  line += spirvExecutionModelName(entryPoint.executionModel);
  line += " ";
  line += entryPoint.functionId.str();
  line += " ";
  line += quoteSPIRVString(entryPoint.name);
  for (const SPIRVId &interfaceId : entryPoint.interfaces) {
    line += " ";
    line += interfaceId.str();
  }
  return line;
}

std::string renderExecutionMode(
    const SPIRVExecutionModeDefinition &executionMode) {
  std::string line = "OpExecutionMode ";
  line += executionMode.entryPoint.str();
  line += " ";
  line += executionMode.mode;
  appendOperands(line, executionMode.operands);
  return line;
}

} // namespace

SPIRVId::SPIRVId(std::string text) : text_(std::move(text)) {}

std::string_view spirvExecutionModelName(SPIRVExecutionModel model) {
  switch (model) {
  case SPIRVExecutionModel::Vertex:
    return "Vertex";
  case SPIRVExecutionModel::Fragment:
    return "Fragment";
  case SPIRVExecutionModel::GLCompute:
    return "GLCompute";
  }
  return "Unknown";
}

std::string_view spirvAddressingModelName(SPIRVAddressingModel model) {
  switch (model) {
  case SPIRVAddressingModel::Logical:
    return "Logical";
  }
  return "Logical";
}

std::string_view spirvMemoryModelName(SPIRVMemoryModel model) {
  switch (model) {
  case SPIRVMemoryModel::GLSL450:
    return "GLSL450";
  }
  return "GLSL450";
}

std::string_view spirvStorageClassName(SPIRVStorageClass storageClass) {
  switch (storageClass) {
  case SPIRVStorageClass::Function:
    return "Function";
  case SPIRVStorageClass::Input:
    return "Input";
  case SPIRVStorageClass::Output:
    return "Output";
  case SPIRVStorageClass::Uniform:
    return "Uniform";
  case SPIRVStorageClass::UniformConstant:
    return "UniformConstant";
  case SPIRVStorageClass::StorageBuffer:
    return "StorageBuffer";
  case SPIRVStorageClass::Workgroup:
    return "Workgroup";
  case SPIRVStorageClass::Image:
    return "Image";
  }
  return "Function";
}

std::string_view spirvCapabilityName(SPIRVCapability capability) {
  switch (capability) {
  case SPIRVCapability::Shader:
    return "Shader";
  case SPIRVCapability::ImageQuery:
    return "ImageQuery";
  case SPIRVCapability::RuntimeDescriptorArrayEXT:
    return "RuntimeDescriptorArrayEXT";
  case SPIRVCapability::ShaderNonUniformEXT:
    return "ShaderNonUniformEXT";
  case SPIRVCapability::SampledImageArrayNonUniformIndexingEXT:
    return "SampledImageArrayNonUniformIndexingEXT";
  case SPIRVCapability::StorageImageArrayNonUniformIndexingEXT:
    return "StorageImageArrayNonUniformIndexingEXT";
  case SPIRVCapability::StorageBufferArrayNonUniformIndexingEXT:
    return "StorageBufferArrayNonUniformIndexingEXT";
  }
  return "Unknown";
}

std::string_view spirvExtensionName(SPIRVExtension extension) {
  switch (extension) {
  case SPIRVExtension::SPV_EXT_descriptor_indexing:
    return "SPV_EXT_descriptor_indexing";
  }
  return "Unknown";
}

std::string_view
spirvExtInstInstructionSetName(SPIRVExtInstInstructionSet instructionSet) {
  switch (instructionSet) {
  case SPIRVExtInstInstructionSet::GLSLStd450:
    return "GLSL.std.450";
  }
  return "Unknown";
}

std::string_view spirvDecorationName(SPIRVDecoration decoration) {
  switch (decoration) {
  case SPIRVDecoration::ArrayStride:
    return "ArrayStride";
  case SPIRVDecoration::Binding:
    return "Binding";
  case SPIRVDecoration::Block:
    return "Block";
  case SPIRVDecoration::DescriptorSet:
    return "DescriptorSet";
  case SPIRVDecoration::Offset:
    return "Offset";
  }
  return "Unknown";
}

SPIRVId SPIRVModule::id(std::string text) {
  if (!text.empty() && text.front() != '%') {
    text.insert(text.begin(), '%');
  }
  return SPIRVId(std::move(text));
}

SPIRVId SPIRVModule::nextResultId(std::string_view prefix) {
  return allocateId(prefix, nextResultIndex_);
}

SPIRVId SPIRVModule::nextLabelId(std::string_view prefix) {
  return allocateId(prefix, nextLabelIndex_);
}

void SPIRVModule::addCapability(std::string_view capability) {
  const std::string text(capability);
  requireNonEmpty(text, "capability");
  if (capabilitySet_.insert(text).second) {
    capabilities_.push_back(SPIRVCapabilityDeclaration{text});
  }
}

void SPIRVModule::addCapability(SPIRVCapability capability) {
  addCapability(spirvCapabilityName(capability));
}

void SPIRVModule::addExtension(std::string_view extension) {
  const std::string text(extension);
  requireNonEmpty(text, "extension");
  if (extensionSet_.insert(text).second) {
    extensions_.push_back(SPIRVExtensionDeclaration{text});
  }
}

void SPIRVModule::addExtension(SPIRVExtension extension) {
  addExtension(spirvExtensionName(extension));
}

SPIRVId SPIRVModule::addExtInstImport(const SPIRVId &result,
                                      std::string_view instructionSet) {
  if (result.empty()) {
    throw std::logic_error("SPIR-V OpExtInstImport requires a result id");
  }
  const std::string resultText = result.str();
  const std::string instructionSetText(instructionSet);
  requireNonEmpty(instructionSetText, "OpExtInstImport instruction set");

  if (auto existing = importInstructionSetById_.find(resultText);
      existing != importInstructionSetById_.end()) {
    if (existing->second != instructionSetText) {
      throw std::logic_error("SPIR-V OpExtInstImport result id '" +
                             resultText +
                             "' already imports a different instruction set");
    }
    return result;
  }
  if (auto existing = importIdByInstructionSet_.find(instructionSetText);
      existing != importIdByInstructionSet_.end()) {
    if (existing->second != resultText) {
      throw std::logic_error("SPIR-V OpExtInstImport instruction set '" +
                             instructionSetText +
                             "' already uses result id '" + existing->second +
                             "'");
    }
    return result;
  }

  reserveDefinedId(result, "OpExtInstImport");
  importInstructionSetById_[resultText] = instructionSetText;
  importIdByInstructionSet_[instructionSetText] = resultText;
  imports_.push_back(SPIRVExtInstImportDefinition{result, instructionSetText});
  return result;
}

SPIRVId
SPIRVModule::addExtInstImport(const SPIRVId &result,
                              SPIRVExtInstInstructionSet instructionSet) {
  return addExtInstImport(result,
                          spirvExtInstInstructionSetName(instructionSet));
}

void SPIRVModule::setMemoryModel(SPIRVAddressingModel addressingModel,
                                 SPIRVMemoryModel memoryModel) {
  memoryModel_ = SPIRVMemoryModelDefinition{addressingModel, memoryModel};
}

void SPIRVModule::addEntryPoint(SPIRVExecutionModel executionModel,
                                const SPIRVId &functionId,
                                std::string_view name,
                                const std::vector<SPIRVId> &interfaces) {
  if (functionId.empty()) {
    throw std::logic_error("SPIR-V entry point requires a function id");
  }
  reserveIdReference(functionId);
  entryPointIds_.insert(functionId.str());
  SPIRVEntryPointDefinition entryPoint;
  entryPoint.executionModel = executionModel;
  entryPoint.functionId = functionId;
  entryPoint.name = std::string(name);
  entryPoint.interfaces.reserve(interfaces.size());
  for (const SPIRVId &interfaceId : interfaces) {
    reserveIdReference(interfaceId);
    entryPoint.interfaces.push_back(interfaceId);
  }
  entryPoints_.push_back(std::move(entryPoint));
}

void SPIRVModule::addExecutionMode(const SPIRVId &entryPoint,
                                   std::string_view mode,
                                   const std::vector<std::string> &operands) {
  if (entryPoint.empty()) {
    throw std::logic_error("SPIR-V execution mode requires an entry point id");
  }
  reserveIdReference(entryPoint);
  SPIRVExecutionModeDefinition executionMode;
  executionMode.entryPoint = entryPoint;
  executionMode.mode = std::string(mode);
  executionMode.operands = operands;
  executionModes_.push_back(std::move(executionMode));
}

void SPIRVModule::addName(const SPIRVId &target, std::string_view name) {
  reserveIdReference(target);
  names_.push_back("OpName " + target.str() + " " + quoteSPIRVString(name));
}

void SPIRVModule::addMemberName(const SPIRVId &target, std::size_t member,
                                std::string_view name) {
  reserveIdReference(target);
  names_.push_back("OpMemberName " + target.str() + " " +
                   std::to_string(member) + " " + quoteSPIRVString(name));
}

void SPIRVModule::addName(std::string line) {
  names_.push_back(std::move(line));
}

void SPIRVModule::addDecoration(const SPIRVId &target,
                                std::string_view decoration,
                                const std::vector<std::string> &operands) {
  reserveIdReference(target);
  std::string line =
      "OpDecorate " + target.str() + " " + std::string(decoration);
  appendOperands(line, operands);
  annotations_.push_back(std::move(line));
}

void SPIRVModule::addDecoration(
    const SPIRVId &target, SPIRVDecoration decoration,
    const std::vector<std::string> &operands) {
  addDecoration(target, spirvDecorationName(decoration), operands);
}

void SPIRVModule::addMemberDecoration(
    const SPIRVId &target, std::size_t member, std::string_view decoration,
    const std::vector<std::string> &operands) {
  reserveIdReference(target);
  std::string line = "OpMemberDecorate " + target.str() + " " +
                     std::to_string(member) + " " + std::string(decoration);
  appendOperands(line, operands);
  annotations_.push_back(std::move(line));
}

void SPIRVModule::addMemberDecoration(
    const SPIRVId &target, std::size_t member, SPIRVDecoration decoration,
    const std::vector<std::string> &operands) {
  addMemberDecoration(target, member, spirvDecorationName(decoration), operands);
}

void SPIRVModule::decorateArrayStride(const SPIRVId &target,
                                      std::size_t strideBytes) {
  addDecoration(target, SPIRVDecoration::ArrayStride,
                {std::to_string(strideBytes)});
}

void SPIRVModule::decorateBlock(const SPIRVId &target) {
  addDecoration(target, SPIRVDecoration::Block);
}

void SPIRVModule::decorateDescriptorSetBinding(const SPIRVId &target,
                                               std::size_t set,
                                               std::size_t binding) {
  addDecoration(target, SPIRVDecoration::DescriptorSet, {std::to_string(set)});
  addDecoration(target, SPIRVDecoration::Binding, {std::to_string(binding)});
}

void SPIRVModule::decorateMemberOffset(const SPIRVId &target,
                                       std::size_t member,
                                       std::size_t offsetBytes) {
  addMemberDecoration(target, member, SPIRVDecoration::Offset,
                      {std::to_string(offsetBytes)});
}

void SPIRVModule::addAnnotation(std::string line) {
  annotations_.push_back(std::move(line));
}

void SPIRVModule::addTypeInstruction(std::string line) {
  reserveDefinedIdFromInstruction(line, "type instruction");
  types_.push_back(std::move(line));
}

void SPIRVModule::addConstantInstruction(std::string line) {
  reserveDefinedIdFromInstruction(line, "constant instruction");
  constants_.push_back(std::move(line));
}

void SPIRVModule::addGlobalInstruction(std::string line) {
  reserveDefinedIdFromInstruction(line, "global instruction");
  globals_.push_back(std::move(line));
}

void SPIRVModule::addFunction(SPIRVFunctionDefinition function) {
  const bool hasBody =
      !function.parameterLines.empty() || !function.variableLines.empty() ||
      !function.instructionLines.empty() || function.hasTerminator ||
      !function.defaultTerminator.empty();
  if (function.id.empty() || function.returnType.empty() ||
      function.functionType.empty()) {
    throw std::logic_error("SPIR-V function requires id, return type, and "
                           "function type identifiers");
  }
  if (hasBody && function.entryLabel.empty()) {
    throw std::logic_error("SPIR-V function body requires an entry label");
  }
  if (!function.entryLabel.empty() && !function.hasTerminator &&
      function.defaultTerminator.empty()) {
    throw std::logic_error("SPIR-V function body requires a terminator");
  }
  reserveDefinedId(function.id, "OpFunction");
  reserveIdReference(function.returnType);
  reserveIdReference(function.functionType);
  for (const std::string &line : function.parameterLines) {
    reserveDefinedIdFromInstruction(line, "function parameter");
  }
  if (!function.entryLabel.empty()) {
    reserveDefinedIdText(function.entryLabel, "function entry label");
  }
  for (const std::string &line : function.variableLines) {
    reserveDefinedIdFromInstruction(line, "function variable");
  }
  for (const std::string &line : function.instructionLines) {
    reserveDefinedIdFromInstruction(line, "function instruction");
  }
  functions_.push_back(std::move(function));
}

void SPIRVModule::defineType(const SPIRVId &result, std::string_view opcode,
                             const std::vector<std::string> &operands) {
  addTypeInstruction(joinInstruction(result.str(), opcode, operands));
}

void SPIRVModule::defineRuntimeArrayType(const SPIRVId &result,
                                         const SPIRVId &elementType) {
  reserveIdReference(elementType);
  defineType(result, "OpTypeRuntimeArray", {elementType.str()});
}

void SPIRVModule::defineArrayType(const SPIRVId &result,
                                  const SPIRVId &elementType,
                                  const SPIRVId &length) {
  reserveIdReference(elementType);
  reserveIdReference(length);
  defineType(result, "OpTypeArray", {elementType.str(), length.str()});
}

void SPIRVModule::defineStructType(
    const SPIRVId &result, const std::vector<SPIRVId> &memberTypes) {
  std::vector<std::string> operands;
  operands.reserve(memberTypes.size());
  for (const SPIRVId &memberType : memberTypes) {
    reserveIdReference(memberType);
    operands.push_back(memberType.str());
  }
  defineType(result, "OpTypeStruct", operands);
}

void SPIRVModule::definePointerType(const SPIRVId &result,
                                    SPIRVStorageClass storageClass,
                                    const SPIRVId &pointeeType) {
  reserveIdReference(pointeeType);
  defineType(result, "OpTypePointer",
             {std::string(spirvStorageClassName(storageClass)),
              pointeeType.str()});
}

void SPIRVModule::defineConstant(const SPIRVId &result, const SPIRVId &type,
                                 std::string_view literal) {
  addConstantInstruction(result.str() + " = OpConstant " + type.str() + " " +
                         std::string(literal));
}

void SPIRVModule::defineBoolConstant(const SPIRVId &result, const SPIRVId &type,
                                     bool value) {
  addConstantInstruction(result.str() +
                         (value ? " = OpConstantTrue " : " = OpConstantFalse ") +
                         type.str());
}

void SPIRVModule::defineGlobalVariable(const SPIRVId &result,
                                       const SPIRVId &pointerType,
                                       SPIRVStorageClass storageClass) {
  addGlobalInstruction(result.str() + " = OpVariable " + pointerType.str() +
                       " " + std::string(spirvStorageClassName(storageClass)));
}

std::string SPIRVModule::render(const SPIRVRenderOptions &options) const {
  if (options.validateReferences) {
    validateStructuredReferences();
    validateReferencedIds();
  }

  std::ostringstream out;
  std::size_t lineNumber = 1;
  if (options.emitDisassemblyHeader) {
    out << "; SPIR-V\n";
    ++lineNumber;
    out << "; Version: " << options.version << "\n";
    ++lineNumber;
    if (!options.generator.empty()) {
      out << "; Generator: " << options.generator << "\n";
      ++lineNumber;
    }
    if (options.bound.has_value()) {
      out << "; Bound: " << *options.bound << "\n";
      ++lineNumber;
    }
    if (options.emitSchema) {
      out << "; Schema: 0\n";
      ++lineNumber;
    }
  }

  for (const SPIRVCapabilityDeclaration &capability : capabilities_) {
    appendLine(out, renderCapability(capability), &lineNumber);
  }
  for (const SPIRVExtensionDeclaration &extension : extensions_) {
    appendLine(out, renderExtension(extension), &lineNumber);
  }
  for (const SPIRVExtInstImportDefinition &importDefinition : imports_) {
    appendLine(out, renderExtInstImport(importDefinition), &lineNumber);
  }
  if (memoryModel_.has_value()) {
    appendLine(out, renderMemoryModel(*memoryModel_), &lineNumber);
  }
  for (const SPIRVEntryPointDefinition &entryPoint : entryPoints_) {
    appendLine(out, renderEntryPoint(entryPoint), &lineNumber);
  }
  for (const SPIRVExecutionModeDefinition &executionMode : executionModes_) {
    appendLine(out, renderExecutionMode(executionMode), &lineNumber);
  }
  appendSection(out, names_, &lineNumber);
  appendSection(out, annotations_, &lineNumber);
  appendSection(out, types_, &lineNumber);
  appendSection(out, constants_, &lineNumber);
  appendSection(out, globals_, &lineNumber);
  for (const SPIRVFunctionDefinition &function : functions_) {
    out << function.id.str() << " = OpFunction " << function.returnType.str()
        << " " << function.functionControl << " "
        << function.functionType.str() << "\n";
    ++lineNumber;
    appendSection(out, function.parameterLines, &lineNumber);
    appendLine(out,
               function.entryLabel.empty() ? std::string{}
                                           : function.entryLabel + " = OpLabel",
               &lineNumber);
    appendSection(out, function.variableLines, &lineNumber);
    for (std::size_t instructionIndex = 0;
         instructionIndex < function.instructionLines.size();
         ++instructionIndex) {
      const std::size_t emittedLine = lineNumber;
      if (appendLine(out, function.instructionLines[instructionIndex],
                     &lineNumber) &&
          options.instructionLineMappings != nullptr) {
        options.instructionLineMappings->push_back(
            {function.id.str(), instructionIndex, emittedLine});
      }
    }
    if (!function.hasTerminator && !function.defaultTerminator.empty()) {
      appendLine(out, function.defaultTerminator, &lineNumber);
    }
    appendLine(out, "OpFunctionEnd", &lineNumber);
  }
  return out.str();
}

std::string SPIRVModule::sanitizePrefix(std::string_view prefix) {
  std::string result;
  result.reserve(prefix.size());
  for (const char character : prefix) {
    const bool isAlpha = (character >= 'a' && character <= 'z') ||
                         (character >= 'A' && character <= 'Z');
    const bool isDigit = character >= '0' && character <= '9';
    result.push_back(isAlpha || isDigit ? character : '_');
  }
  if (result.empty()) {
    return "id";
  }
  if (result.front() >= '0' && result.front() <= '9') {
    result.insert(result.begin(), '_');
  }
  return result;
}

SPIRVId SPIRVModule::allocateId(std::string_view prefix,
                                std::size_t &nextIndex) {
  const std::string stem = sanitizePrefix(prefix);
  for (;;) {
    SPIRVId candidate = id(stem + "_" + std::to_string(nextIndex++));
    if (allocatedIds_.insert(candidate.str()).second) {
      return candidate;
    }
  }
}

void SPIRVModule::reserveIdReference(const SPIRVId &id) {
  if (!id.empty()) {
    const std::string text = id.str();
    allocatedIds_.insert(text);
    if (referencedIdSet_.insert(text).second) {
      referencedIds_.push_back(text);
    }
  }
}

void SPIRVModule::reserveDefinedId(const SPIRVId &id,
                                   std::string_view context) {
  reserveDefinedIdText(id.str(), context);
}

void SPIRVModule::reserveDefinedIdText(std::string_view id,
                                       std::string_view context) {
  if (id.empty() || id.front() != '%') {
    throw std::logic_error("SPIR-V " + std::string(context) +
                           " requires a result id");
  }
  const std::string text(id);
  if (!definedIds_.insert(text).second) {
    throw std::logic_error("SPIR-V result id '" + text +
                           "' is defined more than once");
  }
  allocatedIds_.insert(text);
}

void SPIRVModule::reserveDefinedIdFromInstruction(std::string_view line,
                                                  std::string_view context) {
  const std::string resultId = leadingResultId(line);
  if (!resultId.empty()) {
    reserveDefinedIdText(resultId, context);
  }
}

void SPIRVModule::validateStructuredReferences() const {
  for (const SPIRVExecutionModeDefinition &executionMode : executionModes_) {
    const std::string entryPoint = executionMode.entryPoint.str();
    if (entryPointIds_.find(entryPoint) == entryPointIds_.end()) {
      throw std::logic_error("SPIR-V execution mode target '" + entryPoint +
                             "' is not declared by OpEntryPoint");
    }
  }
}

void SPIRVModule::validateReferencedIds() const {
  std::vector<std::string> unresolvedIds;
  for (const std::string &id : referencedIds_) {
    if (definedIds_.find(id) == definedIds_.end()) {
      unresolvedIds.push_back(id);
    }
  }
  if (unresolvedIds.empty()) {
    return;
  }

  std::string message = "SPIR-V module references undefined result id";
  if (unresolvedIds.size() != 1) {
    message += "s";
  }
  message += ": ";
  for (std::size_t index = 0; index < unresolvedIds.size(); ++index) {
    if (index != 0) {
      message += ", ";
    }
    message += unresolvedIds[index];
  }
  throw std::logic_error(message);
}

} // namespace crossgl
