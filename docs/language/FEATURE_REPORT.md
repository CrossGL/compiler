# CrossGL Language Feature Report Plan

This is a report-only planning contract for the language/version feature report
that Milestone 9 expects the compiler to emit for each module. It defines the
shape and evidence rules for that future report; it does not authorize parser,
native backend, package build, or CrossTL behavior changes.
Compiler emission is future work for package artifacts and broad frontend
redesign. The focused `cglc language-feature-report <input.cgl>` command now
emits this v1 report for a parsed source module.

<!-- crossgl-language-feature-report-plan-v1:begin -->
```json
{
  "compatibility_buckets": [
    "cross-tl-inventory-only",
    "accepted-source",
    "package-supported",
    "compatibility-only",
    "spec.unsupported-for-native-v0",
    "spec.deprecated",
    "spec.error",
    "target.unsupported"
  ],
  "evidence_id_namespaces": [
    "spec-index",
    "compatibility",
    "contract",
    "support-matrix",
    "conformance",
    "ctest",
    "fixture",
    "diagnostic",
    "reflection",
    "target-contract"
  ],
  "fact_severities": [
    "unsupported",
    "deprecated",
    "error"
  ],
  "report_kind": "crossgl-language-feature-report-plan",
  "required_report_fields": [
    "schemaVersion",
    "kind",
    "module",
    "language",
    "crossTLSnapshotSeal",
    "compatibilityBucketSummary",
    "targetFeatureGates",
    "resourceMemoryLayoutFeatures",
    "facts",
    "evidence",
    "generation"
  ],
  "required_sections": [
    "Scope",
    "Report Contract",
    "Language And Snapshot Seal",
    "Compatibility Bucket Summary",
    "Target Feature Gates",
    "Resource Memory Layout Features",
    "Unsupported Deprecated Error Facts",
    "Evidence IDs",
    "Emission Rules"
  ],
  "schema": 1,
  "source_seal": {
    "compatibility_path": "docs/language/COMPATIBILITY.md",
    "contract_manifest_path": "tools/cross_repo_language_contract.json",
    "snapshot_path": "docs/language/crosstl-frontend-language-spec-v0.json",
    "snapshot_schema_version": 0,
    "snapshot_sha256": "86b133c7da54ac206972d452a9a48419dccb00420875e06cc1a51cbbb0109d35",
    "support_contract_path": "docs/language/V0_SUPPORT.md"
  }
}
```
<!-- crossgl-language-feature-report-plan-v1:end -->

## Scope

The feature report is a deterministic module summary emitted after the frontend
has enough information to classify source forms against the v0 language/support
contract. The report is descriptive: it must not make a module buildable, change
diagnostics, or relax target legality rules by itself.

The current report surface is intentionally narrow:
`cglc language-feature-report <input.cgl> [--root <repo>]`. It reads an existing
source module through the parser/HIR path and emits only the v1 JSON contract
documented here.

## Report Contract

The report is a JSON object with stable key ordering in the emitted artifact.
The canonical valid fixture is
[`tests/language-feature-report/canonical.json`](../../tests/language-feature-report/canonical.json).
It is a hand-maintained schema fixture, not compiler output. The canonical
`module.sourceSha256` value is the SHA-256 of `module.sourcePath` after reading
the file as UTF-8 text and normalizing CRLF/CR line endings to LF. The canonical
shape is:

```json
{
  "schemaVersion": 1,
  "kind": "crossgl.languageFeatureReport",
  "module": {
    "moduleId": "ResourceShader",
    "sourcePath": "tests/fixtures/ResourceShader.cgl",
    "sourceSha256": "9213f2331dec7747d0e4bea92b083bb3bd9c4e30238d59b943fe49f33b525038",
    "stageEntryPoints": [
      {
        "stage": "compute",
        "entryPoint": "main"
      }
    ]
  },
  "language": {
    "family": "CrossGL",
    "version": "v0",
    "nativeProfile": "native-v0",
    "compatibilityContract": "docs/language/V0_SUPPORT.md"
  },
  "crossTLSnapshotSeal": {
    "snapshotId": "crosstl-frontend-language-spec-v0",
    "snapshotPath": "docs/language/crosstl-frontend-language-spec-v0.json",
    "snapshotSha256": "86b133c7da54ac206972d452a9a48419dccb00420875e06cc1a51cbbb0109d35",
    "snapshotSchemaVersion": 0
  },
  "compatibilityBucketSummary": {
    "cross-tl-inventory-only": 15,
    "accepted-source": 1,
    "package-supported": 2,
    "compatibility-only": 0,
    "spec.unsupported-for-native-v0": 1,
    "spec.deprecated": 1,
    "spec.error": 1,
    "target.unsupported": 0
  },
  "targetFeatureGates": [
    {
      "target": "vulkan",
      "targetVersion": "v0",
      "packageMode": "native",
      "gateId": "target.resource-arrays",
      "featureFamily": "resources",
      "status": "planned-failure",
      "requiredCapabilities": [
        "descriptor-array"
      ],
      "diagnosticCodes": [],
      "evidenceIds": [
        "compatibility:target.resource-arrays",
        "target-contract:vulkan.package-mode.native",
        "target-contract:vulkan.package-support",
        "target-contract:vulkan.support.unsupported"
      ]
    }
  ],
  "resourceMemoryLayoutFeatures": {
    "resources": [
      {
        "featureId": "resource.storage-buffer",
        "status": "package-supported",
        "sourceLocations": [],
        "evidenceIds": [
          "fixture:tests/fixtures/ResourceShader.cgl"
        ]
      },
      {
        "featureId": "resource.storage-image-types",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:grammar.resources"
        ]
      },
      {
        "featureId": "resource.buffer-types",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:grammar.resources"
        ]
      },
      {
        "featureId": "resource.uav-buffer-types",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:grammar.resources"
        ]
      },
      {
        "featureId": "resource.sampler-state-types",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:grammar.resources"
        ]
      },
      {
        "featureId": "resource.access-metadata",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:grammar.resources"
        ]
      },
      {
        "featureId": "resource.descriptor-index-metadata",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:grammar.resources"
        ]
      },
      {
        "featureId": "resource.image-format-metadata",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:grammar.resources"
        ]
      }
    ],
    "memory": [
      {
        "featureId": "memory.workgroup-shared",
        "status": "package-supported",
        "sourceLocations": [],
        "evidenceIds": [
          "support-matrix:cglc_build_vulkan_resource_shader_workgroup_shared_native"
        ]
      },
      {
        "featureId": "memory.address-spaces",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:grammar.resources",
          "spec-index:semantics.metadata-and-layout"
        ]
      },
      {
        "featureId": "memory.layout-metadata",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:grammar.resources",
          "spec-index:semantics.metadata-and-layout"
        ]
      }
    ],
    "layout": [
      {
        "featureId": "layout.set-binding",
        "status": "accepted-source",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:semantics.metadata-and-layout"
        ]
      },
      {
        "featureId": "layout.builtin-semantics",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:semantics.metadata-and-layout"
        ]
      },
      {
        "featureId": "layout.metadata-single-values",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:semantics.metadata-and-layout"
        ]
      },
      {
        "featureId": "layout.metadata-aliases",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:semantics.metadata-and-layout"
        ]
      },
      {
        "featureId": "layout.metadata-multi-values",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:semantics.metadata-and-layout"
        ]
      },
      {
        "featureId": "layout.interpolation-metadata",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:semantics.metadata-and-layout"
        ]
      },
      {
        "featureId": "layout.stage-layout-entries",
        "status": "cross-tl-inventory-only",
        "sourceLocations": [],
        "evidenceIds": [
          "spec-index:semantics.metadata-and-layout"
        ]
      }
    ]
  },
  "facts": {
    "unsupported": [
      {
        "factId": "resource.var-address-space",
        "classification": "spec.unsupported-for-native-v0",
        "message": "Only workgroup/shared var address spaces are native-v0 source forms.",
        "evidenceIds": [
          "compatibility:resource.var-address-space",
          "diagnostic:parse.unsupported-var-address-space"
        ]
      }
    ],
    "deprecated": [
      {
        "factId": "stage.kernel-alias",
        "classification": "spec.deprecated",
        "message": "Use compute stage blocks instead of kernel aliases.",
        "evidenceIds": [
          "compatibility:stage.kernel-alias"
        ]
      }
    ],
    "error": [
      {
        "factId": "sema.no-stage-or-entry",
        "classification": "spec.error",
        "message": "A shared module must contain a supported stage and entry function.",
        "evidenceIds": [
          "compatibility:sema.no-stage-or-entry"
        ]
      }
    ]
  },
  "evidence": [
    {
      "id": "spec-index:semantics.metadata-and-layout",
      "kind": "spec-index",
      "path": "docs/language/SPEC_INDEX.md",
      "anchor": "semantics.metadata-and-layout"
    },
    {
      "id": "spec-index:grammar.resources",
      "kind": "spec-index",
      "path": "docs/language/SPEC_INDEX.md",
      "anchor": "grammar.resources"
    },
    {
      "id": "compatibility:target.resource-arrays",
      "kind": "compatibility",
      "path": "docs/language/COMPATIBILITY.md",
      "anchor": "target.resource-arrays"
    },
    {
      "id": "target-contract:vulkan.package-support",
      "kind": "target-contract",
      "path": "docs/TARGET_CAPABILITY_REGISTRY.md",
      "anchor": "vulkan"
    },
    {
      "id": "target-contract:vulkan.package-mode.native",
      "kind": "target-contract",
      "path": "docs/TARGET_CAPABILITY_REGISTRY.md",
      "anchor": "vulkan"
    },
    {
      "id": "target-contract:vulkan.support.unsupported",
      "kind": "target-contract",
      "path": "docs/TARGET_CAPABILITY_REGISTRY.md",
      "anchor": "vulkan"
    },
    {
      "id": "fixture:tests/fixtures/ResourceShader.cgl",
      "kind": "fixture",
      "path": "tests/fixtures/ResourceShader.cgl"
    },
    {
      "id": "support-matrix:cglc_build_vulkan_resource_shader_workgroup_shared_native",
      "kind": "support-matrix",
      "path": "docs/SUPPORT_MATRIX_EVIDENCE.md",
      "ctestName": "cglc_build_vulkan_resource_shader_workgroup_shared_native"
    },
    {
      "id": "compatibility:resource.var-address-space",
      "kind": "compatibility",
      "path": "docs/language/COMPATIBILITY.md",
      "anchor": "resource.var-address-space"
    },
    {
      "id": "diagnostic:parse.unsupported-var-address-space",
      "kind": "diagnostic",
      "path": "docs/language/COMPATIBILITY.md",
      "diagnosticCode": "parse.unsupported-var-address-space"
    },
    {
      "id": "compatibility:stage.kernel-alias",
      "kind": "compatibility",
      "path": "docs/language/COMPATIBILITY.md",
      "anchor": "stage.kernel-alias"
    },
    {
      "id": "compatibility:sema.no-stage-or-entry",
      "kind": "compatibility",
      "path": "docs/language/COMPATIBILITY.md",
      "anchor": "sema.no-stage-or-entry"
    }
  ],
  "generation": {
    "tool": "schema-fixture",
    "mode": "report-only",
    "command": [
      "not-emitted-by-cglc"
    ]
  }
}
```
Validate the committed fixture with:

```sh
python tools/validate_json_schema.py \
  --schema docs/schemas/language-feature-report-v1.schema.json \
  --instance tests/language-feature-report/canonical.json
python tools/check_language_feature_report_plan.py --root .
```

Emit and validate a compiler-generated module report with:

```sh
cglc language-feature-report tests/fixtures/ResourceShader.cgl \
  > /tmp/resource-language-feature-report.json
python tools/validate_json_schema.py \
  --schema docs/schemas/language-feature-report-v1.schema.json \
  --instance /tmp/resource-language-feature-report.json
```

Unknown fields should be rejected until the schema is intentionally extended.
Empty arrays are valid when the module has no facts in that family, but every
reported feature, gate, or fact must cite at least one `evidenceIds` entry.
For report examples, `module.sourceSha256` is line-ending independent: hash the
normalized UTF-8 source text, not platform checkout bytes.
The v1 machine-readable schema is
[`docs/schemas/language-feature-report-v1.schema.json`](../schemas/language-feature-report-v1.schema.json),
with schema policy summarized in
[`docs/LANGUAGE_FEATURE_REPORT_SCHEMA.md`](../LANGUAGE_FEATURE_REPORT_SCHEMA.md).

## Language And Snapshot Seal

The report must name the CrossGL language family and the compiler-native profile
separately: `language.version` is the shared language claim, while
`language.nativeProfile` is the compiler support layer. For Milestone 9 the
initial values are `v0` and `native-v0`.

`crossTLSnapshotSeal` must mirror the committed CrossTL snapshot:
`docs/language/crosstl-frontend-language-spec-v0.json`, its SHA-256 over
normalized UTF-8 text, and the snapshot schema version. A future implementation
may also include the CrossTL source-file hashes from the cross-repo contract
report, but the module report must at minimum make the language inventory seal
visible.
Spec-index evidence tied only to this snapshot is CrossTL translator inventory
coverage. It must not be interpreted as native compiler accepted-source
coverage without separate compiler fixture/HIR evidence.

## Compatibility Bucket Summary

`compatibilityBucketSummary` gives one module-level count per bucket. The
required buckets are:

| Bucket | Meaning |
| --- | --- |
| `cross-tl-inventory-only` | The shared CrossTL-derived language/spec inventory exposes the form, but this row is not a native compiler accepted-source claim. |
| `accepted-source` | The native compiler frontend accepts the source form for the module under the shared v0 language contract. |
| `package-supported` | Package evidence names the target/form combination. |
| `compatibility-only` | The form exists for compatibility or HIR preservation but is not a package claim. |
| `spec.unsupported-for-native-v0` | CrossTL exposes the form, but native-v0 does not support it. |
| `spec.deprecated` | The source form is accepted only as a legacy compatibility spelling. |
| `spec.error` | The source form is invalid shared CrossGL and should reject before target emission. |
| `target.unsupported` | The frontend accepts the form, but one or more targets cannot emit it. |

Counts should be derived from normalized facts, not from rendered prose. If a
fact affects more than one target, count the language bucket once and record
target-specific rows under `targetFeatureGates`.

For the v1 schema validation slice, bucket counts are checked against the
reported `resourceMemoryLayoutFeatures.*[].status` entries plus
`facts.*[].classification` entries. `targetFeatureGates` are evidence-checked
target details and do not add additional module bucket count entries unless the
same limitation is also represented by a fact.

## Target Feature Gates

`targetFeatureGates` records target/version-specific decisions that can differ
from the shared source bucket. Each gate should include:

- `target`: normalized target id such as `directx`, `metal`, `opengl`, or
  `vulkan`.
- `targetVersion`: the target contract version used for the decision.
- `packageMode`: the public report spelling projected from the target
  legalization package mode (`source-package` becomes `source`, `native`
  stays `native`, and `unsupported` becomes `unavailable`).
- `gateId`: a stable compatibility or target-contract id.
- `featureFamily`: one of `language`, `resources`, `memory`, `layout`,
  `intrinsics`, or `package`.
- `status`: `supported`, `unsupported`, `planned-failure`, `deprecated`, or
  `unavailable`.
- `requiredCapabilities`, `diagnosticCodes`, and `evidenceIds`.

Unsupported, unavailable, and planned-failure gates must carry at least one
required or missing legalization capability. Every target gate must include
corresponding `target-contract:<target>.package-support`,
`target-contract:<target>.package-mode.<mode>`, and
`target-contract:<target>.support.<status>` evidence IDs so report consumers can
trace the row back to target legalization instead of a separate support policy.

This gate list must report target limitations; it must not replace existing
target diagnostics or package legality checks.

## Resource Memory Layout Features

`resourceMemoryLayoutFeatures` groups feature facts that are easy to lose in a
flat unsupported list:

| Group | Examples |
| --- | --- |
| `resources` | cbuffers, storage buffers, storage images, textures, samplers, descriptor arrays, comparison samplers, and nonuniform descriptor index forms. |
| `memory` | workgroup/shared memory, barriers, atomics, image atomics, and read/write access restrictions. |
| `layout` | `layout(set = N, binding = M)`, image formats, local sizes, address spaces, register/group aliases, and builtin semantic metadata. |

Every entry should include `featureId`, `status`, `sourceLocations`, and
`evidenceIds`. Source locations may be empty for aggregate module facts, but
the field must always be present so downstream report consumers do not infer a
missing location from an omitted key.

Schema semantics derive required aggregate `featureId` rows from populated
resource, memory, and layout facets in the committed CrossTL frontend snapshot.
Those aggregate rows use `cross-tl-inventory-only` unless separate compiler
fixture/HIR evidence promotes an actual source form to `accepted-source` or
`package-supported`. If CrossTL adds a new snapshotted facet in those surfaces,
reports must add a matching inventory row instead of relying only on prose or
source seals.

When a contributing feature has a real compiler span, the CLI emits it in
`sourceLocations` using the v1 source-location object. Resource and
workgroup/shared-memory records use HIR type spans, expression-derived records
such as barriers, atomics, and nonuniform descriptor indexes use HIR expression
spans, and layout metadata uses existing parser layout spans where HIR currently
keeps only resolved values or boolean flags. Location files are normalized to
`module.sourcePath`, ordered by source position, and deduplicated.

Inventory-only rows must keep `sourceLocations` empty. Non-empty
`sourceLocations` require native compiler span evidence, normally a
`support-matrix`, `ctest`, or `conformance` evidence record that names HIR
source-map provenance from the compiler. CrossTL AST `source_location`
inventory cannot populate feature-report spans, and spec-index, compatibility,
contract, fixture, reflection, or target-contract evidence alone is not enough
to justify a concrete report location.

## Unsupported Deprecated Error Facts

The `facts` object is split into `unsupported`, `deprecated`, and `error` so
clients can display status without interpreting free-form messages. Each fact
must include:

- `factId`: stable id, preferably from `docs/language/COMPATIBILITY.md`.
- `classification`: one of `spec.unsupported-for-native-v0`,
  `spec.deprecated`, `spec.error`, or `target.unsupported`.
- `message`: short human-readable summary.
- `evidenceIds`: non-empty references proving why the fact was reported.

Unsupported facts are not diagnostics by themselves. If a fact corresponds to a
current diagnostic, cite the diagnostic code as evidence and let the diagnostic
pipeline keep owning behavior.

## Evidence IDs

Evidence IDs are strings with a required namespace prefix and a stable suffix:
`namespace:suffix`. Required namespaces are `spec-index`, `compatibility`,
`contract`, `support-matrix`, `conformance`, `ctest`, `fixture`, `diagnostic`,
`reflection`, and `target-contract`.

An evidence record should include `id`, `kind`, and the most specific local
pointer available: `path`, `anchor`, `ctestName`, `fixture`, `diagnosticCode`,
or `schemaPath`. Report consumers should treat unresolved evidence IDs as report
quality failures, not compiler feature support.

For committed examples, local pointers must resolve against the repository:
`path` must exist, `anchor` and `diagnosticCode` must appear in that file, and
`ctestName` must appear both in the evidence file and in CTest registration.
When a pointer field is the canonical evidence suffix for its namespace
(`spec-index`/`compatibility` anchors, `ctestName`, or `diagnosticCode`), the
`id` suffix must match the pointer value.

## Emission Rules

Future implementation work should follow these rules:

1. Build the report from existing parser/HIR/package facts. Do not change
   accepted syntax, recovery, diagnostics, native target behavior, or package
   build semantics to make the report easier to emit.
2. Emit deterministic JSON: stable key order, stable array ordering, normalized
   POSIX paths, normalized source hashes, and explicit empty arrays.
3. Keep language/spec inventory, CrossTL translator coverage, native compiler
   accepted-source evidence, and target gates separate. A feature can be native
   accepted source and still have one or more `target.unsupported` gates.
4. Cite evidence IDs for every feature, gate, and unsupported/deprecated/error
   fact. Missing evidence should fail the report-generation test.
5. Extend this planning contract before adding new report fields or bucket
   names.
