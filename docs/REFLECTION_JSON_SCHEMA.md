# CrossGL Reflection JSON Schema

Every successful `cglc build` writes `reflection.json` in the generated `.cglb`
directory package. Reflection records the shader-visible interface after HIR
analysis and backend ABI assignment: entry points, resource declarations,
target-specific bindings, push constants, function constants, vertex layouts,
workgroup sizes, manual texture-compare kernels, and target feature records.

## Compatibility Policy

- `schemaVersion` is required and is currently `1`.
- Consumers should branch on `schemaVersion` before reading nested fields.
- Unknown future versions should be treated as incompatible unless the consumer
  explicitly opts into best-effort feature detection.
- Adding optional reflection fields is compatible within schema version 1.
- Removing required fields, changing field types, renaming fields, or changing
  required ABI/resource semantics requires a schema-version bump.
- The compiler emits only the current schema.
- The current machine-readable schema is
  [`docs/schemas/reflection-v1.schema.json`](schemas/reflection-v1.schema.json).

## Version 1

Top-level fields:

- `schemaVersion`: integer schema version, currently `1`.
- `module`: HIR module name.
- `target`: package target name.
- `nativeBinary`: package-relative native binary path or planned native binary
  path. Emitted package paths use `/` separators and must stay inside the
  `.cglb` directory.
- `legalizationCoreEvidenceIds` (optional): deterministic core evidence IDs
  from the target legalization result used to produce reflection. These mirror
  target explanation/debug legalization core evidence and use the
  `target-legalization.v1.<target>.` prefix.
- `entryPoints`: backend entry-point records.
- `structs`: reflected structure definitions.
- `resources`: source-level resource declarations.
- `targetResourceBindings`: target-specific ABI/binding records.
- `pushConstants`: push-constant records.
- `functionConstants`: specialization/function constant records.
- `vertexLayouts`: backend vertex input layouts.
- `workgroupSizes`: compute workgroup-size records.
- `manualTextureCompareKernelSummary`: manual shadow compare summary counts.
- `manualTextureCompareKernels`: per-kernel manual shadow compare records.
- `targetFeatures`: target capability and feature records used by the package.

The schema intentionally distinguishes source declarations from target ABI
records. `resources` keeps the shader-facing name, kind, type, and optional
`set`/`binding` metadata. `targetResourceBindings` adds backend-specific fields
such as Metal attribute namespace/index, HLSL descriptor class, Vulkan
descriptor/storage class, SPIR-V type spelling, array counts, usage roles, and
storage-buffer layout.

Target resource bindings also carry target-specific ABI contracts:

- Metal bindings use `metalType` and must not declare HLSL, descriptor, SPIR-V,
  or Vulkan storage-class fields. Non-shared resources use `kernelArgument` with
  `argumentIndex`, `set`, and `binding`; `shared` resources use
  `threadgroupLocal` without descriptor coordinates.
- DirectX bindings may declare `hlslType` when the backend can spell a concrete
  HLSL resource type, and must not declare Metal, SPIR-V, or Vulkan
  storage-class fields. Non-shared resources use `registerBinding` with
  `descriptorType`, `argumentIndex`, `set`, and `binding`; `shared` resources use
  `groupsharedLocal` without descriptor coordinates.
- Vulkan bindings use `storageClass` and `spirvType` and must not declare Metal
  or HLSL type fields. Non-shared resources use `descriptor` with
  `descriptorType`, `set`, and `binding`; `shared` resources use
  `workgroupLocal` without descriptor coordinates.
- OpenGL bindings must not declare Metal, HLSL, descriptor, SPIR-V, or Vulkan
  storage-class fields. Non-shared resources use `programResourceBinding` with
  `argumentIndex`, `set`, and `binding`; `shared` resources use
  `workgroupLocal` without descriptor coordinates.

DirectX and OpenGL source-package records still carry the same source resource
coordinates as native-capable targets. Reflection preserves shader-facing
`resources[].set`/`binding` and records target ABI coordinates in
`targetResourceBindings`: DirectX uses the HLSL register class, register space,
register index, and argument index; OpenGL uses the program resource binding
index and binding class while retaining the source `set`/`binding` identity.

This schema validates the public shape and field types. `tools/validate_json_schema.py`
adds semantic validation for cross-field relationships that JSON Schema does not
express in the current lightweight validator: optional
`legalizationCoreEvidenceIds` entries must match the document target prefix,
use known target-legalization core evidence suffixes, stay unique, and appear in
canonical core evidence order; manual texture-compare summary
counts must match `manualTextureCompareKernels`, each manual kernel
`compatibilityAlias` must agree with whether `operation` differs from
`canonicalOperation`, `nativeBinary` must be a package-relative path when
populated, target-specific records must use the document `target`, entry-point
backend names must equal `<stage>_<sourceName>`, entry-point references must
name emitted backend entry points, target resource ABI fields must match the
backend-specific contracts above, and `targetResourceBindings` must correspond
to source-level `resources` by shader-visible resource identity.
Those semantic checks also pin target binding `stage` to the referenced backend
entry point, require source resource `type`, `set`, `binding`, address space,
storage-image format, and array dimensions to match the corresponding target
binding record, and validate array-dimension source facts in source resources,
target bindings, struct fields, and storage-buffer layout fields.

Target-specific ABI enum subsets remain intentionally test-pinned by package
CTests so new backend fields can grow without forcing an immediate schema
version bump. Package integrity validation can run this schema with
`--reflection-schema` or `--schema-root`, pairing the shape checks with the
manifest `artifacts.nativeBinary` parity check.
