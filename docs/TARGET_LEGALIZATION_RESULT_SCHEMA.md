# Target Legalization Result Schema

`docs/schemas/target-legalization-result-v0.schema.json` defines the
report-only JSON envelope for the next `TargetLegalizationResult` projection.
It is a validation contract for architecture fixtures and checker self-tests; it
is not a production `cglc` output contract and does not change backend support,
package emission, runtime admission, or release behavior.

The schema pins the v0 report-only policy block:

```json
{
  "mode": "report-only",
  "decisionAuthority": "current-compiler-behavior",
  "consumerMigration": "pending",
  "productionBehavior": "unchanged"
}
```

The schema requires the complete result groups that future consumers need to
agree on before behavior can move behind target legalization:

- support state via `supportStatus`, `moduleSupported`, and canonical support
  evidence IDs
- package mode, package provenance, and target profile
- required and missing target capability IDs
- diagnostics with target, severity, missing capabilities, and evidence IDs
- top-level evidence IDs that include nested diagnostic, rewrite, ABI, resource,
  and tool requirement evidence
- ABI fact placeholders with state, fact IDs, fact status, target, and evidence
- rewrite IDs, order, status, description, and evidence
- optional and native package tool requirements with required/missing tool IDs,
  concrete `records`, evidence IDs, and explicit optional-native-tool state.
  Each tool record carries `id`, `kind`, `name`, `status`, `target`, and
  `evidenceIds`, and its `status` must agree with the required/missing ID
  arrays. The canonical serialized native tool kind is `native-tool`; legacy
  internal `nativeTool` spelling is not valid v0 JSON and is diagnosed by the
  checker. Native package records make Metal `xcrun metal` / `xcrun metallib`
  and Vulkan `spirv-as` / `spirv-val` requirements explicit without changing
  package build behavior. `spirv-opt` is intentionally not required by this
  result unless a future optimization policy is represented as target
  legalization evidence.

`tools/check_target_legalization_result_contract.py` is the authoritative local
checker for this report-only surface. It validates the embedded architecture
example and all fixtures against the JSON Schema, then applies cross-field
semantic invariants that JSON Schema cannot express, such as
`supportStatus`/`moduleSupported`/package mode consistency, target-prefixed
capability IDs, evidence target alignment, contradictory core `state.*` /
`support.*` / `package-mode.*` evidence rejection, missing-capability
diagnostic coverage, diagnostic evidence kind coverage, and tool requirement
record/evidence consistency.

Focused validation:

```sh
python3 tools/check_target_legalization_result_contract.py --self-test
python3 tools/check_target_legalization_result_contract.py --root .
```

See
[`architecture/TARGET_LEGALIZATION_RESULT_V0.md`](architecture/TARGET_LEGALIZATION_RESULT_V0.md)
for the full report-only contract and migration policy.
