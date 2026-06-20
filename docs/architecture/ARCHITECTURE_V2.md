# CrossGL Compiler Architecture V2

This document defines the intended architecture for CrossGL-Compiler as a
native compiler and package producer. It is deliberately more ambitious than
the current implementation. The current compiler remains valuable as a working
prototype, test corpus, and incremental migration path, but the long-term
architecture must be designed around a real CrossGL language and a stable
semantic IR rather than around backend-specific source emitters.

## Goals

- Make CrossGL a first-class graphics language, not just a translation surface.
- Preserve enough semantic information to generate performant target-native
  artifacts for Metal, Vulkan, DirectX, and OpenGL.
- Keep target ABI decisions explicit and queryable through reflection,
  diagnostics, debug metadata, and package contracts.
- Optimize at the highest level that still preserves portable semantics, then
  use vendor compilers and validators for target-specific binary quality.
- Let unsupported target shapes fail early with structured diagnostics instead
  of falling through to backend source-generation errors.
- Make every public support claim traceable to a spec section, HIR fixture,
  target capability record, package test, and native or validator evidence.

## Shared Language Source of Truth

CrossGL-Compiler and CrossGL-Translator must share one CrossGL language
specification. The initial spec should be extracted from the CrossTL frontend:
`crosstl/translator/lexer.py`, `crosstl/translator/parser.py`,
`crosstl/translator/ast.py`, `crosstl/translator/validation.py`, examples, and
cross-repo contract fixtures. CrossGL-Compiler can then strengthen or narrow
the spec for native compilation, but those changes should be made deliberately
against the shared spec and reflected back into CrossTL when the frontend needs
to change.

The rule is: Translator and compiler may have different implementation
pipelines, but they must not have different languages. CrossTL remains the
interchange parser and compatibility reference until the shared grammar and
semantic spec are formalized.

## Non-Goals

- Do not use LLVM IR as CrossGL's canonical shader IR. LLVM IR is too low-level
  to preserve stages, resource bindings, descriptor spaces, interpolation,
  layout rules, memory scopes, and shader ABI decisions without rebuilding those
  concepts out of band.
- Do not make a real MLIR dependency a v0 blocker. MLIR is the preferred
  long-term compiler framework, but the current HIR must stay the production
  contract until a CrossGL dialect proves parity.
- Do not outsource CrossGL semantics to Slang, SPIRV-Cross, Tint, Naga, glslang,
  or DXC. These tools are useful validators, references, or target compilers,
  but CrossGL owns its source semantics and ABI model.

## Pipeline

The production pipeline is:

```text
CrossGL source
  -> lexer/parser AST
  -> semantic analysis
  -> canonical typed HIR
  -> HIR validation
  -> target-independent optimization
  -> target-aware legalization
  -> backend IR/source/binary emission
  -> vendor compiler and validator
  -> CrossGL package (.cglb) with reflection, diagnostics, and debug metadata
```

The current implementation already has the first usable version of this shape:
`source -> lexer -> parser AST -> HIR builder -> HIR pass pipeline ->
CompilerModule`. Architecture V2 keeps that direction but makes the boundaries
formal and stricter.

## Ownership Boundaries

### Source and AST

The AST owns syntactic fidelity. It should remain close to source text and
source locations. It is allowed to preserve raw or unknown syntax during
parsing, but source constructs that reach HIR must be semantically classified.

### Canonical HIR

HIR is the authoritative semantic representation for v0. It owns:

- Typed values and expressions.
- Structured control flow.
- Shader stages and entry points.
- Resources, resource arrays, storage images, storage buffers, uniforms,
  textures, samplers, and shared memory.
- Descriptor set/binding declarations.
- Target-neutral storage layout facts.
- Source provenance for diagnostics and tooling.
- Feature requirements that are independent of target APIs.

HIR should not encode target register spaces, Metal argument indices, OpenGL
binding flattening, Vulkan decorations, DXIL profiles, or MSL spelling. Those
belong in target ABI lowering.

HIR owns logical layout constraints, not final target layout. For example, HIR
can record source array dimensions, runtime-tail eligibility, struct field
order, and alignment-sensitive resource categories. Concrete byte offsets,
strides, address spaces, register classes, descriptor types, and Metal argument
coordinates are produced by target legalization and recorded as target-specific
ABI facts.

### HIR Validation

Validation must be cheap and always-on. The default pass pipeline should reject:

- Malformed expression and statement shapes.
- Unknown or incompatible types after semantic analysis.
- Invalid resource declarations and duplicate bindings.
- Unresolved stage entry points.
- Ill-formed storage-buffer and runtime-array shapes.
- Control-flow forms that cannot be represented in canonical HIR.

Raw-token fallbacks should be treated as source-preservation artifacts, not as
backend-ready HIR.

### HIR Optimization

Target-independent optimization runs before target capability decisions when it
does not change observable shader behavior. This layer owns:

- Constant folding and algebraic simplification.
- Intrinsic folding for pure known intrinsics.
- Dead local declarations and dead stores.
- Unreachable statement cleanup.
- Branch cleanup after constant conditions.
- Local scalar propagation where side-effect and scope analysis prove safety.

Target-independent optimization must not make target ABI decisions. For example,
it can preserve `nonuniform(index)` as a semantic marker, but Vulkan-specific
SPIR-V decorations belong to Vulkan legalization/emission.

### Target-Aware Legalization

Target-aware legalization is the biggest missing architecture layer. It runs
after HIR optimization and before backend emission. It should:

- Decide whether a module is supportable on the selected target.
- Rewrite legal but target-inconvenient HIR into backend-friendly HIR when the
  rewrite is semantics-preserving.
- Attach target ABI facts that are not target-neutral.
- Produce structured diagnostics for unsupported target shapes.
- Feed target capability, reflection, and package decisions from one model.

The legalization data contract should be a typed `LegalizationResult` owned by
the driver/backend boundary, not by ad hoc backend source printers. Its minimum
fields are:

- `target`: concrete target and target profile.
- `moduleSupported`: whether the target can build the optimized module.
- `packageMode`: native, source-package, or unsupported.
- `requiredCapabilities`: flat and grouped capability IDs required by the
  module.
- `missingCapabilities`: flat and grouped capability IDs that block support.
- `diagnostics`: structured diagnostics with source locations when available.
- `rewrites`: ordered records describing target-aware rewrites applied before
  backend emission.
- `abiFacts`: target resource bindings, layout records, entry-point ABI, native
  profile, extension/capability requirements, and toolchain expectations.
- `evidenceIds`: optional support-matrix evidence rows or fixture IDs that
  justify support claims.

`explain-targets`, `doctor --json`, debug metadata, package manifests,
reflection, and package verification should all consume this result rather than
recomputing support decisions independently.

The report-only JSON contract for the first migration checkpoint is
`docs/architecture/TARGET_LEGALIZATION_RESULT_V0.md`.

Examples:

- DirectX sampler state role splitting for ordinary vs comparison sampling.
- Metal storage-buffer descriptor array expansion into multiple buffer
  arguments.
- Vulkan descriptor-indexing capability and `NonUniformEXT` requirements.
- OpenGL shadow comparison LOD limitations for array and cube shapes.

### Backend Emission

Backends consume legalized HIR plus target ABI records. They should emit a
target artifact and metadata, not independently decide broad package policy.
The driver remains responsible for composing package manifests, reflection,
diagnostics, debug artifacts, and package verification.

## Target Toolchains

| Target | Backend artifact | Target profile | Native or validation tool | v0 package mode |
| --- | --- | --- | --- | --- |
| Metal | MSL, AIR, metallib | macOS Metal toolchain selected by `xcrun` | `xcrun metal`, `xcrun metallib` | native |
| Vulkan | SPIR-V assembly and `.spv` | Vulkan 1.2 target environment until schema says otherwise | `spirv-as --target-env vulkan1.2`, `spirv-val --target-env vulkan1.2`; `spirv-opt` is discovered/reported but not yet required | native |
| DirectX | HLSL, optional DXIL | Shader Model 6.0 by default, higher only per feature | `dxc` | source package with optional native binary |
| OpenGL | GLSL source, optional validated source | GLSL 4.50/4.60 according to emitted feature requirements | `glslangValidator` | source package with validation status |

Long-term DirectX should produce DXIL packages whenever `dxc` is available.
Long-term OpenGL may remain a validated source-package target unless a runtime
package format for program binaries becomes practical and portable enough.

## MLIR and LLVM Strategy

MLIR is the preferred long-term compiler framework, but it should enter as an
experimental parallel path:

```text
CrossGL HIR -> CrossGL MLIR dialect -> MLIR verification/canonicalization
  -> optional SPIR-V/GPU dialect lowering -> target backend experiments
```

The first MLIR milestone is not "replace HIR." It is:

- Rename or clearly label the current textual `printMLIR` output as
  pseudo-MLIR so users do not confuse it with a real MLIR dialect.
- Define a minimal CrossGL dialect.
- Lower a stable HIR subset into that dialect.
- Print and verify the dialect in CI when MLIR is available.
- Prove round-trip semantic parity for selected fixtures.

Only after that should MLIR own optimization or target lowering. Direct LLVM IR
remains a support technology through tools such as DXC, not CrossGL's semantic
truth.

## Package Model

The `.cglb` package is a compiler contract, not just a build output directory.
Every package must contain enough information for a runtime, editor, cache, or
release system to reason about the shader without reparsing generated target
source.

v0 `.cglb` packages are directory packages. Archive formats can be layered on
top later, but the directory layout and schemas are the compatibility anchor.
Current schema documents are the v0 baseline:

- `docs/MANIFEST_JSON_SCHEMA.md`
- `docs/REFLECTION_JSON_SCHEMA.md`
- `docs/DIAGNOSTICS_JSON_SCHEMA.md`
- `docs/DEBUG_METADATA_SCHEMA.md`
- `docs/HIR_SOURCE_MAP_SCHEMA.md`
- `docs/PACKAGE_INSPECT_SCHEMA.md`
- `docs/PACKAGE_VERIFY_SCHEMA.md`
- `docs/TARGET_EXPLANATION_SCHEMA.md`

Required package concepts:

- Source hash and compiler version.
- Target and package mode.
- Native binary or source artifact status.
- Reflection: entry points, resources, target bindings, layout metadata, target
  features, and native binary path.
- Diagnostics: empty for success, structured for planned or failed builds.
- Debug artifacts: HIR, HIR source map, target explanation, pass traces where
  requested.
- Verification: package integrity, schema validity, artifact existence, and
  source-hash checks.

Native-only targets such as Metal and Vulkan must provide a real native binary
artifact and must not use `nativeBinaryStatus`. Source-package targets such as
DirectX and OpenGL may provide target source plus `nativeBinaryStatus` values
such as `emitted`, `validated`, or `planned`, depending on toolchain results.
Architecture V2 should preserve those semantics while moving support decisions
to legalization results.

## Runtime Boundary

CrossGL-Compiler should not become the renderer. A separate CrossGL Runtime or
SDK should consume `.cglb` packages and create native API objects:

- Metal libraries, functions, pipeline descriptors, argument encoders, and
  resource bindings.
- Vulkan shader modules, descriptor set layouts, pipeline layouts, and pipeline
  objects.
- DirectX shader bytecode, root signatures, descriptor tables, and pipeline
  state objects.
- OpenGL shader/program objects and binding setup.

The compiler owns the package and reflection contract. The runtime owns device
creation, pipeline creation, resource lifetime, and command submission.
Runtime loader prototypes must keep that boundary visible in their handoff:
admission summaries should name the metadata documents, manifest-declared
artifact paths, and reflected binding facts they consume, while keeping source
inputs empty and compiler/device execution out of scope until a later runtime
milestone.

## Conformance Rule

No feature is considered supported just because one backend can print it. A
feature reaches support status only when all applicable evidence exists:

1. Language/spec statement.
2. Parser/HIR fixture.
3. HIR validation or semantic diagnostics.
4. Target capability record.
5. Backend or planned-failure evidence per target.
6. Package/reflection/schema evidence.
7. Native compiler or validator evidence where available.
8. Cross-repo compatibility check when the feature overlaps CrossGL-Translator.

This rule is how the project avoids random expansion while still moving fast.

## References

- MLIR: https://mlir.llvm.org/docs/
- MLIR SPIR-V dialect: https://mlir.llvm.org/docs/Dialects/SPIR-V/
- MLIR GPU dialect: https://mlir.llvm.org/docs/Dialects/GPU/
- LLVM DirectX target: https://llvm.org/docs/DirectXUsage.html
- Vulkan shader modules and SPIR-V: https://docs.vulkan.org/spec/latest/chapters/shaders.html
- SPIRV-Tools: https://github.com/KhronosGroup/SPIRV-Tools
- DirectX Shader Compiler: https://github.com/microsoft/DirectXShaderCompiler
- glslang: https://github.com/KhronosGroup/glslang
- Slang: https://github.com/shader-slang/slang
- SPIRV-Cross: https://github.com/KhronosGroup/SPIRV-Cross
