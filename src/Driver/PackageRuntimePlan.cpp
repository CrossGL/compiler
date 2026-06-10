#include "crossgl/Driver/PackageRuntimePlan.h"

#include "crossgl/Basic/Json.h"
#include "crossgl/Driver/PackageJson.h"
#include "crossgl/Driver/PackageMetadata.h"
#include "crossgl/Driver/PackageTargetContracts.h"

#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <optional>
#include <ostream>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

namespace crossgl {
namespace {

constexpr std::string_view kNativeBinaryArtifact = "nativeBinary";
constexpr std::string_view kBackendSourceArtifact = "backendSource";

void writeNullableString(std::ostream &out,
                         const std::optional<std::string> &value) {
  if (value) {
    out << "\"" << escapeJson(*value) << "\"";
  } else {
    out << "null";
  }
}

void writeNullableString(std::ostream &out, const std::string *value) {
  if (value != nullptr) {
    out << "\"" << escapeJson(*value) << "\"";
  } else {
    out << "null";
  }
}

void writeStringArray(std::ostream &out,
                      const std::vector<std::string> &values) {
  out << "[";
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << "\"" << escapeJson(values[index]) << "\"";
  }
  out << "]";
}

void writeSourceLocation(std::ostream &out, const SourceLocation &location,
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

void writeDiagnosticRecord(std::ostream &out, const Diagnostic &diagnostic,
                           std::string_view indent) {
  out << indent << "{\n"
      << indent << "  \"severity\": \""
      << escapeJson(toString(diagnostic.severity)) << "\",\n"
      << indent << "  \"code\": \"" << escapeJson(diagnostic.code) << "\",\n"
      << indent << "  \"message\": \"" << escapeJson(diagnostic.message)
      << "\",\n"
      << indent << "  \"location\": ";
  writeSourceLocation(out, diagnostic.location, std::string(indent) + "  ");
  if (!diagnostic.target.empty()) {
    out << ",\n"
        << indent << "  \"target\": \"" << escapeJson(diagnostic.target)
        << "\"";
  }
  if (!diagnostic.missingCapabilities.empty()) {
    out << ",\n" << indent << "  \"missingCapabilities\": ";
    writeStringArray(out, diagnostic.missingCapabilities);
  }
  out << "\n" << indent << "}";
}

void writeDiagnostics(std::ostream &out,
                      const std::vector<Diagnostic> &diagnostics,
                      std::string_view indent) {
  out << "[";
  for (std::size_t index = 0; index < diagnostics.size(); ++index) {
    out << (index == 0 ? "\n" : ",\n");
    writeDiagnosticRecord(out, diagnostics[index], std::string(indent) + "  ");
  }
  if (!diagnostics.empty()) {
    out << "\n" << indent;
  }
  out << "]";
}

std::size_t countDiagnostics(const std::vector<Diagnostic> &diagnostics,
                             DiagnosticSeverity severity) {
  return std::count_if(diagnostics.begin(), diagnostics.end(),
                       [severity](const Diagnostic &diagnostic) {
                         return diagnostic.severity == severity;
                       });
}

const PackageArtifactRecord *
findArtifact(const PackageMetadata &metadata, std::string_view name) {
  for (const PackageArtifactRecord &artifact : metadata.artifacts) {
    if (artifact.name == name) {
      return &artifact;
    }
  }
  return nullptr;
}

bool nativeStatusIsReady(const std::optional<std::string> &status) {
  return status == "emitted" || status == "validated";
}

bool artifactUsable(const PackageArtifactRecord *artifact) {
  return artifact != nullptr && artifact->packageRelative && artifact->exists;
}

bool targetSupportsSourcePackage(const PackageTargetContract &contract) {
  return contract.allowsPlannedNativeBinary ||
         contract.allowsPlannedNativeSourceEvidence;
}

bool nativeArtifactReady(const PackageMetadata &metadata,
                         const PackageTargetContract &contract,
                         const PackageArtifactRecord *nativeArtifact) {
  if (!artifactUsable(nativeArtifact)) {
    return false;
  }
  if (!contract.requiresNativeBinaryStatus) {
    return true;
  }
  return nativeStatusIsReady(effectivePackageNativeBinaryStatus(metadata));
}

std::optional<std::size_t> jsonArraySize(std::string_view object,
                                         std::string_view key) {
  const std::optional<std::string_view> array = findObjectMemberValue(object, key);
  if (!array) {
    return std::nullopt;
  }
  return arrayLength(*array);
}

struct Selection {
  std::optional<std::string> mode;
  const PackageArtifactRecord *artifact = nullptr;
};

Selection selectArtifact(const PackageMetadata &metadata,
                         const PackageTargetContract &contract,
                         RuntimeLoaderPackageMode requestedMode,
                         std::vector<Diagnostic> &diagnostics) {
  const PackageArtifactRecord *nativeArtifact =
      findArtifact(metadata, kNativeBinaryArtifact);
  const PackageArtifactRecord *sourceArtifact =
      findArtifact(metadata, kBackendSourceArtifact);
  const bool nativeReady =
      nativeArtifactReady(metadata, contract, nativeArtifact);
  const bool sourceReady =
      targetSupportsSourcePackage(contract) && artifactUsable(sourceArtifact);

  if (requestedMode == RuntimeLoaderPackageMode::Native) {
    if (!nativeReady) {
      Diagnostic diagnostic;
      diagnostic.severity = DiagnosticSeverity::Error;
      diagnostic.code = "package.runtime-plan.native-artifact-unavailable";
      diagnostic.message =
          "runtime loader plan requires an available nativeBinary artifact";
      diagnostic.target = metadata.target;
      diagnostics.push_back(std::move(diagnostic));
      return {};
    }
    return Selection{"native", nativeArtifact};
  }

  if (requestedMode == RuntimeLoaderPackageMode::SourcePackage) {
    if (!sourceReady) {
      Diagnostic diagnostic;
      diagnostic.severity = DiagnosticSeverity::Error;
      diagnostic.code = "package.runtime-plan.source-artifact-unavailable";
      diagnostic.message =
          "runtime loader plan requires an available backendSource artifact";
      diagnostic.target = metadata.target;
      diagnostics.push_back(std::move(diagnostic));
      return {};
    }
    return Selection{"source-package", sourceArtifact};
  }

  if (nativeReady) {
    return Selection{"native", nativeArtifact};
  }
  if (sourceReady) {
    return Selection{"source-package", sourceArtifact};
  }

  Diagnostic diagnostic;
  diagnostic.severity = DiagnosticSeverity::Error;
  diagnostic.code = "package.runtime-plan.artifact-unavailable";
  diagnostic.message =
      "runtime loader plan could not select a native or source-package artifact";
  diagnostic.target = metadata.target;
  diagnostics.push_back(std::move(diagnostic));
  return {};
}

void writePackageArtifactRequirements(
    std::ostream &out, const PackageArtifactRequirementsRecord &requirements,
    std::string_view indent) {
  out << "{\n"
      << indent << "  \"target\": \"" << escapeJson(requirements.target)
      << "\",\n"
      << indent << "  \"packageMode\": \""
      << escapeJson(requirements.packageMode) << "\",\n"
      << indent << "  \"requiredPathArtifacts\": [";
  for (std::size_t index = 0; index < requirements.requiredPathArtifacts.size();
       ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << "\"" << escapeJson(requirements.requiredPathArtifacts[index].name)
        << "\"";
  }
  out << "],\n"
      << indent << "  \"requiresNativeBinaryStatus\": "
      << (requirements.requiresNativeBinaryStatus ? "true" : "false") << ",\n"
      << indent << "  \"allowsPlannedNativeBinary\": "
      << (requirements.allowsPlannedNativeBinary ? "true" : "false") << ",\n"
      << indent << "  \"allowsPlannedNativeSourceEvidence\": "
      << (requirements.allowsPlannedNativeSourceEvidence ? "true" : "false")
      << ",\n"
      << indent << "  \"evidenceIds\": ";
  writeStringArray(out, requirements.evidenceIds);
  out << "\n" << indent << "}";
}

void writeContractRequirements(std::ostream &out,
                               const PackageTargetContract &contract,
                               std::string_view indent) {
  out << "{\n"
      << indent << "  \"target\": \"" << escapeJson(contract.target)
      << "\",\n"
      << indent << "  \"packageMode\": \""
      << (targetSupportsSourcePackage(contract) ? "source-package" : "native")
      << "\",\n"
      << indent << "  \"requiredPathArtifacts\": [";
  for (std::size_t index = 0; index < contract.requiredArtifactCount; ++index) {
    if (index != 0) {
      out << ", ";
    }
    out << "\"" << escapeJson(contract.requiredArtifacts[index]) << "\"";
  }
  out << "],\n"
      << indent << "  \"requiresNativeBinaryStatus\": "
      << (contract.requiresNativeBinaryStatus ? "true" : "false") << ",\n"
      << indent << "  \"allowsPlannedNativeBinary\": "
      << (contract.allowsPlannedNativeBinary ? "true" : "false") << ",\n"
      << indent << "  \"allowsPlannedNativeSourceEvidence\": "
      << (contract.allowsPlannedNativeSourceEvidence ? "true" : "false")
      << ",\n"
      << indent << "  \"evidenceIds\": []\n"
      << indent << "}";
}

void writeSelectedArtifact(std::ostream &out,
                           const PackageArtifactRecord *artifact,
                           const std::optional<std::string> &mode,
                           std::string_view indent) {
  if (artifact == nullptr || !mode) {
    out << "null";
    return;
  }
  out << "{\n"
      << indent << "  \"name\": \"" << escapeJson(artifact->name) << "\",\n"
      << indent << "  \"path\": \"" << escapeJson(artifact->path) << "\",\n"
      << indent << "  \"packageMode\": \"" << escapeJson(*mode) << "\",\n"
      << indent << "  \"packageRelative\": "
      << (artifact->packageRelative ? "true" : "false") << ",\n"
      << indent << "  \"exists\": " << (artifact->exists ? "true" : "false")
      << "\n"
      << indent << "}";
}

void writeTargetLegalizationEvidenceSummary(std::ostream &out,
                                            const PackageMetadata &metadata,
                                            std::string_view indent) {
  out << "{\n"
      << indent << "  \"toolRequirementsPresent\": "
      << (metadata.targetLegalizationToolRequirements ? "true" : "false")
      << ",\n"
      << indent << "  \"target\": ";
  if (metadata.targetLegalizationToolRequirements) {
    out << "\""
        << escapeJson(metadata.targetLegalizationToolRequirements->target)
        << "\"";
  } else {
    out << "null";
  }
  out << ",\n" << indent << "  \"packageMode\": ";
  if (metadata.targetLegalizationToolRequirements) {
    out << "\""
        << escapeJson(metadata.targetLegalizationToolRequirements->packageMode)
        << "\"";
  } else {
    out << "null";
  }
  out << ",\n" << indent << "  \"requiredToolCount\": "
      << (metadata.targetLegalizationToolRequirements
              ? metadata.targetLegalizationToolRequirements->requiredToolCount
              : 0)
      << ",\n"
      << indent << "  \"missingToolCount\": "
      << (metadata.targetLegalizationToolRequirements
              ? metadata.targetLegalizationToolRequirements->missingToolCount
              : 0)
      << ",\n"
      << indent << "  \"requiredToolIds\": ";
  if (metadata.targetLegalizationToolRequirements) {
    writeStringArray(
        out, metadata.targetLegalizationToolRequirements->requiredToolIds);
  } else {
    out << "[]";
  }
  out << ",\n" << indent << "  \"missingToolIds\": ";
  if (metadata.targetLegalizationToolRequirements) {
    writeStringArray(out,
                     metadata.targetLegalizationToolRequirements->missingToolIds);
  } else {
    out << "[]";
  }
  out << ",\n" << indent << "  \"toolRequirementEvidenceIds\": ";
  if (metadata.targetLegalizationToolRequirements) {
    writeStringArray(
        out,
        metadata.targetLegalizationToolRequirements->toolRequirementEvidenceIds);
  } else {
    out << "[]";
  }
  out << "\n" << indent << "}";
}

std::size_t selectedTargetBindingCount(const PackageMetadata &metadata) {
  return std::count_if(metadata.reflectionTargetResourceBindings.begin(),
                       metadata.reflectionTargetResourceBindings.end(),
                       [&](const PackageReflectionTargetResourceBindingRecord
                               &binding) {
                         return binding.target == metadata.target;
                       });
}

std::size_t selectedTargetFeatureCount(const PackageMetadata &metadata) {
  return std::count_if(
      metadata.reflectionTargetFeatures.begin(),
      metadata.reflectionTargetFeatures.end(),
      [&](const PackageReflectionTargetFeatureRecord &feature) {
        return feature.target == metadata.target;
      });
}

void writeReflectionSummary(std::ostream &out, const PackageMetadata &metadata,
                            std::string_view indent) {
  const std::optional<std::size_t> workgroupSizeCount =
      jsonArraySize(metadata.documents.reflection, "workgroupSizes");
  const std::optional<std::size_t> entryPointCount =
      jsonArraySize(metadata.documents.reflection, "entryPoints");
  out << "{\n"
      << indent << "  \"resourceCount\": "
      << metadata.reflectionResources.size() << ",\n"
      << indent << "  \"targetResourceBindingCount\": "
      << selectedTargetBindingCount(metadata) << ",\n"
      << indent << "  \"targetFeatureCount\": "
      << selectedTargetFeatureCount(metadata) << ",\n"
      << indent << "  \"entryPointCount\": ";
  if (entryPointCount) {
    out << *entryPointCount;
  } else {
    out << "null";
  }
  out << ",\n" << indent << "  \"workgroupSizeCount\": ";
  if (workgroupSizeCount) {
    out << *workgroupSizeCount;
  } else {
    out << "null";
  }
  out << ",\n"
      << indent << "  \"threadgroupShapeSource\": \"reflection.workgroupSizes\""
      << "\n"
      << indent << "}";
}

void writePlanJson(std::ostream &out, const PackageRuntimePlanOptions &options,
                   const PackageMetadata *metadata,
                   const PackageTargetContract *contract,
                   const std::optional<std::string> &packageFormat,
                   const Selection &selection,
                   const std::vector<Diagnostic> &diagnostics,
                   bool success) {
  const std::string *packageTarget = metadata ? &metadata->target : nullptr;
  const std::string *requestedLoaderTarget =
      isKnownPackageTarget(options.requestedTarget) ? &options.requestedTarget
                                                   : nullptr;
  const bool targetMatchesPackage =
      metadata != nullptr && metadata->target == options.requestedTarget;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"kind\": \"crossgl-runtime-loader-plan\",\n"
      << "  \"success\": " << (success ? "true" : "false") << ",\n"
      << "  \"metadataOnly\": true,\n"
      << "  \"compilerInvocationRequired\": false,\n"
      << "  \"deviceExecutionRequired\": false,\n"
      << "  \"packageFormat\": ";
  writeNullableString(out, packageFormat);
  out << ",\n"
      << "  \"packageTarget\": ";
  writeNullableString(out, packageTarget);
  out << ",\n"
      << "  \"requestedLoaderTarget\": ";
  writeNullableString(out, requestedLoaderTarget);
  out << ",\n"
      << "  \"targetMatchesPackage\": "
      << (targetMatchesPackage ? "true" : "false") << ",\n"
      << "  \"requestedPackageMode\": \""
      << escapeJson(toString(options.packageMode)) << "\",\n"
      << "  \"selectedPackageMode\": ";
  writeNullableString(out, selection.mode);
  out << ",\n"
      << "  \"selectedArtifact\": ";
  writeSelectedArtifact(out, selection.artifact, selection.mode, "  ");
  out << ",\n"
      << "  \"requiredMetadataInputs\": [\"manifest.json\", "
         "\"reflection.json\", \"diagnostics.json\"],\n"
      << "  \"packageArtifactRequirementsSource\": ";
  if (metadata && metadata->artifactRequirements) {
    out << "\"manifest.packageArtifactRequirements\"";
  } else if (contract) {
    out << "\"generated-package-target-contract\"";
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"packageArtifactRequirements\": ";
  if (metadata && metadata->artifactRequirements) {
    writePackageArtifactRequirements(out, *metadata->artifactRequirements, "  ");
  } else if (contract) {
    writeContractRequirements(out, *contract, "  ");
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"targetLegalizationEvidenceSummary\": ";
  if (metadata) {
    writeTargetLegalizationEvidenceSummary(out, *metadata, "  ");
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"reflectionSummary\": ";
  if (metadata) {
    writeReflectionSummary(out, *metadata, "  ");
  } else {
    out << "null";
  }
  out << ",\n"
      << "  \"diagnosticCounts\": {\n"
      << "    \"note\": " << countDiagnostics(diagnostics, DiagnosticSeverity::Note)
      << ",\n"
      << "    \"warning\": "
      << countDiagnostics(diagnostics, DiagnosticSeverity::Warning) << ",\n"
      << "    \"error\": "
      << countDiagnostics(diagnostics, DiagnosticSeverity::Error) << "\n"
      << "  },\n"
      << "  \"diagnostics\": ";
  writeDiagnostics(out, diagnostics, "  ");
  out << "\n}\n";
}

} // namespace

std::string toString(RuntimeLoaderPackageMode mode) {
  switch (mode) {
  case RuntimeLoaderPackageMode::Auto:
    return "auto";
  case RuntimeLoaderPackageMode::Native:
    return "native";
  case RuntimeLoaderPackageMode::SourcePackage:
    return "source-package";
  }
  return "auto";
}

bool parseRuntimeLoaderPackageMode(std::string_view text,
                                   RuntimeLoaderPackageMode &mode) {
  if (text == "auto") {
    mode = RuntimeLoaderPackageMode::Auto;
    return true;
  }
  if (text == "native") {
    mode = RuntimeLoaderPackageMode::Native;
    return true;
  }
  if (text == "source-package" || text == "source") {
    mode = RuntimeLoaderPackageMode::SourcePackage;
    return true;
  }
  return false;
}

PackageRuntimePlanResult
planPackageRuntimeLoader(const PackageRuntimePlanOptions &options) {
  DiagnosticEngine diagnostics;
  std::optional<std::string> packageFormat =
      detectPackageMetadataFormat(options.packagePath);
  PackageMetadataLoadOptions metadataOptions;
  metadataOptions.diagnosticCodePrefix = "package.runtime-plan";
  metadataOptions.commandName = "package plan-runtime";
  metadataOptions.allowStoredZipPackages = true;
  std::optional<PackageMetadata> metadata =
      loadPackageMetadata(options.packagePath, diagnostics, metadataOptions);

  std::vector<Diagnostic> allDiagnostics = diagnostics.diagnostics();
  const PackageTargetContract *contract = nullptr;
  Selection selection;

  if (metadata) {
    contract = packageTargetContractFor(metadata->target);
    if (options.requestedTarget.empty()) {
      Diagnostic diagnostic;
      diagnostic.severity = DiagnosticSeverity::Error;
      diagnostic.code = "package.runtime-plan.missing-target";
      diagnostic.message = "runtime loader plan requires --target";
      allDiagnostics.push_back(std::move(diagnostic));
    } else if (!isKnownPackageTarget(options.requestedTarget)) {
      Diagnostic diagnostic;
      diagnostic.severity = DiagnosticSeverity::Error;
      diagnostic.code = "package.runtime-plan.unknown-target";
      diagnostic.message =
          "runtime loader plan requested an unknown loader target";
      diagnostic.target = options.requestedTarget;
      allDiagnostics.push_back(std::move(diagnostic));
    } else if (metadata->target != options.requestedTarget) {
      Diagnostic diagnostic;
      diagnostic.severity = DiagnosticSeverity::Error;
      diagnostic.code = "package.runtime-plan.target-mismatch";
      diagnostic.message = "package target does not match requested loader target";
      diagnostic.target = metadata->target;
      allDiagnostics.push_back(std::move(diagnostic));
    } else if (contract == nullptr) {
      Diagnostic diagnostic;
      diagnostic.severity = DiagnosticSeverity::Error;
      diagnostic.code = "package.runtime-plan.unsupported-target";
      diagnostic.message =
          "runtime loader plan has no package target contract for target";
      diagnostic.target = metadata->target;
      allDiagnostics.push_back(std::move(diagnostic));
    } else {
      selection =
          selectArtifact(*metadata, *contract, options.packageMode, allDiagnostics);
    }
  }

  const bool success =
      metadata.has_value() && selection.artifact != nullptr &&
      countDiagnostics(allDiagnostics, DiagnosticSeverity::Error) == 0;

  std::ostringstream json;
  writePlanJson(json, options, metadata ? &*metadata : nullptr, contract,
                packageFormat, selection, allDiagnostics, success);
  return PackageRuntimePlanResult{success, json.str(), std::move(allDiagnostics)};
}

} // namespace crossgl
