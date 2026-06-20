# Target Legalization Result Contract v0

This document defines the minimal report-only `LegalizationResult` JSON shape
for Milestone 2 groundwork. It is a machine-checkable contract for future target
support decisions, but it does not change backend behavior, package behavior,
runtime behavior, release policy, or existing production serialized schemas.
The structural schema is
`docs/schemas/target-legalization-result-v0.schema.json`; the schema and checker
are report-only validation aids for the next target-legalization result shape.

## Status

v0 is report-only until consumers migrate. The current compiler behavior remains
the decision authority for target support, package artifact production,
diagnostics, reflection, debug metadata, verification, and runtime admission.
The result contract version stays `v0`, while target legalization evidence IDs
use the shared compiler/schema evidence namespace `target-legalization.v1`.
The compiler can serialize real `legalizeTarget` / `legalizeTargets` decisions
to this v0 JSON shape through `targetLegalizationResultV0Json`. That projection
is evidence-only: it normalizes existing legalization decisions into the v0
report vocabulary and does not select targets, enable unsupported backends, or
change package artifact emission.

The exact v0 policy block is:

```json
{
  "mode": "report-only",
  "decisionAuthority": "current-compiler-behavior",
  "consumerMigration": "pending",
  "productionBehavior": "unchanged"
}
```

Any future behavior-changing consumer must migrate explicitly and keep this
contract as the recorded decision source before it can gate production.

## JSON Shape

Each fixture is one target legalization result document:

<!-- crossgl-target-legalization-result-v0-example:begin -->
```json
{
  "contract": "crossgl.target-legalization-result.v0",
  "schemaVersion": 0,
  "policy": {
    "mode": "report-only",
    "decisionAuthority": "current-compiler-behavior",
    "consumerMigration": "pending",
    "productionBehavior": "unchanged"
  },
  "result": {
    "target": "vulkan",
    "targetProfile": {
      "target": "vulkan",
      "profile": "vulkan.v0.native",
      "packageMode": "native"
    },
    "packageMode": "native",
    "packageDecisionProvenance": "native-package-available",
    "supportStatus": "native",
    "moduleSupported": true,
    "requiredCapabilities": [
      "vulkan.backend.spirv-lowering",
      "vulkan.package.native-artifact"
    ],
    "missingCapabilities": [],
    "toolRequirements": {
      "requiredToolIds": [
        "vulkan.toolchain.spirv-as",
        "vulkan.validation.spirv-val"
      ],
      "missingToolIds": [],
      "optionalNativeToolMissing": false,
      "optionalNativeToolStatus": "not-required",
      "evidenceIds": [
        "target-legalization.v1.vulkan.tool-requirement.required.toolchain.spirv-as",
        "target-legalization.v1.vulkan.tool-requirement.required.validation.spirv-val",
        "target-legalization.v1.vulkan.tool-requirements.present"
      ],
      "records": [
        {
          "id": "vulkan.toolchain.spirv-as",
          "kind": "toolchain",
          "name": "spirv-as",
          "status": "required",
          "target": "vulkan",
          "evidenceIds": [
            "target-legalization.v1.vulkan.tool-requirement.required.toolchain.spirv-as"
          ]
        },
        {
          "id": "vulkan.validation.spirv-val",
          "kind": "validation",
          "name": "spirv-val",
          "status": "required",
          "target": "vulkan",
          "evidenceIds": [
            "target-legalization.v1.vulkan.tool-requirement.required.validation.spirv-val"
          ]
        }
      ]
    },
    "diagnostics": [],
    "rewrites": [
      {
        "id": "descriptor-set-normalization",
        "order": 0,
        "status": "not-required",
        "description": "No target-aware rewrite is required for this fixture.",
        "evidenceIds": [
          "target-legalization.v1.vulkan.rewrite.not-required"
        ]
      }
    ],
    "abiFacts": {
      "state": "complete",
      "facts": [
        {
          "id": "entry-point.compute-main",
          "kind": "entry-point",
          "status": "provided",
          "target": "vulkan",
          "evidenceIds": [
            "target-legalization.v1.vulkan.abi.entry-point"
          ]
        }
      ],
      "evidenceIds": [
        "target-legalization.v1.vulkan.abi.entry-point"
      ]
    },
    "resourceBindingEvidenceIds": [
      "target-legalization.v1.vulkan.resource-bindings.empty"
    ],
    "evidenceIds": [
      "target-legalization.v1.vulkan.abi.entry-point",
      "target-legalization.v1.vulkan.decision",
      "target-legalization.v1.vulkan.package-mode.native",
      "target-legalization.v1.vulkan.package-provenance.native-package-available",
      "target-legalization.v1.vulkan.resource-bindings.empty",
      "target-legalization.v1.vulkan.rewrite.not-required",
      "target-legalization.v1.vulkan.state.legalized",
      "target-legalization.v1.vulkan.support.native",
      "target-legalization.v1.vulkan.tool-requirement.required.toolchain.spirv-as",
      "target-legalization.v1.vulkan.tool-requirement.required.validation.spirv-val",
      "target-legalization.v1.vulkan.tool-requirements.present"
    ]
  }
}
```
<!-- crossgl-target-legalization-result-v0-example:end -->

## Field Rules

Top-level fields are exact: `contract`, `schemaVersion`, `policy`, and `result`.

`result` fields are exact: `target`, `targetProfile`, `packageMode`,
`packageDecisionProvenance`, `supportStatus`, `moduleSupported`, `requiredCapabilities`,
`missingCapabilities`, `toolRequirements`, `diagnostics`, `rewrites`,
`abiFacts`, and
`resourceBindingEvidenceIds`, and `evidenceIds`.

- `target` is one of `metal`, `vulkan`, `directx`, or `opengl`.
- `targetProfile.target` must match `target`.
- `targetProfile.profile` must be exactly `<target>.v0.<packageMode>`.
- `targetProfile.packageMode` must match `packageMode`.
- `packageMode` is one of `native`, `source-package`, or `unsupported`.
- `packageDecisionProvenance` records the source decision as one of
  `native-package-available`, `source-package-only`, `unsupported`,
  `unsupported-native-form`, `unsupported-raw-hir`, or
  `unsupported-source-form`.
- `supportStatus` is the normalized support status: `native`, `source-package`,
  or `unsupported`.
- `moduleSupported` is the contract support bit for this target result.
- `requiredCapabilities` and `missingCapabilities` are sorted unique capability
  ID arrays. Supported native and source-package results must include the
  package artifact capability implied by `packageMode`:
  `<target>.package.native-artifact` for `native` or
  `<target>.package.source-artifact` for `source-package`.
- `toolRequirements` records sorted unique required and missing native-tool
  capability IDs, concrete `records` with `id`, `kind`, `name`, `status`,
  `target`, and `evidenceIds`, the `optionalNativeToolMissing` support bit, the
  normalized `optionalNativeToolStatus`, and tool requirement evidence IDs. v0
  uses this for source-package targets that remain buildable while native
  compiler or validator tools are unavailable, for source-package targets whose
  optional native tools are recorded as available, and for native package
  targets that require concrete native toolchain steps such as Metal
  `xcrun metal` / `xcrun metallib` or Vulkan `spirv-as` / `spirv-val`.
- `diagnostics` is a sorted array of structured diagnostic objects with target,
  severity, missing capability, and evidence references.
- `rewrites` is an ordered array of target-aware rewrite records. v0 can record
  `not-required` rewrite evidence without claiming a new rewrite pass.
- `abiFacts` records whether ABI facts are complete, not required, partial, or
  unsupported, plus any target ABI fact records that future reflection/debug
  metadata consumers can project.
- `resourceBindingEvidenceIds` records the resource ABI evidence generated by
  target legalization. Empty-resource modules still carry an explicit
  `resource-bindings.empty` evidence ID.
- `evidenceIds` is the sorted unique target legalization evidence source for
  the result. Nested diagnostic, rewrite, ABI, and resource binding evidence IDs
  must be present in this top-level list. Support and package decisions must
  also carry their canonical `state.*`, `support.*`, `package-mode.*`,
  `package-provenance.*`, and `decision` evidence IDs at top level.

## Invariants

- `packageMode` is `unsupported` if and only if `moduleSupported` is `false`.
- `supportStatus` must be `native` for native support, `source-package` for
  source-package support, or `unsupported` for unsupported results. It must
  agree with both `moduleSupported` and `packageMode`.
- `packageMode` of `native` requires `packageDecisionProvenance` of
  `native-package-available`; `packageMode` of `source-package` requires
  `packageDecisionProvenance` of `source-package-only`.
- `packageMode` of `unsupported` must not carry `native-package-available` or
  `source-package-only` provenance.
- `source-package` is valid only for `directx` and `opengl` v0 source-package
  targets.
- `missingCapabilities` must be a subset of `requiredCapabilities`.
- `packageMode` and package artifact capability expectations must agree:
  `native` requires `<target>.package.native-artifact` and must not require
  `<target>.package.source-artifact`; `source-package` requires
  `<target>.package.source-artifact` and must not require
  `<target>.package.native-artifact`; `unsupported` must not advertise either
  package artifact capability.
- `toolRequirements.missingToolIds` must be a subset of
  `toolRequirements.requiredToolIds`.
- Tool requirement IDs must be target-prefixed capability IDs whose kind is
  `toolchain`, `validation`, or `native-tool`.
- `native-tool` is the canonical serialized native tool kind. The legacy
  internal spelling `nativeTool` is normalized before v0 JSON serialization and
  is diagnosed by the contract checker if it appears in serialized
  `toolRequirements` records or IDs.
- `toolRequirements.records` must contain one `required` record for each
  `requiredToolIds` entry and one `missing` record for each `missingToolIds`
  entry. Each record `id` must equal `<target>.<kind>.<name>`, and its
  `evidenceIds` must include
  `target-legalization.v1.<target>.tool-requirement.<status>.<kind>.<name>`.
- `toolRequirements.optionalNativeToolMissing` is true if and only if
  `packageMode` is `source-package` and `toolRequirements.missingToolIds` is
  non-empty.
- `toolRequirements.optionalNativeToolStatus` must be `missing` when
  `packageMode` is `source-package` and `toolRequirements.missingToolIds` is
  non-empty, `available` when `packageMode` is `source-package` and
  `toolRequirements.requiredToolIds` is non-empty while
  `toolRequirements.missingToolIds` is empty, and `not-required` otherwise.
- `toolRequirements.evidenceIds` must include exactly the summary
  `tool-requirements.empty` or `tool-requirements.present` evidence ID implied
  by its required/missing tool lists, each required/missing tool requirement
  evidence ID, and
  `optional-native-tool.missing` when optional native tools are missing.
- Supported modules must not carry missing capabilities or error diagnostics.
- Unsupported modules must carry at least one missing capability and one error
  diagnostic that names the missing capability.
- Nested diagnostic, rewrite, and ABI records must use the same `target`.
- Each diagnostic must cite at least one `diagnostic.*` evidence ID from the
  target legalization namespace, so consumers can distinguish diagnostic
  evidence from broad support, package mode, or ABI evidence.
- Rewrite evidence must match rewrite status; for example, `blocked` rewrites
  must not cite `rewrite.not-required` evidence.
- ABI fact evidence IDs must be present in both `abiFacts.evidenceIds` and the
  top-level `evidenceIds` list.
- `abiFacts.evidenceIds` and `abiFacts.facts[].evidenceIds` must contain only
  `abi.*` evidence IDs for the same target. Support, package-mode, diagnostic,
  rewrite, tool, and resource-binding evidence must stay in their own result
  fields so future reflection/debug consumers do not infer ABI completeness
  from unrelated support evidence.
- `resourceBindingEvidenceIds` must use the same `target` and be present in the
  top-level `evidenceIds` list, so ABI resource evidence cannot be silently
  dropped by result consumers.
- Top-level resource-binding evidence must be exactly the resource-binding
  evidence projected through `resourceBindingEvidenceIds`; v0 consumers must not
  infer a resource ABI state from unprojected top-level evidence alone.
- `resourceBindingEvidenceIds` must include exactly one summary ID:
  `resource-bindings.empty` when there is no detailed `resource-binding.*`
  evidence, or `resource-bindings.present` when detailed resource-binding
  evidence is present.
- `evidenceIds` must include the canonical
  `target-legalization.v1.<target>.decision` ID plus the support evidence
  implied by `supportStatus`, `moduleSupported`, and `packageMode`:
  `state.legalized`, `support.native`, and `package-mode.native` for native support;
  `state.legalized`, `support.source-package`, and
  `package-mode.source-package` for source-package support; or
  `state.rejected`, `support.unsupported`, and `package-mode.unsupported` for
  unsupported results. Support, ABI, package, diagnostic, reflection, and
  debug-metadata consumers must anchor their target decision projections on
  this shared legalization result evidence instead of accepting a partial result
  assembled from nested evidence alone.
- `evidenceIds` must not include any other `state.*`, `support.*`, or
  `package-mode.*` evidence ID for the same target. Contradictory top-level
  support or package-mode evidence is invalid even when the expected evidence
  IDs are also present, so consumers cannot recover an unsafe support/package
  claim from stale positive evidence.
- Supported modules must have `abiFacts.state` of `complete` or `not-required`.
- `abiFacts.state` of `complete` must include at least one fact with a
  non-missing support status.
- Unsupported modules must not claim `abiFacts.state` of `complete`.
- Every evidence ID must use the `target-legalization.v1.<target>.` prefix.
  This is the evidence namespace policy for the v0 report contract and matches
  the existing target/debug/doctor schema semantics and C++ projection evidence.
- `evidenceIds` must include the specific
  `target-legalization.v1.<target>.package-provenance.<packageDecisionProvenance>`
  ID, so source-package results do not rely on stale generic decision evidence
  or target-specific fallback strings.
- `evidenceIds` must not include any other
  `target-legalization.v1.<target>.package-provenance.*` ID; package,
  runtime, and ABI consumers must not be able to infer a different package mode
  from contradictory top-level evidence.

## Consumer Policy

v0 is not a production gate. It exists so future migrations of
`explain-targets`, `doctor --json`, language feature reports, debug metadata,
reflection, package manifests, package verification, package inspection, and
runtime admission can consume one result contract instead of recomputing target
support policy.

Until those consumers migrate, v0 fixtures and checker output are evidence only.
They must not expand support claims, alter target selection, change package
artifact requirements, or replace current diagnostics.
New package/debug consumers must not claim support, native/source package mode,
or target availability from raw backend predicates unless the same claim is
projected from `TargetLegalizationContractProjection` or backed by the top-level
contract evidence IDs described above.

The C++ serializer is also evidence-only. Unit coverage exercises real native,
source-package, and unsupported legalization decisions for `metal`, `vulkan`,
`directx`, and `opengl`, then asserts the emitted JSON carries the v0 envelope,
policy, package mode, provenance, diagnostics, rewrite, ABI, and evidence
fields expected by this contract.

## Consumer Audit Expansion

The v0 result contract must map current consumers that still depend on
predicate-backed, projection-backed, or metadata-backed target decisions. This
table is report-only evidence for migration planning; it does not make the v0
JSON a production source and it does not serialize new fields into existing
consumer schemas.

| Consumer category | Current dependency to audit | v0 result fields/evidence to consume before migration | Boundary/status | References |
| --- | --- | --- | --- | --- |
| `explain-targets` | Projection-backed target records still originate from current `legalizeTargets` decisions and target explanation must not grow a second support policy. | `targetProfile.target`, `supportStatus`, `moduleSupported`, `packageMode`, `requiredCapabilities`, `missingCapabilities`, and `evidenceIds`. | Report-only; consumerMigration stays `pending`; current compiler behavior remains the decision authority; production behavior remains unchanged. | `src/Driver/TargetExplanation.cpp::buildTargetExplanationDocument` `src/Driver/TargetExplanation.cpp::targetRecordFromLegalizationProjection` `src/Driver/TargetExplanation.cpp::targetLegalizationSupportsPackage` `src/Driver/TargetExplanation.cpp::targetLegalizationCoreEvidenceIds` |
| `doctor --json` | Doctor embeds target explanation and should remain an indirect consumer rather than recomputing target support or package mode. | `targetProfile`, `supportStatus`, `moduleSupported`, `packageMode`, `diagnostics`, and `evidenceIds` through the target explanation payload. | Report-only; consumerMigration stays `pending`; current compiler behavior remains the decision authority; production behavior remains unchanged. | `tools/cglc/main.cpp::commandDoctorJson` `tools/cglc/main.cpp::commandDoctor` `tools/cglc/main.cpp::explainTargets` `docs/DOCTOR_JSON_SCHEMA.md::targetExplanation` |
| Package build | Package admission uses current compiler legalization and package build paths, including target-specific artifact emission. | `supportStatus`, `moduleSupported`, `packageMode`, `packageDecisionProvenance`, `toolRequirements`, `diagnostics`, and `evidenceIds` before any build gate can migrate. | Report-only; consumerMigration stays `pending`; current compiler behavior remains the decision authority; production behavior remains unchanged. | `src/Driver/Compiler.cpp::targetLegalizationAdmissionDecision` `src/Driver/Compiler.cpp::requireAdmittedBackendInput` `src/Driver/Compiler.cpp::manifestJson` `src/Driver/Compiler.cpp::finalizePackageBuild` |
| Package inspect/verify | Inspect and verify currently admit packages from recorded manifest metadata, native-binary status, native artifact descriptor health, and legacy compatibility fallbacks. | `packageMode`, `packageDecisionProvenance`, `toolRequirements`, `resourceBindingEvidenceIds`, and `evidenceIds` only after a package schema explicitly records the v0 result. | Report-only; consumerMigration stays `pending`; current compiler behavior remains the decision authority; production behavior remains unchanged. | `src/Driver/PackageIntegrity.cpp::packageArtifactRequirementsForVerification` `src/Driver/PackageIntegrity.cpp::verifyPackageMetadata` `src/Driver/PackageInspect.cpp::packageInspectJson` `src/Driver/PackageInspect.cpp::writePackageArtifactRequirements` `src/Driver/PackageMetadata.cpp::collectPackageNativeArtifactDescriptorHealth` |
| Reflection/debug metadata | Debug metadata consumes legalization projections for summaries and selected-target diagnostics; reflection still owns resource-binding and layout projections. | `targetProfile`, `requiredCapabilities`, `missingCapabilities`, `diagnostics`, `rewrites`, `abiFacts`, `resourceBindingEvidenceIds`, and `evidenceIds`. | Report-only; consumerMigration stays `pending`; current compiler behavior remains the decision authority; production behavior remains unchanged. | `src/Driver/DebugMetadata.cpp::targetCapabilitySummaryFromProjection` `src/Driver/DebugMetadata.cpp::selectedTargetFromProjectionRecords` `src/Driver/DebugMetadata.cpp::buildTargetDecision` `src/Driver/Reflection.cpp::reflectionTargetFeaturesFromLegalization` `src/Driver/Reflection.cpp::reflectionTargetResourceBindingFromLegalization` |
| Runtime admission | Runtime package readers and loaders admit artifacts from manifest metadata, generated package target contracts, and native artifact descriptor evidence, not from serialized v0 results. | `targetProfile`, `packageMode`, `packageDecisionProvenance`, `toolRequirements`, `resourceBindingEvidenceIds`, and `evidenceIds` only after a runtime/package schema owns the serialized result. | Report-only; consumerMigration stays `pending`; current compiler behavior remains the decision authority; production behavior remains unchanged. | `runtime/package_reader.py::read_compatibility_report` `runtime/package_reader.py::select_runtime_artifact` `runtime/package_reader.py::_admission_summary` `runtime/loader.py::runtime_artifact_admission_summary` `runtime/README.md::Current target admission behavior` |

The migration status remains `consumerMigration: "pending"` for all categories
above. A consumer can move from this audit table to a behavior-changing gate
only after the owning schema or runtime/package contract explicitly serializes
the v0 result fields it needs and preserves the top-level evidence IDs as the
decision source.

## Checker

`tools/check_target_legalization_result_contract.py` validates this document,
the JSON Schema in `docs/schemas/target-legalization-result-v0.schema.json`, the
embedded example, the consumer field matrix in
`docs/architecture/TARGET_LEGALIZATION_AUDIT.md`, and the JSON fixtures under
`tests/target-legalization-result-contract`. The checker is deterministic and
offline. It validates each result against the schema first, then applies the
semantic report-only invariants for support state, package mode/provenance,
capability IDs, diagnostics, evidence IDs, ABI placeholders, rewrites, resource
binding evidence, and optional tool requirements.

`tools/check_target_legalization_contract_audit.py` also validates the consumer
audit expansion table above, checks that each category keeps the report-only
`consumerMigration` boundary, verifies the table references, and audits valid
fixtures for exact policy status plus canonical target-scoped evidence IDs.

Required focused validation:

```sh
python3 tools/check_target_legalization_result_contract.py --self-test
python3 tools/check_target_legalization_result_contract.py --root .
```
