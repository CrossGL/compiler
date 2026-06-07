#include "crossgl/Driver/DebugMetadata.h"

#include "crossgl/Backend/TargetCapabilities.h"
#include "crossgl/Backend/TargetLegalization.h"
#include "crossgl/Basic/Json.h"

#include <algorithm>
#include <map>
#include <set>
#include <sstream>
#include <string_view>
#include <utility>

namespace crossgl {
namespace {

void appendIndexArray(std::ostringstream &out, std::string_view name,
                      const std::vector<std::size_t> &indexes,
                      bool trailingComma) {
  out << "    \"" << name << "\": [";
  for (std::size_t i = 0; i < indexes.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    out << indexes[i];
  }
  out << "]";
  if (trailingComma) {
    out << ",";
  }
  out << "\n";
}

void appendInlineStringArray(std::ostringstream &out,
                             const std::vector<std::string> &values) {
  out << "[";
  for (std::size_t i = 0; i < values.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    out << "\"" << escapeJson(values[i]) << "\"";
  }
  out << "]";
}

bool sourceLocationAvailable(const SourceLocation &location) {
  return !location.file.empty();
}

DebugMetadataSourceLocation
debugSourceLocation(const SourceLocation &location) {
  return DebugMetadataSourceLocation{location.file, location.line,
                                     location.column, location.offset,
                                     location.length, location.endLine,
                                     location.endColumn, location.endOffset};
}

void appendSourceLocation(std::ostringstream &out,
                          const DebugMetadataSourceLocation &location) {
  out << "{\"file\":\"" << escapeJson(location.file) << "\""
      << ",\"line\":" << location.line << ",\"column\":" << location.column
      << ",\"offset\":" << location.offset << ",\"length\":"
      << location.length << ",\"endLine\":" << location.endLine
      << ",\"endColumn\":" << location.endColumn
      << ",\"endOffset\":" << location.endOffset << "}";
}

void appendOriginalSourceLocation(
    std::ostringstream &out,
    const std::optional<DebugMetadataSourceLocation> &location) {
  if (!location) {
    return;
  }
  out << ",\"originalLocation\":";
  appendSourceLocation(out, *location);
}

SourceLocation sourceLocationFromDebug(
    const DebugMetadataSourceLocation &location) {
  return SourceLocation{location.file,      location.line,
                        location.column,    location.offset,
                        location.length,    location.endLine,
                        location.endColumn, location.endOffset};
}

DebugMetadataSourceLocation
debugSourceLocationFromBasic(const SourceLocation &location) {
  return DebugMetadataSourceLocation{location.file, location.line,
                                     location.column, location.offset,
                                     location.length, location.endLine,
                                     location.endColumn, location.endOffset};
}

std::optional<DebugMetadataSourceLocation>
remappedDebugSourceLocation(const SourceRemap &remap,
                            const DebugMetadataSourceLocation &location) {
  std::optional<SourceLocation> remapped =
      remapSourceLocation(remap, sourceLocationFromDebug(location));
  if (!remapped) {
    return std::nullopt;
  }
  return debugSourceLocationFromBasic(*remapped);
}

void applySourceRemap(DebugMetadataHIRSourceLocations &locations,
                      const SourceRemap &remap) {
  for (DebugMetadataHIRExpressionSourceLocation &expression :
       locations.expressions) {
    expression.originalLocation =
        remappedDebugSourceLocation(remap, expression.location);
  }
  for (DebugMetadataHIRTypeSourceLocation &type : locations.types) {
    type.originalLocation = remappedDebugSourceLocation(remap, type.location);
  }
  for (DebugMetadataHIRStatementSourceLocation &statement :
       locations.statements) {
    statement.originalLocation =
        remappedDebugSourceLocation(remap, statement.location);
  }
  for (DebugMetadataHIRResourceSourceLocation &resource :
       locations.resources) {
    resource.originalLocation =
        remappedDebugSourceLocation(remap, resource.location);
  }
}

std::string capabilityKindFromId(std::string_view capabilityId) {
  const std::size_t targetSeparator = capabilityId.find('.');
  if (targetSeparator == std::string_view::npos) {
    return "unknown";
  }
  const std::size_t kindSeparator = capabilityId.find('.', targetSeparator + 1);
  if (kindSeparator == std::string_view::npos ||
      kindSeparator == targetSeparator + 1) {
    return "unknown";
  }
  return std::string(capabilityId.substr(
      targetSeparator + 1, kindSeparator - targetSeparator - 1));
}

std::vector<DebugMetadataTargetCapabilityGroup>
capabilityGroupsFromIds(const std::vector<std::string> &capabilities) {
  std::vector<DebugMetadataTargetCapabilityGroup> groups;
  for (const std::string &capability : capabilities) {
    DebugMetadataTargetCapabilityGroup *group = nullptr;
    const std::string kind = capabilityKindFromId(capability);
    for (DebugMetadataTargetCapabilityGroup &candidate : groups) {
      if (candidate.kind == kind) {
        group = &candidate;
        break;
      }
    }
    if (group == nullptr) {
      DebugMetadataTargetCapabilityGroup newGroup;
      newGroup.kind = kind;
      groups.push_back(std::move(newGroup));
      group = &groups.back();
    }
    group->capabilities.push_back(capability);
    group->count = group->capabilities.size();
  }
  return groups;
}

void appendCapabilityGroups(
    std::ostringstream &out,
    const std::vector<DebugMetadataTargetCapabilityGroup> &groups) {
  out << "[";
  for (std::size_t i = 0; i < groups.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const DebugMetadataTargetCapabilityGroup &group = groups[i];
    out << "{\"kind\":\"" << escapeJson(group.kind) << "\",\"count\":"
        << group.count << ",\"capabilities\":";
    appendInlineStringArray(out, group.capabilities);
    out << "}";
  }
  out << "]";
}

void appendTargetDecisionDiagnostics(
    std::ostringstream &out,
    const std::vector<DebugMetadataTargetDecisionDiagnostic> &diagnostics) {
  out << "[";
  for (std::size_t i = 0; i < diagnostics.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const DebugMetadataTargetDecisionDiagnostic &diagnostic = diagnostics[i];
    out << "{\"code\":\"" << escapeJson(diagnostic.code) << "\""
        << ",\"severity\":\"" << escapeJson(diagnostic.severity) << "\""
        << ",\"target\":\"" << escapeJson(diagnostic.target) << "\""
        << ",\"message\":\"" << escapeJson(diagnostic.message) << "\""
        << ",\"capabilities\":";
    appendInlineStringArray(out, diagnostic.capabilities);
    out << ",\"legalizationCoreEvidenceIds\":";
    appendInlineStringArray(out, diagnostic.legalizationCoreEvidenceIds);
    out << ",\"capabilityGroups\":";
    appendCapabilityGroups(out, diagnostic.capabilityGroups);
    out << "}";
  }
  out << "]";
}

void appendFallbackTargetRecords(
    std::ostringstream &out,
    const std::vector<DebugMetadataTargetFallback> &fallbacks) {
  out << "[";
  for (std::size_t i = 0; i < fallbacks.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const DebugMetadataTargetFallback &fallback = fallbacks[i];
    out << "{\"rank\":" << fallback.rank << ",\"target\":\""
        << escapeJson(fallback.target) << "\""
        << ",\"packageMode\":\"" << escapeJson(fallback.packageMode) << "\""
        << ",\"rankReason\":\"" << escapeJson(fallback.rankReason) << "\""
        << ",\"nativeImplemented\":"
        << (fallback.nativeImplemented ? "true" : "false")
        << ",\"sourcePackageSupported\":"
        << (fallback.sourcePackageSupported ? "true" : "false")
        << ",\"packageBuildSupported\":"
        << (fallback.packageBuildSupported ? "true" : "false")
        << ",\"missingCapabilityCount\":"
        << fallback.missingCapabilityCount << ",\"missingCapabilities\":";
    appendInlineStringArray(out, fallback.missingCapabilities);
    out << ",\"legalizationCoreEvidenceIds\":";
    appendInlineStringArray(out, fallback.legalizationCoreEvidenceIds);
    out << ",\"requiredToolCount\":" << fallback.requiredToolCount
        << ",\"missingToolCount\":" << fallback.missingToolCount
        << ",\"requiredToolIds\":";
    appendInlineStringArray(out, fallback.requiredToolIds);
    out << ",\"missingToolIds\":";
    appendInlineStringArray(out, fallback.missingToolIds);
    out << ",\"optionalNativeToolMissing\":"
        << (fallback.optionalNativeToolMissing ? "true" : "false")
        << ",\"optionalNativeToolStatus\":\""
        << escapeJson(fallback.optionalNativeToolStatus) << "\""
        << ",\"toolRequirementEvidenceIds\":";
    appendInlineStringArray(out, fallback.toolRequirementEvidenceIds);
    out << ",\"missingCapabilityGroups\":";
    appendCapabilityGroups(out, fallback.missingCapabilityGroups);
    out << "}";
  }
  out << "]";
}

void appendHIRExpressionSourceLocation(
    std::ostringstream &out,
    const DebugMetadataHIRExpressionSourceLocation &expression);
void appendHIRTypeSourceLocation(
    std::ostringstream &out, const DebugMetadataHIRTypeSourceLocation &type);
void appendHIRStatementSourceLocation(
    std::ostringstream &out,
    const DebugMetadataHIRStatementSourceLocation &statement);
void appendHIRResourceSourceLocation(
    std::ostringstream &out,
    const DebugMetadataHIRResourceSourceLocation &resource);

bool hirSourceMapIncludesResources(int schemaVersion) {
  return schemaVersion >= 8;
}

void appendHIRExpressionSourceLocations(
    std::ostringstream &out,
    const std::vector<DebugMetadataHIRExpressionSourceLocation> &expressions) {
  out << "[";
  for (std::size_t i = 0; i < expressions.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const DebugMetadataHIRExpressionSourceLocation &expression = expressions[i];
    appendHIRExpressionSourceLocation(out, expression);
  }
  out << "]";
}

void appendHIRExpressionSourceLocation(
    std::ostringstream &out,
    const DebugMetadataHIRExpressionSourceLocation &expression) {
  out << "{\"index\":" << expression.index << ",\"stage\":\""
      << escapeJson(expression.stage) << "\""
      << ",\"entryPoint\":\"" << escapeJson(expression.entryPoint) << "\""
      << ",\"function\":\"" << escapeJson(expression.function) << "\""
      << ",\"statementKind\":\"" << escapeJson(expression.statementKind)
      << "\""
      << ",\"kind\":\"" << escapeJson(expression.kind) << "\""
      << ",\"value\":\"" << escapeJson(expression.value) << "\""
      << ",\"type\":\"" << escapeJson(expression.type) << "\""
      << ",\"location\":";
  appendSourceLocation(out, expression.location);
  appendOriginalSourceLocation(out, expression.originalLocation);
  out << "}";
}

void appendHIRTypeSourceLocations(
    std::ostringstream &out,
    const std::vector<DebugMetadataHIRTypeSourceLocation> &types) {
  out << "[";
  for (std::size_t i = 0; i < types.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const DebugMetadataHIRTypeSourceLocation &type = types[i];
    appendHIRTypeSourceLocation(out, type);
  }
  out << "]";
}

void appendHIRTypeSourceLocation(
    std::ostringstream &out, const DebugMetadataHIRTypeSourceLocation &type) {
  out << "{\"index\":" << type.index << ",\"stage\":\""
      << escapeJson(type.stage) << "\""
      << ",\"entryPoint\":\"" << escapeJson(type.entryPoint) << "\""
      << ",\"function\":\"" << escapeJson(type.function) << "\""
      << ",\"ownerKind\":\"" << escapeJson(type.ownerKind) << "\""
      << ",\"ownerName\":\"" << escapeJson(type.ownerName) << "\""
      << ",\"type\":\"" << escapeJson(type.type) << "\""
      << ",\"location\":";
  appendSourceLocation(out, type.location);
  appendOriginalSourceLocation(out, type.originalLocation);
  out << "}";
}

void appendHIRStatementSourceLocations(
    std::ostringstream &out,
    const std::vector<DebugMetadataHIRStatementSourceLocation> &statements) {
  out << "[";
  for (std::size_t i = 0; i < statements.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const DebugMetadataHIRStatementSourceLocation &statement = statements[i];
    appendHIRStatementSourceLocation(out, statement);
  }
  out << "]";
}

void appendHIRStatementSourceLocation(
    std::ostringstream &out,
    const DebugMetadataHIRStatementSourceLocation &statement) {
  out << "{\"index\":" << statement.index << ",\"stage\":\""
      << escapeJson(statement.stage) << "\""
      << ",\"entryPoint\":\"" << escapeJson(statement.entryPoint) << "\""
      << ",\"function\":\"" << escapeJson(statement.function) << "\""
      << ",\"statementKind\":\"" << escapeJson(statement.statementKind) << "\""
      << ",\"name\":\"" << escapeJson(statement.name) << "\""
      << ",\"location\":";
  appendSourceLocation(out, statement.location);
  appendOriginalSourceLocation(out, statement.originalLocation);
  out << "}";
}

void appendHIRResourceSourceLocations(
    std::ostringstream &out,
    const std::vector<DebugMetadataHIRResourceSourceLocation> &resources) {
  out << "[";
  for (std::size_t i = 0; i < resources.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    const DebugMetadataHIRResourceSourceLocation &resource = resources[i];
    appendHIRResourceSourceLocation(out, resource);
  }
  out << "]";
}

void appendHIRResourceSourceLocation(
    std::ostringstream &out,
    const DebugMetadataHIRResourceSourceLocation &resource) {
  out << "{\"index\":" << resource.index << ",\"resourceRecordKind\":\""
      << escapeJson(resource.resourceRecordKind) << "\""
      << ",\"stage\":\"" << escapeJson(resource.stage) << "\""
      << ",\"entryPoint\":\"" << escapeJson(resource.entryPoint) << "\""
      << ",\"resourceName\":\"" << escapeJson(resource.resourceName) << "\""
      << ",\"resourceKind\":\"" << escapeJson(resource.resourceKind) << "\""
      << ",\"type\":\"" << escapeJson(resource.type) << "\"";
  if (resource.bindingSet) {
    out << ",\"bindingSet\":" << *resource.bindingSet;
  }
  if (resource.binding) {
    out << ",\"binding\":" << *resource.binding;
  }
  out << ",\"location\":";
  appendSourceLocation(out, resource.location);
  appendOriginalSourceLocation(out, resource.originalLocation);
  out << "}";
}

bool hasFilter(const std::optional<std::string> &filter) {
  return filter.has_value();
}

bool sourceMapFilterEmpty(const DebugMetadataHIRSourceMapFilter &filters) {
  return !filters.stage && !filters.entryPoint && !filters.function &&
         !filters.statementKind && !filters.expressionKind &&
         !filters.expressionValue && !filters.ownerKind && !filters.ownerName &&
         !filters.resourceRecordKind && !filters.resourceName &&
         !filters.resourceKind;
}

std::size_t
sourceMapFilterActiveCount(const DebugMetadataHIRSourceMapFilter &filters,
                           bool includeResources) {
  std::size_t count = 0;
  count += hasFilter(filters.stage) ? 1 : 0;
  count += hasFilter(filters.entryPoint) ? 1 : 0;
  count += hasFilter(filters.function) ? 1 : 0;
  count += hasFilter(filters.statementKind) ? 1 : 0;
  count += hasFilter(filters.expressionKind) ? 1 : 0;
  count += hasFilter(filters.expressionValue) ? 1 : 0;
  count += hasFilter(filters.ownerKind) ? 1 : 0;
  count += hasFilter(filters.ownerName) ? 1 : 0;
  if (includeResources) {
    count += hasFilter(filters.resourceRecordKind) ? 1 : 0;
    count += hasFilter(filters.resourceName) ? 1 : 0;
    count += hasFilter(filters.resourceKind) ? 1 : 0;
  }
  return count;
}

bool matchesFilter(const std::optional<std::string> &filter,
                   std::string_view value) {
  return !filter || value == *filter;
}

bool expressionMatchesFilter(
    const DebugMetadataHIRExpressionSourceLocation &expression,
    const DebugMetadataHIRSourceMapFilter &filters) {
  if (filters.ownerKind || filters.ownerName || filters.resourceRecordKind ||
      filters.resourceName || filters.resourceKind) {
    return false;
  }
  return matchesFilter(filters.stage, expression.stage) &&
         matchesFilter(filters.entryPoint, expression.entryPoint) &&
         matchesFilter(filters.function, expression.function) &&
         matchesFilter(filters.statementKind, expression.statementKind) &&
         matchesFilter(filters.expressionKind, expression.kind) &&
         matchesFilter(filters.expressionValue, expression.value);
}

bool typeMatchesFilter(const DebugMetadataHIRTypeSourceLocation &type,
                       const DebugMetadataHIRSourceMapFilter &filters) {
  if (filters.statementKind || filters.expressionKind ||
      filters.expressionValue || filters.resourceRecordKind ||
      filters.resourceName || filters.resourceKind) {
    return false;
  }
  return matchesFilter(filters.stage, type.stage) &&
         matchesFilter(filters.entryPoint, type.entryPoint) &&
         matchesFilter(filters.function, type.function) &&
         matchesFilter(filters.ownerKind, type.ownerKind) &&
         matchesFilter(filters.ownerName, type.ownerName);
}

bool statementMatchesFilter(
    const DebugMetadataHIRStatementSourceLocation &statement,
    const DebugMetadataHIRSourceMapFilter &filters) {
  if (filters.expressionKind || filters.expressionValue || filters.ownerKind ||
      filters.ownerName || filters.resourceRecordKind || filters.resourceName ||
      filters.resourceKind) {
    return false;
  }
  return matchesFilter(filters.stage, statement.stage) &&
         matchesFilter(filters.entryPoint, statement.entryPoint) &&
         matchesFilter(filters.function, statement.function) &&
         matchesFilter(filters.statementKind, statement.statementKind);
}

bool resourceMatchesFilter(const DebugMetadataHIRResourceSourceLocation &resource,
                           const DebugMetadataHIRSourceMapFilter &filters) {
  if (filters.function || filters.statementKind || filters.expressionKind ||
      filters.expressionValue || filters.ownerKind || filters.ownerName) {
    return false;
  }
  return matchesFilter(filters.stage, resource.stage) &&
         matchesFilter(filters.entryPoint, resource.entryPoint) &&
         matchesFilter(filters.resourceRecordKind, resource.resourceRecordKind) &&
         matchesFilter(filters.resourceName, resource.resourceName) &&
         matchesFilter(filters.resourceKind, resource.resourceKind);
}

DebugMetadataHIRSourceLocations filterHIRSourceLocations(
    const DebugMetadataHIRSourceLocations &locations,
    const DebugMetadataHIRSourceMapFilter &filters) {
  if (sourceMapFilterEmpty(filters)) {
    return locations;
  }

  DebugMetadataHIRSourceLocations filtered;
  for (const DebugMetadataHIRExpressionSourceLocation &expression :
       locations.expressions) {
    if (expressionMatchesFilter(expression, filters)) {
      filtered.expressions.push_back(expression);
    }
  }
  for (const DebugMetadataHIRTypeSourceLocation &type : locations.types) {
    if (typeMatchesFilter(type, filters)) {
      filtered.types.push_back(type);
    }
  }
  for (const DebugMetadataHIRStatementSourceLocation &statement :
       locations.statements) {
    if (statementMatchesFilter(statement, filters)) {
      filtered.statements.push_back(statement);
    }
  }
  for (const DebugMetadataHIRResourceSourceLocation &resource :
       locations.resources) {
    if (resourceMatchesFilter(resource, filters)) {
      filtered.resources.push_back(resource);
    }
  }
  filtered.summary.expressionCount = filtered.expressions.size();
  filtered.summary.expressionWithLocationCount = filtered.expressions.size();
  filtered.summary.typeCount = filtered.types.size();
  filtered.summary.typeWithLocationCount = filtered.types.size();
  filtered.summary.statementCount = filtered.statements.size();
  filtered.summary.statementWithLocationCount = filtered.statements.size();
  filtered.summary.resourceCount = filtered.resources.size();
  filtered.summary.resourceWithLocationCount = filtered.resources.size();
  return filtered;
}

std::size_t sourceMapPaginationActiveCount(
    const DebugMetadataHIRSourceMapPagination &pagination,
    bool includeResources) {
  std::size_t count = 0;
  count += pagination.expressionOffset != 0 ? 1 : 0;
  count += pagination.expressionLimit.has_value() ? 1 : 0;
  count += pagination.typeOffset != 0 ? 1 : 0;
  count += pagination.typeLimit.has_value() ? 1 : 0;
  count += pagination.statementOffset != 0 ? 1 : 0;
  count += pagination.statementLimit.has_value() ? 1 : 0;
  if (includeResources) {
    count += pagination.resourceOffset != 0 ? 1 : 0;
    count += pagination.resourceLimit.has_value() ? 1 : 0;
  }
  return count;
}

template <typename Record>
std::vector<Record> pageRecords(const std::vector<Record> &records,
                                std::size_t offset,
                                std::optional<std::size_t> limit) {
  if (offset >= records.size()) {
    return {};
  }
  const std::size_t available = records.size() - offset;
  const std::size_t count = limit ? std::min(*limit, available) : available;
  return std::vector<Record>(records.begin() + static_cast<std::ptrdiff_t>(offset),
                             records.begin() +
                                 static_cast<std::ptrdiff_t>(offset + count));
}

std::size_t nextSourceMapOffset(std::size_t offset, std::size_t emitted,
                                std::size_t total) {
  return std::min(offset + emitted, total);
}

DebugMetadataHIRSourceMapPage makeSourceMapPage(
    const DebugMetadataHIRSourceLocations &locations,
    const DebugMetadataHIRSourceMapPagination &pagination,
    const DebugMetadataHIRSourceLocations &pagedLocations,
    bool includeResources) {
  DebugMetadataHIRSourceMapPage page;
  page.request = pagination;
  page.expressionTotalCount = locations.expressions.size();
  page.expressionEmittedCount = pagedLocations.expressions.size();
  page.expressionNextOffset =
      nextSourceMapOffset(pagination.expressionOffset,
                          page.expressionEmittedCount,
                          page.expressionTotalCount);
  page.expressionHasMore = page.expressionNextOffset < page.expressionTotalCount;
  page.typeTotalCount = locations.types.size();
  page.typeEmittedCount = pagedLocations.types.size();
  page.typeNextOffset =
      nextSourceMapOffset(pagination.typeOffset, page.typeEmittedCount,
                          page.typeTotalCount);
  page.typeHasMore = page.typeNextOffset < page.typeTotalCount;
  page.statementTotalCount = locations.statements.size();
  page.statementEmittedCount = pagedLocations.statements.size();
  page.statementNextOffset =
      nextSourceMapOffset(pagination.statementOffset,
                          page.statementEmittedCount,
                          page.statementTotalCount);
  page.statementHasMore =
      page.statementNextOffset < page.statementTotalCount;
  if (includeResources) {
    page.resourceTotalCount = locations.resources.size();
    page.resourceEmittedCount = pagedLocations.resources.size();
    page.resourceNextOffset =
        nextSourceMapOffset(pagination.resourceOffset,
                            page.resourceEmittedCount,
                            page.resourceTotalCount);
    page.resourceHasMore = page.resourceNextOffset < page.resourceTotalCount;
  }
  return page;
}

DebugMetadataHIRSourceLocations paginateHIRSourceLocations(
    const DebugMetadataHIRSourceLocations &locations,
    const DebugMetadataHIRSourceMapPagination &pagination,
    bool includeResources) {
  if (sourceMapPaginationActiveCount(pagination, includeResources) == 0) {
    return locations;
  }

  DebugMetadataHIRSourceLocations paged;
  paged.expressions =
      pageRecords(locations.expressions, pagination.expressionOffset,
                  pagination.expressionLimit);
  paged.types =
      pageRecords(locations.types, pagination.typeOffset, pagination.typeLimit);
  paged.statements =
      pageRecords(locations.statements, pagination.statementOffset,
                  pagination.statementLimit);
  if (includeResources) {
    paged.resources =
        pageRecords(locations.resources, pagination.resourceOffset,
                    pagination.resourceLimit);
  } else {
    paged.resources = locations.resources;
  }
  paged.summary.expressionCount = paged.expressions.size();
  paged.summary.expressionWithLocationCount = paged.expressions.size();
  paged.summary.typeCount = paged.types.size();
  paged.summary.typeWithLocationCount = paged.types.size();
  paged.summary.statementCount = paged.statements.size();
  paged.summary.statementWithLocationCount = paged.statements.size();
  paged.summary.resourceCount = paged.resources.size();
  paged.summary.resourceWithLocationCount = paged.resources.size();
  return paged;
}

void incrementCategoryCount(std::map<std::string, std::size_t> &counts,
                            std::string_view name) {
  ++counts[std::string(name)];
}

std::vector<DebugMetadataHIRSourceMapCategoryCount>
categoryCountsFromMap(const std::map<std::string, std::size_t> &counts) {
  std::vector<DebugMetadataHIRSourceMapCategoryCount> entries;
  entries.reserve(counts.size());
  for (const auto &[name, count] : counts) {
    entries.push_back({name, count});
  }
  return entries;
}

DebugMetadataHIRSourceMapCategoryCounts buildHIRSourceMapCategoryCounts(
    const DebugMetadataHIRSourceLocations &locations, bool includeResources) {
  DebugMetadataHIRSourceMapCategoryCounts categoryCounts;
  categoryCounts.expressionTotalCount = locations.expressions.size();
  categoryCounts.typeTotalCount = locations.types.size();
  categoryCounts.statementTotalCount = locations.statements.size();
  if (includeResources) {
    categoryCounts.resourceTotalCount = locations.resources.size();
  }
  categoryCounts.recordTotalCount =
      categoryCounts.expressionTotalCount + categoryCounts.typeTotalCount +
      categoryCounts.statementTotalCount + categoryCounts.resourceTotalCount;

  std::map<std::string, std::size_t> expressionKinds;
  std::map<std::string, std::size_t> statementKinds;
  std::map<std::string, std::size_t> typeOwnerKinds;
  std::map<std::string, std::size_t> resourceRecordKinds;
  std::map<std::string, std::size_t> resourceKinds;
  for (const DebugMetadataHIRExpressionSourceLocation &expression :
       locations.expressions) {
    incrementCategoryCount(expressionKinds, expression.kind);
  }
  for (const DebugMetadataHIRTypeSourceLocation &type : locations.types) {
    incrementCategoryCount(typeOwnerKinds, type.ownerKind);
  }
  for (const DebugMetadataHIRStatementSourceLocation &statement :
       locations.statements) {
    incrementCategoryCount(statementKinds, statement.statementKind);
  }
  if (includeResources) {
    for (const DebugMetadataHIRResourceSourceLocation &resource :
         locations.resources) {
      incrementCategoryCount(resourceRecordKinds, resource.resourceRecordKind);
      incrementCategoryCount(resourceKinds, resource.resourceKind);
    }
  }

  categoryCounts.expressionKinds = categoryCountsFromMap(expressionKinds);
  categoryCounts.statementKinds = categoryCountsFromMap(statementKinds);
  categoryCounts.typeOwnerKinds = categoryCountsFromMap(typeOwnerKinds);
  categoryCounts.resourceRecordKinds =
      categoryCountsFromMap(resourceRecordKinds);
  categoryCounts.resourceKinds = categoryCountsFromMap(resourceKinds);
  return categoryCounts;
}

struct SourceMapRecordRef {
  enum class Kind { Type, Statement, Expression, Resource };

  Kind kind = Kind::Type;
  std::size_t arrayIndex = 0;
  std::size_t offset = 0;
  std::size_t endOffset = 0;
  std::size_t sourceIndex = 0;
};

int sourceMapRecordKindRank(SourceMapRecordRef::Kind kind) {
  switch (kind) {
  case SourceMapRecordRef::Kind::Type:
    return 0;
  case SourceMapRecordRef::Kind::Statement:
    return 1;
  case SourceMapRecordRef::Kind::Expression:
    return 2;
  case SourceMapRecordRef::Kind::Resource:
    return 3;
  }
  return 4;
}

std::size_t sourceMapRecordActiveCount(
    const DebugMetadataHIRSourceMapPagination &pagination) {
  std::size_t count = 0;
  count += pagination.recordsEnabled ? 1 : 0;
  count += pagination.recordOffset != 0 ? 1 : 0;
  count += pagination.recordLimit.has_value() ? 1 : 0;
  return count;
}

bool sourceMapRecordsEnabled(
    const DebugMetadataHIRSourceMapPagination &pagination) {
  return pagination.recordsEnabled || pagination.recordOffset != 0 ||
         pagination.recordLimit.has_value();
}

std::vector<SourceMapRecordRef>
buildCombinedSourceMapRecordRefs(const DebugMetadataHIRSourceLocations &locations,
                                 bool includeResources) {
  std::vector<SourceMapRecordRef> refs;
  refs.reserve(locations.expressions.size() + locations.types.size() +
               locations.statements.size() +
               (includeResources ? locations.resources.size() : 0));
  for (std::size_t index = 0; index < locations.expressions.size(); ++index) {
    const DebugMetadataHIRExpressionSourceLocation &expression =
        locations.expressions[index];
    refs.push_back({SourceMapRecordRef::Kind::Expression, index,
                    expression.location.offset,
                    expression.location.endOffset, expression.index});
  }
  for (std::size_t index = 0; index < locations.types.size(); ++index) {
    const DebugMetadataHIRTypeSourceLocation &type = locations.types[index];
    refs.push_back({SourceMapRecordRef::Kind::Type, index, type.location.offset,
                    type.location.endOffset, type.index});
  }
  for (std::size_t index = 0; index < locations.statements.size(); ++index) {
    const DebugMetadataHIRStatementSourceLocation &statement =
        locations.statements[index];
    refs.push_back({SourceMapRecordRef::Kind::Statement, index,
                    statement.location.offset, statement.location.endOffset,
                    statement.index});
  }
  if (includeResources) {
    for (std::size_t index = 0; index < locations.resources.size(); ++index) {
      const DebugMetadataHIRResourceSourceLocation &resource =
          locations.resources[index];
      refs.push_back({SourceMapRecordRef::Kind::Resource, index,
                      resource.location.offset, resource.location.endOffset,
                      resource.index});
    }
  }

  std::stable_sort(refs.begin(), refs.end(),
                   [](const SourceMapRecordRef &lhs,
                      const SourceMapRecordRef &rhs) {
                     if (lhs.offset != rhs.offset) {
                       return lhs.offset < rhs.offset;
                     }
                     if (lhs.endOffset != rhs.endOffset) {
                       return lhs.endOffset < rhs.endOffset;
                     }
                     if (lhs.kind != rhs.kind) {
                       return sourceMapRecordKindRank(lhs.kind) <
                              sourceMapRecordKindRank(rhs.kind);
                     }
                     return lhs.sourceIndex < rhs.sourceIndex;
                   });
  return refs;
}

DebugMetadataHIRSourceMapRecords buildCombinedSourceMapRecords(
    const DebugMetadataHIRSourceLocations &locations,
    const DebugMetadataHIRSourceMapPagination &pagination,
    bool includeResources) {
  DebugMetadataHIRSourceMapRecords records;
  records.enabled = sourceMapRecordsEnabled(pagination);
  records.activeCount = sourceMapRecordActiveCount(pagination);
  records.offset = pagination.recordOffset;
  records.limit = pagination.recordLimit;

  const std::vector<SourceMapRecordRef> refs =
      buildCombinedSourceMapRecordRefs(locations, includeResources);
  records.totalCount = refs.size();
  if (!records.enabled || records.offset >= refs.size()) {
    return records;
  }

  const std::size_t available = refs.size() - records.offset;
  const std::size_t count =
      records.limit ? std::min(*records.limit, available) : available;
  records.items.reserve(count);
  for (std::size_t cursor = records.offset; cursor < records.offset + count;
       ++cursor) {
    const SourceMapRecordRef &ref = refs[cursor];
    DebugMetadataHIRSourceMapRecord record;
    record.cursor = cursor;
    if (ref.kind == SourceMapRecordRef::Kind::Expression) {
      record.recordKind = "expression";
      record.expression = locations.expressions[ref.arrayIndex];
    } else if (ref.kind == SourceMapRecordRef::Kind::Statement) {
      record.recordKind = "statement";
      record.statement = locations.statements[ref.arrayIndex];
    } else if (ref.kind == SourceMapRecordRef::Kind::Resource) {
      record.recordKind = "resource";
      record.resource = locations.resources[ref.arrayIndex];
    } else {
      record.recordKind = "type";
      record.type = locations.types[ref.arrayIndex];
    }
    records.items.push_back(std::move(record));
  }

  records.emittedCount = records.items.size();
  records.nextOffset =
      nextSourceMapOffset(records.offset, records.emittedCount, records.totalCount);
  records.hasMore = records.nextOffset < records.totalCount;
  return records;
}

void appendSourceMapFilterField(std::ostringstream &out,
                                std::string_view fieldName,
                                const std::optional<std::string> &filter) {
  if (!filter) {
    return;
  }
  out << ",\"" << fieldName << "\":\"" << escapeJson(*filter) << "\"";
}

void appendHIRSourceMapFilters(
    std::ostringstream &out, const DebugMetadataHIRSourceMapFilter &filters,
    bool includeResources) {
  out << "{\"activeCount\":"
      << sourceMapFilterActiveCount(filters, includeResources);
  appendSourceMapFilterField(out, "stage", filters.stage);
  appendSourceMapFilterField(out, "entryPoint", filters.entryPoint);
  appendSourceMapFilterField(out, "function", filters.function);
  appendSourceMapFilterField(out, "statementKind", filters.statementKind);
  appendSourceMapFilterField(out, "expressionKind", filters.expressionKind);
  appendSourceMapFilterField(out, "expressionValue", filters.expressionValue);
  appendSourceMapFilterField(out, "ownerKind", filters.ownerKind);
  appendSourceMapFilterField(out, "ownerName", filters.ownerName);
  if (includeResources) {
    appendSourceMapFilterField(out, "resourceRecordKind",
                               filters.resourceRecordKind);
    appendSourceMapFilterField(out, "resourceName", filters.resourceName);
    appendSourceMapFilterField(out, "resourceKind", filters.resourceKind);
  }
  out << "}";
}

void appendOptionalSizeField(std::ostringstream &out,
                             std::string_view fieldName,
                             std::optional<std::size_t> value) {
  if (!value.has_value()) {
    return;
  }
  out << ",\"" << fieldName << "\":" << *value;
}

void appendHIRSourceMapPagination(std::ostringstream &out,
                                  const DebugMetadataHIRSourceMapPage &page,
                                  bool includeResources) {
  out << "{\"activeCount\":"
      << sourceMapPaginationActiveCount(page.request, includeResources)
      << ",\"expressionOffset\":" << page.request.expressionOffset
      << ",\"typeOffset\":" << page.request.typeOffset
      << ",\"statementOffset\":" << page.request.statementOffset;
  if (includeResources) {
    out << ",\"resourceOffset\":" << page.request.resourceOffset;
  }
  appendOptionalSizeField(out, "expressionLimit", page.request.expressionLimit);
  appendOptionalSizeField(out, "typeLimit", page.request.typeLimit);
  appendOptionalSizeField(out, "statementLimit", page.request.statementLimit);
  if (includeResources) {
    appendOptionalSizeField(out, "resourceLimit", page.request.resourceLimit);
  }
  out << ",\"expressionTotalCount\":" << page.expressionTotalCount
      << ",\"expressionEmittedCount\":" << page.expressionEmittedCount
      << ",\"expressionHasMore\":"
      << (page.expressionHasMore ? "true" : "false")
      << ",\"expressionNextOffset\":" << page.expressionNextOffset
      << ",\"typeTotalCount\":" << page.typeTotalCount
      << ",\"typeEmittedCount\":" << page.typeEmittedCount
      << ",\"typeHasMore\":" << (page.typeHasMore ? "true" : "false")
      << ",\"typeNextOffset\":" << page.typeNextOffset
      << ",\"statementTotalCount\":" << page.statementTotalCount
      << ",\"statementEmittedCount\":" << page.statementEmittedCount
      << ",\"statementHasMore\":"
      << (page.statementHasMore ? "true" : "false")
      << ",\"statementNextOffset\":" << page.statementNextOffset;
  if (includeResources) {
    out << ",\"resourceTotalCount\":" << page.resourceTotalCount
        << ",\"resourceEmittedCount\":" << page.resourceEmittedCount
        << ",\"resourceHasMore\":"
        << (page.resourceHasMore ? "true" : "false")
        << ",\"resourceNextOffset\":" << page.resourceNextOffset;
  }
  out << "}";
}

void appendCategoryCountArray(
    std::ostringstream &out,
    const std::vector<DebugMetadataHIRSourceMapCategoryCount> &counts) {
  out << "[";
  for (std::size_t index = 0; index < counts.size(); ++index) {
    if (index != 0) {
      out << ",";
    }
    out << "{\"name\":\"" << escapeJson(counts[index].name)
        << "\",\"count\":" << counts[index].count << "}";
  }
  out << "]";
}

void appendHIRSourceMapCategoryCounts(
    std::ostringstream &out,
    const DebugMetadataHIRSourceMapCategoryCounts &categoryCounts,
    bool includeResources) {
  out << "{\"expressionTotalCount\":"
      << categoryCounts.expressionTotalCount
      << ",\"typeTotalCount\":" << categoryCounts.typeTotalCount
      << ",\"statementTotalCount\":" << categoryCounts.statementTotalCount;
  if (includeResources) {
    out << ",\"resourceTotalCount\":" << categoryCounts.resourceTotalCount;
  }
  out
      << ",\"recordTotalCount\":" << categoryCounts.recordTotalCount
      << ",\"expressionKinds\":";
  appendCategoryCountArray(out, categoryCounts.expressionKinds);
  out << ",\"statementKinds\":";
  appendCategoryCountArray(out, categoryCounts.statementKinds);
  out << ",\"typeOwnerKinds\":";
  appendCategoryCountArray(out, categoryCounts.typeOwnerKinds);
  if (includeResources) {
    out << ",\"resourceRecordKinds\":";
    appendCategoryCountArray(out, categoryCounts.resourceRecordKinds);
    out << ",\"resourceKinds\":";
    appendCategoryCountArray(out, categoryCounts.resourceKinds);
  }
  out << "}";
}

void appendHIRSourceMapRecords(std::ostringstream &out,
                               const DebugMetadataHIRSourceMapRecords &records,
                               bool includeResources) {
  out << "{\"enabled\":" << (records.enabled ? "true" : "false")
      << ",\"activeCount\":" << records.activeCount
      << ",\"offset\":" << records.offset;
  appendOptionalSizeField(out, "limit", records.limit);
  out << ",\"totalCount\":" << records.totalCount
      << ",\"emittedCount\":" << records.emittedCount
      << ",\"hasMore\":" << (records.hasMore ? "true" : "false")
      << ",\"nextOffset\":" << records.nextOffset << ",\"items\":[";
  for (std::size_t index = 0; index < records.items.size(); ++index) {
    if (index != 0) {
      out << ",";
    }
    const DebugMetadataHIRSourceMapRecord &record = records.items[index];
    out << "{\"cursor\":" << record.cursor << ",\"recordKind\":\""
        << escapeJson(record.recordKind) << "\"";
    if (record.recordKind == "expression") {
      out << ",\"expression\":";
      appendHIRExpressionSourceLocation(out, record.expression);
    } else if (record.recordKind == "statement") {
      out << ",\"statement\":";
      appendHIRStatementSourceLocation(out, record.statement);
    } else if (includeResources && record.recordKind == "resource") {
      out << ",\"resource\":";
      appendHIRResourceSourceLocation(out, record.resource);
    } else {
      out << ",\"type\":";
      appendHIRTypeSourceLocation(out, record.type);
    }
    out << "}";
  }
  out << "]}";
}

void appendHIRSourceLocations(std::ostringstream &out,
                              const DebugMetadataHIRSourceLocations &locations,
                              bool includeResources) {
  out << "{"
      << "\"expressionCount\":" << locations.summary.expressionCount
      << ",\"expressionWithLocationCount\":"
      << locations.summary.expressionWithLocationCount
      << ",\"typeCount\":" << locations.summary.typeCount
      << ",\"typeWithLocationCount\":" << locations.summary.typeWithLocationCount
      << ",\"statementCount\":" << locations.summary.statementCount
      << ",\"statementWithLocationCount\":"
      << locations.summary.statementWithLocationCount;
  if (includeResources) {
    out << ",\"resourceCount\":" << locations.summary.resourceCount
        << ",\"resourceWithLocationCount\":"
        << locations.summary.resourceWithLocationCount;
  }
  out << ",\"expressions\":";
  appendHIRExpressionSourceLocations(out, locations.expressions);
  out << ",\"types\":";
  appendHIRTypeSourceLocations(out, locations.types);
  out << ",\"statements\":";
  appendHIRStatementSourceLocations(out, locations.statements);
  if (includeResources) {
    out << ",\"resources\":";
    appendHIRResourceSourceLocations(out, locations.resources);
  }
  out << "}";
}

std::string projectionTargetName(
    const TargetLegalizationContractProjection &projection) {
  if (!projection.targetProfile.resolvedTargetName.empty()) {
    return projection.targetProfile.resolvedTargetName;
  }
  return targetName(projection.targetProfile.resolvedTarget);
}

std::string projectionPackageModeName(
    const TargetLegalizationContractProjection &projection) {
  if (!projection.packageModeName.empty()) {
    return projection.packageModeName;
  }
  return targetLegalizationPackageModeName(projection.packageMode);
}

std::string decisionReasonCodeValue(
    const std::vector<std::string> &decisionReasonCodes,
    std::string_view prefix, const std::string &fallback) {
  for (const std::string &code : decisionReasonCodes) {
    if (code.size() <= prefix.size()) {
      continue;
    }
    if (code.compare(0, prefix.size(), prefix.data(), prefix.size()) == 0) {
      return code.substr(prefix.size());
    }
  }
  return fallback;
}

std::string projectionPackageDecisionReason(
    const TargetLegalizationContractProjection &projection) {
  return decisionReasonCodeValue(projection.consumerDecisionReasonCodes,
                                 "package-reason:", projection.reason);
}

struct DebugMetadataTargetLegalizationProjectionRecord {
  TargetLegalizationContractProjection projection;
  std::vector<TargetLegalizationDiagnostic> diagnostics;
  DebugMetadataTargetCapabilitySummary summary;
};

DebugMetadataTargetCapabilitySummary targetCapabilitySummaryFromProjection(
    const TargetLegalizationContractProjection &projection) {
  DebugMetadataTargetCapabilitySummary summary;
  summary.target = projectionTargetName(projection);
  summary.nativeImplemented = projection.nativeImplemented;
  summary.sourcePackageSupported = projection.sourcePackageSupported;
  summary.packageBuildSupported =
      targetLegalizationProjectionSupportsPackage(projection);
  summary.packageMode = projectionPackageModeName(projection);
  summary.packageDecisionReason = projectionPackageDecisionReason(projection);
  summary.decisionReasonCodes = projection.consumerDecisionReasonCodes;
  summary.packageRankScore = projection.packageRankScore;
  summary.requiredCapabilityCount = projection.requiredCapabilityCount;
  summary.missingCapabilityCount = projection.missingCapabilityCount;
  summary.requiredCapabilities = projection.requiredCapabilityIds;
  summary.missingCapabilities = projection.missingCapabilityIds;
  summary.legalizationCoreEvidenceIds = projection.coreEvidenceIds;
  summary.requiredToolCount = projection.requiredToolCount;
  summary.missingToolCount = projection.missingToolCount;
  summary.requiredToolIds = projection.requiredToolIds;
  summary.missingToolIds = projection.missingToolIds;
  summary.optionalNativeToolMissing = projection.optionalNativeToolMissing;
  summary.optionalNativeToolStatus = projection.optionalNativeToolStatusName;
  summary.toolRequirementEvidenceIds = projection.toolRequirementEvidenceIds;
  summary.requiredCapabilityGroups =
      capabilityGroupsFromIds(projection.requiredCapabilityIds);
  summary.missingCapabilityGroups =
      capabilityGroupsFromIds(projection.missingCapabilityIds);
  return summary;
}

std::vector<DebugMetadataTargetLegalizationProjectionRecord>
targetLegalizationProjectionRecords(
    const std::vector<TargetLegalizationResult> &legalizations) {
  std::vector<DebugMetadataTargetLegalizationProjectionRecord> records;
  records.reserve(legalizations.size());
  for (const TargetLegalizationResult &legalization : legalizations) {
    const TargetLegalizationContract contract =
        targetLegalizationContract(legalization);
    DebugMetadataTargetLegalizationProjectionRecord record;
    record.projection = targetLegalizationContractProjection(contract);
    record.diagnostics = contract.diagnostics;
    record.summary = targetCapabilitySummaryFromProjection(record.projection);
    records.push_back(std::move(record));
  }
  return records;
}

TargetKind selectedTargetFromProjectionRecords(
    const std::vector<DebugMetadataTargetLegalizationProjectionRecord> &records,
    TargetKind requestedTarget) {
  if (requestedTarget != TargetKind::Auto) {
    return requestedTarget;
  }
  if (records.empty()) {
    return TargetKind::Auto;
  }
  return records.front().projection.targetProfile.selectedTarget;
}

DebugMetadataTargetCapabilities buildTargetCapabilities(
    const std::vector<DebugMetadataTargetLegalizationProjectionRecord> &records,
    TargetKind defaultTarget) {
  DebugMetadataTargetCapabilities targetCapabilities;
  targetCapabilities.defaultTarget = targetName(defaultTarget);

  for (const DebugMetadataTargetLegalizationProjectionRecord &record :
       records) {
    targetCapabilities.summaries.push_back(record.summary);
  }

  return targetCapabilities;
}

using HIRResourceLookup = std::map<std::string, const HIRResource *>;

struct HIRSourceLocationContext {
  std::string stage;
  std::string entryPoint;
  std::string function;
  std::string statementKind;
  const HIRResourceLookup *resources = nullptr;
  std::set<std::string> hiddenResourceNames;
};

void recordHIRTypeSourceLocationAt(DebugMetadataHIRSourceLocations &locations,
                                   const HIRType &type,
                                   const SourceLocation &location,
                                   const HIRSourceLocationContext &context,
                                   std::string_view ownerKind,
                                   std::string_view ownerName) {
  const std::size_t index = locations.summary.typeCount++;
  if (!sourceLocationAvailable(location)) {
    return;
  }

  DebugMetadataHIRTypeSourceLocation record;
  record.index = index;
  record.stage = context.stage;
  record.entryPoint = context.entryPoint;
  record.function = context.function;
  record.ownerKind = ownerKind;
  record.ownerName = ownerName;
  record.type = formatType(type);
  record.location = debugSourceLocation(location);
  locations.types.push_back(std::move(record));
  locations.summary.typeWithLocationCount = locations.types.size();
}

void recordHIRTypeSourceLocation(DebugMetadataHIRSourceLocations &locations,
                                 const HIRType &type,
                                 const HIRSourceLocationContext &context,
                                 std::string_view ownerKind,
                                 std::string_view ownerName) {
  recordHIRTypeSourceLocationAt(locations, type, type.location, context,
                                ownerKind, ownerName);
}

void recordHIRResourceSourceLocation(DebugMetadataHIRSourceLocations &locations,
                                     const HIRResource &resource,
                                     const HIRSourceLocationContext &context,
                                     std::string_view resourceRecordKind,
                                     const SourceLocation &location) {
  if (!sourceLocationAvailable(location)) {
    return;
  }

  const std::size_t index = locations.summary.resourceCount++;
  DebugMetadataHIRResourceSourceLocation record;
  record.index = index;
  record.resourceRecordKind = resourceRecordKind;
  record.stage = context.stage;
  record.entryPoint = context.entryPoint;
  record.resourceName = resource.name;
  record.resourceKind = resourceKindName(resource.kind);
  record.type = formatType(resource.type);
  if (resource.explicitSet) {
    record.bindingSet = resource.set;
  }
  if (resource.explicitBinding) {
    record.binding = resource.binding;
  }
  record.location = debugSourceLocation(location);
  locations.resources.push_back(std::move(record));
  locations.summary.resourceWithLocationCount = locations.resources.size();
}

void recordHIRResourceSourceLocations(DebugMetadataHIRSourceLocations &locations,
                                      const HIRResource &resource,
                                      const HIRSourceLocationContext &context) {
  recordHIRResourceSourceLocation(locations, resource, context, "declaration",
                                  resource.declarationSpan);
  recordHIRResourceSourceLocation(locations, resource, context, "layout",
                                  resource.layoutSpan);
  recordHIRResourceSourceLocation(locations, resource, context, "set",
                                  resource.setSpan);
  recordHIRResourceSourceLocation(locations, resource, context, "binding",
                                  resource.bindingSpan);
}

void hideHIRResourceName(HIRSourceLocationContext &context,
                         const std::string &name) {
  if (!name.empty()) {
    context.hiddenResourceNames.insert(name);
  }
}

const HIRResource *
findHIRResourceAccess(const HIRExpression &expression,
                      const HIRSourceLocationContext &context) {
  if (expression.kind != HIRExpressionKind::Identifier ||
      expression.value.empty() || expression.type.name.empty() ||
      context.resources == nullptr ||
      context.hiddenResourceNames.contains(expression.value)) {
    return nullptr;
  }

  const auto found = context.resources->find(expression.value);
  if (found == context.resources->end() || found->second == nullptr) {
    return nullptr;
  }

  const HIRResource *resource = found->second;
  return formatType(expression.type) == formatType(resource->type) ? resource
                                                                   : nullptr;
}

void recordHIRResourceAccessSourceLocation(
    DebugMetadataHIRSourceLocations &locations, const HIRExpression &expression,
    const HIRSourceLocationContext &context) {
  const HIRResource *resource = findHIRResourceAccess(expression, context);
  if (resource == nullptr) {
    return;
  }
  recordHIRResourceSourceLocation(locations, *resource, context, "access",
                                  expression.location);
}

void recordHIRExpressionSourceLocations(
    DebugMetadataHIRSourceLocations &locations, const HIRExpression &expression,
    const HIRSourceLocationContext &context) {
  if (expression.kind == HIRExpressionKind::Empty) {
    return;
  }

  const std::size_t index = locations.summary.expressionCount++;
  const std::string ownerName =
      expression.value.empty() ? expressionKindName(expression.kind)
                               : expression.value;
  recordHIRTypeSourceLocation(locations, expression.type, context,
                              "expression-type", ownerName);
  if (sourceLocationAvailable(expression.location)) {
    DebugMetadataHIRExpressionSourceLocation record;
    record.index = index;
    record.stage = context.stage;
    record.entryPoint = context.entryPoint;
    record.function = context.function;
    record.statementKind = context.statementKind;
    record.kind = expressionKindName(expression.kind);
    record.value = expression.value;
    record.type = formatType(expression.type);
    record.location = debugSourceLocation(expression.location);
    locations.expressions.push_back(std::move(record));
    locations.summary.expressionWithLocationCount =
        locations.expressions.size();
  }
  recordHIRResourceAccessSourceLocation(locations, expression, context);

  for (const HIRExpression &child : expression.children) {
    recordHIRExpressionSourceLocations(locations, child, context);
  }
}

std::string statementSourceName(const HIRStatement &statement) {
  if (!statement.name.empty()) {
    return statement.name;
  }
  if (!statement.target.value.empty()) {
    return statement.target.value;
  }
  if (!statement.value.value.empty()) {
    return statement.value.value;
  }
  return {};
}

void recordHIRStatementSelfSourceLocation(
    DebugMetadataHIRSourceLocations &locations, const HIRStatement &statement,
    const HIRSourceLocationContext &context) {
  const std::size_t index = locations.summary.statementCount++;
  if (!sourceLocationAvailable(statement.location)) {
    return;
  }

  DebugMetadataHIRStatementSourceLocation record;
  record.index = index;
  record.stage = context.stage;
  record.entryPoint = context.entryPoint;
  record.function = context.function;
  record.statementKind = context.statementKind;
  record.name = statementSourceName(statement);
  record.location = debugSourceLocation(statement.location);
  locations.statements.push_back(std::move(record));
  locations.summary.statementWithLocationCount = locations.statements.size();
}

void recordHIRStatementSourceLocations(
    DebugMetadataHIRSourceLocations &locations, const HIRStatement &statement,
    const HIRSourceLocationContext &context);

void recordHIRStatementBlockSourceLocations(
    DebugMetadataHIRSourceLocations &locations,
    const std::vector<HIRStatement> &statements,
    const HIRSourceLocationContext &context) {
  HIRSourceLocationContext blockContext = context;
  for (const HIRStatement &statement : statements) {
    recordHIRStatementSourceLocations(locations, statement, blockContext);
    if (statement.kind == HIRStatementKind::Declaration) {
      hideHIRResourceName(blockContext, statement.name);
    }
  }
}

void recordHIRStatementSourceLocations(
    DebugMetadataHIRSourceLocations &locations, const HIRStatement &statement,
    const HIRSourceLocationContext &context) {
  HIRSourceLocationContext statementContext = context;
  statementContext.statementKind = statementKindName(statement.kind);
  recordHIRStatementSelfSourceLocation(locations, statement, statementContext);
  recordHIRTypeSourceLocation(locations, statement.declaredType,
                              statementContext, "statement-declared-type",
                              statement.name);

  if (statement.kind == HIRStatementKind::For) {
    HIRSourceLocationContext loopContext = statementContext;
    recordHIRExpressionSourceLocations(locations, statement.target,
                                       loopContext);
    recordHIRExpressionSourceLocations(locations, statement.value,
                                       loopContext);
    recordHIRStatementBlockSourceLocations(locations, statement.initializer,
                                           loopContext);
    for (const HIRStatement &initializer : statement.initializer) {
      if (initializer.kind == HIRStatementKind::Declaration) {
        hideHIRResourceName(loopContext, initializer.name);
      }
    }
    recordHIRStatementBlockSourceLocations(locations, statement.update,
                                           loopContext);
    recordHIRStatementBlockSourceLocations(locations, statement.body,
                                           loopContext);
    recordHIRStatementBlockSourceLocations(locations, statement.elseBody,
                                           loopContext);
    return;
  }

  recordHIRExpressionSourceLocations(locations, statement.target,
                                     statementContext);
  recordHIRExpressionSourceLocations(locations, statement.value,
                                     statementContext);

  recordHIRStatementBlockSourceLocations(locations, statement.initializer,
                                         statementContext);
  recordHIRStatementBlockSourceLocations(locations, statement.update,
                                         statementContext);
  recordHIRStatementBlockSourceLocations(locations, statement.body,
                                         statementContext);
  recordHIRStatementBlockSourceLocations(locations, statement.elseBody,
                                         statementContext);
}

void recordHIRFunctionSourceLocations(
    DebugMetadataHIRSourceLocations &locations, const HIRFunction &function,
    HIRSourceLocationContext context) {
  context.function = function.name;
  recordHIRTypeSourceLocation(locations, function.returnType, context,
                              "function-return-type", function.name);
  for (const HIRParameter &parameter : function.parameters) {
    recordHIRTypeSourceLocation(locations, parameter.type, context,
                                "parameter-type", parameter.name);
    recordHIRTypeSourceLocationAt(locations, parameter.type, parameter.nameSpan,
                                  context, "parameter-name", parameter.name);
    hideHIRResourceName(context, parameter.name);
  }
  recordHIRStatementBlockSourceLocations(locations, function.body, context);
}

DebugMetadataHIRSourceLocations
buildHIRSourceLocations(const HIRModule &module,
                        bool includeResourceAccesses = false) {
  DebugMetadataHIRSourceLocations locations;
  HIRSourceLocationContext context;

  for (const HIRStruct &structure : module.structs) {
    for (const HIRField &field : structure.fields) {
      recordHIRTypeSourceLocation(locations, field.type, context, "field-type",
                                  structure.name + "." + field.name);
      recordHIRTypeSourceLocationAt(locations, field.type, field.nameSpan,
                                    context, "field-name",
                                    structure.name + "." + field.name);
    }
  }
  for (const HIRConstant &constant : module.constants) {
    recordHIRTypeSourceLocation(locations, constant.type, context,
                                "constant-type", constant.name);
    recordHIRExpressionSourceLocations(locations, constant.value, context);
  }
  for (const HIRFunction &function : module.functions) {
    recordHIRFunctionSourceLocations(locations, function, context);
  }
  for (const HIRStage &stage : module.stages) {
    HIRSourceLocationContext stageContext;
    stageContext.stage = stage.stage;
    stageContext.entryPoint = stage.entryPointName;
    HIRResourceLookup resourceLookup;
    for (const HIRResource &resource : stage.resources) {
      resourceLookup.emplace(resource.name, &resource);
      recordHIRResourceSourceLocations(locations, resource, stageContext);
      recordHIRTypeSourceLocation(locations, resource.type, stageContext,
                                  "resource-type", resource.name);
    }
    if (includeResourceAccesses) {
      stageContext.resources = &resourceLookup;
    }
    for (const HIRFunction &function : stage.functions) {
      recordHIRFunctionSourceLocations(locations, function, stageContext);
    }
  }

  return locations;
}

const DebugMetadataTargetCapabilitySummary *
findTargetSummary(const DebugMetadataTargetCapabilities &targetCapabilities,
                  std::string_view target) {
  for (const DebugMetadataTargetCapabilitySummary &summary :
       targetCapabilities.summaries) {
    if (summary.target == target) {
      return &summary;
    }
  }
  return nullptr;
}

const DebugMetadataTargetLegalizationProjectionRecord *
findTargetProjectionRecord(
    const std::vector<DebugMetadataTargetLegalizationProjectionRecord> &records,
    std::string_view target) {
  for (const DebugMetadataTargetLegalizationProjectionRecord &record :
       records) {
    if (record.summary.target == target) {
      return &record;
    }
  }
  return nullptr;
}

DebugMetadataHIRSourceMapFilter sourceMapFiltersForSchema(
    DebugMetadataHIRSourceMapFilter filters, bool includeResources) {
  if (!includeResources) {
    filters.resourceRecordKind.reset();
    filters.resourceName.reset();
    filters.resourceKind.reset();
  }
  return filters;
}

DebugMetadataHIRSourceMapPagination sourceMapPaginationForSchema(
    DebugMetadataHIRSourceMapPagination pagination, bool includeResources) {
  if (!includeResources) {
    pagination.resourceOffset = 0;
    pagination.resourceLimit.reset();
  }
  return pagination;
}

std::string
selectedTargetPackageMode(const DebugMetadataTargetCapabilitySummary *summary) {
  if (summary == nullptr) {
    return "unknown";
  }
  return summary->packageMode;
}

DebugMetadataTargetFallback fallbackTargetRecord(
    const DebugMetadataTargetCapabilitySummary &summary, std::size_t rank) {
  DebugMetadataTargetFallback fallback;
  fallback.rank = rank;
  fallback.target = summary.target;
  fallback.packageMode = summary.packageMode;
  fallback.rankReason = summary.packageDecisionReason;
  fallback.nativeImplemented = summary.nativeImplemented;
  fallback.sourcePackageSupported = summary.sourcePackageSupported;
  fallback.packageBuildSupported = summary.packageBuildSupported;
  fallback.missingCapabilityCount = summary.missingCapabilityCount;
  fallback.missingCapabilities = summary.missingCapabilities;
  fallback.legalizationCoreEvidenceIds = summary.legalizationCoreEvidenceIds;
  fallback.requiredToolCount = summary.requiredToolCount;
  fallback.missingToolCount = summary.missingToolCount;
  fallback.requiredToolIds = summary.requiredToolIds;
  fallback.missingToolIds = summary.missingToolIds;
  fallback.optionalNativeToolMissing = summary.optionalNativeToolMissing;
  fallback.optionalNativeToolStatus = summary.optionalNativeToolStatus;
  fallback.toolRequirementEvidenceIds = summary.toolRequirementEvidenceIds;
  fallback.missingCapabilityGroups = summary.missingCapabilityGroups;
  return fallback;
}

DebugMetadataTargetDecisionDiagnostic selectedTargetUnknownDiagnostic(
    std::string_view selectedTargetName) {
  DebugMetadataTargetDecisionDiagnostic diagnostic;
  diagnostic.code = "target.selected.unknown";
  diagnostic.severity = "error";
  diagnostic.target = selectedTargetName;
  diagnostic.message = "selected target '" + std::string(selectedTargetName) +
                       "' has no capability summary";
  return diagnostic;
}

DebugMetadataTargetDecisionDiagnostic selectedTargetUnsupportedDiagnostic(
    const DebugMetadataTargetCapabilitySummary &summary) {
  DebugMetadataTargetDecisionDiagnostic diagnostic;
  diagnostic.code = "target.selected.unsupported";
  diagnostic.severity = "error";
  diagnostic.target = summary.target;
  diagnostic.message = "selected target '" + summary.target +
                       "' cannot build a package for this module";
  diagnostic.capabilities = summary.missingCapabilities;
  diagnostic.legalizationCoreEvidenceIds = summary.legalizationCoreEvidenceIds;
  diagnostic.capabilityGroups = summary.missingCapabilityGroups;
  return diagnostic;
}

DebugMetadataTargetDecisionDiagnostic targetDecisionDiagnosticFromLegalization(
    const TargetLegalizationDiagnostic &legalizationDiagnostic,
    const DebugMetadataTargetCapabilitySummary &summary) {
  DebugMetadataTargetDecisionDiagnostic diagnostic;
  diagnostic.code = legalizationDiagnostic.code;
  diagnostic.severity = toString(legalizationDiagnostic.severity);
  diagnostic.target =
      legalizationDiagnostic.target == TargetKind::Auto
          ? summary.target
          : targetName(legalizationDiagnostic.target);
  diagnostic.message = legalizationDiagnostic.message;
  for (const TargetCapability &capability :
       legalizationDiagnostic.capabilities) {
    diagnostic.capabilities.push_back(targetCapabilityId(capability));
  }
  if (diagnostic.capabilities.empty()) {
    diagnostic.capabilities = summary.missingCapabilities;
  }
  diagnostic.legalizationCoreEvidenceIds =
      summary.legalizationCoreEvidenceIds;
  diagnostic.capabilityGroups =
      capabilityGroupsFromIds(diagnostic.capabilities);
  return diagnostic;
}

std::vector<DebugMetadataTargetDecisionDiagnostic>
selectedTargetDiagnosticsFromProjectionRecord(
    const DebugMetadataTargetLegalizationProjectionRecord &record) {
  std::vector<DebugMetadataTargetDecisionDiagnostic> diagnostics;
  if (record.summary.packageBuildSupported) {
    return diagnostics;
  }
  diagnostics.reserve(record.diagnostics.size());
  for (const TargetLegalizationDiagnostic &diagnostic : record.diagnostics) {
    diagnostics.push_back(targetDecisionDiagnosticFromLegalization(
        diagnostic, record.summary));
  }
  if (diagnostics.empty()) {
    diagnostics.push_back(selectedTargetUnsupportedDiagnostic(record.summary));
  }
  return diagnostics;
}

DebugMetadataTargetDecision buildTargetDecision(
    const DebugMetadataTargetCapabilities &targetCapabilities,
    const std::vector<DebugMetadataTargetLegalizationProjectionRecord> &records,
    TargetKind requestedTarget, TargetKind selectedTarget) {
  const TargetKind resolvedSelectedTarget =
      selectedTarget == TargetKind::Auto ? defaultTargetForHost()
                                         : selectedTarget;
  const std::string selectedTargetName = targetName(resolvedSelectedTarget);

  DebugMetadataTargetDecision decision;
  decision.requestedTarget = targetName(requestedTarget);
  decision.selectedTarget = selectedTargetName;
  if (requestedTarget == TargetKind::Auto) {
    decision.selectionReason =
        resolvedSelectedTarget == defaultTargetForHost()
            ? "auto-host-default"
            : "auto-recommended-target";
  } else {
    decision.selectionReason = "explicit-target";
  }

  std::vector<const DebugMetadataTargetCapabilitySummary *> fallbackSummaries;
  for (const DebugMetadataTargetCapabilitySummary &summary :
       targetCapabilities.summaries) {
    if (summary.packageBuildSupported) {
      decision.viableTargets.push_back(summary.target);
      if (summary.target != selectedTargetName) {
        fallbackSummaries.push_back(&summary);
      }
    } else {
      decision.nonViableTargets.push_back(summary.target);
    }
  }
  std::stable_sort(
      fallbackSummaries.begin(), fallbackSummaries.end(),
      [](const DebugMetadataTargetCapabilitySummary *lhs,
         const DebugMetadataTargetCapabilitySummary *rhs) {
        return lhs->packageRankScore < rhs->packageRankScore;
      });
  decision.fallbackTargetRecords.reserve(fallbackSummaries.size());
  for (const DebugMetadataTargetCapabilitySummary *summary : fallbackSummaries) {
    decision.fallbackTargets.push_back(summary->target);
    decision.fallbackTargetRecords.push_back(fallbackTargetRecord(
        *summary, decision.fallbackTargetRecords.size() + 1));
  }
  decision.fallbackTargetRecordCount = decision.fallbackTargetRecords.size();

  const DebugMetadataTargetCapabilitySummary *selectedSummary =
      findTargetSummary(targetCapabilities, selectedTargetName);
  const DebugMetadataTargetLegalizationProjectionRecord *selectedRecord =
      findTargetProjectionRecord(records, selectedTargetName);
  if (selectedSummary != nullptr) {
    decision.selectedTargetNativeImplemented =
        selectedSummary->nativeImplemented;
    decision.selectedTargetSourcePackageSupported =
        selectedSummary->sourcePackageSupported;
    decision.selectedTargetPackageBuildSupported =
        selectedSummary->packageBuildSupported;
    decision.selectedTargetMissingCapabilityCount =
        selectedSummary->missingCapabilityCount;
    decision.selectedTargetMissingCapabilities =
        selectedSummary->missingCapabilities;
    decision.selectedTargetLegalizationCoreEvidenceIds =
        selectedSummary->legalizationCoreEvidenceIds;
    decision.selectedTargetRequiredToolCount =
        selectedSummary->requiredToolCount;
    decision.selectedTargetMissingToolCount = selectedSummary->missingToolCount;
    decision.selectedTargetRequiredToolIds = selectedSummary->requiredToolIds;
    decision.selectedTargetMissingToolIds = selectedSummary->missingToolIds;
    decision.selectedTargetOptionalNativeToolMissing =
        selectedSummary->optionalNativeToolMissing;
    decision.selectedTargetOptionalNativeToolStatus =
        selectedSummary->optionalNativeToolStatus;
    decision.selectedTargetToolRequirementEvidenceIds =
        selectedSummary->toolRequirementEvidenceIds;
    decision.selectedTargetMissingCapabilityGroups =
        selectedSummary->missingCapabilityGroups;
    if (selectedRecord != nullptr) {
      decision.diagnostics =
          selectedTargetDiagnosticsFromProjectionRecord(*selectedRecord);
    } else if (!selectedSummary->packageBuildSupported) {
      decision.diagnostics.push_back(
          selectedTargetUnsupportedDiagnostic(*selectedSummary));
    }
  } else {
    decision.diagnostics.push_back(
        selectedTargetUnknownDiagnostic(selectedTargetName));
  }
  decision.selectedTargetPackageMode = selectedTargetPackageMode(selectedSummary);
  decision.selectedTargetDiagnosticCount = decision.diagnostics.size();

  return decision;
}

} // namespace

DebugMetadataDocument buildDebugMetadataDocument(
    const HIRModule &module, TargetKind requestedTarget,
    const std::optional<DebugMetadataSourcePackageValidation>
        &sourcePackageValidation) {
  return buildDebugMetadataDocument(module, requestedTarget,
                                    sourcePackageValidation,
                                    DebugMetadataOptions{});
}

DebugMetadataDocument buildDebugMetadataDocument(
    const HIRModule &module, TargetKind requestedTarget,
    const std::optional<DebugMetadataSourcePackageValidation>
        &sourcePackageValidation,
    const DebugMetadataOptions &options) {
  const ManualTextureCompareKernelModuleAnalysis manualKernelAnalysis =
      manualTextureCompareKernelModuleAnalysis(module);
  const std::vector<TargetLegalizationResult> targetLegalizations =
      legalizeTargets(module, requestedTarget);
  const std::vector<DebugMetadataTargetLegalizationProjectionRecord>
      targetProjectionRecords =
          targetLegalizationProjectionRecords(targetLegalizations);
  const TargetKind selectedTarget =
      selectedTargetFromProjectionRecords(targetProjectionRecords,
                                          requestedTarget);

  DebugMetadataDocument document;
  document.targetCapabilities =
      buildTargetCapabilities(targetProjectionRecords, defaultTargetForHost());
  document.targetDecision =
      buildTargetDecision(document.targetCapabilities, targetProjectionRecords,
                          requestedTarget,
                          selectedTarget);
  document.sourcePackageValidation = sourcePackageValidation;
  document.hirSourceLocations = buildHIRSourceLocations(module);
  if (options.sourceRemap) {
    applySourceRemap(document.hirSourceLocations, *options.sourceRemap);
  }
  document.manualTextureCompareKernelSummary.totalCount =
      manualKernelAnalysis.kernels.size();
  document.manualTextureCompareKernelSummary.staticNormalizedCount =
      manualKernelAnalysis.staticNormalized.size();
  document.manualTextureCompareKernelSummary.staticNonNormalizedCount =
      manualKernelAnalysis.staticNonNormalized.size();
  document.manualTextureCompareKernelSummary.staticZeroSumCount =
      manualKernelAnalysis.staticZeroSum.size();
  document.manualTextureCompareKernelSummary.dynamicCount =
      manualKernelAnalysis.dynamic.size();

  document.manualTextureCompareKernelBuckets.staticNormalized =
      manualKernelAnalysis.staticNormalized;
  document.manualTextureCompareKernelBuckets.staticNonNormalized =
      manualKernelAnalysis.staticNonNormalized;
  document.manualTextureCompareKernelBuckets.staticZeroSum =
      manualKernelAnalysis.staticZeroSum;
  document.manualTextureCompareKernelBuckets.dynamic = manualKernelAnalysis.dynamic;

  document.manualTextureCompareKernels.reserve(
      manualKernelAnalysis.kernels.size());
  for (std::size_t i = 0; i < manualKernelAnalysis.kernels.size(); ++i) {
    const ManualTextureCompareKernelOccurrence &occurrence =
        manualKernelAnalysis.kernels[i];

    DebugMetadataManualTextureCompareKernel kernel;
    kernel.index = i;
    kernel.stage = occurrence.stage;
    kernel.entryPoint = occurrence.entryPoint;
    kernel.function = occurrence.function;
    kernel.operation = occurrence.analysis.sourceOperation;
    kernel.sourceKind =
        manualTextureCompareKernelFormName(occurrence.analysis.form);
    kernel.canonicalOperation = occurrence.analysis.canonicalOperation;
    kernel.compatibilityAlias = occurrence.analysis.compatibilityAlias;
    kernel.weightClass =
        manualTextureCompareKernelWeightClassName(occurrence.weightClass);
    kernel.tapCount = occurrence.analysis.weights.tapCount;
    kernel.weightsStatic = occurrence.analysis.weights.allWeightsStatic;
    if (occurrence.analysis.weights.allWeightsStatic) {
      kernel.weightSum = occurrence.analysis.weights.sum;
    }
    kernel.weightsZeroSum = occurrence.analysis.weights.zeroSum;
    kernel.weightsNormalized = occurrence.analysis.weights.normalized;
    document.manualTextureCompareKernels.push_back(std::move(kernel));
  }

  return document;
}

DebugMetadataHIRSourceMapDocument buildHIRSourceMapDocument(
    const HIRModule &module,
    const DebugMetadataHIRSourceMapFilter &filters,
    const DebugMetadataHIRSourceMapPagination &pagination) {
  return buildHIRSourceMapDocument(
      module, filters, pagination, DebugMetadataHIRSourceMapOptions{});
}

DebugMetadataHIRSourceMapDocument buildHIRSourceMapDocument(
    const HIRModule &module, const DebugMetadataHIRSourceMapFilter &filters,
    const DebugMetadataHIRSourceMapPagination &pagination,
    const DebugMetadataHIRSourceMapOptions &options) {
  DebugMetadataHIRSourceMapDocument document;
  document.schemaVersion = options.schemaVersion;
  const bool includeResources =
      hirSourceMapIncludesResources(document.schemaVersion);
  document.filters = sourceMapFiltersForSchema(filters, includeResources);
  const DebugMetadataHIRSourceMapPagination effectivePagination =
      sourceMapPaginationForSchema(pagination, includeResources);
  DebugMetadataHIRSourceLocations sourceLocations =
      buildHIRSourceLocations(module, includeResources);
  if (options.sourceRemap) {
    applySourceRemap(sourceLocations, *options.sourceRemap);
  }
  const DebugMetadataHIRSourceLocations filteredLocations =
      filterHIRSourceLocations(sourceLocations, document.filters);
  document.hirSourceLocations =
      paginateHIRSourceLocations(filteredLocations, effectivePagination,
                                 includeResources);
  document.pagination =
      makeSourceMapPage(filteredLocations, effectivePagination,
                        document.hirSourceLocations, includeResources);
  document.categoryCounts =
      buildHIRSourceMapCategoryCounts(filteredLocations, includeResources);
  document.records = buildCombinedSourceMapRecords(
      filteredLocations, effectivePagination, includeResources);
  return document;
}

std::string debugMetadataJson(
    const HIRModule &module, TargetKind requestedTarget,
    const std::optional<DebugMetadataSourcePackageValidation>
        &sourcePackageValidation) {
  return debugMetadataJson(module, requestedTarget, sourcePackageValidation,
                           DebugMetadataOptions{});
}

std::string debugMetadataJson(
    const HIRModule &module, TargetKind requestedTarget,
    const std::optional<DebugMetadataSourcePackageValidation>
        &sourcePackageValidation,
    const DebugMetadataOptions &options) {
  return debugMetadataJson(buildDebugMetadataDocument(
      module, requestedTarget, sourcePackageValidation, options));
}

std::string hirSourceMapJson(const HIRModule &module,
                             const DebugMetadataHIRSourceMapFilter &filters,
                             const DebugMetadataHIRSourceMapPagination &pagination) {
  return hirSourceMapJson(
      buildHIRSourceMapDocument(module, filters, pagination));
}

std::string hirSourceMapJson(
    const HIRModule &module, const DebugMetadataHIRSourceMapFilter &filters,
    const DebugMetadataHIRSourceMapPagination &pagination,
    const DebugMetadataHIRSourceMapOptions &options) {
  return hirSourceMapJson(
      buildHIRSourceMapDocument(module, filters, pagination, options));
}

std::string hirSourceMapJson(
    const DebugMetadataHIRSourceMapDocument &document) {
  const bool includeResources =
      hirSourceMapIncludesResources(document.schemaVersion);
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": " << document.schemaVersion << ",\n"
      << "  \"filters\": ";
  appendHIRSourceMapFilters(out, document.filters, includeResources);
  out << ",\n"
      << "  \"pagination\": ";
  appendHIRSourceMapPagination(out, document.pagination, includeResources);
  out << ",\n"
      << "  \"categoryCounts\": ";
  appendHIRSourceMapCategoryCounts(out, document.categoryCounts,
                                   includeResources);
  out << ",\n"
      << "  \"records\": ";
  appendHIRSourceMapRecords(out, document.records, includeResources);
  out << ",\n"
      << "  \"hirSourceLocations\": ";
  appendHIRSourceLocations(out, document.hirSourceLocations, includeResources);
  out << "\n}\n";
  return out.str();
}

std::string debugMetadataJson(const DebugMetadataDocument &document) {
  std::ostringstream out;
  out << "{\n"
      << "  \"schemaVersion\": " << document.schemaVersion << ",\n"
      << "  \"targetDecision\": {"
      << "\"requestedTarget\":\""
      << escapeJson(document.targetDecision.requestedTarget) << "\""
      << ",\"selectedTarget\":\""
      << escapeJson(document.targetDecision.selectedTarget) << "\""
      << ",\"selectionReason\":\""
      << escapeJson(document.targetDecision.selectionReason) << "\""
      << ",\"selectedTargetNativeImplemented\":"
      << (document.targetDecision.selectedTargetNativeImplemented ? "true"
                                                                  : "false")
      << ",\"selectedTargetSourcePackageSupported\":"
      << (document.targetDecision.selectedTargetSourcePackageSupported ? "true"
                                                                       : "false")
      << ",\"selectedTargetPackageBuildSupported\":"
      << (document.targetDecision.selectedTargetPackageBuildSupported ? "true"
                                                                      : "false")
      << ",\"selectedTargetPackageMode\":\""
      << escapeJson(document.targetDecision.selectedTargetPackageMode) << "\""
      << ",\"selectedTargetMissingCapabilityCount\":"
      << document.targetDecision.selectedTargetMissingCapabilityCount
      << ",\"selectedTargetMissingCapabilities\":";
  appendInlineStringArray(out,
                          document.targetDecision
                              .selectedTargetMissingCapabilities);
  out << ",\"selectedTargetLegalizationCoreEvidenceIds\":";
  appendInlineStringArray(
      out, document.targetDecision.selectedTargetLegalizationCoreEvidenceIds);
  out << ",\"selectedTargetRequiredToolCount\":"
      << document.targetDecision.selectedTargetRequiredToolCount
      << ",\"selectedTargetMissingToolCount\":"
      << document.targetDecision.selectedTargetMissingToolCount
      << ",\"selectedTargetRequiredToolIds\":";
  appendInlineStringArray(
      out, document.targetDecision.selectedTargetRequiredToolIds);
  out << ",\"selectedTargetMissingToolIds\":";
  appendInlineStringArray(
      out, document.targetDecision.selectedTargetMissingToolIds);
  out << ",\"selectedTargetOptionalNativeToolMissing\":"
      << (document.targetDecision.selectedTargetOptionalNativeToolMissing
              ? "true"
              : "false")
      << ",\"selectedTargetOptionalNativeToolStatus\":\""
      << escapeJson(document.targetDecision.selectedTargetOptionalNativeToolStatus)
      << "\""
      << ",\"selectedTargetToolRequirementEvidenceIds\":";
  appendInlineStringArray(
      out, document.targetDecision.selectedTargetToolRequirementEvidenceIds);
  out << ",\"selectedTargetMissingCapabilityGroups\":";
  appendCapabilityGroups(
      out, document.targetDecision.selectedTargetMissingCapabilityGroups);
  out << ",\"selectedTargetDiagnosticCount\":"
      << document.targetDecision.selectedTargetDiagnosticCount
      << ",\"diagnostics\":";
  appendTargetDecisionDiagnostics(out, document.targetDecision.diagnostics);
  out << ",\"viableTargets\":";
  appendInlineStringArray(out, document.targetDecision.viableTargets);
  out << ",\"fallbackTargets\":";
  appendInlineStringArray(out, document.targetDecision.fallbackTargets);
  out << ",\"fallbackTargetRecordCount\":"
      << document.targetDecision.fallbackTargetRecordCount
      << ",\"fallbackTargetRecords\":";
  appendFallbackTargetRecords(out,
                              document.targetDecision.fallbackTargetRecords);
  out << ",\"nonViableTargets\":";
  appendInlineStringArray(out, document.targetDecision.nonViableTargets);
  out << "},\n"
      << "  \"targetCapabilities\": {\n"
      << "    \"defaultTarget\":\""
      << escapeJson(document.targetCapabilities.defaultTarget) << "\",\n"
      << "    \"summaries\": [";
  for (std::size_t i = 0; i < document.targetCapabilities.summaries.size();
       ++i) {
    const DebugMetadataTargetCapabilitySummary &summary =
        document.targetCapabilities.summaries[i];
    if (i != 0) {
      out << ",";
    }
    out << "\n      {"
        << "\"target\":\"" << escapeJson(summary.target) << "\""
        << ",\"nativeImplemented\":"
        << (summary.nativeImplemented ? "true" : "false")
        << ",\"sourcePackageSupported\":"
        << (summary.sourcePackageSupported ? "true" : "false")
        << ",\"packageBuildSupported\":"
        << (summary.packageBuildSupported ? "true" : "false")
        << ",\"packageMode\":\"" << escapeJson(summary.packageMode) << "\""
        << ",\"packageDecisionReason\":\""
        << escapeJson(summary.packageDecisionReason) << "\""
        << ",\"packageRankScore\":" << summary.packageRankScore
        << ",\"requiredCapabilityCount\":"
        << summary.requiredCapabilityCount
        << ",\"missingCapabilityCount\":" << summary.missingCapabilityCount
        << ",\"requiredCapabilities\":";
    appendInlineStringArray(out, summary.requiredCapabilities);
    out << ",\"missingCapabilities\":";
    appendInlineStringArray(out, summary.missingCapabilities);
    out << ",\"legalizationCoreEvidenceIds\":";
    appendInlineStringArray(out, summary.legalizationCoreEvidenceIds);
    out << ",\"requiredToolCount\":" << summary.requiredToolCount
        << ",\"missingToolCount\":" << summary.missingToolCount
        << ",\"requiredToolIds\":";
    appendInlineStringArray(out, summary.requiredToolIds);
    out << ",\"missingToolIds\":";
    appendInlineStringArray(out, summary.missingToolIds);
    out << ",\"optionalNativeToolMissing\":"
        << (summary.optionalNativeToolMissing ? "true" : "false")
        << ",\"optionalNativeToolStatus\":\""
        << escapeJson(summary.optionalNativeToolStatus) << "\""
        << ",\"toolRequirementEvidenceIds\":";
    appendInlineStringArray(out, summary.toolRequirementEvidenceIds);
    out << ",\"requiredCapabilityGroups\":";
    appendCapabilityGroups(out, summary.requiredCapabilityGroups);
    out << ",\"missingCapabilityGroups\":";
    appendCapabilityGroups(out, summary.missingCapabilityGroups);
    out << "}";
  }
  if (!document.targetCapabilities.summaries.empty()) {
    out << "\n    ";
  }
  out << "]\n"
      << "  }";
  if (document.sourcePackageValidation.has_value()) {
    const DebugMetadataSourcePackageValidation &validation =
        *document.sourcePackageValidation;
    out << ",\n"
        << "  \"sourcePackageValidation\": {"
        << "\"target\":\"" << escapeJson(validation.target) << "\""
        << ",\"tool\":\"" << escapeJson(validation.tool) << "\""
        << ",\"policy\":\"" << escapeJson(validation.policy) << "\""
        << ",\"status\":\"" << escapeJson(validation.status) << "\""
        << "}";
  }
  out << ",\n"
      << "  \"hirSourceLocations\": ";
  appendHIRSourceLocations(out, document.hirSourceLocations, false);
  out << ",\n"
      << "  \"manualTextureCompareKernelSummary\": {"
      << "\"totalCount\":"
      << document.manualTextureCompareKernelSummary.totalCount
      << ",\"staticNormalizedCount\":"
      << document.manualTextureCompareKernelSummary.staticNormalizedCount
      << ",\"staticNonNormalizedCount\":"
      << document.manualTextureCompareKernelSummary.staticNonNormalizedCount
      << ",\"staticZeroSumCount\":"
      << document.manualTextureCompareKernelSummary.staticZeroSumCount
      << ",\"dynamicCount\":"
      << document.manualTextureCompareKernelSummary.dynamicCount << "},\n"
      << "  \"manualTextureCompareKernelBuckets\": {\n";
  appendIndexArray(
      out, "staticNormalized",
      document.manualTextureCompareKernelBuckets.staticNormalized, true);
  appendIndexArray(
      out, "staticNonNormalized",
      document.manualTextureCompareKernelBuckets.staticNonNormalized, true);
  appendIndexArray(out, "staticZeroSum",
                   document.manualTextureCompareKernelBuckets.staticZeroSum,
                   true);
  appendIndexArray(out, "dynamic",
                   document.manualTextureCompareKernelBuckets.dynamic, false);
  out << "  },\n"
      << "  \"manualTextureCompareKernels\": [";
  for (std::size_t i = 0; i < document.manualTextureCompareKernels.size();
       ++i) {
    const DebugMetadataManualTextureCompareKernel &kernel =
        document.manualTextureCompareKernels[i];
    if (i != 0) {
      out << ",";
    }
    out << "\n    {"
        << "\"index\":" << kernel.index
        << ",\"stage\":\"" << escapeJson(kernel.stage) << "\""
        << ",\"entryPoint\":\"" << escapeJson(kernel.entryPoint) << "\""
        << ",\"function\":\"" << escapeJson(kernel.function) << "\""
        << ",\"operation\":\"" << escapeJson(kernel.operation) << "\""
        << ",\"sourceKind\":\"" << escapeJson(kernel.sourceKind) << "\""
        << ",\"canonicalOperation\":\""
        << escapeJson(kernel.canonicalOperation) << "\""
        << ",\"compatibilityAlias\":"
        << (kernel.compatibilityAlias ? "true" : "false")
        << ",\"weightClass\":\"" << escapeJson(kernel.weightClass) << "\""
        << ",\"tapCount\":" << kernel.tapCount << ",\"weightsStatic\":"
        << (kernel.weightsStatic ? "true" : "false");
    if (kernel.weightSum.has_value()) {
      out << ",\"weightSum\":" << *kernel.weightSum;
    }
    out << ",\"weightsZeroSum\":"
        << (kernel.weightsZeroSum ? "true" : "false")
        << ",\"weightsNormalized\":"
        << (kernel.weightsNormalized ? "true" : "false") << "}";
  }
  if (!document.manualTextureCompareKernels.empty()) {
    out << "\n  ";
  }
  out << "]\n"
      << "}\n";
  return out.str();
}

} // namespace crossgl
