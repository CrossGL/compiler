"""Semantic checks for crosstl-runtime-adapter-descriptor-v1.schema.json."""


def validate_adapter_plan(errors, adapter_plan):
    if adapter_plan["kind"] != "crosstl-runtime-adapter-plan":
        errors.append(
            "$.adapterPlan.kind: expected 'crosstl-runtime-adapter-plan'"
        )
    if adapter_plan["scope"] != "runtime-adapter-integration-planning":
        errors.append(
            "$.adapterPlan.scope: expected "
            "'runtime-adapter-integration-planning'"
        )


def validate_host_interface_readiness(errors, instance):
    host_interface = instance["hostInterface"]
    if not isinstance(host_interface, dict) or "status" not in host_interface:
        return
    validation = instance["validation"]
    if "loadReady" not in validation:
        return

    status = host_interface["status"]
    load_ready = validation["loadReady"]
    if status == "ready" and load_ready is not True:
        errors.append("$.hostInterface.status: ready requires validation.loadReady true")
    if status in ("blocked", "unavailable") and load_ready is not False:
        errors.append(
            "$.hostInterface.status: blocked/unavailable requires "
            "validation.loadReady false"
        )


def validate_semantics(instance):
    errors = []

    validate_adapter_plan(errors, instance["adapterPlan"])
    if instance["adapterKind"] == "":
        errors.append("$.adapterKind: expected non-empty adapter kind")
    validate_host_interface_readiness(errors, instance)

    return errors
