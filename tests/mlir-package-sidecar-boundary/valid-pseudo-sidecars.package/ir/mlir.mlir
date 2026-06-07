// CrossGL pseudo-MLIR: textual HIR projection, not a registered MLIR dialect.
// Compatibility package fixture; future real dialect output must stay separate.
module @ValidPseudo attributes {
  crossgl.version = "fixture",
  crossgl.ir_kind = "pseudo-mlir",
  crossgl.real_mlir = "false"
} {
  func.func @vertex_main(%input: !crossgl.struct<VertexInput>) -> !crossgl.struct<VertexOutput>
}
