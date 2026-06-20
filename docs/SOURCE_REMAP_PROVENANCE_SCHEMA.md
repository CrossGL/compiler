# CrossGL Source Remap Provenance Schema

`cglc build --debug-ir --source-remap <remap.json>` emits
`ir/source-remap-provenance.json` when the remap was loaded from a sidecar file.
The package manifest records this file as `artifacts.sourceRemap`.

The sidecar identifies the source-remap input that supplied generated-to-original
`originalLocation` records in package debug metadata and HIR source maps. It is
provenance only: `manifest.sourceHash` continues to hash the compiler input
`.cgl` bytes and is not affected by the remap sidecar.

## Compatibility Policy

- `schemaVersion` is required and is currently `1`.
- The current machine-readable schema is
  [`docs/schemas/source-remap-provenance-v1.schema.json`](schemas/source-remap-provenance-v1.schema.json).
- Unknown future versions must be treated as incompatible.
- The sidecar is emitted only for file-backed remap inputs. In-memory API remaps
  can still apply `originalLocation` records, but they do not claim file/hash
  provenance.

## Version 1

Top-level fields:

- `schemaVersion`: integer schema version, currently `1`.
- `kind`: fixed to `crossgl.sourceRemapProvenance`.
- `contractVersion`: fixed to `source-remap-provenance-v1`.
- `target`: package target.
- `generatedFile`: effective compiler-input path from the source remap sidecar.
- `mappingGranularity`: currently `source-span`.
- `mappingCount`: number of source-remap mappings consumed.
- `sourceRemap`: identity of the input remap sidecar.

`sourceRemap` contains:

- `path`: remap sidecar path supplied to the compiler.
- `sha256`: SHA-256 hash object for the remap sidecar bytes.
- `sizeBytes`: remap sidecar byte size.

`cglc package inspect --json` reports this sidecar under
`debugArtifacts.sourceRemap`, and `cglc package verify` fails packages whose
declared source-remap provenance is missing, malformed, or target-inconsistent.
