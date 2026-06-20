# HIR Dialect Catalog

The HIR dialect catalog is a small, read-only metadata manifest for the HIR
surface that already exists in the compiler. It does not participate in parsing,
optimization, validation, or backend lowering. Its purpose is to make current HIR
operation, type, and intrinsic names explicit enough for future MLIR mapping and
capability-registry work.

The catalog lives in `include/crossgl/HIR/HIRDialect.h` and
`src/HIR/HIRDialect.cpp`.

## Operation Records

`HIRDialectOperationRecord` describes stable operation names with enough shape
metadata to map existing HIR nodes or builtin calls into a future dialect:

| Field | Meaning |
| --- | --- |
| `name` | Stable dialect name, using the `hir.` prefix. |
| `sourceName` | Existing HIR enum name or builtin call spelling. |
| `kind` | Expression node, statement node, or builtin call. |
| `category` | Core, data-flow, control-flow, texture, image, atomic, synchronization, structural. |
| `effect` | Pure, store, resource read/write, control transfer, opaque, structural, or unknown. |
| `mlirMnemonic` | MLIR-ready mnemonic for the canonical operation. |

Examples include:

| Dialect name | Current source name | Category | Effect |
| --- | --- | --- | --- |
| `hir.texture_sample` | `TextureSample` | `texture` | `resource-read` |
| `hir.image_store` | `imageStore` | `image` | `resource-write` |
| `hir.atomic_add` | `atomicAdd` | `atomic` | `resource-read-write` |
| `hir.workgroup_barrier` | `workgroupBarrier` | `synchronization` | `opaque` |
| `hir.barrier` | `barrier` | `synchronization` | `opaque` |

The `barrier` compatibility alias maps to the same canonical MLIR mnemonic as
`workgroupBarrier`.

## Type Records

`HIRDialectTypeRecord` covers the builtin HIR type spellings currently accepted
by `TypeSemantics`, plus the two supported integer atomic forms:

| Field | Meaning |
| --- | --- |
| `name` | Existing HIR type spelling. |
| `category` | Void, scalar, vector, matrix, sampler, texture, storage image, or atomic. |
| `scalar` | Payload scalar class when one applies. |
| `lanes` | Vector lane count. |
| `rows`, `columns` | Matrix shape. |
| `mlirType` | Future-facing textual type spelling for the HIR dialect. |

Examples include `vec4`, `iimage2DArray`, `sampler`, `atomic<int>`, and
`atomic<uint>`.

## Intrinsic Records

`HIRDialectIntrinsicRecord` mirrors the current intrinsic registry at the
unique-name level. It records category, effect, result rule, arity, overload
presence, and existing capability names for atomic read-modify-write intrinsics.

Examples include:

| Name | Category | Effect | Result rule |
| --- | --- | --- | --- |
| `dot` | `math` | `pure` | `FixedFloat` |
| `length` | `math` | `pure` | `FixedFloat`, overloaded |
| `atomicAdd` | `atomic` | `resource-read-write` | `AtomicIntegerReadModifyWriteOldValue` |
| `barrier` | `synchronization` | `opaque` | `Void` |

## Validation

The catalog exposes lookup helpers for each slice and
`validateHIRDialectCatalog()` for duplicate-name checks across operations,
types, and intrinsics. The unit tests cover representative operation, type, and
intrinsic entries, stable category names, and duplicate rejection helpers.

The duplicate checks are intentionally local to the manifest. They do not change
production lowering semantics and do not reject source programs.
