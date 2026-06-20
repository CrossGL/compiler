"""Semantic checks for package-maintenance-policy-v1.schema.json."""


def validate_semantics(instance):
    errors = []
    stale_sidecars = instance.get("staleSidecars")
    if not isinstance(stale_sidecars, dict):
        return errors

    configured = [
        key
        for key in ("keepLast", "olderThanSeconds")
        if isinstance(stale_sidecars.get(key), int)
        and not isinstance(stale_sidecars.get(key), bool)
    ]
    if not configured:
        errors.append(
            "$.staleSidecars: expected keepLast or olderThanSeconds to be set"
        )
    return errors
