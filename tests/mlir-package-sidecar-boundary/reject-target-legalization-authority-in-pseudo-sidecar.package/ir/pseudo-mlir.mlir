// CrossGL pseudo-MLIR: textual HIR projection, not a registered MLIR dialect.
// This fixture intentionally puts target-legalization parity authority in a production path.
module @TargetLegalizationAuthorityInPseudoSidecar attributes {
  crossgl.version = "fixture",
  crossgl.ir_kind = "pseudo-mlir",
  crossgl.real_mlir = "false",
  crossgl.target_legalization_facts = "claimed"
} {
}
