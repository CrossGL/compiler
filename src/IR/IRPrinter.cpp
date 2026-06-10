#include "crossgl/IR/IRPrinter.h"

#include "crossgl/Backend/DirectXBackend.h"
#include "crossgl/Backend/MetalBackend.h"
#include "crossgl/Backend/OpenGLBackend.h"
#include "crossgl/Backend/VulkanBackend.h"
#include "crossgl/Frontend/TokenText.h"

#include <optional>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace crossgl {
namespace {

std::string formatHIRExpression(const HIRExpression &expression) {
  switch (expression.kind) {
  case HIRExpressionKind::Empty:
    return "";
  case HIRExpressionKind::Identifier:
  case HIRExpressionKind::Literal:
    return expression.value;
  case HIRExpressionKind::Group:
    return expression.children.empty() ? "()"
                                       : "(" + formatHIRExpression(expression.children[0]) + ")";
  case HIRExpressionKind::MemberAccess:
    return expression.children.empty()
               ? expression.value
               : formatHIRExpression(expression.children[0]) + "." + expression.value;
  case HIRExpressionKind::IndexAccess:
    if (expression.children.size() < 2) {
      return "";
    }
    return formatHIRExpression(expression.children[0]) + "[" +
           formatHIRExpression(expression.children[1]) + "]";
  case HIRExpressionKind::NonUniform:
    return expression.children.empty()
               ? "nonuniform()"
               : "nonuniform(" + formatHIRExpression(expression.children[0]) + ")";
  case HIRExpressionKind::Call:
  case HIRExpressionKind::Constructor: {
    std::ostringstream out;
    out << (expression.value == "textureCompareKernel"
                ? "texture_compare_kernel"
                : expression.value)
        << "(";
    for (std::size_t i = 0; i < expression.children.size(); ++i) {
      if (i != 0) {
        out << ", ";
      }
      out << formatHIRExpression(expression.children[i]);
    }
    out << ")";
    return out.str();
  }
  case HIRExpressionKind::Unary:
    return expression.value +
           (expression.children.empty() ? "" : formatHIRExpression(expression.children[0]));
  case HIRExpressionKind::Binary:
    if (expression.children.size() < 2) {
      return expression.value;
    }
    return formatHIRExpression(expression.children[0]) + " " + expression.value + " " +
           formatHIRExpression(expression.children[1]);
  case HIRExpressionKind::Select:
    if (expression.children.size() < 3) {
      return "";
    }
    return formatHIRExpression(expression.children[0]) + " ? " +
           formatHIRExpression(expression.children[1]) + " : " +
           formatHIRExpression(expression.children[2]);
  case HIRExpressionKind::TextureSample: {
    std::ostringstream out;
    out << (expression.value == "textureLod" ? "texture_sample_lod("
                                              : "texture_sample(");
    for (std::size_t i = 0; i < expression.children.size(); ++i) {
      if (i != 0) {
        out << ", ";
      }
      out << formatHIRExpression(expression.children[i]);
    }
    out << ")";
    return out.str();
  }
  case HIRExpressionKind::TextureCompare: {
    std::ostringstream out;
    out << (expression.value == "textureCompareLod" ? "texture_compare_lod("
                                                     : "texture_compare(");
    for (std::size_t i = 0; i < expression.children.size(); ++i) {
      if (i != 0) {
        out << ", ";
      }
      out << formatHIRExpression(expression.children[i]);
    }
    out << ")";
    return out.str();
  }
  case HIRExpressionKind::TextureCompareLodManual: {
    if (const std::optional<std::vector<ManualTextureCompareKernelTap>> taps =
            manualTextureCompareKernelTaps(expression);
        taps.has_value() &&
        (expression.value == "textureCompareLodManualKernel4" ||
         expression.value == "textureCompareLodManualKernel8")) {
      std::ostringstream out;
      out << "texture_compare_lod_manual_kernel(";
      for (std::size_t i = 0; i < 6; ++i) {
        if (i != 0) {
          out << ", ";
        }
        out << formatHIRExpression(expression.children[i]);
      }
      out << ", texture_compare_kernel(";
      for (std::size_t i = 0; i < taps->size(); ++i) {
        if (i != 0) {
          out << ", ";
        }
        out << formatHIRExpression(*(*taps)[i].offset) << ", "
            << formatHIRExpression(*(*taps)[i].weight);
      }
      out << "))";
      return out.str();
    }

    std::ostringstream out;
    if (expression.value == "textureCompareLodManualOffset") {
      out << "texture_compare_lod_manual_offset(";
    } else if (expression.value == "textureCompareLodManualGather2x2") {
      out << "texture_compare_lod_manual_gather_2x2(";
    } else if (expression.value == "textureCompareLodManualKernel") {
      out << "texture_compare_lod_manual_kernel(";
    } else if (expression.value == "textureCompareLodManualKernel4") {
      out << "texture_compare_lod_manual_kernel_4(";
    } else if (expression.value == "textureCompareLodManualKernel8") {
      out << "texture_compare_lod_manual_kernel_8(";
    } else {
      out << "texture_compare_lod_manual(";
    }
    for (std::size_t i = 0; i < expression.children.size(); ++i) {
      if (i != 0) {
        out << ", ";
      }
      out << formatHIRExpression(expression.children[i]);
    }
    out << ")";
    return out.str();
  }
  }
  return "";
}

std::string expressionTypeSuffix(const HIRExpression &expression) {
  if (expression.type.name.empty()) {
    return "";
  }
  return " : " + formatType(expression.type);
}

std::string indent(std::size_t spaces) { return std::string(spaces, ' '); }

void printHIRStatement(std::ostringstream &out, const HIRStatement &statement,
                       std::size_t indentation) {
  out << indent(indentation) << statementKindName(statement.kind);
  const bool hasStatementOperand =
      !(statement.kind == HIRStatementKind::Return &&
        statement.value.kind == HIRExpressionKind::Empty) &&
      statement.kind != HIRStatementKind::Block &&
      statement.kind != HIRStatementKind::Break &&
      statement.kind != HIRStatementKind::Continue &&
      statement.kind != HIRStatementKind::Discard;
  if (hasStatementOperand) {
    out << " ";
  }

  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    out << formatType(statement.declaredType) << " " << statement.name;
    if (statement.value.kind != HIRExpressionKind::Empty) {
      out << " = " << formatHIRExpression(statement.value)
          << expressionTypeSuffix(statement.value);
    }
    out << "\n";
    break;
  case HIRStatementKind::Assignment:
    out << formatHIRExpression(statement.target) << expressionTypeSuffix(statement.target)
        << " = " << formatHIRExpression(statement.value)
        << expressionTypeSuffix(statement.value) << "\n";
    break;
  case HIRStatementKind::Return:
    if (statement.value.kind != HIRExpressionKind::Empty) {
      out << formatHIRExpression(statement.value)
          << expressionTypeSuffix(statement.value);
    }
    out << "\n";
    break;
  case HIRStatementKind::Expression:
    out << formatHIRExpression(statement.value)
        << expressionTypeSuffix(statement.value) << "\n";
    break;
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
    out << "\n";
    break;
  case HIRStatementKind::Block:
    out << "\n";
    for (const HIRStatement &child : statement.body) {
      printHIRStatement(out, child, indentation + 2);
    }
    break;
  case HIRStatementKind::If:
    out << formatHIRExpression(statement.value)
        << expressionTypeSuffix(statement.value) << "\n";
    for (const HIRStatement &child : statement.body) {
      printHIRStatement(out, child, indentation + 2);
    }
    if (!statement.elseBody.empty()) {
      out << indent(indentation) << "else\n";
      for (const HIRStatement &child : statement.elseBody) {
        printHIRStatement(out, child, indentation + 2);
      }
    }
    break;
  case HIRStatementKind::For:
    out << formatHIRExpression(statement.value)
        << expressionTypeSuffix(statement.value);
    if (!statement.updateTokens.empty()) {
      out << " update " << tokensToText(statement.updateTokens);
    }
    out << "\n";
    for (const HIRStatement &initializer : statement.initializer) {
      out << indent(indentation + 2) << "init ";
      printHIRStatement(out, initializer, 0);
    }
    for (const HIRStatement &update : statement.update) {
      out << indent(indentation + 2) << "update ";
      printHIRStatement(out, update, 0);
    }
    for (const HIRStatement &child : statement.body) {
      printHIRStatement(out, child, indentation + 2);
    }
    break;
  case HIRStatementKind::Raw:
    out << tokensToText(statement.rawTokens) << "\n";
    break;
  }
}

void printCrossGLStatement(std::ostringstream &out, const HIRStatement &statement,
                           std::size_t indentation) {
  out << indent(indentation) << "crossgl." << statementKindName(statement.kind);
  switch (statement.kind) {
  case HIRStatementKind::Declaration:
    out << " %" << statement.name << " : " << typeToIR(statement.declaredType);
    if (statement.value.kind != HIRExpressionKind::Empty) {
      out << " = \"" << formatHIRExpression(statement.value) << "\"";
    }
    out << "\n";
    break;
  case HIRStatementKind::Assignment:
    out << " \"" << formatHIRExpression(statement.target) << "\" = \""
        << formatHIRExpression(statement.value) << "\"\n";
    break;
  case HIRStatementKind::Return:
    if (statement.value.kind != HIRExpressionKind::Empty) {
      out << " \"" << formatHIRExpression(statement.value) << "\"";
    }
    out << "\n";
    break;
  case HIRStatementKind::Expression:
    out << " \"" << formatHIRExpression(statement.value) << "\"\n";
    break;
  case HIRStatementKind::Break:
  case HIRStatementKind::Continue:
  case HIRStatementKind::Discard:
    out << "\n";
    break;
  case HIRStatementKind::Block:
    out << " {\n";
    for (const HIRStatement &child : statement.body) {
      printCrossGLStatement(out, child, indentation + 2);
    }
    out << indent(indentation) << "}\n";
    break;
  case HIRStatementKind::If:
    out << " condition \"" << formatHIRExpression(statement.value) << "\" {\n";
    for (const HIRStatement &child : statement.body) {
      printCrossGLStatement(out, child, indentation + 2);
    }
    if (!statement.elseBody.empty()) {
      out << indent(indentation) << "} else {\n";
      for (const HIRStatement &child : statement.elseBody) {
        printCrossGLStatement(out, child, indentation + 2);
      }
    }
    out << indent(indentation) << "}\n";
    break;
  case HIRStatementKind::For:
    out << " condition \"" << formatHIRExpression(statement.value) << "\"";
    if (!statement.updateTokens.empty()) {
      out << " update \"" << tokensToText(statement.updateTokens) << "\"";
    }
    out << " {\n";
    for (const HIRStatement &initializer : statement.initializer) {
      out << indent(indentation + 2) << "crossgl.for_init {\n";
      printCrossGLStatement(out, initializer, indentation + 4);
      out << indent(indentation + 2) << "}\n";
    }
    for (const HIRStatement &update : statement.update) {
      out << indent(indentation + 2) << "crossgl.for_update {\n";
      printCrossGLStatement(out, update, indentation + 4);
      out << indent(indentation + 2) << "}\n";
    }
    for (const HIRStatement &child : statement.body) {
      printCrossGLStatement(out, child, indentation + 2);
    }
    out << indent(indentation) << "}\n";
    break;
  case HIRStatementKind::Raw:
    out << " \"" << tokensToText(statement.rawTokens) << "\"\n";
    break;
  }
}

} // namespace

DumpStage dumpStageFromString(std::string_view value) {
  if (value == "hir") {
    return DumpStage::HIR;
  }
  if (value == "crossgl") {
    return DumpStage::CrossGL;
  }
  if (value == "pseudo-mlir" || isLegacyMLIRDumpStageName(value)) {
    return DumpStage::PseudoMLIR;
  }
  if (value == "backend") {
    return DumpStage::Backend;
  }
  if (value == "backend-source-map") {
    return DumpStage::BackendSourceMap;
  }
  if (value == "debug") {
    return DumpStage::Debug;
  }
  if (value == "hir-source-map" || value == "source-map") {
    return DumpStage::HIRSourceMap;
  }
  if (value == "hir-pass-trace" || value == "pass-trace") {
    return DumpStage::HIRPassTrace;
  }
  throw std::invalid_argument(
      "unknown dump stage; expected hir, crossgl, pseudo-mlir, backend, "
      "backend-source-map, debug, hir-source-map, or hir-pass-trace "
      "(legacy alias: mlir)");
}

std::string dumpStageName(DumpStage stage) {
  switch (stage) {
  case DumpStage::HIR:
    return "hir";
  case DumpStage::CrossGL:
    return "crossgl";
  case DumpStage::PseudoMLIR:
    return "pseudo-mlir";
  case DumpStage::Backend:
    return "backend";
  case DumpStage::BackendSourceMap:
    return "backend-source-map";
  case DumpStage::Debug:
    return "debug";
  case DumpStage::HIRSourceMap:
    return "hir-source-map";
  case DumpStage::HIRPassTrace:
    return "hir-pass-trace";
  }
  return "unknown";
}

bool isLegacyMLIRDumpStageName(std::string_view value) {
  return value == "mlir";
}

std::string printHIR(const HIRModule &module) {
  std::ostringstream out;
  out << "module " << module.name << "\n";
  for (const HIRStruct &structure : module.structs) {
    out << "  struct " << structure.name << "\n";
    for (const HIRField &field : structure.fields) {
      out << "    " << formatType(field.type) << " " << field.name << "\n";
    }
  }
  for (const HIRConstant &constant : module.constants) {
    out << "  const " << formatType(constant.type) << " " << constant.name
        << " = " << formatHIRExpression(constant.value);
    if (constant.foldedValue.has_value()) {
      out << " folded " << *constant.foldedValue;
    }
    if (constant.specializationId.has_value()) {
      out << " specialization_id " << *constant.specializationId;
    }
    out << "\n";
  }
  for (const HIRStage &stage : module.stages) {
    out << "  stage " << stage.stage << " entry " << stage.entryPointName << "\n";
    if (stage.workgroupSize.has_value()) {
      out << "    workgroup_size " << stage.workgroupSize->x << ", "
          << stage.workgroupSize->y << ", " << stage.workgroupSize->z;
      if (stage.workgroupSize->x != stage.workgroupSize->sourceX ||
          stage.workgroupSize->y != stage.workgroupSize->sourceY ||
          stage.workgroupSize->z != stage.workgroupSize->sourceZ) {
        out << " source " << stage.workgroupSize->sourceX << ", "
            << stage.workgroupSize->sourceY << ", "
            << stage.workgroupSize->sourceZ;
      }
      out << "\n";
    }
    for (const HIRResource &resource : stage.resources) {
      out << "    resource " << resourceKindName(resource.kind) << " "
          << formatType(resource.type) << " " << resource.name;
      if (resource.kind == HIRResourceKind::StorageImage) {
        out << " access "
            << storageImageAccessName(resource.storageImageAccess)
            << " format " << resolvedStorageImageFormatName(resource);
      }
      if (resource.kind == HIRResourceKind::Shared) {
        out << " local\n";
      } else {
        out << " set " << resource.set << " binding " << resource.binding << "\n";
      }
    }
    for (const HIRFunction &function : stage.functions) {
      out << "    fn " << function.name << "(";
      for (std::size_t i = 0; i < function.parameters.size(); ++i) {
        if (i != 0) {
          out << ", ";
        }
        out << formatType(function.parameters[i].type) << " "
            << function.parameters[i].name;
      }
      out << ") -> " << formatType(function.returnType) << "\n";
      for (const HIRStatement &statement : function.body) {
        printHIRStatement(out, statement, 6);
      }
    }
  }
  return out.str();
}

std::string printCrossGLIR(const HIRModule &module) {
  std::ostringstream out;
  out << "// CrossGL textual IR: debug projection, not a registered MLIR "
         "dialect.\n";
  out << "// This .mlir sidecar is production debug evidence only; real MLIR "
         "remains gated by CROSSGL_ENABLE_MLIR_EXPERIMENTAL.\n";
  out << "// crossgl.ir_kind = \"crossgl-debug\"; crossgl.real_mlir = "
         "\"false\"\n";
  out << "crossgl.module @" << module.name << " {\n";
  for (const HIRStruct &structure : module.structs) {
    out << "  crossgl.struct @" << structure.name << " {\n";
    for (const HIRField &field : structure.fields) {
      out << "    %" << field.name << " : " << typeToIR(field.type) << "\n";
    }
    out << "  }\n";
  }
  for (const HIRConstant &constant : module.constants) {
    out << "  crossgl.constant @" << constant.name << " : "
        << typeToIR(constant.type) << " = \""
        << formatHIRExpression(constant.value) << "\"";
    if (constant.foldedValue.has_value()) {
      out << " attributes {folded = \"" << *constant.foldedValue << "\"}";
    }
    out << "\n";
  }
  for (const HIRStage &stage : module.stages) {
    out << "  crossgl.stage @" << stage.stage << " attributes {entry = \""
        << stage.entryPointName << "\"";
    if (stage.workgroupSize.has_value()) {
      out << ", workgroup_size = [\"" << stage.workgroupSize->x << "\", \""
          << stage.workgroupSize->y << "\", \"" << stage.workgroupSize->z
          << "\"]";
      if (stage.workgroupSize->x != stage.workgroupSize->sourceX ||
          stage.workgroupSize->y != stage.workgroupSize->sourceY ||
          stage.workgroupSize->z != stage.workgroupSize->sourceZ) {
        out << ", workgroup_source = [\"" << stage.workgroupSize->sourceX
            << "\", \"" << stage.workgroupSize->sourceY << "\", \""
            << stage.workgroupSize->sourceZ << "\"]";
      }
    }
    out << "} {\n";
    for (const HIRResource &resource : stage.resources) {
      out << "    crossgl.resource @" << resource.name << " : "
          << typeToIR(resource.type) << " attributes {kind = \""
          << resourceKindName(resource.kind) << "\"";
      if (resource.kind == HIRResourceKind::StorageImage) {
        out << ", access = \""
            << storageImageAccessName(resource.storageImageAccess)
            << "\", format = \"" << resolvedStorageImageFormatName(resource)
            << "\"";
      }
      if (resource.kind == HIRResourceKind::Shared) {
        out << ", address_space = \"shared\"";
      } else {
        out << ", set = " << resource.set << ", binding = " << resource.binding;
      }
      out << "}\n";
    }
    for (const HIRFunction &function : stage.functions) {
      out << "    crossgl.func @" << function.name << "(";
      for (std::size_t i = 0; i < function.parameters.size(); ++i) {
        if (i != 0) {
          out << ", ";
        }
        out << "%" << function.parameters[i].name << ": "
            << typeToIR(function.parameters[i].type);
      }
      out << ") -> " << typeToIR(function.returnType) << " {\n";
      for (const HIRStatement &statement : function.body) {
        printCrossGLStatement(out, statement, 6);
      }
      out << "    }\n";
    }
    out << "  }\n";
  }
  out << "}\n";
  return out.str();
}

std::string printPseudoMLIR(const HIRModule &module) {
  std::ostringstream out;
  out << "// CrossGL pseudo-MLIR: textual HIR projection, not a registered "
         "MLIR dialect.\n";
  out << "// This dump is for debugging only; no CrossGL MLIR dialect is "
         "registered, and this is not verifier-ready real MLIR.\n";
  out << "// Canonical stage: dump-ir --stage pseudo-mlir; legacy --stage "
         "mlir maps here until real MLIR is enabled experimentally.\n";
  out << "module @" << module.name << " attributes {crossgl.version = \""
      << CROSSGL_VERSION
      << "\", crossgl.ir_kind = \"pseudo-mlir\", crossgl.real_mlir = "
         "\"false\"} {\n";
  for (const HIRStruct &structure : module.structs) {
    out << "  // crossgl.struct @" << structure.name << "\n";
  }
  for (const HIRStage &stage : module.stages) {
    for (const HIRFunction &function : stage.functions) {
      out << "  func.func @" << stage.stage << "_" << function.name << "(";
      for (std::size_t i = 0; i < function.parameters.size(); ++i) {
        if (i != 0) {
          out << ", ";
        }
        out << "%" << function.parameters[i].name << ": "
            << typeToIR(function.parameters[i].type);
      }
      out << ") attributes {crossgl.stage = \"" << stage.stage << "\"}";
      if (function.returnType.name != "void") {
        out << " -> " << typeToIR(function.returnType);
      }
      out << "\n";
    }
  }
  out << "}\n";
  return out.str();
}

std::string printMLIR(const HIRModule &module) {
  return printPseudoMLIR(module);
}

std::string printBackendIR(const HIRModule &module, TargetKind target) {
  if (target == TargetKind::Auto) {
    target = defaultTargetForHost();
  }
  if (target == TargetKind::Metal) {
    return generateMetalSource(module);
  }
  if (target == TargetKind::Vulkan) {
    std::ostringstream out;
    out << generateVulkanBackendIR(module);
    out << printCrossGLIR(module);
    return out.str();
  }
  if (target == TargetKind::DirectX) {
    std::ostringstream out;
    out << generateDirectXBackendIR(module);
    out << printCrossGLIR(module);
    return out.str();
  }
  if (target == TargetKind::OpenGL) {
    std::ostringstream out;
    out << generateOpenGLBackendIR(module);
    out << printCrossGLIR(module);
    return out.str();
  }
  std::ostringstream out;
  out << "; backend lowering for " << targetName(target)
      << " is reserved by the compiler architecture but not implemented in this "
         "iteration\n";
  out << printCrossGLIR(module);
  return out.str();
}

} // namespace crossgl
