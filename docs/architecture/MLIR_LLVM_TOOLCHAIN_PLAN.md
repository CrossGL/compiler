# CrossGL MLIR and LLVM Toolchain Plan

This document turns the MLIR/LLVM direction in
`docs/architecture/ARCHITECTURE_V2.md` and
`docs/architecture/LANGUAGE_AND_IR_PLAN.md` into an adoption plan. The
v0 decision record is
`docs/architecture/MLIR_LLVM_TOOLCHAIN_DECISION_V0.md`, and the machine-readable
follow-up gate is `experimental/mlir/experiment_gate_followup.v0.json`.
Together with `experimental/mlir/experiment_manifest.json`, those artifacts
keep MLIR and LLVM work as design and validation evidence until a future PR
adds production compiler integration. The
recommendation is staged adoption:

1. Keep the current C++ HIR as the production semantic IR through v0.
2. Make target legalization a real compiler layer before MLIR owns lowering.
3. Introduce MLIR as an optional, parity-tested projection from verified HIR.
4. Use LLVM infrastructure where it is already part of target toolchains or
   optional build discovery, but do not make LLVM IR the CrossGL shader IR.

The goal is not to make CrossGL look like a compiler by adding an MLIR
dependency. The goal is to protect source semantics, produce native packages,
and add compiler infrastructure only after it improves correctness,
diagnostics, portability, or optimization.

## Current Repo Grounding

The plan below is based on the current CrossGL-Compiler tree:

| Area | Current file evidence | Implication |
| --- | --- | --- |
| Shared language seed | `docs/language/crosstl-frontend-language-spec-v0.json`, `docs/language/README.md`, `tools/extract_crosstl_language_spec.py`, `tools/cross_repo_language_contract.json` | The source language must be extracted from CrossTL and tested as a shared contract before the compiler invents new syntax. |
| Source to HIR boundary | `include/crossgl/Driver/CompilerPipeline.h`, `src/Driver/CompilerPipeline.cpp`, `docs/COMPILER_PIPELINE.md` | `loadCompilerModule(...)` is the current source-to-post-pass-HIR boundary and should remain the production entry point for v0. |
| C++ HIR model | `include/crossgl/HIR/HIR.h`, `src/HIR/HIR.cpp` | HIR already carries modules, structs, constants, stages, resources, workgroup size, typed expressions, structured statements, and source locations. |
| HIR validation and optimization | `include/crossgl/Optimizer/HIRPassManager.h`, `src/Optimizer/HIRPassManager.cpp`, `docs/COMPILER_PIPELINE.md` | The pass manager is the right insertion point for target-independent verification and optimization before any MLIR projection. |
| Current pseudo-MLIR text | `include/crossgl/IR/IRPrinter.h`, `src/IR/IRPrinter.cpp` | `printMLIR(...)` emits a textual approximation, not a registered MLIR dialect. It must be renamed or clearly labeled before real MLIR appears. |
| Target selection and legalization seed | `include/crossgl/Backend/TargetCapabilities.h`, `include/crossgl/Backend/TargetLegalization.h`, `src/Backend/TargetLegalization.cpp` | A `TargetLegalizationResult` facade exists, but it currently wraps package decisions and does not yet own rewrites or complete ABI facts. |
| Target backends | `include/crossgl/Backend/MetalBackend.h`, `VulkanBackend.h`, `DirectXBackend.h`, `OpenGLBackend.h` and matching `src/Backend/*.cpp` files | Existing backends consume HIR directly and emit source or native artifacts. They should move behind legalized HIR, not be rewritten first. |
| Package artifacts | `docs/MANIFEST_JSON_SCHEMA.md`, `include/crossgl/Driver/PackageTargetContracts.h`, `src/Driver/PackagePublication.cpp` | The `.cglb` package contract already distinguishes native targets from source-package targets and must remain stable during compiler internals work. |
| Diagnostics and source maps | `include/crossgl/Basic/Diagnostic.h`, `docs/DIAGNOSTICS_JSON_SCHEMA.md`, `include/crossgl/Driver/DebugMetadata.h`, `docs/HIR_SOURCE_MAP_SCHEMA.md` | MLIR adoption must preserve structured diagnostics and HIR source-location provenance rather than replacing them with backend-only errors. |
| Toolchain discovery | `CMakeLists.txt`, `include/crossgl/Backend/Toolchain.h`, `src/Backend/Toolchain.cpp` | LLVM and MLIR are currently optional build discoveries; toolchain JSON already reports `hasMLIR` and LLVM version metadata. |

## Decision

CrossGL should use both MLIR and LLVM ecosystem pieces, but at different
layers and on different schedules.

MLIR should become the optional compiler framework for verified, structured,
source-located CrossGL semantics after HIR verifier and legalization contracts
are stable. It is appropriate for canonicalization, common subexpression
elimination, structured control-flow lowering, SPIR-V dialect experiments, and
longer-term backend factoring.

LLVM IR should not become the canonical shader IR. CrossGL needs to preserve
shader stages, descriptor sets and bindings, resource classes, storage-image
formats and access qualifiers, interpolation and graphics ABI, workgroup
semantics, nonuniform indexing markers, reflection metadata, package artifact
contracts, and target diagnostics. Plain LLVM IR would require rebuilding those
facts out of band. LLVM remains useful as:

- an optional configured dependency surfaced by `CMakeLists.txt` and package
  metadata;
- the infrastructure underneath tools such as DXC where CrossGL emits HLSL and
  receives DXIL;
- a possible long-term implementation detail for CPU-side tools or future
  target compilers, not CrossGL's semantic truth.

For v0, the production path should be:

```text
CrossTL-derived language spec
  -> CrossGL source parser and AST
  -> C++ semantic HIR
  -> HIR validation and target-independent optimization
  -> C++ target legalization result with ABI facts
  -> existing target backends
  -> target compilers and validators
  -> .cglb package with manifest, reflection, diagnostics, and debug metadata
```

The first real MLIR path should be optional:

```text
verified C++ HIR
  -> HIR MLIR dialect using canonical hir.* names
  -> MLIR verification and canonicalization
  -> parity reports and optional backend experiments
```

Only after that path preserves package evidence for a meaningful subset should
MLIR own production optimization or target lowering.

## Layered Compiler Model

### Layer 0: Shared Language Spec

The source language starts from CrossTL-derived facts, not from MLIR syntax.
The committed seed is `docs/language/crosstl-frontend-language-spec-v0.json`,
generated by `tools/extract_crosstl_language_spec.py`. The plan is:

- Turn the snapshot into prose grammar, semantic rules, and compatibility
  classes under `docs/language/`.
- Keep `tools/cross_repo_language_contract.json` as the compatibility gate
  between CrossGL-Translator AST behavior and CrossGL-Compiler HIR behavior.
- Treat compiler-only tightening as a shared spec decision with diagnostics,
  not as a hidden fork of the language.

### Layer 1: AST and Semantic HIR

The current AST remains a source-fidelity layer. The current C++ HIR remains
the production semantic layer for v0 because it already appears across:

- `include/crossgl/HIR/HIR.h`
- `src/HIR/TypeSemantics.cpp`
- `src/HIR/StorageShape.cpp`
- `src/HIR/Intrinsics.cpp`
- `src/HIR/SideEffects.cpp`
- `src/HIR/ConstantFolding.cpp`
- `src/Optimizer/HIRPassManager.cpp`
- `docs/COMPILER_PIPELINE.md`

HIR owns:

- typed source constructs;
- stages and entry points;
- resources, descriptor set/binding, resource arrays, storage images, samplers,
  storage buffers, uniform buffers, and shared memory;
- target-neutral storage-buffer shape facts;
- source locations for diagnostics, debug metadata, and HIR source maps;
- structured control flow;
- target-independent feature requirements.

HIR must not own final target ABI facts such as Metal argument indexes, HLSL
register spaces, OpenGL flattened bindings, SPIR-V decorations, DXIL profiles,
or emitted source spellings.

### Layer 2: Target-Independent HIR Passes

The default HIR pass pipeline is the v0 optimization and validation layer. It
should stay before target capability decisions and before MLIR projection.

Allowed here:

- verifier invariants for module, stage, resource, type, expression, statement,
  loop, intrinsic, and storage-shape validity;
- pure constant folding through the existing constant and intrinsic machinery;
- branch cleanup after constant conditions;
- unreachable statement cleanup;
- dead local declaration and dead local store cleanup;
- source-map-preserving simplifications that do not decide target ABI.

Not allowed here:

- target profile selection;
- descriptor binding remapping;
- resource array expansion for a specific API;
- storage layout offset finalization;
- emission of target-only helper code;
- SPIR-V, MSL, HLSL, or GLSL policy decisions.

### Layer 3: Target Legalization

Target legalization is the next serious compiler layer. The repo already has
`include/crossgl/Backend/TargetLegalization.h`. The current implementation in
`src/Backend/TargetLegalization.cpp` still derives outcomes from target package
decisions, but it now exposes a v0 `TargetLegalizationContract` projection so
downstream consumers can use one normalized support shape while real target
rewrites are built out.

The expanded result should include:

- requested target and resolved target;
- target profile and toolchain expectations;
- package mode: native, source-package, or unsupported;
- required and missing capability IDs from
  `include/crossgl/Backend/TargetCapabilities.h`;
- target-specific ABI facts;
- ordered rewrite records;
- structured diagnostics with source locations;
- support-matrix evidence IDs when available;
- links to package artifact expectations.

Legalization should produce one of these states for every target:

| State | Meaning | Backend behavior |
| --- | --- | --- |
| Supported without rewrite | HIR can lower directly for the target. | Backend emits from optimized HIR plus ABI facts. |
| Supported after rewrite | Legalization rewrote HIR or attached helper ABI facts. | Backend emits from legalized HIR and records rewrites in debug metadata. |
| Unsupported | Legal language, but selected target cannot support it. | Backend must not emit a successful package. Diagnostics explain missing capabilities. |

Examples that belong in legalization:

- Metal storage-buffer descriptor array expansion into multiple buffer
  arguments.
- Vulkan nonuniform descriptor indexing markers and required SPIR-V
  capabilities.
- DirectX sampler/comparison-sampler role splitting and register class policy.
- OpenGL descriptor set flattening and explicit LOD shadow-compare limits.
- Storage-image access qualifier and format legality per target.
- Runtime tail storage-buffer shape support and target layout facts.

### Layer 4: HIR MLIR Dialect

The first real MLIR layer should represent CrossGL HIR semantics, not target
semantics. It must use the canonical HIR dialect catalog names, written as
`hir.*`, so the C++ HIR model and HIR catalog remain the single semantic
authority. It should be lowered from verified C++ HIR and should fail if any
required source or package fact would be lost.

Minimum dialect concepts:

- `hir.module`
- `hir.stage`
- `hir.func`
- `hir.resource`
- `hir.constant`
- `hir.struct`
- typed scalar, vector, matrix, array, resource, texture, sampler,
  storage-image, storage-buffer, and shared-memory types;
- source-location attributes copied from HIR;
- descriptor set/binding attributes as source ABI coordinates;
- workgroup size attributes;
- storage-image access and format attributes;
- nonuniform index operation;
- structured branch, loop, break, continue, discard, and return operations;
- texture sample, compare, explicit LOD, manual compare, image load/store, and
  atomic operations.

This dialect should initially be a mirror of HIR, not a replacement for it.
The required tests are fixture parity tests:

- HIR fixture builds successfully.
- HIR-to-MLIR emits valid dialect text when MLIR is configured.
- MLIR verifier accepts the dialect.
- Source locations, resources, entry points, workgroup sizes, and target-neutral
  type information match HIR/debug metadata.
- The fixture manifest `boundaryFactCoverage` mirrors source-location, entry
  point, resource, target-independent resource metadata, and target-independent
  type facts from `experimental/mlir/fixture_inventory.json`.
- No production package path depends on MLIR yet.

### Layer 5: Legalized MLIR Dialects

After the HIR dialect has parity, add target-aware dialect layers only when
they remove real duplication:

| Dialect layer | Purpose | Gate |
| --- | --- | --- |
| `hir.legal` attributes or target-owned ops | Carry target profile, ABI facts, and rewrite provenance in MLIR form without redefining canonical HIR ops. | C++ `TargetLegalizationResult` is already complete and schema-covered. |
| MLIR `func`, `arith`, and `scf` | Represent structured computation and control flow for canonicalization. | HIR fixture parity plus source-location preservation. |
| MLIR `gpu` | Experiment with kernel/module structure where it maps cleanly. | Does not hide shader-stage ABI or resource binding policy. |
| MLIR `spirv` | Experiment with Vulkan SPIR-V lowering. | Output validates against the same `spirv-as` and `spirv-val` gate as the existing Vulkan backend. |

Do not route Metal, DirectX, or OpenGL through SPIR-V just to centralize code.
Direct target backends remain necessary for source-quality diagnostics, package
contracts, and API-specific ABI control.

### Layer 6: Backend and Native Binary Paths

The backend paths should stay explicit:

| Target | v0 path | Binary or validation artifact | Current repo anchors |
| --- | --- | --- | --- |
| Metal | HIR -> Metal legalization -> MSL -> `xcrun metal` -> AIR -> `xcrun metallib` -> `.metallib` | Native `.metallib`, with MSL and AIR artifacts | `include/crossgl/Backend/MetalBackend.h`, `src/Backend/MetalBackend.cpp`, `docs/architecture/TARGET_TOOLCHAIN_PLAN.md`, `include/crossgl/Driver/PackageTargetContracts.h` |
| Vulkan | HIR -> Vulkan legalization -> SPIR-V assembly -> `spirv-as` -> `.spv` -> `spirv-val` | Native `.spv`; debug disassembly and `spirv-opt` later | `include/crossgl/Backend/VulkanBackend.h`, `src/Backend/VulkanBackend.cpp`, `src/Backend/TargetCapabilities.cpp` |
| DirectX | HIR -> DirectX legalization -> HLSL -> source package, plus `dxc` -> DXIL when available | HLSL always for supported source package; DXIL when tool succeeds | `include/crossgl/Backend/DirectXBackend.h`, `src/Backend/DirectXBackend.cpp`, `docs/MANIFEST_JSON_SCHEMA.md` |
| OpenGL | HIR -> OpenGL legalization -> GLSL -> `glslangValidator` when available | GLSL source package with validation status; no portable binary claim for v0 | `include/crossgl/Backend/OpenGLBackend.h`, `src/Backend/OpenGLBackend.cpp`, `docs/MANIFEST_JSON_SCHEMA.md` |

The package contract stays the public interface. `manifest.json`,
`reflection.json`, `diagnostics.json`, `ir/debug-metadata.json`, and
`ir/hir-source-map.json` must not change just because a backend internally
moves from C++ lowering to MLIR-assisted lowering.

## What Stays in C++ HIR

Keep these in the current C++ HIR until after v0:

- Source parser and AST integration through `loadCompilerModule(...)`.
- HIR node ownership and data model in `include/crossgl/HIR/HIR.h`.
- Shared type/resource semantics in `src/HIR/TypeSemantics.cpp`.
- Storage shape invariants in `src/HIR/StorageShape.cpp`.
- Intrinsic registry and side-effect analysis in `src/HIR/Intrinsics.cpp` and
  `src/HIR/SideEffects.cpp`.
- Default validation and optimization pipeline in
  `src/Optimizer/HIRPassManager.cpp`.
- Target capability IDs and package decisions in
  `src/Backend/TargetCapabilities.cpp` until legalization consumes them.
- Package metadata, reflection, diagnostics, and debug metadata generation.
- Native package finalization and verification.

Reasons:

- The current test corpus and package schemas already depend on this boundary.
- HIR carries source locations and package-facing concepts that must be kept
  stable while the public v0 contract hardens.
- Rewriting parser, HIR, optimizer, and all backends at once would hide
  regressions behind an infrastructure migration.

## What Can Migrate to MLIR

Migration should be incremental and evidence-based:

| Candidate | First MLIR role | Production migration gate |
| --- | --- | --- |
| HIR textual projection | Replace pseudo-MLIR with real dialect printing when MLIR is configured. | `dump-ir --stage mlir` is clearly optional or renamed until real dialect output exists. |
| Module/stage/resource representation | Mirror HIR in the canonical `hir.*` dialect. | Fixture parity for source locations, resources, entry points, and workgroup sizes. |
| Structured control flow | Lower to MLIR structured control-flow ops where source semantics match. | Break/continue/discard behavior and diagnostics match C++ HIR. |
| Pure expression canonicalization | Use MLIR canonicalization and CSE for a defined pure subset. | Equal or better HIR pass results on optimizer fixtures with source-map preservation. |
| Vulkan SPIR-V generation | Experimental `hir.*` dialect -> SPIR-V dialect path. | `.spv` validates and package metadata matches the existing Vulkan path for selected fixtures. |
| Target rewrite records | Represent finalized legalization facts in MLIR attributes. | C++ `TargetLegalizationResult` already feeds explain-targets, doctor, debug metadata, reflection, and package build. |

Do not migrate these before v0:

- CrossTL shared spec extraction and compatibility policy.
- Parser and source diagnostics.
- `.cglb` package schemas and artifact rules.
- Existing Metal, Vulkan, DirectX, and OpenGL production backends.
- Native tool invocation and package verification.
- Target support claims and support-matrix evidence.

## Optimization Strategy

Optimization should happen at the highest layer that can prove semantic safety.

| Stage | Owner | Examples | Constraints |
| --- | --- | --- | --- |
| HIR verify | C++ HIR pass manager | shape checks, typed symbols, storage-buffer shapes | Always-on, cheap, source-located diagnostics. |
| HIR optimize | C++ HIR pass manager | constant intrinsic folding, branch cleanup, unreachable cleanup, dead locals, dead stores | Preserve conservative floating-point behavior from `docs/architecture/LANGUAGE_AND_IR_PLAN.md`. |
| Legalization rewrites | Target legalization | resource array expansion, shadow compare fallback, target binding assignment, profile selection | Must be recorded as rewrites and reflected in debug metadata. |
| MLIR canonicalization | Optional MLIR path | canonicalization, CSE, structured control-flow cleanup | Only for proven pure subsets and only after HIR parity. |
| Target tools | Vendor or target validators | `spirv-opt`, DXC optimization flags, Metal compiler flags | Controlled by package/debug metadata and disabled or minimized for readable debug output. |

The first production optimization levels should be package-visible:

- `-O0`: validation and required legalization only, readable artifacts.
- `-O1`: existing safe HIR cleanup and constant folding.
- `-O2`: target compiler optimization flags and optional target IR optimizers
  after validation coverage exists.

`spirv-opt` should be added after the Vulkan path has stable validation and
debug disassembly sidecars. DXC and Metal optimization flags should be recorded
in debug metadata when they affect artifacts.

## Caching and Artifacts

CrossGL should cache by semantic inputs, not by backend source strings alone.
The cache key should include:

- source hash from the package manifest;
- compiler version;
- shared language/spec snapshot hash or version;
- HIR schema or dump version;
- target, target profile, and package mode;
- legalization rewrite IDs and ABI facts;
- optimization level and pass pipeline identity;
- toolchain identity and compiler flags when native tools are invoked.

Cacheable artifacts:

- post-pass HIR dump;
- real `hir.*` MLIR dialect dump when enabled;
- legalization result JSON;
- backend source or assembly;
- native binary or validation result;
- reflection, diagnostics, debug metadata, and HIR source map;
- package verification result.

Artifact policy:

- Keep package-relative artifact paths stable according to
  `docs/MANIFEST_JSON_SCHEMA.md`.
- Do not expose MLIR artifacts as required package files until a schema update
  and package verifier support exist.
- If MLIR artifacts are emitted under `--debug-ir`, add them as optional debug
  artifacts only after schema and verifier updates.
- Native package caches must fail closed when a toolchain changes or a
  validator rejects regenerated output.

## Diagnostics and Source Maps

Diagnostics remain a CrossGL responsibility. MLIR and backend tools can add
notes, but they must not replace compiler diagnostics.

Required behavior:

- Preserve `SourceLocation` from AST through HIR, legalization, and MLIR.
- Map target-legalization diagnostics to original source when possible.
- Convert tool diagnostics from `xcrun`, `spirv-val`, DXC, and
  `glslangValidator` into structured CrossGL diagnostics with target/tool
  context.
- Record target decisions and missing capabilities in the same model consumed
  by `explain-targets`, `doctor --json`, debug metadata, and packages.
- Keep `docs/HIR_SOURCE_MAP_SCHEMA.md` as the editor-facing source map contract
  until an explicit MLIR source-map schema is designed.

MLIR location requirements:

- Every dialect op generated from HIR should carry either a file/line/column
  location or a fused location that includes the source HIR record.
- Generated helper operations should carry rewrite provenance from target
  legalization.
- MLIR verifier failures should be development diagnostics unless they can be
  tied to user source. User-facing errors must stay source-level and stable.

## Milestone Gates

### Gate 0: Documentation and Naming

- Dedicated MLIR/LLVM plan committed.
- Current `printMLIR(...)` behavior documented as pseudo-MLIR.
- `dump-ir --stage pseudo-mlir` is documented as the canonical textual HIR
  projection, and legacy `dump-ir --stage mlir` is documented as a pseudo-MLIR
  compatibility alias before real MLIR dialect output is added.

### Gate 1: v0 HIR Contract

- CrossTL-derived spec is turned into a prose v0 spec or checked snapshot.
- HIR verifier covers all v0-supported constructs.
- Raw-token fallback statements cannot reach a supported backend package claim.
- Package schemas, diagnostics, reflection, debug metadata, and source map
  contracts stay stable.

### Gate 2: Real Target Legalization

- `TargetLegalizationResult` contains support state, diagnostics, rewrites,
  ABI facts, capability IDs, target profile, package mode, and evidence IDs.
- `explain-targets`, `doctor --json`, debug metadata, reflection, and package
  builds consume the same legalization result or v0 legalization contract view.
- Backends are invoked only after legalization succeeds or after the selected
  source-package fallback is explicitly allowed.

### Gate 3: Optional CrossGL MLIR Dialect

- Build option is explicit and optional, such as
  `CROSSGL_ENABLE_MLIR_EXPERIMENTAL`.
- The compiler can still build and pass tests without MLIR.
- `experimental/mlir` remains a fixture-limited scaffold. CMake records the
  experiment source and fixture inventory, but builds the experiment target
  only when `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON` and MLIR is discovered.
- The `sourceInventory` in `experimental/mlir/experiment_manifest.json` must
  exactly match `CROSSGL_MLIR_EXPERIMENT_SOURCES`; today that source inventory
  is only `experimental/mlir/CrossGLMLIRExperiment.cpp`.
- The source-inventory gate treats `tests/mlir-package-sidecar-boundary`,
  package-relative `ir/*.mlir` sidecar names, verifier `.mlir` inputs, and the
  pseudo-MLIR printer/CLI files as boundary evidence, not real MLIR experiment
  sources.
- `tools/check_mlir_scaffold_source_inventory.py` is the report-only guard for
  that compile-gated source inventory. It checks CMake/manifest alignment,
  keeps the scaffold under `experimental/mlir`, rejects production headers or
  HIR-to-MLIR lowering entry points in the current inventory source, and does
  not probe MLIR while `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=OFF`.
- `experimental/mlir/CrossGLMLIRExperiment.cpp` remains a compile-gated
  scaffold source, not a lowering implementation. Its constexpr records name
  the admitted compute entry points, required source-location facts,
  target-independent type facts, resource-free versus single-storage-buffer
  resource modes, the `targetIndependentResourceMetadata` inventory, the
  structured `hir.if` inventory, and the builtin-MLIR smoke verifier input.
  Static assertions keep these records production-isolated from
  `crossgl_compiler` and package outputs.
- HIR-to-MLIR lowering covers a named fixture subset.
- The current inventory admits only minimal compute, scalar expression,
  storage-buffer, and single structured `if`/`else` fixtures; loops,
  `break`, `continue`, `discard`, and early-return control transfer remain
  outside the MLIR experiment.
- The experimental surface is limited to
  `experimental/mlir/CrossGLMLIRExperiment.cpp`,
  `experimental/mlir/fixture_inventory.json`, the
  `experimental/mlir/experiment_manifest.json` report-only manifest, the
  `docs/architecture/MLIR_DIALECT_BOUNDARY_CONTRACT.md` dialect boundary
  contract, the
  `crossgl_mlir_experiment` object target, and the
  `tools/check_mlir_experiment_gate.py` and
  `tools/check_mlir_experiment_manifest.py` policy checks.
- The production surface remains `crossgl_compiler`, `cglc`, C++ HIR,
  target legalization, existing backend emitters, package schemas,
  diagnostics, reflection, and debug metadata.
- The manifest `productionIsolation` rules audit production target sources,
  include directories, links, dependencies, and package output commands.
  `productionPackageMustExclude` keeps `crossgl_mlir_experiment` and
  `experimental/mlir` out of normal package outputs.
- The manifest `releaseBehaviorGate` keeps real MLIR and LLVM artifacts from
  release behavior until a production proposal proves source-map/debug
  preservation, native backend parity, fail-closed package evidence, and
  enabled/disabled MLIR coverage. Pseudo-MLIR cannot satisfy that gate.
- The CMake fixture list must exactly match the JSON fixture inventory. When
  the option is off or MLIR is absent, configure output records
  `CROSSGL_ENABLE_MLIR_EXPERIMENTAL`, `MLIR_FOUND`, and that
  `crossgl_mlir_experiment` was not created.
- The manifest `fixtureInventory` must exactly match both
  `CROSSGL_MLIR_EXPERIMENT_FIXTURES` and
  `experimental/mlir/fixture_inventory.json`; pseudo-MLIR production files stay
  separated by `separationRules` and
  `pseudoMlirFilesMustNotBeRealMlirFiles=true`.
- `tools/check_mlir_package_sidecar_boundary.py` remains
  MLIR-toolchain-free. Its repository fixtures under
  `tests/mlir-package-sidecar-boundary` include a valid pseudo-sidecar package,
  a pseudo-labeled package that attempts to masquerade as canonical `hir.*`
  dialect output, and a pseudo-labeled package that carries the real MLIR smoke
  marker. The checker rejects those invalid packages even when the payload is
  placed at the allowed `ir/pseudo-mlir.mlir` and legacy `ir/mlir.mlir` paths.
- Each fixture inventory record must carry `parityRequirements` for
  source-location, entry-point, and resource fields. Resource-free fixtures
  prove that descriptor, buffer, image, texture, and sampler families remain
  empty; resource-bearing fixtures name the descriptor and storage-buffer item
  fields that any future real MLIR projection must preserve.
- Each fixture inventory record must also carry report-only `loweringEvidence`
  for entry point identity, source-location expectation, resource mode, type
  facts, and control-flow category. `experimental/mlir/experiment_manifest.json`
  mirrors this block for every eligible fixture so Gate 3 can prove the named
  subset has target-independent HIR facts before real lowering is attempted.
- The manifest `verifierParityScaffold` is report-only evidence. It mirrors
  each eligible fixture's `boundaryFactCoverage` for source locations,
  typed HIR facts, resource fields, entry point identity, target-independent
  resource metadata, and target-independent type facts. The compile-gated C++
  scaffold mirrors those evidence categories without lowering HIR or linking
  production targets; executable verifier use remains optional-tool gated by
  `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON`, `MLIR_FOUND=TRUE`, and `mlir-opt`.
- The default build keeps `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=OFF`; the
  report-only checks can run without an installed MLIR toolchain.
- MLIR verifier tests are optional-tool gated.
- Configured-build optional-tool evidence must make verifier registration
  state explicit. Default-off and unavailable states are skipped evidence:
  they do not run `find_program`, do not probe `mlir-opt --version`, do not
  invoke `mlir-opt --verify-diagnostics`, do not build
  `crossgl_mlir_experiment`, and do not require verifier files. Only the
  available state may register the executable verifier, and that record must
  name `crossgl_mlir_experiment` plus
  `tests/fixtures/mlir/minimal_compute_builtin_module.mlir`.
- Source locations and package-facing metadata survive lowering.

The current eligible HIR-to-MLIR experiment fixture set is:

| Fixture path | Admitted slice |
| --- | --- |
| `tests/fixtures/MinimalComputeShader.cgl` | Minimal compute module, entry point, source file, local size, and return facts. |
| `tests/fixtures/ScalarExpressionComputeShader.cgl` | Straight-line scalar locals, scalar expressions, casts, comparisons, and return facts. |
| `tests/fixtures/StorageBufferComputeShader.cgl` | Single non-array float storage buffer at set 0 binding 0 plus write facts. |
| `tests/fixtures/IfComputeShader.cgl` | Single structured `if`/`else` branch using the same storage-buffer shape. |

Everything outside that table remains ineligible for real MLIR lowering until
the fixture inventory, report-only manifest, source-location facts, and
optional-tool gates are updated together.

### Gate 4: MLIR-Assisted Optimization

- MLIR canonicalization is enabled only for a pure subset with fixture parity.
- Optimizer fixture outputs match C++ HIR semantics.
- Debug metadata records the MLIR pass pipeline when it affects emitted
  artifacts.

### Gate 5: MLIR-Assisted Vulkan Lowering

- CrossGL MLIR -> SPIR-V dialect path exists for selected compute fixtures.
- Generated SPIR-V validates through the same `spirv-val` gate as the current
  Vulkan backend.
- Package manifest, reflection, diagnostics, and native binary paths are
  identical or intentionally versioned.
- Existing Vulkan backend remains available until the MLIR path has broader
  coverage and better evidence.

### Gate 6: Production Adoption Decision

- Each target has a written decision: stay direct backend, partially use MLIR,
  or move a specific lowering layer to MLIR.
- No target loses package support.
- CI covers MLIR-enabled and MLIR-disabled builds where practical.
- Package verification and support-matrix evidence remain the release gate.

## What Not to Rewrite Before v0

Do not rewrite these before v0:

- The parser and AST solely to fit MLIR.
- The C++ HIR data model.
- The existing HIR pass manager.
- All backends behind a new MLIR backend facade.
- Package manifest/reflection/debug schemas for speculative MLIR artifacts.
- Direct Metal MSL generation.
- Direct DirectX HLSL generation.
- OpenGL GLSL source-package emission.
- Vulkan SPIR-V package production before an MLIR path validates the same
  fixtures.
- Toolchain discovery and package verifier behavior.

The v0 compiler needs a stable source language, HIR verifier, legalization
contract, package model, and native/validator evidence more than it needs a new
IR implementation.

## Benefits

- HIR stays stable while CrossGL hardens as a language and package producer.
- MLIR adoption becomes measurable through fixture parity instead of faith.
- Backend-specific ABI facts are captured once in legalization and reused by
  diagnostics, reflection, debug metadata, and package decisions.
- Vulkan can eventually benefit from MLIR SPIR-V lowering without forcing
  Metal, DirectX, and OpenGL through a lossy common denominator.
- Optional MLIR builds let contributors experiment without making v0 users
  install an extra compiler stack.

## Risks and Controls

| Risk | Control |
| --- | --- |
| Infrastructure migration slows v0. | Keep MLIR optional and behind milestone gates. |
| Pseudo-MLIR confuses users. | Rename or label current `printMLIR(...)` output before real dialect output. |
| Source locations are lost in MLIR. | Require source-location parity tests before any MLIR output is user-facing. |
| Legalization remains scattered in backend predicates. | Promote `TargetLegalizationResult` before backend rewrites. |
| SPIR-V path diverges from package metadata. | Validate MLIR-generated `.spv` through the same package verifier and reflection checks. |
| LLVM IR loses shader ABI facts. | Do not use LLVM IR as canonical shader IR; keep shader-specific facts in HIR, legalization, MLIR attributes, and package metadata. |
| Optional tool differences destabilize CI. | Keep MLIR tests optional-tool gated and keep non-MLIR builds authoritative through v0. |

## v0 Exit Position

At v0, CrossGL should be able to say:

- The language surface is tied to the CrossTL-derived shared spec.
- The C++ HIR is the production semantic contract.
- Target legalization produces the support decision and ABI facts for all
  public package surfaces.
- Metal and Vulkan native package paths remain direct and validator-backed.
- DirectX and OpenGL remain source-package paths with optional native or
  validation status.
- MLIR is either not present or present only as an optional verified projection
  for a named subset.
- LLVM is a supporting ecosystem dependency, not CrossGL's semantic IR.
