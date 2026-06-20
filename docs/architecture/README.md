# CrossGL Architecture Planning

These documents define the long-term compiler direction used to coordinate
future development batches.

- [Architecture V2](ARCHITECTURE_V2.md): compiler architecture, ownership
  boundaries, package model, runtime boundary, and conformance rule.
- [Language and IR Plan](LANGUAGE_AND_IR_PLAN.md): language principles,
  semantic surface areas, HIR requirements, legalization requirements, and MLIR
  entry criteria.
- [Shared Language Spec Plan](SHARED_LANGUAGE_SPEC_PLAN.md): how to extract the
  common CrossGL language spec from the CrossTL frontend and keep translator and
  compiler behavior aligned.
- [Target Toolchain Plan](TARGET_TOOLCHAIN_PLAN.md): Metal, Vulkan, DirectX,
  OpenGL, reference tools, and CI/infrastructure strategy.
- [Target Legalization Audit](TARGET_LEGALIZATION_AUDIT.md): current support
  and package decision call-site map, proposed legalization result contract, and
  staged migration stop conditions.
- [Target Legalization Contract Next Call-Site Map](TARGET_LEGALIZATION_CONTRACT_NEXT_CALLSITE_MAP.md):
  next report-only call-site risk map, normalized result field proposal, target
  migration order, and stop conditions for the legalization contract expansion.
- [MLIR and LLVM Toolchain Plan](MLIR_LLVM_TOOLCHAIN_PLAN.md): staged MLIR/LLVM
  adoption, HIR ownership boundaries, target lowering paths, optimization,
  artifacts, diagnostics, and milestone gates.
- [Roadmap](ROADMAP.md): milestone sequence and agent batch policy.
- [Post-v0 Backlog Index](POST_V0_BACKLOG.md): ordered post-v0 worker lanes,
  risk notes, and stop conditions for the first batches after the v0 candidate.

The current implementation remains the working prototype and validation corpus.
These plans describe how to evolve it into the production CrossGL language and
compiler without treating the current subset as the final design.
