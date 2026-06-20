# CrossGL Target Toolchain Plan

This document records the target toolchain strategy for native and
source-package builds. The key principle is that CrossGL owns source semantics,
target ABI records, reflection, and package contracts. External tools compile,
validate, optimize, or cross-check target artifacts.

## Toolchain Summary

| Tool | Role | Production use |
| --- | --- | --- |
| `xcrun metal` | Compile generated MSL to AIR | Required for native Metal packages on Apple hosts |
| `xcrun metallib` | Link AIR into `.metallib` | Required for native Metal packages on Apple hosts |
| `spirv-as` | Assemble SPIR-V assembly | Required for current Vulkan native packages |
| `spirv-val` | Validate SPIR-V binary | Required for current Vulkan native packages |
| `spirv-opt` | Optimize SPIR-V binary | Optional for Vulkan native packages at `--opt-level O2`; skipped metadata when unavailable |
| `spirv-dis` | Disassemble SPIR-V for diagnostics/debug | Planned debug and golden-test aid |
| `dxc` | Compile HLSL to DXIL and validate HLSL | Optional native DirectX artifact producer |
| `glslangValidator` | Validate GLSL and optionally produce SPIR-V | Optional OpenGL source-package validator |
| Slang | Differential oracle and architecture reference | Optional test/reference tool, not source of truth |
| SPIRV-Cross | Reflection/cross-compile oracle | Optional fallback/reference tool, not source of truth |
| Tint/Naga | WebGPU-style validation references | Optional comparative testing tools |

## Target Capability Registry Invariants

The v0 backend selection contract is enforced across
`docs/target-capability-registry-v1.json`,
`tools/package_target_contracts.json`, `src/Backend/Target.cpp`, and the
`TargetCapabilityRegistryContract` table in `src/Backend/TargetCapabilities.cpp`.
`tools/check_target_capability_registry.py` is the focused gate for this
alignment.

The enforced v0 support classes are:

| Target | Package mode | Native support class | Baseline backend capability |
| --- | --- | --- | --- |
| `metal` | `native` | `native` | `metal.backend.native-metal-package` |
| `vulkan` | `native` | `prototype-native` | `vulkan.backend.vulkan-prototype-package` |
| `directx` | `source-package` | `planned-native` | `directx.backend.hlsl-lowering` |
| `opengl` | `source-package` | `planned-native` | `opengl.backend.glsl-lowering` |

`native` and `prototype-native` targets must have `nativeArtifact.status:
supported`, must not allow planned native binaries, and must remain
`targetInfo(...).implemented == true`. `planned-native` targets must remain
source-package selectable, must require native binary status, and must allow
planned native binary records.

## Metal

Recommended path:

```text
HIR -> Metal legalization -> MSL -> xcrun metal -> AIR -> xcrun metallib
```

Metal should stay a direct backend. A SPIR-V-to-MSL path can be useful for
differential tests, but direct MSL is necessary for control over argument ABI,
resource arrays, storage-buffer layouts, texture access, and Metal-specific
diagnostics.

Near-term requirements:

- Keep native Metal package tests on macOS.
- Preserve source MSL and AIR as package artifacts.
- Reflect Metal argument indices and namespaces.
- Keep storage-buffer layout metadata target-specific instead of assuming
  Vulkan `std430`.
- Add compile option records to debug metadata when optimization flags are
  introduced.

## Vulkan

Recommended v0 path:

```text
HIR -> Vulkan legalization -> SPIR-V assembly -> spirv-as -> SPIR-V binary
  -> optional O2 spirv-opt --target-env=vulkan1.2 -O -> spirv-val -> package
```

Vulkan must treat `spirv-val` failure as a compiler failure. The package should
never claim native Vulkan support for an invalid SPIR-V binary.
`spirv-opt` remains optional: O0 and O1 do not invoke it, O2 invokes
`spirv-opt --target-env=vulkan1.2 -O` when present, and O2 without the tool
records skipped optimization metadata without making the tool mandatory.
An available `spirv-opt` failure is a compiler failure and does not promote a
package from the staged build.

Planned improvements:

- Keep Vulkan native package availability dependent only on required
  `spirv-as` and `spirv-val`; optional optimizer evidence must not become a
  v0 package prerequisite.
- Emit disassembly sidecars in debug mode for human-readable diagnostics.
- Replace ad hoc SPIR-V assembly construction with a structured SPIR-V builder
  or MLIR SPIR-V lowering when that route proves parity.
- Track target environment explicitly (`vulkan1.2`, later `vulkan1.3`) in
  package metadata.
- Add schema, manifest/reflection, and CI assertions before allowing any target
  environment beyond the current Vulkan 1.2 path.

## DirectX

Recommended v0 path:

```text
HIR -> DirectX legalization -> HLSL -> package
                                  -> dxc -> DXIL when available
```

DirectX source packages are valid when `dxc` is unavailable, but a host with
`dxc` should emit DXIL and record `nativeBinaryStatus: emitted`.

Tool behavior must distinguish three states:

- `dxc` unavailable: source package may succeed with `nativeBinaryStatus:
  planned`.
- `dxc` available and succeeds: source package succeeds with DXIL and
  `nativeBinaryStatus: emitted`.
- `dxc` available and rejects generated HLSL: development builds may preserve a
  source package for diagnostics, but release promotion must treat the target
  feature row as blocked until the failure is fixed or reclassified as a
  planned unsupported diagnostic.

Near-term requirements:

- Compile compute and graphics profiles with the correct shader model.
- Use Shader Model 6.7 only when features such as explicit shadow compare LOD
  require it.
- Reflect register class and register space for SRV, UAV, sampler, and CBV
  bindings.
- Keep `SamplerState` and `SamplerComparisonState` role conflicts as structured
  diagnostics.
- Treat real `dxc` validation as stronger evidence than fake-tool tests.

Long-term considerations:

- Root signature generation belongs in the runtime or package ABI layer, not in
  raw HLSL emission alone.
- LLVM's DirectX backend should be watched but not used as the primary plan
  until it is no longer experimental for our needed feature set.

## OpenGL

Recommended v0 path:

```text
HIR -> OpenGL legalization -> GLSL -> glslangValidator when available
```

OpenGL should remain a source-package target for v0. Portable OpenGL program
binary packaging is not reliable enough to be the default package contract.

Validator behavior must distinguish:

- `glslangValidator` unavailable: source package may succeed with
  `nativeBinaryStatus: planned`.
- Validator available and succeeds: package records validation status.
- Validator available and rejects generated GLSL: development builds may keep
  diagnostics/source artifacts, but release promotion must block the support
  claim unless the shape is intentionally rejected by legalization.

Near-term requirements:

- Emit GLSL version and extension requirements explicitly.
- Flatten descriptor sets into OpenGL binding indices with reflection metadata
  preserving original set/binding.
- Validate generated GLSL with `glslangValidator` when present.
- Record `nativeBinaryStatus: validated` only for validated source artifacts.
- Keep target-specific limitations, such as unsupported explicit LOD shadow
  compare shapes, as planned diagnostics.

## Reference Tools

Reference tools are not production dependencies unless explicitly promoted.

### Slang

Use Slang to study:

- Capability sets.
- Multi-target code generation.
- Shader module and generic design.
- Target-specific diagnostics.

Use it for differential tests where feasible, but do not let it define CrossGL
language semantics.

### SPIRV-Cross

Use SPIRV-Cross to compare reflection and generated source shapes from SPIR-V.
It is valuable for testing and fallback experiments, but CrossGL should keep
direct target backends because source regenerated from SPIR-V can lose or
distort high-level ABI policy.

### Tint and Naga

Use Tint and Naga as references for validation discipline, IR design, and
backend coverage tradeoffs. They are especially useful for understanding
WebGPU-style restrictions, but CrossGL's target scope is broader than WebGPU.

## CI and Infrastructure

Baseline CI should continue to cover:

- Ubuntu: CMake/Ninja, SPIR-V tools, Vulkan package tests.
- macOS: CMake/Ninja, SPIR-V tools, Metal native package tests.
- Windows: CMake/MSVC, DirectX source and fake/real DXC coverage where possible.
- Cross-repo language contract against CrossGL-Translator.
- Pre-commit hooks before every push to `main`.

The local coordinator gate is stricter than current GitHub Actions:

```sh
pre-commit run --all-files
pre-commit run --hook-stage manual --all-files
ctest --test-dir build --output-on-failure -j <jobs>
```

If CI does not run pre-commit, the coordinator still must run it locally before
pushing. A future CI hardening batch should add explicit pre-commit jobs rather
than relying only on local discipline.

Private-repo CI cost policy: batch related pushes instead of using GitHub
Actions as the first feedback loop, run the full local coordinator gates before
pushing, and keep `workflow_dispatch` available for deliberate manual
validation runs. Scheduled workflow triggers are not part of the default
private-repo policy; heavyweight native validation should be launched through
explicit manual dispatch or a reviewed, documented exception. The coordinator
should wait for a meaningful batch, monitor CI after the push, and route
failures to the worker or subsystem owner.
Workflow cost controls must preserve push/PR cancellation and scoped expensive
path filters where they exist. Job timeout controls must also stay in place so
stalled native-toolchain probes or package jobs fail bounded instead of turning
into runaway hosted runs.

Optional expanded infrastructure:

- A self-hosted Apple Silicon runner for Metal performance and native package
  validation.
- A Windows runner with a pinned DXC release for real DXIL validation.
- A Linux runner with Vulkan SDK for broader SPIR-V and runtime tests.
- GCP Cloud Run or Cloud Build only for release orchestration, package signing,
  artifact indexing, and dashboard/report generation.

Cost rule: GPU-backed cloud jobs should be on-demand, manually gated, and
budget-limited. Normal compiler CI should stay CPU-only unless a milestone
explicitly requires device execution.

Cloud release rule: release validation must default to dry-run, mock, or
local-only execution. Any future GCS/GCP upload path must call the local release
publish guardrail before invoking cloud CLIs or SDKs, and live upload must
require `--allow-cloud-upload` or `CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD=1`.
