// CrossGL pseudo-MLIR: textual HIR projection, not a registered MLIR dialect.
// This fixture intentionally puts real experiment evidence in a production path.
module attributes {
  crossgl.version = "fixture",
  crossgl.ir_kind = "pseudo-mlir",
  crossgl.real_mlir = "false",
  crossgl_real_mlir_smoke = true
} {
}
