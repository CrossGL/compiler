"""Runtime package metadata helpers for CrossGL directory packages."""

from .loader import (
    LoaderArtifactPlan,
    RuntimeLoaderPlan,
    read_loader_plan,
)
from .package_reader import (
    Artifact,
    CompatibilityDiagnostic,
    DebugMetadataRecord,
    PackageCompatibilityReport,
    PackageReadError,
    RuntimeArtifactSelection,
    RuntimePackage,
    TargetArtifactContract,
    read_compatibility_report,
    read_package,
    select_runtime_artifact,
)

__all__ = [
    "Artifact",
    "CompatibilityDiagnostic",
    "DebugMetadataRecord",
    "LoaderArtifactPlan",
    "PackageCompatibilityReport",
    "PackageReadError",
    "RuntimeArtifactSelection",
    "RuntimeLoaderPlan",
    "RuntimePackage",
    "TargetArtifactContract",
    "read_compatibility_report",
    "read_loader_plan",
    "read_package",
    "select_runtime_artifact",
]
