"""Semantic checks for hir-source-map-v8.schema.json."""

from .common import active_field_count
from .common import add_equal_error
from .common import add_length_count_error
from .common import optional_field_count
from .common import validate_named_count_entries
from .common import validate_source_map_category_entries
from .common import validate_source_map_filters
from .common import validate_source_map_record_order
from .common import validate_source_map_record_payloads
from .common import validate_source_location_span
from .common import validate_source_locations
from .hir_source_map_v6 import validate_hir_source_location_ranges
from .hir_source_map_v6 import validate_optional_original_source_location_range
from .hir_source_map_v6 import validate_source_location_range
from .hir_source_map_v7 import validate_source_map_record_context


RECORD_KINDS = ("expression", "type", "statement", "resource")
RECORD_TOTAL_FIELD_BY_KIND = {
    "expression": "expressionTotalCount",
    "type": "typeTotalCount",
    "statement": "statementTotalCount",
    "resource": "resourceTotalCount",
}


def validate_source_map_record_kind_totals(errors, path, items, categories):
    emitted_counts = {record_kind: 0 for record_kind in RECORD_TOTAL_FIELD_BY_KIND}
    for item in items:
        emitted_counts[item["recordKind"]] += 1

    for record_kind, total_field in RECORD_TOTAL_FIELD_BY_KIND.items():
        emitted_count = emitted_counts[record_kind]
        total_count = categories[total_field]
        if emitted_count > total_count:
            errors.append(
                f"{path}: expected emitted {record_kind} record count <= "
                f"$.categoryCounts.{total_field} {total_count!r}, "
                f"got {emitted_count!r}"
            )


def validate_resource_source_location_context(errors, path, record):
    if record["entryPoint"] and not record["stage"]:
        errors.append(f"{path}.stage: expected non-empty when entryPoint is non-empty")
    if record["resourceRecordKind"] == "access":
        if not record.get("accessKind"):
            errors.append(
                f"{path}.accessKind: access resource records must declare accessKind"
            )
        return
    if record["resourceRecordKind"] != "access":
        for field in (
            "accessKind",
            "accessPath",
            "operation",
            "memberName",
            "indexExpression",
        ):
            if field in record:
                errors.append(
                    f"{path}.{field}: {record['resourceRecordKind']} resource "
                    "records must not declare access-only context"
                )


def validate_resource_location_ranges(errors, path, locations):
    for index, resource in enumerate(locations["resources"]):
        validate_source_location_range(
            errors,
            f"{path}.resources[{index}].location",
            resource["location"],
        )
        validate_optional_original_source_location_range(
            errors,
            f"{path}.resources[{index}]",
            resource,
        )


def location_records(locations):
    return (
        list(locations["expressions"])
        + list(locations["types"])
        + list(locations["statements"])
        + list(locations["resources"])
    )


def has_entrypoint_stage_anchor(records):
    return any(record["entryPoint"] and record["stage"] for record in records)


def validate_source_map_debug_boundary(errors, instance):
    filters = instance["filters"]
    if filters["activeCount"] != 0:
        return

    categories = instance["categoryCounts"]
    locations = instance["hirSourceLocations"]
    records = location_records(locations)
    if categories["recordTotalCount"] == 0:
        errors.append(
            "$.categoryCounts.recordTotalCount: unfiltered source map must "
            "contain at least one source anchor"
        )
    if not records:
        errors.append(
            "$.hirSourceLocations: unfiltered source map must emit at least "
            "one source anchor"
        )
        return
    if not has_entrypoint_stage_anchor(records):
        errors.append(
            "$.hirSourceLocations: expected at least one emitted source anchor "
            "with non-empty stage and entryPoint"
        )


def validate_v8_source_map_record_contexts(errors, path, locations):
    for index, expression in enumerate(locations["expressions"]):
        validate_source_map_record_context(
            errors,
            f"{path}.expressions[{index}]",
            expression,
        )
    for index, type_record in enumerate(locations["types"]):
        validate_source_map_record_context(
            errors,
            f"{path}.types[{index}]",
            type_record,
        )
    for index, statement in enumerate(locations["statements"]):
        validate_source_map_record_context(
            errors,
            f"{path}.statements[{index}]",
            statement,
            statement_record=True,
        )
    for index, resource in enumerate(locations["resources"]):
        validate_resource_source_location_context(
            errors,
            f"{path}.resources[{index}]",
            resource,
        )


def validate_unpaged_source_location_index_bounds(
    errors,
    path,
    locations,
    *,
    filters_active_count,
    pagination_active_count,
):
    if filters_active_count != 0 or pagination_active_count != 0:
        return

    for kind in RECORD_KINDS:
        count = locations[f"{kind}Count"]
        for index, record in enumerate(locations[f"{kind}s"]):
            record_index = record["index"]
            if record_index >= count:
                errors.append(
                    f"{path}.{kind}s[{index}].index: expected < "
                    f"{path}.{kind}Count {count!r}, got {record_index!r}"
                )


def validate_pagination_kind(errors, pagination, kind):
    offset = pagination[f"{kind}Offset"]
    total = pagination[f"{kind}TotalCount"]
    emitted = pagination[f"{kind}EmittedCount"]
    next_offset = pagination[f"{kind}NextOffset"]
    has_more = pagination[f"{kind}HasMore"]
    if offset > total:
        errors.append(
            f"$.pagination.{kind}Offset: expected <= {kind}TotalCount "
            f"{total!r}, got {offset!r}"
        )
    remaining = max(total - offset, 0)
    if emitted > remaining:
        errors.append(
            f"$.pagination.{kind}EmittedCount: expected <= remaining "
            f"{kind} records {remaining!r}, got {emitted!r}"
        )
    add_equal_error(
        errors,
        f"$.pagination.{kind}NextOffset",
        next_offset,
        min(offset + emitted, total),
        f"min({kind}Offset + {kind}EmittedCount, {kind}TotalCount)",
    )
    add_equal_error(
        errors,
        f"$.pagination.{kind}HasMore",
        has_more,
        next_offset < total,
        f"{kind}NextOffset < {kind}TotalCount",
    )
    if f"{kind}Limit" in pagination and emitted > pagination[f"{kind}Limit"]:
        errors.append(
            f"$.pagination.{kind}EmittedCount: expected <= "
            f"{kind}Limit {pagination[f'{kind}Limit']!r}, got {emitted!r}"
        )


def validate_record_stream(errors, records, categories, locations):
    items = records["items"]
    records_active_count = active_field_count(
        records,
        [
            ("enabled", bool),
            ("offset", lambda value: value != 0),
            ("limit", lambda _value: True),
        ],
    )
    add_equal_error(
        errors,
        "$.records.activeCount",
        records["activeCount"],
        records_active_count,
        "active record paging field count",
    )
    add_equal_error(
        errors,
        "$.records.totalCount",
        records["totalCount"],
        categories["recordTotalCount"],
        "$.categoryCounts.recordTotalCount",
    )
    add_length_count_error(
        errors,
        "$.records.emittedCount",
        records["emittedCount"],
        items,
        "$.records.items length",
    )
    if records["offset"] > records["totalCount"]:
        errors.append(
            "$.records.offset: expected <= totalCount "
            f"{records['totalCount']!r}, got {records['offset']!r}"
        )
    records_remaining = max(records["totalCount"] - records["offset"], 0)
    if records["emittedCount"] > records_remaining:
        errors.append(
            "$.records.emittedCount: expected <= remaining records "
            f"{records_remaining!r}, got {records['emittedCount']!r}"
        )
    if "limit" in records and records["emittedCount"] > records["limit"]:
        errors.append(
            f"$.records.emittedCount: expected <= limit {records['limit']!r}, "
            f"got {records['emittedCount']!r}"
        )
    if not records["enabled"] and items:
        errors.append("$.records.items: disabled records must not emit items")
    if not records["enabled"] and records["emittedCount"] != 0:
        errors.append("$.records.emittedCount: disabled records must emit zero items")
    if not records["enabled"]:
        add_equal_error(
            errors,
            "$.records.activeCount",
            records["activeCount"],
            0,
            "disabled record stream activeCount",
        )
        add_equal_error(
            errors,
            "$.records.offset",
            records["offset"],
            0,
            "disabled record stream offset",
        )
        add_equal_error(
            errors,
            "$.records.hasMore",
            records["hasMore"],
            False,
            "disabled record stream hasMore",
        )
        add_equal_error(
            errors,
            "$.records.nextOffset",
            records["nextOffset"],
            0,
            "disabled record stream nextOffset",
        )
        if "limit" in records:
            errors.append("$.records.limit: disabled records must not declare limit")
    validate_source_map_record_kind_totals(
        errors,
        "$.records.items",
        items,
        categories,
    )
    validate_source_map_record_order(errors, "$.records.items", items)
    for index, item in enumerate(items):
        add_equal_error(
            errors,
            f"$.records.items[{index}].cursor",
            item["cursor"],
            records["offset"] + index,
            "$.records.offset + item index",
        )
        record_kind = item["recordKind"]
        if record_kind == "resource":
            validate_resource_source_location_context(
                errors,
                f"$.records.items[{index}].resource",
                item["resource"],
            )
        else:
            validate_source_map_record_context(
                errors,
                f"$.records.items[{index}].{record_kind}",
                item[record_kind],
                statement_record=record_kind == "statement",
            )
        validate_source_location_span(
            errors,
            f"$.records.items[{index}].{record_kind}.location",
            item[record_kind]["location"],
        )
        validate_source_location_range(
            errors,
            f"$.records.items[{index}].{record_kind}.location",
            item[record_kind]["location"],
        )
        validate_optional_original_source_location_range(
            errors,
            f"$.records.items[{index}].{record_kind}",
            item[record_kind],
        )
    validate_source_map_record_payloads(
        errors,
        "$.records.items",
        records,
        locations,
        {
            "expression": categories["expressionTotalCount"],
            "type": categories["typeTotalCount"],
            "statement": categories["statementTotalCount"],
            "resource": categories["resourceTotalCount"],
        },
        include_statements=True,
        include_resources=True,
    )
    if records["enabled"] and (
        records["offset"] < records["totalCount"] or records["emittedCount"] != 0
    ):
        expected_next = min(
            records["offset"] + records["emittedCount"],
            records["totalCount"],
        )
        add_equal_error(
            errors,
            "$.records.nextOffset",
            records["nextOffset"],
            expected_next,
            "min(offset + emittedCount, totalCount)",
        )
        add_equal_error(
            errors,
            "$.records.hasMore",
            records["hasMore"],
            records["nextOffset"] < records["totalCount"],
            "nextOffset < totalCount",
        )


def validate_semantics(instance):
    errors = []
    filters = instance["filters"]
    filters_active_count = optional_field_count(
        filters,
        [
            "stage",
            "entryPoint",
            "function",
            "statementKind",
            "expressionKind",
            "expressionValue",
            "ownerKind",
            "ownerName",
            "resourceRecordKind",
            "resourceName",
            "resourceKind",
        ],
    )
    add_equal_error(
        errors,
        "$.filters.activeCount",
        filters["activeCount"],
        filters_active_count,
        "present filter field count",
    )

    pagination = instance["pagination"]
    pagination_active_count = active_field_count(
        pagination,
        [
            ("expressionOffset", lambda value: value != 0),
            ("expressionLimit", lambda _value: True),
            ("typeOffset", lambda value: value != 0),
            ("typeLimit", lambda _value: True),
            ("statementOffset", lambda value: value != 0),
            ("statementLimit", lambda _value: True),
            ("resourceOffset", lambda value: value != 0),
            ("resourceLimit", lambda _value: True),
        ],
    )
    add_equal_error(
        errors,
        "$.pagination.activeCount",
        pagination["activeCount"],
        pagination_active_count,
        "active pagination field count",
    )

    locations = instance["hirSourceLocations"]
    validate_source_locations(
        errors,
        "$.hirSourceLocations",
        locations,
        require_statements=True,
        include_resources=True,
    )
    validate_hir_source_location_ranges(
        errors,
        "$.hirSourceLocations",
        locations,
        include_statements=True,
    )
    validate_resource_location_ranges(errors, "$.hirSourceLocations", locations)
    validate_v8_source_map_record_contexts(errors, "$.hirSourceLocations", locations)
    validate_unpaged_source_location_index_bounds(
        errors,
        "$.hirSourceLocations",
        locations,
        filters_active_count=filters_active_count,
        pagination_active_count=pagination_active_count,
    )
    validate_source_map_debug_boundary(errors, instance)

    for kind in RECORD_KINDS:
        add_length_count_error(
            errors,
            f"$.pagination.{kind}EmittedCount",
            pagination[f"{kind}EmittedCount"],
            locations[f"{kind}s"],
            f"$.hirSourceLocations.{kind}s length",
        )

    categories = instance["categoryCounts"]
    add_equal_error(
        errors,
        "$.categoryCounts.recordTotalCount",
        categories["recordTotalCount"],
        categories["expressionTotalCount"]
        + categories["typeTotalCount"]
        + categories["statementTotalCount"]
        + categories["resourceTotalCount"],
        (
            "expressionTotalCount + typeTotalCount + statementTotalCount + "
            "resourceTotalCount"
        ),
    )
    for kind in RECORD_KINDS:
        add_equal_error(
            errors,
            f"$.pagination.{kind}TotalCount",
            pagination[f"{kind}TotalCount"],
            categories[f"{kind}TotalCount"],
            f"$.categoryCounts.{kind}TotalCount",
        )
    validate_named_count_entries(
        errors,
        "$.categoryCounts.expressionKinds",
        categories["expressionKinds"],
        categories["expressionTotalCount"],
    )
    validate_named_count_entries(
        errors,
        "$.categoryCounts.statementKinds",
        categories["statementKinds"],
        categories["statementTotalCount"],
    )
    validate_named_count_entries(
        errors,
        "$.categoryCounts.typeOwnerKinds",
        categories["typeOwnerKinds"],
        categories["typeTotalCount"],
    )
    validate_named_count_entries(
        errors,
        "$.categoryCounts.resourceRecordKinds",
        categories["resourceRecordKinds"],
        categories["resourceTotalCount"],
    )
    validate_named_count_entries(
        errors,
        "$.categoryCounts.resourceKinds",
        categories["resourceKinds"],
        categories["resourceTotalCount"],
    )
    validate_source_map_category_entries(
        errors,
        "$.categoryCounts",
        categories,
        locations,
        include_statements=True,
        include_resources=True,
    )

    for kind in RECORD_KINDS:
        validate_pagination_kind(errors, pagination, kind)

    records = instance["records"]
    validate_source_map_filters(
        errors,
        filters,
        categories,
        locations,
        records,
        include_statements=True,
        include_resources=True,
    )
    validate_record_stream(errors, records, categories, locations)
    return errors
