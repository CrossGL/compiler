# CrossGL Target Capability Registry

The target capability registry is a checked-in v0 data set that makes baseline
target support explicit and reviewable. The current registry instance is
[`docs/target-capability-registry-v1.json`](target-capability-registry-v1.json)
and is validated by
[`docs/schemas/target-capability-registry-v1.schema.json`](schemas/target-capability-registry-v1.schema.json).

The registry is intentionally descriptive. It does not enable backend behavior
by itself; backend implementation remains owned by compiler code and package
target contracts. The registry records the ordered baseline capability IDs
emitted by `src/Backend/TargetCapabilities.cpp` so the checked-in data cannot
drift from compiler capability emission. The checker
[`tools/check_target_capability_registry.py`](../tools/check_target_capability_registry.py)
keeps this data aligned with `tools/package_target_contracts.json` for native
artifact path facts and with
`include/crossgl/Backend/TargetCapabilityInventory.h` plus
`src/Backend/TargetCapabilities.cpp` for native/source package admission facts.

## v0 Scope

Registry v0 records the four public package targets in fixed order:

| Target | Package mode | Optimization capability | Native artifact capability | Package admission capability |
| --- | --- | --- | --- | --- |
| `metal` | `native` | `metal.optimization.hir-pipeline` | `metal.native-artifact.metallib` | `metal.package-admission.native-source-package` |
| `vulkan` | `native` | `vulkan.optimization.hir-pipeline` | `vulkan.native-artifact.spirv` | `vulkan.package-admission.native-source-package` |
| `directx` | `source-package` | `directx.optimization.hir-pipeline` | `directx.native-artifact.dxil` | `directx.package-admission.native-source-package` |
| `opengl` | `source-package` | `opengl.optimization.hir-pipeline` | `opengl.native-artifact.glsl-source` | `opengl.package-admission.native-source-package` |

Each target also carries the ordered `emittedBaselineCapabilities` list from
`addBaselineCapabilities`:

| Target | Emitted baseline capability IDs |
| --- | --- |
| `metal` | `metal.backend.native-metal-package`<br>`metal.sourceLanguage.MSL`<br>`metal.binaryFormat.metallib`<br>`metal.toolchain.xcrun-metal`<br>`metal.toolchain.xcrun-metallib` |
| `vulkan` | `vulkan.capability.Shader`<br>`vulkan.addressingModel.Logical`<br>`vulkan.memoryModel.GLSL450`<br>`vulkan.targetEnv.vulkan1.2`<br>`vulkan.backend.vulkan-prototype-package` |
| `directx` | `directx.backend.hlsl-lowering`<br>`directx.backend.native-dxil-package`<br>`directx.toolchain.dxc`<br>`directx.validation.dxil-validator` |
| `opengl` | `opengl.backend.glsl-lowering`<br>`opengl.backend.native-glsl-package`<br>`opengl.toolchain.opengl-driver`<br>`opengl.validation.glsl-program-validation` |

For v0 source-package targets, the emitted `toolchain` and `validation`
baseline capability IDs are the optional native tool requirement set consumed by
target legalization evidence. DirectX must expose `directx.toolchain.dxc` and
`directx.validation.dxil-validator`; OpenGL must expose
`opengl.toolchain.opengl-driver` and
`opengl.validation.glsl-program-validation`. The schema semantics reject drift
in those IDs so optional native tool evidence cannot silently change class or
name while the target remains `source-package`.

Each target record has three first-class capability groups:

- `optimization`: whether the target participates in the shared HIR
  optimization pipeline and which optimization levels are claimed.
- `nativeArtifact`: the native artifact status, package artifact keys, and
  native-binary-status policy derived from package target contracts.
- `packageAdmission`: the static native/source package admission contract,
  including `native`, `prototype-native`, or `planned-native` support class,
  native implementation and source-package selection flags, the baseline backend
  capability used for missing-capability evidence, the linked native artifact
  capability, package decision reason/rank, and package artifact requirement
  source plus evidence IDs.

The v0 package admission rows expose these support classes and baseline backend
admission capabilities:

| Target | Native support class | Baseline backend capability | Native implemented | Source package selectable |
| --- | --- | --- | --- | --- |
| `metal` | `native` | `metal.backend.native-metal-package` | `true` | `false` |
| `vulkan` | `prototype-native` | `vulkan.backend.vulkan-prototype-package` | `true` | `false` |
| `directx` | `planned-native` | `directx.backend.hlsl-lowering` | `false` | `true` |
| `opengl` | `planned-native` | `opengl.backend.glsl-lowering` | `false` | `true` |

The flattened `capabilities` array mirrors those structured fields with stable
capability IDs, status, summary text, and evidence references. Consumers that
only need auditable support IDs should read the flattened records; consumers
that need target packaging details should read the structured fields.
The checker requires each v0 target to expose exactly the structured
`optimization`, `nativeArtifact`, and `packageAdmission` capability IDs in the
flattened array, with matching status and evidence lists. Each structured
`optimization` and `nativeArtifact` row must keep both package contract evidence
anchors: `tools/package_target_contracts.json` and
`cglc_package_target_contracts`. Each structured `packageAdmission` row must
also keep `include/crossgl/Backend/TargetCapabilityInventory.h` and
`src/Backend/TargetCapabilities.cpp` as admission contract evidence anchors.
Its `packageArtifactRequirementsSource` is pinned to
`tools/package_target_contracts.json`, making the registry's static package
requirement projection explicit about the generated contract source it mirrors.

## Status Semantics

- `supported` means the registry claims current package support for that
  capability.
- `planned` means the registry exposes a package slot or status field, but the
  native artifact is not a current native package guarantee.
- `unsupported` is reserved for future records that need to make an explicit
  absence auditable.

For registry v0, Metal and Vulkan native artifact capabilities are `supported`.
DirectX and OpenGL native artifact capabilities are `planned` because their
current package mode is `source-package` and `nativeBinaryStatus` is required.

## Validation

Run the focused registry gate with:

```sh
python3 tools/check_target_capability_registry.py --root .
```

The checker validates the registry against the JSON schema, applies semantic
invariants from `tools/json_schema_semantics/target_capability_registry_v1.py`,
checks documentation references, and compares native artifact fields with
`tools/package_target_contracts.json`. It also resolves evidence entries to the
checked file path or `cglc_package_target_contracts` CTest, requires those two
package contract evidence anchors on every structured optimization and native
artifact support claim, pins v0 optimization levels to `O0`, `O1`, and `O2`,
pins source-package optional native tool requirement IDs, verifies that this
guide's v0 target table matches the checked-in registry rows, and compares
`emittedBaselineCapabilities` with `src/Backend/TargetCapabilities.cpp`.
