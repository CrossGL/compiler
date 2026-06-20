"""Semantic checks for package-maintenance-set-v1.schema.json."""


def validate_semantics(instance):
    errors = []
    packages = instance["packages"]
    if not packages:
        errors.append("$.packages: expected at least one package path")

    package_paths = [package for package in packages if isinstance(package, str)]
    if package_paths != sorted(package_paths):
        errors.append("$.packages: expected sorted package paths")

    seen = set()
    for index, package in enumerate(packages):
        if not isinstance(package, str):
            continue
        if package == "":
            errors.append(f"$.packages[{index}]: expected non-empty package path")
        if package in seen:
            errors.append(f"$.packages[{index}]: duplicate package path")
        seen.add(package)
    return errors
