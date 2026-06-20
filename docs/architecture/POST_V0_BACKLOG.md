# CrossGL Post-v0 Backlog Index

This index is the first post-v0 planning slice. It does not add release gates,
support claims, or implementation requirements by itself. Use it to choose
future worker batches after the v0 alpha candidate is green.

The canonical milestone ladder remains [ROADMAP.md](ROADMAP.md). This page
adds ordering, risk notes, and practical batch boundaries for the next technical
work after the current v0 stabilization batch.

## Operating Rules

- Keep v0 stabilization separate from post-v0 expansion. A post-v0 task should
  not be merged into the release path unless it is explicitly scoped as a v0
  readiness fix.
- Every worker prompt should cite the roadmap milestone, touched docs/contracts,
  expected focused tests, and stop condition.
- Prefer small interface-expansion slices before moving broad backend behavior.
  Shared contracts should be reviewed before target-specific rewrites depend on
  them.
- Do not create new CI or release gates from this page. Promote a backlog item
  into a gate only through a dedicated gate-design task.

## Priority Order

| Priority | Backlog lane | Roadmap anchor | First useful output | Main risk |
| --- | --- | --- | --- | --- |
| P0 | Shared language spec formalization | [Milestone 1](ROADMAP.md#milestone-1-v0-alpha-contract), [Milestone 9](ROADMAP.md#milestone-9-crossgl-language-10) | Versioned prose/spec index generated from the CrossTL snapshot and compatibility ledger | Compiler and CrossTL drift into separate dialects |
| P0 | Target legalization expansion | [Milestone 2](ROADMAP.md#milestone-2-target-legalization-layer), [Language and IR Plan](LANGUAGE_AND_IR_PLAN.md#target-legalization) | A complete target legalization result contract that explains support, ABI facts, rewrites, and package mode | Backend predicates keep disagreeing with package/debug evidence |
| P1 | Runtime loader prototypes | [Milestone 5](ROADMAP.md#milestone-5-runtime-loader-prototype), [Architecture V2](ARCHITECTURE_V2.md#runtime-boundary), [runtime reader](../../runtime/README.md) | Minimal loader-facing API sketches and one target prototype that consumes `.cglb` without parsing source | Runtime starts duplicating compiler policy or assuming hidden source semantics |
| P1 | Performance thresholds | [Milestone 6](ROADMAP.md#milestone-6-optimization-and-performance-track), [Performance Benchmarks](../PERFORMANCE_BENCHMARKS.md) | Advisory baseline policy and threshold proposal based on existing report/comparator output | Host/tool variance turns performance checks into flaky release blockers |
| P2 | Real MLIR experiment | [Milestone 7](ROADMAP.md#milestone-7-real-mlir-experiment), [MLIR/LLVM plan](MLIR_LLVM_TOOLCHAIN_PLAN.md) | Optional MLIR build scaffold and fixture-limited HIR-to-MLIR experiment | MLIR migration distracts from HIR, legalization, and package correctness |

## Backlog Lanes

### Shared Language Spec Formalization

Current anchors:

- [Shared Language Spec Plan](SHARED_LANGUAGE_SPEC_PLAN.md)
- [Language and IR Plan](LANGUAGE_AND_IR_PLAN.md)
- [docs/language/README.md](../language/README.md)
- [docs/language/COMPATIBILITY.md](../language/COMPATIBILITY.md)
- [docs/language/crosstl-frontend-language-spec-v0.json](../language/crosstl-frontend-language-spec-v0.json)

Near-term worker slices:

- Convert the extracted CrossTL snapshot into a stable spec index that maps
  lexical grammar, grammar productions, AST nodes, semantic checks, and
  compatibility classifications to source files and contract fixtures.
- Add a drift-report review checklist for CrossTL parser changes. This should
  stay report-only until the team decides which drift classes block release.
- Split native-v0 unsupported forms into language-level, compiler-front-end,
  and target-legalization buckets so future work changes the right layer.
- Draft a CrossTL change policy for syntax tightening, deprecation, and source
  location requirements.

Stop conditions:

- Stop before changing accepted syntax, CrossTL behavior, compiler parser
  behavior, or conformance expectations unless the worker task explicitly owns
  that behavior change.
- Stop if the task would require editing both repositories without a paired
  cross-repo contract update.

### Target Legalization Expansion

Current anchors:

- [Architecture V2 target-aware legalization](ARCHITECTURE_V2.md#target-aware-legalization)
- [Language and IR Plan target legalization](LANGUAGE_AND_IR_PLAN.md#target-legalization)
- [Target Toolchain Plan](TARGET_TOOLCHAIN_PLAN.md)
- [MLIR/LLVM plan Gate 2](MLIR_LLVM_TOOLCHAIN_PLAN.md#gate-2-real-target-legalization)

Near-term worker slices:

- Audit current support decisions across `explain-targets`, `doctor --json`,
  package builds, debug metadata, reflection, and package verification. The
  first output should be a call-site map, not a rewrite.
- Expand the legalization contract so it can carry support state, target
  profile, package mode, diagnostics, rewrite IDs, ABI facts, optional tool
  requirements, and evidence IDs.
- Migrate one target/feature family at a time to consume legalization output.
  Good early candidates are source-package-only DirectX/OpenGL decisions and
  Vulkan native package preflight because their evidence is already explicit.
- Keep backend emitters focused on emitting target code from legalized facts.
  They should not become the place where source-level support is decided.

Stop conditions:

- Stop if a migration would remove current package evidence or weaken a
  package verifier failure.
- Stop if two targets need incompatible contract fields. Add a contract design
  task before continuing target-specific implementation.

### Runtime Loader Prototypes

Current anchors:

- [Architecture V2 runtime boundary](ARCHITECTURE_V2.md#runtime-boundary)
- [Roadmap Milestone 5](ROADMAP.md#milestone-5-runtime-loader-prototype)
- [runtime package reader prototype](../../runtime/README.md)

Current prototype state:

- `runtime.package_reader` exposes a package compatibility report that reads
  `.cglb` manifest, reflection, diagnostics, and declared artifact metadata
  without opening CrossGL source.
- `runtime.loader` exposes a target-neutral loader plan sketch for required
  artifact selection, reflection lookup, diagnostics handoff, and version
  compatibility.
- `runtime.loader` exposes a `metadataContract` loader-plan summary that
  enumerates the package metadata documents, manifest-declared artifact inputs,
  reflection inputs, and `sourceInputs: []` policy so CI can prove the prototype
  consumes package metadata without parsing source.

Near-term worker slices:

- Harden package compatibility reports against real package fixtures and
  schema evolution, keeping malformed package-contract fields as structured
  reject diagnostics instead of inferred loader behavior.
- Prototype one native-loader path first, preferably Metal on Apple hosts or
  Vulkan where SPIR-V tools are available. Keep device execution optional until
  a dedicated runtime test environment exists.
- Add examples only when they consume `.cglb` packages through the runtime
  boundary. Do not recompile source in the runtime sample.

Stop conditions:

- Stop if the prototype needs compiler-private HIR or parser APIs.
- Stop if a runtime task starts deciding target support instead of reading the
  package contract.

### Performance Thresholds

Current anchors:

- [Performance Benchmarks](../PERFORMANCE_BENCHMARKS.md)
- [Roadmap Milestone 6](ROADMAP.md#milestone-6-optimization-and-performance-track)
- [Target Toolchain Plan reference tools](TARGET_TOOLCHAIN_PLAN.md#reference-tools)

Near-term worker slices:

- Define a baseline policy for report files: toolchain versions, host labels,
  target profiles, opt level, case categories, skipped-tool accounting, and
  comparison window.
- Keep the first thresholds advisory. A worker can add threshold reporting and
  documentation without making CI fail on timing deltas.
- Promote structural failures before timing failures: missing cases, missing
  categories, missing command profiles, and invalid report shape should be
  harder failures than performance deltas.
- Add target-specific threshold proposals only after several reports exist for
  the same host/toolchain class.

Stop conditions:

- Stop before adding mandatory CI timing failures unless a separate stability
  study shows low variance.
- Stop if a threshold hides functional package failures behind benchmark
  runner behavior.

### Real MLIR Experiment

Current anchors:

- [MLIR and LLVM Toolchain Plan](MLIR_LLVM_TOOLCHAIN_PLAN.md)
- [Roadmap Milestone 7](ROADMAP.md#milestone-7-real-mlir-experiment)
- [Language and IR Plan IR layering](LANGUAGE_AND_IR_PLAN.md#ir-layering)

Near-term worker slices:

- Keep MLIR optional behind an explicit build flag. Non-MLIR builds remain the
  authoritative v0 and post-v0 path until fixture parity proves otherwise.
- Keep the existing pseudo-MLIR dump visibly separate before any real MLIR
  dialect output is user-visible: `dump-ir --stage pseudo-mlir` is the canonical
  textual HIR projection, legacy `--stage mlir` stays only a warned
  compatibility alias, and package sidecars remain labeled as not registered
  MLIR dialect output.
- Start with a fixture-limited CrossGL dialect experiment for compute-only HIR:
  entry point, scalar/vector types, resources, source locations, and structured
  control flow.
- Keep experiment sources under `experimental/mlir`, record the source and
  fixture inventory in CMake, and build the scaffold only when both the
  experimental flag and MLIR discovery are present.
- Use MLIR verifier tests only when MLIR is installed. The absence of MLIR
  should produce skipped optional-tool evidence, not missing test coverage.

Stop conditions:

- Stop before replacing production HIR, target legalization, package schemas,
  or direct Metal/DirectX/OpenGL/Vulkan emitters.
- Stop if MLIR output cannot preserve source locations and package-facing
  resource facts for the selected fixture subset.

## Suggested Batch Sequence

1. Spec index and drift audit: docs/tooling only, report-producing, no behavior
   changes.
2. Legalization contract audit and field proposal: C++ header/API design can
   follow only after the audit shows the shared shape.
3. Runtime loader API sketch plus package-reader compatibility tests.
4. Performance baseline policy and advisory threshold report mode.
5. Optional MLIR scaffold and fixture-limited dialect spike.

This order keeps language and support contracts ahead of implementation. It
also lets runtime, performance, and MLIR work consume stable package and
legalization facts instead of inventing parallel metadata.

## Worker Handoff Template

Future prompts for these lanes should include:

- Roadmap milestone and backlog lane.
- Branch/worktree base SHA.
- File ownership and forbidden areas.
- Expected output artifact: doc, report, API skeleton, fixture, or focused
  implementation.
- Focused verification commands.
- Whether cross-repo CrossTL coordination is in scope.
- Stop condition for unsupported source changes, optional-tool gaps, or target
  evidence conflicts.
