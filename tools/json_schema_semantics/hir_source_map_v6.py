"""Semantic checks for hir-source-map-v6.schema.json."""

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


def validate_source_location_range(errors, path, location):
    if location["length"] <= 0:
        errors.append(f"{path}.length: expected > 0")
    for field in ("line", "column", "endLine", "endColumn"):
        if location[field] <= 0:
            errors.append(f"{path}.{field}: expected > 0")
    if (
        location["length"] > 0
        and location["endLine"] == location["line"]
        and location["endColumn"] <= location["column"]
    ):
        errors.append(f"{path}.endColumn: expected > column for same-line span")


def validate_optional_original_source_location_range(errors, path, record):
    if "originalLocation" in record:
        validate_source_location_range(
            errors,
            f"{path}.originalLocation",
            record["originalLocation"],
        )


def validate_hir_source_location_ranges(
    errors,
    path,
    locations,
    *,
    include_statements=False,
):
    for index, expression in enumerate(locations["expressions"]):
        validate_source_location_range(
            errors,
            f"{path}.expressions[{index}].location",
            expression["location"],
        )
        validate_optional_original_source_location_range(
            errors,
            f"{path}.expressions[{index}]",
            expression,
        )
    for index, type_record in enumerate(locations["types"]):
        validate_source_location_range(
            errors,
            f"{path}.types[{index}].location",
            type_record["location"],
        )
        validate_optional_original_source_location_range(
            errors,
            f"{path}.types[{index}]",
            type_record,
        )
    if include_statements:
        for index, statement in enumerate(locations["statements"]):
            validate_source_location_range(
                errors,
                f"{path}.statements[{index}].location",
                statement["location"],
            )
            validate_optional_original_source_location_range(
                errors,
                f"{path}.statements[{index}]",
                statement,
            )


def validate_semantics(instance):
    errors = []
    filters = instance["filters"]
    add_equal_error(
        errors,
        "$.filters.activeCount",
        filters["activeCount"],
        optional_field_count(
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
            ],
        ),
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
    validate_source_locations(errors, "$.hirSourceLocations", locations)
    validate_hir_source_location_ranges(errors, "$.hirSourceLocations", locations)
    add_length_count_error(
        errors,
        "$.pagination.expressionEmittedCount",
        pagination["expressionEmittedCount"],
        locations["expressions"],
        "$.hirSourceLocations.expressions length",
    )
    add_length_count_error(
        errors,
        "$.pagination.typeEmittedCount",
        pagination["typeEmittedCount"],
        locations["types"],
        "$.hirSourceLocations.types length",
    )

    categories = instance["categoryCounts"]
    add_equal_error(
        errors,
        "$.categoryCounts.recordTotalCount",
        categories["recordTotalCount"],
        categories["expressionTotalCount"] + categories["typeTotalCount"],
        "expressionTotalCount + typeTotalCount",
    )
    add_equal_error(
        errors,
        "$.pagination.expressionTotalCount",
        pagination["expressionTotalCount"],
        categories["expressionTotalCount"],
        "$.categoryCounts.expressionTotalCount",
    )
    add_equal_error(
        errors,
        "$.pagination.typeTotalCount",
        pagination["typeTotalCount"],
        categories["typeTotalCount"],
        "$.categoryCounts.typeTotalCount",
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
        categories["expressionTotalCount"],
    )
    validate_named_count_entries(
        errors,
        "$.categoryCounts.typeOwnerKinds",
        categories["typeOwnerKinds"],
        categories["typeTotalCount"],
    )
    validate_source_map_category_entries(
        errors,
        "$.categoryCounts",
        categories,
        locations,
    )

    for kind in ["expression", "type"]:
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

    records = instance["records"]
    items = records["items"]
    validate_source_map_filters(errors, filters, categories, locations, records)
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
    validate_source_map_record_payloads(
        errors,
        "$.records.items",
        records,
        locations,
        {
            "expression": categories["expressionTotalCount"],
            "type": categories["typeTotalCount"],
        },
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

    return errors
