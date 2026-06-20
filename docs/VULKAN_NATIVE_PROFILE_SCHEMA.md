# Vulkan Native Profile JSON Schema

Generated prototype Vulkan packages may include `artifacts.nativeProfile`,
currently `backend/vulkan/<module>.profile.json`. The current schema is
[`docs/schemas/vulkan-native-profile-v1.schema.json`](schemas/vulkan-native-profile-v1.schema.json).

The V1 sidecar records package-local Vulkan/SPIR-V evidence only:

- `schemaVersion`: integer schema version, currently `1`.
- `module`, `target`, and `api`: package identity. `target` and `api` are both
  `vulkan`.
- `profile`: the native prototype profile name, Vulkan target version, and
  SPIR-V version.
- `generator`: compiler component that emitted the prototype package.
- `artifacts`: package-relative `backendAssembly` `.spvasm` and `nativeBinary`
  `.spv` paths. These paths are part of the profile identity: semantic
  validation requires `backend/vulkan/<module>.spvasm` and
  `backend/vulkan/<module>.spv`.
- `debug`: binary/assembly format labels, the validation target environment,
  optional optimization evidence, and optional `spirv-dis` disassembly
  evidence. When present, `debug.optimization.requestedLevel` records the
  `cglc build --opt-level` value. Profiles with `requestedLevel` also record
  `targetEnv: "vulkan1.2"` and `toolStatus` so optimizer evidence names the
  same target environment as validation and distinguishes `not-run`, `missing`,
  and `available` optimizer states. Its absence means the V1 profile was
  emitted before build opt-level metadata existed. For profiles with
  `requestedLevel` present, `O0` and `O1` use
  `policy: "disabled-by-opt-level"`, `level: "none"`,
  `status: "skipped-disabled"`, `targetEnv: "vulkan1.2"`, and
  `toolStatus: "not-run"` and do not invoke `spirv-opt`. `O2` is the only level
  that uses `policy: "use-when-available"` with `level: "-O"`: if `spirv-opt`
  is available the backend invokes `spirv-opt --target-env=vulkan1.2 -O`,
  records `status: "applied"` and `toolStatus: "available"`, and validates the
  resulting `.spv`; if it is missing, the backend records
  `status: "skipped-tool-missing"` and `toolStatus: "missing"` and still
  requires `spirv-val` to validate the assembled unoptimized `.spv`. A present
  but failing `spirv-opt` emits `vulkan.optimize-failed` and no package is
  emitted.
  Only `requestedLevel: "O2"` with `status: "applied"` is O2 optimizer
  evidence for a native artifact descriptor. `skipped-disabled` and
  `skipped-tool-missing` remain diagnostic metadata and must not back a
  descriptor-level O2 optimization claim.
  `debug.disassembly.status` is `emitted`, `failed`, or
  `skipped-tool-missing`; `debug.disassembly.path` is the package-relative
  `.disassembly.spvasm` sidecar path only when a disassembly was emitted,
  otherwise `null`. When emitted, semantic validation requires
  `backend/vulkan/<module>.disassembly.spvasm` so the debug evidence cannot
  drift away from the package module identity.

`cglc package inspect --json` summarizes this sidecar under
`vulkanNativeProfile` and checks that the sidecar agrees with manifest package
metadata. Disassembly sidecars are human-readable debug evidence and are not
manifest artifacts unless a future package contract explicitly promotes them;
inspection reports their profile status/path and checks existence only when the
profile says the sidecar was emitted. Full sidecar contents remain available
through `manifest.artifacts.nativeProfile`.

`tools/check_native_artifact_contract.py` links the native artifact descriptor
contract to this sidecar for the canonical Vulkan O2 fixture: the descriptor
`artifactPath` must equal `artifacts.nativeBinary`, the descriptor `sourcePath`
must equal `artifacts.backendAssembly`, and
`debug.optimization.status` must be `applied`. Current-profile semantic checks
also require `debug.optimization.targetEnv: "vulkan1.2"` and
`debug.optimization.toolStatus: "available"` so descriptor-level O2 claims stay
tied to explicit optimizer invocation evidence.
