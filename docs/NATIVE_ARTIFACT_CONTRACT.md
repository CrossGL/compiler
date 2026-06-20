# Native Artifact Contract

`docs/schemas/native-artifact-v0.schema.json` defines a report-only descriptor
for native/package artifacts produced by the v0 native backend surface. Its
public schema `$id` is `https://crossgl.dev/schemas/native-artifact-v0.schema.json`.

Compiler-produced packages publish this descriptor as the optional
`manifest.artifacts.nativeArtifactDescriptor` JSON artifact. `cglc package
inspect --json`, `cglc package verify --json`, runtime package readers, and
release consumers load the descriptor from that manifest-declared path when it
is present. The contract is an audit shape for package manifests, release
checks, and backend-specific sidecars that need to describe Metal `.metallib`,
Vulkan SPIR-V modules, DirectX DXIL/DXBC binaries, and OpenGL source/package
outputs without using target-specific JSON shapes.

## Contract

The descriptor is a closed JSON object with these required fields:

- `schemaVersion`: schema version, currently `1`.
- `kind`: fixed to `crossgl.nativeArtifact`.
- `contractVersion`: fixed to `native-artifact-v0`.
- `target`: one of `metal`, `vulkan`, `directx`, or `opengl`.
- `binaryKind`: one of `metal.metallib`, `vulkan.spirv-module`,
  `directx.dxil`, `directx.dxbc`, `opengl.source`, or `opengl.package`.
- `sourcePath`: normalized path to the source artifact that was compiled,
  assembled, linked, generated, or packaged.
- `sourceHash`: `sha256` hash object for the source content.
- `toolchainProvenance`: producer, tool records, and hashed invocation
  provenance. Emitted or validated package descriptors enrich external tool
  records with evidence from the same tool resolver used by doctor/toolchain
  reporting when available: `resolvedExecutable`, `executableSource`,
  `versionProbeStatus`, captured `version`, and failure `versionDetail`.
  Planned source-package descriptors remain generator-only and do not promote
  optional native tools into native package evidence.
- `optimizationLevel`: `none`, `debug`, `O0`, `O1`, `O2`, `O3`, `Os`, `Oz`, or
  `unknown`.
- `validationStatus`: `not-run`, `validated`, `failed`, or `unavailable`.
- `validationDiagnostics`: validation diagnostics, empty unless validation
  failed.

Produced descriptors also carry:

- `artifactPath`: normalized package-relative or workspace-relative artifact
  path.
- `artifactHash`: `sha256` hash object for the output artifact content.
- `sizeBytes`: non-negative output artifact size in bytes.
- `optimizationEvidence`: optional descriptor-level optimizer evidence, including
  requested/effective levels, policy, status, tool details, and the sidecar or
  provenance source used to justify an optimizer claim.

Package artifact path fields such as `artifactPath`, `sourcePath`, optimizer
evidence `path`, and manifest-declared descriptor paths are normalized
`/`-separated relative paths. Leading `/`, Windows drive-prefixed forms such as
`C:/tmp/output.spv` or `C:tmp/output.spv`, backslashes, and `..` path traversal
are rejected for those package paths.

`toolchainProvenance.tools[].resolvedExecutable` is host toolchain evidence, not
a package artifact path. It may record an absolute POSIX path, Windows path, or
tool resolver output exactly as observed from the build host. Consumers must not
use it to locate files inside the package. `executableSource` uses the same
resolver vocabulary as doctor/toolchain reports: `PATH`, `direct`, `fallback`,
`xcrun`, or `not-found`.

`manifest.artifacts.nativeArtifactDescriptor` is the canonical package path for
the descriptor. Current compiler-built packages write it next to backend output
as `backend/<target>/<module>.native-artifact.json`, while some hand-authored
fixtures use `metadata/native-artifact.json`. That metadata path is a convention
for fixtures and examples, not the only valid v0 descriptor location. Consumers
must dereference the manifest artifact path and then compare descriptor
`sourcePath` and `artifactPath` fields against the package's other manifest
artifacts.

DirectX and OpenGL source-package descriptors also carry `nativeBinaryStatus`.
Metal and Vulkan descriptors have no planned state and are produced descriptors.
`planned` represents a successful source package with no produced native
artifact yet, so `artifactPath` and `artifactHash` are absent and
`sizeBytes` is absent, `validationStatus` is `unavailable`, and
`optimizationLevel` is `unknown`. `emitted` and `validated` require a produced
artifact path plus `artifactHash` and `sizeBytes`; `validated` must align with
`validationStatus: "validated"`.

For Vulkan, `optimizationLevel: "O2"` on a `vulkan.spirv-module` descriptor is
native optimizer evidence only when descriptor `optimizationEvidence` records
`requestedLevel: "O2"`, `effectiveLevel: "O2"`,
`policy: "use-when-available"`, `status: "applied"`, `tool: "spirv-opt"`,
`toolFlag: "-O"`, and an `evidenceSource` pointing to the package's
`artifacts.nativeProfile` sidecar. That sidecar must validate against
`docs/schemas/vulkan-native-profile-v1.schema.json`, records
`debug.optimization.requestedLevel: "O2"`, records
`debug.optimization.status: "applied"`, records
`debug.optimization.targetEnv: "vulkan1.2"` and
`debug.optimization.toolStatus: "available"`, and names the same `.spvasm`
source path and `.spv` artifact path as the descriptor.
`skipped-disabled` and `skipped-tool-missing` profile records are metadata, not
O2 optimizer evidence.

For DirectX, compiler-emitted DXIL descriptors may record descriptor-level
`optimizationEvidence` without a native-profile sidecar. The current compiler
maps CrossGL `O2` to DXC `-O3` and records
`policy: "crossgl-to-dxc-optimization-map"`, `status: "applied"`,
`tool: "dxc"`, and
`toolFlag: "-O3"` when DXIL is emitted. The `tool` value must match a
`toolchainProvenance.tools[].name` entry, so optimizer evidence cannot name a
tool that is absent from producer provenance. Legacy DirectX descriptors without
`optimizationEvidence` remain valid, and planned source-package descriptors
must still use `optimizationLevel: "unknown"`.

For Metal `.metallib` descriptors, compiler-emitted release evidence records
the conservative native package policy directly in the descriptor:
`policy: "metal-conservative-native-package-v1"`, `status: "applied"`,
`tool: "xcrun metal"`, `toolFlag: "-O2"`, `profile: "release"`,
`debugInfo: false`, and `flags: ["-O2"]`. The optimizer `tool` must match a
`toolchainProvenance.tools[].name` entry. Metal evidence is descriptor-level
provenance and does not require a Vulkan-style native-profile sidecar.

The target and binary kind are intentionally both required. Consumers can index
by target while still distinguishing DirectX DXIL from DXBC and OpenGL source
from packaged OpenGL output.

## Semantic Checks

`tools/json_schema_semantics/native_artifact_v0.py` and the focused contract
checker enforce cross-field and fixture-evidence rules that the structural
schema cannot express:

- `target` must own the declared `binaryKind`.
- `artifactPath`, when present, must use the extension expected for the binary
  kind.
- Produced descriptors must carry `artifactHash` and `sizeBytes`; planned
  source-package descriptors must not carry `artifactPath`, `artifactHash`, or
  `sizeBytes`.
- Required tool roles must be present for produced descriptors: Metal
  `.metallib` needs compiler and linker provenance, Vulkan SPIR-V modules need
  assembler provenance, DirectX DXIL/DXBC needs compiler provenance, OpenGL
  source needs generator provenance, and OpenGL packages need packager
  provenance. Planned source-package descriptors need generator provenance for
  the produced backend source.
- `validated` and `failed` descriptors must include validator provenance.
- DirectX and OpenGL descriptors must include `nativeBinaryStatus`; Metal and
  Vulkan descriptors must not. The source-package target set is cross-checked
  against `tools/package_target_contracts.json`.
- Planned source-package descriptors must use `optimizationLevel: "unknown"` so
  a planned DirectX or OpenGL native file does not become a native performance
  claim.
- Evidence rows must declare `claimState` as `source-package`,
  `planned-native`, `emitted-native`, `validated-native`, or
  `optimized-native`; the checker compares that state with package mode,
  `nativeBinaryStatus`, `validationStatus`, artifact path/hash/size fields, and
  Vulkan optimizer metadata.
- Vulkan `O2` descriptor evidence must be paired with a validating Vulkan
  native profile whose `debug.optimization.status` is `applied`, whose
  `debug.optimization.targetEnv` is `vulkan1.2`, whose
  `debug.optimization.toolStatus` is `available`, and whose source/native
  artifact paths match the descriptor. The native artifact contract checker also
  requires negative Vulkan profile fixtures proving that missing target-env,
  mismatched target-env, and non-available optimizer tool-status records are
  rejected before they can support an optimized-native claim.
- Applied descriptor-level optimizer evidence that names a `tool` must match a
  `toolchainProvenance.tools[].name` entry, keeping optimizer claims tied to
  executable producer metadata.
- DirectX and Metal descriptor-level optimizer evidence fixtures are checked
  against the compiler-emitted policy, tool, flag, effective level, and
  backend-specific fields while legacy descriptors without
  `optimizationEvidence` remain valid.
- `failed` descriptors must include at least one validation diagnostic, while
  non-failed descriptors must not carry diagnostics.

## Checkout-stable Hashed Fixtures

Descriptor fixture hashes and `sizeBytes` are byte claims. If a committed
native artifact descriptor fixture hashes a committed file, that file must be
checkout-stable across macOS, Linux, and Windows. Declare checkout stability in
`.gitattributes` with `-text`/binary handling, or an explicit `eol=lf` rule when
the hashed bytes are LF text by policy. Do not rely on user-level Git defaults
such as `core.autocrlf`.

Descriptor fixtures may also describe generated package paths rather than
committed payload bytes. Those paths are acceptable when the fixture is a
schema/semantic evidence fixture or the payload is generated deterministically
by the package-build test that owns the descriptor. Once a descriptor fixture
checks a real committed payload by `sourceHash`, `artifactHash`, or `sizeBytes`,
the committed payload must have a checkout-stable Git attribute declaration.

`runtime/examples/fixtures` contains source-free package fixtures with real
payload bytes. The source-free Vulkan example hashes its committed `.spvasm`
and `.spv` payloads, so those files are marked `-text` in `.gitattributes`.
The emitted DirectX DXIL example hashes committed HLSL source evidence and
fake `.dxil` bytes; the HLSL is pinned with `eol=lf` and the `.dxil` is marked
`-text` so descriptor `sourceHash`, `artifactHash`, and `sizeBytes` remain
checkout-stable without invoking DXC, D3D, a validator, or a device.
The native artifact contract checker audits these real byte-hashed fixture
references and reports schema-only/generated references separately.

## Canonical Fixtures

`tests/native-artifact-contract/evidence-rows.json` is the deterministic
evidence table for the v0 descriptor surface. It names every supported
target/binary-kind pair and may include additional rows when a pair has
multiple meaningful claim states, such as DirectX DXIL `emitted-native` and
`validated-native`. Each row records package mode, `claimState`, allowed
artifact extensions, required tool roles, and the valid produced descriptor
fixture that proves the row. It also names the Vulkan O2 native-profile evidence fixture
that links descriptor `optimizationLevel` to applied `spirv-opt` evidence,
planned source-package fixtures for DirectX and OpenGL, and representative
negative fixtures for target/kind ownership, artifact-extension drift,
native-status placement, planned artifact rules, planned optimizer overclaims,
validation provenance, and applied optimizer evidence that names a tool missing
from toolchain provenance. The `vulkanProfileNegativeFixtureEvidence` rows pin
the target-environment and optimizer tool-status guards used by Vulkan O2
evidence without making any performance parity claim.

`tests/native-artifact-contract/valid/*.json` contains valid descriptor
fixtures for every v0 binary kind and the planned source-package states. The
focused checker validates those fixtures, proves that all v0 target/kind rows
from `tests/native-artifact-contract/evidence-rows.json` are covered by valid
produced descriptors, allows additional claim-state evidence for an already
covered target/kind pair, and exercises the committed negative fixtures in
`tests/schema-failures/native-artifact-v0`.
The optimization-evidence section additionally names DirectX and Metal
descriptor fixtures that cover backend-specific compiler evidence without
requiring that legacy descriptors add the optional field. Package inspect and
verify fixture checks also synthesize a
`nativeArtifactDescriptor` package artifact so the descriptor fields are read
back and compared with manifest/file evidence by an executable consumer.

Validate the contract directly with:

```sh
python tools/check_native_artifact_contract.py --root .
python tools/check_invalid_json_schema_fixtures.py --root .
python tools/check_package_inspect_fixtures.py --root . --cglc build/cglc
python tools/check_package_verify_fixtures.py --root . --cglc build/cglc
```

## Report-only Descriptor Validation

External tools can validate descriptor JSON against this report-only contract
without implying that `cglc` emitted the descriptor:

```sh
python tools/check_native_artifact_contract.py --root . \
  --descriptor path/to/native-artifact.json
```

Passing `--descriptor` validates the supplied `native-artifact-v0` file against
the schema, semantic checks, and descriptor-level optimization guardrails. It
does not read package manifests, produce native artifacts, or claim native
parity for targets whose package contract is source-package/report-only.
