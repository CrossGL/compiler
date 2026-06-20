// CrossGL pseudo-MLIR: textual HIR projection, not a registered MLIR dialect.
// This fixture intentionally tries to masquerade as future real dialect output.
module @Masquerade attributes {
  crossgl.version = "fixture",
  crossgl.ir_kind = "pseudo-mlir",
  crossgl.real_mlir = "false"
} {
  hir.module @WouldBeRealDialect {
  }
}
