# CI Readiness Gates

This document maps the local readiness commands to the gates that protect
`main`. Run the smallest gate that covers the files you changed, and run the
full affected gate set before pushing or merging to `main`.

## Local Build Root

The GitHub workflows use `build` as the CMake build directory. Use a clean
worktree or remove the local `build` directory before mirroring CI exactly.
When using another build directory, pass the matching `--cglc` path to helper
scripts that need a compiler binary.

## Required v0 Readiness Gates

Required before a v0 release candidate: these gates are the minimum release
readiness set that must remain visible in CMake, CI, and this document. The
meta-gate
`tools/check_v0_release_gate.py --root . --build-dir build --ctest-config Release`
checks this matrix, the source CMake registrations, and the workflow references
below; `tools/check_v0_release_gate.py --self-test` checks the checker itself.
The checks are deterministic/offline and must not call live cloud services or
the GitHub API.

The same meta-gate also machine-audits the newer local contract checks that
feed the v0 decision but should remain regular CTest/readiness inventory rather
than extra native artifact contract rules: CI parallelism and release cost
guardrails, cross-repo language authority, target legalization consumer audit,
package-facing legalization alignment, doctor target-explanation alignment,
target legalization contract audit, optional native validator policy, target
read-only consumer alignment, target capability registry, MLIR experiment
policy plus manifest, dialect-boundary, op/resource catalog, fixture-parity,
package-sidecar, and optional-tool report-only evidence, package
inspect/verify fixture checks, native artifact contract checks, invalid schema
fixtures, performance comparator evidence, and runtime admission/source-free
loader inventory.

The release-candidate report surface
`tools/check_v0_release_candidate_report.py` is a local report-only handoff
helper. It emits `crossgl-v0-release-candidate-report-v1` JSON with
`reportOnly: true`, `mode: "report-only"`, and
`releaseStatus: "not-shipped"` while summarizing local gate status, artifact
policy evidence, provenance/checksum requirements, source-free runtime status,
and remaining operator sign-off fields. It is not a CI trigger and must not
call GitHub, GCP, network services, credential helpers, or publishing commands.
Configured builds register it as the local CTests
`cglc_v0_release_candidate_report` and
`cglc_v0_release_candidate_report_self_test` for focused report generation and
checker self-test coverage. The report CTest consumes the
`cglc_v0_conformance_manifest_execution` output at
`build/reports/conformance/manifest.v0.execution.json` through
`--conformance-execution-report`, and records it as the
`conformance-manifest-execution` local gate.

The meta-gate also checks the Snapshot Freshness Checklist in
`docs/V0_READINESS.md`. The checklist keeps the snapshot base pinned to the
current M6 freshness floor, names `cglc_native_artifact_contract` /
`tools/check_native_artifact_contract.py`, names
`cglc_benchmark_build_modes` / `tools/check_benchmark_build_modes.py` /
`tools/benchmark_build_modes.py`, names `cglc_performance_corpus_runner` /
`tools/check_performance_corpus_runner.py` /
`tools/benchmark_performance_corpus.py`, names
`cglc_cli_dump_ir_hir_pass_trace_contract`,
`cglc_optimizer_opt_level_o2_trace_has_distinct_pass`,
`cglc_optimizer_opt_level_o0_trace_is_validation_only`, and
`hir-pass-trace --opt-level O2`, names
`cglc_performance_corpus_manifest` /
`cglc_performance_corpus_manifest_self_test` /
`tools/check_performance_corpus_manifest.py`, names
`cglc_performance_report_comparator` /
`tools/check_performance_report_comparator.py` /
`tools/compare_performance_reports.py`, links
`tests/performance/performance_corpus_manifest.json`, names the Vulkan O2-only
optimizer metadata evidence `spirv-opt --target-env=vulkan1.2 -O`,
`cglc_vulkan_spirv_opt_native_smoke_unavailable`, and
`debug.optimization.status=skipped-tool-missing`, and preserves the
advisory/report-only statement that M6 performance evidence is not yet a native
parity or performance-threshold claim. The checklist also names target
legalization local evidence through `cglc_target_legalization_contract_audit` /
`tools/check_target_legalization_contract_audit.py`,
`cglc_doctor_target_explanation_alignment` /
`tools/check_doctor_target_explanation_alignment.py`, and
`targetLegalizationEvidence`; and it names MLIR report-only evidence through
`cglc_mlir_experiment_manifest` / `tools/check_mlir_experiment_manifest.py`,
`cglc_mlir_dialect_boundary_contract` /
`tools/check_mlir_dialect_boundary_contract.py`,
`cglc_mlir_op_type_catalog` / `tools/check_mlir_op_type_catalog.py`,
`cglc_mlir_source_resource_catalog` /
`tools/check_mlir_source_resource_catalog.py`,
`cglc_mlir_fixture_parity_report` /
`tools/check_mlir_fixture_parity_report.py`,
`cglc_mlir_package_sidecar_boundary` /
`tools/check_mlir_package_sidecar_boundary.py`,
`cglc_mlir_optional_tool_evidence` /
`tools/check_mlir_optional_tool_evidence.py`, and
`cglc_mlir_experiment_minimal_compute_verifier`.

The runtime admission/source-free loader portion is metadata-only. It checks
that the local runtime package-reader, loader, source-free example, and
target-loader CTests stay registered; that source-free fixtures keep manifest,
reflection, and diagnostics metadata without `.cgl` source files; and that docs
and tests keep structured admission visibility through fields such as
`sourceParsingRequired`, `compilerInvocationRequired`, and
`deviceExecutionRequired`. It also guards the runtime-facing native descriptor
summary boundary: descriptor summaries expose `sourcePathDeclared` but do not
expose raw `sourcePath` inside descriptor `fields`. This gate does not run
Metal, Vulkan, DirectX, or OpenGL devices, does not invoke target shader
compilers, and does not prove full native runtime execution.

## Optional Native Package Claim Policy

Host-dependent package evidence is explicit and fail-closed. A
`native-tool-available` CTest is package-support evidence only on a runner with
the named tool installed; a `native-tool-unavailable` sentinel is skipped
evidence, and tool-unavailable skipped evidence is not package-support evidence.
When a tool is present, real compiler, validator, package
verification, or expected artifact/status failures are CTest failures, so
tool-present validation failures fail closed instead of becoming skipped
coverage.

| Target | Required runner/tools for claimed package evidence | Tool-present claimed evidence | Tool-unavailable skipped evidence |
| --- | --- | --- | --- |
| Vulkan | Ubuntu/macOS spirv-tools providing `spirv-as` and `spirv-val`; `spirv-opt` / `spirv-dis` remain metadata sidecars, not the base native gate. | `cglc_vulkan_toolchain_native_smoke` under `native-tool-available`; SPIR-V package is assembled, validated, reassembled, and verified. | `cglc_vulkan_toolchain_native_smoke_unavailable` under `native-tool-unavailable`; list with `ctest --test-dir build -N -L native-tool-unavailable`. |
| DirectX | host with dxc on PATH. The default Windows CI leg does not install `dxc`, so DXIL claims require a configured host that registers the tool-backed smoke. | `cglc_directx_toolchain_native_smoke` under `native-tool-available`; package verify reports `nativeBinaryStatus: "emitted"`. | `cglc_directx_toolchain_native_smoke_unavailable` under `native-tool-unavailable`; planned/source-package status is not native evidence. |
| OpenGL | host with glslangValidator on PATH. Default CI does not install `glslangValidator`; validated GLSL claims require a configured host that registers the tool-backed smoke. | `cglc_opengl_toolchain_native_smoke` under `native-tool-available`; package verify reports `nativeBinaryStatus: "validated"`. | `cglc_opengl_toolchain_native_smoke_unavailable` under `native-tool-unavailable`; planned/source-package status is not validated evidence. |
| Metal | macOS runner with xcrun metal and xcrun metallib. Non-Apple hosts must expose unavailable sentinels instead of silently dropping the lane. | `cglc_metal_toolchain_native_smoke` under `native-tool-available`; package verify reports native package mode, `summary.nativeBinaryStatus: null`, and healthy native artifact descriptor evidence. | `cglc_metal_toolchain_native_smoke_unavailable` under `native-tool-unavailable`; explicit unavailable evidence is not native evidence. |

| Required gate | Evidence id / anchor | Local command | Required registration or workflow anchor | CI expectation | Why it is required |
| --- | --- | --- | --- | --- | --- |
| `cglc_v0_release_gate` | <a id="v0-gate-cglc-v0-release-gate"></a>`v0-evidence-release-meta-gate` | `python tools/check_v0_release_gate.py --root . --build-dir build --ctest-config Release` | Explicit `.github/workflows/ci.yml` step plus CTest registration in `tests/cmake/CrossGLPythonTests.cmake` | CI: Ubuntu, macOS, and Windows via `.github/workflows/ci.yml` build-test matrix before the full CTest step. | Keeps the release docs, schema index, fixture helper references, CMake registrations, workflow references, and CTest inventory tied together. |
| `cglc_ctest_registration_health` | <a id="v0-gate-cglc-ctest-registration-health"></a>`v0-evidence-ctest-registration-health` | `python tools/check_ctest_registration.py --root . --build-dir build --ctest-config Release --metadata-only` | CTest registration in `tests/cmake/CrossGLPythonTests.cmake` | CI: Ubuntu, macOS, and Windows through `.github/workflows/ci.yml` full CTest. | Ensures required Python-backed tests are registered and their metadata is visible before relying on the broader CTest run. |
| `cglc_v0_support_evidence_gate` | <a id="v0-gate-cglc-v0-support-evidence-gate"></a>`v0-evidence-support-matrix-trace` | `python tools/check_v0_support_evidence.py --root .` | CTest registration in `tests/cmake/CrossGLPythonTests.cmake` | CI: Ubuntu, macOS, and Windows through `.github/workflows/ci.yml` full CTest. | Keeps `docs/language/V0_SUPPORT.md`, compatibility rows, conformance families, HIR evidence, and support-matrix evidence synchronized. |
| `cglc_v0_conformance_manifest` | <a id="v0-gate-cglc-v0-conformance-manifest"></a>`v0-evidence-conformance-manifest` | `python tools/check_conformance_manifest.py --root . --build-dir build --ctest-config Release` | CTest registration in `tests/cmake/CrossGLPythonTests.cmake` | CI: Ubuntu, macOS, and Windows through `.github/workflows/ci.yml` full CTest. | Verifies fixture paths, command profiles, evidence CTests, and planned native-v0 diagnostics for the conformance seed. |
| `cglc_v0_conformance_manifest_execution` | <a id="v0-gate-cglc-v0-conformance-manifest-execution"></a>`v0-evidence-conformance-manifest-execution` | `python tools/check_conformance_manifest.py --root . --build-dir build --ctest-config Release --cglc build/cglc --work-dir build/conformance/v0-manifest-execution --report-json build/reports/conformance/manifest.v0.execution.json --skip-native-package-builds` | CTest registration in `tests/cmake/CrossGLPythonTests.cmake`; consumed by the release-candidate report CTest through `--conformance-execution-report` | CI: Ubuntu, macOS, and Windows through `.github/workflows/ci.yml` full CTest. | Executes the conformance manifest entries with the local compiler, writes the JSON execution report, and keeps native package builds optional-tool/report-only for RC traceability. |
| `cglc_release_artifact_policy` | <a id="v0-gate-cglc-release-artifact-policy"></a>`v0-evidence-release-artifact-policy` | `python tools/check_release_artifact_policy.py --root .` | CTest registration in `tests/cmake/CrossGLPythonTests.cmake` | CI: Ubuntu, macOS, and Windows through `.github/workflows/ci.yml` full CTest. | Keeps the operator-owned v0 release policy, dry-run defaults, provenance, checksum, upload, promotion, and rollback controls explicit. |
| `cglc_release_provenance_manifest_self_test` | <a id="v0-gate-cglc-release-provenance-manifest-self-test"></a>`v0-evidence-release-provenance-manifest` | `python tools/check_release_provenance_manifest.py --self-test` | CTest registration in `tests/cmake/CrossGLPythonTests.cmake` | CI: Ubuntu, macOS, and Windows through `.github/workflows/ci.yml` full CTest. | Proves release provenance validation stays local, hashes staged artifacts, and requires explicit live-cloud opt-ins plus approval evidence. |
| `cglc_package_recover_fixtures` | <a id="v0-gate-cglc-package-recover-fixtures"></a>`v0-evidence-package-recovery-fixtures` | `python tools/check_package_recover_fixtures.py --root . --cglc build/cglc` | CTest registration in `tests/cmake/CrossGLPythonTests.cmake` | CI: Ubuntu, macOS, and Windows through `.github/workflows/ci.yml` full CTest. | Covers release bundle and bundle verification paths used by package recovery fixtures. |
| `cglc_package_release_publish_flow` | <a id="v0-gate-cglc-package-release-publish-flow"></a>`v0-evidence-package-release-publish-flow` | `python tools/check_package_release_publish_flow.py --root . --cglc build/cglc --work-dir build/package-release-publish-flow` | Explicit Linux/macOS step in `.github/workflows/ci.yml` plus CTest registration in `tests/cmake/CrossGLPythonTests.cmake` | CI: Ubuntu, macOS, and Windows through `.github/workflows/ci.yml` full CTest, plus an explicit Linux/macOS release-validation step with report upload. | Exercises local package set export, verification batch, release summary, promotion manifest, publish plan, staged/local/mock upload, dry-run GCS mode, and release provenance generation. |
| `cglc_package_inspect_artifact_inventory_runtime` | <a id="v0-gate-cglc-package-inspect-artifact-inventory-runtime"></a>`v0-evidence-package-artifact-inventory-runtime` | `python tools/check_package_artifact_inventory_runtime.py --root . --cglc build/cglc --jobs <jobs>` | CTest registration in `tests/cmake/CrossGLPythonTests.cmake` with `--jobs ${CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS}` and matching `PROCESSORS` | CI: Ubuntu, macOS, and Windows through `.github/workflows/ci.yml` full CTest; `CROSSGL_PACKAGE_ARTIFACT_INVENTORY_RUNTIME_JOBS` is set from the runner CPU count. | Keeps runtime-loadable package inspect artifact inventory paths required by the v0 meta gate without changing runtime package-reader behavior. |
| `cglc_package_reproducibility` | <a id="v0-gate-cglc-package-reproducibility"></a>`v0-evidence-package-reproducibility` | `python tools/check_package_reproducibility.py --root . --cglc build/cglc --report build/package-reproducibility.json`<br>`python tools/check_package_reproducibility.py --self-test` | CTest registration in `tests/cmake/CrossGLPythonTests.cmake` with `--jobs ${CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS}` and matching `PROCESSORS` | CI: Ubuntu, macOS, and Windows through `.github/workflows/ci.yml` full CTest; `CROSSGL_PACKAGE_REPRODUCIBILITY_JOBS` is set from the runner CPU count. | Keeps deterministic package metadata, path safety, manifest source hashes, inspect/verify summaries, native descriptor facts, and `metadataReportSha256` report digests as first-class v0 release evidence. |
| `cglc_v0_release_candidate_report` | <a id="v0-gate-cglc-v0-release-candidate-report"></a>`v0-evidence-release-candidate-report` | `python tools/check_v0_release_candidate_report.py --root . --build-dir build --ctest-config Release --conformance-execution-report build/reports/conformance/manifest.v0.execution.json --output build/reports/v0-release-candidate-report.json`<br>`python tools/check_v0_release_candidate_report.py --self-test` | CTest registrations `cglc_v0_release_candidate_report` and `cglc_v0_release_candidate_report_self_test` in `tests/cmake/CrossGLPythonTests.cmake`; depends on `cglc_v0_conformance_manifest_execution` | Local CTest inventory only; no explicit workflow trigger and no scheduled CI trigger. | Keeps the offline release-candidate report generation, `conformance-manifest-execution` local gate, and self-test discoverable without approving, publishing, or calling GitHub, GCP, network services, or credential helpers. |
| `cglc_install_layout_smoke` | <a id="v0-gate-cglc-install-layout-smoke"></a>`v0-evidence-install-layout-smoke` | `ctest --test-dir build --output-on-failure -C Release -R cglc_install_layout_smoke --parallel <jobs>` | CTest registration in `CMakeLists.txt` using `cmake/CrossGLInstallSmoke.cmake` | CI: Ubuntu, macOS, and Windows through `.github/workflows/ci.yml` full CTest. | Confirms the installed v0 package layout has the expected binary, CMake config, headers, and docs. |
| `cglc_cpack_layout_smoke` | <a id="v0-gate-cglc-cpack-layout-smoke"></a>`v0-evidence-cpack-layout-smoke` | `ctest --test-dir build --output-on-failure -C Release -R cglc_cpack_layout_smoke --parallel <jobs>` | CTest registration in `CMakeLists.txt` using `cmake/CrossGLCPackSmoke.cmake` | CI: Ubuntu, macOS, and Windows through `.github/workflows/ci.yml` full CTest. | Confirms the generated v0 source/package archive preserves the expected release layout. |

These gates are reached by standard CI because `.github/workflows/ci.yml`
configures with `CROSSGL_REQUIRE_PYTHON_TESTS=ON`, runs
`ctest --test-dir build --output-on-failure -C Release --parallel <jobs>`, runs
parallel CMake builds, sets `CMAKE_BUILD_PARALLEL_LEVEL` and
`CTEST_PARALLEL_LEVEL` from the runner CPU count, exposes the same count to
package inspect fixtures and runtime artifact inventory, runs
`pre-commit run --all-files` with `--jobs <jobs>` when the installed pre-commit
supports it, and has an explicit v0 release-gate step. The
cross-repository language half of the v0 readiness set is tracked in
`.github/workflows/cross-repo-language-contract.yml`.

## Gate Matrix

| Gate | Local command | GitHub gate | What it proves | Run before `main` when |
| --- | --- | --- | --- | --- |
| Standard CI configure, build, and CTest | `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCROSSGL_REQUIRE_PYTHON_TESTS=ON`<br>`cmake --build build --config Release --parallel <jobs>`<br>`ctest --test-dir build --output-on-failure -C Release --parallel <jobs>` | `.github/workflows/ci.yml` on Ubuntu, macOS, and Windows | The compiler builds, registered tests run, required Python-backed tests are present, package integrity fixtures pass, install/CPack smoke tests work, and platform-specific CTest skips are explicit. CI sets `CMAKE_BUILD_PARALLEL_LEVEL` and `CTEST_PARALLEL_LEVEL` from the runner CPU count, passes explicit `--parallel` values to CMake and CTest, and gives `cglc_package_inspect_fixtures` and `cglc_package_inspect_artifact_inventory_runtime` the same count as their internal worker count and CTest processor reservation. | Any compiler, CMake, test fixture, package, schema, or tool helper change. Docs-only changes can rely on pre-commit unless the docs describe executable behavior. |
| Cross-repo language contract | `cmake --build build --config Release --target cglc --parallel <jobs>`<br>`python tools/check_language_spec_index.py --root .`<br>`python tools/check_cross_repo_contract_tool.py --root .`<br>`python tools/check_cross_repo_language_contract.py --translator-root <CrossGL-Translator> --compiler-root . --cglc build/cglc` | `.github/workflows/cross-repo-language-contract.yml` on Ubuntu, macOS, and Windows | Current compiler fixtures and Translator examples still parse in Translator and produce the expected compiler HIR hashes recorded in `tools/cross_repo_language_contract.json`. CI sets `CMAKE_BUILD_PARALLEL_LEVEL` and `CTEST_PARALLEL_LEVEL` from the runner CPU count, checks the language spec index and PR720 support-reference fixture, then builds `cglc` with an explicit CMake `--parallel` value. Local inventory CTests `cglc_language_spec_index`, `cglc_cross_repo_contract_tool`, and `cglc_cross_repo_language_feature_spec` keep the report-only language index, helper surface, and shared feature-spec authority registered. | Any frontend grammar, HIR, source fixture, language spec, Translator compatibility, support-reference fixture, or contract manifest change. |

Push and pull-request cross-repo runs intentionally check CrossGL/crosstl
`main`. Manual `workflow_dispatch` runs may set `crosstl_ref` to an active
CrossTL branch or PR ref for preview-only drift review, but a preview failure
does not authorize refreshing the committed compiler snapshot until that
CrossTL ref becomes the agreed language authority.
| v0 support evidence | `python tools/check_v0_support_evidence.py --root .` | Included in standard CTest when `CROSSGL_REQUIRE_PYTHON_TESTS=ON`. | `docs/language/V0_SUPPORT.md` support tables cite concrete fixtures, CTest names, unit-test functions, compatibility row ids, or planned-failure evidence instead of batch-only prose; package-supported rows cite concrete tests; planned unsupported compatibility rows stay listed in the unsupported table. | Any language/support prose, support matrix, compatibility row id, fixture, or evidence test rename. |
| v0 conformance manifest | `python tools/check_conformance_manifest.py --root .`<br>`python tools/check_conformance_manifest.py --root . --build-dir build --ctest-config Release --cglc build/cglc --work-dir build/conformance/v0-manifest-execution --report-json build/reports/conformance/manifest.v0.execution.json --skip-native-package-builds`<br>`python tools/check_conformance_manifest.py --self-test` | Included in standard CTest when `CROSSGL_REQUIRE_PYTHON_TESTS=ON`; required by `tools/check_v0_release_gate.py` as `cglc_v0_conformance_manifest` and `cglc_v0_conformance_manifest_execution`. | The v0 conformance seed has valid fixture paths, classification buckets, command profiles, evidence CTests, planned native-v0 diagnostics for unsupported cases, and a local compiler execution report consumed by the release-candidate report. | Any v0 language/support claim, conformance manifest, CTest evidence name, planned unsupported diagnostic change, or conformance execution report wiring change. |
| v0 release readiness meta-gate | `python tools/check_v0_release_gate.py --root . --build-dir build --ctest-config Release`<br>`python tools/check_v0_release_gate.py --self-test` | Explicit step in `.github/workflows/ci.yml`; CTest `cglc_v0_release_gate`. | The required v0 release gates stay referenced by docs, CMake source registrations, workflow steps, schema indexes, fixture helper tokens, and CTest inventory. | Any readiness doc, workflow, release schema, release helper, CMake test registration, or v0 gate script change. |
| Pre-commit | `pre-commit run --all-files`<br>`pre-commit run --hook-stage manual --all-files` | `.github/workflows/ci.yml` on Ubuntu for the default pre-commit stage. CI discovers the runner processor count and passes `--jobs <jobs>` only when the installed pre-commit supports it. Manual hooks remain local because they configure, build, and run CTest in `build/pre-commit`; the manual CMake build and CTest hooks use `--parallel`. | Formatting and repository hygiene pass, JSON/YAML/TOML syntax is valid, critical Python syntax checks pass, schema indexes stay synced, generated package target contracts match, CTest registration self-tests still pass, and local manual build/test gates use available CMake/CTest parallelism. | Every change before committing or pushing to `main`. Run `pre-commit run --hook-stage manual --all-files` as the stricter coordinator gate before high-risk pushes. |
| Package schema checks | `python tools/check_json_schema_index.py --root .`<br>`python tools/check_shared_json_schema_defs.py --root .`<br>`python tools/check_invalid_json_schema_fixtures.py --root .`<br>`python tools/check_package_target_contracts.py --root .`<br>`python tools/generate_package_target_contracts.py --root . --check`<br>`python tools/check_package_target_contract_generator.py --root .` | Included in standard CTest when `CROSSGL_REQUIRE_PYTHON_TESTS=ON`; also partially covered by pre-commit for touched files. | Public JSON schema guides and machine-readable schemas are indexed, shared defs are valid, negative fixtures still fail as intended, and generated package target facts remain authoritative. | Any `docs/schemas`, `docs/schema-defs`, schema guide, JSON fixture, package target contract, or schema validator change. |
| Package fixture schema and integrity checks | `python tools/check_package_integrity_fixtures.py --root . --cglc build/cglc`<br>`python tools/check_package_inspect_fixtures.py --root . --cglc build/cglc`<br>`python tools/check_package_artifact_inventory_runtime.py --root . --cglc build/cglc --jobs <jobs>`<br>`python tools/check_package_recover_fixtures.py --root . --cglc build/cglc`<br>`python tools/check_package_verify_fixtures.py --root . --cglc build/cglc` | Included in standard CTest when `CROSSGL_REQUIRE_PYTHON_TESTS=ON`. | Package metadata, inspect, recover, and verify reports satisfy schema and semantic invariants, including required artifacts, path safety, source hashes, debug IR pairing, and runtime-loadable artifact inventory paths. The runtime inventory CTest passes the configured worker count through `--jobs` and reserves matching CTest `PROCESSORS`. | Any package writer, package reader, package schema, debug metadata, source-map, sidecar, or integrity validator change. |
| Package reproducibility evidence | `python tools/check_package_reproducibility.py --self-test`<br>`python tools/check_package_reproducibility.py --root . --cglc build/cglc --report build/package-reproducibility.json` | Included in standard CTest as `cglc_package_reproducibility` when `CROSSGL_REQUIRE_PYTHON_TESTS=ON`; the self-test is compiler-free. | Rebuilds source packages twice per required source target and checks native fixture packages twice, then compares deterministic metadata reports, JSON metadata, inspect/verify payloads, package inventory, backend source, path safety, artifact hashes, manifest source-hash evidence, manifest compiler identity, manifest-declared native descriptor path/byte/SHA-256 evidence, local `cglc` toolchain fingerprint, inspect provenance, and report digests. | Any package writer, package reader, package inspect, package verify, source-map, debug metadata, native fixture helper, or reproducibility checker change. |
| Optional native validators | `python tools/check_optional_native_validator_policy.py --root .`<br>`ctest --test-dir build --output-on-failure -C Release -L optional-native --parallel <jobs>`<br>`ctest --test-dir build -N -L native-tool-unavailable` | Included in standard CTest as `cglc_optional_native_validator_policy`; CI installs SPIR-V tools on Ubuntu/macOS and runs explicit Metal and Vulkan package smoke steps where available. The `ctest -N -L native-tool-unavailable` command is the list-only sentinel inventory tied to [Missing-Tool Sentinel Coverage](OPTIONAL_NATIVE_VALIDATORS.md#optional-native-missing-tool-sentinel-coverage). | Optional tool discovery is explicit, native-tool-backed tests run when tools exist, policy fake-tool failures fail closed, and missing `spirv-as`, `spirv-val`, `spirv-opt`, `dxc`, `glslangValidator`, `xcrun metal`, or `xcrun metallib` produce skipped or metadata evidence instead of silent coverage loss. `spirv-opt` is intentionally not part of the Vulkan native gate; missing optimization is surfaced through `debug.optimization.status=skipped-tool-missing` and `cglc_vulkan_spirv_opt_native_smoke_unavailable`. | Any backend native emission, target toolchain discovery, optional native CTest registration, or target package artifact behavior change. |
| CI parallelism and release cost guardrails | `python tools/check_ci_parallelism_contract.py --root .`<br>`python tools/check_release_cloud_guardrails.py --root .` | Included in standard CTest when `CROSSGL_REQUIRE_PYTHON_TESTS=ON`; release validation remains offline unless explicitly opted in. | `cglc_ci_parallelism_contract` keeps CMake, CTest, pre-commit, cross-repo, package fixture, and runtime inventory worker controls visible; `cglc_release_cloud_guardrails` keeps dry-run, local-only, mock, and live-cloud opt-in policy audited without invoking providers. | Any CI workflow, pre-commit hook, release upload, package publish, cloud guardrail, or cost-control change. |
| MLIR report-only evidence | `python tools/check_mlir_experiment_gate.py --root .`<br>`python tools/check_mlir_experiment_manifest.py --root .`<br>`python tools/check_mlir_dialect_boundary_contract.py --root .`<br>`python tools/check_mlir_op_type_catalog.py --root .`<br>`python tools/check_mlir_source_resource_catalog.py --root .`<br>`python tools/check_mlir_fixture_parity_report.py --root .`<br>`python tools/check_mlir_package_sidecar_boundary.py --root . --cglc build/cglc`<br>`python tools/check_mlir_optional_tool_evidence.py --root . --evidence build/mlir/optional_tool_evidence.v0.json` | Included in standard CTest as `cglc_mlir_experiment_gate`, `cglc_mlir_experiment_manifest`, `cglc_mlir_dialect_boundary_contract`, `cglc_mlir_op_type_catalog`, `cglc_mlir_source_resource_catalog`, `cglc_mlir_fixture_parity_report`, `cglc_mlir_package_sidecar_boundary`, and `cglc_mlir_optional_tool_evidence` when `CROSSGL_REQUIRE_PYTHON_TESTS=ON`; `cglc_mlir_experiment_minimal_compute_verifier` remains the optional verifier sentinel. | Pseudo-MLIR remains explicitly labeled, `--stage mlir` stays a compatibility alias unless `CROSSGL_ENABLE_MLIR_EXPERIMENTAL` is configured, doctor JSON schema exposes MLIR gate fields, the fixture-limited `experimental/mlir` source inventory is present but not linked into production, package sidecars stay pseudo-MLIR/not-registered unless the optional experiment owns them, optional MLIR tool evidence is report-only and records the option default/actual values, target/input state, skip metadata, and default-off no-probe proof, and docs do not describe LLVM IR as canonical CrossGL shader IR. | Any MLIR, LLVM, doctor schema, compiler pipeline, manifest sidecar, package sidecar, CLI stage, optional MLIR tool evidence, or architecture documentation change. |
| Target capability registry | `python tools/check_target_capability_registry.py --root .` | Included in standard CTest as `cglc_target_capability_registry` when `CROSSGL_REQUIRE_PYTHON_TESTS=ON`. | The checked-in target capability registry and guide table stay synchronized with target package facts without requiring native tools. | Any target capability, target explanation, package target contract, backend target support, or capability guide change. |
| Target legalization consumer audit | `python tools/check_target_legalization_consumer_audit.py --root .`<br>`python tools/check_package_target_legalization_alignment.py --root .`<br>`python tools/check_doctor_target_explanation_alignment.py --root .`<br>`python tools/check_target_legalization_contract_audit.py --root .`<br>`python tools/check_target_legalization_result_contract.py --root .`<br>`python tools/check_target_readonly_consumer_alignment.py --root . --cglc build/cglc` | Included in standard CTest as `cglc_target_legalization_consumer_audit`, `cglc_package_target_legalization_alignment`, `cglc_doctor_target_explanation_alignment`, `cglc_target_legalization_contract_audit`, `cglc_target_legalization_result_contract`, and `cglc_target_readonly_consumer_alignment` when `CROSSGL_REQUIRE_PYTHON_TESTS=ON`. | The P0 legalization consumer audit names every current driver/tooling package-decision consumer, each documented `path::token` reference still points at an existing file and symbol/token, package-facing inspect/verify/release artifact requirement rows stay aligned with target legalization package mode, doctor target explanation rows stay aligned with the same facts, target legalization contract references remain current, artifact/native-status requirements, diagnostics/evidence IDs, and fail-closed language stay synchronized, `targetLegalizationEvidence` remains visible in inspect/verify consumers, the report-only v0 result contract fixtures stay machine-checkable, and read-only package/inspect/diagnostic consumers stay aligned with target decisions. | Any target legalization, target capability, target explanation, doctor target explanation, package build, manifest artifact, debug metadata, reflection, package verification, package inspect, release-facing artifact requirements, or architecture documentation change. |
| Native artifact and schema contract checks | `python tools/check_native_artifact_contract.py --root .`<br>`python tools/check_invalid_json_schema_fixtures.py --root .`<br>`python tools/check_package_inspect_fixtures.py --root . --cglc build/cglc`<br>`python tools/check_package_verify_fixtures.py --root . --cglc build/cglc` | Included in standard CTest when `CROSSGL_REQUIRE_PYTHON_TESTS=ON`. | `cglc_native_artifact_contract`, `cglc_invalid_json_schema_fixtures`, `cglc_package_inspect_fixtures`, and `cglc_package_verify_fixtures` keep the native artifact descriptor contract, negative schema corpus, package inspect reports, and package verify reports covered as local readiness checks without changing the native artifact contract itself. | Any native artifact descriptor schema/semantics, invalid schema fixture, package inspect, package verify, manifest artifact, or package report change. |
| Runtime admission and source-free loader inventory | `python tools/check_v0_release_gate.py --root .`<br>`python tools/check_v0_release_gate.py --root . --build-dir build --ctest-config Release` after configuring CMake | Covered by the v0 release readiness meta-gate and by standard CTest inventory when a build directory is supplied. | The cheap local audit verifies `crossgl_runtime_package_reader`, `crossgl_runtime_loader`, `crossgl_runtime_source_free_loader_example`, and target-loader test registrations; source-free fixtures with manifest/reflection/diagnostics metadata and no `.cgl` source inputs; and structured admission visibility in loader summaries. It is metadata-only and does not run Metal, Vulkan, DirectX, or OpenGL devices or claim full native runtime execution. | Any runtime package reader, runtime loader, source-free fixture, loader admission doc, source-free example, target-loader sketch, or runtime admission summary change. |
| Performance comparator evidence | `python tools/check_benchmark_build_modes.py --root .`<br>`python tools/check_performance_corpus_runner.py --root .`<br>`python tools/check_performance_corpus_manifest.py --root .`<br>`python tools/check_performance_corpus_manifest.py --self-test`<br>`python tools/check_performance_report_comparator.py --root .` | Included in standard CTest as `cglc_benchmark_build_modes`, `cglc_performance_corpus_runner`, `cglc_performance_corpus_manifest`, `cglc_performance_corpus_manifest_self_test`, and `cglc_performance_report_comparator` when `CROSSGL_REQUIRE_PYTHON_TESTS=ON`; benchmark execution stays in the focused performance helpers. | `tools/benchmark_build_modes.py`, `tools/benchmark_performance_corpus.py`, `tests/performance/performance_corpus_manifest.json`, `tools/compare_performance_reports.py`, and the checker CTests prove build-profile, corpus, report-shape, comparison semantics, native descriptor optimization evidence summaries, producer-declared advisory policy/readiness provenance, and advisory evidence handling are registered in the local readiness inventory without requiring a cloud or long-running benchmark in the v0 meta-gate. The evidence remains advisory/report-only and does not make a native parity or performance-threshold claim. | Any benchmark build profile, performance corpus manifest, corpus runner, performance report schema, comparator, native descriptor optimization evidence, advisory threshold, producer readiness/policy provenance, or evidence-report change. |
| Release artifact policy audit | `python tools/check_release_artifact_policy.py --root .`<br>`python tools/check_release_provenance_manifest.py --self-test` | Included in standard CTest when `CROSSGL_REQUIRE_PYTHON_TESTS=ON`; required by `tools/check_v0_release_gate.py`. | The operator-owned release policy names the publishable v0 artifact set, dry-run default, provenance and checksum requirements, promotion/rollback receipt preservation, rollback/promotion provenance planning checklist, release schema surfaces, no implicit credential discovery, project/budget allowlist placeholders, release-scoped object prefixes, lifecycle/retention expectations, preserved upload receipts, and pre-push/pre-release validation commands. The provenance manifest checker self-test proves source commit, toolchain summary, local artifact path, SHA-256, `cloudUpload.mode`/`cloudUpload.modes`, mode-specific guardrail flags, and live-cloud opt-in plus approval evidence checks remain offline. | Any release policy, release schema, publish helper, package verification, provenance, upload, or cloud guardrail change. |
| Release candidate report surface | `python tools/check_v0_release_candidate_report.py --root . --output build/reports/v0-release-candidate-report.json`<br>`python tools/check_v0_release_candidate_report.py --root . --package-reproducibility-report build/package-reproducibility.json --conformance-execution-report build/reports/conformance/manifest.v0.execution.json --output build/reports/v0-release-candidate-report.json`<br>`python tools/check_v0_release_candidate_report.py --self-test` | Local CTests `cglc_v0_release_candidate_report` and `cglc_v0_release_candidate_report_self_test`; no explicit workflow or scheduled CI trigger. | Summarizes local gate status, package reproducibility evidence through the `package-reproducibility` local gate, conformance execution evidence through the `conformance-manifest-execution` local gate, artifact policy evidence, provenance/checksum requirements, source-free runtime status, and remaining operator sign-off fields in `crossgl-v0-release-candidate-report-v1` JSON while preserving `reportOnly: true`, `mode: "report-only"`, `releaseStatus: "not-shipped"`, and no GitHub/GCP/network/credential/publishing actions. | Any release readiness report, release policy, provenance/checksum, package reproducibility evidence, conformance execution report wiring, source-free runtime admission, or operator sign-off documentation change. |
| Release and package validation | `python tools/check_package_release_publish_flow.py --root . --cglc build/cglc --work-dir build/package-release-publish-flow` | Explicit Linux/macOS step in `.github/workflows/ci.yml`; reports are uploaded as `package-maintenance-*`. | Package set export, verification batch, release summary, promotion manifest, bundle verification, publish plan, stage publish, local publish, GCS dry run, upload preflight, mock upload, fake-gcloud upload, and dry-run release provenance manifest generation all satisfy their schemas and success contracts. The helper also emits `package-release-publish-guardrails.json` to record dry-run, mock, and local-only cloud modes. | Any package maintenance, release, promotion, bundle, publish, upload, target descriptor, or release schema change. |

## Failure Handback

Hand back failures with the failing command, platform, first failing test or
helper label, and the smallest artifact path that explains the failure. Do not
rewrite unrelated lanes while fixing a gate.

| Failure surface | Owner lane |
| --- | --- |
| Parser diagnostics, Translator parse failures, HIR hash changes, or contract manifest drift | Frontend/HIR language contract owner. If intentional, ask that lane to update `tools/cross_repo_language_contract.json` after validating both repositories. |
| Backend source, SPIR-V, Metal, DirectX, OpenGL, or target feature mismatches | Target backend owner for the affected target. Include the fixture, selected target, emitted artifact path, and native tool availability. |
| Package manifest, reflection, diagnostics, inspect, verify, recover, sidecar, or debug IR integrity failures | Package metadata owner. Include the package directory and validator output. |
| JSON schema index, schema semantics, negative fixture, or generated package target contract failures | Schema/tooling owner. Include the schema file, fixture, and helper script that failed. |
| Optional native tool discovery or missing/available sentinel behavior | Toolchain/CTest owner. Include the CMake configure summary and `ctest -N -L optional-native` output. |
| MLIR experiment gate, pseudo-MLIR labels, `mlir` alias warnings, or LLVM IR canonicality claims | MLIR/toolchain policy owner. Include `python tools/check_mlir_experiment_gate.py --root .` output and the file/line named by the audit. |
| Release publish flow, upload manifest, target descriptor, GCS dry-run, or package maintenance batch failures | Release/package validation owner. Include `build/package-release-publish-flow` artifacts and the failing flow label. |
| Pre-commit formatting, whitespace, JSON/YAML/TOML syntax, or critical Python check failures | Author lane for the touched files, unless the failure is in a shared hook. |

## Batched CI Usage Traceability

Release and CI usage evidence is local/static unless a coordinator explicitly
asks for a push. Record pre-push/pre-release evidence before spending private
GitHub Actions minutes: hold changes until there is a meaningful batch, run
`pre-commit run --all-files`, run
`pre-commit run --hook-stage manual --all-files` for stricter coordinator
handoffs, run `tools/check_v0_release_gate.py --root .` for release-readiness
changes, and run `tools/check_v0_release_candidate_report.py --self-test` for
report contract changes, then push once.

The release-candidate report provides the auditable offline boundary without a
new workflow. Its `offlineBoundary` block must keep `networkCalls`,
`githubCalls`, `cloudCalls`, `credentialReads`, and `publishing` as
`not-performed`; this is the no-live-network/no-GCP/no-publish evidence for
the handoff. CI cost reporting remains local/static and report-only: do not
query live billing data, GitHub organization setting values, provider cost
APIs, or cloud budget APIs from readiness paths. Stop and hand back the
request if a real billing query or organization setting read is required. Its
`ciUsageCostGuardrailEvidence` block must keep
`githubActionsRunsTriggered: "not-performed"`, require batched pushes,
coordinator approval, one push after local validation, and explicit local
evidence placeholders for `pre-commit run --all-files`,
`pre-commit run --hook-stage manual --all-files`, and
`ctest --test-dir build --output-on-failure -C Release --parallel <jobs>`.
Coordinator and private GitHub Actions budget-owner sign-off placeholders stay
empty until a release owner records local evidence paths and identities. The
report CTests remain local inventory only, with no explicit workflow trigger
and no scheduled triggers. Normal release-readiness evidence must not set
`CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD=1`.

## Main Push Rule

Before pushing directly to `main`, run `pre-commit run --all-files` and every
gate whose "Run before `main` when" condition matches the change. The main CI
workflow enforces the default pre-commit stage on Ubuntu, so failures there
should be fixed before retrying the push. For a cross-lane integration, run
standard CI, cross-repo language contract, manual pre-commit hooks, optional
native validators, and the release/package validation helper from a clean build.

For coordinator batches in this private repository, do not spend GitHub Actions
minutes on small serial pushes. Hold changes until there is a meaningful batch,
run the full affected local gate set first, including `pre-commit run
--all-files` and local CTest coverage for executable changes, then push once
and monitor CI. If CI fails, route the failure to the owning lane with the
failing command, platform, and artifact path instead of retrying unrelated
workflow edits.

## Cloud Cost Guardrails

GitHub Actions cost controls are part of the readiness contract for this
private repository. CI workflows must keep push/PR cancellation,
least-privilege workflow `permissions` with only `contents: read`, bounded
`timeout-minutes` on every job, `fail-fast: false` on OS matrix jobs, and no
scheduled triggers by default.
Matrix CI coverage is bounded to the required Ubuntu, macOS, and Windows legs;
extra matrix axes or OS entries need a documented budget owner before they can
join the default private-repo contract.
The workflow-level `concurrency` group and `cancel-in-progress` expression
limit Push/PR cancellation to superseded automatic runs for the same workflow
and branch or pull request. Manual `workflow_dispatch` validation runs are
grouped by their run id and must not be canceled by later branch updates.
Uploaded CI artifacts must set short `retention-days` values so smoke-package
evidence does not silently inherit longer repository defaults. Successful pull
request runs should not upload routine evidence artifacts; keep uploads for
`main` pushes and manual validation runs, where missing expected evidence
remains an error, and for failed pull request runs only when the artifact was
generated and helps route the failure. Expensive native or package validation
should stay on push/PR path filters or explicit `workflow_dispatch` runs unless
a future maintainer documents the exception and its budget owner. The
cross-repo language contract must keep identical `push` and `pull_request` path
filters so one automatic event cannot accidentally run the full external OS
matrix for unrelated changes.

Release validation is offline by default. GCS coverage in
`tools/check_package_release_publish_flow.py` must stay dry-run, mock, or
local-only through the fake `gcloud` shim unless a maintainer intentionally opts
in to a live cloud upload. Future live cloud release code must call the
guardrail helper in that tool before invoking provider CLIs or SDKs.
Normal CI, pre-commit, and release validation must not replace provider CLIs
with direct HTTP cloud access; `tools/check_release_cloud_guardrails.py`
statically rejects release-validation `curl`, `wget`, PowerShell web cmdlets,
Python HTTP/cloud client imports, and Google API endpoint strings.
The same static guardrail rejects common live publish commands and actions such
as package registry publishing, GitHub release publishing, Google cloud auth
Actions, and live GitHub billing or organization setting queries. Any future
cost report for Actions or cloud usage must stay local/static/report-only until
a coordinator records separate approval outside the default readiness path.

The release provenance manifest checker,
`tools/check_release_provenance_manifest.py`, hashes local staged files and
summarizes the guardrail record; it must not invoke `gcloud`, cloud SDKs, or
network uploads. Live cloud modes in a manifest or guardrail file require the
same explicit opt-ins as upload helpers and a non-placeholder `approvalEvidence`
object naming the project/bucket allowlist, budget guardrail, release object
prefix, lifecycle policy, and audit receipt paths. Guardrail records must also
carry an operation label, a known mode, and mode-specific flags that agree with
`dry-run`, `local-only`, `mock`, or `live-cloud`.

The only accepted live-upload opt-ins are `--allow-cloud-upload` on the helper
or `CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD=1` in the environment. Normal CI,
pre-commit, and local readiness runs must not set either opt-in.

Release policy checks are report-only guardrails. They verify that the policy
names dry-run defaults, no implicit credential discovery, project and budget
allowlist decision points, release-scoped object prefixes, lifecycle and
retention expectations, preserved upload receipts, promotion/rollback receipts,
the rollback/promotion provenance planning checklist, and pre-push/pre-release
commands without reading credentials or invoking cloud provider commands.
