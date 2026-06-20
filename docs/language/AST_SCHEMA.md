# CrossGL v0 AST Schema Guide

This page documents the AST schema seed exposed by the sealed CrossTL frontend
snapshot. It is not a complete serialized AST contract yet. The snapshot
records class names, inheritance roots, node-family inventories, and enum
values extracted from CrossTL `ast.py`, plus a constructor-derived per-class
field inventory. The field inventory is a seed schema for node shape; it is not
full semantic support, not native compiler support, not a serialized AST wire
format, and not a source-location contract.

## Fact Sources

| Source | Role |
| --- | --- |
| `docs/language/crosstl-frontend-language-spec-v0.json` | Sealed CrossTL AST class, enum, expression, statement, and type-node inventory. |
| `tools/cross_repo_language_contract.json` | Accepted fixture groups with stable CrossTL AST hashes and compiler HIR hashes. |
| `docs/language/COMPATIBILITY.md` | Native-v0 deltas for accepted, unsupported, deprecated, invalid, and target-limited forms. |
| `docs/language/SEMANTICS.md` | Human-readable semantic baseline layered on top of this schema seed. |

## Schema Status

| Area | v0 status |
| --- | --- |
| Node names | Sealed by the CrossTL snapshot. |
| Node families | Sealed by snapshot arrays such as `statementNodes`, `expressionNodes`, and `typeNodes`. |
| Enum values | Sealed for `ShaderStage` and `ExecutionModel`. |
| Per-node fields | Seed schema sealed at `/ast/classFields` from constructor parameters and `self.*` assignments in CrossTL `ast.py`. |
| Source locations | Not sealed by the current snapshot. Compiler diagnostics must keep using native source-map evidence; `docs/language/SOURCE_LOCATION_REQUIREMENTS.md` owns the report-only evidence gate. |
| Native compiler HIR | Separate from CrossTL AST. HIR support is proven by fixtures and support evidence, not by AST class presence. |

## Checked Contract v1

The checked AST schema contract v1 is an inventory/report-only handoff from the
CrossTL snapshot to this prose page. It pins the current class inventory,
`/ast/classFields`, node-family arrays, and enum values so stale prose is caught
without changing CrossTL syntax, compiler parser behavior, HIR lowering, or
native support claims. Source-location requirements remain future shared-spec
work and are not implied by the current field inventory. The companion
`docs/language/SOURCE_LOCATION_REQUIREMENTS.md` contract keeps CrossTL
`source_location` inventory separate from native source-map and diagnostic-span
support evidence.

<!-- crossgl-crosstl-ast-schema-contract-v1:begin -->
```json
{
  "classCount": 81,
  "classFieldsCount": 81,
  "classFieldsSha256": "4168ff39aa1fb7f2184f442fd6e7196dcf469f16fe1fc514dd46ef3a9e8117fc",
  "classInventorySha256": "16086c3ab2ed33a5d99b9e60005c06715eb0b9931bbceeb67a12102d759606f4",
  "enums": {
    "ExecutionModel": [
      "graphics_pipeline",
      "compute_kernel",
      "ray_tracing",
      "general_purpose"
    ],
    "ShaderStage": [
      "vertex",
      "fragment",
      "geometry",
      "task",
      "amplification",
      "object",
      "mesh",
      "tessellation_control",
      "tessellation_evaluation",
      "compute",
      "ray_generation",
      "ray_intersection",
      "ray_closest_hit",
      "ray_miss",
      "ray_any_hit",
      "ray_callable"
    ]
  },
  "expressionNodes": [
    "ArrayAccessNode",
    "ArrayLiteralNode",
    "AtomicOpNode",
    "BinaryOpNode",
    "BufferOpNode",
    "BuiltinVariableNode",
    "CastNode",
    "ConstructorNode",
    "FunctionCallNode",
    "IdentifierNode",
    "LambdaNode",
    "LiteralNode",
    "MemberAccessNode",
    "MeshOpNode",
    "PointerAccessNode",
    "RangeNode",
    "RayQueryOpNode",
    "RayTracingOpNode",
    "SwizzleNode",
    "TernaryOpNode",
    "TextureNode",
    "TextureOpNode",
    "UnaryOpNode",
    "WaveOpNode"
  ],
  "kind": "crossgl-crosstl-ast-schema-contract",
  "nativeCompilerSupportClaim": "not-claimed-by-ast-presence",
  "pointers": [
    "/ast/classes",
    "/ast/classFields",
    "/ast/typeNodes",
    "/ast/statementNodes",
    "/ast/expressionNodes",
    "/ast/enums"
  ],
  "snapshot": "docs/language/crosstl-frontend-language-spec-v0.json",
  "sourceLocationClaim": "not-sealed-report-only",
  "statementNodes": [
    "AssignmentNode",
    "BlockNode",
    "BreakNode",
    "ContinueNode",
    "DoWhileNode",
    "ExpressionStatementNode",
    "ForInNode",
    "ForNode",
    "IfNode",
    "LoopNode",
    "MatchNode",
    "ReturnNode",
    "SwitchNode",
    "SyncNode",
    "WhileNode"
  ],
  "status": "report-only-inventory",
  "typeNodes": [
    "ArrayType",
    "FunctionType",
    "GenericType",
    "MatrixType",
    "NamedType",
    "PointerType",
    "PrimitiveType",
    "ReferenceType",
    "VectorType"
  ],
  "version": 1,
  "wireFormatClaim": "not-a-serialized-ast-wire-format"
}
```
<!-- crossgl-crosstl-ast-schema-contract-v1:end -->

## Field Inventory

The snapshot records one `/ast/classFields` entry for each class in CrossTL
`ast.py`. Each entry includes whether the class defines its own constructor,
the extracted constructor parameters, and fields assigned through `self.*`
inside that constructor.

Field entries record:

| Entry key | Meaning |
| --- | --- |
| `name` | The instance attribute name. |
| `source` | Whether the value is parameter-backed, parameter-derived, constant, or otherwise derived. |
| `parameter` | The constructor parameter feeding the field, when statically visible. |
| `annotation` | The constructor parameter or explicit assignment annotation, when present. |
| `required` / `optional` | Whether the feeding constructor parameter has no default or has an optional/default hint. |
| `default` | The constructor default expression or constant assignment value, when statically available. |
| `initializer` | The source expression assigned to the field. |

This inventory intentionally stays close to Python source shape. It captures
compatibility aliases such as `AssignmentNode.left`, `FunctionCallNode.args`,
and `VariableNode.vtype`, and metadata fields such as `ASTNode.annotations` and
`ASTNode.parent`. It does not infer full inherited effective fields, child-node
semantics, native compiler lowering, or target package support.

## Root and Type Nodes

CrossTL exposes `ASTNode` as the root class and `TypeNode` for type syntax.
The v0 type-node inventory is:

| Node | Meaning in the CrossTL surface | Native-v0 guidance |
| --- | --- | --- |
| `PrimitiveType` | Built-in scalar types. | Baseline for fixture-covered scalar forms. |
| `VectorType` | Built-in vector families. | Baseline for fixture-covered vector forms. |
| `MatrixType` | Built-in matrix families. | CrossTL fact; native package support is fixture scoped. |
| `ArrayType` | Prefix and postfix array forms. | Baseline only for documented fixed and runtime-tail forms. |
| `PointerType` | Postfix `*` type operator. | Unsupported for native-v0 unless future evidence names it. |
| `ReferenceType` | Postfix `&` and `& mut` type operators. | Unsupported for native-v0 unless future evidence names it. |
| `FunctionType` | Function type syntax. | CrossTL surface only for v0. |
| `GenericType` | Generic type syntax. | Unsupported for native-v0. |
| `NamedType` | User or resource named type fallback. | Accepted subject to semantic validation and target evidence. |

## Module and Declaration Nodes

| Node | CrossTL role | Native-v0 status |
| --- | --- | --- |
| `ShaderNode` | Shader module root. | Native-v0 baseline for `shader Name { ... }`. |
| `StageNode` | Stage block. | Baseline for `vertex`, `fragment`, and `compute`; other stage enum values are unsupported for native-v0. |
| `StructNode`, `StructMemberNode` | Struct declarations and fields. | Baseline in fixture-covered forms. |
| `FunctionNode`, `ParameterNode` | Functions and parameters. | Baseline for C-style functions; `fn` style and generics are unsupported. |
| `VariableNode`, `ConstantNode`, `ArrayNode` | Variables, constants, and array declarations. | Baseline only where native fixtures cover shape and storage rules. |
| `LayoutQualifierNode`, `AttributeNode` | Layout and metadata annotations. | Baseline for explicit `set`, `binding`, storage-image `format`, and workgroup sizes; broader aliases are unsupported. |
| `ImportNode`, `PreprocessorNode` | Import/preprocessor source forms. | Unsupported for native-v0. |
| `EnumNode`, `EnumVariantNode` | Enum declarations. | CrossTL surface only unless future compiler evidence names support. |
| `GenericParameterNode` | Generic parameters. | Unsupported for native-v0. |

## Statement Nodes

The snapshot records these statement nodes:

```text
AssignmentNode
BlockNode
BreakNode
ContinueNode
DoWhileNode
ExpressionStatementNode
ForInNode
ForNode
IfNode
LoopNode
MatchNode
ReturnNode
SwitchNode
SyncNode
WhileNode
```

Native-v0 baseline statement support is limited to block, declaration,
assignment, expression statement, `if`, C-style `for`, `while`, `return`,
`break`, and `continue` in fixture-covered contexts. `DoWhileNode`,
`ForInNode`, `LoopNode`, `MatchNode`, `SwitchNode`, and broad `SyncNode`
surface are accepted/exposed CrossTL nodes but unsupported for native-v0 unless
future rows move them into the baseline. Loop-control nodes outside loops are
`spec.error`.

## Expression Nodes

The snapshot records these expression nodes:

```text
ArrayAccessNode
ArrayLiteralNode
AtomicOpNode
BinaryOpNode
BufferOpNode
BuiltinVariableNode
CastNode
ConstructorNode
FunctionCallNode
IdentifierNode
LambdaNode
LiteralNode
MemberAccessNode
MeshOpNode
PointerAccessNode
RangeNode
RayQueryOpNode
RayTracingOpNode
SwizzleNode
TernaryOpNode
TextureNode
TextureOpNode
UnaryOpNode
WaveOpNode
```

Native-v0 baseline expression support is fixture scoped. Supported families
include literals, identifiers, arithmetic/comparison expressions, constructors,
casts, calls, swizzles, member access, array access, texture/sample forms,
storage-image operations, buffer operations, and scalar integer atomics where
`V0_SUPPORT.md` and support-matrix rows name evidence. `LambdaNode`,
`RangeNode`, `PointerAccessNode`, `WaveOpNode`, `RayTracingOpNode`,
`RayQueryOpNode`, and `MeshOpNode` are CrossTL surface only for native-v0.

## Pattern and Advanced Operation Nodes

CrossTL also exposes:

```text
PatternNode
WildcardPatternNode
IdentifierPatternNode
LiteralPatternNode
ConstructorPatternNode
StructPatternNode
TextureResourceNode
BufferNode
SamplerNode
```

`PatternNode`, `WildcardPatternNode`, `IdentifierPatternNode`,
`LiteralPatternNode`, `ConstructorPatternNode`, and `StructPatternNode` belong
to the CrossTL pattern/match surface and are unsupported for native-v0.
Resource helper nodes are schema facts; native support depends on the resource
grammar, semantic checks, and target-specific package evidence.

## Enum Values

`ShaderStage` values in the snapshot are:

```text
vertex
fragment
geometry
task
amplification
object
mesh
tessellation_control
tessellation_evaluation
compute
ray_generation
ray_intersection
ray_closest_hit
ray_miss
ray_any_hit
ray_callable
```

Only `vertex`, `fragment`, and `compute` are native-v0 baseline stages. The
other enum values are CrossTL accepted/exposed stage concepts but unsupported
for native-v0 unless target and HIR evidence are added.

`ExecutionModel` values are:

```text
graphics_pipeline
compute_kernel
ray_tracing
general_purpose
```

Native-v0 package claims are narrower than these enum values. The current
public package subset is compute-heavy with fixture-scoped graphics rows only.
Ray tracing and general-purpose execution models are not native-v0 package
support.

## Invariants for Consumers

Consumers should treat the AST schema seed with these rules:

1. AST class presence is not native compiler support.
2. A native-v0 support claim needs fixture, compatibility, or support-matrix
   evidence.
3. A target support claim needs package/reflection/native or validator evidence
   for the selected target.
4. Unsupported CrossTL nodes should fail closed through `cglc check` or
   target-specific diagnostics, not silently lower into backend-ready HIR.
5. The `/ast/classFields` data is a seed schema for CrossTL object shape; a
   future serialized AST contract must still define inheritance expansion,
   child-node semantics, and source-location requirements explicitly.
