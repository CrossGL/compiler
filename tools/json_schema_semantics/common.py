"""Shared semantic validation helpers for CrossGL JSON schema fixtures."""

from package_target_contracts import (
    PACKAGE_DEBUG_ARTIFACT_COUNT,
    PACKAGE_PATH_ARTIFACTS,
    PACKAGE_TARGET_CONTRACTS,
    PACKAGE_TARGET_MIN_ARTIFACT_COUNTS,
    PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS,
)

NATIVE_ARTIFACT_DESCRIPTOR = "nativeArtifactDescriptor"

PACKAGE_TARGET_NATIVE_SUMMARY_STATUS = {
    "metal": "emitted",
}

TARGET_EXPLANATION_TARGET_ORDER = {
    "metal": 0,
    "vulkan": 1,
    "directx": 2,
    "opengl": 3,
}

TARGET_EXPLANATION_PACKAGE_MODE_EVIDENCE = {
    "native": {
        "metal": "metal.backend.native-metal-package",
        "vulkan": "vulkan.backend.vulkan-prototype-package",
    },
    "source-package": {
        "directx": "directx.backend.hlsl-lowering",
        "opengl": "opengl.backend.glsl-lowering",
    },
}


SOURCE_MAP_RECORD_KIND_RANK = {
    "type": 0,
    "statement": 1,
    "expression": 2,
    "resource": 3,
}

SOURCE_MAP_RECORD_ARRAY_FIELD = {
    "expression": "expressions",
    "type": "types",
    "statement": "statements",
    "resource": "resources",
}

SOURCE_MAP_FILTER_FIELDS_BY_RECORD_KIND = {
    "expression": (
        ("stage", "stage"),
        ("entryPoint", "entryPoint"),
        ("function", "function"),
        ("statementKind", "statementKind"),
        ("expressionKind", "kind"),
        ("expressionValue", "value"),
    ),
    "type": (
        ("stage", "stage"),
        ("entryPoint", "entryPoint"),
        ("function", "function"),
        ("ownerKind", "ownerKind"),
        ("ownerName", "ownerName"),
    ),
    "statement": (
        ("stage", "stage"),
        ("entryPoint", "entryPoint"),
        ("function", "function"),
        ("statementKind", "statementKind"),
    ),
    "resource": (
        ("stage", "stage"),
        ("entryPoint", "entryPoint"),
        ("resourceRecordKind", "resourceRecordKind"),
        ("resourceName", "resourceName"),
        ("resourceKind", "resourceKind"),
    ),
}

SOURCE_MAP_EXCLUDING_FILTER_FIELDS_BY_RECORD_KIND = {
    "expression": (
        "ownerKind",
        "ownerName",
        "resourceRecordKind",
        "resourceName",
        "resourceKind",
    ),
    "type": (
        "statementKind",
        "expressionKind",
        "expressionValue",
        "resourceRecordKind",
        "resourceName",
        "resourceKind",
    ),
    "statement": (
        "expressionKind",
        "expressionValue",
        "ownerKind",
        "ownerName",
        "resourceRecordKind",
        "resourceName",
        "resourceKind",
    ),
    "resource": (
        "function",
        "statementKind",
        "expressionKind",
        "expressionValue",
        "ownerKind",
        "ownerName",
    ),
}


def add_equal_error(errors, path, actual, expected, expected_label):
    if actual != expected:
        errors.append(f"{path}: expected {expected_label} {expected!r}, got {actual!r}")


def add_at_least_error(errors, path, actual, minimum, minimum_label):
    if actual < minimum:
        errors.append(
            f"{path}: expected >= {minimum_label} {minimum!r}, got {actual!r}"
        )


def add_length_count_error(errors, path, actual, values, values_label):
    add_equal_error(errors, path, actual, len(values), values_label)


def validate_diagnostic_message(errors, path, diagnostic):
    if diagnostic["message"].strip() == "":
        errors.append(f"{path}.message: expected non-empty diagnostic message")


def validate_normalized_package_path(errors, path, package_path):
    if "\\" in package_path:
        errors.append(f"{path}: expected normalized '/' path separators")


def validate_package_artifact_requirements(
    errors,
    path,
    target,
    requirements,
):
    if requirements["target"] != target:
        errors.append(f"{path}.target: must match package target")
    contract = next(
        (
            contract
            for contract in PACKAGE_TARGET_CONTRACTS
            if contract.target == target
        ),
        None,
    )
    if contract is not None:
        expected_mode = (
            "source-package" if contract.allows_planned_native_binary else "native"
        )
        if requirements["packageMode"] != expected_mode:
            errors.append(
                f"{path}.packageMode: expected target contract mode {expected_mode!r}"
            )
        if (
            requirements["requiresNativeBinaryStatus"]
            != contract.requires_native_binary_status
            or requirements["allowsPlannedNativeBinary"]
            != contract.allows_planned_native_binary
            or requirements["allowsPlannedNativeSourceEvidence"]
            != contract.allows_planned_native_source_evidence
        ):
            errors.append(f"{path}: native binary policy must match target contract")
        expected_artifacts = list(contract.required_path_artifacts)
        if requirements["requiredPathArtifacts"] != expected_artifacts:
            errors.append(
                f"{path}.requiredPathArtifacts: expected target contract "
                f"artifacts {expected_artifacts!r}"
            )
    if (
        requirements["allowsPlannedNativeSourceEvidence"]
        and not requirements["allowsPlannedNativeBinary"]
    ):
        errors.append(
            f"{path}.allowsPlannedNativeSourceEvidence: "
            "requires allowsPlannedNativeBinary"
        )
    required_names = requirements["requiredPathArtifacts"]
    if len(required_names) != len(set(required_names)):
        errors.append(f"{path}.requiredPathArtifacts: duplicate artifact names")
    for index, name in enumerate(required_names):
        if name not in PACKAGE_PATH_ARTIFACTS:
            errors.append(
                f"{path}.requiredPathArtifacts[{index}]: expected known path artifact"
            )


def validate_release_package_artifacts_against_requirements(
    errors,
    path,
    package,
    *,
    require_existing=True,
):
    requirements = package["packageArtifactRequirements"]
    validate_package_artifact_requirements(
        errors, f"{path}.packageArtifactRequirements", package["target"], requirements
    )
    artifacts = {artifact["name"]: artifact for artifact in package["artifacts"]}
    planned_native_binary_allowed = (
        requirements["allowsPlannedNativeBinary"]
        and package["nativeBinaryStatus"] == "planned"
    )
    for name in requirements["requiredPathArtifacts"]:
        artifact = artifacts.get(name)
        if artifact is None:
            if name == "nativeBinary" and planned_native_binary_allowed:
                continue
            errors.append(f"{path}.artifacts.{name}: required artifact missing")
        elif (
            require_existing
            and not artifact["exists"]
            and not (name == "nativeBinary" and planned_native_binary_allowed)
        ):
            errors.append(f"{path}.artifacts.{name}: required artifact must exist")

    has_native_binary = "nativeBinary" in artifacts
    if (
        package["nativeBinaryStatus"] is not None
        and not requirements["requiresNativeBinaryStatus"]
    ):
        errors.append(
            f"{path}.nativeBinaryStatus: recorded requirements do not allow "
            "nativeBinaryStatus"
        )
    elif (
        package["nativeBinaryStatus"] is not None
        and not has_native_binary
        and not planned_native_binary_allowed
    ):
        errors.append(
            f"{path}.nativeBinaryStatus: nativeBinaryStatus requires nativeBinary"
        )
    elif (
        requirements["requiresNativeBinaryStatus"]
        and package["nativeBinaryStatus"] is None
    ):
        errors.append(
            f"{path}.nativeBinaryStatus: recorded requirements require "
            "nativeBinaryStatus"
        )

    native_binary = artifacts.get("nativeBinary")
    native_binary_exists = native_binary is not None and (
        not require_existing or native_binary.get("exists") is True
    )
    native_ready = package["nativeBinaryStatus"] in {"emitted", "validated"} or (
        requirements["packageMode"] == "native" and native_binary_exists
    )
    planned_source_evidence = (
        package["nativeBinaryStatus"] == "planned"
        and requirements["allowsPlannedNativeSourceEvidence"]
    )
    descriptor = artifacts.get(NATIVE_ARTIFACT_DESCRIPTOR)
    if (native_ready or planned_source_evidence) and descriptor is None:
        descriptor_context = (
            "planned native source evidence"
            if planned_source_evidence and not native_ready
            else "native readiness"
        )
        errors.append(
            f"{path}.artifacts.{NATIVE_ARTIFACT_DESCRIPTOR}: "
            f"{descriptor_context} requires descriptor artifact evidence"
        )
    elif native_ready and require_existing and descriptor.get("exists") is not True:
        errors.append(
            f"{path}.artifacts.{NATIVE_ARTIFACT_DESCRIPTOR}: "
            "descriptor artifact must exist when native readiness is recorded"
        )


def validate_native_binary_state(errors, path, package):
    status = package["nativeBinaryStatus"]
    if status is None:
        return

    requirements = package["packageArtifactRequirements"]
    native_binary = None
    for artifact in package["artifacts"]:
        if artifact["name"] == "nativeBinary":
            native_binary = artifact
            break

    if status == "planned":
        if not requirements["allowsPlannedNativeBinary"]:
            errors.append(
                f"{path}.nativeBinaryStatus: planned nativeBinaryStatus "
                "requires allowsPlannedNativeBinary"
            )
        if native_binary is not None and native_binary["exists"]:
            errors.append(
                f"{path}.artifacts.nativeBinary: planned nativeBinaryStatus "
                "requires missing nativeBinary artifact"
            )
        return

    if status in ("emitted", "validated") and native_binary is not None:
        if not native_binary["exists"]:
            errors.append(
                f"{path}.artifacts.nativeBinary: nativeBinaryStatus {status!r} "
                "requires existing nativeBinary artifact"
            )


def validate_package_summary_minimums(
    errors,
    path,
    summary,
    context_label,
    artifact_context_label=None,
    enforce_target_native_status=True,
):
    if artifact_context_label is None:
        artifact_context_label = context_label

    target = summary["target"]
    if (
        enforce_target_native_status
        and target in PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS
        and summary["nativeBinaryStatus"] is None
    ):
        errors.append(
            f"{path}.nativeBinaryStatus: "
            f"{target} {context_label} requires nativeBinaryStatus"
        )
    if (
        target not in PACKAGE_TARGETS_REQUIRING_NATIVE_STATUS
        and summary["nativeBinaryStatus"] is not None
    ):
        allowed_status = PACKAGE_TARGET_NATIVE_SUMMARY_STATUS.get(target)
        if allowed_status is None:
            errors.append(
                f"{path}.nativeBinaryStatus: "
                f"{target} {context_label} must not declare nativeBinaryStatus"
            )
        elif summary["nativeBinaryStatus"] != allowed_status:
            errors.append(
                f"{path}.nativeBinaryStatus: "
                f"{target} {context_label} may only report nativeBinaryStatus "
                f"{allowed_status!r}"
            )

    minimum_artifacts = PACKAGE_TARGET_MIN_ARTIFACT_COUNTS[target]
    if summary["debugArtifactsPresent"]:
        minimum_artifacts += PACKAGE_DEBUG_ARTIFACT_COUNT
    artifact_count = summary["artifactCount"]
    if artifact_count < minimum_artifacts:
        errors.append(
            f"{path}.artifactCount: expected {artifact_context_label} "
            f"{target} artifact count >= {minimum_artifacts}, got {artifact_count}"
        )


def optional_field_count(document, fields):
    return sum(1 for field in fields if field in document)


def active_field_count(document, field_specs):
    return sum(
        1
        for field, is_active in field_specs
        if field in document and is_active(document[field])
    )


def sum_count_entries(entries):
    return sum(entry["count"] for entry in entries)


def validate_named_count_entries(errors, path, entries, expected_total):
    add_equal_error(
        errors,
        path,
        sum_count_entries(entries),
        expected_total,
        "sum of entry counts",
    )
    names = [entry["name"] for entry in entries]
    if len(names) != len(set(names)):
        errors.append(f"{path}: duplicate category names")
    if names != sorted(names):
        errors.append(f"{path}: category names must be sorted")


def count_category_entries(records, field):
    counts = {}
    for record in records:
        name = record[field]
        counts[name] = counts.get(name, 0) + 1
    return [{"name": name, "count": counts[name]} for name in sorted(counts)]


def validate_category_entries_match_records(
    errors,
    path,
    entries,
    expected_entries,
    label,
):
    if entries != expected_entries:
        errors.append(
            f"{path}: expected {label} category counts to match complete "
            "source-location records"
        )


def validate_source_map_category_entries(
    errors,
    path,
    categories,
    locations,
    include_statements=False,
    include_resources=False,
):
    expressions = locations["expressions"]
    if len(expressions) == categories["expressionTotalCount"]:
        validate_category_entries_match_records(
            errors,
            f"{path}.expressionKinds",
            categories["expressionKinds"],
            count_category_entries(expressions, "kind"),
            "expression kind",
        )
        if not include_statements:
            validate_category_entries_match_records(
                errors,
                f"{path}.statementKinds",
                categories["statementKinds"],
                count_category_entries(expressions, "statementKind"),
                "statement kind",
            )

    types = locations["types"]
    if len(types) == categories["typeTotalCount"]:
        validate_category_entries_match_records(
            errors,
            f"{path}.typeOwnerKinds",
            categories["typeOwnerKinds"],
            count_category_entries(types, "ownerKind"),
            "type owner kind",
        )

    if include_statements:
        statements = locations["statements"]
        if len(statements) == categories["statementTotalCount"]:
            validate_category_entries_match_records(
                errors,
                f"{path}.statementKinds",
                categories["statementKinds"],
                count_category_entries(statements, "statementKind"),
                "statement kind",
            )

    if include_resources:
        resources = locations["resources"]
        if len(resources) == categories["resourceTotalCount"]:
            validate_category_entries_match_records(
                errors,
                f"{path}.resourceRecordKinds",
                categories["resourceRecordKinds"],
                count_category_entries(resources, "resourceRecordKind"),
                "resource record kind",
            )
            validate_category_entries_match_records(
                errors,
                f"{path}.resourceKinds",
                categories["resourceKinds"],
                count_category_entries(resources, "resourceKind"),
                "resource kind",
            )


def first_present_field(document, fields):
    for field in fields:
        if field in document:
            return field
    return None


def validate_source_map_filter_total_counts(
    errors,
    path,
    filters,
    categories,
    include_statements=False,
    include_resources=False,
):
    expression_excluding_field = first_present_field(
        filters,
        SOURCE_MAP_EXCLUDING_FILTER_FIELDS_BY_RECORD_KIND["expression"],
    )
    if expression_excluding_field is not None:
        add_equal_error(
            errors,
            f"{path}.expressionTotalCount",
            categories["expressionTotalCount"],
            0,
            f"{expression_excluding_field} filter excludes expression records",
        )

    type_excluding_field = first_present_field(
        filters,
        SOURCE_MAP_EXCLUDING_FILTER_FIELDS_BY_RECORD_KIND["type"],
    )
    if type_excluding_field is not None:
        add_equal_error(
            errors,
            f"{path}.typeTotalCount",
            categories["typeTotalCount"],
            0,
            f"{type_excluding_field} filter excludes type records",
        )

    if include_statements:
        statement_excluding_field = first_present_field(
            filters,
            SOURCE_MAP_EXCLUDING_FILTER_FIELDS_BY_RECORD_KIND["statement"],
        )
        if statement_excluding_field is not None:
            add_equal_error(
                errors,
                f"{path}.statementTotalCount",
                categories["statementTotalCount"],
                0,
                f"{statement_excluding_field} filter excludes statement records",
            )

    if include_resources:
        resource_excluding_field = first_present_field(
            filters,
            SOURCE_MAP_EXCLUDING_FILTER_FIELDS_BY_RECORD_KIND["resource"],
        )
        if resource_excluding_field is not None:
            add_equal_error(
                errors,
                f"{path}.resourceTotalCount",
                categories["resourceTotalCount"],
                0,
                f"{resource_excluding_field} filter excludes resource records",
            )


def validate_source_map_record_filters(errors, path, filters, record_kind, record):
    excluding_field = first_present_field(
        filters,
        SOURCE_MAP_EXCLUDING_FILTER_FIELDS_BY_RECORD_KIND[record_kind],
    )
    if excluding_field is not None:
        errors.append(
            f"{path}: {record_kind} records must not be emitted when "
            f"{excluding_field} filter is active"
        )
        return

    for filter_field, record_field in SOURCE_MAP_FILTER_FIELDS_BY_RECORD_KIND[
        record_kind
    ]:
        if filter_field in filters and record[record_field] != filters[filter_field]:
            errors.append(
                f"{path}.{record_field}: expected to match active "
                f"{filter_field} filter {filters[filter_field]!r}, "
                f"got {record[record_field]!r}"
            )


def validate_source_map_filters(
    errors,
    filters,
    categories,
    locations,
    records,
    include_statements=False,
    include_resources=False,
):
    validate_source_map_filter_total_counts(
        errors,
        "$.categoryCounts",
        filters,
        categories,
        include_statements=include_statements,
        include_resources=include_resources,
    )

    for index, expression in enumerate(locations["expressions"]):
        validate_source_map_record_filters(
            errors,
            f"$.hirSourceLocations.expressions[{index}]",
            filters,
            "expression",
            expression,
        )
    for index, type_record in enumerate(locations["types"]):
        validate_source_map_record_filters(
            errors,
            f"$.hirSourceLocations.types[{index}]",
            filters,
            "type",
            type_record,
        )
    if include_statements:
        for index, statement in enumerate(locations["statements"]):
            validate_source_map_record_filters(
                errors,
                f"$.hirSourceLocations.statements[{index}]",
                filters,
                "statement",
                statement,
            )
    if include_resources:
        for index, resource in enumerate(locations["resources"]):
            validate_source_map_record_filters(
                errors,
                f"$.hirSourceLocations.resources[{index}]",
                filters,
                "resource",
                resource,
            )

    for index, item in enumerate(records["items"]):
        record_kind = item["recordKind"]
        validate_source_map_record_filters(
            errors,
            f"$.records.items[{index}].{record_kind}",
            filters,
            record_kind,
            item[record_kind],
        )


def validate_source_location_indices(errors, path, records, record_label):
    previous_index = None
    for array_index, record in enumerate(records):
        record_index = record["index"]
        if previous_index is not None and record_index <= previous_index:
            errors.append(
                f"{path}[{array_index}].index: expected {record_label} "
                f"indexes to be strictly increasing"
            )
        previous_index = record_index


def validate_source_locations(
    errors,
    path,
    locations,
    require_statements=False,
    include_resources=False,
):
    expressions = locations["expressions"]
    types = locations["types"]
    validate_source_location_indices(
        errors,
        f"{path}.expressions",
        expressions,
        "expression",
    )
    validate_source_location_indices(errors, f"{path}.types", types, "type")
    for index, expression in enumerate(expressions):
        validate_source_location_span(
            errors,
            f"{path}.expressions[{index}].location",
            expression["location"],
        )
        validate_optional_original_source_location_span(
            errors,
            f"{path}.expressions[{index}]",
            expression,
        )
    for index, type_record in enumerate(types):
        validate_source_location_span(
            errors,
            f"{path}.types[{index}].location",
            type_record["location"],
        )
        validate_optional_original_source_location_span(
            errors,
            f"{path}.types[{index}]",
            type_record,
        )
    add_length_count_error(
        errors,
        f"{path}.expressionWithLocationCount",
        locations["expressionWithLocationCount"],
        expressions,
        f"{path}.expressions length",
    )
    add_length_count_error(
        errors,
        f"{path}.typeWithLocationCount",
        locations["typeWithLocationCount"],
        types,
        f"{path}.types length",
    )
    add_at_least_error(
        errors,
        f"{path}.expressionCount",
        locations["expressionCount"],
        locations["expressionWithLocationCount"],
        f"{path}.expressionWithLocationCount",
    )
    add_at_least_error(
        errors,
        f"{path}.typeCount",
        locations["typeCount"],
        locations["typeWithLocationCount"],
        f"{path}.typeWithLocationCount",
    )
    if require_statements:
        statements = locations["statements"]
        validate_source_location_indices(
            errors,
            f"{path}.statements",
            statements,
            "statement",
        )
        for index, statement in enumerate(statements):
            validate_source_location_span(
                errors,
                f"{path}.statements[{index}].location",
                statement["location"],
            )
            validate_optional_original_source_location_span(
                errors,
                f"{path}.statements[{index}]",
                statement,
            )
        add_length_count_error(
            errors,
            f"{path}.statementWithLocationCount",
            locations["statementWithLocationCount"],
            statements,
            f"{path}.statements length",
        )
        add_at_least_error(
            errors,
            f"{path}.statementCount",
            locations["statementCount"],
            locations["statementWithLocationCount"],
            f"{path}.statementWithLocationCount",
        )
    if include_resources:
        resources = locations["resources"]
        validate_source_location_indices(
            errors,
            f"{path}.resources",
            resources,
            "resource",
        )
        for index, resource in enumerate(resources):
            validate_source_location_span(
                errors,
                f"{path}.resources[{index}].location",
                resource["location"],
            )
            validate_optional_original_source_location_span(
                errors,
                f"{path}.resources[{index}]",
                resource,
            )
        add_length_count_error(
            errors,
            f"{path}.resourceWithLocationCount",
            locations["resourceWithLocationCount"],
            resources,
            f"{path}.resources length",
        )
        add_at_least_error(
            errors,
            f"{path}.resourceCount",
            locations["resourceCount"],
            locations["resourceWithLocationCount"],
            f"{path}.resourceWithLocationCount",
        )


def validate_source_location_span(errors, path, location):
    if location["endOffset"] != location["offset"] + location["length"]:
        errors.append(f"{path}.endOffset: expected offset + length")
    if location["endLine"] < location["line"]:
        errors.append(f"{path}.endLine: expected >= line")
    if (
        location["endLine"] == location["line"]
        and location["endColumn"] < location["column"]
    ):
        errors.append(f"{path}.endColumn: expected >= column on same line")


def validate_optional_original_source_location_span(errors, path, record):
    if "originalLocation" in record:
        validate_source_location_span(
            errors,
            f"{path}.originalLocation",
            record["originalLocation"],
        )


def source_map_record_sort_key(record_kind, record):
    location = record["location"]
    return (
        location["offset"],
        location["endOffset"],
        SOURCE_MAP_RECORD_KIND_RANK[record_kind],
        record["index"],
    )


def source_map_item_sort_key(item):
    record_kind = item["recordKind"]
    return source_map_record_sort_key(record_kind, item[record_kind])


def validate_source_map_record_order(errors, path, items):
    for index in range(1, len(items)):
        if source_map_item_sort_key(items[index - 1]) > source_map_item_sort_key(
            items[index]
        ):
            errors.append(
                f"{path}[{index}]: expected combined records sorted by "
                "location offset, endOffset, record kind, and source index"
            )


def source_map_location_arrays_are_complete(
    locations,
    total_counts,
    include_statements=False,
    include_resources=False,
):
    record_kinds = ["expression", "type"]
    if include_statements:
        record_kinds.append("statement")
    if include_resources:
        record_kinds.append("resource")
    return all(
        len(locations[SOURCE_MAP_RECORD_ARRAY_FIELD[record_kind]])
        == total_counts[record_kind]
        for record_kind in record_kinds
    )


def expected_source_map_records(
    locations,
    include_statements=False,
    include_resources=False,
):
    record_refs = []
    record_kinds = ["expression", "type"]
    if include_statements:
        record_kinds.append("statement")
    if include_resources:
        record_kinds.append("resource")
    for record_kind in record_kinds:
        array_field = SOURCE_MAP_RECORD_ARRAY_FIELD[record_kind]
        for record in locations[array_field]:
            record_refs.append((record_kind, record))
    return sorted(
        record_refs,
        key=lambda record_ref: source_map_record_sort_key(
            record_ref[0],
            record_ref[1],
        ),
    )


def validate_source_map_record_payloads(
    errors,
    path,
    records,
    locations,
    total_counts,
    include_statements=False,
    include_resources=False,
):
    if not records["enabled"] or not source_map_location_arrays_are_complete(
        locations,
        total_counts,
        include_statements=include_statements,
        include_resources=include_resources,
    ):
        return

    expected_records = expected_source_map_records(
        locations,
        include_statements=include_statements,
        include_resources=include_resources,
    )
    for index, item in enumerate(records["items"]):
        cursor = records["offset"] + index
        if cursor >= len(expected_records):
            continue
        expected_kind, expected_record = expected_records[cursor]
        if (
            item["recordKind"] != expected_kind
            or item[expected_kind] != expected_record
        ):
            errors.append(
                f"{path}[{index}]: expected cursor {cursor} to match "
                f"{expected_kind} source-location index {expected_record['index']}"
            )


def validate_capability_groups(errors, path, groups, flat_capabilities):
    group_total = 0
    for index, group in enumerate(groups):
        group_path = f"{path}[{index}]"
        capabilities = group["capabilities"]
        add_length_count_error(
            errors,
            f"{group_path}.count",
            group["count"],
            capabilities,
            f"{group_path}.capabilities length",
        )
        group_total += group["count"]
    add_equal_error(
        errors,
        path,
        group_total,
        len(flat_capabilities),
        "flat capability list length",
    )


def validate_unique_values(errors, path, values, value_label):
    seen = set()
    for value in values:
        if value in seen:
            errors.append(f"{path}: duplicate {value_label} {value!r}")
        seen.add(value)


def validate_capability_target_prefix(errors, path, target, capabilities):
    target_prefix = f"{target}."
    for index, capability in enumerate(capabilities):
        if not capability.startswith(target_prefix):
            errors.append(
                f"{path}[{index}]: expected target capability prefix "
                f"{target_prefix!r}, got {capability!r}"
            )


def expected_package_mode(record):
    if not record["packageBuildSupported"]:
        return "unsupported"
    if record["nativeImplemented"]:
        return "native"
    if record["sourcePackageSupported"]:
        return "source-package"
    return "unsupported"


def validate_target_record_package_decision(errors, path, record):
    target = record["target"]
    required_capabilities = record["requiredCapabilities"]
    missing_capabilities = record["missingCapabilities"]
    add_length_count_error(
        errors,
        f"{path}.requiredCapabilityCount",
        record["requiredCapabilityCount"],
        required_capabilities,
        f"{path}.requiredCapabilities length",
    )
    add_length_count_error(
        errors,
        f"{path}.missingCapabilityCount",
        record["missingCapabilityCount"],
        missing_capabilities,
        f"{path}.missingCapabilities length",
    )
    validate_unique_values(
        errors,
        f"{path}.requiredCapabilities",
        required_capabilities,
        "required capability",
    )
    validate_unique_values(
        errors,
        f"{path}.missingCapabilities",
        missing_capabilities,
        "missing capability",
    )
    validate_capability_target_prefix(
        errors,
        f"{path}.requiredCapabilities",
        target,
        required_capabilities,
    )
    validate_capability_target_prefix(
        errors,
        f"{path}.missingCapabilities",
        target,
        missing_capabilities,
    )

    required_set = set(required_capabilities)
    for capability in missing_capabilities:
        if capability not in required_set:
            errors.append(
                f"{path}.missingCapabilities: expected missing capability "
                f"{capability!r} to appear in requiredCapabilities"
            )

    mode = expected_package_mode(record)
    expected_reason = {
        "native": "native-package-available",
        "source-package": "source-package-available",
        "unsupported": "unsupported",
    }[mode]
    expected_rank = {
        "native": 0,
        "source-package": 1,
        "unsupported": 2,
    }[mode]

    add_equal_error(
        errors,
        f"{path}.packageMode",
        record["packageMode"],
        mode,
        "package flags",
    )
    add_equal_error(
        errors,
        f"{path}.packageBuildSupported",
        record["packageBuildSupported"],
        mode != "unsupported",
        "package mode support",
    )
    add_equal_error(
        errors,
        f"{path}.packageDecisionReason",
        record["packageDecisionReason"],
        expected_reason,
        "package mode reason",
    )
    add_equal_error(
        errors,
        f"{path}.packageRankScore",
        record["packageRankScore"],
        expected_rank,
        "package mode rank",
    )

    if mode == "unsupported":
        if not missing_capabilities:
            errors.append(
                f"{path}.missingCapabilities: unsupported target requires "
                "at least one missing capability"
            )
        return

    mode_evidence = TARGET_EXPLANATION_PACKAGE_MODE_EVIDENCE.get(mode, {})
    evidence_capability = mode_evidence.get(target)
    if evidence_capability is None:
        errors.append(
            f"{path}.packageMode: target {target!r} does not support "
            f"package mode {mode!r}"
        )
        return

    if evidence_capability not in required_set:
        errors.append(
            f"{path}.requiredCapabilities: {mode} support requires "
            f"{evidence_capability!r}"
        )
    if evidence_capability in set(missing_capabilities):
        errors.append(
            f"{path}.missingCapabilities: {mode} support cannot miss "
            f"{evidence_capability!r}"
        )
    if mode == "native" and missing_capabilities:
        errors.append(
            f"{path}.missingCapabilities: native support requires no "
            "missing capabilities"
        )


def recommended_target_record(targets, default_target):
    recommended = None
    for record in targets:
        if not record["packageBuildSupported"]:
            continue
        if (
            recommended is None
            or record["packageRankScore"] < recommended["packageRankScore"]
            or (
                record["packageRankScore"] == recommended["packageRankScore"]
                and record["target"] == default_target
                and recommended["target"] != default_target
            )
        ):
            recommended = record
    return recommended


def validate_target_explanation_document(errors, path, document):
    targets = document["targets"]
    target_names = [record["target"] for record in targets]
    validate_unique_values(errors, f"{path}.targets", target_names, "target record")
    if len(target_names) == len(set(target_names)):
        target_order = [TARGET_EXPLANATION_TARGET_ORDER[name] for name in target_names]
        if target_order != sorted(target_order):
            errors.append(f"{path}.targets: target records must be in target order")
    if document["defaultTarget"] not in target_names:
        errors.append(f"{path}.defaultTarget: expected target to appear in targets")

    for index, record in enumerate(targets):
        validate_target_record_package_decision(
            errors,
            f"{path}.targets[{index}]",
            record,
        )

    buildable_targets = [
        record for record in targets if record["packageBuildSupported"]
    ]
    add_equal_error(
        errors,
        f"{path}.buildableTargetCount",
        document["buildableTargetCount"],
        len(buildable_targets),
        "buildable target count",
    )

    recommended = recommended_target_record(targets, document["defaultTarget"])
    if recommended is None:
        add_equal_error(
            errors,
            f"{path}.recommendedTarget",
            document["recommendedTarget"],
            None,
            "no buildable target",
        )
        add_equal_error(
            errors,
            f"{path}.recommendedPackageMode",
            document["recommendedPackageMode"],
            None,
            "no buildable target",
        )
        return

    add_equal_error(
        errors,
        f"{path}.recommendedTarget",
        document["recommendedTarget"],
        recommended["target"],
        "recommended target",
    )
    add_equal_error(
        errors,
        f"{path}.recommendedPackageMode",
        document["recommendedPackageMode"],
        expected_package_mode(recommended),
        "recommended package mode",
    )


def validate_array_dimensions(errors, path, dimensions):
    product = 1
    complete_fixed_product = bool(dimensions)
    for index, dimension in enumerate(dimensions):
        dimension_path = f"{path}[{index}]"
        kind = dimension["kind"]
        source = dimension["source"]
        has_element_count = "elementCount" in dimension
        if kind == "runtime":
            if source != "":
                errors.append(
                    f"{dimension_path}.source: runtime arrays use empty source"
                )
            if has_element_count:
                errors.append(
                    f"{dimension_path}.elementCount: runtime arrays must omit elementCount"
                )
            complete_fixed_product = False
        elif kind == "fixed":
            if source == "":
                errors.append(f"{dimension_path}.source: fixed arrays require source")
            if not has_element_count:
                errors.append(
                    f"{dimension_path}.elementCount: fixed arrays require elementCount"
                )
                complete_fixed_product = False
            else:
                product *= dimension["elementCount"]
        elif kind == "unresolved":
            if source == "":
                errors.append(
                    f"{dimension_path}.source: unresolved arrays require source"
                )
            if has_element_count:
                errors.append(
                    f"{dimension_path}.elementCount: unresolved arrays must omit elementCount"
                )
            complete_fixed_product = False
        else:
            errors.append(
                f"{dimension_path}.kind: unknown array dimension kind {kind!r}"
            )
            complete_fixed_product = False
    return product if complete_fixed_product else None


def validate_array_element_count(errors, path, document, fixed_product):
    if "arrayElementCount" in document and fixed_product is not None:
        add_equal_error(
            errors,
            f"{path}.arrayElementCount",
            document["arrayElementCount"],
            fixed_product,
            "array dimension product",
        )


def validate_entry_point_stage(errors, path, document, entry_points):
    entry = entry_points.get(document["entryPoint"])
    if entry is None:
        errors.append(
            f"{path}.entryPoint: unknown entry point {document['entryPoint']!r}"
        )
        return None
    add_equal_error(
        errors, f"{path}.stage", document["stage"], entry["stage"], "entry point stage"
    )
    return entry
