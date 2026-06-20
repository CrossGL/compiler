# CrossGL Diagnostics JSON Schema

`cglc check --diagnostics-json`, `cglc build --diagnostics-json`, package
`diagnostics.json` files, and CrossTL project/orchestrator reports use the same
diagnostics document shape.

## Compatibility Policy

- `schemaVersion` is required and is currently `1`.
- Consumers should branch on `schemaVersion` before reading nested fields.
- Unknown future versions should be treated as incompatible unless the consumer
  explicitly opts into best-effort feature detection.
- Adding optional diagnostic fields is compatible within schema version 1.
- Removing required fields, changing field types, renaming fields, or changing
  required diagnostic record semantics requires a schema-version bump.
- The compiler emits only the current schema. CrossTL project/orchestrator
  reports may also emit this schema when they use the `project.` diagnostic
  namespace described below.
- The current machine-readable schema is
  [`docs/schemas/diagnostics-v1.schema.json`](schemas/diagnostics-v1.schema.json).

## Version 1

Top-level fields:

- `schemaVersion`: integer schema version, currently `1`.
- `diagnostics`: array of diagnostic records.

Each diagnostic record contains:

- `severity`: one of `note`, `warning`, or `error`.
- `code`: stable diagnostic code. Codes are non-empty lowercase tokens
  separated by `.` or `-`.
- `message`: human-readable diagnostic text.
- `location`: source span object with `file`, `line`, `column`, `offset`,
  `length`, `endLine`, `endColumn`, and `endOffset`. `file` is a stable
  slash-separated relative path; v1 diagnostics must not emit absolute host
  paths. `cglc check --logical-input <path>` can report this logical
  compiler-input path after the physical source file is read; line/column and
  offset coordinates still describe the generated input text.
- `originalLocation`: optional source span object with the same shape as
  `location`. It is emitted only when `cglc check --source-remap <remap.json>`
  maps the diagnostic span back to original authoring source. `location`
  remains the generated compiler-input span for stable machine consumers.
- `target`: optional target selector. Compiler/backend diagnostics keep this
  limited to `metal`, `vulkan`, `directx`, or `opengl`. Diagnostics with
  `target.` codes must include this field so target capability evidence remains
  stable even when no capability array is present. `project.*` diagnostics may
  instead use an open, stable project/config selector such as `webgpu` or
  `workspace.default`.
- `missingCapabilities`: optional non-empty, unique array of capability ids for
  planned or unsupported work. Compiler/backend diagnostics require `target`
  and every capability id must use that target namespace (for example,
  `directx.backend.hlsl-lowering` on a `directx` diagnostic). `project.*`
  diagnostics may omit `target` and may use non-target project capability ids
  such as `include.resolution` and `target.backend`.

The v0 diagnostic code prefix inventory is:

- `artifact.`
- `directx.`
- `io.`
- `lex.`
- `metal.`
- `opengl.`
- `opt.`
- `package.`
- `parse.`
- `project.`
- `sema.`
- `spec.`
- `target.`
- `vulkan.`

`tools/validate_json_schema.py` also checks that messages are non-empty, and
source span coherence for every diagnostic `location` and `originalLocation`:
`endOffset == offset + length`, `endLine >= line`, and same-line
`endColumn >= column`. It also rejects absolute source path values so
diagnostics remain reproducible across workspaces. For target capability
evidence, it checks that `target.` diagnostic codes are paired with `target`,
compiler/backend diagnostics only use compiler target names, and
compiler/backend `missingCapabilities` are prefixed by that target. `project.*`
diagnostics are the v1 extension point for CrossTL project/orchestrator
diagnostics: they may carry project/config targets and non-target project
capabilities, while capability ids still use stable lowercase dotted or dashed
segments. The stable `spec.unsupported-for-native-v0` diagnostic also requires a
non-empty source span so unsupported-native-v0 reports cannot fall back to a
source-free placeholder location.

Native-v0 unsupported diagnostics are regression-tested by
`cglc_diagnostic_provenance_fixtures`: the emitted JSON must keep the stable
`spec.unsupported-for-native-v0` code and its source span must select the
unsupported source token in the check-failure fixture.

Package integrity validation can run this schema with `--diagnostics-schema`
or `--schema-root` against the root `diagnostics.json` emitted in every
`.cglb` package.
