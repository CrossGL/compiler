# Native Binary Backend Contract

This document is an engineering contract for backend package claims. It is
grounded in the current `cglc` CLI, backend emitters, package verifier, and
schema contracts. It is not a support matrix and it does not promote a target
from source-package status to native status.

## Grounding Map

- CLI surface: `tools/cglc/main.cpp`.
- Build orchestration, staging, manifest emission, and package verification:
  `src/Driver/Compiler.cpp`.
- Package target contract source:
  `tools/package_target_contracts.json`, generated into
  `include/crossgl/Driver/PackageTargetContracts.h` and documented in
  `docs/package-targets.md`.
- Package schemas and semantic policy:
  `docs/MANIFEST_JSON_SCHEMA.md`, `docs/PACKAGE_INSPECT_SCHEMA.md`,
  `docs/PACKAGE_VERIFY_SCHEMA.md`, and `docs/schemas/*.schema.json`.
- Target decision JSON:
  `docs/TARGET_EXPLANATION_SCHEMA.md`,
  `docs/DOCTOR_JSON_SCHEMA.md`, and
  `src/Backend/TargetCapabilities.cpp`.
- Toolchain detection: `src/Backend/Toolchain.cpp` and
  `tests/cmake/CrossGLOptionalNativeTools.cmake`.
- Target emitters:
  `src/Backend/MetalBackend.cpp`, `src/Backend/VulkanBackend.cpp`,
  `src/Backend/DirectXBackend.cpp`, and `src/Backend/OpenGLBackend.cpp`.

## CLI Contract

The package-producing entry point is:

```sh
build/cglc build <input.cgl> --target auto|metal|vulkan|directx|opengl \
  --output <out.cglb> [--debug-ir] [--diagnostics-json]
```

`--target auto` uses the same package decision model exposed by:

```sh
build/cglc explain-targets <input.cgl>
build/cglc doctor --json <input.cgl>
```

Successful `cglc build` writes into a sibling staging directory, emits package
metadata, runs compiler-native package verification, and promotes the staging
directory only after finalization succeeds. Package consumers must validate
with:

```sh
build/cglc package inspect <out.cglb> --json
build/cglc package verify <out.cglb> --source <input.cgl> --json
```

`dump-ir --stage backend --target <target>` is useful evidence for generated
source or assembly shape, but it is not package evidence. A backend claim
requires a verified `.cglb`.

## Shared Package Constraints

Every successful package root contains:

- `manifest.json`
- `reflection.json`
- `diagnostics.json`

When `--debug-ir` is present, `ir/debug-metadata.json`,
`ir/hir-source-map.json`, and `ir/target-explanation.json` are emitted. The
verifier rejects partial debug metadata/source-map pairs and checks the target
explanation as a normal manifest artifact; schema-root validation can validate
the sidecar against `target-explanation-v1`.

Manifest artifact paths are package-relative, non-empty strings that stay
inside the package and use `/` separators. The manifest schema has
`additionalProperties: false` for `artifacts`, so new artifact keys require a
schema and semantic-validator change.

Current target artifact contract:

| Target | Package mode | Required artifacts | Manifest `nativeBinaryStatus` | Planned native file may be absent |
| --- | --- | --- | --- | --- |
| Metal | native | `backendSource`, `intermediate`, `nativeBinary` | forbidden | no |
| Vulkan | native | `backendAssembly`, `nativeBinary` | forbidden | no |
| DirectX | source-package | `backendSource`, `nativeBinary` | required: `planned` or `emitted` | yes, when `planned` |
| OpenGL | source-package | `backendSource`, `nativeBinary` | required: `planned` or `validated` | yes, when `planned` |

For DirectX and OpenGL, `nativeBinary` is a schema field name shared with native
targets. It does not by itself prove native binary parity. Release gates must
read `nativeBinaryStatus` and the package mode.

## Evidence State Vocabulary

Native backend evidence must name the state it proves. The fixture contract in
`tests/native-artifact-contract/evidence-rows.json` records this as
`claimState`, and `tools/check_native_artifact_contract.py` checks it against
descriptor and debug metadata:

- `source-package`: generated source/package evidence only. It can be verified
  and hashed, but it is not native binary evidence.
- `planned-native`: a source-package target has a planned native path, but the
  optional native tool was missing or failed. There must be no native artifact
  path, size, hash, validator provenance, or optimizer level claim.
- `emitted-native`: native artifact bytes exist and are named by descriptor
  path/hash/size metadata. This is artifact-existence evidence only unless
  validation also ran.
- `validated-native`: validator-backed evidence for the emitted artifact or
  validated source artifact. For source-package targets, the package mode still
  remains `source-package`.
- `optimized-native`: optimized native evidence. For Vulkan v0 this requires a
  `native-artifact-v0` descriptor with `optimizationLevel: "O2"` and a matching
  Vulkan native profile whose `debug.optimization.status` is `applied` for the
  same `.spvasm` source and `.spv` artifact paths.

None of these states is a performance claim. Runtime/driver acceptance,
graphics API object creation, device execution, and performance parity require
separate validation evidence and must not be inferred from package verification
or descriptor metadata alone.

## Target Compiler Optimization Policy

Target compiler flags are controlled by `cglc --opt-level`, not by the host
CMake build type alone. The benchmark `debug` and `release` lanes select CMake
`Debug` or `Release`; the `release-o2` lane is the one that additionally passes
`--opt-level O2`.

| Target tool | O0 / debug target policy | O1 default target policy | O2 target policy | Missing optional tool status |
| --- | --- | --- | --- | --- |
| Vulkan `spirv-opt` | Do not invoke optimizer; record `debug.optimization.status: "skipped-disabled"`. | Do not invoke optimizer; record `debug.optimization.status: "skipped-disabled"`. | Invoke `spirv-opt --target-env=vulkan1.2 -O`; successful runs record `debug.optimization.status: "applied"`. | O2 records `skipped-tool-missing`; this is metadata only, not optimization evidence. |
| Metal `xcrun metal` | Invoke `xcrun -sdk macosx metal -O0 -gline-tables-only` and record the debug compile profile in `metal-compile-options.json`. | Invoke `xcrun -sdk macosx metal -O2` and record the release compile profile. | Same conservative release compile profile as O1: `-O2`. | Missing `xcrun` fails native package emission; no package is promoted. |
| Metal `xcrun metallib` | Use default `metallib` link behavior. | Use default `metallib` link behavior. | Use default `metallib` link behavior. | Missing `metallib` fails native package emission; no package is promoted. |
| DirectX `dxc` | Invoke `dxc -O0` when available. | Invoke `dxc -O3` when available. | Invoke `dxc -O3` when available. | Missing or failing `dxc` keeps `nativeBinaryStatus: "planned"` and is not DXIL evidence. |

`cglc doctor --json` reports this policy through each relevant tool's
`toolchain.tools[].detail` field. It also reports
`toolchain.tools[].evidenceStatus` as `tool-missing`, `probe-failed`,
`version-unknown`, or `version-captured` so missing optional tools and failed
local version probes remain explicit report evidence instead of implicit target
support decisions. Unit tests pin the serialized metadata and the public Metal
compile-option helper so policy drift is visible before optional native tool
availability changes test coverage.

## Runtime Admission Boundary

Milestone 5 runtime admission is source-free and metadata-only. Runtime plans
consume `.cglb` directory or zip packages through manifest, reflection,
diagnostics, optional debug metadata, and declared artifact bytes. They do not
parse CrossGL source, invoke `cglc`, run target shader compilers, create native
graphics API objects, or execute device work. Runtime summaries therefore keep
`compilerInvocationRequired: false` and `deviceExecutionRequired: false`.

Runtime artifact selection is a handoff decision, not a backend parity claim:

| Request | Selection contract |
| --- | --- |
| `auto` | Prefer a usable `nativeBinary`; if none is usable, fall back to `backendSource` only for source-package targets. |
| `native` | Require a usable `nativeBinary`; planned or missing native artifacts reject admission. |
| `source-package` | Require `backendSource` and ignore optional `nativeBinary` files. |

Target-specific v0 admission:

- Metal and Vulkan are native-mode packages for runtime admission. Metal
  selects `.metallib`; Vulkan selects `.spv`. Their manifests must not declare
  `nativeBinaryStatus`.
- DirectX remains a source-package target. If DXIL is emitted and
  `nativeBinaryStatus: "emitted"` is consistent with the artifact, `auto`
  admission may select the `.dxil`; `source-package` admission still selects
  HLSL source.
- OpenGL remains a source-package target. `nativeBinaryStatus: "validated"`
  means validator-backed GLSL source evidence. It does not claim portable
  OpenGL program binaries or runtime object creation; `source-package`
  admission still selects generated GLSL `backendSource`.

Runtime-facing package inventory can be audited without parsing compiler source
with:

```sh
python tools/check_package_artifact_inventory_runtime.py --root . \
  --cglc build/cglc \
  --report-json /tmp/crossgl-package-artifact-inventory-runtime-report.json
```

The checker builds synthetic DirectX, OpenGL, Metal, and Vulkan package
fixtures, reads only `cglc package inspect --json` output, and validates that
declared artifact records, `nativeBinary`, Vulkan `nativeProfile`, and optional
`nativeArtifactDescriptor` metadata agree on runtime-loadable package paths,
existence, checksums, and source-package native status. Runtime-facing artifact
records and `nativeArtifactDescriptor` source/artifact hash and size fields are
checked against the package bytes, so mutually consistent but tampered inspect
records cannot stand in for the artifact actually present on disk. Its
self-test also exercises runtime selection directly: a Vulkan package whose
declared `nativeProfile` metadata names a non-Vulkan target is rejected before
loader dispatch without parsing source or invoking compiler/device work.

## Metal Contract

Concrete path:

```text
CrossGL source -> HIR -> Metal legalization -> MSL
  -> xcrun -sdk macosx metal -c <module>.metal -o <module>.air
  -> xcrun -sdk macosx metallib <module>.air -o <module>.metallib
  -> verified .cglb
```

Package artifacts:

- `backend/metal/<module>.metal`
- `backend/metal/<module>.air`
- `backend/metal/<module>.metallib`

Metal package builds also emit
`backend/metal/<module>.metal-compile-options.json` as backend-local policy
evidence. The file records the conservative native package compile policy,
including the selected profile, requested optimization level, debug-info
decision, and the exact Metal/metallib flag lists. It is intentionally not a
manifest artifact until a cross-target native profile contract exists for Metal.

Toolchain behavior:

- `cglc build --target metal` requires `xcrun` at package build time.
- The CTest discovery path requires Apple `xcrun`, `xcrun -find metal`, and
  `xcrun -find metallib` before registering real optional-native Metal tests.
- Missing `xcrun` is an error diagnostic: `metal.xcrun-missing`.
- Metal compiler failure is `metal.compile-failed`.
- Metal library failure is `metal.library-failed`.
- The default `O1` native package policy is release-oriented and passes `-O2`
  to `xcrun -sdk macosx metal`; `O2` currently uses the same conservative
  release profile. `O0` selects the debug profile, passes `-O0
  -gline-tables-only`, and keeps `xcrun -sdk macosx metallib` at its default
  link behavior.
- Successful native Metal packages with recorded `packageArtifactRequirements`
  must not declare manifest `nativeBinaryStatus`; inspect/verify summaries
  report `summary.nativeBinaryStatus: null` and rely on native package mode plus
  native artifact descriptor evidence for `.air` and `.metallib`.

Target validation commands:

```sh
build/cglc doctor --json tests/fixtures/SimpleShader.cgl
build/cglc explain-targets tests/fixtures/SimpleShader.cgl
build/cglc build tests/fixtures/SimpleShader.cgl --target metal \
  --output /tmp/SimpleShader-metal.cglb --debug-ir --diagnostics-json
build/cglc package inspect /tmp/SimpleShader-metal.cglb --json
build/cglc package verify /tmp/SimpleShader-metal.cglb \
  --source tests/fixtures/SimpleShader.cgl --json
ctest --test-dir build -L 'metal-native' --output-on-failure
ctest --test-dir build -R 'cglc_build_metal_native|cglc_manifest_json_schema_metal_native' \
  --output-on-failure
```

Release evidence required:

- Real Apple toolchain run, not only fake `xcrun`, producing `.air` and
  `.metallib`.
- `cglc_metal_toolchain_native_smoke` output, from `ctest -V` or
  `Testing/Temporary/LastTest.log`, showing the resolved `xcrun`, `metal`, and
  `metallib` paths used for that run.
- Verified package with `summary.target: "metal"`,
  `summary.nativeBinaryStatus: null`,
  `summary.targetLegalizationEvidence.packageMode: "native"`,
  `summary.nativeArtifactDescriptor.health: "ok"`, and manifest artifacts in
  the order pinned by the package target contract.
- Reflection `nativeBinary` equals the manifest `artifacts.nativeBinary`.
- Reflection target resource bindings prove Metal argument indices, binding
  classes, array sizes, and target-specific storage-buffer layout for the
  claimed feature row.
- Unsupported module shapes fail before package promotion with targeted Metal
  diagnostics and no successful package summary.

## Vulkan Contract

Concrete path:

```text
CrossGL source -> HIR -> Vulkan legalization -> SPIR-V assembly
  -> spirv-as --target-env vulkan1.2 <module>.spvasm -o <module>.spv
  -> optional O2 spirv-opt --target-env=vulkan1.2 -O <module>.spv -o <module>.opt.spv
  -> spirv-val --target-env vulkan1.2 <module>.spv
  -> optional spirv-dis <module>.spv -o <module>.disassembly.spvasm
  -> verified .cglb
```

Package artifacts:

- `backend/vulkan/<module>.spvasm`
- `backend/vulkan/<module>.spv`
- `backend/vulkan/<module>.disassembly.spvasm` when `spirv-dis` is available

Toolchain behavior:

- `spirv-as` and `spirv-val` are required for current Vulkan native packages.
- `spirv-opt` is discovered and reported by doctor/toolchain checks. Vulkan
  packages invoke it only for `--opt-level O2`; O0 and O1 record
  `debug.optimization.status: "skipped-disabled"` with
  `debug.optimization.policy: "disabled-by-opt-level"`.
- When O2 is requested and `spirv-opt` is unavailable, the package still builds
  after recording `debug.optimization.status: "skipped-tool-missing"`; this is
  skipped optimization metadata, not optimization evidence.
- When O2 `spirv-opt` succeeds, the optimized `.spv` replaces the assembled
  module and the final packaged `.spv` is validated by `spirv-val`.
- The native artifact descriptor records the requested compiler optimization
  level. Optimized-native Vulkan evidence requires the package `nativeProfile`
  to also record `debug.optimization.requestedLevel: "O2"` and
  `debug.optimization.status: "applied"` for the same `.spvasm` source path and
  `.spv` native artifact path; `skipped-disabled` and `skipped-tool-missing`
  remain skipped metadata, not optimizer evidence.
- `spirv-dis` is discovered and reported by doctor/toolchain checks. It is
  optional; packages succeed without it. When available, the Vulkan backend
  emits a human-readable disassembly sidecar next to the packaged `.spv`.
- Missing assembler is `vulkan.spirv-as-missing`.
- Missing validator is `vulkan.spirv-val-missing`.
- Assembly failure is `vulkan.assemble-failed`.
- O2 optimization failure is `vulkan.optimize-failed`.
- Validation failure is `vulkan.validate-failed`.
- Successful native Vulkan packages must not declare `nativeBinaryStatus`.
- The target environment is currently `vulkan1.2` in both assembly and
  validation invocations.

Target validation commands:

```sh
build/cglc doctor --json tests/fixtures/StorageBufferComputeShader.cgl
build/cglc explain-targets tests/fixtures/StorageBufferComputeShader.cgl
build/cglc build tests/fixtures/StorageBufferComputeShader.cgl --target vulkan \
  --output /tmp/StorageBufferComputeShader-vulkan.cglb --debug-ir --opt-level O2 \
  --diagnostics-json
spirv-as --target-env vulkan1.2 \
  /tmp/StorageBufferComputeShader-vulkan.cglb/backend/vulkan/StorageBufferComputeShader.spvasm \
  -o /tmp/StorageBufferComputeShader-vulkan.reassembled.spv
spirv-val --target-env vulkan1.2 \
  /tmp/StorageBufferComputeShader-vulkan.cglb/backend/vulkan/StorageBufferComputeShader.spv
spirv-dis \
  /tmp/StorageBufferComputeShader-vulkan.cglb/backend/vulkan/StorageBufferComputeShader.spv \
  -o /tmp/StorageBufferComputeShader-vulkan.disassembly.spvasm
build/cglc package inspect /tmp/StorageBufferComputeShader-vulkan.cglb --json
build/cglc package verify /tmp/StorageBufferComputeShader-vulkan.cglb \
  --source tests/fixtures/StorageBufferComputeShader.cgl --json
ctest --test-dir build -L 'vulkan-native' --output-on-failure
ctest --test-dir build -R 'cglc_build_vulkan_native|cglc_build_vulkan_native_fake_spirv_success' \
  --output-on-failure
```

Release evidence required:

- Real SPIR-V tools run, not only fake `spirv-as` and `spirv-val`.
- Package verification passes with `summary.target: "vulkan"` and
  `summary.nativeBinaryStatus: null`.
- `.spvasm` contains the expected entry point, execution mode, descriptor
  decorations, storage layouts, extensions, and capabilities for the claimed
  feature row.
- `spirv-val --target-env vulkan1.2` succeeds on the exact packaged `.spv`.
- O2 optimization claims require `debug.optimization.status: "applied"` in the
  Vulkan native profile, with `requestedLevel: "O2"` and paths matching the
  native artifact descriptor. `skipped-disabled` and `skipped-tool-missing` are
  not optimizer evidence.
- When `spirv-dis` is present, the package includes
  `backend/vulkan/<module>.disassembly.spvasm` as human-readable sidecar
  evidence for the final `.spv`.
- Reflection records match the SPIR-V ABI: descriptor type, set, binding,
  array element count, storage class, and target features.
- Validator failure blocks package promotion.

## DirectX Contract

Concrete path:

```text
CrossGL source -> HIR -> DirectX legalization -> HLSL source package
  -> optional dxc -> DXIL
  -> verified .cglb
```

Package artifacts:

- Compute source: `backend/directx/<module>.hlsl`
- Graphics source: `backend/directx/<module>.graphics.hlsl`
- Planned or emitted DXIL path: `backend/directx/<module>.dxil`

Toolchain behavior:

- DirectX is currently a source-package target, even when DXIL is emitted.
- `dxc` is optional. When unavailable, the package can still succeed with
  `nativeBinaryStatus: "planned"` and `directx.source-package-only`.
- When `dxc` succeeds, the package records `nativeBinaryStatus: "emitted"` and
  the `.dxil` artifact must exist.
- When `dxc` is found but fails, the package keeps HLSL source, records
  `nativeBinaryStatus: "planned"`, warns with `directx.dxc-failed`, and does
  not use that run as native evidence. The diagnostic records the deterministic
  command profile with package-relative source/output paths, entry point, and
  target profile, and any partial DXIL output is discarded before package
  verification.
- When `dxc` is unavailable, the package warns with
  `directx.source-package-only`, records that no `dxc` command was invoked, and
  keeps the planned source-package artifact contract.
- CrossGL passes `-O3` for native DXIL emission under the default `O1` policy;
  `O2` currently uses the same conservative flag and `O0` passes `-O0`.
- Compute uses `cs_6_0` unless explicit LOD shadow compare requires `cs_6_7`.
- Graphics uses vertex and fragment entry points with `vs_6_0`/`ps_6_0` or
  `vs_6_7`/`ps_6_7` for the same explicit LOD shadow compare requirement.

Target validation commands:

```sh
build/cglc doctor --json tests/fixtures/StorageBufferComputeShader.cgl
build/cglc explain-targets tests/fixtures/StorageBufferComputeShader.cgl
build/cglc build tests/fixtures/StorageBufferComputeShader.cgl --target directx \
  --output /tmp/StorageBufferComputeShader-directx.cglb --debug-ir \
  --diagnostics-json
dxc -O3 -T cs_6_0 -E compute_main -Fo /tmp/StorageBufferComputeShader.dxil \
  /tmp/StorageBufferComputeShader-directx.cglb/backend/directx/StorageBufferComputeShader.hlsl
build/cglc package inspect /tmp/StorageBufferComputeShader-directx.cglb --json
build/cglc package verify /tmp/StorageBufferComputeShader-directx.cglb \
  --source tests/fixtures/StorageBufferComputeShader.cgl --json
ctest --test-dir build -R 'directx.*fake_dxc|cglc_build_directx_source_package' \
  --output-on-failure
```

For graphics packages, validate both stages:

```sh
dxc -O3 -T vs_6_0 -E vertex_main -Fo /tmp/<module>.vertex.dxil \
  <package>/backend/directx/<module>.graphics.hlsl
dxc -O3 -T ps_6_0 -E fragment_main -Fo /tmp/<module>.fragment.dxil \
  <package>/backend/directx/<module>.graphics.hlsl
```

Release evidence required:

- Verified source package with `summary.target: "directx"` and
  `summary.nativeBinaryStatus` present.
- Real pinned `dxc` run on at least the release feature row. Fake `dxc` tests
  prove command wiring only, including the fixed `-O3` flag and the concrete
  `-Fo` artifact names for compute, vertex, and fragment DXIL outputs.
- For native DXIL evidence, `summary.nativeBinaryStatus` must be `emitted` and
  the `.dxil` artifact must exist and hash through package inspection.
- Reflection must record HLSL resource type, register class, register space,
  array sizes, and target feature requirements such as
  `intrinsic.NonUniformResourceIndex`.
- `planned` status is acceptable source-package evidence only. It is not native
  parity evidence.

## OpenGL Contract

Concrete path:

```text
CrossGL source -> HIR -> OpenGL legalization -> GLSL source package
  -> optional glslangValidator validation
  -> runtime/driver compilation by the consumer
```

OpenGL v0 is a source/runtime fallback. Portable OpenGL program binary
packaging is not part of the current contract.

Package artifacts:

- Compute source: `backend/opengl/<module>.comp.glsl`
- Graphics source: `backend/opengl/<module>.graphics.glsl`
- Validated source copy when validation succeeds:
  `backend/opengl/<module>.glsl`

Toolchain behavior:

- `glslangValidator` is optional.
- When unavailable, the package can still succeed with
  `nativeBinaryStatus: "planned"` and `opengl.source-package-only`.
- When validation succeeds, the package records
  `nativeBinaryStatus: "validated"` and writes the `.glsl` artifact.
- When validation fails, the package keeps GLSL source, records
  `nativeBinaryStatus: "planned"`, warns with `opengl.glslang-failed`, and
  does not use that run as validated evidence.
- Debug metadata records the validator provenance when `--debug-ir` is enabled:
  `sourcePackageValidation.tool: "glslangValidator"`,
  `policy: "use-when-available"`, and status `validated`,
  `skipped-tool-missing`, or `failed`.
- Fake-tool package-inspect tests pin the same validation statuses and
  diagnostics for validator success, validator failure, and unavailable-tool
  source-package fallback.
- Fake failing validators write a partial `.glsl` sentinel; OpenGL regression
  tests require the package to remove it and keep planned/unavailable evidence.
- Compute validation uses `glslangValidator -S comp`.
- Graphics validation uses linked vertex and fragment passes over the combined
  source with `-DCROSSGL_STAGE_VERTEX=1` and
  `-DCROSSGL_STAGE_FRAGMENT=1`.

Target validation commands:

```sh
build/cglc doctor --json tests/fixtures/StorageBufferComputeShader.cgl
build/cglc explain-targets tests/fixtures/StorageBufferComputeShader.cgl
build/cglc build tests/fixtures/StorageBufferComputeShader.cgl --target opengl \
  --output /tmp/StorageBufferComputeShader-opengl.cglb --debug-ir \
  --diagnostics-json
glslangValidator -S comp \
  /tmp/StorageBufferComputeShader-opengl.cglb/backend/opengl/StorageBufferComputeShader.comp.glsl
build/cglc package inspect /tmp/StorageBufferComputeShader-opengl.cglb --json
build/cglc package verify /tmp/StorageBufferComputeShader-opengl.cglb \
  --source tests/fixtures/StorageBufferComputeShader.cgl --json
ctest --test-dir build -R 'opengl.*glslang|cglc_build_opengl_source_package' \
  --output-on-failure
```

For graphics packages, validate both stages:

```sh
glslangValidator -l -S vert -DCROSSGL_STAGE_VERTEX=1 \
  <package>/backend/opengl/<module>.graphics.glsl
glslangValidator -l -S frag -DCROSSGL_STAGE_FRAGMENT=1 \
  <package>/backend/opengl/<module>.graphics.glsl
```

Release evidence required:

- Verified source package with `summary.target: "opengl"` and
  `summary.nativeBinaryStatus` present.
- `validated` status from real `glslangValidator` for every claimed GLSL row,
  or an explicit release note that the row is source-only planned validation.
- Reflection must preserve original CrossGL set/binding while recording the
  flattened OpenGL binding index, binding class, descriptor-array size/count,
  GLSL source type, and extension requirements such as
  `GL_EXT_nonuniform_qualifier`.
- Runtime evidence, when claiming end-user compatibility, must be separate from
  package verification because current `.cglb` files do not contain portable
  OpenGL program binaries.

## V0 Blockers To Native Parity Claims

- DirectX is not a native package target in the package decision model. It has
  `packageMode: "source-package"` and optional DXIL emission. Claiming native
  DirectX parity requires changing the target contract, release gates, and
  schema/semantic checks so DXIL is required for native rows instead of an
  optional `nativeBinaryStatus: "emitted"` detail.
- OpenGL has no portable native binary artifact in the v0 contract. It can
  claim GLSL source-package and validator coverage, not native binary parity.
- Vulkan is a native package path, but the backend is still named and gated as a
  prototype package. Native parity requires replacing each planned predicate
  rejection with package evidence or keeping it explicitly unsupported in
  `explain-targets`.
- Metal is a native package path, but release evidence is macOS toolchain
  dependent. Fake `xcrun` coverage is not enough for a release claim.
- Package schemas intentionally distinguish native-only targets from
  source-package targets. Adding artifacts, changing required artifacts, or
  moving `nativeBinaryStatus` requires updates to
  `tools/package_target_contracts.json`, generated headers/docs, JSON schemas,
  semantic validators, and fixtures in one change.
- Package verification proves artifact integrity and metadata consistency. It
  does not prove runtime execution, GPU behavior, root-signature compatibility,
  driver acceptance, or performance.
- DirectX and OpenGL tool failure currently degrades to a successful source
  package with warnings. Release gates must treat `planned` as blocked for any
  native or validated claim.
- Optional validator/compiler evidence is intentionally asymmetric:
  tool-present failures must surface the target diagnostic and either block
  package promotion or downgrade to explicit `planned` source-package evidence.
  Missing tools may register skipped sentinels or planned source-package
  evidence, but they must not silently satisfy native, DXIL, or validated GLSL
  support claims.

## Release Evidence Checklist

For every backend feature row promoted in a release:

- `cglc explain-targets <input.cgl>` shows the target as buildable with the
  expected package mode.
- `cglc build ... --debug-ir --diagnostics-json` succeeds and reports no error
  diagnostics.
- `cglc package inspect ... --json` passes schema validation and shows all
  required artifacts with regular-file status and SHA-256 digests.
- `cglc package verify ... --source <input.cgl> --json` succeeds.
- Target-specific real tool validation succeeds:
  - Metal: `xcrun metal` and `xcrun metallib`.
  - Vulkan: `spirv-as --target-env vulkan1.2` and
    `spirv-val --target-env vulkan1.2`.
  - DirectX: `dxc` emits DXIL when the row is claimed as native DXIL evidence.
  - OpenGL: `glslangValidator` validates GLSL when the row is claimed as
    validated source evidence.
- Reflection proves ABI facts for resources, entry points, workgroup sizes,
  vertex layouts, storage layouts, target features, and descriptor-array counts
  relevant to the row.
- Negative fixtures prove unsupported shapes fail with targeted diagnostics and
  do not publish a successful package.
- Optional native CTest labels register either real tool-backed coverage
  (`native-tool-available`) or an explicit skip sentinel
  (`native-tool-unavailable`); silent disappearance of native coverage is a
  release blocker.
- `tools/check_optional_native_validator_policy.py` audits the policy manifest
  and fake-tool CMake evidence so failure/unavailable validator fixtures cannot
  claim `emitted` or `validated` status without the required diagnostics.
