#include "crossgl/Driver/LanguageFeatureReport.h"

#include "crossgl/Backend/TargetCapabilities.h"
#include "crossgl/Backend/TargetLegalization.h"
#include "crossgl/Basic/Json.h"
#include "crossgl/Basic/SHA256.h"
#include "crossgl/Driver/CompilerPipeline.h"
#include "crossgl/Driver/PackageJson.h"
#include "crossgl/HIR/HIR.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <string_view>
#include <system_error>
#include <tuple>
#include <utility>
#include <vector>

namespace crossgl {
namespace {

constexpr std::string_view kReportKind = "crossgl.languageFeatureReport";
constexpr std::string_view kSnapshotId =
    "crosstl-frontend-language-spec-v0";
constexpr std::string_view kSnapshotPath =
    "docs/language/crosstl-frontend-language-spec-v0.json";
constexpr std::string_view kCompatibilityPath =
    "tools/cross_repo_language_contract.json";
constexpr std::string_view kSpecIndexPath =
    "docs/language/crosstl-frontend-language-spec-v0.json";
constexpr std::string_view kSupportContractPath =
    "tools/cross_repo_language_contract.json";
constexpr std::string_view kTargetCapabilityRegistryPath =
    "docs/target-capability-registry-v1.json";

constexpr std::string_view kCrossTLInventoryOnly = "cross-tl-inventory-only";

constexpr std::array<std::string_view, 8> kCompatibilityBuckets = {
    kCrossTLInventoryOnly,
    "accepted-source",
    "package-supported",
    "compatibility-only",
    "spec.unsupported-for-native-v0",
    "spec.deprecated",
    "spec.error",
    "target.unsupported",
};

struct StageEntryPoint {
  std::string stage;
  std::string entryPoint;
};

struct FeatureRecord {
  std::string featureId;
  std::string status;
  std::vector<SourceLocation> sourceLocations;
  std::vector<std::string> evidenceIds;
};

struct FeatureRecordGroups {
  std::vector<FeatureRecord> resources;
  std::vector<FeatureRecord> memory;
  std::vector<FeatureRecord> layout;
};

struct TargetGateRecord {
  std::string target;
  std::string targetVersion;
  std::string packageMode;
  std::string gateId;
  std::string featureFamily;
  std::string status;
  std::vector<std::string> requiredCapabilities;
  std::vector<std::string> diagnosticCodes;
  std::vector<std::string> evidenceIds;
};

struct FactRecord {
  std::string factId;
  std::string classification;
  std::string message;
  std::vector<std::string> evidenceIds;
};

struct EvidenceRecord {
  std::string id;
  std::string kind;
  std::optional<std::string> path;
  std::optional<std::string> anchor;
  std::optional<std::string> ctestName;
  std::optional<std::string> fixture;
  std::optional<std::string> diagnosticCode;
  std::optional<std::string> schemaPath;
};

std::string normalizeText(std::string_view text) {
  std::string normalized;
  normalized.reserve(text.size());
  for (std::size_t index = 0; index < text.size(); ++index) {
    if (text[index] == '\r') {
      if (index + 1 < text.size() && text[index + 1] == '\n') {
        ++index;
      }
      normalized.push_back('\n');
      continue;
    }
    normalized.push_back(text[index]);
  }
  return normalized;
}

std::optional<std::string> readTextFile(const std::filesystem::path &path,
                                        DiagnosticEngine &diagnostics,
                                        std::string_view code) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    diagnostics.error(std::string(code), "failed to read '" + path.string() +
                                             "'");
    return std::nullopt;
  }

  std::ostringstream buffer;
  buffer << input.rdbuf();
  if (input.bad()) {
    diagnostics.error(std::string(code), "failed to read '" + path.string() +
                                             "'");
    return std::nullopt;
  }
  return buffer.str();
}

bool hasSnapshot(const std::filesystem::path &root) {
  std::error_code error;
  return std::filesystem::is_regular_file(root / kSnapshotPath, error);
}

std::filesystem::path absoluteNormalized(const std::filesystem::path &path) {
  std::error_code error;
  std::filesystem::path absolute = std::filesystem::absolute(path, error);
  if (error) {
    absolute = path;
  }
  return absolute.lexically_normal();
}

std::optional<std::filesystem::path>
findRepositoryRoot(const std::filesystem::path &inputPath,
                   const LanguageFeatureReportOptions &options,
                   DiagnosticEngine &diagnostics) {
  if (options.repositoryRoot.has_value()) {
    const std::filesystem::path root =
        absoluteNormalized(*options.repositoryRoot);
    if (hasSnapshot(root)) {
      return root;
    }
    diagnostics.error("language-feature-report.root",
                      "repository root does not contain " +
                          std::string(kSnapshotPath) + ": " + root.string());
    return std::nullopt;
  }

  std::vector<std::filesystem::path> starts;
  starts.push_back(absoluteNormalized(inputPath).parent_path());
  starts.push_back(absoluteNormalized(std::filesystem::current_path()));

  std::set<std::string> visited;
  for (std::filesystem::path start : starts) {
    for (std::filesystem::path current = start; !current.empty();
         current = current.parent_path()) {
      const std::string key = current.generic_string();
      if (!visited.insert(key).second) {
        if (current == current.parent_path()) {
          break;
        }
        continue;
      }
      if (hasSnapshot(current)) {
        return current;
      }
      if (current == current.parent_path()) {
        break;
      }
    }
  }

  diagnostics.error("language-feature-report.root",
                    "failed to locate repository root containing " +
                        std::string(kSnapshotPath));
  return std::nullopt;
}

bool isContainedRelativePath(const std::filesystem::path &path) {
  if (path.empty() || path.is_absolute()) {
    return false;
  }
  const auto first = path.begin();
  return first == path.end() || first->string() != "..";
}

std::string reportSourcePath(const std::filesystem::path &inputPath,
                             const std::filesystem::path &root) {
  const std::filesystem::path absoluteInput = absoluteNormalized(inputPath);
  const std::filesystem::path relative =
      absoluteInput.lexically_relative(absoluteNormalized(root));
  if (isContainedRelativePath(relative)) {
    return relative.lexically_normal().generic_string();
  }
  return inputPath.lexically_normal().generic_string();
}

std::string sha256NormalizedText(std::string_view text) {
  return sha256(normalizeText(text));
}

std::optional<std::uintmax_t>
snapshotSchemaVersion(std::string_view snapshotText,
                      DiagnosticEngine &diagnostics) {
  std::optional<std::uintmax_t> version =
      objectUnsignedMember(snapshotText, "schemaVersion");
  if (!version) {
    diagnostics.error("language-feature-report.snapshot-schema",
                      "failed to read CrossTL snapshot schemaVersion");
  }
  return version;
}

bool startsWithAlphaNumeric(std::string_view text) {
  return !text.empty() &&
         std::isalnum(static_cast<unsigned char>(text.front())) != 0;
}

bool isEvidenceIdTailCharacter(char value) {
  const unsigned char byte = static_cast<unsigned char>(value);
  return std::isalnum(byte) != 0 || value == '_' || value == '.' ||
         value == ':' || value == '/' || value == '-';
}

bool isFixtureEvidenceIdTail(std::string_view text) {
  return startsWithAlphaNumeric(text) &&
         std::all_of(text.begin(), text.end(), isEvidenceIdTailCharacter);
}

std::string slugFixtureEvidenceIdTail(std::string_view sourcePath) {
  std::string slug;
  slug.reserve(sourcePath.size());
  bool previousWasDash = false;
  for (char value : sourcePath) {
    if (isEvidenceIdTailCharacter(value)) {
      slug.push_back(value);
      previousWasDash = value == '-';
      continue;
    }
    if (!previousWasDash) {
      slug.push_back('-');
      previousWasDash = true;
    }
  }

  if (slug.empty()) {
    slug = "source-module";
  } else if (!startsWithAlphaNumeric(slug)) {
    slug.insert(0, "source-");
  }

  const std::string digest = sha256(std::string(sourcePath));
  return slug + "-" + digest.substr(0, 12);
}

std::string fixtureEvidenceIdForSourcePath(std::string_view sourcePath) {
  if (isFixtureEvidenceIdTail(sourcePath)) {
    return "fixture:" + std::string(sourcePath);
  }
  return "fixture:" + slugFixtureEvidenceIdTail(sourcePath);
}

void appendUnique(std::vector<std::string> &values,
                  const std::string &candidate) {
  if (std::find(values.begin(), values.end(), candidate) == values.end()) {
    values.push_back(candidate);
  }
}

std::vector<std::string> sortedUnique(std::vector<std::string> values) {
  std::sort(values.begin(), values.end());
  values.erase(std::unique(values.begin(), values.end()), values.end());
  return values;
}

class EvidenceBuilder {
public:
  void add(EvidenceRecord record) {
    if (!seen_.insert(record.id).second) {
      return;
    }
    records_.push_back(std::move(record));
  }

  void addFixture(std::string id, std::string path) {
    EvidenceRecord record;
    record.id = std::move(id);
    record.kind = "fixture";
    record.path = std::move(path);
    add(std::move(record));
  }

  void addSpecIndex(std::string anchor) {
    EvidenceRecord record;
    record.id = "spec-index:" + anchor;
    record.kind = "spec-index";
    record.path = std::string(kSpecIndexPath);
    record.anchor = std::move(anchor);
    add(std::move(record));
  }

  void addCompatibility(std::string anchor) {
    EvidenceRecord record;
    record.id = "compatibility:" + anchor;
    record.kind = "compatibility";
    record.path = std::string(kCompatibilityPath);
    record.anchor = std::move(anchor);
    add(std::move(record));
  }

  void addTargetContract(std::string target) {
    EvidenceRecord record;
    record.id = "target-contract:" + target + ".package-support";
    record.kind = "target-contract";
    record.path = std::string(kTargetCapabilityRegistryPath);
    record.anchor = std::move(target);
    add(std::move(record));
  }

  void addTargetPackageModeContract(std::string target,
                                    std::string packageModeName) {
    EvidenceRecord record;
    record.id = "target-contract:" + target + ".package-mode." +
                std::move(packageModeName);
    record.kind = "target-contract";
    record.path = std::string(kTargetCapabilityRegistryPath);
    record.anchor = std::move(target);
    add(std::move(record));
  }

  void addTargetSupportContract(std::string target,
                                std::string supportStatusName) {
    EvidenceRecord record;
    record.id = "target-contract:" + target + ".support." +
                std::move(supportStatusName);
    record.kind = "target-contract";
    record.path = std::string(kTargetCapabilityRegistryPath);
    record.anchor = std::move(target);
    add(std::move(record));
  }

  const std::vector<EvidenceRecord> &records() const { return records_; }

private:
  std::set<std::string> seen_;
  std::vector<EvidenceRecord> records_;
};

class FeatureCollector {
public:
  explicit FeatureCollector(std::string sourcePath)
      : sourcePath_(std::move(sourcePath)) {}

  void addResource(std::string featureId, std::string status,
                   std::vector<std::string> evidenceIds,
                   std::vector<SourceLocation> sourceLocations = {}) {
    add(resources_, std::move(featureId), std::move(status),
        std::move(evidenceIds), std::move(sourceLocations));
  }

  void addMemory(std::string featureId, std::string status,
                 std::vector<std::string> evidenceIds,
                 std::vector<SourceLocation> sourceLocations = {}) {
    add(memory_, std::move(featureId), std::move(status),
        std::move(evidenceIds), std::move(sourceLocations));
  }

  void addLayout(std::string featureId, std::string status,
                 std::vector<std::string> evidenceIds,
                 std::vector<SourceLocation> sourceLocations = {}) {
    add(layout_, std::move(featureId), std::move(status),
        std::move(evidenceIds), std::move(sourceLocations));
  }

  void addLayoutLocation(std::string_view featureId,
                         SourceLocation sourceLocation) {
    addLocation(layout_, featureId, std::move(sourceLocation));
  }

  FeatureRecordGroups groups() const {
    return FeatureRecordGroups{records(resources_), records(memory_),
                               records(layout_)};
  }

private:
  using FeatureMap = std::map<std::string, FeatureRecord>;

  static bool sourceLocationAvailable(const SourceLocation &location) {
    return !location.file.empty();
  }

  SourceLocation reportLocation(SourceLocation location) const {
    location.file = sourcePath_;
    return location;
  }

  void appendLocation(FeatureRecord &record, SourceLocation location) const {
    if (!sourceLocationAvailable(location)) {
      return;
    }
    record.sourceLocations.push_back(reportLocation(std::move(location)));
  }

  void add(FeatureMap &features, std::string featureId, std::string status,
           std::vector<std::string> evidenceIds,
           std::vector<SourceLocation> sourceLocations) {
    FeatureRecord &record = features[featureId];
    if (record.featureId.empty()) {
      record.featureId = std::move(featureId);
      record.status = std::move(status);
    }
    for (SourceLocation &location : sourceLocations) {
      appendLocation(record, std::move(location));
    }
    for (const std::string &evidenceId : evidenceIds) {
      appendUnique(record.evidenceIds, evidenceId);
    }
  }

  void addLocation(FeatureMap &features, std::string_view featureId,
                   SourceLocation sourceLocation) {
    auto existing = features.find(std::string(featureId));
    if (existing == features.end()) {
      return;
    }
    appendLocation(existing->second, std::move(sourceLocation));
  }

  static bool locationLess(const SourceLocation &lhs,
                           const SourceLocation &rhs) {
    return std::tie(lhs.file, lhs.offset, lhs.endOffset, lhs.line, lhs.column,
                    lhs.endLine, lhs.endColumn, lhs.length) <
           std::tie(rhs.file, rhs.offset, rhs.endOffset, rhs.line, rhs.column,
                    rhs.endLine, rhs.endColumn, rhs.length);
  }

  static bool locationEqual(const SourceLocation &lhs,
                            const SourceLocation &rhs) {
    return std::tie(lhs.file, lhs.line, lhs.column, lhs.offset, lhs.length,
                    lhs.endLine, lhs.endColumn, lhs.endOffset) ==
           std::tie(rhs.file, rhs.line, rhs.column, rhs.offset, rhs.length,
                    rhs.endLine, rhs.endColumn, rhs.endOffset);
  }

  static void sortAndDeduplicateLocations(
      std::vector<SourceLocation> &locations) {
    std::sort(locations.begin(), locations.end(), locationLess);
    locations.erase(std::unique(locations.begin(), locations.end(),
                                locationEqual),
                    locations.end());
  }

  static std::vector<FeatureRecord> records(const FeatureMap &features) {
    std::vector<FeatureRecord> result;
    result.reserve(features.size());
    for (const auto &[unused, record] : features) {
      (void)unused;
      FeatureRecord normalized = record;
      sortAndDeduplicateLocations(normalized.sourceLocations);
      result.push_back(std::move(normalized));
    }
    return result;
  }

  std::string sourcePath_;
  FeatureMap resources_;
  FeatureMap memory_;
  FeatureMap layout_;
};

std::string resourceFeatureId(const HIRResource &resource) {
  switch (resource.kind) {
  case HIRResourceKind::Uniform:
    return "resource.uniform-buffer";
  case HIRResourceKind::Buffer:
    return "resource.storage-buffer";
  case HIRResourceKind::Texture:
    return "resource.texture";
  case HIRResourceKind::StorageImage:
    return "resource.storage-image";
  case HIRResourceKind::Sampler:
    return "resource.sampler";
  case HIRResourceKind::Shared:
    return "memory.workgroup-shared";
  case HIRResourceKind::Value:
    break;
  }
  return "resource.value";
}

bool isDescriptorResource(HIRResourceKind kind) {
  return kind == HIRResourceKind::Uniform || kind == HIRResourceKind::Buffer ||
         kind == HIRResourceKind::Texture ||
         kind == HIRResourceKind::StorageImage ||
         kind == HIRResourceKind::Sampler;
}

void collectExpressionFeatures(const HIRExpression &expression,
                               FeatureCollector &features,
                               const std::vector<std::string> &resourceEvidence,
                               const std::vector<std::string> &memoryEvidence) {
  if (expression.kind == HIRExpressionKind::NonUniform) {
    features.addResource("resource.nonuniform-descriptor-index",
                         "package-supported", resourceEvidence,
                         {expression.location});
  }
  if (expression.kind == HIRExpressionKind::Call) {
    if (expression.value == "workgroupBarrier" ||
        expression.value == "barrier") {
      features.addMemory("memory.workgroup-barrier", "package-supported",
                         memoryEvidence, {expression.location});
    } else if (expression.value.rfind("imageAtomic", 0) == 0) {
      features.addMemory("memory.storage-image-atomic", "package-supported",
                         memoryEvidence, {expression.location});
    } else if (expression.value.rfind("atomic", 0) == 0) {
      features.addMemory("memory.atomic", "package-supported", memoryEvidence,
                         {expression.location});
    }
  }
  for (const HIRExpression &child : expression.children) {
    collectExpressionFeatures(child, features, resourceEvidence,
                              memoryEvidence);
  }
}

void collectStatementFeatures(const HIRStatement &statement,
                              FeatureCollector &features,
                              const std::vector<std::string> &resourceEvidence,
                              const std::vector<std::string> &memoryEvidence) {
  collectExpressionFeatures(statement.target, features, resourceEvidence,
                            memoryEvidence);
  collectExpressionFeatures(statement.value, features, resourceEvidence,
                            memoryEvidence);
  for (const HIRStatement &child : statement.initializer) {
    collectStatementFeatures(child, features, resourceEvidence, memoryEvidence);
  }
  for (const HIRStatement &child : statement.update) {
    collectStatementFeatures(child, features, resourceEvidence, memoryEvidence);
  }
  for (const HIRStatement &child : statement.body) {
    collectStatementFeatures(child, features, resourceEvidence, memoryEvidence);
  }
  for (const HIRStatement &child : statement.elseBody) {
    collectStatementFeatures(child, features, resourceEvidence, memoryEvidence);
  }
}

void collectModuleFeatures(const HIRModule &module, FeatureCollector &features,
                           EvidenceBuilder &evidence,
                           const std::string &fixtureEvidenceId) {
  evidence.addSpecIndex("grammar.resources");
  evidence.addSpecIndex("semantics.metadata-and-layout");

  const std::vector<std::string> resourceEvidence = {
      fixtureEvidenceId, "spec-index:grammar.resources"};
  const std::vector<std::string> aggregateResourceEvidence = {
      "spec-index:grammar.resources"};
  const std::vector<std::string> layoutEvidence = {
      "spec-index:semantics.metadata-and-layout"};
  const std::vector<std::string> aggregateMemoryEvidence = {
      "spec-index:grammar.resources", "spec-index:semantics.metadata-and-layout"};
  const std::vector<std::string> memoryEvidence = {fixtureEvidenceId};

  for (std::string_view featureId :
       {"resource.storage-image-types", "resource.buffer-types",
        "resource.uav-buffer-types", "resource.sampler-state-types",
        "resource.access-metadata", "resource.descriptor-index-metadata",
        "resource.image-format-metadata"}) {
    features.addResource(std::string(featureId),
                         std::string(kCrossTLInventoryOnly),
                         aggregateResourceEvidence);
  }
  for (std::string_view featureId :
       {"memory.address-spaces", "memory.layout-metadata"}) {
    features.addMemory(std::string(featureId),
                       std::string(kCrossTLInventoryOnly),
                       aggregateMemoryEvidence);
  }
  for (std::string_view featureId :
       {"layout.builtin-semantics", "layout.metadata-single-values",
        "layout.metadata-aliases", "layout.metadata-multi-values",
        "layout.interpolation-metadata", "layout.stage-layout-entries"}) {
    features.addLayout(std::string(featureId),
                       std::string(kCrossTLInventoryOnly),
                       layoutEvidence);
  }

  for (const HIRStage &stage : module.stages) {
    if (stage.workgroupSize.has_value()) {
      features.addLayout("layout.local-size", "accepted-source",
                         layoutEvidence);
    }
    for (const HIRResource &resource : stage.resources) {
      const std::string featureId = resourceFeatureId(resource);
      if (resource.kind == HIRResourceKind::Shared) {
        features.addMemory(featureId, "package-supported", memoryEvidence,
                           {resource.type.location});
      } else if (resource.kind != HIRResourceKind::Value) {
        features.addResource(featureId, "package-supported", resourceEvidence,
                             {resource.type.location});
      }

      if (resource.explicitSet || resource.explicitBinding) {
        features.addLayout("layout.set-binding", "accepted-source",
                           layoutEvidence);
      }
      if (resource.storageImageFormat.has_value()) {
        features.addLayout("layout.storage-image-format", "accepted-source",
                           layoutEvidence);
      }
      if (isDescriptorResource(resource.kind) &&
          resource.type.arraySize.has_value()) {
        features.addResource(resource.type.arraySize->empty()
                                 ? "resource.runtime-descriptor-array"
                                 : "resource.descriptor-array",
                             "package-supported", resourceEvidence,
                             {resource.type.location});
        features.addLayout(resource.type.arraySize->empty()
                               ? "layout.runtime-array"
                               : "layout.fixed-array",
                           "accepted-source", layoutEvidence,
                           {resource.type.location});
      }
    }

    for (const HIRFunction &function : stage.functions) {
      for (const HIRStatement &statement : function.body) {
        collectStatementFeatures(statement, features, resourceEvidence,
                                 memoryEvidence);
      }
    }
  }

  for (const HIRFunction &function : module.functions) {
    for (const HIRStatement &statement : function.body) {
      collectStatementFeatures(statement, features, resourceEvidence,
                               memoryEvidence);
    }
  }
}

void collectFrontendMetadataFeatures(const ShaderModule &module,
                                     FeatureCollector &features,
                                     const std::string &fixtureEvidenceId) {
  const std::vector<std::string> resourceEvidence = {
      fixtureEvidenceId, "spec-index:grammar.resources"};
  for (const StageDecl &stage : module.stages) {
    if (stage.workgroupSize.has_value()) {
      features.addLayoutLocation("layout.local-size",
                                 stage.workgroupSize->location);
    }
    for (const ResourceDecl &resource : stage.resources) {
      if (resource.set.has_value() || resource.binding.has_value()) {
        features.addLayoutLocation("layout.set-binding",
                                   resource.bindingLocation);
      }
      if (resource.storageImageFormat.has_value()) {
        features.addLayoutLocation("layout.storage-image-format",
                                   resource.storageImageFormatLocation);
      }
      if (resource.storageImageAccessQualifier.has_value()) {
        features.addResource("resource.storage-image-access-qualifier",
                             "accepted-source", resourceEvidence,
                             {resource.storageImageAccessLocation});
      }
    }
  }
}

std::string projectionTargetName(
    const TargetLegalizationContractProjection &projection) {
  if (!projection.targetProfile.resolvedTargetName.empty()) {
    return projection.targetProfile.resolvedTargetName;
  }
  return targetName(projection.targetProfile.resolvedTarget);
}

std::string
projectionPackageModeName(
    const TargetLegalizationContractProjection &projection) {
  if (!projection.packageModeName.empty()) {
    return projection.packageModeName;
  }
  return targetLegalizationPackageModeName(projection.packageMode);
}

std::string
projectionSupportStatusName(
    const TargetLegalizationContractProjection &projection) {
  if (!projection.supportStatusName.empty()) {
    return projection.supportStatusName;
  }
  return targetLegalizationSupportStatusName(projection.supportStatus);
}

std::string
packageModeForGate(const TargetLegalizationContractProjection &projection) {
  const std::string packageModeName = projectionPackageModeName(projection);
  if (packageModeName == "native") {
    return "native";
  }
  if (packageModeName == "source-package") {
    return "source";
  }
  return "unavailable";
}

std::string
gateIdForCapabilities(const TargetLegalizationContractProjection &projection) {
  const auto contains = [](const std::vector<std::string> &values,
                           std::string_view needle) {
    return std::find_if(values.begin(), values.end(),
                        [needle](const std::string &value) {
                          return value.find(needle) != std::string::npos;
                        }) != values.end();
  };
  const std::vector<std::string> &missing = projection.missingCapabilityIds;
  if (contains(missing, "descriptor-array") ||
      contains(missing, "runtime-resource-array") ||
      contains(missing, "runtime-texture") ||
      contains(missing, "runtime-sampler")) {
    return "target.resource-arrays";
  }
  if (contains(missing, "texture-shadow") ||
      contains(missing, "texture-compare-lod") ||
      contains(missing, "shadow-compare")) {
    return "target.texture-shadow-lod";
  }
  if (contains(missing, "function-parameter-array")) {
    return "target.helper-array-params";
  }
  return "target.package-support";
}

std::string featureFamilyForGate(std::string_view gateId) {
  if (gateId == "target.resource-arrays") {
    return "resources";
  }
  if (gateId == "target.texture-shadow-lod") {
    return "intrinsics";
  }
  if (gateId == "target.helper-array-params") {
    return "language";
  }
  return "package";
}

std::string statusForGate(
    const TargetLegalizationContractProjection &projection) {
  if (targetLegalizationProjectionSupportsPackage(projection)) {
    return "supported";
  }
  if (projection.optionalNativeToolMissing) {
    return "unavailable";
  }
  if (projectionSupportStatusName(projection) != "unsupported") {
    return "unsupported";
  }
  return "planned-failure";
}

std::vector<std::string>
diagnosticCodesForGate(const TargetLegalizationContractProjection &projection) {
  std::vector<std::string> codes = projection.diagnosticSummary.codes;
  for (const std::string &capability : projection.missingCapabilityIds) {
    const std::string marker = ".diagnostic.";
    const std::size_t markerPosition = capability.find(marker);
    if (markerPosition != std::string::npos) {
      codes.push_back(capability.substr(markerPosition + marker.size()));
    }
  }
  return sortedUnique(std::move(codes));
}

std::vector<std::string>
gateEvidenceIds(const TargetLegalizationContractProjection &projection,
                std::string_view gateId, EvidenceBuilder &evidence) {
  std::vector<std::string> ids;
  if (gateId == "target.resource-arrays" ||
      gateId == "target.texture-shadow-lod" ||
      gateId == "target.helper-array-params") {
    const std::string compatibilityId = "compatibility:" + std::string(gateId);
    ids.push_back(compatibilityId);
    evidence.addCompatibility(std::string(gateId));
  }

  const std::string target = projectionTargetName(projection);
  const std::string targetContractId =
      "target-contract:" + target + ".package-support";
  ids.push_back(targetContractId);
  evidence.addTargetContract(target);
  const std::string packageModeName = projectionPackageModeName(projection);
  const std::string packageModeId =
      "target-contract:" + target + ".package-mode." + packageModeName;
  ids.push_back(packageModeId);
  evidence.addTargetPackageModeContract(target, packageModeName);
  const std::string supportStatusName = projectionSupportStatusName(projection);
  const std::string supportStatusId =
      "target-contract:" + target + ".support." + supportStatusName;
  ids.push_back(supportStatusId);
  evidence.addTargetSupportContract(target, supportStatusName);
  return sortedUnique(std::move(ids));
}

void mergeFact(std::map<std::string, FactRecord> &facts, std::string factId,
               std::string classification, std::string message,
               const std::vector<std::string> &evidenceIds) {
  FactRecord &fact = facts[factId];
  if (fact.factId.empty()) {
    fact.factId = std::move(factId);
    fact.classification = std::move(classification);
    fact.message = std::move(message);
  }
  for (const std::string &evidenceId : evidenceIds) {
    appendUnique(fact.evidenceIds, evidenceId);
  }
  fact.evidenceIds = sortedUnique(std::move(fact.evidenceIds));
}

std::vector<TargetGateRecord>
targetGates(const HIRModule &module, EvidenceBuilder &evidence,
            std::map<std::string, FactRecord> &unsupportedFacts) {
  std::vector<TargetGateRecord> gates;
  const std::vector<TargetLegalizationResult> legalizations =
      legalizeTargets(module, defaultTargetForHost());
  for (const TargetLegalizationResult &legalization : legalizations) {
    const TargetLegalizationContractProjection projection =
        targetLegalizationContractProjection(legalization);
    // Audit anchors: targetLegalizationContract and package support evidence
    // are consumed through the projection here.
    if (targetLegalizationProjectionSupportsPackage(projection)) {
      continue;
    }

    TargetGateRecord gate;
    gate.target = projectionTargetName(projection);
    gate.targetVersion = "v0";
    gate.packageMode = packageModeForGate(projection);
    gate.gateId = gateIdForCapabilities(projection);
    gate.featureFamily = featureFamilyForGate(gate.gateId);
    gate.status = statusForGate(projection);
    gate.requiredCapabilities =
        projection.missingCapabilityIds.empty()
            ? sortedUnique(projection.requiredCapabilityIds)
            : sortedUnique(projection.missingCapabilityIds);
    gate.diagnosticCodes = diagnosticCodesForGate(projection);
    gate.evidenceIds = gateEvidenceIds(projection, gate.gateId, evidence);

    mergeFact(unsupportedFacts, gate.gateId, "target.unsupported",
              "One or more targets cannot emit this module in the v0 package "
              "lane.",
              gate.evidenceIds);
    gates.push_back(std::move(gate));
  }
  std::sort(gates.begin(), gates.end(), [](const TargetGateRecord &lhs,
                                           const TargetGateRecord &rhs) {
    if (lhs.target != rhs.target) {
      return lhs.target < rhs.target;
    }
    return lhs.gateId < rhs.gateId;
  });
  return gates;
}

std::map<std::string, std::size_t>
bucketSummary(const FeatureRecordGroups &features,
              const std::vector<FactRecord> &unsupportedFacts,
              const std::vector<FactRecord> &deprecatedFacts,
              const std::vector<FactRecord> &errorFacts) {
  std::map<std::string, std::size_t> counts;
  for (std::string_view bucket : kCompatibilityBuckets) {
    counts[std::string(bucket)] = 0;
  }
  const auto countFeature = [&counts](const FeatureRecord &record) {
    ++counts[record.status];
  };
  for (const FeatureRecord &record : features.resources) {
    countFeature(record);
  }
  for (const FeatureRecord &record : features.memory) {
    countFeature(record);
  }
  for (const FeatureRecord &record : features.layout) {
    countFeature(record);
  }
  const auto countFact = [&counts](const FactRecord &record) {
    ++counts[record.classification];
  };
  for (const FactRecord &record : unsupportedFacts) {
    countFact(record);
  }
  for (const FactRecord &record : deprecatedFacts) {
    countFact(record);
  }
  for (const FactRecord &record : errorFacts) {
    countFact(record);
  }
  return counts;
}

std::vector<FactRecord> factRecords(
    const std::map<std::string, FactRecord> &facts) {
  std::vector<FactRecord> records;
  records.reserve(facts.size());
  for (const auto &[unused, fact] : facts) {
    (void)unused;
    records.push_back(fact);
  }
  return records;
}

std::vector<StageEntryPoint> stageEntryPoints(const HIRModule &module) {
  std::vector<StageEntryPoint> entries;
  entries.reserve(module.stages.size());
  for (const HIRStage &stage : module.stages) {
    entries.push_back(StageEntryPoint{stage.stage, stage.entryPointName});
  }
  std::sort(entries.begin(), entries.end(),
            [](const StageEntryPoint &lhs, const StageEntryPoint &rhs) {
              if (lhs.stage != rhs.stage) {
                return lhs.stage < rhs.stage;
              }
              return lhs.entryPoint < rhs.entryPoint;
            });
  return entries;
}

void appendStringArray(std::ostringstream &out,
                       const std::vector<std::string> &values,
                       std::string_view indent) {
  out << "[";
  if (values.empty()) {
    out << "]";
    return;
  }

  out << "\n";
  for (std::size_t index = 0; index < values.size(); ++index) {
    out << indent << "  \"" << escapeJson(values[index]) << "\"";
    if (index + 1 != values.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << indent << "]";
}

void appendSourceLocation(std::ostringstream &out,
                          const SourceLocation &location,
                          std::string_view indent) {
  out << indent << "{\n"
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

void appendSourceLocationArray(std::ostringstream &out,
                               const std::vector<SourceLocation> &locations,
                               std::string_view indent) {
  out << "[";
  if (locations.empty()) {
    out << "]";
    return;
  }

  out << "\n";
  for (std::size_t index = 0; index < locations.size(); ++index) {
    appendSourceLocation(out, locations[index], std::string(indent) + "  ");
    if (index + 1 != locations.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << indent << "]";
}

void appendFeatureRecordArray(std::ostringstream &out,
                              const std::vector<FeatureRecord> &records,
                              std::string_view indent) {
  out << "[";
  if (records.empty()) {
    out << "]";
    return;
  }

  out << "\n";
  for (std::size_t index = 0; index < records.size(); ++index) {
    const FeatureRecord &record = records[index];
    out << indent << "  {\n"
        << indent << "    \"featureId\": \"" << escapeJson(record.featureId)
        << "\",\n"
        << indent << "    \"status\": \"" << escapeJson(record.status)
        << "\",\n"
        << indent << "    \"sourceLocations\": ";
    appendSourceLocationArray(out, record.sourceLocations,
                              std::string(indent) + "    ");
    out << ",\n" << indent << "    \"evidenceIds\": ";
    appendStringArray(out, record.evidenceIds, std::string(indent) + "    ");
    out << "\n" << indent << "  }";
    if (index + 1 != records.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << indent << "]";
}

void appendFactRecordArray(std::ostringstream &out,
                           const std::vector<FactRecord> &records,
                           std::string_view indent) {
  out << "[";
  if (records.empty()) {
    out << "]";
    return;
  }

  out << "\n";
  for (std::size_t index = 0; index < records.size(); ++index) {
    const FactRecord &record = records[index];
    out << indent << "  {\n"
        << indent << "    \"factId\": \"" << escapeJson(record.factId)
        << "\",\n"
        << indent << "    \"classification\": \""
        << escapeJson(record.classification) << "\",\n"
        << indent << "    \"message\": \"" << escapeJson(record.message)
        << "\",\n"
        << indent << "    \"evidenceIds\": ";
    appendStringArray(out, record.evidenceIds, std::string(indent) + "    ");
    out << "\n" << indent << "  }";
    if (index + 1 != records.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << indent << "]";
}

void appendTargetGateArray(std::ostringstream &out,
                           const std::vector<TargetGateRecord> &gates,
                           std::string_view indent) {
  out << "[";
  if (gates.empty()) {
    out << "]";
    return;
  }

  out << "\n";
  for (std::size_t index = 0; index < gates.size(); ++index) {
    const TargetGateRecord &gate = gates[index];
    out << indent << "  {\n"
        << indent << "    \"target\": \"" << escapeJson(gate.target)
        << "\",\n"
        << indent << "    \"targetVersion\": \""
        << escapeJson(gate.targetVersion) << "\",\n"
        << indent << "    \"packageMode\": \"" << escapeJson(gate.packageMode)
        << "\",\n"
        << indent << "    \"gateId\": \"" << escapeJson(gate.gateId)
        << "\",\n"
        << indent << "    \"featureFamily\": \""
        << escapeJson(gate.featureFamily) << "\",\n"
        << indent << "    \"status\": \"" << escapeJson(gate.status)
        << "\",\n"
        << indent << "    \"requiredCapabilities\": ";
    appendStringArray(out, gate.requiredCapabilities,
                      std::string(indent) + "    ");
    out << ",\n" << indent << "    \"diagnosticCodes\": ";
    appendStringArray(out, gate.diagnosticCodes, std::string(indent) + "    ");
    out << ",\n" << indent << "    \"evidenceIds\": ";
    appendStringArray(out, gate.evidenceIds, std::string(indent) + "    ");
    out << "\n" << indent << "  }";
    if (index + 1 != gates.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << indent << "]";
}

void appendEvidenceArray(std::ostringstream &out,
                         const std::vector<EvidenceRecord> &records,
                         std::string_view indent) {
  out << "[";
  if (records.empty()) {
    out << "]";
    return;
  }

  out << "\n";
  for (std::size_t index = 0; index < records.size(); ++index) {
    const EvidenceRecord &record = records[index];
    out << indent << "  {\n"
        << indent << "    \"id\": \"" << escapeJson(record.id) << "\",\n"
        << indent << "    \"kind\": \"" << escapeJson(record.kind) << "\"";
    const auto appendOptional = [&](std::string_view name,
                                    const std::optional<std::string> &value) {
      if (value.has_value()) {
        out << ",\n"
            << indent << "    \"" << name << "\": \"" << escapeJson(*value)
            << "\"";
      }
    };
    appendOptional("path", record.path);
    appendOptional("anchor", record.anchor);
    appendOptional("ctestName", record.ctestName);
    appendOptional("fixture", record.fixture);
    appendOptional("diagnosticCode", record.diagnosticCode);
    appendOptional("schemaPath", record.schemaPath);
    out << "\n" << indent << "  }";
    if (index + 1 != records.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << indent << "]";
}

std::vector<std::string>
generationCommand(const LanguageFeatureReportOptions &options,
                  const std::string &sourcePath) {
  if (!options.commandLine.empty()) {
    return options.commandLine;
  }
  return {"cglc", "language-feature-report", sourcePath};
}

} // namespace

std::optional<std::string> languageFeatureReportJson(
    const std::filesystem::path &inputPath, DiagnosticEngine &diagnostics,
    const LanguageFeatureReportOptions &options) {
  const std::optional<std::filesystem::path> root =
      findRepositoryRoot(inputPath, options, diagnostics);
  if (!root) {
    return std::nullopt;
  }

  const std::optional<std::string> snapshotText =
      readTextFile(*root / kSnapshotPath, diagnostics,
                   "language-feature-report.snapshot-read");
  if (!snapshotText) {
    return std::nullopt;
  }
  const std::optional<std::uintmax_t> schemaVersion =
      snapshotSchemaVersion(*snapshotText, diagnostics);
  if (!schemaVersion) {
    return std::nullopt;
  }

  CompilerModuleOptions compilerOptions;
  compilerOptions.validateBackendInput = false;
  std::optional<CompilerModule> module =
      loadCompilerModule(inputPath, diagnostics, compilerOptions);
  if (!module) {
    return std::nullopt;
  }

  const std::string sourcePath = reportSourcePath(inputPath, *root);
  const std::string fixtureEvidenceId =
      fixtureEvidenceIdForSourcePath(sourcePath);

  EvidenceBuilder evidence;
  evidence.addFixture(fixtureEvidenceId, sourcePath);

  FeatureCollector featureCollector(sourcePath);
  collectModuleFeatures(module->hir, featureCollector, evidence,
                        fixtureEvidenceId);
  collectFrontendMetadataFeatures(module->ast, featureCollector,
                                  fixtureEvidenceId);
  FeatureRecordGroups features = featureCollector.groups();

  std::map<std::string, FactRecord> unsupportedFactMap;
  std::vector<TargetGateRecord> gates =
      targetGates(module->hir, evidence, unsupportedFactMap);
  std::vector<FactRecord> unsupportedFacts = factRecords(unsupportedFactMap);
  const std::vector<FactRecord> deprecatedFacts;
  const std::vector<FactRecord> errorFacts;
  const std::map<std::string, std::size_t> summary =
      bucketSummary(features, unsupportedFacts, deprecatedFacts, errorFacts);
  const std::vector<StageEntryPoint> entries = stageEntryPoints(module->hir);
  const std::vector<std::string> command =
      generationCommand(options, sourcePath);

  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": 1,\n"
      << "  \"kind\": \"" << kReportKind << "\",\n"
      << "  \"module\": {\n"
      << "    \"moduleId\": \"" << escapeJson(module->hir.name) << "\",\n"
      << "    \"sourcePath\": \"" << escapeJson(sourcePath) << "\",\n"
      << "    \"sourceSha256\": \"" << sha256NormalizedText(module->source)
      << "\",\n"
      << "    \"stageEntryPoints\": [";
  if (!entries.empty()) {
    out << "\n";
    for (std::size_t index = 0; index < entries.size(); ++index) {
      out << "      {\n"
          << "        \"stage\": \"" << escapeJson(entries[index].stage)
          << "\",\n"
          << "        \"entryPoint\": \""
          << escapeJson(entries[index].entryPoint) << "\"\n"
          << "      }";
      if (index + 1 != entries.size()) {
        out << ",";
      }
      out << "\n";
    }
    out << "    ";
  }
  out << "]\n"
      << "  },\n"
      << "  \"language\": {\n"
      << "    \"family\": \"CrossGL\",\n"
      << "    \"version\": \"v0\",\n"
      << "    \"nativeProfile\": \"native-v0\",\n"
      << "    \"compatibilityContract\": \"" << kSupportContractPath << "\"\n"
      << "  },\n"
      << "  \"crossTLSnapshotSeal\": {\n"
      << "    \"snapshotId\": \"" << kSnapshotId << "\",\n"
      << "    \"snapshotPath\": \"" << kSnapshotPath << "\",\n"
      << "    \"snapshotSha256\": \"" << sha256NormalizedText(*snapshotText)
      << "\",\n"
      << "    \"snapshotSchemaVersion\": " << *schemaVersion << "\n"
      << "  },\n"
      << "  \"compatibilityBucketSummary\": {\n";
  for (std::size_t index = 0; index < kCompatibilityBuckets.size(); ++index) {
    const std::string bucket(kCompatibilityBuckets[index]);
    out << "    \"" << bucket << "\": " << summary.at(bucket);
    if (index + 1 != kCompatibilityBuckets.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << "  },\n"
      << "  \"targetFeatureGates\": ";
  appendTargetGateArray(out, gates, "  ");
  out << ",\n"
      << "  \"resourceMemoryLayoutFeatures\": {\n"
      << "    \"resources\": ";
  appendFeatureRecordArray(out, features.resources, "    ");
  out << ",\n"
      << "    \"memory\": ";
  appendFeatureRecordArray(out, features.memory, "    ");
  out << ",\n"
      << "    \"layout\": ";
  appendFeatureRecordArray(out, features.layout, "    ");
  out << "\n"
      << "  },\n"
      << "  \"facts\": {\n"
      << "    \"unsupported\": ";
  appendFactRecordArray(out, unsupportedFacts, "    ");
  out << ",\n"
      << "    \"deprecated\": ";
  appendFactRecordArray(out, deprecatedFacts, "    ");
  out << ",\n"
      << "    \"error\": ";
  appendFactRecordArray(out, errorFacts, "    ");
  out << "\n"
      << "  },\n"
      << "  \"evidence\": ";
  appendEvidenceArray(out, evidence.records(), "  ");
  out << ",\n"
      << "  \"generation\": {\n"
      << "    \"tool\": \"cglc\",\n"
      << "    \"mode\": \"report-only\",\n"
      << "    \"command\": ";
  appendStringArray(out, command, "    ");
  out << "\n"
      << "  }\n"
      << "}\n";
  return out.str();
}

} // namespace crossgl
