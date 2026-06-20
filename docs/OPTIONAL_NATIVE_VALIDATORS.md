# Optional Native Validator Tests

CTest registration discovers native shader tools in
`tests/cmake/CrossGLOptionalNativeTools.cmake`. These tools are optional for
developer machines and CI jobs. Missing tools should produce skipped CTest
sentinels instead of configure failures or silently disappearing coverage.

## V0 Policy Manifest

The JSON block below is the checked v0 policy source for optional native
validator behavior. Update it with any optional native tool behavior change and
run `python tools/check_optional_native_validator_policy.py --root .`.

<!-- crossgl-optional-native-validator-policy-v1:begin -->
```json
{
  "schemaVersion": 1,
  "policy": "crossgl-optional-native-validator-policy-v0",
  "toolchainReportEvidence": {
    "tools": [
      "spirv-as",
      "spirv-val",
      "spirv-opt",
      "dxc",
      "glslangValidator",
      "xcrun metal",
      "xcrun metallib"
    ],
    "doctorToolRows": {
      "spirv-as": "spirv-as",
      "spirv-val": "spirv-val",
      "spirv-opt": "spirv-opt",
      "dxc": "dxc",
      "glslangValidator": "glslangValidator",
      "xcrun metal": "metal",
      "xcrun metallib": "metallib"
    },
    "states": [
      {
        "state": "tool-missing",
        "evidenceStatus": "tool-missing",
        "available": false,
        "probeStatus": "unavailable",
        "version": "empty",
        "versionDetail": "empty"
      },
      {
        "state": "probe-failed",
        "evidenceStatus": "probe-failed",
        "available": true,
        "probeStatus": "failed",
        "version": "empty",
        "versionDetail": "required"
      },
      {
        "state": "version-unknown",
        "evidenceStatus": "version-unknown",
        "available": true,
        "probeStatus": "version-unknown",
        "version": "empty",
        "versionDetail": "required"
      },
      {
        "state": "version-captured",
        "evidenceStatus": "version-captured",
        "available": true,
        "probeStatus": "succeeded",
        "version": "required",
        "versionDetail": "empty"
      }
    ]
  },
  "tools": [
    {
      "tool": "spirv-as",
      "target": "vulkan",
      "requiredVariables": [
        "CROSSGL_SPIRV_AS"
      ],
      "availabilityGate": "CROSSGL_HAS_VULKAN_NATIVE_TOOLS",
      "toolPresentFailure": {
        "diagnosticCode": "vulkan.assemble-failed",
        "packageResult": "fail-no-package",
        "releaseClaimPolicy": "blocks-native-release-evidence",
        "ctestEvidence": [
          "cglc_build_vulkan_native_fake_spirv_as_planned_failure"
        ],
        "blockedSupportClaims": [
          "cglc_vulkan_toolchain_native_smoke"
        ]
      },
      "claimedSupportEvidence": [
        "cglc_vulkan_toolchain_native_smoke"
      ],
      "missingToolBehavior": {
        "diagnosticCode": "vulkan.spirv-as-missing",
        "packageResult": "fail-no-package",
        "releaseClaimPolicy": "explicit-unavailable-is-not-native-evidence"
      },
      "missingToolFallbackCoverage": [
        "cglc_build_vulkan_native_fake_spirv_as_unavailable_planned_failure"
      ],
      "missingToolSentinels": [
        "cglc_vulkan_toolchain_native_smoke_unavailable",
        "cglc_build_vulkan_native_tools_unavailable",
        "cglc_package_verify_json_schema_vulkan_native_unavailable"
      ]
    },
    {
      "tool": "spirv-val",
      "target": "vulkan",
      "requiredVariables": [
        "CROSSGL_SPIRV_VAL"
      ],
      "availabilityGate": "CROSSGL_HAS_VULKAN_NATIVE_TOOLS",
      "toolPresentFailure": {
        "diagnosticCode": "vulkan.validate-failed",
        "packageResult": "fail-no-package",
        "releaseClaimPolicy": "blocks-native-release-evidence",
        "ctestEvidence": [
          "cglc_build_vulkan_native_fake_spirv_val_planned_failure"
        ],
        "blockedSupportClaims": [
          "cglc_vulkan_toolchain_native_smoke"
        ]
      },
      "claimedSupportEvidence": [
        "cglc_vulkan_toolchain_native_smoke"
      ],
      "missingToolBehavior": {
        "diagnosticCode": "vulkan.spirv-val-missing",
        "packageResult": "fail-no-package",
        "releaseClaimPolicy": "explicit-unavailable-is-not-native-evidence"
      },
      "missingToolFallbackCoverage": [
        "cglc_build_vulkan_native_fake_spirv_val_unavailable_planned_failure"
      ],
      "missingToolSentinels": [
        "cglc_vulkan_toolchain_native_smoke_unavailable",
        "cglc_build_vulkan_native_tools_unavailable",
        "cglc_package_verify_json_schema_vulkan_native_unavailable"
      ]
    },
    {
      "tool": "spirv-opt",
      "target": "vulkan",
      "requiredVariables": [
        "CROSSGL_SPIRV_OPT"
      ],
      "availabilityGate": "CROSSGL_HAS_VULKAN_SPIRV_OPT",
      "toolPresentFailure": {
        "diagnosticCode": "vulkan.optimize-failed",
        "packageResult": "fail-no-package",
        "releaseClaimPolicy": "blocks-native-release-evidence",
        "ctestEvidence": [
          "cglc_build_vulkan_native_fake_spirv_opt_planned_failure"
        ],
        "blockedSupportClaims": [
          "cglc_vulkan_toolchain_native_smoke"
        ]
      },
      "claimedSupportEvidence": [
        "cglc_vulkan_toolchain_native_smoke"
      ],
      "missingToolBehavior": {
        "metadataEvidence": [
          "debug.optimization.status=skipped-tool-missing"
        ],
        "packageResult": "metadata-only",
        "releaseClaimPolicy": "skipped-optimization-is-not-optimization-evidence"
      },
      "missingToolFallbackCoverage": [
        "cglc_build_vulkan_native_fake_spirv_success"
      ],
      "missingToolSentinels": [
        "cglc_vulkan_spirv_opt_native_smoke_unavailable"
      ]
    },
    {
      "tool": "spirv-dis",
      "target": "vulkan",
      "requiredVariables": [
        "CROSSGL_SPIRV_DIS"
      ],
      "availabilityGate": "CROSSGL_HAS_VULKAN_SPIRV_DIS",
      "toolPresentFailure": {
        "diagnosticCode": "vulkan.disassemble-failed",
        "packageResult": "metadata-only",
        "releaseClaimPolicy": "failed-disassembly-is-not-disassembly-evidence",
        "metadataEvidence": [
          "debug.disassembly.status=failed",
          "debug.disassembly.path=null"
        ],
        "ctestEvidence": [
          "cglc_build_vulkan_native_fake_disassembly_tool_failure"
        ],
        "blockedSupportClaims": [
          "cglc_vulkan_toolchain_native_smoke"
        ]
      },
      "claimedSupportEvidence": [
        "cglc_vulkan_toolchain_native_smoke"
      ],
      "missingToolBehavior": {
        "metadataEvidence": [
          "debug.disassembly.status=skipped-tool-missing",
          "debug.disassembly.path=null"
        ],
        "packageResult": "metadata-only",
        "releaseClaimPolicy": "skipped-disassembly-is-not-disassembly-evidence"
      },
      "missingToolFallbackCoverage": [
        "cglc_build_vulkan_native_fake_disassembly_unavailable"
      ],
      "missingToolSentinels": [
        "cglc_vulkan_spirv_dis_native_smoke_unavailable"
      ]
    },
    {
      "tool": "dxc",
      "target": "directx",
      "requiredVariables": [
        "CROSSGL_DXC"
      ],
      "availabilityGate": "CROSSGL_HAS_DIRECTX_NATIVE_VALIDATOR",
      "toolPresentFailure": {
        "diagnosticCode": "directx.dxc-failed",
        "packageResult": "source-package-planned-warning",
        "releaseClaimPolicy": "planned-status-is-not-native-evidence",
        "ctestEvidence": [
          "cglc_build_directx_source_package_fake_dxc_tool_failure",
          "cglc_build_directx_graphics_resources_fake_dxc_tool_failure"
        ],
        "blockedSupportClaims": [
          "cglc_directx_toolchain_native_smoke"
        ]
      },
      "claimedSupportEvidence": [
        "cglc_directx_toolchain_native_smoke"
      ],
      "missingToolBehavior": {
        "diagnosticCode": "directx.source-package-only",
        "packageResult": "source-package-planned-warning",
        "releaseClaimPolicy": "planned-status-is-not-native-evidence"
      },
      "missingToolFallbackCoverage": [
        "cglc_build_directx_source_package_fake_dxc_unavailable",
        "cglc_build_directx_graphics_resources_fake_dxc_unavailable"
      ],
      "missingToolSentinels": [
        "cglc_directx_toolchain_native_smoke_unavailable",
        "cglc_build_directx_storage_buffer_dxc_unavailable"
      ]
    },
    {
      "tool": "glslangValidator",
      "target": "opengl",
      "requiredVariables": [
        "CROSSGL_GLSLANG_VALIDATOR"
      ],
      "availabilityGate": "CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR",
      "toolPresentFailure": {
        "diagnosticCode": "opengl.glslang-failed",
        "packageResult": "source-package-planned-warning",
        "releaseClaimPolicy": "planned-status-is-not-validated-evidence",
        "ctestEvidence": [
          "cglc_build_opengl_source_package_fake_glslang_tool_failure",
          "cglc_build_opengl_graphics_fake_glslang_fragment_tool_failure"
        ],
        "blockedSupportClaims": [
          "cglc_opengl_toolchain_native_smoke"
        ]
      },
      "claimedSupportEvidence": [
        "cglc_opengl_toolchain_native_smoke"
      ],
      "missingToolBehavior": {
        "diagnosticCode": "opengl.source-package-only",
        "packageResult": "source-package-planned-warning",
        "releaseClaimPolicy": "planned-status-is-not-validated-evidence"
      },
      "missingToolFallbackCoverage": [
        "cglc_build_opengl_source_package_fake_glslang_unavailable"
      ],
      "missingToolSentinels": [
        "cglc_opengl_toolchain_native_smoke_unavailable",
        "cglc_build_opengl_storage_buffer_glsl_validator_unavailable"
      ]
    },
    {
      "tool": "xcrun metal",
      "target": "metal",
      "requiredVariables": [
        "CROSSGL_XCRUN",
        "CROSSGL_METAL"
      ],
      "availabilityGate": "CROSSGL_HAS_METAL_NATIVE_TOOLS",
      "toolPresentFailure": {
        "diagnosticCode": "metal.compile-failed",
        "packageResult": "fail-no-package",
        "releaseClaimPolicy": "blocks-native-release-evidence",
        "ctestEvidence": [
          "cglc_build_metal_native_fake_xcrun_metal_tool_failure"
        ],
        "blockedSupportClaims": [
          "cglc_metal_toolchain_native_smoke"
        ]
      },
      "claimedSupportEvidence": [
        "cglc_metal_toolchain_native_smoke"
      ],
      "missingToolBehavior": {
        "diagnosticCode": "metal.xcrun-missing",
        "packageResult": "fail-no-package",
        "releaseClaimPolicy": "explicit-unavailable-is-not-native-evidence"
      },
      "missingToolFallbackCoverage": [
        "cglc_build_metal_native_fake_xcrun_unavailable"
      ],
      "missingToolSentinels": [
        "cglc_metal_toolchain_native_smoke_unavailable",
        "cglc_build_metal_native_tools_unavailable",
        "cglc_build_metal_source_package_native_tools_unavailable",
        "cglc_package_verify_json_schema_metal_native_unavailable"
      ]
    },
    {
      "tool": "xcrun metallib",
      "target": "metal",
      "requiredVariables": [
        "CROSSGL_XCRUN",
        "CROSSGL_METALLIB"
      ],
      "availabilityGate": "CROSSGL_HAS_METAL_NATIVE_TOOLS",
      "toolPresentFailure": {
        "diagnosticCode": "metal.library-failed",
        "packageResult": "fail-no-package",
        "releaseClaimPolicy": "blocks-native-release-evidence",
        "ctestEvidence": [
          "cglc_build_metal_native_fake_xcrun_metallib_tool_failure"
        ],
        "blockedSupportClaims": [
          "cglc_metal_toolchain_native_smoke"
        ]
      },
      "claimedSupportEvidence": [
        "cglc_metal_toolchain_native_smoke"
      ],
      "missingToolBehavior": {
        "diagnosticCode": "metal.xcrun-missing",
        "packageResult": "fail-no-package",
        "releaseClaimPolicy": "explicit-unavailable-is-not-native-evidence"
      },
      "missingToolFallbackCoverage": [
        "cglc_build_metal_native_fake_xcrun_unavailable"
      ],
      "missingToolSentinels": [
        "cglc_metal_toolchain_native_smoke_unavailable",
        "cglc_build_metal_native_tools_unavailable",
        "cglc_build_metal_source_package_native_tools_unavailable",
        "cglc_package_verify_json_schema_metal_native_unavailable"
      ]
    }
  ],
  "skippedSentinels": [
    {
      "name": "cglc_vulkan_toolchain_native_smoke_unavailable",
      "target": "vulkan",
      "requiredVariables": [
        "CROSSGL_SPIRV_AS",
        "CROSSGL_SPIRV_VAL"
      ],
      "labels": [
        "optional-native",
        "vulkan-native",
        "native-tool-unavailable"
      ]
    },
    {
      "name": "cglc_build_vulkan_native_tools_unavailable",
      "target": "vulkan",
      "requiredVariables": [
        "CROSSGL_SPIRV_AS",
        "CROSSGL_SPIRV_VAL"
      ],
      "labels": [
        "optional-native",
        "vulkan-native",
        "native-tool-unavailable"
      ]
    },
    {
      "name": "cglc_package_verify_json_schema_vulkan_native_unavailable",
      "target": "vulkan",
      "requiredVariables": [
        "CROSSGL_SPIRV_AS",
        "CROSSGL_SPIRV_VAL"
      ],
      "labels": [
        "optional-native",
        "vulkan-native",
        "native-tool-unavailable"
      ]
    },
    {
      "name": "cglc_vulkan_spirv_opt_native_smoke_unavailable",
      "target": "vulkan",
      "requiredVariables": [
        "CROSSGL_SPIRV_OPT"
      ],
      "labels": [
        "optional-native",
        "vulkan-native",
        "native-tool-unavailable"
      ]
    },
    {
      "name": "cglc_vulkan_spirv_dis_native_smoke_unavailable",
      "target": "vulkan",
      "requiredVariables": [
        "CROSSGL_SPIRV_DIS"
      ],
      "labels": [
        "optional-native",
        "vulkan-native",
        "native-tool-unavailable"
      ]
    },
    {
      "name": "cglc_directx_toolchain_native_smoke_unavailable",
      "target": "directx",
      "requiredVariables": [
        "CROSSGL_DXC"
      ],
      "labels": [
        "optional-native",
        "directx-native",
        "native-tool-unavailable"
      ]
    },
    {
      "name": "cglc_build_directx_storage_buffer_dxc_unavailable",
      "target": "directx",
      "requiredVariables": [
        "CROSSGL_DXC"
      ],
      "labels": [
        "optional-native",
        "directx-native",
        "native-tool-unavailable"
      ]
    },
    {
      "name": "cglc_opengl_toolchain_native_smoke_unavailable",
      "target": "opengl",
      "requiredVariables": [
        "CROSSGL_GLSLANG_VALIDATOR"
      ],
      "labels": [
        "optional-native",
        "opengl-native",
        "native-tool-unavailable"
      ]
    },
    {
      "name": "cglc_build_opengl_storage_buffer_glsl_validator_unavailable",
      "target": "opengl",
      "requiredVariables": [
        "CROSSGL_GLSLANG_VALIDATOR"
      ],
      "labels": [
        "optional-native",
        "opengl-native",
        "native-tool-unavailable"
      ]
    },
    {
      "name": "cglc_metal_toolchain_native_smoke_unavailable",
      "target": "metal",
      "requiredVariables": [
        "CROSSGL_XCRUN",
        "CROSSGL_METAL",
        "CROSSGL_METALLIB"
      ],
      "labels": [
        "optional-native",
        "metal-native",
        "native-tool-unavailable"
      ]
    },
    {
      "name": "cglc_build_metal_native_tools_unavailable",
      "target": "metal",
      "requiredVariables": [
        "CROSSGL_XCRUN",
        "CROSSGL_METAL",
        "CROSSGL_METALLIB"
      ],
      "labels": [
        "optional-native",
        "metal-native",
        "native-tool-unavailable"
      ]
    },
    {
      "name": "cglc_build_metal_source_package_native_tools_unavailable",
      "target": "metal",
      "requiredVariables": [
        "CROSSGL_XCRUN",
        "CROSSGL_METAL",
        "CROSSGL_METALLIB"
      ],
      "labels": [
        "optional-native",
        "metal-native",
        "native-tool-unavailable"
      ]
    },
    {
      "name": "cglc_package_verify_json_schema_metal_native_unavailable",
      "target": "metal",
      "requiredVariables": [
        "CROSSGL_XCRUN",
        "CROSSGL_METAL",
        "CROSSGL_METALLIB"
      ],
      "labels": [
        "optional-native",
        "metal-native",
        "native-tool-unavailable"
      ]
    }
  ]
}
```
<!-- crossgl-optional-native-validator-policy-v1:end -->

## Required Tool-Present Behavior

| Tool | Target | Present-but-failing behavior | Release evidence policy |
| --- | --- | --- | --- |
| `spirv-as` | Vulkan | Emit `vulkan.assemble-failed`, fail the package build, and publish no package. | Blocks native release evidence. |
| `spirv-val` | Vulkan | Emit `vulkan.validate-failed`, fail the package build, and publish no package. | Blocks native release evidence. |
| `spirv-opt` | Vulkan | For O2 Vulkan package builds, emit `vulkan.optimize-failed`, fail the package build, and publish no package. O0/O1 do not invoke it. | Blocks O2 optimization release evidence. |
| `spirv-dis` | Vulkan | Emit warning `vulkan.disassemble-failed`, keep the package build valid, and record `debug.disassembly.status=failed` with `debug.disassembly.path=null`. | Failed disassembly is not disassembly evidence. |
| `dxc` | DirectX | Emit warning `directx.dxc-failed`, keep a planned source package, and do not use the run as DXIL evidence. | `planned` status is not native evidence. |
| `glslangValidator` | OpenGL | Emit warning `opengl.glslang-failed`, keep a planned source package, and do not use the run as validated GLSL evidence. | `planned` status is not validated evidence. |
| `xcrun metal` | Metal | Emit `metal.compile-failed`, fail the package build, and publish no package. | Blocks native release evidence. |
| `xcrun metallib` | Metal | Emit `metal.library-failed`, fail the package build, and publish no package. | Blocks native release evidence. |

`tools/check_optional_native_validator_policy.py` makes this split executable:
tool-present Vulkan and Metal package-tool failures must assert no promoted
package, while DirectX and OpenGL validator failures must assert planned
source-package status, absent native binary output, and no native or validated
success evidence. Each `toolPresentFailure` also lists
`blockedSupportClaims`, which must match the claimed-support CTest evidence
that a present-but-failing tool invalidates.

## Claimed-Support Smoke Evidence

Real toolchain smoke tests are the CTest evidence for claimed native or
validated support. They are registered only when the relevant host tools are
present, and any real compiler, validator, package verification, or claimed
artifact/status failure is a CTest failure. Missing tools register the matching
skipped sentinel instead of silently removing the evidence lane.

| Target | Claimed-support CTest | Missing-tool sentinel | Claimed evidence |
| --- | --- | --- | --- |
| Vulkan | `cglc_vulkan_toolchain_native_smoke` | `cglc_vulkan_toolchain_native_smoke_unavailable` | SPIR-V package is assembled, validated, reassembled, and verified. |
| DirectX | `cglc_directx_toolchain_native_smoke` | `cglc_directx_toolchain_native_smoke_unavailable` | DXIL package records `nativeBinaryStatus: "emitted"` and verifies. |
| OpenGL | `cglc_opengl_toolchain_native_smoke` | `cglc_opengl_toolchain_native_smoke_unavailable` | GLSL package records `nativeBinaryStatus: "validated"` and verifies. |
| Metal | `cglc_metal_toolchain_native_smoke` | `cglc_metal_toolchain_native_smoke_unavailable` | Metal package emits AIR/metallib and verifies with native package mode, `summary.nativeBinaryStatus: null`, and healthy native artifact descriptor evidence. |

## Doctor and Toolchain Report Evidence

Doctor JSON, doctor text, and embedded doctor target reports must keep optional
native tools as explicit tool rows, not implicit failures. The report states
below apply to `spirv-as`, `spirv-val`, `spirv-opt`, `dxc`,
`glslangValidator`, and the Metal tool rows that represent `xcrun metal` and
`xcrun metallib`:

| Report state | `evidenceStatus` | `available` | `probeStatus` | `version` | `versionDetail` | Meaning |
| --- | --- | --- | --- | --- | --- | --- |
| `tool-missing` | `tool-missing` | `false` | `unavailable` | Empty | Empty | The tool was not found. This is skip/metadata evidence for optional tools, not a compilation failure by itself. |
| `probe-failed` | `probe-failed` | `true` | `failed` | Empty | Required | The tool was found, but the local version probe failed or could not launch. |
| `version-unknown` | `version-unknown` | `true` | `version-unknown` | Empty | Required | The tool was found and the version probe completed, but emitted no usable version text. |
| `version-captured` | `version-captured` | `true` | `succeeded` | Required | Empty | The tool was found and the first version output line was captured. |

For Apple Metal discovery, doctor/toolchain JSON keeps `name: "metal"` and
`name: "metallib"` with `source: "xcrun"` when `xcrun -find` resolves them.
The checked policy manifest maps those rows back to `xcrun metal` and
`xcrun metallib` for optional native validator evidence.

## Required Missing-Tool Behavior

| Tool | Target | Missing-tool behavior | Release evidence policy |
| --- | --- | --- | --- |
| `spirv-as` | Vulkan | Emit `vulkan.spirv-as-missing`, fail the package build, and publish no package. | Explicit unavailable evidence is not native evidence. |
| `spirv-val` | Vulkan | Emit `vulkan.spirv-val-missing`, fail the package build, and publish no package. | Explicit unavailable evidence is not native evidence. |
| `spirv-opt` | Vulkan | Keep Vulkan native tests gated on `spirv-as` and `spirv-val`. For O2 builds without `spirv-opt`, record `debug.optimization.status=skipped-tool-missing` and register a skipped optimization sentinel. O0/O1 record `skipped-disabled`. | Skipped optimization metadata is not optimization evidence. |
| `spirv-dis` | Vulkan | Keep Vulkan native tests gated on `spirv-as` and `spirv-val`, record `debug.disassembly.status=skipped-tool-missing` with `debug.disassembly.path=null`, and register a skipped disassembly sentinel. | Skipped disassembly metadata is not disassembly evidence. |
| `dxc` | DirectX | Emit warning `directx.source-package-only`, keep `nativeBinaryStatus: "planned"`, and record that no `dxc` command was invoked. | `planned` status is not native evidence. |
| `glslangValidator` | OpenGL | Emit warning `opengl.source-package-only`, keep `nativeBinaryStatus: "planned"`, and record skipped validation evidence. | `planned` status is not validated evidence. |
| `xcrun metal` | Metal | Emit `metal.xcrun-missing`, fail the package build, and publish no package. | Explicit unavailable evidence is not native evidence. |
| `xcrun metallib` | Metal | Emit `metal.xcrun-missing`, fail the package build, and publish no package. | Explicit unavailable evidence is not native evidence. |

<a id="optional-native-missing-tool-sentinel-coverage"></a>

## Missing-Tool Sentinel Coverage

The anchor IDs in this table are part of the local static evidence contract.
`tools/check_optional_native_validator_policy.py` checks them against the JSON
policy and CTest skip registrations so missing optional tools remain visible
without adding native-tool runtime work.

| Sentinel | Target | Required variables |
| --- | --- | --- |
| <a id="optional-native-sentinel-cglc-vulkan-toolchain-native-smoke-unavailable"></a>`cglc_vulkan_toolchain_native_smoke_unavailable` | Vulkan | `CROSSGL_SPIRV_AS`, `CROSSGL_SPIRV_VAL` |
| <a id="optional-native-sentinel-cglc-build-vulkan-native-tools-unavailable"></a>`cglc_build_vulkan_native_tools_unavailable` | Vulkan | `CROSSGL_SPIRV_AS`, `CROSSGL_SPIRV_VAL` |
| <a id="optional-native-sentinel-cglc-package-verify-json-schema-vulkan-native-unavailable"></a>`cglc_package_verify_json_schema_vulkan_native_unavailable` | Vulkan | `CROSSGL_SPIRV_AS`, `CROSSGL_SPIRV_VAL` |
| <a id="optional-native-sentinel-cglc-vulkan-spirv-opt-native-smoke-unavailable"></a>`cglc_vulkan_spirv_opt_native_smoke_unavailable` | Vulkan | `CROSSGL_SPIRV_OPT` |
| <a id="optional-native-sentinel-cglc-vulkan-spirv-dis-native-smoke-unavailable"></a>`cglc_vulkan_spirv_dis_native_smoke_unavailable` | Vulkan | `CROSSGL_SPIRV_DIS` |
| <a id="optional-native-sentinel-cglc-directx-toolchain-native-smoke-unavailable"></a>`cglc_directx_toolchain_native_smoke_unavailable` | DirectX | `CROSSGL_DXC` |
| <a id="optional-native-sentinel-cglc-build-directx-storage-buffer-dxc-unavailable"></a>`cglc_build_directx_storage_buffer_dxc_unavailable` | DirectX | `CROSSGL_DXC` |
| <a id="optional-native-sentinel-cglc-opengl-toolchain-native-smoke-unavailable"></a>`cglc_opengl_toolchain_native_smoke_unavailable` | OpenGL | `CROSSGL_GLSLANG_VALIDATOR` |
| <a id="optional-native-sentinel-cglc-build-opengl-storage-buffer-glsl-validator-unavailable"></a>`cglc_build_opengl_storage_buffer_glsl_validator_unavailable` | OpenGL | `CROSSGL_GLSLANG_VALIDATOR` |
| <a id="optional-native-sentinel-cglc-metal-toolchain-native-smoke-unavailable"></a>`cglc_metal_toolchain_native_smoke_unavailable` | Metal | `CROSSGL_XCRUN`, `CROSSGL_METAL`, `CROSSGL_METALLIB` |
| <a id="optional-native-sentinel-cglc-build-metal-native-tools-unavailable"></a>`cglc_build_metal_native_tools_unavailable` | Metal | `CROSSGL_XCRUN`, `CROSSGL_METAL`, `CROSSGL_METALLIB` |
| <a id="optional-native-sentinel-cglc-build-metal-source-package-native-tools-unavailable"></a>`cglc_build_metal_source_package_native_tools_unavailable` | Metal | `CROSSGL_XCRUN`, `CROSSGL_METAL`, `CROSSGL_METALLIB` |
| <a id="optional-native-sentinel-cglc-package-verify-json-schema-metal-native-unavailable"></a>`cglc_package_verify_json_schema_metal_native_unavailable` | Metal | `CROSSGL_XCRUN`, `CROSSGL_METAL`, `CROSSGL_METALLIB` |

## CMake Variables

Backend agents should reuse these variables instead of adding local
`find_program` calls:

- `CROSSGL_SPIRV_AS`: `spirv-as` for Vulkan SPIR-V assembly.
- `CROSSGL_SPIRV_VAL`: `spirv-val` for Vulkan SPIR-V validation.
- `CROSSGL_SPIRV_OPT`: `spirv-opt` for Vulkan SPIR-V optimization discovery.
- `CROSSGL_SPIRV_DIS`: `spirv-dis` for optional Vulkan SPIR-V disassembly
  sidecar evidence.
- `CROSSGL_DXC`: `dxc` for DirectX DXIL emission.
- `CROSSGL_GLSLANG_VALIDATOR`: `glslangValidator` for OpenGL GLSL validation.
- `CROSSGL_XCRUN`: Apple `xcrun` launcher.
- `CROSSGL_METAL`: Metal compiler path resolved through `xcrun -find metal`.
- `CROSSGL_METALLIB`: Metal library tool path resolved through
  `xcrun -find metallib`.
- `CROSSGL_HAS_VULKAN_NATIVE_TOOLS`: true when `spirv-as` and `spirv-val` are
  both available. `spirv-opt` is intentionally not part of this gate; when it is
  missing, O2 Vulkan package tests must report skipped optimization metadata and
  a `cglc_vulkan_spirv_opt_native_smoke_unavailable` sentinel.
- `CROSSGL_HAS_VULKAN_SPIRV_OPT`: true when `spirv-opt` is available.
- `CROSSGL_HAS_VULKAN_SPIRV_DIS`: true when `spirv-dis` is available.
- `CROSSGL_HAS_DIRECTX_NATIVE_VALIDATOR`: true when `dxc` is available.
- `CROSSGL_HAS_OPENGL_NATIVE_VALIDATOR`: true when `glslangValidator` is
  available.
- `CROSSGL_HAS_METAL_NATIVE_TOOLS`: true on Apple hosts when `xcrun`, `metal`,
  and `metallib` are all available.

Configure output also prints a Metal-specific optional-native line with either
the resolved `xcrun`, `metal`, and `metallib` paths or the exact missing
`CROSSGL_*` variables. Non-Apple hosts still register unavailable sentinels
instead of requiring the Apple toolchain.

## CTest Labels

Optional native tests use these labels:

- `optional-native`: any test requiring an optional native shader tool.
- `<target>-native`: target-specific grouping, such as `metal-native` or
  `vulkan-native`.
- `native-tool-available`: a tool-backed native test was registered.
- `native-tool-policy`: fake-tool coverage for failure or unavailable paths.
- `native-tool-unavailable`: a skipped sentinel was registered because a
  required tool is missing.

Use `crossgl_label_optional_native_test(<test> <target>)` for a single
tool-backed test, or `crossgl_label_new_optional_native_tests(<target>
<before-tests>)` after a guarded block. Use
`crossgl_label_optional_native_policy_test(<test> <target>)` for fake-tool
failure and unavailable policy coverage. Use
`crossgl_add_optional_native_skip_test(...)` in the missing-tool branch so CTest
reports an explicit `SKIP: optional native <target> unavailable` line with the
missing variable names.

## Policy Checker Contract

`tools/check_optional_native_validator_policy.py` is report-only. It must not
make `spirv-as`, `spirv-val`, `spirv-opt`, `dxc`, `glslangValidator`, `xcrun`,
`metal`, or `metallib` mandatory for configure, build, or local test runs.

The checker validates that each JSON policy tool has non-empty required
variables, missing-tool fallback CTest coverage, missing-tool sentinel coverage,
tool-present failure CTest evidence, `blockedSupportClaims`, and
claimed-support CTest evidence. Each
skipped sentinel must carry
`optional-native`, `<target>-native`, and `native-tool-unavailable` labels, and
must list the required variables that make the missing-tool state visible.

Sentinel names referenced by the JSON policy must appear in CTest registration
text or in explicit fixtures under `tests/optional-native-validator-policy/`,
must keep the `_unavailable` suffix, and must have exactly one matching
anchor in the Missing-Tool Sentinel Coverage table.
Tool-present and missing-tool fallback evidence must remain registered CTest
names, must carry `native-tool-policy` labels for the right target, and must
not assert successful native evidence when the fake validator has failed or is
unavailable. `blockedSupportClaims` must match the claimed-support evidence, so
present-but-failing tools explicitly fail the affected support lane. Claimed
support evidence must remain registered under `native-tool-available`, and its
matching tool-absent path must remain a `native-tool-unavailable` sentinel.

`tests/native-artifact-contract/evidence-rows.json` also records
`optionalToolEvidence` for each planned source-package descriptor fixture.
`tools/check_native_artifact_contract.py` cross-checks those entries against the
policy JSON above so planned DirectX and OpenGL evidence keeps naming the
optional tool, missing-tool diagnostic, and release-claim policy that prevent an
unavailable validator from being treated as native or validated coverage.
