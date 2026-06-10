"""Semantic JSON schema checks for CrossGL compiler tooling."""

from . import debug_metadata_v10
from . import debug_metadata_v11
from . import debug_metadata_v12
from . import conformance_report_v0
from . import backend_source_map_v1
from . import crosstl_project_portability_report_v1
from . import diagnostics_v1
from . import doctor_v1
from . import graphics_abi_v1
from . import graphics_abi_verify_v1
from . import hir_source_map_v6
from . import hir_source_map_v7
from . import hir_source_map_v8
from . import language_feature_report_v1
from . import manifest_v1
from . import native_artifact_v0
from . import package_inspect_v1
from . import package_maintenance_report_v1
from . import package_maintenance_policy_v1
from . import package_maintenance_set_v1
from . import package_maintenance_set_report_v1
from . import package_maintenance_set_verification_batch_report_v1
from . import package_maintenance_set_verification_batch_summary_v1
from . import package_maintenance_set_verification_batch_v1
from . import package_maintenance_set_verification_v1
from . import package_recover_v1
from . import package_release_bundle_v1
from . import package_release_bundle_verification_v1
from . import package_release_publish_plan_v1
from . import package_release_publish_receipt_v1
from . import package_release_publish_receipt_v2
from . import package_release_publish_stage_v1
from . import package_release_publish_target_v1
from . import package_release_publish_upload_batch_v1
from . import package_release_publish_upload_manifest_v1
from . import package_release_publish_upload_preflight_v1
from . import package_release_publish_upload_receipt_v1
from . import package_release_promotion_manifest_v1
from . import package_sidecars_v1
from . import package_stale_sidecars_v1
from . import package_verify_v1
from . import reflection_v1
from . import release_report_artifact_inventory_v1
from . import release_provenance_manifest_v1
from . import source_batch_result_v1
from . import source_remap_v1
from . import source_remap_provenance_v1
from . import target_capability_registry_v1
from . import target_explanation_v1
from . import target_legalization_result_v0
from . import vulkan_native_profile_v1


def validate_semantics(instance, schema):
    schema_id = schema.get("$id", "")
    if schema_id.endswith("/backend-source-map-v1.schema.json"):
        return backend_source_map_v1.validate_semantics(instance)
    if schema_id.endswith("/conformance-report-v0.schema.json"):
        return conformance_report_v0.validate_semantics(instance)
    if schema_id.endswith("/crosstl-project-portability-report-v1.schema.json"):
        return crosstl_project_portability_report_v1.validate_semantics(instance)
    if schema_id.endswith("/diagnostics-v1.schema.json"):
        return diagnostics_v1.validate_semantics(instance)
    if schema_id.endswith("/doctor-v1.schema.json"):
        return doctor_v1.validate_semantics(instance)
    if schema_id.endswith("/graphics-abi-v1.schema.json"):
        return graphics_abi_v1.validate_semantics(instance)
    if schema_id.endswith("/graphics-abi-verify-v1.schema.json"):
        return graphics_abi_verify_v1.validate_semantics(instance)
    if schema_id.endswith("/reflection-v1.schema.json"):
        return reflection_v1.validate_semantics(instance)
    if schema_id.endswith("/release-report-artifact-inventory-v1.schema.json"):
        return release_report_artifact_inventory_v1.validate_semantics(instance)
    if schema_id.endswith("/release-provenance-manifest-v1.schema.json"):
        return release_provenance_manifest_v1.validate_semantics(instance)
    if schema_id.endswith("/source-remap-v1.schema.json"):
        return source_remap_v1.validate_semantics(instance)
    if schema_id.endswith("/source-remap-provenance-v1.schema.json"):
        return source_remap_provenance_v1.validate_semantics(instance)
    if schema_id.endswith("/source-batch-result-v1.schema.json"):
        return source_batch_result_v1.validate_semantics(instance)
    if schema_id.endswith("/debug-metadata-v10.schema.json"):
        return debug_metadata_v10.validate_semantics(instance)
    if schema_id.endswith("/debug-metadata-v11.schema.json"):
        return debug_metadata_v11.validate_semantics(instance)
    if schema_id.endswith("/debug-metadata-v12.schema.json"):
        return debug_metadata_v12.validate_semantics(instance)
    if schema_id.endswith("/hir-source-map-v6.schema.json"):
        return hir_source_map_v6.validate_semantics(instance)
    if schema_id.endswith("/hir-source-map-v7.schema.json"):
        return hir_source_map_v7.validate_semantics(instance)
    if schema_id.endswith("/hir-source-map-v8.schema.json"):
        return hir_source_map_v8.validate_semantics(instance)
    if schema_id.endswith("/language-feature-report-v1.schema.json"):
        return language_feature_report_v1.validate_semantics(instance)
    if schema_id.endswith("/manifest-v1.schema.json"):
        return manifest_v1.validate_semantics(instance)
    if schema_id.endswith("/native-artifact-v0.schema.json"):
        return native_artifact_v0.validate_semantics(instance)
    if schema_id.endswith("/package-inspect-v1.schema.json"):
        return package_inspect_v1.validate_semantics(instance)
    if schema_id.endswith("/package-maintenance-report-v1.schema.json"):
        return package_maintenance_report_v1.validate_semantics(instance)
    if schema_id.endswith("/package-maintenance-policy-v1.schema.json"):
        return package_maintenance_policy_v1.validate_semantics(instance)
    if schema_id.endswith("/package-maintenance-set-v1.schema.json"):
        return package_maintenance_set_v1.validate_semantics(instance)
    if schema_id.endswith("/package-maintenance-set-report-v1.schema.json"):
        return package_maintenance_set_report_v1.validate_semantics(instance)
    if schema_id.endswith(
        "/package-maintenance-set-verification-batch-report-v1.schema.json"
    ):
        return package_maintenance_set_verification_batch_report_v1.validate_semantics(
            instance
        )
    if schema_id.endswith(
        "/package-maintenance-set-verification-batch-summary-v1.schema.json"
    ):
        return package_maintenance_set_verification_batch_summary_v1.validate_semantics(
            instance
        )
    if schema_id.endswith("/package-maintenance-set-verification-batch-v1.schema.json"):
        return package_maintenance_set_verification_batch_v1.validate_semantics(
            instance
        )
    if schema_id.endswith("/package-maintenance-set-verification-v1.schema.json"):
        return package_maintenance_set_verification_v1.validate_semantics(instance)
    if schema_id.endswith("/package-recover-v1.schema.json"):
        return package_recover_v1.validate_semantics(instance)
    if schema_id.endswith("/package-release-bundle-v1.schema.json"):
        return package_release_bundle_v1.validate_semantics(instance)
    if schema_id.endswith("/package-release-bundle-verification-v1.schema.json"):
        return package_release_bundle_verification_v1.validate_semantics(instance)
    if schema_id.endswith("/package-release-publish-plan-v1.schema.json"):
        return package_release_publish_plan_v1.validate_semantics(instance)
    if schema_id.endswith("/package-release-publish-receipt-v1.schema.json"):
        return package_release_publish_receipt_v1.validate_semantics(instance)
    if schema_id.endswith("/package-release-publish-receipt-v2.schema.json"):
        return package_release_publish_receipt_v2.validate_semantics(instance)
    if schema_id.endswith("/package-release-publish-stage-v1.schema.json"):
        return package_release_publish_stage_v1.validate_semantics(instance)
    if schema_id.endswith("/package-release-publish-target-v1.schema.json"):
        return package_release_publish_target_v1.validate_semantics(instance)
    if schema_id.endswith("/package-release-publish-upload-batch-v1.schema.json"):
        return package_release_publish_upload_batch_v1.validate_semantics(instance)
    if schema_id.endswith("/package-release-publish-upload-manifest-v1.schema.json"):
        return package_release_publish_upload_manifest_v1.validate_semantics(instance)
    if schema_id.endswith("/package-release-publish-upload-preflight-v1.schema.json"):
        return package_release_publish_upload_preflight_v1.validate_semantics(instance)
    if schema_id.endswith("/package-release-publish-upload-receipt-v1.schema.json"):
        return package_release_publish_upload_receipt_v1.validate_semantics(instance)
    if schema_id.endswith("/package-release-promotion-manifest-v1.schema.json"):
        return package_release_promotion_manifest_v1.validate_semantics(instance)
    if schema_id.endswith("/package-sidecars-v1.schema.json"):
        return package_sidecars_v1.validate_semantics(instance)
    if schema_id.endswith("/package-stale-sidecars-v1.schema.json"):
        return package_stale_sidecars_v1.validate_semantics(instance)
    if schema_id.endswith("/package-verify-v1.schema.json"):
        return package_verify_v1.validate_semantics(instance)
    if schema_id.endswith("/target-explanation-v1.schema.json"):
        return target_explanation_v1.validate_semantics(instance)
    if schema_id.endswith("/target-capability-registry-v1.schema.json"):
        return target_capability_registry_v1.validate_semantics(instance)
    if schema_id.endswith("/target-legalization-result-v0.schema.json"):
        return target_legalization_result_v0.validate_semantics(instance)
    if schema_id.endswith("/vulkan-native-profile-v1.schema.json"):
        return vulkan_native_profile_v1.validate_semantics(instance)
    return []
