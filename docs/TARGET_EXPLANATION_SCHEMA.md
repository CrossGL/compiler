# CrossGL Target Explanation Schema

`cglc explain-targets <input.cgl>` emits the target explanation document. The
same document is embedded as `targetExplanation` in `cglc doctor --json
<input.cgl>`. `cglc build --debug-ir` also writes the same document to the
package manifest artifact `ir/target-explanation.json`.
For generated single-file workflows, `cglc explain-targets <input.cgl>
--logical-input <path>` uses the logical path for input diagnostics before the
target explanation document is produced; successful schema fields are unchanged.

## Compatibility Policy

- `schemaVersion` is required and is currently `1`.
- Consumers should branch on `schemaVersion` before reading nested fields.
- Unknown future versions should be treated as incompatible unless the consumer
  explicitly opts into best-effort feature detection.
- Adding optional target record fields is compatible within schema version 1.
- Removing required fields, changing field types, renaming fields, or changing
  target package decision semantics requires a schema-version bump.
- The compiler emits only the current schema.
- The current machine-readable schema is
  [`docs/schemas/target-explanation-v1.schema.json`](schemas/target-explanation-v1.schema.json).

## Version 1

Top-level fields:

- `schemaVersion`: integer schema version, currently `1`.
- `module`: HIR module name.
- `defaultTarget`: host default target name.
- `buildableTargetCount`: count of target records that can produce a package.
- `recommendedTarget`: recommended target name (`metal`, `vulkan`, `directx`,
  or `opengl`), or `null` when no target can produce a package. This is the
  concrete package target that `cglc build --target auto` selects when a
  buildable recommendation exists.
- `recommendedPackageMode`: package mode for the recommendation, or `null`.
- `targets`: target package decision records.

Each target record contains these required fields:

- `target`: target name.
- `targetBackend`: backend identity for the decision. In v1 this must match
  `target`; it is serialized explicitly so report consumers do not infer the
  backend from array order or evidence ID prefixes.
- `nativeImplemented`: whether a native package emitter exists for the target.
  This is target implementation presence, not a guarantee that the current
  module can be packaged natively.
- `sourcePackageSupported`: whether the source package path supports this
  shader and target. DirectX and OpenGL evaluate backend preflight predicates
  per module, so this is not merely an emitter-availability flag.
- `packageBuildSupported`: whether either native or source package output is
  supported for this shader and target.
- `supportStatus`: normalized target legalization support status. It is
  `native` for native package support, `source-package` for source-package
  support, and `unsupported` for rejected targets.
- `legalizationState`: normalized target legalization state, either
  `legalized` for buildable targets or `rejected` for unsupported targets.
- `packageMode`: `native`, `source-package`, or `unsupported`.
- `packageDecisionProvenance`: normalized target legalization package
  provenance. Native records use `native-package-available`, source-package
  records use `source-package-only`, and unsupported records preserve the
  target legalization rejection provenance.
- `packageDecisionReason`: machine-readable package decision reason.
- `decisionReasonCodes`: deterministic, consumer-facing reason codes derived
  from `packageMode`, `packageDecisionReason`, optional-native-tool fallback
  state, and unsupported missing-capability state.
- `packageRankScore`: lower score means a more preferred package mode. Native
  packages rank `0`, source packages rank `1`, and unsupported targets rank `2`.
- `artifactLinks`: deterministic artifact anchors for this target decision.
  Current v1 records link to `ir/target-explanation.json#targets/<target>`.
- `reportLinks`: deterministic report anchors for this target decision. Current
  v1 records link to `target-explanation-v1#targets/<target>`.
- `remediation`: consumer-readable next step text. Buildable native records
  state that no remediation is required. Source-package fallback records explain
  available source output and name missing native-artifact capabilities when
  applicable. Unsupported records direct consumers to select a buildable target
  or satisfy missing capabilities, and must name each missing capability.
- `legalizationCoreEvidenceIds`: non-empty deterministic evidence IDs for the target
  decision, legalization state, support status, package mode, package
  provenance, optional native-tool status, and package decision reason. The v1
  semantic validator requires the serialized list to match the target
  legalization contract core evidence prefix exactly, so malformed, missing,
  unknown, empty, duplicated, or reordered IDs fail closed. These IDs let tools
  explain why an explicit target was accepted or rejected without replaying
  backend support predicates.
- `requiredCapabilityCount` and `requiredCapabilities`: target capabilities
  required by this shader.
- `missingCapabilityCount` and `missingCapabilities`: required capabilities not
  currently satisfied by the target/package path.

The compiler also emits these optional v1 target fields:

- `diagnosticEvidenceIds`: deterministic diagnostic evidence IDs projected from
  `TargetLegalizationContractProjection::diagnosticEvidenceIds`. Buildable
  records emit an empty list. Unsupported records emit the diagnostic evidence
  used by package and debug consumers for the same target decision. When present,
  semantic validation requires target-scoped `target-legalization.v1.<target>.`
  `diagnostic.*` IDs, rejects duplicates, rejects buildable records with
  diagnostic evidence, and requires unsupported records to preserve at least one
  diagnostic evidence ID.
- `requiredToolCount`, `requiredToolIds`, `missingToolCount`, and
  `missingToolIds`: normalized native toolchain, validation, and native-tool
  requirements projected from
  `TargetLegalizationContractProjection`. Missing tool IDs are always a subset
  of required tool IDs. Native Metal/Vulkan packages include their package
  toolchain requirements, while DirectX/OpenGL source-package records preserve
  missing optional native tool IDs without rejecting the source package path.
- `optionalNativeToolMissing` and `optionalNativeToolStatus`: normalized
  optional native-tool state. Source-package records with missing tool IDs use
  `optionalNativeToolMissing: true` and `optionalNativeToolStatus: "missing"`;
  source-package records with required but satisfied tool IDs use `"available"`;
  non-source-package records use `"not-required"`.
- `toolRequirementEvidenceIds`: deterministic target legalization evidence IDs
  for the tool requirement summary and each required or missing tool ID. The
  summary ID is `tool-requirements.present` when either tool list is non-empty
  and `tool-requirements.empty` otherwise.

Target records are projected from the v0 `TargetLegalizationContract` view of
`TargetLegalizationResult`. That contract normalizes requested/resolved target,
support status, legalization state, package mode, missing capability IDs,
reason text, diagnostics, rewrite provenance, package-decision provenance,
optional native-tool state, and evidence IDs before `explain-targets` or
package builds decide that a target is supported. The v1 JSON record serializes
the normalized `supportStatus`, `legalizationState`,
`packageDecisionProvenance`, stable core evidence prefix, and, when emitted by
the compiler, the projection diagnostic and tool requirement evidence lists.
Consumers should treat `packageBuildSupported: true` as a legalization success
claim, not as raw backend availability. Unsupported legalization results always
report `supportStatus: "unsupported"`, `legalizationState: "rejected"`, and
`packageMode: "unsupported"` and are excluded from recommendations even if the
target has a native emitter.

`tools/validate_json_schema.py` performs semantic validation that JSON Schema
cannot express directly: capability counts match array lengths, missing
capabilities are a subset of required capabilities, capability IDs belong to
their target prefix, target records are unique, target/backend identity matches,
decision reason codes, artifact anchors, report anchors, and remediation text
agree with the serialized decision, package mode/reason/rank fields agree with
module-specific package support, diagnostic evidence IDs are target-scoped and
consistent with buildable versus unsupported support state when present, tool
requirement fields are emitted as an all-or-none group, tool counts match tool
ID arrays, missing tool IDs are required tool IDs, optional native-tool status
matches package mode and missing tool IDs, `toolRequirementEvidenceIds` match
the normalized tool summary and per-tool evidence IDs, `buildableTargetCount`
matches buildable target records, and the recommended target is the lowest-rank
buildable target with the default target used as the tie-breaker when it is also
buildable at that rank. This mirrors auto build selection: the host default is
preferred only for a best-rank tie, otherwise the best ranked buildable target
is recommended. If no target is buildable, `recommendedTarget` and
`recommendedPackageMode` are `null`; `cglc build --target auto` may still keep
the host default selected to produce concrete unsupported-target diagnostics.

The semantic validator also checks that a buildable target has internally
consistent package-mode evidence. Native package records must require and
satisfy their native backend marker (`metal.backend.native-metal-package` or
`vulkan.backend.vulkan-prototype-package`) and must not report any missing
capabilities. Source-package records must require and satisfy their source
backend marker (`directx.backend.hlsl-lowering` or
`opengl.backend.glsl-lowering`). Source-package records may still report
planned native artifact capabilities such as `directx.backend.native-dxil-package`
or `opengl.backend.native-glsl-package` as missing because those do not block
the source-package path. Buildable source-package records may only report
missing capabilities from that optional native evidence set; any other missing
required capability contradicts the successful package legalization state and
must instead be represented as an unsupported record with rejected core
legalization evidence. Unsupported records must include at least one missing
capability so consumers have a concrete blocker for the rejection.

Native Metal/Vulkan records and DirectX/OpenGL source-package records are
predicate-gated. A target may have an emitter in the compiler while reporting
`packageBuildSupported: false`, `packageMode: "unsupported"`,
`packageDecisionReason: "unsupported"`, and `packageRankScore: 2` when backend
support predicates already know this module cannot be packaged for that
backend. DirectX/OpenGL source-package rejections also report
`sourcePackageSupported: false` and include a backend marker such as
`directx.backend.hlsl-lowering` or `opengl.backend.glsl-lowering`, plus
predicate diagnostic capabilities when available. Such records are not
considered for `recommendedTarget`. Accepted DirectX/OpenGL modules report
`sourcePackageSupported: true`, `packageBuildSupported: true`, and
`packageMode: "source-package"`.

Backend support predicates are allowed to become more precise without changing
this schema version because capability identifiers remain open-ended strings.
Current post-batch-19 predicate evidence is summarized in
[`docs/SUPPORT_MATRIX_EVIDENCE.md`](SUPPORT_MATRIX_EVIDENCE.md), including
DirectX one-unbounded-descriptor-array source packages, OpenGL read-only fixed
struct-element helper arrays, Metal folded-zero runtime-tail singleton storage
buffers, Vulkan fixed uniform-buffer descriptor arrays and local-zero
runtime-tail singleton access, and compiler-local `while` HIR support.
