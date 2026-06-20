# Compiler Pipeline

CrossGL-Compiler keeps one source-text driver boundary for the current
front-end pipeline:

```text
source file -> lexer -> parser AST -> HIR builder -> HIR pass pipeline
  -> CompilerModule
```

The public API for that boundary is `crossgl::loadCompilerModule(...)` for
files and `crossgl::loadCompilerModuleFromSource(...)` for generated
in-memory source in `include/crossgl/Driver/CompilerPipeline.h`. Both return a
`CompilerModule` containing the compiler-input identity, original source text,
parsed AST, post-pass typed HIR, and the HIR pass pipeline result. Driver
operations such as `check`, `dump-ir`, target explanation, and package builds
consume this same boundary so diagnostics and HIR construction stay consistent.
The translator-to-compiler handoff rules are documented in
[COMPILER_INGEST_CONTRACT.md](COMPILER_INGEST_CONTRACT.md).

## Current Boundaries

- Frontend: `Lexer` and `Parser` own tokenization and AST construction.
- HIR: `buildHIR` performs semantic lowering, resource discovery, typed
  expression/statement construction, and current semantic diagnostics.
  `crossgl/HIR/TypeSemantics.h` owns shared HIR type classification,
  qualifier/pointer normalization, array element views, resource-kind
  inference, and conservative type-compatibility policy used by lowering,
  storage layout, backends, and post-HIR validation.
  `crossgl/HIR/StorageShape.h` owns target-neutral storage-buffer shape
  invariants that later passes, layout code, and backend policy checks can
  share without pulling in target-specific capability rules.
- Optimizer: `runHIRPassPipeline` owns the post-HIR optimization insertion
  point. It accepts named pass descriptors, records per-pass change results,
  and runs the default `hir.validate.module-shape` pass before backends consume
  HIR, followed by `hir.validate.typed-symbols` for backend-facing type and
  scope guarantees and `hir.validate.storage-buffer-shapes` for target-neutral
  storage-buffer layout-shape invariants. Loop headers allow parsed
  declaration, assignment, and expression statements plus raw-token fallback
  statements so partially supported source constructs can stay lossless until a
  later legalization pass handles them. Source `while` statements are
  compiler-local HIR today: they lower through the existing loop statement kind
  with an empty initializer and header update so semantic checks and HIR dumps can
  preserve condition/body scope without implying target package support.
- Driver: `CompilerPipeline` is the shared source-to-post-pass-HIR entrypoint.
  File inputs and generated `SourceInput` buffers share the same byte
  validation, lexer, parser, HIR builder, and HIR pass pipeline. Package builds
  remain file-based for v0 source-hash verification.
- Target policy: `TargetCapabilities` and `TargetExplanation` decide package
  viability from HIR. `cglc build --target auto` consumes the same target
  recommendation as `cglc explain-targets`: the host default wins a best-rank
  buildable tie, the best ranked buildable target can be selected when the host
  default is not buildable, and the host default may remain selected when no
  target is buildable so diagnostics name a concrete target.
- Backend/package emission: Metal, Vulkan, DirectX, and OpenGL consume HIR and
  produce target source, native binaries where available, reflection, manifest,
  diagnostics, and optional debug IR artifacts. Package finalization runs the
  native verifier over the generated directory before reporting build success,
  so emitted packages satisfy the same artifact, source-hash, reflection, and
  debug IR contracts that `cglc package verify` exposes to consumers. Backend
  output is staged in a sibling temporary directory and promoted into the
  requested output path only after finalization succeeds.

## Translator And Batch Boundary

The compiler accepts generated CrossGL `.cgl` text, not serialized CrossTL AST
or CrossTL IR JSON. `SourceInput` gives orchestrators a no-temp-file API for
single generated modules while preserving a logical compiler-input path for
diagnostics and source maps. Repository-scale discovery, batch manifests, and
generated-to-original span remapping remain translator/orchestrator
responsibilities until a dedicated compiler schema is introduced. Source-ingest
CLI commands reject reserved batch-manifest flags so repository tooling cannot
silently pass unused manifest arguments into per-file compiler commands.

## CLI v0 Contract Surface

The public `cglc` commands share the same source-to-HIR boundary described
above. v0 command behavior treats exit code `0` as success, `1` as a source,
target, package, or verification failure, and `2` as a usage or argument
error. Text diagnostics are written to stderr. JSON modes write the command
document to stdout and keep diagnostics either in that document or on stderr
when the command also has a human-readable diagnostic stream.

| Command | v0 behavior |
| --- | --- |
| `cglc check <input.cgl> [--opt-level O0\|O1\|O2] [--logical-input <path>] [--source-remap <remap.json>] [--diagnostics-json]` | Loads the compiler module and returns `0` when no errors are reported. `--opt-level` defaults to `O1`. `--logical-input` changes public diagnostic/source-map coordinates after the physical input file is loaded, and `--source-remap` can add original-source coordinates to diagnostic JSON without changing the physical source hash. Text mode prints `check passed: <input>` on stdout. `--diagnostics-json` emits diagnostics JSON v1 on stdout and suppresses the pass message. |
| `cglc dump-ir <input.cgl> [--stage <stage>] [--target <target>] [--opt-level O0\|O1\|O2] [--logical-input <path>] [--source-remap <remap.json>]` | Dumps post-pass IR from the shared pipeline. `--stage` currently defaults to `hir`; accepted stages are `hir`, `crossgl`, `pseudo-mlir`, `backend`, `debug`, `hir-source-map`, and `hir-pass-trace`. `--opt-level` defaults to `O1`, and `hir-pass-trace` reports the selected level and executed HIR pass policy. `pseudo-mlir` is a textual HIR projection, not a registered MLIR dialect; `mlir` remains a compatibility alias that emits the same pseudo-MLIR with a warning so the real `mlir` stage remains available for a future `CROSSGL_ENABLE_MLIR_EXPERIMENTAL` path. `debug`, `hir-source-map`, and `hir-pass-trace` emit schema-versioned JSON; `hir-source-map` emits schema 7 by default and can opt into schema 8 with `--source-map-schema-version 8` or the `--hir-source-map-schema-version 8` alias. `debug` and `hir-source-map` honor logical input/source remap provenance, while the other stages emit text IR. Bad stage, target, opt-level, source-remap, source-map schema selector, or source-map pagination arguments return `2`. |
| `cglc explain-targets <input.cgl> [--logical-input <path>]` | Emits target explanation JSON v1 for the post-pass HIR. `--logical-input` changes public source diagnostics before JSON production; the schema remains unchanged on success. The same target package decision data feeds `build --target auto` and `doctor --json <input.cgl>`. |
| `cglc doctor [--json] [input.cgl]` | Without input, reports host/toolchain status. With input, appends target explanation text or embeds target explanation JSON v1 under `targetExplanation`. JSON mode emits doctor JSON v1 and uses `targetExplanation: null` when no input is supplied. |
| `cglc build <input.cgl> [--target <target>] [--output <out.cglb>] [--opt-level O0\|O1\|O2] [--debug-ir] [--logical-input <path>] [--source-remap <remap.json>] [--diagnostics-json]` | Builds a package directory through the target package path. `--target` defaults to `auto`; `--output` currently defaults to `<input-stem>.cglb`; `--opt-level` defaults to `O1`. `--debug-ir` writes labeled pseudo-MLIR to `ir/pseudo-mlir.mlir`, keeps `ir/mlir.mlir` as a legacy alias with identical pseudo-MLIR contents, and writes the HIR pass trace to the non-manifest `ir/hir-pass-trace.json` sidecar. `--logical-input` changes debug source coordinates after the physical input file is loaded, and `--source-remap` can add original-source coordinates to package debug sidecars without changing the manifest source hash. Successful text mode prints the output path and resolved target. `--diagnostics-json` emits diagnostics JSON v1 on stdout. Planned or unsupported target/package paths return `1` with diagnostics and do not publish a completed package. |
| `cglc package inspect <out.cglb> --json` | Read-only package inspection. JSON is required in v0; omitting `--json` is a usage error. Success and failure both emit package inspect JSON v1 on stdout, with exit code `0` for valid packages and `1` for package read/format failures. |
| `cglc package verify <out.cglb> [--source <input.cgl>] [--json]` | Verifies package structure, manifest artifacts, source hash when `--source` is supplied, reflection, diagnostics, and optional debug IR artifacts. Text mode prints `verified package ...` on success. JSON mode emits package verify JSON v1 on stdout. Verification failures return `1`. |

## Next Compiler Hooks

The first optimization pass manager now sits after HIR construction and before
target capability analysis or backend emission. Each pass has a stable name and
reports whether it changed HIR, giving later optimization tracing, debug dumps,
and pass-level testing a concrete result model. The executed pass registry
can be inspected with `cglc dump-ir <input.cgl> --stage hir-pass-trace`, which
emits scheduled/executed pass counts, completion status, stop reason, and
per-pass names, indexes, changed flags, status, and diagnostic/error counts as
JSON. Trace accounting is self-consistent: `passCount` matches the `passes`
array length, the changed/diagnostic/error pass totals are derived from the
per-pass records, and per-pass module statistic `delta` values are the absolute
difference between the recorded before/after HIR counts. The trace also includes
an `optimizationPolicy` object with stable
`id`, `name`, `description`, and `backendInputMode` fields so consumers can
distinguish policy selection from the raw `optimizationLevel` label, plus a
`passSchedule` object with an `fnv1a64` fingerprint over the scheduled pass IDs
and a stability label for report-only drift detection. Like source HIR dumps,
the trace stage uses the source validation pipeline and records
`backendInputMode: "source-validation"` because it does not run the final
backend-input validation pass.
Named optimization levels (`O0`, `O1`, and `O2`) are accepted by check, dump,
and package build commands. `O0` selects validation-only HIR passes and disables
package target optimizer invocations that can be skipped safely, such as
Vulkan `spirv-opt`. `O1` is the default safe HIR cleanup/folding policy and
preserves the previous default build behavior. `O2` adds conservative safe
temporary inlining after the `O1` cleanup passes and before storage-buffer shape
validation:
`hir.optimize.o2.inline-scalar-temporaries` and
`hir.optimize.o2.inline-literal-vector-temporaries`.
`dump-ir --stage hir-pass-trace` records the selected optimization level,
stable optimization policy metadata, scheduled/executed pass count, and pass
names, so `O0`, `O1`, and `O2` produce distinct stable trace policies. These
HIR pass-policy claims are separate from target-native optimizer hooks and do
not claim performance parity or native-device execution.

The default registry currently
contains `hir.validate.module-shape`, a non-mutating validation pass that checks
backend-facing HIR invariants such as named modules, struct and constant
declaration shapes, valid stage names, resolvable stage entry points, unique
function definitions, resource name/type shapes, unique non-shared resource
bindings, function signature shapes, statement field shapes, loop header
structure, and fixed-arity expression shapes for
leaf/group/member/index/nonuniform/unary/binary/select nodes. It also validates
expression payloads such as identifier/literal text, member and callee names,
constructor result types, and parsed unary/binary operators, plus the
value-specific arity matrix for
texture sample, texture compare, and manual texture compare HIR nodes so later
transforms cannot hand malformed control flow or texture calls to a backend.
The follow-on `hir.validate.typed-symbols` pass checks post-pass type holes,
resource kind/type consistency, scoped identifier resolution across constants,
resources, parameters, and locals, scalar bool control-flow conditions when the
condition type is known, constructor and known-call result metadata, type-name
calls that should have been constructor expressions, known intrinsic arity,
target-neutral per-argument intrinsic domains and compatibility relationships,
and conservative declaration/assignment/return type compatibility. It deliberately
avoids duplicating source-backed unknown-type warnings, and skips raw-token
statement internals, symbolic manual texture-compare operations, image access
operands, and open-ended call resolution that still rely on target-aware
legalization.
Known generic call result metadata comes from the shared HIR intrinsic registry
used by both HIR construction and validation. The registry stores overload sets
by intrinsic name and resolves candidate signatures by arity, per-argument
domain checks, and compatibility rules before emitting a validation diagnostic,
so builtin result, arity, and per-argument validation knowledge does not diverge
between frontend inference and optimizer checks.
The `hir.optimize.fold-constant-intrinsics` pass then canonicalizes foldable
scalar intrinsic calls, scalar-result vector intrinsics such as `dot` and
vector `length`, and vector-valued intrinsics such as `normalize`, `reflect`,
and vector `mix`/`min`/`max` over exact-width constant constructor operands.
Scalar results become literals, while vector results become typed constructor
expressions with literal components. Logical `&&` and `||` are folded with
source-level short-circuit behavior when the folded left operand determines the
result, so dynamic right-hand expressions are not required for those cases. The
pass also tracks folded top-level vector constants internally so later
scalar-result intrinsics can consume names like `const vec3 AXIS` without
serializing vector `foldedValue` metadata yet. It updates top-level folded
constant values only when the rewritten expression becomes scalar-constant, and
deliberately leaves manual texture-compare kernel operands untouched so
reflection can keep its source-level static/dynamic weight classification.
The `hir.optimize.cleanup-constant-branches` pass then prunes `if` statements
whose conditions have become literal booleans. It removes dead arms, erases
constant-false branches with no `else`, and inlines selected branches only when
doing so cannot hoist direct local declarations or raw statements into a wider
scope. When a selected branch needs its scope preserved, the pass replaces the
branch with an explicit scoped HIR block around the live body.
The `hir.optimize.cleanup-unreachable-statements` pass then removes statements
that follow a guaranteed terminator in the same HIR block. Today that means
code after `return`, including code after an `if` whose then and else branches
both return. It recurses into nested blocks but does not treat loops as
terminating, because a loop body is not guaranteed to execute.
The `hir.optimize.cleanup-dead-local-declarations` and
`hir.optimize.cleanup-dead-local-stores` passes then remove local work that no
backend can observe. Declaration cleanup drops unused pure local declarations.
Store cleanup removes overwritten pure assignments to local identifiers and
clears pure declaration initializers when the variable declaration is still
needed but its initial value is dead. Declaration cleanup also drops standalone
expression statements when the full statement is proven pure. Both passes skip
raw-token regions and unparsed loop updates, and use the shared HIR side-effect
summary to remove only expressions proven to be pure. Their liveness collection
respects scoped blocks, branch-local declarations, and `for` initializer names
so a shadowed local in one lexical scope does not keep an unrelated same-named
outer declaration alive. Store cleanup uses pass-local binding IDs while walking
scopes, so overwritten stores in shadowed locals are pruned independently even
when an outer same-named local is live after the nested scope. Nested block and
branch cleanup returns binding-aware liveness to its parent, allowing
all-path overwrites to kill earlier stores without treating surviving assignment
targets as reads. Assignment-only `for` initializers are handled as single-run
stores before the loop condition, so dead initializer stores can be removed
while condition, body, update, and post-loop reads still feed conservative
liveness back to the parent. Store cleanup also optimizes locals declared inside
loop bodies with a protected outer-binding view: loop-body temporaries are
rewriteable, and incoming rewriteable outer bindings can be pruned when another
same-iteration store overwrites them before any post-loop, loop-update,
condition, or next-iteration body read can observe them. Next-iteration body
reads are collected as upward-exposed reads: a local read only protects a
previous-iteration store until the binding has been definitely written on every
path to that read. Branches merge definite writes by intersection, so all-arm
overwrites before a read can prune a trailing loop-carried store while missing
`else` arms and other partial overwrites remain protected. Loop body liveness
treats simple assignment targets as writes while still collecting reads from
assignment values and non-simple targets, so stores that feed the next
iteration remain protected. Loop initializer declarations are visible to
condition, body, and update read tracking through protected bindings, so pure
initializer values can be cleared only when the loop counter is not observed
after body cleanup. Parsed loop update
assignments treat simple identifier targets as writes while still collecting
reads from assignment values; non-simple update targets such as indexed writes
remain conservative because their target expressions can observe loop-carried
state. Pure stores in parsed loop updates can be removed when the assigned
binding is not read by the next condition check, the next body iteration,
later update operands, or post-loop code; when an update is rewritten, stale
source update tokens are cleared so textual and native backends consume the
same optimized HIR. When store cleanup changes a function, it reruns the
declaration cleanup and another store sweep until that local cleanup pair
converges, so declarations and follow-on stores exposed by removed update
assignments are also pruned in the same default pipeline run. Those follow-up
declaration removals are reported as part of the
`hir.optimize.cleanup-dead-local-stores` pass result. The loop declaration
itself and path-dependent outer loop-carried stores that can still reach a read
before an overwrite remain conservative until deeper loop-carried binding
liveness is modeled explicitly.
The side-effect summary resolves calls through the builtin-effect table,
distinguishes resource reads, resource writes, structural
`textureCompareKernel` builder calls, and unknown calls, and keeps those
non-pure forms.
The `hir.validate.storage-buffer-shapes` pass then delegates to the shared HIR
storage-shape helper to reject runtime-array fields that are not direct final
fields of a storage-buffer element struct, as well as recursive storage-buffer
element structs that cannot have finite layout. That keeps optimizations
target-independent by default, while still allowing later target-aware
legalization passes to run before a backend consumes HIR.

Native binary backends should continue to consume the post-optimization HIR and
return package-oriented build results rather than writing manifest/reflection
metadata themselves. The driver remains responsible for package composition so
artifact contracts stay identical across targets.
