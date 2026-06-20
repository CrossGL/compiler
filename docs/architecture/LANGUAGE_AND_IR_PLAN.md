# CrossGL Language and IR Plan

This document defines the language and IR direction needed for CrossGL to become
a strong portable graphics language. It separates language semantics from
backend availability so that v0 can be small, coherent, and honest while the
compiler architecture still points toward a larger production language.

## Language Design Principles

- Portable by default, target-specific by opt-in feature gates.
- Explicit resource and memory semantics over implicit backend inference.
- Strong static typing with no hidden numeric narrowing or signedness changes.
- Stable layout rules that are reflected in packages and testable across
  targets.
- Structured diagnostics for every portability limitation.
- Native performance as a target, not source-level sameness as a target.

## Shared Spec Extraction

The first formal CrossGL language spec must be extracted from the CrossTL
frontend, not invented independently inside CrossGL-Compiler. The extraction
sources are:

- `CrossGL-Translator/crosstl/translator/lexer.py` for tokens and reserved
  words.
- `CrossGL-Translator/crosstl/translator/parser.py` for accepted grammar and
  source forms.
- `CrossGL-Translator/crosstl/translator/ast.py` for the canonical translation
  AST shape.
- `CrossGL-Translator/crosstl/translator/validation.py` for semantic checks
  already enforced by the translator.
- Translator examples and compiler/translator cross-repo contract fixtures for
  real accepted programs.

CrossGL-Compiler may propose stricter semantics where native compilation
requires them, but those changes must be handled as shared language changes:
update the spec, update CrossTL frontend behavior or compatibility diagnostics,
and update the cross-repo contract. The compiler should not drift into a second
CrossGL dialect.

## Language Surface Areas

### Modules and Entry Points

CrossGL modules should define named shader stages with explicit entry points.
v0 should cover:

- Compute stages.
- Vertex and fragment graphics stages.
- Explicit stage input/output records.
- Entry-point reflection.
- Stage-specific builtins such as global invocation ID, position, vertex ID,
  instance ID, and fragment coordinates where supported.

Later versions should add:

- Geometry, tessellation, mesh/task, ray tracing, and callable stages.
- Multi-entry modules with shared helper code and package-level linking.

### Type System

v0 should formalize:

- Scalar types: `bool`, `int`, `uint`, `float`.
- Vector types: `vec2`, `vec3`, `vec4`, plus integer and unsigned variants.
- Matrix types only when layout, multiplication order, and backend lowering are
  specified clearly.
- Struct types with target-neutral layout constraints.
- Fixed-size arrays with positive literal or folded integer dimensions.
- Runtime arrays only in explicitly supported storage-buffer tail positions.
- Resource types: buffers, uniform buffers, textures, samplers, storage images,
  shared memory, and descriptor arrays.

Rules to keep strict:

- No implicit integer/float conversion.
- No implicit signed/unsigned conversion.
- No implicit vector width change.
- No implicit pointer/address-space conversion.
- Explicit constructor or bitcast surfaces for every non-trivial conversion.

### Control Flow

v0 should support:

- Blocks, declarations, assignments, calls, returns.
- `if`/`else`.
- Structured `for` and `while`.
- `break`, `continue`, and `discard` where target/stage legal.

Unsupported or target-limited control flow should fail in target legalization,
not during string emission.

### Resource Model

CrossGL should keep a target-neutral resource model:

- Descriptor set and binding are source-level ABI coordinates.
- Resource arrays preserve source size and folded element count separately.
- `nonuniform(index)` is a semantic marker, not just syntax.
- Texture and sampler resources remain split even when a target uses combined
  sampler types at the use site.
- Storage-image access qualifiers and explicit formats are source semantics.
- Storage-buffer logical layout constraints are target-neutral HIR facts, while
  concrete target offsets, strides, address spaces, and argument/register
  coordinates are target ABI facts emitted by legalization and recorded in
  reflection.
- Standalone graphics ABI records preserve source resource order, and source
  `(stage, set, binding)` coordinates remain unique before target ABI mapping.

Target backends map this model into:

- Metal argument indices and argument namespaces.
- Vulkan descriptor sets, bindings, descriptor types, decorations, and SPIR-V
  capabilities.
- DirectX register classes, spaces, HLSL resource declarations, and DXIL
  profiles.
- OpenGL flattened bindings, GLSL declarations, extensions, and program
  validation policy.

## Graphics Stage ABI

The graphics ABI needs a concrete source-level model before broad graphics
support is considered complete. v0 graphics work should define:

- Vertex input locations, formats, and optional semantic names.
- Vertex-to-fragment varying locations and interpolation qualifiers.
- Builtins such as position, vertex ID, instance ID, front-facing, fragment
  coordinates, and sample-related values.
- Fragment outputs, render-target locations, and depth output policy.
- Validation that producer and consumer stage IO records match.
- Target mappings for Metal attributes/varyings, Vulkan locations/builtins,
  DirectX semantics/registers, and OpenGL locations/builtins.

Until that ABI is formalized, graphics backend package support should stay
fixture-scoped and evidence-driven.

### Memory and Synchronization

The language needs a formal memory model before it claims advanced features.
v0 should keep this intentionally narrow:

- Storage-buffer and storage-image read/write side effects.
- Shared/workgroup memory accesses that are observable inside a compute
  workgroup.
- `workgroupBarrier` as a workgroup-scope synchronization point for shared
  memory and supported workgroup-visible resource effects.
- Storage-image atomics only on explicitly formatted integer images where target
  legalization can map the operation to a native atomic instruction.
- Conservative, target-defined default atomic ordering until configurable
  memory scope and memory semantics are designed.

Target legalization must record the concrete memory mapping:

- Vulkan: storage classes, memory scope, semantics operands, SPIR-V image
  format, and required capabilities.
- Metal: address space, texture or buffer atomic form, and access qualifier.
- DirectX: UAV/resource form and `Interlocked*` mapping.
- OpenGL: image format, qualifier, extension requirements, and GLSL atomic
  operation.

Later versions should add:

- Configurable memory scopes and semantics.
- Coherent/volatile/restrict qualifiers.
- Subgroup/wave operations.
- Device-scope synchronization features.

### Texture and Image Operations

v0 should continue to grow from the current texture and storage-image evidence:

- Sampled textures with explicit sampler operands.
- Explicit LOD where each target has a legal mapping.
- Comparison sampling and manual comparison fallback policy.
- Storage-image loads, stores, explicit formats, access qualifiers, and integer
  atomics for the supported image families.

Do not claim broad image support until mip, sample, multisample, cube, 3D,
helper-function parameters, atomics, and memory semantics have explicit rules.

## Canonical HIR Requirements

Canonical HIR must be:

- Typed.
- Source-located.
- Structured.
- Target-neutral.
- Validatable without backend context.
- Serializable or dumpable in a stable form.
- Versioned for debug metadata and editor tooling.

HIR should eventually support a stable binary or JSON debug representation for
tooling, but source-controlled golden text dumps remain useful for human review.

## Floating-Point Semantics

Floating-point behavior must be specified before aggressive optimization can be
considered portable. v0 uses conservative IEEE-oriented source semantics:

- Preserve NaN, infinity, and signed-zero behavior unless an explicit fast-math
  mode is added later.
- Do not reassociate floating-point expressions.
- Do not introduce or remove fused multiply-add contraction.
- Do not fold operations whose result can differ because of NaN, signed zero,
  overflow, underflow, target precision, or rounding-mode behavior.
- Allow literal-only folds for operations with target-independent results under
  the compiler's chosen constant evaluator.
- Keep algebraic simplifications whitelist-based. For example, integer `x + 0`
  is safer than floating `x + 0.0` because of signed zero and NaN behavior.

Any future `fastmath` or precision qualifier must be represented in HIR and
reflection so target backends can select matching compiler flags.

## IR Layering

The planned layers are:

| Layer | Purpose | Stability |
| --- | --- | --- |
| AST | Syntax and source fidelity | Internal but source-compatible |
| HIR | Canonical semantics and v0 compiler contract | Stable enough for tests |
| Legalized HIR | Target-aware semantic lowering | Target-versioned |
| Backend IR | MSL, HLSL, GLSL, SPIR-V assembly, DXIL metadata | Target-owned |
| Real MLIR dialect | Future optimizing compiler framework | Reserved for gated experiments until parity |

The current `dump-ir --stage pseudo-mlir` output, and the legacy
`dump-ir --stage mlir` alias, are not this real MLIR dialect layer. They are
labeled textual HIR projections for debugging only, not registered MLIR dialect
output and not verifier-ready MLIR. Any future user-visible real MLIR surface
must use a distinct experiment-gated contract so the compatibility alias cannot
be mistaken for production MLIR lowering.

## HIR Verifier Invariants

The verifier should prove before backend dispatch that:

- Every stage has a valid entry point.
- Every expression has a type or a deliberate unknown diagnostic.
- Every resource has a kind, type, and binding policy.
- Every control-flow node is structurally valid.
- Every known intrinsic has legal arity and operand domains.
- Every storage-buffer shape is finite or an allowed runtime tail.
- Every resource array has either a valid fixed count or a legal runtime policy.
- Every source-preserved raw statement is rejected or legalized before backend
  support predicates claim success.

## Target Legalization Requirements

Target legalization should produce one of three outcomes:

- Supported without rewrite.
- Supported after explicit rewrite.
- Unsupported with structured diagnostics and missing capability IDs.

The outcome must be consumed by:

- `explain-targets`.
- `doctor --json`.
- package build selection.
- debug metadata.
- reflection target feature records.
- package verification expectations.

The concrete legalization result should include target profile, package mode,
required and missing capability IDs, structured diagnostics, target ABI facts,
rewrite records, and support-matrix evidence IDs. That result is the single
source for target support decisions across CLI, package, reflection, and debug
surfaces.

For every concrete target contract, the core evidence prefix is deterministic:
decision, state, support status, package mode, package-decision provenance,
optional native-tool state when present, and package reason. Consumers that gate
on a serialized legalization contract must fail closed when that support state
or evidence prefix violates the shared invariants.

## MLIR Entry Criteria

Start real MLIR work only when these are true:

- HIR verifier has stable invariants for the chosen subset.
- Target capability records are generated from shared models.
- Package schemas are stable for v0.
- The current textual `printMLIR`/`dump-ir --stage mlir` compatibility surface
  remains clearly marked as pseudo-MLIR, with `dump-ir --stage pseudo-mlir` as
  the canonical spelling and explicit "not real MLIR" markers in output,
  CLI/docs, package sidecars, and tests.
- A minimal CrossGL dialect can represent modules, stages, resources, typed
  values, control flow, and source locations without losing package metadata.

MLIR becomes production only after it passes fixture parity against HIR for a
defined subset and does not reduce native package coverage.
