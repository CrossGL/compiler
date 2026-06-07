#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "crossgl/Basic/Diagnostic.h"

namespace crossgl {

struct PackageSidecarRecord {
  std::filesystem::path path;
  std::filesystem::path requestedPath;
  std::string kind;
  std::string token;
  std::uint64_t attempt = 0;
  bool isDirectory = false;
};

struct PackagePublicationInfo {
  std::filesystem::path requestedPath;
  std::string state;
  std::optional<PackageSidecarRecord> currentSidecar;
  std::vector<PackageSidecarRecord> siblingSidecars;
};

struct PackageSidecarListResult {
  bool success = false;
  bool requestedExists = false;
  std::filesystem::path packagePath;
  PackagePublicationInfo publication;
  std::vector<Diagnostic> diagnostics;
};

struct PackageStaleSidecarCleanupOptions {
  bool dryRun = true;
  std::optional<std::size_t> keepLast;
  std::optional<std::uint64_t> olderThanSeconds;
};

struct PackageStaleSidecarCleanupRecord {
  PackageSidecarRecord sidecar;
  std::string reason;
  std::string retainedBy;
  std::string action;
  bool success = true;
};

struct PackageStaleSidecarCleanupResult {
  bool success = false;
  bool dryRun = true;
  bool requestedExists = false;
  std::filesystem::path packagePath;
  PackagePublicationInfo publication;
  std::optional<std::size_t> keepLast;
  std::optional<std::uint64_t> olderThanSeconds;
  std::vector<PackageStaleSidecarCleanupRecord> retained;
  std::vector<PackageStaleSidecarCleanupRecord> candidates;
  std::vector<Diagnostic> diagnostics;
};

struct PackageMaintenancePolicyResult {
  bool success = false;
  PackageStaleSidecarCleanupOptions options;
  std::vector<Diagnostic> diagnostics;
};

struct PackageMaintenanceScanResult {
  bool success = false;
  bool dryRun = true;
  std::filesystem::path rootPath;
  std::optional<std::size_t> keepLast;
  std::optional<std::uint64_t> olderThanSeconds;
  std::vector<PackageStaleSidecarCleanupResult> packages;
  std::vector<Diagnostic> diagnostics;
};

struct PackageMaintenanceSetLoadResult {
  bool success = false;
  std::filesystem::path setPath;
  std::vector<std::filesystem::path> packagePaths;
  std::vector<Diagnostic> diagnostics;
};

struct PackageMaintenanceSetResult {
  bool success = false;
  bool dryRun = true;
  std::filesystem::path setPath;
  std::optional<std::size_t> keepLast;
  std::optional<std::uint64_t> olderThanSeconds;
  std::vector<PackageStaleSidecarCleanupResult> packages;
  std::vector<Diagnostic> diagnostics;
};

struct PackageMaintenanceSetExportResult {
  bool success = false;
  std::filesystem::path rootPath;
  std::filesystem::path setPath;
  std::vector<std::filesystem::path> packagePaths;
  std::vector<Diagnostic> diagnostics;
};

struct PackageMaintenanceSetVerificationResult {
  bool success = false;
  bool matches = false;
  std::filesystem::path rootPath;
  std::filesystem::path setPath;
  std::vector<std::filesystem::path> scannedPackagePaths;
  std::vector<std::filesystem::path> setPackagePaths;
  std::vector<std::filesystem::path> missingFromSet;
  std::vector<std::filesystem::path> extraInSet;
  std::vector<Diagnostic> diagnostics;
};

struct PackageMaintenanceSetVerificationBatchEntry {
  std::filesystem::path rootPath;
  std::filesystem::path setPath;
};

struct PackageMaintenanceSetVerificationBatchLoadResult {
  bool success = false;
  std::filesystem::path batchPath;
  std::vector<PackageMaintenanceSetVerificationBatchEntry> entries;
  std::vector<Diagnostic> diagnostics;
};

struct PackageMaintenanceSetVerificationBatchResult {
  bool success = false;
  bool matches = false;
  std::filesystem::path batchPath;
  std::vector<PackageMaintenanceSetVerificationResult> verifications;
  std::vector<Diagnostic> diagnostics;
};

struct PackageMaintenanceSetVerificationBatchExportResult {
  bool success = false;
  std::filesystem::path batchPath;
  std::vector<PackageMaintenanceSetVerificationBatchEntry> entries;
  std::vector<Diagnostic> diagnostics;
};

struct PackageMaintenanceSetVerificationBatchSummaryExportResult {
  bool success = false;
  std::filesystem::path summaryPath;
  std::vector<Diagnostic> diagnostics;
};

struct PackageReleasePromotionDiagnosticCounts {
  std::size_t note = 0;
  std::size_t warning = 0;
  std::size_t error = 0;
};

struct PackageReleasePromotionSummary {
  std::filesystem::path summaryPath;
  std::filesystem::path batchPath;
  bool success = false;
  bool matches = false;
  bool releaseEligible = false;
  std::size_t verificationCount = 0;
  std::size_t matchedCount = 0;
  std::size_t mismatchedCount = 0;
  std::size_t failedCount = 0;
  std::size_t scannedPackageCount = 0;
  std::size_t setPackageCount = 0;
  std::size_t missingFromSetCount = 0;
  std::size_t extraInSetCount = 0;
  PackageReleasePromotionDiagnosticCounts diagnosticCounts;
};

struct PackageReleasePromotionBlocker {
  std::string code;
  std::string message;
  std::size_t count = 0;
};

struct PackageReleasePromotionSourceHash {
  std::string algorithm;
  std::string value;
};

struct PackageReleasePromotionArtifact {
  std::string name;
  std::string path;
  bool exists = false;
  std::optional<std::uintmax_t> sizeBytes;
  std::optional<std::string> sha256;
};

struct PackageReleasePackageArtifactRequirements {
  std::string target;
  std::string packageMode;
  std::vector<std::string> requiredPathArtifacts;
  bool requiresNativeBinaryStatus = false;
  bool allowsPlannedNativeBinary = false;
  bool allowsPlannedNativeSourceEvidence = false;
};

struct PackageReleasePromotionPackage {
  std::filesystem::path packagePath;
  std::string module;
  std::string target;
  std::optional<PackageReleasePromotionSourceHash> sourceHash;
  std::optional<std::string> nativeBinaryStatus;
  std::optional<PackageReleasePackageArtifactRequirements>
      artifactRequirements;
  std::vector<PackageReleasePromotionArtifact> artifacts;
};

struct PackageReleasePromotionManifestResult {
  bool success = false;
  bool releaseEligible = false;
  bool manifestWritten = false;
  std::filesystem::path summaryPath;
  std::filesystem::path manifestPath;
  PackageReleasePromotionSummary summary;
  std::vector<PackageReleasePromotionBlocker> blockers;
  std::vector<PackageReleasePromotionPackage> packages;
  std::vector<Diagnostic> diagnostics;
};

struct PackageReleaseBundleManifestResult {
  bool success = false;
  bool bundleWritten = false;
  bool releaseEligible = false;
  std::filesystem::path bundlePath;
  std::filesystem::path promotionManifestPath;
  PackageReleasePromotionManifestResult promotion;
  std::vector<Diagnostic> diagnostics;
};

struct PackageReleaseBundleVerificationResult {
  bool success = false;
  bool releaseEligible = false;
  std::filesystem::path bundlePath;
  std::string status;
  std::size_t blockerCount = 0;
  std::size_t packageCount = 0;
  std::size_t artifactCount = 0;
  std::size_t existingArtifactCount = 0;
  std::size_t missingArtifactCount = 0;
  std::uintmax_t totalArtifactBytes = 0;
  std::size_t verifiedArtifactCount = 0;
  std::vector<Diagnostic> diagnostics;
};

struct PackageReleasePublishPlanArtifact {
  std::string name;
  std::filesystem::path packagePath;
  std::string module;
  std::string target;
  std::string packageArtifactPath;
  std::filesystem::path sourcePath;
  std::string destinationPath;
  std::uintmax_t sizeBytes = 0;
  std::string sha256;
};

struct PackageReleasePublishPlanPackage {
  std::filesystem::path packagePath;
  std::string module;
  std::string target;
  std::optional<PackageReleasePromotionSourceHash> sourceHash;
  std::optional<std::string> nativeBinaryStatus;
  std::optional<PackageReleasePackageArtifactRequirements>
      artifactRequirements;
  std::uintmax_t totalArtifactBytes = 0;
  std::vector<PackageReleasePublishPlanArtifact> artifacts;
};

struct PackageReleasePublishPlanResult {
  bool success = false;
  bool releaseEligible = false;
  bool planWritten = false;
  std::filesystem::path bundlePath;
  std::filesystem::path planPath;
  PackageReleaseBundleVerificationResult verification;
  std::uintmax_t totalArtifactBytes = 0;
  std::vector<PackageReleasePublishPlanPackage> packages;
  std::vector<PackageReleasePublishPlanArtifact> artifacts;
  std::vector<Diagnostic> diagnostics;
};

struct PackageReleasePublishStageArtifact {
  PackageReleasePublishPlanArtifact artifact;
  std::filesystem::path stagedPath;
  bool staged = false;
};

struct PackageReleasePublishStageResult {
  bool success = false;
  std::filesystem::path planPath;
  std::filesystem::path stagePath;
  std::size_t packageCount = 0;
  std::size_t artifactCount = 0;
  std::uintmax_t totalArtifactBytes = 0;
  std::size_t stagedArtifactCount = 0;
  std::uintmax_t stagedArtifactBytes = 0;
  std::vector<PackageReleasePublishStageArtifact> artifacts;
  std::vector<Diagnostic> diagnostics;
};

struct PackageReleasePublishReceiptArtifact {
  PackageReleasePublishStageArtifact artifact;
  std::string publishedPath;
  bool planned = false;
  bool published = false;
};

struct PackageReleasePublishUploadRequest {
  std::string targetKind;
  std::filesystem::path stagedPath;
  std::string destinationPath;
  std::string bucket;
  std::string objectName;
  std::string uploadUri;
  std::string credentialsEnv;
  std::uintmax_t sizeBytes = 0;
  std::string sha256;
};

enum class PackageReleasePublishUploadAttemptStatus {
  Uploaded,
  AlreadyPresent,
  Failed,
};

struct PackageReleasePublishUploadAttempt {
  PackageReleasePublishUploadRequest request;
  PackageReleasePublishUploadAttemptStatus status =
      PackageReleasePublishUploadAttemptStatus::Failed;
  std::string provider;
  bool overwrite = false;
  std::string idempotencyKey;
  std::string preconditionKind;
  std::string preconditionValue;
  std::string generation;
  std::string metageneration;
  std::string crc32c;
  std::string md5Hash;
  std::string errorMessage;
};

struct PackageReleasePublishUploadBatchResult {
  bool success = false;
  bool reportWritten = false;
  bool receiptWritten = false;
  std::filesystem::path manifestPath;
  std::filesystem::path reportPath;
  std::filesystem::path receiptPath;
  std::string uploadMode = "custom";
  std::size_t requestCount = 0;
  std::uintmax_t requestBytes = 0;
  std::size_t uploadedArtifactCount = 0;
  std::uintmax_t uploadedArtifactBytes = 0;
  std::vector<PackageReleasePublishUploadAttempt> attempts;
  std::vector<PackageReleasePublishUploadRequest> uploadedRequests;
  std::vector<Diagnostic> diagnostics;
};

struct PackageReleasePublishUploadBatchOptions {
  std::optional<std::filesystem::path> reportPath;
  std::optional<std::filesystem::path> receiptPath;
  std::string uploadMode = "custom";
};

struct PackageReleasePublishUploadPreflightOptions {
  std::optional<std::filesystem::path> reportPath;
};

struct PackageReleasePublishUploadPreflightResult {
  bool success = false;
  bool dryRun = true;
  bool reportWritten = false;
  std::filesystem::path manifestPath;
  std::filesystem::path reportPath;
  std::size_t requestCount = 0;
  std::uintmax_t requestBytes = 0;
  std::size_t validatedRequestCount = 0;
  std::uintmax_t validatedRequestBytes = 0;
  std::vector<PackageReleasePublishUploadRequest> validatedRequests;
  std::vector<Diagnostic> diagnostics;
};

class PackageReleasePublishUploader {
public:
  virtual ~PackageReleasePublishUploader() = default;
  virtual bool uploadPackageReleaseArtifact(
      const PackageReleasePublishUploadRequest &request,
      std::string &errorMessage) = 0;
  virtual PackageReleasePublishUploadAttempt uploadPackageReleaseArtifactDetailed(
      const PackageReleasePublishUploadRequest &request);
};

struct PackageReleasePublishOptions {
  std::string targetKind;
  std::filesystem::path targetPath;
  std::optional<std::filesystem::path> targetDescriptorPath;
  std::optional<std::filesystem::path> receiptPath;
  std::optional<std::filesystem::path> uploadManifestPath;
  bool dryRun = false;
};

struct PackageReleasePublishReceiptResult {
  bool success = false;
  bool receiptWritten = false;
  bool dryRun = false;
  bool targetEnabled = false;
  std::filesystem::path stageReportPath;
  std::filesystem::path targetDescriptorPath;
  std::filesystem::path receiptPath;
  std::string targetKind;
  std::filesystem::path targetPath;
  std::string targetUri;
  std::string targetBucket;
  std::string targetPrefix;
  std::string targetCredentialsEnv;
  std::size_t packageCount = 0;
  std::size_t artifactCount = 0;
  std::uintmax_t totalArtifactBytes = 0;
  std::size_t plannedArtifactCount = 0;
  std::uintmax_t plannedArtifactBytes = 0;
  std::size_t publishedArtifactCount = 0;
  std::uintmax_t publishedArtifactBytes = 0;
  std::vector<PackageReleasePublishReceiptArtifact> artifacts;
  std::vector<PackageReleasePublishUploadRequest> uploadRequests;
  std::vector<Diagnostic> diagnostics;
};

struct PackageReleaseReportArtifactInventoryOptions {
  std::optional<std::filesystem::path> bundlePath;
  std::optional<std::filesystem::path> publishPlanPath;
  std::optional<std::filesystem::path> stageReportPath;
};

struct PackageReleaseReportArtifactInventoryRecord {
  std::string sourceRecordKind;
  std::filesystem::path packagePath;
  std::string packageArtifactPath;
  std::optional<std::filesystem::path> stagedPath;
  std::optional<std::string> destinationPath;
  std::optional<std::uintmax_t> sizeBytes;
  std::optional<std::string> sha256;
};

struct PackageReleaseReportArtifactInventoryResult {
  bool success = false;
  std::optional<std::filesystem::path> bundlePath;
  std::optional<std::filesystem::path> publishPlanPath;
  std::optional<std::filesystem::path> stageReportPath;
  std::size_t artifactRecordCount = 0;
  std::size_t bundleArtifactRecordCount = 0;
  std::size_t publishPlanArtifactRecordCount = 0;
  std::size_t publishStageArtifactRecordCount = 0;
  std::size_t stagedArtifactRecordCount = 0;
  std::uintmax_t totalArtifactRecordBytes = 0;
  std::vector<PackageReleaseReportArtifactInventoryRecord> records;
  std::vector<Diagnostic> diagnostics;
};

enum class PackageRecoveryAction {
  Promote,
  Discard,
};

struct PackageRecoveryOptions {
  PackageRecoveryAction action = PackageRecoveryAction::Promote;
  bool replace = false;
  std::optional<std::filesystem::path> sourcePath;
};

struct PackageRecoveryResult {
  bool success = false;
  std::filesystem::path sidecarPath;
  std::filesystem::path requestedPath;
  std::optional<std::filesystem::path> backupPath;
  std::string message;
  std::vector<Diagnostic> diagnostics;
};

std::filesystem::path packageParentPath(const std::filesystem::path &path);
std::string packageSidecarPrefix(const std::filesystem::path &path);
std::string packageSidecarToken();

std::optional<std::filesystem::path> availablePackageSidecarPath(
    const std::filesystem::path &finalPath, std::string_view label,
    std::string_view diagnosticCode, DiagnosticEngine &diagnostics);

std::optional<PackageSidecarRecord>
parsePackageSidecarPath(const std::filesystem::path &path);

PackagePublicationInfo
collectPackagePublicationInfo(const std::filesystem::path &packagePath);

PackageSidecarListResult
listPackageSidecars(const std::filesystem::path &packagePath);

std::string packageSidecarListJson(const PackageSidecarListResult &result);
std::string packageSidecarListText(const PackageSidecarListResult &result);

PackageStaleSidecarCleanupResult
cleanupStalePackageSidecars(const std::filesystem::path &packagePath,
                            const PackageStaleSidecarCleanupOptions &options);

PackageMaintenancePolicyResult
loadPackageMaintenancePolicy(const std::filesystem::path &policyPath);

PackageMaintenanceSetLoadResult
loadPackageMaintenanceSet(const std::filesystem::path &setPath);

PackageMaintenanceSetVerificationBatchLoadResult
loadPackageMaintenanceSetVerificationBatch(
    const std::filesystem::path &batchPath);

PackageMaintenanceScanResult scanPackageMaintenanceDirectory(
    const std::filesystem::path &rootPath,
    const PackageStaleSidecarCleanupOptions &options);

PackageMaintenanceSetResult
maintainPackageSet(const std::filesystem::path &setPath,
                   const PackageStaleSidecarCleanupOptions &options);

PackageMaintenanceSetExportResult
exportPackageMaintenanceSetFromScan(const std::filesystem::path &rootPath,
                                    const std::filesystem::path &setPath);

PackageMaintenanceSetVerificationResult
verifyPackageMaintenanceSetFromScan(const std::filesystem::path &rootPath,
                                    const std::filesystem::path &setPath);

PackageMaintenanceSetVerificationBatchResult
verifyPackageMaintenanceSetsFromBatch(const std::filesystem::path &batchPath);

PackageMaintenanceSetVerificationBatchExportResult
exportPackageMaintenanceSetVerificationBatch(
    const std::filesystem::path &batchPath,
    const std::vector<PackageMaintenanceSetVerificationBatchEntry> &entries);
PackageMaintenanceSetVerificationBatchSummaryExportResult
exportPackageMaintenanceSetVerificationBatchSummary(
    const PackageMaintenanceSetVerificationBatchResult &result,
    const std::filesystem::path &summaryPath);
PackageReleasePromotionManifestResult exportPackageReleasePromotionManifest(
    const std::filesystem::path &summaryPath,
    const std::filesystem::path &manifestPath);
PackageReleaseBundleManifestResult exportPackageReleaseBundleManifest(
    const PackageReleasePromotionManifestResult &promotion,
    const std::filesystem::path &bundlePath);
PackageReleaseBundleVerificationResult
verifyPackageReleaseBundleManifest(const std::filesystem::path &bundlePath);
PackageReleasePublishPlanResult
exportPackageReleasePublishPlan(const std::filesystem::path &bundlePath,
                                const std::filesystem::path &planPath);
PackageReleasePublishStageResult
stagePackageReleasePublishPlan(const std::filesystem::path &planPath,
                               const std::filesystem::path &stagePath);
PackageReleasePublishReceiptResult
publishPackageReleaseStage(const std::filesystem::path &stageReportPath,
                           const PackageReleasePublishOptions &options);
PackageReleasePublishUploadBatchResult uploadPackageReleaseArtifacts(
    const std::vector<PackageReleasePublishUploadRequest> &requests,
    PackageReleasePublishUploader &uploader);
PackageReleasePublishUploadBatchResult uploadPackageReleaseManifest(
    const std::filesystem::path &manifestPath,
    const PackageReleasePublishUploadBatchOptions &options,
    PackageReleasePublishUploader &uploader);
PackageReleasePublishUploadPreflightResult
preflightPackageReleaseUploadManifest(
    const std::filesystem::path &manifestPath,
    const PackageReleasePublishUploadPreflightOptions &options);
PackageReleaseReportArtifactInventoryResult
loadPackageReleaseReportArtifactInventory(
    const PackageReleaseReportArtifactInventoryOptions &options);

std::string
packageStaleSidecarCleanupJson(const PackageStaleSidecarCleanupResult &result);
std::string
packageStaleSidecarCleanupText(const PackageStaleSidecarCleanupResult &result);

std::string
packageMaintenanceScanJson(const PackageMaintenanceScanResult &result);
std::string
packageMaintenanceScanText(const PackageMaintenanceScanResult &result);

std::string
packageMaintenanceSetJson(const PackageMaintenanceSetResult &result);
std::string
packageMaintenanceSetText(const PackageMaintenanceSetResult &result);

std::string packageMaintenanceSetDocumentJson(
    const std::vector<std::filesystem::path> &packagePaths,
    const std::filesystem::path &basePath);
std::string packageMaintenanceSetVerificationBatchDocumentJson(
    const std::vector<PackageMaintenanceSetVerificationBatchEntry> &entries,
    const std::filesystem::path &basePath);
std::string packageMaintenanceSetExportText(
    const PackageMaintenanceSetExportResult &result);
std::string packageMaintenanceSetVerificationBatchExportText(
    const PackageMaintenanceSetVerificationBatchExportResult &result);
std::string packageMaintenanceSetVerificationBatchSummaryJson(
    const PackageMaintenanceSetVerificationBatchResult &result);
std::string packageMaintenanceSetVerificationBatchSummaryExportText(
    const PackageMaintenanceSetVerificationBatchSummaryExportResult &result);
std::string packageReleasePromotionManifestJson(
    const PackageReleasePromotionManifestResult &result);
std::string packageReleasePromotionManifestText(
    const PackageReleasePromotionManifestResult &result);
std::string packageReleaseBundleManifestJson(
    const PackageReleaseBundleManifestResult &result);
std::string packageReleaseBundleManifestText(
    const PackageReleaseBundleManifestResult &result);
std::string packageReleaseBundleVerificationJson(
    const PackageReleaseBundleVerificationResult &result);
std::string packageReleaseBundleVerificationText(
    const PackageReleaseBundleVerificationResult &result);
std::string
packageReleasePublishPlanJson(const PackageReleasePublishPlanResult &result);
std::string
packageReleasePublishPlanText(const PackageReleasePublishPlanResult &result);
std::string
packageReleasePublishStageJson(const PackageReleasePublishStageResult &result);
std::string
packageReleasePublishStageText(const PackageReleasePublishStageResult &result);
std::string packageReleaseReportArtifactInventoryJson(
    const PackageReleaseReportArtifactInventoryResult &result);
std::string packageReleaseReportArtifactInventoryText(
    const PackageReleaseReportArtifactInventoryResult &result);
std::string packageReleasePublishReceiptJson(
    const PackageReleasePublishReceiptResult &result);
std::string packageReleasePublishReceiptText(
    const PackageReleasePublishReceiptResult &result);
std::string packageReleasePublishUploadManifestJson(
    const std::vector<PackageReleasePublishUploadRequest> &requests);
std::string packageReleasePublishUploadBatchJson(
    const PackageReleasePublishUploadBatchResult &result);
std::string packageReleasePublishUploadReceiptJson(
    const PackageReleasePublishUploadBatchResult &result);
std::string packageReleasePublishUploadBatchText(
    const PackageReleasePublishUploadBatchResult &result);
std::string packageReleasePublishUploadPreflightJson(
    const PackageReleasePublishUploadPreflightResult &result);
std::string packageReleasePublishUploadPreflightText(
    const PackageReleasePublishUploadPreflightResult &result);
std::string packageMaintenanceSetVerificationJson(
    const PackageMaintenanceSetVerificationResult &result);
std::string packageMaintenanceSetVerificationText(
    const PackageMaintenanceSetVerificationResult &result);
std::string packageMaintenanceSetVerificationBatchJson(
    const PackageMaintenanceSetVerificationBatchResult &result);
std::string packageMaintenanceSetVerificationBatchText(
    const PackageMaintenanceSetVerificationBatchResult &result);

PackageRecoveryResult
recoverPackageSidecar(const std::filesystem::path &sidecarPath,
                      const PackageRecoveryOptions &options);

std::string packageRecoveryJson(const PackageRecoveryResult &result,
                                const PackageRecoveryOptions &options);

} // namespace crossgl
