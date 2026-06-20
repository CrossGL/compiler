# CrossGL Performance Benchmarks

Milestone 6 adds a reproducible performance corpus runner, not a performance
gate. The runner records measurements in a stable JSON shape so future CI or
release automation can compare compiler behavior over time without changing
compiler semantics today.

## Build Profiles

`tools/benchmark_build_modes.py` owns the named benchmark profiles. Use it to
inspect the profile contract:

```sh
python tools/benchmark_build_modes.py
python tools/benchmark_build_modes.py --list-names
```

The same tool also publishes the current advisory baseline structural contract:

```sh
python tools/benchmark_build_modes.py --baseline-contract
python tools/benchmark_build_modes.py --list-baseline-fields
python tools/benchmark_build_modes.py \
  --check-baseline-report tests/performance/report-comparator-advisory-baseline.json
python tools/benchmark_build_modes.py \
  --check-baseline-report tests/performance/report-comparator-advisory-window-baseline.json \
  --check-baseline-report tests/performance/report-comparator-advisory-window-candidate.json
```

That checker is intentionally about report shape, not benchmark timing. Missing
baseline identity, case-category, command-profile, skipped-tool, or comparison
window metadata is a structural report problem; timing threshold classifications
remain advisory/report-only.
The `report-comparator-advisory-window-*` fixtures are offline examples with
deterministic repeated samples and warmup accounting. They exist to prove the
baseline window metadata, advisory threshold state, and non-regression
classification shape without running native toolchains or expensive benchmarks.

The performance corpus runner imports those profiles and records the selected
profile, package mode, native-validation request bit, and expanded command
profile metadata on every case. Reports also carry configured command-profile
coverage in `config.commandProfiles` and aggregate command-profile accounting in
`summary.commandProfiles` and `summary.caseCountByCommandProfile`. Corpus-runner
summaries also include `summary.optLevels`, `summary.caseCountByOptLevel`,
`summary.packageModes`, `summary.packageModeCount`, and
`summary.caseCountByPackageMode` so trend consumers can group advisory results
by optimization level and source/native package mode without re-parsing every
case. They also include
`summary.caseCountByCategoryTarget`, a category-to-target/backend matrix derived
from the case list, so Milestone 6 dashboards can see which fixture categories
are represented on each backend lane without joining separate summary fields.

The default profile remains `release`. Use `release-o2` when a benchmark lane
must explicitly pass `--opt-level O2`; that profile records
`compilerConfig: "O2"` and `cglcArgs: ["--opt-level", "O2"]` in command-profile
metadata.
Use `release-o2-debug-ir` only for provenance-focused benchmark reports that
need release O2 behavior plus HIR pass-trace capture. It records
`compilerConfig: "O2"` and
`cglcArgs: ["--opt-level", "O2", "--debug-ir"]`, which lets the existing runner
request `ir/hir-pass-trace.json` without changing the default `release` or
plain `release-o2` lanes.

For Vulkan package benchmarks, actual runs also copy optional
`artifacts.nativeProfile` sidecar evidence into
`case.artifactSummary.nativeProfile`. When the sidecar includes
`debug.optimization`, the report preserves the optimizer `tool`, `policy`,
`requestedLevel`, `level`, and `status` fields so consumers can distinguish
`applied`, `skipped-tool-missing`, and `skipped-disabled` without invoking native
GPU/device execution. Aggregate status coverage is reported through
`summary.nativeOptimizationStatuses` and
`summary.caseCountByNativeOptimizationStatus`. Reports also include
`summary.caseCountByNativeOptimizationEvidenceStatus` and
`summary.nativeOptimizationEvidence` so consumers can distinguish cases with a
known optimization status from cases where a native profile was declared but the
profile file was missing, unparsable, lacked `debug.optimization`, or contained
an optimization record without a `status`. Each native-profile summary also
records that derived state directly as
`case.artifactSummary.nativeProfile.optimizationEvidenceStatus`.
The comparator treats those native optimization summary fields as optional for
older reports, but when they are present it validates the status and evidence
counts against the case entries before reporting native optimization drift.
Actual package runs also read manifest-declared
`artifacts.nativeArtifactDescriptor` JSON when it exists and surface its
`optimizationLevel` and optional `optimizationEvidence` under
`case.artifactSummary.nativeArtifactDescriptor`. Descriptor evidence preserves
fields such as `requestedLevel`, `effectiveLevel`, `policy`, `status`, `tool`,
and `toolFlag` exactly as package metadata reported them. Descriptor status and
coverage are summarized through
`summary.nativeArtifactDescriptorOptimizationStatuses`,
`summary.caseCountByNativeArtifactDescriptorOptimizationStatus`,
`summary.caseCountByNativeArtifactDescriptorOptimizationEvidenceStatus`, and
`summary.nativeArtifactDescriptorOptimizationEvidence`. These fields are
additive: reports without descriptor evidence still validate and compare, while
new reports can show descriptor optimizer status, effective-level, and tool-flag
drift in the comparator's report-only `nativeOptimization` section.
Generated package reports also include deterministic manifest artifact-kind
inventory under `summary.manifestArtifactKinds`, with per-kind record counts,
emitted/missing counts, emitted byte totals, and case counts. This is
report-only package evidence for dashboards and native-performance follow-up; it
does not add artifact-size gates.
Reports also declare HIR pass-trace provenance in a machine-checkable shape.
`metadata.passTraceProvenance` records that the expected trace source is the
non-manifest package sidecar `ir/hir-pass-trace.json`, while each case carries a
`passTraceProvenance` record with the expected HIR optimization level, sidecar
availability, parse state, policy id, pass counts, pass-schedule fingerprint,
and whether the trace was incorrectly exposed through `manifest.artifacts`.
`summary.passTraceProvenance` and `summary.caseCountByPassTraceStatus` are
derived from cases so consumers can distinguish available traces from dry-run,
skipped, not-requested, requested-missing, artifact-unavailable, or unparsable
evidence, and can see when a report mixes different scheduled HIR pass
fingerprints. This is structural provenance only; it does not make pass-trace
availability or timing deltas a performance gate.

## Corpus Runner

The checked-in corpus manifest lives at
`tests/performance/performance_corpus_manifest.json`. It keeps the default
Milestone 6 corpus small enough for dry-run CI checks while recording fixture
categories for future trend grouping. The manifest also carries a top-level
`requiredCategories` list so structural checks can detect category omissions
before any timing comparison is trusted, plus a top-level `requiredCoverage`
list for package-evidence lanes that must remain represented in the small
corpus:

- storage buffers
- texture sampling
- descriptor arrays
- storage images
- atomics
- control flow

The `source-package-artifacts` coverage rule requires a DirectX/OpenGL
category-target matrix and names the source-package artifact evidence fields
that generated reports summarize. The `native-optimization-evidence` rule
requires aggregate Metal/Vulkan coverage across the native-optimization
categories that are currently represented by the smoke corpus and names the
native-profile/native-artifact descriptor summary fields. Both rules are
`report-only`; they prevent the checked-in corpus from silently dropping package
evidence coverage, but they do not invoke native tools or create performance
thresholds.

The curated default corpus includes descriptor-array variants for mixed
storage-buffer/texture/sampler resources, storage-image load/store and atomic
paths, a while-loop control-flow fixture, and one Metal-only folded
storage-buffer descriptor-array fixture. Those expanded cases remain
advisory/report-only and are intended to broaden report coverage without turning
native performance readiness into a threshold gate.
Every fixture in the default corpus must declare its target coverage explicitly;
the checker treats an omitted `targets` list as a structural manifest failure so
advisory v0 reports do not silently inherit or change benchmark lanes through a
fallback default.

Validate the corpus manifest contract locally without invoking `cglc`, running
performance benchmarks, or touching native/GPU devices:

```sh
python tools/check_performance_corpus_manifest.py --root .
python tools/check_performance_corpus_manifest.py --self-test
```

The static checker verifies required fixture fields, known target names,
repository-local fixture paths, duplicate-free fixture/case names, the canonical
`requiredCategories` list, required Milestone 6 category coverage, and the
expanded fixture/target case matrix. It also verifies the canonical
`requiredCoverage` rules for source-package artifact coverage and native
optimization evidence coverage, including the target/category coverage shape
they require from the default corpus. A missing required category such as storage
buffers, texture sampling, descriptor arrays, storage images, atomics, or
control flow, or a default-corpus fixture without explicit `targets`, is a
manifest-shape failure. It also verifies each `sourceSha256` against the
fixture's normalized UTF-8 source text with CRLF/CR line endings converted to
LF, so source hashes are independent of platform checkout line endings while
still detecting real source edits. These structural failures are hard-fail
coverage checks; benchmark timings, artifact sizes, native optimization
classifications, package-artifact inventory, and baseline curation remain
advisory/report-only. It is registered in CTest as
`cglc_performance_corpus_manifest` for cheap local shape checks.

List the small Milestone 6 fixture corpus without invoking the compiler:

```sh
python tools/benchmark_performance_corpus.py --list-corpus
```

Emit a dry-run report for CI shape checks:

```sh
python tools/benchmark_performance_corpus.py \
  --root . \
  --cglc build/cglc \
  --profile release \
  --target directx \
  --dry-run
```

Run actual measurements after building `cglc`:

```sh
python tools/benchmark_performance_corpus.py \
  --root . \
  --cglc build/cglc \
  --profile release \
  --target directx \
  --target opengl \
  --warmup 1 \
  --repeat 3 \
  --work-dir build/performance-corpus \
  --json-output build/performance-corpus/report.json
```

Run a Vulkan O2 report shape with explicit command-profile evidence:

```sh
python tools/benchmark_performance_corpus.py \
  --root . \
  --cglc build/cglc \
  --profile release-o2 \
  --target vulkan \
  --target-profile crossgl-vulkan-o2-package \
  --dry-run
```

Run an O2 report that also requests debug IR/pass-trace sidecar evidence:

```sh
python tools/benchmark_performance_corpus.py \
  --root . \
  --cglc build/cglc \
  --profile release-o2-debug-ir \
  --target vulkan \
  --target-profile crossgl-vulkan-o2-debug-ir-package \
  --dry-run
```

Baseline jobs can override the default advisory policy metadata for later trend
comparison:

```sh
python tools/benchmark_performance_corpus.py \
  --root . \
  --cglc build/cglc \
  --profile release \
  --target directx \
  --host-label ci-linux-x86_64-pool-a \
  --host-class linux-x86_64 \
  --target-profile crossgl-milestone6-smoke \
  --comparison-window '{"sampleCount":5,"warmupCount":1,"unit":"elapsedNs"}' \
  --toolchain-label cglc \
  --toolchain-version 0.6.0
```

Each case records the compiler path, fixture path, target, profile, package
mode, fixture category, success/failure state, diagnostic summary, skipped
state, unavailable tool markers, pass-trace provenance, artifact summary,
optional Vulkan native-profile summary, and whether native validation was
requested by the selected profile.
Actual measurement runs also populate the timing object with `elapsedNs`,
`minNs`, `medianNs`, `meanNs`, `maxNs`, `runs`, and `warmups`. The case-level
`elapsedNs` and `timing.elapsedNs` fields intentionally mirror the selected
summary value, currently the median measured duration, so older comparators can
keep using `elapsedNs`. Dry-run and skipped cases keep timing empty and report
`sampleCount: 0` / `warmupCount: 0` in the default comparison window so shape
checks stay deterministic.
Reports also include `metadata.measurementWindow` and
`summary.timingWindow` so consumers can distinguish optional comparison-window
policy labels from the sample and warmup counts the runner actually executed.
`summary.timingWindow.consistent` stays true only when every timed case carries
the configured number of measured and warmup records.
When expanded `commandProfile` metadata is present, the per-case profile labels
must agree with it: `optLevel` mirrors `commandProfile.compilerConfig`,
`profileBuildType` mirrors `commandProfile.buildType`, `packageMode` mirrors
`commandProfile.packageMode`, and `nativeValidationRequested` mirrors
`commandProfile.nativeValidationRequested`. When no baseline policy overrides
the report-level optimization label, `metadata.optLevel` is derived from the
selected command-profile `compilerConfig` values, using `mixed:<levels>` for
multi-profile reports.

The top-level report includes a `corpusVersion` marker. It also emits a
deterministic `metadata` block with the advisory report profile, report-only
timing/artifact-size policy labels, selected command-profile definitions, case
categories, target profile, optimization level, comparison window, measurement
window, dry-run flag, timed-case count, and `runtimeEnvironment` details for the
Python/platform runtime that produced the report. The runtime block is emitted
for normal, dry-run, and skipped reports and uses a canonical absolute POSIX
`pythonExecutable` path so archived reports can be compared without inferring
the producer interpreter from the surrounding CI job. The summary includes case
categories, case counts grouped by category, target, profile,
category-target/backend pair, command profile, optimization level, and package
mode, fixture counts by category, skipped/unavailable counts, skipped case lists
grouped by unavailable tool, skipped reason counts, skipped cases with
unavailable-tool evidence, native optimization status counts when sidecar
evidence is present, native optimization evidence coverage counts when sidecar
evidence is absent or incomplete, descriptor optimizer evidence counts when
native artifact descriptor evidence is present, manifest artifact-kind inventory
for generated package artifacts, measurement-window consistency accounting, and
timed case counts.
Those fields are intended for dashboarding and regression tracking while timing
thresholds remain report-only by default.
The `metadata.reportPolicy` object explicitly marks `timing`, `artifactSize`,
`nativeOptimization`, `packageArtifacts`, and future `baselineCuration`
decisions as `report-only`; only structural report-shape validation is
`hard-fail`.

## Baseline Policy Metadata

Saved reports should carry enough metadata to explain whether two performance
runs are comparable before looking at elapsed time. Report producers may record
this either in a top-level `baselinePolicy` object or in equivalent top-level,
`metadata`, `config`, `host`, `toolchain`, `toolchains`, and `toolAvailability`
fields. The comparator understands these labels when present:

- `hostLabel`: specific runner or machine pool label.
- `hostClass`: stable class such as operating system, architecture, and runner
  family.
- `toolchainLabel` / `toolchainVersion`: compiler or native toolchain identity.
- `toolchainClass`: stable compiler or native-tool family/class label, separate
  from a specific toolchain version or optional/required role.
- `targetProfile`: benchmark target lane or runtime profile.
- `optLevel`: optimization level used for generated/native artifacts.
- `comparisonWindow`: sample count, warmup count, date window, or other
  aggregation window information.
- `metadata.runtimeEnvironment`: Python/platform runtime provenance for the
  report producer, including machine, platform, Python executable,
  implementation, version, system, and system release.
- `toolAvailability.<tool>.available` / `status`: availability classification
  for compilers, validators, and native target tools.
- `toolAvailability.<tool>.optional` or `required`: whether an unavailable tool
  represents optional evidence or required benchmark coverage.

The current corpus runner records profile, target, optimization/profile details,
artifact summaries, optional Vulkan native-profile optimization summaries,
skipped-tool accounting, `metadata`, and `toolAvailability` directly in the
report. `toolAvailability.cglc.role` is `required`, so skipped compiler coverage
is classified explicitly instead of inferred. Every runner report also carries a
top-level `advisoryThresholdPolicy` and `thresholdBaselineReadiness` block, with
the same objects mirrored under `metadata`. These blocks are report-only
provenance: the runner publishes no numeric threshold rules because the
repository does not contain stable multi-run timing baselines. The readiness
block records host/toolchain/target-profile/opt-level provenance, runtime
environment shape, repeated-sample evidence, timed-case identity evidence, and
skipped-tool accounting, but `readyForThresholdBaseline` remains false until a
future owner-approved policy has stable data to promote. The runner policy stub
also carries `advisoryThresholdPolicy.enforcement` with `enforced: false`,
`hardFail: false`, `exitStatusAffected: false`, and `releaseBlocker: false` so
generated corpus reports cannot be mistaken for timing gates.

The runner always emits a top-level `baselinePolicy` object plus `toolchains`
metadata and mirrors the recognized labels into `metadata`, `host`, and
`toolchain` for consumers that do not parse `baselinePolicy`. By default this
policy records an auto-derived `hostClass` from the producer OS and architecture,
the selected target profile, optimization label, comparison window, and `cglc`
toolchain label. The specific `hostLabel` and `toolchainVersion` remain
explicit producer inputs because those values should identify a stable runner
pool and compiler build, not be guessed from a local checkout. If a producer does
not provide those labels through one of the recognized fields above, the
comparator reports them under `missingFields` or `toolchainsMissingVersions` in
the advisory context instead of assuming them. Missing or incomplete runtime
environment provenance is treated the same way: it prevents threshold-baseline
readiness and suppresses timing threshold claims, but it does not change
comparator exit status.

Skipped-tool accounting is derived from the case list and `toolAvailability`.
Each case must keep its category, profile, target, and command profile labels
explicit so report consumers do not have to infer missing shape from the case
key. Reports compared by `tools/compare_performance_reports.py` must include
top-level `schemaVersion`, `tool`, `corpusVersion`, `cases`, and `summary`
fields. Corpus-runner reports also carry `config`, `metadata`, and
`toolAvailability` blocks. The runner checker treats `metadata.optLevel`,
`metadata.targetProfile`, `metadata.commandProfiles`,
`metadata.measurementWindow`, `metadata.passTraceProvenance`,
`metadata.reportPolicy`, and `metadata.runtimeEnvironment` as required contract
fields. The runtime block
records `machine`, `platform`, `pythonExecutable`, `pythonImplementation`,
`pythonVersion`, `system`, and `systemRelease` so saved fixture reports can be
audited without rerunning benchmarks. The checker also requires
`advisoryThresholdPolicy` and `thresholdBaselineReadiness` at top level and under
`metadata`, verifies their `report-only` mode/failure mode, and rejects reports
that claim stable baseline data, hard timing-threshold behavior, or enforced
advisory-threshold status from the runner. `summary.commandProfiles`,
`summary.caseCountByCommandProfile`, `summary.optLevels`, and
`summary.caseCountByOptLevel`, `summary.caseCountByPassTraceStatus`, and
`summary.passTraceProvenance` are required accounting fields, as are
`summary.caseCount`, `summary.caseCategories`, `summary.caseCountByCategory`,
`summary.caseCountByCategoryTarget`, `summary.caseCountByProfile`, and
`summary.caseCountByTarget`. Missing or mismatched
case/category-target/profile/target/command-profile/opt-level accounting is a
structural report-shape failure. New reports also emit optional
`summary.packageModes`, `summary.packageModeCount`, and
`summary.caseCountByPackageMode`; when either package-mode list/count rollup is
present, the comparator validates it against per-case `packageMode` labels, and
requires `summary.packageModes` and `summary.caseCountByPackageMode` to be
emitted together. Older reports that omit those package-mode rollups remain
comparable. When a report also provides configured
`fixtures`, `profiles`, `commandProfiles`, or `targets`, those declared coverage
lists are audited before timing data is useful: emitted case fixtures must
appear in `config.fixtures`, configured profiles and command profiles must stay
consistent, emitted targets must be covered by `config.targets`, and selected
fixture counts in `summary.fixtureCount` and `summary.fixtureCountByCategory`
must be internally consistent. If expanded command-profile metadata is present,
profile-derived labels such as opt level, build type, package mode, and
native-validation request state must match the per-case labels, and default
`metadata.optLevel` must match the command-profile compiler-config coverage.
Native-profile `optimizationEvidenceStatus` must match the sidecar evidence
shape and the native optimization evidence summary counts. Reports that include
known native optimization status evidence, such as an `applied` or
`skipped-tool-missing` optimizer status, must also carry explicit
`metadata.hostLabel`, `metadata.hostClass`, `metadata.toolchainLabel`, and
`metadata.toolchainVersion` fields plus matching required `toolchains` metadata;
otherwise the runner checker treats the status evidence as incomplete run
identity instead of a usable optimization observation. A known optimizer status
must also include non-empty optimizer `tool`, `policy`, and `requestedLevel`
fields so dashboards can explain which advisory optimizer path produced the
status. Native artifact descriptor `optimizationEvidenceStatus` must match the
descriptor evidence shape when `case.artifactSummary.nativeArtifactDescriptor` is
present, and any descriptor summary counts must match the per-case descriptor
entries. Descriptor status, effective-level, and tool-flag changes are surfaced
as report-only native optimization drift; they do not create timing or
structural failures by themselves. Summary accounting such as skipped, timed,
category, profile, target, command profile, artifact, verification, success,
failure, or dry-run counts
must also match the cases. A
mismatch is treated as report-shape failure because consumers cannot trust the
report. Metadata compatibility differences such as a different host label or
comparison window are reported under
`metadata.baselinePolicy.compatibility` and remain advisory by default.
The comparator also emits `metadata.baselinePolicy.advisorySummary` and mirrors
the same object under `timing.advisoryContext.advisorySummary`. This summary
groups report-only warning classes such as missing context,
policy-value drift, toolchain metadata drift, and skipped-tool accounting drift
so dashboards can scan comparator evidence without parsing every mismatch.
`advisorySummary.mode` and `advisorySummary.failureMode` are always
`report-only`; structural report-shape failures still determine the comparator
exit status before any timing or advisory metadata warning is considered.
Conflicting aliases inside a single report, such as `baselinePolicy.optLevel`
disagreeing with `metadata.optLevel` or a mirrored toolchain version, are
structural validation issues because consumers cannot tell which run context is
authoritative. Cross-report host/toolchain/target-profile/optimization drift is
still advisory compatibility evidence and does not create a timing gate.
Explicit `toolchains` and `toolAvailability` metadata is also shape-validated
before timing output is trusted. Toolchain maps must use non-empty string
labels; list-form toolchain entries must carry a non-empty `label` or `name`;
entry `label`/`name` mirrors must match their map key; scalar fields such as
`version`, `status`, `role`, `class`, and `path` must be non-empty strings when
set; and `available`, `optional`, and `required` must be booleans or null.
Contradictory `optional`/`required` flags are structural report-shape errors.
When the same toolchain label appears in more than one recognized metadata
surface, canonical identity fields must also agree. For example,
`baselinePolicy.toolchainVersion`, `metadata.toolchainVersion`,
`toolchain.version`, `toolchains.<label>.version`, and
`toolAvailability.<label>.version` cannot describe different versions for the
same label. Conflicting class, version, status, role/classification, or
availability fields are treated as malformed report metadata because consumers
cannot know which toolchain identity is authoritative.
These checks fail-close malformed comparison metadata without turning elapsed
time regressions into mandatory CI failures.
Malformed case arrays, non-object case entries, missing case keys, and duplicate
normalized case identities are also reported as structural validation issues in
the comparison JSON. Unreadable files or invalid JSON still produce a usage-style
tool failure because there is no report shape to summarize.
Skipped cases are shape-checked more strictly than timing deltas: a skipped
case needs a non-empty `skipReason`, at least one `unavailableTools` entry,
empty timing, non-success status, and matching `toolAvailability` metadata for
the skipped tool. Stale command-profile coverage, selected-fixture accounting,
or skipped-tool summaries are structural report-shape failures; elapsed-time
regressions remain advisory/report-only.

`tools/check_performance_corpus_runner.py` self-tests the runner contract with
dry-run reports, skipped-tool reports, fake timed reports, Vulkan O2 native
profile summaries, and supplied host/toolchain labels. Its diagnostics name the
failing JSON path, for example `$.metadata.optLevel`,
`$.metadata.reportPolicy.timing`, `$.cases[0].optLevel`,
`$.cases[0].artifactSummary.target`, or
`$.summary.caseCountByCommandProfile`. Newer structural diagnostics can also
name stale configured coverage or selected-fixture accounting, such as
`$.config.fixtures`, `$.config.profiles`, `$.config.targets`,
`$.summary.fixtureCount`, `$.summary.fixtureCountByCategory`, or
`$.summary.skippedToolCasesByTool`. Treat those as producer contract errors: fix
the report metadata/accounting first, then evaluate advisory timing output.
`tools/check_benchmark_build_modes.py --self-test` also exercises the
build-profile registry and the advisory baseline structural contract, including
an intentionally incomplete report that fails on missing host/toolchain/target
profile/optimization/comparison-window context and skipped-tool metadata.

The comparator normalizes case identity from structured case fields before it
checks coverage. When `fixtureName`, `target`, and `profile` are available,
those labels form the comparison key; otherwise the legacy
`<fixture>::<target>::<profile>` case string is used. This lets older reports
that used fixture paths in `case` compare against newer reports that use stable
fixture names. Raw `case` label changes are reported under
`structure.changedReportCaseLabels`, but they are not structural coverage loss
when the normalized identity still matches.

Future timing-threshold proposals should only be made from baselines that carry
complete structural metadata and repeated timing evidence: host label and class,
runtime environment provenance,
toolchain labels and versions, tool availability classifications with
optional/required roles, target profile, optimization level, comparison window,
configured fixture, target, profile, and command-profile coverage,
skipped-tool accounting, explicit timed-case `fixtureName`, `target`,
`profile`, and `optLevel` labels, at least two timed samples for both baseline
and candidate observations, and zero candidate package/build failures. Without
those fields and repeated samples, the comparator can still publish timing
observations, but the pair is not a strong threshold baseline and threshold
excess claims are withheld. Legacy case-key inference remains available for
coverage comparison, but inferred timed-case identity is not treated as eligible
threshold evidence. The comparator self-test keeps this advisory contract pinned
for incomplete baseline and candidate fixtures by checking the reported
`missingFields`, threshold-readiness requirements, advisory context, and
threshold-policy suppression reasons without turning timing deltas into
failures.

## Report Comparator

Use `tools/compare_performance_reports.py` to compare two saved JSON reports
offline:

```sh
python tools/compare_performance_reports.py \
  build/performance-corpus/baseline.json \
  build/performance-corpus/candidate.json
```

By default the comparator is advisory for timing changes: it reports slower
timed cases but exits successfully unless the candidate loses structural
coverage. Structural coverage is checked before timing and includes baseline
case keys, fixture categories, command profiles, profiles, targets, newly
skipped cases, skip reason changes, functional package/build failures,
toolchain labels, required or unclassified newly unavailable toolchain labels,
and report accounting validation, including configured fixture/profile/target
coverage, command profile labels, and skipped-tool metadata. Added cases,
categories, command profiles, profiles, targets, resolved skips, optional
unavailable tools, and resolved unavailable toolchains are reported without
failing the comparison unless they also remove case coverage.
Per-case fixture-category drift is also structural: swapping categories between
otherwise matching case keys makes timing evidence ambiguous even when the
overall category set is unchanged.

The top-level `policy` block makes the pass/fail rules machine-readable:
`policy.failureClass` reports the dominant failure class. Structural failures
are the only hard-fail class in v0. `policy.failureSurfaces.hardFail` lists
`structure`; `policy.failureSurfaces.reportOnly` lists timing, artifact-size,
and baseline-policy advisory surfaces. `policy.structural.mode` is always
`hard-fail`, while `policy.timing.mode` and `policy.artifactSize.mode` are
`report-only`. Timing regressions therefore stay advisory in CI shape checks,
while invalid report shape, malformed skipped cases, missing
category/profile/target/command-profile fields, missing command-profile
accounting, missing case/category/profile/target/opt-level summary accounting,
package/build failures, and required toolchain coverage loss remain hard
structural failures. The comparator guarantee is intentionally limited to report
readability and coverage accounting: if the JSON shape is valid, the comparison
can be used by dashboards and release notes without inferring coverage from raw
case keys. It does not guarantee that a timing regression is acceptable for a
future release; timing thresholds, artifact-size changes, and threshold-baseline
readiness remain advisory evidence until a later milestone explicitly promotes
them. Advisory timing thresholds are not release blockers without explicit owner
approval.
Every threshold surface also carries normalized enforcement provenance:
`policy.timing.thresholdEnforcement`, `timing.thresholdEnforcement`,
`timing.advisoryThresholds.enforcement`, `timing.explicitThresholdPolicy.enforcement`,
and per-case `advisoryThreshold.enforcement` or `explicitThreshold.enforcement`
all record `mode: report-only`, `enforced: false`, `hardFail: false`,
`exitStatusAffected: false`, and `releaseBlocker: false`. Consumers should read
those fields instead of inferring enforcement from threshold-exceeded counts.

The comparator also emits a top-level `reportArtifacts` contract block so
dashboard and archival jobs can validate the expected comparison-report shape
without inferring it from prose. `reportArtifacts.comparisonReport` lists the
required top-level JSON fields for the comparison report artifact. The
`structure` artifact is marked `failureMode: hard-fail`; the
`timingAdvisory`, `artifactSizeAdvisory`, and `baselinePolicyAdvisory`
artifacts are marked `failureMode: report-only`. The timing advisory artifact
identifies `timing.timingDeltas` as its optional full-delta list and defaults to
`regressions-only`; it also advertises
`timing.evidenceSufficiency` as the advisory evidence summary and
`timing.warningSummary` as the report-only warning inventory, plus
`timing.advisoryThresholdPolicy` as the report-only threshold policy surface.
The artifact-size advisory artifact identifies `artifactSize.sizeDeltas`,
defaults to `increases-only`, and advertises
`artifactSize.manifestArtifactKindEvidence` for per-manifest artifact kind
evidence plus `artifactSize.warningSummary` as the report-only size warning
inventory. Those declarations document the current artifact expectations and do
not introduce hard timing or artifact-size thresholds. The comparator self-test
walks these advertised paths and required fields for default and
explicit-threshold comparisons so the artifact contract cannot drift silently
while timing and artifact-size deltas remain report-only. The baseline policy
advisory artifact requires
`compatibility`, `comparisonDimensions`, `producerClaims`, `readiness`, and
`stability` fields under `metadata.baselinePolicy`.

Pairwise comparison output also includes
`metadata.baselinePolicy.comparisonDimensions`. This report-only block gives
dashboard consumers one stable location for the comparison context that should
be reviewed before timing: host label/class, target profile, opt level,
comparison window, case categories, command profiles, profiles, targets,
toolchain labels/versions/classes/classifications, required context fields,
missing context fields, and skipped-tool accounting. The raw
`toolchainLabels` list is emitted alongside the richer `toolchains` map so
consumers can group by label without parsing version/class strings. It mirrors
the advisory compatibility result so host, toolchain, target-profile,
optimization, comparison-window, or skipped-tool drift is visible without
turning timing deltas into CI failures.

The same pairwise block includes `metadata.baselinePolicy.producerClaims`.
This preserves producer-declared `advisoryThresholdPolicy` and
`thresholdBaselineReadiness` objects from both top-level report fields and their
`metadata.*` mirrors for the baseline and candidate reports. Each report entry
records whether top-level and metadata mirrors were present, which source was
used for the compact summary, whether the mirrors matched, and a
`readinessReconciliation` object comparing producer-declared
`readyForThresholdBaseline` / `status` values with the comparator-recomputed
readiness. The pair summary counts producer claim mirror mismatches and
producer-vs-comparator readiness disagreements. These fields are provenance for
dashboards only: the comparator still treats recomputed readiness,
compatibility, and structural report shape as the authoritative report-only
curation signals, and producer claim drift never changes comparator exit
status.

The default comparator output also includes a named advisory threshold proposal
profile, `milestone6`, under `timing.advisoryThresholdProfile`. This is a
report-only profile, not a CI gate. It groups proposed maximum timing
regressions by fixture category and benchmark profile so dashboards can show
which cases would need attention if those proposals were enforced later. Each
reported timing regression includes:

- `currentPolicyDisposition`: whether the current comparator run treats the
  change as advisory, within an advisory threshold, advisory-threshold
  exceeded, insufficient repeated evidence, or incomparable metadata.
- `advisoryThreshold`: the matched report-only rule, including category,
  benchmark profile, allowed nanoseconds, exact allowed nanoseconds, raw
  baseline/candidate/delta timings, threshold delta, threshold excess/headroom,
  proposed maximum regression, `ruleSpecificity`, `ruleMatch`, `claimEligible`,
  `claimDisposition`, embedded evidence sufficiency, `enforcement`, and
  `reportOnlyReason`.
- `exceedsAdvisoryThreshold` and `wouldFailAdvisoryProfileIfEnforced`: whether
  the case has an eligible threshold-exceeded claim for the proposed
  report-only profile.
- `measuredExceedsAdvisoryThreshold`: whether the raw elapsed-time delta crosses
  the proposed threshold even if the evidence is insufficient for a claim.
- `explicitThreshold`, `exceedsExplicitThreshold`, and
  `wouldFailExplicitThresholdIfEnforced`: the explicit
  `--max-regression-percent` assessment. This is still report-only in v0 and
  carries the same sufficiency, disposition, and measured-excess fields as the
  advisory profile.

Threshold-exceeded claims require repeated evidence, comparable metadata, and
explicit timed-case identity. The comparator reads case-level
`timing.sampleCount`, falls back to `timing.runs`, and then to
`metadata.measurementWindow.sampleCount` or `comparisonWindow.sampleCount`; both
the baseline and candidate side must carry at least two samples, recognized
host/toolchain/target-profile/optimization/comparison-window/skipped-tool
metadata must be present and compatible, and timed cases must explicitly carry
`fixtureName`, `target`, `profile`, and `optLevel` before
`exceedsAdvisoryThreshold` or `exceedsExplicitThreshold` can become true.
`timing.evidenceSufficiency` summarizes the shared gate with the minimum sample
count, metadata comparability result, explicit identity completeness,
claim-eligibility disposition counts, current policy disposition counts,
insufficient-evidence cases, and separate measured-versus-claimed
threshold-excess case lists for both advisory and explicit thresholds.
`timing.warningSummary` is the compact report-only warning inventory for this
same timing surface. It names slower cases, measured advisory or explicit
threshold excesses, claimed threshold excesses, insufficient-evidence cases, and
untimed cases as warning classes for dashboards and release-note triage. The
summary always carries `mode: report-only` and `failureMode: report-only`; its
warning counts do not affect `status`, `policy.failureClass`, or comparator
exit status.
`timing.advisoryThresholdPolicy`,
`timing.advisoryThresholdProfile`, and `timing.explicitThresholdPolicy` mirror
the same measured-versus-claimed split for their own threshold surface. If
elapsed time exceeds the numeric threshold but the pair lacks repeated evidence,
the timing entry still records `measuredExceedsAdvisoryThreshold` or
`measuredExceedsExplicitThreshold`, but the threshold-exceeded claim is withheld
with `currentPolicyDisposition` set to
`advisory-threshold-insufficient-repeated-evidence`. If metadata drifts or is
missing, the measured excess stays visible and the disposition becomes
`advisory-threshold-incomparable-metadata` for explicit thresholds or
`advisory-incomparable-metadata` for the default advisory profile. If timed-case
identity is partial, the measured excess also stays visible and the disposition
uses `advisory-threshold-incomplete-case-identity` for explicit thresholds or
`advisory-incomplete-case-identity` for the default advisory profile. Per-case
`timingEvidence.claimSuppressionReasons`, `timingEvidence.caseIdentity`,
`advisoryThreshold.evidence`, `explicitThreshold.evidence`, and
`reportOnlyReason` explain why the measured delta remains advisory. This keeps
advisory reports useful without turning one-off timing noise, incomparable
runner metadata, or inferred case identity into a release or CI blocker.

The comparator also emits `timing.thresholdProposalLayer` as a compact
report-only proposal-input layer for offline fixtures and dashboards. It groups
timing observations by baseline/candidate host label and class, raw toolchain
label, toolchain identity and class, target profile, opt level, comparison
window, skipped-tool accounting, fixture category, target, and benchmark
profile. The same object has a separate
`structural` block with the hard-fail structural status and failure reasons, so
consumers do not have to infer whether a threshold observation came from a
structurally valid report pair. Timing observations, measured threshold
excesses, claimed threshold excesses, and per-observation threshold
excess/headroom deltas remain separate lists/counts in each group.
The layer also includes
`timing.thresholdProposalLayer.repeatedReportTrendReadiness`, a report-only
checklist that says whether the current comparison can count as one repeated
report pair toward the documented threshold-proposal release-claim minimum. It
reuses existing structural status, baseline/candidate readiness, metadata
comparability, timing-observation counts, claim-eligibility evidence, and
report-only classification counts. Incomplete readiness records deterministic
blockers such as structural failure, metadata drift, missing claim-eligible
timing evidence, or unstable advisory classifications; it never changes
comparator exit status.

A threshold proposal is not a release claim after a single comparison. Before a
proposal can be promoted into release notes or a future release threshold, keep
at least three repeated report pairs with complete structural shape, compatible
host/toolchain/target-profile metadata, explicit timed-case identity, repeated
baseline and candidate samples, and stable report-only classification. Until
those repeated reports agree, the proposal layer is advisory evidence only and
must not be used as a mandatory CI timing failure.

Use `--advisory-threshold-profile none` when a consumer wants the legacy
advisory timing report without proposed threshold classification:

```sh
python tools/compare_performance_reports.py \
  build/performance-corpus/baseline.json \
  build/performance-corpus/candidate.json \
  --advisory-threshold-profile none
```

To generate the active report-only threshold policy metadata for review or
customization:

```sh
python tools/compare_performance_reports.py \
  --write-advisory-threshold-policy build/performance-corpus/m6-threshold-policy.json
```

To supply a custom report-only policy during comparison:

```sh
python tools/compare_performance_reports.py \
  build/performance-corpus/baseline.json \
  build/performance-corpus/candidate.json \
  --advisory-threshold-policy build/performance-corpus/m6-threshold-policy.json \
  --include-timing-deltas
```

Policy JSON uses the same compact rule shape emitted by the generator:

```json
{
  "schemaVersion": 1,
  "tool": "compare_performance_reports",
  "kind": "advisory-threshold-policy",
  "mode": "report-only",
  "name": "custom-m6",
  "description": "Custom report-only threshold proposals.",
  "enforcement": {
    "mode": "report-only",
    "failureMode": "report-only",
    "enforced": false,
    "hardFail": false,
    "exitStatusAffected": false,
    "releaseBlocker": false,
    "policy": "Timing thresholds are emitted as report-only observations. They are not enforced, do not affect comparator exit status, and cannot become release blockers without explicit owner approval.",
    "releaseBlockerPolicy": "Timing advisory thresholds are report-only and are not release blockers without explicit owner approval."
  },
  "evidencePolicy": {
    "metadataComparabilityPolicy": "Timing threshold claims require matching recognized host, toolchain, target-profile, optimization, comparison-window, and skipped-tool metadata on both reports. Metadata drift is advisory context only; it never changes comparator exit status.",
    "minimumSampleCount": 2,
    "policy": "Timing threshold claims require repeated baseline and candidate samples and comparable baseline-policy metadata, with explicit timed-case fixtureName, target, profile, and optLevel identity. Cases without at least two samples on both sides, pairs with missing/drifting metadata, or timed cases that rely on inferred identity are reported as timing observations, but threshold-exceeded claims are withheld.",
    "requiresComparableMetadata": true,
    "requiresExplicitTimedCaseIdentity": true,
    "requiresRepeatedBaselineAndCandidateSamples": true
  },
  "failurePolicy": "report-only; advisory timing threshold observations never change comparator exit status",
  "releaseBlockerPolicy": "Timing advisory thresholds are report-only and are not release blockers without explicit owner approval.",
  "ruleCount": 1,
  "rules": [
    {
      "category": "storage-buffers",
      "profile": "release",
      "maxRegressionPercent": 12,
      "label": "release storage buffer compile lane",
      "ruleSpecificity": "category-profile"
    }
  ]
}
```

Policy files supplied through `--advisory-threshold-policy` are validated as
tool configuration before any report comparison runs. They must include the
same `schemaVersion`, `tool`, `kind`, `mode`, `name`, `description`,
`enforcement`, `evidencePolicy`, `failurePolicy`, `releaseBlockerPolicy`,
`ruleCount`, and `rules` fields emitted by the generator. The enforcement and
evidence policy text must match the comparator's report-only contract, so a
custom policy cannot quietly turn timing observations into CI failures or
release blockers.

When a custom or generated policy is active, the comparator keeps the legacy
`timing.advisoryThresholdProfile` and `timing.advisoryThresholdPolicy` fields and
also emits `timing.advisoryThresholds`. That compact summary records the policy
source (`builtin` or `file`), normalized policy metadata, matched/unmatched case
counts, measured threshold excesses, claim-eligible threshold excesses, and
insufficient-evidence cases. These fields are advisory classification only:
they do not change `status`, `policy.failureClass`, or CI exit behavior.
Rules generated by the comparator also carry `ruleSpecificity`, one of
`category-profile`, `category-only`, `profile-only`, or `fallback`. Per-case
threshold annotations mirror that value under `advisoryThreshold.ruleSpecificity`
and include `advisoryThreshold.ruleMatch` with the case category, target, and
benchmark profile plus exact/wildcard match modes. The compact policy summaries
and `timing.thresholdProposalLayer` groups include `ruleSpecificityCounts` so
dashboards can distinguish exact lane evidence from broad fallback evidence
without turning either class into a timing gate.
The comparator self-test pins this contract with checked-in policy fixtures under
`tests/performance`: the generated default policy fixture, a compact custom
report-only policy fixture, and malformed policy fixtures for duplicate rules,
non-report-only mode, missing enforcement metadata, missing evidence policy, and
release-blocker policy drift. Policy files are also rejected when `ruleCount`
does not match `rules`, required `name`, `description`, `enforcement`,
`evidencePolicy`, `failurePolicy`, or `releaseBlockerPolicy` fields are missing
or malformed, rule `label` fields are present but empty, or enforcement/evidence
metadata contradicts report-only semantics. If present, `ruleSpecificity` must
match the rule's category/profile wildcard shape.
Malformed policy files fail as configuration errors; they do not produce
comparison JSON or convert timing deltas into mandatory CI failures.

The comparator also surfaces baseline policy metadata for both reports. The
`metadata.baselinePolicy.compatibility` block lists missing fields, added
fields, toolchain/version changes, skipped-tool accounting changes, and scalar
metadata mismatches. This compatibility block is intentionally advisory so a
trend job can publish evidence from imperfect runners without creating flaky
timing gates. Treat incompatibilities as a reason to avoid promoting that pair
to a release threshold baseline until a matching host/toolchain class has enough
history.
When baseline policy aliases are present, they must be well-formed. Scalar
host/toolchain/target-profile/optimization fields must be non-empty strings, and
`comparisonWindow` aliases must be objects with non-negative `sampleCount` and
`warmupCount` plus a non-empty `unit`. Malformed baseline policy fields are
report-shape issues because consumers cannot tell whether timing evidence is
comparable; missing fields remain advisory context under `missingFields`.

`metadata.baselinePolicy.producerClaims` keeps producer-declared threshold
policy provenance visible without making it authoritative. For baseline and
candidate reports, the comparator copies any top-level
`advisoryThresholdPolicy` and `thresholdBaselineReadiness` object plus the
matching `metadata.advisoryThresholdPolicy` and
`metadata.thresholdBaselineReadiness` mirrors, summarizes their report-only
fields, and reports mirror mismatches. The readiness reconciliation compares
the producer-declared readiness claim with the comparator-recomputed readiness
below. A producer claim can be stale, missing, or contradictory; that is
reported for dashboards but never changes comparator status or timing
threshold enforcement.

The same metadata block includes `metadata.baselinePolicy.readiness`, a
report-only promotion hint for baseline curation. A report is marked
`readyForThresholdBaseline` only when it has complete recognized run context,
at least one timed case, repeated timing evidence for every timed case, no
report-shape validation issues, no package/build functional failures, no
required or unclassified skipped-tool coverage, and no skipped cases missing
unavailable-tool evidence. Missing readiness does not change comparator exit
status; it is meant to keep dashboards useful while making it obvious which
passing reports are still too weak for future threshold proposals.
`compatibleReadyPair` is true only when both reports are individually ready and
their baseline policy metadata is compatible.
Each readiness object also includes a deterministic
`thresholdBaselineRequirements` checklist with report-only pass/fail evidence
for recognized context fields, timed cases, repeated timing evidence, clean
report shape, functional success, required tool coverage, and skipped-tool
evidence. The companion
`unsatisfiedThresholdBaselineRequirements` and
`satisfiedThresholdBaselineRequirementCount` fields let dashboards explain why a
report is incomplete without turning missing metadata or timing noise into a CI
failure.

The same metadata block also includes `metadata.baselinePolicy.stability`.
This compact report-only section compares the baseline and candidate timed
samples for each normalized case and records host, toolchain, target-profile,
optimization, profile, target, and fixture-category dimensions. It reports
stability requirements, per-case spread, dimension mismatches, and a
`stableEnoughForThresholdBaseline` curation hint. The current hint requires a
compatible ready pair, at least one comparable timed case, matching stability
dimensions, and no case exceeding the advisory 10% spread-from-minimum
recommendation. This stability assessment never changes comparator exit status;
it is only evidence for future threshold-baseline promotion.

Aggregate mode carries the same readiness summary per report under
`reports[].baselineReadiness`, counts ready reports in
`summary.reportsReadyForThresholdBaselineCount`, and counts ready reports per
baseline group in `baselineGroups[].reportsReadyForThresholdBaseline`. This lets
trend jobs separate useful advisory evidence from reports that are suitable for
threshold-baseline promotion without adding timing-based CI failures.
It also emits report-only baseline stability evidence from repeated timed
samples with the same normalized case and baseline dimensions. Stability
classes such as `single-sample`, `identical`, and `variable` are descriptive
inventory only; they do not propose target-specific thresholds and never change
aggregate exit status.

Advisory threshold profiles and supplied policy files are validated before
comparison. A malformed profile definition, such as duplicate category/profile
rules or unreachable rules after an earlier wildcard match, is a tool
configuration error and exits with a usage-style comparator failure. Valid
advisory threshold profiles remain report-only and do not create timing-based CI
failures.

The `structure` block separates structural policy from timing deltas. It lists
missing command profiles, changed per-case command profiles, role-aware
toolchain classifications, optional skipped-tool labels, and candidate
functional failures. Candidate package/build failures are structural failures:
they should be fixed as functional regressions rather than explained away as
missing or noisy benchmark timings.
The block also carries `failed`, `failureMode`, `mode`, `failureReasons`, and
explicit missing case/category/profile/target/toolchain counts so report
consumers can identify hard structural report-shape failures without deriving
them from timing output.
When structural loss and an explicit timing threshold excess are both present,
`policy.failurePriority` lists only the hard structural class and
`policy.failureClass` remains `structural`. Timing observations are still
reported, and threshold-exceeded claim lists are populated only when the pair
also satisfies the repeated-sample and metadata-comparability advisory evidence
rules. Neither measured timing excess nor threshold claim evidence changes the
comparator exit status.

Both `timing.advisoryContext` and `artifactSize.advisoryContext` carry the
recognized host, toolchain, target-profile, optimization, comparison-window, and
per-case profile/target/category context used by advisory output. When a field
is absent from the report shape, the context block lists it in `missingFields`.
This keeps trend uploads honest about incomplete host/toolchain evidence without
turning metadata drift into a timing failure.

Add an explicit report-only tolerance to annotate timing regressions:

```sh
python tools/compare_performance_reports.py \
  build/performance-corpus/baseline.json \
  build/performance-corpus/candidate.json \
  --max-regression-percent 10
```

The comparator emits stable JSON with the structural comparison, timing policy,
comparable timed-case count, untimed cases, and any threshold excesses. It does
not run benchmarks itself, so CI can self-test it with synthetic reports without
adding native toolchain cost or timing gates.
The top-level `policy.timing.advisoryThresholds` summary is the compact policy
surface for dashboards and release notes: it records the active report-only
threshold source/profile, required host/toolchain/profile metadata fields,
baseline and candidate `missingFields`, metadata compatibility, measured
threshold excess count, and claimed threshold excess count. Structural failures
remain the only hard-fail surface; timing threshold excesses are reported under
this policy summary and under `timing.advisoryThresholds` without changing the
comparator exit status.
Threshold math uses decimal arithmetic and rounds the exact allowed nanosecond
limit up to the next integer nanosecond. For example, a 12.5% threshold on a
101ns baseline records `allowedNsExact = "113.625"` and `allowedNs = 114`; a
114ns candidate is still within the report-only threshold, while 115ns is an
excess. The exact and rounded values are emitted in both explicit and advisory
threshold annotations so dashboards can explain the boundary. Each annotation
also records `thresholdDeltaNs` (`candidateNs - allowedNs`),
`thresholdExcessNs`, `thresholdHeadroomNs`, and
`thresholdDeltaPercentOfAllowed`; positive threshold deltas remain advisory and
do not change comparator exit status.

To aggregate several saved advisory reports without selecting a baseline pair,
use aggregate mode:

```sh
python tools/compare_performance_reports.py \
  --aggregate \
  build/performance-corpus/linux-pool-a.json \
  build/performance-corpus/linux-pool-b.json \
  build/performance-corpus/macos-metal.json
```

Aggregate mode is report-only. It reads one or more reports, validates their
shape, and exits successfully for readable reports while recording validation
issues under `validation` and per-report `validationIssues`. It does not apply
timing thresholds, evaluate timing regressions, or create CI timing failures.
The output includes:

- `baselineGroups`: explicit groups by host label/class, target profile,
  optimization level, and toolchain/version/role/availability. Each group also
  includes `timingStability`, a report-only summary of repeated timed samples
  observed for that baseline group.
- `baselineStability`: aggregate report-only stability counts for exact
  normalized case/baseline-dimension groups, including sample counts, stability
  class counts, and maximum observed spread.
- `caseDimensionGroups`: deterministic case summaries grouped by host,
  toolchain, target, fixture category, command profile, and optimization level.
- `caseStabilityGroups`: exact normalized-case timing evidence grouped by host,
  toolchain, target profile, optimization level, fixture category, benchmark
  profile, command profile, target, and fixture name. Each group reports
  min/median/average/max elapsed nanoseconds, spread, percent spread from the
  minimum sample, source reports, and per-sample threshold-baseline readiness.
- `coverage`: the union of categories, targets, profiles, command profiles, and
  optimization levels seen across the input reports, plus native optimization
  status, native-profile evidence-status coverage, and native artifact
  descriptor optimizer evidence-status coverage, including cases where no native
  profile or descriptor was declared.
- `nativeOptimization`: aggregate report-only native optimization status and
  evidence coverage counts, including descriptor optimizer status and
  descriptor evidence coverage when present. These counts are also reflected in
  `summary`, each `reports[]` entry, `baselineGroups`, and
  `caseDimensionGroups`.
- `thresholdBaselineReadiness`: aggregate report-only readiness accounting for
  future threshold-baseline promotion. It counts ready and incomplete reports,
  groups blockers by readiness reason, unsatisfied requirement, missing context
  field, and insufficient repeated-sample evidence, and mirrors summary counts
  without changing aggregate exit status.
- `thresholdReleaseClaimReadiness`: aggregate report-only release-claim review
  readiness by baseline group. A group needs at least three ready reports, clean
  aggregate validation, all reports ready for threshold-baseline use, timed-case
  stability evidence, at least three samples per timed case, and no spread above
  the advisory stability recommendation. This block is review evidence only: it
  never promotes timing thresholds automatically and never changes aggregate
  exit status.
- per-report `missingCategories`, `missingTargets`, `missingCommandProfiles`,
  `missingProfiles`, and `missingOptLevels`.
- `skippedToolAccounting`: skipped cases grouped by unavailable tool, including
  optional tool skips.

Use aggregate output for dashboards, trend uploads, baseline inventory, and
future threshold-curation evidence. A variable stability group means the
measurements need more investigation or more samples before anyone should use
them to justify an advisory threshold; it is not a failure. Use the pairwise
comparator when a job needs hard structural coverage checks between one
baseline and one candidate.

When a report consumer needs every comparable timing delta, enable the
report-only delta list:

```sh
python tools/compare_performance_reports.py \
  build/performance-corpus/baseline.json \
  build/performance-corpus/candidate.json \
  --include-timing-deltas
```

`--include-timing-deltas` does not change pass/fail behavior. Timing thresholds
and timing deltas remain report-only.

The comparator also emits an `artifactSize` advisory section from
`case.artifactSummary.byteSize` when both reports have available artifacts for a
case. Candidate byte-size increases are listed under
`artifactSize.advisoryIncreases`, but they do not fail the comparison. Cases
without available artifact size metadata are listed under
`artifactSize.unsizedCases`; dry-run and skipped cases normally appear there.
`artifactSize.warningSummary` is the compact report-only warning inventory for
the same artifact-size surface. It lists byte-size increase cases, cases without
comparable size evidence, and zero-count threshold-excess fields because
artifact-size thresholds are not supported in v0. The summary always carries
`mode: report-only` and `failureMode: report-only`; its warning counts do not
affect `status`, `policy.failureClass`, or comparator exit status.
When both reports include runner `case.artifactSummary.manifestArtifacts`
records, the comparator also reports
`artifactSize.manifestArtifactKindEvidence`. This report-only section compares
manifest artifact kinds such as `nativeBinary`, `backendSource`,
`debugMetadata`, `hirSourceMap`, and `nativeArtifactDescriptor` by declared
record count, emitted count, missing count, and emitted bytes. Changed cases are
listed under `artifactSize.manifestArtifactKindEvidence.deltas`; unchanged
missing manifest artifacts remain visible in each changed case's per-kind
entries. This evidence is advisory and separate from timing thresholds and hard
artifact-size gates.
When a producer includes `summary.manifestArtifactKinds`, the comparator also
checks that the summary matches case-level manifest artifact records. Mismatches
are report-shape issues because consumers cannot trust stale artifact
accounting, but the artifact-size evidence itself remains report-only.

To include every comparable artifact byte-size delta, use:

```sh
python tools/compare_performance_reports.py \
  build/performance-corpus/baseline.json \
  build/performance-corpus/candidate.json \
  --include-size-deltas
```

`--include-size-deltas` is report-only. There is no mandatory artifact-size
regression gate in the default comparator.

When a trend-upload job should produce a report even if `cglc` is not present,
use:

```sh
python tools/benchmark_performance_corpus.py \
  --root . \
  --cglc build/cglc \
  --profile release \
  --target directx \
  --skip-unavailable-tools
```

That mode emits skipped cases and `toolAvailability.cglc.status =
"unavailable"` instead of recording timings.

The `native-package` profile requests native validation in the report metadata.
It can require host native tools for targets such as Metal or Vulkan. Do not add
heavyweight native corpus execution to default CI; use dry-run/list checks in
default jobs and schedule real measurements separately.
