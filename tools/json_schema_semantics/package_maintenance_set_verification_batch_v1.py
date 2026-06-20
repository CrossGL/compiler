"""Semantic checks for package-maintenance-set-verification-batch-v1.schema.json."""


def validate_semantics(instance):
    errors = []
    verifications = instance["verifications"]

    if not verifications:
        errors.append("$.verifications: expected at least one verification")

    seen = set()
    for index, verification in enumerate(verifications):
        root_path = verification["rootPath"]
        set_path = verification["setPath"]
        if root_path == "":
            errors.append(f"$.verifications[{index}].rootPath: expected non-empty path")
        if set_path == "":
            errors.append(f"$.verifications[{index}].setPath: expected non-empty path")
        key = (root_path, set_path)
        if key in seen:
            errors.append(f"$.verifications[{index}]: duplicate rootPath/setPath pair")
        seen.add(key)

    return errors
