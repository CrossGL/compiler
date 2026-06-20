# CrossGL Compiler Roadmap

This roadmap turns the architecture plan into execution milestones. It is meant
to guide coordinator and worker agents so that "keep going" batches expand
coverage deliberately instead of adding unrelated features.

## Milestone 0: Architecture Lock

Objective: make the design target explicit before more source work.

Deliverables:

- Architecture V2 document.
- Language and IR plan.
- Shared language spec extraction plan.
- Target toolchain plan.
- v0 support matrix definition.
- Agent ownership model for future batches.

Exit criteria:

- Docs are committed and validated.
- Future batches can cite a milestone and support-matrix row.
- Coordinator rejects worker tasks that do not map to a roadmap item.

## Milestone 1: v0 Alpha Contract

Objective: define the smallest coherent public compiler.

Deliverables:

- Extract the shared CrossGL language spec from CrossTL lexer, parser, AST,
  validation hooks, examples, and cross-repo contract fixtures.
- Frozen v0 feature subset for compute, vertex, and fragment.
- Stable diagnostics for unsupported source and target shapes.
- HIR verifier coverage for all v0 constructs.
- Package schemas marked stable for v0.
- Target package contracts regenerated and checked.
- Cross-repo language contract updated for v0 fixtures.

Exit criteria:

- `cglc check`, `dump-ir`, `explain-targets`, `doctor`, `build`, `package
  inspect`, and `package verify` are documented for v0 behavior.
- Every supported feature has support-matrix evidence.
- Every planned unsupported feature has a targeted diagnostic.
- Compiler and CrossTL frontend changes are tied to the same shared language
  spec and cross-repo contract.

## Milestone 2: Target Legalization Layer

Objective: stop spreading target policy across capability predicates and backend
string generation.

Deliverables:

- Shared legalization result model.
- Per-target legalization passes.
- Structured target ABI records before backend emission.
- Package decisions based on legalization output.
- Tests that prove rejected modules do not emit partial packages.

Exit criteria:

- Backends consume legalized HIR or target ABI records.
- `explain-targets`, `doctor --json`, debug metadata, and package builds agree
  on support decisions.
- Raw HIR statements cannot be claimed as supported by any backend predicate.

## Milestone 3: Native Package Maturity

Objective: make target package outputs trustworthy.

Deliverables:

- Metal: native `.metallib` packages for v0 compute and graphics subset.
- Vulkan: valid `.spv` packages for v0 compute and selected graphics subset.
- DirectX: HLSL source packages plus DXIL when `dxc` is available.
- OpenGL: GLSL source packages with validation status when `glslangValidator`
  is available.
- Debug sidecars for backend source, native binary, and target explanations.

Exit criteria:

- Native or validator-backed package evidence exists for all v0-supported
  target/feature combinations.
- Missing optional tools register skipped sentinels rather than disappearing
  tests.
- Package verification fails closed for missing, stale, or inconsistent
  artifacts.
- Vulkan target environment is recorded in package metadata and schema tests
  before any expansion beyond the current Vulkan 1.2 target.
- Tool-present validation failures for DXC or glslang block release promotion
  unless the affected shape is intentionally reclassified as unsupported by
  legalization.

## Milestone 4: Release and Provenance

Objective: make compiler packages shippable and auditable.

Deliverables:

- Release bundle signing or checksum manifest.
- Build provenance for compiler version, source commit, toolchain versions, and
  target profiles.
- Protected publish environment for remote artifact upload.
- Rollback and promotion plan for package release bundles.
- Report-only rollback/promotion provenance checklist covering dry-run safety,
  promotion decision evidence, rollback inputs, receipt preservation,
  release-scoped object prefixes, project/budget allowlist references, and
  lifecycle/retention review.
- Cross-platform validation of `package release` flows.
- Explicit GCP cost controls for any remote release or validation job,
  including dry-run default evidence, project and budget allowlist approval,
  explicit credential environment use, release-scoped object prefixes,
  lifecycle/retention expectations, and preserved audit receipts.

Exit criteria:

- A release bundle can be built, verified, published to a dry-run target, and
  rolled back without relying on ad hoc local files.
- Promotion and rollback decisions are auditable from preserved dry-run
  receipts, release-owner decisions, previous verified bundle inputs, and
  object generation evidence before any real binary shipment is approved.
- Live GCP operations are opt-in, project allowlisted, budget-limited,
  prefix-scoped, lifecycle/retention-reviewed, and auditable through preserved
  upload receipts.
- Package release metadata is schema-validated and reproducible.

## Milestone 5: Runtime Loader Prototype

Objective: prove `.cglb` is enough for source-free runtime admission and a
metadata handoff to future native API loaders.

Deliverables:

- Minimal CrossGL Runtime repository or `runtime/` package.
- Package reader for manifest, reflection, diagnostics, and target artifacts.
- Source-free directory and zip package admission.
- Target-neutral loader plans with deterministic `auto`, `native`, and
  `source-package` artifact selection.
- Metadata-only Metal and Vulkan native admission plans.
- DirectX emitted-DXIL and OpenGL validated-GLSL source-package admission.
- Loader contract summaries that expose source parsing, compiler invocation,
  and device execution requirements.

Exit criteria:

- Runtime does not parse CrossGL source.
- Runtime exposes package reflection for future resource binding.
- Runtime admission summaries report `compilerInvocationRequired: false` and
  `deviceExecutionRequired: false`.
- Runtime artifact selection rejects target-incompatible manifest sidecars, such
  as non-Vulkan `nativeProfile` entries, before loader dispatch.
- Compiler/runtime version compatibility is documented.
- Runtime compatibility reports explain accepted, rejected, and skipped
  packages from `.cglb` metadata and declared artifacts.
- Milestone 5 docs do not claim device execution or full graphics API object
  creation; that belongs to later runtime integration work.

## Milestone 6: Optimization and Performance Track

Objective: make the compiler produce artifacts that are competitive with
handwritten native shaders.

Deliverables:

- HIR pass tracing.
- Optimization levels: `-O0`, `-O1`, `-O2`.
- SPIR-V `spirv-opt` integration.
- DXC optimization flag policy.
- Metal compile option policy.
- Performance fixture corpus with source, generated artifacts, and expected
  package metadata.
- Microbenchmarks for storage buffers, texture sampling, descriptor arrays,
  storage images, atomics, and control flow.

Exit criteria:

- Performance regressions can be detected separately from functional failures.
- Debug builds can disable optimization for readable artifacts.
- Release builds use target compiler optimization settings consistently.

## Milestone 7: Real MLIR Experiment

Objective: introduce MLIR without destabilizing v0.

Deliverables:

- `CROSSGL_ENABLE_MLIR_EXPERIMENTAL` CMake option.
- Rename or clearly label the existing pseudo-MLIR dump before introducing real
  MLIR output.
- Minimal CrossGL MLIR dialect.
- HIR-to-MLIR lowering for a defined compute subset.
- MLIR verifier tests when MLIR is installed.
- Pseudo-MLIR textual dump renamed or clearly separated from real MLIR.

Exit criteria:

- MLIR tests are optional-tool gated.
- HIR remains canonical for production packages.
- MLIR fixture output preserves source locations, resources, entry points, and
  target-independent type information.

## Milestone 8: MLIR-Assisted Lowering

Objective: use MLIR where it provides clear compiler leverage.

Deliverables:

- MLIR canonicalization and CSE experiments.
- Lowering from CrossGL dialect to MLIR SPIR-V dialect for selected compute
  fixtures.
- Comparison tests against existing Vulkan output.
- Decision document on whether MLIR should replace specific HIR optimization or
  SPIR-V generation paths.

Exit criteria:

- MLIR path produces equal or better validation and package evidence for a
  meaningful subset.
- No production target loses support because of MLIR adoption.

## Milestone 9: CrossGL Language 1.0

Objective: graduate from compiler prototype to stable language.

Deliverables:

- Formal grammar.
- CrossTL frontend extraction audit for every grammar and AST claim.
- Type system specification.
- Resource and memory model specification.
- Layout specification.
- Target feature-gate specification.
- Compatibility and versioning policy.
- Conformance suite that external implementations could run.

Exit criteria:

- Source compatibility rules are documented.
- Package compatibility rules are documented.
- The compiler can emit a language/version feature report for each module.

## Agent Batch Policy

Every worker task should name:

- Milestone.
- Target or subsystem owner.
- Write scope.
- Expected tests.
- Handoff criteria.
- Explicit stop condition.
- Base SHA, branch, and worktree.
- Generated-file commands run.
- Shared schemas, contracts, support-matrix files, or CrossTL spec files
  touched.
- Rebase/merge status against current `origin/main`.

Suggested worker lanes:

- Frontend/HIR.
- Optimizer.
- Target legalization.
- Metal backend.
- Vulkan backend.
- DirectX backend.
- OpenGL backend.
- Package/schema/release.
- Toolchain/CI.
- Runtime prototype.
- Docs/spec/conformance.

Workers should stop when their assigned task is complete, blocked, or outside
the roadmap. They should not edit unrelated files to stay busy.

## Integration Gate

The coordinator can integrate only when:

- Worker handoff identifies exact commits and changed files.
- Worker handoff names base SHA, branch, worktree, generated-file commands, and
  touched shared contract files.
- Worktree is clean or dirty state is explained.
- Focused tests pass.
- Full local test gate appropriate to the batch passes.
- `pre-commit run --all-files` passes before pushing to `main`.
- Manual pre-commit hooks are run for release or generated-contract batches when
  those hooks cover the touched files.
- GitHub CI and cross-repo language contract are monitored after push.

If a worker-owned failure appears, the coordinator hands it back to the owner
instead of fixing that source code directly.

## Coordinator Batching Policy

This private repo should not spend GitHub Actions minutes on small serial
pushes. Before pushing, the coordinator runs the appropriate local CTest gate
and `pre-commit run --all-files`, holds work until there is a meaningful batch,
then monitors CI after the push. Any CI failure is routed to the worker or
subsystem owner responsible for the failing area.
Workflow timeout controls are part of that budget: stalled setup, package, or
native-toolchain jobs must fail bounded instead of becoming runaway Actions
runs.
