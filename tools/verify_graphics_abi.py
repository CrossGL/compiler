#!/usr/bin/env python3
"""Validate standalone CrossGL graphics ABI contract records."""

import argparse
import json
import sys
from pathlib import Path

from validate_json_schema import SchemaError
from validate_json_schema import load_json
from validate_json_schema import validate as validate_schema


SEVERITIES = ("note", "warning", "error")
DIAGNOSTIC_PREFIX = "graphics.abi."
SUPPORTED_BUILTINS = {
    "position": ("vertex", "output", "vec4"),
    "front_facing": ("fragment", "input", "bool"),
}


def normalized_path(path):
    return str(path).replace("\\", "/")


def input_location(path):
    return {
        "file": normalized_path(path),
        "line": 1,
        "column": 1,
        "offset": 0,
        "length": 0,
        "endLine": 1,
        "endColumn": 1,
        "endOffset": 0,
    }


def make_diagnostic(path, code, message, target=None):
    diagnostic = {
        "severity": "error",
        "code": f"{DIAGNOSTIC_PREFIX}{code}",
        "message": message,
        "location": input_location(path),
    }
    if target is not None:
        diagnostic["target"] = target
    return diagnostic


def add_required_field_diagnostic(
    diagnostics, path, record_path, record, field, target
):
    if field not in record:
        diagnostics.append(
            make_diagnostic(
                path,
                "required-field",
                f"{record_path}.{field}: required for "
                f"{record['target']} {record['abi']} ABI",
                target,
            )
        )


def add_forbidden_field_diagnostic(
    diagnostics,
    path,
    record_path,
    record,
    field,
    target,
):
    if field in record:
        diagnostics.append(
            make_diagnostic(
                path,
                "forbidden-field",
                f"{record_path}.{field}: forbidden for "
                f"{record['target']} {record['abi']} ABI",
                target,
            )
        )


def require_fields(diagnostics, path, record_path, record, fields, target):
    for field in fields:
        add_required_field_diagnostic(
            diagnostics, path, record_path, record, field, target
        )


def forbid_fields(diagnostics, path, record_path, record, fields, target):
    for field in fields:
        add_forbidden_field_diagnostic(
            diagnostics, path, record_path, record, field, target
        )


def add_equal_diagnostic(
    diagnostics,
    path,
    code,
    field_path,
    actual,
    expected,
    expected_label,
    target,
):
    if actual != expected:
        diagnostics.append(
            make_diagnostic(
                path,
                code,
                f"{field_path}: expected {expected_label} {expected!r}, got {actual!r}",
                target,
            )
        )


def validate_record_target_abi(diagnostics, path, record_path, record, document_target):
    target = record["target"]
    abi = record["abi"]
    shared = record["kind"] == "shared"

    add_equal_diagnostic(
        diagnostics,
        path,
        "target-mismatch",
        f"{record_path}.target",
        target,
        document_target,
        "$.target",
        target,
    )

    if target == "metal":
        require_fields(diagnostics, path, record_path, record, ("metalType",), target)
        forbid_fields(
            diagnostics,
            path,
            record_path,
            record,
            ("hlslType", "descriptorType", "storageClass", "spirvType"),
            target,
        )
        expected_abi = "threadgroupLocal" if shared else "kernelArgument"
        add_equal_diagnostic(
            diagnostics,
            path,
            "abi-kind-mismatch",
            f"{record_path}.abi",
            abi,
            expected_abi,
            "Metal resource ABI",
            target,
        )
        if abi == "kernelArgument":
            require_fields(
                diagnostics,
                path,
                record_path,
                record,
                ("argumentIndex", "set", "binding"),
                target,
            )
        elif abi == "threadgroupLocal":
            forbid_fields(
                diagnostics,
                path,
                record_path,
                record,
                ("argumentIndex", "set", "binding"),
                target,
            )
        return

    if target == "directx":
        forbid_fields(
            diagnostics,
            path,
            record_path,
            record,
            ("metalType", "storageClass", "spirvType"),
            target,
        )
        expected_abi = "groupsharedLocal" if shared else "registerBinding"
        add_equal_diagnostic(
            diagnostics,
            path,
            "abi-kind-mismatch",
            f"{record_path}.abi",
            abi,
            expected_abi,
            "DirectX resource ABI",
            target,
        )
        if abi == "registerBinding":
            require_fields(
                diagnostics,
                path,
                record_path,
                record,
                ("descriptorType", "argumentIndex", "set", "binding"),
                target,
            )
        elif abi == "groupsharedLocal":
            forbid_fields(
                diagnostics,
                path,
                record_path,
                record,
                ("descriptorType", "argumentIndex", "set", "binding"),
                target,
            )
        return

    if target == "vulkan":
        require_fields(
            diagnostics,
            path,
            record_path,
            record,
            ("storageClass", "spirvType"),
            target,
        )
        forbid_fields(
            diagnostics,
            path,
            record_path,
            record,
            ("metalType", "hlslType"),
            target,
        )
        expected_abi = "workgroupLocal" if shared else "descriptor"
        add_equal_diagnostic(
            diagnostics,
            path,
            "abi-kind-mismatch",
            f"{record_path}.abi",
            abi,
            expected_abi,
            "Vulkan resource ABI",
            target,
        )
        if abi == "descriptor":
            require_fields(
                diagnostics,
                path,
                record_path,
                record,
                ("descriptorType", "set", "binding"),
                target,
            )
        elif abi == "workgroupLocal":
            forbid_fields(
                diagnostics,
                path,
                record_path,
                record,
                ("descriptorType", "set", "binding"),
                target,
            )
        return

    if target == "opengl":
        forbid_fields(
            diagnostics,
            path,
            record_path,
            record,
            ("metalType", "hlslType", "descriptorType", "storageClass", "spirvType"),
            target,
        )
        expected_abi = "workgroupLocal" if shared else "programResourceBinding"
        add_equal_diagnostic(
            diagnostics,
            path,
            "abi-kind-mismatch",
            f"{record_path}.abi",
            abi,
            expected_abi,
            "OpenGL resource ABI",
            target,
        )
        if abi == "programResourceBinding":
            require_fields(
                diagnostics,
                path,
                record_path,
                record,
                ("argumentIndex", "set", "binding"),
                target,
            )
        elif abi == "workgroupLocal":
            forbid_fields(
                diagnostics,
                path,
                record_path,
                record,
                ("argumentIndex", "set", "binding"),
                target,
            )


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


def validate_unique_entry_points(diagnostics, path, entry_points, target):
    entries_by_name = {}
    entries_by_source_identity = {}
    for index, entry in enumerate(entry_points):
        entry_path = f"$.entryPoints[{index}]"
        source_name = entry["sourceName"]
        backend_name = entry["backendName"]
        if not source_name:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "empty-entry-point-source-name",
                    f"{entry_path}.sourceName: expected non-empty entry point sourceName",
                    target,
                )
            )
        if not backend_name:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "empty-entry-point-backend-name",
                    f"{entry_path}.backendName: expected non-empty entry point backendName",
                    target,
                )
            )
        if source_name and backend_name:
            add_equal_diagnostic(
                diagnostics,
                path,
                "entry-point-backend-name-mismatch",
                f"{entry_path}.backendName",
                backend_name,
                f"{entry['stage']}_{source_name}",
                "stage/sourceName backend name",
                target,
            )
        if backend_name in entries_by_name:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "duplicate-entry-point",
                    f"{entry_path}.backendName: duplicate entry point {backend_name!r}",
                    target,
                )
            )
        else:
            entries_by_name[backend_name] = entry

        source_identity = (entry["stage"], source_name)
        if source_name:
            if source_identity in entries_by_source_identity:
                diagnostics.append(
                    make_diagnostic(
                        path,
                        "duplicate-source-entry-point",
                        f"{entry_path}.sourceName: duplicate source entry point "
                        f"{source_identity!r}",
                        target,
                    )
                )
            else:
                entries_by_source_identity[source_identity] = entry
    return entries_by_name


def source_resource_coordinate(resource):
    if "set" not in resource or "binding" not in resource:
        return None
    return (resource["stage"], resource["set"], resource["binding"])


def validate_resources(diagnostics, path, resources, target):
    resource_map = {}
    resource_indices = {}
    source_coordinates = {}
    for index, resource in enumerate(resources):
        key = (resource["stage"], resource["name"], resource["kind"])
        if key in resource_map:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "duplicate-resource",
                    f"$.resources[{index}]: duplicate source resource {key!r}",
                    target,
                )
            )
        else:
            resource_map[key] = resource
            resource_indices[key] = index

        coordinate = source_resource_coordinate(resource)
        if coordinate is not None:
            if coordinate in source_coordinates:
                diagnostics.append(
                    make_diagnostic(
                        path,
                        "duplicate-source-coordinate",
                        f"$.resources[{index}]: duplicate source resource "
                        f"coordinate {coordinate!r}",
                        target,
                    )
                )
            else:
                source_coordinates[coordinate] = index
    return resource_map, resource_indices


def validate_entry_point_link(
    diagnostics,
    path,
    record_path,
    entries_by_name,
    stage,
    entry_point,
    target,
):
    entry = entries_by_name.get(entry_point)
    if entry is None:
        diagnostics.append(
            make_diagnostic(
                path,
                "entry-point-unknown",
                f"{record_path}.entryPoint: unknown entry point {entry_point!r}",
                target,
            )
        )
        return None
    add_equal_diagnostic(
        diagnostics,
        path,
        "stage-mismatch",
        f"{record_path}.stage",
        stage,
        entry["stage"],
        "entry point stage",
        target,
    )
    return entry


def validate_interface_stage(
    diagnostics,
    path,
    code,
    field_path,
    actual,
    expected,
    target,
):
    add_equal_diagnostic(
        diagnostics,
        path,
        code,
        field_path,
        actual,
        expected,
        "graphics interface stage",
        target,
    )


def validate_vertex_inputs(diagnostics, path, vertex_inputs, entries_by_name, target):
    identities = {}
    locations = {}
    for index, record in enumerate(vertex_inputs):
        record_path = f"$.vertexInputs[{index}]"
        validate_entry_point_link(
            diagnostics,
            path,
            record_path,
            entries_by_name,
            record["stage"],
            record["entryPoint"],
            target,
        )
        validate_interface_stage(
            diagnostics,
            path,
            "vertex-input-stage-mismatch",
            f"{record_path}.stage",
            record["stage"],
            "vertex",
            target,
        )

        identity = (record["entryPoint"], record["name"])
        if identity in identities:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "duplicate-vertex-input",
                    f"{record_path}: duplicate vertex input {identity!r}",
                    target,
                )
            )
        else:
            identities[identity] = index

        coordinate = (record["entryPoint"], record["location"])
        if coordinate in locations:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "duplicate-vertex-input-location",
                    f"{record_path}: duplicate vertex input location {coordinate!r}",
                    target,
                )
            )
        else:
            locations[coordinate] = index


def validate_fragment_outputs(
    diagnostics, path, fragment_outputs, entries_by_name, target
):
    identities = {}
    locations = {}
    for index, record in enumerate(fragment_outputs):
        record_path = f"$.fragmentOutputs[{index}]"
        validate_entry_point_link(
            diagnostics,
            path,
            record_path,
            entries_by_name,
            record["stage"],
            record["entryPoint"],
            target,
        )
        validate_interface_stage(
            diagnostics,
            path,
            "fragment-output-stage-mismatch",
            f"{record_path}.stage",
            record["stage"],
            "fragment",
            target,
        )

        identity = (record["entryPoint"], record["name"])
        if identity in identities:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "duplicate-fragment-output",
                    f"{record_path}: duplicate fragment output {identity!r}",
                    target,
                )
            )
        else:
            identities[identity] = index

        coordinate = (record["entryPoint"], record["location"])
        if coordinate in locations:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "duplicate-fragment-output-location",
                    f"{record_path}: duplicate fragment output location {coordinate!r}",
                    target,
                )
            )
        else:
            locations[coordinate] = index


def validate_builtins(diagnostics, path, builtins, entries_by_name, target):
    identities = {}
    for index, record in enumerate(builtins):
        record_path = f"$.builtins[{index}]"
        validate_entry_point_link(
            diagnostics,
            path,
            record_path,
            entries_by_name,
            record["stage"],
            record["entryPoint"],
            target,
        )
        expected = SUPPORTED_BUILTINS.get(record["builtin"])
        if expected is None:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "unsupported-builtin",
                    f"{record_path}.builtin: unsupported fixture-scoped "
                    f"graphics builtin {record['builtin']!r}",
                    target,
                )
            )
        else:
            actual = (record["stage"], record["direction"], record["type"])
            if actual != expected:
                diagnostics.append(
                    make_diagnostic(
                        path,
                        "builtin-contract-mismatch",
                        f"{record_path}: builtin {record['builtin']!r} "
                        f"requires (stage, direction, type) {expected!r}, "
                        f"got {actual!r}",
                        target,
                    )
                )
        identity = (
            record["stage"],
            record["entryPoint"],
            record["direction"],
            record["builtin"],
        )
        if identity in identities:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "duplicate-builtin",
                    f"{record_path}: duplicate builtin interface {identity!r}",
                    target,
                )
            )
        else:
            identities[identity] = index


def validate_varying_endpoint(
    diagnostics,
    path,
    endpoint_path,
    endpoint,
    entries_by_name,
    expected_stage,
    expected_direction,
    target,
):
    validate_entry_point_link(
        diagnostics,
        path,
        endpoint_path,
        entries_by_name,
        endpoint["stage"],
        endpoint["entryPoint"],
        target,
    )
    validate_interface_stage(
        diagnostics,
        path,
        "varying-stage-mismatch",
        f"{endpoint_path}.stage",
        endpoint["stage"],
        expected_stage,
        target,
    )
    add_equal_diagnostic(
        diagnostics,
        path,
        "varying-direction-mismatch",
        f"{endpoint_path}.direction",
        endpoint["direction"],
        expected_direction,
        "varying endpoint direction",
        target,
    )


def validate_varyings(diagnostics, path, varyings, entries_by_name, target):
    identities = {}
    locations = {}
    for index, record in enumerate(varyings):
        record_path = f"$.varyings[{index}]"
        producer = record["producer"]
        consumer = record["consumer"]
        validate_varying_endpoint(
            diagnostics,
            path,
            f"{record_path}.producer",
            producer,
            entries_by_name,
            "vertex",
            "output",
            target,
        )
        validate_varying_endpoint(
            diagnostics,
            path,
            f"{record_path}.consumer",
            consumer,
            entries_by_name,
            "fragment",
            "input",
            target,
        )

        for field in ("name", "type", "location"):
            add_equal_diagnostic(
                diagnostics,
                path,
                "varying-producer-consumer-mismatch",
                f"{record_path}.consumer.{field}",
                consumer[field],
                producer[field],
                f"varying producer {field}",
                target,
            )

        identity = (
            producer["entryPoint"],
            consumer["entryPoint"],
            producer["name"],
        )
        if identity in identities:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "duplicate-varying",
                    f"{record_path}: duplicate varying interface {identity!r}",
                    target,
                )
            )
        else:
            identities[identity] = index

        coordinate = (
            producer["entryPoint"],
            consumer["entryPoint"],
            producer["location"],
        )
        if coordinate in locations:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "duplicate-varying-location",
                    f"{record_path}: duplicate varying location {coordinate!r}",
                    target,
                )
            )
        else:
            locations[coordinate] = index


def validate_resource_link(
    diagnostics,
    path,
    record_path,
    record,
    resource,
    target,
):
    add_equal_diagnostic(
        diagnostics,
        path,
        "source-type-mismatch",
        f"{record_path}.sourceType",
        record["sourceType"],
        resource["type"],
        "source resource type",
        target,
    )
    add_equal_diagnostic(
        diagnostics,
        path,
        "array-dimensions-mismatch",
        f"{record_path}.arrayDimensions",
        record.get("arrayDimensions", []),
        resource.get("arrayDimensions", []),
        "source resource arrayDimensions",
        target,
    )
    for field in ("set", "binding"):
        if field in resource or field in record:
            add_equal_diagnostic(
                diagnostics,
                path,
                f"source-{field}-mismatch",
                f"{record_path}.{field}",
                record.get(field),
                resource.get(field),
                f"source resource {field}",
                target,
            )
    if "addressSpace" in resource:
        add_equal_diagnostic(
            diagnostics,
            path,
            "address-space-mismatch",
            f"{record_path}.addressSpace",
            record["addressSpace"],
            resource["addressSpace"],
            "source resource addressSpace",
            target,
        )
    if "storageImageFormat" in resource or "storageImageFormat" in record:
        add_equal_diagnostic(
            diagnostics,
            path,
            "storage-image-format-mismatch",
            f"{record_path}.storageImageFormat",
            record.get("storageImageFormat"),
            resource.get("storageImageFormat"),
            "source resource storageImageFormat",
            target,
        )


DESCRIPTOR_METADATA_OPTIONS = {
    "vulkan": {
        "descriptor": {
            "uniform-buffer": (
                ("VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER", "uniform_buffer"),
                ("uniformBuffer", "uniform-buffer"),
            ),
            "storage-buffer": (
                ("VK_DESCRIPTOR_TYPE_STORAGE_BUFFER", "storage_buffer"),
                ("storageBuffer", "storage-buffer"),
            ),
            "texture": (
                ("VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE", "combined_image_sampler"),
                ("sampledImage", "sampled-texture"),
            ),
            "storage-image": (
                ("VK_DESCRIPTOR_TYPE_STORAGE_IMAGE", "storage_image"),
                ("storageImage", "storage-image"),
            ),
            "sampler": (("VK_DESCRIPTOR_TYPE_SAMPLER",), ("sampler",)),
        },
    },
    "directx": {
        "registerBinding": {
            "uniform-buffer": (("CBV",), ("constant-buffer",)),
            "storage-buffer": (("UAV",), ("uav",)),
            "texture": (("SRV",), ("srv",)),
            "storage-image": (("UAV",), ("uav",)),
            "sampler": (("Sampler",), ("sampler",)),
        },
    },
    "metal": {
        "kernelArgument": {
            "uniform-buffer": (None, ("buffer", "uniform-buffer")),
            "storage-buffer": (None, ("buffer",)),
            "texture": (None, ("texture",)),
            "storage-image": (None, ("texture",)),
            "sampler": (None, ("sampler",)),
        },
    },
    "opengl": {
        "programResourceBinding": {
            "uniform-buffer": (None, ("uniform-buffer",)),
            "storage-buffer": (None, ("storage-buffer",)),
            "texture": (None, ("texture",)),
            "storage-image": (None, ("image",)),
            "sampler": (None, ("sampler",)),
        },
    },
}


def normalized_resource_metadata_kind(record, resource):
    kind = resource["kind"]
    address_space = resource.get("addressSpace", record.get("addressSpace"))

    if kind in {"uniform", "uniform_buffer"}:
        return "uniform-buffer"
    if kind in {"storageBuffer", "storage_buffer"}:
        return "storage-buffer"
    if kind == "buffer":
        if address_space in {"Uniform", "uniform", "constant", "constant-buffer"}:
            return "uniform-buffer"
        if address_space in {
            "StorageBuffer",
            "storage",
            "shader-storage",
            "buffer",
            "device",
            "unordered-access",
        }:
            return "storage-buffer"
    if kind == "texture":
        return "texture"
    if kind in {"storage_image", "storageImage"}:
        return "storage-image"
    if kind == "sampler":
        return "sampler"
    return None


def expected_descriptor_metadata_options(record, resource):
    target_options = DESCRIPTOR_METADATA_OPTIONS.get(record["target"])
    if target_options is None:
        return None

    abi_options = target_options.get(record["abi"])
    if abi_options is None:
        return None

    metadata_kind = normalized_resource_metadata_kind(record, resource)
    if metadata_kind is None:
        return None
    return abi_options.get(metadata_kind)


def add_allowed_diagnostic(
    diagnostics,
    path,
    code,
    field_path,
    actual,
    expected_options,
    expected_label,
    target,
):
    if actual not in expected_options:
        diagnostics.append(
            make_diagnostic(
                path,
                code,
                f"{field_path}: expected {expected_label} one of "
                f"{list(expected_options)!r}, got {actual!r}",
                target,
            )
        )


def validate_descriptor_metadata(
    diagnostics,
    path,
    record_path,
    record,
    resource,
    target,
):
    expected = expected_descriptor_metadata_options(record, resource)
    if expected is None:
        return

    expected_descriptor_types, expected_binding_classes = expected
    if expected_descriptor_types is not None:
        add_allowed_diagnostic(
            diagnostics,
            path,
            "descriptor-type-mismatch",
            f"{record_path}.descriptorType",
            record.get("descriptorType"),
            expected_descriptor_types,
            "source resource descriptorType",
            target,
        )
    add_allowed_diagnostic(
        diagnostics,
        path,
        "binding-class-mismatch",
        f"{record_path}.bindingClass",
        record.get("bindingClass"),
        expected_binding_classes,
        "source resource bindingClass",
        target,
    )


def validate_semantics(path, instance):
    diagnostics = []
    target = instance["target"]
    entries_by_name = validate_unique_entry_points(
        diagnostics, path, instance["entryPoints"], target
    )
    validate_vertex_inputs(
        diagnostics, path, instance["vertexInputs"], entries_by_name, target
    )
    validate_varyings(diagnostics, path, instance["varyings"], entries_by_name, target)
    validate_fragment_outputs(
        diagnostics, path, instance["fragmentOutputs"], entries_by_name, target
    )
    validate_builtins(diagnostics, path, instance["builtins"], entries_by_name, target)
    resource_map, resource_indices = validate_resources(
        diagnostics, path, instance["resources"], target
    )
    bound_resource_keys = set()
    record_identities = {}
    coordinates = {}
    previous_resource_index = -1

    for index, record in enumerate(instance["abiRecords"]):
        record_path = f"$.abiRecords[{index}]"
        record_target = record["target"]
        validate_record_target_abi(diagnostics, path, record_path, record, target)

        entry = entries_by_name.get(record["entryPoint"])
        if entry is None:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "entry-point-unknown",
                    f"{record_path}.entryPoint: unknown entry point "
                    f"{record['entryPoint']!r}",
                    record_target,
                )
            )
        else:
            add_equal_diagnostic(
                diagnostics,
                path,
                "stage-mismatch",
                f"{record_path}.stage",
                record["stage"],
                entry["stage"],
                "entry point stage",
                record_target,
            )

        resource_key = (record["stage"], record["name"], record["kind"])
        bound_resource_keys.add(resource_key)
        resource = resource_map.get(resource_key)
        if resource is None:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "source-resource-missing",
                    f"{record_path}: missing matching source resource {resource_key!r}",
                    record_target,
                )
            )
        else:
            resource_index = resource_indices[resource_key]
            if resource_index < previous_resource_index:
                diagnostics.append(
                    make_diagnostic(
                        path,
                        "resource-order-mismatch",
                        f"{record_path}: ABI records must preserve $.resources "
                        f"order; linked source resource index {resource_index} "
                        f"follows index {previous_resource_index}",
                        record_target,
                    )
                )
            else:
                previous_resource_index = resource_index
            validate_resource_link(
                diagnostics, path, record_path, record, resource, record_target
            )
            validate_descriptor_metadata(
                diagnostics, path, record_path, record, resource, record_target
            )

        identity = (
            record["stage"],
            record["entryPoint"],
            record["name"],
            record["kind"],
        )
        if identity in record_identities:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "duplicate-record",
                    f"{record_path}: duplicate ABI record identity {identity!r}",
                    record_target,
                )
            )
        else:
            record_identities[identity] = index

        coordinate = abi_coordinate(record)
        if coordinate is not None:
            if coordinate in coordinates:
                diagnostics.append(
                    make_diagnostic(
                        path,
                        "duplicate-coordinate",
                        f"{record_path}: duplicate target ABI coordinate "
                        f"{coordinate!r}",
                        record_target,
                    )
                )
            else:
                coordinates[coordinate] = index

    for index, resource in enumerate(instance["resources"]):
        resource_key = (resource["stage"], resource["name"], resource["kind"])
        if resource_key not in bound_resource_keys:
            diagnostics.append(
                make_diagnostic(
                    path,
                    "unbound-resource",
                    f"$.resources[{index}]: missing ABI record for {resource_key!r}",
                    target,
                )
            )

    return diagnostics


def make_summary(instance):
    if not isinstance(instance, dict):
        return None
    try:
        return {
            "module": instance["module"],
            "target": instance["target"],
            "entryPointCount": len(instance["entryPoints"]),
            "vertexInputCount": len(instance["vertexInputs"]),
            "varyingCount": len(instance["varyings"]),
            "fragmentOutputCount": len(instance["fragmentOutputs"]),
            "builtinCount": len(instance["builtins"]),
            "resourceCount": len(instance["resources"]),
            "abiRecordCount": len(instance["abiRecords"]),
        }
    except (KeyError, TypeError):
        return None


def make_entry_point_evidence(instance):
    if not isinstance(instance, dict):
        return []
    evidence = []
    try:
        for index, entry in enumerate(instance["entryPoints"]):
            evidence.append(
                {
                    "entryPointIndex": index,
                    "stage": entry["stage"],
                    "sourceName": entry["sourceName"],
                    "backendName": entry["backendName"],
                    "sourceMapRef": entry["sourceMapRef"],
                }
            )
    except (KeyError, TypeError):
        return []
    return evidence


def make_resource_binding_evidence(instance):
    if not isinstance(instance, dict):
        return []
    evidence = []
    try:
        entry_indices = {
            entry["backendName"]: index
            for index, entry in enumerate(instance["entryPoints"])
        }
        resource_indices = {
            (resource["stage"], resource["name"], resource["kind"]): index
            for index, resource in enumerate(instance["resources"])
        }
        resources = {
            (resource["stage"], resource["name"], resource["kind"]): resource
            for resource in instance["resources"]
        }
        for index, record in enumerate(instance["abiRecords"]):
            resource_key = (record["stage"], record["name"], record["kind"])
            resource = resources.get(resource_key)
            row = {
                "abiRecordIndex": index,
                "sourceResourceIndex": resource_indices.get(resource_key),
                "target": record["target"],
                "stage": record["stage"],
                "entryPoint": record["entryPoint"],
                "entryPointIndex": entry_indices.get(record["entryPoint"]),
                "name": record["name"],
                "kind": record["kind"],
                "sourceType": record["sourceType"],
                "addressSpace": record["addressSpace"],
                "abi": record["abi"],
                "bindingClass": record["bindingClass"],
                "arrayDimensions": record.get("arrayDimensions", []),
                "sourceMapRef": (
                    resource["sourceMapRef"] if resource is not None else None
                ),
                "abiSourceMapRef": record["sourceMapRef"],
            }
            for field in ("set", "binding", "argumentIndex"):
                if field in record:
                    row[field] = record[field]
            evidence.append(row)
    except (KeyError, TypeError):
        return []
    return evidence


def make_source_map_evidence(instance):
    if not isinstance(instance, dict):
        return []
    evidence = []
    try:
        for owner, collection in (
            ("entryPoint", instance["entryPoints"]),
            ("resource", instance["resources"]),
            ("abiRecord", instance["abiRecords"]),
        ):
            for index, record in enumerate(collection):
                evidence.append(
                    {
                        "owner": owner,
                        "index": index,
                        "location": record["sourceMapRef"],
                    }
                )
    except (KeyError, TypeError):
        return []
    return evidence


def make_report(path, instance, diagnostics):
    counts = {severity: 0 for severity in SEVERITIES}
    for diagnostic in diagnostics:
        severity = diagnostic.get("severity")
        if severity in counts:
            counts[severity] += 1
    return {
        "schemaVersion": 1,
        "inputPath": normalized_path(path),
        "success": counts["error"] == 0,
        "summary": make_summary(instance),
        "entryPointEvidence": make_entry_point_evidence(instance),
        "resourceBindingEvidence": make_resource_binding_evidence(instance),
        "sourceMapEvidence": make_source_map_evidence(instance),
        "diagnosticCounts": counts,
        "diagnostics": diagnostics,
    }


def verify(path, schema_path):
    instance = None
    diagnostics = []
    try:
        schema = load_json(schema_path)
        instance = load_json(path)
        validate_schema(instance, schema, schema)
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        diagnostics.append(
            make_diagnostic(path, "schema", f"input schema validation failed: {exc}")
        )
        return make_report(path, instance, diagnostics)

    diagnostics.extend(validate_semantics(path, instance))
    return make_report(path, instance, diagnostics)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="graphics ABI JSON input")
    parser.add_argument(
        "--schema",
        help="graphics ABI JSON schema path",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args()

    input_path = Path(args.input)
    schema_path = (
        Path(args.schema)
        if args.schema
        else (
            Path(__file__).resolve().parent.parent
            / "docs"
            / "schemas"
            / "graphics-abi-v1.schema.json"
        )
    )
    report = verify(input_path, schema_path)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=False))
    else:
        for diagnostic in report["diagnostics"]:
            print(
                f"{diagnostic['severity']}: {diagnostic['code']}: "
                f"{diagnostic['message']}",
                file=sys.stderr,
            )
        if report["success"]:
            print(f"validated graphics ABI contract {input_path}")

    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
