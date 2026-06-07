"""Generated CrossGL runtime package target contracts."""

# Derived from tools/package_target_contracts.json.
# Do not edit by hand.

SCHEMA_VERSION = 1

PACKAGE_DEBUG_ARTIFACTS = (
    "debugMetadata",
    "hirSourceMap",
)

PACKAGE_TARGET_CONTRACTS = (
    {
        "target": "metal",
        "requiredPathArtifacts": (
            "backendSource",
            "intermediate",
            "nativeBinary",
        ),
        "requiresNativeBinaryStatus": False,
        "allowsPlannedNativeBinary": False,
        "allowsPlannedNativeSourceEvidence": False,
    },
    {
        "target": "vulkan",
        "requiredPathArtifacts": (
            "backendAssembly",
            "nativeBinary",
        ),
        "requiresNativeBinaryStatus": False,
        "allowsPlannedNativeBinary": False,
        "allowsPlannedNativeSourceEvidence": False,
    },
    {
        "target": "directx",
        "requiredPathArtifacts": (
            "backendSource",
            "nativeBinary",
        ),
        "requiresNativeBinaryStatus": True,
        "allowsPlannedNativeBinary": True,
        "allowsPlannedNativeSourceEvidence": True,
    },
    {
        "target": "opengl",
        "requiredPathArtifacts": (
            "backendSource",
            "nativeBinary",
        ),
        "requiresNativeBinaryStatus": True,
        "allowsPlannedNativeBinary": True,
        "allowsPlannedNativeSourceEvidence": True,
    },
)

__all__ = (
    "SCHEMA_VERSION",
    "PACKAGE_DEBUG_ARTIFACTS",
    "PACKAGE_TARGET_CONTRACTS",
)
