#include "crossgl/Backend/ResourceArrays.h"

#include "crossgl/Basic/Diagnostic.h"
#include "crossgl/HIR/HIR.h"

#include <algorithm>
#include <sstream>

namespace crossgl {

bool supportedResourceArraySize(const HIRType &type) {
  return !type.arraySize.has_value() || !type.arraySize->empty();
}

std::optional<std::size_t>
parseStaticResourceArrayIndex(std::string_view text) {
  if (!text.empty() && (text.back() == 'u' || text.back() == 'U')) {
    text.remove_suffix(1);
  }
  if (text.empty()) {
    return std::nullopt;
  }

  std::size_t value = 0;
  for (const char character : text) {
    if (character < '0' || character > '9') {
      return std::nullopt;
    }
    value = value * 10 + static_cast<std::size_t>(character - '0');
  }
  return value;
}

std::optional<std::size_t> staticResourceArrayIndexValue(
    const HIRExpression &expression,
    const std::vector<HIRConstant> *constants) {
  if ((expression.kind == HIRExpressionKind::Group ||
       (expression.kind == HIRExpressionKind::Unary &&
        expression.value == "+")) &&
      expression.children.size() == 1) {
    return staticResourceArrayIndexValue(expression.children.front(),
                                         constants);
  }
  if (expression.kind == HIRExpressionKind::Literal) {
    return parseStaticResourceArrayIndex(expression.value);
  }
  if (expression.kind == HIRExpressionKind::Identifier &&
      constants != nullptr) {
    for (const HIRConstant &constant : *constants) {
      if (constant.name == expression.value &&
          constant.foldedValue.has_value() &&
          !constant.type.arraySize.has_value() &&
          (constant.type.name == "int" || constant.type.name == "uint")) {
        return parseStaticResourceArrayIndex(*constant.foldedValue);
      }
    }
  }
  return std::nullopt;
}

std::string resourceArraySuffix(const HIRType &type) {
  if (!type.arraySize.has_value()) {
    return "";
  }
  return "[" + *type.arraySize + "]";
}

bool isRuntimeDescriptorArray(const HIRResource &resource) {
  return resource.type.arraySize.has_value() && resource.type.arraySize->empty();
}

std::string resourceArrayLabel(const HIRResource &resource) {
  return resource.name + " (" + resourceKindLabel(resource.kind) + ")";
}

std::string runtimeDescriptorArrayPolicyName(
    RuntimeDescriptorArrayPolicy policy) {
  switch (policy) {
  case RuntimeDescriptorArrayPolicy::RejectAll:
    return "reject-all";
  case RuntimeDescriptorArrayPolicy::AllowSingleUnboundedDescriptorArray:
    return "allow-single-unbounded-descriptor-array";
  }
  return "unknown";
}

bool runtimeDescriptorArrayKindMatches(
    HIRResourceKind kind, std::span<const HIRResourceKind> resourceKinds) {
  return resourceKinds.empty() ||
         std::find(resourceKinds.begin(), resourceKinds.end(), kind) !=
             resourceKinds.end();
}

std::set<std::string> runtimeDescriptorArrayLabels(const HIRModule &module) {
  return runtimeDescriptorArrayLabels(module, {});
}

std::set<std::string>
runtimeDescriptorArrayLabels(const HIRModule &module,
                             std::span<const HIRResourceKind> resourceKinds) {
  std::set<std::string> labels;
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (isRuntimeDescriptorArray(resource) &&
          runtimeDescriptorArrayKindMatches(resource.kind, resourceKinds)) {
        labels.insert(resourceArrayLabel(resource));
      }
    }
  }
  return labels;
}

bool runtimeDescriptorArraySupportedByPolicy(
    const HIRModule &module, const HIRResource &resource,
    RuntimeDescriptorArrayPolicy policy) {
  return runtimeDescriptorArraySupportedByPolicy(module, resource, policy, {});
}

bool runtimeDescriptorArraySupportedByPolicy(
    const HIRModule &module, const HIRResource &resource,
    RuntimeDescriptorArrayPolicy policy,
    std::span<const HIRResourceKind> resourceKinds) {
  if (!isRuntimeDescriptorArray(resource)) {
    return true;
  }
  if (!runtimeDescriptorArrayKindMatches(resource.kind, resourceKinds)) {
    return false;
  }

  switch (policy) {
  case RuntimeDescriptorArrayPolicy::RejectAll:
    return false;
  case RuntimeDescriptorArrayPolicy::AllowSingleUnboundedDescriptorArray:
    return runtimeDescriptorArrayLabels(module, resourceKinds).size() == 1;
  }
  return false;
}

bool runtimeDescriptorArraysSupportedByPolicy(
    const HIRModule &module, RuntimeDescriptorArrayPolicy policy,
    std::span<const HIRResourceKind> resourceKinds) {
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (isRuntimeDescriptorArray(resource) &&
          runtimeDescriptorArrayKindMatches(resource.kind, resourceKinds) &&
          !runtimeDescriptorArraySupportedByPolicy(module, resource, policy,
                                                   resourceKinds)) {
        return false;
      }
    }
  }
  return true;
}

std::set<std::string>
unsupportedStorageBufferArrayNames(const HIRModule &module) {
  std::set<std::string> bufferArrays;
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind == HIRResourceKind::Buffer &&
          isRuntimeDescriptorArray(resource)) {
        bufferArrays.insert(resource.name);
      }
    }
  }
  return bufferArrays;
}

bool hasUnsupportedStorageBufferArray(const HIRModule &module) {
  return !unsupportedStorageBufferArrayNames(module).empty();
}

bool diagnoseUnsupportedStorageBufferArray(const HIRModule &module,
                                           DiagnosticEngine &diagnostics,
                                           std::string_view diagnosticCode,
                                           std::string_view targetName) {
  const std::set<std::string> bufferArrays =
      unsupportedStorageBufferArrayNames(module);
  if (bufferArrays.empty()) {
    return false;
  }
  diagnostics.error(
      std::string(diagnosticCode),
      std::string(targetName) +
          " source package requires fixed-size storage-buffer descriptor "
          "array(s); unsupported unsized array(s): " +
          joinNames(bufferArrays) + "; use a fixed descriptor array size");
  return true;
}

std::string resourceKindLabel(HIRResourceKind kind) {
  switch (kind) {
  case HIRResourceKind::Uniform:
    return "uniform";
  case HIRResourceKind::Buffer:
    return "storage-buffer";
  case HIRResourceKind::Texture:
    return "texture";
  case HIRResourceKind::StorageImage:
    return "storage-image";
  case HIRResourceKind::Sampler:
    return "sampler";
  case HIRResourceKind::Shared:
    return "shared";
  case HIRResourceKind::Value:
    return "value";
  }
  return "resource";
}

std::set<std::string>
unsupportedRuntimeResourceArrayLabels(const HIRModule &module) {
  std::set<std::string> resourceArrays;
  for (const HIRStage &stage : module.stages) {
    for (const HIRResource &resource : stage.resources) {
      if (resource.kind != HIRResourceKind::Buffer &&
          isRuntimeDescriptorArray(resource)) {
        resourceArrays.insert(resourceArrayLabel(resource));
      }
    }
  }
  return resourceArrays;
}

bool hasUnsupportedRuntimeResourceArray(const HIRModule &module) {
  return !unsupportedRuntimeResourceArrayLabels(module).empty();
}

bool diagnoseUnsupportedRuntimeResourceArray(const HIRModule &module,
                                             DiagnosticEngine &diagnostics,
                                             std::string_view diagnosticCode,
                                             std::string_view targetName) {
  const std::set<std::string> resourceArrays =
      unsupportedRuntimeResourceArrayLabels(module);
  if (resourceArrays.empty()) {
    return false;
  }
  diagnostics.error(
      std::string(diagnosticCode),
      std::string(targetName) +
          " source package requires fixed-size descriptor arrays; unsupported "
          "unsized/runtime resource array(s): " +
          joinNames(resourceArrays) + "; use a fixed descriptor array size");
  return true;
}

std::string joinNames(const std::set<std::string> &names) {
  std::ostringstream out;
  bool first = true;
  for (const std::string &name : names) {
    if (!first) {
      out << ", ";
    }
    first = false;
    out << name;
  }
  return out.str();
}

} // namespace crossgl
