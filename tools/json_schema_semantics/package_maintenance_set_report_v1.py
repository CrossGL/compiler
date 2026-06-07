"""Semantic checks for package-maintenance-set-report-v1.schema.json."""

from .package_maintenance_report_v1 import validate_semantics as validate_aggregate


def validate_semantics(instance):
    return validate_aggregate(instance)
