# CrossGL MLIR Experiment Scaffold

This directory is reserved for fixture-limited real MLIR experiments. Sources
here are not part of the production compiler library and must only compile
through the `crossgl_mlir_experiment` CMake target.

Current scope:

- Build gate: `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON` and MLIR discovered by
  `find_package(MLIR CONFIG QUIET)`.
- Fixture seed: `tests/fixtures/MinimalComputeShader.cgl`.
- Deterministic verifier input:
  `tests/fixtures/mlir/minimal_compute_builtin_module.mlir`, a checked-in
  builtin-MLIR module that carries minimal-compute metadata for the optional
  `mlir-opt --verify-diagnostics` CTest. It now carries explicit builtin
  metadata markers for the minimal fixture's source-location facts
  (`source_file`, `shader_module`, `compute_stage`, `entry_point`,
  `layout_local_size`, and `return_statement`) and the target-independent
  `void_entry_point` type fact. This is verifier fact-preservation input only,
  not a CrossGL dialect definition, HIR dialect registration, or production
  lowering.
- Scalar-expression fixture slice:
  `tests/fixtures/ScalarExpressionComputeShader.cgl`, which admits only
  straight-line local scalar declarations, arithmetic, constructor cast, and
  comparison facts. The boundary inventory tracks comparison result parity with
  a dedicated report-only `hir.scalar_compare` row so that comparison typing
  cannot be hidden inside generic scalar expression coverage.
- Resource-bearing fixture slice:
  `tests/fixtures/StorageBufferComputeShader.cgl`, which records only the
  existing compute local size, set/binding descriptor, and single non-array
  float storage buffer fact. This is inventory evidence only, not production
  MLIR resource lowering.
- Structured control-flow fixture slice:
  `tests/fixtures/IfComputeShader.cgl`, which records only the existing
  storage-buffer facts plus a single structured `if`/`else` branch with
  statement and branch-condition facts. This is inventory evidence only, not
  production MLIR control-flow lowering.
- Machine-readable inventory: `experimental/mlir/fixture_inventory.json`,
  which records the admitted fixture input, allowed HIR family, unsupported HIR
  families, required source-location/type/resource facts, source lineage, and
  gate expectations. Each fixture must cite CrossGL v0 source lineage through
  `docs/language/crosstl-frontend-language-spec-v0.json` and
  `tools/cross_repo_language_contract.json`, and must remain a checked-in,
  non-production fixture input rather than an anonymous MLIR seed. Resource
  metadata is recorded in
  `targetIndependentResourceMetadata` so set/binding, source type, element
  type, address space, and access facts stay separate from target ABI fields.
- Parity inventory: each admitted fixture has checker-enforced
  `parityRequirements` and `parityReportFields` derived from existing fixture
  data. The contract covers source locations, entry point identity, workgroup
  size, resource bindings, target-independent resource metadata, type facts,
  diagnostics/provenance, `sourceMapDebugPreservation`, control-flow slices,
  and blocked-family rationale. The source-map/debug preservation section is
  report-only evidence: it names the `ir/debug-metadata.json` and
  `ir/hir-source-map.json` artifact pair, debug-metadata schema v11, HIR
  source-map schema v7, the shared `hirSourceLocations`, unfiltered/unpaged
  source-map state, disabled combined records, and the fixture source/type facts
  that must survive before real MLIR output can graduate.
  Resource-free fixtures still list the empty descriptor, buffer, image,
  texture, sampler, and target-independent metadata fields that must remain
  empty; resource-bearing fixtures additionally list the descriptor,
  storage-buffer item, and target-independent metadata fields that a future real
  MLIR projection must preserve.
  The checker requires the `layout_local_size` source-location fact for every
  admitted compute fixture because each checked-in fixture declares
  `layout(local_size_x = 1, local_size_y = 1, local_size_z = 1)`.
- Source inventory: `CROSSGL_MLIR_EXPERIMENT_SOURCES` in `CMakeLists.txt` and
  the `sourceInventory` records in `experimental/mlir/experiment_manifest.json`
  must both name exactly `experimental/mlir/CrossGLMLIRExperiment.cpp`.
- Scaffold source inventory guard:
  `tools/check_mlir_scaffold_source_inventory.py` validates that the CMake and
  manifest source inventory match, that scaffold C++ sources stay under
  `experimental/mlir`, that the compile-gated macro fence is present, and that
  the source remains declarative inventory rather than a production HIR,
  backend, dialect-registration, or lowering dependency. The checker is
  report-only and does not discover MLIR, invoke `mlir-opt`, or change the
  `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=OFF` default path.
- Compile-gated scaffold inventory:
  `experimental/mlir/CrossGLMLIRExperiment.cpp` is a constexpr,
  verifier-oriented inventory source. It records the admitted compute entry
  points, required source-location fact names, target-independent type fact names,
  resource-free versus single-storage-buffer resource modes, the structured
  `hir.if` control-flow slice, the builtin-MLIR smoke input, and static
  assertions that the records remain production-isolated. It does not lower
  HIR, include production HIR or backend headers, register a dialect, or change
  the pseudo-MLIR printer.
- Verifier input inventory: `CROSSGL_MLIR_EXPERIMENT_VERIFIER_INPUTS` in
  `CMakeLists.txt` currently names exactly
  `tests/fixtures/mlir/minimal_compute_builtin_module.mlir`. This keeps the
  optional real-toolchain CTest path concrete without treating the checked-in
  verifier smoke input as a production lowering artifact.
- Verifier parity scaffold: `experimental/mlir/experiment_manifest.json`
  records report-only verifier evidence for each admitted fixture. The scaffold
  mirrors each fixture's `boundaryFactCoverage` sections for source locations,
  entry point identity, resource fields, target-independent resource metadata,
  target-independent type facts, and `sourceMapDebugFacts`. It is not an
  executable MLIR verifier yet; any executable use remains gated by
  `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON`, `MLIR_FOUND=TRUE`, and `mlir-opt`.
  Its real-MLIR file inventory must also name the generated op/type,
  source/resource, and textual projection catalogs plus their checkers, so
  report-only parity evidence cannot drift outside the decision contract.
- Lowering evidence: each admitted fixture carries report-only
  `loweringEvidence` for entry point identity, source-location expectation,
  resource mode, type facts, and control-flow category. The manifest mirrors
  this block from `experimental/mlir/fixture_inventory.json`; it is evidence
  for future HIR-to-MLIR parity, not a lowering implementation.
- Report-only experiment manifest:
  `experimental/mlir/experiment_manifest.json`, which separates legacy
  pseudo-MLIR text files from the future real MLIR experiment path, lists the
  eligible fixture paths, mirrors the fixtureInventory from
  `experimental/mlir/fixture_inventory.json`, records per-fixture
  `boundaryFactCoverage` for source locations, entry point identity, resource
  fields, target-independent resource metadata, and target-independent type
  facts plus `sourceMapDebugFacts`, and records which checks must remain
  optional-tool gated.
- Fixture-limited boundary inventory:
  `experimental/mlir/boundary_inventory.v0.json`, which records the admitted
  `hir.*` operation boundary, source-location/type/resource preservation
  fields, fixture coverage, and blocked fixture families without requiring MLIR
  or replacing pseudo-MLIR dumps. The report-only `hir.source_location_anchor`
  row requires every admitted fixture to preserve the common `source_file`,
  `shader_module`, `compute_stage`, `entry_point`, `layout_local_size`, and
  `return_statement` provenance facts explicitly instead of relying only on
  generic fixture coverage.
- Report-only op/type catalog:
  `experimental/mlir/op_type_catalog.v0.json`, generated by
  `tools/check_mlir_op_type_catalog.py --update` from the boundary inventory,
  fixture inventory, and experiment manifest. It records deterministic
  `hir.*` operation coverage plus target-independent HIR type facts for the
  admitted fixtures, with per-fixture required-fact matches. Its
  `fixtureUniverse` block requires every admitted fixture to appear in at
  least one operation coverage row and rejects operation rows that reference
  fixtures outside `fixture_inventory.json`. The checker is pure Python, does
  not require MLIR or `mlir-opt`, and fails if the committed catalog is stale
  or its schema/order changes unexpectedly.
- Report-only source/resource preservation catalog:
  `experimental/mlir/source_resource_catalog.v0.json`, generated by
  `tools/check_mlir_source_resource_catalog.py --update` from the boundary
  inventory, fixture inventory, experiment manifest, and op/type catalog. It
  records deterministic per-fixture entry-point identity, source-location
  evidence, target-independent type facts, source-map/debug preservation
  contract facts, resource-free versus single-storage-buffer resource modes,
  target-independent resource metadata, cross-catalog fixture/type consistency,
  cross-linked
  `sourceResourceEntrypointPreservation` fields, and parity-report fields. The
  cross-linked preservation block requires the source file, module, compute
  stage, entry point, local size source anchor, resource binding fields, and
  target-independent resource metadata fields to be present together for each
  admitted fixture. Its top-level `catalogConsistency` block requires the
  source/resource fixture universe, target-independent type facts, and op/type
  fixture coverage rows to match `op_type_catalog.v0.json`; its
  `parityCoverageMatrix` records covered versus missing fixture counts for
  source locations, entry point identity, resource bindings,
  target-independent resource metadata, source/resource/entry-point
  preservation, and source-map/debug preservation. The checker is pure Python,
  keeps optional MLIR tooling disabled, preserves pseudo-MLIR versus real-MLIR
  separation, and self-tests stale schema/order, catalog drift,
  missing-source-location, missing-entry-point, and missing-type-fact failure
  modes plus missing resource-binding and target-independent resource metadata
  failure modes.
- Report-only textual dialect projection catalog:
  `experimental/mlir/textual_dialect_projection.v0.json`, generated by
  `tools/check_mlir_textual_dialect_projection.py --update` from the boundary
  inventory, fixture inventory, and experiment manifest. It records a
  fixture-limited future `hir.*` textual operation skeleton, per-fixture
  source/resource preservation facts, resource-bound storage-buffer lines, and
  a verifier plan that remains `catalog-only-not-parser-input`. The checker is
  pure Python, rejects `crossgl.*` dialect drift, requires every boundary
  operation to match fixture facts, and keeps `registersDialect=false`,
  `emitsRealMlir=false`, `optionalMlirToolingRequired=false`, and
  `productionLinked=false`.
- v0 experiment gate follow-up:
  `experimental/mlir/experiment_gate_followup.v0.json`, which points at
  `docs/architecture/MLIR_LLVM_TOOLCHAIN_DECISION_V0.md` and records the
  report-only graduation evidence for when MLIR dialect work, LLVM IR
  emission, and backend-native binary experiments can advance.
- Optional verifier CTest:
  `tests/cmake/CrossGLMLIRExperimentTests.cmake` reads the deterministic
  builtin-MLIR fixture, requires the minimal source-location and
  `void_entry_point` fact markers, rejects pseudo-MLIR markers before invoking
  `mlir-opt`, requires `mlir-opt` output to preserve those builtin metadata
  markers, registers a stable `default-off` skip when
  `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=OFF`, reports `toolchain-unavailable`
  when MLIR or `mlir-opt` is missing, probes `mlir-opt --version` before
  registering the real verifier, and builds `crossgl_mlir_experiment` only
  when the MLIR gate, target, verifier input, and tool probe are available.
- Optional-tool evidence record:
  the MLIR CTest registration writes
  `mlir/optional_tool_evidence.v0.json` in the configured build tree and
  `tools/check_mlir_optional_tool_evidence.py` validates it without probing
  MLIR. The record captures the default and configured
  `CROSSGL_ENABLE_MLIR_EXPERIMENTAL` values, `MLIR_FOUND`,
  `crossgl_mlir_experiment` target creation, verifier input presence,
  `mlir-opt` discovery status, the CTest skip labels/regex used when MLIR is
  absent, and structured skip diagnostics with missing reasons plus
  `find_program` and `mlir-opt --version` probe-attempt flags. It also names the
  report-only source/resource catalog and required
  `sourceResourceEntrypointPreservation` fixture section, and carries an
  explicit default-off tool-probe policy proving the default-off verifier branch
  may not run `find_program` or `mlir-opt --version`. The same record also
  carries `verifierRegistration`: default-off and unavailable states must be
  `mode=skipped` with no `mlir-opt` invocation, no `--verify-diagnostics`, no
  experiment target build, and no required files; the available state must be
  `mode=executable` with `mlir-opt --verify-diagnostics`, the
  `crossgl_mlir_experiment` build target, and the builtin verifier input named
  as the only required file. The Python checker also validates that the
  checked-in verifier input and optional CMake harness retain the minimal
  fact-preservation markers.
- HIR dialect authority: any future real MLIR projection must use canonical HIR dialect catalog names and `hir.*` operation names. The experiment must not define a competing `crossgl.*` HIR dialect namespace.
- Dialect boundary contract:
  `docs/architecture/MLIR_DIALECT_BOUNDARY_CONTRACT.md` records the
  machine-checkable report-only boundary for canonical HIR authority, admitted
  dialects, fixture coverage, required preservation facts, production
  isolation, pseudo-MLIR labeling, LLVM IR limits, and graduation order.
- Fixture inventory validation: `CROSSGL_MLIR_EXPERIMENT_FIXTURES` in
  `CMakeLists.txt` must exactly match the admitted fixtures in
  `experimental/mlir/fixture_inventory.json`; this is inventory evidence only
  and does not register production lowering.
- Inventory drift reporting: the experiment gate reports fixture and source
  inventory entries that are missing from JSON and stale entries that no longer
  appear in the CMake authority lists, so optional MLIR coverage can be audited
  without enabling real MLIR builds.
- Fixture parity report hardening:
  `tools/check_mlir_fixture_parity_report.py` validates the report-only
  fixture contract without invoking MLIR, lowering HIR, or inspecting package
  outputs. It requires per-fixture `sourceFile`, `entryPoint`,
  `entryPointIdentity`, `localSize`, `workgroupSize`, `resourceBindings`,
  `typeFacts`, `diagnosticsProvenance`, `sourceMapDebugPreservation`,
  `controlFlowSlice`, `blockedFamilyRationale`, and `loweringEvidence`
  sections.
  `blockedFamilyRationale` must cite the top-level `unsupportedHirFamilies`
  ids and reasons, so broadening the fixture set must update either admitted
  facts or the blocked-family rationale.
- Package sidecar boundary validation:
  `tools/check_mlir_package_sidecar_boundary.py` builds one normal debug package
  when `--cglc` is supplied or `build/cglc` is discoverable; otherwise it
  validates the checked-in package-shaped boundary fixtures. It does not require
  an installed MLIR toolchain and rejects any `.mlir` package file except
  `ir/crossgl.mlir`, `ir/pseudo-mlir.mlir`, and the legacy `ir/mlir.mlir` alias.
  The pseudo-MLIR files must be identical, and all three allowed `.mlir`
  sidecars must carry explicit non-real MLIR markers, so production packages
  cannot start shipping real MLIR while the experiment remains gated.
- Unavailable evidence: CMake skip messages must report
  `CROSSGL_ENABLE_MLIR_EXPERIMENTAL`, `MLIR_FOUND`, and whether the
  `crossgl_mlir_experiment` target was created, so an absent MLIR install is a
  clean optional skip instead of a silent partial build.
- Production behavior: no HIR, target legalization, package schema, or backend
  emitter changes. The manifest `productionIsolation` rules require
  production targets to exclude `experimental/mlir` sources, include paths,
  links, and dependencies, and `productionPackageMustExclude` keeps
  `crossgl_mlir_experiment` and the `experimental/mlir` tree out of normal
  package outputs.
- Release behavior gate: the manifest `releaseBehaviorGate` keeps real MLIR and
  LLVM artifacts out of release behavior until a written production proposal
  provides source-map/debug contracts, native backend parity for Metal, Vulkan,
  DirectX, and OpenGL, fail-closed package evidence, and enabled/disabled MLIR
  coverage. Pseudo-MLIR cannot satisfy this gate.
- Pseudo-vs-real separation: the manifest `separationRules` require
  `pseudoMlirFilesMustNotBeRealMlirFiles=true`, keep the legacy `mlir` stage as
  pseudo-MLIR, and exclude `include/crossgl/IR/IRPrinter.h`,
  `src/IR/IRPrinter.cpp`, and `tools/cglc/main.cpp` from the real MLIR file
  inventory.

When MLIR is absent, CMake records the scaffold source and fixture counts but
skips the experiment target. The default build keeps
`CROSSGL_ENABLE_MLIR_EXPERIMENTAL=OFF`, so this directory has no effect on
normal `cglc` behavior or the pseudo-MLIR compatibility alias.

Eligible report-only fixture inputs:

| Fixture path | Experiment slice |
| --- | --- |
| `tests/fixtures/MinimalComputeShader.cgl` | Minimal compute entry point and source-location seed. |
| `tests/fixtures/ScalarExpressionComputeShader.cgl` | Straight-line scalar expressions and type facts. |
| `tests/fixtures/StorageBufferComputeShader.cgl` | Single set/binding storage-buffer resource fact. |
| `tests/fixtures/IfComputeShader.cgl` | Single structured `if`/`else` branch over the storage-buffer fixture shape. |

The manifest checker is report-only and requires no installed MLIR toolchain.
Any future verifier, `mlir-opt`, or dialect round-trip test must stay gated by
`CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON` and MLIR discovery, and must skip cleanly
when those optional tools are unavailable.
