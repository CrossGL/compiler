"""Semantic checks for graphics-abi-v1.schema.json."""

import re

from .common import add_equal_error
from .common import validate_array_dimensions
from .common import validate_array_element_count
from .common import validate_source_location_span


SUPPORTED_BUILTINS = {
    "position": ("vertex", "output", "vec4"),
    "front_facing": ("fragment", "input", "bool"),
}
TARGET_LEGALIZATION_EVIDENCE_PREFIX = "target-legalization.v1"
TARGET_LEGALIZATION_RESOURCE_BINDING_EVIDENCE_RE = re.compile(
    r"^target-legalization\.v1\."
    r"(?P<target>metal|vulkan|directx|opengl)\."
    r"resource-binding\.[A-Za-z0-9_.-]+$"
)


def validate_source_map_ref(errors, path, source_map_ref):
    validate_source_location_span(errors, path, source_map_ref)
    if "\\" in source_map_ref["file"]:
        errors.append(f"{path}.file: expected normalized '/' path separators")


def source_resource_coordinate(resource):
    if "set" not in resource or "binding" not in resource:
        return None
    return (resource["stage"], resource["set"], resource["binding"])


def abi_coordinate(record):
    target = record["target"]
    abi = record["abi"]
    if target == "vulkan" and abi == "descriptor":
        if "set" not in record or "binding" not in record:
            return None
        return (
            target,
            record["stage"],
            record["entryPoint"],
            record["set"],
            record["binding"],
        )
    if target == "directx" and abi == "registerBinding":
        if "set" not in record or "binding" not in record:
            return None
        return (
            target,
            record["stage"],
            record["entryPoint"],
            record["bindingClass"],
            record["set"],
            record["binding"],
        )
    if target == "metal" and abi == "kernelArgument":
        if "argumentIndex" not in record:
            return None
        return (
            target,
            record["stage"],
            record["entryPoint"],
            record["bindingClass"],
            record["argumentIndex"],
        )
    if target == "opengl" and abi == "programResourceBinding":
        if "argumentIndex" not in record:
            return None
        return (
            target,
            record["stage"],
            record["entryPoint"],
            record["bindingClass"],
            record["argumentIndex"],
        )
    return None


def add_duplicate_error(errors, path, value, value_label):
    errors.append(f"{path}: duplicate {value_label} {value!r}")


def add_non_empty_error(errors, path, value_label):
    errors.append(f"{path}: expected non-empty {value_label}")


def validate_abi_record_evidence_id(errors, path, record, seen_evidence_ids):
    evidence_id = record.get("evidenceId")
    if evidence_id is None:
        return

    if evidence_id in seen_evidence_ids:
        errors.append(
            f"{path}.evidenceId: duplicate target resource binding evidence id "
            f"{evidence_id!r}"
        )
    seen_evidence_ids.add(evidence_id)

    match = TARGET_LEGALIZATION_RESOURCE_BINDING_EVIDENCE_RE.fullmatch(evidence_id)
    if match is None:
        return

    expected_prefix = (
        f"{TARGET_LEGALIZATION_EVIDENCE_PREFIX}.{record['target']}.resource-binding."
    )
    if not evidence_id.startswith(expected_prefix):
        errors.append(
            f"{path}.evidenceId: expected target resource binding evidence prefix "
            f"{expected_prefix!r}, got {evidence_id!r}"
        )


def validate_storage_image_format(errors, path, document, record_label):
    if "storageImageFormat" in document and document["kind"] != "storage_image":
        errors.append(
            f"{path}.storageImageFormat: storageImageFormat is only valid for "
            f"storage_image {record_label}"
        )


def fixed_array_dimension_product(dimensions):
    if not dimensions:
        return None

    product = 1
    for dimension in dimensions:
        if dimension["kind"] != "fixed" or "elementCount" not in dimension:
            return None
        product *= dimension["elementCount"]
    return product


def validate_builtins(errors, builtins):
    for index, record in enumerate(builtins):
        record_path = f"$.builtins[{index}]"
        expected = SUPPORTED_BUILTINS.get(record["builtin"])
        if expected is None:
            errors.append(
                f"{record_path}.builtin: unsupported fixture-scoped graphics "
                f"builtin {record['builtin']!r}"
            )
            continue

        actual = (record["stage"], record["direction"], record["type"])
        if actual != expected:
            errors.append(
                f"{record_path}: builtin {record['builtin']!r} requires "
                f"(stage, direction, type) {expected!r}, got {actual!r}"
            )


def validate_resource_order(
    errors,
    path,
    resource_index,
    previous_resource_index,
):
    if resource_index < previous_resource_index:
        errors.append(
            f"{path}: ABI records must preserve $.resources order; linked "
            f"source resource index {resource_index} follows index "
            f"{previous_resource_index}"
        )


def validate_resources(errors, resources):
    resource_map = {}
    resource_indices = {}
    source_coordinates = {}
    for index, resource in enumerate(resources):
        resource_path = f"$.resources[{index}]"
        validate_source_map_ref(
            errors, f"{resource_path}.sourceMapRef", resource["sourceMapRef"]
        )
        dimensions = resource.get("arrayDimensions", [])
        validate_array_dimensions(
            errors, f"{resource_path}.arrayDimensions", dimensions
        )
        validate_storage_image_format(errors, resource_path, resource, "resources")

        key = (resource["stage"], resource["name"], resource["kind"])
        if key in resource_map:
            add_duplicate_error(errors, resource_path, key, "source resource")
        else:
            resource_map[key] = resource
            resource_indices[key] = index

        coordinate = source_resource_coordinate(resource)
        if coordinate is not None:
            if coordinate in source_coordinates:
                add_duplicate_error(
                    errors,
                    resource_path,
                    coordinate,
                    "source resource coordinate",
                )
            else:
                source_coordinates[coordinate] = index
    return resource_map, resource_indices


def validate_abi_record_link(
    errors,
    record_path,
    record,
    resource,
):
    dimensions = record.get("arrayDimensions", [])
    add_equal_error(
        errors,
        f"{record_path}.sourceType",
        record["sourceType"],
        resource["type"],
        "source resource type",
    )
    add_equal_error(
        errors,
        f"{record_path}.arrayDimensions",
        dimensions,
        resource.get("arrayDimensions", []),
        "source resource arrayDimensions",
    )
    source_fixed_product = fixed_array_dimension_product(
        resource.get("arrayDimensions", [])
    )
    if source_fixed_product is not None:
        add_equal_error(
            errors,
            f"{record_path}.arrayElementCount",
            record.get("arrayElementCount"),
            source_fixed_product,
            "source resource arrayElementCount",
        )
    for field in ("set", "binding"):
        if field in resource or field in record:
            add_equal_error(
                errors,
                f"{record_path}.{field}",
                record.get(field),
                resource.get(field),
                f"source resource {field}",
            )
    if "addressSpace" in resource:
        add_equal_error(
            errors,
            f"{record_path}.addressSpace",
            record["addressSpace"],
            resource["addressSpace"],
            "source resource addressSpace",
        )
    if "storageImageFormat" in resource or "storageImageFormat" in record:
        add_equal_error(
            errors,
            f"{record_path}.storageImageFormat",
            record.get("storageImageFormat"),
            resource.get("storageImageFormat"),
            "source resource storageImageFormat",
        )


def validate_semantics(instance):
    errors = []
    target = instance["target"]

    entries_by_name = {}
    entries_by_source_identity = {}
    for index, entry in enumerate(instance["entryPoints"]):
        entry_path = f"$.entryPoints[{index}]"
        source_name = entry["sourceName"]
        backend_name = entry["backendName"]
        if not source_name:
            add_non_empty_error(
                errors, f"{entry_path}.sourceName", "entry point sourceName"
            )
        if not backend_name:
            add_non_empty_error(
                errors, f"{entry_path}.backendName", "entry point backendName"
            )
        if source_name and backend_name:
            add_equal_error(
                errors,
                f"{entry_path}.backendName",
                backend_name,
                f"{entry['stage']}_{source_name}",
                "stage/sourceName backend name",
            )
        if backend_name in entries_by_name:
            add_duplicate_error(
                errors,
                f"{entry_path}.backendName",
                backend_name,
                "entry point",
            )
        else:
            entries_by_name[backend_name] = entry

        source_identity = (entry["stage"], source_name)
        if source_name:
            if source_identity in entries_by_source_identity:
                add_duplicate_error(
                    errors,
                    f"{entry_path}.sourceName",
                    source_identity,
                    "source entry point",
                )
            else:
                entries_by_source_identity[source_identity] = entry
        validate_source_map_ref(
            errors, f"{entry_path}.sourceMapRef", entry["sourceMapRef"]
        )

    validate_builtins(errors, instance["builtins"])

    resource_map, resource_indices = validate_resources(errors, instance["resources"])
    bound_resource_keys = set()
    record_identities = {}
    coordinates = {}
    seen_evidence_ids = set()
    previous_resource_index = -1

    for index, record in enumerate(instance["abiRecords"]):
        record_path = f"$.abiRecords[{index}]"
        validate_source_map_ref(
            errors, f"{record_path}.sourceMapRef", record["sourceMapRef"]
        )
        validate_abi_record_evidence_id(errors, record_path, record, seen_evidence_ids)
        add_equal_error(
            errors, f"{record_path}.target", record["target"], target, "$.target"
        )

        entry = entries_by_name.get(record["entryPoint"])
        if entry is None:
            errors.append(
                f"{record_path}.entryPoint: unknown entry point "
                f"{record['entryPoint']!r}"
            )
        else:
            add_equal_error(
                errors,
                f"{record_path}.stage",
                record["stage"],
                entry["stage"],
                "entry point stage",
            )

        dimensions = record.get("arrayDimensions", [])
        fixed_product = validate_array_dimensions(
            errors, f"{record_path}.arrayDimensions", dimensions
        )
        validate_array_element_count(errors, record_path, record, fixed_product)
        validate_storage_image_format(errors, record_path, record, "ABI records")

        resource_key = (record["stage"], record["name"], record["kind"])
        bound_resource_keys.add(resource_key)
        resource = resource_map.get(resource_key)
        if resource is None:
            errors.append(
                f"{record_path}: missing matching source resource {resource_key!r}"
            )
        else:
            resource_index = resource_indices[resource_key]
            validate_resource_order(
                errors,
                record_path,
                resource_index,
                previous_resource_index,
            )
            if resource_index >= previous_resource_index:
                previous_resource_index = resource_index
            validate_abi_record_link(errors, record_path, record, resource)

        identity = (
            record["stage"],
            record["entryPoint"],
            record["name"],
            record["kind"],
        )
        if identity in record_identities:
            add_duplicate_error(errors, record_path, identity, "ABI record identity")
        else:
            record_identities[identity] = index

        coordinate = abi_coordinate(record)
        if coordinate is not None:
            if coordinate in coordinates:
                add_duplicate_error(
                    errors, record_path, coordinate, "target ABI coordinate"
                )
            else:
                coordinates[coordinate] = index

    for index, resource in enumerate(instance["resources"]):
        resource_key = (resource["stage"], resource["name"], resource["kind"])
        if resource_key not in bound_resource_keys:
            errors.append(
                f"$.resources[{index}]: missing ABI record for {resource_key!r}"
            )

    return errors
