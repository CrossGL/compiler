# CrossGL Source Remap Sidecar Schema

`cglc check`, `cglc dump-ir --stage hir-source-map`, and
`cglc build --debug-ir` can consume a generated-to-original source remap sidecar
with `--source-remap <remap.json>`. The compiler input remains generated CrossGL
source text; the remap sidecar adds optional original-source provenance to
diagnostics, HIR source-map records, and package debug metadata.

## Compatibility Policy

- `schemaVersion` is required and is currently `1`.
- The current machine-readable schema is
  [`docs/schemas/source-remap-v1.schema.json`](schemas/source-remap-v1.schema.json).
- Unknown future versions must be treated as incompatible.
- Adding optional metadata fields requires a schema update because v1 rejects
  unknown fields.
- The sidecar is an input contract. It is not copied into packages and does not
  change package source hashes or package debug artifact schemas. File-backed
  debug package builds emit a separate
  [`source-remap-provenance-v1`](SOURCE_REMAP_PROVENANCE_SCHEMA.md) sidecar that
  records the input sidecar's path, hash, and mapping summary.

## Version 1

Top-level fields:

- `schemaVersion`: integer schema version, currently `1`.
- `generatedFile`: stable relative POSIX compiler-input path. For CLI
  generated-source workflows this normally matches `--logical-input <path>`.
- `mappings`: non-empty array of generated/original span pairs.

Each mapping contains:

- `generated`: source span in the compiler-input path. `generated.file` must
  match the top-level `generatedFile`; this cross-field invariant is enforced
  by the schema validator's source-remap semantic checks.
- `original`: corresponding span in the original authoring source.

Each span contains `file`, `line`, `column`, `offset`, `length`, `endLine`,
`endColumn`, and `endOffset`. Paths are stable relative POSIX paths. Line and
column values are 1-based. Offsets are zero-based byte offsets. Mapping spans
must be non-empty and must satisfy `endOffset == offset + length`.

## Example

```json
{
  "schemaVersion": 1,
  "generatedFile": "generated/from-translator.cgl",
  "mappings": [
    {
      "generated": {
        "file": "generated/from-translator.cgl",
        "line": 7,
        "column": 1,
        "offset": 148,
        "length": 1,
        "endLine": 7,
        "endColumn": 2,
        "endOffset": 149
      },
      "original": {
        "file": "shaders/original.crossgl",
        "line": 42,
        "column": 9,
        "offset": 900,
        "length": 1,
        "endLine": 42,
        "endColumn": 10,
        "endOffset": 901
      }
    }
  ]
}
```

## CLI Behavior

`cglc check <input.cgl> --logical-input <generated-path> --source-remap
<remap.json> --diagnostics-json` keeps `location` as the generated compiler
input span and adds `originalLocation` when a diagnostic span is covered by a
mapping. The remap `generatedFile` must match the effective compiler input path
after `--logical-input` is applied, otherwise the command fails with
`io.invalid-source-remap`. Human-readable diagnostics prefer `originalLocation`
when present.

`cglc dump-ir <input.cgl> --stage hir-source-map --logical-input
<generated-path> --source-remap <remap.json>` keeps generated source-map
`location` fields and adds optional `originalLocation` fields to covered
expression, type, statement, resource, and combined record payloads. The same
generated path match is required.

`cglc dump-ir <input.cgl> --stage debug --logical-input <generated-path>
--source-remap <remap.json>` applies the same remap to debug metadata
`hirSourceLocations`, keeping generated `location` anchors and adding covered
`originalLocation` payloads.

`cglc build <input.cgl> --debug-ir --logical-input <generated-path>
--source-remap <remap.json>` applies the same generated-path validation and
adds `originalLocation` fields to package `ir/debug-metadata.json` and
`ir/hir-source-map.json` for covered HIR source spans. The remap sidecar is not
embedded in the package. Instead, file-backed remap inputs are identified by
`manifest.artifacts.sourceRemap`, which points to
`ir/source-remap-provenance.json`. Package `sourceHash` continues to describe
the physical `<input.cgl>` bytes.
