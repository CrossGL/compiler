# CrossGL Compiler v0 Readiness

Snapshot base: `ab79fd66f6ccc0ae83a37cd12d23c485c7895206`
(`Guard pseudo MLIR package sidecars`). This document is an
inventory and release gate for the current repository state. It is not a
support-matrix replacement and it should not be read as a promise that every
parsed CrossGL source form can be packaged for every target. v0 is not fully
released; the current work is Milestone 6 optimization and performance evidence
hardening on top of the metadata-only Milestone 5 runtime admission boundary.

## Snapshot Freshness Checklist

The v0 release meta-gate audits this checklist so the readiness snapshot cannot
silently drift back to pre-M6 evidence metadata.

- Snapshot base matches
  `ab79fd66f6ccc0ae83a37cd12d23c485c7895206`; older snapshot base metadata is
  stale for the current M6 readiness gate.
- Repository inventory cites 49 machine-readable schemas, 1201 invalid schema
  invalid fixture instances, 145 shared fixture records in the CrossTL language
  contract, a configured local build that registered 1975 CTests, and a
  portable configured-build floor of at least 1500 CTests for CI hosts where
  optional/native test registration differs.
- M6 native artifact evidence cites `cglc_native_artifact_contract`,
  `tools/check_native_artifact_contract.py`, `docs/NATIVE_ARTIFACT_CONTRACT.md`,
  `native-artifact-v0`, `manifest.artifacts.nativeArtifactDescriptor`,
  `.native-artifact.json`, `metadata/native-artifact.json`, and
  `tests/native-artifact-contract/evidence-rows.json`.
- M6 performance evidence cites `cglc_benchmark_build_modes`,
  `tools/check_benchmark_build_modes.py`, `tools/benchmark_build_modes.py`,
  `cglc_performance_corpus_runner`,
  `tools/check_performance_corpus_runner.py`,
  `tools/benchmark_performance_corpus.py`,
  `cglc_cli_dump_ir_hir_pass_trace_contract`,
  `cglc_optimizer_opt_level_o2_trace_has_distinct_pass`,
  `cglc_optimizer_opt_level_o0_trace_is_validation_only`,
  `hir-pass-trace --opt-level O2`,
  `cglc_performance_corpus_manifest`,
  `cglc_performance_corpus_manifest_self_test`,
  `tools/check_performance_corpus_manifest.py`,
  `cglc_performance_report_comparator`,
  `tools/check_performance_report_comparator.py`,
  `tools/compare_performance_reports.py`, `docs/PERFORMANCE_BENCHMARKS.md`,
  `tests/performance/performance_corpus_manifest.json`,
  `spirv-opt --target-env=vulkan1.2 -O`,
  `cglc_vulkan_spirv_opt_native_smoke_unavailable`,
  `debug.optimization.status=skipped-tool-missing`, and the
  advisory/report-only policy that still makes no native parity or performance
  thresholds claim.
- M6 package verify descriptor evidence cites
  `summary.nativeArtifactDescriptor`, `tools/check_package_verify_fixtures.py`,
  `docs/PACKAGE_VERIFY_SCHEMA.md`, nativeArtifactDescriptor health, and
  `optimizationEvidence` so verifier JSON reports retain descriptor optimizer
  evidence.
- M6 package reproducibility evidence cites
  `cglc_package_reproducibility`,
  `tools/check_package_reproducibility.py`,
  `build/package-reproducibility.json`, `metadataReportSha256`, and
  manifest sourceHash parity so deterministic package metadata stays first-class release
  evidence instead of only a standalone CTest.
- Conformance execution traceability cites
  `cglc_v0_conformance_manifest_execution`,
  `build/reports/conformance/manifest.v0.execution.json`, `--report-json`,
  `--skip-native-package-builds`, and the release-candidate report
  `--conformance-execution-report` input. The RC report summarizes that input
  through the `conformance-manifest-execution` local gate.
- Optional native package claims are fail-closed:
  tool-unavailable skipped evidence is not package-support evidence, and
  tool-present validation failures fail closed. Claimed evidence is the
  `native-tool-available` CTest lane; skipped evidence is the
  `native-tool-unavailable` sentinel lane. Runner/tool expectations are
  Ubuntu/macOS spirv-tools for Vulkan `spirv-as` / `spirv-val`, a host with
  dxc on PATH for DirectX, a host with glslangValidator on PATH for OpenGL,
  and a macOS runner with xcrun metal and xcrun metallib for Metal. The
  sentinel names are `cglc_vulkan_toolchain_native_smoke_unavailable`,
  `cglc_directx_toolchain_native_smoke_unavailable`,
  `cglc_opengl_toolchain_native_smoke_unavailable`, and
  `cglc_metal_toolchain_native_smoke_unavailable`.
- Target legalization local evidence cites
  `cglc_target_legalization_contract_audit`,
  `tools/check_target_legalization_contract_audit.py`,
  `cglc_doctor_target_explanation_alignment`,
  `tools/check_doctor_target_explanation_alignment.py`, and
  `targetLegalizationEvidence` so package, doctor, inspect, verify, and
  release-facing consumers stay aligned with the v0 result contract.
- M6 MLIR report-only evidence cites `cglc_mlir_experiment_manifest`,
  `tools/check_mlir_experiment_manifest.py`,
  `cglc_mlir_dialect_boundary_contract`,
  `tools/check_mlir_dialect_boundary_contract.py`,
  `cglc_mlir_op_type_catalog`, `tools/check_mlir_op_type_catalog.py`,
  `cglc_mlir_source_resource_catalog`,
  `tools/check_mlir_source_resource_catalog.py`,
  `cglc_mlir_fixture_parity_report`,
  `tools/check_mlir_fixture_parity_report.py`,
  `cglc_mlir_package_sidecar_boundary`,
  `tools/check_mlir_package_sidecar_boundary.py`,
  `cglc_mlir_optional_tool_evidence`,
  `tools/check_mlir_optional_tool_evidence.py`, and the
  `cglc_mlir_experiment_minimal_compute_verifier` sentinel while preserving the
  report-only/default-off MLIR boundary.

## Current Inventory

### Build, Packaging, and Test Harness

- The repository builds a C++20 `crossgl_compiler` library and `cglc` CLI from
  `CMakeLists.txt`.
- Install and CPack smoke coverage exists through
  `cmake/CrossGLInstallSmoke.cmake`, `cmake/CrossGLCPackSmoke.cmake`, and the
  `cglc_install_layout_smoke` / `cglc_cpack_layout_smoke` CTests.
- Milestone 5 runtime admission evidence is tracked as a local
  runtime admission/source-free loader inventory in
  `tools/check_v0_release_gate.py`. The gate checks runtime package-reader,
  loader, source-free loader example, and target-loader CTest registrations,
  source-free fixtures with manifest/reflection/diagnostics metadata and no
  `.cgl` source inputs, and structured admission visibility in loader summary
  fields. It also keeps the runtime native descriptor summary source-free:
  `sourcePathDeclared` is visible, but raw `sourcePath` is not exposed inside
  descriptor `fields`. This is metadata-only evidence; it does not execute real device code.
  It does not execute target shader compilers or full native runtime loaders.
- `.github/workflows/ci.yml` runs configure, build, and CTest on Ubuntu,
  macOS, and Windows, then runs focused native Metal and prototype Vulkan
  package smoke commands where the runner supports them.
- `.pre-commit-config.yaml` covers JSON/YAML/Markdown hygiene, critical Python
  checks, generated contract checks, schema index checks, and manual CMake/CTest
  hooks for release-grade local validation.

Local inventory from a Debug configure on this snapshot registered 1975 CTests
with Python-backed tests required. The same configure reported optional native
tool availability as `vulkan=TRUE`, `directx=FALSE`, `opengl=TRUE`,
`metal=TRUE` on the local macOS host; this varies by machine.

### Frontend, HIR, and Optimizer

- The shared compiler entrypoint is `crossgl::loadCompilerModule(...)` in
  `include/crossgl/Driver/CompilerPipeline.h`, documented in
  [COMPILER_PIPELINE.md](COMPILER_PIPELINE.md).
- Frontend implementation lives under `src/Frontend` and `include/crossgl/Frontend`.
  HIR construction, typing helpers, storage-shape checks, side-effect analysis,
  constant folding, and intrinsics live under `src/HIR` and
  `include/crossgl/HIR`.
- The default HIR pass pipeline is implemented in `src/Optimizer` and currently
  includes validation, intrinsic folding, constant branch cleanup, unreachable
  cleanup, dead local declaration cleanup, and dead local store cleanup.
- Milestone 6 performance evidence is in progress. The checked-in performance
  corpus, report comparator, pass-trace, optimization-level, and native
  optimization status checks are advisory/report-only evidence surfaces; they do
  not yet establish native parity or performance thresholds.
- The HIR pass-trace readiness surface names
  `cglc_cli_dump_ir_hir_pass_trace_contract`,
  `cglc_optimizer_opt_level_o2_trace_has_distinct_pass`, and
  `cglc_optimizer_opt_level_o0_trace_is_validation_only`. The Vulkan native
  optimizer surface names the O2-only `spirv-opt --target-env=vulkan1.2 -O`
  policy, `cglc_vulkan_spirv_opt_native_smoke_unavailable`, and
  `debug.optimization.status=skipped-tool-missing`; these remain metadata and
  advisory evidence, not native performance claims.
- The implemented HIR surface is broad enough for the existing fixture corpus:
  scalar/vector expressions, constructors, swizzles, structured `if`, `for`, and
  compiler-local `while`, resource discovery, descriptor arrays, texture/sample
  operations, storage buffers, storage images, atomics, and debug/source-map
  projection.
- The language-level contract remains narrower than the implementation.
  [docs/language/V0_SUPPORT.md](language/V0_SUPPORT.md) is the current v0 alpha
  language/support freeze point. The extracted CrossTL snapshot in
  [docs/language/crosstl-frontend-language-spec-v0.json](language/crosstl-frontend-language-spec-v0.json)
  remains the shared machine-readable inventory, not a full prose grammar.

### Backend and Target Surfaces

- Target and capability policy is implemented under `src/Backend` and
  `src/Driver/TargetExplanation.cpp`, with package-target contract data in
  `tools/package_target_contracts.json`.
- [package-targets.md](package-targets.md) is generated from the target contract
  data. It currently defines four package targets:
  `metal` and `vulkan` as native package targets, and `directx` / `opengl` as
  source-package targets with optional native or validation artifacts.
- `cglc explain-targets <input.cgl>` emits target explanation JSON v1. The same
  model feeds `doctor --json` target summaries and `build --target auto`
  selection.
- Metal emits MSL, AIR, and `.metallib` native packages when `xcrun metal` and
  `xcrun metallib` are available.
- Vulkan emits SPIR-V assembly and `.spv` native packages for the prototype
  supported subset, requiring `spirv-as` and `spirv-val`.
- DirectX emits HLSL source packages, and records DXIL when `dxc` is available.
- OpenGL emits GLSL source packages, and records validated source when
  `glslangValidator` is available.
- Optional native package claims are host-dependent: Vulkan claimed package
  evidence is `cglc_vulkan_toolchain_native_smoke` on Ubuntu/macOS spirv-tools
  hosts and proves the SPIR-V package is assembled, validated, reassembled, and verified;
  DirectX claimed package evidence is
  `cglc_directx_toolchain_native_smoke` on a host with dxc on PATH and proves
  `nativeBinaryStatus: "emitted"`; OpenGL claimed validation evidence is
  `cglc_opengl_toolchain_native_smoke` on a host with glslangValidator on PATH
  and proves `nativeBinaryStatus: "validated"`; Metal claimed package evidence
  is `cglc_metal_toolchain_native_smoke` on a macOS runner with xcrun metal
  and xcrun metallib and proves native package mode, `summary.nativeBinaryStatus: null`, and healthy native artifact descriptor evidence.
  Their unavailable sentinels are not package-support evidence.
- Unsupported target/module combinations are expected to fail with structured
  diagnostics and missing capability IDs instead of publishing partial
  completed packages.

### Package and JSON Contracts

- Public JSON contracts are indexed in [JSON_SCHEMAS.md](JSON_SCHEMAS.md).
  This snapshot has 50 machine-readable schemas under `docs/schemas`.
- Diagnostics JSON v1 is emitted by `cglc check --diagnostics-json`,
  `cglc build --diagnostics-json`, and package `diagnostics.json`.
- Package contracts include manifest, reflection, debug metadata, HIR source
  map, package inspect, package verify, recovery, maintenance, release bundle,
  publish plan, publish stage, upload manifest, and upload receipt documents.
- Schema negative coverage is substantial: this snapshot contains 1201 invalid
  schema fixture instances under `tests/schema-failures`.
- Package finalization verifies generated packages before reporting build
  success, and `cglc package inspect` / `cglc package verify` expose read-only
  integrity checks for consumers.
- Package reproducibility evidence is tracked as `cglc_package_reproducibility`
  and may be summarized in the release-candidate report through the
  `package-reproducibility` local gate when
  `build/package-reproducibility.json` is supplied.

### Cross-Repo Language Contract

- [docs/language/README.md](language/README.md) documents the current CrossTL
  frontend snapshot extraction workflow.
- `tools/cross_repo_language_contract.json` currently pins 145 shared fixture
  records with source, compiler HIR, and translator AST hashes.
- `.github/workflows/cross-repo-language-contract.yml` checks out
  `CrossGL/crosstl`, builds `cglc`, and runs
  `tools/check_cross_repo_language_contract.py`.

## Credible for v0

The following surfaces are credible v0 candidates because they have named code
paths, CLI exposure, schemas or fixture coverage, and CTest registration:

- The `cglc` command surface for `doctor`, `targets`, `check`,
  `explain-targets`, `dump-ir`, `build`, `package inspect`, and
  `package verify`, documented in [V0_CLI_USAGE.md](V0_CLI_USAGE.md).
  `tools/check_v0_release_gate.py` parses that command table plus its
  unsupported/usage diagnostics table and verifies the documented CTest
  evidence is present in CMake sources and registered in the configured build.
- The diagnostics JSON v1, target explanation JSON v1, manifest JSON v1,
  reflection JSON v1, package inspect JSON v1, and package verify JSON v1
  contracts.
- Directory `.cglb` package production for supported modules, including
  generated backend artifacts, reflection, diagnostics, manifest, source hash,
  and optional debug IR/source-map artifacts.
- Native Metal and Vulkan package evidence for the fixture-scoped supported
  subset when their toolchains are installed.
- DirectX and OpenGL source-package evidence for the fixture-scoped supported
  subset, with optional `dxc` / `glslangValidator` strengthening when present.
- Graphics entry-point ABI names are formalized as `{stage}_{sourceName}` for
  the current fixture evidence, but broader graphics ABI, resource lowering,
  and native lowering remain fixture-scoped/prototype readiness work.
- Target explanation and package target contract checks as the current
  automation surface for package-mode and capability decisions.
- Runtime loader admission for Milestone 5 source-free surfaces, scoped to the
  metadata-only boundary documented in `runtime/README.md`. The readiness gate
  verifies local inventory for `crossgl_runtime_loader`,
  `crossgl_runtime_source_free_loader_example`, target-loader tests, and
  structured admission fields such as `sourceParsingRequired`,
  `compilerInvocationRequired`, and `deviceExecutionRequired`. This is evidence
  for loader handoff/admission visibility, not a claim that Metal, Vulkan,
  DirectX, or OpenGL runtime objects are created.
- `dump-ir --stage pseudo-mlir` is the canonical textual HIR projection for
  MLIR-shaped debugging. The legacy `--stage mlir` spelling is retained only as
  a warned compatibility alias, and CLI help, dump headers, package sidecars,
  and tests label the output as pseudo-MLIR rather than a registered MLIR
  dialect. Real MLIR remains optional/experimental and report-only for v0
  readiness until explicitly enabled by the separate MLIR experiment track. The
  local CTest inventory now includes report-only manifest, dialect-boundary,
  op-catalog, source/resource-catalog, fixture-parity, package-sidecar-boundary,
  optional-tool-evidence, and minimal-verifier evidence for that track.
- Cross-repo compiler/translator fixture hashing as a drift detector, provided
  it remains run against current `CrossGL/crosstl` before v0 is cut.

## Blocking Gaps

These are blockers for a stable v0 claim, even though many individual features
already compile or package:

- The v0 language subset now has a first concrete freeze point in
  [docs/language/V0_SUPPORT.md](language/V0_SUPPORT.md). Before tagging v0, the
  page still needs a final cross-repo contract run against current CrossTL and
  any intentional divergences recorded there.
- Broad graphics support is not ready to claim. Entry-point ABI names are now
  formalized as `{stage}_{sourceName}`, but graphics package support still
  stays fixture-scoped while the full source-level graphics ABI, resource
  lowering, and native graphics lowering remain prototype work.
- Target-aware legalization is still identified by
  [ARCHITECTURE_V2.md](architecture/ARCHITECTURE_V2.md) as the biggest missing
  architecture layer. The v0 result contract, consumer audit, package-facing
  alignment, doctor alignment, contract audit, and read-only consumer checks
  now provide report-only local evidence, but production support decisions are
  still predicate-backed rather than owned by a complete legalization pipeline.
- Optional native tools make evidence host-dependent. v0 must define which
  checks are required on which runner, and tool-present validation failures for
  `spirv-val`, `dxc`, `glslangValidator`, or Metal tools must block affected
  support claims.
- The cross-repo language contract only proves the pinned fixture set. It does
  not replace a formal grammar, semantic spec, or compatibility policy.
- Release and publish flows have schemas and tests, and
  `tools/check_v0_release_gate.py` now pins the release bundle/provenance docs,
  install and CPack smoke registrations, schema index, CTest registrations, and
  the workflow/readiness matrix in
  [CI_READINESS_GATES.md](CI_READINESS_GATES.md), plus the operator-owned
  artifact policy in
  [RELEASE_ARTIFACT_POLICY.md](RELEASE_ARTIFACT_POLICY.md). v0 still needs a
  final operator sign-off on the exact artifact set before it ships binaries
  rather than just declaring compiler contracts.
- The offline release-candidate report surface in
  [V0_RELEASE_CANDIDATE_REPORT.md](V0_RELEASE_CANDIDATE_REPORT.md) and
  `tools/check_v0_release_candidate_report.py` summarizes local gate status,
  artifact policy evidence, provenance/checksum requirements, conformance
  manifest execution evidence from
  `build/reports/conformance/manifest.v0.execution.json`, source-free runtime
  status, and remaining operator sign-off fields. The report consumes that
  execution report with `--conformance-execution-report` and records it as the
  `conformance-manifest-execution` local gate. The report kind
  `crossgl-v0-release-candidate-report-v1` is explicitly report-only:
  generated records must keep `reportOnly: true`,
  `mode: "report-only"`, and `releaseStatus: "not-shipped"`, and the helper
  must not call GitHub, GCP, network services, credential helpers, or publishing
  commands. The report is indexed as
  `v0-release-candidate-report-v1.schema.json` so generated fields are
  machine-auditable and unexpected live-publish or network-looking fields fail
  closed. It must also fail closed if an approved readiness or promotion claim
  is missing dry-run receipt/preflight/upload-manifest evidence, reviewed
  project/bucket/budget guardrail references, provenance manifest evidence,
  artifact inventory evidence, or sign-off summary lists that match the
  per-control statuses.
- The release-gate traceability source of truth is the required-gate table in
  [CI_READINESS_GATES.md](CI_READINESS_GATES.md). Each row must keep stable evidence ids,
  required doc anchors, required command references, and cross-platform CI expectations
  aligned with the CMake/CTest registrations and workflow steps. The meta-gate
  pins those rows by anchor, including
  [cglc_v0_release_gate](CI_READINESS_GATES.md#v0-gate-cglc-v0-release-gate),
  [cglc_v0_conformance_manifest_execution](CI_READINESS_GATES.md#v0-gate-cglc-v0-conformance-manifest-execution),
  and
  [cglc_package_release_publish_flow](CI_READINESS_GATES.md#v0-gate-cglc-package-release-publish-flow).
- CI usage/cost traceability stays local/static for release-readiness handoffs.
  The meta-gate requires pre-push/pre-release evidence in
  [CI_READINESS_GATES.md](CI_READINESS_GATES.md): batched pushes,
  `pre-commit run --all-files`, manual pre-commit when requested,
  `tools/check_v0_release_gate.py --root .`, and
  `tools/check_v0_release_candidate_report.py --self-test`. The
  release-candidate report keeps `networkCalls`, `githubCalls`, `cloudCalls`,
  `credentialReads`, and `publishing` at `not-performed` so CI usage and cloud
  cost controls are auditable without adding more Actions.
- The same meta-gate now machine-audits the local readiness inventory for CI
  parallelism and release cost guardrails, cross-repo language authority, target
  legalization consumer audit and contract alignment, MLIR experiment,
  manifest, dialect-boundary, op/resource catalog, fixture-parity,
  package-sidecar, and optional-tool evidence gates, package inspect/verify
  fixture checks, native artifact contract checks, invalid schema fixtures, and
  performance comparator evidence, plus runtime admission/source-free loader
  inventory. These checks must stay registered in CMake and documented in
  [CI_READINESS_GATES.md](CI_READINESS_GATES.md), but they do not extend or
  change the native artifact contract itself or imply real device execution.
- `tools/check_v0_support_evidence.py` now gates the v0 language/support page
  so native-v0 support rows cite concrete fixtures, CTests, unit tests,
  conformance/HIR family trace tokens, compatibility row ids, or
  planned-failure evidence instead of batch-only prose. It also verifies that
  planned unsupported compatibility ids are bucketed as language, frontend, or
  target-legalization gaps rather than ambiguous native-v0 exclusions.

## v0 Exit Criteria

The v0 exit gate should be concrete and repeatable:

1. A v0 language/support page exists and links every supported source feature to
   CTest evidence in [SUPPORT_MATRIX_EVIDENCE.md](SUPPORT_MATRIX_EVIDENCE.md),
   conformance/HIR family trace evidence, or to an intentional planned-failure
   diagnostic.
   `tools/check_conformance_manifest.py` must also validate
   `tests/conformance/manifest.v0.json`, including fixture paths, command
   profiles, evidence tests, optional report-only target feature evidence
   tests, planned native-v0 diagnostics, required v0 feature/status coverage,
   and classified planned-unsupported versus target-metadata evidence. The
   local execution form must also emit
   `build/reports/conformance/manifest.v0.execution.json` through
   `--report-json` with `--skip-native-package-builds` so the
   release-candidate report can consume it through
   `--conformance-execution-report`.
2. `cglc` CLI behavior for the v0 public commands is documented in
   [V0_CLI_USAGE.md](V0_CLI_USAGE.md) and covered by CLI surface tests.
3. Public JSON schemas are indexed, schema-validated, and have negative fixture
   coverage.
4. Target package contracts are generated and checked; no hand-written target
   mode claim conflicts with `tools/package_target_contracts.json`.
5. Every v0-supported target/feature combination has package evidence:
   native package evidence for Metal/Vulkan, source-package evidence for
   DirectX/OpenGL, and validator/native status evidence when optional tools are
   present.
6. Every v0-unsupported but accepted source form returns a targeted diagnostic
   with a stable code and, where applicable, missing capability IDs. Public
   CLI/package usage errors and unsupported package paths must also keep named
   CTest evidence in [V0_CLI_USAGE.md](V0_CLI_USAGE.md).
7. CrossGL-Compiler and CrossTL pass the cross-repo language contract against
   current main branches, or any intentional divergence is recorded in the v0
   language/support page.
8. Install and CPack smoke tests pass from a clean configured build.
9. Runtime admission/source-free loader readiness remains visible in the local
   v0 release gate. Source-free loader surfaces must expose structured
   admission visibility for target match, required artifacts, source-package
   fallback, and no-source/no-compiler/no-device execution fields, while the
   release claim stays metadata-only until real native runtime execution exists.
10. The worktree passes `pre-commit run --all-files` before tagging or merging
   v0 readiness docs.

## Validation Commands

Recommended clean build gate:

```sh
cmake -S . -B build/v0 -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCROSSGL_REQUIRE_PYTHON_TESTS=ON
jobs="$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu)"
cmake --build build/v0 --config Release --parallel "${jobs}"
ctest --test-dir build/v0 --output-on-failure -C Release --parallel "${jobs}"
```

Focused contract gate:

```sh
python3 tools/check_v0_release_gate.py --root . --build-dir build/v0
python3 tools/check_v0_release_gate.py --self-test
python3 tools/check_release_artifact_policy.py --root .
python3 tools/check_v0_release_candidate_report.py --root . \
  --conformance-execution-report \
    build/v0/reports/conformance/manifest.v0.execution.json \
  --output build/v0-release-candidate-report.json
python3 tools/check_v0_release_candidate_report.py --self-test
python3 tools/check_v0_support_evidence.py --root .
python3 tools/check_conformance_manifest.py --root .
python3 tools/check_conformance_manifest.py --root . \
  --build-dir build/v0 \
  --ctest-config Release \
  --cglc build/v0/cglc \
  --work-dir build/v0/conformance/v0-manifest-execution \
  --report-json build/v0/reports/conformance/manifest.v0.execution.json \
  --skip-native-package-builds
ctest --test-dir build/v0 \
  -R 'cglc_(v0_conformance_manifest|release_artifact_policy|v0_release_gate|v0_release_candidate_report|v0_support_evidence_gate|json_schema_index|shared_json_schema_defs|cross_repo_contract_tool|package_target_contracts|package_target_contracts_generated|invalid_json_schema_fixtures|ctest_registration_health|fixture_registration|cli_|doctor|explain_targets|target_decision|package_inspect|package_verify|package_recover_fixtures|package_release_publish_flow|install|cpack)' \
  --output-on-failure -C Release --parallel "${jobs}"
```

Representative CLI/package smoke gate after building:

```sh
build/v0/cglc doctor --json
build/v0/cglc check tests/fixtures/SimpleShader.cgl --diagnostics-json
build/v0/cglc explain-targets tests/fixtures/SimpleShader.cgl
build/v0/cglc dump-ir tests/fixtures/SimpleShader.cgl --stage hir
build/v0/cglc dump-ir tests/fixtures/SimpleShader.cgl --stage debug
build/v0/cglc build tests/fixtures/VectorBufferComputeShader.cgl \
  --target directx \
  --output build/v0/VectorBufferComputeShader-directx.cglb \
  --debug-ir
build/v0/cglc package inspect \
  build/v0/VectorBufferComputeShader-directx.cglb --json
build/v0/cglc package verify \
  build/v0/VectorBufferComputeShader-directx.cglb \
  --source tests/fixtures/VectorBufferComputeShader.cgl --json
```

Native target gates are host/toolchain conditional:

```sh
build/v0/cglc build tests/fixtures/SimpleShader.cgl \
  --target metal --output build/v0/SimpleShader-metal.cglb --debug-ir
build/v0/cglc build tests/fixtures/VectorBufferComputeShader.cgl \
  --target vulkan --output build/v0/VectorBufferComputeShader-vulkan.cglb \
  --debug-ir
```

Cross-repo language gate, with a current CrossTL checkout:

```sh
python3 tools/check_cross_repo_language_contract.py \
  --translator-root /path/to/CrossGL-Translator \
  --compiler-root .
```

Local style and release-grade hooks:

```sh
pre-commit run --all-files
pre-commit run --hook-stage manual --all-files
```

Manual hooks run the configured CMake/CTest gate with parallel build/test
execution and are appropriate for release or generated-contract batches. For
docs-only updates, the non-manual
`pre-commit run --all-files` gate is the minimum.

## Milestone Ladder

### Current State

The repository is a credible v0 alpha candidate, not a finished v0 release: the
CLI, package format, schema contracts, target explanation surface, runtime
metadata admission, and fixture evidence are real and heavily tested. The
current readiness gap is final release discipline plus Milestone 6
optimization/performance evidence hardening, not a claim of full graphics API
object creation, device execution, or native performance parity.

### v0

Freeze the v0 language/support matrix, keep graphics claims fixture-scoped,
label pseudo-MLIR honestly, run the cross-repo language contract, and require
the full build/CTest/pre-commit gate for release. v0 should claim only the
feature/target pairs with package evidence and should list all accepted-but-
unsupported forms as planned diagnostics.

### v0.1

Move support decisions toward an explicit target legalization result, tighten
optional validator handling, expand the v0 language prose spec from the CrossTL
snapshot, and make release bundle/provenance validation part of the normal
handoff for published packages.

### v1.0

Publish a formal CrossGL language and compatibility spec, stabilize package and
source compatibility policies, promote target legalization to the single source
of target/package decisions, prove runtime consumption of `.cglb` packages, and
require conformance tests that external implementations could run.
