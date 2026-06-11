"""Semantic checks for runtime-loader-plan-v1.schema.json."""

from collections import Counter

from package_target_contracts import TARGET_REQUIRED_PATH_ARTIFACTS

from .common import add_equal_error, validate_normalized_package_path


REQUIRED_METADATA_INPUTS = ["manifest.json", "reflection.json", "diagnostics.json"]
HOST_LOADER_NON_GOALS = [
    "host-code-rewriting",
    "device-execution",
    "runtime-framework-generation",
    "target-sdk-installation",
]
SEVERITIES = ("note", "warning", "error")
TARGET_RESOURCE_BINDING_METADATA_PARITY_FIELDS = (
    "bindingClass",
    "descriptorType",
    "set",
    "binding",
    "argumentIndex",
    "abi",
    "evidenceId",
    "arrayDimensions",
    "arrayElementCount",
    "storageImageFormat",
    "storageImageAccess",
)


def validate_diagnostic_counts(errors, instance):
    counts = Counter(diagnostic["severity"] for diagnostic in instance["diagnostics"])
    for severity in SEVERITIES:
        add_equal_error(
            errors,
            f"$.diagnosticCounts.{severity}",
            instance["diagnosticCounts"][severity],
            counts[severity],
            f"{severity} diagnostic count",
        )
    return counts


def validate_metadata_only_contract(errors, instance):
    if instance["metadataOnly"] is not True:
        errors.append("$.metadataOnly: runtime loader plan must be metadata-only")
    if instance["sourceParsingRequired"] is not False:
        errors.append(
            "$.sourceParsingRequired: runtime loader plan must not require source parsing"
        )
    if instance["compilerInvocationRequired"] is not False:
        errors.append(
            "$.compilerInvocationRequired: runtime loader plan must not require "
            "compiler invocation"
        )
    if instance["deviceExecutionRequired"] is not False:
        errors.append(
            "$.deviceExecutionRequired: runtime loader plan must not require "
            "device execution"
        )
    if instance["requiredMetadataInputs"] != REQUIRED_METADATA_INPUTS:
        errors.append(
            "$.requiredMetadataInputs: expected stable root metadata inputs "
            f"{REQUIRED_METADATA_INPUTS!r}"
        )

    selection = instance["runtimeArtifactSelection"]
    for field in (
        "sourceParsingRequired",
        "compilerInvocationRequired",
        "deviceExecutionRequired",
    ):
        add_equal_error(
            errors,
            f"$.runtimeArtifactSelection.{field}",
            selection[field],
            instance[field],
            f"$.{field}",
        )
    if selection["sourceInputs"] != []:
        errors.append("$.runtimeArtifactSelection.sourceInputs: expected []")


def validate_target_and_mode(errors, instance):
    package_target = instance["packageTarget"]
    requested_target = instance["requestedLoaderTarget"]
    targets_match = (
        package_target is not None
        and requested_target is not None
        and package_target == requested_target
    )
    add_equal_error(
        errors,
        "$.targetMatchesPackage",
        instance["targetMatchesPackage"],
        targets_match,
        "package/requested target equality",
    )
    selected_target = requested_target if instance["success"] else None
    add_equal_error(
        errors,
        "$.selectedTarget",
        instance["selectedTarget"],
        selected_target,
        "successful requested loader target",
    )
    add_equal_error(
        errors,
        "$.loadable",
        instance["loadable"],
        instance["success"],
        "$.success",
    )

    selected_mode = instance["selectedPackageMode"]
    selected_artifact = instance["selectedArtifact"]
    if instance["success"]:
        if selected_mode is None:
            errors.append("$.selectedPackageMode: successful plan requires mode")
        if selected_artifact is None:
            errors.append("$.selectedArtifact: successful plan requires artifact")
        if not instance["targetMatchesPackage"]:
            errors.append("$.success: successful plan requires matching target")
    else:
        if instance["diagnosticCounts"]["error"] == 0:
            errors.append("$.success: failed plan requires at least one error")

    if selected_artifact is None:
        if selected_mode is not None:
            errors.append(
                "$.selectedPackageMode: must be null when selectedArtifact is null"
            )
        if instance["runtimeArtifactPath"] is not None:
            errors.append(
                "$.runtimeArtifactPath: must be null when selectedArtifact is null"
            )
        validate_runtime_artifact_selection(errors, instance)
        return

    add_equal_error(
        errors,
        "$.selectedArtifact.packageMode",
        selected_artifact["packageMode"],
        selected_mode,
        "$.selectedPackageMode",
    )
    if selected_mode is None:
        errors.append(
            "$.selectedPackageMode: selectedArtifact requires selectedPackageMode"
        )
        return
    expected_artifact = {
        "native": "nativeBinary",
        "source-package": "backendSource",
    }[selected_mode]
    add_equal_error(
        errors,
        "$.selectedArtifact.name",
        selected_artifact["name"],
        expected_artifact,
        f"{selected_mode} artifact",
    )
    if not selected_artifact["packageRelative"]:
        errors.append("$.selectedArtifact.packageRelative: expected true")
    if not selected_artifact["exists"]:
        errors.append("$.selectedArtifact.exists: expected true")
    if selected_artifact["path"].startswith("/"):
        errors.append("$.selectedArtifact.path: expected normalized package path")
    validate_normalized_package_path(
        errors,
        "$.selectedArtifact.path",
        selected_artifact["path"],
    )
    add_equal_error(
        errors,
        "$.runtimeArtifactPath",
        instance["runtimeArtifactPath"],
        selected_artifact["path"],
        "$.selectedArtifact.path",
    )

    requested_mode = instance["requestedPackageMode"]
    if requested_mode != "auto" and selected_mode != requested_mode:
        errors.append(
            "$.selectedPackageMode: explicit requestedPackageMode must select "
            f"{requested_mode!r}"
        )
    validate_runtime_artifact_selection(errors, instance)


def validate_runtime_artifact_selection(errors, instance):
    selection = instance["runtimeArtifactSelection"]
    equal_fields = (
        ("requestedTarget", "requestedLoaderTarget"),
        ("requestedPackageMode", "requestedPackageMode"),
        ("packageTarget", "packageTarget"),
        ("selectedTarget", "selectedTarget"),
        ("selectedPackageMode", "selectedPackageMode"),
    )
    for selection_field, top_level_field in equal_fields:
        add_equal_error(
            errors,
            f"$.runtimeArtifactSelection.{selection_field}",
            selection[selection_field],
            instance[top_level_field],
            f"$.{top_level_field}",
        )
    add_equal_error(
        errors,
        "$.runtimeArtifactSelection.selected",
        selection["selected"],
        instance["success"],
        "$.success",
    )
    add_equal_error(
        errors,
        "$.runtimeArtifactSelection.artifact",
        selection["artifact"],
        instance["selectedArtifact"],
        "$.selectedArtifact",
    )


def validate_artifact_requirements(errors, instance):
    requirements = instance["packageArtifactRequirements"]
    package_target = instance["packageTarget"]
    if requirements is None:
        if instance["success"]:
            errors.append(
                "$.packageArtifactRequirements: successful plan requires requirements"
            )
        if instance["requiredArtifacts"] != []:
            errors.append("$.requiredArtifacts: expected [] without requirements")
        if instance["requiredArtifactPaths"] != {}:
            errors.append("$.requiredArtifactPaths: expected {} without requirements")
        return

    add_equal_error(
        errors,
        "$.packageArtifactRequirements.target",
        requirements["target"],
        package_target,
        "$.packageTarget",
    )
    add_equal_error(
        errors,
        "$.requiredArtifacts",
        instance["requiredArtifacts"],
        requirements["requiredPathArtifacts"],
        "$.packageArtifactRequirements.requiredPathArtifacts",
    )
    required_path_keys = list(instance["requiredArtifactPaths"].keys())
    if sorted(required_path_keys) != sorted(instance["requiredArtifacts"]):
        errors.append(
            "$.requiredArtifactPaths: expected exactly the requiredArtifacts keys"
        )
    for artifact_name, artifact_path in instance["requiredArtifactPaths"].items():
        if artifact_path is None:
            continue
        if artifact_path.startswith("/"):
            errors.append(
                f"$.requiredArtifactPaths.{artifact_name}: expected package path"
            )
        validate_normalized_package_path(
            errors,
            f"$.requiredArtifactPaths.{artifact_name}",
            artifact_path,
        )

    expected_artifacts = TARGET_REQUIRED_PATH_ARTIFACTS.get(requirements["target"])
    if expected_artifacts is not None:
        expected_artifacts = list(expected_artifacts)
        if requirements["requiredPathArtifacts"] != expected_artifacts:
            errors.append(
                "$.packageArtifactRequirements.requiredPathArtifacts: expected "
                f"target contract artifacts {expected_artifacts!r}, got "
                f"{requirements['requiredPathArtifacts']!r}"
            )

    selected_artifact = instance["selectedArtifact"]
    if selected_artifact is not None and (
        selected_artifact["name"] not in requirements["requiredPathArtifacts"]
    ):
        errors.append(
            "$.selectedArtifact.name: expected artifact required by package "
            "artifact requirements"
        )


def validate_target_legalization_summary(errors, instance):
    summary = instance["targetLegalizationEvidenceSummary"]
    if summary is None:
        if instance["success"]:
            errors.append(
                "$.targetLegalizationEvidenceSummary: successful plan requires summary"
            )
        return

    if summary["toolRequirementsPresent"]:
        add_equal_error(
            errors,
            "$.targetLegalizationEvidenceSummary.target",
            summary["target"],
            instance["packageTarget"],
            "$.packageTarget",
        )
        if (
            summary["packageMode"] is not None
            and instance["packageArtifactRequirements"]
        ):
            add_equal_error(
                errors,
                "$.targetLegalizationEvidenceSummary.packageMode",
                summary["packageMode"],
                instance["packageArtifactRequirements"]["packageMode"],
                "$.packageArtifactRequirements.packageMode",
            )
    else:
        for field in ("target", "packageMode"):
            if summary[field] is not None:
                errors.append(
                    f"$.targetLegalizationEvidenceSummary.{field}: expected null "
                    "when tool requirements are absent"
                )

    add_equal_error(
        errors,
        "$.targetLegalizationEvidenceSummary.requiredToolCount",
        summary["requiredToolCount"],
        len(summary["requiredToolIds"]),
        "requiredToolIds length",
    )
    add_equal_error(
        errors,
        "$.targetLegalizationEvidenceSummary.missingToolCount",
        summary["missingToolCount"],
        len(summary["missingToolIds"]),
        "missingToolIds length",
    )


def validate_reflection_summary(errors, instance):
    summary = instance["reflectionSummary"]
    if summary is None:
        if instance["success"]:
            errors.append("$.reflectionSummary: successful plan requires summary")
        return

    if summary["threadgroupShapeSource"] != "reflection.workgroupSizes":
        errors.append(
            "$.reflectionSummary.threadgroupShapeSource: expected "
            "reflection.workgroupSizes"
        )
    if (
        summary["workgroupSizeCount"] is not None
        and summary["entryPointCount"] is not None
        and summary["workgroupSizeCount"] > summary["entryPointCount"]
    ):
        errors.append(
            "$.reflectionSummary.workgroupSizeCount: expected <= entryPointCount"
        )


def validate_reflection_inputs(errors, instance):
    inputs = instance["reflectionInputs"]
    summary = instance["reflectionSummary"]
    if inputs is None:
        if instance["success"]:
            errors.append("$.reflectionInputs: successful plan requires inputs")
        return

    add_equal_error(
        errors,
        "$.reflectionInputs.selectedTarget",
        inputs["selectedTarget"],
        instance["selectedTarget"],
        "$.selectedTarget",
    )
    add_equal_error(
        errors,
        "$.reflectionInputs.entryPointCount",
        inputs["entryPointCount"],
        len(inputs["entryPoints"]),
        "entryPoints length",
    )
    add_equal_error(
        errors,
        "$.reflectionInputs.resourceCount",
        inputs["resourceCount"],
        len(inputs["resources"]),
        "resources length",
    )
    add_equal_error(
        errors,
        "$.reflectionInputs.targetResourceBindingCount",
        inputs["targetResourceBindingCount"],
        len(inputs["targetResourceBindings"]),
        "targetResourceBindings length",
    )
    add_equal_error(
        errors,
        "$.reflectionInputs.targetFeatureCount",
        inputs["targetFeatureCount"],
        len(inputs["targetFeatures"]),
        "targetFeatures length",
    )
    add_equal_error(
        errors,
        "$.reflectionInputs.workgroupSizeCount",
        inputs["workgroupSizeCount"],
        len(inputs["workgroupSizes"]),
        "workgroupSizes length",
    )
    add_equal_error(
        errors,
        "$.reflectionInputs.functionConstantCount",
        inputs["functionConstantCount"],
        len(inputs["functionConstants"]),
        "functionConstants length",
    )
    add_equal_error(
        errors,
        "$.reflectionInputs.specializationConstantCount",
        inputs["specializationConstantCount"],
        sum(
            1 for record in inputs["functionConstants"] if "specializationId" in record
        ),
        "functionConstants specializationId count",
    )
    add_equal_error(
        errors,
        "$.reflectionInputs.workgroupSizesAvailable",
        inputs["workgroupSizesAvailable"],
        inputs["workgroupSizeCount"] > 0,
        "workgroup size availability",
    )
    add_equal_error(
        errors,
        "$.reflectionInputs.functionConstantsAvailable",
        inputs["functionConstantsAvailable"],
        inputs["functionConstantCount"] > 0,
        "function constant availability",
    )

    if summary is not None:
        for field in (
            "resourceCount",
            "targetResourceBindingCount",
            "targetFeatureCount",
        ):
            add_equal_error(
                errors,
                f"$.reflectionInputs.{field}",
                inputs[field],
                summary[field],
                f"$.reflectionSummary.{field}",
            )
        if summary["entryPointCount"] is not None:
            add_equal_error(
                errors,
                "$.reflectionInputs.entryPointCount",
                inputs["entryPointCount"],
                summary["entryPointCount"],
                "$.reflectionSummary.entryPointCount",
            )
        if summary["workgroupSizeCount"] is not None:
            add_equal_error(
                errors,
                "$.reflectionInputs.workgroupSizeCount",
                inputs["workgroupSizeCount"],
                summary["workgroupSizeCount"],
                "$.reflectionSummary.workgroupSizeCount",
            )
        if summary["functionConstantCount"] is not None:
            add_equal_error(
                errors,
                "$.reflectionInputs.functionConstantCount",
                inputs["functionConstantCount"],
                summary["functionConstantCount"],
                "$.reflectionSummary.functionConstantCount",
            )
        if summary["specializationConstantCount"] is not None:
            add_equal_error(
                errors,
                "$.reflectionInputs.specializationConstantCount",
                inputs["specializationConstantCount"],
                summary["specializationConstantCount"],
                "$.reflectionSummary.specializationConstantCount",
            )

    selected_target = inputs["selectedTarget"] or instance["requestedLoaderTarget"]
    if selected_target is not None:
        for index, binding in enumerate(inputs["targetResourceBindings"]):
            add_equal_error(
                errors,
                f"$.reflectionInputs.targetResourceBindings[{index}].target",
                binding["target"],
                selected_target,
                "selected reflection target",
            )
        for index, feature in enumerate(inputs["targetFeatures"]):
            add_equal_error(
                errors,
                f"$.reflectionInputs.targetFeatures[{index}].target",
                feature["target"],
                selected_target,
                "selected reflection target",
            )


def validate_target_resource_binding_metadata(errors, instance):
    metadata = instance["targetResourceBindingMetadata"]
    summary = instance["reflectionSummary"]
    reflection_inputs = instance["reflectionInputs"]
    if metadata is None:
        if instance["success"]:
            errors.append(
                "$.targetResourceBindingMetadata: successful plan requires metadata"
            )
        return

    add_equal_error(
        errors,
        "$.targetResourceBindingMetadata.selectedTarget",
        metadata["selectedTarget"],
        instance["selectedTarget"],
        "$.selectedTarget",
    )
    add_equal_error(
        errors,
        "$.targetResourceBindingMetadata.loaderTarget",
        metadata["loaderTarget"],
        instance["requestedLoaderTarget"],
        "$.requestedLoaderTarget",
    )
    add_equal_error(
        errors,
        "$.targetResourceBindingMetadata.packageTarget",
        metadata["packageTarget"],
        instance["packageTarget"],
        "$.packageTarget",
    )
    add_equal_error(
        errors,
        "$.targetResourceBindingMetadata.bindingCount",
        metadata["bindingCount"],
        len(metadata["bindings"]),
        "bindings length",
    )
    if summary is not None:
        add_equal_error(
            errors,
            "$.targetResourceBindingMetadata.bindingCount",
            metadata["bindingCount"],
            summary["targetResourceBindingCount"],
            "$.reflectionSummary.targetResourceBindingCount",
        )
    if reflection_inputs is not None:
        add_equal_error(
            errors,
            "$.targetResourceBindingMetadata.bindingCount",
            metadata["bindingCount"],
            reflection_inputs["targetResourceBindingCount"],
            "$.reflectionInputs.targetResourceBindingCount",
        )

    selected_target = metadata["selectedTarget"] or metadata["loaderTarget"]
    reflection_binding_by_identity = {}
    if reflection_inputs is not None:
        reflection_binding_by_identity = target_resource_binding_identity_map(
            reflection_inputs["targetResourceBindings"]
        )
    for index, binding in enumerate(metadata["bindings"]):
        if selected_target is not None:
            add_equal_error(
                errors,
                f"$.targetResourceBindingMetadata.bindings[{index}].target",
                binding["target"],
                selected_target,
                "selected binding target",
            )
        for field in ("target", "stage", "entryPoint", "name", "kind"):
            add_equal_error(
                errors,
                f"$.targetResourceBindingMetadata.bindings[{index}].identity.{field}",
                binding["identity"][field],
                binding[field],
                f"$.targetResourceBindingMetadata.bindings[{index}].{field}",
            )
        if reflection_inputs is not None:
            validate_target_resource_binding_metadata_reflection_parity(
                errors,
                index,
                binding,
                reflection_binding_by_identity,
            )


def target_resource_binding_identity(record):
    return tuple(
        record.get(field) for field in ("target", "stage", "entryPoint", "name", "kind")
    )


def target_resource_binding_identity_map(bindings):
    by_identity = {}
    for index, binding in enumerate(bindings):
        identity = target_resource_binding_identity(binding)
        by_identity.setdefault(identity, (index, binding))
    return by_identity


def validate_target_resource_binding_metadata_reflection_parity(
    errors,
    metadata_index,
    metadata_binding,
    reflection_binding_by_identity,
):
    identity = target_resource_binding_identity(metadata_binding)
    reflection_record = reflection_binding_by_identity.get(identity)
    metadata_path = f"$.targetResourceBindingMetadata.bindings[{metadata_index}]"
    if reflection_record is None:
        errors.append(
            f"{metadata_path}: expected matching "
            "$.reflectionInputs.targetResourceBindings record for identity "
            f"{identity!r}"
        )
        return

    reflection_index, reflection_binding = reflection_record
    for field in TARGET_RESOURCE_BINDING_METADATA_PARITY_FIELDS:
        add_equal_error(
            errors,
            f"{metadata_path}.{field}",
            metadata_binding.get(field),
            reflection_binding.get(field),
            f"$.reflectionInputs.targetResourceBindings[{reflection_index}].{field}",
        )


def host_loader_required_tools(instance):
    summary = instance["targetLegalizationEvidenceSummary"]
    if summary is None:
        return []
    return list(summary["requiredToolIds"])


def host_loader_responsibilities(load_unit, required_tools):
    responsibilities = [
        "load-package-artifact",
        "bind-reflected-entry-points",
        "bind-reflected-resources",
    ]
    if load_unit["sourceRemap"] is not None:
        responsibilities.insert(1, "load-source-remap")
    if load_unit["hostInterface"]["workgroupSizeCount"] > 0:
        responsibilities.append("bind-workgroup-shape")
    if required_tools:
        responsibilities.append("review-target-tool-requirements")
    return responsibilities


def host_loader_artifact_format(selected_artifact):
    return (
        "native-binary"
        if selected_artifact["name"] == "nativeBinary"
        else "backend-source"
    )


def validate_host_loader_load_step_metadata(
    errors,
    index,
    step,
    selected_artifact,
    load_unit,
    summary,
):
    kind = step["kind"]
    metadata = step["metadata"]
    metadata_path = f"$.hostLoaderIntegration.loadUnits[0].loadSteps[{index}].metadata"

    source = metadata.get("source")
    if not isinstance(source, dict):
        errors.append(f"{metadata_path}.source: expected object")
        return

    if kind == "load-package-artifact":
        add_equal_error(
            errors,
            f"{metadata_path}.source.field",
            source.get("field"),
            "selectedArtifact.path",
            "selected artifact path reference",
        )
        add_equal_error(
            errors,
            f"{metadata_path}.source.path",
            source.get("path"),
            selected_artifact["path"],
            "$.selectedArtifact.path",
        )
        artifact = metadata.get("artifact")
        if not isinstance(artifact, dict):
            errors.append(f"{metadata_path}.artifact: expected object")
            return
        add_equal_error(
            errors,
            f"{metadata_path}.artifact.name",
            artifact.get("name"),
            selected_artifact["name"],
            "$.selectedArtifact.name",
        )
        add_equal_error(
            errors,
            f"{metadata_path}.artifact.packageMode",
            artifact.get("packageMode"),
            load_unit["packageMode"],
            "$.hostLoaderIntegration.loadUnits[0].packageMode",
        )
        add_equal_error(
            errors,
            f"{metadata_path}.artifact.artifactFormat",
            artifact.get("artifactFormat"),
            host_loader_artifact_format(selected_artifact),
            "selected artifact format",
        )
    elif kind == "load-source-remap":
        add_equal_error(
            errors,
            f"{metadata_path}.source.field",
            source.get("field"),
            "manifest.artifacts.sourceRemap",
            "source remap artifact reference",
        )
        source_remap = load_unit["sourceRemap"]
        expected_path = (
            source_remap["packagePath"] if source_remap is not None else None
        )
        add_equal_error(
            errors,
            f"{metadata_path}.source.path",
            source.get("path"),
            expected_path,
            "$.hostLoaderIntegration.loadUnits[0].sourceRemap.packagePath",
        )
    elif kind == "bind-host-interface":
        add_equal_error(
            errors,
            f"{metadata_path}.source.field",
            source.get("field"),
            "reflectionInputs",
            "reflection input metadata reference",
        )
        for field in (
            "entryPointCount",
            "resourceBindingCount",
            "workgroupSizeCount",
            "functionConstantCount",
            "specializationConstantCount",
        ):
            add_equal_error(
                errors,
                f"{metadata_path}.{field}",
                metadata.get(field),
                summary[field],
                f"$.hostLoaderIntegration.summary.{field}",
            )


def validate_host_loader_integration(errors, instance):
    integration = instance["hostLoaderIntegration"]
    summary = integration["summary"]
    load_units = integration["loadUnits"]
    selected_artifact = instance["selectedArtifact"]
    reflection_inputs = instance["reflectionInputs"]
    selected_artifact_present = selected_artifact is not None
    host_interface_ready = (
        instance["success"]
        and selected_artifact_present
        and reflection_inputs is not None
        and reflection_inputs["entryPointCount"] > 0
    )

    add_equal_error(
        errors,
        "$.hostLoaderIntegration.nonGoals",
        integration["nonGoals"],
        HOST_LOADER_NON_GOALS,
        "stable host-loader non-goals",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.summary.loadUnitCount",
        summary["loadUnitCount"],
        len(load_units),
        "loadUnits length",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.summary.targetCount",
        summary["targetCount"],
        1 if selected_artifact_present else 0,
        "selected artifact target count",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.summary.readyLoadUnitCount",
        summary["readyLoadUnitCount"],
        1 if host_interface_ready else 0,
        "ready host-loader unit count",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.summary.blockedLoadUnitCount",
        summary["blockedLoadUnitCount"],
        1 if selected_artifact_present and not host_interface_ready else 0,
        "blocked host-loader unit count",
    )
    if reflection_inputs is not None:
        add_equal_error(
            errors,
            "$.hostLoaderIntegration.summary.entryPointCount",
            summary["entryPointCount"],
            reflection_inputs["entryPointCount"],
            "$.reflectionInputs.entryPointCount",
        )
        add_equal_error(
            errors,
            "$.hostLoaderIntegration.summary.resourceBindingCount",
            summary["resourceBindingCount"],
            reflection_inputs["targetResourceBindingCount"],
            "$.reflectionInputs.targetResourceBindingCount",
        )
        add_equal_error(
            errors,
            "$.hostLoaderIntegration.summary.workgroupSizeCount",
            summary["workgroupSizeCount"],
            reflection_inputs["workgroupSizeCount"],
            "$.reflectionInputs.workgroupSizeCount",
        )
        add_equal_error(
            errors,
            "$.hostLoaderIntegration.summary.functionConstantCount",
            summary["functionConstantCount"],
            reflection_inputs["functionConstantCount"],
            "$.reflectionInputs.functionConstantCount",
        )
        add_equal_error(
            errors,
            "$.hostLoaderIntegration.summary.specializationConstantCount",
            summary["specializationConstantCount"],
            reflection_inputs["specializationConstantCount"],
            "$.reflectionInputs.specializationConstantCount",
        )
    elif any(
        summary[field] != 0
        for field in (
            "entryPointCount",
            "resourceBindingCount",
            "workgroupSizeCount",
            "functionConstantCount",
            "specializationConstantCount",
        )
    ):
        errors.append(
            "$.hostLoaderIntegration.summary: expected zero interface counts "
            "without reflectionInputs"
        )

    expected_status = (
        "ready"
        if host_interface_ready
        else ("blocked" if selected_artifact_present else "unavailable")
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.status",
        integration["status"],
        expected_status,
        "host-loader readiness",
    )
    if not selected_artifact_present:
        if load_units:
            errors.append(
                "$.hostLoaderIntegration.loadUnits: expected [] without "
                "selectedArtifact"
            )
        return

    if len(load_units) != 1:
        errors.append("$.hostLoaderIntegration.loadUnits: expected one load unit")
        return
    load_unit = load_units[0]
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].target",
        load_unit["target"],
        instance["selectedTarget"],
        "$.selectedTarget",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].packageMode",
        load_unit["packageMode"],
        instance["selectedPackageMode"],
        "$.selectedPackageMode",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].artifact",
        load_unit["artifact"],
        selected_artifact,
        "$.selectedArtifact",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].packagePath",
        load_unit["packagePath"],
        selected_artifact["path"],
        "$.selectedArtifact.path",
    )
    expected_id = (
        f"runtime-loader.{load_unit['target'] or 'unselected'}."
        f"{selected_artifact['name']}"
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].id",
        load_unit["id"],
        expected_id,
        "stable host-loader load-unit id",
    )
    expected_adapter_kind = (
        "native-binary-loader"
        if selected_artifact["name"] == "nativeBinary"
        else "backend-source-loader"
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].artifactFormat",
        load_unit["artifactFormat"],
        host_loader_artifact_format(selected_artifact),
        "selected artifact format",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].adapterKind",
        load_unit["adapterKind"],
        expected_adapter_kind,
        "selected artifact adapter kind",
    )
    expected_required_tools = host_loader_required_tools(instance)
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].requiredTools",
        load_unit["requiredTools"],
        expected_required_tools,
        "$.targetLegalizationEvidenceSummary.requiredToolIds",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].hostResponsibilities",
        load_unit["hostResponsibilities"],
        host_loader_responsibilities(load_unit, expected_required_tools),
        "stable host-loader responsibilities",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].validation.loadReady",
        load_unit["validation"]["loadReady"],
        host_interface_ready,
        "host interface readiness",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].hostInterface.entryPointCount",
        load_unit["hostInterface"]["entryPointCount"],
        summary["entryPointCount"],
        "$.hostLoaderIntegration.summary.entryPointCount",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].hostInterface.resourceBindingCount",
        load_unit["hostInterface"]["resourceBindingCount"],
        summary["resourceBindingCount"],
        "$.hostLoaderIntegration.summary.resourceBindingCount",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].hostInterface.workgroupSizeCount",
        load_unit["hostInterface"]["workgroupSizeCount"],
        summary["workgroupSizeCount"],
        "$.hostLoaderIntegration.summary.workgroupSizeCount",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].hostInterface.functionConstantCount",
        load_unit["hostInterface"]["functionConstantCount"],
        summary["functionConstantCount"],
        "$.hostLoaderIntegration.summary.functionConstantCount",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].hostInterface.specializationConstantCount",
        load_unit["hostInterface"]["specializationConstantCount"],
        summary["specializationConstantCount"],
        "$.hostLoaderIntegration.summary.specializationConstantCount",
    )

    expected_unit_status = "ready" if host_interface_ready else "blocked"
    expected_interface_status = "ready" if host_interface_ready else "unavailable"
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].status",
        load_unit["status"],
        expected_unit_status,
        "host-loader unit readiness",
    )
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].hostInterface.status",
        load_unit["hostInterface"]["status"],
        expected_interface_status,
        "host interface readiness",
    )
    source_remap = load_unit["sourceRemap"]
    expected_step_kinds = ["load-package-artifact"]
    if source_remap is not None:
        expected_step_kinds.append("load-source-remap")
    if host_interface_ready:
        expected_step_kinds.append("bind-host-interface")
    add_equal_error(
        errors,
        "$.hostLoaderIntegration.loadUnits[0].loadSteps[].kind",
        [step["kind"] for step in load_unit["loadSteps"]],
        expected_step_kinds,
        "stable host-loader step order",
    )
    expected_messages = {
        "load-package-artifact": "Load the selected runtime package artifact.",
        "load-source-remap": "Load source remap provenance for diagnostics.",
        "bind-host-interface": "Bind reflected host interface metadata.",
    }
    for index, step in enumerate(load_unit["loadSteps"]):
        kind = step["kind"]
        add_equal_error(
            errors,
            f"$.hostLoaderIntegration.loadUnits[0].loadSteps[{index}].message",
            step["message"],
            expected_messages[kind],
            f"stable {kind} message",
        )
        add_equal_error(
            errors,
            f"$.hostLoaderIntegration.loadUnits[0].loadSteps[{index}].target",
            step["target"],
            load_unit["target"],
            "$.hostLoaderIntegration.loadUnits[0].target",
        )
        add_equal_error(
            errors,
            f"$.hostLoaderIntegration.loadUnits[0].loadSteps[{index}].hostInterfaceStatus",
            step["hostInterfaceStatus"],
            load_unit["hostInterface"]["status"],
            "$.hostLoaderIntegration.loadUnits[0].hostInterface.status",
        )
        expected_package_path = (
            source_remap["packagePath"]
            if kind == "load-source-remap" and source_remap is not None
            else selected_artifact["path"]
        )
        add_equal_error(
            errors,
            f"$.hostLoaderIntegration.loadUnits[0].loadSteps[{index}].packagePath",
            step["packagePath"],
            expected_package_path,
            f"stable {kind} package path",
        )
        validate_host_loader_load_step_metadata(
            errors,
            index,
            step,
            selected_artifact,
            load_unit,
            summary,
        )
    if host_interface_ready:
        if load_unit["blockers"] != []:
            errors.append(
                "$.hostLoaderIntegration.loadUnits[0].blockers: expected [] "
                "for ready unit"
            )
    elif not load_unit["blockers"]:
        errors.append(
            "$.hostLoaderIntegration.loadUnits[0].blockers: blocked unit "
            "requires blocker"
        )


def validate_semantics(instance):
    errors = []
    counts = validate_diagnostic_counts(errors, instance)
    validate_metadata_only_contract(errors, instance)
    validate_target_and_mode(errors, instance)
    validate_artifact_requirements(errors, instance)
    validate_target_legalization_summary(errors, instance)
    validate_reflection_summary(errors, instance)
    validate_reflection_inputs(errors, instance)
    validate_target_resource_binding_metadata(errors, instance)
    validate_host_loader_integration(errors, instance)

    add_equal_error(
        errors,
        "$.success",
        instance["success"],
        counts["error"] == 0,
        "zero-error diagnostic status",
    )
    return errors
