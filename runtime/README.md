# CrossGL Runtime Package Reader Prototype

This directory contains the narrow runtime-side `.cglb` package reader
prototype for the Milestone 5 loader-admission boundary. The reader opens a
directory or zip package, reads `manifest.json`, `reflection.json`,
`diagnostics.json`, and optional debug sidecars such as
`artifacts.debugMetadata` and `artifacts.targetExplanation`, and resolves the
target artifact paths declared in `manifest.artifacts`.

The prototype does not parse CrossGL source and does not depend on Metal,
Vulkan, DirectX, OpenGL, shader compilers, or native graphics loaders. It does
not create graphics API objects and does not execute a device workload. Its job
is to define the small runtime-facing handoff a later graphics runtime can use:

- package module and target identity,
- reflected entry-point/resource metadata,
- build diagnostics metadata,
- optional debug metadata summary,
- target/package mode classification,
- package-relative artifact discovery,
- native-vs-source runtime artifact selection,
- deterministic target/package-mode artifact selection,
- reflected entry-point/resource binding lookup,
- required artifact lookup and byte/text loading,
- runtime compatibility reporting for the v0 package contract,
- target-neutral loader plan construction,
- source-free directory/zip loader admission,
- a metadata-only loader contract summary for CI-facing admission checks.

Use `read_package()` for a permissive package summary. Missing declared
artifact files are recorded with `exists: false` and `size: null`, which keeps
metadata inspection useful for incomplete packages. Loader code that needs a
specific artifact should opt into strict access:

```python
from runtime.package_reader import read_package

package = read_package("shader.cglb")
source = package.read_artifact_text("backendSource")
native_binary = package.read_artifact_bytes("nativeBinary")
```

For loader-oriented selection, use the package mode and runtime artifact helpers
instead of interpreting `manifest.json` directly:

```python
target, mode = package.target_package_mode()
artifact = package.runtime_artifact()          # native when emitted/validated
entry = package.require_entry_point("compute", "main")
binding = package.require_resource_binding("compute", "OutputBuffer")
target_binding = package.require_target_resource_binding("compute", "OutputBuffer")
```

Before a runtime loader consumes a package, use the compatibility report to keep
the runtime boundary explicit:

```python
report = package.compatibility_report(loader_target="metal")
report.require_compatible()

print(report.required_artifacts)
print(report.available_targets)
print(report.to_summary()["availableArtifacts"])
print(report.to_summary()["missingArtifacts"])
print(report.to_summary()["targetAvailability"])
print(report.availability_summary["artifacts"]["runtime"])
print(report.to_summary()["artifactCompatibility"]["accepted"])
```

Use `read_compatibility_report()` when a loader needs a compatibility decision
even if `read_package()` would reject the package, for example because the
manifest schema version is newer than the prototype supports:

```python
from runtime.package_reader import read_compatibility_report

report = read_compatibility_report("shader.cglb", loader_target="vulkan")
if report.skip_reasons:
    print(report.to_summary()["skipReasons"])
```

Use `read_loader_plan()` when target-specific loader code needs the runtime
handoff in one object:

```python
from runtime.loader import read_loader_plan

plan = read_loader_plan("shader.cglb", "metal", package_mode="auto")
plan.require_loadable()

primary_artifact = plan.require_runtime_artifact()
print(primary_artifact.name, primary_artifact.package_path)
for artifact in plan.selected_artifacts:
    print(artifact.name, artifact.package_path)

entry = plan.require_entry_point("compute", "main")
target_binding = plan.require_target_resource_binding("compute", "OutputBuffer")
```

For a complete source-free loader-boundary example, run:

```sh
python -m runtime.examples.source_free_loader runtime/examples/fixtures/source-free-metal-native.cglb metal --json
python -m runtime.examples.source_free_loader runtime/examples/fixtures/source-free-vulkan-native.cglb vulkan --json
python -m runtime.examples.source_free_loader runtime/examples/fixtures/source-free-directx.cglb directx --json
python -m runtime.examples.source_free_loader runtime/examples/fixtures/source-free-directx-emitted-dxil.cglb directx --json --native-admission
python -m runtime.examples.source_free_loader runtime/examples/fixtures/source-free-opengl.cglb opengl --json
python -m runtime.examples.source_free_loader runtime/examples/fixtures/future-schema-directx.cglb directx --json
python -m runtime.examples.source_free_loader runtime/examples/fixtures/source-free-metal-native.cglb metal --json --native-admission
python -m runtime.examples.source_free_loader runtime/examples/fixtures/source-free-opengl.cglb opengl --json --native-admission
```

The example fixtures are packages, not CrossGL source inputs. They may be
directory packages or source-free zip-backed `.cglb` packages with metadata at
the archive root or under one top-level directory. The loadable Metal fixture
exposes generated `backendSource`, `intermediate`, and `nativeBinary` artifacts
and contains no `.cgl` source file; `auto` mode selects the `nativeBinary`
because `manifest.target`, `manifest.artifacts`, `reflection.target`, and
reflected target bindings agree on `metal`. The loadable DirectX fixture
exposes a generated `backendSource` artifact and reflection binding metadata
while leaving the planned `nativeBinary` absent, so no DXC or device runtime is
needed. The emitted DirectX DXIL fixture keeps DirectX in its source-package
policy, records `nativeBinaryStatus: "emitted"`, and ships committed HLSL plus
fake `.dxil` bytes with a native artifact descriptor whose hash and `sizeBytes`
claims match the checkout. It demonstrates an accepted
`directxNativeApiBoundary` without running DXC, D3D, a shader validator, or a
device. The future-schema fixture keeps declared artifacts present but is
rejected from manifest schema metadata before any artifact or source fallback
can be used.
The optional `--native-admission` flag adds a compact
`nativeBackendAdmission` block from the backend-native loader planner for
Metal, Vulkan, DirectX, or OpenGL. It remains metadata-only: the planner does
not parse CrossGL source, invoke `cglc`, compile backend source, or execute a
graphics API. OpenGL native admission is reported as a structured rejection
rather than executable native readiness.
Zip-backed package admission uses the same metadata-only contract as directory
packages. The reader first indexes safe package-relative archive members,
accepts root metadata either at the archive root or under one top-level package
directory, and rejects ambiguous duplicate members after normalizing `.` and
repeated separator aliases. Undeclared `.cgl`
members, sibling filesystem `.cgl` files, and unsafe archive paths are not
runtime inputs. Loader plans expose selected artifacts as `archive!/member`
paths and keep `metadataContract["sourceInputs"]` empty; missing or malformed
zip metadata becomes structured compatibility diagnostics instead of a compiler
or source fallback.
Metal native loader summaries also include `metalNativeAdmission`, a
loader-facing `.metallib` admission detail for a future real Metal API loader.
It records the manifest target and artifact contract, the selected
`nativeBinary` `.metallib` path/size/suffix facts, manifest-declared
`nativeArtifactDescriptor` target, binary kind, artifact path, artifact hash,
validation status, and size facts, plus reflected Metal entry points and buffer
binding indices. `metalNativeApiBoundary` is the narrower native API handoff
sketch for a future Metal runtime: it exposes only `.cglb` metadata inputs such
as the `.metallib` artifact path/hash, descriptor freshness facts, reflection
resources, target binding indices, and loader version compatibility. The
boundary is still metadata-only and reports `sourceInputs: []`,
`sourceParsingRequired: false`, `compilerInvocationRequired: false`,
`deviceExecutionRequired: false`, and Metal work flags such as
`metalDeviceCreationPerformed: false`, `metalLibraryCreationPerformed: false`,
and `metalCommandExecutionPerformed: false`. Missing or stale descriptor
`artifactPath`, `artifactHash`, or `sizeBytes` facts remain fail-closed
compatibility diagnostics instead of a source parser, compiler, or Metal device
fallback.
DirectX native loader summaries also include `directxNativeApiBoundary`, a
metadata-only D3D handoff sketch for future DXIL/DXBC loading. It records the
declared `nativeBinary` identity, DXIL/DXBC binary kind and suffix facts,
manifest `nativeBinaryStatus`, native artifact descriptor schema/contract,
target, binary kind, artifact path/hash/size freshness, reflected HLSL
register/space bindings, and loader version compatibility. The boundary stays
source-free and runtime-free: `sourceInputs: []`,
`sourceParsingRequired: false`, `compilerInvocationRequired: false`,
`deviceExecutionRequired: false`, `d3dRuntimeCallsPerformed: false`,
`d3dDeviceCreationPerformed: false`, `d3dShaderModuleCreationPerformed: false`,
`d3dPipelineCreationPerformed: false`, and
`d3dCommandExecutionPerformed: false`.
The Vulkan source-free fixture exercises the same native-selection boundary
with a declared `.spv` artifact. The OpenGL fixture exercises the v0
source-package boundary: `auto` selects `backendSource`, keeps planned GLSL
evidence metadata-only, and reports native admission as a structured
`opengl_loader.native_mode_unsupported` rejection.
Missing compiler version metadata, unsupported compiler identity, and
incompatible root metadata schema versions are reported as structured
compatibility diagnostics and carried through loader plans before any artifact
dispatch. Loader plans leave `selected_artifacts` empty for those packages
instead of inferring compatibility from artifact names, package source, or
backend file extensions.

The loader facade is target-neutral. It reads the package through
`read_compatibility_report()`, selects only artifacts required by the reported
package contract, and returns the report diagnostics alongside the selected
artifact paths. It also exposes reflected entry points, generic resource
bindings, and target-specific resource binding facts from `reflection.json` so a
target loader can bind generated artifacts without opening CrossGL source. If
the package target does not match the loader target, a required artifact is
missing, or the package has no known runtime target contract, `plan.loadable` is
`False` and `selected_artifacts` is empty. The diagnostic reason is available in
`plan.reject_reasons`, `plan.skip_reasons`, and
`plan.to_summary()["diagnostics"]`. The plan summary also mirrors the
compatibility report's `availableTargets`, `targetAvailability`, `availability`,
`artifactAvailability`, and `diagnosticSummary` slices so loaders can
distinguish source-only planned native binaries from rejected missing artifacts
without parsing diagnostic text or package source. The summary also includes
`loaderDiagnostics`, which separates package compatibility diagnostics from
requested artifact-selection diagnostics. This lets a target loader report, for
example, that the package metadata is otherwise compatible but a caller asked
for `package_mode="native"` while the package only declares a planned native
binary. The summary includes
`selectedTarget`, `runtimeArtifactPath`, `requiredArtifactPaths`,
`artifactCompatibility`, and `reflectionResources` so target dispatch code can
hand off package-declared artifact paths and reflected resource facts without
opening CrossGL source. It also includes `metadataContract`, a deterministic
summary of the metadata documents, manifest-declared artifact inputs,
reflection inputs, runtime artifact, and source-free policy a loader is allowed
to consume. Loader-plan summaries explicitly report `requiredMetadataInputs`
for the root `manifest.json`, `reflection.json`, and `diagnostics.json`
documents; `artifactSelection` for the normalized `auto`, `native`, or
`source-package` selection mode and selected runtime artifact; and
`targetCompatibility` for target-match diagnostics sourced from package
metadata. The same blocks are mirrored through `metadataContract` and
`loaderDiagnostics`, and `versionCompatibility` summarizes compiler identity
and supported schema-version checks. `metadataContract["sourceInputs"]` is
always empty,
`metadataContract["sourceParsingRequired"]` is `false`, and the contract records
that no compiler invocation or device execution is part of this prototype
boundary. Loader plans also fail closed before artifact dispatch if a required
manifest artifact path points at a CrossGL source input such as `*.cgl`; this
adds `package.artifact.source_input_leakage` to the plan's compatibility report
instead of exposing that source path as a loader input.
`RuntimeLoaderPlan.to_summary()` mirrors the loader metadata contract's
`packageArtifactRequirements` and `packageArtifactRequirementsSource` at the
top level and inside `runtimeArtifactAdmission`. Shared source-free native
backend summaries mirror the same fields at the top level and inside
`nativeAdmission`, and the source-free loader example carries them through
optional `nativeBackendAdmission`. Consumers can distinguish recorded
`manifest.packageArtifactRequirements` from report-only `legacy-v0-target-contract`
fallback without expanding the full compatibility report.
Backend-specific admission and API-boundary blocks mirror the same fields:
DirectX source-package admission and native API boundaries, Metal native
admission and API boundaries, Vulkan native admission and API boundaries, and
OpenGL source-package admission all report the same requirement source and
normalized requirement summary as their enclosing loader plan.
Native artifact descriptors are summarized through the same metadata-only
runtime boundary. Loader-facing descriptor summaries may report
`sourcePathDeclared: true` so a runtime can tell that compiler-side provenance
named a source input, but raw `sourcePath` is not exposed inside descriptor
`fields`. Source paths stay provenance metadata for compiler/package tools, not
runtime loader inputs. `optimizationEvidence` is preserved as a whitelisted
metadata summary, but descriptors that claim applied optimization must also
declare a known concrete `optimizationLevel` and produced artifact facts
(`artifactPath`, `artifactHash`, and `sizeBytes`); planned native descriptors
must keep optimization evidence metadata-only.
Malformed declared `toolchainProvenance.tools` fields also fail closed: invalid
tool identity or host-probe fields such as `name`, `role`, `version`,
`executable`, `resolvedExecutable`, `executableSource`, or
`versionProbeStatus` become structured
`package.native_artifact_descriptor.toolchain_provenance_tool_*` diagnostics
instead of being ignored or repaired by probing host tools.
Vulkan `nativeProfile` metadata is admitted the same way. After the profile
schema and target are accepted, its declared `backendAssembly` and
`nativeBinary` fields must match the corresponding `manifest.artifacts` paths
when those artifacts are declared. Missing or stale profile links emit
`package.native_profile.backend_assembly_*` or
`package.native_profile.native_binary_*` diagnostics, and loader plans leave
`selected_artifacts` empty instead of selecting a native artifact from
conflicting sidecar metadata.

## V0 Runtime Admission Semantics

Milestone 5 admission is metadata-only. `read_loader_plan()` and
`select_runtime_artifact()` consume manifest, reflection, diagnostics, optional
debug metadata, and declared artifact bytes. They never parse `.cgl` source,
never invoke `cglc` or target shader compilers, and never create Metal, Vulkan,
DirectX, or OpenGL runtime objects. Loader-plan summaries report
`sourceParsingRequired: false`, `compilerInvocationRequired: false`, and
`deviceExecutionRequired: false`.

Runtime artifact selection is deterministic:

- `package_mode="auto"` selects a usable `nativeBinary` when package metadata
  proves the artifact is ready. For source-package targets this means
  `nativeBinaryStatus` is `emitted` or `validated`; for native targets such as
  Metal and Vulkan, the target contract forbids `nativeBinaryStatus` and the
  declared `nativeBinary` file must exist. If no usable native artifact exists,
  `auto` falls back to `backendSource` only for source-package targets.
- `package_mode="native"` requires a usable `nativeBinary` and reports planned
  or missing native artifacts as structured diagnostics.
- `package_mode="source-package"` and the alias `source` require generated
  `backendSource` and intentionally do not select optional `nativeBinary`
  artifacts.

Native backend admission is stricter than target-neutral artifact selection.
When `manifest.packageArtifactRequirements.packageMode` is recorded as
`native`, the shared native backend planner requires a manifest-declared
`nativeArtifactDescriptor` before reporting the plan ready. This keeps recorded
native package admission tied to descriptor metadata for target, binary kind,
hash, and size freshness. Legacy generated target contracts remain report-only
compatibility data and do not retroactively require new descriptor metadata.

Current target admission behavior:

| Target | V0 package contract | Loader admission behavior |
| --- | --- | --- |
| `metal` | native | `auto`/`native` select the `.metallib` `nativeBinary` when required metadata, reflection, and descriptor facts agree. |
| `vulkan` | native | `auto`/`native` select the `.spv` `nativeBinary`; target metadata must stay Vulkan-specific before dispatch. |
| `directx` | source-package | `auto` selects emitted DXIL when `nativeBinaryStatus: "emitted"` and the `.dxil` exists; otherwise it selects HLSL `backendSource`. `source-package` always selects HLSL. `plan_directx_native_loader()` exposes metadata-only `directxNativeApiBoundary` facts for future D3D/DXIL or DXBC handoff without DXC, D3D device creation, shader module creation, pipeline creation, or command execution. |
| `opengl` | source-package | `validated` means validator-backed GLSL source evidence, not portable OpenGL program binary evidence. `auto` and `source-package` select GLSL `backendSource`; `native` rejects with an explicit v0 source-package-only diagnostic. |

For admission checks that only need the one artifact a target loader should
consume first, use `select_runtime_artifact()` on an existing compatibility
report:

```python
from runtime.package_reader import read_compatibility_report, select_runtime_artifact

report = read_compatibility_report("shader.cglb", loader_target="directx")
selection = select_runtime_artifact(
    report, target="directx", package_mode="source-package"
)
selection.require_selected()
print(selection.to_summary()["artifact"])
```

`package_mode="auto"` deterministically prefers a metadata-proven ready
`nativeBinary`; if no native binary is usable, it falls back to `backendSource`
only for source-package targets. `package_mode="native"` requires an
emitted/validated `nativeBinary`, while `package_mode="source-package"` requires
the generated backend source and does not select optional native binaries.
Selection failures reuse compatibility diagnostics and add structured
package-mode or missing-artifact reasons such as
`package.native_binary_status.not_ready` and
`package.artifact.selection_file_missing`. The selector never opens CrossGL
source and never invokes `cglc`.
Selection summaries also include an `admission` object that separates target
admission, native artifact admission, and source-package fallback admission so
loaders can report target mismatches, unsupported or unavailable native
contracts, planned-only native binaries, and accepted generated-source fallback
without parsing diagnostic prose. Missing or unreadable `manifest.target`
metadata is carried into the runtime artifact selection target admission as a
`target-unavailable` rejection, so callers do not need to infer that state from
generic load failure.

When `manifest.artifacts.debugMetadata` is declared and the file exists, the
reader parses it as raw JSON and exposes a lightweight
`DebugMetadataRecord` summary. `manifest.artifacts.targetExplanation` is
accepted as a normal optional artifact; callers can read it through the
artifact API when they need the compiler's target-explanation sidecar:

```python
debug_metadata = package.require_debug_metadata()
record = package.debug_metadata_record()
print(debug_metadata["schemaVersion"])
print(record.selected_target if record else None)
```

Compatibility reports also include a metadata-only
`targetLegalizationEvidence` summary. When debug metadata declares explicit
target-legalization evidence, or when a target-explanation sidecar is present,
the runtime checks the recorded target, package mode, package-build support
flag, and package-artifact requirement evidence IDs against
`manifest.target` and `manifest.packageArtifactRequirements`. Drift is reported
with `package.target_legalization_evidence.*` diagnostics; malformed evidence
arrays are rejected instead of being treated as absent metadata. The check uses
only declared JSON sidecars and works the same for directory and zip packages.

The report records compiler name/version metadata, runtime-supported schema
versions, root metadata schema compatibility, the target artifact contract,
available artifact files, reflection entry-point/resource binding availability,
diagnostics metadata availability, optional debug metadata availability, and
structured reject/skip reasons. It also exposes `status`,
`available_targets`, `target_availability`, `availability_summary`,
`artifactAvailability`, `artifactCompatibility`, and `diagnosticSummary` so
loaders can distinguish `compatible`, `source-only`, `missing-artifact`,
`unsupported-version`, `target-mismatch`, `unsupported-target`, and generic
`incompatible` reports without parsing diagnostic messages. The
`admission` object gives the same decision in a loader-oriented shape: target
admission distinguishes loader mismatches from unsupported or unavailable
targets, requirements admission records whether
`manifest.packageArtifactRequirements` was declared or legacy-inferred, and
fallback admission records that runtime reads never parse source or invoke a
compiler fallback.
`artifactCompatibility` object groups manifest artifacts into `accepted`,
`rejected`, and `skipped` records for the requested loader target. Rejected
records carry the artifact-specific or package-level diagnostics that block
use; skipped records cover target mismatches, optional artifacts outside the
runtime contract, and planned source-package native binaries that do not need
bytes yet. A declared debug metadata sidecar is also fail-closed: if its
`schemaVersion` does not match the runtime-supported debug metadata schema, the
report emits `package.debug_metadata.schema_incompatible`, reports
`status: "unsupported-version"`, and loader plans leave `selected_artifacts`
empty instead of ignoring the newer sidecar or falling back to CrossGL source.
Malformed `diagnostics.json` record metadata is also rejected instead of being
treated as absent diagnostics. A non-array `diagnostics` field, non-object
entries, or non-string/non-empty `severity` values emit
`package.diagnostics.records_invalid`,
`package.diagnostics.record_invalid`, or
`package.diagnostics.severity_invalid`; `diagnosticsMetadata["valid"]` and
`diagnosticsMetadata["recordShapeValid"]` let loaders report the malformed
contract field without inspecting CrossGL source.
Available targets are derived only from explicit, target-compatible package
metadata. The runtime reports `manifest.target`, and only reflected target
resource bindings/features whose `target` exactly matches that manifest target;
stale, malformed, or future target records become diagnostics and do not add
advertised target support. It never infers extra targets from source files or
backend file names. It always reports
`sourceParsingRequired: false`, `compilerInvocationRequired: false`,
`deviceExecutionRequired: false`, and `sourceInputs: []`.
Runtime consumers must treat `.cglb` packages as manifest/reflection/artifact
metadata plus declared artifact bytes; CrossGL source parsing stays on the
compiler side of the boundary.

The compatibility report also rejects stale cross-document metadata before
artifact selection. If `reflection.nativeBinary` no longer matches
`manifest.artifacts.nativeBinary`, or reflected target-specific records such as
`targetResourceBindings` and `targetFeatures` name a different target from
`manifest.target`, the report returns structured errors like
`package.reflection.native_binary_mismatch`,
`package.reflection.target_resource_binding_target_mismatch`, or
`package.reflection.target_feature_target_mismatch`. Loader plans leave
`selected_artifacts` empty for those packages rather than trusting backend file
names or package source as a fallback.
Malformed reflected handoff fields are rejected the same way: invalid
`reflection.nativeBinary` package paths, non-array runtime reflection
collections, entry-point/resource/target binding records with missing
loader-facing string fields, and target records without a string `target` become
structured runtime diagnostics instead of being treated as absent metadata.

`read_package()` remains strict and raises when required package metadata or the
artifact map is malformed. `read_compatibility_report()` is more useful for
loader admission checks: when root metadata is missing or malformed, optional
debug metadata cannot be decoded, or `manifest.artifacts` is missing, empty, or
has an invalid package-relative path, it returns a report with structured reject
diagnostics such as `package.metadata.missing`, `package.metadata.invalid`,
`package.debug_metadata.invalid`, `package.artifacts.missing`, or
`package.artifact.path_invalid` instead of guessing replacement artifacts.
Runtime artifact selection consumes those diagnostics and leaves the selected
artifact empty until the package contract fields are explicit and valid. The
reader also rejects duplicate `manifest.artifacts` package paths with
`package.artifact.path_duplicate` so loaders never infer artifact roles from a
shared filename.
Unsupported root metadata schema versions report the precise
`schemaVersion` path in the diagnostic summary.
When `manifest.packageArtifactRequirements` is present, the reader exposes that
record in `targetContract` and `packageArtifactRequirements` summaries and uses
its `requiredPathArtifacts`, `packageMode`,
`requiresNativeBinaryStatus`, `allowsPlannedNativeBinary`, and
`allowsPlannedNativeSourceEvidence` fields for admission and loader artifact
selection. Malformed records, unknown requirement fields, and unknown
`manifest.artifacts` fields are not interpreted as future runtime support; the
compatibility report rejects them with structured diagnostics such as
`package.artifact_requirements.unexpected_field` or
`package.artifact.unexpected`. Recorded target, package mode, and native status
flags must also agree with the manifest target and the runtime v0 target
contract; contradictions are reported as
`package.artifact_requirements.*_mismatch` diagnostics instead of falling back
to legacy defaults. Requirement-source fields are runtime-derived: manifest
fields such as `requirementsSource`, `requirements_source`, or `contractSource`
are rejected with `package.artifact_requirements.*_source_invalid` diagnostics
instead of letting a package choose legacy or recorded loader behavior. If a
recorded requirements object declares an unsupported `schemaVersion` or unknown
contract keys, the runtime rejects that metadata as recorded-package contract
drift and does not reconcile its fields against the legacy generated v0 target
contract. DirectX may record a source-free native descriptor boundary for
emitted DXIL by declaring native requirements over only `nativeBinary`, without
`nativeBinaryStatus` or planned-native fallback flags. Older manifests without
the field continue to use the legacy v0 target contract table below and report
`admission.requirements.legacyInferred: true`.

Root JSON metadata (`manifest.json`, `reflection.json`, and
`diagnostics.json`) and optional `debugMetadata` JSON are read through a bounded
runtime metadata path. The default limit is exposed as
`runtime.package_reader.RUNTIME_METADATA_JSON_BYTE_LIMIT` and in compatibility
report summaries as `runtime.metadataJsonByteLimit`. Oversized root metadata is
reported as `package.metadata.too_large`; oversized debug metadata is reported
as `package.debug_metadata.too_large`. In both cases the reader rejects the
package without parsing CrossGL source or trying to infer replacement metadata.

The low-level `package.package_mode` and `runtime_artifact()` helpers remain
status-oriented: `package.package_mode` is `native` only when
`manifest.artifacts.nativeBinaryStatus` is `emitted` or `validated`.
`runtime_artifact("native")` requires an emitted/validated `nativeBinary`; if
the manifest says the native binary is still `planned`, the reader raises a
specific error instead of falling through to a missing file. Target-aware
runtime admission should use `read_compatibility_report()`,
`select_runtime_artifact()`, or `read_loader_plan()` because those APIs also
apply `packageArtifactRequirements` and the v0 target contract, including
Metal and Vulkan native contracts where `nativeBinaryStatus` is forbidden.

The runtime API also exposes `require_artifact(name)` for a required manifest
key, `require_existing_artifact(name)` for a required file, and convenience
selectors for the standard `backendSource` and `nativeBinary` artifacts. These
helpers make artifact access explicit for future Metal, Vulkan, DirectX, and
OpenGL loaders without adding graphics API behavior here.
For legacy manifests, `required_target_artifacts()` and
`compatibility_report()` use the current v0 target package contract:

| Target | Contract mode | Required artifacts | Native status |
| --- | --- | --- | --- |
| `metal` | `native` | `backendSource`, `intermediate`, `nativeBinary` | forbidden |
| `vulkan` | `native` | `backendAssembly`, `nativeBinary` | forbidden |
| `directx` | `source-package` | `backendSource`, `nativeBinary` | `planned` or `emitted` |
| `opengl` | `source-package` | `backendSource`, `nativeBinary` | `planned` or `validated` |

Run it directly with:

```sh
python -m runtime.package_reader path/to/package.cglb --json
python -m runtime.package_reader path/to/package.cglb --compatibility-report --loader-target metal
```

The current reader accepts schema version `1` directory packages and zip-backed
`.cglb` packages with metadata at the archive root or under one top-level
directory. It rejects archives that expose conflicting root metadata locations,
such as both root-level metadata and a prefixed package metadata set. It performs
basic metadata checks and package-relative artifact path normalization, but it is
not a replacement for `cglc package verify` or the JSON schema validators.
