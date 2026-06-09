#pragma once

#include <string>
#include <string_view>

#include "crossgl/Backend/Target.h"
#include "crossgl/HIR/HIR.h"

namespace crossgl {

enum class DumpStage {
  HIR,
  CrossGL,
  PseudoMLIR,
  MLIR = PseudoMLIR,
  Backend,
  BackendSourceMap,
  Debug,
  HIRSourceMap,
  HIRPassTrace,
};

DumpStage dumpStageFromString(std::string_view value);
std::string dumpStageName(DumpStage stage);
bool isLegacyMLIRDumpStageName(std::string_view value);

std::string printHIR(const HIRModule &module);
std::string printCrossGLIR(const HIRModule &module);
std::string printPseudoMLIR(const HIRModule &module);
// Compatibility wrapper that emits pseudo-MLIR, not real MLIR.
std::string printMLIR(const HIRModule &module);
std::string printBackendIR(const HIRModule &module, TargetKind target);

} // namespace crossgl
