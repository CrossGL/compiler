"""Semantic checks for package-release-publish-target-v1.schema.json."""


def is_gcs_bucket_name(value):
    if not (3 <= len(value) <= 63):
        return False
    alphanumeric = "abcdefghijklmnopqrstuvwxyz0123456789"
    allowed = alphanumeric + "-_."
    return (
        value[0] in alphanumeric
        and value[-1] in alphanumeric
        and all(character in allowed for character in value)
        and "/" not in value
        and "\\" not in value
    )


def is_normalized_relative_path(value):
    if value == "":
        return False
    if "\\" in value or value.startswith("/"):
        return False
    parts = value.split("/")
    return not any(part in ("", ".", "..") for part in parts)


def validate_local_descriptor(instance):
    errors = []
    target_path = instance.get("targetPath", "")
    if target_path == "":
        errors.append(
            "$.targetPath: expected non-empty path for local-filesystem target"
        )
    elif "://" in target_path:
        errors.append(
            "$.targetPath: expected filesystem path for local-filesystem target"
        )
    for field in ("bucket", "prefix", "credentialsEnv"):
        if field in instance:
            errors.append(f"$.{field}: expected absent for local-filesystem target")
    return errors


def validate_gcs_descriptor(instance):
    errors = []
    if instance["enabled"]:
        errors.append("$.enabled: expected false for gcs validation target")
    if "targetPath" in instance:
        errors.append("$.targetPath: expected absent for gcs target")
    bucket = instance.get("bucket", "")
    if bucket == "":
        errors.append("$.bucket: expected non-empty bucket for gcs target")
    elif not is_gcs_bucket_name(bucket):
        errors.append("$.bucket: expected valid gcs bucket name")
    if "prefix" not in instance:
        errors.append("$.prefix: expected release-scoped object prefix for gcs target")
    else:
        prefix = instance["prefix"]
        if not is_normalized_relative_path(prefix):
            errors.append("$.prefix: expected normalized relative path")
    if "credentialsEnv" not in instance:
        errors.append("$.credentialsEnv: expected explicit credential environment gate")
    elif instance["credentialsEnv"] == "":
        errors.append("$.credentialsEnv: expected non-empty value")
    return errors


def validate_semantics(instance):
    if instance["targetKind"] == "local-filesystem":
        return validate_local_descriptor(instance)
    if instance["targetKind"] == "gcs":
        return validate_gcs_descriptor(instance)
    return []
