# CrossTL AST To Compiler HIR Mapping Contract

This document defines the bounded contract between the CrossTL Translator AST
surface and the CrossGL-Compiler frontend AST/HIR surface. It is a mapping and
gate document only. It does not change accepted syntax, parser behavior, HIR
lowering, backend legalization, package artifacts, support-matrix coverage, or
MLIR/native artifact policy.

## Scope And Authority

The CrossTL frontend/spec is the language authority; compiler HIR mapping must
track it through explicit gates. A CrossTL AST class or enum value proves that
the language surface exists in the Translator snapshot, not that the native
compiler accepts, lowers, optimizes, legalizes, or emits that surface.
The compiler ingest contract is generated CrossGL `.cgl` source text, including
the in-process `crossgl::SourceInput` buffer form documented in
[COMPILER_INGEST_CONTRACT.md](COMPILER_INGEST_CONTRACT.md). That source-text
API does not make serialized CrossTL AST or CrossTL IR JSON an accepted HIR
input.
CrossTL `ASTNode.source_location` and inherited `source_location` fields are
inventory-only object-shape facts. Native HIR source-map evidence is separate
from CrossTL AST fields and must come from compiler-owned spans such as
`cglc dump-ir --stage hir-source-map` provenance, diagnostics, CTest,
support-matrix, or conformance evidence before a support claim can cite source
locations.

Compiler support claims need one of these gates:

1. A positive cross-repo contract fixture with stable CrossTL AST and compiler
   HIR hashes.
2. A native compiler fixture, unit test, conformance row, or v0 support evidence
   entry that names the source form and HIR behavior.
3. A compatibility or planned-gap row that rejects or excludes the source form
   explicitly.
4. Target-specific legality evidence before a frontend/HIR feature becomes a
   backend or package support claim.

Unsupported CrossTL nodes must fail closed through `cglc check`,
compatibility-ledger gates, or target legality diagnostics. They must not be
silently represented as backend-ready HIR.

## Contract Status Terms

| Status | Meaning |
| --- | --- |
| `mapped-now` | The current compiler frontend AST and HIR have an explicit field or enum path for the concept, with fixture-scoped support. |
| `token-boundary` | The compiler frontend preserves source tokens and HIR reparses only the supported subset. Unsupported shapes may become `HIRStatementKind::Raw`. |
| `planned-gap` | CrossTL exposes the concept, but the native compiler has no support claim yet. |
| `compatibility-gated` | The concept is valid CrossTL surface but currently rejected, skipped, warned on, or target-limited by named compatibility evidence. |
| `target-gated` | The frontend/HIR surface can exist, but backend/package support needs separate target evidence. |

## Source Artifacts

| Artifact | Role |
| --- | --- |
| `docs/language/crosstl-frontend-language-spec-v0.json` | Sealed CrossTL lexer, parser, AST, validation, stage, resource, and intrinsic snapshot. |
| `docs/language/AST_SCHEMA.md` | Human-readable CrossTL AST schema seed and inventory. |
| `docs/language/COMPATIBILITY.md` | Native-v0 compatibility ledger and explicit unsupported rows. |
| `docs/language/V0_SUPPORT.md` | Fixture-scoped native-v0 support evidence. |
| `tools/cross_repo_language_contract.json` | Cross-repo positive and negative language/HIR contract manifest. |
| `include/crossgl/Frontend/AST.h` | Compiler frontend declaration AST, after native parsing and before HIR. |
| `include/crossgl/HIR/HIR.h` | Compiler HIR data model. |
| `src/HIR/HIR.cpp` | Current compiler AST-to-HIR construction and function-body token reparsing. |

## Module And Stage Declarations

| CrossTL concept | Compiler frontend AST | HIR contract | Gate |
| --- | --- | --- | --- |
| `ShaderNode.name`, `ShaderNode.structs`, `ShaderNode.cbuffers`, `ShaderNode.constants`, `ShaderNode.functions`, and `ShaderNode.stages` | `ShaderModule` with matching declaration vectors for the native subset | `HIRModule.name`, `HIRModule.structs`, `HIRModule.constants`, `HIRModule.functions`, and `HIRModule.stages` | `mapped-now` for `shader Name { ... }`; imports, preprocessors, and broad globals stay `planned-gap`. |
| `StageNode.stage` and `StageNode.entry_point` metadata | `StageDecl.stage` and `StageDecl.name` | `HIRStage.stage`; `HIRStage.entryPointName` is inferred from `main` or the first function | `mapped-now` for `vertex`, `fragment`, and `compute`; explicit CrossTL entry-point metadata is tracked below. |
| `ShaderStage` enum values `ShaderStage.VERTEX`, `ShaderStage.FRAGMENT`, `ShaderStage.GEOMETRY`, `ShaderStage.TASK`, `ShaderStage.AMPLIFICATION`, `ShaderStage.OBJECT`, `ShaderStage.MESH`, `ShaderStage.TESSELLATION_CONTROL`, `ShaderStage.TESSELLATION_EVALUATION`, `ShaderStage.COMPUTE`, `ShaderStage.RAY_GENERATION`, `ShaderStage.RAY_INTERSECTION`, `ShaderStage.RAY_CLOSEST_HIT`, `ShaderStage.RAY_MISS`, `ShaderStage.RAY_ANY_HIT`, and `ShaderStage.RAY_CALLABLE` | Native lexer/parser stage keywords only for baseline stages | HIR stores the accepted stage spelling as a string, not a closed enum | Extended graphics, tessellation, mesh, task, amplification, object, and ray stages are `planned-gap`. |
| `ExecutionModel` enum values `ExecutionModel.GRAPHICS_PIPELINE`, `ExecutionModel.COMPUTE_KERNEL`, `ExecutionModel.RAY_TRACING`, and `ExecutionModel.GENERAL_PURPOSE` | No native compiler frontend AST field | No `HIRModule` or `HIRStage` execution-model field | `planned-gap`; package or target execution claims need a separate behavior branch. |
| `StageNode.layout_qualifiers` for compute size | `WorkgroupSizeDecl` from `layout(local_size_x = ..., local_size_y = ..., local_size_z = ...) in;` | `HIRWorkgroupSize` with source and folded component strings | `mapped-now` for local-size keys only; other stage-layout metadata remains `compatibility-gated`. |

## Structures Functions And Entry Points

| CrossTL concept | Compiler frontend AST | HIR contract | Gate |
| --- | --- | --- | --- |
| `StructNode.name` and `StructNode.members` | `StructDecl` at module scope or stage scope | `HIRStruct` in the module struct list | `mapped-now` for fixture-covered non-generic structs. Generic structs are recovered or rejected under compatibility gates. |
| `StructMemberNode.member_type` and `StructMemberNode.name` | `StructField` with `TypeRef`, name, and array suffix | `HIRField` with `HIRType` and name | `mapped-now`; array-size validity is checked during HIR construction. |
| `FunctionNode.return_type`, `FunctionNode.name`, `FunctionNode.parameters`, and `FunctionNode.body` | `FunctionDecl` with return type, name, parameters, and `FunctionDecl.bodyTokens` | `HIRFunction` with typed parameters, preserved `bodyTokens`, and parsed HIR body where supported | `mapped-now` for C-style functions. `fn` style, async/unsafe qualifiers, generics, and traits are `planned-gap`. |
| `ParameterNode.param_type` and `ParameterNode.name` | `Parameter` with `TypeRef`, name, and array suffix | `HIRParameter` | `mapped-now` for native C-style parameters; default values, mutability, and broad qualifiers are not mapped. |
| `StageNode.entry_point` | No explicit native AST entry-point field | `HIRStage.entryPointName` picks `main` first, otherwise first function with a warning | Explicit CrossTL entry-point metadata is a `planned-gap`. |
| `VariableNode.var_type`, `VariableNode.name`, and `VariableNode.initial_value` in function bodies | Preserved in `FunctionDecl.bodyTokens` until HIR body parsing | `HIRStatementKind::Declaration` when the supported token shape parses | `token-boundary`; module globals and unsupported local declaration forms need compatibility rows. |
| `ConstantNode.const_type`, `ConstantNode.name`, and `ConstantNode.value` | `ConstantDecl` with type, name, and value tokens | `HIRConstant` with parsed expression and optional folded value | `mapped-now` for native `const` declarations in fixture-covered forms. |

## Resources Constants And Layout Metadata

| CrossTL concept | Compiler frontend AST | HIR contract | Gate |
| --- | --- | --- | --- |
| `TextureResourceNode.name`, `TextureResourceNode.texture_type`, `TextureResourceNode.set`, `TextureResourceNode.binding`, `BufferNode.name`, `BufferNode.buffer_type`, `BufferNode.set`, `BufferNode.binding`, `BufferNode.access`, `SamplerNode.name`, `SamplerNode.binding`, and resource-like `VariableNode.vtype` declarations | `ResourceDecl` with `TypeRef`, name, optional `set`, `binding`, storage-image access, and storage-image `format` | `HIRResource` with kind, type, name, descriptor set/binding, explicitness flags, storage-image access, and optional format | `mapped-now` for native resource declarations and current resource type names only. CrossTL helper-node fields that do not have a `ResourceDecl` field are `planned-gap`. |
| `LayoutQualifierNode.entries` for resource layout | `ResourceLayoutDecl` from `layout(set = N, binding = M[, format = F])` | `HIRResource.set`, `HIRResource.binding`, `explicitSet`, `explicitBinding`, and `storageImageFormat` | `mapped-now` for these keys only. `group`, `register`, semantic aliases, interpolation metadata, and memory layouts are `compatibility-gated`. |
| CrossTL resource access metadata such as `readonly`, `writeonly`, and `readwrite` | Optional storage-image access qualifier before the resource type | `HIRStorageImageAccess` | `mapped-now` for storage-image resources only; aliases outside native parser spelling need a compatibility row. |
| `ShaderNode.cbuffers` | Native `cbuffer Name { ... }` parsed as `StructDecl` in `ShaderModule.cbuffers` | Emitted as `HIRStruct` plus per-stage uniform `HIRResource` with implicit set `0` and assigned binding | `mapped-now`; cbuffer fields are also available as unqualified function variables unless duplicate field names make them ambiguous. |
| `VariableNode.qualifiers` with `var<workgroup>` address space | Stage-scope `ResourceDecl` normalized to a `shared ...` type | `HIRResourceKind::Shared` without descriptor set or binding | `mapped-now` for `workgroup`/shared aliases accepted by the native parser. Other address spaces are `compatibility-gated`. |
| `AttributeNode.name`, `AttributeNode.arguments`, and broad metadata annotations | No general native AST metadata node | No general HIR metadata bag | `planned-gap` unless a dedicated compiler field, validation rule, and fixture evidence exist. |

## Function Body Boundary

The current compiler does not consume serialized CrossTL body AST nodes.
`FunctionDecl.bodyTokens` is the stable raw boundary. HIR body construction
reparses those tokens into the supported HIR subset and preserves unsupported
statement shapes as raw tokens.

| CrossTL concept | Compiler frontend AST | HIR contract | Gate |
| --- | --- | --- | --- |
| `BlockNode` | Tokens enclosed by braces in `FunctionDecl.bodyTokens` | `HIRStatementKind::Block` with child statements | `mapped-now` for balanced native token bodies. |
| `ExpressionStatementNode` | Body tokens ending in `;` | `HIRStatementKind::Expression` with parsed `HIRExpression` | `token-boundary`; unsupported expression tokens fall back to raw statement handling. |
| `AssignmentNode` | Body tokens with top-level assignment operator | `HIRStatementKind::Assignment` with target and value expressions | `mapped-now` for supported assignment and compound-assignment token forms. |
| `IfNode` | Body tokens beginning with `if` | `HIRStatementKind::If` with condition, body, and else body | `mapped-now` for native `if (...)` forms. |
| `ForNode` | Body tokens beginning with `for` | `HIRStatementKind::For` with initializer, condition, update tokens/statements, and body | `mapped-now` for C-style `for` headers. |
| `WhileNode` | Body tokens beginning with `while` | Current HIR uses `HIRStatementKind::For` as the loop representation | `mapped-now` as a loop, not as a distinct HIR `While` kind. |
| `ReturnNode`, `BreakNode`, `ContinueNode` | Native return/break/continue tokens | `HIRStatementKind::Return`, `Break`, or `Continue` | `mapped-now` where control-flow validation allows placement. |
| `SwitchNode`, `DoWhileNode`, `ForInNode`, `LoopNode`, `MatchNode`, broad `SyncNode` | Tokens may be skipped, diagnosed, or preserved as raw statements depending on native parser position | No backend-ready HIR support claim | `planned-gap`; `workgroupBarrier`/`barrier` are supported as call intrinsics, not as broad `SyncNode` lowering. |
| `LiteralNode`, `IdentifierNode`, `BuiltinVariableNode` | Expression tokens | `HIRExpressionKind::Literal` or `Identifier` with inferred type where available | `mapped-now` for known native spellings and builtins. |
| `BinaryOpNode`, `UnaryOpNode`, `TernaryOpNode` | Expression tokens | `HIRExpressionKind::Binary`, `Unary`, or `Select` | `mapped-now` for supported operators. |
| `FunctionCallNode`, `ConstructorNode`, `CastNode` | Call-like expression tokens | `HIRExpressionKind::Call` or `Constructor` | `mapped-now`; intrinsic meaning is gated by HIR intrinsic/type validation. |
| `MemberAccessNode`, `SwizzleNode`, `ArrayAccessNode` | Member, swizzle, and index tokens | `HIRExpressionKind::MemberAccess` or `IndexAccess` | `mapped-now` for supported vector/resource/struct/array shapes. |
| `TextureOpNode` and texture call spellings | Texture expression tokens | `HIRExpressionKind::TextureSample`, `TextureCompare`, `TextureCompareLodManual`, or ordinary call | `mapped-now` only for current texture sample/compare forms. Other texture/image operations are `planned-gap`. |
| `AtomicOpNode` and image atomic spellings | Call expression tokens | HIR atomic intrinsic calls or image atomic calls with side-effect validation | `mapped-now` for current scalar integer and storage-image atomic families only. |
| `RangeNode`, `LambdaNode`, `PointerAccessNode`, array literals beyond native parser support | No dedicated frontend AST field at the body boundary | No backend-ready HIR support claim | `planned-gap`. |

## Planned Gaps

| CrossTL area | Current compiler contract | Required gate |
| --- | --- | --- |
| Wave operations through `WaveOpNode` | No dedicated native AST or HIR node family | Add parser/HIR representation, diagnostics, positive/negative fixtures, and target legality evidence. |
| Ray stages and ray operations through `RayTracingOpNode` and `RayQueryOpNode` | No native ray stage or ray operation HIR lane | Add stage acceptance, HIR operation forms, compatibility updates, and target/package evidence. |
| Mesh/task/amplification/object stages and `MeshOpNode` | Stage enum values are CrossTL facts only; native stage parser does not lower them | Add frontend stage support, HIR stage contract, backend legality, and fixture evidence. |
| Broad image operation surface beyond current storage-image calls | Compiler supports only narrow `imageLoad`, `imageStore`, and `imageAtomic*` call spellings with resource type/layout gates | Add explicit CrossTL AST-to-HIR operation rows before claiming any additional image operation support. |
| CrossTL abstract AST base families `ASTNode`, `ExpressionNode`, `StatementNode`, `TypeNode`, and `PatternNode` | Abstract snapshot classes are inventory anchors only; support claims must name concrete compiler fields, HIR nodes, and fixtures. | Keep abstract bases out of `mapped-now` claims unless a concrete row and fixture prove behavior. |
| Import, preprocessor, enum, and generic declaration nodes `ImportNode`, `PreprocessorNode`, `EnumNode`, `EnumVariantNode`, and `GenericParameterNode` | Compatibility ledger records these as unsupported for native-v0 or outside the current compiler parser boundary. | Add behavior-owning parser/HIR changes and cross-repo fixtures before moving any of these into support. |
| CrossTL type AST nodes `PrimitiveType`, `VectorType`, `MatrixType`, `ArrayType`, `NamedType`, `GenericType`, `PointerType`, `ReferenceType`, and `FunctionType` | The compiler has an independent `TypeRef` parser for native-v0 type spellings; it does not consume the CrossTL type AST as HIR truth. | Add shared type semantics, validation, backend legality, and source-map fixtures before claiming direct AST-to-HIR type-node support. |
| Match and pattern helper nodes `CaseNode`, `MatchArmNode`, `IdentifierPatternNode`, `LiteralPatternNode`, `ConstructorPatternNode`, `StructPatternNode`, and `WildcardPatternNode` | No native-v0 match or pattern HIR lowering exists. | Add pattern semantics, diagnostics, HIR representation, and target legality before support claims. |
| Array and helper expression nodes `ArrayNode`, `ArrayLiteralNode`, `TextureNode`, and `BufferOpNode` | HIR maps selected native indexing, constructor, texture, and storage-buffer call forms through token parsing, not by consuming these CrossTL helper nodes. | Add explicit AST consumption or compatibility diagnostics before claiming support beyond the token boundary. |
| Imports, preprocessors, enums, generics, traits, impls, patterns, and match arms | Compatibility ledger records them as unsupported for native-v0 | Add behavior-owning frontend and HIR changes, then update this contract and cross-repo evidence. |
| Pointer, reference, function, and generic type nodes | Type names may be tokenized, but no general native-v0 HIR type support exists | Add type semantics, validation, backend legality, and fixtures before support claims. |
| General attributes and semantic metadata | No HIR metadata bag or source-location contract for arbitrary attributes | Add a typed metadata model and explicit validation gates. |

## Change Gates

When a row moves from `planned-gap` or `compatibility-gated` to `mapped-now`,
the behavior-owning branch must update the gates in this order:

1. Update the CrossTL snapshot-derived language/spec documentation if the
   Translator surface changed.
2. Update `docs/language/COMPATIBILITY.md` and this mapping contract so the
   support claim, unsupported row, or target limitation is explicit.
3. Add or update compiler parser/HIR implementation in the behavior branch.
4. Add positive compiler fixtures or unit tests for accepted HIR shapes and
   negative diagnostics for rejected shapes.
5. Update `tools/cross_repo_language_contract.json` only when both repositories
   intentionally accept the form and the new AST/HIR hashes are reviewed.
6. Add target legality, backend, package, or support evidence before claiming
   target support.

Documentation-only branches may add or tighten this contract and its checker,
but must not refresh support matrices, MLIR manifests, native artifact records,
or cross-repo fixture hashes unless they own that behavior change.

## Compiler Anchors

| Anchor | Contract role |
| --- | --- |
| `include/crossgl/Frontend/AST.h::ShaderModule` | Native frontend module declaration container. |
| `include/crossgl/Frontend/AST.h::StageDecl` | Native stage declaration container. |
| `include/crossgl/Frontend/AST.h::StructDecl` | Native struct and cbuffer declaration shape. |
| `include/crossgl/Frontend/AST.h::FunctionDecl` | Native function declaration and body-token boundary. |
| `include/crossgl/Frontend/AST.h::ResourceDecl` | Native stage resource declaration and layout metadata. |
| `include/crossgl/HIR/HIR.h::HIRModule` | HIR module declaration container. |
| `include/crossgl/HIR/HIR.h::HIRStage` | HIR stage container and entry-point field. |
| `include/crossgl/HIR/HIR.h::HIRResource` | HIR resource kind, descriptor, and storage-image metadata. |
| `include/crossgl/HIR/HIR.h::HIRStatementKind` | HIR statement support boundary, including `Raw`. |
| `include/crossgl/HIR/HIR.h::HIRExpressionKind` | HIR expression support boundary. |
| `src/Frontend/Parser.cpp::parseModule` | Native module parser entry point. |
| `src/Frontend/Parser.cpp::parseStage` | Native stage parser and stage-local declaration boundary. |
| `src/Frontend/Parser.cpp::parseResource` | Native resource parser and `var<workgroup>` gate. |
| `src/HIR/HIR.cpp::buildHIR` | Compiler frontend AST-to-HIR construction entry point. |
| `src/HIR/HIR.cpp::BodyParser` | Function-body token-to-HIR parser boundary. |
| `src/HIR/HIR.cpp::convertResource` | Resource declaration to `HIRResource` mapping. |
