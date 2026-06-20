#pragma once

#include <cstddef>
#include <optional>
#include <set>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace crossgl {

class DiagnosticEngine;
struct HIRConstant;
struct HIRExpression;
enum class HIRResourceKind;
struct HIRResource;
struct HIRModule;
struct HIRType;

enum class RuntimeDescriptorArrayPolicy {
  RejectAll,
  AllowSingleUnboundedDescriptorArray,
};

bool supportedResourceArraySize(const HIRType &type);
std::optional<std::size_t> staticResourceArrayIndexValue(
    const HIRExpression &expression,
    const std::vector<HIRConstant> *constants = nullptr);
std::string resourceArraySuffix(const HIRType &type);
bool isRuntimeDescriptorArray(const HIRResource &resource);
std::string resourceArrayLabel(const HIRResource &resource);
std::string runtimeDescriptorArrayPolicyName(
    RuntimeDescriptorArrayPolicy policy);
std::set<std::string> runtimeDescriptorArrayLabels(const HIRModule &module);
std::set<std::string>
runtimeDescriptorArrayLabels(const HIRModule &module,
                             std::span<const HIRResourceKind> resourceKinds);
bool runtimeDescriptorArraySupportedByPolicy(
    const HIRModule &module, const HIRResource &resource,
    RuntimeDescriptorArrayPolicy policy);
bool runtimeDescriptorArraySupportedByPolicy(
    const HIRModule &module, const HIRResource &resource,
    RuntimeDescriptorArrayPolicy policy,
    std::span<const HIRResourceKind> resourceKinds);
bool runtimeDescriptorArraysSupportedByPolicy(
    const HIRModule &module, RuntimeDescriptorArrayPolicy policy,
    std::span<const HIRResourceKind> resourceKinds);
std::set<std::string> unsupportedStorageBufferArrayNames(
    const HIRModule &module);
bool hasUnsupportedStorageBufferArray(const HIRModule &module);
bool diagnoseUnsupportedStorageBufferArray(const HIRModule &module,
                                           DiagnosticEngine &diagnostics,
                                           std::string_view diagnosticCode,
                                           std::string_view targetName);
std::string resourceKindLabel(HIRResourceKind kind);
std::set<std::string> unsupportedRuntimeResourceArrayLabels(
    const HIRModule &module);
bool hasUnsupportedRuntimeResourceArray(const HIRModule &module);
bool diagnoseUnsupportedRuntimeResourceArray(const HIRModule &module,
                                             DiagnosticEngine &diagnostics,
                                             std::string_view diagnosticCode,
                                             std::string_view targetName);
std::string joinNames(const std::set<std::string> &names);

} // namespace crossgl
