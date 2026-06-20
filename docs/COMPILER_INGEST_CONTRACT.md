# Compiler Ingest Contract

CrossGL-Compiler v0 ingests CrossGL source text. The stable
translator-to-compiler artifact is UTF-8 `.cgl` text that the compiler can
lex, parse, lower to HIR, optimize, and emit through the existing driver
surfaces.

## Artifact Boundary

- The official v0 handoff artifact is generated CrossGL `.cgl` source text.
  CrossTL/Translator may produce this text from another shading language, but
  the compiler consumes the generated CrossGL source as its input language.
- File-based CLI commands remain the package-producing surface:
  `cglc check <input.cgl>`, `cglc dump-ir <input.cgl>`,
  `cglc explain-targets <input.cgl>`, and
  `cglc build <input.cgl> --output <out.cglb>`.
- `cglc check`, `cglc explain-targets`, `cglc dump-ir`, and `cglc build` accept
  `--logical-input <path>` for
  generated single-file workflows. The compiler still reads the physical
  `<input.cgl>` path, then uses the logical path for diagnostics and source
  maps.
- `cglc check` and `cglc dump-ir --stage hir-source-map` accept
  `--source-remap <remap.json>` for generated-to-original source provenance.
  `cglc build --debug-ir` accepts the same sidecar for package debug metadata
  and HIR source-map artifacts. The sidecar follows
  [SOURCE_REMAP_SCHEMA.md](SOURCE_REMAP_SCHEMA.md).
- The C++ driver API also exposes `crossgl::SourceInput`, which pairs generated
  source bytes with a logical path for in-memory `checkSource`,
  `loadCompilerModuleFromSource`, `dumpIR`, and `explainTargets` calls.
- The compiler does not consume serialized CrossTL AST, CrossTL helper nodes,
  or a separate CrossTL IR JSON as HIR truth in v0.
- CrossTL project-portability reports, including project scan, translate,
  validate, inspect, `sourceBackend`, and source-remap/report data, are
  orchestrator artifacts in v0. They may describe why an orchestrator invokes
  `cglc`, but they are not compiler build inputs and the compiler does not
  schema-validate them as a prerequisite for compiling source text.

## Source Identity

`SourceInput::logicalPath` and CLI `--logical-input` are compiler-input
identities used by diagnostics, HIR source maps, debug metadata, and target
explanation diagnostics generated from source text. They should be stable
repo-relative or orchestrator logical paths when possible. Source coordinates
still describe the generated CrossGL input text.

`--source-remap <remap.json>` adds optional `originalLocation` fields to
diagnostics JSON, HIR source-map JSON, and package debug metadata when a
generated span is covered by the sidecar. The required `location` field remains
the generated compiler-input coordinate space so existing package, editor, and
CI consumers keep a stable anchor.

`SourceInput::source` is the exact byte buffer validated by the compiler. The
same UTF-8 and embedded-NUL checks used for file inputs also apply to in-memory
inputs.

## Package Boundary

Package builds intentionally remain file-based in v0. `manifest.sourceHash`
hashes the compiler input `.cgl` text, and package verification compares that
hash with the source file supplied to `cglc package verify --source` or the
source path used by `cglc build`. In-memory package builds require a future
package-integrity extension that verifies source bytes without pretending a
virtual path is a readable file.

Debug packages continue to write source maps for compiler-input coordinates.
`build --debug-ir --source-remap` can add original-source coordinates to debug
sidecars, but the package manifest still records the physical compiler input
source hash and does not embed the remap sidecar payload. File-backed remaps
emit `manifest.artifacts.sourceRemap` pointing at
`ir/source-remap-provenance.json` so package inspect/verify can report the
remap input identity. HIR source-map schema v8 resource records remain opt-in
for `dump-ir`; package debug artifacts remain on the default schema documented
in [HIR_SOURCE_MAP_SCHEMA.md](HIR_SOURCE_MAP_SCHEMA.md).

## Repo And Batch Boundary

Compiler APIs are per-input. Repository-scale manifests, source discovery,
multi-file scheduling, and output-path fanout stay in translator or
orchestrator tooling until a dedicated compiler batch schema is introduced.
A future compiler-owned batch mode must define per-input diagnostics, source
hashing, package output paths, target matrices, and remap sidecar fanout before
it can become a package contract.

Any future compiler awareness of CrossTL project-portability reports must be a
separate read-only report-inspection or batch-ingest contract. It must not make
the report a substitute for the generated `.cgl` compiler input, the
`--source-remap` sidecar, or package `manifest.sourceHash` verification.

To keep that boundary explicit, source-ingest CLI commands reject reserved
manifest-like flags including `--source-manifest`, `--batch-manifest`,
`--source-batch`, `--batch`, and `--manifest` with a usage error. Package and
release subcommands still own their existing package-manifest options; the
reserved source flags apply only to commands that ingest CrossGL source text.
The public usage diagnostic names this deferred capability as compiler batch source manifest mode and states that `cglc v0 is per-input`.
