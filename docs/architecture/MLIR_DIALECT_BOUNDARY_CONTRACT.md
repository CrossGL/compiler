# CrossGL MLIR Dialect Boundary Contract

<!-- mlir-boundary:contract-id=crossgl-mlir-dialect-boundary-v0 -->
<!-- mlir-boundary:status=report-only -->
<!-- mlir-boundary:production-linked=false -->
<!-- mlir-boundary:canonical-semantic-ir=C++ HIR -->
<!-- mlir-boundary:authority-anchors=include/crossgl/HIR/HIR.h|tools/cross_repo_language_contract.json|docs/language/crosstl-frontend-language-spec-v0.json -->
<!-- mlir-boundary:hir-namespace=hir -->
<!-- mlir-boundary:hir-operation-prefix=hir. -->
<!-- mlir-boundary:blocked-hir-namespace=crossgl. -->
<!-- mlir-boundary:allowed-dialects=hir|func|arith|scf|gpu|spirv -->
<!-- mlir-boundary:gate-option=CROSSGL_ENABLE_MLIR_EXPERIMENTAL -->
<!-- mlir-boundary:gate-default=OFF -->
<!-- mlir-boundary:gate-target=crossgl_mlir_experiment -->
<!-- mlir-boundary:requires-cmake-package=MLIR -->
<!-- mlir-boundary:fixture-source=experimental/mlir/fixture_inventory.json -->
<!-- mlir-boundary:source-inventory=experimental/mlir/CrossGLMLIRExperiment.cpp -->
<!-- mlir-boundary:allowed-fixtures=tests/fixtures/MinimalComputeShader.cgl|tests/fixtures/ScalarExpressionComputeShader.cgl|tests/fixtures/StorageBufferComputeShader.cgl|tests/fixtures/IfComputeShader.cgl -->
<!-- mlir-boundary:required-preservation=source_locations|source_map_debug_contracts|typed_hir_facts|stage_entry_points|resource_bindings|workgroup_size|target_legalization_facts|package_artifact_contracts -->
<!-- mlir-boundary:production-target-exclusions=crossgl_compiler|cglc -->
<!-- mlir-boundary:pseudo-mlir-must-remain-labeled=true -->
<!-- mlir-boundary:pseudo-sidecar-forbidden-real-dialect-markers=hir. -->
<!-- mlir-boundary:package-sidecar-fixtures=tests/mlir-package-sidecar-boundary -->
<!-- mlir-boundary:llvm-ir-canonical-shader-ir=false -->
<!-- mlir-boundary:blocked-use=backend_native_binary_gate_bypass|canonical_crossgl_shader_ir -->
<!-- mlir-boundary:graduation-stages=report_only|compile_gated_scaffold|dialect_verifier_parity|hir_parity_reports|backend_experiment|production_proposal -->

This contract is a compiler-facing boundary for the optional MLIR experiment. It
does not add a production lowering path and does not require an installed MLIR
toolchain. The anchors above are validated by
`tools/check_mlir_dialect_boundary_contract.py` and must stay aligned with
`experimental/mlir/experiment_manifest.json`,
`experimental/mlir/experiment_gate_followup.v0.json`,
`experimental/mlir/fixture_inventory.json`, and `CMakeLists.txt`.

## Boundary Rules

| Rule | Contract |
| --- | --- |
| Semantic IR authority | C++ HIR remains CrossGL's canonical semantic IR. Any real MLIR projection must be derived from `include/crossgl/HIR/HIR.h`, `tools/cross_repo_language_contract.json`, and `docs/language/crosstl-frontend-language-spec-v0.json`. |
| HIR dialect namespace | The only CrossGL HIR dialect namespace admitted by this experiment is `hir`, with operation names using `hir.*`. A competing `crossgl.*` HIR dialect namespace is blocked. |
| Experiment source dialect tokens | Files in `sourceInventory` must not introduce operation-like tokens from undeclared dialects. This keeps accidental `crossgl.*` or other unapproved dialect spellings out of the optional real MLIR experiment source before verifier work exists. |
| Allowed external dialects | Fixture-limited experiments may mention `func`, `arith`, `scf`, `gpu`, and `spirv` only when the HIR facts they carry remain anchored to the canonical C++ HIR inputs. |
| Build gate | Real MLIR experiment code is limited to the `crossgl_mlir_experiment` target and builds only when `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON` and `MLIR` is discovered by CMake. The option default is `OFF`. |
| Source inventory | The real MLIR source inventory is exactly `experimental/mlir/CrossGLMLIRExperiment.cpp`, mirrored in `CROSSGL_MLIR_EXPERIMENT_SOURCES` and `experimental/mlir/experiment_manifest.json` `sourceInventory`. The gate rejects package sidecar fixtures, package-relative `ir/*.mlir` sidecar names, verifier `.mlir` inputs, and pseudo-MLIR production surfaces as real MLIR source entries. |
| Scaffold source guard | `tools/check_mlir_scaffold_source_inventory.py` audits the compile-gated source inventory without discovering MLIR or invoking `mlir-opt`. It requires `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=OFF` to remain the default path, keeps scaffold sources under `experimental/mlir`, and rejects production headers, dialect registration APIs, or HIR-to-MLIR lowering entry points in the current declarative inventory source. |
| Fixture boundary | The admitted fixture set is exactly the fixture list in `experimental/mlir/fixture_inventory.json`: `tests/fixtures/MinimalComputeShader.cgl`, `tests/fixtures/ScalarExpressionComputeShader.cgl`, `tests/fixtures/StorageBufferComputeShader.cgl`, and `tests/fixtures/IfComputeShader.cgl`. |
| Source-location provenance | `experimental/mlir/boundary_inventory.v0.json` includes a report-only `hir.source_location_anchor` boundary row covering all admitted fixtures and requiring the common source-location facts `source_file`, `shader_module`, `compute_stage`, `entry_point`, `layout_local_size`, and `return_statement`. |
| Scalar comparison parity | `experimental/mlir/boundary_inventory.v0.json` keeps scalar comparison result typing as an explicit report-only `hir.scalar_compare` boundary row for `tests/fixtures/ScalarExpressionComputeShader.cgl`, rather than folding it into generic scalar expression coverage. |
| Fixture fact coverage | The manifest `boundaryFactCoverage` for each eligible fixture must mirror the fixture inventory's source-location facts, entry point identity facts, resource parity fields, target-independent resource metadata fields, target-independent type facts, and `sourceMapDebugFacts` before any real MLIR fixture projection is accepted. The derived source/resource catalog must also keep a `sourceResourceEntrypointPreservation` block proving those source, entry point, workgroup-size, resource-binding, and target-independent metadata fields are present together for each admitted compute fixture. The textual dialect projection catalog may outline future `hir.*` forms only as report-only, non-parser input with `registersDialect=false` and `emitsRealMlir=false`. Optional verifier input evidence must cite only facts inside that eligible fixture boundary coverage. |
| Verifier parity scaffold | The manifest `verifierParityScaffold` is report-only and must mirror each eligible fixture's `boundaryFactCoverage` sections for source locations, entry point identity, resource fields, target-independent resource metadata, target-independent type facts, and `sourceMapDebugFacts`. Any executable verifier use stays optional-tool gated by `CROSSGL_ENABLE_MLIR_EXPERIMENTAL=ON`, `MLIR_FOUND=TRUE`, and `mlir-opt`. |
| Required preservation | Before any MLIR output can become user-facing, the experiment must preserve source locations, `source_map_debug_contracts`, typed HIR facts, stage entry points, resource bindings, target-independent resource metadata, workgroup size, target legalization facts, and package artifact contracts for admitted fixtures. |
| Production isolation | `crossgl_compiler` and `cglc` must not depend on real MLIR experiment code. The manifest `productionIsolation` contract audits target sources, include paths, links, dependencies, and normal package output exclusions so `crossgl_mlir_experiment` and `experimental/mlir` cannot leak into production. Package schemas, production HIR, target legalization, and backend emitters remain outside this milestone. |
| Pseudo-MLIR boundary | Existing `dump-ir --stage mlir` behavior remains a compatibility alias for pseudo-MLIR and must stay labeled as pseudo-MLIR, not real MLIR, and not a registered MLIR dialect. The manifest `separationRules` keep pseudo-MLIR production files out of the real MLIR inventory. |
| Package sidecar evidence | `tools/check_mlir_package_sidecar_boundary.py` is MLIR-toolchain-free and checks both a normal debug package and package-shaped fixtures under `tests/mlir-package-sidecar-boundary`. Those fixtures prove that allowed production sidecar paths cannot carry real MLIR smoke markers, optional verifier/tool markers, or canonical `hir.*` dialect output while still being accepted as pseudo-MLIR aliases. |
| LLVM IR boundary | LLVM IR must not become CrossGL's canonical shader IR. It may only be considered as a target-owned or toolchain-owned artifact after shader ABI facts remain preserved by HIR and target legalization. |
| Release behavior gate | The manifest `releaseBehaviorGate` keeps real MLIR and LLVM artifacts from affecting release behavior until a production proposal proves source-map/debug preservation, native backend parity, fail-closed package evidence, and enabled/disabled MLIR coverage. The report-only source-map/debug evidence names `ir/debug-metadata.json`, `ir/hir-source-map.json`, schema versions, shared `hirSourceLocations`, and unfiltered/unpaged source-map state; pseudo-MLIR cannot satisfy this gate. |
| Graduation order | No experiment can skip directly to production. The required stage order is report-only, compile-gated scaffold, dialect verifier parity, HIR parity reports, backend experiment, and production proposal. |

## Milestone Use

This artifact answers one bounded v0 question: what must remain true before the
MLIR path can move from report-only evidence to fixture verifier work. It is not
a promise that MLIR will own optimization, target legalization, package output,
or backend-native binary production.
