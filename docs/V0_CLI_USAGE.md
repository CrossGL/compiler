# CrossGL Compiler v0 CLI Usage

This page documents the public v0 `cglc` commands covered by the CLI surface
and contract tests. Examples use repository fixtures so they can be copied into
a configured build without depending on external CrossGL-Translator paths.
`tools/check_v0_release_gate.py` pins this page so public v0 commands keep a
command reference row, runnable example, JSON schema link when applicable, and
named CTest evidence.

Build the compiler first:

```sh
cmake -S . -B build -G Ninja -DCROSSGL_REQUIRE_PYTHON_TESTS=ON
cmake --build build --parallel
```

## Command Reference

| Command | Purpose | Primary test coverage |
| --- | --- | --- |
| `cglc doctor [--json] [input.cgl]` | Reports host toolchain status. With an input file, also reports target package decisions. | `cglc_cli_doctor_text_toolchain_contract`, `cglc_cli_doctor_json_toolchain_contract`, `cglc_doctor_json_schema_target_explanation` |
| `cglc targets` | Lists known compile targets. | `cglc_targets`, `cglc_cli_help_lists_major_commands` |
| `cglc check <input.cgl> [--opt-level O0\|O1\|O2] [--logical-input <path>] [--source-remap <remap.json>] [--diagnostics-json]` | Runs frontend, HIR construction, and diagnostics without building a package. | `cglc_cli_check_text_success_contract`, `cglc_cli_check_diagnostics_json_success_contract`, `cglc_diagnostics_json_schema_empty` |
| `cglc explain-targets <input.cgl> [--logical-input <path>]` | Emits target explanation JSON v1 for package support and target selection. | `cglc_cli_explain_targets_json_contract`, `cglc_explain_targets_json_schema`, `cglc_cli_explain_targets_logical_input_diagnostics` |
| `cglc dump-ir <input.cgl> [--stage <stage>] [--target <target>] [--opt-level O0\|O1\|O2] [--logical-input <path>] [--source-remap <remap.json>] [--source-map-schema-version 7\|8] [--hir-source-map-schema-version 7\|8]` | Dumps HIR, CrossGL text, pseudo-MLIR, backend text, debug JSON, HIR source-map JSON, or HIR pass-trace JSON. HIR source-map dumps emit schema 7 by default and opt into schema 8 with `--source-map-schema-version 8` or `--hir-source-map-schema-version 8`. | `cglc_cli_dump_ir_default_stage_hir_contract`, `cglc_cli_dump_ir_hir_pass_trace_contract`, `cglc_dump_hir_simple`, `cglc_dump_hir_source_map_schema_v8_cli_json_schema` |
| `cglc build <input.cgl> --target <target> --output <out.cglb> [--opt-level O0\|O1\|O2] [--debug-ir] [--logical-input <path>] [--source-remap <remap.json>] [--diagnostics-json]` | Builds a directory `.cglb` package for a concrete target or `auto`. | `cglc_cli_build_directx_source_package_success_contract`, `cglc_cli_build_vulkan_unsupported_diagnostics_json_contract`, `cglc_build_directx_source_package_logical_source_remap` |
| `cglc package inspect <out.cglb> --json` | Reads a package and emits package inspect JSON v1. JSON is required in v0. | `cglc_cli_package_inspect_json_success_contract`, `cglc_package_inspect_json_schema_source_package` |
| `cglc package verify <out.cglb> [--source <input.cgl>] [--json]` | Verifies package structure, manifest artifacts, source hash when supplied, reflection, diagnostics, and debug IR artifacts. | `cglc_cli_package_verify_text_success_contract`, `cglc_package_verify_json_schema_directx_source_package` |

Exit codes are part of the v0 surface: `0` means success, `1` means a source,
target, package, or verification failure, and `2` means usage or argument error.

## Ingest And Batch Boundary

The CLI consumes one CrossGL `.cgl` source file per command. CrossTL and other
orchestrators may generate that file, but serialized CrossTL AST/IR JSON is not
a v0 compiler input. In-process callers that already hold generated source text
can use the C++ `crossgl::SourceInput` APIs documented in
[COMPILER_INGEST_CONTRACT.md](COMPILER_INGEST_CONTRACT.md); package-producing
CLI builds remain file-based so manifest `sourceHash` verification has a real
compiler input file. Repository-level source discovery and batch manifests stay
outside `cglc` until a dedicated public batch schema is defined.
CrossTL project-portability reports, including project scan, translate,
validate, inspect, `sourceBackend`, and source-remap/report data, are
orchestrator artifacts for now. They can guide orchestrator calls to `cglc`,
but `check`, `language-feature-report`, `dump-ir`, and `build` still take the
generated `.cgl` input plus the compiler-owned `--logical-input` and
`--source-remap` sidecars; they do not accept a project-portability report as a
compiler build input.
Source-ingest commands reserve and reject manifest-like flags such as
`--source-manifest`, `--batch-manifest`, `--source-batch`, `--batch`, and
`--manifest` so repository build tools do not accidentally depend on ignored
arguments.

`--logical-input <path>` is available on `check`, `explain-targets`, `dump-ir`,
and `build` for generated single-file workflows. The compiler still reads
`<input.cgl>` from disk, but diagnostics, debug metadata, and HIR source maps
use the logical path after the bytes are loaded. For `build`, package
`manifest.sourceHash` and package verification still use the physical
`<input.cgl>` bytes. Coordinates still refer to the generated CrossGL input
text.
`--source-remap <remap.json>` can additionally attach optional
`originalLocation` spans to `check --diagnostics-json` and
`dump-ir --stage hir-source-map`. With `build --debug-ir`, it also attaches
`originalLocation` spans to package `ir/debug-metadata.json` and
`ir/hir-source-map.json`. File-backed remap inputs also emit
`manifest.artifacts.sourceRemap` pointing at `ir/source-remap-provenance.json`,
which records the input sidecar path, hash, and mapping summary without
changing `manifest.sourceHash`. The sidecar formats are documented in
[SOURCE_REMAP_SCHEMA.md](SOURCE_REMAP_SCHEMA.md) and
[SOURCE_REMAP_PROVENANCE_SCHEMA.md](SOURCE_REMAP_PROVENANCE_SCHEMA.md).

HIR source-map package sidecars remain schema 7 in v0, even when logical input
paths or source-remap `originalLocation` fields are present. Schema 8 is an
explicit `dump-ir` selector for the resource source-location lane, not the
default package artifact format.

## Release Gate Evidence

The v0 release gate treats these commands as the public alpha CLI surface:
`doctor`, `targets`, `check`, `explain-targets`, `dump-ir`, `build`,
`package inspect`, and `package verify`. A release candidate must keep each
command documented here, keep its CTest evidence name in the command table, and
keep the example command plus schema reference for every machine-readable JSON
contract.

## Unsupported and Usage Diagnostics

Unsupported source, target, package, and argument paths must keep stable
diagnostic or usage fragments. The release gate parses this table and verifies
that each cited CTest is registered in the configured build.

| Surface | Stable diagnostic or usage contract | CTest evidence |
| --- | --- | --- |
| top-level usage | No arguments print usage; unknown commands return a usage error naming the command. | `cglc_cli_no_args_prints_usage`, `cglc_cli_unknown_command_fails` |
| `cglc check --diagnostics-json` | Missing inputs emit diagnostics JSON with `io.read-failed`; invalid source bytes emit `io.invalid-source-byte`. | `cglc_cli_check_missing_input_diagnostics_json`, `cglc_cli_check_nul_source_diagnostics_json`, `cglc_cli_check_invalid_source_bytes_diagnostics_json` |
| source batch manifest flags | Source-ingest commands reject reserved compiler batch manifest flags with `cglc v0 is per-input`; orchestrators must invoke `cglc` once per source until a dedicated compiler batch schema is introduced. | `cglc_cli_doctor_batch_manifest_deferred`, `cglc_cli_check_batch_manifest_deferred`, `cglc_cli_explain_targets_batch_manifest_deferred`, `cglc_cli_language_feature_report_batch_manifest_deferred`, `cglc_cli_dump_ir_batch_manifest_deferred`, `cglc_cli_build_batch_manifest_deferred` |
| `cglc dump-ir` | Unknown stages return usage error `error: unknown dump stage` and list valid stages. | `cglc_cli_dump_ir_invalid_stage_fails` |
| `cglc build --diagnostics-json` | Missing build inputs print `cglc build <input.cgl>` usage; unsupported target/package combinations emit diagnostics JSON with `target.unsupported` and missing capability IDs. | `cglc_cli_build_missing_input_fails`, `cglc_cli_build_vulkan_unsupported_diagnostics_json_contract` |
| `cglc package inspect` | JSON is required in v0 and missing paths print `cglc package inspect <out.cglb> --json` usage. | `cglc_cli_package_inspect_requires_json`, `cglc_cli_package_inspect_missing_path_fails` |
| `cglc package verify` | Missing paths print `cglc package verify <out.cglb>` usage. | `cglc_cli_package_verify_missing_path_fails` |

## Examples

Inspect host/toolchain state:

```sh
build/cglc doctor
build/cglc doctor --json
build/cglc doctor --json tests/fixtures/SimpleShader.cgl
```

List targets and validate source:

```sh
build/cglc targets
build/cglc check tests/fixtures/SimpleShader.cgl
build/cglc check tests/fixtures/SimpleShader.cgl --opt-level O0
build/cglc check tests/fixtures/SimpleShader.cgl --diagnostics-json
build/cglc check generated.cgl --logical-input shaders/generated.cgl
build/cglc check generated.cgl --logical-input shaders/generated.cgl \
  --source-remap source-remap.json --diagnostics-json
```

Explain target package decisions:

```sh
build/cglc explain-targets tests/fixtures/SimpleShader.cgl
build/cglc explain-targets generated.cgl --logical-input shaders/generated.cgl
```

Dump public IR/debug views:

```sh
build/cglc dump-ir tests/fixtures/SimpleShader.cgl --stage hir
build/cglc dump-ir generated.cgl --stage hir-source-map --logical-input shaders/generated.cgl
build/cglc dump-ir generated.cgl --stage hir-source-map \
  --logical-input shaders/generated.cgl --source-remap source-remap.json
build/cglc dump-ir tests/fixtures/SimpleShader.cgl --stage pseudo-mlir
build/cglc dump-ir tests/fixtures/SimpleShader.cgl --stage backend --target directx
build/cglc dump-ir tests/fixtures/SimpleShader.cgl --stage debug
build/cglc dump-ir tests/fixtures/SimpleShader.cgl --stage hir-source-map
build/cglc dump-ir tests/fixtures/SimpleShader.cgl --stage hir-pass-trace --opt-level O0
build/cglc build generated.cgl --target directx --output out.cglb --debug-ir \
  --logical-input shaders/generated.cgl --source-remap source-remap.json
```

`--stage mlir` remains a compatibility alias for `pseudo-mlir`; its output is
not a real MLIR dialect.

`--opt-level` accepts `O0`, `O1`, or `O2` for `check`, `dump-ir`, and `build`.
The v0 default is `O1`, which runs the safe HIR cleanup/folding pipeline and
preserves the current conservative package toolchain behavior. `O0` runs
validation-only HIR plumbing so dumped HIR and pass traces remain close to
frontend output, and package builds avoid target optimizer passes where the
backend has an explicit optimizer hook. `O2` runs the `O1` HIR cleanup policy
plus conservative temporary inlining:
`hir.optimize.o2.inline-scalar-temporaries` and
`hir.optimize.o2.inline-literal-vector-temporaries`. Package target profiles
record the requested level and the target compiler or optimizer flag actually
used; the HIR optimization level is not native-device execution or performance
parity evidence.

Build, inspect, and verify a source package:

```sh
build/cglc build tests/fixtures/StorageBufferComputeShader.cgl \
  --target directx \
  --output build/StorageBufferComputeShader-directx.cglb \
  --debug-ir

build/cglc package inspect \
  build/StorageBufferComputeShader-directx.cglb --json

build/cglc package verify \
  build/StorageBufferComputeShader-directx.cglb \
  --source tests/fixtures/StorageBufferComputeShader.cgl \
  --json
```

## JSON Contracts

Machine-readable outputs use the public schema index in
[JSON_SCHEMAS.md](JSON_SCHEMAS.md):

- `check --diagnostics-json` and `build --diagnostics-json`:
  [DIAGNOSTICS_JSON_SCHEMA.md](DIAGNOSTICS_JSON_SCHEMA.md)
- `check --source-remap`, `dump-ir --stage hir-source-map --source-remap`, and
  `build --debug-ir --source-remap`:
  [SOURCE_REMAP_SCHEMA.md](SOURCE_REMAP_SCHEMA.md)
- `doctor --json`: [DOCTOR_JSON_SCHEMA.md](DOCTOR_JSON_SCHEMA.md)
- `explain-targets`: [TARGET_EXPLANATION_SCHEMA.md](TARGET_EXPLANATION_SCHEMA.md)
- `dump-ir --stage debug`: [DEBUG_METADATA_SCHEMA.md](DEBUG_METADATA_SCHEMA.md)
- `dump-ir --stage hir-source-map`:
  [HIR_SOURCE_MAP_SCHEMA.md](HIR_SOURCE_MAP_SCHEMA.md)
- `package inspect --json`: [PACKAGE_INSPECT_SCHEMA.md](PACKAGE_INSPECT_SCHEMA.md)
- `package verify --json`: [PACKAGE_VERIFY_SCHEMA.md](PACKAGE_VERIFY_SCHEMA.md)
