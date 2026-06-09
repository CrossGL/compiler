"""Semantic checks for reflection-v1.schema.json."""

import re

from .common import add_equal_error
from .common import add_length_count_error
from .common import validate_array_dimensions
from .common import validate_array_element_count
from .common import validate_entry_point_stage
from .common import validate_unique_values


WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:")
TARGET_LEGALIZATION_EVIDENCE_PREFIX = "target-legalization.v1"
TARGET_LEGALIZATION_CORE_EVIDENCE_SUFFIX_RANK = {
    "decision": 0,
    "state.legalized": 1,
    "state.rejected": 1,
    "support.native": 2,
    "support.source-package": 2,
    "support.unsupported": 2,
    "package-mode.native": 3,
    "package-mode.source-package": 3,
    "package-mode.unsupported": 3,
    "package-provenance.native-package-available": 4,
    "package-provenance.source-package-only": 4,
    "package-provenance.unsupported-source-form": 4,
    "package-provenance.unsupported-native-form": 4,
    "package-provenance.unsupported": 4,
    "optional-native-tool.missing": 5,
}
PACKAGE_REASON_EVIDENCE_SUFFIX_PREFIX = "package-reason."
TARGET_LEGALIZATION_RESOURCE_BINDING_EVIDENCE_RE = re.compile(
    r"^target-legalization\.v1\."
    r"(?P<target>metal|vulkan|directx|opengl)\."
    r"resource-binding\.[A-Za-z0-9_.-]+$"
)

TARGET_RESOURCE_BINDING_FIELDS = {
    ("metal", "uniform"): {
        "addressSpace": "constant",
        "bindingClass": "buffer",
    },
    ("metal", "buffer"): {
        "addressSpace": "device",
        "bindingClass": "buffer",
    },
    ("metal", "texture"): {
        "addressSpace": "texture",
        "bindingClass": "texture",
    },
    ("metal", "storage_image"): {
        "addressSpace": "texture",
        "bindingClass": "texture",
    },
    ("metal", "sampler"): {
        "addressSpace": "sampler",
        "bindingClass": "sampler",
    },
    ("metal", "shared"): {
        "addressSpace": "threadgroup",
        "bindingClass": "threadgroup",
    },
    ("directx", "uniform"): {
        "addressSpace": "constant-buffer",
        "bindingClass": "constant-buffer",
        "descriptorType": "CBV",
    },
    ("directx", "buffer"): {
        "addressSpace": "unordered-access",
        "bindingClass": "uav",
        "descriptorType": "UAV",
    },
    ("directx", "storage_image"): {
        "addressSpace": "unordered-access",
        "bindingClass": "uav",
        "descriptorType": "UAV",
    },
    ("directx", "texture"): {
        "addressSpace": "shader-resource",
        "bindingClass": "srv",
        "descriptorType": "SRV",
    },
    ("directx", "sampler"): {
        "addressSpace": "sampler",
        "bindingClass": "sampler",
        "descriptorType": "Sampler",
    },
    ("directx", "shared"): {
        "addressSpace": "groupshared",
        "bindingClass": "groupshared",
    },
    ("vulkan", "uniform"): {
        "addressSpace": "Uniform",
        "bindingClass": "uniformBuffer",
        "descriptorType": "VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER",
        "storageClass": "Uniform",
    },
    ("vulkan", "buffer"): {
        "addressSpace": "StorageBuffer",
        "bindingClass": "storageBuffer",
        "descriptorType": "VK_DESCRIPTOR_TYPE_STORAGE_BUFFER",
        "storageClass": "StorageBuffer",
    },
    ("vulkan", "texture"): {
        "addressSpace": "UniformConstant",
        "bindingClass": "sampledImage",
        "descriptorType": "VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE",
        "storageClass": "UniformConstant",
    },
    ("vulkan", "storage_image"): {
        "addressSpace": "UniformConstant",
        "bindingClass": "storageImage",
        "descriptorType": "VK_DESCRIPTOR_TYPE_STORAGE_IMAGE",
        "storageClass": "UniformConstant",
    },
    ("vulkan", "sampler"): {
        "addressSpace": "UniformConstant",
        "bindingClass": "sampler",
        "descriptorType": "VK_DESCRIPTOR_TYPE_SAMPLER",
        "storageClass": "UniformConstant",
    },
    ("vulkan", "shared"): {
        "addressSpace": "Workgroup",
        "bindingClass": "workgroup",
        "storageClass": "Workgroup",
    },
    ("opengl", "uniform"): {
        "addressSpace": "uniform",
        "bindingClass": "uniform-buffer",
    },
    ("opengl", "buffer"): {
        "addressSpace": "shader-storage",
        "bindingClass": "storage-buffer",
    },
    ("opengl", "texture"): {
        "addressSpace": "texture",
        "bindingClass": "texture",
    },
    ("opengl", "storage_image"): {
        "addressSpace": "image",
        "bindingClass": "image",
    },
    ("opengl", "sampler"): {
        "addressSpace": "sampler",
        "bindingClass": "sampler",
    },
    ("opengl", "shared"): {
        "addressSpace": "shared",
        "bindingClass": "shared",
    },
}


def validate_native_binary_path(errors, value):
    if value == "":
        return
    if "\\" in value:
        errors.append("$.nativeBinary: native binary path must use '/' separators")
    if value.startswith("/") or WINDOWS_DRIVE_PATH.match(value):
        errors.append("$.nativeBinary: native binary path must be package-relative")
    if ".." in value.split("/"):
        errors.append("$.nativeBinary: native binary path must stay inside package")


def validate_reflection_manual_kernel_semantics(errors, instance):
    summary = instance["manualTextureCompareKernelSummary"]
    kernels = instance["manualTextureCompareKernels"]
    add_length_count_error(
        errors,
        "$.manualTextureCompareKernelSummary.totalCount",
        summary["totalCount"],
        kernels,
        "$.manualTextureCompareKernels length",
    )

    expected_counts = {
        "static-normalized": "staticNormalizedCount",
        "static-non-normalized": "staticNonNormalizedCount",
        "static-zero-sum": "staticZeroSumCount",
        "dynamic": "dynamicCount",
    }
    actual_counts = {weight_class: 0 for weight_class in expected_counts}
    for index, kernel in enumerate(kernels):
        kernel_path = f"$.manualTextureCompareKernels[{index}]"
        weight_class = kernel["weightClass"]
        if weight_class not in expected_counts:
            errors.append(f"{kernel_path}.weightClass: unknown class {weight_class!r}")
            continue
        actual_counts[weight_class] += 1

        if kernel["weightsStatic"] and "weightSum" not in kernel:
            errors.append(f"{kernel_path}: static weights require weightSum")
        if not kernel["weightsStatic"] and "weightSum" in kernel:
            errors.append(f"{kernel_path}: dynamic weights must omit weightSum")
        add_equal_error(
            errors,
            f"{kernel_path}.compatibilityAlias",
            kernel["compatibilityAlias"],
            kernel["operation"] != kernel["canonicalOperation"],
            "operation/canonicalOperation alias flag",
        )

        if weight_class == "static-normalized":
            add_equal_error(
                errors,
                f"{kernel_path}.weightsStatic",
                kernel["weightsStatic"],
                True,
                "static-normalized static flag",
            )
            add_equal_error(
                errors,
                f"{kernel_path}.weightsNormalized",
                kernel["weightsNormalized"],
                True,
                "static-normalized normalized flag",
            )
            add_equal_error(
                errors,
                f"{kernel_path}.weightsZeroSum",
                kernel["weightsZeroSum"],
                False,
                "static-normalized zero-sum flag",
            )
        elif weight_class == "static-non-normalized":
            add_equal_error(
                errors,
                f"{kernel_path}.weightsStatic",
                kernel["weightsStatic"],
                True,
                "static-non-normalized static flag",
            )
            add_equal_error(
                errors,
                f"{kernel_path}.weightsNormalized",
                kernel["weightsNormalized"],
                False,
                "static-non-normalized normalized flag",
            )
            add_equal_error(
                errors,
                f"{kernel_path}.weightsZeroSum",
                kernel["weightsZeroSum"],
                False,
                "static-non-normalized zero-sum flag",
            )
        elif weight_class == "static-zero-sum":
            add_equal_error(
                errors,
                f"{kernel_path}.weightsStatic",
                kernel["weightsStatic"],
                True,
                "static-zero-sum static flag",
            )
            add_equal_error(
                errors,
                f"{kernel_path}.weightsZeroSum",
                kernel["weightsZeroSum"],
                True,
                "static-zero-sum zero-sum flag",
            )
        elif weight_class == "dynamic":
            add_equal_error(
                errors,
                f"{kernel_path}.weightsStatic",
                kernel["weightsStatic"],
                False,
                "dynamic static flag",
            )

    for weight_class, summary_field in expected_counts.items():
        add_equal_error(
            errors,
            f"$.manualTextureCompareKernelSummary.{summary_field}",
            summary[summary_field],
            actual_counts[weight_class],
            f"manualTextureCompareKernels with weightClass {weight_class!r}",
        )
    summary_bucket_total = sum(summary[field] for field in expected_counts.values())
    add_equal_error(
        errors,
        "$.manualTextureCompareKernelSummary",
        summary_bucket_total,
        summary["totalCount"],
        "sum of bucket counts",
    )


def validate_reflection_storage_layout(errors, path, binding, layout):
    if binding["kind"] != "buffer":
        errors.append(f"{path}: storageBufferLayout is only valid for buffer bindings")
    if (
        layout["arrayStrideBytes"] != 0
        and layout["arrayStrideBytes"] < layout["elementSizeBytes"]
    ):
        errors.append(
            f"{path}.arrayStrideBytes: expected >= elementSizeBytes "
            f"{layout['elementSizeBytes']!r}, got {layout['arrayStrideBytes']!r}"
        )

    previous_offset = None
    for index, field in enumerate(layout.get("fields", [])):
        field_path = f"{path}.fields[{index}]"
        if previous_offset is not None and field["offsetBytes"] < previous_offset:
            errors.append(f"{field_path}.offsetBytes: fields must be nondecreasing")
        previous_offset = field["offsetBytes"]
        if field["storageSizeBytes"] < field["sizeBytes"]:
            errors.append(
                f"{field_path}.storageSizeBytes: expected >= sizeBytes "
                f"{field['sizeBytes']!r}, got {field['storageSizeBytes']!r}"
            )
        dimensions = field.get("arrayDimensions", [])
        fixed_product = validate_array_dimensions(
            errors, f"{field_path}.arrayDimensions", dimensions
        )
        if "arrayElementCount" in field:
            if "arrayStrideBytes" not in field:
                errors.append(
                    f"{field_path}.arrayStrideBytes: array fields require stride"
                )
            validate_array_element_count(errors, field_path, field, fixed_product)


def validate_required_entry_point_stage(errors, path, entry, required_stage):
    if entry is None:
        return
    if entry["stage"] != required_stage:
        errors.append(
            f"{path}.entryPoint: expected {required_stage} entry point, "
            f"got {entry['stage']!r}"
        )


def require_target_resource_binding_fields(errors, path, binding, fields):
    for field in fields:
        if field not in binding:
            errors.append(
                f"{path}.{field}: required for "
                f"{binding['target']} {binding['abi']} binding"
            )


def forbid_target_resource_binding_fields(errors, path, binding, fields):
    for field in fields:
        if field in binding:
            errors.append(
                f"{path}.{field}: forbidden for "
                f"{binding['target']} {binding['abi']} binding"
            )


def validate_target_resource_binding_abi(errors, path, binding):
    target = binding["target"]
    abi = binding["abi"]
    shared = binding["kind"] == "shared"
    expected_fields = TARGET_RESOURCE_BINDING_FIELDS.get((target, binding["kind"]), {})

    for field, expected_value in expected_fields.items():
        if field in binding:
            add_equal_error(
                errors,
                f"{path}.{field}",
                binding[field],
                expected_value,
                f"{target} {binding['kind']} resource {field}",
            )

    if target == "metal":
        require_target_resource_binding_fields(errors, path, binding, ("metalType",))
        forbid_target_resource_binding_fields(
            errors,
            path,
            binding,
            ("hlslType", "descriptorType", "storageClass", "spirvType"),
        )
        expected_abi = "threadgroupLocal" if shared else "kernelArgument"
        add_equal_error(errors, f"{path}.abi", abi, expected_abi, "Metal resource ABI")
        if abi == "kernelArgument":
            require_target_resource_binding_fields(
                errors, path, binding, ("argumentIndex", "set", "binding")
            )
        elif abi == "threadgroupLocal":
            forbid_target_resource_binding_fields(
                errors, path, binding, ("argumentIndex", "set", "binding")
            )
        return

    if target == "directx":
        forbid_target_resource_binding_fields(
            errors, path, binding, ("metalType", "storageClass", "spirvType")
        )
        expected_abi = "groupsharedLocal" if shared else "registerBinding"
        add_equal_error(
            errors, f"{path}.abi", abi, expected_abi, "DirectX resource ABI"
        )
        if abi == "registerBinding":
            require_target_resource_binding_fields(
                errors,
                path,
                binding,
                ("descriptorType", "argumentIndex", "set", "binding"),
            )
        elif abi == "groupsharedLocal":
            forbid_target_resource_binding_fields(
                errors,
                path,
                binding,
                ("descriptorType", "argumentIndex", "set", "binding"),
            )
        return

    if target == "vulkan":
        require_target_resource_binding_fields(
            errors, path, binding, ("storageClass", "spirvType")
        )
        forbid_target_resource_binding_fields(
            errors, path, binding, ("metalType", "hlslType")
        )
        expected_abi = "workgroupLocal" if shared else "descriptor"
        add_equal_error(errors, f"{path}.abi", abi, expected_abi, "Vulkan resource ABI")
        if abi == "descriptor":
            require_target_resource_binding_fields(
                errors, path, binding, ("descriptorType", "set", "binding")
            )
        elif abi == "workgroupLocal":
            forbid_target_resource_binding_fields(
                errors, path, binding, ("descriptorType", "set", "binding")
            )
        return

    if target == "opengl":
        forbid_target_resource_binding_fields(
            errors,
            path,
            binding,
            ("metalType", "hlslType", "descriptorType", "storageClass", "spirvType"),
        )
        expected_abi = "workgroupLocal" if shared else "programResourceBinding"
        add_equal_error(errors, f"{path}.abi", abi, expected_abi, "OpenGL resource ABI")
        if abi == "programResourceBinding":
            require_target_resource_binding_fields(
                errors, path, binding, ("argumentIndex", "set", "binding")
            )
        elif abi == "workgroupLocal":
            forbid_target_resource_binding_fields(
                errors, path, binding, ("argumentIndex", "set", "binding")
            )


def target_resource_binding_coordinate(binding):
    target = binding["target"]
    abi = binding["abi"]
    if target == "vulkan" and abi == "descriptor":
        if "set" not in binding or "binding" not in binding:
            return None
        return (
            target,
            binding["stage"],
            binding["entryPoint"],
            binding["set"],
            binding["binding"],
        )
    if target == "directx" and abi == "registerBinding":
        if "set" not in binding or "binding" not in binding:
            return None
        return (
            target,
            binding["stage"],
            binding["entryPoint"],
            binding["bindingClass"],
            binding["set"],
            binding["binding"],
        )
    if target == "metal" and abi == "kernelArgument":
        if "argumentIndex" not in binding:
            return None
        return (
            target,
            binding["stage"],
            binding["entryPoint"],
            binding["bindingClass"],
            binding["argumentIndex"],
        )
    if target == "opengl" and abi == "programResourceBinding":
        if "argumentIndex" not in binding:
            return None
        return (
            target,
            binding["stage"],
            binding["entryPoint"],
            binding["bindingClass"],
            binding["argumentIndex"],
        )
    return None


def validate_target_resource_binding_evidence_id(
    errors, path, binding, seen_evidence_ids
):
    evidence_id = binding.get("evidenceId")
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
        f"{TARGET_LEGALIZATION_EVIDENCE_PREFIX}.{binding['target']}.resource-binding."
    )
    if not evidence_id.startswith(expected_prefix):
        errors.append(
            f"{path}.evidenceId: expected target resource binding evidence prefix "
            f"{expected_prefix!r}, got {evidence_id!r}"
        )


def source_resource_coordinate(resource):
    if "set" not in resource or "binding" not in resource:
        return None
    return (resource["stage"], resource["set"], resource["binding"])


def fixed_array_dimension_product(dimensions):
    if not dimensions:
        return None

    product = 1
    for dimension in dimensions:
        if dimension["kind"] != "fixed" or "elementCount" not in dimension:
            return None
        product *= dimension["elementCount"]
    return product


def validate_reflection_resource_links(errors, instance, entry_points):
    target = instance["target"]
    resource_map = {}
    resource_coordinates = {}
    for index, resource in enumerate(instance["resources"]):
        resource_path = f"$.resources[{index}]"
        dimensions = resource.get("arrayDimensions", [])
        validate_array_dimensions(
            errors, f"{resource_path}.arrayDimensions", dimensions
        )
        if "storageImageFormat" in resource and resource["kind"] != "storage_image":
            errors.append(
                f"{resource_path}.storageImageFormat: storageImageFormat is only "
                "valid for storage_image resources"
            )
        key = (resource["stage"], resource["name"], resource["kind"])
        if key in resource_map:
            errors.append(f"{resource_path}: duplicate resource identity {key!r}")
        resource_map[key] = resource
        coordinate = source_resource_coordinate(resource)
        if coordinate is not None:
            if coordinate in resource_coordinates:
                errors.append(
                    f"{resource_path}: duplicate source resource coordinate "
                    f"{coordinate!r}"
                )
            else:
                resource_coordinates[coordinate] = index

    binding_keys = []
    binding_coordinates = {}
    binding_evidence_ids = set()
    bound_resource_keys = set()
    for index, binding in enumerate(instance["targetResourceBindings"]):
        binding_path = f"$.targetResourceBindings[{index}]"
        add_equal_error(
            errors, f"{binding_path}.target", binding["target"], target, "$.target"
        )
        validate_target_resource_binding_evidence_id(
            errors, binding_path, binding, binding_evidence_ids
        )
        validate_entry_point_stage(errors, binding_path, binding, entry_points)

        dimensions = binding.get("arrayDimensions", [])
        fixed_product = validate_array_dimensions(
            errors, f"{binding_path}.arrayDimensions", dimensions
        )
        validate_array_element_count(errors, binding_path, binding, fixed_product)
        if "storageImageFormat" in binding and binding["kind"] != "storage_image":
            errors.append(
                f"{binding_path}.storageImageFormat: storageImageFormat is only "
                "valid for storage_image bindings"
            )
        validate_target_resource_binding_abi(errors, binding_path, binding)

        resource_key = (binding["stage"], binding["name"], binding["kind"])
        bound_resource_keys.add(resource_key)
        resource = resource_map.get(resource_key)
        if resource is None:
            errors.append(
                f"{binding_path}: missing matching source resource {resource_key!r}"
            )
        else:
            add_equal_error(
                errors,
                f"{binding_path}.sourceType",
                binding["sourceType"],
                resource["type"],
                "source resource type",
            )
            add_equal_error(
                errors,
                f"{binding_path}.arrayDimensions",
                dimensions,
                resource.get("arrayDimensions", []),
                "source resource arrayDimensions",
            )
            source_fixed_product = fixed_array_dimension_product(
                resource.get("arrayDimensions", [])
            )
            if source_fixed_product is not None and "arrayElementCount" not in binding:
                errors.append(
                    f"{binding_path}.arrayElementCount: required for fixed "
                    "source resource arrayDimensions"
                )
            for field in ["set", "binding"]:
                if field in resource or field in binding:
                    add_equal_error(
                        errors,
                        f"{binding_path}.{field}",
                        binding.get(field),
                        resource.get(field),
                        f"source resource {field}",
                    )
            if "addressSpace" in resource:
                add_equal_error(
                    errors,
                    f"{binding_path}.addressSpace",
                    binding["addressSpace"],
                    resource["addressSpace"],
                    "source resource addressSpace",
                )
            if "storageImageFormat" in resource or "storageImageFormat" in binding:
                add_equal_error(
                    errors,
                    f"{binding_path}.storageImageFormat",
                    binding.get("storageImageFormat"),
                    resource.get("storageImageFormat"),
                    "source resource storageImageFormat",
                )

        if "storageBufferLayout" in binding:
            validate_reflection_storage_layout(
                errors,
                f"{binding_path}.storageBufferLayout",
                binding,
                binding["storageBufferLayout"],
            )
        binding_keys.append(
            (binding["stage"], binding["entryPoint"], binding["name"], binding["kind"])
        )
        binding_coordinate = target_resource_binding_coordinate(binding)
        if binding_coordinate is not None:
            if binding_coordinate in binding_coordinates:
                errors.append(
                    f"{binding_path}: duplicate target ABI coordinate "
                    f"{binding_coordinate!r}"
                )
            else:
                binding_coordinates[binding_coordinate] = index
    validate_unique_values(
        errors,
        "$.targetResourceBindings",
        binding_keys,
        "(stage, entryPoint, name, kind)",
    )
    for index, resource in enumerate(instance["resources"]):
        resource_key = (resource["stage"], resource["name"], resource["kind"])
        if resource_key not in bound_resource_keys:
            errors.append(
                f"$.resources[{index}]: missing target resource binding {resource_key!r}"
            )


def legalization_core_evidence_suffix_rank(suffix):
    if suffix in TARGET_LEGALIZATION_CORE_EVIDENCE_SUFFIX_RANK:
        return TARGET_LEGALIZATION_CORE_EVIDENCE_SUFFIX_RANK[suffix]
    if suffix.startswith(PACKAGE_REASON_EVIDENCE_SUFFIX_PREFIX):
        reason = suffix[len(PACKAGE_REASON_EVIDENCE_SUFFIX_PREFIX) :]
        if reason and re.fullmatch(r"[a-z0-9][a-z0-9-]*", reason):
            return 6
    return None


def validate_legalization_core_evidence_ids(errors, instance):
    field = "legalizationCoreEvidenceIds"
    if field not in instance:
        return

    evidence_ids = instance[field]
    if not evidence_ids:
        errors.append(f"$.{field}: must be a non-empty array")
        return

    seen = set()
    ranks = []
    expected_prefix = f"{TARGET_LEGALIZATION_EVIDENCE_PREFIX}.{instance['target']}."
    for index, evidence_id in enumerate(evidence_ids):
        item_path = f"$.{field}[{index}]"
        if evidence_id in seen:
            errors.append(
                f"$.{field}: duplicate legalization core evidence id {evidence_id!r}"
            )
        seen.add(evidence_id)

        if not evidence_id.startswith(expected_prefix):
            errors.append(
                f"{item_path}: expected target legalization evidence prefix "
                f"{expected_prefix!r}, got {evidence_id!r}"
            )
            continue

        suffix = evidence_id[len(expected_prefix) :]
        rank = legalization_core_evidence_suffix_rank(suffix)
        if rank is None:
            errors.append(
                f"{item_path}: expected known target legalization core "
                f"evidence id, got {evidence_id!r}"
            )
            continue
        ranks.append(rank)

    if ranks != sorted(ranks):
        errors.append(
            f"$.{field}: expected canonical target legalization core evidence ordering"
        )


def validate_semantics(instance):
    errors = []
    validate_native_binary_path(errors, instance["nativeBinary"])
    validate_legalization_core_evidence_ids(errors, instance)
    entry_points = {}
    for index, entry in enumerate(instance["entryPoints"]):
        path = f"$.entryPoints[{index}]"
        if entry["backendName"] in entry_points:
            errors.append(
                f"{path}.backendName: duplicate entry point {entry['backendName']!r}"
            )
        entry_points[entry["backendName"]] = entry
        expected_prefix = f"{entry['stage']}_"
        if not entry["backendName"].startswith(expected_prefix):
            errors.append(
                f"{path}.backendName: expected to start with {expected_prefix!r}"
            )
        else:
            add_equal_error(
                errors,
                f"{path}.backendName",
                entry["backendName"],
                f"{entry['stage']}_{entry['sourceName']}",
                "stage/sourceName backend name",
            )

    validate_unique_values(
        errors,
        "$.structs",
        [structure["name"] for structure in instance["structs"]],
        "struct name",
    )
    for index, structure in enumerate(instance["structs"]):
        field_names = [field["name"] for field in structure["fields"]]
        validate_unique_values(
            errors, f"$.structs[{index}].fields", field_names, "field name"
        )
        for field_index, field in enumerate(structure["fields"]):
            validate_array_dimensions(
                errors,
                f"$.structs[{index}].fields[{field_index}].arrayDimensions",
                field.get("arrayDimensions", []),
            )

    validate_reflection_resource_links(errors, instance, entry_points)

    validate_unique_values(
        errors,
        "$.functionConstants",
        [constant["name"] for constant in instance["functionConstants"]],
        "function constant name",
    )
    for index, layout in enumerate(instance["vertexLayouts"]):
        path = f"$.vertexLayouts[{index}]"
        entry = entry_points.get(layout["entryPoint"])
        if entry is None:
            errors.append(
                f"{path}.entryPoint: unknown entry point {layout['entryPoint']!r}"
            )
        else:
            validate_required_entry_point_stage(errors, path, entry, "vertex")
        locations = []
        for attribute_index, attribute in enumerate(layout["attributes"]):
            add_equal_error(
                errors,
                f"{path}.attributes[{attribute_index}].location",
                attribute["location"],
                attribute_index,
                "attribute index",
            )
            locations.append(attribute["location"])
        validate_unique_values(errors, f"{path}.attributes", locations, "location")

    for index, size in enumerate(instance["workgroupSizes"]):
        path = f"$.workgroupSizes[{index}]"
        entry = validate_entry_point_stage(errors, path, size, entry_points)
        validate_required_entry_point_stage(errors, path, entry, "compute")

    for index, feature in enumerate(instance["targetFeatures"]):
        feature_path = f"$.targetFeatures[{index}]"
        add_equal_error(
            errors,
            f"{feature_path}.target",
            feature["target"],
            instance["target"],
            "$.target",
        )
        for field in ("kind", "name"):
            if feature[field] == "":
                errors.append(f"{feature_path}.{field}: must not be empty")
    validate_unique_values(
        errors,
        "$.targetFeatures",
        [
            (feature["target"], feature["kind"], feature["name"])
            for feature in instance["targetFeatures"]
        ],
        "(target, kind, name)",
    )

    validate_reflection_manual_kernel_semantics(errors, instance)
    for index, kernel in enumerate(instance["manualTextureCompareKernels"]):
        path = f"$.manualTextureCompareKernels[{index}]"
        validate_entry_point_stage(errors, path, kernel, entry_points)
    return errors
