# CrossGL Package Manifest Schema

Every successful `cglc build` writes `manifest.json` in the generated `.cglb`
directory package after the native package verifier accepts the generated root
files, artifact paths, source hash, and debug IR artifact pair. The manifest
records compiler identity, module/target identity, source hash, and package
artifact paths. Build output is first emitted into a sibling staging directory;
the requested output path is replaced only after package finalization succeeds.

## Compatibility Policy

- `schemaVersion` is required and is currently `1`.
- Consumers should branch on `schemaVersion` before reading nested fields.
- Unknown future versions should be treated as incompatible unless the consumer
  explicitly opts into best-effort feature detection.
- Adding optional artifact fields is compatible within schema version 1.
- Removing required fields, changing field types, renaming fields, or changing
  existing artifact semantics requires a schema-version bump.
- The compiler emits only the current schema.
- The current machine-readable schema is
  [`docs/schemas/manifest-v1.schema.json`](schemas/manifest-v1.schema.json).

## M1 v0 Stability Boundary

The M1 v0 manifest boundary is the `schemaVersion: 1` package manifest shape.
Unknown future versions should fail closed for consumers that have not adopted
the newer schema. Within v1, the top-level field names, object types,
`sourceHash` shape, package-relative artifact path rules, and target names are
stable.

Target package mode is not a hand-maintained manifest rule. It is generated from
`tools/package_target_contracts.json`, emitted into
`include/crossgl/Driver/PackageTargetContracts.h`, and checked by
`tools/check_package_target_contracts.py`. Changing a target from native to
source-package mode, changing required manifest artifacts, or changing
`nativeBinaryStatus` placement must update that generated contract and its
freshness checks in the same change.

Adding a new public artifact key within manifest v1 requires updating the
machine-readable manifest schema, semantic validator, package integrity/verify
fixtures, and the JSON schema index together. Older validators using the frozen
v1 schema are expected to reject unknown artifact keys.

## Version 1

Top-level fields:

- `schemaVersion`: integer schema version, currently `1`.
- `compiler`: compiler identity and build dependency version metadata.
- `module`: HIR module name.
- `target`: package target name.
- `sourceHash`: source hash object.
- `packageArtifactRequirements`: optional recorded target package artifact
  contract.
- `targetLegalizationToolRequirements`: optional recorded target legalization
  tool requirement evidence.
- `artifacts`: package artifact path map.

The `compiler` object contains:

- `name`: currently `CrossGL-Compiler`.
- `version`: compiler version string.
- `llvmVersion`: LLVM version used by the compiler build.

The `sourceHash` object contains:

- `algorithm`: currently `sha256`.
- `value`: source hash value. Semantic validation requires a 64-character
  lowercase hexadecimal SHA-256 value.

`sourceHash.value` is computed over the compiler input `.cgl` text. When a
translator or orchestrator generated that `.cgl` from another source language,
the manifest still records the generated compiler-input hash, not the original
source file hash. When `build --debug-ir --source-remap` receives a file-backed
remap sidecar, manifest v1 may additionally declare `artifacts.sourceRemap`,
which points to source-remap provenance for the sidecar that supplied
`originalLocation` records. This provenance does not change `sourceHash`.

Package manifests remain single-input in v1. Repository-scale source manifests,
per-input result arrays, and target matrices are outside the package manifest
contract until a dedicated batch schema is defined.

Known `artifacts` fields:

- `backendSource`: package-relative generated Metal/HLSL/GLSL source path.
- `backendAssembly`: package-relative generated SPIR-V assembly path for Vulkan
  packages.
- `intermediate`: package-relative intermediate artifact path, such as Metal
  AIR.
- `nativeBinary`: package-relative native binary path or planned native binary
  path.
- `nativeProfile`: optional package-relative Vulkan profile/debug evidence
  sidecar path.
- `nativeArtifactDescriptor`: optional package-relative
  `native-artifact-v0` descriptor sidecar path consumed by package inspect,
  verify, runtime readers, and release tooling. This manifest value is the
  canonical descriptor location; compiler-built packages currently use
  `backend/<target>/<module>.native-artifact.json`, and
  `metadata/native-artifact.json` is only a conventional fixture/example path.
- `nativeBinaryStatus`: `planned`, `emitted`, or `validated` for source-package
  targets that may produce optional native binaries.
- `sourceRemap`: optional package-relative
  `source-remap-provenance-v1` sidecar path emitted for debug packages built
  with a file-backed `--source-remap` sidecar.
- `debugMetadata`: optional package-relative `--debug-ir` metadata path.
- `hirSourceMap`: optional package-relative `--debug-ir` HIR source-map path.
- `targetExplanation`: optional package-relative `--debug-ir`
  `target-explanation-v1` sidecar path.

`--debug-ir` packages also include non-manifest sidecars for humans and debug
tools: `ir/hir.txt`, `ir/crossgl.mlir`, `ir/pseudo-mlir.mlir`, the legacy
`ir/mlir.mlir` alias, and `ir/hir-pass-trace.json`. The `targetExplanation`
manifest artifact uses the same document shape as `cglc explain-targets
<input.cgl>` and is written to `ir/target-explanation.json`. The pass trace
sidecar uses
the same JSON format as `cglc dump-ir --stage hir-pass-trace` and records the
package build pipeline, including backend-input validation. It is intentionally
not listed in `manifest.artifacts`; adding it as a public artifact key would
require the artifact schema and validator update described above.
Both pseudo-MLIR files are labeled as textual HIR projections, not registered
MLIR dialect output. The real `mlir` package surface remains reserved for a
future `CROSSGL_ENABLE_MLIR_EXPERIMENTAL` path.

Target-specific tests and generated contract checks pin which artifact fields
are required for each package mode. Semantic validation also checks the current
target package contracts:

- Metal packages include `backendSource`, `intermediate`, and `nativeBinary`.
- Vulkan packages include `backendAssembly` and `nativeBinary`; generated
  prototype packages also include `nativeProfile`.
- Only Vulkan packages may include `nativeProfile`; loaders must treat the
  sidecar as Vulkan/SPIR-V evidence, not as a generic native profile.
- Metal and Vulkan packages must not include `nativeBinaryStatus`.
- DirectX and OpenGL source packages include `backendSource`, `nativeBinary`,
  and `nativeBinaryStatus`.
- `packageArtifactRequirements.evidenceIds`, when present, records the
  aggregate target-legalization evidence IDs for the package artifact
  requirement contract. New compiler-built packages emit it so package
  inspect/verify can report requirement evidence without debug sidecars; older
  manifests that omit it remain valid.
- `targetLegalizationToolRequirements`, when present, records the selected
  target's package mode, required and missing native-tool IDs, normalized
  optional-native-tool status, and the target-legalization evidence IDs that
  produced those values. This object is report-only package evidence. Package
  admission is still decided by target legalization before manifest emission,
  and source-package targets remain valid when optional native tools are missing
  and the recorded package artifact requirements are satisfied.
- Target explanation, doctor, and debug metadata records can still report
  predicate-rejected native Metal/Vulkan or DirectX/OpenGL source-package
  targets with `packageBuildSupported: false`; successful manifests are emitted
  only for supported package decisions. Supported Metal and Vulkan manifests
  remain native-only and omit `nativeBinaryStatus`; supported DirectX and
  OpenGL manifests remain source-package manifests and include
  `nativeBinaryStatus`.
- Duplicate JSON object keys are rejected during package metadata loading so
  tools do not depend on parser-specific first-key or last-key behavior.
- Artifact paths are non-empty, package-relative, stay inside the package, and
  use `/` separators for stable cross-platform JSON.
- Artifact path values are unique across manifest artifact keys, so each key is
  auditable as separate package evidence.
- `debugMetadata` and `hirSourceMap` are emitted as a pair when `--debug-ir` is
  enabled.
- `targetExplanation` is emitted when `--debug-ir` is enabled and uses the
  target-explanation v1 schema.

## Package Integrity Validation

`tools/validate_package_integrity.py` validates an emitted `.cglb` directory
against its root metadata. It requires the package root to contain
`manifest.json`, `reflection.json`, and `diagnostics.json`; verifies manifest
artifact paths are non-empty package-relative paths with `/` separators that
stay inside the package; and requires every artifact path to resolve to a
regular file, with separate diagnostics for missing paths and paths that resolve
to directories or other non-file entries. When manifest schema validation is
enabled, the schema semantic checker also rejects duplicate manifest artifact
path values before artifact evidence is accepted as distinct.

`artifacts.nativeBinary` may be absent only for DirectX and OpenGL source
packages when `nativeBinaryStatus` is `planned`. When the status is `emitted` or
`validated`, the native binary path must exist. `debugMetadata` and
`hirSourceMap` must be present as a pair. Non-empty `reflection.nativeBinary`
values must also be package-relative paths with `/` separators that stay inside
the package before they can be compared with `artifacts.nativeBinary`. The
validator can also check the manifest, reflection, diagnostics, debug metadata,
and HIR source-map schemas; compare `reflection.nativeBinary` with
`artifacts.nativeBinary`; and compare `sourceHash.value` with the original
source file.

Pass `--schema-root docs/schemas` to load the current default manifest,
reflection, diagnostics, debug metadata, HIR source-map, target-explanation,
and Vulkan native-profile schemas in one option. Explicit schema options such
as `--manifest-schema` override the schema-root default for that schema. Pass
`--package-verifier build/cglc` to
delegate root file, artifact, debug-artifact pairing, reflection/native binary
consistency, source-hash record validation, and optional source-content hash
comparison to
`cglc package verify --source <input.cgl> --json` while the Python validator
continues to run schema checks.
