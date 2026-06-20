# CrossGL Doctor JSON Schema

`cglc doctor --json` emits a machine-readable toolchain report. When an input
shader is supplied, `cglc doctor --json <input.cgl>` also embeds the target
explanation document as `targetExplanation`.

## Compatibility Policy

- `schemaVersion` is required and is currently `1`.
- Consumers should branch on `schemaVersion` before reading nested fields.
- Unknown future versions should be treated as incompatible unless the consumer
  explicitly opts into best-effort feature detection.
- Adding optional top-level, toolchain, tool, or target explanation fields is
  compatible within schema version 1.
- Removing required fields, changing field types, renaming fields, or changing
  target package decision semantics requires a schema-version bump.
- The compiler emits only the current schema.
- The current machine-readable schema is
  [`docs/schemas/doctor-v1.schema.json`](schemas/doctor-v1.schema.json).

## Version 1

Top-level fields:

- `schemaVersion`: integer schema version, currently `1`.
- `toolchain`: host and tool availability report.
- `targetExplanation`: `null` for toolchain-only reports, or a
  `TargetExplanationDocument` when an input shader is supplied.

The `toolchain` object contains:

- `hostPlatform`: `macos`, `windows`, `linux`, or `unknown`.
- `hostArch`: `arm64`, `x86_64`, or `unknown`.
- `defaultTarget`: host default backend target.
- `llvmVersion`: LLVM version used by the compiler build.
- `hasLLVM`: compatibility field for whether LLVM was discovered by the
  compiler build. This has the same value as `llvmConfigured`.
- `llvmConfigured`: explicit LLVM configure-time discovery status.
- `hasMLIR`: compatibility field for whether MLIR was discovered by the
  compiler build. This has the same value as `mlirConfigured`.
- `mlirConfigured`: explicit MLIR configure-time discovery status.
- `mlirNativePipelineAvailable`: whether CrossGL has the experimental native
  MLIR pipeline gate available. This is true only when MLIR was configured and
  `CROSSGL_ENABLE_MLIR_EXPERIMENTAL` was enabled at configure time.
- `tools`: array of tool records.

LLVM and MLIR fields currently report configure-time package detection and
tool availability only. They do not indicate that CrossGL lowers shaders
through LLVM IR or through a real MLIR dialect/pipeline. In schema version 1,
`mlirConfigured` reports MLIR discovery independently from the experimental
gate, while `mlirNativePipelineAvailable` additionally requires
`CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON`. The `dump-ir --stage mlir` compatibility
alias remains pseudo-MLIR debug output rather than registered MLIR dialect
output.
`tools/validate_json_schema.py` audits these configure-time fields by checking
that `hasLLVM` matches `llvmConfigured`, `hasMLIR` matches `mlirConfigured`,
and `mlirNativePipelineAvailable` is not true when MLIR is not configured.

Each tool record contains:

- `name`: tool name.
- `available`: whether the tool was found.
- `evidenceStatus`: normalized report evidence state. Current values are
  `tool-missing`, `probe-failed`, `version-unknown`, and `version-captured`.
  This field is derived from local discovery and version probing only; it does
  not promote optional native tool availability into backend support.
- `path`: resolved path, or an empty string when unavailable.
- `detail`: additional detection detail, currently empty for most tools.
- `source`: how the tool was discovered. Current values are `PATH`, `direct`,
  `fallback`, `xcrun`, or `not-found`. `PATH` means normal executable lookup
  found the tool in the process `PATH`; `fallback` means CrossGL's fixed local
  fallback directories found it; `xcrun` means Apple's `xcrun -find` resolved
  the tool; `direct` means the requested tool name was already a path; and
  `not-found` means no resolver found it.
- `resolvedPath`: resolved executable path when available, or an empty string.
  This mirrors `path` for compatibility with older consumers that already read
  `path`.
- `probeStatus`: cheap local version probe status. Current values are
  `succeeded`, `version-unknown`, `failed`, `not-started`, and `unavailable`.
  `succeeded` means a version string was captured. `version-unknown` means the
  tool was found and the probe ran successfully, but it emitted no usable
  version text. `failed` and `not-started` mean the probe could not complete.
  `unavailable` means the tool itself was not found.
- `version`: first line of local version output when `probeStatus` is
  `succeeded`.
- `versionDetail`: launch, exit, or no-output detail when `probeStatus` is
  `failed`, `not-started`, or `version-unknown`.

The optional native tool rows for `dxc`, `glslangValidator`, `spirv-as`,
`spirv-val`, `spirv-opt`, `spirv-dis`, `metal`, and `metallib` are always
present. Missing tools are reported with `available: false`,
`evidenceStatus: "tool-missing"`, empty `path` and `resolvedPath`, and
`probeStatus: "unavailable"`; this does not make those tools required for
normal compilation or CI.
`tools/validate_json_schema.py` also checks the compatibility path aliases and
probe evidence: available tools must keep `path` and `resolvedPath` aligned,
unavailable tools must not report paths or version text, successful probes must
carry captured `version` text and no failure detail, and failed, not-started, or
version-unknown probes must include `versionDetail` without reporting a
successful `version`. It also validates that `evidenceStatus` remains aligned
with `probeStatus`: `unavailable` maps to `tool-missing`, `succeeded` maps to
`version-captured`, `version-unknown` maps to `version-unknown`, and `failed`
or `not-started` maps to `probe-failed`.

Doctor probes do not use cloud services or network calls.

`targetExplanation`, when present, follows
[`docs/TARGET_EXPLANATION_SCHEMA.md`](TARGET_EXPLANATION_SCHEMA.md).
That embedded document uses the same module-specific package decision semantics
as `cglc explain-targets`: predicate-rejected DirectX/OpenGL source-package
modules are reported as unsupported target records, while accepted modules
remain buildable `source-package` recommendations when they are the best
available target. Embedded target records include the same projection-backed
`supportStatus`, `legalizationState`, `packageDecisionProvenance`, required
`legalizationCoreEvidenceIds` array, and, when emitted by the compiler, the
same optional `diagnosticEvidenceIds`, tool requirement, and optional
native-tool status fields as standalone target explanation JSON.
`tools/validate_json_schema.py` applies those target explanation semantic
checks to embedded documents, including package-mode evidence checks for native
and source-package support, diagnostic evidence checks for unsupported target
records, and tool requirement evidence/count checks for emitted target records.
It also checks that `targetExplanation.defaultTarget` matches
`toolchain.defaultTarget`.
Doctor validation additionally keeps DirectX and OpenGL source-package fallback
records tied to their optional native evidence: the native backend, toolchain,
and validator capabilities must remain required and missing while the
source-package backend capability remains present and not missing. Buildable
source-package target records cannot report missing capabilities outside that
optional native evidence set, because those blockers would contradict the
embedded package support state and core legalization evidence. For tool-backed
optional native evidence, a target record must not list the
capability as missing when the matching doctor tool row reports the tool as
available; this currently covers `directx.toolchain.dxc` via `dxc`. OpenGL
source-package fallback still records
`opengl.validation.glsl-program-validation` as missing native/runtime evidence;
`glslangValidator` availability describes GLSL source validation and does not
satisfy that program-validation capability.
