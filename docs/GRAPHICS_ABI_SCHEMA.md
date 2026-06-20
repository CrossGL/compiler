# Graphics ABI JSON Schema

`tools/verify_graphics_abi.py --input <abi.json> --json` validates a
standalone graphics ABI contract document and emits a schema-versioned verifier
report. The input schema is
[`docs/schemas/graphics-abi-v1.schema.json`](schemas/graphics-abi-v1.schema.json),
and the report schema is
[`docs/schemas/graphics-abi-verify-v1.schema.json`](schemas/graphics-abi-verify-v1.schema.json).

This is a verifier foundation for future native graphics backends, not an ABI
lowering step. The compiler-produced `graphicsAbi` package sidecar is optional
and is emitted only for packages with vertex/fragment graphics stages. Compute
packages do not require or emit this sidecar.

The current compiler-produced slice mirrors entry points, reflected resources,
target resource binding records, deterministic vertex inputs, matched
vertex-to-fragment varyings, deterministic fragment outputs, and the vertex
`position` builtin when it is represented by a `vec4` field named `position` or
`clipPosition` in the vertex return struct. It does not claim to describe the
full graphics interface ABI yet. Compiler-produced varyings currently use
`smooth` interpolation until interpolation policy is modeled explicitly by
source or HIR metadata.

`sourceMapRef` is direct source-location evidence: a span object with file,
line, column, offset, length, and end-position fields. It is not an ID or index
into `ir/hir-source-map.json`, and consumers should treat it as independently
useful evidence for the record that carries it.

## Input Contract

- `schemaVersion`: integer schema version, currently `1`.
- `module`: source module identity.
- `target`: one of `metal`, `vulkan`, `directx`, or `opengl`.
- `entryPoints`: backend entry-point records with `stage`, `sourceName`, and
  `backendName`, plus a `sourceMapRef` debug anchor. The source identity
  `(stage, sourceName)` is unique and `backendName` is the stable ABI spelling
  `{stage}_{sourceName}`.
- `vertexInputs`: source vertex-input records keyed by vertex entry point and
  input location, with source type, format, and optional semantic name. The
  compiler sidecar derives current records from the vertex entry input struct
  and assigns locations by field order.
- `varyings`: source vertex-to-fragment IO records with producer and consumer
  endpoints. Producer endpoints must be vertex outputs, consumer endpoints must
  be fragment inputs, and their names, types, and locations must match. The
  compiler sidecar derives current records by matching non-builtin vertex entry
  return struct fields to fragment entry first-parameter struct fields by field
  name and formatted source type. Varying locations follow vertex output field
  order, excluding vertex output fields named `position` or `clipPosition` from
  the location stream. Matched compiler-produced varyings use `smooth`
  interpolation until source/HIR interpolation metadata exists.
- `fragmentOutputs`: source fragment-output records keyed by fragment entry
  point and render-target location. The compiler sidecar derives current
  records from the fragment entry return struct and assigns locations by field
  order.
- `builtins`: implicit source-level stage interface values. The current
  fixture-scoped contract recognizes only `position` as a vertex `output`
  `vec4` and `front_facing` as a fragment `input` `bool`; this intentionally
  avoids claiming a complete graphics-builtin ABI. The compiler sidecar emits
  only the vertex `position` builtin when backed by the vertex return struct;
  it does not emit `front_facing` until that source/HIR/backend path exists.
- `resources`: source resource records keyed by `(stage, name, kind)`, each
  with a `sourceMapRef` debug anchor.
- `abiRecords`: target ABI binding records keyed by
  `(stage, entryPoint, name, kind)`, each with a `sourceMapRef` debug anchor.

ABI records intentionally mirror the resource-binding subset already published
in reflection JSON. The standalone checker keeps this contract testable without
touching backend implementation files.

## Verifier Rules

The first verifier slice checks these invariants:

- Every ABI record target matches the document target.
- Every entry point has a non-empty source/backend name, a unique
  `(stage, sourceName)` source identity, and a stable backend ABI name equal to
  `{stage}_{sourceName}`.
- Every ABI record references a known entry point whose stage matches the
  record stage.
- Every ABI record links to a source resource with matching source type, array
  dimensions, address space, and storage-image format when those fields are
  present.
- Every entry point, source resource, and ABI record carries a normalized
  `sourceMapRef` span so verifier evidence can be traced back to source-map or
  debug metadata.
- Vertex inputs reference vertex entry points, fragment outputs reference
  fragment entry points, and their `(entryPoint, location)` coordinates are
  unique.
- Varying producer endpoints reference vertex entry points, consumer endpoints
  reference fragment entry points, and producer/consumer name, type, and
  location records match exactly.
- Builtin records reference known entry points, and each
  `(stage, entryPoint, direction, builtin)` interface slot is unique.
- Builtin records are limited to the fixture-scoped signatures above:
  `position` must be a vertex output `vec4`, and `front_facing` must be a
  fragment input `bool`.
- Source `set` and `binding` identity is preserved exactly when either the
  source resource or ABI record carries those fields, so target ABI records
  cannot invent binding identities absent from the linked source resource.
- Every source resource is bound by at least one ABI record.
- ABI record identities and target ABI coordinates are unique.
- Target-specific ABI fields are required or forbidden consistently:
  - Metal uses `kernelArgument` for ordinary resources and `threadgroupLocal`
    for shared resources.
  - Vulkan uses `descriptor` for ordinary resources and `workgroupLocal` for
    shared resources.
  - DirectX uses `registerBinding` for ordinary resources and
    `groupsharedLocal` for shared resources.
  - OpenGL uses `programResourceBinding` for ordinary resources and
    `workgroupLocal` for shared resources.

Verifier diagnostics use the `graphics.abi.` prefix. Diagnostic ordering follows
input order so fixture output stays stable.

## Report Contract

Reports include:

- `schemaVersion`: integer schema version, currently `1`.
- `inputPath`: normalized input path string.
- `success`: `true` exactly when there are no error diagnostics.
- `summary`: module, target, and top-level record counts when the input shape
  was readable, including entry point, vertex input, varying, fragment output,
  builtin, source resource, and target ABI record counts; otherwise `null`.
- `entryPointEvidence`: one row per entry point, preserving source name,
  backend name, stage, and source-map anchor.
- `resourceBindingEvidence`: one row per ABI record, linking the ABI record to
  its entry point, source resource index, binding/layout coordinates, and both
  source resource and ABI record source-map anchors.
- `sourceMapEvidence`: flattened source-map anchors for every entry point,
  source resource, and ABI record.
- `diagnosticCounts`: counts for note, warning, and error diagnostics.
- `diagnostics`: stable diagnostic records with standard source-location spans.

Successful reports are rejected by the report schema semantics when any
evidence array is missing or does not match the corresponding summary counts.
This prevents consumers from accepting a verifier report that says the ABI is
valid while omitting entry-point linkage, resource binding/layout evidence, or
source-map/debug anchors.
