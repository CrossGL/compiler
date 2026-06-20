# MLIR/LLVM Toolchain Decision Record v0

Status: accepted for v0 design and validation gates.

Decision ID: `crossgl-v0-mlir-llvm-toolchain-decision`

Related artifacts:

- `docs/architecture/MLIR_LLVM_TOOLCHAIN_PLAN.md`
- `docs/architecture/MLIR_DIALECT_BOUNDARY_CONTRACT.md`
- `experimental/mlir/experiment_manifest.json`
- `experimental/mlir/experiment_gate_followup.v0.json`
- `experimental/mlir/fixture_inventory.json`
- `tools/check_mlir_dialect_boundary_contract.py`
- `tools/check_mlir_experiment_manifest.py`
- `tools/check_mlir_experiment_gate.py`
- `tools/check_mlir_package_sidecar_boundary.py`
- `tools/check_mlir_scaffold_source_inventory.py`

Current report-only fixture inputs:

- `tests/fixtures/MinimalComputeShader.cgl`
- `tests/fixtures/ScalarExpressionComputeShader.cgl`
- `tests/fixtures/StorageBufferComputeShader.cgl`
- `tests/fixtures/IfComputeShader.cgl`

Current report-only source inventory:

- `experimental/mlir/CrossGLMLIRExperiment.cpp`, listed by
  `CROSSGL_MLIR_EXPERIMENT_SOURCES` and mirrored in the manifest
  `sourceInventory`.
- That source is a compile-gated constexpr inventory only. It names admitted
  compute entry points, source-location facts, target-independent type facts,
  the resource-free and single-storage-buffer fixture modes,
  target-independent resource metadata, the structured `hir.if` control-flow
  slice, and the builtin-MLIR smoke verifier input. It does not include
  production HIR or backend headers, register a dialect, or replace the
  existing pseudo-MLIR dump path.
- `tools/check_mlir_scaffold_source_inventory.py` keeps that compile-gated
  source inventory aligned with CMake and the manifest while the default path
  remains `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=OFF`.

## Context

CrossGL's v0 compiler surface is a source language, a C++ HIR semantic model,
target legalization, native or source-package backend emission, and package
evidence. The public contract is the package: `manifest.json`,
`reflection.json`, `diagnostics.json`, `ir/debug-metadata.json`,
`ir/hir-source-map.json`, backend source or assembly, and native binary
artifacts where a target has a real binary format.

MLIR and LLVM can help CrossGL, but they solve different problems. MLIR is a
good fit for structured compiler IR, verification, canonicalization, and
dialect-to-dialect experiments. LLVM IR is a lower-level compiler IR that does
not directly preserve shader stage, resource binding, storage-image,
workgroup, reflection, and package metadata semantics without side channels.

## Decision

For v0, CrossGL keeps C++ HIR as the production semantic IR and keeps existing
backend package paths as the production surface. Real MLIR remains optional,
fixture-limited, and report-only until it proves parity with HIR and package
evidence.

MLIR dialects may be used when the experiment starts from verified C++ HIR,
preserves source locations and HIR facts, stays behind
`CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON`, and does not make `crossgl_compiler`,
`cglc`, package schemas, or backend emitters depend on MLIR.

The report-only manifest is also the pseudo-vs-real boundary. Its
`separationRules` require `pseudoMlirFilesMustNotBeRealMlirFiles=true`: the
legacy `dump-ir --stage mlir` alias remains pseudo-MLIR, while real MLIR work
is admitted only through `crossgl_mlir_experiment` and the explicit source and
fixture inventories.

LLVM IR must not be CrossGL's canonical shader IR. LLVM IR may be emitted only
when it is a target-owned or toolchain-owned artifact with a package purpose,
such as a future CPU-side tool, a target compiler handoff, or an inspected
debug artifact whose required shader ABI facts are already represented in HIR,
legalization, reflection, diagnostics, and package metadata.

## HIR Boundary

The v0 HIR boundary is:

```text
CrossGL source
  -> AST
  -> C++ HIR
  -> HIR validation and target-independent optimization
  -> target legalization with ABI facts
  -> backend-native source, assembly, validators, and binary artifacts
```

This boundary owns:

- typed modules, stages, entry points, expressions, and statements;
- resource classes, descriptor set/binding coordinates, storage buffers,
  storage images, textures, samplers, shared memory, and workgroup size;
- source locations for diagnostics and HIR source maps;
- target-independent feature requirements;
- package-facing evidence consumed by native binary and source-package gates.

Target legalization, not MLIR lowering, decides target package support,
backend ABI facts, rewrites, and missing capability diagnostics.

## HIR MLIR Dialect Authority

The first CrossGL-owned MLIR dialect must use canonical HIR dialect catalog names, written as `hir.*`. The C++ HIR model and HIR catalog remain the authority for semantic operation names; MLIR may project those names but must not introduce a competing `crossgl.*` HIR namespace.

Initial HIR MLIR operation names are reserved to mirror HIR concepts, for
example `hir.module`, `hir.stage`, `hir.func`, `hir.resource`,
`hir.constant`, and `hir.struct`. Any future target-specific or helper
operations must either extend the HIR catalog through the normal HIR decision
path or live in a clearly target-owned dialect that does not claim HIR
semantic authority.

## When To Use MLIR Dialects

Use a HIR MLIR dialect when all of these are true:

- input is verified C++ HIR, not source text or ad hoc pseudo-MLIR text;
- the dialect uses canonical `hir.*` names from the HIR catalog before target
  lowering;
- every operation derived from HIR carries source location or fused
  provenance;
- resource and stage facts remain comparable with reflection and debug
  metadata;
- package output can be disabled without changing normal builds;
- the fixture inventory and report-only manifest name the admitted HIR family.

Use MLIR common dialects only after the HIR dialect has parity:

- `func`, `arith`, and `scf` for structured computation and pure
  canonicalization;
- `gpu` only for kernel structure that does not hide shader ABI facts;
- `spirv` for Vulkan experiments only when generated `.spv` validates through
  the same native binary gate as the current Vulkan path.

Do not use MLIR dialects to centralize Metal, DirectX, or OpenGL through a
lossy common lowering path. Those backends keep direct target control until a
written target decision and package evidence justify migration.

## When To Emit LLVM IR

LLVM IR emission is allowed only outside the canonical shader semantics path.
An LLVM IR artifact must meet these conditions:

- HIR and target legalization already own shader semantics and ABI facts;
- the artifact has a named target, toolchain, and package or debug purpose;
- reflection, diagnostics, and source maps do not depend on recovering shader
  facts from LLVM IR;
- validation records the toolchain identity and any optimization pipeline that
  affected emitted artifacts;
- the package verifier can fail closed when LLVM-derived artifacts are stale,
  missing, or rejected by their target validator.

LLVM IR is not appropriate for CrossGL's canonical shader IR, target support
decision model, resource binding model, source diagnostic model, or package
metadata truth.

## Experiment Graduation

MLIR/LLVM experiments graduate only by evidence, in this order:

| Stage | Required evidence | Production impact |
| --- | --- | --- |
| Report-only | Decision record, manifest, fixture inventory, checker, and default-off CMake gate. | None. Normal builds do not use MLIR. |
| Compile-gated scaffold | `crossgl_mlir_experiment` builds only with `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON` and MLIR discovery; its source contains only fixture-limited inventory and verifier-smoke records. | None. Object target is isolated from `crossgl_compiler`. |
| Dialect verifier parity | Named fixtures lower from HIR to a real `hir.*` dialect, MLIR verifier accepts them, and HIR facts match inventory. | Optional developer test only. |
| HIR parity reports | Source locations, types, resources, entry points, workgroup sizes, diagnostics, and debug metadata match C++ HIR for an expanded subset. | Optional artifact/report only. |
| Backend experiment | A target-specific path, such as `hir.*` dialect to SPIR-V dialect, validates through the same backend-native binary gate as the direct backend. | Optional target experiment. |
| Production proposal | Written target decision, package verifier updates, CI coverage for enabled and disabled builds, and no regression in existing packages. | Explicit follow-up PR required. |

No experiment can skip directly from report-only or verifier parity into
package production. A production proposal must show that HIR, legalization,
reflection, diagnostics, package manifests, and native binary gates remain the
release authority.

## Release Behavior Gate

The manifest `releaseBehaviorGate` is the concrete admission check for any
future MLIR or LLVM artifact that wants to affect release behavior. It stays
blocked until a written production proposal provides native backend parity for
Metal, Vulkan, DirectX, and OpenGL, source-map/debug contracts, fail-closed
package verifier evidence, enabled and disabled MLIR coverage, and proof that
the direct backend release path remains available.

Pseudo-MLIR cannot satisfy `releaseBehaviorGate`. The legacy `mlir` dump stage
is compatibility text only, and the optional real MLIR experiment remains
behind `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON` until the gate has the required
evidence.

## Consequences

- v0 users do not need LLVM or MLIR to build or use CrossGL.
- Pseudo-MLIR remains labeled as pseudo output until a real dialect exists.
- MLIR adoption is measured through fixture parity and package evidence.
- LLVM remains useful as ecosystem infrastructure, not semantic truth.
- Backend-native binary goals stay explicit: Metal produces `.metallib`,
  Vulkan produces `.spv`, DirectX may produce DXIL when the target toolchain is
  available, and OpenGL remains a source-package and validator path for v0.
