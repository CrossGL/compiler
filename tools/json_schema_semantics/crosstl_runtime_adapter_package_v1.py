"""Semantic checks for crosstl-runtime-adapter-package-v1.schema.json."""

import re

from .common import add_equal_error, add_length_count_error


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def is_normalized_relative_path(value):
    if value == "" or value.startswith("/") or "\\" in value or value.endswith("/"):
        return False
    parts = value.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def descriptor_blocked(status):
    return status in ("blocked", "unavailable")


def validate_descriptor_record(errors, path, descriptor):
    descriptor_path = descriptor["descriptorPath"]
    if not is_normalized_relative_path(descriptor_path):
        errors.append(f"{path}.descriptorPath: expected normalized relative path")
    if not descriptor_path.endswith(".adapter.json"):
        errors.append(f"{path}.descriptorPath: expected .adapter.json path")
    descriptor_hash = descriptor["descriptorHash"]
    descriptor_hash_value = (
        descriptor_hash.get("value") if isinstance(descriptor_hash, dict) else None
    )
    if not isinstance(descriptor_hash_value, str) or not SHA256_RE.match(
        descriptor_hash_value
    ):
        errors.append(f"{path}.descriptorHash: expected lowercase SHA-256 digest")
    if descriptor["descriptorSizeBytes"] < 0:
        errors.append(f"{path}.descriptorSizeBytes: expected nonnegative size")


def validate_summary(errors, instance):
    summary = instance["summary"]
    targets = instance["targets"]
    descriptors = instance["descriptors"]
    actions = instance["actions"]

    add_length_count_error(
        errors, "$.summary.targetCount", summary["targetCount"], targets, "target length"
    )
    add_length_count_error(
        errors,
        "$.summary.descriptorCount",
        summary["descriptorCount"],
        descriptors,
        "descriptor length",
    )
    add_length_count_error(
        errors, "$.summary.actionCount", summary["actionCount"], actions, "action length"
    )

    ready_count = sum(
        1
        for descriptor in descriptors
        if descriptor["hostInterfaceStatus"] == "ready"
    )
    blocked_count = sum(
        1
        for descriptor in descriptors
        if descriptor_blocked(descriptor["hostInterfaceStatus"])
    )
    add_equal_error(
        errors,
        "$.summary.readyDescriptorCount",
        summary["readyDescriptorCount"],
        ready_count,
        "ready descriptor count",
    )
    add_equal_error(
        errors,
        "$.summary.blockedDescriptorCount",
        summary["blockedDescriptorCount"],
        blocked_count,
        "blocked descriptor count",
    )

    target_adapter_count = sum(target["adapterCount"] for target in targets)
    target_runtime_reference_count = sum(
        target["runtimeReferenceCount"] for target in targets
    )
    add_equal_error(
        errors,
        "$.summary.adapterCount",
        summary["adapterCount"],
        target_adapter_count,
        "target adapter count sum",
    )
    add_equal_error(
        errors,
        "$.summary.runtimeReferenceCount",
        summary["runtimeReferenceCount"],
        target_runtime_reference_count,
        "target runtime reference count sum",
    )


def validate_adapter_plan(errors, instance):
    adapter_plan = instance["adapterPlan"]
    if adapter_plan["kind"] != "crosstl-runtime-adapter-plan":
        errors.append(
            "$.adapterPlan.kind: expected 'crosstl-runtime-adapter-plan'"
        )
    if "adapterCount" in adapter_plan:
        add_equal_error(
            errors,
            "$.adapterPlan.adapterCount",
            adapter_plan["adapterCount"],
            instance["summary"]["adapterCount"],
            "$.summary.adapterCount",
        )


def validate_target_records(errors, instance):
    descriptors_by_target = {}
    for descriptor in instance["descriptors"]:
        descriptors_by_target.setdefault(descriptor["target"], []).append(descriptor)

    seen_targets = set()
    for index, target in enumerate(instance["targets"]):
        path = f"$.targets[{index}]"
        target_name = target["target"]
        if target_name in seen_targets:
            errors.append(f"{path}.target: duplicate target record")
        seen_targets.add(target_name)

        target_descriptors = descriptors_by_target.get(target_name, [])
        descriptor_ids = [descriptor["id"] for descriptor in target_descriptors]
        package_paths = [descriptor["packagePath"] for descriptor in target_descriptors]
        ready_count = sum(
            1
            for descriptor in target_descriptors
            if descriptor["hostInterfaceStatus"] == "ready"
        )
        blocked_count = sum(
            1
            for descriptor in target_descriptors
            if descriptor_blocked(descriptor["hostInterfaceStatus"])
        )

        add_equal_error(
            errors,
            f"{path}.descriptorCount",
            target["descriptorCount"],
            len(target_descriptors),
            "target descriptor count",
        )
        add_equal_error(
            errors,
            f"{path}.readyDescriptorCount",
            target["readyDescriptorCount"],
            ready_count,
            "target ready descriptor count",
        )
        add_equal_error(
            errors,
            f"{path}.blockedDescriptorCount",
            target["blockedDescriptorCount"],
            blocked_count,
            "target blocked descriptor count",
        )
        if target["descriptors"] != descriptor_ids:
            errors.append(
                f"{path}.descriptors: expected descriptor ids {descriptor_ids!r}"
            )
        if target["packagePaths"] != package_paths:
            errors.append(
                f"{path}.packagePaths: expected descriptor package paths "
                f"{package_paths!r}"
            )


def validate_descriptor_paths(errors, descriptors):
    descriptor_paths = []
    for index, descriptor in enumerate(descriptors):
        validate_descriptor_record(errors, f"$.descriptors[{index}]", descriptor)
        descriptor_paths.append(descriptor["descriptorPath"])
    duplicates = {
        path for path in descriptor_paths if descriptor_paths.count(path) > 1
    }
    for path in sorted(duplicates):
        errors.append(f"$.descriptors: duplicate descriptorPath {path!r}")


def validate_semantics(instance):
    errors = []

    validate_summary(errors, instance)
    validate_adapter_plan(errors, instance)
    validate_target_records(errors, instance)
    validate_descriptor_paths(errors, instance["descriptors"])

    return errors
